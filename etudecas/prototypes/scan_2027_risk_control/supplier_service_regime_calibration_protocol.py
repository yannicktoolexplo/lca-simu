#!/usr/bin/env python3
"""Prepare a fail-closed 93% / 80% service-regime calibration.

The protocol is additive: it writes new candidate inputs and a staged execution
plan, but never runs the simulation engine.  A later runner can execute a
one-seed screening, confirm the selected candidates on the first 15 seeds, then
add the remaining 15 seeds without recomputing the first block.

Each candidate changes exactly one structural family.  Acute supplier quality
or transport incidents are deliberately excluded: they belong to the incident
study performed *after* a service regime has been calibrated.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_PARENT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
DEFAULT_OUTPUT_DIR = (
    ARTIFACT_PARENT / "supplier_service_regime_calibration_plan_20260903_v2"
)
DEFAULT_REFERENCE_CAMPAIGN = (
    ARTIFACT_PARENT / "supplier_network_risk_screen_20260902_v2"
)
DEFAULT_LEGACY_COMBINED = (
    ARTIFACT_PARENT
    / "supplier_risk_influence_20260829_v1"
    / "calibration_probe"
    / "paired_replays_v2"
)
DEFAULT_LEGACY_STOCK = (
    ARTIFACT_PARENT
    / "supplier_021081_stock773_calibrated_incidents_20260902_v1"
)
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
DEFAULT_PROFILE = (
    REPO_ROOT
    / "etudecas"
    / "prototypes"
    / "scan_2027_risk_control"
    / "config"
    / "canonical_real_baseline_engine_profile.json"
)

SCHEMA_VERSION = "etudecas.supplier_service_regime_calibration_plan.v1"
MEASURED_DAYS = 720
WARMUP_DAYS = 240
SCREENING_SEED = 340281
FINAL_CONFIRMATION_SEEDS = tuple(range(340282, 340312))
PRELIMINARY_CONFIRMATION_SEEDS = FINAL_CONFIRMATION_SEEDS[:15]
TARGETS = (0.93, 0.80)
TARGET_TOLERANCE = 0.015
PRODUCT_BALANCE_GUARD = 0.05
PRODUCTS = ("268091", "268967")
CLIENT_NODE_ID = "C-XXXXX"

# These arguments reproduce the corrected network reference after the older
# profile arguments.  The list is recorded in the plan; this module still does
# not execute it.
MANAGED_REFERENCE_PROTOCOL_ARGS = (
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

IDENTIFIED_CAPACITY_PAIRS = {
    ("SDC-VD0914360C", "item:338929", "M-1810"): 75_000.0,
    ("SDC-VD0993480A", "item:344135", "M-1430"): 300_000.0,
}
MODELED_FINISHED_FACTORY_PROCESSES = {
    ("M-1430", "item:268967"): 154_000.0,
    ("M-1810", "item:268091"): 203_550.0,
}


@dataclass(frozen=True)
class Family:
    key: str
    label_fr: str
    kind: str
    values: tuple[float, ...]
    unit: str
    domain: str
    changed_parameter: str
    scope_fr: str
    supplier_ranking_allowed: bool
    interpretation_fr: str


FAMILIES: tuple[Family, ...] = (
    Family(
        key="supplier_capacity_identified",
        label_fr="Capacité des voies fournisseurs quantifiables",
        kind="supplier_floor",
        values=(0.75, 0.60, 0.45, 0.41, 0.40, 0.39, 0.25, 0.10),
        unit="ratio_de_la_reference",
        domain="supplier",
        changed_parameter="supplier_capacity_qty_per_day",
        scope_fr="338929 et 344135 uniquement; aucune capacité n'est inventée pour les autres voies",
        supplier_ranking_allowed=True,
        interpretation_fr=(
            "Hypothèse de capacité permanente, appliquée avant la période de mise en régime. "
            "Les niveaux 0,41/0,40/0,39 encadrent le seuil d'un lot de 120 000 UN sur 344135."
        ),
    ),
    Family(
        key="supplier_planned_lead",
        label_fr="Délai nominal fournisseur",
        kind="graph_lead",
        values=(7.0, 14.0, 30.0, 60.0, 90.0, 120.0, 180.0),
        unit="jours_ajoutes",
        domain="supplier",
        changed_parameter="edge.lead_time.mean",
        scope_fr="18 voies fournisseurs actives",
        supplier_ranking_allowed=True,
        interpretation_fr=(
            "Délai structurel connu de la planification, distinct d'un retard soudain. "
            "La limite numérique de délai est ajustée mécaniquement à deux fois le nouveau délai moyen."
        ),
    ),
    Family(
        key="supplier_nominal_delivery_reliability",
        label_fr="Fiabilité nominale de livraison fournisseur",
        kind="graph_reliability",
        values=(0.98, 0.95, 0.90, 0.85, 0.80, 0.70, 0.50),
        unit="ratio_de_quantite_livree",
        domain="supplier",
        changed_parameter="edge.service_level.otif",
        scope_fr="18 voies fournisseurs actives",
        supplier_ranking_allowed=True,
        interpretation_fr=(
            "Performance structurelle connue du plan. Ce paramètre n'est pas une probabilité historique "
            "estimée et ne remplace pas un incident qualité."
        ),
    ),
    Family(
        key="finished_factory_capacity",
        label_fr="Capacité des usines de produits finis",
        kind="factory_capacity",
        values=(0.85, 0.75, 0.71, 0.70, 0.69, 0.60, 0.40),
        unit="ratio_de_la_reference",
        domain="internal_context",
        changed_parameter="process.capacity.max_rate",
        scope_fr="M-1430/268967 et M-1810/268091; le procédé 773474 non borné reste inchangé",
        supplier_ranking_allowed=False,
        interpretation_fr=(
            "Contexte interne permettant de séparer une fragilité usine d'une fragilité fournisseur. "
            "Les niveaux 0,71/0,70/0,69 encadrent le lot fixe de 107 800 UN sur M-1430."
        ),
    ),
    Family(
        key="customer_demand_load",
        label_fr="Charge de demande client",
        kind="graph_demand",
        values=(1.02, 1.05, 1.10, 1.15, 1.20, 1.30, 1.50),
        unit="ratio_de_la_reference",
        domain="market_context",
        changed_parameter="scenario.demand.profile.points.value",
        scope_fr="demande des produits 268091 et 268967 au client C-XXXXX",
        supplier_ranking_allowed=False,
        interpretation_fr=(
            "Contexte de charge, pas une dégradation fournisseur. Cette famille ne peut pas être utilisée "
            "pour classer les fournisseurs."
        ),
    ),
)
FAMILY_BY_KEY = {family.key: family for family in FAMILIES}


@dataclass(frozen=True)
class Candidate:
    scenario_id: str
    family: str
    severity_index: int
    value: float
    unit: str
    kind: str
    domain: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def ordered_fields(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    return fields


def write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(fields or ordered_fields(rows))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def finite_float(value: Any, default: float = math.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "oui"}


def candidate_code(value: float) -> str:
    return format(float(value), ".12g").replace("-", "m").replace(".", "p")


def build_candidates() -> list[Candidate]:
    candidates: list[Candidate] = []
    for family in FAMILIES:
        for severity_index, value in enumerate(family.values, 1):
            candidates.append(
                Candidate(
                    scenario_id=f"{family.key}__{candidate_code(value)}",
                    family=family.key,
                    severity_index=severity_index,
                    value=value,
                    unit=family.unit,
                    kind=family.kind,
                    domain=family.domain,
                )
            )
    if len(candidates) != 36:
        raise AssertionError(f"Expected 36 screening candidates, got {len(candidates)}")
    return candidates


def graph_edge_index(graph: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for edge in graph.get("edges") or []:
        edge_id = str(edge.get("id") or "")
        if not edge_id or edge_id in result:
            raise ValueError(f"Missing or duplicate graph edge id: {edge_id!r}")
        result[edge_id] = edge
    return result


def graph_process_index(
    graph: Mapping[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for node in graph.get("nodes") or []:
        node_id = str(node.get("id") or "")
        for process in node.get("processes") or []:
            outputs = process.get("outputs") or []
            if not outputs:
                continue
            item_id = str((outputs[0] or {}).get("item_id") or "")
            key = (node_id, item_id)
            if key in result:
                raise ValueError(f"Duplicate process output pair: {key}")
            result[key] = process
    return result


def demand_entries(graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in graph.get("scenarios") or []:
        for demand in scenario.get("demand") or []:
            if (
                str(demand.get("node_id") or demand.get("customer_id") or "")
                == CLIENT_NODE_ID
                and str(demand.get("item_id") or "").replace("item:", "")
                in PRODUCTS
            ):
                rows.append(demand)
    return rows


def baseline_rows(reference_campaign: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for filename in ("screening_metrics.csv", "confirmation_metrics.csv"):
        for row in read_csv_rows(reference_campaign / filename):
            if str(row.get("scenario_id") or "") == "baseline_nominal":
                rows.append(row)
    return rows


def validate_reference(
    *,
    reference_campaign: Path,
    graph_path: Path,
    engine_path: Path,
    profile_path: Path,
) -> dict[str, Any]:
    required = (
        reference_campaign / "campaign_manifest.json",
        reference_campaign / "active_lane_reference.csv",
        reference_campaign / "screening_metrics.csv",
        reference_campaign / "confirmation_metrics.csv",
        reference_campaign / "inputs" / "prepared_physical_supplier_floors.csv",
        graph_path,
        engine_path,
        profile_path,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing reference input(s): " + "; ".join(missing))

    manifest = read_json(reference_campaign / "campaign_manifest.json")
    if manifest.get("status") != "complete":
        raise ValueError("The network reference campaign is not complete")
    if int(manifest.get("days") or 0) != MEASURED_DAYS:
        raise ValueError("The network reference does not use the 720-day horizon")
    for label, path, key in (
        ("graph", graph_path, "graph_sha256"),
        ("engine", engine_path, "engine_sha256"),
        ("profile", profile_path, "profile_sha256"),
    ):
        actual = sha256_file(path)
        expected = str(manifest.get(key) or "")
        if actual != expected:
            raise ValueError(
                f"Current {label} differs from the completed reference: {actual} != {expected}"
            )

    lanes = read_csv_rows(reference_campaign / "active_lane_reference.csv")
    if len(lanes) != 18:
        raise ValueError(f"Expected 18 active lanes, found {len(lanes)}")
    lane_keys = {
        (row["supplier_id"], row["item_id"], row["dst_node_id"]) for row in lanes
    }
    edge_ids = {row["edge_id"] for row in lanes}
    if len(lane_keys) != 18 or len(edge_ids) != 18:
        raise ValueError("The active-lane reference contains duplicates")
    if {row["target_product_id"] for row in lanes} != set(PRODUCTS):
        raise ValueError("Active lanes do not cover both target products")

    graph = read_json(graph_path)
    edges = graph_edge_index(graph)
    for row in lanes:
        edge = edges.get(row["edge_id"])
        if edge is None:
            raise ValueError(f"Active edge missing from graph: {row['edge_id']}")
        exact = (
            str(edge.get("from") or "") == row["supplier_id"]
            and str(edge.get("to") or "") == row["dst_node_id"]
            and row["item_id"] in {str(item) for item in edge.get("items") or []}
        )
        if not exact:
            raise ValueError(f"Active edge scope mismatch: {row['edge_id']}")
        otif = finite_float((edge.get("service_level") or {}).get("otif"), 1.0)
        if not math.isclose(otif, 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("Reference active-lane reliability is not neutral")

    demands = demand_entries(graph)
    if len(demands) != 2:
        raise ValueError(f"Expected two target demand entries, found {len(demands)}")
    if {str(row.get("item_id") or "").replace("item:", "") for row in demands} != set(
        PRODUCTS
    ):
        raise ValueError("Target demand entries do not cover both products")

    processes = graph_process_index(graph)
    for key, expected_capacity in MODELED_FINISHED_FACTORY_PROCESSES.items():
        process = processes.get(key)
        if process is None:
            raise ValueError(f"Missing finished-product process {key}")
        actual = finite_float((process.get("capacity") or {}).get("max_rate"))
        if not math.isclose(actual, expected_capacity, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"Unexpected reference process capacity for {key}: {actual}")

    floor_rows = read_csv_rows(
        reference_campaign / "inputs" / "prepared_physical_supplier_floors.csv"
    )
    found_capacity_pairs: dict[tuple[str, str, str], float] = {}
    for row in floor_rows:
        key = (row["supplier_id"], row["item_id"], row["dst_node_id"])
        found_capacity_pairs[key] = finite_float(
            row.get("tested_capacity_floor_qty_per_day")
        )
    if found_capacity_pairs != IDENTIFIED_CAPACITY_PAIRS:
        raise ValueError(
            "The two identified supplier capacities differ from the reference campaign"
        )

    references = baseline_rows(reference_campaign)
    expected_seeds = {SCREENING_SEED, *FINAL_CONFIRMATION_SEEDS}
    actual_seeds = {int(float(row["seed"])) for row in references}
    if len(references) != 31 or actual_seeds != expected_seeds:
        raise ValueError("The reusable baseline does not contain the expected 31 seeds")
    for row in references:
        if not truthy(row.get("valid")):
            raise ValueError(f"Invalid reusable baseline seed: {row.get('seed')}")
        for product in PRODUCTS:
            if not truthy(row.get(f"horizon_complete_{product}")):
                raise ValueError(f"Incomplete reusable baseline for {product}")
            if finite_float(row.get(f"on_due_volume_proxy_{product}")) < 0.95:
                raise ValueError(f"Reusable baseline service below 95% for {product}")

    return {
        "validated": True,
        "reference_campaign": str(reference_campaign),
        "reference_manifest_sha256": sha256_file(
            reference_campaign / "campaign_manifest.json"
        ),
        "active_lane_reference_sha256": sha256_file(
            reference_campaign / "active_lane_reference.csv"
        ),
        "active_lane_count": len(lanes),
        "active_supplier_count": len({row["supplier_id"] for row in lanes}),
        "reusable_baseline_seed_count": len(references),
        "reusable_baseline_seeds": sorted(actual_seeds),
        "graph_sha256": sha256_file(graph_path),
        "engine_sha256": sha256_file(engine_path),
        "profile_sha256": sha256_file(profile_path),
        "supplier_floor_sha256": sha256_file(
            reference_campaign / "inputs" / "prepared_physical_supplier_floors.csv"
        ),
        "baseline_mean_on_due_by_product": {
            product: fmean(
                finite_float(row[f"on_due_volume_proxy_{product}"])
                for row in references
            )
            for product in PRODUCTS
        },
    }


def _scale_graph_lead(
    graph: dict[str, Any], active_edge_ids: set[str], extra_days: float
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for edge in graph.get("edges") or []:
        if str(edge.get("id") or "") not in active_edge_ids:
            continue
        lead = edge.get("lead_time")
        if not isinstance(lead, dict):
            raise ValueError(f"Missing lead_time on active edge {edge.get('id')}")
        old = finite_float(lead.get("mean"))
        if not math.isfinite(old) or old <= 0:
            raise ValueError(f"Invalid reference lead on active edge {edge.get('id')}")
        new = old + extra_days
        lead["mean"] = new
        limit = edge.get("delay_step_limit")
        if not isinstance(limit, dict):
            raise ValueError(f"Missing delay_step_limit on active edge {edge.get('id')}")
        old_limit = finite_float(limit.get("value"))
        new_limit = int(math.ceil(2.0 * new))
        limit["value"] = new_limit
        changes.append(
            {
                "edge_id": edge["id"],
                "field": "lead_time.mean",
                "reference_value": old,
                "candidate_value": new,
                "derived_delay_step_limit_reference": old_limit,
                "derived_delay_step_limit_candidate": new_limit,
            }
        )
    if len(changes) != len(active_edge_ids):
        raise ValueError("Not all active edges received the lead-time candidate")
    return changes


def _scale_graph_reliability(
    graph: dict[str, Any], active_edge_ids: set[str], reliability: float
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for edge in graph.get("edges") or []:
        if str(edge.get("id") or "") not in active_edge_ids:
            continue
        service = edge.get("service_level")
        if not isinstance(service, dict):
            service = {}
            edge["service_level"] = service
        old = finite_float(service.get("otif"), 1.0)
        service["otif"] = reliability
        changes.append(
            {
                "edge_id": edge["id"],
                "field": "service_level.otif",
                "reference_value": old,
                "candidate_value": reliability,
            }
        )
    if len(changes) != len(active_edge_ids):
        raise ValueError("Not all active edges received the reliability candidate")
    return changes


def _scale_graph_demand(
    graph: dict[str, Any], demand_scale: float
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for demand in demand_entries(graph):
        point_count = 0
        reference_total = 0.0
        candidate_total = 0.0
        for profile in demand.get("profile") or []:
            for point in profile.get("points") or []:
                old = finite_float(point.get("value"))
                if not math.isfinite(old):
                    raise ValueError("Non-finite demand point")
                new = old * demand_scale
                point["value"] = new
                point_count += 1
                reference_total += old
                candidate_total += new
        if point_count == 0:
            raise ValueError("Target demand entry has no profile point")
        changes.append(
            {
                "node_id": CLIENT_NODE_ID,
                "item_id": str(demand.get("item_id") or ""),
                "field": "demand.profile.points.value",
                "point_count": point_count,
                "reference_profile_total": reference_total,
                "candidate_profile_total": candidate_total,
                "scale": demand_scale,
            }
        )
    if len(changes) != 2:
        raise ValueError("Demand candidate did not change exactly two products")
    return changes


def _supplier_floor_rows(scale: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    for (supplier_id, item_id, dst_node_id), reference in sorted(
        IDENTIFIED_CAPACITY_PAIRS.items()
    ):
        candidate = reference * scale
        rows.append(
            {
                "supplier_id": supplier_id,
                "item_id": item_id,
                "dst_node_id": dst_node_id,
                "neutral_capacity_floor_qty_per_day": candidate,
                "tested_capacity_floor_qty_per_day": candidate,
                "capacity_floor_basis": "structural_service_regime_candidate",
            }
        )
        changes.append(
            {
                "supplier_id": supplier_id,
                "item_id": item_id,
                "dst_node_id": dst_node_id,
                "field": "supplier_capacity_qty_per_day",
                "reference_value": reference,
                "candidate_value": candidate,
                "scale": scale,
            }
        )
    return rows, changes


def _factory_capacity_rows(
    scale: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    for (node_id, item_id), reference in sorted(
        MODELED_FINISHED_FACTORY_PROCESSES.items()
    ):
        candidate = reference * scale
        rows.append(
            {
                "node_id": node_id,
                "output_item_id": item_id,
                "industrial_nominal_capacity_qty_per_day": candidate,
                "capacity_basis": "structural_service_regime_candidate",
            }
        )
        changes.append(
            {
                "node_id": node_id,
                "item_id": item_id,
                "field": "process.capacity.max_rate",
                "reference_value": reference,
                "candidate_value": candidate,
                "scale": scale,
            }
        )
    return rows, changes


def write_candidate_inputs(
    *,
    output_dir: Path,
    graph_path: Path,
    reference_campaign: Path,
    candidates: Sequence[Candidate],
) -> dict[str, dict[str, Any]]:
    source_graph = read_json(graph_path)
    lanes = read_csv_rows(reference_campaign / "active_lane_reference.csv")
    active_edge_ids = {row["edge_id"] for row in lanes}
    reference_floor_path = (
        reference_campaign / "inputs" / "prepared_physical_supplier_floors.csv"
    ).resolve()
    reference_graph_sha256 = sha256_file(graph_path)
    reference_floor_sha256 = sha256_file(reference_floor_path)
    result: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        scenario_dir = output_dir / "inputs" / candidate.scenario_id
        if candidate.kind == "supplier_floor":
            rows, changes = _supplier_floor_rows(candidate.value)
            path = scenario_dir / "supplier_capacity_floors.csv"
            write_csv(path, rows)
            input_kind = "supplier_floor_csv"
        elif candidate.kind == "factory_capacity":
            rows, changes = _factory_capacity_rows(candidate.value)
            path = scenario_dir / "factory_capacities.csv"
            write_csv(path, rows)
            input_kind = "factory_capacity_csv"
        else:
            graph = copy.deepcopy(source_graph)
            if candidate.kind == "graph_lead":
                changes = _scale_graph_lead(graph, active_edge_ids, candidate.value)
            elif candidate.kind == "graph_reliability":
                changes = _scale_graph_reliability(
                    graph, active_edge_ids, candidate.value
                )
            elif candidate.kind == "graph_demand":
                changes = _scale_graph_demand(graph, candidate.value)
            else:
                raise ValueError(f"Unsupported candidate kind: {candidate.kind}")
            path = scenario_dir / "candidate_graph.json"
            write_json(path, graph)
            input_kind = "graph_json"
        change_path = scenario_dir / "change_ledger.json"
        write_json(
            change_path,
            {
                "schema_version": f"{SCHEMA_VERSION}.change_ledger",
                "scenario_id": candidate.scenario_id,
                "family": candidate.family,
                "changed_family_count": 1,
                "acute_incident_event_count": 0,
                "changes": changes,
            },
        )
        result[candidate.scenario_id] = {
            "input_kind": input_kind,
            "input_path": str(path),
            "input_sha256": sha256_file(path),
            "change_ledger_path": str(change_path),
            "change_ledger_sha256": sha256_file(change_path),
            "changed_row_count": len(changes),
            "family": candidate.family,
            "value": candidate.value,
            "execution_inputs": {
                "graph": str(path if input_kind == "graph_json" else graph_path),
                "graph_sha256": (
                    sha256_file(path)
                    if input_kind == "graph_json"
                    else reference_graph_sha256
                ),
                "supplier_floors": str(
                    path if input_kind == "supplier_floor_csv" else reference_floor_path
                ),
                "supplier_floors_sha256": (
                    sha256_file(path)
                    if input_kind == "supplier_floor_csv"
                    else reference_floor_sha256
                ),
                "factory_capacities": (
                    str(path) if input_kind == "factory_capacity_csv" else ""
                ),
                "factory_capacities_sha256": (
                    sha256_file(path)
                    if input_kind == "factory_capacity_csv"
                    else ""
                ),
                "supplier_risk_events": "",
                "demand_perturbation": "",
                "control_schedule": "",
            },
        }
    return result


def scenario_design_rows(
    candidates: Sequence[Candidate], input_inventory: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "scenario_id": "baseline_nominal",
            "family": "baseline",
            "family_label_fr": "Fonctionnement nominal simulé",
            "severity_index": 0,
            "parameter_value": 1.0,
            "parameter_unit": "reference",
            "domain": "reference",
            "changed_parameter": "none",
            "changed_family_count": 0,
            "scope_fr": "référence réseau validée sur 30 graines",
            "supplier_ranking_allowed": False,
            "acute_supplier_incident": False,
            "evidence_status": "reusable_simulated_reference",
            "interpretation_fr": "Aucun paramètre de dégradation ajouté.",
            "input_path": "",
            "input_sha256": "",
        }
    ]
    for candidate in candidates:
        family = FAMILY_BY_KEY[candidate.family]
        inventory = input_inventory[candidate.scenario_id]
        rows.append(
            {
                "scenario_id": candidate.scenario_id,
                "family": family.key,
                "family_label_fr": family.label_fr,
                "severity_index": candidate.severity_index,
                "parameter_value": candidate.value,
                "parameter_unit": candidate.unit,
                "domain": family.domain,
                "changed_parameter": family.changed_parameter,
                "changed_family_count": 1,
                "scope_fr": family.scope_fr,
                "supplier_ranking_allowed": family.supplier_ranking_allowed,
                "acute_supplier_incident": False,
                "evidence_status": "planned_not_executed",
                "interpretation_fr": family.interpretation_fr,
                "input_path": inventory["input_path"],
                "input_sha256": inventory["input_sha256"],
            }
        )
    return rows


def service_from_daily_rows(
    rows: Iterable[Mapping[str, Any]], *, days: int = MEASURED_DAYS
) -> dict[str, Any]:
    """Compute catch-up-safe client service for the two finished products."""

    grouped = {
        product: {
            "demand": 0.0,
            "on_due": 0.0,
            "backlog_qty_days": 0.0,
            "ending_backlog": 0.0,
            "days": set(),
        }
        for product in PRODUCTS
    }
    for row in rows:
        if str(row.get("node_id") or "") != CLIENT_NODE_ID:
            continue
        product = str(row.get("item_id") or "").replace("item:", "")
        if product not in grouped:
            continue
        day = int(finite_float(row.get("day"), -1))
        if day < 0 or day >= days:
            continue
        demand = max(0.0, finite_float(row.get("demand_qty"), 0.0))
        served = max(0.0, finite_float(row.get("served_qty"), 0.0))
        required = max(
            demand,
            finite_float(row.get("required_with_backlog_qty"), demand),
        )
        starting_backlog = max(0.0, required - demand)
        on_due = min(demand, max(0.0, served - starting_backlog))
        ending_backlog = max(0.0, finite_float(row.get("backlog_end_qty"), 0.0))
        stats = grouped[product]
        stats["demand"] += demand
        stats["on_due"] += on_due
        stats["backlog_qty_days"] += ending_backlog
        stats["ending_backlog"] = ending_backlog
        stats["days"].add(day)

    output: dict[str, Any] = {}
    global_demand = 0.0
    global_on_due = 0.0
    product_services: list[float] = []
    for product, stats in grouped.items():
        if stats["days"] != set(range(days)):
            raise ValueError(f"Incomplete service horizon for product {product}")
        demand = float(stats["demand"])
        service = float(stats["on_due"]) / demand if demand else 1.0
        output[f"demand_qty_{product}"] = demand
        output[f"on_due_qty_{product}"] = stats["on_due"]
        output[f"on_due_service_{product}"] = service
        output[f"backlog_qty_days_{product}"] = stats["backlog_qty_days"]
        output[f"ending_backlog_qty_{product}"] = stats["ending_backlog"]
        global_demand += demand
        global_on_due += float(stats["on_due"])
        product_services.append(service)
    output["system_on_due_service"] = (
        global_on_due / global_demand if global_demand else 1.0
    )
    output["minimum_product_on_due_service"] = min(product_services, default=1.0)
    output["service_metric_definition"] = (
        "sum(on-time served volume for 268091 and 268967) / sum(client demand volume); "
        "same UN unit; backlog catch-up excluded"
    )
    return output


def select_target_candidates(
    screening_rows: Sequence[Mapping[str, Any]],
    *,
    targets: Sequence[float] = TARGETS,
    tolerance: float = TARGET_TOLERANCE,
    product_balance_guard: float = PRODUCT_BALANCE_GUARD,
) -> dict[str, Any]:
    """Select a point in tolerance or adjacent simulated brackets.

    No interpolation is performed.  A global service point is balanced only if
    neither product falls more than ``product_balance_guard`` below the target.
    """

    by_id = {str(row.get("scenario_id") or ""): row for row in screening_rows}
    expected = {candidate.scenario_id for candidate in build_candidates()}
    if set(by_id) != expected:
        missing = sorted(expected - set(by_id))
        extra = sorted(set(by_id) - expected)
        raise ValueError(f"Screening scope mismatch; missing={missing}, extra={extra}")
    if any(not truthy(row.get("valid")) for row in screening_rows):
        raise ValueError("At least one screening row is invalid")

    records: list[dict[str, Any]] = []
    selected: set[str] = set()
    candidates = build_candidates()
    for family in FAMILIES:
        points = [candidate for candidate in candidates if candidate.family == family.key]
        for target in targets:
            evaluated: list[tuple[Candidate, float, float, float, bool]] = []
            for candidate in points:
                row = by_id[candidate.scenario_id]
                global_service = finite_float(row.get("system_on_due_service"))
                product_268091 = finite_float(row.get("on_due_service_268091"))
                product_268967 = finite_float(row.get("on_due_service_268967"))
                if not all(
                    math.isfinite(value)
                    for value in (global_service, product_268091, product_268967)
                ):
                    raise ValueError(f"Missing service metric for {candidate.scenario_id}")
                balanced = min(product_268091, product_268967) >= (
                    float(target) - product_balance_guard
                )
                evaluated.append(
                    (
                        candidate,
                        global_service,
                        product_268091,
                        product_268967,
                        balanced,
                    )
                )
            nearest = min(
                evaluated,
                key=lambda point: (
                    abs(point[1] - target),
                    point[0].severity_index,
                ),
            )
            selected_for_target: list[tuple[Candidate, float, float, float, bool]] = []
            method = "target_not_attained_or_bracketed"
            if abs(nearest[1] - target) <= tolerance and nearest[4]:
                selected_for_target = [nearest]
                method = "discrete_point_within_tolerance"
            else:
                brackets = []
                for left, right in zip(evaluated, evaluated[1:]):
                    if (left[1] - target) * (right[1] - target) <= 0:
                        brackets.append((left, right))
                balanced_brackets = [
                    pair for pair in brackets if pair[0][4] and pair[1][4]
                ]
                if balanced_brackets:
                    best = min(
                        balanced_brackets,
                        key=lambda pair: (
                            abs(pair[0][1] - target) + abs(pair[1][1] - target),
                            pair[0][0].severity_index,
                        ),
                    )
                    selected_for_target = list(best)
                    method = "adjacent_discrete_bracket_no_interpolation"
            for point in selected_for_target:
                selected.add(point[0].scenario_id)
            records.append(
                {
                    "family": family.key,
                    "target_service": target,
                    "selection_method": method,
                    "selected_scenario_ids": [
                        point[0].scenario_id for point in selected_for_target
                    ],
                    "nearest_scenario_id": nearest[0].scenario_id,
                    "nearest_system_service": nearest[1],
                    "nearest_product_268091_service": nearest[2],
                    "nearest_product_268967_service": nearest[3],
                    "nearest_balanced": nearest[4],
                    "interpolation_claim_allowed": False,
                }
            )
    if len(selected) > 4 * len(FAMILIES):
        raise AssertionError("Selection exceeds the declared 20-scenario maximum")
    return {
        "schema_version": f"{SCHEMA_VERSION}.selection",
        "selected_scenario_ids": sorted(selected),
        "selected_scenario_count": len(selected),
        "maximum_selected_scenario_count": 4 * len(FAMILIES),
        "target_records": records,
        "selection_is_screening_only": True,
        "interpolation_claim_allowed": False,
    }


def missing_confirmation_jobs(
    selected_scenario_ids: Sequence[str],
    *,
    requested_seeds: Sequence[int],
    existing_keys: Iterable[tuple[str, int]] = (),
) -> list[tuple[str, int]]:
    known = set(existing_keys)
    return [
        (scenario_id, int(seed))
        for scenario_id in selected_scenario_ids
        for seed in requested_seeds
        if (scenario_id, int(seed)) not in known
    ]


def _legacy_audit(
    legacy_combined: Path, legacy_stock: Path
) -> dict[str, Any]:
    combined_rows = read_csv_rows(legacy_combined / "paired_replay_results.csv")
    hypothesis = [row for row in combined_rows if row.get("variant") == "target_hypothesis"]
    stock_rows = read_csv_rows(legacy_stock / "baseline_calibration_metrics.csv")
    stock_baselines = {
        int(round(finite_float(row.get("state_regime_target_cover_days")))): row
        for row in stock_rows
        if row.get("scenario_id") == "baseline_observed_order_book"
    }
    incident_rows = [
        row for row in stock_rows if row.get("scenario_id") != "baseline_observed_order_book"
    ]
    zero_incident_delta_count = sum(
        abs(finite_float(row.get("product_on_due_delta_vs_paired_baseline"), 0.0))
        <= 1e-12
        for row in incident_rows
    )
    return {
        "legacy_combined_campaign": {
            "path": str(legacy_combined),
            "seed_count": len(hypothesis),
            "mean_fill_268091": fmean(
                finite_float(row["fill_rate_268091"]) for row in hypothesis
            ),
            "min_fill_268091": min(
                finite_float(row["fill_rate_268091"]) for row in hypothesis
            ),
            "max_fill_268091": max(
                finite_float(row["fill_rate_268091"]) for row in hypothesis
            ),
            "mean_fill_268967": fmean(
                finite_float(row["fill_rate_268967"]) for row in hypothesis
            ),
            "changed_families": [
                "338929 lead time",
                "all M-1430 supplier capacities",
                "268967 demand",
            ],
            "reusable_as_global_93_80_calibration": False,
            "reasons": [
                "three physical families changed together",
                "one product is near 93% while the other is near 80%; no global target was defined",
                "365-day horizon and prior initialization protocol differ from the current 720-day reference",
                "legacy service calculation can count backlog catch-up as on-time service",
            ],
        },
        "legacy_stock_773474_campaign": {
            "path": str(legacy_stock),
            "seed_count": 1,
            "cover_300d_proxy": finite_float(
                stock_baselines[300]["product_on_due_volume_proxy"]
            ),
            "cover_384d_proxy": finite_float(
                stock_baselines[384]["product_on_due_volume_proxy"]
            ),
            "cover_385d_proxy": finite_float(
                stock_baselines[385]["product_on_due_volume_proxy"]
            ),
            "tested_incident_row_count": len(incident_rows),
            "zero_service_delta_incident_row_count": zero_incident_delta_count,
            "reusable_as_global_93_80_calibration": False,
            "reasons": [
                "single 268967 chain and one seed only",
                "80% proxy exists at 300 days but 93% is skipped by a lot-size discontinuity",
                "the tested 021081 incidents are masked in these states",
                "legacy metric is explicitly a proxy and must be recomputed with catch-up excluded",
            ],
        },
    }


def _business_report(
    *,
    audit: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> str:
    combined = audit["legacy_combined_campaign"]
    stock = audit["legacy_stock_773474_campaign"]
    return f"""# Calibration préliminaire des niveaux de service 93 % et 80 %

