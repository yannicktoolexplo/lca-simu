# 2026-09-20 — Intégration native et preuves Etudecas

Le pack ne disposait que de rôles documentaires ; son test bout en bout vérifiait un ancien répertoire d'outputs et pouvait réussir grâce à des fichiers périmés.

Ajouts : profils et skills Codex prêts à intégrer sous `etudecas_codex_multiagent_pack/native`, instructions racine et configuration sans dépendance LLM externe ; toolbox locale `python -m etudecas.toolbox` avec catalogue fermé, fichiers UUID, empreintes et refus d'agrégation si les preuves manquent ou changent. Les contrôles réutilisent les outils indépendants déjà présents dans Etudecas.

Correction du mini-kit : `run` retourne le répertoire réellement créé ; test isolé sur deux runs, JSON et image vérifiés ; Pillow est une dépendance d'exécution.

Vérifications : 27 tests du pack réussis ; essais positifs et négatifs de toolbox, validation des trois skills, doctor structurel et qualification d'un vrai calcul. Les verdicts détaillés sont conservés dans `etudecas/artifacts/testing/native_multiagent_20260920`. Le guide [MULTI_AGENT_OPERATIONNEL.md](../MULTI_AGENT_OPERATIONNEL.md) décrit installation, commandes, contrats et limites. Un doctor staging n'est pas une preuve de chargement par Codex : la présence racine et la découverte à l'exécution restent des états distincts.
