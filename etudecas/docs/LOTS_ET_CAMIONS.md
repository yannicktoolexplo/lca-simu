# Lots, commandes, palettes et camions

Un lot de traçabilité identifie une quantité dont l'origine de fabrication est commune. Une réception ne suffit pas à établir cette origine : nos identifiants BATCH sont simulés et les numéros fabricant non documentés restent inconnus. Une palette est une unité de manutention ; une commande exprime un besoin ; un camion regroupe des marchandises pour un trajet. Ces identités ne sont pas interchangeables. Une commande peut être livrée en plusieurs fois, un lot réparti entre plusieurs palettes ou livraisons, et un camion contenir plusieurs lots ou commandes compatibles. Le [contrat matières et incidents](MATIERES_LOTS_ET_INCIDENTS.md) précise les liens et leur niveau de preuve.

Dans ce cas, 107 800 UN est la taille fixe du lot de production de 268967. L'hypothèse de conditionnement existante est de 125 UN par caisse et 48 caisses par palette : 863 caisses, 18 palettes et un camion estimé, partiellement rempli. Les 33 palettes représentent une capacité centrale de 198 000 UN selon la place seule. La limite de 23 tonnes doit aussi être respectée ; le poids identifiable du produit ne remplace pas un poids brut chargé.

Pour 268091, le minimum et multiple de fabrication sont de 14 400 UN, avec un maximum déclaré de 142 485 UN. Le plus grand multiple admissible est donc 129 600 UN. Ces paramètres dimensionnent la fabrication ; ils ne prouvent ni une capacité de palette de 14 400 UN, ni la règle industrielle exacte d'attribution des numéros de lots qualité.

## Application à la carte

La section « Regroupement camion » du suivi de lots appelle le même module que la consolidation logistique. Les groupes utilisent trajet, compatibilité et semaine de départ. Le calcul porte sur toutes les lignes du groupe, pas seulement la contribution au lot sélectionné. Les identifiants SHIP restent les lignes de livraison de la simulation ; les groupes sont des propositions de planification, sans déplacement des dates de départ/réception du calcul historique.

Pour 338929, une nouvelle hypothèse provisoire reprend **uniquement le conditionnement** de 268967. Elle est enregistrée dans `logistics_estimate_proxies`, séparément des profils du moteur. Aucune masse d'un autre article n'est copiée. Cette analogie n'est pas une mesure du composant et elle est indiquée dans la carte. Elle applique la demande de l'utilisateur d'utiliser des estimations ; elle ne prétend pas retrouver un conditionnement historique validé pour 338929.

Les quatre SHIP de la capture se répartissent entre trois semaines de départ :

| Semaine | Lignes visibles | Groupe complet sur ce trajet | Palettes estimées | Camions selon les places palettes |
|---|---|---:|---:|---:|
| J42–48 | SHIP-00000251 | 105 000 UN | 18 | 1 |
| J49–55 | SHIP-00000252 | 145 000 UN | 25 | 1 |
| J56–62 | SHIP-00000203 et SHIP-00000204 | 150 000 UN | 25 | 1 |

Ces totaux comprennent les autres livraisons de la semaine. Ils ne correspondent pas aux seules 14 400 UN consommées par PBATCH-411EC755D7110AE0. Les quantités de production, les stocks, les consommations et les dates de la simulation ne sont pas recalculés par cette vue.

## Vérification

Les tests distinguent un nombre estimé d'un chargement dimensionné. Un profil sourcé de 25 tonnes doit produire au moins deux chargements sous la limite de 23 tonnes ; sans profil complet, `truck_count` reste indéterminé et `estimated_truck_count` porte l'estimation séparée. Les tests vérifient aussi les 18 palettes du lot 107 800 UN et le regroupement des quatre SHIP en trois semaines. Le navigateur vérifie l'analogie affichée et les identifiants regroupés. Les preuves sont dans `artifacts/testing/transport_20260918`.
