# SC first analysis

## Executive summary
- Items: 25
- Nodes: 29
- Edges: 33
- Scenarios: 1
- Geo completeness: 29 / 29 (100.0%)
- Single-source pairs: 22 (66.7% des edges)
- Cross-border edges: 7 / 27 (25.9%)

## Coverage des questions d'analyse
| Question | Statut | Evidence |
|---|---|---|
| 1. Structure réseau saine ? | Partiel | 3 composantes, 2 nœuds isolés |
| 2. Dépendances critiques ? | Oui | 22 couples mono-source |
| 3. Demande servable ? | Oui | 2 lignes, 0 non atteignables, 0 à demande nulle |
| 4. Risque géographique ? | Partiel | 7 flux cross-border, concentration pays mesurée |
| 5. Réel vs défaut ? | Oui | lead_time par défaut: 0/33 |
| 6. Priorités d'enrichissement ? | Partiel | Voir section Priorités |

## Connectivity
- Weakly connected components: 3
- Largest component size: 27
- Isolated nodes: 2
- Source nodes: 23
- Sink nodes: 1

### Top nœuds entrants (in-degree)
| Node | In-degree |
|---|---|
| M-1810 | 21 |
| M-1430 | 8 |
| C-XXXXX | 2 |
| DC-1910 | 2 |
| DC-1450 | 0 |

### Top nœuds sortants (out-degree)
| Node | Out-degree |
|---|---|
| DC-1910 | 2 |
| SDC-1450 | 2 |
| SDC-VD0519670A | 2 |
| SDC-VD0520132A | 2 |
| SDC-VD0910216A | 2 |

## Data quality
- Geo filled (lat/lon): 29 / 29
- Edge lead_time default count: 0 / 33
- Edge transport_cost zero default count: 0 / 33
- Inventory states with default initial: 0 / 57
- Process capacity default count: 0 / 2
- Process cost default count: 0 / 2

## Geography
- Countries represented: 6
- Edge with known countries: 27 / 33
- Cross-border edges: 7
- Domestic edges: 20

### Top countries (nodes)
| Country | Node count |
|---|---|
| France | 19 |
| Germany | 4 |
| unknown | 3 |
| Belgium | 1 |
| Italy | 1 |
| Sweden | 1 |

## Supply risk
- Single-source receiving pairs: 22
- Items with <=1 unique supplier: 18

### Sample mono-source pairs (top 10)
| Receiving node | Item | Supplier |
|---|---|---|
| C-XXXXX | item:268091 | DC-1910 |
| C-XXXXX | item:268967 | DC-1910 |
| DC-1910 | item:268091 | M-1810 |
| DC-1910 | item:268967 | M-1430 |
| M-1430 | item:038005 | SDC-VD0520132A |
| M-1430 | item:042342 | SDC-VD0914690A |
| M-1430 | item:333362 | SDC-VD0525412A |
| M-1430 | item:344135 | SDC-VD0993480A |
| M-1430 | item:708073 | SDC-VD0520115A |
| M-1430 | item:730384 | SDC-VD0508918A |

## Demand checks
- Demand rows: 2
- Unreachable demand rows: 0
- Zero-demand rows: 0

## Priorités d'action
- Traiter les couples mono-source (dual sourcing ou stock de sécurité ciblé).
- Décider du sort des nœuds isolés (supprimer, connecter ou documenter).

## Files generated
- summary.json
- node_degrees.csv
- single_source_risk.csv
