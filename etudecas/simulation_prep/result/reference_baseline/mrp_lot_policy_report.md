# MRP Seed Injection Report

- Source graph: `etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_real_demand_target_calibrated.json`
- Output graph: `etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy.json`
- Workbook: `etudecas\donnees\Stocks_MRP.xlsx`
- Snapshot UTC: `2025-01-01T03:03:48+00:00`
- Stock rows injected: `28` / `32`
- Inventory states created: `0`
- Inventory states updated: `28`
- MRP policy rows applied: `25`
- MRP policy overrides applied: `2`
- MRP lot policies applied: `3`
- Legacy batch-size updates: `0`

## Injected stock rows
- DC-1920 / item:268091: `120.0` -> `430538.0` `UN` (source `430538.0` `UN`)
- DC-1920 / item:268967: `120.0` -> `1101534.0` `UN` (source `1101534.0` `UN`)
- M-1430 / item:038005: `0.0` -> `37598.5325` `KG` (source `37598532.5` `G`)
- M-1430 / item:042342: `0.0` -> `78749996.0` `UN` (source `78749996.0` `UN`)
- M-1430 / item:333362: `0.0` -> `142250.0` `UN` (source `142250.0` `UN`)
- M-1430 / item:344135: `0.0` -> `0.0` `UN` (source `0.0` `UN`)
- M-1430 / item:708073: `0.0` -> `10326.88` `KG` (source `10326880.0` `G`)
- M-1430 / item:730384: `0.0` -> `68387.0` `M` (source `68387.0` `M`)
- M-1430 / item:734545: `0.0` -> `1641.0` `UN` (source `1641.0` `UN`)
- M-1430 / item:773474: `0.0` -> `14593000.0` `G` (source `14593000.0` `G`)
- M-1810 / item:001757: `0.0` -> `8499.654` `KG` (source `8499654.0` `G`)
- M-1810 / item:001848: `0.0` -> `10262.646` `KG` (source `10262646.0` `G`)
- M-1810 / item:001893: `0.0` -> `9783.5` `KG` (source `9783.5` `KG`)
- M-1810 / item:002612: `0.0` -> `153521.63671875` `KG` (source `153521.63671875` `KG`)
- M-1810 / item:007923: `0.0` -> `55018.98` `KG` (source `55018980.0` `G`)
- M-1810 / item:016332: `0.0` -> `883.02` `KG` (source `883020.0` `G`)
- M-1810 / item:029313: `0.0` -> `226.83` `KG` (source `226830.0` `G`)
- M-1810 / item:039668: `0.0` -> `459.695` `KG` (source `459695.0` `G`)
- M-1810 / item:049371: `0.0` -> `4138.93` `KG` (source `4138930.0` `G`)
- M-1810 / item:055703: `0.0` -> `569.805000976563` `KG` (source `569805.000976563` `G`)
- M-1810 / item:099439: `0.0` -> `4972.616` `KG` (source `4972616.0` `G`)
- M-1810 / item:338928: `0.0` -> `404065.0` `UN` (source `404065.0` `UN`)
- M-1810 / item:338929: `0.0` -> `354000.0` `UN` (source `354000.0` `UN`)
- M-1810 / item:426331: `0.0` -> `24159.0` `UN` (source `24159.0` `UN`)
- M-1810 / item:693055: `0.0` -> `1010000.0` `G` (source `1010000.0` `G`)
- SDC-1450 / item:021081: `0.0` -> `1142100.0` `KG` (source `1142100.0` `KG`)
- SDC-1450 / item:693055: `0.0` -> `1800000.0` `G` (source `1800000.0` `G`)
- SDC-1450 / item:773474: `0.0` -> `9600000.0` `G` (source `9600000.0` `G`)

