"""
Tests pytest complets pour les 3 modules backend BEG RMI.
Chaque test utilise une DB isolée (tmpfile) ou une connexion en mémoire.
Aucun import Qt — modules backend purs.
"""

import io
import os
import sqlite3
import sys
import tempfile
from datetime import datetime

import pytest

# ── Path ─────────────────────────────────────────────────────────────────────
sys.path.insert(0, r"P:\BEG_RMI\_app")

import database as db
import import_data as imp
import pdf_export as pdf


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures partagées
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """DB isolée dans un fichier temp — jamais la DB de prod."""
    db_file = str(tmp_path / "test_beg.db")
    monkeypatch.setattr(db, "DB_PATH", db_file)
    db.init_db()
    return db_file


@pytest.fixture
def mem_conn():
    """Connexion SQLite en mémoire pour les tests import_data (pas de DB_PATH)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chantiers (
            id_chantier TEXT PRIMARY KEY,
            departement TEXT, gestionnaire TEXT, intitule TEXT, secteur TEXT,
            adresse TEXT, province TEXT, distance REAL, client TEXT,
            type_client TEXT, montant REAL, delai_execution INTEGER,
            date_marche_gagne TEXT, ordre_commencer TEXT,
            rp_demandee TEXT, rp_realisee TEXT,
            rd_a_demander TEXT, rd_realisee TEXT,
            rp_statut TEXT, rd_statut TEXT,
            n_cautionnement TEXT, organisme TEXT, montant_cautionnement REAL,
            document_rp TEXT, document_rd TEXT, prix_de_revient REAL
        );
        CREATE TABLE IF NOT EXISTS decomptes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_chantier TEXT NOT NULL,
            n_decompte TEXT, intitule TEXT,
            montant REAL, delai_complementaire INTEGER, statut_accepte INTEGER
        );
        CREATE TABLE IF NOT EXISTS etats_avancement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num_chantier TEXT, lot TEXT, gestionnaire TEXT, nom_chantier TEXT,
            date_envoi TEXT, n_ea TEXT, montant_facture REAL
        );
    """)
    yield conn
    conn.close()


