# Audit stock composant Pharma - PF 268967 / D1430

## Lecture courte

- Mapping corrige: `268967` correspond a `Stock_Composants*_Pharma.csv` et a l'usine `M-1430`.
- Le KPI reel Pharma n'est pas comparable au stock brut simule PFI inclus. Les PFI internes doivent etre exclus du KPI composant fournisseur.
- Stock composant direct simule: moyenne 960 771 EUR vs reel 259 678 EUR, ecart 701 093 EUR (270.0%).
- Stock utile selon cible MRP: moyenne 378 432 EUR, MAE 118 753 EUR.
- Couverture utile courte: premier snapshot 222 023 EUR vs reel 220 644 EUR, mais moyenne annuelle 57 261 EUR; ce n'est donc pas une regle stable seule.
- La premiere campagne 268967 est reportee jusqu'au J70 apres 70 reports. Blocage principal: `item:344135` (70 evenements).

## Meilleures regles candidates

| rule | real_mean_eur | sim_mean_eur | bias_eur | mae_eur | corr | first_real_eur | first_sim_eur |
| --- | --- | --- | --- | --- | --- | --- | --- |
| subset/target_stock/useful/038005+333362 | 259678.40 | 249453.00 | -10225.40 | 31350.49 | 0.51 | 220644.25 | 210689.42 |
| subset/target_stock/useful/038005+333362+344135 | 259678.40 | 251843.00 | -7835.40 | 31580.94 | 0.51 | 220644.25 | 210689.42 |
| subset/target_stock/useful/038005+333362+734545 | 259678.40 | 252158.33 | -7520.07 | 31591.44 | 0.51 | 220644.25 | 211389.20 |
| subset/target_stock/useful/038005+333362+344135+734545 | 259678.40 | 254548.34 | -5130.06 | 31821.89 | 0.51 | 220644.25 | 211389.20 |
| subset/target_stock/useful/038005+333362+708073 | 259678.40 | 272706.01 | 13027.61 | 35860.60 | 0.51 | 220644.25 | 241378.67 |
| subset/target_stock/useful/038005+333362+344135+708073 | 259678.40 | 275096.02 | 15417.62 | 36653.79 | 0.51 | 220644.25 | 241378.67 |
| subset/target_stock/useful/038005+333362+708073+734545 | 259678.40 | 275411.34 | 15732.94 | 37038.30 | 0.50 | 220644.25 | 242078.46 |
| target_stock/useful/exclude_042342/direct_only | 259678.40 | 277801.35 | 18122.95 | 37831.50 | 0.51 | 220644.25 | 242078.46 |
| subset/target_stock/useful/038005+333362+344135+708073+734545 | 259678.40 | 277801.35 | 18122.95 | 37831.50 | 0.51 | 220644.25 | 242078.46 |
| coverage/stock/only_042342/direct_only | 259678.40 | 252357.07 | -7321.33 | 50458.26 | -0.18 | 220644.25 | 174037.49 |
| demand_180d/stock/only_042342/direct_only | 259678.40 | 252357.07 | -7321.33 | 50458.26 | -0.18 | 220644.25 | 174037.49 |
| demand_90d/stock/only_042342/direct_only | 259678.40 | 252357.07 | -7321.33 | 50458.26 | -0.18 | 220644.25 | 174037.49 |

## Premier snapshot reel

- Photo reelle: 2025-01-06 -> jour source 5, compare au stock fin J4: 220 644 EUR.

