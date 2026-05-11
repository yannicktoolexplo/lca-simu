# First simulation report

## Run setup
- Input: etudecas\simulation\sensibility\active_supplier_parameter_result_external_procurement_leads\cases\supplier_capacity_node_SDC-VD0508918A_1_0\input_case.json
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
- Supplier neutral floor test enabled / capacity pairs / stock pairs: False / 0 / 0
- Factory nominal capacity test enabled / applied processes: False / 0
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 0.09
- Inventory cost split capital / warehouse / risk: 0.35 / 0.45 / 0.2
- Transport / purchase realism multipliers: 0.2 / 1.0
- Production cost enabled / target share: True / 0.3
- Production cost basis: pharma_standard_target_share_allocated_on_actual_production
- Production cost line shares: {'M-1430|item:268967': 0.4, 'M-1810|item:268091': 0.45, 'SDC-1450|item:773474': 0.15}
- External procurement enabled: True
- External procurement proactive supplier replenishment: True
- External procurement lead days: 4
- External procurement lead mode / scale: supplier_material / 1.0
- External procurement daily cap days: 999.0
- External procurement min daily cap qty: 1000000000.0
- External procurement unit cost / multiplier / transport unit: 0.0 / 2.0 / 0.04
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
- External upstream sourcing for unmodeled source pairs: 34
- Opening stock bootstrap pairs (lead-time coverage at max capacity): 0
- Opening open-order rows seeded: 88
- MRP trace tracked pairs / rows / orders: 65 / 118625 / 33216

## KPIs
- Total demand: 25762139.9999
- Total served: 25762139.9999
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 106327600.0
- Total shipped: 643752744.0108
- Avg inventory: 591479052.893
- Ending inventory: 511042420.1437
- Transport cost: 5547160.3566
- Holding cost (capital tied-up): 10254244.9942
- Warehouse operating cost: 13184029.2782
- Inventory risk cost (obsolescence/compliance proxy): 5859568.5681
- Legacy raw holding cost before split: 29297842.8405
- Purchase cost (from order_terms sell_price): 14584871.4195
- Production cost (pharma conversion proxy): 21184231.9786
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 34845003.1971
- Total cost: 70614106.5952
- Total external procured ordered qty: 611862556.7491
- Total external procured arrived qty: 605393055.0019
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 261664373.574
- Total estimated source ordered qty: 0.0
- Total estimated source replenished qty: 0.0
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase / production: 0.145215 / 0.186705 / 0.08298 / 0.078556 / 0.206543 / 0.3
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 208012846.7465
- Total explicit initialization pipeline qty: 68338188.0
- Total opening open-order qty: 68338188.0
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 0.0
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
| input_material | M-1810 | item:001757 | 20.0 | 14.531107 | 290.622141 | 290.622141 | 935.424 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001848 | 20.0 | 10.89833 | 217.966606 | 217.966606 | 701.568 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001893 | 15.0 | 69.022759 | 1035.341379 | 1035.341379 | 3332.448 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:002612 | 20.0 | 18.163884 | 363.277677 | 363.277677 | 1169.28 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:007923 | 15.0 | 29.062214 | 435.933212 | 435.933212 | 1403.136 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:016332 | 7.0 | 4.359332 | 30.515325 | 30.515325 | 98.21952 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:029313 | 7.0 | 0.363278 | 2.542944 | 2.542944 | 8.18496 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:039668 | 7.0 | 0.363278 | 2.542944 | 2.542944 | 8.18496 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:049371 | 40.0 | 13.441274 | 537.650962 | 938.782895 | 1730.5344 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:055703 | 30.0 | 0.726555 | 21.796661 | 21.796661 | 70.1568 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:099439 | 7.0 | 18.163884 | 127.147187 | 127.147187 | 409.248 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:338928 | 10.0 | 8947.726027 | 89477.260274 | 89477.260274 | 288000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:338929 | 10.0 | 8947.726027 | 89477.260274 | 89477.260274 | 288000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:426331 | 7.0 | 98.424986 | 688.974904 | 688.974904 | 2217.6 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:693055 | 20.0 | 3632.776767 | 72655.535342 | 72655.535342 | 233856.0 | mrp_trace_demand_signal | G |
| input_material | SDC-1450 | item:021081 | 0.0 | 407.566027 | 0.0 | 900000.0 | 900000.0 | mrp_trace_demand_signal | KG |

## Remarques validation industrielle
Le graphe `Reappro amont` utilise maintenant `order_date_IMT` pour dater les ordres MRP. Les commandes du carnet initial peuvent donc apparaitre avant J0 au lieu d'etre empilees artificiellement au 1er janvier.

| Noeud | Item | Lot std | Ancien pic J0 | Pic IMT | Jour IMT | Avant J0 | Lots au pic | Remarque |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M-1810 | 338929 | 5000.0 | 295000.0 | 250000.0 | 1640 | 120000.0 | 50.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1430 | 333362 | 5000.0 | 1170000.0 | 65000.0 | 18 | 350000.0 | 13.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1430 | 042342 | 30000000.0 | 30000000.0 | 60000000.0 | -2 | 150000000.0 | 2.0 | Lot FIA tres eleve a valider avec l'industriel. |
| M-1430 | 773474 | 1.0 | 9600000.0 | 1600650.0 | 8 | 1600000.0 | 1600650.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 344135 | 120000.0 | 4200000.0 | 240000.0 | 889 | 720000.0 | 2.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 693055 | 1.0 | 5847.0 | 146177.0 | 1074 | 7490.0 | 146177.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 734545 | 6300.0 | 18900.0 | 6300.0 | -5 | 6300.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1430 | 708073 | 5000.0 | 25000.0 | 5000.0 | -7 | 5000.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |

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
