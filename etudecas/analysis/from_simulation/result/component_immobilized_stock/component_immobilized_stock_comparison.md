# Stock composants immobilise - verification source vs simulation

- Run: `etudecas\simulation\result\_experiments\stock_target_268091_source_truth\5y\source_truth_wip_pipeline_v2`
- Graphe: non fourni
- Produits compares: 268091, 268967

## Contrat de comparaison

- Source de verite: fichiers de `etudecas/data/source`.
- Les CSV source exposent `Sum_Valeur totale du stock`: on compare donc le stock composant physique valorise simule.
- Les PFI et flux internes ne sont pas valorises dans la ligne principale; une ligne brute reste disponible en diagnostic si un roll-up interne existe.
- Les commandes ouvertes ne sont pas ajoutees au stock tant qu'elles ne sont pas receptionnees.
- Les diagnostics de surstock (`90j`, `cible MRP`) servent a expliquer, pas a calibrer directement.
- L'alignement `previous_day` est prioritaire car les photos DMP sont vers 00:06 et la simulation stocke des fins de jour.
- Convention produit utilisee ici: `268091 -> Cos`, `268967 -> Pharma`; les workbooks source ont des libelles ambigus, donc ce mapping reste explicite.

## Resultat principal

| Produit | Alignement | Reel moyen | Simulation moyenne aux photos | Ecart | Ecart % | MAE | MAE % | Sim > reel | Composants valorises |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 268091 | previous_day | 930 695 EUR | 1 065 467 EUR | 134 771 EUR | 14.5% | 194 554 EUR | 20.9% | 44/52 | 14.0/15.0 |
| 268967 | previous_day | 259 678 EUR | 960 771 EUR | 701 093 EUR | 270.0% | 701 093 EUR | 270.0% | 52/52 | 7.0/8.0 |

## Diagnostics disponibles

| Produit | Alignement | Lecture simulation | Role | Reel moyen | Simulation moyenne | Ecart | Ecart % |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| 268091 | previous_day | Stock composant valorise hors PFI/flux internes | direct | 930 695 EUR | 1 065 467 EUR | 134 771 EUR | 14.5% |
| 268091 | same_day | Stock composant valorise hors PFI/flux internes | direct | 930 695 EUR | 1 067 105 EUR | 136 409 EUR | 14.7% |
| 268091 | previous_day | Diagnostic: excedent au-dessus cible MRP | diagnostic | 930 695 EUR | 1 000 995 EUR | 70 300 EUR | 7.6% |
| 268091 | previous_day | Diagnostic: excedent au-dessus couverture 90j | diagnostic | 930 695 EUR | 824 945 EUR | -105 750 EUR | -11.4% |
| 268091 | previous_day | Diagnostic: stock composant brut, PFI inclus si valorise | diagnostic | 930 695 EUR | 1 065 467 EUR | 134 771 EUR | 14.5% |
| 268091 | same_day | Diagnostic: excedent au-dessus cible MRP | diagnostic | 930 695 EUR | 1 002 313 EUR | 71 618 EUR | 7.7% |
| 268091 | same_day | Diagnostic: excedent au-dessus couverture 90j | diagnostic | 930 695 EUR | 826 276 EUR | -104 419 EUR | -11.2% |
| 268091 | same_day | Diagnostic: stock composant brut, PFI inclus si valorise | diagnostic | 930 695 EUR | 1 067 105 EUR | 136 409 EUR | 14.7% |
| 268967 | previous_day | Stock composant valorise hors PFI/flux internes | direct | 259 678 EUR | 960 771 EUR | 701 093 EUR | 270.0% |
| 268967 | same_day | Stock composant valorise hors PFI/flux internes | direct | 259 678 EUR | 966 894 EUR | 707 216 EUR | 272.3% |
| 268967 | previous_day | Diagnostic: excedent au-dessus cible MRP | diagnostic | 259 678 EUR | 1 735 279 EUR | 1 475 601 EUR | 568.2% |
| 268967 | previous_day | Diagnostic: excedent au-dessus couverture 90j | diagnostic | 259 678 EUR | 2 172 119 EUR | 1 912 441 EUR | 736.5% |
| 268967 | previous_day | Diagnostic: stock composant brut, PFI inclus si valorise | diagnostic | 259 678 EUR | 3 158 456 EUR | 2 898 778 EUR | 1116.3% |
| 268967 | same_day | Diagnostic: excedent au-dessus cible MRP | diagnostic | 259 678 EUR | 1 743 232 EUR | 1 483 554 EUR | 571.3% |
| 268967 | same_day | Diagnostic: excedent au-dessus couverture 90j | diagnostic | 259 678 EUR | 2 177 959 EUR | 1 918 281 EUR | 738.7% |
| 268967 | same_day | Diagnostic: stock composant brut, PFI inclus si valorise | diagnostic | 259 678 EUR | 3 168 969 EUR | 2 909 290 EUR | 1120.3% |

## Top composants expliquant le stock simule

### 268091

