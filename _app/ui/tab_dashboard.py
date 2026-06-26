from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import database as db

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    HAS_MPL = True
except Exception:
    HAS_MPL = False

BEG_BLUE = "#1a3a5c"


class MetricCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            "QFrame { background: white; border: 1px solid #d0d9e8;"
            " border-top: 3px solid #1a3a5c; border-radius: 6px; }"
        )
        vl = QVBoxLayout(self)
        vl.setContentsMargins(14, 12, 14, 12)
        vl.setSpacing(4)
        self._title = QLabel(title)
        self._title.setFont(QFont("Segoe UI", 8))
        self._title.setStyleSheet("color: #6b7c93; border: none;")
        self._value = QLabel("—")
        self._value.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._value.setStyleSheet(f"color: {BEG_BLUE}; border: none;")
        vl.addWidget(self._title)
        vl.addWidget(self._value)

    def set_value(self, v: str):
        self._value.setText(v)


class DashboardTab(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window

        vl = QVBoxLayout(self)
        vl.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Dashboard — Vue d'ensemble")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{BEG_BLUE};")
        vl.addWidget(title)

        # Métriques
        hl_m = QHBoxLayout()
        self._card_bilans = MetricCard("Bilans enregistrés")
        self._card_sat = MetricCard("Satisfaction client moy.")
        self._card_marge = MetricCard("Marge finale moy.")
        self._card_chantiers = MetricCard("Chantiers / Bilans")
        for c in (self._card_bilans, self._card_sat, self._card_marge, self._card_chantiers):
            hl_m.addWidget(c)
        vl.addLayout(hl_m)

        if HAS_MPL:
            self._fig = Figure(figsize=(12, 4), tight_layout=True)
            self._canvas = FigureCanvasQTAgg(self._fig)
            vl.addWidget(self._canvas, 1)
        else:
            vl.addWidget(QLabel("matplotlib non disponible — graphiques désactivés."))

        vl.addStretch()

    def refresh(self):
        bilans = db.get_all_bilans()
        chantiers = db.get_all_chantiers()

        self._card_bilans.set_value(str(len(bilans)))

        sats = [b["satisfaction_client"] for b in bilans if b.get("satisfaction_client") is not None]
        self._card_sat.set_value(f"{sum(sats)/len(sats):.1f}/5" if sats else "—")

        marges = [b["marge_finale"] for b in bilans if b.get("marge_finale") is not None]
        self._card_marge.set_value(f"{sum(marges)/len(marges):.1f}%" if marges else "—")

        self._card_chantiers.set_value(f"{len(chantiers)} / {len(bilans)}")

        if not HAS_MPL or not bilans:
            return

        self._fig.clear()

        ax1 = self._fig.add_subplot(1, 2, 1)
        sat_data = [(b["id_chantier"], b["satisfaction_client"]) for b in bilans if b.get("satisfaction_client") is not None]
        if sat_data:
            ids, vals = zip(*sat_data[-30:])
            ax1.bar(range(len(ids)), vals, color=BEG_BLUE, alpha=0.8)
            ax1.set_xticks(range(len(ids)))
            ax1.set_xticklabels([str(i) for i in ids], rotation=45, ha="right", fontsize=7)
            ax1.set_ylim(0, 5.5)
            ax1.set_title("Satisfaction client /5", fontweight="bold", color=BEG_BLUE)
            ax1.axhline(y=3, color="#aaa", linestyle="--", linewidth=0.8)

        ax2 = self._fig.add_subplot(1, 2, 2)
        marge_data = [(b["id_chantier"], b["marge_finale"]) for b in bilans if b.get("marge_finale") is not None]
        if marge_data:
            ids2, vals2 = zip(*marge_data[-30:])
            colors = ["#27ae60" if v >= 0 else "#c0392b" for v in vals2]
            ax2.bar(range(len(ids2)), vals2, color=colors, alpha=0.8)
            ax2.set_xticks(range(len(ids2)))
            ax2.set_xticklabels([str(i) for i in ids2], rotation=45, ha="right", fontsize=7)
            ax2.set_title("Marge finale (%)", fontweight="bold", color=BEG_BLUE)
            ax2.axhline(y=0, color="#333", linewidth=0.8)

        self._canvas.draw()
