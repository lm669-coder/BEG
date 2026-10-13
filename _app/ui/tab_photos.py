import hashlib
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, NamedTuple

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QProgressBar,
)
from PyQt6.QtCore import Qt, QSize, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QIcon, QImage, QImageReader, QPixmap

import database as db
import paths

BEG_BLUE = "#1a3a5c"
IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic"}
THUMB = 140
THUMB_DIR = ".thumbs"  # miniatures légères, à côté des photos (partagées)
MAX_SIDE = 2560  # côté max après réduction
REDUCE_ABOVE = 1_500_000  # on ne réduit que les JPEG plus lourds que 1,5 Mo
WORKERS = 4  # copies en parallèle (masque la latence du disque réseau)

# Les photos sont rangées à côté de la base : <dossier données>/Photos/<id chantier>/
PHOTOS_ROOT = os.path.join(paths.DATA_DIR, "Photos")


class ImportResult(NamedTuple):
    copied: int
    skipped: int
    reduced: int
    saved: int  # octets gagnés par la réduction
    cancelled: bool
    errors: list


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name.strip()).strip(" .") or "_"


def chantier_dir(id_chantier: str) -> str:
    return os.path.join(PHOTOS_ROOT, _safe(id_chantier))


def _is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMG_EXT


def _collect(paths_: list[str]) -> list[tuple[str, str]]:
    """(fichier, sous-dossier d'album) pour chaque image ; les dossiers sont
    parcourus récursivement et leur nom devient l'album."""
    out: list[tuple[str, str]] = []
    for p in paths_:
        if os.path.isdir(p):
            racine = os.path.dirname(os.path.normpath(p))
            for cur, _dirs, files in os.walk(p):
                album = os.path.relpath(cur, racine)
                for f in sorted(files):
                    fp = os.path.join(cur, f)
                    if _is_image(fp):
                        out.append((fp, "" if album == "." else album))
        elif os.path.isfile(p) and _is_image(p):
            out.append((p, ""))
    return out


def _unique(dest_dir: str, name: str, reserved: set[str]) -> str:
    base, ext = os.path.splitext(name)
    cand, i = os.path.join(dest_dir, name), 1
    while os.path.exists(cand) or cand in reserved:
        cand = os.path.join(dest_dir, f"{base}_{i}{ext}")
        i += 1
    return cand


# ── Miniatures ────────────────────────────────────────────────────────────
def thumb_path(id_base: str, photo: str) -> str:
    rel = os.path.relpath(photo, id_base).lower()
    return os.path.join(
        id_base, THUMB_DIR, hashlib.md5(rel.encode("utf-8")).hexdigest() + ".jpg"
    )


def _read_scaled(src: str, side: int) -> QImage:
    reader = QImageReader(src)
    reader.setAutoTransform(True)
    sz = reader.size()
    if sz.isValid():  # décodage réduit : rapide même pour de grosses photos
        sz.scale(side, side, Qt.AspectRatioMode.KeepAspectRatio)
        reader.setScaledSize(sz)
    return reader.read()


def make_thumb(src: str, dst: str) -> QImage:
    """Crée la miniature `dst` (JPEG ~10 Ko) depuis `src` ; retourne l'image."""
    img = _read_scaled(src, THUMB * 2)
    if not img.isNull():
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        img.save(dst, "JPG", 85)
    return img


def load_thumb(id_base: str, photo: str) -> QImage:
    """Miniature en cache (rapide) ou, à défaut, générée depuis la photo."""
    tp = thumb_path(id_base, photo)
    if os.path.isfile(tp):
        img = QImage(tp)
        if not img.isNull():
            return img
    return make_thumb(photo, tp)


# ── Import ────────────────────────────────────────────────────────────────
def _copy_or_reduce(src: str, dest: str, reduce: bool) -> bool:
    """Copie `src` vers `dest` ; réduit les gros JPEG (EXIF/ICC conservés).
    Retourne True si l'image a été réduite."""
    ext = os.path.splitext(src)[1].lower()
    if reduce and ext in (".jpg", ".jpeg") and os.path.getsize(src) > REDUCE_ABOVE:
        try:
            from PIL import Image

            with Image.open(src) as im:
                if max(im.size) > MAX_SIDE or os.path.getsize(src) > 3 * REDUCE_ABOVE:
                    exif = im.info.get("exif")
                    icc = im.info.get("icc_profile")
                    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
                    kw = {"quality": 85}
                    if exif:
                        kw["exif"] = exif
                    if icc:
                        kw["icc_profile"] = icc
                    im.convert("RGB").save(dest, "JPEG", **kw)
                    return True
        except Exception:
            if os.path.exists(dest):
                os.remove(dest)  # on retombe sur la copie brute
    shutil.copyfile(src, dest)  # (pas copy2 : moins d'appels réseau)
    return False


