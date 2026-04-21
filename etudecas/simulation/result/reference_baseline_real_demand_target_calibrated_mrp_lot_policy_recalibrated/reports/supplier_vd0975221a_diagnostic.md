# Supplier Diagnostic: SDC-VD0975221A

## Scope

Supplier audited:

- `Supplier of Raw Materials - VD0975221A`
- node id: `SDC-VD0975221A`

Canonical run audited:

- `reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated`

## Executive Summary

`SDC-VD0975221A` is a real supplier present in the case-study source data, but it is fully dormant in the current run.

This is not a rendering bug and not a missing-node issue.

The structural explanation is:

1. `VD0975221A` is a qualified FIA supplier for raw material `021081`.
2. `021081` feeds `SDC-1450` (Gaillac) upstream.
3. Gaillac starts with a very high initial stock of `021081`.
4. The run never generates a positive net requirement on `SDC-1450 / item:021081`.
5. Therefore no lane in the upstream `021081` family is activated, including `VD0975221A`.

## Source Data (`etudecas/donnees`)

### `021081.xlsx` / sheet `FIA`

Observed source row:

- `021081 | VD0975221A | 15 | 1 | USD | 120 | 20000 | KG`

Interpretation:

- supplier account is real,
- mean lead time is `120` days,
- standard order quantity is `20000 KG`,
- currency/price basis is `15 / 1 USD`.

### `Stocks_MRP.xlsx` / sheet `Stocks`

Observed source row:

- `021081 | MP | 1450 | Gaillac | 1142100 | KG | 45658.127638888887`

Interpretation:

- Gaillac starts with `1,142,100 KG` of `021081`,
- which is already a very large upstream buffer for this family.

### `Fournisseur.xlsx` / sheet `LOCATION`

Observed source row:

- `VD0975221A | USA - FORT PIEERCE FL - 34947 | USA | 34947 | FORT PIEERCE FL`

Interpretation:

- supplier location is present and sourced,
- upstream geography is real, not synthetic.

## Graph / Modeling Presence

The supplier is explicitly present in the simulation-ready graph:

- node: `SDC-VD0975221A`
- lane: `edge:SDC-VD0975221A_TO_SDC-1450_021081`

The case-data refresh also documents that:

- `021081.xlsx` is modeled as an upstream component feeding `SDC-1450`,
- then `SDC-1450` transforms `021081` into `773474`.

## Simulation Facts

Observed in the canonical run:

- supplier shipments: `0`
- MRP orders touching supplier: `0`
- supplier stock rows: `365`
- supplier stock item: `item:021081`
- supplier stock distinct values: `1`
- supplier stock min/max: `125160 / 125160`
- supplier capacity utilization average: `0`

Observed on the downstream pair `SDC-1450 / item:021081`:

- MRP trace rows: `365`
- gross requirement sum (`bb_sum`): `6526200`
- net requirement days (`bn_days`): `0`
- net requirement sum (`bn_sum`): `0`
- projected stock min/max: `1113492 / 1142100`

Interpretation:

- the family is consumed in the model,
- but never enough to create a positive net requirement,
- so the upstream supplier family remains untouched.

## Conclusion

`SDC-VD0975221A` should be read as:

- `real qualified supplier in source data`
- `modeled upstream in the graph`
- `inactive in this baseline because the family is fully covered by initial stock`

It should not be interpreted as:

- a broken supplier,
- a missing lane,
- or an HTML issue.
