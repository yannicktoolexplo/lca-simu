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
- Remove generic placeholders such as `Polymere`, `Aluminium`, `Velours`, `FRN-C8F1EAD07EF6EA` from the supplier network.
- Move paper/packaging groups such as FRN-A982B812225B13 or FRN-52D7A4109CB90E to packaging/auxiliary unless the paper is explicitly part of the seat material.
- Demote generic electronics brands/foundries to COTS-upstream context unless an exact part supplier is known.
- Normalize noisy names: `FRN-DA064DA90071AA -> Orbia`, `FRN-1E191B6E8030DB -> FRN-332F92E4BA4B00`, `FRN-338328B0A1AC92 -> FRN-B9C4C86C42C8B4`, `Sekisui SPI -> FRN-86B55CBC7AFCE9`.

## Remove / replace first

- T4 `Polymère`: generic_placeholder - Generic material label, not a supplier. Replace with named polymer producer from purchasing/BOM.
- T4 `Aluminium`: generic_placeholder - Generic material label, not a supplier. Replace with FRN-34B2AC7037114C/FRN-191F6AC0669F77/FRN-7A25E45203FCC9/FRN-798BE9ED657B85/etc. according to traceability.
- T3 `Velours`: generic_placeholder - Generic material label, not a supplier.
- T3 `FRN-E857FD00FA3A46`: industry_association_not_supplier - Industry association/channel, useful for sourcing context but not a supplier node.
- T3 `FRN-C8F1EAD07EF6EA`: generic_placeholder - Generic material label, not a supplier.
- T2 `FRN-98FB52FC24BF7A`: wrong_scope_or_unrelated - Industrial valve group; not coherent for listed plastics/resin/leather records without product proof.
- T2 `FRN-0A6EA63B8561C3`: wrong_scope_or_unrelated - Laminate flooring brand; not a credible aerospace-seat supplier without material traceability.
- T2 `FRN-045ADA837ADDB0`: wrong_scope_or_unrelated - Flooring laminate brand; not credible as aerospace-seat supply node without traceability.
- T2 `FRN-D07D31613908BE`: wrong_scope_or_unrelated - Data logger/vehicle testing supplier does not fit cable bracket record without exact product proof.
- T1 `FRN-E8268BC81624C2`: not_verified_probable_error - Not verifiable as aerospace-seat supplier; likely typo/noise.

## Highest exposure reviewed rows

- T3 `FRN-D9805DB47110D5` -> T3, status=validated_supplier, exposure=68.848552355 kg, action=normalize_name
- T3 `FRN-BF4B1E88874E39` -> T3, status=needs_business_validation, exposure=68.749552355 kg, action=verify_exact_legal_entity_and_site
- T2 `FRN-0D8AFB8AB6CBCA` -> T2, status=needs_business_validation, exposure=34.384931413 kg, action=verify_exact_legal_entity_and_product
- T2 `FRN-A98036B11DAF17` -> T2, status=validated_supplier, exposure=34.384931413 kg, action=normalize_name
- T2 `FRN-EAF03ECECB6231` -> T2, status=validated_supplier, exposure=34.384931413 kg, action=keep
- T2 `FRN-664F9D3A953246` -> T2, status=validated_supplier, exposure=12.09 kg, action=keep
- T2 `FRN-7A1F937DE08462` -> T2, status=needs_business_validation, exposure=9.319 kg, action=verify_exact_legal_entity_and_site
- T1 `FRN-DE6523078882AF` -> T1, status=validated_supplier, exposure=6.485 kg, action=keep_with_product_scope_check
- T1 `FRN-E8268BC81624C2` -> T1, status=not_verified_probable_error, exposure=6.435 kg, action=remove_or_replace_with_JAMCO_if_intended
- T4 `Polymère` -> T4, status=generic_placeholder, exposure=4.756 kg, action=remove_replace_with_named_supplier
- T2 `FRN-002EAED5EB16E6` -> T2, status=cots_brand_not_supply_node, exposure=4.756 kg, action=replace_with_exact_part_supplier_or_distributor
- T1 `Continental` -> T1, status=cots_brand_not_supply_node, exposure=4.756 kg, action=demote_or_remove_unless_exact_display_supplier
- T4 `FRN-8C9D165AC08887` -> T4, status=validated_supplier, exposure=3.661 kg, action=keep
- T4 `FRN-DA064DA90071AA` -> T4, status=validated_supplier, exposure=3.661 kg, action=normalize_name
- T4 `FRN-4C5D687CCB33A2` -> T4, status=validated_supplier, exposure=3.661 kg, action=keep_with_source_check
- T2 `FRN-EF424F32D1E80A` -> T2, status=validated_supplier, exposure=3.651 kg, action=normalize_name
- T1 `FRN-1BDCFA9C2C8341` -> T1, status=wrong_scope_or_too_broad, exposure=3.3664 kg, action=remove_unless_exact_GE_aerospace_product
- T2 `FRN-D07D31613908BE` -> T2, status=wrong_scope_or_unrelated, exposure=3.365 kg, action=remove_unless_product_traceability_exists
- T1 `FRN-AB3EB7C0CECDE9` -> T1, status=validated_supplier_with_scope_issue, exposure=3.365 kg, action=keep_with_product_scope_check
- T1 `FRN-CF3EA93B7C15EE` -> T1, status=cots_brand_not_supply_node, exposure=3.365 kg, action=demote_or_remove_unless_exact_part
