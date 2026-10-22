# Travail Codex sur lca-simu / Etudecas

## Se repérer avant d'agir

Partir du simulateur existant : relever branche, commit et diff local ; lire les `AGENTS.md` applicables et préserver les changements de l'utilisateur. Utiliser `rg` pour repérer les consommateurs avant modification. Ne pas créer de `agent.md` concurrent.

Pour Etudecas, commencer par [son README](etudecas/README.md) et le [guide documentaire](etudecas/docs/README.md), puis lire seulement les contrats utiles :

- référence active : [MRP_REFERENCE_20261014.md](etudecas/docs/MRP_REFERENCE_20261014.md), puis le bundle désigné ; les anciens registres « current » ne prouvent pas quelle référence exécute le code ;
- règles et sources : [REGLES_MRP.md](etudecas/docs/REGLES_MRP.md), [SIMULATION_INPUT_CONTRACT.md](etudecas/docs/SIMULATION_INPUT_CONTRACT.md), [DONNEES_SOURCES.md](etudecas/docs/DONNEES_SOURCES.md) ;
- maintenance, expérimentation ou nouveau mécanisme : sections pertinentes du [guide scientifique](etudecas/docs/DEVELOPPEMENT_SCIENTIFIQUE.md) ;
- contrôles : [TEST_VALIDATION.md](etudecas/docs/TEST_VALIDATION.md) ; agents et commandes : [MULTI_AGENT_OPERATIONNEL.md](etudecas/docs/MULTI_AGENT_OPERATIONNEL.md).

Distinguer acquis vérifié sur l'état courant, capacité existante mais non éprouvée, proposition et inconnue. Les bilans datés et résultats temporaires restent dans leur suivi ; les consignes durables ne servent pas de journal de tâche.

## Conduire les changements

Diagnostiquer avant de modifier : périmètre article/site/usages partagés, unités et BOM, dates/calendriers, stocks et ordres initiaux, puis bilans, disponibilités et décisions MRP. Utiliser [etudecas-supply-diagnose](.agents/skills/etudecas-supply-diagnose/SKILL.md) pour expliquer un écart, [etudecas-supply-calibrate](.agents/skills/etudecas-supply-calibrate/SKILL.md) pour départager les hypothèses. Quantifier la propagation jusqu'au client et les stocks qui l'absorbent. Une contrainte immédiate n'explique pas encore sa cause industrielle.

Préférer les règles paramétrées par les sources, les noms métier et les extractions progressives par responsabilité ; sourcer toute exception article/site. Une recommandation d'architecture ou d'outil ne déclenche pas une réécriture. Justifier ajout de dépendance ou migration par problème, alternative existante, compatibilité, maintenance et preuve attendue. Le noyau reste reproductible sans réponse LLM. Pour une mission limitée aux instructions, reporter les changements moteur/données/dépendances au backlog distinct.

Lire les gros fichiers par agrégats et anomalies. Réutiliser les travaux seulement si code, données, paramètres et conventions sont compatibles. Garder un point de reprise court dans le suivi existant : référence, faits décisifs, hypothèses soutenues/réfutées/indécidables, preuves et prochain essai. Le parent seul édite le [registre commun](.agents/skills/etudecas-supply-diagnose/references/tickets.md).

Avant un essai, fixer question, témoin, intervention, critères de soutien/réfutation, budgets calcul/temps/mémoire/stockage et arrêt. Commencer par un oracle manuel ou un cas court ; élargir seulement si une nouvelle question le justifie. Si les variantes coïncident, vérifier activation, traces et compensations avant de multiplier les calculs. Ne pas imposer un quota arbitraire de contexte qui tronque l'investigation utile.

## Préserver les contrats métier

