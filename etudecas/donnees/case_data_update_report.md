# Case data update report

## Summary

- Updated graph: `etudecas/donnees/supply_graph_poc.json`
- Created items: 0
- Removed orphan items: 1
- Created nodes: 0
- Created edges: 0
- Created processes: 0
- Synced processes: 3
- Updated edges from FIA: 33
- Updated node locations: 0

## Workbook findings

- `021081.xlsx` -> output `773474` (BOM rows=1, FIA rows=4, file/product mismatch=True)
- `268191.xlsx` -> output `268091` (BOM rows=15, FIA rows=21, file/product mismatch=False)
- `268967.xlsx` -> output `268967` (BOM rows=8, FIA rows=8, file/product mismatch=False)

## Important assumptions

- `268191.xlsx` is interpreted as product `268091` because the BOM sheet explicitly points to `268091`.
- `021081.xlsx` is modeled as an upstream component feeding supplier `SDC-1450`, which now transforms `021081` into `773474` before delivery to `M-1430`.
- The new `SDC-1450` transformation capacity is set to 500000 G/day to avoid creating an artificial bottleneck.
- FIA lead times are applied directly to lanes, and delay limits are set to `max(lead + 14, 2 * lead)` as a simulation cap assumption.
- Component `007923` is kept in the 268091 BOM but left unconstrained because no supplier lane is provided in the new FIA data.

## Unresolved points

- Removed orphan inventory state M-1810/item:007923 because no inbound lane is provided.