def _make_wb(headers, data_rows, sheet_name="Sheet1"):
    """Crée un workbook openpyxl en mémoire (BytesIO)."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(headers)
    for row in data_rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ═════════════════════════════════════════════════════════════════════════════
# 1. database.py
# ═════════════════════════════════════════════════════════════════════════════

class TestInitDb:
    def test_creates_all_tables(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        expected = {
            "chantiers", "decomptes", "etats_avancement", "bilans",
            "bilan_parties_prenantes", "bilan_sous_traitants",
            "bilan_postes_perte", "bilan_postes_surbenefice",
            "bilan_travaux_internes",
        }
        assert expected.issubset(tables)

    def test_idempotent(self, tmp_db):
        """Appelée deux fois sans erreur."""
        db.init_db()
        db.init_db()  # deuxième appel — ne doit pas lever d'exception

    def test_migration_columns_added(self, tmp_db):
        """Les colonnes de migration sont présentes (statut_accepte sur decomptes)."""
        conn = sqlite3.connect(tmp_db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(decomptes)").fetchall()}
        conn.close()
        assert "statut_accepte" in cols


class TestGetChantier:
    def test_returns_none_if_absent(self, tmp_db):
        assert db.get_chantier("NONEXISTENT") is None

    def test_returns_dict_if_present(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO chantiers (id_chantier, intitule, gestionnaire) VALUES (?,?,?)",
            ("C001", "Chantier Test", "Dupont"),
        )
        conn.commit()
        conn.close()

        result = db.get_chantier("C001")
        assert result is not None
        assert isinstance(result, dict)
        assert result["id_chantier"] == "C001"
        assert result["intitule"] == "Chantier Test"
        assert result["gestionnaire"] == "Dupont"


class TestSaveBilan:
    def _base_data(self, id_c="C001"):
        return {
            "id_chantier": id_c,
            "date_bilan": "2024-06-30",
            "parties_prenantes": [],
            "sous_traitants": [],
            "postes_perte": [],
            "postes_surbenefice": [],
            "travaux_internes": [],
        }

    def test_insert_returns_positive_id(self, tmp_db):
        bilan_id = db.save_bilan(self._base_data())
        assert isinstance(bilan_id, int)
        assert bilan_id > 0

    def test_update_modifies_correct_record(self, tmp_db):
        bilan_id = db.save_bilan(self._base_data())

        data = self._base_data()
        data["id"] = bilan_id
        data["marge_finale"] = 14.75
        db.save_bilan(data)

        loaded = db.load_bilan(bilan_id)
        assert loaded is not None
        assert loaded["marge_finale"] == pytest.approx(14.75)

    def test_update_does_not_create_duplicate(self, tmp_db):
        bilan_id = db.save_bilan(self._base_data())

        data = self._base_data()
        data["id"] = bilan_id
        db.save_bilan(data)

        conn = sqlite3.connect(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM bilans").fetchone()[0]
        conn.close()
        assert count == 1

    def test_saves_child_rows(self, tmp_db):
        data = self._base_data()
        data["postes_perte"] = [{"denomination": "Béton", "prs": 10000.0, "pre": 12500.0}]
        data["travaux_internes"] = [{"denomination": "Maçon.", "heures_soumission": 100.0, "heures_execution": 90.0}]
        bilan_id = db.save_bilan(data)

        conn = sqlite3.connect(tmp_db)
        pp_count = conn.execute(
            "SELECT COUNT(*) FROM bilan_postes_perte WHERE bilan_id=?", (bilan_id,)
        ).fetchone()[0]
        ti_count = conn.execute(
            "SELECT COUNT(*) FROM bilan_travaux_internes WHERE bilan_id=?", (bilan_id,)
        ).fetchone()[0]
        conn.close()
        assert pp_count == 1
        assert ti_count == 1


class TestLoadBilan:
    def test_returns_none_for_missing_id(self, tmp_db):
        assert db.load_bilan(99999) is None

    def test_loads_all_subtables(self, tmp_db):
        data = {
            "id_chantier": "C001",
            "date_bilan": "2024-01-15",
            "parties_prenantes": [
                {"role": "MO", "nom": "Dupont", "relation": "Bonne", "evaluation": 4}
            ],
            "sous_traitants": [
                {
                    "nom": "ST1",
                    "respect_prix": 3, "respect_delais": 4,
                    "respect_securite": 5, "respect_qualite": 4,
                    "reactivite": 3, "communication": 4,
                }
            ],
            "postes_perte": [
                {"denomination": "Terrassement", "prs": 10000.0, "pre": 12000.0}
            ],
            "postes_surbenefice": [
                {"denomination": "Béton", "prs": 5000.0, "pre": 4000.0}
            ],
            "travaux_internes": [
                {"denomination": "Maçonnerie", "heures_soumission": 100.0, "heures_execution": 90.0}
            ],
        }
        bilan_id = db.save_bilan(data)
        loaded = db.load_bilan(bilan_id)

        assert loaded is not None
        assert len(loaded["parties_prenantes"]) == 1
        assert loaded["parties_prenantes"][0]["nom"] == "Dupont"
        assert len(loaded["sous_traitants"]) == 1
        assert loaded["sous_traitants"][0]["nom"] == "ST1"
        assert len(loaded["postes_perte"]) == 1
        assert loaded["postes_perte"][0]["denomination"] == "Terrassement"
        assert len(loaded["postes_surbenefice"]) == 1
        assert len(loaded["travaux_internes"]) == 1
        assert loaded["travaux_internes"][0]["heures_soumission"] == pytest.approx(100.0)

    def test_update_replaces_child_rows(self, tmp_db):
        """Un UPDATE doit remplacer les lignes enfants, pas s'y accumuler."""
        data = {
            "id_chantier": "C001",
            "postes_perte": [{"denomination": "Poste1", "prs": 1000.0, "pre": 1200.0}],
            "parties_prenantes": [], "sous_traitants": [],
            "postes_surbenefice": [], "travaux_internes": [],
        }
        bilan_id = db.save_bilan(data)

        data["id"] = bilan_id
        data["postes_perte"] = [
            {"denomination": "Poste2", "prs": 2000.0, "pre": 2500.0},
            {"denomination": "Poste3", "prs": 3000.0, "pre": 3500.0},
        ]
        db.save_bilan(data)

        loaded = db.load_bilan(bilan_id)
        # L'ancienne ligne doit être remplacée, pas dupliquée
        assert len(loaded["postes_perte"]) == 2
        assert loaded["postes_perte"][0]["denomination"] == "Poste2"


