# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/shock_campaign_result/cases/combo_supplier_crunch/input_case.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 7.0
- Replenishment review period (days): 4
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
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
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 22

## KPIs
- Total demand: 1500.0
- Total served: 626.4402
- Fill rate: 0.417627
- Ending backlog: 873.5598
- Total produced: 1064.6439
- Total shipped: 22305.6039
- Avg inventory: 35065.6391
- Ending inventory: 21991.787
- Transport cost: 1818.9231
- Holding cost: 35173.343
- Purchase cost (from order_terms sell_price): 1417.171
- Logistics cost (transport + holding): 36992.266
- Total cost: 38409.4371
- Total external procured ordered qty: 26931.3772
- Total external procured arrived qty: 23205.8174
- Total external procured rejected qty (cap-limited): 53431.087
- Total external procurement cost premium: 1976.1046
- Cost share holding / transport / purchase: 0.915747 / 0.047356 / 0.036896
- Total opening stock bootstrap qty: 48539.3447
- Total unreliable supplier loss qty: 5576.401
- Economic consistency status: warn
- Economic consistency warnings: ['holding_cost_share_above_90pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 461.1147
  },
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268967",
    "backlog": 412.4451
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
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
