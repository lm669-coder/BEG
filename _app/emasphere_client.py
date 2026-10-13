"""Marge réelle de chantier issue d'EMAsphere (facturé réel / coûts réels).

L'application n'a pas d'accès direct à EMAsphere : les chiffres sont lus dans
un instantané `emasphere_renta.json` (hors base de données), généré depuis les
tables « Renta & plan de charge CONS/ELEC ». Pour le rafraîchir, relancer
l'extraction via le MCP EMAsphere dans Claude.
"""

import json
import os
import re
import sys

if getattr(sys, "frozen", False):
    _BASE = os.path.dirname(sys.executable)
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

SNAPSHOT_PATH = os.path.join(_BASE, "emasphere_renta.json")

_cache: dict = {"mtime": None, "data": None}


def _load() -> dict | None:
    try:
        mtime = os.path.getmtime(SNAPSHOT_PATH)
    except OSError:
        return None
    if _cache["mtime"] != mtime:
        try:
            with open(SNAPSHOT_PATH, encoding="utf-8") as f:
                _cache["data"] = json.load(f)
        except (OSError, ValueError):
            return None
        _cache["mtime"] = mtime
    return _cache["data"]


def _societes(departement: str | None) -> tuple[str, ...]:
    d = (departement or "").strip().lower()
    if d == "bat":
        return ("CONS",)
    if d == "elec":
        return ("ELEC",)
    return ("CONS", "ELEC")


def get_marge_reelle(id_chantier: str, departement: str | None = None) -> dict | None:
    """Retourne {facture, couts, marge_pct, nom, cle, extrait_le} ou None.

    `id_chantier` peut porter un suffixe de sous-chantier (« 22026-2 ») :
    EMAsphere ne connaît que le numéro de base, dont il cumule les chiffres.
    """
    data = _load()
    m = re.match(r"\s*(\d+)", id_chantier or "")
    if not data or not m:
        return None
    base = m.group(1)
    found = [
        (k, data["chantiers"][k])
        for k in (f"{base} {s}" for s in _societes(departement))
        if k in data["chantiers"]
    ]
    if len(found) != 1:  # introuvable, ou ambigu (BAT et ELEC) sans département
        return None
    cle, c = found[0]
    facture, couts = c["facture"], c["couts"]
    return {
        "cle": cle,
        "nom": c["nom"],
        "facture": facture,
        "couts": couts,
        "marge_pct": round((facture - couts) / facture * 100, 2) if facture else None,
        "regroupe": id_chantier.strip() != base,
        "extrait_le": data.get("extrait_le", ""),
    }
