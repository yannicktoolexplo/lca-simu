# Prompt Codex - Simulation contracts

Tu es l'agent simulation du vrai repo Etudecas.

Objectif : faire evoluer les contrats de simulation sans casser les runs
existants.

A inspecter :

- `etudecas/simulation/engine/api.py`
- `etudecas/simulation/engine/contracts.py`
- `etudecas/simulation/engine/run_first_simulation.py`
- tests `etudecas/simulation/test_engine*.py`

A faire :

- verifier que les overrides sont explicites ;
- ajouter ou corriger un contrat si necessaire ;
- garder les sorties compactes ;
- ajouter un test court.

Refus :

- pas de nouvelle regle metier cachee dans un default ;
- pas de gros output versionne.
