# First simulation report

## Run setup
- Input: etudecas\simulation_prep\result\reference_baseline\_mrp_bom_tests\bom_weekly_mps_lotified_no_static_fallback_physical_floor.json
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
- Initialization stock days factory / supplier FG / DC / customer: 0.0 / 0.0 / 0.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: False / 1.0 / False
- Opening open-orders reconstruction enabled / horizon days: True / 0
- Opening open-orders demand multiplier / BOM signal for MRP: 1.0 / True
- MRP demand signal source: mps_lotified
- MRP demand signal smoothing / static fallback on propagated pairs: 7 j / False
- MRP physical safety floor enforced: True
- MRP strict safety floor from safety time only: False
- Soft safety-time physical stock target factor: 1.0
- Soft safety-time pair factors: {}
- Base stock floor pair factors: {'SDC-1450|item:021081': 0.0}
- Unmodeled supplier source mode: external_procurement
- Stochastic lead times: True
- Lead-time distribution mode: industrial
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 0.09
- Inventory cost split capital / warehouse / risk: 0.35 / 0.45 / 0.2
- Transport / purchase realism multipliers: 0.2 / 1.0
- External procurement enabled: True
- External procurement proactive supplier replenishment: True
- External procurement lead days: 4
- External procurement daily cap days: 999.0
- External procurement min daily cap qty: 1000000000.0
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
- Opening open-order rows reconstructed from January snapshot: 106
- MRP trace tracked pairs / rows / orders: 65 / 118625 / 27925

## KPIs
- Total demand: 25762139.9999
- Total served: 25762139.9999
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 102878000.0
- Total shipped: 887549051.2087
- Avg inventory: 289651034.8983
- Ending inventory: 394966596.3529
- Transport cost: 5643456.2857
- Holding cost (capital tied-up): 5980008.1747
- Warehouse operating cost: 7688581.9389
- Inventory risk cost (obsolescence/compliance proxy): 3417147.5284
- Legacy raw holding cost before split: 17085737.6421
- Purchase cost (from order_terms sell_price): 18684812.739
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 22729193.9277
- Total cost: 41414006.6667
- Total external procured ordered qty: 596537104.3564
- Total external procured arrived qty: 596537006.0992
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 249171517.3112
- Total estimated source ordered qty: 0.0
- Total estimated source replenished qty: 0.0
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.144396 / 0.185652 / 0.082512 / 0.136269 / 0.451171
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 207973206.7465
- Total explicit initialization pipeline qty: 25012341.2857
- Total opening open-order qty: 25012341.2857
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 6057306.1714
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[]

## Safety stock reference
Calcul: `stock equiv delai = demande moyenne journaliere MRP x delai de securite`. Quand une trace MRP existe, la demande moyenne vient du signal reel utilise par le MRP (`bb_demand_signal_qty`), pas d'une capacite ou d'un besoin statique gonfle. Si le mode strict est actif, le plancher physique MRP vient uniquement de cette couverture de delai de securite. La cible physique simulee applique le facteur global `1.0` ou un facteur specifique par couple si renseigne.

| Scope | Noeud | Item | Delai secu j | Demande MRP moy/j | Stock equiv delai moy | Cible physique moy | Max cible physique | Base | Unite |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| finished_good | DC-1920 | item:268091 | 20.0 | 9798.471233 | 195969.424658 | 195969.424658 | 399840.0 | mrp_trace_demand_signal | UN |
| finished_good | DC-1920 | item:268967 | 25.0 | 4317.769863 | 107944.246573 | 107944.246573 | 592153.571425 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:038005 | 20.0 | 76.490097 | 1529.801938 | 1529.801937 | 37728.223456 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:042342 | 5.0 | 263759.015014 | 1318795.075068 | 1318795.075068 | 32524338.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:333362 | 10.0 | 4371.068493 | 43710.684932 | 43710.684932 | 1078000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:344135 | 10.0 | 4371.068493 | 43710.684932 | 43710.684932 | 1078000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:708073 | 10.0 | 34.662573 | 346.625732 | 346.625732 | 8548.54 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:730384 | 10.0 | 926.666521 | 9266.665205 | 9266.665205 | 228536.0 | mrp_trace_demand_signal | M |
| input_material | M-1430 | item:734545 | 10.0 | 34.968548 | 349.685479 | 349.685479 | 8624.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:773474 | 20.0 | 42201.43366 | 844028.673201 | 844028.673201 | 20815572.008 | mrp_trace_demand_signal | G |
| input_material | M-1810 | item:001757 | 20.0 | 16.389141 | 327.782821 | 327.782821 | 935.424 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001848 | 20.0 | 12.291856 | 245.837116 | 245.837116 | 701.568 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001893 | 15.0 | 77.84842 | 1167.726299 | 1167.726299 | 3332.448 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:002612 | 20.0 | 20.486426 | 409.728526 | 409.728526 | 1169.28 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:007923 | 15.0 | 32.778282 | 491.674231 | 491.674231 | 1403.136 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:016332 | 7.0 | 4.916742 | 34.417196 | 34.417196 | 98.21952 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:029313 | 7.0 | 0.409729 | 2.8681 | 2.8681 | 8.18496 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:039668 | 7.0 | 0.409729 | 2.8681 | 2.8681 | 8.18496 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:049371 | 40.0 | 15.159955 | 606.398219 | 606.398219 | 1730.5344 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:055703 | 30.0 | 0.819457 | 24.583712 | 24.583712 | 70.1568 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:099439 | 7.0 | 20.486426 | 143.404984 | 143.404984 | 409.248 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:338928 | 10.0 | 10091.835616 | 100918.356164 | 100918.356164 | 288000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:338929 | 10.0 | 10091.835616 | 100918.356164 | 100918.356164 | 288000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:426331 | 7.0 | 111.010192 | 777.071342 | 777.071342 | 2217.6 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:693055 | 20.0 | 4097.28526 | 81945.705205 | 81945.705205 | 233856.0 | mrp_trace_demand_signal | G |

## Remarques validation industrielle
Le graphe `Reappro amont` utilise maintenant `order_date_IMT` pour dater les ordres MRP. Les commandes du carnet initial peuvent donc apparaitre avant J0 au lieu d'etre empilees artificiellement au 1er janvier.

| Noeud | Item | Lot std | Ancien pic J0 | Pic IMT | Jour IMT | Avant J0 | Lots au pic | Remarque |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M-1810 | 338928 | 25000.0 | 0.0 | 350000.0 | 281 | 0.0 | 14.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1810 | 338929 | 5000.0 | 0.0 | 235000.0 | 1299 | 0.0 | 47.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1430 | 042342 | 30000000.0 | 30000000.0 | 60000000.0 | 1641 | 150000000.0 | 2.0 | Lot FIA tres eleve a valider avec l'industriel. |
| M-1430 | 773474 | 1.0 | 6431833.0 | 1825047.0 | 1631 | 1607959.0 | 1825047.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1810 | 693055 | 1.0 | 0.0 | 84307.0 | 261 | 0.0 | 84307.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 333362 | 5000.0 | 885000.0 | 25000.0 | -11 | 250000.0 | 5.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| SDC-1450 | 021081 | 1.0 | 0.0 | 810.0 | 1611 | 0.0 | 810.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |

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
- data/production_supplier_capacity_daily.csv
- Additional detailed CSVs: generated
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (etudecas\simulation\result\mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_021081_floor_test\maps\supply_graph_mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_021081_floor_test.html)
