# Audit etudecas - scripts, donnees, resultats

Date: 2026-07-01  
Racine analysee: `C:\dev\lca-simu`

## 1. Synthese courte

Le projet a maintenant une base fonctionnelle solide pour simuler, lotifier, auditer des chemins de lots, construire des vues HTML et comparer des risques. Les derniers runs de lotification sont coherents sur les controles critiques: references de lots, chronologie, transport, quantites de production et genealogie.

Le principal probleme n'est plus la faisabilite fonctionnelle, mais la gouvernance du code et des resultats:

- le depot melange encore code source, runs exploratoires, HTML lourds et milliers de CSV de sensibilite;
- `etudecas/simulation/sensibility` contient environ 86 GB et plusieurs milliers de runs complets;
- les deux gros moteurs restent trop volumineux: `run_first_simulation.py` environ 9 700 lignes, `build_supplychain_worldmap.py` environ 31 300 lignes;
- `unittest discover` ne voit que 4 tests alors que les tests explicites en lancent 26: la decouverte de tests n'est pas encore fiable;
- les outputs HTML embarquent trop de donnees dans un seul fichier, avec plusieurs cartes entre 136 et 151 MB.

Priorite recommandee: separer strictement `source`, `config`, `data reference`, `runs`, `archives`, puis sortir/compresser les gros resultats hors depot de travail courant.

## 2. Perimetre et commandes de verification

Controles effectues:

- inventaire des fichiers par extension et par dossier;
- tailles des principaux resultats;
- compilation Python: `python -m compileall -q etudecas`;
- tests explicites:
  `python -m unittest etudecas.simulation.test_kpi_engine etudecas.simulation.test_lot_ledger etudecas.simulation.test_lot_path_audit etudecas.simulation.test_lot_trace_payload etudecas.simulation.test_lot_trace_view_model etudecas.simulation.test_production_campaigns etudecas.simulation.test_factory_nervousness etudecas.knowledge_graph.test_excel_enrichment etudecas.visualization.maps.test_global_kpi_tree_payload etudecas.affichage_supply_script.test_lot_trace_config`;
- test discovery: `python -m unittest discover -s etudecas -p "test*.py"`;
- parsing JSON de tous les JSON sous `etudecas`;
- validation CSV approfondie sur les resultats recents/canoniques;
- lecture des summaries et audits de lotification;
- controle structurel des graphes d'entree simulation.

Limite explicite: la validation exhaustive ligne par ligne de tous les CSV n'est pas raisonnable en audit interactif, car le disque contient des dizaines de milliers de CSV, principalement dans `simulation/sensibility`. Meme le scan leger de toutes les premieres lignes CSV a depasse 5 minutes. C'est un probleme operationnel a corriger par organisation des artefacts.

## 3. Inventaire technique

Vue globale observee:

- environ 75 498 fichiers hors `.git`;
- `etudecas` pese environ 92.7 GB sur disque;
- `etudecas/simulation/sensibility` pese environ 86.2 GB;
- `etudecas/simulation/result` pese environ 6.4 GB;
- `supply_geo` pese environ 284 MB;
- le repo contient au moins 221 fichiers Python au total, dont 73 visibles sous `etudecas` via `rg`;
- JSON sous `etudecas`: 8 715 fichiers parses avec 0 erreur;
- CSV visibles via `rg` sous `etudecas`: 45 287 fichiers; scan disque precedent sous `sensibility`: environ 49 891 CSV;
- HTML visibles sous `etudecas`: 9 via `rg`; scan disque sous resultats: 19 HTML.

Repartition notable:

- `etudecas/simulation/sensibility`: environ 4 371 runs complets detectes par `first_simulation_summary.json`, total environ 85.4 GB;
- `etudecas/simulation/result`: environ 109 runs complets detectes, total environ 6.4 GB;
- `risk_amplitude_duration_sweep_5y`: 41 cas, environ 2.2 GB, 901 CSV;
- `_codex_lot_trace_5y_risk_portfolio`: environ 811 MB;
- `_codex_campaign_trace_5y`: environ 226 MB;
- `_codex_nervosite_usine_5y`: environ 75 MB.

## 4. Bons points

### Simulation et lotification

Le run `_codex_nervosite_usine_5y` est propre sur les controles critiques:

- 30 291 lots;
- 95 473 evenements de lots;
- 55 388 liens genealogiques;
- 1 136 campagnes de production;
- 4 campagnes/ordres reportes ou bloques;
- 0 reference de lot manquante;
- 0 erreur de chronologie;
- 0 mismatch de route transport apres alias canoniques;
- 0 quantite negative;
- 0 lot consomme au-dela de sa quantite initiale;
- 0 mismatch production plan vs lots produits.

Le diagnostic de nervosite usine ajoute une lecture utile:

