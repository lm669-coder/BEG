from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
)
from PyQt6.QtGui import QFont

import database as db

_MPL = None  # (FigureCanvasQTAgg, Figure) ou False si indisponible


def _load_mpl():
    """matplotlib est lourd : importé seulement à l'ouverture du Dashboard."""
    global _MPL
    if _MPL is None:
        try:
            import matplotlib

            matplotlib.use("QtAgg")
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure

            _MPL = (FigureCanvasQTAgg, Figure)
        except Exception:
            _MPL = False
    return _MPL


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
        for c in (
            self._card_bilans,
            self._card_sat,
            self._card_marge,
            self._card_chantiers,
        ):
            hl_m.addWidget(c)
        vl.addLayout(hl_m)

        self._vl_main = vl
        self._canvas = None
        self._fig = None

    def _ensure_canvas(self) -> bool:
        if self._canvas is None:
            mpl = _load_mpl()
            if mpl:
                canvas_cls, fig_cls = mpl
                self._fig = fig_cls(figsize=(12, 4), tight_layout=True)
                self._canvas = canvas_cls(self._fig)
                self._vl_main.addWidget(self._canvas, 1)
            else:
                self._canvas = False
                self._vl_main.addWidget(
                    QLabel("matplotlib non disponible — graphiques désactivés.")
                )
        return bool(self._canvas)

    def refresh(self):
        bilans = db.get_all_bilans()
        chantiers = db.get_all_chantiers()

        self._card_bilans.set_value(str(len(bilans)))

        sats = [
            b["satisfaction_client"]
            for b in bilans
            if b.get("satisfaction_client") is not None
        ]
        self._card_sat.set_value(f"{sum(sats)/len(sats):.1f}/5" if sats else "—")

        marges = [
            b["marge_finale"] for b in bilans if b.get("marge_finale") is not None
        ]
        self._card_marge.set_value(f"{sum(marges)/len(marges):.1f}%" if marges else "—")

        self._card_chantiers.set_value(f"{len(chantiers)} / {len(bilans)}")

        if not bilans or not self._ensure_canvas():
            return

        self._fig.clear()

        ax1 = self._fig.add_subplot(1, 2, 1)
        sat_data = [
            (b["id_chantier"], b["satisfaction_client"])
            for b in bilans
            if b.get("satisfaction_client") is not None
        ]
        if sat_data:
            ids, vals = zip(*sat_data[-30:])
            ax1.bar(range(len(ids)), vals, color=BEG_BLUE, alpha=0.8)
            ax1.set_xticks(range(len(ids)))
            ax1.set_xticklabels(
                [str(i) for i in ids], rotation=45, ha="right", fontsize=7
            )
            ax1.set_ylim(0, 5.5)
            ax1.set_title("Satisfaction client /5", fontweight="bold", color=BEG_BLUE)
            ax1.axhline(y=3, color="#aaa", linestyle="--", linewidth=0.8)

        ax2 = self._fig.add_subplot(1, 2, 2)
        marge_data = [
            (b["id_chantier"], b["marge_finale"])
            for b in bilans
            if b.get("marge_finale") is not None
        ]
        if marge_data:
            ids2, vals2 = zip(*marge_data[-30:])
            colors = ["#27ae60" if v >= 0 else "#c0392b" for v in vals2]
            ax2.bar(range(len(ids2)), vals2, color=colors, alpha=0.8)
            ax2.set_xticks(range(len(ids2)))
            ax2.set_xticklabels(
                [str(i) for i in ids2], rotation=45, ha="right", fontsize=7
            )
            ax2.set_title("Marge finale (%)", fontweight="bold", color=BEG_BLUE)
            ax2.axhline(y=0, color="#333", linewidth=0.8)

        self._canvas.draw()
