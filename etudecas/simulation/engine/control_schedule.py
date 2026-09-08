"""Typed daily control schedules for the canonical simulation engine.

The schedule is deliberately independent from the simulation loop.  It parses
and validates a CSV once, then resolves the controls that apply to one measured
simulation day and one operational scope.  Measured days are zero-based; warm-up
day handling remains the responsibility of the engine integration.

Scopes use exact identifiers.  A blank scope is global.  More-specific rows
override less-specific rows field by field, so a targeted row can change one
lever while inheriting the other levers from a global row.  Equal-specificity
rows that could both match the same request are rejected as ambiguous.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import math
from pathlib import Path
import re
from typing import Any, Collection, Iterable, Literal, Mapping


SCOPE_FIELDS: tuple[str, ...] = (
    "node_id",
    "supplier_id",
    "item_id",
    "dst_node_id",
)

ACTION_FIELDS: tuple[str, ...] = (
    "order_multiplier",
    "safety_stock_multiplier",
    "production_target_multiplier",
    "capacity_multiplier",
    "external_procurement_multiplier",
    "expedite_level",
    "lead_time_adjustment_days",
    "priority_weight",
)

CONTROL_SCHEDULE_COLUMNS: tuple[str, ...] = (
    "day",
    "policy",
    *SCOPE_FIELDS,
    *ACTION_FIELDS,
)

BoundStatus = Literal["none", "lower", "upper"]
ControlNumber = float | int


class ControlScheduleError(ValueError):
    """Raised when a control schedule cannot be interpreted safely."""


@dataclass(frozen=True)
class ControlBound:
    """Engineering safety rail for one control lever."""

    lower: ControlNumber
    upper: ControlNumber
    neutral: ControlNumber
    integer: bool = False
    unit: str = "dimensionless"

    def apply(self, requested: ControlNumber) -> tuple[ControlNumber, BoundStatus]:
        if requested < self.lower:
            return self.lower, "lower"
        if requested > self.upper:
            return self.upper, "upper"
        return requested, "none"


# These are safety rails, not calibrated policy recommendations.  They are kept
# in one public mapping so research campaigns can report the exact contract.
CONTROL_BOUNDS: Mapping[str, ControlBound] = {
    "order_multiplier": ControlBound(0.0, 2.0, 1.0),
    "safety_stock_multiplier": ControlBound(0.0, 3.0, 1.0),
    "production_target_multiplier": ControlBound(0.0, 2.0, 1.0),
    "capacity_multiplier": ControlBound(0.0, 1.5, 1.0),
    "external_procurement_multiplier": ControlBound(0.0, 3.0, 1.0),
    "expedite_level": ControlBound(0.0, 1.0, 0.0),
    "lead_time_adjustment_days": ControlBound(
        -30,
        90,
        0,
        integer=True,
        unit="measured days",
    ),
    "priority_weight": ControlBound(0.0, 10.0, 1.0),
}


@dataclass(frozen=True)
class ControlCatalog:
    """Optional allow-lists used to reject identifiers unknown to a graph.

    ``None`` means that an allow-list is unavailable and the corresponding
    identifier is only validated syntactically.  An empty collection means that
    no targeted identifier is valid for that dimension.
    """

    node_ids: Collection[str] | None = None
    supplier_ids: Collection[str] | None = None
    item_ids: Collection[str] | None = None
    dst_node_ids: Collection[str] | None = None
    policies: Collection[str] | None = None


@dataclass(frozen=True)
class ControlScheduleRow:
    """One validated CSV row."""

    day: int
    policy: str = ""
    node_id: str = ""
    supplier_id: str = ""
    item_id: str = ""
    dst_node_id: str = ""
    requested: Mapping[str, ControlNumber] = field(default_factory=dict)
    effective: Mapping[str, ControlNumber] = field(default_factory=dict)
    bound: Mapping[str, BoundStatus] = field(default_factory=dict)
    source_line: int = 0

    @property
    def specificity(self) -> int:
        return sum(bool(getattr(self, name)) for name in SCOPE_FIELDS)

    @property
    def is_global(self) -> bool:
        return self.specificity == 0

    @property
    def scope_key(self) -> tuple[str, str, str, str]:
        return tuple(getattr(self, name) for name in SCOPE_FIELDS)  # type: ignore[return-value]

    def matches(self, scope: Mapping[str, str]) -> bool:
        return all(
            not getattr(self, name) or getattr(self, name) == scope[name]
            for name in SCOPE_FIELDS
        )


@dataclass(frozen=True)
class ResolvedAction:
    """Requested and effective value selected for one lever."""

    name: str
    requested: ControlNumber
    effective: ControlNumber
    bound: BoundStatus = "none"
    source_line: int | None = None
    policy: str = ""
    node_id: str = ""
    supplier_id: str = ""
    item_id: str = ""
    dst_node_id: str = ""
    specificity: int = 0

    @property
    def applied(self) -> bool:
        return self.source_line is not None


@dataclass(frozen=True)
class ResolvedControl:
    """Effective controls for one day and one operational scope."""

    day: int
    node_id: str = ""
    supplier_id: str = ""
    item_id: str = ""
    dst_node_id: str = ""
    order_multiplier: float = 1.0
    safety_stock_multiplier: float = 1.0
    production_target_multiplier: float = 1.0
    capacity_multiplier: float = 1.0
    external_procurement_multiplier: float = 1.0
    expedite_level: float = 0.0
    lead_time_adjustment_days: int = 0
    priority_weight: float = 1.0
    metadata: tuple[ResolvedAction, ...] = ()
    matched_source_lines: tuple[int, ...] = ()

    @property
    def enabled(self) -> bool:
        return any(action.applied for action in self.metadata)

    @property
    def policies(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                action.policy
                for action in self.metadata
                if action.applied and action.policy
            )
        )

    @property
    def policy(self) -> str:
        return "|".join(self.policies)

    @property
    def requested(self) -> dict[str, ControlNumber]:
        return {action.name: action.requested for action in self.metadata}

    @property
    def effective(self) -> dict[str, ControlNumber]:
        return {action.name: action.effective for action in self.metadata}

    @property
    def bound(self) -> dict[str, BoundStatus]:
        return {action.name: action.bound for action in self.metadata}

    @property
    def source_lines(self) -> dict[str, int | None]:
        return {action.name: action.source_line for action in self.metadata}

    def action(self, name: str) -> ResolvedAction:
        try:
            return next(action for action in self.metadata if action.name == name)
        except StopIteration as exc:
            raise KeyError(name) from exc

    def to_ledger_rows(
        self,
        *,
        include_neutral: bool = False,
        status: str = "resolved",
        extra: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return JSON/CSV-compatible audit rows, one row per resolved lever."""

        rows: list[dict[str, Any]] = []
        for action in self.metadata:
            if not include_neutral and not action.applied:
                continue
            row: dict[str, Any] = {
                "day": self.day,
                "resolved_node_id": self.node_id,
                "resolved_supplier_id": self.supplier_id,
                "resolved_item_id": self.item_id,
                "resolved_dst_node_id": self.dst_node_id,
                "policy": action.policy,
                "action": action.name,
                "requested": action.requested,
                "effective": action.effective,
                "bound": action.bound,
                "status": status,
                "source_line": action.source_line if action.source_line is not None else "",
                "scope_type": "global" if action.specificity == 0 else "targeted",
                "scope_specificity": action.specificity,
                "source_node_id": action.node_id,
                "source_supplier_id": action.supplier_id,
                "source_item_id": action.item_id,
                "source_dst_node_id": action.dst_node_id,
                "matched_source_lines": ";".join(str(line) for line in self.matched_source_lines),
            }
            if extra:
                row.update(extra)
            rows.append(row)
        return rows


