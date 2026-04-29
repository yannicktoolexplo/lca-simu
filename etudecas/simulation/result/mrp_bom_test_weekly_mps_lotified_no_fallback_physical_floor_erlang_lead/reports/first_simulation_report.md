# First simulation report

## Run setup
- Input: etudecas\simulation_prep\result\reference_baseline\_mrp_bom_tests\bom_weekly_mps_lotified_no_static_fallback_physical_floor.json
- Scenario: scn:BASE
- Measured horizon (days): 1825
- Warm-up (days): 0
- Total simulated timeline (days): 1825
- Output profile: full
- Safety stock policy (days): 7.0
- Replenishment review period (days): 1
- Finished-goods target cover (days): 0.0
- Production stock-gap gain: 0.25
- Production smoothing factor: 0.2
- Opening stock bootstrap scale: 1.0
- Initialization mode: explicit_state
- Initialization stock days factory / supplier FG / DC / customer: 0.0 / 0.0 / 0.0 / 0.0
- Initialization seed in-transit / fill ratio / estimated-source pipeline: False / 1.0 / False
- Opening open-orders reconstruction enabled / horizon days: True / 0
- Opening open-orders demand multiplier / BOM signal for MRP: 1.0 / True
- MRP demand signal source: mps_lotified
- MRP demand signal smoothing / static fallback on propagated pairs: 7 j / False
- MRP physical safety floor enforced: True
- Soft safety-time physical stock target factor: 1.0
- Unmodeled supplier source mode: external_procurement
- Stochastic lead times: True
- Lead-time distribution mode: erlang
- Random seed: 42
- Economic policy transport floor /km: 0.02 / 8e-05
- Economic policy purchase floor: 0.01
- Holding cost scale: 0.09
- Inventory cost split capital / warehouse / risk: 0.35 / 0.45 / 0.2
- Transport / purchase realism multipliers: 0.2 / 1.0
- External procurement enabled: True
- External procurement proactive supplier replenishment: True
- External procurement lead days: 4
- External procurement daily cap days: 999.0
- External procurement min daily cap qty: 1000000000.0
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
- Opening open-order rows reconstructed from January snapshot: 106
- MRP trace tracked pairs / rows / orders: 65 / 118625 / 60535

## KPIs
- Total demand: 25762139.9999
- Total served: 25762139.9999
- Fill rate: 1.0
- Ending backlog: 0
- Total produced: 103029000.0
- Total shipped: 736503962.0063
- Avg inventory: 317836296.4175
- Ending inventory: 286784552.0343
- Transport cost: 7192550.361
- Holding cost (capital tied-up): 27987621.4351
- Warehouse operating cost: 35984084.7023
- Inventory risk cost (obsolescence/compliance proxy): 15992926.5343
- Legacy raw holding cost before split: 79964632.6717
- Purchase cost (from order_terms sell_price): 66524394.9906
- Logistics cost (transport + inventory capital + warehouse + inventory risk): 87157183.0327
- Total cost: 153681578.0233
- Total external procured ordered qty: 440238013.3253
- Total external procured arrived qty: 440237916.5576
- Total external procured rejected qty (cap-limited): 0.0
- Total external procurement cost premium: 1492617821.7454
- Total estimated source ordered qty: 0.0
- Total estimated source replenished qty: 0.0
- Total estimated source rejected qty: 0.0
- Cost share capital holding / warehouse / inventory risk / transport / purchase: 0.182114 / 0.234147 / 0.104065 / 0.046802 / 0.432872
- Total opening stock bootstrap qty: 0.0
- Total explicit initialization stock qty: 273044347.8265
- Total explicit initialization pipeline qty: 25012341.2857
- Total opening open-order qty: 25012341.2857
- Total unreliable supplier loss qty: 0.0
- Total supplier capacity binding qty: 47686509.5802
- Economic consistency status: ok
- Economic consistency warnings: []

## Top backlog pairs
[]

## Safety stock reference
Calcul: `stock equiv delai = demande moyenne journaliere planifiee x delai de securite`. Les `safety_stock_qty` explicites sont ignores dans cette variante: seules les durees de securite pilotent la cible. La cible souple simulee applique le facteur `1.0` sur cette couverture.

