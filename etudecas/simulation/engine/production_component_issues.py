"""Pure component-issue arithmetic for one continuously progressing batch.

An integer component already debited for this batch can cover later work in
the same batch. It is not available stock and cannot fund another batch. The
caller owns the batch-scoped physical issue ledger and its lot genealogy.
Mass and length retain the existing per-operation quantity multiplication.
"""
from __future__ import annotations

import math

from etudecas.simulation.lot_policy.engine_adapter import required_component_quantity
from etudecas.simulation.lot_policy.models import normalize_uom

BATCH_CUMULATIVE_ISSUE_POLICY = "batch_cumulative_v1"


def _quantity(raw, name):
    if isinstance(raw, bool):
        raise ValueError(f"{name} must be numeric, not boolean")
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite nonnegative quantity") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative quantity")
    return value


def _component(ratio, uom, issued_before, available=None):
    ratio = _quantity(ratio, "BOM ratio")
    if ratio <= 0:
        raise ValueError("BOM ratio must be positive")
    unit = normalize_uom(uom)
    issued = _quantity(issued_before, "Previously issued component")
    stock = None if available is None else _quantity(available, "Available component")
    if unit == "UN" and (not issued.is_integer() or (stock is not None and not stock.is_integer())):
        raise ValueError("Physical UN issues and available stock must be integers")
    return ratio, unit, issued, stock


def incremental_component_issue(executed_before, additional_work, ratio, uom, issued_before):
    """Physical debit now; only integer components use the cumulative ceiling.

    UN: max(0, ceil((previous work + new work) * ratio) - already debited).
    KG/G/M: new work * ratio, exactly the existing operation convention.
    A zero-work pass never consumes a component or repairs old ledger entries.
    """
    before = _quantity(executed_before, "Previously executed work")
    additional = _quantity(additional_work, "Additional work")
    ratio, unit, issued, _ = _component(ratio, uom, issued_before)
    if additional == 0:
        return 0.0
    if unit != "UN":
        return _quantity(additional * ratio, "Continuous component issue")
    total = _quantity(before + additional, "Cumulative batch work")
    _quantity(total * ratio, "Cumulative component requirement")
    target = required_component_quantity(total, ratio, unit)
    return max(0.0, target - issued)


def cumulative_work_bound(*, executed_before, available, ratio, uom, issued_before):
    """Additional work supported by current stock and this batch's UN credit.

    This bound never rounds the work or the capacity upwards. It is a float
    bound; feasible_cumulative_work repairs an UN ceiling at its numeric edge.
    """
    before = _quantity(executed_before, "Previously executed work")
    ratio, unit, issued, stock = _component(ratio, uom, issued_before, available)
    if stock is None:
        raise ValueError("Available component stock is required")
    if unit == "UN":
        total_component = _quantity(issued + stock, "Total batch component allowance")
        supported_total = _quantity(total_component / ratio, "Supported cumulative work")
        return max(0.0, supported_total - before)
    return _quantity(stock / ratio, "Supported continuous work")


def feasible_cumulative_work(value, executed_before, component_limits):
    """Bound work without mutating stock, reservations, WIP or the input list.

    Each limit is (available stock, BOM ratio, component unit, already issued
    for this batch). All limits are validated before applying any of them.
    The returned work never exceeds the caller's actual capacity/work limit.
    """
    quantity = _quantity(value, "Candidate work")
    before = _quantity(executed_before, "Previously executed work")
    try:
        limits = tuple(component_limits)
    except TypeError as exc:
        raise ValueError("Component limits must be an iterable of four-field records") from exc
    checked = []
    for row in limits:
        if not isinstance(row, (tuple, list)) or len(row) != 4:
            raise ValueError("Each component limit needs stock, ratio, unit and previous issue")
        available, ratio, unit, issued = row
        ratio, unit, issued, stock = _component(ratio, unit, issued, available)
        if stock is None:
            raise ValueError("Available component stock is required")
        checked.append((stock, ratio, unit, issued))
    for stock, ratio, unit, issued in checked:
        quantity = min(quantity, cumulative_work_bound(executed_before=before,
            available=stock, ratio=ratio, uom=unit, issued_before=issued))
        if unit != "UN":
            continue
        # Moving the cumulative work by one ULP avoids an unbounded number of
        # nextafter steps on a tiny increment beside a large previous WIP.
        # Division/multiplication can straddle an integer by a binary ULP;
        # repair the feasible work, never permit an extra physical component.
        for _ in range(64):
            if incremental_component_issue(before, quantity, ratio, unit, issued) <= stock:
                break
            total = before + quantity
            lowered = max(0.0, math.nextafter(total, 0.0) - before)
            quantity = min(lowered, math.nextafter(quantity, 0.0))
        else:
            raise ArithmeticError("Unable to resolve cumulative integer-component feasibility")
    return quantity
