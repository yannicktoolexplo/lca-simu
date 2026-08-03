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

## Daily external controls

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
