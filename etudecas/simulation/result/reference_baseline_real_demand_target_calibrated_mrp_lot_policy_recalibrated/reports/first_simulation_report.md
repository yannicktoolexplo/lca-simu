# First simulation report

## Run setup
- Input: etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated.json
- Scenario: scn:BASE
- Measured horizon (days): 365
- Warm-up (days): 0
- Total simulated timeline (days): 365
- Output profile: compact
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 1.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 0.0 / 1.0 / 3.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: True / 1.0 / True
- Opening open-orders reconstruction enabled / horizon days: False / 0
- Opening open-orders demand multiplier / BOM signal for MRP: 1.0 / False
- MRP demand signal source: demand
- MRP demand signal smoothing / static fallback on propagated pairs: 1 j / True
- MRP physical safety floor enforced: False
- MRP strict safety floor from safety time only: False
- Soft safety-time physical stock target factor: 0.75
- Soft safety-time pair factors: {}
- Base stock floor factor: 1.0
- Base stock floor pair factors: {}
- Unmodeled supplier source mode: external_procurement
- Stochastic lead times: True
- Lead-time distribution mode: erlang
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 1.0
- Inventory cost split capital / warehouse / risk: 0.35 / 0.45 / 0.2
- Transport / purchase realism multipliers: 0.2 / 1.0
- External procurement enabled: True
- External procurement proactive supplier replenishment: True
- External procurement lead days: 4
- External procurement daily cap days: 2.0
- External procurement min daily cap qty: 0.0
- External procurement unit cost / multiplier / transport unit: 0.0 / 2.0 / 0.04
- Nodes: 33
- Edges: 39
- Lanes (edge x item): 39
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
- Opening open-order rows reconstructed from January snapshot: 0
- MRP trace tracked pairs / rows / orders: 65 / 23725 / 32886

## KPIs
- Total demand: 5152428.0
- Total served: 5152428.0
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 37526400.0
- Total shipped: 153973408.5286
- Avg inventory: 2307293387.8085
- Ending inventory: 2332320206.0493
- Transport cost: 1143534.8731
- Holding cost (capital tied-up): 27515882.9559
- Warehouse operating cost: 35377563.8005
- Inventory risk cost (obsolescence/compliance proxy): 15723361.6891
- Legacy raw holding cost before split: 78616808.4455
- Purchase cost (from order_terms sell_price): 5289146.7322
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 79760343.3186
- Total cost: 85049490.0508
- Total external procured ordered qty: 1324914.1334
- Total external procured arrived qty: 1226528.5334
- Total external procured rejected qty (cap-limited): 353910614.7438
- Total external procurement cost premium: 335244.4508
- Total estimated source ordered qty: 0.0
- Total estimated source replenished qty: 1580989730.825
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.323528 / 0.415964 / 0.184873 / 0.013446 / 0.062189
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 272360187.8265
- Total explicit initialization pipeline qty: 2055441163.8865
- Total opening open-order qty: 0.0
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 216262050.7826
- Economic consistency status: warn
- Economic consistency warnings: ['transport_cost_share_below_2pct']

## Top backlog pairs
[]

## Safety stock reference
Calcul: `stock equiv delai = demande moyenne journaliere MRP x delai de securite`. Quand une trace MRP existe, la demande moyenne vient du signal reel utilise par le MRP (`bb_demand_signal_qty`), pas d'une capacite ou d'un besoin statique gonfle. Si le mode strict est actif, le plancher physique MRP vient uniquement de cette couverture de delai de securite. La cible physique simulee applique le facteur global `0.75` ou un facteur specifique par couple si renseigne.

