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
- `outputs/data/supplier_context_summary.csv` (optional web-context cache)
- `outputs/data/supplier_context_results.csv` (optional web-search result cache)
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
- `outputs/data/sdd_brightway_inventory_delta.csv`
- `outputs/data/sdd_brightway_exchange_delta.csv`
- `outputs/data/sdd_brightway_exchange_category_totals.csv`
- `outputs/data/sdd_brightway_top_exchanges.csv`
- `outputs/data/sdd_brightway_exchange_lcia.csv`
- `outputs/data/sdd_brightway_exchange_lcia_factors.csv`
- `outputs/data/sdd_brightway_exchange_lcia_category_totals.csv`
- `outputs/data/sdd_brightway_exchange_lcia_monthly.csv`
- `outputs/data/sdd_brightway_exchange_lcia_top.csv`
- `outputs/data/sdd_brightway_monthly.csv`
- `outputs/data/sdd_brightway_cumulative.csv`
- `outputs/data/sdd_brightway_mechanism_totals.csv`
- `outputs/data/sdd_brightway_top_sites.csv`
- `outputs/data/sdd_brightway_top_components.csv`
- `outputs/data/brightway_component_impacts.csv`
- `outputs/data/brightway_indicator_summary.csv`
- `outputs/data/brightway_indicator_unit_views.csv`
- `outputs/data/brightway_reference_person_equivalent_results.csv`
- `outputs/data/brightway_reference_weighted_results.csv`
- `outputs/data/brightway_reference_phase_breakdown.csv`
- `outputs/data/brightway_reference_use_phase_components.csv`
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
- `outputs/data/brightway_exact_scenario_lcia.csv`
- `outputs/data/brightway_excel_runtime_comparison.csv`
- `outputs/data/brightway_usage_calibration.csv`
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

Optional supplier context enrichment:

```bash
python POC2026/supply_geo_case/tools/enrich_supplier_context.py --limit 30 --exclude-oem
python POC2026/supply_geo_case/adapter.py
```

The enrichment step is intentionally separate from the SDD simulation. It uses
DuckDuckGo HTML search by default, or Bright Data DuckDuckGo SERP when
`--provider brightdata`, `BRIGHTDATA_API_TOKEN` and `BRIGHTDATA_SERP_ZONE` are
provided. The map reads the generated cache and exposes supplier context,
weak-signal families and documentary criticality in hover tooltips, site click
details, the `Contexte fournisseurs` map view and KPI dashboard plots.

Brightway runtime:

```bash
python -m venv .venv-brightway
.\.venv-brightway\Scripts\python.exe -m pip install brightway25 bw2data bw2io bw2calc bw2analyzer lca-algebraic-bw25 ecoinvent_interface pyyaml python-dotenv
$env:ECOINVENT_USERNAME="..."
$env:ECOINVENT_PASSWORD="..."
.\.venv-brightway\Scripts\python.exe POC2026\supply_geo_case\tools\import_ecoinvent_bw25.py
.\.venv-brightway\Scripts\python.exe POC2026\supply_geo_case\tools\import_opera_package_bw25.py
.\.venv-brightway\Scripts\python.exe POC2026\supply_geo_case\tools\import_ecoinvent_bw25.py --with-lcia
```

The adapter detects `.venv-brightway` automatically, or a custom interpreter
through `BRIGHTWAY_PYTHON`. A runtime is considered executable only when
`biosphere3`, `ecoinvent-3.10-cutoff`, `OPERA_siege` and LCIA methods are
available in the `bw25-ecoinvent310` Brightway project.

The adapter keeps only active primary paths, splits mass across multiple primary
path alternatives when they exist, and creates deterministic weather-driven
event seeds per supplier site. These event seeds are not calibrated weather
observations; they are scenario inputs for state-dependent dynamics.

The weather driver assigns each site to a coarse world region and weather
profile, then derives heatwave, drought, storm, hurricane/cyclone and cold
stress. Maritime lanes using `ship` also receive monthly route-risk estimates
for ocean storms, hurricane/typhoon exposure, monsoon and cold shipping stress.
The weather scenario is non-stationary over the 240-month horizon: it applies a
configurable climate-change signal from month 1 to the end of the run. The
default trajectory reaches +2.2 °C at horizon end and progressively increases
heatwave, drought, extreme rainfall, storm wind, hurricane/cyclone and maritime
risk factors. These drivers are exported in the data as
`climate_progress`, `warming_delta_c`, `hazard_intensification_factor` and
maritime-specific intensification factors, so long runs naturally generate more
climate stress in later years.

The SDD engine simulates monthly path states with stock drawdown, backlog,
upstream service propagation, transport degradation, adaptation decisions and
recalculated monthly/cumulative impacts. It is a deterministic scenario engine,
not an optimized policy solver.

The SDD-to-Brightway coupling anchors static production on the exact Brightway
`production du siege` climate score, scales path-level supply alignment to that
anchor, then creates dynamic inventory deltas for alternative sourcing,
quality losses/rework, extra capacity energy, accelerated transport, degraded
operations energy and corrective maintenance. The exported inventory delta
ledger is aggregated by month, site, role and SDD mechanism; it keeps join
samples back to `sdd_event_ledger.csv` and source weather/transport counts,
while top component and top site tables are computed from the detailed internal
ledger before aggregation.

Rebut et reprise are modelled with an explicit net-recycling convention.
Operation-driven rejects first create replacement production on the role-local
component scope, then add family-level sorting/treatment, then subtract an
avoided-burden recycling credit. The current profiles are conservative
family-level estimates; they keep replacement, treatment and recycling credit
as separate ledger mechanisms (`scrap_rework`, `scrap_treatment`,
`recycling_credit`) so cut-off, no-credit or component-specific recycling
variants can be compared later. Alternative sourcing is kept as a calibrated
supplier cost/impact overhead and is not expanded onto raw material exchanges,
because that previously double counted component production. Exact Brightway
exchange LCIA therefore reports real exchange factors where a direct exchange
exists and marks those calibrated SDD estimates as
`calibrated_sdd_proxy_not_exact`.

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
switches requires the Brightway runtime. When available, exact EF 3.0 climate
LCIA is recalculated for `france_first`, `europe_first` and `fully_globalized`
on `production du siege`. The raw imported `siege cycle de vie` row is still
exported and flagged because the OPERA use-phase tkm amount is not aligned with
the Excel reference. A corrected `lifecycle_excel_aligned` row is also exported:
it removes the raw tkm use branch and adds the STELIA Excel use phase split into
passive kerosene, cargo-plane estimate and cleaning/maintenance. The cargo-plane
line is treated as an Excel-calibrated aircraft-use estimate until its physical
unit is confirmed in the legacy model.
Transport changes are applied as scenario amount factors, not as a route-by-route
Brightway rerouting.

`supply_geo_base_results_map.html` is the single HTML map/dashboard entrypoint.
It is an enriched copy of the original `supply_geo` Plotly map: the base filters
remain available, and added view buttons switch the same page between source
data, SDD site results, SDD lane risk, localized operational impacts and an
integrated KPI dashboard.
