# Sensibility

Script principal:
- `run_sensitivity_analysis.py`
- `run_targeted_experiment_plan.py` (plan d'experiences cible, 15 scenarios)

Commande:
```bash
python3 etudecas/simulation/sensibility/run_sensitivity_analysis.py
```

Plan cible:
```bash
python3 etudecas/simulation/sensibility/run_targeted_experiment_plan.py
```

Options utiles:
- `--delta 0.2` (variation +/-20% des facteurs)
- `--days 30` (defaut 30 jours ; mettre `0` pour utiliser l'horizon du scenario)
- `--scenario-id scn:BASE`

Sorties:
- `result/sensitivity_cases.csv`
- `result/sensitivity_delta_vs_baseline.csv`
- `result/sensitivity_summary.json`
- `result/sensitivity_report.md`
- `result/cases/*/simulation_output/*`
- `targeted_plan_result/scenario_results.csv`
- `targeted_plan_result/scenario_delta_vs_baseline.csv`
- `targeted_plan_result/experiment_plan_summary.json`
- `targeted_plan_result/experiment_plan_report.md`
