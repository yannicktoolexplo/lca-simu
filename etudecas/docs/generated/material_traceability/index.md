# Supplier lots, receipts and incident scope

Document généré : modifier le registre et les sources, puis relancer le générateur.

Les statuts métier sont déclaratifs. Les tests ci-dessous sont référencés, **pas exécutés** par le générateur.
Une empreinte inchangée ne prouve ni la validité métier ni la réussite des tests.

## Règles métier

### MATERIAL-IDENTITY-001 — Supplier origins and receipts

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Do not infer a manufacturer batch from SHIP, BATCH or a truck. Documented allocations preserve unknown remainder. Single-origin splits retain identity; mixed picks retain possible origins without invented quantities.

Périmètre : Material receipt details and retrospective incident exploration

Unités : Physical quantities by article and unit; unique occurrences

Limites : Unknown manufacturer lots and inbound containers remain unknown. No quarantine, quality loss or delay is applied by a preview. Source authenticity is not certified.

Sources métier : [MATIERES_LOTS_ET_INCIDENTS.md](<../../MATIERES_LOTS_ET_INCIDENTS.md>)

Références :

- implementation : [build_material_traceability](<../../../simulation/lot_trace/materials.py#L55>)
- test : [MaterialTraceabilityTest](<../../../simulation/lot_trace/test_materials.py#L27>)

### MATERIAL-EXPOSURE-001 — Incident scope distinct from physical effect

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Recall previews follow positive physical links, deduplicate descendants and preserve unrelated branches. Native shipment incidents start at received occurrences, not all uses of source inventory. Exposure is not proven defect quantity, delay or service loss.

Périmètre : Material receipt details and retrospective incident exploration

Unités : Physical quantities by article and unit; unique occurrences

Limites : Unknown manufacturer lots and inbound containers remain unknown. No quarantine, quality loss or delay is applied by a preview. Source authenticity is not certified.

Sources métier : [MATIERES_LOTS_ET_INCIDENTS.md](<../../MATIERES_LOTS_ET_INCIDENTS.md>)

Références :

- implementation : [build_incident_preview](<../../../simulation/lot_trace/materials.py#L286>)
- implementation : [_incident_scope](<../../../simulation/lot_trace/materials.py#L267>)
- test : [MaterialTraceabilityTest](<../../../simulation/lot_trace/test_materials.py#L27>)
- test : [review](<../../../testing/material_browser_review.py#L10>)

### MATERIAL-JOURNEY-001 — Bidirectional physical lot journey

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Traverse ancestors and descendants separately. Preserve each stock occurrence and its actual links. Separate selected PF contribution from mixed receipt totals; do not infer PF quantities from material presence.

Périmètre : Separate read-only dialog with independent navigation; existing detailed lot tracking is preserved

Unités : Quantity in each article unit; simulated departure and arrival days

Limites : Unknown manufacturer batches and actual truck identities remain unknown. Initial stock history before J0 is absent. No physical incident effect is applied. Large diagrams are explicitly paginated.

Sources métier : [PARCOURS_DES_LOTS.md](<../../PARCOURS_DES_LOTS.md>), [lot_journey.js](<../../../visualization/maps/lot_journey.js>)

Références :

- implementation : [html_template](<../../../visualization/maps/worldmap_html_template.py#L226>)
- implementation : [refresh](<../../../visualization/maps/material_delivery.py#L27>)
- test : [test_forward_and_reverse_exclude_unrelated_sibling_consumption](<../../../testing/test_lot_journey.py#L49>)
- test : [test_stock_cards_preserve_paths_without_inventing_cross_branches](<../../../testing/test_lot_journey.py#L93>)
- test : [review](<../../../testing/journey_browser_review.py#L11>)

### MATERIAL-BALANCE-001 — Occurrence stock summary and reserved departures

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Reconcile occurrence events through the selected end-of-day cutoff or all history. Preserve article, site and unit. Reserved departures are not debited twice. A pre-creation occurrence is distinct from unknown or invalid data. The summary covers the whole inspected occurrence independently of visible branches.

Périmètre : Read-only lot summary in the separate simplified journey dialog

Unités : Physical article unit; fractional KG allowed, whole UN required; simulation days

Limites : Local occurrence balance, independent of main-map time. Mixed receipts include all origins. The separate network balance follows the journey starting occurrence, not all units of all ancestors.

Sources métier : [FICHE_LOT.md](<../../FICHE_LOT.md>), [lot_journey.js](<../../../visualization/maps/lot_journey.js>)

Références :

- implementation : [html_template](<../../../visualization/maps/worldmap_html_template.py#L226>)
- test : [review](<../../../testing/journey_browser_review.py#L11>)
- test : [test_balance_reserved_departure_is_not_debited_twice](<../../../testing/test_lot_journey.py#L148>)
- test : [test_balance_invalid_ledger_never_displays_certified_totals](<../../../testing/test_lot_journey.py#L179>)
- test : [test_balance_uses_entire_occurrence_independent_of_direction](<../../../testing/test_lot_journey.py#L187>)

### MATERIAL-TRANSPORT-IMPACT-001 — Complete shipment cargo and conservative impact scope

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Shipment totals count departures once by article and unit. Display existing truck planning groups with their assumptions, without inventing actual vehicle assignment. Impact scope follows positive descendant links from occurrence seeds or explicit supplier-origin allocations, including possible mixed origins. Co-loaded lots and other mixed parents are not added by proximity. Preserve physical data and legacy tracking.

Périmètre : Independent simplified journey dialog, full recorded horizon

Unités : Article units and simulated days; local stock balances; estimated/proposed vehicle dimensions

Limites : Potential exposure is not proven defect quantity, delay or service loss. Whole mixed receipts are included conservatively. Unknown supplier batches and actual vehicles remain unknown. Planning assumptions are not independently calibrated by display checks.

Sources métier : [TRANSPORTS_ET_IMPACTS.md](<../../TRANSPORTS_ET_IMPACTS.md>), [lot_journey_operations.js](<../../../visualization/maps/lot_journey_operations.js>)

Références :

- implementation : [html_template](<../../../visualization/maps/worldmap_html_template.py#L226>)
- implementation : [refresh](<../../../visualization/maps/material_delivery.py#L27>)
- test : [test_complete_shipment_cargo_excludes_reservation_double_count](<../../../testing/test_journey_operations.py#L37>)
- test : [test_impact_does_not_spread_to_co_loaded_or_other_mixed_origins](<../../../testing/test_journey_operations.py#L65>)
- test : [test_supplier_lot_scope_requires_explicit_identity_including_possible_mixes](<../../../testing/test_journey_operations.py#L75>)
- test : [check_operations](<../../../testing/journey_operations_browser.py#L6>)

### MATERIAL-EXPLORER-001 — Complete identity access and separate inspection

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Index stock and business identities including mixed business_lot_ids, received shipments, with source occurrence fallback before receipt and documented external origins or containers. Filter and paginate without merging occurrences. Distinguish diagram origin from inspected card, with independent history and sidebar. Preserve legacy tracking.

Périmètre : Read-only simplified journey

Unités : Occurrence identities and creation days

Limites : Search establishes recorded identity presence, not defect or proportional physical allocation. Unknown origin and quality remain unknown.

Sources métier : [EXPLORATEUR_DES_LOTS.md](<../../EXPLORATEUR_DES_LOTS.md>), [lot_journey.js](<../../../visualization/maps/lot_journey.js>), [lot_journey_explorer.js](<../../../visualization/maps/lot_journey_explorer.js>), [lot_journey_explorer.css](<../../../visualization/maps/lot_journey_explorer.css>)

Références :

- implementation : [html_template](<../../../visualization/maps/worldmap_html_template.py#L226>)
- test : [test_identity_search_finds_mixed_business_occurrences_and_filters](<../../../testing/test_journey_explorer.py#L81>)
- test : [test_documented_origin_and_handling_unit_search_and_quality_unknown](<../../../testing/test_journey_explorer.py#L90>)
- test : [review](<../../../testing/journey_explorer_review.py#L11>)

### MATERIAL-NETWORK-001 — Dated physical network balance with mixed attribution bounds

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Follow the starting occurrence through same-item same-unit transports to current stock, reserved stock, transit, consumption, service and loss. Transfers do not double count quantity. Unreceived shipments stay in transit. Mixed removals carry lower and upper bounds; conservation tightens categories without inventing proportional physical allocations.

Périmètre : End of simulation day, independent of displayed graph pagination; no engine mutation

Unités : Whole UN, fractional KG, recorded simulation days

Limites : Mixed attribution bounds can remain conservative and correlated; they are not additive exact quantities. Receipt passage totals differ from current stock and service. Material-to-PF conversion is not inferred. Unsupported or inconsistent data prevents numeric display.

Sources métier : [EXPLORATEUR_DES_LOTS.md](<../../EXPLORATEUR_DES_LOTS.md>), [lot_journey_timeline.js](<../../../visualization/maps/lot_journey_timeline.js>)

Références :

- implementation : [html_template](<../../../visualization/maps/worldmap_html_template.py#L226>)
- test : [test_timeline_exact_reservation_transit_receipt_and_open_shipment](<../../../testing/test_journey_explorer.py#L37>)
- test : [test_mixed_service_bounds_match_all_possible_integer_allocations](<../../../testing/test_journey_explorer.py#L48>)
- test : [test_fractional_kg_roundoff_does_not_amplify_in_conservation_bounds](<../../../testing/test_journey_explorer.py#L129>)
- test : [review](<../../../testing/journey_explorer_review.py#L11>)
- test : [test_local_balance_before_creation_and_during_reservation](<../../../testing/test_journey_explorer.py#L61>)

### MATERIAL-SCENARIO-001 — Scenario-local identities, provenance and business state

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Use one explicitly identified scenario and its manifest input graph for a standalone explorer. Expose native receipt incident IDs, initial history boundaries, reference-transition consumption and physical states. Manufacturer identity, containers, quality and expiry are not fabricated. A present stock is not proof of quality release.

Périmètre : Existing nominal and separately exported scenario results; new physical incidents deferred

Unités : Scenario-local LOT/SHIP identifiers and article units

Limites : No cross-scenario identity equivalence inferred from matching IDs. Standalone scenario diagrams use recorded link quantities without the nominal canonical PF contribution overlay. Quality and expiry remain undocumented.

Sources métier : [EXPLORATEUR_DES_LOTS.md](<../../EXPLORATEUR_DES_LOTS.md>), [lot_journey_explorer.js](<../../../visualization/maps/lot_journey_explorer.js>)

Références :

- implementation : [build_scenario_explorer](<../../../visualization/maps/journey_scenario_delivery.py#L21>)
- test : [review](<../../../testing/journey_scenario_review.py#L12>)
- test : [test_scenario_export_rejects_graph_different_from_run_manifest](<../../../testing/test_journey_scenario_delivery.py#L40>)
- test : [test_documented_origin_and_handling_unit_search_and_quality_unknown](<../../../testing/test_journey_explorer.py#L90>)

### MATERIAL-INVESTIGATION-001 — Read-only investigation files, reports and graph neighbourhoods

Statut déclaré : **documented**. Relecture des sources : **aucun changement détecté**.

Bind navigation files to SHA-256 fingerprints of events, genealogy, lot identities, materials, trucks and nodes. Validate all fields before replacing the independent journey state. Recompute optional impact scopes. Reports capture dated balances and full-horizon physical links, irrespective of graph visibility. Neighbourhoods expose only actual scoped edges without changing physical data or network totals.

Périmètre : Offline nominal and separate existing risk explorer; navigation files and script-free HTML reports

Unités : Scenario-local identities, simulation days and article units

Limites : The navigation JSON requires matching map data and contains no simulation results. Fingerprints do not certify industrial truth or rendering/engine versions. Report links cover the full selected direction and horizon, not just the cutoff or visible cards. Detailed shipment cargo and impacts require reopening the map. No new physical incidents.

Sources métier : [ENQUETES_LOTS.md](<../../ENQUETES_LOTS.md>), [lot_journey_case.js](<../../../visualization/maps/lot_journey_case.js>)

Références :

- implementation : [html_template](<../../../visualization/maps/worldmap_html_template.py#L226>)
- implementation : [refresh](<../../../visualization/maps/material_delivery.py#L27>)
- implementation : [build_scenario_explorer](<../../../visualization/maps/journey_scenario_delivery.py#L21>)
- test : [test_saved_case_roundtrip_restores_context_and_recomputes_impact](<../../../testing/test_journey_case.py#L18>)
- test : [test_case_rejects_same_lot_ids_with_different_physical_results](<../../../testing/test_journey_case.py#L31>)
- test : [test_invalid_case_never_partially_replaces_navigation](<../../../testing/test_journey_case.py#L44>)
- test : [test_neighbourhood_expansion_preserves_real_edges_and_full_scope](<../../../testing/test_journey_case.py#L58>)
- test : [test_neighbourhood_does_not_truncate_network_totals](<../../../testing/test_journey_case.py#L73>)
- test : [test_printable_report_captures_date_bounds_and_full_links](<../../../testing/test_journey_case.py#L91>)
- test : [review](<../../../testing/journey_case_review.py#L11>)

## Référence technique extraite

Les constantes sont affichées comme expressions Python ; les références et dépliages `*` ne sont pas exécutés.

### material-context

[etudecas/simulation/lot_trace/materials.py:55](<../../../simulation/lot_trace/materials.py#L55>)

```python
def build_material_traceability(events, genealogy, graph=None, metadata=None):
```

Build the auditable context shared by the map and offline checks.

Metadata allocations refer to receipt *event* IDs and sum to at most its
quantity. Unmapped remainder stays unknown. Handling units describe the inbound
receipt only, not the current location/contents of a pallet after consumption.

### incident-preview

[etudecas/simulation/lot_trace/materials.py:286](<../../../simulation/lot_trace/materials.py#L286>)

```python
def build_incident_preview(context, events, genealogy, incident):
```

Resolve an explicitly scoped future incident without mutating any ledger.

For mixed receipts/containers, descendants are a conservative candidate set.
We deliberately do not prorate a quality defect into a false output quantity.
The detection day is informational: a recall can include earlier production.

### incident-scope

[etudecas/simulation/lot_trace/materials.py:267](<../../../simulation/lot_trace/materials.py#L267>)

```python
def _incident_scope(incident, seed_lots, events, outgoing):
```

### material-tests

[etudecas/simulation/lot_trace/test_materials.py:27](<../../../simulation/lot_trace/test_materials.py#L27>)

```python
class MaterialTraceabilityTest
```

### material-browser

[etudecas/testing/material_browser_review.py:10](<../../../testing/material_browser_review.py#L10>)

```python
def review(html, data, output):
```

### journey-template

[etudecas/visualization/maps/worldmap_html_template.py:226](<../../../visualization/maps/worldmap_html_template.py#L226>)

```python
def html_template(title: str, data_json: str, material_table_html: str, material_table_count: int, global_model_equations_html: str) -> str:
```

### journey-delivery

[etudecas/visualization/maps/material_delivery.py:27](<../../../visualization/maps/material_delivery.py#L27>)

```python
def refresh(source, data, graph, output, evidence, metadata_path=None):
```

### journey-directions-test

[etudecas/testing/test_lot_journey.py:49](<../../../testing/test_lot_journey.py#L49>)

```python
def test_forward_and_reverse_exclude_unrelated_sibling_consumption(page):
```

### journey-branches-test

[etudecas/testing/test_lot_journey.py:93](<../../../testing/test_lot_journey.py#L93>)

```python
def test_stock_cards_preserve_paths_without_inventing_cross_branches(page):
```

### journey-browser

[etudecas/testing/journey_browser_review.py:11](<../../../testing/journey_browser_review.py#L11>)

```python
def review(html, data, output):
```

### lot-balance-reservation-test

[etudecas/testing/test_lot_journey.py:148](<../../../testing/test_lot_journey.py#L148>)

```python
def test_balance_reserved_departure_is_not_debited_twice(page):
```

### lot-balance-invalid-test

[etudecas/testing/test_lot_journey.py:179](<../../../testing/test_lot_journey.py#L179>)

```python
def test_balance_invalid_ledger_never_displays_certified_totals(page, mutation):
```

### lot-balance-scope-test

[etudecas/testing/test_lot_journey.py:187](<../../../testing/test_lot_journey.py#L187>)

```python
def test_balance_uses_entire_occurrence_independent_of_direction(page):
```

### journey-cargo-test

[etudecas/testing/test_journey_operations.py:37](<../../../testing/test_journey_operations.py#L37>)

```python
def test_complete_shipment_cargo_excludes_reservation_double_count(page):
```

### journey-impact-test

[etudecas/testing/test_journey_operations.py:65](<../../../testing/test_journey_operations.py#L65>)

```python
def test_impact_does_not_spread_to_co_loaded_or_other_mixed_origins(page):
```

### journey-supplier-impact-test

[etudecas/testing/test_journey_operations.py:75](<../../../testing/test_journey_operations.py#L75>)

```python
def test_supplier_lot_scope_requires_explicit_identity_including_possible_mixes(page):
```

### journey-operations-browser

[etudecas/testing/journey_operations_browser.py:6](<../../../testing/journey_operations_browser.py#L6>)

```python
def check_operations(page, events, links, check, output):
```

### explorer-search-test

[etudecas/testing/test_journey_explorer.py:81](<../../../testing/test_journey_explorer.py#L81>)

```python
def test_identity_search_finds_mixed_business_occurrences_and_filters(page):
```

### explorer-timeline-test

[etudecas/testing/test_journey_explorer.py:37](<../../../testing/test_journey_explorer.py#L37>)

```python
def test_timeline_exact_reservation_transit_receipt_and_open_shipment(page, day, expected):
```

### explorer-mix-test

[etudecas/testing/test_journey_explorer.py:48](<../../../testing/test_journey_explorer.py#L48>)

```python
def test_mixed_service_bounds_match_all_possible_integer_allocations(page):
```

### explorer-identities-test

[etudecas/testing/test_journey_explorer.py:90](<../../../testing/test_journey_explorer.py#L90>)

```python
def test_documented_origin_and_handling_unit_search_and_quality_unknown(page):
```

### explorer-fraction-test

[etudecas/testing/test_journey_explorer.py:129](<../../../testing/test_journey_explorer.py#L129>)

```python
def test_fractional_kg_roundoff_does_not_amplify_in_conservation_bounds(page):
```

### explorer-browser

[etudecas/testing/journey_explorer_review.py:11](<../../../testing/journey_explorer_review.py#L11>)

```python
def review(html, data, graph, output):
```

### explorer-scenario-export

[etudecas/visualization/maps/journey_scenario_delivery.py:21](<../../../visualization/maps/journey_scenario_delivery.py#L21>)

```python
def build_scenario_explorer(data, graph, output, evidence):
```

### explorer-scenario-browser

[etudecas/testing/journey_scenario_review.py:12](<../../../testing/journey_scenario_review.py#L12>)

```python
def review(html, data, output):
```

### explorer-scenario-graph-test

[etudecas/testing/test_journey_scenario_delivery.py:40](<../../../testing/test_journey_scenario_delivery.py#L40>)

```python
def test_scenario_export_rejects_graph_different_from_run_manifest(tmp_path):
```

### explorer-local-day-test

[etudecas/testing/test_journey_explorer.py:61](<../../../testing/test_journey_explorer.py#L61>)

```python
def test_local_balance_before_creation_and_during_reservation(page):
```

### case-roundtrip

[etudecas/testing/test_journey_case.py:18](<../../../testing/test_journey_case.py#L18>)

```python
def test_saved_case_roundtrip_restores_context_and_recomputes_impact(case_page):
```

### case-mismatch

[etudecas/testing/test_journey_case.py:31](<../../../testing/test_journey_case.py#L31>)

```python
def test_case_rejects_same_lot_ids_with_different_physical_results(case_page):
```

### case-invalid

[etudecas/testing/test_journey_case.py:44](<../../../testing/test_journey_case.py#L44>)

```python
def test_invalid_case_never_partially_replaces_navigation(case_page, mutation):
```

### case-neighbourhood

[etudecas/testing/test_journey_case.py:58](<../../../testing/test_journey_case.py#L58>)

```python
def test_neighbourhood_expansion_preserves_real_edges_and_full_scope(page):
```

### case-network-scope

[etudecas/testing/test_journey_case.py:73](<../../../testing/test_journey_case.py#L73>)

```python
def test_neighbourhood_does_not_truncate_network_totals(case_page):
```

### case-report

[etudecas/testing/test_journey_case.py:91](<../../../testing/test_journey_case.py#L91>)

```python
def test_printable_report_captures_date_bounds_and_full_links(case_page):
```

### case-browser

[etudecas/testing/journey_case_review.py:11](<../../../testing/journey_case_review.py#L11>)

```python
def review(html, scenario_html, data, output):
```
