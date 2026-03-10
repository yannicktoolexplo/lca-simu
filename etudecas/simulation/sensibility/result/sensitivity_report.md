# Sensitivity Analysis Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 365
- OAT delta: +/-20.0%
- Severity profile: balanced
- Parameter levels: {"lead_time": [0.8, 1.2], "transport_cost": [0.8, 1.2], "supplier_stock": [0.8, 1.2], "production_stock": [0.8, 1.2], "safety_stock_days": [0.8, 1.2], "supplier_reliability": [0.8, 1.0], "demand_item": [0.8, 1.2], "capacity_node": [0.8, 1.2], "supplier_node": [0.8, 1.2], "edge_src_lead_time": [0.8, 1.2], "edge_src_reliability": [0.8, 1.0]}
- Cases total: 242
- Cases success: 242
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 1.8089291140532022, "slope_dy_dx": 1.6311150000000005}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": 0.21206008193394257, "slope_dy_dx": 0.1912149999999999}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.19572153549620616, "slope_dy_dx": 0.17648250000000007}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.1749996118451552, "slope_dy_dx": -0.15779750000000012}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": -0.17176129142443955, "slope_dy_dx": -0.15487749999999997}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -16.593531621238782, "slope_dy_dx": -28381.38400000001}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 2.2459615020775403, "slope_dy_dx": 3841.466500000001}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 2.207570222061843, "slope_dy_dx": 3775.8025000000007}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": -1.9452423788655258, "slope_dy_dx": -3327.120000000001}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": -1.7953816805586382, "slope_dy_dx": -3070.8000000000006}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.9377361814396071, "slope_dy_dx": 14357640.000000004}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.7013729509798906, "slope_dy_dx": 10738692.326499999}, {"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": 0.22374837323218816, "slope_dy_dx": 3425802.114749999}, {"parameter": "edge_src_lead_time_scale::SDC-VD0960508A", "normalized_sensitivity": 0.22374837323218816, "slope_dy_dx": 3425802.114749999}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": 0.22373785950456732, "slope_dy_dx": 3425641.1395000024}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
