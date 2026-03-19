# Threshold-Oriented Sensitivity Study

## Method
- Horizon: 365 days
- Scenario: scn:BASE
- Design: deterministic one-factor-at-a-time, multi-level sweeps
- Artifact mode: compact
- Kept detailed cases: baseline
- Service threshold: 0.950
- Soft service threshold: 0.930
- Backlog alert threshold: +25.0% vs baseline
- Cost alert threshold: +10.0% vs baseline
- Active suppliers screened individually: SDC-1450, SDC-VD0914690A, SDC-VD0525412A, SDC-VD0901566A

## Baseline
- Fill rate: 0.951540
- Ending backlog: 843.2095
- Total cost: 19256325.8659
- External procured qty: 0.0000
- Avg inventory: 8253511.0415

## Most Critical For Service Threshold
- Bootstrap stock initial: cross<0.95 at level 0.25, safe band [None, None], max fill drop 0.6202
- Lead time fournisseur SDC-VD0914690A: cross<0.95 at level 0.7, safe band [1.0, 1.5], max fill drop 0.1354
- Capacite M-1430: cross<0.95 at level 0.7, safe band [1.0, 1.3], max fill drop 0.1337
- Lead time global: cross<0.95 at level 0.75, safe band [1.0, 1.5], max fill drop 0.1057
- Fiabilite fournisseur globale: cross<0.95 at level 0.85, safe band [1.0, 1.0], max fill drop 0.2624
- Demande 268967: cross<0.95 at level 1.1, safe band [0.8, 1.0], max fill drop 0.0826
- Periode de revue: cross<0.95 at level 2.0, safe band [1.0, 1.0], max fill drop 0.4676

## Strongest Fill-Rate Effects
- Bootstrap stock initial: max fill drop 0.6202, monotonicity=increasing, steepest segment=[0.25, 0.5]
- Periode de revue: max fill drop 0.4676, monotonicity=decreasing, steepest segment=[2.0, 3.0]
- Fiabilite fournisseur globale: max fill drop 0.2624, monotonicity=increasing, steepest segment=[0.95, 1.0]
- Lead time fournisseur SDC-VD0914690A: max fill drop 0.1354, monotonicity=non_monotonic, steepest segment=[0.7, 0.85]
- Capacite M-1430: max fill drop 0.1337, monotonicity=increasing, steepest segment=[0.7, 0.85]
- Lead time global: max fill drop 0.1057, monotonicity=non_monotonic, steepest segment=[0.75, 0.9]
- Demande 268967: max fill drop 0.0826, monotonicity=decreasing, steepest segment=[1.0, 1.1]
- Stock fournisseur SDC-VD0914690A: max fill drop 0.0005, monotonicity=non_monotonic, steepest segment=[1.2, 1.4]
- Fiabilite fournisseur SDC-VD0914690A: max fill drop 0.0004, monotonicity=increasing, steepest segment=[0.9, 0.95]
- Demande 268091: max fill drop 0.0003, monotonicity=non_monotonic, steepest segment=[1.0, 1.1]

## Strongest Cost Effects
- Cout de stock: max total-cost increase 9585440.16, monotonicity=increasing
- Lead time global: max total-cost increase 1842408.89, monotonicity=increasing
- Periode de revue: max total-cost increase 506206.39, monotonicity=increasing
- Capacite M-1430: max total-cost increase 26706.31, monotonicity=increasing
- Lead time fournisseur SDC-1450: max total-cost increase 16502.67, monotonicity=increasing
- Stock fournisseur global: max total-cost increase 8722.38, monotonicity=increasing
- Lead time fournisseur SDC-VD0914690A: max total-cost increase 4552.51, monotonicity=non_monotonic
- Capacite M-1810: max total-cost increase 4471.10, monotonicity=increasing
- Safety stock global: max total-cost increase 3910.59, monotonicity=increasing
- Fiabilite fournisseur SDC-1450: max total-cost increase 2084.51, monotonicity=decreasing

## Files
- threshold_sweep_cases.csv
- parameter_threshold_summary.csv
- threshold_sensitivity_summary.json
- cases/*/input_case.json
- cases/*/simulation_output/(summaries,reports) in compact mode
