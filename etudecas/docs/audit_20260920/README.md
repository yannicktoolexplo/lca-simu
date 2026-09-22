# Audit approfondi Etudecas et carte HTML — 20 septembre 2026

**Suivi post-audit :** les [corrections intégrées et nouveaux replays](../changes/2026-09-20-audit-integrated-corrections.md) et leur [contre-vérification numérique](../changes/2026-09-20-final-map-numeric-verification.md) sont désormais disponibles. Voir le [bilan courant](../PROJECT_STATUS.md) pour les décisions et les contrôles finaux de la livraison corrigée. Le présent rapport conserve les constats et empreintes de l'ancienne carte ; il n'est pas réécrit comme s'il avait examiné le nouveau livrable.

Public de référence : **planificateur supply chain / responsable industriel**, conformément au choix utilisateur. Ce rapport couvre le modèle, les données métier, les résultats livrés, leur affichage et le pack multi-agent.

**Conclusion : le registre physique et plusieurs outils de suivi sont solides, mais la carte ne peut pas encore être considérée comme un outil qualifié de décision industrielle.** Des défauts démontrés touchent l'échéancier de demande, les bases de valorisation, les bilans matière affichés et l'attribution des impacts. Les courbes peuvent reproduire correctement les CSV tout en portant une interprétation métier erronée.

La priorité est de corriger ces contrats et leurs vérifications avant d'ajouter des incidents physiques ou de nouveaux indicateurs. Les anomalies constatées ne justifient pas de jeter la simulation ni le suivi des lots : les couches concernées sont identifiées et les corrections peuvent rester ciblées.

## Livrable examiné et préservation

La [carte examinée](../../simulation/result/_reruns/corrected_map_20260918/maps/supply_graph_corrected_map_20260918_enquetes_20260920.html) est celle des enquêtes du 20 septembre, issue de `corrected_map_20260918`. Son empreinte SHA-256 est :

```text
434511736e814d149b4ce0697d08d3d5b243fda0e2fc954f1d83ab4678a2cf5a
```

Le nominal, le scénario de risque `state_dependent_full` et les deux actions finales `safety_150` / `expedite_50` ont été examinés séparément. Les dossiers historiques `actions_initial_review` ne servent pas de référence. Les manifestes et graphes préparés propres à chaque calcul font autorité ; le graphe brut est une étape antérieure.

Cet audit ajoute des rapports et des scripts de preuve. Il ne corrige ni le moteur, ni les entrées, ni les résultats, ni la carte livrée. Les valeurs de sécurité réelles du nominal restent distinctes de la sensibilité ×1,5. Le suivi détaillé et le nouvel explorateur restent inchangés.

L'accueil, le README et le bilan documentaire du projet renvoient maintenant vers ce nouvel audit pour préciser la portée des qualifications précédentes.

## Ce qui est acquis, et ce qui ne l'est pas

| Dimension | Appréciation fondée sur les contrôles |
|---|---|
| Bilans physiques et généalogie | Les quatre calculs passent les 62 familles d'invariants CSV, notamment bilans, rapprochement stocks/registre et quantités physiques UN entières. Cela valide les propriétés testées dans les conventions du modèle. |
| Nomenclatures et lots | 15 672 rapprochements de consommations par campagne et 10 294 contrôles de lots/capacités/semaine passent. Les sorties d'en-cours initiaux restent un cas distinct. |
| Valeurs des courbes | 1 246 séries temporelles rapprochées sur leurs 1 852 391 valeurs ; 538 figures inventoriées avec contrôles numériques. Aucun écart numérique inexpliqué dans ces rapprochements. |
| Fidélité à la référence métier | Insuffisante pour la demande datée et plusieurs conventions de prix, calendrier et besoins MRP. Une conservation annuelle ne prouve pas la fidélité des dates. |
| Présentation métier | Bilans matière, alertes, agrégats d'unités et périmètres de coûts à corriger. Le vocabulaire distingue encore mal prévu, exécuté dans la simulation et observé dans l'entreprise. |
| Interactivité | Carte et parcours utilisables hors ligne ; filtres, sélection, légendes et nouvel explorateur fonctionnent dans les cas examinés. Radars masqués, diagnostics non synchronisés avec la période et navigation clavier incomplète. |
| Recherche | Base de calcul et de traçabilité intéressante ; pas de qualification industrielle ni de preuve causale générale. Les hypothèses, politiques comparées et informations disponibles à la décision doivent être explicitées. |
| Documentation automatique | Dix registres à jour techniquement. Leur réussite vérifie la synchronisation document/code/tests, pas la vérité métier des règles documentées. |
| Pack multi-agent | Rôles et workflows utiles ; absence de configuration native découvrable à la racine lors de l'audit. Le mini-kit Python n'est pas un orchestrateur Codex. |

