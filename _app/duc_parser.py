"""Lecture de la DUC (« Déclaration de travaux », PDF) d'un chantier.

Extrait le maître d'oeuvre (conception / contrôle d'exécution), les
coordinateurs sécurité et les sous-traitants déclarés.
Les DUC sont rangées dans `<dossier chantier>/DUC/*.pdf` sur SharePoint
(synchronisé localement par OneDrive).
"""

import glob
import os
import re

import chantier_dirs

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
_RE_ANGLAIS = re.compile(r"(^|[_\- ])EN([_. ]|$)", re.IGNORECASE)


def find_duc_all(id_chantier: str, departement: str | None = None) -> list[str]:
    """PDF candidats du dossier DUC du chantier (hors versions anglaises),
    versions « _FR » d'abord, puis les plus récents."""
    # Dossiers du chantier (en cours sur SharePoint, sinon archives S:) : voir chantier_dirs
    candidats: list[str] = []
    for dossier in chantier_dirs.find_chantier_dirs(id_chantier, departement):
        candidats += glob.glob(os.path.join(glob.escape(dossier), "DUC", "*.pdf"))
    candidats = [c for c in candidats if not _RE_ANGLAIS.search(os.path.splitext(os.path.basename(c))[0])]
    candidats.sort(
        key=lambda p: ("_FR" in os.path.basename(p), os.path.getmtime(p)), reverse=True
    )
    return candidats


def find_duc(id_chantier: str, departement: str | None = None) -> str | None:
    """Premier PDF candidat (voir find_duc_all) ou None."""
    c = find_duc_all(id_chantier, departement)
    return c[0] if c else None


def _score(duc: dict) -> int:
    return (
        10 * len(duc["sous_traitants"])
        + (3 if duc["mo_conception"] or duc["mo_controle"] else 0)
        + (1 if duc["coord_realisation"] or duc["coord_elaboration"] else 0)
    )


def parse_best(candidats: list[str]) -> tuple[dict | None, str]:
    """Lit chaque PDF candidat et garde le plus complet (les dossiers DUC mêlent
    déclaration complète, résumés Constructiv d'une page, scans...).
    Retourne (résultat | None, message d'état si rien d'exploitable)."""
    best, best_score, vides, erreurs = None, 0, 0, 0
    for path in candidats:
        try:
            duc = parse_duc(path)
        except Exception:
            erreurs += 1
            continue
        if duc["caracteres"] < 50:
            vides += 1
            continue
        sc = _score(duc)
        if sc > best_score:
            best, best_score = duc, sc
    if best:
        return best, ""
    if vides:
        return None, "DUC scannée (image sans texte) : lecture automatique impossible."
    if erreurs:
        return None, "DUC illisible (PDF protégé ou endommagé)."
    return None, "Aucune information exploitable dans les PDF du dossier DUC."


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
    val = re.split(r"\s{3,}", m.group(2).strip())[0].strip()
    # Un « libellé: » (ex. « Boîte: ») n'est pas une valeur : champ vide dans le PDF
    return m.group(1).strip(), "" if val.endswith(":") else val


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
        "caracteres": len(text.strip()),
        "chantier": m.group(1).strip() if m else "",
        "donneur_ordre": nom(_H_DONNEUR),
        "mo_conception": nom(_H_CONCEPTION),
        "mo_controle": nom(_H_CONTROLE),
        "coord_elaboration": nom(_H_COORD_ELAB),
        "coord_realisation": nom(_H_COORD_REAL),
        "sous_traitants": _split_sous_traitants(sec.get(_H_ST, [])),
    }


# ── Interprétation : Client / Architecte ──────────────────────────────────
_STOP = {
    "ville", "commune", "adm", "administration", "communale", "communal", "cpas",
    "de", "du", "des", "la", "le", "les", "l", "d", "et", "en", "sa", "sprl", "srl",
    "asbl", "scrl", "ac", "of",
}


def _tokens(nom: str) -> set[str]:
    import unicodedata

    n = unicodedata.normalize("NFD", nom or "")
    n = "".join(c for c in n if unicodedata.category(c) != "Mn").lower()
    return {t for t in re.split(r"[^a-z0-9]+", n) if t and t not in _STOP}


def meme_entite(a: str, b: str) -> bool:
    """« adm Enghien » et « Ville d'Enghien » désignent la même entité."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return ta == tb or ta <= tb or tb <= ta


def est_mignone(nom: str) -> bool:
    return "mignone" in re.sub(r"[^a-z]", "", (nom or "").lower())


def interpreter(duc: dict, client_actuel: str = "") -> dict:
    """Répartit les intervenants de la DUC.

    - client      : le donneur d'ordre (maître d'ouvrage) remplace le client existant ;
    - architecte  : maître d'oeuvre conception / contrôle d'exécution, SEULEMENT s'il
                    est distinct du client (souvent le maître d'oeuvre est le maître
                    d'ouvrage lui-même : ce n'est alors pas un architecte) ;
    - coordinateur: coordinateur sécurité.
    """
    donneur = duc.get("donneur_ordre", "")
    client = "" if est_mignone(donneur) else donneur
    ref = client or client_actuel
    distincts: list[str] = []
    for nom in (duc.get("mo_conception", ""), duc.get("mo_controle", "")):
        if (
            nom
            and not est_mignone(nom)
            and not (ref and meme_entite(nom, ref))
            and not any(meme_entite(nom, d) for d in distincts)
        ):
            distincts.append(nom)
    archi = ""
    if distincts:
        archi = distincts[0]
        if len(distincts) > 1:
            archi = f"{distincts[0]} / {distincts[1]} (contrôle)"
    note = ""
    if not archi:
        mos = [n for n in (duc.get("mo_conception", ""), duc.get("mo_controle", "")) if n]
        if any(est_mignone(n) for n in mos):
            note = "le maître d'oeuvre déclaré est Mignone (ignoré)"
        elif mos:
            note = "le maître d'oeuvre est le client lui-même"
        else:
            note = "maître d'oeuvre non renseigné dans la DUC"
    return {
        "client": client,
        "architecte": archi,
        "note_architecte": note,
        "coordinateur": duc.get("coord_realisation") or duc.get("coord_elaboration") or "",
    }
