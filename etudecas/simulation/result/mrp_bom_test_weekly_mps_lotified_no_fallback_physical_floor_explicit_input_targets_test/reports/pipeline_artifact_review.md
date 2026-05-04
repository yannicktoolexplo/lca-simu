# Revue scripts, JSON, sorties et carte HTML

## 1. Vue d'ensemble

La simulation active se lit comme une chaine:

1. Donnees Excel et graph initial.
2. Enrichissement du graph supply.
3. Preparation simulation.
4. Injection MRP, stocks, lots et ordres ouverts.
5. Simulation journaliere.
6. Generation des rapports, CSV et carte HTML.

La baseline active conservee est:

`etudecas/simulation/result/mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test`

Le JSON source retenu est:

`etudecas/simulation_prep/result/reference_baseline/_mrp_bom_tests/bom_weekly_mps_lotified_no_static_fallback_physical_floor.json`

## 2. Scripts actifs du pipeline

|Script|Role|Entrees principales|Sorties principales|Statut|
|---|---|---|---|---|
|`etudecas/run_etudecas_pipeline.py`|Entree unifiee du pipeline.|Graph, Excel, parametres CLI.|Graph prepare, baseline 1y/5y, simulation, carte, rerun baseline active.|Actif. Contient maintenant la commande securisee `active-mrp-physical`.|
|`etudecas/donnees/update_supply_graph_from_case_data.py`|Enrichit le graph avec les fichiers metier.|`Data_poc.xlsx`, `Fournisseur.xlsx`, `021081.xlsx`, `268191.xlsx`, `268967.xlsx`, `Extract_En_cours.xlsx`.|`supply_graph_poc.json`, rapports de mise a jour.|Actif pour constituer la structure supply.|
|`etudecas/scripts_geocodage/geocode_nodes_offline.py`|Ajoute les positions geographiques aux noeuds.|Graph supply.|Graph geocode.|Actif si on regenere depuis les donnees brutes.|
|`etudecas/simulation_prep/prepare_simulation_graph.py`|Transforme le graph en graph exploitable par le simulateur.|Graph geocode + donnees demande/prix.|Graph simulation-ready + rapports prep.|Actif pour preparer le modele.|
|`etudecas/simulation_prep/inject_mrp_seed_data_v2.py`|Injecte stocks MRP, politiques MRP, lots et securites.|`Stocks_MRP.xlsx`, graph prepare.|Graph MRP/lots.|Actif. Version a conserver.|
|`etudecas/simulation/baselines/rebuild_real_demand_target_baseline.py`|Construit une baseline real demand/service.|Graph prepare.|Graph baseline demande/service.|Actif dans l'ancien pipeline reference.|
|`etudecas/simulation/baselines/rebuild_mrp_lot_policy_baseline.py`|Ajoute/recalibre les politiques MRP et lots.|Graph MRP/lots.|Graph recalibre + run possible.|Actif dans l'ancien pipeline reference.|
|`etudecas/simulation/run_first_simulation.py`|Moteur principal de simulation journaliere.|JSON source + scenario.|CSV journaliers, rapports, summaries, carte si activee.|Script central.|
|`etudecas/affichage_supply_script/build_supplychain_worldmap.py`|Construit la carte HTML interactive.|JSON + CSV de simulation.|HTML autonome avec graphes Plotly.|Actif pour la restitution.|

Commande officielle de rerun non destructif:

```powershell
python etudecas/run_etudecas_pipeline.py active-mrp-physical
```

Par defaut, cette commande ecrit dans un dossier timestamp sous `etudecas/simulation/result/_reruns/` et ne touche pas la baseline validee. Pour verifier sans lancer la simulation:

```powershell
python etudecas/run_etudecas_pipeline.py active-mrp-physical --dry-run
```

Un rerun ecrit aussi un `run_manifest.json` dans son dossier de sortie avec le JSON source, les parametres et la commande exacte.

Verification effectuee: avec la regle MRP validee embarquee dans la commande (`base-stock` global a 0, overrides a 1 sur les paires M-1430/M-1810 retenues), les KPI et CSV dynamiques principaux sont identiques a la baseline active.

## 3. Scripts utiles mais hors baseline active

