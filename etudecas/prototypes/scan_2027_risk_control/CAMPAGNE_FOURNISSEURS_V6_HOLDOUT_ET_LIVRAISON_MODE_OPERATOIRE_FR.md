# V6 — holdout frais et livraison industrielle

## Statut et barrière d'activation

Le développement V6 peut être planifié ou actif après le no-go terminal V5.
Cela n'autorise jamais, à lui seul, la création du plan holdout : aucune graine
réservée ne doit être ouverte avant la sélection V6 officielle signée.

Elle ne devient utilisable que si :

1. V5 se termine par `development_failed_no_holdout` ;
2. la campagne de développement V6 est exécutée sur ses deux seuls candidats ;
3. V6 sélectionne et signe un triplet avec le statut
   `development_selected_pending_separate_fresh_holdout_protocol` ;
4. le compteur de cas holdout lus vaut toujours zéro.

Tout autre état provoque un refus avant création du plan holdout.

## Orchestrateur de calibration recommandé

La commande suivante assure la continuité sans terminal interactif. Elle peut
s'attacher à un développement V6 officiel déjà actif, attend sa fin, le
finalise, puis s'arrête immédiatement en no-go si aucun triplet n'est retenu.
En cas de sélection seulement, elle fige le plan holdout séparé, enregistre le
run sans appel moteur, démarre le watcher, attend et vérifie son accusé signé et
son lease OS, exécute les 3 × 30 cas frais, finalise les deux inventaires et
s'arrête. Elle ne contient aucune commande de pont, campagne ou livraison.

Depuis `C:\dev\lca-simu-pr40` :

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.continue_supplier_v6_calibration `
  --repo C:\dev\lca-simu-pr40 `
  --v5-plan-dir <PLAN_V5_TERMINE> `
  --v5-run-dir <RUN_V5_TERMINE> `
  --v5-sidecar-root <SIDECAR_V5_ABSENT_OU_VIDE> `
  --development-plan-dir <PLAN_DEVELOPPEMENT_V6> `
  --development-run-dir <RUN_DEVELOPPEMENT_V6> `
  --holdout-plan-dir <PLAN_HOLDOUT_V6> `
  --holdout-run-dir <RUN_HOLDOUT_V6> `
  --sidecar-dir <SIDECAR_HOLDOUT_V6> `
  --supervision-dir <SUPERVISION_CALIBRATION_V6_NOUVELLE> `
  --workers 2 `
  --max-wait-hours 6 `
  --poll-seconds 5 `
  --detach
```

Surveiller `status.json` et `orchestrator.log` dans la racine de supervision ;
`development_progress.json` puis `holdout_progress.json` restent les compteurs
signés des producteurs. Le reçu `detached.json` est écrit avant la création de
l'enfant et distingue réservation, démarrage et échec de démarrage. Un dossier
de supervision existant n'est jamais réutilisé.

Un verrou développement dont le PID est mort n'est jamais supprimé
automatiquement : l'orchestrateur s'arrête pour audit opérateur. De même, un
lease sidecar déjà détenu provoque un refus explicite avant tout second watcher.
Une calibration holdout déjà terminale est seulement reconstruite et validée
en lecture seule ; aucun progrès, accusé watcher ou résultat n'est réécrit.

## Ce qui est figé avant le holdout

- exactement trois états : référence, état proche de 93 %, état proche de 80 % ;
- exactement 30 graines réservées par état, soit 90 simulations ;
- les trois candidats sélectionnés par le développement V6, sans substitution ;
- les critères V4/V5 inchangés : bandes de service, ordre strict global et par
  produit, ordre apparié sur au moins 24 graines ;
- aucun ajustement après lecture d'un résultat holdout ;
- en cas de rejet : publication d'un no-go et nouvelle cohorte obligatoire.

Les décimales des décalages sont des paramètres du modèle, pas une promesse de
précision opérationnelle à la demi-journée.

## Étape 1 — figer le protocole séparé

À exécuter seulement après une sélection V6 officielle réussie :

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_holdout_v6 plan `
  --development-plan-dir <PLAN_DEVELOPPEMENT_V6> `
  --development-run-dir <RUN_DEVELOPPEMENT_V6> `
  --output-dir <PLAN_HOLDOUT_V6>
