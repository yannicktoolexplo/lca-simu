# Itérations de rapprochement entre l’usine, D1920 et les clients

Le rapprochement examine séparément les volumes qui entrent à D1920,
la date des réceptions et du contrôle, la règle qui déclenche le
transfert depuis l’usine et la date de livraison au client. Les deux
produits sont évalués à dates, unités et sources comparables.
[Explorer les essais](../../resultats/iterations_chainage_20261121.html) ·
[Preuves et empreintes](../../artifacts/testing/iterations_chainage_20261121/final_manifest.json)

## 1. Départager volumes reçus et date des sorties

Sur 21 semaines comparables par produit, remplacer par calcul les
sorties simulées par la demande historique, en gardant les réceptions
simulées, donne les résultats suivants. L’erreur compare la variation
du stock physique à celle des photos industrielles, avec les
ajustements suivis séparément. Les sorties clients effectives et les
autres sorties brutes ne sont pas identifiées.

| Produit | Erreur moyenne de variation hebdomadaire | Après échange comptable des sorties |
| --- | ---: | ---: |
| 268091 | 128 234 unités | 127 631 unités |
| 268967 | 23 692 unités | 12 613 unités |

Pour le 268091, conserver les **544 100 unités reçues en simulation**
à la semaine du 3 mars exige **202 467 à 231 267 sorties de plus**
que toute la demande de cette semaine et des quatre précédentes,
même en supposant leur report intégral. La fourchette compare les
deux bornes données par le mouvement signé et par les photos.
Le constat se retrouve à d’autres dates du 268091, dont le 12 et
le 26 mai. Pour le 268967, la semaine du 3 mars est compatible
avec un écart d’horloge sur les sorties. Il n’y a aucune réception
simulée et l’échange comptable ramène l’écart de −17 730 à −1 unité
sur cette semaine.
[Rapprochements et cellules](../../artifacts/testing/iterations_chainage_20261121/sources/receipt_pressure.json)

## 2. Rejouer le calendrier à quantités conservées

Le calcul retrouve les 304 états journaliers du témoin archivé pour
les deux produits. Douze variantes testent le report des réceptions
du week-end, un jour de transit supplémentaire, un jour hebdomadaire
d’expédition, plusieurs durées de contrôle et une combinaison.
Les volumes et les lots enregistrés sont conservés, y compris
lorsqu’une réception sort de la fenêtre. Ce rejeu n’applique pas
de nouveau plan de production.

| Produit et convention de photo | Témoin | Réception du week-end reportée au lundi |
| --- | ---: | ---: |
| 268091 · fin de dimanche | 277 106 | 250 609 |
| 268091 · fin de lundi | 263 435 | 263 435 |
| 268967 · fin de dimanche | 32 873 | 35 157 |
| 268967 · fin de lundi | 12 389 | 12 389 |

Les valeurs sont des erreurs absolues moyennes de stock à D1920.
Le 10 mars, la photo est de 540 004 unités. En décalant les
403 200 reçues le samedi et le dimanche, le stock simulé du dimanche
passe de 935 531 à 532 331, avec toujours 863 670 unités le lundi
soir. Le stock utilisable le dimanche reste à 264 636.
Allonger ou raccourcir le contrôle de deux ou cinq jours ouvrés
change le stock utilisable. Les volumes expédiés et les courbes
de stock physique restent identiques sur le rejeu.
Les variantes ne créent aucune attente supplémentaire au départ
de D1920 sous la convention de demande du témoin.
[Rejeu des calendriers](../../artifacts/testing/iterations_chainage_20261121/timing_replay.json) ·
[Oracle indépendant](../../artifacts/testing/iterations_chainage_20261121/validator/grid_oracle.json)

Le bundle de référence actif place déjà les 10 et 15 jours ouvrés
de contrôle à D1920 après transport. L’ancien résultat annuel
utilisé comme comparaison plaçait le contrôle en usine. Un
déplacement comptable du stock en contrôle, à dates d’utilisation
identiques, améliore l’erreur de niveau du 268091 mais dégrade
celle du 268967. Les deux versions doivent être identifiées avant
de comparer leurs stocks en contrôle.
[Emplacement dans les graphes](../../artifacts/testing/iterations_chainage_20261121/sources/control_scope.json) ·
[Essai à libérations inchangées](../../artifacts/testing/iterations_chainage_20261121/sources/control_location.json)

