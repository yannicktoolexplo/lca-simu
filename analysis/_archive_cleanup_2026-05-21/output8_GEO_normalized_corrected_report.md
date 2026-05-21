# Corrected output8_GEO_normalized.json

- Source: `C:/dev/lca-simu/analysis/output8_GEO_normalized.json`
- Corrected JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_corrected.json`
- Changes CSV: `C:/dev/lca-simu/analysis/output8_GEO_normalized_corrected_changes.csv`
- Generated at: `2026-05-20T12:10:17+00:00`

## Scope

- Records: 175 -> 175
- Supplier entries in original `suppliers`: 3866
- Supplier entries after cleaning: 3047
- OEM/internal site entries moved to `oem_sites`: 177
- Logistics entries moved to `logistics_providers`: 64
- Change log rows: 4863

## Main corrections

- Mass zeros changed to `null`: 160
- Empty market shares changed to `null`: 175
- Raw materials inferred from component labels: 156
- OEM entries removed from external suppliers: 237
- Logistics entries removed from external suppliers: 64

## Remaining limitations

- Records with missing market share: 175
- Records with missing mass: 160
- Supplier coordinates still missing because no verified site was available: 74
- Supplier coordinates outside declared country after cleaning: 0
- Supplier coordinates still at country centroid after cleaning: 0
- Role groups without exactly one baseline primary supplier: 0

## Simulation readiness note

The corrected file is cleaner for mapping and scenario design, but it is still not a full stress-test model. Before quantitative stress tests, fill `mass_kg`, `market_share_pct` or supplier allocation shares, lead times, capacities, safety stocks, and recovery assumptions from BOM/ERP/logistics sources.
