# Full System Exploration Report

## Setup
- Input: etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json
- Scenario: scn:BASE
- Days override: 30
- Seed: 42
- Total runs: 437
  - Baseline: 1
  - Corner scenarios: 256
  - Random runs: 180
- Successful runs: 437
- Failed runs: 0

## KPI Statistics
{
  "kpi::avg_inventory": {
    "n": 437,
    "mean": 1039384.8693338673,
    "std": 232027.86006920476,
    "min": 553939.4475,
    "p05": 713627.1249200001,
    "p50": 1007204.3745,
    "p95": 1405930.8683600002,
    "max": 1683451.0016,
    "baseline": 1045717.0788
  },
  "kpi::cost_share_holding": {
    "n": 437,
    "mean": 0.9865110823798627,
    "std": 0.005890967615646105,
    "min": 0.969103,
    "p05": 0.9781407999999999,
    "p50": 0.986177,
    "p95": 0.9951792,
    "max": 0.997391,
    "baseline": 0.980377
  },
  "kpi::cost_share_purchase": {
    "n": 437,
    "mean": 0.0015845308924485127,
    "std": 0.0006986590012841779,
    "min": 0.000341,
    "p05": 0.0005890000000000001,
    "p50": 0.001613,
    "p95": 0.0026821999999999996,
    "max": 0.004143,
    "baseline": 0.002157
  },
  "kpi::cost_share_transport": {
    "n": 437,
    "mean": 0.011904405034324942,
    "std": 0.005238190715842188,
    "min": 0.002112,
    "p05": 0.0041294,
    "p50": 0.012102,
    "p95": 0.019344399999999998,
    "max": 0.027216,
    "baseline": 0.017466
  },
  "kpi::ending_backlog": {
    "n": 437,
    "mean": 823.835528375286,
    "std": 279.71247222000477,
    "min": 182.1019,
    "p05": 330.98582,
    "p50": 817.922,
    "p95": 1274.19212,
    "max": 1796.5975,
    "baseline": 315.8476
  },
  "kpi::ending_inventory": {
    "n": 437,
    "mean": 1025281.9433171625,
    "std": 229082.36949436998,
    "min": 542729.3844,
    "p05": 708156.25256,
    "p50": 1001883.5001,
    "p95": 1389290.13146,
    "max": 1668834.5788,
    "baseline": 1035949.2243
  },
  "kpi::fill_rate": {
    "n": 437,
    "mean": 0.4754364691075515,
    "std": 0.13567858326257393,
    "min": 0.202651,
    "p05": 0.29373,
    "p50": 0.450935,
    "p95": 0.7467364000000001,
    "max": 0.855975,
    "baseline": 0.787666
  },
  "kpi::total_arrived": {
    "n": 437,
    "mean": 9820.922544393592,
    "std": 5251.843805378678,
    "min": 2017.5074,
    "p05": 3549.10946,
    "p50": 8648.355,
    "p95": 20048.95234,
    "max": 28086.5618,
    "baseline": 15989.339
  },
  "kpi::total_cost": {
    "n": 437,
    "mean": 1318227.0920340961,
    "std": 338689.4771845262,
    "min": 634351.1339,
    "p05": 869238.7073799999,
    "p50": 1236366.1288,
    "p95": 1813949.5117199998,
    "max": 2912911.1708,
    "baseline": 1273360.3167
  },
  "kpi::total_demand": {
    "n": 437,
    "mean": 1552.6943496567505,
    "std": 272.96194161255175,
    "min": 931.8224,
    "p05": 1262.14716,
    "p50": 1567.7149,
    "p95": 1926.75266,
    "max": 2426.5445,
    "baseline": 1487.5
  },
  "kpi::total_external_procured_arrived_qty": {
    "n": 437,
    "mean": 27316.993516475974,
    "std": 13597.67176044095,
    "min": 5282.5578,
    "p05": 8063.715020000001,
    "p50": 26279.607,
    "p95": 50685.632280000005,
    "max": 63832.9032,
    "baseline": 42489.9504
  },
  "kpi::total_external_procured_ordered_qty": {
    "n": 437,
    "mean": 31431.74101784897,
    "std": 14202.391831056479,
    "min": 7099.4288,
    "p05": 10315.8596,
    "p50": 30458.4221,
    "p95": 55909.824499999995,
    "max": 64815.4112,
    "baseline": 42871.1216
  },
  "kpi::total_external_procured_qty": {
    "n": 437,
    "mean": 31431.74101784897,
    "std": 14202.391831056479,
    "min": 7099.4288,
    "p05": 10315.8596,
    "p50": 30458.4221,
    "p95": 55909.824499999995,
    "max": 64815.4112,
    "baseline": 42871.1216
  },
  "kpi::total_external_procured_rejected_qty": {
    "n": 437,
    "mean": 56870.663302059496,
    "std": 59250.92974183429,
    "min": 0.0,
    "p05": 0.0,
    "p50": 38940.5706,
    "p95": 176285.26812,
    "max": 332691.4435,
    "baseline": 18148.2001
  },
  "kpi::total_external_procurement_cost": {
    "n": 437,
    "mean": 2639.4541780320365,
    "std": 1297.0744114484596,
    "min": 594.6385,
    "p05": 755.5623,
    "p50": 2727.9315,
    "p95": 4838.519679999999,
    "max": 7189.2481,
    "baseline": 3318.2119
  },
  "kpi::total_holding_cost": {
    "n": 437,
    "mean": 1301213.169076888,
    "std": 337696.1386010203,
    "min": 628800.6083,
    "p05": 850656.3909400001,
    "p50": 1217209.613,
    "p95": 1799200.88436,
    "max": 2905218.7239,
    "baseline": 1248373.7888
  },
  "kpi::total_logistics_cost": {
    "n": 437,
    "mean": 1316229.7029256292,
    "std": 338561.5723191004,
    "min": 633674.9641,
    "p05": 867202.0106,
    "p50": 1235277.3638,
    "p95": 1811530.11808,
    "max": 2911393.0184,
    "baseline": 1270613.7549
  },
  "kpi::total_opening_stock_bootstrap_qty": {
    "n": 437,
    "mean": 1051245.6322059496,
    "std": 233058.7720417483,
    "min": 563326.6398,
    "p05": 724622.9464999998,
    "p50": 1023071.2186,
    "p95": 1415682.3521,
    "max": 1687835.4024,
    "baseline": 1060029.4897
  },
  "kpi::total_produced": {
    "n": 437,
    "mean": 2221.776600457666,
    "std": 381.35011520719087,
    "min": 1217.6269,
    "p05": 1718.14196,
    "p50": 2176.1107,
    "p95": 2959.46916,
    "max": 3306.1473,
    "baseline": 2610.2267
  },
  "kpi::total_purchase_cost": {
    "n": 437,
    "mean": 1997.389104805492,
    "std": 845.8530986313093,
    "min": 652.595,
    "p05": 804.4153399999999,
    "p50": 1988.0085,
    "p95": 3446.08456,
    "max": 5152.8322,
    "baseline": 2746.5618
  },
  "kpi::total_served": {
    "n": 437,
    "mean": 728.8588221967964,
    "std": 212.93297932269908,
    "min": 291.029,
    "p05": 413.09134,
    "p50": 691.7352,
    "p95": 1073.55086,
    "max": 1369.2496,
    "baseline": 1171.6524
  },
  "kpi::total_shipped": {
    "n": 437,
    "mean": 29632.01458604119,
    "std": 12279.777227609411,
    "min": 8834.0258,
    "p05": 12175.293700000002,
    "p50": 28806.3214,
    "p95": 46816.87014,
    "max": 62383.4476,
    "baseline": 45988.6462
  },
  "kpi::total_transport_cost": {
    "n": 437,
    "mean": 15016.533848512587,
    "std": 6440.42320871855,
    "min": 3622.6023,
    "p05": 5764.735320000001,
    "p50": 15204.4018,
    "p95": 25323.4101,
    "max": 34369.1883,
    "baseline": 22239.9661
  },
  "kpi::total_unreliable_loss_qty": {
    "n": 437,
    "mean": 2637.4512398169336,
    "std": 2742.5816587802087,
    "min": 0.0,
    "p05": 0.0,
    "p50": 1959.8037,
    "p95": 7799.23912,
    "max": 10553.4912,
    "baseline": 0.0
  }
}