class TestDeleteBilan:
    def test_deletes_bilan(self, tmp_db):
        bilan_id = db.save_bilan({
            "id_chantier": "C001",
            "parties_prenantes": [], "sous_traitants": [],
            "postes_perte": [], "postes_surbenefice": [], "travaux_internes": [],
        })
        db.delete_bilan(bilan_id)
        assert db.load_bilan(bilan_id) is None

    def test_cascade_deletes_children(self, tmp_db):
        """Les lignes enfants sont supprimées en CASCADE avec le bilan parent."""
        data = {
            "id_chantier": "C001",
            "postes_perte": [{"denomination": "Test", "prs": 1000.0, "pre": 1200.0}],
            "parties_prenantes": [{"role": "MO", "nom": "X", "relation": "OK", "evaluation": 3}],
            "sous_traitants": [],
            "postes_surbenefice": [],
            "travaux_internes": [],
        }
        bilan_id = db.save_bilan(data)

        # Vérification avant suppression
        conn = sqlite3.connect(tmp_db)
        n_perte = conn.execute(
            "SELECT COUNT(*) FROM bilan_postes_perte WHERE bilan_id=?", (bilan_id,)
        ).fetchone()[0]
        n_pp = conn.execute(
            "SELECT COUNT(*) FROM bilan_parties_prenantes WHERE bilan_id=?", (bilan_id,)
        ).fetchone()[0]
        conn.close()
        assert n_perte == 1
        assert n_pp == 1

        db.delete_bilan(bilan_id)

        conn = sqlite3.connect(tmp_db)
        n_perte_after = conn.execute(
            "SELECT COUNT(*) FROM bilan_postes_perte WHERE bilan_id=?", (bilan_id,)
        ).fetchone()[0]
        n_pp_after = conn.execute(
            "SELECT COUNT(*) FROM bilan_parties_prenantes WHERE bilan_id=?", (bilan_id,)
        ).fetchone()[0]
        conn.close()
        assert n_perte_after == 0
        assert n_pp_after == 0


class TestGetDecompotesTotals:
    def test_sums_montant_and_delai(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO decomptes (id_chantier, montant, delai_complementaire, statut_accepte) VALUES (?,?,?,?)",
            ("C001", 5000.0, 10, 1),
        )
        conn.execute(
            "INSERT INTO decomptes (id_chantier, montant, delai_complementaire, statut_accepte) VALUES (?,?,?,?)",
            ("C001", 3000.0, 5, 1),
        )
        conn.commit()
        conn.close()

        result = db.get_decomptes_totals("C001")
        assert result["montant"] == pytest.approx(8000.0)
        assert result["delai"] == 15

    def test_filters_refused_statut(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO decomptes (id_chantier, montant, delai_complementaire, statut_accepte) VALUES (?,?,?,?)",
            ("C002", 5000.0, 10, 1),  # accepté
        )
        conn.execute(
            "INSERT INTO decomptes (id_chantier, montant, delai_complementaire, statut_accepte) VALUES (?,?,?,?)",
            ("C002", 9000.0, 20, 0),  # refusé — doit être exclu
        )
        conn.commit()
        conn.close()

        result = db.get_decomptes_totals("C002")
        assert result["montant"] == pytest.approx(5000.0)
        assert result["delai"] == 10

    def test_null_statut_is_included(self, tmp_db):
        """statut_accepte IS NULL doit être inclus (= non renseigné)."""
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO decomptes (id_chantier, montant, delai_complementaire) VALUES (?,?,?)",
            ("C003", 4000.0, 8),
        )
        conn.commit()
        conn.close()

        result = db.get_decomptes_totals("C003")
        assert result["montant"] == pytest.approx(4000.0)

    def test_returns_zero_if_no_decomptes(self, tmp_db):
        result = db.get_decomptes_totals("MISSING")
        assert result["montant"] == 0.0
        assert result["delai"] == 0


class TestGetMontantFacture:
    def test_returns_zero_if_no_ea(self, tmp_db):
        assert db.get_montant_facture("MISSING") == 0.0

    def test_sums_ea_montants(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO etats_avancement (num_chantier, montant_facture) VALUES (?,?)",
            ("C001", 10000.0),
        )
        conn.execute(
            "INSERT INTO etats_avancement (num_chantier, montant_facture) VALUES (?,?)",
            ("C001", 5000.0),
        )
        conn.commit()
        conn.close()
        assert db.get_montant_facture("C001") == pytest.approx(15000.0)

    def test_only_sums_matching_chantier(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO etats_avancement (num_chantier, montant_facture) VALUES (?,?)",
            ("C001", 10000.0),
        )
        conn.execute(
            "INSERT INTO etats_avancement (num_chantier, montant_facture) VALUES (?,?)",
            ("C002", 99999.0),  # autre chantier — ne doit pas être inclus
        )
        conn.commit()
        conn.close()
        assert db.get_montant_facture("C001") == pytest.approx(10000.0)


