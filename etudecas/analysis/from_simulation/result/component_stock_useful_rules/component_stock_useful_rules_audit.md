# Audit stock composant immobilise - regles de stock utile

Perimetre: composants des PF 268091 et 268967, PFI/roll-up internes exclus de la lecture principale.
Comparaison: photos source hebdomadaires vers cloture simulation de la veille.

## Stock utile implicite depuis les donnees source

Formule demandee: stock composants source au 01/01 - consommation BOM semaine 1 - premier stock immobilise reel.

| PF | Stock composants source 01/01 | Conso semaine 1 | Stock apres conso | Premier immobilise reel | Stock utile implicite | Date photo reelle |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 268091 | 726 887 EUR | 6 349 EUR | 720 538 EUR | 656 922 EUR | 63 616 EUR | 2025-01-06 00:05:56 |
| 268967 | 422 500 EUR | 9 373 EUR | 413 127 EUR | 220 644 EUR | 192 483 EUR | 2025-01-06 00:05:56 |

## Meme lecture cote simulation

Formule: stock composants simule debut J0 - consommation simulee de la periode - immobilise simule en fin de periode.

| PF | Periode | Stock sim debut J0 | Conso sim | Apres conso | Immobilise sim | Utile implicite sim | Utile MRP sim |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 268091 | J0-J4 | 726 887 EUR | 6 874 EUR | 720 013 EUR | 334 308 EUR | 385 705 EUR | 385 705 EUR |
| 268091 | J0-J5 | 726 887 EUR | 6 874 EUR | 720 013 EUR | 334 308 EUR | 385 705 EUR | 385 705 EUR |
| 268091 | J0-J6 | 726 887 EUR | 6 874 EUR | 720 013 EUR | 334 308 EUR | 385 705 EUR | 385 705 EUR |
| 268967 | J0-J4 | 422 500 EUR | 0 EUR | 422 500 EUR | 30 280 EUR | 392 220 EUR | 392 220 EUR |
| 268967 | J0-J5 | 422 500 EUR | 0 EUR | 422 500 EUR | 30 280 EUR | 392 220 EUR | 394 949 EUR |
| 268967 | J0-J6 | 422 500 EUR | 0 EUR | 422 500 EUR | 30 280 EUR | 392 220 EUR | 394 949 EUR |

## Diagnostic des regles sur stock simule

Cette section reste un diagnostic modele: elle part du stock physique simule moyen, pas de la photo source du 01/01.

| PF | Regle | Reel moyen | Simulation | Ecart | MAE | Stock physique sim | Stock utile candidat | Utile implicite depuis stock simule |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 268091 | `excess_vs_future_need_180d` | 930 695 EUR | 942 375 EUR | 11 680 EUR (1.3%) | 139 182 EUR | 1 423 062 EUR | 480 687 EUR | 494 028 EUR |
| 268967 | `excess_vs_max_safety_coverage` | 259 678 EUR | 359 916 EUR | 100 237 EUR (38.6%) | 148 776 EUR | 1 038 815 EUR | 678 900 EUR | 779 137 EUR |

## Regles candidates principales

