"""Shared campaign mechanics with an explicit, version-owned dependency context.

Scientific constants and helpers stay in each V2/V4 policy module. A context
reads that module's live namespace, preserving scoped adapter patches. No code
is evaluated dynamically and no historical source identity is substituted.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd

    from etudecas.prototypes.scan_2027_risk_control.finalize_supplier_operating_point_full_campaign_v2 import (
        InputEvidence,
    )
    from etudecas.prototypes.scan_2027_risk_control.launch_supplier_operating_point_full_campaign_v2 import (
        ActiveShard,
        Shard,
    )
    from etudecas.prototypes.scan_2027_risk_control.supplier_operating_point_full_campaign_v2 import (
        Lane,
        Mechanism,
    )


class Context:
    """Read current helpers/constants from one version's namespace."""

    def __init__(self, namespace: Mapping[str, Any]) -> None:
        self._namespace = namespace

    def __getattr__(self, name: str) -> Any:
        try:
            return self._namespace[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _validate_client_service_horizon(
    rows: Sequence[Mapping[str, Any]], *, days: int, context: Context
) -> None:
    indexed: set[tuple[str, int]] = set()
    for row in rows:
        if str(row.get("node_id") or "") != context.protocol.CLIENT_NODE_ID:
            continue
        product = str(row.get("item_id") or "").replace("item:", "")
        if product not in context.TARGET_PRODUCTS:
            continue
        day = context._as_int(row.get("day"), -1)
        key = (product, day)
        if key in indexed:
            raise ValueError(f"Duplicate product/day service row: {key}")
        indexed.add(key)
        for field in (
            "demand_qty",
            "required_with_backlog_qty",
            "served_qty",
            "backlog_end_qty",
        ):
            value = context._as_float(row.get(field))
            if not context.math.isfinite(value) or value < 0.0:
                raise ValueError(f"Invalid {field} in product/day service row: {key}")
        if context._as_float(row.get("required_with_backlog_qty")) + 1e-9 < context._as_float(
            row.get("demand_qty")
        ):
            raise ValueError(f"Required quantity below current demand: {key}")
    expected = {(product, day) for product in context.TARGET_PRODUCTS for day in range(days)}
    if indexed != expected:
        raise ValueError(f"Product/day service matrix is not exactly 2 x {days}")


def _validate_production_horizon(
    rows: Sequence[Mapping[str, Any]], *, days: int, context: Context
) -> None:
    for product, factory in context.PRODUCT_FACTORY.items():
        selected_days = [
            context._as_int(row.get("day"), -1)
            for row in rows
            if str(row.get("node_id") or "") == factory
            and str(row.get("item_id") or "") == f"item:{product}"
        ]
        if len(selected_days) != days or set(selected_days) != set(range(days)):
            raise ValueError(
                f"Incomplete production horizon for {factory}/item:{product}"
            )


def _window_metrics(
    *,
    service_rows: Sequence[Mapping[str, Any]],
    production_rows: Sequence[Mapping[str, Any]],
    start_day: int,
    end_day: int,
    context: Context,
) -> dict[str, Any]:
    if start_day < 0 or end_day < start_day:
        raise ValueError("Impact window is outside the simulated horizon")
    expected_days = set(range(start_day, end_day + 1))
    product_metrics: dict[str, dict[str, Any]] = {}
    total_demand = 0.0
    total_on_due = 0.0
    total_backlog_by_day: dict[int, float] = context.defaultdict(float)
    for product in context.TARGET_PRODUCTS:
        selected = [
            row
            for row in service_rows
            if str(row.get("node_id") or "") == context.protocol.CLIENT_NODE_ID
            and str(row.get("item_id") or "").replace("item:", "") == product
            and start_day <= context._as_int(row.get("day"), -1) <= end_day
        ]
        if {context._as_int(row.get("day"), -1) for row in selected} != expected_days or len(
            selected
        ) != len(expected_days):
            raise ValueError(f"Incomplete service impact window for product {product}")
        demand = 0.0
        on_due = 0.0
        backlog_qty_days = 0.0
        backlog_by_day: dict[int, float] = {}
        for row in selected:
            day = context._as_int(row.get("day"))
            daily_demand = max(0.0, context._as_float(row.get("demand_qty"), 0.0))
            served = max(0.0, context._as_float(row.get("served_qty"), 0.0))
            required = max(
                daily_demand,
                context._as_float(row.get("required_with_backlog_qty"), daily_demand),
            )
            starting_backlog = max(0.0, required - daily_demand)
            daily_on_due = min(daily_demand, max(0.0, served - starting_backlog))
            ending_backlog = max(0.0, context._as_float(row.get("backlog_end_qty"), 0.0))
            demand += daily_demand
            on_due += daily_on_due
            backlog_qty_days += ending_backlog
            backlog_by_day[day] = ending_backlog
            total_backlog_by_day[day] += ending_backlog
        production_selected = [
            row
            for row in production_rows
            if str(row.get("node_id") or "") == context.PRODUCT_FACTORY[product]
            and str(row.get("item_id") or "") == f"item:{product}"
            and start_day <= context._as_int(row.get("day"), -1) <= end_day
        ]
        if {
            context._as_int(row.get("day"), -1) for row in production_selected
        } != expected_days or len(production_selected) != len(expected_days):
            raise ValueError(
                f"Incomplete production impact window for product {product}"
            )
        product_metrics[product] = {
            "demand_qty": demand,
            "on_due_qty": on_due,
            "service_pct": 100.0 * on_due / demand if demand > 1e-12 else 100.0,
            "backlog_qty_days": backlog_qty_days,
            "max_backlog_qty": max(backlog_by_day.values(), default=0.0),
            "ending_backlog_qty": backlog_by_day.get(end_day, 0.0),
            "production_released_qty": sum(
                max(0.0, context._as_float(row.get("released_qty"), 0.0))
                for row in production_selected
            ),
        }
        total_demand += demand
        total_on_due += on_due
    return {
        "start_day": start_day,
        "end_day": end_day,
        "day_count": end_day - start_day + 1,
        "fully_observed": True,
        "demand_qty_268091": product_metrics["268091"]["demand_qty"],
        "demand_qty_268967": product_metrics["268967"]["demand_qty"],
        "demand_qty_global": total_demand,
        "on_due_qty_268091": product_metrics["268091"]["on_due_qty"],
        "on_due_qty_268967": product_metrics["268967"]["on_due_qty"],
        "on_due_qty_global": total_on_due,
        "service_268091_pct": product_metrics["268091"]["service_pct"],
        "service_268967_pct": product_metrics["268967"]["service_pct"],
        "service_global_pct": (
            100.0 * total_on_due / total_demand if total_demand > 1e-12 else 100.0
        ),
        "backlog_qty_days_268091": product_metrics["268091"]["backlog_qty_days"],
        "backlog_qty_days_268967": product_metrics["268967"]["backlog_qty_days"],
        "max_backlog_qty_268091": product_metrics["268091"]["max_backlog_qty"],
        "max_backlog_qty_268967": product_metrics["268967"]["max_backlog_qty"],
        "backlog_qty_days_global": sum(total_backlog_by_day.values()),
        "backlog_day_count_global": sum(
            value > 1e-9 for value in total_backlog_by_day.values()
        ),
        "max_backlog_qty_global": max(total_backlog_by_day.values(), default=0.0),
        "ending_backlog_qty_global": total_backlog_by_day.get(end_day, 0.0),
        "production_released_268091_qty": product_metrics["268091"][
            "production_released_qty"
        ],
        "production_released_268967_qty": product_metrics["268967"][
            "production_released_qty"
        ],
    }


def _required_campaign_holdout_contract(
    *,
    context: Context,
) -> dict[str, Any]:
    expected_window = {
        "start_day": 0,
        "end_day": context.STATE_EVALUATION_DAYS - 1,
        "day_count": context.STATE_EVALUATION_DAYS,
    }
    return {
        "status_only_if_passed": context.HOLDOUT_ACCEPTED_STATUS,
        "fixed_point_count": len(context.OPERATING_POINT_IDS),
        "seed_count": len(context.SEEDS),
        "baseline_case_count": len(context.OPERATING_POINT_IDS) * len(context.SEEDS),
        "seeds": list(context.SEEDS),
        "service_window": expected_window,
        "op100_minimum_global_and_each_product": 0.985,
        "op93_global_pooled_and_median_band": [0.915, 0.945],
        "op80_global_pooled_and_median_band": [0.785, 0.815],
        "degraded_product_strictly_below": 0.995,
        "pooled_strict_order_required_for": [
            "system_on_due_service",
            "on_due_service_268091",
            "on_due_service_268967",
        ],
        "same_seed_joint_strict_order_required": 24,
        "bootstrap_repetitions_descriptive": context.PREFLIGHT_BOOTSTRAP_REPLICATES,
        "retuning_after_holdout": False,
    }


def _validate_pending_multiseed_v1_source(
    path: Path,
    payload: Mapping[str, Any],
    *,
    context: Context,
) -> dict[str, Any]:
    """Validate the pending five-seed selection and its signed source chain.

    The 30 campaign seeds are deliberately still sealed at this point.  The
    campaign discovery is their one holdout use; accepting a stand-alone JSON
    without its signed calibration plan/selection would make that separation
    impossible to audit.
    """

    # Lazy import avoids a cycle while the additive calibration producer reuses
    # the legacy non-strict operating-point loader from this module.
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_calibration as multiseed_calibration,
    )

    if (
        payload.get("schema_version") != context.V1_POINTS_SCHEMA_VERSION
        or payload.get("status") != context.V1_POINTS_PENDING_STATUS
    ):
        raise ValueError("Pending V1 operating-point schema/status mismatch")
    plan_reference = payload.get("plan")
    if not isinstance(plan_reference, context.Mapping):
        raise ValueError("Multi-seed operating points have no signed plan reference")
    plan_dir_raw = str(plan_reference.get("path") or "").strip()
    if not plan_dir_raw:
        raise ValueError("Multi-seed operating points have no calibration plan path")
    plan_dir = context.Path(plan_dir_raw)
    if not plan_dir.is_absolute():
        plan_dir = path.parent / plan_dir
    plan = multiseed_calibration.validate_plan(plan_dir.resolve())
    plan_manifest = plan.manifest
    if (
        str(plan_reference.get("plan_signature") or "")
        != str(plan_manifest.get("plan_signature") or "")
        or payload.get("source_hashes") != plan_manifest.get("source_hashes")
        or payload.get("cohorts") != plan_manifest.get("cohorts")
    ):
        raise ValueError("Multi-seed selection does not match its signed source plan")

    expected_window = {
        "start_day": 0,
        "end_day": context.STATE_EVALUATION_DAYS - 1,
        "day_count": context.STATE_EVALUATION_DAYS,
    }
    holdout_contract = dict(plan_manifest.get("holdout_contract") or {})
    required_holdout_contract = context._required_campaign_holdout_contract()
    changed_holdout_fields = [
        field
        for field, expected in required_holdout_contract.items()
        if holdout_contract.get(field) != expected
    ]
    if changed_holdout_fields:
        raise ValueError(
            "Signed calibration holdout contract is incompatible: "
            + ", ".join(changed_holdout_fields)
        )
    selection_contract = dict(plan_manifest.get("selection_contract") or {})
    if (
        selection_contract.get("no_holdout_retuning") is not True
        or selection_contract.get("global_median_must_also_be_in_target_band")
        is not True
    ):
        raise ValueError("Signed calibration does not preserve the sealed holdout")
    if payload.get("service_evaluation_window") != expected_window:
        raise ValueError("Selected operating-point service window changed")

    selection_path = path.parent / "selection.json"
    if not selection_path.is_file():
        raise FileNotFoundError(
            f"Missing signed multi-seed selection evidence: {selection_path}"
        )
    selection = context._read_json(selection_path)
    unsigned_selection = dict(selection)
    selection_signature = str(unsigned_selection.pop("selection_signature", ""))
    if (
        not selection_signature
        or selection_signature != context._stable_sha256(unsigned_selection)
        or selection_signature != str(payload.get("selection_signature") or "")
        or selection.get("schema_version")
        != multiseed_calibration.SELECTION_SCHEMA_VERSION
        or selection.get("status") != "calibration_selected"
        or selection.get("plan_signature") != plan_manifest.get("plan_signature")
        or selection.get("calibration_seeds")
        != list(multiseed_calibration.CALIBRATION_SEEDS)
        or selection.get("holdout_seeds_sealed_and_unread") != list(context.SEEDS)
        or selection.get("selection_contract")
        != plan_manifest.get("selection_contract")
        or selection.get("fallback_required") is not False
    ):
        raise ValueError("Multi-seed selection evidence/signature is invalid")
    selected_pair = selection.get("selected_pair")
    if not isinstance(selected_pair, context.Mapping):
        raise ValueError("Multi-seed selection has no selected operating-point pair")
    candidate_by_point = {
        str(point.get("operating_point_id") or ""): str(
            point.get("candidate_key") or ""
        )
        for point in payload.get("operating_points") or []
        if isinstance(point, context.Mapping)
    }
    if (
        candidate_by_point.get("op_100") != "op100_reference"
        or candidate_by_point.get("op_93")
        != str(selected_pair.get("op93_candidate_key") or "")
        or candidate_by_point.get("op_80")
        != str(selected_pair.get("op80_candidate_key") or "")
    ):
        raise ValueError("Selected operating points differ from selection evidence")
    return {
        "producer": "v1_calibration",
        "plan_path": str(plan.plan_dir.resolve()),
        "plan_manifest_path": str((plan.plan_dir / "calibration_plan.json").resolve()),
        "plan_signature": str(plan_manifest["plan_signature"]),
        "selection_path": str(selection_path.resolve()),
        "selection_signature": selection_signature,
        "holdout_contract": holdout_contract,
    }


