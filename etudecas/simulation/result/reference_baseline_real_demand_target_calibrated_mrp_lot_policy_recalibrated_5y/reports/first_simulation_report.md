# First simulation report

## Run setup
- Input: etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.json
- Scenario: scn:BASE
- Measured horizon (days): 1825
- Warm-up (days): 0
- Total simulated timeline (days): 1825
- Output profile: full
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 1.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 0.0 / 1.0 / 3.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: True / 1.0 / True
- Opening open-orders reconstruction enabled / horizon days: False / 0
- Opening open-orders demand multiplier / BOM signal for MRP: 1.0 / False
- MRP demand signal source: demand
- MRP demand signal smoothing / static fallback on propagated pairs: 1 j / True
- MRP physical safety floor enforced: False
- Soft safety-time physical stock target factor: 0.75
- Unmodeled supplier source mode: external_procurement
- Stochastic lead times: True
- Lead-time distribution mode: erlang
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 1.0
- Inventory cost split capital / warehouse / risk: 0.35 / 0.45 / 0.2
- Transport / purchase realism multipliers: 0.2 / 1.0
- External procurement enabled: True
- External procurement proactive supplier replenishment: True
- External procurement lead days: 4
- External procurement daily cap days: 2.0
- External procurement min daily cap qty: 0.0
- External procurement unit cost / multiplier / transport unit: 0.0 / 2.0 / 0.04
- Nodes: 33
- Edges: 39
- Lanes (edge x item): 39
- Demand rows: 2
- Input material pairs tracked: 24
- Output product pairs tracked: 3 (M-1430 | item:268967, M-1810 | item:268091, SDC-1450 | item:773474)
- Inputs non modelises par Relations_acteurs (non bloquants): 0 (none)
- Conversions d'unites BOM appliquees: 11
- Mismatch d'unites non convertis: 0
- Assumed supplier nodes (explicitly tagged, includes '?'): 0 (none)
- Assumed supply edges (explicitly tagged, includes '?'): 0 (none)
- External upstream sourcing for unmodeled source pairs: 34
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 0
- Opening open-order rows reconstructed from January snapshot: 0
- MRP trace tracked pairs / rows / orders: 65 / 118625 / 143505

## KPIs
- Total demand: 25762139.9999
- Total served: 25762139.9999
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 128506800.0
- Total shipped: 694962045.8724
- Avg inventory: 2171123523.4567
- Ending inventory: 1940406485.6388
- Transport cost: 5423398.129
- Holding cost (capital tied-up): 167817366.1697
- Warehouse operating cost: 215765185.0753
- Inventory risk cost (obsolescence/compliance proxy): 95895637.8112
- Legacy raw holding cost before split: 479478189.0562
- Purchase cost (from order_terms sell_price): 14459224.3114
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 484901587.1852
- Total cost: 499360811.4966
- Total external procured ordered qty: 21461235.7334
- Total external procured arrived qty: 21411235.7334
- Total external procured rejected qty (cap-limited): 59198.4881
- Total external procurement cost premium: 5305455.2468
- Total estimated source ordered qty: 0.0
- Total estimated source replenished qty: 1583944474.9346
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.336064 / 0.432083 / 0.192037 / 0.010861 / 0.028955
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 272405347.8265
- Total explicit initialization pipeline qty: 2059374837.9961
- Total opening open-order qty: 0.0
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 41421825.0
- Economic consistency status: warn
- Economic consistency warnings: ['transport_cost_share_below_2pct']

## Top backlog pairs
[]

## Safety stock reference
Calcul: `stock equiv delai = demande moyenne journaliere planifiee x delai de securite`. Les `safety_stock_qty` explicites sont ignores dans cette variante: seules les durees de securite pilotent la cible. La cible souple simulee applique le facteur `0.75` sur cette couverture.

