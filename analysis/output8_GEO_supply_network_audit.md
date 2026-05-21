# Supply network audit - Tier4 to OEM

- Source JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_corrected.json`
- Primary nodes: `C:/dev/lca-simu/analysis/output8_GEO_network_primary_nodes.csv`
- Primary edges: `C:/dev/lca-simu/analysis/output8_GEO_network_primary_edges.csv`
- All-enabled nodes: `C:/dev/lca-simu/analysis/output8_GEO_network_all_nodes.csv`
- All-enabled edges: `C:/dev/lca-simu/analysis/output8_GEO_network_all_edges.csv`
- Component gaps: `C:/dev/lca-simu/analysis/output8_GEO_network_component_gaps.csv`
- Component redundancy: `C:/dev/lca-simu/analysis/output8_GEO_network_component_redundancy.csv`
- Switch options: `C:/dev/lca-simu/analysis/output8_GEO_supplier_switch_options.csv`
- Restructuring scenarios: `C:/dev/lca-simu/analysis/output8_GEO_restructuring_scenarios.csv`

## Network sizes

- Records/components/material lines: 175
- Primary-only unique nodes: 53
- Primary-only implied edges: 549
- All-enabled unique nodes: 117
- All-enabled possible edges: 7453
- Supplier switch candidates: 2341

## Primary-only network

- Nodes by role: tier3_first_transformation=14, tier1=14, tier2_second_transformation=14, tier4_raw_material=10, oem=1
- Nodes by region: Outside_Europe=22, France=17, Europe_non_FR=14
- Edges with distance: 549/549
- Median edge distance: 832.1 km
- P90 edge distance: 9,470.8 km
- Total mass-distance proxy: 7,539,676.3 kg.km
- Missing-role counts on primary chains: tier2_second_transformation=47, tier4_raw_material=31, tier1=11, tier3_first_transformation=5

## All-enabled network

- Nodes by role: tier1=31, tier4_raw_material=30, tier3_first_transformation=29, tier2_second_transformation=26, oem=1
- Nodes by region: Outside_Europe=47, France=46, Europe_non_FR=24
- Edges with distance: 7453/7453
- Median possible edge distance: 6,084.9 km
- P90 possible edge distance: 9,724.6 km
- Total mass-distance over all possible edges: 100,965,175.1 kg.km

## Redundancy risks

- Weak roles with <=1 candidate: tier2_second_transformation=89, tier4_raw_material=39, tier3_first_transformation=28, tier1=15
- Primary chains are not always full Tier4->Tier3->Tier2->Tier1->OEM; missing Tier2 is the dominant structural gap.
- All-enabled mode increases optionality, but many alternates have no allocation share, capacity, lead time, qualification status or recovery assumption yet.

## Scenario comparison

| Scenario | Nodes | Edges | Median km | P90 km | France nodes | Europe non-FR | Outside Europe | Mass-distance kg.km |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| primary_baseline | 53 | 549 | 832.132 | 9470.757 | 17 | 14 | 22 | 7539676.276 |
| max_france | 55 | 549 | 500.42 | 8650.125 | 33 | 7 | 15 | 5555541.971 |
| max_europe | 51 | 549 | 502.395 | 7458.945 | 22 | 19 | 10 | 4129531.349 |
| nearest_downstream | 64 | 549 | 320.059 | 7310.514 | 33 | 14 | 17 | 3640775.17 |

## Switch options to review first

- R8 `tier4_raw_material` Klabin S.A. (Brazil) -> Nordic Paper (Sweden), delta distance=-10398.454 km, component=AIRVOLT LAMINAT
- R8 `tier4_raw_material` Klabin S.A. (Brazil) -> Billerud (Sweden), delta distance=-10337.789 km, component=AIRVOLT LAMINAT
- R8 `tier4_raw_material` Klabin S.A. (Brazil) -> Gascogne Papier (France), delta distance=-9658.655 km, component=AIRVOLT LAMINAT
- R33 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=4140 (acier)
- R51 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=35NC6 (nickel-chrome)
- R81 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=inox
- R94 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=inox
- R95 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=inox
- R96 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=inox
- R98 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=inox
- R99 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=inox
- R100 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=inox
- R101 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=inox
- R102 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=inox
- R138 `tier1` Senior Aerospace Thailand (Thailand) -> SUMPAR (France), delta distance=-9480.97 km, component=inox

## Recommended stress-test setup

- Start with `primary_baseline` as the reference network.
- Use `all_enabled` only as the option universe, not as simultaneous purchasing.
- For local restructuring, compare `max_france`, `max_europe`, and `nearest_downstream` scenarios.
- Add missing scenario parameters before quantitative simulation: supplier capacity, allocation share, lead time, MOQ/lot size, qualification status, recovery time, and switching penalty.
- Treat record-level masses carefully: material/detail rows and aggregate `Siege` rows coexist, so do not sum all records as a seat total without choosing one aggregation level.
