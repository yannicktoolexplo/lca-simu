# Realistic Annual Sensitivity Study

## Method
- Horizon: 365 days
- Baseline: annual simulation current setup
- Local sensitivity: calibrated perturbations around baseline
- Stress tests: adverse scenarios separated from local elasticities
- Supplier scope: 27 active suppliers -> SDC-VD0914690A, SDC-1450, SDC-VD0525412A, SDC-VD0901566A, SDC-VD0993480A, SDC-VD0914360C, SDC-VD0508918A, SDC-VD0949099A, SDC-VD0520132A, SDC-VD0960508A, SDC-VD0989480A, SDC-VD1095770A, SDC-VD0520115A, SDC-VD0910216A, SDC-VD0972460A, SDC-VD0975221A, SDC-VD0505677A, SDC-VD0951020A, SDC-VD1091642A, SDC-VD0519670A, SDC-VD0518684A, SDC-VD0514881A, SDC-VD0990780A, SDC-VD0500655A, SDC-VD0914320A, SDC-VD1096202A, SDC-VD0964290A
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
- Lead time fournisseur SDC-VD0520132A: elasticity=-0.03427037287457533
- Capacite SDC-1450: elasticity=0.0011564102109976916
- Fiabilite fournisseur SDC-VD0949099A: elasticity=0.0010834834409361289

### Ending backlog
- Fiabilite fournisseur globale: elasticity=-77.46594097460527
- Capacite globale: elasticity=-3.6481660947151653
- Demande 268967: elasticity=3.079272477693891
- Demande 268091: elasticity=2.8553534660260804
- Capacite M-1810: elasticity=-2.199039121482497
- Lead time global: elasticity=1.5684317089910769
- Capacite M-1430: elasticity=-1.4083733699382268
- Lead time fournisseur SDC-VD0520132A: elasticity=0.8544955387783114
- Capacite SDC-1450: elasticity=-0.040753603294440076
- Debit fournisseur SDC-VD0972460A: elasticity=0.02037680164722005

### Total cost
- Capacite globale: elasticity=0.8743534421265323
- Capacite SDC-1450: elasticity=0.7669253668383528
- Lead time global: elasticity=0.6179895993477913
- Lead time fournisseur SDC-VD0949099A: elasticity=0.2960175252346856
- Lead time fournisseur SDC-VD0960508A: elasticity=0.2960175252346856
- Lead time fournisseur SDC-VD0972460A: elasticity=0.29600591239579416
- Lead time fournisseur SDC-VD0975221A: elasticity=0.2954680926448901
- Demande 268967: elasticity=0.23071660552823287
- Cout transport global: elasticity=0.2144675836150852
- Fiabilite fournisseur SDC-VD0914690A: elasticity=-0.13481977194798478

## Top Stress Impacts

### Fill rate drops
- Fiabilite fournisseur globale: delta_fill_rate=-0.282083
- Demande 268967: delta_fill_rate=-0.08588300000000004
- Capacite M-1430: delta_fill_rate=-0.06492300000000006
- Fiabilite fournisseur SDC-1450: delta_fill_rate=-0.06409900000000002
- Demande 268091: delta_fill_rate=-0.019181000000000004
- Lead time global: delta_fill_rate=-0.01683699999999999
- Lead time fournisseur SDC-VD0520132A: delta_fill_rate=-0.016436000000000006
- Capacite M-1810: delta_fill_rate=-0.014970000000000039
- Capacite SDC-1450: delta_fill_rate=-0.0025610000000000355
- Lead time fournisseur SDC-VD0951020A: delta_fill_rate=-0.001358999999999999

### Backlog increases
- Fiabilite fournisseur globale: delta_backlog=5831.3412
- Demande 268967: delta_backlog=1837.65
- Capacite M-1430: delta_backlog=1203.8625
- Fiabilite fournisseur SDC-1450: delta_backlog=1177.283
- Demande 268091: delta_backlog=480.1500000000001
- Lead time global: delta_backlog=318.36030000000005
- Lead time fournisseur SDC-VD0520132A: delta_backlog=316.25
- Capacite M-1810: delta_backlog=287.6
- Capacite SDC-1450: delta_backlog=47.5
- Lead time fournisseur SDC-VD0951020A: delta_backlog=25.75

### Cost increases
- Lead time fournisseur SDC-VD0949099A: delta_cost=739728.8094999995
- Lead time fournisseur SDC-VD0960508A: delta_cost=739728.8094999995
- Lead time fournisseur SDC-VD0972460A: delta_cost=739722.9024999999
- Lead time fournisseur SDC-VD0975221A: delta_cost=739722.9024999999
- Cout transport global: delta_cost=727282.4454999994
- Lead time global: delta_cost=669370.4037999995
- Demande 268967: delta_cost=257210.96699999832
- Lead time fournisseur SDC-VD0914690A: delta_cost=55375.54899999872
- Demande 268091: delta_cost=21165.852699998766
- Fiabilite fournisseur SDC-VD0525412A: delta_cost=5153.316599998623

## Files
- local_cases.csv
- stress_cases.csv
- local_elasticities.csv
- stress_impacts.csv
- realistic_sensitivity_summary.json
