# Prompt Codex — Validation automatique des visuels

Tu es l’agent visual validator.

Objectif : créer des contrôles automatiques sur les figures générées.

À vérifier :
- fichier existe ;
- fichier non vide ;
- dimensions image correctes ;
- titre présent dans la spec ;
- axes présents dans la spec ;
- nombre de points attendu ;
- absence de NaN dans les données tracées ;
- cohérence entre dimensions de la figure et `visual_spec`.

Livrables :
- `etudecas/validation/visual_checks.py` ;
- `tests/test_visual_checks.py` ;
- `outputs/reports/visual_report.json`.
