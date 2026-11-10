# Validation de la sensibilité courte — 10 novembre 2026

Le pilote du parcours adaptatif est vérifié sur cinq simulations de 21 jours.
L'étude de sensibilité des 19 facteurs sur 362 jours est distincte : elle n'est
pas validée tant que ses calculs et sa lecture indépendante ne sont pas terminés.
La référence reste `coherent-MRP-20261014` ; aucune référence n'est promue.

## Trois mesures explicites

La version 2 du rapport utilise :

1. **Part de demande servie en quantité** : quantité servie divisée par la
   demande nouvelle cumulée et l'arriéré initial, compté une fois par
   client/article. Elle inclut les rattrapages ; ce n'est ni la ponctualité ni
   le stock disponible à Muret. Les journées entièrement soldées restent un
   diagnostic séparé. Les anciens résultats v1 ne sont pas repris comme v2.
2. **Révisions du programme prévisionnel de fabrication simulé** : définition
   et base d'engagement conservées, avec numérateur/dénominateur explicites ;
   aucune assimilation aux ordres de fabrication industriels.
3. **Coût connu du capital immobilisé** : sous-total valorisé, distinct du
   transport et des frais d'exploitation. Les 12 couples sans valorisation
   fiable restent exclus, dont les deux PF à Muret ; ce n'est pas le coût
   complet des stocks de produits finis.

Le périmètre client/article et l'unité viennent du scénario, des états de stock
et de l'historique source. Les données manquantes, un jour ou une paire entière
absents donnent une inconnue. Le défaut « CSV client absent ⇒ disponibilité
100 % » est corrigé. Les bilans de retard sont vérifiés et les unités
incompatibles ne sont pas agrégées. Aucune règle MRP ou physique n'est changée.

## Pilote exécuté et contre-vérifié

Même témoin, même horizon, un facteur à la fois :

| Cas | Demande servie | Révision du programme | Coût connu |
| --- | ---: | ---: | ---: |
| Témoin | 85,5070 % | 28,2051 % | 66 811,7721 |
| Capacité ×0,5 | 85,5070 % | 28,2051 % | 66 814,4074 |
| Capacité ×2 | 85,5070 % | 28,2051 % | 66 811,7721 |
| Coût de stockage ×0,5 | 85,5070 % | 28,2051 % | 33 405,8861 |
| Coût de stockage ×2 | 85,5070 % | 28,2051 % | 133 623,5442 |

Les changements de capacités atteignent effectivement les deux capacités PF
renseignées. Les deux capacités de procédés absentes à Gaillac ne sont pas
inventées. L'absence d'effet significatif sur les taux à 21 jours n'établit pas
une insensibilité annuelle ; des délais peuvent atteindre 154 jours.

Les deux variantes de coût de stockage laissent identiques les 11 CSV
physiques et de programme comparés. Leur coût suit la variation attendue.
Le coût est recalculé indépendamment à partir du stock utilisable et retenu,
des taux dimensionnés et de la part d'immobilisation. La borne d'arrondi a été
fixée avant les résultats ; les coûts quotidiens concordent aussi.

Contrôles réellement exécutés sur les sources gelées :

- environnement toolbox vérifié ; 71 cas de tests exacts réussis, relus en
  mémoire, sans suite globale ni manipulation d'intégrité ;
- 40 contrôles indépendants en mémoire et 105 contrôles sur les cinq résultats
  réussis : service, périmètre, unités, programmes, crédits de campagnes,
  coût, changements de capacité et contrôles physiques sous coût seul ;
- cinq calculs en 716 secondes, pic des mémoires de travail échantillonnées de
  l'arbre possédé d'environ 1,09 GiB, environ 626 MiB de résultats ;
- qualification générique du témoin **refusée** : le profil compact n'exporte
  pas `production_input_consumption_daily.csv`. Les preuves ciblées ci-dessus
  ne qualifient pas les bilans matière complets. Les réserves antérieures de
  provenance F3 et transferts ne sont ni réévaluées ni levées par ce pilote ;
- aucun navigateur, Node, installation ou appel LLM externe exécuté.

## Étude 2025 et critères de conclusion

Le protocole déclaré couvre **19 facteurs globaux et 38 directions**, avec
paliers ×0,5, ×0,1, ×0,01 et ×2, ×5, ×20 ; au plus 115 calculs annuels, témoin
inclus, un seul à la fois. Les seuils valent 0,1 point pour chaque taux et 1 %
du coût témoin, avec plancher d'une unité monétaire. Les premiers effets sont
rapportés séparément et ne démontrent aucune monotonie globale.

Il est incorrect d'exiger que chaque paramètre change les trois mesures. Un
coût de stockage seul doit changer le coût, sans changer les flux. Quatre autres
facteurs monétaires ne ciblent pas directement l'immobilisation. Une entrée
inchangée ou saturée est distincte d'une absence d'effet dans les bornes :
la cible PF nominale à zéro reste zéro ; réduire la revue d'un jour ou augmenter
une fiabilité déjà à 100 % laisse les entrées effectives identiques. Ces quatre
comparaisons d'entrée ont été vérifiées en mémoire, sans simulation inutile.
L'activation physique des signaux de gain/lissage et des règles génériques
reste à établir dans les traces plutôt qu'à déduire d'un hash modifié.

La progression est conservée après chaque cas. Tous les exports compacts
produits sont retenus. La reprise v2 ne concerne qu'un arrêt de budget propre,
entre cas terminés, avec mêmes sources, protocole et reçus CSV. Ses gardes sont
testées en mémoire ; aucune reprise native d'une étude interrompue n'a été
éprouvée dans ce pilote. Les cas partiels ou échoués ne sont pas relancés.

Un contrôleur local borne l'exécution à 48 heures cumulées, 20 GiB cumulés de
résultats, 10 GiB d'espace libre minimum et 4 GiB de mémoires de travail
échantillonnées pour l'arbre possédé. Ce dernier contrôle n'est pas une limite
OS stricte ; les pics entre échantillons peuvent être manqués. Une lecture
indépendante des cas et des seuils est prévue automatiquement après les calculs.
Un arrêt de budget, une mesure inconnue ou une incohérence restent distincts
d'une étude bornée terminée et vérifiée. `all_three_satisfied=false` ne signifie
pas à lui seul une panne du programme.

Preuves locales :
`artifacts/testing/sensibilite_courte_validation_20261110/` ; pilote
`artifacts/testing/scv26_p21/` ; étude 2025 prévue sous
`artifacts/testing/scv26_c362/`. La page de progression et les manifestes donnent
le statut réel ; aucun résultat de la future étude n'est anticipé ici.
