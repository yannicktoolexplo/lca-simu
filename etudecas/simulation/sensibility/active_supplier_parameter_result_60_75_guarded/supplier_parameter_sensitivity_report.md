# Supplier Parameter Sensitivity

## Method
- Horizon: 1825 days
- Scenario: scn:BASE
- Groups: capacity, combined, external, lead_time, reliability, stock
- Suppliers swept: SDC-VD0914690A, SDC-VD0914360C, SDC-VD0901566A, SDC-VD0993480A, SDC-VD0525412A, SDC-VD0508918A, SDC-VD0960508A, SDC-VD0949099A, SDC-VD0520132A, SDC-VD0989480A, SDC-VD0910216A, SDC-VD0972460A, SDC-VD0975221A, SDC-VD0520115A, SDC-VD1095770A, SDC-VD0951020A, SDC-VD1091642A, SDC-VD0518684A, SDC-VD0956464A, SDC-VD0505677A, SDC-VD0990780A, SDC-VD0500655A, SDC-VD0514881A, SDC-VD0519670A, SDC-VD0914320A, SDC-VD1096202A, SDC-VD0964290A
- Supplier floor calibration CSV: etudecas\simulation\result\mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test\data\supplier_nominal_60_75_calibration.csv
- Baseline guardrails are not warmup-adjusted: startup behavior remains included.
- Accepted case: fill rate target met, ending backlog no worse than baseline, daily backlog no worse than baseline, raw-material safety-floor and target-stock gaps no worse than baseline.

## Baseline
- Fill rate: 1.000000
- Product availability: 0.999143
- Line adherence: 0.998946
- Line nervousness: 37
- Ending backlog: 0.0000
- Max daily backlog: 5653.4082
- Backlog days: 2
- Raw material safety-floor breach days: 136
- Raw material max target gap qty: 20793472.4136
- Total cost: 61148676.1216
- Inventory holding cost: 7772700.3728
- Supplier upstream ordered qty: 546130544.8797

## Critical Parameters
- Combine capacite x0.75 + delai x1.25 fournisseur SDC-VD0901566A: first unacceptable level 1.0, plage continue baseline [None, None], max fill drop 0.000000, max availability drop 0.000000, max adherence drop 0.000088, max target gap increase 0.0000
- Combine stock x0.5 + fiabilite x0.97 fournisseur SDC-VD0520132A: first unacceptable level 1.0, plage continue baseline [None, None], max fill drop 0.000000, max availability drop 0.000000, max adherence drop 0.000088, max target gap increase 0.0000
- Combine stock x0.5 + fiabilite x0.97 fournisseur SDC-VD1091642A: first unacceptable level 1.0, plage continue baseline [None, None], max fill drop 0.000000, max availability drop 0.000000, max adherence drop 0.000083, max target gap increase 0.0000
- Combine capacite x0.75 + delai x1.25 fournisseur SDC-VD0951020A: first unacceptable level 1.0, plage continue baseline [None, None], max fill drop 0.000000, max availability drop 0.000000, max adherence drop 0.000077, max target gap increase 0.0000
- Combine stock x0.5 + fiabilite x0.97 fournisseur SDC-VD0500655A: first unacceptable level 1.0, plage continue baseline [None, None], max fill drop 0.000000, max availability drop 0.000000, max adherence drop 0.000066, max target gap increase 0.0000
- Combine stock x0.5 + fiabilite x0.97 fournisseur SDC-VD0990780A: first unacceptable level 1.0, plage continue baseline [None, None], max fill drop 0.000000, max availability drop 0.000000, max adherence drop 0.000066, max target gap increase 0.0000
- Combine capacite x0.75 + delai x1.25 fournisseur SDC-VD0505677A: first unacceptable level 1.0, plage continue baseline [None, None], max fill drop 0.000000, max availability drop 0.000000, max adherence drop 0.000036, max target gap increase 0.0000
- Combine stock x0.5 + fiabilite x0.97 fournisseur SDC-VD0520115A: first unacceptable level 1.0, plage continue baseline [None, None], max fill drop 0.000000, max availability drop 0.000000, max adherence drop 0.000036, max target gap increase 0.0000
- Combine stock x0.5 + fiabilite x0.97 fournisseur SDC-VD0914320A: first unacceptable level 1.0, plage continue baseline [None, None], max fill drop 0.000000, max availability drop 0.000000, max adherence drop 0.000036, max target gap increase 0.0000
- Appro amont combinee cap x0.75 + delai x1.25: first unacceptable level 1.0, plage continue baseline [None, None], max fill drop 0.000000, max availability drop 0.000000, max adherence drop 0.000030, max target gap increase 0.0000

## Strongest Fill Effects
- Capacite fournisseur globale: max fill drop 0.726519, acceptable [0.75, 0.9, 1.0]
- Capacite fournisseur SDC-VD0514881A: max fill drop 0.531537, acceptable [0.75, 0.9, 1.0]
- Capacite fournisseur SDC-VD0505677A: max fill drop 0.506805, acceptable [0.75, 0.9, 1.0]
- Appro amont fournisseur active: max fill drop 0.497246, acceptable [1.0]
- Capacite fournisseur SDC-VD0989480A: max fill drop 0.448885, acceptable [0.75, 0.9, 1.0]
- Capacite fournisseur SDC-VD0519670A: max fill drop 0.385023, acceptable [0.75, 0.9, 1.0]
- Capacite fournisseur SDC-VD0914690A: max fill drop 0.173860, acceptable [0.75, 0.9, 1.0]
- Capacite fournisseur SDC-VD1096202A: max fill drop 0.162386, acceptable [0.75, 0.9, 1.0]
- Combine capacite x0.75 + delai x1.25 fournisseur SDC-VD0901566A: max fill drop 0.000000, acceptable []
- Combine stock x0.5 + fiabilite x0.97 fournisseur SDC-VD0520132A: max fill drop 0.000000, acceptable []