## Ce que les anciens calculs disent réellement

- L'ancienne combinaison de trois réglages a produit, sur {combined['seed_count']} répétitions, un service de 268091 compris entre {100*combined['min_fill_268091']:.2f} % et {100*combined['max_fill_268091']:.2f} % (moyenne {100*combined['mean_fill_268091']:.2f} %), tandis que 268967 était à {100*combined['mean_fill_268967']:.2f} %. Elle ne constitue donc ni une référence globale à 93 %, ni une référence globale à 80 %.
- La réduction du stock 773474 donne un indicateur proche de 80 % à 300 jours de couverture ({100*stock['cover_300d_proxy']:.2f} %), mais saute de {100*stock['cover_384d_proxy']:.2f} % à 384 jours à {100*stock['cover_385d_proxy']:.2f} % à 385 jours. Il n'existe pas de point simulé à 93 % dans cette série.
- Les {stock['tested_incident_row_count']} comparaisons d'incident de cette série ont toutes un écart de service nul. Cela signifie que les incidents testés sont masqués dans cette configuration, pas que la supply est invulnérable.

Ces résultats restent utiles pour comprendre les effets de lots et de stocks, mais ils ne doivent pas être présentés comme une calibration réseau confirmée.

## Nouvelle définition proposée

Le niveau de service global simulé est le volume livré à la date demandée pour 268091 et 268967, divisé par la demande totale des deux produits. Les deux volumes sont exprimés en unités. Un rattrapage de retard n'est jamais compté comme une livraison à l'heure.