@dataclass(frozen=True)
class ControlSchedule:
    """Validated schedule indexed by measured day."""

    rows: tuple[ControlScheduleRow, ...] = ()
    warnings: tuple[str, ...] = ()
    path: Path | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.rows)

    def resolve(
        self,
        day: int,
        node_id: str = "",
        supplier_id: str = "",
        item_id: str = "",
        dst_node_id: str = "",
    ) -> ResolvedControl:
        """Resolve controls for one zero-based measured day and exact scope."""

        if isinstance(day, bool) or not isinstance(day, int) or day < 0:
            raise ControlScheduleError(
                f"resolve(day=...) requires a zero-based non-negative integer, got {day!r}."
            )
        scope = {
            "node_id": _normalize_identifier(node_id),
            "supplier_id": _normalize_identifier(supplier_id),
            "item_id": _normalize_identifier(item_id),
            "dst_node_id": _normalize_identifier(dst_node_id),
        }
        matching = tuple(
            row
            for row in self.rows
            if row.day == day and row.matches(scope)
        )
        metadata: list[ResolvedAction] = []
        for action_name in ACTION_FIELDS:
            candidates = [
                row
                for row in matching
                if action_name in row.effective
            ]
            if not candidates:
                neutral = CONTROL_BOUNDS[action_name].neutral
                metadata.append(
                    ResolvedAction(
                        name=action_name,
                        requested=neutral,
                        effective=neutral,
                    )
                )
                continue
            specificity = max(row.specificity for row in candidates)
            winners = [row for row in candidates if row.specificity == specificity]
            if len(winners) != 1:
                lines = ", ".join(str(row.source_line) for row in winners)
                raise ControlScheduleError(
                    f"Ambiguous {action_name!r} resolution for measured day {day}: "
                    f"equally specific source lines {lines}."
                )
            source = winners[0]
            metadata.append(
                ResolvedAction(
                    name=action_name,
                    requested=source.requested[action_name],
                    effective=source.effective[action_name],
                    bound=source.bound[action_name],
                    source_line=source.source_line,
                    policy=source.policy,
                    node_id=source.node_id,
                    supplier_id=source.supplier_id,
                    item_id=source.item_id,
                    dst_node_id=source.dst_node_id,
                    specificity=source.specificity,
                )
            )

        values = {action.name: action.effective for action in metadata}
        return ResolvedControl(
            day=day,
            **scope,
            order_multiplier=float(values["order_multiplier"]),
            safety_stock_multiplier=float(values["safety_stock_multiplier"]),
            production_target_multiplier=float(values["production_target_multiplier"]),
            capacity_multiplier=float(values["capacity_multiplier"]),
            external_procurement_multiplier=float(values["external_procurement_multiplier"]),
            expedite_level=float(values["expedite_level"]),
            lead_time_adjustment_days=int(values["lead_time_adjustment_days"]),
            priority_weight=float(values["priority_weight"]),
            metadata=tuple(metadata),
            matched_source_lines=tuple(row.source_line for row in matching),
        )


