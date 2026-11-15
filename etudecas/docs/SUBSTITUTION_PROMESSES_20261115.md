# Promesses de fabrication et composants de remplacement

Cette correction prolonge l'[étude de production](PRODUCTION_REALISTE_20261115.md)
sans modifier ses archives. Point de départ : `85c5f3f0d`, branche `dev_P0001`.

## Défaut et correction

Dans la première campagne de 268967, au 23 mars 2025 (J81), il reste 53 900
unités à fabriquer. À 7 700 unités par jour, la fin attendue est le 30 mars
(J88). L'exécution dispose du composant de remplacement EX-344135, mais le MRP
attendait la disponibilité de 344135 le 3 avril (J92) pour annoncer cette fin.
Le contrôle qualité du dépôt est un événement distinct.

La correction affecte le besoin restant au stock de remplacement utilisable,
dans les seules conditions déjà autorisées par l'exécution. Elle conserve la
matière, partage le stock disponible entre campagnes et maintient un crédit
unique de 107 800 produits finis. Un manque de substitut reste un besoin du
composant principal ; aucun achat d'ancienne référence n'est inventé.

Le mécanisme s'applique aux références configurées, sans exception de code
pour 268967 ou 344135. Les cas incertains restent prudents : arrivée du
principal avant la fin, autorisation expirante, unité différente ou stock
ancien déjà protégé par un autre usage. Les refus sont tracés.

## Vérification du défaut dans le moteur complet

Les deux nouveaux calculs se terminent avec un code retour nul, en 368,16
secondes pour le témoin et 464,59 secondes pour la variante. Les graphes sont
identiques octet pour octet à ceux de l'étude précédente ; les arguments ne
diffèrent que par leurs chemins d'entrée et de sortie.

Au 23 mars, dans les deux calculs réseau de la journée, la variante affecte
53 900 unités au stock ancien et zéro au composant principal pour le travail
restant. Le crédit fini reste unique, de 107 800 unités, désormais promis au
30 mars. La seconde campagne, qui dispose du composant principal, garde sa
promesse J116 au jour J109. La correction atteint donc effectivement le
moteur complet et ne se limite pas au cas de test en mémoire.

51 cas ciblés passent sur le code final, complétés par 82 assertions
indépendantes regroupées en six familles de cas. Les 662 sources sont stables.
Ces contrôles portent sur les quantités, dates, affectations et absence de
double débit ; ils ne valident pas les hypothèses industrielles de capacité.

La première paire de calculs a été interrompue volontairement après 125
secondes : une nouvelle trace nommait « matin » un calcul réalisé après la
fabrication. L'étiquette est corrigée en `evening_plan`, puis les tests et les
deux calculs ont été refaits dans de nouveaux dossiers. Les résultats
interrompus ne figurent dans aucune courbe.

## Effet sur la production et les clients

Le rapprochement indépendant des CSV retrouve **les mêmes séries quotidiennes
avant et après correction** pour les deux produits : travail exécuté, étuis
consommés, lots achevés, encours, stocks du dépôt, expéditions et arrivées client.
Ce constat vaut séparément pour le témoin et pour la variante de programme.

| Variante avec programme usine requis | Avant | Après |
|---|---:|---:|
| 268967 : volume sur 11 semaines connues, UN | 215 600 | 215 600 |
| 268967 : erreur hebdomadaire moyenne, UN | 8 131,82 | 8 131,82 |
| 268091 : volume sur 18 semaines connues, UN | 2 351 136 | 2 351 136 |
| 268091 : erreur hebdomadaire moyenne, UN | 81 971,67 | 81 971,67 |

L'erreur hebdomadaire est la moyenne des distances entre quantités simulées
et quantités estimées depuis les étuis, sans compensation des excès et des
manques. Une semaine absente reste inconnue. Le gain de 58,5 % sur l'erreur de
268967 obtenu dans l'étude précédente est conservé ; cette correction ne
produit pas un gain supplémentaire de fabrication sur les 135 jours étudiés.

Le mécanisme est bien actif : la planification utilise maintenant le même
composant disponible que l'exécution, dont le prélèvement était déjà correct.
Le défaut corrigé portait sur les besoins planifiés et la date promise ; il
n'explique pas le volume encore manquant par rapport aux observations.

Un effet amont est cependant mesuré pour le composant 344135 à 1430 :

| Achats et stock du composant | Avant | Après |
|---|---:|---:|
| Nombre de commandes simulées | 4 | 3 |
| Quantité totale commandée, UN | 600 000 | 600 000 |
| Stock physique final, UN | 372 200 | 372 200 |

