# Simulation prep report

## Inputs / outputs
- Input graph: etudecas\result_geocodage\supply_graph_poc_geocoded.json
- Output graph: etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_simulation_ready.json
- Generated at (UTC): 2026-04-21T09:08:35.756827+00:00

## What was enriched
- Edge distances filled: 38
- Edge lead times updated: 11
- Edge transport costs updated: 44
- Edge delay limits updated: 11
- Edge pricing aligned from Data_poc Relations_acteurs: 0
- Edge pricing aligned from demand_PF Relations_acteurs: 39
- Nodes added from demand_PF Acteurs: 2
- Node locations filled from demand_PF Acteurs: 0
- Edges added from demand_PF Relations_acteurs: 7
- Inventory states added from demand_PF Relations_acteurs: 7
- Inventory initials updated: 67
- Inventory holding costs updated: 67
- Holding-cost source item-value median: 54
- Holding-cost source global fallback: 13
- Inventory UOM harmonized: 11
- Node policies added: 34
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
- Changed nodes: 35
- Changed demand rows: 3

## Validation after prep
- Missing geo nodes: 2
- Edges still missing distance: 6
- Edges still zero transport cost: 0
- Factory inbound edges missing sell_price: 0
- Zero-demand rows remaining: 0

## Data_poc pricing import
- Enabled: True
- XLSX path: etudecas\donnees\Data_poc.xlsx
- Rows read: 33
- Rows mapped: 33
- Error: none

## demand_PF import
- Enabled: True
- XLSX path: etudecas\donnees\demand_PF.xlsx
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
- Priced edge-item pairs used: 36
- Fallback global unit value: 4.485

## Review reminder
This graph is assumption-based and intended for pre-simulation validation.
Review the assumptions in simulation_prep_report.json before scenario studies.
