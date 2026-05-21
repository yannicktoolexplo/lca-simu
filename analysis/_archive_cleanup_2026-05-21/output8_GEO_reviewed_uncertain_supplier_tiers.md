# Review of uncertain supplier tiers

- Input: `C:/dev/lca-simu/analysis/output8_GEO_meaningful_supplier_tiers.csv`
- Reviewed rows: `C:/dev/lca-simu/analysis/output8_GEO_reviewed_uncertain_supplier_tiers.csv`
- Source registry: `C:/dev/lca-simu/analysis/output8_GEO_reviewed_uncertain_supplier_sources.csv`

## Summary

- Rows reviewed: 81
- Review status: validated_supplier=41, needs_business_validation=9, cots_brand_not_supply_node=7, generic_placeholder=4, validated_supplier_with_scope_issue=4, wrong_scope_or_unrelated=4, validated_supplier_cots_upstream=3, validated_supplier_with_component_scope_issue=2, packaging_or_paper_auxiliary=2, industry_association_not_supplier=1, legacy_or_defunct_supplier=1, not_verified_probable_error=1, wrong_scope_or_too_broad=1, duplicate_normalization=1
- Recommended tier/action target: T2=30, T3=17, T4=16, T1=16, PKG=2
- Actions: keep=18, normalize_name=11, keep_with_product_scope_check=7, remove_replace_with_named_supplier=4, verify_exact_legal_entity_and_site=4, verify_exact_legal_entity_and_product=4, demote_to_electronics_cots_upstream=3, keep_with_aerospace_scope_check=2, move_to_packaging_or_auxiliary_flow=2, remove_unless_product_traceability_exists=2, remove_unless_material_traceability_exists=2, keep_or_reclassify_T3_composites=2, replace_with_exact_component_supplier=2, keep_with_source_check=1, keep_only_for_polymer_records=1, keep_only_for_chemical_or_composite_records=1, remove_from_supplier_network=1, keep_with_scope_check=1, keep_as_leather_distributor_if_traceable=1, replace_with_exact_part_supplier_or_distributor=1, verify_exact_supplier=1, replace_with_current_legal_entity=1, keep_only_with_product_traceability=1, keep_with_material_scope_check=1, normalize_or_remove=1, remove_or_replace_with_JAMCO_if_intended=1, demote_or_remove_unless_exact_display_supplier=1, remove_unless_exact_GE_aerospace_product=1, demote_or_remove_unless_exact_product=1, merge_with_ESPACE=1, demote_or_remove_unless_exact_part=1

## Main decisions

- Keep validated real suppliers, but attach scope notes when the supplier is real yet not valid for every component row.
- Remove generic placeholders such as `Polymere`, `Aluminium`, `Velours`, `Tissus:` from the supplier network.
- Move paper/packaging groups such as Mondi or Smurfit Kappa to packaging/auxiliary unless the paper is explicitly part of the seat material.
- Demote generic electronics brands/foundries to COTS-upstream context unless an exact part supplier is known.
- Normalize noisy names: `Mexichem -> Orbia`, `Toschiba-Shinetsu -> Shin-Etsu Silicones`, `Tyco Electronic -> TE Connectivity`, `Sekisui SPI -> SEKISUI KYDEX`.

## Remove / replace first

- T4 `Polymère`: generic_placeholder - Generic material label, not a supplier. Replace with named polymer producer from purchasing/BOM.
- T4 `Aluminium`: generic_placeholder - Generic material label, not a supplier. Replace with Alcoa/Hindalco/Chalco/Constellium/etc. according to traceability.
- T3 `Velours`: generic_placeholder - Generic material label, not a supplier.
- T3 `La Filière Française du cuir`: industry_association_not_supplier - Industry association/channel, useful for sourcing context but not a supplier node.
- T3 `Tissus:`: generic_placeholder - Generic material label, not a supplier.
- T2 `Valco Group`: wrong_scope_or_unrelated - Industrial valve group; not coherent for listed plastics/resin/leather records without product proof.
- T2 `Balterio`: wrong_scope_or_unrelated - Laminate flooring brand; not a credible aerospace-seat supplier without material traceability.
- T2 `Pergo`: wrong_scope_or_unrelated - Flooring laminate brand; not credible as aerospace-seat supply node without traceability.
- T2 `Racelogic`: wrong_scope_or_unrelated - Data logger/vehicle testing supplier does not fit cable bracket record without exact product proof.
- T1 `JAMMY Inc`: not_verified_probable_error - Not verifiable as aerospace-seat supplier; likely typo/noise.

## Highest exposure reviewed rows

- T3 `Tissu Huddersfield` -> T3, status=validated_supplier, exposure=68.848552355 kg, action=normalize_name
- T3 `Paragon Textiles` -> T3, status=needs_business_validation, exposure=68.749552355 kg, action=verify_exact_legal_entity_and_site
- T2 `A Tech Supply APS` -> T2, status=needs_business_validation, exposure=34.384931413 kg, action=verify_exact_legal_entity_and_product
- T2 `Auberon technologie` -> T2, status=validated_supplier, exposure=34.384931413 kg, action=normalize_name
- T2 `Innoptec` -> T2, status=validated_supplier, exposure=34.384931413 kg, action=keep
- T2 `Plastiform` -> T2, status=validated_supplier, exposure=12.09 kg, action=keep
- T2 `STECO` -> T2, status=needs_business_validation, exposure=9.319 kg, action=verify_exact_legal_entity_and_site
- T1 `THALES` -> T1, status=validated_supplier, exposure=6.485 kg, action=keep_with_product_scope_check
- T1 `JAMMY Inc` -> T1, status=not_verified_probable_error, exposure=6.435 kg, action=remove_or_replace_with_JAMCO_if_intended
- T4 `Polymère` -> T4, status=generic_placeholder, exposure=4.756 kg, action=remove_replace_with_named_supplier
- T2 `SONY` -> T2, status=cots_brand_not_supply_node, exposure=4.756 kg, action=replace_with_exact_part_supplier_or_distributor
- T1 `Continental` -> T1, status=cots_brand_not_supply_node, exposure=4.756 kg, action=demote_or_remove_unless_exact_display_supplier
- T4 `ChemChina` -> T4, status=validated_supplier, exposure=3.661 kg, action=keep
- T4 `Mexichem` -> T4, status=validated_supplier, exposure=3.661 kg, action=normalize_name
- T4 `Shandong Loyal Chemical Co., Ltd.` -> T4, status=validated_supplier, exposure=3.661 kg, action=keep_with_source_check
- T2 `Sekisui SPI (Kydex)` -> T2, status=validated_supplier, exposure=3.651 kg, action=normalize_name
- T1 `General Electric` -> T1, status=wrong_scope_or_too_broad, exposure=3.3664 kg, action=remove_unless_exact_GE_aerospace_product
- T2 `Racelogic` -> T2, status=wrong_scope_or_unrelated, exposure=3.365 kg, action=remove_unless_product_traceability_exists
- T1 `Honeywell` -> T1, status=validated_supplier_with_scope_issue, exposure=3.365 kg, action=keep_with_product_scope_check
- T1 `SCHNEIDER` -> T1, status=cots_brand_not_supply_node, exposure=3.365 kg, action=demote_or_remove_unless_exact_part
