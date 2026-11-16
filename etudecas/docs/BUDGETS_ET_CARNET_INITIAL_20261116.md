# Budgets de fabrication et carnet initial : essais du 16 novembre 2026

[Comparaison interactive](../resultats/carnet_initial_338928_20261116.html) ·
[Protocole initial](../artifacts/testing/budget_duree_lot_20261116/protocol.json) ·
[Protocole du carnet](../artifacts/testing/budget_duree_lot_20261116/protocol_initial_book.json) ·
[Preuves et limites](../artifacts/testing/budget_duree_lot_20261116/final_manifest.json).

## Ce que l'essai apporte

La reprise de réceptions prévues dès le premier MRP améliore le calendrier de
268091, mais augmente son surplus final. Elle reste une **hypothèse expérimentale**.
Le moteur, les capacités, les tailles de lots et la référence nominale sont conservés.
Pour 268967, la vérification des budgets sur toute la durée du lot ne fournit
aucune autorisation supplémentaire démontrable avec les données disponibles.

Comparaison du 1er janvier au 1er juin 2025, sur le même état de code
`REV-0374` et les mêmes sources :

| Indicateur | Témoin du 15 novembre | Essai du carnet initial |
|---|---:|---:|
| 268091 : erreur absolue hebdomadaire moyenne, 21 semaines connues | 78 377 unités | **44 147 unités ; −43,67 %** |
| 268091 : fabrication cumulée sur ces semaines | 2 420 915 | 2 579 315 |
| Écart au réel estimé, 2 409 100 unités | +0,49 % | **+7,07 %** |
| 268967 : fabrication sur 13 semaines connues, réel estimé 402 500 | 323 400 ; −19,65 % | Inchangé |
| 268091 : stock physique à D1920 en fin de calcul | 1 353 585 | 1 511 985 |
| Écart à la photo du 2 juin, 976 157 unités | +38,66 % | **+54,89 %** |
| 268091 : somme quotidienne des quantités clients en attente | 3 564 139 unités-jours | **2 984 607 ; −16,26 %** |

Le « réel estimé » de fabrication provient des **retraits d'étuis enregistrés**,
pas d'un journal industriel des ordres achevés. Les semaines absentes ne deviennent
pas des zéros. La photo de stock du lundi est rapprochée de la clôture simulée du
dimanche précédent ; l'heure exacte de la photo reste inconnue. Ces chiffres
ne sont pas des résultats annuels.

Les 20 ordres initiaux, soit **1 945 715 unités**, gardent leurs identités et
quantités : neuf se terminent plus tôt, aucun plus tard. Au total, 892 906 unités
sont fabriquées plus tôt. Par exemple, la semaine du 17 février passe de 20 874
à 294 895 unités simulées, pour 285 600 estimées dans les données. La semaine
du 24 mars passe de 350 000 à 38 600, pour 73 400 estimées. D'autres écarts
subsistent : le gain ne signifie pas que toutes les semaines sont reproduites.

## 268967 : pourquoi ne pas ajouter la règle envisagée

Le programme expérimental compare actuellement les composants de tout un lot
au budget de la semaine courante. L'hypothèse testée répartit au contraire le
besoin sur les dates physiques du lot, dans **la seule version MRP connue à la
décision**. Aucune version publiée plus tard ne complète les trous.

Le 7 avril, le lot inchangé de 107 800 unités occupe 14 jours à 7 700 unités/jour.
Cette cadence reste une hypothèse du simulateur. Les semaines sources vont du
dimanche au samedi : le lot traverse donc trois semaines, avec respectivement
46 200, 53 900 et 7 700 unités. Le plan connu le 6 avril renseigne 66 523 étuis
pour la première semaine, mais aucune ligne pour les deux suivantes. Le premier
budget positif suivant concerne le 27 avril, après la fin de ce lot.

L'oracle indépendant examine 96 dates ouvrées où le lot peut finir dans
l'horizon : **aucune ne dispose des budgets datés nécessaires**, même sans
déduire les consommations ou les autres engagements. Les trois lancements du
témoin seraient également refusés. Ce sont des calculs de conditions nécessaires,
pas 96 simulations ni une preuve d'impossibilité industrielle.

La modification stricte n'est donc pas intégrée. La question prioritaire devient
la **fonction du budget** : la colonne source contient des prévisions de besoins
bruts de composants, sans preuve qu'il s'agit d'autorisations fermes de fabrication.
Transformer ce signal en plafond obligatoire demeure une hypothèse à départager.

## 338928 : mécanisme identifié et intervention

La cadence simulée de 50 000 unités/jour provient d'un plafond fournisseur
technique supposé de 62 500, arrondi au multiple d'achat source de 25 000.
Le délai source est de 70 jours ; le contrôle à réception dure six jours ouvrés
dans le candidat. Les commandes des 3–5 janvier arrivent les 14–16 mars puis
deviennent toutes utilisables le 24 mars. Le regroupement du lundi est expliqué ;
aucune erreur arithmétique de ce calendrier n'est démontrée.

Avant le 10 mars, les mouvements industriels enregistrent **1 296 489 unités
reçues**, contre **365 033** prévues par les commandes initiales intégrées au
simulateur. Les nouveaux achats du modèle ne peuvent arriver avant le 12 mars.
L'écart de **931 456 unités** précède donc le rattrapage ; une hausse de capacité
fournisseur ne suffirait pas à réparer ces arrivées précoces.

