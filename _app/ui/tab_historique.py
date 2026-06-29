from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

import database as db


class HistoriqueTab(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._bilans = []

        vl = QVBoxLayout(self)
        vl.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Historique des bilans")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color:#1a3a5c;")
        vl.addWidget(title)

        # Filtres
        hl_f = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Recherche (ID, nom, client)…")
        self._search.textChanged.connect(self._filter)
        hl_f.addWidget(self._search, 3)

        self._combo_gest = QComboBox()
        self._combo_gest.addItem("Tous les gestionnaires")
        self._combo_gest.currentIndexChanged.connect(self._filter)
        hl_f.addWidget(self._combo_gest, 2)

        self._combo_sort = QComboBox()
        self._combo_sort.addItems(["Date (récent)", "ID chantier", "Client"])
        self._combo_sort.currentIndexChanged.connect(self._filter)
        hl_f.addWidget(self._combo_sort, 1)
        vl.addLayout(hl_f)

        self._count_lbl = QLabel("")
        vl.addWidget(self._count_lbl)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            [
                "ID Chantier",
                "Nom chantier",
                "Gestionnaire",
                "Client",
                "Date bilan",
                "Marge finale (%)",
                "Satisfaction /5",
            ]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemSelectionChanged.connect(self._on_selection)
        vl.addWidget(self._table, 1)

        # Actions
        hl_a = QHBoxLayout()
        self._btn_mod = QPushButton("Modifier")
        self._btn_mod.setEnabled(False)
        self._btn_del = QPushButton("Supprimer")
        self._btn_del.setObjectName("btn_danger")
        self._btn_del.setEnabled(False)
        self._btn_mod.clicked.connect(self._modifier)
        self._btn_del.clicked.connect(self._supprimer)
        hl_a.addWidget(self._btn_mod)
        hl_a.addWidget(self._btn_del)
        hl_a.addStretch()
        vl.addLayout(hl_a)

    def refresh(self):
        self._bilans = db.get_all_bilans()
        gestionnaires = sorted(
            {
                b.get("gestionnaire") or "?"
                for b in self._bilans
                if b.get("gestionnaire")
            }
        )
        current_gest = self._combo_gest.currentText()
        self._combo_gest.blockSignals(True)
        self._combo_gest.clear()
        self._combo_gest.addItem("Tous les gestionnaires")
        for g in gestionnaires:
            self._combo_gest.addItem(g)
        idx = self._combo_gest.findText(current_gest)
        if idx >= 0:
            self._combo_gest.setCurrentIndex(idx)
        self._combo_gest.blockSignals(False)
        self._filter()

    def _filter(self):
        rows = list(self._bilans)
        search = self._search.text().lower()
        if search:
            rows = [
                b
                for b in rows
                if search in str(b.get("id_chantier") or "").lower()
                or search in (b.get("intitule") or "").lower()
                or search in (b.get("client") or "").lower()
            ]

        gest = self._combo_gest.currentText()
        if gest and gest != "Tous les gestionnaires":
            rows = [b for b in rows if b.get("gestionnaire") == gest]

        sort = self._combo_sort.currentText()
        if sort == "ID chantier":
            rows.sort(key=lambda b: int(b.get("id_chantier") or 0), reverse=True)
        elif sort == "Client":
            rows.sort(key=lambda b: (b.get("client") or "").lower())

        self._count_lbl.setText(f"{len(rows)} bilan(s) trouvé(s)")
        self._populate(rows)

    def _populate(self, rows):
        self._table.setRowCount(len(rows))
        for r, b in enumerate(rows):
            vals = [
                str(b.get("id_chantier") or ""),
                b.get("intitule") or "—",
                b.get("gestionnaire") or "—",
                b.get("client") or "—",
                b.get("date_bilan") or "—",
                (
                    f"{b['marge_finale']:.1f}%"
                    if b.get("marge_finale") is not None
                    else "—"
                ),
                (
                    f"{b['satisfaction_client']}/5"
                    if b.get("satisfaction_client") is not None
                    else "—"
                ),
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setData(Qt.ItemDataRole.UserRole, b["id"])
                self._table.setItem(r, c, item)

            # Couleur marge
            if b.get("marge_finale") is not None:
                color = (
                    QColor(200, 240, 200)
                    if b["marge_finale"] >= 0
                    else QColor(255, 210, 210)
                )
                self._table.item(r, 5).setBackground(color)

        self._btn_mod.setEnabled(False)
        self._btn_del.setEnabled(False)

    def _on_selection(self):
        has = bool(self._table.selectedItems())
        self._btn_mod.setEnabled(has)
        self._btn_del.setEnabled(has)

    def _selected_id(self):
        items = self._table.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    def _modifier(self):
        bilan_id = self._selected_id()
        if bilan_id:
            self._main.open_bilan(bilan_id)

    def _supprimer(self):
        bilan_id = self._selected_id()
        if not bilan_id:
            return
        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            "Supprimer définitivement ce bilan ? Cette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.delete_bilan(bilan_id)
            self.refresh()
            self._main.status("Bilan supprimé.")