## Défauts à traiter en premier

Les identifiants renvoient aux rapports détaillés ; ils évitent de compter plusieurs fois un même défaut vu par différents auditeurs.

| Priorité | Constat et preuve représentative | Conséquence pour l'utilisateur | Correction et critère d'acceptation |
|---|---|---|---|
| P1 — Demande de référence | **MD-01** : 268091, semaine 1 = 13 300 UN dans Excel, contre 22 908,142858 dans le service simulé. Le lissage MRP affecte aussi la demande réalisée. | Les ruptures et les actions sont évaluées sur un autre échéancier, malgré un total annuel conservé. | Séparer demande réalisée et prévision MRP. Changer le lissage doit laisser les demandes et leurs dates inchangées ; produire ensuite un nouveau calcul comparatif. |
| P1 — Valorisation et transport | **MD-02** : changer KG en G pour un article connu multiplie/divise par 1 000 le coût de secours d'un autre article. **MD-05** : tarif déclaré par unité appliqué par batch économique. | Les additions sont correctes, mais leurs bases ne permettent pas de justifier une décision économique. | Prix par article, unité et devise ; estimation explicite ou valeur inconnue. Test d'invariance au changement d'unité et cas de tarif calculable à la main. |
| P1 — Bilans matière affichés | **N1/N2** : pour 338929, consommation présentée 17 900 915 UN contre 15 955 200 consommées dans le registre ; « livré » 17 062 600 contre 16 582 600 réceptionnées. Dix-huit diagnostics de bilan sont remplacés par un statut d'activité. | La carte peut suggérer un bilan physique faux sans montrer l'écart détecté. | Séparer théorique BOM, consommation physique, départ et réception. Afficher le bilan daté et conserver les anomalies visibles. |
| P1 — Alertes et unités | **N3/N4/N5** : reliquats fractionnaires transformés en 1 825 jours de situation critique ; ancienne référence épuisée prise pour une rupture ; détails MRP additionnant UN, G et KG. | Priorités opérationnelles et score descriptif trompeurs. | Définir demande entière en retard et référence active ; séparer unités et seuils métier. Tests négatifs sur reliquat, référence retirée et mélange d'unités. |
| P1 — Attribution des impacts | **MD-03** : un incident jamais appliqué peut afficher « Client atteint » et recommander une action prioritaire sur la seule présence d'un backlog concomitant. **MD-04** : un délai futur entre dans les observations dès l'expédition décidée. | Une association ou une prévision peut être présentée comme un impact causal constaté. | Distinguer configuration, application, exposition et effet attribué. Définir ETA connue et délai réalisé. Sans preuve, afficher « association à investiguer ». |
| P1 — Comparaison économique | **N6** : le risque semble moins coûteux de 27,25 millions sur les opérations ; avec l'exceptionnel, l'écart devient +16,75 millions, dans les unités monétaires du modèle. | « Coût total le plus bas » peut inverser le choix. Ces montants ne sont pas des pertes réelles validées. | Afficher les trois périmètres, l'horizon et le service ; ne conclure économiquement qu'après correction des bases de valorisation. |
| P2 — Informations réellement visibles | **UI-01/UI-02** : 87 radars présents mais inaccessibles depuis les onglets masqués ; filtre année 1 appliqué aux courbes, mais preuve de production restant sur cinq ans. | Une information existe dans le HTML sans être utilisable, ou deux chiffres d'une même vue portent sur des périodes différentes. | Rendre les radars accessibles ; appliquer un contexte commun article/site/scénario/période aux courbes, cartes et diagnostics. Test navigateur à chaque changement de période. |

