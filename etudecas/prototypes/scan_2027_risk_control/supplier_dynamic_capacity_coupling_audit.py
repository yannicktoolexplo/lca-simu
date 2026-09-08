#!/usr/bin/env python3
"""Audit the requirement/capacity coupling before the dynamic-reference smoke.

This module is deliberately analytical: it reads an already completed supplier
parameter export and replays the *initial sizing formulas* found in the engine.
It never launches the simulation engine and must not be interpreted as a new
simulation result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "etudecas.dynamic_capacity_coupling_audit.v2"
REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = REPO_ROOT.parent / "lca-simu-pr40-validation-artifacts-20260726"
DEFAULT_GRAPH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
DEFAULT_SUPPLIER_PARAMETERS = (
    ARTIFACT_ROOT
    / "supplier_network_post_priority_extensions_smoke_20260903_v1"
    / "cases"
    / "baseline"
    / "baseline_metrics__seed_340282"
    / "seed_340282"
    / "data"
    / "supplier_nominal_parameters.csv"
)
DEFAULT_CURRENT_FLOORS = (
    ARTIFACT_ROOT
    / "supplier_network_risk_screen_20260902_v2"
    / "inputs"
    / "prepared_physical_supplier_floors.csv"
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
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "supplier_dynamic_capacity_coupling_audit_20260904_v3"

AUDIT_JSON = "capacity_coupling_audit.json"
LANE_CSV = "supplier_capacity_coupling_rows.csv"
PAIR_CSV = "requirement_pair_scope.csv"
REPORT_MD = "RAPPORT_COUPLAGE_BESOINS_CAPACITES.md"
FROZEN_SUPPLIER_PARAMETERS = "source_supplier_nominal_parameters.csv"

# These three pairs were already forced dynamic by the managed V3 command.
ALREADY_DYNAMIC_PAIRS = {
    "M-1430|item:344135",
    "M-1810|item:338929",
    "SDC-1450|item:021081",
}
EXPECTED_COUNTS = {
    "supplier_capacity_rows": 33,
    "current_exact_capacity_overrides": 2,
    "current_scale_320_rows": 31,
    "changed_requirement_pairs_with_supplier_lanes": 19,
    "supplier_lanes_in_changed_requirement_scope": 27,
    "estimated_changed_direct_capacities": 22,
    "estimated_changed_upstream_capacities": 21,
}
TOLERANCE = 1e-6


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _number(row: Mapping[str, Any], field: str) -> float:
    raw = row.get(field)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Finite number required for {field}: {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"Finite number required for {field}: {raw!r}")
    return value


def _different(left: float, right: float) -> bool:
    scale = max(1.0, abs(left), abs(right))
    return abs(left - right) > TOLERANCE * scale


def _profile_pairs(path: Path, flag: str) -> set[str]:
    args = _read_json(path).get("args")
    if not isinstance(args, list):
        raise ValueError(f"Profile arguments are invalid: {path}")
    result: set[str] = set()
    for index, value in enumerate(args):
        if value != flag:
            continue
        if index + 1 >= len(args):
            raise ValueError(f"Missing value after {flag}: {path}")
        parts = str(args[index + 1]).split(",", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Malformed pair after {flag}: {args[index + 1]!r}")
        result.add(f"{parts[0]}|{parts[1]}")
    return result


def _review_days(graph_node: Mapping[str, Any]) -> float:
    raw = (
        ((graph_node.get("policies") or {}).get("simulation_policy") or {}).get(
            "review_period_days"
        )
    )
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 1.0
    return max(1.0, value)


def replay_direct_capacity(
    row: Mapping[str, Any], *, demand_anchor: float, review_days: float
) -> tuple[float, float, str]:
    """Replay ``derive_supplier_daily_capacity_by_pair`` for one single-lane pair."""

    explicit_capacity = max(0.0, _number(row, "explicit_capacity_qty_per_day"))
    process_capacity = max(0.0, _number(row, "process_capacity_qty_per_day"))
    initial_stock = max(0.0, _number(row, "input_initial_stock_qty"))
    inventory_fallback = initial_stock / max(1.0, review_days)
    standard_order_qty = max(0.0, _number(row, "standard_order_qty"))
    lead_cover_days = max(1.0, _number(row, "lead_cover_days"))
    hint_days = max(1.0, review_days, lead_cover_days)
    standard_hint = standard_order_qty / hint_days if standard_order_qty > 0.0 else 0.0

    if explicit_capacity > 0.0:
        nominal = explicit_capacity
        basis = "explicit_capacity"
    elif process_capacity > 0.0:
        nominal = process_capacity
        basis = "process_capacity"
    elif demand_anchor > 0.0:
        nominal = max(demand_anchor * 1.25, inventory_fallback, 1.0)
        basis = "demand_anchor"
    else:
        nominal = max(inventory_fallback, 1.0)
        basis = "inventory_fallback"

    if (
        standard_hint > 0.0
        and nominal * 0.25 <= standard_hint <= nominal * 4.0
    ):
        nominal = max(nominal, standard_hint)
        basis += "+fia_hint"

    scale = max(0.01, _number(row, "applied_capacity_scale"))
    effective = max(0.01, nominal * scale)
    if explicit_capacity <= 0.0 and standard_order_qty > 0.0 and effective < standard_order_qty:
        effective = standard_order_qty
        basis += "+standard_lot_floor"
    return nominal, effective, basis


def replay_upstream_capacity(
    row: Mapping[str, Any], *, demand_anchor: float, review_days: float
) -> tuple[float, float]:
    """Replay the initial unmodelled-source daily-need and capacity formulas."""

    standard_order_qty = max(0.0, _number(row, "standard_order_qty"))
    lead_cover_days = max(1.0, _number(row, "lead_cover_days"))
    lot_daily_need = standard_order_qty / max(1.0, review_days, lead_cover_days)
    daily_need = max(0.0, demand_anchor, lot_daily_need)
    target_utilization = _number(row, "external_procurement_target_utilization")
    if daily_need > 0.0 and target_utilization <= 0.0:
        raise ValueError("Positive upstream need requires positive target utilization")
    nominal_capacity = daily_need / target_utilization if daily_need > 0.0 else 0.0
    return daily_need, nominal_capacity


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    fields = list(rows[0])
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _write_text(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def analyze(
    *,
    graph_path: Path,
    supplier_parameters_path: Path,
    current_floors_path: Path,
    old_profile_path: Path,
    new_profile_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    inputs = (
        graph_path,
        supplier_parameters_path,
        current_floors_path,
        old_profile_path,
        new_profile_path,
    )
    if any(path.is_symlink() or not path.is_file() for path in inputs):
        raise FileNotFoundError("All audit inputs must be regular, non-symlink files")

    graph = _read_json(graph_path)
    nodes = {str(row.get("id") or ""): row for row in graph.get("nodes") or []}
    supplier_rows = _read_csv(supplier_parameters_path)
    floor_rows = _read_csv(current_floors_path)
    old_static = _profile_pairs(old_profile_path, "--mrp-static-requirement-pair")
    new_dynamic = _profile_pairs(new_profile_path, "--mrp-dynamic-requirement-pair")
    if len(old_static) != 23 or len(new_dynamic) != 24:
        raise ValueError("Expected 23 old static pairs and 24 new dynamic pairs")
    if len(supplier_rows) != EXPECTED_COUNTS["supplier_capacity_rows"]:
        raise ValueError("Supplier export must contain exactly 33 capacity rows")
    source_keys = [f"{row.get('supplier_id')}|{row.get('item_id')}" for row in supplier_rows]
    if len(set(source_keys)) != len(source_keys):
        raise ValueError("Supplier/item source pairs must be unique")

    floor_source_keys = {
        f"{row.get('supplier_id')}|{row.get('item_id')}" for row in floor_rows
    }
    if len(floor_source_keys) != EXPECTED_COUNTS["current_exact_capacity_overrides"]:
        raise ValueError("Current physical floor file must contain exactly two source pairs")

    effective_old_static = old_static - ALREADY_DYNAMIC_PAIRS
    lane_rows: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    work_rows: list[tuple[Mapping[str, Any], dict[str, Any], float]] = []
    for source in supplier_rows:
        supplier_id = str(source.get("supplier_id") or "")
        item_id = str(source.get("item_id") or "")
        dst_node_id = str(source.get("dst_node_id") or "")
        pair_key = f"{dst_node_id}|{item_id}"
        source_key = f"{supplier_id}|{item_id}"
        if supplier_id not in nodes:
            raise ValueError(f"Supplier node is absent from graph: {supplier_id}")
        review_days = _review_days(nodes[supplier_id])
        in_scope = pair_key in effective_old_static and pair_key in new_dynamic
        old_requirement = max(0.0, _number(source, "downstream_requirement_qty_per_day"))
        dynamic_signal = max(0.0, _number(source, "downstream_signal_qty_per_day"))
        current_direct = max(0.0, _number(source, "effective_capacity_qty_per_day"))
        current_upstream_need = max(
            0.0, _number(source, "external_procurement_daily_need_qty")
        )
        current_upstream_capacity = max(
            0.0,
            _number(source, "external_procurement_nominal_capacity_qty_per_day"),
        )

        estimated_direct = current_direct
        direct_change = False
        replay_basis = "not_in_19_pair_switch"
        if in_scope:
            old_anchor = max(old_requirement, dynamic_signal)
            old_nominal, old_effective, _ = replay_direct_capacity(
                source, demand_anchor=old_anchor, review_days=review_days
            )
            if _different(
                old_nominal, _number(source, "nominal_capacity_qty_per_day")
            ) or _different(old_effective, current_direct):
                raise ValueError(f"Direct capacity formula replay mismatch: {source_key}")
            estimated_nominal, estimated_direct, replay_basis = replay_direct_capacity(
                source, demand_anchor=dynamic_signal, review_days=review_days
            )
            direct_change = _different(current_direct, estimated_direct)
        else:
            estimated_nominal = _number(source, "nominal_capacity_qty_per_day")

        row = {
            "supplier_id": supplier_id,
            "item_id": item_id,
            "dst_node_id": dst_node_id,
            "requirement_pair": pair_key,
            "supplier_source_pair": source_key,
            "in_19_pair_requirement_switch": in_scope,
            "current_exact_direct_capacity_override": source_key in floor_source_keys,
            "current_capacity_basis": str(source.get("capacity_basis") or ""),
            "current_capacity_scale": _number(source, "applied_capacity_scale"),
            "static_requirement_qty_per_day": old_requirement,
            "dynamic_signal_qty_per_day_from_existing_export": dynamic_signal,
            "static_to_dynamic_signal_ratio": (
                old_requirement / dynamic_signal if dynamic_signal > 0.0 else ""
            ),
            "current_direct_capacity_qty_per_day": current_direct,
            "estimated_dynamic_direct_nominal_qty_per_day": estimated_nominal,
            "estimated_dynamic_direct_capacity_qty_per_day": estimated_direct,
            "estimated_direct_capacity_change": direct_change,
            "estimated_direct_capacity_ratio": (
                estimated_direct / current_direct if current_direct > 0.0 else ""
            ),
            "estimated_dynamic_direct_capacity_basis": replay_basis,
            "current_upstream_daily_need_qty": current_upstream_need,
            "estimated_dynamic_upstream_daily_need_qty": current_upstream_need,
            "current_upstream_nominal_capacity_qty_per_day": current_upstream_capacity,
            "estimated_dynamic_upstream_nominal_capacity_qty_per_day": current_upstream_capacity,
            "estimated_upstream_capacity_change": False,
            "estimated_upstream_capacity_ratio": 1.0,
            "evidence_status": (
                "formula_replay_estimate_not_new_simulation"
                if in_scope
                else "existing_export_not_in_switch_scope"
            ),
        }
        lane_rows.append(row)
        work_rows.append((source, row, review_days))

    # The external-source policy allocates each downstream need across all
    # qualified suppliers in proportion to their direct capacities.  Replaying
    # that second stage requires all old and estimated-new capacities first.
    current_capacity_by_destination: dict[str, float] = defaultdict(float)
    estimated_capacity_by_destination: dict[str, float] = defaultdict(float)
    for row in lane_rows:
        pair_key = str(row["requirement_pair"])
        current_capacity_by_destination[pair_key] += float(
            row["current_direct_capacity_qty_per_day"]
        )
        estimated_capacity_by_destination[pair_key] += float(
            row["estimated_dynamic_direct_capacity_qty_per_day"]
        )

    for source, row, review_days in work_rows:
        if not bool(row["in_19_pair_requirement_switch"]):
            continue
        pair_key = str(row["requirement_pair"])
        source_key = str(row["supplier_source_pair"])
        current_total = current_capacity_by_destination[pair_key]
        estimated_total = estimated_capacity_by_destination[pair_key]
        if current_total <= 0.0 or estimated_total <= 0.0:
            raise ValueError(f"Positive allocation capacity required: {pair_key}")
        current_share = float(row["current_direct_capacity_qty_per_day"]) / current_total
        estimated_share = (
            float(row["estimated_dynamic_direct_capacity_qty_per_day"])
            / estimated_total
        )
        old_requirement = float(row["static_requirement_qty_per_day"])
        dynamic_signal = float(
            row["dynamic_signal_qty_per_day_from_existing_export"]
        )
        old_anchor = max(old_requirement * current_share, dynamic_signal * current_share)
        estimated_anchor = dynamic_signal * estimated_share
        old_need, old_upstream_capacity = replay_upstream_capacity(
            source, demand_anchor=old_anchor, review_days=review_days
        )
        current_upstream_need = float(row["current_upstream_daily_need_qty"])
        current_upstream_capacity = float(
            row["current_upstream_nominal_capacity_qty_per_day"]
        )
        if _different(old_need, current_upstream_need) or _different(
            old_upstream_capacity, current_upstream_capacity
        ):
            raise ValueError(f"Upstream capacity formula replay mismatch: {source_key}")
        estimated_need, estimated_upstream_capacity = replay_upstream_capacity(
            source, demand_anchor=estimated_anchor, review_days=review_days
        )
        row["estimated_dynamic_upstream_daily_need_qty"] = estimated_need
        row[
            "estimated_dynamic_upstream_nominal_capacity_qty_per_day"
        ] = estimated_upstream_capacity
        row["estimated_upstream_capacity_change"] = _different(
            current_upstream_capacity, estimated_upstream_capacity
        )
        row["estimated_upstream_capacity_ratio"] = (
            estimated_upstream_capacity / current_upstream_capacity
            if current_upstream_capacity > 0.0
            else ""
        )
        grouped[pair_key].append(row)

    pair_rows: list[dict[str, Any]] = []
    for pair_key, rows in sorted(grouped.items()):
        pair_rows.append(
            {
                "requirement_pair": pair_key,
                "supplier_lane_count": len(rows),
                "supplier_ids": "|".join(sorted(str(row["supplier_id"]) for row in rows)),
                "static_requirement_qty_per_day": rows[0][
                    "static_requirement_qty_per_day"
                ],
                "dynamic_signal_qty_per_day_from_existing_export": rows[0][
                    "dynamic_signal_qty_per_day_from_existing_export"
                ],
                "static_to_dynamic_signal_ratio": rows[0][
                    "static_to_dynamic_signal_ratio"
                ],
                "estimated_changed_direct_capacity_lane_count": sum(
                    bool(row["estimated_direct_capacity_change"]) for row in rows
                ),
                "estimated_changed_upstream_capacity_lane_count": sum(
                    bool(row["estimated_upstream_capacity_change"]) for row in rows
                ),
                "evidence_status": "formula_replay_estimate_not_new_simulation",
            }
        )

    counts = {
        "supplier_capacity_rows": len(lane_rows),
        "current_exact_capacity_overrides": sum(
            bool(row["current_exact_direct_capacity_override"]) for row in lane_rows
        ),
        "current_scale_320_rows": sum(
            math.isclose(float(row["current_capacity_scale"]), 320.0)
            for row in lane_rows
        ),
        "changed_requirement_pairs_with_supplier_lanes": len(pair_rows),
        "supplier_lanes_in_changed_requirement_scope": sum(
            bool(row["in_19_pair_requirement_switch"]) for row in lane_rows
        ),
        "estimated_changed_direct_capacities": sum(
            bool(row["estimated_direct_capacity_change"]) for row in lane_rows
        ),
        "estimated_changed_upstream_capacities": sum(
            bool(row["estimated_upstream_capacity_change"]) for row in lane_rows
        ),
    }
    if counts != EXPECTED_COUNTS:
        raise ValueError(f"Unexpected coupling audit counts: {counts}")

    baseline_rebuild = ((graph.get("meta") or {}).get("baseline_rebuild") or {})
    if (
        float(baseline_rebuild.get("supplier_capacity_scale") or 0.0) != 320.0
        or baseline_rebuild.get("type") != "real_demand_target_service_rebuild"
    ):
        raise ValueError("The graph no longer exposes the expected service-calibration provenance")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "analytical_pre_smoke_not_simulated",
        "created_at_utc": _utc_now(),
        "source_inputs": {
            "graph": {"path": str(graph_path.resolve()), "sha256": _sha256(graph_path)},
            "supplier_parameters": {
                "path": str(supplier_parameters_path.resolve()),
                "sha256": _sha256(supplier_parameters_path),
                "meaning": "already completed hybrid-reference export",
            },
            "current_floors": {
                "path": str(current_floors_path.resolve()),
                "sha256": _sha256(current_floors_path),
            },
            "old_profile": {
                "path": str(old_profile_path.resolve()),
                "sha256": _sha256(old_profile_path),
            },
            "new_profile": {
                "path": str(new_profile_path.resolve()),
                "sha256": _sha256(new_profile_path),
            },
        },
        "counts": counts,
        "interpretation": {
            "recommended_smoke_label": (
                "diagnostic couple besoins dynamiques + capacites et politique amont inferees"
            ),
            "mrp_only_causal_attribution_allowed": False,
            "supplier_ranking_allowed": False,
            "new_simulation_result": False,
            "estimated_values_meaning": (
                "deterministic replay of initialization formulas using fields in an existing export"
            ),
            "current_floor_option_semantics": (
                "exact replacement for listed supplier/item rows, not a lower bound; only two rows are listed"
            ),
            "partial_isolation_with_full_direct_capacity_csv": (
                "direct supplier release capacities can be fixed, but upstream procurement capacities and targets remain requirement-dependent"
            ),
            "true_heterogeneous_isolation_requires_engine_override": True,
            "required_future_override": (
                "per supplier/item override for external_procurement_nominal_capacity_qty_per_day"
            ),
            "diagnostic_only_workaround_without_engine_change": (
                "global non-binding policy_cap plus deterministic leads; intentionally non-industrial"
            ),
        },
        "capacity_scale_320": {
            "row_count": counts["current_scale_320_rows"],
            "graph_value": float(baseline_rebuild["supplier_capacity_scale"]),
            "graph_provenance_type": baseline_rebuild["type"],
            "target_service_by_item": baseline_rebuild.get("target_service_by_item"),
            "observed_supplier_capacity": False,
            "status": "service-calibration assumption requiring industrial validation",
        },
        "engine_mechanisms_audited": [
            "derive_supplier_daily_capacity_by_pair",
            "derive_unmodeled_supplier_source_policies",
            "load_supplier_neutral_floor_overrides",
            "apply supplier capacity override before upstream policy derivation",
        ],
        "future_isolated_comparison_contract": {
            "same_direct_capacity_by_supplier_item": True,
            "same_external_upstream_capacity_by_supplier_item": True,
            "same_lead_parameters": True,
            "deterministic_leads_for_first_mechanistic_check": True,
            "same_lot_and_allocation_policy": True,
            "same_initial_state_before_warmup": True,
            "different_state_at_J0_after_warmup_is_an_endogenous_result": True,
        },
    }
    return payload, lane_rows, pair_rows


def _render_report(payload: Mapping[str, Any], pairs: Sequence[Mapping[str, Any]]) -> str:
    counts = payload["counts"]
    lines = [
        "# Couplage besoins dynamiques / capacités fournisseurs",
        "",
        "**Statut : analyse de formule avant simulation.** Aucune nouvelle simulation n'a été lancée.",
        "",
        "La table de paramètres fournisseurs utilisée est copiée octet pour octet dans ce paquet. La validation dépend de cette copie interne et non du dossier de simulation, qui peut être allégé après le point d'arrêt.",
        "",
        "## Conclusion",
        "",
        "Le prochain essai old/new doit être présenté comme un **diagnostic couplé**. Le passage aux besoins dynamiques change le besoin MRP local, mais il sert aussi à dimensionner des capacités fournisseurs et la politique d'approvisionnement amont.",
        "",
        f"- {counts['changed_requirement_pairs_with_supplier_lanes']} couples usine-matière sont concernés, soit {counts['supplier_lanes_in_changed_requirement_scope']} voies fournisseur.",
        f"- La formule prévoit {counts['estimated_changed_direct_capacities']} capacités directes modifiées et {counts['estimated_changed_upstream_capacities']} capacités amont modifiées. Ce sont des estimations de formule, pas des résultats simulés.",
        f"- Le facteur 320 s'applique à {counts['current_scale_320_rows']}/{counts['supplier_capacity_rows']} lignes. Il vient d'un ancien calibrage au taux de service cible, pas d'une capacité fournisseur observée.",
        "- Le fichier de capacités actuel remplace exactement seulement deux capacités (338929 et 344135); malgré son nom, il ne pose pas une simple borne minimale.",
        "",
        "## Portée des 19 couples",
        "",
        "| Usine / matière | Nombre de fournisseurs | Besoin statique | Signal dynamique existant | Rapport statique/dynamique |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in pairs:
        lines.append(
            "| {pair} | {count} | {static:.6g} | {dynamic:.6g} | {ratio:.3g} |".format(
                pair=str(row["requirement_pair"]).replace("|", "\\|"),
                count=row["supplier_lane_count"],
                static=float(row["static_requirement_qty_per_day"]),
                dynamic=float(row["dynamic_signal_qty_per_day_from_existing_export"]),
                ratio=float(row["static_to_dynamic_signal_ratio"]),
            )
        )
    lines.extend(
        [
            "",
            "## Décision pour le premier essai",
            "",
            "Conserver la comparaison prévue, mais l'étiqueter « diagnostic couplé besoins + capacités/politique amont ». Elle permet de vérifier la cohérence de la variante dynamique; elle ne permet pas d'attribuer seule un écart au calcul MRP.",
            "",
            "Une comparaison où les capacités directes sont figées par un CSV complet resterait seulement partiellement isolée : la capacité d'approvisionnement externe est recalculée depuis le besoin. Une isolation hétérogène et réaliste nécessite un futur paramètre moteur par fournisseur et matière pour `external_procurement_nominal_capacity_qty_per_day`.",
            "",
        ]
    )
    return "\n".join(lines)


def build(
    *,
    graph_path: Path,
    supplier_parameters_path: Path,
    current_floors_path: Path,
    old_profile_path: Path,
    new_profile_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError("Audit output directory must be new and empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    payload, lanes, pairs = analyze(
        graph_path=graph_path.resolve(),
        supplier_parameters_path=supplier_parameters_path.resolve(),
        current_floors_path=current_floors_path.resolve(),
        old_profile_path=old_profile_path.resolve(),
        new_profile_path=new_profile_path.resolve(),
    )
    supplier_parameters_origin = dict(payload["source_inputs"]["supplier_parameters"])
    frozen_supplier_parameters = output_dir / FROZEN_SUPPLIER_PARAMETERS
    shutil.copyfile(supplier_parameters_path, frozen_supplier_parameters)
    if _sha256(frozen_supplier_parameters) != supplier_parameters_origin["sha256"]:
        raise ValueError("Supplier-parameter snapshot differs from its source")
    payload["supplier_parameter_origin"] = {
        **supplier_parameters_origin,
        "validation_dependency": False,
        "availability_after_build_not_required": True,
    }
    payload["source_inputs"]["supplier_parameters"] = {
        "path": str(frozen_supplier_parameters.resolve()),
        "sha256": supplier_parameters_origin["sha256"],
        "meaning": (
            "byte-identical internal snapshot of the completed hybrid-reference "
            "export; immutable validation source after checkpoint pruning"
        ),
        "internal_snapshot": True,
    }
    payload["source_retention"] = {
        "supplier_parameters_copied_byte_for_byte": True,
        "validation_depends_on_internal_snapshot_only": True,
        "original_case_directory_may_be_summary_pruned": True,
    }
    _write_csv(output_dir / LANE_CSV, lanes)
    _write_csv(output_dir / PAIR_CSV, pairs)
    _write_text(output_dir / REPORT_MD, _render_report(payload, pairs))
    payload["files"] = {
        FROZEN_SUPPLIER_PARAMETERS: _sha256(frozen_supplier_parameters),
        LANE_CSV: _sha256(output_dir / LANE_CSV),
        PAIR_CSV: _sha256(output_dir / PAIR_CSV),
        REPORT_MD: _sha256(output_dir / REPORT_MD),
    }
    _write_json(output_dir / AUDIT_JSON, payload)
    return payload


def validate(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    payload = _read_json(output_dir / AUDIT_JSON)
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("status") != "analytical_pre_smoke_not_simulated"
        or payload.get("counts") != EXPECTED_COUNTS
    ):
        raise ValueError("Audit identity or counts are invalid")
    expected_inventory = {
        AUDIT_JSON,
        FROZEN_SUPPLIER_PARAMETERS,
        LANE_CSV,
        PAIR_CSV,
        REPORT_MD,
    }
    if {path.name for path in output_dir.iterdir() if path.is_file()} != expected_inventory:
        raise ValueError("Audit file inventory is invalid")
    for filename, expected_hash in (payload.get("files") or {}).items():
        path = output_dir / filename
        if not path.is_file() or _sha256(path) != expected_hash:
            raise ValueError(f"Audit file mismatch: {filename}")
    for source in (payload.get("source_inputs") or {}).values():
        path = Path(str(source.get("path") or ""))
        if path.is_symlink() or not path.is_file() or _sha256(path) != source.get("sha256"):
            raise ValueError(f"Audit source mismatch: {path}")
    supplier_parameters = (payload.get("source_inputs") or {}).get(
        "supplier_parameters"
    ) or {}
    frozen_path = Path(str(supplier_parameters.get("path") or ""))
    if (
        frozen_path.resolve() != (output_dir / FROZEN_SUPPLIER_PARAMETERS).resolve()
        or supplier_parameters.get("internal_snapshot") is not True
        or (payload.get("source_retention") or {}).get(
            "validation_depends_on_internal_snapshot_only"
        )
        is not True
        or (payload.get("supplier_parameter_origin") or {}).get(
            "validation_dependency"
        )
        is not False
        or str((payload.get("supplier_parameter_origin") or {}).get("sha256") or "")
        != str(supplier_parameters.get("sha256") or "")
    ):
        raise ValueError("Supplier-parameter snapshot contract is invalid")
    lanes = _read_csv(output_dir / LANE_CSV)
    pairs = _read_csv(output_dir / PAIR_CSV)
    recomputed_counts = {
        "supplier_capacity_rows": len(lanes),
        "current_exact_capacity_overrides": sum(
            row.get("current_exact_direct_capacity_override") == "True"
            for row in lanes
        ),
        "current_scale_320_rows": sum(
            math.isclose(float(row["current_capacity_scale"]), 320.0)
            for row in lanes
        ),
        "changed_requirement_pairs_with_supplier_lanes": len(pairs),
        "supplier_lanes_in_changed_requirement_scope": sum(
            row.get("in_19_pair_requirement_switch") == "True" for row in lanes
        ),
        "estimated_changed_direct_capacities": sum(
            row.get("estimated_direct_capacity_change") == "True" for row in lanes
        ),
        "estimated_changed_upstream_capacities": sum(
            row.get("estimated_upstream_capacity_change") == "True" for row in lanes
        ),
    }
    if recomputed_counts != EXPECTED_COUNTS or payload.get("counts") != recomputed_counts:
        raise ValueError("Audit CSV dimensions are invalid")
    return {
        "status": "valid_analytical_pre_smoke_not_simulated",
        "supplier_capacity_rows": len(lanes),
        "requirement_pair_rows": len(pairs),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("build", "validate"), default="build")
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument(
        "--supplier-parameters", type=Path, default=DEFAULT_SUPPLIER_PARAMETERS
    )
    parser.add_argument("--current-floors", type=Path, default=DEFAULT_CURRENT_FLOORS)
    parser.add_argument("--old-profile", type=Path, default=DEFAULT_OLD_PROFILE)
    parser.add_argument("--new-profile", type=Path, default=DEFAULT_NEW_PROFILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.mode == "build":
        result = build(
            graph_path=args.graph,
            supplier_parameters_path=args.supplier_parameters,
            current_floors_path=args.current_floors,
            old_profile_path=args.old_profile,
            new_profile_path=args.new_profile,
            output_dir=args.output_dir,
        )
        print(json.dumps({"status": result["status"], "counts": result["counts"]}))
    else:
        print(json.dumps(validate(args.output_dir)))


if __name__ == "__main__":
    main()
