# Map Asset Audit 5Y

Total records: 363

## edge | edge | incoming | -
- : 11
- constant: 14
- quasi_constant: 10
- variable: 9

## edge | edge | outgoing | -
- : 11
- quasi_constant: 6
- variable: 27

## edge | edge | third | -
- : 11
- bar_variable: 12
- constant: 21

## node | customer | fourth | Carnet
- text: 1

## node | customer | fourth | MRP detaille
- variable: 1

## node | customer | fourth | Reappro amont
- variable: 1

## node | customer | fourth | Risque
- variable: 1

## node | customer | incoming | -
- variable: 1

## node | customer | outgoing | -
- variable: 1

## node | customer | third | -
- all_zero: 1

## node | distribution_center | fourth | Carnet
- text: 1

## node | distribution_center | fourth | MRP detaille
- variable: 1

## node | distribution_center | fourth | Reappro amont
- variable: 1

## node | distribution_center | fourth | Risque
- variable: 1

## node | distribution_center | incoming | -
- variable: 1

## node | distribution_center | outgoing | -
- step_variable: 1

## node | distribution_center | third | -
- step_variable: 1

## node | factory | fourth | Carnet
- text: 3

## node | factory | fourth | MRP detaille
- variable: 3

## node | factory | fourth | Reappro amont
- variable: 3

## node | factory | fourth | Risque
- variable: 3

## node | factory | incoming | -
- : 1
- variable: 2

## node | factory | outgoing | -
- : 1
- variable: 2

## node | factory | third | -
- : 1
- variable: 2

## node | supplier_dc | fourth | Carnet
- text: 22
- text_empty: 6

## node | supplier_dc | fourth | MRP detaille
- quasi_constant: 27
- variable: 1

## node | supplier_dc | fourth | Reappro amont
- : 6
- constant: 10
- quasi_constant: 8
- variable: 4

## node | supplier_dc | fourth | Risque
- variable: 28

## node | supplier_dc | incoming | -
- step_variable: 28

## node | supplier_dc | outgoing | -
- : 6
- constant: 4
- sparse_pulses: 13
- step_piecewise: 1
- step_variable: 4

## node | supplier_dc | third | -
- all_zero: 6
- sparse_pulses: 17
- step_piecewise: 1
- step_variable: 4

## Examples none
- none

## Examples text_empty
- node SDC-VD0500655A | fourth Carnet | html vide ou message d'absence | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0990780A | fourth Carnet | html vide ou message d'absence | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0949099A | fourth Carnet | html vide ou message d'absence | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0960508A | fourth Carnet | html vide ou message d'absence | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0972460A | fourth Carnet | html vide ou message d'absence | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0975221A | fourth Carnet | html vide ou message d'absence | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html

## Examples constant
- node SDC-VD0914690A | fourth Reappro amont | SDC-VD0914690A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 16 src, 0 dst)
- node SDC-VD0508918A | fourth Reappro amont | SDC-VD0508918A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 6 src, 0 dst)
- node SDC-VD0518684A | outgoing  | SDC-VD0518684A - expeditions journalieres par item - 001893 | serie issue de production_supplier_shipments_daily.csv par src_node_id (2 lignes)
- node SDC-VD0518684A | fourth Reappro amont | SDC-VD0518684A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (1 lignes node_id, 2 src, 1 dst)
- node SDC-VD1091642A | outgoing  | SDC-VD1091642A - expeditions journalieres par item - 001893 | serie issue de production_supplier_shipments_daily.csv par src_node_id (2 lignes)
- node SDC-VD1091642A | fourth Reappro amont | SDC-VD1091642A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (1 lignes node_id, 2 src, 1 dst)
- node SDC-VD0514881A | fourth Reappro amont | SDC-VD0514881A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 8 src, 0 dst)
- node SDC-VD1096202A | outgoing  | SDC-VD1096202A - expeditions journalieres par item - 039668 | serie issue de production_supplier_shipments_daily.csv par src_node_id (1 lignes)
- node SDC-VD1096202A | fourth Reappro amont | SDC-VD1096202A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 1 src, 0 dst)
- node SDC-VD0914320A | fourth Reappro amont | SDC-VD0914320A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 6 src, 0 dst)
- node SDC-VD0964290A | outgoing  | SDC-VD0964290A - expeditions journalieres par item - 055703 | serie issue de production_supplier_shipments_daily.csv par src_node_id (1 lignes)
- node SDC-VD0964290A | fourth Reappro amont | SDC-VD0964290A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 1 src, 0 dst)
- node SDC-VD0505677A | fourth Reappro amont | SDC-VD0505677A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 9 src, 0 dst)
- node SDC-VD0989480A | fourth Reappro amont | SDC-VD0989480A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 11 src, 0 dst)
- edge edge:SDC-VD0520132A_TO_M-1430_038005 | third  | edge:SDC-VD0520132A_TO_M-1430_038005 - statuts du carnet d'ordres | barres de statut / risque de lane; qty_constant_flag=False

