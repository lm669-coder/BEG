# BEG RMI — Avancement développement

## Session 2026-06-25

### Ce qui a été fait

#### 1. Installation PyQt6 + matplotlib
```
python_portable\python.exe -m pip install PyQt6 matplotlib
```

#### 2. App PyQt6 créée (remplace Streamlit)

Fichiers créés :
```
_app/
├── app_qt.py               ← point d'entrée (QMainWindow + QTabWidget)
├── ui/
│   ├── __init__.py
│   ├── tab_formulaire.py   ← formulaire 8 sections (principal)
│   ├── tab_historique.py   ← table bilans + filtres + Modifier/Supprimer
│   ├── tab_dashboard.py    ← métriques + graphiques matplotlib
│   └── tab_import.py       ← import Excel (chantiers, EA, décomptes)
LANCER_QT.bat               ← lanceur double-clic
```

`database.py`, `pdf_export.py`, `import_data.py` inchangés.

#### 3. Bugs corrigés

| Bug | Cause | Fix |
|-----|-------|-----|
| Crash ajout poste | `clicked(bool)` passait `False` comme `denomination` à `QLineEdit(False)` | `connect(self.add_row)` → `connect(lambda: self.add_row())` × 4 |

#### 4. Cleanup qualité (/simplify — 4 agents parallèles)

| Catégorie | Fix appliqué |
|-----------|-------------|
| **Critique** | `import os` manquant dans `tab_formulaire.py` → crash PDF évité |
| **Correctness** | Signal `currentIndexChanged` reconnecté à chaque file-pick (×N fires) → connexion unique dans le constructeur |
| **Reuse** | `_remove()` copy-pastée 4× → consolidée dans `DynamicSection` avec hook `_on_removed()` ; `TravauxSection` l'override pour `_update_totals()` |
| **Dead code** | Supprimé : classe `DynamicRow`, helper `_btn`, `idx = len(self._rows)` |
| **Imports** | Supprimé : `QFormLayout`, `QSplitter`, `QSizePolicy` (non utilisés) |
| **Fiabilité** | `getattr(self, attr)` fragile → accès direct aux widgets RP |
| **Maintenabilité** | Magic indices `idx==1/2` → `hasattr(widget, "refresh")` générique |
| **Efficacité** | `_refresh_counts` : 3 connexions DB → 1 seule |

Skippés (trop invasifs) : `ExcelImportWidget`, `PP_FIXED_ROLES`, `_labeled_field`, `QSortFilterProxyModel`.

---

### État actuel

- App démarre sans erreur
- 4 onglets fonctionnels : Formulaire / Historique / Dashboard / Importer Excel
- Lookup chantier auto (délai, montants, RP, PR préremplis)
- Lignes dynamiques : postes perte/surb, travaux internes, sous-traitants, PP extra
- Calculs temps réel : respect délai, date fin théorique, total PV, coefficients, moyennes ST
- Enregistrer / PDF (dialog save) / Enregistrer+PDF / Supprimer avec confirmation
- Modifier depuis l'historique → navigation vers formulaire

### Pour lancer
```
double-clic LANCER_QT.bat
— ou —
python_portable\python.exe _app\app_qt.py
```

### Prochaine étape potentielle
- Compiler en `.exe` avec PyInstaller :
  ```
  python_portable\python.exe -m pip install pyinstaller
  python_portable\python.exe -m PyInstaller --onefile --windowed --name "BEG_RMI" --distpath P:\BEG_RMI _app\app_qt.py
  ```
- Tests utilisateur en cours (2026-06-25)
