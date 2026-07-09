# Audit des cibles MRP de stock

- Run: `C:\dev\lca-simu\etudecas\simulation\result\_reruns\active_mrp_physical_nominal100_20260709_134334`
- Graphe d'entree: `C:\dev\lca-simu\etudecas\simulation_prep\result\reference_baseline\_mrp_bom_tests\bom_weekly_mps_lotified_no_static_fallback_physical_floor.json`
- Lignes stock source: `32`
- Lignes politique MRP source: `25`
- Couples suivis dans `mrp_trace_daily`: `65`

## Lecture cle

La source MRP ne donne pas une cible unique de stock. Elle donne principalement un stock physique J0, un delai de securite et parfois un stock de securite explicite. La simulation transforme ensuite ces parametres en cibles journalieres (`target_stock_qty`, `safety_floor_qty`, `soft_safety_target_qty`) en fonction du signal de demande, des flux et de la position inventaire.

Parametres de scenario qui ne viennent pas directement du classeur MRP:
- `demand_stock_target_days`: `14.0` jours
- `safety_stock_days`: `7.0` jours
- `fg_target_days`: `0.0` jours
- `review_period_days`: `1.0` jour(s)

## Statut global

- Couples avec cible positive: `29`
- Couples avec stock source: `32`
- Couples avec politique MRP source: `25`
- Couples avec ordres MRP simules: `56`
- Lignes d'alertes: `47`

## Points de decision

1. Les cibles fournisseurs `supply_pair` ne sont pas des stocks cibles a tenir: elles peuvent etre a zero tout en generant des commandes d'approvisionnement.
2. Plusieurs composants usine sont pilotes par un delai de securite source, mais la cible effective est souvent une cible molle inferieure au safety floor. Il faut decider si le metier veut tenir le safety floor complet ou une couverture reduite.
3. Les PF/DC/client sont surtout pilotes par couverture de demande et service cible, pas par un stock de securite explicite du fichier MRP.
4. Les stocks J0 viennent bien du snapshot ERP/MRP; ils ne prouvent pas a eux seuls que le stock est immobilise au sens KPI industriel.

## Cas metier a corriger ou confirmer

- `M-1430 / item:344135`: stock J0 nul, aucun en-cours source, mais besoin critique pour `268967`. La simulation commande ensuite, mais ce n'est pas un nominal propre si le composant est cense etre disponible.
- `division 1820`: 16 lignes d'en-cours source ne sont pas mappees. Il faut statuer si 1820 doit alimenter 1810, rester hors perimetre, ou devenir un noeud explicite.
- `SDC-1450 / item:021081`: stock et en-cours importants, mais aucune politique MRP source. C'est acceptable court terme, fragile pour une simulation longue.
- `SDC-1450 / item:773474`: PFI interne avec stock et ordre de production, mais pas de cible positive dans le run. Il faut le lire comme flux interne/PFI, pas comme stock fournisseur.
- `M-1430 / item:730384`: cible explicite faible par rapport a la cible dynamique; a valider avec conditionnement/lot fournisseur.
- Delais source: le fichier parle de jours ouvres; le run les manipule comme jours numeriques. A valider si l'ecart ouvre/calendaire est important.

## Comparaison stock composants immobilise reel vs simulation

| Produit | Reel moyen EUR | Simulation moyenne EUR | Ecart EUR |
|---|---:|---:|---:|
| Cos | 930 695 | 1 622 769 | 692 073 |
| Pharma | 259 678 | 2 631 678 | 2 371 999 |

## Top couples sous cible

| Couple | Semantique | Jours sous cible | Ecart moyen stock-cible | Ordres | Alertes |
|---|---|---:|---:|---:|---|
| `M-1810 / item:268091` | cible calculee par simulation sans politique source directe | 99.8% | -61 305.4 | n/a | stock/position sous cible plus de 80% du run |
| `DC-1920 / item:268091` | delai securite source converti en couverture dynamique | 80.5% | -63 817.1 | 1 404 | stock/position sous cible plus de 80% du run | position sous safety floor plus de 80% du run |
| `M-1430 / item:268967` | cible calculee par simulation sans politique source directe | 27.9% | 32 062.9 | n/a |  |
| `DC-1920 / item:268967` | delai securite source converti en couverture dynamique | 27.3% | 115 443.4 | 478 |  |
| `M-1810 / item:693055` | delai securite source converti en couverture dynamique | 27.2% | -518 510.2 | 128 803 | position sous safety floor plus de 80% du run | nervosite MRP tres elevee: trop d'ordres |
| `C-XXXXX / item:268091` | couverture demande PF/DC/client calculee par scenario | 14.7% | -6 903.4 | 1 334 |  |
| `M-1810 / item:049371` | stock securite explicite source + delai securite | 8.8% | -2 298.0 | 20 | position sous safety floor plus de 80% du run |
| `M-1430 / item:038005` | delai securite source converti en couverture dynamique | 8.5% | -9 886.1 | 13 | position sous safety floor plus de 80% du run |
| `M-1810 / item:338928` | delai securite source converti en couverture dynamique | 5.5% | -827 653.0 | 763 | position sous safety floor plus de 80% du run |
| `M-1430 / item:333362` | stock securite explicite source + delai securite | 3.6% | -543 717.6 | 1 604 | position sous safety floor plus de 80% du run |
| `M-1430 / item:730384` | stock securite explicite source + delai securite | 3.5% | 73 809.8 | 5 |  |
| `M-1810 / item:001893` | delai securite source converti en couverture dynamique | 3.2% | 8 008.2 | 7 |  |
| `M-1810 / item:338929` | delai securite source converti en couverture dynamique | 2.6% | -844 794.7 | 3 821 | position sous safety floor plus de 80% du run |
| `M-1430 / item:344135` | delai securite source converti en couverture dynamique | 2.2% | -140 260.7 | 69 | position sous safety floor plus de 80% du run | 344135: zero stock initial et aucun en-cours source |
| `M-1430 / item:734545` | delai securite source converti en couverture dynamique | 1.5% | 1 509.7 | 11 |  |