## 3. Mesurer le service au bon jalon

Dans le scénario archivé de 152 jours, D1920 expédie les **1 419 969**
unités du 268091 et les **623 081** du 268967 le jour où la demande
est publiée. Les quantités arrivent intégralement à **J+2**.
L’indicateur historique de disponibilité vaut pourtant **33,33 %**
pour chacun. Il compte les jours avec un besoin entièrement
satisfait à la clôture. L’analyse affiche donc séparément les
unités encore à expédier, celles déjà en transit et les livraisons
à un délai donné après publication.

Si on répartit cette même demande sur les jours d’effet reconstruits,
la part livrée à J+7 est de 71,62 % et 72,02 %. Les dates individuelles
de commande restent inconnues. Les volumes publiés après la
clôture restent hors de ces comparaisons. Le CA perdu conserve son
périmètre financier.
[Trajet des 40 expéditions](../../artifacts/testing/iterations_chainage_20261121/service/service_split.json) ·
[Contrôle indépendant](../../artifacts/testing/iterations_chainage_20261121/validator/service_oracle.json)

## 4. Rejouer le moteur avec des transferts déclenchés par le besoin

Les deux exécutions appariées couvrent **98 jours du 1er janvier
au 8 avril**. Le témoin reproduit chaque jour la série déjà qualifiée
sur les deux produits. Dans l’essai, le besoin daté de D1920
déclenche le transfert. Le témoin expédie tout le stock rendu
utilisable en usine. Les demandes connues à chaque date, les lots, les délais,
les protections et le reste du scénario sont partagés.

| Erreur absolue moyenne sur les photos du 17 mars au 7 avril | Témoin | Transfert selon le besoin |
| --- | ---: | ---: |
| 268091 · fin de dimanche | 286 211 | 262 112 |
| 268091 · fin de lundi | 209 058 | 181 911 |
| 268967 · fin de dimanche | 26 899 | 52 679 |
| 268967 · fin de lundi | 15 027 | 68 927 |

Le 10 mars, sur le 268091, l’écart à la photo industrielle passe de
**+395 527 à +165 127 unités** en fin de dimanche et de **+323 666
à +83 271** en fin de lundi. L’amélioration persiste sur les photos
suivantes. À D1430, le lot de **107 800** est fabriqué dans les deux
cas. Le témoin le transfère et l’essai le garde à l’usine dans la
fenêtre. L’erreur de stock de D1920 augmente pour ce produit.

Le stock physique total en usine, en transit vers D1920 et à D1920
est exactement identique chaque jour entre les deux variantes
pour chacun des produits. Les lots
neufs totalisent **259 200** unités à D1810 et **107 800** à D1430
dans chaque exécution. Les **1 030 550** unités issues du carnet
initial libérées à D1810 sont comptées à part. À la clôture,
**62 277** et **33 853** unités déjà expédiées attendent seulement
leur livraison. L’attente avant départ reste nulle.
[Comparaison des runs](../../artifacts/testing/iterations_chainage_20261121/native_comparison.json) ·
[Oracle des séries](../../artifacts/testing/iterations_chainage_20261121/validator/native_oracle.json) ·
[Stock de bout en bout](../../artifacts/testing/iterations_chainage_20261121/validator/chain_daily_oracle.json)

## Décisions

Le transfert déclenché par le besoin explique une part de l’écart
du 268091 à D1920. La dégradation du 268967 et le déplacement
de stock empêchent de retenir cette règle générale. Le calendrier
du quai pourrait expliquer un décalage ponctuel de photo. Les
essais ne démontrent aucune correction commune de ce calendrier.
La référence reste en place.

La prochaine itération doit départager le **volume libéré en usine**
et la **décision d’expédier**. Pour le 268091, rapprocher les lots déjà
engagés et les nouveaux ordres qui alimentent les départs du 6 au
8 mars. Pour le 268967, examiner le départ du lot de 107 800 après
sa fabrication malgré une couverture élevée à D1920. La bonne unité
d’analyse est une position datée de stock, avec le type de besoin,
le départ, la réception et la première date où le lot peut servir.
L’affichage du service distingue désormais les jalons dans ce rapport.
