# Réduction des lots figés non lancés : essai commun aux deux PF

**Le surplus tardif diminue, mais le calendrier industriel n'est pas reproduit.**
Pour 268967, le pic de la semaine du 26 mai passe de 539 000 à 107 800 unités,
contre 82 250 estimées par les prélèvements d'étuis. L'erreur hebdomadaire
diminue de 55,5 % et l'erreur de stock de 21,7 %. En revanche, l'écart cumulé
sur les mêmes semaines documentées se dégrade en valeur absolue : +136 500
avant, −294 700 après. L'essai reste une option expérimentale ; la référence
est conservée. Les fabrications précoces et les engagements initiaux restent
le prochain problème à expliquer.

## Question et périmètre

L'[audit de 268967](2026-11-19-audit-complet-268967.md) a montré que cinq lots,
soit 539 000 unités, restaient programmés fin mai après une forte baisse de
prévision connue le 28 avril. Le gel strict empêchait toute annulation.
Cet essai teste une exception explicite à cette interprétation du gel.
L'autorisation industrielle correspondante reste une hypothèse.

Le témoin est le dernier calcul **sans plafond de capacité**, rejoué sur le
même code que le candidat. La seule différence métier est
`--production-frozen-reduction-policy unstarted_whole_lot_reduction_v1`.
La comparaison couvre le 1er janvier au 1er juin 2025 : les mêmes 13 semaines
documentées pour 268967, 21 pour 268091 et 22 photos de stock par PF. Les
semaines absentes restent inconnues.

La taille des lots, les stocks initiaux, les prévisions connues, les règles
de disponibilité, les 25 jours ouvrés de protection du régime historique et
les périodes figées de 28/56 jours restent identiques. Le profil des autres
usages des composants reste le même scénario reconstitué, distinct d'une
observation industrielle. Ni la référence courante ni les anciennes courbes
ne sont remplacées.

## Règle implémentée

À la clôture du lundi, après les opérations physiques de la journée, le
modèle examine les lots figés non lancés, du plus tardif au plus précoce.
Seuls les ordres créés par la simulation sont concernés : les engagements
initiaux observés, les hypothèses d'engagement initial et les lots déjà
lancés restent intangibles.

Pour chaque lot, un calcul sans effet physique retire ensemble sa réception
prévue, ses besoins de composants et sa réservation de travail. L'annulation
est acceptée seulement si les besoins datés des PF et leur protection restent
les mêmes et si leur couverture ne se dégrade à aucune des dates contrôlées.
La comparaison protège aussi l'autre PF et les besoins clients externes.
Les déficits déjà présents ne sont pas assimilés à une couverture totale.

Un lot entier est annulé ; aucune quantité de lot n'est ajustée à la courbe.
Les identités, quantités et dates originales restent dans le journal. Les
stocks physiques, les consommations exécutées et les en-cours ne sont pas
modifiés par cette décision.

Un remplacement peut être proposé après la période figée. Sa disponibilité
reste une projection conditionnelle, sans garantie de composants futurs.
Un apport prévu au jour 41 ne peut jamais couvrir un manque du jour 40.
Annuler puis reproposer plus tard constitue un report ; cela ne prouve pas
une diminution de la production annuelle.

## Vérification de la règle

Oracle simple : stock disponible 80, protection 30 ; deux lots de 100 sont
prévus aux jours 31 et 35 ; les besoins valent 90 au jour 32 et 40 au jour 39.
Sans le deuxième lot, il reste **80 + 100 − 90 − 40 = 50** : l'annulation
respecte la protection de 30. Si un besoin supplémentaire de 30 arrive au
jour 40, il ne reste que 20 : l'annulation est refusée, même si un nouveau
lot pourrait arriver au jour 41.

Les tests ciblés couvrent le défaut strict, les bornes 28/56 jours, les
engagements initiaux, les identités, les besoins aval et les trois contributions
de planification. Une première garde a été renforcée après un test refusé :
un crédit présent à la fois dans les réceptions natives et le carnet figé
bloque toute tentative de réduction avant le recalcul. Cette preuve initiale
reste archivée. Un premier essai complet a ensuite refusé toutes les réductions
parce que le contrôle de la période figée incluait à tort les achats de
composants. Cette garde porte désormais uniquement sur les fabrications. Les
achats restent pilotés par leurs propres besoins et délais. Un test dédié et
deux réseaux indépendants avec achat de composant dans la zone vérifient cette
distinction. Les 98 cas ciblés passent sur l'état final, y compris les bornes
d'arrondi au kilogramme et les cas de protection ci-dessous.

