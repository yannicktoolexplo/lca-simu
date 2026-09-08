#!/usr/bin/env python3
"""Freeze an additive old-versus-dynamic requirement-system comparison protocol.

This module never launches the simulation engine.  It proves that the candidate
profile is the old profile with only the explicit static-requirement overrides
removed, inventories the 24 production-input materials, and writes a small
``planned_not_executed`` protocol directory for the separate runner.  The
comparison is deliberately labelled as a coupled diagnostic: changing the
requirement mode also changes inferred direct supplier capacities and upstream
procurement policies in the current engine.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "etudecas.dynamic_requirement_reference_protocol.v3"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GRAPH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
DEFAULT_ENGINE = (
    REPO_ROOT / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"
)
DEFAULT_OLD_PROFILE = (
    Path(__file__).resolve().parent
    / "config"
    / "canonical_real_baseline_engine_profile.json"
)
DEFAULT_NEW_PROFILE = (
    Path(__file__).resolve().parent
    / "config"
    / "canonical_mps_bom_dynamic_requirement_engine_profile_v2.json"
)
DEFAULT_FLOORS = (
    REPO_ROOT.parent
    / "lca-simu-pr40-validation-artifacts-20260726"
    / "supplier_network_risk_screen_20260902_v2"
    / "inputs"
    / "prepared_physical_supplier_floors.csv"
)
DEFAULT_ACTIVE_CAMPAIGN_DIR = (
    REPO_ROOT.parent
    / "lca-simu-pr40-validation-artifacts-20260726"
    / "supplier_network_post_priority_extensions_20260903_v1"
)
DEFAULT_CAPACITY_AUDIT_DIR = (
    REPO_ROOT.parent
    / "lca-simu-pr40-validation-artifacts-20260726"
    / "supplier_dynamic_capacity_coupling_audit_20260904_v3"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT.parent
    / "lca-simu-pr40-validation-artifacts-20260726"
    / "supplier_dynamic_requirement_reference_protocol_20260904_v3"
)
PROTOCOL_FILE = "comparison_protocol.json"
MATERIAL_SCOPE_FILE = "material_scope.csv"
PROFILE_AUDIT_FILE = "profile_change_audit.json"
CAPACITY_AUDIT_FILE = "capacity_coupling_audit.json"
CAPACITY_AUDIT_FROZEN_SUPPLIER_PARAMETERS_FILE = (
    "source_supplier_nominal_parameters.csv"
)
ACTIVE_CAMPAIGN_MANIFEST_FILE = "post_priority_extension_runner_manifest.json"
OLD_VARIANT_ID = "ancienne_reference_hybride"
NEW_VARIANT_ID = "variante_besoins_dynamiques_a_evaluer"
MEASURED_DAYS = 720
WARMUP_DAYS = 240
SMOKE_SEEDS = (340282, 340283, 340284)
COMPARISON_SEEDS = tuple(range(340282, 340297))
LOT_TRACE_SEED = 340282
BOUND_CAMPAIGN_CHECKPOINT_AFTER_REPETITIONS = 15
EXPLICIT_DYNAMIC_PAIRS = (
    "M-1430|item:344135",
    "M-1810|item:338929",
    "SDC-1450|item:021081",
)
SMOOTHED_COVER_PAIRS = ("M-1430|item:344135",)
MANAGED_PROTOCOL_ARGS = (
    "--initial-state-scale",
    "0.1",
    "--opening-observed-stock-scale",
    "1",
    "--mrp-demand-signal-smoothing-days",
    "7",
    "--warmup-days",
    str(WARMUP_DAYS),
    "--warmup-profile-mode",
    "preperiod",
    "--no-restore-opening-stock-after-warmup",
    "--warmup-boundary-audit",
    "--no-initial-seed-open-orders-from-january-snapshot",
    "--mrp-multisource-policy",
    "legacy",
    "--mrp-dynamic-requirement-pair",
    "M-1810,item:338929",
    "--mrp-dynamic-requirement-pair",
    "M-1430,item:344135",
    "--mrp-dynamic-requirement-pair",
    "SDC-1450,item:021081",
    "--mrp-smoothed-cover-requirement-pair",
    "M-1430,item:344135",
    "--external-procurement-enabled",
    "--external-procurement-proactive-replenishment",
    "--external-procurement-lead-mode",
    "supplier_material",
    "--external-procurement-capacity-mode",
    "supplier_nominal",
    "--external-procurement-nominal-capacity-scale",
    "1",
    "--no-supplier-risk-loss-gross-up",
    "--no-supplier-state-dependent-risks",
)


@dataclass(frozen=True)
class Material:
    node_id: str
    item_id: str
    uom: str
    safety_time_days: float
    old_variant_static_profile_override: bool
    old_variant_managed_dynamic_override: bool
    old_variant_requirement_mode: str
    candidate_variant_dynamic_profile_override: bool
    candidate_variant_requirement_mode: str

    @property
    def pair_key(self) -> str:
        return f"{self.node_id}|{self.item_id}"


@dataclass(frozen=True)
class ValidatedProtocol:
    protocol_dir: Path
    manifest: dict[str, Any]
    materials: tuple[Material, ...]
    graph: Path
    engine: Path
    supplier_floors: Path
    old_profile: Path
    new_profile: Path
    active_campaign_dir: Path
    capacity_audit_dir: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_sha256(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def write_csv_atomic(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("Refusing to write an empty material scope")
    fields = list(rows[0])
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def profile_args(path: Path) -> list[str]:
    payload = read_json(path)
    if payload.get("schema_version") != "scan.canonical_engine_profile.v1":
        raise ValueError(f"Unsupported profile schema: {path}")
    args = payload.get("args")
    if (
        not isinstance(args, list)
        or not args
        or not all(isinstance(value, str) for value in args)
    ):
        raise ValueError(f"Invalid profile arguments: {path}")
    return list(args)


def split_static_overrides(args: Sequence[str]) -> tuple[list[str], tuple[str, ...]]:
    retained: list[str] = []
    removed: list[str] = []
    index = 0
    while index < len(args):
        value = args[index]
        if value != "--mrp-static-requirement-pair":
            retained.append(value)
            index += 1
            continue
        if index + 1 >= len(args):
            raise ValueError("Static requirement flag lacks its node,item value")
        pair = str(args[index + 1]).strip()
        parts = pair.split(",")
        if len(parts) != 2 or not parts[0] or not parts[1].startswith("item:"):
            raise ValueError(f"Malformed static requirement pair: {pair!r}")
        removed.append(f"{parts[0]}|{parts[1]}")
        index += 2
    if len(set(removed)) != len(removed):
        raise ValueError("Duplicate static requirement pair in old profile")
    return retained, tuple(removed)


def split_dynamic_overrides(args: Sequence[str]) -> tuple[list[str], tuple[str, ...]]:
    retained: list[str] = []
    removed: list[str] = []
    index = 0
    while index < len(args):
        value = args[index]
        if value != "--mrp-dynamic-requirement-pair":
            retained.append(value)
            index += 1
            continue
        if index + 1 >= len(args):
            raise ValueError("Dynamic requirement flag lacks its node,item value")
        pair = str(args[index + 1]).strip()
        parts = pair.split(",")
        if len(parts) != 2 or not parts[0] or not parts[1].startswith("item:"):
            raise ValueError(f"Malformed dynamic requirement pair: {pair!r}")
        removed.append(f"{parts[0]}|{parts[1]}")
        index += 2
    if len(set(removed)) != len(removed):
        raise ValueError("Duplicate dynamic requirement pair in candidate profile")
    return retained, tuple(removed)


def _inventory_state(node: Mapping[str, Any], item_id: str) -> Mapping[str, Any]:
    matches = [
        row
        for row in ((node.get("inventory") or {}).get("states") or [])
        if str(row.get("item_id") or "") == item_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Unique inventory state required for {node.get('id')}|{item_id}"
        )
    return matches[0]


def material_scope(
    graph: Mapping[str, Any], old_static_pairs: Sequence[str]
) -> tuple[Material, ...]:
    old_set = set(old_static_pairs)
    pairs: dict[str, Material] = {}
    for node in graph.get("nodes") or []:
        node_id = str(node.get("id") or "")
        processes = list(node.get("processes") or [])
        if not processes:
            continue
        for process in processes:
            for component in process.get("inputs") or []:
                item_id = str(component.get("item_id") or "")
                key = f"{node_id}|{item_id}"
                state = _inventory_state(node, item_id)
                mrp_policy = state.get("mrp_policy") or {}
                old_managed_dynamic = key in EXPLICIT_DYNAMIC_PAIRS
                material = Material(
                    node_id=node_id,
                    item_id=item_id,
                    uom=str(state.get("uom") or ""),
                    safety_time_days=float(mrp_policy.get("safety_time_days") or 0.0),
                    old_variant_static_profile_override=key in old_set,
                    old_variant_managed_dynamic_override=old_managed_dynamic,
                    old_variant_requirement_mode=(
                        "explicit_dynamic_mps_bom"
                        if old_managed_dynamic
                        else "explicit_static_capacity_based_requirement"
                    ),
                    candidate_variant_dynamic_profile_override=True,
                    candidate_variant_requirement_mode="explicit_dynamic_mps_bom",
                )
                previous = pairs.get(key)
                if previous is not None and previous != material:
                    raise ValueError(
                        f"Inconsistent repeated material definition: {key}"
                    )
                pairs[key] = material
    ordered = tuple(pairs[key] for key in sorted(pairs))
    expected_nodes = {"M-1430", "M-1810", "SDC-1450"}
    if len(ordered) != 24 or {row.node_id for row in ordered} != expected_nodes:
        raise ValueError(
            "The comparison graph must expose exactly 24 materials on the three production nodes"
        )
    direct = {row.pair_key for row in ordered if row.node_id in {"M-1430", "M-1810"}}
    if len(direct) != 23 or direct != old_set:
        raise ValueError(
            "Old static overrides must match the 23 direct factory-input pairs"
        )
    if {row.pair_key for row in ordered if row.node_id == "SDC-1450"} != {
        "SDC-1450|item:021081"
    }:
        raise ValueError("The 24th material must be upstream 021081 at SDC-1450")
    return ordered


def validate_source_contract(
    *,
    graph: Path,
    engine: Path,
    supplier_floors: Path,
    old_profile: Path,
    new_profile: Path,
) -> dict[str, Any]:
    paths = (graph, engine, supplier_floors, old_profile, new_profile)
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise FileNotFoundError(
            "Every comparison input must be a regular, non-symlink file"
        )
    old_args = profile_args(old_profile)
    new_args = profile_args(new_profile)
    retained, removed = split_static_overrides(old_args)
    old_base, old_dynamic = split_dynamic_overrides(retained)
    new_without_static, new_removed = split_static_overrides(new_args)
    new_base, new_dynamic = split_dynamic_overrides(new_without_static)
    graph_payload = read_json(graph)
    materials = material_scope(graph_payload, removed)
    material_pair_keys = tuple(row.pair_key for row in materials)
    if (
        len(removed) != 23
        or old_dynamic
        or new_removed
        or new_base != old_base
        or set(new_dynamic) != set(material_pair_keys)
        or len(new_dynamic) != 24
    ):
        raise ValueError(
            "Candidate profile must remove 23 static overrides, add the exact 24 dynamic material pairs, and preserve every other argument in order"
        )
    floors = read_csv(supplier_floors)
    if not floors:
        raise ValueError("Prepared physical supplier-floor file is empty")
    return {
        "paths": {
            "graph": str(graph.resolve()),
            "engine": str(engine.resolve()),
            "supplier_floors": str(supplier_floors.resolve()),
            "old_profile": str(old_profile.resolve()),
            "new_profile": str(new_profile.resolve()),
        },
        "sha256": {
            "graph": sha256_file(graph),
            "engine": sha256_file(engine),
            "supplier_floors": sha256_file(supplier_floors),
            "old_profile": sha256_file(old_profile),
            "new_profile": sha256_file(new_profile),
        },
        "old_args": old_args,
        "new_args": new_args,
        "removed_static_pairs": list(removed),
        "added_dynamic_pairs": list(new_dynamic),
        "materials": materials,
    }


ACTIVE_CAMPAIGN_IDENTITY_FIELDS = (
    "schema_version",
    "runner_signature",
    "plan_signature",
    "runner_script_sha256",
    "planner_script_sha256",
    "plan_manifest_sha256",
    "source_campaign_manifest_sha256",
    "checkpoint_after_repetitions",
    "mode",
    "scenario_id",
    "contract_revision",
    "source_dir",
    "plan_dir",
)


def read_json_snapshot(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload, hashlib.sha256(raw).hexdigest()


def capture_active_campaign_identity(active_campaign_dir: Path) -> dict[str, Any]:
    """Capture the stable identity and the mutable state of the named V3 campaign."""

    directory = active_campaign_dir.resolve()
    if not directory.is_dir() or directory.is_symlink():
        raise FileNotFoundError(f"Active V3 campaign directory missing: {directory}")
    manifest_path = directory / ACTIVE_CAMPAIGN_MANIFEST_FILE
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise FileNotFoundError(f"Active V3 campaign manifest missing: {manifest_path}")
    manifest, manifest_sha256 = read_json_snapshot(manifest_path)
    identity = {field: manifest.get(field) for field in ACTIVE_CAMPAIGN_IDENTITY_FIELDS}
    if (
        identity.get("schema_version")
        != "etudecas.supplier_network_post_priority_extension_runner.v1"
        or any(
            value in (None, "")
            for field, value in identity.items()
            if field != "checkpoint_after_repetitions"
        )
        or not isinstance(identity.get("checkpoint_after_repetitions"), int)
        or int(identity["checkpoint_after_repetitions"]) <= 0
    ):
        raise ValueError("Active V3 campaign identity fields are incomplete")
    return {
        "path": str(directory),
        "manifest_file": ACTIVE_CAMPAIGN_MANIFEST_FILE,
        "identity": identity,
        "identity_signature": stable_sha256(identity),
        "manifest_sha256_at_capture": manifest_sha256,
        "status_at_capture": str(manifest.get("status") or ""),
        "active_process_id_at_capture": manifest.get("active_process_id"),
    }


def validate_capacity_coupling_audit(
    capacity_audit_dir: Path,
    *,
    source: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the additive analytical audit that proves the comparison coupling."""

    directory = capacity_audit_dir.resolve()
    if not directory.is_dir() or directory.is_symlink():
        raise FileNotFoundError(
            f"Capacity-coupling audit directory missing: {directory}"
        )
    audit_path = directory / CAPACITY_AUDIT_FILE
    if not audit_path.is_file() or audit_path.is_symlink():
        raise FileNotFoundError(f"Capacity-coupling audit missing: {audit_path}")
    audit = read_json(audit_path)
    files = audit.get("files") or {}
    expected_files = {
        "RAPPORT_COUPLAGE_BESOINS_CAPACITES.md",
        "requirement_pair_scope.csv",
        CAPACITY_AUDIT_FROZEN_SUPPLIER_PARAMETERS_FILE,
        "supplier_capacity_coupling_rows.csv",
    }
    if (
        audit.get("schema_version") != "etudecas.dynamic_capacity_coupling_audit.v2"
        or audit.get("status") != "analytical_pre_smoke_not_simulated"
        or set(files) != expected_files
        or (audit.get("interpretation") or {}).get(
            "mrp_only_causal_attribution_allowed"
        )
        is not False
    ):
        raise ValueError("Capacity-coupling audit contract mismatch")
    for filename in sorted(expected_files):
        path = directory / filename
        if (
            not path.is_file()
            or path.is_symlink()
            or sha256_file(path) != str(files.get(filename) or "")
        ):
            raise ValueError(f"Capacity-coupling audit file changed: {filename}")
    audit_sources = audit.get("source_inputs") or {}
    expected_source_keys = {
        "graph": "graph",
        "current_floors": "supplier_floors",
        "old_profile": "old_profile",
        "new_profile": "new_profile",
    }
    for audit_key, source_key in expected_source_keys.items():
        record = audit_sources.get(audit_key) or {}
        if Path(str(record.get("path") or "")).resolve() != Path(
            str(source["paths"][source_key])
        ).resolve() or str(record.get("sha256") or "") != str(
            source["sha256"][source_key]
        ):
            raise ValueError(
                f"Capacity-coupling audit source differs from protocol: {audit_key}"
            )
    supplier_parameters = audit_sources.get("supplier_parameters") or {}
    supplier_parameters_path = Path(str(supplier_parameters.get("path") or ""))
    if (
        not supplier_parameters_path.is_absolute()
        or not supplier_parameters_path.is_file()
        or supplier_parameters_path.is_symlink()
        or supplier_parameters_path.resolve()
        != (directory / CAPACITY_AUDIT_FROZEN_SUPPLIER_PARAMETERS_FILE).resolve()
        or supplier_parameters.get("internal_snapshot") is not True
        or sha256_file(supplier_parameters_path)
        != str(supplier_parameters.get("sha256") or "")
        or (audit.get("source_retention") or {}).get(
            "validation_depends_on_internal_snapshot_only"
        )
        is not True
        or (audit.get("supplier_parameter_origin") or {}).get(
            "validation_dependency"
        )
        is not False
        or str((audit.get("supplier_parameter_origin") or {}).get("sha256") or "")
        != str(supplier_parameters.get("sha256") or "")
    ):
        raise ValueError("Capacity-coupling audit immutable supplier snapshot changed")
    counts = audit.get("counts") or {}
    if (
        int(counts.get("supplier_lanes_in_changed_requirement_scope") or 0) <= 0
        or int(counts.get("estimated_changed_direct_capacities") or 0) <= 0
        or int(counts.get("estimated_changed_upstream_capacities") or 0) <= 0
    ):
        raise ValueError("Capacity-coupling audit does not demonstrate the coupling")
    return {
        "directory": str(directory),
        "audit_file": str(audit_path.resolve()),
        "audit_sha256": sha256_file(audit_path),
        "schema_version": audit["schema_version"],
        "status": audit["status"],
        "counts": counts,
        "interpretation": audit["interpretation"],
        "supplier_parameters_source": {
            "path": str(supplier_parameters_path.resolve()),
            "sha256": str(supplier_parameters["sha256"]),
            "meaning": str(supplier_parameters.get("meaning") or ""),
            "internal_snapshot": True,
            "original_path": str(
                (audit.get("supplier_parameter_origin") or {}).get("path") or ""
            ),
        },
        "files": {key: files[key] for key in sorted(files)},
    }