## Examples quasi_constant
- node SDC-VD0520132A | fourth Reappro amont | SDC-VD0520132A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 32 src, 0 dst)
- node SDC-VD0520132A | fourth MRP detaille | SDC-VD0520132A - releases / receipts / target | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 32 src, 0 dst)
- node SDC-VD0914690A | fourth MRP detaille | SDC-VD0914690A - releases / receipts / target | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 16 src, 0 dst)
- node SDC-VD0525412A | fourth Reappro amont | SDC-VD0525412A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 74 src, 0 dst)
- node SDC-VD0525412A | fourth MRP detaille | SDC-VD0525412A - releases / receipts / target | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 74 src, 0 dst)
- node SDC-VD0993480A | fourth Reappro amont | SDC-VD0993480A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 67 src, 0 dst)
- node SDC-VD0993480A | fourth MRP detaille | SDC-VD0993480A - releases / receipts / target | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 67 src, 0 dst)
- node SDC-VD0520115A | fourth Reappro amont | SDC-VD0520115A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 2 src, 0 dst)
- node SDC-VD0520115A | fourth MRP detaille | SDC-VD0520115A - releases / receipts / target | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 2 src, 0 dst)
- node SDC-VD0508918A | fourth MRP detaille | SDC-VD0508918A - releases / receipts / target | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 6 src, 0 dst)
- node SDC-VD1095770A | fourth Reappro amont | SDC-VD1095770A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 11 src, 0 dst)
- node SDC-VD1095770A | fourth MRP detaille | SDC-VD1095770A - releases / receipts / target | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 11 src, 0 dst)
- node SDC-VD0951020A | fourth MRP detaille | SDC-VD0951020A - releases / receipts / target | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (0 lignes node_id, 1373 src, 0 dst)
- node SDC-VD0519670A | fourth Reappro amont | SDC-VD0519670A - reappro amont | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (1 lignes node_id, 8 src, 1 dst)
- node SDC-VD0519670A | fourth MRP detaille | SDC-VD0519670A - releases / receipts / target | serie MRP/reappro construite depuis model_panel et mrp_orders_daily.csv (1 lignes node_id, 8 src, 1 dst)

## Examples sparse_pulses
- node SDC-VD0520132A | outgoing  | SDC-VD0520132A - expeditions journalieres par item | serie issue de production_supplier_shipments_daily.csv par src_node_id (32 lignes)
- node SDC-VD0520132A | third  | SDC-VD0520132A - utilisation capacite par item | serie issue de production_supplier_capacity_daily.csv (3650 lignes) ou carnet MRP html
- node SDC-VD0914690A | outgoing  | SDC-VD0914690A - expeditions journalieres par item - 042342 | serie issue de production_supplier_shipments_daily.csv par src_node_id (16 lignes)
- node SDC-VD0914690A | third  | SDC-VD0914690A - utilisation capacite par item - 042342 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0525412A | outgoing  | SDC-VD0525412A - expeditions journalieres par item - 333362 | serie issue de production_supplier_shipments_daily.csv par src_node_id (74 lignes)
- node SDC-VD0525412A | third  | SDC-VD0525412A - utilisation capacite par item - 333362 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0993480A | outgoing  | SDC-VD0993480A - expeditions journalieres par item - 344135 | serie issue de production_supplier_shipments_daily.csv par src_node_id (67 lignes)
- node SDC-VD0993480A | third  | SDC-VD0993480A - utilisation capacite par item - 344135 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0520115A | outgoing  | SDC-VD0520115A - expeditions journalieres par item - 708073 | serie issue de production_supplier_shipments_daily.csv par src_node_id (2 lignes)
- node SDC-VD0520115A | third  | SDC-VD0520115A - utilisation capacite par item - 708073 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0508918A | outgoing  | SDC-VD0508918A - expeditions journalieres par item - 730384 | serie issue de production_supplier_shipments_daily.csv par src_node_id (6 lignes)
- node SDC-VD0508918A | third  | SDC-VD0508918A - utilisation capacite par item - 730384 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD1095770A | outgoing  | SDC-VD1095770A - expeditions journalieres par item - 734545 | serie issue de production_supplier_shipments_daily.csv par src_node_id (11 lignes)
- node SDC-VD1095770A | third  | SDC-VD1095770A - utilisation capacite par item - 734545 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0519670A | outgoing  | SDC-VD0519670A - expeditions journalieres par item | serie issue de production_supplier_shipments_daily.csv par src_node_id (8 lignes)

## Examples all_zero
- node SDC-VD0500655A | third  | SDC-VD0500655A - utilisation capacite par item - 002612 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0990780A | third  | SDC-VD0990780A - utilisation capacite par item - 002612 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node C-XXXXX | third  | C-XXXXX - demande du dernier jour par produit | bloc synthese HTML construit depuis les KPI client
- node SDC-VD0949099A | third  | SDC-VD0949099A - utilisation capacite par item - 021081 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0960508A | third  | SDC-VD0960508A - utilisation capacite par item - 021081 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0972460A | third  | SDC-VD0972460A - utilisation capacite par item - 021081 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
- node SDC-VD0975221A | third  | SDC-VD0975221A - utilisation capacite par item - 021081 | serie issue de production_supplier_capacity_daily.csv (1825 lignes) ou carnet MRP html
