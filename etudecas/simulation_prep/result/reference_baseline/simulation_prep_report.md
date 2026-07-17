# Simulation prep report

## Inputs / outputs
- Input graph: etudecas\data\geocoded\supply_graph_poc_geocoded.json
- Output graph: etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_simulation_ready.json
- Generated at (UTC): 2026-07-09T11:43:37.623558+00:00

## What was enriched
- Edge distances filled: 38
- Edge lead times updated: 4
- Edge transport costs updated: 39
- Edge delay limits updated: 4
- Edge pricing aligned from Data_poc Relations_acteurs: 0
- Edge pricing aligned from demand_PF Relations_acteurs: 39
- Nodes added from demand_PF Acteurs: 1
- Node locations filled from demand_PF Acteurs: 1
- Edges added from demand_PF Relations_acteurs: 5
- Inventory states added from demand_PF Relations_acteurs: 4
- Inventory initials updated: 65
- Inventory holding costs updated: 65
- Holding-cost source item-value median: 53
- Holding-cost source global fallback: 12
- Inventory UOM harmonized: 16
- Node policies added: 35
- Process capacities updated: 2
- Process costs updated: 3
- DC alias reconciliations (1910->1920): 1
- Customer location recovered: 1
- Assumed Gaillac supplier nodes added: 0
- Assumed Gaillac supplier node tags updated: 0
- Assumed Gaillac supplier edges added: 0
- Assumed Gaillac supplier inventory states added: 0
- Assumed destination inventory states added (M-1810 unsourced input): 0
- Demand rows added: 1
- Demand rows updated: 0
- Demand rows loaded from demand_PF.xlsx: 2
- Scenario horizons updated to default simulation days: 1

## Changed entities
- Changed edges: 44
- Changed nodes: 37
- Changed demand rows: 3

## Validation after prep
- Missing geo nodes: 3
- Edges still missing distance: 1
- Edges still zero transport cost: 0
- Factory inbound edges missing sell_price: 0
- Zero-demand rows remaining: 0

## Data_poc pricing import
- Enabled: True
- XLSX path: etudecas\data\source\Data_poc.xlsx
- Rows read: 33
- Rows mapped: 33
- Error: none

## demand_PF import
- Enabled: True
- XLSX path: etudecas\data\source\demand_PF.xlsx
- Sheet found: True
- Rows read: 104
- Rows mapped: 104
- Pairs loaded: 2
- Annual totals by pair: `{'C-XXXXX::item:268091': 3576442.0, 'C-XXXXX::item:268967': 1575986.0}`
- Error: none

## demand_PF Acteurs import
- Enabled: True
- Rows read: 32
- Rows mapped: 32
- Error: none

## demand_PF Relations_acteurs import
- Enabled: True
- Rows read: 39
- Rows mapped: 39
- Error: none

## Holding cost model
- Formula: item_unit_value * annual_carry_rate / 365
- Annual carry rate: 0.2
- Item value basis: median(sell_price / price_base) per item after Data_poc pricing alignment
- Fallback unit value basis: global median priced item-unit value
- Priced items used: 21
- Priced edge-item pairs used: 32
- Fallback global unit value: 3.895

## Review reminder
This graph is assumption-based and intended for pre-simulation validation.
Review the assumptions in simulation_prep_report.json before scenario studies.
