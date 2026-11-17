# Production : prochaines pistes vérifiées le 17 novembre 2026

La priorité est de tester la protection des composants d'un lot déjà engagé,
puis son lancement selon les dates de disponibilité. Les calculs locaux
soutiennent ces pistes ; leur bénéfice sur toute la chaîne reste à mesurer.
Le moteur, la référence et les comparaisons HTML sont conservés.

## Périmètre et preuves

Étude sur `dev_yannick`, code `b0280a613`, référence
`coherent-MRP-20261014`. Lecture des trois essais de 152 jours déjà qualifiés :
A = témoin avec programme figé ; B = calendrier lundi–vendredi à 1430 ;
C = B avec carnet initial hypothétique. Les horizons figés restent de quatre
semaines à 1810 et huit à 1430. Priorité au PF 268967, contrôle du PF 268091.

Le [manifeste local](../../artifacts/testing/pistes_mrp_20261117/final_manifest.json)
relie les calculs, sources et contre-vérifications.
Le [protocole des prochains essais](../../artifacts/testing/pistes_mrp_20261117/next_experiments.json)
fixe interventions, critères et budgets. Aucune nouvelle simulation complète
n'a été exécutée pour cette préparation.

## 1. Préserver de quoi terminer un lot engagé

**Constat dans A.** Le 11 mai, après fabrication, il reste 3 281 699 unités
utilisables du composant 042342. Un prélèvement résiduel reconstruit les absorbe
toutes. Il aurait suffi d'en conserver **464 633** pour terminer le lot de
**107 800 produits finis** le 12 mai, au lieu du 22 mai. Les sept autres
composants et la capacité du 12 mai suffisent dans ce calcul local.

Le prélèvement concurrent n'est pas une consommation industrielle identifiée :
il complète une quantité hebdomadaire observée après déduction des
consommations propres simulées. Sa provenance est
`reconstructed_scan3_residual_not_identified_other_format`. Il faut conserver
cette distinction même si un libellé de journal parle d'« autres usages observés ».

**Compromis mesuré.** Protéger le lot laisserait **555 500 unités** de besoins
résiduels en attente, contre 90 867 dans le témoin. Le besoin concurrent n'est
donc pas effacé : 464 633 unités changent de priorité. Les 30 millions d'unités
physiquement présentes mais encore en contrôle ne deviennent pas utilisables
plus tôt. La réservation matière actuellement exportée est un besoin planifié,
pas une protection du stock physique contre ce prélèvement.
Cet essai reste un diagnostic historique : le résidu dépend du réalisé simulé
et d'une quantité industrielle observée. Il ne constitue pas, à lui seul, une
demande autonome des autres utilisateurs pour le nominal prospectif.

**Prochain essai.** Ajouter une règle commune facultative protégeant le reste
nécessaire aux lots actifs, sans exception par article. Comparer au témoin à
prévisions, stocks, quantités et délais identiques. Suivre la fin du lot, les
autres besoins différés, les stocks et les livraisons. Arrêter si un besoin
disparaît, si une réserve est comptée deux fois ou si le gain exige du stock
encore en contrôle. Vérifier le report du résidu entre semaines : le simple
report à la fin d'une journée ne suffit pas.

Preuves : [calcul local](../../artifacts/testing/pistes_mrp_20261117/allocation/local_allocation_result.json),
[contre-vérification indépendante](../../artifacts/testing/pistes_mrp_20261117/validator/allocation_review.json).
Les dix jours gagnés concernent une fin de fabrication hypothétique ; aucun
gain client n'est démontré.

## 2. Lancer selon les réceptions utilisables prévues

Dans B et C, les interruptions examinées viennent d'un manque de composant
avant sa libération, sans prélèvement concurrent pendant la pause. Sur un cas
à un composant contraignant, décaler le lancement évite la pause sans déplacer
la fin. Attendre tous les composants avant de commencer retarde au contraire
la fin du lot.

| Cas | Lancement actuel → fin | Lancement aligné → fin | Attente de tous les composants → fin |
| --- | --- | --- | --- |
| B | 28 avril → 20 mai | 1er mai → 20 mai | 9 mai → 28 mai |
| C | 17 avril → 9 mai | 22 avril → 9 mai | 8 mai → 27 mai |

Ces dates utilisent le calendrier expérimental lundi–vendredi, sans fermeture
supplémentaire pour jours fériés. Les sept autres composants sont supposés
disponibles dans ces deux petits cas. Avant toute règle prospective, il faut
vérifier les huit composants, leurs usages concurrents et surtout que la date
de réception/libération était connue au lancement. Une date constatée après
coup ne peut pas justifier la décision.

Preuves : [trajectoires calculées](../../artifacts/testing/pistes_mrp_20261117/allocation/bc_dated_coverage_result.json)
et contre-vérification ci-dessus. Pas de gain aval établi.