- `M-1430 / item:268967`: nervosite haute, gros lots + reports intrants;
- `M-1810 / item:268091`: nervosite haute, cadence tres frequente;
- `SDC-1450 / item:773474`: nervosite moderee, reports/blocages ponctuels.

### Graphes d'entree

Le graphe principal:
`etudecas/simulation_prep/result/reference_baseline/_mrp_bom_tests/bom_weekly_mps_lotified_no_static_fallback_physical_floor.json`

est structurellement sain:

- 35 noeuds;
- 39 arcs;
- 0 doublon de noeud;
- 0 arc casse;
- typologie coherente: 1 client, 2 DC, 3 usines, 29 supplier DC.

La version enrichie Excel smoke garde la meme structure et ajoute `case_config`.

### Tests

Les tests explicites passent:

- 26 tests lances;
- 24 OK;
- 2 skipped.

La compilation Python de `etudecas` passe.

### Organisation recemment amelioree

Les wrappers de compatibilite sont maintenant propres:

- `etudecas/simulation/run_first_simulation.py` pointe vers `etudecas.simulation.engine.run_first_simulation`;
- `etudecas/affichage_supply_script/build_supplychain_worldmap.py` pointe vers `etudecas.visualization.maps.build_supplychain_worldmap`.

C'est une bonne direction: garder les anciens chemins comme wrappers, mais stabiliser une implementation canonique.

## 5. Problemes et risques

### P0 - Volume de resultats ingerable dans le workspace

`etudecas/simulation/sensibility` contient environ 86 GB et plusieurs milliers de sorties de simulation. Cela ralentit:

- les recherches;
- les scans CSV/JSON;
- les audits;
- les operations Git;
- les sauvegardes;
- la comprehension du repo.

Impact: tres fort. On ne peut plus traiter le repo comme un projet source classique.

Action recommandee:

- sortir `simulation/sensibility/*/cases/*/simulation_output` du depot source;
- garder seulement les summaries consolides, rapports et quelques runs canoniques;
- archiver le reste en `.zip`/parquet externe ou stockage d'artefacts;
- ajouter une regle `.gitignore` stricte pour les outputs massifs.

### P0 - HTML trop lourds

Plusieurs cartes HTML font entre 136 et 151 MB:

- `_codex_lot_trace_5y_risk_portfolio/maps/_codex_reorg_smoke.html`: 151.28 MB;
- `_codex_lot_trace_5y_risk_portfolio/maps/_codex_lot_trace_view_model_smoke.html`: 151.28 MB;
- `_codex_campaign_trace_5y/maps/supply_graph_campaign_trace_5y.html`: 150.59 MB;
- `_codex_lot_trace_5y_risk_portfolio/maps/supply_graph_lot_trace_5y_risk_portfolio.html`: 147.30 MB.

Cause probable: payloads JSON complets embarques dans le HTML, Plotly inline, duplication de donnees de lot trace et courbes.

Action recommandee:

- conserver le HTML comme shell leger;
- charger les payloads depuis `data/*.json` externes;
- compresser les gros payloads (`.json.gz`);
- paginer la liste de lots;
- charger les arbres de lot a la demande;
- limiter les runs smoke a des payloads reduits.

### P0 - Scripts centraux trop gros

Scripts identifies comme trop massifs:

- `etudecas/visualization/maps/build_supplychain_worldmap.py`: environ 31 325 lignes, 422 fonctions;
- `etudecas/simulation/engine/run_first_simulation.py`: environ 9 725 lignes, 105 fonctions;
- `etudecas/simulation_prep/prepare_simulation_graph.py`: environ 2 395 lignes;
- `etudecas/simulation/sensibility/run_supplier_parameter_sensitivity.py`: environ 1 781 lignes.

Impact:

- difficile a tester finement;
- difficile a relire;
- risque eleve de regressions UI/metier;
- cout d'entree important pour tout nouveau developpement.

Action recommandee:

- extraire progressivement des modules:
  - `simulation/engine/state.py`;
  - `simulation/engine/mrp.py`;
  - `simulation/engine/production.py`;
  - `simulation/engine/logistics.py`;
  - `simulation/engine/risks.py`;
  - `visualization/maps/panels/`;
  - `visualization/maps/charts/`;
  - `visualization/maps/lot_trace_ui.py`;
  - `visualization/maps/risk_ui.py`.

### P1 - Decouverte de tests incomplete

`python -m unittest discover -s etudecas -p "test*.py"` ne lance que 4 tests, alors que la commande explicite en lance 26.

Cause probable:

- certains dossiers ne sont pas decouverts comme packages;
- noms ou structure de tests non standard;
- imports dependant du chemin courant.

Action recommandee:

- ajouter/normaliser `__init__.py` la ou necessaire;
- definir une commande canonique `python -m unittest discover`;
- ou introduire `pytest` avec `python_files = test_*.py`;
- ajouter une CI locale simple qui lance exactement la commande canonique.

