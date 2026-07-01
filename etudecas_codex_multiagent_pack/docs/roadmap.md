# Roadmap recommandée pour `etudecas`

## PR 1 — Structure projet et contrats

Créer les interfaces minimales : `CaseStudy`, `ConfigLoader`, `ValidationReport`.

## PR 2 — Validation données générique

Créer `DataValidator`, schémas YAML et tests données.

## PR 3 — Moteur KPI configurable

Créer `KPIEngine`, normalisation, agrégations et tests métier.

## PR 4 — Trajectoires

Créer `TrajectoryBuilder` pour construire des trajectoires à partir de dimensions configurées.

## PR 5 — Visualisations génériques

Créer `FigureFactory` basée sur `visual_spec.yaml`.

## PR 6 — Vérification automatique des résultats

Créer `ResultValidator` et `validation_report.json`.

## PR 7 — Vérification automatique des visuels

Créer `VisualValidator` et `visual_report.json`.

## PR 8 — Documentation et exemples de cas

Documenter le workflow complet et ajouter un cas minimal de référence.
