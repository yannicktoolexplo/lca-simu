# MRP Lot-Policy Rebuild

- Source graph: `etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy.json`
- Output graph: `etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated.json`
- Scenario id: `scn:BASE`
- Measured horizon: `365` days
- Applied patch: `{'warmup_days': 14, 'reset_backlog_after_warmup': True, 'fg_target_days': 0.0, 'demand_stock_target_days': 14.0}`
- Applied factory lot-execution policy: `{'M-1430': {'item:268967': {'max_lots_per_week': 10, 'source': 'industrial_confirmation_2026-04-13'}}, 'M-1810': {'item:268091': {'max_lots_per_week': 10, 'source': 'industrial_confirmation_2026-04-13'}}}`
- Applied factory lot-sizing overrides: `{'M-1810': {'item:268091': {'lot_multiple_qty': 14400.0, 'source': 'industrial_confirmation_2026-04-13'}}}`
- Applied supplier capacity overrides: `{'SDC-VD0901566A': {'item:338928': {'capacity_qty_per_day': 64.935065, 'basis': 'peer_packaging_alignment'}}}`

## Availability KPI
- item:268091: objective `14.0 j`, avg demand `9844.7/j`, avg coverage `13.4 j`, ending coverage `18.8 j`, days >= objective `38.9%`
- item:268967: objective `14.0 j`, avg demand `4682.6/j`, avg coverage `23.1 j`, ending coverage `18.2 j`, days >= objective `76.2%`

## Factory Plan Adherence
- M-1430: adherence executable plan `36.9%`, lot uplift vs desired `1372.3%`, plan gap `3260540.9`, input-shortage days `36.8%`, weekly-lot-limit days `0.0%`, capacity days `0.0%`
- M-1810: adherence executable plan `100.0%`, lot uplift vs desired `99.0%`, plan gap `0.0`, input-shortage days `0.0%`, weekly-lot-limit days `0.0%`, capacity days `0.0%`
- SDC-1450: adherence executable plan `59.7%`, lot uplift vs desired `48.8%`, plan gap `32400000.0`, input-shortage days `0.0%`, weekly-lot-limit days `0.0%`, capacity days `60.0%`

## Cost KPI
- Inventory cost: `133060601.8985`
- Transport cost: `34544896.6356`
- Total logistics cost: `167605498.5342`
- Total cost: `220714935.3445`
- Simulation summary file: `etudecas\simulation\result\reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated\summaries\first_simulation_summary.json`
- Simulation report file: `etudecas\simulation\result\reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated\reports\first_simulation_report.md`

## Delta Vs Previous Run
- item:268091: days >= objective `+1.1 pts`, ending coverage `-1.7 j`
- item:268967: days >= objective `+0.0 pts`, ending coverage `+0.0 j`
- M-1430: executable-plan adherence `+3.7 pts`, lot uplift vs desired `-32.2 pts`, input-shortage days `+0.8 pts`
- M-1810: executable-plan adherence `+0.0 pts`, lot uplift vs desired `+0.0 pts`, input-shortage days `+0.0 pts`
- SDC-1450: executable-plan adherence `+0.0 pts`, lot uplift vs desired `+0.1 pts`, input-shortage days `+0.0 pts`
- Costs: inventory `-189007.5`, transport `+53227.6`, total `+163960.8`
