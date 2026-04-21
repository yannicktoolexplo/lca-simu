# Source Truth vs 1Y Material Reconciliation

This report keeps the XLSX-derived annual requirement and source opening quantities,
then refreshes the simulation-dependent columns from the current baseline outputs.

- Families audited: `24`
- Strong reconciliation issues: `14`

## Strong Issues
- `001893` @ `M-1810`: annual req `27588.674`, source opening `9783.5`, sim received `9138.746289`, sim ending `5703.535889` -> graph seed matches source stock; under-delivered vs source gap; ending stock builds up
- `016332` @ `M-1810`: annual req `1742.442542`, source opening `883.02`, sim received `1183.311200`, sim ending `1231.465280` -> graph seed matches source stock; over-delivered vs source gap; ending stock builds up
- `049371` @ `M-1810`: annual req `5372.531172`, source opening `4138.93`, sim received `767.774420`, sim ending `2332.534500` -> graph seed matches source stock; under-delivered vs source gap; ending stock builds up
- `099439` @ `M-1810`: annual req `7260.1772599999995`, source opening `4972.616`, sim received `246.848000`, sim ending `1740.856000` -> graph seed matches source stock; under-delivered vs source gap; ending stock builds up
- `338928` @ `M-1810`: annual req `3576442.0`, source opening `404065.0`, sim received `1318200.000000`, sim ending `8665.000000` -> graph seed matches source stock; under-delivered vs source gap
- `338929` @ `M-1810`: annual req `3576442.0`, source opening `354000.0`, sim received `1441300.000000`, sim ending `81700.000000` -> graph seed matches source stock; under-delivered vs source gap
- `426331` @ `M-1810`: annual req `39340.862`, source opening `24159.0`, sim received `1086.800000`, sim ending `6396.200000` -> graph seed matches source stock; under-delivered vs source gap; ending stock builds up
- `693055` @ `M-1810`: annual req `1452035.452`, source opening `1010000.0`, sim received `98739.200000`, sim ending `413017.600000` -> graph seed matches source stock; under-delivered vs source gap; ending stock builds up
- `042342` @ `M-1430`: annual req `95098147.212`, source opening `78749996.0`, sim received `6031269.103197`, sim ending `39247191.903194` -> graph seed matches source stock; under-delivered vs source gap; ending stock builds up
- `333362` @ `M-1430`: annual req `1575986.0`, source opening `142250.0`, sim received `706914.285730`, sim ending `94564.285730` -> graph seed matches source stock; under-delivered vs source gap
- `344135` @ `M-1430`: annual req `1575986.0`, source opening `0.0`, sim received `871822.857152`, sim ending `117222.857152` -> graph seed matches source stock; under-delivered vs source gap
- `708073` @ `M-1430`: annual req `12497.56898`, source opening `10326.88`, sim received `1056.819771`, sim ending `5399.721771` -> graph seed matches source stock; under-delivered vs source gap; ending stock builds up
- `734545` @ `M-1430`: annual req `12607.888`, source opening `1641.0`, sim received `7099.611423`, sim ending `2703.811429` -> graph seed matches source stock; under-delivered vs source gap; ending stock builds up
- `773474` @ `M-1430`: annual req `15215700.402`, source opening `14593000.0`, sim received `358783.113355`, sim ending `7666332.910554` -> graph seed matches source stock; under-delivered vs source gap; ending stock builds up

## Reference Files
- Reconciliation CSV: `etudecas\simulation\result\reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated\data\source_truth_vs_1y_material_reconciliation.csv`
- Simulation input stocks: `etudecas\simulation\result\reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated\data\production_input_stocks_daily.csv`
- Simulation input arrivals: `etudecas\simulation\result\reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated\data\production_input_replenishment_arrivals_daily.csv`
- Simulation supplier shipments: `etudecas\simulation\result\reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated\data\production_supplier_shipments_daily.csv`