class TestGetAllBilans:
    def test_returns_empty_list_if_none(self, tmp_db):
        assert db.get_all_bilans() == []

    def test_returns_list_of_dicts(self, tmp_db):
        db.save_bilan({
            "id_chantier": "C001",
            "date_bilan": "2024-06-30",
            "parties_prenantes": [], "sous_traitants": [],
            "postes_perte": [], "postes_surbenefice": [], "travaux_internes": [],
        })
        result = db.get_all_bilans()
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]["id_chantier"] == "C001"

    def test_ordered_by_date_desc(self, tmp_db):
        for date in ["2024-01-01", "2024-06-15", "2023-12-01"]:
            db.save_bilan({
                "id_chantier": "C001",
                "date_bilan": date,
                "parties_prenantes": [], "sous_traitants": [],
                "postes_perte": [], "postes_surbenefice": [], "travaux_internes": [],
            })
        result = db.get_all_bilans()
        assert len(result) == 3
        dates = [r["date_bilan"] for r in result]
        assert dates == sorted(dates, reverse=True)


class TestBilanExistsForChantier:
    def test_returns_none_if_absent(self, tmp_db):
        assert db.bilan_exists_for_chantier("MISSING") is None

    def test_returns_id_if_present(self, tmp_db):
        bilan_id = db.save_bilan({
            "id_chantier": "C001",
            "parties_prenantes": [], "sous_traitants": [],
            "postes_perte": [], "postes_surbenefice": [], "travaux_internes": [],
        })
        result = db.bilan_exists_for_chantier("C001")
        assert result == bilan_id

    def test_returns_first_match(self, tmp_db):
        """Doit retourner l'id du premier bilan trouvé pour ce chantier."""
        id1 = db.save_bilan({
            "id_chantier": "C001",
            "parties_prenantes": [], "sous_traitants": [],
            "postes_perte": [], "postes_surbenefice": [], "travaux_internes": [],
        })
        result = db.bilan_exists_for_chantier("C001")
        assert result == id1


# ═════════════════════════════════════════════════════════════════════════════
# 2. import_data.py
# ═════════════════════════════════════════════════════════════════════════════

class TestSafe:
    def test_none_returns_none(self):
        assert imp._safe(None) is None

    def test_datetime_returns_ddmmyyyy(self):
        dt = datetime(2024, 3, 15)
        assert imp._safe(dt) == "15/03/2024"

    def test_na_returns_none(self):
        assert imp._safe("#N/A") is None

    def test_ref_returns_none(self):
        assert imp._safe("#REF!") is None

    def test_value_error_returns_none(self):
        assert imp._safe("#VALUE!") is None

    def test_empty_string_returns_none(self):
        assert imp._safe("") is None

    def test_none_string_returns_none(self):
        assert imp._safe("None") is None

    def test_nan_string_returns_none(self):
        assert imp._safe("nan") is None

    def test_normal_string_returns_same(self):
        assert imp._safe("Dupont") == "Dupont"

    def test_number_returns_string(self):
        assert imp._safe(42) == "42"

    def test_whitespace_stripped(self):
        assert imp._safe("  hello  ") == "hello"


class TestNum:
    def test_french_space_comma(self):
        assert imp._num("1 234,56") == pytest.approx(1234.56)

    def test_none_returns_none(self):
        assert imp._num(None) is None

    def test_invalid_string_returns_none(self):
        assert imp._num("abc") is None

    def test_comma_decimal(self):
        assert imp._num("12,5") == pytest.approx(12.5)

    def test_dot_decimal(self):
        assert imp._num("12.5") == pytest.approx(12.5)

    def test_integer_string(self):
        assert imp._num("100") == pytest.approx(100.0)

    def test_float_value(self):
        assert imp._num(3.14) == pytest.approx(3.14)

    def test_zero_string(self):
        assert imp._num("0") == pytest.approx(0.0)

    def test_nbsp_stripped(self):
        # Non-breaking space (Excel parfois génère \xa0)
        assert imp._num("1\xa0000,00") == pytest.approx(1000.0)


class TestNormalize:
    def test_accents_removed(self):
        assert imp._normalize("éàü") == "eau"

    def test_lowercase(self):
        assert imp._normalize("HELLO") == "hello"

    def test_strips_spaces(self):
        assert imp._normalize("  test  ") == "test"

    def test_empty_string(self):
        assert imp._normalize("") == ""

    def test_none_returns_empty(self):
        assert imp._normalize(None) == ""

    def test_mixed_accents(self):
        assert imp._normalize("  Désignation  ") == "designation"

    def test_cedilla(self):
        assert imp._normalize("façon") == "facon"


