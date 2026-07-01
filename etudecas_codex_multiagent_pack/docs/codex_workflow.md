# Workflow Codex recommandé

## 1. Audit sans modification

Utiliser `docs/prompts/00_audit_multiagent.md`.

## 2. Mise en place des règles

Utiliser `docs/prompts/01_create_agents_docs.md`.

## 3. Refactor incrémental

Appliquer les PR dans l’ordre de `docs/roadmap.md`.

## 4. Revue GitHub

Sur chaque PR, demander :

```text
@codex review
```

avec le focus défini dans `docs/prompts/08_github_review.md`.

## 5. Garde-fou permanent

Un cas métier doit pouvoir changer sans modifier le moteur Python.
