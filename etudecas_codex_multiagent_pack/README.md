# etudecas — pack Codex multi-agent

Ce pack donne une base prête à déposer dans le repo `etudecas` pour piloter Codex comme une équipe de développement structurée.

Il contient :

- `AGENTS.md` : règles permanentes du repo pour Codex ;
- `docs/agents/*.md` : rôles spécialisés à utiliser comme sous-agents ;
- `docs/prompts/*.md` : prompts prêts à copier dans Codex ;
- `configs/*` : exemples de cas, schémas, visualisations et règles de validation ;
- `etudecas/*` : squelette Python générique ;
- `tests/*` : tests minimaux pour verrouiller la généricité ;
- `data/reference/*` : petits jeux de données de référence.

## Installation locale

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m pytest
```

## Usage minimal

```bash
python -m etudecas.cli configs/cases/fal_aircraft.yaml
```

La règle principale est simple :

```text
Le moteur Python reste générique.
Le cas métier vit dans YAML.
Les résultats et les visuels sont validés automatiquement.
Les notebooks ne sont pas la source de vérité.
Chaque changement a un test.
```

## Premier prompt à lancer dans Codex

```text
Lis le repo etudecas et applique AGENTS.md.
Je veux passer d’un projet one-shot à un moteur générique de cas d’étude.
Utilise les rôles dans docs/agents/*.md.
Ne modifie aucun fichier applicatif dans cette première passe.
Produis un audit architecture, données, KPI, visualisation, tests et reviewer.
```
