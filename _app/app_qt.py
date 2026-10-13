import importlib
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QSplashScreen,
    QStatusBar,
    QTabWidget,
    QWidget,
)
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QPixmap

import database as db

BEG_BLUE = "#1a3a5c"


def _apply_palette(app: QApplication):
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(245, 247, 250))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(235, 240, 248))
    pal.setColor(QPalette.ColorRole.Text, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.Button, QColor(245, 247, 250))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(26, 58, 92))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(pal)
    app.setStyleSheet("""
        QTabWidget::pane {
            border: 1px solid #d0d9e8;
            border-top: none;
            background: #f5f7fa;
        }
        QTabBar {
            qproperty-drawBase: 0;
        }
        QTabBar::tab {
            background: #edf1f7;
            color: #6b7c93;
            padding: 9px 22px;
            border: 1px solid #d0d9e8;
            border-bottom: none;
            margin-right: 2px;
            font-weight: 600;
            min-width: 110px;
        }
        QTabBar::tab:selected {
            background: #f5f7fa;
            color: #1a3a5c;
            border-top: 2px solid #1a3a5c;
        }
        QTabBar::tab:hover:!selected {
            background: #dce5f0;
            color: #1a3a5c;
        }
        QPushButton {
            background: #1a3a5c;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 7px 16px;
            font-weight: 600;
        }
        QPushButton:hover { background: #25517f; }
        QPushButton:pressed { background: #112840; }
        QPushButton:disabled { background: #c5cdd8; color: #8a96a3; }
        QPushButton#btn_secondary {
            background: white;
            color: #1a3a5c;
            border: 1.5px solid #1a3a5c;
        }
        QPushButton#btn_secondary:hover { background: #edf1f7; }
        QPushButton#btn_danger {
            background: white;
            color: #c0392b;
            border: 1.5px solid #c0392b;
        }
        QPushButton#btn_danger:hover { background: #fdf0ef; }
        QPushButton#btn_danger:disabled { border-color: #daa; color: #daa; }
        QPushButton#btn_small {
            background: #f0f2f5;
            color: #8a96a3;
            border: none;
            padding: 2px 7px;
            font-size: 11px;
            border-radius: 3px;
        }
        QPushButton#btn_small:hover { background: #fde8e6; color: #c0392b; }
        QPushButton#btn_add {
            background: transparent;
            color: #27ae60;
            border: 1.5px dashed #27ae60;
            padding: 5px 14px;
            border-radius: 5px;
        }
        QPushButton#btn_add:hover { background: #f0faf4; }
        QGroupBox {
            border: 1.5px solid #d0d9e8;
            border-radius: 6px;
            margin-top: 14px;
            padding-top: 6px;
            font-weight: 600;
            color: #1a3a5c;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 6px;
            color: #1a3a5c;
            background: #f5f7fa;
        }
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
            border: 1.5px solid #d0d9e8;
            border-radius: 4px;
            padding: 4px 8px;
            background: white;
        }
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus,
        QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {
            border-color: #1a3a5c;
        }
        QLabel#section_header {
            color: #1a3a5c;
            font-weight: 700;
            padding: 5px 8px 5px 10px;
            border-left: 3px solid #1a3a5c;
            margin-top: 4px;
        }
        QLabel#info_label {
            background: #edf1f7;
            color: #1a3a5c;
            padding: 5px 10px;
            border-radius: 4px;
        }
        QTableWidget {
            border: 1px solid #d0d9e8;
            gridline-color: #edf1f7;
        }
        QHeaderView::section {
            background: #edf1f7;
            color: #1a3a5c;
            font-weight: 600;
            padding: 6px 8px;
            border: none;
            border-right: 1px solid #d0d9e8;
            border-bottom: 2px solid #1a3a5c;
        }
        QScrollBar:vertical {
            border: none;
            background: #f0f2f5;
            width: 8px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background: #c0ccd8;
            border-radius: 4px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover { background: #1a3a5c; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QStatusBar {
            background: #edf1f7;
            color: #1a3a5c;
            font-size: 11px;
        }
    """)


