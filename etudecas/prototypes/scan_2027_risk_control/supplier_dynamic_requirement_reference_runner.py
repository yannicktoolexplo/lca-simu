#!/usr/bin/env python3
"""Run a fail-closed paired diagnostic of two coupled requirement systems.

The three-seed smoke test and the 15-seed comparison must use separate output
directories.  Execution is refused while the named V3 campaign reports an
active process.  No supplier incident or occurrence probability is involved.
This is not an MRP-only causal experiment: direct supplier capacities and
upstream procurement policies can change with the dynamic requirement signal.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Callable, Iterable, Mapping, Sequence

if __package__ in {None, ""}:
    _DIRECT_REPO_ROOT = Path(__file__).resolve().parents[3]
    if not (_DIRECT_REPO_ROOT / "etudecas").is_dir():
        raise RuntimeError("Cannot locate the repository root for direct execution")
    _direct_repo_root_text = str(_DIRECT_REPO_ROOT)
    if _direct_repo_root_text not in sys.path:
        sys.path.insert(0, _direct_repo_root_text)

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_dynamic_requirement_reference_protocol as protocol,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_post_priority_extension_runner as v3_runner,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_service_landscape_campaign as campaign_core,
)


SCHEMA_VERSION = "etudecas.dynamic_requirement_reference_runner.v2"
LEDGER_SCHEMA_VERSION = f"{SCHEMA_VERSION}.ledger"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case_evidence"
MANIFEST_FILE = "comparison_runner_manifest.json"
LEDGER_FILE = "execution_ledger.json"
LOCK_FILE = ".dynamic_reference_runner.lock"
LOCK_COORDINATION_FILE = ".dynamic_reference_runner.lock.coordination"
ABANDONED_LOCK_DIR = "abandoned_locks"
V3_MANIFEST_FILE = "post_priority_extension_runner_manifest.json"
V3_CHECKPOINT_FILE = "preliminary_checkpoint_15_manifest.json"
VARIANTS = (protocol.OLD_VARIANT_ID, protocol.NEW_VARIANT_ID)
PRODUCTS = ("268091", "268967")
ZERO_EPS = 1e-9
BALANCE_ABS_TOL = 2e-4
BALANCE_REL_TOL = 2e-8
RESULT_FILES = (
    "case_metrics.csv",
    "material_seed_metrics.csv",
    "paired_system_metrics.csv",
    "paired_material_metrics.csv",
    "system_comparison_summary.csv",
    "material_comparison_summary.csv",
)


@dataclass(frozen=True)
class PlannedCase:
    variant_id: str
    seed: int

    @property
    def key(self) -> str:
        return f"{self.variant_id}::seed_{self.seed}"


CaseExecutor = Callable[[PlannedCase, protocol.ValidatedProtocol, Path], dict[str, Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return protocol.sha256_file(path)


def _stable_sha256(payload: Any) -> str:
    return protocol.stable_sha256(payload)


def _read_json(path: Path) -> dict[str, Any]:
    return protocol.read_json(path)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required result file missing: {path}")
    return protocol.read_csv(path)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    protocol.write_json_atomic(path, payload)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing empty result table: {path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _float(value: Any, default: float = math.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _int(value: Any, default: int = -1) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "oui"}


def _percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(value for value in values if math.isfinite(value))
    if not ordered:
        return math.nan
    if len(ordered) == 1:
        return ordered[0]
    position = min(1.0, max(0.0, quantile)) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _close(left: float, right: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=BALANCE_REL_TOL,
        abs_tol=BALANCE_ABS_TOL,
    )


def _normalise_uom(value: Any) -> str:
    raw = str(value or "").strip().upper().replace(" ", "")
    aliases = {
        "UNIT": "UN",
        "UNITS": "UN",
        "UNITES": "UN",
        "UNITÉS": "UN",
        "GRAM": "G",
        "GRAMME": "G",
        "GRAMMES": "G",
        "KILOGRAM": "KG",
        "KILOGRAMME": "KG",
        "KILOGRAMMES": "KG",
        "METER": "M",
        "METRE": "M",
        "MÈTRE": "M",
    }
    return aliases.get(raw, raw)


def _convert_uom(quantity: float, source_uom: Any, target_uom: Any) -> float:
    source = _normalise_uom(source_uom)
    target = _normalise_uom(target_uom)
    if not source:
        source = target
    if source == target:
        return quantity
    mass_in_kg = {"MG": 1e-6, "G": 1e-3, "KG": 1.0, "T": 1e3}
    if source in mass_in_kg and target in mass_in_kg:
        return quantity * mass_in_kg[source] / mass_in_kg[target]
    raise ValueError(
        f"Unsupported BOM unit conversion: {source or '?'} -> {target or '?'}"
    )


def _variant_requirement_mode(variant_id: str, pair_key: str) -> str:
    if variant_id == protocol.NEW_VARIANT_ID:
        return "explicit_dynamic_mps_bom"
    if variant_id == protocol.OLD_VARIANT_ID:
        return (
            "explicit_dynamic_mps_bom"
            if pair_key in protocol.EXPLICIT_DYNAMIC_PAIRS
            else "explicit_static_capacity_based_requirement"
        )
    raise ValueError(f"Unknown variant: {variant_id}")


def _bom_requirements(
    validated: protocol.ValidatedProtocol,
) -> dict[str, tuple[tuple[str, str, float], ...]]:
    """Return component usage per executed output unit, in inventory units."""

    graph = _read_json(validated.graph)
    materials = {row.pair_key: row for row in validated.materials}
    requirements: dict[str, list[tuple[str, str, float]]] = {
        key: [] for key in materials
    }
    for node in graph.get("nodes") or []:
        node_id = str(node.get("id") or "")
        for process in node.get("processes") or []:
            outputs = process.get("outputs") or []
            if len(outputs) != 1:
                raise ValueError(f"Exactly one process output is required at {node_id}")
            output_item_id = str((outputs[0] or {}).get("item_id") or "")
            batch_size = _float(process.get("batch_size"))
            if not math.isfinite(batch_size) or batch_size <= ZERO_EPS:
                raise ValueError(
                    f"Invalid process batch size: {node_id}|{output_item_id}"
                )
            for component in process.get("inputs") or []:
                item_id = str(component.get("item_id") or "")
                key = f"{node_id}|{item_id}"
                if key not in materials:
                    continue
                ratio = _float(component.get("ratio_per_batch"))
                if not math.isfinite(ratio) or ratio <= ZERO_EPS:
                    raise ValueError(f"Invalid BOM ratio: {key}")
                ratio_in_inventory_uom = _convert_uom(
                    ratio,
                    component.get("ratio_unit"),
                    materials[key].uom,
                )
                requirements[key].append(
                    (node_id, output_item_id, ratio_in_inventory_uom / batch_size)
                )
    if any(not rows for rows in requirements.values()):
        missing = sorted(key for key, rows in requirements.items() if not rows)
        raise ValueError(f"No BOM requirement found for materials: {missing}")
    return {key: tuple(rows) for key, rows in requirements.items()}


def _variant_profile(validated: protocol.ValidatedProtocol, variant_id: str) -> Path:
    if variant_id == protocol.OLD_VARIANT_ID:
        return validated.old_profile
    if variant_id == protocol.NEW_VARIANT_ID:
        return validated.new_profile
    raise ValueError(f"Unknown variant: {variant_id}")


def _authoritative_v3_checkpoint_validation(
    *,
    output_dir: Path,
    runner_signature: str,
    plan_manifest_sha256: str,
    require_live_ledger_match: bool,
    expected_signed_seed_ids: Sequence[int],
) -> dict[str, Any] | None:
    """Delegate checkpoint-file and live-ledger integrity to its owning runner."""

    return v3_runner._validate_preliminary_checkpoint(
        output_dir=output_dir,
        runner_signature=runner_signature,
        plan_manifest_sha256=plan_manifest_sha256,
        require_live_ledger_match=require_live_ledger_match,
        expected_signed_seed_ids=expected_signed_seed_ids,
    )


def validate_v3_stopped(
    active_campaign_dir: Path,
    expected_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture a stopped V3 campaign and enforce its immutable protocol identity."""

    snapshot = protocol.capture_active_campaign_identity(active_campaign_dir)
    directory = Path(snapshot["path"])
    if expected_binding is not None and (
        str(expected_binding.get("path") or "") != snapshot["path"]
        or expected_binding.get("manifest_file") != snapshot["manifest_file"]
        or expected_binding.get("identity") != snapshot["identity"]
        or expected_binding.get("identity_signature") != snapshot["identity_signature"]
    ):
        raise ValueError("Named V3 campaign does not match the protocol binding")
    manifest_path = directory / V3_MANIFEST_FILE
    manifest, manifest_sha256 = protocol.read_json_snapshot(manifest_path)
    if manifest_sha256 != snapshot["manifest_sha256_at_capture"]:
        raise RuntimeError("V3 manifest changed while its stopped state was captured")
    status = str(manifest.get("status") or "")
    active_pid = _int(manifest.get("active_process_id"), -1)
    if status not in {"paused_preliminary", "complete"} or active_pid != 0:
        raise RuntimeError(
            "Comparison execution is blocked until V3 is paused at its checkpoint or complete"
        )
    checkpoint_path = directory / V3_CHECKPOINT_FILE
    if not checkpoint_path.is_file() or checkpoint_path.is_symlink():
        raise ValueError("Stopped V3 campaign lacks its preliminary checkpoint")
    checkpoint, checkpoint_hash = protocol.read_json_snapshot(checkpoint_path)
    signed_seed_ids = manifest.get("signed_full_seed_ids")
    if not isinstance(signed_seed_ids, list) or not all(
        isinstance(seed, int) and not isinstance(seed, bool) for seed in signed_seed_ids
    ):
        raise ValueError("V3 manifest lacks its signed seed schedule")
    validated_checkpoint = _authoritative_v3_checkpoint_validation(
        output_dir=directory,
        runner_signature=str(manifest.get("runner_signature") or ""),
        plan_manifest_sha256=str(manifest.get("plan_manifest_sha256") or ""),
        require_live_ledger_match=status == "paused_preliminary",
        expected_signed_seed_ids=signed_seed_ids,
    )
    if validated_checkpoint is None:
        raise ValueError("Stopped V3 campaign checkpoint was not validated")
    checkpoint_signature = str(checkpoint.get("checkpoint_signature") or "")
    checkpoint_history = manifest.get("checkpoint_history")
    history_match = isinstance(checkpoint_history, list) and any(
        isinstance(item, dict)
        and item.get("checkpoint_manifest") == V3_CHECKPOINT_FILE
        and item.get("checkpoint_signature") == checkpoint_signature
        and item.get("completed_seed_count")
        == v3_runner.PRELIMINARY_CHECKPOINT_REPEAT_COUNT
        and item.get("completed_seed_ids")
        == signed_seed_ids[: v3_runner.PRELIMINARY_CHECKPOINT_REPEAT_COUNT]
        for item in checkpoint_history
    )
    semantic_links = {
        "checkpoint_schema": checkpoint.get("schema_version")
        == v3_runner.PRELIMINARY_CHECKPOINT_SCHEMA,
        "checkpoint_internal_signature": (
            bool(checkpoint_signature)
            and protocol.stable_sha256(
                {
                    key: value
                    for key, value in checkpoint.items()
                    if key != "checkpoint_signature"
                }
            )
            == checkpoint_signature
        ),
        "runner_signature": checkpoint.get("runner_signature")
        == manifest.get("runner_signature"),
        "plan_signature": checkpoint.get("plan_signature")
        == manifest.get("plan_signature"),
        "plan_manifest_sha256": checkpoint.get("plan_manifest_sha256")
        == manifest.get("plan_manifest_sha256"),
        "runner_builder_sha256": checkpoint.get("runner_builder_sha256")
        == manifest.get("runner_script_sha256"),
        "planner_builder_sha256": checkpoint.get("planner_builder_sha256")
        == manifest.get("planner_script_sha256"),
        "priority_selection_lineage_sha256": checkpoint.get(
            "priority_selection_lineage_sha256"
        )
        == manifest.get("priority_selection_lineage_sha256"),
        "seed_scheduling_policy": checkpoint.get("seed_scheduling_policy")
        == manifest.get("seed_scheduling_policy"),
        "signed_seed_schedule": checkpoint.get("signed_full_seed_ids")
        == signed_seed_ids,
        "completed_seed_prefix": checkpoint.get("completed_seed_ids")
        == signed_seed_ids[: v3_runner.PRELIMINARY_CHECKPOINT_REPEAT_COUNT],
        "checkpoint_repeat_count": (
            manifest.get("checkpoint_after_repetitions")
            == v3_runner.PRELIMINARY_CHECKPOINT_REPEAT_COUNT
            and checkpoint.get("completed_seed_count")
            == v3_runner.PRELIMINARY_CHECKPOINT_REPEAT_COUNT
        ),
        "checkpoint_filename": manifest.get("preliminary_checkpoint_manifest")
        == V3_CHECKPOINT_FILE,
        "checkpoint_file_sha256": manifest.get("preliminary_checkpoint_manifest_sha256")
        == checkpoint_hash,
        "checkpoint_history": history_match,
    }
    if status == "paused_preliminary":
        ledger_path = directory / LEDGER_FILE
        semantic_links.update(
            {
                "paused_completed_seed_count": manifest.get("completed_seed_count")
                == checkpoint.get("completed_seed_count"),
                "paused_completed_seed_ids": manifest.get("completed_seed_ids")
                == checkpoint.get("completed_seed_ids"),
                "paused_ledger_case_count": manifest.get("ledger_case_count")
                == checkpoint.get("ledger_evidence_case_count"),
                "paused_ledger_hash_count": manifest.get(
                    "ledger_case_file_sha256_count"
                )
                == checkpoint.get("ledger_evidence_case_count"),
                "paused_execution_ledger_sha256": (
                    ledger_path.is_file()
                    and not ledger_path.is_symlink()
                    and manifest.get("execution_ledger_sha256")
                    == checkpoint.get("execution_ledger_sha256_at_checkpoint")
                    == _sha256(ledger_path)
                ),
                "paused_executed_engine_count": manifest.get(
                    "executed_engine_case_count"
                )
                == checkpoint.get("executed_engine_physical_run_count"),
                "paused_remaining_engine_count": manifest.get(
                    "remaining_engine_physical_run_count"
                )
                == checkpoint.get("remaining_engine_physical_run_count"),
            }
        )
    if validated_checkpoint.get(
        "checkpoint_signature"
    ) != checkpoint_signature or not all(semantic_links.values()):
        failed = sorted(key for key, value in semantic_links.items() if not value)
        raise ValueError(
            "V3 checkpoint does not belong to the stopped campaign manifest: "
            + ", ".join(failed)
        )
    return {
        "path": str(directory),
        "manifest_file": snapshot["manifest_file"],
        "manifest_sha256": snapshot["manifest_sha256_at_capture"],
        "identity": snapshot["identity"],
        "identity_signature": snapshot["identity_signature"],
        "status": status,
        "active_process_id": active_pid,
        "checkpoint_sha256": checkpoint_hash,
        "checkpoint_status": str(checkpoint.get("status") or ""),
        "checkpoint_signature": checkpoint_signature,
        "checkpoint_semantic_membership_validated": True,
        "checkpoint_live_ledger_exact_match_required": status == "paused_preliminary",
    }


