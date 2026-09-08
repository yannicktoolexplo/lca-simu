# Campagne fournisseurs V5 — mode opératoire

## Ce que produit le traitement

Le relais aval V5 reprend uniquement une calibration V5 déjà terminée et acceptée. Son préflight relit le plan signé, les 210 preuves de développement, la sélection figée, les 90 preuves de holdout acceptées sans nouveau réglage, le contrat de capture et les deux inventaires sidecar finalisés. Il ne crée aucune commande de calibration : il ne planifie, n’exécute, ne reprend et ne finalise jamais le développement ou le holdout. Il ne réécrit aucune preuve V4, aucun plan/run V5 ni aucun inventaire sidecar source ; seuls les agrégats de courbes dérivés sont ajoutés dans leur sous-dossier dédié.

L’ordre est imposé :

1. vérifier en lecture seule le plan, le réglage retenu, le test sur données réservées accepté sans retuning, l’accusé du watcher et les inventaires signés des courbes ;
2. confirmer que le périmètre contient exactement 18 relations fournisseur-produit et 16 fournisseurs distincts ;
3. construire puis valider le pont V5 à partir de ces seules preuves ;
4. construire les 3 330 résultats d’incidents ;
5. sélectionner au plus trois dossiers prioritaires et rejouer leur suivi de lots ;
6. vérifier que chaque incident sélectionné a réellement touché une expédition et une réception, puis qualifier jusqu’où son effet est démontré ;
7. tester les actions opérationnelles en mode obligatoire ;
8. valider les courbes, produire le tableau technique secondaire et terminer par le HTML autonome V5 en trois vues.

La qualification distingue ce qui est effectivement démontré de ce qui reste une hypothèse. Deux relations sur 18 disposent d’un besoin MRP explicitement dynamique ; les 16 autres ont un besoin configuré comme fixe. Tant qu’une trace explicite ne relie pas réception, consommation, production et client, le livrable parle d’« effet partiellement démontré », jamais de « cascade complète ». Un résultat où tous les dossiers sont partiels reste publiable, à condition que cette limite soit affichée.

Les incidents restent les deux hypothèses fournisseurs figées : retard de transport et livraison partielle. Aucune retenue qualité, panne de capacité, indisponibilité produit, rupture artificielle ou probabilité historique n’est ajoutée.

## Commande prête à lancer

À lancer seulement après acceptation du test sur données réservées et présence de `capture_contract.json`, `watcher_ready.json`, `capture_inventory.json` et `capture_inventory_v5.json`. Le relais recalcule les preuves et leurs liaisons avant de créer son dossier de supervision ; une calibration incomplète, rejetée, retunée ou un sidecar altéré ne produit donc aucune sortie aval. Toutes les destinations V5 sont séparées des entrées V4 et des anciens HTML ; les plan/run V5 et les quatre preuves sidecar citées restent des entrées en lecture seule.

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v5 `
  --repo C:\dev\lca-simu-pr40 `
  --v4-plan-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_delay_multiseed_refinement_plan_20260905_v4 `
  --v4-run-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_delay_multiseed_refinement_run_20260905_v4 `
  --v4-sidecar-root C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_holdout_nominal_curves_sidecar_20260905_v4 `
  --calibration-plan-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_delay_multiseed_refinement_plan_20260905_v5 `
  --calibration-run-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_delay_multiseed_refinement_run_20260905_v5 `
  --sidecar-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_holdout_nominal_curves_sidecar_20260905_v5 `
  --bridge-json C:\dev\lca-simu-pr40-validation-artifacts-20260726\validated_operating_points_bridge_20260905_v5.json `
  --campaign-root C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_20260905_v5 `
  --results-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_results_20260905_v5 `
  --lot-replay-root C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_priority_lot_replay_20260905_v5 `
  --qualification-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_physical_cascade_qualification_20260905_v5 `
  --action-replay-root C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_priority_action_replay_20260905_v5 `
  --action-replay-mode required `
  --dashboard-html C:\dev\lca-simu-pr40-validation-artifacts-20260726\OUVRIR_CAMPAGNE_FOURNISSEURS_V5_20260905.html `
  --final-html C:\dev\lca-simu-pr40-validation-artifacts-20260726\OUVRIR_RESULTATS_SUPPLY_CHAIN_V5_20260905.html `
  --legacy-risk-html C:\dev\lca-simu-pr40-validation-artifacts-20260726\DEMONSTRATION_REUNION_1500_20260904_v1\OUVRIR_DEMONSTRATION_RESILIENCE_SCAN.html `
  --legacy-control-html C:\dev\lca-simu-pr40-validation-artifacts-20260726\industrial_supply_preliminary_consolidated_20260904_v4\assets\carte_reseau_existante_hors_ligne.html `
  --supervision-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_full_campaign_relay_20260905_v5 `
  --calibration-workers 2 `
  --parallel-shards 2 `
  --workers-per-shard 2 `
  --max-wait-hours 240 `
  --detach
