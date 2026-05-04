# Diagnostic baseline supply physique

Baseline auditee: `mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test`.
JSON source: `etudecas/simulation_prep/result/reference_baseline/_mrp_bom_tests/bom_weekly_mps_lotified_no_static_fallback_physical_floor.json`.

## 1. Integrite JSON
|Controle|Resultat|
|---|---|
|Items|26|
|Noeuds|35|
|Flux|39|
|Scenarios|1|
|Ordres ouverts embarques JSON|88|
|References cassees|0|
|Horizon|{'steps_to_run': 1825, 'time_unit': 'Day', 'repeat_period_days': 365}|
Aucune reference cassee detectee dans le JSON.

## 2. Integrite CSV
|Fichier|Lignes|Jours|Qt neg|Non numerique|
|---|---|---|---|---|
|assumptions_ledger.csv|223||0|0|
|first_simulation_daily.csv|1825|0..1824|0|0|
|mrp_orders_daily.csv|31992|0..1824|0|0|
|mrp_trace_daily.csv|118625|0..1824|0|0|
|production_constraint_daily.csv|1112|0..1819|0|0|
|production_dc_stocks_daily.csv|3650|0..1824|0|0|
|production_demand_service_daily.csv|3650|0..1824|0|0|
|production_input_consumption_daily.csv|43800|0..1824|0|0|
|production_input_replenishment_arrivals_daily.csv|43800|0..1824|0|0|
|production_input_replenishment_shipments_daily.csv|43800|0..1824|0|0|
|production_input_stocks_daily.csv|43800|0..1824|0|0|
|production_input_stocks_pivot.csv|1825|0..1824|0|0|
|production_output_products_daily.csv|5475|0..1824|0|0|
|production_supplier_capacity_daily.csv|60225|0..1824|0|0|
|production_supplier_shipments_daily.csv|30294|-140..1907|0|0|
|production_supplier_stocks_daily.csv|60225|0..1824|0|0|
|supplier_local_criticality_ranking.csv|29||0|0|
Remarque: `production_supplier_shipments_daily.csv` contient des jours <0 et >1824 car les ordres ouverts peuvent etre lances avant J0 ou arriver apres horizon.

## 3. Produits finis et service client
|PF|Demande 5y|Servi 5y|Fill rate|Production usine|Backlog final|Jours backlog|
|---|---|---|---|---|---|---|
|268091|17.88M|17.88M|100.00%|16.01M|0.0|1|
|268967|7.88M|7.88M|100.00%|7.11M|0.0|2|
Constat: le service client est rempli a 100%, avec quelques jours de backlog transitoire seulement.

## 4. Production et lots
|Noeud|Item produit|Production 5y|Lot|Nb lots|Jours prod|Max/jour|Max lots/sem|
|---|---|---|---|---|---|---|---|
|M-1430|268967|7.11M|107.8k|66.0|66|107.8k|10.0|
|M-1810|268091|16.01M|14.4k|1112.0|1019|28.8k|10.0|
|SDC-1450|773474|83.20M|3.20M|26.0|25|6.40M|10.0|
Constat: M-1810 produit quasi quotidiennement de petits lots multiples; M-1430 et D-1450 restent fortement campagne/lotifies.

