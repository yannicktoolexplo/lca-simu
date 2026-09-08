---
name: etudecas-lot-trace
description: Use when working on Etudecas lotification, lot genealogy, upstream/downstream traceability, mixed lots, transport links, production campaign history, or lot trace payloads and diagrams.
---

# Etudecas Lot Trace

## Workflow

1. Treat the lot ledger as the source of truth: lots, events and parent-child links.
2. Keep selectable lots limited to business lots: PF, PFI and MP. Transports are visible but not selectable.
3. Preserve direction semantics: `all/both`, `upstream/ancestors`, `downstream/descendants`.
4. Distinguish `parent_qty`, `child_qty` and `contribution_qty`.
5. Separate the stable business batch, its stock occurrence and its physical shipment.
6. Prefer backend view models over duplicating business graph logic in JavaScript.

## Identity Contract

- `business_batch_id`: stable identity of the material/PFI/PF batch across sites.
- `lot_occurrence_id`: inventory occurrence at one node; the technical `LOT-*` may remain its compatibility alias.
- `shipment_id`: physical dispatch identity shared by ship, transport genealogy and receipt.
- `handling_unit_id`: optional pallet/container identity; never invent it when packaging data is absent.
- A receipt may create a new stock occurrence, but must preserve `business_batch_id`.
- An aggregate/backordered receipt without parent lot must expose `trace_status=untraced_origin` and a reason.

## Quantity Contract

- For transport, quantities and allocation shares use one item and one UOM.
- For production, compute contribution per `(child_lot_id, parent_item_id)`.
- Never sum quantities from different BOM items or UOMs to calculate a production share.
- When several lots provide one component, the attributable output is:
  `child_qty * parent_qty / total_parent_qty_for_same_component`.
- A mixed customer lot must show traced contribution, other contribution and their batch origins.

## Transport Contract

- A route/day/item grouping is an inferred display group, not a truck.
- Call a movement physical only when `shipment_id`, departure and arrival are recorded.
- Consolidation must be explicit and capacity-aware; it must not be inferred from a post-hoc pallet estimate.
- Preserve departure day, arrival day, route, item, UOM and trace status in the backend payload.

## Procurement Contract

- Keep the MRP order separate from the business lot, stock occurrence and shipment.
- Join `mrp_orders_daily.csv` to lot movements by item, supplier/destination, route, day and quantity.
- Never allocate more received or shipped quantity to an MRP order than the order quantity, and reject an incompatible route instead of merely penalizing it.
- Show distinct dates when available: MRP decision, requested release, simulated shipment, planned arrival and actual receipt.
- A supplier replenishment profile without an individual MRP order must be labelled `reapprovisionnement agrege`.
- For an aggregate receipt, a departure may be inferred from the receipt day and nominal lane lead time only when it is explicitly labelled as estimated.
- Opening stock before J0 must remain `fournisseur/date avant J0 non traces` unless source history provides those facts.
- Never present a lane, inferred departure or simulated shipment as a physical purchase order or carrier proof.

## Key Files

- Payload: `etudecas/simulation/lot_trace/payload.py`.
- Graph indexes: `etudecas/simulation/lot_trace/indexes.py`.
- View model: `etudecas/simulation/lot_trace/view_model.py`.
- Procurement join: `etudecas/simulation/lot_trace/procurement.py`.
- Campaigns and reports: `etudecas/simulation/lot_trace/campaigns.py`.
- Audit: `etudecas/simulation/analysis/audit_lot_paths.py`.

## Validation

Run the full fast suite, then add or run targeted lot tests:

```powershell
python -B -m unittest discover -s etudecas -p "test*.py"
```

Check mixed lots, transport consolidation, reports/rattrapage and stock reconciliation when relevant.

Run the exhaustive lot audits against the active run:

```powershell
python -m etudecas.simulation.analysis.audit_lot_paths --output-root <run>
python -m etudecas.simulation.analysis.audit_lot_trace_semantics --output-root <run>
```
