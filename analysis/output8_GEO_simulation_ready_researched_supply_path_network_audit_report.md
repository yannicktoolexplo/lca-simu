# Supply Path Network Audit

- Input JSON: `analysis/output8_GEO_normalized_simulation_ready_researched.json`
- Generated at: `2026-05-21T14:17:23+00:00`
- Records audited: **170**
- Records excluded as non-supply LCA/process references: **5**
- Primary paths: **172**
- Secondary candidate paths: **24620**
- Total paths enumerated: **24792**

## Main Result

- Primary paths not hard-blocked: **172 / 172**
- Secondary paths not hard-blocked: **24620 / 24620**
- Paths with lane-specific transport model: **24792 / 24792**

Interpretation: primary baseline paths can now carry lane-specific transport scenarios when provided. Secondary switch paths still need lane validation before activation.

## Readiness

- `secondary_candidate_needs_qualification`: **24620**
- `primary_complete_needs_validation`: **127**
- `primary_ready_topology`: **45**

## Primary Readiness

- `primary_complete_needs_validation`: **127**
- `primary_ready_topology`: **45**

## LCA Use Classes

- `quantitative_ready`: **128** records
- `usable_for_baseline`: **17** records
- `scenario_only_review_required`: **13** records
- `usable_with_review`: **12** records

## Families

- `textile_leather`: **52** records
- `steel`: **41** records
- `aluminium`: **37** records
- `polymer_plastic`: **23** records
- `electronics_cots`: **8** records
- `general`: **3** records
- `adhesive_composite`: **2** records
- `rubber_silicone`: **2** records
- `copper`: **1** records
- `titanium_carbon`: **1** records

## Top Issue Codes

- `inactive_alternate_requires_allocation`: **24620** path occurrences
- `baseline_node_is_assumption`: **9180** path occurrences
- `material_certificate_required`: **8640** path occurrences
- `lca_mass_low_confidence`: **2181** path occurrences
- `lca_mass_requires_review`: **1372** path occurrences
- `raw_material_source_missing`: **422** path occurrences
- `site_is_fallback_or_centroid`: **3** path occurrences

## Transport Issue Codes


## Files

- Full path list: `C:/dev/lca-simu/analysis/output8_GEO_simulation_ready_researched_supply_path_network_full_paths.csv`
- Component summary: `C:/dev/lca-simu/analysis/output8_GEO_simulation_ready_researched_supply_path_network_component_summary.csv`
- Issue detail: `C:/dev/lca-simu/analysis/output8_GEO_simulation_ready_researched_supply_path_network_issues.csv`
- Transport lane audit: `C:/dev/lca-simu/analysis/output8_GEO_simulation_ready_researched_supply_path_network_transport_lanes.csv`
- Node candidate quality: `C:/dev/lca-simu/analysis/output8_GEO_simulation_ready_researched_supply_path_network_node_quality.csv`

## Recommended Next Step

For stress tests, keep primary paths as the first baseline. Secondary candidates now have lane-specific transport topology; before activation, validate procurement allocation, qualification, lead time, material evidence and the industrial plausibility of the selected mode per lane.
