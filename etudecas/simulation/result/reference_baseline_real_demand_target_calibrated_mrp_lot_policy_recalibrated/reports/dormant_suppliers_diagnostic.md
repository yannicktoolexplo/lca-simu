# Dormant Suppliers Diagnostic

## Scope

This note audits the following suppliers identified as dormant or quasi-dormant in the current canonical run:

- `SDC-VD0990780A`
- `SDC-VD0500655A`
- `SDC-VD0518684A`
- `SDC-VD0914320A`
- `SDC-VD0949099A`
- `SDC-VD0960508A`
- `SDC-VD0964290A`
- `SDC-VD0972460A`
- `SDC-VD0975221A`
- `SDC-VD1096202A`

Run audited:

- `etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated`

## Executive Summary

All ten suppliers are **truly dormant in the current run**, not merely hidden by the map:

- `0` MRP orders
- `0` outbound shipments
- `0` observed active days
- flat supplier stock over the full horizon

They are still present in the model and in the simulation-ready graph:

- they have outgoing lanes in the graph,
- they have MRP safety-policy rows in the assumptions ledger,
- they have supplier-capacity basis metadata,
- and they are all tagged with `unmodeled_supplier_source_policy = estimated_replenishment`.

The reason they remain dormant is not a rendering issue. It is structural:

1. the downstream item never reaches positive net requirement within the measured horizon, or
2. an alternative lane is the only one actually pulled, or
3. the family is modeled as a qualified alternative source that is not activated in the baseline.

## Global Findings

For all ten suppliers:

- `orders_est = 0`
- `orders_lane = 0`
- `ship_days = 0`
- `ship_qty = 0`
- `stock_distinct = 1`

This means they are not "constant active suppliers". They are inactive supplier candidates.

## Cluster Analysis

### Cluster A: Qualified alternatives for `M-1810`, but no downstream pull at all

Suppliers:

- `SDC-VD0990780A` for `item:002612`
- `SDC-VD0500655A` for `item:002612`
- `SDC-VD0914320A` for `item:055703`
- `SDC-VD0964290A` for `item:055703`
- `SDC-VD1096202A` for `item:039668`

Observed facts:

- For `M-1810 / item:002612`, `bn_days = 0`, `bn_sum = 0.0` in `mrp_trace_daily.csv`
- For `M-1810 / item:055703`, `bn_days = 0`, `bn_sum = 0.0`
- For `M-1810 / item:039668`, `bn_days = 0`, `bn_sum = 0.0`
- Stocks stay positive over the full year:
  - `item:002612`: min `146915.2`, max `153463.2`
  - `item:055703`: min `305.5`, max `567.5`
  - `item:039668`: min `327.6`, max `458.5`

Interpretation:

- these lanes are available,
- but the baseline never produces a positive net requirement on those item families,
- so no supplier in the family is triggered.

Implication:

- these suppliers should not be read as failed or broken,
- they should be read as **qualified but unused alternatives under a high-stock baseline**.

Recommendation:

- keep them in the graph if the objective is sourcing resilience,
- mark them explicitly as `inactive qualified source`,
- do not interpret their flat stock as meaningful supplier behavior.

### Cluster B: Alternative lane family where another source is used

Supplier:

- `SDC-VD0518684A` for `M-1810 / item:001893`

Observed facts:

- `SDC-VD0518684A`: `0` orders, `0` shipments
- competing family:
  - `SDC-VD0910216A` shipped `23451.4`
  - `SDC-VD1091642A` shipped `0.0`
  - `SDC-VD0518684A` shipped `0.0`
- `M-1810 / item:001893` has `bn_days = 0`, `bn_sum = 0.0`
- stock still remains positive over the full year: min `8130.5`, max `18794.3`

Interpretation:

- the item family is nearly dormant from an MRP standpoint,
- but the very small amount of replenishment that does occur is captured by `SDC-VD0910216A`,
- so `SDC-VD0518684A` remains a non-used alternate.

Recommendation:

- classify as `inactive alternate source`,
- useful for stress scenarios,
- low value in baseline storytelling unless an outage is injected on `SDC-VD0910216A`.

### Cluster C: Upstream suppliers to `SDC-1450` never activated

Suppliers:

- `SDC-VD0949099A`
- `SDC-VD0960508A`
- `SDC-VD0972460A`
- `SDC-VD0975221A`

All four feed:

- `SDC-1450 / item:021081`

Observed facts:

- all four have `0` orders and `0` shipments
- `SDC-1450 / item:021081` has `bn_days = 0`, `bn_sum = 0.0`
- `SDC-1450 / item:021081` stock remains high:
  - min `1113492.0`
  - max `1142100.0`
