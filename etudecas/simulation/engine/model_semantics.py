"""Explicit units, observation dates and missing-value contracts for the engine."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import math
from typing import Any


def inventory_holding_rate(payload: dict[str, Any]) -> tuple[float | None, str]:
    source = str(payload.get('source') or '')
    if 'global_value_median_fallback' in source:
        return None, 'rejected_heterogeneous_unit_price_fallback'
    if payload.get('valuation_status') == 'unknown' or payload.get('value') is None:
        return None, 'missing_dimensioned_inventory_value'
    value = float(payload['value'])
    if not math.isfinite(value) or value < 0:
        raise ValueError('Inventory holding rate must be finite and nonnegative.')
    return value, 'configured_rate'


def transport_charge(lane: dict[str, Any], pulled_qty: float, delivered_qty: float) -> tuple[float, str, float]:
    """The declared tariff unit governs billing; procurement lot size is not a tariff."""
    basis = str(lane.get('transport_cost_basis') or 'unit').strip().lower()
    rate = float(lane.get('unit_transport_cost') or 0)
    if basis in {'unit', 'piece'}:
        units = max(0.0, delivered_qty)
        basis = 'unit'
    elif basis in {'lot', 'batch'}:
        lot_qty = float(lane.get('transport_tariff_batch_qty') or 0)
        if lot_qty <= 0 or not math.isfinite(lot_qty):
            raise ValueError('A per-batch transport tariff requires transport_cost.batch_qty > 0.')
        units = max(0.0, pulled_qty) / lot_qty
        basis = 'batch'
    elif basis in {'shipment', 'dispatch'}:
        units = float(pulled_qty > 0)
        basis = 'shipment'
    else:
        raise ValueError(f'Unsupported transport tariff unit: {basis!r}; supply an explicit tariff conversion.')
    if not math.isfinite(rate) or rate < 0:
        raise ValueError('Transport tariff must be finite and nonnegative.')
    return rate * units, basis, units


def shipment_execution_state(departure_day: int, arrival_day: int, observation_day: int, *, reserved: bool = True) -> str:
    if arrival_day < departure_day:
        raise ValueError('A shipment cannot arrive before departure.')
    if departure_day > observation_day:
        return 'reserved_pending_departure' if reserved else 'planned_pending_departure'
    return 'received' if arrival_day <= observation_day else 'in_transit'


class ReceiptLeadObservations:
    """Latent sampled outcomes become observations only on their receipt date."""
    def __init__(self):
        self.pending = defaultdict(list)

    def schedule(self, *, arrival_day: int, departure_day: int, supplier_pair: tuple[str, str], reference_days: float, quantity: float) -> None:
        if quantity <= 0:
            return
        if arrival_day < departure_day:
            raise ValueError('Receipt precedes departure.')
        self.pending[int(arrival_day)].append((supplier_pair, float(arrival_day - departure_day), max(1.0, float(reference_days))))

    def observe(self, day: int) -> dict[tuple[str, str], list[tuple[float, float]]]:
        observations = defaultdict(list)
        for pair, realized, reference in self.pending.pop(int(day), []):
            observations[pair].append((realized, reference))
        return observations


def safety_calendar_anchor(graph: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    meta = graph.get('meta') or {}
    candidates = [
        ((scenario.get('horizon') or {}).get('start_date'), 'scenario.horizon.start_date'),
        ((meta.get('mrp_seed') or {}).get('snapshot_at_utc'), 'meta.mrp_seed.snapshot_at_utc'),
        ((meta.get('opening_open_orders') or {}).get('snapshot_date'), 'meta.opening_open_orders.snapshot_date'),
    ]
    for value, source in candidates:
        if value:
            start = date.fromisoformat(str(value)[:10])
            return {'start_date': start.isoformat(), 'weekday': start.weekday(), 'anchor_basis': source}
    return {'start_date': None, 'weekday': 0, 'anchor_basis': 'explicit_convention_J0_Monday_without_civil_date'}


def safety_calendar_days(source_days: float, *, day: int, anchor_weekday: int, calendar: str) -> float:
    """Elapsed cover after N working days; no production/transport closure implied."""
    quantity = float(source_days)
    if not math.isfinite(quantity) or quantity < 0:
        raise ValueError('Safety days must be finite and nonnegative.')
    if calendar == 'calendar_days' or quantity == 0:
        return quantity
    if calendar != 'weekdays':
        raise ValueError(f'Unknown safety calendar: {calendar!r}')
    remaining = quantity
    elapsed = 0.0
    weekday = (int(anchor_weekday) + int(day)) % 7
    while remaining > 1e-12:
        weekday = (weekday + 1) % 7
        if weekday < 5:
            fraction = min(1.0, remaining)
            elapsed += fraction
            remaining -= fraction
        else:
            elapsed += 1
    return elapsed
