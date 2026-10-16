"""Localisation du dossier d'un chantier (en cours sur SharePoint, clos sur S:).

Racines (beg_config.ini, valeurs par défaut ci-dessous) :
  bat_en_cours / elec_en_cours : dossiers SharePoint synchronisés (OneDrive)
  bat_archives / elec_archives : archives sur le partage réseau S:
Un dossier chantier est retrouvé par son numéro (« 22081 Saint-Ghislain »,
« 08005 - Nom ») ; le département est indispensable car certains numéros existent
en BAT et en ELEC. Structure créée pour le bilan d'expérience :

  <chantier>\\Satisfaction & Expérience\\Photos
  <chantier>\\Satisfaction & Expérience\\Bilan d'expérience
"""

import os
import re
import time
from pathlib import Path
from typing import NamedTuple

import paths

SE_DIR = "Satisfaction & Expérience"
PHOTOS_SUB = "Photos"
BILANS_SUB = "Bilan d'expérience"

_SP = Path.home() / "MIGNONE S.A" / "SP - Documents"
_UNC = r"\\192.168.1.220\datas\Technique"
_DEFAULTS = {
    "bat_en_cours": str(_SP / "02. Batiment" / "21. Affaires en cours BAT"),
    "elec_en_cours": str(_SP / "01. Electricité" / "11. Affaires en cours"),
    "bat_archives": _UNC + r"\1 BATIMENT\Archives",
    "elec_archives": _UNC + r"\2 ELECTRICITE\Archives",
}
DEPARTEMENTS = ("bat", "elec")

# Surcharge des racines (tests) : {"bat": [dossiers…], "elec": [dossiers…]}
ROOTS: dict[str, list[str]] | None = None

_TTL = 60.0  # s : évite de reparcourir le réseau à chaque appel
_cache: dict[tuple[str, str], tuple[float, "Resolution"]] = {}


class Resolution(NamedTuple):
    path: str | None
    status: str  # "ok" | "absent" | "ambigu"


def clear_cache() -> None:
    _cache.clear()


def _roots(dept: str) -> list[str]:
    """Racines d'un département : en cours d'abord, puis archives."""
    if ROOTS is not None:
        return list(ROOTS.get(dept, []))
    out = []
    for kind in ("en_cours", "archives"):
        key = f"{dept}_{kind}"
        out.append(paths._cfg(key, "BEG_" + key.upper()) or _DEFAULTS[key])
    return out


def _normalize_dept(departement: str | None) -> tuple[str, ...]:
    d = (departement or "").strip().lower()
    return (d,) if d in DEPARTEMENTS else DEPARTEMENTS


def _scan(root: str, id_c: str, base: str) -> tuple[list[str], list[str]]:
    """(dossiers à l'ID exact, dossiers au même numéro de base) sous `root`."""
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return [], []
    exact = re.compile(rf"^{re.escape(id_c)}(?!\d)", re.IGNORECASE)
    same_base = re.compile(rf"^{re.escape(base)}(?!\d)", re.IGNORECASE)
    ex, ba = [], []
    for n in names:
        full = os.path.join(root, n)
        if not os.path.isdir(full):
            continue
        if exact.match(n):
            ex.append(full)
        elif same_base.match(n):
            ba.append(full)
    return ex, ba


def find_chantier_dirs(id_chantier: str, departement: str | None = None) -> list[str]:
    """Tous les dossiers du chantier (utile pour la DUC : le n° de base suffit).
    La première racine qui contient le chantier l'emporte (en cours avant archives)."""
    id_c = (id_chantier or "").strip()
    m = re.match(r"\d+", id_c)
    if not m:
        return []
    base = m.group(0)
    res: list[str] = []
    for dept in _normalize_dept(departement):
        for root in _roots(dept):
            ex, ba = _scan(root, id_c, base)
            if ex or ba:
                res += ex + ba
                break
    return res


def resolve(id_chantier: str, departement: str | None = None) -> Resolution:
    """Dossier unique du chantier, ou « absent » / « ambigu »."""
    id_c = (id_chantier or "").strip()
    key = (id_c.lower(), (departement or "").strip().lower())
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    m = re.match(r"\d+", id_c)
    res = Resolution(None, "absent")
    if m:
        base = m.group(0)
        trouves: list[str] = []
        for dept in _normalize_dept(departement):
            for root in _roots(dept):
                ex, ba = _scan(root, id_c, base)
                # ID complet d'abord ; sinon n° de base seulement s'il est sans équivoque
                cand = ex or ba
                if cand:
                    trouves.append(cand)
                    break
        if len(trouves) == 1 and len(trouves[0]) == 1:
            res = Resolution(trouves[0][0], "ok")
        elif trouves:
            res = Resolution(None, "ambigu")
    _cache[key] = (time.monotonic(), res)
    return res


def satisfaction_dirs(
    id_chantier: str, departement: str | None = None, create: bool = False
) -> tuple[str, str] | None:
    """(dossier Photos, dossier Bilan d'expérience) du chantier ; None si le dossier
    du chantier est introuvable. `create=True` crée l'arborescence (peut lever OSError
    si le dossier est protégé ou le réseau coupé : l'appelant se replie alors)."""
    r = resolve(id_chantier, departement)
    if not r.path:
        return None
    se = os.path.join(r.path, SE_DIR)
    photos, bilans = os.path.join(se, PHOTOS_SUB), os.path.join(se, BILANS_SUB)
    if create:
        os.makedirs(photos, exist_ok=True)
        os.makedirs(bilans, exist_ok=True)
    return photos, bilans
