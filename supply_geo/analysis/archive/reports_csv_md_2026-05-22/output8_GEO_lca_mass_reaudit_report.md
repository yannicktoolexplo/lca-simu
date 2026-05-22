# LCA Mass Re-Audit

- Generated at: `2026-05-22T07:15:40+00:00`
- Source workbook: `C:/dev/lca-simu/data/quantity_material.xlsx`
- Primary path source: `C:/dev/lca-simu/analysis/output8_GEO_simulation_ready_researched_supply_path_network_full_paths.csv`

## Main Result

- Workbook non-packaging mass: **115.966 kg**
- Current primary nominal mass: **315.765 kg**
- Apparent overcount vs workbook: **199.799 kg**
- Conservative component baseline: **119.530 kg**
- Additive baseline with review rows: **129.949 kg**

Interpretation: the current nominal total is not a valid additive mass because top-down `Siège`/global ACV rows coexist with detailed component rows. Those rows should remain as reference/scenario rows, not be summed with the detailed baseline.

## Recommended Policy

- Use `exact_plus_baseline_estimates_kg` for conservative nominal simulations.
- Use `recommended_additive_with_review_kg` for exploratory simulations when medium-confidence non-aggregate component rows are acceptable.
- Keep `topdown_reference_only` rows visible, but do not add them to component-level baseline totals.
- Keep `scenario_only_mass` rows out of quantitative baseline unless manually validated.

## Policy Counts

- `include_exact_component`: 128 records, current mass 96.403 kg
- `topdown_reference_only`: 18 records, current mass 185.816 kg
- `include_baseline_estimate`: 17 records, current mass 23.127 kg
- `include_with_review`: 7 records, current mass 10.420 kg

## Families After Re-Audit

- `aluminium`: current 160.410 kg, recommended additive 85.032 kg, top-down reference 75.378 kg
- `textile_leather`: current 74.706 kg, recommended additive 8.404 kg, top-down reference 66.302 kg
- `polymer_plastic`: current 45.210 kg, recommended additive 12.379 kg, top-down reference 32.831 kg
- `steel`: current 11.733 kg, recommended additive 11.733 kg, top-down reference 0.000 kg
- `electronics_cots`: current 9.506 kg, recommended additive 7.128 kg, top-down reference 2.378 kg
- `titanium_carbon`: current 8.927 kg, recommended additive 0.000 kg, top-down reference 8.927 kg
- `general`: current 4.385 kg, recommended additive 4.385 kg, top-down reference 0.000 kg
- `adhesive_composite`: current 0.880 kg, recommended additive 0.880 kg, top-down reference 0.000 kg
- `copper`: current 0.006 kg, recommended additive 0.006 kg, top-down reference 0.000 kg
- `rubber_silicone`: current 0.001 kg, recommended additive 0.001 kg, top-down reference 0.000 kg

## Largest Equipment Deltas

- `ENSEMBLE COQUE`: workbook 41.031 kg, recommended additive 9.423 kg, delta -31.608 kg (-77.0%)
- `ENSEMBLE PALETTE OPTIMISEE`: workbook 13.6548069 kg, recommended additive 26.1522374 kg, delta 12.4974305 kg (91.5%)
- `ENSEMBLE STRUCTURE FIXE`: workbook 10.06629842 kg, recommended additive 5.0542004 kg, delta -5.01209802 kg (-49.8%)
- `ENS STRUCTURE FAUTEUIL`: workbook 25.8461 kg, recommended additive 22.1101 kg, delta -3.736 kg (-14.5%)
- `ACCOUDOIR ALLEE`: workbook 3.9019877 kg, recommended additive 7.6239143 kg, delta 3.7219266 kg (95.4%)
- `RENFORT TUBULAIRE`: workbook 4.171333333 kg, recommended additive 1.338 kg, delta -2.833333333 kg (-67.9%)
- `ECRAN 17,3 INCH PNR 00-5155-02`: workbook 3.428 kg, recommended additive 1.928 kg, delta -1.5 kg (-43.8%)
- `PADDING`: workbook 2.25 kg, recommended additive 0.95 kg, delta -1.3 kg (-57.8%)
- `SYSTEM IFE BOITIER`: workbook 2.5 kg, recommended additive 1.5 kg, delta -1.0 kg (-40.0%)
- `00-5136-51 Rev F Seat Power Box 4 (SPB4)`: workbook 2.5 kg, recommended additive 1.5 kg, delta -1.0 kg (-40.0%)
- `LIGHTING x3`: workbook 1.8 kg, recommended additive 0.8 kg, delta -1.0 kg (-55.6%)
- `COMMANDE ACTIONNEMENT`: workbook 1.75 kg, recommended additive 0.75 kg, delta -1.0 kg (-57.1%)

## Files

- Record audit: `C:/dev/lca-simu/analysis/output8_GEO_lca_mass_reaudit_records.csv`
- Equipment summary: `C:/dev/lca-simu/analysis/output8_GEO_lca_mass_reaudit_equipment_summary.csv`
- Family summary: `C:/dev/lca-simu/analysis/output8_GEO_lca_mass_reaudit_family_summary.csv`
- Policy summary: `C:/dev/lca-simu/analysis/output8_GEO_lca_mass_policy_summary.csv`
