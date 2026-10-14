"""Causal, opt-in execution of already existing opening purchase commitments.

The opening book remains the planning promise. Historical weekly receipts are
an *execution scenario*, revealed only on their declared knowledge day. They
are never turned into future firm receipts for the MRP. FIFO allocation links
quantities to original rows for bookkeeping; it does not identify actual
industrial purchase orders or supplier batches.

No files are read and no physical stock is changed here. The engine must remove
the managed original promises from its physical scheduler, keep their pending
quantities in its planning book, and execute each returned fragment once through
its normal physical-receipt / held-stock / availability-release registers.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import json
from typing import Any, Mapping, Sequence


MODE = "known_weekly_receipts_fifo_v1"


def _day(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _quantity(value: Any, unit: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("A boolean is not a physical quantity")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid physical quantity") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError("Physical quantity must be positive and finite")
    if unit == "UN" and result != result.to_integral_value():
        raise ValueError("Physical UN quantities must be integers")
    return result


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _pair(row: Mapping[str, Any]) -> tuple[str, str]:
    return _text(row.get("node_id"), "node_id"), _text(row.get("item_id"), "item_id")


def _workday_release(origin: date, received_day: int, workdays: int) -> int:
    current = origin + timedelta(days=received_day)
    remaining = workdays
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return (current - origin).days


class OpeningReceiptExecutionLedger:
    """Allocate known receipt quantities to opening purchases, with no lookahead.

    Construct with :meth:`from_policy`. The opt-in policy has ``schema_version``
    1, ``mode`` :data:`MODE`, ``calendar`` ``monday_friday``, explicit ``pairs``
    and ``events``. Each event provides its pair, ``known_day``, ``quantity``,
    normalized ``uom`` and ``source_file/source_row/source_cell``. The knowledge
    day is the physical execution day of this bounded historical replay; for a
    weekly total the caller must explicitly choose the closing day, not pretend
    to know the exact receipt day within the week.

    ``receive(day)`` returns only new fragments known on that day. The fragment
    retains the original Extract row, but has its own unique ``marker``. Its
    availability day uses the original ``receipt_release_days`` (Monday-Friday)
    from the now executed physical receipt. This is an explicit model convention,
    not an observed quality-release date. Unknown future receipts and quantities
    not yet received remain absent from this API's execution output.
    """

    @classmethod
    def from_policy(
        cls, payload: Mapping[str, Any], *, opening_rows: Sequence[Mapping[str, Any]],
        item_unit_map: Mapping[str, str], origin_date: date,
    ) -> "OpeningReceiptExecutionLedger":
        if (not isinstance(payload, Mapping) or payload.get("schema_version") != 1
                or type(payload.get("schema_version")) is not int
                or payload.get("mode") != MODE or payload.get("calendar") != "monday_friday"):
            raise ValueError("Opening receipt execution requires its explicit versioned policy")
        if type(origin_date) is not date:
            raise ValueError("Opening receipt execution requires a calendar origin date")
        pairs_raw, events_raw = payload.get("pairs"), payload.get("events")
        if not isinstance(pairs_raw, list) or not pairs_raw or not isinstance(events_raw, list):
            raise ValueError("Opening receipt execution requires explicit pairs and an event list")
        pairs = [_pair(row) for row in pairs_raw]
        if len(set(pairs)) != len(pairs):
            raise ValueError("Duplicate opening receipt execution pair")
        obj = cls()
        obj._origin = origin_date
        obj._rows: dict[str, dict[str, Any]] = {}
        obj._remaining: dict[str, Decimal] = {}
        obj._fifo: dict[tuple[str, str], list[str]] = defaultdict(list)
        obj._events: dict[int, list[dict[str, Any]]] = defaultdict(list)
        obj._last_day = -1
        obj._received_days: set[int] = set()
        for raw in opening_rows:
            pair = _pair(raw)
            if pair not in pairs or raw.get("order_type") != "opening_purchase_order":
                continue
            source_file = _text(raw.get("source_file"), "opening source_file")
            source_row = raw.get("source_row")
            if isinstance(source_row, bool) or source_row is None or not str(source_row).strip():
                raise ValueError("Opening purchase requires its original source row")
            marker = "OPENING_DATED_PURCHASE|" + json.dumps(
                [source_file, str(source_row)], ensure_ascii=False, separators=(",", ":"))
            if raw.get("marker", marker) != marker or marker in obj._rows:
                raise ValueError("Opening purchase marker must uniquely identify its source row")
            unit = _text(item_unit_map.get(pair[1]), "normalized item unit").upper()
            quantity = _quantity(raw.get("receipt_qty"), unit)
            physical = _day(raw.get("physical_delivery_day"), "promised physical receipt")
            available = _day(raw.get("arrival_day"), "promised availability")
            workdays = _day(raw.get("receipt_release_days"), "receipt workdays")
            if available < physical:
                raise ValueError("Opening availability cannot precede its promised physical receipt")
            row = deepcopy(dict(raw))
            row.update(marker=marker, uom=unit, quantity=float(quantity),
                       receipt_release_days=workdays, received=False, released=False, lot_id="")
            obj._rows[marker] = row
            obj._remaining[marker] = quantity
            obj._fifo[pair].append(marker)
        if set(obj._fifo) != set(pairs):
            raise ValueError("Every execution pair must have explicit opening purchase commitments")
        # Source row is a deterministic tie-breaker only, not an industrial ID.
        for pair, markers in obj._fifo.items():
            markers.sort(key=lambda m: (obj._rows[m]["physical_delivery_day"],
                                       obj._rows[m]["arrival_day"],
                                       str(obj._rows[m]["source_file"]),
                                       str(obj._rows[m]["source_row"])))
        event_ids: set[str] = set()
        for raw in events_raw:
            pair = _pair(raw)
            if pair not in obj._fifo:
                raise ValueError("Historical receipt outside the explicit opening purchase scope")
            known_day = _day(raw.get("known_day"), "receipt knowledge day")
            unit = _text(raw.get("uom"), "receipt unit").upper()
            if unit != obj._rows[obj._fifo[pair][0]]["uom"]:
                raise ValueError("Historical receipts must already use the normalized item unit")
            source_file = _text(raw.get("source_file"), "receipt source_file")
            source_cell = _text(raw.get("source_cell"), "receipt source_cell")
            source_row = raw.get("source_row")
            if type(source_row) is not int or source_row <= 0:
                raise ValueError("Historical receipt requires a positive Excel source row")
            event_id = json.dumps([source_file, source_row, source_cell], separators=(",", ":"))
            if event_id in event_ids:
                raise ValueError("A source receipt cell cannot be allocated twice")
            event_ids.add(event_id)
            obj._events[known_day].append(dict(pair=pair, known_day=known_day,
                quantity=_quantity(raw.get("quantity"), unit), uom=unit,
                source_file=source_file, source_row=source_row, source_cell=source_cell,
                event_id=event_id))
        return obj

    @property
    def managed_markers(self) -> frozenset[str]:
        return frozenset(self._rows)

    @property
    def initial_rows_by_marker(self) -> dict[str, dict[str, Any]]:
        """Initial promises only; no future historical event is exposed."""
        return deepcopy(self._rows)

    def pending_by_marker(self) -> dict[str, float]:
        """Unreceived quantity, including zero for fully received original rows.

        An overdue positive remainder stays committed. Its planning bound is
        obtained from :meth:`pending_available_day`, which also preserves the
        treatment still required after a not-yet-observed physical receipt.
        """
        return {marker: float(quantity) for marker, quantity in self._remaining.items()}

    def pending_available_day(self, marker: str, decision_day: int) -> int:
        """Earliest planning bound, not a newly observed delivery promise.

        If the purchase has not physically arrived by today's planning step,
        receipt is possible no earlier than tomorrow, followed by the original
        treatment duration. Its old promised availability remains a lower bound.
        No future historical receipt event is consulted for this calculation.
        """
        _day(decision_day, "planning decision day")
        if marker not in self._rows:
            raise ValueError("Unknown opening commitment marker")
        original = self._rows[marker]
        earliest = _workday_release(self._origin, decision_day + 1,
                                   original["receipt_release_days"])
        return max(original["arrival_day"], earliest)

    def receive(self, day: int) -> list[dict[str, Any]]:
        """Reveal today's receipts and allocate FIFO exactly once.

        Skipping a pending knowledge day is rejected rather than executing a
        receipt retroactively. A repeated call on the same day is idempotent.
        Excess history is rejected before changing any state: the caller must
        never silently allocate it to autonomous new purchases.
        """
        _day(day, "execution day")
        if day < self._last_day:
            raise ValueError("Opening receipt execution cannot move backwards in time")
        if any(known < day and known not in self._received_days for known in self._events):
            raise ValueError("A receipt knowledge day was skipped; no retroactive execution allowed")
        if day in self._received_days:
            return []
        events = self._events.get(day, ())
        needed: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        for event in events:
            needed[event["pair"]] += event["quantity"]
        for pair, quantity in needed.items():
            remaining = sum((self._remaining[m] for m in self._fifo[pair]), Decimal(0))
            if quantity > remaining:
                raise ValueError("Known receipts exceed the remaining opening purchase commitments")
        fragments = []
        for event in events:
            unallocated = event["quantity"]
            for marker in self._fifo[event["pair"]]:
                quantity = min(self._remaining[marker], unallocated)
                if quantity <= 0:
                    continue
                original = self._rows[marker]
                fragment_marker = "OPENING_EXECUTED_FRAGMENT|" + json.dumps(
                    [marker, event["event_id"]], ensure_ascii=False, separators=(",", ":"))
                available = _workday_release(self._origin, day, original["receipt_release_days"])
                fragment = deepcopy(original)
                fragment.update(marker=fragment_marker, mrp_order_id=fragment_marker,
                    baseline_reference_id=marker, original_marker=marker,
                    original_source_file=original["source_file"], original_source_row=original["source_row"],
                    quantity=float(quantity), receipt_qty=float(quantity),
                    physical_delivery_day=day, arrival_day=available, available_day=available,
                    execution_mode=MODE, receipt_known_day=day,
                    receipt_source_file=event["source_file"], receipt_source_row=event["source_row"],
                    receipt_source_cell=event["source_cell"], receipt_event_id=event["event_id"],
                    original_promised_physical_day=original["physical_delivery_day"],
                    original_promised_available_day=original["arrival_day"],
                    allocation_basis="fifo_technical_not_observed_order_identity",
                    availability_basis="original_receipt_workdays_after_known_physical_receipt",
                    received=False, released=False, lot_id="")
                fragments.append(fragment)
                self._remaining[marker] -= quantity
                unallocated -= quantity
                if unallocated == 0:
                    break
        self._last_day = day
        self._received_days.add(day)
        return fragments
