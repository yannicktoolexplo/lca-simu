# POC2026 supply_geo case

This folder adapts the latest `supply_geo` extended supply case into a
simulation-ready POC2026 package.

Source data:

- `supply_geo/analysis/output8_GEO_normalized_simulation_ready_researched.json`
- `supply_geo/analysis/maps/output8_GEO_simulation_ready_researched_map.html`

Generated package:

- `outputs/data/primary_supply_paths.csv`
- `outputs/data/primary_supply_nodes.csv`
- `outputs/data/primary_supply_lanes.csv`
- `outputs/data/primary_supply_sites.csv`
- `outputs/data/site_weather_driver.csv`
- `outputs/data/supplier_risk_event_seed.csv`
- `outputs/data/transport_weather_risk.csv`
- `outputs/data/node_operational_state.csv`
- `outputs/data/operational_event_seed.csv`
- `outputs/data/sdd_node_state.csv`
- `outputs/data/sdd_lane_state.csv`
- `outputs/data/sdd_flow_state.csv`
- `outputs/data/sdd_event_ledger.csv`
- `outputs/data/sdd_monthly_impacts.csv`
- `outputs/data/sdd_cumulative_impacts.csv`
- `outputs/summaries/sdd_method_comparison.json`
- `outputs/summaries/primary_supply_case_summary.json`
- `outputs/summaries/general_kpis.json`
- `outputs/maps/supply_geo_base_results_map.html`
- `outputs/run/run_manifest.json`

Run:

```bash
python POC2026/supply_geo_case/adapter.py
```

The adapter keeps only active primary paths, splits mass across multiple primary
path alternatives when they exist, and creates deterministic weather-driven
event seeds per supplier site. These event seeds are not calibrated weather
observations; they are scenario inputs for state-dependent dynamics.

The weather driver assigns each site to a coarse world region and weather
profile, then derives heatwave, drought, storm, hurricane/cyclone and cold
stress. Maritime lanes using `ship` also receive monthly route-risk proxies
for ocean storms, hurricane/typhoon exposure, monsoon and cold shipping stress.

The SDD engine simulates monthly path states with stock drawdown, backlog,
upstream service propagation, transport degradation, adaptation decisions and
recalculated monthly/cumulative impacts. It is a deterministic scenario engine,
not an optimized policy solver.

`supply_geo_base_results_map.html` is the single HTML map/dashboard entrypoint.
It is an enriched copy of the original `supply_geo` Plotly map: the base filters
remain available, and added view buttons switch the same page between source
data, SDD site results, SDD lane risk, localized operational impacts and an
integrated KPI dashboard.