def build_engine_command(
    case: PlannedCase, validated: protocol.ValidatedProtocol, case_dir: Path
) -> list[str]:
    profile = _variant_profile(validated, case.variant_id)
    lot_arguments = (
        ["--lot-trace"]
        if case.seed == protocol.LOT_TRACE_SEED
        else ["--no-lot-trace", "--skip-lot-audit"]
    )
    return [
        sys.executable,
        str(validated.engine),
        "--input",
        str(validated.graph),
        "--output-dir",
        str(case_dir),
        "--scenario-id",
        "scn:BASE",
        "--days",
        str(protocol.MEASURED_DAYS),
        "--seed",
        str(case.seed),
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        *lot_arguments,
        "--common-random-numbers",
        "--supplier-neutral-floors-csv",
        str(validated.supplier_floors),
        *protocol.profile_args(profile),
        *protocol.MANAGED_PROTOCOL_ARGS,
    ]


def _require_complete_daily_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    pair_keys: Sequence[str],
    label: str,
) -> dict[str, list[Mapping[str, Any]]]:
    expected_days = set(range(protocol.MEASURED_DAYS))
    grouped: dict[str, list[Mapping[str, Any]]] = {key: [] for key in pair_keys}
    for row in rows:
        key = f"{row.get('node_id')}|{row.get('item_id')}"
        if key in grouped:
            grouped[key].append(row)
    for key, group in grouped.items():
        days = [_int(row.get("day")) for row in group]
        if (
            len(group) != protocol.MEASURED_DAYS
            or set(days) != expected_days
            or len(days) != len(set(days))
        ):
            raise ValueError(f"Incomplete or duplicate {label} series: {key}")
    return grouped


def _finite_nonnegative(row: Mapping[str, Any], field: str, label: str) -> float:
    value = _float(row.get(field))
    if not math.isfinite(value) or value < -ZERO_EPS:
        raise ValueError(f"Invalid {field} in {label}")
    return max(0.0, value)