| threshold_mode | component_code | component_type | stock_value_eur | useful_value_eur | immobilized_value_eur | stock_qty | useful_qty | lead_days | standard_lot_qty |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| coverage | 042342 | MP | 174037.49 | 100630.30 | 73407.19 | 78749996.00 | 45534073.20 | 21.00 | 30000000.00 |
| coverage | 038005 | MP | 171825.29 | 60346.29 | 111479.00 | 37598.53 | 13204.88 | 154.00 | 10000.00 |
| coverage | 333362 | Pack | 38864.12 | 38864.12 | 0.00 | 142250.00 | 754600.00 | 60.00 | 5000.00 |
| coverage | 708073 | Pack | 37073.50 | 21482.48 | 15591.02 | 10326.88 | 5983.98 | 28.00 | 5000000.00 |
| coverage | 734545 | Pack | 699.79 | 699.79 | 0.00 | 1641.00 | 6036.80 | 21.00 | 6300.00 |
| coverage | 344135 | Pack | 0.00 | 0.00 | 0.00 | 0.00 | 754600.00 | 35.00 | 120000.00 |
| target_stock | 042342 | MP | 174037.49 | 100630.30 | 73407.19 | 78749996.00 | 45534073.20 | 21.00 | 30000000.00 |
| target_stock | 038005 | MP | 171825.29 | 171825.29 | 0.00 | 37598.53 | 37728.22 | 154.00 | 10000.00 |
| target_stock | 333362 | Pack | 38864.12 | 38864.12 | 0.00 | 142250.00 | 1078000.00 | 60.00 | 5000.00 |
| target_stock | 708073 | Pack | 37073.50 | 30689.26 | 6384.24 | 10326.88 | 8548.54 | 28.00 | 5000000.00 |
| target_stock | 734545 | Pack | 699.79 | 699.79 | 0.00 | 1641.00 | 8624.00 | 21.00 | 6300.00 |
| target_stock | 344135 | Pack | 0.00 | 0.00 | 0.00 | 0.00 | 1078000.00 | 35.00 | 120000.00 |

## Contributeurs du stock direct

| component_code | component_type | mean_stock_value_eur | first_stock_value_eur | mean_useful_value_eur | mean_immobilized_value_eur | unit_value_eur | lead_days | standard_lot_qty |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 038005 | MP | 322732.95 | 171825.29 | 68320.47 | 254412.47 | 4.57 | 154.00 | 10000.00 |
| 333362 | Pack | 182446.92 | 38864.12 | 168250.01 | 14196.91 | 0.27 | 60.00 | 5000.00 |
| 042342 | MP | 154653.27 | 174037.49 | 97307.80 | 57345.48 | 0.00 | 21.00 | 30000000.00 |
| 708073 | Pack | 36126.07 | 37073.50 | 21929.70 | 14196.37 | 3.59 | 28.00 | 5000000.00 |
| 734545 | Pack | 4580.01 | 699.79 | 2607.90 | 1972.11 | 0.43 | 21.00 | 6300.00 |
| 344135 | Pack | 3829.58 | 0.00 | 2820.39 | 1009.19 | 0.00 | 35.00 | 120000.00 |

## Flux physiques simules sur 5 ans

| item_id | initial_qty | final_qty | total_arrivals_qty | implied_consumption_qty | component_item_id | component_code | component_type | bom_qty_per_1000 | bom_uom |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| item:038005 | 37598.53 | 34981.81 | 120000.00 | 122616.73 | item:038005 | 038005 | MP | 17499.18 | G |
| item:042342 | 78749996.00 | 45933602.00 | 390000000.00 | 422816394.00 | item:042342 | 042342 | MP | 60342.00 | UN. |
| item:333362 | 142250.00 | 864250.00 | 7729000.00 | 7007000.00 | item:333362 | 333362 | Pack | 1000.00 | UN. |
| item:344135 | 0.00 | 1033000.00 | 8040000.00 | 7007000.00 | item:344135 | 344135 | Pack | 1000.00 | UN. |
| item:708073 | 10326.88 | 9761.37 | 55000.00 | 55565.51 | item:708073 | 708073 | Pack | 7930.00 | G |
| item:730384 | 68387.00 | 432903.00 | 1850000.00 | 1485484.00 | item:730384 | 730384 | Pack | 212.00 | M |
| item:734545 | 1641.00 | 8685.00 | 63100.00 | 56056.00 | item:734545 | 734545 | Pack | 8.00 | UN. |
| item:773474 | 14593000.00 | 20414458.97 | 73472068.00 | 67650609.03 | item:773474 | 773474 | MP | 9654.72 | G |

## Reports de production 268967

| binding_input_item_id | delay_events | first_delay_day | last_delay_day | delayed_qty |
| --- | --- | --- | --- | --- |
| item:344135 | 70 | 0 | 69 | 7546000.00 |

## Conclusion diagnostic

- L'ecart Pharma residuel vient surtout du perimetre de valorisation et de la dynamique de reapprovisionnement: les gros composants directs `038005`, `042342` et `333362` portent l'essentiel de la valeur simulee.
- Le premier point reel est proche d'une lecture 'stock utile de couverture', mais cette lecture ne reproduit pas toute l'annee.
- Pour fermer l'ecart sans regle arbitraire, il faut soit le detail article du KPI reel Pharma, soit aligner explicitement la simulation sur la meme definition finance: stock physique, stock disponible utile, stock bloque/qualite, ou stock net des besoins engages.