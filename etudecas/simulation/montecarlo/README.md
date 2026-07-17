# Monte Carlo

Script principal:
- `run_montecarlo_analysis.py`
- `run_robust_montecarlo.py` pour une suite adaptative multi-profils

Commande:
```bash
python3 etudecas/simulation/montecarlo/run_montecarlo_analysis.py --runs 120
```

Commande robuste recommandee pour un run existant:
```bash
python3 etudecas/simulation/montecarlo/run_robust_montecarlo.py \
  --manifest-json etudecas/simulation/result/_reruns/<run>/run_manifest.json \
  --output-dir etudecas/simulation/result/_reruns/<run>/montecarlo \
  --days 1825 \
  --probe-runs 8 \
  --final-runs 60
```

Cette commande teste plusieurs profils (`workshop`, `risk_probe`,
`stress_probe`, `breakpoint_probe`), mesure si les KPI bougent assez sans
detruire tout le systeme, puis lance le profil selectionne avec les trajectoires
compactes pour la carte.

Options utiles:
- `--seed 42` (reproductibilite)
- `--days 30` (defaut 30 jours ; mettre `0` pour utiliser l'horizon du scenario)
- `--uncertainty-profile workshop|risk_probe|stress_probe|breakpoint_probe|legacy`
  - `workshop`: incertitude operationnelle proche du nominal
  - `risk_probe`: aleas elargis pour detecter les fragilites
  - `stress_probe`: stress exploratoire impactant mais lisible, pas une probabilite previsionnelle
  - `breakpoint_probe`: stress severe pour chercher les points de rupture
- `--keep-run-artifacts` (garde les dossiers run_XXXX)
- `--save-trajectories` (garde uniquement un JSON compact de trajectoires journalieres pour l'onglet Incertitude)
- `--trajectory-max-points 730` (defaut ; reduit les vues longues 5 ans, `0` garde tous les jours)
- `--trajectory-display-runs 60` (defaut ; limite les trajectoires dessinees, mais les bandes percentiles restent calculees sur tous les runs)

Options robustes utiles:
- `--final-profile auto|workshop|risk_probe|stress_probe|breakpoint_probe`
- `--probe-runs 8` pour calibrer rapidement l'amplitude
- `--final-runs 60` ou plus pour la distribution finale
- `--profiles workshop,risk_probe,stress_probe,breakpoint_probe`

Sorties:
- `result/montecarlo_samples.csv`
- `result/montecarlo_summary.json`
- `result/montecarlo_trajectories.json` si `--save-trajectories`
- `result/montecarlo_report.md`
- `result/montecarlo_failed_runs.csv` (si erreurs)

La suite robuste ecrit en plus:
- `montecarlo_suite_summary.json`
- `montecarlo_suite_report.md`
- `selected/montecarlo_summary.json`
- `selected/montecarlo_trajectories.json`
