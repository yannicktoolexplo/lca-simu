---
name: etudecas-supply-calibrate
description: Concevoir et comparer des essais Etudecas pour départager une erreur de simulation, une règle MRP manquante ou un aléa supply chain, et vérifier leur propagation sans surajuster la référence.
---

# Expérimentation et calibration supply chain

Utiliser après formulation d'un écart et de ses explications concurrentes avec `etudecas-supply-diagnose`. Appliquer AGENTS.md et actualiser le ticket commun selon [le contrat des tickets](../etudecas-supply-diagnose/references/tickets.md). Ce skill ne remplace ni `etudecas-qualify` ni une preuve industrielle.

## Choisir l'expérience qui peut changer la conclusion

Écrire avant calcul : question, cas de référence exact, hypothèse, intervention, périmètre, données conservées, effet attendu avec date et quantité ou intervalle, résultats contradictoires possibles et métriques de comparaison. Ne pas choisir après coup la seule fenêtre favorable. Définir un témoin et vérifier que le mécanisme intervient réellement dans la période étudiée.

Privilégier la question discriminante : une correction de calendrier doit déplacer les événements attendus ; une contrainte de capacité doit modifier le travail physique ; une disponibilité tardive doit empêcher un prélèvement avant libération. Distinguer ouverture administrative d'OF, réservation, travail exécuté et réception. Ne pas exiger zéro création d'ordre comme preuve d'un arrêt physique, sauf si c'est une condition explicitement testée.

Commencer par un bilan manuel ou un calcul court en mémoire, puis un scénario ciblé. Étendre à l'année complète lorsque la conclusion dépend du rattrapage, des stocks tampons ou des effets de bord ; un calcul court peut suffire à isoler une erreur. Passer aux cinq ans, Monte Carlo ou sensibilités lorsque la question et les instructions utilisateur le justifient. Pas de campagne volumineuse avant vérification d'une baseline exploitable.

## Exécuter des scénarios réellement distincts

Conserver nominal, stocks et ordres initiaux, demande, sécurités et règles non ciblées. Enregistrer explicitement les seules différences, le code et les entrées, puis exécuter dans un nouveau dossier. Préserver les identités d'engagements et les deux suivis de lots ; ne pas supprimer une commande pour forcer un creux ni la dupliquer pour améliorer le service.

Vérifier dans les traces et événements exécutés que l'intervention atteint le moteur, que l'état antérieur au changement est cohérent et que les quantités sont conservées. Pour un aléa non anticipé, le planificateur ne doit pas connaître arbitrairement l'incident futur ; si une adaptation anticipée est testée, la déclarer comme stratégie distincte. Respecter les restrictions Sophos et les contrats de qualification : aucune preuve manquante ou partielle ne devient un succès global.

Isoler d'abord les effets, puis combiner les mécanismes si leurs interactions départagent encore les explications. Si deux essais donnent les mêmes sorties, examiner activation, couverture par les stocks et compensation MRP avant de multiplier les amplitudes. Vérifier les identifiants et quantités des lots consolidés : un lot reçu peut regrouper plusieurs origines.

## Comparer la chaîne, pas seulement une courbe

Sur les mêmes dates et unités, comparer besoins et ordres prévus, fabrications/réceptions/transferts exécutés, stocks physiques et utilisables, durée/volume de manque et service client. Montrer les écarts hebdomadaires et les cumuls, le rattrapage et les états de fin d'horizon, dont le transit et le stock retenu. Un déficit de fabrication peut être absorbé en aval ; un rattrapage annuel n'efface pas les livraisons tardives.

Pour une règle commune, tester des références ou périodes non utilisées pour la régler. Pour un aléa, distinguer la compatibilité d'un scénario avec les observations de l'identification d'une cause réelle. Plusieurs causes peuvent produire la même courbe : ne pas calibrer une loi de probabilité à partir d'un seul scénario rétrospectif.

Faire contre-vérifier les calculs métier avec un oracle indépendant sur l'état stabilisé. Restituer gains, dégradations, effet résiduel, hypothèses réfutées et décision sur le ticket. Préserver la référence ; une amélioration locale ou des invariants réussis n'autorisent pas automatiquement sa promotion. Si les données ne départagent pas les causes, nommer l'observation supplémentaire qui serait discriminante.

Pour fixer séparation chronologique, identifiabilité, critères avant ajustement et incertitude, lire les sections calibration et incertitude du [guide scientifique](../../../etudecas/docs/DEVELOPPEMENT_SCIENTIFIQUE.md).
