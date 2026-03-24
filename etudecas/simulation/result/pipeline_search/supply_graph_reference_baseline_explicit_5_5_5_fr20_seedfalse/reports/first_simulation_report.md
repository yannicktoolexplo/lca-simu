# First simulation report

## Run setup
- Input: C:\dev\lca-simu\etudecas\simulation_prep\result\reference_baseline\pipeline_search\supply_graph_reference_baseline_explicit_5_5_5_fr20_seedfalse.json
- Scenario: scn:BASE
- Horizon (days): 30
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 2.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 5.0 / 5.0 / 5.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: True / 0.2 / False
- Unmodeled supplier source mode: estimated_replenishment
- Stochastic lead times: True
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 1.0
- Inventory cost split capital / warehouse / risk: 0.35 / 0.45 / 0.2
- Transport / purchase realism multipliers: 8.0 / 1.0
- External procurement enabled: False
- External procurement lead days: 4
- External procurement daily cap days: 2.0
- External procurement min daily cap qty: 0.0
- External procurement unit cost / multiplier / transport unit: 0.0 / 2.0 / 0.04
- Nodes: 32
- Edges: 38
- Lanes (edge x item): 38
- Demand rows: 2
- Input material pairs tracked: 24
- Output product pairs tracked: 3 (M-1430 | item:268967, M-1810 | item:268091, SDC-1450 | item:773474)
- Inputs non modelises par Relations_acteurs (non bloquants): 0 (none)
- Conversions d'unites BOM appliquees: 10
- Mismatch d'unites non convertis: 0
- Assumed supplier nodes (explicitly tagged, includes '?'): 1 (SDC-1450)
- Assumed supply edges (explicitly tagged, includes '?'): 1 (edge:SDC-1450_TO_M-1810_007923_Q)
- External upstream sourcing for unmodeled source pairs: 33
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 0

## KPIs
- Total demand: 1487.5
- Total served: 1399.8588
- Fill rate: 0.941082
- Ending backlog: 87.6412
- Total produced: 18467.8185
- Total shipped: 248568.9392
- Avg inventory: 196634.1999
- Ending inventory: 251508.9335
- Transport cost: 14025205.4649
- Holding cost (capital tied-up): 10776.5942
- Warehouse operating cost: 13855.6212
- Inventory risk cost (obsolescence/compliance proxy): 6158.0539
- Legacy raw holding cost before split: 30790.2693
- Purchase cost (from order_terms sell_price): 2595359.0792
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 14055995.7342
- Total cost: 16651354.8134
- Total external procured ordered qty: 0.0
- Total external procured arrived qty: 0.0
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 0.0
- Total estimated source ordered qty: 738786.4642
- Total estimated source replenished qty: 226267.9344
- Total estimated source rejected qty: 54876133.5728
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.000647 / 0.000832 / 0.00037 / 0.842286 / 0.155865
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 132409.3165
- Total explicit initialization pipeline qty: 843260.5245
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 3021.3999
- Economic consistency status: warn
- Economic consistency warnings: ['warehouse_operating_cost_share_below_10pct', 'inventory_risk_cost_share_below_5pct']

## Top backlog pairs
[
  {
    "node_id": "C-XXXXX",
    "item_id": "item:268091",
    "backlog": 87.6412
  }
]

## Files
- summaries/first_simulation_summary.json
- data/first_simulation_daily.csv
- data/production_input_stocks_daily.csv
- data/production_input_consumption_daily.csv
- data/production_input_replenishment_arrivals_daily.csv
- data/production_input_replenishment_shipments_daily.csv
- data/production_input_stocks_pivot.csv
- data/production_output_products_daily.csv
- data/production_demand_service_daily.csv
- data/production_constraint_daily.csv
- data/production_supplier_shipments_daily.csv
- data/production_supplier_stocks_daily.csv
- data/production_supplier_capacity_daily.csv
- data/production_dc_stocks_daily.csv
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