Les détails, fichiers et lignes concernés, tolérances et contre-exemples sont dans [modèle et données](model_data.md), [courbes et résultats](numeric_map.md), [interface](interface.md) et [contre-relecture](review.md).

## Décisions métier à distinguer des erreurs de code

Ces points ne doivent pas recevoir une correction arbitraire :

- **Calendrier de sécurité — MD-06 :** la source parle de jours ouvrés ; le calcul utilise des jours continus. Il faut préciser les calendriers fournisseur, usine et dépôt. Le coefficient de dépôt 0,75 reste une convention connue à décider, pas une modification autorisée par cet audit.
- **Base des besoins MRP — MD-07 :** 23 couples article/usine utilisent un besoin statique issu de capacité × BOM. Pour 042342, 9,29 millions UN/j sont comparés à une consommation moyenne de 0,235 million. Dire si la cible couvre la capacité potentielle, le programme de production ou la demande.
- **Durée de fabrication — MD-11 :** `tau_process=3` intervient dans la planification, tandis que les lots nouveaux sont libérés au jour du démarrage. Le Gantt ne prouve donc pas trois jours de transformation, contrôle ou maturation physique.
- **Stock réservé — MD-09 :** préciser propriété et présence physique pour sa valorisation jusqu'au départ. Le coût conditionnel recalculé n'est pas une correction déjà décidée.
- **Prix, capacités et origines — MD-02/MD-10 :** des valeurs de secours, capacités estimées et origines fabricant inconnues restent des hypothèses. Aucune automatisation ne peut les rendre observées par simple changement de libellé.

Les départs au-delà de l'horizon (**MD-08**) nécessitent des statuts prévu/réservé/expédié distincts. Leur présence dans un CSV ne prouve pas une erreur de bilan ni une surfacturation : le moteur reporte déjà les métriques de coût à la date de départ prévue.

## Carte adaptée à un planificateur

La carte géographique doit rester une entrée pour localiser le réseau. Pour répondre vite à une question opérationnelle, il faut un contexte de lecture commun et trois accès :

1. **Situation à une date** : stock disponible, réservé, en transit, production en cours, demande échue et prochaines réceptions ; un article et une unité par grandeur.
2. **Parcours d'un lot** : origine → réception → consommation → fabrication → expédition → client, avec remontée inverse, identités inconnues explicites et bornes après mélange. Conserver le suivi détaillé en complément de l'explorateur simplifié.
3. **Comparaison et preuve** : nominal/action/risque sur le même périmètre, hypothèses visibles, données sources et formule accessibles depuis chaque résultat ; exposition potentielle distincte de l'effet réellement recalculé.

Chaque indicateur doit donner son unité, sa période, son scénario, sa définition, sa source et son statut : donnée observée, estimation, prévision ou exécution simulée. Un bouton « Pourquoi ce chiffre ? » doit ouvrir ces éléments, pas seulement une interprétation narrative.

