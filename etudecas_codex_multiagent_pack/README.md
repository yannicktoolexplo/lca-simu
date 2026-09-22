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
- `native/` : configuration, profils et skills natifs prets a deployer a la racine.

Le [guide operationnel](../etudecas/docs/MULTI_AGENT_OPERATIONNEL.md) decrit la
toolbox `python -m etudecas.toolbox`, ses preuves et le contrat de delegation.
La presence du staging ne suffit pas a prouver son installation : executer
`python -m etudecas.toolbox doctor` depuis la racine du depot.

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

`pytest` est une dependance de developpement. `pandas`, `pyyaml` et `Pillow`
font partie des dependances d'execution du mini-kit.

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
python -m etudecas.toolbox tests --path etudecas/testing/test_report.py
```

## Premier prompt utile

```text
Lis etudecas_codex_multiagent_pack/AGENTS.md.
La tache concerne le vrai repo Etudecas, pas le mini-kit.
Utilise les profils natifs etudecas_explorer, etudecas_simulation,
etudecas_map et etudecas_validator selon le travail independant disponible.
Attribue des perimetres disjoints, implemente et fournis les manifestes des tests.
```

## Skills disponibles

Les six skills ci-dessous restent des references du pack ; ils ne sont pas
automatiquement decouverts depuis ce dossier. Le deploiement `native/`
fournit trois skills projet actifs documentes dans le guide operationnel.

- `etudecas-simulation`
- `etudecas-lot-trace`
- `etudecas-sensitivity`
- `etudecas-map-payload`
- `etudecas-data-knowledge`
- `etudecas-validation`
