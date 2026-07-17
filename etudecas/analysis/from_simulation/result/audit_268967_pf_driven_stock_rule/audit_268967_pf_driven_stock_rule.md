# Audit regles PF -> stock composant Pharma - 268967

## Lecture courte

- Stock composant reel Pharma moyen: 259 678 EUR.
- Stock PF reel moyen: 1 534 650 EUR; conversion indicative PF: 2.436 EUR/unite, issue du premier snapshot PF reel / stock DC simule au meme jour.
- Stock PF source au 01/01/2025: 1,101,534 UN. Le PF couvre donc deja une grande partie du debut d'annee; le stock composant ne doit pas etre lu comme tout le besoin futur brut.
- Premiere campagne usine reportee J0 -> J70: 70 reports, cause dominante `item:344135`.

## Cout BOM par unite PF

| component_code | component_type | qty_per_pf | unit_price_eur | cost_per_pf_unit_eur | is_internal_pfi | is_unpriced |
| --- | --- | --- | --- | --- | --- | --- |
| 038005 | MP | 0.02 | 4.57 | 0.08 | False | False |
| 042342 | MP | 60.34 | 0.00 | 0.13 | False | False |
| 773474 | MP | 9.65 | 0.00 | 0.00 | True | True |
| 333362 | Pack | 1.00 | 0.27 | 0.27 | False | False |
| 344135 | Pack | 1.00 | 0.00 | 0.00 | False | False |
| 708073 | Pack | 0.01 | 3.59 | 0.03 | False | False |
| 730384 | Pack | 0.21 | 0.00 | 0.00 | False | True |
| 734545 | Pack | 0.01 | 0.43 | 0.00 | False | False |

## Meilleures regles PF candidates

| variant | component_set | horizon_weeks | week_offset | cost_per_pf_unit_eur | sim_mean_eur | bias_eur | mae_eur | corr | first_real_eur | first_sim_eur |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| min_future_and_real_pf_stock | all_direct_priced | 17 | -2 | 0.52 | 222777.56 | -36900.84 | 58530.41 | -0.49 | 220644.25 | 267904.17 |
| gross_future_demand | all_direct_priced | 16 | -2 | 0.52 | 222641.66 | -37036.74 | 59292.52 | -0.38 | 220644.25 | 247835.93 |
| min_future_and_real_pf_stock | all_direct_priced | 16 | -2 | 0.52 | 215235.75 | -44442.65 | 59473.93 | -0.44 | 220644.25 | 247835.93 |
| gross_future_demand | all_direct_priced | 17 | -2 | 0.52 | 233709.61 | -25968.79 | 59733.38 | -0.39 | 220644.25 | 267904.17 |
| lot_ceiled_future_demand | no_042342 | 20 | -2 | 0.39 | 215366.61 | -44311.79 | 61024.89 | -0.39 | 220644.25 | 167776.24 |
| lot_ceiled_future_demand | all_direct_priced | 15 | -2 | 0.52 | 240442.29 | -19236.11 | 61031.21 | -0.36 | 220644.25 | 281599.08 |
| min_future_and_real_pf_stock | all_direct_priced | 18 | -2 | 0.52 | 229458.66 | -30219.74 | 61591.83 | -0.54 | 220644.25 | 250996.21 |
| lot_ceiled_future_demand | no_042342 | 19 | -2 | 0.39 | 208913.68 | -50764.72 | 62029.02 | -0.41 | 220644.25 | 209720.29 |
| lot_ceiled_future_demand | all_direct_priced | 16 | -2 | 0.52 | 245857.66 | -13820.74 | 62522.26 | -0.37 | 220644.25 | 281599.08 |
| gross_future_demand | all_direct_priced | 15 | -2 | 0.52 | 211233.58 | -48444.82 | 63737.26 | -0.34 | 220644.25 | 230149.52 |
| min_future_and_real_pf_stock | all_direct_priced | 15 | -2 | 0.52 | 206709.46 | -52968.94 | 63819.85 | -0.38 | 220644.25 | 230149.52 |
| gross_future_demand | all_direct_priced | 18 | -2 | 0.52 | 244391.64 | -15286.76 | 63959.47 | -0.40 | 220644.25 | 250996.21 |
| min_future_and_real_pf_stock | all_direct_priced | 17 | -1 | 0.52 | 219094.56 | -40583.84 | 64107.26 | -0.53 | 220644.25 | 250996.21 |
| min_future_and_real_pf_stock | all_direct_priced | 19 | -2 | 0.52 | 236342.24 | -23336.16 | 64285.00 | -0.57 | 220644.25 | 230621.81 |
| gross_future_demand | all_direct_priced | 17 | -1 | 0.52 | 229239.23 | -30439.17 | 64392.99 | -0.44 | 220644.25 | 250996.21 |

