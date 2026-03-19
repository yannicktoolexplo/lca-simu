# Monte Carlo

Script principal:
- `run_montecarlo_analysis.py`

Commande:
```bash
python3 etudecas/simulation/montecarlo/run_montecarlo_analysis.py --runs 120
```

Options utiles:
- `--seed 42` (reproductibilite)
- `--days 30` (defaut 30 jours ; mettre `0` pour utiliser l'horizon du scenario)
- `--keep-run-artifacts` (garde les dossiers run_XXXX)

Sorties:
- `result/montecarlo_samples.csv`
- `result/montecarlo_summary.json`
- `result/montecarlo_report.md`
- `result/montecarlo_failed_runs.csv` (si erreurs)
