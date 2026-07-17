# Cause racine - stock composants 268091

## Conclusion courte

- Le KPI reel Cos vaut en moyenne 930 695 EUR sur 52 photos 2025.
- La simulation comparee en stock composant physique vaut 1 065 467 EUR, soit un ecart de 134 771 EUR.
- Les 3 composants `049371`, `002612`, `007923` portent deja 663 993 EUR de stock simule moyen, donc plus que le KPI reel complet.
- Les O.Proc ne sont pas la cause principale: ils sont traites comme encours deja engages, pas comme une nouvelle consommation de stock libre.
- La cause la plus probable est un ecart de perimetre: la simulation valorise le stock physique MRP des composants du BOM, alors que le CSV reel est un KPI agrege d'immobilise sans detail article/statut.

## Verification O.Proc

- Lignes composant O.Proc tracees: 300.
- Consommation de stock libre a J0: 0.0.
- Composants consideres deja engages en WIP initial: 4 741 738.2.
- Manque O.Proc: 0.0.
- Ordres de fabrication source: 20 lignes.

## Stock J0 selon plusieurs lectures

| Lecture simulation J0 | Stock physique | Stock utile | Excedent / immobilise calcule |
| --- | ---: | ---: | ---: |
| coverage | 720 013 EUR | 48 119 EUR | 671 894 EUR |
| demand_180d | 720 013 EUR | 376 180 EUR | 343 833 EUR |
| demand_90d | 720 013 EUR | 282 652 EUR | 437 362 EUR |
| max_safety_coverage | 720 013 EUR | 82 935 EUR | 637 078 EUR |
| safety_plus_coverage | 720 013 EUR | 61 128 EUR | 658 885 EUR |
| target_stock | 720 013 EUR | 84 134 EUR | 635 879 EUR |

## Top composants expliquant l'ecart

| Item | Valeur moyenne simulee | Part | Stock debut | Commandes ouvertes | Consommation approx. | MRP genere | Lecture |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 049371 | 276 447 EUR | 25.9% | 60 635 EUR | 290 070 EUR | 86 248 EUR | 0.0 | stock source + commandes ouvertes |
| 002612 | 243 584 EUR | 22.9% | 193 437 EUR | 56 700 EUR | 10 024 EUR | 0.0 | stock source + commandes ouvertes |
| 007923 | 143 961 EUR | 13.5% | 110 038 EUR | 38 280 EUR | 25 458 EUR | 0.0 | stock source + commandes ouvertes |
| 001757 | 81 829 EUR | 7.7% | 46 153 EUR | 43 440 EUR | 34 560 EUR | 0.0 | stock source + commandes ouvertes |
| 338928 | 75 983 EUR | 7.1% | 57 098 EUR | 51 583 EUR | 553 808 EUR | 3 425 000.0 | stock source + MRP |
| 338929 | 45 642 EUR | 4.3% | 76 411 EUR | 12 433 EUR | 845 937 EUR | 3 775 000.0 | stock source + MRP |
| 001848 | 42 899 EUR | 4.0% | 29 659 EUR | 17 340 EUR | 13 795 EUR | 0.0 | stock source + commandes ouvertes |
| 099439 | 41 553 EUR | 3.9% | 45 599 EUR | 0 EUR | 72 954 EUR | 4 200.0 | stock source + MRP |
| 001893 | 37 616 EUR | 3.5% | 45 395 EUR | 0 EUR | 140 276 EUR | 23 920.0 | stock source + MRP |
| 055703 | 28 631 EUR | 2.7% | 19 815 EUR | 10 432 EUR | 11 066 EUR | 0.0 | stock source + commandes ouvertes |

## Commandes ouvertes achat principales

