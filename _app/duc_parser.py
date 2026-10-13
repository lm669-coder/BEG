"""Lecture de la DUC (« Déclaration de travaux », PDF) d'un chantier.

Extrait le maître d'oeuvre (conception / contrôle d'exécution), les
coordinateurs sécurité et les sous-traitants déclarés.
Les DUC sont rangées dans `<dossier chantier>/DUC/*.pdf` sur SharePoint
(synchronisé localement par OneDrive).
"""

import glob
import os
import re
from pathlib import Path

# Racines SharePoint synchronisées : (dossier racine, dossier « affaires en cours »)
_SP_ROOT = Path.home() / "MIGNONE S.A" / "SP - Documents"
_AFFAIRES = {
    "bat": [("02. Batiment", "21. Affaires en cours BAT")],
    "elec": [("01. Electricité", "11. Affaires en cours")],
}

_SOCIETE = "M.I.G.N.O.N.E"

_H_CONCEPTION = "Maître d'oeuvre chargé de la conception"
_H_CONTROLE = "Maître d'oeuvre chargé du contrôle de l'exécution"
_H_COORD_ELAB = "Coordinateur en matière de sécurité et de santé pendant l'élaboration"
_H_COORD_REAL = "Coordinateur en matière de sécurité et de santé pendant la réalisation"
_H_DONNEUR = "Donneur d'ordre"
_H_DECLARANT = "Déclarant"
_H_CONTRAT = "Contrat"
_H_ST = "Informations sur les sous-traitants"
_HEADINGS = (
    _H_CONCEPTION,
    _H_CONTROLE,
    _H_COORD_ELAB,
    _H_COORD_REAL,
    _H_DONNEUR,
    _H_DECLARANT,
    _H_CONTRAT,
    _H_ST,
)

# Agences d'intérim : décochées par défaut dans la liste des sous-traitants.
_INTERIM = (
    "interim",
    "intérim",
    "jobs",
    "synergie",
    "asap",
    "accent",
    "randstad",
    "adecco",
    "manpower",
    "daoust",
    "start people",
    "t-groep",
)


def est_interim(nom: str) -> bool:
    n = nom.lower()
    return any(k in n for k in _INTERIM)


# ── Localisation du PDF ───────────────────────────────────────────────────
def find_duc(id_chantier: str, departement: str | None = None) -> str | None:
    """Chemin du PDF DUC (version FR) du chantier, ou None."""
    m = re.match(r"\s*(\d+)", id_chantier or "")
    if not m:
        return None
    num = m.group(1)
    d = (departement or "").strip().lower()
    cles = [d] if d in _AFFAIRES else list(_AFFAIRES)
    candidats: list[str] = []
    for cle in cles:
        for dept_dir, affaires_dir in _AFFAIRES[cle]:
            base = _SP_ROOT / dept_dir / affaires_dir
            for dossier in glob.glob(glob.escape(str(base)) + os.sep + num + "*"):
                candidats += glob.glob(os.path.join(dossier, "DUC", "*.pdf"))
    candidats = [c for c in candidats if "_EN_" not in os.path.basename(c)]
    if not candidats:
        return None
    # Préfère les PDF « _FR », puis le plus récent
    candidats.sort(
        key=lambda p: ("_FR" in os.path.basename(p), os.path.getmtime(p)), reverse=True
    )
    return candidats[0]


# ── Analyse du texte ──────────────────────────────────────────────────────
def _read_text(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    txt = "\n".join(p.extract_text(extraction_mode="layout") or "" for p in reader.pages)
    return re.sub(r"\n\s*\n+", "\n", txt)


def _field(line: str) -> tuple[str, str] | None:
    m = re.match(r"^\s*([^:]{2,40}):\s*(.*)$", line)
    if not m:
        return None
    return m.group(1).strip(), re.split(r"\s{3,}", m.group(2).strip())[0].strip()


def _denomination(fields: dict) -> str:
    """Dénomination d'un bloc ; corrige l'inversion « Rue »/« Dénomination »
    présente dans certaines DUC (la dénomination contient alors « Boîte: »)."""
    den = fields.get("Dénomination", "")
    rue = fields.get("Rue et n°", "")
    if "Boîte" in fields.get("_den_raw", "") and rue and "Boîte" not in rue:
        return rue
    return den


def _parse_block(lines: list[str]) -> dict:
    out: dict = {}
    parent = False
    for ln in lines:
        if ln.strip().startswith("Agissant en sous-traitance de"):
            parent = True
            continue
        f = _field(ln)
        if not f:
            continue
        k, v = f
        if k == "Dénomination":
            if parent:
                out["pour"] = v
            elif "Dénomination" not in out:
                out["Dénomination"] = v
                out["_den_raw"] = ln
        elif k not in out:
            out[k] = v
    return out


def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for ln in text.splitlines():
        s = ln.strip()
        head = next((h for h in _HEADINGS if s.startswith(h) and s.endswith(":")), None)
        if head:
            current = head
            sections[current] = []
        elif current:
            sections[current].append(ln)
    return sections


def _split_sous_traitants(lines: list[str]) -> list[dict]:
    blocs: list[list[str]] = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("N° BCE:") or s.startswith("N° TVA intracom"):
            blocs.append([])
        if blocs:
            blocs[-1].append(ln)
    result = []
    for b in blocs:
        d = _parse_block(b)
        nom = d.get("Dénomination", "").strip()
        if not nom:
            continue
        result.append(
            {
                "nom": nom,
                "bce": d.get("N° BCE") or d.get("N° TVA intracom", ""),
                "pour": d.get("pour", ""),
                "direct": _SOCIETE in d.get("pour", "").upper().replace(" ", ""),
                "interim": est_interim(nom),
            }
        )
    return result


def parse_duc(path: str) -> dict:
    """Retourne {chantier, donneur_ordre, mo_conception, mo_controle,
    coord_elaboration, coord_realisation, sous_traitants[]}."""
    text = _read_text(path)
    sec = _split_sections(text)

    def nom(h: str) -> str:
        d = _parse_block(sec.get(h, []))
        return _denomination(d).strip()

    m = re.search(r"Nom des travaux:\s+(.+)", text)
    return {
        "fichier": path,
        "chantier": m.group(1).strip() if m else "",
        "donneur_ordre": nom(_H_DONNEUR),
        "mo_conception": nom(_H_CONCEPTION),
        "mo_controle": nom(_H_CONTROLE),
        "coord_elaboration": nom(_H_COORD_ELAB),
        "coord_realisation": nom(_H_COORD_REAL),
        "sous_traitants": _split_sous_traitants(sec.get(_H_ST, [])),
    }
