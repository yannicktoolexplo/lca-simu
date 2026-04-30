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
- Base stock floor factor: 0.0
- Base stock floor pair factors: {'M-1430|item:038005': 1.0, 'M-1430|item:042342': 1.0, 'M-1430|item:333362': 1.0, 'M-1430|item:344135': 1.0, 'M-1430|item:708073': 1.0, 'M-1430|item:730384': 1.0, 'M-1430|item:734545': 1.0, 'M-1430|item:773474': 1.0, 'M-1810|item:001757': 1.0, 'M-1810|item:001848': 1.0, 'M-1810|item:001893': 1.0, 'M-1810|item:002612': 1.0, 'M-1810|item:007923': 1.0, 'M-1810|item:016332': 1.0, 'M-1810|item:029313': 1.0, 'M-1810|item:039668': 1.0, 'M-1810|item:049371': 1.0, 'M-1810|item:055703': 1.0, 'M-1810|item:099439': 1.0, 'M-1810|item:338928': 1.0, 'M-1810|item:338929': 1.0, 'M-1810|item:426331': 1.0, 'M-1810|item:693055': 1.0}
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
- MRP trace tracked pairs / rows / orders: 65 / 118625 / 23276

## KPIs
- Total demand: 25762139.9999
- Total served: 25762139.9999
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 92228400.0
- Total shipped: 755214164.3169
- Avg inventory: 349460916.8328
- Ending inventory: 337685147.2921
- Transport cost: 5298048.4713
- Holding cost (capital tied-up): 8149581.5603
- Warehouse operating cost: 10478033.4346
- Inventory risk cost (obsolescence/compliance proxy): 4656903.7487
- Legacy raw holding cost before split: 23284518.7436
- Purchase cost (from order_terms sell_price): 21678935.6297
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 28582567.215
- Total cost: 50261502.8447
- Total external procured ordered qty: 486959763.4235
- Total external procured arrived qty: 486959749.4972
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 311250893.8996
- Total estimated source ordered qty: 0.0
- Total estimated source replenished qty: 0.0
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.162144 / 0.20847 / 0.092653 / 0.10541 / 0.431323
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 208012846.7465
- Total explicit initialization pipeline qty: 25012341.2857
- Total opening open-order qty: 25012341.2857
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 10692521.2
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
| input_material | M-1430 | item:038005 | 20.0 | 68.220897 | 1364.417944 | 1364.417944 | 37728.223456 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:042342 | 5.0 | 235244.526904 | 1176222.634521 | 1176222.634521 | 32524338.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:333362 | 10.0 | 3898.520548 | 38985.205479 | 145007.123288 | 1078000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:344135 | 10.0 | 3898.520548 | 38985.205479 | 38985.205479 | 1078000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:708073 | 10.0 | 30.915268 | 309.152679 | 2236.823912 | 8548.54 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:730384 | 10.0 | 826.486356 | 8264.863562 | 30915.000548 | 228536.0 | mrp_trace_demand_signal | M |
| input_material | M-1430 | item:734545 | 10.0 | 31.188164 | 311.881644 | 311.881644 | 8624.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:773474 | 20.0 | 37639.116508 | 752782.330152 | 752782.330152 | 20815572.008 | mrp_trace_demand_signal | G |
| input_material | M-1810 | item:001757 | 20.0 | 16.376327 | 327.52654 | 327.52654 | 935.424 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001848 | 20.0 | 12.282245 | 245.644905 | 245.644905 | 701.568 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001893 | 15.0 | 77.787553 | 1166.8133 | 1166.8133 | 3332.448 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:002612 | 20.0 | 20.470409 | 409.408175 | 409.408175 | 1169.28 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:007923 | 15.0 | 32.752654 | 491.28981 | 491.28981 | 1403.136 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:016332 | 7.0 | 4.912898 | 34.390287 | 34.390287 | 98.21952 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:029313 | 7.0 | 0.409408 | 2.865857 | 2.865857 | 8.18496 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:039668 | 7.0 | 0.409408 | 2.865857 | 2.865857 | 8.18496 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:049371 | 40.0 | 15.148102 | 605.9241 | 938.782895 | 1730.5344 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:055703 | 30.0 | 0.818816 | 24.564491 | 24.564491 | 70.1568 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:099439 | 7.0 | 20.470409 | 143.292861 | 143.292861 | 409.248 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:338928 | 10.0 | 10083.945205 | 100839.452055 | 100839.452055 | 288000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:338929 | 10.0 | 10083.945205 | 100839.452055 | 100839.452055 | 288000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:426331 | 7.0 | 110.923397 | 776.463781 | 776.463781 | 2217.6 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:693055 | 20.0 | 4094.081753 | 81881.635068 | 81881.635068 | 233856.0 | mrp_trace_demand_signal | G |
| input_material | SDC-1450 | item:021081 | 0.0 | 329.187945 | 0.0 | 900000.0 | 900000.0 | mrp_trace_demand_signal | KG |

## Remarques validation industrielle
Le graphe `Reappro amont` utilise maintenant `order_date_IMT` pour dater les ordres MRP. Les commandes du carnet initial peuvent donc apparaitre avant J0 au lieu d'etre empilees artificiellement au 1er janvier.

| Noeud | Item | Lot std | Ancien pic J0 | Pic IMT | Jour IMT | Avant J0 | Lots au pic | Remarque |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M-1810 | 338928 | 25000.0 | 0.0 | 350000.0 | 309 | 0.0 | 14.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1810 | 338929 | 5000.0 | 0.0 | 215000.0 | 1404 | 0.0 | 43.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1430 | 042342 | 30000000.0 | 30000000.0 | 60000000.0 | 1273 | 150000000.0 | 2.0 | Lot FIA tres eleve a valider avec l'industriel. |
| M-1430 | 773474 | 1.0 | 6431833.0 | 2723444.0 | 903 | 1607959.0 | 2723444.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1810 | 693055 | 1.0 | 0.0 | 78636.0 | 291 | 0.0 | 78636.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 333362 | 5000.0 | 885000.0 | 40000.0 | 533 | 180000.0 | 8.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |

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
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (etudecas\simulation\result\mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test\maps\supply_graph_mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test.html)
