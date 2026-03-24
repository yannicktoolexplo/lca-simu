# First simulation report

## Run setup
- Input: etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_explicit_30_25_20.json
- Scenario: scn:BASE
- Horizon (days): 365
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 2.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 30.0 / 25.0 / 20.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: True / 1.0 / True
- Unmodeled supplier source mode: estimated_replenishment
- Stochastic lead times: True
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 1.0
- Inventory cost split capital / warehouse / risk: 0.35 / 0.45 / 0.2
- Transport / purchase realism multipliers: 8.0 / 1.0
- External procurement enabled: False
- External procurement lead days: 4
- External procurement daily cap days: 2.0
- External procurement min daily cap qty: 0.0
- External procurement unit cost / multiplier / transport unit: 0.0 / 2.0 / 0.04
- Nodes: 32
- Edges: 38
- Lanes (edge x item): 38
- Demand rows: 2
- Input material pairs tracked: 24
- Output product pairs tracked: 3 (M-1430 | item:268967, M-1810 | item:268091, SDC-1450 | item:773474)
- Inputs non modelises par Relations_acteurs (non bloquants): 0 (none)
- Conversions d'unites BOM appliquees: 10
- Mismatch d'unites non convertis: 0
- Assumed supplier nodes (explicitly tagged, includes '?'): 1 (SDC-1450)
- Assumed supply edges (explicitly tagged, includes '?'): 1 (edge:SDC-1450_TO_M-1810_007923_Q)
- External upstream sourcing for unmodeled source pairs: 33
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 0

## KPIs
- Total demand: 17400.0
- Total served: 17400.0
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 82065.6843
- Total shipped: 505078.3213
- Avg inventory: 6274030.2024
- Ending inventory: 7402750.8977
- Transport cost: 1810581.6119
- Holding cost (capital tied-up): 4905203.7198
- Warehouse operating cost: 6306690.4969
- Inventory risk cost (obsolescence/compliance proxy): 2802973.5542
- Legacy raw holding cost before split: 14014867.771
- Purchase cost (from order_terms sell_price): 10006.5237
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 15825449.3828
- Total cost: 15835455.9065
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 356953.6432
- Total estimated source replenished qty: 852702.2384
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.309761 / 0.398264 / 0.177006 / 0.114337 / 0.000632
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 2972029.5399
- Total explicit initialization pipeline qty: 4743556.8755
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 0.0
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[]

## Files
- summaries/first_simulation_summary.json
- data/first_simulation_daily.csv
- data/production_input_stocks_daily.csv
- data/production_input_consumption_daily.csv
- data/production_input_replenishment_arrivals_daily.csv
- data/production_input_replenishment_shipments_daily.csv
- data/production_input_stocks_pivot.csv
- data/production_output_products_daily.csv
- data/production_demand_service_daily.csv
- data/production_constraint_daily.csv
- data/production_supplier_shipments_daily.csv
- data/production_supplier_stocks_daily.csv
- data/production_supplier_capacity_daily.csv
- data/production_dc_stocks_daily.csv
- production_input_stocks_by_material_*.png (etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\factories\input_stocks\production_input_stocks_by_material_M-1430.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\factories\input_stocks\production_input_stocks_by_material_M-1810.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\factories\input_stocks\production_input_stocks_by_material_SDC-1450.png)
- production_output_products.png (etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\factories\output_products\production_output_products.png)
- production_output_products_by_factory_*.png (etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\factories\output_products\production_output_products_by_factory_M-1430.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\factories\output_products\production_output_products_by_factory_M-1810.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\factories\output_products\production_output_products_by_factory_SDC-1450.png)
- production_supplier_input_stocks_by_material_*.png (etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-1450.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0500655A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0505677A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0508918A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0514881A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0518684A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0519670A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0520115A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0520132A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0525412A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0901566A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0910216A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0914320A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0914360C.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0914690A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0949099A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0951020A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0960508A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0964290A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0972460A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0975221A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0989480A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0990780A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0993480A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD1091642A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD1095770A.png, etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD1096202A.png)
- production_dc_factory_outputs_by_material_*.png (etudecas\simulation\result\reference_baseline_explicit_30_25_20_fixed_source_replenishment\plots\distribution_centers\factory_outputs\production_dc_factory_outputs_by_material_DC-1920.png)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
