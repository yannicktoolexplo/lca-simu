# AGENTS.md — etudecas

## Objectif du projet

`etudecas` est un moteur générique de cas d’étude pour analyser des systèmes dynamiques, des KPI, des trajectoires de performance, des scénarios et des visualisations.

Le projet ne doit pas produire du code one-shot pour un seul dataset. Toute logique spécifique à un cas doit être décrite dans une configuration, pas codée en dur.

## Règle principale

Avant toute modification, Codex doit identifier si la demande concerne :

- architecture ;
- données ;
- KPI / métier ;
- simulation ;
- trajectoire ;
- visualisation ;
- validation ;
- tests ;
- documentation.

Codex doit ensuite traiter la tâche avec le rôle approprié dans `docs/agents/`.

## Rôles spécialisés

- Architecture : suivre `docs/agents/architecte.md`.
- Données : suivre `docs/agents/data_agent.md`.
- KPI / métier : suivre `docs/agents/kpi_agent.md`.
- Visualisation : suivre `docs/agents/viz_agent.md`.
- Validation résultat : suivre `docs/agents/result_validator_agent.md`.
- Validation visuelle : suivre `docs/agents/visual_validator_agent.md`.
- Tests : suivre `docs/agents/test_agent.md`.
- Revue finale : suivre `docs/agents/reviewer.md`.
- Orchestration multi-agent : suivre `docs/agents/orchestrateur.md`.

## Interdits

Ne pas :

- coder des noms de colonnes métier en dur dans le moteur ;
- mettre la logique métier dans un notebook ;
- créer une visualisation utilisable pour un seul fichier uniquement ;
- ajouter une fonctionnalité sans test ;
- modifier plusieurs couches à la fois sans plan ;
- supprimer du code existant sans expliquer l’impact ;
- produire des résultats numériques sans validation ;
- modifier `data/raw/` ;
- versionner des sorties lourdes dans `outputs/`.

## Architecture attendue

```text
configs/   = ce qui change d’un cas à l’autre
etudecas/  = moteur Python générique
tests/     = preuves automatiques que le moteur marche
notebooks/ = exploration uniquement
outputs/   = artefacts générés, non source de vérité
```

## Critères de qualité

Une modification est acceptable seulement si :

- les tests existants passent ;
- les nouveaux comportements sont testés ;
- les fonctions sont génériques ;
- les entrées/sorties sont typées ou documentées ;
- les erreurs sont explicites ;
- les visualisations sont configurables ;
- les résultats sont reproductibles ;
- la logique métier reste dans YAML.

## Commandes de vérification

À lancer avant de conclure une tâche :

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Si une commande n’existe pas encore dans le projet, Codex doit proposer son ajout au lieu de l’inventer.

## Stratégie de PR

Découper les changements en PR courtes :

1. Structure projet et contrats.
2. Validation données générique.
3. Moteur KPI configurable.
4. Génération de trajectoires.
5. Visualisations génériques.
6. Vérification automatique des résultats.
7. Vérification automatique des visuels.
8. Documentation et exemples.

## Format de résumé attendu par Codex

Chaque tâche doit se terminer par :

```text
Changements réalisés :
- ...

Tests exécutés :
- ...

Risques / limites :
- ...

Prochaine étape recommandée :
- ...
```
