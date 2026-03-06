# Sensitivity Analysis Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 30
- OAT delta: +/-20.0%
- Cases total: 20
- Cases success: 20
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.36840170833830566, "slope_dy_dx": -0.29017749999999987}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": 0.29535996221748845, "slope_dy_dx": 0.23264500000000027}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.269276571541745, "slope_dy_dx": 0.21210000000000012}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": -0.22403531446069763, "slope_dy_dx": -0.17646499999999984}, {"parameter": "supplier_stock_scale", "normalized_sensitivity": -0.03383731175396654, "slope_dy_dx": -0.02665249999999981}]
- Ending backlog: [{"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 1.8985651624391007, "slope_dy_dx": 599.6572500000001}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 1.41658587875925, "slope_dy_dx": 447.4252500000001}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": -1.0956605337510876, "slope_dy_dx": -346.06175}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": -0.9988978861957477, "slope_dy_dx": -315.4995}, {"parameter": "supplier_stock_scale", "normalized_sensitivity": 0.12552177062608666, "slope_dy_dx": 39.64574999999997}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.926744759141119, "slope_dy_dx": 1180080.0000000005}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.7231202982564251, "slope_dy_dx": 920792.692}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.06266912020378342, "slope_dy_dx": 79800.37075000002}, {"parameter": "transport_cost_scale", "normalized_sensitivity": 0.017465571769690862, "slope_dy_dx": 22239.966000000135}, {"parameter": "supplier_stock_scale", "normalized_sensitivity": 0.006757320482782694, "slope_dy_dx": 8604.503749999569}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