```

La validation relit les 150 preuves de développement, recalcule la sélection et
vérifie l'absence de tout fichier holdout dans la source.

## Étape 2 — démarrer la capture des courbes

En mode manuel de diagnostic, enregistrer d'abord le run sans moteur :

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_holdout_v6 prepare-run `
  --plan-dir <PLAN_HOLDOUT_V6> `
  --run-dir <RUN_HOLDOUT_V6>
```

Puis, dans un premier terminal, avant le moteur :

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_holdout_curve_sidecar_v6 watch `
  --plan-dir <PLAN_HOLDOUT_V6> `
  --run-dir <RUN_HOLDOUT_V6> `
  --output-dir <SIDECAR_V6> `
  --poll-ms 25 `
  --stability-ms 12 `
  --timeout-seconds 864000
```

Le sidecar conserve les courbes journalières utiles à la lecture des stocks,
productions, contraintes, demandes servies et lots. Le watcher doit réussir sa
construction et un premier balayage avant de publier `watcher_ready.json`.
Chaque appel moteur revérifie le PID, le lease OS et les hashes exacts du contrat
et de cet accusé. Une capture incomplète ou altérée bloque toute livraison.

## Étape 3 — exécuter puis décider le holdout

Dans un second terminal :

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_holdout_v6 run-holdout `
  --plan-dir <PLAN_HOLDOUT_V6> `
  --run-dir <RUN_HOLDOUT_V6> `
  --workers 2 `
  --sidecar-dir <SIDECAR_V6> `
  --watcher-pid <PID_PROCESSUS_PYTHON_WATCHER_V6>

python -m etudecas.prototypes.scan_2027_risk_control.supplier_fresh_holdout_v6 finalize-holdout `
  --plan-dir <PLAN_HOLDOUT_V6> `
  --run-dir <RUN_HOLDOUT_V6>
```

Résultat accepté attendu : `holdout_validated_30_fresh_reserved_seeds`.
`holdout_rejected_no_retuning` interdit toute livraison aval avec ce triplet.

## Étape 4 — pont vers la campagne de 3 330 résultats

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.build_validated_operating_points_v6 build `
  --plan-dir <PLAN_HOLDOUT_V6> `
  --run-dir <RUN_HOLDOUT_V6> `
  --output <PONT_V6_JSON>
```

Le pont contient les trois états, les 90 références de traces compactes, les
services validés et les décalages figés. Son enveloppe reste compatible avec le
moteur de campagne V4/V5 afin de ne pas recopier ni modifier ce moteur.

## Étape 5 — chaîne aval complète

Le module `continue_supplier_full_campaign_v6` réutilise la chaîne éprouvée et
ne sait pas lancer une calibration. Il refuse explicitement ses méthodes de
planification, développement et holdout. Son exécution aval enchaîne :

1. revalidation en lecture seule du holdout et du sidecar ;
2. pont V6 ;
3. campagne incidents de 3 330 résultats ;
4. sélection et rejeu des dossiers de lots ;
5. qualification physique des cascades ;
6. actions réalistes ou constat signé qu'aucune action n'est représentable ;
7. courbes nominales ;
8. tableau de bord et HTML autonome final.

Il reprend les arguments du relais V5. Dans cette enveloppe de compatibilité :

- `--v4-plan-dir` et `--v4-run-dir` désignent le plan et le run de
  **développement V6**, qui restent protégés en lecture seule ;
- `--v4-sidecar-root` désigne son emplacement sidecar interdit, absent ou vide ;
- `--calibration-plan-dir` et `--calibration-run-dir` désignent le plan et le
  run du **holdout V6 accepté** ;
- `--sidecar-dir` désigne le sidecar V6 finalisé ;
- toutes les sorties pont, campagne, résultats, lots, qualification, actions,
  supervision et HTML doivent être nouvelles, distinctes et hors des sources.

Le relais peut être lancé au premier plan avec la commande ci-dessous, ou en
ajoutant `--detach`. Le mode détaché effectue toute la prévalidation en lecture
seule avant de créer le dossier de supervision, le journal, le reçu signé et le
processus enfant. L'enfant relance explicitement le module V6 avec
`--detached-child`; il réinstalle donc lui-même tous les adaptateurs V6. Un reçu
existant, actif ou historique, provoque un refus : utiliser une nouvelle racine
de supervision plutôt que d'écraser sa preuve.

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v6 `
  --repo C:\dev\lca-simu-pr40 `
  --v4-plan-dir <PLAN_DEVELOPPEMENT_V6> `
  --v4-run-dir <RUN_DEVELOPPEMENT_V6> `
  --v4-sidecar-root <EMPLACEMENT_INTERDIT_VIDE> `
  --calibration-plan-dir <PLAN_HOLDOUT_V6> `
  --calibration-run-dir <RUN_HOLDOUT_V6> `
  --sidecar-dir <SIDECAR_V6> `
  --bridge-json <PONT_V6_JSON> `
  --campaign-root <CAMPAGNE_V6> `
  --results-dir <RESULTATS_V6> `
  --lot-replay-root <LOTS_V6> `
  --qualification-dir <QUALIFICATION_V6> `
  --action-replay-root <ACTIONS_V6> `
  --action-replay-mode required `
  --dashboard-html <TABLEAU_DE_BORD_V6.html> `
  --final-html <LIVRAISON_CLIENT_V6.html> `
  --supervision-dir <SUPERVISION_V6> `
  --max-wait-hours 240 `
  --detach
