# Insights - Plan d'experiences cible (15 scenarios, 30 jours)

Source resultats:
- `etudecas/simulation/sensibility/targeted_plan_result/scenario_results.csv`
- `etudecas/simulation/sensibility/targeted_plan_result/scenario_delta_vs_baseline.csv`
- `etudecas/simulation/sensibility/targeted_plan_result/experiment_plan_report.md`

## Baseline (reference)
- Fill rate: `0.733333`
- Cost total: `7392.8060`
- Ending backlog: `400.0`
- Cost split:
  - Holding: `6526.9631`
  - Transport: `121.8`
  - Purchase: `744.0429`

## 1) Levier service le plus efficace (dans ce plan)
- Scenario `resilience_combo`:
  - Fill rate: `0.806667` (mieux)
  - Backlog: `290.0` (mieux)
  - Cost total: `8627.8196` (plus cher)

Lecture:
- Gain service/backlog clair, avec un surcout.

## 2) Levier cout le plus fort (mais service degrade)
- Scenario `review_period_7d`:
  - Cost total: `9073.7522`
  - Fill rate: `0.266667`
  - Backlog: `1100.0`

Lecture:
- La revue hebdomadaire degrade fortement le service et le backlog sur 30 jours.

## 3) Risque fournisseur
- `supplier_reliability_95`:
  - Fill rate: `0.659458`
  - Backlog: `510.8125`
  - `total_unreliable_loss_qty`: `3188.7383`
- `supplier_reliability_85`:
  - Fill rate: `0.523458`
  - Backlog: `714.8123`
  - `total_unreliable_loss_qty`: `10456.3276`

Lecture:
- La fiabilite fournisseur reste un driver critique du service.

## 4) Sensibilite lead time
- `lead_time_plus_20pct`:
  - Fill rate: `0.666667`
  - Backlog: `500.0`
- `lead_time_plus_40pct`:
  - Fill rate: `0.566667`
  - Backlog: `650.0`

Lecture:
- Degradation monotone du service quand le lead time augmente.

## 5) Stress combine (pire cas)
- `stress_combo`:
  - Fill rate: `0.326958`
  - Backlog: `1259.9355`
  - Cost total: `8674.3617`
  - `total_unreliable_loss_qty`: `9451.8413`

Lecture:
- Vulnérabilite forte aux chocs combines demande + delai + fiabilite + capacite.

## 6) Safety stock dans cet horizon
- `safety_stock_low` et `safety_stock_high` sont identiques a baseline.

Interpretation:
- Dans ce modele 30 jours, ce levier reste non actif comparativement aux autres contraintes.

## 7) Decision guide
1. Prioriser reduction lead time et fiabilite fournisseur.
2. Utiliser `resilience_combo` si l'objectif prioritaire est le service.
3. Eviter les politiques de revue trop espacees (type 7 jours) sur ce systeme.