## Risk Probabilities
{
  "p_fill_lt_0_90": 1.0,
  "p_fill_lt_0_85": 0.9931350114416476,
  "p_backlog_gt_100": 1.0,
  "p_backlog_gt_200": 0.9931350114416476,
  "p_cost_gt_24000": 1.0,
  "p_cost_gt_28000": 1.0,
  "p_fill_ge_baseline": 0.02288329519450801,
  "p_backlog_le_baseline": 0.036613272311212815,
  "p_cost_le_baseline": 0.5903890160183066
}

## Top Runs
- Best fill rate: [{"run_id": "full_run_0202", "kpi::fill_rate": 0.855975}, {"run_id": "full_run_0206", "kpi::fill_rate": 0.855975}, {"run_id": "full_run_0078", "kpi::fill_rate": 0.853522}, {"run_id": "full_run_0070", "kpi::fill_rate": 0.838748}, {"run_id": "full_run_0066", "kpi::fill_rate": 0.836395}, {"run_id": "full_run_0194", "kpi::fill_rate": 0.836395}, {"run_id": "full_run_0198", "kpi::fill_rate": 0.836395}, {"run_id": "full_run_0074", "kpi::fill_rate": 0.820042}, {"run_id": "full_run_0086", "kpi::fill_rate": 0.797892}, {"run_id": "full_run_0000", "kpi::fill_rate": 0.787666}]
- Worst fill rate: [{"run_id": "full_run_0352", "kpi::fill_rate": 0.202651}, {"run_id": "full_run_0261", "kpi::fill_rate": 0.21079}, {"run_id": "full_run_0366", "kpi::fill_rate": 0.216447}, {"run_id": "full_run_0402", "kpi::fill_rate": 0.23913}, {"run_id": "full_run_0346", "kpi::fill_rate": 0.245628}, {"run_id": "full_run_0317", "kpi::fill_rate": 0.261856}, {"run_id": "full_run_0318", "kpi::fill_rate": 0.261889}, {"run_id": "full_run_0394", "kpi::fill_rate": 0.265298}, {"run_id": "full_run_0059", "kpi::fill_rate": 0.269017}, {"run_id": "full_run_0063", "kpi::fill_rate": 0.269017}]
- Lowest total cost: [{"run_id": "full_run_0301", "kpi::total_cost": 634351.1339}, {"run_id": "full_run_0409", "kpi::total_cost": 704691.5005}, {"run_id": "full_run_0257", "kpi::total_cost": 723085.2929}, {"run_id": "full_run_0306", "kpi::total_cost": 727984.6966}, {"run_id": "full_run_0284", "kpi::total_cost": 739675.5199}, {"run_id": "full_run_0279", "kpi::total_cost": 764052.122}, {"run_id": "full_run_0308", "kpi::total_cost": 780619.4148}, {"run_id": "full_run_0379", "kpi::total_cost": 781899.8398}, {"run_id": "full_run_0275", "kpi::total_cost": 792414.0689}, {"run_id": "full_run_0354", "kpi::total_cost": 794055.833}]
- Highest total cost: [{"run_id": "full_run_0336", "kpi::total_cost": 2912911.1708}, {"run_id": "full_run_0346", "kpi::total_cost": 2613575.3475}, {"run_id": "full_run_0366", "kpi::total_cost": 2285752.6676}, {"run_id": "full_run_0358", "kpi::total_cost": 2273505.4218}, {"run_id": "full_run_0371", "kpi::total_cost": 2184547.0516}, {"run_id": "full_run_0287", "kpi::total_cost": 2146958.061}, {"run_id": "full_run_0281", "kpi::total_cost": 2133784.7636}, {"run_id": "full_run_0296", "kpi::total_cost": 2112994.5517}, {"run_id": "full_run_0431", "kpi::total_cost": 2101745.3115}, {"run_id": "full_run_0273", "kpi::total_cost": 2085553.8654}]

