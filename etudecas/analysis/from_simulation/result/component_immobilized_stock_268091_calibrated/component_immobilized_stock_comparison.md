# Stock composants immobilise - comparaison simulation / reel

- Run: `etudecas\simulation\result\_experiments\stock_target_268091_snapshotfix\365d\mc_refine_028_s2_soft025_cap050_strict_fia_orders\run`
- Produits compares: 268091

## Lecture

- Le fichier reel expose `Sum_Valeur totale du stock`: la comparaison principale est donc la valeur totale du stock composant simule.
- Les lignes `Diagnostic` ne sont pas le KPI reel: elles indiquent seulement la part au-dessus d'une couverture 90j ou au-dessus de la cible MRP.
- Pour simuler le stock immobilise reel, lire d'abord `Stock composant total valorise`.

## Resultats

| Produit | Lecture simulation | Role | Reel moyen | Simulation moyenne | Ecart | Ecart % |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 268091 | Stock composant total valorise | comparaison directe | 259 678 EUR | 374 947 EUR | 115 268 EUR | 44.4% |
| 268091 | Diagnostic: excedent au-dessus couverture 90j | diagnostic | 259 678 EUR | 207 440 EUR | -52 239 EUR | -20.1% |
| 268091 | Diagnostic: excedent au-dessus cible MRP | diagnostic | 259 678 EUR | 349 959 EUR | 90 281 EUR | 34.8% |

## Sources

- 268091: `C:\dev\lca-simu\etudecas\data\source\Stock_Composants_Immobilisé_Pharma.csv`
