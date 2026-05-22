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

- `daio paper corporation`: Shikokuchuo, Japan (medium_high) - https://www.daio-paper.co.jp/en/company/base/
- `diodes incorporated`: Plano, United States (medium) - https://www.diodes.com/about/company-profile/
- `huddersfield textiles`: Huddersfield, United Kingdom (medium) - https://www.huddersfieldtextiles.com/
- `intel`: Santa Clara, United States (medium) - https://www.intel.com/content/www/us/en/company-overview/company-overview.html
- `kemko aerospace`: St. Louis, United States (low) - https://kemkoaerospace.net/
- `liebherr aerospace`: Lindenberg im Allgau, Germany (medium_high) - https://www.liebherr.com/en/int/products/aerospace-and-transportation-systems/aerospace-and-transportation-systems.html
- `mondi`: Vienna, Austria (medium_high) - https://www.mondigroup.com/locations/
- `rohm`: Kyoto, Japan (medium) - https://www.rohm.com/company
- `shin etsu silicones`: Tokyo, Japan (medium_high) - https://www.shinetsu.co.jp/en/company/network/office/
- `silicone engineering`: Blackburn, United Kingdom (medium_high) - https://silicone.co.uk/
- `sony`: Tokyo, Japan (medium) - https://www.sony.com/en/SonyInfo/CorporateInfo/
- `te connectivity`: Berwyn, United States (medium) - https://www.te.com/en/industries/aerospace.html
- `tsmc`: Hsinchu, Taiwan (medium) - https://www.tsmc.com/english/aboutTSMC
- `xpo logistic`: Greenwich, United States (medium) - https://investors.xpo.com/

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
