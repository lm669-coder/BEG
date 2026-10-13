"""Chemins de l'application.

APP_DIR  : code et ressources embarquées (logo...), local à l'exécutable.
DATA_DIR : Photos/ et emasphere_renta.json (BEG_DATA_DIR > beg_config.ini data_dir).
DB_DIR   : base SQLite (BEG_DB_DIR > beg_config.ini db_dir > DATA_DIR).
           Défaut : dossier de l'exe (gelé) ou du code (développement).
CACHE_DIR: cache local par utilisateur (miniatures...), jamais sur le réseau.
"""

import configparser
import os
import sys

FROZEN = bool(getattr(sys, "frozen", False))

if FROZEN:
    EXE_DIR = os.path.dirname(sys.executable)
    APP_DIR = getattr(sys, "_MEIPASS", EXE_DIR)
    LOGO_PATH = os.path.join(APP_DIR, "Données", "logo.png")
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = APP_DIR
    LOGO_PATH = os.path.join(os.path.dirname(APP_DIR), "Données", "logo.png")


def _cfg(key: str, env: str) -> str:
    """Valeur de config : variable d'environnement > beg_config.ini ([beg]) > "".
    Les variables Windows (%USERPROFILE%...) sont développées : un même .ini
    sert à tous les postes (ex. dossier SharePoint synchronisé)."""
    val = os.environ.get(env, "").strip()
    if not val:
        ini = os.path.join(EXE_DIR, "beg_config.ini")
        if os.path.isfile(ini):
            cp = configparser.ConfigParser(interpolation=None)  # le "%" de %USERPROFILE% n'est pas une interpolation
            try:
                cp.read(ini, encoding="utf-8")
                val = cp.get("beg", key, fallback="").strip()
            except configparser.Error:
                val = ""
    return os.path.expandvars(val)


# Photos et instantané EMAsphere (fichiers entiers : un dossier synchronisé,
# p. ex. SharePoint/OneDrive, convient).
DATA_DIR = _cfg("data_dir", "BEG_DATA_DIR") or EXE_DIR
# Base SQLite. Sur un dossier synchronisé (OneDrive/SharePoint), des enregistrements
# SIMULTANÉS de plusieurs postes peuvent créer des copies en conflit : l'application
# fait des sauvegardes quotidiennes (backups/) et signale ces copies (database.py).
DB_DIR_EXPLICIT = bool(_cfg("db_dir", "BEG_DB_DIR"))  # configurée => ne jamais créer une base vide
DB_DIR = _cfg("db_dir", "BEG_DB_DIR") or DATA_DIR

CACHE_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "BEG", "cache"
)
