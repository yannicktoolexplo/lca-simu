#!/usr/bin/env python3
"""Plan and validate post-priority supplier-network extensions.

This module is intentionally non-executable: it never launches the simulation
engine.  It consumes a complete ``supplier_network_risk_screen_campaign``
artifact and writes a separate, signed, non-overwritable plan for the tests
that must follow the lane-by-lane screening:

* one simultaneous severe incident on both lanes of each known multi-lane
  supplier, for the four business causes;
* the retained severe cause on four non-overlapping calendar windows for each
  member of the service non-separation group selected by the boundary audit;
* the four severe business causes on those same follow-up lanes;
* a small, explicitly paired lot-trace subset that separates genealogical
  exposure from a measured counterfactual date or quantity difference.

The generated plan cannot promote a priority by itself.  Promotion requires
separate execution manifests and their scientific controls to pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_IMPORT_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_IMPORT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_risk_screen_campaign as network,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_priority_boundary_audit as boundary,
)


SCHEMA_VERSION = "etudecas.supplier_network_post_priority_extensions.plan.v1"
CONTRACT_REVISION = "setwise_descriptive_postselection_lineage_2026_09"
# Updated only after the boundary implementation has passed its independent
# falsification review.  The final plan path refuses any other implementation.
EXPECTED_PRIORITY_BOUNDARY_BUILDER_SHA256 = (
    "066e6a9046c17325b068641d9803d3857618168cbaa3439732972a41b1bb7f15"
)
EXPECTED_MULTI_LANE_SUPPLIERS = (
    "SDC-VD0519670A",
    "SDC-VD0520132A",
)
CALENDAR_WINDOWS = (
    (0, 179),
    (180, 359),
    (360, 539),
    (540, 719),
)
FULL_PAIRED_SEED_COUNT = 30
BOUNDARY_DISPLAY_SET_SIZE = 3
CAUSAL_LOT_SEED_COUNT = 1
BASE_SIMULATION_DAYS = 720
TEMPORAL_SEVERE_DATE_SHIFT_DAYS = 120
TEMPORAL_FIXED_FOLLOWUP_DAYS = 120
EXTENDED_HORIZON_INPUT_POLICY = (
    "explicit_annual_cycle_repeat_from_365_day_observed_demand_profile"
)
BOUNDARY_MANIFEST = "priority_boundary_audit_manifest.json"
BOUNDARY_RESULT = "scientific_priority_boundary_audit.json"
BOUNDARY_RANKING = "supplier_metric_rankings.csv"
BOUNDARY_FILES = (*boundary.OUTPUT_FILES, BOUNDARY_MANIFEST)

REQUIRED_SOURCE_FILES = (
    "campaign_manifest.json",
    "active_lane_reference.csv",
    "confirmation_metrics.csv",
    "confirmation_lane_sensitivity_ranking.csv",
    "scenario_design.csv",
    "multi_lane_supplier_common_cause_design.csv",
    "temporal_robustness_extension_design.csv",
    "priority_severe_mode_extension_design.csv",
    "post_priority_extensions_manifest.json",
)

PLAN_FILES = (
    "paired_baseline_design.csv",
    "multi_lane_supplier_common_cause_design.csv",
    "temporal_robustness_design.csv",
    "priority_four_business_causes_design.csv",
    "causal_lot_attribution_design.csv",
    "promotion_controls.json",
    "post_priority_extensions_plan_manifest.json",
    "PLAN.md",
)
IMMUTABLE_PLAN_FILES = tuple(
    name for name in PLAN_FILES if name != "post_priority_extensions_plan_manifest.json"
)


@dataclass(frozen=True)
class SourceContext:
    artifact_dir: Path
    manifest: Mapping[str, Any]
    source_hashes: Mapping[str, str]
    seeds: tuple[int, ...]
    active_lanes: tuple[Mapping[str, str], ...]
    priorities: tuple[Mapping[str, str], ...]
    severe_scenarios: Mapping[tuple[str, str], Mapping[str, str]]
    common_windows: Mapping[str, tuple[int, int]]
    source_gate_state: Mapping[str, bool]
    baseline_by_seed: Mapping[int, Mapping[str, str]]
    confirmation_by_scenario_seed: Mapping[tuple[str, int], Mapping[str, str]]
    priority_boundary_dir: Path | None = None
    priority_selection_lineage: Mapping[str, Any] | None = None
    temporal_horizon: Mapping[str, Any] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(value: Any, default: int = 0) -> int:
    return network.campaign_core.to_int(value, default)


def _to_float(value: Any, default: float = 0.0) -> float:
    return network.campaign_core.to_float(value, default)


def _as_bool(value: Any) -> bool:
    return network.campaign_core.as_bool(value)


def _read_csv(path: Path) -> list[dict[str, str]]:
    return network.campaign_core.read_csv_rows(path)


def _read_json(path: Path) -> dict[str, Any]:
    return network.campaign_core.read_json(path)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Le plan refuse un CSV vide: {path.name}")
    network.campaign_core.write_csv_atomic(path, rows)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    network.campaign_core.write_json_atomic(path, payload)


def _sha256(path: Path) -> str:
    return network.campaign_core.sha256_file(path)


def _canonical_signature(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _lineage_digest(payload: Mapping[str, Any]) -> str:
    return _canonical_signature(
        {
            key: value
            for key, value in payload.items()
            if key != "priority_selection_lineage_sha256"
        }
    )


def _required_source_paths(artifact_dir: Path) -> dict[str, Path]:
    paths = {name: artifact_dir / name for name in REQUIRED_SOURCE_FILES}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Le dossier réseau complet ne contient pas: " + ", ".join(missing)
        )
    return paths


def _source_hashes(paths: Mapping[str, Path]) -> dict[str, str]:
    return {name: _sha256(path) for name, path in sorted(paths.items())}


def _exact_file_inventory(root: Path, expected: Sequence[str], *, label: str) -> None:
    observed_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    observed_dirs = [path for path in root.rglob("*") if path.is_dir()]
    expected_set = set(expected)
    if observed_files != expected_set or observed_dirs:
        raise ValueError(
            f"Inventaire {label} non exact: "
            f"missing={sorted(expected_set - observed_files)}, "
            f"extra={sorted(observed_files - expected_set)}, "
            f"dirs={[path.relative_to(root).as_posix() for path in observed_dirs]}"
        )


def _validate_and_recompute_boundary(
    *, network_artifact: Path, boundary_dir: Path
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    """Validate, then independently rebuild the compact priority boundary.

    The package digests are integrity checks, not authenticated signatures.  A
    byte-for-byte deterministic rebuild from the closed campaign is therefore
    required before an expensive extension plan can be emitted.
    """

    boundary_dir = boundary_dir.resolve()
    _exact_file_inventory(boundary_dir, BOUNDARY_FILES, label="boundary")
    builder_sha = _sha256(Path(boundary.__file__).resolve())
    if builder_sha != EXPECTED_PRIORITY_BOUNDARY_BUILDER_SHA256:
        raise ValueError(
            "Implémentation boundary non revue: "
            f"attendu={EXPECTED_PRIORITY_BOUNDARY_BUILDER_SHA256}, obtenu={builder_sha}"
        )
    validation = boundary.validate_audit_package(boundary_dir)
    if not _as_bool(validation.get("valid")):
        raise ValueError("Le paquet boundary n'est pas valide.")
    manifest = _read_json(boundary_dir / BOUNDARY_MANIFEST)
    if str(manifest.get("builder_sha256") or "") != builder_sha:
        raise ValueError("Le manifeste boundary ne référence pas le builder revu.")
    source_hashes = manifest.get("source_file_sha256") or {}
    expected_source_paths = boundary._source_inputs(network_artifact)  # noqa: SLF001
    expected_source_hashes = {
        name: _sha256(path) for name, path in sorted(expected_source_paths.items())
    }
    if source_hashes != expected_source_hashes:
        raise ValueError("La boundary ne provient pas exactement de la campagne fournie.")

    temporary = Path(
        tempfile.mkdtemp(
            prefix=".boundary-recompute-", dir=boundary_dir.parent
        )
    )
    rebuilt = temporary / "rebuilt"
    try:
        boundary.build_audit_package(
            network_dir=network_artifact,
            output_dir=rebuilt,
        )
        boundary.validate_audit_package(rebuilt)
        for name in boundary.OUTPUT_FILES:
            if (boundary_dir / name).read_bytes() != (rebuilt / name).read_bytes():
                raise ValueError(
                    "Boundary auto-cohérente mais non reproductible depuis les sources: "
                    f"{name}"
                )
    finally:
        resolved = temporary.resolve()
        if resolved.parent == boundary_dir.parent.resolve() and resolved.name.startswith(
            ".boundary-recompute-"
        ):
            shutil.rmtree(resolved)
    audit = _read_json(boundary_dir / BOUNDARY_RESULT)
    rankings = _read_csv(boundary_dir / BOUNDARY_RANKING)
    return manifest, audit, rankings


def _scientific_source_gates(manifest: Mapping[str, Any]) -> dict[str, bool]:
    gates = manifest.get("scientific_release_gates") or {}
    baseline = _as_bool(
        gates.get("baseline_both_products_on_due_at_least_95_all_seeds_pass")
    ) or _as_bool(manifest.get("baseline_service_gate_pass"))
    metric_valid = _as_bool(gates.get("all_metric_rows_valid_pass"))
    j0 = _as_bool(gates.get("j0_state_hash_pairing_100pct_pass"))
    graph = _as_bool(gates.get("input_graph_hash_pairing_100pct_pass"))
    paired = metric_valid and j0 and graph
    if not gates:
        paired = _as_bool(manifest.get("pairing_integrity_gate_pass"))
    active_flow = _as_bool(
        gates.get(
            "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass"
        )
    ) or _as_bool(manifest.get("active_lane_flow_gate_pass"))
    all_main = _as_bool(gates.get("all_release_gates_pass"))
    if not gates:
        all_main = baseline and paired and active_flow
    return {
        "baseline_service_all_30_pass": baseline,
        "paired_inputs_and_j0_all_rows_pass": paired,
        "active_lane_flow_at_least_29_of_30_pass": active_flow,
        "all_main_scientific_release_gates_pass": all_main,
        "main_priority_set_stabilized": _as_bool(
            manifest.get("priority_set_stabilized")
        ),
        "rank3_rank4_separated": _as_bool(
            manifest.get("rank3_rank4_interval_separated")
        ),
    }


def _load_confirmation_rows(
    path: Path,
) -> tuple[
    tuple[int, ...],
    dict[int, Mapping[str, str]],
    dict[tuple[str, int], Mapping[str, str]],
]:
    rows = _read_csv(path)
    baselines = [
        row
        for row in rows
        if str(row.get("scenario_id") or "") == "baseline_nominal"
    ]
    seeds = tuple(sorted({_to_int(row.get("seed"), -1) for row in baselines}))
    if len(seeds) != FULL_PAIRED_SEED_COUNT or any(seed < 0 for seed in seeds):
        raise ValueError(
            "Le résultat réseau doit contenir exactement 30 références appariées."
        )
    if len(baselines) != FULL_PAIRED_SEED_COUNT:
        raise ValueError("Une et une seule référence est requise par graine.")
    missing_trace_contract = [
        row
        for row in rows
        if "lot_trace_required_for_paired_seed_block" not in row
    ]
    if missing_trace_contract:
        raise ValueError(
            "Le résultat réseau doit expliciter le réglage de traçage lots de "
            "chaque bloc apparié."
        )
    by_seed = {_to_int(row.get("seed"), -1): dict(row) for row in baselines}
    by_case: dict[tuple[str, int], Mapping[str, str]] = {}
    for row in rows:
        scenario_id = str(row.get("scenario_id") or "")
        seed = _to_int(row.get("seed"), -1)
        if not scenario_id or seed < 0:
            continue
        key = (scenario_id, seed)
        if key in by_case:
            raise ValueError(f"Cas de confirmation dupliqué: {key}")
        by_case[key] = dict(row)
    return seeds, by_seed, by_case


def _load_active_lanes(path: Path) -> tuple[Mapping[str, str], ...]:
    rows = _read_csv(path)
    required = {
        "chain_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "target_product_id",
        "active_window_start_day",
        "active_window_end_day",
    }
    if not rows or any(not required.issubset(row) for row in rows):
        raise ValueError("Référentiel des voies actives incomplet.")
    chain_ids = [str(row.get("chain_id") or "") for row in rows]
    if not all(chain_ids) or len(set(chain_ids)) != len(chain_ids):
        raise ValueError("Les identifiants de voie active doivent être uniques.")
    return tuple(dict(row) for row in rows)


def _load_priorities(
    path: Path, active_by_chain: Mapping[str, Mapping[str, str]]
) -> tuple[Mapping[str, str], ...]:
    rows = sorted(
        _read_csv(path),
        key=lambda row: _to_int(row.get("lane_sensitivity_rank"), 10**9),
    )
    if len(rows) < BOUNDARY_DISPLAY_SET_SIZE + 1:
        raise ValueError(
            "Au moins quatre voies sont requises pour distinguer les rangs 3 et 4."
        )
    ranks = [_to_int(row.get("lane_sensitivity_rank"), -1) for row in rows]
    if ranks[:4] != [1, 2, 3, 4]:
        raise ValueError("Les quatre premiers rangs de voie doivent être 1, 2, 3, 4.")
    priorities: list[dict[str, str]] = []
    for row in rows[:BOUNDARY_DISPLAY_SET_SIZE]:
        chain_id = str(row.get("chain_id") or "")
        if chain_id not in active_by_chain:
            raise ValueError(f"Voie prioritaire absente du référentiel actif: {chain_id}")
        merged = dict(active_by_chain[chain_id])
        merged.update(row)
        priorities.append(merged)
    return tuple(priorities)


def _load_severe_scenarios(
    path: Path,
) -> dict[tuple[str, str], Mapping[str, str]]:
    rows = _read_csv(path)
    severe: dict[tuple[str, str], Mapping[str, str]] = {}
    for row in rows:
        if str(row.get("level_code") or "") != "severe":
            continue
        key = (
            str(row.get("chain_id") or ""),
            str(row.get("failure_mode") or ""),
        )
        if not all(key):
            continue
        if key in severe:
            raise ValueError(f"Scénario sévère dupliqué: {key}")
        severe[key] = dict(row)
    return severe


def _unique_sorted_ids(values: Sequence[Any], *, label: str) -> list[str]:
    ids = [str(value).strip() for value in values if str(value).strip()]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Identifiants dupliqués dans {label}.")
    return sorted(ids)


def _boundary_priority_selection(
    *,
    artifact_dir: Path,
    boundary_dir: Path,
    source_manifest: Mapping[str, Any],
    active_lanes: Sequence[Mapping[str, str]],
    severe_scenarios: Mapping[tuple[str, str], Mapping[str, str]],
) -> tuple[tuple[Mapping[str, str], ...], dict[str, Any]]:
    boundary_manifest, audit, rankings = _validate_and_recompute_boundary(
        network_artifact=artifact_dir,
        boundary_dir=boundary_dir,
    )
    if str(audit.get("schema_version") or "") != boundary.SCHEMA_VERSION:
        raise ValueError("Version scientifique boundary absente ou obsolète.")
    display_allowed = _as_bool(
        audit.get("scoped_descriptive_priority_set_display_allowed")
    )
    displayed_ids = _unique_sorted_ids(
        audit.get("displayed_scoped_priority_supplier_ids") or (),
        label="displayed scoped priority suppliers",
    )
    nonseparation_ids = _unique_sorted_ids(
        audit.get("envelope_service_nonseparation_group_supplier_ids") or (),
        label="service nonseparation group",
    )
    universal_group = _unique_sorted_ids(
        audit.get("priority_group_supplier_ids_if_no_universal_top3") or (),
        label="universal ambiguity group",
    )
    boundary_driver_rows = audit.get("envelope_service_driver_mappings") or []
    if not isinstance(boundary_driver_rows, list):
        raise ValueError("Les cibles de suivi boundary sont absentes ou invalides.")
    boundary_driver_by_supplier = {
        str(row.get("supplier_id") or ""): dict(row)
        for row in boundary_driver_rows
        if isinstance(row, Mapping)
    }
    if (
        len(boundary_driver_by_supplier) != len(boundary_driver_rows)
        or set(boundary_driver_by_supplier)
        != set((audit.get("supplier_lane_count_by_id") or {}).keys())
    ):
        raise ValueError(
            "Les cibles de suivi boundary ne couvrent pas exactement les fournisseurs."
        )
    if display_allowed:
        if len(displayed_ids) != BOUNDARY_DISPLAY_SET_SIZE:
            raise ValueError("Le signal service affichable doit contenir exactement trois fournisseurs.")
        candidate_pool = displayed_ids
        selected_suppliers = displayed_ids
        selection_status = "scoped_descriptive_service_set"
        provisional_rule = "none"
        follow_up_rule = "complete_displayed_service_set_canonical_supplier_id_order"
    else:
        candidate_pool = nonseparation_ids
        if len(candidate_pool) < BOUNDARY_DISPLAY_SET_SIZE:
            raise ValueError("Le groupe service provisoire contient moins de trois fournisseurs.")
        selected_suppliers = candidate_pool
        selection_status = "complete_service_nonseparation_group_follow_up"
        provisional_rule = "none"
        follow_up_rule = (
            "all_group_members_canonical_supplier_id_order_not_scientific_rank"
        )

    service_rows = [
        row
        for row in rankings
        if str(row.get("aggregation_scope") or "")
        == boundary.SUPPLIER_ENVELOPE_SCOPE
        and str(row.get("metric_key") or "")
        == "horizon_on_due_service_delta"
    ]
    by_supplier = {str(row.get("supplier_id") or ""): row for row in service_rows}
    if len(by_supplier) != _to_int(source_manifest.get("distinct_supplier_count"), -1):
        raise ValueError("Le classement service boundary ne couvre pas tous les fournisseurs.")
    active_by_chain = {
        str(row.get("chain_id") or ""): dict(row) for row in active_lanes
    }
    mappings: list[dict[str, Any]] = []
    priorities: list[dict[str, str]] = []
    for slot, supplier_id in enumerate(selected_suppliers, 1):
        rank_row = by_supplier.get(supplier_id)
        boundary_mapping = boundary_driver_by_supplier.get(supplier_id)
        if rank_row is None:
            raise ValueError(f"Fournisseur sélectionné absent du classement service: {supplier_id}")
        if boundary_mapping is None:
            raise ValueError(f"Cible de suivi boundary absente: {supplier_id}")
        chain_id = str(boundary_mapping.get("driver_chain_id") or "")
        scenario_id = str(boundary_mapping.get("driver_scenario_id") or "")
        failure_mode = str(boundary_mapping.get("driver_failure_mode") or "")
        if any(
            str(rank_row.get(field) or "")
            != str(boundary_mapping.get(field) or "")
            for field in (
                "supplier_id",
                "driver_chain_id",
                "driver_scenario_id",
                "driver_failure_mode",
            )
        ):
            raise ValueError(f"Classement et cibles boundary divergent: {supplier_id}")
        if (
            _as_bool(boundary_mapping.get("driver_lane_uniqueness_claimed"))
            or str(boundary_mapping.get("driver_selection_rule") or "")
            != "worst_mean_service_scenario_then_identifier_tie_break"
        ):
            raise ValueError(f"Sémantique de cible boundary inconnue: {supplier_id}")
        lane = active_by_chain.get(chain_id)
        scenario = severe_scenarios.get((chain_id, failure_mode))
        if lane is None or scenario is None:
            raise ValueError(f"Cible de suivi boundary inconnue: {supplier_id}/{chain_id}/{failure_mode}")
        if (
            str(lane.get("supplier_id") or "") != supplier_id
            or str(scenario.get("scenario_id") or "") != scenario_id
            or str(scenario.get("supplier_id") or "") != supplier_id
            or str(scenario.get("item_id") or "") != str(lane.get("item_id") or "")
            or str(scenario.get("dst_node_id") or "") != str(lane.get("dst_node_id") or "")
        ):
            raise ValueError(f"Lignée supplier/voie/scénario boundary incohérente: {supplier_id}")
        mapping = {
            "selection_slot": slot,
            "supplier_id": supplier_id,
            "driver_chain_id": chain_id,
            "driver_scenario_id": scenario_id,
            "driver_failure_mode": failure_mode,
            "driver_lane_uniqueness_claimed": False,
            "driver_selection_rule": "worst_mean_service_scenario_then_identifier_tie_break",
        }
        mappings.append(mapping)
        merged = dict(lane)
        merged.update(
            {
                "selection_slot": str(slot),
                "priority_selection_slot": str(slot),
                "supplier_id": supplier_id,
                "chain_id": chain_id,
                "driver_scenario_id": scenario_id,
                "worst_scenario_id": scenario_id,
                "driver_failure_mode": failure_mode,
                "worst_failure_mode": failure_mode,
                "driver_lane_uniqueness_claimed": "False",
                "slot_order_has_scientific_meaning": "False",
                "priority_selection_status": selection_status,
            }
        )
        priorities.append(merged)

    if len({row["driver_chain_id"] for row in mappings}) != len(selected_suppliers):
        raise ValueError("Les cibles de suivi doivent être des voies distinctes.")
    lane_counts: dict[str, int] = {}
    active_chain_ids_by_supplier: dict[str, list[str]] = {}
    for lane in active_lanes:
        supplier = str(lane.get("supplier_id") or "")
        lane_counts[supplier] = lane_counts.get(supplier, 0) + 1
        chain_id = str(lane.get("chain_id") or "")
        if supplier and chain_id:
            active_chain_ids_by_supplier.setdefault(supplier, []).append(chain_id)
    all_multi_lane_supplier_ids = sorted(
        supplier for supplier, count in lane_counts.items() if count > 1
    )
    all_multi_lane_supplier_active_chain_ids_by_id = {
        supplier: sorted(set(active_chain_ids_by_supplier[supplier]))
        for supplier in all_multi_lane_supplier_ids
    }
    source_manifest_sha = _sha256(artifact_dir / "campaign_manifest.json")
    source_campaign_signature = str(source_manifest.get("campaign_signature") or "")
    lineage: dict[str, Any] = {
        "schema_version": "etudecas.supplier_network_priority_selection_lineage.v1",
        "contract_revision": CONTRACT_REVISION,
        "priority_boundary_dir": str(boundary_dir.resolve()),
        "priority_boundary_package_signature": str(
            boundary_manifest.get("package_signature") or ""
        ),
        "priority_boundary_manifest_sha256": _sha256(
            boundary_dir / BOUNDARY_MANIFEST
        ),
        "priority_boundary_result_sha256": _sha256(boundary_dir / BOUNDARY_RESULT),
        "priority_boundary_ranking_sha256": _sha256(boundary_dir / BOUNDARY_RANKING),
        "priority_boundary_builder_sha256": str(
            boundary_manifest.get("builder_sha256") or ""
        ),
        "priority_boundary_schema_version": str(audit.get("schema_version") or ""),
        "priority_boundary_manifest_schema_version": str(
            boundary_manifest.get("schema_version") or ""
        ),
        "source_campaign_manifest_sha256": source_manifest_sha,
        "source_campaign_signature": source_campaign_signature,
        "priority_selection_scope": boundary.SUPPLIER_ENVELOPE_SCOPE,
        "priority_selection_metric": "horizon_on_due_service_delta",
        "primary_selection_metric_predeclared": True,
        "priority_selection_status": selection_status,
        "legacy_service_release_aliases_used": False,
        "envelope_service_priority_set_release_pass": False,
        "scoped_descriptive_priority_set_display_allowed": display_allowed,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "priority_set_evidence": "signal_descriptif_conditionnel_30_tirages",
        "selection_candidate_pool_supplier_ids": candidate_pool,
        "service_nonseparation_group_supplier_ids": nonseparation_ids,
        "boundary_universal_nonseparation_group_supplier_ids": universal_group,
        "priority_supplier_ids": selected_suppliers,
        "priority_chain_ids": [row["driver_chain_id"] for row in mappings],
        "priority_driver_mappings": mappings,
        "follow_up_supplier_ids": selected_suppliers,
        "follow_up_chain_ids": [row["driver_chain_id"] for row in mappings],
        "follow_up_driver_mappings": mappings,
        "follow_up_selection_rule": follow_up_rule,
        "follow_up_group_is_unordered": True,
        "priority_fields_are_legacy_compatibility_aliases": True,
        "slot_order_has_scientific_meaning": False,
        "scientific_order_claimed": False,
        "provisional_subset_selection_rule": provisional_rule,
        "selected_subset_covers_candidate_pool": set(selected_suppliers)
        == set(candidate_pool),
        "selected_subset_covers_service_nonseparation_group": set(selected_suppliers)
        == set(nonseparation_ids),
        "service_nonseparation_group_fully_followed_up": set(selected_suppliers)
        == set(nonseparation_ids),
        "selected_subset_covers_boundary_universal_group": set(selected_suppliers)
        == set(universal_group),
        "extension_selection_meaning": (
            "deterministic_post_selection_follow_up_not_unique_worst_lane"
        ),
        "supplier_lane_count_by_id": dict(sorted(lane_counts.items())),
        "all_multi_lane_supplier_ids": all_multi_lane_supplier_ids,
        "all_multi_lane_supplier_active_chain_ids_by_id": (
            all_multi_lane_supplier_active_chain_ids_by_id
        ),
        "multi_lane_common_cause_scope_complete": (
            tuple(all_multi_lane_supplier_ids)
            == tuple(sorted(EXPECTED_MULTI_LANE_SUPPLIERS))
        ),
        "supplier_lane_exposure_balanced": len(set(lane_counts.values())) == 1,
        "lane_count_normalization_applied": False,
        "driver_lane_uniqueness_claimed": False,
        "selection_and_assessment_seed_blocks_independent": False,
        "post_selection_confirmatory_inference_evaluable": False,
        "population_or_out_of_sample_top3_claimed": False,
        "independent_confirmation_required_for_confirmatory_top3": True,
        "extension_seed_blocks_independent_of_priority_selection": False,
        "extension_is_post_selection_characterization_not_confirmation": True,
        "baseline_service_configuration_count": 1,
        "cross_baseline_service_level_priority_robustness_evaluable": False,
        "lane_specific_peak_flow_window_selection": True,
        "cross_lane_same_calendar_comparison": False,
        "intrinsic_supplier_reliability_claimed": False,
        "stochastic_uncertainty_sources_included": [
            "transport_lead_time_draws_under_configured_distribution"
        ],
        "stochastic_uncertainty_sources_excluded": [
            "incident_occurrence_and_frequency",
            "incident_severity_and_duration",
            "demand_and_forecast",
            "initial_stock",
            "capacity_and_unplanned_breakdowns",
            "quality_yield_outside_stress",
            "model_parameters_and_network_structure",
        ],
        "broad_supply_uncertainty_monte_carlo_claimed": False,
        "historical_recurrence_evaluable": False,
        "global_variance_based_sensitivity_evaluable": False,
        "action_lever_influence_ranking_evaluable": False,
        "downstream_consequence_propagation_evaluable": True,
        "risk_to_risk_cascade_evaluable": False,
        "network_contagion_probability_evaluable": False,
        "individual_customer_or_order_attribution_evaluable": False,
        "revenue_or_penalty_loss_evaluable": False,
        "quality_hold_event_anchor": "shipment_decision_day",
        "opening_or_preexisting_in_transit_receipts_affected": False,
        "native_quarantine_inventory_modeled": False,
        "laboratory_release_process_modeled": False,
        "causal_lot_pair_count": len(selected_suppliers),
        "paired_seed_count_per_causal_lot_lane": CAUSAL_LOT_SEED_COUNT,
        "counterfactual_entity_identity_validated": False,
        "network_wide_lot_effect_evaluable": False,
        "multi_lane_common_cause_lot_effect_evaluable": False,
        "four_cause_lot_effect_evaluable": False,
        "temporal_lot_effect_variability_evaluable": False,
        "lot_effect_recurrence_evaluable": False,
        "integrity_digest_not_authenticated_signature": True,
        "cryptographic_authentication_present": False,
        "internal_consistency_recomputed_from_source": True,
    }
    lineage["priority_selection_lineage_sha256"] = _canonical_signature(lineage)
    return tuple(priorities), lineage


def _temporal_horizon_contract(
    *,
    artifact_dir: Path,
    priorities: Sequence[Mapping[str, str]],
    baseline_by_seed: Mapping[int, Mapping[str, str]],
) -> dict[str, Any]:
    first_seed = min(baseline_by_seed)
    run_dir = Path(str(baseline_by_seed[first_seed].get("run_dir") or ""))
    summary_path = run_dir / "summaries" / "first_simulation_summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"Résumé baseline requis pour l'horizon: {summary_path}")
    summary = _read_json(summary_path)
    graph_path = Path(str(summary.get("input_file") or "")).resolve()
    if not graph_path.is_file() or _sha256(graph_path) != str(
        summary.get("input_sha256") or ""
    ):
        raise ValueError("Le graphe du résumé baseline n'est pas vérifiable.")
    graph = _read_json(graph_path)
    scenario = next(
        (
            row
            for row in graph.get("scenarios", [])
            if str(row.get("id") or "") == "scn:BASE"
        ),
        None,
    )
    if scenario is None:
        raise ValueError("Scénario scn:BASE absent du graphe.")
    demand_by_product = {
        str(row.get("item_id") or "").replace("item:", ""): row
        for row in scenario.get("demand", [])
    }
    demand_support: dict[str, Any] = {}
    for product in network.TARGET_PRODUCTS:
        demand = demand_by_product.get(product)
        profiles = list((demand or {}).get("profile") or [])
        supported = bool(
            profiles
            and all(
                _to_int(profile.get("repeat_period_days"), 0) > 0
                and str(profile.get("repeat_mode") or "") == "annual_cycle"
                for profile in profiles
            )
        )
        demand_support[product] = {
            "supported": supported,
            "repeat_period_days": sorted(
                {_to_int(profile.get("repeat_period_days"), 0) for profile in profiles}
            ),
            "repeat_modes": sorted(
                {str(profile.get("repeat_mode") or "") for profile in profiles}
            ),
        }
    policies = {
        (str(row.get("node_id") or ""), str(row.get("item_id") or "")): row
        for row in (
            (summary.get("production_tracking") or {}).get(
                "unmodeled_supplier_source_policies"
            )
            or []
        )
    }
    lead_cover_by_chain: dict[str, int] = {}
    for lane in priorities:
        policy = policies.get(
            (str(lane.get("supplier_id") or ""), str(lane.get("item_id") or ""))
        )
        if policy is None:
            raise ValueError(f"Lead-cover absent pour {lane.get('chain_id')}")
        cover = _to_int(policy.get("source_material_lead_cover_days"), -1)
        if cover < 0:
            raise ValueError(f"Lead-cover invalide pour {lane.get('chain_id')}")
        lead_cover_by_chain[str(lane.get("chain_id") or "")] = cover
    max_cover = max(lead_cover_by_chain.values())
    tail = TEMPORAL_SEVERE_DATE_SHIFT_DAYS + max_cover + TEMPORAL_FIXED_FOLLOWUP_DAYS
    days = CALENDAR_WINDOWS[-1][1] + tail + 1
    graph_days = _to_int((scenario.get("horizon") or {}).get("steps_to_run"), -1)
    support = bool(graph_days >= days and all(v["supported"] for v in demand_support.values()))
    if not support:
        raise ValueError("Les entrées ne couvrent pas explicitement l'horizon temporel prolongé.")
    outcome_specs = [
        {
            "outcome_spec_id": f"calendar_window_{index}_fixed_followup",
            "incident_start_day": start,
            "incident_end_day": end,
            "outcome_start_day": start,
            "outcome_end_day": end + tail,
            "outcome_day_count": (end + tail) - start + 1,
        }
        for index, (start, end) in enumerate(CALENDAR_WINDOWS, 1)
    ]
    bundle_digest = _canonical_signature({"outcome_specs": outcome_specs})
    return {
        "simulation_days": days,
        "base_simulation_days": BASE_SIMULATION_DAYS,
        "severe_date_shift_days": TEMPORAL_SEVERE_DATE_SHIFT_DAYS,
        "maximum_selected_lane_source_material_lead_cover_days": max_cover,
        "selected_lane_lead_cover_days_by_chain": dict(
            sorted(lead_cover_by_chain.items())
        ),
        "fixed_followup_days": TEMPORAL_FIXED_FOLLOWUP_DAYS,
        "local_outcome_tail_after_incident_end_days": tail,
        "local_outcome_day_count": outcome_specs[0]["outcome_day_count"],
        "outcome_specs": outcome_specs,
        "outcome_bundle_sha256": bundle_digest,
        "graph_declared_horizon_days": graph_days,
        "extended_horizon_input_support_pass": support,
        "post_J719_extrapolation_policy": (
            EXTENDED_HORIZON_INPUT_POLICY
        ),
        "demand_profile_support_by_product": demand_support,
        "right_censoring_possible": True,
        "late_arrival_residual_must_be_reported": True,
        "period_specific_conditional_effects_described": True,
        "temporal_effect_causal_state_dependence_evaluable": False,
        "state_or_calendar_heterogeneity_only": True,
        "preincident_state_snapshot_contract": (
            "J0_pre_event_or_end_of_day_start_minus_1_observable_state"
        ),
        "preincident_complete_engine_checkpoint_available": False,
        "network_recovery_metric_status": "excluded_invalid_common_window",
    }


def _load_common_windows(path: Path) -> dict[str, tuple[int, int]]:
    rows = [
        row
        for row in _read_csv(path)
        if str(row.get("level_code") or "") == "severe"
        and str(row.get("supplier_id") or "") in EXPECTED_MULTI_LANE_SUPPLIERS
    ]
    expected_modes = set(network.MECHANISM_BY_KEY)
    windows: dict[str, tuple[int, int]] = {}
    for supplier_id in EXPECTED_MULTI_LANE_SUPPLIERS:
        supplier_rows = [
            row for row in rows if str(row.get("supplier_id") or "") == supplier_id
        ]
        modes = {str(row.get("failure_mode") or "") for row in supplier_rows}
        if modes != expected_modes or len(supplier_rows) != len(expected_modes):
            raise ValueError(
                f"Le plan source doit contenir quatre causes sévères pour {supplier_id}."
            )
        candidates = {
            (
                _to_int(row.get("stress_start_day"), -1),
                _to_int(row.get("stress_end_day"), -1),
            )
            for row in supplier_rows
        }
        if len(candidates) != 1:
            raise ValueError(
                f"Les quatre causes de {supplier_id} doivent partager la même fenêtre."
            )
        window = next(iter(candidates))
        if window[0] < 0 or window[1] < window[0]:
            raise ValueError(f"Fenêtre commune invalide pour {supplier_id}: {window}")
        windows[supplier_id] = window
    return windows


def load_complete_source(
    artifact_dir: Path,
    *,
    priority_boundary_audit: Path | None = None,
) -> SourceContext:
    artifact_dir = artifact_dir.resolve()
    paths = _required_source_paths(artifact_dir)
    hashes = _source_hashes(paths)
    manifest = _read_json(paths["campaign_manifest.json"])
    if str(manifest.get("status") or "") != "complete":
        raise ValueError("La campagne réseau source n'est pas complète.")
    if str(manifest.get("mode") or "") != "full":
        raise ValueError("Le plan additif exige la campagne réseau complète en mode full.")
    if _to_int(manifest.get("confirmation_seed_count"), -1) != FULL_PAIRED_SEED_COUNT:
        raise ValueError("Le manifeste source ne déclare pas 30 graines appariées.")
    configuration_hash_fields = (
        "graph_sha256",
        "profile_sha256",
        "engine_sha256",
        "v4_extraction_core_sha256",
    )
    missing_configuration_hashes = [
        field
        for field in configuration_hash_fields
        if not str(manifest.get(field) or "").strip()
    ]
    if missing_configuration_hashes:
        raise ValueError(
            "La réutilisation stricte exige les empreintes de configuration: "
            + ", ".join(missing_configuration_hashes)
        )
    seeds, baseline_by_seed, confirmation_by_case = _load_confirmation_rows(
        paths["confirmation_metrics.csv"]
    )
    active_lanes = _load_active_lanes(paths["active_lane_reference.csv"])
    active_by_chain = {
        str(row.get("chain_id") or ""): row for row in active_lanes
    }
    severe = _load_severe_scenarios(paths["scenario_design.csv"])
    priority_lineage: Mapping[str, Any] | None = None
    temporal_horizon: Mapping[str, Any] | None = None
    if priority_boundary_audit is None:
        priorities = _load_priorities(
            paths["confirmation_lane_sensitivity_ranking.csv"], active_by_chain
        )
    else:
        priorities, priority_lineage = _boundary_priority_selection(
            artifact_dir=artifact_dir,
            boundary_dir=priority_boundary_audit,
            source_manifest=manifest,
            active_lanes=active_lanes,
            severe_scenarios=severe,
        )
        temporal_horizon = _temporal_horizon_contract(
            artifact_dir=artifact_dir,
            priorities=priorities,
            baseline_by_seed=baseline_by_seed,
        )
    for priority in priorities:
        scenario_id = str(priority.get("worst_scenario_id") or "")
        matches = [
            row
            for (chain_id, _mode), row in severe.items()
            if chain_id == str(priority.get("chain_id") or "")
            and str(row.get("scenario_id") or "") == scenario_id
        ]
        if len(matches) != 1:
            raise ValueError(
                "Chaque priorité doit référencer un scénario sévère unique: "
                f"{priority.get('chain_id')} / {scenario_id}"
            )
    common_windows = _load_common_windows(
        paths["multi_lane_supplier_common_cause_design.csv"]
    )
    return SourceContext(
        artifact_dir=artifact_dir,
        manifest=manifest,
        source_hashes=hashes,
        seeds=seeds,
        active_lanes=active_lanes,
        priorities=priorities,
        severe_scenarios=severe,
        common_windows=common_windows,
        source_gate_state=_scientific_source_gates(manifest),
        baseline_by_seed=baseline_by_seed,
        confirmation_by_scenario_seed=confirmation_by_case,
        priority_boundary_dir=(
            priority_boundary_audit.resolve()
            if priority_boundary_audit is not None
            else None
        ),
        priority_selection_lineage=priority_lineage,
        temporal_horizon=temporal_horizon,
    )


def _lane_descriptor(row: Mapping[str, Any]) -> str:
    return "|".join(
        (
            str(row.get("chain_id") or ""),
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
            str(row.get("edge_id") or ""),
            str(row.get("target_product_id") or ""),
        )
    )


def _source_case_key(row: Mapping[str, Any]) -> str:
    run_dir = str(row.get("run_dir") or "").strip()
    if run_dir:
        return str(Path(run_dir).resolve())
    return (
        f"source::{row.get('scenario_id')}::seed_{_to_int(row.get('seed'), -1)}"
    )


def _baseline_reuse_pass(row: Mapping[str, Any]) -> bool:
    return bool(
        _as_bool(row.get("valid"))
        and str(row.get("input_sha256") or "")
        and str(row.get("j0_state_sha256") or "")
        and "lot_trace_required_for_paired_seed_block" in row
    )


def _stress_reuse_pass(
    row: Mapping[str, Any] | None,
    baseline: Mapping[str, Any],
    *,
    start_day: int,
    end_day: int,
) -> bool:
    if row is None or not _as_bool(row.get("valid")):
        return False
    return bool(
        str(row.get("input_sha256") or "")
        == str(baseline.get("input_sha256") or "")
        and str(row.get("j0_state_sha256") or "")
        == str(baseline.get("j0_state_sha256") or "")
        and _as_bool(row.get("lot_trace_required_for_paired_seed_block"))
        == _as_bool(baseline.get("lot_trace_required_for_paired_seed_block"))
        and _to_int(row.get("stress_start_day"), -1) == start_day
        and _to_int(row.get("stress_end_day"), -1) == end_day
    )


def _raw_lot_trace_available(row: Mapping[str, Any]) -> bool:
    if not _as_bool(row.get("lot_trace_required_for_paired_seed_block")):
        return False
    run_dir = str(row.get("run_dir") or "").strip()
    if not run_dir:
        return False
    data_dir = Path(run_dir) / "data"
    return bool(
        (data_dir / "production_lot_events.csv").is_file()
        and (data_dir / "production_lot_genealogy.csv").is_file()
    )


def _raw_lot_trace_hashes(row: Mapping[str, Any]) -> dict[str, str]:
    if not _raw_lot_trace_available(row):
        return {}
    data_dir = Path(str(row.get("run_dir") or "")) / "data"
    return {
        "lot_events_sha256": _sha256(data_dir / "production_lot_events.csv"),
        "lot_genealogy_sha256": _sha256(
            data_dir / "production_lot_genealogy.csv"
        ),
    }


def _retained_stress_lot_evidence_available(row: Mapping[str, Any]) -> bool:
    if _raw_lot_trace_available(row):
        return True
    if not _as_bool(row.get("lot_trace_required_for_paired_seed_block")):
        return False
    run_dir = str(row.get("run_dir") or "").strip()
    if not run_dir:
        return False
    proof_dir = Path(run_dir) / "proofs"
    return bool(
        (proof_dir / "impacted_receipt_lots.csv").is_file()
        and (proof_dir / "impacted_descendant_lots.csv").is_file()
        and (proof_dir / "impacted_genealogy.csv").is_file()
    )


def _retained_stress_lot_evidence_hashes(row: Mapping[str, Any]) -> dict[str, str]:
    raw = _raw_lot_trace_hashes(row)
    if raw:
        return {"evidence_format": "raw_lot_exports", **raw}
    if not _retained_stress_lot_evidence_available(row):
        return {}
    proof_dir = Path(str(row.get("run_dir") or "")) / "proofs"
    result = {
        "evidence_format": "retained_genealogical_proof_exports",
        "impacted_receipts_sha256": _sha256(
            proof_dir / "impacted_receipt_lots.csv"
        ),
        "impacted_descendants_sha256": _sha256(
            proof_dir / "impacted_descendant_lots.csv"
        ),
        "impacted_genealogy_sha256": _sha256(
            proof_dir / "impacted_genealogy.csv"
        ),
    }
    client_path = proof_dir / "impacted_client_deliveries.csv"
    if client_path.is_file():
        result["impacted_client_deliveries_sha256"] = _sha256(client_path)
    return result


def _mechanism_fields(mechanism_key: str) -> dict[str, Any]:
    mechanism = network.MECHANISM_BY_KEY[mechanism_key]
    return {
        "failure_mode": mechanism.key,
        "failure_mode_label": mechanism.label,
        "risk_type": mechanism.risk_type,
        "mechanism_value": mechanism.values[1],
        "mechanism_unit": mechanism.unit,
        "tested_level": "severe",
        "historical_occurrence_probability": "not_estimated",
    }


def _mathematical_family(mechanism_key: str) -> str:
    if mechanism_key in {"transport_delay", "quality_hold"}:
        return "date_shift"
    if mechanism_key in {"supply_availability", "quality_yield"}:
        return "usable_quantity_loss"
    raise KeyError(f"Cause sans famille mathématique déclarée: {mechanism_key}")


def _full_horizon_outcome_bundle() -> dict[str, Any]:
    return {
        "outcome_specs": [
            {
                "outcome_spec_id": "full_horizon_J0_J719",
                "outcome_start_day": 0,
                "outcome_end_day": BASE_SIMULATION_DAYS - 1,
                "outcome_day_count": BASE_SIMULATION_DAYS,
            }
        ]
    }


def build_baseline_design(
    context: SourceContext,
    causal_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    full_horizon_bundle = _full_horizon_outcome_bundle()
    full_horizon_digest = _canonical_signature(full_horizon_bundle)
    for seed in context.seeds:
        source = context.baseline_by_seed[seed]
        source_reference_valid = _baseline_reuse_pass(source)
        rows.append(
            {
                "pairing_block_id": f"metrics_seed_{seed}",
                "baseline_case_id": f"baseline_metrics__seed_{seed}",
                "seed": seed,
                "simulation_days": BASE_SIMULATION_DAYS,
                "outcome_bundle_sha256": full_horizon_digest,
                "outcome_specs_json": json.dumps(
                    full_horizon_bundle["outcome_specs"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "lot_trace_required": _as_bool(
                    source.get("lot_trace_required_for_paired_seed_block")
                ),
                "paired_scope": (
                    "common_cause|four_business_causes"
                    if context.temporal_horizon
                    else "common_cause|temporal|four_business_causes"
                ),
                # The summary-retained source is valid as the paired metric
                # reference, but it no longer contains the exact daily flow
                # ledger required by the extension runner.  A fresh physical
                # baseline is therefore always materialized.  Keeping the
                # source link is evidence lineage, not an engine-run reuse.
                "case_action": "new_baseline_run_required",
                "source_case_key": (
                    _source_case_key(source) if source_reference_valid else ""
                ),
                "new_run_count": 1,
                "execution_status": "planned_not_executed_source_reference_retained",
                "source_reference_valid_for_metrics": source_reference_valid,
                "source_reference_reused_as_physical_run": False,
                "pairing_rule": (
                    "même graine, même graphe, même profil, même état J0 et même "
                    "réglage de traçage lots"
                ),
            }
        )
    if context.temporal_horizon:
        temporal_specs = list(context.temporal_horizon["outcome_specs"])
        temporal_digest = str(context.temporal_horizon["outcome_bundle_sha256"])
        temporal_days = _to_int(context.temporal_horizon["simulation_days"], -1)
        for seed in context.seeds:
            rows.append(
                {
                    "pairing_block_id": f"temporal_metrics_seed_{seed}",
                    "baseline_case_id": f"baseline_temporal__seed_{seed}",
                    "seed": seed,
                    "simulation_days": temporal_days,
                    "outcome_bundle_sha256": temporal_digest,
                    "outcome_specs_json": json.dumps(
                        temporal_specs,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "lot_trace_required": False,
                    "paired_scope": "temporal_period_characterization",
                    "case_action": "new_baseline_run_required",
                    "source_case_key": "",
                    "new_run_count": 1,
                    "execution_status": "planned_not_executed",
                    "pairing_rule": (
                        "même graine, horizon prolongé, même graphe/profil/état J0 et "
                        "bundle de fenêtres locales pré-déclaré"
                    ),
                }
            )
    causal_seed = min(context.seeds)
    causal_needs_new_pair = any(
        str(row.get("baseline_case_action") or "")
        == "new_dedicated_traced_baseline_required"
        for row in causal_rows
    )
    if causal_needs_new_pair:
        rows.append(
            {
                "pairing_block_id": f"causal_lot_seed_{causal_seed}",
                "baseline_case_id": f"baseline_causal_lot__seed_{causal_seed}",
                "seed": causal_seed,
                "simulation_days": BASE_SIMULATION_DAYS,
                "outcome_bundle_sha256": full_horizon_digest,
                "outcome_specs_json": json.dumps(
                    full_horizon_bundle["outcome_specs"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "lot_trace_required": True,
                "paired_scope": "causal_lot_attribution_subset",
                "case_action": "new_dedicated_traced_baseline_required",
                "source_case_key": "",
                "new_run_count": 1,
                "execution_status": "planned_not_executed",
                "pairing_rule": (
                    "référence dédiée; traçage lots activé à l'identique sur référence "
                    "et incidents"
                ),
            }
        )
    return rows


def build_common_cause_design(context: SourceContext) -> list[dict[str, Any]]:
    observed_counts: dict[str, int] = {}
    for lane in context.active_lanes:
        supplier = str(lane.get("supplier_id") or "")
        observed_counts[supplier] = observed_counts.get(supplier, 0) + 1
    observed_multi_lane = tuple(
        sorted(supplier for supplier, count in observed_counts.items() if count > 1)
    )
    if observed_multi_lane != tuple(sorted(EXPECTED_MULTI_LANE_SUPPLIERS)):
        raise ValueError(
            "Périmètre common-cause incomplet: "
            f"attendu={sorted(EXPECTED_MULTI_LANE_SUPPLIERS)}, "
            f"observé={list(observed_multi_lane)}"
        )
    by_supplier: dict[str, list[Mapping[str, str]]] = {}
    for supplier_id in EXPECTED_MULTI_LANE_SUPPLIERS:
        lanes = [
            row
            for row in context.active_lanes
            if str(row.get("supplier_id") or "") == supplier_id
        ]
        if len(lanes) != 2:
            raise ValueError(
                f"{supplier_id} doit avoir exactement deux voies actives, trouvé {len(lanes)}."
            )
        by_supplier[supplier_id] = sorted(
            lanes, key=lambda row: str(row.get("chain_id") or "")
        )
    rows: list[dict[str, Any]] = []
    for supplier_id in EXPECTED_MULTI_LANE_SUPPLIERS:
        lanes = by_supplier[supplier_id]
        start_day, end_day = context.common_windows[supplier_id]
        for mechanism_key in sorted(network.MECHANISM_BY_KEY):
            base_id = f"common__{supplier_id.lower()}__{mechanism_key}"
            for seed in context.seeds:
                baseline = context.baseline_by_seed[seed]
                rows.append(
                    {
                        "extension": "multi_lane_supplier_common_cause",
                        "case_id": base_id,
                        "seed": seed,
                        "pairing_block_id": f"metrics_seed_{seed}",
                        "paired_baseline_case_id": f"baseline_metrics__seed_{seed}",
                        "simulation_days": BASE_SIMULATION_DAYS,
                        "outcome_spec_id": "full_horizon_J0_J719",
                        "outcome_start_day": 0,
                        "outcome_end_day": BASE_SIMULATION_DAYS - 1,
                        "outcome_day_count": BASE_SIMULATION_DAYS,
                        "outcome_bundle_sha256": _canonical_signature(
                            _full_horizon_outcome_bundle()
                        ),
                        "supplier_id": supplier_id,
                        "affected_lane_count": 2,
                        "affected_chain_ids": "|".join(
                            str(row.get("chain_id") or "") for row in lanes
                        ),
                        "affected_lanes": ";".join(_lane_descriptor(row) for row in lanes),
                        "affected_products": "|".join(
                            sorted({str(row.get("target_product_id") or "") for row in lanes})
                        ),
                        "stress_start_day": start_day,
                        "stress_end_day": end_day,
                        "lot_trace_required": _as_bool(
                            baseline.get("lot_trace_required_for_paired_seed_block")
                        ),
                        "case_action": "new_run_required",
                        "source_case_key": "",
                        "new_run_count": 1,
                        "execution_status": "planned_not_executed",
                        "joint_multi_lane_conditional_effect_evaluable": True,
                        "multi_lane_interaction_or_synergy_evaluable": False,
                        "cascade_amplification_claimed": False,
                        **_mechanism_fields(mechanism_key),
                    }
                )
    return rows


def _retained_severe(context: SourceContext, priority: Mapping[str, str]) -> Mapping[str, str]:
    chain_id = str(priority.get("chain_id") or "")
    scenario_id = str(priority.get("worst_scenario_id") or "")
    return next(
        row
        for (candidate_chain, _mode), row in context.severe_scenarios.items()
        if candidate_chain == chain_id
        and str(row.get("scenario_id") or "") == scenario_id
    )


def build_temporal_design(context: SourceContext) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for priority in context.priorities:
        slot = _to_int(
            priority.get("selection_slot"),
            _to_int(priority.get("lane_sensitivity_rank"), -1),
        )
        severe = _retained_severe(context, priority)
        mechanism_key = str(severe.get("failure_mode") or "")
        for window_index, (start_day, end_day) in enumerate(CALENDAR_WINDOWS, 1):
            temporal_spec = (
                dict(context.temporal_horizon["outcome_specs"][window_index - 1])
                if context.temporal_horizon
                else {
                    "outcome_spec_id": "full_horizon_J0_J719",
                    "outcome_start_day": 0,
                    "outcome_end_day": BASE_SIMULATION_DAYS - 1,
                    "outcome_day_count": BASE_SIMULATION_DAYS,
                }
            )
            simulation_days = (
                _to_int(context.temporal_horizon["simulation_days"], -1)
                if context.temporal_horizon
                else BASE_SIMULATION_DAYS
            )
            for seed in context.seeds:
                baseline = context.baseline_by_seed[seed]
                source_case = context.confirmation_by_scenario_seed.get(
                    (str(severe.get("scenario_id") or ""), seed)
                )
                reusable = bool(
                    not context.temporal_horizon
                    and _stress_reuse_pass(
                        source_case,
                        baseline,
                        start_day=start_day,
                        end_day=end_day,
                    )
                )
                rows.append(
                    {
                        "extension": "temporal_robustness",
                        "case_id": (
                            f"temporal__slot{slot}__{priority['chain_id']}__"
                            f"{mechanism_key}__window{window_index}"
                        ),
                        "seed": seed,
                        "pairing_block_id": (
                            f"temporal_metrics_seed_{seed}"
                            if context.temporal_horizon
                            else f"metrics_seed_{seed}"
                        ),
                        "paired_baseline_case_id": (
                            f"baseline_temporal__seed_{seed}"
                            if context.temporal_horizon
                            else f"baseline_metrics__seed_{seed}"
                        ),
                        "selection_slot": slot,
                        "priority_selection_slot": slot,
                        "slot_order_has_scientific_meaning": False,
                        "priority_status_at_planning": (
                            priority.get("priority_selection_status")
                            or "legacy_lane_identifier_only_not_scientific_rank"
                        ),
                        "chain_id": priority["chain_id"],
                        "supplier_id": priority["supplier_id"],
                        "item_id": priority["item_id"],
                        "dst_node_id": priority["dst_node_id"],
                        "edge_id": priority["edge_id"],
                        "target_product_id": priority["target_product_id"],
                        "window_index": window_index,
                        "stress_start_day": start_day,
                        "stress_end_day": end_day,
                        "simulation_days": simulation_days,
                        **temporal_spec,
                        "outcome_bundle_sha256": (
                            str(context.temporal_horizon["outcome_bundle_sha256"])
                            if context.temporal_horizon
                            else _canonical_signature(_full_horizon_outcome_bundle())
                        ),
                        "preincident_snapshot_day": start_day - 1,
                        "preincident_snapshot_semantics": (
                            "J0_pre_event"
                            if start_day == 0
                            else "end_of_day_start_minus_1_before_risk_application"
                        ),
                        "preincident_complete_engine_checkpoint_available": False,
                        "local_metric_components_required": True,
                        "recovery_metric_status": "excluded_not_redefined",
                        "lot_trace_required": _as_bool(
                            baseline.get("lot_trace_required_for_paired_seed_block")
                        ) if not context.temporal_horizon else False,
                        "case_action": (
                            "reuse_existing_confirmation_case"
                            if reusable
                            else "new_run_required"
                        ),
                        "source_case_key": (
                            _source_case_key(source_case) if reusable and source_case else ""
                        ),
                        "new_run_count": 0 if reusable else 1,
                        "execution_status": (
                            "source_case_referenced"
                            if reusable
                            else "planned_not_executed"
                        ),
                        "period_specific_conditional_effects_described": True,
                        "temporal_effect_causal_state_dependence_evaluable": False,
                        "extension_is_post_selection_characterization_not_confirmation": True,
                        **_mechanism_fields(mechanism_key),
                    }
                )
    return rows


def build_four_cause_design(context: SourceContext) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for priority in context.priorities:
        slot = _to_int(
            priority.get("selection_slot"),
            _to_int(priority.get("lane_sensitivity_rank"), -1),
        )
        start_day = _to_int(priority.get("active_window_start_day"), -1)
        end_day = _to_int(priority.get("active_window_end_day"), -1)
        if start_day < 0 or end_day < start_day:
            raise ValueError(f"Fenêtre active invalide pour {priority['chain_id']}")
        for mechanism_key in sorted(network.MECHANISM_BY_KEY):
            if (str(priority["chain_id"]), mechanism_key) not in context.severe_scenarios:
                raise ValueError(
                    f"Cause sévère absente: {priority['chain_id']} / {mechanism_key}"
                )
            for seed in context.seeds:
                baseline = context.baseline_by_seed[seed]
                severe = context.severe_scenarios[
                    (str(priority["chain_id"]), mechanism_key)
                ]
                source_case = context.confirmation_by_scenario_seed.get(
                    (str(severe.get("scenario_id") or ""), seed)
                )
                reusable = _stress_reuse_pass(
                    source_case,
                    baseline,
                    start_day=start_day,
                    end_day=end_day,
                )
                rows.append(
                    {
                        "extension": "priority_four_business_causes",
                        "case_id": (
                            f"four_causes__slot{slot}__{priority['chain_id']}__"
                            f"{mechanism_key}"
                        ),
                        "seed": seed,
                        "pairing_block_id": f"metrics_seed_{seed}",
                        "paired_baseline_case_id": f"baseline_metrics__seed_{seed}",
                        "selection_slot": slot,
                        "priority_selection_slot": slot,
                        "slot_order_has_scientific_meaning": False,
                        "chain_id": priority["chain_id"],
                        "supplier_id": priority["supplier_id"],
                        "item_id": priority["item_id"],
                        "dst_node_id": priority["dst_node_id"],
                        "edge_id": priority["edge_id"],
                        "target_product_id": priority["target_product_id"],
                        "stress_start_day": start_day,
                        "stress_end_day": end_day,
                        "simulation_days": BASE_SIMULATION_DAYS,
                        "outcome_spec_id": "full_horizon_J0_J719",
                        "outcome_start_day": 0,
                        "outcome_end_day": BASE_SIMULATION_DAYS - 1,
                        "outcome_day_count": BASE_SIMULATION_DAYS,
                        "outcome_bundle_sha256": _canonical_signature(
                            _full_horizon_outcome_bundle()
                        ),
                        "lot_trace_required": _as_bool(
                            baseline.get("lot_trace_required_for_paired_seed_block")
                        ),
                        "case_action": (
                            "reuse_existing_confirmation_case"
                            if reusable
                            else "new_run_required"
                        ),
                        "source_case_key": (
                            _source_case_key(source_case) if reusable and source_case else ""
                        ),
                        "new_run_count": 0 if reusable else 1,
                        "execution_status": (
                            "source_case_referenced"
                            if reusable
                            else "planned_not_executed"
                        ),
                        "mathematical_family": _mathematical_family(mechanism_key),
                        "calculation_justification": (
                            "reuse_exact_same_severe_case_from_main_confirmation"
                            if reusable
                            else (
                                "new_daily_case_needed_because_tested_severe_value_or_"
                                "business_semantics_differs_from_confirmed_family_case"
                            )
                        ),
                        "comparison_scope": (
                            "quatre causes métier conditionnelles; ni fréquence ni probabilité"
                        ),
                        "extension_is_post_selection_characterization_not_confirmation": True,
                        **_mechanism_fields(mechanism_key),
                    }
                )
    return rows


def build_causal_lot_design(context: SourceContext) -> list[dict[str, Any]]:
    causal_seed = min(context.seeds)
    rows: list[dict[str, Any]] = []
    for priority in context.priorities:
        slot = _to_int(
            priority.get("selection_slot"),
            _to_int(priority.get("lane_sensitivity_rank"), -1),
        )
        severe = _retained_severe(context, priority)
        mechanism_key = str(severe.get("failure_mode") or "")
        baseline = context.baseline_by_seed[causal_seed]
        source_case = context.confirmation_by_scenario_seed.get(
            (str(severe.get("scenario_id") or ""), causal_seed)
        )
        start_day = _to_int(priority.get("active_window_start_day"), -1)
        end_day = _to_int(priority.get("active_window_end_day"), -1)
        baseline_raw_reusable = bool(
            _baseline_reuse_pass(baseline) and _raw_lot_trace_available(baseline)
        )
        stress_evidence_reusable = bool(
            source_case
            and _stress_reuse_pass(
                source_case,
                baseline,
                start_day=start_day,
                end_day=end_day,
            )
            and _retained_stress_lot_evidence_available(source_case)
        )
        if baseline_raw_reusable and stress_evidence_reusable:
            case_action = "reuse_existing_traced_pair"
        elif baseline_raw_reusable:
            case_action = "new_traced_stress_with_existing_baseline"
        elif stress_evidence_reusable:
            case_action = "reuse_existing_stress_with_new_traced_baseline"
        else:
            case_action = "new_traced_stress_with_new_shared_baseline"
        baseline_hashes = _raw_lot_trace_hashes(baseline)
        stress_hashes = _retained_stress_lot_evidence_hashes(source_case or {})
        rows.append(
            {
                "extension": "causal_lot_attribution_subset",
                "case_id": (
                    f"causal_lot__slot{slot}__{priority['chain_id']}__{mechanism_key}"
                ),
                "seed": causal_seed,
                "pairing_block_id": (
                    f"metrics_seed_{causal_seed}"
                    if baseline_raw_reusable
                    else f"causal_lot_seed_{causal_seed}"
                ),
                "paired_baseline_case_id": (
                    f"baseline_metrics__seed_{causal_seed}"
                    if baseline_raw_reusable
                    else f"baseline_causal_lot__seed_{causal_seed}"
                ),
                "selection_slot": slot,
                "priority_selection_slot": slot,
                "slot_order_has_scientific_meaning": False,
                "chain_id": priority["chain_id"],
                "supplier_id": priority["supplier_id"],
                "item_id": priority["item_id"],
                "dst_node_id": priority["dst_node_id"],
                "edge_id": priority["edge_id"],
                "target_product_id": priority["target_product_id"],
                "stress_start_day": start_day,
                "stress_end_day": end_day,
                "simulation_days": BASE_SIMULATION_DAYS,
                "outcome_spec_id": "full_horizon_J0_J719",
                "outcome_start_day": 0,
                "outcome_end_day": BASE_SIMULATION_DAYS - 1,
                "outcome_day_count": BASE_SIMULATION_DAYS,
                "outcome_bundle_sha256": _canonical_signature(
                    _full_horizon_outcome_bundle()
                ),
                "lot_trace_required": True,
                "baseline_lot_trace_required": True,
                "case_action": case_action,
                "baseline_case_action": (
                    "reuse_existing_traced_baseline"
                    if baseline_raw_reusable
                    else "new_dedicated_traced_baseline_required"
                ),
                "source_baseline_case_key": (
                    _source_case_key(baseline) if baseline_raw_reusable else ""
                ),
                "source_incident_case_key": (
                    _source_case_key(source_case)
                    if stress_evidence_reusable and source_case
                    else ""
                ),
                "source_baseline_lot_events_sha256": baseline_hashes.get(
                    "lot_events_sha256", ""
                ),
                "source_baseline_lot_genealogy_sha256": baseline_hashes.get(
                    "lot_genealogy_sha256", ""
                ),
                "source_incident_evidence_format": stress_hashes.get(
                    "evidence_format", ""
                ),
                "source_incident_lot_events_sha256": stress_hashes.get(
                    "lot_events_sha256", ""
                ),
                "source_incident_lot_genealogy_sha256": stress_hashes.get(
                    "lot_genealogy_sha256", ""
                ),
                "source_incident_impacted_receipts_sha256": stress_hashes.get(
                    "impacted_receipts_sha256", ""
                ),
                "source_incident_impacted_descendants_sha256": stress_hashes.get(
                    "impacted_descendants_sha256", ""
                ),
                "source_incident_impacted_genealogy_sha256": stress_hashes.get(
                    "impacted_genealogy_sha256", ""
                ),
                "source_incident_impacted_client_deliveries_sha256": stress_hashes.get(
                    "impacted_client_deliveries_sha256", ""
                ),
                "new_run_count": 0 if stress_evidence_reusable else 1,
                "execution_status": (
                    "source_pair_referenced"
                    if baseline_raw_reusable and stress_evidence_reusable
                    else "planned_not_executed"
                ),
                "genealogical_exposure_output": "lot_genealogical_exposure_summary.csv",
                "genealogical_quantity_meaning": (
                    "borne haute des descendants exposés; pas quantité causée par l'incident"
                ),
                "technical_heuristic_difference_output": "causal_lot_attribution_summary.csv",
                "technical_heuristic_match_rule": (
                    "clé technique unique présente dans référence et incident; "
                    "même unité; identité contrefactuelle non prouvée"
                ),
                "causal_fields_required": (
                    "baseline_day|stress_day|day_delta|baseline_qty|stress_qty|qty_delta|uom"
                ),
                "unmatched_lot_rule": (
                    "conserver comme exposition généalogique; exclure de toute "
                    "attribution causale"
                ),
                "lot_identifier_scope": (
                    "identifiant technique simulé; pas numéro de lot industriel observé"
                ),
                "quality_hold_semantics": (
                    "attente qualité reconstruite; pas de stock de quarantaine natif"
                    if mechanism_key == "quality_hold"
                    else "not_applicable"
                ),
                "quantity_aggregation_rule": "séparer chaque unité; aucun total inter-unités",
                "counterfactual_entity_identity_validated": False,
                "causal_lot_attribution_available": False,
                "heuristic_comparison_display_allowed": True,
                **_mechanism_fields(mechanism_key),
            }
        )
    return rows


def _expected_counts(
    baseline_rows: Sequence[Mapping[str, Any]],
    common_rows: Sequence[Mapping[str, Any]],
    temporal_rows: Sequence[Mapping[str, Any]],
    four_cause_rows: Sequence[Mapping[str, Any]],
    causal_rows: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    follow_up_lane_sets = {
        "temporal": {str(row.get("chain_id") or "") for row in temporal_rows},
        "four_causes": {
            str(row.get("chain_id") or "") for row in four_cause_rows
        },
        "lot": {str(row.get("chain_id") or "") for row in causal_rows},
    }
    if (
        not follow_up_lane_sets["temporal"]
        or any("" in values for values in follow_up_lane_sets.values())
        or len({frozenset(values) for values in follow_up_lane_sets.values()}) != 1
    ):
        raise AssertionError(
            "Les extensions temporelle, quatre-causes et lots doivent couvrir "
            "exactement le même groupe de voies."
        )
    follow_up_lane_count = len(follow_up_lane_sets["temporal"])
    metric_baseline_rows = [
        row
        for row in baseline_rows
        if str(row.get("paired_scope") or "") != "causal_lot_attribution_subset"
    ]
    expected_metric_baseline_count = FULL_PAIRED_SEED_COUNT * (
        2
        if any(
            str(row.get("paired_scope") or "")
            == "temporal_period_characterization"
            for row in metric_baseline_rows
        )
        else 1
    )
    logical = {
        "paired_metric_baseline_references": expected_metric_baseline_count,
        "multi_lane_common_cause_stress_cases": (
            len(EXPECTED_MULTI_LANE_SUPPLIERS)
            * len(network.MECHANISMS)
            * FULL_PAIRED_SEED_COUNT
        ),
        "temporal_robustness_stress_cases": (
            follow_up_lane_count * len(CALENDAR_WINDOWS) * FULL_PAIRED_SEED_COUNT
        ),
        "priority_four_business_causes_stress_cases": (
            follow_up_lane_count * len(network.MECHANISMS) * FULL_PAIRED_SEED_COUNT
        ),
        "causal_lot_stress_cases": follow_up_lane_count * CAUSAL_LOT_SEED_COUNT,
    }
    actual = {
        "paired_metric_baseline_references": sum(
            str(row.get("paired_scope") or "")
            != "causal_lot_attribution_subset"
            for row in baseline_rows
        ),
        "multi_lane_common_cause_stress_cases": len(common_rows),
        "temporal_robustness_stress_cases": len(temporal_rows),
        "priority_four_business_causes_stress_cases": len(four_cause_rows),
        "causal_lot_stress_cases": len(causal_rows),
    }
    if actual != logical:
        raise AssertionError(
            f"Compteurs logiques incohérents: attendu={logical}, obtenu={actual}"
        )
    all_rows = [
        *baseline_rows,
        *common_rows,
        *temporal_rows,
        *four_cause_rows,
        *causal_rows,
    ]
    reused_keys: set[str] = set()
    reused_reference_links = 0
    for row in all_rows:
        for field in (
            "source_case_key",
            "source_baseline_case_key",
            "source_incident_case_key",
        ):
            value = str(row.get(field) or "").strip()
            if value:
                reused_reference_links += 1
                reused_keys.add(value)
    new_keys: set[str] = set()
    for row in baseline_rows:
        if _to_int(row.get("new_run_count"), 0):
            new_keys.add(f"baseline::{row.get('baseline_case_id')}")
    for row in [*common_rows, *temporal_rows, *four_cause_rows, *causal_rows]:
        if _to_int(row.get("new_run_count"), 0):
            new_keys.add(
                f"{row.get('extension')}::{row.get('case_id')}::seed_{row.get('seed')}"
            )
    counts = dict(logical)
    counts["follow_up_lane_count"] = follow_up_lane_count
    counts["dedicated_lot_trace_baseline_logical_reference_count"] = sum(
        str(row.get("case_action") or "")
        == "new_dedicated_traced_baseline_required"
        for row in baseline_rows
    )
    counts["logical_stress_comparison_count"] = (
        len(common_rows) + len(temporal_rows) + len(four_cause_rows) + len(causal_rows)
    )
    counts["logical_case_reference_count"] = (
        len(baseline_rows) + counts["logical_stress_comparison_count"]
    )
    counts["reused_case_count"] = len(reused_keys)
    counts["reused_case_reference_link_count"] = reused_reference_links
    counts["source_referenced_unique_case_count"] = len(reused_keys)
    counts["source_referenced_case_link_count"] = reused_reference_links
    source_baseline_keys = {
        str(row.get("source_case_key") or "").strip()
        for row in baseline_rows
        if str(row.get("source_case_key") or "").strip()
    }
    source_stress_keys = {
        str(row.get(field) or "").strip()
        for row in [*common_rows, *temporal_rows, *four_cause_rows, *causal_rows]
        for field in ("source_case_key", "source_incident_case_key")
        if str(row.get(field) or "").strip()
    }
    counts["source_baseline_reference_count"] = len(source_baseline_keys)
    counts["source_stress_reused_unique_case_count"] = len(source_stress_keys)
    counts["source_evidence_alias_link_count"] = reused_reference_links - len(
        reused_keys
    )
    counts["design_declared_new_run_flag_reference_count"] = len(new_keys)
    counts["design_declared_new_baseline_reference_count"] = sum(
        _to_int(row.get("new_run_count"), 0) for row in baseline_rows
    )
    counts["design_declared_new_stress_run_count"] = sum(
        _to_int(row.get("new_run_count"), 0)
        for row in [*common_rows, *temporal_rows, *four_cause_rows, *causal_rows]
    )
    baseline_fingerprints = {
        (
            _to_int(row.get("seed"), -1),
            _to_int(row.get("simulation_days"), BASE_SIMULATION_DAYS),
            _as_bool(row.get("lot_trace_required")),
            str(row.get("outcome_bundle_sha256") or ""),
        )
        for row in baseline_rows
    }
    metric_baseline_fingerprints = {
        (
            _to_int(row.get("seed"), -1),
            _to_int(row.get("simulation_days"), BASE_SIMULATION_DAYS),
            _as_bool(row.get("lot_trace_required")),
            str(row.get("outcome_bundle_sha256") or ""),
        )
        for row in metric_baseline_rows
    }
    counts["dedicated_lot_trace_baseline_new_runs"] = len(
        baseline_fingerprints - metric_baseline_fingerprints
    )
    counts["runner_materialized_baseline_physical_run_count"] = len(
        baseline_fingerprints
    )
    counts["new_baseline_engine_run_count"] = len(baseline_fingerprints)
    counts["new_stress_engine_run_count"] = counts[
        "design_declared_new_stress_run_count"
    ]
    counts["expected_engine_physical_run_count"] = (
        counts["new_baseline_engine_run_count"]
        + counts["new_stress_engine_run_count"]
    )
    # Compatibility name, now defined unambiguously as actual engine
    # invocations expected from a fresh full runner execution.
    counts["new_run_count"] = counts["expected_engine_physical_run_count"]
    counts["unique_physical_case_count_after_reuse"] = counts[
        "expected_engine_physical_run_count"
    ]
    counts["logical_comparison_and_baseline_reference_count"] = counts[
        "logical_case_reference_count"
    ]
    counts["double_counted_evidence_case_count"] = 0
    if counts["new_run_count"] != (
        counts["new_baseline_engine_run_count"]
        + counts["new_stress_engine_run_count"]
    ):
        raise AssertionError("Le compteur de calculs moteur n'est pas réconcilié.")
    return counts


def build_promotion_controls(
    context: SourceContext, counts: Mapping[str, int]
) -> dict[str, Any]:
    source = context.source_gate_state
    source_all_pass = all(
        source.get(key, False)
        for key in (
            "baseline_service_all_30_pass",
            "paired_inputs_and_j0_all_rows_pass",
            "active_lane_flow_at_least_29_of_30_pass",
        )
    )
    controls = [
        {
            "control_id": "source_network_full_30_paired",
            "state": "pass",
            "required": True,
            "criterion": (
                "campagne réseau complète et exactement 30 références appariées, "
                "réutilisées si graphe, profil, graine, état J0 et traçage sont identiques"
            ),
        },
        {
            "control_id": "source_scientific_release_gates",
            "state": "pass" if source_all_pass else "fail",
            "required": True,
            "criterion": (
                "service référence, intégrité graphe/J0 et flux actif; aucun ordre de rang utilisé"
            ),
            "details": dict(source),
        },
        {
            "control_id": "multi_lane_common_cause_execution",
            "state": "planned_not_executed",
            "required": True,
            "criterion": (
                "2 fournisseurs × 4 causes × 30 graines; deux voies réellement sollicitées "
                "dans au moins 29 graines sur 30"
            ),
            "expected_manifest": "multi_lane_supplier_common_cause_manifest.json",
        },
        {
            "control_id": "temporal_robustness_execution",
            "state": "planned_not_executed",
            "required": True,
            "criterion": (
                f"{counts['follow_up_lane_count']} voies × 4 fenêtres × 30 graines, "
                "sans réinjecter les résultats dans "
                "le classement voie-par-voie"
            ),
            "expected_manifest": "temporal_robustness_manifest.json",
        },
        {
            "control_id": "four_business_causes_execution",
            "state": "planned_not_executed",
            "required": True,
            "criterion": (
                f"{counts['follow_up_lane_count']} voies × 4 causes sévères "
                "× 30 graines appariées"
            ),
            "expected_manifest": "priority_four_business_causes_manifest.json",
        },
        {
            "control_id": "causal_lot_attribution_execution",
            "state": "planned_not_executed",
            "required": True,
            "criterion": (
                "référence et incident avec traçage identique; exposition généalogique "
                "séparée des écarts entre événements techniques appariés "
                "heuristiquement"
            ),
            "expected_manifest": "causal_lot_attribution_manifest.json",
        },
    ]
    return {
        "status": "not_promotable_from_plan",
        "all_required_controls_pass": False,
        "source_controls_pass": source_all_pass,
        "planned_case_counts": dict(counts),
        "controls": controls,
        "promotion_rule": (
            "Le statut stabilisé n'est autorisé que lorsque tous les contrôles requis "
            "sont passés dans des manifestes d'exécution séparés et auditables."
        ),
        "industrial_criticality_claimed": False,
        "historical_supplier_probability_estimated": False,
        "scoped_descriptive_priority_set_display_allowed": bool(
            (context.priority_selection_lineage or {}).get(
                "scoped_descriptive_priority_set_display_allowed"
            )
        ),
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "selected_group_effect_characterization_is_not_confirmation": True,
    }


def _plan_text(manifest: Mapping[str, Any]) -> str:
    counts = manifest["planned_case_counts"]
    return "\n".join(
        (
            "# Plan additif après sélection des priorités",
            "",
            "Ce dossier décrit les simulations à exécuter plus tard. Il ne contient ",
            "aucun résultat et ne lance pas le moteur.",
            "",
            "## Périmètre exact",
            "",
            f"- incidents communs multi-voies : {counts['multi_lane_common_cause_stress_cases']} cas ;",
            f"- caractérisation sur quatre périodes : {counts['temporal_robustness_stress_cases']} cas ;",
            f"- quatre causes métier sur les priorités : {counts['priority_four_business_causes_stress_cases']} cas ;",
            f"- illustrations techniques lots appariées heuristiquement : {counts['causal_lot_stress_cases']} cas ;",
            f"- cas source distincts réutilisés : {counts['reused_case_count']} ;",
            f"- nouveaux stress nécessaires : {counts['new_stress_engine_run_count']} ;",
            f"- références physiques à recalculer : {counts['new_baseline_engine_run_count']} ;",
            f"- calculs physiques attendus, références incluses : {counts['expected_engine_physical_run_count']}.",
            "",
            "Les incidents sont des hypothèses exogènes. Le moteur supply reste dynamique ",
            "par ses stocks, ses retards et son calcul des besoins, mais ce plan n'est ni ",
            "une prévision de probabilité fournisseur ni un pilotage automatique en boucle fermée.",
            "",
            f"Les {counts['follow_up_lane_count']} voies sont des cibles déterministes de suivi, ",
            "sans ordre scientifique entre elles. Les résultats futurs resteront ",
            "séparés du test voie-par-voie.",
        )
    ) + "\n"


def validate_plan_artifact(
    output_dir: Path,
    *,
    require_boundary_lineage: bool = False,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _exact_file_inventory(output_dir, PLAN_FILES, label="plan")
    manifest = _read_json(output_dir / "post_priority_extensions_plan_manifest.json")
    if str(manifest.get("schema_version") or "") != SCHEMA_VERSION:
        raise ValueError("Version de plan additif inconnue.")
    if str(manifest.get("status") or "") != "planned_not_executed":
        raise ValueError("Le plan ne doit pas se présenter comme un résultat exécuté.")
    if _as_bool(manifest.get("execution_enabled")):
        raise ValueError("Un plan de validation ne peut pas activer l'exécution.")
    file_hashes = manifest.get("plan_file_hashes") or {}
    if set(file_hashes) != set(IMMUTABLE_PLAN_FILES):
        raise ValueError("Inventaire plan_file_hashes incomplet ou excessif.")
    for name, expected in file_hashes.items():
        path = output_dir / str(name)
        if not path.is_file() or _sha256(path) != str(expected):
            raise ValueError(f"Empreinte du fichier de plan invalide: {name}")
    signature_payload = manifest.get("signature_payload") or {}
    expected_signature = _canonical_signature(signature_payload)
    if str(manifest.get("plan_signature") or "") != expected_signature:
        raise ValueError("Signature du plan additif invalide.")
    mirrored = {
        "planner_builder_sha256": manifest.get("planner_builder_sha256"),
        "source_campaign_signature": manifest.get("source_campaign_signature"),
        "source_file_hashes": manifest.get("source_artifact_file_hashes"),
        "confirmation_seeds": manifest.get("confirmation_seeds"),
        "calendar_windows": manifest.get("calendar_windows"),
        "multi_lane_supplier_ids": manifest.get("multi_lane_supplier_ids"),
        "all_multi_lane_supplier_ids": manifest.get(
            "all_multi_lane_supplier_ids"
        ),
        "all_multi_lane_supplier_active_chain_ids_by_id": manifest.get(
            "all_multi_lane_supplier_active_chain_ids_by_id"
        ),
        "priority_chain_ids": manifest.get("priority_chain_ids"),
        "priority_selection_lineage": manifest.get("priority_selection_lineage"),
        "priority_selection_lineage_sha256": manifest.get(
            "priority_selection_lineage_sha256"
        ),
        "temporal_horizon_contract": manifest.get("temporal_horizon_contract"),
        "design_hashes": manifest.get("design_hashes"),
        "planned_case_counts": manifest.get("planned_case_counts"),
        "execution_configuration_lock": manifest.get(
            "execution_configuration_lock"
        ),
        "execution_enabled": manifest.get("execution_enabled"),
        "contract_revision": manifest.get("contract_revision"),
    }
    for key, value in mirrored.items():
        if signature_payload.get(key) != value:
            raise ValueError(f"Payload signé et manifeste divergent pour {key}.")
    if str(manifest.get("planner_builder_sha256") or "") != _sha256(Path(__file__)):
        raise ValueError("Le plan n'a pas été produit par le planner courant.")
    actual_design_hashes = {
        "paired_baseline_design": file_hashes["paired_baseline_design.csv"],
        "multi_lane_common_cause_design": file_hashes[
            "multi_lane_supplier_common_cause_design.csv"
        ],
        "temporal_robustness_design": file_hashes[
            "temporal_robustness_design.csv"
        ],
        "priority_four_business_causes_design": file_hashes[
            "priority_four_business_causes_design.csv"
        ],
        "causal_lot_attribution_design": file_hashes[
            "causal_lot_attribution_design.csv"
        ],
        "promotion_controls": file_hashes["promotion_controls.json"],
        "plan_readme_sha256": file_hashes["PLAN.md"],
    }
    if manifest.get("design_hashes") != actual_design_hashes:
        raise ValueError("Les design_hashes ne correspondent pas aux fichiers du plan.")
    source_dir = Path(str(manifest.get("source_artifact") or "")).resolve()
    source_paths = _required_source_paths(source_dir)
    if manifest.get("source_artifact_file_hashes") != _source_hashes(source_paths):
        raise ValueError("La campagne source ne correspond plus au plan.")

    lineage = manifest.get("priority_selection_lineage")
    if lineage:
        if str(lineage.get("contract_revision") or "") != CONTRACT_REVISION:
            raise ValueError("Révision de lignée priority absente ou inconnue.")
        digest = _lineage_digest(lineage)
        if str(lineage.get("priority_selection_lineage_sha256") or "") != digest:
            raise ValueError("Digest interne de lignée priority invalide.")
        if str(manifest.get("priority_selection_lineage_sha256") or "") != digest:
            raise ValueError("Digest top-level de lignée priority invalide.")
        boundary_dir = Path(str(lineage.get("priority_boundary_dir") or "")).resolve()
        source_manifest = _read_json(source_paths["campaign_manifest.json"])
        active_lanes = _load_active_lanes(source_paths["active_lane_reference.csv"])
        severe = _load_severe_scenarios(source_paths["scenario_design.csv"])
        _expected_priorities, expected_lineage = _boundary_priority_selection(
            artifact_dir=source_dir,
            boundary_dir=boundary_dir,
            source_manifest=source_manifest,
            active_lanes=active_lanes,
            severe_scenarios=severe,
        )
        if lineage != expected_lineage:
            raise ValueError("La lignée priority ne correspond pas à la boundary vivante.")
        # Rebuild every immutable design from the closed source and the live
        # boundary.  This rejects a self-consistent plan forgery where CSVs,
        # hashes and the local digest have all been rewritten together.
        context = load_complete_source(
            source_dir,
            priority_boundary_audit=boundary_dir,
        )
        expected_common = build_common_cause_design(context)
        expected_temporal = build_temporal_design(context)
        expected_four = build_four_cause_design(context)
        expected_causal = build_causal_lot_design(context)
        expected_baseline = build_baseline_design(context, expected_causal)
        expected_counts = _expected_counts(
            expected_baseline,
            expected_common,
            expected_temporal,
            expected_four,
            expected_causal,
        )
        expected_promotion = build_promotion_controls(context, expected_counts)
        expected_readme = _plan_text({"planned_case_counts": expected_counts})
        with tempfile.TemporaryDirectory(prefix="etudecas_plan_rebuild_") as temp_name:
            temp_dir = Path(temp_name)
            expected_files: dict[str, Any] = {
                "paired_baseline_design.csv": expected_baseline,
                "multi_lane_supplier_common_cause_design.csv": expected_common,
                "temporal_robustness_design.csv": expected_temporal,
                "priority_four_business_causes_design.csv": expected_four,
                "causal_lot_attribution_design.csv": expected_causal,
            }
            for name, rows in expected_files.items():
                _write_csv(temp_dir / name, rows)
            _write_json(temp_dir / "promotion_controls.json", expected_promotion)
            (temp_dir / "PLAN.md").write_text(expected_readme, encoding="utf-8")
            mismatched = [
                name
                for name in IMMUTABLE_PLAN_FILES
                if (temp_dir / name).read_bytes() != (output_dir / name).read_bytes()
            ]
        if mismatched:
            raise ValueError(
                "Le plan ne correspond pas à sa reconstruction déterministe: "
                + ", ".join(mismatched)
            )
    elif require_boundary_lineage:
        raise ValueError("Le plan publiable exige une lignée boundary recomposée.")
    return {
        "valid": True,
        "plan_signature": expected_signature,
        "status": "planned_not_executed",
        "execution_enabled": False,
        "priority_boundary_lineage_present": bool(lineage),
        "final_eligible": bool(lineage),
    }


def create_plan(
    *,
    network_artifact: Path,
    output_dir: Path | None = None,
    priority_boundary_audit: Path | None = None,
) -> Path:
    context = load_complete_source(
        network_artifact,
        priority_boundary_audit=priority_boundary_audit,
    )
    source_before = dict(context.source_hashes)
    common_rows = build_common_cause_design(context)
    temporal_rows = build_temporal_design(context)
    four_cause_rows = build_four_cause_design(context)
    causal_rows = build_causal_lot_design(context)
    baseline_rows = build_baseline_design(context, causal_rows)
    counts = _expected_counts(
        baseline_rows, common_rows, temporal_rows, four_cause_rows, causal_rows
    )
    promotion = build_promotion_controls(context, counts)
    plan_readme = _plan_text({"planned_case_counts": counts})
    execution_configuration_lock = {
        field: str(context.manifest.get(field) or "")
        for field in (
            "graph_sha256",
            "profile_sha256",
            "engine_sha256",
            "v4_extraction_core_sha256",
        )
    }
    execution_configuration_lock["scenario_id"] = "scn:BASE"
    if output_dir is None:
        output_dir = (
            context.artifact_dir.parent
            / "supplier_network_post_priority_extension_plans"
            / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "__planned")
        )
    output_dir = output_dir.resolve()
    try:
        output_dir.relative_to(context.artifact_dir)
    except ValueError:
        pass
    else:
        raise ValueError("Le plan additif doit être écrit hors du dossier réseau source.")
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(output_dir / "paired_baseline_design.csv", baseline_rows)
    _write_csv(
        output_dir / "multi_lane_supplier_common_cause_design.csv", common_rows
    )
    _write_csv(output_dir / "temporal_robustness_design.csv", temporal_rows)
    _write_csv(
        output_dir / "priority_four_business_causes_design.csv", four_cause_rows
    )
    _write_csv(output_dir / "causal_lot_attribution_design.csv", causal_rows)
    _write_json(output_dir / "promotion_controls.json", promotion)
    (output_dir / "PLAN.md").write_text(
        plan_readme, encoding="utf-8"
    )
    file_hashes = {
        name: _sha256(output_dir / name) for name in IMMUTABLE_PLAN_FILES
    }
    design_hashes = {
        "paired_baseline_design": file_hashes["paired_baseline_design.csv"],
        "multi_lane_common_cause_design": file_hashes[
            "multi_lane_supplier_common_cause_design.csv"
        ],
        "temporal_robustness_design": file_hashes[
            "temporal_robustness_design.csv"
        ],
        "priority_four_business_causes_design": file_hashes[
            "priority_four_business_causes_design.csv"
        ],
        "causal_lot_attribution_design": file_hashes[
            "causal_lot_attribution_design.csv"
        ],
        "promotion_controls": file_hashes["promotion_controls.json"],
        "plan_readme_sha256": file_hashes["PLAN.md"],
    }
    lineage = dict(context.priority_selection_lineage or {})
    lineage_digest = str(lineage.get("priority_selection_lineage_sha256") or "")
    contract_revision = CONTRACT_REVISION if lineage else "legacy_unlinked_test_only"
    planner_builder_sha256 = _sha256(Path(__file__))
    signature_payload = {
        "schema_version": SCHEMA_VERSION,
        "contract_revision": contract_revision,
        "planner_builder_sha256": planner_builder_sha256,
        "source_campaign_signature": str(
            context.manifest.get("campaign_signature") or ""
        ),
        "source_file_hashes": source_before,
        "confirmation_seeds": list(context.seeds),
        "calendar_windows": [list(window) for window in CALENDAR_WINDOWS],
        "multi_lane_supplier_ids": list(EXPECTED_MULTI_LANE_SUPPLIERS),
        "all_multi_lane_supplier_ids": lineage.get(
            "all_multi_lane_supplier_ids", []
        ),
        "all_multi_lane_supplier_active_chain_ids_by_id": lineage.get(
            "all_multi_lane_supplier_active_chain_ids_by_id", {}
        ),
        "priority_chain_ids": [str(row["chain_id"]) for row in context.priorities],
        "priority_selection_lineage": lineage or None,
        "priority_selection_lineage_sha256": lineage_digest,
        "temporal_horizon_contract": dict(context.temporal_horizon or {}),
        "design_hashes": design_hashes,
        "planned_case_counts": counts,
        "execution_configuration_lock": execution_configuration_lock,
        "execution_enabled": False,
    }
    signature = _canonical_signature(signature_payload)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "contract_revision": contract_revision,
        "planner_builder_sha256": planner_builder_sha256,
        "status": "planned_not_executed",
        "created_at_utc": _utc_now(),
        "plan_signature": signature,
        "signature_payload": signature_payload,
        "plan_file_hashes": file_hashes,
        "output_dir": str(output_dir),
        "source_artifact": str(context.artifact_dir),
        "source_campaign_signature": str(
            context.manifest.get("campaign_signature") or ""
        ),
        "source_artifact_file_hashes": source_before,
        "confirmation_seeds": list(context.seeds),
        "calendar_windows": [list(window) for window in CALENDAR_WINDOWS],
        "multi_lane_supplier_ids": list(EXPECTED_MULTI_LANE_SUPPLIERS),
        "all_multi_lane_supplier_ids": lineage.get(
            "all_multi_lane_supplier_ids", []
        ),
        "all_multi_lane_supplier_active_chain_ids_by_id": lineage.get(
            "all_multi_lane_supplier_active_chain_ids_by_id", {}
        ),
        "priority_chain_ids": [str(row["chain_id"]) for row in context.priorities],
        "priority_selection_lineage": lineage or None,
        "priority_selection_lineage_sha256": lineage_digest,
        "temporal_horizon_contract": dict(context.temporal_horizon or {}),
        "design_hashes": design_hashes,
        "source_artifact_mutated": False,
        "previous_artifacts_mutated": False,
        "main_lane_ranking_mutated": False,
        "execution_enabled": False,
        "subprocess_or_engine_call_present": False,
        "planned_case_counts": counts,
        "execution_configuration_lock": execution_configuration_lock,
        "reuse_rule": (
            "cas source réutilisé seulement si graphe, profil, moteur, graine, état J0, "
            "entrée et réglage de traçage lots sont strictement identiques"
        ),
        "source_gate_state": dict(context.source_gate_state),
        "promotion_status": "not_promotable_from_plan",
        "scoped_descriptive_priority_set_display_allowed": bool(
            lineage.get("scoped_descriptive_priority_set_display_allowed")
        ),
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "evidence_meaning": (
            "plan de simulations conditionnelles; aucune probabilité fournisseur estimée"
        ),
        "dynamic_model_scope": (
            "moteur supply dynamique par stocks, retards et calcul des besoins; incidents "
            "exogènes; risques endogènes dépendant de l'état et pilotage automatique en "
            "boucle fermée non revendiqués dans ce plan"
        ),
        "unit_contract": (
            "les futures quantités doivent rester par unité; aucun total brut inter-unités"
        ),
        "low_sample_reporting_contract": (
            "aucun percentile inférieur publié avec moins de 100 réalisations"
        ),
        "genealogy_contract": (
            "descendants exposés = borne haute; les identifiants techniques du moteur ne "
            "prouvent pas l'identité contrefactuelle d'un même lot"
        ),
        "counterfactual_entity_identity_validated": False,
        "network_recovery_metric_status": "excluded_invalid_common_window",
    }
    _write_json(output_dir / "post_priority_extensions_plan_manifest.json", manifest)
    paths = _required_source_paths(context.artifact_dir)
    source_after = _source_hashes(paths)
    if source_after != source_before:
        raise RuntimeError("Le dossier réseau source a changé pendant la création du plan.")
    validate_plan_artifact(
        output_dir,
        require_boundary_lineage=priority_boundary_audit is not None,
    )
    return output_dir


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network-artifact", type=Path, default=None)
    parser.add_argument("--priority-boundary-audit", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--validate-plan",
        type=Path,
        default=None,
        help="Valider un plan existant sans écrire ni exécuter de simulation.",
    )
    parser.add_argument(
        "--allow-legacy-unlinked-plan",
        action="store_true",
        help="Validation de compatibilité seulement; jamais éligible au paquet final.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.validate_plan is not None:
        result = validate_plan_artifact(
            args.validate_plan,
            require_boundary_lineage=not args.allow_legacy_unlinked_plan,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0
    if args.network_artifact is None:
        raise ValueError("--network-artifact est requis pour créer un plan.")
    if args.priority_boundary_audit is None:
        raise ValueError(
            "--priority-boundary-audit est requis pour un plan exécutable publiable."
        )
    output_dir = create_plan(
        network_artifact=args.network_artifact,
        output_dir=args.output_dir,
        priority_boundary_audit=args.priority_boundary_audit,
    )
    print(
        json.dumps(
            {
                "status": "planned_not_executed",
                "output_dir": str(output_dir),
                "execution_enabled": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
