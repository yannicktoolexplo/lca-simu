# Étape 2 V7 — exécution additive après validation complète de l’étape 1

## But et règle d’arrêt

Cette étape construit le livrable client en trois vues sans modifier ni remplacer les sorties V7 amont. Elle peut être armée pendant l’étape 1, mais elle ne crée avant son acceptation complète que son propre répertoire de supervision.

- Si la décision V7 signée est négative, le watcher s’arrête avec le code `3` et ne lance aucun calcul aval.
- Si l’étape 1 reste incomplète au-delà de la limite, il s’arrête avec le code `4` et reste reprenable.
- Toute modification du code inventorié, du reçu amont signé ou d’une preuve déjà publiée provoque un arrêt fail-closed.
- Une relance emploie exactement la même commande. Les sorties complètes sont revalidées; les sorties partielles appartenant à l’étape 2 sont reprises ou archivées dans leur seul répertoire.

## Sources officielles, en lecture seule

Racine des preuves : `C:\dev\lca-simu-pr40-validation-artifacts-20260726`

- plan de validation : `supplier_fixed_triplet_confirmation_plan_20260905_v7`
- résultat de validation : `supplier_fixed_triplet_confirmation_run_20260905_v7`
- traces de campagne : `supplier_v7_campaign_trace_package_20260905_v1`
- points de fonctionnement : `validated_operating_points_v7_20260905_v1.json`
- campagne : `supplier_operating_point_full_campaign_v7_20260905_v1`
- résultats : `supplier_operating_point_full_campaign_v7_results_20260905_v1`
- supervision du relais étape 1 : `supplier_operating_point_full_campaign_v7_supervision_20260905_v1`
- contexte observé 2025 facultatif : `observed_2025_supply_bilan_20260901_v1`

Le watcher n’utilise le résultat confirmatoire final que lorsque `validation_result.json` prouve 150 simulations indépendantes et 450 cas acceptés. Un checkpoint intermédiaire n’est jamais une preuve de décision.

## Sorties propres à l’étape 2

Ces chemins sont nouveaux et séparés des sources :

- lots détaillés : `supplier_v7_stage2_lot_replays_20260906_v1`
- qualification physique : `supplier_v7_stage2_physical_qualification_20260906_v1`
- actions en boucle ouverte : `supplier_v7_stage2_action_replays_20260906_v1`
- courbes nominales : `supplier_v7_stage2_nominal_curves_20260906_v1`
- registre incidents et lots : `supplier_v7_stage2_incident_lot_registry_20260906_v1`
- supervision : `supplier_v7_stage2_supervision_20260906_v1`
- livrable autonome : `OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_V7_STAGE2_20260906_V1.html`
- manifeste du livrable : même chemin HTML suivi de `.manifest.json`

## Commande unique à exécuter seulement après GO d’audit