## 3. Vérifier ce que date la production « réelle »

La production comparée est estimée par des retraits d'étuis. La date source,
repérée un dimanche et rattachée au lundi suivant selon la convention
existante, ne prouve pas le jour de fabrication physique.

Sur le bloc fixé **du 31 mars au 27 avril**, les données renseignées représentent
**171 000 unités**, contre **154 000** possibles à 7 700 unités/jour pendant
quatre semaines de cinq jours. Répartir autrement les retraits à l'intérieur
du bloc ne résout pas cet écart. Il manque le calendrier réel, les heures machine
allouées et le lien entre dates de fabrication, prélèvement et saisie.
Les 154 000 unités sont la borne de notre hypothèse, pas une capacité
industrielle mesurée.

L'agrégation peut aussi masquer les écarts : sur les mêmes huit semaines
observées, l'erreur hebdomadaire moyenne de C est supérieure à celle de B
(36 649 contre 34 724 unités), alors que les erreurs sur deux blocs de quatre
semaines diminuent (19 325 contre 34 725 unités par bloc). Des avances et retards
s'annulent. Seuls **deux blocs sur cinq** sont entièrement renseignés pour
268967 ; ce résultat ne valide pas C sur l'année.

Pour 268091, les vingt semaines complètes sont renseignées : les trois essais
produisent 2 867 315 unités contre 2 350 700 estimées, soit **516 615 de plus**.
Le changement de calendrier à 1430 n'explique pas cet écart.

Preuves : [sources et capacité](../../artifacts/testing/pistes_mrp_20261117/measurement/measurement.json),
[effet séparé du choix des semaines et de l'agrégation](../../artifacts/testing/pistes_mrp_20261117/measurement/mask_aggregation_review.json).
Les ratios de formats et la nomenclature ne sont pas modifiés.

## Explications examinées, sans correction justifiée à ce stade

- **Double comptage initial : non identifié dans le calcul vérifié.** Au
  démarrage, 2 464 228 unités de besoins projetés du dépôt + 159 109 de
  protection finale − 1 101 534 disponibles à Muret donnent 1 521 803 unités
  nettes. La lotification usine donne quinze lots, soit 1 617 000 unités.
  Ces lots couvrent l'horizon annuel, pas une fabrication immédiate.
- **Prévisions figées toute l'année : réfuté.** Les versions connues sont
  actualisées ; le budget du mois est fixé à son ouverture puis consommé
  chaque semaine par la demande réelle devenue connue. Sur vingt semaines,
  la prévision brute connue au démarrage dépasse le réel ultérieur de
  **45,89 %**. Cela explique une pression initiale, sans prouver que toutes
  les prévisions ultérieures restent aussi élevées. Les engagements figés
  peuvent survivre aux révisions.
- **Anticipation due aux besoins lointains : démontrée dans le placement.**
  À lots proches identiques, davantage de charge future avance leur placement.
  Un petit cas montre le compromis : éviter 16 unités-jours de stockage
  ajoute huit jours de retard à un besoin lointain. Supprimer des besoins
  futurs pour rapprocher une courbe retirerait des obligations au modèle.
  Ce petit cas impose l'ordre des campagnes, sans entrelacement ; il ne
  démontre pas l'optimalité générale de l'ordonnancement.

Preuves : [calcul net indépendant](../../artifacts/testing/pistes_mrp_20261117/validator/j0_netting_review.json),
[versions et provenance](../../artifacts/testing/pistes_mrp_20261117/observations_explorer.json),
[placement indépendant](../../artifacts/testing/pistes_mrp_20261117/validator/calendar_review.json).
La sécurité active de 268967 reste de 25 jours ouvrés.

## Vérification et point de reprise

117 contrôles sur les petits cas de placement ; contre-vérifications
indépendantes : 1 539 contrôles de placement, 24 de calcul net initial et
1 396 d'allocation. Les analyses de sources et d'agrégation ont été exécutées
avec succès. Ce sont des contrôles de calcul et de provenance, pas une
validation de causalité industrielle. Un premier script local a échoué avant
calcul sur un type de chemin ; l'échec est conservé et exclu des réussites.

Le contrôle documentaire global reste distinct : cinq registres déjà périmés
empêchent sa validation. Aucun test de modification volontaire de fichiers,
aucune suite globale ni vérification navigateur n'a été exécuté.

**Reprise :** implémenter et contre-valider d'abord la protection des composants
engagés ; seulement ensuite lancer la paire courte prévue. Mesurer ensemble
gain de fabrication et dégradation des autres besoins. Ne promouvoir aucune
variante avant cette comparaison. Lancer ensuite le cas de couverture datée
avec connaissance vérifiée des réceptions. Conserver les courbes existantes.
