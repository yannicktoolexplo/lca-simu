# Realistic Annual Sensitivity Study

## Method
- Horizon: 365 days
- Baseline: annual simulation current setup
- Local sensitivity: calibrated perturbations around baseline
- Stress tests: adverse scenarios separated from local elasticities
- Supplier scope: 8 active suppliers -> SDC-VD0914690A, SDC-1450, SDC-VD0525412A, SDC-VD0914360C, SDC-VD0901566A, SDC-VD0993480A, SDC-VD0508918A, SDC-VD0949099A

## Baseline
- Fill rate: 0.901702
- Ending backlog: 1710.3884
- Total cost: 15310958.7581
- External procured qty: 615226.4196
- Avg inventory: 1028769.1852

## Deterministic Check
- Status: pass
- Max absolute KPI diff baseline vs repeat: 0.0

## Top Local Elasticities

### Fill rate
- Fiabilite fournisseur globale: elasticity=1.874455196949766
- Fiabilite fournisseur SDC-VD0949099A: elasticity=-0.13949176113616213
- Demande 268967: elasticity=-0.11695659985227931
- Demande 268091: elasticity=-0.10919904802251716
- Fiabilite fournisseur SDC-1450: elasticity=-0.0837083648478087
- Fiabilite fournisseur SDC-VD0508918A: elasticity=-0.0837083648478087
- Fiabilite fournisseur SDC-VD0525412A: elasticity=-0.0837083648478087
- Fiabilite fournisseur SDC-VD0914360C: elasticity=-0.0837083648478087
- Fiabilite fournisseur SDC-VD0901566A: elasticity=-0.05580557656520581
- Fiabilite fournisseur SDC-VD0914690A: elasticity=-0.05580557656520581

### Ending backlog
- Fiabilite fournisseur globale: elasticity=-17.19463719468629
- Demande 268967: elasticity=1.6125635557397375
- Demande 268091: elasticity=1.5391486518500703
- Fiabilite fournisseur SDC-VD0949099A: elasticity=1.2797093338565668
- Fiabilite fournisseur SDC-1450: elasticity=0.7678256003139395
- Fiabilite fournisseur SDC-VD0508918A: elasticity=0.7678256003139395
- Fiabilite fournisseur SDC-VD0525412A: elasticity=0.7678256003139395
- Fiabilite fournisseur SDC-VD0914360C: elasticity=0.7678256003139395
- Fiabilite fournisseur SDC-VD0901566A: elasticity=0.5118837335426272
- Fiabilite fournisseur SDC-VD0914690A: elasticity=0.5118837335426272

### Total cost
- Capacite globale: elasticity=1.0180830424321743
- Capacite SDC-1450: elasticity=0.9377361814396061
- Lead time global: elasticity=0.9339980786594839
- Lead time fournisseur SDC-VD0949099A: elasticity=0.4475430418016701
- Capacite M-1430: elasticity=0.06238690797169504
- Lead time fournisseur SDC-VD0914690A: elasticity=0.025835238161733765
- Fiabilite fournisseur SDC-VD0525412A: elasticity=0.02490334315597823
- Fiabilite fournisseur SDC-VD0914360C: elasticity=0.02414968937228534
- Cout transport global: elasticity=0.022729214152960163
- Fiabilite fournisseur globale: elasticity=-0.02225550727316385

## Top Stress Impacts

### Fill rate drops
- Fiabilite fournisseur globale: delta_fill_rate=-0.16928600000000005
- Demande 268967: delta_fill_rate=-0.05921200000000004
- Demande 268091: delta_fill_rate=-0.056925
- Capacite M-1810: delta_fill_rate=-0.04649300000000001
- Capacite M-1430: delta_fill_rate=-0.04159400000000002
- Stock fournisseur global: delta_fill_rate=-0.0012579999999999814
- Capacite SDC-1450: delta_fill_rate=0.0
- Cout transport global: delta_fill_rate=0.0
- Debit fournisseur SDC-1450: delta_fill_rate=0.0
- Debit fournisseur SDC-VD0508918A: delta_fill_rate=0.0

### Backlog increases
- Fiabilite fournisseur globale: delta_backlog=2945.5677000000005
- Demande 268967: delta_backlog=1304.3556
- Demande 268091: delta_backlog=1260.5795999999998
- Capacite M-1810: delta_backlog=808.9747
- Capacite M-1430: delta_backlog=723.7266999999999
- Stock fournisseur global: delta_backlog=21.88799999999992
- Capacite SDC-1450: delta_backlog=0.0
- Cout transport global: delta_backlog=0.0
- Debit fournisseur SDC-1450: delta_backlog=0.0
- Debit fournisseur SDC-VD0508918A: delta_backlog=0.0

### Cost increases
- Lead time fournisseur SDC-VD0949099A: delta_cost=1370555.6012000013
- Lead time global: delta_cost=1347232.1225000005
- Cout transport global: delta_cost=87001.51510000043
- Fiabilite fournisseur globale: delta_cost=21337.48909999989
- Capacite M-1810: delta_cost=15710.063599999994
- Fiabilite fournisseur SDC-VD0525412A: delta_cost=13306.329900000244
- Fiabilite fournisseur SDC-VD0914360C: delta_cost=12767.31220000051
- Debit fournisseur SDC-VD0914690A: delta_cost=8708.886200001463
- Stock fournisseur SDC-1450: delta_cost=6122.468100000173
- Stock fournisseur SDC-VD0949099A: delta_cost=4271.248100001365

## Files
- local_cases.csv
- stress_cases.csv
- local_elasticities.csv
- stress_impacts.csv
- realistic_sensitivity_summary.json
