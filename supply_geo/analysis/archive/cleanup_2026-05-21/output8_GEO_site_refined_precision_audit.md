# Site refined precision audit

- Source JSON: `analysis\output8_GEO_normalized_final_site_refined.json`
- Total active map-scope entries: **3066**
- `country_centroid`: **0** occurrences, **0** unique nodes.
- `unpositioned_unknown_site`: **29** occurrences, **1** unique nodes.
- `unresolved_hq_or_fallback`: **5** occurrences, **1** unique nodes.
- `site_candidate_requires_certificate_or_pn`: **216** occurrences, **8** unique nodes.
- `logistics_company_node_not_depot`: **16** occurrences, **1** unique nodes.
- `approx_source_geocode`: **36** occurrences, **6** unique nodes.

## Nodes requiring attention

| categories | node | role | occurrences | status | action |
|---|---|---:|---:|---|---|
| unpositioned_unknown_site | FRN-0F56088BEA4986 | tier3_first_transformation | 29 | site_unknown_requires_material_grade_or_supplier_proof | Set site_unknown=true or use actual supplier such as FRN-0CA3DB5897A052 if that is the sourced supplier. |
| unresolved_hq_or_fallback | FRN-6378B78052F4FE | tier4_raw_material | 5 | fallback_site_needs_source | Do not apply Hiratsuka to display/electronics records without BOM/PN proving FRN-6378B78052F4FE material scope. |
| site_candidate_requires_certificate_or_pn | FRN-7A25E45203FCC9 | tier4_raw_material | 42 | source_backed_industrial_site_candidate_requires_certificate | Use as aluminium producer scenario candidate, not as guaranteed active source. |
| site_candidate_requires_certificate_or_pn | FRN-CF71418802439F | tier4_raw_material | 35 | source_backed_industrial_site_candidate_requires_certificate | Keep as China steel-mill scenario candidate; active=false until certificate/order confirms. |
| site_candidate_requires_certificate_or_pn | FRN-5AA9E59DA0B02F | tier4_raw_material | 35 | source_backed_industrial_site_candidate_requires_certificate | Use only for steel scenarios and require material certificate before active allocation. Remove from aluminium rows. |
| site_candidate_requires_certificate_or_pn | FRN-3C5607FC501E5A | tier4_raw_material | 34 | source_backed_industrial_site_candidate_requires_certificate | Use as special-steel scenario candidate; active=false until mill certificate confirms. |
| site_candidate_requires_certificate_or_pn | FRN-B8E884308EA449 | tier4_raw_material | 33 | source_backed_industrial_site_candidate_requires_certificate | Use as US steel-mill scenario candidate; active=false unless certificate confirms. |
| site_candidate_requires_certificate_or_pn | FRN-0F56088BEA4986 | tier3_first_transformation | 20 | source_backed_industrial_site_candidate | Nagoya applied only for nylon/polyamide/engineering-plastics contexts; grade certificate still required. |
| site_candidate_requires_certificate_or_pn | FRN-6378B78052F4FE | tier4_raw_material | 16 | source_backed_industrial_site_candidate | Hiratsuka applied for polymer/engineering-plastics contexts; PN/grade validation still required. |
| site_candidate_requires_certificate_or_pn | FRN-B9C4C86C42C8B4 | tier1 | 1 | source_backed_aerospace_connector_site_candidate | Use Évreux rather than Berwyn for aerospace connector/cable-hardware scenarios; active=false until part number/supplier code confirms. |
| logistics_company_node_not_depot | FRN-7BCA1282BFEC03 | logistics | 16 | source_backed_europe_company_hq_not_depot | Use Lyon for company-level European logistics node. For a physical transport leg, choose lane-specific depot/warehouse instead. |
| approx_source_geocode | FRN-0CA3DB5897A052 | tier3_first_transformation | 29 | source_backed_industrial_site_approx | Use as textile company site; do not assume it is the actual weaving/finishing mill unless order evidence confirms. |
| approx_source_geocode | FRN-332F92E4BA4B00 | tier3_first_transformation | 2 | source_backed_industrial_site_approx | Use as silicone chemistry supplier candidate; active=false until grade/SDS confirms. |
| approx_source_geocode | FRN-BDE3FD68E4E87F | tier2_second_transformation | 2 | source_backed_industrial_site_approx | Use as T2 silicone converter. Keep Shin-Etsu/Wacker/Momentive/etc. separate as chemistry candidates. |
| approx_source_geocode | FRN-B7600B824E7BC7 | tier3_first_transformation | 1 | source_backed_industrial_site_approx | Use as paper mill candidate for packaging/paperboard flows; active=false until supplier evidence confirms. |
| approx_source_geocode | FRN-0F56088BEA4986 | tier3_first_transformation | 1 | source_backed_industrial_site_nearby_station_geocode | Use Ehime for carbon-fiber record; exact gate coordinate can be refined later. |
| approx_source_geocode | FRN-0F56088BEA4986 | tier2_second_transformation | 1 | source_backed_industrial_site_nearby_station_geocode | Use Ehime for carbon-fiber record; exact gate coordinate can be refined later. |
