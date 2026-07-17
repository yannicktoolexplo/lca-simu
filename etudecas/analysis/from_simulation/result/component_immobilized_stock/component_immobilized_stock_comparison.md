# Stock composants immobilise - verification source vs simulation

- Run: `etudecas\simulation\result\_reruns\_codex_mrp_open_orders_targets_5y`
- Graphe: `etudecas\simulation_prep\result\reference_baseline\_mrp_bom_tests\bom_weekly_mps_lotified_no_static_fallback_physical_floor.json`
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
| 268091 | previous_day | 930 695 EUR | 1 423 062 EUR | 492 367 EUR | 52.9% | 495 690 EUR | 53.3% | 49/52 | 14.0/15.0 |
| 268967 | previous_day | 259 678 EUR | 1 038 815 EUR | 779 137 EUR | 300.0% | 779 137 EUR | 300.0% | 52/52 | 7.0/8.0 |

## Diagnostics disponibles

| Produit | Alignement | Lecture simulation | Role | Reel moyen | Simulation moyenne | Ecart | Ecart % |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| 268091 | previous_day | Stock composant valorise hors PFI/flux internes | direct | 930 695 EUR | 1 423 062 EUR | 492 367 EUR | 52.9% |
| 268091 | same_day | Stock composant valorise hors PFI/flux internes | direct | 930 695 EUR | 1 426 157 EUR | 495 462 EUR | 53.2% |
| 268091 | previous_day | Diagnostic: excedent au-dessus cible MRP, hors PFI/flux internes | diagnostic | 930 695 EUR | 610 717 EUR | -319 978 EUR | -34.4% |
| 268091 | previous_day | Diagnostic brut: excedent au-dessus cible MRP, PFI inclus si valorise | diagnostic | 930 695 EUR | 610 717 EUR | -319 978 EUR | -34.4% |
| 268091 | previous_day | Diagnostic: stock composant brut, PFI inclus si valorise | diagnostic | 930 695 EUR | 1 423 062 EUR | 492 367 EUR | 52.9% |
| 268091 | previous_day | Diagnostic: excedent au-dessus couverture 90j, hors PFI/flux internes | diagnostic | 930 695 EUR | 221 623 EUR | -709 072 EUR | -76.2% |
| 268091 | previous_day | Diagnostic brut: excedent au-dessus couverture 90j, PFI inclus si valorise | diagnostic | 930 695 EUR | 221 623 EUR | -709 072 EUR | -76.2% |
| 268091 | same_day | Diagnostic: excedent au-dessus cible MRP, hors PFI/flux internes | diagnostic | 930 695 EUR | 612 592 EUR | -318 103 EUR | -34.2% |
| 268091 | same_day | Diagnostic brut: excedent au-dessus cible MRP, PFI inclus si valorise | diagnostic | 930 695 EUR | 612 592 EUR | -318 103 EUR | -34.2% |
| 268091 | same_day | Diagnostic: stock composant brut, PFI inclus si valorise | diagnostic | 930 695 EUR | 1 426 157 EUR | 495 462 EUR | 53.2% |
| 268091 | same_day | Diagnostic: excedent au-dessus couverture 90j, hors PFI/flux internes | diagnostic | 930 695 EUR | 222 128 EUR | -708 567 EUR | -76.1% |
| 268091 | same_day | Diagnostic brut: excedent au-dessus couverture 90j, PFI inclus si valorise | diagnostic | 930 695 EUR | 222 128 EUR | -708 567 EUR | -76.1% |
| 268967 | previous_day | Stock composant valorise hors PFI/flux internes | direct | 259 678 EUR | 1 038 815 EUR | 779 137 EUR | 300.0% |
| 268967 | same_day | Stock composant valorise hors PFI/flux internes | direct | 259 678 EUR | 1 045 267 EUR | 785 588 EUR | 302.5% |
| 268967 | previous_day | Diagnostic: excedent au-dessus cible MRP, hors PFI/flux internes | diagnostic | 259 678 EUR | 359 916 EUR | 100 237 EUR | 38.6% |
| 268967 | previous_day | Diagnostic brut: excedent au-dessus cible MRP, PFI inclus si valorise | diagnostic | 259 678 EUR | 511 511 EUR | 251 833 EUR | 97.0% |
| 268967 | previous_day | Diagnostic: excedent au-dessus couverture 90j, hors PFI/flux internes | diagnostic | 259 678 EUR | 0 EUR | -259 678 EUR | -100.0% |
| 268967 | previous_day | Diagnostic brut: excedent au-dessus couverture 90j, PFI inclus si valorise | diagnostic | 259 678 EUR | 0 EUR | -259 678 EUR | -100.0% |
| 268967 | previous_day | Diagnostic: stock composant brut, PFI inclus si valorise | diagnostic | 259 678 EUR | 4 301 622 EUR | 4 041 944 EUR | 1556.5% |
| 268967 | same_day | Diagnostic: excedent au-dessus cible MRP, hors PFI/flux internes | diagnostic | 259 678 EUR | 365 404 EUR | 105 725 EUR | 40.7% |
| 268967 | same_day | Diagnostic: excedent au-dessus couverture 90j, hors PFI/flux internes | diagnostic | 259 678 EUR | 0 EUR | -259 678 EUR | -100.0% |
| 268967 | same_day | Diagnostic brut: excedent au-dessus couverture 90j, PFI inclus si valorise | diagnostic | 259 678 EUR | 0 EUR | -259 678 EUR | -100.0% |
| 268967 | same_day | Diagnostic brut: excedent au-dessus cible MRP, PFI inclus si valorise | diagnostic | 259 678 EUR | 521 278 EUR | 261 600 EUR | 100.7% |
| 268967 | same_day | Diagnostic: stock composant brut, PFI inclus si valorise | diagnostic | 259 678 EUR | 4 314 744 EUR | 4 055 066 EUR | 1561.6% |

