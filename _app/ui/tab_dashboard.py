from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
)
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen

import database as db

BEG_BLUE = "#1a3a5c"
GREEN = "#27ae60"
RED = "#c0392b"


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


class BarChart(QWidget):
    """Histogramme dessiné avec QPainter (remplace matplotlib : démarrage et
    taille de l'exe bien plus faibles)."""

    def __init__(self, title: str, ref_line: float | None = None, parent=None):
        super().__init__(parent)
        self._title = title
        self._ref = ref_line
        self._data: list[tuple[str, float]] = []
        self._ymin = 0.0
        self._ymax = 1.0
        self._signed_colors = False
        self.setMinimumHeight(260)

    def set_data(self, data, ymin=None, ymax=None, signed_colors=False):
        self._data = [(str(k), float(v)) for k, v in data]
        vals = [v for _, v in self._data] + ([self._ref] if self._ref is not None else [])
        lo = min(vals + [0.0]) if vals else 0.0
        hi = max(vals + [0.0]) if vals else 1.0
        pad = (hi - lo) * 0.08 or 1.0
        self._ymin = ymin if ymin is not None else (lo - pad if lo < 0 else 0.0)
        self._ymax = ymax if ymax is not None else hi + pad
        self._signed_colors = signed_colors
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QColor(BEG_BLUE))
        f = QFont("Segoe UI", 10, QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(QRectF(0, 4, w, 22), Qt.AlignmentFlag.AlignCenter, self._title)
        if not self._data:
            p.setPen(QColor("#6b7c93"))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "Pas de données")
            return

        left, right, top, bottom = 42, 10, 32, 62
        pw, ph = w - left - right, h - top - bottom
        span = (self._ymax - self._ymin) or 1.0

        def y_of(v):
            return top + ph * (1 - (v - self._ymin) / span)

        # grille + axe Y
        p.setFont(QFont("Segoe UI", 7))
        for i in range(5):
            v = self._ymin + span * i / 4
            y = y_of(v)
            p.setPen(QPen(QColor("#e3e8ef"), 1))
            p.drawLine(QPointF(left, y), QPointF(w - right, y))
            p.setPen(QColor("#6b7c93"))
            p.drawText(
                QRectF(0, y - 8, left - 4, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{v:.1f}".rstrip("0").rstrip("."),
            )
        if self._ref is not None:
            p.setPen(QPen(QColor("#aaaaaa"), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(left, y_of(self._ref)), QPointF(w - right, y_of(self._ref)))

        # barres
        n = len(self._data)
        slot = pw / n
        bw = min(slot * 0.7, 40)
        zero_y = y_of(0 if self._ymin <= 0 <= self._ymax else self._ymin)
        p.setPen(Qt.PenStyle.NoPen)
        for i, (label, v) in enumerate(self._data):
            cx = left + slot * (i + 0.5)
            col = QColor(GREEN if v >= 0 else RED) if self._signed_colors else QColor(BEG_BLUE)
            col.setAlpha(205)
            y = y_of(v)
            p.setBrush(col)
            p.drawRect(QRectF(cx - bw / 2, min(y, zero_y), bw, abs(zero_y - y)))
            # libellé incliné
            p.save()
            p.translate(cx, h - bottom + 6)
            p.rotate(45)
            p.setPen(QColor("#333333"))
            p.setFont(QFont("Segoe UI", 7))
            p.drawText(QPointF(0, 0), label)
            p.restore()
            p.setPen(Qt.PenStyle.NoPen)

        # axe zéro
        p.setPen(QPen(QColor("#333333"), 1))
        p.drawLine(QPointF(left, zero_y), QPointF(w - right, zero_y))


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

        hl_c = QHBoxLayout()
        self._chart_sat = BarChart("Satisfaction client /5", ref_line=3)
        self._chart_marge = BarChart("Marge finale (%)")
        hl_c.addWidget(self._chart_sat, 1)
        hl_c.addWidget(self._chart_marge, 1)
        vl.addLayout(hl_c, 1)

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

        self._chart_sat.set_data(
            [
                (b["id_chantier"], b["satisfaction_client"])
                for b in bilans
                if b.get("satisfaction_client") is not None
            ][-30:],
            ymin=0,
            ymax=5.5,
        )
        self._chart_marge.set_data(
            [
                (b["id_chantier"], b["marge_finale"])
                for b in bilans
                if b.get("marge_finale") is not None
            ][-30:],
            signed_colors=True,
        )
