# Passerelle V7 vers la campagne fournisseurs complète

## Décision de conception

La campagne incidents doit partir des simulations V7 nouvelles, et non des 30
simulations V6 déjà examinées.

Le chemin retenu est le suivant :

1. V7 valide ou rejette une seule fois le triplet fixe sur 150 graines, soit
   450 simulations physiques.
2. Après une acceptation V7 seulement, les CSV complets d'expéditions conservés
   pour les 30 premières graines V7 sont relus et contrôlés par SHA-256.
3. Ces CSV produisent 90 traces compactes : 3 états × 30 graines. Aucun moteur
   n'est relancé pour cette dérivation.
4. Les mêmes 30 graines servent à la situation normale et aux incidents de la
   campagne. Elles permettent donc une comparaison appariée.
5. La campagne mature reste inchangée : 3 états × 30 graines ×
   (1 situation normale + 18 voies × 2 incidents) = 3 330 lignes.
   Elle contient exactement 90 lignes normales et 3 240 lignes incidents.

La sélection des 30 premières graines est déterministe, inscrite dans le code
avant l'exécution V7 et indépendante des résultats simulés. Ce sous-ensemble ne
constitue pas une seconde validation du triplet. La décision scientifique reste
exclusivement celle des 150 graines V7.

V6 reste seulement la provenance de conception du triplet et des 18 voies. Ni
ses résultats de simulation, ni ses 30 traces ne sont réutilisés comme preuve ou
comme situation normale de la campagne V7.

## Ce qui est verrouillé

- Module scientifique V7 :
  `supplier_fresh_development_holdout_protocol_v7.py`.
- SHA-256 attendu :
  `f11ba2523bd319e210e5d5d82a25beb1e88a2fc5bd17a181540f8662526a63e5`.
- Validation : 150 graines distinctes, 450 preuves physiques complètes.
- Campagne : les 30 premières graines V7, 90 traces normales, 18 voies, deux
  incidents seulement.
- Incidents autorisés : retard transport et livraison planifiée partielle.
- Incidents exclus : qualité, disponibilité, capacité et stock.
- Risques fournisseurs dépendants de l'état désactivés dans cette campagne :
  aucun scénario secondaire implicite ne se superpose aux deux incidents testés.
- Aucun réglage du triplet après lecture d'un résultat V7.
- Aucun résultat V4, V5 ou V6 écrasé ou réutilisé comme preuve V7.

Tout écart de hash, de signature, de nombre de cas, de graine, de voie ou de
statut provoque un arrêt. Un résultat V7 rejeté ou incomplet ne crée aucun
dossier aval.

## Fichiers additifs

- `supplier_v7_campaign_trace_package.py` : dérive et revalide les 90 traces à
  partir des bundles V7.
- `build_validated_operating_points_v7.py` : construit le pont signé et rend
  explicite la séparation 150 graines / 30 graines.
- `supplier_operating_point_full_campaign_v7.py` : adapte le moteur de campagne
  mature aux 30 graines V7 et ajoute une provenance scientifique explicite :
  les 150 graines/450 preuves autorisent le triplet ; les 30 graines/90 traces
  ne servent qu'à apparier référence et incidents.
- `launch_supplier_operating_point_full_campaign_v7.py` : lance et reprend les
  18 blocs avec ces mêmes graines.
- `finalize_supplier_operating_point_full_campaign_v7.py` : consolide exactement
  3 330 preuves.
- `continue_supplier_full_campaign_v7.py` : enchaîne les étapes en mode
  relançable ou détaché, après acceptation V7 seulement.
- `watch_then_continue_supplier_full_campaign_v7.py` : peut être armé pendant
  les 450 cas. Il attend une progression signée 450/450, finalise la décision
  avec le verrou du protocole, la reconstruit entièrement, puis appelle le
  relais uniquement si elle est acceptée.
- `supplier_operating_point_full_campaign_v7_dashboard.py` : adapte en lecture
  le contrôle du dashboard mature aux 30 graines V7, remplace de façon contrôlée
  ses trois mentions visibles héritées par le vocabulaire V7, puis restaure la
  cohorte et le gabarit historiques V4.
- `supplier_v7_final_standalone_delivery.py` : identité V7 du futur livrable
  autonome. Son branchement complet aux lots, actions et courbes appartient à
  l'étape aval suivante.

Aucun de ces modules ne modifie le moteur, V4, V5, V6 ou les résultats
historiques.

## Contrat de test

Les tests automatiques vérifient notamment :

