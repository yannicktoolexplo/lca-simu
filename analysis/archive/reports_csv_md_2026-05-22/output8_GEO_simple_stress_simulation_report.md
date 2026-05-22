# Simple Supply Stress Simulation

- Generated at: `2026-05-22T07:17:14+00:00`
- Model: static topology only, no inventory, no capacity, no dynamic MRP.
- Mass policy: recommended additive ACV mass from `C:/dev/lca-simu/analysis/output8_GEO_lca_mass_reaudit_records.csv`.
- Fallback means: at least one secondary path avoids the disrupted node/lane/mode.
- Fallback is not automatically qualified; its validation class is retained.

## Summary

- Supplier disruption scenarios: **89**
- Lane disruption scenarios: **126**
- Transport mode scenarios: **4**
- Component impact rows: **1780**

## Top Supplier Disruptions By Mass

- `T4` `FRN-34B2AC7037114C`: 31 components, 58.922 kg, fallback coverage 100.0%, classes `candidate_requires_allocation_and_qualification=31`
- `T3` `FRN-CD09D021B366DB`: 31 components, 58.922 kg, fallback coverage 100.0%, classes `candidate_requires_allocation_and_qualification=31`
- `T1` `FRN-72A106312E8F95`: 22 components, 43.2038 kg, fallback coverage 100.0%, classes `candidate_requires_t1_t2_pairing=15;candidate_requires_allocation_and_qualification=7`
- `T2` `FRN-72A106312E8F95 - internal machining/forming process`: 15 components, 43.1565 kg, fallback coverage 0.0%, classes `no_topology_fallback=15`
- `T3` `FRN-6EF3EF62BA6339`: 7 components, 26.7708 kg, fallback coverage 85.7%, classes `candidate_requires_allocation_and_qualification=6;no_topology_fallback=1`
- `T4` `FRN-7A25E45203FCC9`: 6 components, 26.1101 kg, fallback coverage 100.0%, classes `candidate_requires_allocation_and_qualification=6`
- `T1` `FRN-45A091671294B0`: 44 components, 23.7835 kg, fallback coverage 97.7%, classes `candidate_requires_allocation_and_qualification=28;candidate_requires_t1_t2_pairing=15;no_topology_fallback=1`
- `T1` `FRN-98C883F706EF89`: 15 components, 20.0889 kg, fallback coverage 100.0%, classes `candidate_requires_t1_t2_pairing=14;candidate_requires_allocation_and_qualification=1`
- `T2` `FRN-98C883F706EF89 - internal machining/forming process`: 14 components, 20.0079 kg, fallback coverage 0.0%, classes `no_topology_fallback=14`
- `T2` `FRN-1DE52367D9D2BE`: 34 components, 14.2896 kg, fallback coverage 100.0%, classes `candidate_requires_allocation_and_qualification=30;candidate_scenario_only_mass_review=3;candidate_requires_site_validation=1`
- `T3` `FRN-0F56088BEA4986`: 31 components, 13.7166 kg, fallback coverage 64.5%, classes `candidate_requires_allocation_and_qualification=17;no_topology_fallback=11;candidate_scenario_only_mass_review=3`
- `T2` `FRN-45A091671294B0 - internal machining/forming process`: 15 components, 12.003 kg, fallback coverage 0.0%, classes `no_topology_fallback=15`

## Top Lane Disruptions By Mass

- `T4->T3` FRN-34B2AC7037114C -> FRN-CD09D021B366DB: 31 components, 58.922 kg, fallback coverage 100.0%, modes `ship|truck`
- `T1->OEM` FRN-72A106312E8F95 -> FRN-AA08AEDDCB94EB: 22 components, 43.2038 kg, fallback coverage 100.0%, modes `truck`
- `T2->T1` FRN-72A106312E8F95 - internal machining/forming process -> FRN-72A106312E8F95: 15 components, 43.1565 kg, fallback coverage 100.0%, modes `internal`
- `T3->T2` FRN-6EF3EF62BA6339 -> FRN-72A106312E8F95 - internal machining/forming process: 6 components, 26.7708 kg, fallback coverage 83.3%, modes `truck`
- `T4->T3` FRN-7A25E45203FCC9 -> FRN-6EF3EF62BA6339: 6 components, 26.1101 kg, fallback coverage 100.0%, modes `ship|truck`
- `T1->OEM` FRN-45A091671294B0 -> FRN-AA08AEDDCB94EB: 44 components, 23.7835 kg, fallback coverage 100.0%, modes `truck`
- `T1->OEM` FRN-98C883F706EF89 -> FRN-AA08AEDDCB94EB: 15 components, 20.0889 kg, fallback coverage 100.0%, modes `ship|truck`
- `T2->T1` FRN-98C883F706EF89 - internal machining/forming process -> FRN-98C883F706EF89: 14 components, 20.0079 kg, fallback coverage 100.0%, modes `internal`
- `T3->T2` FRN-CD09D021B366DB -> FRN-98C883F706EF89 - internal machining/forming process: 2 components, 18.4201 kg, fallback coverage 100.0%, modes `ship|truck`
- `T3->T2` FRN-CD09D021B366DB -> FRN-72A106312E8F95 - internal machining/forming process: 4 components, 15.123 kg, fallback coverage 100.0%, modes `truck`
- `T3->T2` FRN-0F56088BEA4986 -> FRN-1DE52367D9D2BE: 30 components, 13.7166 kg, fallback coverage 100.0%, modes `ship|truck`
- `T3->T2` FRN-CD09D021B366DB -> FRN-45A091671294B0 - internal machining/forming process: 15 components, 12.003 kg, fallback coverage 100.0%, modes `truck`

## Transport Mode Shocks

- `truck` unavailable: 170 components, 129.9495 kg, fallback coverage 0.0%, classes `no_topology_fallback=170`
- `ship` unavailable: 144 components, 115.7271 kg, fallback coverage 20.8%, classes `no_topology_fallback=114;candidate_requires_allocation_and_qualification=21;candidate_scenario_only_mass_review=9`
- `internal` unavailable: 84 components, 103.6262 kg, fallback coverage 15.5%, classes `no_topology_fallback=71;candidate_requires_allocation_and_qualification=12;candidate_requires_site_validation=1`
- `rail` unavailable: 22 components, 11.57 kg, fallback coverage 100.0%, classes `candidate_requires_allocation_and_qualification=16;candidate_requires_t1_t2_pairing=5;candidate_scenario_only_mass_review=1`

## Files

- Supplier scenarios: `C:/dev/lca-simu/analysis/output8_GEO_simple_stress_supplier_disruptions.csv`
- Lane scenarios: `C:/dev/lca-simu/analysis/output8_GEO_simple_stress_lane_disruptions.csv`
- Mode scenarios: `C:/dev/lca-simu/analysis/output8_GEO_simple_stress_transport_mode_disruptions.csv`
- Component impacts: `C:/dev/lca-simu/analysis/output8_GEO_simple_stress_component_impacts.csv`
