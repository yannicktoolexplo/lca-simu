# Secondary Candidate Test Simulation

- Generated at: `2026-05-22T07:17:15+00:00`
- Scenario: secondary candidates as topology-only test alternatives.
- Mass policy: recommended additive ACV mass from `C:/dev/lca-simu/analysis/output8_GEO_lca_mass_reaudit_records.csv`.
- Important: candidate mass is counted once per scenario path; totals are scenario-universe metrics, not physical BOM totals.

## Summary

- Secondary candidate paths tested: **24620**
- Components with at least one secondary candidate: **168**
- Components with a preferred topology candidate: **142**
- Components requiring at least one paired T1/T2 option: **69**
- Components with at least one lower kg.km candidate than primary: **130**

## Switch Classes

- `candidate_requires_allocation_and_qualification`: 10110 paths, 142 components, lower kg.km count 3846
- `candidate_requires_t1_t2_pairing`: 6427 paths, 69 components, lower kg.km count 2606
- `candidate_requires_material_certificate`: 5582 paths, 75 components, lower kg.km count 735
- `candidate_requires_material_source`: 332 paths, 4 components, lower kg.km count 320
- `candidate_requires_site_validation`: 2 paths, 1 components, lower kg.km count 0
- `candidate_scenario_only_mass_review`: 2167 paths, 12 components, lower kg.km count 0

## Top Components By Candidate Count

- record `106` `kydex`: 419 candidates, best `candidate_requires_allocation_and_qualification` delta -89.7%, shortest `candidate_requires_allocation_and_qualification` delta -89.7%
- record `105` `kydex`: 419 candidates, best `candidate_requires_allocation_and_qualification` delta -89.7%, shortest `candidate_requires_allocation_and_qualification` delta -89.7%
- record `107` `kydex`: 419 candidates, best `candidate_requires_allocation_and_qualification` delta -89.7%, shortest `candidate_requires_allocation_and_qualification` delta -89.7%
- record `109` `kydex`: 419 candidates, best `candidate_requires_allocation_and_qualification` delta -89.7%, shortest `candidate_requires_allocation_and_qualification` delta -89.7%
- record `103` `kydex`: 419 candidates, best `candidate_requires_allocation_and_qualification` delta -89.7%, shortest `candidate_requires_allocation_and_qualification` delta -89.7%
- record `108` `kydex`: 419 candidates, best `candidate_requires_allocation_and_qualification` delta -89.7%, shortest `candidate_requires_allocation_and_qualification` delta -89.7%
- record `104` `kydex`: 419 candidates, best `candidate_requires_allocation_and_qualification` delta -89.7%, shortest `candidate_requires_allocation_and_qualification` delta -89.7%
- record `158` `Tissu, mousse, polyéthylène`: 391 candidates, best `candidate_scenario_only_mass_review` delta 0.0%, shortest `candidate_scenario_only_mass_review` delta 0.0%
- record `168` `Tissu, mousse, polyéthylène`: 391 candidates, best `candidate_scenario_only_mass_review` delta 0.0%, shortest `candidate_scenario_only_mass_review` delta 0.0%
- record `169` `Tissu, mousse, polyéthylène`: 391 candidates, best `candidate_scenario_only_mass_review` delta 0.0%, shortest `candidate_scenario_only_mass_review` delta 0.0%
- record `72` `acier`: 339 candidates, best `candidate_requires_allocation_and_qualification` delta -4.0%, shortest `candidate_requires_material_certificate` delta -4.7%
- record `122` `acier`: 339 candidates, best `candidate_requires_allocation_and_qualification` delta -4.0%, shortest `candidate_requires_material_certificate` delta -4.7%
- record `46` `acier`: 339 candidates, best `candidate_requires_allocation_and_qualification` delta -4.0%, shortest `candidate_requires_material_certificate` delta -4.7%
- record `56` `acier`: 339 candidates, best `candidate_requires_allocation_and_qualification` delta -4.0%, shortest `candidate_requires_material_certificate` delta -4.7%

## Top Supplier Exposure In Secondary Universe

- `T2` `SCHROTH Safety Products`: 7034 candidate paths, 30 components, classes `candidate_requires_material_certificate=5185;candidate_requires_allocation_and_qualification=1849`
- `T3` `Toray Industries`: 4418 candidate paths, 30 components, classes `candidate_requires_allocation_and_qualification=4301;candidate_scenario_only_mass_review=117`
- `T3` `thyssenkrupp Materials France`: 3231 candidate paths, 75 components, classes `candidate_requires_t1_t2_pairing=1426;candidate_requires_material_certificate=1386;candidate_requires_allocation_and_qualification=419`
- `T4` `BASF`: 2870 candidate paths, 46 components, classes `candidate_requires_allocation_and_qualification=1831;candidate_scenario_only_mass_review=1039`
- `T2` `DuPont de Nemours`: 2431 candidate paths, 61 components, classes `candidate_requires_allocation_and_qualification=1778;candidate_scenario_only_mass_review=544;candidate_requires_material_source=108;candidate_requires_site_validation=1`
- `T3` `EXSTO / Baule-Exsto Polymere`: 2384 candidate paths, 24 components, classes `candidate_requires_allocation_and_qualification=2096;candidate_scenario_only_mass_review=288`
- `T2` `Senior Aerospace Thailand - internal machining/forming process`: 2339 candidate paths, 14 components, classes `candidate_requires_t1_t2_pairing=2106;candidate_requires_material_certificate=182;candidate_requires_allocation_and_qualification=51`
- `T1` `MGA Villeneuve St Lot`: 2266 candidate paths, 123 components, classes `candidate_requires_allocation_and_qualification=1120;candidate_requires_t1_t2_pairing=698;candidate_requires_material_certificate=343;candidate_requires_material_source=84;candidate_scenario_only_mass_review=21`
- `T2` `ESPACE - internal machining/forming process`: 2235 candidate paths, 15 components, classes `candidate_requires_t1_t2_pairing=2025;candidate_requires_allocation_and_qualification=135;candidate_requires_material_certificate=75`
- `T3` `Aubert & Duval`: 2195 candidate paths, 38 components, classes `candidate_requires_material_certificate=1366;candidate_requires_t1_t2_pairing=507;candidate_requires_allocation_and_qualification=322`
- `T3` `Altec Etirage`: 2187 candidate paths, 34 components, classes `candidate_requires_material_certificate=1349;candidate_requires_t1_t2_pairing=500;candidate_requires_allocation_and_qualification=338`
- `T3` `Krupp`: 2168 candidate paths, 33 components, classes `candidate_requires_material_certificate=1344;candidate_requires_t1_t2_pairing=488;candidate_requires_allocation_and_qualification=336`

## Files

- Candidate paths: `C:/dev/lca-simu/analysis/output8_GEO_secondary_test_candidate_path_flows.csv`
- Component summary: `C:/dev/lca-simu/analysis/output8_GEO_secondary_test_component_summary.csv`
- Switch class summary: `C:/dev/lca-simu/analysis/output8_GEO_secondary_test_switch_class_summary.csv`
- Supplier exposure: `C:/dev/lca-simu/analysis/output8_GEO_secondary_test_supplier_exposure.csv`
