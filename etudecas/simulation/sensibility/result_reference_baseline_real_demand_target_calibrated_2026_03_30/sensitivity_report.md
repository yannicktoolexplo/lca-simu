# Sensitivity Analysis Report

## Setup
- Input: etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_current.json
- Scenario: scn:BASE
- Days override: 0
- OAT delta: +/-20.0%
- Severity profile: aggressive
- Artifact mode: compact
- Kept detailed cases: baseline, baseline_repeat
- Parameter levels: {"lead_time": [0.5, 1.8], "transport_cost": [0.2, 2.0], "supplier_stock": [0.2, 1.8], "production_stock": [0.2, 1.8], "safety_stock_days": [0.2, 2.0], "supplier_reliability": [0.2, 1.0], "demand_item": [0.2, 1.8], "capacity_node": [0.2, 1.8], "supplier_node": [0.2, 1.8], "edge_src_lead_time": [0.5, 1.8], "edge_src_reliability": [0.2, 1.0]}
- Cases total: 242
- Cases success: 242
- Cases failed: 0
- Determinism check (baseline vs repeat): pass (max abs KPI diff=0)

## Top Drivers (normalized sensitivity)
- Fill rate: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": 1.237037975396222, "slope_dy_dx": 1.0985824999999998}, {"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": 0.8494285392562564, "slope_dy_dx": 0.7543562499999998}, {"parameter": "edge_src_reliability_scale::SDC-VD0520132A", "normalized_sensitivity": 0.8395828055062916, "slope_dy_dx": 0.7456124999999999}, {"parameter": "edge_src_reliability_scale::SDC-VD0901566A", "normalized_sensitivity": 0.6940672240520226, "slope_dy_dx": 0.6163837499999999}, {"parameter": "edge_src_reliability_scale::SDC-VD0505677A", "normalized_sensitivity": 0.6050924752976944, "slope_dy_dx": 0.5373674999999999}]
- Ending backlog: [{"parameter": "supplier_reliability_scale", "normalized_sensitivity": -9.815327609122143, "slope_dy_dx": -5825182.928499999}, {"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": -6.739821793438064, "slope_dy_dx": -3999937.283375}, {"parameter": "edge_src_reliability_scale::SDC-VD0520132A", "normalized_sensitivity": -6.661696453256021, "slope_dy_dx": -3953571.597375}, {"parameter": "edge_src_reliability_scale::SDC-VD0901566A", "normalized_sensitivity": -5.507097871243009, "slope_dy_dx": -3268342.513125}, {"parameter": "edge_src_reliability_scale::SDC-VD0505677A", "normalized_sensitivity": -4.801130099553517, "slope_dy_dx": -2849366.0331249996}]
- Total cost: [{"parameter": "edge_src_reliability_scale::SDC-1450", "normalized_sensitivity": 0.466240550893699, "slope_dy_dx": 13017854.194}, {"parameter": "edge_src_reliability_scale::SDC-VD0520132A", "normalized_sensitivity": 0.4394993421722504, "slope_dy_dx": 12271215.671374997}, {"parameter": "transport_cost_scale", "normalized_sensitivity": 0.3999843429086988, "slope_dy_dx": 11167921.464333333}, {"parameter": "capacity_node_scale::SDC-1450", "normalized_sensitivity": 0.3749001329226152, "slope_dy_dx": 10467547.831999999}, {"parameter": "edge_src_reliability_scale::SDC-VD0993480A", "normalized_sensitivity": 0.35604180394752194, "slope_dy_dx": 9941006.379374996}]

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- parameter_sensitivity_summary.csv
- sensitivity_summary.json
- cases/*/input_case.json
- cases/*/simulation_output/(summaries,reports) in compact mode
