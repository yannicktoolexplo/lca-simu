# Sensitivity Analysis Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 60
- OAT delta: +/-20.0%
- Cases total: 132
- Cases success: 132
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 1.1192989172044188, "slope_dy_dx": 0.6140249999999999}, {"parameter": "production_stock_scale", "normalized_sensitivity": 0.5276987859564696, "slope_dy_dx": 0.2894850000000001}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.4601152065332311, "slope_dy_dx": -0.2524099999999999}, {"parameter": "supplier_node_scale::SDC-1450", "normalized_sensitivity": 0.4369189543913378, "slope_dy_dx": 0.2396850000000001}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.42156112144081087, "slope_dy_dx": 0.23126}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -1.3602053210139309, "slope_dy_dx": -1788.3445000000004}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 1.0455771533177103, "slope_dy_dx": 1374.6837500000001}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 0.9385498821192327, "slope_dy_dx": 1233.9685}, {"parameter": "production_stock_scale", "normalized_sensitivity": -0.6412744920045148, "slope_dy_dx": -843.1225000000003}, {"parameter": "supplier_node_scale::SDC-1450", "normalized_sensitivity": -0.5309532753755112, "slope_dy_dx": -698.0764999999998}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.9508519195474325, "slope_dy_dx": 1180080.0}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.7203487996411585, "slope_dy_dx": 894007.9880000004}, {"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": 0.22680631967484344, "slope_dy_dx": 281483.9999999997}, {"parameter": "edge_src_lead_time_scale::SDC-VD0960508A", "normalized_sensitivity": 0.22680631967484344, "slope_dy_dx": 281483.9999999997}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": 0.22680631967484344, "slope_dy_dx": 281483.9999999997}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
