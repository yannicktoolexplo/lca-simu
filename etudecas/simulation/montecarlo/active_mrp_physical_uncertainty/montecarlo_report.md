# Monte Carlo Analysis Report

## Setup
- Input: etudecas\simulation_prep\result\reference_baseline\_mrp_bom_tests\bom_weekly_mps_lotified_no_static_fallback_physical_floor.json
- Scenario: scn:BASE
- Days override: 1825
- Seed: 13
- Uncertainty profile: stress_probe
- Runs requested (excluding baseline): 10
- Runs total (including baseline): 11
- Runs success: 11
- Stochastic runs success: 10
- Runs failed: 0
- Keep run artifacts: False

## Decision Metrics
{
  "fill_rate_below_100pct": 1.0,
  "fill_rate_below_99pct": 1.0,
  "backlog_positive": 1.0,
  "total_cost_above_baseline": 0.8,
  "inventory_cost_above_baseline": 0.6,
  "supplier_capacity_binding_above_baseline": 1.0
}

## KPI Statistics (distribution over successful runs)
{
  "kpi::avg_inventory": {
    "n": 10,
    "mean": 717328864.6702,
    "std": 165831384.33487695,
    "min": 472969633.0408,
    "p05": 536356803.78839505,
    "p50": 650755547.4909999,
    "p95": 1002145104.2135649,
    "max": 1018014039.7258,
    "baseline": 577063086.7792
  },
  "kpi::cost_share_holding": {
    "n": 10,
    "mean": 0.1297646,
    "std": 0.016030264889888752,
    "min": 0.095844,
    "p05": 0.10177230000000001,
    "p50": 0.131343,
    "p95": 0.14883134999999997,
    "max": 0.154581,
    "baseline": 0.149176
  },
  "kpi::cost_share_inventory_risk": {
    "n": 10,
    "mean": 0.0741513,
    "std": 0.009160170239138572,
    "min": 0.054768,
    "p05": 0.0581556,
    "p50": 0.0750535,
    "p95": 0.08504655,
    "max": 0.088332,
    "baseline": 0.085243
  },
  "kpi::cost_share_production": {
    "n": 10,
    "mean": 0.3,
    "std": 0.0,
    "min": 0.3,
    "p05": 0.30000000000000004,
    "p50": 0.3,
    "p95": 0.3,
    "max": 0.3,
    "baseline": 0.3
  },
  "kpi::cost_share_purchase": {
    "n": 10,
    "mean": 0.251962,
    "std": 0.035652116430865646,
    "min": 0.200989,
    "p05": 0.20942875,
    "p50": 0.24466949999999998,
    "p95": 0.31662945,
    "max": 0.331299,
    "baseline": 0.195815
  },
  "kpi::cost_share_transport": {
    "n": 10,
    "mean": 0.0772818,
    "std": 0.013058624803554164,
    "min": 0.05735,
    "p05": 0.05869775000000001,
    "p50": 0.0790485,
    "p95": 0.0926838,
    "max": 0.09486,
    "baseline": 0.077968
  },
  "kpi::cost_share_warehouse_operating": {
    "n": 10,
    "mean": 0.1668403,
    "std": 0.020610190940648754,
    "min": 0.123229,
    "p05": 0.13085065,
    "p50": 0.1688695,
    "p95": 0.19135485,
    "max": 0.198747,
    "baseline": 0.191798
  },
  "kpi::ending_backlog": {
    "n": 10,
    "mean": 9604568.1046,
    "std": 4710794.509761295,
    "min": 2871825.7039,
    "p05": 3146623.224235,
    "p50": 10642494.1397,
    "p95": 15593006.135309998,
    "max": 16045876.8105,
    "baseline": 0.0
  },
  "kpi::ending_inventory": {
    "n": 10,
    "mean": 815014002.94035,
    "std": 236830733.39922777,
    "min": 514664207.282,
    "p05": 517088698.94549,
    "p50": 749357176.86075,
    "p95": 1211968798.26298,
    "max": 1292477857.2223,
    "baseline": 559962085.1798
  },
  "kpi::fill_rate": {
    "n": 10,
    "mean": 0.7142695,
    "std": 0.14150860029499973,
    "min": 0.49905,
    "p05": 0.5209074,
    "p50": 0.6741725,
    "p95": 0.9025037,
    "max": 0.908837,
    "baseline": 1.0
  },
  "kpi::measured_required_total": {
    "n": 10,
    "mean": 33611518.957270004,
    "std": 2467371.958163112,
    "min": 30243703.8728,
    "p05": 30810016.860905,
    "p50": 33168606.25285,
    "p95": 38095706.705275,
    "max": 38326261.6045,
    "baseline": 25762139.9999
  },
  "kpi::measurement_starting_backlog": {
    "n": 10,
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
    "n": 10,
    "mean": 753072424.8819,
    "std": 622311039.4897354,
    "min": 218581257.9451,
    "p05": 220212072.35144502,
    "p50": 274831281.00205,
    "p95": 1636650291.6512446,
    "max": 1731421303.829,
    "baseline": 758283589.0363
  },
  "kpi::total_cost": {
    "n": 10,
    "mean": 86101909.08186,
    "std": 14181962.991580565,
    "min": 61128581.3846,
    "p05": 63311086.828655005,
    "p50": 89282130.88455,
    "p95": 104487268.66183499,
    "max": 107753487.8442,
    "baseline": 68524646.9136
  },
  "kpi::total_demand": {
    "n": 10,
    "mean": 33611518.957270004,
    "std": 2467371.958163112,
    "min": 30243703.8728,
    "p05": 30810016.860905,
    "p50": 33168606.25285,
    "p95": 38095706.705275,
    "max": 38326261.6045,
    "baseline": 25762139.9999
  },
  "kpi::total_estimated_source_ordered_qty": {
    "n": 10,
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
    "n": 10,
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
    "n": 10,
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
    "n": 10,
    "mean": 68338188.0,
    "std": 0.0,
    "min": 68338188.0,
    "p05": 68338188.0,
    "p50": 68338188.0,
    "p95": 68338188.0,
    "max": 68338188.0,
    "baseline": 68338188.0
  },
  "kpi::total_explicit_initialization_stock_qty": {
    "n": 10,
    "mean": 0.0,
    "std": 0.0,
    "min": 0.0,
    "p05": 0.0,
    "p50": 0.0,
    "p95": 0.0,
    "max": 0.0,
    "baseline": 0.0
  },
  "kpi::total_external_procured_arrived_qty": {
    "n": 10,
    "mean": 1379353173.60683,
    "std": 902424932.9359293,
    "min": 453207356.4653,
    "p05": 524510499.1764951,
    "p50": 776449721.503,
    "p95": 2557997926.28921,
    "max": 2586763812.3608,
    "baseline": 856039017.9771
  },
  "kpi::total_external_procured_ordered_qty": {
    "n": 10,
    "mean": 1424274339.8806,
    "std": 954562294.7017266,
    "min": 453357576.2332,
    "p05": 524613948.81319004,
    "p50": 787854738.1794,
    "p95": 2760226777.787965,
    "max": 2879270811.5632,
    "baseline": 856231196.5145
  },
  "kpi::total_external_procured_qty": {
    "n": 10,
    "mean": 1424274339.8806,
    "std": 954562294.7017266,
    "min": 453357576.2332,
    "p05": 524613948.81319004,
    "p50": 787854738.1794,
    "p95": 2760226777.787965,
    "max": 2879270811.5632,
    "baseline": 856231196.5145
  },
  "kpi::total_external_procured_rejected_qty": {
    "n": 10,
    "mean": 88466122260.93066,
    "std": 48182248817.38199,
    "min": 19718401770.2511,
    "p05": 26067741831.650253,
    "p50": 101289501629.7475,
    "p95": 144839713903.10925,
    "max": 150954718521.4352,
    "baseline": 6543497354.9585
  },
  "kpi::total_external_procurement_cost": {
    "n": 10,
    "mean": 310631051.35996,
    "std": 140180123.89826185,
    "min": 167983166.5778,
    "p05": 170617964.02404502,
    "p50": 235377381.4505,
    "p95": 496055236.97927,
    "max": 496594809.7733,
    "baseline": 98015650.3365
  },
  "kpi::total_holding_cost": {
    "n": 10,
    "mean": 11128907.47911,
    "std": 2125069.880853854,
    "min": 7818177.4049,
    "p05": 8224791.585230001,
    "p50": 10960743.78565,
    "p95": 13934706.058135,
    "max": 14061298.8286,
    "baseline": 10222232.2415
  },
  "kpi::total_inventory_cost_legacy_raw_holding": {
    "n": 10,
    "mean": 31796878.51173,
    "std": 6071628.231065496,
    "min": 22337649.7283,
    "p05": 23499404.529185,
    "p50": 31316410.81605,
    "p95": 39813445.8805,
    "max": 40175139.5104,
    "baseline": 29206377.8329
  },
  "kpi::total_inventory_risk_cost": {
    "n": 10,
    "mean": 6359375.70234,
    "std": 1214325.6462164358,
    "min": 4467529.9457,
    "p05": 4699880.905850001,
    "p50": 6263282.1632,
    "p95": 7962689.17612,
    "max": 8035027.9021,
    "baseline": 5841275.5666
  },
  "kpi::total_logistics_cost": {
    "n": 10,
    "mean": 38455945.2551,
    "std": 6492031.444129394,
    "min": 27721775.9362,
    "p05": 28924842.69049,
    "p50": 36163505.795200005,
    "p95": 46681105.177845,
    "max": 47839958.6625,
    "baseline": 34549130.1228
  },
  "kpi::total_opening_open_order_qty": {
    "n": 10,
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
    "n": 10,
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
    "n": 10,
    "mean": 146977000.0,
    "std": 94829848.04324006,
    "min": 48204800.0,
    "p05": 53004320.0,
    "p50": 84108800.0,
    "p95": 287154290.0,
    "max": 294152600.0,
    "baseline": 106428400.0
  },
  "kpi::total_production_cost": {
    "n": 10,
    "mean": 25830572.72456,
    "std": 4254588.897473984,
    "min": 18338574.4154,
    "p05": 18993326.048585,
    "p50": 26784639.2654,
    "p95": 31346180.598539997,
    "max": 32326046.3532,
    "baseline": 20557394.0741
  },
  "kpi::total_purchase_cost": {
    "n": 10,
    "mean": 21815391.1022,
    "std": 5366598.654561628,
    "min": 15068231.033,
    "p05": 15392918.089535002,
    "p50": 19851198.43575,
    "p95": 29972646.916289993,
    "max": 31924144.8063,
    "baseline": 13418122.7167
  },
  "kpi::total_served": {
    "n": 10,
    "mean": 24006950.85268,
    "std": 4999759.296394971,
    "min": 15985039.429,
    "p05": 16984439.772985,
    "p50": 23652585.3969,
    "p95": 30602598.545679998,
    "max": 31415298.1486,
    "baseline": 25762139.9999
  },
  "kpi::total_shipped": {
    "n": 10,
    "mean": 689678961.51121,
    "std": 627125119.7930313,
    "min": 152299555.722,
    "p05": 153054986.62194002,
    "p50": 206608355.91689998,
    "p95": 1577088336.1916897,
    "max": 1670728248.4691,
    "baseline": 690749320.0363
  },
  "kpi::total_supplier_capacity_binding_qty": {
    "n": 10,
    "mean": 939344624.77684,
    "std": 1224887326.5155137,
    "min": 5481360.7112,
    "p05": 6825748.686725,
    "p50": 203083732.26035,
    "p95": 3162174779.822745,
    "max": 3376326950.5107,
    "baseline": 0.0
  },
  "kpi::total_transport_cost": {
    "n": 10,
    "mean": 6659066.74338,
    "std": 1642703.969755009,
    "min": 4734394.8242,
    "p05": 4827856.086905001,
    "p50": 6266774.6031,
    "p95": 9098514.86517,
    "max": 9140717.3733,
    "baseline": 5342752.2899
  },
  "kpi::total_unreliable_loss_qty": {
    "n": 10,
    "mean": 310027261.38304996,
    "std": 333903672.74397755,
    "min": 36059998.7449,
    "p05": 37257266.983285,
    "p50": 68465113.06735,
    "p95": 833766452.2104545,
    "max": 1013208924.1534,
    "baseline": 0.0
  },
  "kpi::total_warehouse_operating_cost": {
    "n": 10,
    "mean": 14308595.33027,
    "std": 2732232.703987925,
    "min": 10051942.3777,
    "p05": 10574732.038105,
    "p50": 14092384.8672,
    "p95": 17916050.646245,
    "max": 18078812.7797,
    "baseline": 13142870.0248
  },
  "kpi::warmup_backlog_cleared_qty": {
    "n": 10,
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
      "factor": "supplier_lead_node::SDC-VD1091642A",
      "correlation": 0.7242401928696495,
      "absolute_correlation": 0.7242401928696495
    },
    {
      "factor": "supplier_stock_node::SDC-VD0520132A",
      "correlation": -0.7171276251873615,
      "absolute_correlation": 0.7171276251873615
    },
    {
      "factor": "supplier_lead_node::SDC-VD0914360C",
      "correlation": 0.6975679000908634,
      "absolute_correlation": 0.6975679000908634
    },
    {
      "factor": "factor::capacity_scale",
      "correlation": 0.691462730485691,
      "absolute_correlation": 0.691462730485691
    },
    {
      "factor": "supplier_stock_node::SDC-VD0914320A",
      "correlation": 0.6812147844257671,
      "absolute_correlation": 0.6812147844257671
    },
    {
      "factor": "supplier_stock_node::SDC-VD0520115A",
      "correlation": 0.6566763862146402,
      "absolute_correlation": 0.6566763862146402
    },
    {
      "factor": "capacity_node::M-1430",
      "correlation": 0.6562228945068482,
      "absolute_correlation": 0.6562228945068482
    },
    {
      "factor": "supplier_reliability_node::SDC-VD0505677A",
      "correlation": 0.635367917213912,
      "absolute_correlation": 0.635367917213912
    },
    {
      "factor": "supplier_lead_node::SDC-VD0960508A",
      "correlation": 0.6310159082011015,
      "absolute_correlation": 0.6310159082011015
    },
    {
      "factor": "factor::holding_cost_scale",
      "correlation": 0.6215568931131609,
      "absolute_correlation": 0.6215568931131609
    },
    {
      "factor": "supplier_reliability_node::SDC-VD0520115A",
      "correlation": -0.5902821117826048,
      "absolute_correlation": 0.5902821117826048
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0518550B",
      "correlation": -0.5715485570890821,
      "absolute_correlation": 0.5715485570890821
    }
  ],
  "kpi::ending_backlog": [
    {
      "factor": "supplier_stock_node::SDC-VD0520132A",
      "correlation": 0.7108141927965201,
      "absolute_correlation": 0.7108141927965201
    },
    {
      "factor": "supplier_lead_node::SDC-VD1091642A",
      "correlation": -0.6860049141510065,
      "absolute_correlation": 0.6860049141510065
    },
    {
      "factor": "capacity_node::M-1430",
      "correlation": -0.6759716686493662,
      "absolute_correlation": 0.6759716686493662
    },
    {
      "factor": "supplier_lead_node::SDC-VD0960508A",
      "correlation": -0.6722964790643117,
      "absolute_correlation": 0.6722964790643117
    },
    {
      "factor": "supplier_stock_node::SDC-VD0914320A",
      "correlation": -0.6666100460775116,
      "absolute_correlation": 0.6666100460775116
    },
    {
      "factor": "factor::capacity_scale",
      "correlation": -0.6424470341364085,
      "absolute_correlation": 0.6424470341364085
    },
    {
      "factor": "supplier_reliability_node::SDC-VD0505677A",
      "correlation": -0.6333812468183136,
      "absolute_correlation": 0.6333812468183136
    },
    {
      "factor": "supplier_lead_node::SDC-VD0914360C",
      "correlation": -0.6243609838849592,
      "absolute_correlation": 0.6243609838849592
    },
    {
      "factor": "supplier_stock_node::SDC-VD0520115A",
      "correlation": -0.586111852579483,
      "absolute_correlation": 0.586111852579483
    },
    {
      "factor": "supplier_reliability_node::SDC-VD0520115A",
      "correlation": 0.5824641700323927,
      "absolute_correlation": 0.5824641700323927
    },
    {
      "factor": "supplier_lead_node::SDC-VD0993480A",
      "correlation": -0.5662164619482383,
      "absolute_correlation": 0.5662164619482383
    },
    {
      "factor": "factor::holding_cost_scale",
      "correlation": -0.5588332415672261,
      "absolute_correlation": 0.5588332415672261
    }
  ],
  "kpi::total_cost": [
    {
      "factor": "supplier_reliability_node::SDC-VD0505677A",
      "correlation": 0.8276802060247284,
      "absolute_correlation": 0.8276802060247284
    },
    {
      "factor": "factor::capacity_scale",
      "correlation": 0.8021570219319404,
      "absolute_correlation": 0.8021570219319404
    },
    {
      "factor": "supplier_lead_node::SDC-VD0914360C",
      "correlation": 0.7951868562369189,
      "absolute_correlation": 0.7951868562369189
    },
    {
      "factor": "factor::holding_cost_scale",
      "correlation": 0.7334102093386284,
      "absolute_correlation": 0.7334102093386284
    },
    {
      "factor": "supplier_lead_node::SDC-VD1091642A",
      "correlation": 0.7281873878323898,
      "absolute_correlation": 0.7281873878323898
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0989480A",
      "correlation": -0.6997282623459888,
      "absolute_correlation": 0.6997282623459888
    },
    {
      "factor": "supplier_capacity_node::SDC-VD1095770A",
      "correlation": -0.6909357795841538,
      "absolute_correlation": 0.6909357795841538
    },
    {
      "factor": "capacity_node::M-1430",
      "correlation": 0.6904981765934277,
      "absolute_correlation": 0.6904981765934277
    },
    {
      "factor": "supplier_stock_node::SDC-VD0520115A",
      "correlation": 0.6605108350494433,
      "absolute_correlation": 0.6605108350494433
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0520132A",
      "correlation": 0.6582298833380598,
      "absolute_correlation": 0.6582298833380598
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0508918A",
      "correlation": -0.610250534592542,
      "absolute_correlation": 0.610250534592542
    },
    {
      "factor": "supplier_reliability_node::SDC-VD0514881A",
      "correlation": 0.6041126464374422,
      "absolute_correlation": 0.6041126464374422
    }
  ],
  "kpi::total_produced": [
    {
      "factor": "supplier_reliability_node::SDC-VD0505677A",
      "correlation": 0.7978458705954325,
      "absolute_correlation": 0.7978458705954325
    },
    {
      "factor": "capacity_node::M-1430",
      "correlation": 0.7818953618604643,
      "absolute_correlation": 0.7818953618604643
    },
    {
      "factor": "supplier_stock_node::SDC-VD0520132A",
      "correlation": -0.7778579254440978,
      "absolute_correlation": 0.7778579254440978
    },
    {
      "factor": "factor::capacity_scale",
      "correlation": 0.7019935640182321,
      "absolute_correlation": 0.7019935640182321
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0901566A",
      "correlation": -0.6187940739111699,
      "absolute_correlation": 0.6187940739111699
    },
    {
      "factor": "supplier_stock_node::SDC-VD1095770A",
      "correlation": -0.6144770029746491,
      "absolute_correlation": 0.6144770029746491
    },
    {
      "factor": "demand_item::item:268967",
      "correlation": 0.6125637986357075,
      "absolute_correlation": 0.6125637986357075
    },
    {
      "factor": "supplier_stock_node::SDC-VD1096202A",
      "correlation": -0.607798506716608,
      "absolute_correlation": 0.607798506716608
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0518550B",
      "correlation": -0.5926598909315877,
      "absolute_correlation": 0.5926598909315877
    },
    {
      "factor": "supplier_stock_node::SDC-VD1091642A",
      "correlation": 0.5867077541112169,
      "absolute_correlation": 0.5867077541112169
    },
    {
      "factor": "supplier_capacity_node::SDC-VD0949099A",
      "correlation": 0.5739671258425689,
      "absolute_correlation": 0.5739671258425689
    },
    {
      "factor": "supplier_stock_node::SDC-VD0505677A",
      "correlation": 0.5730508893825075,
      "absolute_correlation": 0.5730508893825075
    }
  ]
}