## Injected MRP safety policies
- DC-1920 / item:268091: safety time `0.0` d, safety stock `0.0` `UN` (source `mrp_policy_sheet`)
- DC-1920 / item:268967: safety time `25.0` d, safety stock `0.0` `UN` (source `mrp_policy_sheet`)
- M-1430 / item:038005: safety time `20.0` d, safety stock `0.0` `KG` (source `mrp_policy_sheet`)
- M-1430 / item:042342: safety time `5.0` d, safety stock `0.0` `UN` (source `mrp_policy_sheet`)
- M-1430 / item:333362: safety time `10.0` d, safety stock `110000.0` `UN` (source `mrp_policy_sheet`)
- M-1430 / item:344135: safety time `10.0` d, safety stock `0.0` `UN` (source `mrp_policy_sheet`)
- M-1430 / item:708073: safety time `10.0` d, safety stock `2000.0` `KG` (source `mrp_policy_sheet`)
- M-1430 / item:730384: safety time `10.0` d, safety stock `23500.0` `M` (source `mrp_policy_sheet`)
- M-1430 / item:734545: safety time `10.0` d, safety stock `0.0` `UN` (source `mrp_policy_sheet`)
- M-1430 / item:773474: safety time `20.0` d, safety stock `0.0` `G` (source `mrp_policy_sheet`)
- M-1810 / item:001757: safety time `20.0` d, safety stock `0.0` `KG` (source `mrp_policy_sheet`)
- M-1810 / item:001848: safety time `20.0` d, safety stock `0.0` `KG` (source `mrp_policy_sheet`)
- M-1810 / item:001893: safety time `15.0` d, safety stock `0.0` `KG` (source `mrp_policy_sheet`)
- M-1810 / item:002612: safety time `20.0` d, safety stock `0.0` `KG` (source `mrp_policy_sheet`)
- M-1810 / item:007923: safety time `15.0` d, safety stock `0.0` `KG` (source `mrp_policy_sheet`)
- M-1810 / item:016332: safety time `7.0` d, safety stock `0.0` `KG` (source `mrp_policy_sheet`)
- M-1810 / item:029313: safety time `7.0` d, safety stock `0.0` `KG` (source `mrp_policy_sheet`)
- M-1810 / item:039668: safety time `7.0` d, safety stock `0.0` `KG` (source `mrp_policy_sheet`)
- M-1810 / item:049371: safety time `40.0` d, safety stock `888.0` `KG` (source `mrp_policy_sheet`)
- M-1810 / item:055703: safety time `30.0` d, safety stock `0.0` `KG` (source `mrp_policy_sheet`)
- M-1810 / item:099439: safety time `7.0` d, safety stock `0.0` `KG` (source `mrp_policy_sheet`)
- M-1810 / item:338928: safety time `10.0` d, safety stock `0.0` `UN` (source `mrp_policy_sheet`)
- M-1810 / item:338929: safety time `10.0` d, safety stock `0.0` `UN` (source `mrp_policy_sheet`)
- M-1810 / item:426331: safety time `7.0` d, safety stock `0.0` `UN` (source `mrp_policy_sheet`)
- M-1810 / item:693055: safety time `20.0` d, safety stock `0.0` `G` (source `mrp_policy_sheet`)

## Applied policy overrides
- DC-1920 / item:268091: safety time `20.0` d, safety stock `None` `UN` (source `industrial_confirmation_2026-04-10`)
- DC-1920 / item:268967: safety time `25.0` d, safety stock `None` `UN` (source `industrial_confirmation_2026-04-10`)

## Injected MRP lot policies
- M-1430 / proc:MAKE_268967 / item:268967: fixed `107800.0`, min `107800.0`, max `107800.0` `UN` (min_equals_max_as_fixed)
- M-1810 / proc:MAKE_268091 / item:268091: fixed `0.0`, min `14400.0`, max `142485.0` `UN` (direct)
- SDC-1450 / proc:MAKE_773474 / item:773474: fixed `3200000.0`, min `0.0`, max `0.0` `G` (direct)

## Skipped stock rows
- M-1430 / item:001848: `node_item_pair_not_modeled`
- M-1430 / item:007923: `node_item_pair_not_modeled`
- SDC-1450 / item:001893: `node_item_pair_not_modeled`
- SDC-1450 / item:002612: `node_item_pair_not_modeled`
