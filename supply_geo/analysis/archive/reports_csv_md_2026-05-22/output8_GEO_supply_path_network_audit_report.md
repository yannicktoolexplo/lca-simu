# Supply Path Network Audit

- Input JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_primary_complete_lca_marked.json`
- Generated at: `2026-05-21T11:20:38+00:00`
- Records audited: **173**
- Records excluded as non-supply LCA/process references: **2**
- Primary paths: **175**
- Secondary candidate paths: **29814**
- Total paths enumerated: **29989**

## Main Result

- Primary paths not hard-blocked: **124 / 175**
- Secondary paths not hard-blocked: **16321 / 29814**
- Paths with lane-specific transport model: **0 / 29989**

Interpretation: the main topology is complete, but transport remains modeled with generic phase modes, not lane-specific transport legs.

## Readiness

- `secondary_candidate_needs_qualification`: **16321**
- `not_ready_rework_required`: **8280**
- `not_ready_transport_rework`: **5264**
- `primary_complete_needs_validation`: **124**

## Primary Readiness

- `primary_complete_needs_validation`: **124**
- `not_ready_rework_required`: **28**
- `not_ready_transport_rework`: **23**

## LCA Use Classes

- `quantitative_ready`: **128** records
- `usable_for_baseline`: **17** records
- `scenario_only_review_required`: **16** records
- `usable_with_review`: **12** records

## Families

- `textile_leather`: **52** records
- `aluminium`: **40** records
- `steel`: **38** records
- `polymer_plastic`: **23** records
- `electronics_cots`: **8** records
- `general`: **3** records
- `mixed_metal`: **3** records
- `adhesive_composite`: **2** records
- `rubber_silicone`: **2** records
- `copper`: **1** records
- `titanium_carbon`: **1** records

## Top Issue Codes

- `edge_transport_mode_not_explicit`: **29989** path occurrences
- `inactive_alternate_requires_allocation`: **29814** path occurrences
- `material_certificate_required`: **9073** path occurrences
- `supplier_material_family_incompatible`: **7448** path occurrences
- `baseline_node_is_assumption`: **7343** path occurrences
- `long_distance_mode_implausible`: **7061** path occurrences
- `lca_mass_low_confidence`: **4520** path occurrences
- `lca_mass_requires_review`: **2212** path occurrences
- `edge_distance_not_computable`: **1128** path occurrences
- `node_missing_coordinates`: **1128** path occurrences
- `regional_long_truck_only`: **524** path occurrences
- `raw_material_source_missing`: **432** path occurrences
- `electronics_upstream_requires_bom`: **289** path occurrences
- `site_is_fallback_or_centroid`: **87** path occurrences
- `mixed_material_component_should_split`: **13** path occurrences

## Transport Issue Codes

- `edge_transport_mode_not_explicit`: **55034** path-edge occurrences
- `long_distance_mode_implausible`: **7430** path-edge occurrences
- `edge_distance_not_computable`: **2256** path-edge occurrences
- `regional_long_truck_only`: **524** path-edge occurrences

## Files

- Full path list: `C:/dev/lca-simu/analysis/output8_GEO_supply_path_network_full_paths.csv`
- Component summary: `C:/dev/lca-simu/analysis/output8_GEO_supply_path_network_component_summary.csv`
- Issue detail: `C:/dev/lca-simu/analysis/output8_GEO_supply_path_network_issues.csv`
- Transport lane audit: `C:/dev/lca-simu/analysis/output8_GEO_supply_path_network_transport_lanes.csv`
- Node candidate quality: `C:/dev/lca-simu/analysis/output8_GEO_supply_path_network_node_quality.csv`

## Recommended Next Step

For stress tests, keep primary paths as the first baseline. Then curate secondary candidates by family before enabling switches: remove material-incompatible nodes, validate certificates/allocations, and add lane-level transport modes for T3->T2, T2->T1 and T1->OEM.
