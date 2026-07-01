# Generic Sensitivity Studies

This package separates sensitivity study orchestration from historical
`sensibility` runners.

## Contract

- `study_manifest.json`: study definition and reproducibility context.
- `scenario_design.csv`: scenarios to run, one row per parameter combination.
- `metrics.csv`: normalized case-level KPIs, using `kpi::<name>` columns.
- `registry.csv`: lightweight index of case ids, source files and output dirs.
- `summary.json`: compact KPI ranges for visualization.

The web map should consume these compact files. Full simulation outputs remain
optional debug artifacts controlled by retention mode.

## Commands

```bash
python -m etudecas.simulation.experiments.sensitivity init-example
python -m etudecas.simulation.experiments.sensitivity design --study etudecas/config/sensitivity/supplier_lead_capacity_example.json
python -m etudecas.simulation.experiments.sensitivity materialize --study etudecas/config/sensitivity/supplier_lead_capacity_example.json
python -m etudecas.simulation.experiments.sensitivity ingest --study etudecas/config/sensitivity/supplier_lead_capacity_example.json --case-csv etudecas/simulation/sensibility/active_supplier_parameter_result_60_75_guarded/supplier_parameter_sensitivity_cases.csv
python -m etudecas.simulation.experiments.sensitivity discover --root etudecas/simulation/sensibility
python -m etudecas.simulation.experiments.sensitivity consolidate --root etudecas/simulation/sensibility
```

`discover` and `consolidate` intentionally ignore heavy folders such as
`cases`, `simulation_output`, `data`, `plots`, `maps`, `reports` and
`summaries`.
