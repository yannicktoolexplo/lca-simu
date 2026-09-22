# Expéditions, lots et exposition aux risques

Document généré : modifier le registre et les sources, puis relancer le générateur.

Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.
Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.

## Règles métier

### TRACE-SHIPMENT-001 — Identité partagée entre expédition et lots

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Chaque transaction du planning fournisseur (un article et un chunk de livraison) conserve son shipment_id depuis le CSV fournisseur jusqu’aux événements physiques et à la généalogie. Plusieurs lots sources peuvent contribuer à cette transaction. Des articles ou chunks partageant route et dates restent distincts. Une identité présente mais différente ne doit pas être remplacée silencieusement par un rapprochement temporel.

Périmètre : Identité de transaction unique dans un run, portée par le CSV fournisseur, les réservations, départs, réceptions et commandes MRP. Elle ne constitue pas une preuve de véhicule ou de chargement consolidé.

Unités : Identifiants textuels ; quantités accompagnées de leur unité article.

Limites : La rupture SHIP-*/SHP-* constatée dans l’audit a été corrigée et les scénarios courts mono-article et multi-articles vérifiés le 16 septembre 2026. Les anciens runs ne sont pas réécrits : ils peuvent conserver la rupture et doivent être régénérés pour cette preuve native. Les références aux tests ne remplacent pas leur exécution ; aucune validation métier externe n’est revendiquée.

Sources métier : [RISK_IMPACT_REGISTRY.md](<../../simulation/lot_trace/RISK_IMPACT_REGISTRY.md>)

Références :

