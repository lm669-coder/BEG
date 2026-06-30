import io
import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    Image as RLImage,
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

if getattr(sys, "frozen", False):
    _BASE = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOGO_PATH = os.path.join(_BASE, "Données", "logo.png")

# ── Palette Apple-inspired ────────────────────────────────────────────────────
C_DARK = colors.HexColor("#1d1d1f")  # primary text
C_MID = colors.HexColor("#424245")  # medium text / section titles
C_GRAY = colors.HexColor("#6e6e73")  # labels / secondary text
C_SUBTLE = colors.HexColor("#aeaeb2")  # placeholder / disabled
C_DIV = colors.HexColor("#d2d2d7")  # thin separators
C_STRIPE = colors.HexColor("#f5f5f7")  # very light alternating row
C_ACCENT = colors.HexColor("#0066cc")  # accent blue (used sparingly)
C_WHITE = colors.white
C_GREEN = colors.HexColor("#e8f8ee")  # positive row bg
C_RED = colors.HexColor("#fff0f0")  # negative row bg
C_GREEN_T = colors.HexColor("#1a7a3c")  # positive text
C_RED_T = colors.HexColor("#c0392b")  # negative text

PAGE_W, PAGE_H = A4
MARGIN = 1.6 * cm
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Styles ────────────────────────────────────────────────────────────────────
def _s(name, **kw):
    defaults = dict(
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=C_DARK,
        spaceBefore=0,
        spaceAfter=0,
    )
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


STYLES = {
    "doc_title": _s(
        "doc_title",
        fontSize=20,
        fontName="Helvetica-Bold",
        textColor=C_DARK,
        alignment=TA_CENTER,
        leading=24,
    ),
    "doc_sub": _s("doc_sub", fontSize=9, textColor=C_GRAY, alignment=TA_CENTER),
    "sec": _s(
        "sec",
        fontSize=12,
        fontName="Helvetica-Bold",
        textColor=C_MID,
        leading=15,
        spaceBefore=2,
    ),
    "label": _s("label", fontSize=8.5, textColor=C_GRAY),
    "value": _s("value", fontSize=8.5, textColor=C_DARK),
    "value_b": _s("value_b", fontSize=8.5, fontName="Helvetica-Bold", textColor=C_DARK),
    "small": _s("small", fontSize=7.5, textColor=C_GRAY),
    "note": _s(
        "note", fontSize=8, fontName="Helvetica-Oblique", textColor=C_GRAY, leading=11
    ),
    "body": _s("body", fontSize=8.5, leading=13, textColor=C_DARK),
    "pos_val": _s("pos_val", fontSize=8.5, textColor=C_GREEN_T),
    "neg_val": _s("neg_val", fontSize=8.5, textColor=C_RED_T),
    "footer": _s("footer", fontSize=7, textColor=C_SUBTLE, alignment=TA_RIGHT),
    "hdr_right": _s("hdr_right", fontSize=7.5, textColor=C_GRAY, alignment=TA_RIGHT),
    "th": _s(
        "th", fontSize=7.5, fontName="Helvetica-Bold", textColor=C_GRAY, leading=10
    ),
    "subsec": _s(
        "subsec",
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=C_ACCENT,
        spaceAfter=5,
    ),
    "loss_lbl": _s(
        "loss_lbl",
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=C_RED_T,
        spaceAfter=5,
    ),
    "gain_lbl": _s(
        "gain_lbl",
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=C_GREEN_T,
        spaceAfter=5,
    ),
    "int_lbl": _s(
        "int_lbl",
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=C_ACCENT,
        spaceAfter=5,
    ),
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _euro(v):
    if v is None:
        return "—"
    return f"{float(v):,.2f} €".replace(",", " ").replace(".", ",")


def _pct(v):
    if v is None:
        return "—"
    return f"{float(v):.1f} %"


def _stars(n):
    if n is None:
        return "—"
    return "★" * int(n) + "·" * (5 - int(n)) + f"  {n}/5"


def _val(v):
    return str(v) if v not in (None, "", "None") else "—"


# ── Layout components ─────────────────────────────────────────────────────────
def _section_header(number, title):
    """Apple-style: thin hairline + small caps bold label."""
    return [
        Spacer(1, 0.30 * cm),
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_DIV, spaceAfter=5),
        Paragraph(f"{number}. {title.upper()}", STYLES["sec"]),
        Spacer(1, 0.15 * cm),
    ]


