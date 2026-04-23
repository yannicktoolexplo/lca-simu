# MRP Lot-Policy Rebuild

- Source graph: `etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy.json`
- Output graph: `etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated.json`
- Scenario id: `scn:BASE`
- Measured horizon: `365` days
- Applied patch: `{'warmup_days': 0, 'reset_backlog_after_warmup': False, 'fg_target_days': 0.0, 'demand_stock_target_days': 14.0, 'initialization_policy': {'mode': 'explicit_state', 'state_scale': 0.02, 'factory_input_on_hand_days': 0.0, 'supplier_output_on_hand_days': 1.0, 'distribution_center_on_hand_days': 3.0, 'customer_on_hand_days': 0.0, 'seed_in_transit': True, 'in_transit_fill_ratio': 1.0, 'seed_estimated_source_pipeline': True}, 'estimated_source_requirement_cap_by_item': {'item:042342': 12.0, 'item:333362': 8.0, 'item:344135': 8.0, 'item:338928': 10.0, 'item:338929': 10.0}}`
- Applied factory lot-execution policy: `{'M-1430': {'item:268967': {'max_lots_per_week': 10, 'source': 'industrial_confirmation_2026-04-13'}}, 'M-1810': {'item:268091': {'max_lots_per_week': 10, 'source': 'industrial_confirmation_2026-04-13'}}}`
- Applied factory lot-sizing overrides: `{'M-1810': {'item:268091': {'lot_multiple_qty': 14400.0, 'source': 'industrial_confirmation_2026-04-13'}}}`
- Applied supplier capacity overrides: `{'SDC-VD0901566A': {'item:338928': {'capacity_qty_per_day': 64.935065, 'basis': 'peer_packaging_alignment'}}}`

## Availability KPI
- item:268091: objective `14.0 j`, avg demand `9798.5/j`, avg coverage `13.4 j`, ending coverage `20.7 j`, days >= objective `38.1%`
- item:268967: objective `14.0 j`, avg demand `4317.8/j`, avg coverage `23.4 j`, ending coverage `19.8 j`, days >= objective `72.3%`

## Factory Plan Adherence
- M-1430: adherence executable plan `100.0%`, lot uplift vs desired `1747.7%`, plan gap `0.0`, input-shortage days `0.0%`, weekly-lot-limit days `0.0%`, capacity days `0.0%`
- M-1810: adherence executable plan `100.0%`, lot uplift vs desired `104.8%`, plan gap `0.0`, input-shortage days `0.0%`, weekly-lot-limit days `0.0%`, capacity days `0.0%`
- SDC-1450: adherence executable plan `21.3%`, lot uplift vs desired `35.8%`, plan gap `153900000.0`, input-shortage days `0.0%`, weekly-lot-limit days `0.0%`, capacity days `87.6%`

## Cost KPI
- Inventory cost: `93639467.7406`
- Transport cost: `14593049.2163`
- Total logistics cost: `108232516.957`
- Total cost: `114148325.6405`
- Simulation summary file: `etudecas\simulation\result\reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated\summaries\first_simulation_summary.json`
- Simulation report file: `etudecas\simulation\result\reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated\reports\first_simulation_report.md`

## Delta Vs Previous Run
- item:268091: days >= objective `-0.6 pts`, ending coverage `-1.7 j`
- item:268967: days >= objective `-0.5 pts`, ending coverage `+0.0 j`
- M-1430: executable-plan adherence `+0.0 pts`, lot uplift vs desired `+0.0 pts`, input-shortage days `+0.0 pts`
- M-1810: executable-plan adherence `+0.0 pts`, lot uplift vs desired `+0.0 pts`, input-shortage days `+0.0 pts`
- SDC-1450: executable-plan adherence `+0.0 pts`, lot uplift vs desired `+0.0 pts`, input-shortage days `+0.0 pts`
- Costs: inventory `-26540235.4`, transport `+23433.8`, total `-26505084.7`
