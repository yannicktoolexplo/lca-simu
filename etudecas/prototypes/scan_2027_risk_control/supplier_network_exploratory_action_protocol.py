#!/usr/bin/env python3
"""Build a fail-closed exploratory action-simulation protocol.

The protocol is additive and does not run the simulation engine.  It consumes
the signed V3 post-priority plan, keeps its exact four-lane service group, and
prepares paired ``normal / incident / incident + action`` comparisons.

The first protocol level deliberately distinguishes four physically different
questions:

* a fixed, lane-scoped reduction of *future* transport lead time;
* a quantified stock already present at measured J0 (never an injection during
  the incident);
* a fixed seven-day calendar control over the whole lane in the quality
  scenario, whose quality-delay component is preserved;
* a second source represented only by an explicit counterfactual graph.

Nothing produced here is a recommendation, a supplier probability, a promoted
priority, or a closed-loop claim.  The 15-seed preliminary design is exactly
the prefix of the 30-seed design so completed action runs can be reused.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_post_priority_extensions as post_priority,
)


ARTIFACT_PARENT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
DEFAULT_POST_PRIORITY_PLAN = (
    ARTIFACT_PARENT / "supplier_network_post_priority_extensions_plan_20260903_v3"
)
DEFAULT_OBSERVED_POST_PRIORITY_SMOKE = (
    ARTIFACT_PARENT / "supplier_network_post_priority_extensions_smoke_20260903_v2"
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
DEFAULT_ENGINE = REPO_ROOT / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"
DEFAULT_PROFILE = (
    REPO_ROOT
    / "etudecas"
    / "prototypes"
    / "scan_2027_risk_control"
    / "config"
    / "canonical_real_baseline_engine_profile.json"
)

SCHEMA_VERSION = "etudecas.supplier_network_exploratory_action_protocol.v2"
CONTRACT_REVISION = "four_exact_service_lanes_lotified_stock_honest_costs_2026_09_v5"
PRELIMINARY_REPEAT_COUNT = 15
FINAL_REPEAT_COUNT = 30
SIMULATION_DAYS = 720
BUFFER_COVER_DAYS = 14
TRANSPORT_REDUCTION_DAYS = 7
EXPECTED_LANE_COUNT = 4
EXPECTED_LEVERS = (
    "future_lane_transport_reduction",
    "prepositioned_free_stock_14d",
    "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d",
    "explicit_counterfactual_alternative_source",
)
EXPECTED_FAILURE_MODES = {
    "future_lane_transport_reduction": "transport_delay",
    "prepositioned_free_stock_14d": "supply_availability",
    "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d": "quality_hold",
    "explicit_counterfactual_alternative_source": "supply_availability",
}
LEVER_LABELS_FR = {
    "future_lane_transport_reduction": (
        "Réduction calendaire open-loop de 7 jours du transport sur toute la voie"
    ),
    "prepositioned_free_stock_14d": (
        "Stock déjà présent à J0, cible brute de 14 jours puis arrondie par lot"
    ),
    "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d": (
        "Scénario qualité — réduction calendaire open-loop de 7 jours du transport "
        "sur toute la voie"
    ),
    "explicit_counterfactual_alternative_source": (
        "Seconde source qualifiée décrite dans un graphe contrefactuel explicite"
    ),
}
PLAN_FILES = (
    "action_lever_parameters.csv",
    "paired_experiment_design.csv",
    "alternative_source_graph_requirements.csv",
    "execution_budget.json",
    "scientific_controls.json",
    "PROTOCOL.md",
    "exploratory_action_protocol_manifest.json",
)
IMMUTABLE_PLAN_FILES = tuple(
    name for name in PLAN_FILES if name != "exploratory_action_protocol_manifest.json"
)


@dataclass(frozen=True)
class Lane:
    selection_slot: int
    chain_id: str
    supplier_id: str
    item_id: str
    dst_node_id: str
    edge_id: str
    target_product_id: str
    active_window_start_day: int
    active_window_end_day: int
    active_window_pulled_qty: float
    inventory_initial_qty: float
    inventory_uom: str
    holding_cost_model_per_unit_day: float
    graph_transport_cost_model_per_unit: float | None
    graph_lead_time_mean_days: float
    procurement_standard_order_qty: float | None
    procurement_standard_order_uom: str
    procurement_standard_order_source: str
    procurement_min_order_qty: float | None
    procurement_min_order_source: str
    procurement_lot_multiple_qty: float | None
    procurement_lot_multiple_source: str
    procurement_max_order_qty: float | None
    procurement_max_order_source: str


@dataclass(frozen=True)
class ProtocolContext:
    plan_dir: Path
    source_dir: Path
    plan_manifest: Mapping[str, Any]
    source_manifest: Mapping[str, Any]
    lanes: tuple[Lane, ...]
    seeds: tuple[int, ...]
    severe_cases: Mapping[tuple[str, str], Mapping[str, str]]
    source_severe_cases: Mapping[tuple[str, str], Mapping[str, str]]
    graph: Mapping[str, Any]
    graph_path: Path
    engine_path: Path
    profile_path: Path
    alternative_by_chain: Mapping[str, Mapping[str, Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "oui"}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"Objet JSON attendu: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"CSV vide refusé: {path.name}")
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen:
                seen.add(field)
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _signature(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _required_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} absent: {resolved}")
    return resolved


def _edge_keys(edge: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    source = str(edge.get("from") or "")
    destination = str(edge.get("to") or "")
    return [
        (source, str(item), destination)
        for item in edge.get("items") or []
        if source and destination and str(item)
    ]


def _positive_constraint(
    edge: Mapping[str, Any], *field_names: str
) -> tuple[float | None, str]:
    """Return one positive procurement constraint and its exact graph path."""

    for container_name in ("order_terms", "attrs"):
        container = edge.get(container_name) or {}
        if not isinstance(container, Mapping):
            continue
        for field_name in field_names:
            raw = container.get(field_name)
            if raw is None or str(raw).strip() == "":
                continue
            value = _to_float(raw, -1.0)
            if value <= 0.0:
                raise ValueError(
                    f"Contrainte d'approvisionnement non positive: "
                    f"edge.{container_name}.{field_name}={raw}"
                )
            return value, f"edge.{container_name}.{field_name}"
    return None, ""


def _ceil_lot_count(quantity: float, lot_qty: float) -> int:
    if quantity <= 0.0 or lot_qty <= 0.0:
        raise ValueError("Quantité et lot doivent être strictement positifs.")
    return max(1, int(math.ceil((quantity / lot_qty) - 1e-12)))


def _inventory_state(
    graph: Mapping[str, Any], *, node_id: str, item_id: str
) -> Mapping[str, Any]:
    candidates = []
    for node in graph.get("nodes") or []:
        if str(node.get("id") or "") != node_id:
            continue
        candidates.extend(
            state
            for state in (node.get("inventory") or {}).get("states") or []
            if str(state.get("item_id") or "") == item_id
        )
    if len(candidates) != 1:
        raise ValueError(
            f"Un état de stock exact attendu pour {node_id}/{item_id}, trouvé={len(candidates)}"
        )
    return candidates[0]


def _graph_edge(
    graph: Mapping[str, Any], *, supplier_id: str, item_id: str, dst_node_id: str
) -> Mapping[str, Any]:
    matches = [
        edge
        for edge in graph.get("edges") or []
        if (supplier_id, item_id, dst_node_id) in _edge_keys(edge)
    ]
    if len(matches) != 1:
        raise ValueError(
            "Une voie graphe exacte attendue pour "
            f"{supplier_id}/{item_id}/{dst_node_id}, trouvé={len(matches)}"
        )
    return matches[0]


def _index_unique(
    rows: Sequence[Mapping[str, str]], fields: Sequence[str], *, label: str
) -> dict[tuple[str, ...], Mapping[str, str]]:
    output: dict[tuple[str, ...], Mapping[str, str]] = {}
    for row in rows:
        key = tuple(str(row.get(field) or "") for field in fields)
        if not all(key):
            continue
        if key in output:
            raise ValueError(f"{label} dupliqué: {key}")
        output[key] = row
    return output


def _load_alternative_register(
    path: Path | None,
    *,
    graph: Mapping[str, Any],
    chain_ids: set[str],
) -> dict[str, Mapping[str, Any]]:
    if path is None:
        return {}
    rows = _read_csv(_required_file(path, "registre de sources alternatives"))
    required = {
        "chain_id",
        "alternative_supplier_id",
        "qualification_evidence_ref",
        "counterfactual_edge_id",
        "lead_time_mean_days",
        "lead_time_stages",
        "distance_km",
        "transport_cost_model_per_unit",
        "quantity_uom",
        "allocation_contract",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError(
            "Le registre alternatif doit contenir: " + ", ".join(sorted(required))
        )
    by_chain: dict[str, Mapping[str, Any]] = {}
    graph_node_ids = {str(node.get("id") or "") for node in graph.get("nodes") or []}
    graph_edge_ids = {str(edge.get("id") or "") for edge in graph.get("edges") or []}
    for row in rows:
        chain_id = str(row.get("chain_id") or "")
        if chain_id not in chain_ids or chain_id in by_chain:
            raise ValueError(f"Chaîne alternative absente ou dupliquée: {chain_id}")
        alternative = str(row.get("alternative_supplier_id") or "")
        if alternative not in graph_node_ids:
            raise ValueError(f"Le fournisseur alternatif n'est pas un nœud du graphe: {alternative}")
        evidence = str(row.get("qualification_evidence_ref") or "").strip()
        if not evidence:
            raise ValueError(f"Preuve de qualification absente: {chain_id}")
        edge_id = str(row.get("counterfactual_edge_id") or "").strip()
        if not edge_id or edge_id in graph_edge_ids:
            raise ValueError(f"Identifiant d'arête contrefactuelle absent ou déjà utilisé: {chain_id}")
        positive_fields = (
            "lead_time_mean_days",
            "lead_time_stages",
            "distance_km",
            "transport_cost_model_per_unit",
        )
        if any(_to_float(row.get(field), -1.0) < 0.0 for field in positive_fields):
            raise ValueError(f"Paramètre alternatif négatif: {chain_id}")
        if _to_int(row.get("lead_time_stages"), 0) <= 0:
            raise ValueError(f"Nombre d'étapes de délai alternatif invalide: {chain_id}")
        if str(row.get("allocation_contract") or "") != "legacy_capacity_weighted_after_graph_addition":
            raise ValueError(f"Règle d'allocation alternative non revue: {chain_id}")
        by_chain[chain_id] = dict(row)
    return by_chain


def load_context(
    *,
    post_priority_plan: Path,
    graph: Path,
    engine: Path,
    profile: Path,
    alternative_source_register: Path | None = None,
) -> ProtocolContext:
    plan_dir = post_priority_plan.resolve()
    post_priority.validate_plan_artifact(plan_dir, require_boundary_lineage=True)
    manifest_path = _required_file(
        plan_dir / "post_priority_extensions_plan_manifest.json", "manifeste V3"
    )
    plan_manifest = _read_json(manifest_path)
    if str(plan_manifest.get("status") or "") != "planned_not_executed":
        raise ValueError("Le plan V3 doit rester un plan non exécuté.")
    lineage = plan_manifest.get("priority_selection_lineage") or {}
    supplier_ids = [str(value) for value in lineage.get("follow_up_supplier_ids") or []]
    chain_ids = [str(value) for value in lineage.get("follow_up_chain_ids") or []]
    if (
        len(supplier_ids) != EXPECTED_LANE_COUNT
        or len(chain_ids) != EXPECTED_LANE_COUNT
        or len(set(supplier_ids)) != EXPECTED_LANE_COUNT
        or len(set(chain_ids)) != EXPECTED_LANE_COUNT
    ):
        raise ValueError("Le protocole exige exactement les quatre voies du groupe service V3.")

    source_dir = Path(str(plan_manifest.get("source_artifact") or "")).resolve()
    source_manifest = _read_json(_required_file(source_dir / "campaign_manifest.json", "campagne source"))
    if str(source_manifest.get("status") or "") != "complete":
        raise ValueError("La campagne réseau source doit être complète.")
    seeds = tuple(_to_int(value, -1) for value in plan_manifest.get("confirmation_seeds") or [])
    if len(seeds) != FINAL_REPEAT_COUNT or len(set(seeds)) != FINAL_REPEAT_COUNT or min(seeds) < 0:
        raise ValueError("Le protocole exige exactement 30 graines appariées distinctes.")

    graph_path = _required_file(graph, "graphe")
    engine_path = _required_file(engine, "moteur")
    profile_path = _required_file(profile, "profil moteur")
    lock = plan_manifest.get("execution_configuration_lock") or {}
    for field, path in (
        ("graph_sha256", graph_path),
        ("engine_sha256", engine_path),
        ("profile_sha256", profile_path),
    ):
        if str(lock.get(field) or "") != _sha256(path):
            raise ValueError(f"Entrée différente de la configuration V3: {field}")
    graph_payload = _read_json(graph_path)

    active_rows = _read_csv(_required_file(source_dir / "active_lane_reference.csv", "voies actives"))
    active_by_chain = _index_unique(active_rows, ("chain_id",), label="voie active")
    temporal_rows = _read_csv(_required_file(plan_dir / "temporal_robustness_design.csv", "design temporel"))
    temporal_by_chain: dict[str, Mapping[str, str]] = {}
    for chain_id in chain_ids:
        candidates = [row for row in temporal_rows if str(row.get("chain_id") or "") == chain_id]
        if not candidates:
            raise ValueError(f"Voie V3 absente du design temporel: {chain_id}")
        temporal_by_chain[chain_id] = candidates[0]

    lanes: list[Lane] = []
    for slot, chain_id in enumerate(chain_ids, 1):
        active = active_by_chain.get((chain_id,))
        selected = temporal_by_chain[chain_id]
        if active is None:
            raise ValueError(f"Voie active source absente: {chain_id}")
        supplier_id = str(selected.get("supplier_id") or "")
        if supplier_id not in supplier_ids:
            raise ValueError(f"Fournisseur de voie hors groupe V3: {supplier_id}")
        item_id = str(selected.get("item_id") or "")
        destination = str(selected.get("dst_node_id") or "")
        edge = _graph_edge(
            graph_payload,
            supplier_id=supplier_id,
            item_id=item_id,
            dst_node_id=destination,
        )
        same_target = [
            key for candidate in graph_payload.get("edges") or [] for key in _edge_keys(candidate)
            if key[1:] == (item_id, destination)
        ]
        if len(same_target) != 1:
            raise ValueError(
                f"La voie {chain_id} n'est plus mono-source dans le graphe de référence."
            )
        state = _inventory_state(graph_payload, node_id=destination, item_id=item_id)
        state_uom = str(state.get("uom") or "")
        edge_uom = str((edge.get("order_terms") or {}).get("quantity_unit") or "")
        if not state_uom or state_uom != edge_uom:
            raise ValueError(f"Unité stock/voie incohérente: {chain_id}")
        standard_order_qty, standard_order_source = _positive_constraint(
            edge, "standard_order_qty"
        )
        min_order_qty, min_order_source = _positive_constraint(
            edge, "min_order_qty", "minimum_order_qty"
        )
        lot_multiple_qty, lot_multiple_source = _positive_constraint(
            edge, "lot_multiple_qty", "order_multiple_qty"
        )
        max_order_qty, max_order_source = _positive_constraint(
            edge, "max_order_qty", "maximum_order_qty"
        )
        standard_order_uom = str((edge.get("attrs") or {}).get("standard_order_uom") or edge_uom)
        if standard_order_qty is not None and standard_order_uom != state_uom:
            raise ValueError(f"Unité du lot standard incohérente: {chain_id}")
        holding = state.get("holding_cost") or {}
        transport_cost = edge.get("transport_cost") or {}
        lanes.append(
            Lane(
                selection_slot=slot,
                chain_id=chain_id,
                supplier_id=supplier_id,
                item_id=item_id,
                dst_node_id=destination,
                edge_id=str(edge.get("id") or ""),
                target_product_id=str(selected.get("target_product_id") or ""),
                active_window_start_day=_to_int(active.get("active_window_start_day"), -1),
                active_window_end_day=_to_int(active.get("active_window_end_day"), -1),
                active_window_pulled_qty=_to_float(active.get("reference_active_window_pulled_qty")),
                inventory_initial_qty=_to_float(state.get("initial")),
                inventory_uom=state_uom,
                holding_cost_model_per_unit_day=_to_float(holding.get("value")),
                graph_transport_cost_model_per_unit=(
                    _to_float(transport_cost.get("value"))
                    if str(transport_cost.get("value") or "").strip()
                    else None
                ),
                graph_lead_time_mean_days=_to_float((edge.get("lead_time") or {}).get("mean")),
                procurement_standard_order_qty=standard_order_qty,
                procurement_standard_order_uom=standard_order_uom,
                procurement_standard_order_source=standard_order_source,
                procurement_min_order_qty=min_order_qty,
                procurement_min_order_source=min_order_source,
                procurement_lot_multiple_qty=lot_multiple_qty,
                procurement_lot_multiple_source=lot_multiple_source,
                procurement_max_order_qty=max_order_qty,
                procurement_max_order_source=max_order_source,
            )
        )
    if {lane.supplier_id for lane in lanes} != set(supplier_ids):
        raise ValueError("Les quatre fournisseurs et les quatre voies V3 ne correspondent pas exactement.")

    four_rows = _read_csv(
        _required_file(
            plan_dir / "priority_four_business_causes_design.csv",
            "design quatre causes V3",
        )
    )
    severe_cases: dict[tuple[str, str], Mapping[str, str]] = {}
    for chain_id in chain_ids:
        for failure_mode in set(EXPECTED_FAILURE_MODES.values()):
            rows = [
                row
                for row in four_rows
                if str(row.get("chain_id") or "") == chain_id
                and str(row.get("failure_mode") or "") == failure_mode
            ]
            if len(rows) != FINAL_REPEAT_COUNT:
                raise ValueError(f"Design V3 incomplet pour {chain_id}/{failure_mode}")
            first = rows[0]
            invariant = (
                "case_id",
                "risk_type",
                "mechanism_value",
                "mechanism_unit",
                "stress_start_day",
                "stress_end_day",
            )
            if any(any(str(row.get(field)) != str(first.get(field)) for field in invariant) for row in rows):
                raise ValueError(f"Paramètres V3 variables dans {chain_id}/{failure_mode}")
            severe_cases[(chain_id, failure_mode)] = first

    source_scenario_rows = _read_csv(_required_file(source_dir / "scenario_design.csv", "scénarios source"))
    source_severe_cases = _index_unique(
        [row for row in source_scenario_rows if str(row.get("level_code") or "") == "severe"],
        ("chain_id", "failure_mode"),
        label="scénario source sévère",
    )
    alternative_by_chain = _load_alternative_register(
        alternative_source_register,
        graph=graph_payload,
        chain_ids=set(chain_ids),
    )
    return ProtocolContext(
        plan_dir=plan_dir,
        source_dir=source_dir,
        plan_manifest=plan_manifest,
        source_manifest=source_manifest,
        lanes=tuple(lanes),
        seeds=seeds,
        severe_cases=severe_cases,
        source_severe_cases=source_severe_cases,
        graph=graph_payload,
        graph_path=graph_path,
        engine_path=engine_path,
        profile_path=profile_path,
        alternative_by_chain=alternative_by_chain,
    )


def build_lever_parameters(context: ProtocolContext) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane in context.lanes:
        average_daily_pull = lane.active_window_pulled_qty / 180.0
        buffer_raw_qty = average_daily_pull * BUFFER_COVER_DAYS
        effective_lot_qty = (
            lane.procurement_lot_multiple_qty or lane.procurement_standard_order_qty
        )
        effective_lot_source = (
            lane.procurement_lot_multiple_source
            if lane.procurement_lot_multiple_qty is not None
            else lane.procurement_standard_order_source
        )
        if effective_lot_qty is None:
            raise ValueError(
                "Lotification du stock impossible sans multiple explicite ni quantité "
                f"standard pour {lane.chain_id}"
            )
        quantity_before_rounding = max(
            buffer_raw_qty, lane.procurement_min_order_qty or 0.0
        )
        buffer_lot_count = _ceil_lot_count(quantity_before_rounding, effective_lot_qty)
        buffer_rounded_qty = buffer_lot_count * effective_lot_qty
        max_constraint_satisfied: bool | str = ""
        if lane.procurement_max_order_qty is not None:
            max_constraint_satisfied = (
                buffer_rounded_qty <= lane.procurement_max_order_qty + 1e-9
            )
        missing_constraints = [
            label
            for label, value in (
                ("moq", lane.procurement_min_order_qty),
                ("explicit_multiple", lane.procurement_lot_multiple_qty),
                ("max_order", lane.procurement_max_order_qty),
            )
            if value is None
        ]
        for lever_id in EXPECTED_LEVERS:
            mode = EXPECTED_FAILURE_MODES[lever_id]
            incident = context.severe_cases[(lane.chain_id, mode)]
            start = _to_int(incident.get("stress_start_day"), -1)
            end = _to_int(incident.get("stress_end_day"), -1)
            if start < 0 or end < start or end >= SIMULATION_DAYS:
                raise ValueError(f"Fenêtre d'incident invalide: {lane.chain_id}/{mode}")
            alternative = context.alternative_by_chain.get(lane.chain_id)
            row: dict[str, Any] = {
                "selection_slot": lane.selection_slot,
                "slot_order_has_scientific_meaning": False,
                "chain_id": lane.chain_id,
                "supplier_id": lane.supplier_id,
                "item_id": lane.item_id,
                "dst_node_id": lane.dst_node_id,
                "edge_id": lane.edge_id,
                "target_product_id": lane.target_product_id,
                "lever_id": lever_id,
                "lever_label_fr": LEVER_LABELS_FR[lever_id],
                "incident_failure_mode": mode,
                "incident_risk_type": str(incident.get("risk_type") or ""),
                "incident_value": _to_float(incident.get("mechanism_value")),
                "incident_unit": str(incident.get("mechanism_unit") or ""),
                "incident_start_day": start,
                "incident_end_day": end,
                "simulation_days": SIMULATION_DAYS,
                "action_level_count": 1,
                "action_timing": "",
                "control_scope": "",
                "control_start_day": "",
                "control_end_day": "",
                "lead_time_adjustment_days": "",
                "buffer_cover_days": "",
                "buffer_raw_qty": "",
                "buffer_additional_qty": "",
                "buffer_rounded_qty": "",
                "buffer_procurement_lot_count": "",
                "buffer_uom": "",
                "buffer_quantity_basis": "",
                "procurement_standard_lot_qty": "",
                "procurement_moq_qty": "",
                "procurement_explicit_multiple_qty": "",
                "procurement_max_order_qty": "",
                "procurement_effective_rounding_lot_qty": "",
                "procurement_constraint_uom": "",
                "procurement_constraint_sources": "",
                "procurement_constraints_not_in_graph": "",
                "procurement_max_constraint_satisfied": "",
                "buffer_rounding_rule": "",
                "paired_j0_stock_requirement": "",
                "stock_present_at_j0_hypothesis": "",
                "stock_acquisition_simulated": "",
                "stock_procurement_lead_time_simulated": "",
                "stock_procurement_cost_simulated": "",
                "alternative_supplier_id": "",
                "counterfactual_edge_id": "",
                "graph_counterfactual_required": False,
                "priority_weight_used": False,
                "closed_loop_claimed": False,
                "identified_shipment_claimed": False,
                "identified_lot_claimed": False,
                "quality_hold_reduction_claimed": False,
                "new_action_run_status": "",
                "blocking_reason": "",
                "model_cost_value": "",
                "model_cost_unit": "",
                "industrial_cost_status": "not_estimated_missing_industrial_cost_inputs",
                "industrial_action_cost_available": False,
                "incremental_holding_cost_status": "not_applicable",
                "incremental_holding_cost_formula": "",
                "graph_holding_cost_model_input_per_unit_day": "",
                "graph_holding_cost_model_input_unit": "",
                "graph_transport_cost_model_input_per_unit": "",
                "static_720_day_holding_cost_published": False,
                "not_a_recommendation": True,
                "action_promotion_allowed": False,
            }
            if lever_id == "future_lane_transport_reduction":
                row.update(
                    {
                        "action_timing": "fixed_open_loop_future_lane_dispatches",
                        "control_scope": "supplier_id+item_id+dst_node_id",
                        "control_start_day": start,
                        "control_end_day": end,
                        "lead_time_adjustment_days": -TRANSPORT_REDUCTION_DAYS,
                        "new_action_run_status": "planned_new_run",
                    }
                )
            elif lever_id == "prepositioned_free_stock_14d":
                if buffer_raw_qty <= 0.0 or not lane.inventory_uom:
                    raise ValueError(f"Tampon non chiffrable pour {lane.chain_id}")
                constraint_sources = sorted(
                    source
                    for source in {
                        lane.procurement_standard_order_source,
                        lane.procurement_min_order_source,
                        lane.procurement_lot_multiple_source,
                        lane.procurement_max_order_source,
                        effective_lot_source,
                    }
                    if source
                )
                stock_status = "conditional_positive_paired_J0_stock"
                stock_blocking_reason = ""
                if max_constraint_satisfied is False:
                    stock_status = "blocked_rounded_buffer_exceeds_graph_max_order_qty"
                    stock_blocking_reason = (
                        "rounded_J0_buffer_exceeds_single_graph_max_order_qty; "
                        "split_order_or_exception_not_simulated"
                    )
                row.update(
                    {
                        "action_timing": "already_present_at_measured_J0_before_incident_hypothesis",
                        "control_scope": "dst_node_id+item_id",
                        "buffer_cover_days": BUFFER_COVER_DAYS,
                        "buffer_raw_qty": round(buffer_raw_qty, 9),
                        "buffer_additional_qty": round(buffer_rounded_qty, 9),
                        "buffer_rounded_qty": round(buffer_rounded_qty, 9),
                        "buffer_procurement_lot_count": buffer_lot_count,
                        "buffer_uom": lane.inventory_uom,
                        "buffer_quantity_basis": "14_days_of_simulated_active_window_average_pull",
                        "procurement_standard_lot_qty": (
                            round(lane.procurement_standard_order_qty, 9)
                            if lane.procurement_standard_order_qty is not None
                            else ""
                        ),
                        "procurement_moq_qty": (
                            round(lane.procurement_min_order_qty, 9)
                            if lane.procurement_min_order_qty is not None
                            else ""
                        ),
                        "procurement_explicit_multiple_qty": (
                            round(lane.procurement_lot_multiple_qty, 9)
                            if lane.procurement_lot_multiple_qty is not None
                            else ""
                        ),
                        "procurement_max_order_qty": (
                            round(lane.procurement_max_order_qty, 9)
                            if lane.procurement_max_order_qty is not None
                            else ""
                        ),
                        "procurement_effective_rounding_lot_qty": round(
                            effective_lot_qty, 9
                        ),
                        "procurement_constraint_uom": lane.procurement_standard_order_uom,
                        "procurement_constraint_sources": ";".join(constraint_sources),
                        "procurement_constraints_not_in_graph": ";".join(
                            missing_constraints
                        ),
                        "procurement_max_constraint_satisfied": max_constraint_satisfied,
                        "buffer_rounding_rule": (
                            "target=max(raw_14d,graph_moq_if_present); "
                            "rounded=ceil(target/effective_lot)*effective_lot; "
                            "effective_lot=explicit_graph_multiple_else_graph_standard_order_qty"
                        ),
                        "paired_j0_stock_requirement": (
                            "per_seed_positive_free_stock_then_scale=(J0+buffer_rounded_qty)/J0; "
                            "zero_J0_is_blocked"
                        ),
                        "stock_present_at_j0_hypothesis": True,
                        "stock_acquisition_simulated": False,
                        "stock_procurement_lead_time_simulated": False,
                        "stock_procurement_cost_simulated": False,
                        "new_action_run_status": stock_status,
                        "blocking_reason": stock_blocking_reason,
                        "incremental_holding_cost_status": (
                            "not_computed_requires_future_incremental_inventory_trajectory_"
                            "and_validated_industrial_unit_value_and_carry_rate"
                        ),
                        "incremental_holding_cost_formula": (
                            "sum_day(max(stock_action-stock_incident_no_action,0)*"
                            "validated_industrial_holding_cost_per_unit_day)"
                        ),
                        "graph_holding_cost_model_input_per_unit_day": round(
                            lane.holding_cost_model_per_unit_day, 12
                        ),
                        "graph_holding_cost_model_input_unit": (
                            f"model_value_unit_per_{lane.inventory_uom}_day_not_action_cost"
                        ),
                    }
                )
            elif lever_id == (
                "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d"
            ):
                row.update(
                    {
                        "action_timing": (
                            "fixed_calendar_open_loop_whole_lane_in_quality_scenario"
                        ),
                        "control_scope": (
                            "supplier_id+item_id+dst_node_id+all_future_dispatches_in_window"
                        ),
                        "control_start_day": start,
                        "control_end_day": end,
                        "lead_time_adjustment_days": -TRANSPORT_REDUCTION_DAYS,
                        "new_action_run_status": "planned_after_V3_quality_pair_available",
                    }
                )
            else:
                row["graph_counterfactual_required"] = True
                if alternative is None:
                    row.update(
                        {
                            "action_timing": "prepared_before_incident",
                            "new_action_run_status": "blocked_missing_explicit_alternative_source_register",
                            "blocking_reason": (
                                "reference_graph_is_mono_source_and_no_qualified_counterfactual_edge_is_supplied"
                            ),
                        }
                    )
                else:
                    alternative_supplier = str(alternative.get("alternative_supplier_id") or "")
                    if alternative_supplier == lane.supplier_id:
                        raise ValueError(f"La source alternative égale la source initiale: {lane.chain_id}")
                    quantity_uom = str(alternative.get("quantity_uom") or "")
                    if quantity_uom != lane.inventory_uom:
                        raise ValueError(f"Unité alternative incohérente: {lane.chain_id}")
                    row.update(
                        {
                            "action_timing": "counterfactual_graph_prepared_before_incident",
                            "alternative_supplier_id": alternative_supplier,
                            "counterfactual_edge_id": str(alternative.get("counterfactual_edge_id") or ""),
                            "new_action_run_status": "conditional_explicit_graph_counterfactual",
                            "graph_transport_cost_model_input_per_unit": _to_float(
                                alternative.get("transport_cost_model_per_unit")
                            ),
                        }
                    )
            rows.append(row)
    rows.sort(key=lambda row: (_to_int(row["selection_slot"]), EXPECTED_LEVERS.index(str(row["lever_id"]))))
    return rows


def build_alternative_requirements(
    context: ProtocolContext, parameters: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_chain = {lane.chain_id: lane for lane in context.lanes}
    for parameter in parameters:
        if str(parameter.get("lever_id")) != "explicit_counterfactual_alternative_source":
            continue
        lane = by_chain[str(parameter["chain_id"])]
        alternative = context.alternative_by_chain.get(lane.chain_id) or {}
        rows.append(
            {
                "chain_id": lane.chain_id,
                "incumbent_supplier_id": lane.supplier_id,
                "item_id": lane.item_id,
                "dst_node_id": lane.dst_node_id,
                "reference_edge_id": lane.edge_id,
                "reference_graph_source_count_for_item_destination": 1,
                "alternative_supplier_id": str(alternative.get("alternative_supplier_id") or ""),
                "qualification_evidence_ref": str(alternative.get("qualification_evidence_ref") or ""),
                "counterfactual_edge_id": str(alternative.get("counterfactual_edge_id") or ""),
                "lead_time_mean_days": str(alternative.get("lead_time_mean_days") or ""),
                "lead_time_stages": str(alternative.get("lead_time_stages") or ""),
                "distance_km": str(alternative.get("distance_km") or ""),
                "transport_cost_model_per_unit": str(
                    alternative.get("transport_cost_model_per_unit") or ""
                ),
                "quantity_uom": str(alternative.get("quantity_uom") or ""),
                "allocation_contract": str(alternative.get("allocation_contract") or ""),
                "graph_patch_status": (
                    "specified_not_materialized"
                    if alternative
                    else "blocked_missing_operational_register"
                ),
                "priority_weight_used": False,
                "baseline_graph_sha256": _sha256(context.graph_path),
                "normal_base_graph_required": True,
                "incident_no_action_base_graph_required": True,
                "incident_action_counterfactual_graph_required": True,
                "structural_normal_counterfactual_control_recommended": True,
                "not_a_recommendation": True,
            }
        )
    return rows


def _source_case_id(context: ProtocolContext, *, chain_id: str, mode: str) -> str:
    if mode in {"transport_delay", "supply_availability"}:
        source = context.source_severe_cases.get((chain_id, mode))
        if source is None:
            raise ValueError(f"Cas source sévère absent: {chain_id}/{mode}")
        return str(source.get("scenario_id") or "")
    return str(context.severe_cases[(chain_id, mode)].get("case_id") or "")


def build_experiment_design(
    context: ProtocolContext, parameters: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for parameter in parameters:
        chain_id = str(parameter["chain_id"])
        lever_id = str(parameter["lever_id"])
        failure_mode = str(parameter["incident_failure_mode"])
        status = str(parameter["new_action_run_status"])
        blocked = status.startswith("blocked_")
        no_action_case = _source_case_id(context, chain_id=chain_id, mode=failure_mode)
        for seed_index, seed in enumerate(context.seeds, 1):
            pairing_id = f"{chain_id}__{lever_id}__seed_{seed}"
            for arm in ("normal", "incident_no_action", "incident_with_action"):
                if arm == "normal":
                    source_kind = "reuse_network_confirmation_baseline"
                    source_case_id = "baseline_nominal"
                    run_status = "logical_alias_existing_source"
                    new_run = 0
                elif arm == "incident_no_action":
                    source_kind = (
                        "reuse_network_confirmation_case"
                        if failure_mode in {"transport_delay", "supply_availability"}
                        else "reuse_V3_four_cause_case_when_complete"
                    )
                    source_case_id = no_action_case
                    run_status = "logical_alias_existing_or_pending_source"
                    new_run = 0
                else:
                    source_kind = "new_action_simulation"
                    source_case_id = ""
                    run_status = status
                    new_run = 0 if blocked else 1
                rows.append(
                    {
                        "pairing_id": pairing_id,
                        "seed": seed,
                        "seed_prefix_index": seed_index,
                        "included_in_preliminary_15": seed_index <= PRELIMINARY_REPEAT_COUNT,
                        "included_in_final_30": True,
                        "selection_slot": parameter["selection_slot"],
                        "slot_order_has_scientific_meaning": False,
                        "chain_id": chain_id,
                        "supplier_id": parameter["supplier_id"],
                        "item_id": parameter["item_id"],
                        "dst_node_id": parameter["dst_node_id"],
                        "target_product_id": parameter["target_product_id"],
                        "lever_id": lever_id,
                        "failure_mode": failure_mode,
                        "arm": arm,
                        "source_kind": source_kind,
                        "source_case_id": source_case_id,
                        "new_engine_run_count": new_run,
                        "execution_status": run_status,
                        "risk_event_exogenous_hypothesis": arm != "normal",
                        "action_applied": arm == "incident_with_action",
                        "graph_counterfactual": (
                            arm == "incident_with_action"
                            and _as_bool(parameter.get("graph_counterfactual_required"))
                        ),
                        "priority_weight_used": False,
                        "closed_loop_claimed": False,
                        "historical_probability_estimated": False,
                        "industrial_cost_estimated": False,
                        "action_promotion_allowed": False,
                        "not_a_recommendation": True,
                    }
                )
    rows.sort(
        key=lambda row: (
            _to_int(row["selection_slot"]),
            EXPECTED_LEVERS.index(str(row["lever_id"])),
            _to_int(row["seed_prefix_index"]),
            ("normal", "incident_no_action", "incident_with_action").index(str(row["arm"])),
        )
    )
    return rows


def _elapsed_hours(start: str, end: str) -> float:
    try:
        return (
            datetime.fromisoformat(end) - datetime.fromisoformat(start)
        ).total_seconds() / 3600.0
    except (TypeError, ValueError):
        return 0.0


def build_execution_budget(
    context: ProtocolContext,
    design: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    main_start = str(context.source_manifest.get("created_or_resumed_at_utc") or "")
    main_end = str(context.source_manifest.get("completed_at_utc") or "")
    main_hours = _elapsed_hours(main_start, main_end)
    main_runs = _to_int((context.source_manifest.get("planned_run_counts") or {}).get("full"), 0)
    main_rate = main_runs / main_hours if main_hours > 0 and main_runs > 0 else 0.0
    throughput_observations: list[dict[str, Any]] = [
        {
            "source": str(context.source_dir),
            "kind": "completed_network_campaign",
            "completed_physical_run_count": main_runs,
            "elapsed_hours": round(main_hours, 6),
            "runs_per_hour": round(main_rate, 6),
        }
    ]
    smoke_dir = DEFAULT_OBSERVED_POST_PRIORITY_SMOKE
    smoke_manifest_path = smoke_dir / "post_priority_extension_runner_manifest.json"
    if smoke_manifest_path.is_file():
        smoke_manifest = _read_json(smoke_manifest_path)
        smoke_hours = _elapsed_hours(
            str(smoke_manifest.get("created_or_resumed_at_utc") or ""),
            str(smoke_manifest.get("completed_at_utc") or ""),
        )
        smoke_completed = _to_int(
            smoke_manifest.get("executed_engine_case_count"), 0
        )
        smoke_rate = smoke_completed / smoke_hours if smoke_hours > 0 else 0.0
        smoke_is_complete = (
            str(smoke_manifest.get("status") or "") == "complete"
            and str(smoke_manifest.get("mode") or "") == "smoke"
            and smoke_completed > 0
            and smoke_completed
            == _to_int(smoke_manifest.get("expected_engine_physical_run_count"), -1)
            and _to_int(smoke_manifest.get("remaining_engine_physical_run_count"), -1)
            == 0
        )
        if smoke_is_complete and smoke_rate > 0:
            throughput_observations.append(
                {
                    "source": str(smoke_dir),
                    "kind": "completed_post_priority_smoke_v2_small_sample",
                    "manifest_sha256": _sha256(smoke_manifest_path),
                    "completed_physical_run_count": smoke_completed,
                    "elapsed_hours": round(smoke_hours, 6),
                    "runs_per_hour": round(smoke_rate, 6),
                    "small_sample_warning": True,
                    "included_in_planning_rate": False,
                    "exclusion_reason": (
                        "five_run_smoke_is_too_small_and_not_comparable_to_the_full_campaign"
                    ),
                }
            )
    planning_rate = main_rate if main_rate > 0 else 64.0

    def count_new(prefix: int, lever_ids: set[str]) -> int:
        return sum(
            _to_int(row.get("new_engine_run_count"), 0)
            for row in design
            if _to_int(row.get("seed_prefix_index"), 10**9) <= prefix
            and str(row.get("lever_id")) in lever_ids
        )

    parameterized_transport = {"future_lane_transport_reduction"}
    quality_waiting_for_v3 = {
        "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d"
    }
    stock = {"prepositioned_free_stock_14d"}
    alternative = {"explicit_counterfactual_alternative_source"}
    all_non_alt = parameterized_transport | quality_waiting_for_v3 | stock
    all_levers = all_non_alt | alternative

    def estimate(run_count: int) -> dict[str, float | bool]:
        return {
            "point_estimate_hours_at_completed_campaign_rate": round(
                run_count / planning_rate, 3
            ),
            "planning_range_claimed": False,
        }

    preliminary_counts = {
        "parameterized_transport_new_action_runs": count_new(
            PRELIMINARY_REPEAT_COUNT, parameterized_transport
        ),
        "quality_new_action_runs_waiting_for_V3_pair": count_new(
            PRELIMINARY_REPEAT_COUNT, quality_waiting_for_v3
        ),
        "conditional_stock_new_action_runs_max": count_new(PRELIMINARY_REPEAT_COUNT, stock),
        "alternative_new_action_runs_currently_executable": count_new(
            PRELIMINARY_REPEAT_COUNT, alternative
        ),
        "potential_alternative_new_action_runs_after_valid_register": (
            EXPECTED_LANE_COUNT * PRELIMINARY_REPEAT_COUNT
        ),
        "maximum_new_action_runs_without_alternative": count_new(PRELIMINARY_REPEAT_COUNT, all_non_alt),
        "currently_planned_new_action_runs_all_levers": count_new(
            PRELIMINARY_REPEAT_COUNT, all_levers
        ),
    }
    final_counts = {
        "parameterized_transport_new_action_runs": count_new(
            FINAL_REPEAT_COUNT, parameterized_transport
        ),
        "quality_new_action_runs_waiting_for_V3_pair": count_new(
            FINAL_REPEAT_COUNT, quality_waiting_for_v3
        ),
        "conditional_stock_new_action_runs_max": count_new(FINAL_REPEAT_COUNT, stock),
        "alternative_new_action_runs_currently_executable": count_new(
            FINAL_REPEAT_COUNT, alternative
        ),
        "potential_alternative_new_action_runs_after_valid_register": (
            EXPECTED_LANE_COUNT * FINAL_REPEAT_COUNT
        ),
        "maximum_new_action_runs_without_alternative": count_new(FINAL_REPEAT_COUNT, all_non_alt),
        "currently_planned_new_action_runs_all_levers": count_new(
            FINAL_REPEAT_COUNT, all_levers
        ),
    }
    per_lever: dict[str, Any] = {}
    for lever_id in EXPECTED_LEVERS:
        lever_set = {lever_id}
        preliminary_new = count_new(PRELIMINARY_REPEAT_COUNT, lever_set)
        final_new = count_new(FINAL_REPEAT_COUNT, lever_set)
        per_lever[lever_id] = {
            "preliminary_logical_rows": EXPECTED_LANE_COUNT * PRELIMINARY_REPEAT_COUNT * 3,
            "final_logical_rows": EXPECTED_LANE_COUNT * FINAL_REPEAT_COUNT * 3,
            "preliminary_normal_alias_rows": EXPECTED_LANE_COUNT * PRELIMINARY_REPEAT_COUNT,
            "preliminary_incident_no_action_alias_rows": (
                EXPECTED_LANE_COUNT * PRELIMINARY_REPEAT_COUNT
            ),
            "preliminary_new_action_runs": preliminary_new,
            "final_normal_alias_rows": EXPECTED_LANE_COUNT * FINAL_REPEAT_COUNT,
            "final_incident_no_action_alias_rows": EXPECTED_LANE_COUNT * FINAL_REPEAT_COUNT,
            "final_new_action_runs": final_new,
            "potential_preliminary_new_action_runs_after_missing_prerequisite": (
                EXPECTED_LANE_COUNT * PRELIMINARY_REPEAT_COUNT
                if lever_id == "explicit_counterfactual_alternative_source"
                and preliminary_new == 0
                else 0
            ),
            "potential_final_new_action_runs_after_missing_prerequisite": (
                EXPECTED_LANE_COUNT * FINAL_REPEAT_COUNT
                if lever_id == "explicit_counterfactual_alternative_source"
                and final_new == 0
                else 0
            ),
        }
    unique_reused_preliminary = (
        PRELIMINARY_REPEAT_COUNT
        + EXPECTED_LANE_COUNT * len(set(EXPECTED_FAILURE_MODES.values())) * PRELIMINARY_REPEAT_COUNT
    )
    unique_reused_final = (
        FINAL_REPEAT_COUNT
        + EXPECTED_LANE_COUNT * len(set(EXPECTED_FAILURE_MODES.values())) * FINAL_REPEAT_COUNT
    )
    return {
        "preliminary_repeat_count": PRELIMINARY_REPEAT_COUNT,
        "final_repeat_count": FINAL_REPEAT_COUNT,
        "seed_prefix_reuse_exact": list(context.seeds[:PRELIMINARY_REPEAT_COUNT]),
        "preliminary_is_final_prefix": True,
        "logical_triplet_row_count_preliminary": sum(
            _to_int(row.get("seed_prefix_index"), 99) <= PRELIMINARY_REPEAT_COUNT for row in design
        ),
        "logical_triplet_row_count_final": len(design),
        "preliminary": preliminary_counts,
        "final": final_counts,
        "per_lever": per_lever,
        "physical_evidence_after_alias_reuse": {
            "preliminary_unique_reused_normal_or_incident_cases": unique_reused_preliminary,
            "preliminary_max_new_action_runs_without_alternative": preliminary_counts[
                "maximum_new_action_runs_without_alternative"
            ],
            "preliminary_total_unique_physical_cases_without_alternative": (
                unique_reused_preliminary
                + preliminary_counts["maximum_new_action_runs_without_alternative"]
            ),
            "final_unique_reused_normal_or_incident_cases": unique_reused_final,
            "final_max_new_action_runs_without_alternative": final_counts[
                "maximum_new_action_runs_without_alternative"
            ],
            "final_total_unique_physical_cases_without_alternative": (
                unique_reused_final
                + final_counts["maximum_new_action_runs_without_alternative"]
            ),
            "normal_alias_is_shared_across_all_lanes_and_levers": True,
            "supply_availability_incident_alias_is_shared_by_stock_and_alternative_levers": True,
            "quality_incident_alias_must_come_from_completed_V3": True,
            "missing_quality_alias_must_block_not_create_a_substitute_baseline": True,
        },
        "eta_basis": {
            "source_campaign_run_count": main_runs,
            "source_campaign_elapsed_hours": round(main_hours, 6),
            "observed_main_campaign_runs_per_hour": round(main_rate, 6),
            "throughput_observations": throughput_observations,
            "planning_rate_runs_per_hour": round(planning_rate, 6),
            "planning_rate_source": "completed_network_campaign_only",
            "small_smoke_rate_used_for_eta": False,
            "planning_range_claimed": False,
            "rate_is_historical_not_guaranteed": True,
        },
        "eta_preliminary_max_without_alternative": estimate(
            preliminary_counts["maximum_new_action_runs_without_alternative"]
        ),
        "eta_final_max_without_alternative": estimate(
            final_counts["maximum_new_action_runs_without_alternative"]
        ),
        "quality_no_action_source_runs_are_owned_by_V3_and_not_recounted": 4 * FINAL_REPEAT_COUNT,
        "normal_and_main_incident_source_runs_are_reused_and_not_recounted": True,
        "missing_source_case_fallback_execution_allowed": False,
        "interpretation": (
            "Le budget compte les nouveaux cas avec action. Les références normales et les incidents "
            "sans action sont des cas appariés existants ou produits par V3; ils ne sont pas relancés."
        ),
    }


def build_scientific_controls(context: ProtocolContext) -> dict[str, Any]:
    return {
        "scope": {
            "exact_service_group_lane_count": len(context.lanes),
            "follow_up_chain_ids": [lane.chain_id for lane in context.lanes],
            "follow_up_supplier_ids": [lane.supplier_id for lane in context.lanes],
            "slot_order_has_scientific_meaning": False,
        },
        "pairing": {
            "arms": ["normal", "incident_no_action", "incident_with_action"],
            "same_seed_required": True,
            "common_random_numbers_required": True,
            "preliminary_seed_prefix_reused_in_final": True,
            "preliminary_repeat_count": PRELIMINARY_REPEAT_COUNT,
            "final_repeat_count": FINAL_REPEAT_COUNT,
        },
        "transport": {
            "lever_changes_future_lane_lead_time_only": True,
            "identified_real_shipment_claimed": False,
            "fixed_schedule_not_closed_loop": True,
            "first_level_days": -TRANSPORT_REDUCTION_DAYS,
            "real_transport_quote_available": False,
        },
        "stock": {
            "stock_already_present_at_measured_J0_is_a_hypothesis": True,
            "stock_acquisition_simulated": False,
            "stock_procurement_lead_time_simulated": False,
            "stock_procurement_cost_simulated": False,
            "raw_and_rounded_absolute_quantities_and_uom_required": True,
            "quantity_basis": "14_days_of_simulated_active_window_average_pull",
            "standard_order_qty_used_as_target_multiple_when_explicit_multiple_absent": True,
            "standard_order_qty_available_on_all_lanes": all(
                lane.procurement_standard_order_qty is not None for lane in context.lanes
            ),
            "moq_absent_lane_count": sum(
                lane.procurement_min_order_qty is None for lane in context.lanes
            ),
            "explicit_multiple_absent_lane_count": sum(
                lane.procurement_lot_multiple_qty is None for lane in context.lanes
            ),
            "max_order_absent_lane_count": sum(
                lane.procurement_max_order_qty is None for lane in context.lanes
            ),
            "per_seed_positive_J0_required_for_multiplicative_engine_actuator": True,
            "zero_J0_must_be_blocked": True,
            "stock_injected_during_incident": False,
            "physical_procurement_origin_and_feasibility_still_to_validate": True,
        },
        "quality": {
            "quality_hold_days_preserved_in_full": True,
            "transport_component_only": True,
            "fixed_calendar_open_loop_whole_lane_not_lot_identity": True,
            "transport_reduction_days": TRANSPORT_REDUCTION_DAYS,
            "identified_lot_claimed": False,
            "closed_loop_claimed": False,
        },
        "alternative_source": {
            "reference_graph_lanes_are_mono_source": True,
            "explicit_graph_counterfactual_required": True,
            "qualification_evidence_required": True,
            "priority_weight_on_mono_source_forbidden": True,
            "normal_base_graph_required": True,
            "incident_no_action_base_graph_required": True,
            "incident_action_counterfactual_graph_required": True,
        },
        "claims": {
            "supplier_probability_estimated": False,
            "historical_frequency_estimated": False,
            "closed_loop_claimed": False,
            "action_recommended": False,
            "action_promotion_allowed": False,
            "industrial_cost_claimed": False,
            "model_costs_must_keep_model_units": True,
            "static_720_day_stock_cost_published": False,
            "real_incremental_holding_cost_requires_future_paired_stock_trajectory": True,
            "transport_or_procurement_quote_required_for_action_cost": True,
        },
        "execution": {
            "engine_execution_enabled": False,
            "requires_explicit_review_before_launch": True,
            "previous_artifacts_modified": False,
            "graph_modified": False,
            "engine_modified": False,
            "cold_start_modified": False,
        },
    }


def _protocol_text(
    *,
    context: ProtocolContext,
    parameters: Sequence[Mapping[str, Any]],
    budget: Mapping[str, Any],
) -> str:
    preliminary = budget["preliminary"]
    final = budget["final"]
    stock_rows = [
        row
        for row in parameters
        if str(row.get("lever_id") or "") == "prepositioned_free_stock_14d"
    ]
    stock_detail = chr(10).join(
        "- `{}` : cible brute {} {}, arrondie à {} {} = {} lot(s) de {} {}; "
        "MOQ={}, multiple contractuel={}, maximum={}.".format(
            row["chain_id"],
            row["buffer_raw_qty"],
            row["buffer_uom"],
            row["buffer_rounded_qty"],
            row["buffer_uom"],
            row["buffer_procurement_lot_count"],
            row["procurement_effective_rounding_lot_qty"],
            row["buffer_uom"],
            row["procurement_moq_qty"] or "non renseigné",
            row["procurement_explicit_multiple_qty"] or "non renseigné",
            row["procurement_max_order_qty"] or "non renseigné",
        )
        for row in stock_rows
    )
    return f"""# Protocole exploratoire des leviers — quatre voies V3

