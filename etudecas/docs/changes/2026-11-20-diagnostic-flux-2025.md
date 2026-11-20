# Origine des écarts dans les flux de 2025

Le diagnostic réunit **40 couples article-site** documentés par des
stocks, mouvements, plans ou positions d’ouverture. Les photos et
stocks simulés se recoupent sur **31 couples** et 1 563 relevés dans
la référence annuelle. L’essai récent de 152 jours couvre **30 couples**
et 630 relevés. Les autres couples restent repérables par les sources
disponibles et les champs manquants. Le bilan hebdomadaire porte sur
1 295 semaines dans la référence et 538 dans l’essai, avec les dates
et unités des deux photos et des mouvements. Sur les courbes, un clic
sur une semaine ouvre ses mouvements, ses cellules source et le plan
connu à sa date. Le sélecteur de semaine donne accès au même détail.
[Atlas interactif](../../resultats/diagnostic_flux_2025_20261120.html)

L’écart est le stock physique simulé moins le stock physique observé.
Chaque fiche donne le premier point comparable, le plus grand écart
et la semaine où l’écart change le plus. Elle sépare les déclarations
de mouvements et le résidu entre deux photos. Le détail décompose le
bilan entre entrées, prélèvements, autres flux et résidus quand le
périmètre le permet. À Muret le mouvement n’isole pas les entrées et
sorties brutes. Pour 773474 à Gaillac, la colonne d’entrée présente
une redondance connue. Ces deux cas sont examinés à partir du solde
net. Le MRP est donné avec sa version, à titre de plan connu.
[Protocole et masques](../../artifacts/testing/diagnostic_flux_2025_20261120/protocol.json)

## 268091 à Muret, pourquoi le surplus de juin vient de plusieurs périodes

Le 28 avril, Muret compte déjà **1 148 275 unités physiques simulées**,
dont 531 795 en contrôle, face à **819 138 observées**. L’écart de
329 137 précède donc la revue qui fige les onze ordres. Un saut apparaît
dès la semaine du 3 mars. Le modèle reçoit 544 100 unités et expédie
95 154, soit une hausse nette de 448 946. Les photos diminuent de
50 622 unités. Le mouvement déclaré donne une baisse de 79 422, avec
un résidu de +28 800 unités au bilan des photos. Sur les entrées
simulées, 294 895 proviennent de positions d’ouverture et 249 205 de
nouveaux ordres. Cette attribution concerne le journal simulé.

Entre le 28 avril et le relevé du 2 juin, le stock réel augmente de
157 019 unités. Le stock simulé augmente de 1 063 029 unités, avec
1 379 190 entrées et 316 161 départs. L’écart final de **1 235 147**
unités se décompose donc en 329 137 déjà présents et 906 010 accumulés
sur la période. Parmi les arrivées simulées de la période, **333 420**
proviennent des onze ordres du 29 avril, encore en contrôle à la
clôture. Une partie de leur production reste en amont du dépôt.

| Origine des arrivées simulées entre le 28 avril et le 1er juin | Unités |
| --- | ---: |
| Ordres d’ouverture | 440 970 |
| Nouveaux ordres antérieurs au 12 mai | 360 000 |
| Autres nouveaux ordres de mai | 244 800 |
| Onze ordres figés le 29 avril | 333 420 |

Retarder les réceptions de ces onze ordres au-delà du 1er juin laisse
**901 727 unités d’excédent** au dépôt dans un bilan à flux constants.
Retarder les réceptions des 18 nouveaux ordres de mai laisse **656 927**.
Dans ces deux calculs conditionnels, les départs restent couverts par
les lots disponibles. La simulation d’origine n’affecte aucun des
18 nouveaux lots aux clients avant la clôture. Le service simulé ne
permet donc pas de valider la quantité produite. Les livraisons réelles
restent indéterminées dans ce fichier de mouvements.
[Bilan indépendant du dépôt](../../artifacts/testing/diagnostic_flux_2025_20261120/balance_268091/muret_268091_balance.json)