def _material_metrics(
    case_dir: Path,
    validated: protocol.ValidatedProtocol,
    variant_id: str,
) -> list[dict[str, Any]]:
    pair_keys = [row.pair_key for row in validated.materials]
    graph = _read_json(validated.graph)
    node_types = {
        str(node.get("id") or ""): str(node.get("type") or "")
        for node in graph.get("nodes") or []
    }
    source_nodes_by_pair: dict[str, set[str]] = {key: set() for key in pair_keys}
    for edge in graph.get("edges") or []:
        destination = str(edge.get("to") or "")
        source = str(edge.get("from") or "")
        for item_id in edge.get("items") or []:
            key = f"{destination}|{item_id}"
            if key in source_nodes_by_pair:
                source_nodes_by_pair[key].add(source)
    stocks = _require_complete_daily_rows(
        _read_csv(case_dir / "data" / "production_input_stocks_daily.csv"),
        pair_keys=pair_keys,
        label="stock",
    )
    arrivals = _require_complete_daily_rows(
        _read_csv(
            case_dir / "data" / "production_input_replenishment_arrivals_daily.csv"
        ),
        pair_keys=pair_keys,
        label="arrival",
    )
    traces = _require_complete_daily_rows(
        _read_csv(case_dir / "data" / "mrp_trace_daily.csv"),
        pair_keys=pair_keys,
        label="MRP trace",
    )
    order_rows = _read_csv(case_dir / "data" / "mrp_orders_daily.csv")
    shipment_rows = _read_csv(
        case_dir / "data" / "production_supplier_shipments_daily.csv"
    )
    supplier_parameter_rows = _read_csv(
        case_dir / "data" / "supplier_nominal_parameters.csv"
    )
    bom_requirements = _bom_requirements(validated)
    output_pair_keys = sorted(
        {
            f"{node_id}|{output_item_id}"
            for requirements in bom_requirements.values()
            for node_id, output_item_id, _ratio in requirements
        }
    )
    production_outputs = _require_complete_daily_rows(
        _read_csv(case_dir / "data" / "production_output_products_daily.csv"),
        pair_keys=output_pair_keys,
        label="executed production",
    )
    executed_by_output: dict[str, list[float]] = {}
    for output_key, rows in production_outputs.items():
        ordered = sorted(rows, key=lambda row: _int(row.get("day")))
        executed_by_output[output_key] = [
            _finite_nonnegative(
                row,
                "executed_qty",
                f"executed production/{output_key}",
            )
            for row in ordered
        ]
    orders: dict[str, list[Mapping[str, Any]]] = {key: [] for key in pair_keys}
    shipments: dict[str, list[Mapping[str, Any]]] = {key: [] for key in pair_keys}
    supplier_parameters: dict[str, list[Mapping[str, Any]]] = {
        key: [] for key in pair_keys
    }
    for row in order_rows:
        key = f"{row.get('node_id')}|{row.get('item_id')}"
        day = _int(row.get("day"))
        if key in orders and 0 <= day < protocol.MEASURED_DAYS:
            orders[key].append(row)
    for row in shipment_rows:
        key = f"{row.get('dst_node_id')}|{row.get('item_id')}"
        day = _int(row.get("risk_decision_day", row.get("day")))
        if key in shipments and 0 <= day < protocol.MEASURED_DAYS:
            shipments[key].append(row)
    for row in supplier_parameter_rows:
        key = f"{row.get('dst_node_id')}|{row.get('item_id')}"
        if key in supplier_parameters:
            supplier_parameters[key].append(row)
    result: list[dict[str, Any]] = []
    for material in validated.materials:
        key = material.pair_key
        stock_group = sorted(stocks[key], key=lambda row: _int(row.get("day")))
        arrival_group = sorted(arrivals[key], key=lambda row: _int(row.get("day")))
        trace_group = sorted(traces[key], key=lambda row: _int(row.get("day")))
        stock_before = [
            _finite_nonnegative(row, "stock_before_production", f"stock/{key}")
            for row in stock_group
        ]
        stock_end = [
            _finite_nonnegative(row, "stock_end_of_day", f"stock/{key}")
            for row in stock_group
        ]
        consumption: list[float] = []
        for before, end in zip(stock_before, stock_end, strict=True):
            used = before - end
            if used < -1e-6:
                raise ValueError(
                    f"Stock rises during production accounting step: {key}"
                )
            consumption.append(max(0.0, used))
        arrived = [
            _finite_nonnegative(row, "arrived_qty", f"arrival/{key}")
            for row in arrival_group
        ]
        uoms = {str(row.get("uom") or "") for row in arrival_group}
        if {_normalise_uom(value) for value in uoms} != {_normalise_uom(material.uom)}:
            raise ValueError(f"Material unit mismatch: {key}/{uoms}")
        opening_stock_before_day0_arrival = stock_before[0] - arrived[0]
        if opening_stock_before_day0_arrival < -BALANCE_ABS_TOL:
            raise ValueError(f"Day-0 arrival exceeds stock before production: {key}")
        opening_stock_before_day0_arrival = max(0.0, opening_stock_before_day0_arrival)
        stock_balance_residuals = [0.0]
        for day in range(1, protocol.MEASURED_DAYS):
            expected_before = stock_end[day - 1] + arrived[day]
            residual = stock_before[day] - expected_before
            stock_balance_residuals.append(residual)
            if not _close(stock_before[day], expected_before):
                raise ValueError(
                    "Material stock balance failed "
                    f"for {key} at day {day}: previous_end+arrival="
                    f"{expected_before}, before_production={stock_before[day]}"
                )
        expected_consumption: list[float] = []
        for day in range(protocol.MEASURED_DAYS):
            expected_consumption.append(
                sum(
                    executed_by_output[f"{node_id}|{output_item_id}"][day]
                    * requirement_per_output_unit
                    for node_id, output_item_id, requirement_per_output_unit in bom_requirements[
                        key
                    ]
                )
            )
        bom_residuals: list[float] = []
        for day, (actual, expected) in enumerate(
            zip(consumption, expected_consumption, strict=True)
        ):
            residual = actual - expected
            bom_residuals.append(residual)
            if not _close(actual, expected):
                raise ValueError(
                    "BOM consumption balance failed "
                    f"for {key} at day {day}: stock_consumption={actual}, "
                    f"BOM_times_executed_production={expected} {material.uom}"
                )
        targets = [
            _finite_nonnegative(row, "target_stock_qty", f"MRP trace/{key}")
            for row in trace_group
        ]
        signals = [
            _finite_nonnegative(row, "target_demand_signal_qty", f"MRP trace/{key}")
            for row in trace_group
        ]
        backlogs = [
            _finite_nonnegative(row, "bb_backlog_qty", f"MRP trace/{key}")
            for row in trace_group
        ]
        relevant_orders = orders[key]
        j0_orders = [row for row in relevant_orders if _int(row.get("day")) == 0]
        release_quantities = [
            _finite_nonnegative(row, "release_qty", f"MRP order/{key}")
            for row in relevant_orders
        ]
        receipt_quantities = [
            _finite_nonnegative(row, "planned_receipt_qty", f"MRP order/{key}")
            for row in relevant_orders
        ]
        consumption_total = sum(consumption)
        consumption_daily = consumption_total / protocol.MEASURED_DAYS
        mean_target = fmean(targets)
        signal_daily = fmean(signals)
        day0_arrival = arrived[0]
        relevant_shipments = shipments[key]
        shipped_quantities = [
            _finite_nonnegative(row, "shipped_qty", f"supplier shipment/{key}")
            for row in relevant_shipments
        ]
        positive_shipment_count = sum(value > ZERO_EPS for value in shipped_quantities)
        arriving_in_horizon_rows = [
            row
            for row in relevant_shipments
            if 0 <= _int(row.get("arrival_day")) < protocol.MEASURED_DAYS
        ]
        shipment_arriving_in_horizon_qty = sum(
            _finite_nonnegative(
                row,
                "shipped_qty",
                f"supplier shipment arriving in horizon/{key}",
            )
            for row in arriving_in_horizon_rows
        )
        shipment_uoms = {
            _normalise_uom(row.get("uom")) for row in arriving_in_horizon_rows
        }
        if shipment_uoms and shipment_uoms != {_normalise_uom(material.uom)}:
            raise ValueError(
                f"Supplier shipment unit mismatch: {key}/{sorted(shipment_uoms)}"
            )
        arrival_minus_recorded_shipment = (
            sum(arrived) - shipment_arriving_in_horizon_qty
        )
        if arrival_minus_recorded_shipment < -max(
            BALANCE_ABS_TOL,
            BALANCE_REL_TOL * max(sum(arrived), shipment_arriving_in_horizon_qty),
        ):
            raise ValueError(
                "Recorded in-horizon supplier shipments exceed material arrivals "
                f"for {key}: arrivals={sum(arrived)}, shipments="
                f"{shipment_arriving_in_horizon_qty}"
            )
        stock_cover = (
            stock_before[0] / consumption_daily
            if consumption_daily > ZERO_EPS
            else math.nan
        )
        requirement_to_consumption = (
            signal_daily / consumption_daily
            if consumption_daily > ZERO_EPS
            else math.nan
        )
        if consumption_daily <= ZERO_EPS and signal_daily <= ZERO_EPS:
            ratio_status = "not_evaluable_zero_signal_and_zero_consumption"
        elif consumption_daily <= ZERO_EPS:
            ratio_status = "alert_signal_without_consumption"
        elif signal_daily <= ZERO_EPS:
            ratio_status = "alert_zero_signal_with_consumption"
        elif 0.5 <= requirement_to_consumption <= 2.0:
            ratio_status = "within_diagnostic_band_0p5_2"
        else:
            ratio_status = "alert_outside_diagnostic_band_0p5_2"
        parameter_rows = supplier_parameters[key]
        source_nodes = source_nodes_by_pair[key]
        if not source_nodes:
            raise ValueError(f"No source lane in graph for material: {key}")
        external_supplier_lane = any(
            node_types.get(source) != "factory" for source in source_nodes
        )
        if not parameter_rows and external_supplier_lane:
            raise ValueError(f"No supplier nominal parameter row for material: {key}")
        dynamic_basis_count = 0
        explicit_capacity_count = 0
        zero_signal_basis_count = 0
        unexpected_static_basis_count = 0
        supplier_ids: set[str] = set()
        capacity_bases: set[str] = set()
        external_procurement_capacity_bases: set[str] = set()
        external_procurement_capacity_profiles: set[str] = set()
        nominal_capacities: list[float] = []
        effective_capacities: list[float] = []
        applied_capacity_scales: list[float] = []
        explicit_capacities: list[float] = []
        process_capacities: list[float] = []
        downstream_requirements: list[float] = []
        downstream_signals: list[float] = []
        upstream_daily_needs: list[float] = []
        upstream_nominal_capacities: list[float] = []
        upstream_target_utilizations: list[float] = []
        upstream_pipeline_targets: list[float] = []
        upstream_initial_pipeline_seeds: list[float] = []
        for parameter in parameter_rows:
            basis = str(parameter.get("capacity_basis") or "")
            supplier_id = str(parameter.get("supplier_id") or "")
            if not supplier_id:
                raise ValueError(f"Supplier parameter lacks supplier_id: {key}")
            supplier_ids.add(supplier_id)
            capacity_bases.add(basis)
            external_procurement_capacity_bases.add(
                str(parameter.get("external_procurement_capacity_basis") or "")
            )
            external_procurement_capacity_profiles.add(
                str(parameter.get("external_procurement_capacity_profile") or "")
            )
            row_signal = _finite_nonnegative(
                parameter,
                "downstream_signal_qty_per_day",
                f"supplier nominal parameters/{key}",
            )
            explicit_capacity = _finite_nonnegative(
                parameter,
                "explicit_capacity_qty_per_day",
                f"supplier nominal parameters/{key}",
            )
            nominal_capacities.append(
                _finite_nonnegative(
                    parameter,
                    "nominal_capacity_qty_per_day",
                    f"supplier nominal parameters/{key}",
                )
            )
            effective_capacities.append(
                _finite_nonnegative(
                    parameter,
                    "effective_capacity_qty_per_day",
                    f"supplier nominal parameters/{key}",
                )
            )
            applied_capacity_scales.append(
                _finite_nonnegative(
                    parameter,
                    "applied_capacity_scale",
                    f"supplier nominal parameters/{key}",
                )
            )
            explicit_capacities.append(explicit_capacity)
            process_capacities.append(
                _finite_nonnegative(
                    parameter,
                    "process_capacity_qty_per_day",
                    f"supplier nominal parameters/{key}",
                )
            )
            downstream_requirements.append(
                _finite_nonnegative(
                    parameter,
                    "downstream_requirement_qty_per_day",
                    f"supplier nominal parameters/{key}",
                )
            )
            downstream_signals.append(row_signal)
            upstream_daily_needs.append(
                _finite_nonnegative(
                    parameter,
                    "external_procurement_daily_need_qty",
                    f"supplier nominal parameters/{key}",
                )
            )
            upstream_nominal_capacities.append(
                _finite_nonnegative(
                    parameter,
                    "external_procurement_nominal_capacity_qty_per_day",
                    f"supplier nominal parameters/{key}",
                )
            )
            upstream_target_utilizations.append(
                _finite_nonnegative(
                    parameter,
                    "external_procurement_target_utilization",
                    f"supplier nominal parameters/{key}",
                )
            )
            upstream_pipeline_targets.append(
                _finite_nonnegative(
                    parameter,
                    "external_procurement_pipeline_target_qty",
                    f"supplier nominal parameters/{key}",
                )
            )
            upstream_initial_pipeline_seeds.append(
                _finite_nonnegative(
                    parameter,
                    "external_procurement_initial_pipeline_seed_qty",
                    f"supplier nominal parameters/{key}",
                )
            )
            if basis.startswith("propagated_dynamic_demand"):
                dynamic_basis_count += 1
            elif explicit_capacity > ZERO_EPS or basis.startswith(
                "supplier_capacity_override_from_csv"
            ):
                explicit_capacity_count += 1
            elif row_signal <= ZERO_EPS and basis.startswith("inventory_fallback"):
                zero_signal_basis_count += 1
            else:
                unexpected_static_basis_count += 1
        result.append(
            {
                "node_id": material.node_id,
                "item_id": material.item_id,
                "pair_key": key,
                "uom": material.uom,
                "safety_time_days": material.safety_time_days,
                "requirement_mode_in_variant": _variant_requirement_mode(
                    variant_id, key
                ),
                "stock_J0_before_production_qty": stock_before[0],
                "stock_before_day0_arrival_qty": opening_stock_before_day0_arrival,
                "stock_end_min_qty": min(stock_end),
                "stock_end_mean_qty": fmean(stock_end),
                "zero_stock_day_count": sum(value <= ZERO_EPS for value in stock_end),
                "consumption_total_qty": consumption_total,
                "consumption_daily_mean_qty": consumption_daily,
                "bom_expected_consumption_total_qty": sum(expected_consumption),
                "bom_consumption_max_abs_residual_qty": max(
                    abs(value) for value in bom_residuals
                ),
                "bom_consumption_balance_valid": True,
                "bom_consumption_balance_basis": (
                    "daily_executed_output_qty_times_graph_ratio_per_batch_"
                    "converted_to_material_inventory_uom"
                ),
                "arrival_total_qty": sum(arrived),
                "arrival_positive_day_count": sum(
                    value > ZERO_EPS for value in arrived
                ),
                "day0_boundary_arrival_qty": day0_arrival,
                "day0_boundary_arrival_included_in_stock_J0": True,
                "stock_balance_max_abs_residual_qty_J1_J719": max(
                    abs(value) for value in stock_balance_residuals[1:]
                ),
                "stock_balance_valid_J1_J719": True,
                "stock_balance_equation": (
                    "stock_end_day_minus_1_plus_arrival_day_minus_"
                    "bom_consumption_day_equals_stock_end_day"
                ),
                "mrp_order_row_count": len(relevant_orders),
                "mrp_order_J0_row_count": len(j0_orders),
                "mrp_order_J0_release_qty": sum(
                    _finite_nonnegative(row, "release_qty", f"MRP order J0/{key}")
                    for row in j0_orders
                ),
                "mrp_order_J0_planned_receipt_qty": sum(
                    _finite_nonnegative(
                        row, "planned_receipt_qty", f"MRP order J0/{key}"
                    )
                    for row in j0_orders
                ),
                "mrp_release_total_qty": sum(release_quantities),
                "mrp_planned_receipt_total_qty": sum(receipt_quantities),
                "mrp_target_stock_J0_qty": targets[0],
                "mrp_target_stock_mean_qty": mean_target,
                "mrp_target_stock_median_qty": _percentile(targets, 0.5),
                "mrp_target_stock_p95_qty": _percentile(targets, 0.95),
                "mrp_target_stock_max_qty": max(targets),
                "mrp_target_demand_signal_daily_mean_qty": signal_daily,
                "mrp_target_demand_signal_median_qty": _percentile(signals, 0.5),
                "mrp_target_demand_signal_p95_qty": _percentile(signals, 0.95),
                "mrp_target_demand_signal_max_qty": max(signals),
                "mrp_backlog_J0_qty": backlogs[0],
                "mrp_backlog_max_qty": max(backlogs),
                "target_stock_mean_to_consumption_daily_mean_days": (
                    mean_target / consumption_daily
                    if consumption_daily > ZERO_EPS
                    else math.nan
                ),
                "consumption_observation_status": (
                    "positive_consumption_observed"
                    if consumption_daily > ZERO_EPS
                    else "zero_consumption_observed"
                ),
                "mrp_demand_signal_status": (
                    "positive_signal_observed"
                    if signal_daily > ZERO_EPS
                    else "zero_signal_observed"
                ),
                "stock_J0_cover_days": stock_cover,
                "stock_J0_cover_status": (
                    "evaluable_positive_consumption"
                    if consumption_daily > ZERO_EPS
                    else "not_evaluable_zero_consumption"
                ),
                "stock_J0_covers_measured_horizon": (
                    stock_cover >= protocol.MEASURED_DAYS
                    if math.isfinite(stock_cover)
                    else False
                ),
                "requirement_signal_to_consumption_ratio": requirement_to_consumption,
                "requirement_signal_to_consumption_diagnostic": ratio_status,
                "j0_pipeline_qty": None,
                "j0_pipeline_cover_days": None,
                "j0_pipeline_quantification_status": (
                    "not_evaluable_engine_exports_boundary_digest_only"
                ),
                "future_supplier_lane_shipment_row_count": len(relevant_shipments),
                "future_supplier_lane_positive_shipment_count": positive_shipment_count,
                "future_supplier_lane_shipped_qty": sum(shipped_quantities),
                "supplier_shipment_arriving_J0_J719_row_count": len(
                    arriving_in_horizon_rows
                ),
                "supplier_shipment_arriving_J0_J719_qty": (
                    shipment_arriving_in_horizon_qty
                ),
                "supplier_arrival_minus_recorded_shipment_qty": max(
                    0.0, arrival_minus_recorded_shipment
                ),
                "supplier_arrival_reconciliation_status": (
                    "bounded_not_exact_opening_pipeline_quantities_not_exported"
                ),
                "supplier_arrival_reconciliation_scope": (
                    "recorded_shipments_decided_J0_J719_with_arrival_day_J0_J719_"
                    "are_a_lower_bound; arrivals_from_pre_J0_pipeline_cannot_be_"
                    "separated_by_pair"
                ),
                "supplier_risk_scope": (
                    "external_supplier_lane"
                    if external_supplier_lane
                    else "internal_upstream_transfer_not_supplier_risk"
                ),
                "supplier_risk_flow_evaluable": (
                    external_supplier_lane and positive_shipment_count > 0
                ),
                "supplier_risk_flow_evaluability_reason": (
                    "positive_future_supplier_shipment_observed_J0_J719"
                    if external_supplier_lane and positive_shipment_count > 0
                    else (
                        "not_evaluable_no_positive_future_supplier_shipment_J0_J719"
                        if external_supplier_lane
                        else "not_applicable_internal_upstream_transfer"
                    )
                ),
                "supplier_parameter_status": (
                    "available_external_supplier_rows"
                    if parameter_rows
                    else "not_applicable_internal_upstream_transfer"
                ),
                "supplier_parameter_row_count": len(parameter_rows),
                "supplier_ids": "|".join(sorted(supplier_ids)),
                "supplier_capacity_bases": "|".join(sorted(capacity_bases)),
                "supplier_direct_nominal_capacity_total_qty_per_day": sum(
                    nominal_capacities
                ),
                "supplier_direct_effective_capacity_total_qty_per_day": sum(
                    effective_capacities
                ),
                "supplier_applied_capacity_scale_min": (
                    min(applied_capacity_scales)
                    if applied_capacity_scales
                    else math.nan
                ),
                "supplier_applied_capacity_scale_max": (
                    max(applied_capacity_scales)
                    if applied_capacity_scales
                    else math.nan
                ),
                "supplier_explicit_capacity_total_qty_per_day": sum(
                    explicit_capacities
                ),
                "supplier_process_capacity_total_qty_per_day": sum(process_capacities),
                "supplier_downstream_requirement_lane_row_sum_qty_per_day": sum(
                    downstream_requirements
                ),
                "supplier_downstream_requirement_pair_qty_per_day": (
                    downstream_requirements[0] if downstream_requirements else math.nan
                ),
                "supplier_downstream_requirement_pair_min_qty_per_day": (
                    min(downstream_requirements)
                    if downstream_requirements
                    else math.nan
                ),
                "supplier_downstream_requirement_pair_max_qty_per_day": (
                    max(downstream_requirements)
                    if downstream_requirements
                    else math.nan
                ),
                "supplier_downstream_requirement_pair_values_all_equal": (
                    bool(downstream_requirements)
                    and all(
                        _close(value, downstream_requirements[0])
                        for value in downstream_requirements[1:]
                    )
                ),
                "supplier_downstream_signal_lane_row_sum_qty_per_day": sum(
                    downstream_signals
                ),
                "supplier_downstream_signal_pair_qty_per_day": (
                    downstream_signals[0] if downstream_signals else math.nan
                ),
                "supplier_downstream_signal_pair_min_qty_per_day": (
                    min(downstream_signals) if downstream_signals else math.nan
                ),
                "supplier_downstream_signal_pair_max_qty_per_day": (
                    max(downstream_signals) if downstream_signals else math.nan
                ),
                "supplier_downstream_signal_pair_values_all_equal": (
                    bool(downstream_signals)
                    and all(
                        _close(value, downstream_signals[0])
                        for value in downstream_signals[1:]
                    )
                ),
                "external_procurement_daily_need_total_qty": sum(upstream_daily_needs),
                "external_procurement_nominal_capacity_total_qty_per_day": sum(
                    upstream_nominal_capacities
                ),
                "external_procurement_target_utilization_min": (
                    min(upstream_target_utilizations)
                    if upstream_target_utilizations
                    else math.nan
                ),
                "external_procurement_target_utilization_max": (
                    max(upstream_target_utilizations)
                    if upstream_target_utilizations
                    else math.nan
                ),
                "external_procurement_capacity_bases": "|".join(
                    sorted(external_procurement_capacity_bases)
                ),
                "external_procurement_capacity_profiles": "|".join(
                    sorted(external_procurement_capacity_profiles)
                ),
                "external_procurement_pipeline_target_total_qty": sum(
                    upstream_pipeline_targets
                ),
                "external_procurement_initial_pipeline_seed_total_qty": sum(
                    upstream_initial_pipeline_seeds
                ),
                "supplier_capacity_dynamic_signal_basis_row_count": dynamic_basis_count,
                "supplier_capacity_explicit_override_row_count": explicit_capacity_count,
                "supplier_capacity_zero_signal_fallback_row_count": zero_signal_basis_count,
                "supplier_capacity_unexpected_static_basis_row_count": (
                    unexpected_static_basis_count
                ),
            }
        )
    return result


