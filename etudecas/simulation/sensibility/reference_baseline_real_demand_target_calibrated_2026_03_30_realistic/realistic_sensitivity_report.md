# Realistic Annual Sensitivity Study

## Method
- Horizon: 0 days
- Baseline: annual simulation current setup
- Local sensitivity: calibrated perturbations around baseline
- Stress tests: adverse scenarios separated from local elasticities
- Supplier scope: 8 active suppliers -> SDC-VD0914690A, SDC-1450, SDC-VD0901566A, SDC-VD0914360C, SDC-VD0525412A, SDC-VD0993480A, SDC-VD0508918A, SDC-VD0949099A
- Artifact mode: compact

## Baseline
- Fill rate: 0.888075
- Ending backlog: 593478.1966
- Total cost: 27920896.5609
- External procured qty: 0.0
- Avg inventory: 19766465.3509

## Deterministic Check
- Status: pass
- Max absolute KPI diff baseline vs repeat: 0.0

## Top Local Elasticities

### Fill rate
- Fiabilite fournisseur globale: elasticity=2.1026377276693937
- Capacite globale: elasticity=0.35239140838330146
- Capacite M-1810: elasticity=0.21815725023224372
- Capacite M-1430: elasticity=0.20918278298567183
- Fiabilite fournisseur SDC-VD0914690A: elasticity=-0.16039185879571133
- Debit fournisseur SDC-VD0508918A: elasticity=0.14822509360132863
- Demande 268967: elasticity=-0.1348872561439063
- Fiabilite fournisseur SDC-VD0949099A: elasticity=0.10314444162936494
- Demande 268091: elasticity=-0.09472172958364972
- Fiabilite fournisseur SDC-VD0901566A: elasticity=0.09332545111617649

### Ending backlog
- Fiabilite fournisseur globale: elasticity=-16.683402993949166
- Capacite globale: elasticity=-2.7960664646260383
- Capacite M-1810: elasticity=-1.7309804974897707
- Capacite M-1430: elasticity=-1.6597893480220218
- Demande 268091: elasticity=1.4377542231346734
- Demande 268967: elasticity=1.3849719083344665
- Fiabilite fournisseur SDC-VD0914690A: elasticity=1.2727270526992773
- Debit fournisseur SDC-VD0508918A: elasticity=-1.176075790144705
- Fiabilite fournisseur SDC-VD0949099A: elasticity=-0.8182996119861164
- Fiabilite fournisseur SDC-VD0901566A: elasticity=-0.7403748790052828

### Total cost
- Capacite globale: elasticity=0.7307327832936292
- Cout transport global: elasticity=0.39998434289675977
- Capacite SDC-1450: elasticity=0.374679880181569
- Capacite M-1430: elasticity=0.35884663836443104
- Lead time global: elasticity=0.2877241019276585
- Debit fournisseur SDC-VD0508918A: elasticity=0.2830769792710851
- Demande 268967: elasticity=0.2069975869289815
- Fiabilite fournisseur globale: elasticity=0.155999420738499
- Fiabilite fournisseur SDC-VD0914360C: elasticity=0.11763045870809724
- Fiabilite fournisseur SDC-VD0508918A: elasticity=0.11193873023321092

## Top Stress Impacts

### Fill rate drops
- Fiabilite fournisseur globale: delta_fill_rate=-0.171948
- Debit fournisseur SDC-VD0901566A: delta_fill_rate=-0.11757399999999996
- Capacite M-1810: delta_fill_rate=-0.047090999999999994
- Demande 268091: delta_fill_rate=-0.04012099999999996
- Demande 268967: delta_fill_rate=-0.029630999999999963
- Capacite M-1430: delta_fill_rate=-0.018819999999999948
- Fiabilite fournisseur SDC-VD0901566A: delta_fill_rate=-0.018113999999999963
- Debit fournisseur SDC-VD0508918A: delta_fill_rate=-0.010457999999999967
- Lead time fournisseur SDC-1450: delta_fill_rate=-0.007916999999999952
- Lead time fournisseur SDC-VD0914690A: delta_fill_rate=-0.00634099999999993

### Backlog increases
- Fiabilite fournisseur globale: delta_backlog=911746.965
- Debit fournisseur SDC-VD0901566A: delta_backlog=623427.2984999999
- Demande 268091: delta_backlog=322008.72899999993
- Capacite M-1810: delta_backlog=249698.78500000003
- Demande 268967: delta_backlog=205500.90819999995
- Capacite M-1430: delta_backlog=99791.64489999996
- Fiabilite fournisseur SDC-VD0901566A: delta_backlog=96049.51939999999
- Debit fournisseur SDC-VD0508918A: delta_backlog=55452.94990000001
- Lead time fournisseur SDC-1450: delta_backlog=41980.99170000001
- Lead time fournisseur SDC-VD0914690A: delta_backlog=33621.5368

### Cost increases
- Cout transport global: delta_cost=2791980.366100002
- Demande 268967: delta_cost=969935.2944000028
- Lead time global: delta_cost=465101.0642000027
- Lead time fournisseur SDC-VD0949099A: delta_cost=448680.6526999995
- Fiabilite fournisseur SDC-1450: delta_cost=118862.6064000018
- Fiabilite fournisseur SDC-VD0914690A: delta_cost=102608.68670000136
- Fiabilite fournisseur SDC-VD0525412A: delta_cost=84845.8973999992
- Demande 268091: delta_cost=69692.46209999919
- Debit fournisseur SDC-VD0525412A: delta_cost=48420.650400001556
- Debit fournisseur SDC-VD0993480A: delta_cost=31141.022100001574

## Files
- local_cases.csv
- stress_cases.csv
- local_elasticities.csv
- stress_impacts.csv
- realistic_sensitivity_summary.json
