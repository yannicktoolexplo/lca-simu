# Realistic Annual Sensitivity Study

## Method
- Horizon: 365 days
- Baseline: annual simulation current setup
- Local sensitivity: calibrated perturbations around baseline
- Stress tests: adverse scenarios separated from local elasticities
- Supplier scope: 6 active suppliers -> SDC-VD0914690A, SDC-1450, SDC-VD0525412A, SDC-VD0901566A, SDC-VD0993480A, SDC-VD0914360C
- Artifact mode: compact

## Baseline
- Fill rate: 0.959867
- Ending backlog: 728.5
- Total cost: 13564426.5346
- External procured qty: 0.0
- Avg inventory: 4656606.0037

## Deterministic Check
- Status: pass
- Max absolute KPI diff baseline vs repeat: 0.0

## Top Local Elasticities

### Fill rate
- Fiabilite fournisseur globale: elasticity=2.997436103126785
- Capacite globale: elasticity=0.145832703905853
- Demande 268967: elasticity=-0.10307157137395072
- Demande 268091: elasticity=-0.09457039360661439
- Capacite M-1810: elasticity=0.08826222799617059
- Lead time global: elasticity=-0.06308686515944444
- Capacite M-1430: elasticity=0.05652866490878462
- Capacite SDC-1450: elasticity=0.0011564102109976916
- Stock fournisseur global: elasticity=-0.0005521598304767767
- Cout transport global: elasticity=0.0

### Ending backlog
- Fiabilite fournisseur globale: elasticity=-77.46594097460527
- Capacite globale: elasticity=-3.6481660947151653
- Demande 268967: elasticity=3.079272477693891
- Demande 268091: elasticity=2.8553534660260804
- Capacite M-1810: elasticity=-2.199039121482497
- Lead time global: elasticity=1.5684317089910769
- Capacite M-1430: elasticity=-1.4083733699382268
- Capacite SDC-1450: elasticity=-0.040753603294440076
- Stock fournisseur global: elasticity=0.013726835964310222
- Cout transport global: elasticity=0.0

### Total cost
- Capacite globale: elasticity=0.8743534421265323
- Capacite SDC-1450: elasticity=0.7669253668383528
- Lead time global: elasticity=0.6179895993477913
- Demande 268967: elasticity=0.23071660552823287
- Cout transport global: elasticity=0.2144675836150852
- Fiabilite fournisseur SDC-VD0914690A: elasticity=-0.13481977194798478
- Debit fournisseur global: elasticity=-0.1188925119603331
- Debit fournisseur SDC-VD0914690A: elasticity=-0.11265676419139997
- Capacite M-1430: elasticity=0.106321704962702
- Fiabilite fournisseur globale: elasticity=-0.07045991288773507

## Top Stress Impacts

### Fill rate drops
- Fiabilite fournisseur globale: delta_fill_rate=-0.282083
- Demande 268967: delta_fill_rate=-0.08588300000000004
- Capacite M-1430: delta_fill_rate=-0.06492300000000006
- Fiabilite fournisseur SDC-1450: delta_fill_rate=-0.06409900000000002
- Demande 268091: delta_fill_rate=-0.019181000000000004
- Lead time global: delta_fill_rate=-0.01683699999999999
- Capacite M-1810: delta_fill_rate=-0.014970000000000039
- Capacite SDC-1450: delta_fill_rate=-0.0025610000000000355
- Cout transport global: delta_fill_rate=0.0
- Debit fournisseur SDC-1450: delta_fill_rate=0.0

### Backlog increases
- Fiabilite fournisseur globale: delta_backlog=5831.3412
- Demande 268967: delta_backlog=1837.65
- Capacite M-1430: delta_backlog=1203.8625
- Fiabilite fournisseur SDC-1450: delta_backlog=1177.283
- Demande 268091: delta_backlog=480.1500000000001
- Lead time global: delta_backlog=318.36030000000005
- Capacite M-1810: delta_backlog=287.6
- Capacite SDC-1450: delta_backlog=47.5
- Cout transport global: delta_backlog=0.0
- Debit fournisseur SDC-1450: delta_backlog=0.0

### Cost increases
- Cout transport global: delta_cost=727282.4454999994
- Lead time global: delta_cost=669370.4037999995
- Demande 268967: delta_cost=257210.96699999832
- Lead time fournisseur SDC-VD0914690A: delta_cost=55375.54899999872
- Demande 268091: delta_cost=21165.852699998766
- Fiabilite fournisseur SDC-VD0525412A: delta_cost=5153.316599998623
- Lead time fournisseur SDC-VD0525412A: delta_cost=2464.798699999228
- Debit fournisseur SDC-VD0525412A: delta_cost=925.1927999984473
- Debit fournisseur SDC-1450: delta_cost=737.931099999696
- Lead time fournisseur SDC-1450: delta_cost=193.40689999982715

## Files
- local_cases.csv
- stress_cases.csv
- local_elasticities.csv
- stress_impacts.csv
- realistic_sensitivity_summary.json
