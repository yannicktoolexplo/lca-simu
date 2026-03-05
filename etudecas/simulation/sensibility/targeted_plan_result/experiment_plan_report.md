# Targeted Experiment Plan Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 30
- Scenarios total: 15
- Success: 15
- Failed: 0

## Baseline KPIs
{
  "kpi::avg_inventory": 22701.7116,
  "kpi::cost_share_holding": 0.75786,
  "kpi::cost_share_purchase": 0.10459,
  "kpi::cost_share_transport": 0.137549,
  "kpi::ending_backlog": 81.8736,
  "kpi::ending_inventory": 14655.5045,
  "kpi::fill_rate": 0.945418,
  "kpi::total_arrived": 37280.0003,
  "kpi::total_cost": 28723.7188,
  "kpi::total_demand": 1500.0,
  "kpi::total_external_procured_arrived_qty": 49149.966,
  "kpi::total_external_procured_ordered_qty": 53342.633,
  "kpi::total_external_procured_qty": 53342.633,
  "kpi::total_external_procured_rejected_qty": 19998.7226,
  "kpi::total_external_procurement_cost": 3999.8027,
  "kpi::total_holding_cost": 21768.5663,
  "kpi::total_logistics_cost": 25719.4932,
  "kpi::total_opening_stock_bootstrap_qty": 29870.366,
  "kpi::total_produced": 1425.1456,
  "kpi::total_purchase_cost": 3004.2256,
  "kpi::total_served": 1418.1264,
  "kpi::total_shipped": 55453.5434,
  "kpi::total_transport_cost": 3950.9269,
  "kpi::total_unreliable_loss_qty": 0.0
}

## Top scenarios
- Best fill rate: [{"scenario_id": "resilience_combo", "category": "combined_mitigation", "kpi::fill_rate": 0.989053, "kpi::total_cost": 32153.7107, "kpi::ending_backlog": 16.4205}, {"scenario_id": "demand_spike_sync", "category": "demand_risk", "kpi::fill_rate": 0.956701, "kpi::total_cost": 30646.0459, "kpi::ending_backlog": 59.4406}, {"scenario_id": "safety_stock_low", "category": "inventory_policy", "kpi::fill_rate": 0.945418, "kpi::total_cost": 28723.7188, "kpi::ending_backlog": 81.8736}, {"scenario_id": "safety_stock_high", "category": "inventory_policy", "kpi::fill_rate": 0.945418, "kpi::total_cost": 28724.243, "kpi::ending_backlog": 81.8736}, {"scenario_id": "capacity_m1430_minus_15pct", "category": "production_risk", "kpi::fill_rate": 0.925062, "kpi::total_cost": 25423.527, "kpi::ending_backlog": 112.407}]
- Lowest total cost: [{"scenario_id": "capacity_m1430_minus_15pct", "category": "production_risk", "kpi::total_cost": 25423.527, "kpi::fill_rate": 0.925062, "kpi::ending_backlog": 112.407}, {"scenario_id": "review_period_2d", "category": "inventory_policy", "kpi::total_cost": 27719.4332, "kpi::fill_rate": 0.764753, "kpi::ending_backlog": 352.8708}, {"scenario_id": "demand_volatility_high", "category": "demand_risk", "kpi::total_cost": 28253.02, "kpi::fill_rate": 0.906974, "kpi::ending_backlog": 139.9848}, {"scenario_id": "safety_stock_low", "category": "inventory_policy", "kpi::total_cost": 28723.7188, "kpi::fill_rate": 0.945418, "kpi::ending_backlog": 81.8736}, {"scenario_id": "safety_stock_high", "category": "inventory_policy", "kpi::total_cost": 28724.243, "kpi::fill_rate": 0.945418, "kpi::ending_backlog": 81.8736}]
- Lowest ending backlog: [{"scenario_id": "resilience_combo", "category": "combined_mitigation", "kpi::ending_backlog": 16.4205, "kpi::fill_rate": 0.989053, "kpi::total_cost": 32153.7107}, {"scenario_id": "demand_spike_sync", "category": "demand_risk", "kpi::ending_backlog": 59.4406, "kpi::fill_rate": 0.956701, "kpi::total_cost": 30646.0459}, {"scenario_id": "safety_stock_low", "category": "inventory_policy", "kpi::ending_backlog": 81.8736, "kpi::fill_rate": 0.945418, "kpi::total_cost": 28723.7188}, {"scenario_id": "safety_stock_high", "category": "inventory_policy", "kpi::ending_backlog": 81.8736, "kpi::fill_rate": 0.945418, "kpi::total_cost": 28724.243}, {"scenario_id": "capacity_m1430_minus_15pct", "category": "production_risk", "kpi::ending_backlog": 112.407, "kpi::fill_rate": 0.925062, "kpi::total_cost": 25423.527}]

## Files
- scenario_results.csv
- scenario_delta_vs_baseline.csv
- experiment_plan_summary.json
- experiment_plan_report.md
- cases/*/simulation_output/first_simulation_summary.json
