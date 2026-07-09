# Inference regle stock immobilise - 268091

## Conclusion

- La regle qui colle le mieux aux photos reelles n'est pas le stock physique total. Le stock physique simule moyen reste au-dessus du reel, mais dans le meme ordre de grandeur.
- Stock physique composants simule: 1 065 467 EUR vs reel 930 695 EUR, soit x1.1.
- Excedent au-dessus cible MRP: 1 000 995 EUR, encore x1.1.
- Meilleur exces teste: `physical_minus_future_need_270d_eur` -> 875 243 EUR, MAE 92 673 EUR.
- Meilleur stock utile teste: `useful_for_future_need_730d_eur` -> 300 078 EUR, MAE 630 617 EUR.
- Meilleure regle avec facteur de perimetre: `physical_minus_future_need_365d_eur` x 1.11 -> MAE 94 718 EUR.
- Controle temporel premiere semaine: stock composant source 01/01 726 887 EUR; stock simule fin J5 720 013 EUR; premiere photo reelle 06/01 656 922 EUR.

Lecture metier: avec les donnees disponibles, le KPI reel Cos ne ressemble ni a tout le stock physique, ni a un simple excedent au-dessus du delai fournisseur + delai securite. Il ressemble davantage a un sous-ensemble finance/statut du stock, ou a un stock utile limite a un horizon court. Le CSV reel etant agrege, la vraie regle SAP/finance ne peut pas etre prouvee sans detail article/statut/lot.

Point important sur l'hypothese `besoin pendant delai previsionnel + delai de securite`: elle ne donne que 51 798 EUR en moyenne si on ne garde que le stock utile pendant cet horizon. Elle est donc trop basse pour expliquer directement le KPI reel observe.
Point sur le delai de securite seul: la couverture des delais de securite composants vaut 77 034 EUR en moyenne, alors que le reel vaut 930 695 EUR. Le stock au-dessus de cette couverture vaut 996 958 EUR, donc trop haut.

## Meilleures regles candidates composants

| Rang | Regle | Reel moyen | Simulation moyenne | Ratio sim/reel | MAE | Correlation |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `physical_minus_future_need_270d_eur` | 930 695 EUR | 875 243 EUR | 0.94 | 92 673 EUR | 0.61 |
| 2 | `physical_minus_future_need_365d_eur` | 930 695 EUR | 839 292 EUR | 0.90 | 103 269 EUR | 0.65 |
| 3 | `physical_minus_future_need_180d_eur` | 930 695 EUR | 937 286 EUR | 1.01 | 105 155 EUR | 0.41 |
| 4 | `physical_minus_future_need_540d_eur` | 930 695 EUR | 799 981 EUR | 0.86 | 133 731 EUR | 0.66 |
| 5 | `physical_minus_future_need_120d_eur` | 930 695 EUR | 981 358 EUR | 1.05 | 136 305 EUR | 0.36 |
| 6 | `mrp_target_excess_eur` | 930 695 EUR | 1 000 995 EUR | 1.08 | 153 006 EUR | 0.40 |
| 7 | `physical_minus_future_need_90d_eur` | 930 695 EUR | 1 002 167 EUR | 1.08 | 153 189 EUR | 0.35 |
| 8 | `physical_minus_future_need_lead_plus_safety_eur` | 930 695 EUR | 1 013 669 EUR | 1.09 | 162 069 EUR | 0.36 |
| 9 | `physical_minus_future_need_730d_eur` | 930 695 EUR | 765 388 EUR | 0.82 | 165 962 EUR | 0.67 |
| 10 | `physical_minus_future_need_60d_eur` | 930 695 EUR | 1 022 837 EUR | 1.10 | 169 067 EUR | 0.37 |
| 11 | `physical_minus_future_need_lead_only_eur` | 930 695 EUR | 1 023 173 EUR | 1.10 | 169 234 EUR | 0.37 |
| 12 | `physical_minus_future_need_45d_eur` | 930 695 EUR | 1 033 435 EUR | 1.11 | 176 620 EUR | 0.37 |

## Controle temporel premiere semaine

Cette section corrige un point de lecture important: le stock MRP est photographie le 01/01, alors que le premier KPI reel immobilise est photographie le lundi 06/01 vers 00:06. Si J0 = 01/01, la photo est surtout comparable a la fin de J4; J5 n'a quasiment pas commence.

