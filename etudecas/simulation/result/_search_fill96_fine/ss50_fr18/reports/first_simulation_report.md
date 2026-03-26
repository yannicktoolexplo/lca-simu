# First simulation report

## Run setup
- Input: C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18.json
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
- Initialization seed in-transit / fill ratio / estimated-source pipeline: True / 0.18 / True
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
- Total served: 17446.6235
- Fill rate: 0.957461
- Ending backlog: 775.1265
- Total produced: 101386.7081
- Total shipped: 783526.459
- Avg inventory: 4715319.2227
- Ending inventory: 4845775.7302
- Transport cost: 2889077.2061
- Holding cost (capital tied-up): 3728214.8419
- Warehouse operating cost: 4793419.0824
- Inventory risk cost (obsolescence/compliance proxy): 2130408.4811
- Legacy raw holding cost before split: 10652042.4054
- Purchase cost (from order_terms sell_price): 25388.8255
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 13541119.6115
- Total cost: 13566508.4369
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 743035.2962
- Total estimated source replenished qty: 752878.7569
- Total estimated source rejected qty: 18307350.4335
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.27481 / 0.353327 / 0.157034 / 0.212957 / 0.001871
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 338297.8436
- Total explicit initialization pipeline qty: 806387.3548
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 4768946.8098
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 454.5
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 320.6265
  }
]

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
- production_input_stocks_by_material_*.png (C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\factories\input_stocks\production_input_stocks_by_material_M-1430.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\factories\input_stocks\production_input_stocks_by_material_M-1810.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\factories\input_stocks\production_input_stocks_by_material_SDC-1450.png)
- production_output_products.png (C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\factories\output_products\production_output_products.png)
- production_output_products_by_factory_*.png (C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\factories\output_products\production_output_products_by_factory_M-1430.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\factories\output_products\production_output_products_by_factory_M-1810.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\factories\output_products\production_output_products_by_factory_SDC-1450.png)
- production_supplier_input_stocks_by_material_*.png (C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-1450.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0500655A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0505677A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0508918A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0514881A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0518684A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0519670A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0520115A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0520132A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0525412A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0901566A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0910216A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0914320A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0914360C.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0914690A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0949099A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0951020A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0960508A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0964290A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0972460A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0975221A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0989480A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0990780A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD0993480A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD1091642A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD1095770A.png, C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\suppliers\input_stocks\production_supplier_input_stocks_by_material_SDC-VD1096202A.png)
- production_dc_factory_outputs_by_material_*.png (C:\dev\lca-simu\etudecas\simulation\result\_search_fill96_fine\ss50_fr18\plots\distribution_centers\factory_outputs\production_dc_factory_outputs_by_material_DC-1920.png)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (etudecas\simulation\result\maps\supply_graph_poc_geocoded_map_with_factory_hover.html)
