import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QSpinBox, QCheckBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressBar, QAbstractItemView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import database as db
import import_data as imp


class ImportTab(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window

        vl = QVBoxLayout(self)
        vl.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Importer des données Excel")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color:#1a3a5c;")
        vl.addWidget(title)

        # Métriques
        hl_m = QHBoxLayout()
        self._lbl_ch = QLabel()
        self._lbl_bl = QLabel()
        self._lbl_dec = QLabel()
        for lbl in (self._lbl_ch, self._lbl_bl, self._lbl_dec):
            lbl.setStyleSheet("background:#dce5f0; border-radius:4px; padding:6px 12px; color:#1a3a5c; font-weight:bold;")
            hl_m.addWidget(lbl)
        hl_m.addStretch()
        vl.addLayout(hl_m)
        self._refresh_counts()

        vl.addWidget(self._build_bloc_chantiers())
        vl.addWidget(self._build_bloc_ea())
        vl.addWidget(self._build_bloc_decomptes())
        vl.addStretch()

    def _refresh_counts(self):
        conn = db.get_conn()
        ch = conn.execute("SELECT COUNT(*) FROM chantiers").fetchone()[0]
        bl = conn.execute("SELECT COUNT(*) FROM bilans").fetchone()[0]
        dec = conn.execute("SELECT COUNT(*) FROM decomptes").fetchone()[0]
        conn.close()
        self._lbl_ch.setText(f"Chantiers en base : {ch}")
        self._lbl_bl.setText(f"Bilans en base : {bl}")
        self._lbl_dec.setText(f"Décomptes en base : {dec}")

    # ── Bloc chantiers ────────────────────────────────────────────────────
    def _build_bloc_chantiers(self) -> QGroupBox:
        grp = QGroupBox()
        grp.setTitle("1. Registre des chantiers (Suivi RP & RD)")
        vl = QVBoxLayout(grp)

        hl = QHBoxLayout()
        self._file_ch_lbl = QLabel("Aucun fichier sélectionné")
        btn_ch = QPushButton("Choisir fichier…")
        btn_ch.setObjectName("btn_secondary")
        btn_ch.clicked.connect(self._pick_ch)
        hl.addWidget(btn_ch)
        hl.addWidget(self._file_ch_lbl, 1)
        vl.addLayout(hl)

        hl2 = QHBoxLayout()
        hl2.addWidget(QLabel("Feuille :"))
        self._sheet_ch = QComboBox(); self._sheet_ch.setEnabled(False)
        self._sheet_ch.currentIndexChanged.connect(self._preview_ch_show)
        hl2.addWidget(self._sheet_ch, 2)
        hl2.addWidget(QLabel("Ligne en-têtes :"))
        self._header_ch = QSpinBox(); self._header_ch.setRange(1, 10); self._header_ch.setValue(1)
        hl2.addWidget(self._header_ch)
        hl2.addWidget(QLabel("1ère donnée :"))
        self._data_ch = QSpinBox(); self._data_ch.setRange(2, 20); self._data_ch.setValue(2)
        hl2.addWidget(self._data_ch)
        hl2.addStretch()
        vl.addLayout(hl2)

        self._preview_ch = QTableWidget()
        self._preview_ch.setMaximumHeight(110)
        self._preview_ch.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._preview_ch.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._preview_ch.setVisible(False)
        vl.addWidget(self._preview_ch)

        hl3 = QHBoxLayout()
        self._overwrite_ch = QCheckBox("Écraser les chantiers existants (même ID)")
        self._btn_import_ch = QPushButton("▶ Importer les chantiers")
        self._btn_import_ch.setEnabled(False)
        self._btn_import_ch.clicked.connect(self._import_ch)
        hl3.addWidget(self._overwrite_ch)
        hl3.addStretch()
        hl3.addWidget(self._btn_import_ch)
        vl.addLayout(hl3)

        self._msg_ch = QLabel(""); vl.addWidget(self._msg_ch)
        self._file_ch_path = None
        return grp

    def _pick_ch(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir fichier chantiers",
                                               "", "Excel (*.xlsx *.xlsm *.xls)")
        if not path:
            return
        self._file_ch_path = path
        self._file_ch_lbl.setText(os.path.basename(path))
        try:
            with open(path, "rb") as f:
                sheets = imp.get_sheet_names(f)
            self._sheet_ch.clear()
            self._sheet_ch.addItems(sheets)
            self._sheet_ch.setEnabled(True)
            self._btn_import_ch.setEnabled(True)
            self._preview_ch_show()
        except Exception as e:
            self._msg_ch.setText(f"Erreur lecture : {e}")

    def _preview_ch_show(self):
        if not self._file_ch_path:
            return
        try:
            with open(self._file_ch_path, "rb") as f:
                rows = imp.get_sheet_preview(f, self._sheet_ch.currentText(),
                                              max_rows=self._header_ch.value() + 3)
            if not rows:
                return
            headers = [str(c) if c is not None else "" for c in rows[self._header_ch.value() - 1]]
            data_rows = rows[self._header_ch.value():]
            self._fill_preview(self._preview_ch, headers, data_rows[:3])
            self._preview_ch.setVisible(True)
        except Exception:
            pass

    def _import_ch(self):
        if not self._file_ch_path:
            return
        try:
            with open(self._file_ch_path, "rb") as f:
                conn = db.get_conn()
                ok, skip, detected = imp.import_chantiers(
                    f, self._sheet_ch.currentText(), conn,
                    header_row=self._header_ch.value(),
                    first_data_row=self._data_ch.value(),
                    overwrite=self._overwrite_ch.isChecked(),
                )
                conn.close()
            self._msg_ch.setText(f"✅ {ok} importé(s), {skip} ignoré(s) (déjà présents).")
            self._msg_ch.setStyleSheet("color:green;")
            self._refresh_counts()
        except Exception as e:
            self._msg_ch.setText(f"Erreur : {e}")
            self._msg_ch.setStyleSheet("color:red;")

    # ── Bloc EA ───────────────────────────────────────────────────────────
    def _build_bloc_ea(self) -> QGroupBox:
        grp = QGroupBox()
        grp.setTitle("2. États d'avancement / Facturation (INPUT - EA)")
        vl = QVBoxLayout(grp)

        hl = QHBoxLayout()
        self._file_ea_lbl = QLabel("Aucun fichier sélectionné")
        btn_ea = QPushButton("Choisir fichier…")
        btn_ea.setObjectName("btn_secondary")
        btn_ea.clicked.connect(self._pick_ea)
        hl.addWidget(btn_ea)
        hl.addWidget(self._file_ea_lbl, 1)
        vl.addLayout(hl)

        hl2 = QHBoxLayout()
        hl2.addWidget(QLabel("Feuille :"))
        self._sheet_ea = QComboBox(); self._sheet_ea.setEnabled(False)
        self._sheet_ea.currentIndexChanged.connect(self._preview_ea_show)
        hl2.addWidget(self._sheet_ea, 2)
        hl2.addWidget(QLabel("Ligne en-têtes :"))
        self._header_ea = QSpinBox(); self._header_ea.setRange(1, 10); self._header_ea.setValue(1)
        hl2.addWidget(self._header_ea)
        hl2.addWidget(QLabel("1ère donnée :"))
        self._data_ea = QSpinBox(); self._data_ea.setRange(2, 20); self._data_ea.setValue(2)
        hl2.addWidget(self._data_ea)
        hl2.addStretch()
        vl.addLayout(hl2)

        self._preview_ea = QTableWidget()
        self._preview_ea.setMaximumHeight(110)
        self._preview_ea.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._preview_ea.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._preview_ea.setVisible(False)
        vl.addWidget(self._preview_ea)

        hl3 = QHBoxLayout()
        self._overwrite_ea = QCheckBox("Vider et réimporter tous les EA")
        self._overwrite_ea.setChecked(True)
        self._btn_import_ea = QPushButton("▶ Importer les EA")
        self._btn_import_ea.setEnabled(False)
        self._btn_import_ea.clicked.connect(self._import_ea)
        hl3.addWidget(self._overwrite_ea)
        hl3.addStretch()
        hl3.addWidget(self._btn_import_ea)
        vl.addLayout(hl3)

        self._msg_ea = QLabel(""); vl.addWidget(self._msg_ea)
        self._file_ea_path = None
        return grp

    def _pick_ea(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir fichier EA",
                                               "", "Excel (*.xlsx *.xlsm *.xls)")
        if not path:
            return
        self._file_ea_path = path
        self._file_ea_lbl.setText(os.path.basename(path))
        try:
            with open(path, "rb") as f:
                sheets = imp.get_sheet_names(f)
            self._sheet_ea.clear()
            self._sheet_ea.addItems(sheets)
            self._sheet_ea.setEnabled(True)
            self._btn_import_ea.setEnabled(True)
            self._preview_ea_show()
        except Exception as e:
            self._msg_ea.setText(f"Erreur lecture : {e}")

    def _preview_ea_show(self):
        if not self._file_ea_path:
            return
        try:
            with open(self._file_ea_path, "rb") as f:
                rows = imp.get_sheet_preview(f, self._sheet_ea.currentText(),
                                              max_rows=self._header_ea.value() + 3)
            if not rows:
                return
            headers = [str(c) if c is not None else "" for c in rows[self._header_ea.value() - 1]]
            data_rows = rows[self._header_ea.value():]
            self._fill_preview(self._preview_ea, headers, data_rows[:3])
            self._preview_ea.setVisible(True)
        except Exception:
            pass

    def _import_ea(self):
        if not self._file_ea_path:
            return
        try:
            with open(self._file_ea_path, "rb") as f:
                conn = db.get_conn()
                ok, det = imp.import_ea(
                    f, self._sheet_ea.currentText(), conn,
                    header_row=self._header_ea.value(),
                    first_data_row=self._data_ea.value(),
                    overwrite=self._overwrite_ea.isChecked(),
                )
                conn.close()
            self._msg_ea.setText(f"✅ {ok} ligne(s) EA importée(s). Colonnes : {det}")
            self._msg_ea.setStyleSheet("color:green;")
            self._refresh_counts()
        except Exception as e:
            self._msg_ea.setText(f"Erreur : {e}")
            self._msg_ea.setStyleSheet("color:red;")

    # ── Bloc décomptes ─────────────────────────────────────────────────────
    def _build_bloc_decomptes(self) -> QGroupBox:
        grp = QGroupBox()
        grp.setTitle("3. Décomptes (délai complémentaire & montant par chantier)")
        vl = QVBoxLayout(grp)

        hl = QHBoxLayout()
        self._file_dec_lbl = QLabel("Aucun fichier sélectionné")
        btn_dec = QPushButton("Choisir fichier…")
        btn_dec.setObjectName("btn_secondary")
        btn_dec.clicked.connect(self._pick_dec)
        hl.addWidget(btn_dec)
        hl.addWidget(self._file_dec_lbl, 1)
        vl.addLayout(hl)

        hl2 = QHBoxLayout()
        hl2.addWidget(QLabel("Feuille :"))
        self._sheet_dec = QComboBox(); self._sheet_dec.setEnabled(False)
        self._sheet_dec.currentIndexChanged.connect(self._preview_dec_show)
        hl2.addWidget(self._sheet_dec, 2)
        hl2.addWidget(QLabel("Ligne en-têtes :"))
        self._header_dec = QSpinBox(); self._header_dec.setRange(1, 10); self._header_dec.setValue(1)
        hl2.addWidget(self._header_dec)
        hl2.addWidget(QLabel("1ère donnée :"))
        self._data_dec = QSpinBox(); self._data_dec.setRange(2, 20); self._data_dec.setValue(2)
        hl2.addWidget(self._data_dec)
        hl2.addStretch()
        vl.addLayout(hl2)

        self._preview_dec = QTableWidget()
        self._preview_dec.setMaximumHeight(110)
        self._preview_dec.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._preview_dec.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._preview_dec.setVisible(False)
        vl.addWidget(self._preview_dec)

        hl3 = QHBoxLayout()
        self._overwrite_dec = QCheckBox("Vider et réimporter tous les décomptes")
        self._overwrite_dec.setChecked(True)
        self._btn_import_dec = QPushButton("▶ Importer les décomptes")
        self._btn_import_dec.setEnabled(False)
        self._btn_import_dec.clicked.connect(self._import_dec)
        hl3.addWidget(self._overwrite_dec)
        hl3.addStretch()
        hl3.addWidget(self._btn_import_dec)
        vl.addLayout(hl3)

        self._msg_dec = QLabel(""); vl.addWidget(self._msg_dec)
        self._file_dec_path = None
        return grp

    def _pick_dec(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir fichier décomptes",
                                               "", "Excel (*.xlsx *.xlsm *.xls)")
        if not path:
            return
        self._file_dec_path = path
        self._file_dec_lbl.setText(os.path.basename(path))
        try:
            with open(path, "rb") as f:
                sheets = imp.get_sheet_names(f)
            self._sheet_dec.clear()
            self._sheet_dec.addItems(sheets)
            self._sheet_dec.setEnabled(True)
            self._btn_import_dec.setEnabled(True)
            self._preview_dec_show()
        except Exception as e:
            self._msg_dec.setText(f"Erreur lecture : {e}")

    def _preview_dec_show(self):
        if not self._file_dec_path:
            return
        try:
            with open(self._file_dec_path, "rb") as f:
                rows = imp.get_sheet_preview(f, self._sheet_dec.currentText(),
                                              max_rows=self._header_dec.value() + 3)
            if not rows:
                return
            headers = [str(c) if c is not None else "" for c in rows[self._header_dec.value() - 1]]
            data_rows = rows[self._header_dec.value():]
            self._fill_preview(self._preview_dec, headers, data_rows[:3])
            self._preview_dec.setVisible(True)
        except Exception:
            pass

    def _import_dec(self):
        if not self._file_dec_path:
            return
        try:
            with open(self._file_dec_path, "rb") as f:
                conn = db.get_conn()
                ok, det = imp.import_decomptes(
                    f, self._sheet_dec.currentText(), conn,
                    header_row=self._header_dec.value(),
                    first_data_row=self._data_dec.value(),
                    overwrite=self._overwrite_dec.isChecked(),
                )
                conn.close()
            self._msg_dec.setText(f"✅ {ok} ligne(s) importée(s). Colonnes : {det}")
            self._msg_dec.setStyleSheet("color:green;")
            self._refresh_counts()
        except Exception as e:
            self._msg_dec.setText(f"Erreur : {e}")
            self._msg_dec.setStyleSheet("color:red;")

    # ── Helper ─────────────────────────────────────────────────────────────
    @staticmethod
    def _fill_preview(table: QTableWidget, headers: list, rows: list):
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(str(val) if val is not None else ""))