def _signature_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest.get("schema_version"),
        "status": manifest.get("status"),
        "source_inputs": manifest.get("source_inputs"),
        "variants": manifest.get("variants"),
        "execution": manifest.get("execution"),
        "active_campaign_binding": manifest.get("active_campaign_binding"),
        "capacity_coupling_audit": manifest.get("capacity_coupling_audit"),
        "material_scope": manifest.get("material_scope"),
        "metrics": manifest.get("metrics"),
        "files": manifest.get("files"),
        "interpretation_limits": manifest.get("interpretation_limits"),
    }


def build_protocol(
    *,
    graph: Path,
    engine: Path,
    supplier_floors: Path,
    old_profile: Path,
    new_profile: Path,
    output_dir: Path,
    active_campaign_dir: Path = DEFAULT_ACTIVE_CAMPAIGN_DIR,
    capacity_audit_dir: Path = DEFAULT_CAPACITY_AUDIT_DIR,
) -> dict[str, Any]:
    source = validate_source_contract(
        graph=graph.resolve(),
        engine=engine.resolve(),
        supplier_floors=supplier_floors.resolve(),
        old_profile=old_profile.resolve(),
        new_profile=new_profile.resolve(),
    )
    active_campaign_binding = capture_active_campaign_identity(active_campaign_dir)
    if (
        active_campaign_binding["identity"].get("checkpoint_after_repetitions")
        != BOUND_CAMPAIGN_CHECKPOINT_AFTER_REPETITIONS
    ):
        raise ValueError("The bound V3 campaign must stop after 15 repetitions")
    capacity_coupling_audit = validate_capacity_coupling_audit(
        capacity_audit_dir,
        source=source,
    )
    output_dir = output_dir.resolve()
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError("Protocol output directory must be new and empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    materials: tuple[Material, ...] = source["materials"]
    material_rows = [
        {
            **asdict(row),
            "pair_key": row.pair_key,
        }
        for row in materials
    ]
    write_csv_atomic(output_dir / MATERIAL_SCOPE_FILE, material_rows)
    profile_audit = {
        "schema_version": f"{SCHEMA_VERSION}.profile_change_audit",
        "old_profile": source["paths"]["old_profile"],
        "old_profile_sha256": source["sha256"]["old_profile"],
        "new_profile": source["paths"]["new_profile"],
        "new_profile_sha256": source["sha256"]["new_profile"],
        "only_changes": [
            "remove_explicit_mrp_static_requirement_pair_flags_and_values",
            "add_explicit_mrp_dynamic_requirement_pair_flags_for_all_24_materials",
        ],
        "removed_static_pair_count": len(source["removed_static_pairs"]),
        "removed_static_pairs": source["removed_static_pairs"],
        "all_other_non_mode_arguments_identical_and_order_preserved": True,
        "old_resolved_static_pair_count_after_managed_dynamic_overrides": 21,
        "new_resolved_static_pair_count_after_managed_dynamic_overrides": 0,
        "old_explicit_dynamic_pairs_after_managed_arguments": list(
            EXPLICIT_DYNAMIC_PAIRS
        ),
        "new_explicit_dynamic_pair_count_after_managed_arguments": 24,
        "new_explicit_dynamic_pairs_after_managed_arguments": [
            row.pair_key for row in materials
        ],
    }
    write_json_atomic(output_dir / PROFILE_AUDIT_FILE, profile_audit)
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "planned_not_executed",
        "created_at_utc": utc_now(),
        "source_inputs": {
            key: {"path": source["paths"][key], "sha256": source["sha256"][key]}
            for key in (
                "graph",
                "engine",
                "supplier_floors",
                "old_profile",
                "new_profile",
            )
        },
        "active_campaign_binding": active_campaign_binding,
        "capacity_coupling_audit": capacity_coupling_audit,
        "variants": [
            {
                "variant_id": OLD_VARIANT_ID,
                "profile_key": "old_profile",
                "meaning": "reference currently used; 21 of 24 material requirements remain explicitly static after the three managed dynamic overrides",
            },
            {
                "variant_id": NEW_VARIANT_ID,
                "profile_key": "new_profile",
                "meaning": "candidate to evaluate; all 24 material pairs are explicitly dynamic, which changes local requirements and can also change inferred direct supplier capacities and upstream procurement policy/capacity",
            },
        ],
        "execution": {
            "scenario_id": "scn:BASE",
            "measured_days": MEASURED_DAYS,
            "warmup_days": WARMUP_DAYS,
            "common_random_numbers": True,
            "supplier_incident_loaded": False,
            "supplier_state_dependent_risks_enabled": False,
            "smoke_seeds": list(SMOKE_SEEDS),
            "comparison_seeds": list(COMPARISON_SEEDS),
            "smoke_output_reusable_for_comparison": False,
            "lot_trace_seed": LOT_TRACE_SEED,
            "lot_trace_scope": "one paired seed in both variants; structural check, not 15-seed lot statistics",
            "managed_protocol_args": list(MANAGED_PROTOCOL_ARGS),
            "run_only_after_active_v3_is_paused_or_complete": True,
            "bound_active_campaign_identity_signature": active_campaign_binding[
                "identity_signature"
            ],
            "comparison_type": (
                "coupled_diagnostic_requirements_direct_supplier_capacity_"
                "and_upstream_procurement_policy"
            ),
            "isolates_mrp_only": False,
        },
        "material_scope": {
            "count": len(materials),
            "pair_keys": [row.pair_key for row in materials],
            "direct_factory_material_count": 23,
            "upstream_material_count": 1,
            "upstream_material_pair": "SDC-1450|item:021081",
        },
        "metrics": {
            "system": [
                "client_on_due_service_by_product",
                "client_fill_rate_by_product",
                "client_backlog_quantity_days_by_product",
                "released_production_by_product",
            ],
            "each_of_24_materials": [
                "consumption_total_and_daily_mean",
                "stock_at_J0",
                "minimum_and_mean_end_of_day_stock",
                "zero_stock_days",
                "mrp_order_count_and_quantity",
                "arrival_days_and_quantity",
                "mean_mrp_target_stock",
                "median_p95_and_max_mrp_target_stock",
                "median_p95_and_max_dynamic_requirement_signal",
                "mean_target_to_daily_consumption_ratio_in_days",
                "dynamic_requirement_signal_to_consumption_ratio_and_0p5_2_diagnostic_band",
                "J0_stock_cover_days_or_explicit_zero_consumption_status",
                "J0_pipeline_quantity_and_cover_status",
                "day0_boundary_arrival_quantity_already_included_in_J0_stock",
                "future_supplier_lane_shipment_count_and_quantity",
                "supplier_risk_flow_evaluability",
                "supplier_ids_and_capacity_bases",
                "direct_nominal_and_effective_capacity_totals",
                "applied_capacity_scale_minimum_and_maximum",
                "downstream_requirement_and_signal_pair_values_with_lane_equality_check",
                "downstream_requirement_and_signal_lane_row_sums_explicitly_labelled",
                "external_procurement_daily_need_capacity_and_pipeline_totals",
            ],
        },
        "files": {
            MATERIAL_SCOPE_FILE: sha256_file(output_dir / MATERIAL_SCOPE_FILE),
            PROFILE_AUDIT_FILE: sha256_file(output_dir / PROFILE_AUDIT_FILE),
        },
        "interpretation_limits": {
            "observed_supplier_probability": False,
            "supplier_ranking_allowed": False,
            "industrial_recommendation_allowed": False,
            "causal_change_under_test": (
                "coupled diagnostic: dynamic requirement construction plus direct "
                "supplier capacities and upstream procurement capacity/policy inferred "
                "from those requirements"
            ),
            "isolates_mrp_only": False,
            "direct_supplier_capacities_held_constant": False,
            "upstream_procurement_capacities_and_policies_held_constant": False,
            "capacity_coupling_is_analytically_demonstrated": True,
            "opening_stock_validated_for_scientific_reference": False,
            "warmup_duration_validated_for_scientific_reference": False,
            "supplier_capacities_validated_for_scientific_reference": False,
            "scientifically_reviewable": False,
            "publishable_results": False,
            "scientific_review_blockers": [
                "opening stocks and pair-level opening pipeline not validated",
                "240-day warmup not compared with a longer stabilization period",
                "supplier capacity scale and inferred upstream capacities not validated",
                "comparison does not isolate the MRP requirement mechanism",
            ],
            "opening_stock_is_not_corrected_by_this_variant": True,
            "J0_pipeline_quantity_evaluable_with_current_engine_exports": False,
            "J0_pipeline_limitation": "the engine exports only a boundary-state digest, not pair-level pipeline quantities; day-0 arrivals are reported separately and are already included in stock-before-production",
            "no_future_lane_flow_rule": "a material with no positive future supplier shipment during J0-J719 is not evaluable for a supplier-risk consequence claim in this comparison",
            "warmup_sensitivity_in_this_protocol": False,
            "warmup_follow_up": "compare 240 versus 605 warmup days only after this 15-seed paired test",
            "service_93_80_calibration_prerequisite": "do not calibrate 93/80 service regimes before assessing this reference variant",
            "existing_V3_context": "current V3 evidence is chiefly decision-informative for 338929 and 344135; weak effects on other lanes are not a supplier ranking",
            "result_files_present": False,
        },
    }
    manifest["protocol_signature"] = stable_sha256(_signature_payload(manifest))
    write_json_atomic(output_dir / PROTOCOL_FILE, manifest)
    return manifest


