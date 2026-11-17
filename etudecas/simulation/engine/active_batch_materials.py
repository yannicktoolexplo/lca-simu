"""Optional material protection for already executing physical batches.

This allocates a view of usable stock, never consumes it. A shared pool is
decremented across all batch claims, including authorized substitute articles.
"""
from dataclasses import dataclass, replace
from decimal import Decimal
import math

from etudecas.simulation.lot_policy.models import normalize_uom
from etudecas.simulation.engine.mrp_planning import serve_external_component_requirements
from etudecas.simulation.engine.production_component_issues import incremental_component_issue

ACTIVE_BATCH_MATERIAL_POLICY = "engaged_remaining_v1"


@dataclass(frozen=True)
class ActiveBatchMaterialClaim:
    batch_id: str
    node_id: str
    required_item_id: str
    remaining_qty: float
    uom: str
    started_day: int
    # (physical item, native consume policy); only date-eligible transitions.
    substitutes: tuple[tuple[str, str], ...] = ()


def _quantity(value, unit):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Material protection requires finite nonnegative quantities")
    number = Decimal(str(value))
    if normalize_uom(unit) == "UN" and number != number.to_integral_value():
        raise ValueError("Protected physical units must be integers")
    return number


def claims_for_engaged_batches(batches, *, bom_by_pair, modeled_pairs, item_uoms, substitutes_by_pair):
    """Only batches with physical work already executed, never future orders."""
    claims=[]
    for pair,batch in batches.items():
        if batch.executed_qty <= 0 or batch.is_complete:
            continue
        if (batch.node_id,batch.item_id) != pair:
            raise ValueError("Active batch does not match its process pair")
        for component,ratio in bom_by_pair.get(pair,()):
            if component not in modeled_pairs:
                continue
            unit=item_uoms[component[1]]
            quantity=incremental_component_issue(batch.executed_qty,batch.remaining_qty,
                ratio,unit,batch.issued_by_component.get(component[1],0.0))
            claims.append(ActiveBatchMaterialClaim(batch.batch_id,component[0],component[1],
                quantity,unit,batch.batch_started_day,tuple(substitutes_by_pair.get(component,()))))
    return tuple(claims)


def allocate_active_batch_materials(claims, *, available_by_pair, item_uoms):
    """Return protected quantities and claim allocations without mutating input.

    Oldest engaged batch first, then stable identity. Uncovered needs are
    exported, not fabricated. A substitute's physical stock is reserved once.
    """
    pool = {pair: _quantity(qty, item_uoms[pair[1]]) for pair, qty in available_by_pair.items()}
    physical_snapshot = dict(pool)
    claims = tuple(claims)
    seen = set()
    for claim in claims:
        key = (claim.batch_id, claim.node_id, claim.required_item_id)
        if key in seen or not all(isinstance(v,str) and v for v in key):
            raise ValueError("Duplicate or invalid batch/component claim")
        seen.add(key)
        if type(claim.started_day) is not int:
            raise ValueError("Physical batch start day must be an integer")
        _quantity(claim.remaining_qty, claim.uom)
        if normalize_uom(claim.uom) != normalize_uom(item_uoms[claim.required_item_id]):
            raise ValueError("Claim and physical component units differ")
        substitute_ids = [item for item, _ in claim.substitutes]
        if len(set(substitute_ids)) != len(substitute_ids) or claim.required_item_id in substitute_ids:
            raise ValueError("Duplicate or self substitution")
        for item, _ in claim.substitutes:
            if normalize_uom(item_uoms[item]) != normalize_uom(claim.uom):
                raise ValueError("Physical reference substitution requires matching units")
    protected = {}; audit = []
    for claim in sorted(claims, key=lambda c:(c.started_day,c.batch_id,c.node_id,c.required_item_id)):
        remaining = _quantity(claim.remaining_qty, claim.uom)
        primary_pair = (claim.node_id, claim.required_item_id)
        # A reservation is not a physical consumption: the native transition
        # remains disabled while primary physical stock exists in this snapshot.
        primary_before = physical_snapshot.get(primary_pair, Decimal(0))
        candidates = [(claim.required_item_id, "primary")] + list(claim.substitutes)
        for item, policy in candidates:
            if policy == "use_old_until_new_stock_available" and primary_before > 0:
                continue
            pair = (claim.node_id,item)
            quantity = min(remaining,pool.get(pair,Decimal(0)))
            if quantity <= 0:
                continue
            pool[pair] -= quantity
            protected[pair] = protected.get(pair,Decimal(0)) + quantity
            remaining -= quantity
            audit.append(dict(batch_id=claim.batch_id,node_id=claim.node_id,
                required_item_id=claim.required_item_id,physical_item_id=item,uom=claim.uom,
                requested_remaining_qty=claim.remaining_qty,protected_qty=float(quantity),
                uncovered_qty=0.0,allocation_kind="primary" if item==claim.required_item_id else "authorized_substitute"))
            if remaining == 0:
                break
        if remaining > 0:
            audit.append(dict(batch_id=claim.batch_id,node_id=claim.node_id,
                required_item_id=claim.required_item_id,physical_item_id="",uom=claim.uom,
                requested_remaining_qty=claim.remaining_qty,protected_qty=0.0,
                uncovered_qty=float(remaining),allocation_kind="uncovered"))
    return {pair:float(qty) for pair,qty in protected.items()}, audit


def serve_with_active_batch_protection(*, decision_day, available_qty, protected_qty, backlog, due, uom):
    """Serve external needs from free stock; retain the protected physical stock."""
    available = _quantity(available_qty,uom)
    protected = _quantity(protected_qty,uom)
    if protected > available:
        raise ValueError("Protection exceeds usable physical stock")
    service = serve_external_component_requirements(decision_day=decision_day,
        available_qty=float(available-protected),backlog=backlog,due=due,uom=uom)
    # available_end_qty in the service object is only the FREE remainder.
    # Subtract the real debit from the original stock, preserving protection.
    # Sum the actual allocations in decimal: fsum([.1,.2]) is a binary value
    # slightly above .3 and must not falsely consume a .1 KG reservation.
    consumed = sum((Decimal(str(row.qty)) for row in service.allocations),Decimal(0))
    physical_end = available-consumed
    if physical_end < protected:
        raise ArithmeticError("External service consumed active-batch protection")
    service = replace(service,consumed_qty=float(consumed),available_end_qty=float(physical_end-protected))
    return service,float(physical_end)