- le SHA exact du protocole V7 ;
- les 30 graines et leurs six blocs de cinq ;
- leur appartenance aux 150 graines V7 et leur absence des anciennes cohortes ;
- la propagation puis la restauration des graines dans le runner, le lanceur et
  le finaliseur matures ;
- le hash du gzip et le hash du CSV décompressé pour chaque source d'expédition ;
- l'arrêt sur toute décision V7 non acceptée ;
- la présence explicite des 150 graines/450 preuves comme seule autorisation ;
- le rôle limité des 30 graines/90 traces à l'appariement de campagne ;
- l'absence de toute écriture aval avant l'acceptation V7 ;
- l'absence de finalisation avant une progression signée exactement 450/450 ;
- l'attente si le runner détient encore le verrou V7, sans double processus ;
- l'arrêt sans sortie aval si la décision finale est rejetée ou corrompue ;
- la confirmation signée que l'enfant détaché détient effectivement le verrou
  avant que le parent annonce un lancement réussi ;
- le refus d'un double lancement concurrent, l'arrêt de l'enfant sur délai
  d'acquisition dépassé et l'échec signé s'il meurt avant confirmation ;
- la stabilité de l'inventaire transitif V4/V5/V6 avant et après chaque étape ;
- la surcouche finale V7 signée, qui distingue explicitement 150/450 de 30/90
  et ne peut pas être ajoutée a posteriori à un résultat existant ;
- l'ordre relançable traces → pont → plan → campagne → consolidation.

Commande de contrôle sans moteur :

```powershell
python -m pytest -q etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_fresh_development_holdout_protocol_v7.py etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v7_downstream_adapter.py
python -m ruff check etudecas/prototypes/scan_2027_risk_control/supplier_v7_campaign_trace_package.py etudecas/prototypes/scan_2027_risk_control/build_validated_operating_points_v7.py etudecas/prototypes/scan_2027_risk_control/supplier_operating_point_full_campaign_v7.py etudecas/prototypes/scan_2027_risk_control/launch_supplier_operating_point_full_campaign_v7.py etudecas/prototypes/scan_2027_risk_control/finalize_supplier_operating_point_full_campaign_v7.py etudecas/prototypes/scan_2027_risk_control/supplier_operating_point_full_campaign_v7_dashboard.py etudecas/prototypes/scan_2027_risk_control/continue_supplier_full_campaign_v7.py etudecas/prototypes/scan_2027_risk_control/watch_then_continue_supplier_full_campaign_v7.py etudecas/prototypes/scan_2027_risk_control/supplier_v7_final_standalone_delivery.py
```

Résultat au gel de cette passerelle : 43 tests aval V7 réussis ; la suite
croisée protocole V7 + aval compte 55 tests réussis. Une campagne antérieure de
non-régression élargie au runner, lanceur, finaliseur et dashboard V4 matures
comptait 68 tests réussis. Ruff et la compilation Python réussissent. Aucun
moteur n'a été lancé et aucun artefact officiel aval n'a été créé par ces
contrôles.

## Armement autonome pendant la validation V7

Le watcher externe est la commande à lancer pendant que les 450 cas sont en
cours. Avant la décision, il ne crée que son propre dossier de supervision. Il
ne lance aucun moteur V7. Quand `progress.json` signé déclare exactement 450
cas et 150 blocs complets, il appelle le finaliseur gelé sous le verrou exclusif
V7. Le fichier de décision ainsi produit reste une sortie du protocole V7, pas
une sortie de campagne. Les éventuels checkpoints descriptifs dus sont eux
aussi confinés au dossier du run V7 et ne participent pas à la décision. Le
relais aval n'est appelé qu'après reconstruction intégrale d'une décision
acceptée.

```powershell
$ArtifactRoot = 'C:\dev\lca-simu-pr40-validation-artifacts-20260726'
$V7Plan = Join-Path $ArtifactRoot 'supplier_fixed_triplet_confirmation_plan_20260905_v7'
$V7Run = Join-Path $ArtifactRoot 'supplier_fixed_triplet_confirmation_run_20260905_v7'
$V7Traces = Join-Path $ArtifactRoot 'supplier_v7_campaign_trace_package_20260905_v1'
$V7Bridge = Join-Path $ArtifactRoot 'validated_operating_points_v7_20260905_v1.json'
$V7Campaign = Join-Path $ArtifactRoot 'supplier_operating_point_full_campaign_v7_20260905_v1'
$V7Results = Join-Path $ArtifactRoot 'supplier_operating_point_full_campaign_v7_results_20260905_v1'
$V7RelaySupervision = Join-Path $ArtifactRoot 'supplier_operating_point_full_campaign_v7_supervision_20260905_v1'
$V7WatcherSupervision = Join-Path $ArtifactRoot 'supplier_operating_point_full_campaign_v7_watcher_20260905_v1'

python -m etudecas.prototypes.scan_2027_risk_control.watch_then_continue_supplier_full_campaign_v7 `
  --repo 'C:\dev\lca-simu-pr40' `
  --v7-plan-dir $V7Plan `
  --v7-run-dir $V7Run `
  --trace-package-dir $V7Traces `
  --bridge-json $V7Bridge `
  --campaign-root $V7Campaign `
  --results-dir $V7Results `
  --relay-supervision-dir $V7RelaySupervision `
  --watcher-supervision-dir $V7WatcherSupervision `
  --parallel-shards 2 `
  --workers-per-shard 2 `
  --detach
```

