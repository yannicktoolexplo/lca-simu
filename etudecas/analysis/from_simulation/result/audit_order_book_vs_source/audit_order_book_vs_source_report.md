# Audit carnet d'ordres vs sources

## Synthese

- Lignes brutes `Extract_En_cours.xlsx`: 104.
- Lignes resolues dans `supply_graph_poc.json`: 88.
- Ordres achat source: 82 ; ordres production source: 22.
- Ordres achat sans voie fournisseur-item FIA exacte: 30 lignes, valeur estimee 292,799 EUR.
- Lignes source absentes du graphe ouvert: 16 lignes.
- Lignes achat non multiples de la quantite standard FIA: 17 lignes.

## Lecture metier courte

- Le carnet d'ordres reel est bien injecte dans le run 5 ans complet, mais certaines commandes fermes n'ont pas de voie fournisseur-item valide.
- Quand une ligne achat n'a pas de voie FIA exacte, le moteur peut quand meme injecter la reception ferme; la ligne perd alors sa reference logistique/prix/lead fiable.
- Les ordres de production ouverts (`O.Proc`) n'ont pas d'edge, ce qui est normal; ils representent une production interne deja planifiee.
- Les ecarts critiques sont donc les achats ouverts sans voie FIA, pas les ordres de production sans edge.

## Runs compares

| Run | Ordres MRP | Opening achats | Opening production | Types |
|---|---:|---:|---:|---|
| 5y_full | 33292 | 66 | 22 | external_procurement:170, external_procurement_proactive:2878, lane_release:30092, lane_release_min_annual_lot:64, opening_production_order:22, opening_purchase_order:66 |
| 268091_365d_all_open_orders | 5167 | 66 | 22 | external_procurement_proactive:2515, lane_release:2564, opening_production_order:22, opening_purchase_order:66 |
| 268091_365d_strict_fia_orders | 5252 | 54 | 22 | external_procurement_proactive:2581, lane_release:2595, opening_production_order:22, opening_purchase_order:54 |

## Plus gros ordres ouverts source valorises

| Row | Type | Produit scope | Item | Destination | Fournisseur | Quantite | UOM | Valeur EUR | Flags |
|---:|---|---|---|---|---|---:|---|---:|---|
| 22 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0960508A | 100,000.0 | KG | 1,210,000 | duplicate_same_key |
| 23 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0960508A | 100,000.0 | KG | 1,210,000 | duplicate_same_key |
| 24 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0960508A | 100,000.0 | KG | 1,210,000 | duplicate_same_key |
| 26 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0960508A | 100,000.0 | KG | 1,210,000 | duplicate_same_key |
| 27 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0960508A | 100,000.0 | KG | 1,210,000 | duplicate_same_key |
| 28 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0960508A | 100,000.0 | KG | 1,210,000 | duplicate_same_key |
| 29 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0960508A | 100,000.0 | KG | 1,210,000 | duplicate_same_key |
| 30 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0960508A | 100,000.0 | KG | 1,210,000 | duplicate_same_key |
| 34 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0975221A | 40,000.0 | KG | 600,000 | duplicate_same_key |
| 36 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0975221A | 40,000.0 | KG | 600,000 | duplicate_same_key |
| 31 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0972460A | 40,000.0 | KG | 486,000 | duplicate_same_key |
| 33 | purchase_open_order | 773474 | item:021081 | SDC-1450 | SDC-VD0972460A | 40,000.0 | KG | 486,000 | duplicate_same_key |

## Achats ouverts sans voie FIA exacte

| Row | Produit scope | Item | Destination | Fournisseur carnet | Voie utilisee fallback | Quantite | UOM | Valeur EUR |
|---:|---|---|---|---|---|---:|---|---:|
| 58 | 268091 | item:049371 | M-1810 | SDC-VD0518550B | SDC-VD0520132A | 1,800,000.0 | G | 26,370 |
| 59 | 268091 | item:049371 | M-1810 | SDC-VD0518550B | SDC-VD0520132A | 1,800,000.0 | G | 26,370 |
| 60 | 268091 | item:049371 | M-1810 | SDC-VD0518550B | SDC-VD0520132A | 1,800,000.0 | G | 26,370 |
| 61 | 268091 | item:049371 | M-1810 | SDC-VD0518550B | SDC-VD0520132A | 1,800,000.0 | G | 26,370 |
| 62 | 268091 | item:049371 | M-1810 | SDC-VD0518550B | SDC-VD0520132A | 1,800,000.0 | G | 26,370 |
| 63 | 268091 | item:049371 | M-1810 | SDC-VD0518550B | SDC-VD0520132A | 1,800,000.0 | G | 26,370 |
| 64 | 268091 | item:049371 | M-1810 | SDC-VD0518550B | SDC-VD0520132A | 1,800,000.0 | G | 26,370 |
| 65 | 268091 | item:049371 | M-1810 | SDC-VD0518550B | SDC-VD0520132A | 1,800,000.0 | G | 26,370 |
| 66 | 268091 | item:049371 | M-1810 | SDC-VD0518550B | SDC-VD0520132A | 1,800,000.0 | G | 26,370 |
| 67 | 268091 | item:049371 | M-1810 | SDC-VD0518550B | SDC-VD0520132A | 1,800,000.0 | G | 26,370 |
| 68 | 268091 | item:049371 | M-1810 | SDC-VD0518550B | SDC-VD0520132A | 1,800,000.0 | G | 26,370 |
| 104 | 268967 | item:734545 | M-1430 | SDC-VD0525906A | SDC-VD1095770A | 6,400.0 | UN | 2,729 |

## Top anomalies

| Anomalie | Occurrences |
|---|---:|
| duplicate_same_key | 61 |
| run_qty_not_multiple_of_standard_order | 40 |
| supplier_item_lane_absent | 30 |
| run_opening_purchase_supplier_lane_absent | 30 |
| no_dest_item_lane | 18 |
| not_multiple_of_standard_order_qty | 17 |
| unmapped_division | 16 |
| not_in_graph_open_orders | 16 |
| run_opening_purchase_empty_edge | 3 |
| run_opening_purchase_zero_reference_lead | 3 |

## Fichiers generes

- `source_open_orders_audit.csv` : chaque ligne source enrichie avec voie FIA, lot standard, valeur estimee et flags.
- `source_open_orders_summary.csv` : aggregation source par produit/site/item/fournisseur.
- `run_order_book_audit.csv` : ordres MRP simules et flags de coherence.
- `run_order_book_summary.csv` : aggregation des ordres simules.
- `order_book_anomalies.csv` : anomalies source et run.