| Composant | Valeur moyenne | Part stock simule | Qte moyenne | Prix unitaire | Source prix |
| --- | ---: | ---: | ---: | ---: | --- |
| 049371 | 276 447 EUR | 25.9% | 18,870.1 | 14.65 | inventory_state_unit_value_basis |
| 002612 | 243 584 EUR | 22.9% | 193,320.8 | 1.26 | inventory_state_unit_value_basis |
| 007923 | 143 961 EUR | 13.5% | 71,980.7 | 2 | inventory_state_unit_value_basis |
| 001757 | 81 829 EUR | 7.7% | 15,069.7 | 5.43 | inventory_state_unit_value_basis |
| 338928 | 75 983 EUR | 7.1% | 537,704.4 | 0.14131 | inventory_state_unit_value_basis |
| 338929 | 45 642 EUR | 4.3% | 211,453.8 | 0.21585 | inventory_state_unit_value_basis |
| 001848 | 42 899 EUR | 4.0% | 14,844.1 | 2.89 | inventory_state_unit_value_basis |
| 099439 | 41 553 EUR | 3.9% | 4,531.4 | 9.17 | inventory_state_unit_value_basis |
| 001893 | 37 616 EUR | 3.5% | 8,106.8 | 4.64 | inventory_state_unit_value_basis |
| 055703 | 28 631 EUR | 2.7% | 823.3 | 34.775 | inventory_state_unit_value_basis |

### 268967

| Composant | Valeur moyenne | Part stock simule | Qte moyenne | Prix unitaire | Source prix |
| --- | ---: | ---: | ---: | ---: | --- |
| 038005 | 477 138 EUR | 49.7% | 104,406.5 | 4.57 | inventory_state_unit_value_basis |
| 042342 | 252 357 EUR | 26.3% | 114,188,720.4 | 0.00221 | inventory_state_unit_value_basis |
| 333362 | 186 309 EUR | 19.4% | 681,926.9 | 0.27321 | inventory_state_unit_value_basis |
| 708073 | 37 037 EUR | 3.9% | 10,316.6 | 3.59 | inventory_state_unit_value_basis |
| 734545 | 4 756 EUR | 0.5% | 11,152.6 | 0.42644 | inventory_state_unit_value_basis |
| 344135 | 3 174 EUR | 0.3% | 787,696.2 | 0.00403 | inventory_state_unit_value_basis |

## Flux des composants principaux

Lecture: si les arrivees et commandes generees depassent la consommation approximative, le surplus vient de la politique MRP/lotification ou des commandes ouvertes, pas du stock J0 seul.

### 268091

| Composant | Stock debut | Arrivees | Conso approx. | Stock fin | Commandes totales | Ouvertes | Generees MRP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 049371 | 4,138.9 | 19,800.0 | 5,887.3 | 18,051.7 | 19,800.0 | 19,800.0 | 0.0 |
| 002612 | 153,521.6 | 45,000.0 | 7,955.8 | 190,565.9 | 45,000.0 | 45,000.0 | 0.0 |
| 007923 | 55,019.0 | 19,140.0 | 12,729.2 | 61,429.7 | 19,140.0 | 19,140.0 | 0.0 |
| 001757 | 8,499.7 | 8,000.0 | 6,364.6 | 10,135.0 | 8,000.0 | 8,000.0 | 0.0 |
| 338928 | 404,065.0 | 3,515,033.0 | 3,919,098.0 | 0.0 | 3,790,033.0 | 365,033.0 | 3,425,000.0 |
| 338929 | 354,000.0 | 3,577,600.0 | 3,919,098.0 | 12,502.0 | 3,832,600.0 | 57,600.0 | 3,775,000.0 |
| 001848 | 10,262.6 | 6,000.0 | 4,773.5 | 11,489.2 | 6,000.0 | 6,000.0 | 0.0 |
| 099439 | 4,972.6 | 4,200.0 | 7,955.8 | 1,216.8 | 4,200.0 | 0.0 | 4,200.0 |
| 001893 | 9,783.5 | 23,920.0 | 30,231.9 | 3,471.6 | 23,920.0 | 0.0 | 23,920.0 |
| 055703 | 569.8 | 300.0 | 318.2 | 551.6 | 300.0 | 300.0 | 0.0 |

### 268967

| Composant | Stock debut | Arrivees | Conso approx. | Stock fin | Commandes totales | Ouvertes | Generees MRP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 038005 | 37,598.5 | 120,000.0 | 122,616.7 | 34,981.8 | 130,000.0 | 90,000.0 | 40,000.0 |
| 042342 | 78,749,996.0 | 390,000,000.0 | 422,816,394.0 | 45,933,602.0 | 390,000,000.0 | 60,000,000.0 | 330,000,000.0 |
| 333362 | 142,250.0 | 7,729,000.0 | 7,007,000.0 | 864,250.0 | 7,944,000.0 | 629,000.0 | 7,315,000.0 |
| 708073 | 10,326.9 | 55,000.0 | 55,565.5 | 9,761.4 | 55,000.0 | 0.0 | 55,000.0 |
| 734545 | 1,641.0 | 63,100.0 | 56,056.0 | 8,685.0 | 63,100.0 | 6,400.0 | 56,700.0 |
| 344135 | 0.0 | 8,040,000.0 | 7,007,000.0 | 1,033,000.0 | 8,160,000.0 | 0.0 | 8,160,000.0 |


## Sources

- 268091: `C:\dev\lca-simu\etudecas\data\source\Stock_Composants_Immobilisé_Cos.csv`
- 268967: `C:\dev\lca-simu\etudecas\data\source\Stock_Composants_Immobilisé_Pharma.csv`
