"""Strict measured-day demand perturbations for frequency identification.

The CSV is intentionally narrow: each row targets one exact demand pair on one
zero-based measured day.  Warm-up indexing is owned by the engine integration,
which only calls :meth:`DemandPerturbationSchedule.apply` after the measured
J0 boundary has been captured.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Collection, Mapping


DEMAND_PERTURBATION_COLUMNS: tuple[str, ...] = (
    "day",
    "node_id",
    "item_id",
    "demand_multiplier",
)

DEMAND_PERTURBATION_AUDIT_COLUMNS: tuple[str, ...] = (
    "day",
    "node_id",
    "item_id",
    "demand_multiplier",
    "base_demand_qty",
    "perturbed_demand_qty",
    "demand_delta_qty",
    "source_line",
    "status",
)

DEMAND_MULTIPLIER_MIN = 0.5
DEMAND_MULTIPLIER_MAX = 1.5


class DemandPerturbationError(ValueError):
    """Raised when an excitation CSV is not safe to apply."""


@dataclass(frozen=True)
class DemandPerturbationRow:
    """One validated excitation of one physical demand pair."""

    day: int
    node_id: str
    item_id: str
    demand_multiplier: float
    source_line: int

    @property
    def pair(self) -> tuple[str, str]:
        return (self.node_id, self.item_id)


@dataclass(frozen=True)
class DemandPerturbationSchedule:
    """Validated exact-scope perturbations indexed by measured day and pair."""

    rows: tuple[DemandPerturbationRow, ...] = ()
    path: Path | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.rows)

    def row_for(
        self,
        day: int,
        pair: tuple[str, str],
    ) -> DemandPerturbationRow | None:
        for row in self.rows:
            if row.day == day and row.pair == pair:
                return row
        return None

    def rows_for_day(self, day: int) -> tuple[DemandPerturbationRow, ...]:
        return tuple(row for row in self.rows if row.day == day)

    def apply(
        self,
        day: int,
        demand_by_pair: Mapping[tuple[str, str], float],
    ) -> dict[tuple[str, str], float]:
        """Return a copy with the measured-day multipliers applied exactly once."""

        result = dict(demand_by_pair)
        for row in self.rows_for_day(day):
            result[row.pair] = (
                max(0.0, float(demand_by_pair.get(row.pair, 0.0)))
                * row.demand_multiplier
            )
        return result


def _parse_day(text: str, *, line_number: int, measured_days: int) -> int:
    if not re.fullmatch(r"\+?\d+", text):
        raise DemandPerturbationError(
            f"Line {line_number}: day must be a zero-based non-negative "
            f"measured-day integer, got {text!r}."
        )
    day = int(text)
    if day >= measured_days:
        raise DemandPerturbationError(
            f"Line {line_number}: measured day {day} is outside this run's "
            f"horizon [0, {measured_days - 1}]."
        )
    return day


def _parse_multiplier(text: str, *, line_number: int) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise DemandPerturbationError(
            f"Line {line_number}: demand_multiplier must be numeric, got {text!r}."
        ) from exc
    if not math.isfinite(value):
        raise DemandPerturbationError(
            f"Line {line_number}: demand_multiplier must be finite, got {text!r}."
        )
    if not DEMAND_MULTIPLIER_MIN <= value <= DEMAND_MULTIPLIER_MAX:
        raise DemandPerturbationError(
            f"Line {line_number}: demand_multiplier {value} is outside "
            f"[{DEMAND_MULTIPLIER_MIN}, {DEMAND_MULTIPLIER_MAX}]."
        )
    return value


def load_demand_perturbation_schedule(
    path: Path | str | None,
    *,
    demand_pairs: Collection[tuple[str, str]],
    measured_days: int,
) -> DemandPerturbationSchedule:
    """Load a strict four-column excitation schedule.

    Identifiers must match an exact demand ``(node_id, item_id)`` pair from the
    selected scenario.  Duplicate pair/day rows, unknown columns, non-finite
    values and out-of-run days are rejected instead of being silently ignored.
    """

    if path is None:
        return DemandPerturbationSchedule()
    schedule_path = Path(path)
    if not schedule_path.exists():
        raise DemandPerturbationError(
            f"Demand perturbation CSV does not exist: {schedule_path}"
        )
    if not schedule_path.is_file():
        raise DemandPerturbationError(
            f"Demand perturbation CSV is not a file: {schedule_path}"
        )
    if isinstance(measured_days, bool) or int(measured_days) <= 0:
        raise DemandPerturbationError(
            f"measured_days must be a positive integer, got {measured_days!r}."
        )

    known_pairs = {
        (str(node_id), str(item_id))
        for node_id, item_id in demand_pairs
    }
    rows: list[DemandPerturbationRow] = []
    seen: dict[tuple[int, str, str], int] = {}
    try:
        stream = schedule_path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise DemandPerturbationError(
            f"Cannot open demand perturbation CSV {schedule_path}: {exc}"
        ) from exc

    try:
        with stream:
            reader = csv.DictReader(stream)
            raw_headers = reader.fieldnames
            if raw_headers is None:
                raise DemandPerturbationError(
                    f"Demand perturbation CSV {schedule_path} is empty and has no header."
                )
            headers = [str(name).strip() for name in raw_headers]
            if any(not name for name in headers):
                raise DemandPerturbationError(
                    "Demand perturbation CSV contains an empty column name."
                )
            duplicate_headers = sorted(
                {name for name in headers if headers.count(name) > 1}
            )
            if duplicate_headers:
                raise DemandPerturbationError(
                    "Demand perturbation CSV contains duplicate columns: "
                    + ", ".join(duplicate_headers)
                )
            missing = sorted(set(DEMAND_PERTURBATION_COLUMNS) - set(headers))
            unknown = sorted(set(headers) - set(DEMAND_PERTURBATION_COLUMNS))
            if missing or unknown:
                details: list[str] = []
                if missing:
                    details.append("missing: " + ", ".join(missing))
                if unknown:
                    details.append("unknown: " + ", ".join(unknown))
                raise DemandPerturbationError(
                    "Demand perturbation CSV requires exactly "
                    + ",".join(DEMAND_PERTURBATION_COLUMNS)
                    + " ("
                    + "; ".join(details)
                    + ")."
                )
            reader.fieldnames = headers

            for raw in reader:
                line_number = reader.line_num
                if None in raw:
                    raise DemandPerturbationError(
                        f"Line {line_number}: more values than CSV columns."
                    )
                cells = {
                    str(name): "" if value is None else str(value).strip()
                    for name, value in raw.items()
                }
                if not any(cells.values()):
                    continue
                missing_cells = [
                    name
                    for name in DEMAND_PERTURBATION_COLUMNS
                    if not cells.get(name, "")
                ]
                if missing_cells:
                    raise DemandPerturbationError(
                        f"Line {line_number}: required value(s) missing: "
                        + ", ".join(missing_cells)
                        + "."
                    )
                day = _parse_day(
                    cells["day"],
                    line_number=line_number,
                    measured_days=int(measured_days),
                )
                pair = (cells["node_id"], cells["item_id"])
                if pair not in known_pairs:
                    raise DemandPerturbationError(
                        f"Line {line_number}: unknown demand pair "
                        f"node_id={pair[0]!r}, item_id={pair[1]!r}."
                    )
                key = (day, *pair)
                prior_line = seen.get(key)
                if prior_line is not None:
                    raise DemandPerturbationError(
                        f"Duplicate demand perturbation for measured day {day}, "
                        f"node_id={pair[0]!r}, item_id={pair[1]!r} on lines "
                        f"{prior_line} and {line_number}."
                    )
                seen[key] = line_number
                rows.append(
                    DemandPerturbationRow(
                        day=day,
                        node_id=pair[0],
                        item_id=pair[1],
                        demand_multiplier=_parse_multiplier(
                            cells["demand_multiplier"],
                            line_number=line_number,
                        ),
                        source_line=line_number,
                    )
                )
    except (OSError, UnicodeError, csv.Error) as exc:
        raise DemandPerturbationError(
            f"Cannot parse demand perturbation CSV {schedule_path}: {exc}"
        ) from exc

    if not rows:
        raise DemandPerturbationError(
            "Demand perturbation CSV must contain at least one data row."
        )
    return DemandPerturbationSchedule(
        rows=tuple(sorted(rows, key=lambda row: (row.day, row.node_id, row.item_id))),
        path=schedule_path,
    )


__all__ = [
    "DEMAND_MULTIPLIER_MAX",
    "DEMAND_MULTIPLIER_MIN",
    "DEMAND_PERTURBATION_AUDIT_COLUMNS",
    "DEMAND_PERTURBATION_COLUMNS",
    "DemandPerturbationError",
    "DemandPerturbationRow",
    "DemandPerturbationSchedule",
    "load_demand_perturbation_schedule",
]