La page de résultats devra toujours montrer en parallèle :

- le niveau global pondéré par les volumes ;
- le niveau de chaque produit ;
- le plus faible des deux niveaux, pour qu'un produit ne masque pas l'autre ;
- le retard cumulé et le retard encore ouvert à la fin.

Une configuration n'est dite « proche de 93 % » ou « proche de 80 % » que si le niveau global est à ±1,5 point et si aucun produit ne descend de plus de 5 points sous la cible.

## Cinq causes testées séparément

1. Capacité des deux voies fournisseurs dont la capacité est quantifiable : 338929 et 344135.
2. Délai nominal des 18 voies actives.
3. Fiabilité nominale de livraison des 18 voies actives.
4. Capacité des deux usines de produits finis, utilisée comme contexte interne et jamais pour classer les fournisseurs.
5. Charge de demande des deux produits, utilisée comme contexte marché et jamais pour classer les fournisseurs.

Aucun scénario ne combine ces causes. La qualité reste un incident séparé : le moteur actuel ne possède pas de paramètre de qualité nominale appliqué avant la mise en régime. Une retenue qualité ou une perte de rendement sera donc superposée seulement après sélection d'une configuration de service ; elle ne servira pas à fabriquer artificiellement une référence à 93 % ou 80 %.

## Calcul préliminaire puis confirmation

