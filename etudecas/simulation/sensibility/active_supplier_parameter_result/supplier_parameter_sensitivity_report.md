# Supplier Parameter Sensitivity

## Method
- Horizon: 1825 days
- Scenario: scn:BASE
- Groups: capacity, stock
- Suppliers swept: SDC-VD0914690A, SDC-VD0914360C, SDC-VD0901566A, SDC-VD0993480A, SDC-VD0525412A, SDC-VD0508918A, SDC-VD0960508A, SDC-VD0949099A, SDC-VD0989480A, SDC-VD0520132A, SDC-VD0910216A, SDC-VD0972460A, SDC-VD0975221A, SDC-VD0520115A, SDC-VD1095770A, SDC-VD0951020A, SDC-VD1091642A, SDC-VD0518684A, SDC-VD0956464A, SDC-VD0505677A, SDC-VD0990780A, SDC-VD0500655A, SDC-VD0514881A, SDC-VD0519670A, SDC-VD0914320A, SDC-VD1096202A, SDC-VD0964290A
- Baseline guardrails are not warmup-adjusted: startup behavior remains included.
- Accepted case: fill rate target met, ending backlog no worse than baseline, daily backlog no worse than baseline, raw-material safety-floor breaches no worse than baseline.

## Baseline
- Fill rate: 1.000000
- Ending backlog: 0.0000
- Max daily backlog: 5653.4082
- Backlog days: 2
- Raw material safety-floor breach days: 141
- Total cost: 61416154.1416
- External procured ordered qty: 338885789.8898

## Critical Parameters
- Capacite fournisseur SDC-VD0951020A: first unacceptable level 0.01, safe band [0.05, 1.0], max fill drop 0.000000
- Capacite fournisseur SDC-VD0956464A: first unacceptable level 0.01, safe band [0.05, 1.0], max fill drop 0.000000
- Stock fournisseur global: first unacceptable level 0.01, safe band [0.25, 1.0], max fill drop 0.000000

## Strongest Fill Effects
- Capacite fournisseur SDC-VD0951020A: max fill drop 0.000000, acceptable [0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0956464A: max fill drop 0.000000, acceptable [0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Stock fournisseur global: max fill drop 0.000000, acceptable [0.25, 0.5, 0.75, 0.9, 1.0]
- Capacite fournisseur SDC-VD0500655A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0505677A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0508918A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0514881A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0518684A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0519670A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0520115A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]

## Strongest External Market Effects
- Stock fournisseur global: max external qty delta 174831795.1057, safe band [0.25, 1.0]
- Capacite fournisseur SDC-VD0956464A: max external qty delta 915875.9220, safe band [0.05, 1.0]
- Capacite fournisseur SDC-VD0520115A: max external qty delta 466703.0407, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0951020A: max external qty delta 421150.3178, safe band [0.05, 1.0]
- Capacite fournisseur SDC-VD0993480A: max external qty delta 341869.5209, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0508918A: max external qty delta 251019.5833, safe band [0.01, 1.0]
- Capacite fournisseur globale: max external qty delta 249599.3695, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0525412A: max external qty delta 84059.8841, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD1095770A: max external qty delta 28640.5654, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0914320A: max external qty delta 0.8267, safe band [0.01, 1.0]

## Minimum Tested Supplier Settings
- GLOBAL / capacite_fournisseur_globale: minimum acceptable tested scale 0.01 (first unacceptable none)
- GLOBAL / stock_fournisseur_global: minimum acceptable tested scale 0.25 (first unacceptable 0.01)
- SDC-VD0951020A / capacite_fournisseur: minimum acceptable tested scale 0.05 (first unacceptable 0.01)
- SDC-VD0956464A / capacite_fournisseur: minimum acceptable tested scale 0.05 (first unacceptable 0.01)

## Files
- supplier_parameter_sensitivity_cases.csv
- supplier_parameter_threshold_summary.csv
- supplier_parameter_recommendations.csv
- supplier_parameter_sensitivity_summary.json
- cases/*/input_case.json