|Script/famille|Utilite|Statut recommande|
|---|---|---|
|`etudecas/simulation/analysis/*.py`|Analyses, revues d'hypotheses, reconciliations, risk proxy.|A garder comme boite a outils, mais hors pipeline standard.|
|`etudecas/simulation/sensibility/*.py`|Etudes de sensibilite et campagnes de stress.|A garder si on veut relancer des analyses scenario.|
|`etudecas/simulation/scenarios/*.py`|Runs de scenarios specifiques.|A garder en option, mais ne pas melanger avec les baselines retenues.|
|`etudecas/simulation/montecarlo/run_montecarlo_analysis.py`|Analyse Monte Carlo.|Optionnel, non utilise dans la baseline active.|
|`etudecas/SC_analysis/*.py` et `etudecas/SC_first_analysis/*.py`|Analyses exploratoires historiques.|A archiver ou documenter comme POC.|
|`etudecas/Prediction/run_prediction_poc.py`|POC prediction, hors simulation supply actuelle.|A garder separe de la baseline supply.|

## 4. Scripts a nettoyer ou deprecier

|Script|Pourquoi|Action conseillee|
|---|---|---|
|`etudecas/simulation_prep/inject_mrp_seed_data.py`|Ancienne version remplacee par `inject_mrp_seed_data_v2.py`.|Deprecier ou supprimer apres verification Git.|
|`etudecas/simulation/run_first_simulation_git6066_repeat.py`|Copie historique du simulateur.|Supprimer ou archiver si plus aucune comparaison n'en depend.|
|Scripts d'analyse non relies a un rapport actif|Peuvent etre utiles, mais le lien avec la baseline est parfois implicite.|Ajouter un README dans `simulation/analysis` si on les conserve.|

## 5. JSON source actif

Fichier:

`etudecas/simulation_prep/result/reference_baseline/_mrp_bom_tests/bom_weekly_mps_lotified_no_static_fallback_physical_floor.json`

Contenu utile:

- `nodes`: 35 noeuds supply.
- `edges`: 39 flux source -> destination.
- `items`: 26 articles.
- `scenarios`: 1 scenario, `scn:BASE`.
- `meta.opening_open_orders.rows`: 88 ordres ouverts injectes depuis `Extract_En_cours.xlsx`.
- `meta.mrp_seed`: trace d'injection des stocks MRP.
- `meta.mrp_lot_policy_rebuild`: politiques lots, capacites, overrides et hypotheses.
- `scenarios[0].economic_policy`: couts, external procurement et regles economiques.
- `scenarios[0].lead_time_policy`: politique de delais.
- `scenarios[0].initialization_policy`: etat initial et pipeline.

Ce que le JSON ne contient pas:

- Il ne contient pas les series simulees jour par jour.
- Il ne contient pas les receptions effectives realisees.
- Il ne contient pas les graphes HTML.
- Il ne contient pas les KPI calcules du run.

Conclusion: le JSON est la source de verite statique et politique. Les CSV sont la source de verite dynamique.

## 6. CSV de simulation actifs

|Fichier|Role|Utilisation carte / analyse|
|---|---|---|
|`first_simulation_daily.csv`|KPI globaux jour par jour: demande, servi, backlog, couts, stocks.|Arbre KPI global et tendances management.|
|`mrp_trace_daily.csv`|Trace decisionnelle MRP par jour, site, item.|Onglets pilotage MRP, risque, trace, justification des ordres.|
|`mrp_orders_daily.csv`|Carnet d'ordres: ordre passe, envoi, arrivee previsionnelle, arrivee effective.|Carnet d'ordres, delais, distribution des delais, audit des commandes.|
|`production_input_stocks_daily.csv`|Stocks intrants en usine par jour.|Graphes de stock matiere et comparaison cible/securite.|
|`production_input_consumption_daily.csv`|Consommation intrants par la production.|Bilan matiere, coherence BOM/production.|
|`production_input_replenishment_arrivals_daily.csv`|Arrivees intrants a destination.|Courbes receptions, MRP flux entrant.|
|`production_input_replenishment_shipments_daily.csv`|Expeditions vers les sites producteurs.|Courbes expedition vs reception.|
|`production_output_products_daily.csv`|Production et stock produit fini/semi-fini.|Graphes production, stock produit, Gantt lots.|
|`production_constraint_daily.csv`|Plan de production, lots, capacite, intrants bloquants.|KPI alignement production, contraintes, Gantt.|
|`production_supplier_shipments_daily.csv`|Expeditions fournisseurs avec lead time simule.|Graphes fournisseurs, edges, distribution delais.|
|`production_supplier_stocks_daily.csv`|Stocks fournisseur simules.|Graphes stock fournisseur et diagnostic zero stock.|
|`production_supplier_capacity_daily.csv`|Capacite fournisseur utilisee/restante.|Graphes capacite fournisseur et criticite locale.|
|`production_dc_stocks_daily.csv`|Stocks centres de distribution.|Graphes DC.|
|`production_demand_service_daily.csv`|Demande, servi, backlog par PF.|Service client et disponibilite produit.|
|`supplier_local_criticality_ranking.csv`|Score local fournisseur.|Classement fournisseurs critiques.|
|`assumptions_ledger.csv`|Journal des hypotheses et overrides.|Audit.|
|`production_input_stocks_pivot.csv`|Vue pivot stocks intrants.|Lecture rapide/export externe.|