## Top Runs
- Best fill rate: [{"run_id": "run_0003", "kpi::fill_rate": 0.908837}, {"run_id": "run_0008", "kpi::fill_rate": 0.894763}, {"run_id": "run_0007", "kpi::fill_rate": 0.861928}, {"run_id": "run_0009", "kpi::fill_rate": 0.830787}, {"run_id": "run_0002", "kpi::fill_rate": 0.683518}, {"run_id": "run_0010", "kpi::fill_rate": 0.664827}, {"run_id": "run_0004", "kpi::fill_rate": 0.650745}, {"run_id": "run_0006", "kpi::fill_rate": 0.600618}, {"run_id": "run_0001", "kpi::fill_rate": 0.547622}, {"run_id": "run_0005", "kpi::fill_rate": 0.49905}]
- Worst fill rate: [{"run_id": "run_0005", "kpi::fill_rate": 0.49905}, {"run_id": "run_0001", "kpi::fill_rate": 0.547622}, {"run_id": "run_0006", "kpi::fill_rate": 0.600618}, {"run_id": "run_0004", "kpi::fill_rate": 0.650745}, {"run_id": "run_0010", "kpi::fill_rate": 0.664827}, {"run_id": "run_0002", "kpi::fill_rate": 0.683518}, {"run_id": "run_0009", "kpi::fill_rate": 0.830787}, {"run_id": "run_0007", "kpi::fill_rate": 0.861928}, {"run_id": "run_0008", "kpi::fill_rate": 0.894763}, {"run_id": "run_0003", "kpi::fill_rate": 0.908837}]
- Lowest total cost: [{"run_id": "run_0002", "kpi::total_cost": 61128581.3846}, {"run_id": "run_0001", "kpi::total_cost": 65978593.4825}, {"run_id": "run_0006", "kpi::total_cost": 78308230.1068}, {"run_id": "run_0005", "kpi::total_cost": 78455078.3115}, {"run_id": "run_0004", "kpi::total_cost": 89143867.3706}, {"run_id": "run_0003", "kpi::total_cost": 89420394.3985}, {"run_id": "run_0010", "kpi::total_cost": 93975179.5658}, {"run_id": "run_0009", "kpi::total_cost": 96360455.3596}, {"run_id": "run_0007", "kpi::total_cost": 100495222.9945}, {"run_id": "run_0008", "kpi::total_cost": 107753487.8442}]
- Highest total cost: [{"run_id": "run_0008", "kpi::total_cost": 107753487.8442}, {"run_id": "run_0007", "kpi::total_cost": 100495222.9945}, {"run_id": "run_0009", "kpi::total_cost": 96360455.3596}, {"run_id": "run_0010", "kpi::total_cost": 93975179.5658}, {"run_id": "run_0003", "kpi::total_cost": 89420394.3985}, {"run_id": "run_0004", "kpi::total_cost": 89143867.3706}, {"run_id": "run_0005", "kpi::total_cost": 78455078.3115}, {"run_id": "run_0006", "kpi::total_cost": 78308230.1068}, {"run_id": "run_0001", "kpi::total_cost": 65978593.4825}, {"run_id": "run_0002", "kpi::total_cost": 61128581.3846}]

## Files
- montecarlo_samples.csv
- montecarlo_summary.json
- montecarlo_trajectories.json (si --save-trajectories)
- montecarlo_report.md