- implementation : [main](<../../simulation/engine/run_first_simulation.py#L6869>)
- implementation : [_attach_shipment_trace_ids](<../../simulation/engine/run_first_simulation.py#L370>)
- implementation : [_allocate_source_lots](<../../simulation/lot_trace/risk_impact_registry.py#L1570>)
- test : [test_engine_smoke_emits_native_transaction_join_and_registry_counts_bundle_once](<../../simulation/test_risk_lot_impact_registry.py#L968>)
- contract : [LOT_TRACE_CONTRACT_VERSION](<../../simulation/lot_trace/io.py#L14>)
- implementation : [LotLedger.next_shipment_identity](<../../simulation/engine/run_first_simulation.py#L995>)
- test : [test_multi_chunk_schedule_has_one_unique_join_key_per_physical_chunk](<../../simulation/test_risk_lot_impact_registry.py#L950>)
- implementation : [build_lot_causal_link_rows](<../../simulation/lot_trace/causal_links.py#L178>)

### TRACE-TIME-001 — Jour de décision du risque distinct du mouvement physique

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

risk_decision_day conserve le jour où le risque a été appliqué, même si le départ, la libération ou la réception intervient plus tard. shipment_id et risk_event_ids transportent le contexte vers les lots.

Périmètre : Champs natifs des événements et de la généalogie des lots ; contrat initial documenté dans le registre de risques.

Unités : Jours du run ; identifiants d’incident et d’expédition.

Limites : La propagation effective doit être vérifiée par les tests et les artefacts du run, y compris pour les départs différés. Les anciens runs peuvent manquer du contexte de risque ou porter des identifiants incompatibles ; la correction ne modifie pas ces artefacts historiques.

Sources métier : [RISK_IMPACT_REGISTRY.md](<../../simulation/lot_trace/RISK_IMPACT_REGISTRY.md>)

Références :

- implementation : [main](<../../simulation/engine/run_first_simulation.py#L6869>)
- contract : [LOT_TRACE_EVENT_FIELDS](<../../simulation/lot_trace/io.py#L15>)
- contract : [LOT_TRACE_GENEALOGY_FIELDS](<../../simulation/lot_trace/io.py#L45>)
- test : [test_engine_lot_ledger_carries_native_risk_context_through_receipt_genealogy](<../../simulation/test_risk_lot_impact_registry.py#L899>)
- implementation : [LotLedger.record_allocation_event](<../../simulation/engine/run_first_simulation.py#L1907>)
- test : [test_reserved_shipment_retains_risk_decision_on_later_physical_departure](<../../simulation/test_risk_lot_impact_registry.py#L1107>)

### RISK-BUNDLE-001 — Ne compter une expédition exposée qu’une fois

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Plusieurs incidents peuvent viser la même expédition physique. Le bundle est l’unité d’exposition à sommer ; la table de liaison incidents/bundles ne doit pas multiplier la quantité physique.

Périmètre : Exposition des expéditions aux incidents simultanés ou superposés.

Unités : Quantités par article et unité ; nombre de bundles distincts.

Limites : Les sommes par incident ne sont pas nécessairement additives entre incidents. La qualité du rapprochement expédition/lot reste à contrôler.

Sources métier : [RISK_IMPACT_REGISTRY.md](<../../simulation/lot_trace/RISK_IMPACT_REGISTRY.md>)

Références :

- implementation : [_build_exposure_bundles](<../../simulation/lot_trace/risk_impact_registry.py#L1406>)
- test : [test_overlapping_events_share_one_bundle_and_must_not_be_summed](<../../simulation/test_risk_lot_impact_registry.py#L616>)
- contract : [OUTPUT_FILENAMES](<../../simulation/lot_trace/risk_impact_registry.py#L67>)

### RISK-UNITS-001 — Bornes d’exposition des lots issus de plusieurs composants

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Ne pas additionner des quantités de composants d’unités incompatibles. Pour un lot produit à partir de plusieurs composants exposés, utiliser une borne basse égale à la fraction maximale et une borne haute égale à la somme des fractions plafonnée à un.

Périmètre : Propagation dans la généalogie de production, avec fractions calculées par composant.

Unités : Quantités dans leurs unités propres ; fractions adimensionnelles entre 0 et 1.

Limites : Ces bornes ne décrivent pas le mélange microscopique réel. Un intervalle ne doit pas être remplacé par une valeur ponctuelle sans hypothèse supplémentaire.

Sources métier : [RISK_IMPACT_REGISTRY.md](<../../simulation/lot_trace/RISK_IMPACT_REGISTRY.md>)

Références :

- implementation : [_derive_child_impact](<../../simulation/lot_trace/risk_impact_registry.py#L1993>)
- test : [test_component_merge_uses_union_bounds_instead_of_adding_incompatible_units](<../../simulation/test_risk_lot_impact_registry.py#L633>)
- contract : [LOT_TRACE_GENEALOGY_FIELDS](<../../simulation/lot_trace/io.py#L45>)

### RISK-PROOF-001 — Exposition physique distincte de l’effet causal sur le service

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Tracer la matière exposée jusqu’au client démontre une exposition dans le modèle. Cela ne démontre pas que l’incident a causé une perte de service ou un surcoût : cette conclusion nécessite un contrefactuel apparié. Une association historique reconstruite doit être distinguée d’un lien natif.

Périmètre : Interprétation du registre de risques, des lots servis et des coûts de transactions exposées.

Unités : Quantités servies par unité ; coûts des transactions selon les unités monétaires du run, distincts d’un surcoût causal.

Limites : Aucune validation métier externe ni causalité réelle n’est inférée par ce registre documentaire. Les tests liés sont des vérifications logicielles.

Sources métier : [RISK_IMPACT_REGISTRY.md](<../../simulation/lot_trace/RISK_IMPACT_REGISTRY.md>)

Références :

- implementation : [_client_service_rows](<../../simulation/lot_trace/risk_impact_registry.py#L2171>)
- test : [test_native_incident_propagates_to_campaign_client_and_cost_without_false_service_claim](<../../simulation/test_risk_lot_impact_registry.py#L552>)
- test : [test_legacy_run_is_explicitly_association_not_native_causality](<../../simulation/test_risk_lot_impact_registry.py#L598>)

### RISK-PROVENANCE-001 — Provenance des données effectivement analysées

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Le registre conserve chemins, empreintes et nombre de lignes des sources lues. Une campagne détectée impose une cohérence entre identité du run, manifeste et état initial ; les preuves absentes restent explicitement indisponibles.

Périmètre : Sources du registre et sorties CSV ; ancien run autonome ou run rattaché à une campagne.

Unités : SHA-256 des octets des artefacts, tailles en octets et nombres de lignes.

Limites : Ces empreintes d’artefacts restent exactes sur les octets. La normalisation AST de la documentation ne s’applique pas aux preuves de simulation. Une empreinte garantit une identité de contenu, pas sa justesse métier.

Sources métier : [RISK_IMPACT_REGISTRY.md](<../../simulation/lot_trace/RISK_IMPACT_REGISTRY.md>)

Références :

- implementation : [_build_source_provenance](<../../simulation/lot_trace/risk_impact_registry.py#L974>)
- contract : [SOURCE_FILES](<../../simulation/lot_trace/risk_impact_registry.py#L38>)
- contract : [OUTPUT_FILENAMES](<../../simulation/lot_trace/risk_impact_registry.py#L67>)
- test : [test_standalone_directory_hashes_exact_sources_and_written_registry_csvs](<../../simulation/test_risk_lot_impact_registry.py#L779>)

## Référence technique extraite

Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.

### engine-day-loop

[etudecas/simulation/engine/run_first_simulation.py:6869](<../../simulation/engine/run_first_simulation.py#L6869>)

```python
def main() -> None:
```

### source-allocation

[etudecas/simulation/lot_trace/risk_impact_registry.py:1570](<../../simulation/lot_trace/risk_impact_registry.py#L1570>)

```python
def _allocate_source_lots(bundles: list[dict[str, Any]], lot_event_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
```

### shipment-chunks

[etudecas/simulation/engine/run_first_simulation.py:370](<../../simulation/engine/run_first_simulation.py#L370>)

```python
def _attach_shipment_trace_ids(delivery_schedule: list[tuple[int, float, float]], *, start_sequence: int, risk_event_ids: list[Any] | tuple[Any, ...]) -> tuple[list[tuple[int, float, float, str, str]], int]:
```

Attach one stable transaction ID to every physical delivery chunk.

### native-join-test

[etudecas/simulation/test_risk_lot_impact_registry.py:968](<../../simulation/test_risk_lot_impact_registry.py#L968>)

```python
def test_engine_smoke_emits_native_transaction_join_and_registry_counts_bundle_once(tmp_path: Path, risk_item: str) -> None:
```

### lot-event-fields

[etudecas/simulation/lot_trace/io.py:15](<../../simulation/lot_trace/io.py#L15>)

```python
LOT_TRACE_EVENT_FIELDS = ['event_id', 'day', 'event_type', 'lot_id', 'node_id', 'item_id', 'qty', 'qty_after', 'uom', 'source_type', 'source_id', 'shipment_id', 'risk_decision_day', 'risk_event_ids', 'related_lot_id', 'production_campaign_id', 'notes', 'business_batch_id', 'stock_lot_id', 'lot_occurrence_id', 'provenance_batch_id', 'departure_day', 'arrival_day', 'handling_unit_id', 'trace_status', 'trace_reason', 'lot_trace_contract_version', *LOT_CAUSAL_EVENT_FIELDS]
```

### genealogy-fields

[etudecas/simulation/lot_trace/io.py:45](<../../simulation/lot_trace/io.py#L45>)

```python
LOT_TRACE_GENEALOGY_FIELDS = ['day', 'link_type', 'parent_lot_id', 'parent_node_id', 'parent_item_id', 'child_lot_id', 'child_node_id', 'child_item_id', 'parent_qty', 'child_qty', 'allocation_share', 'source_id', 'shipment_id', 'risk_decision_day', 'risk_event_ids', 'production_campaign_id', 'notes', 'component_allocation_share', 'business_batch_id', 'stock_lot_id', 'lot_occurrence_id', 'parent_business_batch_id', 'parent_stock_lot_id', 'parent_lot_occurrence_id', 'child_business_batch_id', 'child_stock_lot_id', 'child_lot_occurrence_id', 'provenance_batch_id', 'departure_day', 'arrival_day', 'handling_unit_id', 'trace_status', 'trace_reason', 'lot_trace_contract_version', *LOT_CAUSAL_GENEALOGY_FIELDS]
```

### lot-contract-version

[etudecas/simulation/lot_trace/io.py:14](<../../simulation/lot_trace/io.py#L14>)

```python
LOT_TRACE_CONTRACT_VERSION = '3.0'
```

### risk-context-test

[etudecas/simulation/test_risk_lot_impact_registry.py:899](<../../simulation/test_risk_lot_impact_registry.py#L899>)

```python
def test_engine_lot_ledger_carries_native_risk_context_through_receipt_genealogy() -> None:
```

### exposure-bundles

[etudecas/simulation/lot_trace/risk_impact_registry.py:1406](<../../simulation/lot_trace/risk_impact_registry.py#L1406>)

```python
def _build_exposure_bundles(shipment_rows: list[dict[str, Any]], applied_rows: list[dict[str, Any]]) -> dict[str, Any]:
```

### overlap-test

[etudecas/simulation/test_risk_lot_impact_registry.py:616](<../../simulation/test_risk_lot_impact_registry.py#L616>)

```python
def test_overlapping_events_share_one_bundle_and_must_not_be_summed() -> None:
```

### component-union

[etudecas/simulation/lot_trace/risk_impact_registry.py:1993](<../../simulation/lot_trace/risk_impact_registry.py#L1993>)

```python
def _derive_child_impact(child: str, links: list[dict[str, Any]], impacts: dict[str, _LotImpact], lot_info: dict[str, dict[str, Any]]) -> _LotImpact | None:
```

### units-merge-test

[etudecas/simulation/test_risk_lot_impact_registry.py:633](<../../simulation/test_risk_lot_impact_registry.py#L633>)

```python
def test_component_merge_uses_union_bounds_instead_of_adding_incompatible_units() -> None:
```

### client-exposure

[etudecas/simulation/lot_trace/risk_impact_registry.py:2171](<../../simulation/lot_trace/risk_impact_registry.py#L2171>)

```python
def _client_service_rows(incident_id: str, impacts: dict[str, _LotImpact], lot_info: dict[str, dict[str, Any]], lot_events_by_lot: dict[str, list[dict[str, Any]]], service_context: dict[tuple[Any, ...], dict[str, Any]]) -> list[dict[str, Any]]:
```

### no-causal-claim-test

[etudecas/simulation/test_risk_lot_impact_registry.py:552](<../../simulation/test_risk_lot_impact_registry.py#L552>)

```python
def test_native_incident_propagates_to_campaign_client_and_cost_without_false_service_claim() -> None:
```

### legacy-proof-test

[etudecas/simulation/test_risk_lot_impact_registry.py:598](<../../simulation/test_risk_lot_impact_registry.py#L598>)

```python
def test_legacy_run_is_explicitly_association_not_native_causality() -> None:
```

### source-provenance

[etudecas/simulation/lot_trace/risk_impact_registry.py:974](<../../simulation/lot_trace/risk_impact_registry.py#L974>)

```python
def _build_source_provenance(*, data_dir: Path, source_files: dict[str, dict[str, Any]], risk_event_rows: list[dict[str, Any]]) -> dict[str, Any]:
```

### registry-inputs

[etudecas/simulation/lot_trace/risk_impact_registry.py:38](<../../simulation/lot_trace/risk_impact_registry.py#L38>)

```python
SOURCE_FILES = {'assumptions': 'assumptions_ledger.csv', 'state_risk_events': 'supplier_state_dependent_risk_events.csv', 'applied_risk': 'supplier_risk_events_applied_daily.csv', 'supplier_shipments': 'production_supplier_shipments_daily.csv', 'lot_events': 'production_lot_events.csv', 'lot_genealogy': 'production_lot_genealogy.csv', 'production_campaigns': 'production_campaigns.csv', 'demand_service': 'production_demand_service_daily.csv', 'supplier_parameters': 'supplier_nominal_parameters.csv'}
```

### registry-outputs

[etudecas/simulation/lot_trace/risk_impact_registry.py:67](<../../simulation/lot_trace/risk_impact_registry.py#L67>)

```python
OUTPUT_FILENAMES = {'incidents': 'risk_impact_incidents.csv', 'bundles': 'risk_impact_exposure_bundles.csv', 'bundle_events': 'risk_impact_bundle_events.csv', 'entities': 'risk_impact_entities.csv', 'edges': 'risk_impact_edges.csv', 'client_service': 'risk_impact_client_service.csv', 'costs': 'risk_impact_costs.csv', 'quality': 'risk_impact_quality.json'}
```

### source-hash-test

[etudecas/simulation/test_risk_lot_impact_registry.py:779](<../../simulation/test_risk_lot_impact_registry.py#L779>)

```python
def test_standalone_directory_hashes_exact_sources_and_written_registry_csvs(tmp_path: Path) -> None:
```

### consolidated-shipment-identity

[etudecas/simulation/engine/run_first_simulation.py:995](<../../simulation/engine/run_first_simulation.py#L995>)

```python
def next_shipment_identity(self, *, departure_day: int, arrival_day: int, route_id: str) -> tuple[str, str]:
```

Return one route/date shipment ID; handling unit stays unknown without source data.

### chunk-identity-test

[etudecas/simulation/test_risk_lot_impact_registry.py:950](<../../simulation/test_risk_lot_impact_registry.py#L950>)

```python
def test_multi_chunk_schedule_has_one_unique_join_key_per_physical_chunk() -> None:
```

### deferred-departure

[etudecas/simulation/engine/run_first_simulation.py:1907](<../../simulation/engine/run_first_simulation.py#L1907>)

```python
def record_allocation_event(self, *, day: int, event_type: str, parent_allocations: list[dict[str, Any]], source_id: str='', shipment_id: str='', risk_decision_day: int | str='', risk_event_ids: str='', departure_day: int | str='', arrival_day: int | str='', handling_unit_id: str='', notes: str='', trace_status: str='traced', trace_reason: str='', planned_order_id: str='', baseline_reference_id: str='') -> None:
```

Record a physical milestone for stock allocated at an earlier date.

### deferred-risk-test

[etudecas/simulation/test_risk_lot_impact_registry.py:1107](<../../simulation/test_risk_lot_impact_registry.py#L1107>)

```python
def test_reserved_shipment_retains_risk_decision_on_later_physical_departure() -> None:
```

### structural-shipment-links

[etudecas/simulation/lot_trace/causal_links.py:178](<../../simulation/lot_trace/causal_links.py#L178>)

```python
def build_lot_causal_link_rows(*, lot_event_rows: Iterable[dict[str, Any]], genealogy_rows: Iterable[dict[str, Any]], production_plan_rows: Iterable[dict[str, Any]], production_campaign_rows: Iterable[dict[str, Any]], mrp_order_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
```

Build a queryable causal index without replacing the physical genealogy.

Causal roots are scenario events. Entity links remain separate from physical
parent/child lot links so simultaneous risks are retained as co-causes rather
than being assigned arbitrary shares.
