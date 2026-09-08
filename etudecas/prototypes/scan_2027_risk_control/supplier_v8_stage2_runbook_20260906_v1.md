# Étape 2 V8 — lots, cascades, actions, courbes et livraison autonome

Cette étape est strictement additive. Elle lit la validation scientifique V7 et
la campagne V8, puis écrit uniquement dans les nouveaux chemins V8 listés
ci-dessous. Tant que la campagne V8 et sa finalisation ne sont pas complètes, le
watcher ne crée que son répertoire de supervision.

## Conditions obligatoires avant calcul aval

- validation V7 acceptée : 150 simulations indépendantes, 450 cas physiques ;
- campagne V8 finalisée : 90 références et 3 240 cas avec incident ;
- 18 voies exposées sur les 30 répétitions, avec la même fenêtre calendaire dans
  les trois niveaux ;
- aucun résultat d'incident utilisé pour sélectionner la fenêtre ;
- aucun incident qualité, capacité, disponibilité ou stock ;
- deux hypothèses séparées seulement : transport +120 jours, ou quantité
  normalement livrable multipliée par 0,5 pendant 42 jours.

Si une condition manque, l'étape s'arrête sans fabriquer de résultat.

## Commande d'armement

À lancer depuis `C:\dev\lca-simu-pr40`, après la revue finale des sources V8 :

```powershell
$env:PYTHONPATH = "C:\dev\lca-simu-pr40"
python -m etudecas.prototypes.scan_2027_risk_control.supplier_v8_stage2_watcher --repo "C:\dev\lca-simu-pr40" --v7-plan-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_plan_20260905_v7" --v7-run-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_run_20260905_v7" --trace-package-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v7_campaign_trace_package_20260905_v1" --bridge-json "C:\dev\lca-simu-pr40-validation-artifacts-20260726\validated_operating_points_v7_20260905_v1.json" --campaign-root "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v1" --results-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_results_20260906_v1" --stage1-supervision-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v1" --observed-2025-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\observed_2025_supply_bilan_20260901_v1" --lot-replay-root "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage2_lot_replays_20260906_v1" --qualification-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage2_physical_qualification_20260906_v1" --action-replay-root "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage2_action_replays_20260906_v1" --curves-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage2_nominal_curves_20260906_v1" --registry-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage2_incident_lot_registry_20260906_v1" --final-html "C:\dev\lca-simu-pr40-validation-artifacts-20260726\OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_V8_STAGE2_20260906_V1.html" --supervision-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage2_supervision_20260906_v1" --poll-seconds 30 --max-wait-hours 240 --startup-timeout-seconds 600 --detach
```

Les options `--v7-plan-dir` et `--v7-run-dir` gardent volontairement leur nom :
elles désignent la preuve scientifique V7 qui autorise les trois niveaux de
fonctionnement. La campagne, son registre d'exposition et tous les nouveaux
livrables sont V8.

## Résultats produits après validation

1. Courbes nominales issues des 30 situations normales signées : moyenne
   glissante 28 jours pour service et flux ; 7 jours pour stocks, encours,
   retard et contrainte.
2. Jusqu'à trois rejeux détaillés sans incident / avec incident, sans forcer un
   dossier qui ne serait pas retenu par les résultats signés.
3. Qualification explicite des étapes physiques réellement tracées ; les étapes
   absentes restent déclarées absentes.
4. Registre couvrant les 3 240 cas avec incident. Une généalogie détaillée n'est
   revendiquée que pour les dossiers rejoués.
5. Actions pilotables représentables : stock libre qualifié déjà prépositionné,
   réduction contractuelle du délai de futurs départs, ou réallocation vers une
   voie alternative déjà active. Les actions restent décidées avant simulation,
   donc en boucle ouverte.
6. Un HTML autonome en français, trois vues maximum, commençant par 338929.

## Limites à conserver dans la présentation

- Les incidents sont des hypothèses conditionnelles, pas des événements
  historiques ni des probabilités.
- Les conséquences évoluent avec les stocks, transits, production et retards du
  réseau ; la cause injectée reste exogène.
- Un contact physique tracé ne prouve pas automatiquement toute la causalité
  stock–MRP–production–service.
- Les identifiants de lots sont propres à chaque simulation ; on ne prétend pas
  retrouver le « même lot » entre deux calculs.
- Les clients restent agrégés. Aucun ROI, coût complet, jour récupéré ou lot
  sauvé nominativement n'est annoncé sans preuve correspondante.

## Contrôles de code

```powershell
python -m ruff format --check etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage2_common.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage2_pipeline.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage2_delivery.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage2_watcher.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage2_adapter.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage2_delivery.py
python -m ruff check etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage2_common.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage2_pipeline.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage2_delivery.py etudecas/prototypes/scan_2027_risk_control/supplier_v8_stage2_watcher.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage2_adapter.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage2_delivery.py
python -m pytest -q etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v7_stage2_delivery.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage2_adapter.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage2_delivery.py
```