## 5. Matieres usine: consommation, stock, cible
|Noeud|Matiere|Conso 5y|Arrivages|Stock init|Stock min|Stock final|Cible max|Jours sous cible|Min gap|Couverture init+arr|Diagnostic|
|---|---|---|---|---|---|---|---|---|---|---|---|
|M-1430|038005|124.5k|220.0k|37.6k|35.7k|133.1k|128.3k|36|-92.6k|10.3|surcouverture forte, sous cible ponctuel|
|M-1430|042342|429.32M|480.00M|78.75M|72.25M|129.43M|78.75M|42|-6.50M|6.5|surcouverture, sous cible ponctuel|
|M-1430|333362|7.11M|8.59M|142.2k|34.5k|1.62M|1.83M|65|-1.80M|6.1|surcouverture, sous cible ponctuel|
|M-1430|344135|7.11M|11.88M|754.6k|646.8k|5.52M|5.71M|74|-5.07M|8.9|surcouverture, sous cible ponctuel|
|M-1430|708073|56.4k|85.0k|10.3k|9.5k|38.9k|38.5k|45|-29.0k|8.4|surcouverture, sous cible ponctuel|
|M-1430|730384|1.51M|5.18M|68.4k|45.5k|3.74M|1.81M|57|-1.76M|17.4|surcouverture forte, sous cible ponctuel|
|M-1430|734545|56.9k|88.3k|1.6k|778.6|33.0k|27.6k|41|-26.8k|7.9|surcouverture, sous cible ponctuel|
|M-1430|773474|68.69M|87.92M|14.59M|13.55M|33.83M|34.35M|76|-20.79M|7.5|surcouverture, sous cible ponctuel|
|M-1810|001757|26.0k|45.9k|8.5k|7.3k|28.4k|8.5k|127|-1.2k|10.5|surcouverture forte, sous cible ponctuel|
|M-1810|001848|19.5k|50.0k|10.3k|10.2k|40.8k|10.3k|21|-52.6|15.4|surcouverture forte, sous cible ponctuel|
|M-1810|001893|123.5k|405.7k|9.8k|9.2k|292.0k|18.7k|28|-555.4|16.8|surcouverture forte, sous cible ponctuel|
|M-1810|002612|32.5k|587.1k|153.5k|153.4k|708.1k|153.5k|29|-146.2|113.9|surcouverture forte, sous cible ponctuel|
|M-1810|007923|52.0k|52.3k|55.0k|54.7k|55.3k|55.0k|376|-320.5|10.3|surcouverture forte, sous cible ponctuel|
|M-1810|016332|7.8k|12.1k|883.0|847.9|5.2k|940.1|49|-35.1|8.3|surcouverture, sous cible ponctuel|
|M-1810|029313|650.1|3.6k|226.8|221.0|3.2k|226.8|56|-5.8|29.4|surcouverture forte, sous cible ponctuel|
|M-1810|039668|650.1|3.1k|459.7|456.8|3.0k|459.7|35|-2.9|27.8|surcouverture forte, sous cible ponctuel|
|M-1810|049371|24.1k|34.2k|4.1k|4.0k|14.3k|4.1k|26|-108.2|8.0|surcouverture, sous cible ponctuel|
|M-1810|055703|1.3k|2.7k|569.8|567.5|2.0k|569.8|20|-2.3|12.6|surcouverture forte, sous cible ponctuel|
|M-1810|099439|32.5k|33.6k|5.0k|4.8k|6.1k|5.0k|33|-146.2|5.9|surcouverture, sous cible ponctuel|
|M-1810|338928|16.01M|15.87M|404.1k|120.7k|256.3k|2.28M|409|-2.15M|5.1|surcouverture, sous cible ponctuel|
|M-1810|338929|16.01M|23.16M|354.0k|0.0|7.50M|1.38M|246|-1.38M|7.3|surcouverture, sous cible ponctuel|
|M-1810|426331|176.1k|268.8k|24.2k|20.9k|116.8k|24.2k|59|-3.2k|8.3|surcouverture, sous cible ponctuel|
|M-1810|693055|6.50M|16.39M|1.01M|614.7k|10.90M|1.23M|225|-613.1k|13.4|surcouverture forte, sous cible ponctuel|
|SDC-1450|021081|743.8k|1.32M|1.14M|970.5k|1.72M|900.0k|0|70.5k|16.6|surcouverture forte|
Lecture: la couverture est calculee comme (stock initial + arrivages fermes) / consommation annuelle moyenne simulee.

