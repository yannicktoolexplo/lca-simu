# Final supplier corrections applied

- Input JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_corrected_mass_estimated.json`
- Review table: `C:/dev/lca-simu/analysis/output8_GEO_reviewed_uncertain_supplier_tiers.csv`
- Output JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_corrected.json`
- Change log: `C:/dev/lca-simu/analysis/output8_GEO_final_corrections_applied.csv`

## Counts

- Supplier entries before: 3047
- Supplier entries after switchable cleanup: 2947
- Packaging/auxiliary entries: 2
- COTS upstream entries: 15
- Unverified supplier candidates: 52
- Excluded/non-supplier entries: 31
- Change rows: 267

## Actions Applied

- `kept_or_normalized`: 160
- `fill_missing_location_from_review_followup`: 61
- `moved_to_unverified`: 52
- `removed_from_switchable_network`: 29
- `moved_to_cots_upstream`: 15
- `moved_to_packaging`: 2
- `removed_out_of_scope_for_component`: 2

## Location Follow-Up Sources

- `FRN-B7600B824E7BC7`: Shikokuchuo, Japan (medium_high) - https://sources.invalid/FRN-B7600B824E7BC7/5b8fa58f3adb9d79
- `FRN-A75319B66652B8`: Plano, United States (medium) - https://sources.invalid/FRN-A75319B66652B8/457b90d5d3667cac
- `FRN-0CA3DB5897A052`: Huddersfield, United Kingdom (medium) - https://sources.invalid/FRN-0CA3DB5897A052/5364bf02a1bbcc9d
- `intel`: Santa Clara, United States (medium) - https://sources.invalid/FRN-5BF789044ED6FF/e4e19872dedc69fd
- `FRN-EFD76ECB77D7DC`: St. Louis, United States (low) - https://sources.invalid/FRN-EFD76ECB77D7DC/24684e2d793b48e6
- `FRN-42EDB7DB79E4B3`: Lindenberg im Allgau, Germany (medium_high) - https://sources.invalid/FRN-42EDB7DB79E4B3/4bb47925bbd7bd27
- `FRN-A982B812225B13`: Vienna, Austria (medium_high) - https://sources.invalid/FRN-A982B812225B13/b39669b11aca977f
- `FRN-498413D6464206`: Kyoto, Japan (medium) - https://sources.invalid/FRN-498413D6464206/0e0d4cceb6fcf9a4
- `shin etsu silicones`: Tokyo, Japan (medium_high) - https://sources.invalid/FRN-332F92E4BA4B00/3ff419c7daa4e772
- `FRN-BDE3FD68E4E87F`: Blackburn, United Kingdom (medium_high) - https://sources.invalid/FRN-BDE3FD68E4E87F/8c9900b4ae3c7970
- `FRN-002EAED5EB16E6`: Tokyo, Japan (medium) - https://sources.invalid/FRN-002EAED5EB16E6/c89e584c34f7eceb
- `FRN-B9C4C86C42C8B4`: Berwyn, United States (medium) - https://sources.invalid/FRN-B9C4C86C42C8B4/43e1f43c29b50066
- `FRN-A00FD04291B8DD`: Hsinchu, Taiwan (medium) - https://sources.invalid/FRN-A00FD04291B8DD/24891b38ebac5c21
- `FRN-7BCA1282BFEC03`: Greenwich, United States (medium) - https://sources.invalid/FRN-7BCA1282BFEC03/97c5f24196290d7d

## Switchable Supplier Roles After Cleanup

- `tier1`: 1310
- `tier2_second_transformation`: 382
- `tier3_first_transformation`: 661
- `tier4_raw_material`: 594

## Modeling Policy

- `suppliers` now contains switchable production nodes only.
- `packaging_suppliers` contains packaging/paper auxiliary candidates.
- `cots_upstream_suppliers` contains electronics/COTS brands that should not be treated as direct switchable suppliers.
- `unverified_supplier_candidates` contains plausible names that still need purchasing or engineering validation.
- `excluded_suppliers` preserves placeholders, associations, wrong-scope entities, and likely errors for traceability.
