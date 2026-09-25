# Consignes du pack Etudecas

Les [consignes du dépôt](../AGENTS.md) et le
[guide opérationnel](../etudecas/docs/MULTI_AGENT_OPERATIONNEL.md) définissent
le travail courant. Ce pack conserve le déploiement natif révisable dans
`native/` ; il ne contient plus de moteur de démonstration.

## Routage courant

Les profils installés sont dans [`.codex/agents/`](../.codex/agents/) :

- `etudecas_explorer` : repérage en lecture seule des contrats et dépendances ;
- `etudecas_simulation` : moteur, données et tests du périmètre attribué ;
- `etudecas_map` : payloads, carte et interactions ;
- `etudecas_validator` : contre-vérification indépendante et preuves.

Les skills installés sont dans [`.agents/skills/`](../.agents/skills/) :
`etudecas-orchestrate`, `etudecas-qualify` et `etudecas-map-review`.
Le modèle et l'effort sont hérités du parent ; aucun SDK ou service externe
n'est nécessaire à cette orchestration.

Pour des couches indépendantes, attribuer des objectifs observables et des
périmètres d'écriture disjoints. Le parent intègre les changements et vérifie
leurs preuves sur les sources stabilisées. Pour une correction simple,
travailler directement.

## Vérification

Suivre la [procédure de validation](../etudecas/docs/TEST_VALIDATION.md).
Relire les cas et fixtures, puis sélectionner des identifiants précis.
Ne pas lancer de suite globale ni les anciens essais d'altération de fichiers,
de dates ou de disparition simulée. En cas d'alerte ou de refus d'écriture,
arrêter les exécutions concernées et diagnostiquer en lecture seule.

Préserver les unités physiques entières, les sécurités sources du nominal,
les deux suivis de lots et la séparation entre observation et simulation.
Ne pas inventer de donnée industrielle manquante.

## Historique

Les anciens rôles documentaires, prompts et skills sont conservés dans les
[archives](../etudecas/archive/README.md). Ils ne constituent plus le routage
courant. Toute restitution précise les changements, les contrôles réellement
exécutés, leurs preuves et les limites.