Une tranche de 120 000 unités, auparavant reçue le 23 avril et utilisable le
29 avril, est regroupée avec la livraison du 5 mai, utilisable le 9 mai.
Le stock physique baisse donc de 120 000 unités du 23 avril au 4 mai inclus ;
le stock utilisable baisse de la même quantité du 29 avril au 8 mai inclus.
Cela représente **1 440 000 unités-jours de stockage physique en moins**
(120 000 unités pendant douze jours), sans perte de production observée dans
l'essai. Aucune économie monétaire n'est revendiquée. Les consommations
complémentaires reconstruites et les provenances ne changent pas.

Ce résultat est confirmé par onze contrôles de `upstream_delta_release.json`.
Il corrige l'hypothèse exploratoire d'une identité de tous les CSV : les séries
des deux produits finis sont identiques, mais certains achats et stocks de
composants changent. Le refus de cette hypothèse trop large est conservé dans
les preuves du lecteur indépendant.

## Essai décidé avant calcul

Les graphes, demandes, stocks initiaux, programmes, capacités et paramètres
sont strictement ceux des deux calculs de 135 jours de l'étude précédente.
Seul le code de planification des substitutions change. Les comparaisons
avant/après portent séparément sur le témoin nominal et sur la variante avec
programme usine requis. Aucun ajustement à la production réelle n'est ajouté.

Les critères sont : promesse J81 corrigée de J92 à J88, quantité de lot
inchangée, aucune double affectation ni achat fictif, puis mesure des effets
sur les deux produits, les stocks, les achats et le service client. Les
protocoles et résultats sont conservés sous
`etudecas/artifacts/testing/substitution_promesses_20261115/`.

## Portée

Cette correction concerne la cohérence entre planification et exécution.
Le stock initial de 107 800 unités de l'ancienne référence reste une hypothèse
nominale déclarée. La capacité de 7 700 unités par jour et les budgets MRP
utilisés comme autorisations restent des hypothèses de l'étude ; aucun ordre
ferme industriel n'est identifié par cette correction.

La projection des substitutions changeant de politique pendant la campagne,
l'ordonnancement détaillé après une pénurie et la validation industrielle de
la cadence ne sont pas résolus par cette modification. La référence n'est
pas remplacée par la variante expérimentale. Les contrôles navigateur, Node
et les tests d'altération de fichiers restent exclus.

Le partage du stock entre campagnes fixe un ordre de planification par
identité ; il ne réserve pas physiquement la matière et ne remplace pas
l'ordonnancement de l'atelier. Le cas industriel simulé n'a qu'une campagne
utilisatrice de ce substitut à la fois. Les tests de concurrence vérifient
la conservation du stock alloué, pas toutes les priorités physiques possibles.

## Livraison et preuves

Le [rapport interactif avant/après](../resultats/substitution_promesses_20261115.html)
permet de sélectionner une semaine, de suivre les composants affectés et de
distinguer promesse MRP, achèvement, réception et disponibilité après contrôle.
L'ancien rapport reste conservé.

Les deux qualifications globales restent refusées pour les mêmes cinq familles
que précédemment, avec les mêmes comptes : 1 disponibilité de transfert sans
origine, 288 contrôles de budget, 176/174 événements de provenance externe et
40 contrôles dans chacune des deux familles de base de consommation. Le
contrôle d'ensemble refuse donc la livraison comme qualification globale. Le
contrôle documentaire automatique signale toujours cinq registres générés à
revoir ; leurs empreintes ne sont pas réapprouvées automatiquement.

Dans `etudecas/artifacts/testing/substitution_promesses_20261115/` :

- `protocol.json`, `source_freeze_final.json`, `input_comparison.json` :
  intervention annoncée, sources et entrées comparables.
- `tests_release/tests-f6e25ff5409d4123879a9ae436e4463f/manifest.json` : 51 tests.
- `validator/memory_review_release.json` : 82 assertions, six familles.
- `validator/runtime_release_acceptance.json` : compatibilité du parcours natif.
- `validator/csv_core_release.json` : 79 contrôles indépendants des deux PF.
- `validator/upstream_delta_release.json` : effets achats et stocks composants.
- `final_manifest.json` : clôture, versions, refus et liens des preuves finales.

Les échecs de lecture intermédiaires sont conservés : sérialisation de clés
tuples, audit programme absent dans le témoin et rapprochement d'un lot
transporté par sa généalogie plutôt que par un identifiant identique. Ils ont
été corrigés dans les lecteurs, sans modifier les données simulées.