def _kv_table(rows, col_widths=None):
    """Clean 2-column label/value table — only thin row separators, no outer border."""
    if not col_widths:
        col_widths = [CONTENT_W * 0.36, CONTENT_W * 0.64]

    data = []
    for label, value in rows:
        data.append(
            [
                Paragraph(label, STYLES["label"]),
                Paragraph(_val(value), STYLES["value"]),
            ]
        )

    n = len(data)
    tbl = Table(data, colWidths=col_widths)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, n - 2), 0.25, C_DIV),  # row separators only
        ("NOSPLIT", (0, 0), (-1, -1)),
    ]
    tbl.setStyle(TableStyle(style))
    return tbl


def _data_table(
    header_row,
    data_rows,
    col_widths,
    row_bg=None,
    last_row_bold=False,
    extra_style=None,
):
    """General-purpose data table with clean Apple look."""
    all_rows = [header_row] + data_rows
    n = len(all_rows)

    tbl = Table(all_rows, colWidths=col_widths)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        # Header row: light gray bg
        ("BACKGROUND", (0, 0), (-1, 0), C_STRIPE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, C_DIV),
        # Row separators
        ("LINEBELOW", (0, 1), (-1, n - 2), 0.25, C_DIV),
    ]

    if row_bg:
        for i, bg in enumerate(row_bg, start=1):
            if bg and i < n:
                style.append(("BACKGROUND", (0, i), (-1, i), bg))

    if last_row_bold and n > 1:
        style += [
            ("BACKGROUND", (0, n - 1), (-1, n - 1), C_STRIPE),
            ("LINEABOVE", (0, n - 1), (-1, n - 1), 0.5, C_DIV),
        ]

    if extra_style:
        style += extra_style

    tbl.setStyle(TableStyle(style))
    return tbl


