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
  "kpi::avg_inventory": 1045717.0788,
  "kpi::cost_share_holding": 0.980377,
  "kpi::cost_share_purchase": 0.002157,
  "kpi::cost_share_transport": 0.017466,
  "kpi::ending_backlog": 315.8476,
  "kpi::ending_inventory": 1035949.2243,
  "kpi::fill_rate": 0.787666,
  "kpi::total_arrived": 15989.339,
  "kpi::total_cost": 1273360.3167,
  "kpi::total_demand": 1487.5,
  "kpi::total_external_procured_arrived_qty": 42489.9504,
  "kpi::total_external_procured_ordered_qty": 42871.1216,
  "kpi::total_external_procured_qty": 42871.1216,
  "kpi::total_external_procured_rejected_qty": 18148.2001,
  "kpi::total_external_procurement_cost": 3318.2119,
  "kpi::total_holding_cost": 1248373.7888,
  "kpi::total_logistics_cost": 1270613.7549,
  "kpi::total_opening_stock_bootstrap_qty": 1060029.4897,
  "kpi::total_produced": 2610.2267,
  "kpi::total_purchase_cost": 2746.5618,
  "kpi::total_served": 1171.6524,
  "kpi::total_shipped": 45988.6462,
  "kpi::total_transport_cost": 22239.9661,
  "kpi::total_unreliable_loss_qty": 0.0
}

## Top scenarios
- Best fill rate: [{"scenario_id": "demand_spike_sync", "category": "demand_risk", "kpi::fill_rate": 0.819387, "kpi::total_cost": 1274878.9709, "kpi::ending_backlog": 225.4048}, {"scenario_id": "demand_volatility_high", "category": "demand_risk", "kpi::fill_rate": 0.803084, "kpi::total_cost": 1274460.3036, "kpi::ending_backlog": 269.3812}, {"scenario_id": "safety_stock_high", "category": "inventory_policy", "kpi::fill_rate": 0.787666, "kpi::total_cost": 1273360.8408, "kpi::ending_backlog": 315.8476}, {"scenario_id": "safety_stock_low", "category": "inventory_policy", "kpi::fill_rate": 0.786659, "kpi::total_cost": 1273358.1203, "kpi::ending_backlog": 317.3447}, {"scenario_id": "resilience_combo", "category": "combined_mitigation", "kpi::fill_rate": 0.774706, "kpi::total_cost": 1283564.3304, "kpi::ending_backlog": 335.1249}]
- Lowest total cost: [{"scenario_id": "capacity_m1430_minus_15pct", "category": "production_risk", "kpi::total_cost": 1262487.521, "kpi::fill_rate": 0.734112, "kpi::ending_backlog": 395.5085}, {"scenario_id": "supplier_reliability_85", "category": "supplier_risk", "kpi::total_cost": 1271601.4712, "kpi::fill_rate": 0.571694, "kpi::ending_backlog": 637.1045}, {"scenario_id": "supplier_reliability_95", "category": "supplier_risk", "kpi::total_cost": 1273032.905, "kpi::fill_rate": 0.673928, "kpi::ending_backlog": 485.0314}, {"scenario_id": "safety_stock_low", "category": "inventory_policy", "kpi::total_cost": 1273358.1203, "kpi::fill_rate": 0.786659, "kpi::ending_backlog": 317.3447}, {"scenario_id": "safety_stock_high", "category": "inventory_policy", "kpi::total_cost": 1273360.8408, "kpi::fill_rate": 0.787666, "kpi::ending_backlog": 315.8476}]
- Lowest ending backlog: [{"scenario_id": "demand_spike_sync", "category": "demand_risk", "kpi::ending_backlog": 225.4048, "kpi::fill_rate": 0.819387, "kpi::total_cost": 1274878.9709}, {"scenario_id": "demand_volatility_high", "category": "demand_risk", "kpi::ending_backlog": 269.3812, "kpi::fill_rate": 0.803084, "kpi::total_cost": 1274460.3036}, {"scenario_id": "safety_stock_high", "category": "inventory_policy", "kpi::ending_backlog": 315.8476, "kpi::fill_rate": 0.787666, "kpi::total_cost": 1273360.8408}, {"scenario_id": "safety_stock_low", "category": "inventory_policy", "kpi::ending_backlog": 317.3447, "kpi::fill_rate": 0.786659, "kpi::total_cost": 1273358.1203}, {"scenario_id": "resilience_combo", "category": "combined_mitigation", "kpi::ending_backlog": 335.1249, "kpi::fill_rate": 0.774706, "kpi::total_cost": 1283564.3304}]

## Files
- scenario_results.csv
- scenario_delta_vs_baseline.csv
- experiment_plan_summary.json
- experiment_plan_report.md
- cases/*/simulation_output/first_simulation_summary.json