def _validate_pending_multiseed_v2_source(
    path: Path,
    payload: Mapping[str, Any],
    *,
    context: Context,
) -> dict[str, Any]:
    """Delegate V2 proof validation to its producer without a module cycle."""

    # The refinement imports the V1 producer, whose prevalidation layer imports
    # this campaign module.  Importing only at call time keeps that chain acyclic
    # during module initialization.
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_refinement_v2 as refinement_v2,
    )

    if (
        payload.get("schema_version") != refinement_v2.POINTS_SCHEMA_VERSION
        or payload.get("schema_version") != context.V2_POINTS_SCHEMA_VERSION
        or payload.get("status") != context.V2_POINTS_PENDING_STATUS
    ):
        raise ValueError("Pending V2 operating-point schema/status mismatch")
    validated = refinement_v2.validate_selected_operating_points(path)
    if validated != payload:
        raise ValueError("V2 producer validation returned different operating points")
    plan_reference = payload.get("plan")
    if not isinstance(plan_reference, context.Mapping):
        raise ValueError("V2 operating points have no signed refinement plan")
    plan_path = context.Path(str(plan_reference.get("path") or ""))
    if not plan_path.is_absolute():
        plan_path = path.parent / plan_path
    plan = refinement_v2.validate_plan(plan_path.resolve())
    plan_manifest = plan.manifest
    holdout_contract = dict(plan_manifest.get("holdout_contract") or {})
    incompatible = [
        field
        for field, expected in context._required_campaign_holdout_contract().items()
        if holdout_contract.get(field) != expected
    ]
    if incompatible:
        raise ValueError(
            "Signed V2 refinement holdout contract is incompatible: "
            + ", ".join(incompatible)
        )
    if (
        holdout_contract.get("status") != "sealed_unread"
        or holdout_contract.get("cases_in_this_plan") != 0
        or payload.get("holdout_cases_read") != 0
        or payload.get("holdout_contract") != holdout_contract
        or payload.get("target_labels_apply_to_global_service_only") is not True
    ):
        raise ValueError("V2 refinement does not preserve the sealed holdout")
    selection_reference = payload.get("selection")
    if not isinstance(selection_reference, context.Mapping):
        raise ValueError("V2 operating points have no signed selection reference")
    relative_selection = context.Path(str(selection_reference.get("relative_path") or ""))
    selection_path = (path.parent / relative_selection).resolve()
    plan_manifest_path = (plan.plan_dir / "refinement_plan.json").resolve()
    if not plan_manifest_path.is_file() or not selection_path.is_file():
        raise FileNotFoundError("Signed V2 refinement plan/selection disappeared")
    return {
        "producer": "v2_refinement",
        "plan_path": str(plan.plan_dir.resolve()),
        "plan_manifest_path": str(plan_manifest_path),
        "plan_signature": str(plan_manifest["plan_signature"]),
        "selection_path": str(selection_path),
        "selection_signature": str(payload["selection_signature"]),
        "holdout_contract": holdout_contract,
    }


def _validate_pending_multiseed_v3_source(
    path: Path,
    payload: Mapping[str, Any],
    *,
    context: Context,
) -> dict[str, Any]:
    """Validate the frozen V3 producer and independently cross-check its chain."""

    # V3 imports V2, which eventually reaches this campaign module through the
    # legacy prevalidation dependency.  Keep this import local to avoid a cycle
    # while this module initializes.
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_refinement_v3 as refinement_v3,
    )

    producer_module = context.Path(refinement_v3.__file__).resolve()
    producer_module_sha256 = context._sha256_file(producer_module)
    if producer_module_sha256 != context.V3_REFINEMENT_MODULE_SHA256:
        raise ValueError("Frozen V3 refinement producer hash changed")
    if (
        refinement_v3.POINTS_SCHEMA_VERSION != context.V3_POINTS_SCHEMA_VERSION
        or refinement_v3.POINTS_STATUS != context.V3_POINTS_PENDING_STATUS
        or refinement_v3.SELECTION_PASS_STATUS != context.V3_SELECTION_PASS_STATUS
        or payload.get("schema_version") != context.V3_POINTS_SCHEMA_VERSION
        or payload.get("status") != context.V3_POINTS_PENDING_STATUS
    ):
        raise ValueError("Pending V3 operating-point schema/status mismatch")

    # This call revalidates the complete 80-proof run, including the signed V2
    # 65-proof NO-GO source.  The checks below deliberately recut the provenance
    # fields consumed by the full-campaign manifest instead of trusting only the
    # producer's return value.
    validated = refinement_v3.validate_selected_operating_points(path)
    if validated != payload:
        raise ValueError("V3 producer validation returned different operating points")

    plan_reference = payload.get("plan")
    if not isinstance(plan_reference, context.Mapping):
        raise ValueError("V3 operating points have no signed refinement plan")
    plan_path_raw = str(plan_reference.get("path") or "").strip()
    if not plan_path_raw:
        raise ValueError("V3 operating points have no refinement plan path")
    plan_path = context.Path(plan_path_raw)
    if not plan_path.is_absolute():
        plan_path = path.parent / plan_path
    plan = refinement_v3.validate_plan(plan_path.resolve())
    plan_manifest = plan.manifest
    plan_manifest_path = (plan.plan_dir / "refinement_plan.json").resolve()
    if not plan_manifest_path.is_file():
        raise FileNotFoundError("Signed V3 refinement plan disappeared")
    if (
        str(plan_reference.get("plan_signature") or "")
        != str(plan_manifest.get("plan_signature") or "")
        or payload.get("source_hashes") != plan_manifest.get("source_hashes")
        or payload.get("cohorts") != plan_manifest.get("cohorts")
        or dict(plan_manifest.get("source_hashes") or {}).get("v3_driver_sha256")
        != producer_module_sha256
    ):
        raise ValueError("V3 selected points do not match their signed source plan")

    holdout_contract = dict(plan_manifest.get("holdout_contract") or {})
    incompatible = [
        field
        for field, expected in context._required_campaign_holdout_contract().items()
        if holdout_contract.get(field) != expected
    ]
    if incompatible:
        raise ValueError(
            "Signed V3 refinement holdout contract is incompatible: "
            + ", ".join(incompatible)
        )
    if (
        holdout_contract.get("status") != "sealed_unread"
        or holdout_contract.get("cases_in_this_plan") != 0
        or holdout_contract.get("selected_output_status") != context.V3_POINTS_PENDING_STATUS
        or payload.get("holdout_cases_read") != 0
        or payload.get("holdout_contract") != holdout_contract
        or payload.get("target_labels_apply_to_global_service_only") is not True
    ):
        raise ValueError("V3 refinement does not preserve the sealed holdout")

    selection_reference = payload.get("selection")
    if not isinstance(selection_reference, context.Mapping):
        raise ValueError("V3 operating points have no signed selection reference")
    if (
        selection_reference.get("relative_path") != "selection.json"
        or selection_reference.get("schema_version")
        != refinement_v3.SELECTION_SCHEMA_VERSION
    ):
        raise ValueError("V3 operating points do not reference the sibling selection")
    selection_path = (path.parent / "selection.json").resolve()
    if not selection_path.is_file():
        raise FileNotFoundError("Signed V3 refinement selection disappeared")
    selection = context._read_json(selection_path)
    unsigned_selection = dict(selection)
    selection_signature = str(unsigned_selection.pop("selection_signature", ""))
    selected_pair = selection.get("selected_pair")
    eligible_pairs = selection.get("eligible_pairs")
    if (
        not selection_signature
        or selection_signature != context._stable_sha256(unsigned_selection)
        or selection_signature != str(payload.get("selection_signature") or "")
        or selection_signature
        != str(selection_reference.get("selection_signature") or "")
        or selection.get("schema_version") != refinement_v3.SELECTION_SCHEMA_VERSION
        or selection.get("status") != context.V3_SELECTION_PASS_STATUS
        or selection.get("plan_signature") != plan_manifest.get("plan_signature")
        or selection.get("calibration_seeds") != list(context.CALIBRATION_SEEDS)
        or selection.get("holdout_seeds_sealed_and_unread") != list(context.SEEDS)
        or selection.get("holdout_cases_read") != 0
        or selection.get("selection_contract")
        != plan_manifest.get("selection_contract")
        or selection.get("holdout_contract") != holdout_contract
        or selection.get("holdout_launch_permitted") is not True
        or selection.get("fallback_required") is not False
        or not isinstance(selected_pair, context.Mapping)
        or not isinstance(eligible_pairs, list)
        or not eligible_pairs
        or selected_pair != eligible_pairs[0]
    ):
        raise ValueError("V3 selection evidence/status/signature is invalid")

    candidate_by_point = {
        str(point.get("operating_point_id") or ""): str(
            point.get("candidate_key") or ""
        )
        for point in payload.get("operating_points") or []
        if isinstance(point, context.Mapping)
    }
    if (
        candidate_by_point.get("op_100") != refinement_v3.FIXED_REFERENCE_KEY
        or candidate_by_point.get("op_93") != refinement_v3.FIXED_OP93_KEY
        or candidate_by_point.get("op_80")
        != str(selected_pair.get("op80_candidate_key") or "")
        or str(selected_pair.get("op93_candidate_key") or "")
        != refinement_v3.FIXED_OP93_KEY
    ):
        raise ValueError("V3 selected operating points differ from selection evidence")

    return {
        "producer": "v3_refinement",
        "plan_path": str(plan.plan_dir.resolve()),
        "plan_manifest_path": str(plan_manifest_path),
        "plan_signature": str(plan_manifest["plan_signature"]),
        "selection_path": str(selection_path),
        "selection_signature": selection_signature,
        "holdout_contract": holdout_contract,
    }


def load_operating_points(
    path: Path,
    *,
    require_prevalidated: bool = True,
    context: Context,
) -> list[dict[str, Any]]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Missing operating points: {path}")
    payload = context._read_json(path)
    if require_prevalidated:
        context._validate_pending_multiseed_source(path, payload)
    else:
        if payload.get("quality_branch_included") is not False:
            raise ValueError(
                "Operating points must explicitly exclude the quality branch"
            )
        if payload.get("supplier_state_dependent_risks_enabled") is not False:
            raise ValueError(
                "Operating points must explicitly disable state-dependent risks"
            )
        if payload.get("acute_incident_included_in_operating_point") is not False:
            raise ValueError(
                "Operating points must not already contain an acute incident"
            )
    raw_points = [dict(value) for value in payload.get("operating_points") or []]
    by_id = {str(value.get("operating_point_id") or ""): value for value in raw_points}
    if set(by_id) != set(context.OPERATING_POINT_IDS) or len(raw_points) != len(
        context.OPERATING_POINT_IDS
    ):
        raise ValueError("Exactly op_100, op_93 and op_80 are required")
    points: list[dict[str, Any]] = []
    for point_id in context.OPERATING_POINT_IDS:
        point = by_id[point_id]
        graph = context.Path(str(point.get("graph") or "")).resolve()
        floors_raw = str(point.get("supplier_floors") or "").strip()
        floors = context.Path(floors_raw).resolve() if floors_raw else None
        factory_raw = str(point.get("factory_capacities") or "").strip()
        factory = context.Path(factory_raw).resolve() if factory_raw else None
        if not graph.is_file():
            raise FileNotFoundError(f"Missing graph input for {point_id}: {graph}")
        graph_sha256 = context._sha256_file(graph)
        if (
            require_prevalidated
            and str(point.get("graph_sha256") or "") != graph_sha256
        ):
            raise ValueError(f"Signed graph hash changed for {point_id}")
        for field in (
            "target_service",
            "calibration_pooled_service",
            "calibration_product_268091_service",
            "calibration_product_268967_service",
            "offset_days_268091",
            "offset_days_268967",
        ):
            if require_prevalidated and not context.math.isfinite(context._as_float(point.get(field))):
                raise ValueError(f"Missing finite {field} for {point_id}")
        if floors is not None and not floors.is_file():
            raise FileNotFoundError(f"Missing supplier floors for {point_id}: {floors}")
        if factory is not None and not factory.is_file():
            raise FileNotFoundError(
                f"Missing factory capacities for {point_id}: {factory}"
            )
        degradation_family = str(point.get("degradation_family") or "")
        if require_prevalidated and not degradation_family:
            degradation_family = (
                "baseline"
                if point_id == "op_100"
                else "balanced_product_supplier_planned_lead"
            )
        if (
            point_id != "op_100"
            and degradation_family not in context.ALLOWED_OPERATING_POINT_DEGRADATION_FAMILIES
        ):
            raise ValueError(
                "The degraded points must use an allowed structural supplier "
                "family (planned lead, balanced product-specific planned lead, "
                "or nominal delivery reliability)"
            )
        normalized = dict(point)
        normalized.update(
            {
                "degradation_family": degradation_family,
                "graph": str(graph),
                "graph_sha256": graph_sha256,
                "supplier_floors": str(floors) if floors is not None else "",
                "supplier_floors_sha256": context._sha256_file(floors)
                if floors is not None
                else "",
                "factory_capacities": str(factory) if factory is not None else "",
                "factory_capacities_sha256": context._sha256_file(factory)
                if factory is not None
                else "",
                "operating_point_service_pct": context._operating_point_service_pct(point),
            }
        )
        points.append(normalized)
    degraded_families = {
        str(point["degradation_family"])
        for point in points
        if point["operating_point_id"] != "op_100"
    }
    if len(degraded_families) != 1:
        raise ValueError("op_93 and op_80 must share one structural degradation family")
    return points


def load_lanes(
    path: Path,
    *,
    context: Context,
) -> list[Lane]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Missing lane reference: {path}")
    lanes: list[context.Lane] = []
    for row in context._read_csv(path):
        if str(row.get("scope_status") or "") != "active_simulated_reference_v10":
            continue
        lane = context.Lane(
            lane_id=str(row.get("chain_id") or "").strip(),
            supplier_id=str(row.get("supplier_id") or "").strip(),
            item_id=str(row.get("item_id") or "").strip(),
            dst_node_id=str(row.get("dst_node_id") or "").strip(),
            edge_id=str(row.get("edge_id") or "").strip(),
            target_product_id=str(row.get("target_product_id") or "").strip(),
            planned_lead_days=context._as_float(row.get("planned_lead_days")),
        )
        if not all(
            (
                lane.lane_id,
                lane.supplier_id,
                lane.item_id,
                lane.dst_node_id,
                lane.edge_id,
                lane.target_product_id,
            )
        ) or not context.math.isfinite(lane.planned_lead_days):
            raise ValueError(f"Incomplete active lane: {row}")
        if not lane.item_id.startswith("item:"):
            raise ValueError(f"Lane item must be normalized: {lane.item_id}")
        lanes.append(lane)
    if len(lanes) != 18:
        raise ValueError(f"Expected exactly 18 active lanes; found {len(lanes)}")
    if (
        len({lane.lane_id for lane in lanes}) != 18
        or len({lane.key for lane in lanes}) != 18
    ):
        raise ValueError("Lane identities are not unique")
    return sorted(lanes, key=lambda lane: lane.lane_id)


def _lane_day_quantity_map(
    rows: Iterable[Mapping[str, Any]],
    *,
    lane: Lane,
    context: Context,
) -> dict[int, float]:
    quantities: dict[int, float] = context.defaultdict(float)
    for row in rows:
        if not context._lane_matches(row, lane):
            continue
        day = context._as_int(row.get("risk_decision_day"), -1)
        pulled = context._as_float(row.get("pulled_qty"), 0.0)
        shipped = context._as_float(row.get("shipped_qty"), 0.0)
        if (
            0 <= day < context.STATE_EVALUATION_DAYS
            and pulled > 1e-12
            and shipped > 1e-12
            and str(row.get("shipment_id") or "").strip()
        ):
            quantities[day] += shipped
    return dict(quantities)


