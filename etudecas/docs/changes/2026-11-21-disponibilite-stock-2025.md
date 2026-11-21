# Quand le stock reçu devient utilisable

Un relevé confirme la présence physique. Le MRP peut situer une partie
de ce stock en semaine courante et une autre dans des semaines futures.
Le croisement donne une borne de quantité sur la réception, avec une
précision hebdomadaire. Le jour de libération et le numéro de lot
restent inconnus.
[Explorateur des réceptions](../../resultats/disponibilite_stock_20261121.html)

## Règle de rapprochement testée sur 2025

Les photos du lundi qui précède et du lundi qui suit la réception
sont rapprochées des mouvements signés et des deux versions MRP.
Le bilan physique doit fermer. Les périmètres doivent coïncider aux
deux dates. Un résidu positif stable sur trois photos est conservé
dans un résultat conditionnel. Le plan des réceptions prévues ne
s’ajoute jamais au stock physique. Les observations non renseignées
et les mouvements uniquement nets ne permettent pas ce calcul.

Pour chaque catégorie du plan, courante ou future, la borne basse
est la quantité dans cette catégorie moins tout ce que le stock
physique du début de semaine et les autres mouvements positifs
peuvent expliquer. Elle est ramenée à zéro si ce solde est négatif.
La borne haute est la plus petite des deux quantités, réception
enregistrée et total de la catégorie. Les deux intervalles ne
s’additionnent pas librement. Une partie de la réception peut aussi
avoir été consommée avant le relevé qui clôture la semaine.

| Périmètre | Semaines examinées | Entrée présente en courant, minimum positif | Entrée présente en futur, minimum positif |
| --- | ---: | ---: | ---: |
| Concordant, janvier–juin | 109 | 49 | 1 |
| Concordant, juillet–décembre | 100 | 56 | 4 |
| Résidu stable, résultat conditionnel | 43 | 5 | 3 |

Sur **340 semaines avec une réception enregistrée**, 252 sont
analysables sur 22 couples article-site. Les 88 exclusions tiennent
à un bilan de mouvements ouvert (34), à des périmètres divergents
(24), à un champ absent (1), ou à un champ de mouvement net ou
redondant (29). Dans 134 semaines, les deux bornes minimales valent
zéro. Une arrivée seule renseigne donc peu le statut d’utilisation.

Le 693055 à D1810 fournit un contre-exemple avec périmètre concordant.
Sur les 600 kg reçus la semaine du 3 novembre, au plus 20 kg figurent
dans la semaine courante du plan et **au moins 520 kg** figurent plus
tard. Le 021081 à D1450 apporte un autre garde-fou. Le plan du
5 janvier reporte 379 880 kg à la semaine du 13 janvier. Celui du
12 janvier reporte 479 568 kg vers des semaines ultérieures. Chaque
version se réconcilie avec sa photo, avec un calendrier de report
différent. Les dates futures du plan peuvent donc être révisées.
[Données comparées](../../artifacts/testing/disponibilite_stock_20261121/receipt_bounds.json) · [Oracle des fichiers Excel](../../artifacts/testing/disponibilite_stock_20261121/validator/receipt_bounds_independent.json)

## 042342 à D1430, le volume suffirait avec le bon jour

Sur les 23 millions d’unités reçues la semaine du 17 mars,
**13 à 19,75 millions** figurent en semaine courante du MRP du
23 mars, si le résidu de périmètre de 1,5 million est traité à part.
En avril, sur une autre entrée de 30 millions, **19,5 à 30 millions**
figurent plus tard au plan. En juillet, le même calcul donne **15 à
24,75 millions** en semaine courante sur une nouvelle réception.
Le contraste reste visible avec la même règle de rapprochement.

Le dernier rejeu garde les 23 millions en contrôle jusqu’au 11 avril.
Après le travail du 24 mars, il reste 584 248 unités utilisables.
Le calendrier de fabrication témoin en consomme 2 601 947 sur les
quatre journées suivantes. En reclassant **2 017 699 unités au plus
tard avant le travail du 25 mars**, le réexamen à cadence fixe
retrouve la fin du lot de **107 800 PF le 28 mars**. Le stock physique
reste identique au point de reclassement.