Un oracle indépendant vérifie huit cas datés et six petits réseaux utilisant
le recalcul natif : surplus, manque avant remplacement et report autorisé,
pour les deux horizons, puis achats de composants et multiplicité des
propositions, puis la révision des prévisions et de leur sécurité. Ses
380 contrôles finaux ne constituent pas une calibration industrielle. Un
repère calendaire de cet oracle a été corrigé avant admission : cinq jours
ouvrés ne constituent pas cinq jours calendaires. La preuve refusée et sa
correction restent conservées.

## Résultats comparés

Les deux exécutions de 152 jours sont qualifiées et le témoin reproduit les
sorties métier antérieures. Les résultats complets figurent dans le
[comparatif local](../../resultats/correction_gel_268967_20261119.html)
et le [manifeste final](../../artifacts/testing/correction_gel_268967_v7_20261119/final_manifest.json).

| Mesure pour 268967 | Avant | Après | Réel / lecture |
| --- | ---: | ---: | --- |
| Semaine du 26 mai, unités | 539 000 | 107 800 | 82 250 estimées par les étuis |
| Erreur moyenne hebdomadaire, unités | 59 769 | 26 600 | mêmes 13 semaines documentées |
| Erreur moyenne de stock, unités | 76 123 | 59 636 | mêmes 22 photos à Muret |
| Cumul sur semaines documentées, unités | 539 000 | 107 800 | 402 500 estimées |
| Écart de ce cumul au réel, unités | +136 500 | −294 700 | dégradation de l'écart absolu |
| Nouveaux PF terminés, tous les 152 jours | 646 800 | 215 600 | périmètre distinct du cumul documenté |
| Stock final retenu à Muret, unités | 539 000 | 107 800 | stock physique, pas encore utilisable |
| Stock final utilisable à Muret, unités | 586 253 | 586 253 | inchangé |

Six lots de 107 800 unités sont retirés du carnet : quatre prévus en mai,
deux en juin. Les quatre lots de mai expliquent la baisse exécutée de
431 200 unités. Le retrait du carnet ne constitue pas une économie annuelle :
des propositions ultérieures restent conditionnelles. Le stock physique final
à Muret passe de 1 125 253 à 694 053 unités ; la baisse concerne ici le stock
retenu, ce qui explique l'absence d'effet sur les livraisons de cette fenêtre.

Pour 268091, productions, stocks et écarts au réel sont inchangés : erreur
hebdomadaire de 88 985 unités et erreur moyenne de stock de 320 654 unités.
Les deux produits conservent exactement leurs livraisons et attentes
quotidiennes, client par client. Les demandes de 623 081 et 1 419 969 unités
sont servies à la fin, mais l'attente cumulée reste non nulle ; le transport
normal y est inclus. Aucune conclusion sur la ponctualité contractuelle
industrielle n'est déduite de ces totaux.

Les demandes, consommations cumulées et attentes des 27 autres couples
site/article restent également identiques. Les commandes externes sur cette
fenêtre baissent pour 042342 (60 à 30 millions d'UN) et 708073 (15 000 à
10 000 kg). Cela ne prouve pas une économie annuelle. Le sous-total connu
d'immobilisation augmente de 2 529,46 unités monétaires du modèle ; sa
valorisation reste incomplète et exclut notamment les PF à Muret. La baisse
du stock physique ne doit donc pas être présentée comme un gain de coût total.

Les 98 cas ciblés, les deux qualifications et la porte de contrôle technique
passent. Les contrelectures indépendantes vérifient 380 points préparatoires,
913 points du rejeu du 28 avril, 7 883 points de reproduction du témoin et
19 085 points de comparaison des deux calculs. Une contrelecture de 10 614
points recalcule les résultats comparés à partir des CSV et des sources Excel,
y compris le cumul sur les seules semaines connues. Le contrôle de documentation
générée reste **refusé** : les index et empreintes de références demandent une
revue distincte. Il n'est pas compté parmi les contrôles réussis. Le navigateur
n'a pas été exécuté ; le rendu est vérifié statiquement et par inspection PNG.

