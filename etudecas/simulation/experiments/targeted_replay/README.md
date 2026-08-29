# Targeted scenario replay

This module ranks already simulated business scenarios, then replays only the
nominal and the most influential scenarios with lot trace explicitly enabled.
It does not modify or import the simulation engine.

The source must be a pipeline output with:

- a root `run_manifest.json`;
- a recorded `simulator_command`;
- `companion_runs` pointing to scenario outputs with their own manifests.

## Position in the experiment pipeline

- Sensitivity identifies parameters and breakpoints that matter.
- Monte Carlo estimates the dispersion and interactions across uncertain inputs.
- Business/state-dependent risk runs provide named, reproducible scenarios.
- Targeted replay ranks these reproducible scenarios and replays only the most
  influential ones with complete lot artifacts.

An aggregated Monte Carlo row is deliberately not replayed from its KPI values
alone. Exact replay requires the mutated input and command used by that sample.
Monte Carlo campaigns intended for later lot replay must therefore retain their
run artifacts. This module never fabricates an input from an aggregated result.

## Plan a replay

```powershell
python -m etudecas.simulation.experiments.targeted_replay `
  --source-run etudecas/simulation/result/my_run `
  --output-dir etudecas/simulation/result/_targeted/my_suite `
  --top-k 3
```

## Execute it

```powershell
python -m etudecas.simulation.experiments.targeted_replay `
  --source-run etudecas/simulation/result/my_run `
  --output-dir etudecas/simulation/result/_targeted/my_suite `
  --top-k 3 `
  --kpi product_availability:lower:3 `
  --kpi production_replanning_rate:higher:2 `
  --kpi total_cost:higher:1 `
  --execute
```

`lower` means that a decrease from the nominal run is adverse, `higher` means
that an increase is adverse, and `absolute` ranks both directions.

## Rebuild from existing replays

When the simulations already exist, revalidate their lot trace and regenerate
metrics, lot deltas, supply-order deltas, and the comparison manifest without
rerunning the engine:

```powershell
python -m etudecas.simulation.experiments.targeted_replay `
  --source-run etudecas/simulation/result/my_run `
  --output-dir etudecas/simulation/result/_targeted/my_suite `
  --top-k 3 `
  --reuse-existing
```

The suite writes:

- `selection_manifest.json`: source provenance, complete ranking and commands;
- `comparison_manifest.json`: replay KPI deltas and lot-trace evidence;
- `replays/baseline`: nominal replay;
- `replays/NNN_<scenario>`: selected scenario replays.
- `reports/lot_delta_<scenario>.csv`: one row per stable production intent,
  with its production shift, completed business lots, shipments, receipts,
  substitutions, customer allocations and causal roots;
- `reports/lot_delta_<scenario>.json`: decision summary for the same comparison.
- `reports/supply_order_delta_<scenario>.csv`: differences in generated supply
  orders, dispatch groups, receipt dates, received material lots and causal
  roots.

Validation rejects a replay when a lot event or genealogy link contains causal
roots but is still labelled `nominal`. A caused row must be labelled
`scenario_affected`, `co_causes`, or carry an explicit business status such as
an approved reference transition.

The runner replaces only the output directory, optionally the horizon, and
forces `--lot-trace --skip-map --skip-plots`. All other recorded simulation
arguments are preserved.

## Interpretation boundary

- `planned_order_id` is the stable production intent used to compare the
  baseline and scenario.
- `business_batch_id` identifies the produced business lot; a stock occurrence
  or receipt may have a different technical lot identifier.
- `shipment_id` identifies the simulated physical movement.
- `demand_service` proves an allocation from customer-facing stock to demand.
  It is not, by itself, proof of carrier delivery or quality release.
- Several `causal_root_ids` are retained as co-causes. The replay does not
  invent an attribution percentage between simultaneous risks.
- Production intents matched by the same `planned_order_id` are exact inside
  the simulation contract. Supply orders split or merged by a scenario are
  explicitly labelled `quantity_overlap_reconstruction`: they are aligned by
  route, item and cumulative quantity, not presented as the same ERP order.
- `shipment_id` is a simulated route/date consolidation. It becomes a proven
  truck, pallet or handling unit only when those source identifiers are
  imported.
