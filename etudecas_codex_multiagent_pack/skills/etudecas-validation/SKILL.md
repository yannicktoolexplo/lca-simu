---
name: etudecas-validation
description: Use when validating Etudecas changes, checking invariants, running unit tests, reviewing generated artifacts, auditing lot paths, checking map payloads, or deciding whether a change is safe to ship.
---

# Etudecas Validation

## Workflow

1. Start with the fast suite.
2. Add targeted checks for the touched layer: simulation, lot trace, map, data or sensitivity.
3. Verify artifacts are compact and reproducible.
4. Report skipped slow tests and residual risk explicitly.
5. Never approve a change that only hides a data or model inconsistency.

## Commands

Fast baseline:

```powershell
python -B -m unittest discover -s etudecas -p "test*.py"
```

Slow checks are manual/nightly and may require:

```powershell
$env:ETUDECAS_RUN_SLOW_TESTS='1'
python -B -m unittest discover -s etudecas -p "test*.py"
```
