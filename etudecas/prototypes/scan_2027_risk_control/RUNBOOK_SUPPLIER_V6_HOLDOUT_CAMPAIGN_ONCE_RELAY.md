# Relais V6 holdout → campagne — mode opératoire court

## Rôle et garanties

Ce relais additif attend le `status.json` canonique de la supervision de
calibration V6. Une simple copie auto-cohérente ne suffit pas : son empreinte
`status_signature` doit être valide, son `contract_signature` doit être celle du
`contract.json` signé placé à côté, et les chemins/workers/producteurs de ce
contrat doivent correspondre à la commande ci-dessous. Pour cette campagne
one-shot, la signature du contrat est en plus figée à
`42524db76476096c176d02ac9766ca18516b71f62f043e00e73a2aa92e27dad5`.
Il ne lance la chaîne
aval que si le statut vaut exactement `complete`, si le stage vaut exactement
`calibration_accepted_ready_for_downstream_handoff`, si
`downstream_authorized=true`, puis si les signatures annoncées correspondent
réellement au `holdout_result.json` accepté et à l'inventaire complet des 90
courbes. Avant l'attente puis juste avant le lancement, il vérifie aussi :

- les 10 SHA-256 V6 audités le 5 septembre 2026 ;
- les SHA-256 des deux HTML historiques RESILIENCE-SCAN et boucle fermée ;
- l'absence des dix destinations aval, manifeste final compris.

Un no-go, un rejet, un statut ou un contrat altéré, une preuve terminale absente,
un timeout ou une destination déjà présente arrête le relais sans campagne. Une
réservation atomique interdit une deuxième tentative aval, même après une
coupure. En mode `--background`, un jeton signé lie le parent au seul enfant
autorisé et empêche une invocation concurrente de prendre sa place. Le relais
empêche la veille pendant l'attente. Aucune commande ci-dessous n'est exécutée
automatiquement par ce document.

Dans ces fichiers, « signature » désigne une empreinte SHA-256 déterministe de
l'objet JSON : elle détecte une altération et lie les preuves entre elles, mais
ce n'est pas une signature à clé privée ni une preuve d'identité externe.

## Commande préparée — à lancer une seule fois

Les destinations indiquées ont été choisies nouvelles au moment de la création
du runbook. Le programme les revérifie lui-même et refuse de les reprendre.

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_v6_holdout_campaign_once_relay `
  --repo C:\dev\lca-simu-pr40 `
  --calibration-status C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v6_calibration_supervision_20260905\status.json `
  --handoff-supervision-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v6_holdout_campaign_once_relay_20260905_v1 `
  --v4-plan-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_delay_multiseed_refinement_plan_20260905_v6 `
  --v4-run-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_delay_multiseed_refinement_run_20260905_v6 `
  --v4-sidecar-root C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_delay_multiseed_refinement_forbidden_sidecar_20260905_v6 `
  --calibration-plan-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v6_fresh_holdout_plan_20260905 `
  --calibration-run-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v6_fresh_holdout_run_20260905 `
  --sidecar-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v6_fresh_holdout_sidecar_20260905 `
  --bridge-json C:\dev\lca-simu-pr40-validation-artifacts-20260726\validated_operating_points_bridge_20260905_v6.json `
  --campaign-root C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_20260905_v6 `
  --results-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_results_20260905_v6 `
  --lot-replay-root C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_priority_lot_replay_20260905_v6 `
  --qualification-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_physical_cascade_qualification_20260905_v6 `
  --action-replay-root C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_priority_action_replay_20260905_v6 `
  --dashboard-html C:\dev\lca-simu-pr40-validation-artifacts-20260726\OUVRIR_CAMPAGNE_FOURNISSEURS_V6_20260905.html `
  --final-html C:\dev\lca-simu-pr40-validation-artifacts-20260726\OUVRIR_RESULTATS_SUPPLY_CHAIN_V6_20260905.html `
  --downstream-supervision-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_full_campaign_relay_20260905_v6 `
  --legacy-risk-html C:\dev\lca-simu-pr40-validation-artifacts-20260726\DEMONSTRATION_REUNION_1500_20260904_v1\OUVRIR_DEMONSTRATION_RESILIENCE_SCAN.html `
  --legacy-control-html C:\dev\lca-simu-pr40-validation-artifacts-20260726\industrial_supply_preliminary_consolidated_20260904_v4\assets\carte_reseau_existante_hors_ligne.html `
  --calibration-workers 2 `
  --parallel-shards 2 `
  --workers-per-shard 2 `
  --launcher-poll-seconds 5 `
  --relay-poll-seconds 30 `
  --watcher-ready-timeout-seconds 300 `
  --sidecar-poll-ms 25 `
  --sidecar-stability-ms 12 `
  --wait-timeout-hours 12 `
  --poll-seconds 15 `
  --downstream-max-wait-hours 240 `
  --detach-invocation-timeout-seconds 600 `
  --background
```

## Suivi

- `watcher_detached.json` : reçu signé du watcher détaché ;
- `status.json` : état atomique courant ;
- `journal.json` : historique atomique et signé ;
- `launch_reservation.json` : preuve que l'unique tentative aval est consommée ;
- `watcher.log` : sortie du processus détaché.

Le succès du handoff est `downstream_detach_started`. Il signifie seulement que
le relais public `continue_supplier_full_campaign_v6 --detach` a refait sa
prévalidation et renvoyé un reçu signé lié à la commande enfant complète. La
réussite scientifique et technique finale reste à lire dans le `status.json` de
`--downstream-supervision-dir`.

Un `stopped_timeout` concerne l'attente de la décision de calibration : aucune
tentative aval n'a alors été faite. Après `launch_reserved`, tout refus du
préflight, timeout d'invocation ou reçu invalide consomme en revanche l'essai
unique. Pour un timeout ou un reçu invalide, `downstream_started=null` signifie
« résultat inconnu », et non « campagne certainement arrêtée » : examiner la
supervision aval et les PID avant tout diagnostic.

Ne jamais supprimer une réservation pour relancer. Après tout refus ou échec,
diagnostiquer puis choisir explicitement de nouvelles destinations et une
nouvelle supervision.
