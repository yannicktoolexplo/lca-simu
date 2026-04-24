# Validation supply - reference vs simulation

## Perimetre
- Source graphe: `etudecas\simulation_prep\result\reference_baseline\supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y_open_orders_jan_snapshot.json`
- Resultat simule: `etudecas\simulation\result\reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y_open_orders_jan_snapshot_supplier_hard_lot_test`
- Lignes MRP: 241 493
- Lignes stock matieres: 43 800
- Lignes produits: 5 475
- Lignes demande: 3 650

## Verdict executif
- Statut: **a corriger avant validation industrielle** (2 bloquants detectes).
- OK: 7 | Warnings: 25 | Infos: 7 | Blockers: 2
- Service demande finale cumule: fill rate `1.0`, backlog final `0`.
- Open orders initiaux reconstruits: `25 012 341` ; external procurement commande: `404 220 650`.

## Couverture
| Controle | Reference | Couvert | Ecart |
|---|---:|---:|---:|
| Inputs process source | 24 | 24 | 0 |
| Outputs process source | 3 | 3 | 0 |
| Couples matieres simules | 24 | 24 | 0 |
| Couples produits simules | 3 | 3 | 0 |
| Couples demande finale | 2 | 2 | 0 |
| Lanes source edge x item | 39 | 39 | 0 |


## Service client jour par jour
| Noeud | Item | Demande totale | Servi total | Fill rate | Jours en retard | Backlog max |
|---|---:|---:|---:|---:|---:|---:|
| C-XXXXX | 268091 | 17 882 210 | 17 882 210 | 1.000000 | 1 | 950 |
| C-XXXXX | 268967 | 7 879 930 | 7 879 930 | 1.000000 | 8 | 32 668.4 |

Lecture: le cumul est servi a 100 %, mais ces jours en retard restent bloquants si l exigence est un service client sans backlog journalier.

## Delais de securite
- Arrivees MRP controlees: 26 ; conformes: 26 ; non conformes: 0.
- Couverture physique souple: 8 couples descendent sous la cible souple au moins une fois ; couverture complete delai: 10 couples descendent sous l equivalent complet.
- Interpretation: le delai de securite est respecte en planification d arrivee. Le maintien physique permanent reste une regle plus stricte et genere des warnings, pas des bloquants, sauf decision industrielle contraire.

## Lots et quantites
- Ordres lane_release avec lot > 1 non multiples du lot: 0.
- Lanes avec lot standard = 1 a clarifier: 4.
- Lanes avec lot >= 1 000 000 a valider: 1.
- Concentrations >10 lots le meme jour IMT: 1.
- Le cas `708073` est traite avec override `5 000 KG` au lieu de `5 000 000` source, interprete comme grammes.

## Stocks et service
- Stocks negatifs detectes: 0.
- Couples matiere avec stock touchant zero: 0.
- Si le zero physique est interdit, ces warnings doivent devenir des contraintes de plancher; sinon ils restent des alertes de pilotage.

