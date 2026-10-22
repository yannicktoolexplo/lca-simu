# Vérifier une modification

Chaque modification doit être vérifiée sur des sources stabilisées, avec un
périmètre annoncé. Les anciens bilans et inventaires de tests sont dans les
[archives](../archive/README.md) ; ils ne qualifient pas le code actuel.
Les critères scientifiques et les distinctions entre planification, exécution
et observations sont dans [DEVELOPPEMENT_SCIENTIFIQUE.md](DEVELOPPEMENT_SCIENTIFIQUE.md).

## Sélectionner les contrôles

Après l'incident Sophos du 23 septembre 2026, relire les cas sélectionnés et
leurs fixtures avant de les exécuter. Ne pas lancer une suite globale, un
dossier entier ou une découverte automatique en supposant que tous les tests
respectent la consigne. `pytest-reference.ini` décrit un périmètre historique ;
il ne constitue pas une liste de tests autorisés après cet incident.

Les tests qui altèrent volontairement des fichiers, restaurent leurs dates,
simulent leur disparition ou réécrivent en boucle des fichiers factices restent
exclus. Les contrôles à privilégier sont les calculs en mémoire, les simulations
normales dans un nouveau dossier et les comparaisons en lecture seule avec les
références. En cas de refus d'écriture ou d'alerte, arrêter les exécutions
concernées et diagnostiquer en lecture seule, sans contourner la protection.
Ne pas relancer `artifacts/testing/research_triage_20260923/validator/check_source_revision.py`
ni une variante. Cette sélection prévaut sur les exemples anciens proposant un
module entier ou des tests adversariaux : leur présence dans un contrat ne vaut
pas autorisation. Conserver les preuves de l'incident pour le service informatique.

Depuis la racine du dépôt, installer les dépendances si nécessaire avec
`python -m pip install -r requirements-etudecas-test.txt`.
Exemples précis de tests de calcul en mémoire relus :

```powershell
python -B -m pytest -q -p no:cacheprovider etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_campaign_mechanics.py::test_memory_window_metrics_match_manual_two_day_oracle
python -B -m pytest -q -p no:cacheprovider etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_campaign_mechanics.py::test_memory_lane_quantities_count_shipped_and_exact_lane_only
```

Le premier rapproche les indicateurs d'un calcul manuel sur deux jours ; le
second vérifie les quantités expédiées pour la liaison exacte. Ces exemples
portent sur leurs fonctions, pas sur tout le moteur. Ne pas élargir la commande
au fichier entier : il contient aussi des anciens tests d'intégrité exclus.
Pour une autre modification, choisir et relire les cas qui couvrent sa règle.

## Choisir le niveau de preuve et l'oracle

| Objet à vérifier | Preuve attendue et limite |
|---|---|
| Code | Cas ciblé reproduisant le défaut, oracle indépendant et invariants concernés ; ne prouve pas la pertinence industrielle. |
| Données | Provenance, unités, dates de connaissance, périmètres et rapprochements ; une donnée manquante reste inconnue. |
| Modèle conceptuel | Hypothèses, états/transitions, ressources et mécanismes confrontés aux connaissances sourcées ; un bilan fermé n'établit pas tout le modèle. |
| Comportement pour un usage | Critères décidés avant ajustement, données/périodes hors calibration, effets aval et incertitudes ; conclusion bornée à cet usage. |

Une correction métier importante reçoit une revue par un agent distinct qui ne
modifie pas le code évalué. L'oracle est calculé à la main, en mémoire ou depuis
des sources indépendantes ; rappeler le helper de production ne constitue pas
un second calcul. Figer sources, données, paramètres et scénario avant de lancer
la qualification. Toute modification concurrente des sources invalide la preuve.

Ces petits cas sont des spécifications d'oracles à sélectionner selon le défaut,
pas des tests déjà implémentés ou exécutés :

