# Études de sensibilité

Ce dossier conserve les lanceurs de méthodes spécialisées. Le parcours
`python -B -m etudecas.simulation.studies sensitivity` prépare les plans et
rassemble les résultats au format commun ; il ne lance pas implicitement
les calculs. Son implémentation est dans `experiments/sensitivity`.

Les méthodes disponibles restent distinctes :

- `run_sensitivity_analysis.py`
- `run_targeted_experiment_plan.py`
- `run_supplier_parameter_sensitivity.py`
- `run_supplier_risk_campaign.py`
- `run_realistic_sensitivity_study.py`
- `run_threshold_sensitivity_study.py`
- `run_shock_campaign.py`

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

Le lanceur général, l'étude réaliste et l'étude de seuils proposent
`--artifact-mode compact` (par défaut) ou `full`. `--keep-detailed-case`
permet de conserver un cas détaillé en mode compact. La sensibilité des
paramètres fournisseurs propose aussi le mode `summary` ; les options ne
sont donc pas interchangeables entre lanceurs. Consulter leur `--help`.

Voir [la politique de conservation](ARTIFACT_POLICY.md). Les anciens outils
d'alias et de nettoyage collectif ont été retirés ; le code du nommage des cas
est maintenant dans `experiments/sensitivity/designs.py`.

## Sorties a privilegier

Pour les nouvelles etudes, privilegier:

- `etudecas/simulation/experiments/result/<study>/study_manifest.json`
- `etudecas/simulation/experiments/result/<study>/metrics.csv`
- `etudecas/simulation/experiments/result/<study>/registry.csv`
- `etudecas/simulation/experiments/result/<study>/summary.json`

Les dossiers `cases/*/simulation_output/*` ne doivent pas etre conserves par
defaut. Ils sont regenerables depuis les scripts et doivent rester des artefacts
temporaires.
