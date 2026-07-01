import os
from datetime import date, datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QScrollArea,
    QGroupBox,
    QLabel,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QMessageBox,
    QFileDialog,
    QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

import database as db
import pdf_export

BEG_BLUE = "#1a3a5c"
_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y")
_FIXED_PP_ROLES = ("Client", "Architecte", "Bureau d'étude")


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("section_header")
    lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    return lbl


def _info_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("info_label")
    lbl.setWordWrap(True)
    return lbl


def _fmt_eur(n: float) -> str:
    return f"{n:,.0f} €".replace(",", " ")


class DynamicSection(QWidget):
    def __init__(self, label_add: str, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._rows: list[tuple] = []

        self._btn_add = QPushButton(f"+ {label_add}")
        self._btn_add.setObjectName("btn_add")
        self._layout.addWidget(self._btn_add)
        self._btn_add.clicked.connect(lambda: self.add_row())

    def _insert_row_widget(self, row_widget: QWidget):
        idx = self._layout.indexOf(self._btn_add)
        self._layout.insertWidget(idx, row_widget)

    def _remove(self, row_widget):
        for i, (rw, _) in enumerate(self._rows):
            if rw is row_widget:
                self._rows.pop(i)
                self._layout.removeWidget(row_widget)
                row_widget.deleteLater()
                self._on_removed()
                break

    def _on_removed(self):
        pass

    def clear_rows(self):
        for row_widget, _ in self._rows:
            self._layout.removeWidget(row_widget)
            row_widget.deleteLater()
        self._rows.clear()


class PPExtraSection(DynamicSection):
    def __init__(self, parent=None):
        super().__init__("Ajouter une partie prenante", parent)

    def add_row(self, role="", nom="", relation="", evaluation=3):
        role_e = QLineEdit(role)
        role_e.setPlaceholderText("Rôle")
        nom_e = QLineEdit(nom)
        nom_e.setPlaceholderText("Nom")
        rel_e = QLineEdit(relation)
        rel_e.setPlaceholderText("Relation / Appréciation")
        eval_s = QSpinBox()
        eval_s.setRange(1, 5)
        eval_s.setValue(evaluation)
        eval_s.setFixedWidth(55)

        row_widget = QWidget()
        hl = QHBoxLayout(row_widget)
        hl.setContentsMargins(0, 2, 0, 2)
        hl.setSpacing(6)
        hl.addWidget(role_e, 2)
        hl.addWidget(nom_e, 2)
        hl.addWidget(rel_e, 4)
        hl.addWidget(QLabel("Éval. /5"))
        hl.addWidget(eval_s)

        btn_del = QPushButton("✕")
        btn_del.setObjectName("btn_small")
        btn_del.setFixedWidth(28)
        btn_del.clicked.connect(lambda: self._remove(row_widget))
        hl.addWidget(btn_del)

        self._rows.append((row_widget, (role_e, nom_e, rel_e, eval_s)))
        self._insert_row_widget(row_widget)

    def get_data(self) -> list:
        result = []
        for _, (role_e, nom_e, rel_e, eval_s) in self._rows:
            if role_e.text() or nom_e.text():
                result.append(
                    {
                        "role": role_e.text(),
                        "nom": nom_e.text(),
                        "relation": rel_e.text(),
                        "evaluation": eval_s.value(),
                    }
                )
        return result

    def load(self, items: list):
        self.clear_rows()
        for item in items:
            self.add_row(
                role=item.get("role", ""),
                nom=item.get("nom", ""),
                relation=item.get("relation", ""),
                evaluation=item.get("evaluation", 3) or 3,
            )


class PosteSection(DynamicSection):
    def __init__(self, label_add: str, parent=None):
        super().__init__(label_add, parent)

    def add_row(self, denomination="", prs=0.0, pre=0.0):
        denom_e = QLineEdit(denomination)
        denom_e.setPlaceholderText("Dénomination / poste")
        prs_s = QDoubleSpinBox()
        prs_s.setRange(0, 99_999_999)
        prs_s.setSingleStep(100)
        prs_s.setDecimals(2)
        prs_s.setValue(prs or 0.0)
        prs_s.setPrefix("")
        prs_s.setSuffix(" €")
        pre_s = QDoubleSpinBox()
        pre_s.setRange(0, 99_999_999)
        pre_s.setSingleStep(100)
        pre_s.setDecimals(2)
        pre_s.setValue(pre or 0.0)
        pre_s.setPrefix("")
        pre_s.setSuffix(" €")
        ecart_lbl = QLabel("—")
        ecart_lbl.setFixedWidth(90)

        def _update_ecart():
            ecart = pre_s.value() - prs_s.value()
            sign = "+" if ecart >= 0 else ""
            ecart_lbl.setText(f"{sign}{ecart:,.0f} €".replace(",", " "))
            color = "green" if ecart >= 0 else "#c0392b"
            ecart_lbl.setStyleSheet(
                f"color:{color}; font-weight:bold; padding:3px 6px;"
            )

        prs_s.valueChanged.connect(_update_ecart)
        pre_s.valueChanged.connect(_update_ecart)
        _update_ecart()

        row_widget = QWidget()
        hl = QHBoxLayout(row_widget)
        hl.setContentsMargins(0, 2, 0, 2)
        hl.setSpacing(6)
        hl.addWidget(denom_e, 4)
        hl.addWidget(QLabel("PRS:"))
        hl.addWidget(prs_s, 2)
        hl.addWidget(QLabel("PRE:"))
        hl.addWidget(pre_s, 2)
        hl.addWidget(QLabel("Écart:"))
        hl.addWidget(ecart_lbl)

        btn_del = QPushButton("✕")
        btn_del.setObjectName("btn_small")
        btn_del.setFixedWidth(28)
        btn_del.clicked.connect(lambda: self._remove(row_widget))
        hl.addWidget(btn_del)

        self._rows.append((row_widget, (denom_e, prs_s, pre_s)))
        self._insert_row_widget(row_widget)

    def get_data(self) -> list:
        result = []
        for _, (denom_e, prs_s, pre_s) in self._rows:
            if denom_e.text():
                result.append(
                    {
                        "denomination": denom_e.text(),
                        "prs": prs_s.value(),
                        "pre": pre_s.value(),
                    }
                )
        return result

    def load(self, items: list):
        self.clear_rows()
        for item in items:
            self.add_row(
                denomination=item.get("denomination", ""),
                prs=item.get("prs") or 0.0,
                pre=item.get("pre") or 0.0,
            )


class TravauxSection(DynamicSection):
    def __init__(self, parent=None):
        super().__init__("Ajouter travaux internes", parent)
        self._total_lbl = QLabel()
        self._layout.addWidget(self._total_lbl)

    def add_row(self, denomination="", heures_soumission=0.0, heures_execution=0.0):
        denom_e = QLineEdit(denomination)
        denom_e.setPlaceholderText("Dénomination / équipe")
        hs_s = QDoubleSpinBox()
        hs_s.setRange(0, 999_999)
        hs_s.setSingleStep(0.5)
        hs_s.setDecimals(1)
        hs_s.setValue(heures_soumission or 0.0)
        hs_s.setSuffix(" h")
        he_s = QDoubleSpinBox()
        he_s.setRange(0, 999_999)
        he_s.setSingleStep(0.5)
        he_s.setDecimals(1)
        he_s.setValue(heures_execution or 0.0)
        he_s.setSuffix(" h")
        coeff_lbl = QLabel("—")
        coeff_lbl.setFixedWidth(70)

        def _update():
            hs = hs_s.value()
            he = he_s.value()
            if hs:
                coeff = (hs - he) / hs
                coeff_lbl.setText(f"{coeff:.3f}")
            else:
                coeff_lbl.setText("—")
            self._update_totals()

        hs_s.valueChanged.connect(_update)
        he_s.valueChanged.connect(_update)

        row_widget = QWidget()
        hl = QHBoxLayout(row_widget)
        hl.setContentsMargins(0, 2, 0, 2)
        hl.setSpacing(6)
        hl.addWidget(denom_e, 4)
        hl.addWidget(QLabel("H-S:"))
        hl.addWidget(hs_s, 2)
        hl.addWidget(QLabel("H-E:"))
        hl.addWidget(he_s, 2)
        hl.addWidget(QLabel("Coeff:"))
        hl.addWidget(coeff_lbl)

        btn_del = QPushButton("✕")
        btn_del.setObjectName("btn_small")
        btn_del.setFixedWidth(28)
        btn_del.clicked.connect(lambda: self._remove(row_widget))
        hl.addWidget(btn_del)

        self._rows.append((row_widget, (denom_e, hs_s, he_s)))
        self._insert_row_widget(row_widget)
        self._update_totals()

    def _on_removed(self):
        self._update_totals()

    def _update_totals(self):
        total_hs = sum(hs_s.value() for _, (_, hs_s, _) in self._rows)
        total_he = sum(he_s.value() for _, (_, _, he_s) in self._rows)
        if self._rows:
            coeff = f"{(total_hs - total_he)/total_hs:.3f}" if total_hs else "—"
            self._total_lbl.setText(
                f"  Total H-S: {total_hs:.1f} h  |  H-E: {total_he:.1f} h  |  Coeff. global: {coeff}"
            )
            self._total_lbl.setStyleSheet(
                "color:#1a3a5c; font-weight:bold; padding:2px 6px;"
            )
        else:
            self._total_lbl.setText("")

    def get_data(self) -> list:
        result = []
        for _, (denom_e, hs_s, he_s) in self._rows:
            if denom_e.text():
                result.append(
                    {
                        "denomination": denom_e.text(),
                        "heures_soumission": hs_s.value(),
                        "heures_execution": he_s.value(),
                    }
                )
        return result

    def load(self, items: list):
        self.clear_rows()
        for item in items:
            self.add_row(
                denomination=item.get("denomination", ""),
                heures_soumission=item.get("heures_soumission") or 0.0,
                heures_execution=item.get("heures_execution") or 0.0,
            )


class STSection(DynamicSection):
    CRITERIA = [
        ("Prix", "respect_prix"),
        ("Délais", "respect_delais"),
        ("Sécu.", "respect_securite"),
        ("Qualité", "respect_qualite"),
        ("Réact.", "reactivite"),
        ("Comm.", "communication"),
    ]

    def __init__(self, parent=None):
        super().__init__("Ajouter un sous-traitant", parent)

    def add_row(self, nom="", **scores):
        nom_e = QLineEdit(nom)
        nom_e.setPlaceholderText("Nom du sous-traitant")

        spin_widgets = []
        for lbl_text, key in self.CRITERIA:
            lbl = QLabel(lbl_text)
            lbl.setFixedWidth(44)
            spin = QSpinBox()
            spin.setRange(1, 5)
            spin.setValue(scores.get(key, 3) or 3)
            spin.setFixedWidth(46)
            spin_widgets.append((lbl, spin, key))

        avg_lbl = QLabel("—")
        avg_lbl.setFixedWidth(60)
        avg_lbl.setStyleSheet("font-weight:bold; color:#1a3a5c; padding:2px 4px;")

        def _update_avg():
            vals = [spin.value() for _, spin, _ in spin_widgets]
            avg = sum(vals) / len(vals)
            avg_lbl.setText(f"Moy: {avg:.1f}")

        for _, spin, _ in spin_widgets:
            spin.valueChanged.connect(_update_avg)
        _update_avg()

        row_widget = QWidget()
        hl = QHBoxLayout(row_widget)
        hl.setContentsMargins(0, 2, 0, 2)
        hl.setSpacing(4)
        hl.addWidget(nom_e, 3)
        for lbl_text, spin, _ in spin_widgets:
            hl.addWidget(lbl_text)
            hl.addWidget(spin)
        hl.addWidget(avg_lbl)

        btn_del = QPushButton("✕")
        btn_del.setObjectName("btn_small")
        btn_del.setFixedWidth(28)
        btn_del.clicked.connect(lambda: self._remove(row_widget))
        hl.addWidget(btn_del)

        self._rows.append((row_widget, (nom_e, spin_widgets)))
        self._insert_row_widget(row_widget)

    def get_data(self) -> list:
        result = []
        for _, (nom_e, spin_widgets) in self._rows:
            if nom_e.text():
                row = {"nom": nom_e.text()}
                for _, spin, key in spin_widgets:
                    row[key] = spin.value()
                result.append(row)
        return result

    def load(self, items: list):
        self.clear_rows()
        for item in items:
            self.add_row(
                nom=item.get("nom", ""),
                **{key: item.get(key, 3) for _, key in self.CRITERIA},
            )


class FormulaireTab(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._loaded_id = None
        self._chantier_info = None
        self._montant_facture = 0.0

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        self._vl = QVBoxLayout(content)
        self._vl.setContentsMargins(20, 16, 20, 16)
        self._vl.setSpacing(12)
        scroll.setWidget(content)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self._build_header()
        self._build_section1()
        self._build_section2()
        self._build_section3()
        self._build_section4()
        self._build_section5()
        self._build_section6()
        self._build_section7()
        self._build_section8()
        self._build_actions()

        self._vl.addStretch()

        self._lookup_timer = QTimer(self)
        self._lookup_timer.setSingleShot(True)
        self._lookup_timer.setInterval(500)
        self._lookup_timer.timeout.connect(self._do_lookup)

    # ── Header ─────────────────────────────────────────────────────────────
    def _build_header(self):
        hl = QHBoxLayout()
        title = QLabel("Bilan d'expérience")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{BEG_BLUE};")
        hl.addWidget(title)
        hl.addStretch()

        self._combo_bilans = QComboBox()
        self._combo_bilans.setMinimumWidth(360)
        self._combo_bilans.setPlaceholderText("Charger un bilan existant…")
        self._combo_bilans.currentIndexChanged.connect(self._on_combo_select)
        hl.addWidget(self._combo_bilans)

        btn_new = QPushButton("Nouveau bilan vierge")
        btn_new.setObjectName("btn_secondary")
        btn_new.clicked.connect(self.reset_form)
        hl.addWidget(btn_new)

        self._refresh_combo()
        self._vl.addLayout(hl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#b8cce4;")
        self._vl.addWidget(sep)

    def _refresh_combo(self):
        self._combo_bilans.blockSignals(True)
        self._combo_bilans.clear()
        self._combo_bilans.addItem("— Nouveau bilan —", None)
        for b in db.get_all_bilans():
            label = f"{b['id_chantier']} · {b['intitule'] or 'Sans nom'} ({b['date_bilan'] or '?'})"
            self._combo_bilans.addItem(label, b["id"])
        self._combo_bilans.blockSignals(False)

    # ── Section 1 : Identification ─────────────────────────────────────────
    def _build_section1(self):
        self._vl.addWidget(_section_label("1. IDENTIFICATION"))

        hl = QHBoxLayout()
        hl.addWidget(QLabel("ID Chantier *"))
        self._id_chantier = QLineEdit()
        self._id_chantier.setPlaceholderText("ex: 22097")
        self._id_chantier.setMaximumWidth(160)
        self._id_chantier.textChanged.connect(self._on_id_changed)
        hl.addWidget(self._id_chantier)

        hl.addSpacing(20)
        hl.addWidget(QLabel("Date du bilan"))
        self._date_bilan = QLineEdit()
        self._date_bilan.setText(date.today().strftime("%d/%m/%Y"))
        self._date_bilan.setMaximumWidth(120)
        hl.addWidget(self._date_bilan)
        hl.addStretch()
        self._vl.addLayout(hl)

        self._info_chantier = QWidget()
        info_hl = QHBoxLayout(self._info_chantier)
        info_hl.setContentsMargins(0, 0, 0, 0)
        self._lbl_intitule = _info_label("")
        self._lbl_gestionnaire = _info_label("")
        self._lbl_client = _info_label("")
        self._lbl_secteur = _info_label("")
        for lbl in (
            self._lbl_intitule,
            self._lbl_gestionnaire,
            self._lbl_client,
            self._lbl_secteur,
        ):
            info_hl.addWidget(lbl, 1)
        self._info_chantier.setVisible(False)
        self._vl.addWidget(self._info_chantier)

        self._warn_chantier = QLabel("")
        self._warn_chantier.setStyleSheet("color:#c0392b; font-weight:bold;")
        self._vl.addWidget(self._warn_chantier)

    def _on_id_changed(self):
        self._lookup_timer.start()

    def _do_lookup(self):
        id_c = self._id_chantier.text().strip()
        if not id_c:
            self._chantier_info = None
            self._montant_facture = 0.0
            self._info_chantier.setVisible(False)
            self._warn_chantier.setText("")
            return

        ch = db.get_chantier(id_c)
        self._chantier_info = ch
        self._montant_facture = db.get_montant_facture(id_c)

        if ch:
            self._show_chantier_info(ch)
            self._warn_chantier.setText("")

            if self._loaded_id is None:
                self._prefill_from_chantier(ch, id_c)
        else:
            self._info_chantier.setVisible(False)
            self._warn_chantier.setText("⚠ ID chantier non trouvé dans la base.")

        self._update_calculs()

    def _prefill_from_chantier(self, ch: dict, id_c: str):
        if ch.get("delai_execution"):
            self._delai_contractuel.setValue(int(ch["delai_execution"]))
        if ch.get("montant"):
            self._montant_base.setValue(float(ch["montant"]))
        if ch.get("client"):
            self._pp_client_nom.setText(ch["client"])
        dec = db.get_decomptes_totals(id_c)
        if dec["delai"]:
            self._delai_complementaire.setValue(int(dec["delai"]))
        if dec["montant"]:
            self._montant_decomptes.setValue(float(dec["montant"]))
        if ch.get("prix_de_revient"):
            pr = float(ch["prix_de_revient"])
            self._prix_de_revient.setValue(pr)
            pv = float(ch.get("montant") or 0)
            if pv:
                self._marge_devis.setValue(round((pv - pr) / pv * 100, 2))

    # ── Section 2 : Parties prenantes ──────────────────────────────────────
    def _build_section2(self):
        self._vl.addWidget(_section_label("2. PARTIES PRENANTES"))

        grp = QGroupBox()
        grp.setTitle("Parties prenantes fixes")
        gl = QGridLayout(grp)
        gl.setColumnStretch(1, 3)
        gl.setColumnStretch(2, 4)

        headers = ["", "Nom", "Relation / Appréciation", "Éval. /5"]
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            gl.addWidget(lbl, 0, col)

        self._pp_client_nom = QLineEdit()
        self._pp_client_rel = QLineEdit()
        self._pp_client_eval = QSpinBox()
        self._pp_client_eval.setRange(1, 5)
        self._pp_client_eval.setValue(3)
        self._pp_client_eval.setFixedWidth(55)

        self._pp_arch_nom = QLineEdit()
        self._pp_arch_rel = QLineEdit()
        self._pp_arch_eval = QSpinBox()
        self._pp_arch_eval.setRange(1, 5)
        self._pp_arch_eval.setValue(3)
        self._pp_arch_eval.setFixedWidth(55)

        self._pp_be_nom = QLineEdit()
        self._pp_be_rel = QLineEdit()
        self._pp_be_eval = QSpinBox()
        self._pp_be_eval.setRange(1, 5)
        self._pp_be_eval.setValue(3)
        self._pp_be_eval.setFixedWidth(55)

        for row, (role, nom_e, rel_e, eval_s) in enumerate(
            [
                (
                    "Client",
                    self._pp_client_nom,
                    self._pp_client_rel,
                    self._pp_client_eval,
                ),
                (
                    "Architecte",
                    self._pp_arch_nom,
                    self._pp_arch_rel,
                    self._pp_arch_eval,
                ),
                ("Bureau d'étude", self._pp_be_nom, self._pp_be_rel, self._pp_be_eval),
            ],
            start=1,
        ):
            gl.addWidget(QLabel(role), row, 0)
            gl.addWidget(nom_e, row, 1)
            gl.addWidget(rel_e, row, 2)
            gl.addWidget(eval_s, row, 3)

        self._vl.addWidget(grp)

        self._vl.addWidget(QLabel("Autres parties prenantes :"))
        self._pp_extra = PPExtraSection()
        self._vl.addWidget(self._pp_extra)

    # ── Section 3 : Performance ────────────────────────────────────────────
    def _build_section3(self):
        self._vl.addWidget(_section_label("3. PERFORMANCE"))

        # ── Délais ────────────────────────────────────────────────────────
        grp_delai = QGroupBox()
        grp_delai.setTitle("Délais")
        vl_d = QVBoxLayout(grp_delai)

        hl_d1 = QHBoxLayout()
        for lbl_txt, attr in [
            ("Délai contractuel", "_delai_contractuel"),
            ("Délai complémentaire", "_delai_complementaire"),
        ]:
            spin = QSpinBox()
            spin.setRange(0, 9999)
            setattr(self, attr, spin)
            vl_s = QVBoxLayout()
            vl_s.addWidget(QLabel(lbl_txt))
            vl_s.addWidget(spin)
            hl_d1.addLayout(vl_s)

        vl_u = QVBoxLayout()
        vl_u.addWidget(QLabel("Unité"))
        self._unite_delai = QComboBox()
        self._unite_delai.addItems(["JC", "JO", "semaines", "mois"])
        vl_u.addWidget(self._unite_delai)
        hl_d1.addLayout(vl_u)

        vl_tot = QVBoxLayout()
        vl_tot.addWidget(QLabel("Total autorisé (calculé)"))
        self._delai_reel = QLabel("—")
        self._delai_reel.setStyleSheet(
            "font-weight:bold; color:#1a3a5c; padding:4px 8px;"
            "background:#edf1f7; border-radius:4px;"
        )
        vl_tot.addWidget(self._delai_reel)
        hl_d1.addLayout(vl_tot)
        hl_d1.addStretch()
        vl_d.addLayout(hl_d1)

        self._date_fin_lbl = QLabel("")
        vl_d.addWidget(self._date_fin_lbl)

        # Bloc comparaison OC / RP (visible si données chantier disponibles)
        self._rp_compare_widget = QWidget()
        rp_vl = QVBoxLayout(self._rp_compare_widget)
        rp_vl.setContentsMargins(0, 6, 0, 0)
        rp_vl.setSpacing(4)
        rp_title = QLabel("Suivi délai — Restitution cautionnement (RP)")
        rp_title.setStyleSheet("color:#1a3a5c; font-weight:600;")
        rp_vl.addWidget(rp_title)
        rp_hl = QHBoxLayout()
        rp_hl.setSpacing(8)
        self._lbl_oc = QLabel("—")
        self._lbl_rp_dem = QLabel("—")
        self._lbl_rp_real = QLabel("—")
        self._lbl_rp_ecart = QLabel("—")
        _card = (
            "background:#edf1f7; color:#1a3a5c; padding:6px 10px;"
            "border-radius:4px; min-width:130px;"
        )
        for lbl in (self._lbl_oc, self._lbl_rp_dem, self._lbl_rp_real, self._lbl_rp_ecart):
            lbl.setWordWrap(True)
            lbl.setStyleSheet(_card)
            rp_hl.addWidget(lbl, 1)
        rp_vl.addLayout(rp_hl)
        self._rp_compare_widget.setVisible(False)
        vl_d.addWidget(self._rp_compare_widget)

        for s in (self._delai_contractuel, self._delai_complementaire):
            s.valueChanged.connect(self._update_calculs)
        self._unite_delai.currentTextChanged.connect(self._update_calculs)
        self._vl.addWidget(grp_delai)

        # ── Budget ────────────────────────────────────────────────────────
        grp_bud = QGroupBox()
        grp_bud.setTitle("Budget")
        hl2 = QHBoxLayout(grp_bud)

        self._montant_base = QDoubleSpinBox()
        self._montant_base.setRange(0, 999_999_999)
        self._montant_base.setSingleStep(1000)
        self._montant_base.setDecimals(2)
        self._montant_base.setSuffix(" €")
        self._montant_decomptes = QDoubleSpinBox()
        self._montant_decomptes.setRange(0, 999_999_999)
        self._montant_decomptes.setSingleStep(1000)
        self._montant_decomptes.setDecimals(2)
        self._montant_decomptes.setSuffix(" €")
        self._total_pv_lbl = QLabel("0 €")
        self._total_pv_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._total_ea_lbl = QLabel("0 €")
        self._total_ea_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))

        for lbl_text, widget in [
            ("Montant base PV (€ HTVA)", self._montant_base),
            ("Montant décomptes PV (€)", self._montant_decomptes),
        ]:
            vl = QVBoxLayout()
            vl.addWidget(QLabel(lbl_text))
            vl.addWidget(widget)
            hl2.addLayout(vl)

        for lbl_text, lbl_w in [("Total PV", self._total_pv_lbl), ("Total facturé (EA)", self._total_ea_lbl)]:
            vl = QVBoxLayout()
            vl.addWidget(QLabel(lbl_text))
            vl.addWidget(lbl_w)
            hl2.addLayout(vl)
        hl2.addStretch()

        self._montant_base.valueChanged.connect(self._update_calculs)
        self._montant_decomptes.valueChanged.connect(self._update_calculs)
        self._vl.addWidget(grp_bud)

        # ── PR + Marge devis ──────────────────────────────────────────────
        grp_pr = QGroupBox()
        grp_pr.setTitle("Prix de Revient & Marge devis")
        hl3 = QHBoxLayout(grp_pr)

        self._prix_de_revient = QDoubleSpinBox()
        self._prix_de_revient.setRange(0, 999_999_999)
        self._prix_de_revient.setSingleStep(1000)
        self._prix_de_revient.setDecimals(2)
        self._prix_de_revient.setSuffix(" €")
        self._marge_devis = QDoubleSpinBox()
        self._marge_devis.setRange(-100, 100)
        self._marge_devis.setSingleStep(0.1)
        self._marge_devis.setDecimals(2)
        self._marge_devis.setSuffix(" %")

        for lbl_text, widget in [
            ("PR Soumission (€ HTVA)", self._prix_de_revient),
            ("Marge devis (%)", self._marge_devis),
        ]:
            vl = QVBoxLayout()
            vl.addWidget(QLabel(lbl_text))
            vl.addWidget(widget)
            hl3.addLayout(vl)
        hl3.addStretch()
        self._vl.addWidget(grp_pr)

    def _update_calculs(self):
        dc = self._delai_contractuel.value()
        dcomp = self._delai_complementaire.value()
        unite = self._unite_delai.currentText()
        delai_total = dc + dcomp

        self._delai_reel.setText(f"{delai_total} {unite}" if delai_total else "—")

        ch = self._chantier_info or {}
        oc_raw = ch.get("ordre_commencer", "")
        if oc_raw and delai_total:
            start = None
            for fmt in _DATE_FORMATS:
                try:
                    start = datetime.strptime(oc_raw.strip(), fmt).date()
                    break
                except Exception:
                    pass
            if start:
                if unite == "JC":
                    end = start + timedelta(days=delai_total)
                elif unite == "JO":
                    end = start + timedelta(days=int(delai_total * 7 / 5))
                elif unite == "semaines":
                    end = start + timedelta(weeks=delai_total)
                else:
                    end = start + timedelta(days=delai_total * 30)
                self._date_fin_lbl.setText(
                    f"OC : {oc_raw}  →  Date fin théorique : {end.strftime('%d/%m/%Y')} "
                    f"({dc}+{dcomp} {unite})"
                )
                self._date_fin_lbl.setStyleSheet(
                    "color:#27ae60; font-weight:bold; padding:2px 6px;"
                )
            else:
                self._date_fin_lbl.setText(f"Ordre de commencer : {oc_raw}")
        else:
            self._date_fin_lbl.setText("")

        self._update_rp_compare(delai_total, unite)

        mb = self._montant_base.value()
        md = self._montant_decomptes.value()
        self._total_pv_lbl.setText(_fmt_eur(mb + md))
        self._total_ea_lbl.setText(_fmt_eur(self._montant_facture))

    def _update_rp_compare(self, delai_total: int, unite: str) -> None:
        ch = self._chantier_info or {}
        oc_raw = ch.get("ordre_commencer", "")
        if not oc_raw:
            self._rp_compare_widget.setVisible(False)
            return

        oc_date = None
        for fmt in _DATE_FORMATS:
            try:
                oc_date = datetime.strptime(oc_raw.strip(), fmt).date()
                break
            except Exception:
                pass
        if not oc_date:
            self._rp_compare_widget.setVisible(False)
            return

        self._lbl_oc.setText(f"Ordre de commencer\n{oc_raw}")

        rp_dem_raw = ch.get("rp_demandee", "") or ""
        rp_real_raw = ch.get("rp_realisee", "") or ""

        rp_dem_date = None
        if rp_dem_raw:
            for fmt in _DATE_FORMATS:
                try:
                    rp_dem_date = datetime.strptime(rp_dem_raw.strip(), fmt).date()
                    break
                except Exception:
                    pass

        rp_real_date = None
        if rp_real_raw:
            for fmt in _DATE_FORMATS:
                try:
                    rp_real_date = datetime.strptime(rp_real_raw.strip(), fmt).date()
                    break
                except Exception:
                    pass

        self._lbl_rp_dem.setText(f"RP demandée\n{rp_dem_raw if rp_dem_raw else '—'}")
        self._lbl_rp_real.setText(f"RP réalisée\n{rp_real_raw if rp_real_raw else '—'}")

        rp_ref_date = rp_real_date or rp_dem_date
        rp_ref_label = "réalisée" if rp_real_date else ("demandée" if rp_dem_date else None)

        _card_base = "padding:6px 10px; border-radius:4px; min-width:130px;"
        if rp_ref_date and delai_total:
            days_jc = (rp_ref_date - oc_date).days
            if unite == "JO":
                days_u = round(days_jc * 5 / 7)
            elif unite == "semaines":
                days_u = round(days_jc / 7)
            elif unite == "mois":
                days_u = round(days_jc / 30)
            else:
                days_u = days_jc

            ecart = days_u - delai_total
            sign = "+" if ecart > 0 else ""
            if ecart > 0:
                color, verdict = "#c0392b", "DÉPASSEMENT"
            elif ecart < 0:
                color, verdict = "#27ae60", "AVANCE"
            else:
                color, verdict = "#1a3a5c", "RESPECTÉ"

            self._lbl_rp_ecart.setText(
                f"OC → RP ({rp_ref_label})\n{days_u} {unite}\n{verdict} : {sign}{ecart} {unite}"
            )
            self._lbl_rp_ecart.setStyleSheet(
                f"background:#edf1f7; color:{color}; font-weight:bold; {_card_base}"
            )
        else:
            msg = "Comparaison RP\n"
            msg += "(dates RP non disponibles)" if not rp_ref_date else "(délai non saisi)"
            self._lbl_rp_ecart.setText(msg)
            self._lbl_rp_ecart.setStyleSheet(
                f"background:#edf1f7; color:#8a96a3; {_card_base}"
            )

        self._rp_compare_widget.setVisible(True)

    # ── Section 4 : Rendements ─────────────────────────────────────────────
    def _build_section4(self):
        self._vl.addWidget(_section_label("4. RENDEMENTS & EXÉCUTION"))

        lbl_perte = QLabel("Postes en PERTE (évalués trop bas)")
        lbl_perte.setStyleSheet("color:#c0392b; font-weight:bold; padding:2px 0;")
        self._vl.addWidget(lbl_perte)
        self._postes_perte = PosteSection("Ajouter poste en perte")
        self._vl.addWidget(self._postes_perte)

        lbl_surb = QLabel("Postes en SURBÉNÉFICE (évalués trop haut)")
        lbl_surb.setStyleSheet("color:#27ae60; font-weight:bold; padding:2px 0;")
        self._vl.addWidget(lbl_surb)
        self._postes_surb = PosteSection("Ajouter poste en surbénéfice")
        self._vl.addWidget(self._postes_surb)

        self._vl.addWidget(QLabel("Travaux réalisés en interne :"))
        self._travaux = TravauxSection()
        self._vl.addWidget(self._travaux)

    # ── Section 5 : Qualité ────────────────────────────────────────────────
    def _build_section5(self):
        self._vl.addWidget(_section_label("5. QUALITÉ"))

        hl = QHBoxLayout()
        vl_q = QVBoxLayout()
        vl_q.addWidget(QLabel("Niveau de qualité global"))
        self._niveau_qualite = QTextEdit()
        self._niveau_qualite.setFixedHeight(70)
        vl_q.addWidget(self._niveau_qualite)
        hl.addLayout(vl_q, 4)

        vl_s = QVBoxLayout()
        vl_s.addWidget(QLabel("Satisfaction client /5"))
        self._satisfaction_client = QSpinBox()
        self._satisfaction_client.setRange(1, 5)
        self._satisfaction_client.setValue(3)
        vl_s.addWidget(self._satisfaction_client)
        vl_s.addStretch()
        hl.addLayout(vl_s, 1)
        self._vl.addLayout(hl)

        self._vl.addWidget(
            QLabel("Travaux non satisfaisants (description + responsable) :")
        )
        self._travaux_non_sat = QTextEdit()
        self._travaux_non_sat.setFixedHeight(70)
        self._vl.addWidget(self._travaux_non_sat)

        self._vl.addWidget(QLabel("Améliorations proposées :"))
        self._ameliorations_qualite = QTextEdit()
        self._ameliorations_qualite.setFixedHeight(70)
        self._vl.addWidget(self._ameliorations_qualite)

    # ── Section 6 : Sécurité ──────────────────────────────────────────────
    def _build_section6(self):
        self._vl.addWidget(_section_label("6. SÉCURITÉ"))

        hl = QHBoxLayout()
        hl.addWidget(QLabel("Accident(s) sur chantier ?"))
        self._accident_non = QRadioButton("Non")
        self._accident_oui = QRadioButton("Oui")
        self._accident_non.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self._accident_non)
        grp.addButton(self._accident_oui)
        hl.addWidget(self._accident_non)
        hl.addWidget(self._accident_oui)
        hl.addStretch()
        self._accident_grp = grp
        self._vl.addLayout(hl)

        self._vl.addWidget(QLabel("Description des accidents :"))
        self._desc_accidents = QTextEdit()
        self._desc_accidents.setFixedHeight(70)
        self._vl.addWidget(self._desc_accidents)

        self._vl.addWidget(QLabel("Améliorations / mesures préventives :"))
        self._ameliorations_securite = QTextEdit()
        self._ameliorations_securite.setFixedHeight(70)
        self._vl.addWidget(self._ameliorations_securite)

    # ── Section 7 : Sous-traitants ────────────────────────────────────────
    def _build_section7(self):
        self._vl.addWidget(_section_label("7. SOUS-TRAITANTS"))
        self._vl.addWidget(QLabel("Évaluation de 1 (très mauvais) à 5 (excellent)"))
        self._st_section = STSection()
        self._vl.addWidget(self._st_section)

        self._vl.addWidget(QLabel("Notes complémentaires sous-traitants :"))
        self._notes_st = QTextEdit()
        self._notes_st.setFixedHeight(60)
        self._vl.addWidget(self._notes_st)

    # ── Section 8 : Commentaire ───────────────────────────────────────────
    def _build_section8(self):
        self._vl.addWidget(_section_label("8. COMMENTAIRE GÉNÉRAL / SYNTHÈSE"))
        self._vl.addWidget(
            QLabel("Points forts, points faibles, enseignements pour l'avenir :")
        )
        self._commentaire = QTextEdit()
        self._commentaire.setFixedHeight(100)
        self._vl.addWidget(self._commentaire)

    # ── Actions ───────────────────────────────────────────────────────────
    def _build_actions(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#b8cce4;")
        self._vl.addWidget(sep)

        hl = QHBoxLayout()
        btn_save = QPushButton("💾 Enregistrer")
        btn_pdf = QPushButton("📄 Générer PDF")
        btn_pdf.setObjectName("btn_secondary")
        btn_both = QPushButton("💾 + 📄 Enregistrer & PDF")
        btn_del = QPushButton("🗑 Supprimer")
        btn_del.setObjectName("btn_danger")

        btn_save.clicked.connect(self._save)
        btn_pdf.clicked.connect(self._generate_pdf)
        btn_both.clicked.connect(self._save_and_pdf)
        btn_del.clicked.connect(self._delete)

        hl.addWidget(btn_save)
        hl.addWidget(btn_pdf)
        hl.addWidget(btn_both)
        hl.addStretch()
        hl.addWidget(btn_del)
        self._vl.addLayout(hl)

    # ── Data helpers ──────────────────────────────────────────────────────
    def _collect_pp_fixed(self):
        return [
            {
                "role": "Client",
                "nom": self._pp_client_nom.text(),
                "relation": self._pp_client_rel.text(),
                "evaluation": self._pp_client_eval.value(),
            },
            {
                "role": "Architecte",
                "nom": self._pp_arch_nom.text(),
                "relation": self._pp_arch_rel.text(),
                "evaluation": self._pp_arch_eval.value(),
            },
            {
                "role": "Bureau d'étude",
                "nom": self._pp_be_nom.text(),
                "relation": self._pp_be_rel.text(),
                "evaluation": self._pp_be_eval.value(),
            },
        ]

    def _build_data(self) -> dict:
        return {
            "id": self._loaded_id,
            "id_chantier": self._id_chantier.text().strip(),
            "date_bilan": self._date_bilan.text().strip()
            or date.today().strftime("%d/%m/%Y"),
            "delai_soumission": self._delai_contractuel.value() or None,
            "delai_contractuel": self._delai_contractuel.value() or None,
            "delai_complementaire": self._delai_complementaire.value() or None,
            "delai_reel": (self._delai_contractuel.value() + self._delai_complementaire.value()) or None,
            "unite_delai": self._unite_delai.currentText(),
            "montant_base_pv": self._montant_base.value() or None,
            "montant_decomptes_pv": self._montant_decomptes.value() or None,
            "prix_de_revient": self._prix_de_revient.value() or None,
            "marge_devis": self._marge_devis.value() or None,
            "marge_finale": None,
            "niveau_qualite": self._niveau_qualite.toPlainText() or None,
            "satisfaction_client": self._satisfaction_client.value(),
            "travaux_non_satisfaisants": self._travaux_non_sat.toPlainText() or None,
            "ameliorations_qualite": self._ameliorations_qualite.toPlainText() or None,
            "accidents_chantier": "Oui" if self._accident_oui.isChecked() else "Non",
            "description_accidents": self._desc_accidents.toPlainText() or None,
            "ameliorations_securite": self._ameliorations_securite.toPlainText()
            or None,
            "commentaire_general": self._commentaire.toPlainText() or None,
            "notes_sous_traitants": self._notes_st.toPlainText() or None,
            "parties_prenantes": self._collect_pp_fixed() + self._pp_extra.get_data(),
            "sous_traitants": self._st_section.get_data(),
            "postes_perte": self._postes_perte.get_data(),
            "postes_surbenefice": self._postes_surb.get_data(),
            "travaux_internes": self._travaux.get_data(),
        }

    def _save(self):
        if not self._id_chantier.text().strip():
            QMessageBox.warning(
                self, "Champ obligatoire", "L'ID Chantier est obligatoire."
            )
            return
        data = self._build_data()
        new_id = db.save_bilan(data)
        self._loaded_id = new_id
        self._refresh_combo()
        self._main.status(f"Bilan enregistré (ID: {new_id})")

    def _generate_pdf(self):
        id_c = self._id_chantier.text().strip()
        if not id_c:
            QMessageBox.warning(
                self, "Champ obligatoire", "L'ID Chantier est obligatoire."
            )
            return
        data = self._build_data()
        ch = self._chantier_info or {
            "intitule": "",
            "gestionnaire": "",
            "client": "",
            "secteur": "",
            "province": "",
        }
        pdf_bytes = pdf_export.generate_pdf(data, ch, self._montant_facture)
        fname = f"Bilan_{id_c}_{date.today().strftime('%Y%m%d')}.pdf"
        default_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PDFs"
        )
        os.makedirs(default_dir, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le PDF", os.path.join(default_dir, fname), "PDF (*.pdf)"
        )
        if path:
            with open(path, "wb") as f:
                f.write(pdf_bytes)
            self._main.status(f"PDF enregistré : {path}")

    def _save_and_pdf(self):
        self._save()
        self._generate_pdf()

    def _delete(self):
        if not self._loaded_id:
            return
        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            "Supprimer définitivement ce bilan ? Cette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.delete_bilan(self._loaded_id)
            self._loaded_id = None
            self.reset_form()
            self._main.status("Bilan supprimé.")

    # ── Chargement / reset ────────────────────────────────────────────────
    def reset_form(self):
        self._loaded_id = None
        self._chantier_info = None
        self._montant_facture = 0.0
        self._id_chantier.setText("")
        self._date_bilan.setText(date.today().strftime("%d/%m/%Y"))
        for spin in (self._delai_contractuel, self._delai_complementaire):
            spin.setValue(0)
        self._delai_reel.setText("—")
        self._unite_delai.setCurrentText("JC")
        for s in (
            self._montant_base,
            self._montant_decomptes,
            self._prix_de_revient,
            self._marge_devis,
        ):
            s.setValue(0.0)
        self._rp_compare_widget.setVisible(False)
        for w in (
            self._pp_client_nom,
            self._pp_client_rel,
            self._pp_arch_nom,
            self._pp_arch_rel,
            self._pp_be_nom,
            self._pp_be_rel,
        ):
            w.setText("")
        for s in (self._pp_client_eval, self._pp_arch_eval, self._pp_be_eval):
            s.setValue(3)
        self._pp_extra.clear_rows()
        self._postes_perte.clear_rows()
        self._postes_surb.clear_rows()
        self._travaux.clear_rows()
        self._st_section.clear_rows()
        for te in (
            self._niveau_qualite,
            self._travaux_non_sat,
            self._ameliorations_qualite,
            self._desc_accidents,
            self._ameliorations_securite,
            self._commentaire,
            self._notes_st,
        ):
            te.setPlainText("")
        self._satisfaction_client.setValue(3)
        self._accident_non.setChecked(True)
        self._info_chantier.setVisible(False)
        self._warn_chantier.setText("")
        self._refresh_combo()

    def load_bilan(self, bilan_id: int):
        bilan = db.load_bilan(bilan_id)
        if not bilan:
            return
        self._loaded_id = bilan["id"]

        self._id_chantier.blockSignals(True)
        self._id_chantier.setText(str(bilan["id_chantier"]))
        self._id_chantier.blockSignals(False)

        self._date_bilan.setText(
            bilan.get("date_bilan") or date.today().strftime("%d/%m/%Y")
        )
        self._delai_contractuel.setValue(bilan.get("delai_contractuel") or 0)
        self._delai_complementaire.setValue(bilan.get("delai_complementaire") or 0)
        idx = self._unite_delai.findText(bilan.get("unite_delai") or "JC")
        if idx >= 0:
            self._unite_delai.setCurrentIndex(idx)
        self._montant_base.setValue(bilan.get("montant_base_pv") or 0.0)
        self._montant_decomptes.setValue(bilan.get("montant_decomptes_pv") or 0.0)
        self._prix_de_revient.setValue(bilan.get("prix_de_revient") or 0.0)
        self._marge_devis.setValue(bilan.get("marge_devis") or 0.0)
        self._niveau_qualite.setPlainText(bilan.get("niveau_qualite") or "")
        self._satisfaction_client.setValue(bilan.get("satisfaction_client") or 3)
        self._travaux_non_sat.setPlainText(bilan.get("travaux_non_satisfaisants") or "")
        self._ameliorations_qualite.setPlainText(
            bilan.get("ameliorations_qualite") or ""
        )
        if (bilan.get("accidents_chantier") or "Non") == "Oui":
            self._accident_oui.setChecked(True)
        else:
            self._accident_non.setChecked(True)
        self._desc_accidents.setPlainText(bilan.get("description_accidents") or "")
        self._ameliorations_securite.setPlainText(
            bilan.get("ameliorations_securite") or ""
        )
        self._commentaire.setPlainText(bilan.get("commentaire_general") or "")
        self._notes_st.setPlainText(bilan.get("notes_sous_traitants") or "")

        # PP fixes
        pp_fixed = {
            p["role"]: p
            for p in bilan.get("parties_prenantes", [])
            if p.get("role") in _FIXED_PP_ROLES
        }
        pp_extra = [
            p
            for p in bilan.get("parties_prenantes", [])
            if p.get("role") not in _FIXED_PP_ROLES
        ]

        for role, (nom_e, rel_e, eval_s) in [
            (
                "Client",
                (self._pp_client_nom, self._pp_client_rel, self._pp_client_eval),
            ),
            ("Architecte", (self._pp_arch_nom, self._pp_arch_rel, self._pp_arch_eval)),
            ("Bureau d'étude", (self._pp_be_nom, self._pp_be_rel, self._pp_be_eval)),
        ]:
            p = pp_fixed.get(role, {})
            nom_e.setText(p.get("nom") or "")
            rel_e.setText(p.get("relation") or "")
            eval_s.setValue(p.get("evaluation") or 3)

        self._pp_extra.load(pp_extra)
        self._st_section.load(bilan.get("sous_traitants", []))
        self._postes_perte.load(bilan.get("postes_perte", []))
        self._postes_surb.load(bilan.get("postes_surbenefice", []))
        self._travaux.load(bilan.get("travaux_internes", []))

        self._chantier_info = db.get_chantier(str(bilan["id_chantier"]))
        self._montant_facture = db.get_montant_facture(str(bilan["id_chantier"]))
        if self._chantier_info:
            self._show_chantier_info(self._chantier_info)

        self._update_calculs()

    def _show_chantier_info(self, ch: dict):
        self._lbl_intitule.setText(f"Chantier : {ch.get('intitule', '—')}")
        self._lbl_gestionnaire.setText(f"Gestionnaire : {ch.get('gestionnaire', '—')}")
        self._lbl_client.setText(f"Client : {ch.get('client', '—')}")
        self._lbl_secteur.setText(f"Secteur : {ch.get('secteur', '—')}")
        self._info_chantier.setVisible(True)

    def _on_combo_select(self, idx):
        if idx <= 0:
            return
        bilan_id = self._combo_bilans.itemData(idx)
        if bilan_id and bilan_id != self._loaded_id:
            self.load_bilan(bilan_id)
