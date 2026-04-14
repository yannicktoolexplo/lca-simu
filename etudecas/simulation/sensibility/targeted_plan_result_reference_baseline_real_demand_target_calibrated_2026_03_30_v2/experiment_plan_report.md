# Targeted Experiment Plan Report

## Setup
- Input: etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_current.json
- Scenario: scn:BASE
- Days override: 0
- Scenarios total: 15
- Success: 15
- Failed: 0

## Baseline KPIs
{
  "kpi::avg_inventory": 19766465.3509,
  "kpi::cost_share_holding": 0.149954,
  "kpi::cost_share_inventory_risk": 0.085688,
  "kpi::cost_share_purchase": 0.171575,
  "kpi::cost_share_transport": 0.399984,
  "kpi::cost_share_warehouse_operating": 0.192798,
  "kpi::ending_backlog": 593478.1966,
  "kpi::ending_inventory": 18941957.7433,
  "kpi::fill_rate": 0.888075,
  "kpi::measured_required_total": 5302452.7143,
  "kpi::measurement_starting_backlog": 0.0,
  "kpi::total_arrived": 125812449.8774,
  "kpi::total_cost": 27920896.5609,
  "kpi::total_demand": 5302452.7143,
  "kpi::total_estimated_source_ordered_qty": 104693283.3055,
  "kpi::total_estimated_source_rejected_qty": 28206355.8413,
  "kpi::total_estimated_source_replenished_qty": 103072199.171,
  "kpi::total_explicit_initialization_pipeline_qty": 0.0,
  "kpi::total_explicit_initialization_stock_qty": 35076.3627,
  "kpi::total_external_procured_arrived_qty": 0.0,
  "kpi::total_external_procured_ordered_qty": 0.0,
  "kpi::total_external_procured_qty": 0.0,
  "kpi::total_external_procured_rejected_qty": 0.0,
  "kpi::total_external_procurement_cost": 0.0,
  "kpi::total_holding_cost": 4186854.545,
  "kpi::total_inventory_cost_legacy_raw_holding": 11962441.5571,
  "kpi::total_inventory_risk_cost": 2392488.3114,
  "kpi::total_logistics_cost": 23130363.0215,
  "kpi::total_opening_stock_bootstrap_qty": 0.0,
  "kpi::total_produced": 17869743.232,
  "kpi::total_purchase_cost": 4790533.5394,
  "kpi::total_served": 4708974.5176,
  "kpi::total_shipped": 127074616.6123,
  "kpi::total_supplier_capacity_binding_qty": 1580070.6283,
  "kpi::total_transport_cost": 11167921.4643,
  "kpi::total_unreliable_loss_qty": 0.0,
  "kpi::total_warehouse_operating_cost": 5383098.7007,
  "kpi::warmup_backlog_cleared_qty": 2131254.1763
}

## Top scenarios
- Best fill rate: [{"scenario_id": "resilience_combo", "category": "combined_mitigation", "kpi::fill_rate": 0.914679, "kpi::total_cost": 29121487.6889, "kpi::ending_backlog": 452411.9447}, {"scenario_id": "safety_stock_high", "category": "inventory_policy", "kpi::fill_rate": 0.888982, "kpi::total_cost": 27931503.7327, "kpi::ending_backlog": 588665.9108}, {"scenario_id": "lead_time_plus_20pct", "category": "supplier_risk", "kpi::fill_rate": 0.884367, "kpi::total_cost": 28479825.9274, "kpi::ending_backlog": 613136.4467}, {"scenario_id": "safety_stock_low", "category": "inventory_policy", "kpi::fill_rate": 0.883724, "kpi::total_cost": 27627808.0051, "kpi::ending_backlog": 616545.7954}, {"scenario_id": "lead_time_plus_40pct", "category": "supplier_risk", "kpi::fill_rate": 0.879581, "kpi::total_cost": 27899097.549, "kpi::ending_backlog": 638515.3629}]
- Lowest total cost: [{"scenario_id": "review_period_7d", "category": "inventory_policy", "kpi::total_cost": 18189413.5696, "kpi::fill_rate": 0.215136, "kpi::ending_backlog": 4161703.3164}, {"scenario_id": "review_period_2d", "category": "inventory_policy", "kpi::total_cost": 25859182.8737, "kpi::fill_rate": 0.571485, "kpi::ending_backlog": 2272178.7586}, {"scenario_id": "stress_combo", "category": "combined_stress", "kpi::total_cost": 26419479.0527, "kpi::fill_rate": 0.451837, "kpi::ending_backlog": 3934750.9574}, {"scenario_id": "capacity_m1430_minus_15pct", "category": "production_risk", "kpi::total_cost": 26810237.6389, "kpi::fill_rate": 0.869255, "kpi::ending_backlog": 693269.8415}, {"scenario_id": "supplier_reliability_85", "category": "supplier_risk", "kpi::total_cost": 27439695.0755, "kpi::fill_rate": 0.64471, "kpi::ending_backlog": 1883908.2504}]
- Lowest ending backlog: [{"scenario_id": "resilience_combo", "category": "combined_mitigation", "kpi::ending_backlog": 452411.9447, "kpi::fill_rate": 0.914679, "kpi::total_cost": 29121487.6889}, {"scenario_id": "safety_stock_high", "category": "inventory_policy", "kpi::ending_backlog": 588665.9108, "kpi::fill_rate": 0.888982, "kpi::total_cost": 27931503.7327}, {"scenario_id": "lead_time_plus_20pct", "category": "supplier_risk", "kpi::ending_backlog": 613136.4467, "kpi::fill_rate": 0.884367, "kpi::total_cost": 28479825.9274}, {"scenario_id": "safety_stock_low", "category": "inventory_policy", "kpi::ending_backlog": 616545.7954, "kpi::fill_rate": 0.883724, "kpi::total_cost": 27627808.0051}, {"scenario_id": "lead_time_plus_40pct", "category": "supplier_risk", "kpi::ending_backlog": 638515.3629, "kpi::fill_rate": 0.879581, "kpi::total_cost": 27899097.549}]

## Files
- scenario_results.csv
- scenario_delta_vs_baseline.csv
- experiment_plan_summary.json
- experiment_plan_report.md
- cases/*/simulation_output/first_simulation_summary.json
