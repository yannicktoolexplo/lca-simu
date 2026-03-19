# Organisation des resultats d'analyse

- `etudecas/simulation/montecarlo/result/`:
  - `montecarlo_report.md`
  - `montecarlo_summary.json`
  - `montecarlo_samples.csv`

- `etudecas/simulation/sensibility/result/`:
  - `sensitivity_report.md`
  - `sensitivity_summary.json`
  - `sensitivity_cases.csv`
  - `sensitivity_delta_vs_baseline.csv`

- `etudecas/simulation/sensibility/targeted_plan_result/`:
  - `experiment_plan_report.md`
  - `experiment_plan_summary.json`
  - `scenario_results.csv`
  - `scenario_delta_vs_baseline.csv`
  - `targeted_experiment_insights.md`

- `etudecas/simulation/result/` (resultats generaux):
  - `reference_baseline/`
    - `reference_baseline_manifest.md`
    - `reference_baseline_report.md`
    - `reference_baseline_summary.json`
  - `data/`
    - `first_simulation_daily.csv`
    - `production_*.csv`
    - `critical_input_materials_analysis.csv`
    - `fill_rate_whatif_analysis.csv`
    - `full_system_exploration_samples.csv`
  - `summaries/`
    - `first_simulation_summary.json`
    - `deep_supply_analysis_summary.json`
    - `full_system_exploration_summary.json`
  - `reports/`
    - `first_simulation_report.md`
    - `general_analysis_insights.md`
    - `deep_supply_analysis.md`
    - `deep_supply_analysis_technical_review.md`
    - `full_system_exploration_report.md`
  - `maps/`
    - `supply_graph_poc_geocoded_map_with_factory_hover.html`
  - `plots/`
    - `factories/input_stocks/`
    - `factories/output_products/`
    - `suppliers/input_stocks/`
    - `distribution_centers/factory_outputs/`

- `etudecas/simulation/result/max_param_exploration/`:
  - exploration elargie (757 runs)
  - `full_system_exploration_report.md`
  - `full_system_exploration_summary.json`
  - `full_system_exploration_samples.csv`
