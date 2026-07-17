# Etudecas Operations

Ce guide decrit le chemin robuste pour reconstruire le run actif lotifie et la carte HTML autonome.

## Installation Minimale

Depuis la racine du repo :

```powershell
python -m pip install -r requirements-etudecas.txt
```

`requirements.txt` reste disponible pour les notebooks et prototypes, mais il est beaucoup plus large.

## Diagnostic

```powershell
python etudecas/run_etudecas_pipeline.py doctor
```

Le diagnostic verifie :

- les fichiers metier dans `etudecas/data/source/` ;
- les scripts principaux ;
- le graphe actif lotifie retenu ;
- les modules Python necessaires au pipeline.

## Reconstruction Complete Active

Commande canonique :

```powershell
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --open-map
```

`rebuild-active` reste un alias compatible.

Equivalent Windows court :

```powershell
.\run_etudecas_active.cmd
```

Par defaut, cette commande :

- lance la simulation active lotifiee sur 5 ans ;
- utilise le profil `compact` ;
- reconstruit la criticite fournisseur depuis ce run ;
- genere une carte HTML autonome compressee ;
- exporte un package de run generique dans `run/` ;
- verifie les fichiers principaux, la lotification et la taille de carte ;
- ecrit un rapport de pipeline.

Les resultats sont ecrits dans :

```text
etudecas/simulation/result/_reruns/active_mrp_physical_<timestamp>/
```

Les fichiers importants sont :

- `maps/*.html` : carte autonome ;
- `run/run_manifest.json` : point d'entree generique du run ;
- `run/artifact_index.json` : index logique des CSV/JSON lourds ;
- `run/nodes.json`, `run/flows.json`, `run/kpis.json` : contrat metier compact ;
- `summaries/first_simulation_summary.json` : KPI du run ;
- `reports/first_simulation_report.md` : rapport simulation ;
- `reports/pipeline_report.json` : statut de reconstruction ;
- `data/production_lot_events.csv` et `data/production_lot_genealogy.csv` : suivi de lots ;
- `reports/lot_path_audit.md` : audit des chemins de lots.

## Format De Run Generique

Chaque reconstruction operationnelle produit un dossier `run/` qui sert de
contrat stable pour la suite du projet. La carte peut encore utiliser les CSV
historiques, mais les nouveaux developpements doivent partir de ce package.

Exporter un ancien resultat sans relancer la simulation :

```powershell
python etudecas/run_etudecas_pipeline.py export-run --output-dir etudecas/simulation/result/_reruns/<run>
```

Valider un package de run :

```powershell
python etudecas/run_etudecas_pipeline.py validate-run --package-dir etudecas/simulation/result/_reruns/<run>/run
```

Le package ne duplique pas les gros CSV par defaut. Il stocke les petits objets
stables (`nodes`, `flows`, `kpis`) et des index vers les series, evenements,
lots, genealogie et diagnostics.

## Dry Run

Pour voir exactement ce qui serait lance sans creer de resultat :

```powershell
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --dry-run
```

## Options Utiles

```powershell
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --days 365
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --output-dir etudecas/simulation/result/_reruns/mon_run --overwrite
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --full-output
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --max-map-mb 50
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --with-montecarlo --montecarlo-runs 60
```

`--full-output` garde les CSV de debug lourds. Le mode standard doit rester `compact`.
`--with-montecarlo` lance une suite adaptative multi-profils et stocke les
resultats dans `<run>/montecarlo/selected/` pour l'onglet Incertitude de la carte.

## Rebuild Depuis Donnees Source

Pour reconstruire les graphes historiques depuis les XLSX :

```powershell
python etudecas/run_etudecas_pipeline.py all --with-5y
```

Le run operationnel recommande reste `rebuild-map-5y`, qui utilise le graphe actif lotifie valide et produit la carte la plus recente.