def _system_metrics(
    case_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    service_rows = _read_csv(case_dir / "data" / "production_demand_service_daily.csv")
    service = campaign_core.compute_service_metrics(
        service_rows,
        client_node_id="C-XXXXX",
        products=PRODUCTS,
        days=protocol.MEASURED_DAYS,
    )
    service_result: list[dict[str, Any]] = []
    for product in PRODUCTS:
        row = service[product]
        if (
            row.get("horizon_complete") is not True
            or row.get("horizon_day_count") != protocol.MEASURED_DAYS
        ):
            raise ValueError(f"Incomplete client service series: {product}")
        daily_rows = sorted(
            (
                item
                for item in service_rows
                if str(item.get("node_id") or "") == "C-XXXXX"
                and str(item.get("item_id") or "") == f"item:{product}"
            ),
            key=lambda item: _int(item.get("day")),
        )
        days = [_int(item.get("day")) for item in daily_rows]
        if len(daily_rows) != protocol.MEASURED_DAYS or days != list(
            range(protocol.MEASURED_DAYS)
        ):
            raise ValueError(f"Incomplete or duplicate daily client demand: {product}")
        daily_demand = [
            _finite_nonnegative(item, "demand_qty", f"client demand/{product}")
            for item in daily_rows
        ]
        if sum(daily_demand) <= ZERO_EPS:
            raise ValueError(
                f"Client demand must be positive over the horizon: {product}"
            )
        demand_qty = _float(row.get("demand_qty"))
        fill_rate = _float(row.get("fill_rate"))
        on_due_service = _float(row.get("on_due_volume_proxy"))
        backlog_qty_days = _float(row.get("backlog_qty_days"))
        backlog_end_qty = _float(row.get("backlog_end_qty"))
        if (
            not math.isfinite(demand_qty)
            or demand_qty <= ZERO_EPS
            or not _close(demand_qty, sum(daily_demand))
            or not math.isfinite(fill_rate)
            or not -ZERO_EPS <= fill_rate <= 1.0 + ZERO_EPS
            or not math.isfinite(on_due_service)
            or not -ZERO_EPS <= on_due_service <= 1.0 + ZERO_EPS
            or not math.isfinite(backlog_qty_days)
            or backlog_qty_days < -ZERO_EPS
            or not math.isfinite(backlog_end_qty)
            or backlog_end_qty < -ZERO_EPS
        ):
            raise ValueError(f"Invalid client service values: {product}")
        daily_demand_signature = _stable_sha256(
            [
                {"day": day, "demand_qty": format(value, ".17g")}
                for day, value in enumerate(daily_demand)
            ]
        )
        service_result.append(
            {
                "product_id": product,
                "demand_qty": demand_qty,
                "daily_demand_signature": daily_demand_signature,
                "daily_demand_positive_day_count": sum(
                    value > ZERO_EPS for value in daily_demand
                ),
                "daily_demand_min_qty": min(daily_demand),
                "daily_demand_max_qty": max(daily_demand),
                "fill_rate": min(1.0, max(0.0, fill_rate)),
                "on_due_service": min(1.0, max(0.0, on_due_service)),
                "backlog_qty_days": max(0.0, backlog_qty_days),
                "backlog_end_qty": max(0.0, backlog_end_qty),
            }
        )
    production_rows = _read_csv(
        case_dir / "data" / "production_output_products_daily.csv"
    )
    production_result: list[dict[str, Any]] = []
    expected = {("M-1810", "item:268091"), ("M-1430", "item:268967")}
    for node_id, item_id in sorted(expected):
        rows = [
            row
            for row in production_rows
            if row.get("node_id") == node_id and row.get("item_id") == item_id
        ]
        days = [_int(row.get("day")) for row in rows]
        if len(rows) != protocol.MEASURED_DAYS or set(days) != set(
            range(protocol.MEASURED_DAYS)
        ):
            raise ValueError(f"Incomplete production series: {node_id}|{item_id}")
        released = [
            _finite_nonnegative(row, "released_qty", f"production/{node_id}|{item_id}")
            for row in rows
        ]
        executed = [
            _finite_nonnegative(row, "executed_qty", f"production/{node_id}|{item_id}")
            for row in rows
        ]
        production_result.append(
            {
                "node_id": node_id,
                "product_id": item_id.replace("item:", ""),
                "released_production_qty": sum(released),
                "executed_production_qty": sum(executed),
            }
        )
    return service_result, production_result


def _validate_summary(
    summary: Mapping[str, Any], case: PlannedCase, validated: protocol.ValidatedProtocol
) -> None:
    policy = summary.get("policy") or {}
    initialization = policy.get("initialization_policy") or {}
    supplier_risk = policy.get("supplier_risk") or {}
    state_risk = policy.get("supplier_state_dependent_risk") or {}
    floors = policy.get("supplier_neutral_floor_test") or {}
    warmup = policy.get("warmup_boundary_audit") or {}
    expected_static = (
        sorted(
            set((validated.manifest.get("material_scope") or {}).get("pair_keys") or [])
            - set(protocol.EXPLICIT_DYNAMIC_PAIRS)
        )
        if case.variant_id == protocol.OLD_VARIANT_ID
        else []
    )
    actual_static = sorted(initialization.get("mrp_static_requirement_pairs") or [])
    expected_dynamic = (
        sorted(protocol.EXPLICIT_DYNAMIC_PAIRS)
        if case.variant_id == protocol.OLD_VARIANT_ID
        else sorted(
            (validated.manifest.get("material_scope") or {}).get("pair_keys") or []
        )
    )
    actual_dynamic = sorted(initialization.get("mrp_dynamic_requirement_pairs") or [])
    if (
        summary.get("input_sha256") != _sha256(validated.graph)
        or _int(summary.get("sim_days")) != protocol.MEASURED_DAYS
        or _int(policy.get("seed")) != case.seed
        or not _bool(policy.get("common_random_numbers"))
        or _bool(policy.get("lot_trace_enabled"))
        is not (case.seed == protocol.LOT_TRACE_SEED)
        or _int(warmup.get("physical_warmup_days")) != protocol.WARMUP_DAYS
        or not str(warmup.get("core_state_sha256") or "")
        or not str((warmup.get("component_sha256") or {}).get("pipeline") or "")
        or actual_static != expected_static
        or actual_dynamic != expected_dynamic
        or sorted(initialization.get("mrp_smoothed_cover_requirement_pairs") or [])
        != sorted(protocol.SMOOTHED_COVER_PAIRS)
        or not _bool(initialization.get("use_bom_demand_signal_for_mrp"))
        or _bool(initialization.get("mrp_static_fallback_for_propagated_pairs"))
        or _bool(supplier_risk.get("enabled"))
        or _int(supplier_risk.get("event_count"), 0) != 0
        or supplier_risk.get("warnings")
        or _bool(state_risk.get("enabled"))
        or not _bool(floors.get("enabled"))
        or Path(str(floors.get("floors_csv") or "")).resolve()
        != validated.supplier_floors
        or floors.get("warnings")
    ):
        raise ValueError(f"Engine summary violates the comparison contract: {case.key}")


def _case_output_is_complete(case_dir: Path, *, lot_trace_required: bool) -> bool:
    required = [
        case_dir / "summaries" / "first_simulation_summary.json",
        case_dir / "reports" / "first_simulation_report.md",
        case_dir / "data" / "production_input_stocks_daily.csv",
        case_dir / "data" / "production_input_replenishment_arrivals_daily.csv",
        case_dir / "data" / "production_output_products_daily.csv",
        case_dir / "data" / "production_demand_service_daily.csv",
        case_dir / "data" / "production_supplier_shipments_daily.csv",
        case_dir / "data" / "supplier_nominal_parameters.csv",
        case_dir / "data" / "mrp_trace_daily.csv",
        case_dir / "data" / "mrp_orders_daily.csv",
    ]
    if lot_trace_required:
        required.extend(
            [
                case_dir / "data" / "production_lot_events.csv",
                case_dir / "data" / "production_lot_genealogy.csv",
                case_dir / "reports" / "lot_path_audit.md",
                case_dir / "data" / "lot_path_audit_issues.csv",
            ]
        )
    return all(path.is_file() and path.stat().st_size > 0 for path in required)


def _prepare_case_directory(
    output_dir: Path, case: PlannedCase
) -> tuple[Path, bool, str]:
    """Return a clean/reusable case directory without deleting partial evidence."""

    cases_root = (output_dir / "cases").resolve()
    case_dir = (cases_root / case.variant_id / f"seed_{case.seed}").resolve()
    if case_dir.parent != (cases_root / case.variant_id).resolve():
        raise RuntimeError(f"Case directory escaped its expected parent: {case_dir}")
    if case_dir.is_symlink():
        raise ValueError(f"Case directory must not be a symlink: {case_dir}")
    if not case_dir.exists():
        case_dir.mkdir(parents=True, exist_ok=False)
        return case_dir, False, ""
    if not case_dir.is_dir():
        raise ValueError(f"Case path is not a directory: {case_dir}")
    if not any(case_dir.iterdir()):
        return case_dir, False, ""
    lot_required = case.seed == protocol.LOT_TRACE_SEED
    if _case_output_is_complete(case_dir, lot_trace_required=lot_required):
        return case_dir, True, ""
    quarantine_root = output_dir / "incomplete_cases" / case.variant_id
    quarantine_root.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    quarantine = quarantine_root / f"seed_{case.seed}_{suffix}"
    case_dir.replace(quarantine)
    case_dir.mkdir(parents=True, exist_ok=False)
    return case_dir, False, str(quarantine.resolve())


def execute_engine_case(
    case: PlannedCase, validated: protocol.ValidatedProtocol, output_dir: Path
) -> dict[str, Any]:
    case_dir, recovered_complete_output, quarantined_incomplete_directory = (
        _prepare_case_directory(output_dir, case)
    )
    command = build_engine_command(case, validated, case_dir)
    log_path = case_dir / "comparison_engine.log"
    if recovered_complete_output:
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(
                f"[{_utc_now()}] RECOVERED_COMPLETE_OUTPUT_WITHOUT_ENGINE_RERUN\n"
            )
    else:
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(
                f"[{_utc_now()}] COMMAND {json.dumps(command, ensure_ascii=False)}\n"
            )
            completed = subprocess.run(
                command,
                cwd=protocol.REPO_ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(f"Engine failure for {case.key}; see {log_path}")
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    summary = _read_json(summary_path)
    _validate_summary(summary, case, validated)
    materials = _material_metrics(case_dir, validated, case.variant_id)
    if case.variant_id == protocol.NEW_VARIANT_ID and any(
        int(row["supplier_capacity_unexpected_static_basis_row_count"]) != 0
        for row in materials
    ):
        raise ValueError(
            "The dynamic candidate retained an unexplained static upstream capacity basis"
        )
    service, production = _system_metrics(case_dir)
    lot_trace_required = case.seed == protocol.LOT_TRACE_SEED
    lot_events_path = case_dir / "data" / "production_lot_events.csv"
    lot_genealogy_path = case_dir / "data" / "production_lot_genealogy.csv"
    lot_audit_report_path = case_dir / "reports" / "lot_path_audit.md"
    lot_audit_issues_path = case_dir / "data" / "lot_path_audit_issues.csv"
    if lot_trace_required:
        lot_events = _read_csv(lot_events_path)
        lot_genealogy = _read_csv(lot_genealogy_path)
        lot_audit_issues = _read_csv(lot_audit_issues_path)
        if (
            not lot_events
            or not lot_genealogy
            or not lot_audit_report_path.is_file()
            or lot_audit_report_path.stat().st_size <= 0
        ):
            raise ValueError(f"Required one-seed lot trace/audit is empty: {case.key}")
    else:
        lot_events = []
        lot_genealogy = []
        lot_audit_issues = []
    lot_event_type_counts: dict[str, int] = {}
    for row in lot_events:
        event_type = str(row.get("event_type") or "unknown")
        lot_event_type_counts[event_type] = lot_event_type_counts.get(event_type, 0) + 1
    lot_audit_severity_counts: dict[str, int] = {}
    for row in lot_audit_issues:
        severity = str(row.get("severity") or "unknown").strip().lower()
        lot_audit_severity_counts[severity] = (
            lot_audit_severity_counts.get(severity, 0) + 1
        )
    if lot_audit_severity_counts.get("error", 0) > 0:
        raise ValueError(
            f"Lot-path audit contains fatal errors: {case.key}/"
            f"{lot_audit_severity_counts['error']}"
        )
    lot_audit_report_sha256 = (
        _sha256(lot_audit_report_path) if lot_trace_required else ""
    )
    lot_audit_report_relative_path = (
        lot_audit_report_path.resolve().relative_to(output_dir.resolve()).as_posix()
        if lot_trace_required
        else ""
    )
    daily_demand_signature = _stable_sha256(
        [
            {
                "product_id": row["product_id"],
                "daily_demand_signature": row["daily_demand_signature"],
            }
            for row in sorted(service, key=lambda item: item["product_id"])
        ]
    )
    evidence: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "case_key": case.key,
        "variant_id": case.variant_id,
        "seed": case.seed,
        "valid": True,
        "executed_at_utc": _utc_now(),
        "graph_sha256": _sha256(validated.graph),
        "engine_sha256": _sha256(validated.engine),
        "profile_sha256": _sha256(_variant_profile(validated, case.variant_id)),
        "supplier_floors_sha256": _sha256(validated.supplier_floors),
        "command_sha256": _stable_sha256(command),
        "summary_sha256": _sha256(summary_path),
        "engine_process_launched": not recovered_complete_output,
        "complete_case_output_recovered_without_rerun": recovered_complete_output,
        "quarantined_incomplete_directory": quarantined_incomplete_directory,
        "j0_core_state_sha256": str(
            (
                ((summary.get("policy") or {}).get("warmup_boundary_audit") or {}).get(
                    "core_state_sha256"
                )
                or ""
            )
        ),
        "j0_pipeline_state_sha256": str(
            (
                (
                    (
                        (summary.get("policy") or {}).get("warmup_boundary_audit") or {}
                    ).get("component_sha256")
                    or {}
                ).get("pipeline")
                or ""
            )
        ),
        "j0_open_campaign_state_sha256": str(
            (
                (
                    (
                        (summary.get("policy") or {}).get("warmup_boundary_audit") or {}
                    ).get("component_sha256")
                    or {}
                ).get("open_production_campaign_qty")
                or ""
            )
        ),
        "j0_campaign_quantity_status": (
            "not_evaluable_engine_exports_boundary_digest_only"
        ),
        "lot_trace_required": lot_trace_required,
        "lot_trace_scope": (
            "one_paired_seed_structural_check_not_15_seed_lot_statistics"
            if lot_trace_required
            else "not_requested_for_this_seed"
        ),
        "lot_event_row_count": len(lot_events),
        "lot_genealogy_row_count": len(lot_genealogy),
        "lot_events_sha256": _sha256(lot_events_path) if lot_trace_required else "",
        "lot_genealogy_sha256": (
            _sha256(lot_genealogy_path) if lot_trace_required else ""
        ),
        "lot_unique_id_count": len(
            {str(row.get("lot_id") or "") for row in lot_events if row.get("lot_id")}
        ),
        "lot_event_type_counts": dict(sorted(lot_event_type_counts.items())),
        "lot_audit_required": lot_trace_required,
        "lot_audit_report_sha256": lot_audit_report_sha256,
        "retained_lot_audit_report_relative_path": lot_audit_report_relative_path,
        "lot_audit_issue_row_count": len(lot_audit_issues),
        "lot_audit_severity_counts": dict(sorted(lot_audit_severity_counts.items())),
        "lot_audit_error_row_count": lot_audit_severity_counts.get("error", 0),
        "lot_audit_warning_row_count": lot_audit_severity_counts.get("warning", 0),
        "lot_audit_issues_sha256": (
            _sha256(lot_audit_issues_path) if lot_trace_required else ""
        ),
        "lot_trace_lightweight_evidence_preserved": lot_trace_required,
        "lot_audit_report_retained_after_prune": lot_trace_required,
        "lot_audit_warnings_exposed": lot_audit_severity_counts.get("warning", 0),
        "daily_demand_signature": daily_demand_signature,
        "service": service,
        "production": production,
        "materials": materials,
        "probability_interpretation_allowed": False,
    }
    campaign_core.prune_case_artifacts(case_dir)
    if lot_trace_required and (
        not lot_audit_report_path.is_file()
        or lot_audit_report_path.is_symlink()
        or _sha256(lot_audit_report_path) != lot_audit_report_sha256
    ):
        raise ValueError(f"Retained lot-path audit report changed: {case.key}")
    unsigned = dict(evidence)
    evidence["evidence_signature"] = _stable_sha256(unsigned)
    return evidence


def _validate_evidence(
    evidence: Mapping[str, Any],
    case: PlannedCase,
    validated: protocol.ValidatedProtocol,
    output_dir: Path | None = None,
) -> None:
    unsigned = dict(evidence)
    signature = str(unsigned.pop("evidence_signature", ""))
    materials = evidence.get("materials")
    service = evidence.get("service")
    production = evidence.get("production")
    if (
        evidence.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or evidence.get("case_key") != case.key
        or evidence.get("variant_id") != case.variant_id
        or evidence.get("seed") != case.seed
        or evidence.get("valid") is not True
        or not signature
        or _stable_sha256(unsigned) != signature
        or evidence.get("graph_sha256") != _sha256(validated.graph)
        or evidence.get("engine_sha256") != _sha256(validated.engine)
        or evidence.get("profile_sha256")
        != _sha256(_variant_profile(validated, case.variant_id))
        or evidence.get("supplier_floors_sha256") != _sha256(validated.supplier_floors)
        or not str(evidence.get("j0_pipeline_state_sha256") or "")
        or not str(evidence.get("j0_open_campaign_state_sha256") or "")
        or not isinstance(materials, list)
        or len(materials) != 24
        or {row.get("pair_key") for row in materials}
        != {row.pair_key for row in validated.materials}
        or not isinstance(service, list)
        or {row.get("product_id") for row in service} != set(PRODUCTS)
        or not isinstance(production, list)
        or {row.get("product_id") for row in production} != set(PRODUCTS)
        or evidence.get("probability_interpretation_allowed") is not False
    ):
        raise ValueError(f"Invalid case evidence: {case.key}")
    expected_daily_demand_signature = _stable_sha256(
        [
            {
                "product_id": row["product_id"],
                "daily_demand_signature": row["daily_demand_signature"],
            }
            for row in sorted(service, key=lambda item: item["product_id"])
        ]
    )
    if evidence.get("daily_demand_signature") != expected_daily_demand_signature:
        raise ValueError(f"Invalid daily demand signature: {case.key}")
    for row in service:
        demand_qty = _float(row.get("demand_qty"))
        fill_rate = _float(row.get("fill_rate"))
        on_due_service = _float(row.get("on_due_service"))
        backlog_qty_days = _float(row.get("backlog_qty_days"))
        backlog_end_qty = _float(row.get("backlog_end_qty"))
        if (
            demand_qty <= ZERO_EPS
            or not math.isfinite(demand_qty)
            or not str(row.get("daily_demand_signature") or "")
            or not math.isfinite(fill_rate)
            or not 0.0 <= fill_rate <= 1.0
            or not math.isfinite(on_due_service)
            or not 0.0 <= on_due_service <= 1.0
            or not math.isfinite(backlog_qty_days)
            or backlog_qty_days < 0.0
            or not math.isfinite(backlog_end_qty)
            or backlog_end_qty < 0.0
        ):
            raise ValueError(f"Invalid finite/bounded service evidence: {case.key}")
    for row in production:
        if any(
            not math.isfinite(value) or value < 0.0
            for value in (
                _float(row.get("released_production_qty")),
                _float(row.get("executed_production_qty")),
            )
        ):
            raise ValueError(f"Invalid production evidence: {case.key}")
    for row in materials:
        pair_key = str(row.get("pair_key") or "")
        expected_mode = _variant_requirement_mode(case.variant_id, pair_key)
        finite_nonnegative_fields = (
            "stock_J0_before_production_qty",
            "stock_before_day0_arrival_qty",
            "consumption_total_qty",
            "bom_expected_consumption_total_qty",
            "bom_consumption_max_abs_residual_qty",
            "arrival_total_qty",
            "stock_balance_max_abs_residual_qty_J1_J719",
            "supplier_shipment_arriving_J0_J719_qty",
            "supplier_arrival_minus_recorded_shipment_qty",
            "supplier_direct_nominal_capacity_total_qty_per_day",
            "supplier_direct_effective_capacity_total_qty_per_day",
            "supplier_explicit_capacity_total_qty_per_day",
            "supplier_process_capacity_total_qty_per_day",
            "supplier_downstream_requirement_lane_row_sum_qty_per_day",
            "supplier_downstream_requirement_pair_qty_per_day",
            "supplier_downstream_requirement_pair_min_qty_per_day",
            "supplier_downstream_requirement_pair_max_qty_per_day",
            "supplier_downstream_signal_lane_row_sum_qty_per_day",
            "supplier_downstream_signal_pair_qty_per_day",
            "supplier_downstream_signal_pair_min_qty_per_day",
            "supplier_downstream_signal_pair_max_qty_per_day",
            "external_procurement_daily_need_total_qty",
            "external_procurement_nominal_capacity_total_qty_per_day",
            "external_procurement_pipeline_target_total_qty",
            "external_procurement_initial_pipeline_seed_total_qty",
        )
        if (
            row.get("requirement_mode_in_variant") != expected_mode
            or row.get("bom_consumption_balance_valid") is not True
            or row.get("stock_balance_valid_J1_J719") is not True
            or row.get("supplier_arrival_reconciliation_status")
            != "bounded_not_exact_opening_pipeline_quantities_not_exported"
            or not str(row.get("supplier_arrival_reconciliation_scope") or "")
            or any(
                not math.isfinite(_float(row.get(field)))
                or _float(row.get(field)) < 0.0
                for field in finite_nonnegative_fields
            )
        ):
            raise ValueError(
                f"Invalid physical material evidence: {case.key}/{pair_key}"
            )
        parameter_count = _int(row.get("supplier_parameter_row_count"), -1)
        if parameter_count > 0 and (
            not str(row.get("supplier_ids") or "")
            or not str(row.get("supplier_capacity_bases") or "")
            or row.get("supplier_downstream_requirement_pair_values_all_equal")
            is not True
            or row.get("supplier_downstream_signal_pair_values_all_equal") is not True
            or not math.isfinite(_float(row.get("supplier_applied_capacity_scale_min")))
            or not math.isfinite(_float(row.get("supplier_applied_capacity_scale_max")))
            or _float(row.get("supplier_applied_capacity_scale_min")) < 0.0
            or _float(row.get("supplier_applied_capacity_scale_max"))
            < _float(row.get("supplier_applied_capacity_scale_min"))
            or not math.isfinite(
                _float(row.get("external_procurement_target_utilization_min"))
            )
            or not math.isfinite(
                _float(row.get("external_procurement_target_utilization_max"))
            )
            or not 0.0
            <= _float(row.get("external_procurement_target_utilization_min"))
            <= _float(row.get("external_procurement_target_utilization_max"))
            <= 1.0
        ):
            raise ValueError(
                f"Invalid supplier capacity/policy evidence: {case.key}/{pair_key}"
            )
        if _float(row.get("supplier_shipment_arriving_J0_J719_qty")) > _float(
            row.get("arrival_total_qty")
        ) + max(
            BALANCE_ABS_TOL,
            BALANCE_REL_TOL * _float(row.get("arrival_total_qty")),
        ):
            raise ValueError(
                f"Supplier arrival lower-bound violation: {case.key}/{pair_key}"
            )
    lot_required = case.seed == protocol.LOT_TRACE_SEED
    if (
        evidence.get("lot_trace_required") is not lot_required
        or (
            lot_required
            and (
                _int(evidence.get("lot_event_row_count"), 0) <= 0
                or _int(evidence.get("lot_genealogy_row_count"), 0) <= 0
                or not str(evidence.get("lot_events_sha256") or "")
                or not str(evidence.get("lot_genealogy_sha256") or "")
                or evidence.get("lot_audit_required") is not True
                or not str(evidence.get("lot_audit_report_sha256") or "")
                or not str(evidence.get("lot_audit_issues_sha256") or "")
                or not isinstance(evidence.get("lot_audit_severity_counts"), dict)
                or _int(evidence.get("lot_audit_error_row_count"), -1) < 0
                or _int(evidence.get("lot_audit_warning_row_count"), -1) < 0
                or evidence.get("lot_trace_lightweight_evidence_preserved") is not True
                or evidence.get("lot_audit_report_retained_after_prune") is not True
                or not str(
                    evidence.get("retained_lot_audit_report_relative_path") or ""
                )
                or _int(evidence.get("lot_audit_error_row_count"), -1) != 0
                or _int(evidence.get("lot_audit_warnings_exposed"), -1)
                != _int(evidence.get("lot_audit_warning_row_count"), -2)
            )
        )
        or (
            not lot_required
            and (
                _int(evidence.get("lot_event_row_count"), 0) != 0
                or _int(evidence.get("lot_genealogy_row_count"), 0) != 0
                or str(evidence.get("lot_events_sha256") or "")
                or str(evidence.get("lot_genealogy_sha256") or "")
                or evidence.get("lot_audit_required") is not False
                or str(evidence.get("lot_audit_report_sha256") or "")
                or str(evidence.get("lot_audit_issues_sha256") or "")
                or evidence.get("lot_audit_severity_counts") != {}
                or _int(evidence.get("lot_audit_error_row_count"), -1) != 0
                or _int(evidence.get("lot_audit_warning_row_count"), -1) != 0
                or evidence.get("lot_trace_lightweight_evidence_preserved") is not False
                or evidence.get("lot_audit_report_retained_after_prune") is not False
                or str(evidence.get("retained_lot_audit_report_relative_path") or "")
                or _int(evidence.get("lot_audit_warnings_exposed"), -1) != 0
            )
        )
    ):
        raise ValueError(f"Lot trace evidence scope mismatch: {case.key}")
    severity_counts = evidence.get("lot_audit_severity_counts") or {}
    if (
        _int(evidence.get("lot_audit_issue_row_count"), -1)
        != sum(_int(value, 0) for value in severity_counts.values())
        or _int(evidence.get("lot_audit_error_row_count"), -1)
        != _int(severity_counts.get("error"), 0)
        or _int(evidence.get("lot_audit_warning_row_count"), -1)
        != _int(severity_counts.get("warning"), 0)
    ):
        raise ValueError(f"Lot audit severity counts are inconsistent: {case.key}")
    if lot_required and output_dir is not None:
        relative = str(evidence["retained_lot_audit_report_relative_path"])
        report_path = (output_dir.resolve() / relative).resolve()
        try:
            report_path.relative_to(output_dir.resolve())
        except ValueError as exc:
            raise ValueError(
                "Retained lot audit report escapes output directory"
            ) from exc
        if (
            not report_path.is_file()
            or report_path.is_symlink()
            or _sha256(report_path) != evidence.get("lot_audit_report_sha256")
        ):
            raise ValueError(f"Retained lot audit report changed: {case.key}")


def _new_ledger(signature: str) -> dict[str, Any]:
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "campaign_signature": signature,
        "case_files": {},
        "case_file_sha256": {},
        "reconciled_orphan_evidence": [],
        "quarantined_invalid_orphan_evidence": [],
    }


