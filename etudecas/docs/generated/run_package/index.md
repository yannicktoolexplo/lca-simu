# Intégrité et provenance des résultats

Document généré : modifier le registre et les sources, puis relancer le générateur.

Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.
Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.

## Règles métier

### PROVENANCE-SOURCE-001 — Diagnostiquer un écart sans accepter une nouvelle empreinte

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Le diagnostic compare les octets exacts à l'empreinte attendue. Pour une source UTF-8, il indique si CRLF explique seul l'écart. Seule une égalité exacte retourne un succès ; aucun fichier ni manifeste n'est modifié.

Périmètre : Diagnostic des sources figées, distinct du suivi documentaire AST.

Unités : Octets et SHA-256.

Limites : Une différence inexpliquée par les fins de ligne ne prouve pas une différence de comportement. L'origine et la fiabilité de l'empreinte fournie doivent être établies séparément.

Sources métier : [PROVENANCE.md](<../../PROVENANCE.md>)

Références :

- implementation : [diagnose_source_hash](<../../../provenance.py#L12>)
- implementation : [main](<../../../provenance.py#L34>)
- test : [SourceProvenanceTest](<../../../tests/commun/test_provenance.py#L13>)

### PROVENANCE-MONTECARLO-001 — Rattacher les incertitudes au run affiché

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Un résumé Monte Carlo partagé doit déclarer un manifeste du run cible et un horizon positif compatible. Parmi les candidats compatibles, davantage de runs réussis est prioritaire. Sans candidat compatible, le chemin local attendu est retourné, éventuellement absent.

Périmètre : Sélection du résumé Monte Carlo pour la carte du pipeline.

Unités : Jours simulés et nombre de runs réussis.

Limites : Le chemin du manifeste établit une association déclarée, pas une identité cryptographique du graphe, du moteur ou des paramètres. Un résumé local peut omettre le manifeste. Les sorties incompatibles explicites ou locales provoquent une erreur.

Sources métier : [PROVENANCE.md](<../../PROVENANCE.md>)

Références :

- implementation : [resolve_montecarlo_summary_for_map](<../../../run_etudecas_pipeline.py#L391>)
- implementation : [montecarlo_summary_matches_run](<../../../run_etudecas_pipeline.py#L480>)
- test : [test_shared_montecarlo_rejects_missing_incompatible_or_malformed_provenance](<../../../tests/commun/test_run_etudecas_pipeline.py#L255>)
- test : [test_montecarlo_summary_fallback_prefers_more_compatible_runs](<../../../tests/commun/test_run_etudecas_pipeline.py#L104>)

### PACKAGE-INTEGRITY-001 — Présence et lisibilité des résultats livrés

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Une déclaration de présence ne suffit pas : les fichiers indexés sont contrôlés physiquement, les CSV comparés à leurs colonnes et nombres de lignes, les JSON lus. Un échec de validation produit un code de sortie non nul en ligne de commande, y compris après export.

Périmètre : Packages génériques de simulation v1, fichiers stables pendant le contrôle.

Unités : Lignes CSV et octets JSON ; aucune conversion d'unité métier.

Limites : Lecture complète des fichiers. Ni preuve de provenance, ni vérification de chaque valeur métier ou de l'exhaustivité des résumés. Un changement conservant la structure peut rester indétectable.

Sources métier : [README.md](<../../../simulation/run_format/README.md>)

Références :

- implementation : [validate_run_package](<../../../simulation/run_format/validator.py#L84>)
- implementation : [_validate_artifact](<../../../simulation/run_format/validator.py#L36>)
- implementation : [_read_json](<../../../simulation/run_format/validator.py#L13>)
- implementation : [_load_checked](<../../../simulation/run_format/validator.py#L24>)
- implementation : [main](<../../../simulation/run_format/cli.py#L18>)
- test : [RunFormatIntegrityTest](<../../../tests/commun/test_run_format.py#L396>)

### PACKAGE-TRACE-001 — Traçabilité obligatoire et cohérence des index

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Les trois CSV obligatoires du schéma doivent être présents. Les CSV de lots vides ne sont acceptés que lorsque la traçabilité est explicitement désactivée. Les index par groupe correspondent à l'index principal et les flux référencent les nœuds du package.

Périmètre : Structure des résultats quotidiens et des traces de lots.

Unités : Identifiants de nœuds et de flux ; nombres de lignes.

Limites : Ne vérifie pas les jointures entre fichiers de lots, la conservation des quantités ni l'exactitude des KPI. Les KPI vides restent acceptés.

Sources métier : [README.md](<../../../simulation/run_format/README.md>)

Références :

- implementation : [validate_run_package](<../../../simulation/run_format/validator.py#L84>)
- contract : [CANONICAL_DATA_ARTIFACTS](<../../../simulation/run_format/schema.py#L25>)
- test : [RunFormatIntegrityTest](<../../../tests/commun/test_run_format.py#L396>)
- test : [RunFormatExportTest.test_validate_run_package_allows_empty_lot_artifacts_when_lot_trace_disabled](<../../../tests/commun/test_run_format.py#L588>)

## Référence technique extraite

Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.

### mc-resolver

[etudecas/run_etudecas_pipeline.py:391](<../../../run_etudecas_pipeline.py#L391>)

```python
def resolve_montecarlo_summary_for_map(output_dir: Path, montecarlo_summary_json: Path | None=None, *, allow_shared_fallback: bool=True) -> Path:
```

Return the best Monte Carlo summary available for the map.

Explicit and run-local summaries take precedence. Shared summaries require
a manifest path pointing to the target run and a matching known horizon.
Among compatible shared summaries, prefer more successful runs, then newer
files. An incompatible explicit/local file raises instead of falling back.
If no candidate qualifies, return the expected local path, possibly absent.
Manifest paths establish association, not cryptographic provenance.

### mc-matcher

[etudecas/run_etudecas_pipeline.py:480](<../../../run_etudecas_pipeline.py#L480>)

```python
def montecarlo_summary_matches_run(summary_path: Path, *, target_days: int | None, target_manifest_candidates: list[Path], allow_missing_manifest: bool) -> bool:
```

Check declared run association and horizon; reject malformed metadata.

### mc-rejection-test

[etudecas/tests/commun/test_run_etudecas_pipeline.py:255](<../../../tests/commun/test_run_etudecas_pipeline.py#L255>)

```python
def test_shared_montecarlo_rejects_missing_incompatible_or_malformed_provenance(tmp_path, monkeypatch, payload):
```

### mc-selection-test

[etudecas/tests/commun/test_run_etudecas_pipeline.py:104](<../../../tests/commun/test_run_etudecas_pipeline.py#L104>)

```python
def test_montecarlo_summary_fallback_prefers_more_compatible_runs(tmp_path, monkeypatch) -> None:
```

### source-diagnostic

[etudecas/provenance.py:12](<../../../provenance.py#L12>)

```python
def diagnose_source_hash(path: Path, expected_sha256: str) -> dict[str, object]:
```

Classify a mismatch without accepting it or changing the source file.

### source-diagnostic-cli

[etudecas/provenance.py:34](<../../../provenance.py#L34>)

```python
def main(argv: list[str] | None=None) -> int:
```

### source-diagnostic-tests

[etudecas/tests/commun/test_provenance.py:13](<../../../tests/commun/test_provenance.py#L13>)

```python
class SourceProvenanceTest
```

### package-validator

[etudecas/simulation/run_format/validator.py:84](<../../../simulation/run_format/validator.py#L84>)

```python
def validate_run_package(package_dir: Path | str) -> list[dict[str, Any]]:
```

Validate package structure and physical artifacts, not simulation accuracy.

### artifact-validator

[etudecas/simulation/run_format/validator.py:36](<../../../simulation/run_format/validator.py#L36>)

```python
def _validate_artifact(row: dict[str, Any], output: Path, validations: list[dict[str, Any]]) -> int | None:
```

Check the physical file; stream CSV data without retaining its rows.

### json-reader

[etudecas/simulation/run_format/validator.py:13](<../../../simulation/run_format/validator.py#L13>)

```python
def _read_json(path: Path) -> Any:
```

### checked-loader

[etudecas/simulation/run_format/validator.py:24](<../../../simulation/run_format/validator.py#L24>)

```python
def _load_checked(path: Path, expected: type, validations: list[dict[str, Any]], name: str) -> Any:
```

### package-cli

[etudecas/simulation/run_format/cli.py:18](<../../../simulation/run_format/cli.py#L18>)

```python
def main() -> None:
```

### canonical-artifacts

[etudecas/simulation/run_format/schema.py:25](<../../../simulation/run_format/schema.py#L25>)

```python
CANONICAL_DATA_ARTIFACTS: tuple[ArtifactSpec, ...] = (ArtifactSpec('first_simulation_daily.csv', 'timeseries', 'global_kpi', 'day', True), ArtifactSpec('production_demand_service_daily.csv', 'timeseries', 'customer_service', 'day_node_item'), ArtifactSpec('production_output_products_daily.csv', 'timeseries', 'production_output', 'day_node_item'), ArtifactSpec('production_input_stocks_daily.csv', 'timeseries', 'factory_input_stock', 'day_node_item'), ArtifactSpec('component_immobilized_stock_daily.csv', 'timeseries', 'component_immobilized_stock', 'day_node_product'), ArtifactSpec('component_immobilized_stock_components_daily.csv', 'timeseries', 'component_immobilized_stock_component', 'day_node_product_item'), ArtifactSpec('component_immobilized_stock_summary.csv', 'diagnostics', 'component_immobilized_stock_summary', 'node_product_item'), ArtifactSpec('finished_goods_stock_value_daily.csv', 'timeseries', 'finished_goods_stock_value', 'day_node_product'), ArtifactSpec('finished_goods_stock_value_summary.csv', 'diagnostics', 'finished_goods_stock_value_summary', 'product_location'), ArtifactSpec('production_input_consumption_daily.csv', 'timeseries', 'factory_input_consumption', 'day_node_item'), ArtifactSpec('production_input_replenishment_arrivals_daily.csv', 'timeseries', 'factory_input_arrivals', 'day_node_item'), ArtifactSpec('production_input_replenishment_shipments_daily.csv', 'timeseries', 'factory_input_shipments', 'day_node_item'), ArtifactSpec('production_dc_stocks_daily.csv', 'timeseries', 'distribution_stock', 'day_node_item'), ArtifactSpec('production_supplier_stocks_daily.csv', 'timeseries', 'supplier_stock', 'day_node_item'), ArtifactSpec('production_supplier_stock_flows_daily.csv', 'timeseries', 'supplier_stock_flow', 'day_node_item'), ArtifactSpec('production_supplier_shipments_daily.csv', 'timeseries', 'supplier_shipments', 'day_node_item'), ArtifactSpec('production_supplier_capacity_daily.csv', 'timeseries', 'supplier_capacity', 'day_node_item'), ArtifactSpec('production_constraint_daily.csv', 'timeseries', 'production_constraint', 'day_node_item'), ArtifactSpec('mrp_trace_daily.csv', 'events', 'mrp_trace', 'day_node_item'), ArtifactSpec('mrp_orders_daily.csv', 'events', 'mrp_orders', 'day_node_item'), ArtifactSpec('opening_production_order_component_consumption.csv', 'events', 'opening_production_component_issue', 'day_node_item'), ArtifactSpec('production_plan_events.csv', 'events', 'production_plan', 'event'), ArtifactSpec('production_campaigns.csv', 'events', 'production_campaigns', 'campaign'), ArtifactSpec('production_factory_nervousness.csv', 'diagnostics', 'factory_nervousness', 'node_item'), ArtifactSpec('production_lot_events.csv', 'lots', 'lot_events', 'event', True), ArtifactSpec('production_lot_genealogy.csv', 'lots', 'lot_genealogy', 'genealogy', True), ArtifactSpec('lot_causal_links.csv', 'lots', 'lot_causal_links', 'causal_relation'), ArtifactSpec('lot_path_audit_issues.csv', 'diagnostics', 'lot_path_audit', 'issue'), ArtifactSpec('supplier_risk_events_applied_daily.csv', 'events', 'supplier_risk_applied', 'day_node_item'), ArtifactSpec('supplier_state_dependent_risk_events.csv', 'events', 'supplier_risk_configured', 'event'), ArtifactSpec('supplier_local_criticality_ranking.csv', 'diagnostics', 'supplier_local_criticality', 'node_item'), ArtifactSpec('supplier_nominal_parameters.csv', 'diagnostics', 'supplier_nominal_parameters', 'node_item'), ArtifactSpec('production_capacity_nominal_parameters.csv', 'diagnostics', 'factory_nominal_capacities', 'node_process'), ArtifactSpec('initialization_state.csv', 'diagnostics', 'initialization_state', 'run'), ArtifactSpec('initialization_observed_stock.csv', 'diagnostics', 'initialization_observed_stock', 'node_item'), ArtifactSpec('initialization_pipeline.csv', 'diagnostics', 'initialization_pipeline', 'lane_item'), ArtifactSpec('assumptions_ledger.csv', 'diagnostics', 'assumptions_ledger', 'assumption'), ArtifactSpec('physics_of_decision_kpi_daily.csv', 'timeseries', 'decision_physics', 'day'))
```

### integrity-tests

[etudecas/tests/commun/test_run_format.py:396](<../../../tests/commun/test_run_format.py#L396>)

```python
class RunFormatIntegrityTest
```

### disabled-lots-test

[etudecas/tests/commun/test_run_format.py:588](<../../../tests/commun/test_run_format.py#L588>)

```python
def test_validate_run_package_allows_empty_lot_artifacts_when_lot_trace_disabled(self) -> None:
```
