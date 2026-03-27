# Threshold-Oriented Sensitivity Study

## Method
- Horizon: 365 days
- Scenario: scn:BASE
- Design: deterministic one-factor-at-a-time, multi-level sweeps
- Artifact mode: compact
- Kept detailed cases: baseline
- Service threshold: 0.950
- Soft service threshold: 0.940
- Backlog alert threshold: +25.0% vs baseline
- Cost alert threshold: +10.0% vs baseline
- Active suppliers screened individually: SDC-VD0914690A, SDC-1450, SDC-VD0525412A, SDC-VD0901566A, SDC-VD0993480A, SDC-VD0914360C, SDC-VD0508918A, SDC-VD0949099A, SDC-VD0520132A, SDC-VD0960508A, SDC-VD0989480A, SDC-VD1095770A, SDC-VD0520115A, SDC-VD0910216A, SDC-VD0972460A, SDC-VD0975221A, SDC-VD0505677A, SDC-VD0951020A, SDC-VD1091642A, SDC-VD0519670A, SDC-VD0518684A, SDC-VD0514881A, SDC-VD0990780A, SDC-VD0500655A, SDC-VD0914320A, SDC-VD1096202A, SDC-VD0964290A

## Baseline
- Fill rate: 0.959867
- Ending backlog: 728.5000
- Total cost: 13564426.5346
- External procured qty: 0.0000
- Avg inventory: 4656606.0037

## Most Critical For Service Threshold
- Debit fournisseur SDC-VD0914690A: cross<0.95 at level 0.6, safe band [0.8, 1.4], max fill drop 0.1353
- Debit fournisseur SDC-VD0993480A: cross<0.95 at level 0.6, safe band [0.8, 1.4], max fill drop 0.1257
- Debit fournisseur SDC-VD0901566A: cross<0.95 at level 0.6, safe band [0.8, 1.4], max fill drop 0.0954
- Capacite M-1430: cross<0.95 at level 0.7, safe band [1.0, 1.3], max fill drop 0.1800
- Capacite M-1810: cross<0.95 at level 0.7, safe band [1.0, 1.3], max fill drop 0.0248
- Fiabilite fournisseur globale: cross<0.95 at level 0.85, safe band [1.0, 1.0], max fill drop 0.4081
- Fiabilite fournisseur SDC-1450: cross<0.95 at level 0.85, safe band [0.95, 1.0], max fill drop 0.0641
- Demande 268967: cross<0.95 at level 1.1, safe band [0.8, 1.0], max fill drop 0.0859
- Demande 268091: cross<0.95 at level 1.2, safe band [0.8, 1.0], max fill drop 0.0192
- Lead time global: cross<0.95 at level 1.25, safe band [0.75, 1.1], max fill drop 0.0255

## Strongest Fill-Rate Effects
- Periode de revue: max fill drop 0.8244, monotonicity=decreasing, steepest segment=[1.0, 2.0]
- Fiabilite fournisseur globale: max fill drop 0.4081, monotonicity=increasing, steepest segment=[0.95, 1.0]
- Capacite M-1430: max fill drop 0.1800, monotonicity=increasing, steepest segment=[0.7, 0.85]
- Debit fournisseur SDC-VD0914690A: max fill drop 0.1353, monotonicity=increasing, steepest segment=[0.6, 0.8]
- Debit fournisseur SDC-VD0993480A: max fill drop 0.1257, monotonicity=increasing, steepest segment=[0.6, 0.8]
- Debit fournisseur SDC-VD0901566A: max fill drop 0.0954, monotonicity=increasing, steepest segment=[0.6, 0.8]
- Demande 268967: max fill drop 0.0859, monotonicity=decreasing, steepest segment=[1.1, 1.2]
- Fiabilite fournisseur SDC-1450: max fill drop 0.0641, monotonicity=increasing, steepest segment=[0.85, 0.9]
- Lead time global: max fill drop 0.0255, monotonicity=decreasing, steepest segment=[1.0, 1.1]
- Capacite M-1810: max fill drop 0.0248, monotonicity=increasing, steepest segment=[0.85, 1.0]

## Strongest Cost Effects
- Periode de revue: max total-cost increase 126351014.41, monotonicity=non_monotonic
- Cout de stock: max total-cost increase 5314677.96, monotonicity=increasing
- Lead time fournisseur SDC-VD0949099A: max total-cost increase 807327.02, monotonicity=non_monotonic
- Lead time fournisseur SDC-VD0960508A: max total-cost increase 807327.02, monotonicity=non_monotonic
- Lead time fournisseur SDC-VD0972460A: max total-cost increase 807321.11, monotonicity=non_monotonic
- Lead time fournisseur SDC-VD0975221A: max total-cost increase 807321.11, monotonicity=non_monotonic
- Lead time global: max total-cost increase 768535.80, monotonicity=non_monotonic
- Capacite M-1430: max total-cost increase 293676.41, monotonicity=increasing
- Demande 268967: max total-cost increase 273209.13, monotonicity=non_monotonic
- Fiabilite fournisseur SDC-VD0914690A: max total-cost increase 122739.28, monotonicity=non_monotonic

## Files
- threshold_sweep_cases.csv
- parameter_threshold_summary.csv
- threshold_sensitivity_summary.json
- cases/*/input_case.json
- cases/*/simulation_output/(summaries,reports) in compact mode
