# First simulation report

## Run setup
- Input: etudecas\simulation_prep\result\reference_baseline\_mrp_bom_tests\bom_weekly_mps_lotified_no_static_fallback_physical_floor.json
- Scenario: scn:BASE
- Measured horizon (days): 1825
- Warm-up (days): 0
- Total simulated timeline (days): 1825
- Output profile: compact
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
- Soft safety-time pair factors: {'M-1810|item:338928': 3.0, 'M-1810|item:338929': 3.0}
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
- MRP trace tracked pairs / rows / orders: 65 / 118625 / 97699

## KPIs
- Total demand: 25762139.9999
- Total served: 25762139.9999
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 112614600.0
- Total shipped: 889600887.8637
- Avg inventory: 300360170.0578
- Ending inventory: 392417908.5283
- Transport cost: 10161084.9068
- Holding cost (capital tied-up): 8227865.2887
- Warehouse operating cost: 10578683.9427
- Inventory risk cost (obsolescence/compliance proxy): 4701637.3078
- Legacy raw holding cost before split: 23508186.5392
- Purchase cost (from order_terms sell_price): 50525698.2549
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 33669271.446
- Total cost: 84194969.7009
- Total external procured ordered qty: 593329713.6179
- Total external procured arrived qty: 593329625.3364
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 161890646.2333
- Total estimated source ordered qty: 0.0
- Total estimated source replenished qty: 0.0
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.097724 / 0.125645 / 0.055842 / 0.120685 / 0.600104
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 207973206.7465
- Total explicit initialization pipeline qty: 25012341.2857
- Total opening open-order qty: 25012341.2857
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 91776881.7429
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[]

## Safety stock reference
Calcul: `stock equiv delai = demande moyenne journaliere MRP x delai de securite`. Quand une trace MRP existe, la demande moyenne vient du signal reel utilise par le MRP (`bb_demand_signal_qty`), pas d'une capacite ou d'un besoin statique gonfle. Si le mode strict est actif, le plancher physique MRP vient uniquement de cette couverture de delai de securite. La cible physique simulee applique le facteur global `1.0` ou un facteur specifique par couple si renseigne.

| Scope | Noeud | Item | Delai secu j | Demande MRP moy/j | Stock equiv delai moy | Cible physique moy | Max cible physique | Base | Unite |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| finished_good | DC-1920 | item:268091 | 20.0 | 9798.471233 | 195969.424658 | 430538.0 | 430538.0 | mrp_trace_demand_signal | UN |
| finished_good | DC-1920 | item:268967 | 25.0 | 4317.769863 | 107944.246573 | 1101534.0 | 1101534.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:038005 | 20.0 | 77.523747 | 1550.474937 | 37603.862265 | 37728.223456 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:042342 | 5.0 | 267323.326027 | 1336616.630137 | 78749996.0 | 78749996.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:333362 | 10.0 | 4430.136986 | 44301.369863 | 180705.479452 | 1078000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:344135 | 10.0 | 4430.136986 | 44301.369863 | 767890.410959 | 1078000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:708073 | 10.0 | 35.130986 | 351.309863 | 10326.88 | 10326.88 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:730384 | 10.0 | 939.189041 | 9391.890411 | 74968.465753 | 228536.0 | mrp_trace_demand_signal | M |
| input_material | M-1430 | item:734545 | 10.0 | 35.441096 | 354.410959 | 1927.972603 | 8624.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:773474 | 20.0 | 42771.723304 | 855434.466082 | 14848722.137315 | 20815572.008 | mrp_trace_demand_signal | G |
| input_material | M-1810 | item:001757 | 20.0 | 16.286629 | 325.732576 | 8499.654 | 8499.654 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001848 | 20.0 | 12.214972 | 244.299432 | 10262.646 | 10262.646 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001893 | 15.0 | 77.361487 | 1160.422304 | 9783.5 | 9783.5 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:002612 | 20.0 | 20.358286 | 407.165721 | 153521.636719 | 153521.636719 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:007923 | 15.0 | 32.573258 | 488.598865 | 55018.98 | 55018.98 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:016332 | 7.0 | 4.885989 | 34.201921 | 883.02 | 883.02 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:029313 | 7.0 | 0.407166 | 2.85016 | 226.83 | 226.83 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:039668 | 7.0 | 0.407166 | 2.85016 | 459.695 | 459.695 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:049371 | 40.0 | 15.065132 | 602.605266 | 4138.93 | 4138.93 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:055703 | 30.0 | 0.814331 | 24.429943 | 569.805001 | 569.805001 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:099439 | 7.0 | 20.358286 | 142.508002 | 4972.616 | 4972.616 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:338928 | 10.0 | 10028.712329 | 100287.123288 | 926581.931507 | 1212195.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:338929 | 10.0 | 10028.712329 | 100287.123288 | 811775.342466 | 1062000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:426331 | 7.0 | 110.315836 | 772.210849 | 24159.0 | 24159.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:693055 | 20.0 | 4071.657205 | 81433.14411 | 1010000.0 | 1010000.0 | mrp_trace_demand_signal | G |

## Remarques validation industrielle
Le graphe `Reappro amont` utilise maintenant `order_date_IMT` pour dater les ordres MRP. Les commandes du carnet initial peuvent donc apparaitre avant J0 au lieu d'etre empilees artificiellement au 1er janvier.

| Noeud | Item | Lot std | Ancien pic J0 | Pic IMT | Jour IMT | Avant J0 | Lots au pic | Remarque |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M-1810 | 338928 | 25000.0 | 0.0 | 325000.0 | 250 | 0.0 | 13.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1810 | 338929 | 5000.0 | 0.0 | 205000.0 | 226 | 0.0 | 41.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1430 | 042342 | 30000000.0 | 30000000.0 | 60000000.0 | -3 | 150000000.0 | 2.0 | Lot FIA tres eleve a valider avec l'industriel. |
| M-1430 | 773474 | 1.0 | 6431833.0 | 1814135.0 | 1629 | 1607959.0 | 1814135.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1810 | 693055 | 1.0 | 0.0 | 90152.0 | 256 | 0.0 | 90152.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 333362 | 5000.0 | 885000.0 | 20000.0 | 1675 | 180000.0 | 4.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| SDC-1450 | 021081 | 1.0 | 360.0 | 16635.0 | 134 | 22392.0 | 16635.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |

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
- Additional detailed CSVs: skipped in compact mode
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (etudecas\simulation\result\mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_critical_factor_3\maps\supply_graph_mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_critical_factor_3.html)
