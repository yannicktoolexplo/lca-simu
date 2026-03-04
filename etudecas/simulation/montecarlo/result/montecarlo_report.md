# Monte Carlo Analysis Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 30
- Seed: 42
- Runs requested (excluding baseline): 120
- Runs total (including baseline): 121
- Runs success: 121
- Runs failed: 0
- Keep run artifacts: False

## KPI Statistics (distribution over successful runs)
{
  "kpi::avg_inventory": {
    "n": 121,
    "mean": 8792.504378512396,
    "std": 1257.4001360754578,
    "min": 6096.5224,
    "p05": 6778.1824,
    "p50": 8787.1268,
    "p95": 10926.2683,
    "max": 12329.0127,
    "baseline": 8081.6759
  },
  "kpi::ending_backlog": {
    "n": 121,
    "mean": 441.8072652892562,
    "std": 146.36447693063133,
    "min": 149.6525,
    "p05": 191.2201,
    "p50": 440.7523,
    "p95": 663.2347,
    "max": 870.8591,
    "baseline": 400.0
  },
  "kpi::ending_inventory": {
    "n": 121,
    "mean": 5477.637791735538,
    "std": 1093.7295562693537,
    "min": 3234.6004,
    "p05": 3898.6729,
    "p50": 5511.5789,
    "p95": 7563.2545,
    "max": 8124.6104,
    "baseline": 4937.9023
  },
  "kpi::fill_rate": {
    "n": 121,
    "mean": 0.7124447520661157,
    "std": 0.07993744828604415,
    "min": 0.503776,
    "p05": 0.606348,
    "p50": 0.7,
    "p95": 0.865474,
    "max": 0.889238,
    "baseline": 0.733333
  },
  "kpi::total_arrived": {
    "n": 121,
    "mean": 45832.38341900826,
    "std": 5433.809235202365,
    "min": 34354.2394,
    "p05": 37084.4317,
    "p50": 45965.3202,
    "p95": 55602.226,
    "max": 58391.0716,
    "baseline": 45776.5532
  },
  "kpi::total_cost": {
    "n": 121,
    "mean": 7967.984404958677,
    "std": 973.1746595372424,
    "min": 5876.0388,
    "p05": 6460.1765,
    "p50": 7939.6726,
    "p95": 9730.1038,
    "max": 10748.402,
    "baseline": 7392.806
  },
  "kpi::total_demand": {
    "n": 121,
    "mean": 1515.6808933884297,
    "std": 135.74098098383007,
    "min": 1222.6395,
    "p05": 1299.7957,
    "p50": 1507.854,
    "p95": 1726.7003,
    "max": 1872.831,
    "baseline": 1500.0
  },
  "kpi::total_external_procured_qty": {
    "n": 121,
    "mean": 55263.074638842976,
    "std": 6905.84620321608,
    "min": 41035.7237,
    "p05": 44970.6812,
    "p50": 54970.106,
    "p95": 67395.738,
    "max": 70569.3923,
    "baseline": 54542.0385
  },
  "kpi::total_holding_cost": {
    "n": 121,
    "mean": 7082.301232231405,
    "std": 956.3407927029906,
    "min": 5073.1996,
    "p05": 5531.4515,
    "p50": 7017.7884,
    "p95": 8835.8928,
    "max": 9845.5781,
    "baseline": 6526.9631
  },
  "kpi::total_logistics_cost": {
    "n": 121,
    "mean": 7214.303195867768,
    "std": 959.4609051410705,
    "min": 5189.8192,
    "p05": 5656.2013,
    "p50": 7143.5521,
    "p95": 8963.3672,
    "max": 9976.6161,
    "baseline": 6648.7631
  },
  "kpi::total_opening_stock_bootstrap_qty": {
    "n": 121,
    "mean": 15648.48480247934,
    "std": 2520.5196927610446,
    "min": 10611.3264,
    "p05": 11718.7583,
    "p50": 15445.1497,
    "p95": 19891.742,
    "max": 22299.8529,
    "baseline": 14935.183
  },
  "kpi::total_produced": {
    "n": 121,
    "mean": 1519.3214917355372,
    "std": 131.096261994373,
    "min": 1205.6077,
    "p05": 1326.207,
    "p50": 1535.8245,
    "p95": 1716.7215,
    "max": 1917.6105,
    "baseline": 1500.0
  },
  "kpi::total_purchase_cost": {
    "n": 121,
    "mean": 753.6812123966943,
    "std": 65.41447101805781,
    "min": 599.4327,
    "p05": 653.8876,
    "p50": 758.7925,
    "p95": 855.209,
    "max": 951.3844,
    "baseline": 744.0429
  },
  "kpi::total_served": {
    "n": 121,
    "mean": 1073.8736305785123,
    "std": 103.4709427094724,
    "min": 771.4119,
    "p05": 884.1123,
    "p50": 1078.2235,
    "p95": 1218.9369,
    "max": 1278.4779,
    "baseline": 1100.0
  },
  "kpi::total_shipped": {
    "n": 121,
    "mean": 61961.887721487605,
    "std": 7070.043818609998,
    "min": 47511.9004,
    "p05": 50967.8938,
    "p50": 61761.7081,
    "p95": 74447.9644,
    "max": 77860.4247,
    "baseline": 61192.9362
  },
  "kpi::total_transport_cost": {
    "n": 121,
    "mean": 132.00196694214875,
    "std": 23.31044069740009,
    "min": 85.9026,
    "p05": 100.6281,
    "p50": 127.6506,
    "p95": 172.9036,
    "max": 207.5868,
    "baseline": 121.8
  },
  "kpi::total_unreliable_loss_qty": {
    "n": 121,
    "mean": 0.0,
    "std": 0.0,
    "min": 0.0,
    "p05": 0.0,
    "p50": 0.0,
    "p95": 0.0,
    "max": 0.0,
    "baseline": 0.0
  }
}

