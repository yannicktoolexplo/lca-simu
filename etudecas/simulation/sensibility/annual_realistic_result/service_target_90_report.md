# Target 90% Service Rate - Annual What-If Tests

Date: 2026-03-10 (UTC)

Baseline annual run:
- Fill rate: `0.614479`
- Ending backlog: `6708.0716`
- Total cost: `15433873.2401`

Tested annual what-if scenarios:

| Scenario | Main levers | Fill rate | Ending backlog | Total cost |
|---|---|---:|---:|---:|
| `cap_factories_20` | `M-1430` `+20%`, `M-1810` `+20%` | `0.619659` | `6617.9369` | `15621209.1462` |
| `cap_factories_30` | `M-1430` `+30%`, `M-1810` `+30%` | `0.622264` | `6572.5978` | `15734012.7164` |
| `all_ops_moderate` | factory cap `+25%`, supplier/prod stock `+20%`, safety stock `+30%`, key suppliers strengthened | `0.671868` | `5709.4882` | `15696779.7518` |
| `all_ops_strong` | factory cap `+35%`, stock `+35%`, faster external procurement, key suppliers reinforced | `0.721657` | `4843.1755` | `15781410.4282` |
| `extreme_supply_push` | factory cap `+80%`, supplier/prod stock `+80%`, global lead time `-40%`, safety stock `+80%`, stronger/faster external procurement, key suppliers reinforced | `0.837606` | `2825.6598` | `9947062.9900` |
| `heroic_supply` | factory cap `x2`, supplier/prod stock `x2`, global lead time `-50%`, safety stock `x2`, external procurement faster and larger, key suppliers strongly reinforced | `0.917513` | `1435.2727` | `8537543.9215` |
| `superhero_supply` | even more aggressive than `heroic_supply` | `0.994432` | `96.8750` | `7226329.6743` |

Demand shaping sensitivity on top of `extreme_supply_push`:

| Demand scale on `268091` and `268967` | Fill rate | Ending backlog |
|---|---:|---:|
| `0.88` | `0.883040` | `1790.8945` |
| `0.85` | `0.894653` | `1558.0817` |
| `0.82` | `0.912694` | `1245.6886` |
| `0.80` | `0.921962` | `1086.2823` |
| `0.78` | `0.932819` | `911.7746` |

Main takeaway:
- `90%` is **not reachable** with mild or even strong operational tweaks alone.
- With unchanged demand, the annual model only crosses `90%` under a very aggressive multi-lever supply upgrade (`heroic_supply`).
- If demand can be smoothed/reduced, a strong supply upgrade plus about `-18%` demand on both finished goods crosses `90%`.