## Meilleures regles demande brute future

| variant | component_set | horizon_weeks | week_offset | sim_mean_eur | bias_eur | mae_eur | corr |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gross_future_demand | all_direct_priced | 16 | -2 | 222641.66 | -37036.74 | 59292.52 | -0.38 |
| gross_future_demand | all_direct_priced | 17 | -2 | 233709.61 | -25968.79 | 59733.38 | -0.39 |
| gross_future_demand | all_direct_priced | 15 | -2 | 211233.58 | -48444.82 | 63737.26 | -0.34 |
| gross_future_demand | all_direct_priced | 18 | -2 | 244391.64 | -15286.76 | 63959.47 | -0.40 |
| gross_future_demand | all_direct_priced | 17 | -1 | 229239.23 | -30439.17 | 64392.99 | -0.44 |
| gross_future_demand | all_direct_priced | 16 | -1 | 218557.21 | -41121.19 | 64496.05 | -0.43 |
| gross_future_demand | no_042342 | 21 | -2 | 207270.30 | -52408.10 | 66232.30 | -0.44 |
| gross_future_demand | all_direct_priced | 18 | -1 | 240246.41 | -19431.99 | 66954.52 | -0.43 |
| gross_future_demand | no_042342 | 22 | -2 | 215582.53 | -44095.87 | 67590.55 | -0.48 |
| gross_future_demand | all_direct_priced | 15 | -1 | 207489.25 | -52189.15 | 68405.01 | -0.42 |

## Meilleures regles avec stock PF reel

| variant | component_set | horizon_weeks | week_offset | sim_mean_eur | bias_eur | mae_eur | corr |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lot_ceiled_net_future | all_direct_priced | 41 | -2 | 157045.64 | -102632.76 | 131542.91 | -0.56 |
| lot_ceiled_net_future | all_direct_priced | 42 | -2 | 161377.93 | -98300.47 | 132329.92 | -0.55 |
| lot_ceiled_net_future | all_direct_priced | 42 | -1 | 154879.49 | -104798.91 | 133380.96 | -0.56 |
| lot_ceiled_net_future | all_direct_priced | 43 | -2 | 167876.38 | -91802.02 | 133386.75 | -0.57 |
| lot_ceiled_net_future | all_direct_priced | 44 | -2 | 170042.52 | -89635.88 | 133386.75 | -0.59 |
| lot_ceiled_net_future | no_042342 | 51 | -2 | 137931.42 | -121746.98 | 133763.42 | -0.64 |
| lot_ceiled_net_future | all_direct_priced | 39 | -2 | 148381.05 | -111297.35 | 134045.69 | -0.52 |
| lot_ceiled_net_future | all_direct_priced | 40 | -2 | 153796.42 | -105881.98 | 134245.61 | -0.54 |
| lot_ceiled_net_future | no_042342 | 46 | -2 | 131478.49 | -128199.91 | 134275.13 | -0.61 |
| lot_ceiled_net_future | no_042342 | 47 | -2 | 133091.72 | -126586.68 | 134275.13 | -0.61 |

## Ruptures PF projetees source

| year_week | shortage_weeks | shortage_repetition |
| --- | --- | --- |
| 2025|01 | 0.00 | 0.00 |
| 2025|05 | 0.00 | 0.00 |
| 2025|09 | 0.00 | 0.00 |
| 2025|14 | 0.00 | 0.00 |
| 2025|18 | 0.00 | 0.00 |
| 2025|22 | 0.00 | 0.00 |
| 2025|27 | 0.00 | 0.00 |
| 2025|31 | 0.00 | 0.00 |
| 2025|35 | 0.00 | 0.00 |
| 2025|40 | 0.00 | 0.00 |
| 2025|44 | 0.00 | 0.00 |
| 2025|48 | 0.00 | 0.00 |
| 2026|01 | 0.00 | 0.00 |
| 2026|05 | 0.00 | 0.00 |
| 2026|09 | 5.00 | 4.00 |
| 2026|10 | 5.00 | 4.00 |
| 2026|11 | 6.00 | 3.00 |
| 2026|12 | 6.00 | 5.00 |
| 2026|13 | 6.00 | 5.00 |
| 2026|14 | 6.00 | 5.00 |
| 2026|15 | 11.00 | 6.00 |
| 2026|16 | 5.00 | 3.00 |
| 2026|17 | 4.00 | 2.00 |
| 2026|18 | 5.00 | 3.00 |
| 2026|19 | 5.00 | 4.00 |
| 2026|20 | 6.00 | 5.00 |
| 2026|21 | 4.00 | 3.00 |
| 2026|22 | 3.00 | 3.00 |
| 2026|23 | 5.00 | 4.00 |
| 2026|24 | 6.00 | 4.00 |