APP_TITLE = "Bilan d'expérience gestionnaire"


class MainWindow(QMainWindow):
    _LAZY_TABS = (
        ("Historique", "tab_hist", "ui.tab_historique", "HistoriqueTab"),
        ("Dashboard", "tab_dash", "ui.tab_dashboard", "DashboardTab"),
        ("Photos", "tab_photos", "ui.tab_photos", "PhotosTab"),
        ("Importer Excel", "tab_import", "ui.tab_import", "ImportTab"),
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 860)

        db.init_db()

        from ui.tab_formulaire import FormulaireTab

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Seul le Formulaire est construit au démarrage ; les autres onglets le
        # sont à leur 1re ouverture (démarrage plus rapide).
        self.tab_form = FormulaireTab(self)
        self.tabs.addTab(self.tab_form, "Formulaire")
        self._lazy: dict[int, tuple[str, str, str, str]] = {}
        for name, attr, mod, cls in self._LAZY_TABS:
            self._lazy[self.tabs.addTab(QWidget(), name)] = (name, attr, mod, cls)

        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self.tabs)
        self.setStatusBar(QStatusBar())
        # Dépôt de photos/dossiers n'importe où dans la fenêtre
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            w = obj if hasattr(obj, "window") else None
            if w is not None and w.window() is self and ev.mimeData().hasUrls():
                from ui.tab_photos import _collect, _paths_from_mime

                paths = _paths_from_mime(ev.mimeData())
                if paths and _collect(paths):
                    if t == QEvent.Type.Drop:
                        self.show_tab("Photos")
                        self.tab_photos.refresh()
                        self.tab_photos.import_paths(paths)
                    ev.acceptProposedAction()
                    return True
        return super().eventFilter(obj, ev)

    def _ensure_tab(self, idx: int):
        """Construit l'onglet `idx` s'il ne l'est pas encore."""
        spec = self._lazy.pop(idx, None)
        if not spec:
            return
        name, attr, mod, cls = spec
        widget = getattr(importlib.import_module(mod), cls)(self)
        setattr(self, attr, widget)
        placeholder = self.tabs.widget(idx)
        self.tabs.blockSignals(True)
        self.tabs.removeTab(idx)
        self.tabs.insertTab(idx, widget, name)
        self.tabs.setCurrentIndex(idx)
        self.tabs.blockSignals(False)
        placeholder.deleteLater()

    def show_tab(self, name: str):
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == name:
                self._ensure_tab(i)
                self.tabs.setCurrentIndex(i)
                return

    def closeEvent(self, ev):
        # Threads de l'onglet Photos (import / miniatures) : arrêt propre, sinon Qt
        # abandonne l'application à la fermeture d'un QThread encore actif.
        photos = getattr(self, "tab_photos", None)
        if photos is not None:
            photos.shutdown()
        super().closeEvent(ev)

    def _on_tab_changed(self, idx):
        self._ensure_tab(idx)
        widget = self.tabs.widget(idx)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def open_bilan(self, bilan_id: int):
        self.tabs.setCurrentIndex(0)
        self.tab_form.load_bilan(bilan_id)

    def status(self, msg: str):
        self.statusBar().showMessage(msg, 5000)


def _show_error(msg: str):
    from PyQt6.QtWidgets import QMessageBox

    QMessageBox.warning(None, "Erreur inattendue", msg)


