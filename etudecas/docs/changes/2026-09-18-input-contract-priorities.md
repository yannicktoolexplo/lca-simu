# Cinq priorités : entrées du simulateur et API locale

Ce lot reprend les constats E3 et E4 de l'audit initial. Il ne modifie ni les
sources figées de calibration ni le lanceur batch `analysis_batch_common.py`.

## 1. Validation stricte des requêtes

`request_from_dict` refuse les conversions ambiguës de booléens et d'entiers,
les profils inconnus, les structures d'overrides incorrectes, les multiplicateurs
non finis ou négatifs et les champs inconnus. Il exige exactement une source
de graphe. L'API Python conserve ses options internes de confiance et son ordre
historique de paramètres positionnels.

## 2. Frontière HTTP distincte

`http_contract.py` impose le moteur, l'identifiant et le dossier de sortie.
Les entrées sont résolues sous la racine configurée. Le serveur refuse les
arguments moteur libres, vérifie le graphe et l'existence du scénario, exige
un horizon explicite borné et empêche de combiner planning et feedback.
Les payloads existants avec `skip_map=true`, `skip_plots=true` et arguments
vides restent acceptables ; un `run_id` HTTP personnalisé doit être supprimé.

## 3. Accès et ressources de l'API locale

Le serveur est limité à la boucle locale IPv4, exige un jeton de session,
contrôle Host et Origin, remplace CORS `*` par une liste explicite, borne le
corps et les lectures socket et n'accepte qu'une simulation à la fois.
L'exécuteur HTTP séparé applique un délai au sous-processus moteur. Les refus
ont des statuts distincts ; les erreurs libèrent le créneau d'exécution.

Les premières vérifications ont révélé une fermeture TCP Windows pouvant
masquer la réponse d'un refus anticipé. La réponse comporte désormais une
longueur explicite ; le serveur ferme son côté écriture puis évacue une quantité
bornée des données restantes avant de fermer la connexion.

## 4. Validation du graphe

Les structures invalides sont rapportées avant l'accès à leurs champs. Le
validateur ne lève plus `AttributeError` pour une ligne d'article textuelle ou
un stock mal formé. Ses champs numériques contrôlés refusent les booléens et
les valeurs non finies. La validation du graphe actif existant retourne **zéro
anomalie** ; aucune donnée de ce graphe n'a été modifiée.

## 5. Documentation technique et métier automatisée

Le [guide](../SIMULATION_INPUT_CONTRACT.md) documente les unités, les zéros,
la frontière Python/HTTP, les commandes, la migration des clients et les limites.
Quatre règles avec 28 références constituent le sixième registre du catalogue.
Le workflow local prévoit leurs tests sur Windows et Linux. Il n'a pas été poussé
ni exécuté sur GitHub.

## Vérifications et limites

Les **88 tests ciblés passent** : API existante, nouvelles entrées strictes,
HTTP, validation du graphe et enrichissement Excel. Le parcours HTTP positif
exécute un faux moteur choisi uniquement par le test côté serveur. Un autre
test lance un véritable processus dormant et vérifie son interruption par le
délai. Aucune campagne scientifique nouvelle n'a été exécutée.

Les tests ont aussi permis de corriger la comparaison des chemins temporaires
Windows : les contrôles HTTP utilisent le chemin résolu, qui peut différer de
sa représentation courte. Le contrat Python interne conserve ses chemins.

La suite de référence élargie fait l'objet d'un bilan séparé ci-dessous. Les
tests historiques externes restent explicites et ne sont pas requalifiés.

La validation n'est pas une preuve de validité physique du scénario. Le serveur
est un outil local : il ne borne pas toute la mémoire, les sorties ou le nombre
de connexions ; son délai moteur ne couvre pas le prétraitement ou tous les
descendants possibles. Le guide décrit ces limites précisément. Les cartes
existantes ne sont pas réécrites : leurs appels live doivent adopter le jeton
et le nouveau contrat ; l'affichage autonome reste indépendant de cette API.

## Bilan final

La suite de référence a terminé en **308,15 secondes** : **765 réussites,
2 échecs, 2 tests longs ignorés, 17 tests historiques désélectionnés et
53 sous-tests réussis**. Le [rapport original](../quality/2026-09-18-input-contract-reference.json)
conserve les deux échecs :

- Le parcours de checkpoint V1 rencontre encore `WinError 5` au remplacement
  du registre. La V2 passe. La source V1 figée n'a pas été modifiée.
- Le nouveau test de libération du créneau HTTP vérifiait le sémaphore sans
  attendre la fin du bloc `finally` du serveur. La réponse réseau peut arriver
  avant ce nettoyage. Le test attend maintenant le sémaphore avec une borne
  de cinq secondes : une absence de libération échoue toujours, sans retry de
  requête, ni changement du délai moteur. Le test de corps incomplet utilise
  la même synchronisation.

Après cette correction, le [contrôle ciblé final](../quality/2026-09-18-input-contract-final.json)
donne **112 réussites et 4 sous-tests réussis en 7,93 secondes** : 88 tests
d'entrées/API/graphe et 24 tests d'outillage documentaire et de diagnostic.
Deux cas supplémentaires de longueur HTTP invalide ont été ajoutés après la
collecte de la suite de référence ; ils sont inclus dans ce passage final.
Les résultats ciblés ne transforment pas le rapport de référence initial en succès.
La suite complète des prototypes n'a pas été relancée dans ce lot.

Les six registres passent `python -S -m etudecas.documentation check-all`.
Le serveur s'importe aussi avec la seule bibliothèque standard. Le workflow
YAML est valide ; sa matrice Linux/Windows n'a pas été exécutée à distance.
Les rapports bruts sont sous `etudecas/artifacts/testing/2026-09-18-input-contract/`.

Le contrôle de provenance conserve **61 correspondances exactes et 7 écarts**
dans l'inventaire V8 : sa qualification historique reste inchangée. Les trois
empreintes historiques de calibration contrôlées dans le lot précédent sont
également inchangées. Aucun artefact historique n'a été résigné.
