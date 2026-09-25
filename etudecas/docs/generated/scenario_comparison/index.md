# Comparaison descriptive des scenarios

Document généré : modifier le registre et les sources, puis relancer le générateur.

Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.
Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.

## Règles métier

### SCENARIO-COMPARE-001 — Score descriptif et ecarts signes

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Le score customer_cost_v3_valuation_guard retient 5 fois la perte de service et 3 fois le ratio de reliquat. Le poids 0,25 du surcout operationnel est inclus seulement si les deux valorisations sont completes ; sinon cost_delta_pct est null. Les pertes et reports sans unite commune sont exclus. Les ecarts restent signes ; un service nul reste nul.

Périmètre : Comparaison des runs dans la carte HTML.

Unités : Score sans unite probabiliste ; service en points ; couts et quantites dans les unites du modele.

Limites : Coefficients non calibres ; aucune conversion physique entre articles. Les dimensions exclues sont indisponibles, pas nulles physiquement. Demande et cout de reference bornes a 1. Le score monetise l'operationnel ; le classement economique compare l'exposition operationnel + approvisionnement externe seulement si tous les scenarios sont valorises completement.

Sources métier : [SCENARIO_COMPARISON.md](<../../SCENARIO_COMPARISON.md>)

Références :

- implementation : [compute_observed_impact](<../../../visualization/maps/scenario_comparison_payload.py#L87>)
- implementation : [build_scenario_comparison_payload](<../../../visualization/maps/scenario_comparison_payload.py#L135>)
- test : [ScenarioComparisonPayloadTest.test_observed_score_and_signed_deltas](<../../../tests/cartes/test_scenario_comparison_payload.py#L15>)
- test : [ScenarioComparisonPayloadTest.test_zero_service_is_total_service_loss](<../../../tests/cartes/test_scenario_comparison_payload.py#L34>)
- test : [ScenarioComparisonPayloadTest.test_current_run_with_companion_ignores_stale_compact](<../../../tests/cartes/test_scenario_comparison_payload.py#L64>)
- implementation : [economic_cost_view](<../../../visualization/maps/simulation_payload.py#L835>)
- test : [SemanticGuardTests.test_unknown_or_incomplete_value_cannot_affect_cost_ranking_or_score](<../../../tests/cartes/test_audit_payload_contracts.py#L137>)

### SCENARIO-COMPARE-002 — Lecture metier et restitution navigateur

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Le score affiche suit le classement observe. Le service cumule inclut les rattrapages. Le comparatif conserve les reliquats >1e-9 ; la fiche client separe les fractions previsionnelles du retard physique >=1 UN par article. Les enveloppes sont descriptives. Une association temporelle et topologique ne prouve ni perte client ni cout attribue a un evenement. Le rapprochement CSV/resume utilise la borne des arrondis a 4 decimales : (6*N+1)*0.00005 pour l'operationnel, (2*N+1)*0.00005 pour l'externe, avec N jours uniques ; aucune tolerance monetaire relative arbitraire.

Périmètre : Payload, lecture metier et revue manuelle automatisee Chromium.

Unités : Service cumule ; enveloppes descriptives.

Limites : La revue navigateur requiert Playwright et Chromium et ne valide pas scientifiquement le modele. Le HTML JavaScript est couvert par cette revue, pas par une empreinte AST JavaScript.

Sources métier : [SCENARIO_COMPARISON.md](<../../SCENARIO_COMPARISON.md>), [2026-09-20-cost-rounding-README.md](<../../changes/2026-09-20-cost-rounding-README.md>)

Références :

- implementation : [build_scenario_comparison_payload](<../../../visualization/maps/scenario_comparison_payload.py#L135>)
- test : [ScenarioComparisonPayloadTest.test_current_run_with_companion_ignores_stale_compact](<../../../tests/cartes/test_scenario_comparison_payload.py#L64>)
- implementation : [review_map](<../../../testing/map_browser.py#L16>)
- implementation : [reconcile_browser](<../../../testing/map_delivery.py#L111>)
- test : [test_browser_values_are_reconciled_with_runs](<../../../testing/test_independent_review.py#L287>)
- test : [SemanticGuardTests.test_preexisting_client_backlog_is_not_attributed_to_unapplied_event](<../../../tests/cartes/test_audit_payload_contracts.py#L226>)
- test : [SemanticGuardTests.test_fractional_residuals_are_not_whole_unit_backlog](<../../../tests/cartes/test_audit_payload_contracts.py#L177>)
- test : [test_complete_cost_scopes_use_independent_csv_and_operating_score](<../../../testing/test_independent_review.py#L362>)

## Référence technique extraite

Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.

### score

[etudecas/visualization/maps/scenario_comparison_payload.py:87](<../../../visualization/maps/scenario_comparison_payload.py#L87>)

```python
def compute_observed_impact(kpis: dict[str, Any], base_kpis: dict[str, Any]) -> dict[str, float | str]:
```

Descriptive weighted impact, not a probability or calibrated decision score.

### payload

[etudecas/visualization/maps/scenario_comparison_payload.py:135](<../../../visualization/maps/scenario_comparison_payload.py#L135>)

```python
def build_scenario_comparison_payload(current_output_root: Path) -> dict[str, Any]:
```

### score-test

[etudecas/tests/cartes/test_scenario_comparison_payload.py:15](<../../../tests/cartes/test_scenario_comparison_payload.py#L15>)

```python
def test_observed_score_and_signed_deltas(self) -> None:
```

### zero-test

[etudecas/tests/cartes/test_scenario_comparison_payload.py:34](<../../../tests/cartes/test_scenario_comparison_payload.py#L34>)

```python
def test_zero_service_is_total_service_loss(self) -> None:
```

### payload-test

[etudecas/tests/cartes/test_scenario_comparison_payload.py:64](<../../../tests/cartes/test_scenario_comparison_payload.py#L64>)

```python
def test_current_run_with_companion_ignores_stale_compact(self) -> None:
```

### browser

[etudecas/testing/map_browser.py:16](<../../../testing/map_browser.py#L16>)

```python
def review_map(html: Path, output: Path) -> dict:
```

### html-csv

[etudecas/testing/map_delivery.py:111](<../../../testing/map_delivery.py#L111>)

```python
def reconcile_browser(browser: dict, runs: list[dict], *, cost_checks: list | None=None) -> list[str]:
```

Independent source oracle for browser values, monetary scopes and v3 score.

Do not import a map producer: summaries and daily CSVs are read directly.
The score is checked against those quantities, not another payload score.

### html-csv-test

[etudecas/testing/test_independent_review.py:287](<../../../testing/test_independent_review.py#L287>)

```python
def test_browser_values_are_reconciled_with_runs(run, damage):
```

### valuation

[etudecas/visualization/maps/simulation_payload.py:835](<../../../visualization/maps/simulation_payload.py#L835>)

```python
def economic_cost_view(summary: dict[str, Any]) -> dict[str, Any]:
```

### valuation-test

[etudecas/tests/cartes/test_audit_payload_contracts.py:137](<../../../tests/cartes/test_audit_payload_contracts.py#L137>)

```python
def test_unknown_or_incomplete_value_cannot_affect_cost_ranking_or_score(self):
```

### association-test

[etudecas/tests/cartes/test_audit_payload_contracts.py:226](<../../../tests/cartes/test_audit_payload_contracts.py#L226>)

```python
def test_preexisting_client_backlog_is_not_attributed_to_unapplied_event(self):
```

### backlog-test

[etudecas/tests/cartes/test_audit_payload_contracts.py:177](<../../../tests/cartes/test_audit_payload_contracts.py#L177>)

```python
def test_fractional_residuals_are_not_whole_unit_backlog(self):
```

### cost-scope-oracle-test

[etudecas/testing/test_independent_review.py:362](<../../../testing/test_independent_review.py#L362>)

```python
def test_complete_cost_scopes_use_independent_csv_and_operating_score(run, damage):
```
