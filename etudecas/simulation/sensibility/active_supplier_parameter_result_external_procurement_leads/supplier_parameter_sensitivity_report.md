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
- Raw material safety-floor breach days: 140
- Total cost: 70614106.5952
- External procured ordered qty: 611862556.7491

## Critical Parameters
- Capacite fournisseur SDC-VD0993480A: first unacceptable level 0.05, safe band [0.01, 1.0], max fill drop 0.000000
- Capacite fournisseur globale: first unacceptable level 0.05, safe band [0.01, 1.0], max fill drop 0.000000
- Stock fournisseur global: first unacceptable level 0.01, safe band [0.25, 1.0], max fill drop 0.000000

## Strongest Fill Effects
- Capacite fournisseur SDC-VD0993480A: max fill drop 0.000000, acceptable [0.01, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur globale: max fill drop 0.000000, acceptable [0.01, 0.1, 0.25, 0.5, 0.75, 1.0]
- Stock fournisseur global: max fill drop 0.000000, acceptable [0.25, 0.5, 0.75, 0.9, 1.0]
- Capacite fournisseur SDC-VD0500655A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0505677A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0508918A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0514881A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0518684A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0519670A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0520115A: max fill drop 0.000000, acceptable [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]

## Strongest External Market Effects
- Stock fournisseur global: max external qty delta 932824480.2062, safe band [0.25, 1.0]
- Capacite fournisseur SDC-VD0519670A: max external qty delta 707882.7439, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0914320A: max external qty delta 355437.8807, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0520115A: max external qty delta 276023.0404, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0910216A: max external qty delta 272687.9604, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0956464A: max external qty delta 235028.3227, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD1091642A: max external qty delta 219248.7969, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0518684A: max external qty delta 215343.6684, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0951020A: max external qty delta 60.6345, safe band [0.01, 1.0]
- Stock fournisseur SDC-VD0914320A: max external qty delta 44.1311, safe band [0.01, 1.0]

## Minimum Tested Supplier Settings
- GLOBAL / capacite_fournisseur_globale: minimum acceptable tested scale 0.01 (first unacceptable 0.05)
- GLOBAL / stock_fournisseur_global: minimum acceptable tested scale 0.25 (first unacceptable 0.01)
- SDC-VD0993480A / capacite_fournisseur: minimum acceptable tested scale 0.01 (first unacceptable 0.05)

## Files
- supplier_parameter_sensitivity_cases.csv
- supplier_parameter_threshold_summary.csv
- supplier_parameter_recommendations.csv
- supplier_parameter_sensitivity_summary.json
- cases/*/input_case.json
