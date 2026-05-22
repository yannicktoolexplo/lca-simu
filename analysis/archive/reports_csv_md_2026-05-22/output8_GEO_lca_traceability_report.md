# LCA Traceability Marks

- Input JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_primary_complete.json`
- Output JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_primary_complete_lca_marked.json`
- Source workbook: `C:/dev/lca-simu/data/quantity_material.xlsx`
- Detail CSV: `C:/dev/lca-simu/analysis/output8_GEO_lca_traceability_marks.csv`
- Workbook sheets: ACV - OPERA QATAR, ACV - ANALYSE - EQUIPEMENT, ACV - ANALYSE - EQUIPEMENT (2), ACV - FOLIO - 1, CALCUL MASSE CABLE, RECAP MATIERE, BOM, FAUTEUIL, COQUE, TETIERE, ENS TABLETTE COCKTAIL, ENS TABLETTE REPAS, STOWAGE ASSEMBLE AVEC PORTE, SUPPORT ECRAN ASSEMBLE, RENFORT TUBULAIRE, HABILLAGE SOUS FAUTEUIL, ENSEMBLE PALETTE OPTIMISEE, ENSEMBLE EQUIPEMENTS LATERALES, ACCOUDOIR ALLEE, BUMPER VERSION PORTE, STRUCTURE OTTOMAN (horizontale), SUPPORT EQUIPE, ENS STOWAGE LATERAL, MANCHETTE ACC MOBILE, MANCHETTE EQUIPEE, SUPPORT MANCHETTE EQUIPEE, SUPPORT NFC, CAPOT NFC, ENS STRUCTURE FIXE, ENS PORTE, COUSSIN OTTOMAN, COUSSIN TETIERE, ENS COUSSIN DOS VERSION TETIERE, ENS COUSSIN DOSSIER, ENS COUSSIN ASSISE
- Non-packaging BOM mass: **115.966381 kg**
- Records marked: **175**

## Coverage

- Records with LCA mass: **175 / 175**

## Match Levels

- `exact_equipment_material`: 129
- `equipment_material_family`: 20
- `global_material_family`: 10
- `global_material`: 7
- `seat_total_percentage`: 5
- `equipment_material_split`: 4

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

## Simulation Use

- `quantitative_ready`: 129
- `usable_for_baseline`: 17
- `scenario_only_review_required`: 17
- `usable_with_review`: 12

## Interpretation

- `quantitative_ready`: exact equipment/material BOM mass; good for mass-weighted stress tests.
- `usable_for_baseline`: ACV/BOM family or split estimate; useful for baseline sizing.
- `usable_with_review`: percentage or broader fallback; review before sensitive analyses.
- `scenario_only_review_required`: global fallback; keep visible but do not over-interpret.
