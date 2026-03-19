# Recalibration summary

## Variants tested and retained
- Baseline no external generic fallback: [estimated_replenishment_no_external_v2_fresh](/workspaces/lca-simu/etudecas/simulation/result/estimated_replenishment_no_external_v2_fresh/reports/first_simulation_report.md)
- Working calibration >= 0.50: [calibrated_ge050](/workspaces/lca-simu/etudecas/simulation/result/calibrated_ge050/reports/first_simulation_report.md)
- Structural calibration >= 0.90: [calibrated_ge090_structural](/workspaces/lca-simu/etudecas/simulation/result/calibrated_ge090_structural/reports/first_simulation_report.md)
- Best service found in aggressive search: [extreme search results](/workspaces/lca-simu/etudecas/simulation/result/calibration_search_estimated_replenishment_extreme/results.json)

## KPI comparison
- Baseline no external: fill 0.286427, backlog 12416.1638, total cost 14585943.6404, avg inventory 1011223.0315
- Calibrated >= 0.50: fill 0.515575, backlog 8428.9983, total cost 35285374.6215, avg inventory 2443196.13
- Calibrated >= 0.90 structural: fill 0.906406, backlog 1628.5440, total cost 134622281.5255, avg inventory 9316282.1264
- Best service aggressive search: fill 0.914061, backlog 1495.3389, total cost 121069350.8572, avg inventory 8394851.2910

## Retained settings
- >= 0.50 working calibration: opening_stock_bootstrap_scale = 1.5, process capacity scale = 2.0, lead time scale = 0.8, external procurement disabled, source mode = estimated_replenishment
- >= 0.90 structural calibration: opening_stock_bootstrap_scale = 3.0, process capacity scale = 3.0, lead times unchanged, external procurement disabled, source mode = estimated_replenishment
- Best service aggressive search: opening_stock_bootstrap_scale = 5.0, process capacity scale = 4.0, lead time scale = 0.4

## Interpretation
- The 0.50 threshold is reachable with a moderate but still material reinforcement of startup stock and internal capacities.
- The 0.90 threshold is also reachable, but only with very strong assumptions on capacity and/or lead times, which likely exceed a realistic first-pass calibration.
- Supplier capacity scaling was not the primary bottleneck in the tested ranges; startup stock and downstream transformation capacity dominate the response.