class TestFindCol:
    def test_finds_by_partial_keyword(self):
        headers = ["id chantier", "gestionnaire", "montant"]
        norm = [imp._normalize(h) for h in headers]
        assert imp._find_col(norm, "gest") == 1

    def test_returns_none_if_absent(self):
        headers = ["id chantier", "gestionnaire"]
        norm = [imp._normalize(h) for h in headers]
        assert imp._find_col(norm, "montant") is None

    def test_first_match_wins(self):
        headers = ["montant total", "montant net"]
        norm = [imp._normalize(h) for h in headers]
        assert imp._find_col(norm, "montant") == 0

    def test_multiple_keywords_any_match(self):
        headers = ["num chantier", "reference projet"]
        norm = [imp._normalize(h) for h in headers]
        assert imp._find_col(norm, "reference", "gest") == 1


class TestImportChantiers:
    def test_imports_valid_rows(self, mem_conn):
        headers = ["id chantier", "gestionnaire", "intitule", "montant"]
        data = [
            ["C001", "Dupont", "Chantier A", 150000],
            ["C002", "Martin", "Chantier B", 200000],
        ]
        buf = _make_wb(headers, data)
        imported, skipped, col = imp.import_chantiers(buf, "Sheet1", mem_conn)
        assert imported == 2
        assert skipped == 0
        rows = mem_conn.execute(
            "SELECT id_chantier FROM chantiers ORDER BY id_chantier"
        ).fetchall()
        assert len(rows) == 2

    def test_skips_rows_with_no_id(self, mem_conn):
        headers = ["id chantier", "intitule"]
        data = [[None, "Sans ID"], ["C001", "Avec ID"]]
        buf = _make_wb(headers, data)
        imported, skipped, _ = imp.import_chantiers(buf, "Sheet1", mem_conn)
        assert imported == 1

    def test_skips_duplicates_overwrite_false(self, mem_conn):
        headers = ["id chantier", "intitule"]
        buf1 = _make_wb(headers, [["C001", "Chantier A"]])
        imp.import_chantiers(buf1, "Sheet1", mem_conn)

        buf2 = _make_wb(headers, [["C001", "Chantier A modifié"]])
        imported, skipped, _ = imp.import_chantiers(
            buf2, "Sheet1", mem_conn, overwrite=False
        )
        assert imported == 0
        assert skipped == 1
        # L'original est préservé
        row = mem_conn.execute(
            "SELECT intitule FROM chantiers WHERE id_chantier='C001'"
        ).fetchone()
        assert row[0] == "Chantier A"

    def test_overwrites_all_when_overwrite_true(self, mem_conn):
        headers = ["id chantier", "intitule"]
        buf1 = _make_wb(headers, [["C001", "Chantier A"]])
        imp.import_chantiers(buf1, "Sheet1", mem_conn)

        buf2 = _make_wb(headers, [["C001", "Chantier A v2"]])
        imported, skipped, _ = imp.import_chantiers(
            buf2, "Sheet1", mem_conn, overwrite=True
        )
        assert imported == 1
        assert skipped == 0
        row = mem_conn.execute(
            "SELECT intitule FROM chantiers WHERE id_chantier='C001'"
        ).fetchone()
        assert row[0] == "Chantier A v2"

    def test_numeric_montant_parsed(self, mem_conn):
        headers = ["id chantier", "montant"]
        data = [["C001", "150 000,00"]]  # format français
        buf = _make_wb(headers, data)
        imp.import_chantiers(buf, "Sheet1", mem_conn)
        row = mem_conn.execute(
            "SELECT montant FROM chantiers WHERE id_chantier='C001'"
        ).fetchone()
        assert row[0] == pytest.approx(150000.0)