Ce dossier prépare des comparaisons appariées **fonctionnement normal / incident sans action / incident avec action**. Il ne lance aucune simulation, ne recommande aucune action et ne transforme pas un scénario en probabilité fournisseur.

## Périmètre exact

Les {len(context.lanes)} voies du groupe service V3 sont conservées sans classement entre elles :

{chr(10).join(f'- `{lane.chain_id}` — {lane.supplier_id}, {lane.item_id} vers {lane.dst_node_id}' for lane in context.lanes)}

## Premier niveau testé

- transport : réduction fixe de {TRANSPORT_REDUCTION_DAYS} jours sur les futurs départs de la voie ; ce n'est ni une expédition réelle identifiée ni une boucle fermée ;
- stock : hypothèse d'un stock déjà présent à J0. La cible brute de {BUFFER_COVER_DAYS} jours est arrondie au multiple disponible dans le graphe. Son achat, son délai d'acquisition et son financement ne sont pas simulés ; si le stock libre apparié vaut zéro, le cas est refusé car l'actionneur courant ne peut pas créer une quantité absolue ;
- qualité : réduction calendaire open-loop de {TRANSPORT_REDUCTION_DAYS} jours du transport sur toute la voie pendant le scénario qualité, sans réduire un seul jour de retenue qualité ; ce n'est ni une action sur un lot identifié ni une décision déclenchée par l'état du système ;
- seconde source : refusée dans le graphe mono-source actuel tant qu'un fournisseur qualifié et une arête contrefactuelle complètement décrite ne sont pas fournis. Aucun `priority_weight` ne sert de fausse seconde source.

