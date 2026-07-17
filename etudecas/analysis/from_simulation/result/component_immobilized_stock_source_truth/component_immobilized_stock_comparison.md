# Stock composants immobilise - verification source vs simulation

- Run: `etudecas\simulation\result\_experiments\stock_target_268091_snapshotfix\365d\mc_refine_028_s2_soft025_cap050_strict_fia_orders\run`
- Graphe: `etudecas\simulation\result\_experiments\stock_target_268091_snapshotfix\365d\mc_refine_028_s2_soft025_cap050_strict_fia_orders\input_graph.json`
- Produits compares: 268091, 268967

## Contrat de comparaison

- Source de verite: fichiers de `etudecas/data/source`.
- Les CSV source exposent `Sum_Valeur totale du stock`: on compare donc le stock composant total valorise simule.
- Les commandes ouvertes ne sont pas ajoutees au stock tant qu'elles ne sont pas receptionnees.
- Les diagnostics de surstock (`90j`, `cible MRP`) servent a expliquer, pas a calibrer directement.
- L'alignement `previous_day` est prioritaire car les photos DMP sont vers 00:06 et la simulation stocke des fins de jour.
- Convention produit utilisee ici: `268091 -> Pharma`, `268967 -> Cos`; les workbooks source ont des libelles ambigus, donc ce mapping reste explicite.

## Resultat principal

| Produit | Alignement | Reel moyen | Simulation moyenne aux photos | Ecart | Ecart % | MAE | MAE % | Sim > reel | Composants valorises |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 268091 | previous_day | 259 678 EUR | 373 608 EUR | 113 929 EUR | 43.9% | 117 412 EUR | 45.2% | 47/52 | 14.0/15.0 |
| 268967 | previous_day | 930 695 EUR | 1 801 345 EUR | 870 650 EUR | 93.5% | 927 390 EUR | 99.6% | 42/52 | 6.0/8.0 |

## Diagnostics disponibles

| Produit | Alignement | Lecture simulation | Role | Reel moyen | Simulation moyenne | Ecart | Ecart % |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| 268091 | previous_day | Stock composant total valorise | direct | 259 678 EUR | 373 608 EUR | 113 929 EUR | 43.9% |
| 268091 | same_day | Stock composant total valorise | direct | 259 678 EUR | 376 701 EUR | 117 023 EUR | 45.1% |
| 268091 | previous_day | Diagnostic: excedent au-dessus couverture 90j | diagnostic | 259 678 EUR | 205 859 EUR | -53 819 EUR | -20.7% |
| 268091 | previous_day | Diagnostic: excedent au-dessus cible MRP | diagnostic | 259 678 EUR | 348 626 EUR | 88 947 EUR | 34.3% |
| 268091 | same_day | Diagnostic: excedent au-dessus couverture 90j | diagnostic | 259 678 EUR | 208 087 EUR | -51 591 EUR | -19.9% |
| 268091 | same_day | Diagnostic: excedent au-dessus cible MRP | diagnostic | 259 678 EUR | 351 830 EUR | 92 151 EUR | 35.5% |
| 268967 | previous_day | Stock composant total valorise | direct | 930 695 EUR | 1 801 345 EUR | 870 650 EUR | 93.5% |
| 268967 | same_day | Stock composant total valorise | direct | 930 695 EUR | 1 811 140 EUR | 880 445 EUR | 94.6% |
| 268967 | previous_day | Diagnostic: excedent au-dessus cible MRP | diagnostic | 930 695 EUR | 1 444 528 EUR | 513 833 EUR | 55.2% |
| 268967 | previous_day | Diagnostic: excedent au-dessus couverture 90j | diagnostic | 930 695 EUR | 1 536 594 EUR | 605 899 EUR | 65.1% |
| 268967 | same_day | Diagnostic: excedent au-dessus cible MRP | diagnostic | 930 695 EUR | 1 454 245 EUR | 523 550 EUR | 56.3% |
| 268967 | same_day | Diagnostic: excedent au-dessus couverture 90j | diagnostic | 930 695 EUR | 1 543 921 EUR | 613 226 EUR | 65.9% |

## Top composants expliquant le stock simule

### 268091

| Composant | Valeur moyenne | Part stock simule | Qte moyenne | Prix unitaire | Source prix |
| --- | ---: | ---: | ---: | ---: | --- |
| 002612 | 104 615 EUR | 28.0% | 83,027.4 | 1.26 | inventory_state_unit_value_basis |
| 338928 | 51 732 EUR | 13.8% | 366,086.6 | 0.14131 | inventory_state_unit_value_basis |
| 001757 | 49 651 EUR | 13.3% | 9,143.8 | 5.43 | inventory_state_unit_value_basis |
| 338929 | 38 587 EUR | 10.3% | 178,767.4 | 0.21585 | inventory_state_unit_value_basis |
| 007923 | 30 174 EUR | 8.1% | 15,086.9 | 2 | inventory_state_unit_value_basis |
| 001848 | 21 965 EUR | 5.9% | 7,600.3 | 2.89 | inventory_state_unit_value_basis |
| 001893 | 17 470 EUR | 4.7% | 3,765.0 | 4.64 | inventory_state_unit_value_basis |
| 049371 | 14 820 EUR | 4.0% | 1,011.6 | 14.65 | inventory_state_unit_value_basis |
| 055703 | 14 701 EUR | 3.9% | 422.7 | 34.775 | inventory_state_unit_value_basis |
| 426331 | 11 797 EUR | 3.2% | 23,409.1 | 0.50393 | inventory_state_unit_value_basis |

### 268967

| Composant | Valeur moyenne | Part stock simule | Qte moyenne | Prix unitaire | Source prix |
| --- | ---: | ---: | ---: | ---: | --- |
| 333362 | 998 041 EUR | 55.4% | 3,653,019.2 | 0.27321 | inventory_state_unit_value_basis |
| 038005 | 486 422 EUR | 27.0% | 106,438.1 | 4.57 | inventory_state_unit_value_basis |
| 042342 | 267 839 EUR | 14.9% | 121,193,962.4 | 0.00221 | inventory_state_unit_value_basis |
| 708073 | 32 057 EUR | 1.8% | 8,929.5 | 3.59 | inventory_state_unit_value_basis |
| 344135 | 12 403 EUR | 0.7% | 3,077,634.6 | 0.00403 | inventory_state_unit_value_basis |
| 734545 | 4 584 EUR | 0.3% | 10,748.6 | 0.42644 | inventory_state_unit_value_basis |

## Composants non valorises

Ces lignes sont dans le BOM mais n'ont pas de prix fiable exploitable dans le graphe. Elles peuvent creer un ecart de scope si la source finance les inclut.

| Produit | Noeud | Composant | Probleme |
| --- | --- | --- | --- |
| 268091 | M-1810 | 693055 | missing_or_fallback_unit_value |
| 268967 | M-1430 | 730384 | missing_or_fallback_unit_value |
| 268967 | M-1430 | 773474 | missing_or_fallback_unit_value |

## Sources

- 268091: `C:\dev\lca-simu\etudecas\data\source\Stock_Composants_Immobilisé_Pharma.csv`
- 268967: `C:\dev\lca-simu\etudecas\data\source\Stock_Composants_Immobilisé_Cos.csv`
