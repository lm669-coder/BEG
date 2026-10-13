import os
import re
import shutil

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
    QFileDialog,
    QMessageBox,
    QFrame,
)
from PyQt6.QtCore import Qt, QSize, QUrl
from PyQt6.QtGui import QFont, QIcon, QImageReader, QPixmap, QDesktopServices

import database as db

BEG_BLUE = "#1a3a5c"
IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic"}
THUMB = 140

# Les photos sont rangées à côté de la base : <dossier base>/Photos/<id chantier>/
PHOTOS_ROOT = os.path.join(db._BASE, "Photos")


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name.strip()).strip(" .") or "_"


def chantier_dir(id_chantier: str) -> str:
    return os.path.join(PHOTOS_ROOT, _safe(id_chantier))


def _is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMG_EXT


def _collect(paths: list[str]) -> list[tuple[str, str]]:
    """(fichier, sous-dossier d'album) pour chaque image ; les dossiers sont
    parcourus récursivement et leur nom devient l'album."""
    out: list[tuple[str, str]] = []
    for p in paths:
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


def _unique(dest_dir: str, name: str) -> str:
    base, ext = os.path.splitext(name)
    cand, i = os.path.join(dest_dir, name), 1
    while os.path.exists(cand):
        cand = os.path.join(dest_dir, f"{base}_{i}{ext}")
        i += 1
    return cand


def import_photos(id_chantier: str, paths: list[str]) -> tuple[int, int]:
    """Copie photos/dossiers dans le dossier du chantier. -> (copiées, ignorées)."""
    base = chantier_dir(id_chantier)
    copied = 0
    items = _collect(paths)
    for src, album in items:
        dest_dir = os.path.join(base, *[_safe(x) for x in album.split(os.sep) if x])
        os.makedirs(dest_dir, exist_ok=True)
        try:
            shutil.copy2(src, _unique(dest_dir, os.path.basename(src)))
            copied += 1
        except OSError:
            pass
    return copied, len(items) - copied


def list_photos(id_chantier: str) -> list[str]:
    base = chantier_dir(id_chantier)
    res = []
    for cur, _d, files in os.walk(base):
        res += [os.path.join(cur, f) for f in sorted(files) if _is_image(f)]
    return sorted(res)


def _paths_from_mime(mime) -> list[str]:
    return [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]


class PhotosTab(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
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
        self._id.setPlaceholderText("ex. 22081")
        self._id.editingFinished.connect(self.refresh)
        hl.addWidget(self._id)
        self._info = QLabel("")
        self._info.setStyleSheet(f"color:{BEG_BLUE};")
        hl.addWidget(self._info, 1)

        btn_add = QPushButton("➕ Ajouter des photos…")
        btn_add.clicked.connect(self._pick_files)
        btn_dir = QPushButton("📁 Ajouter un dossier…")
        btn_dir.clicked.connect(self._pick_folder)
        btn_open = QPushButton("📂 Ouvrir le dossier")
        btn_open.setObjectName("btn_secondary")
        btn_open.clicked.connect(self._open_folder)
        btn_del = QPushButton("🗑 Supprimer la sélection")
        btn_del.setObjectName("btn_danger")
        btn_del.clicked.connect(self._delete_selected)
        for b in (btn_add, btn_dir, btn_open, btn_del):
            hl.addWidget(b)
        vl.addLayout(hl)

        self._drop = QLabel(
            "Glissez-déposez ici des photos ou des dossiers de photos "
            "(depuis l'Explorateur, le bureau, OneDrive…)"
        )
        self._drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop.setMinimumHeight(70)
        self._set_drop_style(False)
        vl.addWidget(self._drop)

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
        self._id.setText(id_chantier.strip())
        self.refresh()

    def _current_id(self) -> str:
        return self._id.text().strip()

    def refresh(self):
        if not self._id.text().strip():
            # reprend l'ID saisi dans le formulaire
            form = getattr(self._main, "tab_form", None)
            if form is not None:
                self._id.setText(form._id_chantier.text().strip())
        id_c = self._current_id()
        self._list.clear()
        ch = db.get_chantier(id_c) if id_c else None
        self._info.setText(
            f"{ch.get('intitule') or ''} — {ch.get('client') or ''}" if ch else ""
        )
        if not id_c:
            self._count.setText("Saisissez un ID chantier pour voir et ajouter des photos.")
            return
        base = chantier_dir(id_c)
        photos = list_photos(id_c)
        for path in photos:
            reader = QImageReader(path)
            reader.setAutoTransform(True)
            sz = reader.size()
            if sz.isValid():  # décodage réduit : rapide même pour de grosses photos
                sz.scale(THUMB * 2, THUMB * 2, Qt.AspectRatioMode.KeepAspectRatio)
                reader.setScaledSize(sz)
            img = reader.read()
            icon = QIcon(QPixmap.fromImage(img)) if not img.isNull() else QIcon()
            album = os.path.relpath(os.path.dirname(path), base)
            label = os.path.basename(path)
            it = QListWidgetItem(icon, label)
            it.setData(Qt.ItemDataRole.UserRole, path)
            it.setToolTip(path if album == "." else f"{album}\n{path}")
            self._list.addItem(it)
        self._count.setText(f"{len(photos)} photo(s) — {base}")

    # ── Import ────────────────────────────────────────────────────────────
    def import_paths(self, paths: list[str]):
        id_c = self._current_id()
        if not id_c:
            QMessageBox.information(
                self, "Photos", "Saisissez d'abord l'ID du chantier concerné."
            )
            return
        copied, skipped = import_photos(id_c, paths)
        self.refresh()
        msg = f"{copied} photo(s) ajoutée(s) au chantier {id_c}"
        if skipped:
            msg += f" ({skipped} non copiée(s))"
        elif not copied:
            msg = "Aucune image reconnue dans ce qui a été déposé."
        self._main.status(msg)

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
        for it in items:
            try:
                os.remove(it.data(Qt.ItemDataRole.UserRole))
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
        paths = _paths_from_mime(e.mimeData())
        if paths:
            e.acceptProposedAction()
            self.import_paths(paths)
