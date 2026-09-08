# Simulation Engine API

This package provides the stable programmatic boundary for running Etudecas
simulations.

The current engine is still implemented by the historical CLI script, but
callers should use this API instead of invoking that script directly.

## Python usage

```python
from etudecas.simulation.engine import SimulationOverrides, SimulationRequest, simulate

result = simulate(
    SimulationRequest(
        input_path="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        scenario_id="scn:BASE",
        days=365,
        output_profile="lot_trace",
        overrides=SimulationOverrides(
            supplier_capacity_node_scale={"SDC-VD0914320A": 0.7},
            edge_src_lead_time_scale={"SDC-VD0914320A": 1.3},
        ),
    )
)

print(result.kpis)
```

## Demand excitation for frequency identification

`SimulationRequest(demand_perturbation_csv="excitation.csv")` forwards the
strict opt-in engine flag `--demand-perturbation-csv`. With no field/flag, the
engine does not create a perturbation artifact and keeps the historical demand
path and summary schema unchanged. Demand excitation can be combined with an
open-loop control schedule or a feedback policy because it is an exogenous
input, not a control command.

The input CSV contract is exactly:

```csv
day,node_id,item_id,demand_multiplier
0,DC-PARIS,item:FG_A,1.05
1,DC-PARIS,item:FG_A,0.95
```

`day` is a zero-based measured day in the current simulation horizon; warm-up
days are never addressable. `node_id` and `item_id` must form an exact demand
pair in the selected scenario. Blank/global scopes, duplicate pair/day rows,
unknown columns, out-of-horizon days and non-finite multipliers are rejected.
`demand_multiplier` is dimensionless and must lie in `[0.5, 1.5]`; values are
rejected rather than clamped so the realized identification input cannot differ
silently from the designed signal.

On each measured day, the multiplier is applied to that day's physical demand
signal before customer service and before MRP propagation. The J0 state boundary
therefore remains identical to the unexcited run, including after a physical
warm-up. An enabled run writes
`data/canonical_demand_perturbations.csv` with these stable columns:

- `day`, `node_id`, `item_id`, `demand_multiplier`;
- `base_demand_qty`, `perturbed_demand_qty`, `demand_delta_qty`;
- `source_line`, `status`.

`summaries/first_simulation_summary.json` exposes the source path and SHA-256,
configured `row_count`, physical `applied_count`, bounds, day basis and audit
path under `policy.demand_perturbation`. The same object is copied to
`run/run_manifest.json` under `metadata.demand_perturbation`.

## Open-loop daily external controls

`SimulationRequest(control_schedule_csv="controls.csv")` forwards a typed daily
control schedule to the engine as `--control-schedule-csv`. When the field is
omitted, no flag is emitted and the historical physical dynamics and legacy
values are unchanged. The output contract now also contains an empty action
ledger and neutral control-audit columns in the MRP trace. The pipeline
`simulate` command accepts the same optional flag. Its public randomness
contract also exposes `seed` and the tri-state
`common_random_numbers`; omitting both preserves the engine defaults, while an
explicit value is forwarded as `--seed` and
`--[no-]common-random-numbers`.

The CSV contract is implemented in `control_schedule.py`. `day` is a required,
zero-based measured day; it does not include warm-up days. `policy`,
`node_id`, `supplier_id`, `item_id` and `dst_node_id` are optional audit/scope
columns. Blank scopes are global. A more-specific matching scope overrides a
less-specific scope field by field.

Supported action columns are:

- `order_multiplier` in `[0, 2]`;
- `safety_stock_multiplier` in `[0, 3]`;
- `production_target_multiplier` in `[0, 2]`;
- `capacity_multiplier` in `[0, 1.5]`;
- `external_procurement_multiplier` in `[0, 3]`;
- `expedite_level` in `[0, 1]`;
- `lead_time_adjustment_days`, an integer in `[-30, 90]`;
- `priority_weight` in `[0, 10]`.

All values except the lead-time adjustment are dimensionless. Out-of-bound
values are clamped and retained as requested/effective/bound metadata.
Non-finite values, unknown columns or catalog identifiers, duplicate scopes and
ambiguous equal-specificity scopes are rejected. Structurally impossible
action/scope pairs are rejected as well: production targets only support
`node_id`/`item_id`, and safety-stock controls cannot carry `supplier_id`.
When the catalog identifies a `node_id` as a supplier, supplier-capacity
controls must target it through `supplier_id` so lane execution can resolve it.
`ResolvedControl.to_ledger_rows` and `write_control_ledger_csv` expose stable
audit serialization.

The executable engine writes `canonical_action_ledger.csv`. Its status and
stage distinguish a physical application from a neutral/no-flow resolution or
an unmatched schedule row. Quantity-bearing rows expose the distinct
`q_mrp_base_qty`, post-safety, post-order, post-supplier, post-constraint,
post-lotification and executable quantities. Supplier capacity is only reported
as applied when a modeled capacity actually constrained that operational stage.

