# Consommation mensuelle et comparaison des productions

Travail du 13 novembre 2026, sur `dev_yannick`, à partir du commit `6fcb2ba0c`.
Les preuves sont conservées dans
`etudecas/artifacts/testing/mensuel_mines_albi_20261113/`.

Le [rapport interactif](../../resultats/comparaison_production_mensuelle_mines_albi_20261113.html)
sépare l'essai mensuel exploratoire du nominal annuel antérieurement publié.
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

### Comparaison visuelle avec les courbes photographiées

Le [comparatif enrichi des photos](../../resultats/comparaison_production_avec_photos_mines_albi_20261113.html)
ajoute un troisième onglet aux deux vues précédentes. Il superpose nos cumuls
physiques journaliers à **18 jalons approximatifs** lus dans les captures :
production estimée à partir des étuis en noir, simulation Mines Albi v2c en
orange, et dernier point de la série intitulée « Entrées à D1920 » en gris,
dans une vue séparée. Le sens de ce dernier flux reste non qualifié ici.

Chaque lecture possède une plage de quantité et une fenêtre de dates. Ces
plages décrivent l'incertitude d'une lecture manuelle, pas un intervalle de
confiance statistique. Il n'y a ni fichier image local étalonné en pixels, ni
série CSV Mines Albi ; les traits éventuels entre jalons servent seulement
de guides. Le dernier point visible n'est pas placé arbitrairement au
31 décembre et aucun plateau n'est prolongé après ce point.

Pour **268967**, le défaut de calendrier ressort dans les deux modèles.
Notre ancien nominal est à 0,22 million au repère du 30 juin, contre une
lecture d'environ 0,20–0,25 million pour Mines Albi et 0,45–0,70 million pour
la production estimée sur la photo. Au repère du 30 septembre, notre nominal
est à 1,19 million, contre environ 0,65–0,90 pour Mines Albi et 0,80–1,00 pour
la production estimée. Les dates photographiées sont incertaines d'environ
deux semaines : le tableau présente aussi la plage de notre cumul sur toute
cette fenêtre. Les modèles produisent peu au début puis rattrapent fortement ;
un volume final seul ne permet pas de valider le calendrier.

Pour **268091**, Mines Albi prend beaucoup d'avance au premier trimestre,
puis la production estimée le rattrape. Notre nominal est proche de cette
estimation au milieu de l'année, mais reste plus bas au dernier point visible.
Ce constat est visuel et descriptif, sans classement statistique des modèles.

L'année complète de notre courbe provient toujours de l'**ancien nominal**.
Les nouveaux essais hebdomadaire et mensuel restent arrêtés au 15 mai ; leurs
valeurs sont inconnues après cette date, sans ligne horizontale artificielle.
Aucun calcul de simulation ni aucun paramètre MRP n'est changé pour ajuster
les courbes à la photographie. Les preuves de cette extension sont sous
`artifacts/testing/comparaison_photos_mines_20261113/`.

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
