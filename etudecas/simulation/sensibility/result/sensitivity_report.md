# Sensitivity Analysis Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 30
- OAT delta: +/-20.0%
- Severity profile: aggressive
- Parameter levels: {"lead_time": [0.5, 1.8], "transport_cost": [0.2, 2.0], "supplier_stock": [0.2, 1.8], "production_stock": [0.2, 1.8], "safety_stock_days": [0.2, 2.0], "supplier_reliability": [0.2, 1.0], "demand_item": [0.2, 1.8], "capacity_node": [0.2, 1.8], "supplier_node": [0.2, 1.8], "edge_src_lead_time": [0.5, 1.8], "edge_src_reliability": [0.2, 1.0]}
- Cases total: 242
- Cases success: 242
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 1.205688328443946, "slope_dy_dx": 0.9419849999999999}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.28666512433378905, "slope_dy_dx": 0.223966875}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": 0.2546953156598625, "slope_dy_dx": 0.198989375}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.18254965543899526, "slope_dy_dx": -0.142623125}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": -0.15458767234449952, "slope_dy_dx": -0.12077687499999996}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -4.306896121404293, "slope_dy_dx": -1401.2029999999997}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 1.446032589351305, "slope_dy_dx": 470.451375}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 1.2969088972931035, "slope_dy_dx": 421.9355625}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": -1.024011002048937, "slope_dy_dx": -333.151125}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": -0.9098071890462698, "slope_dy_dx": -295.996125}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.9263299430273622, "slope_dy_dx": 1180080.0}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.4468535480184374, "slope_dy_dx": 569260.3795384616}, {"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": 0.06801723357893219, "slope_dy_dx": 86649.23076923077}, {"parameter": "edge_src_lead_time_scale::SDC-VD0960508A", "normalized_sensitivity": 0.06801723357893219, "slope_dy_dx": 86649.23076923077}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": 0.0680168843870873, "slope_dy_dx": 86648.78592307697}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
