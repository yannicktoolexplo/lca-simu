# Cinq priorités : interpréter les résultats et tester des actions

[Ouvrir le tableau de bord métier](../../simulation/result/_reruns/reviewed_map_20260918/decision_support/index.html)
· [Ouvrir la carte](../../simulation/result/_reruns/reviewed_map_20260918/maps/supply_graph_reviewed_map_20260918.html)

## Ce que les travaux apportent

1. **Score expliqué.** Les cinq contributions sont visibles. Les pertes de
   composants représentent environ 98,7 % du score du scénario risqué. Leur
   rapprochement avec les expéditions retrouve 488 148 540 dans l'horizon ;
   21 600 000 supplémentaires concernent des départs hors horizon et sont exclus.
   Aucun doublon exact de ligne à perte positive n'est retenu dans cet horizon.
   Le détail par article et unité évite de confondre composants et produits finis.
2. **Retards mesurés sous hypothèses explicites.** Pour le produit 268967 sous
   risques, le service le jour de la demande est borné entre 76,39 % et 82,31 %.
   Sous FIFO, le délai moyen des quantités servies est de 5,62 jours et le maximum
   de 62 jours. La plus ancienne demande encore ouverte a 22 jours en fin de run.
   Ces mesures ne sont pas un OTIF observé commande par commande.
3. **Blocages expliqués et sources accessibles.** L'usine M-1430 enregistre
   109 jours de contrainte sur le composant 730384 et 77 sur le composant 344135.
   Le tableau de bord relie ces composants aux fournisseurs du graphe et fournit
   les lignes de contraintes ainsi que les liens explicites entre événements et
   lots. Il ne prétend pas répartir le retard client entre fournisseurs.
4. **Deux actions réellement simulées.** Les deux composants limitants servent
   de cibles à un renforcement du stock de sécurité et à une accélération des
   approvisionnements, sur le même horizon de 1 825 jours.
5. **Livraison automatisée.** Une commande assemble analyses, actions, carte,
   documentation et contrôles. Le huitième domaine documentaire relie ces
   conventions au code et aux tests.

## Comparaison des actions

| Mesure | Risques sans action | Stock de sécurité ×1,5 | Accélération ciblée |
|---|---:|---:|---:|
| Service cumulé | 99,632 % | 100 % | 99,632 % |
| Reliquat final | 94 796 | 0 | 94 796 |
| Reliquat cumulé, unités·jours | 45 050 875 | 44 612 374 | 46 100 960 |
| Coût supplémentaire du modèle | — | 3 035 549,28 | 1 206 342,70 |

Le renforcement de stock permet de rattraper la demande en fin d'horizon,
mais ne supprime pas les retards pendant la période. L'accélération testée
coûte davantage sans améliorer le reliquat final et augmente ici le cumul des
reliquats. Ces essais invitent à explorer d'autres réglages ; ils ne démontrent
pas qu'une action serait rentable ou robuste en exploitation.

Les journaux du moteur confirment des commandes non neutres appliquées : 83
lignes pour le stock de sécurité et 667 pour l'accélération. D'autres lignes
ne trouvent pas d'ordre ou de flux exécutable : elles sont distinguées dans le
rapport JSON. Les événements dépendants de l'état peuvent différer entre essais.

## Reproduire et vérifier

```powershell
python -m etudecas.decision_support --run etudecas/simulation/result/_reruns/reviewed_map_20260918 --execute-actions --render-map --browser
```

Le [guide](../DECISION_SUPPORT.md) décrit aussi `--rebuild`, pour partir d'un
nouveau dossier avec les calculs nominal et risqué. Il précise les hypothèses
FIFO, les signatures du cache et les limites des coûts.

Les rapports complets se trouvent dans `decision_support/` sous le run :
`decision-report.json`, `delivery.json`, les deux CSV justificatifs, les
calendriers et journaux d'actions et les captures navigateur. Le
[bilan compact](2026-09-18-decision-review.json) conserve les résultats de
vérification avec le code.

La livraison passe les contrôles : quatre packages de résultats cohérents,
neuf parcours navigateur hors ligne (dont l'accès au tableau de bord et ses
liens), aucune erreur JavaScript, 91 tests ciblés et quatre sous-tests réussis,
huit registres documentaires à jour. Les empreintes des CSV de demande/service
et des résumés nominal et risqué confirment que ces références sont inchangées.

Les calculs nominal et risqué de référence sont réutilisés ; les deux actions
sont nouvelles. Pas de recalibration du score, de nouveau Monte Carlo, de
qualification historique V8 ni de relance de toute la suite de tests du dépôt.
