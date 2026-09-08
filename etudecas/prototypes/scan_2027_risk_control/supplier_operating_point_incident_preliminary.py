#!/usr/bin/env python3
"""Screen the supplier network under the same two incidents at three states.

This is an additive preliminary campaign.  Each incident is paired with the
same operating point and random seed.  It excludes quality mechanisms and the
endogenous supplier state-risk layer.  The primary stage reranks all 18 active
lanes at degraded operating points; the optional four-lane stage is secondary.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_landscape_campaign as campaign_core,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_calibration_protocol as protocol,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_calibration_runner as calibration_runner,
)


ARTIFACT_ROOT = protocol.ARTIFACT_PARENT
DEFAULT_OPERATING_POINTS = (
    ARTIFACT_ROOT
    / "supplier_service_regime_quick_preliminary_20260904_v1"
    / "preliminary_operating_points.json"
)
DEFAULT_RISK_DESIGN = (
    ARTIFACT_ROOT
    / "supplier_network_risk_screen_plan_20260902_v4"
    / "scenario_design.csv"
)
DEFAULT_OUTPUT = (
    ARTIFACT_ROOT / "supplier_operating_point_incidents_preliminary_20260904_v1"
)
DEFAULT_SCREENING_SEEDS = (340281,)
DEFAULT_CONFIRMATION_SEEDS = (340282, 340283)
DEFAULT_HEALTHY_SCREENING = (
    ARTIFACT_ROOT / "supplier_network_risk_screen_20260902_v2" / "screening_metrics.csv"
)

FOUR_CANDIDATE_LANES = {
    "344135": ("SDC-VD0993480A", "M-1430", "268967"),
    "338929": ("SDC-VD0914360C", "M-1810", "268091"),
    "029313": ("SDC-VD0519670A", "M-1810", "268091"),
    "016332": ("SDC-VD0514881A", "M-1810", "268091"),
}
MECHANISMS = {
    "transport_delay": (120.0, "lead_time_extra_days"),
    "supply_availability": (0.5, "availability"),
}
PRODUCT_FACTORY = {"268091": "M-1810", "268967": "M-1430"}

DETAIL_FIELDS = (
    "operating_point_id",
    "operating_point_label",
    "chain_id",
    "realized_global_on_due",
    "realized_268091_on_due",
    "realized_268967_on_due",
    "degradation_family",
    "degradation_value",
    "supplier_id",
    "item_id",
    "factory_id",
    "product_id",
    "incident_mechanism",
    "incident_value",
    "seed",
    "baseline_global_service",
    "incident_global_service",
    "global_service_loss_pp",
    "baseline_service",
    "incident_service",
    "service_loss_pp",
    "backlog_qty_days_delta",
    "production_delta",
    "risk_applied_row_count",
    "risk_applied_event_count",
    "incident_physically_exercised",
    "engine_generation",
    "engine_sha256",
    "status",
)
SUMMARY_METRICS = (
    "realized_global_on_due",
    "realized_268091_on_due",
    "realized_268967_on_due",
    "baseline_global_service",
    "incident_global_service",
    "global_service_loss_pp",
    "baseline_service",
    "incident_service",
    "service_loss_pp",
    "backlog_qty_days_delta",
    "production_delta",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_csv(
    path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _parse_seeds(specification: str) -> tuple[int, ...]:
    seeds = tuple(dict.fromkeys(int(part.strip()) for part in specification.split(",")))
    if not seeds:
        raise ValueError("At least one seed is required")
    return seeds


def _parse_csv_tokens(specification: str | None) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            token.strip()
            for token in str(specification or "").split(",")
            if token.strip()
        )
    )


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "oui"}


def _load_operating_points(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path.resolve())
    if (
        payload.get("quality_branch_included") is not False
        or payload.get("supplier_state_dependent_risks_enabled") is not False
    ):
        raise ValueError("Operating points must exclude quality and endogenous risk")
    points = [dict(item) for item in payload.get("operating_points") or []]
    if {item.get("operating_point_id") for item in points} != {
        "op_100",
        "op_93",
        "op_80",
    }:
        raise ValueError("Exactly op_100, op_93 and op_80 are required")
    degraded_families = {
        str(item.get("degradation_family"))
        for item in points
        if item.get("operating_point_id") != "op_100"
    }
    if len(degraded_families) != 1 or any("quality" in item for item in degraded_families):
        raise ValueError("The 93 and 80 points must share one non-quality family")
    for point in points:
        for field in ("graph", "supplier_floors"):
            resolved = Path(str(point.get(field) or "")).resolve()
            if not resolved.is_file():
                raise FileNotFoundError(f"Missing operating-point {field}: {resolved}")
            point[field] = str(resolved)
        factory = str(point.get("factory_capacities") or "")
        if factory:
            resolved_factory = Path(factory).resolve()
            if not resolved_factory.is_file():
                raise FileNotFoundError(
                    f"Missing operating-point factory capacities: {resolved_factory}"
                )
            point["factory_capacities"] = str(resolved_factory)
    return sorted(points, key=lambda item: (item["operating_point_id"] != "op_100", -float(item["target_service"])))


def _load_incidents(path: Path, *, lane_scope: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in _read_csv(path.resolve()):
        item_id = str(row.get("item_id") or "").replace("item:", "")
        mechanism = str(row.get("failure_mode") or "")
        if mechanism not in MECHANISMS:
            continue
        if lane_scope == "four_candidates" and item_id not in FOUR_CANDIDATE_LANES:
            continue
        expected_value, risk_type = MECHANISMS[mechanism]
        value = float(row["mechanism_value"])
        if not math.isclose(value, expected_value, rel_tol=0.0, abs_tol=1e-12):
            continue
        supplier_id = str(row.get("supplier_id") or "")
        factory_id = str(row.get("dst_node_id") or "")
        product_id = str(row.get("target_product_id") or "")
        chain_id = str(row.get("chain_id") or "")
        if not all((supplier_id, item_id, factory_id, product_id, chain_id)):
            raise ValueError(f"Incomplete lane identity for item {item_id}")
        if lane_scope == "four_candidates" and (
            supplier_id,
            factory_id,
            product_id,
        ) != FOUR_CANDIDATE_LANES[item_id]:
            raise ValueError(f"Four-candidate lane identity mismatch for item {item_id}")
        selected.append(
            {
                "scenario_id": str(row["scenario_id"]),
                "chain_id": chain_id,
                "supplier_id": supplier_id,
                "item_id": item_id,
                "factory_id": factory_id,
                "product_id": product_id,
                "incident_mechanism": mechanism,
                "incident_value": value,
                "risk_type": risk_type,
                "start_day": int(float(row["stress_start_day"])),
                "end_day": int(float(row["stress_end_day"])),
            }
        )
    keys = {
        (row["chain_id"], row["incident_mechanism"]) for row in selected
    }
    expected_count = (
        len(FOUR_CANDIDATE_LANES) * len(MECHANISMS)
        if lane_scope == "four_candidates"
        else 18 * len(MECHANISMS)
    )
    if len(keys) != expected_count or len(selected) != expected_count:
        raise ValueError(
            f"The risk design does not contain the exact {expected_count}-case matrix"
        )
    return sorted(selected, key=lambda row: (row["item_id"], row["incident_mechanism"]))


def _risk_row(operating_point: Mapping[str, Any], incident: Mapping[str, Any]) -> dict[str, Any]:
    event_id = (
        f"{operating_point['operating_point_id']}__{incident['scenario_id']}"
    )
    return {
        "event_id": event_id,
        "risk_type": incident["risk_type"],
        "supplier_id": incident["supplier_id"],
        "item_id": f"item:{incident['item_id']}",
        "dst_node_id": incident["factory_id"],
        "edge_id": "",
        "start_day": incident["start_day"],
        "end_day": incident["end_day"],
        "multiplier": incident["incident_value"],
        "notes": "Hypothèse conditionnelle fournisseur.",
    }


def _build_command(
    operating_point: Mapping[str, Any],
    *,
    case_dir: Path,
    seed: int,
    risk_csv: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(protocol.DEFAULT_ENGINE.resolve()),
        "--input",
        str(operating_point["graph"]),
        "--output-dir",
        str(case_dir),
        "--scenario-id",
        "scn:BASE",
        "--days",
        str(protocol.MEASURED_DAYS),
        "--seed",
        str(seed),
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
        "--common-random-numbers",
        "--supplier-neutral-floors-csv",
        str(operating_point["supplier_floors"]),
    ]
    if operating_point.get("factory_capacities"):
        command.extend(
            ["--factory-nominal-capacities-csv", str(operating_point["factory_capacities"])]
        )
    command.extend(campaign_core.engine_profile_args(protocol.DEFAULT_PROFILE))
    command.extend(protocol.MANAGED_REFERENCE_PROTOCOL_ARGS)
    if risk_csv is not None:
        command.extend(["--supplier-risk-events-csv", str(risk_csv.resolve())])
    return command


def _event_tokens(value: Any) -> set[str]:
    return {
        part.strip()
        for part in str(value or "").replace(",", "|").split("|")
        if part.strip()
    }


def _physical_exercise_from_evidence(
    incident: Mapping[str, Any], metrics: Mapping[str, Any]
) -> bool:
    """Interpret physical application according to the incident mechanism.

    An availability restriction is physically exercised as soon as the engine
    applies it to an eligible requirement.  Requiring a positive shipment in
    that case would be circular: preventing the shipment can be the physical
    effect of the restriction.  A transport delay, by contrast, only exercises
    its mechanism when a positive shipment is actually delayed.
    """

    if str(incident.get("incident_mechanism") or "") == "supply_availability":
        return bool(
            int(metrics.get("risk_applied_row_count") or 0) > 0
            and int(metrics.get("risk_applied_event_count") or 0) > 0
        )
    return bool(metrics.get("incident_physically_exercised"))


def _extract_run(
    case_dir: Path,
    *,
    seed: int,
    operating_point: Mapping[str, Any],
    incident: Mapping[str, Any] | None,
) -> dict[str, Any]:
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    service_path = case_dir / "data" / "production_demand_service_daily.csv"
    production_path = case_dir / "data" / "production_output_products_daily.csv"
    for path in (summary_path, service_path, production_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing engine evidence: {path}")
    summary = _read_json(summary_path)
    service_rows = protocol.read_csv_rows(service_path)
    calibration_runner._validate_daily_service_rows(service_rows)
    service = protocol.service_from_daily_rows(service_rows)
    production_rows = protocol.read_csv_rows(production_path)
    released_by_product: dict[str, float] = {}
    for product_id, factory_id in PRODUCT_FACTORY.items():
        target_rows = [
            row
            for row in production_rows
            if str(row.get("node_id") or "") == factory_id
            and str(row.get("item_id") or "") == f"item:{product_id}"
            and 0 <= int(float(row.get("day") or -1)) < protocol.MEASURED_DAYS
        ]
        if not target_rows:
            raise ValueError(f"No production rows for {factory_id}/item:{product_id}")
        released_by_product[product_id] = sum(
            max(0.0, protocol.finite_float(row.get("released_qty"), 0.0))
            for row in target_rows
        )
    policy = summary.get("policy") or {}
    supplier_risk = policy.get("supplier_risk") or {}
    state_risk = policy.get("supplier_state_dependent_risk") or {}
    event_count = int(supplier_risk.get("event_count") or 0)
    if bool(state_risk.get("enabled")):
        raise ValueError("Endogenous state-dependent risk was unexpectedly enabled")
    expect_incident = incident is not None
    if expect_incident != (event_count > 0):
        raise ValueError("Acute incident loading does not match the planned arm")
    risk_applied_rows: list[dict[str, str]] = []
    exercised_shipment_rows: list[dict[str, str]] = []
    if incident is not None:
        expected_event_id = str(
            _risk_row(operating_point, incident)["event_id"]
        )
        applied_path = case_dir / "data" / "supplier_risk_events_applied_daily.csv"
        shipment_path = case_dir / "data" / "production_supplier_shipments_daily.csv"
        if not applied_path.is_file() or not shipment_path.is_file():
            raise FileNotFoundError("Missing physical supplier-risk application evidence")
        risk_applied_rows = [
            row
            for row in protocol.read_csv_rows(applied_path)
            if expected_event_id in _event_tokens(row.get("event_ids"))
            and str(row.get("supplier_id") or "") == incident["supplier_id"]
            and str(row.get("item_id") or "") == f"item:{incident['item_id']}"
            and str(row.get("dst_node_id") or "") == incident["factory_id"]
        ]
        exercised_shipment_rows = [
            row
            for row in protocol.read_csv_rows(shipment_path)
            if expected_event_id in _event_tokens(row.get("risk_event_ids"))
            and str(row.get("src_node_id") or "") == incident["supplier_id"]
            and str(row.get("item_id") or "") == f"item:{incident['item_id']}"
            and str(row.get("dst_node_id") or "") == incident["factory_id"]
            and (
                protocol.finite_float(row.get("pulled_qty"), 0.0) > 1e-12
                or protocol.finite_float(row.get("shipped_qty"), 0.0) > 1e-12
            )
        ]
        applied_event_ids = {
            token
            for row in risk_applied_rows
            for token in _event_tokens(row.get("event_ids"))
            if token == expected_event_id
        }
    else:
        applied_event_ids = set()
    return {
        **service,
        **{
            f"released_qty_{product_id}": value
            for product_id, value in released_by_product.items()
        },
        "warmup_core_state_sha256": str(
            (policy.get("warmup_boundary_audit") or {}).get("core_state_sha256") or ""
        ),
        "summary_sha256": protocol.sha256_file(summary_path),
        "seed": seed,
        "risk_applied_row_count": len(risk_applied_rows),
        "risk_applied_event_count": len(applied_event_ids),
        "incident_physically_exercised": (
            bool(risk_applied_rows)
            if incident is not None
            and str(incident.get("incident_mechanism") or "")
            == "supply_availability"
            else bool(risk_applied_rows and exercised_shipment_rows)
            if incident is not None
            else True
        ),
    }


def _run_case(
    output: Path,
    operating_point: Mapping[str, Any],
    *,
    seed: int,
    incident: Mapping[str, Any] | None,
) -> dict[str, Any]:
    scenario_id = "baseline" if incident is None else str(incident["scenario_id"])
    case_key = f"{operating_point['operating_point_id']}__{scenario_id}__seed_{seed}"
    evidence_path = output / "case_evidence" / f"{case_key}.json"
    if evidence_path.is_file():
        evidence = _read_json(evidence_path)
        if evidence.get("case_key") != case_key:
            raise ValueError(f"Evidence key mismatch: {case_key}")
        return evidence
    case_dir = output / "cases" / str(operating_point["operating_point_id"]) / scenario_id / f"seed_{seed}"
    risk_csv: Path | None = None
    if incident is not None:
        risk_csv = output / "inputs" / "risk_events" / f"{operating_point['operating_point_id']}__{scenario_id}.csv"
        campaign_core.write_risk_csv(
            risk_csv, [_risk_row(operating_point, incident)]
        )
    command = _build_command(
        operating_point, case_dir=case_dir, seed=seed, risk_csv=risk_csv
    )
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    service_path = case_dir / "data" / "production_demand_service_daily.csv"
    if not (summary_path.is_file() and service_path.is_file()):
        if case_dir.exists() and any(case_dir.iterdir()):
            raise RuntimeError(f"Partial unregistered case requires review: {case_dir}")
        case_dir.mkdir(parents=True, exist_ok=True)
        log_path = case_dir / "operating_point_incident_engine.log"
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"\n[{_now()}] COMMAND {json.dumps(command)}\n")
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(f"Engine failed for {case_key}; see {log_path}")
    metrics = _extract_run(
        case_dir,
        seed=seed,
        operating_point=operating_point,
        incident=incident,
    )
    evidence = {
        "schema_version": "etudecas.supplier_operating_point_incident_preliminary.v1.case",
        "case_key": case_key,
        "operating_point": dict(operating_point),
        "incident": dict(incident) if incident is not None else None,
        "metrics": metrics,
        "quality_branch_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "status": "preliminary_valid",
        "created_at_utc": _now(),
    }
    _write_json(evidence_path, evidence)
    campaign_core.prune_case_artifacts(case_dir)
    return evidence


def _detail_row(
    baseline: Mapping[str, Any], incident_evidence: Mapping[str, Any]
) -> dict[str, Any]:
    point = incident_evidence["operating_point"]
    incident = incident_evidence["incident"]
    baseline_metrics = baseline["metrics"]
    metrics = incident_evidence["metrics"]
    product = str(incident["product_id"])
    baseline_service = float(baseline_metrics[f"on_due_service_{product}"])
    incident_service = float(metrics[f"on_due_service_{product}"])
    if baseline_metrics["warmup_core_state_sha256"] != metrics["warmup_core_state_sha256"]:
        raise ValueError("Paired baseline and incident do not share the same J0 state")
    physically_exercised = _physical_exercise_from_evidence(incident, metrics)
    return {
        "operating_point_id": point["operating_point_id"],
        "operating_point_label": point["operating_point_label"],
        "chain_id": incident["chain_id"],
        "realized_global_on_due": baseline_metrics["system_on_due_service"],
        "realized_268091_on_due": baseline_metrics["on_due_service_268091"],
        "realized_268967_on_due": baseline_metrics["on_due_service_268967"],
        "degradation_family": point["degradation_family"],
        "degradation_value": point["degradation_value"],
        "supplier_id": incident["supplier_id"],
        "item_id": incident["item_id"],
        "factory_id": incident["factory_id"],
        "product_id": product,
        "incident_mechanism": incident["incident_mechanism"],
        "incident_value": incident["incident_value"],
        "seed": metrics["seed"],
        "baseline_global_service": baseline_metrics["system_on_due_service"],
        "incident_global_service": metrics["system_on_due_service"],
        "global_service_loss_pp": 100.0
        * (
            float(baseline_metrics["system_on_due_service"])
            - float(metrics["system_on_due_service"])
        ),
        "baseline_service": baseline_service,
        "incident_service": incident_service,
        "service_loss_pp": 100.0 * (baseline_service - incident_service),
        "backlog_qty_days_delta": (
            float(metrics[f"backlog_qty_days_{product}"])
            - float(baseline_metrics[f"backlog_qty_days_{product}"])
        ),
        "production_delta": (
            float(metrics[f"released_qty_{product}"])
            - float(baseline_metrics[f"released_qty_{product}"])
        ),
        "risk_applied_row_count": metrics["risk_applied_row_count"],
        "risk_applied_event_count": metrics["risk_applied_event_count"],
        "incident_physically_exercised": physically_exercised,
        "engine_generation": "current_20260904",
        "engine_sha256": protocol.sha256_file(protocol.DEFAULT_ENGINE),
        "status": (
            "PRELIMINARY_VALID_NO_QUALITY_STATE_RISK_OFF"
            if physically_exercised
            else "PRELIMINARY_NON_EXERCEE_EXCLUE_CLASSEMENT"
        ),
    }


def _summary_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    key_fields = (
        "operating_point_id",
        "operating_point_label",
        "chain_id",
        "degradation_family",
        "degradation_value",
        "supplier_id",
        "item_id",
        "factory_id",
        "product_id",
        "incident_mechanism",
        "incident_value",
    )
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        groups.setdefault(key, []).append(row)
    fields = [
        *key_fields,
        "seed_count",
        "seed_ids",
        "physically_exercised_seed_count",
        "all_incidents_physically_exercised",
    ]
    for metric in SUMMARY_METRICS:
        fields.extend(
            [f"{metric}_mean", f"{metric}_median", f"{metric}_min", f"{metric}_max"]
        )
    fields.append("status")
    output: list[dict[str, Any]] = []
    for key, group in sorted(groups.items(), key=lambda item: item[0]):
        row = dict(zip(key_fields, key, strict=True))
        row["seed_count"] = len(group)
        row["seed_ids"] = "|".join(str(item["seed"]) for item in sorted(group, key=lambda item: int(item["seed"])))
        row["physically_exercised_seed_count"] = sum(
            _truthy(item.get("incident_physically_exercised")) for item in group
        )
        row["all_incidents_physically_exercised"] = (
            row["physically_exercised_seed_count"] == len(group)
        )
        for metric in SUMMARY_METRICS:
            values = [float(item[metric]) for item in group]
            row[f"{metric}_mean"] = statistics.fmean(values)
            row[f"{metric}_median"] = statistics.median(values)
            row[f"{metric}_min"] = min(values)
            row[f"{metric}_max"] = max(values)
        row["status"] = "PRELIMINARY_3_SEEDS" if len(group) == 3 else "PRELIMINARY_PARTIAL"
        output.append(row)
    return fields, output


def _global_service(row: Mapping[str, Any]) -> float:
    demand = {
        product: float(row[f"demand_qty_{product}"]) for product in protocol.PRODUCTS
    }
    denominator = sum(demand.values())
    if denominator <= 0.0:
        raise ValueError("Non-positive global demand denominator")
    return sum(
        demand[product] * float(row[f"on_due_volume_proxy_{product}"])
        for product in protocol.PRODUCTS
    ) / denominator


def _healthy_reference_rows(
    path: Path,
    incidents: Sequence[Mapping[str, Any]],
    *,
    seed: int,
) -> list[dict[str, Any]]:
    """Project the completed healthy-network screen into the compact schema."""

    path = path.resolve()
    source = _read_csv(path)
    source_manifest_path = path.parent / "campaign_manifest.json"
    source_manifest = (
        _read_json(source_manifest_path) if source_manifest_path.is_file() else {}
    )
    source_engine_sha = str(source_manifest.get("engine_sha256") or "unknown")
    baselines = [
        row
        for row in source
        if row.get("scenario_id") == "baseline_nominal"
        and int(float(row.get("seed") or -1)) == seed
    ]
    if len(baselines) != 1:
        raise ValueError("Healthy reference baseline is not unique")
    baseline = baselines[0]
    baseline_global = _global_service(baseline)
    by_scenario = {
        str(row.get("scenario_id")): row
        for row in source
        if int(float(row.get("seed") or -1)) == seed
    }
    output: list[dict[str, Any]] = []
    for incident in incidents:
        stress = by_scenario.get(str(incident["scenario_id"]))
        if stress is None or not _truthy(stress.get("valid")):
            raise ValueError(
                f"Missing valid healthy reference stress: {incident['scenario_id']}"
            )
        product = str(incident["product_id"])
        stress_global = _global_service(stress)
        baseline_service = float(baseline[f"on_due_volume_proxy_{product}"])
        incident_service = float(stress[f"on_due_volume_proxy_{product}"])
        physically_exercised = _truthy(
            stress.get("paired_baseline_supplier_incident_flow_exercised")
        )
        output.append(
            {
                "operating_point_id": "op_100",
                "operating_point_label": "Référence nominale simulée proche de 100 %",
                "chain_id": incident["chain_id"],
                "realized_global_on_due": baseline_global,
                "realized_268091_on_due": float(
                    baseline["on_due_volume_proxy_268091"]
                ),
                "realized_268967_on_due": float(
                    baseline["on_due_volume_proxy_268967"]
                ),
                "degradation_family": "baseline",
                "degradation_value": 1.0,
                "supplier_id": incident["supplier_id"],
                "item_id": incident["item_id"],
                "factory_id": incident["factory_id"],
                "product_id": product,
                "incident_mechanism": incident["incident_mechanism"],
                "incident_value": incident["incident_value"],
                "seed": seed,
                "baseline_global_service": baseline_global,
                "incident_global_service": stress_global,
                "global_service_loss_pp": 100.0
                * (baseline_global - stress_global),
                "baseline_service": baseline_service,
                "incident_service": incident_service,
                "service_loss_pp": 100.0
                * (baseline_service - incident_service),
                "backlog_qty_days_delta": float(
                    stress["incremental_target_backlog_qty_days"]
                ),
                "production_delta": float(
                    stress["target_released_qty_delta_vs_paired_baseline"]
                ),
                "risk_applied_row_count": int(
                    float(stress.get("risk_applied_rows") or 0)
                ),
                "risk_applied_event_count": int(
                    float(stress.get("risk_applied_event_ids") or 0)
                ),
                "incident_physically_exercised": physically_exercised,
                "engine_generation": "legacy_healthy_screen_20260902_v2",
                "engine_sha256": source_engine_sha,
                "status": (
                    "PRELIMINARY_REUSED_HEALTHY_SCREEN_SEED_340281"
                    if physically_exercised
                    else "PRELIMINARY_NON_EXERCEE_EXCLUE_CLASSEMENT"
                ),
            }
        )
    return output


def _row_key(row: Mapping[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(row["operating_point_id"]),
        str(row["chain_id"]),
        str(row["incident_mechanism"]),
        int(row["seed"]),
    )


def _priority_outputs(
    rows: Sequence[Mapping[str, Any]], output: Path
) -> dict[str, Any]:
    """Rank lanes only by transparent loss metrics; no composite score."""

    screening = [
        row
        for row in rows
        if row["operating_point_id"] in {"op_93", "op_80"}
        and int(row["seed"]) == protocol.SCREENING_SEED
        and _truthy(row.get("incident_physically_exercised"))
    ]
    rankings: list[dict[str, Any]] = []
    dominant_by_point_chain: dict[tuple[str, str], dict[str, Any]] = {}
    top3_chain_ids: set[str] = set()
    for point_id in ("op_93", "op_80"):
        point_rows = [row for row in screening if row["operating_point_id"] == point_id]
        by_chain: dict[str, list[Mapping[str, Any]]] = {}
        for row in point_rows:
            by_chain.setdefault(str(row["chain_id"]), []).append(row)
        dominant: list[Mapping[str, Any]] = []
        for chain_rows in by_chain.values():
            dominant.append(
                max(
                    chain_rows,
                    key=lambda row: (
                        float(row["global_service_loss_pp"]),
                        float(row["backlog_qty_days_delta"]),
                        -float(row["production_delta"]),
                        str(row["incident_mechanism"]),
                    ),
                )
            )
        ordered = sorted(
            dominant,
            key=lambda row: (
                -float(row["global_service_loss_pp"]),
                -float(row["backlog_qty_days_delta"]),
                float(row["production_delta"]),
                str(row["chain_id"]),
            ),
        )
        positive = [
            item for item in ordered if float(item["global_service_loss_pp"]) > 1e-12
        ]
        top3_candidates = positive if len(positive) >= 3 else ordered
        top3_at_point = {
            str(item["chain_id"]) for item in top3_candidates[:3]
        }
        for rank, item in enumerate(ordered, 1):
            ranking = {
                "operating_point_id": point_id,
                "rank": rank,
                "chain_id": item["chain_id"],
                "supplier_id": item["supplier_id"],
                "item_id": item["item_id"],
                "factory_id": item["factory_id"],
                "product_id": item["product_id"],
                "dominant_incident_mechanism": item["incident_mechanism"],
                "global_service_loss_pp": item["global_service_loss_pp"],
                "product_service_loss_pp": item["service_loss_pp"],
                "backlog_qty_days_delta": item["backlog_qty_days_delta"],
                "production_delta": item["production_delta"],
                "ranking_rule": "global_service_loss_pp_desc_then_backlog_then_production",
                "strictly_positive_global_loss": (
                    float(item["global_service_loss_pp"]) > 1e-12
                ),
            }
            rankings.append(ranking)
            dominant_by_point_chain[(point_id, str(item["chain_id"]))] = ranking
            if str(item["chain_id"]) in top3_at_point:
                top3_chain_ids.add(str(item["chain_id"]))
    ranking_fields = list(rankings[0]) if rankings else []
    _write_csv(output / "network_priority_ranking.csv", rankings, ranking_fields)
    selected_cases: list[dict[str, Any]] = []
    for chain_id in sorted(top3_chain_ids):
        available = [
            row
            for (point_id, candidate_chain), row in dominant_by_point_chain.items()
            if candidate_chain == chain_id and point_id in {"op_93", "op_80"}
        ]
        if not available:
            raise ValueError(f"Top3 union chain has no dominant incident: {chain_id}")
        source = max(
            available,
            key=lambda row: (
                float(row["global_service_loss_pp"]),
                float(row["backlog_qty_days_delta"]),
                -float(row["production_delta"]),
            ),
        )
        for point_id in ("op_93", "op_80"):
            existing = dominant_by_point_chain.get((point_id, chain_id))
            selected = dict(existing or source)
            selected["operating_point_id"] = point_id
            selected["confirmation_cause_fallback"] = existing is None
            selected["fallback_reason"] = (
                "no_physically_exercised_cause_in_screening_at_target_point; "
                "reuse_dominant_cause_from_other_degraded_point"
                if existing is None
                else ""
            )
            selected_cases.append(selected)
    payload = {
        "status": "preliminary_one_seed_selection",
        "selection_meaning": (
            "union_of_chain_ids_in_each_operating_point_top3_then_each_union_chain_"
            "confirmed_at_both_points_with_its_point_specific_dominant_cause"
        ),
        "ranking_primary_metric": "global_service_loss_pp",
        "opaque_composite_score_used": False,
        "zero_loss_top3_excluded_when_three_positive_losses_exist": True,
        "cross_point_missing_cause_fallback": (
            "reuse_that_chain_dominant_cause_from_the_other_degraded_point"
        ),
        "top3_union_chain_ids": sorted(top3_chain_ids),
        "selected_cases": selected_cases,
    }
    _write_json(output / "top3_union_selection.json", payload)
    return payload


def run(
    *,
    operating_points_path: Path,
    risk_design_path: Path,
    healthy_screening_path: Path,
    output: Path,
    seeds: Sequence[int],
    workers: int,
    stage: str,
    audit_scope: str,
    chain_ids: Sequence[str] = (),
    operating_point_ids: Sequence[str] = (),
) -> None:
    all_points = _load_operating_points(operating_points_path)
    lane_scope = "four_candidates" if stage == "four-candidate-secondary" else "network"
    incidents = _load_incidents(risk_design_path, lane_scope=lane_scope)
    if chain_ids:
        available_chain_ids = {str(row["chain_id"]) for row in incidents}
        unknown_chain_ids = sorted(set(chain_ids) - available_chain_ids)
        if unknown_chain_ids:
            raise ValueError("Unknown chain ids: " + ", ".join(unknown_chain_ids))
        selected_chain_ids = set(chain_ids)
        incidents = [
            row
            for row in incidents
            if str(row["chain_id"]) in selected_chain_ids
        ]
    if stage == "four-candidate-secondary":
        point_ids = {"op_100", "op_93", "op_80"}
    elif stage == "healthy-current-audit":
        point_ids = {"op_100"}
    else:
        point_ids = {"op_93", "op_80"}
    if operating_point_ids:
        unknown_point_ids = sorted(set(operating_point_ids) - point_ids)
        if unknown_point_ids:
            raise ValueError(
                "Operating points are outside the selected stage: "
                + ", ".join(unknown_point_ids)
            )
        point_ids = set(operating_point_ids)
    points = [
        point for point in all_points if point["operating_point_id"] in point_ids
    ]
    if len(points) != len(point_ids):
        raise ValueError("Selected operating-point inputs are incomplete")
    if stage == "confirmation" or (
        stage == "healthy-current-audit" and audit_scope == "top3-union"
    ):
        selection_path = output.resolve() / "top3_union_selection.json"
        if not selection_path.is_file():
            raise FileNotFoundError("Run network-screening before confirmation")
        selection = _read_json(selection_path)
        if stage == "healthy-current-audit":
            selected_chain_causes = {
                (
                    str(row["chain_id"]),
                    str(row["dominant_incident_mechanism"]),
                )
                for row in selection.get("selected_cases") or []
            }
            selected_keys = {
                ("op_100", chain_id, mechanism)
                for chain_id, mechanism in selected_chain_causes
            }
        else:
            selected_keys = {
                (
                    str(row["operating_point_id"]),
                    str(row["chain_id"]),
                    str(row["dominant_incident_mechanism"]),
                )
                for row in selection.get("selected_cases") or []
            }
    else:
        selected_keys = set()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    baseline_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    baseline_jobs = [(point, seed) for point in points for seed in seeds]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_run_case, output, point, seed=seed, incident=None): (point, seed)
            for point, seed in baseline_jobs
        }
        for future in as_completed(futures):
            point, seed = futures[future]
            evidence = future.result()
            baseline_by_key[(str(point["operating_point_id"]), seed)] = evidence
            metrics = evidence["metrics"]
            print(
                f"[BASE] {point['operating_point_id']} seed={seed} "
                f"service={float(metrics['system_on_due_service']):.4%}",
                flush=True,
            )
    detail_path = output / (
        "op100_current_engine_audit.csv"
        if stage == "healthy-current-audit"
        else "supplier_operating_point_comparison.csv"
    )
    existing_rows = _read_csv(detail_path) if detail_path.is_file() else []
    ledger = {_row_key(row): dict(row) for row in existing_rows}
    if stage == "network-screening":
        healthy_rows = _healthy_reference_rows(
            healthy_screening_path, incidents, seed=protocol.SCREENING_SEED
        )
        for row in healthy_rows:
            ledger[_row_key(row)] = row
    jobs = [
        (point, incident, seed)
        for point in points
        for incident in incidents
        for seed in seeds
        if stage not in {"confirmation", "healthy-current-audit"}
        or (stage == "healthy-current-audit" and audit_scope == "full-network")
        or (
            str(point["operating_point_id"]),
            str(incident["chain_id"]),
            str(incident["incident_mechanism"]),
        )
        in selected_keys
    ]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_run_case, output, point, seed=seed, incident=incident): (
                point,
                incident,
                seed,
            )
            for point, incident, seed in jobs
        }
        for future in as_completed(futures):
            point, incident, seed = futures[future]
            evidence = future.result()
            baseline = baseline_by_key[(str(point["operating_point_id"]), seed)]
            row = _detail_row(baseline, evidence)
            ledger[_row_key(row)] = row
            rows = sorted(
                ledger.values(),
                key=lambda row: (
                    str(row["operating_point_id"]),
                    str(row["chain_id"]),
                    str(row["incident_mechanism"]),
                    int(row["seed"]),
                ),
            )
            _write_csv(detail_path, rows, DETAIL_FIELDS)
            print(
                f"[INCIDENT] {point['operating_point_id']} {incident['item_id']} "
                f"{incident['incident_mechanism']} seed={seed} "
                f"global_loss={row['global_service_loss_pp']:.3f} pp",
                flush=True,
            )
    rows = sorted(
        ledger.values(),
        key=lambda row: (
            str(row["operating_point_id"]),
            str(row["chain_id"]),
            str(row["incident_mechanism"]),
            int(row["seed"]),
        ),
    )
    summary_fields, summaries = _summary_rows(rows)
    _write_csv(
        output
        / (
            "op100_current_engine_audit_summary.csv"
            if stage == "healthy-current-audit"
            else "supplier_operating_point_comparison_summary.csv"
        ),
        summaries,
        summary_fields,
    )
    if stage == "healthy-current-audit":
        old_rows = _healthy_reference_rows(
            healthy_screening_path,
            incidents,
            seed=protocol.SCREENING_SEED,
        )
        old_by_key = {
            (str(row["chain_id"]), str(row["incident_mechanism"])): row
            for row in old_rows
        }
        compatibility_rows: list[dict[str, Any]] = []
        for current in rows:
            key = (
                str(current["chain_id"]),
                str(current["incident_mechanism"]),
            )
            old = old_by_key.get(key)
            if old is None:
                continue
            baseline_delta_pp = 100.0 * (
                float(current["baseline_global_service"])
                - float(old["baseline_global_service"])
            )
            incident_delta_pp = 100.0 * (
                float(current["incident_global_service"])
                - float(old["incident_global_service"])
            )
            loss_delta_pp = float(current["global_service_loss_pp"]) - float(
                old["global_service_loss_pp"]
            )
            compatibility_rows.append(
                {
                    "chain_id": current["chain_id"],
                    "supplier_id": current["supplier_id"],
                    "item_id": current["item_id"],
                    "factory_id": current["factory_id"],
                    "product_id": current["product_id"],
                    "incident_mechanism": current["incident_mechanism"],
                    "old_baseline_global_service": old["baseline_global_service"],
                    "current_baseline_global_service": current[
                        "baseline_global_service"
                    ],
                    "baseline_difference_pp": baseline_delta_pp,
                    "old_incident_global_service": old["incident_global_service"],
                    "current_incident_global_service": current[
                        "incident_global_service"
                    ],
                    "incident_difference_pp": incident_delta_pp,
                    "old_global_service_loss_pp": old["global_service_loss_pp"],
                    "current_global_service_loss_pp": current[
                        "global_service_loss_pp"
                    ],
                    "loss_difference_pp": loss_delta_pp,
                    "old_physically_exercised": old[
                        "incident_physically_exercised"
                    ],
                    "current_physically_exercised": current[
                        "incident_physically_exercised"
                    ],
                    "metrics_equal_within_1e_9": (
                        abs(baseline_delta_pp) <= 1e-9
                        and abs(incident_delta_pp) <= 1e-9
                        and abs(loss_delta_pp) <= 1e-9
                    ),
                }
            )
        compatibility_path = output / "op100_engine_compatibility.csv"
        compatibility_fields = (
            list(compatibility_rows[0]) if compatibility_rows else []
        )
        _write_csv(compatibility_path, compatibility_rows, compatibility_fields)
        all_equal = bool(compatibility_rows) and all(
            _truthy(row["metrics_equal_within_1e_9"])
            for row in compatibility_rows
        )
        _write_json(
            output / "op100_current_engine_audit_manifest.json",
            {
                "schema_version": (
                    "etudecas.supplier_operating_point_incident_preliminary."
                    "op100_compatibility.v1"
                ),
                "status": "complete",
                "evidence_status": "PRELIMINARY",
                "scope": (
                    "current_engine_op100_baseline_and_all_18_lanes_two_causes"
                    if audit_scope == "full-network"
                    else "current_engine_op100_baseline_and_degraded_top3_union_causes"
                ),
                "audit_scope": audit_scope,
                "case_count": len(rows),
                "all_compared_metrics_equal_within_1e_9": all_equal,
                "interpretation": (
                    "current_and_legacy_rows_metric_compatible"
                    if all_equal
                    else "legacy_healthy_rows_not_interchangeable_with_current_engine"
                ),
                "quality_branch_included": False,
                "supplier_state_dependent_risks_enabled": False,
                "current_engine_sha256": protocol.sha256_file(protocol.DEFAULT_ENGINE),
                "completed_at_utc": _now(),
            },
        )
        return
    selection = _priority_outputs(rows, output)
    _write_json(
        output / "campaign_manifest.json",
        {
            "schema_version": "etudecas.supplier_operating_point_incident_preliminary.v1",
            "status": "complete",
            "stage": stage,
            "evidence_status": "PRELIMINARY",
            "detail_row_count": len(rows),
            "summary_row_count": len(summaries),
            "operating_point_count": len(
                {row["operating_point_id"] for row in rows}
            ),
            "lane_count": len({row["chain_id"] for row in rows}),
            "incident_mechanisms": list(MECHANISMS),
            "seed_ids": list(seeds),
            "quality_branch_included": False,
            "supplier_state_dependent_risks_enabled": False,
            "historical_incident_probability_estimated": False,
            "scope": (
                "18_lane_network_screen_then_targeted_confirmation"
                if lane_scope == "network"
                else "secondary_four_healthy_regime_candidates"
            ),
            "service_fields_are_ratios": True,
            "service_loss_pp_unit": "percentage_points",
            "backlog_qty_days_delta_unit": "UN_day",
            "production_delta_definition": "incident_minus_paired_baseline_target_product_released_qty_UN",
            "pairing": "same_operating_point_same_seed_same_J0_core_state",
            "physically_exercised_row_count": sum(
                _truthy(row.get("incident_physically_exercised")) for row in rows
            ),
            "non_exercised_row_count": sum(
                not _truthy(row.get("incident_physically_exercised")) for row in rows
            ),
            "non_exercised_rows_excluded_from_priority_ranking": True,
            "priority_selection": selection,
            "engine_generation_counts": {
                generation: sum(
                    str(row.get("engine_generation") or "") == generation
                    for row in rows
                )
                for generation in sorted(
                    {str(row.get("engine_generation") or "") for row in rows}
                )
            },
            "mixed_engine_generations": len(
                {str(row.get("engine_sha256") or "") for row in rows}
            )
            > 1,
            "engine_sha256": protocol.sha256_file(protocol.DEFAULT_ENGINE),
            "completed_at_utc": _now(),
        },
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operating-points", type=Path, default=DEFAULT_OPERATING_POINTS)
    parser.add_argument("--risk-design", type=Path, default=DEFAULT_RISK_DESIGN)
    parser.add_argument(
        "--healthy-screening", type=Path, default=DEFAULT_HEALTHY_SCREENING
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--stage",
        choices=(
            "network-screening",
            "confirmation",
            "healthy-current-audit",
            "four-candidate-secondary",
        ),
        default="network-screening",
    )
    parser.add_argument("--seeds", default=None)
    parser.add_argument("--workers", type=int, choices=range(1, 7), default=2)
    parser.add_argument(
        "--audit-scope",
        choices=("full-network", "top3-union"),
        default="full-network",
        help="Scope used only by healthy-current-audit.",
    )
    parser.add_argument(
        "--chain-ids",
        default="",
        help="Optional comma-separated lane identifiers for a disjoint additive shard.",
    )
    parser.add_argument(
        "--operating-point-ids",
        default="",
        help="Optional comma-separated operating-point ids within the selected stage.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    default_seeds = (
        DEFAULT_CONFIRMATION_SEEDS
        if args.stage == "confirmation"
        else DEFAULT_SCREENING_SEEDS
    )
    seed_specification = args.seeds or ",".join(str(seed) for seed in default_seeds)
    run(
        operating_points_path=args.operating_points,
        risk_design_path=args.risk_design,
        healthy_screening_path=args.healthy_screening,
        output=args.output_dir,
        seeds=_parse_seeds(seed_specification),
        workers=args.workers,
        stage=args.stage,
        audit_scope=args.audit_scope,
        chain_ids=_parse_csv_tokens(args.chain_ids),
        operating_point_ids=_parse_csv_tokens(args.operating_point_ids),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
