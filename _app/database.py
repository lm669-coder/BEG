import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beg_rmi.db")

_BILAN_CHILD_TABLES = (
    "bilan_parties_prenantes",
    "bilan_sous_traitants",
    "bilan_postes_perte",
    "bilan_postes_surbenefice",
    "bilan_travaux_internes",
)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS chantiers (
            id_chantier TEXT PRIMARY KEY,
            departement TEXT,
            gestionnaire TEXT,
            intitule TEXT,
            secteur TEXT,
            adresse TEXT,
            province TEXT,
            distance REAL,
            client TEXT,
            type_client TEXT,
            montant REAL,
            delai_execution INTEGER,
            date_marche_gagne TEXT,
            ordre_commencer TEXT,
            rp_demandee TEXT,
            rp_realisee TEXT,
            rd_a_demander TEXT,
            rd_realisee TEXT,
            rp_statut TEXT,
            rd_statut TEXT,
            n_cautionnement TEXT,
            organisme TEXT,
            montant_cautionnement REAL,
            document_rp TEXT,
            document_rd TEXT
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS decomptes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_chantier TEXT NOT NULL,
            n_decompte TEXT,
            intitule TEXT,
            montant REAL,
            delai_complementaire INTEGER
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS etats_avancement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num_chantier TEXT,
            lot TEXT,
            gestionnaire TEXT,
            nom_chantier TEXT,
            date_envoi TEXT,
            n_ea TEXT,
            montant_facture REAL
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS bilans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_chantier TEXT NOT NULL,
            date_bilan TEXT,
            delai_soumission INTEGER,
            delai_contractuel INTEGER,
            delai_complementaire INTEGER,
            delai_reel INTEGER,
            unite_delai TEXT DEFAULT 'JC',
            montant_base_pv REAL,
            montant_decomptes_pv REAL,
            marge_devis REAL,
            marge_finale REAL,
            niveau_qualite TEXT,
            satisfaction_client INTEGER,
            travaux_non_satisfaisants TEXT,
            ameliorations_qualite TEXT,
            accidents_chantier TEXT DEFAULT 'Non',
            description_accidents TEXT,
            ameliorations_securite TEXT,
            commentaire_general TEXT,
            notes_sous_traitants TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS bilan_parties_prenantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bilan_id INTEGER NOT NULL,
            role TEXT,
            nom TEXT,
            relation TEXT,
            evaluation INTEGER,
            FOREIGN KEY (bilan_id) REFERENCES bilans(id) ON DELETE CASCADE
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS bilan_sous_traitants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bilan_id INTEGER NOT NULL,
            ordre INTEGER,
            nom TEXT,
            respect_prix INTEGER,
            respect_delais INTEGER,
            respect_securite INTEGER,
            respect_qualite INTEGER,
            reactivite INTEGER,
            communication INTEGER,
            FOREIGN KEY (bilan_id) REFERENCES bilans(id) ON DELETE CASCADE
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS bilan_postes_perte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bilan_id INTEGER NOT NULL,
            denomination TEXT,
            prs REAL,
            pre REAL,
            FOREIGN KEY (bilan_id) REFERENCES bilans(id) ON DELETE CASCADE
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS bilan_postes_surbenefice (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bilan_id INTEGER NOT NULL,
            denomination TEXT,
            prs REAL,
            pre REAL,
            FOREIGN KEY (bilan_id) REFERENCES bilans(id) ON DELETE CASCADE
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS bilan_travaux_internes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bilan_id INTEGER NOT NULL,
            denomination TEXT,
            heures_soumission REAL,
            heures_execution REAL,
            FOREIGN KEY (bilan_id) REFERENCES bilans(id) ON DELETE CASCADE
        )
        """)

        # Migration : ajout colonnes (idempotent)
        for table, col_name, col_type in [
            ("bilans",    "rp_demandee",       "TEXT"),
            ("bilans",    "rp_realisee",       "TEXT"),
            ("bilans",    "rp_statut",         "TEXT"),
            ("bilans",    "rd_a_demander",     "TEXT"),
            ("bilans",    "rd_realisee",       "TEXT"),
            ("bilans",    "rd_statut",         "TEXT"),
            ("bilans",    "prix_de_revient",   "REAL"),
            ("chantiers", "prix_de_revient",   "REAL"),
            ("decomptes", "statut_accepte",    "INTEGER"),
        ]:
            try:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # column already exists

        conn.commit()
    finally:
        conn.close()


def get_chantier(id_chantier: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM chantiers WHERE id_chantier = ?", (str(id_chantier),)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_decomptes_totals(id_chantier: str) -> dict:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT SUM(montant) AS total_montant, SUM(delai_complementaire) AS total_delai "
            "FROM decomptes WHERE id_chantier = ? AND (statut_accepte = 1 OR statut_accepte IS NULL)",
            (str(id_chantier),)
        ).fetchone()
        return {
            "montant": float(row["total_montant"]) if row and row["total_montant"] else 0.0,
            "delai": int(row["total_delai"]) if row and row["total_delai"] else 0,
        }
    finally:
        conn.close()


def get_montant_facture(id_chantier: str) -> float:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT SUM(montant_facture) AS total FROM etats_avancement WHERE num_chantier = ?",
            (str(id_chantier),)
        ).fetchone()
        return float(row["total"]) if row and row["total"] else 0.0
    finally:
        conn.close()


def get_all_chantiers() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id_chantier, intitule, gestionnaire, client FROM chantiers ORDER BY CAST(id_chantier AS INTEGER) DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_bilans() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT b.id, b.id_chantier, b.date_bilan, b.marge_finale, b.satisfaction_client,
                   c.intitule, c.gestionnaire, c.client
            FROM bilans b
            LEFT JOIN chantiers c ON b.id_chantier = c.id_chantier
            ORDER BY b.date_bilan DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def bilan_exists_for_chantier(id_chantier: str) -> int | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT id FROM bilans WHERE id_chantier = ?", (str(id_chantier),)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def save_bilan(data: dict) -> int:
    conn = get_conn()
    try:
        c = conn.cursor()
        bilan_id = data.get("id")

        fields = (
            data["id_chantier"], data.get("date_bilan"),
            data.get("delai_soumission"), data.get("delai_contractuel"),
            data.get("delai_complementaire"), data.get("delai_reel"), data.get("unite_delai", "JC"),
            data.get("montant_base_pv"), data.get("montant_decomptes_pv"),
            data.get("marge_devis"), data.get("marge_finale"),
            data.get("niveau_qualite"), data.get("satisfaction_client"),
            data.get("travaux_non_satisfaisants"), data.get("ameliorations_qualite"),
            data.get("accidents_chantier", "Non"), data.get("description_accidents"),
            data.get("ameliorations_securite"), data.get("commentaire_general"),
            data.get("notes_sous_traitants"),
            data.get("rp_demandee"), data.get("rp_realisee"), data.get("rp_statut"),
            data.get("rd_a_demander"), data.get("rd_realisee"), data.get("rd_statut"),
            data.get("prix_de_revient"),
        )

        if bilan_id:
            c.execute("""
            UPDATE bilans SET
                id_chantier=?, date_bilan=?,
                delai_soumission=?, delai_contractuel=?, delai_complementaire=?, delai_reel=?, unite_delai=?,
                montant_base_pv=?, montant_decomptes_pv=?, marge_devis=?, marge_finale=?,
                niveau_qualite=?, satisfaction_client=?, travaux_non_satisfaisants=?, ameliorations_qualite=?,
                accidents_chantier=?, description_accidents=?, ameliorations_securite=?,
                commentaire_general=?, notes_sous_traitants=?,
                rp_demandee=?, rp_realisee=?, rp_statut=?,
                rd_a_demander=?, rd_realisee=?, rd_statut=?,
                prix_de_revient=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """, fields + (bilan_id,))
        else:
            c.execute("""
            INSERT INTO bilans (
                id_chantier, date_bilan,
                delai_soumission, delai_contractuel, delai_complementaire, delai_reel, unite_delai,
                montant_base_pv, montant_decomptes_pv, marge_devis, marge_finale,
                niveau_qualite, satisfaction_client, travaux_non_satisfaisants, ameliorations_qualite,
                accidents_chantier, description_accidents, ameliorations_securite,
                commentaire_general, notes_sous_traitants,
                rp_demandee, rp_realisee, rp_statut,
                rd_a_demander, rd_realisee, rd_statut,
                prix_de_revient
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, fields)
            bilan_id = c.lastrowid

        for table in _BILAN_CHILD_TABLES:
            c.execute(f"DELETE FROM {table} WHERE bilan_id = ?", (bilan_id,))

        for pp in data.get("parties_prenantes", []):
            c.execute(
                "INSERT INTO bilan_parties_prenantes (bilan_id,role,nom,relation,evaluation) VALUES (?,?,?,?,?)",
                (bilan_id, pp.get("role"), pp.get("nom"), pp.get("relation"), pp.get("evaluation"))
            )

        for i, st in enumerate(data.get("sous_traitants", [])):
            c.execute("""
            INSERT INTO bilan_sous_traitants
                (bilan_id,ordre,nom,respect_prix,respect_delais,respect_securite,respect_qualite,reactivite,communication)
            VALUES (?,?,?,?,?,?,?,?,?)
            """, (bilan_id, i + 1, st.get("nom"), st.get("respect_prix"), st.get("respect_delais"),
                  st.get("respect_securite"), st.get("respect_qualite"), st.get("reactivite"), st.get("communication")))

        for p in data.get("postes_perte", []):
            c.execute("INSERT INTO bilan_postes_perte (bilan_id,denomination,prs,pre) VALUES (?,?,?,?)",
                      (bilan_id, p.get("denomination"), p.get("prs"), p.get("pre")))

        for p in data.get("postes_surbenefice", []):
            c.execute("INSERT INTO bilan_postes_surbenefice (bilan_id,denomination,prs,pre) VALUES (?,?,?,?)",
                      (bilan_id, p.get("denomination"), p.get("prs"), p.get("pre")))

        for t in data.get("travaux_internes", []):
            c.execute(
                "INSERT INTO bilan_travaux_internes (bilan_id,denomination,heures_soumission,heures_execution) VALUES (?,?,?,?)",
                (bilan_id, t.get("denomination"), t.get("heures_soumission"), t.get("heures_execution"))
            )

        conn.commit()
        return bilan_id
    finally:
        conn.close()


def load_bilan(bilan_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM bilans WHERE id=?", (bilan_id,)).fetchone()
        if not row:
            return None
        bilan = dict(row)
        bilan["parties_prenantes"] = [dict(r) for r in conn.execute(
            "SELECT * FROM bilan_parties_prenantes WHERE bilan_id=? ORDER BY id", (bilan_id,)).fetchall()]
        bilan["sous_traitants"] = [dict(r) for r in conn.execute(
            "SELECT * FROM bilan_sous_traitants WHERE bilan_id=? ORDER BY ordre", (bilan_id,)).fetchall()]
        bilan["postes_perte"] = [dict(r) for r in conn.execute(
            "SELECT * FROM bilan_postes_perte WHERE bilan_id=? ORDER BY id", (bilan_id,)).fetchall()]
        bilan["postes_surbenefice"] = [dict(r) for r in conn.execute(
            "SELECT * FROM bilan_postes_surbenefice WHERE bilan_id=? ORDER BY id", (bilan_id,)).fetchall()]
        bilan["travaux_internes"] = [dict(r) for r in conn.execute(
            "SELECT * FROM bilan_travaux_internes WHERE bilan_id=? ORDER BY id", (bilan_id,)).fetchall()]
        return bilan
    finally:
        conn.close()


def delete_bilan(bilan_id: int) -> None:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM bilans WHERE id=?", (bilan_id,))
        conn.commit()
    finally:
        conn.close()
