# Active Constant Suppliers Diagnostic

## Scope

This note explains why some **active suppliers** still appear too constant in the current canonical run.

Run audited:

- `etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated`

## Method

The classification combines:

- source lane structure from `etudecas/donnees/*.xlsx` via the simulation-ready graph,
- observed shipment profiles from `production_supplier_shipments_daily.csv`,
- supplier activity from `supplier_local_criticality_ranking.csv`,
- MRP upstream policy from `assumptions_ledger.csv`.

## Interpretation Rules

The labels used in the map mean:

- `constant car source unique`
  - the supplier is the only modeled source on the downstream `(node, item)` family
- `constant car lot d'achat fixe`
  - the lane has a positive `standard_order_qty` and the observed profile uses very few shipment levels
- `constant car famille quasi lissée`
  - the supplier ships on a large share of the days with very few distinct quantities
- `constant car amont reconstruit`
  - the supplier itself is replenished by `unmodeled_supplier_source_policy = estimated_replenishment`

## Main Suppliers Concerned

### `SDC-VD0993480A`

- downstream family: `M-1430 / item:344135`
- source data family: single FIA lane in `268191.xlsx`
- observed profile:
  - `177` active days
  - `1` distinct quantity
- explanation:
  - source unique
  - lot d'achat fixe
  - amont reconstruit
  - famille quasi lissée

This is the clearest case of a supplier that is active but structurally over-regular in the baseline.

### `SDC-VD0914690A`

- downstream family: `M-1430 / item:042342`
- observed profile:
  - `64` active days
  - `1` distinct quantity
- explanation:
  - source unique
  - lot d'achat fixe
  - amont reconstruit

### `SDC-VD0525412A`

- downstream family: `M-1430 / item:333362`
- observed profile:
  - `112` active days
  - `3` distinct quantities
- explanation:
  - source unique
  - lot d'achat fixe
  - amont reconstruit

This supplier is less flat than `VD0993480A`, but still clearly driven by a narrow shipment policy.

### `SDC-VD0901566A`

- downstream family: `M-1810 / item:338928`
- observed profile:
  - `130` active days
  - `3` distinct quantities
- explanation:
  - source unique
  - lot d'achat fixe
  - amont reconstruit

Important nuance:

- quantity is still too regular,
- but the lane is not constant in delay terms,
- so this is not a dead lane; it is a simplified one.

### Secondary Constant Profiles

These suppliers are also structurally constant, but the volume is low enough that they matter less in baseline interpretation:

- `SDC-VD0508918A`
- `SDC-VD0505677A`
- `SDC-VD0514881A`
- `SDC-VD0520115A`
- `SDC-VD0989480A`
- `SDC-VD1095770A`

Their common pattern is:

- single downstream family,
- fixed order quantum,
- reconstructed upstream,
- very low variety in shipped quantities.

## What This Means

These suppliers are not constant because the UI is wrong.

They are constant because the current baseline combines:

- sparse or single-source FIA families,
- fixed standard order quantities,
- a reconstructed upstream supplier policy,
- and a fairly smooth downstream pull on some families.

## Priority Consequence

For interpretation:

- do not confuse `lead time variability` with `quantity variability`
- several suppliers are active and risky on lead time while still too regular on shipped quantity

For modeling:

- the next realism gain is not more plotting,
- it is a better supplier replenishment policy and a more explicit upstream network.

