# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/shock_campaign_result/cases/combo_extreme_black_swan/input_case.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 7.0
- Replenishment review period (days): 7
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
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 23

## KPIs
- Total demand: 3360.0
- Total served: 273.1641
- Fill rate: 0.081299
- Ending backlog: 3086.8359
- Total produced: 1257.367
- Total shipped: 7413.1994
- Avg inventory: 868127.9617
- Ending inventory: 853199.5654
- Transport cost: 3226.1441
- Holding cost: 1036261.8912
- Purchase cost (from order_terms sell_price): 523.8464
- Logistics cost (transport + holding): 1039488.0353
- Total cost: 1040011.8817
- Total external procured ordered qty: 7361.7137
- Total external procured arrived qty: 5662.0787
- Total external procured rejected qty (cap-limited): 43329.8497
- Total external procurement cost premium: 537.9121
- Cost share holding / transport / purchase: 0.996394 / 0.003102 / 0.000504
- Total opening stock bootstrap qty: 877714.6432
- Total unreliable supplier loss qty: 2471.0665
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct', 'transport_cost_share_below_2pct', 'purchase_cost_share_below_2pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 1569.2578
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 1517.5781
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
- production_demand_service_daily.csv
- production_constraint_daily.csv
- production_supplier_shipments_daily.csv
- production_supplier_stocks_daily.csv
- production_dc_stocks_daily.csv
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