- all four lanes have the same mean lead time `120` days
- prices are very close, except `VD0975221A` which is more expensive

Interpretation:

- the Gaillac upstream family is present in the graph,
- but the baseline never creates positive net requirement on `021081`,
- so the whole upstream family is dormant.

This is important methodologically:

- the model can represent this upstream family,
- but the baseline does not stress it at all,
- so it contributes almost nothing to service or risk in the current horizon.

Recommendation:

- keep only if Tier-2 ripple-effect studies are a near-term objective,
- otherwise grey them visually in the map and exclude them from baseline criticality narratives.

## Source-Data Explanation (`etudecas/donnees`)

The explanations below are grounded in the original case-study workbooks, not only in simulation outputs.

### `SDC-VD0990780A`

- source workbook: `268191.xlsx`, sheet `FIA`
- lane in source data: `002612 | VD0990780A | 1295 / 1000 EUR | lead 35 j | SOQ 23750 KG`
- destination stock in `Stocks_MRP.xlsx`, sheet `Stocks`:
  - `002612 | 1810 | Avène | 153521.6367 KG`
- destination MRP policy in `Stocks_MRP.xlsx`, sheet `Politique de Stock MRP`:
  - `002612 | 1810 | safety time 20 j | safety stock 0`

Explanation:

- the supplier is a qualified FIA source,
- but Avène already starts with a very high stock on `002612`,
- and the family never creates positive net requirement during the measured horizon,
- so this source is never activated.

### `SDC-VD0500655A`

- source workbook: `268191.xlsx`, sheet `FIA`
- lane in source data: `002612 | VD0500655A | 1340 / 1000 EUR | lead 28 j | SOQ 21600 KG`
- same destination family and same Avène starting stock as above

Explanation:

- same family as `VD0990780A`,
- same dormancy mechanism,
- simply another qualified source on an item family that stays covered throughout the run.

### `SDC-VD0518684A`

- source workbook: `268191.xlsx`, sheet `FIA`
- lane in source data: `001893 | VD0518684A | 4.4 EUR | lead 56 j | SOQ 22800 KG`
- destination stock in `Stocks_MRP.xlsx`:
  - `001893 | 1810 | Avène | 9783.5 KG`
- destination policy in `Stocks_MRP.xlsx`:
  - `001893 | 1810 | safety time 15 j | safety stock 0`

Explanation:

- the source is real and qualified,
- but the family is barely used in the horizon,
- and the little replenishment that does occur is captured by another source (`VD0910216A`),
- so `VD0518684A` remains dormant as an alternate.

### `SDC-VD0914320A`

- source workbook: `268191.xlsx`, sheet `FIA`
- lane in source data: `055703 | VD0914320A | 20.35 EUR | lead 21 j | SOQ 300 KG`
- destination stock in `Stocks_MRP.xlsx`:
  - `055703 | 1810 | Avène | 569805 G`
- destination policy in `Stocks_MRP.xlsx`:
  - `055703 | 1810 | safety time 30 j | safety stock 0`

Explanation:

- the source exists in FIA,
- but Avène already holds enough stock for the full run on this family,
- net requirement stays zero,
- so neither `VD0914320A` nor its alternate are activated.

### `SDC-VD0964290A`

- source workbook: `268191.xlsx`, sheet `FIA`
- lane in source data: `055703 | VD0964290A | 49.2 EUR | lead 42 j | SOQ 300 KG`
- same destination stock and policy as `VD0914320A`

Explanation:

- same family as `VD0914320A`,
- qualified but unused,
- also more expensive and slower in the source FIA data,
- so it stays dormant under the current baseline.

### `SDC-VD1096202A`

- source workbook: `268191.xlsx`, sheet `FIA`
- lane in source data: `039668 | VD1096202A | 12.21 EUR | lead 35 j | SOQ 450 KG`
- destination stock in `Stocks_MRP.xlsx`:
  - `039668 | 1810 | Avène | 459695 G`
- destination policy in `Stocks_MRP.xlsx`:
  - `039668 | 1810 | safety time 7 j | safety stock 0`

Explanation:

- this one is a sole source in the modeled family,
- but the item itself never creates positive net requirement over the run,
- so the supplier is dormant because the family is dormant, not because the lane is wrong.

### `SDC-VD0949099A`

- source workbook: `021081.xlsx`, sheet `FIA`
- lane in source data: `021081 | VD0949099A | 12.1 USD | lead 120 j | SOQ 20000 KG`
- destination stock in `Stocks_MRP.xlsx`:
  - `021081 | 1450 | Gaillac | 1142100 KG`
