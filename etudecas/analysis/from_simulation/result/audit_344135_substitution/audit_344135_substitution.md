# Audit substitution 344135

## Conclusion

- Aucune règle explicite de remplacement/substitution pour `344135` n'a été trouvée dans les fichiers source actifs.
- `344135` est présent comme composant `Pack` du PF `268967`, ratio `1000 UN / 1000 PF`, dans `268967.xlsx`, `Data_poc.xlsx` et `demand_PF.xlsx`.
- Le stock source de `344135` au 2025-01-01 est `0 ZUN` à Gien `1430`.
- `Extract_En_cours.xlsx` ne contient aucun ordre ouvert pour `344135`.
- Les références `338928` et `338929` sont structurellement proches (`Pack`, `1000 UN / 1000 PF`) mais elles appartiennent au PF `268091` sur Avène `1810`; ce ne sont pas des substituts déclarés de `344135`.

## Lecture métier

Si `344135` peut réellement être remplacé par une autre référence, il manque une donnée de correspondance article dans les sources. Sans cette table, la simulation a raison de bloquer la première production `268967` jusqu'à arrivée de `344135`.

## Fichiers générés

- `bom_pack_candidate_comparison.csv`
- `source_search_hits.csv`
- `344135_open_orders.csv`
- `344135_stock_rows.csv`
- `summary.json`