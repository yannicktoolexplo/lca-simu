# POC2026 model formalization

This note fixes the modelling contract used by the POC2026 state-dependent
dynamic LCA scripts. It is intentionally compact: the goal is to make the
model reviewable, testable and separable from plotting/storytelling code.

## 1. Scope

POC2026 contains two related models:

- `final_sddlca_poc_script.py`: short-horizon weekly SDD-LCA demonstrator.
- `horizon-adaptation/horizon_adaptation_poc.py`: 20-year monthly adaptation
  demonstrator with climate, energy and resource-stress mechanisms.

Both models are discrete-time stock-flow simulations. They are state-dependent
dynamic LCA models because the life-cycle inventory and characterization factors
depend on the simulated state and operating regime. They are not yet a full
System Dynamics model in the Vensim/Stella sense: exogenous climate and demand
paths are generated deterministically and many response functions are stylized.

## 2. Generic state-transition contract

At each period `t`, the simulator updates:

```text
x_{t+1} = f(x_t, u_t, e_t, theta)
z_t     = g(x_t, u_t, e_t, theta)
i_t     = h(x_t, z_t, e_t, theta)
c_t     = k(x_t, z_t, e_t, theta)
```

Where:

- `x_t`: endogenous state at period start.
- `u_t`: policy/control rules active in the scenario.
- `e_t`: exogenous context for the period.
- `theta`: parameter set loaded from `config/*.yml`.
- `z_t`: operational transition outputs.
- `i_t`: LCA inventory and impacts by method.
- `c_t`: economic costs.

## 3. Short-horizon state vector

The short model state is:

```text
x_t = {
  main_pipeline_t[eta],
  backup_pipeline_t[eta],
  raw_inventory_t[source, batch],
  finished_goods_inventory_t[source, batch],
  backlog_t
}
```

State semantics:

- Pipeline buckets are quantities in transit by time-to-arrival.
- Raw and finished-goods inventories are FIFO layers with source provenance.
- Backlog is unserved demand carried into the next period.

The transition order is:

1. Receive inbound pipeline buckets.
2. Place endogenous orders using current stock position and policy thresholds.
3. Produce using available raw stock, capacity and service pressure.
4. Apply utilization-dependent scrap.
5. Ship finished goods and update backlog.
6. Select outbound mode from backlog thresholds.
7. Build next-period operational feedback from utilization, scrap, air freight
   and backlog.

## 4. Short-horizon state-dependent LCA

The three methods deliberately use the same operational trajectory but different
impact logic:

```text
Classical LCA:
  stationary average factors, main material, nominal energy, truck outbound,
  no explicit scrap burden.

Time-Dependent DLCA:
  period-specific factors for main material, inbound transport, grid and truck,
  but no regime-dependent source, mode or scrap burden.

State-Dependent Dynamic LCA:
  period-specific factors plus operational-regime factors:
  - source-specific material and inbound transport,
  - utilization-dependent kWh per good unit,
  - explicit scrap burden,
  - air or truck outbound mode from backlog state,
  - storage burden from simulated stocks.
```

The SDD impact for period `t` is:

```text
SDD_t =
  material(source_t, good_output_t)
  + inbound_transport(source_t, good_output_t)
  + production_energy(utilization_t, grid_t, good_output_t)
  + outbound_transport(mode_t, shipments_t)
  + storage(raw_stock_t, fg_stock_t)
  + scrap(source_t, scrap_t, utilization_t, grid_t)
```

## 5. Horizon-adaptation state vector

The horizon model extends the short state with energy and resource states:

```text
x_t = {
  main_pipeline_t[eta],
  biosourced_pipeline_t[eta],
  backup_pipeline_t[eta],
  raw_inventory_t[source, batch],
  finished_goods_inventory_t[source, batch],
  backlog_t,
  battery_soc_t,
  battery_soh_t,
  biomass_transition_level_t,
  biomass_resource_stock_t,
  biomass_resource_stress_t,
  biosourced_transition_level_t,
  biosourced_local_stress_t,
  operational_feedback_t
}
```

Additional state-dependent mechanisms:

- climate stress changes capacity, supply availability, HVAC energy and scrap;
- battery state of health declines with throughput and heat stress;
- biomass use can deplete a local resource stock and increase future stress;
- biosourced material adoption ramps over time but is capped by local stress;
- backlog and climate pressure trigger service recovery and air freight.

## 6. Weather-driven event generation

