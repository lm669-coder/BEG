import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta

import database as db
import pdf_export
import import_data as imp

st.set_page_config(
    page_title="Bilan d'Expérience",
    page_icon="🦺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS minimal ───────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
.section-header {
    background:#1a3a5c; color:white; padding:6px 12px;
    border-radius:4px; font-weight:bold; margin:16px 0 8px 0;
}
.sub-header { color:#2e6da4; font-weight:600; margin:10px 0 4px 0; }
.stButton > button { border-radius:4px; }
div[data-testid="stMetricValue"] { font-size:1.4rem; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Constantes champs dynamiques ──────────────────────────────────────────────
ST_FIELDS = [
    "nom",
    "respect_prix",
    "respect_delais",
    "respect_securite",
    "respect_qualite",
    "reactivite",
    "communication",
]
POSTE_FIELDS = ["denomination", "prs", "pre"]
TRAVAIL_FIELDS = ["denomination", "heures_soumission", "heures_execution"]
PP_EXTRA_FIELDS = ["role", "nom", "relation", "evaluation"]


# ── Helpers session state ─────────────────────────────────────────────────────
def _get(key, default=None):
    return st.session_state.get(key, default)


def _set(key, val):
    st.session_state[key] = val


def _clear_dynamic(cat, n, fields):
    for i in range(n):
        for f in fields:
            k = f"{cat}_{i}_{f}"
            if k in st.session_state:
                del st.session_state[k]
    _set(f"n_{cat}", 0)


def _remove_item(cat, idx, fields):
    n = _get(f"n_{cat}", 0)
    for i in range(idx, n - 1):
        for f in fields:
            st.session_state[f"{cat}_{i}_{f}"] = _get(f"{cat}_{i+1}_{f}", "")
    for f in fields:
        k = f"{cat}_{n-1}_{f}"
        if k in st.session_state:
            del st.session_state[k]
    _set(f"n_{cat}", n - 1)


def _add_item(cat, fields, defaults=None):
    n = _get(f"n_{cat}", 0)
    for f in fields:
        k = f"{cat}_{n}_{f}"
        if k not in st.session_state:
            st.session_state[k] = (defaults or {}).get(f, "")
    _set(f"n_{cat}", n + 1)


def _load_list_to_state(cat, items, fields):
    for i, item in enumerate(items):
        for f in fields:
            st.session_state[f"{cat}_{i}_{f}"] = item.get(f, "") or ""
    _set(f"n_{cat}", len(items))


def _collect_list(cat, n, fields):
    result = []
    for i in range(n):
        row = {}
        for f in fields:
            row[f] = _get(f"{cat}_{i}_{f}") or None
        if any(v for v in row.values() if v):
            result.append(row)
    return result


# ── Init DB ───────────────────────────────────────────────────────────────────
db.init_db()


# ── Sidebar navigation ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🦺 Bilans d'expérience")
    st.divider()
    page = st.radio(
        "Navigation",
        [
            "📝 Nouveau / Modifier bilan",
            "📋 Historique bilans",
            "📊 Dashboard",
            "⬆ Importer données Excel",
        ],
        label_visibility="collapsed",
        key="nav_page",
    )
    st.divider()
    total = len(db.get_all_bilans())
    st.metric("Bilans enregistrés", total)


# ── Helper : charger un bilan dans le session state ───────────────────────────
def _apply_bilan_to_state(bilan):
    _set("loaded_bilan_id", bilan["id"])
    _set("f_id_chantier", bilan["id_chantier"])
    _set("f_date_bilan", bilan.get("date_bilan") or "")
    _set("f_delai_soumission", bilan.get("delai_soumission") or 0)
    _set("f_delai_contractuel", bilan.get("delai_contractuel") or 0)
    _set("f_delai_complementaire", bilan.get("delai_complementaire") or 0)
    _set("f_delai_reel", bilan.get("delai_reel") or 0)
    _set("f_unite_delai", bilan.get("unite_delai") or "JC")
    _set("f_montant_base_pv", bilan.get("montant_base_pv") or 0.0)
    _set("f_montant_decomptes_pv", bilan.get("montant_decomptes_pv") or 0.0)
    _set("f_marge_devis", bilan.get("marge_devis") or 0.0)
    _set("f_marge_finale", bilan.get("marge_finale") or 0.0)
    _set("f_niveau_qualite", bilan.get("niveau_qualite") or "")
    _set("f_satisfaction_client", bilan.get("satisfaction_client") or 3)
    _set("f_travaux_non_satisfaisants", bilan.get("travaux_non_satisfaisants") or "")
    _set("f_ameliorations_qualite", bilan.get("ameliorations_qualite") or "")
    _set("f_accidents", bilan.get("accidents_chantier") or "Non")
    _set("f_desc_accidents", bilan.get("description_accidents") or "")
    _set("f_ameliorations_securite", bilan.get("ameliorations_securite") or "")
    _set("f_commentaire_general", bilan.get("commentaire_general") or "")
    _set("f_notes_st", bilan.get("notes_sous_traitants") or "")
    for fk in ["rp_demandee", "rp_realisee", "rp_statut"]:
        _set(f"f_{fk}", bilan.get(fk) or "")
    _set("f_prix_de_revient", bilan.get("prix_de_revient") or 0.0)
    pp_fixed = [
        p
        for p in bilan["parties_prenantes"]
        if p["role"] in ("Client", "Architecte", "Bureau d'étude")
    ]
    pp_extra = [
        p
        for p in bilan["parties_prenantes"]
        if p["role"] not in ("Client", "Architecte", "Bureau d'étude")
    ]
    for r, rkey in [
        ("Client", "client"),
        ("Architecte", "architecte"),
        ("Bureau d'étude", "bureau_d__tude"),
    ]:
        match = next((p for p in pp_fixed if p["role"] == r), {})
        _set(f"pp_{rkey}_nom", match.get("nom") or "")
        _set(f"pp_{rkey}_relation", match.get("relation") or "")
        _set(f"pp_{rkey}_eval", match.get("evaluation") or 3)
    _load_list_to_state("pp2", pp_extra, PP_EXTRA_FIELDS)
    _load_list_to_state("st_", bilan["sous_traitants"], ST_FIELDS)
    _load_list_to_state("perte", bilan["postes_perte"], POSTE_FIELDS)
    _load_list_to_state("surb", bilan["postes_surbenefice"], POSTE_FIELDS)
    _load_list_to_state("trav", bilan["travaux_internes"], TRAVAIL_FIELDS)
    # marquer comme déjà prérempli pour cet ID (évite écrasement par auto-prefill)
    _set("_prefilled_for", bilan["id_chantier"])


# ══════════════════════════════════════════════════════════════════════════════
# PAGE : FORMULAIRE
# ══════════════════════════════════════════════════════════════════════════════
if page == "📝 Nouveau / Modifier bilan":

    st.title("Bilan d'expérience")

    # ── Charger un bilan existant ──────────────────────────────────────────
    bilans = db.get_all_bilans()
    col_load1, col_load2, col_load3 = st.columns([3, 2, 1])
    with col_load1:
        options = ["— Nouveau bilan —"] + [
            f"{b['id_chantier']} · {b['intitule'] or 'Sans nom'} ({b['date_bilan'] or '?'})"
            for b in bilans
        ]
        sel = st.selectbox("Charger un bilan existant :", options, key="sel_bilan")
    with col_load2:
        st.write("")
        st.write("")
        if st.button("🔄 Nouveau bilan vierge"):
            for k in list(st.session_state.keys()):
                if k.startswith(
                    ("f_", "n_", "st_", "pp_", "pp2_", "perte_", "surb_", "trav_")
                ):
                    del st.session_state[k]
            _set("loaded_bilan_id", None)
            if "_prefilled_for" in st.session_state:
                del st.session_state["_prefilled_for"]
            st.rerun()

    # Auto-load depuis bouton Modifier de l'historique
    _autoload = _get("_autoload_bilan_id")
    if _autoload and _get("loaded_bilan_id") != _autoload:
        bilan = db.load_bilan(_autoload)
        if bilan:
            _apply_bilan_to_state(bilan)
            _set("_autoload_bilan_id", None)
            st.rerun()

    if sel != "— Nouveau bilan —":
        idx = options.index(sel) - 1
        bilan_id_to_load = bilans[idx]["id"]
        if _get("loaded_bilan_id") != bilan_id_to_load:
            bilan = db.load_bilan(bilan_id_to_load)
            if bilan:
                _apply_bilan_to_state(bilan)
                st.rerun()

    loaded_id = _get("loaded_bilan_id")
    st.divider()

    # ══ SECTION 1 — Identification ════════════════════════════════════════
    st.markdown(
        '<div class="section-header">1. IDENTIFICATION</div>', unsafe_allow_html=True
    )

    col1, col2 = st.columns([2, 3])
    with col1:
        id_chantier = st.text_input(
            "ID Chantier *",
            key="f_id_chantier",
            help="Référence unique du chantier (ex: 22097)",
        )
    chantier_info = db.get_chantier(id_chantier) if id_chantier else None
    montant_facture = db.get_montant_facture(id_chantier) if id_chantier else 0.0

    if chantier_info:
        c1, c2, c3, c4 = st.columns(4)
        c1.info(f"**Chantier :** {chantier_info.get('intitule', '—')}")
        c2.info(f"**Gestionnaire :** {chantier_info.get('gestionnaire', '—')}")
        c3.info(f"**Client :** {chantier_info.get('client', '—')}")
        c4.info(f"**Secteur :** {chantier_info.get('secteur', '—')}")
    elif id_chantier:
        st.warning(
            "⚠ ID chantier non trouvé dans la base. Vérifiez ou importez les données."
        )

    # Préremplissage automatique depuis le registre chantiers + décomptes (nouveau bilan uniquement)
    # Note : pas de st.rerun() — les _set() avant le rendu des widgets suffisent
    if chantier_info and not loaded_id and _get("_prefilled_for") != id_chantier:
        _set("_prefilled_for", id_chantier)
        if chantier_info.get("delai_execution"):
            _set("f_delai_soumission", int(chantier_info["delai_execution"]))
        if chantier_info.get("montant"):
            _set("f_montant_base_pv", float(chantier_info["montant"]))
        if chantier_info.get("client"):
            _set("pp_client_nom", chantier_info["client"])
        dec = db.get_decomptes_totals(id_chantier)
        if dec["delai"]:
            _set("f_delai_complementaire", int(dec["delai"]))
        if dec["montant"]:
            _set("f_montant_decomptes_pv", float(dec["montant"]))
        for fk in ["rp_demandee", "rp_realisee", "rp_statut"]:
            if chantier_info.get(fk):
                _set(f"f_{fk}", chantier_info[fk])
        if chantier_info.get("prix_de_revient"):
            pr = float(chantier_info["prix_de_revient"])
            _set("f_prix_de_revient", pr)
            pv = float(chantier_info.get("montant") or 0)
            if pv:
                _set("f_marge_devis", round((pv - pr) / pv * 100, 2))

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        date_bilan = st.text_input(
            "Date du bilan",
            value=_get("f_date_bilan") or date.today().strftime("%d/%m/%Y"),
            key="f_date_bilan_inp",
        )
    # On stocke pour réutilisation
    _set("f_date_bilan_val", date_bilan)

    # ══ SECTION 2 — Parties prenantes ════════════════════════════════════
    st.markdown(
        '<div class="section-header">2. PARTIES PRENANTES</div>', unsafe_allow_html=True
    )

    for role_label, rkey in [
        ("Client", "client"),
        ("Architecte", "architecte"),
        ("Bureau d'étude", "bureau_d__tude"),
    ]:
        st.markdown(
            f'<div class="sub-header">{role_label}</div>', unsafe_allow_html=True
        )
        c1, c2, c3 = st.columns([3, 4, 1])
        c1.text_input("Nom", key=f"pp_{rkey}_nom")
        c2.text_input("Relation / Appréciation", key=f"pp_{rkey}_relation")
        c3.number_input(
            "Éval. /5", min_value=1, max_value=5, step=1, key=f"pp_{rkey}_eval"
        )

    n_pp2 = _get("n_pp2", 0)
    if n_pp2 > 0:
        st.markdown(
            '<div class="sub-header">Autres parties prenantes</div>',
            unsafe_allow_html=True,
        )
        for i in range(n_pp2):
            c0, c1, c2, c3, c4 = st.columns([2, 2, 4, 1, 0.5])
            c0.text_input("Rôle", key=f"pp2_{i}_role")
            c1.text_input("Nom", key=f"pp2_{i}_nom")
            c2.text_input("Relation", key=f"pp2_{i}_relation")
            c3.number_input(
                "Éval.", min_value=1, max_value=5, step=1, key=f"pp2_{i}_evaluation"
            )
            with c4:
                st.write("")
                if st.button("✕", key=f"del_pp2_{i}"):
                    _remove_item("pp2", i, PP_EXTRA_FIELDS)
                    st.rerun()

    if st.button("+ Ajouter une partie prenante"):
        _add_item("pp2", PP_EXTRA_FIELDS)
        st.rerun()

    # ══ SECTION 3 — Performance ═══════════════════════════════════════════
    st.markdown(
        '<div class="section-header">3. PERFORMANCE</div>', unsafe_allow_html=True
    )

    st.markdown('<div class="sub-header">Délais</div>', unsafe_allow_html=True)
    for _k in (
        "f_delai_soumission",
        "f_delai_contractuel",
        "f_delai_complementaire",
        "f_delai_reel",
    ):
        v = st.session_state.get(_k)
        if v is not None and not isinstance(v, int):
            try:
                st.session_state[_k] = int(float(str(v))) if str(v) else 0
            except (ValueError, TypeError):
                st.session_state[_k] = 0
    c1, c2, c3, c4, c5 = st.columns(5)
    ds = c1.number_input(
        "Délai soumission", min_value=0, step=1, key="f_delai_soumission"
    )
    dc = c2.number_input(
        "Délai contractuel", min_value=0, step=1, key="f_delai_contractuel"
    )
    dcomp = c3.number_input(
        "Délai complémentaire", min_value=0, step=1, key="f_delai_complementaire"
    )
    dr = c4.number_input("Délai réel", min_value=0, step=1, key="f_delai_reel")
    c5.selectbox("Unité", ["JC", "JO", "semaines", "mois"], key="f_unite_delai")

    respect = (dc + dcomp - dr) if (dc and dr) else None
    if respect is not None:
        col_r = st.columns(4)
        color = "green" if respect >= 0 else "red"
        emoji = "✅" if respect >= 0 else "⚠"
        col_r[0].markdown(
            f"**Respect du délai :** <span style='color:{color}'>{emoji} {respect:+d} {_get('f_unite_delai','JC')}</span>",
            unsafe_allow_html=True,
        )

    # Ordre de commencer + date fin théorique
    oc_raw = (chantier_info or {}).get("ordre_commencer") or ""
    delai_base = dc if dc > 0 else (ds if ds > 0 else None)
    unite = _get("f_unite_delai", "JC")
    if oc_raw or delai_base is not None:
        col_oc1, col_oc2 = st.columns(2)
        col_oc1.info(f"**Ordre de commencer :** {oc_raw if oc_raw else '—'}")
        if oc_raw and delai_base is not None:
            start = None
            for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"]:
                try:
                    start = datetime.strptime(oc_raw.strip(), fmt).date()
                    break
                except Exception:
                    pass
            if start:
                total = delai_base + (dcomp or 0)
                if unite == "JC":
                    end = start + timedelta(days=total)
                elif unite == "JO":
                    end = start + timedelta(days=int(total * 7 / 5))
                elif unite == "semaines":
                    end = start + timedelta(weeks=total)
                else:  # mois
                    end = start + timedelta(days=total * 30)
                col_oc2.success(
                    f"**Date fin théorique :** {end.strftime('%d/%m/%Y')}"
                    f"  —  OC {oc_raw} + {delai_base} + {dcomp or 0} {unite}"
                )

    st.markdown('<div class="sub-header">Budget</div>', unsafe_allow_html=True)
    for _k in (
        "f_montant_base_pv",
        "f_montant_decomptes_pv",
        "f_prix_de_revient",
        "f_marge_devis",
        "f_marge_finale",
    ):
        v = st.session_state.get(_k)
        if v is not None and not isinstance(v, float):
            try:
                st.session_state[_k] = float(str(v)) if str(v) else 0.0
            except (ValueError, TypeError):
                st.session_state[_k] = 0.0
    c1, c2, c3, c4 = st.columns(4)
    mb = c1.number_input(
        "Montant base PV (€ HTVA)",
        min_value=0.0,
        step=1000.0,
        format="%.2f",
        key="f_montant_base_pv",
    )
    md = c2.number_input(
        "Montant décomptes PV (€)",
        min_value=0.0,
        step=1000.0,
        format="%.2f",
        key="f_montant_decomptes_pv",
    )
    with c3:
        st.metric("Total PV", f"{mb + md:,.0f} €".replace(",", " "))
    with c4:
        st.metric(
            "Total facturé (EA)",
            f"{montant_facture:,.0f} €".replace(",", " "),
            help="Calculé automatiquement depuis les états d'avancement importés",
        )

    st.markdown(
        '<div class="sub-header">Prix de Revient (PR)</div>', unsafe_allow_html=True
    )
    pr_val = st.number_input(
        "PR Soumission (€ HTVA)",
        min_value=0.0,
        step=1000.0,
        format="%.2f",
        key="f_prix_de_revient",
    )
    pv_total = mb + md

    st.markdown('<div class="sub-header">Marges</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.number_input(
        "Marge devis (%)",
        min_value=-100.0,
        max_value=100.0,
        step=0.1,
        format="%.2f",
        key="f_marge_devis",
    )
    c2.number_input(
        "Marge finale d'exécution (%)",
        min_value=-100.0,
        max_value=100.0,
        step=0.1,
        format="%.2f",
        key="f_marge_finale",
    )

    # ══ SECTION RP/RD ════════════════════════════════════════════════════
    st.markdown(
        '<div class="section-header">RETENUES (RP)</div>', unsafe_allow_html=True
    )
    rp1, rp2, rp3 = st.columns(3)
    rp1.text_input("RP demandée", key="f_rp_demandee")
    rp2.text_input("RP réalisée", key="f_rp_realisee")
    rp3.text_input("Statut RP", key="f_rp_statut")

    # ══ SECTION 4 — Rendements ════════════════════════════════════════════
    st.markdown(
        '<div class="section-header">4. RENDEMENTS & EXÉCUTION</div>',
        unsafe_allow_html=True,
    )

    def _coerce_float(key):
        """Corrige une valeur str en session_state avant qu'un number_input la lise."""
        v = st.session_state.get(key)
        if isinstance(v, str):
            try:
                st.session_state[key] = float(v) if v else 0.0
            except (ValueError, TypeError):
                st.session_state[key] = 0.0

    def render_postes(cat, label, color):
        st.markdown(
            f'<div class="sub-header" style="color:{color}">{label}</div>',
            unsafe_allow_html=True,
        )
        n = _get(f"n_{cat}", 0)
        for i in range(n):
            _coerce_float(f"{cat}_{i}_prs")
            _coerce_float(f"{cat}_{i}_pre")
            c1, c2, c3, c4 = st.columns([4, 1.5, 1.5, 0.5])
            c1.text_input("Dénomination / poste", key=f"{cat}_{i}_denomination")
            c2.number_input(
                "PRS (€)",
                min_value=0.0,
                step=100.0,
                format="%.2f",
                key=f"{cat}_{i}_prs",
            )
            c3.number_input(
                "PRE (€)",
                min_value=0.0,
                step=100.0,
                format="%.2f",
                key=f"{cat}_{i}_pre",
            )
            prs_v = _get(f"{cat}_{i}_prs", 0) or 0
            pre_v = _get(f"{cat}_{i}_pre", 0) or 0
            ecart = pre_v - prs_v
            c4.metric("Écart", f"{ecart:+,.0f}€".replace(",", " "))
            if st.button("✕ Supprimer", key=f"del_{cat}_{i}"):
                _remove_item(cat, i, POSTE_FIELDS)
                st.rerun()
            st.divider()
        if st.button("+ Ajouter poste", key=f"add_{cat}"):
            _add_item(cat, POSTE_FIELDS, defaults={"prs": 0.0, "pre": 0.0})
            st.rerun()

    render_postes("perte", "Postes évalués trop bas — EN PERTE", "#c0392b")
    render_postes("surb", "Postes évalués trop haut — SURBÉNÉFICE", "#27ae60")

    st.markdown(
        '<div class="sub-header">Travaux réalisés en interne</div>',
        unsafe_allow_html=True,
    )
    n_trav = _get("n_trav", 0)
    total_hs = total_he = 0.0
    for i in range(n_trav):
        _coerce_float(f"trav_{i}_heures_soumission")
        _coerce_float(f"trav_{i}_heures_execution")
        c1, c2, c3, c4 = st.columns([4, 1.5, 1.5, 0.5])
        c1.text_input("Dénomination / équipe", key=f"trav_{i}_denomination")
        hs = c2.number_input(
            "H-S (budg.)", min_value=0.0, step=0.5, key=f"trav_{i}_heures_soumission"
        )
        he = c3.number_input(
            "H-E (réel)", min_value=0.0, step=0.5, key=f"trav_{i}_heures_execution"
        )
        coeff = round((hs - he) / hs, 3) if hs else None
        c4.metric("Coeff.", f"{coeff:.3f}" if coeff is not None else "—")
        total_hs += hs or 0
        total_he += he or 0
        if st.button("✕ Supprimer", key=f"del_trav_{i}"):
            _remove_item("trav", i, TRAVAIL_FIELDS)
            st.rerun()
        st.divider()

    if n_trav > 0:
        coeff_total = round((total_hs - total_he) / total_hs, 3) if total_hs else None
        c1, c2, c3 = st.columns(3)
        c1.metric("Total H-S", f"{total_hs:.1f} h")
        c2.metric("Total H-E", f"{total_he:.1f} h")
        c3.metric(
            "Coefficient global",
            f"{coeff_total:.3f}" if coeff_total is not None else "—",
        )

    if st.button("+ Ajouter travaux internes"):
        _add_item(
            "trav",
            TRAVAIL_FIELDS,
            defaults={"heures_soumission": 0.0, "heures_execution": 0.0},
        )
        st.rerun()

    # ══ SECTION 5 — Qualité ══════════════════════════════════════════════
    st.markdown('<div class="section-header">5. QUALITÉ</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    c1.text_area("Niveau de qualité global", key="f_niveau_qualite", height=80)
    c2.number_input(
        "Satisfaction client /5",
        min_value=1,
        max_value=5,
        step=1,
        key="f_satisfaction_client",
    )
    st.text_area(
        "Travaux non satisfaisants (description + responsable)",
        key="f_travaux_non_satisfaisants",
        height=80,
    )
    st.text_area("Améliorations proposées", key="f_ameliorations_qualite", height=80)

    # ══ SECTION 6 — Sécurité ════════════════════════════════════════════
    st.markdown('<div class="section-header">6. SÉCURITÉ</div>', unsafe_allow_html=True)
    accident = st.radio(
        "Accident(s) sur chantier ?", ["Non", "Oui"], horizontal=True, key="f_accidents"
    )
    if accident == "Oui":
        st.text_area(
            "Description des accidents (circonstances, propre personnel / sous-traitant)",
            key="f_desc_accidents",
            height=100,
        )
    st.text_area(
        "Améliorations / mesures préventives", key="f_ameliorations_securite", height=80
    )

    # ══ SECTION 7 — Sous-traitants ═══════════════════════════════════════
    st.markdown(
        '<div class="section-header">7. SOUS-TRAITANTS</div>', unsafe_allow_html=True
    )
    st.caption("Évaluation de 1 (très mauvais) à 5 (excellent)")
    n_st = _get("n_st_", 0)
    criteria_labels = ["Prix", "Délais", "Sécu.", "Qualité", "Réact.", "Comm."]
    criteria_keys = [
        "respect_prix",
        "respect_delais",
        "respect_securite",
        "respect_qualite",
        "reactivite",
        "communication",
    ]

    for i in range(n_st):
        st.markdown(f"**Sous-traitant {i + 1}**")
        cols = st.columns([3] + [1] * 6 + [1, 0.5])
        cols[0].text_input("Nom", key=f"st__{i}_nom")
        scores = []
        for j, (lbl, kk) in enumerate(zip(criteria_labels, criteria_keys)):
            v = cols[j + 1].number_input(
                lbl, min_value=1, max_value=5, step=1, key=f"st__{i}_{kk}"
            )
            scores.append(v)
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        cols[7].metric("Moy.", f"{avg}/5")
        with cols[8]:
            st.write("")
            if st.button("✕", key=f"del_st_{i}"):
                _remove_item("st_", i, ST_FIELDS)
                st.rerun()
        st.divider()

    if st.button("+ Ajouter un sous-traitant"):
        _add_item("st_", ST_FIELDS, defaults={k: 3 for k in criteria_keys})
        st.rerun()

    st.text_area("Notes complémentaires sous-traitants", key="f_notes_st", height=60)

    # ══ SECTION 8 — Commentaire général ══════════════════════════════════
    st.markdown(
        '<div class="section-header">8. COMMENTAIRE GÉNÉRAL / SYNTHÈSE</div>',
        unsafe_allow_html=True,
    )
    st.text_area(
        "Points forts, points faibles, enseignements pour l'avenir",
        key="f_commentaire_general",
        height=150,
    )

    # ══ ACTIONS : Enregistrer / PDF ═══════════════════════════════════════
    st.divider()
    col_save1, col_save2, col_save3, col_del = st.columns([2, 2, 2, 1])

    def _build_data():
        pp_fixed = []
        for role_label, rkey in [
            ("Client", "client"),
            ("Architecte", "architecte"),
            ("Bureau d'étude", "bureau_d__tude"),
        ]:
            pp_fixed.append(
                {
                    "role": role_label,
                    "nom": _get(f"pp_{rkey}_nom") or "",
                    "relation": _get(f"pp_{rkey}_relation") or "",
                    "evaluation": _get(f"pp_{rkey}_eval") or 3,
                }
            )
        pp_extra = _collect_list("pp2", _get("n_pp2", 0), PP_EXTRA_FIELDS)

        return {
            "id": loaded_id,
            "id_chantier": _get("f_id_chantier", ""),
            "date_bilan": _get("f_date_bilan_val") or date.today().strftime("%d/%m/%Y"),
            "delai_soumission": _get("f_delai_soumission") or None,
            "delai_contractuel": _get("f_delai_contractuel") or None,
            "delai_complementaire": _get("f_delai_complementaire") or None,
            "delai_reel": _get("f_delai_reel") or None,
            "unite_delai": _get("f_unite_delai") or "JC",
            "montant_base_pv": _get("f_montant_base_pv") or None,
            "montant_decomptes_pv": _get("f_montant_decomptes_pv") or None,
            "marge_devis": _get("f_marge_devis") or None,
            "marge_finale": _get("f_marge_finale") or None,
            "niveau_qualite": _get("f_niveau_qualite") or None,
            "satisfaction_client": _get("f_satisfaction_client") or None,
            "travaux_non_satisfaisants": _get("f_travaux_non_satisfaisants") or None,
            "ameliorations_qualite": _get("f_ameliorations_qualite") or None,
            "accidents_chantier": _get("f_accidents") or "Non",
            "description_accidents": _get("f_desc_accidents") or None,
            "ameliorations_securite": _get("f_ameliorations_securite") or None,
            "commentaire_general": _get("f_commentaire_general") or None,
            "notes_sous_traitants": _get("f_notes_st") or None,
            "rp_demandee": _get("f_rp_demandee") or None,
            "rp_realisee": _get("f_rp_realisee") or None,
            "rp_statut": _get("f_rp_statut") or None,
            "prix_de_revient": _get("f_prix_de_revient") or None,
            "parties_prenantes": pp_fixed + pp_extra,
            "sous_traitants": _collect_list("st_", _get("n_st_", 0), ST_FIELDS),
            "postes_perte": _collect_list("perte", _get("n_perte", 0), POSTE_FIELDS),
            "postes_surbenefice": _collect_list(
                "surb", _get("n_surb", 0), POSTE_FIELDS
            ),
            "travaux_internes": _collect_list(
                "trav", _get("n_trav", 0), TRAVAIL_FIELDS
            ),
        }

    with col_save1:
        if st.button("💾 Enregistrer", type="primary", use_container_width=True):
            if not _get("f_id_chantier"):
                st.error("ID Chantier obligatoire.")
            else:
                data = _build_data()
                new_id = db.save_bilan(data)
                _set("loaded_bilan_id", new_id)
                st.success(f"✅ Bilan enregistré (ID bilan: {new_id})")
                st.rerun()

    with col_save2:
        if st.button("📄 Générer PDF", use_container_width=True):
            if not _get("f_id_chantier"):
                st.error("ID Chantier obligatoire.")
            else:
                data = _build_data()
                ch = chantier_info or {
                    "intitule": "",
                    "gestionnaire": "",
                    "client": "",
                    "secteur": "",
                    "province": "",
                }
                pdf_bytes = pdf_export.generate_pdf(data, ch, montant_facture)
                id_c = _get("f_id_chantier", "chantier")
                fname = f"Bilan_{id_c}_{date.today().strftime('%Y%m%d')}.pdf"
                st.download_button(
                    "⬇ Télécharger le PDF",
                    data=pdf_bytes,
                    file_name=fname,
                    mime="application/pdf",
                    use_container_width=True,
                )

    with col_save3:
        if st.button("💾 + 📄 Enregistrer & PDF", use_container_width=True):
            if not _get("f_id_chantier"):
                st.error("ID Chantier obligatoire.")
            else:
                data = _build_data()
                new_id = db.save_bilan(data)
                _set("loaded_bilan_id", new_id)
                ch = chantier_info or {
                    "intitule": "",
                    "gestionnaire": "",
                    "client": "",
                    "secteur": "",
                    "province": "",
                }
                pdf_bytes = pdf_export.generate_pdf(data, ch, montant_facture)
                id_c = _get("f_id_chantier", "chantier")
                fname = f"Bilan_{id_c}_{date.today().strftime('%Y%m%d')}.pdf"
                st.download_button(
                    "⬇ Télécharger le PDF",
                    data=pdf_bytes,
                    file_name=fname,
                    mime="application/pdf",
                    use_container_width=True,
                )

    with col_del:
        if loaded_id and st.button("🗑 Supprimer", use_container_width=True):
            db.delete_bilan(loaded_id)
            _set("loaded_bilan_id", None)
            st.success("Bilan supprimé.")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE : HISTORIQUE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Historique bilans":
    st.title("Historique des bilans")

    bilans = db.get_all_bilans()
    if not bilans:
        st.info("Aucun bilan enregistré. Utilisez le formulaire pour créer le premier.")
    else:
        chantiers = db.get_all_chantiers()
        gestionnaires = ["Tous"] + sorted(
            {b.get("gestionnaire") or "?" for b in bilans if b.get("gestionnaire")}
        )

        col_f1, col_f2, col_f3 = st.columns(3)
        search = col_f1.text_input("🔍 Recherche (ID, nom, client)", "")
        gest_filter = col_f2.selectbox("Gestionnaire", gestionnaires)
        sort_by = col_f3.selectbox(
            "Trier par", ["Date (récent)", "ID chantier", "Client"]
        )

        rows = bilans
        if search:
            s = search.lower()
            rows = [
                b
                for b in rows
                if s in str(b.get("id_chantier") or "").lower()
                or s in (b.get("intitule") or "").lower()
                or s in (b.get("client") or "").lower()
            ]
        if gest_filter != "Tous":
            rows = [b for b in rows if b.get("gestionnaire") == gest_filter]

        if sort_by == "ID chantier":
            rows.sort(key=lambda b: int(b.get("id_chantier") or 0), reverse=True)
        elif sort_by == "Client":
            rows.sort(key=lambda b: (b.get("client") or "").lower())

        st.caption(f"{len(rows)} bilan(s) trouvé(s)")
        df = pd.DataFrame(
            [
                {
                    "ID Chantier": b.get("id_chantier"),
                    "Nom chantier": b.get("intitule") or "—",
                    "Gestionnaire": b.get("gestionnaire") or "—",
                    "Client": b.get("client") or "—",
                    "Date bilan": b.get("date_bilan") or "—",
                    "Marge finale (%)": b.get("marge_finale"),
                    "Satisfaction /5": b.get("satisfaction_client"),
                }
                for b in rows
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Actions")
        labels = [
            f"{b['id_chantier']} — {b.get('intitule') or 'Sans nom'} ({b.get('date_bilan') or '?'})"
            for b in rows
        ]
        sel_id = st.selectbox("Sélectionner un bilan :", ["—"] + labels, key="hist_sel")

        if sel_id != "—":
            idx = labels.index(sel_id)
            target_id = rows[idx]["id"]

            col_mod, col_del = st.columns(2)
            with col_mod:
                if st.button("📝 Modifier", use_container_width=True, type="primary"):
                    _set("_autoload_bilan_id", target_id)
                    st.session_state["nav_page"] = 0
                    st.rerun()
            with col_del:
                if st.button("🗑 Supprimer", use_container_width=True):
                    _set("_confirm_delete_id", target_id)

            if _get("_confirm_delete_id") == target_id:
                st.warning(
                    f"⚠ Supprimer définitivement le bilan **{sel_id}** ? Cette action est irréversible."
                )
                cc1, cc2 = st.columns(2)
                if cc1.button("✅ Confirmer la suppression", use_container_width=True):
                    db.delete_bilan(target_id)
                    _set("_confirm_delete_id", None)
                    st.success("Bilan supprimé.")
                    st.rerun()
                if cc2.button("❌ Annuler", use_container_width=True):
                    _set("_confirm_delete_id", None)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE : DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Dashboard":
    st.title("Dashboard — Vue d'ensemble")

    bilans = db.get_all_bilans()
    if not bilans:
        st.info("Aucune donnée disponible.")
    else:
        df = pd.DataFrame(bilans)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total bilans", len(bilans))
        avg_sat = df["satisfaction_client"].dropna().mean()
        c2.metric(
            "Satisfaction client moy.",
            f"{avg_sat:.1f}/5" if not pd.isna(avg_sat) else "—",
        )
        avg_marge = df["marge_finale"].dropna().mean()
        c3.metric(
            "Marge finale moy.", f"{avg_marge:.1f}%" if not pd.isna(avg_marge) else "—"
        )
        accidents = (
            df[df.get("accidents_chantier") is not None].shape[0]
            if "accidents_chantier" in df
            else 0
        )
        c4.metric(
            "Chantiers / bilans", f"{len(db.get_all_chantiers())} / {len(bilans)}"
        )

        st.divider()
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.subheader("Satisfaction client par bilan")
            sat_df = df[df["satisfaction_client"].notna()][
                ["id_chantier", "satisfaction_client"]
            ]
            if not sat_df.empty:
                st.bar_chart(sat_df.set_index("id_chantier")["satisfaction_client"])

        with col_g2:
            st.subheader("Marge finale par bilan")
            mg_df = df[df["marge_finale"].notna()][["id_chantier", "marge_finale"]]
            if not mg_df.empty:
                st.bar_chart(mg_df.set_index("id_chantier")["marge_finale"])

        st.divider()
        st.subheader("Tous les bilans")
        st.dataframe(
            df[
                [
                    "id_chantier",
                    "intitule",
                    "gestionnaire",
                    "client",
                    "date_bilan",
                    "marge_finale",
                    "satisfaction_client",
                ]
            ].rename(
                columns={
                    "id_chantier": "ID",
                    "intitule": "Chantier",
                    "gestionnaire": "Gest.",
                    "client": "Client",
                    "date_bilan": "Date",
                    "marge_finale": "Marge %",
                    "satisfaction_client": "Satis.",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader("Registre chantiers")
        chantiers = db.get_all_chantiers()
        if chantiers:
            st.dataframe(
                pd.DataFrame(chantiers), use_container_width=True, hide_index=True
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE : IMPORT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⬆ Importer données Excel":
    st.title("Import des données Excel")

    # ── État actuel ────────────────────────────────────────────────────────
    ch_count = len(db.get_all_chantiers())
    bl_count = len(db.get_all_bilans())
    m1, m2 = st.columns(2)
    m1.metric("Chantiers en base", ch_count)
    m2.metric("Bilans en base", bl_count)
    st.divider()

    # ══ BLOC 1 : Registre chantiers ════════════════════════════════════════
    st.subheader("1. Registre des chantiers (Suivi RP & RD)")
    st.caption(
        "Fichier contenant la liste de vos chantiers avec ID, gestionnaire, client, montants..."
    )

    file_ch = st.file_uploader(
        "Choisir le fichier Excel chantiers",
        type=["xlsx", "xlsm", "xls"],
        key="upload_chantiers",
    )

    if file_ch:
        try:
            sheet_names_ch = imp.get_sheet_names(file_ch)
            file_ch.seek(0)
        except Exception as e:
            st.error(f"Impossible de lire le fichier : {e}")
            sheet_names_ch = []

        if sheet_names_ch:
            col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
            sheet_ch = col_s1.selectbox(
                "Feuille contenant les chantiers", sheet_names_ch, key="sheet_ch"
            )
            header_row_ch = col_s2.number_input(
                "Ligne d'en-têtes",
                min_value=1,
                max_value=10,
                value=1,
                key="header_row_ch",
            )
            first_data_ch = col_s3.number_input(
                "Première ligne de données",
                min_value=2,
                max_value=20,
                value=2,
                key="first_data_ch",
            )

            # Aperçu
            try:
                file_ch.seek(0)
                preview = imp.get_sheet_preview(
                    file_ch, sheet_ch, max_rows=int(header_row_ch) + 3
                )
                if preview:
                    st.caption("Aperçu (3 premières lignes de données) :")
                    headers = [
                        str(c) if c is not None else ""
                        for c in preview[int(header_row_ch) - 1]
                    ]
                    data_rows = preview[int(header_row_ch) :]
                    if data_rows:
                        _df_prev = pd.DataFrame(
                            data_rows, columns=headers if headers else None
                        )
                        st.dataframe(
                            _df_prev.head(3), use_container_width=True, hide_index=True
                        )
            except Exception as ex:
                st.warning(f"Aperçu indisponible : {ex}")

            overwrite_ch = st.checkbox(
                "Écraser les chantiers existants (même ID)", key="overwrite_ch"
            )

            if st.button(
                "▶ Importer les chantiers", type="primary", key="btn_import_ch"
            ):
                with st.spinner("Import en cours..."):
                    try:
                        file_ch.seek(0)
                        conn = db.get_conn()
                        ok, skip, detected = imp.import_chantiers(
                            file_ch,
                            sheet_ch,
                            conn,
                            header_row=int(header_row_ch),
                            first_data_row=int(first_data_ch),
                            overwrite=overwrite_ch,
                        )
                        conn.close()
                        st.success(
                            f"✅ {ok} chantier(s) importé(s), {skip} ignoré(s) (déjà présents)."
                        )
                        # Show detected columns
                        det_info = {k: v for k, v in detected.items() if v is not None}
                        if det_info:
                            st.caption(f"Colonnes détectées : {det_info}")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erreur import : {ex}")

    st.divider()

    # ══ BLOC 2 : États d'avancement ════════════════════════════════════════
    st.subheader("2. États d'avancement / Facturation (INPUT - EA)")
    st.caption(
        "Fichier contenant les montants facturés par chantier — utilisé pour le calcul automatique du total facturé."
    )

    file_ea = st.file_uploader(
        "Choisir le fichier Excel états d'avancement",
        type=["xlsx", "xlsm", "xls"],
        key="upload_ea",
    )

    if file_ea:
        try:
            sheet_names_ea = imp.get_sheet_names(file_ea)
            file_ea.seek(0)
        except Exception as e:
            st.error(f"Impossible de lire le fichier : {e}")
            sheet_names_ea = []

        if sheet_names_ea:
            col_e1, col_e2, col_e3 = st.columns([2, 1, 1])
            sheet_ea = col_e1.selectbox(
                "Feuille contenant les EA", sheet_names_ea, key="sheet_ea"
            )
            header_row_ea = col_e2.number_input(
                "Ligne d'en-têtes",
                min_value=1,
                max_value=10,
                value=1,
                key="header_row_ea",
            )
            first_data_ea = col_e3.number_input(
                "Première ligne de données",
                min_value=2,
                max_value=20,
                value=2,
                key="first_data_ea",
            )

            # Aperçu + sélection colonnes clés
            try:
                file_ea.seek(0)
                preview_ea = imp.get_sheet_preview(
                    file_ea, sheet_ea, max_rows=int(header_row_ea) + 3
                )
                if preview_ea:
                    headers_ea = [
                        str(c) if c is not None else f"Col {i}"
                        for i, c in enumerate(preview_ea[int(header_row_ea) - 1])
                    ]
                    st.caption("Aperçu :")
                    data_rows_ea = preview_ea[int(header_row_ea) :]
                    if data_rows_ea:
                        _df_ea = pd.DataFrame(data_rows_ea, columns=headers_ea)
                        st.dataframe(
                            _df_ea.head(3), use_container_width=True, hide_index=True
                        )

                    st.caption(
                        "Sélectionner manuellement les colonnes clés (si la détection auto échoue) :"
                    )
                    col_m1, col_m2 = st.columns(2)
                    col_id_sel = col_m1.selectbox(
                        "Colonne : Numéro de chantier",
                        ["Auto-détection"] + headers_ea,
                        key="ea_col_id",
                    )
                    col_mt_sel = col_m2.selectbox(
                        "Colonne : Montant facturé",
                        ["Auto-détection"] + headers_ea,
                        key="ea_col_montant",
                    )
                    col_id_idx = (
                        headers_ea.index(col_id_sel)
                        if col_id_sel != "Auto-détection"
                        else None
                    )
                    col_mt_idx = (
                        headers_ea.index(col_mt_sel)
                        if col_mt_sel != "Auto-détection"
                        else None
                    )
            except Exception as ex:
                st.warning(f"Aperçu indisponible : {ex}")
                col_id_idx = col_mt_idx = None

            overwrite_ea = st.checkbox(
                "Vider et réimporter tous les EA (recommandé pour mise à jour)",
                key="overwrite_ea",
                value=True,
            )

            if st.button("▶ Importer les EA", type="primary", key="btn_import_ea"):
                with st.spinner("Import en cours..."):
                    try:
                        file_ea.seek(0)
                        conn = db.get_conn()
                        ok_ea, det_ea = imp.import_ea(
                            file_ea,
                            sheet_ea,
                            conn,
                            header_row=int(header_row_ea),
                            first_data_row=int(first_data_ea),
                            col_id=col_id_idx,
                            col_montant=col_mt_idx,
                            overwrite=overwrite_ea,
                        )
                        conn.close()
                        st.success(f"✅ {ok_ea} ligne(s) EA importée(s).")
                        st.caption(
                            f"Colonnes utilisées : ID chantier = col {det_ea['col_id']}, "
                            f"Montant = col {det_ea['col_montant']}"
                        )
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erreur import : {ex}")

    st.divider()

    # ══ BLOC 3 : Décomptes ═════════════════════════════════════════════════════
    st.subheader("3. Décomptes (délai complémentaire & montant par chantier)")
    st.caption(
        "Fichier listant les décomptes par chantier — utilisé pour préremplir le délai complémentaire et le montant des décomptes dans le formulaire."
    )

    from database import get_conn as _get_conn

    dec_count = _get_conn().execute("SELECT COUNT(*) FROM decomptes").fetchone()[0]
    st.metric("Lignes décomptes en base", dec_count)

    file_dec = st.file_uploader(
        "Choisir le fichier Excel décomptes",
        type=["xlsx", "xlsm", "xls"],
        key="upload_dec",
    )

    if file_dec:
        try:
            sheet_names_dec = imp.get_sheet_names(file_dec)
            file_dec.seek(0)
        except Exception as e:
            st.error(f"Impossible de lire le fichier : {e}")
            sheet_names_dec = []

        if sheet_names_dec:
            col_d1, col_d2, col_d3 = st.columns([2, 1, 1])
            sheet_dec = col_d1.selectbox(
                "Feuille contenant les décomptes", sheet_names_dec, key="sheet_dec"
            )
            header_row_dec = col_d2.number_input(
                "Ligne d'en-têtes",
                min_value=1,
                max_value=10,
                value=1,
                key="header_row_dec",
            )
            first_data_dec = col_d3.number_input(
                "Première ligne de données",
                min_value=2,
                max_value=20,
                value=2,
                key="first_data_dec",
            )

            # Valeurs par défaut (détection auto à l'import)
            dec_col_id = dec_col_mt = dec_col_dl = dec_col_ap = None
            headers_dec = []

            try:
                file_dec.seek(0)
                preview_dec = imp.get_sheet_preview(
                    file_dec, sheet_dec, max_rows=int(header_row_dec) + 3
                )
                if preview_dec:
                    headers_dec = [
                        str(c) if c is not None else f"Col {i}"
                        for i, c in enumerate(preview_dec[int(header_row_dec) - 1])
                    ]
                    st.caption("Aperçu :")
                    data_rows_dec = preview_dec[int(header_row_dec) :]
                    if data_rows_dec:
                        st.dataframe(
                            pd.DataFrame(data_rows_dec, columns=headers_dec).head(3),
                            use_container_width=True,
                            hide_index=True,
                        )
            except Exception as ex:
                st.warning(f"Aperçu indisponible : {ex}")

            if headers_dec:
                st.caption(
                    "Sélection manuelle des colonnes clés (laisser Auto-détection si possible) :"
                )
                cm1, cm2, cm3, cm4 = st.columns(4)
                sel_dec_id = cm1.selectbox(
                    "Colonne : ID chantier",
                    ["Auto-détection"] + headers_dec,
                    key="dec_col_id",
                )
                sel_dec_mt = cm2.selectbox(
                    "Colonne : Montant décompte",
                    ["Auto-détection"] + headers_dec,
                    key="dec_col_mt",
                )
                sel_dec_dl = cm3.selectbox(
                    "Colonne : Délai complémentaire",
                    ["Auto-détection"] + headers_dec,
                    key="dec_col_dl",
                )
                sel_dec_ap = cm4.selectbox(
                    "Colonne : Approuvé (0/1)",
                    ["Auto-détection"] + headers_dec,
                    key="dec_col_ap",
                )

                dec_col_id = (
                    headers_dec.index(sel_dec_id)
                    if sel_dec_id != "Auto-détection"
                    else None
                )
                dec_col_mt = (
                    headers_dec.index(sel_dec_mt)
                    if sel_dec_mt != "Auto-détection"
                    else None
                )
                dec_col_dl = (
                    headers_dec.index(sel_dec_dl)
                    if sel_dec_dl != "Auto-détection"
                    else None
                )
                dec_col_ap = (
                    headers_dec.index(sel_dec_ap)
                    if sel_dec_ap != "Auto-détection"
                    else None
                )

            overwrite_dec = st.checkbox(
                "Vider et réimporter tous les décomptes",
                key="overwrite_dec",
                value=True,
            )

            if st.button(
                "▶ Importer les décomptes", type="primary", key="btn_import_dec"
            ):
                with st.spinner("Import en cours..."):
                    try:
                        file_dec.seek(0)
                        conn = db.get_conn()
                        ok_dec, det_dec = imp.import_decomptes(
                            file_dec,
                            sheet_dec,
                            conn,
                            header_row=int(header_row_dec),
                            first_data_row=int(first_data_dec),
                            col_id=dec_col_id,
                            col_montant=dec_col_mt,
                            col_delai=dec_col_dl,
                            col_accepte=dec_col_ap,
                            overwrite=overwrite_dec,
                        )
                        conn.close()
                        # Compter approuvés vs total
                        import sqlite3 as _sq

                        _c = _sq.connect(db.DB_PATH)
                        _tot = _c.execute("SELECT COUNT(*) FROM decomptes").fetchone()[
                            0
                        ]
                        _app = _c.execute(
                            "SELECT COUNT(*) FROM decomptes WHERE statut_accepte=1"
                        ).fetchone()[0]
                        _c.close()
                        st.success(
                            f"✅ {ok_dec} ligne(s) importée(s) — {_app} approuvées / {_tot} total."
                        )
                        if det_dec.get("col_accepte") is None:
                            st.warning(
                                "⚠ Colonne 'Approuvé' non détectée automatiquement. Sélectionnez-la manuellement."
                            )
                        st.caption(f"Colonnes utilisées : {det_dec}")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erreur import : {ex}")
