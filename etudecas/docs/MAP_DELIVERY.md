# Livraison de la carte du 18 septembre 2026

[Ouvrir la carte HTML](../simulation/result/_reruns/reviewed_map_20260918/maps/supply_graph_reviewed_map_20260918.html)

[Ouvrir le diagnostic métier et les actions](../simulation/result/_reruns/reviewed_map_20260918/decision_support/index.html) :
décomposition du score, retards FIFO, preuves des blocages et deux actions simulées.
Le [dernier bilan](changes/2026-09-18-decision-priorities.md) décrit cette livraison
et sa commande de reproduction.

La carte inclut désormais les [cinq améliorations de comparaison](changes/2026-09-18-comparison-priorities.md) :
score affiché corrigé, écarts recalculés, lecture métier précisée, septième domaine
documentaire et rapprochement automatisé du HTML avec les résultats.
La première version est conservée sous `supply_graph_reviewed_map_20260918_v1.html`.

Cette livraison exécute le moteur sur 1 825 jours pour le nominal et le
portefeuille complet de risques dépendants de l'état. Elle utilise le graphe
actif lotifié. Les résultats sont locaux ; les fichiers volumineux ne sont pas
inclus dans Git. Aucune nouvelle campagne Monte Carlo n'a été calculée.

## Les cinq priorités réalisées

1. Identifier la référence et conserver les anciens résultats.
2. Exécuter les deux scénarios dans `simulation/result/_reruns/reviewed_map_20260918`.
3. Régénérer la carte avec les analyses du seul run concerné : une analyse
   absente ne doit pas être remplacée par une ancienne analyse partagée.
4. Rapprocher les résultats des CSV journaliers et examiner la carte dans
   Chromium hors ligne : huit contrôles couvrent les panneaux et le filtre temporel.
5. Livrer cette fiche, les rapports et les empreintes des sources sélectionnées.

## Lecture métier

| Mesure sur 1 825 jours | Nominal | Risques complets |
|---|---:|---:|
| Demande cumulée, arrondie | 25 762 140 | 25 762 140 |
| Quantité servie cumulée, arrondie | 25 762 140 | 25 667 344 |
| Taux de service cumulé | 100 % | 99,632 % |
| Demande restant à servir en fin de période | 0 | 94 796 |
| Jours avec un reliquat, démarrage inclus | 3 | 454 |
| Coût total, unité du modèle | 289 514 139,19 | 262 259 661,75 |

Le service cumulé comprend les rattrapages : **100 % ne signifie pas que
toutes les livraisons étaient à l'heure**. Les trois jours de reliquat au
nominal l'illustrent. Les quantités agrègent les deux produits finis du cas.
Un coût inférieur dans le scénario risqué ne démontre pas un gain économique :
le service, la production et les stocks diffèrent. Cette comparaison ne fournit
ni intervalle de confiance ni estimation probabiliste issue de Monte Carlo.
Les enveloppes P10–P90 du comparatif décrivent seulement les scénarios
sélectionnés ; avec deux scénarios, elles n'estiment pas une incertitude.
La carte retire les trois jours d'amorçage du compteur comparatif de reliquat
(0 et 451 jours), alors que le tableau ci-dessus les inclut (3 et 454 jours).
Le score descriptif du scénario risqué affiche maintenant 1 919,8. La formule
et ses limites sont décrites dans le [guide de comparaison](SCENARIO_COMPARISON.md).
Cette correction d'affichage ne constitue pas une calibration du score.

## Vérification et traçabilité

Le [bilan compact de la première version](changes/2026-09-18-map-delivery-review.json)
contient les résultats : 69 tests ciblés et quatre sous-tests réussis,
huit contrôles navigateur hors ligne, 27 contrôles croisés réussis et six
registres documentaires à jour. Les titres des graphiques comparatifs ont été
repositionnés et leur lecture vérifiée sur la capture du HTML final.

Les rapports de la première version sont dans `etudecas/artifacts/testing/map-delivery-20260918/`.
Ceux de la deuxième version sont dans `etudecas/artifacts/testing/map-comparison-20260918/`.
Leurs empreintes sont historiques. Les contrôles du HTML actuel sont dans
`decision_support/` sous le run, avec son bilan `delivery.json`.
Le premier dossier conserve :

- `numeric-review.json` : rapprochement demande/service/reliquat, bilan de
  conservation, couverture des jours, unicité des lignes et validation des packages.
- `browser/browser-review.json` : empreinte du HTML, données embarquées,
  erreurs JavaScript et résultat de chacun des huit parcours ; captures adjacentes.
- `source-start.json` et `delivery-review.json` : empreintes sélectionnées au
  démarrage et à la livraison, avec distinction entre calcul et rendu.
- `tests.xml` : tests ciblés du pipeline, de la documentation, des outils de
  validation et des composants de visualisation concernés.

Ces contrôles établissent la cohérence de cette livraison. Ils ne qualifient
pas les campagnes historiques V8, ne remplacent pas une calibration métier
et ne constituent pas une validation de toute la suite de tests du dépôt.

## Reproduire

Depuis la racine du dépôt, avec un nouveau dossier de sortie :

```powershell
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --days 1825 --state-dependent-scenarios full --no-require-montecarlo --output-dir etudecas/simulation/result/_reruns/mon_run
python -m etudecas.testing.map_delivery --run etudecas/simulation/result/_reruns/mon_run --run etudecas/simulation/result/_reruns/mon_run/scenario_runs/state_dependent_full --output etudecas/artifacts/testing/mon_run/numeric-review.json
python -m etudecas.testing.map_browser --html etudecas/simulation/result/_reruns/mon_run/maps/supply_graph_mon_run.html --output-dir etudecas/artifacts/testing/mon_run/browser
python -S -m etudecas.documentation check-all
```

La revue navigateur nécessite Playwright et Chromium. La carte livrée se lit
directement dans un navigateur sans serveur. Le mode sans Monte Carlo est un
périmètre explicite : la commande canonique conserve son exigence Monte Carlo.
