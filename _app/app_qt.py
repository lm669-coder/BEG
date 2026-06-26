import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QStatusBar
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPalette, QColor

import database as db

BEG_BLUE = "#1a3a5c"


def _apply_palette(app: QApplication):
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(245, 247, 250))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(235, 240, 248))
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BEG — Bilan d'expérience")
        self.resize(1280, 860)

        db.init_db()

        from ui.tab_formulaire import FormulaireTab
        from ui.tab_historique import HistoriqueTab
        from ui.tab_dashboard import DashboardTab
        from ui.tab_import import ImportTab

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.tab_form = FormulaireTab(self)
        self.tab_hist = HistoriqueTab(self)
        self.tab_dash = DashboardTab(self)
        self.tab_import = ImportTab(self)

        self.tabs.addTab(self.tab_form, "Formulaire")
        self.tabs.addTab(self.tab_hist, "Historique")
        self.tabs.addTab(self.tab_dash, "Dashboard")
        self.tabs.addTab(self.tab_import, "Importer Excel")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self.tabs)
        self.setStatusBar(QStatusBar())

    def _on_tab_changed(self, idx):
        widget = self.tabs.widget(idx)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def open_bilan(self, bilan_id: int):
        self.tabs.setCurrentIndex(0)
        self.tab_form.load_bilan(bilan_id)

    def status(self, msg: str):
        self.statusBar().showMessage(msg, 5000)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("BEG RMI")
    _apply_palette(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