## Points principaux a valider industriellement
- **lead_time / DC-1920->C-XXXXX/268091**: Lead time simule eloigne de la reference moyenne. (ref=2, avg=2.47, min=1, max=7, n=1186)
- **lead_time / M-1430->DC-1920/268967**: Lead time simule eloigne de la reference moyenne. (ref=2.5, avg=2.93, min=1, max=9, n=737)
- **lead_time / M-1810->DC-1920/268091**: Lead time simule eloigne de la reference moyenne. (ref=2.5, avg=2.98, min=1, max=8, n=1261)
- **lead_time / SDC-VD0951020A->M-1810/007923**: Lead time simule eloigne de la reference moyenne. (ref=3, avg=3.45, min=1, max=11, n=1306)
- **lead_time / SDC-VD0956464A->M-1810/007923**: Lead time simule eloigne de la reference moyenne. (ref=3, avg=3.46, min=1, max=10, n=1082)
- **lead_time / SDC-VD1096202A->M-1810/039668**: Lead time simule eloigne de la reference moyenne. (ref=35, avg=64, min=64, max=64, n=1)
- **lot_size / SDC-1450->M-1430/773474**: Taille de lot standard = 1: mathematiquement respectee mais non interpretable comme lot industriel. (orders=1254, total_qty=68 096 657)
- **lot_size / SDC-1450->M-1810/693055**: Taille de lot standard = 1: mathematiquement respectee mais non interpretable comme lot industriel. (orders=128138, total_qty=10 495 140)
- **lot_size / SDC-VD0914690A->M-1430/042342**: Taille de lot tres elevee: elle structure fortement les stocks et pics. (std=30 000 000, max_release=30 000 000)
- **lot_size / SDC-VD0960508A->SDC-1450/021081**: Taille de lot standard = 1: mathematiquement respectee mais non interpretable comme lot industriel. (orders=50430, total_qty=459 316.0)
- **lot_size / SDC-VD0972460A->SDC-1450/021081**: Taille de lot standard = 1: mathematiquement respectee mais non interpretable comme lot industriel. (orders=40354, total_qty=187 276.0)
- **order_smoothing / SDC-VD0914360C->M-1810/338929**: Plus de 10 lots commandes le meme jour IMT sur une lane. (max_lots_same_day=14, std=5 000.0, max_release=70 000.0)
- **physical_safety_cover / input_material:M-1430/333362**: Stock minimum descend sous la cible souple de couverture securite. (min=194 450.0, soft_target=1 155 000, full_equiv=1 540 000, safety_days=10)
- **physical_safety_cover / input_material:M-1430/344135**: Stock minimum descend sous la cible souple de couverture securite. (min=132 200.0, soft_target=1 155 000, full_equiv=1 540 000, safety_days=10)
- **physical_safety_cover / input_material:M-1430/734545**: Stock minimum descend sous la cible souple de couverture securite. (min=7 078.6, soft_target=9 240.0, full_equiv=12 320.0, safety_days=10)