## 6. Flux transport et fournisseurs
|Source|Destination|Item|Qte expediee|Lignes|Jours envoi|Jours reception|Lead moyen|Envois hors horizon|Base|
|---|---|---|---|---|---|---|---|---|---|
|SDC-VD0914690A|M-1430|042342|480.00M|16|-5..1463|21..1483|23.6|1|{'opening_order_book': 2, 'lot': 14}|
|SDC-1450|M-1430|773474|88.44M|912|0..1821|10..1830|10.1|0|{'lot': 912}|
|SDC-VD0914360C|M-1810|338929|23.16M|4165|-34..1708|14..1750|42.4|1|{'opening_order_book': 1, 'lot': 4164}|
|SDC-VD0901566A|M-1810|338928|21.47M|847|-62..1907|16..1977|70.1|148|{'opening_order_book': 3, 'lot': 844}|
|DC-1920|C-XXXXX|268091|18.06M|1515|0..1817|1..1819|2.1|0|{'unit': 1515}|
|M-1810|DC-1920|268091|17.94M|1181|17..1818|19..1820|2.1|0|{'unit': 1181}|
|SDC-1450|M-1810|693055|16.39M|17556|0..1167|70..1237|70.2|0|{'lot': 17556}|
|SDC-VD0993480A|M-1430|344135|12.12M|101|0..1810|35..1845|35.1|0|{'lot': 101}|
|SDC-VD0525412A|M-1430|333362|8.81M|1480|-6..1881|58..1941|60.1|30|{'opening_order_book': 6, 'lot': 1474}|
|DC-1920|C-XXXXX|268967|7.94M|891|0..1810|2..1812|2.1|0|{'unit': 891}|
|M-1430|DC-1920|268967|7.04M|269|165..1810|166..1813|2.1|0|{'unit': 269}|
|SDC-VD0508918A|M-1430|730384|5.18M|14|0..67|57..124|58.5|0|{'lot': 14}|
|SDC-VD0960508A|SDC-1450|021081|820.0k|9|-114..19|112..261|234.4|7|{'opening_order_book': 9}|
|SDC-VD0949099A|SDC-1450|021081|300.0k|8|-114..4|112..247|232.8|7|{'opening_order_book': 8}|
|SDC-VD0989480A|M-1810|426331|268.8k|14|0..1663|29..1691|28.6|0|{'opening_order_book': 1, 'lot': 13}|
|SDC-VD0520132A|M-1430|038005|220.0k|22|-140..1631|34..1794|163.3|9|{'opening_order_book': 9, 'lot': 13}|
|SDC-VD0910216A|M-1810|002612|180.0k|8|-16..25|29..60|37.4|1|{'opening_order_book': 2, 'lot': 6}|
|SDC-VD0910216A|M-1810|001893|143.5k|6|0..25|28..55|28.3|0|{'lot': 6}|
|SDC-VD0990780A|M-1810|002612|142.5k|6|1..26|36..61|35.5|0|{'lot': 6}|
|SDC-VD0518684A|M-1810|001893|136.8k|6|2..27|55..83|55.0|0|{'lot': 6}|
|SDC-VD1091642A|M-1810|002612|135.0k|6|2..27|37..62|35.2|0|{'lot': 6}|
|SDC-VD0500655A|M-1810|002612|129.6k|6|3..28|31..56|29.2|0|{'lot': 6}|
|SDC-VD1091642A|M-1810|001893|125.4k|6|1..26|43..68|42.0|0|{'lot': 6}|
|SDC-VD0972460A|SDC-1450|021081|100.0k|3|-107..-58|119..174|228.7|3|{'opening_order_book': 3}|
|SDC-VD0975221A|SDC-1450|021081|100.0k|3|-107..-58|119..174|229.7|3|{'opening_order_book': 3}|
|SDC-VD0520115A|M-1430|708073|85.0k|17|0..1628|27..1656|27.7|0|{'lot': 17}|
|SDC-VD1095770A|M-1430|734545|81.9k|13|0..1790|21..1812|21.4|0|{'lot': 13}|
|SDC-VD0951020A|M-1810|001757|45.9k|382|-75..1127|28..1211|84.3|3|{'opening_order_book': 3, 'lot': 379}|
|SDC-VD0956464A|M-1810|007923|42.4k|377|0..1822|2..1825|3.2|0|{'opening_order_book': 1, 'unit': 376}|
|SDC-VD0505677A|M-1810|099439|33.6k|8|0..31|33..66|34.5|0|{'lot': 8}|
|SDC-VD0951020A|M-1810|001848|30.0k|5|-6..16|57..72|59.6|1|{'opening_order_book': 1, 'lot': 4}|
|SDC-VD0519670A|M-1810|001848|20.0k|5|0..20|21..41|21.0|0|{'lot': 5}|
|SDC-VD0518550B|M-1810|049371|19.8k|11|-133..-7|26..153|159.2|11|{'opening_order_book': 11}|
|SDC-VD0520132A|M-1810|049371|14.4k|9|0..24|147..176|148.4|0|{'lot': 9}|
|SDC-VD0514881A|M-1810|016332|12.1k|11|0..46|49..95|49.5|0|{'lot': 11}|
|SDC-VD0951020A|M-1810|007923|9.9k|376|0..1822|3..1824|3.1|0|{'unit': 376}|
|SDC-VD0951020A|M-1430|001848|7.0k|1|22..22|42..42|20.0|0|{'opening_order_book': 1}|
|SDC-VD0525906A|M-1430|734545|6.4k|1|-16..-16|5..5|21.0|1|{'opening_order_book': 1}|
|SDC-VD0519670A|M-1810|029313|3.6k|12|0..55|56..111|55.6|0|{'lot': 12}|
|SDC-VD1096202A|M-1810|039668|3.1k|7|0..30|35..65|34.7|0|{'lot': 7}|
|SDC-VD0914320A|M-1810|055703|1.5k|5|-5..15|20..38|25.6|1|{'opening_order_book': 1, 'lot': 4}|
|SDC-VD0964290A|M-1810|055703|1.2k|4|1..16|43..56|41.8|0|{'lot': 4}|
Constat: les gros volumes sont 042342, 773474, 338929, 338928, 268091 et 693055. Les envois hors horizon sont attendus pour les ordres ouverts et les ordres en fin de simulation.

