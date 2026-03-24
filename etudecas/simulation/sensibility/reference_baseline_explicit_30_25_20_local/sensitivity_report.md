# Sensitivity Analysis Report

## Setup
- Input: etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_explicit_30_25_20.json
- Scenario: scn:BASE
- Days override: 365
- OAT delta: +/-20.0%
- Severity profile: balanced
- Artifact mode: full
- Kept detailed cases: baseline, baseline_repeat
- Parameter levels: {"lead_time": [0.8, 1.2], "transport_cost": [0.8, 1.2], "supplier_stock": [0.8, 1.2], "production_stock": [0.8, 1.2], "safety_stock_days": [0.8, 1.2], "supplier_reliability": [0.8, 1.0], "demand_item": [0.8, 1.2], "capacity_node": [0.8, 1.2], "supplier_node": [0.8, 1.2], "edge_src_lead_time": [0.8, 1.2], "edge_src_reliability": [0.8, 1.0]}
- Cases total: 242
- Cases success: 242
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 1.709535185666061, "slope_dy_dx": 1.6458550000000003}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.30962607115035073, "slope_dy_dx": -0.29809250000000015}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.30199688392625307, "slope_dy_dx": 0.29074750000000016}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.19166969618280968, "slope_dy_dx": 0.18453}, {"parameter": "edge_src_lead_time_scale::SDC-VD0914690A", "normalized_sensitivity": 0.1856998182290316, "slope_dy_dx": 0.17878250000000015}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -44.183812309747864, "slope_dy_dx": -28637.870500000005}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 8.80265539155107, "slope_dy_dx": 5705.467500000001}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": -7.805284786153888, "slope_dy_dx": -5059.018750000001}, {"parameter": "lead_time_scale", "normalized_sensitivity": -4.953760917561133, "slope_dy_dx": -3210.7950000000005}, {"parameter": "edge_src_lead_time_scale::SDC-VD0914690A", "normalized_sensitivity": -4.799476358205548, "slope_dy_dx": -3110.7950000000005}]
- Total cost: [{"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.8188887726727632, "slope_dy_dx": 7960712.400000004}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.32560280040700323, "slope_dy_dx": 3165301.976500001}, {"parameter": "edge_src_lead_time_scale::SDC-VD0975221A", "normalized_sensitivity": -0.2591884391289195, "slope_dy_dx": -2519664.074249999}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": -0.25699034054219, "slope_dy_dx": -2498295.567000001}, {"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": -0.25698626330908775, "slope_dy_dx": -2498255.9307500026}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- parameter_sensitivity_summary.csv
- sensitivity_summary.json
- cases/*/input_case.json
- cases/*/simulation_output/(summaries,reports) in compact mode
