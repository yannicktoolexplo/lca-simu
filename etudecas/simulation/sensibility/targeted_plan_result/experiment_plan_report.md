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
  "kpi::avg_inventory": 8081.6759,
  "kpi::ending_backlog": 400.0,
  "kpi::ending_inventory": 4937.9023,
  "kpi::fill_rate": 0.733333,
  "kpi::total_arrived": 45776.5532,
  "kpi::total_cost": 7392.806,
  "kpi::total_demand": 1500.0,
  "kpi::total_external_procured_qty": 54542.0385,
  "kpi::total_holding_cost": 6526.9631,
  "kpi::total_logistics_cost": 6648.7631,
  "kpi::total_opening_stock_bootstrap_qty": 14935.183,
  "kpi::total_produced": 1500.0,
  "kpi::total_purchase_cost": 744.0429,
  "kpi::total_served": 1100.0,
  "kpi::total_shipped": 61192.9362,
  "kpi::total_transport_cost": 121.8,
  "kpi::total_unreliable_loss_qty": 0.0
}

## Top scenarios
- Best fill rate: [{"scenario_id": "resilience_combo", "category": "combined_mitigation", "kpi::fill_rate": 0.806667, "kpi::total_cost": 8627.8196, "kpi::ending_backlog": 290.0}, {"scenario_id": "safety_stock_low", "category": "inventory_policy", "kpi::fill_rate": 0.733333, "kpi::total_cost": 7392.806, "kpi::ending_backlog": 400.0}, {"scenario_id": "safety_stock_high", "category": "inventory_policy", "kpi::fill_rate": 0.733333, "kpi::total_cost": 7392.806, "kpi::ending_backlog": 400.0}, {"scenario_id": "demand_spike_sync", "category": "demand_risk", "kpi::fill_rate": 0.705128, "kpi::total_cost": 7392.806, "kpi::ending_backlog": 460.0}, {"scenario_id": "capacity_m1430_minus_15pct", "category": "production_risk", "kpi::fill_rate": 0.678333, "kpi::total_cost": 7097.4417, "kpi::ending_backlog": 482.5}]
- Lowest total cost: [{"scenario_id": "capacity_m1430_minus_15pct", "category": "production_risk", "kpi::total_cost": 7097.4417, "kpi::fill_rate": 0.678333, "kpi::ending_backlog": 482.5}, {"scenario_id": "capacity_m1810_minus_15pct", "category": "production_risk", "kpi::total_cost": 7324.5758, "kpi::fill_rate": 0.678333, "kpi::ending_backlog": 482.5}, {"scenario_id": "supplier_reliability_85", "category": "supplier_risk", "kpi::total_cost": 7344.1247, "kpi::fill_rate": 0.523458, "kpi::ending_backlog": 714.8123}, {"scenario_id": "supplier_reliability_95", "category": "supplier_risk", "kpi::total_cost": 7377.6258, "kpi::fill_rate": 0.659458, "kpi::ending_backlog": 510.8125}, {"scenario_id": "safety_stock_low", "category": "inventory_policy", "kpi::total_cost": 7392.806, "kpi::fill_rate": 0.733333, "kpi::ending_backlog": 400.0}]
- Lowest ending backlog: [{"scenario_id": "resilience_combo", "category": "combined_mitigation", "kpi::ending_backlog": 290.0, "kpi::fill_rate": 0.806667, "kpi::total_cost": 8627.8196}, {"scenario_id": "safety_stock_low", "category": "inventory_policy", "kpi::ending_backlog": 400.0, "kpi::fill_rate": 0.733333, "kpi::total_cost": 7392.806}, {"scenario_id": "safety_stock_high", "category": "inventory_policy", "kpi::ending_backlog": 400.0, "kpi::fill_rate": 0.733333, "kpi::total_cost": 7392.806}, {"scenario_id": "demand_spike_sync", "category": "demand_risk", "kpi::ending_backlog": 460.0, "kpi::fill_rate": 0.705128, "kpi::total_cost": 7392.806}, {"scenario_id": "capacity_m1430_minus_15pct", "category": "production_risk", "kpi::ending_backlog": 482.5, "kpi::fill_rate": 0.678333, "kpi::total_cost": 7097.4417}]

## Files
- scenario_results.csv
- scenario_delta_vs_baseline.csv
- experiment_plan_summary.json
- experiment_plan_report.md
- cases/*/simulation_output/first_simulation_summary.json
