# Audit mapping KPI stock composants

## Conclusion

Le facteur `28%` n'est pas une regle metier robuste. Le premier ecart vient d'un probleme de perimetre: le produit `268091` doit etre compare au KPI reel dont le niveau correspond a son stock composant source, pas forcement au fichier libelle `Pharma`.

Pour `268091`, la valeur source consolidee du run vaut 726 887 EUR. La premiere photo `Cos` vaut 656 922 EUR, alors que la premiere photo `Pharma` vaut 220 644 EUR.

Le meilleur rapprochement premier point pour `268091` est donc `Cos` avec un ecart absolu de 69 965 EUR.

## Mapping source produit

| Produit | Division | Description source | Stock source min | Stock source moyen | Stock source max | Stock source run | Stock simulation J0 | Stock simulation moyen |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 268091 | 1810 | Manufacturer of Cosmetics - D1810 | 525 288 EUR | 603 766 EUR | 655 344 EUR | 726 887 EUR | 720 013 EUR | 953 226 EUR |
| 268967 | 1430 | Manufacturer of Drugs - D1430 | 422 500 EUR | 422 500 EUR | 422 500 EUR | n/a | 2 004 345 EUR | 2 878 420 EUR |

## Fichiers KPI reels agreges

| Fichier reel | Premiere photo | Moyenne 2025 | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| Cos | 656 922 EUR | 930 695 EUR | 606 979 EUR | 1 435 465 EUR |
| Pharma | 220 644 EUR | 259 678 EUR | 181 338 EUR | 382 654 EUR |

## Comparaison premier point

| Produit | Reference stock source | KPI reel teste | Premiere photo reelle | Ecart |
| --- | ---: | --- | ---: | ---: |
| 268091 | 726 887 EUR | Cos | 656 922 EUR | 69 965 EUR |
| 268091 | 726 887 EUR | Pharma | 220 644 EUR | 506 243 EUR |
| 268967 | 422 500 EUR | Pharma | 220 644 EUR | 201 856 EUR |
| 268967 | 422 500 EUR | Cos | 656 922 EUR | -234 422 EUR |

## Lecture metier

- On ne peut pas expliquer proprement `~220 kEUR` a partir d'un stock initial `~700-900 kEUR` si ces deux chiffres ne portent pas sur le meme couple produit/perimetre.
- Pour `268091`, le niveau `~657 kEUR` du fichier `Cos` colle au stock composant source; l'ecart restant releve ensuite des mouvements de stock et de la convention de valorisation.
- Le fichier `Pharma` a `~221 kEUR` est un autre perimetre. Pour l'expliquer, il faut auditer `268967` en excluant les PFI internes et probablement certaines familles de composants/packaging, mais ce n'est pas la regle de `268091`.
- La prochaine correction propre est de parametrer explicitement le mapping `produit -> KPI reel stock composants` au lieu d'utiliser `Stock_Composants*Pharma.csv` en dur.