| Scope | Noeud | Item | Delai secu j | Demande moy/j | Stock equiv delai | Cible souple sim | Unite |
|---|---:|---:|---:|---:|---:|---:|---|
| finished_good | DC-1920 | item:268091 | 20.0 | 1900.0 | 38000.0 | 38000.0 | UN |
| finished_good | DC-1920 | item:268967 | 25.0 | 2562.857143 | 64071.428575 | 64071.428575 | UN |
| input_material | M-1430 | item:038005 | 20.0 | 2694.873104 | 53897.46208 | 53897.46208 | KG |
| input_material | M-1430 | item:042342 | 5.0 | 9292668.0 | 46463340.0 | 46463340.0 | UN |
| input_material | M-1430 | item:333362 | 10.0 | 154000.0 | 1540000.0 | 1540000.0 | UN |
| input_material | M-1430 | item:344135 | 10.0 | 154000.0 | 1540000.0 | 1540000.0 | UN |
| input_material | M-1430 | item:708073 | 10.0 | 1221.22 | 12212.2 | 12212.2 | KG |
| input_material | M-1430 | item:730384 | 10.0 | 32648.0 | 326480.0 | 326480.0 | M |
| input_material | M-1430 | item:734545 | 10.0 | 1232.0 | 12320.0 | 12320.0 | UN |
| input_material | M-1430 | item:773474 | 20.0 | 1486826.572 | 29736531.44 | 29736531.44 | G |
| input_material | M-1810 | item:001757 | 20.0 | 330.5652 | 6611.304 | 6611.304 | KG |
| input_material | M-1810 | item:001848 | 20.0 | 247.9239 | 4958.478 | 4958.478 | KG |
| input_material | M-1810 | item:001893 | 15.0 | 1570.1847 | 23552.7705 | 23552.7705 | KG |
| input_material | M-1810 | item:002612 | 20.0 | 413.2065 | 8264.13 | 8264.13 | KG |
| input_material | M-1810 | item:007923 | 15.0 | 661.1304 | 9916.956 | 9916.956 | KG |
| input_material | M-1810 | item:016332 | 7.0 | 99.16956 | 694.18692 | 694.18692 | KG |
| input_material | M-1810 | item:029313 | 7.0 | 8.26413 | 57.84891 | 57.84891 | KG |
| input_material | M-1810 | item:039668 | 7.0 | 8.26413 | 57.84891 | 57.84891 | KG |
| input_material | M-1810 | item:049371 | 40.0 | 305.77281 | 12230.9124 | 12230.9124 | KG |
| input_material | M-1810 | item:055703 | 30.0 | 16.52826 | 495.8478 | 495.8478 | KG |
| input_material | M-1810 | item:099439 | 7.0 | 413.2065 | 2892.4455 | 2892.4455 | KG |
| input_material | M-1810 | item:338928 | 10.0 | 203550.0 | 2035500.0 | 2035500.0 | UN |
| input_material | M-1810 | item:338929 | 10.0 | 203550.0 | 2035500.0 | 2035500.0 | UN |
| input_material | M-1810 | item:426331 | 7.0 | 2239.05 | 15673.35 | 15673.35 | UN |
| input_material | M-1810 | item:693055 | 20.0 | 82641.3 | 1652826.0 | 1652826.0 | G |

## Remarques validation industrielle
Le graphe `Reappro amont` utilise maintenant `order_date_IMT` pour dater les ordres MRP. Les commandes du carnet initial peuvent donc apparaitre avant J0 au lieu d'etre empilees artificiellement au 1er janvier.

| Noeud | Item | Lot std | Ancien pic J0 | Pic IMT | Jour IMT | Avant J0 | Lots au pic | Remarque |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M-1810 | 338928 | 25000.0 | 0.0 | 275000.0 | 732 | 0.0 | 11.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1810 | 338929 | 5000.0 | 0.0 | 130000.0 | 227 | 0.0 | 26.0 | Concentration MRP a valider; plusieurs lots commandes le meme jour IMT. |
| M-1430 | 042342 | 30000000.0 | 60000000.0 | 30000000.0 | -24 | 180000000.0 | 1.0 | Lot FIA tres eleve a valider avec l'industriel. |
| M-1430 | 773474 | 1.0 | 6431833.0 | 1153761.0 | 1266 | 5153409.0 | 1153761.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 344135 | 120000.0 | 840000.0 | 240000.0 | 0 | 600000.0 | 2.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1810 | 693055 | 1.0 | 0.0 | 49414.0 | 228 | 0.0 | 49414.0 | Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner. |
| M-1430 | 333362 | 5000.0 | 3910000.0 | 45000.0 | -21 | 940000.0 | 9.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |
| M-1430 | 038005 | 10000.0 | 70000.0 | 10000.0 | -90 | 70000.0 | 1.0 | Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige. |

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
- Additional detailed CSVs: generated
- production_input_stocks_by_material_*.png (not generated)
- production_output_products.png (not generated)
- production_output_products_by_factory_*.png (not generated)
- production_supplier_input_stocks_by_material_*.png (not generated)
- production_dc_factory_outputs_by_material_*.png (not generated)
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html (etudecas\simulation\result\mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_erlang_lead\maps\supply_graph_mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_erlang_lead.html)