def _validate_evidence(
    evidence: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    case_key: str,
    case_signature: str,
    context: Context,
) -> None:
    errors: list[str] = []
    if evidence.get("schema_version") != context.CASE_SCHEMA_VERSION:
        errors.append("schema_version")
    if evidence.get("campaign_signature") != manifest.get("campaign_signature"):
        errors.append("campaign_signature")
    if evidence.get("engine_sha256") != manifest.get("engine_sha256"):
        errors.append("engine_sha256")
    if evidence.get("case_key") != case_key:
        errors.append("case_key")
    if evidence.get("case_signature") != case_signature:
        errors.append("case_signature")
    if not evidence.get("evidence_signature") or evidence.get(
        "evidence_signature"
    ) != context._evidence_signature(evidence):
        errors.append("evidence_signature")
    if evidence.get("quality_branch_included") is not False:
        errors.append("quality_branch_included")
    if evidence.get("availability_incident_included") is not False:
        errors.append("availability_incident_included")
    if evidence.get("supplier_state_dependent_risks_enabled") is not False:
        errors.append("supplier_state_dependent_risks_enabled")
    if str(evidence.get("status") or "") not in {
        "valid",
        "valid_no_exposure",
        "not_applicable",
        "invalid",
    }:
        errors.append("status")
    if errors:
        raise ValueError(f"Evidence fails closed for {case_key}: " + ", ".join(errors))


def _extract_metrics(
    *,
    case_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    risk_csv: Path | None,
    expected_event_id: str | None,
    simulation_days: int,
    context: Context,
) -> tuple[
    dict[str, Any],
    list[dict[str, str]],
    list[dict[str, str]],
    list[str],
    dict[str, list[dict[str, str]]],
]:
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    service_path = case_dir / "data" / "production_demand_service_daily.csv"
    production_path = case_dir / "data" / "production_output_products_daily.csv"
    shipment_path = case_dir / "data" / "production_supplier_shipments_daily.csv"
    required = (summary_path, service_path, production_path, shipment_path)
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Missing engine evidence: {path}")
    summary = context._read_json(summary_path)
    service_rows = context.protocol.read_csv_rows(service_path)
    production_rows = context.protocol.read_csv_rows(production_path)
    shipment_rows = context.protocol.read_csv_rows(shipment_path)
    if simulation_days < context.STATE_EVALUATION_DAYS:
        raise ValueError("Measured engine horizon is shorter than the state window")
    context._validate_client_service_horizon(service_rows, days=simulation_days)
    context._validate_production_horizon(production_rows, days=simulation_days)
    state_service_rows = [
        row
        for row in service_rows
        if 0 <= context._as_int(row.get("day"), -1) < context.STATE_EVALUATION_DAYS
    ]
    service = context.protocol.service_from_daily_rows(
        state_service_rows, days=context.STATE_EVALUATION_DAYS
    )
    state_window = context._window_metrics(
        service_rows=service_rows,
        production_rows=production_rows,
        start_day=0,
        end_day=context.STATE_EVALUATION_DAYS - 1,
    )
    policy = summary.get("policy") or {}
    supplier_risk = policy.get("supplier_risk") or {}
    state_risk = policy.get("supplier_state_dependent_risk") or {}
    economic = policy.get("economic_policy") or {}
    initialization = policy.get("initialization_policy") or {}
    warmup = policy.get("warmup_boundary_audit") or {}
    kpis = summary.get("kpis") or {}
    errors: list[str] = []
    if str(summary.get("input_sha256") or "") != str(point["graph_sha256"]):
        errors.append("engine input graph SHA-256 mismatch")
    if int(summary.get("sim_days") or -1) != simulation_days:
        errors.append("engine measured horizon mismatch")
    if int(policy.get("warmup_days") or -1) != context.protocol.WARMUP_DAYS:
        errors.append("engine warmup mismatch")
    if not str(warmup.get("core_state_sha256") or ""):
        errors.append("missing warmup core-state SHA-256")
    if context._truthy(state_risk.get("enabled")):
        errors.append("state-dependent supplier risks unexpectedly enabled")
    if context._truthy(economic.get("supplier_risk_loss_gross_up")):
        errors.append("temporary supplier loss was grossed up in planning")
    if context._truthy(initialization.get("seed_open_orders_from_january_snapshot")):
        errors.append("January opening orders unexpectedly enabled")
    expected_event_count = 1 if expected_event_id else 0
    if int(supplier_risk.get("event_count") or 0) != expected_event_count:
        errors.append("acute supplier-risk event count mismatch")
    if supplier_risk.get("warnings"):
        errors.append("supplier-risk loader warnings present")
    if risk_csv is None:
        if context._truthy(supplier_risk.get("enabled")):
            errors.append("supplier-risk layer unexpectedly enabled in baseline")
    else:
        if not context._truthy(supplier_risk.get("enabled")):
            errors.append("supplier-risk layer is not enabled in incident")
        if str(supplier_risk.get("events_csv_sha256") or "") != context._sha256_file(risk_csv):
            errors.append("supplier-risk CSV SHA-256 mismatch")
    applied_rows: list[dict[str, str]] = []
    if expected_event_id:
        applied_path = case_dir / "data" / "supplier_risk_events_applied_daily.csv"
        if not applied_path.is_file():
            errors.append("missing supplier-risk application trace")
        else:
            applied_rows = [
                row
                for row in context.protocol.read_csv_rows(applied_path)
                if expected_event_id in context._event_tokens(row.get("event_ids"))
            ]
    metrics = {
        **service,
        "state_window_metrics": state_window,
        "simulation_days": simulation_days,
        "state_evaluation_days": context.STATE_EVALUATION_DAYS,
        "state_evaluation_start_day": 0,
        "state_evaluation_end_day": context.STATE_EVALUATION_DAYS - 1,
        "service_global_pct": 100.0 * float(service["system_on_due_service"]),
        "service_output_product_268091_pct": 100.0
        * float(service["on_due_service_268091"]),
        "service_output_product_268967_pct": 100.0
        * float(service["on_due_service_268967"]),
        "backlog_day_count": state_window["backlog_day_count_global"],
        "backlog_qty": state_window["ending_backlog_qty_global"],
        "max_backlog_qty": state_window["max_backlog_qty_global"],
        "backlog_qty_days": state_window["backlog_qty_days_global"],
        "production_released_268091_qty": state_window[
            "production_released_268091_qty"
        ],
        "production_released_268967_qty": state_window[
            "production_released_268967_qty"
        ],
        "total_cost": context._as_float(kpis.get("total_cost"), 0.0),
        "total_transport_cost": context._as_float(kpis.get("total_transport_cost"), 0.0),
        "total_purchase_cost": context._as_float(kpis.get("total_purchase_cost"), 0.0),
        "total_unreliable_loss_qty": context._as_float(
            kpis.get("total_unreliable_loss_qty"), 0.0
        ),
        "warmup_core_state_sha256": str(warmup.get("core_state_sha256") or ""),
        "summary_sha256": context._sha256_file(summary_path),
        "risk_applied_row_count": len(applied_rows),
        "risk_applied_event_count": len(
            {
                token
                for row in applied_rows
                for token in context._event_tokens(row.get("event_ids"))
                if token == expected_event_id
            }
        ),
    }
    return (
        metrics,
        shipment_rows,
        applied_rows,
        errors,
        {"service_rows": service_rows, "production_rows": production_rows},
    )


def _incident_horizon_from_trace(
    *,
    target: Mapping[str, Any],
    tagged_rows: Sequence[Mapping[str, Any]],
    context: Context,
) -> dict[str, Any]:
    impact_start = int(target["impact_window_start_day"])
    impact_end = int(target["impact_window_end_day"])
    if tagged_rows:
        arrivals = [context._as_int(row.get("arrival_day"), -1) for row in tagged_rows]
        if min(arrivals) < 0:
            raise ValueError("Tagged incident shipment lacks an arrival day")
        baseline_first_arrival = context._as_int(
            target.get("target_arrival_day"), min(arrivals)
        )
        causal_start = min(baseline_first_arrival, min(arrivals))
        latest = max(arrivals)
        causal_end = latest + context.MIN_RECOVERY_OBSERVATION_DAYS - 1
        causal_defined = True
    else:
        causal_start = impact_start
        causal_end = impact_end
        latest = -1
        causal_defined = False
    required_days = max(
        context.MINIMUM_CASE_DAYS,
        impact_end + 1,
        causal_end + 1,
    )
    recovery_in_envelope = max(0, impact_end - latest + 1) if latest >= 0 else 0
    return {
        "impact_window_start_day": impact_start,
        "impact_window_end_day": impact_end,
        "impact_window_days": impact_end - impact_start + 1,
        "impact_window_fully_observed": True,
        "causal_window_start_day": causal_start,
        "causal_window_end_day": causal_end,
        "causal_window_days": causal_end - causal_start + 1,
        "causal_window_defined": causal_defined,
        "causal_window_fully_observed": True,
        "target_latest_stressed_arrival_day": latest,
        "required_simulation_days": required_days,
        "recovery_observation_days_after_latest_stressed_arrival": (
            required_days - latest if latest >= 0 else 0
        ),
        "recovery_observation_days_within_impact_window": recovery_in_envelope,
        "recovery_fully_observed_within_360": (
            latest >= 0 and recovery_in_envelope >= context.MIN_RECOVERY_OBSERVATION_DAYS
        ),
    }