- UN physiques entières ; sécurités sources du nominal ; jours de sécurité lundi–vendredi ; dépôt à 100 % des jours source ; nominal/sensibilités séparés ; références antérieures conservées.
- `tau_process` reste une marge de planification, à confirmer avant d'en faire une durée physique. Distinguer commande, lancement, départ, réception, contrôle et disponibilité ; vérifier les inclusions des délais.
- Distinguer prévu/réservé/exécuté, physique/utilisable, théorie BOM/registre matière, coût opérationnel/approvisionnement externe ; préserver les deux suivis de lots. Une réservation n'est pas une consommation ; un bilan fermé ne prouve pas une correspondance produit/vrac.
- Garder sources et provenance : emplacement, article/site/étape, unité, version, dates d'effet et de connaissance, statut observé/reconstruit/hypothétique/simulé. Une absence n'est pas zéro ; ne pas inventer de donnée industrielle.
- Séparer rapprochement historique, rejeu autonome et prospective. Aucune observation future ni cible à reproduire injectée implicitement dans la décision. Observations industrielles limitées à 2025 ; croissance et reconduction ultérieures déclarées comme hypothèses.

## Déléguer et vérifier

Pour des couches indépendantes, utiliser [etudecas-orchestrate](.agents/skills/etudecas-orchestrate/SKILL.md) et les profils natifs `etudecas_explorer`, `etudecas_simulation`, `etudecas_map`, `etudecas_validator`, avec écritures disjointes. Une correction simple reste directe. Choisir un rôle compatible avec les fichiers attribués. Conserver trois enfants simultanés maximum, parent exclu, et l'héritage du modèle courant. Ne pas ajouter SDK, serveur MCP ou appel LLM externe uniquement pour orchestrer les outils locaux.

Chaque délégation précise objectif et réussite observable, scénario/données/versions, fichiers autorisés/interdits, livrable/preuves, budgets et arrêt. Le parent intègre séquentiellement. Les consignes de rôle et worktrees ne constituent pas une sandbox par fichier ; les permissions effectives viennent du runtime. Faire contre-valider une correction métier par un agent distinct, sans correction du code évalué et avec un oracle indépendant.

Depuis la racine, vérifier l'environnement existant avant toute installation. Python 3.11 minimum pour la toolbox :

```powershell
python -B -m etudecas.toolbox --help
python -B -m etudecas.toolbox doctor
python -B -m etudecas.toolbox docs
```

Les aides et le guide opérationnel définissent `tests --path FICHIER::CAS_EXACT`, `qualify --run DOSSIER`, `browser`, `handoff` et `gate`. Relire cas, fixtures et hooks avant tout test. Pour moteur/calcul, utiliser `etudecas-qualify` ; pour carte, `etudecas-map-review`. Une modification documentaire ne justifie pas une campagne de simulation.

Les commandes effectives écrivent chacune sous `etudecas/artifacts/testing` dans un dossier unique. Stabiliser les sources avant qualification ; un changement concurrent invalide la preuve. Code retour non nul, contrôle ignoré/exclu, preuve absente ou empreinte différente interdisent d'annoncer une réussite. Distinguer vérification du code, des données, du modèle conceptuel et des comportements industriels : les invariants ne certifient ni calibration ni causalité.

Terminer par l'intégration et la revue du résultat demandé, les contrôles adaptés sur l'état final et leurs limites. Restituer fichiers changés, raisons, tests réellement exécutés, liens de manifestes, inconnues et backlog hors périmètre. Ne pas publier de résultats lourds ni promouvoir une référence sans comparer gains et dégradations.

## Vérifications après l'incident Sophos du 23 septembre 2026

Consigne utilisateur : ne plus exécuter de tests qui altèrent volontairement des fichiers, restaurent leurs dates, simulent leur disparition ou réécrivent en boucle des fichiers factices pour éprouver des contrôles d'intégrité. Ne pas relancer `artifacts/testing/research_triage_20260923/validator/check_source_revision.py` ni une variante de ce test. Conserver les preuves de l'incident pour le service informatique.

Avant de lancer des tests existants, relire les cas sélectionnés et leurs fixtures : ne pas lancer une suite globale susceptible de contenir ces opérations. Privilégier les simulations normales dans un nouveau dossier de résultats, les comparaisons en lecture seule avec les références et les tests de calcul en mémoire. Une vérification exclue reste signalée comme non exécutée ; ne pas la compter comme réussie.

En cas de nouveau refus d'écriture ou d'alerte de sécurité, arrêter les exécutions concernées et diagnostiquer en lecture seule. Ne pas multiplier les sondes d'écriture ni contourner Sophos ; sa gestion relève du service informatique.