## Canonical state-feedback controls

`SimulationRequest(control_policy_json="policy.json")` forwards a declarative
feedback policy as `--control-policy-json`. The equivalent direct-engine call is:

```powershell
python etudecas/simulation/engine/run_first_simulation.py `
  --input <canonical_graph.json> `
  --output-dir <result_dir> `
  --scenario-id scn:BASE `
  --days 90 `
  --seed 200260 `
  --common-random-numbers `
  --supplier-state-dependent-risks `
  --mrp-demand-signal-smoothing-days 1 `
  --warmup-days 0 `
  --supplier-state-risk-observation-warmup-days 0 `
  --control-policy-json `
    etudecas/prototypes/scan_2027_risk_control/config/canonical_closed_loop_config.json
```

`--control-schedule-csv`, `--control-policy-json`,
`--control-policy-v2-json` and `--control-policy-v3-json` are mutually
exclusive. A precomputed CSV is an open-loop schedule, whereas a JSON policy is
evaluated online from realized canonical state. Omitting all four retains the
historical MRP path.

The causal contract is strict: after completing measured day `J`, the engine
builds a `CanonicalObservation`, passes it to the provider, and accepts only
commands whose `effective_day` is `J + 1`. Consequently day 0 has no feedback
command based on day-0 state, and observations must be sequential. A forward
MRP demand window wider than one day would leak the future realized demand
profile indirectly through the day-J state. The engine measures this look-ahead,
sets `future_realization_access=true`, and refuses the strict closed-loop claim;
the canonical campaign therefore forces the effective window to one day. The
provider is a bounded safety layer
around the existing MRP, lot-sizing, campaign and capacity logic; it does not
replace those physical stages.

The observation contains realized demand, served quantity and service level,
backlog quantity and demand-day equivalent, total inventory, finished- and
material-inventory cover, production and supplier utilization, executed order
pair count, the median pairwise relative order change, a bounded
supplier-disruption severity score and the active physical-event count. The
pairwise nervousness is dimensionless and never sums incompatible UOMs.
Material cover uses realized consumption and current-day raw propagated need,
not a smoothed future demand window. The provider also retains causal memory of
backlog, nervousness, supplier stress and recent disruption. It classifies the state into
`NOMINAL`, `MATERIAL_TENSION`, `CAPACITY_SATURATION`, `SUPPLIER_STRESS`,
`OSCILLATORY`, `CRISIS`, `RECOVERY` or `POST_CRISIS_OVERSTOCK`.

The versioned policy controls four safeguards:

- `confirmation_days` supplies temporal debounce before a non-emergency regime
  is confirmed; it is not a separate entry/exit threshold hysteresis;
- `review_period_days` and `minimum_dwell_days` limit policy switching, while a
  configured emergency regime can trigger an immediate review;
- `slew_limits` bound the day-to-day change of each of the eight typed control
  levers before the existing absolute bounds and scope checks are applied;
- an invalid or non-finite observation immediately selects `fallback_policy`
  and clears stale external actions. The default fallback is neutral
  `mrp_reference`.

The loader requires the fallback playbook to be physically neutral. It also
rejects non-text scope identifiers, equal-specificity overlaps across reachable
playbooks, and active general scopes beneath compatible targeted scopes. This
versioned topology restriction makes the configured slew limit valid on the
action actually resolved by the engine, not only on an internal per-scope
value.

Feedback runs write the following audit evidence:

- `data/canonical_closed_loop_observations.csv`: normalized realized states,
  validity, regime inputs and deterministic observation hashes;
- `data/canonical_closed_loop_decisions.csv`: raw/confirmed regimes, temporal confirmation,
  reviews, dwell decisions, selected policy, fallback and causal day pair;
- `data/canonical_closed_loop_commands.csv`: requested/effective scoped commands
  and slew-limited fields;
- `data/canonical_action_ledger.csv`: the command joined to the physical stage,
  quantity chain, execution status and binding reason;
- `summaries/first_simulation_summary.json`, under
  `policy.control_provider`: policy/config hash, counts, causal lag, physical
  application evidence and artifact paths.

Passing the flag alone is not proof of closed-loop execution. The engine sets
`policy.control_provider.closed_loop_claimed=true` only when online observations
exist, observation and decision counts match, every decision satisfies
`effective_day = decision_day + 1`, the effective realized-demand window has
zero future-day offset, and at least one feedback action was physically
applied. The summary exposes every check and any failed reason. Consumers must
read that strict boolean rather than infer the claim from a filename or command
line.

The historical V1 interface keeps its original cold-start behavior: controller
memory is initialized at measured day 0. If a physical warm-up is requested on
V1, the summary records `controller_dynamic_warmup_days=0`, marks the mismatch,
emits a warning and disables `closed_loop_claimed`. Existing V1 campaigns and
defaults are unchanged.