- supplier location in `Fournisseur.xlsx`:
  - `USA - NC BOONE - 28607`

Explanation:

- the source is real and mapped to Gaillac upstream,
- but Gaillac starts with a very large stock of `021081`,
- and the family never creates positive net requirement during the horizon,
- so the whole upstream family remains inactive.

### `SDC-VD0960508A`

- source workbook: `021081.xlsx`, sheet `FIA`
- lane in source data: `021081 | VD0960508A | 12.1 USD | lead 120 j | SOQ 1 KG`
- destination stock: same Gaillac `021081` stock as above
- supplier location in `Fournisseur.xlsx`:
  - `USA - 9664 DURHAM - 27704`

Explanation:

- real FIA source,
- but never triggered because Gaillac never enters positive net requirement on `021081`.

### `SDC-VD0972460A`

- source workbook: `021081.xlsx`, sheet `FIA`
- lane in source data: `021081 | VD0972460A | 12.15 USD | lead 120 j | SOQ 1 KG`
- destination stock: same Gaillac `021081` stock as above
- supplier location in `Fournisseur.xlsx`:
  - `USA - FELDA - 33930`

Explanation:

- same dormant upstream family as above,
- retained as a qualified alternate, not activated in baseline.

### `SDC-VD0975221A`

- source workbook: `021081.xlsx`, sheet `FIA`
- lane in source data: `021081 | VD0975221A | 15 USD | lead 120 j | SOQ 20000 KG`
- destination stock: same Gaillac `021081` stock as above
- supplier location in `Fournisseur.xlsx`:
  - `USA - FORT PIEERCE FL - 34947`

Explanation:

- same dormant upstream family,
- additionally less attractive on price in source FIA,
- but this is secondary because the family is not pulled at all.

## Supplier-by-Supplier Classification

| Supplier | Downstream family | Current status | Root cause | Recommendation |
|---|---|---|---|---|
| `SDC-VD0990780A` | `M-1810 / 002612` | dormant | no net requirement on family | keep as qualified alternate |
| `SDC-VD0500655A` | `M-1810 / 002612` | dormant | no net requirement on family | keep as qualified alternate |
| `SDC-VD0518684A` | `M-1810 / 001893` | dormant | family barely used, other lane selected | keep for shock studies |
| `SDC-VD0914320A` | `M-1810 / 055703` | dormant | no net requirement on family | keep as inactive alternate |
| `SDC-VD0949099A` | `SDC-1450 / 021081` | dormant | no net requirement on Gaillac upstream family | hide in baseline, keep for Tier-2 |
| `SDC-VD0960508A` | `SDC-1450 / 021081` | dormant | no net requirement on Gaillac upstream family | hide in baseline, keep for Tier-2 |
| `SDC-VD0964290A` | `M-1810 / 055703` | dormant | no net requirement on family | keep as inactive alternate |
| `SDC-VD0972460A` | `SDC-1450 / 021081` | dormant | no net requirement on Gaillac upstream family | hide in baseline, keep for Tier-2 |
| `SDC-VD0975221A` | `SDC-1450 / 021081` | dormant | no net requirement on Gaillac upstream family | hide in baseline, keep for Tier-2 |
| `SDC-VD1096202A` | `M-1810 / 039668` | dormant | sole-source family but no net requirement | keep, but baseline gives no evidence |

## Modeling Consequences

### What not to do

- Do not treat these suppliers as operationally relevant in the current baseline.
- Do not interpret their flat stock curves as evidence of realistic supplier dynamics.
- Do not use them to argue current resilience; they are not activated.

### What to do instead

For baseline communication:

- tag them as `inactive in current horizon`
- remove them from "active supplier behavior" commentary
- separate them from truly active suppliers in the world map and reports

For resilience work:

- retain them as dormant alternatives,
- especially on `002612`, `001893`, `021081`, `055703`, `039668`
- activate them only in controlled studies:
  - outage on active Tier-1 lane,
  - demand surge,
  - lower opening stock,
  - explicit Tier-2 activation on Gaillac upstream

## Priority Actions

1. In the map, distinguish:
   - `active supplier`
   - `inactive qualified alternate`
   - `inactive family with no downstream pull`

2. In supplier criticality reporting, exclude dormant suppliers from active ranking by default.

3. For methodology, use these dormant suppliers as candidates for:
   - sourcing diversification scenarios
   - upstream outage substitution tests
   - Tier-2 explicit graph enrichment

4. Do not spend effort making their daily curves "more realistic" before the family is actually activated by the model.