Le plan connu le 5 janvier prévoyait déjà cinq réceptions supplémentaires,
totalisant **1 057 080 unités**, avant cette borne. L'essai applique à 338928 la
même règle de complément du carnet que celle déjà utilisée pour deux autres
composants : déduction des ordres présents, enregistrement au jour de connaissance,
livraison conventionnelle le jeudi, puis contrôle de six jours ouvrés.

Sources : `Flow_Data_MRP_results.xlsx/Feuille1!H665,H667,H669:H671` ; les
365 033 unités de `H664` sont déjà couvertes par `Extract_En_cours.xlsx/Sheet1!E98:E100`.
La semaine chevauchant la première nouvelle réception possible est exclue.
**Le caractère ferme des cinq entrées prévues, leur fournisseur et leur jour
exact ne sont pas prouvés.** Les réceptions réelles servent uniquement à comparer
les résultats ; elles ne sélectionnent ni les quantités ni les dates ajoutées.

Le MRP réduit ensuite les nouveaux achats de 338928 de **1 050 000 unités**.
Le complément n'est donc pas simplement empilé sur les achats existants : les
réceptions totales augmentent de seulement 7 080 unités sur l'horizon, avec un
calendrier différent. Les deux suivis de lots et les quantités initiales restent
conservés.

## Conséquences et limites

Le volume finalement livré aux clients est inchangé, mais certaines livraisons
de 268091 arrivent plus tôt : la somme quotidienne de l'attente diminue de
579 532 unités-jours. Une unité-jour représente une unité restant en attente
pendant un jour. En fin de calcul, 22 257 unités restent en transit et en attente
client dans les deux cas.

Les 158 400 produits supplémentaires restent au stock utilisable de D1920.
Le stock retenu y reste de 300 180 unités. Les autres usages de 338928 reçoivent
le même total de 1 084 971 unités, avec une attente cumulée ramenée de
7 495 417 unités-jours à zéro. Pour 029313, elle augmente de 20,21 kilogrammes-jours ;
ces unités ne s'additionnent pas aux unités-jours. Les changements des usages
reconstitués après fabrication ne sont pas de nouvelles observations industrielles.

Ce surplus ne vient pas d'un double comptage des 20 ordres initiaux : le programme
autorise neuf nouveaux lots au lieu de six, soit 633 600 unités au lieu de
475 200. Trois lots de 28 800 sont avancés aux 17, 24 et 31 mars ; d'autres
quantités changent en avril. Les quinze contrôles de remplacement conservent
la quantité totale proposée dans chaque instantané. Il reste à tester **la permission
d'avancer ces fabrications**, dont les besoins projetés s'étendent jusqu'en 2026,
et leur raccordement à la protection du dépôt. La conservation du besoin projeté
ne démontre pas que le calendrier retenu est industriellement justifié.

Six bilans hebdomadaires source de 338928 sur seize ne ferment pas exactement.
Les cinq premiers résidus se compensent et le bilan agrégé du 6 janvier au
10 mars ferme ; le dernier écart est de −9 192 unités sur la semaine du 28 avril.
Le contrôle exigeant la fermeture de toutes les semaines reste **refusé** et
conservé dans les preuves. Ces anomalies empêchent une lecture trop précise des
dates industrielles ; elles ne sont pas corrigées artificiellement.

## Vérifications et suite

Une simulation native de 152 jours a terminé en 456,95 secondes, avec un pic
mémoire de 1,34 Go et 341 Mo de preuves. Le témoin est réutilisé après vérification
indépendante des 664 fichiers de code et de toutes ses entrées. Onze tests ciblés
en mémoire passent ; la contre-vérification des CSV passe 103 contrôles et celle
des clôtures des usages reconstitués en passe dix. Aucune suite globale ni test
d'altération de fichiers n'a été lancé. **La qualification globale reste refusée**
sur les cinq familles déjà présentes : disponibilité de transfert interne,
budget des usages reconstitués, provenance d'événements externes et deux contrôles
de traçabilité de ces usages. Les contrôles d'affichage sont numériques et
statiques ; **le navigateur n'est pas exécuté**. Les manifestes détaillent cette
portée ; la conformité locale ne vaut pas validation industrielle ou promotion
de la référence.

Le rapport conserve toutes les courbes simulées et les détails des deux cas.
Ses données sont rapprochées des CSV par 1 033 contrôles d'affichage, puis une
contre-vérification indépendante de 11 991 valeurs et 41 contrôles. Le premier
assemblage a été arrêté à la borne de 32 Mio ; une mesure de 32,20 Mio a motivé
un avenant explicite à 36 Mio par fichier, sans tronquer les preuves.

La suite doit distinguer deux décisions : autoriser une fabrication à partir du
besoin net et des engagements réellement connus ; choisir quand transférer le
produit vers D1920. Pour 268967, un essai séparé devra traiter le rôle du plafond
issu des prévisions de composants. Pour 268091, il faut expliquer les nouveaux
lots qui ajoutent du surplus, puis la disponibilité et les transferts vers le dépôt.
Le scénario de carnet est conservé pour cette comparaison, sans nouveau réglage
par référence et sans modification des capacités.
