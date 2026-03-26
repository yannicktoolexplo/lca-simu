# First simulation report

## Run setup
- Input: C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40.json
- Scenario: scn:BASE
- Measured horizon (days): 365
- Warm-up (days): 260
- Total simulated timeline (days): 625
- Output profile: compact
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 2.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 0.0 / 3.0 / 6.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: True / 0.4 / True
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
- Total produced: 101396.0466
- Total shipped: 750435.165
- Avg inventory: 4750875.0603
- Ending inventory: 4847929.7505
- Transport cost: 2768816.3677
- Holding cost (capital tied-up): 3755432.049
- Warehouse operating cost: 4828412.6344
- Inventory risk cost (obsolescence/compliance proxy): 2145961.1708
- Legacy raw holding cost before split: 10729805.8542
- Purchase cost (from order_terms sell_price): 24515.1281
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 13498622.2219
- Total cost: 13523137.35
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 742089.0791
- Total estimated source replenished qty: 751642.599
- Total estimated source rejected qty: 22184235.674
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.277704 / 0.357048 / 0.158688 / 0.204747 / 0.001813
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 202228.6262
- Total explicit initialization pipeline qty: 1749791.5594
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 1026248.9213
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[]

## Files
- summaries/first_simulation_summary.json
- data/production_input_stocks_daily.csv
- data/production_output_products_daily.csv
- data/production_demand_service_daily.csv
- data/production_constraint_daily.csv
- data/production_supplier_shipments_daily.csv
- data/production_supplier_stocks_daily.csv
- data/production_supplier_capacity_daily.csv
- Additional detailed CSVs: skipped in compact mode
- production_input_stocks_by_material_*.png (C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\factories\input_stocks\production_input_stocks_by_material_M-1430.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\factories\input_stocks\production_input_stocks_by_material_M-1810.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\factories\input_stocks\production_input_stocks_by_material_SDC-1450.png)
- production_output_products.png (C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\factories\output_products\production_output_products.png)
- production_output_products_by_factory_*.png (C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\factories\output_products\production_output_products_by_factory_M-1430.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\factories\output_products\production_output_products_by_factory_M-1810.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\factories\output_products\production_output_products_by_factory_SDC-1450.png)
- production_supplier_input_stocks_by_material_*.png (C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-1450.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0500655A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0505677A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0508918A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0514881A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0518684A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0519670A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0520115A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0520132A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0525412A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0901566A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0910216A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0914320A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0914360C.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0914690A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0949099A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0951020A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0960508A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0964290A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0972460A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0975221A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0989480A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0990780A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0993480A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD1091642A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD1095770A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD1096202A.png)
- production_dc_factory_outputs_by_material_*.png (C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_statescale\ss30_fr40\plots\distribution_centers\factory_outputs\production_dc_factory_outputs_by_material_DC-1920.png)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (etudecas\simulation\result\maps\supply_graph_poc_geocoded_map_with_factory_hover.html)
