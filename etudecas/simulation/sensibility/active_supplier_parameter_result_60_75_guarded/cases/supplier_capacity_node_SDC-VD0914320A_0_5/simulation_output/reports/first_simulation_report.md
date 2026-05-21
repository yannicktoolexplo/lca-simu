# First simulation report

## Run setup
- Input: etudecas\simulation\sensibility\active_supplier_parameter_result_60_75_guarded\cases\supplier_capacity_node_SDC-VD0914320A_0_5\input_case.json
- Scenario: scn:BASE
- Measured horizon (days): 1825
- Warm-up (days): 0
- Total simulated timeline (days): 1825
- Output profile: compact
- Safety stock policy (days): 7.0
- Replenishment review period (customer/DC, days): 1
- Upstream factory MRP review period (days): 1
- MRP target bucket (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 1.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 0.0 / 0.0 / 0.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: False / 1.0 / False
- Opening open-orders reconstruction enabled / horizon days: True / 0
- Opening open-orders source: Extract_En_cours.xlsx
- Opening open-orders demand multiplier / BOM signal for MRP: 1.0 / True
- MRP demand signal source: mps_lotified
- MRP demand signal smoothing / static fallback on propagated pairs: 7 j / False
- MRP physical safety floor enforced: True
- MRP strict safety floor from safety time only: False
- Soft safety-time physical stock target factor: 1.0
- Soft safety-time pair factors: {}
- Base stock floor factor: 0.0
- Base stock floor pair factors: {'M-1430|item:038005': 1.0, 'M-1430|item:042342': 1.0, 'M-1430|item:333362': 1.0, 'M-1430|item:344135': 1.0, 'M-1430|item:708073': 1.0, 'M-1430|item:730384': 1.0, 'M-1430|item:734545': 1.0, 'M-1430|item:773474': 1.0, 'M-1810|item:001757': 1.0, 'M-1810|item:001848': 1.0, 'M-1810|item:001893': 1.0, 'M-1810|item:002612': 1.0, 'M-1810|item:007923': 1.0, 'M-1810|item:016332': 1.0, 'M-1810|item:029313': 1.0, 'M-1810|item:039668': 1.0, 'M-1810|item:049371': 1.0, 'M-1810|item:055703': 1.0, 'M-1810|item:099439': 1.0, 'M-1810|item:338928': 1.0, 'M-1810|item:338929': 1.0, 'M-1810|item:426331': 1.0, 'M-1810|item:693055': 1.0}
- Unmodeled supplier source mode: external_procurement
- Stochastic lead times: True
- Lead-time distribution mode: industrial
- Random seed: 42
- Supplier risk events enabled / count: False / 0
- Supplier risk warnings: []
- Supplier neutral floor test enabled / capacity pairs / stock pairs: True / 33 / 33
- Factory nominal capacity test enabled / applied processes: False / 0
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 0.09
- Inventory cost split capital / warehouse / risk: 0.35 / 0.45 / 0.2
- Transport / purchase realism multipliers: 0.2 / 1.0
- Production cost enabled / target share: True / 0.3
- Production cost basis: pharma_standard_target_share_allocated_on_actual_production
- Production cost line shares: {'M-1430|item:268967': 0.4, 'M-1810|item:268091': 0.45, 'SDC-1450|item:773474': 0.15}
- Supplier upstream supply enabled: True
- Supplier upstream proactive replenishment: True
- Supplier upstream lead days: 4
- Supplier upstream lead mode / scale: supplier_material / 1.0
- Supplier upstream capacity mode / nominal scale: supplier_nominal / 1.0
- Supplier upstream pipeline seed / fill ratio: True / 1.0
- Supplier upstream daily cap days: 999.0
- Supplier upstream min daily cap qty: 1000000000.0
- Supplier upstream unit cost / multiplier / transport unit: 0.0 / 2.0 / 0.04
- Nodes: 35
- Edges: 39
- Flux transport (edge x item): 39
- Demand rows: 2
- Input material pairs tracked: 24
- Output product pairs tracked: 3 (M-1430 | item:268967, M-1810 | item:268091, SDC-1450 | item:773474)
- Inputs non modelises par Relations_acteurs (non bloquants): 0 (none)
- Conversions d'unites BOM appliquees: 11
- Mismatch d'unites non convertis: 0
- Assumed supplier nodes (explicitly tagged, includes '?'): 0 (none)
- Assumed supply edges (explicitly tagged, includes '?'): 0 (none)
- Supplier upstream sourcing for unmodeled source pairs: 34
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 0
- Opening open-order rows seeded: 88
- MRP trace tracked pairs / rows / orders: 65 / 118625 / 31092

## KPIs
- Total demand: 25762139.9999
- Total served: 25762139.9999
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 106327600.0
- Total shipped: 815672743.1488
- Avg inventory: 662281343.9297
- Ending inventory: 616306701.4301
- Transport cost: 5439726.3435
- Holding cost (capital tied-up): 7608880.2965
- Warehouse operating cost: 9782846.0955
- Inventory risk cost (obsolescence/compliance proxy): 4347931.598
- Legacy raw holding cost before split: 21739657.99
- Purchase cost (from order_terms sell_price): 13976557.1007
- Production cost (pharma conversion proxy): 17638260.6146
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 27179384.3335
- Total cost: 58794202.0488
- Total supplier upstream ordered qty: 537323897.7025
- Total supplier upstream arrived qty: 704594183.0595
- Supplier upstream arrived includes opening upstream pipeline receipts when the upstream pipeline seed is enabled.
- Total supplier upstream rejected qty (cap-limited): 2035602842.1659
- Total supplier upstream cost premium: 50545530.6422
- Total estimated source ordered qty: 0.0
- Total estimated source replenished qty: 0.0
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase / production: 0.129415 / 0.166391 / 0.073952 / 0.092521 / 0.23772 / 0.3
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 754600.0
- Total explicit initialization pipeline qty: 303596475.6707
- Total opening open-order qty: 68338188.0
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 773234.3333
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[]

## Safety stock reference
Calcul: `stock equiv delai = demande moyenne journaliere MRP x delai de securite`. Quand une trace MRP existe, la demande moyenne vient du signal reel utilise par le MRP (`bb_demand_signal_qty`), pas d'une capacite ou d'un besoin statique gonfle. Si le mode strict est actif, le plancher physique MRP vient uniquement de cette couverture de delai de securite. La cible physique simulee applique le facteur global `1.0` ou un facteur specifique par couple si renseigne.

| Scope | Noeud | Item | Delai secu j | Demande MRP moy/j | Stock equiv delai moy | Cible physique moy | Max cible physique | Base | Unite |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| finished_good | DC-1920 | item:268091 | 20.0 | 9798.471233 | 195969.424658 | 195969.424658 | 399840.0 | mrp_trace_demand_signal | UN |
| finished_good | DC-1920 | item:268967 | 25.0 | 4317.769863 | 107944.246573 | 107944.246573 | 592153.571425 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:038005 | 20.0 | 68.220897 | 1364.417944 | 1364.417944 | 37728.223456 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:042342 | 5.0 | 235244.526904 | 1176222.634521 | 1176222.634521 | 32524338.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:333362 | 10.0 | 3898.520548 | 38985.205479 | 145007.123288 | 1078000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:344135 | 10.0 | 3898.520548 | 38985.205479 | 38985.205479 | 1078000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:708073 | 10.0 | 30.915268 | 309.152679 | 2236.823912 | 8548.54 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:730384 | 10.0 | 826.486356 | 8264.863562 | 30915.000548 | 228536.0 | mrp_trace_demand_signal | M |
| input_material | M-1430 | item:734545 | 10.0 | 31.188164 | 311.881644 | 311.881644 | 8624.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:773474 | 20.0 | 37639.116508 | 752782.330152 | 752782.330152 | 20815572.008 | mrp_trace_demand_signal | G |
| input_material | M-1810 | item:001757 | 20.0 | 14.274827 | 285.49653 | 285.49653 | 935.424 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001848 | 20.0 | 10.70612 | 214.122398 | 214.122398 | 701.568 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001893 | 15.0 | 67.805426 | 1017.08139 | 1017.08139 | 3332.448 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:002612 | 20.0 | 17.843533 | 356.870663 | 356.870663 | 1169.28 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:007923 | 15.0 | 28.549653 | 428.244796 | 428.244796 | 1403.136 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:016332 | 7.0 | 4.282448 | 29.977136 | 29.977136 | 98.21952 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:029313 | 7.0 | 0.356871 | 2.498095 | 2.498095 | 8.18496 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:039668 | 7.0 | 0.356871 | 2.498095 | 2.498095 | 8.18496 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:049371 | 40.0 | 13.204215 | 528.168581 | 938.782895 | 1730.5344 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:055703 | 30.0 | 0.713741 | 21.41224 | 21.41224 | 70.1568 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:099439 | 7.0 | 17.843533 | 124.904732 | 124.904732 | 409.248 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:338928 | 10.0 | 8789.917808 | 87899.178082 | 87899.178082 | 288000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:338929 | 10.0 | 8789.917808 | 87899.178082 | 87899.178082 | 288000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:426331 | 7.0 | 96.689096 | 676.823671 | 676.823671 | 2217.6 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:693055 | 20.0 | 3568.70663 | 71374.132603 | 71374.132603 | 233856.0 | mrp_trace_demand_signal | G |
| input_material | SDC-1450 | item:021081 | 0.0 | 407.566027 | 0.0 | 900000.0 | 900000.0 | mrp_trace_demand_signal | KG |

## Remarques validation industrielle
Le graphe `Reappro amont` utilise maintenant `order_date_IMT` pour dater les ordres MRP. Les commandes du carnet initial peuvent donc apparaitre avant J0 au lieu d'etre empilees artificiellement au 1er janvier.

| Noeud | Item | Lot std | Ancien pic J0 | Pic IMT | Jour IMT | Avant J0 | Lots au pic | Remarque |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M-1810 | 338929 | 5000.0 | 295000.0 | 220000.0 | 1048 | 125000.0 | 44.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1430 | 333362 | 5000.0 | 1170000.0 | 110000.0 | 43 | 350000.0 | 22.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1430 | 042342 | 30000000.0 | 30000000.0 | 60000000.0 | 1 | 120000000.0 | 2.0 | Lot FIA tres eleve a valider avec l'industriel. |
| M-1430 | 773474 | 1.0 | 9600000.0 | 1600650.0 | 8 | 1686732.0 | 1600650.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 344135 | 120000.0 | 4440000.0 | 360000.0 | -5 | 1440000.0 | 3.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 693055 | 1.0 | 5847.0 | 102050.0 | 1146 | 6720.0 | 102050.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 708073 | 5000.0 | 30000.0 | 10000.0 | 6 | 10000.0 | 2.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1430 | 734545 | 6300.0 | 25200.0 | 6300.0 | -5 | 6300.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |

Process internes sans capacite source: la simulation ne les bloque pas par capacite, mais conserve les contraintes de lots, d'intrants et de besoin.
| Noeud | Process | Sortie |
|---|---|---:|
| SDC-1450 | proc:MAKE_773474 | 773474 |

## Files
- summaries/first_simulation_summary.json
- reports/mrp_safety_stock_reference.csv
- data/production_input_stocks_daily.csv
- data/production_output_products_daily.csv
- data/production_demand_service_daily.csv
- data/production_constraint_daily.csv
- data/mrp_trace_daily.csv
- data/mrp_orders_daily.csv
- data/assumptions_ledger.csv
- data/production_supplier_shipments_daily.csv
- data/production_supplier_stocks_daily.csv
- data/production_supplier_stock_flows_daily.csv
- data/production_supplier_capacity_daily.csv
- data/supplier_nominal_parameters.csv
- data/production_capacity_nominal_parameters.csv
- data/supplier_risk_events_applied_daily.csv
- reports/supplier_nominal_audit.md
- Additional detailed CSVs: skipped in compact mode
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
