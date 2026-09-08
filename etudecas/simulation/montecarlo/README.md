# Monte Carlo

Script principal:
- `run_montecarlo_analysis.py`
- `run_robust_montecarlo.py` pour une suite adaptative multi-profils
- `calibrate_from_sensitivity.py` pour transformer une etude de sensibilite du run en plancher de profil Monte Carlo

Commande:
```bash
python3 etudecas/simulation/montecarlo/run_montecarlo_analysis.py --runs 120
```

Commande operationnelle recommandee:
```bash
python3 etudecas/run_etudecas_pipeline.py rebuild-active
```

Par defaut, `rebuild-active` relance ou reutilise une sensibilite locale au run,
ecrit `montecarlo/sensitivity_calibration.json`, puis lance Monte Carlo avec un
profil minimum adapte au systeme courant. Cela evite qu'une grosse modification
du modele garde un Monte Carlo trop faible et quasi plat.

Commande robuste recommandee pour un run existant:
```bash
python3 etudecas/simulation/montecarlo/run_robust_montecarlo.py \
  --manifest-json etudecas/simulation/result/_reruns/<run>/run_manifest.json \
  --output-dir etudecas/simulation/result/_reruns/<run>/montecarlo \
  --days 1825 \
  --sensitivity-calibration-json etudecas/simulation/result/_reruns/<run>/montecarlo/sensitivity_calibration.json \
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
- `--resume` (defaut ; reprend les runs valides depuis des checkpoints gzip atomiques)
- `--no-include-systemic-supplier-reliability` (defaut ; exclut le choc simultane de fiabilite de tous les fournisseurs)
- `--paired-factor-count 8` et `--paired-background-count 20` (effets marginaux controles sur des plages metier, dans 20 contextes partages)
- `--no-paired-propagation` pour separer la campagne Monte Carlo principale des experiences controlees longues

Options robustes utiles:
- `--final-profile auto|workshop|risk_probe|stress_probe|breakpoint_probe`
- `--probe-runs 8` pour calibrer rapidement l'amplitude
- `--final-runs 60` ou plus pour la distribution finale
- `--profiles workshop,risk_probe,stress_probe,breakpoint_probe`
- `--sensitivity-calibration-json ...` pour imposer un plancher issu de la sensibilite

Sorties:
- `result/montecarlo_samples.csv`
- `result/montecarlo_summary.json`
- `result/montecarlo_trajectories.json` si `--save-trajectories`
- `result/variance_decomposition.json` (contributions predictives par famille et part interactions/non expliquee ; ce ne sont pas des indices de Sobol)
- `result/montecarlo_cost_diagnostics.json` (cout supply, cout hors production, recours fournisseur exceptionnel, exposition combinee et couplages comptables)
- `result/montecarlo_paired_propagation.json` si la propagation controlee est activee
- `result/montecarlo_report.md`
- `result/montecarlo_failed_runs.csv` (si erreurs)
- `result/checkpoints/` (reprise compacte ; pas un archivage des runs complets)

La suite robuste ecrit en plus:
- `montecarlo_suite_summary.json`
- `montecarlo_suite_report.md`
- `selected/montecarlo_summary.json`
- `selected/montecarlo_trajectories.json`

La calibration par sensibilite ecrit:
- `montecarlo/sensitivity_calibration.json`
- dans le resume Monte Carlo: `uncertainty_profile`, `effective_uncertainty_profile` et `sensitivity_calibration`
