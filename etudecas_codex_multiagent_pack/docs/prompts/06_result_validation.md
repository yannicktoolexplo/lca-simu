# Prompt Codex — Validation automatique des résultats

Tu es l’agent validation résultat.

Objectif : créer un système de validation automatique des résultats.

À faire :
- créer `validation_rules.yaml` ;
- créer `ResultValidator` ;
- vérifier bornes, NaN, valeurs impossibles, monotonie si requise ;
- vérifier cohérence métier ;
- générer `validation_report.json` ;
- ajouter tests.

Exemples de règles :
- un score normalisé doit être entre 0 et 1 ;
- une trajectoire ne doit pas contenir de date non ordonnée ;
- un KPI composite ne peut pas être calculé si un enfant obligatoire manque.