def _shipment_trace_signature(
    rows: Sequence[Mapping[str, Any]],
    *,
    end_day_exclusive: int,
    context: Context,
) -> str:
    fields = (
        "shipment_id",
        "risk_decision_day",
        "risk_event_ids",
        "src_node_id",
        "dst_node_id",
        "item_id",
        "edge_id",
        "pulled_qty",
        "shipped_qty",
        "lead_days",
        "arrival_day",
        "reliability",
    )
    projection = [
        {field: row.get(field, "") for field in fields}
        for row in rows
        if 0 <= context._as_int(row.get("risk_decision_day"), -1) < end_day_exclusive
    ]
    projection.sort(
        key=lambda row: (
            context._as_int(row.get("risk_decision_day"), -1),
            str(row.get("src_node_id") or ""),
            str(row.get("dst_node_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("edge_id") or ""),
            str(row.get("shipment_id") or ""),
        )
    )
    return context._stable_sha256(projection)


def _validate_probe_checkpoint(
    payload: Mapping[str, Any],
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    lane: Lane,
    mechanism: Mechanism,
    seed: int,
    key: str,
    probe_contract_signature: str,
    context: Context,
) -> None:
    unsigned = dict(payload)
    signature = str(unsigned.pop("checkpoint_signature", ""))
    attempted = payload.get("attempted_horizons")
    try:
        horizon = int(payload.get("simulation_days"))
        next_horizon = int(payload.get("next_required_simulation_days"))
        attempted_horizons = [int(value) for value in attempted]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid incident-probe checkpoint counters: {key}") from exc
    case_dir = context.Path(str(payload.get("case_dir") or "")).resolve()
    expected_case_dir = (shard_dir / "cases" / f"probe__{key}__h{horizon}").resolve()
    if (
        payload.get("schema_version") != context.PROBE_CHECKPOINT_SCHEMA_VERSION
        or payload.get("campaign_signature") != manifest.get("campaign_signature")
        or payload.get("probe_contract_signature") != probe_contract_signature
        or payload.get("operating_point_id") != point.get("operating_point_id")
        or int(payload.get("seed", -1)) != seed
        or payload.get("lane_id") != lane.lane_id
        or payload.get("mechanism") != mechanism.key
        or payload.get("case_key") != key
        or case_dir != expected_case_dir
        or not attempted_horizons
        or attempted_horizons[-1] != horizon
        or attempted_horizons != sorted(set(attempted_horizons))
        or next_horizon <= horizon
        or not str(payload.get("J0_J719_shipment_trace_signature") or "")
        or not isinstance(payload.get("incident_window"), context.Mapping)
        or not signature
        or signature != context._stable_sha256(unsigned)
    ):
        raise ValueError(f"Incident-probe checkpoint fails closed: {key}/h{horizon}")


def select_unique_reference_shipment(
    rows: Iterable[Mapping[str, Any]],
    *,
    lane: Lane,
    days: int | None = None,
    state_evaluation_days: int = None,
    impact_window_days: int = None,
    max_delay_days: int = None,
    minimum_recovery_observation_days: int = None,
    forced_decision_day: int | None = None,
    target_window_days: int = None,
    state_match_metadata: Mapping[str, Any] | None = None,
    context,
) -> dict[str, Any]:
    """Select and aggregate a positive lane disruption window without horizon bias."""

    if (
        state_evaluation_days <= 0
        or target_window_days <= 0
        or target_window_days > state_evaluation_days
        or (days is not None and (days <= 0 or state_evaluation_days > days))
        or impact_window_days <= max_delay_days
        or max_delay_days < 0
        or minimum_recovery_observation_days < 1
    ):
        raise ValueError("Invalid target observability window contract")
    lane_rows: list[dict[str, Any]] = []
    for source in rows:
        if not context._lane_matches(source, lane):
            continue
        pulled = context._as_float(source.get("pulled_qty"), 0.0)
        shipped = context._as_float(source.get("shipped_qty"), 0.0)
        decision_day = context._as_int(source.get("risk_decision_day"), -1)
        arrival_day = context._as_int(source.get("arrival_day"), -1)
        shipment_id = str(source.get("shipment_id") or "").strip()
        if (
            pulled > 1e-12
            and shipped > 1e-12
            and shipment_id
            and 0 <= decision_day < state_evaluation_days
            and arrival_day >= 0
        ):
            lane_rows.append(dict(source))
    by_day: dict[int, list[dict[str, Any]]] = context.defaultdict(list)
    for row in lane_rows:
        by_day[context._as_int(row.get("risk_decision_day"))].append(row)
    lane_shipped_qty = sum(
        context._as_float(row.get("shipped_qty"), 0.0) for row in lane_rows
    )
    if not by_day and forced_decision_day is None:
        return {
            "target_status": "not_applicable_no_positive_reference_flow",
            "candidate_window_count": 0,
            "candidate_day_count": 0,
            "target_shipment_count": 0,
            "target_shipment_ids": "",
            "baseline_lane_shipped_qty_state_window": lane_shipped_qty,
            "selection_mode": "not_applicable_no_positive_flow",
            "selection_rule": "positive_lane_dispatch_required_in_J0_J719",
            "reference_kind": context.TARGET_REFERENCE_KIND,
            "reason": "No positive baseline shipment exists in the state window.",
        }
    candidate_groups: dict[int, list[dict[str, Any]]] = {}
    for start in range(0, state_evaluation_days - target_window_days + 1):
        group = [
            row
            for day in range(start, start + target_window_days)
            for row in by_day.get(day, [])
        ]
        if group:
            candidate_groups[start] = group
    if forced_decision_day is not None and forced_decision_day not in candidate_groups:
        selected_end = forced_decision_day + target_window_days - 1
        impact_end = forced_decision_day + impact_window_days - 1
        required_days = max(state_evaluation_days, impact_end + 1)
        zero_flow = {
            "target_status": "identified_registered_window_no_positive_flow",
            "candidate_window_count": len(candidate_groups),
            "candidate_day_count": len(by_day),
            "target_shipment_id": "",
            "target_shipment_count": 0,
            "target_shipment_ids": "",
            "target_decision_day": forced_decision_day,
            "target_window_start_day": forced_decision_day,
            "target_window_end_day": selected_end,
            "target_window_days": target_window_days,
            "target_active_decision_day_count": 0,
            "target_active_decision_days": "",
            "target_release_day": "",
            "target_arrival_day": "",
            "target_release_days": "",
            "target_arrival_days": "",
            "target_planned_qty": 0.0,
            "target_expected_delivered_qty": 0.0,
            "target_nominal_reliability": 0.0,
            "target_lead_days": "",
            "target_uom": "no_flow",
            "baseline_lane_shipped_qty_state_window": lane_shipped_qty,
            "target_qty_share_of_lane_state_window": 0.0,
            "target_group_qty_percentile_lane_state_window": 0.0,
            "target_exposure_concentration_flag": "no_positive_flow_in_fixed_window",
            "impact_window_start_day": forced_decision_day,
            "impact_window_end_day": impact_end,
            "impact_window_days": impact_window_days,
            "impact_window_fully_observed": None if days is None else impact_end < days,
            "target_latest_baseline_arrival_day": -1,
            "target_latest_stressed_arrival_day": -1,
            "observable_days_after_target_decision": (
                "" if days is None else days - forced_decision_day
            ),
            "observable_days_after_first_expected_arrival": "",
            "recovery_observation_days_after_latest_stressed_arrival": 0,
            "recovery_observation_days_within_impact_window": 0,
            "recovery_fully_observed_within_360": False,
            "minimum_recovery_observation_days_required": minimum_recovery_observation_days,
            "causal_window_start_day": forced_decision_day,
            "causal_window_end_day": impact_end,
            "causal_window_days": impact_window_days,
            "causal_window_defined": False,
            "causal_window_fully_observed": None if days is None else impact_end < days,
            "required_simulation_days": required_days,
            "target_selected_independently_by_operating_point": False,
            "target_selection_basis": "fixed_independent_design_window_no_flow",
            "target_shipments": [],
            "eligible_candidate_day_count": "",
            "ineligible_candidate_day_count": "",
            "unique_candidate_day_count": 0,
            "selection_mode": "registered_cross_state_42d_window_no_flow",
            "selection_rule": "fixed_window_selected_on_independent_design_seed",
            "reference_kind": context.TARGET_REFERENCE_KIND,
            "reason": "No positive flow occurred in the fixed 42-day window for this repetition.",
        }
        if state_match_metadata:
            zero_flow.update(dict(state_match_metadata))
        return zero_flow
    candidate_starts = (
        [forced_decision_day]
        if forced_decision_day is not None
        else list(candidate_groups)
    )
    selected_start = min(
        candidate_starts,
        key=lambda start: (
            -sum(
                context._as_float(row.get("shipped_qty"), 0.0)
                for row in candidate_groups[start]
            ),
            start,
            "|".join(
                sorted(
                    str(row.get("shipment_id") or "") for row in candidate_groups[start]
                )
            ),
        ),
    )
    selected_end = selected_start + target_window_days - 1
    selected_rows = sorted(
        candidate_groups[selected_start],
        key=lambda row: (
            context._as_int(row.get("risk_decision_day"), -1),
            str(row.get("shipment_id") or ""),
        ),
    )
    shipment_ids = [str(row["shipment_id"]) for row in selected_rows]
    pulled_qty = sum(
        context._as_float(row.get("pulled_qty"), 0.0) for row in selected_rows
    )
    shipped_qty = sum(
        context._as_float(row.get("shipped_qty"), 0.0) for row in selected_rows
    )
    release_days = [context._as_int(row.get("day")) for row in selected_rows]
    arrival_days = [context._as_int(row.get("arrival_day")) for row in selected_rows]
    active_days = sorted(
        {context._as_int(row.get("risk_decision_day")) for row in selected_rows}
    )
    impact_window_start = selected_start
    impact_window_end = selected_start + impact_window_days - 1
    latest_baseline_arrival = max(arrival_days)
    latest_stressed_arrival = latest_baseline_arrival + max_delay_days
    causal_window_start = min(arrival_days)
    causal_window_end = latest_stressed_arrival + minimum_recovery_observation_days - 1
    required_simulation_days = max(impact_window_end, causal_window_end) + 1
    selected_fully_observable = days is None or required_simulation_days <= days
    recovery_within_impact_window = max(
        0, impact_window_end - latest_stressed_arrival + 1
    )
    window_quantities = [
        sum(context._as_float(row.get("shipped_qty"), 0.0) for row in group)
        for group in candidate_groups.values()
    ]
    target_group_percentile = sum(
        value <= shipped_qty + context.TARGET_QUANTITY_TOLERANCE
        for value in window_quantities
    ) / len(window_quantities)
    target_status = (
        "identified_unique_reference_shipment"
        if len(selected_rows) == 1
        else (
            "identified_reference_lane_day_shipment_group"
            if target_window_days == 1
            else "identified_reference_lane_window_shipment_group"
        )
    )
    selection_mode = (
        "registered_cross_state_42d_window"
        if forced_decision_day is not None
        and target_window_days == context.INCIDENT_DISRUPTION_DAYS
        else (
            "single_shipment_day"
            if len(selected_rows) == 1 and target_window_days == 1
            else "aggregated_lane_window"
        )
    )
    result: dict[str, Any] = {
        "target_status": (
            target_status
            if selected_fully_observable
            else "not_applicable_selected_reference_horizon_censored"
        ),
        "target_shipment_id": "|".join(shipment_ids),
        "target_shipment_count": len(selected_rows),
        "target_shipment_ids": "|".join(shipment_ids),
        "target_decision_day": selected_start,
        "target_window_start_day": selected_start,
        "target_window_end_day": selected_end,
        "target_window_days": target_window_days,
        "target_active_decision_day_count": len(active_days),
        "target_active_decision_days": "|".join(str(day) for day in active_days),
        "target_release_day": min(release_days),
        "target_arrival_day": min(arrival_days),
        "target_release_days": "|".join(str(value) for value in release_days),
        "target_arrival_days": "|".join(str(value) for value in arrival_days),
        "target_planned_qty": pulled_qty,
        "target_expected_delivered_qty": shipped_qty,
        "target_nominal_reliability": shipped_qty / pulled_qty
        if pulled_qty > 1e-12
        else 0.0,
        "target_lead_days": "|".join(
            str(context._as_int(row.get("lead_days"))) for row in selected_rows
        ),
        "target_uom": str(selected_rows[0].get("uom") or ""),
        "baseline_lane_shipped_qty_state_window": lane_shipped_qty,
        "target_qty_share_of_lane_state_window": (
            shipped_qty / lane_shipped_qty if lane_shipped_qty > 1e-12 else 0.0
        ),
        "target_group_qty_percentile_lane_state_window": target_group_percentile,
        "target_exposure_concentration_flag": (
            "selected_window_carries_all_positive_lane_flow"
            if context.math.isclose(
                shipped_qty, lane_shipped_qty, rel_tol=0.0, abs_tol=1e-9
            )
            else "selected_window_is_part_of_lane_flow"
        ),
        "impact_window_start_day": impact_window_start,
        "impact_window_end_day": impact_window_end,
        "impact_window_days": impact_window_days,
        "impact_window_fully_observed": None
        if days is None
        else impact_window_end < days,
        "target_latest_baseline_arrival_day": latest_baseline_arrival,
        "target_latest_stressed_arrival_day": latest_stressed_arrival,
        "observable_days_after_target_decision": ""
        if days is None
        else days - selected_start,
        "observable_days_after_first_expected_arrival": ""
        if days is None
        else days - min(arrival_days),
        "recovery_observation_days_after_latest_stressed_arrival": (
            "" if days is None else max(0, days - latest_stressed_arrival)
        ),
        "recovery_observation_days_within_impact_window": recovery_within_impact_window,
        "recovery_fully_observed_within_360": (
            recovery_within_impact_window >= minimum_recovery_observation_days
        ),
        "minimum_recovery_observation_days_required": minimum_recovery_observation_days,
        "causal_window_start_day": causal_window_start,
        "causal_window_end_day": causal_window_end,
        "causal_window_days": causal_window_end - causal_window_start + 1,
        "causal_window_defined": True,
        "causal_window_fully_observed": (
            None
            if days is None
            else causal_window_start >= 0 and causal_window_end < days
        ),
        "required_simulation_days": required_simulation_days,
        "target_selected_independently_by_operating_point": forced_decision_day is None,
        "target_selection_basis": (
            "global_cross_state_discovery_registered_window"
            if forced_decision_day is not None
            else "within_state_largest_lane_window_quantity"
        ),
        "target_shipments": [
            {
                "shipment_id": str(row["shipment_id"]),
                "risk_decision_day": context._as_int(row.get("risk_decision_day")),
                "release_day": context._as_int(row.get("day")),
                "arrival_day": context._as_int(row.get("arrival_day")),
                "pulled_qty": context._as_float(row.get("pulled_qty"), 0.0),
                "expected_delivered_qty": context._as_float(
                    row.get("shipped_qty"), 0.0
                ),
                "nominal_reliability": context._as_float(row.get("reliability"), 1.0),
                "lead_days": context._as_int(row.get("lead_days")),
                "uom": str(row.get("uom") or ""),
            }
            for row in selected_rows
        ],
        "candidate_window_count": len(candidate_groups),
        "candidate_day_count": len(by_day),
        "eligible_candidate_day_count": sum(
            1
            for start, group in candidate_groups.items()
            if days is None
            or max(
                start + impact_window_days - 1,
                max(context._as_int(row.get("arrival_day"), -1) for row in group)
                + max_delay_days
                + minimum_recovery_observation_days
                - 1,
            )
            < days
        ),
        "ineligible_candidate_day_count": (
            0
            if days is None
            else len(candidate_groups)
            - sum(
                1
                for start, group in candidate_groups.items()
                if max(
                    start + impact_window_days - 1,
                    max(context._as_int(row.get("arrival_day"), -1) for row in group)
                    + max_delay_days
                    + minimum_recovery_observation_days
                    - 1,
                )
                < days
            )
        ),
        "unique_candidate_day_count": sum(
            len(group) == 1 for group in candidate_groups.values()
        ),
        "selection_mode": (
            selection_mode
            if selected_fully_observable
            else "not_applicable_selected_target_requires_longer_horizon"
        ),
        "selection_rule": (
            "registered_cross_state_window_or_within_state_max_quantity; selection_before_"
            "adaptive_horizon; aggregate_every_positive_shipment_in_window"
        ),
        "reference_kind": context.TARGET_REFERENCE_KIND,
        "reason": (
            ""
            if selected_fully_observable
            else (
                "The horizon-independent selected target requires "
                f"{required_simulation_days} simulated days; configured horizon is {days}. "
                "The preflight must fail rather than substitute a faster shipment."
            )
        ),
    }
    if state_match_metadata:
        result.update(dict(state_match_metadata))
    return result


def build_operating_point_preflight(
    *,
    manifest: Mapping[str, Any],
    points: Sequence[Mapping[str, Any]],
    discovery_evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    bootstrap_replicates: int = None,
    context,
) -> dict[str, Any]:
    """Validate the three achieved service states before any incident probe.

    The 30 campaign runs are paired by common seed.  Seed 340281 is reported as design
    evidence only and is never included in the acceptance statistics.
    """

    if bootstrap_replicates < 1:
        raise ValueError("bootstrap_replicates must be positive")
    expected = {
        (point_id, seed)
        for point_id in context.OPERATING_POINT_IDS
        for seed in (context.TARGET_DESIGN_SEED, *context.SEEDS)
    }
    if set(discovery_evidence) != expected:
        raise ValueError("Operating-point preflight discovery matrix is incomplete")
    point_by_id = {str(point["operating_point_id"]): dict(point) for point in points}
    if set(point_by_id) != set(context.OPERATING_POINT_IDS):
        raise ValueError("Operating-point preflight requires exactly three states")

    metric_names = (
        "demand_qty_global",
        "on_due_qty_global",
        "demand_qty_268091",
        "on_due_qty_268091",
        "demand_qty_268967",
        "on_due_qty_268967",
    )
    rows_by_point: dict[str, list[dict[str, float]]] = {}
    design_rows: dict[str, dict[str, Any]] = {}
    for point_id in context.OPERATING_POINT_IDS:
        rows: list[dict[str, float]] = []
        for seed in (context.TARGET_DESIGN_SEED, *context.SEEDS):
            raw = dict(
                discovery_evidence[(point_id, seed)].get("state_service_metrics") or {}
            )
            converted = {
                name: context._as_float(raw.get(name)) for name in metric_names
            }
            if any(
                not context.math.isfinite(value) or value < 0.0
                for value in converted.values()
            ):
                raise ValueError(
                    f"Missing or invalid state-service totals for {point_id}/seed {seed}"
                )
            for demand_field in (
                "demand_qty_268091",
                "demand_qty_268967",
                "demand_qty_global",
            ):
                if converted[demand_field] <= 1e-12:
                    raise ValueError(
                        f"Zero seed-level demand for {point_id}/seed {seed}: "
                        f"{demand_field}"
                    )
            for product in context.TARGET_PRODUCTS:
                if converted[f"on_due_qty_{product}"] > (
                    converted[f"demand_qty_{product}"]
                    + context.TARGET_QUANTITY_TOLERANCE
                ):
                    raise ValueError(
                        f"On-due quantity exceeds demand for {point_id}/seed {seed}/{product}"
                    )
            if converted["on_due_qty_global"] > (
                converted["demand_qty_global"] + context.TARGET_QUANTITY_TOLERANCE
            ):
                raise ValueError(
                    f"Global on-due quantity exceeds demand for {point_id}/seed {seed}"
                )
            converted["seed"] = float(seed)
            if seed == context.TARGET_DESIGN_SEED:
                design_rows[point_id] = {
                    "seed": seed,
                    **converted,
                    "service_global_pct": 100.0
                    * converted["on_due_qty_global"]
                    / converted["demand_qty_global"],
                }
            else:
                rows.append(converted)
        if len(rows) != len(context.SEEDS):
            raise AssertionError("Campaign-seed state preflight count changed")
        rows_by_point[point_id] = rows

    for index, seed in enumerate(context.SEEDS):
        reference = rows_by_point["op_100"][index]
        for point_id in context.OPERATING_POINT_IDS[1:]:
            candidate = rows_by_point[point_id][index]
            for demand_field in (
                "demand_qty_268091",
                "demand_qty_268967",
                "demand_qty_global",
            ):
                if not context.math.isclose(
                    float(reference[demand_field]),
                    float(candidate[demand_field]),
                    rel_tol=1e-12,
                    abs_tol=context.TARGET_QUANTITY_TOLERANCE,
                ):
                    raise ValueError(
                        f"Paired holdout demand changed across states for seed {seed}: "
                        f"{demand_field}"
                    )

    rng = context.random.Random(context.PREFLIGHT_BOOTSTRAP_SEED)
    bootstrap_indices = [
        [rng.randrange(len(context.SEEDS)) for _ in context.SEEDS]
        for _ in range(bootstrap_replicates)
    ]

    def ratio_of_sums(
        rows: Sequence[Mapping[str, float]], demand_field: str, on_due_field: str
    ) -> float:
        demand = sum(float(row[demand_field]) for row in rows)
        if demand <= 1e-12:
            raise ValueError(
                f"Zero total demand in operating-point preflight: {demand_field}"
            )
        return 100.0 * sum(float(row[on_due_field]) for row in rows) / demand

    def seed_service(
        row: Mapping[str, float], demand_field: str, on_due_field: str
    ) -> float:
        demand = float(row[demand_field])
        if demand <= 1e-12:
            raise ValueError(f"Zero seed-level demand in preflight: {demand_field}")
        return 100.0 * float(row[on_due_field]) / demand

    def dispersion(values: Sequence[float]) -> dict[str, float]:
        return {
            "min": min(values),
            "p10": context._linear_quantile(values, 0.10),
            "p25": context._linear_quantile(values, 0.25),
            "median": context._linear_quantile(values, 0.50),
            "p75": context._linear_quantile(values, 0.75),
            "p90": context._linear_quantile(values, 0.90),
            "max": max(values),
            "iqr": context._linear_quantile(values, 0.75)
            - context._linear_quantile(values, 0.25),
        }

    state_rows: list[dict[str, Any]] = []
    for point_id in context.OPERATING_POINT_IDS:
        rows = rows_by_point[point_id]
        global_pct = ratio_of_sums(rows, "demand_qty_global", "on_due_qty_global")
        product_pct = {
            product: ratio_of_sums(
                rows, f"demand_qty_{product}", f"on_due_qty_{product}"
            )
            for product in context.TARGET_PRODUCTS
        }
        seed_level = {
            "global": [
                seed_service(row, "demand_qty_global", "on_due_qty_global")
                for row in rows
            ],
            **{
                product: [
                    seed_service(
                        row,
                        f"demand_qty_{product}",
                        f"on_due_qty_{product}",
                    )
                    for row in rows
                ]
                for product in context.TARGET_PRODUCTS
            },
        }
        bootstrap_global = [
            ratio_of_sums(
                [rows[index] for index in indices],
                "demand_qty_global",
                "on_due_qty_global",
            )
            for indices in bootstrap_indices
        ]
        saturated_seed_count = {
            product: sum(value >= 100.0 - 1e-9 for value in seed_level[product])
            for product in context.TARGET_PRODUCTS
        }
        non_saturation_limit_seed_count = {
            product: sum(value >= 99.5 - 1e-9 for value in seed_level[product])
            for product in context.TARGET_PRODUCTS
        }
        transition_zone_by_product = {
            product: 0 < count < len(context.SEEDS)
            for product, count in saturated_seed_count.items()
        }
        failures: list[str] = []
        target_pct = 100.0 * float(point_by_id[point_id]["target_service"])
        global_median_pct = dispersion(seed_level["global"])["median"]
        if point_id == "op_100":
            if not 98.5 <= global_pct <= 100.0 + 1e-9:
                failures.append("healthy global service is outside the 98.5-100% band")
            if not 98.5 <= global_median_pct <= 100.0 + 1e-9:
                failures.append(
                    "healthy median seed-level global service is outside the 98.5-100% band"
                )
            if any(value < 98.5 - 1e-9 for value in product_pct.values()):
                failures.append("a healthy finished product is below 98.5% service")
            contract = "global and each product 98.5-100%; product gap descriptive"
        elif point_id == "op_93":
            lower = target_pct - 1.5
            upper = target_pct + 1.5
            if not lower <= global_pct <= upper:
                failures.append(
                    f"global service is outside the signed {lower:.3f}-{upper:.3f}% band"
                )
            if not lower <= global_median_pct <= upper:
                failures.append(
                    f"median seed-level global service is outside the signed "
                    f"{lower:.3f}-{upper:.3f}% band"
                )
            if max(product_pct.values()) >= 99.5 - 1e-9:
                failures.append(
                    "a degraded finished product reaches the 99.5% saturation limit"
                )
            contract = (
                f"global {lower:.3f}-{upper:.3f}%; each product below 99.5%; "
                "product gap>5pp flagged"
            )
        else:
            lower = target_pct - 1.5
            upper = target_pct + 1.5
            if not lower <= global_pct <= upper:
                failures.append(
                    f"global service is outside the signed {lower:.3f}-{upper:.3f}% band"
                )
            if not lower <= global_median_pct <= upper:
                failures.append(
                    f"median seed-level global service is outside the signed "
                    f"{lower:.3f}-{upper:.3f}% band"
                )
            if max(product_pct.values()) >= 99.5 - 1e-9:
                failures.append(
                    "a degraded finished product reaches the 99.5% saturation limit"
                )
            contract = (
                f"global {lower:.3f}-{upper:.3f}%; each product below 99.5%; "
                "product gap>5pp flagged"
            )
        state_rows.append(
            {
                "operating_point_id": point_id,
                "target_service_pct": target_pct,
                "campaign_seed_count": len(rows),
                "service_global_ratio_of_sums_pct": global_pct,
                "service_global_seed_median_pct": global_median_pct,
                "service_268091_ratio_of_sums_pct": product_pct["268091"],
                "service_268967_ratio_of_sums_pct": product_pct["268967"],
                "product_service_gap_pp": abs(
                    product_pct["268091"] - product_pct["268967"]
                ),
                "product_service_gap_above_5pp": abs(
                    product_pct["268091"] - product_pct["268967"]
                )
                > 5.0,
                "seed_level_service_dispersion_pct": {
                    name: dispersion(values) for name, values in seed_level.items()
                },
                "saturated_seed_count_by_product": saturated_seed_count,
                "non_saturation_limit_seed_count_by_product": (
                    non_saturation_limit_seed_count
                ),
                "transition_zone_by_product": transition_zone_by_product,
                "transition_zone_observed": any(transition_zone_by_product.values()),
                "global_service_bootstrap_ci95_low_pct": context._linear_quantile(
                    bootstrap_global, 0.025
                ),
                "global_service_bootstrap_ci95_high_pct": context._linear_quantile(
                    bootstrap_global, 0.975
                ),
                "acceptance_contract": contract,
                "accepted": not failures,
                "failures": failures,
                "design_seed_descriptive_only": design_rows[point_id],
            }
        )
    pooled_ordering_by_measure = {
        "global": (
            float(state_rows[0]["service_global_ratio_of_sums_pct"])
            > float(state_rows[1]["service_global_ratio_of_sums_pct"])
            > float(state_rows[2]["service_global_ratio_of_sums_pct"])
        ),
        "268091": (
            float(state_rows[0]["service_268091_ratio_of_sums_pct"])
            > float(state_rows[1]["service_268091_ratio_of_sums_pct"])
            > float(state_rows[2]["service_268091_ratio_of_sums_pct"])
        ),
        "268967": (
            float(state_rows[0]["service_268967_ratio_of_sums_pct"])
            > float(state_rows[1]["service_268967_ratio_of_sums_pct"])
            > float(state_rows[2]["service_268967_ratio_of_sums_pct"])
        ),
    }
    ordering_valid = all(pooled_ordering_by_measure.values())
    seed_order_counts = {
        name: sum(
            seed_service(
                rows_by_point["op_100"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            > seed_service(
                rows_by_point["op_93"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            > seed_service(
                rows_by_point["op_80"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            for index in range(len(context.SEEDS))
        )
        for name in ("global", *context.TARGET_PRODUCTS)
    }
    joint_seed_order_count = sum(
        all(
            seed_service(
                rows_by_point["op_100"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            > seed_service(
                rows_by_point["op_93"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            > seed_service(
                rows_by_point["op_80"][index],
                "demand_qty_global" if name == "global" else f"demand_qty_{name}",
                "on_due_qty_global" if name == "global" else f"on_due_qty_{name}",
            )
            for name in ("global", *context.TARGET_PRODUCTS)
        )
        for index in range(len(context.SEEDS))
    )
    seed_ordering_valid = joint_seed_order_count >= 24
    product_seed_ordering_checks = {
        product: {
            "ordered_seed_count": seed_order_counts[product],
            "ordering_observed_in_at_least_24_of_30_seeds": (
                seed_order_counts[product] >= 24
            ),
            "acceptance_gate": True,
        }
        for product in context.TARGET_PRODUCTS
    }
    if not ordering_valid or not seed_ordering_valid:
        for row in state_rows:
            row["failures"].append(
                "service-state ordering op_100>op_93>op_80 is not preserved "
                "in pooled ratio-of-sums and jointly for global service plus "
                "both finished products on at least the same 24/30 paired seeds"
            )
            row["accepted"] = False
    unsigned = {
        "schema_version": context.PREFLIGHT_SCHEMA_VERSION,
        "contract_revision": context.CONTRACT_REVISION,
        "campaign_signature": manifest["campaign_signature"],
        "status": (
            context.HOLDOUT_ACCEPTED_STATUS
            if all(row["accepted"] for row in state_rows)
            else context.HOLDOUT_REJECTED_STATUS
        ),
        "campaign_seed_count": len(context.SEEDS),
        "campaign_seeds": list(context.SEEDS),
        "calibration_seeds_excluded": list(range(340282, 340287)),
        "holdout_used_once_without_retuning": True,
        "operating_points_input_status": manifest.get(
            "operating_points_input_status", ""
        ),
        "operating_points_artifact_signature": manifest.get(
            "operating_points_artifact_signature", ""
        ),
        "operating_points_calibration_plan_signature": manifest.get(
            "operating_points_calibration_plan_signature", ""
        ),
        "operating_points_selection_signature": manifest.get(
            "operating_points_selection_signature", ""
        ),
        "no_incident_probe_before_holdout_acceptance": True,
        "design_seed": context.TARGET_DESIGN_SEED,
        "design_seed_in_acceptance_statistics": False,
        "bootstrap": {
            "method": "paired_common_seed_resampling",
            "replicates": bootstrap_replicates,
            "seed": context.PREFLIGHT_BOOTSTRAP_SEED,
        },
        "ordering_valid": ordering_valid,
        "pooled_ordering_by_measure": pooled_ordering_by_measure,
        "seed_ordering_valid": seed_ordering_valid,
        "seed_order_counts": seed_order_counts,
        "joint_seed_order_count": joint_seed_order_count,
        "joint_seed_order_required": 24,
        "product_seed_ordering_checks": product_seed_ordering_checks,
        "minimum_seed_order_count": 24,
        "states": state_rows,
    }
    return {**unsigned, "preflight_signature": context._stable_sha256(unsigned)}


def _prepare_incident_probe(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    lane: Lane,
    mechanism: Mechanism,
    seed: int,
    registered_target: Mapping[str, Any],
    context,
) -> dict[str, Any]:
    key = context._case_key(
        point_id=str(point["operating_point_id"]),
        seed=seed,
        stage="incident",
        lane_id=lane.lane_id,
        mechanism=mechanism.key,
    )
    probe_path = shard_dir / "incident_probes" / f"{key}.json"
    risk_row = context.build_risk_row(
        point_id=str(point["operating_point_id"]),
        seed=seed,
        lane=lane,
        mechanism=mechanism,
        target=registered_target,
    )
    risk_csv = shard_dir / "inputs" / "risk_events" / f"{key}.csv"
    context.campaign_core.write_risk_csv(risk_csv, [risk_row])
    probe_contract_signature = context._stable_sha256(
        {
            "campaign_signature": manifest["campaign_signature"],
            "target_registry_signature": manifest["target_registry_signature"],
            "point_id": point["operating_point_id"],
            "seed": seed,
            "lane": context.asdict(lane),
            "mechanism": context.asdict(mechanism),
            "target_window_start_day": registered_target["target_window_start_day"],
            "target_window_end_day": registered_target["target_window_end_day"],
            "risk_csv_sha256": context._sha256_file(risk_csv),
        }
    )
    if probe_path.is_file():
        payload = context._read_json(probe_path)
        unsigned = dict(payload)
        evidence_signature = unsigned.pop("probe_evidence_signature", "")
        if (
            payload.get("probe_contract_signature") != probe_contract_signature
            or evidence_signature != context._stable_sha256(unsigned)
            or not isinstance(payload.get("metrics"), context.Mapping)
            or not isinstance(payload.get("incident_proof"), context.Mapping)
            or not isinstance(payload.get("validation_errors"), list)
        ):
            raise ValueError(f"Incident probe evidence fails closed: {probe_path}")
        if payload.get("case_artifacts_pruned") is not True:
            case_dir = context.Path(str(payload.get("case_dir") or "")).resolve()
            cases_root = (shard_dir / "cases").resolve()
            if not case_dir.is_relative_to(cases_root):
                raise ValueError(f"Incident probe case path escapes shard: {case_dir}")
            if case_dir.exists():
                context.campaign_core.prune_case_artifacts(case_dir)
            payload["case_artifacts_pruned"] = True
            payload["case_artifacts_pruned_at_utc"] = context.utc_now()
            payload["probe_evidence_signature"] = context._stable_sha256(
                {
                    field: value
                    for field, value in payload.items()
                    if field != "probe_evidence_signature"
                }
            )
            context._write_json_atomic(probe_path, payload)
        return payload
    initial_days = max(
        context.MINIMUM_CASE_DAYS,
        int(
            registered_target.get("required_simulation_days")
            or context.MINIMUM_CASE_DAYS
        ),
    )
    checkpoint = context._resume_probe_checkpoint(
        shard_dir=shard_dir,
        manifest=manifest,
        point=point,
        lane=lane,
        mechanism=mechanism,
        seed=seed,
        key=key,
        probe_contract_signature=probe_contract_signature,
    )
    if checkpoint is None:
        previous_trace_signature = ""
        horizons: list[int] = []
        horizon = initial_days
    else:
        previous_trace_signature = str(checkpoint["J0_J719_shipment_trace_signature"])
        horizons = [int(value) for value in checkpoint["attempted_horizons"]]
        horizon = int(checkpoint["next_required_simulation_days"])
    final_case_dir: context.Path | None = None
    final_rows: list[dict[str, str]] = []
    for _iteration in range(len(horizons) + 1, 5):
        probe_key = f"probe__{key}__h{horizon}"
        case_dir = context._run_engine(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=probe_key,
            seed=seed,
            risk_csv=risk_csv,
            simulation_days=horizon,
        )
        shipment_rows = context.protocol.read_csv_rows(
            case_dir / "data" / "production_supplier_shipments_daily.csv"
        )
        trace_signature = context._shipment_trace_signature(shipment_rows)
        if previous_trace_signature and trace_signature != previous_trace_signature:
            raise RuntimeError(
                f"J0-J719 shipment trace changed after horizon extension for {key}"
            )
        tagged = context._tagged_incident_shipments(
            shipment_rows, lane=lane, event_id=str(risk_row["event_id"])
        )
        horizon_contract = context._incident_horizon_from_trace(
            target=registered_target, tagged_rows=tagged
        )
        required_days = int(horizon_contract["required_simulation_days"])
        horizons.append(horizon)
        if required_days <= horizon:
            final_case_dir = case_dir
            final_rows = shipment_rows
            break
        context._persist_probe_extension_checkpoint(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            lane=lane,
            mechanism=mechanism,
            seed=seed,
            key=key,
            probe_contract_signature=probe_contract_signature,
            case_dir=case_dir,
            horizon=horizon,
            horizons=horizons,
            trace_signature=trace_signature,
            horizon_contract=horizon_contract,
            required_days=required_days,
        )
        previous_trace_signature = trace_signature
        horizon = required_days
    if final_case_dir is None:
        raise RuntimeError(f"Adaptive incident horizon did not converge for {key}")
    tagged = context._tagged_incident_shipments(
        final_rows, lane=lane, event_id=str(risk_row["event_id"])
    )
    horizon_contract = context._incident_horizon_from_trace(
        target=registered_target, tagged_rows=tagged
    )
    minimum_required_days = int(horizon_contract["required_simulation_days"])
    horizon_contract["minimum_required_simulation_days"] = minimum_required_days
    horizon_contract["required_simulation_days"] = horizon
    horizon_contract["impact_window_fully_observed"] = (
        int(horizon_contract["impact_window_end_day"]) < horizon
    )
    horizon_contract["causal_window_fully_observed"] = (
        int(horizon_contract["causal_window_end_day"]) < horizon
    )
    horizon_contract["observable_days_after_target_decision"] = horizon - int(
        registered_target["target_window_start_day"]
    )
    causal_start = int(horizon_contract["causal_window_start_day"])
    horizon_contract["observable_days_after_first_expected_arrival"] = (
        horizon - causal_start if horizon_contract["causal_window_defined"] else ""
    )
    latest_stressed = int(horizon_contract["target_latest_stressed_arrival_day"])
    horizon_contract["recovery_observation_days_after_latest_stressed_arrival"] = (
        horizon - latest_stressed if latest_stressed >= 0 else 0
    )
    final_target = {**dict(registered_target), **horizon_contract}
    metrics, shipment_rows, applied_rows, extraction_errors, daily_context = (
        context._extract_metrics(
            case_dir=final_case_dir,
            manifest=manifest,
            point=point,
            risk_csv=risk_csv,
            expected_event_id=str(risk_row["event_id"]),
            simulation_days=horizon,
        )
    )
    metrics["impact_window_metrics"] = context._window_metrics(
        service_rows=daily_context["service_rows"],
        production_rows=daily_context["production_rows"],
        start_day=int(final_target["impact_window_start_day"]),
        end_day=int(final_target["impact_window_end_day"]),
    )
    metrics["causal_window_metrics"] = context._window_metrics(
        service_rows=daily_context["service_rows"],
        production_rows=daily_context["production_rows"],
        start_day=int(final_target["causal_window_start_day"]),
        end_day=int(final_target["causal_window_end_day"]),
    )
    proof, trace_errors = context.validate_incident_trace(
        mechanism=mechanism,
        lane=lane,
        target=final_target,
        risk_row=risk_row,
        shipment_rows=shipment_rows,
        applied_rows=applied_rows,
        simulation_days=horizon,
    )
    incident_pre_trace = context._shipment_trace_signature(
        shipment_rows,
        end_day_exclusive=int(final_target["target_window_start_day"]),
    )
    proof["incident_pre_incident_shipment_trace_sha256"] = incident_pre_trace
    validation_errors = [*extraction_errors, *trace_errors]
    unsigned = {
        "schema_version": f"{context.SCHEMA_VERSION}.incident_probe.v1",
        "campaign_signature": manifest["campaign_signature"],
        "probe_contract_signature": probe_contract_signature,
        "operating_point_id": point["operating_point_id"],
        "seed": seed,
        "lane_id": lane.lane_id,
        "mechanism": mechanism.key,
        "case_dir": str(final_case_dir.resolve()),
        "risk_csv": str(risk_csv.resolve()),
        "risk_csv_sha256": context._sha256_file(risk_csv),
        "attempted_horizons": horizons,
        "final_simulation_days": horizon,
        "J0_J719_shipment_trace_signature": context._shipment_trace_signature(
            final_rows
        ),
        "tagged_shipment_count": len(tagged),
        "incident_window": horizon_contract,
        "metrics": metrics,
        "incident_proof": proof,
        "incident_pre_incident_shipment_trace_sha256": incident_pre_trace,
        "validation_errors": validation_errors,
        "risk_row": risk_row,
        "case_artifacts_pruned": False,
        "case_artifacts_pruned_at_utc": "",
        "created_at_utc": context.utc_now(),
    }
    payload = {**unsigned, "probe_evidence_signature": context._stable_sha256(unsigned)}
    context._write_json_atomic(probe_path, payload)
    context.campaign_core.prune_case_artifacts(final_case_dir)
    payload["case_artifacts_pruned"] = True
    payload["case_artifacts_pruned_at_utc"] = context.utc_now()
    payload["probe_evidence_signature"] = context._stable_sha256(
        {
            field: value
            for field, value in payload.items()
            if field != "probe_evidence_signature"
        }
    )
    context._write_json_atomic(probe_path, payload)
    return payload


def _execute_incident(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    lane: Lane,
    mechanism: Mechanism,
    seed: int,
    target: Mapping[str, Any],
    baseline_evidence: Mapping[str, Any],
    reuse_roots: Sequence[Path],
    prepared_probe: Mapping[str, Any] | None = None,
    context,
) -> dict[str, Any]:
    simulation_days = max(
        context.MINIMUM_CASE_DAYS,
        int(target.get("required_simulation_days") or context.MINIMUM_CASE_DAYS),
    )
    key = context._case_key(
        point_id=str(point["operating_point_id"]),
        seed=seed,
        stage="incident",
        lane_id=lane.lane_id,
        mechanism=mechanism.key,
    )
    signature = context._case_signature(
        manifest=manifest,
        point=point,
        seed=seed,
        stage="incident",
        lane=lane,
        mechanism=mechanism,
        target=target,
        simulation_days=simulation_days,
    )
    existing = context._load_or_reuse_evidence(
        shard_dir=shard_dir,
        manifest=manifest,
        case_key=key,
        case_signature=signature,
        reuse_roots=reuse_roots,
    )
    if existing is not None:
        return existing
    base = context._base_evidence(
        manifest=manifest,
        shard_id=str(manifest.get("active_shard_id") or ""),
        point=point,
        seed=seed,
        stage="incident",
        case_key=key,
        case_signature=signature,
        simulation_days=simulation_days,
    )
    base.update(
        {
            "lane": context.asdict(lane),
            "mechanism": context.asdict(mechanism),
            "target": dict(target),
            "baseline_case_signature": baseline_evidence["case_signature"],
        }
    )
    if not str(target.get("target_status") or "").startswith("identified_"):
        evidence = {
            **base,
            "status": "not_applicable",
            "valid": False,
            "validation_errors": [str(target.get("reason") or "unique target absent")],
            "metrics": {},
            "incident_proof": {"incident_physically_exercised": False},
            "run_dir": "",
        }
        return context._persist_evidence(
            context._evidence_path(shard_dir, key), evidence
        )
    risk_row = context.build_risk_row(
        point_id=str(point["operating_point_id"]),
        seed=seed,
        lane=lane,
        mechanism=mechanism,
        target=target,
    )
    risk_csv = shard_dir / "inputs" / "risk_events" / f"{key}.csv"
    context.campaign_core.write_risk_csv(risk_csv, [risk_row])
    if prepared_probe is not None:
        if (
            int(prepared_probe.get("final_simulation_days") or -1) != simulation_days
            or str(prepared_probe.get("risk_csv_sha256") or "")
            != context._sha256_file(risk_csv)
            or prepared_probe.get("case_artifacts_pruned") is not True
            or prepared_probe.get("risk_row") != risk_row
            or prepared_probe.get("campaign_signature")
            != manifest.get("campaign_signature")
            or prepared_probe.get("operating_point_id")
            != point.get("operating_point_id")
            or int(prepared_probe.get("seed") or -1) != seed
            or prepared_probe.get("lane_id") != lane.lane_id
            or prepared_probe.get("mechanism") != mechanism.key
        ):
            raise ValueError(f"Prepared incident probe contract differs for {key}")
        case_dir: Path | None = None
        metrics = dict(prepared_probe.get("metrics") or {})
        errors = [str(value) for value in prepared_probe.get("validation_errors") or []]
        proof = dict(prepared_probe.get("incident_proof") or {})
        incident_pre_incident_trace = str(
            prepared_probe.get("incident_pre_incident_shipment_trace_sha256") or ""
        )
        if not metrics or not proof or not incident_pre_incident_trace:
            raise ValueError(f"Prepared incident probe payload is incomplete for {key}")
        if int(metrics.get("simulation_days") or -1) != simulation_days:
            errors.append(
                "prepared incident metrics horizon differs from probe horizon"
            )
    else:
        case_dir = context._run_engine(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=key,
            seed=seed,
            risk_csv=risk_csv,
            simulation_days=simulation_days,
        )
        metrics, shipment_rows, applied_rows, errors, daily_context = (
            context._extract_metrics(
                case_dir=case_dir,
                manifest=manifest,
                point=point,
                risk_csv=risk_csv,
                expected_event_id=str(risk_row["event_id"]),
                simulation_days=simulation_days,
            )
        )
        metrics["impact_window_metrics"] = context._window_metrics(
            service_rows=daily_context["service_rows"],
            production_rows=daily_context["production_rows"],
            start_day=int(target["impact_window_start_day"]),
            end_day=int(target["impact_window_end_day"]),
        )
        metrics["causal_window_metrics"] = context._window_metrics(
            service_rows=daily_context["service_rows"],
            production_rows=daily_context["production_rows"],
            start_day=int(target["causal_window_start_day"]),
            end_day=int(target["causal_window_end_day"]),
        )
        proof, trace_errors = context.validate_incident_trace(
            mechanism=mechanism,
            lane=lane,
            target=target,
            risk_row=risk_row,
            shipment_rows=shipment_rows,
            applied_rows=applied_rows,
            simulation_days=simulation_days,
        )
        errors.extend(trace_errors)
        incident_pre_incident_trace = context._shipment_trace_signature(
            shipment_rows,
            end_day_exclusive=int(target["target_window_start_day"]),
        )
    expected_pre_incident_trace = str(
        target.get("baseline_pre_incident_shipment_trace_sha256") or ""
    )
    pre_incident_trace_match = bool(expected_pre_incident_trace) and (
        expected_pre_incident_trace == incident_pre_incident_trace
    )
    if not expected_pre_incident_trace:
        errors.append("paired baseline pre-incident shipment trace is missing")
    elif not pre_incident_trace_match:
        errors.append("incident shipment trace diverges before the disruption window")
    baseline_impact = target.get("baseline_impact_metrics") or {}
    incident_impact = metrics["impact_window_metrics"]
    if not baseline_impact:
        errors.append("paired baseline impact-window metrics are missing")
    else:
        for field in ("start_day", "end_day", "day_count"):
            if baseline_impact.get(field) != incident_impact.get(field):
                errors.append(f"paired impact-window {field} mismatch")
        for field in (
            "demand_qty_268091",
            "demand_qty_268967",
            "demand_qty_global",
        ):
            if not context.math.isclose(
                context._as_float(baseline_impact.get(field)),
                context._as_float(incident_impact.get(field)),
                rel_tol=1e-12,
                abs_tol=context.TARGET_QUANTITY_TOLERANCE,
            ):
                errors.append(f"paired impact-window {field} changed")
    baseline_causal = target.get("baseline_causal_metrics") or {}
    incident_causal = metrics["causal_window_metrics"]
    if not baseline_causal:
        errors.append("paired baseline causal-window metrics are missing")
    else:
        for field in ("start_day", "end_day", "day_count"):
            if baseline_causal.get(field) != incident_causal.get(field):
                errors.append(f"paired causal-window {field} mismatch")
        for field in (
            "demand_qty_268091",
            "demand_qty_268967",
            "demand_qty_global",
        ):
            if not context.math.isclose(
                context._as_float(baseline_causal.get(field)),
                context._as_float(incident_causal.get(field)),
                rel_tol=1e-12,
                abs_tol=context.TARGET_QUANTITY_TOLERANCE,
            ):
                errors.append(f"paired causal-window {field} changed")
    proof["baseline_pre_incident_shipment_trace_sha256"] = expected_pre_incident_trace
    proof["incident_pre_incident_shipment_trace_sha256"] = incident_pre_incident_trace
    proof["pre_incident_shipment_trace_match"] = pre_incident_trace_match
    zero_exposure = (
        str(target.get("target_status") or "")
        == "identified_registered_window_no_positive_flow"
    )
    if zero_exposure:
        for baseline_window, incident_window, label in (
            (baseline_impact, incident_impact, "impact"),
            (baseline_causal, incident_causal, "causal"),
        ):
            for field in (
                "service_268091_pct",
                "service_268967_pct",
                "service_global_pct",
                "backlog_qty_days_global",
                "max_backlog_qty_global",
                "production_released_268091_qty",
                "production_released_268967_qty",
            ):
                if not context.math.isclose(
                    context._as_float(baseline_window.get(field)),
                    context._as_float(incident_window.get(field)),
                    rel_tol=0.0,
                    abs_tol=context.TARGET_QUANTITY_TOLERANCE,
                ):
                    errors.append(f"zero-exposure {label} metric changed: {field}")
    if metrics.get("warmup_core_state_sha256") != (
        baseline_evidence.get("metrics") or {}
    ).get("warmup_core_state_sha256"):
        errors.append("incident and baseline warmup core-state hashes differ")
    proof["incident_physically_exercised"] = (
        bool(proof.get("incident_physically_exercised")) and not errors
    )
    evidence = {
        **base,
        "status": (
            "valid_no_exposure"
            if zero_exposure and not errors
            else ("valid" if not errors else "invalid")
        ),
        "valid": not errors,
        "validation_errors": errors,
        "metrics": metrics,
        "incident_proof": proof,
        "risk_row": risk_row,
        "risk_csv_sha256": context._sha256_file(risk_csv),
        "prepared_probe_evidence_signature": (
            str(prepared_probe.get("probe_evidence_signature") or "")
            if prepared_probe is not None
            else ""
        ),
        "run_dir": str(case_dir) if case_dir is not None else "",
    }
    context._persist_evidence(context._evidence_path(shard_dir, key), evidence)
    if evidence["valid"] and case_dir is not None:
        context.campaign_core.prune_case_artifacts(case_dir)
    return evidence


def _run_engine(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    case_key: str,
    seed: int,
    risk_csv: Path | None,
    simulation_days: int,
    context: Context,
) -> Path:
    case_dir = shard_dir / "cases" / case_key
    required = (
        case_dir / "summaries" / "first_simulation_summary.json",
        case_dir / "data" / "production_demand_service_daily.csv",
        case_dir / "data" / "production_supplier_shipments_daily.csv",
    )
    if case_dir.exists():
        if all(path.is_file() for path in required):
            summary = context._read_json(required[0])
            if int(summary.get("sim_days") or -1) != simulation_days:
                raise RuntimeError(
                    f"Promoted case horizon differs for {case_key}: "
                    f"{summary.get('sim_days')} != {simulation_days}"
                )
            return case_dir
        raise RuntimeError(f"Incomplete promoted case requires review: {case_dir}")
    context._recover_pending_failed_attempt_cleanup(
        shard_dir=shard_dir,
        manifest=manifest,
        case_key=case_key,
    )
    attempt = shard_dir / "_attempts" / f"{case_key}__{context.uuid.uuid4().hex}"
    attempt.mkdir(parents=True, exist_ok=False)
    command = context._build_engine_command(
        manifest=manifest,
        point=point,
        case_dir=attempt,
        seed=seed,
        risk_csv=risk_csv,
        simulation_days=simulation_days,
    )
    log_path = attempt / "campaign_engine.log"
    try:
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(
                f"[{context.utc_now()}] COMMAND {context.json.dumps(command, ensure_ascii=False)}\n"
            )
            completed = context.subprocess.run(
                command,
                cwd=context.REPO_ROOT,
                stdout=stream,
                stderr=context.subprocess.STDOUT,
                text=True,
                check=False,
            )
    except Exception as exc:
        diagnostic = context._record_and_cleanup_failed_attempt(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=case_key,
            attempt=attempt,
            seed=seed,
            simulation_days=simulation_days,
            risk_csv=risk_csv,
            command=command,
            failure_kind="engine_launch_or_runtime_exception",
            failure_detail=f"{type(exc).__name__}: {exc}",
            return_code=None,
        )
        raise RuntimeError(
            f"Engine raised for {case_key}; compact diagnostic: {diagnostic}"
        ) from exc
    if completed.returncode != 0:
        diagnostic = context._record_and_cleanup_failed_attempt(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=case_key,
            attempt=attempt,
            seed=seed,
            simulation_days=simulation_days,
            risk_csv=risk_csv,
            command=command,
            failure_kind="engine_nonzero_exit",
            failure_detail=f"engine return code {completed.returncode}",
            return_code=int(completed.returncode),
        )
        raise RuntimeError(
            f"Engine failed for {case_key}; compact diagnostic: {diagnostic}"
        )
    attempt_required = (
        attempt / "summaries" / "first_simulation_summary.json",
        attempt / "data" / "production_demand_service_daily.csv",
        attempt / "data" / "production_supplier_shipments_daily.csv",
    )
    if not all(path.is_file() for path in attempt_required):
        missing = [
            path.relative_to(attempt).as_posix()
            for path in attempt_required
            if not path.is_file()
        ]
        diagnostic = context._record_and_cleanup_failed_attempt(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=case_key,
            attempt=attempt,
            seed=seed,
            simulation_days=simulation_days,
            risk_csv=risk_csv,
            command=command,
            failure_kind="engine_output_incomplete",
            failure_detail="missing required outputs: " + ", ".join(missing),
            return_code=int(completed.returncode),
        )
        raise RuntimeError(
            f"Engine output incomplete for {case_key}; compact diagnostic: {diagnostic}"
        )
    case_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        attempt.replace(case_dir)
    except Exception as exc:
        diagnostic = context._record_and_cleanup_failed_attempt(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            case_key=case_key,
            attempt=attempt,
            seed=seed,
            simulation_days=simulation_days,
            risk_csv=risk_csv,
            command=command,
            failure_kind="engine_output_promotion_failed",
            failure_detail=f"{type(exc).__name__}: {exc}",
            return_code=int(completed.returncode),
        )
        raise RuntimeError(
            f"Engine output promotion failed for {case_key}; compact diagnostic: "
            f"{diagnostic}"
        ) from exc
    return case_dir


def _execute_baseline(
    *,
    shard_dir: Path,
    manifest: Mapping[str, Any],
    point: Mapping[str, Any],
    lanes: Sequence[Lane],
    seed: int,
    reuse_roots: Sequence[Path],
    registered_targets: Sequence[Mapping[str, Any]],
    simulation_days: int,
    context: Context,
) -> dict[str, Any]:
    key = context._case_key(
        point_id=str(point["operating_point_id"]), seed=seed, stage="baseline"
    )
    adaptive_contract_signature = context._stable_sha256(
        [
            {
                "lane_id": target["lane_id"],
                "incident_windows": target.get("incident_windows") or {},
            }
            for target in registered_targets
        ]
    )
    signature = context._case_signature(
        manifest=manifest,
        point=point,
        seed=seed,
        stage="baseline",
        simulation_days=simulation_days,
        adaptive_contract_signature=adaptive_contract_signature,
    )
    existing = context._load_or_reuse_evidence(
        shard_dir=shard_dir,
        manifest=manifest,
        case_key=key,
        case_signature=signature,
        reuse_roots=reuse_roots,
    )
    if existing is not None:
        return existing
    case_dir = context._run_engine(
        shard_dir=shard_dir,
        manifest=manifest,
        point=point,
        case_key=key,
        seed=seed,
        risk_csv=None,
        simulation_days=simulation_days,
    )
    metrics, shipment_rows, _applied, errors, daily_context = context._extract_metrics(
        case_dir=case_dir,
        manifest=manifest,
        point=point,
        risk_csv=None,
        expected_event_id=None,
        simulation_days=simulation_days,
    )
    registered_by_lane = {
        str(target.get("lane_id") or ""): dict(target) for target in registered_targets
    }
    if set(registered_by_lane) != {lane.lane_id for lane in lanes}:
        raise ValueError("Registered baseline target matrix is incomplete")
    targets: list[dict[str, Any]] = []
    invariant_fields = (
        "target_window_start_day",
        "target_window_end_day",
        "target_window_days",
        "target_active_decision_days",
        "target_shipment_count",
        "target_shipment_ids",
        "target_planned_qty",
        "target_expected_delivered_qty",
        "target_latest_baseline_arrival_day",
        "target_latest_stressed_arrival_day",
        "required_simulation_days",
    )
    metadata_fields = (
        "cross_state_match_status",
        "cross_state_common_day_found",
        "cross_state_quantity_ratio",
        "cross_state_match_threshold_ratio",
        "state_comparison_valid",
        "state_exposure_max_decision_day",
        "state_exposure_max_window_start_day",
        "state_exposure_max_group_qty",
        "cross_state_matched_min_group_qty",
        "cross_state_matched_max_group_qty",
        "cross_state_matched_quantities_json",
        "target_selected_independently_by_operating_point",
    )
    for lane in lanes:
        registered = registered_by_lane[lane.lane_id]
        selected = context.select_unique_reference_shipment(
            shipment_rows,
            lane=lane,
            days=simulation_days,
            forced_decision_day=int(registered["target_window_start_day"]),
            target_window_days=context.INCIDENT_DISRUPTION_DAYS,
            state_match_metadata={
                key: registered.get(key, "") for key in metadata_fields
            },
        )
        mismatches = [
            field
            for field in invariant_fields
            if selected.get(field) != registered.get(field)
        ]
        if mismatches:
            selected["target_status"] = (
                "not_applicable_discovery_extended_trace_mismatch"
            )
            selected["reason"] = (
                "J0-J719 target trace differs between discovery and extended baseline: "
                + ", ".join(mismatches)
            )
            errors.append(f"{lane.lane_id}: {selected['reason']}")
        selected["incident_windows"] = dict(registered.get("incident_windows") or {})
        selected["baseline_pre_incident_shipment_trace_sha256"] = (
            context._shipment_trace_signature(
                shipment_rows,
                end_day_exclusive=int(selected["target_window_start_day"]),
            )
        )
        targets.append(
            context._target_with_lane_fields(
                selected,
                manifest=manifest,
                shard_id=str(manifest.get("active_shard_id") or ""),
                point=point,
                seed=seed,
                lane=lane,
                simulation_days=simulation_days,
            )
        )
    for target in targets:
        if str(target.get("target_status") or "").startswith("identified_"):
            target["baseline_impact_metrics"] = context._window_metrics(
                service_rows=daily_context["service_rows"],
                production_rows=daily_context["production_rows"],
                start_day=int(target["impact_window_start_day"]),
                end_day=int(target["impact_window_end_day"]),
            )
            target["baseline_causal_metrics"] = context._window_metrics(
                service_rows=daily_context["service_rows"],
                production_rows=daily_context["production_rows"],
                start_day=int(target["causal_window_start_day"]),
                end_day=int(target["causal_window_end_day"]),
            )
            target["baseline_causal_metrics_by_mechanism"] = {
                mechanism_key: context._window_metrics(
                    service_rows=daily_context["service_rows"],
                    production_rows=daily_context["production_rows"],
                    start_day=int(window["causal_window_start_day"]),
                    end_day=int(window["causal_window_end_day"]),
                )
                for mechanism_key, window in (
                    target.get("incident_windows") or {}
                ).items()
            }
    evidence = context._base_evidence(
        manifest=manifest,
        shard_id=str(manifest.get("active_shard_id") or ""),
        point=point,
        seed=seed,
        stage="baseline",
        case_key=key,
        case_signature=signature,
        simulation_days=simulation_days,
    )
    evidence.update(
        {
            "status": "valid" if not errors else "invalid",
            "valid": not errors,
            "validation_errors": errors,
            "metrics": metrics,
            "shipment_targets": targets,
            "baseline_case_signature": signature,
            "run_dir": str(case_dir),
        }
    )
    context._persist_evidence(context._evidence_path(shard_dir, key), evidence)
    if evidence["valid"]:
        context.campaign_core.prune_case_artifacts(case_dir)
    return evidence


def _load_shards(manifest: Mapping[str, Any], *, context: Context) -> list[Shard]:
    raw = manifest.get("shards")
    if not isinstance(raw, list) or len(raw) != context.EXPECTED_SHARD_COUNT:
        raise ValueError("Campaign manifest must contain exactly 18 shard designs")
    shards: list[context.Shard] = []
    for row in raw:
        if not isinstance(row, context.Mapping):
            raise ValueError("Invalid shard design row")
        seeds = tuple(int(value) for value in row.get("seed_ids") or [])
        shard = context.Shard(
            shard_id=str(row.get("shard_id") or ""),
            shard_index=int(row.get("shard_index") or 0),
            operating_point_id=str(row.get("operating_point_id") or ""),
            seed_block=int(row.get("seed_block") or 0),
            seed_ids=seeds,
        )
        if (
            not shard.shard_id
            or shard.operating_point_id not in set(context.EXPECTED_OPERATING_POINTS)
            or shard.seed_block not in range(1, 7)
            or len(shard.seed_ids) != 5
            or int(row.get("total_rows") or 0) != context.EXPECTED_CASES_PER_SHARD
        ):
            raise ValueError(f"Invalid shard contract: {row}")
        shards.append(shard)
    if {shard.shard_index for shard in shards} != set(range(1, 19)):
        raise ValueError("Shard indices must be exactly 1 through 18")
    if len({shard.shard_id for shard in shards}) != context.EXPECTED_SHARD_COUNT:
        raise ValueError("Shard ids are not unique")
    expected_pairs = {
        (point_id, block_number)
        for point_id in context.EXPECTED_OPERATING_POINTS
        for block_number in range(1, 7)
    }
    if {
        (shard.operating_point_id, shard.seed_block) for shard in shards
    } != expected_pairs:
        raise ValueError(
            "Shard plan must cover each operating point x seed block exactly once"
        )
    block_seeds: dict[int, tuple[int, ...]] = {}
    for shard in shards:
        previous = block_seeds.setdefault(shard.seed_block, shard.seed_ids)
        if previous != shard.seed_ids:
            raise ValueError(
                "A seed block must be identical across all operating points"
            )
    planned_seeds = tuple(int(value) for value in manifest.get("seeds") or [])
    flattened = tuple(value for block in range(1, 7) for value in block_seeds[block])
    if len(set(flattened)) != 30 or planned_seeds != flattened:
        raise ValueError("Shard seed blocks do not match the 30 signed repetitions")
    return sorted(shards, key=lambda shard: shard.shard_index)


def _progress_payload(
    *,
    manifest: Mapping[str, Any],
    contract: Mapping[str, Any],
    status: str,
    parallel_shards: int,
    workers_per_shard: int,
    started_at_utc: str,
    started_monotonic: float,
    shards: Sequence[Shard],
    queued: Sequence[Shard],
    active: Mapping[str, ActiveShard],
    completed: Mapping[str, float],
    failed: Sequence[Mapping[str, Any]],
    wakefulness_state: Mapping[str, Any] | None = None,
    phase: str = None,
    discovery_status: str = None,
    discovery_pid: int | None = None,
    discovery_log_path: Path | None = None,
    context: Context,
) -> dict[str, Any]:
    elapsed = max(0.0, context.time.monotonic() - started_monotonic)
    durations = [
        value
        for value in completed.values()
        if context.math.isfinite(value) and value > 0
    ]
    mean_duration = sum(durations) / len(durations) if durations else 0.0
    remaining = max(0, len(shards) - len(completed) - len(failed))
    eta = (
        mean_duration * remaining / parallel_shards if durations and remaining else 0.0
    )
    payload = {
        "schema_version": context.PROGRESS_SCHEMA_VERSION,
        "campaign_signature": manifest["campaign_signature"],
        "launch_contract_signature": contract["launch_contract_signature"],
        "status": status,
        "phase": phase,
        "target_discovery_status": discovery_status,
        "target_discovery_pid": discovery_pid or "",
        "target_discovery_log_path": (
            str(discovery_log_path) if discovery_log_path is not None else ""
        ),
        "parallel_shards": parallel_shards,
        "workers_per_shard": workers_per_shard,
        "maximum_engine_processes": parallel_shards * workers_per_shard,
        "planned_shard_count": len(shards),
        "completed_shard_count": len(completed),
        "failed_shard_count": len(failed),
        "active_shard_count": len(active),
        "queued_shard_count": len(queued),
        "completed_shard_ids": sorted(completed),
        "queued_shard_ids": [shard.shard_id for shard in queued],
        "active_shards": [
            {
                "shard_id": item.shard.shard_id,
                "pid": item.process.pid,
                "started_at_utc": item.started_at_utc,
                "log_path": str(item.log_path),
                "command_sha256": context._stable_sha256(item.command),
            }
            for item in sorted(
                active.values(), key=lambda value: value.shard.shard_index
            )
        ],
        "failures": list(failed),
        "started_at_utc": started_at_utc,
        "updated_at_utc": context.utc_now(),
        "elapsed_seconds": elapsed,
        "mean_completed_shard_seconds": mean_duration,
        "eta_seconds": eta,
        "failure_policy": contract["failure_policy"],
    }
    if wakefulness_state is not None:
        payload["wakefulness"] = dict(wakefulness_state)
    return payload


def _load_discovery_service_evidence(
    *,
    evidence: InputEvidence,
    manifest: Mapping[str, Any],
    disruption_window_days: int,
    context: Context,
) -> dict[tuple[str, int], dict[str, float]]:
    """Verify every discovery case and retain only its service totals."""

    paths = sorted(
        (evidence.manifest_path.parent / "target_discovery" / "evidence").glob("*.json")
    )
    expected_keys = {
        (point, seed)
        for point in context.OPERATING_POINTS
        for seed in (context.DESIGN_SEED, *context.EXPECTED_SEEDS)
    }
    state_by_id = {
        str(row.get("operating_point_id")): row
        for row in manifest.get("states") or []
        if isinstance(row, context.Mapping)
    }
    if set(state_by_id) != set(context.OPERATING_POINTS) or len(paths) != len(
        expected_keys
    ):
        raise context.CampaignValidationError(
            "The 93 signed target-discovery cases are required"
        )
    result: dict[tuple[str, int], dict[str, float]] = {}
    fields = (
        "demand_qty_global",
        "on_due_qty_global",
        "demand_qty_268091",
        "on_due_qty_268091",
        "demand_qty_268967",
        "on_due_qty_268967",
    )
    for path in paths:
        payload = context._read_json(path)
        context._verify_payload_signature(
            payload, "evidence_signature", label="target-discovery evidence"
        )
        point = str(payload.get("operating_point_id") or "")
        try:
            seed = int(payload.get("seed"))
        except (TypeError, ValueError) as exc:
            raise context.CampaignValidationError(
                "Invalid target-discovery seed"
            ) from exc
        key = (point, seed)
        if key not in expected_keys or key in result:
            raise context.CampaignValidationError(
                "Target-discovery case is unexpected or duplicated"
            )
        state = state_by_id[point]
        expected_discovery_signature = context._stable_sha256(
            {
                "campaign_signature": manifest["campaign_signature"],
                "engine_sha256": manifest["engine_sha256"],
                "engine_profile_sha256": manifest["engine_profile_sha256"],
                "point_id": point,
                "graph_sha256": state["graph_sha256"],
                "seed": seed,
                "simulation_days": context.STATE_EVALUATION_DAYS,
                "purpose": f"cross_state_{disruption_window_days}d_target_discovery",
            }
        )
        if (
            payload.get("schema_version")
            != f"{context.INPUT_CAMPAIGN_SCHEMA_VERSION}.target_discovery.case.v1"
            or payload.get("campaign_signature") != manifest.get("campaign_signature")
            or payload.get("engine_sha256") != manifest.get("engine_sha256")
            or payload.get("discovery_signature") != expected_discovery_signature
            or int(payload.get("simulation_days", -1)) != context.STATE_EVALUATION_DAYS
        ):
            raise context.CampaignValidationError(
                "Target-discovery case signature or contract differs"
            )
        raw_metrics = payload.get("state_service_metrics")
        if not isinstance(raw_metrics, context.Mapping):
            raise context.CampaignValidationError(
                "Target-discovery service totals are missing"
            )
        converted: dict[str, float] = {}
        for field in fields:
            try:
                value = float(raw_metrics[field])
            except (KeyError, TypeError, ValueError) as exc:
                raise context.CampaignValidationError(
                    f"Invalid target-discovery service field: {field}"
                ) from exc
            if not context.math.isfinite(value) or value < 0:
                raise context.CampaignValidationError(
                    f"Invalid target-discovery service field: {field}"
                )
            converted[field] = value
        for suffix in ("global", "268091", "268967"):
            demand = converted[f"demand_qty_{suffix}"]
            on_due = converted[f"on_due_qty_{suffix}"]
            if (
                demand <= context.NUMERIC_TOLERANCE
                or on_due > demand + context.NUMERIC_TOLERANCE
            ):
                raise context.CampaignValidationError(
                    "Discovery demand/on-due totals are inconsistent"
                )
        result[key] = converted
    if set(result) != expected_keys:
        raise context.CampaignValidationError(
            "Target-discovery case matrix is incomplete"
        )
    return result


def validate_shard_progress(
    campaign_root: Path,
    *,
    campaign_signature: str,
    expected_shard_ids: frozenset[str],
    context: Context,
) -> dict[str, Any]:
    paths = sorted(campaign_root.resolve().glob("shards/*/progress.json"))
    if len(paths) != context.EXPECTED_SHARD_COUNT:
        raise context.CampaignValidationError(
            f"Expected {context.EXPECTED_SHARD_COUNT} shard progress files, found {len(paths)}"
        )
    seen: set[str] = set()
    digests: dict[str, str] = {}
    for path in paths:
        payload = context._read_json(path)
        shard_id = str(payload.get("shard_id") or path.parent.name)
        running = payload.get("running_case_keys") or []
        if (
            payload.get("schema_version")
            != f"{context.INPUT_CAMPAIGN_SCHEMA_VERSION}.progress.v1"
            or payload.get("campaign_signature") != campaign_signature
            or payload.get("status") != "complete"
            or int(payload.get("planned_case_count", -1))
            != context.EXPECTED_ROWS_PER_SHARD
            or int(payload.get("completed_case_count", -1))
            != context.EXPECTED_ROWS_PER_SHARD
            or int(payload.get("failed_case_count", -1)) != 0
            or bool(running)
            or bool(payload.get("errors"))
            or shard_id != path.parent.name
            or shard_id in seen
        ):
            raise context.CampaignValidationError(
                f"Shard is not complete and error-free: {path}"
            )
        seen.add(shard_id)
        digests[str(path)] = context._sha256(path)
    if seen != set(expected_shard_ids):
        raise context.CampaignValidationError(
            "Shard progress IDs differ from the signed manifest"
        )
    return {
        "status": "complete",
        "shard_count": len(paths),
        "planned_case_count": context.EXPECTED_TOTAL_COUNT,
        "completed_case_count": context.EXPECTED_TOTAL_COUNT,
        "failed_case_count": 0,
        "progress_paths_sha256": digests,
    }


def _validate_preflight_from_discovery(
    *,
    preflight: Mapping[str, Any],
    manifest: Mapping[str, Any],
    discovery: Mapping[tuple[str, int], Mapping[str, float]],
    context: Context,
) -> dict[str, dict[str, float]]:
    """Recompute every scientific holdout gate from signed discovery totals."""

    state_inputs = {
        str(row["operating_point_id"]): row
        for row in manifest.get("states") or []
        if isinstance(row, context.Mapping)
    }
    reported_states = {
        str(row.get("operating_point_id")): row
        for row in preflight.get("states") or []
        if isinstance(row, context.Mapping)
    }
    if set(reported_states) != set(context.OPERATING_POINTS):
        raise context.CampaignValidationError("Preflight state results are missing")

    def ratio_of_sums(
        rows: Sequence[context.Mapping[str, float]], suffix: str
    ) -> float:
        demand = sum(float(row[f"demand_qty_{suffix}"]) for row in rows)
        return 100.0 * sum(float(row[f"on_due_qty_{suffix}"]) for row in rows) / demand

    def seed_service(row: context.Mapping[str, float], suffix: str) -> float:
        return (
            100.0
            * float(row[f"on_due_qty_{suffix}"])
            / float(row[f"demand_qty_{suffix}"])
        )

    random_generator = context.random.Random(context.BOOTSTRAP_SEED)
    bootstrap_indices = [
        [
            random_generator.randrange(context.EXPECTED_REPETITION_COUNT)
            for _ in context.EXPECTED_SEEDS
        ]
        for _ in range(context.BOOTSTRAP_REPLICATES)
    ]
    services: dict[str, dict[str, float]] = {}
    seed_services: dict[str, dict[str, list[float]]] = {}
    failures: list[str] = []
    for seed in context.EXPECTED_SEEDS:
        reference = discovery[("op_100", seed)]
        for point in context.OPERATING_POINTS[1:]:
            candidate = discovery[(point, seed)]
            for suffix in ("global", "268091", "268967"):
                if not context.math.isclose(
                    float(reference[f"demand_qty_{suffix}"]),
                    float(candidate[f"demand_qty_{suffix}"]),
                    rel_tol=1e-12,
                    abs_tol=context.NUMERIC_TOLERANCE,
                ):
                    raise context.CampaignValidationError(
                        "Paired holdout demand differs across operating states"
                    )
    for point in context.OPERATING_POINTS:
        rows = [discovery[(point, seed)] for seed in context.EXPECTED_SEEDS]
        by_measure = {
            suffix: ratio_of_sums(rows, suffix)
            for suffix in ("global", "268091", "268967")
        }
        by_seed = {
            suffix: [seed_service(row, suffix) for row in rows]
            for suffix in ("global", "268091", "268967")
        }
        seed_services[point] = by_seed
        median_global = float(context.np.median(by_seed["global"]))
        bootstrap_global = [
            ratio_of_sums([rows[index] for index in indices], "global")
            for indices in bootstrap_indices
        ]
        ci_low = context._linear_quantile(bootstrap_global, 0.025)
        ci_high = context._linear_quantile(bootstrap_global, 0.975)
        reported = reported_states[point]
        target_pct = float(state_inputs[point]["target_service_pct"])
        comparisons = {
            "target_service_pct": target_pct,
            "service_global_ratio_of_sums_pct": by_measure["global"],
            "service_global_seed_median_pct": median_global,
            "service_268091_ratio_of_sums_pct": by_measure["268091"],
            "service_268967_ratio_of_sums_pct": by_measure["268967"],
            "global_service_bootstrap_ci95_low_pct": ci_low,
            "global_service_bootstrap_ci95_high_pct": ci_high,
        }
        for field, expected in comparisons.items():
            try:
                actual = float(reported[field])
            except (KeyError, TypeError, ValueError) as exc:
                raise context.CampaignValidationError(
                    f"Preflight field is missing: {field}"
                ) from exc
            if not context.math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8):
                raise context.CampaignValidationError(
                    f"Preflight field does not match signed discovery evidence: {field}"
                )
        if reported.get("accepted") is not True or reported.get("failures") not in (
            [],
            None,
        ):
            failures.append(f"{point}: reported state is not accepted without failures")
        if point == "op_100":
            if not (
                98.5 <= by_measure["global"] <= 100.0 + context.NUMERIC_TOLERANCE
                and 98.5 <= median_global <= 100.0 + context.NUMERIC_TOLERANCE
                and by_measure["268091"] >= 98.5 - context.NUMERIC_TOLERANCE
                and by_measure["268967"] >= 98.5 - context.NUMERIC_TOLERANCE
            ):
                failures.append(
                    "op_100 fails the healthy-state global/product holdout gate"
                )
        else:
            lower = target_pct - 1.5
            upper = target_pct + 1.5
            if not (
                lower <= by_measure["global"] <= upper
                and lower <= median_global <= upper
                and by_measure["268091"] < 99.5 - context.NUMERIC_TOLERANCE
                and by_measure["268967"] < 99.5 - context.NUMERIC_TOLERANCE
            ):
                failures.append(
                    f"{point} fails its signed target/saturation holdout gate"
                )
        services[point] = {
            "global": by_measure["global"],
            "268091": by_measure["268091"],
            "268967": by_measure["268967"],
            "ci95_low": ci_low,
            "ci95_high": ci_high,
            "median_global": median_global,
            "target": target_pct,
        }
    pooled_ordering = {
        measure: services["op_100"][measure]
        > services["op_93"][measure]
        > services["op_80"][measure]
        for measure in ("global", "268091", "268967")
    }
    order_counts = {
        measure: sum(
            seed_services["op_100"][measure][index]
            > seed_services["op_93"][measure][index]
            > seed_services["op_80"][measure][index]
            for index in range(context.EXPECTED_REPETITION_COUNT)
        )
        for measure in ("global", "268091", "268967")
    }
    joint_order_count = sum(
        all(
            seed_services["op_100"][measure][index]
            > seed_services["op_93"][measure][index]
            > seed_services["op_80"][measure][index]
            for measure in ("global", "268091", "268967")
        )
        for index in range(context.EXPECTED_REPETITION_COUNT)
    )
    product_checks = preflight.get("product_seed_ordering_checks")
    valid_product_checks = isinstance(product_checks, context.Mapping) and all(
        isinstance(product_checks.get(product), context.Mapping)
        and int(product_checks[product].get("ordered_seed_count", -1))
        == order_counts[product]
        and product_checks[product].get("ordering_observed_in_at_least_24_of_30_seeds")
        == (order_counts[product] >= context.MIN_COMPARABLE_SEEDS)
        and product_checks[product].get("acceptance_gate") is True
        for product in ("268091", "268967")
    )
    if (
        not all(pooled_ordering.values())
        or joint_order_count < context.MIN_COMPARABLE_SEEDS
    ):
        failures.append(
            "Global and product service states are not jointly ordered on 24 seeds"
        )
    if (
        preflight.get("pooled_ordering_by_measure") != pooled_ordering
        or preflight.get("seed_order_counts") != order_counts
        or int(preflight.get("joint_seed_order_count", -1)) != joint_order_count
        or int(preflight.get("joint_seed_order_required", -1))
        != context.MIN_COMPARABLE_SEEDS
        or int(preflight.get("minimum_seed_order_count", -1))
        != context.MIN_COMPARABLE_SEEDS
        or not valid_product_checks
        or preflight.get("ordering_valid") is not all(pooled_ordering.values())
        or preflight.get("seed_ordering_valid")
        is not (joint_order_count >= context.MIN_COMPARABLE_SEEDS)
    ):
        failures.append(
            "Reported preflight ordering differs from signed discovery evidence"
        )
    if failures:
        raise context.CampaignValidationError("; ".join(failures))
    return services


def build_global_lane_priority(
    lane_stats: pd.DataFrame,
    lane_bootstrap: Mapping[tuple[str, str, str, str], Mapping[str, np.ndarray]],
    *,
    context: Context,
) -> pd.DataFrame:
    """Rank every physical lane together while retaining its product stratum."""

    records = [row.to_dict() for _, row in lane_stats.iterrows()]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(
            (str(record["operating_point_id"]), str(record["mechanism"])), []
        ).append(record)
    for group_records in grouped.values():
        group_records.sort(key=lambda row: str(row["lane_id"]))
        keys = [
            (
                str(row["operating_point_id"]),
                str(row["mechanism"]),
                str(row["target_product_id"]),
                str(row["lane_id"]),
            )
            for row in group_records
        ]
        context._decorate_rank_group(
            group_records,
            [lane_bootstrap[key]["fixed"] for key in keys],
            [lane_bootstrap[key]["causal"] for key in keys],
        )
        for row in group_records:
            row["ranking_scope"] = "all_target_products"
            row["ranking_within_target_product"] = False
            row["fixed360_effect_mean_pp"] = row[f"{context.PRIMARY_METRIC}_mean"]
            row["bootstrap_ci95_low"] = row[f"{context.PRIMARY_METRIC}_ci95_low"]
            row["bootstrap_ci95_high"] = row[f"{context.PRIMARY_METRIC}_ci95_high"]
            row["positive_mean_effect"] = (
                row[f"{context.PRIMARY_METRIC}_mean"] > context.NUMERIC_TOLERANCE
            )
            row["priority_group"] = row["priority_status"]
    return (
        context.pd.DataFrame(records)
        .sort_values(["operating_point_id", "mechanism", "position", "lane_id"])
        .reset_index(drop=True)
    )