La quantité standard FIA est le multiple cible réellement disponible dans ce modèle ; elle n'est pas présentée comme un MOQ contractuel. Pour les quatre voies, le graphe ne renseigne ni MOQ, ni multiple contractuel distinct, ni maximum :

{stock_detail}

## Taille et réutilisation

- préliminaire 15 graines : {budget['logical_triplet_row_count_preliminary']} lignes logiques, {preliminary['maximum_new_action_runs_without_alternative']} nouveaux cas avec action au maximum hors seconde source ;
- final 30 graines : {budget['logical_triplet_row_count_final']} lignes logiques, {final['maximum_new_action_runs_without_alternative']} nouveaux cas avec action au maximum hors seconde source ;
- détail préliminaire des nouveaux calculs : 60 transport futur, 60 stock J0 conditionnels, 60 transport qualité après disponibilité de la référence V3, 0 seconde source tant que le graphe explicite manque ;
- les {budget['physical_evidence_after_alias_reuse']['preliminary_unique_reused_normal_or_incident_cases']} références physiques uniques du préliminaire sont réutilisées (15 normales partagées et 180 incidents par cause/voie) ; elles ne sont pas 540 nouveaux calculs et aucune référence de remplacement n'est fabriquée ;
- les 15 premières graines sont exactement le préfixe des 30 : elles ne seront pas recalculées dans le final ;
- temps indicatif hors seconde source : environ {budget['eta_preliminary_max_without_alternative']['point_estimate_hours_at_completed_campaign_rate']:.2f} h pour le préliminaire et {budget['eta_final_max_without_alternative']['point_estimate_hours_at_completed_campaign_rate']:.2f} h pour 30 si l'on repart de zéro. Ce sont des estimations ponctuelles fondées uniquement sur la campagne réseau terminée de 1 255 calculs, pas une fourchette ni une garantie. Le smoke V2 de 5 calculs est conservé comme petit échantillon de contrôle mais exclu du calcul de temps.

