# Prompt Codex - Audit multi-agent courant

Lis le vrai repo `etudecas` et le guide `etudecas_codex_multiagent_pack/AGENTS.md`.

Objectif : verifier que la demande est traitee avec les bons roles agents sans
creer de refactor massif inutile.

Utilise des sous-agents seulement si les questions sont independantes :

- simulation ;
- lot_trace ;
- sensitivity ;
- map_payload ;
- data_knowledge ;
- validation.

Chaque sous-agent doit produire :

1. fichiers inspectes ;
2. probleme concret detecte ;
3. correction ou recommandation ;
4. tests ou controles a executer ;
5. risque residuel.

Synthese attendue :

- role principal ;
- roles secondaires utiles ;
- fichiers a modifier ;
- tests minimaux ;
- artefacts a conserver ou supprimer.
