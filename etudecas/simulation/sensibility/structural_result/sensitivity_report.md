# Sensitivity Analysis Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 60
- OAT delta: +/-20.0%
- Severity profile: aggressive
- Parameter levels: {"lead_time": [0.5, 1.8], "transport_cost": [0.2, 2.0], "supplier_stock": [0.2, 1.8], "production_stock": [0.2, 1.8], "safety_stock_days": [0.2, 2.0], "supplier_reliability": [0.2, 1.0], "demand_item": [0.2, 1.8], "capacity_node": [0.2, 1.8], "supplier_node": [0.2, 1.8], "edge_src_lead_time": [0.5, 1.8], "edge_src_reliability": [0.2, 1.0]}
- Cases total: 186
- Cases success: 186
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 1.228257501184877, "slope_dy_dx": 0.6737974999999998}, {"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": 0.7064512012833132, "slope_dy_dx": 0.387545}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.46012204236392135, "slope_dy_dx": -0.25241374999999994}, {"parameter": "production_stock_scale", "normalized_sensitivity": 0.42723486091363155, "slope_dy_dx": 0.23437249999999998}, {"parameter": "supplier_node_scale::SDC-1450", "normalized_sensitivity": 0.3767921269459332, "slope_dy_dx": 0.20670062500000003}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -1.492618580704458, "slope_dy_dx": -1962.4362499999997}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 0.9989690043975302, "slope_dy_dx": 1313.4051875}, {"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": -0.858503281243499, "slope_dy_dx": -1128.7263749999995}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 0.6909051966643055, "slope_dy_dx": 908.375}, {"parameter": "production_stock_scale", "normalized_sensitivity": -0.5191886820164309, "slope_dy_dx": -682.608875}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.9508519195474325, "slope_dy_dx": 1180080.0}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.4474654863508108, "slope_dy_dx": 555338.9126923076}, {"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": 0.06970176998831991, "slope_dy_dx": 86505.23076923062}, {"parameter": "edge_src_lead_time_scale::SDC-VD0960508A", "normalized_sensitivity": 0.06970176998831991, "slope_dy_dx": 86505.23076923062}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": 0.06970176998831991, "slope_dy_dx": 86505.23076923062}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
