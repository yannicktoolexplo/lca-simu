# Cascades de risques et lots — 12 novembre 2026

Suite : [reprise des cascades dépendant de l'état le 13 novembre](2026-11-13-cascades-dependantes-etat.md),
avec comparaison à quatre cas dans la même carte et limites de l'essai annuel.

La demande précisée est de retrouver les incidents **dans la carte complète et
ses deux suivis de lots existants**. L'intégration est livrée dans la
[carte nominale enrichie](../../resultats/campagne_complete_20261109/carte_nominale_reel_2025.html),
avec les lots propres aux trois scénarios de risques déjà calculés sur 56 jours.
L'explorateur des fichiers Excel reste de côté ; aucune nouvelle simulation
n'est nécessaire pour cette intégration.

Le parcours est **Risques simulés → scénario → lot exposé → Parcours
simplifié des lots ou Suivi de lots**. Les incidents sont dépliables dans la
fiche du lot et donnent accès aux expéditions concernées. Le retour au nominal
rétablit ses propres lots, graphiques et observations réelles de 2025.
Les numéros identiques de deux calculs ne désignent pas le même lot physique.

La [vue séparée des cascades](../../resultats/cascades_lots_20261112/cascades_et_lots.html)
reste un complément pour comparer les mécanismes. Elle distingue une expédition
existante exposée à un incident d'un départ empêché avant création d'expédition.
Dans ce dernier cas, ses boutons ouvrent explicitement les lots du témoin,
sans inventer de lot reçu dans le calcul perturbé.

## Calculs conservés et comparaison

Les calculs réutilisent la référence `coherent-MRP-20261014`, le moteur corrigé
du 12 novembre et la graine 42. Source applicative :
`236ab838600cdfaa1e1c1f8c01a3b6a175f0991555dec434bcc6c5cc00293946`.
Stocks, ordres initiaux, demande et règles MRP restent identiques ; les CSV
complets de matière et les deux journaux de lots sont activés.

| Cas | Risques ajoutés | Comparaison utile |
|---|---|---|
| A — nominal | Aucun | Référence sans risques |
| B — réactions selon l'état | Réactions natives, sans choc programmé | B/A : effet des réactions endogènes |
| C — libération interne | Neuf chocs du catalogue + réactions natives | C/B : portefeuille interne et réactions induites |
| D — distribution | Dix chocs du catalogue + réactions natives | D/B : portefeuille aval et réactions induites |

Les fenêtres originales du catalogue sont construites sur 362 jours, puis
seuls les débuts précédant J56 sont retenus. Aucun choc ultérieur n'est ramené
artificiellement à J55. Les dates de fin au-delà de la fenêtre restent déclarées.
Le catalogue est une hypothèse de stress existante, pas une panne industrielle
observée ni une loi de probabilité calibrée.

Les préfixes physiques de C/B jusqu'à J7 et D/B jusqu'à J17 sont identiques.
Comparer C/D à A reste possible pour le stress total, mais n'isole pas un
incident du portefeuille. Les identifiants `LOT-...` de deux calculs ne sont
jamais utilisés seuls pour prétendre à une même identité physique.

## Résultat C : disponibilité et taille du transfert

À J21, pour **773474 de Gaillac à Gien**, le MRP recommande 2 185 kg dans les
deux calculs. Le témoin expédie un lot de transfert simulé de 3 200 kg. Avec la
cascade, la disponibilité de la route est multipliée par 0,18 :

```text
Quantité accessible = stock utilisable avant décision × disponibilité de route
                     = 6 400 kg × 0,18 = 1 152 kg

1 152 kg < minimum simulé de transfert de 3 200 kg → départ exécuté : 0 kg
```

Le stock est utilisable avant décision, distinct du stock physique retenu.
La taille de 3 200 kg vient de la règle de transport simulée existante ; elle
n'est pas une nouvelle confirmation de taille de lot industriel. Cette
contrainte est suffisante pour empêcher le départ dans le portefeuille de
chocs ; elle n'isole pas l'effet causal de chaque multiplicateur pris séparément.

Les départs de **J21, J28 et J35**, 3 200 kg chacun dans le témoin, manquent
dans C. Le même lot source du témoin est prélevé trois fois ; trois départs
ne signifient pas trois lots sources distincts. Les lots reçus dans le témoin
restent des localisateurs de ce calcul, pas des lots reçus dans C.

Le MRP réagit aux non-livraisons : les recommandations de C deviennent
4 182 kg à J28 puis 7 239 kg à J35, contre 982 kg et 839 kg dans le témoin.
Les départs restent nuls. Au dernier jour, le stock utilisable de Gien est de
**4 283,070 kg contre 13 883,070 kg**, soit **9 600 kg de moins**.

Le service client reste identique. En revanche, le témoin ne fabrique aucun
PF 268967 à Gien pendant ces 56 jours : une production inchangée ne démontre
donc pas la résistance d'une fabrication active à ce manque. Les stocks de Muret
permettent encore les mêmes livraisons. Une fenêtre comprenant une fabrication
effective serait nécessaire pour éprouver cette propagation supplémentaire.

L'expédition est empêchée avant création de la transaction. Le registre
d'exposition est vide dans C : **aucun lien natif incident → lot reçu n'est
démontré**, et le contrôle exigeant une exposition non vide est refusé.
L'effet comparé sur les transferts et les stocks est vérifié séparément.

## Résultat D : lots expédiés mais retardés

Le registre relie nativement les incidents à **25 transactions**, avec
**239 408 unités** effectivement expédiées, aucun doublon de transaction et
aucune réception avant J56. Les indicateurs natifs donnent, pour les 25,
`departure_executed=1`, `arrival_executed=0`, `execution_status=in_transit`.
Elles sont réellement en transit, et non seulement réservées.

Ces expéditions proviennent de **deux lots partiellement exposés** :
124 208 unités expédiées sur un lot initial de 1 101 534 unités, et 115 200 sur
un lot de 126 795 unités. Une quantité expédiée exposée ne signifie donc pas
que tout le stock du lot est endommagé. Les incidents superposés sur une même
expédition ne multiplient jamais la quantité.

Les allocations aux lots sources sont réconciliées à 100 %. L'absence de lot
reçu et de généalogie de réception dans la fenêtre est attendue : les réceptions
prévues arrivent après l'horizon. Le taux technique 1,0 de couverture dans
l'horizon porte ici sur zéro réception attendue ; ce n'est pas une preuve de
réception accomplie. Aucune descendance future n'est inventée.

Pour **268967**, les quantités servies passent de **253 785 à 142 694 unités**
sur une demande de 266 902 unités, soit un service en quantité de **95,09 % à
53,46 %**. Cela représente **111 091 unités servies en moins** et autant de
backlog supplémentaire à la fin de la fenêtre. Ce n'est pas une perte définitive
ni du chiffre d'affaires perdu démontré. Le service de 268091 reste inchangé.

Le service en quantité est `somme servie / (nouvelle demande + backlog initial
compté une seule fois)` ; il ne mesure pas la ponctualité. Les 239 408 unités
en transit ne sont pas assimilées aux 111 091 unités de déficit de service.

## Vérifications et limites

Les preuves locales sont dans `etudecas/artifacts/testing/cascades_lots_20261112/` :
préparation appariée, commandes, manifestes des calculs, CSV complets, registres
d'impact, comparaison indépendante et construction HTML. Le point d'entrée de
la revue est `validator/manifest.json` ; la publication est liée par
`delivery_manifest.json`.

- Trois tests exacts de calcul en mémoire, sept oracles de suivi des lots et
  neuf oracles de comparaison ont été exécutés après lecture du périmètre.
- Lecteur ciblé : A 4 495 contrôles réussis ; B 4 641 contrôles réussis avec
  constat de 73 incidents mais aucun lien natif d'exposition ; D 4 501 contrôles
  réussis avec les 25 liens natifs. C conserve un refus sur 4 577 contrôles,
  dû à l'exposition native vide, sans le convertir en succès.
- La comparaison des quatre cas passe 52 contrôles ; 97 contrôles supplémentaires
  rapprochent les allocations du registre D des départs natifs par transaction
  et lot dans leur calcul. Les quantités ne s'additionnent jamais entre incidents
  superposés, ni entre grammes, mètres et unités.
- La qualification générale de A et D reste **refusée** : une disponibilité de
  transfert orpheline, 393 écarts du contrat de budget Scan3, 60 écarts de provenance
  d'événements externes, 14 écarts des champs de base Scan3 et 14 du périmètre
  SKU alternatif. Ces réserves ne sont pas levées par les contrôles ciblés.

Le quatrième calcul initial s'est arrêté sur le garde mémoire disponible.
Son dossier partiel reste conservé. Un nouvel essai D, dans un autre dossier,
emploie le même JSON minifié : **contenu et métadonnées identiques**, empreinte
canonique vérifiée, 99,2 Mo ramenés à 71,5 Mo. Un départ conditionné à 2 Gio de
RAM libre et les mêmes gardes de fonctionnement ont permis sa terminaison à
704 Mo de pic échantillonné. Le bilan est donc **cinq tentatives, quatre calculs
complets et un partiel**, pas cinq succès ni une reprise silencieuse du partiel.

Le compteur d'applications de l'UI a été corrigé après une revue indépendante :
les CSV séparent les identifiants par virgules, tandis que certains registres
utilisent `|` ou `;`. Les trois séparateurs sont maintenant acceptés et testés,
avec déduplication. Les premières candidates refusées restent conservées.
Deux manifestes homonymes existent par calcul : celui à la racine et celui
du package `run/run_manifest.json`. Les empreintes sont vérifiées sur le chemin
explicitement déclaré, sans supposer qu'il s'agit du même fichier.

Les vérifications d'interactions utilisent V8 et un DOM simulé. Le navigateur,
Node et Word restent non exécutés après les refus de sécurité antérieurs non
levés. Une qualification technique ciblée ne constitue ni calibration
industrielle ni promotion du nominal.

La candidate finale V6 passe 184 540 contrôles statiques indépendants, 48
contrôles de provenance aux chemins exacts, 36 contrôles V8 de navigation,
neuf contrôles de parsing/comptage et 18 contrôles de liaison HTML/sources.
Les refus des premières candidates sont conservés. Empreinte de la page
publiée, identique à cette candidate :
`c59d8a57752fa3da804b6c3e691b4aec759bb23267b94d6f885f854dfdeeb31e`.
Empreinte de la première intégration, avec le seul lien de navigation ajouté :
`2187fdd0bcc35f8d7e2ae1dabf36c7abcbb920d046c97597c1add20f46d8500a`.
L'ancienne version complète de cette carte est conservée sous
`cascades_lots_20261112/previous_nominal_map.html`.

## Incidents dans les deux suivis existants

Les preuves de cette intégration sont regroupées dans
`etudecas/artifacts/testing/carte_risques_lots_20261112/` : protocole,
construction des contextes, patch HTML reproductible et revue indépendante.
Le refus de la première candidate est conservé : le second lot exposé n'était
pas ouvrable dans le suivi classique, l'export omettait les incidents et
l'identité calculée pendant un changement de scénario pouvait être mélangée.
Les manifestes et empreintes des versions intermédiaires restent disponibles ;
leurs HTML ont été supprimés pour limiter le stockage, après remplacement par
la candidate finale. La carte antérieure livrée est archivée avant intégration.

Ce second lot vient d'un ordre de production initial en cours. Son type de
création n'entre pas dans le filtre historique de sélection et son modèle
d'affichage n'était pas précalculé. La vue de repli conserve ses quatre
événements natifs : création et blocage à J41, libération et départ à J55.
Les 115 200 unités partent ; 11 595 restent dans cette occurrence. L'arrivée
à J99 reste prévue et hors des 56 jours observés. Aucun descendant reçu ni
consommation amont manquante ne sont inventés. L'élargissement du filtre
applicatif général reste à traiter après le gel des sources.

Les contextes de lots, caches de parcours, sélections et dates sont séparés
entre calculs. Leurs fiches distinguent les expéditions effectuées des arrivées
prévues. Les effets connus d'une expédition viennent de son enregistrement
natif : par exemple, 44 jours de transport, dont 42 jours supplémentaires,
et un multiplicateur de coût de transport de 4. Il s'agit des effets combinés
appliqués à l'expédition, sans les attribuer isolément à chaque incident.
Le scénario interne garde un index d'exposition vide : les transferts bloqués
avant création d'expédition ne deviennent pas de faux lots exposés.

La V3 finale a passé **73 contrôles CSV indépendants, cinq contrôles statiques
et 43 contrôles JavaScript en V8**, ainsi que doctor. La revue exécute les
vraies fonctions de sélection et d'ouverture avec un DOM simulé : elle couvre
le bon lot dans les deux suivis, les expéditions, les filtres, la limite J55,
les exports et le parcours D → nominal → C → D. Les quatre caches sont
réinitialisés ; un changement de contexte pendant un export est refusé.
Les 48 blocs compressés d'origine restent strictement identiques. L'horizon
nominal de 1 825 jours reste distinct des calculs de risques de 56 jours.

Le [manifeste indépendant](../../artifacts/testing/carte_risques_lots_20261112/validator/manifest.json)
autorise cette livraison exploratoire ; le
[manifeste de livraison](../../artifacts/testing/carte_risques_lots_20261112/delivery_manifest.json)
relie la candidate, la carte effectivement écrite et son archive. Empreinte
finale : `6e50ae9ee78b90131e080f97cfc325088359ada37ef35172d3a451e1dfc37a8e`.
La carte précédente complète est conservée dans
`carte_risques_lots_20261112/previous_nominal_map.html` ; le code applicatif
garde l'empreinte `236ab838600cdfaa1e1c1f8c01a3b6a175f0991555dec434bcc6c5cc00293946`.

Le gate formel reste **refusé**, faute de preuve `browser` et de qualification
globale correspondant à cette carte. Il est conservé sous
`toolbox/gate-0bc033b345d149779537516a0f7fc30d/manifest.json` dans les preuves
de l'intégration. Aucun navigateur n'est relancé après les refus de sécurité
antérieurs. Les mocks ne certifient ni mise en page ni téléchargement réel.
Les refus globaux A/D et d'exposition non vide C restent explicitement ouverts ;
aucune nouvelle référence ni calibration industrielle n'est promue.

## Suite prioritaire

Conserver ces deux mécanismes et compléter la traçabilité de la branche MRP
datée des approvisionnements externes agrégés avant de généraliser aux cascades
amont. Le code y applique certaines perturbations aux promesses sans transmettre
tous les identifiants aux lots ; il force aussi à zéro la durée de qualité de
cette branche. Un rapprochement historique reconstruit ne doit pas devenir
une exposition native déclarée.

Ensuite, choisir une fenêtre contenant réellement fabrication et réception
affectées pour éprouver la cascade interne jusqu'au PF. Les grands délais
programmés et les stocks tampons justifient ce choix, mais aucune simulation
longue supplémentaire n'est lancée sans nouvelle question et budget définis.
Le noyau applicatif reste gelé pendant l'étude annuelle de sensibilité active ;
les nouveaux contrôleurs et vues sont conservés localement sous artefacts.
