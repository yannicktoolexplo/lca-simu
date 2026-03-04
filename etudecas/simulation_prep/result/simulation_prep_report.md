# Simulation prep report

## Inputs / outputs
- Input graph: etudecas/result_geocodage/supply_graph_poc_geocoded.json
- Output graph: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Generated at (UTC): 2026-03-04T10:02:28.059938+00:00

## What was enriched
- Edge distances filled: 33
- Edge lead times updated: 0
- Edge transport costs updated: 0
- Edge delay limits updated: 0
- Edge pricing aligned from Data_poc Relations_acteurs: 4
- Inventory initials updated: 55
- Inventory holding costs updated: 55
- Inventory UOM harmonized: 37
- Node policies added: 28
- Process capacities updated: 2
- Process costs updated: 2
- DC alias reconciliations (1910->1920): 1
- Customer location recovered: 1
- Assumed Gaillac supplier nodes added: 0
- Assumed Gaillac supplier node tags updated: 1
- Assumed Gaillac supplier edges added: 1
- Assumed Gaillac supplier inventory states added: 1
- Assumed destination inventory states added (M-1810, 693710): 1
- Demand rows added: 1
- Demand rows updated: 2
- Scenario horizons updated to default simulation days: 1

## Changed entities
- Changed edges: 34
- Changed nodes: 29
- Changed demand rows: 3

## Validation after prep
- Missing geo nodes: 0
- Edges still missing distance: 0
- Edges still zero transport cost: 33
- Factory inbound edges missing sell_price: 1
- Zero-demand rows remaining: 0

## Data_poc pricing import
- Enabled: True
- XLSX path: etudecas/donnees/Data_poc.xlsx
- Rows read: 33
- Rows mapped: 33
- Error: none

## Review reminder
This graph is assumption-based and intended for pre-simulation validation.
Review the assumptions in simulation_prep_report.json before scenario studies.
