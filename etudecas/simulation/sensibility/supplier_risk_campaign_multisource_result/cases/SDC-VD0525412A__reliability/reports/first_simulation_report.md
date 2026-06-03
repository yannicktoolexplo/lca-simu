# First simulation report

## Run setup
- Input: etudecas\simulation_prep\result\reference_baseline\_mrp_bom_tests\bom_weekly_mps_lotified_no_static_fallback_physical_floor.json
- Scenario: scn:BASE
- Measured horizon (days): 365
- Warm-up (days): 0
- Warm-up demand profile mode / cycle: restart / 365 days
- Total simulated timeline (days): 365
- Output profile: compact
- Safety stock policy (days): 7.0
- Replenishment review period (customer/DC, days): 1
- Upstream factory MRP review period (days): 1
- MRP target bucket (days): 1
- MRP target cutover context (days): 0
- MRP multi-source policy / min annual lot window: portfolio_annual_min_lot / 28 days
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 1.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 0.0 / 0.0 / 0.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: False / 1.0 / False
- Opening open-orders reconstruction enabled / horizon days: True / 0
- Opening open-orders source: Extract_En_cours.xlsx
- Opening open-orders demand multiplier / BOM signal for MRP: 1.0 / True
- MRP demand signal source: mps_lotified
- MRP demand signal smoothing / static fallback on propagated pairs: 7 j / False
- MRP physical safety floor enforced: True
- MRP strict safety floor from safety time only: False
- Soft safety-time physical stock target factor: 1.0
- Soft safety-time pair factors: {}
- Base stock floor factor: 1.0
- Base stock floor pair factors: {}
- Unmodeled supplier source mode: external_procurement
- Stochastic lead times: True
- Lead-time distribution mode: industrial
- Random seed: 42
- Supplier risk events enabled / count: True / 1
- Supplier risk warnings: []
- Supplier neutral floor test enabled / capacity pairs / stock pairs: False / 0 / 0
- Factory nominal capacity test enabled / applied processes: False / 0
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 0.09
- Inventory cost split capital / warehouse / risk: 0.35 / 0.45 / 0.2
- Transport / purchase realism multipliers: 0.2 / 1.0
- Production cost enabled / target share: True / 0.3
- Production cost basis: pharma_standard_target_share_allocated_on_actual_production
- Production cost line shares: {'M-1430|item:268967': 0.4, 'M-1810|item:268091': 0.45, 'SDC-1450|item:773474': 0.15}
- Supplier upstream supply enabled: True
- Supplier upstream proactive replenishment: True
- Supplier upstream lead days: 4
- Supplier upstream lead mode / scale: supplier_material / 1.0
- Supplier upstream capacity mode / nominal scale: supplier_nominal / 1.0
- Supplier upstream pipeline seed / fill ratio: True / 1.0
- Supplier upstream daily cap days: 999.0
- Supplier upstream min daily cap qty: 1000000000.0
- Supplier upstream unit cost / multiplier / transport unit: 0.0 / 2.0 / 0.04
- Nodes: 35
- Edges: 39
- Flux transport (edge x item): 39
- Demand rows: 2
- Input material pairs tracked: 24
- Output product pairs tracked: 3 (M-1430 | item:268967, M-1810 | item:268091, SDC-1450 | item:773474)
- Inputs non modelises par Relations_acteurs (non bloquants): 0 (none)
- Conversions d'unites BOM appliquees: 11
- Mismatch d'unites non convertis: 0
- Assumed supplier nodes (explicitly tagged, includes '?'): 0 (none)
- Assumed supply edges (explicitly tagged, includes '?'): 0 (none)
- Supplier upstream sourcing for unmodeled source pairs: 34
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 0
- Opening open-order rows seeded: 88
- MRP trace tracked pairs / rows / orders: 65 / 23725 / 11941

## KPIs
- Total demand: 5152428.0
- Total served: 5152428.0
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 70753600.0
- Total shipped: 484090239.9769
- Avg inventory: 806619515.3648
- Ending inventory: 825159506.7897
- Transport cost: 1235669.1711
- Holding cost (capital tied-up): 2442826.3209
- Warehouse operating cost: 3140776.6983
- Inventory risk cost (obsolescence/compliance proxy): 1395900.7548
- Legacy raw holding cost before split: 6979503.774
- Purchase cost (from order_terms sell_price): 10093646.3891
- Production cost (pharma conversion proxy): 7846636.8575
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 8215172.9451
- Total cost: 26155456.1918
- Total supplier upstream ordered qty: 270387220.3139
- Total supplier upstream arrived qty: 505645265.2622
- Supplier upstream arrived includes opening upstream pipeline receipts when the upstream pipeline seed is enabled.
- Total supplier upstream rejected qty (cap-limited): 890424024.3217
- Total supplier upstream cost premium: 27774463.0602
- Total estimated source ordered qty: 0.0
- Total estimated source replenished qty: 0.0
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase / production: 0.093396 / 0.120081 / 0.053369 / 0.047243 / 0.38591 / 0.3
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 208012846.7465
- Total explicit initialization pipeline qty: 303596232.9482
- Total opening open-order qty: 68338188.0
- Total unreliable supplier loss qty: 1396000.0
- Total supplier capacity binding qty: 0.0
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[]

