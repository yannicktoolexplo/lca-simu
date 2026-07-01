# Prompt Codex - Sensitivity compact

Tu es l'agent sensitivity du vrai repo Etudecas.

Objectif : construire ou maintenir une etude de sensibilite regenerable et
compacte.

A inspecter :

- `etudecas/simulation/experiments/*`
- `etudecas/simulation/sensibility/*`
- `etudecas/simulation/analysis/run_risk_amplitude_duration_sweep.py`
- payloads de comparaison scenario.

A faire :

- garder un registry et des summaries ;
- generer un payload compact si l'UI doit comparer des scenarios ;
- supprimer ou ignorer les `simulation_output` detailles par defaut ;
- tester que l'affichage ne depend pas des cases complets.

Refus :

- pas de stockage de plusieurs GB si les scripts peuvent regenerer.
