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
- Fill rate: [{"parameter": "supplier_stock_scale", "normalized_sensitivity": 0.260493242142629, "slope_dy_dx": 0.24627500000000002}, {"parameter": "lead_time_scale", "normalized_sensitivity": -0.20911914095140988, "slope_dy_dx": -0.19770500000000002}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": -0.18303808474135264, "slope_dy_dx": -0.1730475000000001}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.17415312591890575, "slope_dy_dx": -0.16464750000000003}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": 0.14176269121171817, "slope_dy_dx": 0.13402500000000014}]
- Ending backlog: [{"parameter": "supplier_stock_scale", "normalized_sensitivity": -4.511973334505874, "slope_dy_dx": -369.4115000000001}, {"parameter": "demand_item_scale::item:268091", "normalized_sensitivity": 3.970299950167088, "slope_dy_dx": 325.0627500000001}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 3.8349602313810567, "slope_dy_dx": 313.9820000000001}, {"parameter": "lead_time_scale", "normalized_sensitivity": 3.622123004240684, "slope_dy_dx": 296.5562500000001}, {"parameter": "capacity_node_scale::M-1810", "normalized_sensitivity": -2.455464887338532, "slope_dy_dx": -201.03775000000005}]
- Total cost: [{"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.9210759993932265, "slope_dy_dx": 26456.72800000001}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.5094352807130255, "slope_dy_dx": 14632.875750000007}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.14869530055418861, "slope_dy_dx": -4271.081999999998}, {"parameter": "transport_cost_scale", "normalized_sensitivity": 0.1375492855750977, "slope_dy_dx": 3950.9270000000024}, {"parameter": "supplier_stock_scale", "normalized_sensitivity": 0.0731824547036017, "slope_dy_dx": 2102.0722499999924}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- sensitivity_summary.json
- cases/*/simulation_output/first_simulation_summary.json
