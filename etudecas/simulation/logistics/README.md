# Truck consolidation

This module consolidates simulated shipment lines without changing the
simulation engine or the map.

## Physical rules

The default truck is configured from the explicit project requirement:

- 33 Euro pallets;
- 23,000 kg payload;
- no default volume capacity because none was supplied.

`G` and `KG` are converted to **net** kilograms by unit definition. This net
weight is an auditable lower bound, not a gross loaded weight. `UN` and `M`
are never converted to weight. Pallets and volume are never inferred from
weight.

A line is eligible for physical truck allocation only when every active
capacity dimension is known:

- gross loaded weight;
- pallets;
- volume, only when a volume capacity is configured.

Unknown lines are grouped by route, compatibility class and planning week.
The fallback records quantities by UOM, lots, source shipments, known
dimensions, missing dimensions and a lower bound based only on known capacity
data. Quantities are also retained by item and UOM when several items share a
route and a week. `truck_count` remains empty.

Eligible lines are assigned with a deterministic best-fit-decreasing heuristic
using the dominant capacity ratio. The result is a reproducible loading
proposal, not a claim that the number of trucks is the mathematical optimum.
The audit records the algorithm and every profile source used.

## Item profile

Optional CSV columns:

```text
item_id,uom,kg_per_unit,pallets_per_unit,volume_m3_per_unit,source_reference,compatibility_group,notes
```

Every conversion requires a non-empty `source_reference`.
`kg_per_unit` must describe gross loaded kilograms, including relevant
packaging or handling units. A profile that only supplies pallets does not
turn a net `G`/`KG` mass into a gross payload.

## CLI

```powershell
python -m etudecas.simulation.logistics `
  --lot-events path/to/production_lot_events.csv `
  --graph path/to/simulation_graph.json `
  --profiles path/to/item_logistics_profiles.csv `
  --output-dir path/to/logistics_output
```

Outputs:

- `truck_loads.csv`;
- `truck_load_allocations.csv`;
- `weekly_fallback_groups.csv`;
- `consolidation_audit.json`.