def _load_ledger(output_dir: Path, signature: str) -> dict[str, Any]:
    path = output_dir / LEDGER_FILE
    if not path.is_file():
        return _new_ledger(signature)
    payload = _read_json(path)
    if (
        payload.get("schema_version") != LEDGER_SCHEMA_VERSION
        or payload.get("campaign_signature") != signature
        or not isinstance(payload.get("case_files"), dict)
        or not isinstance(payload.get("case_file_sha256"), dict)
        or set(payload["case_files"]) != set(payload["case_file_sha256"])
        or not isinstance(payload.get("reconciled_orphan_evidence", []), list)
        or not isinstance(payload.get("quarantined_invalid_orphan_evidence", []), list)
    ):
        raise ValueError("Execution ledger contract mismatch")
    return payload


def _evidence_path(output_dir: Path, case: PlannedCase) -> Path:
    return output_dir / "evidence" / case.variant_id / f"seed_{case.seed}.json"


def _persist_evidence(
    output_dir: Path, ledger: dict[str, Any], evidence: Mapping[str, Any]
) -> None:
    case = PlannedCase(str(evidence["variant_id"]), int(evidence["seed"]))
    path = _evidence_path(output_dir, case)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, evidence)
    relative = path.relative_to(output_dir).as_posix()
    ledger["case_files"][case.key] = relative
    ledger["case_file_sha256"][case.key] = _sha256(path)
    _write_json(output_dir / LEDGER_FILE, ledger)


