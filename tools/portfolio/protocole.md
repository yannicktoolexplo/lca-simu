# Qualifier une capacité pour une décision supply

Une fiche répond à une question bornée. Par exemple, à configuration de demande identique, quel stock utilisable protège les livraisons pendant un arrêt, pendant combien de jours, à quel coût et pour quel maillon ? La réponse fait apparaître le témoin, la première divergence observable et la conséquence pour le décideur.

## Grille de revue

| Domaine | Question à instruire avec le métier | Preuve à rechercher |
|---|---|---|
| Demande, prévision et approvisionnement | Quelle alerte peut modifier quelle commande, avant la date de gel ? | Dates de connaissance, commandes ouvertes, délai fournisseur, historique réservé à l’évaluation, calibration des probabilités. |
| MRP, nomenclatures et lots | Une rupture vient-elle d’un manque net, de l’arrondi au lot, d’un délai ou du calendrier ? | Besoin brut et net par période, unités et rendements, stock projeté avant décision, propositions d’ordres et réceptions utilisables. |
| Capacité, ordonnancement et flux | Une priorité, un changement de site ou un transfert avancent-ils réellement la disponibilité ? | Charge/capacité par ressource et période, files, lancement et fin d’ordre, contrôle, départ puis réception. |
| Risque, cascade et résilience | Le choc amont atteint-il le client ? À quelle date s’épuise le premier tampon ? | Chronologie alignée témoin/intervention et identifiant du lot. Relier évènement, état, règle activée et première commande servie ou en retard. |
| Régulation et optimisation | Quelles actions sont faisables avec l’information disponible à chaque décision ? | Mesure observée, consigne, cadence, saturation, effort de commande, coût et service. Pour une optimisation, objectif, contraintes, faisabilité et référence commune. |
| Transport, coûts et environnement | Quel mode, fournisseur ou report de production déplace le coût et l’impact ? | Flux physiques, origine des facteurs, unité fonctionnelle, frontières, modes activés selon l’état. Comparer quantités livrées et horizons avant de classer les scénarios. |
| Incertitude et robustesse | Quelles réalisations conduisent à choisir une autre action ? | Lois et dépendances, horizon, graines et réplications, quantiles, écarts appariés, analyse de sensibilité et scénarios où le gain disparaît. |

Pour une réunion industrielle, nommer le responsable de la décision, le moment où il peut agir et la donnée qu’il possède alors. Un taux de commandes à l’heure, un taux servi en quantité et le pourcentage de demande servi la même semaine ont des dénominateurs distincts. Écrire la définition utilisée. Si les données manquent, formuler une question à poser. Utiliser les processus SCOR pour vérifier la couverture (Plan, Order, Source, Transform, Fulfill, Return et Orchestrate). Une correspondance avec un processus ne vaut pas certification SCOR.

## Niveaux de preuve

| Statut du catalogue | Pièce à relire | Ce que peut dire une diapositive |
|---|---|---|
| `documente` | Spécification ou protocole au commit cité | « La méthode proposée calcule… » |
| `implemente` | Calcul réellement réalisé, point d’entrée et conditions d’activation | « Le code permet de comparer… » |
| `resultat_archive` | Sortie enregistrée avec scénario identifiable et unité | « Sur ce scénario archivé, la série montre… » |
| `reproduit` | Rejeu réalisé au SHA indiqué, environnement et commande, manifeste versionné, oracle, tolérance et valeur constatée | « Le rejeu de cet essai retrouve… » |

La validation métier constitue une appréciation distincte. Indiquer les observations indépendantes, les cas et les dates couverts, le critère d’accord et les cas qui restent mal expliqués. Dans une cascade, l’ordre temporel seul ne démontre pas la causalité. Dans une simulation Monte-Carlo, distinguer l’enveloppe des trajectoires et l’intervalle de confiance sur une moyenne. Un contre-exemple ou une absence d’avantage peut devenir le sujet de la réunion.

## Critères d’acceptation pour le parent et le relecteur

- Une branche avec une barre oblique figure une seule fois avec son SHA. Une branche éloignée de la branche principale reste dans la recherche. Une version partagée entre trois branches ne constitue qu’une pièce au même chemin.
- Chaque conclusion substantielle possède une preuve pertinente qu’un tiers peut ouvrir à la révision annoncée. Une branche disparue ou un contenu modifié suspend la fiche. Vérifier aussi les dépendances si la question concerne l’exécutabilité sur une nouvelle révision.
- Une figure chiffrée possède une unité, une définition du scénario/témoin et un commentaire qui indique où regarder et ce qu’on peut conclure. Conserver les paramètres de sélection des lignes et la convention d’arrondi dans la fiche ou les preuves. Vérifier les valeurs contre les sorties du dépôt.
- Toute hypothèse de manque dit ce qui a été cherché, sur quel périmètre, quelle décision est affectée et quel essai ou entretien permettrait de trancher. Prioriser avec le décideur sur conséquence, incertitude et coût d’investigation.
- Relire la projection destinée à un tiers, y compris commentaires orateur, chiffres, métadonnées et noms de séries. Une fiche interne peut rester dans l’inventaire sans projection externe.

## Fondements et choix de conception

| Référence | Application dans ce harnais |
|---|---|
| [OpenAI, Harness engineering (2026)](https://openai.com/index/harness-engineering/) et [documentation des subagents Codex](https://developers.openai.com/codex/subagents/) | Point d’entrée court dans AGENTS.md, sources versionnées, outils déterministes et rôles à périmètre borné. |
| [Anthropic, Demystifying evals for AI agents (2026)](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) | Examiner les fichiers et l’état final. Tester une divergence entre versions et le contenu réellement livré au destinataire. |
| [Siegel et al., CORE-Bench (TMLR, 2025)](https://tmlr.infinite-conf.org/paper_pages/BsMMc4MEGS.html) | Distinguer une sortie trouvée d’une sortie reproduite en comparant une expérience à un oracle. |
| [Monks et al., STRESS](https://doi.org/10.1080/17477778.2018.1442155) et [grilles DES, SD, ABS](https://stressguidelines.github.io/stress-guides/) | Documenter les hypothèses, données, conditions initiales, logique, horizon, réplications et résultats nécessaires à l’interprétation. |
| [Sargent, Verification and validation of simulation models](https://doi.org/10.1057/jos.2012.20) | Évaluer séparément le modèle conceptuel, les données, l’implémentation et le comportement opérationnel. |
| [ASCM, SCOR Digital Standard](https://scor.ascm.org/processes/source) | Relier une technique à un processus, à un décideur et à un indicateur défini dans son contexte. |

Références consultées le 27 novembre 2026. Les critères ci-dessus sont une adaptation au dépôt. Les auteurs de ces références n’ont pas évalué les résultats de lca-simu.
