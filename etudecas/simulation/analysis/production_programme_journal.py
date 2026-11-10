"""Read-only observations of weekly simulated manufacturing launch programmes.

These are versioned recommendations, not industrial production orders. Physical
work does not revise a target: a campaign's full launch credit is retained once.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import json
import math
from typing import Any, Iterable

SCHEMA_VERSION = 1
BASIS = "simulated_weekly_launch_programme_v1"
AUTHORIZATION_BASIS = "simulated_weekly_launch_programme_authorization_v1"
JOURNAL_FILENAME = "production_programme_snapshots.csv"
JOURNAL_FIELDS = [
    "schema_version", "basis", "scenario_id", "programme_id", "node_id",
    "output_item_id", "uom", "decision_day", "known_day", "version",
    "week_start_day", "coverage_start_day", "coverage_end_day_exclusive",
    "launch_quantities_json", "committed_quantities_json", "proposed_quantities_json",
]


def _day(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("A programme observation day must be an integer")
    return value


def _quantity(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("A programme quantity must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("A programme quantity must be finite and nonnegative")
    return number


class ProductionProgrammeJournal:
    """Append-only snapshots; no mutation of passed proposals or engine state."""

    def __init__(self, *, scenario_id: str, origin_date: str,
                 commitment_policy: str | None = "first_physical_execution_v1"):
        if not scenario_id:
            raise ValueError("Programme observations require a scenario identity")
        if commitment_policy not in (None, "first_physical_execution_v1"):
            raise ValueError("Unknown campaign commitment observation convention")
        self.commitment_policy = commitment_policy
        self.basis = AUTHORIZATION_BASIS if commitment_policy is None else BASIS
        self.scenario_id = scenario_id
        self._weekday = date.fromisoformat(origin_date).weekday()
        self.rows: list[dict[str, Any]] = []
        self._launches: dict[str, tuple[Any, ...]] = {}
        self._committed: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
        self._versions: dict[str, int] = defaultdict(int)
        self._last_day: dict[tuple[str, str], int] = {}
        self._units: dict[tuple[str, str], str] = {}
        self.observed_pairs: set[tuple[str, str]] = set()

    def week_start(self, day: int) -> int:
        return day - ((self._weekday + day) % 7)

    def _unit(self, pair: tuple[str, str], uom: str) -> None:
        if not all(pair) or not uom:
            raise ValueError("Programme observations require site, item and unit")
        if pair in self._units and self._units[pair] != uom:
            raise ValueError("A programme pair cannot change its quantity unit")
        self._units[pair] = uom

    def record_launch(self, *, campaign_id: str, node_id: str, output_item_id: str,
                      uom: str, day: int, qty: float) -> bool:
        """Record the existing campaign engagement, never material consumption.

        The first-physical-work policy dates this credit at actual first work;
        legacy execution dates it at campaign creation, possibly before work.
        """
        day, quantity = _day(day), _quantity(qty)
        pair = node_id, output_item_id
        self._unit(pair, uom)
        if not campaign_id or day < 0 or quantity <= 0:
            raise ValueError("A launch credit requires a campaign, date and positive quantity")
        value = pair, uom, day, quantity
        if campaign_id in self._launches:
            if self._launches[campaign_id] != value:
                raise ValueError("A campaign launch identity has conflicting quantities or dates")
            return False
        self._launches[campaign_id] = value
        self._committed[pair][day] += quantity
        return True

    def observe(self, *, decision_day: int, node_id: str, output_item_id: str,
                uom: str, proposals: Iterable[Any], coverage_end_day_exclusive: int) -> list[dict[str, Any]]:
        """Publish one complete EOD forecast over each covered absolute week.

        Revocable recommendations retain their raw absolute release dates,
        including overdue dates. They are not promises of retroactive work.
        Missing dates outside the coverage are never filled as known zeros.
        """
        day, end = _day(decision_day), _day(coverage_end_day_exclusive)
        pair = node_id, output_item_id
        self._unit(pair, uom)
        if day < 0 or end <= day:
            raise ValueError("Programme coverage must extend beyond the decision day")
        if day <= self._last_day.get(pair, -1):
            raise ValueError("Publish one ordered programme observation per pair and day")
        self._last_day[pair] = day
        self.observed_pairs.add(pair)
        first_week = self.week_start(day)
        start = max(0, first_week)
        committed = self._committed[pair]
        for old_day in tuple(committed):
            if old_day < first_week:
                del committed[old_day]
        if any(launch_day > day for launch_day in committed):
            raise ValueError("An EOD snapshot cannot know a future campaign commitment")
        proposed: dict[int, float] = defaultdict(float)
        for proposal in proposals:
            release = _day(proposal.release_day)
            quantity = _quantity(proposal.qty)
            target_day = release
            if start <= target_day < end:
                proposed[target_day] += quantity
        published = []
        for week in range(first_week, end, 7):
            low, high = max(start, week), min(end, week + 7)
            if low >= high:
                continue
            identity = "PPROG|" + json.dumps([self.scenario_id, node_id, output_item_id, week],
                                               ensure_ascii=False, separators=(",", ":"))
            self._versions[identity] += 1
            committed_vector = {str(d): round(committed.get(d, 0.), 6) for d in range(low, high)}
            proposed_vector = {str(d): round(proposed.get(d, 0.), 6) for d in range(low, high)}
            total_vector = {str(d): round(committed_vector[str(d)] + proposed_vector[str(d)], 6)
                            for d in range(low, high)}
            row = dict(schema_version=SCHEMA_VERSION, basis=self.basis, scenario_id=self.scenario_id,
                programme_id=identity, node_id=node_id, output_item_id=output_item_id,
                uom=uom, decision_day=day, known_day=day, version=self._versions[identity],
                week_start_day=week, coverage_start_day=low, coverage_end_day_exclusive=high,
                launch_quantities_json=json.dumps(total_vector, sort_keys=True, separators=(",", ":")),
                committed_quantities_json=json.dumps(committed_vector, sort_keys=True, separators=(",", ":")),
                proposed_quantities_json=json.dumps(proposed_vector, sort_keys=True, separators=(",", ":")))
            self.rows.append(row)
            published.append(row)
        return published

    def summary(self, *, expected_pairs: Iterable[tuple[str, str]]) -> dict[str, Any]:
        expected = set(expected_pairs)
        return dict(schema_version=SCHEMA_VERSION, basis=self.basis, file="data/" + JOURNAL_FILENAME,
            enabled=True, status="observed" if self.rows else "no_observation",
            published_snapshot_count=len(self.rows),
            observed_pairs=[dict(node_id=pair[0], output_item_id=pair[1]) for pair in sorted(self.observed_pairs)],
            expected_pairs=[dict(node_id=pair[0], output_item_id=pair[1]) for pair in sorted(expected)],
            complete_scope=self.observed_pairs == expected,
            label="Révision du programme prévisionnel des lancements simulés",
            semantics="Published weekly absolute-date vectors; committed campaign launch plus revocable recommendations; not industrial OF revisions",
            commitment_policy=(self.commitment_policy or "campaign_creation_authorization"),
            launch_credit=("Full regular campaign quantity once at first physical work; opening/initial firm orders excluded"
                if self.commitment_policy is not None else
                "Full regular campaign quantity once at existing campaign creation authorization, possibly before physical work; no consumption or manufactured quantity inferred; opening/initial firm orders excluded"),
            publication="One version per pair/absolute Monday week at EOD, including unchanged versions",
            overdue_proposal_convention="Raw absolute release days are preserved even when overdue; recommendations are not guarantees of physical feasibility or retroactive work",
            coverage="Current week committed history plus actual queried planning horizon; explicit partial-week coverage; no known zero outside coverage",
            quantity_precision="Six decimals in each homogeneous programme unit; no cross-item quantity sums")
