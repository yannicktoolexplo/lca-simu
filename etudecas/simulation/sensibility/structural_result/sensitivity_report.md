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
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 2.154671434957533, "slope_dy_dx": 0.18316000000000002}, {"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": 0.5524904124414748, "slope_dy_dx": 0.04696500000000001}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": -0.5050525845234454, "slope_dy_dx": -0.04293249999999999}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.5050525845234454, "slope_dy_dx": -0.04293249999999999}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.4487330306096044, "slope_dy_dx": 0.038145000000000026}]
- Ending backlog: [{"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 0.546451869794363, "slope_dy_dx": 8700.000000000002}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 0.546451869794363, "slope_dy_dx": 8700.000000000002}, {"parameter": "supplier_reliability_scale", "normalized_sensitivity": -0.20017722250674724, "slope_dy_dx": -3186.9995000000026}, {"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": -0.0513276902400266, "slope_dy_dx": -817.1824999999992}, {"parameter": "lead_time_scale", "normalized_sensitivity": -0.04168628502158232, "slope_dy_dx": -663.6827500000028}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.9822762657524535, "slope_dy_dx": 7178820.000000004}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.7207822869629886, "slope_dy_dx": 5267730.146499999}, {"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": 0.23427655669336694, "slope_dy_dx": 1712175.3719999995}, {"parameter": "edge_src_lead_time_scale::SDC-VD0960508A", "normalized_sensitivity": 0.23427655669336694, "slope_dy_dx": 1712175.3719999995}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": 0.23427655669336694, "slope_dy_dx": 1712175.3719999995}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
