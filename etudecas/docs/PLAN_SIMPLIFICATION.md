# Simplifier Etudecas pour pouvoir le maîtriser

Décision du 25 septembre 2026 : garder les fonctionnalités et **un parcours courant
par type d'étude**. Les anciennes commandes ponctuelles et présentations intermédiaires
peuvent quitter le code actif après contrôle de leurs dépendances et sauvegarde.

Le parcours à comprendre est :

**Données → scénario → boucle quotidienne → lots et transports → indicateurs → carte.**

Une étude appelle ce même parcours avec plusieurs paramètres ou tirages explicites.
Elle ne doit pas exiger d'apprendre toutes les versions et étapes historiques.

## Cible : environ 50 fichiers de code

L'enveloppe proposée compte les Python, initialisations, tests et interface JS/CSS.
Les données industrielles, configurations, documentation et quatre HTML livrés restent
des fichiers distincts. Ce budget est une cible de refonte, pas un résultat déjà acquis.

| Responsabilité | Budget |
|---|---:|
| Entrée centrale et initialisation racine | 2 |
| Données : sources, graphe, schéma, configuration | 4 |
| Simulation : état et boucle, planification, flux, lots, transports | 5 |
| Études : exécution, sensibilité, incertitude, fournisseurs, cascades | 5 |
| Recherche courante : calibration, campagnes, commande, fréquence | 4 |
| Résultats : stockage, indicateurs, carte, publication | 4 |
| Vérification numérique, navigateur, documentation automatique | 3 |
| Tests regroupés par capacité | 12 |
| Initialisations des sous-paquets | 5 |
| Interface : réseau, courbes et deux suivis de lots | 4 JS + 1 CSS |
| **Total proposé** | **49** |

Atteindre ce nombre en conservant des centaines de milliers de lignes dans quelques
fichiers géants ne satisferait pas l'objectif. Il faut retirer les étapes obsolètes,
partager les calculs répétés et transformer les variantes en paramètres lisibles.

## Travail concret engagé

Le point de départ de cette passe compte 596 Python et 476 623 lignes, tests compris.
Le dossier de recherche représente 312 Python et la majorité des lignes.

- Sortir les publications, moniteurs et relais historiques devenus inutiles au
  parcours courant, ainsi que leurs tests exclusifs.
- Retirer les investigations ponctuelles par article ; garder l'audit des commandes
  sources, le bilan des observations et les rapports génériques du pipeline.
- Mutualiser les calculs identiques des campagnes V2/V4 dans leur module commun.
- Utiliser `simulation.studies` comme entrée pour les études courantes et raccourcir
  les guides : les détails historiques restent dans les capsules et bilans datés.

La liste exacte, les nombres après intervention et les vérifications sont dans
[le bilan de cette passe](../artifacts/testing/human_code_20260925/BILAN.md).
L'[inventaire courant](INVENTAIRE_PYTHON.csv) décrit les fichiers actifs ; le
[tableau de correspondance](ARBORESCENCE_CIBLE.csv) conserve les anciens chemins,
leurs regroupements et les références de capsule pour les retraits.

## Ordre de refonte restant

La passe suivante, vérifiée, ramène le code de **528 à 518 fichiers Python** et
de **430 172 à 422 626 lignes**. Elle regroupe les contrats de sensibilité avec la génération de
scénarios, la découverte des résultats avec leur lecture, et les critères de
rejeu avec le classement. La sérialisation CSV est commune. Sept fichiers liés
aux anciennes campagnes 021081 et aux deux liaisons présélectionnées quittent
le parcours actif ; leurs sources restent dans la capsule `f2a5da…` et dans Git.
L'audit de leurs résultats devient une option du protocole de calibration.
Le calendrier FIFO estimé propre à cet ancien essai n'est pas remplacé à l'identique.
Le runner conserve son contrôle d'empreinte de l'artefact V2 ; sa généralisation
à de nouveaux plans reste une étape distincte.

Les mesures et contrôles de cette passe sont consignés dans le
[relevé de simplification](../artifacts/testing/simplification_suite_20260925/simplification.json).
La validation reste limitée aux contrôles effectivement enregistrés dans ce relevé.

1. **Études et campagnes** : un plan, une exécution commune, des calculs propres à
   chaque méthode et une publication. Remplacer les scripts par fournisseur,
   version ou étape par des profils explicites quand les contrats le permettent.
2. **Sensibilité et incertitude** : réunir l'exécution, la lecture et les synthèses
   communes ; conserver OAT, seuils, stress temporels, tirages Monte Carlo,
   appariement et propagation temporelle comme méthodes distinctes.
3. **Résultats et carte** : partager lecteurs, unités, séries et tableaux ; séparer
   les calculs métier du rendu. Préserver les deux interfaces de suivi de lots.
4. **Moteur** : rendre l'ordre quotidien lisible, avec état, planification, flux,
   registre physique et exports identifiables. Préserver les rétroactions et délais.
5. **Tests et documentation** : regrouper par capacité après retrait des usages
   obsolètes ; conserver les cas limites utiles et les oracles numériques indépendants.

### Tranche du 28 septembre 2026

La tranche vérifiée passe de **518 à 511 fichiers Python**, et de
**422 626 à 414 860 lignes**. Elle retire l'ancien lanceur et le finaliseur V2
et leurs deux tests exclusifs ; deux oracles de contrat et de classement sont
transférés aux tests V4. Le runner V2 reste nécessaire à la prévalidation et aux
preuves historiques. Aucune fenêtre, graine ou méthode de campagne ne change.

