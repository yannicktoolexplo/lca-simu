# Étape 2 V8 — runbook correctif V3 natif

Ce runbook est strictement additif. Il conserve les sources et runbooks V1/V2
comme preuves historiques, mais n'autorise pas leur exécution : leur lecteur de
dashboard attendait à tort un registre V4 avec une `design_seed`. Le registre
officiel est nativement V8, sans ce champ.

La campagne amont reste la relance officielle V8 V2. Tous les calculs aval,
rejeux, courbes, registres, fichiers de supervision et le HTML utilisent des
chemins V3 neufs. Aucun watcher ni aucune tâche ne sont armés par ce document.

## Conditions obligatoires

- validation V7 acceptée : 150 simulations indépendantes et 450 cas physiques ;
- campagne V8 V2 finalisée : 90 références et 3 240 cas avec incident ;
- registre natif V8 signé : 1 620 cellules uniques, 18 voies, trois niveaux et
  les 30 répétitions exactes ;
- pour chaque voie, même début et même fin de fenêtre dans les trois niveaux et
  les 30 répétitions ;
- première fenêtre admissible de 42 jours à partir de J180, avec quantité
  normalement livrable strictement positive et rapport inter-niveaux ≤ 1,5 ;
- aucun résultat d'incident utilisé pour choisir la fenêtre, aucune simulation
  supplémentaire de sélection et aucune projection vers une `design_seed` ;
- aucun incident qualité, capacité, disponibilité, stock ou risque endogène.

La fenêtre testée n'est ni la pire période, ni une saison moyenne, ni une
fréquence ou une probabilité d'incident fournisseur.

Les deux seuils visibles ont des rôles différents : 30/30 garantit un flux
comparable dans la fenêtre pour chaque simulation ; 24/30 est ensuite une règle
de détection d'effet, complétée par une borne basse d'IC95 strictement positive.
Le seuil 24/30 ne choisit pas la fenêtre.

## Commande V3 réservée au Planificateur Windows

À exécuter depuis `C:\dev\lca-simu-pr40` uniquement après revue et accord
explicite. Tant que `campaign_validation_v8.json` n'existe pas dans le dossier
de résultats finalisés, V3 sort immédiatement sans ouvrir `launch_progress.json`
ni les progressions des blocs. Le Planificateur Windows peut réessayer plus tard.
Après ce marqueur de fin, les lectures JSON demandent également le partage
lecture, écriture et suppression ; l'absence de lecture pendant la campagne
reste toutefois la protection principale contre les collisions `os.replace`.

```powershell
$env:PYTHONPATH = "C:\dev\lca-simu-pr40"
python -m etudecas.prototypes.scan_2027_risk_control.supplier_v8_stage3_watcher --repo "C:\dev\lca-simu-pr40" --v7-plan-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_plan_20260905_v7" --v7-run-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_run_20260905_v7" --trace-package-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v7_campaign_trace_package_20260905_v1" --bridge-json "C:\dev\lca-simu-pr40-validation-artifacts-20260726\validated_operating_points_v7_20260905_v1.json" --campaign-root "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2" --results-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_results_20260906_v2" --stage1-supervision-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2" --observed-2025-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\observed_2025_supply_bilan_20260901_v1" --lot-replay-root "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_lot_replays_20260906_v3" --qualification-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_physical_qualification_20260906_v3" --action-replay-root "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_action_replays_20260906_v3" --curves-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_nominal_curves_20260906_v3" --registry-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_incident_lot_registry_20260906_v3" --final-html "C:\dev\lca-simu-pr40-validation-artifacts-20260726\OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_V8_STAGE2_20260906_V3.html" --supervision-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_supervision_20260906_v3" --poll-seconds 60 --max-wait-hours 240 --startup-timeout-seconds 600 --detach
```

Les noms `--v7-plan-dir` et `--v7-run-dir` désignent volontairement la preuve
scientifique V7. Les chemins campagne/résultats désignent la campagne officielle
V8 V2. Tous les chemins de sortie propres à cette étape sont V3.

## Portée du HTML final

- trois vues maximum, avec 338929 comme point d'entrée agrégé ;
- indication explicite de la présence ou non d'une généalogie détaillée et
  d'une action pour 338929 ;
- si les lots, actions simulées ou actions refusées appartiennent à un autre
  dossier, affichage préalable de son identifiant, son fournisseur et son article ;
- jusqu'à trois dossiers signés, sans forcer 338929 ni un « top 3 » ;
- une cause exogène à la fois : les conséquences se propagent dans l'état du
  réseau, mais aucune combinaison multi-incidents n'est simulée ;
- aucune revendication de cascade dynamique complète stock–MRP–production–service ;
- actions décidées avant calcul, en boucle ouverte, sans régulation automatique ;
- aucun jour récupéré, coût complet, ROI ou lot sauvé annoncé sans preuve ;
- aucune mention client de « graine de conception », « forte exposition » ou
  « quantité planifiée médiane » héritée du lecteur V4.

## Contrôles avant toute autorisation

```powershell
python -m ruff format --check etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage3_dashboard.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage3_common.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage3_pipeline.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage3_delivery.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage3_watcher.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage3_dashboard.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage3_adapter.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage3_delivery.py
python -m ruff check etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage3_dashboard.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage3_common.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage3_pipeline.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage3_delivery.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage3_watcher.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage3_dashboard.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage3_adapter.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage3_delivery.py
python -m pytest -q etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v7_stage2_delivery.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage2_adapter.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage2_delivery.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage3_dashboard.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage3_adapter.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage3_delivery.py
```
