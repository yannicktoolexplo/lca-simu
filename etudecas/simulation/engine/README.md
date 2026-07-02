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
