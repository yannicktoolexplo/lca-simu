# V6 conditionnelle — mode opératoire

## Objet

La V6 est un recours minimal, uniquement si la V5 se termine par un échec de
calibration avant toute validation finale. Elle teste exactement deux nouveaux
points de fonctionnement à 80 % :

- PF 268091 : +17,0 jours ; PF 268967 : +96,6 jours ;
- PF 268091 : +17,5 jours ; PF 268967 : +96,6 jours.

Elle réutilise, sans les recalculer, les 30 preuves V5 du fonctionnement à 100 %
et les 60 preuves des deux configurations V5 à 93 % déjà jugées admissibles
(`8,3 / 80,6` et `8,4 / 80,6`). Seuls les deux points à 80 % sont simulés :
60 nouveaux calculs, soit 2 configurations × 30 répétitions.

Les valeurs décimales sont des paramètres de calibration du modèle. Elles ne
prétendent pas représenter une précision opérationnelle au dixième de jour.

## Pourquoi seulement deux points

La reconstruction sur les 30 mêmes répétitions donne :

| Point à 80 % | Service global regroupé | Médiane | Intervalle retrait d'une répétition | Écart entre produits | Ordre strict |
|---|---:|---:|---:|---:|---:|
| 17,0 / 96,6 | 80,471 % | 80,165 % | 80,242–80,769 % | 3,803 points | 24/30 |
| 17,5 / 96,6 | 80,226 % | 79,654 % | 80,023–80,469 % | 3,449 points | 24/30 |

Ces nombres servent uniquement à choisir les points à exécuter. Ils ne sont pas
des résultats acceptés. Les 60 simulations exactes restent obligatoires.

Les six répétitions qui empêchent de dépasser 24/30 échouent déjà entre les
états 100 % et 93 % sur PF 268967. Modifier davantage le point à 80 % ne peut
donc pas augmenter ce compte. Un troisième point ajouterait des calculs sans
créer de marge sur ce critère.

## Conditions impératives avant toute commande

Ne rien lancer si une seule condition manque :

1. `development_progress.json` de V5 indique `complete` avec 210/210 preuves ;
2. `development_selection.json` de V5 existe, sa signature est valide et son
   statut est exactement `development_failed_no_holdout` ;
3. le fonctionnement à 100 % est admissible ;
4. seules les configurations V5 `8,3 / 80,6` et `8,4 / 80,6` sont admissibles à
   93 %, et aucune configuration V5 à 80 % ne l'est ;
5. V5 indique zéro lecture de validation finale ;
6. aucun répertoire, résultat, essai moteur ou fichier de courbes de validation
   finale V5 n'existe ; le répertoire sidecar V5 est absent ou vide.

Le code contrôle de nouveau ces six conditions à la création du plan, à sa
validation, avant les simulations et avant la synthèse. Tant que V5 tourne, ou
si V5 réussit, la création du plan V6 doit échouer.

## Commandes — à conserver, ne pas exécuter avant l'échec terminal V5

Depuis `C:\dev\lca-simu-pr40` :

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_balanced_product_delay_multiseed_refinement_v6 plan `
  --output-dir <PLAN_DEVELOPPEMENT_V6> `
  --v5-plan-dir <PLAN_V5_TERMINE> `
  --v5-run-dir <RUN_V5_TERMINE> `
  --v5-sidecar-root <SIDECAR_V5_ABSENT_OU_VIDE>
```

Cette commande crée seulement un plan signé. Elle ne lance pas le moteur.

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_balanced_product_delay_multiseed_refinement_v6 validate `
  --plan-dir <PLAN_DEVELOPPEMENT_V6>
```

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_balanced_product_delay_multiseed_refinement_v6 run-development `
  --plan-dir <PLAN_DEVELOPPEMENT_V6> `
  --run-dir <RUN_DEVELOPPEMENT_V6> `
  --workers 2
```

```powershell
python -m etudecas.prototypes.scan_2027_risk_control.supplier_balanced_product_delay_multiseed_refinement_v6 finalize-development `
  --plan-dir <PLAN_DEVELOPPEMENT_V6> `
  --run-dir <RUN_DEVELOPPEMENT_V6>
```

Il n'existe volontairement aucune commande `run-holdout`.

## Résultats attendus

Le développement contient 150 preuves signées :

- 30 preuves V5 importées pour le fonctionnement à 100 % ;
- 60 preuves V5 importées pour les deux configurations à 93 % ;
- 60 nouvelles preuves V6 pour les deux configurations à 80 %.

La synthèse applique sans modification les règles V4/V5 : moyenne regroupée et
médiane dans la bande intérieure 79,25–80,75 %, toutes les estimations obtenues
en retirant une répétition dans la bande 78,5–81,5 %, aucun produit saturé, et
ordre strict 100 % > 93 % > 80 % sur au moins 24 des 30 répétitions.

En cas de succès, le statut est
`development_selected_pending_separate_fresh_holdout_protocol`. Il signifie :
le point est sélectionné en développement, mais aucune validation finale n'est
encore autorisée. Il faut alors figer et contrôler un protocole séparé avant de
révéler ou d'exécuter les graines conservées à part.

En cas d'échec, le statut reste `development_failed_no_holdout` et aucune
validation finale ne doit être lancée.

## Contrôles techniques avant usage éventuel

```powershell
python -m py_compile etudecas\prototypes\scan_2027_risk_control\supplier_balanced_product_delay_multiseed_refinement_v6.py
ruff check etudecas\prototypes\scan_2027_risk_control\supplier_balanced_product_delay_multiseed_refinement_v6.py etudecas\prototypes\scan_2027_risk_control\tests\test_supplier_balanced_product_delay_multiseed_refinement_v6.py
python -m pytest -q etudecas\prototypes\scan_2027_risk_control\tests\test_supplier_balanced_product_delay_multiseed_refinement_v6.py
```

Le test bout en bout vérifie notamment que seulement 60 appels moteur ont lieu,
que les fichiers sources V5 restent identiques avant et après V6, et qu'aucune
trace de validation finale n'est créée.

## Empreintes auditées le 5 septembre 2026

| Fichier | SHA-256 |
|---|---|
| `supplier_balanced_product_delay_multiseed_refinement_v6.py` | `a12a835d376d17a2fd8fee54bb31bc37aa228a542da5417099bb267f2fe9847c` |
| `tests/test_supplier_balanced_product_delay_multiseed_refinement_v6.py` | `d3c039ea25556606cb6e3ff4546daf77ad13f56f51a6f39bb3f310f9be2d47c2` |

Toute différence impose un nouvel audit avant lancement ou reprise.
