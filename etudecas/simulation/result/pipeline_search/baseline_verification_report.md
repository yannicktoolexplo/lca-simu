# Baseline Verification Report

Date: 2026-03-24

## Objective

Verify the explicit baseline after the source-replenishment fix and find a candidate baseline that:

- removes the terminal production rupture observed on `M-1430`
- avoids relying on an oversized opaque bootstrap
- remains economically lighter than the previous explicit `30/25/20` state

## Main Findings

### 1. Original explicit `30/25/20` baseline was not acceptable as-is

Reference:
`etudecas/simulation/result/reference_baseline_explicit_30_25_20`

Observed issue before the replenishment fix:

- global fill rate looked strong (`0.96275`)
- but `M-1430` ended the horizon with a real input shortage on `item:042342`
- the final backlog was concentrated on `item:268967`

This confirmed that the global KPI was masking a terminal local rupture.

### 2. The source-replenishment fix removed the hidden upstream starvation

After fixing the estimated source replenishment anchor in
`etudecas/simulation/run_first_simulation.py`,
the terminal production rupture disappeared on the explicit-state variants.

However, many runs then became too perfect because the initialization still seeded too much pipeline.

### 3. The real lever was the initialization pipeline, not only the on-hand stock

Targeted search was run from the lightest explicit state (`5/5/5`) by varying:

- `in_transit_fill_ratio`
- `seed_estimated_source_pipeline`
- selected on-hand days on downstream buffers

Key results:

| Variant | Fill rate | Ending backlog | Avg inventory | Total cost | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| `fr20_seedfalse` | `0.941082` | `87.6412` | `196634.20` | `16.651 M` | Too low on service, no terminal production rupture |
| `fr40_seedfalse` | `0.954527` | `67.6412` | `273720.51` | `16.647 M` | Good service, but residual final backlog on `item:268091` |
| `fr60_seedfalse` | `0.967972` | `47.6412` | `350170.93` | `16.643 M` | Better service, still residual final backlog on `item:268091` |
| `fr60_seedfalse_dc08_fi02` | `1.000000` | `0` | `275203.17` | `16.644 M` | No terminal backlog, no terminal production rupture, but perfect on seed 42 |

## Recommended Candidate

Single-run candidate:

`etudecas/simulation/result/pipeline_search/supply_graph_reference_baseline_explicit_5_5_5_fr60_seedfalse_dc08_fi02`

Initialization logic:

- `factory_input_on_hand_days = 2`
- `supplier_output_on_hand_days = 5`
- `distribution_center_on_hand_days = 8`
- `in_transit_fill_ratio = 0.60`
- `seed_estimated_source_pipeline = false`

Single-seed result (`seed = 42`):

- `fill_rate = 1.0`
- `ending_backlog = 0`
- `avg_inventory = 275203.1718`
- `total_cost = 16644289.9886`

Operationally, this candidate is much cleaner than the earlier explicit baseline:

- no terminal production rupture on `M-1430`
- no zero-production streak at the end on either main factory flow
- no final backlog on `item:268967`
- no final backlog on `item:268091`

## Robustness Check Across Seeds

Because a single `1.0` fill rate is not credible enough on its own, the recommended candidate was rerun on multiple seeds:

`etudecas/simulation/result/seed_check_fr60_seedfalse_dc08_fi02`

Seeds checked: `1, 2, 3, 4, 5, 42, 99`

Results:

- mean fill rate: `0.999565`
- min fill rate: `0.996956`
- max fill rate: `1.000000`
- max ending backlog: `4.5282`

Important interpretation:

- the candidate is not hiding a terminal production collapse
- it is stable across seeds
- but the service level is still very high in the current model formulation

On the worst tested seed (`seed_5`):

- the residual backlog is tiny (`4.52825`) and sits on `item:268967`
- both `M-1430` and `M-1810` still keep producing in the last 20 days
- there is no end-of-horizon zero-production regime

## Conclusion

Two conclusions should be kept separate:

1. **On the rupture question**, the work is conclusive.
   The terminal production rupture that invalidated the old explicit baseline has been removed.

2. **On the realism question**, the work is only partially conclusive.
   The current model still tends to snap from "small residual backlog" to "near-perfect service" once the initialization becomes just sufficient.

So the best current recommendation is:

- use `fr60_seedfalse_dc08_fi02` as the best **working baseline candidate**
- do **not** present its single-seed `fill_rate = 1.0` as a final business truth
- present the seed sweep as the real validation envelope

## Next Improvement

If a baseline strictly below `100%` is still required while keeping zero terminal rupture, the next improvement should not be more micro-tuning of the initial state alone.

The next realistic step is to evaluate the baseline on a seed ensemble and/or strengthen operational variability, for example through:

- more explicit stochastic reliability realization
- scenario envelopes instead of a single deterministic-looking path
- validation on horizon-end service and backlog by SKU, not only global fill rate