def _quarantine_invalid_orphan_evidence(
    *,
    output_dir: Path,
    evidence_path: Path,
    error: Exception,
) -> dict[str, Any]:
    evidence_root = output_dir / "evidence"
    relative = evidence_path.relative_to(evidence_root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    quarantine_root = output_dir / "orphaned_evidence" / stamp
    destination = quarantine_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.resolve().parent != (quarantine_root / relative.parent).resolve():
        raise RuntimeError("Invalid orphan-evidence quarantine destination")
    was_symlink = evidence_path.is_symlink()
    original_sha256 = (
        _sha256(evidence_path) if evidence_path.is_file() and not was_symlink else ""
    )
    evidence_path.replace(destination)
    return {
        "quarantined_at_utc": _utc_now(),
        "original_relative_path": evidence_path.relative_to(output_dir).as_posix(),
        "quarantine_relative_path": destination.relative_to(output_dir).as_posix(),
        "original_sha256": original_sha256,
        "was_symlink": was_symlink,
        "error_type": type(error).__name__,
        "error": str(error),
    }


def _load_evidence(
    output_dir: Path,
    ledger: dict[str, Any],
    planned: Mapping[str, PlannedCase],
    validated: protocol.ValidatedProtocol,
) -> dict[str, dict[str, Any]]:
    evidence_root = output_dir / "evidence"
    expected_disk = (
        {
            path.relative_to(output_dir).as_posix()
            for path in evidence_root.rglob("*.json")
        }
        if evidence_root.is_dir()
        else set()
    )
    registered_relatives = set((ledger.get("case_files") or {}).values())
    orphan_relatives = sorted(expected_disk - registered_relatives)
    ledger_changed = False
    for relative in orphan_relatives:
        path = output_dir / relative
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("Orphan evidence is not a regular file")
            evidence = _read_json(path)
            case_key = str(evidence.get("case_key") or "")
            case = planned.get(case_key)
            if case is None:
                raise ValueError("Orphan evidence is outside the requested scope")
            canonical_path = _evidence_path(output_dir, case)
            if path.resolve() != canonical_path.resolve():
                raise ValueError("Orphan evidence path is not canonical")
            _validate_evidence(evidence, case, validated, output_dir)
            ledger["case_files"][case_key] = relative
            ledger["case_file_sha256"][case_key] = _sha256(path)
            ledger.setdefault("reconciled_orphan_evidence", []).append(
                {
                    "reconciled_at_utc": _utc_now(),
                    "case_key": case_key,
                    "relative_path": relative,
                    "sha256": ledger["case_file_sha256"][case_key],
                }
            )
            ledger_changed = True
        except Exception as exc:
            record = _quarantine_invalid_orphan_evidence(
                output_dir=output_dir,
                evidence_path=path,
                error=exc,
            )
            ledger.setdefault("quarantined_invalid_orphan_evidence", []).append(record)
            ledger_changed = True
    if ledger_changed:
        _write_json(output_dir / LEDGER_FILE, ledger)
    disk_after_reconciliation = (
        {
            path.relative_to(output_dir).as_posix()
            for path in evidence_root.rglob("*.json")
        }
        if evidence_root.is_dir()
        else set()
    )
    ledger_relatives = set((ledger.get("case_files") or {}).values())
    if disk_after_reconciliation != ledger_relatives:
        raise ValueError(
            "Evidence directory and ledger differ after reconciliation: "
            f"disk={sorted(disk_after_reconciliation)}, "
            f"ledger={sorted(ledger_relatives)}"
        )
    result: dict[str, dict[str, Any]] = {}
    for key, relative in (ledger.get("case_files") or {}).items():
        if key not in planned:
            raise ValueError(f"Evidence outside requested scope: {key}")
        path = (output_dir / str(relative)).resolve()
        try:
            path.relative_to(output_dir.resolve())
        except ValueError as exc:
            raise ValueError("Evidence path escapes output directory") from exc
        if not path.is_file() or _sha256(path) != ledger["case_file_sha256"][key]:
            raise ValueError(f"Evidence file changed: {key}")
        evidence = _read_json(path)
        _validate_evidence(evidence, planned[key], validated, output_dir)
        result[key] = evidence
    return result


def _planned_cases(seeds: Sequence[int]) -> dict[str, PlannedCase]:
    cases = [PlannedCase(variant, seed) for seed in seeds for variant in VARIANTS]
    return {case.key: case for case in cases}


def _flatten_results(
    evidence_by_key: Mapping[str, Mapping[str, Any]], seeds: Sequence[int]
) -> dict[str, list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = []
    system_pairs: list[dict[str, Any]] = []
    material_pairs: list[dict[str, Any]] = []
    for seed in seeds:
        evidence = {
            variant: evidence_by_key[f"{variant}::seed_{seed}"] for variant in VARIANTS
        }
        for variant, item in evidence.items():
            service_by_product = {row["product_id"]: row for row in item["service"]}
            production_by_product = {
                row["product_id"]: row for row in item["production"]
            }
            cases.append(
                {
                    "variant_id": variant,
                    "seed": seed,
                    "j0_core_state_sha256": item["j0_core_state_sha256"],
                    "daily_demand_signature": item["daily_demand_signature"],
                    **{
                        f"on_due_service_{product}": service_by_product[product][
                            "on_due_service"
                        ]
                        for product in PRODUCTS
                    },
                    **{
                        f"fill_rate_{product}": service_by_product[product]["fill_rate"]
                        for product in PRODUCTS
                    },
                    **{
                        f"released_production_{product}": production_by_product[
                            product
                        ]["released_production_qty"]
                        for product in PRODUCTS
                    },
                }
            )
            for row in item["materials"]:
                materials.append({"variant_id": variant, "seed": seed, **row})
        old_demand_signature = evidence[protocol.OLD_VARIANT_ID][
            "daily_demand_signature"
        ]
        new_demand_signature = evidence[protocol.NEW_VARIANT_ID][
            "daily_demand_signature"
        ]
        if old_demand_signature != new_demand_signature:
            raise ValueError(
                f"Paired daily client demand differs between variants for seed {seed}"
            )
        for product in PRODUCTS:
            old = next(
                row
                for row in evidence[protocol.OLD_VARIANT_ID]["service"]
                if row["product_id"] == product
            )
            new = next(
                row
                for row in evidence[protocol.NEW_VARIANT_ID]["service"]
                if row["product_id"] == product
            )
            if old["daily_demand_signature"] != new[
                "daily_demand_signature"
            ] or not _close(old["demand_qty"], new["demand_qty"]):
                raise ValueError(
                    "Paired daily product demand differs between variants "
                    f"for seed {seed}/{product}"
                )
            old_prod = next(
                row
                for row in evidence[protocol.OLD_VARIANT_ID]["production"]
                if row["product_id"] == product
            )
            new_prod = next(
                row
                for row in evidence[protocol.NEW_VARIANT_ID]["production"]
                if row["product_id"] == product
            )
            system_pairs.append(
                {
                    "seed": seed,
                    "product_id": product,
                    "paired_daily_demand_identical": True,
                    "daily_demand_signature": old["daily_demand_signature"],
                    **{
                        f"old_{field}": old[field]
                        for field in (
                            "demand_qty",
                            "fill_rate",
                            "on_due_service",
                            "backlog_qty_days",
                            "backlog_end_qty",
                        )
                    },
                    **{
                        f"new_{field}": new[field]
                        for field in (
                            "demand_qty",
                            "fill_rate",
                            "on_due_service",
                            "backlog_qty_days",
                            "backlog_end_qty",
                        )
                    },
                    "old_released_production_qty": old_prod["released_production_qty"],
                    "new_released_production_qty": new_prod["released_production_qty"],
                    "old_executed_production_qty": old_prod["executed_production_qty"],
                    "new_executed_production_qty": new_prod["executed_production_qty"],
                    "delta_on_due_service": new["on_due_service"]
                    - old["on_due_service"],
                    "delta_fill_rate": new["fill_rate"] - old["fill_rate"],
                    "delta_backlog_qty_days": new["backlog_qty_days"]
                    - old["backlog_qty_days"],
                    "delta_released_production_qty": new_prod["released_production_qty"]
                    - old_prod["released_production_qty"],
                    "delta_executed_production_qty": new_prod["executed_production_qty"]
                    - old_prod["executed_production_qty"],
                }
            )
        old_materials = {
            row["pair_key"]: row
            for row in evidence[protocol.OLD_VARIANT_ID]["materials"]
        }
        new_materials = {
            row["pair_key"]: row
            for row in evidence[protocol.NEW_VARIANT_ID]["materials"]
        }
        fields = (
            "stock_J0_before_production_qty",
            "stock_before_day0_arrival_qty",
            "stock_end_min_qty",
            "stock_end_mean_qty",
            "zero_stock_day_count",
            "consumption_total_qty",
            "consumption_daily_mean_qty",
            "bom_expected_consumption_total_qty",
            "bom_consumption_max_abs_residual_qty",
            "arrival_total_qty",
            "arrival_positive_day_count",
            "day0_boundary_arrival_qty",
            "stock_balance_max_abs_residual_qty_J1_J719",
            "mrp_order_row_count",
            "mrp_order_J0_row_count",
            "mrp_order_J0_release_qty",
            "mrp_order_J0_planned_receipt_qty",
            "mrp_release_total_qty",
            "mrp_planned_receipt_total_qty",
            "mrp_target_stock_J0_qty",
            "mrp_target_stock_mean_qty",
            "mrp_target_stock_median_qty",
            "mrp_target_stock_p95_qty",
            "mrp_target_stock_max_qty",
            "mrp_target_demand_signal_daily_mean_qty",
            "mrp_target_demand_signal_median_qty",
            "mrp_target_demand_signal_p95_qty",
            "mrp_target_demand_signal_max_qty",
            "mrp_backlog_J0_qty",
            "mrp_backlog_max_qty",
            "target_stock_mean_to_consumption_daily_mean_days",
            "stock_J0_cover_days",
            "requirement_signal_to_consumption_ratio",
            "future_supplier_lane_shipment_row_count",
            "future_supplier_lane_positive_shipment_count",
            "future_supplier_lane_shipped_qty",
            "supplier_shipment_arriving_J0_J719_row_count",
            "supplier_shipment_arriving_J0_J719_qty",
            "supplier_arrival_minus_recorded_shipment_qty",
            "supplier_parameter_row_count",
            "supplier_direct_nominal_capacity_total_qty_per_day",
            "supplier_direct_effective_capacity_total_qty_per_day",
            "supplier_applied_capacity_scale_min",
            "supplier_applied_capacity_scale_max",
            "supplier_explicit_capacity_total_qty_per_day",
            "supplier_process_capacity_total_qty_per_day",
            "supplier_downstream_requirement_lane_row_sum_qty_per_day",
            "supplier_downstream_requirement_pair_qty_per_day",
            "supplier_downstream_requirement_pair_min_qty_per_day",
            "supplier_downstream_requirement_pair_max_qty_per_day",
            "supplier_downstream_signal_lane_row_sum_qty_per_day",
            "supplier_downstream_signal_pair_qty_per_day",
            "supplier_downstream_signal_pair_min_qty_per_day",
            "supplier_downstream_signal_pair_max_qty_per_day",
            "external_procurement_daily_need_total_qty",
            "external_procurement_nominal_capacity_total_qty_per_day",
            "external_procurement_target_utilization_min",
            "external_procurement_target_utilization_max",
            "external_procurement_pipeline_target_total_qty",
            "external_procurement_initial_pipeline_seed_total_qty",
            "supplier_capacity_dynamic_signal_basis_row_count",
            "supplier_capacity_explicit_override_row_count",
            "supplier_capacity_zero_signal_fallback_row_count",
            "supplier_capacity_unexpected_static_basis_row_count",
        )
        for key in sorted(old_materials):
            old = old_materials[key]
            new = new_materials[key]
            row: dict[str, Any] = {
                "seed": seed,
                "node_id": old["node_id"],
                "item_id": old["item_id"],
                "pair_key": key,
                "uom": old["uom"],
            }
            for field in fields:
                row[f"old_{field}"] = old[field]
                row[f"new_{field}"] = new[field]
                old_value = _float(old[field])
                new_value = _float(new[field])
                row[f"delta_{field}"] = (
                    new_value - old_value
                    if math.isfinite(old_value) and math.isfinite(new_value)
                    else math.nan
                )
            for field in (
                "consumption_observation_status",
                "requirement_mode_in_variant",
                "bom_consumption_balance_valid",
                "bom_consumption_balance_basis",
                "stock_balance_valid_J1_J719",
                "stock_balance_equation",
                "mrp_demand_signal_status",
                "stock_J0_cover_status",
                "stock_J0_covers_measured_horizon",
                "requirement_signal_to_consumption_diagnostic",
                "j0_pipeline_qty",
                "j0_pipeline_cover_days",
                "j0_pipeline_quantification_status",
                "day0_boundary_arrival_included_in_stock_J0",
                "supplier_risk_scope",
                "supplier_risk_flow_evaluable",
                "supplier_risk_flow_evaluability_reason",
                "supplier_parameter_status",
                "supplier_ids",
                "supplier_capacity_bases",
                "external_procurement_capacity_bases",
                "external_procurement_capacity_profiles",
                "supplier_downstream_requirement_pair_values_all_equal",
                "supplier_downstream_signal_pair_values_all_equal",
                "supplier_arrival_reconciliation_status",
                "supplier_arrival_reconciliation_scope",
            ):
                row[f"old_{field}"] = old[field]
                row[f"new_{field}"] = new[field]
            material_pairs.append(row)
    return {
        "case_metrics.csv": cases,
        "material_seed_metrics.csv": materials,
        "paired_system_metrics.csv": system_pairs,
        "paired_material_metrics.csv": material_pairs,
    }


def _summary_rows(
    rows: Sequence[Mapping[str, Any]], group_field: str
) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row[group_field]), []).append(row)
    result: list[dict[str, Any]] = []
    for key in sorted(groups):
        group = groups[key]
        output: dict[str, Any] = {group_field: key, "paired_seed_count": len(group)}
        for field in group[0]:
            if not field.startswith(("old_", "new_", "delta_")):
                continue
            raw_values = [row.get(field) for row in group]
            if raw_values and all(
                value is None or isinstance(value, bool) for value in raw_values
            ):
                continue
            values = [_float(value) for value in raw_values]
            finite = [value for value in values if math.isfinite(value)]
            if not finite:
                continue
            output[f"mean_{field}"] = fmean(finite) if finite else math.nan
            output[f"median_{field}"] = _percentile(finite, 0.5)
            output[f"p10_{field}"] = _percentile(finite, 0.1)
            output[f"p90_{field}"] = _percentile(finite, 0.9)
            output[f"stddev_{field}"] = pstdev(finite) if finite else math.nan
            output[f"min_{field}"] = min(finite) if finite else math.nan
            output[f"max_{field}"] = max(finite) if finite else math.nan
        if group_field == "pair_key":
            output.update(
                {
                    "node_id": group[0].get("node_id"),
                    "item_id": group[0].get("item_id"),
                    "uom": group[0].get("uom"),
                    "old_zero_consumption_seed_count": sum(
                        row.get("old_consumption_observation_status")
                        == "zero_consumption_observed"
                        for row in group
                    ),
                    "new_zero_consumption_seed_count": sum(
                        row.get("new_consumption_observation_status")
                        == "zero_consumption_observed"
                        for row in group
                    ),
                    "old_zero_mrp_signal_seed_count": sum(
                        row.get("old_mrp_demand_signal_status")
                        == "zero_signal_observed"
                        for row in group
                    ),
                    "new_zero_mrp_signal_seed_count": sum(
                        row.get("new_mrp_demand_signal_status")
                        == "zero_signal_observed"
                        for row in group
                    ),
                    "old_opening_stock_covers_horizon_seed_count": sum(
                        _bool(row.get("old_stock_J0_covers_measured_horizon"))
                        for row in group
                    ),
                    "new_opening_stock_covers_horizon_seed_count": sum(
                        _bool(row.get("new_stock_J0_covers_measured_horizon"))
                        for row in group
                    ),
                    "old_supplier_risk_flow_evaluable_seed_count": sum(
                        _bool(row.get("old_supplier_risk_flow_evaluable"))
                        for row in group
                    ),
                    "new_supplier_risk_flow_evaluable_seed_count": sum(
                        _bool(row.get("new_supplier_risk_flow_evaluable"))
                        for row in group
                    ),
                    "old_requirement_consumption_alert_seed_count": sum(
                        str(
                            row.get("old_requirement_signal_to_consumption_diagnostic")
                            or ""
                        ).startswith("alert_")
                        for row in group
                    ),
                    "new_requirement_consumption_alert_seed_count": sum(
                        str(
                            row.get("new_requirement_signal_to_consumption_diagnostic")
                            or ""
                        ).startswith("alert_")
                        for row in group
                    ),
                    "new_unexpected_static_upstream_basis_seed_count": sum(
                        _float(
                            row.get(
                                "new_supplier_capacity_unexpected_static_basis_row_count"
                            ),
                            0.0,
                        )
                        > 0.0
                        for row in group
                    ),
                    "j0_pipeline_quantity_status": (
                        "not_evaluable_engine_exports_boundary_digest_only"
                    ),
                }
            )
        result.append(output)
    return result


