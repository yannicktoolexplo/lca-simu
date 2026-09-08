#!/usr/bin/env python3
"""Run bounded, auditable action replays after the signed V4 campaign.

This additive module never changes the V4 calibration, campaign, finalizer or
lot-replay artifacts.  It consumes their signed outputs and forms a paired
three-arm comparison for every retained seed: the signed no-incident and
incident rows are reused without rerunning them, while only the
incident-with-action arm executes.  Only controls that the current engine can
execute on the exact supplier/item/destination scope are eligible.

The controls are deliberately open-loop scenario hypotheses.  They are not a
claim of closed-loop regulation, an operational recommendation or observed
supplier performance.  A scheduled action is kept distinct from a physically
executed action through the native engine ledgers.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import statistics
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v4 as campaign_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as lot_replay_v4,
)


SCHEMA_VERSION = "etudecas.supplier_priority_action_replay.v4"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan.v1"
CASE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case.v1"
RUN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.run.v1"
SUMMARY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.summary.v1"
VALIDATION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.validation.v1"
INVENTORY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.source_inventory.v1"
EXPECTED_REPETITIONS = 30
EXPECTED_STATE_WINDOW_DAYS = 720
EXPECTED_IMPACT_WINDOW_DAYS = 360
CLIENT_NODE_ID = lot_replay_v4.V4_CLIENT_NODE_ID
EPS = 1e-9

DEFAULT_STOCK_SCALE = 1.25
DEFAULT_LEAD_REDUCTION_DAYS = 14
DEFAULT_TARGET_PRIORITY_WEIGHT = 0.25
DEFAULT_BOOTSTRAP_REPLICATES = 5_000
DEFAULT_BOOTSTRAP_SEED = 904_221

ACTION_STOCK = "prepositioned_free_stock_j0"
ACTION_LEAD = "future_departures_lead_reduction"
ACTION_REALLOCATION = "active_multisource_reallocation"

ALLOWED_ACTIONS = (ACTION_STOCK, ACTION_LEAD, ACTION_REALLOCATION)
SCHEDULE_ACTIONS = {
    ACTION_LEAD: "lead_time_adjustment_days",
    ACTION_REALLOCATION: "priority_weight",
}

# These flags are owned by this replay.  The signed V4 profile is allowed to
# state the disabled state-risk mode, but may not silently inject another
# incident, controller, initial-state change or reporting mode.
OWNED_ENGINE_FLAGS: dict[str, int] = {
    "--input": 1,
    "--output-dir": 1,
    "--scenario-id": 1,
    "--days": 1,
    "--seed": 1,
    "--output-profile": 1,
    "--skip-map": 0,
    "--skip-plots": 0,
    "--lot-trace": 0,
    "--no-lot-trace": 0,
    "--skip-lot-audit": 0,
    "--common-random-numbers": 0,
    "--no-common-random-numbers": 0,
    "--supplier-risk-events-csv": 1,
    "--supplier-state-dependent-risks": 0,
    "--no-supplier-state-dependent-risks": 0,
    "--control-schedule-csv": 1,
    "--control-probe-schedule-csv": 1,
    "--control-policy-json": 1,
    "--control-policy-v2-json": 1,
    "--control-policy-v3-json": 1,
    "--controller-prime-during-warmup": 0,
    "--no-controller-prime-during-warmup": 0,
    "--measurement-start-stock-scale-csv": 1,
    "--measurement-start-in-transit-scale-csv": 1,
    "--opening-observed-stock-scale": 1,
    "--opening-observed-stock-scale-csv": 1,
    "--supplier-neutral-floors-csv": 1,
    "--factory-nominal-capacities-csv": 1,
}

CONTROL_COLUMNS = (
    "day",
    "policy",
    "node_id",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "order_multiplier",
    "safety_stock_multiplier",
    "production_target_multiplier",
    "capacity_multiplier",
    "external_procurement_multiplier",
    "expedite_level",
    "lead_time_adjustment_days",
    "priority_weight",
)


class ActionReplayError(ValueError):
    """Raised when a signed input or replay result fails closed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _signed(payload: Mapping[str, Any], signature_field: str) -> dict[str, Any]:
    result = dict(payload)
    result[signature_field] = stable_sha256(result)
    return result


