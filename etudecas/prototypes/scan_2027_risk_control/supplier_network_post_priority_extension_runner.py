#!/usr/bin/env python3
"""Execute a signed post-priority extension plan without altering main results.

The runner is additive.  It validates the signed plan and its source campaign,
references exact reusable cases, and executes only physical cases explicitly
marked as new.  ``plan`` performs no execution, ``smoke`` runs a small paired
subset, and ``full`` runs the complete signed design.  No result produced here
is written into the main lane or supplier rankings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field as dataclass_field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_IMPORT_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_IMPORT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_post_priority_extensions as planner,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_risk_screen_campaign as network,
)


SCHEMA_VERSION = "etudecas.supplier_network_post_priority_extension_runner.v1"
EXTENSION_FILES = {
    "multi_lane_supplier_common_cause": (
        "multi_lane_supplier_common_cause_design.csv",
        "multi_lane_supplier_common_cause_metrics.csv",
        "multi_lane_supplier_common_cause_flow_metrics.csv",
        "multi_lane_supplier_common_cause_summary.csv",
        "multi_lane_supplier_common_cause_manifest.json",
    ),
    "temporal_robustness": (
        "temporal_robustness_design.csv",
        "temporal_robustness_metrics.csv",
        "temporal_robustness_flow_metrics.csv",
        "temporal_robustness_summary.csv",
        "temporal_robustness_manifest.json",
    ),
    "priority_four_business_causes": (
        "priority_four_business_causes_design.csv",
        "priority_four_business_causes_metrics.csv",
        "priority_four_business_causes_flow_metrics.csv",
        "priority_four_business_causes_summary.csv",
        "priority_four_business_causes_manifest.json",
    ),
}
RUNNER_MANIFEST = "post_priority_extension_runner_manifest.json"
LEDGER_FILE = "execution_ledger.json"
BASELINE_MATERIALIZATION_POLICY = (
    "one_runner_generated_baseline_per_seed_horizon_trace_engine_input_and_"
    "outcome_bundle_with_compact_exact_window_flows_v2"
)
SEED_PREFIX_SCHEDULING_POLICY = "cumulative_signed_seed_prefix_v1"
PRELIMINARY_CHECKPOINT_REPEAT_COUNT = 15
PRELIMINARY_CHECKPOINT_MANIFEST = "preliminary_checkpoint_15_manifest.json"
PRELIMINARY_CHECKPOINT_SCHEMA = (
    "etudecas.supplier_network_post_priority_extension_runner_checkpoint.v1"
)
RUNNER_BASELINE_ALIAS_STATUS = "reused_runner_generated_baseline"
PRODUCTS = tuple(network.TARGET_PRODUCTS)
CAUSAL_DETAIL_FIELDS = (
    "case_key",
    "case_id",
    "seed",
    "failure_mode",
    "technical_key_type",
    "technical_key_id",
    "node_id",
    "item_id",
    "event_type",
    "uom",
    "baseline_day",
    "stress_day",
    "day_delta",
    "baseline_qty",
    "stress_qty",
    "qty_delta",
    "actual_difference_measured",
    "baseline_evidence_format",
    "pairing_input_sha256_pass",
    "pairing_j0_state_sha256_pass",
    "genealogical_exposure_only",
    "causal_scope",
    "counterfactual_entity_identity_validated",
    "pairing_method",
)
LOT_EXPOSURE_DETAIL_FIELDS = (
    "extension",
    "case_key",
    "case_id",
    "seed",
    "failure_mode",
    "stress_start_day",
    "stress_end_day",
    "chain_ids",
    "supplier_ids",
    "lot_id",
    "exposure_role",
    "genealogy_depth",
    "node_id",
    "item_id",
    "event_id",
    "event_type",
    "day",
    "qty",
    "uom",
    "risk_event_ids",
    "shipment_id",
    "production_campaign_id",
    "source_type",
    "source_id",
    "descendant_quantity_is_exposure_upper_bound",
    "causal_delay_or_loss_claimed",
    "counterfactual_entity_identity_validated",
    "industrial_lot_number_claimed",
    "lot_identifier_semantics",
)
CONSOLIDATED_SMALL_SOURCE_FILES = (
    "supplier_sensitivity_ranking.csv",
    "failure_mode_sensitivity_summary.csv",
    "confirmed_top3_stability.csv",
    "confirmation_supplier_sensitivity_ranking.csv",
    "confirmation_lane_sensitivity_ranking.csv",
    "lane_sensitivity_ranking.csv",
    "lane_priority_membership_stability.csv",
    "lane_evidence_status.csv",
    "confirmation_mathematical_family_summary.csv",
    "active_window_flow_release_gate_by_lane.csv",
)
CONSOLIDATED_SMALL_EXTENSION_FILES = (
    "multi_lane_supplier_common_cause_summary.csv",
    "multi_lane_supplier_common_cause_manifest.json",
    "temporal_robustness_summary.csv",
    "temporal_robustness_manifest.json",
    "priority_four_business_causes_summary.csv",
    "priority_four_business_causes_manifest.json",
    "lot_genealogical_exposure_summary.csv",
    "lot_genealogical_exposure_detail.csv",
    "causal_lot_attribution_summary.csv",
    "causal_lot_attribution_detail.csv",
    "causal_lot_attribution_manifest.json",
    RUNNER_MANIFEST,
)


@dataclass(frozen=True)
class LaneSpec:
    chain_id: str
    supplier_id: str
    item_id: str
    dst_node_id: str
    edge_id: str
    target_product_id: str

    @property
    def key(self) -> tuple[str, str, str]:
        return self.supplier_id, self.item_id, self.dst_node_id


@dataclass(frozen=True)
class PlannedCase:
    case_key: str
    extension: str
    case_id: str
    seed: int
    pairing_block_id: str
    paired_baseline_case_id: str
    mechanism_key: str
    risk_type: str
    mechanism_value: float
    mechanism_unit: str
    start_day: int
    end_day: int
    lot_trace_required: bool
    lanes: tuple[LaneSpec, ...]
    products: tuple[str, ...]
    action: str
    source_case_key: str = ""
    simulation_days: int = planner.BASE_SIMULATION_DAYS
    outcome_spec_id: str = "full_horizon_J0_J719"
    outcome_start_day: int = 0
    outcome_end_day: int = planner.BASE_SIMULATION_DAYS - 1
    outcome_day_count: int = planner.BASE_SIMULATION_DAYS
    outcome_bundle_sha256: str = ""
    outcome_specs: tuple[Mapping[str, Any], ...] = ()
    preincident_snapshot_day: int = -1


@dataclass
class CaseEvidence:
    case_key: str
    seed: int
    status: str
    input_sha256: str
    j0_state_sha256: str
    resolved_lot_trace_enabled: bool
    valid: bool
    validation_errors: list[str]
    product_metrics: list[dict[str, Any]]
    flow_metrics: list[dict[str, Any]]
    applied_event_ids: list[str]
    lot_events: list[dict[str, Any]]
    lot_genealogy: list[dict[str, Any]]
    run_dir: str = ""
    reused_source_case: bool = False
    simulation_days: int = planner.BASE_SIMULATION_DAYS
    outcome_bundle_sha256: str = ""
    local_product_metrics: list[dict[str, Any]] = dataclass_field(default_factory=list)
    preincident_state_snapshots: list[dict[str, Any]] = dataclass_field(default_factory=list)
    configured_event_ids: list[str] = dataclass_field(default_factory=list)
    loaded_event_rows: list[dict[str, Any]] = dataclass_field(default_factory=list)
    risk_input_sha256: str = ""
    risk_load_warnings: list[str] = dataclass_field(default_factory=list)
    risk_application_rows: list[dict[str, Any]] = dataclass_field(default_factory=list)
    extended_horizon_input_support_pass: bool = True
    post_J719_extrapolation_policy: str = ""


@dataclass(frozen=True)
class RunnerContext:
    plan_dir: Path
    source_dir: Path
    output_dir: Path
    mode: str
    days: int
    workers: int
    retention: str
    signature: str
    graph_path: Path
    engine_path: Path
    profile_path: Path
    run_config: network.campaign_core.RunConfig


Executor = Callable[[PlannedCase, RunnerContext, Path | None], CaseEvidence]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _process_is_running(process_id: int) -> bool:
    if process_id <= 0:
        return False
    if process_id == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        synchronize = 0x00100000
        wait_timeout = 0x00000102
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        )
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(synchronize, False, process_id)
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == wait_timeout
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(process_id, 0)
    except PermissionError:
        return True
    except (OSError, ProcessLookupError):
        return False
    return True


def _as_bool(value: Any) -> bool:
    return network.campaign_core.as_bool(value)


def _to_int(value: Any, default: int = 0) -> int:
    return network.campaign_core.to_int(value, default)


def _to_float(value: Any, default: float = 0.0) -> float:
    return network.campaign_core.to_float(value, default)


def _read_csv(path: Path) -> list[dict[str, str]]:
    return network.campaign_core.read_csv_rows(path)


def _read_json(path: Path) -> dict[str, Any]:
    return network.campaign_core.read_json(path)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if rows:
        network.campaign_core.write_csv_atomic(path, rows)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    network.campaign_core.write_json_atomic(path, payload)


def _sha256(path: Path) -> str:
    return network.campaign_core.sha256_file(path)


def _case_key(extension: str, case_id: str, seed: int) -> str:
    return f"{extension}::{case_id}::seed_{seed}"


def _lane_from_descriptor(value: str) -> LaneSpec:
    parts = str(value).split("|")
    if len(parts) != 6 or not all(parts):
        raise ValueError(f"Descripteur de voie invalide: {value!r}")
    return LaneSpec(*parts)


def _row_lanes(row: Mapping[str, Any]) -> tuple[LaneSpec, ...]:
    encoded = str(row.get("affected_lanes") or "").strip()
    if encoded:
        lanes = tuple(_lane_from_descriptor(value) for value in encoded.split(";"))
    else:
        lanes = (
            LaneSpec(
                chain_id=str(row.get("chain_id") or ""),
                supplier_id=str(row.get("supplier_id") or ""),
                item_id=str(row.get("item_id") or ""),
                dst_node_id=str(row.get("dst_node_id") or ""),
                edge_id=str(row.get("edge_id") or ""),
                target_product_id=str(row.get("target_product_id") or ""),
            ),
        )
    if any(not all(asdict(lane).values()) for lane in lanes):
        raise ValueError(f"Voie incomplète dans le cas {row.get('case_id')}")
    if len({lane.key for lane in lanes}) != len(lanes):
        raise ValueError(f"Voie dupliquée dans le cas {row.get('case_id')}")
    return lanes


def _stress_case(row: Mapping[str, Any]) -> PlannedCase:
    extension = str(row.get("extension") or "")
    case_id = str(row.get("case_id") or "")
    seed = _to_int(row.get("seed"), -1)
    lanes = _row_lanes(row)
    source_case_key = str(
        row.get("source_case_key")
        or row.get("source_incident_case_key")
        or ""
    )
    action = (
        "new_run_required"
        if _to_int(row.get("new_run_count"), 0) == 1
        else "reuse_exact_source_case"
    )
    case = PlannedCase(
        case_key=_case_key(extension, case_id, seed),
        extension=extension,
        case_id=case_id,
        seed=seed,
        pairing_block_id=str(row.get("pairing_block_id") or ""),
        paired_baseline_case_id=str(row.get("paired_baseline_case_id") or ""),
        mechanism_key=str(row.get("failure_mode") or ""),
        risk_type=str(row.get("risk_type") or ""),
        mechanism_value=_to_float(row.get("mechanism_value"), math.nan),
        mechanism_unit=str(row.get("mechanism_unit") or ""),
        start_day=_to_int(row.get("stress_start_day"), -1),
        end_day=_to_int(row.get("stress_end_day"), -1),
        lot_trace_required=_as_bool(row.get("lot_trace_required")),
        lanes=lanes,
        products=tuple(sorted({lane.target_product_id for lane in lanes})),
        action=action,
        source_case_key=source_case_key,
        simulation_days=_to_int(
            row.get("simulation_days"), planner.BASE_SIMULATION_DAYS
        ),
        outcome_spec_id=str(
            row.get("outcome_spec_id") or "full_horizon_J0_J719"
        ),
        outcome_start_day=_to_int(row.get("outcome_start_day"), 0),
        outcome_end_day=_to_int(
            row.get("outcome_end_day"), planner.BASE_SIMULATION_DAYS - 1
        ),
        outcome_day_count=_to_int(
            row.get("outcome_day_count"), planner.BASE_SIMULATION_DAYS
        ),
        outcome_bundle_sha256=str(row.get("outcome_bundle_sha256") or ""),
        outcome_specs=(),
        preincident_snapshot_day=_to_int(row.get("preincident_snapshot_day"), -1),
    )
    if not case.case_id or case.seed < 0 or not case.pairing_block_id:
        raise ValueError(f"Cas de stress incomplet: {case}")
    if case.start_day < 0 or case.end_day < case.start_day:
        raise ValueError(f"Fenêtre invalide pour {case.case_key}")
    if not math.isfinite(case.mechanism_value) or not case.mechanism_unit:
        raise ValueError(f"Valeur/unité de mécanisme invalide: {case.case_key}")
    if (
        case.simulation_days <= 0
        or case.outcome_start_day < 0
        or case.outcome_end_day < case.outcome_start_day
        or case.outcome_end_day >= case.simulation_days
        or case.outcome_day_count
        != case.outcome_end_day - case.outcome_start_day + 1
    ):
        raise ValueError(f"Horizon/outcome invalide pour {case.case_key}")
    mechanism = network.MECHANISM_BY_KEY.get(case.mechanism_key)
    if mechanism is None or mechanism.risk_type != case.risk_type:
        raise ValueError(f"Cause métier incohérente: {case.case_key}")
    return case


def _baseline_case(row: Mapping[str, Any]) -> PlannedCase:
    seed = _to_int(row.get("seed"), -1)
    case_id = str(row.get("baseline_case_id") or "")
    action = (
        "new_run_required"
        if _to_int(row.get("new_run_count"), 0) == 1
        else "reuse_exact_source_case"
    )
    raw_specs = str(row.get("outcome_specs_json") or "").strip()
    outcome_specs = tuple(json.loads(raw_specs)) if raw_specs else ()
    if not outcome_specs:
        outcome_specs = tuple(planner._full_horizon_outcome_bundle()["outcome_specs"])
    simulation_days = _to_int(
        row.get("simulation_days"), planner.BASE_SIMULATION_DAYS
    )
    for spec in outcome_specs:
        start = _to_int(spec.get("outcome_start_day"), -1)
        end = _to_int(spec.get("outcome_end_day"), -1)
        if start < 0 or end < start or end >= simulation_days:
            raise ValueError(f"Bundle outcome baseline invalide: {case_id}")
    return PlannedCase(
        case_key=_case_key("baseline", case_id, seed),
        extension="baseline",
        case_id=case_id,
        seed=seed,
        pairing_block_id=str(row.get("pairing_block_id") or ""),
        paired_baseline_case_id="",
        mechanism_key="baseline",
        risk_type="",
        mechanism_value=1.0,
        mechanism_unit="ratio",
        start_day=0,
        end_day=0,
        lot_trace_required=_as_bool(row.get("lot_trace_required")),
        lanes=(),
        products=PRODUCTS,
        action=action,
        source_case_key=str(row.get("source_case_key") or ""),
        simulation_days=simulation_days,
        outcome_spec_id="baseline_outcome_bundle",
        outcome_start_day=0,
        outcome_end_day=simulation_days - 1,
        outcome_day_count=simulation_days,
        outcome_bundle_sha256=str(row.get("outcome_bundle_sha256") or ""),
        outcome_specs=outcome_specs,
        preincident_snapshot_day=-1,
    )


def _validate_causal_source_evidence_row(row: Mapping[str, Any]) -> None:
    """Bind retained lot evidence to the hashes carried by the signed plan."""

    source_case_key = str(row.get("source_incident_case_key") or "").strip()
    evidence_format = str(row.get("source_incident_evidence_format") or "").strip()
    if not source_case_key:
        if evidence_format:
            raise ValueError(
                "Format de preuve lot source déclaré sans cas source réutilisable."
            )
        return
    if evidence_format == "raw_lot_exports":
        expected = {
            "data/production_lot_events.csv": str(
                row.get("source_incident_lot_events_sha256") or ""
            ),
            "data/production_lot_genealogy.csv": str(
                row.get("source_incident_lot_genealogy_sha256") or ""
            ),
        }
    elif evidence_format == "retained_genealogical_proof_exports":
        expected = {
            "proofs/impacted_receipt_lots.csv": str(
                row.get("source_incident_impacted_receipts_sha256") or ""
            ),
            "proofs/impacted_descendant_lots.csv": str(
                row.get("source_incident_impacted_descendants_sha256") or ""
            ),
            "proofs/impacted_genealogy.csv": str(
                row.get("source_incident_impacted_genealogy_sha256") or ""
            ),
        }
        optional_client_hash = str(
            row.get("source_incident_impacted_client_deliveries_sha256") or ""
        )
        if optional_client_hash:
            expected["proofs/impacted_client_deliveries.csv"] = optional_client_hash
    else:
        raise ValueError(
            "Format de preuve lot source absent ou inconnu pour un cas réutilisé: "
            f"{evidence_format!r}"
        )
    missing_hashes = [name for name, expected_hash in expected.items() if not expected_hash]
    if missing_hashes:
        raise ValueError(
            "Empreinte de preuve lot absente du plan signé: "
            + ", ".join(missing_hashes)
        )
    source_dir = Path(source_case_key).resolve()
    for relative, expected_hash in expected.items():
        path = source_dir / relative
        if not path.is_file():
            raise FileNotFoundError(f"Preuve lot source absente: {path}")
        if _sha256(path) != expected_hash:
            raise ValueError(f"Empreinte de preuve lot source invalide: {path}")


def load_signed_plan(
    plan_dir: Path,
    *,
    require_boundary_lineage: bool = False,
) -> tuple[dict[str, Any], list[PlannedCase], list[PlannedCase]]:
    plan_dir = plan_dir.resolve()
    planner.validate_plan_artifact(
        plan_dir, require_boundary_lineage=require_boundary_lineage
    )
    manifest = _read_json(plan_dir / "post_priority_extensions_plan_manifest.json")
    source_dir = Path(str(manifest.get("source_artifact") or "")).resolve()
    for name, expected in (manifest.get("source_artifact_file_hashes") or {}).items():
        path = source_dir / str(name)
        if not path.is_file() or _sha256(path) != str(expected):
            raise ValueError(f"Source réseau modifiée depuis le plan: {name}")
    design_paths = {
        "multi_lane_supplier_common_cause": (
            plan_dir / "multi_lane_supplier_common_cause_design.csv"
        ),
        "temporal_robustness": plan_dir / "temporal_robustness_design.csv",
        "priority_four_business_causes": (
            plan_dir / "priority_four_business_causes_design.csv"
        ),
        "causal_lot_attribution_subset": (
            plan_dir / "causal_lot_attribution_design.csv"
        ),
    }
    stress: list[PlannedCase] = []
    for expected_extension, path in design_paths.items():
        for row in _read_csv(path):
            if expected_extension == "causal_lot_attribution_subset":
                _validate_causal_source_evidence_row(row)
            case = _stress_case(row)
            if case.extension != expected_extension:
                raise ValueError(
                    f"Extension inattendue dans {path.name}: {case.extension}"
                )
            stress.append(case)
    baselines = [
        _baseline_case(row)
        for row in _read_csv(plan_dir / "paired_baseline_design.csv")
    ]
    all_keys = [case.case_key for case in [*baselines, *stress]]
    if len(all_keys) != len(set(all_keys)):
        raise ValueError("Le plan contient des clés physiques dupliquées.")
    baseline_by_id = {case.case_id: case for case in baselines}
    for case in stress:
        baseline = baseline_by_id.get(case.paired_baseline_case_id)
        if baseline is None:
            raise ValueError(f"Référence absente pour {case.case_key}")
        if baseline.seed != case.seed:
            raise ValueError(f"Graine non appariée pour {case.case_key}")
        if baseline.pairing_block_id != case.pairing_block_id:
            raise ValueError(f"Bloc d'appariement incohérent pour {case.case_key}")
        if baseline.lot_trace_required != case.lot_trace_required:
            raise ValueError(f"Traçage lots non apparié pour {case.case_key}")
        if baseline.simulation_days != case.simulation_days:
            raise ValueError(f"Horizon non apparié pour {case.case_key}")
        if baseline.outcome_bundle_sha256 != case.outcome_bundle_sha256:
            raise ValueError(f"Bundle outcome non apparié pour {case.case_key}")
        baseline_spec_ids = {
            str(spec.get("outcome_spec_id") or "") for spec in baseline.outcome_specs
        }
        if case.outcome_spec_id not in baseline_spec_ids:
            raise ValueError(f"Outcome local absent de la baseline: {case.case_key}")
        if case.action == "reuse_exact_source_case" and not case.source_case_key:
            raise ValueError(f"Référence source absente pour {case.case_key}")
    return manifest, baselines, stress


def _causal_source_material_hashes(plan_dir: Path) -> dict[str, str]:
    """Hash every retained source file that the causal extractor may consume."""

    result: dict[str, str] = {}
    rows = _read_csv(plan_dir / "causal_lot_attribution_design.csv")
    for row in rows:
        source_case_key = str(row.get("source_incident_case_key") or "").strip()
        if not source_case_key:
            continue
        source_dir = Path(source_case_key).resolve()
        evidence_format = str(row.get("source_incident_evidence_format") or "")
        if evidence_format == "raw_lot_exports":
            relatives = (
                "data/production_lot_events.csv",
                "data/production_lot_genealogy.csv",
            )
        elif evidence_format == "retained_genealogical_proof_exports":
            relatives = (
                "proofs/impacted_receipt_lots.csv",
                "proofs/impacted_descendant_lots.csv",
                "proofs/impacted_genealogy.csv",
            )
        else:
            raise ValueError(
                f"Format causal source inconnu pour empreinte runner: {evidence_format!r}"
            )
        for relative in relatives:
            path = source_dir / relative
            if not path.is_file():
                raise FileNotFoundError(f"Matériau causal source absent: {path}")
            key = f"{row.get('case_id')}::{relative}"
            result[key] = _sha256(path)
        optional_client = source_dir / "proofs" / "impacted_client_deliveries.csv"
        if evidence_format == "retained_genealogical_proof_exports" and optional_client.is_file():
            key = f"{row.get('case_id')}::proofs/impacted_client_deliveries.csv"
            result[key] = _sha256(optional_client)
    return dict(sorted(result.items()))


def _verify_configuration_paths(
    manifest: Mapping[str, Any],
    *,
    graph_path: Path,
    engine_path: Path,
    profile_path: Path,
) -> tuple[Path, Path, Path]:
    lock = manifest.get("execution_configuration_lock") or {}
    paths = {
        "graph_sha256": graph_path.resolve(),
        "engine_sha256": engine_path.resolve(),
        "profile_sha256": profile_path.resolve(),
    }
    for field, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"Fichier d'exécution absent: {path}")
        if _sha256(path) != str(lock.get(field) or ""):
            raise ValueError(f"Empreinte incompatible avec le plan: {field}")
    extraction_core = Path(network.campaign_core.__file__).resolve()
    if _sha256(extraction_core) != str(lock.get("v4_extraction_core_sha256") or ""):
        raise ValueError("Empreinte incompatible avec le plan: v4_extraction_core_sha256")
    return paths["graph_sha256"], paths["engine_sha256"], paths["profile_sha256"]


def _risk_rows(case: PlannedCase) -> list[dict[str, Any]]:
    if case.extension == "baseline":
        return []
    return [
        {
            "event_id": f"{case.case_id}__lane{index}",
            "risk_type": case.risk_type,
            "supplier_id": lane.supplier_id,
            "item_id": lane.item_id,
            "dst_node_id": lane.dst_node_id,
            "edge_id": lane.edge_id,
            "start_day": case.start_day,
            "end_day": case.end_day,
            "multiplier": case.mechanism_value,
            "notes": (
                "hypothèse conditionnelle exogène; extension séparée du classement principal"
            ),
        }
        for index, lane in enumerate(case.lanes, 1)
    ]


def _selected_cases(
    mode: str,
    baselines: Sequence[PlannedCase],
    stress: Sequence[PlannedCase],
) -> tuple[list[PlannedCase], list[PlannedCase]]:
    if mode in {"plan", "full"}:
        selected_stress = list(stress)
    else:
        selected_stress = []
        for extension in (
            "multi_lane_supplier_common_cause",
            "temporal_robustness",
            "priority_four_business_causes",
            "causal_lot_attribution_subset",
        ):
            candidates = sorted(
                (case for case in stress if case.extension == extension),
                key=lambda case: (case.action != "new_run_required", case.case_key),
            )
            if candidates:
                selected_stress.append(candidates[0])
    needed_baseline_ids = {case.paired_baseline_case_id for case in selected_stress}
    selected_baselines = [
        case for case in baselines if case.case_id in needed_baseline_ids
    ]
    return selected_baselines, selected_stress


def _signed_full_seed_ids(
    *,
    plan_manifest: Mapping[str, Any],
    stress_cases: Sequence[PlannedCase],
) -> tuple[int, ...]:
    raw_seeds = plan_manifest.get("confirmation_seeds")
    if not isinstance(raw_seeds, list) or any(
        isinstance(value, bool) or not isinstance(value, int) for value in raw_seeds
    ):
        raise ValueError("Liste signée des graines de confirmation invalide.")
    seed_ids = tuple(raw_seeds)
    if (
        len(seed_ids) != planner.FULL_PAIRED_SEED_COUNT
        or tuple(sorted(seed_ids)) != seed_ids
        or len(set(seed_ids)) != len(seed_ids)
    ):
        raise ValueError(
            "Les graines signées doivent être les 30 identifiants distincts triés."
        )
    expected_seed_set = set(seed_ids)
    for extension in (
        "multi_lane_supplier_common_cause",
        "temporal_robustness",
        "priority_four_business_causes",
    ):
        by_case_id: dict[str, list[int]] = defaultdict(list)
        for case in stress_cases:
            if case.extension == extension:
                by_case_id[case.case_id].append(case.seed)
        if not by_case_id:
            raise ValueError(f"Matrice signée absente: {extension}")
        for case_id, seeds in by_case_id.items():
            if len(seeds) != len(seed_ids) or set(seeds) != expected_seed_set:
                raise ValueError(
                    "Matrice signée incomplète pour le préfixe cumulatif: "
                    f"{extension}/{case_id}"
                )
    causal_seeds = {
        case.seed
        for case in stress_cases
        if case.extension == "causal_lot_attribution_subset"
    }
    if causal_seeds != {seed_ids[0]}:
        raise ValueError(
            "Les illustrations lots doivent rester sur la première graine signée."
        )
    return seed_ids


def _execution_seed_target(
    *,
    mode: str,
    signed_seed_ids: Sequence[int],
    checkpoint_after_repetitions: int | None,
) -> tuple[tuple[int, ...], bool]:
    if checkpoint_after_repetitions is not None:
        if mode != "full":
            raise ValueError(
                "--checkpoint-after-repetitions est autorisé uniquement en mode full."
            )
        if checkpoint_after_repetitions != PRELIMINARY_CHECKPOINT_REPEAT_COUNT:
            raise ValueError(
                "Le seul jalon pré-déclaré est exactement 15 répétitions sur 30."
            )
    if mode != "full":
        return tuple(), False
    if not signed_seed_ids:
        raise ValueError("Univers signé des graines absent en mode full.")
    if checkpoint_after_repetitions is None:
        return tuple(signed_seed_ids), False
    return (
        tuple(signed_seed_ids[:checkpoint_after_repetitions]),
        checkpoint_after_repetitions < len(signed_seed_ids),
    )


def _baseline_materialization_plan(
    baselines: Sequence[PlannedCase],
) -> tuple[list[PlannedCase], dict[str, str]]:
    """Select one physical baseline owner for each exact engine configuration.

    Source campaigns retained in ``summary`` mode do not keep the daily supplier
    shipment rows needed to measure arbitrary extension windows.  The runner
    therefore materializes one fresh baseline per seed/lot-trace setting and
    aliases any logically distinct pairing block with the same engine inputs.
    """

    owner_by_fingerprint: dict[tuple[int, int, bool, str], PlannedCase] = {}
    owner_key_by_case_key: dict[str, str] = {}
    for case in baselines:
        fingerprint = (
            case.seed,
            case.simulation_days,
            case.lot_trace_required,
            case.outcome_bundle_sha256,
        )
        owner = owner_by_fingerprint.setdefault(fingerprint, case)
        owner_key_by_case_key[case.case_key] = owner.case_key
    return list(owner_by_fingerprint.values()), owner_key_by_case_key


def _baseline_materialization_signature_payload(
    *,
    owners: Sequence[PlannedCase],
    owner_key_by_case_key: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "policy": BASELINE_MATERIALIZATION_POLICY,
        "physical_owner_case_keys": [case.case_key for case in owners],
        "logical_case_to_physical_owner": dict(sorted(owner_key_by_case_key.items())),
    }


def _runner_signature(
    *,
    plan_manifest: Mapping[str, Any],
    plan_manifest_sha256: str,
    mode: str,
    selected_baselines: Sequence[PlannedCase],
    selected_stress: Sequence[PlannedCase],
    baseline_materialization: Mapping[str, Any],
    causal_source_material_hashes: Mapping[str, str],
    scenario_id: str,
    days: int,
    retention: str,
    executor_contract: str,
    custom_executor_used: bool,
    signed_seed_ids: Sequence[int],
) -> str:
    return network.campaign_core.campaign_signature(
        {
            "schema_version": SCHEMA_VERSION,
            "runner_script_sha256": _sha256(Path(__file__)),
            "planner_script_sha256": _sha256(Path(planner.__file__)),
            "plan_signature": str(plan_manifest.get("plan_signature") or ""),
            "plan_manifest_sha256": plan_manifest_sha256,
            "mode": mode,
            "scenario_id": scenario_id,
            "days": days,
            "retention": retention,
            "executor_contract": executor_contract,
            "custom_executor_used": custom_executor_used,
            "seed_scheduling_policy": SEED_PREFIX_SCHEDULING_POLICY,
            "signed_full_seed_ids": list(signed_seed_ids),
            "priority_selection_lineage": plan_manifest.get(
                "priority_selection_lineage"
            ),
            "priority_selection_lineage_sha256": plan_manifest.get(
                "priority_selection_lineage_sha256"
            ),
            "case_simulation_days": {
                case.case_key: case.simulation_days
                for case in [*selected_baselines, *selected_stress]
            },
            "case_outcome_bundle_sha256": {
                case.case_key: case.outcome_bundle_sha256
                for case in [*selected_baselines, *selected_stress]
            },
            "selected_baseline_case_keys": [case.case_key for case in selected_baselines],
            "selected_stress_case_keys": [case.case_key for case in selected_stress],
            "baseline_materialization": dict(baseline_materialization),
            "causal_source_material_hashes": dict(causal_source_material_hashes),
            "execution_configuration_lock": plan_manifest.get(
                "execution_configuration_lock"
            ),
        }
    )


def _prepare_output(
    *,
    output_dir: Path,
    signature: str,
    manifest_payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    runner_manifest_path = output_dir / RUNNER_MANIFEST
    if output_dir.exists():
        if not runner_manifest_path.is_file():
            raise RuntimeError("Dossier de reprise sans manifeste runner.")
        existing = _read_json(runner_manifest_path)
        if str(existing.get("runner_signature") or "") != signature:
            raise RuntimeError("Reprise refusée: signature runner différente.")
        ledger = (
            _read_json(output_dir / LEDGER_FILE)
            if (output_dir / LEDGER_FILE).is_file()
            else {
                "runner_signature": signature,
                "case_files": {},
                "case_file_sha256": {},
            }
        )
        if str(ledger.get("runner_signature") or "") != signature:
            raise RuntimeError("Reprise refusée: signature du registre différente.")
        return existing, ledger
    output_dir.mkdir(parents=True, exist_ok=False)
    manifest = dict(manifest_payload)
    _write_json(runner_manifest_path, manifest)
    ledger = {
        "runner_signature": signature,
        "case_files": {},
        "case_file_sha256": {},
    }
    _write_json(output_dir / LEDGER_FILE, ledger)
    return manifest, ledger


def _canonical_result_paths(output_dir: Path) -> tuple[Path, ...]:
    paths = [
        output_dir / name
        for files in EXTENSION_FILES.values()
        for name in files[1:]
    ]
    paths.extend(
        output_dir / name
        for name in (
            "lot_genealogical_exposure_summary.csv",
            "lot_genealogical_exposure_detail.csv",
            "causal_lot_attribution_summary.csv",
            "causal_lot_attribution_detail.csv",
            "causal_lot_attribution_manifest.json",
            "promotion_controls.json",
        )
    )
    paths.append(output_dir / "consolidated_dashboard_network_artifact")
    return tuple(paths)


def _canonical_ledger_relative_path(case_key: str) -> Path:
    digest = hashlib.sha256(case_key.encode("utf-8")).hexdigest()[:20]
    return Path("ledger_cases") / f"{digest}.json"


def _validated_ledger_evidence_path(
    *,
    output_dir: Path,
    case_key: str,
    relative_value: Any,
) -> Path:
    relative = Path(str(relative_value or ""))
    canonical = _canonical_ledger_relative_path(case_key)
    if (
        not relative.parts
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != canonical.as_posix()
    ):
        raise RuntimeError(f"Chemin de registre non canonique pour {case_key}.")
    path = output_dir / relative
    canonical_path = output_dir / canonical
    if (
        path.is_symlink()
        or not path.is_file()
        or path.resolve() != canonical_path.resolve()
    ):
        raise RuntimeError(f"Preuve de registre absente ou redirigée pour {case_key}.")
    return path


def _validate_preliminary_checkpoint(
    *,
    output_dir: Path,
    runner_signature: str,
    plan_manifest_sha256: str,
    require_live_ledger_match: bool = False,
    expected_signed_seed_ids: Sequence[int] | None = None,
    expected_evidence_keys: set[str] | None = None,
) -> dict[str, Any] | None:
    path = output_dir / PRELIMINARY_CHECKPOINT_MANIFEST
    if not path.is_file():
        return None
    payload = _read_json(path)
    signature = str(payload.get("checkpoint_signature") or "")
    unsigned = dict(payload)
    unsigned.pop("checkpoint_signature", None)
    if (
        payload.get("schema_version") != PRELIMINARY_CHECKPOINT_SCHEMA
        or not signature
        or network.campaign_core.campaign_signature(unsigned) != signature
    ):
        raise RuntimeError("Manifeste du jalon préliminaire invalide.")
    if (
        str(payload.get("runner_signature") or "") != runner_signature
        or str(payload.get("plan_manifest_sha256") or "")
        != plan_manifest_sha256
        or str(payload.get("runner_builder_sha256") or "")
        != _sha256(Path(__file__))
        or str(payload.get("planner_builder_sha256") or "")
        != _sha256(Path(planner.__file__))
    ):
        raise RuntimeError("Lignée du jalon préliminaire incompatible.")
    evidence_files = payload.get("case_evidence_file_sha256")
    if not isinstance(evidence_files, dict) or not evidence_files:
        raise RuntimeError("Inventaire de preuves du jalon préliminaire absent.")
    relative_paths: set[str] = set()
    for case_key, item in evidence_files.items():
        if not isinstance(item, dict):
            raise RuntimeError(
                f"Référence de preuve préliminaire invalide: {case_key}"
            )
        relative = Path(str(item.get("relative_path") or ""))
        canonical_relative = _canonical_ledger_relative_path(str(case_key))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(
                f"Chemin de preuve préliminaire non canonique: {case_key}"
            )
        if relative.as_posix() != canonical_relative.as_posix():
            raise RuntimeError(
                f"Chemin de preuve préliminaire non canonique: {case_key}"
            )
        if relative.as_posix() in relative_paths:
            raise RuntimeError("Chemin de preuve préliminaire dupliqué.")
        relative_paths.add(relative.as_posix())
        evidence_path = _validated_ledger_evidence_path(
            output_dir=output_dir,
            case_key=str(case_key),
            relative_value=relative,
        )
        expected_hash = str(item.get("sha256") or "")
        if (
            not expected_hash
            or not evidence_path.is_file()
            or _sha256(evidence_path) != expected_hash
        ):
            raise RuntimeError(
                f"Preuve du jalon préliminaire altérée: {case_key}"
            )
        if str(_read_json(evidence_path).get("case_key") or "") != str(case_key):
            raise RuntimeError(
                f"Identité de preuve préliminaire incohérente: {case_key}"
            )
    expected_flags = {
        "status": "paused_preliminary",
        "seed_scheduling_policy": SEED_PREFIX_SCHEDULING_POLICY,
        "signed_full_seed_count": planner.FULL_PAIRED_SEED_COUNT,
        "completed_seed_count": PRELIMINARY_CHECKPOINT_REPEAT_COUNT,
        "logical_baseline_reference_count": 31,
        "physical_baseline_owner_count": 30,
        "logical_stress_case_count": 604,
        "reused_source_stress_case_count": 124,
        "executed_engine_physical_run_count": 510,
        "full_expected_engine_physical_run_count": 1020,
        "remaining_engine_physical_run_count": 510,
        "ledger_evidence_case_count": 634,
        "all_target_seed_jobs_complete": True,
        "no_future_seed_job_active": True,
        "full_universe_complete": False,
        "canonical_results_written": False,
        "consolidation_written": False,
        "preliminary_not_final": True,
        "finalization_eligible": False,
        "publishable_execution_contract_pass": False,
        "scoped_descriptive_priority_set_display_allowed": False,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "promotion_allowed": False,
    }
    if any(payload.get(key) != value for key, value in expected_flags.items()):
        raise RuntimeError("Compteurs ou gardes du jalon préliminaire invalides.")
    if len(evidence_files) != 634:
        raise RuntimeError("Nombre de preuves du jalon préliminaire invalide.")
    if expected_signed_seed_ids is not None:
        expected_seed_ids = list(expected_signed_seed_ids)
        if (
            payload.get("signed_full_seed_ids") != expected_seed_ids
            or payload.get("completed_seed_ids")
            != expected_seed_ids[:PRELIMINARY_CHECKPOINT_REPEAT_COUNT]
        ):
            raise RuntimeError("Graines du jalon préliminaire incompatibles.")
    if expected_evidence_keys is not None and set(evidence_files) != set(
        expected_evidence_keys
    ):
        raise RuntimeError("Cas du jalon préliminaire incompatibles avec le plan.")
    if payload.get("logical_stress_case_count_by_extension") != {
        "multi_lane_supplier_common_cause": 120,
        "temporal_robustness": 240,
        "priority_four_business_causes": 240,
        "causal_lot_attribution_subset": 4,
    }:
        raise RuntimeError("Matrice du jalon préliminaire invalide.")
    ledger_path = output_dir / LEDGER_FILE
    if not ledger_path.is_file():
        raise RuntimeError("Registre live absent pour le jalon préliminaire.")
    ledger = _read_json(ledger_path)
    checkpoint_paths = {
        key: str(item["relative_path"])
        for key, item in evidence_files.items()
    }
    checkpoint_hashes = {
        key: str(item["sha256"])
        for key, item in evidence_files.items()
    }
    live_paths = ledger.get("case_files") or {}
    live_hashes = ledger.get("case_file_sha256") or {}
    if str(ledger.get("runner_signature") or "") != runner_signature or any(
        live_paths.get(key) != relative or live_hashes.get(key) != checkpoint_hashes[key]
        for key, relative in checkpoint_paths.items()
    ):
        raise RuntimeError(
            "Les preuves du jalon préliminaire ne sont plus un sous-ensemble "
            "exact du registre live."
        )
    if require_live_ledger_match:
        expected_ledger_hash = str(
            payload.get("execution_ledger_sha256_at_checkpoint") or ""
        )
        if not expected_ledger_hash or _sha256(ledger_path) != expected_ledger_hash:
            raise RuntimeError("Registre live différent du jalon préliminaire.")
        if live_paths != checkpoint_paths or live_hashes != checkpoint_hashes:
            raise RuntimeError("Contenu du registre live différent du jalon.")
        ledger_dir = output_dir / "ledger_cases"
        disk_files = {
            path.relative_to(output_dir).as_posix()
            for path in ledger_dir.rglob("*")
            if path.is_file()
        }
        if disk_files != relative_paths:
            raise RuntimeError(
                "Inventaire disque des preuves du jalon préliminaire non exact."
            )
    return payload


def _write_preliminary_checkpoint(
    *,
    output_dir: Path,
    runner_signature: str,
    plan_manifest: Mapping[str, Any],
    plan_manifest_sha256: str,
    signed_seed_ids: Sequence[int],
    completed_seed_ids: Sequence[int],
    selected_baselines: Sequence[PlannedCase],
    selected_stress: Sequence[PlannedCase],
    baseline_owners: Sequence[PlannedCase],
    evidence_by_case_key: Mapping[str, CaseEvidence],
    case_files: Mapping[str, str],
    case_file_hashes: Mapping[str, str],
    ledger_sha256: str,
) -> dict[str, Any]:
    if any(path.exists() for path in _canonical_result_paths(output_dir)):
        raise RuntimeError(
            "Un jalon préliminaire ne peut coexister avec des résultats "
            "canoniques ou une consolidation finale."
        )
    expected_evidence_keys = {
        case.case_key for case in [*baseline_owners, *selected_stress]
    }
    if set(evidence_by_case_key) != expected_evidence_keys:
        missing = sorted(expected_evidence_keys - set(evidence_by_case_key))
        extra = sorted(set(evidence_by_case_key) - expected_evidence_keys)
        raise RuntimeError(
            "Inventaire du jalon préliminaire non exact: "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    if set(case_files) != set(case_file_hashes) or set(case_files) != expected_evidence_keys:
        raise RuntimeError("Registre de preuves préliminaire non exact.")
    evidence_file_hashes = {
        key: {
            "relative_path": str(case_files[key]),
            "sha256": str(case_file_hashes[key]),
        }
        for key in sorted(expected_evidence_keys)
    }
    extension_counts = {
        extension: sum(case.extension == extension for case in selected_stress)
        for extension in (
            "multi_lane_supplier_common_cause",
            "temporal_robustness",
            "priority_four_business_causes",
            "causal_lot_attribution_subset",
        )
    }
    executed_engine_count = len(baseline_owners) + sum(
        case.action == "new_run_required" for case in selected_stress
    )
    reused_source_count = sum(
        case.action == "reuse_exact_source_case" for case in selected_stress
    )
    payload: dict[str, Any] = {
        "schema_version": PRELIMINARY_CHECKPOINT_SCHEMA,
        "status": "paused_preliminary",
        "checkpoint_at_utc": _utc_now(),
        "runner_signature": runner_signature,
        "runner_builder_sha256": _sha256(Path(__file__)),
        "planner_builder_sha256": _sha256(Path(planner.__file__)),
        "plan_signature": str(plan_manifest.get("plan_signature") or ""),
        "plan_manifest_sha256": plan_manifest_sha256,
        "priority_selection_lineage_sha256": str(
            plan_manifest.get("priority_selection_lineage_sha256") or ""
        ),
        "seed_scheduling_policy": SEED_PREFIX_SCHEDULING_POLICY,
        "signed_full_seed_count": len(signed_seed_ids),
        "signed_full_seed_ids": list(signed_seed_ids),
        "completed_seed_count": len(completed_seed_ids),
        "completed_seed_ids": list(completed_seed_ids),
        "logical_baseline_reference_count": len(selected_baselines),
        "physical_baseline_owner_count": len(baseline_owners),
        "logical_stress_case_count": len(selected_stress),
        "logical_stress_case_count_by_extension": extension_counts,
        "reused_source_stress_case_count": reused_source_count,
        "executed_engine_physical_run_count": executed_engine_count,
        "full_expected_engine_physical_run_count": _to_int(
            (plan_manifest.get("planned_case_counts") or {}).get(
                "expected_engine_physical_run_count"
            ),
            -1,
        ),
        "remaining_engine_physical_run_count": _to_int(
            (plan_manifest.get("planned_case_counts") or {}).get(
                "expected_engine_physical_run_count"
            ),
            -1,
        )
        - executed_engine_count,
        "ledger_evidence_case_count": len(expected_evidence_keys),
        "case_evidence_file_sha256": evidence_file_hashes,
        "execution_ledger_sha256_at_checkpoint": ledger_sha256,
        "all_target_seed_jobs_complete": True,
        "no_future_seed_job_active": True,
        "full_universe_complete": False,
        "canonical_results_written": False,
        "consolidation_written": False,
        "preliminary_not_final": True,
        "finalization_eligible": False,
        "publishable_execution_contract_pass": False,
        "scoped_descriptive_priority_set_display_allowed": False,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "promotion_allowed": False,
        "checkpoint_signature_semantics": (
            "internal_integrity_digest_not_authenticated_signature"
        ),
    }
    if (
        len(signed_seed_ids) != planner.FULL_PAIRED_SEED_COUNT
        or len(completed_seed_ids) != PRELIMINARY_CHECKPOINT_REPEAT_COUNT
        or extension_counts
        != {
            "multi_lane_supplier_common_cause": 120,
            "temporal_robustness": 240,
            "priority_four_business_causes": 240,
            "causal_lot_attribution_subset": 4,
        }
        or len(selected_baselines) != 31
        or len(baseline_owners) != 30
        or len(expected_evidence_keys) != 634
        or reused_source_count != 124
        or executed_engine_count != 510
        or payload["remaining_engine_physical_run_count"] != 510
    ):
        raise RuntimeError(
            "Le jalon ne correspond pas au contrat pré-déclaré 15/30 du plan V3."
        )
    payload["checkpoint_signature"] = network.campaign_core.campaign_signature(
        payload
    )
    path = output_dir / PRELIMINARY_CHECKPOINT_MANIFEST
    existing = _validate_preliminary_checkpoint(
        output_dir=output_dir,
        runner_signature=runner_signature,
        plan_manifest_sha256=plan_manifest_sha256,
        require_live_ledger_match=True,
        expected_signed_seed_ids=signed_seed_ids,
        expected_evidence_keys=expected_evidence_keys,
    )
    if existing is not None:
        stable_existing = dict(existing)
        stable_payload = dict(payload)
        for item in (stable_existing, stable_payload):
            item.pop("checkpoint_at_utc", None)
            item.pop("checkpoint_signature", None)
        if stable_existing != stable_payload:
            raise RuntimeError("Le jalon préliminaire existant est incompatible.")
        return existing
    _write_json(path, payload)
    validated = _validate_preliminary_checkpoint(
        output_dir=output_dir,
        runner_signature=runner_signature,
        plan_manifest_sha256=plan_manifest_sha256,
        require_live_ledger_match=True,
        expected_signed_seed_ids=signed_seed_ids,
        expected_evidence_keys=expected_evidence_keys,
    )
    if validated is None:
        raise RuntimeError("Le jalon préliminaire n'a pas été matérialisé.")
    return validated


def _graph_uom(
    graph: Mapping[str, Any], *, node_id: str, item_id: str
) -> str:
    candidates: set[str] = set()
    for node in graph.get("nodes") or []:
        if str(node.get("id") or "") != node_id:
            continue
        inventory = node.get("inventory") or {}
        for state in inventory.get("states") or []:
            if str(state.get("item_id") or "") == item_id:
                uom = str(state.get("uom") or "").strip()
                if uom:
                    candidates.add(uom)
    if len(candidates) == 1:
        return next(iter(candidates))
    for edge in graph.get("edges") or []:
        if (
            str(edge.get("from") or "") == node_id
            or str(edge.get("to") or "") == node_id
        ) and item_id in {str(item) for item in edge.get("items") or []}:
            uom = str((edge.get("order_terms") or {}).get("quantity_unit") or "")
            if uom:
                candidates.add(uom)
    if len(candidates) != 1:
        raise ValueError(f"Unité ambiguë ou absente: {node_id}/{item_id}: {candidates}")
    return next(iter(candidates))


def _build_run_config(
    *,
    source_dir: Path,
    output_dir: Path,
    graph_path: Path,
    engine_path: Path,
    profile_path: Path,
    scenario_id: str,
    days: int,
    retention: str,
) -> network.campaign_core.RunConfig:
    floors_path = source_dir / "inputs" / "prepared_physical_supplier_floors.csv"
    if not floors_path.is_file():
        raise FileNotFoundError(f"Capacités physiques préparées absentes: {floors_path}")
    floor_rows = _read_csv(floors_path)
    source_manifest = _read_json(source_dir / "campaign_manifest.json")
    expected_floor_signature = str(
        source_manifest.get("prepared_supplier_floor_content_sha256") or ""
    )
    actual_floor_signature = network.campaign_core.campaign_signature(
        {"rows": floor_rows}
    )
    if not expected_floor_signature or actual_floor_signature != expected_floor_signature:
        raise ValueError("Les capacités préparées diffèrent du manifeste réseau source.")
    physical_map = {
        (
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        ): _to_float(row.get("tested_capacity_floor_qty_per_day"))
        for row in floor_rows
    }
    return network.campaign_core.RunConfig(
        repo_root=_IMPORT_REPO_ROOT,
        output_dir=output_dir,
        engine=engine_path,
        graph=graph_path,
        supplier_floors=floors_path,
        factory_capacities=None,
        profile_args=tuple(network.campaign_core.engine_profile_args(profile_path)),
        scenario_id=scenario_id,
        days=days,
        retention=retention,
        physical_capacity_by_lane=physical_map,
    )


def _source_metric_index(source_dir: Path) -> dict[str, Mapping[str, str]]:
    path = source_dir / "confirmation_metrics.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Métriques source absentes: {path}")
    result: dict[str, Mapping[str, str]] = {}
    for row in _read_csv(path):
        key = planner._source_case_key(row)
        if key in result:
            raise ValueError(f"Référence source dupliquée: {key}")
        result[key] = dict(row)
    return result


def _source_product_metrics(
    row: Mapping[str, Any],
    case: PlannedCase,
    chain_product: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    products = PRODUCTS if case.extension == "baseline" else case.products
    metrics: list[dict[str, Any]] = []
    for product in products:
        released = math.nan
        if case.extension != "baseline":
            released = _to_float(row.get("target_released_qty"), math.nan)
        else:
            chain_values: list[float] = []
            for field, value in row.items():
                if not (
                    field.startswith("baseline_chain__")
                    and field.endswith("__ops__target_released_qty")
                ):
                    continue
                chain_id = field.removeprefix("baseline_chain__").removesuffix(
                    "__ops__target_released_qty"
                )
                if chain_product and chain_product.get(chain_id) != product:
                    continue
                numeric = _to_float(value, math.nan)
                if math.isfinite(numeric):
                    chain_values.append(numeric)
            if chain_values:
                released = max(chain_values)
        metrics.append(
            {
                "product_id": product,
                "uom": "UN",
                "demand_qty": _to_float(row.get(f"demand_qty_{product}"), math.nan),
                "fill_rate": _to_float(row.get(f"fill_rate_{product}"), math.nan),
                "on_due_ratio": _to_float(
                    row.get(f"on_due_volume_proxy_{product}"), math.nan
                ),
                "backlog_qty_days": _to_float(
                    row.get(f"backlog_qty_days_{product}"), math.nan
                ),
                "backlog_end_qty": _to_float(
                    row.get(f"backlog_end_qty_{product}"), math.nan
                ),
                "released_qty": released,
            }
        )
    return metrics


def _source_flow_metrics(
    row: Mapping[str, Any], case: PlannedCase
) -> list[dict[str, Any]]:
    if case.extension == "baseline" or len(case.lanes) != 1:
        return []
    lane = case.lanes[0]
    return [
        {
            "chain_id": lane.chain_id,
            "supplier_id": lane.supplier_id,
            "item_id": lane.item_id,
            "dst_node_id": lane.dst_node_id,
            "uom": str(row.get("component_stock_uom") or ""),
            "pulled_qty": _to_float(row.get("active_window_pulled_qty"), math.nan),
            "shipped_qty": _to_float(row.get("active_window_shipped_qty"), math.nan),
        }
    ]


def _full_local_metrics_from_aggregate(
    metrics: Sequence[Mapping[str, Any]], *, spec_id: str, days: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        demand = _to_float(metric.get("demand_qty"), math.nan)
        on_due = _to_float(metric.get("on_due_ratio"), math.nan)
        backlog = _to_float(metric.get("backlog_qty_days"), math.nan)
        rows.append(
            {
                "outcome_spec_id": spec_id,
                "outcome_start_day": 0,
                "outcome_end_day": days - 1,
                "outcome_day_count": days,
                "product_id": str(metric.get("product_id") or ""),
                "uom": str(metric.get("uom") or ""),
                "demand_qty_denominator": demand,
                "required_qty_denominator": demand,
                "served_qty_numerator": demand
                * _to_float(metric.get("fill_rate"), math.nan),
                "fill_rate": _to_float(metric.get("fill_rate"), math.nan),
                "served_on_due_qty_numerator": demand * on_due,
                "on_due_ratio": on_due,
                "backlog_qty_days_numerator": backlog,
                "normalized_backlog_days_per_demand_unit": backlog / demand,
                "backlog_end_qty": _to_float(metric.get("backlog_end_qty"), math.nan),
                "released_qty_numerator": _to_float(
                    metric.get("released_qty"), math.nan
                ),
                "series_day_count": days,
                "series_complete": True,
                "recovery_metric_status": "excluded_not_redefined",
            }
        )
    return rows


def source_case_evidence(
    case: PlannedCase,
    source_index: Mapping[str, Mapping[str, str]],
    source_dir: Path,
) -> CaseEvidence:
    row = source_index.get(case.source_case_key)
    if row is None:
        raise ValueError(f"Cas source référencé introuvable: {case.source_case_key}")
    if _to_int(row.get("seed"), -1) != case.seed:
        raise ValueError(f"Graine du cas source incompatible: {case.case_key}")
    required_trace = _as_bool(row.get("lot_trace_required_for_paired_seed_block"))
    resolved_value = str(row.get("resolved_lot_trace_enabled") or "").strip()
    if not resolved_value:
        raise ValueError(f"Traçage résolu absent du cas source: {case.case_key}")
    resolved_trace = _as_bool(resolved_value)
    if required_trace != case.lot_trace_required or resolved_trace != required_trace:
        raise ValueError(f"Traçage du cas source incompatible: {case.case_key}")
    chain_product = {
        str(item.get("chain_id") or ""): str(item.get("target_product_id") or "")
        for item in _read_csv(source_dir / "active_lane_reference.csv")
    }
    product_metrics = _source_product_metrics(row, case, chain_product)
    source_case_dir = Path(str(row.get("run_dir") or "")).resolve()
    summary_path = source_case_dir / "summaries" / "first_simulation_summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"Résumé source absent: {summary_path}")
    summary = _read_json(summary_path)
    risk_policy = (summary.get("policy") or {}).get("supplier_risk") or {}
    risk_path_value = str(risk_policy.get("events_csv") or "").strip()
    risk_path = Path(risk_path_value).resolve() if risk_path_value else None
    configured_ids, loaded_rows, risk_hash, risk_warnings = _loaded_risk_contract(
        summary=summary,
        risk_csv=risk_path,
    )
    expected_application_count = _to_int(row.get("risk_applied_rows"), 0)
    application_rows = (
        [{"event_ids": event_id, "source": "retained_source_summary"} for event_id in configured_ids]
        if expected_application_count > 0
        else []
    )
    return CaseEvidence(
        case_key=case.case_key,
        seed=case.seed,
        status="reused_exact_source_case",
        input_sha256=str(row.get("input_sha256") or ""),
        j0_state_sha256=str(row.get("j0_state_sha256") or ""),
        resolved_lot_trace_enabled=resolved_trace,
        valid=_as_bool(row.get("valid")),
        validation_errors=[
            value
            for value in str(row.get("validation_errors") or "").split(" | ")
            if value
        ],
        product_metrics=product_metrics,
        flow_metrics=_source_flow_metrics(row, case),
        applied_event_ids=(configured_ids if expected_application_count > 0 else []),
        lot_events=[],
        lot_genealogy=[],
        run_dir=str(row.get("run_dir") or ""),
        reused_source_case=True,
        simulation_days=case.simulation_days,
        outcome_bundle_sha256=case.outcome_bundle_sha256,
        local_product_metrics=_full_local_metrics_from_aggregate(
            product_metrics,
            spec_id=case.outcome_spec_id,
            days=case.simulation_days,
        ),
        configured_event_ids=configured_ids,
        loaded_event_rows=loaded_rows,
        risk_input_sha256=risk_hash,
        risk_load_warnings=risk_warnings,
        risk_application_rows=application_rows,
        extended_horizon_input_support_pass=True,
        post_J719_extrapolation_policy="not_applicable_fixed_J0_J719",
    )


def _risk_event_tokens(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return unique event ids from both engine serialisation conventions.

    The daily application export uses comma-separated ids while lot exports
    historically used ``|``.  Empty or repeated tokens are rejected so that
    an apparently complete exposure cannot hide an ambiguous application.
    """

    tokens: list[str] = []
    for row in rows:
        for field in ("event_ids", "risk_event_ids"):
            raw = str(row.get(field) or "").strip()
            if not raw:
                continue
            values = [value.strip() for value in re.split(r"[|,]", raw)]
            if any(not value for value in values):
                raise ValueError(f"Identifiant risque vide dans {field}: {raw!r}")
            tokens.extend(values)
    if len(tokens) != len(set(tokens)):
        # A token may legitimately recur on several application days.  The
        # ambiguity that matters is a duplicate inside one encoded field, so
        # re-check each field locally before returning the unique inventory.
        for row in rows:
            for field in ("event_ids", "risk_event_ids"):
                raw = str(row.get(field) or "").strip()
                if not raw:
                    continue
                values = [value.strip() for value in re.split(r"[|,]", raw)]
                if len(values) != len(set(values)):
                    raise ValueError(
                        f"Identifiant risque dupliqué dans {field}: {raw!r}"
                    )
    return sorted(set(tokens))