Les phases intermédiaires restent conservées. La première a révélé une garde
appliquée à tort aux achats. La deuxième a révélé deux preuves mal interprétées :
une fenêtre de couverture client n'est pas à elle seule un stock de sécurité,
et le rapprochement industriel remplace déjà certains identifiants de besoins
avant l'examen d'un ordre. La troisième a isolé la décision du 28 avril dans
un calcul de 118 jours, puis reproduit exactement ses 21 décisions en mémoire.
Sept retraits passaient la garde du PF, mais la réaffectation des besoins de
trois composants demandait une preuve supplémentaire. Aucun gain n'est attribué
à ces phases sans annulation.

La quatrième phase a montré une restriction excessive du contrôle : il
conservait le niveau de sécurité calculé avec le lot retiré et cumulait deux
compléments prévisionnels alternatifs. Le diagnostic arithmétique exclut un
double débit ou une réception oubliée. La règle distingue donc les engagements
protégés des prévisions futures révisables. La sécurité est recalculée avec les
mêmes jours source sur les besoins maintenus ; sa quantité dérivée n'est pas
figée artificiellement. Cette distinction est testée avant tout nouveau calcul
complet et ne constitue pas une validation de la permission industrielle
d'annuler un ordre dans la période figée.

La cinquième phase a annulé un lot de juin, sans modifier la production ni les
stocks PF sur les 152 jours. Une commande de 5 000 kg du composant 708073 a
été reportée d'une semaine : ses coûts ont été décalés, pas économisés. Cette
phase conserve donc son résultat négatif sur le pic de mai.

Elle a isolé une dernière incohérence numérique : un retrait était refusé pour
49,74 grammes sous une sécurité prévisionnelle d'environ 10 tonnes. La politique
déjà déclarée dans le graphe arrondit les achats nets au kilogramme le plus
proche et garde un reliquat strictement inférieur à 0,5 kg. Le contrôle utilisait
une exigence plus stricte. La sixième phase l'aligne exclusivement pour la
sécurité dynamique vérifiée. Les quantités fixes, les besoins datés et le stock
physique ne bénéficient d'aucune nouvelle tolérance. Le reliquat reste dans
l'audit, sans réception fictive ni modification des quantités physiques.

L'essai court de cette sixième phase n'a toujours annulé aucun lot de mai :
aucun nouveau calcul complet n'a donc été lancé. Le dernier refus provenait
du repli à la fin de la projection. Le contrôle gardait 8 350 175,984 g alors
que la formule native, après retrait du lot, demandait 7 309 397,384 g.
La différence de 1 040 778,6004 g correspond exactement au besoin du lot retiré.
Les besoins des autres usages restent identiques. Le stock projeté dépasse
la réserve recalculée de 221,465 g : le refus ne prouve pas une pénurie.

La septième phase vérifie explicitement la formule du repli : maximum entre
le plancher fixe et la somme des besoins de la fenêtre initiale connue, avec
les mêmes jours source. La fenêtre future incomplète reste inconnue ; aucune
observation future n'est ajoutée. Si les paramètres, la fenêtre ou les champs
d'audit ne prouvent pas ce calcul, l'annulation reste refusée.

## Limites conservées

Cette règle ne reconstitue pas les engagements industriels expliquant les
fabrications dès mars. Elle ne remplace pas non plus l'hypothèse actuelle
d'exécution d'un lot complet dans la journée par une durée physique mesurée.
Les étuis prélevés mesurent une activité de conditionnement, sans identifier
directement des lots terminés. Le rapprochement des flux d'avril reste ouvert.

Les données réelles ne sont utilisées ni pour imposer des fabrications futures
ni pour annuler un ordre afin de faire passer une courbe par un point observé.
L'effet sur le service, les stocks et l'autre PF doit rester visible, même
lorsqu'il dégrade le rapprochement. Aucun navigateur, Node, test d'altération
de fichiers ou campagne globale n'est exécuté pour cet essai.
