# Mass estimation for output8_GEO_normalized_corrected.json

- Input JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_corrected.json`
- Workbook source: `C:/dev/lca-simu/data/quantity_material.xlsx`
- Output JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_corrected_mass_estimated.json`
- Detail CSV: `C:/dev/lca-simu/analysis/output8_GEO_mass_estimates.csv`
- Non-packaging BOM mass used as seat-total fallback: `115.966381 kg`

## Coverage

- Records: 175
- Records with mass after estimation: 175
- Records still missing mass: 0
- Records whose mass value changed: 170

## Methods

- `bom_exact_system_material`: 129
- `bom_system_material_family_sum`: 20
- `bom_global_material_family_sum`: 10
- `bom_global_material_total`: 7
- `percentage_of_bom_material_total`: 5
- `bom_mixed_material_share`: 4

## Confidence

- `high`: 129
- `medium_high`: 17
- `medium`: 12
- `low`: 10
- `medium_low`: 7

## Remaining Missing

- None.

## Interpretation

High confidence means an exact system + material mass was found in the LCA BOM. Medium confidence usually means a material-family sum or whole-equipment fallback. Low confidence global fallbacks should be reviewed before quantitative stress tests.
