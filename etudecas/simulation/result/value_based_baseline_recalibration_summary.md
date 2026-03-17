# Value-based baseline recalibration summary

## Baseline and retained candidates
- Baseline value-based holding cost: [estimated_replenishment_no_external_value_based_holding](/workspaces/lca-simu/etudecas/simulation/result/estimated_replenishment_no_external_value_based_holding/reports/first_simulation_report.md)
- Candidate around 0.93: [calibrated_value_based_ge093_costmin](/workspaces/lca-simu/etudecas/simulation/result/calibrated_value_based_ge093_costmin/reports/first_simulation_report.md)
- Candidate around 0.95: [calibrated_value_based_ge095_structural](/workspaces/lca-simu/etudecas/simulation/result/calibrated_value_based_ge095_structural/reports/first_simulation_report.md)
- Search results: [calibration_search_value_based_targets_compact](/workspaces/lca-simu/etudecas/simulation/result/calibration_search_value_based_targets_compact/results.json)

## KPI comparison
- Baseline value-based: fill 0.325507, backlog 11736.1761, total cost 2426748.6942, avg inventory 1011556.8546
- Candidate ~0.93: fill 0.930321, backlog 1212.4136, total cost 18195087.7333, avg inventory 7786221.3135
- Candidate ~0.95: fill 0.951540, backlog 843.2095, total cost 19256325.8659, avg inventory 8253511.0415

## Settings
- Candidate ~0.93: opening_stock_bootstrap_scale = 5.0, capacity_scale = 2.5, lead_time_scale = 0.6, supplier_capacity_scale = 1.0
- Candidate ~0.95: opening_stock_bootstrap_scale = 2.0, capacity_scale = 4.0, lead_time_scale = 1.0, supplier_capacity_scale = 1.0

## Recommendation
- If the goal is a strict pharma-style service baseline, the 0.95 candidate is easier to explain because lead times stay unchanged.
- If the goal is the cheapest way to clear the 0.93 floor, the 0.93 candidate wins, but it depends on very aggressive startup stock and shorter leads.
- Supplier capacity scale remained secondary in the tested range.