| Scope | Noeud | Item | Delai secu j | Demande moy/j | Stock equiv delai | Cible souple sim | Unite |
|---|---:|---:|---:|---:|---:|---:|---|
| finished_good | DC-1920 | item:268091 | 20.0 | 1900.0 | 38000.0 | 28500.0 | UN |
| finished_good | DC-1920 | item:268967 | 25.0 | 2562.857143 | 64071.428575 | 48053.571431 | UN |
| input_material | M-1430 | item:038005 | 20.0 | 2694.873104 | 53897.46208 | 40423.09656 | KG |
| input_material | M-1430 | item:042342 | 5.0 | 9292668.0 | 46463340.0 | 34847505.0 | UN |
| input_material | M-1430 | item:333362 | 10.0 | 154000.0 | 1540000.0 | 1155000.0 | UN |
| input_material | M-1430 | item:344135 | 10.0 | 154000.0 | 1540000.0 | 1155000.0 | UN |
| input_material | M-1430 | item:708073 | 10.0 | 1221.22 | 12212.2 | 9159.15 | KG |
| input_material | M-1430 | item:730384 | 10.0 | 32648.0 | 326480.0 | 244860.0 | M |
| input_material | M-1430 | item:734545 | 10.0 | 1232.0 | 12320.0 | 9240.0 | UN |
| input_material | M-1430 | item:773474 | 20.0 | 1486826.572 | 29736531.44 | 22302398.58 | G |
| input_material | M-1810 | item:001757 | 20.0 | 330.5652 | 6611.304 | 4958.478 | KG |
| input_material | M-1810 | item:001848 | 20.0 | 247.9239 | 4958.478 | 3718.8585 | KG |
| input_material | M-1810 | item:001893 | 15.0 | 1570.1847 | 23552.7705 | 17664.577875 | KG |
| input_material | M-1810 | item:002612 | 20.0 | 413.2065 | 8264.13 | 6198.0975 | KG |
| input_material | M-1810 | item:007923 | 15.0 | 661.1304 | 9916.956 | 7437.717 | KG |
| input_material | M-1810 | item:016332 | 7.0 | 99.16956 | 694.18692 | 520.64019 | KG |
| input_material | M-1810 | item:029313 | 7.0 | 8.26413 | 57.84891 | 43.386683 | KG |
| input_material | M-1810 | item:039668 | 7.0 | 8.26413 | 57.84891 | 43.386683 | KG |
| input_material | M-1810 | item:049371 | 40.0 | 305.77281 | 12230.9124 | 9173.1843 | KG |
| input_material | M-1810 | item:055703 | 30.0 | 16.52826 | 495.8478 | 371.88585 | KG |
| input_material | M-1810 | item:099439 | 7.0 | 413.2065 | 2892.4455 | 2169.334125 | KG |
| input_material | M-1810 | item:338928 | 10.0 | 203550.0 | 2035500.0 | 1526625.0 | UN |
| input_material | M-1810 | item:338929 | 10.0 | 203550.0 | 2035500.0 | 1526625.0 | UN |
| input_material | M-1810 | item:426331 | 7.0 | 2239.05 | 15673.35 | 11755.0125 | UN |
| input_material | M-1810 | item:693055 | 20.0 | 82641.3 | 1652826.0 | 1239619.5 | G |

## Remarques validation industrielle
Le graphe `Reappro amont` utilise maintenant `order_date_IMT` pour dater les ordres MRP. Les commandes du carnet initial peuvent donc apparaitre avant J0 au lieu d'etre empilees artificiellement au 1er janvier.

| Noeud | Item | Lot std | Ancien pic J0 | Pic IMT | Jour IMT | Avant J0 | Lots au pic | Remarque |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M-1430 | 042342 | 30000000.0 | 0.0 | 30000000.0 | 24 | 0.0 | 1.0 | Lot FIA tres eleve a valider avec l'industriel. |
| M-1430 | 773474 | 1.0 | 10100000.0 | 884213.0 | 6 | 4073694.0 | 884213.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 344135 | 120000.0 | 1800000.0 | 240000.0 | -8 | 600000.0 | 2.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 338929 | 5000.0 | 1900000.0 | 50000.0 | 51 | 155000.0 | 10.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 001893 | 23920.0 | 67620.0 | 23920.0 | -30 | 68740.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1430 | 333362 | 5000.0 | 1660000.0 | 20000.0 | -68 | 1120000.0 | 4.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1430 | 038005 | 10000.0 | 30000.0 | 10000.0 | -90 | 20000.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 693055 | 1.0 | 731314.0 | 8965.0 | 44 | 539950.0 | 8965.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 734545 | 6300.0 | 18900.0 | 6300.0 | -33 | 12600.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 049371 | 1600.0 | 9600.0 | 1600.0 | -16 | 3200.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |

## Files
- summaries/first_simulation_summary.json
- reports/mrp_safety_stock_reference.csv
- data/production_input_stocks_daily.csv
- data/production_output_products_daily.csv
- data/production_demand_service_daily.csv
- data/production_constraint_daily.csv
- data/mrp_trace_daily.csv
- data/mrp_orders_daily.csv
- data/assumptions_ledger.csv
- data/production_supplier_shipments_daily.csv
- data/production_supplier_stocks_daily.csv
- data/production_supplier_capacity_daily.csv
- Additional detailed CSVs: generated
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (etudecas\simulation\result\reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y\maps\supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.html)
