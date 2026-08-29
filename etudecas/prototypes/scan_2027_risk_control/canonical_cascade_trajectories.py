"""Strict path-level daily trajectories for canonical cascade campaigns.

This module is intentionally independent from the campaign runner and the HTML
demo.  It reads completed campaign artifacts only and writes two new,
non-overwritable artifacts:

* a long daily table at path-stage resolution;
* a compact, offline-ready JSON payload containing mean/min/max envelopes
  across paired seeds.

Dense engine tables must contain exactly one observation per measured day for
every entity they expose.  Event tables (shipments and MRP orders) are the only
tables whose absent days are explicitly interpreted as zero.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "scan.canonical_cascade_trajectories.v1"
COMPACT_SCHEMA_VERSION = "scan.canonical_cascade_trajectory_envelopes.v1"
MANIFEST_SCHEMA_VERSION = "scan.canonical_cascade_trajectory_manifest.v1"

DEFAULT_CONFIG_NAME = "canonical_cascade_config_snapshot.json"
DEFAULT_RUNS_NAME = "canonical_cascade_runs.csv"
LONG_OUTPUT_NAME = "canonical_cascade_trajectories_long.csv"
COMPACT_OUTPUT_NAME = "canonical_cascade_trajectories_compact.json"
MANIFEST_OUTPUT_NAME = "canonical_cascade_trajectories_manifest.json"

LONG_COLUMNS: tuple[str, ...] = (
    "schema_version",
    "cascade_id",
    "variant_id",
    "variant_role",
    "case_type",
    "solution_id",
    "seed",
    "day",
    "path_stage_index",
    "path_stage_kind",
    "path_node_role",
    "stage_from_node_id",
    "stage_to_node_id",
    "node_id",
    "item_id",
    "metric",
    "value",
    "uom",
    "source_file",
    "source_semantics",
)

_REQUIRED_RUN_COLUMNS = frozenset(
    {
        "cascade_id",
        "variant_id",
        "case_type",
        "solution_id",
        "seed",
        "status",
        "result_dir",
    }
)
_CASE_TYPES = frozenset({"normal", "incident_no_action", "incident_with_solution"})


class CascadeTrajectoryError(RuntimeError):
    """Raised when a campaign cannot support strict trajectory extraction."""


@dataclass(frozen=True)
class PathStage:
    index: int
    kind: str
    from_node_id: str = ""
    to_node_id: str = ""
    node_id: str = ""
    item_id: str = ""
    input_item_id: str = ""
    output_item_id: str = ""


@dataclass(frozen=True)
class CascadeDefinition:
    cascade_id: str
    customer_id: str
    finished_item_id: str
    stages: tuple[PathStage, ...]
    solution_ids: frozenset[str]
    configured_uoms: tuple[tuple[str, str], ...]

    @property
    def path_items(self) -> frozenset[str]:
        items: set[str] = {self.finished_item_id}
        for stage in self.stages:
            items.update(
                item
                for item in (stage.item_id, stage.input_item_id, stage.output_item_id)
                if item
            )
        return frozenset(items)


@dataclass(frozen=True)
class RunReference:
    cascade_id: str
    variant_id: str
    case_type: str
    solution_id: str
    seed: int
    result_dir: Path

    @property
    def variant_role(self) -> str:
        if self.case_type == "normal":
            return "normal"
        if self.case_type == "incident_no_action":
            return "no_action"
        return f"solution:{self.solution_id}"


@dataclass(frozen=True)
class DenseTable:
    filename: str
    values: Mapping[tuple[str, str], Mapping[int, Mapping[str, float]]]
    uoms: Mapping[tuple[str, str], str]


@dataclass(frozen=True)
class RunTables:
    input_arrivals: DenseTable
    input_stocks: DenseTable
    output_products: DenseTable
    demand_service: DenseTable
    shipments: tuple[Mapping[str, Any], ...]
    mrp_orders: tuple[Mapping[str, Any], ...]
    input_consumption: DenseTable | None
    input_shipments: DenseTable | None
    supplier_stock_flows: DenseTable | None
    dc_stocks: DenseTable | None
    uom_observations: tuple[tuple[str, str, str], ...]


def _nonempty(value: Any, *, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CascadeTrajectoryError(f"{label} must be a non-empty string.")
    return text


def _strict_int(value: Any, *, label: str) -> int:
    text = str(value).strip()
    if not text:
        raise CascadeTrajectoryError(f"{label} must be an integer.")
    try:
        parsed = int(text)
    except (TypeError, ValueError) as exc:
        raise CascadeTrajectoryError(
            f"{label} must be an integer, got {value!r}."
        ) from exc
    if text not in {str(parsed), f"+{parsed}"}:
        raise CascadeTrajectoryError(f"{label} must be an integer, got {value!r}.")
    return parsed


def _finite_float(value: Any, *, label: str) -> float:
    text = str(value).strip()
    if not text:
        raise CascadeTrajectoryError(f"{label} must be a finite number.")
    try:
        parsed = float(text)
    except (TypeError, ValueError) as exc:
        raise CascadeTrajectoryError(
            f"{label} must be a finite number, got {value!r}."
        ) from exc
    if not math.isfinite(parsed):
        raise CascadeTrajectoryError(f"{label} must be finite, got {value!r}.")
    return parsed


def _normalize_uom(value: Any, *, label: str) -> str:
    raw = _nonempty(value, label=label).upper()
    return {
        "UNIT": "UN",
        "UNITE": "UN",
        "UNITS": "UN",
        "ZUN": "UN",
    }.get(raw, raw)


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise CascadeTrajectoryError(f"{label} not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CascadeTrajectoryError(f"Cannot read {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CascadeTrajectoryError(f"{label} must contain a JSON object: {path}")
    return payload


def _read_csv(
    path: Path,
    *,
    required_columns: Iterable[str],
    label: str,
    required: bool = True,
) -> tuple[list[dict[str, str]], tuple[str, ...]] | None:
    if not path.is_file():
        if required:
            raise CascadeTrajectoryError(f"Required {label} not found: {path}")
        return None
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fieldnames = tuple(reader.fieldnames or ())
            missing = sorted(set(required_columns) - set(fieldnames))
            if missing:
                raise CascadeTrajectoryError(
                    f"{label} is missing required columns {missing}: {path}"
                )
            rows = [dict(row) for row in reader]
    except OSError as exc:
        raise CascadeTrajectoryError(f"Cannot read {label}: {path}: {exc}") from exc
    return rows, fieldnames


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_config(
    payload: Mapping[str, Any],
) -> tuple[int, dict[str, CascadeDefinition]]:
    campaign = payload.get("campaign")
    if not isinstance(campaign, Mapping):
        raise CascadeTrajectoryError("Config snapshot must contain campaign object.")
    days = _strict_int(campaign.get("days"), label="campaign.days")
    if days <= 0:
        raise CascadeTrajectoryError("campaign.days must be positive.")
    raw_cascades = payload.get("cascades")
    if not isinstance(raw_cascades, list) or not raw_cascades:
        raise CascadeTrajectoryError(
            "Config snapshot must contain non-empty cascades list."
        )

    result: dict[str, CascadeDefinition] = {}
    for raw in raw_cascades:
        if not isinstance(raw, Mapping):
            raise CascadeTrajectoryError("Each cascade config must be an object.")
        cascade_id = _nonempty(raw.get("id"), label="cascade.id")
        if cascade_id in result:
            raise CascadeTrajectoryError(f"Duplicate cascade id {cascade_id!r}.")
        customer_id = _nonempty(
            raw.get("customer_id"), label=f"{cascade_id}.customer_id"
        )
        finished_item = _nonempty(
            raw.get("finished_item_id"), label=f"{cascade_id}.finished_item_id"
        )
        raw_path = raw.get("path")
        if not isinstance(raw_path, list) or not raw_path:
            raise CascadeTrajectoryError(f"{cascade_id}.path must be a non-empty list.")
        stages: list[PathStage] = []
        for index, stage_raw in enumerate(raw_path):
            if not isinstance(stage_raw, Mapping):
                raise CascadeTrajectoryError(
                    f"{cascade_id}.path[{index}] must be an object."
                )
            kind = _nonempty(
                stage_raw.get("kind"), label=f"{cascade_id}.path[{index}].kind"
            )
            if kind == "transport":
                stages.append(
                    PathStage(
                        index=index,
                        kind=kind,
                        from_node_id=_nonempty(
                            stage_raw.get("from"),
                            label=f"{cascade_id}.path[{index}].from",
                        ),
                        to_node_id=_nonempty(
                            stage_raw.get("to"), label=f"{cascade_id}.path[{index}].to"
                        ),
                        item_id=_nonempty(
                            stage_raw.get("item_id"),
                            label=f"{cascade_id}.path[{index}].item_id",
                        ),
                    )
                )
            elif kind == "transform":
                stages.append(
                    PathStage(
                        index=index,
                        kind=kind,
                        node_id=_nonempty(
                            stage_raw.get("node_id"),
                            label=f"{cascade_id}.path[{index}].node_id",
                        ),
                        input_item_id=_nonempty(
                            stage_raw.get("input_item_id"),
                            label=f"{cascade_id}.path[{index}].input_item_id",
                        ),
                        output_item_id=_nonempty(
                            stage_raw.get("output_item_id"),
                            label=f"{cascade_id}.path[{index}].output_item_id",
                        ),
                    )
                )
            else:
                raise CascadeTrajectoryError(
                    f"{cascade_id}.path[{index}].kind must be transport or transform."
                )
        _validate_path_continuity(cascade_id, stages, customer_id, finished_item)

        raw_solutions = raw.get("solutions", [])
        if not isinstance(raw_solutions, list):
            raise CascadeTrajectoryError(f"{cascade_id}.solutions must be a list.")
        solution_ids: set[str] = set()
        for solution in raw_solutions:
            if not isinstance(solution, Mapping):
                raise CascadeTrajectoryError(
                    f"{cascade_id}.solutions entries must be objects."
                )
            solution_id = _nonempty(
                solution.get("id"), label=f"{cascade_id}.solution.id"
            )
            if solution_id in solution_ids:
                raise CascadeTrajectoryError(
                    f"Duplicate solution {solution_id!r} in cascade {cascade_id}."
                )
            solution_ids.add(solution_id)

        configured_uoms: list[tuple[str, str]] = []
        selectors = raw.get("stock_selectors", [])
        if selectors is not None:
            if not isinstance(selectors, list):
                raise CascadeTrajectoryError(
                    f"{cascade_id}.stock_selectors must be a list."
                )
            for selector_index, selector in enumerate(selectors):
                if not isinstance(selector, Mapping):
                    raise CascadeTrajectoryError(
                        f"{cascade_id}.stock_selectors[{selector_index}] must be an object."
                    )
                if selector.get("uom"):
                    configured_uoms.append(
                        (
                            _nonempty(
                                selector.get("item_id"),
                                label=f"{cascade_id}.stock_selectors[{selector_index}].item_id",
                            ),
                            _normalize_uom(
                                selector.get("uom"),
                                label=f"{cascade_id}.stock_selectors[{selector_index}].uom",
                            ),
                        )
                    )
        result[cascade_id] = CascadeDefinition(
            cascade_id=cascade_id,
            customer_id=customer_id,
            finished_item_id=finished_item,
            stages=tuple(stages),
            solution_ids=frozenset(solution_ids),
            configured_uoms=tuple(configured_uoms),
        )
    return days, result


def _validate_path_continuity(
    cascade_id: str,
    stages: Sequence[PathStage],
    customer_id: str,
    finished_item_id: str,
) -> None:
    for previous, current in zip(stages, stages[1:]):
        if previous.kind == "transport":
            previous_node = previous.to_node_id
            previous_item = previous.item_id
        else:
            previous_node = previous.node_id
            previous_item = previous.output_item_id
        if current.kind == "transport":
            current_node = current.from_node_id
            current_item = current.item_id
        else:
            current_node = current.node_id
            current_item = current.input_item_id
        parallel_inbound_branches = (
            previous.kind == "transport"
            and current.kind == "transport"
            and previous.to_node_id == current.to_node_id
            and previous.item_id == current.item_id
        )
        if (
            previous_node != current_node or previous_item != current_item
        ) and not parallel_inbound_branches:
            raise CascadeTrajectoryError(
                f"{cascade_id}.path is discontinuous between stages {previous.index} and "
                f"{current.index}: ({previous_node}, {previous_item}) != "
                f"({current_node}, {current_item})."
            )
    terminal = stages[-1]
    terminal_node = (
        terminal.to_node_id if terminal.kind == "transport" else terminal.node_id
    )
    terminal_item = (
        terminal.item_id if terminal.kind == "transport" else terminal.output_item_id
    )
    if terminal_node != customer_id or terminal_item != finished_item_id:
        raise CascadeTrajectoryError(
            f"{cascade_id}.path must terminate at ({customer_id}, {finished_item_id}), "
            f"got ({terminal_node}, {terminal_item})."
        )


def _parse_runs(
    path: Path, *, campaign_root: Path, days: int
) -> tuple[RunReference, ...]:
    loaded = _read_csv(
        path,
        required_columns=_REQUIRED_RUN_COLUMNS,
        label="cascade runs CSV",
    )
    assert loaded is not None
    rows, _ = loaded
    if not rows:
        raise CascadeTrajectoryError("Cascade runs CSV contains no rows.")
    references: list[RunReference] = []
    keys: set[tuple[str, str, int]] = set()
    for row_index, row in enumerate(rows, start=2):
        status = str(row.get("status") or "").strip()
        if status != "ok":
            raise CascadeTrajectoryError(
                f"Run row {row_index} is not a completed physical run: status={status!r}."
            )
        cascade_id = _nonempty(
            row.get("cascade_id"), label=f"runs row {row_index}.cascade_id"
        )
        variant_id = _nonempty(
            row.get("variant_id"), label=f"runs row {row_index}.variant_id"
        )
        case_type = _nonempty(
            row.get("case_type"), label=f"runs row {row_index}.case_type"
        )
        if case_type not in _CASE_TYPES:
            raise CascadeTrajectoryError(
                f"runs row {row_index}.case_type is unsupported: {case_type!r}."
            )
        solution_id = str(row.get("solution_id") or "").strip()
        if case_type == "incident_with_solution" and not solution_id:
            raise CascadeTrajectoryError(
                f"runs row {row_index} solution case requires solution_id."
            )
        if case_type != "incident_with_solution" and solution_id:
            raise CascadeTrajectoryError(
                f"runs row {row_index} reference case must not carry solution_id."
            )
        seed = _strict_int(row.get("seed"), label=f"runs row {row_index}.seed")
        if seed < 0:
            raise CascadeTrajectoryError(
                f"runs row {row_index}.seed must be non-negative."
            )
        if str(row.get("days") or "").strip():
            run_days = _strict_int(row.get("days"), label=f"runs row {row_index}.days")
            if run_days != days:
                raise CascadeTrajectoryError(
                    f"runs row {row_index}.days={run_days} differs from config days={days}."
                )
        raw_result_dir = Path(
            _nonempty(row.get("result_dir"), label=f"runs row {row_index}.result_dir")
        )
        result_dir = (
            raw_result_dir.resolve()
            if raw_result_dir.is_absolute()
            else (campaign_root / raw_result_dir).resolve()
        )
        if not result_dir.is_dir():
            raise CascadeTrajectoryError(
                f"Run result directory does not exist for row {row_index}: {result_dir}"
            )
        key = (cascade_id, variant_id, seed)
        if key in keys:
            raise CascadeTrajectoryError(
                f"Duplicate run key cascade/variant/seed: {cascade_id}/{variant_id}/{seed}."
            )
        keys.add(key)
        references.append(
            RunReference(
                cascade_id=cascade_id,
                variant_id=variant_id,
                case_type=case_type,
                solution_id=solution_id,
                seed=seed,
                result_dir=result_dir,
            )
        )
    return tuple(sorted(references, key=lambda r: (r.cascade_id, r.variant_id, r.seed)))


def _validate_run_grid(
    runs: Sequence[RunReference], cascades: Mapping[str, CascadeDefinition]
) -> dict[tuple[str, str], tuple[int, ...]]:
    grouped: dict[str, dict[str, list[RunReference]]] = {}
    for run in runs:
        cascade = cascades.get(run.cascade_id)
        if cascade is None:
            raise CascadeTrajectoryError(
                f"Run references cascade absent from config snapshot: {run.cascade_id}."
            )
        if (
            run.case_type == "incident_with_solution"
            and run.solution_id not in cascade.solution_ids
        ):
            raise CascadeTrajectoryError(
                f"Run solution {run.solution_id!r} is absent from cascade {run.cascade_id} config."
            )
        grouped.setdefault(run.cascade_id, {}).setdefault(run.variant_id, []).append(
            run
        )

    seeds_by_variant: dict[tuple[str, str], tuple[int, ...]] = {}
    for cascade_id, variants in grouped.items():
        case_variants: dict[str, set[str]] = {
            case_type: set() for case_type in _CASE_TYPES
        }
        expected_seed_set: tuple[int, ...] | None = None
        for variant_id, variant_runs in variants.items():
            case_types = {run.case_type for run in variant_runs}
            solution_ids = {run.solution_id for run in variant_runs}
            if len(case_types) != 1 or len(solution_ids) != 1:
                raise CascadeTrajectoryError(
                    f"Variant {cascade_id}/{variant_id} changes case_type or solution_id across seeds."
                )
            case_type = next(iter(case_types))
            case_variants[case_type].add(variant_id)
            seeds = tuple(sorted(run.seed for run in variant_runs))
            seeds_by_variant[(cascade_id, variant_id)] = seeds
            if expected_seed_set is None:
                expected_seed_set = seeds
            elif seeds != expected_seed_set:
                raise CascadeTrajectoryError(
                    f"Incomplete paired seed grid in cascade {cascade_id}: variant {variant_id} "
                    f"has {list(seeds)}, expected {list(expected_seed_set)}."
                )
        if len(case_variants["normal"]) != 1:
            raise CascadeTrajectoryError(
                f"Cascade {cascade_id} must contain exactly one normal variant."
            )
        if len(case_variants["incident_no_action"]) != 1:
            raise CascadeTrajectoryError(
                f"Cascade {cascade_id} must contain exactly one incident_no_action variant."
            )
        if not case_variants["incident_with_solution"]:
            raise CascadeTrajectoryError(
                f"Cascade {cascade_id} contains no incident_with_solution variant."
            )
    return seeds_by_variant


def _dense_table(
    path: Path,
    *,
    value_columns: Sequence[str],
    days: int,
    label: str,
    node_column: str = "node_id",
    item_column: str = "item_id",
    uom_column: str | None = None,
    required: bool = True,
) -> DenseTable | None:
    required_columns = {"day", node_column, item_column, *value_columns}
    if uom_column:
        required_columns.add(uom_column)
    loaded = _read_csv(
        path,
        required_columns=required_columns,
        label=label,
        required=required,
    )
    if loaded is None:
        return None
    rows, _ = loaded
    by_pair: dict[tuple[str, str], dict[int, dict[str, float]]] = {}
    uoms: dict[tuple[str, str], str] = {}
    for row_index, row in enumerate(rows, start=2):
        day = _strict_int(row.get("day"), label=f"{label} row {row_index}.day")
        if day < 0 or day >= days:
            raise CascadeTrajectoryError(
                f"{label} row {row_index}.day={day} outside dense horizon 0..{days - 1}."
            )
        node_id = _nonempty(
            row.get(node_column), label=f"{label} row {row_index}.{node_column}"
        )
        item_id = _nonempty(
            row.get(item_column), label=f"{label} row {row_index}.{item_column}"
        )
        pair = (node_id, item_id)
        target = by_pair.setdefault(pair, {})
        if day in target:
            raise CascadeTrajectoryError(
                f"{label} contains duplicate dense row for {node_id}/{item_id}/day {day}."
            )
        target[day] = {
            column: _finite_float(
                row.get(column), label=f"{label} row {row_index}.{column}"
            )
            for column in value_columns
        }
        if uom_column:
            uom = _normalize_uom(
                row.get(uom_column), label=f"{label} row {row_index}.{uom_column}"
            )
            previous = uoms.setdefault(pair, uom)
            if previous != uom:
                raise CascadeTrajectoryError(
                    f"{label} mixes UOM for {node_id}/{item_id}: {previous} vs {uom}."
                )
    expected_days = set(range(days))
    for pair, series in by_pair.items():
        observed_days = set(series)
        if observed_days != expected_days:
            missing = sorted(expected_days - observed_days)
            extra = sorted(observed_days - expected_days)
            raise CascadeTrajectoryError(
                f"{label} dense coverage invalid for {pair[0]}/{pair[1]}: "
                f"missing={missing[:10]}, extra={extra[:10]}."
            )
    return DenseTable(filename=path.name, values=by_pair, uoms=uoms)


def _sparse_shipments(
    path: Path,
) -> tuple[tuple[Mapping[str, Any], ...], tuple[tuple[str, str, str], ...]]:
    label = "production supplier shipments"
    loaded = _read_csv(
        path,
        required_columns={
            "day",
            "src_node_id",
            "dst_node_id",
            "item_id",
            "edge_id",
            "shipped_qty",
            "arrival_day",
            "uom",
        },
        label=label,
    )
    assert loaded is not None
    rows, _ = loaded
    parsed: list[Mapping[str, Any]] = []
    observations: list[tuple[str, str, str]] = []
    for row_index, row in enumerate(rows, start=2):
        item_id = _nonempty(
            row.get("item_id"), label=f"{label} row {row_index}.item_id"
        )
        uom = _normalize_uom(row.get("uom"), label=f"{label} row {row_index}.uom")
        parsed.append(
            {
                "day": _strict_int(
                    row.get("day"), label=f"{label} row {row_index}.day"
                ),
                "arrival_day": _strict_int(
                    row.get("arrival_day"), label=f"{label} row {row_index}.arrival_day"
                ),
                "src_node_id": _nonempty(
                    row.get("src_node_id"), label=f"{label} row {row_index}.src_node_id"
                ),
                "dst_node_id": _nonempty(
                    row.get("dst_node_id"), label=f"{label} row {row_index}.dst_node_id"
                ),
                "item_id": item_id,
                "edge_id": _nonempty(
                    row.get("edge_id"), label=f"{label} row {row_index}.edge_id"
                ),
                "shipped_qty": _finite_float(
                    row.get("shipped_qty"), label=f"{label} row {row_index}.shipped_qty"
                ),
                "uom": uom,
            }
        )
        observations.append((item_id, uom, path.name))
    return tuple(parsed), tuple(observations)


def _sparse_mrp_orders(path: Path) -> tuple[Mapping[str, Any], ...]:
    label = "MRP orders"
    loaded = _read_csv(
        path,
        required_columns={
            "day",
            "node_id",
            "item_id",
            "src_node_id",
            "dst_node_id",
            "edge_id",
            "release_qty",
            "planned_receipt_qty",
            "arrival_day",
        },
        label=label,
    )
    assert loaded is not None
    rows, _ = loaded
    parsed: list[Mapping[str, Any]] = []
    for row_index, row in enumerate(rows, start=2):
        parsed.append(
            {
                "day": _strict_int(
                    row.get("day"), label=f"{label} row {row_index}.day"
                ),
                "arrival_day": _strict_int(
                    row.get("arrival_day"), label=f"{label} row {row_index}.arrival_day"
                ),
                "node_id": _nonempty(
                    row.get("node_id"), label=f"{label} row {row_index}.node_id"
                ),
                "item_id": _nonempty(
                    row.get("item_id"), label=f"{label} row {row_index}.item_id"
                ),
                "src_node_id": _nonempty(
                    row.get("src_node_id"), label=f"{label} row {row_index}.src_node_id"
                ),
                "dst_node_id": _nonempty(
                    row.get("dst_node_id"), label=f"{label} row {row_index}.dst_node_id"
                ),
                "edge_id": str(row.get("edge_id") or "").strip(),
                "release_qty": _finite_float(
                    row.get("release_qty"), label=f"{label} row {row_index}.release_qty"
                ),
                "planned_receipt_qty": _finite_float(
                    row.get("planned_receipt_qty"),
                    label=f"{label} row {row_index}.planned_receipt_qty",
                ),
            }
        )
    return tuple(parsed)


def _uoms_from_optional_catalog(path: Path) -> tuple[tuple[str, str, str], ...]:
    if not path.is_file():
        return ()
    loaded = _read_csv(
        path,
        required_columns={"item_id", "uom"},
        label=f"UOM catalog {path.name}",
    )
    assert loaded is not None
    rows, _ = loaded
    observations: list[tuple[str, str, str]] = []
    for row_index, row in enumerate(rows, start=2):
        item_id = str(row.get("item_id") or "").strip()
        uom_raw = str(row.get("uom") or "").strip()
        if not item_id and not uom_raw:
            continue
        observations.append(
            (
                _nonempty(item_id, label=f"{path.name} row {row_index}.item_id"),
                _normalize_uom(uom_raw, label=f"{path.name} row {row_index}.uom"),
                path.name,
            )
        )
    return tuple(observations)


def _load_run_tables(result_dir: Path, *, days: int) -> RunTables:
    data_dir = result_dir / "data"
    if not data_dir.is_dir():
        raise CascadeTrajectoryError(f"Run data directory not found: {data_dir}")
    input_arrivals = _dense_table(
        data_dir / "production_input_replenishment_arrivals_daily.csv",
        value_columns=("arrived_qty",),
        days=days,
        label="production input arrivals",
        uom_column="uom",
    )
    input_stocks = _dense_table(
        data_dir / "production_input_stocks_daily.csv",
        value_columns=("stock_before_production", "stock_end_of_day"),
        days=days,
        label="production input stocks",
    )
    output_products = _dense_table(
        data_dir / "production_output_products_daily.csv",
        value_columns=(
            "produced_qty",
            "executed_qty",
            "released_qty",
            "wip_end_qty",
            "stock_end_of_day",
        ),
        days=days,
        label="production output products",
    )
    demand_service = _dense_table(
        data_dir / "production_demand_service_daily.csv",
        value_columns=(
            "demand_qty",
            "served_qty",
            "backlog_end_qty",
            "available_before_service_qty",
        ),
        days=days,
        label="production demand service",
    )
    assert input_arrivals is not None
    assert input_stocks is not None
    assert output_products is not None
    assert demand_service is not None
    shipments, shipment_uoms = _sparse_shipments(
        data_dir / "production_supplier_shipments_daily.csv"
    )
    mrp_orders = _sparse_mrp_orders(data_dir / "mrp_orders_daily.csv")

    input_consumption = _dense_table(
        data_dir / "production_input_consumption_daily.csv",
        value_columns=("consumed_qty",),
        days=days,
        label="production input consumption",
        uom_column="uom",
        required=False,
    )
    input_shipments = _dense_table(
        data_dir / "production_input_replenishment_shipments_daily.csv",
        value_columns=("shipped_to_node_qty",),
        days=days,
        label="production input shipments",
        uom_column="uom",
        required=False,
    )
    supplier_stock_flows = _dense_table(
        data_dir / "production_supplier_stock_flows_daily.csv",
        value_columns=(
            "stock_start_of_day",
            "incoming_qty",
            "outgoing_shipped_qty",
            "stock_end_of_day",
        ),
        days=days,
        label="production supplier stock flows",
        uom_column="uom",
        required=False,
    )
    dc_stocks = _dense_table(
        data_dir / "production_dc_stocks_daily.csv",
        value_columns=("stock_end_of_day",),
        days=days,
        label="production DC stocks",
        required=False,
    )

    observations: list[tuple[str, str, str]] = list(shipment_uoms)
    for table in (
        input_arrivals,
        input_consumption,
        input_shipments,
        supplier_stock_flows,
    ):
        if table is None:
            continue
        observations.extend(
            (pair[1], uom, table.filename) for pair, uom in table.uoms.items()
        )
    observations.extend(
        _uoms_from_optional_catalog(data_dir / "production_lot_events.csv")
    )
    observations.extend(
        _uoms_from_optional_catalog(data_dir / "initialization_observed_stock.csv")
    )
    return RunTables(
        input_arrivals=input_arrivals,
        input_stocks=input_stocks,
        output_products=output_products,
        demand_service=demand_service,
        shipments=shipments,
        mrp_orders=mrp_orders,
        input_consumption=input_consumption,
        input_shipments=input_shipments,
        supplier_stock_flows=supplier_stock_flows,
        dc_stocks=dc_stocks,
        uom_observations=tuple(observations),
    )


def _require_pair(
    table: DenseTable,
    pair: tuple[str, str],
    *,
    cascade_id: str,
    stage_index: int,
) -> Mapping[int, Mapping[str, float]]:
    series = table.values.get(pair)
    if series is None:
        raise CascadeTrajectoryError(
            f"{table.filename} has no dense series for cascade {cascade_id} stage "
            f"{stage_index}: {pair[0]}/{pair[1]}."
        )
    return series


def _validate_required_path_series(
    tables: RunTables,
    cascade: CascadeDefinition,
) -> None:
    for stage in cascade.stages:
        if stage.kind != "transform":
            continue
        _require_pair(
            tables.input_arrivals,
            (stage.node_id, stage.input_item_id),
            cascade_id=cascade.cascade_id,
            stage_index=stage.index,
        )
        _require_pair(
            tables.input_stocks,
            (stage.node_id, stage.input_item_id),
            cascade_id=cascade.cascade_id,
            stage_index=stage.index,
        )
        _require_pair(
            tables.output_products,
            (stage.node_id, stage.output_item_id),
            cascade_id=cascade.cascade_id,
            stage_index=stage.index,
        )
    terminal_stage = cascade.stages[-1]
    _require_pair(
        tables.demand_service,
        (cascade.customer_id, cascade.finished_item_id),
        cascade_id=cascade.cascade_id,
        stage_index=terminal_stage.index,
    )


def _build_uom_registry(
    runs: Sequence[RunReference],
    cascades: Mapping[str, CascadeDefinition],
    *,
    days: int,
) -> dict[str, str]:
    observed: dict[str, dict[str, set[str]]] = {}
    selected_cascade_ids = {run.cascade_id for run in runs}
    for cascade_id in sorted(selected_cascade_ids):
        cascade = cascades[cascade_id]
        for item_id, uom in cascade.configured_uoms:
            observed.setdefault(item_id, {}).setdefault(uom, set()).add(
                f"config:{cascade.cascade_id}"
            )
    for run in runs:
        tables = _load_run_tables(run.result_dir, days=days)
        cascade = cascades[run.cascade_id]
        _validate_required_path_series(tables, cascade)
        for item_id, uom, source in tables.uom_observations:
            observed.setdefault(item_id, {}).setdefault(uom, set()).add(
                f"{run.cascade_id}/{run.variant_id}/seed{run.seed}:{source}"
            )
    registry: dict[str, str] = {}
    for item_id, by_uom in sorted(observed.items()):
        if len(by_uom) > 1:
            details = "; ".join(
                f"{uom} from {sorted(sources)[:3]}"
                for uom, sources in sorted(by_uom.items())
            )
            raise CascadeTrajectoryError(
                f"Cross-UOM conflict for {item_id}; quantities will not be combined: {details}."
            )
        registry[item_id] = next(iter(by_uom))
    required_items = {
        item_id for run in runs for item_id in cascades[run.cascade_id].path_items
    }
    missing = sorted(required_items - set(registry))
    if missing:
        raise CascadeTrajectoryError(
            "No explicit UOM evidence for configured path items: " + ", ".join(missing)
        )
    return registry


def _base_record(
    run: RunReference,
    stage: PathStage,
    *,
    day: int,
    node_id: str,
    item_id: str,
    node_role: str,
    metric: str,
    value: float,
    uom: str,
    source_file: str,
    source_semantics: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "cascade_id": run.cascade_id,
        "variant_id": run.variant_id,
        "variant_role": run.variant_role,
        "case_type": run.case_type,
        "solution_id": run.solution_id,
        "seed": run.seed,
        "day": day,
        "path_stage_index": stage.index,
        "path_stage_kind": stage.kind,
        "path_node_role": node_role,
        "stage_from_node_id": stage.from_node_id,
        "stage_to_node_id": stage.to_node_id,
        "node_id": node_id,
        "item_id": item_id,
        "metric": metric,
        "value": value,
        "uom": uom,
        "source_file": source_file,
        "source_semantics": source_semantics,
    }


def _emit_dense_metrics(
    records: list[dict[str, Any]],
    run: RunReference,
    stage: PathStage,
    *,
    series: Mapping[int, Mapping[str, float]],
    node_id: str,
    item_id: str,
    node_role: str,
    metric_columns: Mapping[str, str],
    uom: str,
    source_file: str,
) -> None:
    for day, values in sorted(series.items()):
        for source_column, metric in metric_columns.items():
            records.append(
                _base_record(
                    run,
                    stage,
                    day=day,
                    node_id=node_id,
                    item_id=item_id,
                    node_role=node_role,
                    metric=metric,
                    value=float(values[source_column]),
                    uom=uom,
                    source_file=source_file,
                    source_semantics="dense_exact_daily",
                )
            )


def _sparse_stage_values(
    rows: Sequence[Mapping[str, Any]],
    stage: PathStage,
    *,
    value_column: str,
    day_column: str,
    days: int,
    uom: str | None = None,
) -> dict[int, float]:
    output = {day: 0.0 for day in range(days)}
    for row in rows:
        if (
            str(row.get("src_node_id") or "") != stage.from_node_id
            or str(row.get("dst_node_id") or "") != stage.to_node_id
            or str(row.get("item_id") or "") != stage.item_id
        ):
            continue
        if uom is not None and str(row.get("uom") or "") != uom:
            raise CascadeTrajectoryError(
                f"Sparse source UOM mismatch for stage {stage.index} {stage.item_id}: "
                f"{row.get('uom')!r} != {uom!r}."
            )
        day = int(row[day_column])
        if 0 <= day < days:
            output[day] += float(row[value_column])
    return output


def _dc_stock_owner_stages(
    cascade: CascadeDefinition,
) -> dict[tuple[str, str], PathStage]:
    owners: dict[tuple[str, str], PathStage] = {}
    for stage in cascade.stages:
        if stage.kind == "transport":
            owners[(stage.from_node_id, stage.item_id)] = stage
    for stage in cascade.stages:
        if stage.kind == "transport":
            owners.setdefault((stage.to_node_id, stage.item_id), stage)
    return owners


def _extract_run_records(
    run: RunReference,
    cascade: CascadeDefinition,
    *,
    days: int,
    uoms: Mapping[str, str],
) -> list[dict[str, Any]]:
    tables = _load_run_tables(run.result_dir, days=days)
    _validate_required_path_series(tables, cascade)
    records: list[dict[str, Any]] = []

    for stage in cascade.stages:
        if stage.kind == "transform":
            input_pair = (stage.node_id, stage.input_item_id)
            output_pair = (stage.node_id, stage.output_item_id)
            _emit_dense_metrics(
                records,
                run,
                stage,
                series=tables.input_arrivals.values[input_pair],
                node_id=stage.node_id,
                item_id=stage.input_item_id,
                node_role="transform_input",
                metric_columns={"arrived_qty": "input_replenishment_arrival_qty"},
                uom=uoms[stage.input_item_id],
                source_file=tables.input_arrivals.filename,
            )
            _emit_dense_metrics(
                records,
                run,
                stage,
                series=tables.input_stocks.values[input_pair],
                node_id=stage.node_id,
                item_id=stage.input_item_id,
                node_role="transform_input",
                metric_columns={
                    "stock_before_production": "input_stock_before_production_qty",
                    "stock_end_of_day": "input_stock_end_qty",
                },
                uom=uoms[stage.input_item_id],
                source_file=tables.input_stocks.filename,
            )
            _emit_dense_metrics(
                records,
                run,
                stage,
                series=tables.output_products.values[output_pair],
                node_id=stage.node_id,
                item_id=stage.output_item_id,
                node_role="transform_output",
                metric_columns={
                    "produced_qty": "production_produced_qty",
                    "executed_qty": "production_executed_qty",
                    "released_qty": "production_released_qty",
                    "wip_end_qty": "production_wip_end_qty",
                    "stock_end_of_day": "output_stock_end_qty",
                },
                uom=uoms[stage.output_item_id],
                source_file=tables.output_products.filename,
            )
            if (
                tables.input_consumption is not None
                and input_pair in tables.input_consumption.values
            ):
                _emit_dense_metrics(
                    records,
                    run,
                    stage,
                    series=tables.input_consumption.values[input_pair],
                    node_id=stage.node_id,
                    item_id=stage.input_item_id,
                    node_role="transform_input",
                    metric_columns={"consumed_qty": "input_consumed_qty"},
                    uom=uoms[stage.input_item_id],
                    source_file=tables.input_consumption.filename,
                )
            if (
                tables.input_shipments is not None
                and input_pair in tables.input_shipments.values
            ):
                _emit_dense_metrics(
                    records,
                    run,
                    stage,
                    series=tables.input_shipments.values[input_pair],
                    node_id=stage.node_id,
                    item_id=stage.input_item_id,
                    node_role="transform_input",
                    metric_columns={
                        "shipped_to_node_qty": "input_replenishment_shipment_qty"
                    },
                    uom=uoms[stage.input_item_id],
                    source_file=tables.input_shipments.filename,
                )
        else:
            item_uom = uoms[stage.item_id]
            shipment_values = _sparse_stage_values(
                tables.shipments,
                stage,
                value_column="shipped_qty",
                day_column="day",
                days=days,
                uom=item_uom,
            )
            arrival_values = _sparse_stage_values(
                tables.shipments,
                stage,
                value_column="shipped_qty",
                day_column="arrival_day",
                days=days,
                uom=item_uom,
            )
            release_values = _sparse_stage_values(
                tables.mrp_orders,
                stage,
                value_column="release_qty",
                day_column="day",
                days=days,
            )
            receipt_values = _sparse_stage_values(
                tables.mrp_orders,
                stage,
                value_column="planned_receipt_qty",
                day_column="arrival_day",
                days=days,
            )
            for day in range(days):
                for node_id, node_role, metric, value, source in (
                    (
                        stage.from_node_id,
                        "transport_source",
                        "transport_shipment_qty",
                        shipment_values[day],
                        "production_supplier_shipments_daily.csv",
                    ),
                    (
                        stage.to_node_id,
                        "transport_destination",
                        "transport_arrival_qty",
                        arrival_values[day],
                        "production_supplier_shipments_daily.csv",
                    ),
                    (
                        stage.from_node_id,
                        "transport_source",
                        "mrp_release_qty",
                        release_values[day],
                        "mrp_orders_daily.csv",
                    ),
                    (
                        stage.to_node_id,
                        "transport_destination",
                        "mrp_planned_receipt_qty",
                        receipt_values[day],
                        "mrp_orders_daily.csv",
                    ),
                ):
                    records.append(
                        _base_record(
                            run,
                            stage,
                            day=day,
                            node_id=node_id,
                            item_id=stage.item_id,
                            node_role=node_role,
                            metric=metric,
                            value=value,
                            uom=item_uom,
                            source_file=source,
                            source_semantics="sparse_event_zero_filled",
                        )
                    )

            if (
                tables.supplier_stock_flows is not None
                and (stage.from_node_id, stage.item_id)
                in tables.supplier_stock_flows.values
            ):
                _emit_dense_metrics(
                    records,
                    run,
                    stage,
                    series=tables.supplier_stock_flows.values[
                        (stage.from_node_id, stage.item_id)
                    ],
                    node_id=stage.from_node_id,
                    item_id=stage.item_id,
                    node_role="transport_source",
                    metric_columns={
                        "stock_start_of_day": "supplier_stock_start_qty",
                        "incoming_qty": "supplier_incoming_qty",
                        "outgoing_shipped_qty": "supplier_outgoing_shipment_qty",
                        "stock_end_of_day": "supplier_stock_end_qty",
                    },
                    uom=item_uom,
                    source_file=tables.supplier_stock_flows.filename,
                )

    terminal = cascade.stages[-1]
    demand_pair = (cascade.customer_id, cascade.finished_item_id)
    _emit_dense_metrics(
        records,
        run,
        terminal,
        series=tables.demand_service.values[demand_pair],
        node_id=cascade.customer_id,
        item_id=cascade.finished_item_id,
        node_role="customer",
        metric_columns={
            "demand_qty": "customer_demand_qty",
            "served_qty": "customer_served_qty",
            "backlog_end_qty": "customer_backlog_end_qty",
            "available_before_service_qty": "customer_available_before_service_qty",
        },
        uom=uoms[cascade.finished_item_id],
        source_file=tables.demand_service.filename,
    )

    if tables.dc_stocks is not None:
        for pair, owner_stage in _dc_stock_owner_stages(cascade).items():
            if pair not in tables.dc_stocks.values:
                continue
            _emit_dense_metrics(
                records,
                run,
                owner_stage,
                series=tables.dc_stocks.values[pair],
                node_id=pair[0],
                item_id=pair[1],
                node_role=(
                    "transport_source"
                    if owner_stage.from_node_id == pair[0]
                    else "transport_destination"
                ),
                metric_columns={"stock_end_of_day": "distribution_stock_end_qty"},
                uom=uoms[pair[1]],
                source_file=tables.dc_stocks.filename,
            )

    unique: set[tuple[Any, ...]] = set()
    for record in records:
        key = (
            record["day"],
            record["path_stage_index"],
            record["path_node_role"],
            record["node_id"],
            record["item_id"],
            record["metric"],
            record["uom"],
        )
        if key in unique:
            raise CascadeTrajectoryError(
                f"Duplicate trajectory point in {run.cascade_id}/{run.variant_id}/seed {run.seed}: "
                f"{key}."
            )
        unique.add(key)
    return sorted(
        records,
        key=lambda row: (
            int(row["path_stage_index"]),
            int(row["day"]),
            str(row["node_id"]),
            str(row["item_id"]),
            str(row["metric"]),
            str(row["path_node_role"]),
        ),
    )


def _series_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["cascade_id"]),
        str(row["variant_id"]),
        str(row["variant_role"]),
        str(row["case_type"]),
        str(row["solution_id"]),
        int(row["path_stage_index"]),
        str(row["path_stage_kind"]),
        str(row["path_node_role"]),
        str(row["stage_from_node_id"]),
        str(row["stage_to_node_id"]),
        str(row["node_id"]),
        str(row["item_id"]),
        str(row["metric"]),
        str(row["uom"]),
        str(row["source_semantics"]),
    )


def _build_compact_payload(
    stats: Mapping[tuple[Any, ...], Mapping[int, Sequence[float]]],
    *,
    days: int,
    seed_counts: Mapping[tuple[str, str], int],
    cascades: Mapping[str, CascadeDefinition],
) -> dict[str, Any]:
    cascade_payloads: dict[str, Any] = {}
    for cascade_id in sorted({str(key[0]) for key in stats}):
        cascade = cascades[cascade_id]
        variants: dict[str, Any] = {}
        relevant_keys = [key for key in stats if key[0] == cascade_id]
        for variant_id in sorted({str(key[1]) for key in relevant_keys}):
            variant_keys = [key for key in relevant_keys if key[1] == variant_id]
            first = variant_keys[0]
            expected_count = seed_counts[(cascade_id, variant_id)]
            series_payload: list[dict[str, Any]] = []
            for key in sorted(variant_keys, key=lambda value: value[5:]):
                by_day = stats[key]
                means: list[float] = []
                minima: list[float] = []
                maxima: list[float] = []
                for day in range(days):
                    values = list(by_day.get(day, ()))
                    if len(values) != expected_count:
                        raise CascadeTrajectoryError(
                            f"Envelope coverage mismatch for {cascade_id}/{variant_id}, "
                            f"series={key[5:]}, day={day}: {len(values)} values, "
                            f"expected {expected_count}."
                        )
                    means.append(sum(values) / len(values))
                    minima.append(min(values))
                    maxima.append(max(values))
                series_payload.append(
                    {
                        "path_stage_index": key[5],
                        "path_stage_kind": key[6],
                        "path_node_role": key[7],
                        "stage_from_node_id": key[8],
                        "stage_to_node_id": key[9],
                        "node_id": key[10],
                        "item_id": key[11],
                        "metric": key[12],
                        "uom": key[13],
                        "source_semantics": key[14],
                        "mean": means,
                        "min": minima,
                        "max": maxima,
                    }
                )
            variants[variant_id] = {
                "variant_role": first[2],
                "case_type": first[3],
                "solution_id": first[4],
                "seed_count": expected_count,
                "series": series_payload,
            }
        cascade_payloads[cascade_id] = {
            "customer_id": cascade.customer_id,
            "finished_item_id": cascade.finished_item_id,
            "path": [
                {
                    "path_stage_index": stage.index,
                    "kind": stage.kind,
                    "from_node_id": stage.from_node_id,
                    "to_node_id": stage.to_node_id,
                    "node_id": stage.node_id,
                    "item_id": stage.item_id,
                    "input_item_id": stage.input_item_id,
                    "output_item_id": stage.output_item_id,
                }
                for stage in cascade.stages
            ],
            "variants": variants,
        }
    return {
        "schema_version": COMPACT_SCHEMA_VERSION,
        "day_axis": list(range(days)),
        "statistics": ["mean", "min", "max"],
        "aggregation_scope": "paired_seeds_only_no_cross_uom_aggregation",
        "cascades": cascade_payloads,
    }


def export_cascade_trajectories(
    *,
    campaign_dir: Path,
    output_dir: Path,
    config_path: Path | None = None,
    runs_path: Path | None = None,
) -> Path:
    """Export strict long trajectories and compact seed envelopes.

    The output directory must not exist.  The function never launches a
    simulation and never changes campaign inputs.
    """

    campaign_root = campaign_dir.resolve()
    if not campaign_root.is_dir():
        raise CascadeTrajectoryError(f"Campaign directory not found: {campaign_root}")
    output_root = output_dir.resolve()
    if output_root.exists():
        raise CascadeTrajectoryError(
            f"Refusing to overwrite trajectory output directory: {output_root}"
        )
    resolved_config = (
        config_path.resolve()
        if config_path is not None
        else campaign_root / DEFAULT_CONFIG_NAME
    )
    resolved_runs = (
        runs_path.resolve()
        if runs_path is not None
        else campaign_root / DEFAULT_RUNS_NAME
    )
    config_payload = _load_json_object(resolved_config, label="cascade config snapshot")
    days, cascades = _parse_config(config_payload)
    runs = _parse_runs(resolved_runs, campaign_root=campaign_root, days=days)
    seeds_by_variant = _validate_run_grid(runs, cascades)

    # Full preflight happens before the exclusive output directory is created.
    uoms = _build_uom_registry(runs, cascades, days=days)

    if output_root.exists():
        raise CascadeTrajectoryError(
            f"Trajectory output directory appeared during validation: {output_root}"
        )
    output_root.mkdir(parents=True, exist_ok=False)
    long_path = output_root / LONG_OUTPUT_NAME
    compact_path = output_root / COMPACT_OUTPUT_NAME
    manifest_path = output_root / MANIFEST_OUTPUT_NAME

    stats: dict[tuple[Any, ...], dict[int, list[float]]] = {}
    row_count = 0
    with long_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(LONG_COLUMNS), extrasaction="raise"
        )
        writer.writeheader()
        for run in runs:
            cascade = cascades[run.cascade_id]
            records = _extract_run_records(
                run,
                cascade,
                days=days,
                uoms=uoms,
            )
            for record in records:
                writer.writerow(record)
                row_count += 1
                key = _series_key(record)
                stats.setdefault(key, {}).setdefault(int(record["day"]), []).append(
                    float(record["value"])
                )

    seed_counts = {key: len(seeds) for key, seeds in seeds_by_variant.items()}
    compact_payload = _build_compact_payload(
        stats,
        days=days,
        seed_counts=seed_counts,
        cascades=cascades,
    )
    compact_path.write_text(
        json.dumps(
            compact_payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "complete",
        "campaign_dir": str(campaign_root),
        "config_snapshot": {
            "path": str(resolved_config),
            "sha256": _sha256(resolved_config),
        },
        "runs_csv": {
            "path": str(resolved_runs),
            "sha256": _sha256(resolved_runs),
        },
        "days": days,
        "run_count": len(runs),
        "cascade_ids": sorted({run.cascade_id for run in runs}),
        "item_uoms": dict(sorted(uoms.items())),
        "long_row_count": row_count,
        "series_count": len(stats),
        "outputs": {
            "long_csv": str(long_path),
            "long_csv_sha256": _sha256(long_path),
            "compact_json": str(compact_path),
            "compact_json_sha256": _sha256(compact_path),
        },
        "semantics": {
            "dense": "exactly one finite observation per entity and measured day",
            "sparse": (
                "shipment and MRP event tables only; absent measured days are explicit zero"
            ),
            "uom": "no aggregation is performed across distinct normalized UOM values",
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return manifest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export strict path-level trajectories from a completed cascade campaign."
    )
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--runs", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = export_cascade_trajectories(
            campaign_dir=args.campaign_dir,
            output_dir=args.output_dir,
            config_path=args.config,
            runs_path=args.runs,
        )
    except CascadeTrajectoryError as exc:
        raise SystemExit(str(exc)) from exc
    print(manifest.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "COMPACT_OUTPUT_NAME",
    "CascadeTrajectoryError",
    "LONG_COLUMNS",
    "LONG_OUTPUT_NAME",
    "MANIFEST_OUTPUT_NAME",
    "export_cascade_trajectories",
    "main",
]