## Extreme Cases With Parameters
{
  "worst_fill_rate": {
    "run_id": "full_run_0352",
    "target_metric": "fill_rate",
    "target_metric_value": 0.202651,
    "metrics": {
      "avg_inventory": 1105054.5322,
      "cost_share_holding": 0.995683,
      "cost_share_purchase": 0.000612,
      "cost_share_transport": 0.003706,
      "ending_backlog": 1796.5975,
      "ending_inventory": 1090681.294,
      "fill_rate": 0.202651,
      "total_arrived": 4104.5124,
      "total_cost": 1646192.0463,
      "total_demand": 2253.2128,
      "total_external_procured_arrived_qty": 10731.2981,
      "total_external_procured_ordered_qty": 13913.6531,
      "total_external_procured_qty": 13913.6531,
      "total_external_procured_rejected_qty": 37480.5566,
      "total_external_procurement_cost": 1234.8209,
      "total_holding_cost": 1639084.682,
      "total_logistics_cost": 1645184.6847,
      "total_opening_stock_bootstrap_qty": 1113593.0614,
      "total_produced": 2290.3264,
      "total_purchase_cost": 1007.3616,
      "total_served": 456.6154,
      "total_shipped": 10897.8591,
      "total_transport_cost": 6100.0028,
      "total_unreliable_loss_qty": 2630.3423
    },
    "parameters": {
      "factors": {
        "capacity_scale": 1.077176,
        "demand_scale": 1.229786,
        "external_procurement_cost_multiplier_scale": 0.80749,
        "external_procurement_daily_cap_days_scale": 0.955812,
        "external_procurement_lead_days_scale": 1.675782,
        "external_procurement_transport_cost_scale": 1.028056,
        "fg_target_days_scale": 1.168395,
        "holding_cost_scale": 1.246819,
        "lead_time_scale": 0.964269,
        "production_gap_gain_scale": 1.390392,
        "production_smoothing_scale": 0.970516,
        "production_stock_scale": 1.424099,
        "purchase_cost_floor_scale": 1.60069,
        "review_period_scale": 6.0,
        "safety_stock_days_scale": 1.246005,
        "supplier_reliability_scale": 0.805566,
        "supplier_stock_scale": 0.801609,
        "transport_cost_scale": 1.236722
      },
      "demand_item_scale": {
        "item:268091": 1.442239,
        "item:268967": 1.021222
      },
      "capacity_node_scale": {
        "M-1430": 0.953073,
        "M-1810": 1.197071,
        "SDC-1450": 0.978806
      }
    }
  },
  "best_fill_rate": {
    "run_id": "full_run_0202",
    "target_metric": "fill_rate",
    "target_metric_value": 0.855975,
    "metrics": {
      "avg_inventory": 1010007.023,
      "cost_share_holding": 0.980266,
      "cost_share_purchase": 0.002103,
      "cost_share_transport": 0.017631,
      "ending_backlog": 182.1019,
      "ending_inventory": 1002581.5915,
      "fill_rate": 0.855975,
      "total_arrived": 16745.3989,
      "total_cost": 1229460.4726,
      "total_demand": 1264.375,
      "total_external_procured_arrived_qty": 40951.7785,
      "total_external_procured_ordered_qty": 42431.3215,
      "total_external_procured_qty": 42431.3215,
      "total_external_procured_rejected_qty": 80352.1028,
      "total_external_procurement_cost": 3209.2499,
      "total_holding_cost": 1205198.4329,
      "total_logistics_cost": 1226874.539,
      "total_opening_stock_bootstrap_qty": 1023071.2186,
      "total_produced": 2516.2533,
      "total_purchase_cost": 2585.9336,
      "total_served": 1082.2731,
      "total_shipped": 44534.8226,
      "total_transport_cost": 21676.1061,
      "total_unreliable_loss_qty": 0.0
    },
    "parameters": {
      "factors": {
        "capacity_scale": 1.2,
        "demand_scale": 0.85,
        "external_procurement_cost_multiplier_scale": 1.0,
        "external_procurement_daily_cap_days_scale": 0.5,
        "external_procurement_lead_days_scale": 1.8,
        "external_procurement_transport_cost_scale": 1.0,
        "fg_target_days_scale": 1.0,
        "holding_cost_scale": 1.0,
        "lead_time_scale": 0.8,
        "production_gap_gain_scale": 1.0,
        "production_smoothing_scale": 1.0,
        "production_stock_scale": 1.0,
        "purchase_cost_floor_scale": 1.0,
        "review_period_scale": 1.0,
        "safety_stock_days_scale": 1.0,
        "supplier_reliability_scale": 1.0,
        "supplier_stock_scale": 1.3,
        "transport_cost_scale": 1.0
      },
      "demand_item_scale": {
        "item:268091": 1.0,
        "item:268967": 1.0
      },
      "capacity_node_scale": {
        "M-1430": 1.0,
        "M-1810": 1.0,
        "SDC-1450": 1.0
      }
    }
  },
  "highest_total_cost": {
    "run_id": "full_run_0336",
    "target_metric": "total_cost",
    "target_metric_value": 2912911.1708,
    "metrics": {
      "avg_inventory": 1561062.6779,
      "cost_share_holding": 0.997359,
      "cost_share_purchase": 0.000521,
      "cost_share_transport": 0.00212,
      "ending_backlog": 1084.5821,
      "ending_inventory": 1549940.3029,
      "fill_rate": 0.300887,
      "total_arrived": 3783.704,
      "total_cost": 2912911.1708,
      "total_demand": 1551.3679,
      "total_external_procured_arrived_qty": 15000.8405,
      "total_external_procured_ordered_qty": 18702.8015,
      "total_external_procured_qty": 18702.8015,
      "total_external_procured_rejected_qty": 21624.7577,
      "total_external_procurement_cost": 2143.0035,
      "total_holding_cost": 2905218.7239,
      "total_logistics_cost": 2911393.0184,
      "total_opening_stock_bootstrap_qty": 1566570.6978,
      "total_produced": 1756.3513,
      "total_purchase_cost": 1518.1525,
      "total_served": 466.7858,
      "total_shipped": 14460.3253,
      "total_transport_cost": 6174.2945,
      "total_unreliable_loss_qty": 2545.2
    },
    "parameters": {
      "factors": {
        "capacity_scale": 1.076754,
        "demand_scale": 1.085121,
        "external_procurement_cost_multiplier_scale": 1.778123,
        "external_procurement_daily_cap_days_scale": 1.046948,
        "external_procurement_lead_days_scale": 2.063911,
        "external_procurement_transport_cost_scale": 1.689922,
        "fg_target_days_scale": 1.890961,
        "holding_cost_scale": 1.56092,
        "lead_time_scale": 1.364973,
        "production_gap_gain_scale": 0.838028,
        "production_smoothing_scale": 1.510898,
        "production_stock_scale": 1.017896,
        "purchase_cost_floor_scale": 1.071546,
        "review_period_scale": 5.0,
        "safety_stock_days_scale": 2.053355,
        "supplier_reliability_scale": 0.850331,
        "supplier_stock_scale": 1.134492,
        "transport_cost_scale": 0.855417
      },
      "demand_item_scale": {
        "item:268091": 1.264489,
        "item:268967": 0.65776
      },
      "capacity_node_scale": {
        "M-1430": 1.021133,
        "M-1810": 0.838975,
        "SDC-1450": 1.244673
      }
    }
  },
  "lowest_total_cost": {
    "run_id": "full_run_0301",
    "target_metric": "total_cost",
    "target_metric_value": 634351.1339,
    "metrics": {
      "avg_inventory": 587646.252,
      "cost_share_holding": 0.99125,
      "cost_share_purchase": 0.001066,
      "cost_share_transport": 0.007684,
      "ending_backlog": 862.832,
      "ending_inventory": 573921.7408,
      "fill_rate": 0.377405,
      "total_arrived": 4984.3305,
      "total_cost": 634351.1339,
      "total_demand": 1385.8643,
      "total_external_procured_arrived_qty": 5282.5578,
      "total_external_procured_ordered_qty": 7099.4288,
      "total_external_procured_qty": 7099.4288,
      "total_external_procured_rejected_qty": 79685.8233,
      "total_external_procurement_cost": 597.4515,
      "total_holding_cost": 628800.6083,
      "total_logistics_cost": 633674.9641,
      "total_opening_stock_bootstrap_qty": 596930.2876,
      "total_produced": 1692.6837,
      "total_purchase_cost": 676.1699,
      "total_served": 523.0323,
      "total_shipped": 8834.0258,
      "total_transport_cost": 4874.3558,
      "total_unreliable_loss_qty": 1448.3796
    },
    "parameters": {
      "factors": {
        "capacity_scale": 1.020043,
        "demand_scale": 1.064144,
        "external_procurement_cost_multiplier_scale": 0.937546,
        "external_procurement_daily_cap_days_scale": 0.2639,
        "external_procurement_lead_days_scale": 1.848247,
        "external_procurement_transport_cost_scale": 0.92516,
        "fg_target_days_scale": 0.921631,
        "holding_cost_scale": 0.899599,
        "lead_time_scale": 0.692428,
        "production_gap_gain_scale": 1.431874,
        "production_smoothing_scale": 0.96213,
        "production_stock_scale": 0.750922,
        "purchase_cost_floor_scale": 1.504141,
        "review_period_scale": 4.0,
        "safety_stock_days_scale": 0.694022,
        "supplier_reliability_scale": 0.85914,
        "supplier_stock_scale": 0.897894,
        "transport_cost_scale": 1.260691
      },
      "demand_item_scale": {
        "item:268091": 0.900392,
        "item:268967": 0.850637
      },
      "capacity_node_scale": {
        "M-1430": 1.052999,
        "M-1810": 0.768121,
        "SDC-1450": 0.751719
      }
    }
  },
  "highest_ending_backlog": {
    "run_id": "full_run_0352",
    "target_metric": "ending_backlog",
    "target_metric_value": 1796.5975,
    "metrics": {
      "avg_inventory": 1105054.5322,
      "cost_share_holding": 0.995683,
      "cost_share_purchase": 0.000612,
      "cost_share_transport": 0.003706,
      "ending_backlog": 1796.5975,
      "ending_inventory": 1090681.294,
      "fill_rate": 0.202651,
      "total_arrived": 4104.5124,
      "total_cost": 1646192.0463,
      "total_demand": 2253.2128,
      "total_external_procured_arrived_qty": 10731.2981,
      "total_external_procured_ordered_qty": 13913.6531,
      "total_external_procured_qty": 13913.6531,
      "total_external_procured_rejected_qty": 37480.5566,
      "total_external_procurement_cost": 1234.8209,
      "total_holding_cost": 1639084.682,
      "total_logistics_cost": 1645184.6847,
      "total_opening_stock_bootstrap_qty": 1113593.0614,
      "total_produced": 2290.3264,
      "total_purchase_cost": 1007.3616,
      "total_served": 456.6154,
      "total_shipped": 10897.8591,
      "total_transport_cost": 6100.0028,
      "total_unreliable_loss_qty": 2630.3423
    },
    "parameters": {
      "factors": {
        "capacity_scale": 1.077176,
        "demand_scale": 1.229786,
        "external_procurement_cost_multiplier_scale": 0.80749,
        "external_procurement_daily_cap_days_scale": 0.955812,
        "external_procurement_lead_days_scale": 1.675782,
        "external_procurement_transport_cost_scale": 1.028056,
        "fg_target_days_scale": 1.168395,
        "holding_cost_scale": 1.246819,
        "lead_time_scale": 0.964269,
        "production_gap_gain_scale": 1.390392,
        "production_smoothing_scale": 0.970516,
        "production_stock_scale": 1.424099,
        "purchase_cost_floor_scale": 1.60069,
        "review_period_scale": 6.0,
        "safety_stock_days_scale": 1.246005,
        "supplier_reliability_scale": 0.805566,
        "supplier_stock_scale": 0.801609,
        "transport_cost_scale": 1.236722
      },
      "demand_item_scale": {
        "item:268091": 1.442239,
        "item:268967": 1.021222
      },
      "capacity_node_scale": {
        "M-1430": 0.953073,
        "M-1810": 1.197071,
        "SDC-1450": 0.978806
      }
    }
  },
  "lowest_ending_backlog": {
    "run_id": "full_run_0202",
    "target_metric": "ending_backlog",
    "target_metric_value": 182.1019,
    "metrics": {
      "avg_inventory": 1010007.023,
      "cost_share_holding": 0.980266,
      "cost_share_purchase": 0.002103,
      "cost_share_transport": 0.017631,
      "ending_backlog": 182.1019,
      "ending_inventory": 1002581.5915,
      "fill_rate": 0.855975,
      "total_arrived": 16745.3989,
      "total_cost": 1229460.4726,
      "total_demand": 1264.375,
      "total_external_procured_arrived_qty": 40951.7785,
      "total_external_procured_ordered_qty": 42431.3215,
      "total_external_procured_qty": 42431.3215,
      "total_external_procured_rejected_qty": 80352.1028,
      "total_external_procurement_cost": 3209.2499,
      "total_holding_cost": 1205198.4329,
      "total_logistics_cost": 1226874.539,
      "total_opening_stock_bootstrap_qty": 1023071.2186,
      "total_produced": 2516.2533,
      "total_purchase_cost": 2585.9336,
      "total_served": 1082.2731,
      "total_shipped": 44534.8226,
      "total_transport_cost": 21676.1061,
      "total_unreliable_loss_qty": 0.0
    },
    "parameters": {
      "factors": {
        "capacity_scale": 1.2,
        "demand_scale": 0.85,
        "external_procurement_cost_multiplier_scale": 1.0,
        "external_procurement_daily_cap_days_scale": 0.5,
        "external_procurement_lead_days_scale": 1.8,
        "external_procurement_transport_cost_scale": 1.0,
        "fg_target_days_scale": 1.0,
        "holding_cost_scale": 1.0,
        "lead_time_scale": 0.8,
        "production_gap_gain_scale": 1.0,
        "production_smoothing_scale": 1.0,
        "production_stock_scale": 1.0,
        "purchase_cost_floor_scale": 1.0,
        "review_period_scale": 1.0,
        "safety_stock_days_scale": 1.0,
        "supplier_reliability_scale": 1.0,
        "supplier_stock_scale": 1.3,
        "transport_cost_scale": 1.0
      },
      "demand_item_scale": {
        "item:268091": 1.0,
        "item:268967": 1.0
      },
      "capacity_node_scale": {
        "M-1430": 1.0,
        "M-1810": 1.0,
        "SDC-1450": 1.0
      }
    }
  }
}
