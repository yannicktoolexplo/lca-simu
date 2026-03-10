# First simulation report

## Run setup
- Input: etudecas/simulation/result/capacity_x2_annual/input_capacity_x2.json
- Scenario: scn:BASE
- Horizon (days): 365
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 1.0
- Stochastic lead times: True
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 1.0
- External procurement enabled: True
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
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 24

## KPIs
- Total demand: 17400.0
- Total served: 11214.6896
- Fill rate: 0.644522
- Ending backlog: 6185.3104
- Total produced: 27744.5834
- Total shipped: 256007.6878
- Avg inventory: 1121280.3376
- Ending inventory: 1126276.9208
- Transport cost: 117491.0842
- Holding cost: 16313799.6024
- Purchase cost (from order_terms sell_price): 20721.4749
- Logistics cost (transport + holding): 16431290.6867
- Total cost: 16452012.1616
- Total external procured ordered qty: 217005.3331
- Total external procured arrived qty: 215886.8031
- Total external procured rejected qty (cap-limited): 357.3336
- Total external procurement cost premium: 20127.1564
- Cost share holding / transport / purchase: 0.991599 / 0.007141 / 0.00126
- Total opening stock bootstrap qty: 1137275.7795
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 2597.7963
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct', 'transport_cost_share_below_2pct', 'purchase_cost_share_below_2pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 6041.8729
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 143.4375
  }
]

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
- production_input_stocks_by_material_*.png (etudecas/simulation/result/capacity_x2_annual/plots/factories/input_stocks/production_input_stocks_by_material_M-1430.png, etudecas/simulation/result/capacity_x2_annual/plots/factories/input_stocks/production_input_stocks_by_material_M-1810.png, etudecas/simulation/result/capacity_x2_annual/plots/factories/input_stocks/production_input_stocks_by_material_SDC-1450.png)
- production_output_products.png (etudecas/simulation/result/capacity_x2_annual/plots/factories/output_products/production_output_products.png)
- production_output_products_by_factory_*.png (etudecas/simulation/result/capacity_x2_annual/plots/factories/output_products/production_output_products_by_factory_M-1430.png, etudecas/simulation/result/capacity_x2_annual/plots/factories/output_products/production_output_products_by_factory_M-1810.png, etudecas/simulation/result/capacity_x2_annual/plots/factories/output_products/production_output_products_by_factory_SDC-1450.png)
- production_supplier_input_stocks_by_material_*.png (etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-1450.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0500655A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0505677A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0508918A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0514881A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0518684A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0519670A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0520115A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0520132A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0525412A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0901566A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0910216A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0914320A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0914360C.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0914690A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0949099A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0951020A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0960508A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0964290A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0972460A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0975221A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0989480A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0990780A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD0993480A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD1091642A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD1095770A.png, etudecas/simulation/result/capacity_x2_annual/plots/suppliers/input_stocks/production_supplier_input_stocks_by_material_SDC-VD1096202A.png)
- production_dc_factory_outputs_by_material_*.png (etudecas/simulation/result/capacity_x2_annual/plots/distribution_centers/factory_outputs/production_dc_factory_outputs_by_material_DC-1920.png)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (etudecas/simulation/result/capacity_x2_annual/maps/supply_graph_poc_geocoded_map_with_factory_hover.html)