def _verify_signed(
    payload: Mapping[str, Any], signature_field: str, label: str
) -> None:
    expected = str(payload.get(signature_field) or "")
    unsigned = {key: value for key, value in payload.items() if key != signature_field}
    if (
        not re.fullmatch(r"[0-9a-f]{64}", expected)
        or stable_sha256(unsigned) != expected
    ):
        raise ActionReplayError(f"Signature invalide: {label}")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ActionReplayError(f"JSON illisible: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ActionReplayError(f"Le JSON doit contenir un objet: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ActionReplayError(f"CSV illisible: {path}: {exc}") from exc


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_csv_atomic(
    path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = list(fields or [])
    for row in rows:
        for field in row:
            if field not in ordered:
                ordered.append(str(field))
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ordered, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _truthy(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "oui"}


def _float(value: Any, *, label: str, default: float | None = None) -> float:
    if value is None or str(value).strip() == "":
        if default is not None:
            return default
        raise ActionReplayError(f"Valeur absente: {label}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ActionReplayError(f"Valeur non numérique: {label}") from exc
    if not math.isfinite(result):
        raise ActionReplayError(f"Valeur non finie: {label}")
    return result


def _optional_float(value: Any, *, label: str) -> float | None:
    """Return a finite measured value, or ``None`` when the field is absent."""

    if value is None or str(value).strip() == "":
        return None
    return _float(value, label=label)


def _int(value: Any, *, label: str) -> int:
    number = _float(value, label=label)
    rounded = int(round(number))
    if not math.isclose(number, rounded, rel_tol=0.0, abs_tol=1e-9):
        raise ActionReplayError(f"Entier attendu: {label}")
    return rounded


def _measurement_windows(
    dossiers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build and validate the exact signed windows used by action KPIs."""

    ranges: list[dict[str, Any]] = []
    identities: set[tuple[str, int]] = set()
    for dossier in dossiers:
        dossier_id = str(dossier.get("dossier_id") or "")
        if not dossier_id:
            raise ActionReplayError("Identité de dossier absente des fenêtres KPI")
        for seed_plan in dossier.get("seed_plans") or []:
            seed = _int(seed_plan.get("seed"), label="graine fenêtre KPI")
            identity = (dossier_id, seed)
            if identity in identities:
                raise ActionReplayError("Fenêtre KPI dossier/graine dupliquée")
            identities.add(identity)
            horizon = _int(seed_plan.get("horizon_days"), label="horizon fenêtre KPI")
            state_days = _int(
                seed_plan.get("state_evaluation_days"),
                label="durée fenêtre d'état KPI",
            )
            start = _int(
                seed_plan.get("impact_window_start_day"),
                label="début fenêtre d'impact KPI",
            )
            end = _int(
                seed_plan.get("impact_window_end_day"),
                label="fin fenêtre d'impact KPI",
            )
            if state_days != EXPECTED_STATE_WINDOW_DAYS or horizon < state_days:
                raise ActionReplayError(
                    "La fenêtre d'état des KPI actions doit être exactement J0–J719"
                )
            if (
                not 0 <= start <= end < horizon
                or end >= EXPECTED_STATE_WINDOW_DAYS
                or end - start + 1 != EXPECTED_IMPACT_WINDOW_DAYS
            ):
                raise ActionReplayError(
                    "La fenêtre d'impact des KPI actions doit compter exactement 360 jours"
                )
            ranges.append(
                {
                    "dossier_id": dossier_id,
                    "seed": seed,
                    "start_day": start,
                    "end_day": end,
                    "day_count": EXPECTED_IMPACT_WINDOW_DAYS,
                }
            )
    ranges.sort(key=lambda row: (str(row["dossier_id"]), int(row["seed"])))
    return {
        "impact_service": {
            "metric_ids": ["service_gain_pp"],
            "day_count": EXPECTED_IMPACT_WINDOW_DAYS,
            "ranges": ranges,
        },
        "state": {
            "metric_ids": [
                "state_window_service_gain_pp",
                "backlog_qty_days_avoided",
                "production_released_gain_qty",
            ],
            "start_day": 0,
            "end_day": EXPECTED_STATE_WINDOW_DAYS - 1,
            "day_count": EXPECTED_STATE_WINDOW_DAYS,
        },
    }


def _sanitize(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_.")
    if not result:
        raise ActionReplayError("Identifiant vide après normalisation")
    return result


def _source_entry(path: Path, role: str) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ActionReplayError(f"Source absente ({role}): {resolved}")
    return {"role": role, "path": str(resolved), "sha256": sha256_file(resolved)}


def _verify_source_inventory(entries: Sequence[Mapping[str, Any]]) -> None:
    seen: set[Path] = set()
    for entry in entries:
        path = Path(str(entry.get("path") or "")).resolve()
        expected = str(entry.get("sha256") or "")
        if path in seen:
            raise ActionReplayError(f"Source répétée dans l'inventaire: {path}")
        seen.add(path)
        if not path.is_file() or sha256_file(path) != expected:
            raise ActionReplayError(f"Source modifiée ou absente: {path}")


def _profile_args(path: Path) -> list[str]:
    payload = _read_json(path)
    args = payload.get("args")
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        raise ActionReplayError(f"Profil moteur invalide: {path}")
    return list(args)


def _clean_v4_args(args: Sequence[str]) -> list[str]:
    """Retain signed physics while removing only replay-owned flags."""

    result: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        arity = OWNED_ENGINE_FLAGS.get(token)
        if arity is None:
            result.append(token)
            index += 1
            continue
        if index + arity >= len(args):
            raise ActionReplayError(f"Argument moteur incomplet: {token}")
        if token != "--no-supplier-state-dependent-risks":
            raise ActionReplayError(
                f"Le profil V4 tente de piloter un argument réservé au replay: {token}"
            )
        index += arity + 1
    return result


def _flag_values(command: Sequence[str], flag: str) -> list[str | None]:
    arity = OWNED_ENGINE_FLAGS[flag]
    values: list[str | None] = []
    for index, token in enumerate(command):
        if token != flag:
            continue
        if arity == 0:
            values.append(None)
        elif index + 1 < len(command):
            values.append(command[index + 1])
        else:
            raise ActionReplayError(f"Argument sans valeur: {flag}")
    return values


def _validate_command(command: Sequence[str], arm: str) -> None:
    required = (
        "--input",
        "--output-dir",
        "--scenario-id",
        "--days",
        "--seed",
        "--output-profile",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
        "--common-random-numbers",
        "--no-supplier-state-dependent-risks",
    )
    for flag in required:
        if len(_flag_values(command, flag)) != 1:
            raise ActionReplayError(f"Commande {arm}: exactement un {flag} requis")
    if _flag_values(command, "--output-profile") != ["compact"]:
        raise ActionReplayError("Le replay d'actions doit rester compact")
    if _flag_values(command, "--scenario-id") != ["scn:BASE"]:
        raise ActionReplayError("Le scénario moteur doit rester scn:BASE")
    risk_count = len(_flag_values(command, "--supplier-risk-events-csv"))
    schedule_count = len(_flag_values(command, "--control-schedule-csv"))
    stock_count = len(_flag_values(command, "--measurement-start-stock-scale-csv"))
    if arm == "baseline":
        expected = (0, 0, 0)
    elif arm == "incident_no_action":
        expected = (1, 0, 0)
    elif arm.startswith("action:"):
        expected = (1, 1, 0) if arm.split(":", 1)[1] in SCHEDULE_ACTIONS else (1, 0, 1)
    else:
        raise ActionReplayError(f"Bras inconnu: {arm}")
    if (risk_count, schedule_count, stock_count) != expected:
        raise ActionReplayError(
            f"Commande {arm}: combinaison incident/action inattendue "
            f"{(risk_count, schedule_count, stock_count)}"
        )
    forbidden = (
        "--control-probe-schedule-csv",
        "--control-policy-json",
        "--control-policy-v2-json",
        "--control-policy-v3-json",
        "--supplier-state-dependent-risks",
        "--lot-trace",
        "--measurement-start-in-transit-scale-csv",
        "--opening-observed-stock-scale",
        "--opening-observed-stock-scale-csv",
    )
    if any(_flag_values(command, flag) for flag in forbidden):
        raise ActionReplayError(f"Commande {arm}: modificateur hors action détecté")


def _build_command(
    *,
    python_executable: str,
    engine: Path,
    graph: Path,
    output_dir: Path,
    days: int,
    seed: int,
    profile_args: Sequence[str],
    managed_args: Sequence[str],
    supplier_floors: Path | None,
    factory_capacities: Path | None,
    risk_csv: Path | None,
    action_id: str | None,
    action_input: Path | None,
) -> list[str]:
    physics_args = _clean_v4_args([*profile_args, *managed_args])
    command = [
        python_executable,
        str(engine.resolve()),
        "--input",
        str(graph.resolve()),
        "--output-dir",
        str(output_dir.resolve()),
        "--scenario-id",
        "scn:BASE",
    ]
    if supplier_floors is not None:
        command.extend(
            ["--supplier-neutral-floors-csv", str(supplier_floors.resolve())]
        )
    if factory_capacities is not None:
        command.extend(
            ["--factory-nominal-capacities-csv", str(factory_capacities.resolve())]
        )
    command.extend(physics_args)
    command.extend(
        [
            "--days",
            str(days),
            "--seed",
            str(seed),
            "--output-profile",
            "compact",
            "--skip-map",
            "--skip-plots",
            "--no-lot-trace",
            "--skip-lot-audit",
            "--common-random-numbers",
        ]
    )
    if risk_csv is not None:
        command.extend(["--supplier-risk-events-csv", str(risk_csv.resolve())])
    if action_id is not None:
        if action_input is None:
            raise ActionReplayError("Entrée d'action absente")
        if action_id in SCHEDULE_ACTIONS:
            command.extend(["--control-schedule-csv", str(action_input.resolve())])
        elif action_id == ACTION_STOCK:
            command.extend(
                ["--measurement-start-stock-scale-csv", str(action_input.resolve())]
            )
        else:
            raise ActionReplayError(f"Action inconnue: {action_id}")
    command.append("--no-supplier-state-dependent-risks")
    arm = (
        "baseline"
        if risk_csv is None
        else "incident_no_action"
        if action_id is None
        else f"action:{action_id}"
    )
    _validate_command(command, arm)
    return command


def _inventory_state(
    graph: Mapping[str, Any], node_id: str, item_id: str
) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for node in graph.get("nodes") or []:
        if str(node.get("id") or "") != node_id:
            continue
        for state in (node.get("inventory") or {}).get("states") or []:
            if str(state.get("item_id") or "") == item_id:
                matches.append(dict(state))
    if len(matches) > 1:
        raise ActionReplayError(f"État de stock dupliqué: {node_id}/{item_id}")
    return matches[0] if matches else None


def _metric_records(paths: Sequence[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for path in paths:
        for source in _read_csv(path):
            key = (
                str(source.get("case_key") or ""),
                str(source.get("case_signature") or ""),
            )
            if not all(key) or key in identities:
                raise ActionReplayError(
                    "Identité de cas vide ou répétée dans les métriques V4"
                )
            identities.add(key)
            records.append({"row": dict(source), "metrics_path": path.resolve()})
    return records


def _valid_row(row: Mapping[str, Any]) -> bool:
    return _truthy(row.get("valid")) and str(row.get("status") or "") in {
        "valid",
        "valid_no_exposure",
    }


def _cell_incidents(
    records: Sequence[Mapping[str, Any]], priority: Mapping[str, Any]
) -> list[dict[str, Any]]:
    result = [
        dict(record)
        for record in records
        if str(record["row"].get("stage") or "") == "incident"
        and str(record["row"].get("operating_point_id") or "")
        == str(priority.get("operating_point_id") or "")
        and str(record["row"].get("mechanism") or "")
        == str(priority.get("mechanism") or "")
        and str(record["row"].get("lane_id") or "")
        == str(priority.get("lane_id") or "")
        and _valid_row(record["row"])
        and str(record["row"].get("status") or "") == "valid"
        and _truthy(record["row"].get("incident_physically_exercised"))
    ]
    result.sort(key=lambda record: _int(record["row"].get("seed"), label="graine"))
    seeds = [_int(record["row"].get("seed"), label="graine") for record in result]
    if not result or len(seeds) != len(set(seeds)) or len(seeds) > EXPECTED_REPETITIONS:
        raise ActionReplayError("Cohorte V4 vide, dupliquée ou supérieure à 30 graines")
    return result


def _baseline_record(
    records: Sequence[Mapping[str, Any]], incident: Mapping[str, Any]
) -> dict[str, Any]:
    row = incident["row"]
    matches = [
        dict(record)
        for record in records
        if str(record["row"].get("stage") or "") == "baseline"
        and str(record["row"].get("operating_point_id") or "")
        == str(row.get("operating_point_id") or "")
        and _int(record["row"].get("seed"), label="graine baseline")
        == _int(row.get("seed"), label="graine incident")
        and _valid_row(record["row"])
    ]
    if len(matches) != 1:
        raise ActionReplayError("Baseline appariée V4 absente ou dupliquée")
    baseline = matches[0]
    if str(row.get("baseline_case_signature") or "") != str(
        baseline["row"].get("case_signature") or ""
    ):
        raise ActionReplayError("La signature de baseline appariée diffère")
    return baseline


def _case_sources(
    *,
    campaign_root: Path,
    manifest: Mapping[str, Any],
    record: Mapping[str, Any],
    priority: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], Path, Path | None, bytes | None]:
    row = record["row"]
    metrics_path = Path(record["metrics_path"])
    evidence_path = metrics_path.parent / "case_evidence" / f"{row['case_key']}.json"
    evidence = lot_replay_v4._validate_case_evidence(
        evidence_path, manifest=manifest, metric_row=row
    )
    if priority is None:
        return evidence, evidence_path, None, None
    risk_row = lot_replay_v4._risk_row_contract(
        evidence.get("risk_row") or {}, priority=priority, incident=row
    )
    risk_path = (
        metrics_path.parent / "inputs" / "risk_events" / f"{row['case_key']}.csv"
    )
    if risk_path.is_file():
        risk_bytes = risk_path.read_bytes()
    else:
        risk_bytes = lot_replay_v4._risk_csv_bytes(risk_row)
    declared = str(evidence.get("risk_csv_sha256") or "")
    if hashlib.sha256(risk_bytes).hexdigest() != declared:
        raise ActionReplayError("Le CSV d'incident diffère de sa preuve V4 signée")
    if risk_path.is_file() and not risk_path.resolve().is_relative_to(
        campaign_root.resolve()
    ):
        raise ActionReplayError("Le CSV d'incident sort du dossier de campagne")
    return (
        evidence,
        evidence_path,
        risk_path if risk_path.is_file() else None,
        risk_bytes,
    )


def _active_alternatives(
    *,
    records: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    priority: Mapping[str, Any],
    seeds: Sequence[int],
) -> list[dict[str, Any]]:
    point = str(priority["operating_point_id"])
    target_lane = str(priority["lane_id"])
    item = str(priority["item_id"])
    destination = str(priority["dst_node_id"])
    candidates = [
        dict(lane)
        for lane in manifest.get("lanes") or []
        if str(lane.get("lane_id") or "") != target_lane
        and str(lane.get("supplier_id") or "") != str(priority.get("supplier_id") or "")
        and str(lane.get("item_id") or "") == item
        and str(lane.get("dst_node_id") or "") == destination
    ]
    output: list[dict[str, Any]] = []
    for lane in candidates:
        lane_id = str(lane.get("lane_id") or "")
        volumes: list[float] = []
        for seed in seeds:
            matches = [
                record["row"]
                for record in records
                if str(record["row"].get("stage") or "") == "incident"
                and str(record["row"].get("operating_point_id") or "") == point
                and str(record["row"].get("lane_id") or "") == lane_id
                and _int(record["row"].get("seed"), label="graine alternative") == seed
                and _valid_row(record["row"])
            ]
            if not matches:
                volumes = []
                break
            volumes.append(
                max(
                    _float(
                        row.get("baseline_lane_shipped_qty_state_window"),
                        label="flux baseline de la voie alternative",
                        default=0.0,
                    )
                    for row in matches
                )
            )
        if len(volumes) == len(seeds) and all(value > EPS for value in volumes):
            output.append(
                {
                    **lane,
                    "positive_seed_count": len(volumes),
                    "median_baseline_shipped_qty_state_window": statistics.median(
                        volumes
                    ),
                    "minimum_baseline_shipped_qty_state_window": min(volumes),
                    "operational_qualification_proven": False,
                    "interpretation": (
                        "voie déjà présente et alimentée dans la simulation V4; "
                        "qualification contractuelle réelle encore à confirmer"
                    ),
                }
            )
    output.sort(
        key=lambda row: (
            -float(row["median_baseline_shipped_qty_state_window"]),
            str(row.get("supplier_id") or ""),
            str(row.get("lane_id") or ""),
        )
    )
    return output


def _action_catalog(
    *,
    priority: Mapping[str, Any],
    graph: Mapping[str, Any],
    active_alternatives: Sequence[Mapping[str, Any]],
    reallocation_scope_unique: bool,
    stock_scale: float,
    lead_reduction_days: int,
    target_priority_weight: float,
) -> list[dict[str, Any]]:
    inventory = _inventory_state(
        graph, str(priority["dst_node_id"]), str(priority["item_id"])
    )
    initial_qty = _float(
        (inventory or {}).get("initial"), label="stock initial", default=0.0
    )
    stock_eligible = inventory is not None and initial_qty > EPS
    mechanism = str(priority["mechanism"])
    lead_eligible = mechanism == "transport_delay"
    reallocation_eligible = reallocation_scope_unique and bool(active_alternatives)
    return [
        {
            "action_id": ACTION_STOCK,
            "label_fr": "Stock libre prépositionné avant J0",
            "eligible": stock_eligible,
            "refusal_reason": (
                ""
                if stock_eligible
                else "état de stock cible absent ou nul dans le graphe signé"
            ),
            "timing": "préventif_avant_incident",
            "closed_loop": False,
            "actuator": "measurement_start_stock_scale_csv",
            "parameters": {"measurement_start_stock_scale": stock_scale},
            "parameter_units": {"measurement_start_stock_scale": "ratio_sans_unité"},
            "physical_scope": {
                "node_id": str(priority["dst_node_id"]),
                "item_id": str(priority["item_id"]),
                "graph_opening_stock_qty": initial_qty,
                "uom": str((inventory or {}).get("uom") or ""),
            },
            "limits_fr": (
                "Le moteur ajoute à J0 du stock libre déjà qualifié. Son achat, sa "
                "qualification, sa date de constitution et son prix ne sont pas simulés."
            ),
        },
        {
            "action_id": ACTION_LEAD,
            "label_fr": "Réduction contractuelle du délai des futurs départs",
            "eligible": lead_eligible,
            "refusal_reason": (
                ""
                if lead_eligible
                else "levier de délai non aligné avec une perte de quantité livrable"
            ),
            "timing": "plan_scenario_ouvert_sur_fenêtre_incident",
            "closed_loop": False,
            "actuator": "lead_time_adjustment_days",
            "parameters": {"lead_time_adjustment_days": -lead_reduction_days},
            "parameter_units": {"lead_time_adjustment_days": "jour"},
            "physical_scope": {
                "supplier_id": str(priority["supplier_id"]),
                "item_id": str(priority["item_id"]),
                "dst_node_id": str(priority["dst_node_id"]),
            },
            "limits_fr": (
                "Le réglage s'applique à tous les futurs départs de la voie pendant "
                "la fenêtre, jamais à une expédition identifiée. Le surcoût ou "
                "l'engagement transporteur correspondant n'est pas modélisé."
            ),
        },
        {
            "action_id": ACTION_REALLOCATION,
            "label_fr": "Réallocation vers une voie alternative déjà active",
            "eligible": reallocation_eligible,
            "refusal_reason": (
                ""
                if reallocation_eligible
                else (
                    "l'actionneur fournisseur–article–destination ne distingue pas "
                    "sans ambiguïté la voie incidente"
                    if not reallocation_scope_unique
                    else "aucune seconde voie fournisseur simulée avec flux positif "
                    "pour les mêmes article et destination sur toute la cohorte"
                )
            ),
            "timing": "plan_scenario_ouvert_sur_fenêtre_incident",
            "closed_loop": False,
            "actuator": "priority_weight",
            "parameters": {"target_lane_priority_weight": target_priority_weight},
            "parameter_units": {
                "target_lane_priority_weight": "poids_relatif_sans_unité"
            },
            "physical_scope": {
                "target_supplier_id": str(priority["supplier_id"]),
                "item_id": str(priority["item_id"]),
                "dst_node_id": str(priority["dst_node_id"]),
                "active_alternatives": [dict(row) for row in active_alternatives],
            },
            "limits_fr": (
                "La seconde voie existe et porte du flux dans les références simulées. "
                "Sa qualification, son contrat et sa capacité disponible réels restent à confirmer."
            ),
        },
        {
            "action_id": "identified_shipment_expedite",
            "label_fr": "Accélération d'une expédition nommée",
            "eligible": False,
            "refusal_reason": "le moteur ne sait pas cibler un shipment_id dans le planning de contrôle",
            "timing": "refusé",
            "closed_loop": False,
            "actuator": "absent",
            "parameters": {},
            "parameter_units": {},
            "physical_scope": {},
            "limits_fr": "Action non simulée.",
        },
        {
            "action_id": "new_supplier_or_capacity_creation",
            "label_fr": "Création d'un fournisseur ou d'une capacité supposée",
            "eligible": False,
            "refusal_reason": "aucune source, qualification, capacité ni coût signés ne permettent cette action",
            "timing": "refusé",
            "closed_loop": False,
            "actuator": "interdit",
            "parameters": {},
            "parameter_units": {},
            "physical_scope": {},
            "limits_fr": "Action non simulée et aucune disponibilité inventée.",
        },
        {
            "action_id": "targeted_closed_loop_regulation",
            "label_fr": "Régulation ciblée fournisseur–article–destination",
            "eligible": False,
            "refusal_reason": "l'observation du régulateur actuel est agrégée et ne porte pas cette clé de voie",
            "timing": "refusé",
            "closed_loop": False,
            "actuator": "non_raccordé_à_un_capteur_ciblé",
            "parameters": {},
            "parameter_units": {},
            "physical_scope": {},
            "limits_fr": "Aucune performance en boucle fermée n'est revendiquée.",
        },
    ]


def _action_input_rows(
    action: Mapping[str, Any],
    *,
    priority: Mapping[str, Any],
    start_day: int,
    end_day: int,
) -> tuple[list[dict[str, Any]], Sequence[str]]:
    action_id = str(action["action_id"])
    if action_id == ACTION_STOCK:
        return (
            [
                {
                    "node_id": priority["dst_node_id"],
                    "item_id": priority["item_id"],
                    "scale": action["parameters"]["measurement_start_stock_scale"],
                }
            ],
            ("node_id", "item_id", "scale"),
        )
    rows: list[dict[str, Any]] = []
    for day in range(start_day, end_day + 1):
        row = {field: "" for field in CONTROL_COLUMNS}
        row.update(
            {
                "day": day,
                "policy": f"v4_{action_id}_open_loop_hypothesis",
                "supplier_id": priority["supplier_id"],
                "item_id": priority["item_id"],
                "dst_node_id": priority["dst_node_id"],
            }
        )
        if action_id == ACTION_LEAD:
            row["lead_time_adjustment_days"] = action["parameters"][
                "lead_time_adjustment_days"
            ]
        elif action_id == ACTION_REALLOCATION:
            row["priority_weight"] = action["parameters"]["target_lane_priority_weight"]
        else:
            raise ActionReplayError(f"Action non gérée: {action_id}")
        rows.append(row)
    return rows, CONTROL_COLUMNS


def _state_files(
    *, campaign_root: Path, manifest: Mapping[str, Any], point_id: str
) -> tuple[dict[str, Any], Path, Path | None, Path | None]:
    states = [
        dict(state)
        for state in manifest.get("states") or []
        if str(state.get("operating_point_id") or "") == point_id
    ]
    if len(states) != 1:
        raise ActionReplayError(f"État V4 absent ou dupliqué: {point_id}")
    state = states[0]

    def resolve(
        raw: Any, expected_hash: Any, label: str, optional: bool = False
    ) -> Path | None:
        text = str(raw or "").strip()
        if optional and not text:
            return None
        path = lot_replay_v4._resolve_declared_path(text, (campaign_root,), label)
        lot_replay_v4._verify_file(path, expected_hash, label)
        return path

    graph = resolve(state.get("graph"), state.get("graph_sha256"), "graphe V4")
    assert graph is not None
    floors = resolve(
        state.get("supplier_floors"),
        state.get("supplier_floors_sha256"),
        "planchers fournisseurs V4",
        optional=True,
    )
    capacities = resolve(
        state.get("factory_capacities"),
        state.get("factory_capacities_sha256"),
        "capacités usine V4",
        optional=True,
    )
    return state, graph, floors, capacities


def create_action_plan(
    *,
    campaign_root: Path,
    results_dir: Path,
    output_root: Path,
    max_dossiers: int = 3,
    stock_scale: float = DEFAULT_STOCK_SCALE,
    lead_reduction_days: int = DEFAULT_LEAD_REDUCTION_DAYS,
    target_priority_weight: float = DEFAULT_TARGET_PRIORITY_WEIGHT,
    python_executable: str | None = None,
    lot_replay_root: Path | None = None,
    reference_mode: str = "signed_reference",
) -> dict[str, Any]:
    """Create or validate an immutable action plan without running the engine."""

    if not 1 <= max_dossiers <= 3:
        raise ActionReplayError("max_dossiers doit être compris entre 1 et 3")
    if not 1.0 < stock_scale <= 3.0:
        raise ActionReplayError("stock_scale doit être strictement >1 et <=3")
    if not 1 <= lead_reduction_days <= 30:
        raise ActionReplayError("lead_reduction_days doit être compris entre 1 et 30")
    if not 0.0 < target_priority_weight < 1.0:
        raise ActionReplayError(
            "target_priority_weight doit être strictement entre 0 et 1"
        )
    if reference_mode != "signed_reference":
        raise ActionReplayError(
            "Seul signed_reference est autorisé: aucun rerun baseline/incident redondant"
        )
    campaign_root = campaign_root.resolve()
    results_dir = results_dir.resolve()
    output_root = output_root.resolve()
    plan_path = output_root / "action_replay_plan.json"
    if plan_path.is_file():
        plan = load_and_validate_plan(output_root)
        requested = plan.get("requested_parameters") or {}
        expected = {
            "max_dossiers": max_dossiers,
            "stock_scale": stock_scale,
            "lead_reduction_days": lead_reduction_days,
            "target_priority_weight": target_priority_weight,
            "reference_mode": reference_mode,
        }
        if requested != expected:
            raise ActionReplayError("Le plan existant utilise d'autres paramètres")
        if (
            Path(str(plan.get("campaign_root") or "")).resolve() != campaign_root
            or Path(str(plan.get("results_dir") or "")).resolve() != results_dir
        ):
            raise ActionReplayError("Le plan existant appartient à d'autres entrées")
        binding = plan.get("lot_replay_binding") or {}
        expected_lot_root = lot_replay_root.resolve() if lot_replay_root else None
        actual_lot_root = (
            Path(str(binding.get("root") or "")).resolve()
            if binding.get("provided") is True
            else None
        )
        if actual_lot_root != expected_lot_root:
            raise ActionReplayError("Le replay lots demandé diffère du plan existant")
        return plan
    if output_root.exists() and any(output_root.iterdir()):
        raise ActionReplayError(
            f"Dossier de sortie non vide et non enregistré: {output_root}"
        )

    manifest_path = campaign_root / "campaign_manifest.json"
    manifest = lot_replay_v4._verify_campaign_manifest(manifest_path)
    validation, priority_path, metric_paths = lot_replay_v4._validate_campaign_results(
        campaign_root=campaign_root,
        results_dir=results_dir,
        manifest_path=manifest_path,
        manifest=manifest,
    )
    selection_bundle = lot_replay_v4._load_finalizer_selection(
        results_dir=results_dir, validation=validation, manifest=manifest
    )
    if selection_bundle is None:
        raise ActionReplayError(
            "La sélection signée de trois dossiers du finalizer V4 est obligatoire"
        )
    selection, selection_path = selection_bundle
    priority_rows = _read_csv(priority_path)
    priorities = lot_replay_v4._select_priority_rows(
        priority_rows,
        max_dossiers=max_dossiers,
        selection_rows=selection["selected_dossiers"],
    )
    records = _metric_records(metric_paths)

    engine = lot_replay_v4._resolve_declared_path(
        manifest.get("engine"), (campaign_root,), "moteur V4"
    )
    profile = lot_replay_v4._resolve_declared_path(
        manifest.get("engine_profile"), (campaign_root,), "profil moteur V4"
    )
    lot_replay_v4._verify_file(engine, manifest.get("engine_sha256"), "moteur V4")
    lot_replay_v4._verify_file(
        profile, manifest.get("engine_profile_sha256"), "profil moteur V4"
    )
    profile_args = _profile_args(profile)
    managed_args = manifest.get("managed_engine_args")
    if not isinstance(managed_args, list) or not all(
        isinstance(item, str) for item in managed_args
    ):
        raise ActionReplayError("managed_engine_args V4 invalide")
    # Validate before staging any file.
    _clean_v4_args([*profile_args, *managed_args])

    source_paths: dict[Path, str] = {
        manifest_path: "campaign_manifest",
        results_dir / "campaign_validation.json": "campaign_validation",
        priority_path: "priority_lanes",
        selection_path: "signed_finalizer_selection",
        engine: "engine",
        profile: "engine_profile",
        Path(__file__).resolve(): "action_replay_runner",
        Path(lot_replay_v4.__file__).resolve(): "lot_replay_contract_consumer",
        Path(campaign_v4.__file__).resolve(): "campaign_runner_contract",
    }
    for path in metric_paths:
        source_paths[path] = "campaign_metrics"

    lot_binding: dict[str, Any] = {
        "provided": False,
        "status": "not_provided",
        "plan_signature": "",
        "validation_signature": "",
        "dossier_ids": [],
        "root": "",
    }
    lot_dossiers_by_id: dict[str, dict[str, Any]] = {}
    if lot_replay_root is not None:
        lot_root = lot_replay_root.resolve()
        lot_plan_path = lot_root / "replay_plan.json"
        lot_validation_path = lot_root / "finalized" / "replay_validation.json"
        lot_plan = lot_replay_v4.load_and_validate_plan(lot_root)
        if lot_plan.get("campaign_signature") != manifest["campaign_signature"]:
            raise ActionReplayError("Le replay lots appartient à une autre campagne")
        lot_dossiers_by_id = {
            str(dossier.get("dossier_id") or ""): dict(dossier)
            for dossier in lot_plan.get("dossiers") or []
        }
        if "" in lot_dossiers_by_id or len(lot_dossiers_by_id) != len(
            lot_plan.get("dossiers") or []
        ):
            raise ActionReplayError("Identités de dossiers du replay lots invalides")
        source_paths[lot_plan_path] = "priority_lot_replay_plan"
        if not lot_validation_path.is_file():
            raise ActionReplayError(
                "Le replay lots fourni doit être finalisé et validé avant les actions"
            )
        lot_validation = _read_json(lot_validation_path)
        _verify_signed(lot_validation, "validation_signature", "validation replay lots")
        if (
            lot_validation.get("plan_signature") != lot_plan["plan_signature"]
            or lot_validation.get("status") != "complete_validated"
        ):
            raise ActionReplayError(
                "Validation lots et plan lots non appariés ou incomplets"
            )
        lot_binding.update(
            {
                "provided": True,
                "status": "complete_validated",
                "plan_signature": lot_plan["plan_signature"],
                "validation_signature": lot_validation["validation_signature"],
                "dossier_ids": sorted(lot_dossiers_by_id),
                "root": str(lot_root),
            }
        )
        source_paths[lot_validation_path] = "priority_lot_replay_validation"

    staged_dossiers: list[dict[str, Any]] = []
    python_value = str(Path(python_executable or sys.executable).resolve())
    for ordinal, priority in enumerate(priorities, start=1):
        selected_identity = selection["selected_dossiers"][ordinal - 1]
        for field in (
            "operating_point_id",
            "mechanism",
            "lane_id",
            "supplier_id",
            "item_id",
            "dst_node_id",
            "edge_id",
            "target_product_id",
            "priority_status",
        ):
            if str(selected_identity.get(field) or "") != str(
                priority.get(field) or ""
            ):
                raise ActionReplayError(
                    f"La sélection signée diffère de la priorité sur {field}"
                )
        point_id = str(priority["operating_point_id"])
        _state, graph_path, floors, capacities = _state_files(
            campaign_root=campaign_root, manifest=manifest, point_id=point_id
        )
        source_paths[graph_path] = f"graph:{point_id}"
        if floors is not None:
            source_paths[floors] = f"supplier_floors:{point_id}"
        if capacities is not None:
            source_paths[capacities] = f"factory_capacities:{point_id}"
        graph = _read_json(graph_path)
        incident_records = _cell_incidents(records, priority)
        if _int(
            selected_identity.get("valid_exercised_seed_count"),
            label="graines exercées de la sélection",
        ) != len(incident_records):
            raise ActionReplayError(
                "Le nombre de graines exercées diffère de la sélection signée"
            )
        seeds = [
            _int(record["row"]["seed"], label="graine") for record in incident_records
        ]
        if (
            _int(
                selected_identity.get("representative_seed"),
                label="graine représentative signée",
            )
            not in seeds
        ):
            raise ActionReplayError("La graine représentative signée est hors cohorte")
        target_control_scope_lanes = [
            lane
            for lane in manifest.get("lanes") or []
            if str(lane.get("supplier_id") or "") == str(priority["supplier_id"])
            and str(lane.get("item_id") or "") == str(priority["item_id"])
            and str(lane.get("dst_node_id") or "") == str(priority["dst_node_id"])
        ]
        reallocation_scope_unique = len(target_control_scope_lanes) == 1 and str(
            target_control_scope_lanes[0].get("lane_id") or ""
        ) == str(priority["lane_id"])
        alternatives = _active_alternatives(
            records=records,
            manifest=manifest,
            priority=priority,
            seeds=seeds,
        )
        catalog = _action_catalog(
            priority=priority,
            graph=graph,
            active_alternatives=alternatives,
            reallocation_scope_unique=reallocation_scope_unique,
            stock_scale=stock_scale,
            lead_reduction_days=lead_reduction_days,
            target_priority_weight=target_priority_weight,
        )
        eligible_actions = [dict(action) for action in catalog if action["eligible"]]
        dossier_id = _sanitize(
            str(selected_identity.get("dossier_id") or "")
            or f"dossier_{ordinal:02d}_{point_id}_{priority['mechanism']}_{priority['lane_id']}"
        )
        if lot_dossiers_by_id:
            lot_dossier = lot_dossiers_by_id.get(dossier_id)
            if lot_dossier is None:
                raise ActionReplayError(
                    f"Le dossier {dossier_id} est absent du replay lots signé"
                )
            lot_priority = lot_dossier.get("priority") or {}
            for field in (
                "operating_point_id",
                "mechanism",
                "lane_id",
                "supplier_id",
                "item_id",
                "dst_node_id",
                "edge_id",
                "target_product_id",
            ):
                if str(lot_priority.get(field) or "") != str(priority.get(field) or ""):
                    raise ActionReplayError(
                        f"Le replay lots diffère du dossier finalizer sur {field}"
                    )
        seed_plans: list[dict[str, Any]] = []
        if not eligible_actions:
            staged_dossiers.append(
                {
                    "dossier_id": dossier_id,
                    "source_selection_ordinal": ordinal,
                    "priority": dict(priority),
                    "cohort_seed_count": len(incident_records),
                    "cohort_complete_30": len(incident_records) == EXPECTED_REPETITIONS,
                    "seeds": [
                        _int(record["row"]["seed"], label="graine")
                        for record in incident_records
                    ],
                    "graph": str(graph_path),
                    "graph_sha256": sha256_file(graph_path),
                    "action_catalog": catalog,
                    "eligible_action_ids": [],
                    "seed_plans": [],
                }
            )
            continue
        for incident_record in incident_records:
            incident = incident_record["row"]
            baseline_record = _baseline_record(records, incident_record)
            baseline = baseline_record["row"]
            incident_evidence, incident_evidence_path, source_risk_path, risk_bytes = (
                _case_sources(
                    campaign_root=campaign_root,
                    manifest=manifest,
                    record=incident_record,
                    priority=priority,
                )
            )
            baseline_evidence, baseline_evidence_path, _, _ = _case_sources(
                campaign_root=campaign_root,
                manifest=manifest,
                record=baseline_record,
                priority=None,
            )
            source_paths[incident_evidence_path] = "incident_case_evidence"
            source_paths[baseline_evidence_path] = "baseline_case_evidence"
            if source_risk_path is not None:
                source_paths[source_risk_path] = "incident_risk_csv"
            assert risk_bytes is not None
            seed = _int(incident["seed"], label="graine")
            if seed == _int(
                selected_identity.get("representative_seed"),
                label="graine représentative signée",
            ):
                expected_selection = {
                    "incident_case_key": str(incident["case_key"]),
                    "incident_case_signature": str(incident["case_signature"]),
                    "baseline_case_key": str(baseline["case_key"]),
                    "baseline_case_signature": str(baseline["case_signature"]),
                    "risk_csv_sha256": str(incident_evidence["risk_csv_sha256"]),
                    "incident_evidence_sha256": sha256_file(incident_evidence_path),
                    "baseline_evidence_sha256": sha256_file(baseline_evidence_path),
                }
                for field, expected in expected_selection.items():
                    if str(selected_identity.get(field) or "") != expected:
                        raise ActionReplayError(
                            f"La preuve représentative signée diffère sur {field}"
                        )
            days = _int(
                incident.get("required_simulation_days")
                or incident.get("simulation_days"),
                label="horizon",
            )
            state_evaluation_days = _int(
                incident.get("state_evaluation_days"),
                label="fenêtre d'état signée",
            )
            if not 1 <= state_evaluation_days <= days:
                raise ActionReplayError("Fenêtre d'état signée hors horizon")
            start_day = _int(incident.get("risk_start_day"), label="début incident")
            end_day = _int(incident.get("risk_end_day"), label="fin incident")
            if not 0 <= start_day <= end_day < days or end_day - start_day + 1 != 42:
                raise ActionReplayError("Fenêtre incident V4 invalide")
            expected_warmup = str(incident.get("warmup_core_state_sha256") or "")
            evidence_warmups = {
                str(
                    (incident_evidence.get("metrics") or {}).get(
                        "warmup_core_state_sha256"
                    )
                    or ""
                ),
                str(
                    (baseline_evidence.get("metrics") or {}).get(
                        "warmup_core_state_sha256"
                    )
                    or ""
                ),
                str(baseline.get("warmup_core_state_sha256") or ""),
            }
            if len(evidence_warmups | {expected_warmup}) != 1 or not re.fullmatch(
                r"[0-9a-f]{64}", expected_warmup
            ):
                raise ActionReplayError("Preuve d'état de chauffe apparié invalide")

            input_dir = output_root / "inputs" / dossier_id / f"seed_{seed}"
            risk_path = input_dir / "supplier_risk_events.csv"
            input_dir.mkdir(parents=True, exist_ok=True)
            risk_path.write_bytes(risk_bytes)
            risk_sha = sha256_file(risk_path)
            if risk_sha != str(incident_evidence.get("risk_csv_sha256") or ""):
                raise ActionReplayError("Copie du risque V4 modifiée")

            arm_specs: dict[str, Any] = {}
            shared = {
                "python_executable": python_value,
                "engine": engine,
                "graph": graph_path,
                "days": days,
                "seed": seed,
                "profile_args": profile_args,
                "managed_args": managed_args,
                "supplier_floors": floors,
                "factory_capacities": capacities,
            }
            for action in eligible_actions:
                action_id = str(action["action_id"])
                extension = (
                    "stock_scale.csv"
                    if action_id == ACTION_STOCK
                    else "control_schedule.csv"
                )
                action_input = input_dir / action_id / extension
                rows, fields = _action_input_rows(
                    action, priority=priority, start_day=start_day, end_day=end_day
                )
                _write_csv_atomic(action_input, rows, fields)
                run_dir = output_root / "runs" / dossier_id / f"seed_{seed}" / action_id
                command = _build_command(
                    **shared,
                    output_dir=run_dir,
                    risk_csv=risk_path,
                    action_id=action_id,
                    action_input=action_input,
                )
                arm_specs[action_id] = {
                    "arm_id": action_id,
                    "run_dir": str(run_dir),
                    "command": command,
                    "command_sha256": stable_sha256(command),
                    "risk_csv_sha256": risk_sha,
                    "action_id": action_id,
                    "action_input": str(action_input),
                    "action_input_sha256": sha256_file(action_input),
                }
            seed_plans.append(
                {
                    "seed": seed,
                    "horizon_days": days,
                    "state_evaluation_days": state_evaluation_days,
                    "risk_start_day": start_day,
                    "risk_end_day": end_day,
                    "impact_window_start_day": _int(
                        incident.get("impact_window_start_day"),
                        label="début fenêtre impact",
                    ),
                    "impact_window_end_day": _int(
                        incident.get("impact_window_end_day"),
                        label="fin fenêtre impact",
                    ),
                    "warmup_core_state_sha256": expected_warmup,
                    "incident_case_key": str(incident["case_key"]),
                    "incident_case_signature": str(incident["case_signature"]),
                    "incident_evidence_path": str(incident_evidence_path),
                    "incident_evidence_sha256": sha256_file(incident_evidence_path),
                    "baseline_case_key": str(baseline["case_key"]),
                    "baseline_case_signature": str(baseline["case_signature"]),
                    "baseline_evidence_path": str(baseline_evidence_path),
                    "baseline_evidence_sha256": sha256_file(baseline_evidence_path),
                    "signed_reference": {
                        "baseline": dict(baseline),
                        "incident_no_action": dict(incident),
                        "reference_mode": "signed_campaign_metrics_no_engine_rerun",
                    },
                    "incident_risk_contract": dict(
                        incident_evidence.get("risk_row") or {}
                    ),
                    "risk_csv": str(risk_path),
                    "risk_csv_sha256": risk_sha,
                    "arms": arm_specs,
                }
            )
        staged_dossiers.append(
            {
                "dossier_id": dossier_id,
                "source_selection_ordinal": ordinal,
                "priority": dict(priority),
                "cohort_seed_count": len(seed_plans),
                "cohort_complete_30": len(seed_plans) == EXPECTED_REPETITIONS,
                "seeds": [item["seed"] for item in seed_plans],
                "graph": str(graph_path),
                "graph_sha256": sha256_file(graph_path),
                "action_catalog": catalog,
                "eligible_action_ids": [
                    action["action_id"] for action in eligible_actions
                ],
                "seed_plans": seed_plans,
            }
        )

    output_root.mkdir(parents=True, exist_ok=True)
    inventory_entries = [
        _source_entry(path, role)
        for path, role in sorted(source_paths.items(), key=lambda item: str(item[0]))
    ]
    inventory = _signed(
        {
            "schema_version": INVENTORY_SCHEMA_VERSION,
            "campaign_signature": manifest["campaign_signature"],
            "created_at_utc": utc_now(),
            "entries": inventory_entries,
        },
        "inventory_signature",
    )
    inventory_path = output_root / "source_inventory.json"
    _write_json_atomic(inventory_path, inventory)
    plan = _signed(
        {
            "schema_version": PLAN_SCHEMA_VERSION,
            "created_at_utc": utc_now(),
            "replay_root": str(output_root),
            "campaign_root": str(campaign_root),
            "results_dir": str(results_dir),
            "campaign_signature": manifest["campaign_signature"],
            "campaign_validation_sha256": sha256_file(
                results_dir / "campaign_validation.json"
            ),
            "finalizer_selection_signature": selection["selection_signature"],
            "lot_replay_binding": lot_binding,
            "engine": str(engine),
            "engine_sha256": sha256_file(engine),
            "engine_profile": str(profile),
            "engine_profile_sha256": sha256_file(profile),
            "python_executable": python_value,
            "source_inventory": str(inventory_path),
            "source_inventory_sha256": sha256_file(inventory_path),
            "source_inventory_signature": inventory["inventory_signature"],
            "requested_parameters": {
                "max_dossiers": max_dossiers,
                "stock_scale": stock_scale,
                "lead_reduction_days": lead_reduction_days,
                "target_priority_weight": target_priority_weight,
                "reference_mode": reference_mode,
            },
            "measurement_windows": _measurement_windows(staged_dossiers),
            "scientific_contract": {
                "paired_arms": [
                    "signed_baseline",
                    "signed_incident_no_action",
                    "executed_incident_with_action",
                ],
                "action_comparator": "same_seed_signed_incident_no_action",
                "reference_mode": "signed_reference",
                "reference_engine_reruns": 0,
                "only_action_arms_execute_the_engine": True,
                "maximum_dossiers": 3,
                "maximum_repetitions_per_dossier": EXPECTED_REPETITIONS,
                "actions_kept_separate": True,
                "common_severity_or_action_score": False,
                "quality_incident_or_action_included": False,
                "availability_or_capacity_invented": False,
                "shipment_id_targeting_claimed": False,
                "real_client_or_order_claimed": False,
                "client_scope": "aggregated_C_XXXXX",
                "closed_loop_claimed": False,
                "control_mode": "open_loop_scenario_action_hypotheses",
                "historical_probability_claimed": False,
                "cost_completeness_claimed": False,
            },
            "dossiers": staged_dossiers,
        },
        "plan_signature",
    )
    _write_json_atomic(plan_path, plan)
    command_rows = [
        {
            "dossier_id": dossier["dossier_id"],
            "seed": seed_plan["seed"],
            "arm_id": arm_id,
            **arm,
        }
        for dossier in staged_dossiers
        for seed_plan in dossier["seed_plans"]
        for arm_id, arm in seed_plan["arms"].items()
    ]
    commands = _signed(
        {
            "schema_version": f"{SCHEMA_VERSION}.commands.v1",
            "plan_signature": plan["plan_signature"],
            "commands": command_rows,
        },
        "commands_signature",
    )
    _write_json_atomic(output_root / "action_replay_commands.json", commands)
    return plan


def load_and_validate_plan(root: Path) -> dict[str, Any]:
    root = root.resolve()
    plan_path = root / "action_replay_plan.json"
    plan = _read_json(plan_path)
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise ActionReplayError("Schéma de plan d'actions inattendu")
    _verify_signed(plan, "plan_signature", "plan d'actions")
    if Path(str(plan.get("replay_root") or "")).resolve() != root:
        raise ActionReplayError("Le plan appartient à un autre dossier")
    scientific = plan.get("scientific_contract") or {}
    if (
        scientific.get("reference_mode") != "signed_reference"
        or _int(
            scientific.get("reference_engine_reruns"),
            label="nombre de reruns de référence",
        )
        != 0
        or scientific.get("only_action_arms_execute_the_engine") is not True
        or scientific.get("closed_loop_claimed") is not False
    ):
        raise ActionReplayError("Contrat signed_reference du plan invalide")
    inventory_path = Path(str(plan.get("source_inventory") or "")).resolve()
    if not inventory_path.is_file() or sha256_file(inventory_path) != str(
        plan.get("source_inventory_sha256") or ""
    ):
        raise ActionReplayError("Inventaire source absent ou modifié")
    inventory = _read_json(inventory_path)
    if inventory.get("schema_version") != INVENTORY_SCHEMA_VERSION:
        raise ActionReplayError("Schéma d'inventaire source inattendu")
    _verify_signed(inventory, "inventory_signature", "inventaire source")
    if inventory["inventory_signature"] != plan.get("source_inventory_signature"):
        raise ActionReplayError("Signature d'inventaire non liée au plan")
    _verify_source_inventory(inventory.get("entries") or [])
    expected_command_rows: list[dict[str, Any]] = []
    dossier_ids: set[str] = set()
    for dossier in plan.get("dossiers") or []:
        dossier_id = str(dossier.get("dossier_id") or "")
        if not dossier_id or dossier_id in dossier_ids:
            raise ActionReplayError("Identité de dossier vide ou dupliquée")
        dossier_ids.add(dossier_id)
        cohort_count = _int(dossier.get("cohort_seed_count"), label="taille cohorte")
        if not 1 <= cohort_count <= EXPECTED_REPETITIONS:
            raise ActionReplayError("Taille de cohorte invalide")
        catalog = dossier.get("action_catalog") or []
        catalog_ids = [str(action.get("action_id") or "") for action in catalog]
        if "" in catalog_ids or len(catalog_ids) != len(set(catalog_ids)):
            raise ActionReplayError("Catalogue d'actions vide ou dupliqué")
        eligible = [str(value) for value in dossier.get("eligible_action_ids") or []]
        if (
            len(eligible) != len(set(eligible))
            or any(action_id not in ALLOWED_ACTIONS for action_id in eligible)
            or set(eligible)
            != {
                str(action.get("action_id") or "")
                for action in catalog
                if action.get("eligible") is True
            }
        ):
            raise ActionReplayError("Actions éligibles du plan incohérentes")
        seed_plans = dossier.get("seed_plans") or []
        if bool(eligible) != bool(seed_plans):
            raise ActionReplayError(
                "Plans par graine incohérents avec les actions éligibles"
            )
        if seed_plans and len(seed_plans) != cohort_count:
            raise ActionReplayError("La cohorte et les plans par graine diffèrent")
        seeds = [_int(item.get("seed"), label="graine plan") for item in seed_plans]
        if len(seeds) != len(set(seeds)):
            raise ActionReplayError("Graines de replay dupliquées")
        for seed_plan in seed_plans:
            risk = Path(str(seed_plan.get("risk_csv") or ""))
            if not risk.is_file() or sha256_file(risk) != seed_plan.get(
                "risk_csv_sha256"
            ):
                raise ActionReplayError("CSV incident du plan absent ou modifié")
            reference = seed_plan.get("signed_reference") or {}
            if reference.get("reference_mode") != (
                "signed_campaign_metrics_no_engine_rerun"
            ):
                raise ActionReplayError("Mode de référence d'une graine invalide")
            baseline = reference.get("baseline") or {}
            incident = reference.get("incident_no_action") or {}
            seed = _int(seed_plan.get("seed"), label="graine plan")
            state_evaluation_days = _int(
                seed_plan.get("state_evaluation_days"),
                label="fenêtre d'état du plan",
            )
            if (
                not 1
                <= state_evaluation_days
                <= _int(seed_plan.get("horizon_days"), label="horizon du plan")
            ):
                raise ActionReplayError("Fenêtre d'état du plan hors horizon")
            priority = dossier.get("priority") or {}
            if (
                str(baseline.get("stage") or "") != "baseline"
                or str(incident.get("stage") or "") != "incident"
                or _int(baseline.get("seed"), label="graine baseline") != seed
                or _int(incident.get("seed"), label="graine incident") != seed
                or str(baseline.get("operating_point_id") or "")
                != str(priority.get("operating_point_id") or "")
                or str(incident.get("operating_point_id") or "")
                != str(priority.get("operating_point_id") or "")
                or str(incident.get("mechanism") or "")
                != str(priority.get("mechanism") or "")
                or str(incident.get("lane_id") or "")
                != str(priority.get("lane_id") or "")
                or str(incident.get("baseline_case_signature") or "")
                != str(baseline.get("case_signature") or "")
                or str(seed_plan.get("baseline_case_signature") or "")
                != str(baseline.get("case_signature") or "")
                or str(seed_plan.get("incident_case_signature") or "")
                != str(incident.get("case_signature") or "")
            ):
                raise ActionReplayError("Triplet signé mal apparié dans le plan")
            for path_field, hash_field in (
                ("baseline_evidence_path", "baseline_evidence_sha256"),
                ("incident_evidence_path", "incident_evidence_sha256"),
            ):
                evidence_path = Path(str(seed_plan.get(path_field) or "")).resolve()
                if not evidence_path.is_file() or sha256_file(
                    evidence_path
                ) != seed_plan.get(hash_field):
                    raise ActionReplayError(
                        "Preuve signée de référence absente ou modifiée"
                    )
            risk_contract = lot_replay_v4._risk_row_contract(
                seed_plan.get("incident_risk_contract") or {},
                priority=priority,
                incident=incident,
            )
            if hashlib.sha256(
                lot_replay_v4._risk_csv_bytes(risk_contract)
            ).hexdigest() != str(seed_plan.get("risk_csv_sha256") or ""):
                raise ActionReplayError("Contrat physique et CSV d'incident diffèrent")
            arms = seed_plan.get("arms") or {}
            if set(arms) != set(eligible):
                raise ActionReplayError(
                    "Seuls les bras actions séparés sont autorisés; aucun rerun référence"
                )
            for arm_id, arm in arms.items():
                if (
                    arm_id not in ALLOWED_ACTIONS
                    or str(arm.get("action_id") or "") != arm_id
                    or str(arm.get("risk_csv_sha256") or "")
                    != str(seed_plan.get("risk_csv_sha256") or "")
                ):
                    raise ActionReplayError("Identité de bras action invalide")
                command = arm.get("command")
                if not isinstance(command, list) or not all(
                    isinstance(token, str) for token in command
                ):
                    raise ActionReplayError("Commande du plan invalide")
                if stable_sha256(command) != arm.get("command_sha256"):
                    raise ActionReplayError("Commande du plan modifiée")
                _validate_command(
                    command,
                    f"action:{arm_id}",
                )
                expected_flags = {
                    "--input": str(Path(str(dossier.get("graph") or "")).resolve()),
                    "--output-dir": str(Path(str(arm.get("run_dir") or "")).resolve()),
                    "--days": str(_int(seed_plan.get("horizon_days"), label="horizon")),
                    "--seed": str(seed),
                    "--supplier-risk-events-csv": str(risk.resolve()),
                }
                for flag, expected in expected_flags.items():
                    if _flag_values(command, flag) != [expected]:
                        raise ActionReplayError(f"Commande action mal liée: {flag}")
                action_input = str(arm.get("action_input") or "")
                if action_input:
                    action_path = Path(action_input).resolve()
                    if not action_path.is_file() or sha256_file(action_path) != arm.get(
                        "action_input_sha256"
                    ):
                        raise ActionReplayError("Entrée d'action absente ou modifiée")
                    expected_flag = (
                        "--measurement-start-stock-scale-csv"
                        if arm_id == ACTION_STOCK
                        else "--control-schedule-csv"
                    )
                    if _flag_values(command, expected_flag) != [str(action_path)]:
                        raise ActionReplayError("Entrée d'action et commande non liées")
                expected_command_rows.append(
                    {
                        "dossier_id": dossier_id,
                        "seed": seed,
                        "arm_id": arm_id,
                        **arm,
                    }
                )
    expected_windows = _measurement_windows(plan.get("dossiers") or [])
    if plan.get("measurement_windows") != expected_windows:
        raise ActionReplayError("Contrat signé des fenêtres KPI actions incohérent")
    commands_path = root / "action_replay_commands.json"
    commands = _read_json(commands_path)
    _verify_signed(commands, "commands_signature", "liste de commandes")
    if commands.get("plan_signature") != plan.get("plan_signature"):
        raise ActionReplayError("Liste de commandes non liée au plan")
    if commands.get("commands") != expected_command_rows:
        raise ActionReplayError(
            "Liste de commandes différente des seuls bras actions du plan"
        )
    return plan


def _run_files(run_dir: Path) -> dict[str, Path]:
    data = run_dir / "data"
    return {
        "summary": run_dir / "summaries" / "first_simulation_summary.json",
        "shipments": data / "production_supplier_shipments_daily.csv",
        "risk_applied": data / "supplier_risk_events_applied_daily.csv",
        "state_risks": data / "supplier_state_dependent_risk_events.csv",
        "demand": data / "production_demand_service_daily.csv",
        "production": data / "production_output_products_daily.csv",
        "stocks": data / "production_input_stocks_daily.csv",
        "nervousness": data / "production_factory_nervousness.csv",
        "action_ledger": data / "canonical_action_ledger.csv",
        "stock_adjustments": data / "measurement_start_stock_adjustments.csv",
    }


def _event_tokens(value: Any) -> set[str]:
    return {
        token.strip() for token in re.split(r"[;,|]", str(value or "")) if token.strip()
    }


def _validate_applied_incident(
    rows: Sequence[Mapping[str, Any]],
    *,
    dossier: Mapping[str, Any],
    seed_plan: Mapping[str, Any],
) -> None:
    """Prove that the action run retained exactly the signed V4 incident."""

    if not rows:
        raise ActionReplayError(
            "Le bras action ne contient aucun incident physiquement appliqué"
        )
    contract = seed_plan.get("incident_risk_contract") or {}
    event_id = str(contract.get("event_id") or "")
    mechanism = str(dossier["priority"]["mechanism"])
    risk_type, risk_value = lot_replay_v4.ALLOWED_MECHANISMS[mechanism]
    start = _int(seed_plan["risk_start_day"], label="début incident")
    end = _int(seed_plan["risk_end_day"], label="fin incident")
    required_fields = {
        "stock_multiplier": 1.0,
        "capacity_multiplier": 1.0,
        "lead_time_multiplier": 1.0,
        "quality_delay_days": 0.0,
        "quality_yield_multiplier": 1.0,
        "availability_multiplier": 1.0,
        "purchase_cost_multiplier": 1.0,
        "transport_cost_multiplier": 1.0,
        "external_capacity_multiplier": 1.0,
        "external_availability_multiplier": 1.0,
        "external_lead_time_multiplier": 1.0,
        "external_lead_time_extra_days": 0.0,
        "external_quality_yield_multiplier": 1.0,
        "external_cost_multiplier": 1.0,
        "stock_writeoff_fraction": 0.0,
        "lead_time_extra_days": risk_value
        if risk_type == "lead_time_extra_days"
        else 0.0,
        "reliability_multiplier": risk_value if risk_type == "reliability" else 1.0,
    }
    for row in rows:
        if _event_tokens(row.get("event_ids")) != {event_id}:
            raise ActionReplayError(
                "Le ledger contient un événement différent de l'incident signé"
            )
        day = _int(row.get("day"), label="jour d'application du risque")
        if not start <= day <= end:
            raise ActionReplayError("L'incident appliqué sort de la fenêtre signée")
        for result_field, priority_field in (
            ("supplier_id", "supplier_id"),
            ("item_id", "item_id"),
            ("dst_node_id", "dst_node_id"),
            ("edge_id", "edge_id"),
        ):
            if str(row.get(result_field) or "") != str(
                dossier["priority"][priority_field]
            ):
                raise ActionReplayError("Le risque appliqué sort de la voie signée")
        for field, expected in required_fields.items():
            if field not in row or str(row.get(field) or "").strip() == "":
                raise ActionReplayError(f"Le ledger d'incident ne mesure pas {field}")
            if not math.isclose(
                _float(row[field], label=f"risque appliqué {field}"),
                expected,
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                raise ActionReplayError(
                    f"L'incident appliqué diffère du contrat signé: {field}"
                )


def _summary_contract(
    *,
    summary: Mapping[str, Any],
    dossier: Mapping[str, Any],
    seed_plan: Mapping[str, Any],
    arm_id: str,
    arm: Mapping[str, Any],
) -> None:
    if str(summary.get("input_sha256") or "") != str(dossier["graph_sha256"]):
        raise ActionReplayError("Le graphe du résultat diffère du plan")
    if _int(summary.get("sim_days"), label="horizon résultat") != _int(
        seed_plan["horizon_days"], label="horizon plan"
    ):
        raise ActionReplayError("L'horizon du résultat diffère du plan")
    policy = summary.get("policy")
    if not isinstance(policy, Mapping):
        raise ActionReplayError("Politique moteur absente du résumé")
    if _int(policy.get("seed"), label="graine résultat") != _int(
        seed_plan["seed"], label="graine plan"
    ):
        raise ActionReplayError("La graine du résultat diffère du plan")
    if policy.get("common_random_numbers") is not True:
        raise ActionReplayError("Les nombres aléatoires communs ne sont pas actifs")
    if str(policy.get("output_profile") or "") != "compact":
        raise ActionReplayError("Le résultat n'est pas compact")
    if policy.get("lot_trace_enabled") is not False:
        raise ActionReplayError(
            "Le replay statistique d'actions ne doit pas tracer les lots"
        )
    state_risk = policy.get("supplier_state_dependent_risk") or {}
    if state_risk.get("enabled") is not False:
        raise ActionReplayError("Un risque fournisseur endogène a été activé")
    if any(key in policy for key in ("demand_perturbation", "control_probe")):
        raise ActionReplayError("Un modificateur hors action apparaît dans le résumé")
    provider = policy.get("control_provider")
    if (
        not isinstance(provider, Mapping)
        or provider.get("closed_loop_claimed") is not False
    ):
        raise ActionReplayError("Le résultat ne prouve pas l'absence de boucle fermée")

    supplier_risk = policy.get("supplier_risk") or {}
    risk_expected = arm_id != "baseline"
    if bool(supplier_risk.get("enabled")) is not risk_expected:
        raise ActionReplayError("Activation de l'incident incohérente avec le bras")
    expected_risk_hash = str(arm.get("risk_csv_sha256") or "")
    if risk_expected:
        if (
            _int(supplier_risk.get("event_count"), label="nombre d'incidents") != 1
            or str(supplier_risk.get("events_csv_sha256") or "") != expected_risk_hash
        ):
            raise ActionReplayError(
                "Le résultat ne contient pas l'incident signé unique"
            )
    elif _int(supplier_risk.get("event_count", 0), label="nombre d'incidents") != 0:
        raise ActionReplayError("Le bras de référence contient un incident")

    schedule = policy.get("control_schedule") or {}
    stock = policy.get("measurement_start_stock_scale")
    if arm_id in {"baseline", "incident_no_action"}:
        if schedule.get("enabled") is not False or stock is not None:
            raise ActionReplayError("Le bras sans action contient un actionneur")
        if provider.get("enabled") is not False or provider.get("mode") != (
            "historical_no_external_control"
        ):
            raise ActionReplayError(
                "Le bras neutre contient un fournisseur de contrôle"
            )
    elif arm_id == ACTION_STOCK:
        if schedule.get("enabled") is not False or not isinstance(stock, Mapping):
            raise ActionReplayError("Le stock J0 n'est pas l'unique action du bras")
        if provider.get("enabled") is not False or provider.get("mode") != (
            "historical_no_external_control"
        ):
            raise ActionReplayError("Le bras stock contient un autre actionneur")
        if str(stock.get("source_csv_sha256") or "") != str(
            arm.get("action_input_sha256") or ""
        ):
            raise ActionReplayError("Le CSV de stock J0 n'est pas celui du plan")
    elif arm_id in SCHEDULE_ACTIONS:
        if stock is not None or schedule.get("enabled") is not True:
            raise ActionReplayError(
                "Le planning de contrôle n'est pas l'unique action du bras"
            )
        if (
            provider.get("enabled") is not True
            or provider.get("mode") != "daily_open_loop_schedule"
        ):
            raise ActionReplayError("Le planning n'est pas déclaré en boucle ouverte")
        if str(schedule.get("sha256") or "") != str(
            arm.get("action_input_sha256") or ""
        ):
            raise ActionReplayError("Le planning de contrôle n'est pas celui du plan")
        if _int(schedule.get("schedule_rows"), label="lignes planning") != 42:
            raise ActionReplayError(
                "Le planning doit contenir les 42 jours de l'incident"
            )
    else:
        raise ActionReplayError(f"Bras résultat inconnu: {arm_id}")


def _action_application(
    *,
    files: Mapping[str, Path],
    dossier: Mapping[str, Any],
    seed_plan: Mapping[str, Any],
    arm_id: str,
    arm: Mapping[str, Any],
) -> dict[str, Any]:
    priority = dossier["priority"]
    if arm_id in {"baseline", "incident_no_action"}:
        if _read_csv(files["action_ledger"]):
            raise ActionReplayError(
                "Un ledger d'action non vide existe dans un bras neutre"
            )
        adjustments = _read_csv(files["stock_adjustments"])
        if adjustments:
            raise ActionReplayError("Un ajustement de stock existe dans un bras neutre")
        return {
            "scheduled": False,
            "physically_exercised": False,
            "executed_quantity": 0.0,
            "quantity_uom": "",
            "reason": "no_action_arm",
        }

    if arm_id == ACTION_STOCK:
        rows = [
            row
            for row in _read_csv(files["stock_adjustments"])
            if str(row.get("node_id") or "") == str(priority["dst_node_id"])
            and str(row.get("item_id") or "") == str(priority["item_id"])
        ]
        if len(rows) != 1:
            raise ActionReplayError("Ajustement J0 cible absent ou dupliqué")
        row = rows[0]
        action = next(
            item for item in dossier["action_catalog"] if item["action_id"] == arm_id
        )
        expected_scale = _float(
            action["parameters"]["measurement_start_stock_scale"],
            label="échelle stock plan",
        )
        if not math.isclose(
            _float(row.get("scale"), label="échelle stock appliquée"),
            expected_scale,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ActionReplayError("L'échelle de stock appliquée diffère du plan")
        before = _float(
            row.get("stock_before_qty"), label="stock J0 avant", default=0.0
        )
        added = _float(row.get("stock_added_qty"), label="stock J0 ajouté", default=0.0)
        expected_added = before * (expected_scale - 1.0)
        if not math.isclose(added, expected_added, rel_tol=1e-6, abs_tol=1e-5):
            raise ActionReplayError(
                "La quantité physique ajoutée ne correspond pas au facteur planifié"
            )
        after = _float(row.get("stock_after_qty"), label="stock J0 après", default=0.0)
        if not math.isclose(after, before + added, rel_tol=1e-6, abs_tol=1e-5):
            raise ActionReplayError("Le bilan physique du stock J0 ne ferme pas")
        uom = str(row.get("uom") or "").strip()
        if not uom:
            raise ActionReplayError("L'unité physique du stock J0 est absente")
        exercised = before > EPS and added > EPS
        return {
            "scheduled": True,
            "physically_exercised": exercised,
            "executed_quantity": added if exercised else 0.0,
            "quantity_uom": uom,
            "stock_before_j0_qty": before,
            "stock_after_j0_qty": after,
            "stock_scale": expected_scale,
            "stock_base_semantics": "measured_free_qualified_stock_at_j0",
            "reason": "applied_positive_j0_free_stock"
            if exercised
            else "non_exercised_zero_j0_stock",
            "not_a_purchase_realized": True,
        }

    ledger = _read_csv(files["action_ledger"])
    action_name = SCHEDULE_ACTIONS[arm_id]
    relevant = [
        row
        for row in ledger
        if str(row.get("action") or "") == action_name
        and str(row.get("source_supplier_id") or "") == str(priority["supplier_id"])
        and str(row.get("source_item_id") or "") == str(priority["item_id"])
        and str(row.get("source_dst_node_id") or "") == str(priority["dst_node_id"])
    ]
    expected_lines = set(range(2, 44))
    actual_lines = {
        _int(row.get("source_line"), label="ligne source planning") for row in relevant
    }
    if actual_lines != expected_lines:
        raise ActionReplayError("Les 42 lignes du planning ne sont pas toutes auditées")
    start = _int(seed_plan["risk_start_day"], label="début incident")
    end = _int(seed_plan["risk_end_day"], label="fin incident")
    if {_int(row.get("day"), label="jour ledger") for row in relevant} - set(
        range(start, end + 1)
    ):
        raise ActionReplayError("Le ledger d'action sort de la fenêtre signée")

    if arm_id == ACTION_LEAD:
        action = next(
            item for item in dossier["action_catalog"] if item["action_id"] == arm_id
        )
        expected = _float(
            action["parameters"]["lead_time_adjustment_days"], label="réduction délai"
        )
        if any(
            not math.isclose(
                _float(row.get("effective"), label="délai effectif"),
                expected,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
            for row in relevant
        ):
            raise ActionReplayError("Le délai effectif sort de la borne planifiée")
        applied = [
            row
            for row in relevant
            if str(row.get("action_stage") or "") == "supplier_lane_execution"
            and str(row.get("status") or "") == "applied"
            and _float(
                row.get("executed_control_volume_qty"),
                label="volume délai exécuté",
                default=0.0,
            )
            > EPS
        ]
        quantity = sum(
            _float(
                row.get("executed_control_volume_qty"),
                label="volume délai exécuté",
                default=0.0,
            )
            for row in applied
        )
        return {
            "scheduled": True,
            "physically_exercised": bool(applied),
            "executed_quantity": quantity,
            "quantity_uom": next(
                (str(row.get("quantity_uom") or "") for row in applied), ""
            ),
            "scheduled_source_line_count": len(expected_lines),
            "audited_source_line_count": len(actual_lines),
            "effective_adjustment_days": int(expected),
            "reason": "future_departures_touched"
            if applied
            else "non_exercised_no_future_departure",
            "named_shipment_targeted": False,
        }

    # Reallocation is only exercised when the native ledger proves that the
    # target lane's allocation actually decreased.  A matched schedule alone
    # is insufficient.
    shifted_rows = []
    for row in relevant:
        if (
            str(row.get("action_stage") or "") != "supplier_allocation_priority"
            or str(row.get("status") or "") != "applied"
        ):
            continue
        before = _float(
            row.get("q_before_priority_allocation_qty"),
            label="allocation avant",
            default=0.0,
        )
        after = _float(
            row.get("q_after_priority_allocation_qty"),
            label="allocation après",
            default=0.0,
        )
        if before - after > EPS:
            shifted_rows.append((row, before - after))
    shifted = sum(value for _, value in shifted_rows)
    return {
        "scheduled": True,
        "physically_exercised": shifted > EPS,
        "executed_quantity": shifted,
        "quantity_uom": next(
            (str(row.get("quantity_uom") or "") for row, _ in shifted_rows), ""
        ),
        "scheduled_source_line_count": len(expected_lines),
        "audited_source_line_count": len(actual_lines),
        "quantity_shifted_away_from_incident_lane": shifted,
        "eligible_alternative_supplier_ids": sorted(
            {
                str(alternative.get("supplier_id") or "")
                for alternative in next(
                    item
                    for item in dossier["action_catalog"]
                    if item["action_id"] == ACTION_REALLOCATION
                )["physical_scope"]["active_alternatives"]
            }
        ),
        "reason": "allocation_physically_shifted"
        if shifted > EPS
        else "non_exercised_no_quantity_shifted",
    }


def _lead_effect_evidence(
    *,
    incident_shipments: Sequence[Mapping[str, Any]],
    action_shipments: Sequence[Mapping[str, Any]],
    dossier: Mapping[str, Any],
    seed_plan: Mapping[str, Any],
) -> dict[str, Any]:
    priority = dossier["priority"]
    start = _int(seed_plan["risk_start_day"], label="début incident")
    end = _int(seed_plan["risk_end_day"], label="fin incident")

    def indexed(
        rows: Sequence[Mapping[str, Any]],
    ) -> dict[tuple[str, int, float, float], dict[str, Any]]:
        result: dict[tuple[str, int, float, float], dict[str, Any]] = {}
        for row in rows:
            day = _int(
                row.get("risk_decision_day", row.get("day", -1)), label="jour départ"
            )
            if not start <= day <= end:
                continue
            if any(
                str(row.get(field) or "") != str(priority[source])
                for field, source in (
                    ("src_node_id", "supplier_id"),
                    ("item_id", "item_id"),
                    ("dst_node_id", "dst_node_id"),
                    ("edge_id", "edge_id"),
                )
            ):
                continue
            key = (
                str(row.get("shipment_id") or ""),
                day,
                round(_float(row.get("pulled_qty"), label="quantité tirée"), 6),
                round(_float(row.get("shipped_qty"), label="quantité expédiée"), 6),
            )
            if not key[0] or key in result:
                continue
            result[key] = dict(row)
        return result

    incident_index = indexed(incident_shipments)
    action_index = indexed(action_shipments)
    reductions: list[int] = []
    for key in sorted(set(incident_index) & set(action_index)):
        reduction = _int(
            incident_index[key].get("lead_days"), label="délai incident"
        ) - _int(action_index[key].get("lead_days"), label="délai action")
        reductions.append(reduction)
    planned = abs(
        int(
            next(
                item
                for item in dossier["action_catalog"]
                if item["action_id"] == ACTION_LEAD
            )["parameters"]["lead_time_adjustment_days"]
        )
    )
    if any(value < 0 or value > planned for value in reductions):
        raise ActionReplayError(
            "Une réduction effective de délai dépasse la borne planifiée"
        )
    positive = [value for value in reductions if value > 0]
    return {
        "matched_future_departure_count": len(reductions),
        "positively_shortened_departure_count": len(positive),
        "maximum_observed_lead_reduction_days": max(positive, default=0),
        "planned_maximum_lead_reduction_days": planned,
        "bounded_effect_proven": bool(positive) and max(positive) <= planned,
        "comparison_uses_shipment_id_only_as_crn_diagnostic_not_as_actuator": True,
    }


def validate_run_arm(
    *,
    dossier: Mapping[str, Any],
    seed_plan: Mapping[str, Any],
    arm_id: str,
    arm: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = Path(str(arm["run_dir"])).resolve()
    files = _run_files(run_dir)
    required_names = set(files) - {"stock_adjustments"}
    if arm_id == ACTION_STOCK:
        required_names.add("stock_adjustments")
    missing = [
        str(files[name]) for name in sorted(required_names) if not files[name].is_file()
    ]
    if missing:
        raise ActionReplayError("Fichiers moteur absents: " + ", ".join(missing))
    summary = _read_json(files["summary"])
    _summary_contract(
        summary=summary,
        dossier=dossier,
        seed_plan=seed_plan,
        arm_id=arm_id,
        arm=arm,
    )
    if _read_csv(files["state_risks"]):
        raise ActionReplayError("Le ledger de risques endogènes doit rester vide")
    risk_rows = _read_csv(files["risk_applied"])
    if arm_id == "baseline":
        if risk_rows:
            raise ActionReplayError("Le bras baseline contient un incident appliqué")
    else:
        _validate_applied_incident(
            risk_rows,
            dossier=dossier,
            seed_plan=seed_plan,
        )
    application = _action_application(
        files=files,
        dossier=dossier,
        seed_plan=seed_plan,
        arm_id=arm_id,
        arm=arm,
    )
    return {
        "run_dir": str(run_dir),
        "summary_sha256": sha256_file(files["summary"]),
        "files": {
            key: {"path": str(path), "sha256": sha256_file(path)}
            for key, path in files.items()
            if path.is_file()
        },
        "action_application": application,
    }


Executor = Callable[[Sequence[str], Path], Any]


def _archive_partial_action_run(
    *,
    root: Path,
    run_dir: Path,
    dossier_id: str,
    seed: int,
    arm_id: str,
    validation_error: str,
) -> Path:
    """Preserve an incomplete engine directory before a clean replay.

    A process interruption may leave a summary or a subset of compact outputs
    without a signed case-evidence file.  Reusing that directory would mix two
    executions, while merely noticing the summary would make the replay
    permanently non-resumable.  The old bytes are therefore inventoried and
    moved inside the replay's recovery area before the exact signed command is
    run again.
    """

    root = root.resolve()
    run_dir = run_dir.resolve()
    runs_root = (root / "runs").resolve()
    if run_dir == runs_root or not run_dir.is_relative_to(runs_root):
        raise ActionReplayError("Bras partiel hors de la racine de replay actions")
    if not run_dir.is_dir():
        raise ActionReplayError("Le bras partiel n'est pas un dossier")
    files = sorted(path for path in run_dir.rglob("*") if path.is_file())
    inventory = [
        {
            "relative_path": path.relative_to(run_dir).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]
    recovery_root = root / "recovery" / "partial_action_arms"
    recovery_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base = _sanitize(f"{dossier_id}__seed_{seed}__{arm_id}__{stamp}")
    destination = recovery_root / base
    suffix = 1
    while destination.exists():
        destination = recovery_root / f"{base}.{suffix}"
        suffix += 1
    run_dir.replace(destination)
    recovery_manifest = _signed(
        {
            "schema_version": f"{SCHEMA_VERSION}.partial_run_recovery.v1",
            "archived_at_utc": utc_now(),
            "original_run_dir": str(run_dir),
            "archive_dir": str(destination.resolve()),
            "dossier_id": dossier_id,
            "seed": seed,
            "arm_id": arm_id,
            "reason": "incomplete_or_invalid_without_signed_case_evidence",
            "validation_error": validation_error,
            "pre_archive_files": inventory,
        },
        "recovery_signature",
    )
    _write_json_atomic(destination / "recovery_manifest.json", recovery_manifest)
    return destination


def _run_one(
    *,
    root: Path,
    plan: Mapping[str, Any],
    dossier: Mapping[str, Any],
    seed_plan: Mapping[str, Any],
    arm_id: str,
    arm: Mapping[str, Any],
    execute: bool,
    executor: Executor | None,
) -> dict[str, Any]:
    evidence_dir = (
        root
        / "case_evidence"
        / str(dossier["dossier_id"])
        / f"seed_{seed_plan['seed']}"
    )
    evidence_path = evidence_dir / f"{arm_id}.json"
    if evidence_path.is_file():
        evidence = _read_json(evidence_path)
        _verify_signed(evidence, "evidence_signature", "preuve de bras action")
        if (
            evidence.get("plan_signature") != plan.get("plan_signature")
            or evidence.get("command_sha256") != arm.get("command_sha256")
            or evidence.get("status") != "valid"
        ):
            raise ActionReplayError("Preuve de bras existante incompatible")
        # Revalidate output rather than trusting a receipt from an interrupted run.
        validated = validate_run_arm(
            dossier=dossier,
            seed_plan=seed_plan,
            arm_id=arm_id,
            arm=arm,
        )
        for field, current in validated.items():
            if evidence.get(field) != current:
                raise ActionReplayError(
                    f"Le résultat du bras {arm_id} a changé depuis sa preuve signée"
                )
        return evidence
    run_dir = Path(str(arm["run_dir"])).resolve()
    prevalidated: dict[str, Any] | None = None
    if run_dir.is_dir() and any(run_dir.iterdir()):
        try:
            prevalidated = validate_run_arm(
                dossier=dossier,
                seed_plan=seed_plan,
                arm_id=arm_id,
                arm=arm,
            )
        except ActionReplayError as exc:
            if not execute:
                return {
                    "dossier_id": dossier["dossier_id"],
                    "seed": seed_plan["seed"],
                    "arm_id": arm_id,
                    "status": "planned_not_executed",
                    "partial_output_detected": True,
                }
            _archive_partial_action_run(
                root=root,
                run_dir=run_dir,
                dossier_id=str(dossier["dossier_id"]),
                seed=_int(seed_plan["seed"], label="graine du bras partiel"),
                arm_id=arm_id,
                validation_error=str(exc),
            )
    if prevalidated is None:
        if not execute:
            return {
                "dossier_id": dossier["dossier_id"],
                "seed": seed_plan["seed"],
                "arm_id": arm_id,
                "status": "planned_not_executed",
            }
        run_dir.mkdir(parents=True, exist_ok=True)
        command = list(arm["command"])
        if executor is None:
            completed = subprocess.run(
                command,
                cwd=str(Path(__file__).resolve().parents[3]),
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            completed = executor(command, run_dir)
        stdout = str(getattr(completed, "stdout", "") or "")
        stderr = str(getattr(completed, "stderr", "") or "")
        (run_dir / "action_replay.stdout.log").write_text(
            stdout[-200_000:], encoding="utf-8"
        )
        (run_dir / "action_replay.stderr.log").write_text(
            stderr[-200_000:], encoding="utf-8"
        )
        if int(getattr(completed, "returncode", 1)) != 0:
            raise ActionReplayError(
                f"Échec moteur {dossier['dossier_id']}/{seed_plan['seed']}/{arm_id}: "
                f"code {getattr(completed, 'returncode', '?')}"
            )
    validated = prevalidated or validate_run_arm(
        dossier=dossier,
        seed_plan=seed_plan,
        arm_id=arm_id,
        arm=arm,
    )
    evidence = _signed(
        {
            "schema_version": CASE_SCHEMA_VERSION,
            "created_at_utc": utc_now(),
            "plan_signature": plan["plan_signature"],
            "campaign_signature": plan["campaign_signature"],
            "dossier_id": dossier["dossier_id"],
            "seed": seed_plan["seed"],
            "arm_id": arm_id,
            "action_id": str(arm.get("action_id") or ""),
            "command_sha256": arm["command_sha256"],
            "status": "valid",
            **validated,
        },
        "evidence_signature",
    )
    _write_json_atomic(evidence_path, evidence)
    return evidence


def run_action_replay(
    root: Path,
    *,
    execute: bool = False,
    workers: int = 1,
    executor: Executor | None = None,
) -> dict[str, Any]:
    """Resume validated arms; launch the engine only when ``execute`` is true."""

    root = root.resolve()
    if not 1 <= workers <= 4:
        raise ActionReplayError("workers doit être compris entre 1 et 4")
    plan = load_and_validate_plan(root)
    jobs = [
        (dossier, seed_plan, arm_id, arm)
        for dossier in plan.get("dossiers") or []
        for seed_plan in dossier.get("seed_plans") or []
        for arm_id, arm in (seed_plan.get("arms") or {}).items()
    ]
    receipt_path = root / "action_replay_run_receipt.json"
    if receipt_path.is_file():
        previous = _read_json(receipt_path)
        _verify_signed(previous, "run_signature", "reçu d'exécution")
        if previous.get("plan_signature") != plan.get("plan_signature") or previous.get(
            "campaign_signature"
        ) != plan.get("campaign_signature"):
            raise ActionReplayError("Le reçu existant n'appartient pas à ce plan")
        if previous.get("status") in {
            "complete_validated",
            "complete_no_representable_action",
        }:
            expected_keys = {
                (str(dossier["dossier_id"]), int(seed_plan["seed"]), str(arm_id))
                for dossier, seed_plan, arm_id, _arm in jobs
            }
            result_keys = {
                (
                    str(row.get("dossier_id") or ""),
                    int(row.get("seed")),
                    str(row.get("arm_id") or ""),
                )
                for row in previous.get("results") or []
            }
            if expected_keys != result_keys:
                raise ActionReplayError(
                    "Le reçu terminal ne couvre pas exactement les bras actions"
                )
            if (
                _int(
                    previous.get("reference_engine_rerun_count"),
                    label="reruns référence du reçu",
                )
                != 0
            ):
                raise ActionReplayError(
                    "Le reçu terminal contient un rerun baseline/incident"
                )
            for dossier, seed_plan, arm_id, arm in jobs:
                _run_one(
                    root=root,
                    plan=plan,
                    dossier=dossier,
                    seed_plan=seed_plan,
                    arm_id=arm_id,
                    arm=arm,
                    execute=False,
                    executor=None,
                )
            return previous
    results: list[dict[str, Any]] = []
    if workers == 1 or not execute:
        for dossier, seed_plan, arm_id, arm in jobs:
            results.append(
                _run_one(
                    root=root,
                    plan=plan,
                    dossier=dossier,
                    seed_plan=seed_plan,
                    arm_id=arm_id,
                    arm=arm,
                    execute=execute,
                    executor=executor,
                )
            )
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    _run_one,
                    root=root,
                    plan=plan,
                    dossier=dossier,
                    seed_plan=seed_plan,
                    arm_id=arm_id,
                    arm=arm,
                    execute=execute,
                    executor=executor,
                )
                for dossier, seed_plan, arm_id, arm in jobs
            ]
            for future in as_completed(futures):
                results.append(future.result())
    results.sort(
        key=lambda row: (str(row["dossier_id"]), int(row["seed"]), str(row["arm_id"]))
    )
    complete = all(row.get("status") == "valid" for row in results)
    planned_action_arm_count = sum(
        bool(str(row.get("action_id") or "")) for _, _, _, row in jobs
    )
    status = (
        "complete_no_representable_action"
        if planned_action_arm_count == 0
        else "complete_validated"
        if complete
        else "validated_not_executed"
    )
    receipt = _signed(
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "updated_at_utc": utc_now(),
            "plan_signature": plan["plan_signature"],
            "campaign_signature": plan["campaign_signature"],
            "status": status,
            "execute_requested": execute,
            "planned_arm_count": len(jobs),
            "planned_action_arm_count": planned_action_arm_count,
            "reference_engine_rerun_count": 0,
            "executed_action_arm_count": sum(
                row.get("status") == "valid" for row in results
            ),
            "valid_arm_count": sum(row.get("status") == "valid" for row in results),
            "pending_arm_count": sum(
                row.get("status") == "planned_not_executed" for row in results
            ),
            "results": results,
        },
        "run_signature",
    )
    _write_json_atomic(root / "action_replay_run_receipt.json", receipt)
    return receipt


def _daily_state(
    run_dir: Path, *, dossier: Mapping[str, Any], seed_plan: Mapping[str, Any]
) -> dict[str, Any]:
    files = _run_files(run_dir)
    horizon = _int(seed_plan["horizon_days"], label="horizon")
    priority = dossier["priority"]
    destination = str(priority["dst_node_id"])
    component = str(priority["item_id"])
    product = str(priority["target_product_id"]).replace("item:", "")

    result: dict[str, Any] = {
        "demand": {day: 0.0 for day in range(horizon)},
        "served_on_due": {day: 0.0 for day in range(horizon)},
        "backlog": {day: 0.0 for day in range(horizon)},
        "global_backlog": {day: 0.0 for day in range(horizon)},
        "production_released": {day: 0.0 for day in range(horizon)},
        "component_stock": {day: 0.0 for day in range(horizon)},
    }
    demand_seen: set[int] = set()
    all_demand_rows = _read_csv(files["demand"])
    for row in all_demand_rows:
        global_day = _int(row.get("day"), label="jour demande global")
        if global_day in result["global_backlog"]:
            result["global_backlog"][global_day] += max(
                0.0,
                _float(row.get("backlog_end_qty"), label="retard global", default=0.0),
            )
        if (
            str(row.get("node_id") or "") != CLIENT_NODE_ID
            or str(row.get("item_id") or "").replace("item:", "") != product
        ):
            continue
        day = _int(row.get("day"), label="jour demande")
        if day not in result["demand"] or day in demand_seen:
            raise ActionReplayError("Série de demande cible dupliquée ou hors horizon")
        demand_seen.add(day)
        demand = max(0.0, _float(row.get("demand_qty"), label="demande", default=0.0))
        served = max(0.0, _float(row.get("served_qty"), label="servi", default=0.0))
        required = max(
            demand,
            _float(
                row.get("required_with_backlog_qty"),
                label="besoin avec retard",
                default=demand,
            ),
        )
        starting_backlog = max(0.0, required - demand)
        result["demand"][day] = demand
        result["served_on_due"][day] = min(demand, max(0.0, served - starting_backlog))
        result["backlog"][day] = max(
            0.0, _float(row.get("backlog_end_qty"), label="retard", default=0.0)
        )
    if demand_seen != set(range(horizon)):
        raise ActionReplayError("La demande cible ne couvre pas tout l'horizon")

    production_seen: set[int] = set()
    for row in _read_csv(files["production"]):
        if (
            str(row.get("node_id") or "") != destination
            or str(row.get("item_id") or "").replace("item:", "") != product
        ):
            continue
        day = _int(row.get("day"), label="jour production")
        if day not in result["production_released"] or day in production_seen:
            raise ActionReplayError(
                "Série de production cible dupliquée ou hors horizon"
            )
        production_seen.add(day)
        result["production_released"][day] = max(
            0.0,
            _float(row.get("released_qty"), label="production libérée", default=0.0),
        )
    if production_seen != set(range(horizon)):
        raise ActionReplayError("La production cible ne couvre pas tout l'horizon")

    stock_seen: set[int] = set()
    for row in _read_csv(files["stocks"]):
        if (
            str(row.get("node_id") or "") != destination
            or str(row.get("item_id") or "") != component
        ):
            continue
        day = _int(row.get("day"), label="jour stock")
        if day not in result["component_stock"] or day in stock_seen:
            raise ActionReplayError("Série de stock cible dupliquée ou hors horizon")
        stock_seen.add(day)
        result["component_stock"][day] = max(
            0.0,
            _float(row.get("stock_end_of_day"), label="stock composant", default=0.0),
        )
    if stock_seen != set(range(horizon)):
        raise ActionReplayError("Le stock composant ne couvre pas tout l'horizon")

    nervousness_rows = [
        row
        for row in _read_csv(files["nervousness"])
        if str(row.get("node_id") or "") == destination
        and str(row.get("output_item_id") or "").replace("item:", "") == product
    ]
    if len(nervousness_rows) != 1:
        raise ActionReplayError("Diagnostic de nervosité cible absent ou dupliqué")
    nervousness = nervousness_rows[0]
    result["nervousness"] = {
        "actual_churn_ratio": _optional_float(
            nervousness.get("actual_churn_ratio"), label="nervosité"
        ),
        "production_start_count": _optional_float(
            nervousness.get("production_start_count"),
            label="démarrages production",
        ),
        "production_stop_count": _optional_float(
            nervousness.get("production_stop_count"),
            label="arrêts production",
        ),
        "delay_day_count": _optional_float(
            nervousness.get("delay_day_count"),
            label="jours de report production",
        ),
        "nervousness_level": str(nervousness.get("nervousness_level") or ""),
    }
    summary = _read_json(files["summary"])
    kpis = summary.get("kpis") or {}
    result["model_costs"] = {
        name: _optional_float(kpis.get(name), label=name)
        for name in (
            "total_cost",
            "total_transport_cost",
            "total_holding_cost",
            "total_warehouse_operating_cost",
            "total_inventory_risk_cost",
            "total_purchase_cost",
            "total_production_cost",
        )
    }
    return result


def _demand_signature(state: Mapping[str, Any]) -> str:
    return stable_sha256(
        [[day, value] for day, value in sorted(state["demand"].items())]
    )


def _reach_day(
    series: Mapping[int, float], start: int, end: int, target: float
) -> int | None:
    cumulative = 0.0
    for day in range(start, end + 1):
        cumulative += float(series.get(day, 0.0))
        if cumulative + EPS >= target:
            return day
    return None


def _backlog_recovery_day(
    series: Mapping[int, float],
    baseline: Mapping[int, float],
    *,
    start: int,
    end: int,
) -> int | None:
    # Seven days of evidence are required, followed by no relapse to the end.
    for day in range(start, end - 5):
        if all(
            float(series.get(probe, 0.0)) <= float(baseline.get(probe, 0.0)) + 1e-6
            for probe in range(day, end + 1)
        ):
            return day
    return None


def _absolute_metrics(
    state: Mapping[str, Any],
    *,
    baseline: Mapping[str, Any] | None,
    seed_plan: Mapping[str, Any],
) -> dict[str, Any]:
    start = _int(seed_plan["impact_window_start_day"], label="début impact")
    end = _int(seed_plan["impact_window_end_day"], label="fin impact")
    horizon = _int(seed_plan["horizon_days"], label="horizon")
    state_evaluation_days = _int(
        seed_plan["state_evaluation_days"], label="fenêtre d'état"
    )
    if (
        not 0 <= start <= end < horizon
        or end >= EXPECTED_STATE_WINDOW_DAYS
        or end - start + 1 != EXPECTED_IMPACT_WINDOW_DAYS
    ):
        raise ActionReplayError("Fenêtre d'impact KPI différente des 360 jours signés")
    if (
        state_evaluation_days != EXPECTED_STATE_WINDOW_DAYS
        or state_evaluation_days > horizon
    ):
        raise ActionReplayError("Fenêtre d'état KPI différente de J0–J719")
    days = range(start, end + 1)
    state_days = range(state_evaluation_days)
    demand = sum(state["demand"][day] for day in days)
    on_due = sum(state["served_on_due"][day] for day in days)
    backlog_days = sum(state["backlog"][day] for day in days)
    production = sum(state["production_released"][day] for day in days)
    stocks = [state["component_stock"][day] for day in days]
    baseline_production = (
        sum(baseline["production_released"][day] for day in days)
        if baseline is not None
        else None
    )
    threshold_90 = (
        0.9 * baseline_production if baseline_production is not None else None
    )
    reach_90 = (
        _reach_day(state["production_released"], start, end, threshold_90)
        if threshold_90 is not None and threshold_90 > EPS
        else None
    )
    baseline_reach_90 = (
        _reach_day(baseline["production_released"], start, end, threshold_90)
        if baseline is not None and threshold_90 is not None and threshold_90 > EPS
        else None
    )
    recovery_start = max(
        start, _int(seed_plan["risk_end_day"], label="fin incident") + 1
    )
    return {
        "impact_window_start_day": start,
        "impact_window_end_day": end,
        "demand_qty": demand,
        "served_on_due_qty": on_due,
        "service_on_due_pct": 100.0 * on_due / demand if demand > EPS else 100.0,
        "backlog_qty_days": backlog_days,
        "max_backlog_qty": max((state["backlog"][day] for day in days), default=0.0),
        "production_released_qty": production,
        "state_window_days": state_evaluation_days,
        "state_window_demand_qty": sum(state["demand"][day] for day in state_days),
        "state_window_served_on_due_qty": sum(
            state["served_on_due"][day] for day in state_days
        ),
        "state_window_service_on_due_pct": (
            100.0
            * sum(state["served_on_due"][day] for day in state_days)
            / sum(state["demand"][day] for day in state_days)
            if sum(state["demand"][day] for day in state_days) > EPS
            else 100.0
        ),
        "state_window_global_backlog_qty_days": sum(
            state["global_backlog"][day] for day in state_days
        ),
        "state_window_global_max_backlog_qty": max(
            (state["global_backlog"][day] for day in state_days), default=0.0
        ),
        "state_window_production_released_qty": sum(
            state["production_released"][day] for day in state_days
        ),
        "component_stock_average_qty": statistics.fmean(stocks) if stocks else 0.0,
        "component_stock_minimum_qty": min(stocks, default=0.0),
        "production_90pct_baseline_volume_threshold_qty": threshold_90,
        "production_90pct_baseline_volume_reach_day": reach_90,
        "production_90pct_baseline_volume_lag_days": (
            reach_90 - baseline_reach_90
            if reach_90 is not None and baseline_reach_90 is not None
            else None
        ),
        "backlog_recovery_day_vs_baseline": (
            _backlog_recovery_day(
                state["backlog"], baseline["backlog"], start=recovery_start, end=end
            )
            if baseline is not None
            else None
        ),
        **{f"nervousness_{key}": value for key, value in state["nervousness"].items()},
        **{f"model_{key}": value for key, value in state["model_costs"].items()},
    }


def _gain_metrics(
    incident: Mapping[str, Any], action: Mapping[str, Any]
) -> dict[str, float | None]:
    incident_lag = incident["production_90pct_baseline_volume_lag_days"]
    action_lag = action["production_90pct_baseline_volume_lag_days"]
    incident_recovery = incident["backlog_recovery_day_vs_baseline"]
    action_recovery = action["backlog_recovery_day_vs_baseline"]
    return {
        "service_gain_pp": float(action["service_on_due_pct"])
        - float(incident["service_on_due_pct"]),
        "backlog_qty_days_avoided": float(incident["backlog_qty_days"])
        - float(action["backlog_qty_days"]),
        "max_backlog_qty_avoided": float(incident["max_backlog_qty"])
        - float(action["max_backlog_qty"]),
        "production_released_gain_qty": float(action["production_released_qty"])
        - float(incident["production_released_qty"]),
        "component_stock_average_gain_qty": float(action["component_stock_average_qty"])
        - float(incident["component_stock_average_qty"]),
        "component_stock_minimum_gain_qty": float(action["component_stock_minimum_qty"])
        - float(incident["component_stock_minimum_qty"]),
        "nervousness_actual_churn_reduction": float(
            incident["nervousness_actual_churn_ratio"]
        )
        - float(action["nervousness_actual_churn_ratio"]),
        "production_start_count_reduction": float(
            incident["nervousness_production_start_count"]
        )
        - float(action["nervousness_production_start_count"]),
        "production_delay_days_avoided": float(incident["nervousness_delay_day_count"])
        - float(action["nervousness_delay_day_count"]),
        "days_recovered_at_90pct_baseline_volume": (
            float(incident_lag) - float(action_lag)
            if incident_lag is not None and action_lag is not None
            else None
        ),
        "backlog_recovery_days_gained": (
            float(incident_recovery) - float(action_recovery)
            if incident_recovery is not None and action_recovery is not None
            else None
        ),
        "model_total_cost_delta": float(action["model_total_cost"])
        - float(incident["model_total_cost"]),
        "model_transport_cost_delta": float(action["model_total_transport_cost"])
        - float(incident["model_total_transport_cost"]),
        "model_holding_cost_delta": float(action["model_total_holding_cost"])
        - float(incident["model_total_holding_cost"]),
        "model_warehouse_operating_cost_delta": float(
            action["model_total_warehouse_operating_cost"]
        )
        - float(incident["model_total_warehouse_operating_cost"]),
        "model_inventory_risk_cost_delta": float(
            action["model_total_inventory_risk_cost"]
        )
        - float(incident["model_total_inventory_risk_cost"]),
        "model_purchase_cost_delta": float(action["model_total_purchase_cost"])
        - float(incident["model_total_purchase_cost"]),
        "model_production_cost_delta": float(action["model_total_production_cost"])
        - float(incident["model_total_production_cost"]),
    }


def _signed_reference_metrics(
    *, dossier: Mapping[str, Any], seed_plan: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project only metrics genuinely present in the signed V4 rows."""

    reference = seed_plan.get("signed_reference")
    if not isinstance(reference, Mapping) or reference.get("reference_mode") != (
        "signed_campaign_metrics_no_engine_rerun"
    ):
        raise ActionReplayError("Référence signée de campagne absente")
    baseline_row = reference.get("baseline")
    incident_row = reference.get("incident_no_action")
    if not isinstance(baseline_row, Mapping) or not isinstance(incident_row, Mapping):
        raise ActionReplayError("Lignes signées baseline/incident absentes")
    product = str(dossier["priority"]["target_product_id"]).replace("item:", "")
    if product not in {"268091", "268967"}:
        raise ActionReplayError(f"Produit cible V4 inattendu: {product}")
    baseline = {
        "source": "signed_v4_campaign_metric",
        "case_key": str(baseline_row.get("case_key") or ""),
        "case_signature": str(baseline_row.get("case_signature") or ""),
        "seed": _int(baseline_row.get("seed"), label="graine baseline signée"),
        "impact_window_service_on_due_pct": _float(
            incident_row.get(f"baseline_impact_service_{product}_pct"),
            label="service baseline fenêtre impact",
        ),
        "impact_window_demand_qty": _float(
            incident_row.get(f"baseline_impact_demand_{product}_qty"),
            label="demande baseline fenêtre impact",
        ),
        "state_window_days": _int(
            baseline_row.get("state_evaluation_days"),
            label="fenêtre d'état baseline",
        ),
        "state_window_service_on_due_pct": _optional_float(
            baseline_row.get(f"service_output_product_{product}_pct"),
            label="service baseline fenêtre d'état",
        ),
        "state_window_global_backlog_qty_days": _optional_float(
            baseline_row.get("backlog_qty_days"),
            label="retard baseline fenêtre d'état",
        ),
        "state_window_global_max_backlog_qty": _optional_float(
            baseline_row.get("max_backlog_qty"),
            label="retard max baseline",
        ),
        "state_window_production_released_qty": _optional_float(
            baseline_row.get(f"production_released_{product}_qty"),
            label="production baseline fenêtre d'état",
        ),
        "stock_comparator_available": False,
        "nervousness_comparator_available": False,
        "daily_recovery_curve_available": False,
    }
    incident = {
        "source": "signed_v4_campaign_metric",
        "case_key": str(incident_row.get("case_key") or ""),
        "case_signature": str(incident_row.get("case_signature") or ""),
        "seed": _int(incident_row.get("seed"), label="graine incident signée"),
        "impact_window_service_on_due_pct": _float(
            incident_row.get(f"impact_service_{product}_pct"),
            label="service incident fenêtre impact",
        ),
        "impact_window_demand_qty": _float(
            incident_row.get(f"impact_demand_{product}_qty"),
            label="demande incident fenêtre impact",
        ),
        "state_window_days": _int(
            incident_row.get("state_evaluation_days"),
            label="fenêtre d'état incident",
        ),
        "state_window_service_on_due_pct": _float(
            incident_row.get(f"service_output_product_{product}_pct"),
            label="service incident fenêtre d'état",
        ),
        "state_window_global_backlog_qty_days": _optional_float(
            incident_row.get("backlog_qty_days"),
            label="retard incident fenêtre d'état",
        ),
        "state_window_global_max_backlog_qty": _optional_float(
            incident_row.get("max_backlog_qty"),
            label="retard max incident",
        ),
        "state_window_production_released_qty": _optional_float(
            incident_row.get(f"production_released_{product}_qty"),
            label="production incident fenêtre d'état",
        ),
        "model_total_cost": _optional_float(
            incident_row.get("total_cost"), label="coût total incident"
        ),
        "model_total_transport_cost": _optional_float(
            incident_row.get("total_transport_cost"),
            label="coût transport incident",
        ),
        "model_total_purchase_cost": _optional_float(
            incident_row.get("total_purchase_cost"),
            label="coût achat incident",
        ),
        "stock_comparator_available": False,
        "nervousness_comparator_available": False,
        "daily_recovery_curve_available": False,
    }
    if baseline["seed"] != incident["seed"] or incident["seed"] != _int(
        seed_plan["seed"], label="graine plan"
    ):
        raise ActionReplayError("Références signées non appariées par graine")
    if baseline["state_window_days"] != incident["state_window_days"] or incident[
        "state_window_days"
    ] != _int(seed_plan["state_evaluation_days"], label="fenêtre d'état planifiée"):
        raise ActionReplayError("La fenêtre d'état de la référence signée diffère")
    if not math.isclose(
        baseline["impact_window_demand_qty"],
        incident["impact_window_demand_qty"],
        rel_tol=1e-12,
        abs_tol=1e-6,
    ):
        raise ActionReplayError("La demande signée diffère entre baseline et incident")
    return baseline, incident


def _signed_action_gains(
    incident: Mapping[str, Any], action: Mapping[str, Any]
) -> dict[str, float | None]:
    """Compare action output to the identical signed no-action incident."""

    def difference(
        action_field: str, incident_field: str, *, reverse: bool = False
    ) -> float | None:
        action_value = action.get(action_field)
        incident_value = incident.get(incident_field)
        if action_value is None or incident_value is None:
            return None
        if reverse:
            return float(incident_value) - float(action_value)
        return float(action_value) - float(incident_value)

    return {
        "service_gain_pp": float(action["service_on_due_pct"])
        - float(incident["impact_window_service_on_due_pct"]),
        "state_window_service_gain_pp": float(action["state_window_service_on_due_pct"])
        - float(incident["state_window_service_on_due_pct"]),
        "backlog_qty_days_avoided": difference(
            "state_window_global_backlog_qty_days",
            "state_window_global_backlog_qty_days",
            reverse=True,
        ),
        "max_backlog_qty_avoided": difference(
            "state_window_global_max_backlog_qty",
            "state_window_global_max_backlog_qty",
            reverse=True,
        ),
        "production_released_gain_qty": difference(
            "state_window_production_released_qty",
            "state_window_production_released_qty",
        ),
        # The campaign compact evidence does not retain the matching daily
        # stock, nervousness or recovery curves.  Do not manufacture deltas.
        "component_stock_average_gain_qty": None,
        "component_stock_minimum_gain_qty": None,
        "nervousness_actual_churn_reduction": None,
        "production_start_count_reduction": None,
        "production_delay_days_avoided": None,
        "days_recovered_at_90pct_baseline_volume": None,
        "backlog_recovery_days_gained": None,
        "model_total_cost_delta": difference("model_total_cost", "model_total_cost"),
        "model_transport_cost_delta": difference(
            "model_total_transport_cost", "model_total_transport_cost"
        ),
        "model_purchase_cost_delta": difference(
            "model_total_purchase_cost", "model_total_purchase_cost"
        ),
        "model_holding_cost_delta": None,
        "model_warehouse_operating_cost_delta": None,
        "model_inventory_risk_cost_delta": None,
        "model_production_cost_delta": None,
    }


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ActionReplayError("Quantile demandé sur une série vide")
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _metric_summary(
    values: Sequence[float], *, bootstrap_replicates: int, bootstrap_seed: int
) -> dict[str, Any]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p10": None,
            "p90": None,
            "mean_ci95_low": None,
            "mean_ci95_high": None,
        }
    rng = random.Random(bootstrap_seed)
    means = [
        statistics.fmean(rng.choice(clean) for _ in clean)
        for _ in range(bootstrap_replicates)
    ]
    return {
        "count": len(clean),
        "mean": statistics.fmean(clean),
        "median": statistics.median(clean),
        "p10": _quantile(clean, 0.10),
        "p90": _quantile(clean, 0.90),
        "mean_ci95_low": _quantile(means, 0.025),
        "mean_ci95_high": _quantile(means, 0.975),
    }


def _arm_evidence(
    root: Path, dossier_id: str, seed: int, arm_id: str
) -> dict[str, Any]:
    path = root / "case_evidence" / dossier_id / f"seed_{seed}" / f"{arm_id}.json"
    evidence = _read_json(path)
    _verify_signed(evidence, "evidence_signature", "preuve de bras")
    if evidence.get("status") != "valid":
        raise ActionReplayError("Un bras n'est pas validé")
    return evidence


def _flatten_per_seed_row(
    *,
    dossier: Mapping[str, Any],
    seed: int,
    action_id: str,
    application: Mapping[str, Any],
    lead_effect: Mapping[str, Any] | None,
    baseline: Mapping[str, Any],
    incident: Mapping[str, Any],
    action: Mapping[str, Any],
    gains: Mapping[str, Any],
    included: bool,
    exclusion_reason: str,
) -> dict[str, Any]:
    priority = dossier["priority"]
    row: dict[str, Any] = {
        "dossier_id": dossier["dossier_id"],
        "operating_point_id": priority["operating_point_id"],
        "mechanism": priority["mechanism"],
        "lane_id": priority["lane_id"],
        "supplier_id": priority["supplier_id"],
        "item_id": priority["item_id"],
        "dst_node_id": priority["dst_node_id"],
        "target_product_id": priority["target_product_id"],
        "client_scope": CLIENT_NODE_ID,
        "seed": seed,
        "action_id": action_id,
        "action_physically_exercised": application["physically_exercised"],
        "included_in_action_gain_statistics": included,
        "exclusion_reason": exclusion_reason,
        "executed_control_quantity": application.get("executed_quantity", 0.0),
        "executed_control_uom": application.get("quantity_uom", ""),
        "stock_before_j0_qty": application.get("stock_before_j0_qty", ""),
        "stock_after_j0_qty": application.get("stock_after_j0_qty", ""),
        "stock_scale": application.get("stock_scale", ""),
        "stock_base_semantics": application.get("stock_base_semantics", ""),
        "quantity_shifted_away_from_incident_lane": application.get(
            "quantity_shifted_away_from_incident_lane", ""
        ),
        "eligible_alternative_supplier_ids": ";".join(
            application.get("eligible_alternative_supplier_ids") or []
        ),
        "lead_effect_bounded": (lead_effect or {}).get("bounded_effect_proven", ""),
        "lead_reduction_days_max_observed": (lead_effect or {}).get(
            "maximum_observed_lead_reduction_days", ""
        ),
    }
    for prefix, values in (
        ("baseline", baseline),
        ("incident_no_action", incident),
        ("incident_with_action", action),
        ("action_vs_incident", gains),
    ):
        for key, value in values.items():
            row[f"{prefix}__{key}"] = "" if value is None else value
    return row


def finalize_action_replay(
    root: Path,
    *,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if bootstrap_replicates < 1_000:
        raise ActionReplayError("Au moins 1000 réplications bootstrap sont requises")
    root = root.resolve()
    validation_path = root / "action_replay_validation.json"
    if validation_path.is_file():
        existing_summary, existing_validation = validate_action_results(root)
        if existing_summary.get("bootstrap") != {
            "replicates": bootstrap_replicates,
            "seed": bootstrap_seed,
            "interval": "percentile_95_on_paired_seed_mean",
            "historical_probability": False,
        }:
            raise ActionReplayError(
                "La finalisation existante utilise d'autres paramètres bootstrap"
            )
        return existing_summary, existing_validation
    plan = load_and_validate_plan(root)
    receipt_path = root / "action_replay_run_receipt.json"
    receipt = _read_json(receipt_path)
    _verify_signed(receipt, "run_signature", "reçu d'exécution")
    if receipt.get("plan_signature") != plan.get("plan_signature"):
        raise ActionReplayError("Reçu d'exécution non lié au plan")
    if (
        _int(
            receipt.get("reference_engine_rerun_count"),
            label="reruns de référence",
        )
        != 0
    ):
        raise ActionReplayError("Le reçu annonce un rerun baseline/incident interdit")
    expected_receipt_keys = {
        (str(dossier["dossier_id"]), int(seed_plan["seed"]), str(action_id))
        for dossier in plan.get("dossiers") or []
        for seed_plan in dossier.get("seed_plans") or []
        for action_id in (seed_plan.get("arms") or {})
    }
    receipt_by_key = {
        (
            str(row.get("dossier_id") or ""),
            _int(row.get("seed"), label="graine reçue"),
            str(row.get("arm_id") or ""),
        ): row
        for row in receipt.get("results") or []
    }
    if set(receipt_by_key) != expected_receipt_keys:
        raise ActionReplayError(
            "Le reçu ne couvre pas exactement les bras actions planifiés"
        )

    has_eligible_actions = any(
        dossier.get("eligible_action_ids") for dossier in plan.get("dossiers") or []
    )
    if not has_eligible_actions:
        if receipt.get("status") != "complete_no_representable_action":
            raise ActionReplayError("Le statut zéro action est incohérent")
        per_seed_rows: list[dict[str, Any]] = []
        action_summaries: list[dict[str, Any]] = []
    else:
        if receipt.get("status") != "complete_validated":
            raise ActionReplayError("Tous les bras doivent être exécutés et validés")
        per_seed_rows = []
        action_summaries = []
        for dossier in plan["dossiers"]:
            priority = dossier["priority"]
            for action_id in dossier["eligible_action_ids"]:
                action_definition = next(
                    action
                    for action in dossier["action_catalog"]
                    if action["action_id"] == action_id
                )
                action_rows: list[dict[str, Any]] = []
                for seed_plan in dossier["seed_plans"]:
                    seed = _int(seed_plan["seed"], label="graine")
                    arm_evidence = _arm_evidence(
                        root, dossier["dossier_id"], seed, action_id
                    )
                    if (
                        arm_evidence
                        != receipt_by_key[(str(dossier["dossier_id"]), seed, action_id)]
                    ):
                        raise ActionReplayError(
                            "La preuve de bras diffère de celle signée dans le reçu"
                        )
                    action_state = _daily_state(
                        Path(seed_plan["arms"][action_id]["run_dir"]),
                        dossier=dossier,
                        seed_plan=seed_plan,
                    )
                    baseline_metrics, incident_metrics = _signed_reference_metrics(
                        dossier=dossier, seed_plan=seed_plan
                    )
                    action_metrics = _absolute_metrics(
                        action_state, baseline=None, seed_plan=seed_plan
                    )
                    if not math.isclose(
                        action_metrics["demand_qty"],
                        incident_metrics["impact_window_demand_qty"],
                        rel_tol=1e-12,
                        abs_tol=1e-6,
                    ):
                        raise ActionReplayError(
                            "La demande du bras action diffère de l'incident signé"
                        )
                    application = arm_evidence["action_application"]
                    lead_effect: dict[str, Any] | None = None
                    included = bool(application["physically_exercised"])
                    exclusion_reason = (
                        ""
                        if included
                        else str(application.get("reason") or "non_exercised")
                    )
                    if action_id == ACTION_LEAD:
                        incident_evidence_path = Path(
                            str(seed_plan["incident_evidence_path"])
                        ).resolve()
                        if sha256_file(incident_evidence_path) != str(
                            seed_plan["incident_evidence_sha256"]
                        ):
                            raise ActionReplayError(
                                "La preuve signée de l'incident a changé"
                            )
                        signed_incident_evidence = _read_json(incident_evidence_path)
                        lot_replay_v4._verify_signed_payload(
                            signed_incident_evidence,
                            "evidence_signature",
                            "preuve incident V4",
                        )
                        incident_shipments = list(
                            (signed_incident_evidence.get("incident_proof") or {}).get(
                                "tagged_shipments"
                            )
                            or []
                        )
                        action_shipments = _read_csv(
                            _run_files(Path(seed_plan["arms"][action_id]["run_dir"]))[
                                "shipments"
                            ]
                        )
                        lead_effect = _lead_effect_evidence(
                            incident_shipments=incident_shipments,
                            action_shipments=action_shipments,
                            dossier=dossier,
                            seed_plan=seed_plan,
                        )
                        if included and not lead_effect["bounded_effect_proven"]:
                            included = False
                            exclusion_reason = (
                                "bounded_effect_not_proven_on_paired_departure"
                            )
                    gains = _signed_action_gains(incident_metrics, action_metrics)
                    row = _flatten_per_seed_row(
                        dossier=dossier,
                        seed=seed,
                        action_id=action_id,
                        application=application,
                        lead_effect=lead_effect,
                        baseline=baseline_metrics,
                        incident=incident_metrics,
                        action=action_metrics,
                        gains=gains,
                        included=included,
                        exclusion_reason=exclusion_reason,
                    )
                    per_seed_rows.append(row)
                    action_rows.append(row)

                exercised_rows = [
                    row
                    for row in action_rows
                    if _truthy(row["included_in_action_gain_statistics"])
                ]
                gain_fields = sorted(
                    {
                        field.removeprefix("action_vs_incident__")
                        for row in exercised_rows
                        for field, value in row.items()
                        if field.startswith("action_vs_incident__")
                        and str(value).strip() != ""
                    }
                )
                metric_summaries = {}
                for metric in gain_fields:
                    values = [
                        _float(
                            row[f"action_vs_incident__{metric}"], label=f"gain {metric}"
                        )
                        for row in exercised_rows
                        if str(row.get(f"action_vs_incident__{metric}") or "").strip()
                    ]
                    salt = int(
                        stable_sha256([dossier["dossier_id"], action_id, metric])[:8],
                        16,
                    )
                    metric_summaries[metric] = _metric_summary(
                        values,
                        bootstrap_replicates=bootstrap_replicates,
                        bootstrap_seed=bootstrap_seed ^ salt,
                    )
                action_summaries.append(
                    {
                        "dossier_id": dossier["dossier_id"],
                        "operating_point_id": priority["operating_point_id"],
                        "mechanism": priority["mechanism"],
                        "lane_id": priority["lane_id"],
                        "supplier_id": priority["supplier_id"],
                        "item_id": priority["item_id"],
                        "dst_node_id": priority["dst_node_id"],
                        "target_product_id": priority["target_product_id"],
                        "client_scope": CLIENT_NODE_ID,
                        "action_id": action_id,
                        "action_label_fr": action_definition["label_fr"],
                        "action_parameters": action_definition["parameters"],
                        "action_parameter_units": action_definition["parameter_units"],
                        "action_physical_scope": action_definition["physical_scope"],
                        "status": (
                            "estimated_on_physically_exercised_seeds"
                            if exercised_rows
                            else "non_exercised_no_gain_estimate"
                        ),
                        "paired_seed_count": len(action_rows),
                        "paired_seeds": [int(row["seed"]) for row in action_rows],
                        "physically_exercised_seed_count": len(exercised_rows),
                        "non_exercised_seed_count": len(action_rows)
                        - len(exercised_rows),
                        "gain_statistics_population": (
                            "physically_exercised_paired_seeds_only"
                        ),
                        "gain_statistics": metric_summaries,
                        "paired_arms": {
                            "without_incident": "signed_v4_campaign_reference",
                            "incident_without_action": "signed_v4_campaign_reference",
                            "incident_with_action": "executed_action_arm",
                            "reference_engine_rerun_count": 0,
                        },
                        "unavailable_comparators": [
                            "component_stock_delta",
                            "nervousness_delta",
                            "equal_volume_recovery_days",
                            "daily_reference_curves",
                        ],
                        "cost_interpretation": {
                            "model_cost_component_delta_reported": any(
                                name.startswith("model_")
                                and (stats.get("count") or 0) > 0
                                for name, stats in metric_summaries.items()
                            ),
                            "complete_intervention_cost": False,
                            "roi_calculable": False,
                            "missing": (
                                [
                                    "achat_et_qualification_du_stock_ajoute",
                                    "date_et_faisabilite_de_constitution",
                                ]
                                if action_id == ACTION_STOCK
                                else [
                                    "prime_contractuelle_de_reduction_de_delai",
                                    "capacite_transporteur_garantie",
                                ]
                                if action_id == ACTION_LEAD
                                else [
                                    "prix_contractuel_de_reallocation",
                                    "qualification_et_capacite_reelle_alternative",
                                ]
                            ),
                        },
                        "limits_fr": action_definition["limits_fr"],
                        "closed_loop": False,
                        "recommendation_claimed": False,
                    }
                )

    refusal_rows = [
        {
            "dossier_id": dossier["dossier_id"],
            "operating_point_id": dossier["priority"]["operating_point_id"],
            "mechanism": dossier["priority"]["mechanism"],
            "lane_id": dossier["priority"]["lane_id"],
            "supplier_id": dossier["priority"]["supplier_id"],
            "item_id": dossier["priority"]["item_id"],
            "dst_node_id": dossier["priority"]["dst_node_id"],
            "target_product_id": dossier["priority"]["target_product_id"],
            "action_id": action["action_id"],
            "label_fr": action["label_fr"],
            "status": "refused_not_simulated",
            "simulated": False,
            "refusal_reason": action["refusal_reason"],
            "limits_fr": action["limits_fr"],
        }
        for dossier in plan.get("dossiers") or []
        for action in dossier.get("action_catalog") or []
        if not action.get("eligible")
    ]
    application_rows = [
        {
            "dossier_id": row["dossier_id"],
            "seed": row["seed"],
            "action_id": row["action_id"],
            "physically_exercised": row["action_physically_exercised"],
            "status": (
                "exercised"
                if _truthy(row["action_physically_exercised"])
                else "non_exercised"
            ),
            "included_in_gain_statistics": row["included_in_action_gain_statistics"],
            "exclusion_reason": row["exclusion_reason"],
            "executed_quantity": row["executed_control_quantity"],
            "quantity_uom": row["executed_control_uom"],
            "stock_before_j0_qty": row["stock_before_j0_qty"],
            "stock_after_j0_qty": row["stock_after_j0_qty"],
            "stock_scale": row["stock_scale"],
            "stock_base_semantics": row["stock_base_semantics"],
            "quantity_shifted_away_from_incident_lane": row[
                "quantity_shifted_away_from_incident_lane"
            ],
            "eligible_alternative_supplier_ids": row[
                "eligible_alternative_supplier_ids"
            ],
            "lead_effect_bounded": row["lead_effect_bounded"],
            "lead_reduction_days_max_observed": row["lead_reduction_days_max_observed"],
        }
        for row in per_seed_rows
    ]
    per_seed_path = root / "action_replay_per_seed.csv"
    aggregate_path = root / "action_replay_aggregate.csv"
    refusals_path = root / "action_replay_refusals.csv"
    applications_path = root / "action_replay_application_ledger.csv"
    _write_csv_atomic(per_seed_path, per_seed_rows)
    aggregate_rows = []
    for action in action_summaries:
        base = {
            key: action[key]
            for key in (
                "dossier_id",
                "operating_point_id",
                "mechanism",
                "lane_id",
                "supplier_id",
                "item_id",
                "dst_node_id",
                "target_product_id",
                "action_id",
                "status",
                "paired_seed_count",
                "physically_exercised_seed_count",
                "non_exercised_seed_count",
            )
        }
        for metric, stats in action["gain_statistics"].items():
            aggregate_rows.append({**base, "metric": metric, **stats})
        if not action["gain_statistics"]:
            aggregate_rows.append(
                {
                    **base,
                    "metric": "no_gain_estimate",
                    "count": 0,
                    "mean": "",
                    "median": "",
                    "p10": "",
                    "p90": "",
                    "mean_ci95_low": "",
                    "mean_ci95_high": "",
                }
            )
    _write_csv_atomic(aggregate_path, aggregate_rows)
    _write_csv_atomic(refusals_path, refusal_rows)
    _write_csv_atomic(applications_path, application_rows)
    tabular_paths = (
        per_seed_path,
        aggregate_path,
        refusals_path,
        applications_path,
    )
    tabular_outputs = {
        path.name: {
            "path": str(path.resolve()),
            "sha256": sha256_file(path),
            "row_count": len(_read_csv(path)),
        }
        for path in tabular_paths
    }

    summary_status = (
        "complete_no_representable_action"
        if not has_eligible_actions
        else "complete_validated"
    )
    summary = _signed(
        {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "generated_at_utc": utc_now(),
            "status": summary_status,
            "campaign_signature": plan["campaign_signature"],
            "plan_signature": plan["plan_signature"],
            "run_signature": receipt["run_signature"],
            "source_inventory_signature": plan["source_inventory_signature"],
            "finalizer_selection_signature": plan["finalizer_selection_signature"],
            "lot_replay_binding": plan["lot_replay_binding"],
            "dossier_count": len(plan.get("dossiers") or []),
            "action_summary_count": len(action_summaries),
            "refused_action_count": len(refusal_rows),
            "per_seed_action_comparison_count": len(per_seed_rows),
            "reference_mode": "signed_reference",
            "reference_engine_rerun_count": 0,
            "executed_engine_arm_type": "incident_with_action_only",
            "measurement_windows": plan["measurement_windows"],
            "bootstrap": {
                "replicates": bootstrap_replicates,
                "seed": bootstrap_seed,
                "interval": "percentile_95_on_paired_seed_mean",
                "historical_probability": False,
            },
            "action_results": action_summaries,
            "refused_actions": refusal_rows,
            "interpretation_fr": (
                "Chaque action exécutée est comparée, graine par graine, aux lignes "
                "baseline et incident déjà signées par la campagne V4; ces deux "
                "références ne sont pas recalculées. Les moyennes annoncées excluent "
                "les graines où l'action n'a pas été physiquement exercée. Il s'agit "
                "d'hypothèses simulées en boucle ouverte, pas de performances "
                "fournisseurs observées."
            ),
            "unavailable_reference_curve_kpis": {
                "component_stock_delta": None,
                "nervousness_delta": None,
                "equal_volume_recovery_days": None,
                "reason": (
                    "les courbes quotidiennes baseline/incident ne sont pas stockées "
                    "dans les références compactes signées"
                ),
            },
            "cost_limits_fr": (
                "Les composantes de coût calculées par le moteur sont fournies, mais "
                "les coûts contractuels, d'acquisition et de qualification absents "
                "interdisent tout calcul de ROI."
            ),
            "outputs": tabular_outputs,
        },
        "summary_signature",
    )
    summary_path = root / "action_replay_summary.json"
    _write_json_atomic(summary_path, summary)
    outputs = {
        **tabular_outputs,
        summary_path.name: {
            "path": str(summary_path.resolve()),
            "sha256": sha256_file(summary_path),
            "row_count": 1,
        },
    }
    validation = _signed(
        {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "validated_at_utc": utc_now(),
            "status": summary_status,
            "campaign_signature": plan["campaign_signature"],
            "plan_signature": plan["plan_signature"],
            "run_signature": receipt["run_signature"],
            "summary_signature": summary["summary_signature"],
            "source_inventory_signature": plan["source_inventory_signature"],
            "finalizer_selection_signature": plan["finalizer_selection_signature"],
            "measurement_windows": plan["measurement_windows"],
            "checks": {
                "all_source_hashes_revalidated": True,
                "all_commands_revalidated": True,
                "all_planned_arms_validated": bool(
                    not has_eligible_actions
                    or receipt.get("status") == "complete_validated"
                ),
                "signed_reference_triplets_paired_by_seed": True,
                "reference_engine_rerun_count": 0,
                "only_incident_with_action_arms_executed": True,
                "demand_identical_within_each_triplet": True,
                "actions_kept_separate": True,
                "non_exercised_seeds_excluded_from_gain_statistics": True,
                "refused_actions_not_simulated": True,
                "state_dependent_risks_disabled": True,
                "quality_incident_or_action_absent": True,
                "capacity_or_availability_not_invented": True,
                "named_shipment_actuator_absent": True,
                "closed_loop_claimed": False,
                "complete_cost_or_roi_claimed": False,
                "unavailable_reference_curve_kpis_are_null": True,
            },
            "outputs": outputs,
        },
        "validation_signature",
    )
    validation_path = root / "action_replay_validation.json"
    _write_json_atomic(validation_path, validation)
    return summary, validation


def validate_action_results(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Public, fail-closed loader for the final standalone delivery."""

    root = root.resolve()
    plan = load_and_validate_plan(root)
    receipt = _read_json(root / "action_replay_run_receipt.json")
    _verify_signed(receipt, "run_signature", "reçu d'exécution")
    summary = _read_json(root / "action_replay_summary.json")
    validation = _read_json(root / "action_replay_validation.json")
    _verify_signed(summary, "summary_signature", "résumé d'actions")
    _verify_signed(validation, "validation_signature", "validation d'actions")
    if (
        receipt.get("schema_version") != RUN_SCHEMA_VERSION
        or summary.get("schema_version") != SUMMARY_SCHEMA_VERSION
        or validation.get("schema_version") != VALIDATION_SCHEMA_VERSION
    ):
        raise ActionReplayError("Schéma final d'actions inattendu")
    signatures = {
        "campaign_signature": plan["campaign_signature"],
        "plan_signature": plan["plan_signature"],
        "run_signature": receipt["run_signature"],
        "summary_signature": summary["summary_signature"],
        "source_inventory_signature": plan["source_inventory_signature"],
        "finalizer_selection_signature": plan["finalizer_selection_signature"],
    }
    for field, expected in signatures.items():
        if (
            summary.get(field, expected) != expected
            or validation.get(field) != expected
        ):
            raise ActionReplayError(f"Liaison de signature invalide: {field}")
    expected_windows = _measurement_windows(plan.get("dossiers") or [])
    if (
        summary.get("measurement_windows") != expected_windows
        or validation.get("measurement_windows") != expected_windows
    ):
        raise ActionReplayError("Fenêtres KPI finales absentes ou différentes du plan")
    allowed_statuses = {"complete_validated", "complete_no_representable_action"}
    if summary.get("status") not in allowed_statuses or validation.get(
        "status"
    ) != summary.get("status"):
        raise ActionReplayError("Statut final d'actions invalide")
    if receipt.get("status") != summary.get("status"):
        raise ActionReplayError("Le statut du reçu diffère du statut final")
    if (
        summary.get("reference_mode") != "signed_reference"
        or _int(
            summary.get("reference_engine_rerun_count"),
            label="reruns référence du résumé",
        )
        != 0
        or _int(
            receipt.get("reference_engine_rerun_count"),
            label="reruns référence du reçu",
        )
        != 0
    ):
        raise ActionReplayError("Un rerun baseline/incident est annoncé")
    expected_result_keys = {
        (str(dossier["dossier_id"]), int(seed_plan["seed"]), str(action_id))
        for dossier in plan.get("dossiers") or []
        for seed_plan in dossier.get("seed_plans") or []
        for action_id in (seed_plan.get("arms") or {})
    }
    receipt_results = receipt.get("results") or []
    actual_result_keys = {
        (
            str(row.get("dossier_id") or ""),
            _int(row.get("seed"), label="graine du reçu"),
            str(row.get("arm_id") or ""),
        )
        for row in receipt_results
    }
    if expected_result_keys != actual_result_keys or any(
        key[2] not in ALLOWED_ACTIONS for key in actual_result_keys
    ):
        raise ActionReplayError("Le reçu ne contient pas exactement les bras actions")
    for row in receipt_results:
        dossier_id = str(row["dossier_id"])
        seed = _int(row["seed"], label="graine du reçu")
        action_id = str(row["arm_id"])
        evidence_path = (
            root / "case_evidence" / dossier_id / f"seed_{seed}" / f"{action_id}.json"
        )
        evidence = _read_json(evidence_path)
        _verify_signed(evidence, "evidence_signature", "preuve action finale")
        if evidence != row:
            raise ActionReplayError("La preuve action diffère du reçu signé")
        for declaration in (evidence.get("files") or {}).values():
            path = Path(str(declaration.get("path") or "")).resolve()
            if (
                not path.is_relative_to(root)
                or not path.is_file()
                or sha256_file(path) != str(declaration.get("sha256") or "")
            ):
                raise ActionReplayError("Un résultat moteur lié à une action a changé")

    expected_checks = {
        "all_source_hashes_revalidated": True,
        "all_commands_revalidated": True,
        "all_planned_arms_validated": True,
        "signed_reference_triplets_paired_by_seed": True,
        "reference_engine_rerun_count": 0,
        "only_incident_with_action_arms_executed": True,
        "demand_identical_within_each_triplet": True,
        "actions_kept_separate": True,
        "non_exercised_seeds_excluded_from_gain_statistics": True,
        "refused_actions_not_simulated": True,
        "state_dependent_risks_disabled": True,
        "quality_incident_or_action_absent": True,
        "capacity_or_availability_not_invented": True,
        "named_shipment_actuator_absent": True,
        "closed_loop_claimed": False,
        "complete_cost_or_roi_claimed": False,
        "unavailable_reference_curve_kpis_are_null": True,
    }
    if validation.get("checks") != expected_checks:
        raise ActionReplayError("Les contrôles scientifiques finaux ont changé")
    allowed_pairs = {
        (str(dossier["dossier_id"]), str(action_id))
        for dossier in plan.get("dossiers") or []
        for action_id in dossier.get("eligible_action_ids") or []
    }
    action_results = summary.get("action_results") or []
    if (
        len(action_results) != len(allowed_pairs)
        or {
            (str(row.get("dossier_id") or ""), str(row.get("action_id") or ""))
            for row in action_results
        }
        != allowed_pairs
    ):
        raise ActionReplayError(
            "Le résumé ne couvre pas exactement les actions éligibles"
        )
    for result in action_results:
        if (
            result.get("status")
            not in {
                "estimated_on_physically_exercised_seeds",
                "non_exercised_no_gain_estimate",
            }
            or result.get("closed_loop") is not False
            or result.get("recommendation_claimed") is not False
            or (result.get("cost_interpretation") or {}).get("roi_calculable")
            is not False
            or (result.get("paired_arms") or {}).get("reference_engine_rerun_count")
            != 0
        ):
            raise ActionReplayError("Interprétation d'une action finale invalide")
    refused = summary.get("refused_actions") or []
    if any(
        row.get("status") != "refused_not_simulated"
        or row.get("simulated") is not False
        for row in refused
    ):
        raise ActionReplayError("Une action refusée est présentée comme simulée")
    expected_output_names = {
        "action_replay_per_seed.csv",
        "action_replay_aggregate.csv",
        "action_replay_refusals.csv",
        "action_replay_application_ledger.csv",
        "action_replay_summary.json",
    }
    if set(validation.get("outputs") or {}) != expected_output_names:
        raise ActionReplayError("Inventaire des sorties finales inattendu")
    if summary.get("outputs") != {
        name: declaration
        for name, declaration in validation["outputs"].items()
        if name != "action_replay_summary.json"
    }:
        raise ActionReplayError(
            "Inventaire tabulaire du résumé non lié à la validation"
        )
    for name, declaration in (validation.get("outputs") or {}).items():
        path = Path(str(declaration.get("path") or "")).resolve()
        if path.parent != root or path.name != name or not path.is_file():
            raise ActionReplayError(f"Sortie d'actions absente ou hors dossier: {name}")
        if sha256_file(path) != str(declaration.get("sha256") or ""):
            raise ActionReplayError(f"Sortie d'actions modifiée: {name}")
        if path.suffix.casefold() == ".csv" and len(_read_csv(path)) != _int(
            declaration.get("row_count"), label=f"nombre de lignes {name}"
        ):
            raise ActionReplayError(f"Nombre de lignes modifié: {name}")
    if sha256_file(root / "action_replay_summary.json") != str(
        validation["outputs"]["action_replay_summary.json"]["sha256"]
    ):
        raise ActionReplayError("Le résumé n'est pas celui lié par la validation")
    return summary, validation


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay additif des actions pilotables sur les dossiers V4."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    plan = subparsers.add_parser(
        "plan", help="Préparer et signer sans lancer le moteur"
    )
    plan.add_argument("--campaign-root", type=Path, required=True)
    plan.add_argument("--results-dir", type=Path, required=True)
    plan.add_argument("--output-root", type=Path, required=True)
    plan.add_argument("--lot-replay-root", type=Path)
    plan.add_argument("--max-dossiers", type=int, default=3)
    plan.add_argument("--stock-scale", type=float, default=DEFAULT_STOCK_SCALE)
    plan.add_argument(
        "--lead-reduction-days", type=int, default=DEFAULT_LEAD_REDUCTION_DAYS
    )
    plan.add_argument(
        "--target-priority-weight", type=float, default=DEFAULT_TARGET_PRIORITY_WEIGHT
    )
    plan.add_argument(
        "--reference-mode",
        choices=["signed_reference"],
        default="signed_reference",
        help="Réutilise baseline et incident signés; seuls les bras actions sont exécutés.",
    )
    plan.add_argument("--python-executable", default="")

    run = subparsers.add_parser(
        "run", help="Valider/reprendre, moteur seulement avec --execute"
    )
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument("--execute", action="store_true")
    run.add_argument("--workers", type=int, default=1)

    finalize = subparsers.add_parser(
        "finalize", help="Consolider les résultats appariés"
    )
    finalize.add_argument("--output-root", type=Path, required=True)
    finalize.add_argument(
        "--bootstrap-replicates", type=int, default=DEFAULT_BOOTSTRAP_REPLICATES
    )
    finalize.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)

    validate = subparsers.add_parser("validate", help="Revalider le paquet final")
    validate.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "plan":
        result = create_action_plan(
            campaign_root=args.campaign_root,
            results_dir=args.results_dir,
            output_root=args.output_root,
            max_dossiers=args.max_dossiers,
            stock_scale=args.stock_scale,
            lead_reduction_days=args.lead_reduction_days,
            target_priority_weight=args.target_priority_weight,
            python_executable=args.python_executable or None,
            lot_replay_root=args.lot_replay_root,
            reference_mode=args.reference_mode,
        )
        print(
            json.dumps(
                {"status": "planned", "plan_signature": result["plan_signature"]}
            )
        )
        return 0
    if args.mode == "run":
        result = run_action_replay(
            args.output_root, execute=args.execute, workers=args.workers
        )
        print(
            json.dumps(
                {"status": result["status"], "run_signature": result["run_signature"]}
            )
        )
        return 0
    if args.mode == "finalize":
        summary, validation = finalize_action_replay(
            args.output_root,
            bootstrap_replicates=args.bootstrap_replicates,
            bootstrap_seed=args.bootstrap_seed,
        )
        print(
            json.dumps(
                {
                    "status": validation["status"],
                    "summary_signature": summary["summary_signature"],
                    "validation_signature": validation["validation_signature"],
                }
            )
        )
        return 0
    summary, validation = validate_action_results(args.output_root)
    print(
        json.dumps(
            {
                "status": validation["status"],
                "action_summary_count": summary["action_summary_count"],
                "validation_signature": validation["validation_signature"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
