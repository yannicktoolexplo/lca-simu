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
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 1.228413084176512, "slope_dy_dx": 0.677815}, {"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": 0.7096044445169369, "slope_dy_dx": 0.39154625}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.4652219358767336, "slope_dy_dx": -0.25670062499999996}, {"parameter": "production_stock_scale", "normalized_sensitivity": 0.4247563797956073, "slope_dy_dx": 0.23437249999999998}, {"parameter": "supplier_node_scale::SDC-1450", "normalized_sensitivity": 0.3749687375969814, "slope_dy_dx": 0.206900625}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -1.512238834941937, "slope_dy_dx": -1974.1352499999998}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 1.0194914441795357, "slope_dy_dx": 1330.8836875}, {"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": -0.8735597180043981, "slope_dy_dx": -1140.3787499999999}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 0.704807408436152, "slope_dy_dx": 920.0829375000001}, {"parameter": "production_stock_scale", "normalized_sensitivity": -0.5228961135520103, "slope_dy_dx": -682.608875}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.9510156563374934, "slope_dy_dx": 1180080.0}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.44756488705456826, "slope_dy_dx": 555366.6423846154}, {"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": 0.06982982091988586, "slope_dy_dx": 86649.23076923077}, {"parameter": "edge_src_lead_time_scale::SDC-VD0960508A", "normalized_sensitivity": 0.06982982091988586, "slope_dy_dx": 86649.23076923077}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": 0.06982982091988586, "slope_dy_dx": 86649.23076923077}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
