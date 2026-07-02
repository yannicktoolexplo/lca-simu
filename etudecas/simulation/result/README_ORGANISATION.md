# Organisation des resultats de simulation

`etudecas/simulation/result` ne doit pas devenir une archive permanente de tous
les runs. Les simulations sont regenerables; le depot doit conserver seulement
les resultats utiles au developpement courant et a la validation.

## Regle de retention

Conserver localement:

- un run complet canonique pour l'interface et les audits lots;
- les payloads compacts necessaires aux comparaisons de scenarios;
- les summaries, manifests et rapports courts;
- quelques fixtures reduits pour tests.

Eviter de conserver:

- plusieurs runs 5 ans complets redondants;
- les `mrp_trace_daily.csv` de runs non canoniques;
- les HTML generes non canoniques;
- les dossiers debug sans manifest.

## Run canonique courant

Le run de reference actuel est:

```text
_codex_lot_trace_5y_risk_portfolio/
```

Il contient les traces necessaires a la carte, au suivi de lots, aux risques
simules et aux audits de coherence.

## Format attendu pour un run conserve

Un run conserve devrait contenir:

```text
<run>/
  data/       # CSV necessaires, pas tous les CSV si le run est compact
  reports/    # rapports markdown/csv courts
  maps/       # carte canonique si utile
  summaries/  # KPI et syntheses
  run_manifest.json
```

`run_manifest.json` doit identifier le graphe d'entree, la config, l'horizon,
les options de simulation, la date, le mode de retention et les hashes utiles.

## Etudes de sensibilite

Les resultats de sensibilite doivent aller en priorite dans:

```text
etudecas/simulation/experiments/result/<study>/
```

avec `study_manifest.json`, `metrics.csv`, `registry.csv` et `summary.json`.
Les sorties completes de chaque scenario ne doivent etre gardees que pour un
debug explicite.