class TestImportDecomptes:
    def test_import_basic(self, mem_conn):
        headers = ["num chantier", "montant", "delai complementaire"]
        data = [["C001", 10000, 30], ["C001", 5000, 15]]
        buf = _make_wb(headers, data)
        imported, cols = imp.import_decomptes(buf, "Sheet1", mem_conn)
        assert imported == 2
        rows = mem_conn.execute(
            "SELECT montant FROM decomptes WHERE id_chantier='C001'"
        ).fetchall()
        assert len(rows) == 2

    def test_accepte_various_values(self, mem_conn):
        """Teste _accepte avec 0/1/oui/non/x."""
        headers = ["num chantier", "montant", "approuve"]
        data = [
            ["C001", 10000, 1],      # → 1 (int)
            ["C001", 5000, 0],       # → 0 (int)
            ["C001", 2000, "oui"],   # → 1 (string)
            ["C001", 1000, "non"],   # → 0 (string)
            ["C001", 500, "x"],      # → 1 (marqueur)
        ]
        buf = _make_wb(headers, data)
        imported, _ = imp.import_decomptes(buf, "Sheet1", mem_conn)
        assert imported == 5

        rows = mem_conn.execute(
            "SELECT statut_accepte FROM decomptes ORDER BY id"
        ).fetchall()
        statuts = [r[0] for r in rows]
        assert statuts == [1, 0, 1, 0, 1]

    def test_overwrite_clears_table(self, mem_conn):
        headers = ["num chantier", "montant"]
        buf1 = _make_wb(headers, [["C001", 10000]])
        imp.import_decomptes(buf1, "Sheet1", mem_conn)

        buf2 = _make_wb(headers, [["C002", 20000]])
        imp.import_decomptes(buf2, "Sheet1", mem_conn, overwrite=True)

        rows = mem_conn.execute("SELECT id_chantier FROM decomptes").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "C002"

    def test_skips_rows_with_no_id(self, mem_conn):
        headers = ["num chantier", "montant"]
        data = [[None, 5000], ["C001", 10000]]
        buf = _make_wb(headers, data)
        imported, _ = imp.import_decomptes(buf, "Sheet1", mem_conn)
        assert imported == 1