Le nommage des cas rejoint le plan de sensibilité dans `designs.py`. Les deux
utilitaires d'alias et de nettoyage collectif des anciens résultats quittent le
code actif ; les options de conservation des lanceurs courants restent disponibles.
Les sept sources retirées ou regroupées sont conservées dans la capsule `a99c4246…`.
Les [preuves de cette tranche](../artifacts/testing/simplification_campagnes_20260928/simplification.json)
distinguent les contrôles exécutés des limites restantes.

Vérifications : 25 tests ciblés, 3 082 comparaisons des identifiants en mémoire
et neuf valeurs attendues indépendantes ; quatre simulations de 1 825 jours,
124 exports identiques, 47 blocs de carte et cinq volets de diagnostic concordants,
197 contrôles de contenu et provenance, neuf contrôles de navigation et neuf
contrôles des lots. Les campagnes fournisseurs et les ensembles Monte Carlo
complets n'ont pas été rejoués ; les différences de méthode restent conservées.

### Regroupement des lecteurs et retrait des superviseurs historiques

La tranche suivante passe de **511 ? 503 fichiers Python**, et de
**414 860 ? 411 122 lignes** : 281 fichiers applicatifs, 201 fichiers de tests
(y compris leurs deux helpers) et 21 initialisations de paquets. Ces nombres
excluent les r?sultats, les cartes, les archives et la documentation.

- Le lecteur du paquet de r?sultats rejoint `run_format/schema.py`.
- Les r?gles canoniques de lots rejoignent `lot_policy/engine_adapter.py`.
- La d?couverte et la lecture des rejeux rejoignent `targeted_replay/sources.py`.
  Le contr?le des lots parcourt les six CSV une fois chacun, au lieu de onze
  lectures au total. Aucun gain de dur?e du moteur n?en est d?duit.
- Quatre superviseurs/publications historiques V5/V6 et un test exclusif sont
  retir?s ; les m?thodes scientifiques et les tests des adaptateurs utiles restent.

Les inventaires historiques V4 v1/v2/v3 restent lisibles ; les nouveaux plans
utilisent v4/40 et les empreintes actuelles. Un ancien plan incompatible reste
refus?. Les sources avant cette tranche sont dans la capsule `751eeb?`.
Les contr?les et leur ?tat r?el sont dans le
[relev? de cette tranche](../artifacts/testing/simplification_structure_20260928/simplification.json).

V?rification de cette tranche : 44 tests cibl?s, 308 comparaisons m?moire du
lecteur et rapprochement sur les CSV r?els du nominal et des risques ; quatre
calculs de 1 825 jours, 124 exports identiques, 47 blocs de carte concordants,
197 contr?les de contenu/provenance, navigation et suivi des lots hors ligne.
La validation agr?g?e est dans le
[manifeste final](../artifacts/testing/simplification_structure_20260928/toolbox/gate-9c12c964a0664437915a767ea0fb9fde/manifest.json).
Les ensembles Monte Carlo et les campagnes fournisseurs complets n?ont pas ?t?
rejou?s. Les sources avant/apr?s et les preuves sont conserv?es ; les sorties
lourdes de qualification sont retir?es apr?s validation.

## Ce qui doit rester possible

Nominal en dynamique des systèmes ; dépendance à l'état ; lots et transports ;
cascades ; sensibilité ; Monte Carlo et propagation des paramètres incertains ;
criticité fournisseur selon la configuration ; audit et contexte web sourcé ;
construction des cartes et documentation reliée au code et aux règles métier.

Les anciennes commandes ne sont pas toutes conservées. Les capacités courantes
restent l'objectif ; une méthode scientifique différente ne devient pas équivalente
simplement parce qu'une commande plus récente existe.

## Vérifier chaque regroupement

Figer sources, entrées, graines et horizon. Rejouer normalement quatre calculs de
1 825 jours ; comparer trajectoires, commandes, événements, lots, transports et
indicateurs. Vérifier la carte et ses téléchargements dans le navigateur hors ligne.
Les HTML historiques 01/03/04 sont réassemblés depuis leurs données embarquées :
cela ne recalcule pas les anciens modèles manquants.

Après l'incident Sophos, ne pas relancer de suite globale sans lecture de ses tests.
Les tests d'altération physique de fichiers, restauration de dates et disparition
simulée sont interdits. La procédure utilise des calculs en mémoire, des simulations
normales et des comparaisons en lecture seule. Un test exclu n'est pas un test réussi.

Préserver les UN physiques entiers, les sécurités sources du nominal, le calendrier
lundi-vendredi et 100 % des jours source au dépôt. `tau_process` conserve sa convention
actuelle de planification. Les invariants ne certifient pas la calibration industrielle.

Le [dernier relevé vérifié](../artifacts/testing/simplification_campagnes_20260928/simplification.json)
et le [guide de reconstruction](REGENERER_RESULTATS.md) documentent les résultats
vérifiés et les limites. Les anciens dossiers `tmp`, audits et preuves dispersées
ont été retirés du parcours courant ; leurs éléments utiles sont identifiés dans
[l'archive](../archive/README.md). Les sorties lourdes temporaires sont retirées
après qualification, avec conservation des sources et des preuves compactes.
