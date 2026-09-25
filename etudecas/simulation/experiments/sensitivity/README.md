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
python -m etudecas.simulation.studies sensitivity init-example
python -m etudecas.simulation.studies sensitivity design --study etudecas/config/sensitivity/supplier_lead_capacity_example.json
python -m etudecas.simulation.studies sensitivity materialize --study etudecas/config/sensitivity/supplier_lead_capacity_example.json
python -m etudecas.simulation.studies sensitivity ingest --study etudecas/config/sensitivity/supplier_lead_capacity_example.json --case-csv CHEMIN_CSV_REGENERE/scenario_results.csv
python -m etudecas.simulation.studies sensitivity discover --root etudecas/simulation/sensibility
python -m etudecas.simulation.studies sensitivity consolidate --root etudecas/simulation/sensibility
```

`CHEMIN_CSV_REGENERE/scenario_results.csv` is an illustrative placeholder:
replace it with the case-level CSV produced by your regenerated study. Historical
campaign outputs are not required to remain in the repository.

`discover` and `consolidate` intentionally ignore heavy folders such as
`cases`, `simulation_output`, `data`, `plots`, `maps`, `reports` and
`summaries`.
