# Sensitivity Analysis Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 30
- OAT delta: +/-20.0%
- Severity profile: aggressive
- Parameter levels: {"lead_time": [0.5, 1.8], "transport_cost": [0.2, 2.0], "supplier_stock": [0.2, 1.8], "production_stock": [0.2, 1.8], "safety_stock_days": [0.2, 2.0], "supplier_reliability": [0.2, 1.0], "demand_item": [0.2, 1.8], "capacity_node": [0.2, 1.8], "supplier_node": [0.2, 1.8], "edge_src_lead_time": [0.5, 1.8], "edge_src_reliability": [0.2, 1.0]}
- Cases total: 186
- Cases success: 186
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 1.2068598873126426, "slope_dy_dx": 0.9506024999999999}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.27663533782085303, "slope_dy_dx": 0.21789625}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": 0.24963071276403964, "slope_dy_dx": 0.19662562500000003}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": -0.15119670012416425, "slope_dy_dx": -0.11909249999999996}, {"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": 0.15017945423567852, "slope_dy_dx": 0.11829124999999996}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -4.476909512689031, "slope_dy_dx": -1414.0211249999998}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 1.3644707526667923, "slope_dy_dx": 430.96481249999994}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 1.3534268583962645, "slope_dy_dx": 427.476625}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": -1.0261946742669568, "slope_dy_dx": -324.12112500000006}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": -0.9260179988703412, "slope_dy_dx": -292.4805625}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.9267447591411184, "slope_dy_dx": 1180079.9999999998}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.4463268361130446, "slope_dy_dx": 568334.8813846154}, {"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": 0.06804768237883588, "slope_dy_dx": 86649.21838461547}, {"parameter": "edge_src_lead_time_scale::SDC-VD0960508A", "normalized_sensitivity": 0.06804768237883588, "slope_dy_dx": 86649.21838461547}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": 0.0680473330306208, "slope_dy_dx": 86648.77353846167}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