| Scope | Noeud | Item | Delai secu j | Demande MRP moy/j | Stock equiv delai moy | Cible physique moy | Max cible physique | Base | Unite |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| finished_good | DC-1920 | item:268091 | 20.0 | 9798.471233 | 195969.424658 | 146977.068493 | 299880.0 | mrp_trace_demand_signal | UN |
| finished_good | DC-1920 | item:268967 | 25.0 | 4317.769863 | 107944.246573 | 80958.18493 | 444115.178569 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:038005 | 20.0 | 2694.873104 | 53897.46208 | 40423.09656 | 40423.09656 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:042342 | 5.0 | 9292668.0 | 46463340.0 | 34847505.0 | 34847505.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:333362 | 10.0 | 154000.0 | 1540000.0 | 1155000.0 | 1155000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:344135 | 10.0 | 154000.0 | 1540000.0 | 1155000.0 | 1155000.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:708073 | 10.0 | 1221.22 | 12212.2 | 9159.15 | 9159.15 | mrp_trace_demand_signal | KG |
| input_material | M-1430 | item:730384 | 10.0 | 32648.0 | 326480.0 | 244860.0 | 244860.0 | mrp_trace_demand_signal | M |
| input_material | M-1430 | item:734545 | 10.0 | 1232.0 | 12320.0 | 9240.0 | 9240.0 | mrp_trace_demand_signal | UN |
| input_material | M-1430 | item:773474 | 20.0 | 1486826.572 | 29736531.44 | 22302398.58 | 22302398.58 | mrp_trace_demand_signal | G |
| input_material | M-1810 | item:001757 | 20.0 | 330.5652 | 6611.304 | 4958.478 | 4958.478 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001848 | 20.0 | 247.9239 | 4958.478 | 3718.8585 | 3718.8585 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:001893 | 15.0 | 1570.1847 | 23552.7705 | 17664.577875 | 17664.577875 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:002612 | 20.0 | 413.2065 | 8264.13 | 6198.0975 | 6198.0975 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:007923 | 15.0 | 661.1304 | 9916.956 | 7437.717 | 7437.717 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:016332 | 7.0 | 99.16956 | 694.18692 | 520.64019 | 520.64019 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:029313 | 7.0 | 8.26413 | 57.84891 | 43.386683 | 43.386683 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:039668 | 7.0 | 8.26413 | 57.84891 | 43.386683 | 43.386683 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:049371 | 40.0 | 305.77281 | 12230.9124 | 9173.1843 | 9173.1843 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:055703 | 30.0 | 16.52826 | 495.8478 | 371.88585 | 371.88585 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:099439 | 7.0 | 413.2065 | 2892.4455 | 2169.334125 | 2169.334125 | mrp_trace_demand_signal | KG |
| input_material | M-1810 | item:338928 | 10.0 | 203550.0 | 2035500.0 | 1526625.0 | 1526625.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:338929 | 10.0 | 203550.0 | 2035500.0 | 1526625.0 | 1526625.0 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:426331 | 7.0 | 2239.05 | 15673.35 | 11755.0125 | 11755.0125 | mrp_trace_demand_signal | UN |
| input_material | M-1810 | item:693055 | 20.0 | 82641.3 | 1652826.0 | 1239619.5 | 1239619.5 | mrp_trace_demand_signal | G |
| input_material | SDC-1450 | item:021081 | 0.0 | 0.0 | 0.0 | 900000.0 | 900000.0 | mrp_trace_demand_signal | KG |

## Remarques validation industrielle
Le graphe `Reappro amont` utilise maintenant `order_date_IMT` pour dater les ordres MRP. Les commandes du carnet initial peuvent donc apparaitre avant J0 au lieu d'etre empilees artificiellement au 1er janvier.

| Noeud | Item | Lot std | Ancien pic J0 | Pic IMT | Jour IMT | Avant J0 | Lots au pic | Remarque |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M-1430 | 042342 | 30000000.0 | 0.0 | 30000000.0 | 43 | 0.0 | 1.0 | Lot FIA tres eleve a valider avec l'industriel. |
| M-1430 | 773474 | 1.0 | 9600000.0 | 984838.0 | -2 | 6290627.0 | 984838.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 344135 | 120000.0 | 1800000.0 | 120000.0 | -12 | 600000.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 338929 | 5000.0 | 1900000.0 | 50000.0 | 49 | 125000.0 | 10.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1430 | 333362 | 5000.0 | 1660000.0 | 25000.0 | 21 | 1040000.0 | 5.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 001893 | 23920.0 | 67620.0 | 23920.0 | -30 | 68740.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1430 | 038005 | 10000.0 | 30000.0 | 10000.0 | -90 | 20000.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 693055 | 1.0 | 731314.0 | 8739.0 | 42 | 541808.0 | 8739.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 734545 | 6300.0 | 18900.0 | 6300.0 | -33 | 12600.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 049371 | 1600.0 | 9600.0 | 1600.0 | -16 | 3200.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |

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
- data/production_supplier_capacity_daily.csv
- Additional detailed CSVs: skipped in compact mode
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (not generated)