@contextmanager
def _lock_coordination(output_dir: Path) -> Iterable[None]:
    """Serialize acquisition/recovery so a stale-lock race cannot break a new lock."""

    path = output_dir / LOCK_COORDINATION_FILE
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR)
    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"0")
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError(
                    "Runner lock acquisition is already in progress"
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError(
                    "Runner lock acquisition is already in progress"
                ) from exc
        try:
            yield
        finally:
            if os.name == "nt":
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


@contextmanager
def _lock(output_dir: Path) -> Iterable[None]:
    path = output_dir / LOCK_FILE
    descriptor = -1
    with _lock_coordination(output_dir):
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            if path.is_symlink() or not path.is_file():
                raise RuntimeError(
                    f"Runner lock is not a regular file and cannot be recovered: {path}"
                ) from exc
            raw_pid = path.read_text(encoding="ascii").strip()
            if not raw_pid.isdigit() or int(raw_pid) <= 0:
                raise RuntimeError(
                    f"Runner lock has no valid recorded PID and cannot be recovered: {path}"
                ) from exc
            recorded_pid = int(raw_pid)
            if _process_is_running(recorded_pid):
                raise RuntimeError(
                    f"Runner lock belongs to active PID {recorded_pid}: {path}"
                ) from exc
            archive_root = output_dir / ABANDONED_LOCK_DIR
            archive_root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            archived = archive_root / f"{LOCK_FILE}.{stamp}.pid_{recorded_pid}"
            if archived.resolve().parent != archive_root.resolve():
                raise RuntimeError("Abandoned-lock archive path escaped its directory")
            path.replace(archived)
            try:
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as race_exc:
                raise RuntimeError(
                    f"Runner lock was acquired during abandoned-lock recovery: {path}"
                ) from race_exc
    if descriptor < 0:
        raise RuntimeError(f"Unable to acquire runner lock: {path}")
    lock_identity: tuple[int, int] | None = None
    try:
        os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
        os.fsync(descriptor)
        stat = os.fstat(descriptor)
        lock_identity = (stat.st_dev, stat.st_ino)
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if path.is_file() and not path.is_symlink() and lock_identity is not None:
            current = path.stat(follow_symlinks=False)
            if (current.st_dev, current.st_ino) == lock_identity and path.read_text(
                encoding="ascii"
            ).strip() == str(os.getpid()):
                path.unlink()


def _process_is_running(process_id: int) -> bool:
    """Use the V3 runner's cross-platform PID liveness guard."""

    return v3_runner._process_is_running(process_id)


def run_comparison(
    *,
    protocol_dir: Path,
    active_campaign_dir: Path,
    output_dir: Path,
    mode: str,
    workers: int = 2,
    case_executor: CaseExecutor | None = None,
) -> dict[str, Any]:
    if mode not in {"validate", "smoke", "compare15"}:
        raise ValueError(f"Unsupported mode: {mode}")
    if workers <= 0:
        raise ValueError("workers must be positive")
    validated = protocol.validate_protocol(protocol_dir)
    if mode == "validate":
        return {
            "status": "valid_planned_not_executed",
            "protocol_signature": validated.manifest["protocol_signature"],
            "material_count": len(validated.materials),
        }
    campaign_binding = validated.manifest.get("active_campaign_binding") or {}
    guard = validate_v3_stopped(active_campaign_dir, campaign_binding)
    seeds = protocol.SMOKE_SEEDS if mode == "smoke" else protocol.COMPARISON_SEEDS
    planned = _planned_cases(seeds)
    custom_executor = case_executor is not None
    signature = _stable_sha256(
        {
            "schema_version": SCHEMA_VERSION,
            "protocol_signature": validated.manifest["protocol_signature"],
            "runner_sha256": _sha256(Path(__file__).resolve()),
            "mode": mode,
            "seeds": list(seeds),
            "variants": list(VARIANTS),
            "custom_executor": custom_executor,
            "source_v3_guard_at_invocation": guard,
        }
    )
    output_dir = output_dir.resolve()
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("Output path is not a directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    with _lock(output_dir):
        manifest_path = output_dir / MANIFEST_FILE
        if manifest_path.is_file():
            manifest = _read_json(manifest_path)
            if manifest.get("campaign_signature") != signature:
                raise ValueError("Existing output belongs to another comparison scope")
        else:
            coordination_file = output_dir / LOCK_COORDINATION_FILE
            if coordination_file.is_symlink() or not coordination_file.is_file():
                raise ValueError("Runner lock coordination file is invalid")
            abandoned_lock_archive = output_dir / ABANDONED_LOCK_DIR
            if abandoned_lock_archive.exists() and (
                abandoned_lock_archive.is_symlink()
                or not abandoned_lock_archive.is_dir()
                or any(
                    child.is_symlink()
                    or not child.is_file()
                    or not child.name.startswith(f"{LOCK_FILE}.")
                    for child in abandoned_lock_archive.iterdir()
                )
            ):
                raise ValueError("Abandoned-lock archive inventory is invalid")
            unexpected = [
                path.name
                for path in output_dir.iterdir()
                if path.name
                not in {LOCK_FILE, LOCK_COORDINATION_FILE, ABANDONED_LOCK_DIR}
            ]
            if unexpected:
                raise ValueError("Comparison output directory must be new or resumable")
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "status": "running",
                "mode": mode,
                "campaign_signature": signature,
                "protocol_signature": validated.manifest["protocol_signature"],
                "runner_sha256": _sha256(Path(__file__).resolve()),
                "source_v3_guard": guard,
                "bound_active_campaign_identity_signature": campaign_binding.get(
                    "identity_signature"
                ),
                "capacity_coupling_audit_sha256": (
                    validated.manifest.get("capacity_coupling_audit") or {}
                ).get("audit_sha256"),
                "variant_ids": list(VARIANTS),
                "seed_ids": list(seeds),
                "planned_engine_run_count": len(planned),
                "material_count": len(validated.materials),
                "lot_trace_seed": protocol.LOT_TRACE_SEED,
                "planned_lot_trace_run_count": 2,
                "lot_trace_scope": (
                    "one paired seed in both variants; structural trace and lot-path audit only"
                ),
                "supplier_incident_loaded": False,
                "probability_interpretation_allowed": False,
                "supplier_ranking_allowed": False,
                "smoke_reusable_for_compare15": False,
                "custom_executor_used": custom_executor,
                "opening_stock_corrected_by_candidate": False,
                "j0_pipeline_quantity_evaluable": False,
                "j0_campaign_quantity_evaluable": False,
                "warmup_240_vs_605_in_scope": False,
                "service_93_80_calibration_allowed_before_this_test": False,
                "comparison_semantics": (
                    "coupled_diagnostic_dynamic_requirements_direct_supplier_"
                    "capacity_and_upstream_procurement_policy"
                ),
                "isolates_mrp_only": False,
                "direct_supplier_capacities_held_constant": False,
                "upstream_procurement_capacities_and_policies_held_constant": False,
                "scientifically_reviewable": False,
                "publishable_results": False,
                "resume_evidence_policy": (
                    "valid_orphan_evidence_is_reconciled_into_ledger; invalid_orphan_"
                    "evidence_is_archived_without_deletion"
                ),
                "lock_recovery_policy": (
                    "archive_only_when_recorded_positive_pid_is_not_alive; never_break_"
                    "an_active_or_unverifiable_lock"
                ),
                "started_at_utc": _utc_now(),
            }
        for stale_claim in (
            "source_v3_mutated",
            "source_v3_unchanged_during_comparison",
            "old_profile_mutated",
            "new_profile_mutated",
            "protocol_sources_unchanged_during_comparison",
        ):
            manifest.pop(stale_claim, None)
        manifest.update(
            {
                "status": "running",
                "source_v3_guard_at_invocation": guard,
                "scientifically_reviewable": False,
                "publishable_results": False,
            }
        )
        _write_json(manifest_path, manifest)
        try:
            ledger = _load_ledger(output_dir, signature)
            evidence = _load_evidence(output_dir, ledger, planned, validated)
            missing = [case for key, case in planned.items() if key not in evidence]
            executor = case_executor or execute_engine_case
            completed_this_invocation: list[dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(executor, case, validated, output_dir): case
                    for case in missing
                }
                for future in as_completed(futures):
                    case = futures[future]
                    item = future.result()
                    _validate_evidence(item, case, validated, output_dir)
                    _persist_evidence(output_dir, ledger, item)
                    evidence[case.key] = dict(item)
                    completed_this_invocation.append(dict(item))
                    print(f"[{mode}] {case.variant_id} seed={case.seed}", flush=True)
            if set(evidence) != set(planned):
                raise RuntimeError("Paired comparison matrix is incomplete")
            tables = _flatten_results(evidence, seeds)
            for filename, rows in tables.items():
                _write_csv(output_dir / filename, rows)
            system_summary = _summary_rows(
                tables["paired_system_metrics.csv"], "product_id"
            )
            material_summary = _summary_rows(
                tables["paired_material_metrics.csv"], "pair_key"
            )
            if len(system_summary) != 2 or len(material_summary) != 24:
                raise RuntimeError("Comparison summary matrix is incomplete")
            _write_csv(output_dir / "system_comparison_summary.csv", system_summary)
            _write_csv(output_dir / "material_comparison_summary.csv", material_summary)
            validated_at_completion = protocol.validate_protocol(validated.protocol_dir)
            if validated_at_completion.manifest.get(
                "protocol_signature"
            ) != validated.manifest.get("protocol_signature"):
                raise ValueError("Protocol identity changed during comparison")
            guard_at_completion = validate_v3_stopped(
                active_campaign_dir,
                campaign_binding,
            )
            if guard_at_completion != guard:
                raise ValueError(
                    "Stopped V3 campaign manifest or checkpoint changed during comparison"
                )
            manifest.update(
                {
                    "status": (
                        "smoke_complete_nonreusable"
                        if mode == "smoke"
                        else "complete_15_paired_simulations"
                    ),
                    "completed_at_utc": _utc_now(),
                    "completed_engine_run_count": len(evidence),
                    "case_executor_invocation_count_this_invocation": len(missing),
                    "executed_engine_run_count_this_invocation": sum(
                        _bool(item.get("engine_process_launched"))
                        for item in completed_this_invocation
                    ),
                    "complete_case_output_recovered_without_rerun_count_this_invocation": sum(
                        _bool(item.get("complete_case_output_recovered_without_rerun"))
                        for item in completed_this_invocation
                    ),
                    "incomplete_case_directory_quarantined_count_this_invocation": sum(
                        bool(str(item.get("quarantined_incomplete_directory") or ""))
                        for item in completed_this_invocation
                    ),
                    "reused_verified_run_count_this_invocation": len(planned)
                    - len(missing),
                    "paired_seed_count": len(seeds),
                    "lot_trace_evidence_case_count": sum(
                        _bool(item.get("lot_trace_required"))
                        for item in evidence.values()
                    ),
                    "lot_path_audit_evidence_case_count": sum(
                        _bool(item.get("lot_audit_required"))
                        and bool(str(item.get("lot_audit_report_sha256") or ""))
                        for item in evidence.values()
                    ),
                    "lot_path_audit_error_row_count": sum(
                        _int(item.get("lot_audit_error_row_count"), 0)
                        for item in evidence.values()
                    ),
                    "lot_path_audit_warning_row_count": sum(
                        _int(item.get("lot_audit_warning_row_count"), 0)
                        for item in evidence.values()
                    ),
                    "lot_path_audit_reports_retained_and_hash_verified": all(
                        not _bool(item.get("lot_audit_required"))
                        or _bool(item.get("lot_audit_report_retained_after_prune"))
                        for item in evidence.values()
                    ),
                    "results": {
                        filename: {
                            "sha256": _sha256(output_dir / filename),
                            "row_count": len(rows),
                        }
                        for filename, rows in {
                            **tables,
                            "system_comparison_summary.csv": system_summary,
                            "material_comparison_summary.csv": material_summary,
                        }.items()
                    },
                    "execution_ledger_sha256": _sha256(output_dir / LEDGER_FILE),
                    "reconciled_orphan_evidence_count": len(
                        ledger.get("reconciled_orphan_evidence") or []
                    ),
                    "quarantined_invalid_orphan_evidence_count": len(
                        ledger.get("quarantined_invalid_orphan_evidence") or []
                    ),
                    "source_v3_guard_at_completion": guard_at_completion,
                    "source_v3_guard_comparison_basis": (
                        "resolved_path_full_stopped_manifest_sha256_immutable_identity_"
                        "signature_and_checkpoint_sha256"
                    ),
                    "source_v3_unchanged_during_comparison": True,
                    "source_v3_mutated": False,
                    "protocol_sources_unchanged_during_comparison": True,
                    "old_profile_mutated": False,
                    "new_profile_mutated": False,
                    "probability_interpretation_allowed": False,
                    "supplier_ranking_allowed": False,
                    "industrial_recommendation_allowed": False,
                    "no_future_supplier_lane_flow_means_risk_not_evaluable": True,
                    "paired_daily_demand_identical": True,
                    "material_stock_and_bom_balances_validated_daily": True,
                    "supplier_arrival_reconciliation_limit": (
                        "recorded_J0_J719_shipments_are_only_a_lower_bound_because_"
                        "pair_level_opening_pipeline_quantities_are_not_exported"
                    ),
                    "summary_dispersion_statistics": [
                        "mean",
                        "median",
                        "p10",
                        "p90",
                        "population_standard_deviation",
                        "min",
                        "max",
                    ],
                    "requirement_consumption_ratio_diagnostic_band": [0.5, 2.0],
                    "requirement_consumption_band_is_calibration_acceptance": False,
                    "comparison_semantics": (
                        "coupled_diagnostic_dynamic_requirements_direct_supplier_"
                        "capacity_and_upstream_procurement_policy"
                    ),
                    "isolates_mrp_only": False,
                    "scientifically_reviewable": False,
                    "scientific_review_blockers": [
                        "opening stocks and pair-level opening pipeline not validated",
                        "240-day warmup not compared with a longer stabilization period",
                        "supplier capacity scale and inferred upstream capacities not validated",
                        "MRP-only causal mechanism not isolated",
                    ],
                    "follow_up_after_this_test": (
                        "validate opening stocks and capacities, compare warmup 240 vs "
                        "605, then add per-supplier/item upstream-capacity override "
                        "before service 93/80 calibration"
                    ),
                    "publishable_results": False,
                    "automatic_publication_allowed": False,
                }
            )
            _write_json(manifest_path, manifest)
            return manifest
        except Exception as exc:
            manifest.update(
                {
                    "status": "failed",
                    "failed_at_utc": _utc_now(),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "scientifically_reviewable": False,
                    "publishable_results": False,
                }
            )
            _write_json(manifest_path, manifest)
            raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("validate", "smoke", "compare15"), default="validate"
    )
    parser.add_argument(
        "--protocol-dir", type=Path, default=protocol.DEFAULT_OUTPUT_DIR
    )
    parser.add_argument("--active-campaign-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode != "validate" and (
        args.active_campaign_dir is None or args.output_dir is None
    ):
        raise ValueError(
            "Execution modes require --active-campaign-dir and --output-dir"
        )
    result = run_comparison(
        protocol_dir=args.protocol_dir,
        active_campaign_dir=args.active_campaign_dir or Path.cwd(),
        output_dir=args.output_dir or Path.cwd(),
        mode=args.mode,
        workers=args.workers,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
