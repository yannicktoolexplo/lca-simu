# Sensibility

Ce dossier contient les runners historiques de sensibilite. La cible de
developpement est maintenant `etudecas/simulation/experiments/sensitivity`,
qui porte le contrat generique `study_manifest.json`, `metrics.csv`,
`registry.csv` et `summary.json`.

Les scripts historiques restent utiles comme recipes metier:

- `run_sensitivity_analysis.py`
- `run_targeted_experiment_plan.py`
- `run_supplier_parameter_sensitivity.py`
- `run_supplier_risk_campaign.py`

## Commandes

```powershell
python etudecas\simulation\sensibility\run_sensitivity_analysis.py
python etudecas\simulation\sensibility\run_targeted_experiment_plan.py
```

Options frequentes:

- `--delta 0.2`: variation +/-20% des facteurs.
- `--days 30`: horizon court par defaut; `0` utilise l'horizon du scenario.
- `--scenario-id scn:BASE`: scenario de reference.

## Politique d'artefacts

Ne pas conserver les sorties completes de simulation pour tous les cas.

Modes de retention:

- `summary`: mode par defaut, garde uniquement manifests, summaries, reports et petits CSV de diagnostic.
- `compact`: garde quelques CSV operationnels selectionnes, sans `mrp_trace_daily.csv` par defaut.
- `full`: garde tout `simulation_output`, uniquement pour debug cible.

Voir `ARTIFACT_POLICY.md` pour la commande de nettoyage.

## Sorties a privilegier

Pour les nouvelles etudes, privilegier:

- `etudecas/simulation/experiments/result/<study>/study_manifest.json`
- `etudecas/simulation/experiments/result/<study>/metrics.csv`
- `etudecas/simulation/experiments/result/<study>/registry.csv`
- `etudecas/simulation/experiments/result/<study>/summary.json`

Les dossiers `cases/*/simulation_output/*` ne doivent pas etre conserves par
defaut. Ils sont regenerables depuis les scripts et doivent rester des artefacts
temporaires.