## Blocage premiere campagne 268967

- `344135` a un stock initial nul et aucune ligne ouverte dans `Extract_En_cours.xlsx`; la simulation genere ensuite une commande MRP, disponible seulement J70.
- Le premier lot demande 107 800 UN de `344135`; la premiere reception de 240 000 UN arrive J70, ce qui debloque le lot.

| row_type | day | item_id | stock_before_production | stock_end_of_day | uom |
| --- | --- | --- | --- | --- | --- |
| stock_snapshot | 0 | item:038005 | 37598.5325 | 37598.53 |  |
| stock_snapshot | 0 | item:042342 | 78749996.0 | 78749996.00 |  |
| stock_snapshot | 0 | item:333362 | 142250.0 | 142250.00 |  |
| stock_snapshot | 0 | item:344135 | 0.0 | 0.00 |  |
| stock_snapshot | 0 | item:708073 | 10326.88 | 10326.88 |  |
| stock_snapshot | 0 | item:734545 | 1641.0 | 1641.00 |  |
| stock_snapshot | 0 | item:773474 | 14593000.0 | 14593000.00 |  |
| stock_snapshot | 34 | item:038005 | 47598.5325 | 47598.53 |  |
| stock_snapshot | 34 | item:042342 | 78749996.0 | 78749996.00 |  |
| stock_snapshot | 34 | item:333362 | 142250.0 | 142250.00 |  |
| stock_snapshot | 34 | item:344135 | 0.0 | 0.00 |  |
| stock_snapshot | 34 | item:708073 | 10326.88 | 10326.88 |  |
| stock_snapshot | 34 | item:734545 | 8041.0 | 8041.00 |  |
| stock_snapshot | 34 | item:773474 | 20815573.0 | 20815573.00 |  |
| stock_snapshot | 36 | item:038005 | 47598.5325 | 47598.53 |  |
| stock_snapshot | 36 | item:042342 | 108749996.0 | 108749996.00 |  |
| stock_snapshot | 36 | item:333362 | 142250.0 | 142250.00 |  |
| stock_snapshot | 36 | item:344135 | 0.0 | 0.00 |  |
| stock_snapshot | 36 | item:708073 | 10326.88 | 10326.88 |  |
| stock_snapshot | 36 | item:734545 | 8041.0 | 8041.00 |  |
| stock_snapshot | 36 | item:773474 | 20815573.0 | 20815573.00 |  |
| stock_snapshot | 58 | item:038005 | 77598.5325 | 77598.53 |  |
| stock_snapshot | 58 | item:042342 | 138749996.0 | 138749996.00 |  |
| stock_snapshot | 58 | item:333362 | 247250.0 | 247250.00 |  |
| stock_snapshot | 58 | item:344135 | 0.0 | 0.00 |  |
| stock_snapshot | 58 | item:708073 | 10326.88 | 10326.88 |  |
| stock_snapshot | 58 | item:734545 | 14341.0 | 14341.00 |  |
| stock_snapshot | 58 | item:773474 | 20815573.0 | 20815573.00 |  |
| stock_snapshot | 63 | item:038005 | 77598.5325 | 77598.53 |  |
| stock_snapshot | 63 | item:042342 | 138749996.0 | 138749996.00 |  |
| stock_snapshot | 63 | item:333362 | 397250.0 | 397250.00 |  |
| stock_snapshot | 63 | item:344135 | 0.0 | 0.00 |  |
| stock_snapshot | 63 | item:708073 | 10326.88 | 10326.88 |  |
| stock_snapshot | 63 | item:734545 | 14341.0 | 14341.00 |  |
| stock_snapshot | 63 | item:773474 | 20815573.0 | 20815573.00 |  |
| stock_snapshot | 68 | item:038005 | 87598.5325 | 87598.53 |  |
| stock_snapshot | 68 | item:042342 | 138749996.0 | 138749996.00 |  |
| stock_snapshot | 68 | item:333362 | 397250.0 | 397250.00 |  |
| stock_snapshot | 68 | item:344135 | 0.0 | 0.00 |  |
| stock_snapshot | 68 | item:708073 | 10326.88 | 10326.88 |  |
| stock_snapshot | 68 | item:734545 | 14341.0 | 14341.00 |  |
| stock_snapshot | 68 | item:773474 | 20815573.0 | 20815573.00 |  |
| stock_snapshot | 69 | item:038005 | 97598.5325 | 97598.53 |  |
| stock_snapshot | 69 | item:042342 | 138749996.0 | 138749996.00 |  |
| stock_snapshot | 69 | item:333362 | 397250.0 | 397250.00 |  |
| stock_snapshot | 69 | item:344135 | 0.0 | 0.00 |  |
| stock_snapshot | 69 | item:708073 | 10326.88 | 10326.88 |  |
| stock_snapshot | 69 | item:734545 | 14341.0 | 14341.00 |  |
| stock_snapshot | 69 | item:773474 | 20815573.0 | 20815573.00 |  |
| stock_snapshot | 70 | item:038005 | 97598.5325 | 95712.12 |  |
| stock_snapshot | 70 | item:042342 | 138749996.0 | 132245128.40 |  |
| stock_snapshot | 70 | item:333362 | 521250.0 | 413450.00 |  |
| stock_snapshot | 70 | item:344135 | 240000.0 | 132200.00 |  |
| stock_snapshot | 70 | item:708073 | 10326.88 | 9472.03 |  |
| stock_snapshot | 70 | item:734545 | 14341.0 | 13478.60 |  |
| stock_snapshot | 70 | item:773474 | 20815573.0 | 19774794.40 |  |
| stock_snapshot | 71 | item:038005 | 95712.121327 | 95712.12 |  |
| stock_snapshot | 71 | item:042342 | 132245128.4 | 132245128.40 |  |
| stock_snapshot | 71 | item:333362 | 413450.0 | 413450.00 |  |
| stock_snapshot | 71 | item:344135 | 252200.0 | 252200.00 |  |
| stock_snapshot | 71 | item:708073 | 9472.026 | 9472.03 |  |
| stock_snapshot | 71 | item:734545 | 13478.6 | 13478.60 |  |
| stock_snapshot | 71 | item:773474 | 19774794.3996 | 19774794.40 |  |
| stock_snapshot | 77 | item:038005 | 105712.121327 | 105712.12 |  |
| stock_snapshot | 77 | item:042342 | 132245128.4 | 132245128.40 |  |
| stock_snapshot | 77 | item:333362 | 458450.0 | 458450.00 |  |
| stock_snapshot | 77 | item:344135 | 612200.0 | 612200.00 |  |
| stock_snapshot | 77 | item:708073 | 9472.026 | 9472.03 |  |
| stock_snapshot | 77 | item:734545 | 13478.6 | 13478.60 |  |
| stock_snapshot | 77 | item:773474 | 19774794.3996 | 19774794.40 |  |
| arrival | 5 | item:734545 |  | 6400.00 | UN |
| arrival | 10 | item:773474 |  | 518548.00 | G |
| arrival | 11 | item:773474 |  | 518548.00 | G |
| arrival | 12 | item:773474 |  | 518548.00 | G |
| arrival | 13 | item:773474 |  | 518548.00 | G |
| arrival | 14 | item:773474 |  | 518548.00 | G |
| arrival | 15 | item:773474 |  | 518548.00 | G |
| arrival | 16 | item:773474 |  | 518548.00 | G |
| arrival | 17 | item:773474 |  | 518548.00 | G |
| arrival | 18 | item:773474 |  | 518548.00 | G |

## Conclusion

- La meilleure regle PF pure est du type `demande future N semaines x cout BOM`, autour de 16 a 19 semaines selon le perimetre, mais elle reste moins bonne que la lecture composant/MRP: erreur autour de 59 kEUR au mieux et correlation negative.
- Donc le KPI reel Pharma ne semble pas etre directement une regle simple issue du PF seul. Le PF explique le niveau cible global, mais le detail article/MRP explique mieux la valeur observee.
- Pour rendre cela propre dans la simulation, il faut distinguer trois KPI: stock PF disponible, besoin composant couvert par PF/demande future, et stock composant utile/excedentaire par article.