def import_photos(
    id_chantier: str,
    paths_: list[str],
    reduce: bool = True,
    progress: Callable[[int, int, str], None] | None = None,
    cancel: Callable[[], bool] | None = None,
    workers: int = WORKERS,
) -> ImportResult:
    """Copie photos/dossiers dans le dossier du chantier (en parallèle)."""
    base = chantier_dir(id_chantier)
    items = _collect(paths_)
    reserved: set[str] = set()
    plan: list[tuple[str, str]] = []
    for src, album in items:
        dest_dir = os.path.join(base, *[_safe(x) for x in album.split(os.sep) if x])
        os.makedirs(dest_dir, exist_ok=True)
        dest = _unique(dest_dir, os.path.basename(src), reserved)
        reserved.add(dest)
        plan.append((src, dest))

    def one(src: str, dest: str):
        if cancel and cancel():
            return ("cancel", 0, 0)
        try:
            before = os.path.getsize(src)
            reduced = _copy_or_reduce(src, dest, reduce)
            saved = before - os.path.getsize(dest) if reduced else 0
            try:  # la miniature est faite depuis la source (locale = rapide)
                make_thumb(src, thumb_path(base, dest))
            except Exception:
                pass
            return ("ok", int(reduced), saved)
        except Exception as e:
            if os.path.exists(dest):
                try:
                    os.remove(dest)
                except OSError:
                    pass
            return ("err", 0, f"{os.path.basename(src)} : {e}")

    copied = reduced = saved = 0
    errors: list[str] = []
    cancelled = False
    total = len(plan)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(one, s, d): s for s, d in plan}
        done = 0
        for fut in as_completed(futs):
            done += 1
            status, a, b = fut.result()
            if status == "ok":
                copied += 1
                reduced += a
                saved += b
            elif status == "err":
                errors.append(b)
            else:
                cancelled = True
            if progress:
                progress(done, total, os.path.basename(futs[fut]))
    return ImportResult(copied, total - copied, reduced, saved, cancelled, errors)


def list_photos(id_chantier: str) -> list[str]:
    base = chantier_dir(id_chantier)
    res = []
    for cur, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != THUMB_DIR]
        res += [os.path.join(cur, f) for f in sorted(files) if _is_image(f)]
    return sorted(res)


def _paths_from_mime(mime) -> list[str]:
    return [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]


# ── Threads ───────────────────────────────────────────────────────────────
class ImportWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished_import = pyqtSignal(object)

    def __init__(self, id_chantier: str, paths_: list[str], reduce: bool, parent=None):
        super().__init__(parent)
        self._args = (id_chantier, paths_, reduce)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            res = import_photos(
                *self._args,
                progress=lambda d, t, n: self.progress.emit(d, t, n),
                cancel=lambda: self._cancel,
            )
        except Exception as e:  # ne jamais laisser une exception tuer le thread
            res = ImportResult(0, 0, 0, 0, False, [str(e)])
        self.finished_import.emit(res)


class ThumbWorker(QThread):
    ready = pyqtSignal(int, int, QImage)  # génération, index, miniature

    def __init__(self, gen: int, base: str, photos: list[str], parent=None):
        super().__init__(parent)
        self._gen, self._base, self._photos = gen, base, photos
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for i, p in enumerate(self._photos):
            if self._stop:
                return
            try:
                img = load_thumb(self._base, p)
            except Exception:
                continue
            if not img.isNull():
                self.ready.emit(self._gen, i, img)


