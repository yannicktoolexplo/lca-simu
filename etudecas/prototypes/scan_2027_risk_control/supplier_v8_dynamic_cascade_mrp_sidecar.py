#!/usr/bin/env python3
"""Qualify paired V8 supplier cascades with the native MRP trace.

The established Stage3 lot qualification deliberately stops short of a full
stock--MRP--production--service claim because the frozen V4 replay contract did
not bind ``mrp_trace_daily.csv``.  This additive sidecar closes only that
evidence gap.  It never imports or starts the simulation engine and never
modifies a replay.  Instead it:

* revalidates each existing baseline/incident replay pair;
* hashes every native file used for the qualification, including both MRP
  traces;
* checks that the supplier incident is the sole exogenous difference and that
  quality and endogenous supplier-risk events are absent;
* qualifies, without extrapolation, the ordered evidence links from supplier
  shipment through receipt/stock, dynamic MRP response, production and lots,
  then simulated service at an aggregated client node.

Missing empirical links remain an honest negative result.  They can never be
promoted to a complete cascade.  ``--require-all-qualified`` additionally
turns any such negative result into a non-zero command exit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as lot_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_post_stage3_focus_338929 as focus_v1,
)


SCHEMA_VERSION = "etudecas.supplier_v8_dynamic_cascade_mrp_sidecar.v1"
PAYLOAD_SCHEMA_VERSION = f"{SCHEMA_VERSION}.payload.v1"
OUTPUT_NAME = "dynamic_cascade_mrp_evidence_v1.json"

SOURCE_KINDS = ("stage3", "focus_338929")
ALLOWED_MECHANISMS = {
    "transport_delay": ("lead_time_extra_days", 120.0),
    "planned_delivery_shortfall": ("reliability", 0.5),
}

MRP_TRACE_NAME = "mrp_trace_daily.csv"
MRP_REQUIRED_ID_FIELDS = ("day", "node_id", "item_id")
MRP_NUMERIC_FIELDS = (
    "bb_qty",
    "bb_demand_signal_qty",
    "bb_demand_signal_raw_qty",
    "target_demand_signal_qty",
    "target_demand_signal_floor_qty",
    "target_stock_qty",
    "stock_proj_qty",
    "recv_prev_today_qty",
    "recv_prev_future_qty",
    "inventory_position_qty",
    "bn_qty",
    "controlled_bn_qty",
    "planned_release_qty",
    "planned_receipt_qty",
)
MRP_RESPONSE_FIELDS = (
    "bb_demand_signal_qty",
    "target_demand_signal_qty",
    "target_stock_qty",
    "stock_proj_qty",
    "recv_prev_today_qty",
    "recv_prev_future_qty",
    "inventory_position_qty",
    "bn_qty",
    "controlled_bn_qty",
    "planned_release_qty",
    "planned_receipt_qty",
)
MRP_NEED_RESPONSE_FIELDS = (
    "target_demand_signal_qty",
    "target_stock_qty",
    "bn_qty",
    "controlled_bn_qty",
    "planned_release_qty",
    "planned_receipt_qty",
)
TRACE_STAGES = (
    "shipment_to_mp_lots",
    "exposed_consumption_wip",
    "exposed_finished_lots",
    "exposed_client_events",
)
EPS = 1e-9


class DynamicCascadeEvidenceError(ValueError):
    """The available replay evidence cannot satisfy the sidecar contract."""


@dataclass(frozen=True)
class ReplaySource:
    source_kind: str
    source_root: Path
    source_bindings: tuple[dict[str, Any], ...]
    source_signature: str
    dossiers: tuple[dict[str, Any], ...]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _signed(payload: Mapping[str, Any], field: str) -> dict[str, Any]:
    return {**payload, field: stable_sha256(payload)}


def _verify_signed(payload: Mapping[str, Any], field: str, label: str) -> None:
    signature = str(payload.get(field) or "")
    unsigned = {key: value for key, value in payload.items() if key != field}
    if signature != stable_sha256(unsigned):
        raise DynamicCascadeEvidenceError(f"Signature invalide : {label}")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DynamicCascadeEvidenceError(f"JSON illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise DynamicCascadeEvidenceError(f"Objet JSON attendu : {path}")
    return payload


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise DynamicCascadeEvidenceError(f"CSV absent : {path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise DynamicCascadeEvidenceError(f"Entête CSV absente : {path}")
            return list(reader.fieldnames), list(reader)
    except OSError as exc:
        raise DynamicCascadeEvidenceError(f"CSV illisible : {path}") from exc


def _number(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DynamicCascadeEvidenceError(f"Valeur numérique invalide : {label}") from exc
    if not math.isfinite(result):
        raise DynamicCascadeEvidenceError(f"Valeur non finie : {label}")
    return result


def _integer(value: Any, *, label: str) -> int:
    number = _number(value, label=label)
    if not number.is_integer():
        raise DynamicCascadeEvidenceError(f"Entier attendu : {label}")
    return int(number)


def _same_number(left: float, right: float) -> bool:
    return math.isclose(left, right, abs_tol=EPS, rel_tol=1e-12)


def _paths_overlap(left: Path, right: Path) -> bool:
    left, right = left.resolve(), right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _file_binding(path: Path, role: str) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        raise DynamicCascadeEvidenceError(f"Preuve absente ({role}) : {path}")
    return {
        "role": role,
        "path": str(path),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _verify_lot_signature(payload: Mapping[str, Any], field: str, label: str) -> None:
    try:
        lot_v4._verify_signed_payload(payload, field, label)  # noqa: SLF001
    except Exception as exc:
        raise DynamicCascadeEvidenceError(str(exc)) from exc


def _load_stage3_source(root: Path) -> ReplaySource:
    root = root.resolve()
    try:
        plan = lot_v4.load_and_validate_plan(root)
    except Exception as exc:
        raise DynamicCascadeEvidenceError(f"Plan Stage3 invalide : {exc}") from exc
    receipt_path = root / "replay_run_receipt.json"
    validation_path = root / "finalized" / "replay_validation.json"
    receipt = _read_json(receipt_path)
    validation = _read_json(validation_path)
    _verify_lot_signature(receipt, "run_receipt_signature", "reçu Stage3")
    _verify_lot_signature(validation, "validation_signature", "validation Stage3")
    dossiers = plan.get("dossiers")
    declared = validation.get("dossiers")
    if not isinstance(dossiers, list) or not isinstance(declared, list):
        raise DynamicCascadeEvidenceError("Dossiers Stage3 absents")
    planned_ids = [str(row.get("dossier_id") or "") for row in dossiers]
    declared_ids = [str(row.get("dossier_id") or "") for row in declared]
    if (
        receipt.get("status") != "complete_validated"
        or validation.get("status") != "complete_validated"
        or receipt.get("plan_signature") != plan.get("plan_signature")
        or validation.get("plan_signature") != plan.get("plan_signature")
        or validation.get("run_receipt_signature")
        != receipt.get("run_receipt_signature")
        or not planned_ids
        or "" in planned_ids
        or len(planned_ids) != len(set(planned_ids))
        or set(planned_ids) != set(declared_ids)
        or len(declared_ids) != len(set(declared_ids))
    ):
        raise DynamicCascadeEvidenceError("Plan, reçu et validation Stage3 non appariés")
    bindings = (
        _file_binding(root / "replay_plan.json", "stage3_replay_plan"),
        _file_binding(receipt_path, "stage3_replay_receipt"),
        _file_binding(validation_path, "stage3_replay_validation"),
    )
    return ReplaySource(
        source_kind="stage3",
        source_root=root,
        source_bindings=bindings,
        source_signature=str(validation["validation_signature"]),
        dossiers=tuple(dict(row) for row in dossiers),
    )


def _load_focus_source(root: Path) -> ReplaySource:
    root = root.resolve()
    try:
        validation = focus_v1.validate(root)
        plan = focus_v1.load_plan(root)
    except Exception as exc:
        raise DynamicCascadeEvidenceError(f"Focus 338929 invalide : {exc}") from exc
    if validation.get("status") != "complete_validated":
        raise DynamicCascadeEvidenceError("Focus 338929 non exécuté ou non finalisé")
    rows = plan.get("dossiers")
    if not isinstance(rows, list) or len(rows) != 2:
        raise DynamicCascadeEvidenceError("Les deux dossiers du focus 338929 sont requis")
    dossiers = []
    for row in rows:
        dossier = row.get("dossier") if isinstance(row, Mapping) else None
        if not isinstance(dossier, Mapping):
            raise DynamicCascadeEvidenceError("Dossier focus 338929 absent")
        dossiers.append(dict(dossier))
    bindings = (
        _file_binding(root / "focus_plan.json", "focus_338929_plan"),
        _file_binding(root / "focus_run_receipt.json", "focus_338929_receipt"),
        _file_binding(root / "focus_validation.json", "focus_338929_validation"),
    )
    return ReplaySource(
        source_kind="focus_338929",
        source_root=root,
        source_bindings=bindings,
        source_signature=str(validation["validation_signature"]),
        dossiers=tuple(dossiers),
    )


def load_replay_source(root: Path, source_kind: str) -> ReplaySource:
    if source_kind == "stage3":
        return _load_stage3_source(root)
    if source_kind == "focus_338929":
        return _load_focus_source(root)
    raise DynamicCascadeEvidenceError(f"Type de source inconnu : {source_kind}")


def _summary_dynamic_pair(run_dir: Path, pair_key: str) -> tuple[bool, dict[str, Any]]:
    summary_path = run_dir / "summaries" / "first_simulation_summary.json"
    summary = _read_json(summary_path)
    policy = summary.get("policy")
    if not isinstance(policy, Mapping):
        raise DynamicCascadeEvidenceError("Politique moteur absente du résumé")
    initialization = policy.get("initialization_policy")
    state_risk = policy.get("supplier_state_dependent_risk")
    if not isinstance(initialization, Mapping) or not isinstance(state_risk, Mapping):
        raise DynamicCascadeEvidenceError("Contrat MRP/risque absent du résumé")
    dynamic_pairs = initialization.get("mrp_dynamic_requirement_pairs")
    if not isinstance(dynamic_pairs, list) or any(
        not isinstance(value, str) for value in dynamic_pairs
    ):
        raise DynamicCascadeEvidenceError("Liste des besoins MRP dynamiques invalide")
    if state_risk.get("enabled") is not False:
        raise DynamicCascadeEvidenceError("Un risque fournisseur endogène est activé")
    supplier_risk = policy.get("supplier_risk") or {}
    if not isinstance(supplier_risk, Mapping):
        raise DynamicCascadeEvidenceError("Contrat d'incident fournisseur invalide")
    return pair_key in set(dynamic_pairs), summary


def _load_mrp_pair(
    run_dir: Path, *, node_id: str, item_id: str, horizon: int
) -> tuple[Path, dict[int, dict[str, float]]]:
    path = run_dir / "data" / MRP_TRACE_NAME
    fields, rows = _read_csv(path)
    required = {*MRP_REQUIRED_ID_FIELDS, *MRP_NUMERIC_FIELDS}
    if not required.issubset(fields):
        missing = sorted(required - set(fields))
        raise DynamicCascadeEvidenceError(f"Colonnes MRP absentes : {missing}")
    selected: dict[int, dict[str, float]] = {}
    for row in rows:
        if str(row.get("node_id") or "") != node_id or str(
            row.get("item_id") or ""
        ) != item_id:
            continue
        day = _integer(row.get("day"), label="jour MRP")
        if day in selected:
            raise DynamicCascadeEvidenceError(
                f"Trace MRP dupliquée : {node_id}|{item_id}|J{day}"
            )
        selected[day] = {
            field: _number(row.get(field), label=f"MRP {field} J{day}")
            for field in MRP_NUMERIC_FIELDS
        }
    expected_days = set(range(horizon))
    if set(selected) != expected_days:
        missing = sorted(expected_days - set(selected))
        extra = sorted(set(selected) - expected_days)
        raise DynamicCascadeEvidenceError(
            f"Couverture MRP incomplète pour {node_id}|{item_id}; "
            f"jours absents={missing[:10]}, hors horizon={extra[:10]}"
        )
    return path, selected


def _field_divergences(
    baseline: Mapping[int, Mapping[str, float]],
    incident: Mapping[int, Mapping[str, float]],
    fields: Sequence[str],
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for field in fields:
        days = [
            day
            for day in sorted(baseline)
            if not _same_number(baseline[day][field], incident[day][field])
        ]
        output[field] = {
            "divergence_observed": bool(days),
            "first_divergence_day": days[0] if days else None,
            "divergent_day_count": len(days),
            "maximum_absolute_delta": max(
                (
                    abs(incident[day][field] - baseline[day][field])
                    for day in days
                ),
                default=0.0,
            ),
        }
    return output


def _first_series_divergence(
    baseline: Mapping[int, float], incident: Mapping[int, float]
) -> int | None:
    if set(baseline) != set(incident):
        raise DynamicCascadeEvidenceError("Horizons quotidiens non appariés")
    for day in sorted(baseline):
        if not _same_number(float(baseline[day]), float(incident[day])):
            return day
    return None


def _minimum_trace_day(rows: Sequence[Mapping[str, Any]]) -> int | None:
    days = []
    for row in rows:
        value = row.get("day")
        if str(value or "").strip():
            days.append(_integer(value, label="jour de généalogie"))
    return min(days) if days else None


def _tagged_shipment_timing(
    incident_dir: Path, event_id: str
) -> tuple[int, int, int]:
    files = lot_v4._required_run_files(incident_dir)  # noqa: SLF001
    _, rows = _read_csv(files["shipments"])
    tagged = [
        row
        for row in rows
        if event_id in lot_v4._event_tokens(row.get("risk_event_ids"))  # noqa: SLF001
        and _number(row.get("shipped_qty", 0), label="quantité expédiée") > EPS
    ]
    if not tagged:
        raise DynamicCascadeEvidenceError("Aucune expédition incidente positive")
    decisions = [
        _integer(row.get("risk_decision_day"), label="jour de décision")
        for row in tagged
    ]
    arrivals = [
        _integer(row.get("arrival_day"), label="jour de réception") for row in tagged
    ]
    return min(decisions), min(arrivals), len(tagged)


def _arm_bindings(run_dir: Path, arm: str) -> list[dict[str, Any]]:
    files = dict(lot_v4._required_run_files(run_dir))  # noqa: SLF001
    files["mrp_trace"] = run_dir / "data" / MRP_TRACE_NAME
    return [
        _file_binding(path, f"{arm}:{name}")
        for name, path in sorted(files.items())
    ]


def _mechanism_contract(dossier: Mapping[str, Any]) -> tuple[str, int, int]:
    priority = dossier.get("priority")
    risk = dossier.get("risk_row")
    if not isinstance(priority, Mapping) or not isinstance(risk, Mapping):
        raise DynamicCascadeEvidenceError("Identité ou incident du dossier absent")
    mechanism = str(priority.get("mechanism") or "")
    if mechanism not in ALLOWED_MECHANISMS:
        raise DynamicCascadeEvidenceError(
            "Seuls le retard de transport et le manque de livraison sont autorisés"
        )
    expected_type, expected_value = ALLOWED_MECHANISMS[mechanism]
    actual_value = _number(risk.get("multiplier"), label="valeur de l'incident")
    start = _integer(risk.get("start_day"), label="début de l'incident")
    end = _integer(risk.get("end_day"), label="fin de l'incident")
    if (
        str(risk.get("risk_type") or "") != expected_type
        or not _same_number(actual_value, expected_value)
        or not str(risk.get("event_id") or "")
        or end < start
    ):
        raise DynamicCascadeEvidenceError("Contrat d'incident fournisseur inattendu")
    return mechanism, start, end


def qualify_dossier(dossier: Mapping[str, Any], *, source_kind: str) -> dict[str, Any]:
    """Rebuild one paired evidence chain without launching a simulation."""

    try:
        pair_proof = lot_v4._validate_pair(dossier)  # noqa: SLF001
    except Exception as exc:
        raise DynamicCascadeEvidenceError(f"Paire de rejeux invalide : {exc}") from exc
    mechanism, risk_start, risk_end = _mechanism_contract(dossier)
    priority = dossier["priority"]
    dossier_id = str(dossier.get("dossier_id") or "")
    node_id = str(priority.get("dst_node_id") or "")
    item_id = str(priority.get("item_id") or "")
    supplier_id = str(priority.get("supplier_id") or "")
    lane_id = str(priority.get("lane_id") or "")
    target_product = str(priority.get("target_product_id") or "")
    horizon = _integer(dossier.get("horizon_days"), label="horizon du rejeu")
    if not all((dossier_id, node_id, item_id, supplier_id, lane_id, target_product)):
        raise DynamicCascadeEvidenceError("Identité physique du dossier incomplète")
    if not (0 <= risk_start <= risk_end < horizon):
        raise DynamicCascadeEvidenceError("Fenêtre d'incident hors horizon")

    baseline_dir = Path(str(dossier["arms"]["baseline"]["run_dir"])).resolve()
    incident_dir = Path(str(dossier["arms"]["incident"]["run_dir"])).resolve()
    if baseline_dir == incident_dir:
        raise DynamicCascadeEvidenceError("Les deux bras utilisent le même dossier")
    pair_key = f"{node_id}|{item_id}"
    baseline_dynamic, baseline_summary = _summary_dynamic_pair(
        baseline_dir, pair_key
    )
    incident_dynamic, incident_summary = _summary_dynamic_pair(incident_dir, pair_key)
    if baseline_dynamic != incident_dynamic:
        raise DynamicCascadeEvidenceError("Configuration MRP différente entre les bras")
    for label, summary in (("référence", baseline_summary), ("incident", incident_summary)):
        if _integer(summary.get("sim_days"), label=f"horizon {label}") != horizon:
            raise DynamicCascadeEvidenceError(f"Horizon du résumé {label} invalide")

    baseline_mrp_path, baseline_mrp = _load_mrp_pair(
        baseline_dir, node_id=node_id, item_id=item_id, horizon=horizon
    )
    incident_mrp_path, incident_mrp = _load_mrp_pair(
        incident_dir, node_id=node_id, item_id=item_id, horizon=horizon
    )
    mrp_divergences = _field_divergences(
        baseline_mrp, incident_mrp, MRP_RESPONSE_FIELDS
    )
    mrp_response_days = sorted(
        {
            int(proof["first_divergence_day"])
            for field, proof in mrp_divergences.items()
            if field in MRP_NEED_RESPONSE_FIELDS
            and proof["first_divergence_day"] is not None
        }
    )
    dynamic_signal_positive = any(
        baseline_mrp[day]["bb_demand_signal_qty"] > EPS
        or incident_mrp[day]["bb_demand_signal_qty"] > EPS
        for day in baseline_mrp
    )

    try:
        baseline_daily = lot_v4._daily_series(  # noqa: SLF001
            baseline_dir, dossier=dossier
        )
        incident_daily = lot_v4._daily_series(incident_dir, dossier=dossier)  # noqa: SLF001
        trace = lot_v4.extract_native_trace(incident_dir, dossier=dossier)
    except Exception as exc:
        raise DynamicCascadeEvidenceError(
            f"Séries ou généalogie natives invalides : {exc}"
        ) from exc
    if set(trace) != set(TRACE_STAGES):
        raise DynamicCascadeEvidenceError("Périmètre de généalogie inattendu")
    demand_day = _first_series_divergence(
        baseline_daily["demand"], incident_daily["demand"]
    )
    if demand_day is not None:
        raise DynamicCascadeEvidenceError(
            "La demande exogène diffère entre les bras appariés"
        )
    stock_day = _first_series_divergence(
        baseline_daily["component_stock"], incident_daily["component_stock"]
    )
    production_day = _first_series_divergence(
        baseline_daily["production_released"], incident_daily["production_released"]
    )
    wip_day = _first_series_divergence(
        baseline_daily["wip"], incident_daily["wip"]
    )
    served_day = _first_series_divergence(
        baseline_daily["served_on_due"], incident_daily["served_on_due"]
    )
    backlog_day = _first_series_divergence(
        baseline_daily["backlog"], incident_daily["backlog"]
    )
    service_candidates = [day for day in (served_day, backlog_day) if day is not None]
    service_day = min(service_candidates) if service_candidates else None

    event_id = str(dossier["risk_row"]["event_id"])
    decision_day, receipt_day, tagged_count = _tagged_shipment_timing(
        incident_dir, event_id
    )
    if not risk_start <= decision_day <= risk_end or receipt_day < decision_day:
        raise DynamicCascadeEvidenceError(
            "Chronologie décision/réception de l'incident incohérente"
        )
    trace_counts = {stage: len(trace[stage]) for stage in TRACE_STAGES}
    trace_days = {
        stage: _minimum_trace_day(trace[stage])
        for stage in (
            "exposed_consumption_wip",
            "exposed_finished_lots",
            "exposed_client_events",
        )
    }
    response_days = [
        day
        for day in (stock_day, production_day, wip_day, service_day, *mrp_response_days)
        if day is not None
    ]
    if any(day < risk_start for day in response_days):
        raise DynamicCascadeEvidenceError(
            "Une réponse apparente précède l'incident dans la paire"
        )

    pair_incident = pair_proof.get("incident") if isinstance(pair_proof, Mapping) else None
    pair_incident = pair_incident if isinstance(pair_incident, Mapping) else {}
    links = {
        "incident_applied_to_positive_supplier_shipment": tagged_count > 0,
        "material_receipt_lot_linked": trace_counts["shipment_to_mp_lots"] > 0,
        "component_stock_response_observed": stock_day is not None,
        "dynamic_mrp_requirement_configured": baseline_dynamic,
        "dynamic_mrp_signal_physically_active": dynamic_signal_positive,
        "mrp_need_or_order_response_observed": bool(mrp_response_days),
        "consumption_or_wip_lot_linked": trace_counts["exposed_consumption_wip"] > 0,
        "production_release_response_observed": production_day is not None,
        "finished_lot_descendant_linked": trace_counts["exposed_finished_lots"] > 0,
        "service_or_backlog_response_observed": service_day is not None,
        "aggregated_client_lot_contact_linked": trace_counts["exposed_client_events"]
        > 0,
    }
    missing = [name for name, present in links.items() if not present]
    qualified = not missing
    arm_bindings = {
        "baseline": _arm_bindings(baseline_dir, "baseline"),
        "incident": _arm_bindings(incident_dir, "incident"),
    }
    return {
        "dossier_id": dossier_id,
        "source_kind": source_kind,
        "identity": {
            "operating_point_id": str(priority.get("operating_point_id") or ""),
            "mechanism": mechanism,
            "supplier_id": supplier_id,
            "item_id": item_id,
            "dst_node_id": node_id,
            "lane_id": lane_id,
            "target_product_id": target_product,
            "seed": _integer(dossier.get("seed"), label="graine du rejeu"),
        },
        "incident": {
            "event_id": event_id,
            "risk_type": ALLOWED_MECHANISMS[mechanism][0],
            "risk_value": ALLOWED_MECHANISMS[mechanism][1],
            "window_start_day": risk_start,
            "window_end_day": risk_end,
            "first_tagged_decision_day": decision_day,
            "first_tagged_receipt_day": receipt_day,
            "tagged_positive_shipment_count": tagged_count,
            "quality_incident_included": False,
            "endogenous_supplier_risk_enabled": False,
        },
        "mrp_evidence": {
            "pair_key": pair_key,
            "trace_row_count_per_arm": horizon,
            "baseline_trace_sha256": sha256_file(baseline_mrp_path),
            "incident_trace_sha256": sha256_file(incident_mrp_path),
            "dynamic_requirement_configured_in_both_arms": baseline_dynamic,
            "dynamic_signal_positive": dynamic_signal_positive,
            "first_need_or_order_response_day": (
                mrp_response_days[0] if mrp_response_days else None
            ),
            "field_divergences": mrp_divergences,
        },
        "paired_responses": {
            "first_component_stock_response_day": stock_day,
            "first_mrp_need_or_order_response_day": (
                mrp_response_days[0] if mrp_response_days else None
            ),
            "first_production_release_response_day": production_day,
            "first_wip_response_day": wip_day,
            "first_service_or_backlog_response_day": service_day,
            "first_served_on_due_response_day": served_day,
            "first_backlog_response_day": backlog_day,
            "exogenous_demand_identical": True,
        },
        "native_lot_trace": {
            "counts": trace_counts,
            "first_consumption_or_wip_day": trace_days["exposed_consumption_wip"],
            "first_finished_lot_day": trace_days["exposed_finished_lots"],
            "first_aggregated_client_contact_day": trace_days[
                "exposed_client_events"
            ],
            "client_is_aggregated": True,
            "client_contact_is_incremental_service_loss": False,
            "lot_ids_are_run_local": True,
            "cross_arm_same_lot_claimed": False,
        },
        "qualification": {
            "links": links,
            "missing_links": missing,
            "all_links_present": qualified,
            "status": (
                "qualified_complete_simulated_paired_dynamic_cascade"
                if qualified
                else "not_qualified_missing_empirical_link"
            ),
            "full_industrial_causality_claimed": False,
            "scope": (
                "single_exogenous_supplier_incident_in_the_simulated_model_with_"
                "paired_common_random_numbers"
            ),
        },
        "pair_proof": {
            "baseline_warmup_core_state_sha256": str(
                (pair_proof.get("baseline") or {}).get("warmup_core_state_sha256")
                if isinstance(pair_proof, Mapping)
                else ""
            ),
            "incident_warmup_core_state_sha256": str(
                pair_incident.get("warmup_core_state_sha256") or ""
            ),
        },
        "arm_file_bindings": arm_bindings,
    }


def build_payload(source_root: Path, source_kind: str) -> dict[str, Any]:
    source = load_replay_source(source_root, source_kind)
    dossiers = [
        qualify_dossier(dossier, source_kind=source.source_kind)
        for dossier in source.dossiers
    ]
    dossier_ids = [str(row["dossier_id"]) for row in dossiers]
    if not dossier_ids or len(dossier_ids) != len(set(dossier_ids)):
        raise DynamicCascadeEvidenceError("Dossiers vides ou dupliqués")
    qualified_count = sum(
        bool(row["qualification"]["all_links_present"]) for row in dossiers
    )
    unsigned = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "status": (
            "complete_all_dossiers_qualified"
            if qualified_count == len(dossiers)
            else "complete_qualification_with_explicit_gaps"
        ),
        "producer": (
            "etudecas.prototypes.scan_2027_risk_control."
            "supplier_v8_dynamic_cascade_mrp_sidecar"
        ),
        "producer_sha256": sha256_file(Path(__file__)),
        "source": {
            "kind": source.source_kind,
            "root": str(source.source_root),
            "signature": source.source_signature,
            "bindings": list(source.source_bindings),
        },
        "counts": {
            "dossier_count": len(dossiers),
            "qualified_complete_simulated_dynamic_cascade_count": qualified_count,
            "not_qualified_count": len(dossiers) - qualified_count,
        },
        "scientific_scope": {
            "simulation_engine_runs_performed": 0,
            "source_replays_modified": False,
            "single_incident_per_pair": True,
            "quality_incident_included": False,
            "endogenous_supplier_risks_enabled": False,
            "multiple_or_correlated_incidents_simulated": False,
            "dynamic_cascade_claim_requires_every_link": True,
            "industrial_causality_or_historical_probability_claimed": False,
            "clients_are_aggregated": True,
            "lots_are_simulated_and_run_local": True,
        },
        "dossiers": dossiers,
    }
    return _signed(unsigned, "qualification_signature")


def _assert_required(payload: Mapping[str, Any], require_all_qualified: bool) -> None:
    if require_all_qualified and payload.get("status") != (
        "complete_all_dossiers_qualified"
    ):
        missing = {
            str(row.get("dossier_id") or ""): list(
                (row.get("qualification") or {}).get("missing_links") or []
            )
            for row in payload.get("dossiers") or []
            if not (row.get("qualification") or {}).get("all_links_present")
        }
        raise DynamicCascadeEvidenceError(
            "Cascade dynamique non qualifiée pour tous les dossiers : "
            + json.dumps(missing, ensure_ascii=False, sort_keys=True)
        )


def validate_sidecar(
    source_root: Path,
    source_kind: str,
    output_dir: Path,
    *,
    require_all_qualified: bool = False,
) -> dict[str, Any]:
    output = output_dir.resolve()
    source = source_root.resolve()
    if _paths_overlap(output, source):
        raise DynamicCascadeEvidenceError(
            "La sortie additive chevauche les rejeux protégés"
        )
    path = output / OUTPUT_NAME
    if not output.is_dir() or {item.name for item in output.iterdir()} != {OUTPUT_NAME}:
        raise DynamicCascadeEvidenceError("Sidecar absent, incomplet ou non exclusif")
    actual = _read_json(path)
    _verify_signed(actual, "qualification_signature", "qualification MRP")
    expected = build_payload(source, source_kind)
    if actual != expected:
        raise DynamicCascadeEvidenceError("Le sidecar ne reproduit plus ses sources")
    _assert_required(actual, require_all_qualified)
    return {
        "valid": True,
        "sidecar": str(path),
        "sidecar_sha256": sha256_file(path),
        "qualification_signature": actual["qualification_signature"],
        "status": actual["status"],
        **dict(actual["counts"]),
        "simulation_engine_runs_performed": 0,
    }


def build_sidecar(
    source_root: Path,
    source_kind: str,
    output_dir: Path,
    *,
    require_all_qualified: bool = False,
) -> dict[str, Any]:
    output = output_dir.resolve()
    source = source_root.resolve()
    if _paths_overlap(output, source):
        raise DynamicCascadeEvidenceError(
            "La sortie additive chevauche les rejeux protégés"
        )
    if output.exists():
        return validate_sidecar(
            source,
            source_kind,
            output,
            require_all_qualified=require_all_qualified,
        )
    payload = build_payload(source, source_kind)
    _assert_required(payload, require_all_qualified)
    raw = (
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = output.parent / f".{output.name}.stage.{uuid.uuid4().hex}"
    try:
        stage.mkdir()
        with (stage / OUTPUT_NAME).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(stage, output)
        except FileExistsError:
            if not output.is_dir() or (output / OUTPUT_NAME).read_bytes() != raw:
                raise DynamicCascadeEvidenceError(
                    "Publication concurrente différente; aucun écrasement autorisé"
                )
    finally:
        if stage.is_dir():
            shutil.rmtree(stage)
    return validate_sidecar(
        source,
        source_kind,
        output,
        require_all_qualified=require_all_qualified,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "build", "validate"):
        item = subparsers.add_parser(command)
        item.add_argument("--source-root", type=Path, required=True)
        item.add_argument("--source-kind", choices=SOURCE_KINDS, required=True)
        if command != "inspect":
            item.add_argument("--output-dir", type=Path, required=True)
        item.add_argument("--require-all-qualified", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "inspect":
            payload = build_payload(args.source_root, args.source_kind)
            _assert_required(payload, args.require_all_qualified)
            result: Mapping[str, Any] = payload
        elif args.command == "build":
            result = build_sidecar(
                args.source_root,
                args.source_kind,
                args.output_dir,
                require_all_qualified=args.require_all_qualified,
            )
        else:
            result = validate_sidecar(
                args.source_root,
                args.source_kind,
                args.output_dir,
                require_all_qualified=args.require_all_qualified,
            )
    except DynamicCascadeEvidenceError as exc:
        print(f"CASCADE MRP V8 REFUSÉE : {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