class TestImportEa:
    def test_import_basic(self, mem_conn):
        headers = ["num chantier", "montant facture", "lot", "gestionnaire"]
        data = [
            ["C001", 50000, "LOT1", "Dupont"],
            ["C002", 75000, "LOT2", "Martin"],
        ]
        buf = _make_wb(headers, data)
        imported, cols = imp.import_ea(buf, "Sheet1", mem_conn)
        assert imported == 2

    def test_auto_detects_montant_column(self, mem_conn):
        headers = ["num chantier", "montant facture"]
        data = [["C001", 1234.56]]
        buf = _make_wb(headers, data)
        imported, cols = imp.import_ea(buf, "Sheet1", mem_conn)
        assert imported == 1
        row = mem_conn.execute(
            "SELECT montant_facture FROM etats_avancement"
        ).fetchone()
        assert row[0] == pytest.approx(1234.56)

    def test_skips_empty_id_rows(self, mem_conn):
        headers = ["num chantier", "montant facture"]
        data = [[None, 1000], ["C001", 2000]]
        buf = _make_wb(headers, data)
        imported, _ = imp.import_ea(buf, "Sheet1", mem_conn)
        assert imported == 1

    def test_overwrite_clears_table(self, mem_conn):
        headers = ["num chantier", "montant facture"]
        buf1 = _make_wb(headers, [["C001", 1000]])
        imp.import_ea(buf1, "Sheet1", mem_conn)

        buf2 = _make_wb(headers, [["C002", 2000]])
        imp.import_ea(buf2, "Sheet1", mem_conn, overwrite=True)

        rows = mem_conn.execute(
            "SELECT num_chantier FROM etats_avancement"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "C002"

    def test_stores_lot_gestionnaire(self, mem_conn):
        headers = ["num chantier", "montant facture", "lot", "gestionnaire", "n° ea"]
        data = [["C001", 5000, "LOT1", "Martin", "EA01"]]
        buf = _make_wb(headers, data)
        imp.import_ea(buf, "Sheet1", mem_conn)
        row = mem_conn.execute(
            "SELECT lot, gestionnaire, n_ea FROM etats_avancement"
        ).fetchone()
        assert row[0] == "LOT1"
        assert row[1] == "Martin"
        assert row[2] == "EA01"


# ═════════════════════════════════════════════════════════════════════════════
# 3. pdf_export.py
# ═════════════════════════════════════════════════════════════════════════════

class TestEuro:
    def test_none_returns_dash(self):
        assert pdf._euro(None) == "—"

    def test_zero(self):
        result = pdf._euro(0)
        assert "0" in result

    def test_large_number_formatted(self):
        result = pdf._euro(1234.56)
        # Contient les trois groupes de chiffres
        assert "1" in result
        assert "234" in result
        assert "56" in result
        assert "€" in result

    def test_negative(self):
        result = pdf._euro(-500.0)
        assert "-" in result
        assert "€" in result


class TestPct:
    def test_none_returns_dash(self):
        assert pdf._pct(None) == "—"

    def test_formats_float(self):
        result = pdf._pct(12.5)
        assert "12" in result
        assert "%" in result

    def test_zero(self):
        result = pdf._pct(0)
        assert "%" in result


class TestStars:
    def test_none_returns_dash(self):
        assert pdf._stars(None) == "—"

    def test_three_stars(self):
        result = pdf._stars(3)
        assert "★★★" in result
        assert "3/5" in result

    def test_five_stars(self):
        result = pdf._stars(5)
        assert "★★★★★" in result
        assert "5/5" in result

    def test_zero_stars(self):
        result = pdf._stars(0)
        assert "0/5" in result

    def test_correct_total_length(self):
        # 5 étoiles/points + texte
        for n in range(6):
            result = pdf._stars(n)
            stars = result.count("★")
            dots = result.count("·")
            assert stars + dots == 5


class TestVal:
    def test_none_returns_dash(self):
        assert pdf._val(None) == "—"

    def test_empty_string_returns_dash(self):
        assert pdf._val("") == "—"

    def test_none_string_returns_dash(self):
        assert pdf._val("None") == "—"

    def test_normal_string(self):
        assert pdf._val("Dupont") == "Dupont"

    def test_number(self):
        assert pdf._val(42) == "42"

    def test_zero_int(self):
        assert pdf._val(0) == "0"


class TestGeneratePdf:
    """Tests fonctionnels de generate_pdf — vérifie que le PDF est généré sans crash."""

    def _minimal_bilan(self):
        return {
            "id_chantier": "C001",
            "date_bilan": None,
            "parties_prenantes": [],
            "sous_traitants": [],
            "postes_perte": [],
            "postes_surbenefice": [],
            "travaux_internes": [],
        }

    def _minimal_chantier(self):
        return {
            "id_chantier": "C001",
            "intitule": None,
            "gestionnaire": None,
            "client": None,
            "secteur": None,
            "province": None,
        }

    def test_minimal_returns_bytes(self):
        result = pdf.generate_pdf(
            self._minimal_bilan(), self._minimal_chantier(), 0.0
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_minimal_starts_with_pdf_signature(self):
        result = pdf.generate_pdf(
            self._minimal_bilan(), self._minimal_chantier(), 0.0
        )
        assert result[:4] == b"%PDF"

    def test_no_logo_no_crash(self, monkeypatch):
        """Logo inexistant → pas de crash, on tombe dans le else."""
        monkeypatch.setattr(pdf, "LOGO_PATH", r"C:\NONEXISTENT\logo.png")
        result = pdf.generate_pdf(
            self._minimal_bilan(), self._minimal_chantier(), 0.0
        )
        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"

    def test_all_none_fields_no_crash(self):
        bilan = {
            "id_chantier": "C999",
            "date_bilan": None,
            "delai_soumission": None,
            "delai_contractuel": None,
            "delai_complementaire": None,
            "delai_reel": None,
            "montant_base_pv": None,
            "montant_decomptes_pv": None,
            "marge_devis": None,
            "marge_finale": None,
            "satisfaction_client": None,
            "niveau_qualite": None,
            "accidents_chantier": None,
            "travaux_non_satisfaisants": None,
            "ameliorations_qualite": None,
            "description_accidents": None,
            "ameliorations_securite": None,
            "commentaire_general": None,
            "notes_sous_traitants": None,
            "prix_de_revient": None,
            "rp_demandee": None,
            "rp_realisee": None,
            "rp_statut": None,
            "rd_a_demander": None,
            "rd_realisee": None,
            "rd_statut": None,
            "parties_prenantes": [],
            "sous_traitants": [],
            "postes_perte": [],
            "postes_surbenefice": [],
            "travaux_internes": [],
        }
        result = pdf.generate_pdf(bilan, self._minimal_chantier(), 0.0)
        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"

    def test_full_bilan_generates_large_pdf(self):
        """Bilan complet avec toutes les sections → PDF > 10 KB."""
        bilan = {
            "id_chantier": "C002",
            "date_bilan": "2024-06-30",
            "delai_soumission": 180,
            "delai_contractuel": 200,
            "delai_complementaire": 10,
            "delai_reel": 195,
            "unite_delai": "JC",
            "montant_base_pv": 500000.0,
            "montant_decomptes_pv": 25000.0,
            "marge_devis": 18.5,
            "marge_finale": 16.2,
            "prix_de_revient": 410000.0,
            "niveau_qualite": "Satisfaisant",
            "satisfaction_client": 4,
            "travaux_non_satisfaisants": "Aucun",
            "ameliorations_qualite": "Meilleure coordination équipes",
            "accidents_chantier": "Non",
            "description_accidents": None,
            "ameliorations_securite": "Formation mensuelle obligatoire",
            "commentaire_general": "Chantier bien conduit.\nBonne équipe.\nÀ reconduire.",
            "notes_sous_traitants": "Sous-traitants fiables dans l'ensemble.",
            "rp_demandee": "01/03/2024",
            "rp_realisee": "15/03/2024",
            "rp_statut": "Libérée",
            "rd_a_demander": "01/09/2024",
            "rd_realisee": None,
            "rd_statut": "En cours",
            "parties_prenantes": [
                {"role": "Maître d'ouvrage", "nom": "Commune de Test", "relation": "Très bonne", "evaluation": 5},
                {"role": "Architecte", "nom": "Cabinet XYZ", "relation": "Correcte", "evaluation": 3},
                {"role": "Bureau de contrôle", "nom": "Bureau ABC", "relation": "Bonne", "evaluation": 4},
            ],
            "sous_traitants": [
                {
                    "nom": "Electricité SA",
                    "respect_prix": 4, "respect_delais": 3,
                    "respect_securite": 5, "respect_qualite": 4,
                    "reactivite": 4, "communication": 3,
                },
                {
                    "nom": "Plomberie SPRL",
                    "respect_prix": 3, "respect_delais": 3,
                    "respect_securite": 4, "respect_qualite": 3,
                    "reactivite": 3, "communication": 4,
                },
            ],
            "postes_perte": [
                {"denomination": "Terrassement difficile", "prs": 30000.0, "pre": 38000.0},
                {"denomination": "Béton armé surcoût", "prs": 80000.0, "pre": 92000.0},
            ],
            "postes_surbenefice": [
                {"denomination": "Charpente métallique", "prs": 50000.0, "pre": 44000.0},
            ],
            "travaux_internes": [
                {"denomination": "Maçonnerie générale", "heures_soumission": 200.0, "heures_execution": 185.0},
                {"denomination": "Finitions intérieures", "heures_soumission": 80.0, "heures_execution": 95.0},
            ],
        }
        chantier = {
            "id_chantier": "C002",
            "intitule": "Construction école primaire — Test",
            "gestionnaire": "Martin",
            "client": "Commune de Test",
            "secteur": "Bâtiment",
            "province": "Hainaut",
        }
        result = pdf.generate_pdf(bilan, chantier, 487500.0)
        assert isinstance(result, bytes)
        assert len(result) > 10_000, (
            f"PDF trop petit : {len(result)} octets — sections manquantes ?"
        )

    def test_rp_rd_section_no_crash(self):
        """Bilan avec données RP/RD → pas de crash."""
        bilan = {
            **self._minimal_bilan(),
            "rp_demandee": "01/01/2024",
            "rp_realisee": "15/01/2024",
            "rp_statut": "Libérée",
            "rd_a_demander": "01/07/2024",
            "rd_realisee": None,
            "rd_statut": "En attente",
        }
        result = pdf.generate_pdf(bilan, self._minimal_chantier(), 0.0)
        assert result[:4] == b"%PDF"

    def test_sous_traitants_with_avg_row(self):
        """Sous-traitants → ligne de moyenne ajoutée sans crash."""
        bilan = {
            **self._minimal_bilan(),
            "sous_traitants": [
                {
                    "nom": "ST Test",
                    "respect_prix": 3, "respect_delais": 4,
                    "respect_securite": 5, "respect_qualite": 4,
                    "reactivite": 3, "communication": 4,
                }
            ],
        }
        result = pdf.generate_pdf(bilan, self._minimal_chantier(), 0.0)
        assert result[:4] == b"%PDF"

    def test_parties_prenantes_table(self):
        """Parties prenantes → table rendue sans crash."""
        bilan = {
            **self._minimal_bilan(),
            "parties_prenantes": [
                {"role": "MO", "nom": "X", "relation": "Bonne", "evaluation": 4}
            ],
        }
        result = pdf.generate_pdf(bilan, self._minimal_chantier(), 0.0)
        assert result[:4] == b"%PDF"

    def test_commentaire_multiline(self):
        """Commentaire multi-lignes → pas de crash."""
        bilan = {
            **self._minimal_bilan(),
            "commentaire_general": "Ligne 1\nLigne 2\nLigne 3",
        }
        result = pdf.generate_pdf(bilan, self._minimal_chantier(), 0.0)
        assert result[:4] == b"%PDF"
