# Sensitivity Analysis Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 30
- OAT delta: +/-20.0%
- Cases total: 18
- Cases success: 18
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.46591043905019963, "slope_dy_dx": 0.3416675}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": 0.46591043905019963, "slope_dy_dx": 0.3416675}, {"parameter": "lead_time_scale", "normalized_sensitivity": -0.45454452479296603, "slope_dy_dx": -0.33333250000000014}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": -0.42929337695153497, "slope_dy_dx": -0.314815}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.42929337695153497, "slope_dy_dx": -0.314815}]
- Ending backlog: [{"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 1.6875000000000004, "slope_dy_dx": 675.0000000000001}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 1.6875000000000004, "slope_dy_dx": 675.0000000000001}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": -1.2812500000000002, "slope_dy_dx": -512.5000000000001}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": -1.2812500000000002, "slope_dy_dx": -512.5000000000001}, {"parameter": "lead_time_scale", "normalized_sensitivity": 1.2500000000000002, "slope_dy_dx": 500.0000000000001}]
- Total cost: [{"parameter": "supplier_stock_scale", "normalized_sensitivity": 0.6690302031461398, "slope_dy_dx": 4946.010500000001}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.6556230814118484, "slope_dy_dx": 4846.894250000001}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.27194724844666573, "slope_dy_dx": 2010.453250000001}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": 0.06691775761463241, "slope_dy_dx": 494.71000000000015}, {"parameter": "transport_cost_scale", "normalized_sensitivity": 0.01647547629411629, "slope_dy_dx": 121.80000000000067}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
