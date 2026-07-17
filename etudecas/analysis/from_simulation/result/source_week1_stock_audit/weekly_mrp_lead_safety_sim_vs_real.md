# Comparaison hebdomadaire stock composants immobilise

Regle estimee: composant par composant, stock immobilise = max(stock physique - besoin sur lead fournisseur + delai securite - stock de securite, 0).
La variante nette absorbe d'abord la demande future par le stock PF simule au DC-1920. Les snapshots reels a 00:05 sont compares a la fin simulee du jour precedent.
PFI/internal rollups exclus.

## Synthese
| PF | Famille | Variante | Semaines | Reel moyen | Sim moyen | Biais | MAE | Erreur max | Corr |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 268091 | Cos | net_lead_safety | 52 | 930 695 EUR | 615 781 EUR | -314 914 EUR | 314 914 EUR | 843 593 EUR | 0.33 |
| 268091 | Cos | gross_lead_safety | 52 | 930 695 EUR | 605 631 EUR | -325 064 EUR | 325 064 EUR | 843 593 EUR | 0.40 |
| 268091 | Cos | existing_target_stock | 52 | 930 695 EUR | 1 026 476 EUR | 95 780 EUR | 175 269 EUR | 501 765 EUR | 0.37 |
| 268967 | Pharma | net_lead_safety | 52 | 259 678 EUR | 756 450 EUR | 496 771 EUR | 496 771 EUR | 731 464 EUR | 0.10 |
| 268967 | Pharma | gross_lead_safety | 52 | 259 678 EUR | 652 887 EUR | 393 208 EUR | 393 208 EUR | 590 951 EUR | 0.26 |
| 268967 | Pharma | existing_target_stock | 52 | 259 678 EUR | 810 615 EUR | 550 937 EUR | 577 118 EUR | 795 137 EUR | 0.34 |

## Premieres semaines
| Date | PF | Reel | Sim net lead+secu | Gap net | Sim brut lead+secu | Gap brut | Sim cible actuelle | Gap cible actuelle |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025-01-06 | 268091 | 656 922 EUR | 497 997 EUR | -158 925 EUR | 464 060 EUR | -192 862 EUR | 660 726 EUR | 3 804 EUR |
| 2025-01-13 | 268091 | 720 134 EUR | 486 506 EUR | -233 628 EUR | 460 450 EUR | -259 684 EUR | 658 308 EUR | -61 826 EUR |
| 2025-01-20 | 268091 | 606 979 EUR | 476 200 EUR | -130 778 EUR | 458 818 EUR | -148 160 EUR | 720 401 EUR | 113 423 EUR |
| 2025-01-27 | 268091 | 692 705 EUR | 469 187 EUR | -223 518 EUR | 457 376 EUR | -235 330 EUR | 713 735 EUR | 21 029 EUR |
| 2025-02-03 | 268091 | 613 334 EUR | 557 204 EUR | -56 130 EUR | 544 490 EUR | -68 844 EUR | 880 848 EUR | 267 513 EUR |
| 2025-02-10 | 268091 | 656 473 EUR | 568 016 EUR | -88 457 EUR | 555 357 EUR | -101 116 EUR | 890 692 EUR | 234 219 EUR |
| 2025-02-17 | 268091 | 695 645 EUR | 588 958 EUR | -106 687 EUR | 576 338 EUR | -119 307 EUR | 912 203 EUR | 216 558 EUR |
| 2025-02-24 | 268091 | 740 448 EUR | 618 086 EUR | -122 363 EUR | 607 936 EUR | -132 512 EUR | 942 190 EUR | 201 742 EUR |
| 2025-01-06 | 268967 | 220 644 EUR | 354 829 EUR | 134 185 EUR | 240 873 EUR | 20 229 EUR | 79 791 EUR | -140 853 EUR |
| 2025-01-13 | 268967 | 202 837 EUR | 355 780 EUR | 152 943 EUR | 244 936 EUR | 42 099 EUR | 79 791 EUR | -123 046 EUR |
| 2025-01-20 | 268967 | 229 908 EUR | 354 567 EUR | 124 659 EUR | 244 111 EUR | 14 203 EUR | 79 791 EUR | -150 117 EUR |
| 2025-01-27 | 268967 | 207 845 EUR | 351 302 EUR | 143 458 EUR | 242 148 EUR | 34 304 EUR | 79 791 EUR | -128 053 EUR |
| 2025-02-03 | 268967 | 204 820 EUR | 349 209 EUR | 144 390 EUR | 242 835 EUR | 38 016 EUR | 79 791 EUR | -125 028 EUR |
| 2025-02-10 | 268967 | 204 817 EUR | 458 356 EUR | 253 539 EUR | 354 261 EUR | 149 444 EUR | 191 199 EUR | -13 618 EUR |
| 2025-02-17 | 268967 | 235 696 EUR | 504 089 EUR | 268 393 EUR | 404 995 EUR | 169 299 EUR | 239 337 EUR | 3 641 EUR |
| 2025-02-24 | 268967 | 284 703 EUR | 580 703 EUR | 296 000 EUR | 493 669 EUR | 208 966 EUR | 324 903 EUR | 40 200 EUR |