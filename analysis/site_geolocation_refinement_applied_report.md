# Applied site geolocation refinement

- Input JSON: `C:\dev\lca-simu\analysis\output8_GEO_normalized_final_site_reviewed.json`
- Refinement CSV: `C:\Users\yannick.martz\Downloads\site_geolocation_refinement_lca_simu.csv`
- Output JSON: `C:\dev\lca-simu\analysis\output8_GEO_normalized_final_site_refined.json`
- Change log: `C:\dev\lca-simu\analysis\site_geolocation_refinement_applied_changes.csv`
- Total changes/actions: **378**

## Change counts

| change_type | count |
|---|---:|
| approx_site_refined | 34 |
| candidate_site_metadata_refined | 179 |
| mitsubishi_hiratsuka | 16 |
| mitsubishi_left_unresolved_non_polymer | 5 |
| removed_from_aluminium_chain | 41 |
| removed_steel_candidate_from_non_steel_context | 37 |
| te_evreux_with_toulouse_alternative | 1 |
| toray_generic_unknown_site | 29 |
| toray_split_nagoya | 20 |
| xpo_lyon_company_node | 16 |

## Application notes

- Tata Steel was removed from aluminium chains and kept only as a steel candidate.
- Toray Tokyo fallback was split: Nagoya for nylon/polyamide/engineering plastics, unknown site for generic textile/velcro/leather/composite/electronics contexts.
- Mitsubishi Hiratsuka was applied only to polymer/engineering-plastics contexts; display/electronics rows remain unresolved until BOM/PN proof.
- XPO Lyon is a company-level European logistics node, not a physical route depot.
- TE Evreux is applied as the connector/cable-hardware candidate; Toulouse is stored as an inactive sensor/electronics alternative.
