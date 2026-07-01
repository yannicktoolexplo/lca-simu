# Prompt Codex — Validation données générique

Tu es l’agent data du repo `etudecas`.

Objectif : créer une validation générique des datasets.

À faire :
- inspecter les chargements de données existants ;
- identifier les colonnes utilisées ;
- créer un schema YAML ;
- créer `DataValidator` ;
- ajouter des tests avec dataset valide et dataset invalide.

Contraintes :
- aucune colonne métier codée en dur dans `DataValidator` ;
- toutes les règles doivent venir du YAML ;
- les erreurs doivent indiquer colonne, règle, sévérité.

Livrables :
- `etudecas/data/validator.py` ;
- `configs/schemas/current_schema.yaml` ;
- `tests/test_data_validator.py`.