Les tableaux doivent privilégier des quantités entières lisibles pour UN, des colonnes courtes, des totaux compatibles et des détails à la demande. Retirer de la navigation principale les analyses sans résultat actif, ou les annoncer clairement comme indisponibles. Compléter le clavier, la fermeture par Échap, la gestion du focus et la lisibilité des annotations. Voir la [revue d'interface et ses captures](interface.md).

## Vérifications réalisées et limites

| Contrôle | Périmètre et résultat |
|---|---|
| Inventaire du code | 652 fichiers Python sous `etudecas`, hors archives et preuves ; 245 fichiers de tests ; 492 417 lignes ; aucune erreur de syntaxe. Cet inventaire n'est pas une lecture exhaustive de chaque ligne. |
| Analyse statique ciblée | Ruff F821/F822/F823 : aucun nom indéfini détecté dans ce périmètre. Aucun audit de sécurité complet n'est revendiqué. |
| Suite de référence | 887 tests réussis, 2 ignorés, 17 désélectionnés ; 67 sous-tests réussis. Les deux tests ignorés nécessitent une ancienne fixture réelle et ne valident pas la carte actuelle. |
| Suite élargie | Les 1 713 tests hors référence terminent : 1 686 réussis, 27 ignorés, 9 sous-tests réussis, aucun échec. Avec la référence : **2 573 tests réussis, 29 ignorés et 76 sous-tests réussis**, sur 2 602 tests collectés sans doublon. [Synthèse machine et XML](../../artifacts/testing/full_audit_20260920/audit-summary.json). Les tests ignorés ne sont pas comptés comme réussis. |
| Pack isolé | 26 réussites, 1 échec : un test vérifie encore les anciens chemins globaux d'output. Des fichiers historiques peuvent masquer cet échec dans une copie non nettoyée. |
| Invariants des quatre calculs | 62 familles par calcul ; 3 789 002 vérifications ponctuelles ; aucune violation dans les familles contrôlées. |
| Source, BOM, lots | 28 lignes de stocks rapprochées ; 24 composants de trois BOM ; 15 672 contrôles consommation/production et 10 294 contrôles de lots/capacités/semaine. |
| Courbes | 1 981 rapprochements réussis ; 1 246 séries temporelles ; 538 figures avec contrôles numériques. Les points réutilisés entre figures ne sont pas des observations indépendantes. |
| Navigateur hors ligne | 32 panneaux de nœuds nominaux, 29 sélections d'audit fournisseur et ouvertures de panneaux : 70 parcours tentés, 69 exécutés, 1 bouton indisponible. 24 examens complémentaires dont 2 modes indisponibles. Aucune erreur JavaScript capturée ; plusieurs défauts métier et d'accessibilité néanmoins démontrés. |
| Documentation | `check-all` passe sur les dix registres. |
| Contre-relecture | Quatre constats majeurs reproduits indépendamment. Un faux zéro provisoire dans un oracle de consommation a été écarté et corrigé avant conclusion. |

Les 29 tests ignorés correspondent à 24 contrôles dépendant de fixtures historiques, 4 contrôles d'un ancien contrat de campagne à trois voies et 1 contrôle de syntaxe JavaScript nécessitant Node.js, absent du poste. Le passage dans Chromium couvre les parcours décrits, sans remplacer ce dernier contrôle sur toutes les branches.

Les scripts navigateur combinent clics DOM, une sélection réelle à la souris et, pour balayer les nœuds, l'émission de l'événement de sélection du graphe. La couverture n'est donc pas un test à la souris de toutes les positions. Les captures couvrent plusieurs tailles d'écran, dont 1 440 × 900 et 768 × 1 024 ; elles ne certifient pas tous les appareils.

La carte embarque un registre de lots nominal. Les agrégats du risque et sa carte de lots séparée ne doivent pas être assimilés à un basculement complet des données de l'explorateur principal. Les vérifications livrées précédemment sur les enquêtes restent des preuves distinctes ; cet audit ne prétend pas avoir rejoué toutes leurs combinaisons.

Les branches historiques et prototypes ne bénéficient pas d'une validation industrielle par l'exécution de tests. Monte Carlo, certains scans et sensibilités ne disposent pas de résultats dans le HTML actif. Aucun intervalle de confiance scientifique, aucun audit fournisseur réel pour les 28 fournisseurs estimés et aucune durée industrielle détaillée ne sont inventés pour combler ces absences.

## Pourquoi les anciens contrôles ne suffisaient pas

Ils vérifiaient principalement conservation, intégralité des quantités, identité des fichiers et cohérence entre registres. Ce sont des propriétés nécessaires. Elles ne détectent pas une transformation qui conserve le volume annuel mais déplace la demande, un prix arithmétiquement cohérent mais exprimé sur une mauvaise base, ou un diagnostic qui déduit une causalité d'une simple coïncidence temporelle.

La vérification doit donc couvrir quatre niveaux séparés : **source métier → contrat de modèle → mouvement/résultat → interprétation affichée**. Ajouter des tests qui répètent seulement la formule de production ne résout pas ce problème. Les [contrats et expériences proposés](recherche_et_verification.md) utilisent calculs manuels, transformations équivalentes d'unités, contre-exemples, rapprochements de registre et contrôle navigateur.

## Recherche et multi-agent : suite concrète

Le [plan de qualification scientifique](recherche_et_verification.md) précise la traçabilité des hypothèses, la distinction vérification/validation, les comparaisons appariées, les expériences nécessaires à une attribution causale et le traitement de l'incertitude. Cinq années répétant un profil annuel ne représentent pas cinq années indépendantes observées.

L'[audit du pack et la comparaison des outils actuels](multiagent.md) proposent une architecture Codex native : orchestrateur, agents d'exploration/simulation/carte/validation, skills métier découvrables et toolbox déterministe autour des contrôles existants. Les versions et recommandations ont été vérifiées dans l'environnement et les documentations officielles.

**État : architecture documentée, intégration native encore à construire.** Aucun plugin, SDK, service ou configuration globale n'a été installé par cet audit. Les agents ayant participé à l'analyse sont ceux de l'environnement courant, pas la preuve que le pack fonctionne déjà sur un nouveau poste.

L'ordre de réalisation recommandé est le suivant :

1. Ajouter les contre-exemples métier démontrés aux contrôles de non-régression et définir les règles encore ambiguës.
2. Corriger demande, unités/prix/tarifs et données du bilan matière ; produire des résultats nouveaux avec comparaison à la référence conservée.
3. Corriger alertes, attribution des impacts et cohérence des périodes ; vérifier chaque conclusion avec sa preuve.
4. Simplifier la navigation métier et réparer les interactions identifiées, en conservant les deux suivis de lots.
5. Intégrer le multi-agent natif et sa toolbox avec états de tâche, sorties structurées, empreintes et refus de conclure sans preuve. Le valider sur un cas où le vérificateur doit refuser une conclusion fausse, puis sur une correction réelle des étapes précédentes.

Cette progression permet d'évaluer les agents sur un travail utile et mesurable. Multiplier les agents avant de fixer les contrats ne rendrait pas les résultats plus fiables.

## Rapports et preuves

- [Modèle, données sources et hypothèses](model_data.md) — MD-01 à MD-11.
- [Courbes, tableaux et sémantique des résultats](numeric_map.md) — N1 à N7.
- [Clarté, vocabulaire, interactivité et captures](interface.md) — UI-01 à UI-08.
- [Recherche, contrat des indicateurs et stratégie de vérification](recherche_et_verification.md).
- [Pack, agents, skills, toolbox et références actuelles](multiagent.md).
- [Contre-relecture indépendante](review.md).
- [Commandes de reproduction et limites des scripts](reproduction.md).
- [Synthèse machine et empreintes finales](../../artifacts/testing/full_audit_20260920/audit-summary.json).
- [Dossier local de preuves et scripts](../../artifacts/testing/full_audit_20260920/).

Les preuves lourdes restent locales et hors versionnement. Les rapports indiquent leurs chemins et les scripts permettant de refaire les contrôles ; conserver les manifestes et la référence exacte avec toute transmission des conclusions.
