# Sensitivity Analysis Report

## Setup
- Input: etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_explicit_30_25_20.json
- Scenario: scn:BASE
- Days override: 365
- OAT delta: +/-20.0%
- Severity profile: aggressive
- Artifact mode: full
- Kept detailed cases: baseline, baseline_repeat
- Parameter levels: {"lead_time": [0.5, 1.8], "transport_cost": [0.2, 2.0], "supplier_stock": [0.2, 1.8], "production_stock": [0.2, 1.8], "safety_stock_days": [0.2, 2.0], "supplier_reliability": [0.2, 1.0], "demand_item": [0.2, 1.8], "capacity_node": [0.2, 1.8], "supplier_node": [0.2, 1.8], "edge_src_lead_time": [0.5, 1.8], "edge_src_reliability": [0.2, 1.0]}
- Cases total: 242
- Cases success: 242
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 1.188495196052973, "slope_dy_dx": 1.1442237499999999}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": 0.22957283822383798, "slope_dy_dx": 0.22102125}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": -0.19185536224357305, "slope_dy_dx": -0.18470874999999998}, {"parameter": "lead_time_scale", "normalized_sensitivity": 0.12012544194315161, "slope_dy_dx": 0.11565076923076921}, {"parameter": "edge_src_lead_time_scale::SDC-VD0914690A", "normalized_sensitivity": 0.114889639054791, "slope_dy_dx": 0.11061000000000004}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -30.717276437816373, "slope_dy_dx": -19909.494874999997}, {"parameter": "demand_item_scale::item:268967", "normalized_sensitivity": 6.942037605318497, "slope_dy_dx": 4499.5025}, {"parameter": "capacity_node_scale::M-1430", "normalized_sensitivity": -5.9334350840002275, "slope_dy_dx": -3845.77375}, {"parameter": "lead_time_scale", "normalized_sensitivity": -3.1047062843305393, "slope_dy_dx": -2012.3246923076924}, {"parameter": "edge_src_lead_time_scale::SDC-VD0914690A", "normalized_sensitivity": -2.9693702424724266, "slope_dy_dx": -1924.6062307692307}]
- Total cost: [{"parameter": "edge_src_lead_time_scale::SDC-VD0949099A", "normalized_sensitivity": -2.928819104322094, "slope_dy_dx": -28472104.31892308}, {"parameter": "edge_src_lead_time_scale::SDC-VD0960508A", "normalized_sensitivity": -2.928819104322094, "slope_dy_dx": -28472104.31892308}, {"parameter": "edge_src_lead_time_scale::SDC-VD0972460A", "normalized_sensitivity": -2.928819104322094, "slope_dy_dx": -28472104.31892308}, {"parameter": "edge_src_lead_time_scale::SDC-VD0975221A", "normalized_sensitivity": -2.928819104322094, "slope_dy_dx": -28472104.31892308}, {"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.8188887726727626, "slope_dy_dx": 7960712.399999999}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- parameter_sensitivity_summary.csv
- sensitivity_summary.json
- cases/*/input_case.json
- cases/*/simulation_output/(summaries,reports) in compact mode