```

Les options `--legacy-risk-html` et `--legacy-control-html` désignent des archives strictement en lecture seule. Le relais en inventorie la taille et l’empreinte, interdit tout chevauchement avec une destination V5, puis vérifie qu’elles n’ont pas changé. Le compositeur V5 ne les reçoit pas et ne les expose pas dans les trois vues client.

Suivi : `C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_full_campaign_relay_20260905_v5\status.json`

Livrable client : `C:\dev\lca-simu-pr40-validation-artifacts-20260726\OUVRIR_RESULTATS_SUPPLY_CHAIN_V5_20260905.html`

Le tableau de bord détaillé est conservé comme preuve technique secondaire. Il n’est pas exposé dans les trois vues du livrable client.

## Lecture des arrêts et limites

- refus avant lancement : calibration absente, incomplète, rejetée ou sidecar incomplet ; aucune destination aval n’est créée ;
- `scientific_no_go` : les résultats ne permettent pas de poursuivre scientifiquement ; aucun incident aval n’est lancé ;
- `failed` : erreur technique, preuve incohérente, qualification absente ou altérée ; reprendre avec la même commande après diagnostic.
- `complete` : lots, qualification, actions, courbes et HTML final sont validés.
- `complete_no_representable_action` est un sous-statut de la phase actions : une tentative réelle a établi qu’aucune action n’était représentable par le moteur pour les dossiers retenus ; le relais peut alors terminer avec le statut global `complete`.
- `not_run_no_qualified_dossier` est le seul autre sous-statut actions recevable : il signifie qu’aucun dossier n’a été retenu et qu’aucune action ne pouvait donc être rejouée.
- Lorsqu’un dossier est retenu, une action absente, `not_configured` ou incomplète bloque la publication. Une courbe absente ou incomplète bloque toujours la publication.

Le budget d’attente configuré à 240 heures couvre les reprises et le pire cas attendu ; ce n’est pas un coupe-circuit global d’un sous-processus déjà lancé. L’estimation nominale est de 45 à 59 heures ; l’enveloppe défavorable contractuelle est de 165 à 186 heures. Le watcher externe n’étant pas transactionnel, le relais exige son contrat, son accusé signé et les deux inventaires finalisés avant tout lancement aval.

## Annexe technique — compatibilité et empreintes

Le moteur d’incidents, le consolidateur, les lots et les actions conservent des composants V4 gelés. Le rendu final est assuré par le compositeur V5, qui contrôle la qualification physique et masque les pages techniques du parcours client. Toute modification d’un composant épinglé bloque la reprise.

```powershell
$d = 'C:\dev\lca-simu-pr40\etudecas\prototypes\scan_2027_risk_control'
Get-FileHash -Algorithm SHA256 -LiteralPath `
  "$d\supplier_balanced_product_delay_multiseed_refinement_v5.py", `
  "$d\build_validated_operating_points_v5.py", `
  "$d\supplier_holdout_curve_sidecar_v5.py", `
  "$d\supplier_operating_point_full_campaign_v5.py", `
  "$d\launch_supplier_operating_point_full_campaign_v5.py", `
  "$d\finalize_supplier_operating_point_full_campaign_v5.py", `
  "$d\supplier_physical_cascade_qualification_v5.py", `
  "$d\supplier_v5_final_standalone_delivery.py", `
  "$d\continue_supplier_full_campaign_v5.py", `
  "$d\tests\test_supplier_v5_downstream_integration.py"
```

Empreinte gelée du cœur scientifique V5 :

```text
46bc479466edfe9e1610abbf84aa3f0a6ff039b9066c9a395599494d0b4ed922
```

Empreintes V5 relevées après la dernière matrice de tests :

```text
supplier_balanced_product_delay_multiseed_refinement_v5.py 46bc479466edfe9e1610abbf84aa3f0a6ff039b9066c9a395599494d0b4ed922
build_validated_operating_points_v5.py                     41492d5b66835028b7aed9977a4e21f4214e7d6e85d98c6a5ae535a7b2cbacb2
supplier_holdout_curve_sidecar_v5.py                       cdb5c110c847e39a189d87b93a2aca08295913b593c039307b7006b1341ded8a
supplier_operating_point_full_campaign_v5.py               302c59d76d9bf490886ba3f100075992566292b1761b71bed9fd27746e6e7b12
launch_supplier_operating_point_full_campaign_v5.py        59f1c33552f19bcf09c773733ece132e0e04d341c98807ca9c7087a2de1f4d13
finalize_supplier_operating_point_full_campaign_v5.py      2bbfd696b0654f5837da0a51d0022ec1cf4cc9b9eaf98dfd6207a95603898c82
supplier_physical_cascade_qualification_v5.py              0bba07f024d1d3f29774bea6945be5d61a85153422c3dd6fac3c86b16fb739e9
supplier_v5_final_standalone_delivery.py                    19174dc30c28ddfd4143f573414cc76279d1d5b384022b3c2d62d8962fa903be
continue_supplier_full_campaign_v5.py                       4a42e97e20233c7907a1cd5e6b202aa4f3a24b56e5da3b029d2ab4bc11cb21cd
tests/test_supplier_v5_downstream_integration.py             f3228948be14aad1f5fb618df16b99337978ac0345316ddd371227c710ea84fd
```

Validation locale : 81 tests aval et de non-régression V4, puis 61 tests V5, tous réussis. Ruff et la compilation Python sont également validés. Aucun moteur, aucune campagne et aucune calibration n’ont été lancés pendant ces contrôles.
