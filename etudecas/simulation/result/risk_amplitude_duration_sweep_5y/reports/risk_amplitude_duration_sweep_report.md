# Risk amplitude / duration sweep

- Cases run: `41`
- Horizon: `1825` days
- Input: `etudecas\simulation_prep\result\reference_baseline\_mrp_bom_tests\bom_weekly_mps_lotified_no_static_fallback_physical_floor.json`
- Baseline cost: `68.74M`
- Baseline input delay volume: `6.25M`

## Top perturbing cases

| Rank | Case | Family | Fill rate | Backlog max hors amorcage | Delay volume delta | Cost delta | Loss delta | Supplier appro cost delta | Score |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `pf268967_combined_extreme_180d_no_external` | combined_no_external | 0.4850 | 13.3M | 253.0M | -23.5M | 102.9M | -56.9M | 585.4M |
| 2 | `pf268967_delay_plus_90_60d` | lead_time_extra_days | 1.0000 | 0.0 | 542.2M | 29.7M | 0.0 | -1.6M | 117.2M |
| 3 | `pf268967_delay_plus_90_180d` | lead_time_extra_days | 1.0000 | 0.0 | 542.2M | 29.6M | 0.0 | -1.6M | 117.2M |
| 4 | `pf268967_delay_plus_45_60d` | lead_time_extra_days | 1.0000 | 0.0 | 541.9M | 29.3M | 0.0 | -2.7M | 116.9M |
| 5 | `pf268967_delay_plus_45_180d` | lead_time_extra_days | 1.0000 | 0.0 | 541.9M | 29.3M | 0.0 | -2.7M | 116.9M |
| 6 | `pf268967_delay_plus_14_60d` | lead_time_extra_days | 1.0000 | 0.0 | 538.7M | 27.4M | 0.0 | -6.7M | 114.6M |
| 7 | `pf268967_delay_plus_14_180d` | lead_time_extra_days | 1.0000 | 0.0 | 538.7M | 27.4M | 0.0 | -6.7M | 114.6M |
| 8 | `pf268967_combined_severe_120d` | combined | 1.0000 | 0.0 | 230.8M | 11.1M | 167.9M | 14.1M | 63.0M |
| 9 | `pf268967_quality_yield_50_180d` | quality_yield | 1.0000 | 0.0 | 107.8k | -9.1M | 236.2M | 16.6M | 15.1M |
| 10 | `pf268967_quality_yield_50_60d` | quality_yield | 1.0000 | 0.0 | 107.8k | -7.8M | 235.2M | 17.1M | 15.0M |
| 11 | `pf268967_quality_yield_75_180d` | quality_yield | 1.0000 | 0.0 | 107.8k | -6.0M | 114.9M | -608.2k | 7.0M |
| 12 | `pf268967_quality_yield_75_60d` | quality_yield | 1.0000 | 0.0 | 107.8k | -6.2M | 114.8M | 193.4k | 7.0M |

## Best case by family

| Family | Worst case | Main signal | Fill rate | Delay volume delta | Cost delta | Loss delta |
|---|---|---|---:|---:|---:|---:|
| availability | `pf268967_availability_10_30d` | reports +2.6M | 1.0000 | 2.6M | -5.5M | 0.0 |
| capacity | `pf268967_capacity_70_30d` | pas de degradation nette vs nominal | 1.0000 | 0.0 | -177.0k | 0.0 |
| capacity_268091 | `pf268091_key_capacity_40_90d` | pas de degradation nette vs nominal | 1.0000 | 0.0 | -177.0k | 0.0 |
| combined | `pf268967_combined_severe_120d` | reports +230.8M; cout +11.1M; pertes +167.9M | 1.0000 | 230.8M | 11.1M | 167.9M |
| combined_no_external | `pf268967_combined_extreme_180d_no_external` | backlog 13.3M; reports +253.0M; pertes +102.9M | 0.4850 | 253.0M | -23.5M | 102.9M |
| lead_time_extra_days | `pf268967_delay_plus_90_60d` | reports +542.2M; cout +29.7M | 1.0000 | 542.2M | 29.7M | 0.0 |
| quality_yield | `pf268967_quality_yield_50_180d` | reports +107.8k; pertes +236.2M | 1.0000 | 107.8k | -9.1M | 236.2M |
| state-dependent | `state_only` | pas de degradation nette vs nominal | 1.0000 | 0.0 | -177.0k | 0.0 |
| stock_writeoff | `pf268967_stock_writeoff_25_j0` | pas de degradation nette vs nominal | 1.0000 | 0.0 | -177.0k | 0.0 |
| transport_dc_customer | `dc_customer_pf_delay_plus_45_90d` | reports +215.6k; cout +642.2k | 1.0000 | 215.6k | 642.2k | 0.0 |
| transport_factory_dc | `factory_dc_pf_delay_plus_45_90d` | reports +215.6k | 1.0000 | 215.6k | -385.7k | 0.0 |
| transport_network | `network_transport_block_120d` | reports +215.6k; cout +213.3k | 1.0000 | 215.6k | 213.3k | 0.0 |

## Lecture metier

- Service client vraiment degrade uniquement dans le cas extreme sans appro fournisseur: fill rate 0.4850, backlog max 13.3M, 253.0M de volume reporte et 102.9M de pertes fournisseur.
- Risque le plus perturbateur hors rupture service: allongement des delais fournisseurs. Meme +14 jours cree deja 538.7M de volume reporte; +90 jours monte a 542.2M et environ 29.7M de cout additionnel.
- Les cascades combinees sont plus realistes que les chocs unitaires: le scenario severe garde le service a 100%, mais cree 230.8M de reports, 167.9M de pertes et 14.1M de cout d'appro fournisseur supplementaire.
- Le risque qualite/rendement est surtout economique: rendement x0.5 ne casse pas le service, mais genere 236.2M de pertes et davantage d'appro fournisseur.
- L'indisponibilite fournisseur doit etre tres forte pour se voir nettement: disponibilite x0.1 pendant 90 jours ajoute 2.7M de reports, sans backlog client.
- Les baisses de capacite et write-off de stock testes seuls sont absorbes: capacite x0.2 et write-off 80% ne degradent pas le service ni les reports versus nominal. Cela indique un effet tampon important des stocks, pipelines et approvisionnements fournisseur.
- Les retards transport aval sont visibles mais contenus: DC -> client +45 jours cree 215.6k de reports et 642.2k de cout, sans backlog durable.
- Le state-dependent seul declenche des evenements locaux, mais reste absorbe dans cette configuration. Il est utile comme signal dynamique, pas suffisant seul pour un stress severe.

## Interpretation

- The score is a screening score, not a probability. It combines service degradation, backlog, production delay volume, cost delta, supplier loss, supplier replenishment cost, and zero-stock stress.
- If fill rate stays at 1.0, the risk is absorbed by stock, pipeline, replanning, or supplier replenishment. Those cases are still perturbing if they increase delay volume, losses, cost, or stock stress.
- Full CSV: `etudecas\simulation\result\risk_amplitude_duration_sweep_5y\risk_amplitude_duration_sweep_summary.csv`
