# Supplier Criticality

Cette brique transforme les sorties de simulation `etudecas` en KPI hebdomadaires
fournisseur-article-site orientes criticite, resilience et decision.

Elle complete le POC `etudecas/prototypes/prediction` sans le remplacer:

- `prototypes/prediction` montre une architecture predictive sur historique synthetique.
- `risk/supplier_criticality` lit les sorties de simulation reelles et produit un panel
  exploitable pour un MVP KPI.

## Lancer

```powershell
python etudecas/risk/supplier_criticality/build_supplier_criticality.py
```

Par defaut, le script lit:

`etudecas/simulation/result/_codex_lot_trace_5y_risk_portfolio`

et ecrit dans:

`etudecas/risk/supplier_criticality/result`

Pour aligner les KPI risques avec une carte de simulation precise, passer le
repertoire du run:

```powershell
python etudecas/risk/supplier_criticality/build_supplier_criticality.py `
  --sim-result-dir etudecas/simulation/result/<run_id> `
  --output-dir etudecas/risk/supplier_criticality/result
```

## Sorties

- `supplier_item_week_panel.csv`: panel hebdomadaire fournisseur-article-site
- `supplier_item_risk_kpi.csv`: derniere photo KPI par couple fournisseur-article-site
- `supplier_risk_kpi.csv`: aggregation fournisseur
- `supplier_risk_kpi_summary.json`: metadata et compteurs
- `supplier_risk_kpi_report.md`: rapport court pour lecture metier

## Integration carte et arbres KPI

`etudecas/visualization/maps/build_supplychain_worldmap.py` lit ces sorties
par defaut et les integre a deux endroits:

- bouton `Arbres KPI`: famille `Risques fournisseurs`;
- mode carte `Risques`: panneaux fournisseur/site avec risque, incertitude,
  resilience, trajectoire hebdomadaire et decision robuste.

## Cadre operationnel

Le script applique une boucle simple:

`KPI normalises -> risque probabiliste -> incertitude -> resilience -> decision robuste`

Les principales familles de colonnes sont:

- performance: `performance_score_current`, `performance_distance_score`
- risque: `risk_probability_proxy_4w`, `action_priority_score`
- incertitude: `risk_probability_low_proxy_4w`, `risk_probability_high_proxy_4w`, `uncertainty_pressure`
- resilience: `resilience_score`, `time_to_recover_weeks_proxy`, `performance_drop_proxy`
- dynamique: `change_point_score`, `early_warning_score`
- decision: `decision_zone`, `robust_decision`

Les classeurs d'audit fournisseur déposés dans `etudecas/data/source/` sont reliés
aux nœuds `SDC-VD...`. La carte affiche séparément le rang structurel comparable
sur toute la population, l'indice d'audit réel et un indice croisé indicatif
`70 % structurel / 30 % audit`. Cet indice indicatif ne modifie pas le classement.

La fiche cartographique sépare l'audit de la criticité simulée et reproduit les
trois radars du Dashboard sur les six familles, avec leurs seuils de maturité
`75 %`, criticité `15/100` et résilience `70 semaines`.

Pour les fournisseurs sans trame renseignée, les 28 critères sont estimés par
proxy à partir des flux, délais, mono-source, exposition réseau et signaux publics.
Ils portent le statut `estimation proxy`, une confiance explicite, ne comptent
jamais comme réponses d'audit et ne modifient pas la criticité structurelle.
Les réussites, certifications, incidents, fragilités et informations
réglementaires effectivement retenus sont traçables dans
`etudecas/data/source/supplier_public_evidence.csv` et dans l'onglet
`Contexte public` de chaque fiche, avec date et portée. Les URL sont conservées
uniquement dans le registre interne et ne sont pas embarquées dans la carte.

## Lecture correcte

La baseline de simulation actuelle ne contient pas assez d'incidents observables
retard/rupture pour entrainer une probabilite supervisee. Le champ
`risk_probability_proxy_4w` est donc une probabilite proxy construite a partir de
signaux de pression: criticite, mono-source, couverture stock vs lead time,
utilisation capacite, volatilite, sensibilite et qualite de donnees.

La prochaine etape industrielle consiste a remplacer ce proxy par une probabilite
calibree sur incidents reels ou sur campagnes Monte Carlo/stress tests.