class PhotosTab(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._gen = 0  # génération de chargement des miniatures
        self._import: ImportWorker | None = None
        self._import_id = ""
        self._thumb_workers: list[ThumbWorker] = []
        self.setAcceptDrops(True)
        self._build()

    # ── UI ────────────────────────────────────────────────────────────────
    def _build(self):
        vl = QVBoxLayout(self)
        vl.setContentsMargins(16, 12, 16, 12)

        title = QLabel("Photos de chantier")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{BEG_BLUE};")
        vl.addWidget(title)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("ID chantier :"))
        self._id = QLineEdit()
        self._id.setFixedWidth(160)
        self._id.setReadOnly(True)  # suit l'ID saisi dans le Formulaire
        self._id.setPlaceholderText("(ID du Formulaire)")
        self._id.setToolTip("L'onglet suit l'ID chantier saisi dans l'onglet Formulaire.")
        hl.addWidget(self._id)
        self._info = QLabel("")
        self._info.setStyleSheet(f"color:{BEG_BLUE};")
        hl.addWidget(self._info, 1)

        self._btn_add = QPushButton("➕ Ajouter des photos…")
        self._btn_add.clicked.connect(self._pick_files)
        self._btn_dir = QPushButton("📁 Ajouter un dossier…")
        self._btn_dir.clicked.connect(self._pick_folder)
        btn_open = QPushButton("📂 Ouvrir le dossier")
        btn_open.setObjectName("btn_secondary")
        btn_open.clicked.connect(self._open_folder)
        btn_del = QPushButton("🗑 Supprimer la sélection")
        btn_del.setObjectName("btn_danger")
        btn_del.clicked.connect(self._delete_selected)
        for b in (self._btn_add, self._btn_dir, btn_open, btn_del):
            hl.addWidget(b)
        vl.addLayout(hl)

        self._chk_reduce = QCheckBox(
            f"Réduire les grosses photos à l'import (max {MAX_SIDE} px, qualité 85 — "
            "5 à 10 × plus léger, date/GPS conservés)"
        )
        self._chk_reduce.setChecked(True)
        vl.addWidget(self._chk_reduce)

        self._drop = QLabel(
            "Glissez-déposez ici des photos ou des dossiers de photos "
            "(depuis l'Explorateur, le bureau, OneDrive…)"
        )
        self._drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop.setMinimumHeight(70)
        self._set_drop_style(False)
        vl.addWidget(self._drop)

        # Progression de l'import (visible seulement pendant une copie)
        self._prog_row = QWidget()
        pl = QHBoxLayout(self._prog_row)
        pl.setContentsMargins(0, 0, 0, 0)
        self._bar = QProgressBar()
        self._prog_lbl = QLabel("")
        self._btn_cancel = QPushButton("✖ Annuler")
        self._btn_cancel.setObjectName("btn_danger")
        self._btn_cancel.clicked.connect(self._cancel_import)
        pl.addWidget(self._bar, 2)
        pl.addWidget(self._prog_lbl, 3)
        pl.addWidget(self._btn_cancel)
        self._prog_row.setVisible(False)
        vl.addWidget(self._prog_row)

        self._list = QListWidget()
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setIconSize(QSize(THUMB, THUMB))
        self._list.setGridSize(QSize(THUMB + 24, THUMB + 40))
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setWordWrap(True)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.setAcceptDrops(False)
        self._list.itemDoubleClicked.connect(
            lambda it: QDesktopServices.openUrl(
                QUrl.fromLocalFile(it.data(Qt.ItemDataRole.UserRole))
            )
        )
        vl.addWidget(self._list, 1)

        self._count = QLabel("")
        vl.addWidget(self._count)

    def _set_drop_style(self, active: bool):
        color = "#2e86de" if active else "#9fb3c8"
        bg = "#eaf3ff" if active else "#f6f9fc"
        self._drop.setStyleSheet(
            f"border:2px dashed {color}; border-radius:8px; background:{bg};"
            f"color:{BEG_BLUE}; font-weight:bold;"
        )

    # ── Données ───────────────────────────────────────────────────────────
    def set_chantier(self, id_chantier: str):
        """Appelé par le Formulaire à chaque changement d'ID (ou nouveau bilan vierge)."""
        if self._import is not None:  # import en cours : on ne change pas de chantier
            return
        self._id.setText((id_chantier or "").strip())
        self._load()

    def _current_id(self) -> str:
        return self._id.text().strip()

    def refresh(self):
        """L'onglet suit l'ID chantier saisi dans le Formulaire."""
        if self._import is None:
            form = getattr(self._main, "tab_form", None)
            self._id.setText(form._id_chantier.text().strip() if form is not None else "")
        self._load()

    def _load(self):
        id_c = self._current_id()
        self._stop_thumbs()
        self._list.clear()
        ch = db.get_chantier(id_c) if id_c else None
        self._info.setText(
            f"{ch.get('intitule') or ''} — {ch.get('client') or ''}" if ch else ""
        )
        if not id_c:  # pas d'ID : rien n'est chargé
            self._count.setText(
                "Aucun ID chantier : saisissez-le dans le Formulaire pour voir et ajouter des photos."
            )
            return
        base = chantier_dir(id_c)
        photos = list_photos(id_c)
        # Les lignes apparaissent tout de suite ; les miniatures arrivent d'un thread
        # (jamais de lecture de photo complète sur le fil de l'interface).
        for path in photos:
            album = os.path.relpath(os.path.dirname(path), base)
            it = QListWidgetItem(os.path.basename(path))
            it.setData(Qt.ItemDataRole.UserRole, path)
            it.setToolTip(path if album == "." else f"{album}\n{path}")
            self._list.addItem(it)
        self._count.setText(f"{len(photos)} photo(s) — {base}")
        if photos:
            self._gen += 1
            w = ThumbWorker(self._gen, base, photos)
            w.ready.connect(self._on_thumb)
            w.finished.connect(lambda w=w: self._forget_worker(w))
            self._thumb_workers.append(w)
            w.start()

    def _forget_worker(self, w):
        if w in self._thumb_workers:
            self._thumb_workers.remove(w)

    def _on_thumb(self, gen: int, idx: int, img: QImage):
        if gen != self._gen or idx >= self._list.count():
            return
        self._list.item(idx).setIcon(QIcon(QPixmap.fromImage(img)))

    def _stop_thumbs(self):
        for w in self._thumb_workers:
            w.stop()

    # ── Import ────────────────────────────────────────────────────────────
    def import_paths(self, paths_: list[str]):
        id_c = self._current_id()
        if not id_c:
            QMessageBox.information(
                self, "Photos", "Saisissez d'abord l'ID du chantier concerné."
            )
            return
        if self._import is not None:
            self._main.status("Un import est déjà en cours.")
            return
        self._import_id = id_c
        self._set_importing(True)
        self._bar.setRange(0, 0)  # indéterminé le temps de lister les fichiers
        self._prog_lbl.setText("Préparation…")
        w = ImportWorker(id_c, paths_, self._chk_reduce.isChecked(), self)
        w.progress.connect(self._on_progress)
        w.finished_import.connect(self._on_import_done)
        self._import = w
        w.start()

    def _set_importing(self, on: bool):
        self._prog_row.setVisible(on)
        for b in (self._btn_add, self._btn_dir, self._chk_reduce):
            b.setEnabled(not on)

    def _on_progress(self, done: int, total: int, name: str):
        self._bar.setRange(0, max(total, 1))
        self._bar.setValue(done)
        self._prog_lbl.setText(f"{done} / {total} — {name}")

    def _cancel_import(self):
        if self._import is not None:
            self._import.cancel()
            self._prog_lbl.setText("Annulation en cours…")

    def _on_import_done(self, res: ImportResult):
        w, self._import = self._import, None
        if w is not None:
            w.wait(2000)
            w.deleteLater()
        self._set_importing(False)
        self.refresh()
        msg = f"{res.copied} photo(s) ajoutée(s) au chantier {self._import_id}"
        if res.reduced:
            msg += f", {res.reduced} réduite(s) (−{res.saved / 1e6:.0f} Mo)"
        if res.cancelled:
            msg += " — import annulé"
        if res.errors:
            msg += f" — {len(res.errors)} erreur(s)"
        elif not res.copied and not res.cancelled:
            msg = "Aucune image reconnue dans ce qui a été déposé."
        self._main.status(msg)
        if res.errors:
            QMessageBox.warning(
                self,
                "Photos",
                "Certaines photos n'ont pas pu être copiées :\n\n"
                + "\n".join(res.errors[:10]),
            )

    def shutdown(self):
        """À appeler avant la fermeture : arrête proprement les threads."""
        if self._import is not None:
            self._import.cancel()
            self._import.wait(8000)
        self._stop_thumbs()
        for w in list(self._thumb_workers):
            w.wait(3000)

    def _pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Choisir des photos",
            "",
            "Images (" + " ".join("*" + e for e in sorted(IMG_EXT)) + ")",
        )
        if files:
            self.import_paths(files)

    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Choisir un dossier de photos")
        if d:
            self.import_paths([d])

    def _open_folder(self):
        id_c = self._current_id()
        if not id_c:
            return
        d = chantier_dir(id_c)
        os.makedirs(d, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    def _delete_selected(self):
        items = self._list.selectedItems()
        if not items:
            return
        rep = QMessageBox.question(
            self,
            "Supprimer",
            f"Supprimer définitivement {len(items)} photo(s) du dossier du chantier ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if rep != QMessageBox.StandardButton.Yes:
            return
        base = chantier_dir(self._current_id())
        for it in items:
            p = it.data(Qt.ItemDataRole.UserRole)
            for f in (p, thumb_path(base, p)):
                try:
                    os.remove(f)
                except OSError:
                    pass
        self.refresh()

    # ── Glisser-déposer ───────────────────────────────────────────────────
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._set_drop_style(True)

    def dragLeaveEvent(self, e):
        self._set_drop_style(False)

    def dropEvent(self, e):
        self._set_drop_style(False)
        paths_ = _paths_from_mime(e.mimeData())
        if paths_:
            e.acceptProposedAction()  # rend la main à l'Explorateur tout de suite
            self.import_paths(paths_)
