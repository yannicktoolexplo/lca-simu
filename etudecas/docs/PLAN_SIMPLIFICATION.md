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

Le [dernier bilan vérifié](../artifacts/testing/human_code_20260925/BILAN.md)
et le [guide de reconstruction](REGENERER_RESULTATS.md) documentent les résultats
vérifiés et les limites. Les anciens dossiers `tmp`, audits et preuves dispersées
ont été retirés du parcours courant ; leurs éléments utiles sont identifiés dans
[l'archive](../archive/README.md). Les sorties lourdes temporaires sont retirées
après qualification, avec conservation des sources et des preuves compactes.