### La décision du 28 et le gel du 29 avril

La prévision publiée le 28 avril augmente de **362 363 unités** pour
les trois semaines du 5 au 25 mai, passant de 566 732 à 929 095. La
prévision du 26 mai diminue de 223 375 à 187 191. Dans le plan simulé,
la cadence du reliquat prévisionnel d’avril augmente aussi. Les
531 795 unités en contrôle au dépôt figurent déjà dans les réceptions
fermes de son calcul net. Les ordres initiaux encore attendus à
l’usine figurent également au plan.

Le mécanisme de placement explique la concentration. Onze demandes
du plan usine devaient devenir disponibles entre le 10 et le 26 mai.
Le premier démarrage révisable au regard des 28 jours figés était le
**26 mai**. Le moteur y place les onze propositions le 28 avril puis
les fige le lendemain, pour 345 600 unités. À besoins et quantités
constants, un calcul des seules dates avant application de cette borne
donne onze dates distinctes, avec un maximum de 57 600 unités par jour.
La comparaison arithmétique isole la compression des dates. Le gel
reste une règle industrielle à conserver.

Sept ordres, soit 230 400 unités, commencent le 26 mai. Le composant
338928 manque aux quatre autres tentatives. Les quatre ordres restants
commencent chacun plus tard, du 27 au 30 mai. La règle de réduction
des lots non lancés examine les onze identités au cours de quatre
revues. Sur 37 examens, 16 relèvent une dégradation de couverture datée
et 21 une dégradation ou une vérification insuffisante sur les autres
usages ou produits. Le flux réalisé confirme donc un effet combiné
du plan de besoins, de l’horizon figé et de la disponibilité du kit.
Les contrôles de protection expliquent pourquoi ces propositions
restent engagées lorsque la simulation les revoit.
[Calcul des dates et des besoins](../../artifacts/testing/diagnostic_flux_2025_20261120/mrp_268091/verification_manifest.json)

Le rejeu de la décision du 28 avril isole deux signaux. Le passage à la
prévision de mai et le reliquat rééchelonné d’avril avancent ensemble
la date du premier manque projeté à Muret. À stocks et engagements
datés constants, garder l’un ou l’autre ancien signal réduit fortement
le volume placé le 26 mai. La protection de stock modifie le volume
planifié sur l’horizon, avec peu d’effet sur cette concentration.

| Signal maintenu au 28 avril | Premier manque projeté à Muret | Fabrication planifiée le 26 mai |
| --- | --- | ---: |
| Témoin, nouvelles prévisions et cadence rééchelonnée | 21 mai | 345 600 |
| Prévision du 31 mars | 30 mai | 28 800 |
| Ancienne cadence d’avril | 26 mai | 129 600 |
| Ancienne protection de stock | 21 mai | 360 000 |
| Ancienne prévision et ancienne cadence | 9 juin | 0 |

Chaque ligne est un calcul local au 28 avril. Les effets sont
conditionnels, avec les mêmes commandes fermes et le même stock.
[Rejeu du plan et variantes](../../artifacts/testing/diagnostic_flux_2025_20261120/mrp_268091/replay_manifest.json) · [Revues du gel](../../artifacts/testing/diagnostic_flux_2025_20261120/later_review_guard.json)

## Exemples amont confirmés