| Item | Lignes | Fournisseurs source | Quantite source | Jours reception |
| --- | ---: | --- | ---: | --- |
| 338928 | 3 | VD0901566A | 365 033.0 | J16 -> J16 |
| 338929 | 1 | VD0914360C | 57 600.0 | J14 -> J14 |
| 002612 | 2 | VD0910216A | 45 000.0 | J29 -> J47 |
| 049371 | 11 | VD0518550B | 19 800 000.0 | J26 -> J153 |
| 426331 | 1 | VD0989480A | 19 200.0 | J29 -> J29 |
| 007923 | 1 | VD0956464A | 19 140 000.0 | J30 -> J30 |
| 001757 | 3 | VD0951020A | 8 000 000.0 | J28 -> J82 |
| 001848 | 1 | VD0951020A | 6 000 000.0 | J69 -> J69 |
| 055703 | 1 | VD0914320A | 300 000.0 | J35 -> J35 |

## Ordres de fabrication en cours source

Ces lignes sont des PF `268091` deja lances au cut-over. Elles entrent comme PF aux dates source; leurs composants ne sont pas retires une deuxieme fois du stock libre.

| Source row | Quantite PF | Date livraison | Date entree stock | Jour entree |
| ---: | ---: | --- | --- | ---: |
| 75 | 139 660.0 | 2025-01-10 | 2025-01-24 | J23 |
| 72 | 20 795.0 | 2025-01-22 | 2025-02-05 | J35 |
| 82 | 77 520.0 | 2025-01-22 | 2025-02-05 | J35 |
| 80 | 16 800.0 | 2025-01-29 | 2025-02-12 | J42 |
| 78 | 141 795.0 | 2025-01-30 | 2025-02-13 | J43 |
| 89 | 126 795.0 | 2025-02-11 | 2025-02-25 | J55 |
| 88 | 11 300.0 | 2025-02-17 | 2025-03-03 | J61 |
| 90 | 141 800.0 | 2025-02-19 | 2025-03-05 | J63 |
| 77 | 141 795.0 | 2025-02-20 | 2025-03-06 | J64 |
| 81 | 60 695.0 | 2025-03-04 | 2025-03-18 | J76 |
| 79 | 141 795.0 | 2025-03-21 | 2025-04-04 | J93 |
| 85 | 9 800.0 | 2025-03-24 | 2025-04-07 | J96 |
| ... | 8 autres lignes | ... | ... | ... |

## Ecarts source / FIA visibles

Ces points ne suffisent pas seuls a expliquer tout l'ecart, mais ils montrent que le carnet d'ordres et les voies fournisseur du BOM ne sont pas toujours le meme objet.

| Item | Fournisseurs commandes ouvertes | Fournisseurs FIA 268091 | Lecture |
| --- | --- | --- | --- |
| 049371 | VD0518550B | VD0520132A | fournisseur du carnet absent de la FIA |
| 002612 | VD0910216A | VD0500655A, VD0910216A, VD0990780A, VD1091642A | coherent |
| 007923 | VD0956464A | aucun | commande ouverte sans voie FIA dans le workbook |
| 001757 | VD0951020A | VD0951020A | coherent |
| 338928 | VD0901566A | VD0901566A | coherent |
| 338929 | VD0914360C | VD0914360C | coherent |
| 001848 | VD0951020A | VD0519670A, VD0951020A | coherent |
| 099439 | aucun | VD0505677A | voie FIA sans commande ouverte source |
| 001893 | aucun | VD0518684A, VD0910216A, VD1091642A | voie FIA sans commande ouverte source |
| 055703 | VD0914320A | VD0914320A, VD0964290A | coherent |

## Decision metier

Pour coller au KPI reel, il ne faut pas calibrer brutalement le stock physique. Il faut d'abord choisir la meme definition que la source finance:

1. stock physique composant site: tout ce qui est dans `Stocks_MRP.xlsx`;
2. stock attribuable au produit 268091: part du stock composant reservee ou statistiquement allouee a ce PF;
3. stock immobilise finance: sous-ensemble du stock juge excedentaire/bloque/non utile selon une regle metier.

Le fichier reel actuel ne contient que date + valeur. Sans detail article/statut, on ne peut pas verifier si `049371`, `002612` ou `007923` sont inclus dans le KPI reel.
