# First simulation report

## Run setup
- Input: etudecas/simulation/sensibility/targeted_plan_result/cases/resilience_combo/input_case.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 14.0
- Replenishment review period (days): 1
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
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 23

## KPIs
- Total demand: 1500.0
- Total served: 1483.5795
- Fill rate: 0.989053
- Ending backlog: 16.4205
- Total produced: 1481.9495
- Total shipped: 57747.1754
- Avg inventory: 26820.3006
- Ending inventory: 23818.4046
- Transport cost: 4103.5109
- Holding cost: 24952.8226
- Purchase cost (from order_terms sell_price): 3097.3772
- Logistics cost (transport + holding): 29056.3335
- Total cost: 32153.7107
- Total external procured ordered qty: 55273.3859
- Total external procured arrived qty: 50990.8031
- Total external procured rejected qty (cap-limited): 18725.1734
- Total external procurement cost premium: 4144.8841
- Cost share holding / transport / purchase: 0.776048 / 0.127622 / 0.09633
- Total opening stock bootstrap qty: 33337.8826
- Total unreliable supplier loss qty: 0.0
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 16.4205
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
