# Un stock tampon de 10 pièces protège-t-il le client pendant deux jours de retard fournisseur ?

Un fournisseur livre un dépôt. Ce dépôt sert un client qui commande cinq pièces par jour. On retarde les deux premières réceptions jusqu’au troisième jour. Le client reste exposé au même fournisseur quel que soit le stock initial. Pour savoir s’il reçoit ses pièces à temps, il faut comparer ses livraisons avec et sans retard fournisseur, à stock initial identique.

## Entrées communes

L’article est fictif. L’unité est la pièce. J1, J2 et J3 sont trois jours consécutifs. Chaque réception devient utilisable au début du jour indiqué. Chaque commande est connue et exigible ce jour-là. Le dépôt reçoit avant de livrer, impute les pièces à la demande la plus ancienne en premier (FIFO), puis reporte tout reliquat au lendemain. Une pièce sortie du dépôt est livrée au client le même jour. La capacité de service est illimitée. Le reliquat initial est nul.

```csv
jour,demande_pieces,reception_nominale_pieces,reception_avec_choc_pieces
J1,5,5,0
J2,5,5,0
J3,5,5,15
```

Faire quatre passages. Pour chacun des stocks initiaux utilisables de 0 et 10 pièces, jouer une fois la colonne nominale et une fois la colonne avec choc. Les 10 pièces du tampon sont présentes avant J1. La réception de 15 en J3 comprend les trois réceptions de 5. Il n’y a aucune perte de matière.

## Résultats attendus par jour

Toutes les quantités du tableau sont des pièces. « Livré au total » inclut les commandes antérieures rattrapées dans la journée. « Livré à l’échéance » compte uniquement les pièces de la commande exigible ce jour-là.

| Réceptions | Stock initial | Jour | Reçu | Livré au total | Livré à l’échéance | Stock utilisable en fin de jour | Demande en retard en fin de jour |
|---|---:|---|---:|---:|---:|---:|---:|
| Nominales | 0 | J1 | 5 | 5 | 5 | 0 | 0 |
| Nominales | 0 | J2 | 5 | 5 | 5 | 0 | 0 |
| Nominales | 0 | J3 | 5 | 5 | 5 | 0 | 0 |
| Avec choc | 0 | J1 | 0 | 0 | 0 | 0 | 5 |
| Avec choc | 0 | J2 | 0 | 0 | 0 | 0 | 10 |
| Avec choc | 0 | J3 | 15 | 15 | 5 | 0 | 0 |
| Nominales | 10 | J1 | 5 | 5 | 5 | 10 | 0 |
| Nominales | 10 | J2 | 5 | 5 | 5 | 10 | 0 |
| Nominales | 10 | J3 | 5 | 5 | 5 | 10 | 0 |
| Avec choc | 10 | J1 | 0 | 5 | 5 | 5 | 0 |
| Avec choc | 10 | J2 | 0 | 5 | 5 | 0 | 0 |
| Avec choc | 10 | J3 | 15 | 5 | 5 | 10 | 0 |

Sans tampon, les 15 pièces livrées en J3 servent d’abord les 5 dues en J1, puis les 5 dues en J2, puis les 5 dues en J3. Les deux premières commandes subissent respectivement deux jours et un jour de retard, soit **5 × 2 + 5 × 1 = 15 pièces-jours de retard**. Avec le tampon, le dépôt sert J1 et J2 sur son stock initial, qui passe de 10 à 5, puis à 0. Les 15 pièces reçues en J3 permettent de servir la demande de J3 et de finir avec 10 pièces.

## Calculs à vérifier

Pour chaque jour, appeler `D` la demande exigible, `R` la réception, `S` le stock utilisable de la veille et `B` le reliquat de la veille. En J1, prendre le stock initial et un reliquat nul.

| Mesure | Calcul |
|---|---|
| Quantité disponible pour livrer | `A = S + R` |
| Livré au total | `L = min(A, B + D)` |
| Livré à l’échéance | `C = min(D, max(0, L − B))` |
| Stock utilisable en fin de jour | `A − L`, reporté comme stock le jour suivant |
| Demande en retard en fin de jour | `B + D − L`, reportée comme reliquat le jour suivant |
| Pièces-jours de retard sur les trois jours | Somme des trois reliquats de fin de jour × 1 jour |
| Part livrée à l’échéance, en pièces | Somme des `C` divisée par les 15 pièces exigibles |
| Part livrée au plus tard à fin J3, en pièces | Somme des `L` divisée par les 15 pièces exigibles |

