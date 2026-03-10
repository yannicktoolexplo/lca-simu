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
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 1.2068076011831104, "slope_dy_dx": 0.95964375}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.258694598285697, "slope_dy_dx": 0.205711875}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": 0.23704416669181777, "slope_dy_dx": 0.18849562499999994}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": -0.1991374410205334, "slope_dy_dx": -0.1583525}, {"parameter": "edge_src_lead_time_scale::SDC-1450", "normalized_sensitivity": 0.1900276430578546, "slope_dy_dx": 0.15110846153846152}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -4.685578235736088, "slope_dy_dx": -1427.469375}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 1.5624018346196658, "slope_dy_dx": 475.988375}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 1.3463503978477716, "slope_dy_dx": 410.16793749999994}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": -1.0044138109191578, "slope_dy_dx": -305.996375}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": -0.9203559343341919, "slope_dy_dx": -280.388}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.9275588415881905, "slope_dy_dx": 1180080.0}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.4484331933753309, "slope_dy_dx": 570515.8736153845}, {"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": 0.06810745856180621, "slope_dy_dx": 86649.21953846164}, {"parameter": "edge_src_lead_time_scale::SDC-VD0960508A", "normalized_sensitivity": 0.06810745856180621, "slope_dy_dx": 86649.21953846164}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": 0.06810717886191604, "slope_dy_dx": 86648.86369230763}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