## Strongest Supplier Upstream Supply Effects
- Delai appro amont fournisseur: max supplier upstream qty delta 437063088.5029, niveaux acceptables non contigus [1.0, 2.0]; plage continue baseline [1.0, 1.0]
- Appro amont combinee cap x0.75 + delai x1.25: max supplier upstream qty delta 128226899.7687, plage continue baseline [None, None]
- Stock fournisseur global: max supplier upstream qty delta 41593676.9096, niveaux acceptables non contigus [0.5, 1.0]; plage continue baseline [1.0, 1.0]
- Stock fournisseur SDC-VD0914690A: max supplier upstream qty delta 20071148.7636, plage continue baseline [0.25, 1.0]
- Delai fournisseur SDC-VD0914360C: max supplier upstream qty delta 11457428.5545, plage continue baseline [1.0, 1.5]
- Combine stock x0.5 + fiabilite x0.97 fournisseur SDC-VD0901566A: max supplier upstream qty delta 7870730.3809, plage continue baseline [None, None]
- Delai fournisseur SDC-VD0993480A: max supplier upstream qty delta 7451180.7556, plage continue baseline [1.0, 1.0]
- Delai fournisseur SDC-VD0525412A: max supplier upstream qty delta 7410541.8103, plage continue baseline [1.0, 1.0]
- Combine capacite x0.75 + delai x1.25 fournisseur SDC-VD0993480A: max supplier upstream qty delta 5710639.1210, plage continue baseline [None, None]
- Delai fournisseur SDC-VD0508918A: max supplier upstream qty delta 5388876.1963, plage continue baseline [1.0, 1.0]

## Minimum Tested Supplier Settings
- GLOBAL / appro_amont_fournisseur: minimum acceptable scale in the continuous baseline range None (first unacceptable 1.0)
- GLOBAL / appro_amont_fournisseur: minimum acceptable scale in the continuous baseline range 1.0 (first unacceptable 1.25)
- GLOBAL / appro_amont_fournisseur: minimum acceptable scale in the continuous baseline range 1.0 (first unacceptable 0.01)
- GLOBAL / appro_amont_fournisseur: minimum acceptable scale in the continuous baseline range 0.25 (first unacceptable none)
- GLOBAL / capacite_fournisseur_globale: minimum acceptable scale in the continuous baseline range 0.75 (first unacceptable 0.5)
- GLOBAL / delai_fournisseur_global: minimum acceptable scale in the continuous baseline range 1.0 (first unacceptable 2.0)
- GLOBAL / fiabilite_fournisseur_globale: minimum acceptable scale in the continuous baseline range 0.95 (first unacceptable none)
- GLOBAL / stock_fournisseur_global: minimum acceptable scale in the continuous baseline range 1.0 (first unacceptable 0.25)
- SDC-VD0500655A / scenario_combine_stock_fiabilite: minimum acceptable scale in the continuous baseline range None (first unacceptable 1.0)
- SDC-VD0500655A / stock_fournisseur: minimum acceptable scale in the continuous baseline range 1.0 (first unacceptable 0.5)
- SDC-VD0505677A / capacite_fournisseur: minimum acceptable scale in the continuous baseline range 0.75 (first unacceptable 0.5)
- SDC-VD0505677A / delai_fournisseur: minimum acceptable scale in the continuous baseline range 1.0 (first unacceptable 1.25)
- SDC-VD0505677A / fiabilite_fournisseur: minimum acceptable scale in the continuous baseline range 0.99 (first unacceptable 0.95)
- SDC-VD0505677A / scenario_combine_capacite_delai: minimum acceptable scale in the continuous baseline range None (first unacceptable 1.0)
- SDC-VD0508918A / capacite_fournisseur: minimum acceptable scale in the continuous baseline range 0.75 (first unacceptable 0.5)
- SDC-VD0508918A / delai_fournisseur: minimum acceptable scale in the continuous baseline range 1.0 (first unacceptable 1.25)
- SDC-VD0508918A / fiabilite_fournisseur: minimum acceptable scale in the continuous baseline range 0.99 (first unacceptable 0.97)
- SDC-VD0508918A / scenario_combine_capacite_delai: minimum acceptable scale in the continuous baseline range None (first unacceptable 1.0)
- SDC-VD0514881A / capacite_fournisseur: minimum acceptable scale in the continuous baseline range 0.75 (first unacceptable 0.5)
- SDC-VD0514881A / delai_fournisseur: minimum acceptable scale in the continuous baseline range 1.0 (first unacceptable 1.25)

## Files
- supplier_parameter_sensitivity_cases.csv
- supplier_parameter_threshold_summary.csv
- supplier_parameter_recommendations.csv
- supplier_parameter_sensitivity_summary.json
- cases/*/input_case.json
