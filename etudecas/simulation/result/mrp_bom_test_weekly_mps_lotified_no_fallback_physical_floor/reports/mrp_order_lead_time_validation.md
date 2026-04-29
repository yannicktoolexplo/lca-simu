# MRP order lead-time validation

## Definitions

- ordre_passe = order_date_IMT.
- envoi = release_day.
- delai_previsionnel_mrp = lead_reference_days, i.e. supplier reference lead time from FIA/data.
- lead_cover_days = conservative MRP cover used internally for planning buffers; it is not the displayed forecast delay.
- arrivee_previsionnelle = envoi + delai_previsionnel_mrp.
- arrivee_effective = actual_receipt_day.
- ecart = arrivee_effective - arrivee_previsionnelle. Negative means early.
- The scenario uses stochastic lead times with industrial distribution mode, centered on the forecast lead time.

## Global received lane_release orders

- lane_release received orders: 95 433
- received quantity: 767 295 808
- actual delay from envoi: median 120.0 j, mean 103.8 j, p95 126.0 j
- forecast/reference delay: median 120.0 j, mean 103.3 j, p95 120.0 j
- internal MRP cover delay: median 144.0 j, mean 124.1 j, p95 144.0 j
- effective - forecast arrival: median 0.0 j, mean 0.4 j, p95 6.0 j, max 19.0 j
- exact forecast day: 71.66% orders, 73.51% quantity
- early arrivals: 14.78% orders, 4.13% quantity
- late arrivals: 13.57% orders, 22.36% quantity
- <=J prev.: 86.43% orders, 77.64% quantity
- <=J+2: 89.24% orders, 95.12% quantity
- <=J+5: 93.68% orders, 99.50% quantity
- <=J+10: 97.62% orders, 99.93% quantity
- >J+10: 2.38% orders, 0.07% quantity

### Top lanes by received quantity

| Lane | Ordres | Quantite | <=J+2 qte | <=J+5 qte | >J+10 qte | Ecart moy | P95 ecart | Delai reel moy | Delai prev moy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SDC-VD0914690A -> M-1430 / 042342 | 19 | 570 000 000 | 94.7% | 100.0% | 0.0% | 0.4 j | 1.2 j | 21.4 j | 21.0 j |
| SDC-1450 -> M-1430 / 773474 | 400 | 72 854 500 | 100.0% | 100.0% | 0.0% | -0.0 j | 1.0 j | 10.0 j | 10.0 j |
| SDC-VD0914360C -> M-1810 / 338929 | 3940 | 21 540 000 | 92.9% | 95.5% | 0.0% | 0.4 j | 5.0 j | 42.4 j | 42.0 j |
| SDC-VD0901566A -> M-1810 / 338928 | 770 | 19 250 000 | 85.8% | 90.9% | 1.9% | 0.6 j | 8.0 j | 70.6 j | 70.0 j |
| M-1810 -> DC-1920 / 268091 | 1218 | 18 063 518 | 97.5% | 100.0% | 0.0% | 0.1 j | 2.0 j | 2.1 j | 2.0 j |
| DC-1920 -> C-XXXXX / 268091 | 1515 | 18 059 189 | 96.9% | 100.0% | 0.0% | 0.1 j | 2.0 j | 2.1 j | 2.0 j |
| SDC-VD0993480A -> M-1430 / 344135 | 82 | 9 840 000 | 98.8% | 98.8% | 0.0% | 0.0 j | 1.0 j | 35.0 j | 35.0 j |
| SDC-1450 -> M-1810 / 693055 | 8316 | 8 104 558 | 92.5% | 94.9% | 0.6% | 0.1 j | 5.0 j | 70.1 j | 70.0 j |
| M-1430 -> DC-1920 / 268967 | 555 | 7 943 770 | 96.5% | 100.0% | 0.0% | 0.1 j | 2.0 j | 2.1 j | 2.0 j |
| DC-1920 -> C-XXXXX / 268967 | 892 | 7 931 908 | 96.8% | 100.0% | 0.0% | 0.1 j | 2.0 j | 2.1 j | 2.0 j |
| SDC-VD0525412A -> M-1430 / 333362 | 1365 | 7 350 000 | 93.2% | 94.6% | 0.0% | 0.4 j | 8.0 j | 60.4 j | 60.0 j |
| SDC-VD0508918A -> M-1430 / 730384 | 5 | 1 850 000 | 100.0% | 100.0% | 0.0% | -0.6 j | 0.0 j | 55.4 j | 56.0 j |
| SDC-VD0960508A -> SDC-1450 / 021081 | 25508 | 1 386 081 | 87.5% | 93.5% | 2.4% | 0.4 j | 6.0 j | 120.4 j | 120.0 j |
| SDC-VD0972460A -> SDC-1450 / 021081 | 48672 | 1 374 242 | 87.5% | 92.2% | 3.8% | 0.5 j | 7.0 j | 120.5 j | 120.0 j |
| SDC-VD0989480A -> M-1810 / 426331 | 13 | 249 600 | 100.0% | 100.0% | 0.0% | -0.2 j | 0.4 j | 27.8 j | 28.0 j |
| SDC-VD0910216A -> M-1810 / 002612 | 7 | 157 500 | 100.0% | 100.0% | 0.0% | 0.0 j | 0.0 j | 35.0 j | 35.0 j |
| SDC-VD0910216A -> M-1810 / 001893 | 6 | 143 520 | 100.0% | 100.0% | 0.0% | 0.0 j | 0.0 j | 28.0 j | 28.0 j |
| SDC-VD0990780A -> M-1810 / 002612 | 6 | 142 500 | 83.3% | 100.0% | 0.0% | 0.2 j | 2.8 j | 35.2 j | 35.0 j |
| SDC-VD0518684A -> M-1810 / 001893 | 6 | 136 800 | 83.3% | 100.0% | 0.0% | 0.5 j | 2.2 j | 56.5 j | 56.0 j |
| SDC-VD1091642A -> M-1810 / 002612 | 6 | 135 000 | 100.0% | 100.0% | 0.0% | 0.2 j | 0.8 j | 35.2 j | 35.0 j |

Full lane table: `mrp_order_lead_time_validation_by_lane.csv`
