# Case data update report

## Summary

- Updated graph: `etudecas\donnees\supply_graph_poc.json`
- Created items: 0
- Removed orphan items: 0
- Created nodes: 0
- Created edges: 0
- Created processes: 0
- Synced processes: 0
- Updated edges from FIA: 0
- Updated node locations: 0

## Workbook findings

- `021081.xlsx` -> output `n/a` (BOM rows=0, FIA rows=0, file/product mismatch=False)
- `268191.xlsx` -> output `268091` (BOM rows=0, FIA rows=23, file/product mismatch=False)
- `268967.xlsx` -> output `n/a` (BOM rows=0, FIA rows=0, file/product mismatch=False)

## Important assumptions

- `268191.xlsx` is interpreted as product `268091` because the BOM sheet explicitly points to `268091`.
- `021081.xlsx` is modeled as an upstream component feeding internal site `D-1450` (technical id `SDC-1450`), which transforms `021081` into `773474` before delivery to downstream factories.
- `D-1450` is typed as an internal PFI site (`factory`) and its transformation capacity is set to 500000 G/day to avoid creating an artificial bottleneck.
- FIA lead times are applied directly to lanes, and delay limits are set to `max(lead + 14, 2 * lead)` as a simulation cap assumption.
- Component `007923` is the active BOM component kept for `268091`; `Data_poc.xlsx` still shows the former reference `693710`, but the product workbook `268191.xlsx` is treated as the operational source of truth.
- Component `007923` remains unconstrained because no supplier lane is provided in the new FIA data.

## Unresolved points

- No destination node found for workbook 021081.xlsx / output .
- No destination node found for workbook 268967.xlsx / output .