## 7. Stocks fournisseurs et capacite
|Fournisseur|Item|Expedie|Utilise capacite|Cap totale|Util max|Stock min|Stock final|Jours stock zero|Diagnostic|
|---|---|---|---|---|---|---|---|---|---|
|SDC-VD0500655A|002612|129.6k|129.6k|371.01M|0.11|0.0|21.6k|15|stock fournisseur a zero|
|SDC-VD0505677A|099439|33.6k|33.6k|301.64M|0.03|0.0|4.3k|10|stock fournisseur a zero|
|SDC-VD0508918A|730384|5.18M|5.18M|23.83B|0.06|0.0|370.0k|25|stock fournisseur a zero|
|SDC-VD0514881A|016332|12.1k|12.1k|72.39M|0.03|0.0|1.1k|15|stock fournisseur a zero|
|SDC-VD0518684A|001893|136.8k|136.8k|1.15B|0.04|0.0|22.8k|15|stock fournisseur a zero|
|SDC-VD0519670A|001848|20.0k|20.0k|180.98M|0.04|0.0|4.0k|15|stock fournisseur a zero|
|SDC-VD0519670A|029313|3.6k|3.6k|15.02M|0.04|0.0|300.0|30|stock fournisseur a zero|
|SDC-VD0520115A|708073|85.0k|85.0k|891.49M|0.05|0.0|5.0k|45|stock fournisseur a zero|
|SDC-VD0520132A|038005|220.0k|130.0k|1.97B|0.01|779.5|10.8k|0||
|SDC-VD0520132A|049371|14.4k|14.4k|223.21M|0.01|0.0|1.6k|10|stock fournisseur a zero|
|SDC-VD0525412A|333362|8.81M|8.18M|112.42B|0.02|66.0k|616.0k|0||
|SDC-VD0901566A|338928|21.47M|21.10M|584.00B|0.00|767.0|2.2k|0||
|SDC-VD0910216A|001893|143.5k|143.5k|1.15B|0.04|0.0|23.9k|15|stock fournisseur a zero|
|SDC-VD0910216A|002612|180.0k|135.0k|312.86M|0.13|0.0|22.5k|15|stock fournisseur a zero|
|SDC-VD0914320A|055703|1.5k|1.2k|15.02M|0.04|0.0|300.0|10|stock fournisseur a zero|
|SDC-VD0914360C|338929|23.16M|23.11M|148.59B|0.01|0.0|814.2k|2|stock fournisseur a zero|
|SDC-VD0914690A|042342|480.00M|420.00M|6783.65B|0.01|5.85M|37.17M|0||
|SDC-VD0949099A|021081|300.0k|0.0|36.50M|0.00|20.0k|57.2k|0|ordres ouverts seulement|
|SDC-VD0951020A|001757|45.9k|37.9k|241.31M|0.01|4.1|1.3k|0||
|SDC-VD0951020A|001848|37.0k|24.0k|180.98M|0.06|0.0|6.0k|10|stock fournisseur a zero|
|SDC-VD0951020A|007923|9.9k|9.9k|482.63M|0.00|1.0k|1.3k|0||
|SDC-VD0956464A|007923|42.4k|23.2k|482.63M|0.00|629.6|1.2k|0||
|SDC-VD0960508A|021081|820.0k|0.0|36.50M|0.00|20.0k|57.2k|0|ordres ouverts seulement|
|SDC-VD0964290A|055703|1.2k|1.2k|15.02M|0.04|0.0|300.0|10|stock fournisseur a zero|
|SDC-VD0972460A|021081|100.0k|0.0|36.50M|0.00|20.0k|57.2k|0|ordres ouverts seulement|
|SDC-VD0975221A|021081|100.0k|0.0|36.50M|0.00|20.0k|57.2k|0|ordres ouverts seulement|
|SDC-VD0989480A|426331|268.8k|249.6k|1.63B|0.02|0.0|31.1k|16|stock fournisseur a zero|
|SDC-VD0990780A|002612|142.5k|142.5k|330.24M|0.13|0.0|23.8k|15|stock fournisseur a zero|
|SDC-VD0993480A|344135|12.12M|12.12M|112.42B|0.07|16.0k|616.0k|0||
|SDC-VD1091642A|001893|125.4k|125.4k|1.15B|0.03|0.0|20.9k|15|stock fournisseur a zero|
|SDC-VD1091642A|002612|135.0k|135.0k|312.86M|0.13|0.0|22.5k|15|stock fournisseur a zero|
|SDC-VD1095770A|734545|81.9k|81.9k|899.36M|0.04|0.0|6.3k|50|stock fournisseur a zero|
|SDC-VD1096202A|039668|3.1k|3.1k|15.02M|0.05|0.0|461.7|20|stock fournisseur a zero|
Constat: aucune capacite fournisseur n est depassee. Les zeros fournisseur traduisent surtout un modele external procurement/proactive tres juste-a-temps, pas une rupture bloquante.

