# Business review applied to missing tiers

- Input JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_corrected.json`
- Missing-tier decision CSV: `C:/dev/lca-simu/analysis/output8_GEO_missing_tier_most_probable.csv`
- Output JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_business_reviewed.json`
- Change log: `C:/dev/lca-simu/analysis/output8_GEO_business_review_changes.csv`

## Principle

- No missing tier was completed by inventing an active supplier.
- Metal T2 gaps are modeled as internalized process metadata under the primary T1.
- Material-family mismatches are removed from the active supplier network.
- LCA process-reference rows are disabled for supply-chain mapping/simulation.

## Counts

- Active supplier entries before: 2947
- Active supplier entries after: 2905
- Disabled records: 2
- Unverified supplier candidates after: 57
- Excluded supplier entries after: 67
- Change rows: 43

## Applied Actions

- `internalized_process_metadata`: 43
- `lca_process_suppliers_removed`: 28
- `wrong_steel_t4_on_copper`: 5
- `polymer_t1_scope_validation`: 4
- `wrong_alcoa_on_steel`: 2
- `lca_process_records_disabled`: 2
- `combigo_packaging_review`: 1
- `unverified_copper_t4`: 1
- `wrong_metal_t3_on_polymer`: 1

## Active Roles After Review

- `tier1`: 1302
- `tier2_second_transformation`: 376
- `tier3_first_transformation`: 652
- `tier4_raw_material`: 575

## Notes

- R5 copper alloy: steel T4 candidates were removed from active suppliers; copper upstream remains unverified.
- R16/R51 35NC6: Alcoa was removed from active steel chains.
- R75 Lexan/FST: metal T3/T1 candidates were removed or demoted pending polymer routing validation.
- R127/R156: SimaPro/GLO process references are no longer active supply-chain records in this reviewed JSON.