# ── Main export ───────────────────────────────────────────────────────────────
def generate_pdf(bilan: dict, chantier: dict, montant_facture: float) -> bytes:
    buf = io.BytesIO()

    id_c = bilan.get("id_chantier", "")
    titre = chantier.get("intitule") or ""

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.6 * cm,
        bottomMargin=1.8 * cm,
        title=f"Bilan d'expérience — {id_c} — {titre}",
    )

    story = []

    # ── En-tête ───────────────────────────────────────────────────────────────
    sub_parts = [p for p in [id_c, titre, bilan.get("date_bilan")] if p]
    title_para = Paragraph("BILAN D'EXPÉRIENCE", STYLES["doc_title"])
    sub_para = Paragraph(" — ".join(sub_parts), STYLES["doc_sub"])

    if os.path.exists(LOGO_PATH):
        ir = ImageReader(LOGO_PATH)
        iw, ih = ir.getSize()
        max_h = 1.6 * cm
        max_w = 4.5 * cm
        ratio = iw / ih
        if ratio > max_w / max_h:
            logo_w, logo_h = max_w, max_w / ratio
        else:
            logo_w, logo_h = max_h * ratio, max_h
        logo_cell = RLImage(LOGO_PATH, width=logo_w, height=logo_h)
        hdr = Table(
            [[[title_para, Spacer(1, 0.1 * cm), sub_para], logo_cell]],
            colWidths=[CONTENT_W * 0.68, CONTENT_W * 0.32],
        )
        hdr.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(hdr)
    else:
        story.append(Spacer(1, 0.1 * cm))
        story.append(title_para)
        story.append(Spacer(1, 0.15 * cm))
        story.append(sub_para)

    story.append(Spacer(1, 0.2 * cm))
    story.append(HRFlowable(width=CONTENT_W, thickness=1, color=C_DARK, spaceAfter=0))
    story.append(Spacer(1, 0.1 * cm))

    # ── 1. Identification ─────────────────────────────────────────────────────
    story += _section_header(1, "Identification")
    story.append(
        _kv_table(
            [
                ("Référence chantier", id_c),
                ("Nom du chantier", chantier.get("intitule")),
                ("Gestionnaire", chantier.get("gestionnaire")),
                ("Client", chantier.get("client")),
                ("Secteur", chantier.get("secteur")),
                ("Province", chantier.get("province")),
                ("Date du bilan", bilan.get("date_bilan")),
            ]
        )
    )

    # ── 2. Retenues RP & RD ───────────────────────────────────────────────────
    rp_dem = bilan.get("rp_demandee")
    rp_re = bilan.get("rp_realisee")
    rp_st = bilan.get("rp_statut")
    rd_dem = bilan.get("rd_a_demander")
    rd_re = bilan.get("rd_realisee")
    rd_st = bilan.get("rd_statut")

    if any([rp_dem, rp_re, rp_st, rd_dem, rd_re, rd_st]):
        story += _section_header(2, "Retenues RP & RD")
        story.append(
            _kv_table(
                [
                    ("RP — Date demandée", rp_dem),
                    ("RP — Date réalisée", rp_re),
                    ("RP — Statut", rp_st),
                    ("RD — À demander", rd_dem),
                    ("RD — Date réalisée", rd_re),
                    ("RD — Statut", rd_st),
                ],
                col_widths=[CONTENT_W * 0.36, CONTENT_W * 0.64],
            )
        )

    # ── 3. Performance ────────────────────────────────────────────────────────
    story += _section_header(3, "Performance")

    ds = bilan.get("delai_soumission")
    dc = bilan.get("delai_contractuel")
    dcomp = bilan.get("delai_complementaire") or 0
    dr = bilan.get("delai_reel")
    unite = bilan.get("unite_delai", "JC")
    respect = ((dc or 0) + dcomp - dr) if (dc is not None and dr is not None) else None

    story.append(Paragraph("Délais", STYLES["subsec"]))
    story.append(
        _kv_table(
            [
                ("Délai soumission", f"{ds} {unite}" if ds else "—"),
                ("Délai contractuel", f"{dc} {unite}" if dc else "—"),
                ("Délai complémentaire accordé", f"{dcomp} {unite}"),
                ("Délai réel d'exécution", f"{dr} {unite}" if dr else "—"),
                (
                    "Écart (+ = avance / − = retard)",
                    f"{respect:+d} {unite}" if respect is not None else "—",
                ),
            ]
        )
    )

    story.append(Spacer(1, 0.2 * cm))

    mb = bilan.get("montant_base_pv")
    md = bilan.get("montant_decomptes_pv") or 0
    pr = bilan.get("prix_de_revient")
    total_pv = (mb or 0) + md
    pct_dec = (md / mb * 100) if mb else None
    mg_devis = bilan.get("marge_devis")
    mg_finale = bilan.get("marge_finale")

    story.append(Paragraph("Budget & Marges", STYLES["subsec"]))
    story.append(
        _kv_table(
            [
                ("Montant de base PV", _euro(mb)),
                ("Montant des décomptes PV", _euro(md)),
                ("% décomptes / base", _pct(pct_dec)),
                ("Total PV (base + décomptes)", _euro(total_pv)),
                ("Prix de revient soumission", _euro(pr)),
                ("Montant total facturé (EA)", _euro(montant_facture)),
                ("Marge devis", _pct(mg_devis)),
                ("Marge finale d'exécution", _pct(mg_finale)),
            ]
        )
    )

    # ── 4. Rendements & exécution ─────────────────────────────────────────────
    postes_perte = bilan.get("postes_perte", [])
    postes_surb = bilan.get("postes_surbenefice", [])
    travaux = bilan.get("travaux_internes", [])

    if postes_perte or postes_surb or travaux:
        story += _section_header(4, "Rendements & Exécution")

        def _postes_tbl(postes, is_loss):
            header = [
                Paragraph(h, STYLES["th"])
                for h in ["Dénomination", "PRS (€)", "PRE (€)", "Écart (€)"]
            ]
            rows = []
            bgs = []
            for p in postes:
                prs = p.get("prs")
                pre = p.get("pre")
                ecart = (pre - prs) if (prs is not None and pre is not None) else None
                txt_s = STYLES["neg_val"] if is_loss else STYLES["pos_val"]
                rows.append(
                    [
                        Paragraph(_val(p.get("denomination")), STYLES["value"]),
                        Paragraph(_euro(prs), STYLES["value"]),
                        Paragraph(_euro(pre), STYLES["value"]),
                        Paragraph(_euro(ecart), txt_s),
                    ]
                )
                bgs.append(C_RED if is_loss else C_GREEN)
            cw = [
                CONTENT_W * 0.46,
                CONTENT_W * 0.18,
                CONTENT_W * 0.18,
                CONTENT_W * 0.18,
            ]
            return _data_table(header, rows, cw, row_bg=bgs)

        if postes_perte:
            story.append(
                Paragraph("Postes évalués trop bas — en perte", STYLES["loss_lbl"])
            )
            story.append(_postes_tbl(postes_perte, is_loss=True))
            story.append(Spacer(1, 0.2 * cm))

        if postes_surb:
            story.append(
                Paragraph("Postes évalués trop haut — surbénéfice", STYLES["gain_lbl"])
            )
            story.append(_postes_tbl(postes_surb, is_loss=False))
            story.append(Spacer(1, 0.2 * cm))

        if travaux:
            story.append(Paragraph("Travaux réalisés en interne", STYLES["int_lbl"]))
            header = [
                Paragraph(h, STYLES["th"])
                for h in ["Dénomination", "H-S (budg.)", "H-E (réel)", "Coefficient"]
            ]
            rows = []
            total_hs = total_he = 0.0
            for t in travaux:
                hs = t.get("heures_soumission") or 0
                he = t.get("heures_execution") or 0
                total_hs += hs
                total_he += he
                coeff = round(he / hs, 3) if hs else None
                rows.append(
                    [
                        Paragraph(_val(t.get("denomination")), STYLES["value"]),
                        Paragraph(f"{hs:.1f} h", STYLES["value"]),
                        Paragraph(f"{he:.1f} h", STYLES["value"]),
                        Paragraph(
                            f"{coeff:.3f}" if coeff is not None else "—",
                            STYLES["value"],
                        ),
                    ]
                )
            coeff_t = round(total_he / total_hs, 3) if total_hs else None
            rows.append(
                [
                    Paragraph("Total", STYLES["value_b"]),
                    Paragraph(f"{total_hs:.1f} h", STYLES["value_b"]),
                    Paragraph(f"{total_he:.1f} h", STYLES["value_b"]),
                    Paragraph(
                        f"{coeff_t:.3f}" if coeff_t is not None else "—",
                        STYLES["value_b"],
                    ),
                ]
            )
            cw = [
                CONTENT_W * 0.46,
                CONTENT_W * 0.18,
                CONTENT_W * 0.18,
                CONTENT_W * 0.18,
            ]
            story.append(_data_table(header, rows, cw, last_row_bold=True))

    # ── 5. Qualité ────────────────────────────────────────────────────────────
    story += _section_header(5, "Qualité")
    story.append(
        _kv_table(
            [
                ("Niveau de qualité global", bilan.get("niveau_qualite")),
                ("Satisfaction client", _stars(bilan.get("satisfaction_client"))),
                ("Travaux non satisfaisants", bilan.get("travaux_non_satisfaisants")),
                ("Améliorations proposées", bilan.get("ameliorations_qualite")),
            ]
        )
    )

    # ── 6. Sécurité ───────────────────────────────────────────────────────────
    story += _section_header(6, "Sécurité")
    story.append(
        _kv_table(
            [
                ("Accident(s) sur chantier", bilan.get("accidents_chantier", "Non")),
                ("Description", bilan.get("description_accidents")),
                ("Améliorations / Prévention", bilan.get("ameliorations_securite")),
            ]
        )
    )

    # ── 7. Parties prenantes ──────────────────────────────────────────────────
    pp_list = bilan.get("parties_prenantes", [])
    if pp_list:
        story += _section_header(7, "Parties Prenantes")
        header = [
            Paragraph(h, STYLES["th"])
            for h in ["Rôle", "Nom", "Relation", "Évaluation"]
        ]
        rows = []
        for pp in pp_list:
            rows.append(
                [
                    Paragraph(_val(pp.get("role")), STYLES["value"]),
                    Paragraph(_val(pp.get("nom")), STYLES["value"]),
                    Paragraph(_val(pp.get("relation")), STYLES["value"]),
                    Paragraph(_stars(pp.get("evaluation")), STYLES["value"]),
                ]
            )
        cw = [CONTENT_W * 0.18, CONTENT_W * 0.24, CONTENT_W * 0.36, CONTENT_W * 0.22]
        story.append(_data_table(header, rows, cw))

    # ── 8. Sous-traitants ─────────────────────────────────────────────────────
    sts = bilan.get("sous_traitants", [])
    if sts:
        story += _section_header(8, "Sous-Traitants")
        criteria_labels = ["Prix", "Délais", "Sécu.", "Qualité", "Réact.", "Comm."]
        header = (
            [Paragraph("Sous-traitant", STYLES["th"])]
            + [Paragraph(c, STYLES["th"]) for c in criteria_labels]
            + [Paragraph("Moy.", STYLES["th"])]
        )
        rows = []
        avg_totals = []
        for st in sts:
            scores = [
                st.get(k)
                for k in (
                    "respect_prix",
                    "respect_delais",
                    "respect_securite",
                    "respect_qualite",
                    "reactivite",
                    "communication",
                )
            ]
            valid = [x for x in scores if x is not None]
            avg = round(sum(valid) / len(valid), 1) if valid else None
            if avg:
                avg_totals.append(avg)
            rows.append(
                [Paragraph(_val(st.get("nom")), STYLES["value"])]
                + [Paragraph(str(sc) if sc else "—", STYLES["value"]) for sc in scores]
                + [Paragraph(f"{avg}" if avg else "—", STYLES["value_b"])]
            )
        if avg_totals:
            overall = round(sum(avg_totals) / len(avg_totals), 1)
            rows.append(
                [Paragraph("Moyenne générale", STYLES["value_b"])]
                + [Paragraph("", STYLES["value"]) for _ in criteria_labels]
                + [Paragraph(f"{overall}/5", STYLES["value_b"])]
            )

        cw = [CONTENT_W * 0.27] + [CONTENT_W * 0.09] * 6 + [CONTENT_W * 0.10]
        tbl = _data_table(
            header,
            rows,
            cw,
            last_row_bold=bool(avg_totals),
            extra_style=[("ALIGN", (1, 0), (-1, -1), "CENTER")],
        )
        story.append(tbl)

        if bilan.get("notes_sous_traitants"):
            story.append(Spacer(1, 0.15 * cm))
            story.append(
                Paragraph(f"Notes : {bilan['notes_sous_traitants']}", STYLES["note"])
            )

    # ── 9. Commentaire général ────────────────────────────────────────────────
    if bilan.get("commentaire_general"):
        story += _section_header(9, "Commentaire Général")
        for line in bilan["commentaire_general"].split("\n"):
            story.append(Paragraph(line or " ", STYLES["body"]))

    # ── Pied de page ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width=CONTENT_W, thickness=0.5, color=C_DIV, spaceAfter=4))
    story.append(
        Paragraph(
            f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", STYLES["footer"]
        )
    )

    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_SUBTLE)
        canvas.drawRightString(PAGE_W - MARGIN, 0.7 * cm, f"{doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()
