---
name: etudecas-supply-diagnose
description: Investiguer les écarts de service, stocks ou mouvements Etudecas et remonter les contraintes dans la chaîne réelle et simulée, avec preuves et hypothèses concurrentes. Utiliser pour un diagnostic métier, pas une simple retouche de graphique.
---

# Diagnostic supply chain

Appliquer AGENTS.md. Pour une investigation couvrant plusieurs couches indépendantes, utiliser `etudecas-orchestrate`. Lire [le contrat des tickets](references/tickets.md) à l'ouverture ou à la reprise d'une investigation ; garder un registre commun, pas un document par symptôme.

## Partir d'un événement précis

Définir article, site, produits couverts, unité, intervalle et mesure : demande non servie à l'échéance, rattrapage, stock physique/utilisable ou mouvement prévu/exécuté. Distinguer départ de Muret et livraison au client. Quantifier l'écart et localiser la première divergence, avant d'expliquer les mois suivants.

Chercher les analyses existantes et les sections utiles de `etudecas/docs/DONNEES_SOURCES.md`. Revenir aux cellules et CSV pertinents pour vérifier la sémantique ; un ancien rapport n'est pas un oracle industriel. Conserver versions, dates de publication et valeurs manquantes. Ne pas rouvrir un sujet explicitement suspendu par l'utilisateur.

## Remonter les conditions qui autorisent le flux

- Reconstituer aux mêmes bornes `stock physique fin = stock physique début + entrées physiques − sorties physiques + ajustements signés`. N'appliquer cette écriture qu'après vérification du signe et du périmètre des colonnes. Garder les résidus, les quantités brutes et les compensations visibles ; une variation de stock ne remplace pas une sortie brute.
- Pour chaque départ ou fabrication manquant, examiner la quantité **utilisable à la date nécessaire** : lots présents, libérations, réservations, affectations et transports. Ne pas assimiler stock physique, stock libre et réception future. Le découpage disponible/retenu/réservé du registre simulé ne prouve pas les statuts industriels absents.
- Si une condition est bloquante, remonter à son événement producteur : réception, contrôle, fabrication, intrant BOM, transfert ou décision de lancement. Comparer dates promises, replanifiées et exécutées sans inventer l'identité d'un ordre entre versions MRP agrégées. Distinguer calendrier ouvré, transport, traitement à réception et `tau_process`.
- Si le stock utilisable paraît suffisant, poursuivre vers demande connue, prévision, besoin net, engagement déjà couvrant, priorité/allocation, capacité et calendrier, puis expédition et livraison. Ne pas forcer une explication fournisseur. Examiner aussi un besoin retardé, une production non lancée ou un problème de simulation.

Faire suivre le déficit jusqu'à l'aval : quantité et durée non couvertes, fabrication déplacée, stock tampon consommé, livraison retardée ou perdue. Examiner les usages partagés et la nomenclature seulement dans le périmètre autorisé. Une baisse amont n'implique pas automatiquement une perte de service ; un rattrapage peut masquer un déficit dans le total annuel.

## Établir une conclusion qui résiste à la comparaison

Séparer **symptôme**, **contrainte immédiate démontrée**, **cause de cette contrainte** et **impact aval**. Rechercher les explications concurrentes plausibles et l'observation qui les distingue. Rechercher un épisode comparable sans problème ou une autre référence : la cause proposée doit expliquer pourquoi le problème survient ici et pas dans le témoin.

Si un essai peut départager les causes, utiliser `etudecas-supply-calibrate`. Sinon, poursuivre les rapprochements accessibles ou décrire précisément l'information manquante et ce qu'elle permettrait de trancher. Un bilan fermé ou un premier rapprochement plausible ne clôt pas le diagnostic. Ne pas remplacer l'incertitude par une longue liste de risques génériques.

Restituer d'abord les causes étayées et leur contribution chiffrée, puis l'écart restant, les alternatives réfutées et la prochaine vérification utile. Donner les preuves accessibles ; conserver au ticket le niveau de confiance et la portée exacte, sans promettre une cause unique quand les données ne l'identifient pas.
