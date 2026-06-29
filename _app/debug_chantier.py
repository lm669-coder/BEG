import os
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import database as db

    db.init_db()

    ID = "24039"

    bilan_id = db.bilan_exists_for_chantier(ID)
    print(f"Bilan existant pour {ID}: {bilan_id}")

    c = db.get_chantier(ID)
    print(f"\nChamps qui seraient préremplis:")
    print(f"  f_delai_soumission  = {c.get('delai_execution')}")
    print(f"  f_montant_base_pv   = {c.get('montant')}")
    print(f"  pp_client_nom       = {c.get('client')!r}")
    print(f"  f_prix_de_revient   = {c.get('prix_de_revient')}")
    print(f"  f_rp_demandee       = {c.get('rp_demandee')!r}")
    print(f"  f_rp_realisee       = {c.get('rp_realisee')!r}")
    print(f"  f_rp_statut         = {c.get('rp_statut')!r}")
    print(f"  f_rd_a_demander     = {c.get('rd_a_demander')!r}")
    print(f"  f_rd_realisee       = {c.get('rd_realisee')!r}")
    print(f"  f_rd_statut         = {c.get('rd_statut')!r}")

    pv = c.get("montant") or 0
    pr = c.get("prix_de_revient") or 0
    if pv and pr:
        marge = round((pv - pr) / pv * 100, 2)
        print(f"  f_marge_devis (calc) = {marge}%")

    dec = db.get_decomptes_totals(ID)
    print(f"  f_delai_complementaire = {dec['delai']}")
    print(f"  f_montant_decomptes_pv = {dec['montant']}")

    conn = db.get_conn()
    try:
        raw = conn.execute("SELECT id_chantier FROM chantiers WHERE id_chantier=?", (ID,)).fetchone()
        print(f"\nCorrespondance exacte en DB: {raw}")
        raw2 = conn.execute("SELECT id_chantier FROM chantiers WHERE id_chantier=?", (int(ID),)).fetchone()
        print(f"Correspondance int en DB: {raw2}")
    finally:
        conn.close()
