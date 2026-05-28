# Monte Carlo Analysis Report

## Setup
- Input: etudecas\simulation_prep\result\reference_baseline\_mrp_bom_tests\bom_weekly_mps_lotified_no_static_fallback_physical_floor.json
- Scenario: scn:BASE
- Days override: 365
- Seed: 20260526
- Uncertainty profile: risk_probe
- Runs requested (excluding baseline): 200
- Runs total (including baseline): 201
- Runs success: 201
- Stochastic runs success: 200
- Runs failed: 0
- Keep run artifacts: False

## Decision Metrics
{
  "fill_rate_below_100pct": 0.155,
  "fill_rate_below_99pct": 0.145,
  "backlog_positive": 0.155,
  "total_cost_above_baseline": 0.475,
  "inventory_cost_above_baseline": 0.73,
  "supplier_capacity_binding_above_baseline": 1.0
}

## KPI Statistics (distribution over successful runs)
{
  "kpi::avg_inventory": {
    "n": 200,
    "mean": 793050302.8596725,
    "std": 136378507.31838062,
    "min": 509130416.0283,
    "p05": 562564608.5218849,
    "p50": 809195399.85875,
    "p95": 1006318031.96857,
    "max": 1057621079.5089,
    "baseline": 792769665.058
  },
  "kpi::cost_share_holding": {
    "n": 200,
    "mean": 0.086665135,
    "std": 0.011596467281322144,
    "min": 0.059103,
    "p05": 0.06971795,
    "p50": 0.085699,
    "p95": 0.1074259,
    "max": 0.120279,
    "baseline": 0.082313
  },
  "kpi::cost_share_inventory_risk": {
    "n": 200,
    "mean": 0.04952297,
    "std": 0.006626571860253234,
    "min": 0.033773,
    "p05": 0.0398394,
    "p50": 0.048971,
    "p95": 0.0613865,
    "max": 0.068731,
    "baseline": 0.047036
  },
  "kpi::cost_share_production": {
    "n": 200,
    "mean": 0.3,
    "std": 0.0,
    "min": 0.3,
    "p05": 0.3,
    "p50": 0.3,
    "p95": 0.3,
    "max": 0.3,
    "baseline": 0.3
  },
  "kpi::cost_share_purchase": {
    "n": 200,
    "mean": 0.383252995,
    "std": 0.03756554856733727,
    "min": 0.28158,
    "p05": 0.31696905,
    "p50": 0.383765,
    "p95": 0.4409401,
    "max": 0.465026,
    "baseline": 0.405492
  },
  "kpi::cost_share_transport": {
    "n": 200,
    "mean": 0.069132315,
    "std": 0.007785950003421227,
    "min": 0.05187,
    "p05": 0.057447450000000004,
    "p50": 0.06839500000000001,
    "p95": 0.08359099999999997,
    "max": 0.092768,
    "baseline": 0.059329
  },
  "kpi::cost_share_warehouse_operating": {
    "n": 200,
    "mean": 0.111426575,
    "std": 0.01490970676185065,
    "min": 0.07599,
    "p05": 0.08963765,
    "p50": 0.11018449999999999,
    "p95": 0.13811915,
    "max": 0.154644,
    "baseline": 0.105831
  },
  "kpi::ending_backlog": {
    "n": 200,
    "mean": 56223.397287,
    "std": 161303.36011376328,
    "min": 0.0,
    "p05": 0.0,
    "p50": 0.0,
    "p95": 478317.93875999964,
    "max": 900165.3941,
    "baseline": 0.0
  },
  "kpi::ending_inventory": {
    "n": 200,
    "mean": 854818792.779632,
    "std": 184618874.25669578,
    "min": 506174931.9811,
    "p05": 554486694.4394,
    "p50": 869390785.43195,
    "p95": 1146202114.908925,
    "max": 1222743242.6605,
    "baseline": 817699006.1844
  },
  "kpi::fill_rate": {
    "n": 200,
    "mean": 0.989904215,
    "std": 0.028389298233643872,
    "min": 0.851492,
    "p05": 0.9118256000000001,
    "p50": 1.0,
    "p95": 1.0,
    "max": 1.0,
    "baseline": 1.0
  },
  "kpi::measured_required_total": {
    "n": 200,
    "mean": 5320824.3497325,
    "std": 405568.0843074426,
    "min": 4374187.6632,
    "p05": 4684666.40465,
    "p50": 5320397.1712,
    "p95": 6010447.479959999,
    "max": 6559111.3761,
    "baseline": 5152428.0
  },
  "kpi::measurement_starting_backlog": {
    "n": 200,
    "mean": 0.0,
    "std": 0.0,
    "min": 0.0,
    "p05": 0.0,
    "p50": 0.0,
    "p95": 0.0,
    "max": 0.0,
    "baseline": 0.0
  },
  "kpi::total_arrived": {
    "n": 200,
    "mean": 400462490.4157595,
    "std": 170265585.30329463,
    "min": 125685402.9852,
    "p05": 133688023.606465,
    "p50": 478447149.91585,
    "p95": 588218068.11436,
    "max": 610901719.6694,
    "baseline": 488771958.8388
  },
  "kpi::total_cost": {
    "n": 200,
    "mean": 17584698.1025295,
    "std": 2634405.820535884,
    "min": 12061353.312,
    "p05": 13543162.28248,
    "p50": 17458029.402149998,
    "p95": 22061387.483714998,
    "max": 24857442.1861,
    "baseline": 17589815.1881
  },
  "kpi::total_demand": {
    "n": 200,
    "mean": 5320824.3497325,
    "std": 405568.0843074426,
    "min": 4374187.6632,
    "p05": 4684666.40465,
    "p50": 5320397.1712,
    "p95": 6010447.479959999,
    "max": 6559111.3761,
    "baseline": 5152428.0
  },
  "kpi::total_estimated_source_ordered_qty": {
    "n": 200,
    "mean": 0.0,
    "std": 0.0,
    "min": 0.0,
    "p05": 0.0,
    "p50": 0.0,
    "p95": 0.0,
    "max": 0.0,
    "baseline": 0.0
  },
  "kpi::total_estimated_source_rejected_qty": {
    "n": 200,
    "mean": 0.0,
    "std": 0.0,
    "min": 0.0,
    "p05": 0.0,
    "p50": 0.0,
    "p95": 0.0,
    "max": 0.0,
    "baseline": 0.0
  },
  "kpi::total_estimated_source_replenished_qty": {
    "n": 200,
    "mean": 0.0,
    "std": 0.0,
    "min": 0.0,
    "p05": 0.0,
    "p50": 0.0,
    "p95": 0.0,
    "max": 0.0,
    "baseline": 0.0
  },
  "kpi::total_explicit_initialization_pipeline_qty": {
    "n": 200,
    "mean": 382906532.9077105,
    "std": 56881381.42252634,
    "min": 280799338.5267,
    "p05": 303381000.657035,
    "p50": 374396449.7845,
    "p95": 484982312.98172504,
    "max": 566865455.6293,
    "baseline": 303596359.9729
  },
  "kpi::total_explicit_initialization_stock_qty": {
    "n": 200,
    "mean": 754600.0,
    "std": 0.0,
    "min": 754600.0,
    "p05": 754600.0,
    "p50": 754600.0,
    "p95": 754600.0,
    "max": 754600.0,
    "baseline": 754600.0
  },
  "kpi::total_external_procured_arrived_qty": {
    "n": 200,
    "mean": 602328979.667762,
    "std": 195425332.62724873,
    "min": 226512667.1081,
    "p05": 288601348.732835,
    "p50": 625648269.2105999,
    "p95": 889359585.6962099,
    "max": 1005052889.3232,
    "baseline": 486715499.818
  },
  "kpi::total_external_procured_ordered_qty": {
    "n": 200,
    "mean": 290485934.4203155,
    "std": 170031980.17729598,
    "min": 15398931.0514,
    "p05": 21628449.417165,
    "p50": 342060261.3217,
    "p95": 496271703.94375,
    "max": 568886364.3508,
    "baseline": 259836932.546
  },
  "kpi::total_external_procured_qty": {
    "n": 200,
    "mean": 290485934.4203155,
    "std": 170031980.17729598,
    "min": 15398931.0514,
    "p05": 21628449.417165,
    "p50": 342060261.3217,
    "p95": 496271703.94375,
    "max": 568886364.3508,
    "baseline": 259836932.546
  },
  "kpi::total_external_procured_rejected_qty": {
    "n": 200,
    "mean": 1690484613.9759624,
    "std": 1531298264.127523,
    "min": 44919005.1551,
    "p05": 72134898.98812,
    "p50": 1346474607.5889,
    "p95": 4715212185.745534,
    "max": 7616888037.6027,
    "baseline": 781238311.2852
  },
  "kpi::total_external_procurement_cost": {
    "n": 200,
    "mean": 31255145.151244,
    "std": 13612825.89287564,
    "min": 5065844.8609,
    "p05": 8062838.87356,
    "p50": 32613410.5874,
    "p95": 53230772.39447,
    "max": 60143234.968,
    "baseline": 23691384.1758
  },
  "kpi::total_holding_cost": {
    "n": 200,
    "mean": 1496432.9374985,
    "std": 89044.87154842718,
    "min": 1261254.0106,
    "p05": 1356376.5993549998,
    "p50": 1492949.1076500001,
    "p95": 1639960.452785,
    "max": 1736310.4681,
    "baseline": 1447864.7509
  },
  "kpi::total_inventory_cost_legacy_raw_holding": {
    "n": 200,
    "mean": 4275522.6785695,
    "std": 254413.91870633297,
    "min": 3603582.8873,
    "p05": 3875361.712315,
    "p50": 4265568.879000001,
    "p95": 4685601.293579999,
    "max": 4960887.0517,
    "baseline": 4136756.431
  },
  "kpi::total_inventory_risk_cost": {
    "n": 200,
    "mean": 855104.5357115,
    "std": 50882.78373883578,
    "min": 720716.5775,
    "p05": 775072.3425,
    "p50": 853113.7758,
    "p95": 937120.2587349999,
    "max": 992177.4103,
    "baseline": 827351.2862
  },
  "kpi::total_logistics_cost": {
    "n": 200,
    "mean": 5479679.971182,
    "std": 323354.417876752,
    "min": 4655807.8854,
    "p05": 4981664.488015,
    "p50": 5482703.475649999,
    "p95": 5981404.461679999,
    "max": 6419345.1319,
    "baseline": 5180340.6681
  },
  "kpi::total_opening_open_order_qty": {
    "n": 200,
    "mean": 68338188.0,
    "std": 0.0,
    "min": 68338188.0,
    "p05": 68338188.0,
    "p50": 68338188.0,
    "p95": 68338188.0,
    "max": 68338188.0,
    "baseline": 68338188.0
  },
  "kpi::total_opening_stock_bootstrap_qty": {
    "n": 200,
    "mean": 0.0,
    "std": 0.0,
    "min": 0.0,
    "p05": 0.0,
    "p50": 0.0,
    "p95": 0.0,
    "max": 0.0,
    "baseline": 0.0
  },
  "kpi::total_produced": {
    "n": 200,
    "mean": 32364828.262521,
    "std": 3918073.408246825,
    "min": 21999800.0,
    "p05": 25427290.0,
    "p50": 31890100.0,
    "p95": 39245050.0,
    "max": 42458000.0,
    "baseline": 24651200.0
  },
  "kpi::total_production_cost": {
    "n": 200,
    "mean": 5275409.4307565,
    "std": 790321.7461586391,
    "min": 3618405.9936,
    "p05": 4062948.68479,
    "p50": 5237408.82065,
    "p95": 6618416.245074999,
    "max": 7457232.6558,
    "baseline": 5276944.5564
  },
  "kpi::total_purchase_cost": {
    "n": 200,
    "mean": 6829608.700589,
    "std": 1638937.1661757063,
    "min": 3428059.5433,
    "p05": 4321028.7634000005,
    "p50": 6686076.11035,
    "p95": 9752722.028685,
    "max": 11559348.6768,
    "baseline": 7132529.9636
  },
  "kpi::total_served": {
    "n": 200,
    "mean": 5264600.9524455,
    "std": 400344.24206067156,
    "min": 4374187.6632,
    "p05": 4671395.65506,
    "p50": 5227183.8455,
    "p95": 5956143.952594999,
    "max": 6559111.3761,
    "baseline": 5152428.0
  },
  "kpi::total_shipped": {
    "n": 200,
    "mean": 334525259.074926,
    "std": 170362190.7751673,
    "min": 62132190.4356,
    "p05": 68753406.327135,
    "p50": 412599283.29345,
    "p95": 522345220.33278,
    "max": 544525022.54,
    "baseline": 429257525.8388
  },
  "kpi::total_supplier_capacity_binding_qty": {
    "n": 200,
    "mean": 8556228.979769,
    "std": 17511615.631472178,
    "min": 1337647.9115,
    "p05": 2703978.829360001,
    "p50": 7028561.7785,
    "p95": 11942490.267515,
    "max": 224613081.3449,
    "baseline": 773234.3333
  },
  "kpi::total_transport_cost": {
    "n": 200,
    "mean": 1204157.2926185,
    "std": 151939.66841045037,
    "min": 831022.8663,
    "p05": 996209.567825,
    "p50": 1204184.0343,
    "p95": 1494857.62302,
    "max": 1643272.0994,
    "baseline": 1043584.2371
  },
  "kpi::total_unreliable_loss_qty": {
    "n": 200,
    "mean": 22163994.7960095,
    "std": 17294395.11597748,
    "min": 804419.4988,
    "p05": 1970786.8458899998,
    "p50": 20749321.2376,
    "p95": 52927283.40832499,
    "max": 70691874.6942,
    "baseline": 0.0
  },
  "kpi::total_warehouse_operating_cost": {
    "n": 200,
    "mean": 1923985.2053555,
    "std": 114486.26341725758,
    "min": 1621612.2993,
    "p05": 1743912.770555,
    "p50": 1919505.99555,
    "p95": 2108520.582155,
    "max": 2232399.1733,
    "baseline": 1861540.394
  },
  "kpi::warmup_backlog_cleared_qty": {
    "n": 200,
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

## Top Drivers
{
  "kpi::fill_rate": [
    {
      "factor": "factor::supplier_capacity_scale",
      "correlation": 0.5516844307213662,
      "absolute_correlation": 0.5516844307213662
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0910216A",
      "correlation": 0.265047343684982,
      "absolute_correlation": 0.265047343684982
    },
    {
      "factor": "demand_item::item:268091",
      "correlation": -0.2455682201675166,
      "absolute_correlation": 0.2455682201675166
    },
    {
      "factor": "factor::production_stock_scale",
      "correlation": 0.21324659662250273,
      "absolute_correlation": 0.21324659662250273
    },
    {
      "factor": "supplier_lead_node::SDC-VD0960508A",
      "correlation": -0.19397898769932176,
      "absolute_correlation": 0.19397898769932176
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0520115A",
      "correlation": 0.1692495988395323,
      "absolute_correlation": 0.1692495988395323
    },
    {
      "factor": "supplier_reliability_node::SDC-VD0910216A",
      "correlation": 0.16024919656816444,
      "absolute_correlation": 0.16024919656816444
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0964290A",
      "correlation": -0.15809707725601999,
      "absolute_correlation": 0.15809707725601999
    },
    {
      "factor": "supplier_lead_node::SDC-VD0989480A",
      "correlation": 0.1487020575800291,
      "absolute_correlation": 0.1487020575800291
    },
    {
      "factor": "supplier_reliability_node::SDC-VD1096202A",
      "correlation": -0.14093417233025007,
      "absolute_correlation": 0.14093417233025007
    },
    {
      "factor": "supplier_stock_node::SDC-VD0500655A",
      "correlation": -0.12456623430308339,
      "absolute_correlation": 0.12456623430308339
    },
    {
      "factor": "supplier_reliability_node::SDC-VD0989480A",
      "correlation": 0.12217420597323758,
      "absolute_correlation": 0.12217420597323758
    }
  ],
  "kpi::ending_backlog": [
    {
      "factor": "factor::supplier_capacity_scale",
      "correlation": -0.5402998998535502,
      "absolute_correlation": 0.5402998998535502
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0910216A",
      "correlation": -0.26053272891497264,
      "absolute_correlation": 0.26053272891497264
    },
    {
      "factor": "demand_item::item:268091",
      "correlation": 0.24960472148082344,
      "absolute_correlation": 0.24960472148082344
    },
    {
      "factor": "factor::production_stock_scale",
      "correlation": -0.2090172532206145,
      "absolute_correlation": 0.2090172532206145
    },
    {
      "factor": "supplier_lead_node::SDC-VD0960508A",
      "correlation": 0.20317121785476716,
      "absolute_correlation": 0.20317121785476716
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0520115A",
      "correlation": -0.1725254100985938,
      "absolute_correlation": 0.1725254100985938
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0964290A",
      "correlation": 0.15597785356921992,
      "absolute_correlation": 0.15597785356921992
    },
    {
      "factor": "supplier_reliability_node::SDC-VD0910216A",
      "correlation": -0.15263683829803468,
      "absolute_correlation": 0.15263683829803468
    },
    {
      "factor": "supplier_lead_node::SDC-VD0989480A",
      "correlation": -0.14929226908973184,
      "absolute_correlation": 0.14929226908973184
    },
    {
      "factor": "supplier_reliability_node::SDC-VD1096202A",
      "correlation": 0.13907383057494,
      "absolute_correlation": 0.13907383057494
    },
    {
      "factor": "supplier_stock_node::SDC-VD0500655A",
      "correlation": 0.12702834008513833,
      "absolute_correlation": 0.12702834008513833
    },
    {
      "factor": "supplier_stock_node::SDC-VD0975221A",
      "correlation": 0.1238920386863922,
      "absolute_correlation": 0.1238920386863922
    }
  ],
  "kpi::total_cost": [
    {
      "factor": "factor::lead_time_scale",
      "correlation": 0.5199047809609743,
      "absolute_correlation": 0.5199047809609743
    },
    {
      "factor": "factor::supplier_capacity_scale",
      "correlation": 0.45994374992592224,
      "absolute_correlation": 0.45994374992592224
    },
    {
      "factor": "demand_item::item:268091",
      "correlation": 0.4321392416344801,
      "absolute_correlation": 0.4321392416344801
    },
    {
      "factor": "factor::demand_scale",
      "correlation": 0.36134838568447025,
      "absolute_correlation": 0.36134838568447025
    },
    {
      "factor": "supplier_lead_node::SDC-VD0914360C",
      "correlation": 0.3141480959534294,
      "absolute_correlation": 0.3141480959534294
    },
    {
      "factor": "factor::supplier_stock_scale",
      "correlation": -0.24797142192492222,
      "absolute_correlation": 0.24797142192492222
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0914690A",
      "correlation": 0.22117071573410513,
      "absolute_correlation": 0.22117071573410513
    },
    {
      "factor": "supplier_stock_node::SDC-VD0519670A",
      "correlation": -0.19083148356838633,
      "absolute_correlation": 0.19083148356838633
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0520132A",
      "correlation": 0.18890161282980747,
      "absolute_correlation": 0.18890161282980747
    },
    {
      "factor": "supplier_lead_node::SDC-VD0960508A",
      "correlation": -0.17688150497106483,
      "absolute_correlation": 0.17688150497106483
    },
    {
      "factor": "supplier_lead_node::SDC-VD0901566A",
      "correlation": 0.15355159944310648,
      "absolute_correlation": 0.15355159944310648
    },
    {
      "factor": "supplier_capacity_node::SDC-VD1096202A",
      "correlation": -0.1529992882078748,
      "absolute_correlation": 0.1529992882078748
    }
  ],
  "kpi::total_produced": [
    {
      "factor": "factor::lead_time_scale",
      "correlation": 0.5232566332462727,
      "absolute_correlation": 0.5232566332462727
    },
    {
      "factor": "factor::demand_scale",
      "correlation": 0.44819471471192623,
      "absolute_correlation": 0.44819471471192623
    },
    {
      "factor": "factor::supplier_reliability_scale",
      "correlation": -0.4443051153370245,
      "absolute_correlation": 0.4443051153370245
    },
    {
      "factor": "demand_item::item:268967",
      "correlation": 0.41605972236546573,
      "absolute_correlation": 0.41605972236546573
    },
    {
      "factor": "factor::supplier_stock_scale",
      "correlation": -0.37310410278652384,
      "absolute_correlation": 0.37310410278652384
    },
    {
      "factor": "supplier_capacity_node::SDC-VD1096202A",
      "correlation": -0.19176620250476065,
      "absolute_correlation": 0.19176620250476065
    },
    {
      "factor": "supplier_stock_node::SDC-VD0520132A",
      "correlation": -0.15993603208661764,
      "absolute_correlation": 0.15993603208661764
    },
    {
      "factor": "factor::production_stock_scale",
      "correlation": -0.15358436845145235,
      "absolute_correlation": 0.15358436845145235
    },
    {
      "factor": "supplier_stock_node::SDC-VD0519670A",
      "correlation": -0.15301381756998564,
      "absolute_correlation": 0.15301381756998564
    },
    {
      "factor": "supplier_reliability_node::SDC-VD0514881A",
      "correlation": -0.1528001714356264,
      "absolute_correlation": 0.1528001714356264
    },
    {
      "factor": "supplier_lead_node::SDC-VD0993480A",
      "correlation": 0.14395883640430762,
      "absolute_correlation": 0.14395883640430762
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0964290A",
      "correlation": -0.14213898289536203,
      "absolute_correlation": 0.14213898289536203
    }
  ]
}

## Top Runs
- Best fill rate: [{"run_id": "run_0001", "kpi::fill_rate": 1.0}, {"run_id": "run_0002", "kpi::fill_rate": 1.0}, {"run_id": "run_0003", "kpi::fill_rate": 1.0}, {"run_id": "run_0004", "kpi::fill_rate": 1.0}, {"run_id": "run_0006", "kpi::fill_rate": 1.0}, {"run_id": "run_0008", "kpi::fill_rate": 1.0}, {"run_id": "run_0010", "kpi::fill_rate": 1.0}, {"run_id": "run_0011", "kpi::fill_rate": 1.0}, {"run_id": "run_0012", "kpi::fill_rate": 1.0}, {"run_id": "run_0014", "kpi::fill_rate": 1.0}]
- Worst fill rate: [{"run_id": "run_0183", "kpi::fill_rate": 0.851492}, {"run_id": "run_0172", "kpi::fill_rate": 0.856741}, {"run_id": "run_0101", "kpi::fill_rate": 0.874095}, {"run_id": "run_0128", "kpi::fill_rate": 0.886369}, {"run_id": "run_0195", "kpi::fill_rate": 0.891093}, {"run_id": "run_0103", "kpi::fill_rate": 0.892958}, {"run_id": "run_0007", "kpi::fill_rate": 0.900219}, {"run_id": "run_0120", "kpi::fill_rate": 0.901569}, {"run_id": "run_0013", "kpi::fill_rate": 0.9085}, {"run_id": "run_0055", "kpi::fill_rate": 0.908721}]
- Lowest total cost: [{"run_id": "run_0124", "kpi::total_cost": 12061353.312}, {"run_id": "run_0154", "kpi::total_cost": 12182268.616}, {"run_id": "run_0133", "kpi::total_cost": 12506640.8693}, {"run_id": "run_0071", "kpi::total_cost": 12797734.9745}, {"run_id": "run_0005", "kpi::total_cost": 12880866.0725}, {"run_id": "run_0041", "kpi::total_cost": 12981209.4113}, {"run_id": "run_0063", "kpi::total_cost": 13144140.854}, {"run_id": "run_0107", "kpi::total_cost": 13341323.0822}, {"run_id": "run_0101", "kpi::total_cost": 13409484.6877}, {"run_id": "run_0162", "kpi::total_cost": 13445296.6261}]
- Highest total cost: [{"run_id": "run_0025", "kpi::total_cost": 24857442.1861}, {"run_id": "run_0085", "kpi::total_cost": 23708610.8651}, {"run_id": "run_0088", "kpi::total_cost": 23290093.6145}, {"run_id": "run_0023", "kpi::total_cost": 23245735.972}, {"run_id": "run_0173", "kpi::total_cost": 23110079.7612}, {"run_id": "run_0182", "kpi::total_cost": 22749226.9171}, {"run_id": "run_0184", "kpi::total_cost": 22734955.8588}, {"run_id": "run_0186", "kpi::total_cost": 22716580.0705}, {"run_id": "run_0048", "kpi::total_cost": 22526961.7553}, {"run_id": "run_0021", "kpi::total_cost": 22281974.6321}]

## Files
- montecarlo_samples.csv
- montecarlo_summary.json
- montecarlo_report.md
