# Prompt Codex — Moteur KPI configurable

Tu es l’agent KPI du repo `etudecas`.

Objectif : remplacer les calculs KPI one-shot par un moteur KPI configurable.

À faire :
- créer `KPIEngine` ;
- lire les KPI depuis YAML ;
- supporter les KPI élémentaires depuis colonnes ;
- supporter les KPI composites par agrégation ;
- supporter `direction: minimize / maximize` ;
- supporter `target`, `min`, `max` ;
- ajouter tests unitaires.

Interdit :
- pas de noms de KPI codés en dur dans le moteur ;
- pas de dépendance à un cas particulier ;
- pas de visualisation dans le moteur KPI.
