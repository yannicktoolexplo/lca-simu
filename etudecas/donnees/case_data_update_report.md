# Case data update report

## Summary

- Updated graph: `etudecas\donnees\supply_graph_poc.json`
- Created items: 0
- Removed orphan items: 0
- Created nodes: 3
- Created edges: 0
- Created processes: 0
- Synced processes: 3
- Updated edges from FIA: 33
- Updated node locations: 0
- Opening open orders resolved: 88
- Opening open orders skipped: 16

## Workbook findings

- `021081.xlsx` -> output `773474` (BOM rows=1, FIA rows=4, file/product mismatch=True)
- `268191.xlsx` -> output `268091` (BOM rows=15, FIA rows=21, file/product mismatch=False)
- `268967.xlsx` -> output `268967` (BOM rows=8, FIA rows=8, file/product mismatch=False)

## Important assumptions

- `268191.xlsx` is interpreted as product `268091` because the BOM sheet explicitly points to `268091`.
- `021081.xlsx` is modeled as an upstream component feeding internal site `D-1450` (technical id `SDC-1450`), which transforms `021081` into `773474` before delivery to downstream factories.
- `D-1450` is typed as an internal PFI site (`factory`). No process capacity is provided in the source data, so no artificial daily capacity is injected.
- FIA lead times are applied directly to lanes, and delay limits are set to `max(lead + 14, 2 * lead)` as a simulation cap assumption.
- Component `007923` is the active BOM component kept for `268091`; `Data_poc.xlsx` still shows the former reference `693710`, but the product workbook `268191.xlsx` is treated as the operational source of truth.
- Component `007923` remains unconstrained because no supplier lane is provided in the new FIA data.

## Unresolved points

- Opening open-order row 5 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 6 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 9 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 10 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 11 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 12 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 13 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 16 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 17 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 18 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 20 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 21 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 45 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 46 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 70 skipped (unmapped_or_missing_division:1820).
- Opening open-order row 71 skipped (unmapped_or_missing_division:1820).
- Removed orphan inventory state M-1430/item:001848 because no inbound lane is provided.
- Removed orphan inventory state M-1810/item:007923 because no inbound lane is provided.
- Removed orphan inventory state SDC-VD0956464A/item:007923 because no inbound lane is provided.
- Removed orphan inventory state SDC-VD0518550B/item:049371 because no inbound lane is provided.
- Removed orphan inventory state SDC-VD0525906A/item:734545 because no inbound lane is provided.