## 7. Rapports et summaries

|Artefact|Role|
|---|---|
|`summaries/first_simulation_summary.json`|Synthese machine-readable: politiques, compteurs, KPI, couts, consistance economique.|
|`summaries/supplier_local_criticality_summary.json`|Synthese machine-readable des fournisseurs critiques.|
|`reports/first_simulation_report.md`|Rapport humain du run.|
|`reports/baseline_integrity_diagnostic.md`|Diagnostic complet de coherence baseline, donnees, stocks, ordres, fournisseurs.|
|`reports/mrp_safety_arrival_compliance.*`|Controle arrivees MRP vs securite. Attention: ne prouve pas que le stock physique reste toujours au-dessus de la cible.|
|`reports/mrp_safety_stock_reference.csv`|Reference de stock/securite utilisee par le run.|
|`reports/safety_target_comparison.csv`|Comparaison des cibles de securite.|

## 8. Carte HTML et graphes

Fichier:

`maps/supply_graph_mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test.html`

Nature:

- HTML autonome d'environ 16 MB.
- Embarque le graph, les series et les figures Plotly.
- N'est pas source de verite primaire; c'est une restitution interactive.
- Ne depend plus de `plots/*.png`.

Graphes et vues principales:

- Carte supply: noeuds, flux, roles.
- Noeuds usine: stocks intrants, stocks/production produits, Gantt lots, contraintes, pilotage MRP, carnet.
- Noeuds fournisseurs: stock fournisseur, expeditions, capacite, delais, distribution des delais.
- Edges/flux: expeditions vs receptions, distribution des delais, delai previsionnel en repere vertical, carnet associe.
- KPI global: arbre KPI management, formules, courbes principales/secondaires.
- Modele: explication des equations et variables par type de noeud/flux.

Points de vigilance:

- Le Gantt est une visualisation de lots lances. Il ne represente pas encore un ordonnancement atelier complet avec calendriers, equipes, changements de format et disponibilites machines fines.
- `build_supplychain_worldmap.py` est tres monolithique: donnees, HTML, CSS et JS sont dans un seul fichier. C'est pratique pour generer un HTML autonome, mais difficile a maintenir.
- Les ordres MRP bruts sont des evenements de simulation. Pour lecture industrielle, lire les commandes consolidees semaine/flux/item.

## 9. Ce qui est clair aujourd'hui

- Les sources dynamiques sont identifiables: les CSV de `data/`.
- Le JSON source actif est unique.
- Les baselines intermediaires MRP ont ete nettoyees.
- Le vocabulaire visible utilise `flux` / `ordre_flux`; `lane` reste interne.
- La carte active est autosuffisante.

## 10. Ce qui reste a ameliorer

1. Deprecier ou supprimer `inject_mrp_seed_data.py` si `inject_mrp_seed_data_v2.py` est bien la seule version utilisee.
2. Supprimer ou archiver `run_first_simulation_git6066_repeat.py` si ce snapshot n'est plus utile.
3. Decouper `build_supplychain_worldmap.py` en modules: preparation donnees, model panel, KPI, templates HTML/JS.
4. Enrichir le `run_manifest.json` avec des hash des fichiers principaux.
5. Garder une convention stricte: JSON = modele statique, CSV = verite dynamique, HTML = restitution.

## 11. Decision recommandee

La baseline active est maintenant relancable par commande unique sans ecraser l'etat valide. La prochaine vraie etape est de simplifier la maintenance: deprecier les anciens scripts et decouper la generation HTML, devenue trop monolithique.