### P1 - Working tree tres sale

Le working tree contient de nombreux fichiers modifies, supprimes et non suivis:

- nouveaux modules `engine`, `lot_trace`, `visualization`, `knowledge_graph`;
- anciens fichiers supprimes;
- wrappers modifies;
- resultats HTML modifies;
- nombreux tests non suivis.

Impact:

- risque de perdre des changements;
- difficile de relire le diff;
- difficile de revenir proprement a un point de controle.

Action recommandee:

- faire un commit de consolidation source uniquement;
- separer un commit resultats/artefacts si necessaire;
- eviter de versionner les gros outputs;
- garder un tag/branche `audit-base` avant nettoyage.

### P1 - Resultats de risques encore difficiles a interpreter

Le sweep `risk_amplitude_duration_sweep_5y` contient 41 scenarios.

Observations:

- fill rate min: 0.485014;
- fill rate max: 1.0;
- un seul scenario degrade vraiment le service client: `pf268967_combined_extreme_180d_no_external`;
- la majorite des scenarios conserve le service a 100%;
- les impacts sont plutot visibles via couts, production, stocks, achats/appro fournisseur, reports intrants;
- cout total min: 45.23 M;
- cout total max: 98.45 M;
- scenario cout max: `pf268967_delay_plus_90_60d`;
- scenario service le plus degrade: `pf268967_combined_extreme_180d_no_external`.

Lecture metier:

- le reseau absorbe beaucoup via stocks et appro fournisseur;
- il ne faut pas presenter les risques uniquement par fill rate;
- il faut privilegier des KPI couples: service, backlog temporaire, cout total, cout appro fournisseur, zero-stock, reports intrants, stock consomme.

### P1 - Lot trace: limites metier attendues mais a mieux afficher

Audit lotification recent:

- 50 lots produits sur 1 134 ont seulement un amont stock initial pre-J0;
- 88 lots de reception lane sans parent transport sur 24 997;
- 1 355 lots client mixtes sur 2 586.

Ce n'est pas une incoherence technique, mais l'affichage doit les traiter explicitement:

- "origine stock initial non tracee";
- "reception agregat/carnet non trace";
- "lot client mixte: contribution du lot selectionne + autres parents".

### P2 - Donnees d'entree encore dispersees

Bon point: un debut de module `knowledge_graph` existe, avec enrichissement Excel.

Probleme restant:

- les donnees sources, enrichissements, graphes simulation-ready et resultats sont encore disperses;
- certains anciens dossiers (`supply_geo`, `donnees`, `scripts_geocodage`, `simulation_prep/result`) restent hors d'une convention unique;
- il n'y a pas encore de manifeste clair des datasets canoniques.

Action recommandee:

- instaurer une structure:
  - `data/raw/`;
  - `data/interim/`;
  - `data/processed/`;
  - `configs/cases/`;
  - `runs/<run_id>/`;
  - `artifacts/maps/`;
  - `reports/`;
- ajouter un `manifest.json` par run.

### P2 - Nommage et separation metier/UI

Le vocabulaire a progresse mais reste parfois heterogene:

- "risques simules" vs "criticite fournisseurs";
- "recours externe" renomme conceptuellement en appro fournisseur, mais verifier partout;
- "nervosite planning" vs "nervosite usine";
- "lot" vs "ordre" vs "campagne" vs "transport".

Action recommandee:

- ajouter un glossaire metier dans `etudecas/README.md` ou `docs/`;
- imposer les objets:
  - lot physique;
  - ordre de production;
  - campagne;
  - transport;
  - reception;
  - contribution de lot mixte.

## 6. Analyse des resultats recents

### Run `_codex_nervosite_usine_5y`

KPI:

- horizon: 1 825 jours;
- fill rate: 1.0;
- cout total: 68.74 M;
- lot trace active;
- 30 291 lots;
- 95 473 evenements de lots;
- 55 388 liens genealogiques;
- 1 194 evenements de planification production;
- 1 136 campagnes;
- 4 campagnes/ordres reportes ou bloques.

Lecture:

- le systeme sert toute la demande sur l'horizon;
- la lotification est coherente techniquement;
- la nervosite usine est bien presente mais pas uniquement sous forme de ruptures;
- `268967` est nerveux par gros lots et reports intrants;
- `268091` est nerveux par cadence tres frequente;
- `773474` est modere avec quelques blocages de limite hebdomadaire.

### Run `_codex_lot_trace_5y_risk_portfolio`

KPI:

- fill rate: 1.0;
- cout total: 68.95 M;
- lot trace: 30 836 lots, 96 973 evenements, 56 026 liens genealogiques.

Audit:

