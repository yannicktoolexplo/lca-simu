# Prediction POC

Ce dossier contient un proof of concept pour passer d'un score structurel a une vraie logique de prediction de risque fournisseur-matiere.

## Ce que fait le POC
- reutilise les couples fournisseur-matiere de l'etude simulation
- genere un historique synthetique hebdomadaire
- entraine un modele probabiliste (`LogisticRegression`)
- calibre les probabilites
- combine `probabilite predite x impact supply`
- produit des CSV, un rapport et des PNG

## Lancer
```bash
python etudecas/Prediction/run_prediction_poc.py
```

## Sorties principales
- `data/synthetic_supplier_item_history.csv`
- `result/predicted_supplier_item_risk.csv`
- `result/predicted_supplier_risk.csv`
- `result/evaluation_metrics.json`
- `result/prediction_poc_report.md`

## Limite principale
Le POC utilise des donnees synthetiques pour la partie historique/labels.
L'objectif est de valider l'architecture, pas de produire une calibration industrielle finale.