| Réceptions | Stock initial (pièces) | Livré à l’échéance | Livré au plus tard à fin J3 | Retard (pièces-jours) | Stock fin J3 (pièces) |
|---|---:|---:|---:|---:|---:|
| Nominales | 0 | 15/15 = 100 % | 15/15 = 100 % | 0 | 0 |
| Avec choc | 0 | 5/15 = 33⅓ % | 15/15 = 100 % | 15 | 0 |
| Nominales | 10 | 15/15 = 100 % | 15/15 = 100 % | 0 | 10 |
| Avec choc | 10 | 15/15 = 100 % | 15/15 = 100 % | 0 | 10 |

À stock initial nul, le choc fait baisser de 66⅔ points la part livrée à l’échéance par rapport au nominal. Avec 10 pièces de tampon, cette baisse vaut zéro. Le volume livré à fin J3 est identique dans les quatre passages. Un outil qui s’arrête au volume cumulé ne permet donc pas de voir les deux commandes arrivées en retard.

## Preuves à recueillir pour chaque solution

Répéter les quatre passages pour chacune des solutions étudiées, LCA-SIMU, BOXARR et Supply-Graph, et pour chaque version évaluée. Conserver les résultats de chaque couple solution/version séparément. S’il faut adapter le cas aux conventions d’un produit, consigner la correspondance des champs, l’ordre des événements et l’unité. Une différence de convention non résolue laisse la mesure concernée incomparable.

Consigner la version ou le SHA, la date d’essai, les paramètres des quatre passages et les sorties natives consultées. Pour chaque livraison relever, si disponibles, sa quantité, sa date de livraison et l’échéance de la commande qu’elle sert. Conserver la sortie datée, l’export ou la capture qui permet de retrouver ces valeurs. Si le service doit être reconstitué à partir de traces et de la règle FIFO, indiquer les champs utilisés et marquer le résultat comme recalculé. Un résultat inaccessible reste « non observé ». Une solution sans essai reste « non testée ».

Comparer les sorties aux douze lignes de référence, en pièces entières avant tout arrondi de pourcentage. Signaler la première divergence par scénario, jour et champ, avec la valeur attendue et la valeur observée. Un chemin fournisseur–dépôt–client permet de montrer l’exposition, y compris quand le tampon protège entièrement le client. L’effet sur le service exige les dates, quantités et comparaisons appariées ci-dessus. Le tableau donne les résultats du calcul de référence. Une affirmation sur un produit exige sa propre preuve.

Le [test LCA-SIMU du registre d’impact des lots](../../etudecas/tests/risques/test_risk_lot_impact_registry.py) vérifie déjà qu’un lot peut être relié au client et que cette exposition ne suffit pas à conclure à une perte de service. Il s’appuie sur un autre jeu de données. [Source du test à la révision examinée](https://github.com/yannicktoolexplo/lca-simu/blob/3daaedbbc6d8863c29940170841d4ef15e921a06/etudecas/tests/risques/test_risk_lot_impact_registry.py#L552) · [Contrat du registre à la même révision](https://github.com/yannicktoolexplo/lca-simu/blob/3daaedbbc6d8863c29940170841d4ef15e921a06/etudecas/simulation/lot_trace/RISK_IMPACT_REGISTRY.md)

## Contrôler l’export d’une démonstration

Préparer un CSV UTF-8 par solution et version à partir des sorties observées. Conserver l’export d’origine et la correspondance de ses champs. Utiliser cet en-tête et une ligne par combinaison de `nominal` ou `choc`, de stock initial (`0` ou `10`) et de jour (`J1`, `J2` ou `J3`).

```csv
regime,stock_initial,jour,recu,livre_total,livre_echeance,stock_fin,reliquat
```

Renseigner les mesures en pièces entières. Laisser vide une mesure indisponible. Depuis la racine du dépôt, lancer `python -B tools/portfolio/check_buffer.py mon-export.csv --produit BOXARR --version "version de la démonstration"`, en remplaçant le chemin, le produit et la version par ceux de l’essai.
Le contrôle compare chaque jour au tableau de référence ci-dessus et affiche le bilan de chaque passage. Un `?` indique qu’une mesure nécessaire au bilan manque. Le code de sortie vaut `0` pour un résultat conforme, `1` pour une preuve incomplète ou un écart mesuré et `2` pour un export inexploitable.