Une coupure de l'interface de conversation n'arrête pas le processus détaché.
Un second `--detach` avec le même dossier est refusé. Si le processus est
réellement arrêté, une reprise explicite utilise la même commande sans
`--detach` ; les contrats signés et les verrous empêchent une double campagne.

Suivi du watcher :

```powershell
Get-Content -LiteralPath (Join-Path $V7WatcherSupervision 'status.json') -Raw
Get-Content -LiteralPath (Join-Path $V7WatcherSupervision 'detached_watcher.log') -Tail 40
```

## Lancement manuel après acceptation V7

Le relais direct reste le mode manuel de secours après acceptation. Les chemins
ci-dessous sont nouveaux et séparés des sources.

```powershell
$ArtifactRoot = 'C:\dev\lca-simu-pr40-validation-artifacts-20260726'
$V7Plan = Join-Path $ArtifactRoot 'supplier_fixed_triplet_confirmation_plan_20260905_v7'
$V7Run = Join-Path $ArtifactRoot 'supplier_fixed_triplet_confirmation_run_20260905_v7'
$V7Traces = Join-Path $ArtifactRoot 'supplier_v7_campaign_trace_package_20260905_v1'
$V7Bridge = Join-Path $ArtifactRoot 'validated_operating_points_v7_20260905_v1.json'
$V7Campaign = Join-Path $ArtifactRoot 'supplier_operating_point_full_campaign_v7_20260905_v1'
$V7Results = Join-Path $ArtifactRoot 'supplier_operating_point_full_campaign_v7_results_20260905_v1'
$V7Supervision = Join-Path $ArtifactRoot 'supplier_operating_point_full_campaign_v7_supervision_20260905_v1'

python -m etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v7 `
  --repo 'C:\dev\lca-simu-pr40' `
  --v7-plan-dir $V7Plan `
  --v7-run-dir $V7Run `
  --trace-package-dir $V7Traces `
  --bridge-json $V7Bridge `
  --campaign-root $V7Campaign `
  --results-dir $V7Results `
  --supervision-dir $V7Supervision `
  --parallel-shards 2 `
  --workers-per-shard 2 `
  --detach