V2 is a separate opt-in interface. Use `--control-policy-v2-json` together with
`--controller-prime-during-warmup` to feed negative-day end-of-day observations
to controller memory without resolving or applying controls. Priming is written
to `data/canonical_controller_priming.csv`; measured observations still begin at
J0 and the first possible command is effective at J1. The optional
`--warmup-boundary-audit` records a deterministic SHA-256 fingerprint of core
engine state at the J0 cutover. That fingerprint supports paired burn-in
equality checks; it is explicitly not a loadable restart checkpoint.

The V2 gates fail closed on invalid observations. Positive order, safety-stock
and production changes require the service-recovery gate; external procurement
and expediting require the stricter exceptional-cost gate. Gate closure returns
the guarded action to neutral immediately, without a slew-limited tail.

V3 is another additive opt-in interface, selected only by
`--control-policy-v3-json`. It keeps the V2 supervisory regimes, safeguards and
priming contract, then adds a small continuous correction inside one configured
regime and playbook. The current research configuration activates it only in
`SUPPLIER_STRESS` with `supplier_relief`: correction intensity rises smoothly
with projected stress, while service, backlog and stock-cover guards reduce or
cancel it. Order and production multipliers remain within configured lower
bounds and their daily movement is limited. The correction is still computed
from day `J` state and can act only on day `J + 1`; invalid observations and
safety violations return it to the neutral value. V1, V2, cold-start defaults
and the open-loop schedule path are unchanged.

The typed `SimulationRequest` adapter currently exposes only the historical V1
`control_policy_json` field. Until dedicated V2/V3 request fields are added,
invoke those interfaces through the direct engine command or the canonical
campaign runners so the versioned flag cannot be confused.

The supplier-disruption input is a bounded proxy built from active physical
effects; it is not an incident probability and cost-only events do not increase
it. The optional dynamic parameter `recent_disruption_score_floor` controls
when that score arms the recent-incident memory. Its default is `0.0`, which
strictly preserves the historical rule (every positive score arms the memory);
configured values must lie in `[0, 1]`, and arming requires a score strictly
above the configured value. The finite-state thresholds and stress dynamics remain research
coefficients requiring calibration. A 60-day paired burn-in reduces cold-start
bias but does not prove stationarity. This integration does not establish global
stability, an optimized MPC law, or frequency-domain margins. A first designed
V3 demand-response pilot has now measured four frequencies in a fixed stressed
operating regime. It detected coherent controller motion at the two slowest
frequencies, but the physical responses were not sufficiently repeatable to
support a local transfer function, attenuation or stability-margin claim.

## Request contract without server

The UI can build a simulation request without executing it. This keeps the
current HTML offline-first while preparing a later local server or Pyodide
worker integration.

```python
from etudecas.simulation.engine.contracts import supplier_parameter_request_payload

payload = supplier_parameter_request_payload(
    input_path="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
    scenario_id="scn:BASE",
    days=1825,
    parameter_group="supplier_capacity_node",
    supplier_id="SDC-VD0914320A",
    level=0.7,
)
```

This returns a JSON-compatible object with the same shape accepted by
`request_from_dict(...)` and by `POST /simulate`.

## Local HTTP API

```bash
python -m etudecas.simulation.engine.server --host 127.0.0.1 --port 8765
```

For the interactive map, use the launcher from the repository root:

```bash
python etudecas/launch_interactive_map.py
```

On Windows, double-click:

```text
launch_etudecas_interactive.cmd
```

The launcher starts the local API, opens the HTML map, and keeps the server
alive while its terminal window remains open. The HTML file alone cannot start
Python because browsers intentionally block that for security reasons.

Health check:

```bash
curl http://127.0.0.1:8765/health
```

Run a simulation:

```bash
curl -X POST http://127.0.0.1:8765/simulate ^
  -H "Content-Type: application/json" ^
  -d "{\"input_path\":\"etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json\",\"scenario_id\":\"scn:BASE\",\"days\":365,\"output_profile\":\"diagnostic\",\"overrides\":{\"supplier_capacity_node_scale\":{\"SDC-VD0914320A\":0.7}}}"
```

## Output profiles

- `minimal`: compact run, no lot trace, no lot audit.
- `diagnostic`: compact run, no lot trace, no lot audit.
- `lot_trace`: compact run with lot events and genealogy.
- `full_debug`: full CSV output with lot trace.

## Why this exists

The UI, sensitivity studies and future web app should depend on:

```text
input graph + overrides -> simulate(...) -> structured result
```

not on a large CLI script that writes many files. This API lets us migrate in
small steps: first by wrapping the existing script, then by moving the engine
internals toward a pure in-memory implementation.
