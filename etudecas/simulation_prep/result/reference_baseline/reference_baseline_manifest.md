# Reference Baseline Manifest

## Official baseline retained
- Working baseline kept: `reference_baseline_real_demand_target_calibrated_2026-03-30`
- Reference date: `2026-03-30`
- Decision: keep only the calibrated `2026-03-30` baseline as the official working reference
- Superseded intermediate run: `reference_baseline_real_demand_service_targets` from `2026-03-27`

## Official service targets retained
- `item:268091` target fill rate: `93%`
- `item:268967` target fill rate: `80%`

## Achieved calibrated result
- Global fill rate: `0.888075`
- Ending backlog: `593478.1966`
- Total cost: `27920896.5609`
- Warm-up backlog cleared: `2131254.1763`
- `item:268091` achieved fill rate: `0.9301795700`
- `item:268967` achieved fill rate: `0.7995535887`

## Canonical files
- Prep source graph: `C:\dev\lca-simu\etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_service96_no_prod_stop.json`
- Current graph: `C:\dev\lca-simu\etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_current.json`
- Named calibrated graph: `C:\dev\lca-simu\etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_real_demand_target_calibrated.json`
- Calibrated simulation directory: `C:\dev\lca-simu\etudecas\simulation\result\reference_baseline_real_demand_target_calibrated`
- Calibrated report: `C:\dev\lca-simu\etudecas\simulation\result\reference_baseline_real_demand_target_calibrated\reports\first_simulation_report.md`
- Calibrated rebuild report: `C:\dev\lca-simu\etudecas\simulation\result\reference_baseline_real_demand_target_calibrated\reports\baseline_rebuild_report.md`

## Calibration settings retained
- Factory scale `M-1430`: `52.0`
- Factory scale `M-1810`: `119.0`
- Supplier capacity scale: `320.0`
- Warm-up days: `260`
- Reset backlog after warm-up: `True`
- Transport realism multiplier: `0.2`

## Prep provenance kept
- Prep input graph: `C:\dev\lca-simu\etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_service96_no_prod_stop.json`
- Prep output graph: `C:\dev\lca-simu\etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_current.json`
- Prep generated at (UTC): `2026-03-30T08:00:55.358370+00:00`
- Demand rows loaded from `demand_PF.xlsx`: `2`
- Weekly demand pairs loaded: `2`
- Weeks loaded per pair: `52`

## Remaining prep notes
- Changed nodes: `3`
- Changed demand rows: `2`
- Factory inbound edges still missing `sell_price`: `1`
- `demand_PF.xlsx` rows read / mapped: `104 / 104`
- `Data_poc.xlsx` rows read / mapped: `33 / 33`
