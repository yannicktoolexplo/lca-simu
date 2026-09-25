# Execution physique et verification independante

Document généré : modifier le registre et les sources, puis relancer le générateur.

Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.
Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.

## Règles métier

### PHYSICAL-001 — Unites physiques entieres

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

La demande previsionnelle fractionnaire reste dans le reliquat ; les mouvements en UN sont entiers avant mise a jour simultanee du stock et du registre.

Périmètre : Moteur canonique et nouvelles livraisons ; aucune requalification automatique des campagnes historiques.

Unités : UN entieres ; masses et longueurs non arrondies

Limites : Les tests logiciels ne certifient ni les sources metier ni la calibration. Voir le guide pour les hypotheses ouvertes.

Sources métier : [EXECUTION_VERIFICATION.md](<../../EXECUTION_VERIFICATION.md>)

Références :

- implementation : [physical_execution_quantity](<../../../simulation/engine/run_first_simulation.py#L1903>)
- implementation : [require_physical_integer](<../../../simulation/engine/run_first_simulation.py#L1891>)
- test : [test_fractional_forecast_accumulates_without_losing_demand](<../../../testing/test_independent_review.py#L158>)

### INPUT-REJECTION-001 — Refus des entrees invalides

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Les requetes natives sont revalidees et les facteurs inconnus refuses avant execution.

Périmètre : Moteur canonique et nouvelles livraisons ; aucune requalification automatique des campagnes historiques.

Unités : Types, noms et multiplicateurs

Limites : Les tests logiciels ne certifient ni les sources metier ni la calibration. Voir le guide pour les hypotheses ouvertes.

Sources métier : [EXECUTION_VERIFICATION.md](<../../EXECUTION_VERIFICATION.md>)

Références :

- implementation : [simulate](<../../../simulation/engine/api.py#L292>)
- implementation : [validate_factors](<../../../simulation/analysis_batch_common.py#L309>)
- test : [test_invalid_sensitivity_cannot_be_recorded_as_applied](<../../../testing/test_independent_review.py#L197>)

### TRACE-SELECTION-001 — Selection causale commune

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Tous les lots selectionnables partagent le meme calcul Python des evenements et contributions ; le HTML utilise des liens mutualises. Le navigateur rapproche le lot PBATCH des contributions reçues dans les CSV du calcul explicitement fourni, sans imposer une découpe historique à un nouveau scénario.

Périmètre : Moteur canonique et nouvelles livraisons ; aucune requalification automatique des campagnes historiques.

Unités : Occurrences, lots metier, quantites par article/unite

Limites : Les tests logiciels ne certifient ni les sources metier ni la calibration. Voir le guide pour les hypotheses ouvertes.

Sources métier : [EXECUTION_VERIFICATION.md](<../../EXECUTION_VERIFICATION.md>)

Références :

- implementation : [build_lot_trace_view_model](<../../../simulation/lot_trace/view_model.py#L6>)
- implementation : [build_lot_trace_payload](<../../../simulation/lot_trace/payload.py#L42>)
- implementation : [review](<../../../testing/lot_browser_review.py#L40>)
- test : [LotTraceViewModelTest.test_view_model_excludes_events_outside_selected_contribution](<../../../tests/lots/test_lot_trace_view_model.py#L91>)
- implementation : [business_batch_csv_oracle](<../../../testing/lot_browser_review.py#L15>)
- test : [test_customer_oracle_uses_current_csv_split_and_excludes_future_receipts](<../../../testing/test_lot_journey.py#L621>)

### DELIVERY-PROOF-001 — Livraison sous controle independant

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Les invariants CSV sont recalcules sans importer le moteur. Une corruption ou preuve manquante refuse la livraison. Une empreinte identifie les octets sans prouver leur justesse.

Périmètre : Moteur canonique et nouvelles livraisons ; aucune requalification automatique des campagnes historiques.

Unités : Bilans quotidiens ; quantites ; couts ; empreintes

Limites : Les tests logiciels ne certifient ni les sources metier ni la calibration. Voir le guide pour les hypotheses ouvertes.

Sources métier : [EXECUTION_VERIFICATION.md](<../../EXECUTION_VERIFICATION.md>)

Références :

- implementation : [audit_run](<../../../testing/independent_review.py#L92>)
- implementation : [require_run_invariants](<../../../testing/qualification.py#L20>)
- test : [test_delivery_gate_refuses_corrupt_stock_and_missing_evidence](<../../../testing/test_independent_review.py#L214>)
- implementation : [implementation_fingerprint](<../../../simulation/source_fingerprint.py#L20>)

### TRUCK-ESTIMATE-001 — Lots and estimated truck consolidation

Statut déclaré : **hypothesis**. Relecture des sources : **aucun changement détecté**.

A production lot, purchase order, pallet and truck are distinct identities. Group complete compatible route/week flows; estimates by packaging analogy remain distinct from physically dimensioned truck loads.

Périmètre : Lot diagram, no rescheduling or simulation stock changes.

Unités : UN, pallets, loaded kg, trucks

Limites : Unknown gross weights and borrowed packaging remain explicit hypotheses; no certified loading for incomplete profiles.

Sources métier : [LOTS_ET_CAMIONS.md](<../../LOTS_ET_CAMIONS.md>), [data_poc.json](<../../../config/cases/data_poc.json>)

Références :

- implementation : [build_transport_context](<../../../simulation/logistics/io.py#L269>)
- test : [test_four_shipments_are_three_weekly_groups_not_four_trucks](<../../../tests/lots/test_logistics.py#L39>)
- test : [test_sourced_profile_can_dimension_real_capacity_proposals](<../../../tests/lots/test_logistics.py#L60>)

### COST-EXPORT-ROUNDING-001 — Rapprochement des couts exportes arrondis

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Export a 4 decimales. Operationnel: cinq postes journaliers deja arrondis plus dernier arrondi avec production brute, puis arrondi du resume, soit (6*N+1)*0.00005. Externe: deux colonnes journalieres plus resume, soit (2*N+1)*0.00005. Calcul Decimal, precision et unicite des jours verifies.

Périmètre : Verification de livraison HTML/CSV uniquement; aucune modification des montants simules.

Unités : Unite monetaire du modele, N jours executes

Limites : Un ecart inferieur a la borne est compatible avec les arrondis, sans preuve de sa cause. Une precision ou formule export modifiee impose une revue. Les prix inconnus restent inconnus.

Sources métier : [2026-09-20-cost-rounding-README.md](<../../changes/2026-09-20-cost-rounding-README.md>)

Références :

- implementation : [reconcile_exported_cost](<../../../testing/map_delivery.py#L83>)
- implementation : [reconcile_browser](<../../../testing/map_delivery.py#L111>)
- test : [test_cost_rounding_bound_accepts_only_mathematically_possible_error](<../../../testing/test_independent_review.py#L337>)
- test : [test_long_horizon_rounding_accepts_accumulation_but_rejects_one_currency_unit](<../../../testing/test_independent_review.py#L344>)
- test : [test_unexpected_cost_export_precision_is_not_silently_tolerated](<../../../testing/test_independent_review.py#L356>)
- test : [test_browser_values_are_reconciled_with_runs](<../../../testing/test_independent_review.py#L287>)

## Référence technique extraite

Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.

### physical

[etudecas/simulation/engine/run_first_simulation.py:1903](<../../../simulation/engine/run_first_simulation.py#L1903>)

```python
def physical_execution_quantity(value: Any, uom: Any) -> float:
```

Execute only whole countable units; retain forecast residuals upstream.

Round down at a physical boundary, before updating stock AND its ledger.
Mass and length retain their precision. This never rounds display values.

### ledger-guard

[etudecas/simulation/engine/run_first_simulation.py:1891](<../../../simulation/engine/run_first_simulation.py#L1891>)

```python
def require_physical_integer(value: Any, uom: Any) -> float:
```

Ledger guard: a physical boundary must quantize before recording it.

### native-request

[etudecas/simulation/engine/api.py:292](<../../../simulation/engine/api.py#L292>)

```python
def simulate(request: SimulationRequest, *, run_executor=None) -> SimulationResult:
```

Run one simulation from structured inputs and return structured outputs.

### factor-contract

[etudecas/simulation/analysis_batch_common.py:309](<../../../simulation/analysis_batch_common.py#L309>)

```python
def validate_factors(factors: dict[str, float]) -> None:
```

### view-contract

[etudecas/simulation/lot_trace/view_model.py:6](<../../../simulation/lot_trace/view_model.py#L6>)

```python
def build_lot_trace_view_model(payload: dict[str, Any], lot_id: str, direction: str='all', indexes: LotTraceIndexes | None=None) -> dict[str, Any]:
```

### view-payload

[etudecas/simulation/lot_trace/payload.py:42](<../../../simulation/lot_trace/payload.py#L42>)

```python
def build_lot_trace_payload(lot_events_csv: Path, lot_genealogy_csv: Path, production_plan_events_csv: Path, raw: dict[str, Any] | None=None, input_stocks_csv: Path | None=None, output_products_csv: Path | None=None, dc_stocks_csv: Path | None=None, demand_service_csv: Path | None=None, supplier_stocks_csv: Path | None=None, visible_finished_product_items: Iterable[str] | None=None, production_campaigns_csv: Path | None=None, mrp_orders_csv: Path | None=None, lot_causal_links_csv: Path | None=None, include_causal_links: bool=True, material_traceability_json: Path | None=None) -> dict[str, Any]:
```

### csv-oracle

[etudecas/testing/independent_review.py:92](<../../../testing/independent_review.py#L92>)

```python
def audit_run(run):
```

### delivery-gate

[etudecas/testing/qualification.py:20](<../../../testing/qualification.py#L20>)

```python
def require_run_invariants(run: Path) -> dict:
```

### browser-proof

[etudecas/testing/lot_browser_review.py:40](<../../../testing/lot_browser_review.py#L40>)

```python
def review(html, output, source_run=None):
```

### cache-sources

[etudecas/simulation/source_fingerprint.py:20](<../../../simulation/source_fingerprint.py#L20>)

```python
def implementation_fingerprint(run_script: Path) -> str:
```

### known-demand

[etudecas/testing/test_independent_review.py:158](<../../../testing/test_independent_review.py#L158>)

```python
def test_fractional_forecast_accumulates_without_losing_demand():
```

### corruption

[etudecas/testing/test_independent_review.py:214](<../../../testing/test_independent_review.py#L214>)

```python
def test_delivery_gate_refuses_corrupt_stock_and_missing_evidence(known_run):
```

### bad-factor-test

[etudecas/testing/test_independent_review.py:197](<../../../testing/test_independent_review.py#L197>)

```python
def test_invalid_sensitivity_cannot_be_recorded_as_applied(factors):
```

### causal-test

[etudecas/tests/lots/test_lot_trace_view_model.py:91](<../../../tests/lots/test_lot_trace_view_model.py#L91>)

```python
def test_view_model_excludes_events_outside_selected_contribution(self) -> None:
```

### truck-context

[etudecas/simulation/logistics/io.py:269](<../../../simulation/logistics/io.py#L269>)

```python
def build_transport_context(events, graph, profiles=()):
```

### truck-groups-test

[etudecas/tests/lots/test_logistics.py:39](<../../../tests/lots/test_logistics.py#L39>)

```python
def test_four_shipments_are_three_weekly_groups_not_four_trucks():
```

### truck-capacity-test

[etudecas/tests/lots/test_logistics.py:60](<../../../tests/lots/test_logistics.py#L60>)

```python
def test_sourced_profile_can_dimension_real_capacity_proposals():
```

### customer-csv-oracle

[etudecas/testing/lot_browser_review.py:15](<../../../testing/lot_browser_review.py#L15>)

```python
def business_batch_csv_oracle(run, batch_id):
```

Read the supplied run's physical customer contributions, never a historical split.

### customer-csv-oracle-test

[etudecas/testing/test_lot_journey.py:621](<../../../testing/test_lot_journey.py#L621>)

```python
def test_customer_oracle_uses_current_csv_split_and_excludes_future_receipts(tmp_path):
```

### cost-rounding

[etudecas/testing/map_delivery.py:83](<../../../testing/map_delivery.py#L83>)

```python
def reconcile_exported_cost(values: list[str], summary_total: float, *, rounding_terms_per_value: int) -> dict:
```

Bound export rounding, without a relative or arbitrary money tolerance.

The engine exports monetary columns and summary totals to four decimals.
total_supply_cost_day combines five already-rounded costs and rounds its
sum with raw production cost once more: six rounding terms per daily value.
Each external purchase/transport column has just one rounding term.
A final half-quantum covers the independently rounded summary total.
See run_first_simulation.py daily_rows, total_supply_cost_day and kpis.

### cost-browser

[etudecas/testing/map_delivery.py:111](<../../../testing/map_delivery.py#L111>)

```python
def reconcile_browser(browser: dict, runs: list[dict], *, cost_checks: list | None=None) -> list[str]:
```

Independent source oracle for browser values, monetary scopes and v3 score.

Do not import a map producer: summaries and daily CSVs are read directly.
The score is checked against those quantities, not another payload score.

### cost-rounding-bound-test

[etudecas/testing/test_independent_review.py:337](<../../../testing/test_independent_review.py#L337>)

```python
def test_cost_rounding_bound_accepts_only_mathematically_possible_error(daily_terms, summary, expected):
```

### cost-rounding-long-test

[etudecas/testing/test_independent_review.py:344](<../../../testing/test_independent_review.py#L344>)

```python
def test_long_horizon_rounding_accepts_accumulation_but_rejects_one_currency_unit():
```

### cost-rounding-precision-test

[etudecas/testing/test_independent_review.py:356](<../../../testing/test_independent_review.py#L356>)

```python
def test_unexpected_cost_export_precision_is_not_silently_tolerated(value):
```

### cost-browser-test

[etudecas/testing/test_independent_review.py:287](<../../../testing/test_independent_review.py#L287>)

```python
def test_browser_values_are_reconciled_with_runs(run, damage):
```
