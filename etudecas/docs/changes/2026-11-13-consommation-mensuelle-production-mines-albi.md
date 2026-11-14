# Consommation mensuelle et comparaison des productions

Travail du 13 novembre 2026, sur `dev_yannick`, à partir du commit `6fcb2ba0c`.
Les preuves sont conservées dans
`etudecas/artifacts/testing/mensuel_mines_albi_20261113/`.

Le [comparatif à trois courbes et grille d'acceptation](../../resultats/comparaison_production_grille_mines_albi_20261114.html)
réunit les données réelles, Mines Albi et notre simulateur hebdomadaire sur le
même graphique pour chaque produit. Les versions précédentes restent conservées.
**Conclusion : le programme est moins souvent révisé, mais la production ne
se rapproche pas uniformément des observations.** La référence n'est pas promue.

## Règle implémentée

Le candidat explicite `calendar_month_actual_demand_v1` soustrait du budget du
mois la demande réelle déjà connue, puis répartit le reste sur les jours futurs
du mois. La référence conserve sa règle hebdomadaire. Les données sources,
stocks initiaux, ordres, délais, capacités et lots ne sont pas ajustés.

L'exemple utilisateur passe : 1 000 − 300 = 700 UN sur trois semaines ; puis
700 − 250 = 450 UN sur deux semaines. Le premier du mois renouvelle seulement
la prévision. La demande non servie et les engagements physiques persistent.

Les budgets mensuels sont reconstruits à partir des prévisions hebdomadaires
connues au début du mois, avec prorata calendaire et repli documenté pour les
fragments non couverts. Le réétalement quotidien suit la revue MRP existante :
c'est une hypothèse d'implémentation, distincte du témoignage de revue hebdomadaire.
La date de publication réelle des versions et les premières semaines suspectes
de janvier/février restent à expliquer avec l'industriel.

Fichiers : `simulation/engine/monthly_forecast.py`,
`simulation/engine/run_first_simulation.py`,
`tests/simulation/test_monthly_forecast_consumption.py`.
La variante est limitée à 365 jours, origine en début de mois. Son argument est
transmis par `current_reference_sensitivity_runner.py`, pas par les CLI strictes
`regenerate.py` ou `current_reference.py`.

## Ce qui est mesuré

La production physique simulée comprend les sorties des nouveaux ordres et les
achèvements des ordres initiaux. Ces deux contributions sont séparées. La
libération qualité rend disponible un lot déjà produit : elle ne s'ajoute jamais
à sa fabrication. Les réceptions à D1920 constituent encore un autre événement.

Les ordres initiaux utilisent l'hypothèse d'encours à l'ouverture ; leurs matières
hors packaging sont déclarées non tracées avant l'horizon. Leur achèvement dans
le modèle ne prouve ni une fabrication industrielle à cette date ni une charge
machine exécutée en 2025.

Le comparatif industriel utilise une production **estimée à partir des mouvements
de packaging divisés par la nomenclature** : 338929 pour 268091 et 333362 pour
268967. Ce n'est pas un journal certifié d'ordres de fabrication. Les semaines
absentes restent inconnues. Les fenêtres complètes vont du 6 janvier au 28 décembre ;
46 semaines sont renseignées pour 268091 et 36 pour 268967, sur 51 possibles.
Les comparaisons de quantités utilisent les mêmes semaines renseignées dans les
deux simulations et la source, séparément des totaux de simulation sur 365 jours.

À D1920, la colonne source « Entrées » est effectivement renseignée à zéro
dans les lignes examinées, tandis que « Sorties » contient des mouvements de
signes différents. Cela ne prouve pas l'absence de réceptions physiques.
Le rapport ne trace donc **aucune courbe industrielle de réception** et ne
calcule aucun score de réception : cette vue compare seulement les simulations.
Les mouvements signés ne sont transformés ni en livraisons clients, ni en
réceptions brutes par leur signe ou une somme de colonnes.

## Comparaison à Mines Albi

L'utilisateur confirme ne disposer que des captures de leur version v2c, pas de
ses séries numériques ni de son code. Leurs écarts annuels de production **−4 % pour 268091 et −9 %
pour 268967** sont rapportés, pas recalculés. Leur corrélation de trajectoire
porte sur les **stocks**, pas sur la production. Aucun classement numérique de
nos modèles à périmètre identique n'est démontré avec ces seules images.

La courbe noire de leur image est aussi une estimation à partir des étuis ;
la courbe grise représente les entrées à D1920. Leur grille mesure un stock
comprenant la marchandise en contrôle. Il faut leurs exports datés, les formules
et la définition de leur compensation pour reproduire la comparaison.

### Courbe industrielle calculée depuis les données

#### Trois courbes réunies, avec leur propre couverture — 14 novembre

Le [comparatif à trois courbes](../../resultats/comparaison_production_3_courbes_completes_20261114.html)
affiche exactement trois lignes par produit : **noire, production réelle estimée
depuis les fichiers ; orange, Mines Albi reconstitué depuis la photo ; bleue,
notre simulateur hebdomadaire**. Aucun mode de sources séparées ni courbe
mensuelle n'est affiché. Le cumul hebdomadaire est sélectionné par défaut ;
les volumes par semaine restent disponibles dans le même graphique. Chaque
courbe conserve ses dates et ses quantités disponibles, indépendamment des
deux autres.

La ligne bleue utilise par défaut le nominal annuel archivé, dont la politique
`weekly_actual_orders_v1` est confirmée dans le résumé original. Le témoin
hebdomadaire récent de 135 jours peut être sélectionné à sa place ; une seule
ligne bleue reste visible. Il demeure inconnu après le 15 mai. Les jours
disponibles des semaines partielles sont conservés et signalés : le dernier
point annuel est le 31 décembre, pas le 28 décembre. Ces deux versions ne
mesurent pas un effet mensuel.

La ligne orange reprend les repères et les plateaux de la **simulation Mines
Albi**, relus sur la photo : environ 4,8 millions en fin de courbe pour 268091,
et 1,15 million pour 268967. Le cumul est tracé directement depuis ces repères,
sans retirer les périodes où une autre source manque. Une interpolation entre
eux donne des quantités hebdomadaires **indicatives**, pas les véritables
exports de Mines Albi. Les dates et les volumes restent des lectures manuelles
approximatives ; aucun point précis n'est présenté comme un export original.
Les derniers points ne sont pas prolongés au-delà de leur couverture lue.

La ligne noire additionne les quantités industrielles documentées. Ses semaines
absentes restent inconnues dans la vue hebdomadaire ; relier les observations
du cumul ne fournit aucune quantité pour ces semaines. Ce cumul documenté
n'est pas un total industriel annuel certifié. Le bleu annuel conserve ses
totaux physiques de **4 825 715 UN** et **1 509 200 UN**. Aucun score comparatif
ne divise ces totaux complets par un total industriel partiel.
La relecture bornée des sources et du cache de la carte complète retrouve les
mêmes stocks, mouvements et estimations Scan3 ; elle n'identifie aucune série
supplémentaire de fabrications industrielles permettant de compléter les
46 et 36 semaines documentées.

L'ancienne [vue sur semaines communes](../../resultats/comparaison_3_courbes_hebdo_20261114.html)
est conservée. Elle recalculait les trois cumuls sur le même sous-ensemble de
semaines : cela ramenait notamment l'orange de 268967 à environ 0,75 million.
Cette représentation ne reproduisait donc pas la courbe complète de la photo.
La nouvelle vue retire ce filtrage de l'affichage. Un éventuel calcul de biais
reste soumis à des périodes communes, distinctes des courbes complètes.
Les preuves de cette correction sont sous
`artifacts/testing/trois_courbes_completes_20261114/`. Aucun score de calibration,
classement ni précision hebdomadaire originale Mines n'est revendiqué.
Le [manifeste de livraison](../../artifacts/testing/trois_courbes_completes_20261114/final_manifest.json)
relie les contrôles indépendants aux empreintes des données et du HTML livré.
Les interactions JavaScript sont contrôlées en mémoire ; le navigateur n'est
pas exécuté et la qualification globale antérieure reste refusée.

#### Estimation de la grille d'acceptation — 14 novembre

Le [comparatif avec la grille Mines Albi](../../resultats/comparaison_production_grille_mines_albi_20261114.html)
ajoute les sept critères à la même simulation annuelle archivée, sans modifier
les trois courbes. Les chiffres Mines sont rapportés depuis la capture ; nos
calculs utilisent les sources numériques. Leur code et leurs définitions
complètes ne sont pas disponibles : les résultats ci-dessous restent des
estimations selon des conventions explicites.

Le périmètre principal est le **stock physique à D1920, contrôle inclus**.
Il est comparé aux 52 relevés du lundi, du 6 janvier au 29 décembre 2025,
avec la clôture simulée du dimanche précédent. La photo initiale du 1er janvier
est exclue des indicateurs hebdomadaires. L'Excel fournit un « Stock Total »,
sans ventilation du contrôle : son inclusion reste une hypothèse de comparaison.

| Critère estimé | Seuil de la capture | 268091 | 268967 |
|---|---|---:|---:|
| Conservation locale à Muret, écart maximal sur 365 jours | 0 UN | 0 UN | 0 UN |
| Production annuelle par rapport au réel | ±10 % | Indéterminée | Indéterminée |
| Biais moyen du stock physique | ±10 % | +14,80 % | +17,99 % |
| Pire trimestre, erreur de moyenne de stock | ≤30 % | 40,20 % | 73,91 % |
| Corrélation des trajectoires de stock | ≥0,7 | 0,855 | 0,199 |
| Relevés hebdomadaires au stock physique nul | 0 | 0 sur 52 | 0 sur 52 |
| Gain face à un stock constant, erreur absolue moyenne | ≥25 % sous cette définition | −71,80 % | −35,05 % |

Le volume de production sur les **seules semaines connues** reste calculable :
−4,38 % pour 268091 sur 46 semaines et −23,23 % pour 268967 sur 36 semaines.
Ce ne sont pas des erreurs annuelles. Aucun score global comparable sur sept
critères n'est attribué.

Les formules choisies sont :

- Biais : `100 × (moyenne(S) − moyenne(R)) / moyenne(R)`.
  `S` désigne les stocks physiques simulés et `R` les stocks industriels aux
  mêmes dates, en unités. Le pire trimestre prend le plus grand biais
  trimestriel en valeur absolue.
- Corrélation : coefficient de Pearson entre les séries `S` et `R`, avec
  `S` les stocks physiques simulés et `R` les stocks industriels aux mêmes dates.
- Gain : `100 × (1 − MAE(S,R) / MAE(C,R))`.
  `S` est le stock simulé, `R` le stock industriel, `C` un stock toujours égal
  à la moyenne industrielle ; `MAE` est la moyenne des écarts en valeur absolue.
  Un gain négatif signifie que cette référence constante est plus proche
  des observations selon l'erreur choisie. Sa moyenne est calculée après coup
  pour l'évaluation ; elle n'est pas injectée dans les décisions MRP.
- Conservation locale : `stock_fin = stock_début + réceptions − départs`.
  Les stocks, réceptions et départs sont les quantités physiques à Muret,
  en unités. Une libération du contrôle change l'état, pas la quantité physique.

Les variantes testées conservent aussi la clôture du lundi, l'erreur absolue
trimestrielle et les gains calculés avec l'erreur quadratique ou sa racine.
Ces variantes ne changent pas les échecs du pire trimestre et du gain, ni
le contraste entre les corrélations des deux produits. Le disponible seul
reste un diagnostic de périmètre distinct : le confondre avec le physique
ferait artificiellement passer les deux biais moyens sous 10 %.

Le zéro du stock physique ne mesure pas le service client. Pour 268091,
le stock disponible simulé est nul du 8 au 22 avril, soit 15 jours. Chaque
jour, le stock physique est entièrement retenu en contrôle, sans quantité
réservée ; cela ne prouve pas 15 jours de rupture client réelle.

Les preuves et les contrôles effectivement exécutés sont reliés dans le
[manifeste de la grille](../../artifacts/testing/grille_mines_albi_20261114/final_manifest.json).
La fermeture vérifiée à Muret ne qualifie ni toute la nomenclature, ni
l'ensemble du modèle industriel. Le navigateur n'est pas exécuté.

#### Vue de données précédente, conservée

Le [comparatif avec le réel issu des fichiers](../../resultats/comparaison_production_reel_donnees_mines_albi_20261113.html)
utilise comme courbe noire la **production réelle estimée depuis les étuis**.
Les repères noirs lus sur la photographie ne sont plus une référence active.
Les quantités proviennent directement de la colonne « Sorties_article_scan3 »
du fichier `Flow_Data_Inventory_movements.xlsx`, pour 338929 à 1810 et 333362 à
1430, puis de leur coefficient de nomenclature dans `268091.xlsx` et
`268967.xlsx`. L'opposé de la sortie signée d'étuis est divisé par ce coefficient,
égal à un dans les deux cas. Ce calcul reste une estimation de fabrication,
distincte d'un registre industriel d'ordres exécutés.

L'extraction brute et la contre-revue indépendante confirment **46 semaines
renseignées pour 268091 et 36 pour 268967**, sur 51 semaines complètes du
6 janvier au 28 décembre. Elles contiennent respectivement 14 et 12 zéros
explicites. Les cinq et quinze autres semaines n'ont pas de ligne : elles
restent inconnues. Les fragments du 1er au 5 janvier et du 29 au 31 décembre
ne sont pas non plus renseignés. Le véritable cumul calendaire depuis le
1er janvier est donc indéterminé.

La vue de données présente les volumes hebdomadaires ou le **cumul des seules
semaines renseignées**, avec des trous visibles. Le cumul reprend après un trou
en additionnant uniquement les semaines connues ; il ne prétend pas retrouver
le volume physique manquant. Les simulations sont agrégées et masquées sur les
**mêmes semaines**. Pour les calculs de 135 jours, la semaine du 12 au 18 mai
est exclue car le calcul s'arrête le 15 mai. Aucun volume observé ou simulé
n'est inventé pour compléter ces périodes.

La simulation orange Mines Albi reste une lecture photographique incertaine,
dans un mode visuel séparé : son cumul complet ne peut pas être comparé
numériquement à un cumul de semaines connues sans sa série d'origine. La série
grise reste consultable dans l'ancien comparatif photographique, sans qualification
de réception physique brute. Aucun pourcentage précis contre la photo n'est ajouté.
L'[ancienne comparaison photographique](../../resultats/comparaison_production_avec_photos_mines_albi_20261113.html)
est conservée séparément, avec ses intervalles de lecture et sa provenance.

Le nominal annuel archivé et les nouveaux essais limités au 15 mai gardent
leurs versions et leurs limites précédentes. Aucun nouveau calcul de simulation
ni aucun paramètre MRP n'est changé pour construire la courbe industrielle.
Les preuves de cette correction sont sous
`artifacts/testing/courbe_reelle_donnees_20261113/`.

## Résultats et statut des calculs

Les deux calculs de 60 jours sont terminés : même demande réelle, mêmes
initialisations et même service client. Pour 268091, les deux donnent 544 239 UN
issues des ordres initiaux et aucune fabrication de nouvel ordre ; 523 365 UN
sont libérées et reçues à D1920. Les 20 874 UN restantes sont encore en contrôle.
Ces volumes ne doivent pas être additionnés. Aucun de ces flux pour 268967.

Sur les exports complets des **135 jours jusqu'au 15 mai**, la consommation
mensuelle stabilise le programme sans améliorer uniformément la production :

| Indicateur | Hebdomadaire | Mensuelle |
|---|---:|---:|
| Révisions / comparaisons actives du programme | 3 427 / 13 161 | 2 515 / 13 213 |
| Taux de révision du programme simulé | 26,04 % | 19,03 % |
| Nouveaux lots 268091 achevés, UN | 590 400 | 676 800 |
| Première sortie d'un nouveau lot 268091 | 14 avril | 14 avril |
| Nouveaux lots 268967 achevés, UN | 107 800 | 107 800 |
| Première sortie d'un nouveau lot 268967 | 15 avril | 19 avril |
| Demande réelle servie simulée, UN | 1 809 946 | 1 809 946 |
| Retard client en fin de fenêtre, UN | 36 686 | 36 686 |

**Limite décisive : le mensuel a été arrêté par la garde mémoire en fin
d'exécution.** Les exports centraux couvrent les 135 jours et leurs identités
sont contre-vérifiées ; cinq diagnostics F3 de fin manquent. Ces résultats sont
**descriptifs et exploratoires**, sans réussite du processus mensuel ni
qualification globale. Le témoin dispose d'une réception corrigée après une
erreur de nom d'export dans le superviseur ; aucun calcul n'a été réexécuté
pour corriger cette réception. Les refus initiaux restent conservés.

Sur les semaines complètes connues du proxy industriel :

| Production physique, ordres initiaux compris | Biais de volume hebdo → mensuel | Écart hebdomadaire cumulé hebdo → mensuel |
|---|---:|---:|
| 268091, 18 semaines | +10,51 % → +15,90 % | 76,63 % → 68,90 % |
| 268967, 11 semaines connues, 7 exclues | −63,55 % → −63,55 % | 87,81 % → 87,81 % |

L'écart hebdomadaire cumulé additionne les différences de quantité entre
simulation et proxy, prises positives, puis divise par le volume du proxy et
multiplie par 100. Il mélange écarts de volume et de calendrier. Pour 268091,
il diminue mais le surplus global augmente : aucun gain uniforme n'est établi.
Ces pourcentages ne sont pas les erreurs **annuelles** affichées par Mines Albi.

Le champ `executed_qty` mesure le travail dans l'encours, pas nécessairement
les produits finis achevés ce jour-là. Le témoin exécute 22 363,235672 équivalents
le 24 avril, puis 6 436,764328 le 28 avril : le lot physique de 28 800 UN apparaît
seulement le 28 avril. Les bilans quotidiens d'encours sont contrôlés ; aucune
valeur source n'est arrondie pour masquer un échec. Les vues de fabrication
utilisent les événements de lots achevés. `released_qty` inclut les nouveaux
lots immédiatement utilisables et les libérations qualité ; ces dernières
sont identifiées séparément par leurs événements dédiés.

Les plans PF changent dès J0, mais les dernières propositions à J59 visent
avril pour 268091 et mai pour 268967. Une proposition révisable n'est pas un
ordre exécuté. Les essais annuels, distincts, n'ont pas abouti ; leurs décisions
et leurs arrêts sont conservés dans les preuves. Ils ne fournissent aucune
validation annuelle de la nouvelle règle.

La demande client historique hebdomadaire est conservée et répartie par jour
sur les 365 jours de 2025 ; il ne s'agit pas de 365 mesures journalières. La borne
J362 de la référence concerne aussi d'autres usages : aux trois derniers jours,
les observations fournies restent prioritaires, les absences utilisent un profil
reconduit déclaré. L'année ne doit donc pas être décrite comme entièrement
observée pour tous les flux industriels.

La première préparation annuelle a été refusée avant J0 : le graphe court ne
contenait pas le profil d'autres usages exigé par le runner après J362. L'échec
et son journal sont conservés dans `runner/annual365/weekly/`. Une préparation
longue distincte utilise la fonction officielle `current_reference.prepare_graph`.
Les adaptations prospectives de prévision et de calendrier sont déclarées et
partagées par les deux cas annuels ; les plans annuels ne sont pas assimilés aux
plans du pilote court.

Les adaptations historiques de la référence restent également actives, dont
`legacy_residual` et la protection hebdomadaire des usages partagés. Cette
comparaison isole une règle au sein de ce modèle de rapprochement historique ;
elle ne constitue pas un rejeu industriel autonome. Les bilans et les calculs
indépendants ne suffisent pas à certifier une capacité machine ou une cause réelle.

La famille des mouvements Scan3 sert au proxy et à certaines réconciliations
historiques. Cependant, la contre-revue du F3 hebdomadaire complet ne trouve
**aucun budget actif pour 338929/M1810 ou 333362/M1430** : aucune réinjection
directe des deux cellules de proxy n'est démontrée ici. Les diagnostics F3
mensuels manquent ; cette vérification n'est pas réussie pour ce cas. Stocks,
ordres initiaux et nomenclatures restent des sources communes. Une ressemblance
ne suffit donc pas à prouver une calibration industrielle indépendante.

## Vérifications et limites

- 16 cas ciblés passent, sans cas ignoré, dont les régressions hebdomadaires.
- 59 contrôles indépendants en mémoire et 8 780 contrôles bornés sur les CSV
  des deux calculs courts passent, avec reconstruction depuis les prévisions
  source et la demande réelle.
- 20 622 comparaisons bornées passent sur les exports 135 jours : budgets connus
  à la décision, demande et initialisations identiques, bilans clients, stocks et
  encours, unités physiques entières. Ce sont des contrôles de données, pas
  20 622 tests pytest ni une réussite du processus arrêté.
- La qualification globale des deux calculs courts est **refusée** sur les
  mêmes six groupes : disponibilité interne orpheline, deux déclarations du
  mode Scan3, cohérence événements/besoins externes, demande externe connue et
  absence de l'audit automatique des parcours de lots. Elle n'est pas validée
  par les contrôles ciblés et ne permet aucune promotion de référence.
- L'audit automatique des parcours de lots et le navigateur ne sont pas exécutés.
  Les cartes nominale et cascades antérieures sont conservées.
- La qualification du témoin 135 jours reste refusée sur six groupes. Celle du
  mensuel reste refusée sur huit groupes, dont des diagnostics F3 absents et
  leurs conséquences sur la provenance. Les contre-calculs ciblés ne les effacent pas.

L'ancien nominal `cc20261109/nominal`, terminé sur 1 825 jours, est présenté
séparément pour son année 2025. Code, graphe, graine et certains contrats diffèrent :
il n'est pas le témoin du nouveau mensuel et ne permet pas d'en mesurer l'effet.

| Ancien nominal 2025 | Total annuel simulé, UN | Simulation / proxy sur semaines connues, UN | Biais sur ces seules semaines |
|---|---:|---:|---:|
| 268091, 46 semaines | 4 825 715 | 4 796 915 / 5 016 700 | −4,38 % |
| 268967, 36 semaines | 1 509 200 | 970 200 / 1 263 850 | −23,23 % |

Les semaines absentes peuvent changer fortement le jugement : il est incorrect
de diviser notre total annuel par un total industriel partiel. Même le −4,38 %
ne peut pas être classé directement face au −4 % annuel rapporté par Mines Albi.

L'essai annuel préparé a atteint la garde
de mémoire disponible après environ 18 minutes, dernier jalon J240 ; il est
**incomplet**, sans résultat annuel exploitable, et son mensuel n'a pas été lancé.
L'arrêt et les partiels sont conservés, sans abaisser les seuils ni relancer
l'année. Une paire distincte de 135 jours répond à la question plus courte des
premières fabrications proposées pour avril/mai. Elle reprend le graphe court
du pilote ; ses plans sont comparés entre ses deux cas, pas au témoin annuel arrêté.

Les horizons figés, la capacité machine de 268967
et les délais conditionnels de 338929 restent des questions distinctes ; aucun
réglage arbitraire de ces paramètres n'est introduit dans cette comparaison.

## Preuves et suite

- [Tests ciblés, 16 cas sans cas ignoré](../../artifacts/testing/mensuel_mines_albi_20261113/engine/toolbox/tests-16e5fe4123784832a6a8b74069d4b37a/manifest.json).
- [Contre-revue des exports 135 jours](../../artifacts/testing/mensuel_mines_albi_20261113/validator/native135_partial_manifest.json),
  [comparaison des semaines connues](../../artifacts/testing/mensuel_mines_albi_20261113/validator/proxy135_independent_review.json)
  et [contrat travail/produits finis](../../artifacts/testing/mensuel_mines_albi_20261113/production_measurement_decision.json).
- [Qualification 135 jours, témoin refusé](../../artifacts/testing/mensuel_mines_albi_20261113/qualification135_weekly/qualify-9d695fad4a8e49f7b7a6a9392fe4df04/manifest.json)
  et [mensuel refusé](../../artifacts/testing/mensuel_mines_albi_20261113/qualification135_monthly/qualify-4de92329d3f54b11ace157db0676277b/manifest.json).

Priorité suivante : rapprocher, pour 268967, le programme initial réellement
engagé et les stocks utilisables avant les premières fabrications ; quantifier
ensuite la capacité machine rapportée par l'industriel. Le déficit précoce n'est
pas résolu par la seule consommation mensuelle. La complétion des diagnostics de
fin doit devenir moins gourmande en mémoire avant un nouveau test annuel.