The horizon model now separates weather curves from climate events.

The synthetic weather driver produces one row per month:

```text
w_t = {
  temp_c_t,
  humidity_pct_t,
  precip_mm_t,
  wind_ms_t,
  heat_index_c_t
}
```

Calendar rules only shape weather anomalies. Climate events are then generated
from weather thresholds:

```text
heatwave_t    = f(temp_c_t, heat_index_c_t)
drought_t     = f(precip_mm_t, temp_c_t, humidity_pct_t)
storm_t       = f(precip_mm_t, wind_ms_t)
cold_stress_t = f(temp_c_t)
```

The generated event label is:

```text
climate_event_t = {
  canicule if heatwave_t > 0,
  secheresse if drought_t > 0,
  tempete / inondation if storm_t > 0
}
```

The weather driver is exported as `ha_weather_driver.csv` and displayed as
`ha_weather_driver.png` in each horizon output package.

## 7. Parameter contract

Parameters now live in:

- `POC2026/config/sddlca_parameters.yml`
- `POC2026/horizon-adaptation/config/ha_parameters.yml`
- `POC2026/supply_geo_case/config/supply_geo_case.yml`

The scripts remain responsible for generating scenario time series. Parameter
files hold values that should be reviewable independently:

- lead times;
- initial stocks;
- environmental factors;
- economic factors;
- policy thresholds and strategy definitions.

Any future calibrated parameter should include, at minimum:

```text
value, unit, source, confidence, last_reviewed
```

The current YAML files are POC assumptions and should be treated as low
confidence until calibrated against industrial data or cited literature.

## 8. supply_geo primary case package

The `supply_geo_case` adapter turns the latest extended supply case into a
POC2026 run package:

```text
source:
  supply_geo/analysis/output8_GEO_normalized_simulation_ready_researched.json

outputs:
  POC2026/supply_geo_case/outputs/data/primary_supply_paths.csv
  POC2026/supply_geo_case/outputs/data/primary_supply_nodes.csv
  POC2026/supply_geo_case/outputs/data/primary_supply_lanes.csv
  POC2026/supply_geo_case/outputs/data/site_weather_driver.csv
  POC2026/supply_geo_case/outputs/data/supplier_risk_event_seed.csv
  POC2026/supply_geo_case/outputs/summaries/general_kpis.json
  POC2026/supply_geo_case/outputs/maps/supply_geo_results_dashboard.html
  POC2026/supply_geo_case/outputs/run/run_manifest.json
```

It keeps only active primary paths, in the role order:

```text
T4 raw material -> T3 first transformation -> T2 second transformation
-> T1 supplier -> OEM
```

The package mirrors the `etudecas` result contract at a smaller scale: stable
`data`, `reports`, `summaries`, `maps`, `plots` and `run` folders; a manifest;
and artifact discovery by logical domain.

The current package is not yet a full production system dynamics simulation.
It is the real topology and mass-allocation substrate for the next SDD-LCA
step. It already supports state-dependent event inputs by generating a
deterministic site-month weather driver and supplier risk event seeds:

```text
site_weather_t = {temp_c, humidity_pct, precip_mm, wind_ms, heat_index_c}
event_seed_t   = weather_threshold(site_weather_t)
```

Generated event seeds carry direct operational multipliers:

```text
capacity_multiplier, lead_time_multiplier, scrap_multiplier
```

These are scenario drivers, not calibrated meteorological observations.

## 9. Validation invariants

The tests in `POC2026/tests` enforce these invariants on generated artifacts:

- configs are parseable and contain required sections;
- weather drivers are exported and climate events are generated from weather
  intensities;
- the supply_geo primary case package exports 172 active primary paths from
  170 usable records and excludes the 5 known non-supply/process records;
- primary path mass allocation reconciles to source record mass;
- every supply_geo primary path has T4, T3, T2, T1 and OEM nodes plus four
  transport lanes;
- supply_geo site weather curves generate non-empty supplier event seeds;
- policy names are unique and thresholds are coherent;
- stocks, orders, flows, backlog and energy quantities are non-negative;
- source splits sum back to total inventory/output quantities;
- capacity utilization remains in `[0, 1]`;
- state-space pipeline totals match ETA bucket sums;
- LCA method outputs remain ordered as expected for the POC scenarios;
- energy supply components reconcile with total energy demand in horizon runs.

These tests do not prove the model is calibrated. They protect the core stock-
flow and method-comparison semantics from accidental regressions.