| Article et site | Premier mécanisme à vérifier |
| --- | --- |
| **021081, Gaillac** | Au 17 février, le surplus simulé atteint 665 490 kg. Le bilan retrouve 9 908 kg au premier relevé comparable du 6 janvier, 620 000 kg reçus dans le moteur selon le carnet initial, et 35 582 kg d’écart net de prélèvement. Les mouvements observés enregistrent zéro entrée sur ces semaines. |
| **042342, site 1430** | La réception simulée de 30 millions d’unités le 17 janvier, issue du carnet initial (ligne 56), explique l’écart de variation de la semaine du 13. L’entrée observée est nulle. Les retraits débitent le stock simulé de 16 625 000 unités en prélèvements suivis rejoués et de 125 000 en autres usages. |
| **773474, Gaillac vers 1430** | Une entrée observée de 6 400 kg la semaine du 13 janvier est déjà visible au MRP du 5 janvier. Aucun transfert entrant de 6 400 kg n’est identifié dans l’extrait d’ouverture à 1430. La première réception simulée, de 3 200 kg, tombe le 1er février. |
| **693055, Gaillac vers 1810** | Les mouvements de 1 190 kg observés à l’origine et à destination la semaine du 20 janvier concordent en volume avec les deux réceptions simulées de 590 kg le 15 et 600 kg le 29. Le rapprochement est agrégé sur trois semaines. Les dates réelles de libération restent inconnues. |
| **001893, site 1810** | Trois commandes simulées de 23 920 kg arrivent le 2 février. Le rapprochement de la semaine du 27 janvier montre une hausse observée de 594,032 kg et zéro entrée déclarée. |
| **338929, site 1810** | La semaine du 7 avril, le stock physique observé baisse de 39 700 unités. Le modèle gagne 227 802 unités après une nouvelle réception fournisseur de 418 397 et des retraits de 190 595 liés à des ordres de fabrication d’ouverture. |

La revue précédente comparait la colonne des prélèvements suivis avec
les seuls débits de fabrication simulés. Une partie des retraits
historiques est exécutée dans le modèle comme usages résiduels. L’atlas
affiche les deux quantités. Cela corrige le périmètre du rapprochement
physique pour des paires comme 042342/1430 et 773474/1430. Les débits
rejoués depuis les observations restent des entrées du rapprochement.
[Bilans par paire et semaine](../../artifacts/testing/diagnostic_flux_2025_20261120/flow_atlas_charts_delivery.json)

Sur 28 couples amont comparés au même calendrier de photos, dix
comportent des prélèvements historiques rejoués. Pour 042342 à 1430,
l’écart par semaine passe de 8 195 312 à 987 346 unités quand ces débits
sont rapprochés sur les mêmes 16 semaines. Pour 773474 à 1430, il passe
de 1 183 à 223 kg sur 18 semaines. Ces rapprochements physiques isolent
la part saisie en entrée et la part que le moteur simule lui-même.
[Vérification de la portée du rapprochement](../../artifacts/testing/diagnostic_flux_2025_20261120/replayed_withdrawal_scope.json)

## Prochain test discriminant

Rapprocher les trois positions d’ouverture associées au saut de mars
du 268091 avec les réceptions réelles à Muret et leurs dates de
libération. Appliquer la même vérification aux approvisionnements
d’ouverture du 021081 et du 042342, puis au transfert de 773474
visible au MRP de janvier. Le test départage une date reprise du plan,
un ordre d’ouverture incomplet et un retard d’exécution. Les sources
actuelles donnent surtout des volumes agrégés et des échéances de
plan. L’identité des lots et les expéditions clients brutes restent
inconnues.
[Bilan du saut de mars](../../artifacts/testing/diagnostic_flux_2025_20261120/balance_268091/march_origin_balance.json)

## Vérifications

Le calcul des bilans et des écarts moyens a passé 1 919 contrôles.
Le bilan indépendant du 268091 en a passé 812. Le plan du 28 avril
a été reproduit à partir de l’état daté. Chromium a vérifié la
navigation, les points cliquables, les valeurs sélectionnées et
l’affichage mobile sur le HTML livré, hors ligne. La référence
annuelle et l’essai de 152 jours proviennent de résultats qualifiés
existants. Le rejeu s’exécute en mémoire et conserve les engagements
connus à la date de décision.
[Manifeste de vérification](../../artifacts/testing/diagnostic_flux_2025_20261120/final_manifest.json)
