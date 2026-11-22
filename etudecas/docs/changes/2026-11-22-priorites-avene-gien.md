# Avène et Gien · écarts au réel et essais sur les lots

[Graphiques cliquables et valeurs hebdomadaires](../../resultats/priorites_avene_gien_20261122.html) ·
[Preuves](../../artifacts/testing/priorites_avene_gien_20261122/final_manifest.json)

Le **268091** reste prioritaire pour les volumes engagés en mai.
Les nouveaux essais de report ne préservent pas toutes les couvertures
du plan. Pour le **268967**, le moment où le 042342 devient utilisable
peut faire terminer le lot étudié. Ensuite, déplacer son départ
change le stock de Muret. Le stock déjà présent amortit l’effet sur
les clients dans les scénarios testés.

## Écarts chiffrés sur les mêmes dates

L’erreur absolue en pourcentage est la somme des écarts absolus divisée
par la somme des quantités observées. Le **biais** garde le signe et
mesure si la simulation est globalement au-dessus ou au-dessous.
Les photos du lundi comparent le stock physique aux chiffres simulés
de la veille au soir. La production industrielle est **estimée par
les retraits d’étuis**. Les valeurs physiques simulées distinguent
les nouveaux lots du carnet initial. Une semaine sans observation
est laissée vide dans le graphique et exclue de l’erreur.

| Série et période | Dates communes | Erreur précédente | Erreur du candidat | Biais du candidat |
| --- | ---: | ---: | ---: | ---: |
| 268091 · production, 17 février–16 mars | 4 semaines | 82,32 % | 82,32 % | +82,32 % |
| 268091 · production, 12 mai–1er juin | 3 semaines | 191,65 % | 191,65 % | +172,59 % |
| 268091 · stock à Muret, 12–26 mai | 3 photos | 77,58 % | 77,58 % | +77,58 % |
| 268967 · production, 10 mars–20 avril | 6 semaines | 100,00 % | **74,10 %** | +15,76 % |
| 268967 · stock à Muret, mars–avril | 6 photos | 6,92 % | **3,60 %** | +3,01 % |
| 042342 · stock à Gien, mars–avril | 6 photos | 125,98 % | **116,26 %** | +80,79 % |

Sur janvier–juin, l’erreur de stock à Muret reste **42,39 %** pour
le 268091. Elle baisse de **7,29 % à 3,94 %** pour le 268967 sur
21 photos. Le résultat de production de Gien s’améliore sur
mars–avril. Sur les 13 semaines documentées de la fenêtre complète,
l’erreur de profil remonte de **85,91 % à 88,01 %**. Le biais de
volume se rapproche, de −73,22 % à −46,43 %.
[Séries et pourcentages](../../artifacts/testing/priorites_avene_gien_20261122/series.json) ·
[Oracle des relevés et journaux](../../artifacts/testing/priorites_avene_gien_20261122/validator/chart_oracle.json)

## 268091 · pourquoi le pic reste concentré à Avène

La revue du **27 janvier** place **8 ordres et 259 200 unités** au
24 février, premier jour révisable du plan. Dans l’exécution,
la fabrication se termine les 6 et 7 mars. La revue du **28 avril**
regroupe **11 ordres et 345 600 unités** au 26 mai. Au 1er juin,
**333 420** de ces unités sont arrivées à Muret. Sur les trois
semaines du 12 mai, **732 180 unités** sortent de fabrication
dans la simulation et **268 600** sont estimées par les étuis.
Le stock physique du relevé du **2 juin**, présenté hors score
apparié, est de **976 157 unités** contre **2 211 304 simulées**,
soit **+126,53 %**.

Les **6 906 combinaisons** décalent de 1, 2 ou 7 jours des
sous-ensembles de lots du groupe de février et de celui de mai.
Les informations connues à chaque revue, les tailles de lot,
les engagements fermes et les besoins prévus sont conservés.

- **À +1 jour**, les dates possibles de mise à disposition à
  Muret restent identiques. Les dates requises par le plan d’Avène
  font néanmoins apparaître un manque d’au moins **28 800 unités**
  en février et **19 402 en mai** dans le calcul.
