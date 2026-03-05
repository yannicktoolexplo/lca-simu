# First simulation report

## Run setup
- Input: etudecas/worstcase/input_case_worst_fill.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 5.728359
- Replenishment review period (days): 6
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.284994
- Production smoothing factor: 0.238686
- Stochastic lead times: True
- Random seed: 42
- Economic policy transport floor /km: 0.028493 / 0.000114
- Economic policy purchase floor: 0.009008
- Holding cost scale: 0.94914
- External procurement enabled: True
- External procurement lead days: 5
- External procurement daily cap days: 3.054816
- External procurement min daily cap qty: 0.0
- External procurement unit cost / multiplier / transport unit: 0.0 / 3.262786 / 0.072461
- Nodes: 28
- Edges: 34
- Lanes (edge x item): 34
- Demand rows: 2
- Input material pairs tracked: 23
- Output product pairs tracked: 2 (M-1430 | item:268967, M-1810 | item:268091)
- Inputs non modelises par Relations_acteurs (non bloquants): 0 (none)
- Conversions d'unites BOM appliquees: 10
- Mismatch d'unites non convertis: 0
- Assumed supplier nodes (explicitly tagged, includes '?'): 1 (SDC-1450)
- Assumed supply edges (explicitly tagged, includes '?'): 1 (edge:SDC-1450_TO_M-1810_693710_Q)
- External upstream sourcing for unmodeled source pairs: 30
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 23

## KPIs
- Total demand: 1838.9566
- Total served: 642.9611
- Fill rate: 0.349634
- Ending backlog: 1195.9955
- Total produced: 973.9194
- Total shipped: 18034.9039
- Avg inventory: 32231.2671
- Ending inventory: 28306.3874
- Transport cost: 2473.2048
- Holding cost: 29720.3223
- Purchase cost (from order_terms sell_price): 1428.4809
- Logistics cost (transport + holding): 32193.5271
- Total cost: 33622.008
- Total external procured ordered qty: 22350.4757
- Total external procured arrived qty: 22350.4757
- Total external procured rejected qty (cap-limited): 16999.5743
- Total external procurement cost premium: 2643.9256
- Cost share holding / transport / purchase: 0.883954 / 0.073559 / 0.042486
- Total opening stock bootstrap qty: 40758.0586
- Total unreliable supplier loss qty: 3093.7407
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 620.406
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 575.5895
  }
]

## Files
- first_simulation_summary.json
- first_simulation_daily.csv
- production_input_stocks_daily.csv
- production_input_consumption_daily.csv
- production_input_replenishment_arrivals_daily.csv
- production_input_replenishment_shipments_daily.csv
- production_input_stocks_pivot.csv
- production_output_products_daily.csv
- production_supplier_shipments_daily.csv
- production_supplier_stocks_daily.csv
- production_dc_stocks_daily.csv
- production_input_stocks_by_material_*.png (etudecas/worstcase/production_input_stocks_by_material_M-1430.png, etudecas/worstcase/production_input_stocks_by_material_M-1810.png)
- production_output_products.png (etudecas/worstcase/production_output_products.png)
- production_output_products_by_factory_*.png (etudecas/worstcase/production_output_products_by_factory_M-1430.png, etudecas/worstcase/production_output_products_by_factory_M-1810.png)
- production_supplier_input_stocks_by_material_*.png (etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-1450.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0500655A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0505677A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0508918A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0514881A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0518684A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0519670A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0520115A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0520132A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0525412A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0901566A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0910216A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0914320A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0914360C.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0914690A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0951020A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0964290A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0989480A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0990780A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD0993480A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD1091642A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD1095770A.png, etudecas/worstcase/production_supplier_input_stocks_by_material_SDC-VD1096202A.png)
- production_dc_factory_outputs_by_material_*.png (etudecas/worstcase/production_dc_factory_outputs_by_material_DC-1920.png)
- supply_graph_poc_geocoded_map_with_factory_hover.html (etudecas/worstcase/supply_graph_poc_geocoded_map_with_factory_hover.html)
