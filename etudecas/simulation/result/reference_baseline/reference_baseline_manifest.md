# Reference Baseline

- Baseline id: `baseline_value_based_ge095_structural_2026-03-17`
- Status: `frozen_working_reference`
- Scope: `etudecas` baseline after value-based inventory holding cost recalibration

## Official files
- Current graph: [/workspaces/lca-simu/etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_current.json](/workspaces/lca-simu/etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_current.json)
- Versioned graph: [/workspaces/lca-simu/etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_value_based_ge095_structural.json](/workspaces/lca-simu/etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_value_based_ge095_structural.json)
- Official report: [/workspaces/lca-simu/etudecas/simulation/result/reference_baseline/reference_baseline_report.md](/workspaces/lca-simu/etudecas/simulation/result/reference_baseline/reference_baseline_report.md)
- Official summary: [/workspaces/lca-simu/etudecas/simulation/result/reference_baseline/reference_baseline_summary.json](/workspaces/lca-simu/etudecas/simulation/result/reference_baseline/reference_baseline_summary.json)
- Selection rationale: [/workspaces/lca-simu/etudecas/simulation/result/value_based_baseline_recalibration_summary.md](/workspaces/lca-simu/etudecas/simulation/result/value_based_baseline_recalibration_summary.md)

## Baseline settings
- Scenario: `scn:BASE`
- Horizon: `365 days`
- Seed: `42`
- Source mode: `estimated_replenishment`
- External procurement enabled: `false`
- Opening stock bootstrap scale: `2.0`
- Capacity scale: `4.0`
- Lead time scale: `1.0`
- Supplier capacity scale: `1.0`

## Holding cost model
- Formula: `item_unit_value * annual_carry_rate / 365`
- Annual carry rate: `0.20`
- Priced items used: `20`
- Priced edge-item pairs used: `30`
- Fallback global unit value: `4.3`

## KPIs
- Fill rate: `0.951540`
- Ending backlog: `843.2095`
- Total cost: `19256325.8659`
- Avg inventory: `8253511.0415`
- Total estimated source ordered qty: `49570.1`
- Total estimated source replenished qty: `47944.2243`
- Total opening stock bootstrap qty: `8523781.9898`

## Rationale
- This is the current working reference because it reaches a pharma-style service level around `95%`.
- It is easier to defend than the cheaper `~0.93` option because it keeps lead times unchanged.
- Lower-cost alternatives existed, but they depended on shortened lead times and were less credible as a baseline.