```

La commande détachée effectue d'abord une relecture complète de V7. Elle ne
crée le reçu et le processus aval qu'après acceptation. Une seconde commande
avec le même dossier de supervision est refusée ; il n'y a ni relance parallèle
silencieuse ni remplacement d'un reçu existant.

Le suivi se fait sans interrompre le calcul :

```powershell
Get-Content -LiteralPath (Join-Path $V7Supervision 'status.json') -Raw
Get-Content -LiteralPath (Join-Path $V7Campaign 'launch_progress.json') -Raw
```

Une reprise explicite utilise la même commande sans `--detach`. Le relais relit
les signatures existantes, attend un enfant encore actif et ne recommence que
les étapes dont la preuve finale manque.

## Sorties attendues de cette première étape aval

- `trace_package_manifest.json` et 90 traces compactes ;
- un pont JSON V7 signé ;
- un manifeste de campagne, un registre des cibles et 18 blocs ;
- 3 330 preuves de cas signées ;
- `campaign_validation.json`, les sensibilités, dispersions et priorités ;
- `campaign_validation_v7.json`, surcouche signée qui rend non ambiguë la
  provenance scientifique V7 et marque les noms de champs V4 comme de simples
  alias de compatibilité ;
- un plan de rejeu des lots prioritaires.

Le plan de rejeu est produit, mais les rejeux détaillés, la qualification des
cascades, les actions, les courbes nominales et le HTML autonome ne sont pas
encore exécutés par ce relais minimal. Ils doivent être ajoutés après projection
des bundles V7 vers le contrat de courbes, sans réutiliser le sidecar V6.

## Étape 2 à adapter après les 3 330 cas

Le futur relais de livraison V7 devra envelopper les briques matures suivantes,
sans les modifier :

1. `supplier_priority_lot_replay_v4.py` pour sélectionner au plus trois
   dossiers réellement exposés, rejouer une situation normale et un incident
   avec traçage natif des lots, puis consolider les courbes et généalogies.
2. `supplier_physical_cascade_qualification_v5.py` pour distinguer ce qui est
   physiquement démontré de ce qui ne l'est pas. La qualification historique
   connaît 18 voies, dont deux seulement sont dynamiques dans le MRP ; elle ne
   doit jamais transformer une trace partielle en cascade complète.
3. `supplier_v6_full_incident_lot_registry.py` pour présenter les 3 240 cas
   incidents et les 90 références appariées. Cette brique doit être enveloppée
   afin que `finalize_supplier_operating_point_full_campaign_v4.EXPECTED_SEEDS`
   soit temporairement remplacé par les 30 graines V7 puis restauré. Les
   généalogies détaillées restent limitées aux rejeux effectués : le registre ne
   permet pas de prétendre que tous les lots des 3 330 cas ont été tracés.
4. `supplier_priority_action_replay_v4.py` pour les actions représentables. Son
   accès au lecteur lots doit être rebindi vers l'adaptateur V7. Les modules
   `supplier_v2_action_input_generator.py`,
   `supplier_v2_controllable_action_selector.py` et
   `supplier_post_top3_action_protocol.py` servent à qualifier les prérequis
   opérationnels ; une action non qualifiée ou non représentable doit rester
   refusée. Les rejeux d'actions actuels sont en boucle ouverte et sans traçage
   lot : aucun gain ne doit encore être attribué à un lot précis.
5. `supplier_holdout_curve_aggregator_v4.py` pour agréger les courbes après
   création d'une nouvelle projection V7. Cette projection devra extraire, pour
   les mêmes 30 premières graines, les quatre CSV quotidiens obligatoires déjà
   conservés dans chaque bundle V7 : service, production, stocks d'entrée et
   contraintes. Elle devra contrôler les SHA du gzip et du CSV décompressé et
   ne jamais lire le sidecar V6.
6. `supplier_operating_point_full_campaign_v7_dashboard.py`, déjà ajouté, pour
   le contrôle seed-aware des résultats ; puis
   `supplier_v7_final_standalone_delivery.py`, dont le lecteur de campagne est
   déjà rebindi vers cet adaptateur, pour le HTML final après branchement des
   lots, actions, qualification et courbes.

Préconditions obligatoires de cette étape : décision V7 acceptée et entièrement
reconstruite ; campagne 3 330 cas consolidée ; matrice exacte 90 + 3 240 sur les
mêmes 30 graines ; deux incidents seulement ; six indicateurs d'exclusion à
`false` (qualité, branche qualité, disponibilité, capacité, stock et risques
fournisseur dépendants de l'état) ; fichiers sources et sorties liés par hash ;
aucun dossier prioritaire forcé ; et aucune publication HTML avant validation
des preuves de lots, de la portée physique, du statut des actions et des 90
jeux de courbes.

## Risques résiduels et durée

1. La revalidation V7 relit les 450 preuves et leurs bundles. Elle est volontaire
   mais peut ajouter du temps d'entrée à chaque processus de campagne. Mesurer
   ce coût sur le premier bloc avant de modifier ce choix de sûreté.
2. Les 30 graines de campagne font partie des 150 graines V7. C'est correct pour
   comparer normalement et incident avec les mêmes conditions, mais leurs
   statistiques descriptives ne sont pas une nouvelle preuve indépendante de
   calibration.
3. Les incidents restent des scénarios conditionnels. Ils classent les impacts
   si l'incident arrive ; ils n'estiment pas sa probabilité historique.
4. Les cascades secondaires corrélées ne sont pas revendiquées dans cette
   campagne mature. Elles devront être distinguées des effets physiques de lot
   effectivement rejoués.

Après l'acceptation V7, la dérivation des traces, le pont et le plan devraient
prendre de quelques minutes à quelques dizaines de minutes selon la taille des
bundles. L'ordre de grandeur historique de la campagne 3 330 cas est de 45 à
59 heures dans les conditions usuelles, avec une borne prudente antérieure de
165 à 186 heures. La consolidation finale est courte devant les simulations.
Ces durées devront être recalées sur les premiers blocs V7 réellement terminés.