Ne pas lancer cette commande tant que la revue indépendante n’a pas rendu GO.

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_v7_stage2_watcher --repo "C:\dev\lca-simu-pr40" --v7-plan-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_plan_20260905_v7" --v7-run-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_run_20260905_v7" --trace-package-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v7_campaign_trace_package_20260905_v1" --bridge-json "C:\dev\lca-simu-pr40-validation-artifacts-20260726\validated_operating_points_v7_20260905_v1.json" --campaign-root "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v7_20260905_v1" --results-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v7_results_20260905_v1" --stage1-supervision-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v7_supervision_20260905_v1" --observed-2025-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\observed_2025_supply_bilan_20260901_v1" --lot-replay-root "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v7_stage2_lot_replays_20260906_v1" --qualification-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v7_stage2_physical_qualification_20260906_v1" --action-replay-root "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v7_stage2_action_replays_20260906_v1" --curves-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v7_stage2_nominal_curves_20260906_v1" --registry-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v7_stage2_incident_lot_registry_20260906_v1" --final-html "C:\dev\lca-simu-pr40-validation-artifacts-20260726\OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_V7_STAGE2_20260906_V1.html" --supervision-dir "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v7_stage2_supervision_20260906_v1" --poll-seconds 30 --max-wait-hours 240 --startup-timeout-seconds 600 --detach
```

Le retour `detached_ready` n’est accepté que si le fils est encore vivant, détient son verrou, a revalidé l’inventaire, maintient Windows éveillé et prouve qu’aucun moteur n’a démarré avant ce reçu. Un reçu invalide ou un délai de démarrage dépassé arrête le fils créé par la commande.

## Ce que le pipeline exécute après acceptation signée

1. Revalide les 450 cas confirmatoires et la matrice 90 références + 3 240 cas avec incident.
2. Publie un reçu amont immuable, puis le revalide avant chaque étape et le lie au manifeste final.
3. Construit 108 courbes nominales depuis les 30 premiers scénarios V7 : MM28 pour service et flux, MM7 pour stocks, encours, retard et signal de contrainte.
4. Exécute au plus trois comparaisons détaillées sans incident / incident, exactement celles du plan signé; aucun dossier n’est ajouté pour rendre le résultat spectaculaire.
5. Qualifie la propagation physique et consolide les traces de lots disponibles, sans annoncer une causalité dynamique complète lorsque la preuve manque.
6. Teste seulement les leviers V4 éligibles : stock libre qualifié déjà prépositionné, réduction contractuelle du délai des futurs départs, réallocation vers une voie alternative déjà active.
7. Produit un HTML autonome français, sans URL, script ou style externe, avec exactement trois vues.

## Lecture métier imposée

- Aucun incident qualité ou quarantaine.
- Aucune capacité, disponibilité fournisseur ou disponibilité produit fini inventée.
- Les deux incidents sont des hypothèses conditionnelles séparées : retard de transport de 120 jours; quantité normalement livrable multipliée par 0,5 pendant 42 jours.
- Il n’y a pas de combinaison de plusieurs incidents dans un même cas.
- Les conséquences dépendent de l’état évolutif du réseau; la génération des incidents reste exogène.
- Les actions sont en boucle ouverte, décidées avant simulation; il ne s’agit pas de régulation automatique.
- Les clients sont agrégés et les lots sont simulés.
- Aucun coût, ROI, jour récupéré ou lot sauvé nominativement n’est annoncé sans preuve disponible.
- Les valeurs observées de CA et de stock comptable ne sont attribuées à aucun fournisseur, commande, lot ou cause; leur devise n’est pas renseignée.
- La probabilité fournisseur industrielle reste à calibrer à partir des commandes promises et reçues réelles.

## Contrôles avant GO

Depuis `C:\dev\lca-simu-pr40` :

```powershell
python -m ruff format --check etudecas/prototypes/scan_2027_risk_control/supplier_v7_stage2_common.py etudecas/prototypes/scan_2027_risk_control/supplier_v7_stage2_curves.py etudecas/prototypes/scan_2027_risk_control/supplier_v7_stage2_pipeline.py etudecas/prototypes/scan_2027_risk_control/supplier_v7_stage2_delivery.py etudecas/prototypes/scan_2027_risk_control/supplier_v7_stage2_watcher.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v7_stage2_delivery.py
python -m ruff check etudecas/prototypes/scan_2027_risk_control/supplier_v7_stage2_common.py etudecas/prototypes/scan_2027_risk_control/supplier_v7_stage2_curves.py etudecas/prototypes/scan_2027_risk_control/supplier_v7_stage2_pipeline.py etudecas/prototypes/scan_2027_risk_control/supplier_v7_stage2_delivery.py etudecas/prototypes/scan_2027_risk_control/supplier_v7_stage2_watcher.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v7_stage2_delivery.py
python -m pytest -q etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v7_stage2_delivery.py
```

Le HTML final doit être ouvert directement depuis le disque. Les trois onglets, leurs graphiques, les sélecteurs, le détail J0/fenêtre de 42 jours et la pagination des lots doivent fonctionner sans réseau.