## Top composants expliquant le stock simule

### 268091

| Composant | Valeur moyenne | Part stock simule | Qte moyenne | Prix unitaire | Source prix |
| --- | ---: | ---: | ---: | ---: | --- |
| 049371 | 274 600 EUR | 19.3% | 18,744.0 | 14.65 | inventory_state_unit_value_basis |
| 338929 | 255 038 EUR | 17.9% | 1,181,553.8 | 0.21585 | inventory_state_unit_value_basis |
| 002612 | 243 370 EUR | 17.1% | 193,150.4 | 1.26 | inventory_state_unit_value_basis |
| 338928 | 150 266 EUR | 10.6% | 1,063,381.3 | 0.14131 | inventory_state_unit_value_basis |
| 007923 | 143 416 EUR | 10.1% | 71,708.1 | 2 | inventory_state_unit_value_basis |
| 001893 | 111 450 EUR | 7.8% | 24,019.3 | 4.64 | inventory_state_unit_value_basis |
| 001757 | 81 089 EUR | 5.7% | 14,933.4 | 5.43 | inventory_state_unit_value_basis |
| 001848 | 42 604 EUR | 3.0% | 14,741.8 | 2.89 | inventory_state_unit_value_basis |
| 099439 | 40 731 EUR | 2.9% | 4,441.8 | 9.17 | inventory_state_unit_value_basis |
| 055703 | 28 394 EUR | 2.0% | 816.5 | 34.775 | inventory_state_unit_value_basis |

### 268967

| Composant | Valeur moyenne | Part stock simule | Qte moyenne | Prix unitaire | Source prix |
| --- | ---: | ---: | ---: | ---: | --- |
| 038005 | 480 122 EUR | 46.2% | 105,059.5 | 4.57 | inventory_state_unit_value_basis |
| 042342 | 257 333 EUR | 24.8% | 116,440,405.3 | 0.00221 | inventory_state_unit_value_basis |
| 333362 | 244 920 EUR | 23.6% | 896,453.8 | 0.27321 | inventory_state_unit_value_basis |
| 708073 | 45 693 EUR | 4.4% | 12,727.9 | 3.59 | inventory_state_unit_value_basis |
| 734545 | 6 278 EUR | 0.6% | 14,722.2 | 0.42644 | inventory_state_unit_value_basis |
| 344135 | 4 469 EUR | 0.4% | 1,108,857.7 | 0.00403 | inventory_state_unit_value_basis |