| Lecture | Valeur / quantite |
| --- | ---: |
| Stock composant source 01/01 | 726 887 EUR |
| Stock composant simule fin J0 | 720 013 EUR |
| Stock composant simule fin J5, juste avant photo 06/01 | 720 013 EUR |
| KPI reel composants immobilises 06/01 | 656 922 EUR |
| Production simulee J0-J5 | 14 400 PF |
| Valeur BOM consommee par cette production | 6 781 EUR |
| Demande source semaine 1  ligne Excel | 13 300 PF |
| Demande source uniformisee | 1 900 PF/j |
| Demande source proratee J0-J4 avant photo 06/01 | 9 500 PF |
| Demande service simulee lissee J0-J4 | 14 075 PF |
| Demande service simulee lissee J0-J5 | 18 263 PF |
| Demande service simulee lissee J0-J6 | 22 908 PF |
| Servi simule J0-J4 | 14 075 PF |
| Backlog simule fin J4 | 0 PF |
| Valeur BOM equivalente demande source J0-J4 | 4 473 EUR |
| Valeur BOM equivalente demande simulee lissee J0-J4 | 6 628 EUR |

Conclusion temporelle: la premiere semaine existe bien, mais il faut distinguer la ligne hebdo source et la demande lissee utilisee par le simulateur. Meme avec la demande lissee J0-J4, la consommation BOM reste de quelques milliers d'euros; elle ne peut pas expliquer seule le passage de 727 kEUR a 221 kEUR. L'ecart pointe donc surtout vers une difference de definition du KPI immobilise ou de perimetre/statut du stock, pas seulement vers un decalage de date.

## Lecture par delai de securite composants

Cette lecture teste explicitement si le KPI reel peut correspondre a la couverture des delais de securite MRP composants.

| Lecture | Reel moyen | Simulation moyenne | Ratio sim/reel | MAE |
| --- | ---: | ---: | ---: | ---: |
| `excess_above_effective_reference_eur` | 930 695 EUR | 990 018 EUR | 1.06 | 139 531 EUR |
| `excess_above_safety_delay_eur` | 930 695 EUR | 996 958 EUR | 1.07 | 143 993 EUR |
| `stock_value_eur` | 930 695 EUR | 1 065 467 EUR | 1.14 | 194 554 EUR |
| `effective_reference_value_eur` | 930 695 EUR | 84 767 EUR | 0.09 | 845 928 EUR |
| `safety_delay_value_eur` | 930 695 EUR | 77 034 EUR | 0.08 | 853 661 EUR |

Conclusion: le delai de securite composant seul est trop faible pour expliquer le stock immobilise reel; l'excedent au-dessus du delai de securite est trop eleve. Le KPI reel semble donc filtrer une partie du stock excedentaire, plutot que prendre toute la couverture de securite ou tout le surplus.

| Composant | Delai securite | Besoin moyen/j | Stock equiv. securite | Stock physique moyen | Couverture securite | Excedent au-dessus securite |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 049371 | 40 j | 20.2 | 807.0 | 276 447 EUR | 11 822 EUR | 264 625 EUR |
| 002612 | 20 j | 27.3 | 545.2 | 243 584 EUR | 687 EUR | 242 897 EUR |
| 007923 | 15 j | 43.6 | 654.3 | 143 961 EUR | 1 309 EUR | 142 653 EUR |
| 001757 | 20 j | 21.8 | 436.2 | 81 829 EUR | 2 369 EUR | 79 460 EUR |
| 338928 | 10 j | 13 429.5 | 134 294.8 | 75 983 EUR | 18 977 EUR | 57 006 EUR |
| 338929 | 10 j | 13 429.5 | 134 294.8 | 45 642 EUR | 28 988 EUR | 25 181 EUR |
| 001848 | 20 j | 16.4 | 327.1 | 42 899 EUR | 945 EUR | 41 954 EUR |
| 099439 | 7 j | 27.3 | 190.8 | 41 553 EUR | 1 750 EUR | 39 803 EUR |
| 001893 | 15 j | 103.6 | 1 553.9 | 37 616 EUR | 7 210 EUR | 30 405 EUR |
| 055703 | 30 j | 1.1 | 32.7 | 28 631 EUR | 1 138 EUR | 27 493 EUR |

## Regles candidates avec facteur de perimetre

Lecture: ce test repond a la question `la source reelle couvre-t-elle une fraction stable de cette famille de stock ?`.

