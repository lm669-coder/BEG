"""Tests de la localisation des dossiers chantier et de la sauvegarde de secours.

Arborescences temporaires uniquement : aucun accès aux vrais dossiers SharePoint / S:.
"""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_app"))

import chantier_dirs as cd
import database as db
import paths


def _mk(root, *names):
    for n in names:
        os.makedirs(os.path.join(root, n), exist_ok=True)
    return str(root)


@pytest.fixture
def arbo(tmp_path, monkeypatch):
    """BAT et ELEC : un dossier « en cours » et un dossier « archives » chacun."""
    bat_c = _mk(tmp_path / "bat_cours", "22081 Saint-Ghislain", "24087 Enghien",
                "22026-1 Fabiola L1", "22026-2 Fabiola L2", "220261 Autre")
    bat_a = _mk(tmp_path / "bat_arch", "08005 - Dassis Georges", "08014 - Chatelet rotonde",
                "22081 Doublon archive")
    el_c = _mk(tmp_path / "elec_cours", "21005 Cite des Metiers")
    el_a = _mk(tmp_path / "elec_arch", "08014 - Ville de Chatelet - Pictogramme")
    monkeypatch.setattr(cd, "ROOTS", {"bat": [bat_c, bat_a], "elec": [el_c, el_a]})
    cd.clear_cache()
    yield tmp_path
    cd.clear_cache()


def _name(res):
    return os.path.basename(res.path) if res.path else None


class TestResolve:
    def test_en_cours_bat(self, arbo):
        r = cd.resolve("22081", "Bat")
        assert r.status == "ok" and _name(r) == "22081 Saint-Ghislain"

    def test_en_cours_prioritaire_sur_archives(self, arbo):
        assert "bat_cours" in cd.resolve("22081", "Bat").path

    def test_archives_si_absent_en_cours(self, arbo):
        r = cd.resolve("08005", "Bat")
        assert r.status == "ok" and "bat_arch" in r.path

    def test_departement_elec(self, arbo):
        r = cd.resolve("21005", "Elec")
        assert r.status == "ok" and "elec_cours" in r.path

    def test_collision_bat_elec_avec_departement(self, arbo):
        assert "bat_arch" in cd.resolve("08014", "Bat").path
        assert "elec_arch" in cd.resolve("08014", "Elec").path

    def test_collision_bat_elec_sans_departement_est_ambigu(self, arbo):
        r = cd.resolve("08014", None)
        assert r.path is None and r.status == "ambigu"

    def test_departement_inconnu_mais_numero_unique(self, arbo):
        assert cd.resolve("21005", None).status == "ok"

    def test_casse_du_departement(self, arbo):
        assert cd.resolve("22081", "BAT").status == "ok"

    def test_id_complet_avec_suffixe(self, arbo):
        assert _name(cd.resolve("22026-1", "Bat")) == "22026-1 Fabiola L1"
        assert _name(cd.resolve("22026-2", "Bat")) == "22026-2 Fabiola L2"

    def test_numero_de_base_commun_a_deux_sous_chantiers_est_ambigu(self, arbo):
        assert cd.resolve("22026", "Bat").status == "ambigu"
        assert cd.resolve("22026-3", "Bat").status == "ambigu"

    def test_suffixe_inconnu_numero_de_base_unique(self, arbo):
        assert _name(cd.resolve("24087-1", "Bat")) == "24087 Enghien"

    def test_pas_de_confusion_de_prefixe_numerique(self, arbo):
        # « 220261 Autre » ne doit pas être pris pour le chantier 22026
        for d in ("22026-1 Fabiola L1", "22026-2 Fabiola L2"):
            os.rmdir(os.path.join(arbo, "bat_cours", d))
        cd.clear_cache()
        assert cd.resolve("22026", "Bat").status == "absent"

    @pytest.mark.parametrize("bad", ["", "   ", "abc", "X-12", None])
    def test_id_invalide(self, arbo, bad):
        r = cd.resolve(bad, "Bat")
        assert r.path is None and r.status == "absent"

    def test_introuvable(self, arbo):
        r = cd.resolve("99999", "Bat")
        assert r.path is None and r.status == "absent"

    def test_racine_inexistante_ne_leve_pas(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cd, "ROOTS", {"bat": [str(tmp_path / "nope")], "elec": []})
        cd.clear_cache()
        assert cd.resolve("22081", "Bat").status == "absent"

    def test_fichier_du_meme_nom_ignore(self, tmp_path, monkeypatch):
        root = str(tmp_path / "r")
        os.makedirs(root)
        open(os.path.join(root, "22081 fichier.txt"), "w").close()
        monkeypatch.setattr(cd, "ROOTS", {"bat": [root], "elec": []})
        cd.clear_cache()
        assert cd.resolve("22081", "Bat").status == "absent"