| Cas et hypothèses | Résultat calculable indépendamment |
|---|---|
| Besoin 10 UN à J2, stock libre 3, réception ferme unique de 7 à J4, sécurité nulle et aucun autre besoin | 3 couverts à J2, 7 couverts avec 2 jours de retard, zéro nouvel achat ; aucune disponibilité fictive à J2. |
| Besoin 3 UN puis 6 UN, stock et sécurité nuls, lot minimum 10, aucun maximum, proposition à temps | Une proposition de 10 couvre les deux besoins, surplus final 1 ; pas deux commandes de 10. |
| Réception vendredi 16/10/2026, contrôle de 2 jours lundi–vendredi, réception exclue du décompte, sans jours fériés | Disponibilité mardi 20/10 ; impossible de consommer ces unités lundi. Ce calendrier d'exemple n'est pas une nouvelle source industrielle. |
| 10 kg utilisables communs, BOM A = 2 kg/UN et B = 3 kg/UN, sans apport ni perte | `2 * q_A + 3 * q_B <= 10` avec `q_A`, `q_B` entiers ; allocation selon la priorité déclarée, pas 10 kg disponibles pour chaque produit. |
| Deux produits se partagent 8 heures/jour, chacun exige 1 heure/UN | Somme des productions au plus 8 UN/jour, indépendamment du nombre d'articles. |
| Demandes successives 0,5 UN × 4, stock suffisant, reliquat initial nul et arrondi physique par reliquat | Service 0, 1, 0, 1 ; stock et mouvements entiers, conservation de la demande. |

Compléter selon le périmètre avec demande nulle, capacité nulle, absence de
composants, délai au-delà de l'horizon, stock bloqué et lot en cours à la fin.
Vérifier absence de double réservation/réception/consommation, conservation et
respect des dates ; un encours ou un transit final ne disparaît pas du bilan.

Déclarer les hypothèses des propriétés métamorphiques. Une conversion kg/g doit
préserver les masses converties et la valeur économique lorsque quantités et
prix sont convertis ensemble. Une hausse de capacité ou de stock ne garantit
pas universellement une hausse du service avec priorités, lots et engagements
interactifs. Pour un couplage temporel, examiner pas et ordre des événements ;
si le moteur n'expose qu'un pas fixe, déclarer cette limite au lieu d'inventer
une vérification de convergence.

## Vérifier le moteur, les cartes et la documentation

Le [guide de reconstruction](REGENERER_RESULTATS.md) décrit le recalcul nominal
sur 1 825 jours et les quatre présentations conservées. Après un changement du
moteur, rapprocher les résultats du nouveau calcul de la référence : quantités,
stocks, service, coûts et lots concernés. Conserver les conventions sources du
nominal ; les sensibilités utilisent des paramètres séparés.
Le recalcul cinq ans est un parcours disponible, pas le contrôle minimal de
chaque changement. Commencer au plus petit périmètre discriminant, puis étendre
si rattrapage, stocks tampons ou effets de bord l'exigent. Pour une modification
documentaire, vérifier liens, cohérence, commandes et configuration concernées ;
aucune campagne de simulation n'est requise par défaut.

Les commandes de qualification CSV et de navigation hors ligne figurent dans
le [guide de la toolbox](MULTI_AGENT_OPERATIONNEL.md). Elles prennent le run
et le HTML exacts à vérifier. Les contrôles d'invariants ne certifient ni la
calibration industrielle ni toutes les interactions de la carte.

Le contrôle documentaire est une lecture statique :

```powershell
python -B -m etudecas.documentation check-all
```

Il ne lance ni simulation ni tests métier. Les règles de mise à jour des
empreintes sont dans [AUTOMATION.md](AUTOMATION.md). Les données de tests et
intégrations historiques sont décrites dans [TEST_FIXTURES.md](TEST_FIXTURES.md) ;
leur présence ne dispense pas de la relecture avant exécution.

## Garder une preuve compréhensible

Pour enregistrer le test ciblé et son rapport dans un nouveau dossier de preuves :

```powershell
python -B -m etudecas.toolbox tests --path etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_campaign_mechanics.py::test_memory_window_metrics_match_manual_two_day_oracle
```

La toolbox écrit sous `etudecas/artifacts/testing` et affiche le chemin du
manifeste. Ce dossier contient les commandes réellement exécutées, les résultats
et leurs empreintes. L'outil de rapport `python -m etudecas.testing.report`
peut aussi lire un JUnit existant ; son aide précise les chemins d'entrée et de
sortie. Un rapport absent ou inexploitable ne devient pas un succès.

La restitution doit indiquer les cas exécutés, les résultats, les exclusions et
les limites. Conserver le résumé pytest avec le JUnit pour distinguer tests,
sous-tests et ignorés. Un test ignoré ou exclu n'est pas réussi ; une sélection
réussie n'est pas une validation de toute l'application.
