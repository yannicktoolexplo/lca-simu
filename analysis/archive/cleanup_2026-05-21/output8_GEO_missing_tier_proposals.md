# Missing tier candidate proposals

- Source JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_corrected.json`
- Proposal JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_with_missing_tier_proposals.json`
- Proposal CSV: `C:/dev/lca-simu/analysis/output8_GEO_missing_tier_proposals.csv`

## Principle

These are candidate tier completions, not validated production suppliers.
They are stored outside `suppliers` so they do not become active switch options until a buyer, BOM, drawing, or route validates them.

## Counts

- Records analysed: 175
- Proposal rows: 94
- By missing tier: T2=47, T4=31, T1=11, T3=5
- By confidence: medium_high=43, medium=26, low=15, medium_low=10

## Modeling Actions

- `model_as_internalized_T2_at_T1_or_validate_subcontractor`: 43
- `add_material_family_T4_after_material_spec_validation`: 17
- `manual_validation_required`: 7
- `candidate_only_until_part_number_supplier_validation`: 5
- `validate_program_supplier_or_model_as_internal_Safran_operation`: 4
- `keep_as_COTS_upstream_context_not_supply_tier`: 3
- `select_existing_material_processor_based_on_grade_and_traceability`: 3
- `keep_gap_bridge_until_purchase_or_routing_data`: 3
- `keep_out_of_switchable_supplier_network_until_exact_BOM`: 2
- `candidate_only_until_silicone_grade_traceability`: 2
- `choose_steelmaker_by_grade_certificate_before_activation`: 2
- `choose_candidate_by_material_grade_before_activation`: 1
- `add_candidate_only_after_process_and_part_traceability`: 1
- `split_material_before_supplier_activation`: 1

## High/Medium-High Confidence Examples

- R1 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R2 `15CDV6 (chrome, molibdene, vanadium)` T2: MGA Villeneuve St Lot - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R5 `alliage Cu` T2: SUMPAR - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R13 `30NCD6 (nickel-chrome- molibdene)` T2: SUMPAR - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R14 `35NC6 (nickel-chrome)` T2: SUMPAR - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R16 `35NC6 (nickel-chrome)` T2: ETS Gattefin - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R29 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R30 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R31 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R33 `4140 (acier)` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R34 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R35 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R36 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R37 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R38 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R39 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R40 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R41 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R42 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R43 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R44 `A6060 - Aluminium` T2: Groupe Segnere / SEGNERE Ade - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R50 `de: aluminium cast part machining + tth compris dans le steel tinplated` T2: SUMPAR - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R51 `35NC6 (nickel-chrome)` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R66 `Alu` T2: SUMPAR - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R67 `Alu` T2: SUMPAR - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R68 `Alu` T2: SUMPAR - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R69 `A5086 - Aluminium` T2: ESPACE - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R70 `Alu` T2: SUMPAR - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R81 `inox` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R94 `inox` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R95 `inox` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R96 `inox` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R98 `inox` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R99 `inox` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R100 `inox` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R101 `inox` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R102 `inox` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R116 `35NC6 (nickel-chrome)` T2: MGA Villeneuve St Lot - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R123 `Alu` T2: SUMPAR - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R138 `inox` T2: Senior Aerospace Thailand - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R154 `de: aluminium cast part machining glo: steel sheet stamping and bending` T2: SUMPAR - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R155 `de: aluminium cast part machining glo: steel sheet stamping and bending` T2: SUMPAR - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor
- R161 `65% aluminium` T2: JAMCO Aircraft Interiors - Niigata - machining/forming process owner - model_as_internalized_T2_at_T1_or_validate_subcontractor

## Recommended Use

- Keep the current final JSON as the validated simulation base.
- Use this file to prioritize purchasing/engineering validation of missing tiers.
- Promote a proposal into `suppliers` only after exact site, role, allocation, lead time, capacity, and qualification are known.
- For metal rows missing T2, prefer modeling a T1-internal process unless a separate machining/forming subcontractor is documented.