class TestFindChantierDirs:
    def test_tous_les_sous_chantiers_pour_la_duc(self, arbo):
        noms = sorted(os.path.basename(p) for p in cd.find_chantier_dirs("22026-1", "Bat"))
        assert noms == ["22026-1 Fabiola L1", "22026-2 Fabiola L2"]

    def test_vide_si_introuvable(self, arbo):
        assert cd.find_chantier_dirs("99999", "Bat") == []
        assert cd.find_chantier_dirs("", "Bat") == []


class TestSatisfactionDirs:
    def test_aucune_creation_sans_create(self, arbo):
        photos, bilans = cd.satisfaction_dirs("22081", "Bat")
        assert not os.path.exists(photos) and not os.path.exists(bilans)
        assert not os.path.exists(os.path.dirname(photos))

    def test_creation_et_noms(self, arbo):
        photos, bilans = cd.satisfaction_dirs("22081", "Bat", create=True)
        assert os.path.isdir(photos) and os.path.isdir(bilans)
        assert photos.endswith(os.path.join("22081 Saint-Ghislain", "Satisfaction & Expérience", "Photos"))
        assert bilans.endswith(os.path.join("Satisfaction & Expérience", "Bilan d'expérience"))

    def test_creation_idempotente(self, arbo):
        a = cd.satisfaction_dirs("22081", "Bat", create=True)
        open(os.path.join(a[1], "Bilan_22081.pdf"), "w").close()
        b = cd.satisfaction_dirs("22081", "Bat", create=True)
        assert a == b and os.path.exists(os.path.join(b[1], "Bilan_22081.pdf"))

    def test_archives(self, arbo):
        photos, _ = cd.satisfaction_dirs("08005", "Bat", create=True)
        assert "bat_arch" in photos and os.path.isdir(photos)

    def test_introuvable_donne_none_et_ne_cree_rien(self, arbo):
        assert cd.satisfaction_dirs("99999", "Bat", create=True) is None

    def test_ambigu_donne_none(self, arbo):
        assert cd.satisfaction_dirs("08014", None, create=True) is None


class TestCache:
    def test_resultat_mis_en_cache(self, arbo):
        assert cd.resolve("24087", "Bat").status == "ok"
        os.rmdir(os.path.join(arbo, "bat_cours", "24087 Enghien"))
        assert cd.resolve("24087", "Bat").status == "ok"  # encore en cache
        cd.clear_cache()
        assert cd.resolve("24087", "Bat").status == "absent"


# ── Sauvegarde de secours ───────────────────────────────────────────────────
@pytest.fixture
def base(tmp_path, monkeypatch):
    f = str(tmp_path / "data" / "BEG_Data.db")
    os.makedirs(os.path.dirname(f))
    c = sqlite3.connect(f)
    c.execute("CREATE TABLE t (x INTEGER)")
    c.execute("INSERT INTO t VALUES (42)")
    c.commit()
    c.close()
    monkeypatch.setattr(db, "DB_PATH", f)
    monkeypatch.setenv("USERNAME", "testeur")
    return f


def _fichiers(d):
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


class TestBackupSecours:
    def test_copie_dans_le_dossier_de_secours(self, base, tmp_path, monkeypatch):
        sec = str(tmp_path / "secours")
        monkeypatch.setattr(paths, "BACKUP_DIR_SECOURS", sec)
        created = db.backup_if_due()
        assert created and os.path.exists(created)
        copies = _fichiers(sec)
        assert len(copies) == 1 and copies[0] == os.path.basename(created)
        c = sqlite3.connect(os.path.join(sec, copies[0]))
        assert c.execute("SELECT x FROM t").fetchone()[0] == 42  # copie exploitable
        c.close()

    def test_pas_de_doublon_au_second_appel(self, base, tmp_path, monkeypatch):
        sec = str(tmp_path / "secours")
        monkeypatch.setattr(paths, "BACKUP_DIR_SECOURS", sec)
        db.backup_if_due()
        assert db.backup_if_due() is None
        assert len(_fichiers(sec)) == 1

    def test_secours_rattrape_une_sauvegarde_locale_deja_faite(self, base, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "BACKUP_DIR_SECOURS", "")
        db.backup_if_due()  # sauvegarde locale du jour, secours désactivé
        sec = str(tmp_path / "secours")
        monkeypatch.setattr(paths, "BACKUP_DIR_SECOURS", sec)
        assert db.backup_if_due() is None  # rien de nouveau en local...
        assert len(_fichiers(sec)) == 1  # ...mais le secours est alimenté

    def test_secours_desactive(self, base, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "BACKUP_DIR_SECOURS", "")
        assert db.backup_if_due()
        assert not os.path.exists(tmp_path / "secours")

    def test_secours_injoignable_ne_bloque_pas(self, base, tmp_path, monkeypatch):
        bloc = tmp_path / "fichier"
        bloc.write_text("x")  # un fichier à la place du dossier : makedirs échoue
        monkeypatch.setattr(paths, "BACKUP_DIR_SECOURS", str(bloc / "sous"))
        assert db.backup_if_due()  # la sauvegarde principale reste faite
