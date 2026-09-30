# Conservation des résultats de sensibilité

Les lanceurs `run_sensitivity_analysis.py`, `run_realistic_sensitivity_study.py`
et `run_threshold_sensitivity_study.py` gèrent les résultats à chaque calcul :

- `--artifact-mode compact` est leur valeur par défaut. Après extraction des
  indicateurs, les données détaillées, cartes et figures des cas sont retirées ;
  leurs synthèses et rapports restent disponibles, ainsi que les entrées des cas.
- `--artifact-mode full` conserve les sorties détaillées de tous les cas.
- `--keep-detailed-case IDENTIFIANT` conserve un cas complet en mode compact.
  L'option peut être répétée. Le nominal est conservé par défaut ; les lanceurs
  général et réaliste conservent aussi sa répétition `baseline_repeat`.

Pour reconstruire une carte détaillée, conserver le cas correspondant avec
`--keep-detailed-case` ou le recalculer en mode `full`.

Le parcours générique `python -m etudecas.simulation.studies sensitivity`
prépare les scénarios et consolide leurs indicateurs ; ses commandes `design`
et `materialize` ne lancent pas la simulation. Voir son
[guide](../experiments/sensitivity/README.md) pour les sorties compactes.

Les anciens utilitaires de création d'alias et de nettoyage collectif des
résultats ont été retirés du code actif. Leurs sources restent dans la capsule
de reproduction `a99c4246c2be2b0dcc0a690e1cadff454c259e3184f05ee408e832fe1227b9d1.zip`
sous `etudecas/config/reproduction_20260920/sources/`. Ils ne sont pas nécessaires
au calcul des études ni à la reconstruction des cartes.