def install_excepthook():
    """PyQt6 ferme l'application sur toute exception non gérée dans un slot :
    on journalise et on affiche un message, l'application reste ouverte."""
    import datetime
    import traceback

    import paths

    def hook(exc_type, exc, tb):
        txt = "".join(traceback.format_exception(exc_type, exc, tb))
        log = os.path.join(paths.CACHE_DIR, "erreurs.log")
        try:
            os.makedirs(paths.CACHE_DIR, exist_ok=True)
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n{txt}\n")
        except OSError:
            pass
        try:
            _show_error(
                f"Une erreur est survenue, l'application reste ouverte :\n\n{exc}\n\n"
                f"Détails : {log}"
            )
        except Exception:
            pass

    sys.excepthook = hook


def _splash() -> QSplashScreen:
    pm = QPixmap(440, 150)
    pm.fill(QColor("#1a3a5c"))
    p = QPainter(pm)
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
    p.drawText(pm.rect().adjusted(0, -14, 0, 0), int(Qt.AlignmentFlag.AlignCenter.value), APP_TITLE)
    p.setFont(QFont("Segoe UI", 10))
    p.drawText(pm.rect().adjusted(0, 56, 0, 0), int(Qt.AlignmentFlag.AlignCenter.value), "Chargement…")
    p.end()
    return QSplashScreen(pm)


def _selftest(out_path: str) -> int:
    """Vérifie, dans l'exe compilé, ressources et imports différés. -> code retour."""
    import json
    import traceback

    res: dict = {}

    def check(name, fn):
        try:
            res[name] = fn() or "ok"
        except Exception:
            res[name] = "ERREUR " + traceback.format_exc(limit=3)

    def _modules():
        for m in (
            "ui.tab_historique",
            "ui.tab_dashboard",
            "ui.tab_photos",
            "ui.tab_import",
            "import_data",
            "pdf_export",
            "duc_parser",
            "emasphere_client",
            "pypdf",
            "openpyxl",
            "PIL",
        ):
            importlib.import_module(m)

    def _pdf():
        import pdf_export

        assert os.path.isfile(pdf_export.LOGO_PATH), "logo absent : " + pdf_export.LOGO_PATH
        data = {"id_chantier": "T1", "date_bilan": "01/01/2026", "point_significatif": "x"}
        return f"{len(pdf_export.generate_pdf(data, {'id_chantier': 'T1'}, 0))} octets"

    def _db():
        db.init_db()
        return f"{len(db.get_all_chantiers())} chantiers ({db.DB_PATH})"

    def _photos():
        import tempfile

        from PIL import Image
        from PyQt6.QtWidgets import QApplication as _QA

        _QA.instance() or _QA([])  # QImage/QImageReader : pas besoin de fenêtre
        import ui.tab_photos as tp

        tmp = tempfile.mkdtemp(prefix="beg_selftest_")
        tp.PHOTOS_ROOT = os.path.join(tmp, "Photos")
        src = os.path.join(tmp, "src.jpg")
        Image.frombytes("RGB", (900, 700), os.urandom(900 * 700 * 3)).resize(
            (3600, 2800)
        ).save(src, "JPEG", quality=92)
        res = tp.import_photos("T1", [src], reduce=True)
        out = tp.list_photos("T1")
        assert res.copied == 1 and res.reduced == 1, f"import/réduction: {res}"
        assert max(Image.open(out[0]).size) <= tp.MAX_SIDE, "image non réduite"
        thumb = tp.thumb_path(tp.chantier_dir("T1"), out[0])
        assert os.path.isfile(thumb), "miniature absente (plugin JPEG Qt ?)"
        return f"{os.path.getsize(src) // 1024} Ko -> {os.path.getsize(out[0]) // 1024} Ko, miniature OK"

    check("modules", _modules)
    check("photos (réduction + miniature)", _photos)
    check("pdf+logo", _pdf)
    check("base", _db)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    return 0 if all(v == "ok" or not v.startswith("ERREUR") for v in res.values()) else 1


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--selftest":
        sys.exit(_selftest(sys.argv[2]))
    install_excepthook()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    _apply_palette(app)
    splash = _splash()
    splash.show()
    app.processEvents()
    win = MainWindow()
    win.show()
    splash.finish(win)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
