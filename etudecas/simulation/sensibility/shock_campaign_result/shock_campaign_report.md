# Shock Campaign Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 30
- Scenarios total: 59
- Success: 59
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
- Best fill rate: [{"scenario_id": "combo_resilience_max", "category": "combined_mitigation", "kpi::fill_rate": 0.855975, "kpi::total_cost": 1554066.749, "kpi::ending_backlog": 214.2375}, {"scenario_id": "capacity_scale_up", "category": "single_factor_global", "kpi::fill_rate": 0.837269, "kpi::total_cost": 1527464.5189, "kpi::ending_backlog": 242.0625}, {"scenario_id": "demand_item_268967_down", "category": "single_factor_item_demand", "kpi::fill_rate": 0.833996, "kpi::total_cost": 1275618.4331, "kpi::ending_backlog": 209.8916}, {"scenario_id": "demand_sync_spike_150", "category": "profile_shock", "kpi::fill_rate": 0.817164, "kpi::total_cost": 1274052.0241, "kpi::ending_backlog": 245.0001}, {"scenario_id": "capacity_M-1430_up20", "category": "single_factor_node_capacity", "kpi::fill_rate": 0.7981, "kpi::total_cost": 1290226.1238, "kpi::ending_backlog": 300.3259}, {"scenario_id": "transport_cost_scale_down", "category": "single_factor_global", "kpi::fill_rate": 0.787666, "kpi::total_cost": 1268912.3235, "kpi::ending_backlog": 315.8476}, {"scenario_id": "transport_cost_scale_up", "category": "single_factor_global", "kpi::fill_rate": 0.787666, "kpi::total_cost": 1280032.3065, "kpi::ending_backlog": 315.8476}, {"scenario_id": "transport_cost_scale_up_severe", "category": "single_factor_global", "kpi::fill_rate": 0.787666, "kpi::total_cost": 1286704.2963, "kpi::ending_backlog": 315.8476}]
- Lowest total cost: [{"scenario_id": "capacity_scale_down_severe", "category": "single_factor_global", "kpi::total_cost": 893962.4018, "kpi::fill_rate": 0.576471, "kpi::ending_backlog": 630.0}, {"scenario_id": "capacity_SDC-1450_down30", "category": "single_factor_node_capacity", "kpi::total_cost": 919336.3167, "kpi::fill_rate": 0.787666, "kpi::ending_backlog": 315.8476}, {"scenario_id": "capacity_scale_down", "category": "single_factor_global", "kpi::total_cost": 1019864.319, "kpi::fill_rate": 0.644082, "kpi::ending_backlog": 529.4279}, {"scenario_id": "lead_time_scale_down", "category": "single_factor_global", "kpi::total_cost": 1025173.4841, "kpi::fill_rate": 0.727965, "kpi::ending_backlog": 404.6517}, {"scenario_id": "capacity_SDC-1450_down20", "category": "single_factor_node_capacity", "kpi::total_cost": 1037344.3167, "kpi::fill_rate": 0.787666, "kpi::ending_backlog": 315.8476}, {"scenario_id": "combo_extreme_black_swan", "category": "combined_stress", "kpi::total_cost": 1040011.8817, "kpi::fill_rate": 0.081299, "kpi::ending_backlog": 3086.8359}, {"scenario_id": "capacity_SDC-1450_down10", "category": "single_factor_node_capacity", "kpi::total_cost": 1155352.3167, "kpi::fill_rate": 0.787666, "kpi::ending_backlog": 315.8476}, {"scenario_id": "combo_dual_plant_outage", "category": "combined_stress", "kpi::total_cost": 1243231.4224, "kpi::fill_rate": 0.546218, "kpi::ending_backlog": 675.0}]
- Lowest ending backlog: [{"scenario_id": "demand_item_268967_down", "category": "single_factor_item_demand", "kpi::ending_backlog": 209.8916, "kpi::fill_rate": 0.833996, "kpi::total_cost": 1275618.4331}, {"scenario_id": "combo_resilience_max", "category": "combined_mitigation", "kpi::ending_backlog": 214.2375, "kpi::fill_rate": 0.855975, "kpi::total_cost": 1554066.749}, {"scenario_id": "demand_drop_recovery_30", "category": "profile_shock", "kpi::ending_backlog": 220.0, "kpi::fill_rate": 0.74537, "kpi::total_cost": 1278201.5733}, {"scenario_id": "capacity_scale_up", "category": "single_factor_global", "kpi::ending_backlog": 242.0625, "kpi::fill_rate": 0.837269, "kpi::total_cost": 1527464.5189}, {"scenario_id": "demand_sync_spike_150", "category": "profile_shock", "kpi::ending_backlog": 245.0001, "kpi::fill_rate": 0.817164, "kpi::total_cost": 1274052.0241}, {"scenario_id": "demand_drop_recovery_50", "category": "profile_shock", "kpi::ending_backlog": 260.0, "kpi::fill_rate": 0.74, "kpi::total_cost": 1276811.1619}, {"scenario_id": "demand_scale_down", "category": "single_factor_global", "kpi::ending_backlog": 260.7499, "kpi::fill_rate": 0.780882, "kpi::total_cost": 1274697.6622}, {"scenario_id": "demand_item_268091_down", "category": "single_factor_item_demand", "kpi::ending_backlog": 272.9916, "kpi::fill_rate": 0.78409, "kpi::total_cost": 1273265.3025}]
- Worst fill rate: [{"scenario_id": "combo_extreme_black_swan", "category": "combined_stress", "kpi::fill_rate": 0.081299, "kpi::total_cost": 1040011.8817, "kpi::ending_backlog": 3086.8359}, {"scenario_id": "combo_systemic_stress", "category": "combined_stress", "kpi::fill_rate": 0.187129, "kpi::total_cost": 1376284.0397, "kpi::ending_backlog": 2219.984}, {"scenario_id": "combo_supplier_crunch", "category": "combined_stress", "kpi::fill_rate": 0.288266, "kpi::total_cost": 1399696.338, "kpi::ending_backlog": 1058.704}, {"scenario_id": "review_period_scale_7d", "category": "single_factor_global", "kpi::fill_rate": 0.315402, "kpi::total_cost": 1308172.0514, "kpi::ending_backlog": 1018.34}, {"scenario_id": "combo_logistics_strike", "category": "combined_stress", "kpi::fill_rate": 0.315402, "kpi::total_cost": 1430864.8547, "kpi::ending_backlog": 1018.34}, {"scenario_id": "supplier_reliability_scale_75pct", "category": "single_factor_global", "kpi::fill_rate": 0.425615, "kpi::total_cost": 1269972.6832, "kpi::ending_backlog": 854.3983}, {"scenario_id": "combo_demand_boom", "category": "combined_stress", "kpi::fill_rate": 0.479704, "kpi::total_cost": 1273328.8784, "kpi::ending_backlog": 1245.5888}, {"scenario_id": "review_period_scale_4d", "category": "single_factor_global", "kpi::fill_rate": 0.498067, "kpi::total_cost": 1286476.7409, "kpi::ending_backlog": 746.6253}]
- Highest ending backlog: [{"scenario_id": "combo_extreme_black_swan", "category": "combined_stress", "kpi::ending_backlog": 3086.8359, "kpi::fill_rate": 0.081299, "kpi::total_cost": 1040011.8817}, {"scenario_id": "combo_systemic_stress", "category": "combined_stress", "kpi::ending_backlog": 2219.984, "kpi::fill_rate": 0.187129, "kpi::total_cost": 1376284.0397}, {"scenario_id": "combo_demand_boom", "category": "combined_stress", "kpi::ending_backlog": 1245.5888, "kpi::fill_rate": 0.479704, "kpi::total_cost": 1273328.8784}, {"scenario_id": "combo_supplier_crunch", "category": "combined_stress", "kpi::ending_backlog": 1058.704, "kpi::fill_rate": 0.288266, "kpi::total_cost": 1399696.338}, {"scenario_id": "review_period_scale_7d", "category": "single_factor_global", "kpi::ending_backlog": 1018.34, "kpi::fill_rate": 0.315402, "kpi::total_cost": 1308172.0514}, {"scenario_id": "combo_logistics_strike", "category": "combined_stress", "kpi::ending_backlog": 1018.34, "kpi::fill_rate": 0.315402, "kpi::total_cost": 1430864.8547}, {"scenario_id": "demand_scale_up_severe", "category": "single_factor_global", "kpi::ending_backlog": 934.0888, "kpi::fill_rate": 0.551458, "kpi::total_cost": 1273328.8784}, {"scenario_id": "supplier_reliability_scale_75pct", "category": "single_factor_global", "kpi::ending_backlog": 854.3983, "kpi::fill_rate": 0.425615, "kpi::total_cost": 1269972.6832}]

## Files
- scenario_results.csv
- scenario_delta_vs_baseline.csv
- shock_campaign_summary.json
- shock_campaign_report.md
- cases/*/simulation_output/first_simulation_summary.json
