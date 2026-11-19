# Règles industrielles et programme de mars pour 268967

Le rapprochement progresse sur deux décisions distinctes. Le MRP de 1430
contient dès janvier un signal pour un lot de mars. Le calcul expérimental
actuel construit ses ordres depuis le besoin net du dépôt et remplace
l'autorisation par les budgets de composants par un carnet figé. Puis, en
avril, il gèle quatre lots regroupés au 26 mai après la révision commerciale
du 31 mars. La baisse du pic de mai traitait donc une conséquence tardive.

| Information donnée par l'industriel | Application vérifiée |
| --- | --- |
| Budget mensuel, demande réelle retranchée chaque semaine, remise à zéro au mois suivant | Actif dans l'essai sans plafond. Le 17 mars, budget de 131 301 unités, demande connue de 84 566, reste de 46 735 réparti sur 15 jours. La carte nominale conserve la convention hebdomadaire antérieure. |
| Gel de 4 semaines à 1810 et 8 à 1430 | Actif dans l'essai, ancré à la date de lancement. Le gel des dates et des quantités ainsi que la possibilité d'annuler un lot restent des interprétations à vérifier. |
| Le dépôt 1920 transmet son besoin et l'usine applique ses lots | Le dépôt transmet la quantité nette exacte. Au démarrage, 1 521 803 unités demandées à l'usine donnent 15 propositions de 107 800 unités pour 268967. Le dépôt applique la protection de 25 jours ouvrés, et la date de demande tient aussi compte du transport et du contrôle. |
| L'usine achète depuis son propre plan | Les quantités des lots et leurs dates génèrent les besoins matière. Le programme matière source déjà prévu avant le gel ne pilote pas encore le placement de ces lots. |

Le suivi des règles de D1450, du délai court conditionnel de 338929 et de
la sous-capacité de 268967 reste associé au
[retour industriel](2026-11-13-retour-industriel-mrp.md). La présente étude
examine le calendrier des décisions pour 1430, avec la taille de lot et le
calendrier sans plafond du dernier essai.

## Les besoins de mars étaient visibles avant le gel

Pour la semaine source du **16 mars**, la version MRP du **12 janvier** donne
**110 495 étuis** et **23 424,94 m** à 1430. Les quantités correspondent au
rapport de nomenclature de **0,212 mètre par unité**. Le rapprochement vaut
aussi pour deux autres jalons de la même version et se retrouve le 19 janvier.
Les cellules portent des sorties planifiées et ne donnent pas l'identité
ni le statut ferme d'un ordre. La marge de 2,5 % entre 110 495 et le lot
standard de 107 800 reste inexpliquée.
[Preuve des cellules et du lot](../../artifacts/testing/rejeu_prevision_268967_20261119/early_programme.json)

Le 12 janvier, le premier lot simulé de 107 800 unités existe déjà et son
lancement est prévu le 30 avril. Il est exécuté le 9 mai. Le carnet natif,
testé sur ce seul ordre, conserve son identité et sa quantité quand sa
date est avancée au 17 mars le 12 janvier. La date reste encore modifiable le
20 janvier, exactement à la borne des 56 jours, et devient figée le 21.
Le retrait d'étuis observé sur les deux semaines du 17 et du 24 mars vaut
109 250 unités. Déplacer un lot entier rapproche ce cumul, mais son exécution
sur une seule journée ne reproduit pas le profil des deux semaines.

Sur les mêmes onze semaines documentées jusqu'au 11 mai, les étuis
indiquent 295 750 unités. L'ancien essai avec autorisation par les budgets
et travail étalé en reproduisait 215 600, contre zéro dans le dernier essai.
Le lot du 9 mai tombe dans une semaine inconnue. L'ancien essai combinait
plusieurs changements, dont un débit uniforme et l'absence de gel, avec une
qualification globale refusée. Le résultat ciblé oriente l'enquête, sans
mesurer l'effet propre de chacune de ses règles.
[Ancien essai](../PRODUCTION_REALISTE_20261115.md)

Sur le stock simulé du 17 mars, sept des huit composants couvrent le lot.
Le 344135 principal est à **0 disponible pour 107 800 requis**. Le substitut
dispose de 107 800 unités dans le modèle, selon une hypothèse de stock initial.
Le contrôle de lancement sans plafond exige le kit principal. La première
commande de 120 000 unités dans le témoin part le 17 mars, puis devient
utilisable le 25 avril. L'essai isolé de planification réemploie le délai de
35 jours calendaires et le contrôle de 4 jours ouvrés. Une commande au
21 janvier serait disponible le **3 mars**, soit 10 jours ouvrés avant
le lancement envisagé. Le calcul complet devra vérifier que la réservation
déclenche effectivement cet achat et que le lot est utilisable dans le réseau.
[Stocks et achat simulés](../../artifacts/testing/correction_gel_268967_v7_20261119/runs/candidate/run/data/mrp_orders_daily.csv)

## La prévision et la protection expliquent deux effets différents le 31 mars

Quatre calculs locaux conservent le stock de 697 655 unités, le lot ferme
de 107 800 et la demande publiée. Le rejeu reproduit les propositions
du 31 mars et leurs dates dans les exports natifs.

| Prévision | Profil de protection | Nouveaux lots proposés sur l'horizon | Lots au 26 mai |
| --- | --- | ---: | ---: |
| 24 février | Calculé avec la version du 24 février | 18 | 1 |
| 31 mars | Calculé avec la version du 24 février | 38 | 2 |
| 24 février | Calculé avec la version du 31 mars | 19 | 3 |
| 31 mars | Calculé avec la version du 31 mars | 38 | 4 |

La hausse de prévision ajoute **20 lots proposés**, soit 2 156 000 unités à
l'horizon du plan. Avec la nouvelle prévision, son profil de protection
regroupe deux lots supplémentaires à la borne du gel sans changer le
total. Les profils croisés sont des calculs d'attribution. Le besoin
industriel réel ne se déduit pas de ces propositions.
[Rejeu et empreintes](../../artifacts/testing/rejeu_prevision_268967_20261119/replay_31_march.json)

## Rapprochement des stocks à D1920

La dernière simulation enregistre les départs de la semaine écoulée le lundi.
Sur neuf photos du lundi, comparer après ces départs révèle un écart stable
de **5 077 unités** avant l'activité de mars. Il atteint **200 408 unités**
le 5 mai. Les 195 331 unités d'écart supplémentaire correspondent au bilan
d'apports nets reconstitué de mars et avril, sous l'hypothèse que la demande
industrielle est servie la semaine où elle est comptée. Ce rapprochement
ne donne pas les départs clients bruts. Le jour de publication de la demande
sert à dater ce que le MRP sait. Le jour physique de chaque sortie reste
une autre donnée. Le taux comparé sur 152 jours porte sur les demandes
publiées. Pour 268091, 77 899 unités de la dernière semaine sont connues
le 2 juin et se trouvent hors de la fenêtre du calcul.
[Contrôle des neuf photos](../../artifacts/testing/rejeu_prevision_268967_20261119/D1920_photos.json)

Le résultat est une étude de données et de décisions locales avec
contrelecture indépendante. La référence et les simulations qualifiées
sont conservées. Le test réseau qui en découle compare sur janvier–avril
un lot existant avancé depuis le signal concordant avec le même lot daté
par le besoin du dépôt. Les achats sont recalculés dans les deux cas et
leurs traces indiquent si l'avance traverse effectivement le contrôle
matière. Le contrôle sur 268091 doit déduire les engagements initiaux
déjà présents avant d'attribuer un signal à un nouveau lancement. Les
dates observées en mars servent à évaluer le résultat.
