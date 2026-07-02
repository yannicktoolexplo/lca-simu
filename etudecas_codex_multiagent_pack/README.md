# Etudecas Codex Multi-Agent Pack

Ce dossier est un kit d'orchestration pour developper le vrai repo Etudecas
avec des sous-agents specialises. Il ne remplace pas le package principal
`etudecas`.

## Contenu

- `AGENTS.md` : regles de routage multi-agent pour Etudecas ;
- `docs/agents/*.md` : roles operationnels ;
- `skills/*/SKILL.md` : skills Codex reutilisables par domaine Etudecas ;
- `docs/prompts/*.md` : prompts de travail reutilisables ;
- `configs/*` : exemples generiques de cas, schemas et visuals ;
- `etudecas_agentkit/*` : mini-kit de reference sans collision avec le vrai
  package `etudecas` ;
- `tests/*` : tests du mini-kit de reference ;
- `data/reference/*` : petits jeux de donnees.

## Regle de fond

```text
Le moteur Python reste generique.
Le cas metier vit dans les donnees, les configs ou le knowledge graph.
Les resultats lourds ne sont pas source de verite.
Une simulation ou sensibilite doit etre regenerable par script.
Chaque changement important a un test ou un controle objectif.
```

## Installation du mini-kit de reference

Le mini-kit est optionnel. Il sert a tester des contrats generiques hors du
vrai package `etudecas`.

```powershell
cd etudecas_codex_multiagent_pack
python -m pip install -e ".[dev]"
python -m pytest
```

Sans dependances dev, les tests peuvent echouer sur `pytest`, `pandas` ou
`pyyaml`. Ce n'est pas bloquant pour le repo principal.

## Usage minimal du mini-kit

```powershell
python -m etudecas_agentkit.cli configs/cases/example_minimal.yaml
```

## Usage recommande dans le vrai repo

1. Lire `AGENTS.md`.
2. Choisir le role principal.
3. Deleguer uniquement les taches independantes.
4. Modifier le vrai code dans `../etudecas`, pas le squelette du pack.
5. Valider avec les tests du repo principal :

```powershell
python -m unittest discover -s etudecas -p "test*.py" -v
```

## Premier prompt utile

```text
Lis etudecas_codex_multiagent_pack/AGENTS.md.
La tache concerne le vrai repo Etudecas, pas le mini-kit.
Choisis les agents utiles parmi simulation, lot_trace, sensitivity, map_payload,
data_knowledge et validation. Propose un perimetre court, puis implemente avec
tests.
```

## Skills disponibles

- `etudecas-simulation`
- `etudecas-lot-trace`
- `etudecas-sensitivity`
- `etudecas-map-payload`
- `etudecas-data-knowledge`
- `etudecas-validation`