## Top Runs
- Best fill rate: [{"run_id": "run_0032", "kpi::fill_rate": 0.889238}, {"run_id": "run_0117", "kpi::fill_rate": 0.872469}, {"run_id": "run_0109", "kpi::fill_rate": 0.871485}, {"run_id": "run_0019", "kpi::fill_rate": 0.869255}, {"run_id": "run_0027", "kpi::fill_rate": 0.868773}, {"run_id": "run_0002", "kpi::fill_rate": 0.865854}, {"run_id": "run_0107", "kpi::fill_rate": 0.865474}, {"run_id": "run_0067", "kpi::fill_rate": 0.864465}, {"run_id": "run_0025", "kpi::fill_rate": 0.85921}, {"run_id": "run_0089", "kpi::fill_rate": 0.854747}]
- Worst fill rate: [{"run_id": "run_0068", "kpi::fill_rate": 0.503776}, {"run_id": "run_0085", "kpi::fill_rate": 0.521389}, {"run_id": "run_0017", "kpi::fill_rate": 0.541165}, {"run_id": "run_0045", "kpi::fill_rate": 0.567717}, {"run_id": "run_0010", "kpi::fill_rate": 0.591825}, {"run_id": "run_0043", "kpi::fill_rate": 0.602474}, {"run_id": "run_0026", "kpi::fill_rate": 0.606348}, {"run_id": "run_0091", "kpi::fill_rate": 0.607098}, {"run_id": "run_0033", "kpi::fill_rate": 0.607181}, {"run_id": "run_0054", "kpi::fill_rate": 0.60925}]
- Lowest total cost: [{"run_id": "run_0111", "kpi::total_cost": 5876.0388}, {"run_id": "run_0012", "kpi::total_cost": 5930.3915}, {"run_id": "run_0050", "kpi::total_cost": 6076.9945}, {"run_id": "run_0064", "kpi::total_cost": 6174.058}, {"run_id": "run_0037", "kpi::total_cost": 6246.8844}, {"run_id": "run_0083", "kpi::total_cost": 6390.5585}, {"run_id": "run_0067", "kpi::total_cost": 6460.1765}, {"run_id": "run_0008", "kpi::total_cost": 6511.5232}, {"run_id": "run_0021", "kpi::total_cost": 6511.947}, {"run_id": "run_0020", "kpi::total_cost": 6520.1468}]
- Highest total cost: [{"run_id": "run_0013", "kpi::total_cost": 10748.402}, {"run_id": "run_0107", "kpi::total_cost": 10006.3199}, {"run_id": "run_0045", "kpi::total_cost": 9947.153}, {"run_id": "run_0044", "kpi::total_cost": 9859.7178}, {"run_id": "run_0099", "kpi::total_cost": 9845.545}, {"run_id": "run_0081", "kpi::total_cost": 9774.9538}, {"run_id": "run_0066", "kpi::total_cost": 9730.1038}, {"run_id": "run_0026", "kpi::total_cost": 9625.6581}, {"run_id": "run_0042", "kpi::total_cost": 9623.4191}, {"run_id": "run_0119", "kpi::total_cost": 9520.8994}]

## Files
- montecarlo_samples.csv
- montecarlo_summary.json
- montecarlo_report.md
