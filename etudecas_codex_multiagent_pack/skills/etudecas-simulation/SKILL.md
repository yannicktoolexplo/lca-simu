---
name: etudecas-simulation
description: Use when working on the Etudecas dynamic simulation engine, including MRP, production, inventory, supplier flows, state-dependent risks, replanning, costs, output writers, or the simulation API.
---

# Etudecas Simulation

## Workflow

1. Identify whether the change touches model logic, orchestration, outputs, or API.
2. Prefer `etudecas/simulation/engine/api.py` for new entrypoints.
3. Keep business parameters in graph/config data, not hard-coded in the engine.
4. Avoid adding new full-run artifacts by default; emit manifests, summaries and compact outputs.
5. Add focused tests for any changed rule.

## Key Files

- Engine monolith to reduce: `etudecas/simulation/engine/run_first_simulation.py`.
- Stable API: `etudecas/simulation/engine/api.py`.
- Contracts: `etudecas/simulation/engine/contracts.py`.
- Shared batch helpers: `etudecas/simulation/analysis_batch_common.py`.

## Validation

Run at minimum:

```powershell
python -B -m unittest discover -s etudecas -p "test*.py"
```

For engine changes, add targeted tests around MRP, production reports, lot sizing, risks, or outputs.