def _safe_source(manifest: Mapping[str, Any], key: str) -> Path:
    record = (manifest.get("source_inputs") or {}).get(key) or {}
    path = Path(str(record.get("path") or ""))
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(f"Invalid protocol source path: {key}")
    if sha256_file(path) != str(record.get("sha256") or ""):
        raise ValueError(f"Protocol source changed: {key}")
    return path.resolve()


def validate_protocol(protocol_dir: Path) -> ValidatedProtocol:
    protocol_dir = protocol_dir.resolve()
    if not protocol_dir.is_dir() or protocol_dir.is_symlink():
        raise FileNotFoundError(f"Protocol directory missing: {protocol_dir}")
    inventory = {path.name for path in protocol_dir.iterdir() if path.is_file()}
    if inventory != {PROTOCOL_FILE, MATERIAL_SCOPE_FILE, PROFILE_AUDIT_FILE}:
        raise ValueError("Protocol file inventory is not exact")
    manifest = read_json(protocol_dir / PROTOCOL_FILE)
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "planned_not_executed"
    ):
        raise ValueError("Protocol schema/status mismatch")
    signature = str(manifest.get("protocol_signature") or "")
    if not signature or stable_sha256(_signature_payload(manifest)) != signature:
        raise ValueError("Protocol signature mismatch")
    for filename in (MATERIAL_SCOPE_FILE, PROFILE_AUDIT_FILE):
        if sha256_file(protocol_dir / filename) != (manifest.get("files") or {}).get(
            filename
        ):
            raise ValueError(f"Protocol file changed: {filename}")
    graph = _safe_source(manifest, "graph")
    engine = _safe_source(manifest, "engine")
    floors = _safe_source(manifest, "supplier_floors")
    old_profile = _safe_source(manifest, "old_profile")
    new_profile = _safe_source(manifest, "new_profile")
    fresh = validate_source_contract(
        graph=graph,
        engine=engine,
        supplier_floors=floors,
        old_profile=old_profile,
        new_profile=new_profile,
    )
    binding = manifest.get("active_campaign_binding") or {}
    active_campaign_dir = Path(str(binding.get("path") or ""))
    current_binding = capture_active_campaign_identity(active_campaign_dir)
    if (
        str(binding.get("path") or "") != current_binding["path"]
        or binding.get("manifest_file") != current_binding["manifest_file"]
        or binding.get("identity") != current_binding["identity"]
        or binding.get("identity_signature") != current_binding["identity_signature"]
    ):
        raise ValueError("Bound active V3 campaign identity changed")
    capacity_record = manifest.get("capacity_coupling_audit") or {}
    capacity_audit_dir = Path(str(capacity_record.get("directory") or ""))
    fresh_capacity_record = validate_capacity_coupling_audit(
        capacity_audit_dir,
        source=fresh,
    )
    if capacity_record != fresh_capacity_record:
        raise ValueError("Capacity-coupling audit binding changed")
    rows = read_csv(protocol_dir / MATERIAL_SCOPE_FILE)
    expected_materials: tuple[Material, ...] = fresh["materials"]
    if len(rows) != 24 or [row.get("pair_key") for row in rows] != [
        row.pair_key for row in expected_materials
    ]:
        raise ValueError("Material scope rows changed")
    execution = manifest.get("execution") or {}
    if (
        execution.get("measured_days") != MEASURED_DAYS
        or execution.get("warmup_days") != WARMUP_DAYS
        or execution.get("smoke_seeds") != list(SMOKE_SEEDS)
        or execution.get("comparison_seeds") != list(COMPARISON_SEEDS)
        or execution.get("lot_trace_seed") != LOT_TRACE_SEED
        or execution.get("managed_protocol_args") != list(MANAGED_PROTOCOL_ARGS)
        or execution.get("supplier_incident_loaded") is not False
        or execution.get("supplier_state_dependent_risks_enabled") is not False
        or execution.get("bound_active_campaign_identity_signature")
        != current_binding["identity_signature"]
        or execution.get("isolates_mrp_only") is not False
        or current_binding["identity"].get("checkpoint_after_repetitions")
        != BOUND_CAMPAIGN_CHECKPOINT_AFTER_REPETITIONS
    ):
        raise ValueError("Execution contract changed")
    limits = manifest.get("interpretation_limits") or {}
    if (
        limits.get("result_files_present") is not False
        or limits.get("isolates_mrp_only") is not False
        or limits.get("scientifically_reviewable") is not False
        or limits.get("publishable_results") is not False
        or limits.get("direct_supplier_capacities_held_constant") is not False
        or limits.get("upstream_procurement_capacities_and_policies_held_constant")
        is not False
    ):
        raise ValueError("Protocol improperly claims results")
    return ValidatedProtocol(
        protocol_dir=protocol_dir,
        manifest=manifest,
        materials=expected_materials,
        graph=graph,
        engine=engine,
        supplier_floors=floors,
        old_profile=old_profile,
        new_profile=new_profile,
        active_campaign_dir=active_campaign_dir.resolve(),
        capacity_audit_dir=capacity_audit_dir.resolve(),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("build", "validate"), default="build")
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument("--supplier-floors", type=Path, default=DEFAULT_FLOORS)
    parser.add_argument("--old-profile", type=Path, default=DEFAULT_OLD_PROFILE)
    parser.add_argument("--new-profile", type=Path, default=DEFAULT_NEW_PROFILE)
    parser.add_argument(
        "--active-campaign-dir", type=Path, default=DEFAULT_ACTIVE_CAMPAIGN_DIR
    )
    parser.add_argument(
        "--capacity-audit-dir", type=Path, default=DEFAULT_CAPACITY_AUDIT_DIR
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "build":
        payload = build_protocol(
            graph=args.graph,
            engine=args.engine,
            supplier_floors=args.supplier_floors,
            old_profile=args.old_profile,
            new_profile=args.new_profile,
            output_dir=args.output_dir,
            active_campaign_dir=args.active_campaign_dir,
            capacity_audit_dir=args.capacity_audit_dir,
        )
    else:
        validated = validate_protocol(args.output_dir)
        payload = {
            "status": "valid_planned_not_executed",
            "protocol_signature": validated.manifest["protocol_signature"],
            "material_count": len(validated.materials),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
