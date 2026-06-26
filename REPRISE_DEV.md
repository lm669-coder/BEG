# Reprise développement BEG RMI — jeudi 2026-06-26

## Décision prise
Réécrire l'app en **PyQt6** (application de bureau Windows native, sans navigateur).
- `database.py` et `pdf_export.py` restent identiques (pas de dépendance Streamlit)
- `import_data.py` reste identique
- `app.py` (Streamlit) sera **remplacé** par une nouvelle app PyQt6

---

## État du projet aujourd'hui (2026-06-19)

### Ce qui tourne déjà
- **`LANCER.exe`** — lanceur C compilé avec MinGW qui démarre `streamlit.exe` et ouvre le navigateur quand le port 8501 est prêt. Fonctionne.
- **`_app/.streamlit/config.toml`** — config streamlit correcte (bind 127.0.0.1:8501, pas de stats)
- **SQLite `beg_rmi.db`** — 82 chantiers + 1615 lignes EA importés, prêt

### Problème VPN (à garder en tête)
- Le disque `P:\` est un réseau → streamlit démarre en **30-60 secondes** à cause d'opérations git lentes
- C'est pourquoi on passe à PyQt6 (plus besoin du navigateur)

### Fichiers clés
```
P:\BEG_RMI\
├── LANCER.exe              ← lanceur Streamlit (garde-le en backup)
├── LANCER.bat              ← ancien, ne fonctionne pas bien sur VPN
├── python_portable\        ← Python 3.13 portable avec tous les packages
│   └── Scripts\streamlit.exe
├── _app\
│   ├── app.py              ← UI Streamlit ACTUELLE (garder comme référence)
│   ├── database.py         ← SQLite wrapper (RÉUTILISER tel quel)
│   ├── pdf_export.py       ← Génération PDF ReportLab (RÉUTILISER tel quel)
│   ├── import_data.py      ← Import Excel (RÉUTILISER tel quel)
│   ├── .streamlit\config.toml
│   └── beg_rmi.db          ← base de données SQLite
└── Données\                ← fichiers Excel source
```

---

## App PyQt6 à créer

### Architecture cible
```
_app/
├── app_qt.py           ← point d'entrée PyQt6 (nouveau)
├── ui/
│   ├── main_window.py  ← QMainWindow + QTabWidget
│   ├── tab_formulaire.py
│   ├── tab_historique.py
│   ├── tab_dashboard.py
│   └── tab_import.py
├── database.py         ← inchangé
├── pdf_export.py       ← inchangé
└── import_data.py      ← inchangé
```

### Tabs à implémenter (comme Streamlit actuel)
1. **📝 Formulaire** (tab principal)
   - Section 1 : Identification (ID chantier → lookup auto nom/gestionnaire/client/montant)
   - Section 2 : Parties prenantes (Client, Architecte, BE fixes + lignes dynamiques extra)
   - Section 3 : Performance (délais + budget + PR + marges + RP)
   - Section 4 : Rendements (postes perte/surb dynamiques + travaux internes dynamiques)
   - Section 5 : Qualité (textes libres + satisfaction /5)
   - Section 6 : Sécurité (accidents oui/non + description + améliorations)
   - Section 7 : Sous-traitants (lignes dynamiques — 6 critères /5 + moyenne auto)
   - Section 8 : Commentaire général
   - Boutons : Enregistrer | Générer PDF | Enregistrer + PDF

2. **📋 Historique** — QTableWidget avec filtre gestionnaire + recherche texte, bouton Modifier

3. **📊 Dashboard** — graphiques matplotlib (satisfaction / marge par chantier)

4. **⬆ Import Excel** — sélecteur de fichier + feuille + import Suivi RP&RD / INPUT-EA

### Widgets PyQt6 recommandés
- Lignes dynamiques → `QScrollArea` + layout vertical avec bouton ➕/✕ par ligne
- Tableaux → `QTableWidget`
- Scores /5 → `QSpinBox(1..5)` ou étoiles custom
- Textes longs → `QTextEdit`
- Dates → `QDateEdit`
- Lookup chantier → `QLineEdit` + `QLabel` pour afficher info auto
- PDF → `pdf_export.generate_pdf(data, ch, montant_facture)` → sauvegarder dans `PDFs/`

### Couleur BEG
```python
BEG_BLUE = "#1a3a5c"
```

### Installer PyQt6
```
P:\BEG_RMI\python_portable\python.exe -m pip install PyQt6
```
(était en cours d'installation le 2026-06-19, peut nécessiter retry sur VPN)

---

## Commande pour compiler l'exe final
```
P:\BEG_RMI\python_portable\python.exe -m PyInstaller ^
    --onefile --windowed --name "BEG_RMI" ^
    --distpath P:\BEG_RMI ^
    _app\app_qt.py
```

---

## Pour tester sans compiler
```bat
P:\BEG_RMI\python_portable\python.exe P:\BEG_RMI\_app\app_qt.py
```

---

## Référence : signature database.py
```python
db.init_db()
db.get_chantier(id_chantier)          # → dict ou None
db.get_montant_facture(id_chantier)   # → float
db.get_decomptes_totals(id_chantier)  # → {"delai": int, "montant": float}
db.get_all_bilans()                   # → list[dict]
db.load_bilan(bilan_id)               # → dict complet avec listes
db.save_bilan(data_dict)              # → new_id (int)
db.delete_bilan(bilan_id)
```

## Référence : signature pdf_export.py
```python
pdf_bytes = pdf_export.generate_pdf(data, chantier_info, montant_facture)
# → bytes à écrire dans un fichier .pdf
```