## 8. Ordres MRP / carnet
|Type ordre|Nombre|
|---|---|
|lane_release / ordre_flux|30228|
|external_procurement_proactive|1131|
|external_procurement|545|
|opening_purchase_order|66|
|opening_production_order|22|
|Statut fin|Nombre|
|---|---|
|received|31705|
|released_in_transit|287|
- `opening_purchase_order` et `opening_production_order` viennent de `Extract_En_cours.xlsx`.
- `lane_release` est l'identifiant technique CSV; l'affichage metier est `ordre_flux`.
- `external_procurement*` represente le realimentement amont fournisseur non facture dans les couts metier, mais utile pour eviter un fournisseur artificiellement limite.

## 9. Points coherents et points a valider
### Coherent
- Le service client PF est a 100% sur les deux PF.
- Les references JSON sont coherentes: pas de noeud/item/flux casse.
- Les CSV journaliers sont complets sur 1825 jours pour les paires attendues.
- Les ordres ouverts 021081 vers D-1450 correspondent exactement aux dates d entree et quantites de `Extract_En_cours.xlsx`.
- Les scripts principaux passent une validation syntaxique AST.

### A valider / clarifier
- La couverture 021081 est tres forte: stock initial + ordres ouverts = environ 16.6 ans de consommation simulee.
- Beaucoup de matieres ont une couverture init+arrivages >5 ans, surtout parce que les cibles base-stock par paire restent actives pour M-1430/M-1810.
- Plusieurs matieres passent sous cible MRP ponctuellement; la conformite `mrp_safety_arrival_compliance` reste OK car elle controle les arrivees planifiees, pas le maintien physique permanent au-dessus de la cible.
- Les ordres MRP sont tres granulaires: il faut continuer a les lire comme evenements de simulation/flux consolides, pas forcement comme commandes industrielles unitaires.
- Le HTML est autosuffisant mais lourd (~16 MB); c est normal avec les series embarquees, mais il faut eviter de multiplier les variantes non retenues.

### Artefacts utiles
- `README.md`: point d'entree court pour distinguer source de verite, restitution et audit.
- JSON source: structure statique modele, reseau, BOM, politiques, ordres ouverts embarques.
- `first_simulation_summary.json`: synthese machine-readable des KPI.
- `first_simulation_report.md`: synthese humaine du run.
- `mrp_trace_daily.csv`: meilleur fichier pour expliquer chaque decision MRP jour/site/item.
- `mrp_orders_daily.csv`: carnet et ordre de flux, a consolider pour lecture industrielle.
- `production_*_daily.csv`: verite dynamique pour stocks, consommations, productions, expeditions, fournisseurs.
- HTML carte: restitution interactive, pas source de verite primaire.

### Artefacts a nettoyer ou harmoniser
- Les anciens dossiers de scenarios de test MRP ont ete supprimes; seule la baseline active est conservee dans la famille `mrp_bom_test*`.
- Les mentions `lane` restantes sont limitees aux noms internes de variables/champs techniques; l affichage metier utilise `flux`.
- Le dossier `plots` n'est pas necessaire: la carte utilise les figures Plotly embarquees.
- Les ordres external procurement devraient rester visibles pour audit technique, mais masques ou separes dans une vue metier.
