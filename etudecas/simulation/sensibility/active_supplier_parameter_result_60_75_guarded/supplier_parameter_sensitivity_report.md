# Supplier Parameter Sensitivity

## Method
- Horizon: 1825 days
- Scenario: scn:BASE
- Groups: capacity, external, lead_time, reliability, stock
- Suppliers swept: SDC-VD0914690A, SDC-VD0914360C, SDC-VD0901566A, SDC-VD0993480A, SDC-VD0525412A, SDC-VD0508918A, SDC-VD0960508A, SDC-VD0949099A
- Supplier floor calibration CSV: etudecas\simulation\result\mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test\data\supplier_nominal_60_75_calibration.csv
- Baseline guardrails are not warmup-adjusted: startup behavior remains included.
- Accepted case: fill rate target met, ending backlog no worse than baseline, daily backlog no worse than baseline, raw-material safety-floor and target-stock gaps no worse than baseline.

## Baseline
- Fill rate: 1.000000
- Ending backlog: 0.0000
- Max daily backlog: 5653.4082
- Backlog days: 2
- Raw material safety-floor breach days: 136
- Raw material max target gap qty: 20793472.4136
- Total cost: 61148676.1216
- Supplier upstream ordered qty: 546130544.8797

## Critical Parameters
- Fiabilite fournisseur SDC-VD0901566A: first unacceptable level 0.97, niveaux acceptables non contigus [0.95, 0.99, 1.0]; plage continue baseline [0.99, 1.0], max fill drop 0.000000, max target gap increase 0.0000
- Delai appro amont fournisseur: first unacceptable level 1.25, niveaux acceptables non contigus [1.0, 1.5, 2.0]; plage continue baseline [1.0, 1.0], max fill drop 0.000000, max target gap increase 0.0000
- Delai fournisseur SDC-VD0508918A: first unacceptable level 1.25, plage continue baseline [1.0, 1.0], max fill drop 0.000000, max target gap increase 0.0000
- Delai fournisseur SDC-VD0525412A: first unacceptable level 1.25, plage continue baseline [1.0, 1.0], max fill drop 0.000000, max target gap increase 0.0000
- Delai fournisseur SDC-VD0993480A: first unacceptable level 1.25, plage continue baseline [1.0, 1.0], max fill drop 0.000000, max target gap increase 0.0000
- Capacite fournisseur globale: first unacceptable level 0.5, plage continue baseline [0.75, 1.0], max fill drop 0.726519, max target gap increase 57956523.5864
- Capacite fournisseur SDC-VD0914690A: first unacceptable level 0.5, plage continue baseline [0.75, 1.0], max fill drop 0.173860, max target gap increase 57956523.5864
- Capacite fournisseur SDC-VD0508918A: first unacceptable level 0.5, plage continue baseline [0.75, 1.0], max fill drop 0.000000, max target gap increase 0.0000
- Capacite fournisseur SDC-VD0525412A: first unacceptable level 0.5, plage continue baseline [0.6, 1.0], max fill drop 0.000000, max target gap increase 0.0000
- Delai fournisseur SDC-VD0914690A: first unacceptable level 1.5, plage continue baseline [1.0, 1.25], max fill drop 0.000000, max target gap increase 0.0000

## Strongest Fill Effects
- Capacite fournisseur globale: max fill drop 0.726519, acceptable [0.75, 0.9, 1.0]
- Appro amont fournisseur active: max fill drop 0.497246, acceptable [1.0]
- Capacite fournisseur SDC-VD0914690A: max fill drop 0.173860, acceptable [0.75, 0.9, 1.0]
- Fiabilite fournisseur SDC-VD0901566A: max fill drop 0.000000, acceptable [0.95, 0.99, 1.0]
- Delai appro amont fournisseur: max fill drop 0.000000, acceptable [1.0, 1.5, 2.0]
- Delai fournisseur SDC-VD0508918A: max fill drop 0.000000, acceptable [1.0]
- Delai fournisseur SDC-VD0525412A: max fill drop 0.000000, acceptable [1.0]
- Delai fournisseur SDC-VD0993480A: max fill drop 0.000000, acceptable [1.0]
- Capacite fournisseur SDC-VD0508918A: max fill drop 0.000000, acceptable [0.75, 0.9, 1.0]
- Capacite fournisseur SDC-VD0525412A: max fill drop 0.000000, acceptable [0.6, 0.75, 0.9, 1.0]

## Strongest Supplier Upstream Supply Effects
- Delai appro amont fournisseur: max supplier upstream qty delta 437063088.5029, niveaux acceptables non contigus [1.0, 1.5, 2.0]; plage continue baseline [1.0, 1.0]
- Stock fournisseur global: max supplier upstream qty delta 41593676.9096, niveaux acceptables non contigus [0.5, 1.0]; plage continue baseline [1.0, 1.0]
- Stock fournisseur SDC-VD0914690A: max supplier upstream qty delta 20071148.7636, plage continue baseline [0.25, 1.0]
- Delai fournisseur SDC-VD0914360C: max supplier upstream qty delta 11457428.5545, plage continue baseline [1.0, 1.5]
- Delai fournisseur SDC-VD0993480A: max supplier upstream qty delta 7451180.7556, plage continue baseline [1.0, 1.0]
- Delai fournisseur SDC-VD0525412A: max supplier upstream qty delta 7410541.8103, plage continue baseline [1.0, 1.0]
- Delai fournisseur SDC-VD0508918A: max supplier upstream qty delta 5388876.1963, plage continue baseline [1.0, 1.0]
- Fiabilite fournisseur SDC-VD0901566A: max supplier upstream qty delta 5021030.3809, niveaux acceptables non contigus [0.95, 0.99, 1.0]; plage continue baseline [0.99, 1.0]
- Fiabilite fournisseur globale: max supplier upstream qty delta 5000442.5534, plage continue baseline [0.95, 1.0]
- Stock fournisseur SDC-VD0901566A: max supplier upstream qty delta 4274550.0000, plage continue baseline [0.25, 1.0]

## Minimum Tested Supplier Settings
- GLOBAL / capacite_fournisseur_globale: minimum acceptable scale in the continuous baseline range 0.75 (first unacceptable 0.5)
- GLOBAL / stock_fournisseur_global: minimum acceptable scale in the continuous baseline range 1.0 (first unacceptable 0.25)
- SDC-VD0508918A / capacite_fournisseur: minimum acceptable scale in the continuous baseline range 0.75 (first unacceptable 0.5)
- SDC-VD0525412A / capacite_fournisseur: minimum acceptable scale in the continuous baseline range 0.6 (first unacceptable 0.5)
- SDC-VD0914360C / stock_fournisseur: minimum acceptable scale in the continuous baseline range 0.5 (first unacceptable 0.25)
- SDC-VD0914690A / capacite_fournisseur: minimum acceptable scale in the continuous baseline range 0.75 (first unacceptable 0.5)
- SDC-VD0993480A / stock_fournisseur: minimum acceptable scale in the continuous baseline range 1.0 (first unacceptable 0.5)

## Files
- supplier_parameter_sensitivity_cases.csv
- supplier_parameter_threshold_summary.csv
- supplier_parameter_recommendations.csv
- supplier_parameter_sensitivity_summary.json
- cases/*/input_case.json