CONTROL_LEDGER_COLUMNS: tuple[str, ...] = (
    "day",
    "resolved_node_id",
    "resolved_supplier_id",
    "resolved_item_id",
    "resolved_dst_node_id",
    "policy",
    "action",
    "requested",
    "effective",
    "bound",
    "status",
    "source_line",
    "scope_type",
    "scope_specificity",
    "source_node_id",
    "source_supplier_id",
    "source_item_id",
    "source_dst_node_id",
    "matched_source_lines",
    # Stable execution-evidence schema.  These fields remain empty when a
    # scheduled action never reaches a physical execution stage; their
    # presence must not depend on which kinds of rows happened to be emitted.
    "action_stage",
    "edge_id",
    "quantity_uom",
    "executed_control_volume_qty",
)


def _normalize_identifier(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_number(text: str, *, action_name: str, line_number: int) -> ControlNumber:
    bound = CONTROL_BOUNDS[action_name]
    if bound.integer:
        if not re.fullmatch(r"[+-]?\d+", text):
            raise ControlScheduleError(
                f"Line {line_number}: {action_name} must be an integer in "
                f"{bound.unit}, got {text!r}."
            )
        value: ControlNumber = int(text)
    else:
        try:
            value = float(text)
        except ValueError as exc:
            raise ControlScheduleError(
                f"Line {line_number}: {action_name} must be numeric, got {text!r}."
            ) from exc
    if not math.isfinite(float(value)):
        raise ControlScheduleError(
            f"Line {line_number}: {action_name} must be finite, got {text!r}."
        )
    return value


def _parse_day(text: str, *, line_number: int) -> int:
    if not re.fullmatch(r"\+?\d+", text):
        raise ControlScheduleError(
            f"Line {line_number}: day must be a zero-based non-negative integer, got {text!r}."
        )
    return int(text)


def _compatible_scopes(left: ControlScheduleRow, right: ControlScheduleRow) -> bool:
    return all(
        not getattr(left, name)
        or not getattr(right, name)
        or getattr(left, name) == getattr(right, name)
        for name in SCOPE_FIELDS
    )


def _validate_catalog(
    row: ControlScheduleRow,
    *,
    catalog: ControlCatalog,
) -> None:
    checks: tuple[tuple[str, Collection[str] | None], ...] = (
        ("node_id", catalog.node_ids),
        ("supplier_id", catalog.supplier_ids),
        ("item_id", catalog.item_ids),
        (
            "dst_node_id",
            catalog.dst_node_ids if catalog.dst_node_ids is not None else catalog.node_ids,
        ),
        ("policy", catalog.policies),
    )
    for name, allowed in checks:
        value = getattr(row, name)
        if value and allowed is not None and value not in allowed:
            raise ControlScheduleError(
                f"Line {row.source_line}: unknown {name} {value!r}."
            )


def _validate_action_scope_compatibility(
    row: ControlScheduleRow,
    *,
    catalog: ControlCatalog | None = None,
) -> None:
    """Reject scopes that the canonical execution stage cannot resolve.

    The rule is intentionally conservative: it only rejects combinations that
    are structurally impossible in the current engine.  Other targeted scopes
    remain auditable at run time through ``scheduled_not_resolved``.
    """

    if (
        "production_target_multiplier" in row.requested
        and (row.supplier_id or row.dst_node_id)
    ):
        raise ControlScheduleError(
            f"Line {row.source_line}: production_target_multiplier supports "
            "node_id and item_id scopes only; supplier_id/dst_node_id cannot "
            "match a production process."
        )
    if (
        "safety_stock_multiplier" in row.requested
        and row.supplier_id
    ):
        raise ControlScheduleError(
            f"Line {row.source_line}: safety_stock_multiplier cannot use "
            "supplier_id; safety stock is resolved on destination node/item."
        )
    if (
        "capacity_multiplier" in row.requested
        and row.node_id
        and not row.supplier_id
        and catalog is not None
        and catalog.supplier_ids is not None
        and row.node_id in catalog.supplier_ids
    ):
        raise ControlScheduleError(
            f"Line {row.source_line}: capacity_multiplier cannot target "
            f"supplier {row.node_id!r} through node_id alone; use "
            "supplier_id so the supplier lane execution can resolve it."
        )


def _validate_row_relationships(rows: Iterable[ControlScheduleRow]) -> None:
    by_day: dict[int, list[ControlScheduleRow]] = {}
    for row in rows:
        by_day.setdefault(row.day, []).append(row)
    for day, day_rows in by_day.items():
        exact_scopes: dict[tuple[str, str, str, str], ControlScheduleRow] = {}
        for row in day_rows:
            prior = exact_scopes.get(row.scope_key)
            if prior is not None:
                raise ControlScheduleError(
                    f"Duplicate control scope for measured day {day} on lines "
                    f"{prior.source_line} and {row.source_line}."
                )
            exact_scopes[row.scope_key] = row
        for index, left in enumerate(day_rows):
            for right in day_rows[index + 1 :]:
                if (
                    left.specificity == right.specificity
                    and _compatible_scopes(left, right)
                ):
                    raise ControlScheduleError(
                        f"Ambiguous control scopes for measured day {day} on lines "
                        f"{left.source_line} and {right.source_line}: both can match "
                        f"the same request with specificity {left.specificity}."
                    )


def load_control_schedule(
    path: Path | str | None,
    *,
    catalog: ControlCatalog | None = None,
) -> ControlSchedule:
    """Load and validate a control schedule.

    Multipliers, ``expedite_level`` and ``priority_weight`` are dimensionless.
    ``lead_time_adjustment_days`` is an integer number of measured days.  Values
    outside :data:`CONTROL_BOUNDS` are clamped and recorded as warnings; invalid,
    non-finite, duplicate, unknown or ambiguous input is rejected.
    """

    if path is None:
        return ControlSchedule()
    schedule_path = Path(path)
    if not schedule_path.exists():
        raise ControlScheduleError(f"Control schedule does not exist: {schedule_path}")
    if not schedule_path.is_file():
        raise ControlScheduleError(f"Control schedule is not a file: {schedule_path}")

    rows: list[ControlScheduleRow] = []
    warnings: list[str] = []
    try:
        stream = schedule_path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise ControlScheduleError(
            f"Cannot open control schedule {schedule_path}: {exc}"
        ) from exc

    try:
        with stream:
            reader = csv.DictReader(stream)
            raw_headers = reader.fieldnames
            if raw_headers is None:
                raise ControlScheduleError(
                    f"Control schedule {schedule_path} is empty and has no CSV header."
                )
            headers = [str(name).strip() for name in raw_headers]
            if any(not name for name in headers):
                raise ControlScheduleError("Control schedule contains an empty column name.")
            duplicates = sorted({name for name in headers if headers.count(name) > 1})
            if duplicates:
                raise ControlScheduleError(
                    "Control schedule contains duplicate columns: "
                    + ", ".join(duplicates)
                )
            unknown = sorted(set(headers) - set(CONTROL_SCHEDULE_COLUMNS))
            if unknown:
                raise ControlScheduleError(
                    "Control schedule contains unknown columns: "
                    + ", ".join(unknown)
                )
            if "day" not in headers:
                raise ControlScheduleError("Control schedule requires a 'day' column.")
            if not set(headers).intersection(ACTION_FIELDS):
                raise ControlScheduleError(
                    "Control schedule requires at least one control action column."
                )
            reader.fieldnames = headers

            for raw in reader:
                line_number = reader.line_num
                if None in raw:
                    raise ControlScheduleError(
                        f"Line {line_number}: more values than CSV columns."
                    )
                cells = {
                    str(name): "" if value is None else str(value).strip()
                    for name, value in raw.items()
                }
                if not any(cells.values()):
                    continue
                day_text = cells.get("day", "")
                if not day_text:
                    raise ControlScheduleError(f"Line {line_number}: day is required.")
                day = _parse_day(day_text, line_number=line_number)
                requested: dict[str, ControlNumber] = {}
                effective: dict[str, ControlNumber] = {}
                applied_bounds: dict[str, BoundStatus] = {}
                for action_name in ACTION_FIELDS:
                    text = cells.get(action_name, "")
                    if not text:
                        continue
                    value = _parse_number(
                        text,
                        action_name=action_name,
                        line_number=line_number,
                    )
                    bounded, bound_status = CONTROL_BOUNDS[action_name].apply(value)
                    requested[action_name] = value
                    effective[action_name] = bounded
                    applied_bounds[action_name] = bound_status
                    if bound_status != "none":
                        spec = CONTROL_BOUNDS[action_name]
                        warnings.append(
                            f"Line {line_number}: {action_name} requested {value} "
                            f"outside [{spec.lower}, {spec.upper}]; "
                            f"effective={bounded} ({bound_status} bound)."
                        )
                if not requested:
                    raise ControlScheduleError(
                        f"Line {line_number}: at least one control action value is required."
                    )
                row = ControlScheduleRow(
                    day=day,
                    policy=cells.get("policy", ""),
                    node_id=cells.get("node_id", ""),
                    supplier_id=cells.get("supplier_id", ""),
                    item_id=cells.get("item_id", ""),
                    dst_node_id=cells.get("dst_node_id", ""),
                    requested=requested,
                    effective=effective,
                    bound=applied_bounds,
                    source_line=line_number,
                )
                if catalog is not None:
                    _validate_catalog(row, catalog=catalog)
                _validate_action_scope_compatibility(
                    row,
                    catalog=catalog,
                )
                rows.append(row)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ControlScheduleError(
            f"Cannot parse control schedule {schedule_path}: {exc}"
        ) from exc

    _validate_row_relationships(rows)
    if not rows:
        warnings.append("Control schedule contains no action rows; controls are disabled.")
    return ControlSchedule(
        rows=tuple(rows),
        warnings=tuple(warnings),
        path=schedule_path,
    )


def serialize_control_ledger(
    resolutions: ResolvedControl | Iterable[ResolvedControl],
    *,
    include_neutral: bool = False,
    status: str = "resolved",
) -> list[dict[str, Any]]:
    """Serialize one or more resolutions into flat audit rows."""

    if isinstance(resolutions, ResolvedControl):
        values: Iterable[ResolvedControl] = (resolutions,)
    else:
        values = resolutions
    rows: list[dict[str, Any]] = []
    for resolved in values:
        rows.extend(
            resolved.to_ledger_rows(
                include_neutral=include_neutral,
                status=status,
            )
        )
    return rows


def write_control_ledger_csv(
    path: Path | str,
    resolutions: ResolvedControl | Iterable[ResolvedControl],
    *,
    include_neutral: bool = False,
    status: str = "resolved",
) -> Path:
    """Write resolved control metadata to a stable CSV ledger."""

    ledger_path = Path(path)
    rows = serialize_control_ledger(
        resolutions,
        include_neutral=include_neutral,
        status=status,
    )
    extra_columns = sorted(
        {
            name
            for row in rows
            for name in row
            if name not in CONTROL_LEDGER_COLUMNS
        }
    )
    columns = [*CONTROL_LEDGER_COLUMNS, *extra_columns]
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return ledger_path


__all__ = [
    "ACTION_FIELDS",
    "CONTROL_BOUNDS",
    "CONTROL_LEDGER_COLUMNS",
    "CONTROL_SCHEDULE_COLUMNS",
    "SCOPE_FIELDS",
    "ControlBound",
    "ControlCatalog",
    "ControlSchedule",
    "ControlScheduleError",
    "ControlScheduleRow",
    "ResolvedAction",
    "ResolvedControl",
    "load_control_schedule",
    "serialize_control_ledger",
    "write_control_ledger_csv",
]