```

## Limites qui doivent rester visibles

- Les trois niveaux sont des états simulés, pas des taux fournisseurs observés.
- Les risques aigus de la campagne sont des hypothèses et non des probabilités
  historiques prédites.
- Le moteur est dynamique et dépend des stocks, flux, MRP et règles de lots,
  mais les actions aval restent des scénarios préparés, pas une régulation
  automatique en boucle fermée.
- La preuve lot dépend des traces effectivement exercées et de la qualification
  physique ; une trace partielle ne devient jamais une cascade complète.
- Les coûts restent ceux du modèle tant qu'ils ne sont pas raccordés aux coûts
  industriels validés.
- Aucun risque qualité, capacité ou disponibilité n'est ajouté à la V6 : ces
  branches restent explicitement désactivées. Les événements aigus aval restent
  les seules hypothèses déjà déclarées par la campagne compatible V4/V5.
- Le producteur historique n'offre pas de transaction de capture ; la réponse
  V6 est donc fail-closed : seuls 90 instantanés complets, uniques et hashés
  autorisent le relais aval.

## Empreintes auditées le 5 septembre 2026

| Fichier | SHA-256 |
|---|---|
| `supplier_fresh_holdout_v6.py` | `bae2589fa99f18cc1237aece1e5db9ae22a25882203b280d41f800c8fab181f2` |
| `supplier_holdout_curve_sidecar_v6.py` | `b2424ddb272a1601b60d60f7716e8dd23b64916d0a15a4e4f6a60ad60c513016` |
| `continue_supplier_v6_calibration.py` | `9af8432e26435aa4b2fb99157a944fa270c1427247087af133b2d9eb8adaa047` |
| `build_validated_operating_points_v6.py` | `8943209948f19979b3f448c65ca364f9e18b98aac34aaecec21d4fc6f5a123a4` |
| `supplier_operating_point_full_campaign_v6.py` | `ac251c2f7fec97d770ae43e21247e07a2d1eda09ebed5dbf0a113f035e9c8564` |
| `launch_supplier_operating_point_full_campaign_v6.py` | `5b6f166d753c6a8e25b7da3156fe6815ec80457d09e41f7f051939a4b9873cec` |
| `finalize_supplier_operating_point_full_campaign_v6.py` | `a4d523d0817464074ae4089b660de2db992de950cad8566e9efd2b68dd08715b` |
| `supplier_v6_final_standalone_delivery.py` | `3b52c8b85d9eff7f8e15a6b256276ca05da0144b2d1b53fa9ae7850d7b8c74dd` |
| `continue_supplier_full_campaign_v6.py` | `b087250de5ccc483e08668b9074a943cf978a6589f3d9e74e733b38bd83512ad` |
| `tests/test_supplier_v6_completion_path.py` | `3b43186935c27debbfbe7ea0220fbb312c07f41f8cc1333103f36bd4b61326a2` |

Toute différence impose un nouvel audit avant holdout ou relais aval.