- **En mai, à +2 ou +7 jours**, le report du groupe entier ne
  crée pas de manque supplémentaire sur les besoins clients
  prévus à Muret. Le déficit supplémentaire face à la cible
  de stock de sécurité atteint **323 630** ou **339 092 unités**.
  À dates de demande et sécurité inchangées, aucune combinaison
  ne conserve la couverture aux deux sites.

La trace relie les 19 ordres aux achèvements et aux expéditions
simulées. Les réceptions industrielles brutes par lot manquent.
Le problème immédiat à examiner est le **besoin daté qui impose
le regroupement en sortie de gel**, avec les volumes que le carnet
doit effectivement couvrir. Une baisse de stock à Muret due à un
stock gardé en usine garde le volume de chaîne en place.
[Essais et cheminement des 19 ordres](../../artifacts/testing/priorites_avene_gien_20261122/avene/avene_priority.json)

## 268967 · la date de libération change l’issue du lot

Le calcul suit le travail à cadence fixe du lot de **107 800**.
Dans la variante où les 23 millions d’unités reçues restent
en contrôle, le travail cumulé atteint **74 362 équivalents PF**
le 28 mars. Le lot reste en cours. Le cumul minimal de 042342
à rendre utilisable avant chaque poste est le suivant.

| Avant le travail du | 042342 utilisable en cumul |
| --- | ---: |
| 25 mars | 66 239 unités |
| 26 mars | 716 726 unités |
| 27 mars | 1 367 212 unités |
| 28 mars | 2 017 699 unités |

Ce calendrier permet d’achever le lot le 28 mars dans le calcul.
Avec **13 millions** rendues utilisables le 26 mars, le travail
cumule **106 702 équivalents PF** à cette date de contrôle, le 28.
Le lot reste inachevé. Sur les deux semaines du lot, le calendrier
fractionné ramène l’erreur d’activité en équivalent étuis de
**40,45 % à 9,84 %**. C’est un calcul local avec la cadence figée.
Les classeurs industriels donnent des bornes hebdomadaires
variables. En avril, une autre réception présente surtout du stock
classé dans des semaines futures. En juillet, une part importante
est classée dans la semaine courante.

Sur les 14 relevés de l’essai natif antérieur de 96 jours, corriger
les dates prévues de réception ramène l’erreur du stock physique du
042342 de **52,31 % à 14,65 %**. Si on se limite aux quatre relevés du
17 mars au 7 avril, elle passe de **136,04 % à 103,61 %**. Le gain de
janvier–février masque donc un écart encore élevé autour du lot.
[Essai de réception et quantités comparées](../../artifacts/testing/priorites_avene_gien_20261122/series.json) ·
[Contrôle de l’essai court](../../artifacts/testing/priorites_avene_gien_20261122/validator/receipts_oracle.json)

## 268967 · le premier transfert et le stock tampon

| Hypothèse de départ du lot simulé | Reçu à Muret | Utilisable à Muret | Erreur de stock sur 11 photos |
| --- | --- | --- | ---: |
| 28 mars | 30 mars | 18 avril | **4,95 %** |
| 4 avril | 6 avril | 25 avril | 5,54 % |
| 11 avril | 13 avril | 2 mai | 6,21 % |
| Lot gardé à Gien | — | — | 8,18 % |

Sur ces 11 photos du 17 mars au 26 mai, le départ immédiat se
rapproche le plus du stock physique observé. Les trois calendriers
transférés ont la même erreur, **5,96 %**, sur les six photos
du 21 avril au 26 mai. Le volume de 107 800 reste conservé entre
usine, transit et dépôt. Le stock utilisable à Muret reste supérieur
ou égal à **586 253 unités** en l’absence du lot étudié. Les sorties
clients sont celles du scénario et restent servies sur le rejeu
à flux fixés. Le jour industriel d’arrivée du lot reste inconnu.
[Libérations, transfert et métriques](../../artifacts/testing/priorites_avene_gien_20261122/gien/gien_study.json) ·
[Contre-calcul](../../artifacts/testing/priorites_avene_gien_20261122/gien/gien_oracle.json)

Les résultats orientent deux contrôles séparés. À Avène, ventiler
le besoin au 29 avril entre commandes déjà couvertes et protection
à reconstituer. À Gien, retrouver la première date de 042342
utilisable puis rapprocher les dates de fin de lot, de départ et
de contrôle à Muret. Les essais locaux utilisent des archives
qualifiées. La référence est conservée.
