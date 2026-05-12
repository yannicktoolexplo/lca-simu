# Supplier Parameter Sensitivity

## Method
- Horizon: 1825 days
- Scenario: scn:BASE
- Groups: capacity, external, stock
- Suppliers swept: SDC-VD0914690A, SDC-VD0914360C, SDC-VD0901566A, SDC-VD0993480A, SDC-VD0525412A, SDC-VD0508918A, SDC-VD0960508A, SDC-VD0949099A, SDC-VD0520132A, SDC-VD0989480A, SDC-VD0910216A, SDC-VD0972460A, SDC-VD0975221A, SDC-VD0520115A, SDC-VD1095770A, SDC-VD0951020A, SDC-VD1091642A, SDC-VD0518684A, SDC-VD0956464A, SDC-VD0505677A, SDC-VD0990780A, SDC-VD0500655A, SDC-VD0514881A, SDC-VD0519670A, SDC-VD0914320A, SDC-VD1096202A, SDC-VD0964290A
- Baseline guardrails are not warmup-adjusted: startup behavior remains included.
- Accepted case: fill rate target met, ending backlog no worse than baseline, daily backlog no worse than baseline, raw-material safety-floor breaches no worse than baseline.

## Baseline
- Fill rate: 1.000000
- Ending backlog: 0.0000
- Max daily backlog: 5653.4082
- Backlog days: 2
- Raw material safety-floor breach days: 136
- Total cost: 61148958.3234
- External procured ordered qty: 546130595.6450

## Critical Parameters
- Capacite fournisseur SDC-VD0520115A: first unacceptable level 0.05, safe band [0.01, 1.0], max fill drop 0.000000
- Capacite fournisseur SDC-VD1095770A: first unacceptable level 0.05, safe band [0.01, 1.0], max fill drop 0.000000
- Capacite fournisseur globale: first unacceptable level 0.05, safe band [0.01, 1.0], max fill drop 0.000000
- External market active: first unacceptable level 0.01, safe band [1.0, 1.0], max fill drop 0.497246
- Capacite fournisseur SDC-VD0508918A: first unacceptable level 0.01, safe band [0.1, 1.0], max fill drop 0.000000
- Capacite fournisseur SDC-VD0518684A: first unacceptable level 0.01, safe band [0.25, 1.0], max fill drop 0.000000
- Capacite fournisseur SDC-VD0525412A: first unacceptable level 0.01, safe band [0.05, 1.0], max fill drop 0.000000
- Capacite fournisseur SDC-VD0910216A: first unacceptable level 0.01, safe band [0.25, 1.0], max fill drop 0.000000
- Capacite fournisseur SDC-VD0914320A: first unacceptable level 0.01, safe band [0.25, 1.0], max fill drop 0.000000
- Capacite fournisseur SDC-VD0993480A: first unacceptable level 0.01, safe band [0.1, 1.0], max fill drop 0.000000

## Strongest Fill Effects
- External market active: max fill drop 0.497246, acceptable [1.0]
- Capacite fournisseur SDC-VD0520115A: max fill drop 0.000000, acceptable [0.01, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD1095770A: max fill drop 0.000000, acceptable [0.01, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur globale: max fill drop 0.000000, acceptable [0.01, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0508918A: max fill drop 0.000000, acceptable [0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0518684A: max fill drop 0.000000, acceptable [0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0525412A: max fill drop 0.000000, acceptable [0.05, 0.1, 0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0910216A: max fill drop 0.000000, acceptable [0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0914320A: max fill drop 0.000000, acceptable [0.25, 0.5, 0.75, 1.0]
- Capacite fournisseur SDC-VD0993480A: max fill drop 0.000000, acceptable [0.1, 0.25, 0.5, 0.75, 1.0]

## Strongest External Market Effects
- Delai external market: max external qty delta 437062157.4965, safe band [1.0, 2.0]
- Stock fournisseur global: max external qty delta 23261391.9174, safe band [0.25, 1.0]
- Capacite fournisseur SDC-VD0518684A: max external qty delta 4940663.9138, safe band [0.25, 1.0]
- Capacite fournisseur SDC-VD0910216A: max external qty delta 4407543.7396, safe band [0.25, 1.0]
- Capacite fournisseur SDC-VD0993480A: max external qty delta 4340039.3301, safe band [0.1, 1.0]
- Capacite fournisseur globale: max external qty delta 4024399.2639, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0520115A: max external qty delta 1413464.2427, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0914320A: max external qty delta 1288281.9224, safe band [0.25, 1.0]
- Capacite fournisseur SDC-VD1095770A: max external qty delta 1187823.2022, safe band [0.01, 1.0]
- Capacite fournisseur SDC-VD0508918A: max external qty delta 1187823.2022, safe band [0.1, 1.0]

## Minimum Tested Supplier Settings
- GLOBAL / capacite_fournisseur_globale: minimum acceptable tested scale 0.01 (first unacceptable 0.05)
- GLOBAL / stock_fournisseur_global: minimum acceptable tested scale 0.25 (first unacceptable 0.01)
- SDC-VD0508918A / capacite_fournisseur: minimum acceptable tested scale 0.1 (first unacceptable 0.01)
- SDC-VD0518684A / capacite_fournisseur: minimum acceptable tested scale 0.25 (first unacceptable 0.01)
- SDC-VD0520115A / capacite_fournisseur: minimum acceptable tested scale 0.01 (first unacceptable 0.05)
- SDC-VD0525412A / capacite_fournisseur: minimum acceptable tested scale 0.05 (first unacceptable 0.01)
- SDC-VD0910216A / capacite_fournisseur: minimum acceptable tested scale 0.25 (first unacceptable 0.01)
- SDC-VD0914320A / capacite_fournisseur: minimum acceptable tested scale 0.25 (first unacceptable 0.01)
- SDC-VD0993480A / capacite_fournisseur: minimum acceptable tested scale 0.1 (first unacceptable 0.01)
- SDC-VD1095770A / capacite_fournisseur: minimum acceptable tested scale 0.01 (first unacceptable 0.05)

## Files
- supplier_parameter_sensitivity_cases.csv
- supplier_parameter_threshold_summary.csv
- supplier_parameter_recommendations.csv
- supplier_parameter_sensitivity_summary.json
- cases/*/input_case.json
