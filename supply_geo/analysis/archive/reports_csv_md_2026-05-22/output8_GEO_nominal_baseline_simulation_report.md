# Nominal Baseline Simulation

- Generated at: `2026-05-22T07:17:13+00:00`
- Scenario: `nominal_baseline`, no disruption, primary paths only.
- Mass policy: recommended additive ACV mass from `C:/dev/lca-simu/analysis/output8_GEO_lca_mass_reaudit_records.csv`.
- Unique primary component flows: **170**
- Duplicate identical primary rows collapsed: **2**
- Total modeled mass: **129.9495 kg**
- Total transport proxy: **1702441.0 kg.km**
- Average route length: **15481.0 km**

## Readiness

- `primary_complete_needs_validation`: **125**
- `primary_ready_topology`: **45**

## LCA Classes

- `quantitative_ready`: **128**
- `usable_for_baseline`: **17**
- `scenario_only_review_required`: **13**
- `usable_with_review`: **12**

## Mass By Family

- `aluminium`: 85.0321 kg (65.4%), 37 components, kg.km share 61.1%
- `polymer_plastic`: 12.3794 kg (9.5%), 23 components, kg.km share 17.1%
- `steel`: 11.7334 kg (9.0%), 41 components, kg.km share 9.4%
- `textile_leather`: 8.4041 kg (6.5%), 52 components, kg.km share 7.6%
- `electronics_cots`: 7.128 kg (5.5%), 8 components, kg.km share 2.4%
- `general`: 4.385 kg (3.4%), 3 components, kg.km share 1.4%
- `adhesive_composite`: 0.88 kg (0.7%), 2 components, kg.km share 0.9%
- `copper`: 0.006 kg (0.0%), 1 components, kg.km share 0.0%
- `rubber_silicone`: 0.0014 kg (0.0%), 2 components, kg.km share 0.0%
- `titanium_carbon`: 0.0 kg (0.0%), 1 components, kg.km share 0.0%

## Transport Mode Proxy

- `truck`: 892047.4 kg.km equal-split (52.4%), 581 segments
- `ship`: 799374.3 kg.km equal-split (47.0%), 278 segments
- `rail`: 11019.4 kg.km equal-split (0.6%), 32 segments
- `internal`: 0.0 kg.km equal-split (0.0%), 99 segments

## Top Suppliers By Nominal Mass

- `OEM` `FRN-AA08AEDDCB94EB`: 129.9495 kg, 170 components, families `textile_leather=52;steel=41;aluminium=37;polymer_plastic=23;electronics_cots=8;general=3;adhesive_composite=2;rubber_silicone=2;copper=1;titanium_carbon=1`
- `T3` `FRN-CD09D021B366DB`: 58.922 kg, 31 components, families `aluminium=31`
- `T4` `FRN-34B2AC7037114C`: 58.922 kg, 31 components, families `aluminium=31`
- `T1` `FRN-72A106312E8F95`: 43.2038 kg, 22 components, families `aluminium=9;polymer_plastic=7;steel=5;copper=1`
- `T2` `FRN-72A106312E8F95 - internal machining/forming process`: 43.1565 kg, 15 components, families `aluminium=9;steel=5;copper=1`
- `T3` `FRN-6EF3EF62BA6339`: 26.7708 kg, 7 components, families `aluminium=6;steel=1`
- `T4` `FRN-7A25E45203FCC9`: 26.1101 kg, 6 components, families `aluminium=6`
- `T1` `FRN-45A091671294B0`: 23.7835 kg, 44 components, families `steel=20;aluminium=15;polymer_plastic=8;textile_leather=1`
- `T1` `FRN-98C883F706EF89`: 20.0889 kg, 15 components, families `steel=12;aluminium=2;polymer_plastic=1`
- `T2` `FRN-98C883F706EF89 - internal machining/forming process`: 20.0079 kg, 14 components, families `steel=12;aluminium=2`
- `T2` `FRN-1DE52367D9D2BE`: 14.2896 kg, 34 components, families `polymer_plastic=22;textile_leather=10;adhesive_composite=1;general=1`
- `T3` `FRN-0F56088BEA4986`: 13.7166 kg, 31 components, families `polymer_plastic=20;textile_leather=10;titanium_carbon=1`

## Top Lanes By kg.km

- `T4->T3` FRN-34B2AC7037114C -> FRN-CD09D021B366DB: 449898.8 kg.km, 58.922 kg, 7635.5 km, modes `ship|truck`
- `T4->T3` FRN-7A25E45203FCC9 -> FRN-6EF3EF62BA6339: 198870.1 kg.km, 26.1101 kg, 7616.6 km, modes `ship|truck`
- `T1->OEM` FRN-98C883F706EF89 -> FRN-AA08AEDDCB94EB: 192146.7 kg.km, 20.0889 kg, 9564.8 km, modes `ship|truck`
- `T3->T2` FRN-CD09D021B366DB -> FRN-98C883F706EF89 - internal machining/forming process: 161684.3 kg.km, 18.4201 kg, 8777.6 km, modes `ship|truck`
- `T3->T2` FRN-0F56088BEA4986 -> FRN-1DE52367D9D2BE: 128856.9 kg.km, 13.7166 kg, 9394.3 km, modes `ship|truck`
- `T1->OEM` FRN-B4E809AFDBFA0B -> FRN-AA08AEDDCB94EB: 86146.6 kg.km, 9.078 kg, 9489.6 km, modes `ship|truck`
- `T2->T1` FRN-1DE52367D9D2BE -> FRN-B4E809AFDBFA0B: 82405.1 kg.km, 8.927 kg, 9231.0 km, modes `ship|truck`
- `T3->T2` FRN-83186B5AEF84D8 -> FRN-C2C13D47AFDB04: 60394.4 kg.km, 8.1213 kg, 7436.5 km, modes `ship|truck`
- `T2->T1` FRN-C2C13D47AFDB04 -> FRN-45A091671294B0: 58483.4 kg.km, 8.1213 kg, 7201.2 km, modes `ship|truck`
- `T4->T3` FRN-0B3DAD918C8F64 - fiber/polymer source assumption -> FRN-F436B1B68664EB: 30198.6 kg.km, 2.469 kg, 12231.1 km, modes `ship|truck`
- `T3->T2` FRN-F436B1B68664EB -> FRN-0B3DAD918C8F64: 30198.6 kg.km, 2.469 kg, 12231.1 km, modes `ship|truck`
- `T2->T1` FRN-0B3DAD918C8F64 -> FRN-0B41BF5B9E4B4E: 15534.8 kg.km, 2.445 kg, 6353.7 km, modes `ship|truck`

## Files

- Component flows: `C:/dev/lca-simu/analysis/output8_GEO_nominal_baseline_component_flows.csv`
- Family summary: `C:/dev/lca-simu/analysis/output8_GEO_nominal_baseline_family_summary.csv`
- Supplier load: `C:/dev/lca-simu/analysis/output8_GEO_nominal_baseline_supplier_load.csv`
- Lane flows: `C:/dev/lca-simu/analysis/output8_GEO_nominal_baseline_lane_flows.csv`
- Transport modes: `C:/dev/lca-simu/analysis/output8_GEO_nominal_baseline_transport_modes.csv`