## Safety stock reference
Calcul: `stock equiv delai = demande moyenne journaliere MRP x delai de securite`. Quand une trace MRP existe, la demande moyenne vient du signal reel utilise par le MRP (`bb_demand_signal_qty`), pas d'une capacite ou d'un besoin statique gonfle. Si le mode strict est actif, le plancher physique MRP vient uniquement de cette couverture de delai de securite. La cible physique simulee applique le facteur global `1.0` ou un facteur specifique par couple si renseigne.

| Scope | Noeud | Item | Delai secu j | Demande MRP moy/j | Stock equiv delai moy | Cible physique moy | Max cible physique | Base | Unite |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| finished_good | DC-1920 | item:268091 | 20.0 | 9798.471233 | 195969.424658 | 215801.39281 | 399840.0 | mrp_trace_demand_signal | UN |
| finished_good | DC-1920 | item:268967 | 25.0 | 4317.769863 | 107944.246573 | 130737.25468 | 592153.571425 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:038005 | 20.0 | 387.618734 | 7752.374684 | 8930.588059 | 37728.223456 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:042342 | 5.0 | 1336616.630137 | 6683083.150685 | 7631695.558745 | 32524338.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:333362 | 10.0 | 22150.684932 | 221506.849315 | 308905.845977 | 1078000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:344135 | 10.0 | 22150.684932 | 221506.849315 | 254463.780378 | 1078000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:708073 | 10.0 | 175.654932 | 1756.549315 | 3345.590411 | 8548.54 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:730384 | 10.0 | 4695.945205 | 46959.452055 | 65630.684932 | 228536.0 | mrp_trace_demand_signal | M |
| input_material | M-1430 | item:734545 | 10.0 | 177.205479 | 1772.054795 | 2034.646529 | 8624.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:773474 | 20.0 | 213858.616521 | 4277172.330411 | 4911024.380365 | 20815572.008 | mrp_trace_demand_signal | G |
| input_material | M-1810 | item:001757 | 20.0 | 8.200978 | 164.019551 | 377.617883 | 935.424 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001848 | 20.0 | 6.150733 | 123.014663 | 282.085372 | 701.568 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001893 | 15.0 | 38.954643 | 584.319649 | 1342.307137 | 3332.448 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:002612 | 20.0 | 10.251222 | 205.024438 | 470.142287 | 1169.28 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:007923 | 15.0 | 16.401955 | 246.029326 | 562.377933 | 1403.136 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:016332 | 7.0 | 2.460293 | 17.222053 | 39.650174 | 98.21952 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:029313 | 7.0 | 0.205024 | 1.435171 | 3.296185 | 8.18496 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:039668 | 7.0 | 0.205024 | 1.435171 | 3.297687 | 8.18496 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:049371 | 40.0 | 7.585904 | 303.436169 | 924.933015 | 1730.5344 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:055703 | 30.0 | 0.410049 | 12.301466 | 28.272209 | 70.1568 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:099439 | 7.0 | 10.251222 | 71.758553 | 164.884327 | 409.248 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:338928 | 10.0 | 5049.863014 | 50498.630137 | 115962.005995 | 288000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:338929 | 10.0 | 5049.863014 | 50498.630137 | 116040.074446 | 288000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:426331 | 7.0 | 55.548493 | 388.839452 | 887.864986 | 2217.6 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:693055 | 20.0 | 2050.244384 | 41004.887671 | 94131.175654 | 233856.0 | mrp_trace_demand_signal | G |
| input_material | SDC-1450 | item:021081 | 0.0 | 1645.939726 | 0.0 | 900000.0 | 900000.0 | mrp_trace_demand_signal | KG |

## Remarques validation industrielle
Le graphe `Reappro amont` utilise maintenant `order_date_IMT` pour dater les ordres MRP. Les commandes du carnet initial peuvent donc apparaitre avant J0 au lieu d'etre empilees artificiellement au 1er janvier.

| Noeud | Item | Lot std | Ancien pic J0 | Pic IMT | Jour IMT | Avant J0 | Lots au pic | Remarque |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M-1810 | 338929 | 5000.0 | 295000.0 | 215000.0 | 46 | 120000.0 | 43.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1430 | 333362 | 5000.0 | 1300000.0 | 205000.0 | 42 | 865000.0 | 41.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1430 | 042342 | 30000000.0 | 30000000.0 | 60000000.0 | 1 | 120000000.0 | 2.0 | Lot FIA tres eleve a valider avec l'industriel. |
| M-1430 | 773474 | 1.0 | 9600000.0 | 5066668.0 | 8 | 1686732.0 | 5066668.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 344135 | 120000.0 | 4440000.0 | 480000.0 | 16 | 1320000.0 | 4.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 338928 | 25000.0 | 400000.0 | 75000.0 | 52 | 400000.0 | 3.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 693055 | 1.0 | 5847.0 | 67586.0 | 73 | 28506.0 | 67586.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 708073 | 5000.0 | 30000.0 | 10000.0 | 6 | 10000.0 | 2.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1430 | 734545 | 6300.0 | 25200.0 | 6300.0 | -5 | 6300.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |

Process internes sans capacite source: la simulation ne les bloque pas par capacite, mais conserve les contraintes de lots, d'intrants et de besoin.
| Noeud | Process | Sortie |
|---|---|---:|
| SDC-1450 | proc:MAKE_773474 | 773474 |

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
- data/production_supplier_stock_flows_daily.csv
- data/production_supplier_capacity_daily.csv
- data/supplier_nominal_parameters.csv
- data/production_capacity_nominal_parameters.csv
- data/supplier_risk_events_applied_daily.csv
- reports/supplier_nominal_audit.md
- Additional detailed CSVs: skipped in compact mode
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