| Hypothèse de disponibilité dans le calcul | Travail cumulé dans le lot au 28 mars | Lot terminé |
| --- | ---: | --- |
| Aucun reclassement | 74 362 PF | Non |
| 2 017 698 unités avant le travail du 25 mars | 107 799 PF | Non |
| 2 017 699 unités avant le travail du 25 mars | 107 800 PF | Oui |
| 13 millions le 26 mars | 106 702 PF | Non |
| 13 millions le 28 mars | 85 142 PF | Non |

Le volume classé courant suffit largement dans le calcul. Le jour
exact change l’issue et la version du dimanche ne le renseigne pas.
Dans le témoin de 152 jours, le lot est reçu à D1920 le 30 mars et
libéré le 18 avril. Le suivi n’attribue aucune expédition client
à ce lot jusqu’au 1er juin. En le retirant du témoin avec les mêmes
départs, le stock utilisable reste au moins de **586 253 PF** après
le 18 avril. Le stock tampon explique l’absence d’effet sur le
service à la coupure de l’essai qualifié de 96 jours.
[Seuil au poste](../../artifacts/testing/disponibilite_stock_20261121/local_release_effects.json) · [Stock tampon au dépôt](../../artifacts/testing/disponibilite_stock_20261121/D1920_buffer.json)

## 001893 à D1810, la disponibilité avance le pic

Le 24 février, le témoin a **95 680 kg physiques en contrôle** et
zéro utilisable. Le MRP du 23 février place **34 537,397 kg** en
semaine courante. La photo réelle est de 38 337,397 kg. Le bilan de
la semaine se ferme par les mouvements signés. Le champ des entrées
physiques est à zéro pour cette semaine, et l’écart de 3 800 kg entre
le plan et la photo reste un résidu, même s’il égale une entrée
prévue. Les trois gros achats reçus dans la simulation début février
restent une autre cause de l’excès physique du modèle.

Dans le calcul des huit ordres figés, les autres besoins modélisés
doivent d’abord être couverts. Ils totalisent **28 020 kg** et
reposent sur une estimation des usages concurrents. Il faut **28 242
kg** de 001893 pour le premier ordre. Libérer un seul lot de 23 920 kg
ne suffit pas. Reclasser l’équivalent des 34 537 kg du plan permet à
**six ordres, soit 201 600 PF**, de passer le contrôle du kit. Le
338929 devient alors la contrainte immédiate. Les deux dernières
fabrications restent en dehors de cette avancée.

À volumes constants, le pic passe de la semaine du 3 mars à celle
du 24 février. Face aux étuis, l’écart absolu cumulé sur les deux
semaines reste **268 295 PF**. Avancer le 001893 traite un blocage
simulé. Pour expliquer la quantité à produire, il reste à distinguer
les usages réellement prioritaires et les huit ordres regroupés par
le gel. Le calcul ne rejoue pas les décisions du MRP.
[Essais de kit et du calendrier](../../artifacts/testing/disponibilite_stock_20261121/local_release_effects.json)

## Décision et contrôles

Le rapprochement proposé sert à signaler une incohérence entre
disponibilité simulée et plan industriel. Une libération dans le
moteur demanderait une information datée sur un lot ou une tranche,
en conservant réception, quantité, provenance et engagement. Le
rejeu des achats sait conserver les ordres et tracer leurs fragments.
Il applique actuellement le délai du carnet. Le classement observé
ici est hebdomadaire et autorise des issues différentes dans la même
semaine. La référence et le moteur sont conservés.

Les seuils locaux ont été contrôlés en mémoire sur les journaux de
deux essais qualifiés. Un oracle indépendant compare les 252 cas aux
classeurs bruts et teste 5 250 configurations synthétiques. Quatre
tests ciblés vérifient la conservation des réceptions et des traces
dans le moteur existant. Le HTML a été vérifié hors ligne sur
ordinateur et mobile. Aucun nouveau run natif n’a été lancé.
[Manifeste complet](../../artifacts/testing/disponibilite_stock_20261121/final_manifest.json)