## Top couples au-dessus de cible

| Couple | Semantique | Ecart moyen stock-cible | Stock moyen | Cible moyenne | Alertes |
|---|---|---:|---:|---:|---|
| `M-1430 / item:042342` | delai securite source converti en couverture dynamique | 8 835 862.8 | 73 884 538.8 | 65 048 676.0 |  |
| `M-1810 / item:002612` | delai securite source converti en couverture dynamique | 129 737.2 | 135 935.3 | 6 198.1 |  |
| `DC-1920 / item:268967` | delai securite source converti en couverture dynamique | 115 443.4 | 218 906.4 | 103 463.0 |  |
| `M-1430 / item:730384` | stock securite explicite source + delai securite | 73 809.8 | 318 669.8 | 244 860.0 |  |
| `C-XXXXX / item:268967` | couverture demande PF/DC/client calculee par scenario | 39 672.9 | n/a | 75 389.3 |  |
| `M-1430 / item:268967` | cible calculee par simulation sans politique source directe | 32 062.9 | 66 922.4 | 34 859.5 |  |
| `M-1810 / item:007923` | delai securite source converti en couverture dynamique | 22 673.3 | 30 111.1 | 7 437.7 |  |
| `M-1810 / item:001893` | delai securite source converti en couverture dynamique | 8 008.2 | 25 672.8 | 17 664.6 |  |
| `M-1810 / item:426331` | delai securite source converti en couverture dynamique | 6 686.4 | 22 359.7 | 15 673.4 |  |
| `M-1810 / item:001848` | delai securite source converti en couverture dynamique | 2 418.3 | 6 137.1 | 3 718.9 |  |
| `M-1430 / item:708073` | stock securite explicite source + delai securite | 1 578.5 | 10 737.7 | 9 159.1 |  |
| `M-1430 / item:734545` | delai securite source converti en couverture dynamique | 1 509.7 | 10 749.7 | 9 240.0 |  |
| `M-1810 / item:099439` | delai securite source converti en couverture dynamique | 1 217.9 | 4 110.3 | 2 892.4 |  |
| `M-1810 / item:016332` | delai securite source converti en couverture dynamique | 389.8 | 1 084.0 | 694.2 |  |
| `M-1810 / item:039668` | delai securite source converti en couverture dynamique | 234.8 | 292.7 | 57.8 |  |

## Stocks source non retrouves comme etats graphe

| Source | Article | Division | Quantite | Commentaire |
|---|---|---:|---:|---|
| ligne(s) 3 | `item:001848` | 1430 | 31 660 430.0 G | stock source present mais couple site/article non modele dans la cible run |
| ligne(s) 5 | `item:001893` | 1450 | 1 094.0 KG | stock source present mais couple site/article non modele dans la cible run |
| ligne(s) 7 | `item:002612` | 1450 | 414.0 KG | stock source present mais couple site/article non modele dans la cible run |
| ligne(s) 9 | `item:007923` | 1430 | 200 560.0 G | stock source present mais couple site/article non modele dans la cible run |

## En-cours source non resolus

| Raison | Lignes |
|---|---:|
| `unmapped_or_missing_division:1820` | 16 |

## Verdict

Techniquement, le run est coherent avec le graphe d'entree: les stocks J0 et politiques injectees sont exploitables et tracables. Metierement, il ne faut pas appeler toutes les courbes `cible MRP` de la meme facon. Il y a au moins quatre objets differents: stock physique J0, safety floor de reference, cible de commande effective, et politique d'approvisionnement fournisseur.

Priorites recommandees:

1. Renommer dans l'interface les cibles fournisseurs a zero en `politique d'approvisionnement`, pas `cible stock`.
2. Afficher simultanement `safety floor` et `cible effective` pour les composants usine, avec une legende metier claire.
3. Valider avec l'industriel si la cible effective doit etre le safety floor complet ou la cible molle actuelle.
4. Traiter separement le KPI `stock immobilise`: ce n'est pas le stock physique brut; c'est un stock valorise au-dessus d'une regle de couverture utile.
