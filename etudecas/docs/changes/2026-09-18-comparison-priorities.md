# Cinq priorités : fiabiliser la comparaison dans la carte

La [carte corrigée](../../simulation/result/_reruns/reviewed_map_20260918/maps/supply_graph_reviewed_map_20260918.html)
réutilise les deux calculs de 1 825 jours déjà livrés. Les CSV de demande/service
et les résumés des deux runs sont inchangés, vérifiés par SHA-256.
La [première carte](../../simulation/result/_reruns/reviewed_map_20260918/maps/supply_graph_reviewed_map_20260918_v1.html)
est conservée pour comparaison.

## Réalisations

1. **Score et classement cohérents.** Le navigateur lisait le score historique
   du balayage de scénarios, absent des runs courants, alors que le score observé
   était déjà calculé. La synthèse et le bouton « Top perturbateurs » utilisent
   désormais le score observé. Un zéro valide n'est plus remplacé par un compteur
   d'événements. Le scénario risqué affiche **1 919,8**, pas zéro.
2. **Écarts au nominal recalculés.** Les écarts de service, coût, reports,
   pertes et achat externe utilisent la référence publiée dans le payload.
   Le service nul est conservé par le filtre « Service dégradé ». Pour la
   livraison courante, l'écart de service est **−0,368 point** et l'écart de
   coût **−27 254 477,44**, dans l'unité du modèle.
3. **Lecture métier précisée dans la carte.** Le service cumulé inclut les
   rattrapages ; les enveloppes de scénarios ne sont pas des intervalles de
   confiance Monte Carlo ; le score est descriptif et ses coefficients non calibrés.
4. **Septième domaine de documentation automatique.** Le
   [guide métier](../SCENARIO_COMPARISON.md), son registre et les pages générées
   relient formule, unités, limites, fonctions et tests. Le catalogue inclut ce
   domaine dans `build-all`, `check-all` et `watch-all`. Le workflow GitHub
   préparé inclut ses tests ; aucune exécution distante n'est revendiquée.
5. **Livraison revue et contrôles réutilisables.** La carte a été régénérée,
   examinée dans Chromium hors ligne et rapprochée des CSV. L'option
   `map_delivery --browser-review` détecte aussi un HTML modifié après revue,
   les scénarios dupliqués et les écarts numériques incohérents.

## Résultats des vérifications

- 77 tests ciblés réussis, avec quatre sous-tests ; après la dernière correction
  du contrôleur navigateur, 41 tests concernés et quatre sous-tests repassés.
- Huit parcours navigateur hors ligne réussis, sans erreur JavaScript.
- Rapprochement des deux runs et des KPI embarqués réussi, y compris les écarts signés.
- Sept registres documentaires à jour, contrôlés sans importer le moteur.
- Rapports complets : `etudecas/artifacts/testing/map-comparison-20260918/`.
- [Bilan compact](2026-09-18-comparison-review.json) conservé avec le code.

Le contrôle navigateur a d'abord échoué parce que son script essayait d'appeler
une fonction JavaScript interne non globale. Il lit maintenant les scénarios
embarqués et les cases effectivement sélectionnées ; la carte n'avait pas
d'erreur JavaScript.

## Limites conservées

Les résultats de simulation restent identiques : 100 % de service cumulé au
nominal et environ 99,632 % sous risques, avec 94 796 unités restant à servir.
La formule du score n'a pas été recalibrée. Les pertes répétées peuvent dominer
ce score : il ne doit pas être interprété comme un pourcentage ou une décision
industrielle. Aucun nouveau Monte Carlo ni qualification historique V8 ; la
suite complète du dépôt n'a pas été relancée.

Pour contrôler une prochaine carte après sa revue navigateur :

```powershell
python -m etudecas.testing.map_delivery --run <run_nominal> --run <run_risque> --browser-review <rapport_navigateur.json> --output <rapport_livraison.json>
python -S -m etudecas.documentation check-all
```
