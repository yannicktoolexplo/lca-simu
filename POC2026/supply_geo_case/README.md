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
- `outputs/data/brightway_component_impacts.csv`
- `outputs/data/brightway_indicator_summary.csv`
- `outputs/data/brightway_indicator_unit_views.csv`
- `outputs/data/brightway_reference_person_equivalent_results.csv`
- `outputs/data/brightway_reference_weighted_results.csv`
- `outputs/data/brightway_reference_phase_breakdown.csv`
- `outputs/data/brightway_reference_scenarios.csv`
- `outputs/data/brightway_reference_weighting_factors.csv`
- `outputs/data/brightway_reference_climate_contributors.csv`
- `outputs/data/brightway_masterboard_equipment_summary.csv`
- `outputs/data/brightway_masterboard_material_summary.csv`
- `outputs/data/brightway_parameters.csv`
- `outputs/data/brightway_activities.csv`
- `outputs/data/brightway_activity_exchanges.csv`
- `outputs/data/brightway_supply_alignment.csv`
- `outputs/data/brightway_parametric_levers.csv`
- `outputs/data/brightway_parametric_sensitivity.csv`
- `outputs/data/brightway_parametric_switches.csv`
- `outputs/data/brightway_parametric_regional_scenarios.csv`
- `outputs/summaries/sdd_method_comparison.json`
- `outputs/summaries/brightway_model_summary.json`
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

The adapter also consumes the `bw_tristan` aircraft-seat LCA model exports:
`STELIALCASEATS.xlsx` for EF 3.0 component impacts and
`opera_bw2 - inventaire.xlsx` for Brightway parameters, activities and exchanges.
It also reads the legacy result workbook
`STELIA LCA SEATS v14022022v2.xlsx` to recover the official person-equivalent,
weighted, phase-breakdown and scenario values shown in the original ACV deck,
and `STELIA Masterboard LCA SEATS 6.0.xlsx` to summarize BOM mass drivers.
If the Brightway runtime is not installed locally, the package still exports and
plots those model results, while marking runtime recomputation as unavailable.
It also evaluates foreground formulas to show first-order parametric levers
such as aluminium, electricity, transport, packaging and end-of-life changes.
EF 3.0 indicators are exported both in raw units and, where an official EF 3.0
normalisation factor is mapped, in person-equivalent units. The same Brightway
section also exposes sourcing scenarios for current export, French-first,
European-first and fully globalized assumptions; exact LCIA recomputation of
switches still requires the Brightway runtime, while transport changes are shown
as transparent foreground proxies.

`supply_geo_base_results_map.html` is the single HTML map/dashboard entrypoint.
It is an enriched copy of the original `supply_geo` Plotly map: the base filters
remain available, and added view buttons switch the same page between source
data, SDD site results, SDD lane risk, localized operational impacts and an
integrated KPI dashboard.
