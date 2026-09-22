# Etudecas — commandes et effets

[Comprendre le code et les dossiers](README.md) · [Documentation par sujet](docs/README.md)

Ce guide sert à choisir une commande et à savoir ce qu'elle lit ou produit.
Les commandes se lancent depuis la racine du dépôt, qui contient `etudecas/`.

## Choisir une commande

| Besoin | Commande ou entrée | Effet |
|---|---|---|
| Comprendre l'organisation | [README.md](README.md) | Lecture du guide ; aucune exécution nécessaire. |
| Voir les commandes disponibles | `python etudecas/run_etudecas_pipeline.py --help` | Affiche l'aide. |
| Vérifier les fichiers et dépendances du pipeline | `python etudecas/run_etudecas_pipeline.py doctor` | Diagnostic ; ne lance pas la simulation. |
| Contrôler la documentation liée au code | `python -m etudecas.documentation check-all` | Contrôle les registres sans régénération. |
| Consulter une carte existante | [Accueil des résultats](index.html) | Ouvre les fichiers déjà produits. |
| Construire le graphe depuis les données source | `python etudecas/run_etudecas_pipeline.py graph` | Écrit le graphe enrichi et géocodé. |
| Préparer les entrées du moteur | `python etudecas/run_etudecas_pipeline.py prepare` | Écrit un graphe préparé ; ne correspond pas à toute la chaîne de reconstruction. |
| Recalculer et produire une carte | `python etudecas/run_etudecas_pipeline.py rebuild-map-5y` | Lance des calculs et crée un dossier de résultats ; détails ci-dessous. |

`rebuild-map-5y` utilise par défaut un graphe **déjà préparé** ; il ne rejoue
pas l'import des Excel. L'option `--refresh-input-graph` demande de reconstruire
son entrée. `graph`, `prepare`, `reference` et `all` couvrent les
étapes de construction correspondantes. Lire l'aide du sous-programme avant
de choisir une reconstruction. Le lanceur `launch_interactive_map.py` ouvre
un HTML existant avec l'API locale ; il n'est pas un constructeur de carte.

Les exemples de reconstruction qui suivent sont des opérations à lancer
volontairement, pas des étapes nécessaires pour lire le code.

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

La commande canonique exige Monte Carlo par défaut : 200 exécutions pour la
phase finale du profil retenu, précédées d'exécutions de sélection et, par
défaut, d'une campagne de sensibilité fournisseur. Ce nombre n'est donc pas
le total des calculs de la commande.
Pour produire explicitement une carte sans analyse d'incertitude, utiliser
`--no-require-montecarlo`. La [livraison du 18 septembre 2026](docs/MAP_DELIVERY.md)
documente ce perimetre, ses resultats et ses controles.

Equivalent Windows court :

```powershell
.\run_etudecas_active.cmd
```

Par defaut, cette commande :

- lance la simulation active lotifiee sur 5 ans ;
- construit également les scénarios de risque compagnons sélectionnés
  (`--state-dependent-scenarios all` par défaut) ;
- prépare les sensibilités puis la sélection et la phase finale Monte-Carlo,
  lorsque leurs artefacts locaux compatibles doivent être produits ;
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
python etudecas/run_etudecas_pipeline.py export-run --output-dir "CHEMIN_RESULTAT_EXISTANT" --input-graph "GRAPHE_EXACT_DU_RESULTAT.json"
```

Remplacer ces deux chemins par ceux du résultat concerné et de son manifeste
source. Sans `--input-graph`, la commande prend le graphe actif actuel, qui
peut être différent de celui d'un ancien calcul. Cet export écrit un package.

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

La commande opérationnelle `rebuild-map-5y` utilise le graphe actif lotifié
retenu et produit une nouvelle carte du calcul lancé. Pour reproduire une
livraison précise, reprendre son graphe et ses paramètres enregistrés ; le
nom de la commande ne garantit pas à lui seul une reproduction identique.
