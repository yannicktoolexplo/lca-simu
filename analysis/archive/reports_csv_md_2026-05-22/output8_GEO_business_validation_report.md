# Business Assumption Validation

- Generated at: `2026-05-21T14:33:23+00:00`
- Path rows audited: **24792**
- Supplier switch options audited: **244**
- Critical/visible transport lanes listed: **5264**

## Interpretation

The graph is topologically usable. This audit does not certify purchasing truth; it tells which evidence is still needed before a candidate path can be activated in stress tests.

## Path Status

- `secondary_candidate_business_validation_needed`: **18193**
- `secondary_candidate_pair_switch_required`: **6427**
- `baseline_usable_business_validation_needed`: **127**
- `simulation_ready_topology_business_check_light`: **45**

## Families

- `steel`: **8749** path rows
- `textile_leather`: **6166** path rows
- `aluminium`: **4878** path rows
- `polymer_plastic`: **4801** path rows
- `general`: **99** path rows
- `rubber_silicone`: **36** path rows
- `electronics_cots`: **33** path rows
- `adhesive_composite`: **16** path rows
- `copper`: **12** path rows
- `titanium_carbon`: **2** path rows

## Main Validation Gates

- `lead_time_required`: **24766** occurrences
- `allocation_required`: **24620** occurrences
- `longhaul_transport_lane_check`: **23435** occurrences
- `switch_candidate_qualification_material_and_process`: **13560** occurrences
- `material_certificate_required`: **8592** occurrences
- `internal_process_t1_pairing_required`: **6427** occurrences
- `switch_candidate_qualification_cabin_trim`: **6147** occurrences
- `material_source_and_fst_required`: **6004** occurrences
- `material_certificate_check`: **5049** occurrences
- `grade_and_process_datasheet_required`: **4817** occurrences
- `switch_candidate_qualification_polymer_process`: **4792** occurrences
- `soft_goods_fst_required`: **198** occurrences
- `baseline_allocation_assumption`: **112** occurrences
- `material_definition_review`: **99** occurrences
- `switch_candidate_qualification_role_review`: **96** occurrences
- `baseline_qualification_material_and_process`: **81** occurrences

## Supplier Switch Risk

- `high`: **131** supplier/family/tier options
- `medium`: **113** supplier/family/tier options

## Transport Lanes To Review

- `high`: **3288** lanes
- `medium`: **923** lanes
- `critical`: **888** lanes
- `low`: **165** lanes

## Action Backlog

- `path_validation`: **40** actions
- `transport_lane`: **40** actions
- `supplier_switch`: **40** actions

## Top Critical Lanes

- `critical` `T1->OEM` JAMCO Aircraft Interiors - Niigata -> Safran Seats / Safran internal group (9489.6 km, modes `ship|truck`, kg.km proxy 14790378.2)
- `critical` `T3->T2` thyssenkrupp Materials France -> JAMCO Aircraft Interiors - Niigata - internal machining/forming process (9495.7 km, modes `ship|truck`, kg.km proxy 11452292.4)
- `critical` `T3->T2` Aluminium France -> JAMCO Aircraft Interiors - Niigata - internal machining/forming process (9493.4 km, modes `ship|truck`, kg.km proxy 11449518.5)
- `critical` `T3->T2` Euralliage Ile de France -> JAMCO Aircraft Interiors - Niigata - internal machining/forming process (9453.8 km, modes `ship|truck`, kg.km proxy 11401758.9)
- `critical` `T1->OEM` JAMCO Philippines Inc. -> Safran Seats / Safran internal group (10691.9 km, modes `ship|truck`, kg.km proxy 9671227.4)
- `critical` `T1->OEM` JAMCO Aircraft Interiors - Miyazaki -> Safran Seats / Safran internal group (9734.7 km, modes `ship|truck`, kg.km proxy 8805403.8)
- `critical` `T1->OEM` JAMCO Aircraft Interiors - Niigata -> Safran Seats / Safran internal group (9489.6 km, modes `ship|truck`, kg.km proxy 8583701.6)
- `critical` `T1->OEM` JAMCO Philippines Inc. -> Safran Seats / Safran internal group (10691.9 km, modes `ship|truck`, kg.km proxy 8332134.4)
- `critical` `T1->OEM` JAMCO Aircraft Interiors - Miyazaki -> Safran Seats / Safran internal group (9734.7 km, modes `ship|truck`, kg.km proxy 7586194.1)
- `critical` `T1->OEM` JAMCO Aircraft Interiors - Niigata -> Safran Seats / Safran internal group (9489.6 km, modes `ship|truck`, kg.km proxy 7395189.1)
- `critical` `T2->T1` JAMCO Aircraft Interiors - Niigata - internal machining/forming process -> J&C Aero (7960.9 km, modes `internal`, kg.km proxy 7200934.7)
- `critical` `T2->T1` DuPont de Nemours -> JAMCO Aircraft Interiors - Niigata (10811.2 km, modes `ship|truck`, kg.km proxy 5616736.1)

## Files

- Path validation: `C:/dev/lca-simu/analysis/output8_GEO_business_validation_path_audit.csv`
- Supplier matrix: `C:/dev/lca-simu/analysis/output8_GEO_business_validation_supplier_matrix.csv`
- Critical lanes: `C:/dev/lca-simu/analysis/output8_GEO_business_validation_critical_lanes.csv`
- Component summary: `C:/dev/lca-simu/analysis/output8_GEO_business_validation_component_summary.csv`
- Action backlog: `C:/dev/lca-simu/analysis/output8_GEO_business_validation_action_backlog.csv`
