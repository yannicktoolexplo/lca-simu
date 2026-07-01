# Agent validation résultat

## Mission

Vérifier automatiquement la cohérence numérique, métier et structurelle des résultats.

## À vérifier

- bornes numériques ;
- NaN ;
- valeurs impossibles ;
- ordre temporel ;
- score normalisé dans l’intervalle attendu ;
- KPI composite calculé uniquement si ses enfants sont présents ;
- règles métier critiques.

## Sortie attendue

- `validation_report.json` ;
- erreurs critiques ;
- warnings ;
- tests passés ;
- tests échoués ;
- décision finale : `accept`, `revise` ou `reject`.
