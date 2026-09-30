"""Pure dated material planning, independent of the daily physical simulation.

Existing commitments are netted before proposing additional purchases, even
when late. This explicit no-duplicate-purchase convention is not claimed to be
the unidentified industrial ERP policy. Dates of firm receipts never change.
The signed balances are projections, not negative physical inventories.
"""
from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_left, bisect_right
from collections import defaultdict, deque
from datetime import date
from decimal import Decimal
from math import ceil, floor, fsum, isfinite, nextafter
from typing import Iterable, Mapping


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    due_day: int
    qty: float


@dataclass(frozen=True)
class ExternalComponentService:
    """Physical allocations to uses outside the modeled finished products."""

    allocations: tuple[Requirement, ...]
    remaining: tuple[Requirement, ...]
    demand_qty: float
    backlog_start_qty: float
    consumed_qty: float
    available_end_qty: float


def _component_quantity(value, *, uom: str, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{field} must be a numeric component quantity")
    quantity = _number(value, field)
    if uom == "UN" and quantity != floor(quantity):
        raise ValueError(f"{field} must be integer for physical UN")
    return quantity


class ExternalComponentDemandCalendar:
    """One selected incremental scenario, never a sum of rolling MRP vintages.

    Weekly quantities are already net of the modeled product scope in the
    scenario estimator. This class neither derives them from stock nor subtracts
    a BOM again. Unprovided periods remain outside the declared scenario; they
    are not industrial observations of zero demand. Repeated years are synthetic.
    """

    def __init__(self, payload, *, pair_uoms: Mapping, origin_date: str, horizon_days: int):
        if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or payload["schema_version"] not in (1, 2, 3):
            raise ValueError("External component demands require schema_version 1, 2 or 3")
        self.schema_version = payload["schema_version"]
        self.has_revisions = self.schema_version in (2, 3)
        if not self.has_revisions and "versioned_series" in payload:
            raise ValueError("Versioned external component demands require schema_version 2 or 3")
        if payload.get("origin") != origin_date:
            raise ValueError("External component demand origin must match the simulation")
        date.fromisoformat(origin_date)
        if type(horizon_days) is not int or horizon_days <= 0:
            raise ValueError("External component horizon must be a positive integer")
        self.scenario_id = payload.get("scenario_id")
        if not isinstance(self.scenario_id, str) or not self.scenario_id.strip():
            raise ValueError("External component scenario_id is required")
        if payload.get("semantics") != "incremental_non_modelled_component_use":
            raise ValueError("External component rows must describe incremental non-modeled uses")
        repeat = payload.get("repeat_period_days")
        if repeat is not None and (type(repeat) is not int or repeat != 365):
            raise ValueError("External component repetition must explicitly be 365 days or null")
        self.repeat_period_days = repeat
        self.horizon_days = horizon_days
        rows = payload.get("rows")
        if not isinstance(rows, list) or (not rows and not self.has_revisions):
            raise ValueError("External component rows must be a list, nonempty for schema 1")
        self.row_count = len(rows)
        self._daily: dict = defaultdict(list)
        self._provenance: dict = {}
        self._fixed_day_audit: dict = {}
        self._revision_series: dict = {}
        self._revision_identity: dict = {}
        self.version_count = 0
        intervals: dict = defaultdict(list)
        seen: set[str] = set()
        all_pairs = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("External component row must be an object")
            identity = row.get("demand_id")
            _identity(identity, seen, "external demand_id")
            pair = (row.get("node_id"), row.get("item_id"))
            uom = row.get("uom")
            if (any(not isinstance(part, str) or not part.strip() for part in pair)
                    or pair not in pair_uoms or not isinstance(uom, str) or not uom or pair_uoms[pair] != uom):
                raise ValueError("External demand must identify a modeled component with its exact unit")
            known, start, length = (row.get(k) for k in ("known_day", "period_start_day", "period_days"))
            if (any(type(day) is not int for day in (known, start, length))
                    or not 0 <= known <= start < 365 or not 1 <= length <= 7 or start + length > 365):
                raise ValueError("External component periods must lie in year one and be known by their start")
            if any(start < previous_end and previous_start < start + length
                   for previous_start, previous_end in intervals[pair]):
                raise ValueError("External component periods overlap; select one source plan rather than add vintages")
            intervals[pair].append((start, start + length))
            qty = _component_quantity(row.get("qty"), uom=uom, field="external component qty")
            for field in ("source_file", "source_cells", "estimation_basis"):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise ValueError(f"External component {field} is required")
            all_pairs.add(pair)
            cycles = range((horizon_days - 1) // repeat + 1) if repeat else range(1)
            total = Decimal(str(qty))
            # Difference of cumulative floors conserves each weekly UN total.
            cumulative = [Decimal(floor(total * i / length)) if uom == "UN" else total * i / length
                          for i in range(length + 1)]
            for cycle in cycles:
                shift = cycle * (repeat or 0)
                for offset in range(length):
                    due_day = start + shift + offset
                    if due_day >= horizon_days:
                        continue
                    amount = float(cumulative[offset + 1] - cumulative[offset])
                    if self.has_revisions:
                        self._fixed_day_audit[(pair, due_day)] = {
                            "known_day": known + shift, "period_start_day": start + shift,
                            "source_file": row["source_file"], "source_cells": row["source_cells"],
                        }
                    if amount <= 0:
                        continue
                    requirement_id = f"external:{self.scenario_id}:{identity}:C{cycle}:D{due_day}"
                    requirement = Requirement(requirement_id, due_day, amount)
                    self._daily[pair].append((due_day, known + shift, requirement))
                    self._provenance[requirement_id] = {
                        "demand_id": identity, "scenario_id": self.scenario_id, "cycle_index": cycle,
                        "known_day": known + shift, "source_file": row["source_file"],
                        "source_cells": row["source_cells"], "estimation_basis": row["estimation_basis"],
                    }
        if self.has_revisions:
            self._load_revision_series(payload.get("versioned_series"), pair_uoms, all_pairs)
        self.versioned_pairs = tuple(sorted(self._revision_series))
        self.pairs = tuple(sorted(all_pairs))
        self._days = {}
        for pair, events in self._daily.items():
            events.sort(key=lambda event: (event[0], event[2].requirement_id))
            self._days[pair] = [event[0] for event in events]

    def _load_revision_series(self, series_rows, pair_uoms: Mapping, all_pairs: set) -> None:
        """Validate complete forecast vintages without treating omissions as data."""
        if not isinstance(series_rows, list) or not series_rows:
            raise ValueError("Revision schemas require nonempty versioned_series")
        for series in series_rows:
            if not isinstance(series, dict):
                raise ValueError("A versioned component series must be an object")
            pair = (series.get("node_id"), series.get("item_id"))
            uom = series.get("uom")
            if (any(not isinstance(part, str) or not part.strip() for part in pair)
                    or pair not in pair_uoms or not isinstance(uom, str) or not uom or pair_uoms[pair] != uom):
                raise ValueError("Versioned demand must identify a modeled component with its exact unit")
            if pair in all_pairs:
                raise ValueError("A component cannot have both fixed and versioned demand series")
            if (type(series.get("repeat_period_days")) is not int or series["repeat_period_days"] != 0
                    or type(series.get("period_anchor_day")) is not int or series["period_anchor_day"] != 4
                    or type(series.get("period_days")) is not int or series["period_days"] != 7):
                raise ValueError("Versioned component series requires no repetition, Sunday anchor 4 and seven-day periods")
            if (series.get("current_bucket_policy") != "freeze_previous_exclude_current_vintage"
                    or series.get("missing_future_policy") != "unprovided_not_observed_zero"):
                raise ValueError("Versioned component series must freeze current weeks and expose missing future periods")
            source_versions = series.get("versions")
            if not isinstance(source_versions, list) or not source_versions:
                raise ValueError("A versioned component series requires explicit vintages")
            versions, known_days, identities = [], set(), set()
            for version in source_versions:
                if not isinstance(version, dict):
                    raise ValueError("A component vintage must be an object")
                vintage_id, known = version.get("vintage_id"), version.get("known_day")
                _identity(vintage_id, identities, "component vintage_id")
                if type(known) is not int or not 0 <= known < 365 or known in known_days:
                    raise ValueError("Component vintage known_day must be unique and within year one")
                known_days.add(known)
                period_rows = version.get("rows")
                if not isinstance(period_rows, list):
                    raise ValueError("Component vintage rows must be an explicit list (possibly empty)")
                periods, row_ids = {}, set()
                for row in period_rows:
                    if not isinstance(row, dict):
                        raise ValueError("Component vintage row must be an object")
                    _identity(row.get("demand_id"), row_ids, "versioned demand_id")
                    start, length = row.get("period_start_day"), row.get("period_days")
                    if type(start) is not int or type(length) is not int or start in periods:
                        raise ValueError("Versioned periods require integer dates and unique weeks")
                    if self.schema_version == 3:
                        if not known < start <= known + 364 or (start - 4) % 7 != 0 or length != 7:
                            raise ValueError("Schema 3 periods must be future Sunday weeks within the known vintage's 52-week horizon")
                    elif not known < start < 365 or (start - 4) % 7 != 0 or length != min(7, 365 - start):
                        raise ValueError("Versioned periods must be unique future Sunday weeks, truncated only at year end")
                    qty = _component_quantity(row.get("qty"), uom=uom, field="versioned component qty")
                    for field in ("source_file", "source_cells", "estimation_basis"):
                        if not isinstance(row.get(field), str) or not row[field].strip():
                            raise ValueError(f"Versioned component {field} is required")
                    total = Decimal(str(qty))
                    cumulative = [Decimal(floor(total * i / length)) if uom == "UN" else total * i / length
                                  for i in range(length + 1)]
                    periods[start] = {**row, "daily_qty": tuple(float(cumulative[i + 1] - cumulative[i])
                                                               for i in range(length))}
                    for due_day in range(start, start + length):
                        identity = self._versioned_requirement_id(pair, start, due_day)
                        self._revision_identity[identity] = (pair, due_day)
                self.row_count += len(period_rows)
                versions.append({"vintage_id": vintage_id, "known_day": known, "periods": periods})
            versions.sort(key=lambda version: version["known_day"])
            self.version_count += len(versions)
            self._revision_series[pair] = {
                "versions": versions, "known_days": [version["known_day"] for version in versions],
            }
            all_pairs.add(pair)

    def _versioned_requirement_id(self, pair, period_start: int, due_day: int) -> str:
        # Forecast revisions change amounts, never the logical need's identity.
        return f"external:{self.scenario_id}:revision:{pair[0]}:{pair[1]}:W{period_start}:D{due_day}"

    def _revision_selection(self, pair, *, decision_day: int, due_day: int):
        period_start = 4 + ((due_day - 4) // 7) * 7
        series = self._revision_series[pair]
        as_of = min(decision_day, period_start - 1)
        index = bisect_right(series["known_days"], as_of) - 1
        version = series["versions"][index] if index >= 0 else None
        end = self.horizon_days if self.schema_version == 3 else 365
        row = version["periods"].get(period_start) if version is not None and 0 <= due_day < end else None
        return period_start, version, row

    def requirements(self, *, decision_day: int, first_day: int, through_day: int) -> dict:
        for value in (decision_day, first_day, through_day):
            _day(value, "external component query day")
        if decision_day < 0 or first_day < 0 or through_day < first_day:
            raise ValueError("Invalid external component query interval")
        result = {}
        for pair, events in self._daily.items():
            days = self._days[pair]
            selected = tuple(event[2] for event in events[bisect_left(days, first_day):bisect_right(days, through_day)]
                             if event[1] <= decision_day)
            if selected:
                result[pair] = selected
        for pair in self._revision_series:
            selected = []
            revision_end = self.horizon_days - 1 if self.schema_version == 3 else min(self.horizon_days - 1, 364)
            for due_day in range(first_day, min(through_day, revision_end) + 1):
                start, version, row = self._revision_selection(pair, decision_day=decision_day, due_day=due_day)
                if row is not None:
                    amount = row["daily_qty"][due_day - start]
                    if amount > 0:
                        selected.append(Requirement(self._versioned_requirement_id(pair, start, due_day), due_day, amount))
            if selected:
                result[pair] = tuple(selected)
        return result

    def due(self, day: int) -> dict:
        return self.requirements(decision_day=day, first_day=day, through_day=day)

    def provenance(self, requirement_id: str) -> dict:
        if requirement_id in self._revision_identity:
            pair, due_day = self._revision_identity[requirement_id]
            _, version, row = self._revision_selection(pair, decision_day=due_day, due_day=due_day)
            if row is None:
                raise ValueError("No frozen physical demand exists for this versioned requirement")
            return {"demand_id": row["demand_id"], "scenario_id": self.scenario_id, "cycle_index": 0,
                    "vintage_id": version["vintage_id"], "known_day": version["known_day"],
                    "period_start_day": row["period_start_day"], "source_file": row["source_file"],
                    "source_cells": row["source_cells"], "estimation_basis": row["estimation_basis"],
                    "forecast_update_mode": "rolling_vintages_future_replacement_current_week_frozen"}
        return dict(self._provenance[requirement_id])

    def day_audit(self, pair, *, decision_day: int) -> dict:
        """Audit today's frozen need separately from the latest future forecast."""
        _day(decision_day, "external component audit day")
        if decision_day < 0 or pair not in self.pairs:
            raise ValueError("External component audit requires a modeled pair and nonnegative day")
        audit = {
            "forecast_selection_mode": "fixed_scenario", "forecast_vintage_id": "",
            "forecast_known_day": "", "forecast_latest_known_vintage_id": "",
            "forecast_latest_known_day": "", "forecast_period_start_day": "",
            "forecast_source_covered": 0, "forecast_coverage_reason": "unprovided_scenario_period",
            "forecast_source_file": "", "forecast_source_cells": "",
        }
        if pair not in self._revision_series:
            row = self._fixed_day_audit.get((pair, decision_day))
            if row is not None and row["known_day"] <= decision_day:
                audit.update(forecast_vintage_id="fixed", forecast_known_day=row["known_day"],
                             forecast_latest_known_vintage_id="fixed", forecast_latest_known_day=row["known_day"],
                             forecast_period_start_day=row["period_start_day"], forecast_source_covered=1,
                             forecast_coverage_reason="provided_scenario_period",
                             forecast_source_file=row["source_file"], forecast_source_cells=row["source_cells"])
            return audit
        start, version, row = self._revision_selection(pair, decision_day=decision_day, due_day=decision_day)
        series = self._revision_series[pair]
        latest_index = bisect_right(series["known_days"], decision_day) - 1
        latest = series["versions"][latest_index] if latest_index >= 0 else None
        audit.update(forecast_selection_mode="rolling_vintages_current_week_frozen",
                     forecast_period_start_day=start,
                     forecast_coverage_reason=("outside_revision_horizon" if decision_day >= (self.horizon_days if self.schema_version == 3 else 365)
                                               else "no_known_vintage_before_period" if version is None
                                               else "missing_period_in_selected_vintage"))
        if version is not None:
            audit.update(forecast_vintage_id=version["vintage_id"], forecast_known_day=version["known_day"])
        if latest is not None:
            audit.update(forecast_latest_known_vintage_id=latest["vintage_id"],
                         forecast_latest_known_day=latest["known_day"])
        if row is not None:
            audit.update(forecast_source_covered=1, forecast_coverage_reason="provided_scenario_period",
                         forecast_source_file=row["source_file"], forecast_source_cells=row["source_cells"])
        return audit


def serve_external_component_requirements(
    *, decision_day: int, available_qty: float, backlog: Iterable[Requirement],
    due: Iterable[Requirement], uom: str,
) -> ExternalComponentService:
    """Allocate only available stock, FIFO, without adding a finished product.

    Caller supplies stock after modeled production, excluding held/reserved
    quantities. The returned remainders retain their original identities/dates
    for tomorrow's execution and today's dated purchasing snapshot.
    """
    _day(decision_day, "external service day")
    if decision_day < 0 or not isinstance(uom, str) or not uom:
        raise ValueError("External service requires a nonnegative day and an explicit unit")
    available = Decimal(str(_component_quantity(available_qty, uom=uom, field="available stock")))
    pending, incoming = tuple(backlog), tuple(due)
    seen: set[str] = set()
    for row in pending + incoming:
        _identity(row.requirement_id, seen, "external remaining requirement")
        if not 0 <= _day(row.due_day, "external due day") <= decision_day:
            raise ValueError("Only current or overdue component demand can be physically consumed")
        _component_quantity(row.qty, uom=uom, field="remaining external demand")
    allocations, remaining = [], []
    for row in sorted(pending + incoming, key=lambda row: (row.due_day, row.requirement_id)):
        quantity = Decimal(str(row.qty))
        take = min(available, quantity)
        if take > 0:
            allocations.append(Requirement(row.requirement_id, row.due_day, float(take)))
        if quantity > take:
            remaining.append(Requirement(row.requirement_id, row.due_day, float(quantity - take)))
        available -= take
    return ExternalComponentService(
        tuple(allocations), tuple(remaining), fsum(row.qty for row in incoming),
        fsum(row.qty for row in pending), fsum(row.qty for row in allocations), float(available),
    )


@dataclass(frozen=True)
class FirmReceipt:
    receipt_id: str
    available_day: int
    qty: float
    state: str = "in_transit"


@dataclass(frozen=True)
class LotSizing:
    minimum: float = 0.0
    multiple: float = 0.0
    maximum: float | None = None
    integer: bool = False


@dataclass(frozen=True)
class Allocation:
    requirement_id: str
    supply_id: str
    supply_kind: str
    qty: float
    due_day: int
    available_day: int
    delay_days: int


@dataclass(frozen=True)
class OrderProposal:
    proposal_id: str
    release_day: int
    available_day: int
    requested_day: int
    qty: float


@dataclass(frozen=True)
class ProjectedBalance:
    day: int
    requirement_qty: float
    firm_receipt_qty: float
    proposed_receipt_qty: float
    before_proposals_qty: float
    after_proposals_qty: float


@dataclass(frozen=True)
class ProcurementGroup:
    group_id: str
    first_requirement_day: int
    window_end_day_exclusive: int
    physical_net_qty: float
    reserve_net_qty: float
    net_requirement_qty: float
    proposed_qty: float
    requirement_ids: tuple[str, ...]
    proposal_ids: tuple[str, ...]


@dataclass(frozen=True)
class DatedPlan:
    decision_day: int
    opening_available_qty: float
    commitment_allocations: tuple[Allocation, ...]
    allocations: tuple[Allocation, ...]
    proposals: tuple[OrderProposal, ...]
    balances: tuple[ProjectedBalance, ...]
    late_qty: float
    late_qty_days: float
    firm_late_qty: float
    proposed_qty: float
    unallocated_firm_qty: float
    closing_projected_qty: float
    procurement_groups: tuple[ProcurementGroup, ...] = ()


@dataclass(frozen=True)
class StockProtection:
    protection_id: str
    day: int
    minimum_qty: float


@dataclass(frozen=True)
class ProtectionBalance:
    day: int
    target_qty: float
    projected_qty: float
    shortfall_qty: float


@dataclass(frozen=True)
class ProtectedDatedPlan:
    plan: DatedPlan
    protection: tuple[ProtectionBalance, ...]
    planning_envelope_requirements: tuple[Requirement, ...]


@dataclass(frozen=True)
class SupplierOffer:
    supplier_id: str
    purchase_unit_cost: float
    currency: str
    uom: str
    lead_days: int
    lot_sizing: LotSizing = LotSizing()
    availability_by_release: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class SourcedProposal:
    proposal: OrderProposal
    supplier_id: str
    role: str
    reason: str
    backup_required_qty: float = 0.0


@dataclass(frozen=True)
class SourcedPlan:
    plan: DatedPlan
    proposals: tuple[SourcedProposal, ...]
    primary_available_day: int
    physical_shortage_before_primary_qty: float
    backup_proposed_qty: float
    retained_firm_qty: float
    bridge_surplus_qty: float


def _number(value: float, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite nonnegative quantity")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite nonnegative quantity") from exc
    if not isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a finite nonnegative quantity")
    return number


def _day(value: int, field: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{field} must be an integer day")
    return value


def _identity(value: str, seen: set[str], field: str) -> None:
    if not isinstance(value, str) or not value.strip() or value in seen:
        raise ValueError(f"{field} must be nonempty and unique")
    seen.add(value)


def _lot_bounds(policy: LotSizing) -> tuple[float, float, float | None]:
    if type(policy.integer) is not bool:
        raise ValueError("integer must be a boolean")
    minimum = _number(policy.minimum, "minimum")
    multiple = _number(policy.multiple, "multiple")
    maximum = None if policy.maximum is None else _number(policy.maximum, "maximum")
    if maximum is not None and (maximum == 0 or minimum > maximum):
        raise ValueError("maximum must be positive and at least minimum")
    if policy.integer:
        # Bounds and purchase multiples are physical; forecasts may be fractional.
        for value in (minimum, multiple, maximum):
            if value is not None and value != floor(value):
                raise ValueError("Physical UN lot bounds must be integers")
    if multiple:
        step = Decimal(str(multiple))
        minimum = _number(float(ceil(Decimal(str(minimum)) / step) * step), "rounded minimum")
        if maximum is not None:
            maximum = float(floor(Decimal(str(maximum)) / step) * step)
            if maximum == 0 or minimum > maximum:
                raise ValueError("No purchase lot satisfies the bounds and multiple")
    return minimum, multiple, maximum


def _allocate(requirements, supplies):
    """FIFO needs and earliest availability; inputs contain only local copies."""
    # Decimal conversion of the declared quantities avoids a ghost UN purchase
    # after subtracting thirty 0.1 forecasts from three physical units.
    pools = [[identity, day, Decimal(str(qty)), kind] for identity, day, qty, kind in supplies]
    pools.sort(key=lambda row: (row[1], row[0]))
    allocations, missing = [], []
    cursor = 0
    for requirement in requirements:
        remaining = Decimal(str(requirement.qty))
        while remaining > 0 and cursor < len(pools):
            supply = pools[cursor]
            if supply[2] <= 0:
                cursor += 1
                continue
            qty = min(remaining, supply[2])
            allocations.append(Allocation(
                requirement.requirement_id, supply[0], supply[3], float(qty),
                requirement.due_day, supply[1], max(0, supply[1] - requirement.due_day),
            ))
            remaining -= qty
            supply[2] -= qty
        if remaining > 0:
            # Keep the exact remainder until lot sizing. A float here can round
            # down (e.g. 2 - 0.9999999999999999) and leave a need uncovered.
            missing.append((requirement, remaining))
    return tuple(allocations), tuple(missing), pools


def plan_dated_requirements(
    *, decision_day: int, available_qty: float,
    requirements: Iterable[Requirement], firm_receipts: Iterable[FirmReceipt],
    lead_days: int, lot_sizing: LotSizing | None = None,
    grouping_days: int | None = None,
) -> DatedPlan:
    """Propose quantities not covered by stock/commitments and expose lateness.

    Requirements describe remaining needs, not repeated daily MPS signals.
    Firm receipts include each held or undelivered quantity exactly once, at its
    availability date. Receipts already available belong in available_qty.
    New proposals remain revocable until their release is physically executed.
    Lot maxima limit one order, not total daily manufacturing capacity.
    """
    decision_day = _day(decision_day, "decision_day")
    if grouping_days is not None and (_day(grouping_days, "grouping_days") < 0):
        raise ValueError("Procurement grouping days must be nonnegative")
    lead_days = _day(lead_days, "lead_days")
    if lead_days < 0:
        raise ValueError("lead_days must be nonnegative")
    available = _number(available_qty, "available_qty")
    policy = lot_sizing or LotSizing()
    minimum, multiple, maximum = _lot_bounds(policy)
    if policy.integer and available != floor(available):
        raise ValueError("Physical UN available stock must be integer")
    needs, receipts = tuple(requirements), tuple(firm_receipts)
    seen = set()
    for row in needs:
        _identity(row.requirement_id, seen, "requirement_id")
        _day(row.due_day, "due_day")
        _number(row.qty, "requirement qty")
    needs = tuple(sorted(needs, key=lambda row: (row.due_day, row.requirement_id)))
    seen = {"opening_stock"}
    supplies = [("opening_stock", decision_day, available, "available")]
    for row in receipts:
        _identity(row.receipt_id, seen, "receipt_id")
        _day(row.available_day, "available_day")
        if row.available_day < decision_day:
            raise ValueError("Past receipts must be reconciled with available stock")
        qty = _number(row.qty, "firm receipt qty")
        if policy.integer and qty != floor(qty):
            raise ValueError("Physical UN firm receipts must be integer")
        if row.state not in ("held", "in_transit", "confirmed"):
            raise ValueError("Firm receipt state must be held, in_transit or confirmed")
        supplies.append((row.receipt_id, row.available_day, qty, row.state))

    committed_allocations, missing, _ = _allocate(needs, supplies)
    proposals, procurement_groups = [], []
    surplus = Decimal(0)
    pending = deque(missing)
    while pending:
        requirement, remainder = pending.popleft()
        need = max(Decimal(0), remainder - surplus)
        surplus = max(Decimal(0), surplus - remainder)
        members = [(requirement, need)]
        window_end = requirement.due_day + max(1, grouping_days or 0)
        if grouping_days is not None:
            # Anchor at the first STILL uncovered need, after existing firm
            # receipts and earlier purchase-lot surplus. Never move that due
            # date or create a second consumption/safety requirement.
            if need <= 0:
                continue
            if grouping_days:
                while pending and pending[0][0].due_day < window_end:
                    member, quantity = pending.popleft()
                    members.append((member, quantity))
                    need += quantity
        net_requirement = need
        first_proposal = len(proposals)
        while need > 0:
            qty = max(need, Decimal(str(minimum)))
            if multiple:
                qty = ceil(qty / Decimal(str(multiple))) * Decimal(str(multiple))
            if policy.integer:
                qty = Decimal(ceil(qty))
            if maximum is not None:
                qty = min(qty, Decimal(str(maximum)))
            published_qty = _number(qty, "proposal qty")
            if Decimal(str(published_qty)) < qty:
                # The public engine interface uses floats. Represent a proposal
                # outward by at most one ULP, then use that SAME quantity for
                # netting and balances. Never erase a shortage with a tolerance
                # or turn floating-point dust into an extra physical UN lot.
                published_qty = _number(nextafter(published_qty, float("inf")), "proposal qty")
            qty = Decimal(str(published_qty))
            if qty <= 0:
                raise ValueError("Lot policy produced a zero purchase for a positive need")
            release = max(decision_day, requirement.due_day - lead_days)
            arrival = release + lead_days
            proposal_id = f"proposal:{len(proposals) + 1}"
            if proposal_id in seen:
                raise ValueError("Receipt id collides with a generated proposal id")
            proposals.append(OrderProposal(proposal_id, release, arrival, requirement.due_day, published_qty))
            surplus += max(Decimal(0), qty - need)
            need = max(Decimal(0), need - qty)
        if grouping_days is not None:
            grouped_proposals = proposals[first_proposal:]
            procurement_groups.append(ProcurementGroup(
                f"group:{len(procurement_groups) + 1}", requirement.due_day, window_end,
                float(sum((quantity for member, quantity in members if not member.requirement_id.startswith("reserve:")), Decimal(0))),
                float(sum((quantity for member, quantity in members if member.requirement_id.startswith("reserve:")), Decimal(0))),
                float(net_requirement), fsum(row.qty for row in grouped_proposals),
                tuple(member.requirement_id for member, _ in members),
                tuple(row.proposal_id for row in grouped_proposals),
            ))

    return _complete_plan(decision_day, available, needs, receipts, proposals, supplies, committed_allocations, procurement_groups)


def _complete_plan(decision_day, available, needs, receipts, proposals, supplies, committed_allocations, procurement_groups=()):
    # Minimum/multiple rounding may provide earlier surplus. Reallocate by actual
    # availability so lateness is not overstated when that surplus covers a need.
    all_supplies = supplies + [(p.proposal_id, p.available_day, p.qty, "proposal") for p in proposals]
    allocations, uncovered, leftovers = _allocate(needs, all_supplies)
    if uncovered:
        raise ArithmeticError("Proposed plan does not cover every remaining quantity")
    events: dict[int, list[list[float]]] = {decision_day: [[], [], []]}
    for row in needs:
        events.setdefault(max(decision_day, row.due_day), [[], [], []])[0].append(float(row.qty))
    for row in receipts:
        events.setdefault(row.available_day, [[], [], []])[1].append(float(row.qty))
    for row in proposals:
        events.setdefault(row.available_day, [[], [], []])[2].append(row.qty)
    balances = []
    before = after = Decimal(str(available))
    for day, amounts in sorted(events.items()):
        needed, firm, proposed = (sum((Decimal(str(value)) for value in group), Decimal(0)) for group in amounts)
        before += firm - needed
        after += firm + proposed - needed
        if not isfinite(before) or not isfinite(after):
            raise ValueError("Projected balance overflow")
        balances.append(ProjectedBalance(day, float(needed), float(firm), float(proposed), float(before), float(after)))
    return DatedPlan(
        decision_day, available, committed_allocations, allocations, tuple(proposals), tuple(balances),
        fsum(a.qty for a in allocations if a.delay_days),
        fsum(a.qty * a.delay_days for a in allocations),
        fsum(a.qty for a in allocations if a.delay_days and a.supply_kind in ("held", "in_transit", "confirmed")),
        fsum(p.qty for p in proposals),
        fsum(p[2] for p in leftovers if p[3] in ("held", "in_transit", "confirmed")),
        float(after),
        tuple(procurement_groups),
    )


def plan_with_stock_protection(
    *, decision_day: int, available_qty: float, requirements: Iterable[Requirement],
    firm_receipts: Iterable[FirmReceipt], lead_days: int,
    lot_sizing: LotSizing | None = None, protection: Iterable[StockProtection] = (),
) -> ProtectedDatedPlan:
    """Net a persistent inventory floor without turning it into consumption.

    A checkpoint sets the floor until the next checkpoint; it is zero before
    the first. The nondecreasing envelope max(cumulative physical needs+floor)
    determines procurement. Physical balances and allocations are reconstructed
    from the ORIGINAL needs and the same proposals. Late firm volume retains
    the existing no-duplicate-purchase contract; a floor may therefore be late.
    """
    needs, receipts, points = tuple(requirements), tuple(firm_receipts), tuple(protection)
    if not points:
        return ProtectedDatedPlan(plan_dated_requirements(
            decision_day=decision_day, available_qty=available_qty, requirements=needs,
            firm_receipts=receipts, lead_days=lead_days, lot_sizing=lot_sizing,
        ), (), ())
    _day(decision_day, "decision_day")
    seen, days = set(), set()
    for point in points:
        _identity(point.protection_id, seen, "protection_id")
        _day(point.day, "protection day")
        _number(point.minimum_qty, "protection minimum")
        if point.day < decision_day or point.day in days:
            raise ValueError("Protection checkpoints must have distinct nonpast days")
        days.add(point.day)
    points = tuple(sorted(points, key=lambda point: point.day))
    amounts = defaultdict(list)
    seen = set()
    for need in needs:
        _identity(need.requirement_id, seen, "requirement_id")
        _day(need.due_day, "due_day")
        _number(need.qty, "requirement qty")
        amounts[max(decision_day, need.due_day)].append(Decimal(str(need.qty)))
    levels = {point.day: Decimal(str(point.minimum_qty)) for point in points}
    cumulative, floor_qty, envelope = Decimal(0), Decimal(0), Decimal(0)
    virtual = []
    for event_day in sorted(set(amounts) | set(levels)):
        cumulative += sum(amounts.get(event_day, ()), Decimal(0))
        floor_qty = levels.get(event_day, floor_qty)
        next_envelope = max(envelope, cumulative + floor_qty)
        increment = next_envelope - envelope
        if increment:
            represented = float(increment)
            if Decimal(str(represented)) < increment:
                represented = nextafter(represented, float("inf"))
            virtual.append(Requirement(f"protection_envelope:{event_day}", event_day, represented))
        envelope = next_envelope
    net = plan_dated_requirements(
        decision_day=decision_day, available_qty=available_qty, requirements=virtual,
        firm_receipts=receipts, lead_days=lead_days, lot_sizing=lot_sizing,
    )
    physical = tuple(sorted(needs, key=lambda row: (row.due_day, row.requirement_id)))
    supplies = [("opening_stock", decision_day, available_qty, "available")] + [
        (row.receipt_id, row.available_day, row.qty, row.state) for row in receipts
    ]
    committed, _, _ = _allocate(physical, supplies)
    plan = _complete_plan(decision_day, available_qty, physical, receipts, net.proposals, supplies, committed)
    physical_balances = {row.day: row.after_proposals_qty for row in plan.balances}
    floor_qty, projected = Decimal(0), float(available_qty)
    audit = []
    for event_day in sorted(set(physical_balances) | set(levels)):
        floor_qty = levels.get(event_day, floor_qty)
        projected = physical_balances.get(event_day, projected)
        audit.append(ProtectionBalance(event_day, float(floor_qty), projected, max(0.0, float(floor_qty) - projected)))
    return ProtectedDatedPlan(plan, tuple(audit), tuple(virtual))


def plan_sourced_requirements(
    *, decision_day: int, available_qty: float,
    requirements: Iterable[Requirement], firm_receipts: Iterable[FirmReceipt],
    primary: SupplierOffer, backups: tuple[SupplierOffer, ...],
    protected_backup_receipt_ids: tuple[str, ...] = (),
) -> SourcedPlan:
    """Optional purchase policy, not an inferred industrial ERP algorithm.

    Keep commitments. A backup may bridge a *physical* requirement before the
    earliest new primary delivery, only when it improves that requirement's
    availability. Technical reserve requirements never trigger a backup. Net
    backup proposals before sizing new primary purchases. Firm late purchases
    are neither cancelled nor moved; the extra horizon balance is disclosed.
    Calendars describe nominal planning availability, not executed receipts.
    """
    decision_day = _day(decision_day, "decision_day")
    needs, receipts = tuple(requirements), tuple(firm_receipts)
    baseline = plan_dated_requirements(
        decision_day=decision_day, available_qty=available_qty, requirements=needs,
        firm_receipts=receipts, lead_days=primary.lead_days, lot_sizing=primary.lot_sizing,
    )
    needs = tuple(sorted(needs, key=lambda row: (row.due_day, row.requirement_id)))
    offers = (primary, *backups)
    seen, calendars, prices = set(), {}, {}
    for offer in offers:
        _identity(offer.supplier_id, seen, "supplier_id")
        prices[offer.supplier_id] = _number(offer.purchase_unit_cost, "purchase_unit_cost")
        if (not isinstance(offer.currency, str) or not offer.currency.strip()
                or not isinstance(offer.uom, str) or not offer.uom.strip()
                or offer.currency != primary.currency or offer.uom != primary.uom):
            raise ValueError("Supplier prices must use the same explicit currency and physical unit")
        if _day(offer.lead_days, "lead_days") < 0:
            raise ValueError("Supplier lead must be nonnegative")
        _lot_bounds(offer.lot_sizing)
        if offer.lot_sizing.integer != primary.lot_sizing.integer:
            raise ValueError("Supplier physical integer policies must agree")
        if prices[offer.supplier_id] < prices[primary.supplier_id]:
            raise ValueError("Confirmed primary must have the cheapest comparable purchase price")
        calendar = tuple(offer.availability_by_release)
        for index, (release, available) in enumerate(calendar):
            _day(release, "release day")
            _day(available, "available day")
            if (release < decision_day or available < release
                    or (index and (release != calendar[index - 1][0] + 1 or available < calendar[index - 1][1]))):
                raise ValueError("Supplier calendar must have consecutive releases and monotone availability")
        if calendar and calendar[0][0] != decision_day:
            raise ValueError("Supplier calendar must start at the decision day")
        if calendar and calendar[-1][0] < max((r.due_day for r in needs), default=decision_day):
            raise ValueError("Supplier calendar must cover all future requirement dates")
        calendars[offer.supplier_id] = calendar
    protected = set(protected_backup_receipt_ids)
    if (len(protected) != len(protected_backup_receipt_ids)
            or not protected <= {row.receipt_id for row in receipts}):
        raise ValueError("Protected backup identities must reference unique existing firm receipts")

    def dates(offer, due):
        calendar = calendars[offer.supplier_id]
        if not calendar:
            release = max(decision_day, due - offer.lead_days)
            return release, release + offer.lead_days
        index = bisect_right([row[1] for row in calendar], due) - 1
        return calendar[max(0, index)]

    def calendar_proposals(plan, offer, prefix):
        return tuple(OrderProposal(
            f"{prefix}:{index}", *dates(offer, row.requested_day), row.requested_day, row.qty,
        ) for index, row in enumerate(plan.proposals, 1))

    primary_day = dates(primary, decision_day)[1]
    baseline_proposals = calendar_proposals(baseline, primary, "sourcing:primary")
    physical_needs = tuple(row for row in needs if not row.requirement_id.startswith("reserve:"))
    supplies = [("opening_stock", decision_day, available_qty, "available")] + [
        (row.receipt_id, row.available_day, row.qty, row.state) for row in receipts
    ]
    physical_supplies = supplies + [(p.proposal_id, p.available_day, p.qty, "proposal") for p in baseline_proposals]
    initial_allocations, missing, _ = _allocate(physical_needs, physical_supplies)
    if missing:
        raise ArithmeticError("Primary plan must cover the physical requirements")
    initial_shortage = fsum(a.qty for a in initial_allocations if a.due_day < primary_day and a.delay_days)
    backup_rows = []
    # Cheapest confirmed backup first. Each newly proposed lot is netted before
    # inspecting the next requirement; its rounding surplus is not bought again.
    for offer in sorted(backups, key=lambda row: (prices[row.supplier_id], dates(row, decision_day)[1], row.supplier_id)):
        for need in physical_needs:
            if need.due_day >= primary_day:
                continue
            release, arrival = dates(offer, need.due_day)
            allocations, _, _ = _allocate(physical_needs, physical_supplies)
            bridge = fsum(a.qty for a in allocations if a.requirement_id == need.requirement_id
                          and a.available_day > max(need.due_day, arrival) and a.supply_id not in protected)
            if bridge <= 0:
                continue
            sized = plan_dated_requirements(
                decision_day=decision_day, available_qty=0.0,
                requirements=(Requirement(need.requirement_id, need.due_day, bridge),), firm_receipts=(),
                lead_days=offer.lead_days, lot_sizing=offer.lot_sizing,
            )
            for row in sized.proposals:
                proposal = OrderProposal(f"sourcing:backup:{len(backup_rows) + 1}", release, arrival, need.due_day, row.qty)
                backup_rows.append(SourcedProposal(proposal, offer.supplier_id, "backup",
                                                   "physical_shortage_before_primary", bridge))
                physical_supplies.append((proposal.proposal_id, arrival, proposal.qty, "proposal"))
    # Temporary netting does not turn an unexecuted backup into a firm order in
    # the returned plan. It only prevents a second new primary purchase for it.
    temporary_firms = receipts + tuple(FirmReceipt(row.proposal.proposal_id, row.proposal.available_day,
                                                  row.proposal.qty, "confirmed") for row in backup_rows)
    primary_net = plan_dated_requirements(
        decision_day=decision_day, available_qty=available_qty, requirements=needs,
        firm_receipts=temporary_firms, lead_days=primary.lead_days, lot_sizing=primary.lot_sizing,
    )
    primary_proposals = calendar_proposals(primary_net, primary, "sourcing:primary")
    sourced = tuple(backup_rows) + tuple(SourcedProposal(row, primary.supplier_id, "primary",
                                                        "cheapest_confirmed_purchase_price") for row in primary_proposals)
    proposals = tuple(row.proposal for row in sourced)
    ids = {row[0] for row in supplies}
    if any(row.proposal_id in ids for row in proposals):
        raise ValueError("Firm receipt id collides with a sourced proposal id")
    # A technical reserve cannot absorb a rescue before its physical purpose.
    # Balances still retain every reserve event separately at its original date.
    allocation_needs = physical_needs + tuple(row for row in needs if row.requirement_id.startswith("reserve:"))
    commitments, _, _ = _allocate(allocation_needs, supplies)
    plan = _complete_plan(decision_day, float(available_qty), allocation_needs, receipts, proposals, supplies, commitments)
    return SourcedPlan(
        plan, sourced, primary_day, initial_shortage, fsum(row.proposal.qty for row in backup_rows),
        fsum(row.qty for row in receipts), max(0.0, plan.proposed_qty - baseline.proposed_qty),
    )
