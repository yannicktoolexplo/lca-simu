# Sensitivity Analysis Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 60
- OAT delta: +/-20.0%
- Severity profile: aggressive
- Parameter levels: {"lead_time": [0.5, 1.8], "transport_cost": [0.2, 2.0], "supplier_stock": [0.2, 1.8], "production_stock": [0.2, 1.8], "safety_stock_days": [0.2, 2.0], "supplier_reliability": [0.2, 1.0], "demand_item": [0.2, 1.8], "capacity_node": [0.2, 1.8], "supplier_node": [0.2, 1.8], "edge_src_lead_time": [0.5, 1.8], "edge_src_reliability": [0.2, 1.0]}
- Cases total: 242
- Cases success: 242
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 1.2284167689168946, "slope_dy_dx": 0.6797825}, {"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": 0.7126148169163741, "slope_dy_dx": 0.3943475}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.46258590374443637, "slope_dy_dx": -0.25598624999999997}, {"parameter": "production_stock_scale", "normalized_sensitivity": 0.42280544507310514, "slope_dy_dx": 0.2339725}, {"parameter": "supplier_node_scale::SDC-1450", "normalized_sensitivity": 0.3731617547404049, "slope_dy_dx": 0.20650062500000002}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -1.5220647006687305, "slope_dy_dx": -1979.8681249999997}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 1.0209049715558667, "slope_dy_dx": 1327.970625}, {"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": -0.882960400080598, "slope_dy_dx": -1148.5353750000002}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 0.6960926035105609, "slope_dy_dx": 905.4618750000001}, {"parameter": "production_stock_scale", "normalized_sensitivity": -0.5238739257485846, "slope_dy_dx": -681.4436249999998}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.9508724125341024, "slope_dy_dx": 1180080.0}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.4476544400925107, "slope_dy_dx": 555561.445153846}, {"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": 0.06970327221744099, "slope_dy_dx": 86505.2307692308}, {"parameter": "edge_src_lead_time_scale::SDC-VD0960508A", "normalized_sensitivity": 0.06970327221744099, "slope_dy_dx": 86505.2307692308}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": 0.06970327221744099, "slope_dy_dx": 86505.2307692308}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