## Flux des composants principaux

Lecture: si les arrivees et commandes generees depassent la consommation approximative, le surplus vient de la politique MRP/lotification ou des commandes ouvertes, pas du stock J0 seul.

### 268091

| Composant | Stock debut | Arrivees | Conso approx. | Stock fin | Commandes totales | Ouvertes | Generees MRP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 049371 | 4,138.9 | 32,600.0 | 23,946.3 | 12,792.7 | 32,600.0 | 19,800.0 | 12,800.0 |
| 338929 | 354,000.0 | 16,547,600.0 | 15,940,800.0 | 960,800.0 | 17,622,600.0 | 57,600.0 | 17,565,000.0 |
| 002612 | 153,521.6 | 45,000.0 | 32,359.8 | 166,161.8 | 45,000.0 | 45,000.0 | 0.0 |
| 338928 | 404,065.0 | 16,665,033.0 | 15,940,800.0 | 1,128,298.0 | 17,590,033.0 | 365,033.0 | 17,225,000.0 |
| 007923 | 55,019.0 | 19,140.0 | 51,775.7 | 22,383.3 | 19,140.0 | 19,140.0 | 0.0 |
| 001893 | 9,783.5 | 143,520.0 | 122,967.3 | 30,336.2 | 143,520.0 | 0.0 | 143,520.0 |
| 001757 | 8,499.7 | 22,300.0 | 25,887.9 | 4,911.8 | 24,000.0 | 8,000.0 | 16,000.0 |
| 001848 | 10,262.6 | 14,000.0 | 19,415.9 | 4,846.8 | 18,000.0 | 6,000.0 | 12,000.0 |
| 099439 | 4,972.6 | 29,400.0 | 32,359.8 | 2,012.8 | 33,600.0 | 0.0 | 33,600.0 |
| 055703 | 569.8 | 1,200.0 | 1,294.4 | 475.4 | 1,500.0 | 300.0 | 1,200.0 |

### 268967

| Composant | Stock debut | Arrivees | Conso approx. | Stock fin | Commandes totales | Ouvertes | Generees MRP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 038005 | 37,598.5 | 140,000.0 | 122,616.7 | 54,981.8 | 140,000.0 | 90,000.0 | 50,000.0 |
| 042342 | 78,749,996.0 | 420,000,000.0 | 422,816,394.0 | 75,933,602.0 | 420,000,000.0 | 60,000,000.0 | 360,000,000.0 |
| 333362 | 142,250.0 | 7,954,000.0 | 7,007,000.0 | 1,089,250.0 | 8,409,000.0 | 629,000.0 | 7,780,000.0 |
| 708073 | 10,326.9 | 60,000.0 | 55,565.5 | 14,761.4 | 60,000.0 | 0.0 | 60,000.0 |
| 734545 | 1,641.0 | 69,400.0 | 56,056.0 | 14,985.0 | 69,400.0 | 6,400.0 | 63,000.0 |
| 344135 | 0.0 | 8,400,000.0 | 7,007,000.0 | 1,393,000.0 | 8,640,000.0 | 0.0 | 8,640,000.0 |

## Composants non valorises

Ces lignes sont dans le BOM mais n'ont pas de prix fiable exploitable dans le graphe. Elles peuvent creer un ecart de scope si la source finance les inclut.

| Produit | Noeud | Composant | Probleme |
| --- | --- | --- | --- |
| 268091 | M-1810 | 693055 | missing_or_fallback_unit_value |
| 268967 | M-1430 | 730384 | missing_or_fallback_unit_value |

## Sources

- 268091: `C:\dev\lca-simu\etudecas\data\source\Stock_Composants_Immobilisé_Cos.csv`
- 268967: `C:\dev\lca-simu\etudecas\data\source\Stock_Composants_Immobilisé_Pharma.csv`
