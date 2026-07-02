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
5. Prefer backend view models over duplicating business graph logic in JavaScript.

## Key Files

- Payload: `etudecas/simulation/lot_trace/payload.py`.
- Graph indexes: `etudecas/simulation/lot_trace/indexes.py`.
- View model: `etudecas/simulation/lot_trace/view_model.py`.
- Campaigns and reports: `etudecas/simulation/lot_trace/campaigns.py`.
- Audit: `etudecas/simulation/analysis/audit_lot_paths.py`.

## Validation

Run the full fast suite, then add or run targeted lot tests:

```powershell
python -B -m unittest discover -s etudecas -p "test*.py"
```

Check mixed lots, transport consolidation, reports/rattrapage and stock reconciliation when relevant.
