# AGENTS.md - Etudecas multi-agent rules

## Objectif

Etudecas doit rester un moteur de simulation et d'analyse generique. Les cas
metier vivent dans les donnees, les configs et les graphes de connaissance. Le
code source doit permettre de regenerer les resultats au lieu de stocker des
gigaoctets d'artefacts.

## Regle principale

Avant une modification, identifier la couche principale touchee puis appliquer
le role correspondant dans `docs/agents/`.

## Roles operationnels principaux

- Orchestration : `docs/agents/orchestrateur.md`
- Simulation dynamique : `docs/agents/simulation_agent.md`
- Lotification et genealogie : `docs/agents/lot_trace_agent.md`
- Sensibilite et risques : `docs/agents/sensitivity_agent.md`
- Map, HTML et payloads : `docs/agents/map_payload_agent.md`
- Donnees et graphe de connaissance : `docs/agents/data_knowledge_agent.md`
- Validation et revue : `docs/agents/validation_agent.md`

Les anciens fichiers generiques sont ranges dans `docs/agents/reference/`. Ils
peuvent servir de references specialisees, mais ils ne sont plus le routage
principal.

## Quand utiliser plusieurs agents

Utiliser plusieurs agents seulement si les taches sont independantes :

- simulation vs affichage ;
- payload lot trace vs validation invariants ;
- sensibilite vs politique d'artefacts ;
- data/knowledge graph vs rendu carte.

Chaque agent doit avoir un perimetre clair, des fichiers a inspecter, des
livrables et des tests attendus. Eviter deux agents qui modifient le meme
module en parallele.

## Interdits

- coder une regle metier specifique dans un moteur generique sans config ;
- ajouter une sortie lourde versionnee ;
- corriger des donnees sans rapport d'enrichissement ;
- masquer une incoherence par une valeur par defaut silencieuse ;
- casser l'autonomie de la carte HTML courante sans alternative ;
- produire une conclusion numerique sans verifier les invariants ;
- confondre lot metier et evenement logistique.

## Politique d'artefacts

Par defaut, garder :

- configs ;
- inputs compacts ;
- summaries ;
- registries ;
- payloads compacts necessaires a l'affichage courant.

Ne garder les sorties completes de simulation que pour un debug court et
documente. Une etude de sensibilite doit etre regenerable par script.

## Verification minimale

Avant de conclure :

```powershell
python -m unittest discover -s etudecas -p "test*.py" -v
```

Ajouter des verifications ciblees si la carte, les payloads ou la simulation
sont touches.

## Format de synthese

Chaque tache se termine par :

```text
Changements realises :
- ...

Tests executes :
- ...

Risques / limites :
- ...

Prochaine etape recommandee :
- ...
```