| PF | Regle | Reel moyen | Simulation | Bias | MAE | Corr | Utile candidat | Utile implique | Biais utile |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 268091 | `excess_vs_future_need_180d` | 930 695 EUR | 942 375 EUR | 11 680 EUR (1.3%) | 139 182 EUR | 0.05 | 480 687 EUR | 494 028 EUR | -13 341 EUR |
| 268091 | `excess_vs_coverage` | 930 695 EUR | 883 137 EUR | -47 558 EUR (-5.1%) | 144 186 EUR | 0.52 | 539 924 EUR | 494 028 EUR | 45 896 EUR |
| 268091 | `excess_vs_safety_plus_coverage` | 930 695 EUR | 870 128 EUR | -60 567 EUR (-6.5%) | 146 903 EUR | 0.52 | 552 934 EUR | 494 028 EUR | 58 905 EUR |
| 268091 | `excess_vs_future_need_90d` | 930 695 EUR | 1 199 256 EUR | 268 561 EUR (28.9%) | 319 211 EUR | 0.31 | 223 806 EUR | 494 028 EUR | -270 222 EUR |
| 268091 | `excess_vs_max_safety_coverage` | 930 695 EUR | 610 717 EUR | -319 978 EUR (-34.4%) | 319 978 EUR | 0.54 | 812 345 EUR | 494 028 EUR | 318 317 EUR |
| 268091 | `excess_vs_target_stock` | 930 695 EUR | 610 717 EUR | -319 978 EUR (-34.4%) | 319 978 EUR | 0.54 | 812 345 EUR | 494 028 EUR | 318 317 EUR |
| 268091 | `excess_vs_future_need_60d` | 930 695 EUR | 1 285 447 EUR | 354 752 EUR (38.1%) | 374 993 EUR | 0.46 | 137 615 EUR | 494 028 EUR | -356 413 EUR |
| 268091 | `excess_vs_future_need_30d` | 930 695 EUR | 1 358 551 EUR | 427 856 EUR (46.0%) | 434 087 EUR | 0.49 | 64 511 EUR | 494 028 EUR | -429 517 EUR |
| 268091 | `physical_stock_value` | 930 695 EUR | 1 423 062 EUR | 492 367 EUR (52.9%) | 495 690 EUR | 0.52 | 0 EUR | 494 028 EUR | -494 028 EUR |
| 268091 | `excess_vs_demand_90d` | 930 695 EUR | 221 623 EUR | -709 072 EUR (-76.2%) | 709 072 EUR | 0.43 | 1 201 439 EUR | 494 028 EUR | 707 410 EUR |
| 268967 | `excess_vs_max_safety_coverage` | 259 678 EUR | 359 916 EUR | 100 237 EUR (38.6%) | 148 776 EUR | 0.29 | 678 900 EUR | 779 137 EUR | -100 237 EUR |
| 268967 | `excess_vs_target_stock` | 259 678 EUR | 359 916 EUR | 100 237 EUR (38.6%) | 148 776 EUR | 0.29 | 678 900 EUR | 779 137 EUR | -100 237 EUR |
| 268967 | `excess_vs_demand_90d` | 259 678 EUR | 0 EUR | -259 678 EUR (-100.0%) | 259 678 EUR | nan | 1 038 815 EUR | 779 137 EUR | 259 678 EUR |
| 268967 | `excess_vs_safety_plus_coverage` | 259 678 EUR | 535 082 EUR | 275 403 EUR (106.1%) | 294 024 EUR | 0.32 | 503 734 EUR | 779 137 EUR | -275 403 EUR |
| 268967 | `excess_vs_coverage` | 259 678 EUR | 553 747 EUR | 294 069 EUR (113.2%) | 311 462 EUR | 0.35 | 485 068 EUR | 779 137 EUR | -294 069 EUR |
| 268967 | `excess_vs_future_need_180d` | 259 678 EUR | 782 759 EUR | 523 080 EUR (201.4%) | 523 080 EUR | 0.14 | 256 057 EUR | 779 137 EUR | -523 080 EUR |
| 268967 | `excess_vs_future_need_90d` | 259 678 EUR | 926 234 EUR | 666 556 EUR (256.7%) | 666 556 EUR | 0.35 | 112 581 EUR | 779 137 EUR | -666 556 EUR |
| 268967 | `excess_vs_future_need_60d` | 259 678 EUR | 964 142 EUR | 704 463 EUR (271.3%) | 704 463 EUR | 0.38 | 74 674 EUR | 779 137 EUR | -704 463 EUR |
| 268967 | `excess_vs_future_need_30d` | 259 678 EUR | 1 008 523 EUR | 748 844 EUR (288.4%) | 748 844 EUR | 0.40 | 30 293 EUR | 779 137 EUR | -748 844 EUR |
| 268967 | `physical_stock_value` | 259 678 EUR | 1 038 815 EUR | 779 137 EUR (300.0%) | 779 137 EUR | 0.43 | 0 EUR | 779 137 EUR | -779 137 EUR |

## Regles communes aux deux PF

