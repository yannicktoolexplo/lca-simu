# Corrections researched simulation-ready

- Input: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_primary_complete_lca_marked.json`
- Output JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_simulation_ready_researched.json`
- Change log: `C:/dev/lca-simu/analysis/output8_GEO_simulation_ready_researched_changes.csv`
- Generated at: `2026-05-21T14:00:31+00:00`

## Actions

- `add_primary_lane_transport_scenarios`: 170
- `exclude_aggregate_from_active_network`: 3
- `exclude_combigo_from_secondary_switches`: 15
- `exclude_common_sense_incompatible_secondaries`: 44
- `fix_longhaul_transport`: 19
- `fix_material_longhaul_transport`: 5
- `set_internal_t2_process`: 29
- `set_primary_tier1`: 29
- `set_primary_tier3_first_transformation`: 19
- `set_primary_tier4_raw_material`: 19
- `split_mixed_metal_to_active_steel_flow`: 3

## Main rules applied

- Combigo is no longer active as aluminium T2 on A2017/A2024 paths.
- Combigo is removed from secondary switch scenarios, not only demoted from primary paths.
- FRMC55 paths no longer use steel upstream; they use PU foam/material packages tied to LCA suppliers.
- COTS/electronics upstream tiers are explicit non-switchable placeholders until BOM/PN/AVL is available.
- Mixed metal process labels 50/154/155 are split analytically: active steel material flow plus aluminium process reference without duplicated mass.
- Obvious material/role-incompatible secondary candidates are excluded from switch scenarios rather than kept as blocked cartesian combinations.
- Aggregate seat aluminium rows 157, 174 and 175 are excluded from the active mapped network.
- Thailand/Japan longhaul lanes no longer use truck-only T1->OEM transport.
