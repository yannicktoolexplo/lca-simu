# Threshold-Oriented Sensitivity Study

## Method
- Horizon: 0 days
- Scenario: scn:BASE
- Design: deterministic one-factor-at-a-time, multi-level sweeps
- Artifact mode: compact
- Kept detailed cases: baseline
- Service threshold: 0.900
- Soft service threshold: 0.850
- Backlog alert threshold: +25.0% vs baseline
- Cost alert threshold: +10.0% vs baseline
- Active suppliers screened individually: SDC-VD0914690A, SDC-1450, SDC-VD0901566A, SDC-VD0914360C

## Baseline
- Fill rate: 0.888075
- Ending backlog: 593478.1966
- Total cost: 27920896.5609
- External procured qty: 0.0000
- Avg inventory: 19766465.3509

## Most Critical For Service Threshold
- Appro externe activee: cross<0.90 at level 0.0, safe band [None, None], max fill drop 0.0000
- Safety stock global: cross<0.90 at level 0.25, safe band [None, None], max fill drop 0.0044
- Bootstrap stock initial: cross<0.90 at level 0.25, safe band [None, None], max fill drop 0.0000
- Capacite appro externe: cross<0.90 at level 0.4, safe band [None, None], max fill drop 0.0000
- Stock fournisseur global: cross<0.90 at level 0.5, safe band [None, None], max fill drop 0.0232
- Cout de stock: cross<0.90 at level 0.5, safe band [None, None], max fill drop 0.0000
- Stock production global: cross<0.90 at level 0.5, safe band [None, None], max fill drop 0.0000
- Debit fournisseur SDC-VD0901566A: cross<0.90 at level 0.6, safe band [None, None], max fill drop 0.2349
- Debit fournisseur SDC-1450: cross<0.90 at level 0.6, safe band [None, None], max fill drop 0.0145
- Debit fournisseur SDC-VD0914360C: cross<0.90 at level 0.6, safe band [None, None], max fill drop 0.0051

## Strongest Fill-Rate Effects
- Periode de revue: max fill drop 0.6729, monotonicity=decreasing, steepest segment=[1.0, 2.0]
- Fiabilite fournisseur globale: max fill drop 0.2434, monotonicity=increasing, steepest segment=[0.95, 1.0]
- Debit fournisseur SDC-VD0901566A: max fill drop 0.2349, monotonicity=non_monotonic, steepest segment=[0.6, 0.8]
- Capacite M-1810: max fill drop 0.1080, monotonicity=increasing, steepest segment=[0.7, 0.85]
- Capacite M-1430: max fill drop 0.0512, monotonicity=increasing, steepest segment=[0.7, 0.85]
- Demande 268091: max fill drop 0.0401, monotonicity=decreasing, steepest segment=[1.1, 1.2]
- Demande 268967: max fill drop 0.0296, monotonicity=decreasing, steepest segment=[1.1, 1.2]
- Stock fournisseur global: max fill drop 0.0232, monotonicity=non_monotonic, steepest segment=[1.25, 1.5]
- Fiabilite fournisseur SDC-VD0914360C: max fill drop 0.0230, monotonicity=non_monotonic, steepest segment=[0.85, 0.9]
- Fiabilite fournisseur SDC-VD0901566A: max fill drop 0.0181, monotonicity=non_monotonic, steepest segment=[0.85, 0.9]

## Strongest Cost Effects
- Cout de stock: max total-cost increase 5981220.78, monotonicity=increasing
- Capacite M-1430: max total-cost increase 1565316.27, monotonicity=increasing
- Demande 268967: max total-cost increase 969935.29, monotonicity=increasing
- Lead time global: max total-cost increase 637574.91, monotonicity=non_monotonic
- Capacite M-1810: max total-cost increase 468133.24, monotonicity=increasing
- Fiabilite fournisseur SDC-1450: max total-cost increase 166464.41, monotonicity=non_monotonic
- Debit fournisseur SDC-VD0914360C: max total-cost increase 165183.31, monotonicity=non_monotonic
- Lead time fournisseur SDC-VD0914690A: max total-cost increase 109759.35, monotonicity=non_monotonic
- Fiabilite fournisseur SDC-VD0914690A: max total-cost increase 102608.69, monotonicity=non_monotonic
- Demande 268091: max total-cost increase 97777.83, monotonicity=non_monotonic

## Files
- threshold_sweep_cases.csv
- parameter_threshold_summary.csv
- threshold_sensitivity_summary.json
- cases/*/input_case.json
- cases/*/simulation_output/(summaries,reports) in compact mode
