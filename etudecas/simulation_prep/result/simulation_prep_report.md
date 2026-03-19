# Simulation prep report

## Inputs / outputs
- Input graph: /workspaces/lca-simu/etudecas/result_geocodage/supply_graph_poc_geocoded.json
- Output graph: /workspaces/lca-simu/etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Generated at (UTC): 2026-03-17T14:33:29.974606+00:00

## What was enriched
- Edge distances filled: 37
- Edge lead times updated: 4
- Edge transport costs updated: 37
- Edge delay limits updated: 4
- Edge pricing aligned from Data_poc Relations_acteurs: 4
- Inventory initials updated: 60
- Inventory holding costs updated: 62
- Holding-cost source item-value median: 50
- Holding-cost source global fallback: 12
- Inventory UOM harmonized: 10
- Node policies added: 32
- Process capacities updated: 2
- Process costs updated: 3
- DC alias reconciliations (1910->1920): 1
- Customer location recovered: 1
- Assumed Gaillac supplier nodes added: 0
- Assumed Gaillac supplier node tags updated: 1
- Assumed Gaillac supplier edges added: 1
- Assumed Gaillac supplier inventory states added: 1
- Assumed destination inventory states added (M-1810 unsourced input): 1
- Demand rows added: 1
- Demand rows updated: 2
- Scenario horizons updated to default simulation days: 1

## Changed entities
- Changed edges: 38
- Changed nodes: 33
- Changed demand rows: 3

## Validation after prep
- Missing geo nodes: 0
- Edges still missing distance: 0
- Edges still zero transport cost: 0
- Factory inbound edges missing sell_price: 1
- Zero-demand rows remaining: 0

## Data_poc pricing import
- Enabled: True
- XLSX path: /workspaces/lca-simu/etudecas/donnees/Data_poc.xlsx
- Rows read: 33
- Rows mapped: 33
- Error: none

## Holding cost model
- Formula: item_unit_value * annual_carry_rate / 365
- Annual carry rate: 0.2
- Item value basis: median(sell_price / price_base) per item after Data_poc pricing alignment
- Fallback unit value basis: global median priced item-unit value
- Priced items used: 20
- Priced edge-item pairs used: 30
- Fallback global unit value: 4.3

## Review reminder
This graph is assumption-based and intended for pre-simulation validation.
Review the assumptions in simulation_prep_report.json before scenario studies.