- pas d'erreurs critiques de genealogie;
- memes limites attendues autour du stock pre-J0 et des receptions non tracees.

### Sweep risques 5 ans

Lecture:

- 41 scenarios;
- seul le scenario extreme sans appro fournisseur degrade le service;
- les autres stressent surtout la structure de couts et stocks;
- c'est scientifiquement utile, mais l'onglet risques doit afficher des enveloppes et KPI multi-scenarios, pas seulement un scenario courant.

## 7. Recommandations prioritaires

### Priorite 1 - Nettoyage artefacts

1. Deplacer ou archiver `etudecas/simulation/sensibility/*/cases/*/simulation_output`.
2. Garder seulement:
   - summaries agreges;
   - reports;
   - un petit nombre de runs canoniques;
   - un manifest de reproduction.
3. Ajouter `.gitignore` pour:
   - `simulation/sensibility/**/simulation_output/`;
   - gros `maps/*.html` generes;
   - `__pycache__/`;
   - outputs smoke temporaires.

### Priorite 2 - Modularisation de la map

Extraire `build_supplychain_worldmap.py` par domaines:

- payload loading;
- charts Plotly;
- panels simulation;
- panels risques;
- panels criticite;
- lot trace viewer;
- HTML shell.

Objectif: aucun fichier UI > 2 000 lignes.

### Priorite 3 - Modularisation du moteur

Extraire de `run_first_simulation.py`:

- MRP/reappro;
- production/campagnes;
- lot ledger;
- stocks et flux;
- risques state-dependent;
- couts;
- exports.

Objectif: garder `run_first_simulation.py` comme orchestration, pas comme moteur monolithique.

### Priorite 4 - Tests et CI locale

1. Corriger la decouverte des tests.
2. Ajouter un script `python -m etudecas.tests.run_all` ou un `pytest.ini`.
3. Mettre une commande smoke:
   - compile;
   - tests unitaires;
   - run simulation 30 jours;
   - build map mini;
   - audit lots mini.

### Priorite 5 - Payloads externes pour HTML

Passer de:

- un HTML autonome de 150 MB

a:

- `map.html` shell leger;
- `data/simulation_payload.json.gz`;
- `data/lot_trace_index.json.gz`;
- chargement a la demande par lot/scenario.

### Priorite 6 - Gouvernance donnees

Creer un manifest par run:

```json
{
  "run_id": "...",
  "input_graph": "...",
  "config": "...",
  "days": 1825,
  "seed": 42,
  "outputs": {
    "summary": "...",
    "lot_audit": "...",
    "map": "..."
  },
  "retention": "keep_summary_only|keep_full|archive"
}
```

## 8. Conclusion

La partie simulation/lotification est maintenant suffisamment coherente pour continuer: les audits critiques passent et les objets metier principaux sont mieux separes. Le principal risque est que le projet devienne impossible a maintenir parce que les resultats exploratoires et les fichiers HTML massifs restent dans le meme espace que le code.

La prochaine etape la plus rentable est donc une consolidation structurelle:

1. archiver/nettoyer les outputs massifs;
2. rendre les tests decouvrables;
3. externaliser les payloads HTML;
4. continuer l'extraction du moteur et de la map en modules metier.

## 9. Actions appliquees apres audit

### Tests

La decouverte standard fonctionne maintenant avec:

```bash
python -m unittest discover -s etudecas -p "test*.py" -v
```

Resultat de verification: 28 tests detectes, 28 executes, 2 ignores explicitement car lourds.

### Artefacts sensibility

Une politique de retention est documentee dans:

- `etudecas/simulation/sensibility/ARTIFACT_POLICY.md`

Un outil d'inventaire et d'archivage sec est disponible:

- `etudecas/simulation/sensibility/cleanup_sensibility_outputs.py`

Verification a blanc sur les sorties existantes:

- 5 097 dossiers `simulation_output` detectes;
- environ 82,8 GB d'artefacts detectes;
- aucun deplacement massif execute par defaut.

Le script `run_supplier_parameter_sensitivity.py` n'ecrit plus les runs complets par defaut. Il expose maintenant:

- `--artifact-mode summary`;
- `--artifact-mode compact`;
- `--artifact-mode full`;
- `--keep-case-data` comme alias historique de `full`.

### HTML cartographiques

Un outil d'externalisation des payloads est disponible:

- `etudecas/visualization/maps/externalize_html_payload.py`

Le builder de cartes expose aussi l'option:

```bash
python etudecas/visualization/maps/build_supplychain_worldmap.py --externalize-payload
```

Verification a blanc sur une carte reelle:

- HTML initial: 147,30 MB;
- payload JSON extrait: 146,80 MB;
- HTML estime apres extraction: 0,49 MB.

Cette approche impose de servir la carte via HTTP, car le navigateur doit charger le JSON externe avec `fetch()`.