- Durée : 720 jours mesurés, après 240 jours de mise en régime. Réduire à un an créerait une autre expérience et empêcherait la réutilisation directe avec la campagne réseau actuelle.
- Première étape : {plan['run_budget']['new_screening_runs']} configurations sur une répétition pour localiser les niveaux et les discontinuités.
- Étape préliminaire : au maximum {plan['run_budget']['maximum_selected_candidates']} configurations retenues, sur 15 répétitions identiques aux 15 premières de la série finale.
- Étape finale : ajout des 15 répétitions restantes ; les 15 premières ne sont pas recalculées.
- Sélection : un point réellement simulé dans la tolérance, sinon les deux points simulés adjacents qui encadrent la cible. Aucune interpolation entre deux lots.

Le maximum est de {plan['run_budget']['maximum_new_runs_through_preliminary']} nouveaux calculs jusqu'au résultat préliminaire, puis {plan['run_budget']['maximum_incremental_runs_preliminary_to_final']} calculs supplémentaires pour atteindre 30 répétitions. À la cadence de la campagne réseau terminée, le budget prudent est de 6 à 8 heures pour le préliminaire et 5 à 7 heures supplémentaires pour la version 30 répétitions.

## Statut

Ce paquet prépare les entrées et les règles de sélection. **Aucune simulation nouvelle n'a été lancée.** Les résultats futurs seront des hypothèses simulées à valider avec les taux de service, capacités, délais et données qualité de l'industriel.
"""


def prepare(
    *,
    output_dir: Path,
    reference_campaign: Path = DEFAULT_REFERENCE_CAMPAIGN,
    graph_path: Path = DEFAULT_GRAPH,
    engine_path: Path = DEFAULT_ENGINE,
    profile_path: Path = DEFAULT_PROFILE,
    legacy_combined: Path = DEFAULT_LEGACY_COMBINED,
    legacy_stock: Path = DEFAULT_LEGACY_STOCK,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Refusing to overwrite a non-empty plan directory: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    reference_campaign = reference_campaign.resolve()
    graph_path = graph_path.resolve()
    engine_path = engine_path.resolve()
    profile_path = profile_path.resolve()
    legacy_combined = legacy_combined.resolve()
    legacy_stock = legacy_stock.resolve()

    reference_audit = validate_reference(
        reference_campaign=reference_campaign,
        graph_path=graph_path,
        engine_path=engine_path,
        profile_path=profile_path,
    )
    candidates = build_candidates()
    input_inventory = write_candidate_inputs(
        output_dir=output_dir,
        graph_path=graph_path,
        reference_campaign=reference_campaign,
        candidates=candidates,
    )
    design_rows = scenario_design_rows(candidates, input_inventory)
    design_path = output_dir / "scenario_design.csv"
    write_csv(design_path, design_rows)
    audit = _legacy_audit(legacy_combined, legacy_stock)
    write_json(output_dir / "existing_results_audit.json", audit)

    plan_core: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "planned_not_executed",
        "purpose": (
            "Calibrate simulated global service regimes near 93% and 80%, one structural cause at a time."
        ),
        "evidence_class": "simulation_hypothesis_not_observed_performance",
        "old_results_mutated": False,
        "engine_mutated": False,
        "graph_source_mutated": False,
        "acute_incident_included": False,
        "quality_incident_policy": (
            "quality hold/yield remains a separate acute incident after regime calibration; "
            "it is not used to manufacture a 93% or 80% baseline"
        ),
        "horizon": {
            "measured_days": MEASURED_DAYS,
            "warmup_days": WARMUP_DAYS,
            "one_year_shortcut_used": False,
            "reason": (
                "720 measured days preserve the reference annual-cycle coverage and direct reuse of the current network campaign; "
                "a 365-day run would be a separate horizon sensitivity."
            ),
        },
        "service_definition": {
            "primary_metric": "system_on_due_service",
            "formula": (
                "sum(on-time served volume 268091 + 268967) / sum(client demand 268091 + 268967)"
            ),
            "unit_compatibility": "both finished products use UN",
            "backlog_catchup_excluded": True,
            "mandatory_companion_metrics": [
                "on_due_service_268091",
                "on_due_service_268967",
                "minimum_product_on_due_service",
                "backlog_qty_days_by_product",
                "ending_backlog_by_product",
            ],
            "targets": list(TARGETS),
            "tolerance": TARGET_TOLERANCE,
            "maximum_product_shortfall_below_target": PRODUCT_BALANCE_GUARD,
        },
        "families": [asdict(family) for family in FAMILIES],
        "screening_candidate_count": len(candidates),
        "stages": {
            "screening": {
                "seeds": [SCREENING_SEED],
                "purpose": "locate discrete points and adjacent brackets only",
                "publishable_as_mean_performance": False,
            },
            "preliminary": {
                "seeds": list(PRELIMINARY_CONFIRMATION_SEEDS),
                "repetition_count": len(PRELIMINARY_CONFIRMATION_SEEDS),
                "status_label": "preliminary_15_of_30",
                "publishable_as_final_confirmation": False,
            },
            "final": {
                "seeds": list(FINAL_CONFIRMATION_SEEDS),
                "repetition_count": len(FINAL_CONFIRMATION_SEEDS),
                "reuses_preliminary_exactly": True,
                "incremental_seeds": list(FINAL_CONFIRMATION_SEEDS[15:]),
            },
        },
        "selection_rule": {
            "within_tolerance": (
                "confirm one simulated point within ±1.5 percentage points when the two-product balance guard passes"
            ),
            "otherwise": (
                "confirm the two adjacent simulated points that bracket the target when both pass the balance guard"
            ),
            "if_no_point_or_bracket": "report target not attained by this isolated family",
            "interpolation_claim_allowed": False,
            "maximum_candidates_per_family_and_target": 2,
        },
        "run_budget": {
            "reference_baseline_runs_reused": 31,
            "new_screening_runs": len(candidates),
            "maximum_selected_candidates": 4 * len(FAMILIES),
            "maximum_new_confirmation_runs_preliminary": (
                4 * len(FAMILIES) * len(PRELIMINARY_CONFIRMATION_SEEDS)
            ),
            "maximum_new_runs_through_preliminary": (
                len(candidates)
                + 4 * len(FAMILIES) * len(PRELIMINARY_CONFIRMATION_SEEDS)
            ),
            "maximum_incremental_runs_preliminary_to_final": (
                4 * len(FAMILIES)
                * (len(FINAL_CONFIRMATION_SEEDS) - len(PRELIMINARY_CONFIRMATION_SEEDS))
            ),
            "maximum_new_runs_through_final": (
                len(candidates) + 4 * len(FAMILIES) * len(FINAL_CONFIRMATION_SEEDS)
            ),
            "observed_reference_throughput_basis": (
                "1255 runs completed in 19h33 with 4 workers"
            ),
            "preliminary_eta_hours_prudent": [6, 8],
            "incremental_final_eta_hours_prudent": [5, 7],
        },
        "resume_contract": {
            "ledger_key": ["scenario_id", "seed"],
            "input_identity_fields": [
                "scenario_id",
                "input_sha256",
                "engine_sha256",
                "profile_sha256",
                "measured_days",
                "warmup_days",
            ],
            "preliminary_seed_set_is_exact_prefix_of_final": (
                FINAL_CONFIRMATION_SEEDS[:15] == PRELIMINARY_CONFIRMATION_SEEDS
            ),
            "existing_valid_rows_are_not_reexecuted": True,
            "different_signature_requires_new_output_directory": True,
        },
        "execution_contract": {
            "implemented_by_this_prepare_only_module": False,
            "engine_base_arguments": [
                "--scenario-id",
                "scn:BASE",
                "--days",
                str(MEASURED_DAYS),
                "--output-profile",
                "compact",
                "--skip-map",
                "--skip-plots",
                "--no-lot-trace",
                "--skip-lot-audit",
                "--common-random-numbers",
            ],
            "profile_arguments_applied_before_managed_arguments": True,
            "managed_reference_protocol_arguments": list(
                MANAGED_REFERENCE_PROTOCOL_ARGS
            ),
            "candidate_execution_inputs_source": "input_inventory.json:execution_inputs",
            "supplier_risk_event_csv_must_be_absent": True,
            "demand_perturbation_csv_must_be_absent": True,
            "control_inputs_must_be_absent": True,
            "structural_candidate_applies_during_warmup": True,
            "acute_incident_layering_allowed_in_this_campaign": False,
        },
        "reference_audit": reference_audit,
        "source_paths": {
            "graph": str(graph_path),
            "engine": str(engine_path),
            "profile": str(profile_path),
            "reference_campaign": str(reference_campaign),
        },
        "outputs": {
            "scenario_design": str(design_path),
            "input_inventory": str(output_dir / "input_inventory.json"),
            "existing_results_audit": str(
                output_dir / "existing_results_audit.json"
            ),
            "business_report": str(output_dir / "AUDIT_ET_PROTOCOLE.md"),
        },
    }
    write_json(output_dir / "input_inventory.json", input_inventory)
    plan_core["plan_signature"] = stable_sha256(
        {
            "schema_version": SCHEMA_VERSION,
            "reference_audit": reference_audit,
            "families": [asdict(family) for family in FAMILIES],
            "candidate_inputs": {
                key: {
                    "input_sha256": value["input_sha256"],
                    "change_ledger_sha256": value["change_ledger_sha256"],
                }
                for key, value in sorted(input_inventory.items())
            },
            "stages": plan_core["stages"],
            "selection_rule": plan_core["selection_rule"],
            "service_definition": plan_core["service_definition"],
            "execution_contract": plan_core["execution_contract"],
        }
    )
    write_json(output_dir / "calibration_plan.json", plan_core)
    (output_dir / "AUDIT_ET_PROTOCOLE.md").write_text(
        _business_report(audit=audit, plan=plan_core), encoding="utf-8"
    )
    return plan_core


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--reference-campaign", type=Path, default=DEFAULT_REFERENCE_CAMPAIGN)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--legacy-combined", type=Path, default=DEFAULT_LEGACY_COMBINED)
    parser.add_argument("--legacy-stock", type=Path, default=DEFAULT_LEGACY_STOCK)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    plan = prepare(
        output_dir=args.output_dir,
        reference_campaign=args.reference_campaign,
        graph_path=args.graph,
        engine_path=args.engine,
        profile_path=args.profile,
        legacy_combined=args.legacy_combined,
        legacy_stock=args.legacy_stock,
    )
    print(
        "[OK] Plan prepared without simulations: "
        f"{Path(args.output_dir).resolve()} ({plan['screening_candidate_count']} candidates)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
