# Sensitivity Analysis Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 30
- OAT delta: +/-20.0%
- Cases total: 132
- Cases success: 132
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 0.9401891156911688, "slope_dy_dx": 0.7405550000000001}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.36840170833830566, "slope_dy_dx": -0.29017749999999987}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": 0.29535996221748845, "slope_dy_dx": 0.23264500000000027}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.269276571541745, "slope_dy_dx": 0.21210000000000012}, {"parameter": "edge_src_lead_time_scale::SDC-1450", "normalized_sensitivity": 0.22657763569837974, "slope_dy_dx": 0.17846749999999997}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -3.4876701611789995, "slope_dy_dx": -1101.5722500000002}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 1.8985651624391007, "slope_dy_dx": 599.6572500000001}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 1.41658587875925, "slope_dy_dx": 447.4252500000001}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": -1.0956605337510876, "slope_dy_dx": -346.06175}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": -0.9988978861957477, "slope_dy_dx": -315.4995}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.926744759141119, "slope_dy_dx": 1180080.0000000005}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.7231202982564251, "slope_dy_dx": 920792.692}, {"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": 0.22115499934049426, "slope_dy_dx": 281610.00000000006}, {"parameter": "edge_src_lead_time_scale::SDC-VD0960508A", "normalized_sensitivity": 0.22115499934049426, "slope_dy_dx": 281610.00000000006}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": 0.22115386395879522, "slope_dy_dx": 281608.5542500002}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
