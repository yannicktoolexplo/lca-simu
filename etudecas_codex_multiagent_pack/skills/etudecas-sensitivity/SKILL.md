---
name: etudecas-sensitivity
description: Use when working on Etudecas sensitivity studies, risk scenarios, state-dependent events, amplitude/duration sweeps, compact scenario comparison payloads, or artifact retention for experiments.
---

# Etudecas Sensitivity

## Workflow

1. Prefer `etudecas/simulation/experiments/sensitivity` for new studies.
2. Keep historical `simulation/sensibility` scripts as recipes or wrappers.
3. Store `study_manifest.json`, `metrics.csv`, `registry.csv` and `summary.json`.
4. Avoid storing complete `simulation_output` per scenario unless debugging a small selected set.
5. Compare scenarios by service, backlog, production reports, supplier effects, costs and stock stress.

## Key Files

- Generic contract: `etudecas/simulation/experiments/sensitivity`.
- Historical runners: `etudecas/simulation/sensibility`.
- Risk sweep: `etudecas/simulation/analysis/run_risk_amplitude_duration_sweep.py`.
- Artifact policy: `etudecas/simulation/sensibility/ARTIFACT_POLICY.md`.

## Validation

Run fast tests and inspect generated manifests:

```powershell
python -B -m unittest discover -s etudecas -p "test*.py"
```