Aucun coût d'action n'est publié : les devis transport, coûts d'achat et conditions industrielles manquent. Le pseudo-coût « quantité × 720 jours » est supprimé. Le coût de possession incrémental devra être calculé après simulation à partir de la différence quotidienne de stock entre les deux trajectoires appariées, avec une valeur unitaire et un taux de possession validés par l'industriel.
"""


def _exact_inventory(root: Path) -> None:
    files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    dirs = [path for path in root.rglob("*") if path.is_dir()]
    if files != set(PLAN_FILES) or dirs:
        raise ValueError(
            f"Inventaire protocole non exact: missing={sorted(set(PLAN_FILES)-files)}, "
            f"extra={sorted(files-set(PLAN_FILES))}, dirs={len(dirs)}"
        )


def validate_protocol_artifact(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    _exact_inventory(output_dir)
    manifest = _read_json(output_dir / "exploratory_action_protocol_manifest.json")
    if str(manifest.get("schema_version") or "") != SCHEMA_VERSION:
        raise ValueError("Version de protocole inconnue.")
    if str(manifest.get("status") or "") != "planned_not_executed":
        raise ValueError("Le protocole ne doit pas se présenter comme exécuté.")
    if _as_bool(manifest.get("engine_execution_enabled")):
        raise ValueError("Le protocole préparatoire ne peut pas activer le moteur.")
    hashes = manifest.get("plan_file_hashes") or {}
    if set(hashes) != set(IMMUTABLE_PLAN_FILES):
        raise ValueError("Inventaire des empreintes incomplet ou excessif.")
    for name, expected in hashes.items():
        if _sha256(output_dir / str(name)) != str(expected):
            raise ValueError(f"Fichier du protocole modifié: {name}")
    payload = manifest.get("signature_payload") or {}
    if str(manifest.get("protocol_signature") or "") != _signature(payload):
        raise ValueError("Signature interne du protocole invalide.")
    if str(manifest.get("builder_sha256") or "") != _sha256(Path(__file__).resolve()):
        raise ValueError("Le protocole n'a pas été produit par le builder courant.")
    design = _read_csv(output_dir / "paired_experiment_design.csv")
    parameters = _read_csv(output_dir / "action_lever_parameters.csv")
    if len(parameters) != EXPECTED_LANE_COUNT * len(EXPECTED_LEVERS):
        raise ValueError("Matrice de leviers incomplète.")
    if len(design) != EXPECTED_LANE_COUNT * len(EXPECTED_LEVERS) * FINAL_REPEAT_COUNT * 3:
        raise ValueError("Matrice appariée incomplète.")
    if {str(row.get("lever_id") or "") for row in parameters} != set(EXPECTED_LEVERS):
        raise ValueError("Identifiants de leviers inattendus dans les paramètres.")
    if {str(row.get("lever_id") or "") for row in design} != set(EXPECTED_LEVERS):
        raise ValueError("Identifiants de leviers inattendus dans le design.")
    if any(_as_bool(row.get("priority_weight_used")) for row in [*parameters, *design]):
        raise ValueError("Le protocole interdit priority_weight.")
    if any(_as_bool(row.get("closed_loop_claimed")) for row in [*parameters, *design]):
        raise ValueError("Le protocole ne revendique pas de boucle fermée.")
    grouped: dict[str, set[str]] = {}
    for row in design:
        grouped.setdefault(str(row.get("pairing_id") or ""), set()).add(str(row.get("arm") or ""))
    expected_arms = {"normal", "incident_no_action", "incident_with_action"}
    if not grouped or any(arms != expected_arms for arms in grouped.values()):
        raise ValueError("Chaque comparaison doit avoir exactement trois bras.")
    preliminary_seeds = {
        str(row.get("seed")) for row in design if _as_bool(row.get("included_in_preliminary_15"))
    }
    all_seeds = {str(row.get("seed")) for row in design}
    if len(preliminary_seeds) != PRELIMINARY_REPEAT_COUNT or len(all_seeds) != FINAL_REPEAT_COUNT:
        raise ValueError("Préfixe 15/30 invalide.")
    if any(str(row.get("model_cost_value") or "").strip() for row in parameters):
        raise ValueError("Aucun pseudo-coût modèle ne doit être publié comme coût d'action.")
    if any(_as_bool(row.get("industrial_action_cost_available")) for row in parameters):
        raise ValueError("Aucun coût d'action industriel n'est disponible dans ce protocole.")
    stock_lotified_lane_count = 0
    for row in parameters:
        lever = str(row.get("lever_id") or "")
        if lever == "prepositioned_free_stock_14d":
            raw_qty = _to_float(row.get("buffer_raw_qty"), 0.0)
            added_qty = _to_float(row.get("buffer_additional_qty"), 0.0)
            rounded_qty = _to_float(row.get("buffer_rounded_qty"), 0.0)
            lot_qty = _to_float(row.get("procurement_effective_rounding_lot_qty"), 0.0)
            lot_count = _to_int(row.get("buffer_procurement_lot_count"), 0)
            if min(raw_qty, added_qty, rounded_qty, lot_qty) <= 0.0 or not str(
                row.get("buffer_uom") or ""
            ):
                raise ValueError("Le stock prépositionné doit être chiffré et avoir une unité.")
            if rounded_qty + 1e-9 < raw_qty or abs(added_qty - rounded_qty) > 1e-8:
                raise ValueError("La quantité de stock arrondie est incohérente.")
            if lot_count <= 0 or abs(rounded_qty - lot_count * lot_qty) > 1e-7:
                raise ValueError("La quantité de stock ne respecte pas son nombre de lots.")
            if str(row.get("buffer_uom") or "") != str(
                row.get("procurement_constraint_uom") or ""
            ):
                raise ValueError("L'unité du stock et celle de la contrainte diffèrent.")
            if not _as_bool(row.get("stock_present_at_j0_hypothesis")):
                raise ValueError("Le stock doit rester une hypothèse déjà présente à J0.")
            if _as_bool(row.get("stock_acquisition_simulated")) or _as_bool(
                row.get("stock_procurement_lead_time_simulated")
            ) or _as_bool(row.get("stock_procurement_cost_simulated")):
                raise ValueError("L'acquisition du stock J0 ne doit pas être présentée comme simulée.")
            if _as_bool(row.get("static_720_day_holding_cost_published")):
                raise ValueError("Le pseudo-coût statique sur 720 jours est interdit.")
            if not str(row.get("incremental_holding_cost_status") or "").startswith(
                "not_computed_requires_future_incremental_inventory_trajectory"
            ):
                raise ValueError("Le coût de possession futur doit rester à calculer.")
            maximum = _to_float(row.get("procurement_max_order_qty"), 0.0)
            if maximum > 0.0 and rounded_qty > maximum + 1e-9:
                if not str(row.get("new_action_run_status") or "").startswith("blocked_"):
                    raise ValueError("Un stock supérieur au maximum doit rester bloqué.")
            stock_lotified_lane_count += 1
        if lever == (
            "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d"
        ):
            if _as_bool(row.get("quality_hold_reduction_claimed")):
                raise ValueError("Le transport ne peut pas raccourcir la retenue qualité.")
            if _to_int(row.get("lead_time_adjustment_days"), 0) != -TRANSPORT_REDUCTION_DAYS:
                raise ValueError("La réduction transport du scénario qualité doit être de 7 jours.")
            if str(row.get("action_timing") or "") != (
                "fixed_calendar_open_loop_whole_lane_in_quality_scenario"
            ):
                raise ValueError("La sémantique calendaire open-loop qualité est absente.")
        if lever == "explicit_counterfactual_alternative_source" and not _as_bool(
            row.get("graph_counterfactual_required")
        ):
            raise ValueError("La seconde source exige un graphe contrefactuel.")
    if stock_lotified_lane_count != EXPECTED_LANE_COUNT:
        raise ValueError("Les quatre tampons J0 doivent être lotifiés.")
    return {
        "valid": True,
        "status": "planned_not_executed",
        "protocol_signature": manifest["protocol_signature"],
        "lane_count": EXPECTED_LANE_COUNT,
        "parameter_row_count": len(parameters),
        "paired_design_row_count": len(design),
        "stock_lotified_lane_count": stock_lotified_lane_count,
        "industrial_action_cost_published": False,
        "engine_execution_enabled": False,
    }


def create_protocol(
    *,
    post_priority_plan: Path,
    graph: Path,
    engine: Path,
    profile: Path,
    output_dir: Path,
    alternative_source_register: Path | None = None,
) -> Path:
    context = load_context(
        post_priority_plan=post_priority_plan,
        graph=graph,
        engine=engine,
        profile=profile,
        alternative_source_register=alternative_source_register,
    )
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Le nouveau dossier existe déjà: {output_dir}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        parameters = build_lever_parameters(context)
        design = build_experiment_design(context, parameters)
        alternatives = build_alternative_requirements(context, parameters)
        budget = build_execution_budget(context, design)
        controls = build_scientific_controls(context)
        _write_csv(temporary / "action_lever_parameters.csv", parameters)
        _write_csv(temporary / "paired_experiment_design.csv", design)
        _write_csv(temporary / "alternative_source_graph_requirements.csv", alternatives)
        _write_json(temporary / "execution_budget.json", budget)
        _write_json(temporary / "scientific_controls.json", controls)
        (temporary / "PROTOCOL.md").write_text(
            _protocol_text(context=context, parameters=parameters, budget=budget),
            encoding="utf-8",
        )
        hashes = {name: _sha256(temporary / name) for name in IMMUTABLE_PLAN_FILES}
        plan_manifest_path = context.plan_dir / "post_priority_extensions_plan_manifest.json"
        source_manifest_path = context.source_dir / "campaign_manifest.json"
        payload = {
            "schema_version": SCHEMA_VERSION,
            "contract_revision": CONTRACT_REVISION,
            "builder_sha256": _sha256(Path(__file__).resolve()),
            "post_priority_plan_signature": str(context.plan_manifest.get("plan_signature") or ""),
            "post_priority_plan_manifest_sha256": _sha256(plan_manifest_path),
            "source_campaign_signature": str(context.source_manifest.get("campaign_signature") or ""),
            "source_campaign_manifest_sha256": _sha256(source_manifest_path),
            "graph_sha256": _sha256(context.graph_path),
            "engine_sha256": _sha256(context.engine_path),
            "profile_sha256": _sha256(context.profile_path),
            "follow_up_chain_ids": [lane.chain_id for lane in context.lanes],
            "follow_up_supplier_ids": [lane.supplier_id for lane in context.lanes],
            "seeds": list(context.seeds),
            "preliminary_repeat_count": PRELIMINARY_REPEAT_COUNT,
            "final_repeat_count": FINAL_REPEAT_COUNT,
            "action_lever_ids": list(EXPECTED_LEVERS),
            "plan_file_hashes": hashes,
            "engine_execution_enabled": False,
        }
        manifest = {
            **payload,
            "status": "planned_not_executed",
            "created_at_utc": _utc_now(),
            "protocol_signature": _signature(payload),
            "signature_payload": payload,
            "plan_file_hashes": hashes,
            "output_dir": str(output_dir),
            "post_priority_plan_dir": str(context.plan_dir),
            "source_campaign_dir": str(context.source_dir),
            "alternative_source_register": str(alternative_source_register or ""),
            "alternative_source_registered_lane_count": len(context.alternative_by_chain),
            "parameter_row_count": len(parameters),
            "paired_design_row_count": len(design),
            "execution_budget": budget,
            "engine_execution_enabled": False,
            "requires_explicit_review_before_launch": True,
            "not_a_recommendation": True,
            "action_promotion_allowed": False,
            "supplier_probability_estimated": False,
            "historical_frequency_estimated": False,
            "closed_loop_claimed": False,
            "stock_present_at_j0_is_hypothesis": True,
            "stock_acquisition_simulated": False,
            "stock_buffers_lotified": True,
            "industrial_action_cost_published": False,
            "static_720_day_holding_cost_published": False,
            "incremental_holding_cost_requires_future_trajectory": True,
            "previous_artifacts_modified": False,
            "graph_modified": False,
            "engine_modified": False,
            "cold_start_modified": False,
        }
        _write_json(temporary / "exploratory_action_protocol_manifest.json", manifest)
        temporary.replace(output_dir)
    except Exception:
        if temporary.exists() and temporary.parent == output_dir.parent:
            shutil.rmtree(temporary)
        raise
    validate_protocol_artifact(output_dir)
    return output_dir


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--post-priority-plan", type=Path, default=DEFAULT_POST_PRIORITY_PLAN)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--alternative-source-register", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--validate-plan", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.validate_plan is not None:
        print(
            json.dumps(
                validate_protocol_artifact(args.validate_plan),
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 0
    if args.output_dir is None:
        raise ValueError("--output-dir est requis pour créer un nouveau protocole.")
    output = create_protocol(
        post_priority_plan=args.post_priority_plan,
        graph=args.graph,
        engine=args.engine,
        profile=args.profile,
        output_dir=args.output_dir,
        alternative_source_register=args.alternative_source_register,
    )
    print(
        json.dumps(
            {
                "status": "planned_not_executed",
                "output_dir": str(output),
                "engine_execution_enabled": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