## Findings detailles
| Severite | Domaine | Objet | Message | Preuve | Action |
|---|---|---|---|---|---|
| BLOCKER | service | C-XXXXX/268091 | Demande finale non servie integralement. | fill=1.000000, backlog_max=0.0, short_days=1 | Analyser capacite/approvisionnement. |
| BLOCKER | service | C-XXXXX/268967 | Demande finale non servie integralement. | fill=1.000000, backlog_max=0.0, short_days=8 | Analyser capacite/approvisionnement. |
| WARNING | lead_time | DC-1920->C-XXXXX/268091 | Lead time simule eloigne de la reference moyenne. | ref=2, avg=2.47, min=1, max=7, n=1186 | Verifier stochasticite, lead_cover et reference FIA. |
| WARNING | lead_time | M-1430->DC-1920/268967 | Lead time simule eloigne de la reference moyenne. | ref=2.5, avg=2.93, min=1, max=9, n=737 | Verifier stochasticite, lead_cover et reference FIA. |
| WARNING | lead_time | M-1810->DC-1920/268091 | Lead time simule eloigne de la reference moyenne. | ref=2.5, avg=2.98, min=1, max=8, n=1261 | Verifier stochasticite, lead_cover et reference FIA. |
| WARNING | lead_time | SDC-VD0951020A->M-1810/007923 | Lead time simule eloigne de la reference moyenne. | ref=3, avg=3.45, min=1, max=11, n=1306 | Verifier stochasticite, lead_cover et reference FIA. |
| WARNING | lead_time | SDC-VD0956464A->M-1810/007923 | Lead time simule eloigne de la reference moyenne. | ref=3, avg=3.46, min=1, max=10, n=1082 | Verifier stochasticite, lead_cover et reference FIA. |
| WARNING | lead_time | SDC-VD1096202A->M-1810/039668 | Lead time simule eloigne de la reference moyenne. | ref=35, avg=64, min=64, max=64, n=1 | Verifier stochasticite, lead_cover et reference FIA. |
| WARNING | lot_size | SDC-1450->M-1430/773474 | Taille de lot standard = 1: mathematiquement respectee mais non interpretable comme lot industriel. | orders=1254, total_qty=68 096 657 | Demander lot/campagne industrielle reel(le). |
| WARNING | lot_size | SDC-1450->M-1810/693055 | Taille de lot standard = 1: mathematiquement respectee mais non interpretable comme lot industriel. | orders=128138, total_qty=10 495 140 | Demander lot/campagne industrielle reel(le). |
| WARNING | lot_size | SDC-VD0914690A->M-1430/042342 | Taille de lot tres elevee: elle structure fortement les stocks et pics. | std=30 000 000, max_release=30 000 000 | Valider si vraie quantite de commande, MOQ, ou erreur d unite. |
| WARNING | lot_size | SDC-VD0960508A->SDC-1450/021081 | Taille de lot standard = 1: mathematiquement respectee mais non interpretable comme lot industriel. | orders=50430, total_qty=459 316.0 | Demander lot/campagne industrielle reel(le). |
| WARNING | lot_size | SDC-VD0972460A->SDC-1450/021081 | Taille de lot standard = 1: mathematiquement respectee mais non interpretable comme lot industriel. | orders=40354, total_qty=187 276.0 | Demander lot/campagne industrielle reel(le). |
| WARNING | order_smoothing | SDC-VD0914360C->M-1810/338929 | Plus de 10 lots commandes le meme jour IMT sur une lane. | max_lots_same_day=14, std=5 000.0, max_release=70 000.0 | Si non realiste, lisser le carnet initial / cadence fournisseur. |
| WARNING | physical_safety_cover | input_material:M-1430/333362 | Stock minimum descend sous la cible souple de couverture securite. | min=194 450.0, soft_target=1 155 000, full_equiv=1 540 000, safety_days=10 | Validation industrielle: cible souple acceptable ou plancher strict requis ? |
| WARNING | physical_safety_cover | input_material:M-1430/344135 | Stock minimum descend sous la cible souple de couverture securite. | min=132 200.0, soft_target=1 155 000, full_equiv=1 540 000, safety_days=10 | Validation industrielle: cible souple acceptable ou plancher strict requis ? |
| WARNING | physical_safety_cover | input_material:M-1430/734545 | Stock minimum descend sous la cible souple de couverture securite. | min=7 078.6, soft_target=9 240.0, full_equiv=12 320.0, safety_days=10 | Validation industrielle: cible souple acceptable ou plancher strict requis ? |
| WARNING | physical_safety_cover | input_material:M-1430/773474 | Stock minimum descend sous la cible souple de couverture securite. | min=14 383 739, soft_target=22 302 399, full_equiv=29 736 531, safety_days=20 | Validation industrielle: cible souple acceptable ou plancher strict requis ? |
| WARNING | physical_safety_cover | input_material:M-1810/049371 | Stock minimum descend sous la cible souple de couverture securite. | min=5 717.3, soft_target=9 173.2, full_equiv=12 230.9, safety_days=40 | Validation industrielle: cible souple acceptable ou plancher strict requis ? |
| WARNING | physical_safety_cover | input_material:M-1810/338928 | Stock minimum descend sous la cible souple de couverture securite. | min=589 665.0, soft_target=1 526 625, full_equiv=2 035 500, safety_days=10 | Validation industrielle: cible souple acceptable ou plancher strict requis ? |
| WARNING | physical_safety_cover | input_material:M-1810/338929 | Stock minimum descend sous la cible souple de couverture securite. | min=529 600.0, soft_target=1 526 625, full_equiv=2 035 500, safety_days=10 | Validation industrielle: cible souple acceptable ou plancher strict requis ? |
| WARNING | physical_safety_cover | input_material:M-1810/693055 | Stock minimum descend sous la cible souple de couverture securite. | min=1 040 428, soft_target=1 239 620, full_equiv=1 652 826, safety_days=20 | Validation industrielle: cible souple acceptable ou plancher strict requis ? |
| WARNING | source_reference | 001848 | Plusieurs tailles de lot reference pour le meme item selon fournisseur/lane. | 4 000.0, 6 000.0 | Valider si multi-sourcing normal ou erreur FIA. |
| WARNING | source_reference | 001893 | Plusieurs tailles de lot reference pour le meme item selon fournisseur/lane. | 20 900.0, 22 800.0, 23 920.0 | Valider si multi-sourcing normal ou erreur FIA. |
| WARNING | source_reference | 002612 | Plusieurs tailles de lot reference pour le meme item selon fournisseur/lane. | 21 600.0, 22 500.0, 23 750.0 | Valider si multi-sourcing normal ou erreur FIA. |
| WARNING | source_reference | 021081 | Plusieurs tailles de lot reference pour le meme item selon fournisseur/lane. | 1, 20 000.0 | Valider si multi-sourcing normal ou erreur FIA. |
| WARNING | source_reference | 021081.xlsx | FIA 021081 contient des tailles de lot heterogenes, dont des lots a 1. | VD0949099A->SDC-1450/021081: 20 000.0 KG; VD0960508A->SDC-1450/021081: 1 KG; VD0972460A->SDC-1450/021081: 1 KG; VD0975221A->SDC-1450/021081: 20 000.0 KG | Valider si les valeurs 1 sont vraies ou des placeholders. |
| INFO | source_reference | 001848 | Lead times reference differents selon fournisseur/lane. | 21, 56 | Normal si multi-sourcing, sinon harmoniser FIA. |
| INFO | source_reference | 001893 | Lead times reference differents selon fournisseur/lane. | 28, 42, 56 | Normal si multi-sourcing, sinon harmoniser FIA. |
| INFO | source_reference | 002612 | Lead times reference differents selon fournisseur/lane. | 28, 35 | Normal si multi-sourcing, sinon harmoniser FIA. |
| INFO | source_reference | 055703 | Lead times reference differents selon fournisseur/lane. | 21, 42 | Normal si multi-sourcing, sinon harmoniser FIA. |
| INFO | source_reference | 268091 | Lead times reference differents selon fournisseur/lane. | 2, 2.5 | Normal si multi-sourcing, sinon harmoniser FIA. |
| INFO | source_reference | 268967 | Lead times reference differents selon fournisseur/lane. | 2, 2.5 | Normal si multi-sourcing, sinon harmoniser FIA. |
| INFO | unit | 730384 | Unite lineaire M detectee et conservee dans la simulation. | Composant en metres lineaires. | Confirmer que quantite standard et consommation BOM sont en metres. |
| OK | coverage | process_inputs | Tous les inputs de process source sont couverts dans les stocks matieres simules. |  |  |
| OK | coverage | process_outputs | Tous les outputs de process source sont couverts dans les produits simules. |  |  |
| OK | lead_time | arrival_sequence | Aucune reception avant release_day detectee dans mrp_orders_daily. |  |  |
| OK | lot_size | lane_release | Toutes les commandes lane_release avec lot standard > 1 sont des multiples du lot reference simulation. |  |  |
| OK | safety_delay | all | Tous les controles d'arrivee vs besoin respectent le delai de securite (26/26). |  |  |
| OK | safety_policy | explicit_safety_stock_qty | Les safety_stock_qty explicites sont bien ignores dans la reference: seuls les delais de securite pilotent le stock equivalent. |  |  |
| OK | stock | all | Aucun stock physique negatif detecte dans matieres, produits et stocks fournisseurs suivis. |  |  |