| Rang | Regle | Facteur | Simulation calibree | MAE calibree | Correlation brute |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `physical_minus_future_need_365d_eur` | 1.11 | 928 529 EUR | 94 718 EUR | 0.65 |
| 2 | `physical_minus_future_need_270d_eur` | 1.06 | 930 422 EUR | 97 352 EUR | 0.61 |
| 3 | `physical_minus_future_need_540d_eur` | 1.16 | 926 592 EUR | 97 767 EUR | 0.66 |
| 4 | `physical_minus_future_need_730d_eur` | 1.21 | 925 060 EUR | 98 155 EUR | 0.67 |
| 5 | `physical_minus_future_need_180d_eur` | 0.99 | 930 481 EUR | 103 028 EUR | 0.41 |
| 6 | `physical_stock_value_eur` | 0.87 | 926 852 EUR | 109 754 EUR | 0.41 |
| 7 | `physical_minus_future_need_7d_eur` | 0.87 | 926 597 EUR | 110 133 EUR | 0.41 |
| 8 | `physical_minus_future_need_120d_eur` | 0.95 | 928 239 EUR | 110 378 EUR | 0.36 |
| 9 | `physical_minus_future_need_21d_eur` | 0.88 | 926 191 EUR | 110 499 EUR | 0.40 |
| 10 | `physical_minus_future_need_safety_only_eur` | 0.88 | 926 364 EUR | 110 601 EUR | 0.40 |
| 11 | `physical_minus_future_need_14d_eur` | 0.88 | 926 343 EUR | 110 769 EUR | 0.40 |
| 12 | `physical_minus_future_need_45d_eur` | 0.90 | 925 579 EUR | 111 241 EUR | 0.37 |

## Composants qui portent le stock physique simule

| Composant | Valeur physique moyenne | Excedent MRP moyen | Qte moyenne | Prix unitaire |
| --- | ---: | ---: | ---: | ---: |
| 049371 | 276 447 EUR | 262 726 EUR | 18 870.1 | 14.65 |
| 002612 | 243 584 EUR | 242 977 EUR | 193 320.8 | 1.26 |
| 007923 | 143 961 EUR | 142 797 EUR | 71 980.7 | 2 |
| 001757 | 81 829 EUR | 79 726 EUR | 15 069.7 | 5.43 |
| 338928 | 75 983 EUR | 58 957 EUR | 537 704.4 | 0.1413 |
| 338929 | 45 642 EUR | 29 572 EUR | 211 453.8 | 0.2158 |
| 001848 | 42 899 EUR | 42 063 EUR | 14 844.1 | 2.89 |
| 099439 | 41 553 EUR | 39 568 EUR | 4 531.4 | 9.17 |

## Delais source sur les principaux composants

| Composant | Lead FIA median | Lead min-max | Delai securite MRP | Valeur physique moyenne |
| --- | ---: | ---: | ---: | ---: |
| 049371 | 147 j | 147-147 j | 40 j | 276 447 EUR |
| 002612 | 35 j | 28-35 j | 20 j | 243 584 EUR |
| 007923 | 0 j | 0-0 j | 15 j | 143 961 EUR |
| 001757 | 84 j | 84-84 j | 20 j | 81 829 EUR |
| 338928 | 70 j | 70-70 j | 10 j | 75 983 EUR |
| 338929 | 42 j | 42-42 j | 10 j | 45 642 EUR |
| 001848 | 38 j | 21-56 j | 20 j | 42 899 EUR |
| 099439 | 35 j | 35-35 j | 7 j | 41 553 EUR |

## Produit fini 268091

Pour le PF, le CSV reel donne une valeur mais pas la quantite. J'ai donc compare la valeur reelle au stock PF simule en usine + DC via un cout unitaire implicite median.

| Lecture PF | Reel moyen | Simulation moyenne | MAE | Cout unitaire implicite median | Stabilite cout implicite |
| --- | ---: | ---: | ---: | ---: | ---: |
| stock PF physique x cout implicite | 402 762 EUR | 323 117 EUR | 250 388 EUR | 0.9430 EUR/UN | CV 425.3% |

Si ce cout implicite est stable, le stock PF immobilise est probablement une valorisation simple du stock PF physique. S'il varie fortement, le KPI PF applique aussi une regle d'immobilisation ou de valorisation que nous n'avons pas dans les CSV.

## Ce qu'il manque pour conclure sans ambiguite

- Detail du `Stock_Composants_Immobilise_Cos.csv` par article, magasin/statut, lot, age et prix.
- Quantite projetee disponible PF, pas seulement le compteur de semaines de rupture du fichier `Dispo_PF_Projete.csv`.
- Regle finance/SAP exacte: stock libre seulement, stock qualite/bloque, stock lent, stock au-dessus couverture, ou autre filtre.

## Sorties generees

- `component_rule_metrics.csv`
- `component_rule_snapshot_comparison.csv`
- `component_rule_snapshot_by_component.csv`
- `pf_rule_metrics.csv`
- `pf_rule_snapshot_comparison.csv`
- `component_safety_delay_summary.csv`
- `component_safety_delay_snapshot_comparison.csv`
- `component_safety_delay_metrics.csv`