| Regle | MAE moyen pondere | Bias moyen pondere | MAE moyenne relative |
| --- | ---: | ---: | ---: |
| `excess_vs_safety_plus_coverage` | 440 928 EUR | 214 837 EUR (18.0%) | 37.0% |
| `excess_vs_future_need_365d` | 444 484 EUR | -5 829 EUR (-0.5%) | 37.3% |
| `excess_vs_coverage` | 455 648 EUR | 246 511 EUR (20.7%) | 38.3% |
| `excess_vs_max_safety_coverage` | 468 754 EUR | -219 741 EUR (-18.5%) | 39.4% |
| `excess_vs_target_stock` | 468 754 EUR | -219 741 EUR (-18.5%) | 39.4% |
| `excess_vs_future_need_270d` | 482 859 EUR | 198 846 EUR (16.7%) | 40.6% |
| `excess_vs_future_need_180d` | 662 263 EUR | 534 760 EUR (44.9%) | 55.6% |
| `excess_vs_future_need_120d` | 879 467 EUR | 798 048 EUR (67.0%) | 73.9% |
| `excess_vs_demand_90d` | 968 750 EUR | -968 750 EUR (-81.4%) | 81.4% |
| `excess_vs_future_need_90d` | 985 767 EUR | 935 117 EUR (78.6%) | 82.8% |

## Lecture des causes

- Cause 1 / cible MRP: si `excess_vs_target_stock` est trop bas, la cible utile MRP est trop haute; s'il est trop haut, la cible utile MRP est trop basse.
- Cause 3 / prix-perimetre: les composants a prix source nul ou manquant ne peuvent pas expliquer une surevaluation; ils sous-valorisent plutot la simulation.
- Definition du stock utile: la colonne `Utile implique` vaut stock physique simule moins stock immobilise reel. Une bonne regle doit s'en rapprocher sur les deux PF.

## Prix source nuls sur composants BOM

| PF | Composant | Fournisseur | Prix unitaire source | Prix brut / base |
| --- | --- | --- | ---: | ---: |
| 268091 | 693055 | D1450 | 0 | 0 / 1000 |
| 268967 | 730384 | VD0508918A | 0 | 0 / 1000 |
| 268967 | 773474 | D1450 | 0 | 0 / 1000 |

## Top contributeurs valorises par PF

| PF | Composant | Valeur stock | Valeur utile MRP | Immobilise MRP | Prix unitaire | Source valeur |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 268091 | 049371 | 274 600 EUR | 166 681 EUR | 107 919 EUR | 14.65 | inventory_state_unit_value_basis |
| 268091 | 338929 | 255 038 EUR | 254 966 EUR | 72 EUR | 0.21585 | inventory_state_unit_value_basis |
| 268091 | 002612 | 243 370 EUR | 10 413 EUR | 232 957 EUR | 1.26 | inventory_state_unit_value_basis |
| 268091 | 338928 | 150 266 EUR | 150 266 EUR | 0 EUR | 0.14131 | inventory_state_unit_value_basis |
| 268091 | 007923 | 143 416 EUR | 19 834 EUR | 123 582 EUR | 2 | inventory_state_unit_value_basis |
| 268091 | 001893 | 111 450 EUR | 88 845 EUR | 22 605 EUR | 4.64 | inventory_state_unit_value_basis |
| 268091 | 001757 | 81 089 EUR | 35 899 EUR | 45 189 EUR | 5.43 | inventory_state_unit_value_basis |
| 268091 | 001848 | 42 604 EUR | 14 330 EUR | 28 274 EUR | 2.89 | inventory_state_unit_value_basis |
| 268967 | 038005 | 480 122 EUR | 238 596 EUR | 241 526 EUR | 4.57 | inventory_state_unit_value_basis |
| 268967 | 042342 | 257 333 EUR | 143 758 EUR | 113 576 EUR | 0.00221 | inventory_state_unit_value_basis |
| 268967 | 333362 | 244 920 EUR | 244 920 EUR | 0 EUR | 0.27321 | inventory_state_unit_value_basis |
| 268967 | 708073 | 45 693 EUR | 42 172 EUR | 3 521 EUR | 3.59 | inventory_state_unit_value_basis |
| 268967 | 734545 | 6 278 EUR | 5 047 EUR | 1 231 EUR | 0.42644 | inventory_state_unit_value_basis |
| 268967 | 344135 | 4 469 EUR | 4 407 EUR | 61 EUR | 0.00403 | inventory_state_unit_value_basis |