def _normalized_risk_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(row.get("event_id") or ""),
        "risk_type": str(row.get("risk_type") or ""),
        "supplier_id": str(row.get("supplier_id") or ""),
        "item_id": str(row.get("item_id") or ""),
        "dst_node_id": str(row.get("dst_node_id") or ""),
        "edge_id": str(row.get("edge_id") or ""),
        "start_day": _to_int(row.get("start_day"), -1),
        "end_day": _to_int(row.get("end_day"), -1),
        "multiplier": _to_float(row.get("multiplier"), math.nan),
        "notes": str(row.get("notes") or ""),
    }


def _resolve_reused_source_risk_edges(
    rows: Sequence[Mapping[str, Any]],
    graph: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve the source campaign's optional edge wildcard fail-closed.

    The main network campaign deliberately targets one-lane events with the
    exact supplier/item/destination tuple and leaves ``edge_id`` empty.  The
    extension plan retains the graph edge identifier as additional scope
    evidence.  A blank source edge is therefore equivalent only when the
    locked graph resolves that tuple to exactly one non-empty edge.  Explicit
    source edge identifiers must themselves belong to the same tuple.
    """

    resolved: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, source_row in enumerate(rows, 1):
        row = dict(source_row)
        supplier_id = str(row.get("supplier_id") or "")
        item_id = str(row.get("item_id") or "")
        dst_node_id = str(row.get("dst_node_id") or "")
        matching_edges = [
            str(edge.get("id") or "")
            for edge in graph.get("edges") or []
            if str(edge.get("from") or "") == supplier_id
            and str(edge.get("to") or "") == dst_node_id
            and item_id in {str(item) for item in edge.get("items") or []}
        ]
        explicit_edge_id = str(row.get("edge_id") or "")
        if explicit_edge_id:
            if explicit_edge_id not in matching_edges:
                errors.append(
                    "arête risque source explicite hors du triplet planifié "
                    f"(ligne {index}: {explicit_edge_id!r})"
                )
        elif len(matching_edges) != 1 or not matching_edges[0]:
            errors.append(
                "arête risque source vide non résolue de façon unique "
                f"(ligne {index}: {supplier_id}/{item_id}/{dst_node_id}, "
                f"candidats={matching_edges!r})"
            )
        else:
            row["edge_id"] = matching_edges[0]
        resolved.append(row)
    return resolved, errors


def _loaded_risk_contract(
    *, summary: Mapping[str, Any], risk_csv: Path | None
) -> tuple[list[str], list[dict[str, Any]], str, list[str]]:
    """Extract the exact risk configuration loaded by the engine.

    Configuration integrity is deliberately independent from whether an event
    was exercised by a shipment during its window.
    """

    policy = (summary.get("policy") or {}).get("supplier_risk") or {}
    tracking = summary.get("production_tracking") or {}
    loaded_rows = [
        _normalized_risk_row(row)
        for row in tracking.get("supplier_risk_events") or []
    ]
    loaded_rows = _canonical_rows(loaded_rows)
    configured_ids = [str(row.get("event_id") or "") for row in loaded_rows]
    if any(not value for value in configured_ids):
        raise ValueError("Le moteur publie un identifiant de risque vide.")
    if len(configured_ids) != len(set(configured_ids)):
        raise ValueError("Le moteur publie des identifiants de risque dupliqués.")
    warnings = [str(value) for value in policy.get("warnings") or []]
    declared_hash = str(policy.get("events_csv_sha256") or "")
    if risk_csv is None:
        if loaded_rows or _to_int(policy.get("event_count"), 0) != 0:
            raise ValueError("Une baseline neutre a chargé des événements risque.")
        return [], [], declared_hash, warnings
    live_hash = _sha256(risk_csv)
    if declared_hash != live_hash:
        raise ValueError("Empreinte du fichier risque chargé différente du fichier écrit.")
    if _to_int(policy.get("event_count"), -1) != len(loaded_rows):
        raise ValueError("Nombre d'événements risque chargé incohérent.")
    if warnings:
        raise ValueError("Avertissement au chargement des risques: " + " | ".join(warnings))
    return sorted(configured_ids), loaded_rows, live_hash, warnings


def _extract_product_metrics(
    *, case_dir: Path, graph: Mapping[str, Any], days: int
) -> list[dict[str, Any]]:
    service_rows = _read_csv(case_dir / "data" / "production_demand_service_daily.csv")
    service = network.campaign_core.compute_service_metrics(
        service_rows,
        client_node_id="C-XXXXX",
        products=PRODUCTS,
        days=days,
    )
    output_rows = _read_csv(case_dir / "data" / "production_output_products_daily.csv")
    result: list[dict[str, Any]] = []
    for product in PRODUCTS:
        product_item = f"item:{product}"
        relevant = [
            row for row in output_rows if str(row.get("item_id") or "") == product_item
        ]
        output_nodes = {str(row.get("node_id") or "") for row in relevant}
        uoms = {
            _graph_uom(graph, node_id=node, item_id=product_item)
            for node in output_nodes
            if node
        }
        if len(uoms) != 1:
            raise ValueError(f"Unité produit ambiguë: {product}: {uoms}")
        values = service[product]
        result.append(
            {
                "product_id": product,
                "uom": next(iter(uoms)),
                "demand_qty": values["demand_qty"],
                "fill_rate": values["fill_rate"],
                "on_due_ratio": values["on_due_volume_proxy"],
                "backlog_qty_days": values["backlog_qty_days"],
                "backlog_end_qty": values["backlog_end_qty"],
                "released_qty": sum(
                    max(0.0, _to_float(row.get("released_qty"))) for row in relevant
                ),
                "horizon_complete": values["horizon_complete"],
            }
        )
    return result


def _case_outcome_specs(case: PlannedCase) -> tuple[Mapping[str, Any], ...]:
    if case.outcome_specs:
        return case.outcome_specs
    return (
        {
            "outcome_spec_id": case.outcome_spec_id,
            "incident_start_day": case.start_day,
            "incident_end_day": case.end_day,
            "outcome_start_day": case.outcome_start_day,
            "outcome_end_day": case.outcome_end_day,
            "outcome_day_count": case.outcome_day_count,
        },
    )


def _extract_local_product_metrics(
    *, case_dir: Path, graph: Mapping[str, Any], case: PlannedCase
) -> list[dict[str, Any]]:
    service_rows = _read_csv(case_dir / "data" / "production_demand_service_daily.csv")
    output_rows = _read_csv(case_dir / "data" / "production_output_products_daily.csv")
    results: list[dict[str, Any]] = []
    for spec in _case_outcome_specs(case):
        spec_id = str(spec.get("outcome_spec_id") or "")
        start = _to_int(spec.get("outcome_start_day"), -1)
        end = _to_int(spec.get("outcome_end_day"), -1)
        expected_days = end - start + 1
        if not spec_id or start < 0 or end < start or end >= case.simulation_days:
            raise ValueError(f"Outcome local invalide: {case.case_key}/{spec_id}")
        products = PRODUCTS if case.extension == "baseline" else case.products
        for product in products:
            item = f"item:{product}"
            daily = [
                row
                for row in service_rows
                if start <= _to_int(row.get("day"), -1) <= end
                and str(row.get("node_id") or "") == "C-XXXXX"
                and str(row.get("item_id") or "") == item
            ]
            days_seen = {_to_int(row.get("day"), -1) for row in daily}
            if days_seen != set(range(start, end + 1)):
                raise ValueError(
                    f"Série service locale incomplète: {case.case_key}/{spec_id}/{product}"
                )
            demand = 0.0
            required_total = 0.0
            served_total = 0.0
            served_on_due = 0.0
            backlog_qty_days = 0.0
            backlog_end = 0.0
            for row in daily:
                day_demand = max(0.0, _to_float(row.get("demand_qty")))
                served = max(0.0, _to_float(row.get("served_qty")))
                required = max(
                    day_demand,
                    _to_float(row.get("required_with_backlog_qty"), day_demand),
                )
                starting_backlog = max(0.0, required - day_demand)
                demand += day_demand
                required_total += required
                served_total += min(served, required)
                served_on_due += min(
                    day_demand, max(0.0, served - starting_backlog)
                )
                backlog = max(0.0, _to_float(row.get("backlog_end_qty")))
                backlog_qty_days += backlog
                if _to_int(row.get("day"), -1) == end:
                    backlog_end += backlog
            if demand <= 0.0:
                raise ValueError(
                    f"Demande locale nulle: {case.case_key}/{spec_id}/{product}"
                )
            output = [
                row
                for row in output_rows
                if start <= _to_int(row.get("day"), -1) <= end
                and str(row.get("item_id") or "") == item
            ]
            output_nodes = {str(row.get("node_id") or "") for row in output}
            uoms = {
                _graph_uom(graph, node_id=node, item_id=item)
                for node in output_nodes
                if node
            }
            if len(uoms) != 1:
                raise ValueError(
                    f"Unité produit locale ambiguë: {case.case_key}/{product}: {uoms}"
                )
            released = sum(
                max(0.0, _to_float(row.get("released_qty"))) for row in output
            )
            results.append(
                {
                    "outcome_spec_id": spec_id,
                    "outcome_start_day": start,
                    "outcome_end_day": end,
                    "outcome_day_count": expected_days,
                    "product_id": product,
                    "uom": next(iter(uoms)),
                    "demand_qty_denominator": demand,
                    "required_qty_denominator": required_total,
                    "served_qty_numerator": served_total,
                    "fill_rate": (
                        served_total / required_total if required_total > 0.0 else 1.0
                    ),
                    "served_on_due_qty_numerator": served_on_due,
                    "on_due_ratio": served_on_due / demand,
                    "backlog_qty_days_numerator": backlog_qty_days,
                    "normalized_backlog_days_per_demand_unit": (
                        backlog_qty_days / demand
                    ),
                    "backlog_end_qty": backlog_end,
                    "released_qty_numerator": released,
                    "series_day_count": len(days_seen),
                    "series_complete": True,
                    "recovery_metric_status": "excluded_not_redefined",
                }
            )
    return results


def _canonical_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (dict(row) for row in rows),
        key=lambda row: json.dumps(
            row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
    )


def _project_rows(
    rows: Sequence[Mapping[str, Any]], fields: Sequence[str]
) -> list[dict[str, Any]]:
    """Keep only state available at the requested day, never end-of-run fields."""

    return _canonical_rows(
        [{field: row.get(field, "") for field in fields} for row in rows]
    )


def _extract_preincident_state_snapshots(
    *, case_dir: Path, summary: Mapping[str, Any], case: PlannedCase
) -> list[dict[str, Any]]:
    if case.extension not in {"baseline", "temporal_robustness"}:
        return []
    if (
        case.extension == "temporal_robustness"
        and case.outcome_spec_id == "full_horizon_J0_J719"
    ):
        return []
    specs = [
        spec
        for spec in _case_outcome_specs(case)
        if "incident_start_day" in spec
    ]
    snapshots: list[dict[str, Any]] = []
    warmup = (summary.get("policy") or {}).get("warmup_boundary_audit") or {}
    for spec in specs:
        spec_id = str(spec.get("outcome_spec_id") or "")
        incident_start = _to_int(spec.get("incident_start_day"), -1)
        snapshot_day = incident_start - 1
        if incident_start == 0:
            payload = {
                "snapshot_semantics": "J0_pre_event",
                "snapshot_day": -1,
                "core_state_sha256": str(warmup.get("core_state_sha256") or ""),
                "component_sha256": dict(warmup.get("component_sha256") or {}),
            }
            if not payload["core_state_sha256"]:
                raise ValueError(f"État J0 absent: {case.case_key}/{spec_id}")
        else:
            file_specs = {
                "input_stocks": (
                    "production_input_stocks_daily.csv",
                    ("day", "node_id", "item_id", "stock_end_of_day"),
                ),
                "supplier_stocks": (
                    "production_supplier_stocks_daily.csv",
                    ("day", "node_id", "item_id", "stock_end_of_day"),
                ),
                "demand_backlog": (
                    "production_demand_service_daily.csv",
                    ("day", "node_id", "item_id", "backlog_end_qty"),
                ),
                "finished_goods_and_wip": (
                    "production_output_products_daily.csv",
                    (
                        "day",
                        "node_id",
                        "item_id",
                        "stock_end_of_day",
                        "wip_end_qty",
                        "cum_produced_qty",
                    ),
                ),
                "capacity_and_constraints": (
                    "production_constraint_daily.csv",
                    (
                        "day",
                        "node_id",
                        "output_item_id",
                        "cap_qty",
                        "actual_qty",
                        "campaign_remaining_end_qty",
                        "started_lots_this_week",
                    ),
                ),
            }
            components: dict[str, Any] = {}
            for key, (name, fields) in file_specs.items():
                path = case_dir / "data" / name
                rows = _read_csv(path)
                components[key] = _project_rows(
                    [row for row in rows if _to_int(row.get("day"), -1) == snapshot_day],
                    fields,
                )
            shipments = _read_csv(
                case_dir / "data" / "production_supplier_shipments_daily.csv"
            )
            components["outstanding_supplier_pipeline"] = _project_rows(
                [
                    row
                    for row in shipments
                    if _to_int(row.get("risk_decision_day", row.get("day")), -1)
                    <= snapshot_day
                    and _to_int(row.get("arrival_day"), -1) > snapshot_day
                ],
                (
                    "shipment_id",
                    "risk_decision_day",
                    "src_node_id",
                    "dst_node_id",
                    "item_id",
                    "edge_id",
                    "shipped_qty",
                    "arrival_day",
                    "uom",
                ),
            )
            orders = _read_csv(case_dir / "data" / "mrp_orders_daily.csv")
            components["outstanding_planned_orders"] = _project_rows(
                [
                    row
                    for row in orders
                    if _to_int(row.get("day"), -1) <= snapshot_day
                    and _to_int(
                        row.get("actual_receipt_day", row.get("arrival_day")), -1
                    )
                    > snapshot_day
                ],
                (
                    "day",
                    "node_id",
                    "item_id",
                    "order_type",
                    "src_node_id",
                    "dst_node_id",
                    "edge_id",
                    "release_qty",
                    "planned_receipt_qty",
                    "release_day",
                    "arrival_day",
                    "actual_receipt_day",
                    "uom",
                ),
            )
            payload = {
                "snapshot_semantics": "end_of_day_start_minus_1_before_risk_application",
                "snapshot_day": snapshot_day,
                "components": components,
                "complete_engine_checkpoint_available": False,
            }
        snapshots.append(
            {
                "outcome_spec_id": spec_id,
                "incident_start_day": incident_start,
                "snapshot_day": snapshot_day,
                "payload": payload,
                "preincident_state_sha256": planner._canonical_signature(payload),
            }
        )
    return snapshots


def _extended_horizon_support(
    *, summary: Mapping[str, Any], case: PlannedCase, local_rows: Sequence[Mapping[str, Any]]
) -> tuple[bool, str]:
    """Prove that a run beyond J719 uses an explicit cyclic demand policy."""

    if _to_int(summary.get("sim_days"), -1) != case.simulation_days:
        return False, "simulation_days_mismatch"
    if case.simulation_days <= planner.BASE_SIMULATION_DAYS:
        return True, "not_applicable_fixed_J0_J719"
    policy = summary.get("policy") or {}
    cycle_days = _to_int(policy.get("demand_profile_cycle_days"), 0)
    expected_policy = planner.EXTENDED_HORIZON_INPUT_POLICY
    if cycle_days != 365:
        return False, "missing_explicit_demand_profile_cycle"
    spec_ids = {str(spec.get("outcome_spec_id") or "") for spec in _case_outcome_specs(case)}
    indexed = {
        (str(row.get("outcome_spec_id") or ""), str(row.get("product_id") or "")): row
        for row in local_rows
    }
    products = PRODUCTS if case.extension == "baseline" else case.products
    if set(indexed) != {
        (spec_id, product) for spec_id in spec_ids for product in products
    }:
        return False, "local_outcome_matrix_incomplete"
    if any(_to_float(row.get("demand_qty_denominator"), 0.0) <= 0.0 for row in indexed.values()):
        return False, "non_positive_local_demand"
    return True, expected_policy


def _extract_flow_metrics(
    *,
    shipment_rows: Sequence[Mapping[str, Any]],
    graph: Mapping[str, Any],
    case: PlannedCase,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for lane in case.lanes:
        relevant = [
            row
            for row in shipment_rows
            if case.start_day <= _to_int(row.get("day"), -1) <= case.end_day
            and str(row.get("src_node_id") or "") == lane.supplier_id
            and str(row.get("item_id") or "") == lane.item_id
            and str(row.get("dst_node_id") or "") == lane.dst_node_id
        ]
        uoms = {str(row.get("uom") or "") for row in relevant if row.get("uom")}
        if not uoms:
            uoms = {
                _graph_uom(graph, node_id=lane.supplier_id, item_id=lane.item_id)
            }
        if len(uoms) != 1:
            raise ValueError(f"Unités mélangées sur {lane.key}: {uoms}")
        result.append(
            {
                "chain_id": lane.chain_id,
                "supplier_id": lane.supplier_id,
                "item_id": lane.item_id,
                "dst_node_id": lane.dst_node_id,
                "uom": next(iter(uoms)),
                "pulled_qty": sum(
                    max(0.0, _to_float(row.get("pulled_qty"))) for row in relevant
                ),
                "shipped_qty": sum(
                    max(0.0, _to_float(row.get("shipped_qty"))) for row in relevant
                ),
            }
        )
    return result


def execute_engine_case(
    case: PlannedCase,
    context: RunnerContext,
    risk_csv: Path | None,
) -> CaseEvidence:
    case_dir = context.output_dir / "cases" / case.extension / case.case_id / f"seed_{case.seed}"
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    service_path = case_dir / "data" / "production_demand_service_daily.csv"
    status = "reextracted" if summary_path.is_file() and service_path.is_file() else "executed"
    if status == "executed":
        case_dir.mkdir(parents=True, exist_ok=True)
        case_run_config = replace(context.run_config, days=case.simulation_days)
        command = network.build_network_engine_command(
            case_run_config,
            case_dir=case_dir,
            seed=case.seed,
            risk_csv=risk_csv,
            lot_trace_required=case.lot_trace_required,
        )
        log_path = case_dir / "extension_engine.log"
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"\n[{_utc_now()}] COMMAND {json.dumps(command)}\n")
            completed = subprocess.run(
                command,
                cwd=context.run_config.repo_root,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(f"Échec moteur {case.case_key}; voir {log_path}")
    summary = _read_json(summary_path)
    policy = summary.get("policy") or {}
    warmup = policy.get("warmup_boundary_audit") or {}
    graph = _read_json(context.graph_path)
    product_metrics = _extract_product_metrics(
        case_dir=case_dir, graph=graph, days=case.simulation_days
    )
    local_product_metrics = _extract_local_product_metrics(
        case_dir=case_dir, graph=graph, case=case
    )
    if case.extension != "baseline":
        local_product_metrics = [
            row
            for row in local_product_metrics
            if str(row.get("product_id") or "") in case.products
        ]
    preincident_state_snapshots = _extract_preincident_state_snapshots(
        case_dir=case_dir,
        summary=summary,
        case=case,
    )
    configured_event_ids, loaded_event_rows, risk_input_sha256, risk_warnings = (
        _loaded_risk_contract(summary=summary, risk_csv=risk_csv)
    )
    extended_support, extrapolation_policy = _extended_horizon_support(
        summary=summary,
        case=case,
        local_rows=local_product_metrics,
    )
    shipment_rows = _read_csv(
        case_dir / "data" / "production_supplier_shipments_daily.csv"
    )
    flow_metrics = _extract_flow_metrics(
        shipment_rows=shipment_rows, graph=graph, case=case
    ) if case.lanes else []
    applied_rows = _read_csv(case_dir / "data" / "supplier_risk_events_applied_daily.csv")
    compact_application_rows = _project_rows(
        applied_rows,
        (
            "day",
            "supplier_id",
            "dst_node_id",
            "item_id",
            "edge_id",
            "event_ids",
            "lead_time_extra_days",
            "quality_delay_days",
            "quality_yield_multiplier",
            "availability_multiplier",
        ),
    )
    retain_lot_rows = case.lot_trace_required and case.extension in {
        "baseline",
        "causal_lot_attribution_subset",
    }
    lot_events = (
        _read_csv(case_dir / "data" / "production_lot_events.csv")
        if retain_lot_rows
        else []
    )
    genealogy = (
        _read_csv(case_dir / "data" / "production_lot_genealogy.csv")
        if retain_lot_rows
        else []
    )
    resolved_trace = network._resolved_lot_trace_enabled(case_dir)
    if resolved_trace is None:
        raise ValueError(f"Le moteur n'a pas publié son réglage de traçage: {case.case_key}")
    evidence = CaseEvidence(
        case_key=case.case_key,
        seed=case.seed,
        status=status,
        input_sha256=str(summary.get("input_sha256") or ""),
        j0_state_sha256=str(warmup.get("core_state_sha256") or ""),
        resolved_lot_trace_enabled=bool(resolved_trace),
        valid=True,
        validation_errors=[],
        product_metrics=product_metrics,
        flow_metrics=flow_metrics,
        applied_event_ids=_risk_event_tokens(applied_rows),
        lot_events=lot_events,
        lot_genealogy=genealogy,
        run_dir=str(case_dir.resolve()),
        simulation_days=case.simulation_days,
        outcome_bundle_sha256=case.outcome_bundle_sha256,
        local_product_metrics=local_product_metrics,
        preincident_state_snapshots=preincident_state_snapshots,
        configured_event_ids=configured_event_ids,
        loaded_event_rows=loaded_event_rows,
        risk_input_sha256=risk_input_sha256,
        risk_load_warnings=risk_warnings,
        risk_application_rows=compact_application_rows,
        extended_horizon_input_support_pass=extended_support,
        post_J719_extrapolation_policy=extrapolation_policy,
    )
    if context.retention == "summary" and case.extension != "baseline":
        network.campaign_core.prune_case_artifacts(case_dir)
    return evidence


def _evidence_from_dict(payload: Mapping[str, Any]) -> CaseEvidence:
    return CaseEvidence(
        case_key=str(payload.get("case_key") or ""),
        seed=_to_int(payload.get("seed"), -1),
        status=str(payload.get("status") or ""),
        input_sha256=str(payload.get("input_sha256") or ""),
        j0_state_sha256=str(payload.get("j0_state_sha256") or ""),
        resolved_lot_trace_enabled=_as_bool(
            payload.get("resolved_lot_trace_enabled")
        ),
        valid=_as_bool(payload.get("valid")),
        validation_errors=list(payload.get("validation_errors") or []),
        product_metrics=[dict(row) for row in payload.get("product_metrics") or []],
        flow_metrics=[dict(row) for row in payload.get("flow_metrics") or []],
        applied_event_ids=list(payload.get("applied_event_ids") or []),
        lot_events=[dict(row) for row in payload.get("lot_events") or []],
        lot_genealogy=[dict(row) for row in payload.get("lot_genealogy") or []],
        run_dir=str(payload.get("run_dir") or ""),
        reused_source_case=_as_bool(payload.get("reused_source_case")),
        simulation_days=_to_int(
            payload.get("simulation_days"), planner.BASE_SIMULATION_DAYS
        ),
        outcome_bundle_sha256=str(payload.get("outcome_bundle_sha256") or ""),
        local_product_metrics=[
            dict(row) for row in payload.get("local_product_metrics") or []
        ],
        preincident_state_snapshots=[
            dict(row) for row in payload.get("preincident_state_snapshots") or []
        ],
        configured_event_ids=list(payload.get("configured_event_ids") or []),
        loaded_event_rows=[
            dict(row) for row in payload.get("loaded_event_rows") or []
        ],
        risk_input_sha256=str(payload.get("risk_input_sha256") or ""),
        risk_load_warnings=[str(value) for value in payload.get("risk_load_warnings") or []],
        risk_application_rows=[
            dict(row) for row in payload.get("risk_application_rows") or []
        ],
        extended_horizon_input_support_pass=_as_bool(
            payload.get("extended_horizon_input_support_pass", True)
        ),
        post_J719_extrapolation_policy=str(
            payload.get("post_J719_extrapolation_policy") or ""
        ),
    )


def _validate_baseline_evidence(case: PlannedCase, evidence: CaseEvidence) -> None:
    errors = list(evidence.validation_errors)
    if not evidence.valid:
        errors.append("référence marquée invalide")
    if not evidence.input_sha256 or not evidence.j0_state_sha256:
        errors.append("empreinte entrée ou état J0 absente")
    if evidence.resolved_lot_trace_enabled != case.lot_trace_required:
        errors.append("réglage de traçage lots différent du bloc planifié")
    if evidence.simulation_days != case.simulation_days:
        errors.append("horizon simulé différent du plan")
    if evidence.outcome_bundle_sha256 != case.outcome_bundle_sha256:
        errors.append("bundle de mesure différent du plan")
    if not evidence.extended_horizon_input_support_pass:
        errors.append("support des entrées sur l'horizon prolongé non prouvé")
    expected_horizon_policy = (
        planner.EXTENDED_HORIZON_INPUT_POLICY
        if case.simulation_days > planner.BASE_SIMULATION_DAYS
        else "not_applicable_fixed_J0_J719"
    )
    if evidence.post_J719_extrapolation_policy != expected_horizon_policy:
        errors.append("politique d'entrée de l'horizon prolongé incohérente")
    if evidence.configured_event_ids or evidence.loaded_event_rows:
        errors.append("la référence neutre contient des événements risque")
    if evidence.applied_event_ids or evidence.risk_application_rows:
        errors.append("la référence neutre applique un événement risque")
    if evidence.risk_load_warnings:
        errors.append("avertissement au chargement des risques de la référence")
    products = {str(row.get("product_id") or ""): row for row in evidence.product_metrics}
    for product in PRODUCTS:
        row = products.get(product)
        if row is None:
            errors.append(f"métrique référence absente pour {product}")
            continue
        if str(row.get("uom") or "") != "UN":
            errors.append(f"unité produit inattendue pour {product}")
        on_due = _to_float(row.get("on_due_ratio"), math.nan)
        if not math.isfinite(on_due):
            errors.append(f"service référence non mesuré pour {product}")
        elif on_due < 0.95 - 1e-12:
            errors.append(f"service référence inférieur à 95 % pour {product}")
    errors.extend(_local_metric_contract_errors(case, evidence))
    errors.extend(_preincident_snapshot_contract_errors(case, evidence))
    if errors:
        raise ValueError(f"Référence invalide {case.case_key}: " + " | ".join(errors))


def _local_metric_contract_errors(
    case: PlannedCase, evidence: CaseEvidence
) -> list[str]:
    errors: list[str] = []
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in evidence.local_product_metrics:
        key = (
            str(row.get("outcome_spec_id") or ""),
            str(row.get("product_id") or ""),
        )
        if key in indexed:
            errors.append(f"métrique locale dupliquée {key}")
        indexed[key] = row
    products = PRODUCTS if case.extension == "baseline" else case.products
    expected = {
        (str(spec.get("outcome_spec_id") or ""), product)
        for spec in _case_outcome_specs(case)
        for product in products
    }
    if set(indexed) != expected:
        errors.append("matrice de métriques locales incomplète")
        return errors
    specs = {
        str(spec.get("outcome_spec_id") or ""): spec
        for spec in _case_outcome_specs(case)
    }
    for (spec_id, product), row in indexed.items():
        spec = specs[spec_id]
        demand = _to_float(row.get("demand_qty_denominator"), math.nan)
        required = _to_float(row.get("required_qty_denominator"), math.nan)
        served_total = _to_float(row.get("served_qty_numerator"), math.nan)
        fill_rate = _to_float(row.get("fill_rate"), math.nan)
        served = _to_float(row.get("served_on_due_qty_numerator"), math.nan)
        ratio = _to_float(row.get("on_due_ratio"), math.nan)
        backlog = _to_float(row.get("backlog_qty_days_numerator"), math.nan)
        normalized = _to_float(
            row.get("normalized_backlog_days_per_demand_unit"), math.nan
        )
        if str(row.get("uom") or "") != "UN":
            errors.append(f"unité locale inattendue {spec_id}/{product}")
        if not math.isfinite(demand) or demand <= 0.0:
            errors.append(f"demande locale non positive {spec_id}/{product}")
            continue
        if not math.isfinite(required) or required <= 0.0 or not math.isclose(
            served_total / required, fill_rate, rel_tol=0.0, abs_tol=1e-10
        ):
            errors.append(f"taux de satisfaction local incohérent {spec_id}/{product}")
        if not math.isclose(served / demand, ratio, rel_tol=0.0, abs_tol=1e-10):
            errors.append(f"ratio de service local incohérent {spec_id}/{product}")
        if not math.isclose(backlog / demand, normalized, rel_tol=0.0, abs_tol=1e-10):
            errors.append(f"backlog local normalisé incohérent {spec_id}/{product}")
        if _to_int(row.get("outcome_start_day"), -1) != _to_int(
            spec.get("outcome_start_day"), -2
        ) or _to_int(row.get("outcome_end_day"), -1) != _to_int(
            spec.get("outcome_end_day"), -2
        ):
            errors.append(f"fenêtre locale incohérente {spec_id}/{product}")
        if _to_int(row.get("series_day_count"), -1) != _to_int(
            spec.get("outcome_day_count"), -2
        ) or not _as_bool(row.get("series_complete")):
            errors.append(f"série locale incomplète {spec_id}/{product}")
        if str(row.get("recovery_metric_status") or "") != "excluded_not_redefined":
            errors.append(f"recovery locale non autorisée {spec_id}/{product}")
    return errors


def _preincident_snapshot_contract_errors(
    case: PlannedCase, evidence: CaseEvidence
) -> list[str]:
    if case.extension not in {"baseline", "temporal_robustness"}:
        return [] if not evidence.preincident_state_snapshots else [
            "snapshot pré-incident inattendu hors extension temporelle"
        ]
    if (
        case.extension == "temporal_robustness"
        and case.outcome_spec_id == "full_horizon_J0_J719"
    ):
        return [] if not evidence.preincident_state_snapshots else [
            "snapshot pré-incident legacy inattendu"
        ]
    expected_specs = {
        str(spec.get("outcome_spec_id") or ""): _to_int(
            spec.get("incident_start_day"), -1
        )
        for spec in _case_outcome_specs(case)
        if "incident_start_day" in spec
    }
    indexed: dict[str, Mapping[str, Any]] = {}
    errors: list[str] = []
    for row in evidence.preincident_state_snapshots:
        key = str(row.get("outcome_spec_id") or "")
        if key in indexed:
            errors.append(f"snapshot pré-incident dupliqué {key}")
        indexed[key] = row
    if set(indexed) != set(expected_specs):
        if expected_specs or indexed:
            errors.append("matrice de snapshots pré-incident incomplète")
        return errors
    for spec_id, incident_start in expected_specs.items():
        row = indexed[spec_id]
        expected_day = incident_start - 1
        if _to_int(row.get("snapshot_day"), -99) != expected_day:
            errors.append(f"jour snapshot incohérent {spec_id}")
        payload = row.get("payload") or {}
        digest = str(row.get("preincident_state_sha256") or "")
        if not digest or planner._canonical_signature(payload) != digest:
            errors.append(f"empreinte snapshot incohérente {spec_id}")
    return errors


def _validate_stress_evidence(
    case: PlannedCase,
    evidence: CaseEvidence,
    baseline: CaseEvidence,
    graph: Mapping[str, Any],
) -> None:
    errors = list(evidence.validation_errors)
    if not evidence.valid:
        errors.append("cas marqué invalide")
    if evidence.input_sha256 != baseline.input_sha256:
        errors.append("empreinte entrée différente de la référence")
    if evidence.j0_state_sha256 != baseline.j0_state_sha256:
        errors.append("état J0 différent de la référence")
    if evidence.resolved_lot_trace_enabled != case.lot_trace_required:
        errors.append("traçage lots résolu différent du plan")
    if evidence.simulation_days != case.simulation_days:
        errors.append("horizon simulé différent du plan")
    if evidence.outcome_bundle_sha256 != case.outcome_bundle_sha256:
        errors.append("bundle de mesure différent du plan")
    if not evidence.extended_horizon_input_support_pass:
        errors.append("support des entrées sur l'horizon prolongé non prouvé")
    expected_horizon_policy = (
        planner.EXTENDED_HORIZON_INPUT_POLICY
        if case.simulation_days > planner.BASE_SIMULATION_DAYS
        else "not_applicable_fixed_J0_J719"
    )
    if evidence.post_J719_extrapolation_policy != expected_horizon_policy:
        errors.append("politique d'entrée de l'horizon prolongé incohérente")
    expected_rows = _canonical_rows([_normalized_risk_row(row) for row in _risk_rows(case)])
    loaded_rows = _canonical_rows(evidence.loaded_event_rows)
    if evidence.reused_source_case:
        loaded_rows, edge_resolution_errors = _resolve_reused_source_risk_edges(
            loaded_rows, graph
        )
        errors.extend(edge_resolution_errors)
        loaded_rows = _canonical_rows(loaded_rows)
        comparable_fields = tuple(
            key for key in expected_rows[0] if key not in {"event_id", "notes"}
        )
        expected_loaded = _canonical_rows(
            [{key: row.get(key) for key in comparable_fields} for row in expected_rows]
        )
        actual_loaded = _canonical_rows(
            [{key: row.get(key) for key in comparable_fields} for row in loaded_rows]
        )
        expected_events = {
            str(row.get("event_id") or "") for row in loaded_rows
        } - {""}
    else:
        expected_loaded = expected_rows
        actual_loaded = loaded_rows
        expected_events = {str(row["event_id"]) for row in expected_rows}
    if actual_loaded != expected_loaded:
        errors.append("configuration risque chargée différente du plan")
    if set(evidence.configured_event_ids) != expected_events:
        errors.append("inventaire des événements risque configuré incohérent")
    if not evidence.risk_input_sha256:
        errors.append("empreinte de l'entrée risque absente")
    if evidence.risk_load_warnings:
        errors.append("avertissement au chargement des risques")
    applied_events = set(evidence.applied_event_ids)
    if applied_events - expected_events:
        errors.append("événement risque appliqué hors plan")
    try:
        application_tokens = set(_risk_event_tokens(evidence.risk_application_rows))
    except ValueError as error:
        errors.append(str(error))
        application_tokens = set()
    if application_tokens != applied_events:
        errors.append("lignes d'application et identifiants appliqués incohérents")
    product_units = {
        str(row.get("uom") or "") for row in evidence.product_metrics
    }
    if "" in product_units or product_units - {"UN"}:
        errors.append(f"unité produit invalide: {product_units}")
    expected_lane_uom = {
        lane.key: _graph_uom(
            graph,
            node_id=lane.supplier_id,
            item_id=lane.item_id,
        )
        for lane in case.lanes
    }
    for row in evidence.flow_metrics:
        unit = str(row.get("uom") or "")
        if not unit:
            errors.append("unité de flux absente")
        lane_key = (
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        )
        if lane_key not in expected_lane_uom:
            errors.append("voie de flux hors périmètre du cas")
        elif unit != expected_lane_uom[lane_key]:
            errors.append(
                f"unité de flux {unit!r} différente du graphe "
                f"{expected_lane_uom[lane_key]!r} pour {lane_key}"
            )
    try:
        baseline_flow = _baseline_flow_for_case(
            case=case, baseline=baseline, graph=graph
        )
    except (KeyError, ValueError, FileNotFoundError) as error:
        errors.append(f"flux baseline indisponible: {error}")
        baseline_flow = []
    positive_flow_lane_ids = {
        str(row.get("chain_id") or "")
        for row in baseline_flow
        if _to_float(row.get("pulled_qty"), 0.0) > 0.0
        and _to_float(row.get("shipped_qty"), 0.0) > 0.0
    }
    loaded_event_by_lane = {
        (
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        ): str(row.get("event_id") or "")
        for row in loaded_rows
    }
    expected_by_chain = {
        lane.chain_id: loaded_event_by_lane.get(lane.key, "")
        for lane in case.lanes
    }
    missing_exercised = {
        event_id
        for chain_id, event_id in expected_by_chain.items()
        if chain_id in positive_flow_lane_ids and event_id not in applied_events
    }
    if missing_exercised:
        errors.append(
            "flux baseline positif sans événement appliqué attendu: "
            + ",".join(sorted(missing_exercised))
        )
    errors.extend(_local_metric_contract_errors(case, evidence))
    errors.extend(_preincident_snapshot_contract_errors(case, evidence))
    baseline_local = {
        (str(row.get("outcome_spec_id") or ""), str(row.get("product_id") or "")): row
        for row in baseline.local_product_metrics
    }
    for row in evidence.local_product_metrics:
        key = (
            str(row.get("outcome_spec_id") or ""),
            str(row.get("product_id") or ""),
        )
        paired = baseline_local.get(key)
        if paired is None:
            errors.append(f"métrique baseline locale absente {key}")
            continue
        if str(row.get("uom") or "") != str(paired.get("uom") or ""):
            errors.append(f"unité locale non appariée {key}")
        if not math.isclose(
            _to_float(row.get("demand_qty_denominator"), math.nan),
            _to_float(paired.get("demand_qty_denominator"), math.nan),
            rel_tol=0.0,
            abs_tol=1e-8,
        ):
            errors.append(f"demande locale non appariée {key}")
    baseline_snapshots = {
        str(row.get("outcome_spec_id") or ""): row
        for row in baseline.preincident_state_snapshots
    }
    for row in evidence.preincident_state_snapshots:
        spec_id = str(row.get("outcome_spec_id") or "")
        paired = baseline_snapshots.get(spec_id)
        if paired is None or str(row.get("preincident_state_sha256") or "") != str(
            paired.get("preincident_state_sha256") or ""
        ):
            errors.append(f"état pré-incident non apparié {spec_id}")
    if errors:
        raise ValueError(f"Cas invalide {case.case_key}: " + " | ".join(errors))


def _required_baseline_flow_specs(
    cases: Sequence[PlannedCase],
) -> dict[tuple[str, str, str, str, int, int], LaneSpec]:
    specs: dict[tuple[str, str, str, str, int, int], LaneSpec] = {}
    for case in cases:
        for lane in case.lanes:
            key = (
                lane.chain_id,
                lane.supplier_id,
                lane.item_id,
                lane.dst_node_id,
                case.start_day,
                case.end_day,
            )
            specs[key] = lane
    return specs


def _validate_compact_baseline_flows(
    *,
    evidence: CaseEvidence,
    cases: Sequence[PlannedCase],
    graph: Mapping[str, Any],
) -> None:
    expected = _required_baseline_flow_specs(cases)
    indexed: dict[tuple[str, str, str, str, int, int], Mapping[str, Any]] = {}
    for row in evidence.flow_metrics:
        key = (
            str(row.get("chain_id") or ""),
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
            _to_int(row.get("baseline_window_start_day"), -1),
            _to_int(row.get("baseline_window_end_day"), -1),
        )
        if key in indexed:
            raise ValueError(f"Flux baseline compact dupliqué: {key}")
        indexed[key] = row
    if set(indexed) != set(expected):
        missing = sorted(set(expected) - set(indexed))
        extra = sorted(set(indexed) - set(expected))
        raise ValueError(
            "Contrat compact de flux baseline incomplet: "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    for key, lane in expected.items():
        row = indexed[key]
        expected_uom = _graph_uom(
            graph,
            node_id=lane.supplier_id,
            item_id=lane.item_id,
        )
        if str(row.get("uom") or "") != expected_uom:
            raise ValueError(f"Unité baseline compacte incohérente pour {key}")
        for field in ("pulled_qty", "shipped_qty"):
            value = _to_float(row.get(field), math.nan)
            if not math.isfinite(value) or value < -1e-12:
                raise ValueError(f"Flux baseline compact invalide: {key}/{field}")


def _materialize_compact_baseline_flows(
    *,
    evidence: CaseEvidence,
    cases: Sequence[PlannedCase],
    graph: Mapping[str, Any],
) -> None:
    """Persist exact lane/window aggregates before summary retention prunes data."""

    if evidence.flow_metrics:
        _validate_compact_baseline_flows(
            evidence=evidence,
            cases=cases,
            graph=graph,
        )
        return
    if not evidence.run_dir:
        raise ValueError(
            "La baseline matérialisée ne fournit ni dossier de calcul ni flux compacts."
        )
    shipment_path = (
        Path(evidence.run_dir) / "data" / "production_supplier_shipments_daily.csv"
    )
    if not shipment_path.is_file():
        raise FileNotFoundError(
            "Flux quotidien absent avant matérialisation compacte de la baseline: "
            f"{shipment_path}"
        )
    shipments_by_lane: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in _read_csv(shipment_path):
        key = (
            str(row.get("src_node_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        )
        shipments_by_lane[key].append(row)
    compact: list[dict[str, Any]] = []
    for key, lane in sorted(_required_baseline_flow_specs(cases).items()):
        start_day, end_day = key[-2:]
        relevant = [
            row
            for row in shipments_by_lane.get(lane.key, [])
            if start_day <= _to_int(row.get("day"), -1) <= end_day
        ]
        observed_uoms = {
            str(row.get("uom") or "") for row in relevant if str(row.get("uom") or "")
        }
        expected_uom = _graph_uom(
            graph,
            node_id=lane.supplier_id,
            item_id=lane.item_id,
        )
        if observed_uoms and observed_uoms != {expected_uom}:
            raise ValueError(
                f"Unités quotidiennes baseline incohérentes pour {lane.key}: "
                f"{observed_uoms}"
            )
        compact.append(
            {
                "chain_id": lane.chain_id,
                "supplier_id": lane.supplier_id,
                "item_id": lane.item_id,
                "dst_node_id": lane.dst_node_id,
                "uom": expected_uom,
                "baseline_window_start_day": start_day,
                "baseline_window_end_day": end_day,
                "pulled_qty": sum(
                    max(0.0, _to_float(row.get("pulled_qty"))) for row in relevant
                ),
                "shipped_qty": sum(
                    max(0.0, _to_float(row.get("shipped_qty"))) for row in relevant
                ),
                "aggregation_source": "runner_generated_daily_baseline_exact_window",
                "cross_uom_aggregation_allowed": False,
            }
        )
    evidence.flow_metrics = compact
    _validate_compact_baseline_flows(
        evidence=evidence,
        cases=cases,
        graph=graph,
    )


def _baseline_flow_for_case(
    *,
    case: PlannedCase,
    baseline: CaseEvidence,
    graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    compact = [
        row
        for row in baseline.flow_metrics
        if _to_int(row.get("baseline_window_start_day"), -1) == case.start_day
        and _to_int(row.get("baseline_window_end_day"), -1) == case.end_day
        and (
            str(row.get("chain_id") or ""),
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        )
        in {(lane.chain_id, *lane.key) for lane in case.lanes}
    ]
    if len(compact) == len(case.lanes):
        return [dict(row) for row in compact]
    if baseline.run_dir:
        path = Path(baseline.run_dir) / "data" / "production_supplier_shipments_daily.csv"
        if path.is_file():
            return _extract_flow_metrics(
                shipment_rows=_read_csv(path), graph=graph, case=case
            )
    raise RuntimeError(
        "Flux baseline exact indisponible pour la fenêtre du cas "
        f"{case.case_key}; reprise refusée en mode fail-closed."
    )


def _product_rows(
    *,
    case: PlannedCase,
    evidence: CaseEvidence,
    baseline: CaseEvidence,
) -> list[dict[str, Any]]:
    baseline_by_key = {
        (
            str(row.get("outcome_spec_id") or ""),
            str(row.get("product_id") or ""),
        ): row
        for row in baseline.local_product_metrics
    }
    rows: list[dict[str, Any]] = []
    for stress in evidence.local_product_metrics:
        product = str(stress.get("product_id") or "")
        spec_id = str(stress.get("outcome_spec_id") or "")
        if product not in case.products or spec_id != case.outcome_spec_id:
            continue
        reference = baseline_by_key.get((spec_id, product))
        if reference is None:
            raise ValueError(
                f"Produit/outcome {product}/{spec_id} absent de la référence "
                f"{baseline.case_key}"
            )
        if str(reference.get("uom") or "") != str(stress.get("uom") or ""):
            raise ValueError(f"Unités produit non appariées pour {case.case_key}/{product}")
        row: dict[str, Any] = {
            "extension": case.extension,
            "case_key": case.case_key,
            "case_id": case.case_id,
            "seed": case.seed,
            "pairing_block_id": case.pairing_block_id,
            "case_origin": (
                "reused_exact_source_case"
                if evidence.reused_source_case
                else "new_run"
            ),
            "failure_mode": case.mechanism_key,
            "mechanism_value": case.mechanism_value,
            "mechanism_unit": case.mechanism_unit,
            "stress_start_day": case.start_day,
            "stress_end_day": case.end_day,
            "simulation_days": case.simulation_days,
            "outcome_spec_id": spec_id,
            "outcome_start_day": stress.get("outcome_start_day"),
            "outcome_end_day": stress.get("outcome_end_day"),
            "outcome_day_count": stress.get("outcome_day_count"),
            "outcome_bundle_sha256": case.outcome_bundle_sha256,
            "product_id": product,
            "product_uom": stress.get("uom"),
            "service_unit": "ratio_and_percentage_points",
            "backlog_unit": f"{stress.get('uom')}_day",
            "production_unit": stress.get("uom"),
            "pairing_valid": True,
        }
        field_map = {
            "fill_rate": "fill_rate",
            "on_due_ratio": "on_due_ratio",
            "backlog_qty_days": "backlog_qty_days_numerator",
            "backlog_end_qty": "backlog_end_qty",
            "released_qty": "released_qty_numerator",
        }
        for output_field, evidence_field in field_map.items():
            base_value = _to_float(reference.get(evidence_field), math.nan)
            stress_value = _to_float(stress.get(evidence_field), math.nan)
            row[f"baseline_{output_field}"] = base_value
            row[f"stress_{output_field}"] = stress_value
            row[f"delta_{output_field}"] = stress_value - base_value
        for component in (
            "demand_qty_denominator",
            "required_qty_denominator",
            "served_qty_numerator",
            "served_on_due_qty_numerator",
            "backlog_qty_days_numerator",
            "released_qty_numerator",
        ):
            row[f"baseline_{component}"] = reference.get(component)
            row[f"stress_{component}"] = stress.get(component)
        demand = _to_float(reference.get("demand_qty_denominator"), math.nan)
        if not math.isclose(
            demand,
            _to_float(stress.get("demand_qty_denominator"), math.nan),
            rel_tol=0.0,
            abs_tol=1e-8,
        ):
            raise ValueError(f"Demande non appariée pour {case.case_key}/{product}")
        row["delta_backlog_days_per_demand_unit"] = (
            row["delta_backlog_qty_days"] / demand
        )
        baseline_released = row["baseline_released_qty"]
        row["signed_production_shortfall_ratio"] = (
            -row["delta_released_qty"] / baseline_released
            if baseline_released > 0.0
            else ""
        )
        row["delta_on_due_percentage_points"] = (
            100.0 * row["delta_on_due_ratio"]
        )
        rows.append(row)
    return rows


def _flow_rows(
    *,
    case: PlannedCase,
    evidence: CaseEvidence,
    baseline_flow: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    baseline_by_lane = {
        (
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        ): row
        for row in baseline_flow
    }
    stress_by_lane = {
        (
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        ): row
        for row in evidence.flow_metrics
    }
    configured_event_ids_by_lane: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for event in evidence.loaded_event_rows:
        lane_key = (
            str(event.get("supplier_id") or ""),
            str(event.get("item_id") or ""),
            str(event.get("dst_node_id") or ""),
        )
        event_id = str(event.get("event_id") or "")
        if all(lane_key) and event_id:
            configured_event_ids_by_lane[lane_key].add(event_id)
    applied_event_ids = set(evidence.applied_event_ids)
    rows: list[dict[str, Any]] = []
    for lane in case.lanes:
        stress = stress_by_lane.get(lane.key)
        if stress is None:
            raise ValueError(f"Flux stress absent pour {case.case_key}/{lane.key}")
        reference = baseline_by_lane.get(lane.key)
        unit = str(stress.get("uom") or "")
        if reference is not None and str(reference.get("uom") or "") != unit:
            raise ValueError(f"Unité flux non appariée pour {case.case_key}/{lane.key}")
        baseline_pulled = (
            _to_float(reference.get("pulled_qty"), math.nan)
            if reference is not None
            else math.nan
        )
        baseline_shipped = (
            _to_float(reference.get("shipped_qty"), math.nan)
            if reference is not None
            else math.nan
        )
        stress_pulled = _to_float(stress.get("pulled_qty"), math.nan)
        stress_shipped = _to_float(stress.get("shipped_qty"), math.nan)
        rows.append(
            {
                "extension": case.extension,
                "case_key": case.case_key,
                "case_id": case.case_id,
                "seed": case.seed,
                "failure_mode": case.mechanism_key,
                "stress_start_day": case.start_day,
                "stress_end_day": case.end_day,
                "simulation_days": case.simulation_days,
                "outcome_spec_id": case.outcome_spec_id,
                "outcome_bundle_sha256": case.outcome_bundle_sha256,
                "chain_id": lane.chain_id,
                "supplier_id": lane.supplier_id,
                "item_id": lane.item_id,
                "dst_node_id": lane.dst_node_id,
                "uom": unit,
                "baseline_flow_evidence_available": reference is not None,
                "baseline_pulled_qty": baseline_pulled,
                "baseline_shipped_qty": baseline_shipped,
                "stress_pulled_qty": stress_pulled,
                "stress_shipped_qty": stress_shipped,
                "baseline_flow_exercised": bool(
                    reference is not None
                    and baseline_pulled > 1e-12
                    and baseline_shipped > 1e-12
                ),
                "risk_configuration_loaded": bool(evidence.configured_event_ids),
                "risk_event_applied_on_lane": bool(
                    configured_event_ids_by_lane.get(lane.key, set())
                    & applied_event_ids
                ),
                "shipped_coverage_ratio": (
                    min(1.0, max(0.0, stress_shipped) / baseline_shipped)
                    if reference is not None and baseline_shipped > 1e-12
                    else ""
                ),
                "raw_cross_uom_aggregation_allowed": False,
            }
        )
    return rows


def _load_lot_material(
    evidence: CaseEvidence,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    if evidence.lot_events:
        return evidence.lot_events, evidence.lot_genealogy, "runner_case_raw_exports"
    if not evidence.run_dir:
        return [], [], "missing"
    case_dir = Path(evidence.run_dir)
    raw_events = case_dir / "data" / "production_lot_events.csv"
    raw_genealogy = case_dir / "data" / "production_lot_genealogy.csv"
    if raw_events.is_file() and raw_genealogy.is_file():
        return _read_csv(raw_events), _read_csv(raw_genealogy), "source_raw_exports"
    proof_dir = case_dir / "proofs"
    receipt_path = proof_dir / "impacted_receipt_lots.csv"
    descendant_path = proof_dir / "impacted_descendant_lots.csv"
    if receipt_path.is_file() and descendant_path.is_file():
        receipts = [
            {**row, "_proof_role": "direct_exposed_receipt"}
            for row in _read_csv(receipt_path)
        ]
        descendants = [
            {**row, "_proof_role": "exposed_descendant"}
            for row in _read_csv(descendant_path)
        ]
        links_path = proof_dir / "impacted_genealogy.csv"
        links = _read_csv(links_path) if links_path.is_file() else []
        return receipts + descendants, links, "source_retained_proof_exports"
    return [], [], "missing"


def _tokens(value: Any) -> set[str]:
    return {
        token.strip()
        for token in re.split(r"[,;|]", str(value or ""))
        if token.strip()
    }


def _quantity_by_uom(rows: Sequence[Mapping[str, Any]]) -> str:
    grouped: dict[str, float] = defaultdict(float)
    for row in rows:
        uom = str(row.get("uom") or "").strip()
        quantity = _to_float(row.get("qty"), math.nan)
        if not uom:
            raise ValueError("UnitÃ© absente d'une ligne de lot exposÃ©e.")
        if not math.isfinite(quantity) or quantity < 0.0:
            raise ValueError("QuantitÃ© de lot exposÃ©e invalide.")
        grouped[uom] += quantity
    return json.dumps(dict(sorted(grouped.items())), ensure_ascii=False, sort_keys=True)


def _genealogical_exposure(
    *,
    case: PlannedCase,
    evidence: CaseEvidence,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events, genealogy, evidence_format = _load_lot_material(evidence)
    lane_receipt_keys = {(lane.item_id, lane.dst_node_id) for lane in case.lanes}
    expected = set(evidence.configured_event_ids) or {
        row["event_id"] for row in _risk_rows(case)
    }
    applied = set(evidence.applied_event_ids)
    applied_expected = expected & applied

    def has_only_applied_expected_tags(row: Mapping[str, Any]) -> bool:
        tags = _tokens(row.get("risk_event_ids"))
        return bool(tags) and tags <= applied_expected

    proof_roots = [
        row
        for row in events
        if str(row.get("_proof_role") or "") == "direct_exposed_receipt"
        and str(row.get("lot_id") or "").strip()
        and (
            str(row.get("item_id") or ""),
            str(row.get("node_id") or ""),
        )
        in lane_receipt_keys
        and has_only_applied_expected_tags(row)
    ]
    raw_roots = [
        row
        for row in events
        if str(row.get("event_type") or row.get("source_type") or "") == "lane_receipt"
        and (
            str(row.get("item_id") or ""),
            str(row.get("node_id") or ""),
        ) in lane_receipt_keys
        and has_only_applied_expected_tags(row)
    ]
    roots = proof_roots or raw_roots
    root_id_values = [str(row.get("lot_id") or "").strip() for row in roots]
    root_ids = set(root_id_values) - {""}
    duplicate_root_ids = len(root_id_values) != len(root_ids)
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    genealogy_edges: list[tuple[str, str]] = []
    invalid_genealogy_link_count = 0
    for link in genealogy:
        parent = str(link.get("parent_lot_id") or "").strip()
        child = str(link.get("child_lot_id") or "").strip()
        if not parent or not child:
            invalid_genealogy_link_count += 1
        else:
            genealogy_edges.append((parent, child))
            children[parent].append(dict(link))
    duplicate_genealogy_edge_count = len(genealogy_edges) - len(
        set(genealogy_edges)
    )
    exposed_ids = set(root_ids)
    queue = deque(root_ids)
    while queue:
        parent = queue.popleft()
        for link in children.get(parent, []):
            child = str(link.get("child_lot_id") or "")
            if child and child not in exposed_ids:
                exposed_ids.add(child)
                queue.append(child)
    exposed_rows = [
        {
            **row,
            "_computed_exposure_role": (
                "risk_tagged_usable_receipt_root"
                if str(row.get("lot_id") or "") in root_ids
                else "genealogical_descendant"
            ),
        }
        for row in events
        if str(row.get("lot_id") or "") in exposed_ids
    ]
    declared_proof_ids = {
        str(row.get("lot_id") or "")
        for row in events
        if str(row.get("_proof_role") or "") in {
            "direct_exposed_receipt",
            "exposed_descendant",
        }
    } - {""}
    unreachable_proof_ids = declared_proof_ids - exposed_ids
    adjacency = {
        parent: {
            str(link.get("child_lot_id") or "")
            for link in links
            if str(link.get("child_lot_id") or "")
        }
        for parent, links in children.items()
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def has_cycle(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(has_cycle(child) for child in adjacency.get(node, set())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    cycle_detected = any(has_cycle(node) for node in sorted(exposed_ids))
    all_event_lot_ids = {
        str(row.get("lot_id") or "") for row in events if str(row.get("lot_id") or "")
    }
    missing_lot_ids = {
        lot_id
        for link in genealogy
        for lot_id in (
            str(link.get("parent_lot_id") or ""),
            str(link.get("child_lot_id") or ""),
        )
        if lot_id and lot_id not in all_event_lot_ids
    }
    root_contract_pass = bool(root_ids) and not duplicate_root_ids
    genealogy_integrity = bool(
        not missing_lot_ids
        and not unreachable_proof_ids
        and not cycle_detected
        and invalid_genealogy_link_count == 0
        and duplicate_genealogy_edge_count == 0
        and declared_proof_ids <= exposed_ids
    )
    summary = {
        "extension": case.extension,
        "case_key": case.case_key,
        "case_id": case.case_id,
        "seed": case.seed,
        "failure_mode": case.mechanism_key,
        "evidence_format": evidence_format,
        "root_lot_count": len(root_ids),
        "exposed_descendant_lot_count": max(0, len(exposed_ids) - len(root_ids)),
        "exposed_row_count": len(exposed_rows),
        "exposed_quantity_upper_bound_by_uom_json": _quantity_by_uom(exposed_rows),
        "descendant_quantity_is_upper_bound": True,
        "causal_delay_or_loss_claimed_from_genealogy": False,
        "root_gate_pass": root_contract_pass,
        "duplicate_root_lot_id_count": len(root_id_values) - len(root_ids),
        "genealogy_integrity_pass": genealogy_integrity,
        "missing_genealogy_lot_count": len(missing_lot_ids),
        "unreachable_declared_proof_lot_count": len(unreachable_proof_ids),
        "genealogy_cycle_detected": cycle_detected,
        "invalid_genealogy_link_count": invalid_genealogy_link_count,
        "duplicate_genealogy_edge_count": duplicate_genealogy_edge_count,
        "published_exposure_is_exact_bfs_closure": genealogy_integrity,
        "expected_risk_event_ids": "|".join(sorted(expected)),
        "applied_expected_risk_event_ids": "|".join(sorted(applied_expected)),
        "root_eligibility_requires_effective_risk_application": True,
        "quality_hold_wait_semantics": (
            "reconstructed_not_native_quarantine_stock"
            if case.mechanism_key == "quality_hold"
            else "not_applicable"
        ),
    }
    return summary, exposed_rows


def _lot_genealogical_exposure_detail_rows(
    *,
    case: PlannedCase,
    exposed_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for row in exposed_rows:
        lot_id = str(row.get("lot_id") or "").strip()
        role = str(row.get("_computed_exposure_role") or "").strip()
        uom = str(row.get("uom") or "").strip()
        qty = _to_float(row.get("qty"), math.nan)
        if (
            not lot_id
            or role
            not in {
                "risk_tagged_usable_receipt_root",
                "genealogical_descendant",
            }
            or not uom
            or not math.isfinite(qty)
            or qty < 0.0
        ):
            raise ValueError(
                f"Ligne de détail d'exposition lot invalide: {case.case_key}"
            )
        details.append(
            {
                "extension": case.extension,
                "case_key": case.case_key,
                "case_id": case.case_id,
                "seed": case.seed,
                "failure_mode": case.mechanism_key,
                "stress_start_day": case.start_day,
                "stress_end_day": case.end_day,
                "chain_ids": "|".join(
                    sorted(lane.chain_id for lane in case.lanes)
                ),
                "supplier_ids": "|".join(
                    sorted({lane.supplier_id for lane in case.lanes})
                ),
                "lot_id": lot_id,
                "exposure_role": role,
                "genealogy_depth": row.get("genealogy_depth", ""),
                "node_id": row.get("node_id", ""),
                "item_id": row.get("item_id", ""),
                "event_id": row.get("event_id", ""),
                "event_type": (
                    row.get("event_type")
                    or row.get("source_type")
                    or row.get("lot_role")
                    or ""
                ),
                "day": row.get("day", ""),
                "qty": qty,
                "uom": uom,
                "risk_event_ids": row.get("risk_event_ids", ""),
                "shipment_id": row.get("shipment_id", ""),
                "production_campaign_id": row.get(
                    "production_campaign_id", ""
                ),
                "source_type": row.get("source_type", ""),
                "source_id": row.get("source_id", ""),
                "descendant_quantity_is_exposure_upper_bound": True,
                "causal_delay_or_loss_claimed": False,
                "counterfactual_entity_identity_validated": False,
                "industrial_lot_number_claimed": False,
                "lot_identifier_semantics": (
                    "identifiant_technique_simule_pas_numero_lot_industriel"
                ),
            }
        )
    return sorted(
        details,
        key=lambda item: (
            str(item["case_key"]),
            0
            if item["exposure_role"] == "risk_tagged_usable_receipt_root"
            else 1,
            _to_int(item.get("day"), -1),
            str(item["lot_id"]),
            str(item["event_id"]),
        ),
    )


def _stable_lot_key(row: Mapping[str, Any]) -> tuple[str, ...] | None:
    key_type = ""
    key_id = ""
    for field, label in (
        ("shipment_id", "shipment"),
        ("production_campaign_id", "production_campaign"),
        ("source_id", "source"),
    ):
        value = str(row.get(field) or "").strip()
        if value:
            key_type, key_id = label, value
            break
    if not key_id:
        return None
    uom = str(row.get("uom") or "").strip()
    if not uom:
        return None
    return (
        key_type,
        key_id,
        str(row.get("node_id") or ""),
        str(row.get("item_id") or ""),
        str(row.get("event_type") or row.get("lot_role") or ""),
        uom,
    )


def _causal_lot_rows(
    *,
    case: PlannedCase,
    baseline: CaseEvidence,
    stress: CaseEvidence,
    exposed_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    baseline_events, _baseline_genealogy, baseline_format = _load_lot_material(baseline)
    baseline_by_key: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    stress_by_key: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in baseline_events:
        key = _stable_lot_key(row)
        if key is not None:
            baseline_by_key[key].append(row)
    for row in exposed_rows:
        key = _stable_lot_key(row)
        if key is not None:
            stress_by_key[key].append(row)
    rows: list[dict[str, Any]] = []
    for key in sorted(set(baseline_by_key) & set(stress_by_key)):
        baseline_matches = baseline_by_key[key]
        stress_matches = stress_by_key[key]
        if len(baseline_matches) != 1 or len(stress_matches) != 1:
            continue
        reference = baseline_matches[0]
        incident = stress_matches[0]
        baseline_day = _to_int(reference.get("day"), -1)
        stress_day = _to_int(incident.get("day"), -1)
        baseline_qty = _to_float(reference.get("qty"), math.nan)
        stress_qty = _to_float(incident.get("qty"), math.nan)
        rows.append(
            {
                "case_key": case.case_key,
                "case_id": case.case_id,
                "seed": case.seed,
                "failure_mode": case.mechanism_key,
                "technical_key_type": key[0],
                "technical_key_id": key[1],
                "node_id": key[2],
                "item_id": key[3],
                "event_type": key[4],
                "uom": key[5],
                "baseline_day": baseline_day,
                "stress_day": stress_day,
                "day_delta": stress_day - baseline_day,
                "baseline_qty": baseline_qty,
                "stress_qty": stress_qty,
                "qty_delta": stress_qty - baseline_qty,
                "actual_difference_measured": bool(
                    stress_day != baseline_day
                    or abs(stress_qty - baseline_qty) > 1e-12
                ),
                "baseline_evidence_format": baseline_format,
                "pairing_input_sha256_pass": (
                    baseline.input_sha256 == stress.input_sha256
                ),
                "pairing_j0_state_sha256_pass": (
                    baseline.j0_state_sha256 == stress.j0_state_sha256
                ),
                "genealogical_exposure_only": False,
                "causal_scope": "technical_event_heuristic_not_causal_lot_identity",
                "counterfactual_entity_identity_validated": False,
                "pairing_method": (
                    "heuristic_global_engine_counter_or_campaign_identifier; may shift "
                    "between counterfactual runs"
                ),
            }
        )
    return rows


def _technical_pairing_coverage(
    *, baseline: CaseEvidence, stress: CaseEvidence, exposed_rows: Sequence[Mapping[str, Any]]
) -> dict[str, int | bool]:
    baseline_events, _genealogy, _format = _load_lot_material(baseline)
    baseline_by_key: dict[tuple[str, ...], int] = defaultdict(int)
    stress_by_key: dict[tuple[str, ...], int] = defaultdict(int)
    for row in baseline_events:
        key = _stable_lot_key(row)
        if key is not None:
            baseline_by_key[key] += 1
    for row in exposed_rows:
        key = _stable_lot_key(row)
        if key is not None:
            stress_by_key[key] += 1
    baseline_unique = {key for key, count in baseline_by_key.items() if count == 1}
    stress_unique = {key for key, count in stress_by_key.items() if count == 1}
    matched = baseline_unique & stress_unique
    ambiguous = {
        key
        for key in set(baseline_by_key) | set(stress_by_key)
        if baseline_by_key.get(key, 0) > 1 or stress_by_key.get(key, 0) > 1
    }
    return {
        "eligible_baseline_technical_key_count": len(baseline_by_key),
        "eligible_stress_technical_key_count": len(stress_by_key),
        "matched_unique_technical_key_count": len(matched),
        "ambiguous_technical_key_count": len(ambiguous),
        "baseline_only_unique_technical_key_count": len(baseline_unique - stress_unique),
        "stress_only_unique_technical_key_count": len(stress_unique - baseline_unique),
        "technical_event_heuristic_pairing_integrity_pass": not ambiguous,
        "heuristic_comparison_display_allowed": bool(matched) and not ambiguous,
        "counterfactual_entity_identity_validated": False,
        "causal_lot_attribution_available": False,
    }


def _causal_lot_gate_summary(
    *,
    mode: str,
    expected_pair_count: int,
    pair_rows: Sequence[Mapping[str, Any]],
) -> dict[str, bool]:
    """Keep execution integrity independent from heuristic match coverage.

    A technically ambiguous key is a valid, reportable outcome of the comparison
    procedure.  It blocks interpretation of that heuristic match, but it must not
    relabel a complete engine execution and an internally valid genealogy as a
    failed execution.
    """

    complete = expected_pair_count > 0 and len(pair_rows) == expected_pair_count
    execution_integrity = bool(
        mode == "full"
        and complete
        and all(
            _as_bool(row.get("root_gate_pass"))
            and _as_bool(row.get("genealogy_integrity_pass"))
            for row in pair_rows
        )
    )
    heuristic_pairing_integrity = bool(pair_rows) and all(
        _as_bool(row.get("technical_event_heuristic_pairing_integrity_pass"))
        for row in pair_rows
    )
    comparison_evaluable = bool(pair_rows) and all(
        _as_bool(row.get("heuristic_comparison_display_allowed"))
        for row in pair_rows
    )
    return {
        "causal_lot_execution_integrity_pass": execution_integrity,
        "technical_event_heuristic_pairing_integrity_pass": (
            heuristic_pairing_integrity
        ),
        "heuristic_comparison_evaluable_pass": comparison_evaluable,
        "heuristic_comparison_display_allowed": comparison_evaluable,
        "causal_comparison_evaluable_pass": False,
    }


def _sample_std(values: Sequence[float]) -> float | str:
    clean = [value for value in values if math.isfinite(value)]
    return statistics.stdev(clean) if len(clean) >= 2 else ""


def _summarize_product_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row.get("extension") or ""),
                str(row.get("case_id") or ""),
                str(row.get("product_id") or ""),
            )
        ].append(row)
    result: list[dict[str, Any]] = []
    for (extension, case_id, product), group in sorted(grouped.items()):
        deltas = [
            _to_float(row.get("delta_on_due_percentage_points"), math.nan)
            for row in group
        ]
        backlog = [
            _to_float(row.get("delta_backlog_qty_days"), math.nan) for row in group
        ]
        released = [
            _to_float(row.get("delta_released_qty"), math.nan) for row in group
        ]
        clean_delta = [value for value in deltas if math.isfinite(value)]
        clean_backlog = [value for value in backlog if math.isfinite(value)]
        clean_released = [value for value in released if math.isfinite(value)]
        first = group[0]
        result.append(
            {
                "extension": extension,
                "case_id": case_id,
                "failure_mode": first.get("failure_mode"),
                "mechanism_value": first.get("mechanism_value"),
                "mechanism_unit": first.get("mechanism_unit"),
                "stress_start_day": first.get("stress_start_day"),
                "stress_end_day": first.get("stress_end_day"),
                "product_id": product,
                "product_uom": first.get("product_uom"),
                "paired_realization_count": len(group),
                "new_run_row_count": sum(
                    str(row.get("case_origin")) == "new_run" for row in group
                ),
                "reused_source_row_count": sum(
                    str(row.get("case_origin")) == "reused_exact_source_case"
                    for row in group
                ),
                "on_due_delta_percentage_points_mean": (
                    statistics.fmean(clean_delta) if clean_delta else ""
                ),
                "on_due_delta_percentage_points_sample_std": _sample_std(deltas),
                "on_due_delta_percentage_points_min": (
                    min(clean_delta) if clean_delta else ""
                ),
                "on_due_delta_percentage_points_max": (
                    max(clean_delta) if clean_delta else ""
                ),
                "backlog_delta_qty_days_mean": (
                    statistics.fmean(clean_backlog) if clean_backlog else ""
                ),
                "backlog_unit": first.get("backlog_unit"),
                "released_qty_delta_mean": (
                    statistics.fmean(clean_released) if clean_released else ""
                ),
                "production_unit": first.get("production_unit"),
                "lower_tail_percentile_reported": False,
                "industrial_probability_estimated": False,
            }
        )
    return result


def _extension_manifest(
    *,
    extension: str,
    mode: str,
    cases: Sequence[PlannedCase],
    product_rows: Sequence[Mapping[str, Any]],
    flow_rows: Sequence[Mapping[str, Any]],
    lineage: Mapping[str, Any],
) -> dict[str, Any]:
    expected_case_keys = {case.case_key for case in cases}
    product_case_keys = {
        str(row.get("case_key") or "") for row in product_rows
    }
    complete = bool(expected_case_keys) and expected_case_keys <= product_case_keys
    flow_by_case_lane: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in flow_rows:
        flow_by_case_lane[
            (
                str(row.get("case_id") or ""),
                str(row.get("supplier_id") or ""),
                str(row.get("item_id") or ""),
                str(row.get("dst_node_id") or ""),
            )
        ].append(row)
    expected_lane_keys: set[tuple[str, str, str, str]] = set()
    expected_seeds_by_case_id: dict[str, set[int]] = defaultdict(set)
    expected_lanes_by_case_supplier: dict[
        tuple[str, str], set[tuple[str, str, str, str]]
    ] = defaultdict(set)
    for case in cases:
        expected_seeds_by_case_id[case.case_id].add(case.seed)
        for lane in case.lanes:
            lane_key = (
                case.case_id,
                lane.supplier_id,
                lane.item_id,
                lane.dst_node_id,
            )
            expected_lane_keys.add(lane_key)
            expected_lanes_by_case_supplier[
                (case.case_id, lane.supplier_id)
            ].add(lane_key)
    flow_gate_rows: list[dict[str, Any]] = []
    joint_active_seed_ids_by_lane: dict[
        tuple[str, str, str, str], set[int]
    ] = {}
    for key in sorted(expected_lane_keys):
        group = flow_by_case_lane.get(key, [])
        seed_count = len({int(row["seed"]) for row in group})
        available = len(
            {
                int(row["seed"])
                for row in group
                if _as_bool(row.get("baseline_flow_evidence_available"))
            }
        )
        exercised = len(
            {
                int(row["seed"])
                for row in group
                if _as_bool(row.get("baseline_flow_exercised"))
            }
        )
        risk_applied = len(
            {
                int(row["seed"])
                for row in group
                if _as_bool(row.get("risk_event_applied_on_lane"))
            }
        )
        joint_active_seed_ids = {
            int(row["seed"])
            for row in group
            if _as_bool(row.get("baseline_flow_evidence_available"))
            and _as_bool(row.get("baseline_flow_exercised"))
            and _as_bool(row.get("risk_event_applied_on_lane"))
        }
        joint_active_seed_ids_by_lane[key] = joint_active_seed_ids
        joint_active_exposure = len(joint_active_seed_ids)
        expected_seed_count = len(expected_seeds_by_case_id[key[0]])
        required = (
            29
            if mode == "full" and expected_seed_count >= 30
            else expected_seed_count
        )
        baseline_active_flow_pass = bool(
            required and available >= required and exercised >= required
        )
        risk_application_exposure_pass = bool(
            required and risk_applied >= required
        )
        active_exposure_pass = bool(
            baseline_active_flow_pass
            and risk_application_exposure_pass
            and joint_active_exposure >= required
        )
        flow_gate_rows.append(
            {
                "case_id": key[0],
                "supplier_id": key[1],
                "item_id": key[2],
                "dst_node_id": key[3],
                "paired_seed_count": seed_count,
                "expected_paired_seed_count": expected_seed_count,
                "baseline_flow_evidence_seed_count": available,
                "baseline_flow_exercised_seed_count": exercised,
                "distinct_risk_applied_seed_count": risk_applied,
                "distinct_joint_active_exposure_seed_count": joint_active_exposure,
                "minimum_required_seed_count": required,
                "baseline_active_flow_pass": baseline_active_flow_pass,
                "risk_application_exposure_pass": risk_application_exposure_pass,
                "active_exposure_interpretability_pass": active_exposure_pass,
                "pass": active_exposure_pass,
            }
        )
    all_lanes_joint_gate_rows: list[dict[str, Any]] = []
    for key, lane_keys in sorted(expected_lanes_by_case_supplier.items()):
        lane_seed_sets = [
            joint_active_seed_ids_by_lane.get(lane_key, set())
            for lane_key in sorted(lane_keys)
        ]
        all_lanes_joint_seed_ids = (
            set.intersection(*lane_seed_sets) if lane_seed_sets else set()
        )
        expected_seed_count = len(expected_seeds_by_case_id[key[0]])
        required = (
            29
            if mode == "full" and expected_seed_count >= 30
            else expected_seed_count
        )
        all_lanes_joint_gate_rows.append(
            {
                "case_id": key[0],
                "supplier_id": key[1],
                "expected_affected_lane_count": len(lane_keys),
                "expected_paired_seed_count": expected_seed_count,
                "distinct_all_lanes_joint_active_exposure_seed_count": len(
                    all_lanes_joint_seed_ids
                ),
                "minimum_required_seed_count": required,
                "pass": bool(
                    required and len(all_lanes_joint_seed_ids) >= required
                ),
            }
        )
    baseline_active_flow_pass = bool(flow_gate_rows) and all(
        row["baseline_active_flow_pass"] for row in flow_gate_rows
    )
    risk_application_exposure_pass = bool(flow_gate_rows) and all(
        row["risk_application_exposure_pass"] for row in flow_gate_rows
    )
    all_lanes_joint_active_exposure_pass = bool(all_lanes_joint_gate_rows) and all(
        row["pass"] for row in all_lanes_joint_gate_rows
    )
    active_exposure_pass = (
        bool(flow_gate_rows)
        and all(
            row["active_exposure_interpretability_pass"]
            for row in flow_gate_rows
        )
        and all_lanes_joint_active_exposure_pass
    )
    execution_integrity = bool(mode == "full" and complete)
    return {
        "schema_version": SCHEMA_VERSION,
        **dict(lineage),
        "extension": extension,
        "status": (
            "planned_not_executed"
            if mode == "plan"
            else ("complete" if complete else "incomplete")
        ),
        "mode": mode,
        "logical_case_count": len(cases),
        "new_run_case_count": sum(case.action == "new_run_required" for case in cases),
        "reused_source_case_count": sum(
            case.action == "reuse_exact_source_case" for case in cases
        ),
        "executed_or_reused_case_count": len(product_case_keys),
        "all_pairing_rows_valid": complete,
        "execution_integrity_pass": execution_integrity,
        "active_flow_gate_by_case_lane": flow_gate_rows,
        "all_lanes_joint_active_exposure_gate_by_case_supplier": (
            all_lanes_joint_gate_rows
        ),
        "active_flow_gate_pass": baseline_active_flow_pass,
        "baseline_active_flow_pass": baseline_active_flow_pass,
        "risk_application_exposure_pass": risk_application_exposure_pass,
        "all_lanes_joint_active_exposure_pass": (
            all_lanes_joint_active_exposure_pass
        ),
        "active_exposure_interpretability_pass": active_exposure_pass,
        "release_gate_pass": False,
        "interpretation_robustness_release_pass": False,
        "extension_is_post_selection_characterization_not_confirmation": True,
        "extension_seed_blocks_independent_of_priority_selection": False,
        "global_priority_robustness_evaluable": False,
        "main_ranking_mutated": False,
        "industrial_probability_estimated": False,
        "result_scope": "conditional_simulation_extension_separate_from_main_ranking",
    }


def _promotion_payload(
    *,
    mode: str,
    plan_dir: Path,
    extension_manifests: Sequence[Mapping[str, Any]],
    causal_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    plan_controls = _read_json(plan_dir / "promotion_controls.json")
    source_pass = _as_bool(plan_controls.get("source_controls_pass"))
    execution_integrity = bool(extension_manifests) and all(
        _as_bool(manifest.get("execution_integrity_pass"))
        for manifest in extension_manifests
    )
    active_exposure = bool(extension_manifests) and all(
        _as_bool(manifest.get("active_exposure_interpretability_pass"))
        for manifest in extension_manifests
    )
    causal_integrity = _as_bool(
        causal_manifest.get("causal_lot_execution_integrity_pass")
    )
    return {
        "status": "scoped_characterization_only_no_promotion",
        "mode": mode,
        "source_scientific_controls_pass": source_pass,
        "common_cause_execution_integrity_pass": _as_bool(
            extension_manifests[0].get("execution_integrity_pass")
        ) if extension_manifests else False,
        "temporal_execution_integrity_pass": _as_bool(
            extension_manifests[1].get("execution_integrity_pass")
        ) if len(extension_manifests) > 1 else False,
        "four_business_causes_execution_integrity_pass": _as_bool(
            extension_manifests[2].get("execution_integrity_pass")
        ) if len(extension_manifests) > 2 else False,
        "all_extension_execution_integrity_pass": execution_integrity,
        "all_extension_active_exposure_interpretability_pass": active_exposure,
        "causal_lot_execution_integrity_pass": causal_integrity,
        "counterfactual_entity_identity_validated": False,
        "causal_lot_attribution_available": False,
        "common_cause_pass": False,
        "temporal_robustness_pass": False,
        "four_business_causes_pass": False,
        "all_required_controls_pass": False,
        "promotion_allowed": False,
        "scoped_descriptive_priority_set_display_allowed": _as_bool(
            plan_controls.get("scoped_descriptive_priority_set_display_allowed")
        ),
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "industrial_criticality_claimed": False,
        "industrial_probability_estimated": False,
        "interpretation": (
            "Caractérisation post-sélection conditionnelle uniquement; aucune "
            "promotion globale ou action opérationnelle n'est autorisée."
        ),
    }


def consolidate_dashboard_network_artifact(
    *,
    source_dir: Path,
    runner_dir: Path,
    output_dir: Path | None = None,
) -> Path:
    """Create a small additive dashboard input without changing either source."""

    source_dir = source_dir.resolve()
    runner_dir = runner_dir.resolve()
    source_manifest_path = source_dir / "campaign_manifest.json"
    runner_manifest_path = runner_dir / RUNNER_MANIFEST
    if not source_manifest_path.is_file() or not runner_manifest_path.is_file():
        raise FileNotFoundError("Manifestes source/runner requis pour la consolidation.")
    source_manifest = _read_json(source_manifest_path)
    runner_manifest = _read_json(runner_manifest_path)
    source_manifest_sha256 = _sha256(source_manifest_path)
    runner_source = Path(str(runner_manifest.get("source_dir") or "")).resolve()
    if runner_source != source_dir:
        raise ValueError("Le runner ne rÃ©fÃ©rence pas cette campagne rÃ©seau source.")
    if (
        str(runner_manifest.get("source_campaign_manifest_sha256") or "")
        != source_manifest_sha256
    ):
        raise ValueError("Le manifeste source diffÃ¨re de celui validÃ© par le runner.")
    source_complete = bool(
        str(source_manifest.get("status") or "") == "complete"
        and str(source_manifest.get("mode") or "") == "full"
    )
    runner_complete = bool(
        str(runner_manifest.get("status") or "") == "complete"
        and str(runner_manifest.get("mode") or "") == "full"
    )
    extension_manifest_paths = {
        "multi_lane_supplier_common_cause": (
            runner_dir / "multi_lane_supplier_common_cause_manifest.json"
        ),
        "temporal_robustness": runner_dir / "temporal_robustness_manifest.json",
        "four_business_cause_confirmation": (
            runner_dir / "priority_four_business_causes_manifest.json"
        ),
        "causal_lot_attribution": runner_dir / "causal_lot_attribution_manifest.json",
    }
    missing_extension_manifests = [
        name for name, path in extension_manifest_paths.items() if not path.is_file()
    ]
    if missing_extension_manifests:
        raise FileNotFoundError(
            "Manifestes d'extension absents: " + ", ".join(missing_extension_manifests)
        )
    extension_manifests = {
        name: _read_json(path) for name, path in extension_manifest_paths.items()
    }
    expected_runner_signature = str(runner_manifest.get("runner_signature") or "")
    expected_plan_signature = str(runner_manifest.get("plan_signature") or "")
    for name, payload in extension_manifests.items():
        if str(payload.get("runner_signature") or "") != expected_runner_signature:
            raise ValueError(f"Extension {name} liÃ©e Ã  un autre runner.")
        if str(payload.get("plan_signature") or "") != expected_plan_signature:
            raise ValueError(f"Extension {name} liÃ©e Ã  un autre plan.")
        if (
            str(payload.get("source_campaign_manifest_sha256") or "")
            != source_manifest_sha256
        ):
            raise ValueError(f"Extension {name} liÃ©e Ã  une autre source.")
    source_files = {
        name: source_dir / name
        for name in CONSOLIDATED_SMALL_SOURCE_FILES
        if (source_dir / name).is_file()
    }
    required_dashboard_files = {
        "supplier_sensitivity_ranking.csv",
        "failure_mode_sensitivity_summary.csv",
        "confirmed_top3_stability.csv",
    }
    missing_required = sorted(required_dashboard_files - set(source_files))
    if missing_required:
        raise FileNotFoundError(
            "Petits résultats réseau requis absents: " + ", ".join(missing_required)
        )
    oversized = [
        name
        for name, path in source_files.items()
        if path.stat().st_size > 25 * 1024 * 1024
    ]
    if oversized:
        raise ValueError("Fichier trop volumineux pour consolidation: " + ", ".join(oversized))
    source_hashes = {name: _sha256(path) for name, path in sorted(source_files.items())}
    extension_files = {
        name: runner_dir / name
        for name in CONSOLIDATED_SMALL_EXTENSION_FILES
        if (runner_dir / name).is_file()
    }
    missing_extension_files = sorted(
        set(CONSOLIDATED_SMALL_EXTENSION_FILES) - set(extension_files)
    )
    if missing_extension_files:
        raise FileNotFoundError(
            "Petits résultats d'extension requis absents: "
            + ", ".join(missing_extension_files)
        )
    oversized_extensions = [
        name
        for name, path in extension_files.items()
        if path.stat().st_size > 25 * 1024 * 1024
    ]
    if oversized_extensions:
        raise ValueError(
            "Résultat d'extension trop volumineux pour consolidation: "
            + ", ".join(oversized_extensions)
        )
    extension_file_hashes = {
        name: _sha256(path) for name, path in sorted(extension_files.items())
    }
    extension_hashes = {
        name: _sha256(path) for name, path in sorted(extension_manifest_paths.items())
    }
    signature = network.campaign_core.campaign_signature(
        {
            "schema_version": SCHEMA_VERSION,
            "source_campaign_manifest_sha256": source_manifest_sha256,
            "source_small_file_hashes": source_hashes,
            "extension_small_file_hashes": extension_file_hashes,
            "runner_manifest_sha256": _sha256(runner_manifest_path),
            "extension_manifest_hashes": extension_hashes,
        }
    )
    if output_dir is None:
        output_dir = runner_dir / "consolidated_dashboard_network_artifact"
    output_dir = output_dir.resolve()
    consolidation_path = output_dir / "consolidation_manifest.json"
    if output_dir.exists():
        if not consolidation_path.is_file():
            raise RuntimeError("Consolidation existante sans manifeste.")
        existing = _read_json(consolidation_path)
        if str(existing.get("consolidation_signature") or "") != signature:
            raise RuntimeError("Consolidation existante de signature différente.")
        copied_hashes = {
            **dict(existing.get("source_small_file_hashes") or {}),
            **dict(existing.get("extension_small_file_hashes") or {}),
        }
        for name, expected_hash in copied_hashes.items():
            copied = output_dir / str(name)
            if not copied.is_file() or _sha256(copied) != str(expected_hash):
                raise RuntimeError(
                    f"Consolidation existante altérée; empreinte invalide: {name}"
                )
        expected_campaign_hash = str(
            existing.get("consolidated_campaign_manifest_sha256") or ""
        )
        campaign_path = output_dir / "campaign_manifest.json"
        if (
            not expected_campaign_hash
            or not campaign_path.is_file()
            or _sha256(campaign_path) != expected_campaign_hash
        ):
            raise RuntimeError(
                "Consolidation existante altérée; manifeste campagne invalide."
            )
        return output_dir
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, source_path in source_files.items():
        shutil.copy2(source_path, output_dir / name)
    for name, extension_path in extension_files.items():
        shutil.copy2(extension_path, output_dir / name)
    extension_states = {
        name: {
            "execution_integrity_pass": _as_bool(
                payload.get(
                    "execution_integrity_pass",
                    payload.get("causal_lot_execution_integrity_pass"),
                )
            ),
            "active_exposure_interpretability_pass": _as_bool(
                payload.get("active_exposure_interpretability_pass")
            ),
            "interpretation_release_pass": False,
            "pass": False,
            "complete": str(payload.get("status") or "") == "complete",
            "status": str(payload.get("status") or ""),
            "source_manifest_sha256": extension_hashes[name],
        }
        for name, payload in extension_manifests.items()
    }
    consolidated_manifest = dict(source_manifest)
    consolidated_manifest.update(
        {
            "status": "complete" if source_complete and runner_complete else "incomplete",
            "mode": "full",
            "consolidated_additive_artifact": True,
            "consolidation_signature": signature,
            "source_campaign_signature": source_manifest.get("campaign_signature"),
            "extension_runner_signature": runner_manifest.get("runner_signature"),
            "extensions_required": extension_states,
            "priority_selection_lineage": runner_manifest.get(
                "priority_selection_lineage"
            ),
            "priority_selection_lineage_sha256": runner_manifest.get(
                "priority_selection_lineage_sha256"
            ),
            "scoped_descriptive_priority_set_display_allowed": _as_bool(
                (runner_manifest.get("priority_selection_lineage") or {}).get(
                    "scoped_descriptive_priority_set_display_allowed"
                )
            ),
            "confirmatory_priority_set_release_allowed": False,
            "global_priority_release_allowed": False,
            "action_promotion_allowed": False,
            "priority_set_stabilized": False,
            "universal_supplier_top3_release_pass": False,
            "source_campaign_complete": source_complete,
            "extension_runner_complete": runner_complete,
            "previous_artifacts_mutated": False,
            "large_case_directories_copied": False,
            "consolidated_small_file_count": len(source_files),
            "consolidated_extension_file_count": len(extension_files),
        }
    )
    _write_json(output_dir / "campaign_manifest.json", consolidated_manifest)
    consolidated_campaign_manifest_sha256 = _sha256(
        output_dir / "campaign_manifest.json"
    )
    consolidation_manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": consolidated_manifest["status"],
        "consolidation_signature": signature,
        "source_dir": str(source_dir),
        "runner_dir": str(runner_dir),
        "source_campaign_manifest_sha256": source_manifest_sha256,
        "source_small_file_hashes": source_hashes,
        "extension_small_file_hashes": extension_file_hashes,
        "runner_manifest_sha256": _sha256(runner_manifest_path),
        "extension_manifest_hashes": extension_hashes,
        "consolidated_campaign_manifest_sha256": (
            consolidated_campaign_manifest_sha256
        ),
        "extensions_required": extension_states,
        "priority_selection_lineage_sha256": runner_manifest.get(
            "priority_selection_lineage_sha256"
        ),
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "large_case_directories_copied": False,
        "source_artifacts_mutated": False,
    }
    _write_json(consolidation_path, consolidation_manifest)
    return output_dir


def run_extensions(
    *,
    plan_dir: Path,
    mode: str,
    output_dir: Path | None = None,
    graph_path: Path = network.DEFAULT_GRAPH,
    engine_path: Path = network.DEFAULT_ENGINE,
    profile_path: Path = network.DEFAULT_PROFILE,
    scenario_id: str = "scn:BASE",
    days: int = 720,
    workers: int = 2,
    retention: str = "summary",
    case_executor: Executor | None = None,
    checkpoint_after_repetitions: int | None = None,
) -> dict[str, Any]:
    if mode not in {"plan", "smoke", "full"}:
        raise ValueError(f"Mode inconnu: {mode}")
    if days != planner.BASE_SIMULATION_DAYS:
        raise ValueError(
            "--days reste le contrat de compatibilité J0-J719; les horizons "
            "prolongés sont portés et signés cas par cas par le plan."
        )
    if workers <= 0:
        raise ValueError("Le nombre de workers doit être positif.")
    if retention != "summary":
        raise ValueError("Seule la rétention summary est autorisée.")
    plan_dir = plan_dir.resolve()
    custom_executor_used = case_executor is not None
    if mode == "full" and custom_executor_used:
        raise ValueError(
            "Un paquet full publiable exige l'exécuteur moteur intégré; "
            "l'injection d'un exécuteur est réservée aux tests/smokes."
        )
    executor_contract = (
        "builtin_execute_engine_case"
        if not custom_executor_used
        else (
            "custom_nonpublishable:"
            f"{type(case_executor).__module__}.{type(case_executor).__qualname__}"
        )
    )
    plan_manifest, baselines, stress_cases = load_signed_plan(
        plan_dir, require_boundary_lineage=(mode == "full")
    )
    plan_manifest_sha256 = _sha256(
        plan_dir / "post_priority_extensions_plan_manifest.json"
    )
    locked_scenario_id = str(
        (plan_manifest.get("execution_configuration_lock") or {}).get(
            "scenario_id"
        )
        or ""
    )
    if not locked_scenario_id or scenario_id != locked_scenario_id:
        raise ValueError(
            "Scénario d'exécution incompatible avec le plan: "
            f"attendu={locked_scenario_id!r}, obtenu={scenario_id!r}"
        )
    source_dir = Path(str(plan_manifest.get("source_artifact") or "")).resolve()
    graph_path, engine_path, profile_path = _verify_configuration_paths(
        plan_manifest,
        graph_path=graph_path,
        engine_path=engine_path,
        profile_path=profile_path,
    )
    selected_baselines, selected_stress = _selected_cases(mode, baselines, stress_cases)
    signed_seed_ids = (
        _signed_full_seed_ids(
            plan_manifest=plan_manifest,
            stress_cases=selected_stress,
        )
        if mode == "full"
        else ()
    )
    execution_seed_ids, preliminary_checkpoint_requested = _execution_seed_target(
        mode=mode,
        signed_seed_ids=signed_seed_ids,
        checkpoint_after_repetitions=checkpoint_after_repetitions,
    )
    execution_seed_set = set(execution_seed_ids)
    execution_baselines = (
        [case for case in selected_baselines if case.seed in execution_seed_set]
        if mode == "full"
        else list(selected_baselines)
    )
    execution_stress = (
        [case for case in selected_stress if case.seed in execution_seed_set]
        if mode == "full"
        else list(selected_stress)
    )
    baseline_owners, baseline_owner_key_by_case_key = _baseline_materialization_plan(
        selected_baselines
    )
    execution_owner_keys = {
        baseline_owner_key_by_case_key[case.case_key]
        for case in execution_baselines
    }
    execution_baseline_owners = [
        case for case in baseline_owners if case.case_key in execution_owner_keys
    ]
    baseline_materialization = _baseline_materialization_signature_payload(
        owners=baseline_owners,
        owner_key_by_case_key=baseline_owner_key_by_case_key,
    )
    planned_counts = plan_manifest.get("planned_case_counts") or {}
    selected_new_stress_count = sum(
        case.action == "new_run_required" for case in selected_stress
    )
    selected_new_baseline_reference_count = sum(
        case.action == "new_run_required" for case in selected_baselines
    )
    selected_engine_physical_count = len(baseline_owners) + selected_new_stress_count
    if mode == "full":
        exact_count_contract = {
            "logical_stress_comparison_count": len(selected_stress),
            "design_declared_new_baseline_reference_count": (
                selected_new_baseline_reference_count
            ),
            "design_declared_new_stress_run_count": selected_new_stress_count,
            "new_baseline_engine_run_count": len(baseline_owners),
            "new_stress_engine_run_count": selected_new_stress_count,
            "expected_engine_physical_run_count": selected_engine_physical_count,
            "new_run_count": selected_engine_physical_count,
        }
        mismatched_counts = {
            key: {
                "planned": _to_int(planned_counts.get(key), -1),
                "runner": expected,
            }
            for key, expected in exact_count_contract.items()
            if _to_int(planned_counts.get(key), -1) != expected
        }
        if mismatched_counts:
            raise ValueError(
                "Compteurs physiques/logiques du plan incompatibles avec le runner: "
                + json.dumps(mismatched_counts, sort_keys=True)
            )
    causal_source_material_hashes = _causal_source_material_hashes(plan_dir)
    maximum_simulation_days = max(
        (case.simulation_days for case in [*selected_baselines, *selected_stress]),
        default=days,
    )
    signature = _runner_signature(
        plan_manifest=plan_manifest,
        plan_manifest_sha256=plan_manifest_sha256,
        mode=mode,
        selected_baselines=selected_baselines,
        selected_stress=selected_stress,
        baseline_materialization=baseline_materialization,
        causal_source_material_hashes=causal_source_material_hashes,
        scenario_id=scenario_id,
        days=days,
        retention=retention,
        executor_contract=executor_contract,
        custom_executor_used=custom_executor_used,
        signed_seed_ids=signed_seed_ids,
    )
    if output_dir is None:
        output_dir = (
            plan_dir.parent
            / "supplier_network_post_priority_extension_runs"
            / (
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                + "__"
                + signature[:12]
            )
        )
    output_dir = output_dir.resolve()
    for forbidden in (plan_dir, source_dir):
        try:
            output_dir.relative_to(forbidden)
        except ValueError:
            continue
        raise ValueError("Le runner doit écrire hors du plan et de la campagne source.")
    run_config = _build_run_config(
        source_dir=source_dir,
        output_dir=output_dir,
        graph_path=graph_path,
        engine_path=engine_path,
        profile_path=profile_path,
        scenario_id=scenario_id,
        days=maximum_simulation_days,
        retention=retention,
    )
    context = RunnerContext(
        plan_dir=plan_dir,
        source_dir=source_dir,
        output_dir=output_dir,
        mode=mode,
        days=maximum_simulation_days,
        workers=workers,
        retention=retention,
        signature=signature,
        graph_path=graph_path,
        engine_path=engine_path,
        profile_path=profile_path,
        run_config=run_config,
    )
    source_manifest_sha256 = _sha256(source_dir / "campaign_manifest.json")
    lineage = {
        "runner_signature": signature,
        "plan_signature": str(plan_manifest.get("plan_signature") or ""),
        "plan_manifest_sha256": plan_manifest_sha256,
        "source_campaign_manifest_sha256": source_manifest_sha256,
        "contract_revision": plan_manifest.get("contract_revision"),
        "priority_selection_lineage": plan_manifest.get(
            "priority_selection_lineage"
        ),
        "priority_selection_lineage_sha256": plan_manifest.get(
            "priority_selection_lineage_sha256"
        ),
    }
    initial_manifest = {
        "schema_version": SCHEMA_VERSION,
        "runner_signature": signature,
        "plan_signature": plan_manifest.get("plan_signature"),
        "plan_manifest_sha256": plan_manifest_sha256,
        "plan_dir": str(plan_dir),
        "source_dir": str(source_dir),
        "source_campaign_manifest_sha256": source_manifest_sha256,
        "scenario_id": scenario_id,
        "mode": mode,
        "status": "planned" if mode == "plan" else "running",
        "active_process_id": 0 if mode == "plan" else os.getpid(),
        "active_process_guard_semantics": (
            "best_effort_non_atomic_pid_liveness_check_not_exclusive_lock"
        ),
        "created_or_resumed_at_utc": _utc_now(),
        "selected_baseline_case_count": len(selected_baselines),
        "selected_stress_case_count": len(selected_stress),
        "signed_plan_new_baseline_run_count": sum(
            case.action == "new_run_required" for case in selected_baselines
        ),
        "selected_new_baseline_run_count": len(baseline_owners),
        "runner_generated_baseline_physical_run_count": len(baseline_owners),
        "runner_generated_baseline_alias_count": (
            len(selected_baselines) - len(baseline_owners)
        ),
        "baseline_materialization": baseline_materialization,
        "causal_source_material_hashes": causal_source_material_hashes,
        "selected_new_stress_run_count": selected_new_stress_count,
        "selected_reused_stress_case_count": sum(
            case.action == "reuse_exact_source_case" for case in selected_stress
        ),
        "main_ranking_mutated": False,
        "source_artifact_mutated": False,
        "plan_artifact_mutated": False,
        "industrial_probability_estimated": False,
        "incidents_are_exogenous_hypotheses": True,
        "retention": retention,
        "executor_contract": executor_contract,
        "custom_executor_used": custom_executor_used,
        "publishable_execution_contract_pass": bool(
            False
        ),
        "publishable_after_exact_full_completion_only": True,
        "seed_scheduling_policy": SEED_PREFIX_SCHEDULING_POLICY,
        "signed_full_seed_ids": list(signed_seed_ids),
        "current_cumulative_target_seed_ids": list(execution_seed_ids),
        "checkpoint_after_repetitions": checkpoint_after_repetitions,
        "preliminary_checkpoint_requested": preliminary_checkpoint_requested,
        "contract_revision": plan_manifest.get("contract_revision"),
        "priority_selection_lineage": plan_manifest.get(
            "priority_selection_lineage"
        ),
        "priority_selection_lineage_sha256": plan_manifest.get(
            "priority_selection_lineage_sha256"
        ),
        "temporal_horizon_contract": plan_manifest.get(
            "temporal_horizon_contract"
        ),
        "case_simulation_days": sorted(
            {case.simulation_days for case in [*selected_baselines, *selected_stress]}
        ),
        "maximum_simulation_days": maximum_simulation_days,
        "runner_script_sha256": _sha256(Path(__file__)),
        "planner_script_sha256": _sha256(Path(planner.__file__)),
        "expected_engine_physical_run_count": (
            0
            if mode == "plan"
            else selected_engine_physical_count
        ),
    }
    runner_manifest, ledger = _prepare_output(
        output_dir=output_dir,
        signature=signature,
        manifest_payload=initial_manifest,
    )
    checkpoint_seed_set = set(
        signed_seed_ids[:PRELIMINARY_CHECKPOINT_REPEAT_COUNT]
    )
    checkpoint_baseline_owner_keys = {
        baseline_owner_key_by_case_key[case.case_key]
        for case in selected_baselines
        if case.seed in checkpoint_seed_set
    }
    expected_checkpoint_evidence_keys = checkpoint_baseline_owner_keys | {
        case.case_key
        for case in selected_stress
        if case.seed in checkpoint_seed_set
    }
    existing_checkpoint = _validate_preliminary_checkpoint(
        output_dir=output_dir,
        runner_signature=signature,
        plan_manifest_sha256=plan_manifest_sha256,
        require_live_ledger_match=(
            str(runner_manifest.get("status") or "") == "paused_preliminary"
        ),
        expected_signed_seed_ids=signed_seed_ids if mode == "full" else None,
        expected_evidence_keys=(
            expected_checkpoint_evidence_keys if mode == "full" else None
        ),
    )
    if existing_checkpoint is not None and mode != "full":
        raise RuntimeError("Un jalon full ne peut pas être repris dans un autre mode.")
    existing_process_id = _to_int(runner_manifest.get("active_process_id"), 0)
    if (
        mode != "plan"
        and str(runner_manifest.get("status") or "") == "running"
        and existing_process_id not in {0, os.getpid()}
        and _process_is_running(existing_process_id)
    ):
        raise RuntimeError(
            "Une autre invocation du runner est encore active pour ce dossier."
        )
    if (
        str(runner_manifest.get("status") or "") == "complete"
        and preliminary_checkpoint_requested
    ):
        raise RuntimeError(
            "Une exécution full complète ne peut pas être rétrogradée au jalon 15."
        )
    if mode != "plan" and str(runner_manifest.get("status") or "") != "complete":
        runner_manifest.update(
            {
                "status": "running",
                "last_invocation_started_at_utc": _utc_now(),
                "current_cumulative_target_seed_ids": list(execution_seed_ids),
                "checkpoint_after_repetitions": checkpoint_after_repetitions,
                "preliminary_checkpoint_requested": preliminary_checkpoint_requested,
                "publishable_execution_contract_pass": False,
                "active_process_id": os.getpid(),
            }
        )
        runner_manifest.pop("failed_at_utc", None)
        runner_manifest.pop("error", None)
        _write_json(output_dir / RUNNER_MANIFEST, runner_manifest)
    case_reference_rows = [
        {
            "case_key": case.case_key,
            "extension": case.extension,
            "case_id": case.case_id,
            "seed": case.seed,
            "pairing_block_id": case.pairing_block_id,
            "paired_baseline_case_id": case.paired_baseline_case_id,
            "signed_plan_action": case.action,
            "action": (
                "materialize_runner_baseline"
                if case.extension == "baseline"
                and baseline_owner_key_by_case_key.get(case.case_key) == case.case_key
                else (
                    "reuse_runner_materialized_baseline"
                    if case.extension == "baseline"
                    else case.action
                )
            ),
            "physical_baseline_owner_case_key": (
                baseline_owner_key_by_case_key.get(case.case_key, "")
                if case.extension == "baseline"
                else ""
            ),
            "source_case_key": case.source_case_key,
            "lot_trace_required": case.lot_trace_required,
            "simulation_days": case.simulation_days,
            "outcome_spec_id": case.outcome_spec_id,
            "outcome_start_day": case.outcome_start_day,
            "outcome_end_day": case.outcome_end_day,
            "outcome_day_count": case.outcome_day_count,
            "outcome_bundle_sha256": case.outcome_bundle_sha256,
            "preincident_snapshot_day": case.preincident_snapshot_day,
            "stress_start_day": case.start_day,
            "stress_end_day": case.end_day,
            "failure_mode": case.mechanism_key,
            "main_ranking_mutated": False,
            "scheduled_in_current_invocation": (
                case in execution_baselines or case in execution_stress
            ),
        }
        for case in [*selected_baselines, *selected_stress]
    ]
    _write_csv(output_dir / "execution_case_reference.csv", case_reference_rows)
    risk_inputs: dict[str, Path] = {}
    for case in execution_stress:
        if case.action != "new_run_required":
            continue
        risk_path = (
            output_dir
            / "inputs"
            / "risk_events"
            / case.extension
            / case.case_id
            / f"seed_{case.seed}.csv"
        )
        network.campaign_core.write_risk_csv(risk_path, _risk_rows(case))
        risk_inputs[case.case_key] = risk_path
    graph = _read_json(graph_path)
    extension_order = (
        "multi_lane_supplier_common_cause",
        "temporal_robustness",
        "priority_four_business_causes",
    )
    if mode == "plan":
        extension_manifests: list[dict[str, Any]] = []
        for extension in extension_order:
            cases = [case for case in selected_stress if case.extension == extension]
            extension_manifest = _extension_manifest(
                extension=extension,
                mode=mode,
                cases=cases,
                product_rows=[],
                flow_rows=[],
                lineage=lineage,
            )
            extension_manifests.append(extension_manifest)
            _write_json(output_dir / EXTENSION_FILES[extension][4], extension_manifest)
        causal_manifest = {
            "schema_version": SCHEMA_VERSION,
            **lineage,
            "status": "planned_not_executed",
            "mode": mode,
            "logical_pair_count": sum(
                case.extension == "causal_lot_attribution_subset"
                for case in selected_stress
            ),
            "release_gate_pass": False,
            "causal_lot_execution_integrity_pass": False,
            "technical_event_heuristic_pairing_integrity_pass": False,
            "heuristic_comparison_evaluable_pass": False,
            "causal_comparison_evaluable_pass": False,
            "heuristic_comparison_display_allowed": False,
            "all_pairs_heuristic_technical_event_comparison_evaluated": False,
            "all_pairs_counterfactually_evaluated": False,
            "counterfactual_entity_identity_validated": False,
            "causal_lot_attribution_available": False,
            "genealogical_exposure_is_upper_bound": True,
            "main_ranking_mutated": False,
        }
        _write_json(output_dir / "causal_lot_attribution_manifest.json", causal_manifest)
        promotion = _promotion_payload(
            mode=mode,
            plan_dir=plan_dir,
            extension_manifests=extension_manifests,
            causal_manifest=causal_manifest,
        )
        _write_json(output_dir / "promotion_controls.json", promotion)
        runner_manifest.update(
            {
                "status": "planned",
                "completed_at_utc": _utc_now(),
                "executed_engine_case_count": 0,
                "promotion_allowed": False,
            }
        )
        _write_json(output_dir / RUNNER_MANIFEST, runner_manifest)
        return {
            "status": "planned",
            "output_dir": str(output_dir),
            "runner_signature": signature,
            "executed_engine_case_count": 0,
            "promotion_allowed": False,
        }

    executor = case_executor or execute_engine_case
    source_index = _source_metric_index(source_dir)
    inline_cases = dict(ledger.get("cases") or {})
    if inline_cases:
        raise RuntimeError(
            "Ancien registre inline non accepté par le contrat de reprise avec empreintes."
        )
    case_files = dict(ledger.get("case_files") or {})
    case_file_hashes = dict(ledger.get("case_file_sha256") or {})
    if set(case_files) != set(case_file_hashes):
        raise RuntimeError("Registre de reprise incomplet: empreintes de cas incohérentes.")
    expected_ledger_relatives = {
        _canonical_ledger_relative_path(str(key)).as_posix()
        for key in case_files
    }
    if len(expected_ledger_relatives) != len(case_files):
        raise RuntimeError("Collision de chemin canonique dans le registre de reprise.")
    ledger_dir = output_dir / "ledger_cases"
    disk_ledger_files = (
        {
            path.relative_to(output_dir).as_posix()
            for path in ledger_dir.rglob("*")
            if path.is_file()
        }
        if ledger_dir.is_dir()
        else set()
    )
    if disk_ledger_files != expected_ledger_relatives:
        raise RuntimeError("Inventaire disque du registre de reprise non exact.")
    evidence_by_case_key: dict[str, CaseEvidence] = {}
    for key, relative in case_files.items():
        path = _validated_ledger_evidence_path(
            output_dir=output_dir,
            case_key=str(key),
            relative_value=relative,
        )
        if _sha256(path) != str(case_file_hashes.get(key) or ""):
            raise RuntimeError(f"Empreinte de preuve de reprise invalide pour {key}")
        payload = _read_json(path)
        if str(payload.get("case_key") or "") != str(key):
            raise RuntimeError(f"Identité de preuve de reprise invalide pour {key}")
        evidence_by_case_key[str(key)] = _evidence_from_dict(payload)
    baseline_by_id: dict[str, CaseEvidence] = {}

    def persist(case: PlannedCase, evidence: CaseEvidence) -> None:
        if evidence.case_key != case.case_key:
            raise ValueError(
                f"L'exécuteur a retourné {evidence.case_key}, attendu {case.case_key}"
            )
        evidence_by_case_key[case.case_key] = evidence
        relative = _canonical_ledger_relative_path(case.case_key)
        _write_json(output_dir / relative, asdict(evidence))
        case_files[case.case_key] = relative.as_posix()
        case_file_hashes[case.case_key] = _sha256(output_dir / relative)
        ledger["case_files"] = case_files
        ledger["case_file_sha256"] = case_file_hashes
        ledger.pop("cases", None)
        _write_json(output_dir / LEDGER_FILE, ledger)

    try:
        baseline_case_key_by_id = {
            case.case_id: case.case_key for case in execution_baselines
        }
        stress_by_owner_key: dict[str, list[PlannedCase]] = defaultdict(list)
        for stress in execution_stress:
            logical_baseline_key = baseline_case_key_by_id[
                stress.paired_baseline_case_id
            ]
            owner_key = baseline_owner_key_by_case_key[logical_baseline_key]
            stress_by_owner_key[owner_key].append(stress)
        for case in execution_baseline_owners:
            evidence = evidence_by_case_key.get(case.case_key)
            if evidence is None:
                continue
            _materialize_compact_baseline_flows(
                evidence=evidence,
                cases=stress_by_owner_key[case.case_key],
                graph=graph,
            )
            persist(case, evidence)
            _validate_baseline_evidence(case, evidence)
        missing_baseline_owners = [
            case
            for case in execution_baseline_owners
            if case.case_key not in evidence_by_case_key
        ]
        if missing_baseline_owners:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                baseline_futures = {
                    pool.submit(
                        executor,
                        replace(
                            case,
                            action="new_run_required",
                            source_case_key="",
                        ),
                        context,
                        None,
                    ): case
                    for case in missing_baseline_owners
                }
                for future in as_completed(baseline_futures):
                    case = baseline_futures[future]
                    evidence = future.result()
                    _materialize_compact_baseline_flows(
                        evidence=evidence,
                        cases=stress_by_owner_key[case.case_key],
                        graph=graph,
                    )
                    persist(case, evidence)
                    _validate_baseline_evidence(case, evidence)
        for case in execution_baselines:
            owner_key = baseline_owner_key_by_case_key[case.case_key]
            owner_evidence = evidence_by_case_key[owner_key]
            evidence = (
                owner_evidence
                if owner_key == case.case_key
                else replace(
                    owner_evidence,
                    case_key=case.case_key,
                    status=RUNNER_BASELINE_ALIAS_STATUS,
                    reused_source_case=False,
                )
            )
            _validate_baseline_evidence(case, evidence)
            baseline_by_id[case.case_id] = evidence

        reused_stress = [
            case
            for case in execution_stress
            if case.action == "reuse_exact_source_case"
            and case.case_key not in evidence_by_case_key
        ]
        for case in reused_stress:
            evidence = source_case_evidence(case, source_index, source_dir)
            baseline = baseline_by_id[case.paired_baseline_case_id]
            _validate_stress_evidence(case, evidence, baseline, graph)
            persist(case, evidence)

        new_jobs = [
            case
            for case in execution_stress
            if case.action == "new_run_required"
            and case.case_key not in evidence_by_case_key
        ]
        if new_jobs:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(executor, case, context, risk_inputs[case.case_key]): case
                    for case in new_jobs
                }
                for future in as_completed(futures):
                    case = futures[future]
                    evidence = future.result()
                    baseline = baseline_by_id[case.paired_baseline_case_id]
                    _validate_stress_evidence(case, evidence, baseline, graph)
                    persist(case, evidence)
        for case in execution_stress:
            evidence = evidence_by_case_key[case.case_key]
            baseline = baseline_by_id[case.paired_baseline_case_id]
            _validate_stress_evidence(case, evidence, baseline, graph)
    except Exception as error:
        runner_manifest.update(
            {
                "status": "failed",
                "failed_at_utc": _utc_now(),
                "error": f"{type(error).__name__}: {error}",
                "active_process_id": 0,
            }
        )
        _write_json(output_dir / RUNNER_MANIFEST, runner_manifest)
        raise

    expected_execution_evidence_keys = {
        case.case_key
        for case in [*execution_baseline_owners, *execution_stress]
    }
    if set(evidence_by_case_key) != expected_execution_evidence_keys:
        missing = sorted(expected_execution_evidence_keys - set(evidence_by_case_key))
        extra = sorted(set(evidence_by_case_key) - expected_execution_evidence_keys)
        raise RuntimeError(
            "Inventaire des preuves après exécution non exact: "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )

    if preliminary_checkpoint_requested:
        if retention == "summary":
            for case in execution_baseline_owners:
                evidence = evidence_by_case_key[case.case_key]
                if evidence.run_dir:
                    network.campaign_core.prune_case_artifacts(Path(evidence.run_dir))
        planner.validate_plan_artifact(plan_dir, require_boundary_lineage=True)
        if _causal_source_material_hashes(plan_dir) != causal_source_material_hashes:
            raise RuntimeError(
                "Les preuves lots source ont changé pendant le calcul préliminaire."
            )
        source_hashes = plan_manifest.get("source_artifact_file_hashes") or {}
        if not all(
            (source_dir / str(name)).is_file()
            and _sha256(source_dir / str(name)) == str(expected)
            for name, expected in source_hashes.items()
        ):
            raise RuntimeError(
                "La campagne source a changé pendant le calcul préliminaire."
            )
        checkpoint = _write_preliminary_checkpoint(
            output_dir=output_dir,
            runner_signature=signature,
            plan_manifest=plan_manifest,
            plan_manifest_sha256=plan_manifest_sha256,
            signed_seed_ids=signed_seed_ids,
            completed_seed_ids=execution_seed_ids,
            selected_baselines=execution_baselines,
            selected_stress=execution_stress,
            baseline_owners=execution_baseline_owners,
            evidence_by_case_key=evidence_by_case_key,
            case_files=case_files,
            case_file_hashes=case_file_hashes,
            ledger_sha256=_sha256(output_dir / LEDGER_FILE),
        )
        history = list(runner_manifest.get("checkpoint_history") or [])
        checkpoint_record = {
            "completed_seed_count": len(execution_seed_ids),
            "completed_seed_ids": list(execution_seed_ids),
            "checkpoint_manifest": PRELIMINARY_CHECKPOINT_MANIFEST,
            "checkpoint_signature": checkpoint["checkpoint_signature"],
            "checkpoint_at_utc": checkpoint["checkpoint_at_utc"],
        }
        if not any(
            str(item.get("checkpoint_signature") or "")
            == checkpoint["checkpoint_signature"]
            for item in history
        ):
            history.append(checkpoint_record)
        runner_manifest.update(
            {
                "status": "paused_preliminary",
                "active_process_id": 0,
                "paused_at_utc": checkpoint["checkpoint_at_utc"],
                "checkpoint_history": history,
                "completed_seed_count": len(execution_seed_ids),
                "completed_seed_ids": list(execution_seed_ids),
                "ledger_case_count": len(evidence_by_case_key),
                "ledger_case_file_sha256_count": len(case_file_hashes),
                "execution_ledger_sha256": _sha256(output_dir / LEDGER_FILE),
                "executed_engine_case_count": checkpoint[
                    "executed_engine_physical_run_count"
                ],
                "remaining_engine_physical_run_count": checkpoint[
                    "remaining_engine_physical_run_count"
                ],
                "preliminary_checkpoint_manifest": (
                    PRELIMINARY_CHECKPOINT_MANIFEST
                ),
                "preliminary_checkpoint_manifest_sha256": _sha256(
                    output_dir / PRELIMINARY_CHECKPOINT_MANIFEST
                ),
                "preliminary_not_final": True,
                "finalization_eligible": False,
                "canonical_results_written": False,
                "consolidation_written": False,
                "publishable_execution_contract_pass": False,
                "promotion_allowed": False,
                "confirmatory_priority_set_release_allowed": False,
                "global_priority_release_allowed": False,
                "action_promotion_allowed": False,
            }
        )
        _write_json(output_dir / RUNNER_MANIFEST, runner_manifest)
        return {
            "status": "paused_preliminary",
            "output_dir": str(output_dir),
            "runner_signature": signature,
            "completed_seed_count": len(execution_seed_ids),
            "executed_engine_case_count": checkpoint[
                "executed_engine_physical_run_count"
            ],
            "remaining_engine_physical_run_count": checkpoint[
                "remaining_engine_physical_run_count"
            ],
            "preliminary_checkpoint_manifest": str(
                output_dir / PRELIMINARY_CHECKPOINT_MANIFEST
            ),
            "promotion_allowed": False,
        }

    product_rows: list[dict[str, Any]] = []
    flow_rows: list[dict[str, Any]] = []
    exposure_rows: list[dict[str, Any]] = []
    exposure_detail_rows: list[dict[str, Any]] = []
    causal_detail_rows: list[dict[str, Any]] = []
    causal_pair_rows: list[dict[str, Any]] = []
    for case in selected_stress:
        evidence = evidence_by_case_key[case.case_key]
        baseline = baseline_by_id[case.paired_baseline_case_id]
        product_rows.extend(
            _product_rows(case=case, evidence=evidence, baseline=baseline)
        )
        baseline_flow = _baseline_flow_for_case(
            case=case, baseline=baseline, graph=graph
        )
        flow_rows.extend(
            _flow_rows(case=case, evidence=evidence, baseline_flow=baseline_flow)
        )
        if case.extension == "causal_lot_attribution_subset":
            exposure, exposed = _genealogical_exposure(case=case, evidence=evidence)
            exposure_rows.append(exposure)
            exposure_detail_rows.extend(
                _lot_genealogical_exposure_detail_rows(
                    case=case,
                    exposed_rows=exposed,
                )
            )
            detail = _causal_lot_rows(
                case=case,
                baseline=baseline,
                stress=evidence,
                exposed_rows=exposed,
            )
            causal_detail_rows.extend(detail)
            coverage = _technical_pairing_coverage(
                baseline=baseline,
                stress=evidence,
                exposed_rows=exposed,
            )
            causal_pair_rows.append(
                {
                    "case_key": case.case_key,
                    "case_id": case.case_id,
                    "seed": case.seed,
                    "failure_mode": case.mechanism_key,
                    "root_gate_pass": exposure["root_gate_pass"],
                    "genealogy_integrity_pass": exposure[
                        "genealogy_integrity_pass"
                    ],
                    **coverage,
                    "unique_matched_technical_key_count": len(detail),
                    "actual_difference_row_count": sum(
                        _as_bool(row.get("actual_difference_measured")) for row in detail
                    ),
                    "heuristic_technical_event_comparison_evaluated": bool(detail),
                    "paired_counterfactual_evaluated": False,
                    "any_technical_event_difference_detected": any(
                        _as_bool(row.get("actual_difference_measured")) for row in detail
                    ),
                    "genealogical_exposure_is_upper_bound": True,
                    "industrial_lot_number_claimed": False,
                    "paired_seed_count_per_lane": 1,
                }
            )

    extension_manifests = []
    for extension in extension_order:
        cases = [case for case in selected_stress if case.extension == extension]
        extension_products = [
            row for row in product_rows if str(row.get("extension")) == extension
        ]
        extension_flows = [
            row for row in flow_rows if str(row.get("extension")) == extension
        ]
        summary = _summarize_product_rows(extension_products)
        manifest = _extension_manifest(
            extension=extension,
            mode=mode,
            cases=cases,
            product_rows=extension_products,
            flow_rows=extension_flows,
            lineage=lineage,
        )
        extension_manifests.append(manifest)
        _write_csv(output_dir / EXTENSION_FILES[extension][1], extension_products)
        _write_csv(output_dir / EXTENSION_FILES[extension][2], extension_flows)
        _write_csv(output_dir / EXTENSION_FILES[extension][3], summary)
        _write_json(output_dir / EXTENSION_FILES[extension][4], manifest)
    _write_csv(output_dir / "lot_genealogical_exposure_summary.csv", exposure_rows)
    network.campaign_core.write_csv_atomic(
        output_dir / "lot_genealogical_exposure_detail.csv",
        exposure_detail_rows,
        fields=LOT_EXPOSURE_DETAIL_FIELDS,
    )
    _write_csv(output_dir / "causal_lot_attribution_summary.csv", causal_pair_rows)
    network.campaign_core.write_csv_atomic(
        output_dir / "causal_lot_attribution_detail.csv",
        causal_detail_rows,
        fields=CAUSAL_DETAIL_FIELDS,
    )
    expected_causal = [
        case
        for case in selected_stress
        if case.extension == "causal_lot_attribution_subset"
    ]
    causal_complete = bool(expected_causal) and len(causal_pair_rows) == len(expected_causal)
    causal_gates = _causal_lot_gate_summary(
        mode=mode,
        expected_pair_count=len(expected_causal),
        pair_rows=causal_pair_rows,
    )
    causal_manifest = {
        "schema_version": SCHEMA_VERSION,
        **lineage,
        "status": "complete" if causal_complete else "incomplete",
        "mode": mode,
        "logical_pair_count": len(expected_causal),
        "evaluated_pair_count": len(causal_pair_rows),
        "unique_matched_technical_key_count": sum(
            _to_int(row.get("unique_matched_technical_key_count"))
            for row in causal_pair_rows
        ),
        "all_root_gates_pass": bool(causal_pair_rows)
        and all(_as_bool(row.get("root_gate_pass")) for row in causal_pair_rows),
        "all_genealogy_integrity_gates_pass": bool(causal_pair_rows)
        and all(
            _as_bool(row.get("genealogy_integrity_pass"))
            for row in causal_pair_rows
        ),
        "all_pairs_heuristic_technical_event_comparison_evaluated": bool(
            causal_pair_rows
        )
        and all(
            _as_bool(row.get("heuristic_technical_event_comparison_evaluated"))
            for row in causal_pair_rows
        ),
        "all_pairs_counterfactually_evaluated": False,
        **causal_gates,
        "counterfactual_entity_identity_validated": False,
        "causal_lot_attribution_available": False,
        "causal_lot_pair_count": len(causal_pair_rows),
        "paired_seed_count_per_lane": 1,
        "lot_genealogical_exposure_detail_file": (
            "lot_genealogical_exposure_detail.csv"
        ),
        "lot_genealogical_exposure_detail_row_count": len(exposure_detail_rows),
        "lot_genealogical_exposure_detail_sha256": _sha256(
            output_dir / "lot_genealogical_exposure_detail.csv"
        ),
        "lot_genealogical_exposure_detail_is_bfs_closure": bool(exposure_rows)
        and all(
            _as_bool(row.get("published_exposure_is_exact_bfs_closure"))
            for row in exposure_rows
        ),
        "release_gate_pass": False,
        "genealogical_exposure_is_upper_bound": True,
        "quality_hold_quarantine_is_reconstructed_not_native": True,
        "main_ranking_mutated": False,
        "industrial_probability_estimated": False,
        "network_wide_lot_effect_evaluable": False,
        "multi_lane_common_cause_lot_effect_evaluable": False,
        "four_cause_lot_effect_evaluable": False,
        "temporal_lot_effect_variability_evaluable": False,
        "lot_effect_recurrence_evaluable": False,
    }
    _write_json(output_dir / "causal_lot_attribution_manifest.json", causal_manifest)
    promotion = _promotion_payload(
        mode=mode,
        plan_dir=plan_dir,
        extension_manifests=extension_manifests,
        causal_manifest=causal_manifest,
    )
    _write_json(output_dir / "promotion_controls.json", promotion)
    if retention == "summary":
        for case in baseline_owners:
            evidence = baseline_by_id[case.case_id]
            if evidence.run_dir:
                network.campaign_core.prune_case_artifacts(Path(evidence.run_dir))
    planner.validate_plan_artifact(
        plan_dir, require_boundary_lineage=(mode == "full")
    )
    if _causal_source_material_hashes(plan_dir) != causal_source_material_hashes:
        raise RuntimeError(
            "Les preuves lots source ont changé pendant l'exécution additive."
        )
    source_hashes = plan_manifest.get("source_artifact_file_hashes") or {}
    source_unchanged = all(
        (source_dir / str(name)).is_file()
        and _sha256(source_dir / str(name)) == str(expected)
        for name, expected in source_hashes.items()
    )
    if not source_unchanged:
        raise RuntimeError("La campagne source a changé pendant l'exécution additive.")
    executed_engine_case_count = sum(
        not evidence.reused_source_case
        and evidence.status
        not in {"reused_exact_source_case", RUNNER_BASELINE_ALIAS_STATUS}
        for evidence in evidence_by_case_key.values()
    )
    expected_engine_case_count = len(baseline_owners) + sum(
        case.action == "new_run_required" for case in selected_stress
    )
    if executed_engine_case_count != expected_engine_case_count:
        raise RuntimeError(
            "Nombre de calculs physiques incohérent: "
            f"attendu={expected_engine_case_count}, obtenu={executed_engine_case_count}"
        )
    runner_manifest.pop("consolidation_written", None)
    runner_manifest.update(
        {
            "status": "complete",
            "active_process_id": 0,
            "completed_at_utc": (
                runner_manifest.get("completed_at_utc") or _utc_now()
            ),
            "ledger_case_count": len(evidence_by_case_key),
            "ledger_case_file_sha256_count": len(case_file_hashes),
            "execution_ledger_sha256": _sha256(output_dir / LEDGER_FILE),
            "executed_engine_case_count": executed_engine_case_count,
            "executed_baseline_physical_run_count": len(baseline_owners),
            "executed_new_stress_physical_run_count": sum(
                case.action == "new_run_required" for case in selected_stress
            ),
            "baseline_logical_alias_count": (
                len(selected_baselines) - len(baseline_owners)
            ),
            "reused_source_case_count": sum(
                evidence.reused_source_case
                for evidence in evidence_by_case_key.values()
            ),
            "source_artifact_mutated": False,
            "plan_artifact_mutated": False,
            "main_ranking_mutated": False,
            "extension_release_gates": {
                manifest["extension"]: manifest["release_gate_pass"]
                for manifest in extension_manifests
            },
            "extension_execution_integrity_gates": {
                manifest["extension"]: manifest["execution_integrity_pass"]
                for manifest in extension_manifests
            },
            "extension_active_exposure_interpretability_gates": {
                manifest["extension"]: manifest[
                    "active_exposure_interpretability_pass"
                ]
                for manifest in extension_manifests
            },
            "causal_lot_release_gate_pass": causal_manifest[
                "release_gate_pass"
            ],
            "causal_lot_execution_integrity_pass": causal_manifest[
                "causal_lot_execution_integrity_pass"
            ],
            "counterfactual_entity_identity_validated": False,
            "causal_lot_attribution_available": False,
            "completed_seed_count": len(signed_seed_ids),
            "completed_seed_ids": list(signed_seed_ids),
            "remaining_engine_physical_run_count": 0,
            "preliminary_not_final": False,
            "finalization_eligible": mode == "full",
            "canonical_results_written": True,
            "consolidation_requested_after_manifest_write": mode == "full",
            "publishable_execution_contract_pass": bool(
                mode == "full"
                and executor_contract == "builtin_execute_engine_case"
                and not custom_executor_used
            ),
            "promotion_allowed": promotion["promotion_allowed"],
            "confirmatory_priority_set_release_allowed": False,
            "global_priority_release_allowed": False,
            "action_promotion_allowed": False,
        }
    )
    _write_json(output_dir / RUNNER_MANIFEST, runner_manifest)
    consolidated_dashboard_dir = ""
    if mode == "full":
        consolidated_dashboard_dir = str(
            consolidate_dashboard_network_artifact(
                source_dir=source_dir,
                runner_dir=output_dir,
            )
        )
    return {
        "status": "complete",
        "output_dir": str(output_dir),
        "runner_signature": signature,
        "executed_engine_case_count": runner_manifest[
            "executed_engine_case_count"
        ],
        "reused_source_case_count": runner_manifest["reused_source_case_count"],
        "promotion_allowed": promotion["promotion_allowed"],
        "consolidated_dashboard_network_dir": consolidated_dashboard_dir,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "smoke", "full"), default="plan")
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--graph", type=Path, default=network.DEFAULT_GRAPH)
    parser.add_argument("--engine", type=Path, default=network.DEFAULT_ENGINE)
    parser.add_argument("--engine-profile", type=Path, default=network.DEFAULT_PROFILE)
    parser.add_argument("--scenario-id", default="scn:BASE")
    parser.add_argument("--days", type=int, default=720)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--retention", choices=("summary",), default="summary")
    parser.add_argument(
        "--checkpoint-after-repetitions",
        type=int,
        default=None,
        help=(
            "Pause cumulative non finale après exactement 15 des 30 graines "
            "signées; omettre l'option pour reprendre/finaliser les 30."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = run_extensions(
        plan_dir=args.plan_dir,
        mode=args.mode,
        output_dir=args.output_dir,
        graph_path=args.graph,
        engine_path=args.engine,
        profile_path=args.engine_profile,
        scenario_id=args.scenario_id,
        days=args.days,
        workers=args.workers,
        retention=args.retention,
        checkpoint_after_repetitions=args.checkpoint_after_repetitions,
    )
    print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
