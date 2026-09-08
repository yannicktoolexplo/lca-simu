#!/usr/bin/env python3
"""Paired supplier-risk screening across every active V10 supplier lane.

This module is deliberately additive.  It discovers the supplier lanes that
carry a positive simulated shipment in the V10 reference run (where January
opening purchase orders are disabled), stresses each lane independently, and
compares every result with a same-seed baseline.  It does not edit the graph,
the cold-start implementation, or any previous campaign artifact.

The campaign answers a conditional question: *if this failure mode happened
on this lane at the tested intensity, what would the downstream consequence
be?*  It does not estimate historical failure probabilities or declare an
observed supplier criticality.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

_IMPORT_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_IMPORT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_service_landscape_campaign as campaign_core,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_PARENT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
DEFAULT_REFERENCE_RUN = (
    ARTIFACT_PARENT / "supplier_service_landscape_calibration_20260831_v10"
)
DEFAULT_SCOPE_AUDIT = ARTIFACT_PARENT / "supplier_network_scope_audit_20260901_v8"
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

INCIDENT_START_DAY = 45
INCIDENT_DURATION_DAYS = 180
TARGET_PRODUCTS = ("268091", "268967")
DEFAULT_SCREENING_SEED = 340281
DEFAULT_CONFIRMATION_SEEDS = "340282-340311"
DEFAULT_CONFIRMATION_TOP_LANES = 18
DEFAULT_EXPECTED_ACTIVE_LANES = 18
SCHEMA_VERSION = "etudecas.supplier_network_risk_screen_campaign.v1"
CONFIRMATION_MATHEMATICAL_FAMILIES = {
    # Predeclared severe envelopes.  The four business causes remain visible
    # in balanced screening, but confirmation does not pick a cause from one
    # seed.  It repeats one date-shift and one usable-quantity-loss family.
    "date_shift": "transport_delay",
    "usable_quantity_loss": "supply_availability",
}


def planned_run_counts(
    *,
    active_lane_count: int,
    confirmation_seed_count: int,
) -> dict[str, int]:
    """Return the exact main-campaign run budget.

    Screening exercises four business mechanisms at two levels on every
    active lane. Confirmation is independent of the one-seed screening
    result: it repeats two predeclared mathematical families on every lane,
    with one paired baseline per seed.
    """

    screening = 1 + active_lane_count * len(MECHANISMS) * len(LEVELS)
    confirmation_stress = (
        active_lane_count
        * len(CONFIRMATION_MATHEMATICAL_FAMILIES)
        * confirmation_seed_count
    )
    confirmation = confirmation_seed_count + confirmation_stress
    return {
        "smoke": 5,
        "screening": screening,
        "confirmation_baseline": confirmation_seed_count,
        "confirmation_stress": confirmation_stress,
        "confirmation": confirmation,
        "full": screening + confirmation,
    }


@dataclass(frozen=True)
class LaneReference:
    chain: campaign_core.Chain
    edge_id: str
    baseline_shipped_qty: float
    baseline_pulled_qty: float
    common_window_shipped_qty: float
    common_window_pulled_qty: float
    active_window_start_day: int
    active_window_end_day: int
    active_window_shipped_qty: float
    active_window_pulled_qty: float
    first_shipment_day: int
    last_shipment_day: int
    shipment_day_count: int


MECHANISMS: tuple[campaign_core.Mechanism, ...] = (
    campaign_core.Mechanism(
        key="transport_delay",
        label="Retard de transport ou d'expédition",
        risk_type="lead_time_extra_days",
        values=(60.0, 120.0),
        unit="jours_ajoutes",
        no_op_value=0.0,
        evidence_note=(
            "Hypothèse de retard appliquée à la voie; ce n'est ni un OTIF mesuré "
            "ni une fréquence historique."
        ),
    ),
    campaign_core.Mechanism(
        key="supply_availability",
        label="Disponibilité temporaire de l'approvisionnement",
        risk_type="availability",
        values=(0.80, 0.50),
        unit="part_disponible",
        no_op_value=1.0,
        evidence_note=(
            "Hypothèse de part d'approvisionnement accessible ou livrable dans "
            "le modèle pendant l'incident; la capacité réelle reste inconnue."
        ),
    ),
    campaign_core.Mechanism(
        key="quality_hold",
        label="Attente de libération qualité",
        risk_type="quality_delay",
        values=(30.0, 90.0),
        unit="jours_ajoutes",
        no_op_value=0.0,
        evidence_note=(
            "Hypothèse de matière reçue mais non utilisable jusqu'à sa libération; "
            "la cause peut être fournisseur, transport, réception ou laboratoire."
        ),
    ),
    campaign_core.Mechanism(
        key="quality_yield",
        label="Quantité utilisable après contrôle qualité",
        risk_type="quality_yield",
        values=(0.95, 0.80),
        unit="part_utilisable",
        no_op_value=1.0,
        evidence_note=(
            "Hypothèse de rendement qualité sur la quantité reçue; ce n'est pas "
            "un taux de non-conformité observé."
        ),
    ),
)
MECHANISM_BY_KEY = {item.key: item for item in MECHANISMS}


def mechanism_evidence_note(mechanism: campaign_core.Mechanism) -> str:
    if mechanism.key == "quality_hold":
        return (
            "Hypothese de decalage de la date d'utilisabilite. Le moteur ne "
            "materialise pas un stock de quarantaine entre arrivee physique et "
            "liberation; l'intervalle d'attente qualite est reconstruit."
        )
    return mechanism.evidence_note
LEVELS = (("modere", "Modéré"), ("severe", "Sévère"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    cleaned = []
    for character in str(value).lower():
        cleaned.append(character if character.isalnum() else "_")
    return "_".join(part for part in "".join(cleaned).split("_") if part)


def _to_float(value: Any, default: float = 0.0) -> float:
    return campaign_core.to_float(value, default)


def _to_int(value: Any, default: int = 0) -> int:
    return campaign_core.to_int(value, default)


def _read_csv(path: Path) -> list[dict[str, str]]:
    return campaign_core.read_csv_rows(path)


def _read_json(path: Path) -> dict[str, Any]:
    return campaign_core.read_json(path)


def _required_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Fichier {label} absent: {resolved}")
    return resolved


def _sha256(path: Path) -> str:
    return campaign_core.sha256_file(path)


def incident_window(days: int) -> tuple[int, int]:
    if days <= 0:
        raise ValueError("days must be positive")
    start = min(INCIDENT_START_DAY, days - 1)
    end = min(days - 1, start + INCIDENT_DURATION_DAYS - 1)
    return start, end


def strongest_active_window(
    rows: Sequence[Mapping[str, Any]], *, days: int, duration: int = INCIDENT_DURATION_DAYS
) -> tuple[int, int]:
    """Choose a fixed-duration exposure window from the reference flow.

    The primary criterion is shipped quantity within the window.  Ties are
    resolved by proximity to the common V4 start day, then by the earliest
    start.  This keeps the 180-day stress duration identical across lanes
    while ensuring that lumpy, genuinely active lanes are exercised.
    """

    if days <= 0 or duration <= 0:
        raise ValueError("days and duration must be positive")
    width = min(days, duration)
    quantity_by_day = [0.0] * days
    for row in rows:
        day = _to_int(row.get("day"), -1)
        if 0 <= day < days:
            quantity_by_day[day] += max(0.0, _to_float(row.get("shipped_qty")))
    running = sum(quantity_by_day[:width])
    candidates: list[tuple[float, int]] = [(running, 0)]
    for start in range(1, days - width + 1):
        running += quantity_by_day[start + width - 1] - quantity_by_day[start - 1]
        candidates.append((running, start))
    best_quantity = max(value for value, _start in candidates)
    tied = [
        start
        for value, start in candidates
        if math.isclose(value, best_quantity, rel_tol=1e-12, abs_tol=1e-9)
    ]
    best_start = min(tied, key=lambda start: (abs(start - INCIDENT_START_DAY), start))
    return best_start, best_start + width - 1


def _graph_supplier_ids(graph: Mapping[str, Any]) -> set[str]:
    return {
        str(node.get("id") or "")
        for node in graph.get("nodes") or []
        if str(node.get("type") or "").lower() == "supplier"
        or str(node.get("id") or "").startswith("SDC-VD")
    }


def _edge_item_keys(edge: Mapping[str, Any]) -> Iterable[tuple[str, str, str]]:
    source = str(edge.get("from") or "")
    destination = str(edge.get("to") or "")
    for item in edge.get("items") or []:
        yield source, str(item), destination


def downstream_products(
    graph: Mapping[str, Any], *, start_node: str, start_item: str
) -> tuple[str, ...]:
    """Return client products reachable from one received component state."""

    process_outputs: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for node in graph.get("nodes") or []:
        node_id = str(node.get("id") or "")
        for process in node.get("processes") or []:
            outputs = {
                (node_id, str(row.get("item_id") or ""))
                for row in process.get("outputs") or []
                if row.get("item_id")
            }
            for input_row in process.get("inputs") or []:
                item_id = str(input_row.get("item_id") or "")
                if item_id:
                    process_outputs[(node_id, item_id)].update(outputs)
    transports: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for edge in graph.get("edges") or []:
        if str(edge.get("type") or "") != "transport":
            continue
        for source, item, destination in _edge_item_keys(edge):
            transports[(source, item)].add((destination, item))
    client_nodes = {
        str(node.get("id") or "")
        for node in graph.get("nodes") or []
        if str(node.get("type") or "").lower() in {"client", "customer"}
        or str(node.get("id") or "") == "C-XXXXX"
    }
    queue: deque[tuple[str, str]] = deque([(start_node, start_item)])
    visited: set[tuple[str, str]] = set()
    products: set[str] = set()
    while queue:
        state = queue.popleft()
        if state in visited:
            continue
        visited.add(state)
        node_id, item_id = state
        bare_item = item_id.replace("item:", "")
        if node_id in client_nodes and bare_item in TARGET_PRODUCTS:
            products.add(bare_item)
        for following in process_outputs.get(state, set()) | transports.get(state, set()):
            if following not in visited:
                queue.append(following)
    return tuple(sorted(products))


def _reference_open_orders_disabled(reference_run: Path) -> bool:
    summary = _read_json(reference_run / "summaries" / "first_simulation_summary.json")
    initialization = (summary.get("policy") or {}).get("initialization_policy") or {}
    return not campaign_core.as_bool(
        initialization.get("seed_open_orders_from_january_snapshot")
    )


def discover_active_lanes(
    *,
    graph: Mapping[str, Any],
    shipment_rows: Sequence[Mapping[str, Any]],
    days: int,
) -> list[LaneReference]:
    """Discover positive supplier lanes from the measured part of V10."""

    suppliers = _graph_supplier_ids(graph)
    edges_by_key: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for edge in graph.get("edges") or []:
        for key in _edge_item_keys(edge):
            edges_by_key[key].append(edge)
    common_start_day, common_end_day = incident_window(days)
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in shipment_rows:
        day = _to_int(row.get("day"), -1)
        source = str(row.get("src_node_id") or "")
        quantity = max(0.0, _to_float(row.get("shipped_qty")))
        if source not in suppliers or not (0 <= day < days) or quantity <= 1e-12:
            continue
        key = (
            source,
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        )
        grouped[key].append(row)
    references: list[LaneReference] = []
    for key, rows in sorted(grouped.items()):
        matching_edges = edges_by_key.get(key, [])
        if len(matching_edges) != 1:
            raise ValueError(f"La voie active {key} correspond à {len(matching_edges)} arêtes")
        edge = matching_edges[0]
        products = downstream_products(
            graph, start_node=key[2], start_item=key[1]
        )
        if len(products) != 1:
            raise ValueError(
                f"La voie active {key} atteint {products}; un produit aval unique est requis"
            )
        lead = max(0.0, _to_float((edge.get("lead_time") or {}).get("mean")))
        item_bare = key[1].replace("item:", "")
        chain_id = _slug(f"{key[0]}__{item_bare}__{key[2]}")
        lane = campaign_core.Lane(
            supplier_id=key[0],
            item_id=key[1],
            dst_node_id=key[2],
            label=f"{item_bare} : {key[0]} vers {key[2]}",
            planned_lead_days=lead,
        )
        chain = campaign_core.Chain(
            chain_id=chain_id,
            label=f"{key[0]} / {item_bare} → {key[2]} → {products[0]}",
            component_label=item_bare,
            target_product_id=products[0],
            client_node_id="C-XXXXX",
            affected_lanes=(lane,),
        )
        days_with_shipment = sorted({_to_int(row.get("day"), -1) for row in rows})
        common_rows = [
            row
            for row in rows
            if common_start_day <= _to_int(row.get("day"), -1) <= common_end_day
        ]
        active_start_day, active_end_day = strongest_active_window(rows, days=days)
        active_rows = [
            row
            for row in rows
            if active_start_day <= _to_int(row.get("day"), -1) <= active_end_day
        ]
        references.append(
            LaneReference(
                chain=chain,
                edge_id=str(edge.get("id") or ""),
                baseline_shipped_qty=sum(
                    max(0.0, _to_float(row.get("shipped_qty"))) for row in rows
                ),
                baseline_pulled_qty=sum(
                    max(0.0, _to_float(row.get("pulled_qty"))) for row in rows
                ),
                common_window_shipped_qty=sum(
                    max(0.0, _to_float(row.get("shipped_qty")))
                    for row in common_rows
                ),
                common_window_pulled_qty=sum(
                    max(0.0, _to_float(row.get("pulled_qty")))
                    for row in common_rows
                ),
                active_window_start_day=active_start_day,
                active_window_end_day=active_end_day,
                active_window_shipped_qty=sum(
                    max(0.0, _to_float(row.get("shipped_qty")))
                    for row in active_rows
                ),
                active_window_pulled_qty=sum(
                    max(0.0, _to_float(row.get("pulled_qty")))
                    for row in active_rows
                ),
                first_shipment_day=min(days_with_shipment),
                last_shipment_day=max(days_with_shipment),
                shipment_day_count=len(days_with_shipment),
            )
        )
    return references


def validate_scope_audit_crosscheck(
    lanes: Sequence[LaneReference],
    audit_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    discovered = {
        reference.chain.affected_lanes[0].key for reference in lanes
    }
    audited_active = {
        (
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        )
        for row in audit_rows
        if campaign_core.as_bool(row.get("baseline_positive_flow"))
    }
    if discovered != audited_active:
        raise ValueError(
            "Le périmètre actif découvert dans V10 diffère de l'audit v8: "
            f"manquantes={sorted(audited_active - discovered)}, "
            f"inattendues={sorted(discovered - audited_active)}"
        )
    evidence_counts = Counter(str(row.get("evidence_status") or "") for row in audit_rows)
    return {
        "audit_lane_count": len(audit_rows),
        "audited_active_lane_count": len(audited_active),
        "discovered_active_lane_count": len(discovered),
        "exact_active_scope_match": True,
        "evidence_status_counts": dict(sorted(evidence_counts.items())),
        "interpretation": (
            "Le screening couvre exactement les voies à flux positif dans la "
            "référence dynamique V10. Les voies carnet-seul relèvent du replay "
            "021081/commandes et les voies non exercées restent hors classement."
        ),
    }


def configure_campaign_core(lanes: Sequence[LaneReference]) -> None:
    """Point the proven V4 extraction/validation helpers at the dynamic scope."""

    chains = tuple(reference.chain for reference in lanes)
    campaign_core.CHAINS = chains
    campaign_core.CHAIN_BY_ID = {chain.chain_id: chain for chain in chains}
    campaign_core.MECHANISMS = MECHANISMS
    campaign_core.MECHANISM_BY_KEY = MECHANISM_BY_KEY
    campaign_core.INCIDENT_START_DAY = INCIDENT_START_DAY
    campaign_core.INCIDENT_DURATION_DAYS = INCIDENT_DURATION_DAYS


def build_scenarios(lanes: Sequence[LaneReference]) -> list[campaign_core.Scenario]:
    scenarios = [
        campaign_core.Scenario(
            scenario_id="baseline_nominal",
            execution_scenario_id="baseline_nominal",
            chain_id="",
            mechanism_key="baseline",
            level_index=0,
            level_code="baseline",
            level_label="Référence simulée",
            value=1.0,
            unit="ratio",
            target_product_id="",
            client_node_id="C-XXXXX",
            is_campaign_baseline=True,
        )
    ]
    for reference in lanes:
        chain = reference.chain
        for mechanism in MECHANISMS:
            for level_index, (level_code, level_label) in enumerate(LEVELS, 1):
                value = mechanism.values[level_index - 1]
                scenario_id = (
                    f"{chain.chain_id}__{mechanism.key}__"
                    f"{campaign_core.slug_number(value)}"
                )
                scenarios.append(
                    campaign_core.Scenario(
                        scenario_id=scenario_id,
                        execution_scenario_id=scenario_id,
                        chain_id=chain.chain_id,
                        mechanism_key=mechanism.key,
                        level_index=level_index,
                        level_code=level_code,
                        level_label=level_label,
                        value=value,
                        unit=mechanism.unit,
                        target_product_id=chain.target_product_id,
                        client_node_id=chain.client_node_id,
                    )
                )
    return scenarios


def lane_reference_rows(lanes: Sequence[LaneReference], days: int) -> list[dict[str, Any]]:
    start_day, end_day = incident_window(days)
    rows: list[dict[str, Any]] = []
    for reference in lanes:
        chain = reference.chain
        lane = chain.affected_lanes[0]
        rows.append(
            {
                "chain_id": chain.chain_id,
                "supplier_id": lane.supplier_id,
                "item_id": lane.item_id,
                "dst_node_id": lane.dst_node_id,
                "edge_id": reference.edge_id,
                "target_product_id": chain.target_product_id,
                "planned_lead_days": lane.planned_lead_days,
                "reference_total_shipped_qty": reference.baseline_shipped_qty,
                "reference_total_pulled_qty": reference.baseline_pulled_qty,
                "reference_common_window_shipped_qty": reference.common_window_shipped_qty,
                "reference_common_window_pulled_qty": reference.common_window_pulled_qty,
                "common_window_flow_status": (
                    "positive_reference_flow"
                    if reference.common_window_shipped_qty > 1e-12
                    and reference.common_window_pulled_qty > 1e-12
                    else "no_reference_flow_in_common_window"
                ),
                "active_window_start_day": reference.active_window_start_day,
                "active_window_end_day": reference.active_window_end_day,
                "reference_active_window_shipped_qty": reference.active_window_shipped_qty,
                "reference_active_window_pulled_qty": reference.active_window_pulled_qty,
                "active_window_selection_method": (
                    "maximum_reference_shipped_quantity_in_180d; "
                    "tie_nearest_common_J45_then_earliest"
                ),
                "reference_first_shipment_day": reference.first_shipment_day,
                "reference_last_shipment_day": reference.last_shipment_day,
                "reference_shipment_day_count": reference.shipment_day_count,
                "common_window_start_day": start_day,
                "common_window_end_day": end_day,
                "scope_status": "active_simulated_reference_v10",
                "interpretation": (
                    "Flux positif dans la référence simulée V10; ne constitue pas "
                    "une performance fournisseur observée."
                ),
            }
        )
    return rows


def scenario_design_rows(
    scenarios: Sequence[campaign_core.Scenario],
    chain_by_id: Mapping[str, campaign_core.Chain],
    reference_by_chain: Mapping[str, LaneReference],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        if scenario.is_campaign_baseline:
            rows.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "chain_id": "",
                    "supplier_id": "",
                    "item_id": "",
                    "dst_node_id": "",
                    "target_product_id": "",
                    "failure_mode": "baseline",
                    "failure_mode_label": "Référence simulée",
                    "level_code": "baseline",
                    "mechanism_value": 1.0,
                    "mechanism_unit": "ratio",
                    "evidence_class": "simulated_reference",
                    "historical_occurrence_probability": "not_estimated",
                }
            )
            continue
        chain = chain_by_id[scenario.chain_id]
        lane = chain.affected_lanes[0]
        mechanism = MECHANISM_BY_KEY[scenario.mechanism_key]
        reference = reference_by_chain[chain.chain_id]
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "chain_id": chain.chain_id,
                "supplier_id": lane.supplier_id,
                "item_id": lane.item_id,
                "dst_node_id": lane.dst_node_id,
                "target_product_id": chain.target_product_id,
                "failure_mode": mechanism.key,
                "failure_mode_label": mechanism.label,
                "level_code": scenario.level_code,
                "level_label": scenario.level_label,
                "mechanism_value": scenario.value,
                "mechanism_unit": scenario.unit,
                "stress_start_day": reference.active_window_start_day,
                "stress_end_day": reference.active_window_end_day,
                "stress_window_basis": (
                    "strongest_180d_reference_flow_window_for_this_lane"
                ),
                "evidence_class": "conditional_simulation_hypothesis",
                "historical_occurrence_probability": "not_estimated",
                "interpretation": mechanism_evidence_note(mechanism),
            }
        )
    return rows


def multi_lane_common_cause_design(
    *,
    lanes: Sequence[LaneReference],
    shipment_rows: Sequence[Mapping[str, Any]],
    days: int,
    screening_seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Plan, but do not execute, simultaneous incidents on multi-lane suppliers."""

    by_supplier: dict[str, list[LaneReference]] = defaultdict(list)
    for reference in lanes:
        by_supplier[reference.chain.affected_lanes[0].supplier_id].append(reference)
    multi = {
        supplier: refs for supplier, refs in by_supplier.items() if len(refs) > 1
    }
    rows: list[dict[str, Any]] = []
    for supplier, references in sorted(multi.items()):
        lane_keys = {
            (
                ref.chain.affected_lanes[0].supplier_id,
                ref.chain.affected_lanes[0].item_id,
                ref.chain.affected_lanes[0].dst_node_id,
            )
            for ref in references
        }
        supplier_rows = [
            row
            for row in shipment_rows
            if (
                str(row.get("src_node_id") or ""),
                str(row.get("item_id") or ""),
                str(row.get("dst_node_id") or ""),
            )
            in lane_keys
        ]
        start_day, end_day = strongest_active_window(
            supplier_rows, days=days, duration=INCIDENT_DURATION_DAYS
        )
        for mechanism in MECHANISMS:
            for level_index, (level_code, level_label) in enumerate(LEVELS, 1):
                value = mechanism.values[level_index - 1]
                rows.append(
                    {
                        "scenario_id": (
                            f"common_supplier__{_slug(supplier)}__{mechanism.key}__"
                            f"{campaign_core.slug_number(value)}"
                        ),
                        "supplier_id": supplier,
                        "affected_lane_count": len(references),
                        "affected_chain_ids": "|".join(
                            sorted(ref.chain.chain_id for ref in references)
                        ),
                        "affected_items": "|".join(
                            sorted(ref.chain.affected_lanes[0].item_id for ref in references)
                        ),
                        "affected_destinations": "|".join(
                            sorted(
                                {
                                    ref.chain.affected_lanes[0].dst_node_id
                                    for ref in references
                                }
                            )
                        ),
                        "affected_products": "|".join(
                            sorted({ref.chain.target_product_id for ref in references})
                        ),
                        "failure_mode": mechanism.key,
                        "level_code": level_code,
                        "level_label": level_label,
                        "mechanism_value": value,
                        "mechanism_unit": mechanism.unit,
                        "stress_start_day": start_day,
                        "stress_end_day": end_day,
                        "supplier_common_window_basis": (
                            "maximum_combined_reference_shipped_quantity_in_180d_across_supplier_lanes"
                        ),
                        "screening_seed": screening_seed,
                        "execution_status": "planned_separate_not_executed",
                        "reading": "incident_commun_fournisseur_distinct_de_incident_sur_une_voie",
                        "historical_occurrence_probability": "not_estimated",
                        "lot_proof_required": True,
                    }
                )
    manifest = {
        "status": "planned_separate_not_executed",
        "supplier_count": len(multi),
        "supplier_ids": sorted(multi),
        "supplier_lane_counts": {
            supplier: len(refs) for supplier, refs in sorted(multi.items())
        },
        "screening_stress_run_count": len(rows),
        "screening_baseline_reuse": 1,
        "conditional_confirmation_rule": (
            "confirm worst scenario of each supplier on 30 paired seeds only if "
            "screening has an effect"
        ),
        "maximum_confirmation_stress_run_count": len(multi) * 30,
        "confirmation_baselines_reused": 30,
        "main_lane_ranking_unchanged": True,
        "historical_occurrence_probability": "not_estimated",
        "lot_proof_contract": (
            "direct tagged receipts then parent_to_child genealogy; products exposed reported"
        ),
    }
    return rows, manifest


def _stock_safety_by_state(graph: Mapping[str, Any]) -> dict[tuple[str, str], float]:
    result: dict[tuple[str, str], float] = {}
    for node in graph.get("nodes") or []:
        node_id = str(node.get("id") or "")
        inventory = node.get("inventory") or {}
        for state in inventory.get("states") or []:
            key = (node_id, str(state.get("item_id") or ""))
            policy = state.get("mrp_policy") or {}
            result[key] = max(0.0, _to_float(policy.get("safety_stock_qty")))
    return result


def _graph_state_uom(
    graph: Mapping[str, Any], *, node_id: str, item_id: str
) -> str:
    for node in graph.get("nodes") or []:
        if str(node.get("id") or "") != node_id:
            continue
        for state in (node.get("inventory") or {}).get("states") or []:
            if str(state.get("item_id") or "") == item_id:
                return str(state.get("uom") or "")
    return ""


def _daily_groups(
    rows: Iterable[Mapping[str, Any]],
    *,
    node_field: str,
    days: int,
) -> dict[tuple[str, str], list[Mapping[str, Any]]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        day = _to_int(row.get("day"), -1)
        if 0 <= day < days:
            grouped[(str(row.get(node_field) or ""), str(row.get("item_id") or ""))].append(row)
    return grouped


def extract_chain_operations(
    *,
    case_dir: Path,
    chains: Sequence[campaign_core.Chain],
    graph: Mapping[str, Any],
    days: int,
) -> dict[str, dict[str, float]]:
    """Extract production and stock consequences before compact retention."""

    data_dir = case_dir / "data"
    output_groups = _daily_groups(
        _read_csv(data_dir / "production_output_products_daily.csv"),
        node_field="node_id",
        days=days,
    )
    input_groups = _daily_groups(
        _read_csv(data_dir / "production_input_stocks_daily.csv"),
        node_field="node_id",
        days=days,
    )
    supplier_groups = _daily_groups(
        _read_csv(data_dir / "production_supplier_stocks_daily.csv"),
        node_field="node_id",
        days=days,
    )
    arrival_groups = _daily_groups(
        _read_csv(data_dir / "production_input_replenishment_arrivals_daily.csv"),
        node_field="node_id",
        days=days,
    )
    safety_by_state = _stock_safety_by_state(graph)
    result: dict[str, dict[str, float]] = {}
    for chain in chains:
        lane = chain.affected_lanes[0]
        output_key = (lane.dst_node_id, f"item:{chain.target_product_id}")
        input_key = (lane.dst_node_id, lane.item_id)
        supplier_key = (lane.supplier_id, lane.item_id)
        output_rows = output_groups.get(output_key, [])
        input_rows = sorted(
            input_groups.get(input_key, []), key=lambda row: _to_int(row.get("day"), -1)
        )
        supplier_rows = sorted(
            supplier_groups.get(supplier_key, []), key=lambda row: _to_int(row.get("day"), -1)
        )
        arrivals = arrival_groups.get(input_key, [])
        stocks = [max(0.0, _to_float(row.get("stock_end_of_day"))) for row in input_rows]
        supplier_stocks = [
            max(0.0, _to_float(row.get("stock_end_of_day"))) for row in supplier_rows
        ]
        safety = safety_by_state.get(input_key, 0.0)
        result[chain.chain_id] = {
            "target_product_uom": _graph_state_uom(
                graph,
                node_id=lane.dst_node_id,
                item_id=f"item:{chain.target_product_id}",
            ),
            "component_stock_uom": _graph_state_uom(
                graph,
                node_id=lane.dst_node_id,
                item_id=lane.item_id,
            ),
            "service_metric_unit": "ratio_and_percentage_points",
            "target_backlog_qty_days_unit": "UN_day",
            "target_production_quantity_unit": "UN",
            "target_production_shortfall_ratio_unit": "ratio",
            "target_produced_qty": sum(
                max(0.0, _to_float(row.get("produced_qty"))) for row in output_rows
            ),
            "target_released_qty": sum(
                max(0.0, _to_float(row.get("released_qty"))) for row in output_rows
            ),
            "component_arrived_qty": sum(
                max(0.0, _to_float(row.get("arrived_qty"))) for row in arrivals
            ),
            "component_input_stock_j0": (
                max(0.0, _to_float(input_rows[0].get("stock_before_production")))
                if input_rows
                else 0.0
            ),
            "component_input_stock_end": stocks[-1] if stocks else 0.0,
            "component_input_stock_min": min(stocks) if stocks else 0.0,
            "component_input_stock_qty_days": sum(stocks),
            "component_days_at_zero": float(sum(value <= 1e-9 for value in stocks)),
            "component_safety_stock_qty": safety,
            "component_days_below_safety": float(
                sum(value + 1e-9 < safety for value in stocks)
            ),
            "supplier_stock_j0": supplier_stocks[0] if supplier_stocks else 0.0,
            "supplier_stock_end": supplier_stocks[-1] if supplier_stocks else 0.0,
            "supplier_stock_min": min(supplier_stocks) if supplier_stocks else 0.0,
        }
    return result


def extract_active_window_shipment_metrics(
    *,
    case_dir: Path,
    references: Sequence[LaneReference],
    days: int,
) -> dict[str, dict[str, float]]:
    rows = _read_csv(case_dir / "data" / "production_supplier_shipments_daily.csv")
    result: dict[str, dict[str, float]] = {}
    for reference in references:
        lane = reference.chain.affected_lanes[0]
        matched = [
            row
            for row in rows
            if reference.active_window_start_day <= _to_int(row.get("day"), -1)
            <= min(days - 1, reference.active_window_end_day)
            and str(row.get("src_node_id") or "") == lane.supplier_id
            and str(row.get("item_id") or "") == lane.item_id
            and str(row.get("dst_node_id") or "") == lane.dst_node_id
        ]
        result[reference.chain.chain_id] = {
            "active_window_shipped_qty": sum(
                max(0.0, _to_float(row.get("shipped_qty"))) for row in matched
            ),
            "active_window_pulled_qty": sum(
                max(0.0, _to_float(row.get("pulled_qty"))) for row in matched
            ),
        }
    return result


LOT_PROOF_NUMERIC_FIELDS = (
    "expected_risk_application_row_count",
    "positive_tagged_shipment_due_within_horizon_count",
    "positive_tagged_shipment_due_within_horizon_qty",
    "impacted_receipt_lot_count",
    "impacted_receipt_qty",
    "impacted_intermediate_descendant_lot_count",
    "impacted_finished_descendant_lot_count",
    "impacted_finished_descendant_qty_touched_upper",
    "impacted_client_delivery_descendant_lot_count",
    "impacted_client_delivery_event_count",
    "impacted_client_delivery_qty_touched_upper",
    "impacted_genealogy_link_count",
    "impacted_genealogy_max_depth",
    "quality_hold_reconstructed_interval_count",
    "quality_hold_reconstructed_qty",
)


def _risk_event_tokens(value: Any) -> set[str]:
    return {
        token.strip()
        for token in re.split(r"[,;|]", str(value or ""))
        if token.strip()
    }


def _quantities_by_uom_json(
    rows: Iterable[Mapping[str, Any]], *, qty_field: str
) -> str:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        quantity = max(0.0, _to_float(row.get(qty_field)))
        if quantity <= 1e-12:
            continue
        unit = str(row.get("uom") or "UNKNOWN").strip().upper() or "UNKNOWN"
        totals[unit] += quantity
    return json.dumps(
        {unit: round(value, 6) for unit, value in sorted(totals.items())},
        ensure_ascii=False,
        sort_keys=True,
    )


def _write_proof_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    preferred_fields: Sequence[str],
) -> None:
    fields = list(preferred_fields)
    seen = set(fields)
    for row in rows:
        for field in row:
            if field not in seen:
                fields.append(field)
                seen.add(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _baseline_lot_proof() -> dict[str, Any]:
    return {
        "lot_proof_status": "not_applicable_simulated_reference",
        "lot_proof_valid": True,
        "lot_proof_extracted_before_retention": True,
        "lot_proof_detail_retained": False,
        "lot_expected_risk_event_ids": "",
        "resolved_lot_trace_enabled": "not_applicable_reference",
        "lot_trace_runtime_gate_pass": True,
        "lot_root_gate_evaluable": False,
        "lot_root_gate_required": False,
        "lot_root_gate_pass": True,
        "expected_risk_application_row_count": 0,
        "positive_tagged_shipment_due_within_horizon_count": 0,
        "positive_tagged_shipment_due_within_horizon_qty": 0.0,
        "direct_risk_tagged_nonreceipt_lot_count": 0,
        "impacted_receipt_lot_count": 0,
        "impacted_receipt_qty": 0.0,
        "impacted_receipt_qty_by_uom_json": "{}",
        "impacted_intermediate_descendant_lot_count": 0,
        "impacted_intermediate_descendant_qty_touched_upper_by_uom_json": "{}",
        "impacted_finished_descendant_lot_count": 0,
        "impacted_finished_descendant_qty_touched_upper": 0.0,
        "impacted_finished_descendant_qty_touched_upper_by_uom_json": "{}",
        "impacted_client_delivery_descendant_lot_count": 0,
        "impacted_client_delivery_event_count": 0,
        "impacted_client_delivery_qty_touched_upper": 0.0,
        "impacted_client_delivery_qty_touched_upper_by_uom_json": "{}",
        "impacted_genealogy_link_count": 0,
        "impacted_genealogy_max_depth": 0,
        "impacted_first_day": "",
        "impacted_last_day": "",
        "impacted_finished_product_ids": "",
        "impacted_item_ids": "",
        "impacted_site_ids": "",
        "impacted_client_site_ids": "",
        "lot_genealogy_integrity_status": "not_applicable_reference",
        "lot_genealogy_missing_event_lot_count": 0,
        "lot_lineage_horizon_status": "not_applicable_reference",
        "impacted_receipt_semantics": (
            "reception utilisable dans le modele, pas arrivee physique separee"
        ),
        "quality_hold_reconstructed_interval_count": 0,
        "quality_hold_reconstructed_qty": 0.0,
        "quality_hold_interval_status": "not_applicable_reference",
        "quality_hold_interval_relative_csv": "",
        "lot_quantification_scope": (
            "genealogical_touch_not_causal_delay; descendant full-lot quantities are upper bounds"
        ),
        "source_row_semantics": (
            "identifiant technique de ligne, pas numéro de lot industriel"
        ),
        "lot_proof_relative_dir": "",
    }


def _not_traced_lot_proof(reason: str) -> dict[str, Any]:
    proof = _baseline_lot_proof()
    proof.update(
        {
            "lot_proof_status": "not_traced_on_replication_cpu_control",
            "lot_proof_valid": "",
            "lot_proof_extracted_before_retention": True,
            "lot_genealogy_integrity_status": "not_applicable_not_traced",
            "lot_lineage_horizon_status": "not_applicable_not_traced",
            "lot_proof_not_traced_reason": reason,
        }
    )
    return proof


def _resolved_lot_trace_enabled(case_dir: Path) -> bool | None:
    """Read the engine-resolved lot-trace flag, if the summary is available."""

    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    if not summary_path.is_file():
        return None
    summary = _read_json(summary_path)
    policy = summary.get("policy") or {}
    if "lot_trace_enabled" in policy:
        return bool(policy.get("lot_trace_enabled"))
    capabilities = summary.get("capabilities") or {}
    if "lot_trace_enabled" in capabilities:
        return bool(capabilities.get("lot_trace_enabled"))
    return None


def _lane_row_matches(
    row: Mapping[str, Any], lane: campaign_core.Lane, *, shipment: bool
) -> bool:
    supplier_field = "src_node_id" if shipment else "supplier_id"
    return (
        str(row.get(supplier_field) or "") == lane.supplier_id
        and str(row.get("dst_node_id") or "") == lane.dst_node_id
        and str(row.get("item_id") or "") == lane.item_id
    )


def _lot_root_gate_inputs(
    *,
    case_dir: Path,
    lane: campaign_core.Lane,
    expected_event_ids: set[str],
    days: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Return risk-application rows and tagged shipments usable in-horizon."""

    risk_path = case_dir / "data" / "supplier_risk_events_applied_daily.csv"
    shipment_path = case_dir / "data" / "production_supplier_shipments_daily.csv"
    if not risk_path.is_file() or not shipment_path.is_file():
        return [], [], False
    applied = [
        dict(row)
        for row in _read_csv(risk_path)
        if 0 <= _to_int(row.get("day"), -1) < days
        and _lane_row_matches(row, lane, shipment=False)
        and bool(_risk_event_tokens(row.get("event_ids")) & expected_event_ids)
    ]
    due_shipments = [
        dict(row)
        for row in _read_csv(shipment_path)
        if _lane_row_matches(row, lane, shipment=True)
        and bool(_risk_event_tokens(row.get("risk_event_ids")) & expected_event_ids)
        and _to_float(row.get("shipped_qty")) > 1e-12
        and 0 <= _to_int(row.get("arrival_day"), -1) < days
    ]
    return applied, due_shipments, True


def _quality_hold_wait_intervals(
    *,
    scenario: campaign_core.Scenario,
    shipments: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Reconstruct the model's quality wait; this is not native quarantine stock."""

    if scenario.mechanism_key != "quality_hold":
        return []
    quality_delay_days = max(0, int(math.ceil(_to_float(scenario.value) - 1e-12)))
    rows: list[dict[str, Any]] = []
    for row in shipments:
        usable_day = _to_int(row.get("arrival_day"), -1)
        rows.append(
            {
                "shipment_id": str(row.get("shipment_id") or ""),
                "supplier_id": str(row.get("src_node_id") or ""),
                "dst_node_id": str(row.get("dst_node_id") or ""),
                "item_id": str(row.get("item_id") or ""),
                "technical_lot_reference": str(row.get("shipment_id") or ""),
                "estimated_physical_arrival_day": usable_day - quality_delay_days,
                "usable_receipt_day": usable_day,
                "tested_quality_wait_days": quality_delay_days,
                "usable_qty": max(0.0, _to_float(row.get("shipped_qty"))),
                "uom": str(row.get("uom") or ""),
                "risk_event_ids": str(row.get("risk_event_ids") or ""),
                "interval_status": (
                    "reconstructed_interval_not_native_quarantine_stock_state"
                ),
                "source_row_semantics": (
                    "technical shipment/line identifier, not an industrial lot number"
                ),
            }
        )
    return rows


def extract_lot_impact_proof(
    *,
    case_dir: Path,
    scenario: campaign_core.Scenario,
    graph: Mapping[str, Any],
    stage: str,
    lot_trace_required: bool = True,
    days: int = 720,
) -> dict[str, Any]:
    """Trace a configured risk from directly tagged receipts to descendants.

    Risk IDs are deliberately used only to identify received root lots.  Every
    downstream lot is found through the exported parent-to-child genealogy,
    because the current FIFO ledger does not guarantee that a child directly
    inherits its parent's risk IDs.  Full descendant quantities are exposure
    upper bounds, not quantities delayed or lost because of the incident.
    """

    if scenario.is_campaign_baseline:
        proof = _baseline_lot_proof()
        resolved_lot_trace = _resolved_lot_trace_enabled(case_dir)
        proof["resolved_lot_trace_enabled"] = (
            resolved_lot_trace
            if resolved_lot_trace is not None
            else "unknown_fixture"
        )
        proof["lot_trace_runtime_gate_pass"] = (
            resolved_lot_trace is True
            if lot_trace_required
            else resolved_lot_trace in {False, None}
        )
        proof_dir = case_dir / "proofs"
        proof_dir.mkdir(parents=True, exist_ok=True)
        _write_json(proof_dir / "lot_impact_summary.json", proof)
        return proof
    if not lot_trace_required:
        proof = _not_traced_lot_proof(
            "confirmation replication; lot trace retained on the first paired seed "
            "for each lane and mathematical family"
        )
        proof_dir = case_dir / "proofs"
        proof_dir.mkdir(parents=True, exist_ok=True)
        _write_json(proof_dir / "lot_impact_summary.json", proof)
        return proof
    events_path = case_dir / "data" / "production_lot_events.csv"
    genealogy_path = case_dir / "data" / "production_lot_genealogy.csv"
    if not events_path.is_file() or not genealogy_path.is_file():
        raise FileNotFoundError(
            "La preuve lots doit être extraite avant rétention; fichiers absents: "
            f"events={events_path.is_file()}, genealogy={genealogy_path.is_file()}"
        )
    events = _read_csv(events_path)
    genealogy = _read_csv(genealogy_path)
    chain = campaign_core.CHAIN_BY_ID[scenario.chain_id]
    lane = chain.affected_lanes[0]
    expected_event_ids = {
        f"{scenario.scenario_id}__lane{index}"
        for index, _affected_lane in enumerate(chain.affected_lanes, 1)
    }
    resolved_lot_trace = _resolved_lot_trace_enabled(case_dir)
    applied_risk_rows, due_tagged_shipments, root_gate_evaluable = (
        _lot_root_gate_inputs(
            case_dir=case_dir,
            lane=lane,
            expected_event_ids=expected_event_ids,
            days=days,
        )
    )
    root_gate_required = bool(applied_risk_rows and due_tagged_shipments)
    quality_wait_rows = _quality_hold_wait_intervals(
        scenario=scenario,
        shipments=due_tagged_shipments,
    )

    tagged_events = [
        row
        for row in events
        if _risk_event_tokens(row.get("risk_event_ids")) & expected_event_ids
    ]
    receipt_events = [
        row
        for row in tagged_events
        if str(row.get("lot_id") or "")
        and str(row.get("node_id") or "") == lane.dst_node_id
        and str(row.get("item_id") or "") == lane.item_id
        and (
            str(row.get("event_type") or "") == "lane_receipt"
            or str(row.get("source_type") or "") == "lane_receipt"
        )
        and _to_float(row.get("qty")) > 1e-12
    ]
    # create_lot emits exactly one creation event.  Keep the first in case a
    # future engine version also emits a tagged audit event for the same lot.
    receipt_by_lot: dict[str, dict[str, Any]] = {}
    for row in receipt_events:
        receipt_by_lot.setdefault(str(row.get("lot_id")), dict(row))
    root_ids = set(receipt_by_lot)
    lot_trace_runtime_gate_pass = resolved_lot_trace is not False
    lot_root_gate_pass = not root_gate_required or bool(root_ids)

    first_event_by_lot: dict[str, dict[str, Any]] = {}
    for row in events:
        lot_id = str(row.get("lot_id") or "")
        if lot_id:
            first_event_by_lot.setdefault(lot_id, dict(row))
    children_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in genealogy:
        parent = str(row.get("parent_lot_id") or "")
        child = str(row.get("child_lot_id") or "")
        if parent and child:
            children_by_parent[parent].append(dict(row))

    depths = {lot_id: 0 for lot_id in root_ids}
    queue = deque(sorted(root_ids))
    impacted_links: list[dict[str, Any]] = []
    seen_link_keys: set[tuple[str, str, str, str]] = set()
    while queue:
        parent = queue.popleft()
        for link in children_by_parent.get(parent, []):
            child = str(link.get("child_lot_id") or "")
            link_key = (
                parent,
                child,
                str(link.get("link_type") or ""),
                str(link.get("day") or ""),
            )
            if link_key not in seen_link_keys:
                impacted_links.append(link)
                seen_link_keys.add(link_key)
            child_depth = depths[parent] + 1
            if child not in depths or child_depth < depths[child]:
                depths[child] = child_depth
                queue.append(child)
    descendant_ids = set(depths) - root_ids
    finished_item_ids = {f"item:{product}" for product in TARGET_PRODUCTS}
    finished_ids = {
        lot_id
        for lot_id in descendant_ids
        if str(first_event_by_lot.get(lot_id, {}).get("item_id") or "")
        in finished_item_ids
    }
    intermediate_ids = descendant_ids - finished_ids
    client_node_ids = {
        str(node.get("id") or "")
        for node in graph.get("nodes") or []
        if str(node.get("type") or "").lower() in {"client", "customer"}
        or str(node.get("id") or "") == chain.client_node_id
    }
    client_events = [
        dict(row)
        for row in events
        if str(row.get("lot_id") or "") in descendant_ids
        and str(row.get("event_type") or "") == "demand_service"
        and str(row.get("node_id") or "") in client_node_ids
        and _to_float(row.get("qty")) > 1e-12
    ]
    descendant_events = [
        first_event_by_lot[lot_id]
        for lot_id in sorted(descendant_ids)
        if lot_id in first_event_by_lot
    ]
    intermediate_events = [
        first_event_by_lot[lot_id]
        for lot_id in sorted(intermediate_ids)
        if lot_id in first_event_by_lot
    ]
    finished_events = [
        first_event_by_lot[lot_id]
        for lot_id in sorted(finished_ids)
        if lot_id in first_event_by_lot
    ]
    missing_event_lots = sorted(
        {
            lot_id
            for link in impacted_links
            for lot_id in (
                str(link.get("parent_lot_id") or ""),
                str(link.get("child_lot_id") or ""),
            )
            if lot_id and lot_id not in first_event_by_lot
        }
    )
    impacted_days = [
        _to_int(row.get("day"), -10**9)
        for row in [*receipt_by_lot.values(), *descendant_events, *client_events]
        if _to_int(row.get("day"), -10**9) > -10**8
    ]
    finished_qty = sum(max(0.0, _to_float(row.get("qty"))) for row in finished_events)
    client_qty = sum(max(0.0, _to_float(row.get("qty"))) for row in client_events)
    if not root_ids:
        lineage_status = "no_impacted_usable_receipt_within_simulated_horizon"
    elif client_events:
        lineage_status = "genealogy_reaches_client_delivery"
    elif finished_ids:
        lineage_status = "genealogy_reaches_finished_product_not_client_within_horizon"
    elif descendant_ids:
        lineage_status = "genealogy_stops_at_intermediate_or_wip_within_horizon"
    else:
        lineage_status = "receipt_not_transformed_within_horizon"
    if resolved_lot_trace is False:
        integrity = "invalid_engine_resolved_lot_trace_disabled"
        status = "invalid_lot_trace_not_enabled"
    elif root_gate_required and not root_ids:
        integrity = "invalid_expected_tagged_usable_receipt_root_missing"
        status = "invalid_missing_tagged_usable_receipt_root"
    else:
        integrity = (
            "missing_referenced_lot_events_genealogy_may_be_truncated"
            if missing_event_lots
            else "all_impacted_genealogy_lots_have_exported_events"
        )
        status = (
            "valid_no_impacted_usable_receipt_within_horizon"
            if not root_ids
            else (
                "valid_with_genealogy_limit"
                if missing_event_lots
                else "valid_genealogy_traversal"
            )
        )
    proof_dir = case_dir / "proofs"
    proof_dir.mkdir(parents=True, exist_ok=True)
    detail_retained = stage == "confirmation" and bool(root_ids)
    source_row_semantics = (
        "identifiant technique de ligne, pas numéro de lot industriel"
    )
    proof: dict[str, Any] = {
        "lot_proof_status": status,
        "lot_proof_valid": (
            lot_trace_runtime_gate_pass
            and lot_root_gate_pass
            and not missing_event_lots
        ),
        "lot_proof_extracted_before_retention": True,
        "lot_proof_detail_retained": detail_retained,
        "lot_expected_risk_event_ids": "|".join(sorted(expected_event_ids)),
        "resolved_lot_trace_enabled": (
            resolved_lot_trace if resolved_lot_trace is not None else "unknown_fixture"
        ),
        "lot_trace_runtime_gate_pass": lot_trace_runtime_gate_pass,
        "lot_root_gate_evaluable": root_gate_evaluable,
        "lot_root_gate_required": root_gate_required,
        "lot_root_gate_pass": lot_root_gate_pass,
        "expected_risk_application_row_count": len(applied_risk_rows),
        "positive_tagged_shipment_due_within_horizon_count": len(
            due_tagged_shipments
        ),
        "positive_tagged_shipment_due_within_horizon_qty": sum(
            max(0.0, _to_float(row.get("shipped_qty")))
            for row in due_tagged_shipments
        ),
        "direct_risk_tagged_nonreceipt_lot_count": len(
            {
                str(row.get("lot_id") or "")
                for row in tagged_events
                if str(row.get("lot_id") or "") not in root_ids
            }
            - {""}
        ),
        "impacted_receipt_lot_count": len(root_ids),
        "impacted_receipt_qty": sum(
            max(0.0, _to_float(row.get("qty"))) for row in receipt_by_lot.values()
        ),
        "impacted_receipt_qty_by_uom_json": _quantities_by_uom_json(
            receipt_by_lot.values(), qty_field="qty"
        ),
        "impacted_intermediate_descendant_lot_count": len(intermediate_ids),
        "impacted_intermediate_descendant_qty_touched_upper_by_uom_json": (
            _quantities_by_uom_json(intermediate_events, qty_field="qty")
        ),
        "impacted_finished_descendant_lot_count": len(finished_ids),
        "impacted_finished_descendant_qty_touched_upper": finished_qty,
        "impacted_finished_descendant_qty_touched_upper_by_uom_json": (
            _quantities_by_uom_json(finished_events, qty_field="qty")
        ),
        "impacted_client_delivery_descendant_lot_count": len(
            {str(row.get("lot_id") or "") for row in client_events}
        ),
        "impacted_client_delivery_event_count": len(client_events),
        "impacted_client_delivery_qty_touched_upper": client_qty,
        "impacted_client_delivery_qty_touched_upper_by_uom_json": (
            _quantities_by_uom_json(client_events, qty_field="qty")
        ),
        "impacted_genealogy_link_count": len(impacted_links),
        "impacted_genealogy_max_depth": max(depths.values(), default=0),
        "impacted_first_day": min(impacted_days) if impacted_days else "",
        "impacted_last_day": max(impacted_days) if impacted_days else "",
        "impacted_finished_product_ids": "|".join(
            sorted(
                {
                    str(row.get("item_id") or "").replace("item:", "")
                    for row in finished_events
                    if str(row.get("item_id") or "")
                }
            )
        ),
        "impacted_item_ids": "|".join(
            sorted(
                {
                    str(row.get("item_id") or "")
                    for row in [*receipt_by_lot.values(), *descendant_events]
                    if str(row.get("item_id") or "")
                }
            )
        ),
        "impacted_site_ids": "|".join(
            sorted(
                {
                    str(row.get("node_id") or "")
                    for row in [*receipt_by_lot.values(), *descendant_events]
                    if str(row.get("node_id") or "")
                }
            )
        ),
        "impacted_client_site_ids": "|".join(
            sorted(
                {
                    str(row.get("node_id") or "")
                    for row in client_events
                    if str(row.get("node_id") or "")
                }
            )
        ),
        "lot_genealogy_integrity_status": integrity,
        "lot_genealogy_missing_event_lot_count": len(missing_event_lots),
        "lot_lineage_horizon_status": lineage_status,
        "impacted_receipt_semantics": (
            "risk-tagged usable receipt in the model; physical arrival is not a "
            "separate native quarantine-stock state"
        ),
        "quality_hold_reconstructed_interval_count": len(quality_wait_rows),
        "quality_hold_reconstructed_qty": sum(
            max(0.0, _to_float(row.get("usable_qty"))) for row in quality_wait_rows
        ),
        "quality_hold_interval_status": (
            "reconstructed_interval_not_native_quarantine_stock_state"
            if scenario.mechanism_key == "quality_hold"
            else "not_applicable_other_mechanism"
        ),
        "quality_hold_interval_relative_csv": (
            str((proof_dir / "quality_hold_wait_intervals.csv").relative_to(
                case_dir.parent.parent.parent
            ))
            if quality_wait_rows
            else ""
        ),
        "lot_quantification_scope": (
            "direct receipt quantity is exact; descendant and client full-lot quantities "
            "are genealogical-touch upper bounds, not causal delay/loss"
        ),
        "source_row_semantics": source_row_semantics,
        "lot_proof_relative_dir": str(proof_dir.relative_to(case_dir.parent.parent.parent)),
    }
    if detail_retained:
        root_rows = [
            {
                **row,
                "lot_role": "direct_risk_tagged_usable_receipt_root",
                "source_row_semantics": source_row_semantics,
            }
            for row in receipt_by_lot.values()
        ]
        descendant_rows = [
            {
                **row,
                "lot_role": (
                    "finished_descendant"
                    if str(row.get("lot_id") or "") in finished_ids
                    else "intermediate_descendant"
                ),
                "genealogy_depth": depths.get(str(row.get("lot_id") or ""), ""),
                "full_lot_qty_is_exposure_upper_bound": True,
                "source_row_semantics": source_row_semantics,
            }
            for row in descendant_events
        ]
        detailed_links = [
            {
                **row,
                "parent_genealogy_depth": depths.get(
                    str(row.get("parent_lot_id") or ""), ""
                ),
                "child_genealogy_depth": depths.get(
                    str(row.get("child_lot_id") or ""), ""
                ),
                "source_row_semantics": source_row_semantics,
            }
            for row in impacted_links
        ]
        detailed_clients = [
            {
                **row,
                "full_served_qty_is_exposure_upper_bound": True,
                "source_row_semantics": source_row_semantics,
            }
            for row in client_events
        ]
        _write_proof_csv(
            proof_dir / "impacted_receipt_lots.csv",
            root_rows,
            preferred_fields=(
                "lot_id",
                "day",
                "node_id",
                "item_id",
                "qty",
                "uom",
                "risk_event_ids",
                "shipment_id",
                "source_row",
                "supplier_id",
                "lot_role",
                "source_row_semantics",
            ),
        )
        _write_proof_csv(
            proof_dir / "impacted_descendant_lots.csv",
            descendant_rows,
            preferred_fields=(
                "lot_id",
                "day",
                "node_id",
                "item_id",
                "qty",
                "uom",
                "lot_role",
                "genealogy_depth",
                "full_lot_qty_is_exposure_upper_bound",
                "source_row",
                "supplier_id",
                "source_row_semantics",
            ),
        )
        _write_proof_csv(
            proof_dir / "impacted_genealogy.csv",
            detailed_links,
            preferred_fields=(
                "day",
                "link_type",
                "parent_lot_id",
                "parent_node_id",
                "parent_item_id",
                "child_lot_id",
                "child_node_id",
                "child_item_id",
                "parent_qty",
                "child_qty",
                "parent_genealogy_depth",
                "child_genealogy_depth",
                "source_row",
                "supplier_id",
                "source_row_semantics",
            ),
        )
        _write_proof_csv(
            proof_dir / "impacted_client_deliveries.csv",
            detailed_clients,
            preferred_fields=(
                "day",
                "lot_id",
                "node_id",
                "item_id",
                "qty",
                "uom",
                "event_type",
                "full_served_qty_is_exposure_upper_bound",
                "source_row_semantics",
            ),
        )
    if quality_wait_rows:
        _write_proof_csv(
            proof_dir / "quality_hold_wait_intervals.csv",
            quality_wait_rows,
            preferred_fields=(
                "shipment_id",
                "supplier_id",
                "dst_node_id",
                "item_id",
                "technical_lot_reference",
                "estimated_physical_arrival_day",
                "usable_receipt_day",
                "tested_quality_wait_days",
                "usable_qty",
                "uom",
                "risk_event_ids",
                "interval_status",
                "source_row_semantics",
            ),
        )
    _write_json(proof_dir / "lot_impact_summary.json", proof)
    return proof


OPERATION_FIELDS = (
    "target_produced_qty",
    "target_released_qty",
    "component_arrived_qty",
    "component_input_stock_j0",
    "component_input_stock_end",
    "component_input_stock_min",
    "component_input_stock_qty_days",
    "component_days_at_zero",
    "component_safety_stock_qty",
    "component_days_below_safety",
    "supplier_stock_j0",
    "supplier_stock_end",
    "supplier_stock_min",
)


def attach_operational_baseline(
    row: dict[str, Any],
    *,
    scenario: campaign_core.Scenario,
    baseline_row: Mapping[str, Any] | None,
) -> None:
    if scenario.is_campaign_baseline:
        return
    if baseline_row is None:
        raise ValueError("Une baseline appariée est requise")
    prefix = f"baseline_chain__{scenario.chain_id}__ops__"
    for field in OPERATION_FIELDS:
        baseline_value = _to_float(baseline_row.get(f"{prefix}{field}"), math.nan)
        current = _to_float(row.get(field), math.nan)
        row[f"paired_baseline_{field}"] = baseline_value
        row[f"{field}_delta_vs_paired_baseline"] = current - baseline_value
    row["target_production_shortfall_vs_paired_baseline"] = max(
        0.0, -_to_float(row.get("target_released_qty_delta_vs_paired_baseline"))
    )
    row["target_production_shortfall_ratio_vs_paired_baseline"] = (
        row["target_production_shortfall_vs_paired_baseline"]
        / max(1e-12, abs(_to_float(row.get("paired_baseline_target_released_qty"))))
        if abs(_to_float(row.get("paired_baseline_target_released_qty"))) > 1e-12
        else 0.0
    )
    row["supplier_on_due_delta_vs_paired_baseline"] = (
        _to_float(row.get("supplier_on_due_date_proxy"), 1.0)
        - _to_float(row.get("paired_baseline_supplier_on_due_date_proxy"), 1.0)
    )
    paired_active_shipped = _to_float(
        baseline_row.get(
            f"baseline_chain__{scenario.chain_id}__active_window_shipped_qty"
        )
    )
    paired_active_pulled = _to_float(
        baseline_row.get(
            f"baseline_chain__{scenario.chain_id}__active_window_pulled_qty"
        )
    )
    current_active_shipped = _to_float(row.get("active_window_shipped_qty"))
    row["paired_baseline_active_window_shipped_qty"] = paired_active_shipped
    row["paired_baseline_active_window_pulled_qty"] = paired_active_pulled
    row["paired_baseline_active_window_flow_exercised"] = (
        paired_active_shipped > 1e-12 and paired_active_pulled > 1e-12
    )
    row["active_window_flow_coverage_vs_paired_baseline"] = (
        min(1.0, max(0.0, current_active_shipped) / paired_active_shipped)
        if paired_active_shipped > 1e-12
        else 1.0
    )


def classify_effect(row: Mapping[str, Any]) -> str:
    """Describe where an applied stress first has a measurable consequence."""

    if not campaign_core.as_bool(row.get("paired_baseline_active_window_flow_exercised")):
        return "voie_non_sollicitee_pendant_la_fenetre_de_stress"
    service_delta = _to_float(
        row.get("target_on_due_date_proxy_delta_vs_paired_baseline")
    )
    backlog_delta = _to_float(row.get("incremental_target_backlog_qty_days"))
    end_backlog = _to_float(row.get("target_backlog_end_qty"))
    baseline_end_backlog = _to_float(
        row.get("paired_baseline_target_backlog_end_qty")
    )
    if service_delta < -1e-8 or backlog_delta > 1e-6 or end_backlog > baseline_end_backlog + 1e-6:
        return "effet_mesure_sur_le_service_client"
    production_shortfall = _to_float(
        row.get("target_production_shortfall_vs_paired_baseline")
    )
    baseline_released = abs(_to_float(row.get("paired_baseline_target_released_qty")))
    if production_shortfall > max(1e-6, baseline_released * 1e-9):
        return "effet_mesure_sur_la_production_mais_pas_sur_le_service_client"
    flow_coverage = _to_float(
        row.get("active_window_flow_coverage_vs_paired_baseline"), 1.0
    )
    lead_delta = _to_float(row.get("supplier_on_due_delta_vs_paired_baseline"))
    arrived_delta = _to_float(row.get("component_arrived_qty_delta_vs_paired_baseline"))
    stock_end_delta = _to_float(row.get("component_input_stock_end_delta_vs_paired_baseline"))
    baseline_arrived = abs(_to_float(row.get("paired_baseline_component_arrived_qty")))
    baseline_stock = abs(_to_float(row.get("paired_baseline_component_input_stock_end")))
    if (
        flow_coverage < 1.0 - 1e-8
        or lead_delta < -1e-8
        or abs(arrived_delta) > max(1e-6, baseline_arrived * 1e-9)
        or abs(stock_end_delta) > max(1e-6, baseline_stock * 1e-9)
    ):
        return "effet_amont_absorbe_avant_le_client"
    return "stress_applique_sans_effet_mesurable"


def attach_lane_specific_capacity_validation(
    row: dict[str, Any],
    *,
    case_dir: Path,
    scenario: campaign_core.Scenario,
    reference_by_chain: Mapping[str, LaneReference],
    physical_capacity_by_lane_map: Mapping[tuple[str, str, str], float],
    days: int,
) -> None:
    """Audit positive prepared floors on the lane's actual stress window.

    The reused V4 extractor validates the common calendar window and knows the
    legacy key ``availability``.  Network scenarios instead use lane-specific
    windows and the explicit key ``supply_availability``.  This additive audit
    keeps V4 and engine behavior unchanged while preserving strict equality.
    """

    if scenario.is_campaign_baseline:
        row["network_capacity_validation_basis"] = (
            "baseline_all_horizon_core_validation"
        )
        row["network_active_window_capacity_matches_expected"] = (
            campaign_core.as_bool(
                row.get("applied_physical_capacity_matches_expected")
            )
        )
        return

    reference = reference_by_chain[scenario.chain_id]
    start_day = max(0, int(reference.active_window_start_day))
    end_day = min(days - 1, int(reference.active_window_end_day))
    chain = campaign_core.CHAIN_BY_ID[scenario.chain_id]
    capacity_path = case_dir / "data" / "production_supplier_capacity_daily.csv"
    if not capacity_path.is_file():
        raise FileNotFoundError(
            "Lane-specific physical-capacity audit requires "
            f"{capacity_path}"
        )
    capacity_rows = _read_csv(capacity_path)
    lane_audits: list[dict[str, Any]] = []
    for lane in chain.affected_lanes:
        nominal = _to_float(physical_capacity_by_lane_map.get(lane.key), 0.0)
        if nominal <= 0.0:
            continue
        expected = (
            nominal * _to_float(scenario.value, 1.0)
            if scenario.mechanism_key in {"availability", "supply_availability"}
            else nominal
        )
        matched = [
            item
            for item in capacity_rows
            if str(item.get("node_id") or "") == lane.supplier_id
            and str(item.get("item_id") or "") == lane.item_id
            and start_day <= _to_int(item.get("day"), -1) <= end_day
        ]
        outside = [
            item
            for item in capacity_rows
            if str(item.get("node_id") or "") == lane.supplier_id
            and str(item.get("item_id") or "") == lane.item_id
            and 0 <= _to_int(item.get("day"), -1) < days
            and not start_day <= _to_int(item.get("day"), -1) <= end_day
        ]
        observed = [
            _to_float(item.get("capacity_qty_per_day"), math.nan)
            for item in matched
        ]
        outside_observed = [
            _to_float(item.get("capacity_qty_per_day"), math.nan)
            for item in outside
        ]
        observed_days = {
            _to_int(item.get("day"), -1)
            for item in matched
        }
        matches = bool(observed) and len(observed_days) == end_day - start_day + 1
        matches = matches and all(
            math.isfinite(value)
            and campaign_core.values_equal(value, expected)
            for value in observed
        )
        outside_days = {_to_int(item.get("day"), -1) for item in outside}
        outside_matches = len(outside_days) == days - (end_day - start_day + 1)
        outside_matches = outside_matches and all(
            math.isfinite(value)
            and campaign_core.values_equal(value, nominal)
            for value in outside_observed
        )
        matches = matches and outside_matches
        lane_audits.append(
            {
                "lane_key": "|".join(lane.key),
                "expected": expected,
                "observed_min": min(observed) if observed else math.nan,
                "observed_max": max(observed) if observed else math.nan,
                "row_count": len(matched),
                "day_count": len(observed_days),
                "outside_expected_nominal": nominal,
                "outside_observed_min": (
                    min(outside_observed) if outside_observed else math.nan
                ),
                "outside_observed_max": (
                    max(outside_observed) if outside_observed else math.nan
                ),
                "outside_row_count": len(outside),
                "outside_day_count": len(outside_days),
                "outside_match": outside_matches,
                "match": matches,
            }
        )

    # A zero prepared floor remains governed by the graph, as in the V4 core.
    overall_match = all(item["match"] for item in lane_audits)
    row["network_capacity_validation_basis"] = (
        "lane_specific_active_180d_window_prepared_positive_floor"
    )
    row["network_capacity_validation_start_day"] = start_day
    row["network_capacity_validation_end_day"] = end_day
    row["network_capacity_validation_lane_count"] = len(lane_audits)
    row["network_capacity_validation_row_count"] = sum(
        int(item["row_count"]) for item in lane_audits
    )
    row["network_expected_active_capacity_min_qty_per_day"] = (
        min(float(item["expected"]) for item in lane_audits)
        if lane_audits
        else 0.0
    )
    row["network_observed_active_capacity_min_qty_per_day"] = (
        min(float(item["observed_min"]) for item in lane_audits)
        if lane_audits
        else 0.0
    )
    row["network_observed_active_capacity_max_qty_per_day"] = (
        max(float(item["observed_max"]) for item in lane_audits)
        if lane_audits
        else 0.0
    )
    row["network_active_window_capacity_matches_expected"] = overall_match
    row["network_outside_active_window_capacity_matches_nominal"] = all(
        item["outside_match"] for item in lane_audits
    )
    row["network_capacity_validation_lanes_json"] = json.dumps(
        lane_audits, ensure_ascii=False, sort_keys=True
    )
    # Canonical flag consumed by the strict reused validation function.
    row["expected_incident_capacity_qty_per_day"] = row[
        "network_expected_active_capacity_min_qty_per_day"
    ]
    row["applied_physical_capacity_matches_expected"] = overall_match


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    campaign_core.write_csv_atomic(path, rows)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    campaign_core.write_json_atomic(path, payload)


def _case_paths(
    output_dir: Path, scenario: campaign_core.Scenario, seed: int
) -> tuple[Path, Path, Path]:
    case_dir = output_dir / "cases" / scenario.execution_scenario_id / f"seed_{seed}"
    return (
        case_dir,
        case_dir / "summaries" / "first_simulation_summary.json",
        case_dir / "data" / "production_demand_service_daily.csv",
    )


def build_network_engine_command(
    config: campaign_core.RunConfig,
    *,
    case_dir: Path,
    seed: int,
    risk_csv: Path | None,
    lot_trace_required: bool = True,
) -> list[str]:
    """Build the V4 command, then opt this network campaign into lot trace."""

    command = campaign_core.build_engine_command(
        config, case_dir=case_dir, seed=seed, risk_csv=risk_csv
    )
    # argparse.BooleanOptionalAction is last-wins.  Keep the opt-in after V4's
    # --no-lot-trace, profile arguments, managed protocol and risk CSV.
    command.append("--lot-trace" if lot_trace_required else "--no-lot-trace")
    return command


def run_case(
    *,
    config: campaign_core.RunConfig,
    graph: Mapping[str, Any],
    chains: Sequence[campaign_core.Chain],
    reference_by_chain: Mapping[str, LaneReference],
    scenario: campaign_core.Scenario,
    seed: int,
    stage: str,
    risk_csv: Path | None,
    configured_event_count: int,
    baseline_row: Mapping[str, Any] | None,
    lot_trace_required: bool,
) -> dict[str, Any]:
    case_dir, summary_path, service_path = _case_paths(config.output_dir, scenario, seed)
    status = "reextracted" if summary_path.is_file() and service_path.is_file() else "executed"
    if status == "executed":
        case_dir.mkdir(parents=True, exist_ok=True)
        command = build_network_engine_command(
            config,
            case_dir=case_dir,
            seed=seed,
            risk_csv=risk_csv,
            lot_trace_required=lot_trace_required,
        )
        log_path = case_dir / "campaign_engine.log"
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n[{utc_now()}] COMMAND {json.dumps(command, ensure_ascii=False)}\n")
            completed = subprocess.run(
                command,
                cwd=config.repo_root,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Échec moteur pour {scenario.scenario_id}/seed_{seed}; voir {log_path}"
            )
    row = campaign_core.extract_case_metrics(
        case_dir=case_dir,
        scenario=scenario,
        seed=seed,
        stage=stage,
        status=status,
        days=config.days,
        configured_event_count=configured_event_count,
        physical_capacity_by_lane_map=config.physical_capacity_by_lane,
    )
    row["common_comparison_start_day"] = incident_window(config.days)[0]
    row["common_comparison_end_day"] = incident_window(config.days)[1]
    if not scenario.is_campaign_baseline:
        reference = reference_by_chain[scenario.chain_id]
        row["stress_start_day"] = reference.active_window_start_day
        row["stress_end_day"] = reference.active_window_end_day
        row["stress_window_basis"] = (
            "strongest_180d_reference_flow_window_for_this_lane"
        )
    relevant_chains = chains if scenario.is_campaign_baseline else (
        campaign_core.CHAIN_BY_ID[scenario.chain_id],
    )
    operations = extract_chain_operations(
        case_dir=case_dir, chains=relevant_chains, graph=graph, days=config.days
    )
    relevant_references = (
        tuple(reference_by_chain.values())
        if scenario.is_campaign_baseline
        else (reference_by_chain[scenario.chain_id],)
    )
    active_window_metrics = extract_active_window_shipment_metrics(
        case_dir=case_dir, references=relevant_references, days=config.days
    )
    if scenario.is_campaign_baseline:
        for chain_id, metrics in operations.items():
            for field, value in metrics.items():
                row[f"baseline_chain__{chain_id}__ops__{field}"] = value
        for chain_id, metrics in active_window_metrics.items():
            for field, value in metrics.items():
                row[f"baseline_chain__{chain_id}__{field}"] = value
    else:
        row.update(operations[scenario.chain_id])
        row.update(active_window_metrics[scenario.chain_id])
    campaign_core.attach_paired_baseline_metrics(
        row, scenario=scenario, baseline_row=baseline_row
    )
    if not scenario.is_campaign_baseline and baseline_row is not None:
        product = scenario.target_product_id
        row["paired_baseline_target_backlog_end_qty"] = _to_float(
            baseline_row.get(f"backlog_end_qty_{product}")
        )
        attach_operational_baseline(
            row, scenario=scenario, baseline_row=baseline_row
        )
    attach_lane_specific_capacity_validation(
        row,
        case_dir=case_dir,
        scenario=scenario,
        reference_by_chain=reference_by_chain,
        physical_capacity_by_lane_map=config.physical_capacity_by_lane,
        days=config.days,
    )
    campaign_core.validate_metric_row(
        row, scenario=scenario, days=config.days, baseline_row=baseline_row
    )
    row["effect_status"] = (
        "reference_simulee"
        if scenario.is_campaign_baseline
        else classify_effect(row)
    )
    # This must run before summary retention deletes data/.  Direct risk tags
    # identify only reception roots; downstream exposure is reconstructed via
    # the parent-to-child genealogy rather than assumed from child tags.
    lot_proof = extract_lot_impact_proof(
        case_dir=case_dir,
        scenario=scenario,
        graph=graph,
        stage=stage,
        lot_trace_required=lot_trace_required,
        days=config.days,
    )
    if lot_trace_required and str(lot_proof.get("lot_proof_status") or "").startswith(
        "invalid_"
    ):
        raise RuntimeError(
            "Lot proof gate failed for "
            f"{scenario.scenario_id}/seed_{seed}: {lot_proof['lot_proof_status']}"
        )
    row.update(lot_proof)
    row["lot_trace_required_for_paired_seed_block"] = lot_trace_required
    if lot_trace_required and not campaign_core.as_bool(
        lot_proof.get("lot_trace_runtime_gate_pass")
    ):
        raise RuntimeError(
            "Lot-trace runtime gate failed for paired seed block "
            f"{scenario.scenario_id}/seed_{seed}"
        )
    if config.retention == "summary":
        row["retention_removed"] = "|".join(
            campaign_core.prune_case_artifacts(case_dir)
        )
    return row


def _risk_inputs(
    output_dir: Path,
    scenarios: Sequence[campaign_core.Scenario],
    days: int,
    reference_by_chain: Mapping[str, LaneReference],
) -> dict[str, tuple[Path, int]]:
    result: dict[str, tuple[Path, int]] = {}
    risk_dir = output_dir / "inputs" / "risk_events"
    for scenario in scenarios:
        if scenario.is_campaign_baseline:
            continue
        chain = campaign_core.CHAIN_BY_ID[scenario.chain_id]
        reference = reference_by_chain[scenario.chain_id]
        mechanism = MECHANISM_BY_KEY[scenario.mechanism_key]
        rows = []
        for lane_index, lane in enumerate(chain.affected_lanes, 1):
            rows.append(
                {
                    "event_id": f"{scenario.scenario_id}__lane{lane_index}",
                    "risk_type": mechanism.risk_type,
                    "supplier_id": lane.supplier_id,
                    "item_id": lane.item_id,
                    "dst_node_id": lane.dst_node_id,
                    "edge_id": "",
                    "start_day": reference.active_window_start_day,
                    "end_day": reference.active_window_end_day,
                    "multiplier": scenario.value,
                    "notes": (
                        f"{mechanism.label}; niveau {scenario.level_label}; "
                        "fenêtre active propre à la voie, choisie sur le flux V10."
                    ),
                }
            )
        if not rows:
            raise ValueError(f"Aucun événement pour {scenario.scenario_id}")
        path = risk_dir / f"{scenario.scenario_id}.csv"
        campaign_core.write_risk_csv(path, rows)
        result[scenario.scenario_id] = (path, len(rows))
    return result


def _row_key(row: Mapping[str, Any]) -> tuple[str, int, str]:
    return (
        str(row.get("scenario_id") or ""),
        _to_int(row.get("seed"), -1),
        str(row.get("stage") or ""),
    )


def lot_trace_required_for_pair(
    *, stage: str, seed: int, seeds: Sequence[int]
) -> bool:
    """Resolve one lot-trace mode for a complete paired seed block.

    Lot tracing changes the engine's audited J0 representation because the lot
    ledger is part of that representation.  A reference and every stress
    compared with it must therefore use the same trace mode; otherwise a valid
    scientific pairing is impossible even when the physical state is neutral.
    """

    if stage in {"smoke", "screening"}:
        return True
    return stage == "confirmation" and bool(seeds) and seed == min(seeds)


def execute_stage(
    *,
    config: campaign_core.RunConfig,
    graph: Mapping[str, Any],
    chains: Sequence[campaign_core.Chain],
    reference_by_chain: Mapping[str, LaneReference],
    scenarios: Sequence[campaign_core.Scenario],
    seeds: Sequence[int],
    stage: str,
    risk_inputs: Mapping[str, tuple[Path, int]],
    metric_path: Path,
    workers: int,
) -> list[dict[str, Any]]:
    existing = _read_csv(metric_path) if metric_path.is_file() else []
    ledger = {_row_key(row): dict(row) for row in existing}
    baseline = next(item for item in scenarios if item.is_campaign_baseline)
    for seed in seeds:
        key = (baseline.scenario_id, seed, stage)
        if key not in ledger:
            paired_lot_trace = lot_trace_required_for_pair(
                stage=stage, seed=seed, seeds=seeds
            )
            row = run_case(
                config=config,
                graph=graph,
                chains=chains,
                reference_by_chain=reference_by_chain,
                scenario=baseline,
                seed=seed,
                stage=stage,
                risk_csv=None,
                configured_event_count=0,
                baseline_row=None,
                lot_trace_required=paired_lot_trace,
            )
            ledger[key] = row
            _write_csv(metric_path, list(ledger.values()))
            print(
                f"[{stage.upper()}] baseline seed={seed} "
                f"268091={_to_float(row.get('on_due_volume_proxy_268091')):.2%} "
                f"268967={_to_float(row.get('on_due_volume_proxy_268967')):.2%}",
                flush=True,
            )
    baselines = {
        _to_int(row.get("seed")): row
        for row in ledger.values()
        if str(row.get("scenario_id")) == "baseline_nominal"
        and str(row.get("stage")) == stage
    }
    jobs = [
        (scenario, seed)
        for scenario in scenarios
        if not scenario.is_campaign_baseline
        for seed in seeds
        if (scenario.scenario_id, seed, stage) not in ledger
    ]
    if jobs:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {}
            for scenario, seed in jobs:
                risk_csv, event_count = risk_inputs[scenario.scenario_id]
                futures[
                    pool.submit(
                        run_case,
                        config=config,
                        graph=graph,
                        chains=chains,
                        reference_by_chain=reference_by_chain,
                        scenario=scenario,
                        seed=seed,
                        stage=stage,
                        risk_csv=risk_csv,
                        configured_event_count=event_count,
                        baseline_row=baselines[seed],
                        lot_trace_required=lot_trace_required_for_pair(
                            stage=stage, seed=seed, seeds=seeds
                        ),
                    )
                ] = (scenario, seed)
            for future in as_completed(futures):
                scenario, seed = futures[future]
                row = future.result()
                ledger[_row_key(row)] = row
                _write_csv(metric_path, list(ledger.values()))
                print(
                    f"[{stage.upper()}] {scenario.scenario_id} seed={seed} "
                    f"statut={row['effect_status']}",
                    flush=True,
                )
    ordered = sorted(
        ledger.values(),
        key=lambda row: (
            _to_int(row.get("seed")), str(row.get("scenario_id") or "")
        ),
    )
    _write_csv(metric_path, ordered)
    return ordered


def _percentile(values: Sequence[float], quantile: float) -> float:
    return campaign_core.percentile(values, quantile)


SUMMARY_METRICS = (
    "product_on_due_date_proxy",
    "target_on_due_date_proxy_delta_vs_paired_baseline",
    "target_backlog_qty_days",
    "incremental_target_backlog_qty_days",
    "target_backlog_end_qty",
    "target_worst_rolling_28d_on_due_proxy",
    "target_released_qty",
    "target_released_qty_delta_vs_paired_baseline",
    "target_production_shortfall_vs_paired_baseline",
    "target_production_shortfall_ratio_vs_paired_baseline",
    "component_arrived_qty_delta_vs_paired_baseline",
    "component_input_stock_end_delta_vs_paired_baseline",
    "component_input_stock_min_delta_vs_paired_baseline",
    "component_days_at_zero_delta_vs_paired_baseline",
    "component_days_below_safety_delta_vs_paired_baseline",
    "supplier_flow_coverage_vs_paired_baseline",
    "active_window_flow_coverage_vs_paired_baseline",
    "supplier_on_due_delta_vs_paired_baseline",
    *LOT_PROOF_NUMERIC_FIELDS,
)

BOOTSTRAP_REPORT_METRICS = {
    "product_on_due_date_proxy",
    "target_on_due_date_proxy_delta_vs_paired_baseline",
    "target_backlog_qty_days",
    "incremental_target_backlog_qty_days",
    "target_production_shortfall_vs_paired_baseline",
    "target_production_shortfall_ratio_vs_paired_baseline",
    "component_days_below_safety_delta_vs_paired_baseline",
    "active_window_flow_coverage_vs_paired_baseline",
}
_BOOTSTRAP_INDEX_CACHE: dict[tuple[int, int], tuple[tuple[int, ...], ...]] = {}


def _sample_standard_deviation(values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(
        sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    )


def _paired_seed_bootstrap_mean_interval(
    values: Sequence[float], *, resamples: int = 10_000
) -> tuple[float, float]:
    """Bootstrap paired-seed delta rows as indivisible seed blocks."""

    if not values:
        return math.nan, math.nan
    if len(values) == 1:
        return float(values[0]), float(values[0])
    samples = _paired_seed_bootstrap_indices(len(values), resamples=resamples)
    means = sorted(
        sum(values[index] for index in sample) / len(values)
        for sample in samples
    )
    return _percentile(means, 0.025), _percentile(means, 0.975)


def _paired_seed_bootstrap_indices(
    seed_count: int, *, resamples: int = 10_000
) -> tuple[tuple[int, ...], ...]:
    if seed_count <= 0:
        return ()
    cache_key = (seed_count, resamples)
    samples = _BOOTSTRAP_INDEX_CACHE.get(cache_key)
    if samples is None:
        rng = random.Random(90210 + seed_count * 100_003 + resamples)
        samples = tuple(
            tuple(rng.randrange(seed_count) for _ in range(seed_count))
            for _ in range(resamples)
        )
        _BOOTSTRAP_INDEX_CACHE[cache_key] = samples
    return samples


def aggregate_scenarios(
    rows: Sequence[Mapping[str, Any]],
    scenarios: Sequence[campaign_core.Scenario],
    chain_by_id: Mapping[str, campaign_core.Chain],
) -> list[dict[str, Any]]:
    by_scenario: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_scenario[str(row.get("scenario_id") or "")].append(row)
    output: list[dict[str, Any]] = []
    for scenario in scenarios:
        relevant = by_scenario.get(scenario.scenario_id, [])
        if not relevant:
            continue
        row: dict[str, Any] = {
            "scenario_id": scenario.scenario_id,
            "chain_id": scenario.chain_id,
            "failure_mode": scenario.mechanism_key,
            "level_code": scenario.level_code,
            "level_label": scenario.level_label,
            "mechanism_value": scenario.value,
            "mechanism_unit": scenario.unit,
            "target_product_id": scenario.target_product_id,
            "n_runs": len(relevant),
            "n_seeds": len({_to_int(item.get("seed")) for item in relevant}),
            "seeds": "|".join(
                str(seed)
                for seed in sorted({_to_int(item.get("seed")) for item in relevant})
            ),
            "all_runs_valid": all(campaign_core.as_bool(item.get("valid")) for item in relevant),
            "effect_status": Counter(
                str(item.get("effect_status") or "") for item in relevant
            ).most_common(1)[0][0],
            "effect_statuses": "|".join(
                sorted({str(item.get("effect_status") or "") for item in relevant})
            ),
            "evidence_class": (
                "simulated_reference"
                if scenario.is_campaign_baseline
                else "conditional_simulation_hypothesis"
            ),
            "historical_occurrence_probability": "not_estimated",
            "confirmation_mathematical_family": next(
                (
                    family
                    for family, mechanism in CONFIRMATION_MATHEMATICAL_FAMILIES.items()
                    if scenario.mechanism_key == mechanism
                    and scenario.level_code == "severe"
                ),
                "",
            ),
        }
        if not scenario.is_campaign_baseline:
            row["stress_start_day"] = _to_int(relevant[0].get("stress_start_day"), -1)
            row["stress_end_day"] = _to_int(relevant[0].get("stress_end_day"), -1)
            row["stress_window_basis"] = str(
                relevant[0].get("stress_window_basis") or ""
            )
        row["common_comparison_start_day"] = _to_int(
            relevant[0].get("common_comparison_start_day"), -1
        )
        row["common_comparison_end_day"] = _to_int(
            relevant[0].get("common_comparison_end_day"), -1
        )
        raw_stages = sorted({str(item.get("stage") or "") for item in relevant})
        raw_stage = raw_stages[0] if len(raw_stages) == 1 else "mixed"
        row["simulation_stage"] = raw_stage
        row["evidence_stage"] = (
            f"confirmation_{row['n_seeds']}_realisations"
            if raw_stage == "confirmation"
            else (
                "screening_1_realisation"
                if raw_stage == "screening"
                else (
                    "smoke_1_realisation" if raw_stage == "smoke" else raw_stage
                )
            )
        )
        row["empirical_p05_reporting_status"] = (
            "reported_only_at_n_at_least_100"
            if row["n_seeds"] >= 100
            else "not_reported_insufficient_n"
        )
        row["bootstrap95_resample_count"] = 10_000
        row["bootstrap95_pairing_unit"] = "paired_seed_block"
        row["bootstrap95_metric_scope"] = "|".join(
            sorted(BOOTSTRAP_REPORT_METRICS)
        )
        if not scenario.is_campaign_baseline:
            chain = chain_by_id[scenario.chain_id]
            lane = chain.affected_lanes[0]
            row.update(
                {
                    "supplier_id": lane.supplier_id,
                    "item_id": lane.item_id,
                    "dst_node_id": lane.dst_node_id,
                    "target_product_uom": str(
                        relevant[0].get("target_product_uom") or ""
                    ),
                    "component_stock_uom": str(
                        relevant[0].get("component_stock_uom") or ""
                    ),
                    "service_metric_unit": "ratio_and_percentage_points",
                    "target_backlog_qty_days_unit": "UN_day",
                    "target_production_quantity_unit": "UN",
                    "target_production_shortfall_ratio_unit": "ratio",
                    "cross_uom_aggregation_allowed": False,
                }
            )
        for field in SUMMARY_METRICS:
            values = [
                _to_float(item.get(field), math.nan)
                for item in relevant
                if math.isfinite(_to_float(item.get(field), math.nan))
            ]
            if not values:
                continue
            row[f"{field}_mean"] = sum(values) / len(values)
            row[f"{field}_sample_std"] = _sample_standard_deviation(values)
            if row["n_seeds"] >= 100:
                row[f"{field}_p05"] = _percentile(values, 0.05)
            if field in BOOTSTRAP_REPORT_METRICS:
                ci_low, ci_high = _paired_seed_bootstrap_mean_interval(values)
                row[f"{field}_bootstrap95_low"] = ci_low
                row[f"{field}_bootstrap95_high"] = ci_high
            row[f"{field}_min"] = min(values)
            row[f"{field}_max"] = max(values)
        lot_statuses = sorted(
            {str(item.get("lot_proof_status") or "") for item in relevant}
        )
        integrity_statuses = sorted(
            {
                str(item.get("lot_genealogy_integrity_status") or "")
                for item in relevant
            }
        )
        lineage_statuses = sorted(
            {str(item.get("lot_lineage_horizon_status") or "") for item in relevant}
        )
        impacted_first_days = [
            _to_int(item.get("impacted_first_day"), -1)
            for item in relevant
            if str(item.get("impacted_first_day") or "").strip()
        ]
        impacted_last_days = [
            _to_int(item.get("impacted_last_day"), -1)
            for item in relevant
            if str(item.get("impacted_last_day") or "").strip()
        ]
        row.update(
            {
                "lot_proof_statuses": "|".join(lot_statuses),
                "lot_genealogy_integrity_statuses": "|".join(integrity_statuses),
                "lot_lineage_horizon_statuses": "|".join(lineage_statuses),
                "lot_proof_valid_run_fraction": sum(
                    campaign_core.as_bool(item.get("lot_proof_valid"))
                    for item in relevant
                )
                / len(relevant),
                "lot_proof_extracted_before_retention_run_fraction": sum(
                    campaign_core.as_bool(
                        item.get("lot_proof_extracted_before_retention")
                    )
                    for item in relevant
                )
                / len(relevant),
                "lot_detail_proof_retained_run_count": sum(
                    campaign_core.as_bool(item.get("lot_proof_detail_retained"))
                    for item in relevant
                ),
                "impacted_first_day_min": (
                    min(impacted_first_days) if impacted_first_days else ""
                ),
                "impacted_last_day_max": (
                    max(impacted_last_days) if impacted_last_days else ""
                ),
                "impacted_finished_product_ids": "|".join(
                    sorted(
                        {
                            token
                            for item in relevant
                            for token in str(
                                item.get("impacted_finished_product_ids") or ""
                            ).split("|")
                            if token
                        }
                    )
                ),
                "impacted_site_ids": "|".join(
                    sorted(
                        {
                            token
                            for item in relevant
                            for token in str(item.get("impacted_site_ids") or "").split(
                                "|"
                            )
                            if token
                        }
                    )
                ),
                "lot_quantification_scope": (
                    "direct receipt quantity exact; descendant/client full-lot quantities "
                    "are exposure upper bounds, not causal delay or loss"
                ),
                "source_row_semantics": (
                    "identifiant technique de ligne, pas numéro de lot industriel"
                ),
            }
        )
        signs = [
            _to_float(item.get("target_on_due_date_proxy_delta_vs_paired_baseline")) <= 1e-8
            and _to_float(item.get("incremental_target_backlog_qty_days")) >= -1e-6
            and _to_float(item.get("target_released_qty_delta_vs_paired_baseline")) <= 1e-6
            for item in relevant
            if not scenario.is_campaign_baseline
        ]
        row["expected_impact_sign_fraction"] = (
            sum(signs) / len(signs) if signs else 1.0
        )
        output.append(row)
    return output


def _severity_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        _to_float(
            row.get("target_on_due_date_proxy_delta_vs_paired_baseline_mean"), 0.0
        ),
        -_to_float(
            row.get("target_production_shortfall_ratio_vs_paired_baseline_mean")
        ),
        -_to_float(
            row.get("component_days_below_safety_delta_vs_paired_baseline_mean")
        ),
        str(row.get("scenario_id") or ""),
    )


def rank_suppliers(
    summaries: Sequence[Mapping[str, Any]],
    *,
    evidence_stage: str = "screening_1_realisation",
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in summaries:
        supplier = str(row.get("supplier_id") or "")
        if supplier:
            grouped[supplier].append(row)
    result: list[dict[str, Any]] = []
    for supplier, rows in grouped.items():
        worst = min(rows, key=_severity_key)
        result.append(
            {
                "supplier_id": supplier,
                "tested_lane_count": len({str(row.get('chain_id')) for row in rows}),
                "tested_scenario_count": len(rows),
                "tested_failure_modes": "|".join(
                    sorted({str(row.get("failure_mode")) for row in rows})
                ),
                "worst_scenario_id": worst.get("scenario_id"),
                "worst_failure_mode": worst.get("failure_mode"),
                "worst_item_id": worst.get("item_id"),
                "worst_dst_node_id": worst.get("dst_node_id"),
                "worst_target_product_id": worst.get("target_product_id"),
                "worst_target_product_uom": worst.get("target_product_uom", ""),
                "worst_component_stock_uom": worst.get("component_stock_uom", ""),
                "service_metric_unit": "ratio_and_percentage_points",
                "backlog_metric_unit": "UN_day",
                "production_shortfall_quantity_unit": "UN",
                "production_shortfall_ratio_unit": "ratio",
                "raw_stock_cross_uom_aggregation_allowed": False,
                "worst_service_delta": _to_float(
                    worst.get("target_on_due_date_proxy_delta_vs_paired_baseline_mean")
                ),
                "worst_incremental_backlog_qty_days": _to_float(
                    worst.get("incremental_target_backlog_qty_days_mean")
                ),
                "worst_production_shortfall_qty": _to_float(
                    worst.get("target_production_shortfall_vs_paired_baseline_mean")
                ),
                "worst_production_shortfall_ratio": _to_float(
                    worst.get(
                        "target_production_shortfall_ratio_vs_paired_baseline_mean"
                    )
                ),
                "worst_days_below_safety_delta": _to_float(
                    worst.get(
                        "component_days_below_safety_delta_vs_paired_baseline_mean"
                    )
                ),
                "client_effect_scenario_count": sum(
                    str(row.get("effect_status"))
                    == "effet_mesure_sur_le_service_client"
                    for row in rows
                ),
                "no_measurable_effect_scenario_count": sum(
                    str(row.get("effect_status"))
                    == "stress_applique_sans_effet_mesurable"
                    for row in rows
                ),
                "ranking_meaning": (
                    "signal_de_priorite_simule_sous_stress_conditionnel; "
                    "pas_une_probabilite_ni_une_criticite_historique"
                ),
                "evidence_stage": evidence_stage,
            }
        )
    result.sort(
        key=lambda row: (
            _to_float(row.get("worst_service_delta")),
            -_to_float(row.get("worst_production_shortfall_ratio")),
            -_to_float(row.get("worst_days_below_safety_delta")),
            str(row.get("supplier_id")),
        )
    )
    for rank, row in enumerate(result, 1):
        row["supplier_sensitivity_rank"] = rank
    return result


def rank_lanes(
    summaries: Sequence[Mapping[str, Any]],
    *,
    evidence_stage: str,
) -> list[dict[str, Any]]:
    """Rank lane incidents only with cross-UOM comparable consequences."""

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in summaries:
        chain_id = str(row.get("chain_id") or "")
        if chain_id:
            grouped[chain_id].append(row)
    output: list[dict[str, Any]] = []
    for chain_id, rows in grouped.items():
        worst = min(rows, key=_severity_key)
        output.append(
            {
                "chain_id": chain_id,
                "supplier_id": str(worst.get("supplier_id") or ""),
                "item_id": str(worst.get("item_id") or ""),
                "dst_node_id": str(worst.get("dst_node_id") or ""),
                "target_product_id": str(worst.get("target_product_id") or ""),
                "target_product_uom": str(worst.get("target_product_uom") or ""),
                "component_stock_uom": str(worst.get("component_stock_uom") or ""),
                "service_metric_unit": "ratio_and_percentage_points",
                "backlog_metric_unit": "UN_day",
                "production_shortfall_quantity_unit": "UN",
                "production_shortfall_ratio_unit": "ratio",
                "raw_stock_cross_uom_aggregation_allowed": False,
                "tested_mathematical_family_count": len(
                    {
                        str(row.get("confirmation_mathematical_family") or "")
                        for row in rows
                        if str(row.get("confirmation_mathematical_family") or "")
                    }
                ),
                "worst_scenario_id": str(worst.get("scenario_id") or ""),
                "worst_failure_mode": str(worst.get("failure_mode") or ""),
                "worst_service_delta": _to_float(
                    worst.get("target_on_due_date_proxy_delta_vs_paired_baseline_mean")
                ),
                "worst_production_shortfall_ratio": _to_float(
                    worst.get(
                        "target_production_shortfall_ratio_vs_paired_baseline_mean"
                    )
                ),
                "worst_days_below_safety_delta": _to_float(
                    worst.get(
                        "component_days_below_safety_delta_vs_paired_baseline_mean"
                    )
                ),
                "ranking_order": (
                    "service_delta_then_normalized_production_shortfall_then_"
                    "days_below_safety_then_id; no_raw_cross_uom_stock_or_backlog"
                ),
                "evidence_stage": evidence_stage,
                "historical_occurrence_probability": "not_estimated",
            }
        )
    output.sort(
        key=lambda row: (
            _to_float(row.get("worst_service_delta")),
            -_to_float(row.get("worst_production_shortfall_ratio")),
            -_to_float(row.get("worst_days_below_safety_delta")),
            str(row.get("chain_id")),
        )
    )
    for rank, row in enumerate(output, 1):
        row["lane_sensitivity_rank"] = rank
    return output


def summarize_failure_modes(
    summaries: Sequence[Mapping[str, Any]],
    *,
    evidence_stage: str = "screening_1_realisation",
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in summaries:
        mode = str(row.get("failure_mode") or "")
        if mode and mode != "baseline":
            grouped[mode].append(row)
    result: list[dict[str, Any]] = []
    for mode, rows in grouped.items():
        service_deltas = [
            _to_float(row.get("target_on_due_date_proxy_delta_vs_paired_baseline_mean"))
            for row in rows
        ]
        backlogs = [
            _to_float(row.get("incremental_target_backlog_qty_days_mean"))
            for row in rows
        ]
        production = [
            _to_float(row.get("target_production_shortfall_vs_paired_baseline_mean"))
            for row in rows
        ]
        result.append(
            {
                "failure_mode": mode,
                "failure_mode_label": MECHANISM_BY_KEY[mode].label,
                "tested_lane_count": len({str(row.get('chain_id')) for row in rows}),
                "tested_scenario_count": len(rows),
                "worst_service_delta": min(service_deltas, default=0.0),
                "median_service_delta": _percentile(service_deltas, 0.5),
                "worst_incremental_backlog_qty_days": max(backlogs, default=0.0),
                "worst_production_shortfall_qty": max(production, default=0.0),
                "client_effect_scenario_count": sum(
                    str(row.get("effect_status"))
                    == "effet_mesure_sur_le_service_client"
                    for row in rows
                ),
                "no_measurable_effect_scenario_count": sum(
                    str(row.get("effect_status"))
                    == "stress_applique_sans_effet_mesurable"
                    for row in rows
                ),
                "interpretation": (
                    "sensibilite_conditionnelle_du_mode; aucune_frequence_historique_estimee"
                ),
                "evidence_stage": evidence_stage,
            }
        )
    result.sort(
        key=lambda row: (
            _to_float(row.get("worst_service_delta")),
            -_to_float(row.get("worst_incremental_backlog_qty_days")),
            str(row.get("failure_mode")),
        )
    )
    for rank, row in enumerate(result, 1):
        row["failure_mode_sensitivity_rank"] = rank
    return result


def _raw_row_as_summary(
    row: Mapping[str, Any],
    *,
    scenario_by_id: Mapping[str, campaign_core.Scenario],
    chain_by_id: Mapping[str, campaign_core.Chain],
) -> dict[str, Any]:
    scenario = scenario_by_id[str(row.get("scenario_id") or "")]
    chain = chain_by_id[scenario.chain_id]
    lane = chain.affected_lanes[0]
    return {
        "scenario_id": scenario.scenario_id,
        "chain_id": chain.chain_id,
        "supplier_id": lane.supplier_id,
        "item_id": lane.item_id,
        "dst_node_id": lane.dst_node_id,
        "target_product_id": chain.target_product_id,
        "failure_mode": scenario.mechanism_key,
        "confirmation_mathematical_family": next(
            (
                family
                for family, mechanism in CONFIRMATION_MATHEMATICAL_FAMILIES.items()
                if scenario.mechanism_key == mechanism
            ),
            "",
        ),
        "target_on_due_date_proxy_delta_vs_paired_baseline_mean": _to_float(
            row.get("target_on_due_date_proxy_delta_vs_paired_baseline")
        ),
        "incremental_target_backlog_qty_days_mean": _to_float(
            row.get("incremental_target_backlog_qty_days")
        ),
        "target_production_shortfall_vs_paired_baseline_mean": _to_float(
            row.get("target_production_shortfall_vs_paired_baseline")
        ),
        "target_production_shortfall_ratio_vs_paired_baseline_mean": _to_float(
            row.get("target_production_shortfall_ratio_vs_paired_baseline")
        ),
        "component_days_below_safety_delta_vs_paired_baseline_mean": _to_float(
            row.get("component_days_below_safety_delta_vs_paired_baseline")
        ),
        "effect_status": str(row.get("effect_status") or ""),
    }


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if trials <= 0:
        return 0.0, 1.0
    successes = max(0, min(int(successes), int(trials)))
    n = float(trials)
    proportion = successes / n
    denominator = 1.0 + z * z / n
    centre = (proportion + z * z / (2.0 * n)) / denominator
    half = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / n + z * z / (4.0 * n * n)
        )
        / denominator
    )
    return max(0.0, centre - half), min(1.0, centre + half)


def paired_seed_block_bootstrap_supplier_rank_intervals(
    confirmation_rows: Sequence[Mapping[str, Any]],
    *,
    scenario_by_id: Mapping[str, campaign_core.Scenario],
    chain_by_id: Mapping[str, campaign_core.Chain],
    aggregate_ranking: Sequence[Mapping[str, Any]],
    resamples: int = 10_000,
) -> tuple[list[dict[str, Any]], bool]:
    """Bootstrap supplier ranks while preserving each paired seed as a block."""

    stressed = [
        row
        for row in confirmation_rows
        if str(row.get("scenario_id") or "") != "baseline_nominal"
    ]
    seeds = sorted({_to_int(row.get("seed"), -1) for row in stressed})
    seeds = [seed for seed in seeds if seed >= 0]
    scenario_ids = sorted({str(row.get("scenario_id") or "") for row in stressed})
    converted: dict[tuple[int, str], dict[str, Any]] = {}
    for row in stressed:
        key = (_to_int(row.get("seed"), -1), str(row.get("scenario_id") or ""))
        converted[key] = _raw_row_as_summary(
            row,
            scenario_by_id=scenario_by_id,
            chain_by_id=chain_by_id,
        )
    missing = [
        (seed, scenario_id)
        for seed in seeds
        for scenario_id in scenario_ids
        if (seed, scenario_id) not in converted
    ]
    if missing:
        raise ValueError(
            "Bootstrap apparie impossible: scenarios manquants pour certaines graines: "
            + ", ".join(f"{seed}/{scenario}" for seed, scenario in missing[:5])
        )
    metric_fields = (
        "target_on_due_date_proxy_delta_vs_paired_baseline_mean",
        "incremental_target_backlog_qty_days_mean",
        "target_production_shortfall_vs_paired_baseline_mean",
        "target_production_shortfall_ratio_vs_paired_baseline_mean",
        "component_days_below_safety_delta_vs_paired_baseline_mean",
    )
    ranks: dict[str, list[int]] = defaultdict(list)
    seed_samples = _paired_seed_bootstrap_indices(len(seeds), resamples=resamples)
    for sample in seed_samples:
        sampled_summaries: list[dict[str, Any]] = []
        for scenario_id in scenario_ids:
            rows = [converted[(seeds[index], scenario_id)] for index in sample]
            summary = dict(rows[0])
            for field in metric_fields:
                summary[field] = sum(_to_float(row.get(field)) for row in rows) / len(rows)
            sampled_summaries.append(summary)
        ranking = rank_suppliers(
            sampled_summaries,
            evidence_stage=f"paired_seed_block_bootstrap_{resamples}",
        )
        for row in ranking:
            ranks[str(row.get("supplier_id") or "")].append(
                _to_int(row.get("supplier_sensitivity_rank"), 10**9)
            )
    aggregate_rank = {
        str(row.get("supplier_id") or ""): _to_int(
            row.get("supplier_sensitivity_rank"), 10**9
        )
        for row in aggregate_ranking
    }
    output: list[dict[str, Any]] = []
    for supplier_id, rank in sorted(
        aggregate_rank.items(), key=lambda item: (item[1], item[0])
    ):
        values = ranks.get(supplier_id, [])
        output.append(
            {
                "supplier_id": supplier_id,
                "aggregate_confirmation_rank": rank,
                "bootstrap_resample_count": resamples,
                "bootstrap_pairing_unit": "paired_seed_block",
                "bootstrap_rank_ci95_low": (
                    _percentile(values, 0.025) if values else ""
                ),
                "bootstrap_rank_ci95_high": (
                    _percentile(values, 0.975) if values else ""
                ),
                "bootstrap_rank_min": min(values) if values else "",
                "bootstrap_rank_max": max(values) if values else "",
            }
        )
    rank3 = next(
        (row for row in output if row["aggregate_confirmation_rank"] == 3), None
    )
    rank4 = next(
        (row for row in output if row["aggregate_confirmation_rank"] == 4), None
    )
    separated = bool(
        rank3
        and rank4
        and _to_float(rank3.get("bootstrap_rank_ci95_high"), math.inf)
        < _to_float(rank4.get("bootstrap_rank_ci95_low"), -math.inf)
    )
    for row in output:
        row["rank3_rank4_interval_separated"] = separated
    return output, separated


def confirmed_top3_stability(
    confirmation_rows: Sequence[Mapping[str, Any]],
    *,
    scenario_by_id: Mapping[str, campaign_core.Scenario],
    chain_by_id: Mapping[str, campaign_core.Chain],
    aggregate_ranking: Sequence[Mapping[str, Any]],
    minimum_presence_fraction: float = 0.80,
) -> list[dict[str, Any]]:
    """Audit top-three supplier membership independently for every seed."""

    stressed = [
        row
        for row in confirmation_rows
        if str(row.get("scenario_id") or "") != "baseline_nominal"
    ]
    by_seed: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in stressed:
        by_seed[_to_int(row.get("seed"), -1)].append(row)
    presence: Counter[str] = Counter()
    for seed, rows in sorted(by_seed.items()):
        if seed < 0:
            continue
        seed_summaries = [
            _raw_row_as_summary(
                row, scenario_by_id=scenario_by_id, chain_by_id=chain_by_id
            )
            for row in rows
        ]
        seed_ranking = rank_suppliers(
            seed_summaries, evidence_stage=f"confirmation_seed_{seed}"
        )
        presence.update(
            str(row.get("supplier_id")) for row in seed_ranking[:3]
        )
    seed_count = len(by_seed)
    final_presence_required = (
        int(math.ceil(seed_count * 29.0 / 30.0 - 1e-12))
        if seed_count >= 30
        else 0
    )
    aggregate_rank_by_supplier = {
        str(row.get("supplier_id")): _to_int(row.get("supplier_sensitivity_rank"))
        for row in aggregate_ranking
    }
    output: list[dict[str, Any]] = []
    for supplier, aggregate_rank in sorted(
        aggregate_rank_by_supplier.items(), key=lambda item: (item[1], item[0])
    ):
        count = int(presence.get(supplier, 0))
        fraction = count / seed_count if seed_count else 0.0
        wilson_lower, wilson_upper = wilson_interval(count, seed_count)
        aggregate_top3 = aggregate_rank <= 3
        preselection_presence_pass = (
            aggregate_top3 and fraction + 1e-12 >= minimum_presence_fraction
        )
        output.append(
            {
                "supplier_id": supplier,
                "aggregate_confirmation_rank": aggregate_rank,
                "confirmation_seed_count": seed_count,
                "top3_presence_seed_count": count,
                "top3_presence_fraction": fraction,
                "minimum_required_fraction": minimum_presence_fraction,
                "top3_presence_wilson95_lower": wilson_lower,
                "top3_presence_wilson95_upper": wilson_upper,
                "aggregate_top3": aggregate_top3,
                "individual_top3_stability_pass": preselection_presence_pass,
                "preselection_presence_pass": preselection_presence_pass,
                "stabilized_presence_required_seed_count": final_presence_required,
                "stabilized_presence_pass": bool(
                    aggregate_top3
                    and final_presence_required
                    and count >= final_presence_required
                ),
                "evidence_stage": f"confirmation_{seed_count}_realisations",
            }
        )
    aggregate_top3_rows = [row for row in output if row["aggregate_top3"]]
    preselection_set_pass = (
        len(aggregate_top3_rows) == 3
        and all(row["preselection_presence_pass"] for row in aggregate_top3_rows)
    )
    bootstrap_rows: list[dict[str, Any]] = []
    rank3_rank4_separated = False
    if seed_count >= 30:
        bootstrap_rows, rank3_rank4_separated = (
            paired_seed_block_bootstrap_supplier_rank_intervals(
                confirmation_rows,
                scenario_by_id=scenario_by_id,
                chain_by_id=chain_by_id,
                aggregate_ranking=aggregate_ranking,
                resamples=10_000,
            )
        )
    bootstrap_by_supplier = {
        str(row.get("supplier_id") or ""): row for row in bootstrap_rows
    }
    stabilized_set_pass = bool(
        seed_count >= 30
        and len(aggregate_top3_rows) == 3
        and all(row["stabilized_presence_pass"] for row in aggregate_top3_rows)
        and rank3_rank4_separated
    )
    for row in output:
        aggregate_top3 = bool(row["aggregate_top3"])
        row.update(bootstrap_by_supplier.get(str(row.get("supplier_id") or ""), {}))
        row["preselection_set_presence_pass"] = preselection_set_pass
        row["rank3_rank4_interval_separated"] = rank3_rank4_separated
        row["priority_set_stabilized"] = stabilized_set_pass
        # Legacy fields are retained for consumers, but the publication uses
        # "simulated stabilized priorities", never industrial criticality.
        row["top3_set_validated"] = stabilized_set_pass
        row["stable_confirmed_top3"] = stabilized_set_pass and aggregate_top3
        row["final_top3_rank"] = ""
        row["stabilized_priority_rank"] = (
            row["aggregate_confirmation_rank"]
            if stabilized_set_pass and aggregate_top3
            else ""
        )
        row["provisional_priority_rank"] = (
            row["aggregate_confirmation_rank"] if aggregate_top3 else ""
        )
        row["top3_status"] = (
            "priorite_simulee_stabilisee"
            if stabilized_set_pass and aggregate_top3
            else (
                "preselection_a_approfondir_30_graines"
                if seed_count < 30 and aggregate_top3
                else (
                    "groupe_top5_ex_aequo_priorite_non_tranchee"
                    if seed_count >= 30
                    and _to_int(row.get("aggregate_confirmation_rank"), 99) <= 5
                    and not stabilized_set_pass
                    else "fournisseur_confirme_hors_groupe_prioritaire"
                )
            )
        )
    return output


def scientific_release_gate_audit(
    confirmation_rows: Sequence[Mapping[str, Any]],
    *,
    selected_scenario_ids: Sequence[str],
    scenario_by_id: Mapping[str, campaign_core.Scenario],
    minimum_flow_seed_count: int = 29,
) -> dict[str, Any]:
    """Audit non-statistical gates required before publishing priorities."""

    baseline_by_seed = {
        _to_int(row.get("seed"), -1): row
        for row in confirmation_rows
        if str(row.get("scenario_id") or "") == "baseline_nominal"
    }
    stressed = [
        row
        for row in confirmation_rows
        if str(row.get("scenario_id") or "") != "baseline_nominal"
    ]
    baseline_service_pass_by_seed = {
        seed: all(
            _to_float(row.get(f"on_due_volume_proxy_{product}"), math.nan)
            >= 0.95 - 1e-12
            for product in TARGET_PRODUCTS
        )
        for seed, row in baseline_by_seed.items()
    }
    valid_pass = bool(confirmation_rows) and all(
        campaign_core.as_bool(row.get("valid")) for row in confirmation_rows
    )
    j0_pairing_pass = bool(stressed) and all(
        str(row.get("j0_state_sha256") or "")
        and str(row.get("j0_state_sha256") or "")
        == str(baseline_by_seed.get(_to_int(row.get("seed"), -1), {}).get(
            "j0_state_sha256"
        ) or "")
        for row in stressed
    )
    input_hash_pairing_pass = bool(stressed) and all(
        str(row.get("input_sha256") or "")
        and str(row.get("input_sha256") or "")
        == str(baseline_by_seed.get(_to_int(row.get("seed"), -1), {}).get(
            "input_sha256"
        ) or "")
        for row in stressed
    )
    selected_chain_ids = sorted(
        {scenario_by_id[scenario_id].chain_id for scenario_id in selected_scenario_ids}
    )
    positive_flow_seeds_by_chain: dict[str, set[int]] = defaultdict(set)
    for row in stressed:
        scenario_id = str(row.get("scenario_id") or "")
        scenario = scenario_by_id.get(scenario_id)
        if scenario is None or scenario.chain_id not in selected_chain_ids:
            continue
        if (
            _to_float(row.get("paired_baseline_active_window_pulled_qty")) > 1e-12
            and _to_float(row.get("paired_baseline_active_window_shipped_qty")) > 1e-12
        ):
            positive_flow_seeds_by_chain[scenario.chain_id].add(
                _to_int(row.get("seed"), -1)
            )
    lane_flow_rows = [
        {
            "chain_id": chain_id,
            "positive_pulled_and_shipped_seed_count": len(
                positive_flow_seeds_by_chain.get(chain_id, set()) - {-1}
            ),
            "required_seed_count": minimum_flow_seed_count,
            "gate_pass": len(positive_flow_seeds_by_chain.get(chain_id, set()) - {-1})
            >= minimum_flow_seed_count,
        }
        for chain_id in selected_chain_ids
    ]
    baseline_service_gate = (
        len(baseline_by_seed) == 30
        and all(baseline_service_pass_by_seed.values())
    )
    flow_gate = len(lane_flow_rows) == 18 and all(
        row["gate_pass"] for row in lane_flow_rows
    )
    all_gates = bool(
        baseline_service_gate
        and valid_pass
        and j0_pairing_pass
        and input_hash_pairing_pass
        and flow_gate
    )
    return {
        "baseline_seed_count": len(baseline_by_seed),
        "baseline_both_products_on_due_at_least_95_all_seeds_pass": (
            baseline_service_gate
        ),
        "baseline_service_pass_by_seed": baseline_service_pass_by_seed,
        "all_metric_rows_valid_pass": valid_pass,
        "j0_state_hash_pairing_100pct_pass": j0_pairing_pass,
        "input_graph_hash_pairing_100pct_pass": input_hash_pairing_pass,
        "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass": (
            flow_gate
        ),
        "active_window_flow_gate_by_lane": lane_flow_rows,
        "all_release_gates_pass": all_gates,
    }


def confirmed_lane_preselection_stability(
    confirmation_rows: Sequence[Mapping[str, Any]],
    *,
    scenario_by_id: Mapping[str, campaign_core.Scenario],
    chain_by_id: Mapping[str, campaign_core.Chain],
    aggregate_ranking: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    stressed = [
        row
        for row in confirmation_rows
        if str(row.get("scenario_id") or "") != "baseline_nominal"
    ]
    by_seed: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in stressed:
        by_seed[_to_int(row.get("seed"), -1)].append(row)
    top3_presence: Counter[str] = Counter()
    for seed, rows in sorted(by_seed.items()):
        if seed < 0:
            continue
        seed_summaries = [
            _raw_row_as_summary(
                row, scenario_by_id=scenario_by_id, chain_by_id=chain_by_id
            )
            for row in rows
        ]
        top3_presence.update(
            str(row.get("chain_id"))
            for row in rank_lanes(
                seed_summaries, evidence_stage=f"confirmation_seed_{seed}"
            )[:3]
        )
    seed_count = len(by_seed)
    stabilized_required = (
        int(math.ceil(seed_count * 29.0 / 30.0 - 1e-12))
        if seed_count >= 30
        else 0
    )
    output: list[dict[str, Any]] = []
    for aggregate in aggregate_ranking:
        chain_id = str(aggregate.get("chain_id") or "")
        count = int(top3_presence.get(chain_id, 0))
        lower, upper = wilson_interval(count, seed_count)
        rank = _to_int(aggregate.get("lane_sensitivity_rank"), 0)
        output.append(
            {
                "chain_id": chain_id,
                "supplier_id": str(aggregate.get("supplier_id") or ""),
                "item_id": str(aggregate.get("item_id") or ""),
                "dst_node_id": str(aggregate.get("dst_node_id") or ""),
                "aggregate_confirmation_rank": rank,
                "confirmation_seed_count": seed_count,
                "top3_presence_seed_count": count,
                "top3_presence_fraction": count / seed_count if seed_count else 0.0,
                "top3_presence_wilson95_lower": lower,
                "top3_presence_wilson95_upper": upper,
                "aggregate_top3": rank <= 3,
                "preselection_membership_pass": (
                    seed_count > 0
                    and count / seed_count + 1e-12 >= 0.80
                ),
                "stabilized_presence_required_seed_count": (
                    stabilized_required
                ),
                "stabilized_presence_pass": (
                    seed_count >= 30
                    and rank <= 3
                    and count
                    >= stabilized_required
                ),
                "priority_status": (
                    "lane_presence_stable_but_supplier_rank_separation_required"
                    if seed_count >= 30 and rank <= 3 and count >= stabilized_required
                    else (
                        "preselection_a_approfondir_30_graines"
                        if seed_count < 30
                        else "groupe_top5_ou_hors_priorite_non_tranche"
                    )
                ),
                "final_priority_claimed": False,
                "evidence_stage": (
                    f"two_predeclared_families_x_{seed_count}_realisations"
                ),
            }
        )
    return output


def post_priority_extension_designs(
    *,
    lane_ranking: Sequence[Mapping[str, Any]],
    scenarios: Sequence[campaign_core.Scenario],
    chain_by_id: Mapping[str, campaign_core.Chain],
    confirmation_seeds: Sequence[int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    priorities = sorted(
        lane_ranking,
        key=lambda row: _to_int(row.get("lane_sensitivity_rank"), 10**9),
    )[:3]
    scenario_by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    severe_by_chain_mode = {
        (scenario.chain_id, scenario.mechanism_key): scenario
        for scenario in scenarios
        if scenario.level_code == "severe"
    }
    temporal_rows: list[dict[str, Any]] = []
    mode_rows: list[dict[str, Any]] = []
    temporal_seeds = tuple(sorted(confirmation_seeds))[:3]
    four_windows = ((0, 179), (180, 359), (360, 539), (540, 719))
    for priority_rank, priority in enumerate(priorities, 1):
        chain_id = str(priority.get("chain_id") or "")
        chain = chain_by_id[chain_id]
        lane = chain.affected_lanes[0]
        retained = scenario_by_id[str(priority.get("worst_scenario_id") or "")]
        for window_index, (start_day, end_day) in enumerate(four_windows, 1):
            for seed in temporal_seeds:
                temporal_rows.append(
                    {
                        "priority_label": (
                            "3_voies_prioritaires_simulees_ou_provisoires_selon_gate"
                        ),
                        "priority_rank_after_main_confirmation": priority_rank,
                        "chain_id": chain_id,
                        "supplier_id": lane.supplier_id,
                        "item_id": lane.item_id,
                        "dst_node_id": lane.dst_node_id,
                        "target_product_id": chain.target_product_id,
                        "retained_severe_scenario_id": retained.scenario_id,
                        "failure_mode": retained.mechanism_key,
                        "window_index": window_index,
                        "stress_start_day": start_day,
                        "stress_end_day": end_day,
                        "seed": seed,
                        "execution_status": "planned_not_executed",
                        "interpretation_rule": (
                            "effet_dependant_de_la_periode_if_impact_or_rank_changes_across_windows"
                        ),
                        "historical_occurrence_probability": "not_estimated",
                    }
                )
        for mechanism in MECHANISMS:
            severe = severe_by_chain_mode[(chain_id, mechanism.key)]
            for seed in sorted(confirmation_seeds):
                mode_rows.append(
                    {
                        "priority_label": (
                            "3_voies_prioritaires_simulees_ou_provisoires_selon_gate"
                        ),
                        "priority_rank_after_main_confirmation": priority_rank,
                        "chain_id": chain_id,
                        "supplier_id": lane.supplier_id,
                        "item_id": lane.item_id,
                        "dst_node_id": lane.dst_node_id,
                        "target_product_id": chain.target_product_id,
                        "failure_mode": mechanism.key,
                        "severe_scenario_id": severe.scenario_id,
                        "seed": seed,
                        "execution_status": "planned_not_executed",
                        "comparison_scope": (
                            "four_business_causes_balanced_on_same_three_lanes; not_recurrence"
                        ),
                        "historical_occurrence_probability": "not_estimated",
                    }
                )
    manifest = {
        "status": "planned_not_executed",
        "priority_label": (
            "3_voies_prioritaires_simulees_ou_provisoires_selon_gate"
        ),
        "final_top3_claimed": False,
        "temporal_robustness": {
            "stress_run_count": len(temporal_rows),
            "lane_count": len(priorities),
            "calendar_windows": [list(window) for window in four_windows],
            "paired_seed_count": len(temporal_seeds),
            "baseline_reuse": "existing confirmation baselines for the same seeds",
        },
        "severe_mode_confirmation": {
            "stress_run_count": len(mode_rows),
            "lane_count": len(priorities),
            "failure_mode_count": len(MECHANISMS),
            "paired_seed_count": len(set(confirmation_seeds)),
            "baseline_reuse": "existing confirmation baselines",
            "not_a_frequency_or_recurrence": True,
        },
    }
    return temporal_rows, mode_rows, manifest


def lane_evidence_status_rows(
    lanes: Sequence[LaneReference],
    *,
    selected_scenario_ids: Sequence[str],
    scenario_by_id: Mapping[str, campaign_core.Scenario],
    confirmation_seed_count: int,
) -> list[dict[str, Any]]:
    selected_by_chain: dict[str, list[str]] = defaultdict(list)
    for scenario_id in selected_scenario_ids:
        selected_by_chain[scenario_by_id[scenario_id].chain_id].append(scenario_id)
    rows: list[dict[str, Any]] = []
    for reference in lanes:
        chain = reference.chain
        lane = chain.affected_lanes[0]
        selected = bool(selected_by_chain.get(chain.chain_id))
        rows.append(
            {
                "chain_id": chain.chain_id,
                "supplier_id": lane.supplier_id,
                "item_id": lane.item_id,
                "dst_node_id": lane.dst_node_id,
                "target_product_id": chain.target_product_id,
                "selected_for_confirmation": selected,
                "confirmed_scenario_id": "|".join(
                    sorted(selected_by_chain.get(chain.chain_id, []))
                ),
                "confirmed_mathematical_family_count": len(
                    selected_by_chain.get(chain.chain_id, [])
                ),
                "evidence_stage": (
                    f"confirmation_{confirmation_seed_count}_realisations"
                    if selected
                    else "screening_1_realisation"
                ),
                "eligible_for_final_top3": selected,
                "interpretation": (
                    "voie_confirmee_multi_realisations"
                    if selected
                    else "voie_non_retenue_reste_un_resultat_de_screening_a_une_realisation"
                ),
            }
        )
    return rows


def select_confirmation_scenarios(
    screening_summaries: Sequence[Mapping[str, Any]], *, top_lanes: int
) -> tuple[str, ...]:
    """Select one worst scenario per lane, then retain the worst distinct lanes."""

    by_lane: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in screening_summaries:
        chain_id = str(row.get("chain_id") or "")
        if chain_id:
            by_lane[chain_id].append(row)
    worst_by_lane = [min(rows, key=_severity_key) for rows in by_lane.values()]
    worst_by_lane.sort(key=_severity_key)
    return tuple(
        str(row.get("scenario_id")) for row in worst_by_lane[: max(1, top_lanes)]
    )


def select_predeclared_family_confirmation_scenarios(
    scenarios: Sequence[campaign_core.Scenario],
    lanes: Sequence[LaneReference],
) -> tuple[str, ...]:
    """Select two severe mathematical families on every lane without seed bias."""

    expected = {
        (reference.chain.chain_id, mechanism)
        for reference in lanes
        for mechanism in CONFIRMATION_MATHEMATICAL_FAMILIES.values()
    }
    selected = [
        scenario
        for scenario in scenarios
        if not scenario.is_campaign_baseline
        and scenario.level_code == "severe"
        and (scenario.chain_id, scenario.mechanism_key) in expected
    ]
    keys = {(scenario.chain_id, scenario.mechanism_key) for scenario in selected}
    if keys != expected or len(selected) != len(expected):
        raise ValueError(
            "La confirmation doit contenir exactement deux familles severes "
            "predeclarees pour chacune des 18 voies."
        )
    return tuple(
        scenario.scenario_id
        for scenario in sorted(
            selected,
            key=lambda item: (
                item.chain_id,
                tuple(CONFIRMATION_MATHEMATICAL_FAMILIES.values()).index(
                    item.mechanism_key
                ),
            ),
        )
    )


def select_smoke_scenarios(
    lanes: Sequence[LaneReference],
    scenarios: Sequence[campaign_core.Scenario],
    *,
    lane_count: int,
    component_labels: Sequence[str] = (),
    include_all_levels: bool = False,
) -> list[campaign_core.Scenario]:
    baseline = next(item for item in scenarios if item.is_campaign_baseline)
    requested_components = tuple(
        dict.fromkeys(str(value).strip() for value in component_labels if str(value).strip())
    )
    if requested_components:
        by_component = {item.chain.component_label: item for item in lanes}
        missing = [value for value in requested_components if value not in by_component]
        if missing:
            raise ValueError(
                "Unknown active-lane smoke component(s): " + ", ".join(missing)
            )
        chosen = [by_component[value] for value in requested_components]
        lane_count = len(chosen)
    else:
        chosen = []
    ordered = sorted(
        lanes,
        key=lambda item: (-item.baseline_shipped_qty, item.chain.chain_id),
    )
    # Keep the already established 338929 cascade in the smoke and complement
    # it with the largest-flow lane.  This tests both continuity with V4 and
    # the new network-wide discovery logic.
    anchor = next(
        (item for item in lanes if item.chain.component_label == "338929"), None
    )
    if not requested_components:
        chosen = [anchor] if anchor is not None else []
        for reference in ordered:
            if reference not in chosen:
                chosen.append(reference)
            if len(chosen) >= max(1, lane_count):
                break
    chain_ids = {item.chain.chain_id for item in chosen[: max(1, lane_count)]}
    selected = [baseline]
    selected.extend(
        scenario
        for scenario in scenarios
        if scenario.chain_id in chain_ids
        and (include_all_levels or scenario.level_code == "severe")
        and scenario.mechanism_key in {"transport_delay", "supply_availability"}
    )
    return selected


def summarize_lot_proof_campaign(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    stressed = [
        row
        for row in rows
        if str(row.get("scenario_id") or "") != "baseline_nominal"
    ]
    return {
        "stressed_run_count": len(stressed),
        "proof_valid_run_count": sum(
            campaign_core.as_bool(row.get("lot_proof_valid")) for row in stressed
        ),
        "proof_extracted_before_retention_run_count": sum(
            campaign_core.as_bool(row.get("lot_proof_extracted_before_retention"))
            for row in stressed
        ),
        "run_with_impacted_receipt_count": sum(
            _to_int(row.get("impacted_receipt_lot_count"), 0) > 0 for row in stressed
        ),
        "run_with_finished_descendant_count": sum(
            _to_int(row.get("impacted_finished_descendant_lot_count"), 0) > 0
            for row in stressed
        ),
        "run_with_client_delivery_descendant_count": sum(
            _to_int(row.get("impacted_client_delivery_descendant_lot_count"), 0)
            > 0
            for row in stressed
        ),
        "run_without_impacted_receipt_within_horizon_count": sum(
            str(row.get("lot_lineage_horizon_status") or "")
            == "no_impacted_usable_receipt_within_simulated_horizon"
            for row in stressed
        ),
        "invalid_missing_expected_usable_receipt_root_run_count": sum(
            str(row.get("lot_proof_status") or "")
            == "invalid_missing_tagged_usable_receipt_root"
            for row in stressed
        ),
        "invalid_lot_trace_disabled_run_count": sum(
            str(row.get("lot_proof_status") or "")
            == "invalid_lot_trace_not_enabled"
            for row in stressed
        ),
        "genealogy_missing_event_reference_run_count": sum(
            _to_int(row.get("lot_genealogy_missing_event_lot_count"), 0) > 0
            for row in stressed
        ),
        "detailed_confirmation_proof_run_count": sum(
            campaign_core.as_bool(row.get("lot_proof_detail_retained"))
            for row in stressed
        ),
        "root_identification": "direct risk_event_ids on usable lane-receipt lots",
        "descendant_identification": (
            "parent_to_child_genealogy_traversal_not_child_risk_tags"
        ),
        "quantity_scope": (
            "receipt exact; descendant/client full-lot quantities are exposure upper bounds"
        ),
        "source_row_semantics": (
            "identifiant technique de ligne, pas numero de lot industriel"
        ),
        "quality_hold_native_state_limitation": (
            "quality wait is reconstructed from tested delay and usable receipt day; "
            "it is not a native quarantine-stock state"
        ),
    }


def _report_text(
    *,
    mode: str,
    lane_count: int,
    supplier_count: int,
    scenario_count: int,
    executed_runs: int,
    status_counts: Mapping[str, int],
    lot_proof_summary: Mapping[str, Any],
    output_dir: Path,
) -> str:
    lot_section = f"""
## Preuve lots reconstruite par genealogie

Les lots de reception directement marques par l'incident sont les racines. Les
descendants intermediaires, finis et servis au client sont reconstruits en
parcourant la genealogie parent -> enfant. Les tags directs des lots finis ne
sont jamais utilises comme preuve suffisante.

- runs stresses avec extraction : {lot_proof_summary.get('stressed_run_count', 0)} ;
- runs avec une reception touchee : {lot_proof_summary.get('run_with_impacted_receipt_count', 0)} ;
- runs atteignant un lot fini / une livraison client : {lot_proof_summary.get('run_with_finished_descendant_count', 0)} / {lot_proof_summary.get('run_with_client_delivery_descendant_count', 0)} ;
- references de lots manquantes dans l'export : {lot_proof_summary.get('genealogy_missing_event_reference_run_count', 0)} ;
- preuves detaillees de confirmation conservees : {lot_proof_summary.get('detailed_confirmation_proof_run_count', 0)}.

La quantite de reception est exacte dans le modele. La quantite complete d'un
descendant touche est une **borne haute d'exposition genealogique**, pas une
quantite causee, perdue ou retardee par l'incident. `source_row` est un
identifiant technique de ligne, jamais un numero de lot industriel.

## Limite de calendrier et extensions separees

La fenetre active propre a chaque voie melange volontairement vulnerabilite et
periode de charge forte afin d'exercer le flux. Une robustesse temporelle sur
J0-179, J180-359, J360-539 et J540-719 est donc preparee apres selection des
trois priorites. Une seconde extension repetera separement les quatre modes
severes sur ces trois voies. Aucune de ces extensions ne mesure une recurrence
ou une probabilite historique.
"""
    statuses = "\n".join(
        f"- `{status}` : {count}" for status, count in sorted(status_counts.items())
    ) or "- Aucun résultat exécuté (mode plan)."
    return f"""# Screening réseau des risques fournisseurs

## Ce qui est couvert

- {lane_count} voies actives dans la **référence simulée V10** ;
- {supplier_count} fournisseurs distincts ;
- quatre modes de défaillance testés séparément, à deux intensités ;
- commandes initiales de janvier désactivées, comme dans V10 ;
- durée de stress identique de 180 jours ; la fenêtre principale est placée, pour chaque voie, sur sa période de flux V10 la plus forte ;
- fenêtre calendaire commune J45–J224 conservée dans l'audit pour montrer les voies non sollicitées à ces dates.

Une voie « active » signifie qu'elle transporte un flux dans la simulation V10. Ce n'est pas une preuve de performance industrielle observée.

## Lecture scientifique

Chaque incident est une **hypothèse conditionnelle**. Le classement principal repose sur une fenêtre active propre à chaque voie : c'est un test de vulnérabilité, pas une comparaison de fréquence sur un même calendrier. Il indique les fournisseurs auxquels le modèle est le plus sensible sous les stress testés. Il ne donne ni probabilité historique d'incident, ni taux de défaut observé, ni criticité finale fournisseur.

Les fournisseurs et les modes de défaillance sont classés dans deux fichiers séparés. Le service client, le backlog, la production et les stocks restent également visibles séparément : aucun score composite opaque ne remplace ces mesures.

La comparaison globale des quatre modes reste le screening équilibré à une réalisation (18 voies × 4 modes × 2 intensités). La confirmation multi-réalisations porte sur un scénario pénalisant par voie : son résumé séparé ne doit pas être lu comme un classement global des modes, ni comme une fréquence de récurrence.

Les quatre modes représentent des causes métier différentes, mais leurs effets numériques ne sont pas toujours indépendants : disponibilité et rendement qualité peuvent retirer la même quantité utile; retard transport et attente qualité peuvent donner la même date d'utilisabilité. Deux réponses identiques ne constituent donc pas deux preuves indépendantes.

## Exécution

- mode : `{mode}` ;
- scénarios définis : {scenario_count} ;
- runs exécutés ou réextraits : {executed_runs} ;
- dossier : `{output_dir}`.

Statuts d'effet :

{statuses}

{lot_section}

## Volumes prévus

- smoke : 5 runs appariés ;
- screening complet : 145 runs (1 baseline + 18 × 4 × 2) ;
- confirmation : 1 110 runs (30 references + 18 voies x 2 familles x 30 graines) ;
- campagne complete : 1 255 runs.
"""


def _report_text_v4(
    *,
    mode: str,
    lane_count: int,
    supplier_count: int,
    scenario_count: int,
    executed_runs: int,
    status_counts: Mapping[str, int],
    lot_proof_summary: Mapping[str, Any],
    output_dir: Path,
    run_budget: Mapping[str, int],
) -> str:
    statuses = "\n".join(
        f"- `{status}` : {count}" for status, count in sorted(status_counts.items())
    ) or "- Aucun resultat execute (mode plan)."
    return f"""# Screening reseau des risques fournisseurs - protocole v4

## Perimetre et question posee

- {lane_count} voies actives de la reference simulee V10, soit {supplier_count} fournisseurs;
- quatre causes metier x deux niveaux au screening;
- deux familles mathematiques severes predeclarees sur toutes les voies et 30 graines appariees en confirmation;
- stress de 180 jours place sur la fenetre de flux la plus forte de chaque voie.

Le resultat mesure une vulnerabilite conditionnelle du modele. Il ne mesure ni
probabilite d'incident, ni recurrence, ni criticite fournisseur observee. La
fenetre propre a chaque voie melange vulnerabilite et periode de charge; la
robustesse sur quatre fenetres calendrier reste une extension separee.

## Regle de publication

Une priorite simulee n'est dite stabilisee que si elle appartient aux trois
premieres dans au moins 29 graines sur 30 et si un bootstrap de 10 000 blocs de
graines appariees separe les intervalles de rang des positions 3 et 4. Sinon,
le rapport publie un groupe de cinq voies/fournisseurs non tranche. Aucun
"top 3 critique industriel" n'est revendique. Le p05 empirique n'est pas
publie sous 100 realisations; moyenne, ecart-type, min/max et IC95 bootstrap
des indicateurs metier sont conserves.

## Unites

Le service est un ratio (ou un ecart en points), le backlog est en UN.jours,
la production en UN et en pourcentage de sa reference, et chaque stock
composant reste dans son UOM propre. Aucune somme de stocks inter-UOM n'entre
dans le classement reseau.

## Preuve lots

La racine est une **reception utilisable taguee** par l'incident. Les lots
descendants sont trouves par parcours parent-enfant. Le gate refuse un run si
un evenement applique et une expedition taguee positive utilisable dans
l'horizon existent sans racine correspondante. Les quantites de descendants
sont des bornes hautes d'exposition genealogique, jamais des pertes causees.
Pour `quality_hold`, l'intervalle arrivee physique estimee -> date utilisable
est reconstruit; le moteur ne materialise pas un stock de quarantaine natif.

- runs stresses : {lot_proof_summary.get('stressed_run_count', 0)};
- runs avec reception utilisable touchee : {lot_proof_summary.get('run_with_impacted_receipt_count', 0)};
- gates racine invalides : {lot_proof_summary.get('invalid_missing_expected_usable_receipt_root_run_count', 0)};
- genealogies atteignant lot fini/client : {lot_proof_summary.get('run_with_finished_descendant_count', 0)} / {lot_proof_summary.get('run_with_client_delivery_descendant_count', 0)}.

## Execution

- mode : `{mode}`;
- scenarios definis : {scenario_count};
- runs executes ou reextraits : {executed_runs};
- dossier : `{output_dir}`.

Statuts d'effet :

{statuses}

## Volumes du protocole principal

- smoke : {run_budget.get('smoke', 0)} runs;
- screening : {run_budget.get('screening', 0)} runs;
- confirmation : {run_budget.get('confirmation', 0)} runs = {run_budget.get('confirmation_baseline', 0)} references + {run_budget.get('confirmation_stress', 0)} stress;
- campagne complete : {run_budget.get('full', 0)} runs.

Les incidents communs aux fournisseurs multi-voies, la robustesse temporelle
et la comparaison des quatre causes sur les priorites sont des campagnes
separees, planifiees mais non executees ici.
"""


def retention_audit(output_dir: Path, retention: str) -> dict[str, Any]:
    cases_dir = output_dir / "cases"
    files = [path for path in cases_dir.rglob("*") if path.is_file()] if cases_dir.exists() else []
    forbidden_names = set(campaign_core.RETENTION_DIRECTORY_ALLOWLIST)
    forbidden_directories = [
        str(path.resolve())
        for path in cases_dir.rglob("*")
        if path.is_dir() and path.name in forbidden_names
    ] if cases_dir.exists() else []
    largest = max(files, key=lambda path: path.stat().st_size) if files else None
    total_bytes = sum(path.stat().st_size for path in files)
    return {
        "retention_mode": retention,
        "retained_case_file_count": len(files),
        "retained_case_total_bytes": total_bytes,
        "retained_case_largest_file": str(largest.resolve()) if largest else "",
        "retained_case_largest_file_bytes": largest.stat().st_size if largest else 0,
        "forbidden_heavy_directory_count": len(forbidden_directories),
        "forbidden_heavy_directories": forbidden_directories,
        "summary_retention_pass": (
            retention != "summary"
            or (
                not forbidden_directories
                and (largest is None or largest.stat().st_size < 25 * 1024 * 1024)
            )
        ),
        "interpretation": (
            "Le mode summary conserve les petits résumés, rapports et logs; "
            "les répertoires data/plots/maps/run générés par chaque cas sont supprimés."
        ),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "smoke", "screening", "full"), default="plan")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--reference-run", type=Path, default=DEFAULT_REFERENCE_RUN)
    parser.add_argument("--scope-audit", type=Path, default=DEFAULT_SCOPE_AUDIT)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument("--engine-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--scenario-id", default="scn:BASE")
    parser.add_argument("--days", type=int, default=720)
    parser.add_argument("--screening-seed", type=int, default=DEFAULT_SCREENING_SEED)
    parser.add_argument("--confirmation-seeds", default=DEFAULT_CONFIRMATION_SEEDS)
    parser.add_argument("--confirmation-top-lanes", type=int, default=DEFAULT_CONFIRMATION_TOP_LANES)
    parser.add_argument("--expected-active-lanes", type=int, default=DEFAULT_EXPECTED_ACTIVE_LANES)
    parser.add_argument("--smoke-lanes", type=int, default=2)
    parser.add_argument(
        "--smoke-components",
        default="",
        help="Comma-separated active component labels for a targeted smoke.",
    )
    parser.add_argument(
        "--smoke-all-levels",
        action="store_true",
        help="Include both designed levels for targeted smoke mechanisms.",
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--retention", choices=("summary", "full"), default="summary")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.days < INCIDENT_DURATION_DAYS:
        raise ValueError(
            f"L'horizon doit atteindre au moins {INCIDENT_DURATION_DAYS} jours"
        )
    if args.workers <= 0:
        raise ValueError("--workers must be positive")
    confirmation_seeds = campaign_core.parse_seeds(args.confirmation_seeds)
    if args.mode == "full" and len(confirmation_seeds) != 30:
        raise ValueError(
            "La confirmation finale doit utiliser exactement 30 graines appariees "
            "sur les 18 voies et les deux familles predeclarees."
        )
    repo_root = args.repo_root.resolve()
    reference_run = args.reference_run.resolve()
    scope_audit = args.scope_audit.resolve()
    graph_path = _required_file(args.graph, "graphe")
    engine_path = _required_file(args.engine, "moteur")
    profile_path = _required_file(args.engine_profile, "profil moteur")
    shipment_path = _required_file(
        reference_run / "data" / "production_supplier_shipments_daily.csv",
        "flux fournisseurs V10",
    )
    scope_audit_path = _required_file(
        scope_audit / "supplier_lane_scope.csv", "audit de périmètre v8"
    )
    scope_audit_manifest_path = _required_file(
        scope_audit / "manifest.json", "manifeste de périmètre v8"
    )
    floor_source = _required_file(
        reference_run / "data" / "supplier_capacity_calibration_measured_period.csv",
        "calibration de capacité V10",
    )
    if not _reference_open_orders_disabled(reference_run):
        raise ValueError("La référence sélectionnée réactive les commandes initiales de janvier")
    # The V4 helper audits its original three-chain scope.  Prepare the two
    # validated positive physical floors before pointing its extraction
    # helpers at the dynamic 18-lane scope.
    prepared_floor_rows, floor_audit = campaign_core.build_prepared_physical_floor_rows(
        _read_csv(floor_source)
    )
    graph = _read_json(graph_path)
    reference_shipment_rows = _read_csv(shipment_path)
    lanes = discover_active_lanes(
        graph=graph, shipment_rows=reference_shipment_rows, days=args.days
    )
    scope_crosscheck = validate_scope_audit_crosscheck(
        lanes, _read_csv(scope_audit_path)
    )
    scope_manifest = _read_json(scope_audit_manifest_path)
    if _to_int(scope_manifest.get("lane_count"), -1) != 33:
        raise ValueError("Le manifeste v8 ne contient pas les 33 voies structurelles")
    if str(scope_manifest.get("graph_sha256") or "") != _sha256(graph_path):
        raise ValueError("Le graphe du screening diffère de celui audité en v8")
    if str(scope_manifest.get("baseline_shipments_sha256") or "") != _sha256(
        shipment_path
    ):
        raise ValueError("Les flux V10 du screening diffèrent de ceux audités en v8")
    if _to_int(scope_manifest.get("observed_order_row_count"), -1) != 52:
        raise ValueError("Le manifeste v8 ne contient pas les 52 lignes de commandes exactes")
    if _to_int(scope_manifest.get("purchase_order_rows_uom_normalized"), -1) != 14:
        raise ValueError("Le manifeste v8 ne trace pas les 14 conversions G vers KG")
    expected_exclusion_counts = {
        "raw_purchase_order_audit_row_count": 82,
        "purchase_order_rows_excluded_from_exact_lanes": 30,
        "purchase_order_suppliers_excluded_from_exact_lanes": 11,
        "purchase_order_items_excluded_from_exact_lanes": 10,
        "purchase_order_rows_with_unmapped_division": 16,
    }
    for field, expected in expected_exclusion_counts.items():
        if _to_int(scope_manifest.get(field), -1) != expected:
            raise ValueError(
                f"Le manifeste v8 donne {scope_manifest.get(field)!r} pour {field}; "
                f"{expected} attendu"
            )
    scope_crosscheck.update(
        {
            "scope_audit_version": "v8",
            "observed_order_row_count": _to_int(
                scope_manifest.get("observed_order_row_count"), -1
            ),
            "purchase_order_rows_uom_normalized": _to_int(
                scope_manifest.get("purchase_order_rows_uom_normalized"), -1
            ),
            "order_quantity_presentation": (
                "14 lignes G converties en KG; 52 lignes de commandes ouvertes exactes"
            ),
            "raw_purchase_order_audit_row_count": 82,
            "purchase_order_rows_excluded_from_exact_lanes": 30,
            "purchase_order_suppliers_excluded_from_exact_lanes": 11,
            "purchase_order_items_excluded_from_exact_lanes": 10,
            "purchase_order_rows_with_unmapped_division": 16,
            "excluded_order_interpretation": (
                "30 lignes sur 82 ne sont pas rattachées à une voie exacte du graphe; "
                "elles couvrent 11 fournisseurs et 10 articles, dont 16 lignes de la "
                "division 1820 non représentée dans le périmètre simulé."
            ),
        }
    )
    if len(lanes) != args.expected_active_lanes:
        raise ValueError(
            f"{len(lanes)} voies actives découvertes, {args.expected_active_lanes} attendues"
        )
    if args.mode == "full" and args.confirmation_top_lanes != len(lanes):
        raise ValueError(
            "La confirmation finale doit couvrir les 18 voies actives; "
            f"--confirmation-top-lanes={args.confirmation_top_lanes} reçu"
        )
    inactive_in_window = [
        item.chain.chain_id
        for item in lanes
        if item.active_window_shipped_qty <= 1e-12
        or item.active_window_pulled_qty <= 1e-12
    ]
    if inactive_in_window:
        raise ValueError(
            "La fenêtre active propre ne sollicite pas toutes les voies actives: "
            + ", ".join(inactive_in_window)
        )
    configure_campaign_core(lanes)
    chains = tuple(item.chain for item in lanes)
    chain_by_id = {chain.chain_id: chain for chain in chains}
    reference_by_chain = {item.chain.chain_id: item for item in lanes}
    scenarios = build_scenarios(lanes)
    expected_scenarios = 1 + len(lanes) * len(MECHANISMS) * len(LEVELS)
    if len(scenarios) != expected_scenarios:
        raise AssertionError("Le plan de scénarios contient un doublon ou un oubli")
    run_budget = planned_run_counts(
        active_lane_count=len(lanes),
        confirmation_seed_count=len(confirmation_seeds),
    )
    common_cause_rows, common_cause_manifest = multi_lane_common_cause_design(
        lanes=lanes,
        shipment_rows=reference_shipment_rows,
        days=args.days,
        screening_seed=args.screening_seed,
    )
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else ARTIFACT_PARENT
        / "supplier_network_risk_screen_campaign"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    prepared_floor_path = output_dir / "inputs" / "prepared_physical_supplier_floors.csv"
    physical_map = {
        (
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        ): _to_float(row.get("tested_capacity_floor_qty_per_day"))
        for row in prepared_floor_rows
    }
    profile_args = tuple(campaign_core.engine_profile_args(profile_path))
    signature_payload = {
        "schema_version": SCHEMA_VERSION,
        "mode": args.mode,
        "campaign_script_sha256": _sha256(Path(__file__)),
        "v4_extraction_core_sha256": _sha256(Path(campaign_core.__file__)),
        "graph_sha256": _sha256(graph_path),
        "engine_sha256": _sha256(engine_path),
        "reference_shipments_sha256": _sha256(shipment_path),
        "scope_audit_path": str(scope_audit),
        "scope_audit_csv_sha256": _sha256(scope_audit_path),
        "scope_audit_manifest_sha256": _sha256(scope_audit_manifest_path),
        "reference_summary_sha256": _sha256(
            reference_run / "summaries" / "first_simulation_summary.json"
        ),
        "supplier_floor_source_sha256": _sha256(floor_source),
        "prepared_supplier_floor_content_sha256": campaign_core.campaign_signature(
            {"rows": prepared_floor_rows}
        ),
        "profile_sha256": _sha256(profile_path),
        "days": args.days,
        "screening_seed": args.screening_seed,
        "smoke_components_requested": [
            value.strip()
            for value in str(args.smoke_components or "").split(",")
            if value.strip()
        ],
        "smoke_all_levels_requested": bool(args.smoke_all_levels),
        "confirmation_seeds": confirmation_seeds,
        "confirmation_top_lanes": args.confirmation_top_lanes,
        "confirmation_scope_requirement": "all_18_active_lanes",
        "confirmation_mathematical_families": dict(
            CONFIRMATION_MATHEMATICAL_FAMILIES
        ),
        "planned_run_counts": run_budget,
        "common_window_start_day": incident_window(args.days)[0],
        "common_window_end_day": incident_window(args.days)[1],
        "lane_specific_stress_duration_days": INCIDENT_DURATION_DAYS,
        "lane_specific_window_method": (
            "maximum_reference_shipped_quantity_in_180d_tie_nearest_J45_then_earliest"
        ),
        "active_chain_ids": sorted(chain_by_id),
        "scenario_ids": [item.scenario_id for item in scenarios],
        "reference_open_orders_disabled": True,
        "network_lot_trace_opt_in": True,
    }
    signature = campaign_core.campaign_signature(signature_payload)
    manifest_path = output_dir / "campaign_manifest.json"
    if manifest_path.is_file():
        existing_manifest = _read_json(manifest_path)
        if str(existing_manifest.get("campaign_signature") or "") != signature:
            raise RuntimeError(
                "Le dossier existe avec une autre signature; choisir un nouveau dossier additif"
            )
    elif any(path.name != "inputs" for path in output_dir.iterdir()):
        raise RuntimeError("Dossier de sortie non vide sans manifeste compatible")
    _write_csv(prepared_floor_path, prepared_floor_rows)
    manifest: dict[str, Any] = {
        **signature_payload,
        "campaign_signature": signature,
        "status": "planned" if args.mode == "plan" else "running",
        "output_dir": str(output_dir),
        "created_or_resumed_at_utc": utc_now(),
        "reference_class": "simulated_v10_without_january_opening_orders",
        "evidence_class": "conditional_simulation_hypothesis",
        "historical_occurrence_probability": "not_estimated",
        "supplier_ranking_meaning": (
            "conditional_model_sensitivity_priority_not_observed_criticality"
        ),
        "failure_mode_summary_evidence_stage": "screening_1_realisation",
        "failure_mode_summary_meaning": (
            "balanced_18_lanes_x_4_modes_x_2_levels_first_pass; "
            "not_multi_seed_confirmed_and_not_historical_frequency"
        ),
        "mechanism_independence_limitation": (
            "availability_versus_quality_yield_and_transport_delay_versus_quality_hold_"
            "may_be_numerically_equivalent_on_some_lanes; identical_responses_are_not_"
            "independent_evidence_even_when_business_causes_differ"
        ),
        "primary_ranking_time_window_limitation": (
            "lane_specific_strongest_180d_window_intentionally_mixes_lane_vulnerability_"
            "and_high_load_period; temporal_robustness_not_yet_tested"
        ),
        "global_ranking_unit_contract": (
            "no_raw_stock_quantity_tie_break_across_heterogeneous_uom; service_backlog_"
            "production_then_days_or_ratios_only"
        ),
        "lot_proof_contract": {
            "lot_trace_opt_in_network_only": True,
            "root_identification": (
                "direct risk_event_ids on usable lane-receipt lots"
            ),
            "root_gate": (
                "if expected risk is applied and a positive tagged shipment is usable "
                "within horizon, at least one tagged usable-receipt root is mandatory"
            ),
            "descendant_identification": "parent_to_child_genealogy_traversal",
            "extract_before_summary_retention": True,
            "detailed_proof_stage": (
                "first confirmation seed per lane and mathematical family only"
            ),
            "source_row_semantics": (
                "identifiant technique de ligne, pas numero de lot industriel"
            ),
            "descendant_quantity_scope": (
                "full-lot genealogical exposure upper bound, not causal delay or loss"
            ),
            "quality_hold_limitation": (
                "quality wait reconstructed from usable day minus tested delay; no "
                "native quarantine-stock state exists in this engine path"
            ),
        },
        "post_priority_extensions": {
            "executed_in_this_campaign": False,
            "temporal_robustness": (
                "four_non_overlapping_windows_x_three_priority_lanes_x_three_paired_seeds"
            ),
            "severe_mode_confirmation": (
                "four_severe_modes_x_three_priority_lanes_x_thirty_paired_seeds"
            ),
            "if_priority_gate_fails_label": (
                "groupe_top5_ex_aequo_priorite_non_tranchee"
            ),
            "historical_probability_or_recurrence": "not_estimated",
        },
        "graph_mutated": False,
        "cold_start_mutated": False,
        "previous_artifacts_mutated": False,
        "physical_floor_audit": floor_audit,
        "scope_audit_crosscheck": scope_crosscheck,
        "planned_run_counts": run_budget,
        "confirmation_design": {
            "selected_stress_scenario_count": (
                len(lanes) * len(CONFIRMATION_MATHEMATICAL_FAMILIES)
            ),
            "unique_lane_count": len(lanes),
            "family_count": len(CONFIRMATION_MATHEMATICAL_FAMILIES),
            "family_selection_basis": "predeclared_before_screening_results",
            "one_seed_worst_mode_selection_used": False,
            "ten_seed_intermediate_checkpoint_only": True,
            "final_paired_seed_count": len(confirmation_seeds),
        },
        "all_lane_confirmation_to_30": {
            "status": "included_in_main_full_campaign",
            "candidate_preselection_used": False,
            "confirmed_lane_count": len(lanes),
            "mathematical_family_count": len(
                CONFIRMATION_MATHEMATICAL_FAMILIES
            ),
            "paired_seed_count": len(confirmation_seeds),
            "release_rule": (
                "priority_simulee_stabilisee_only_if_top3_presence_at_least_29_of_30_"
                "and_paired_seed_block_bootstrap_or_interval_separates_rank3_from_rank4"
            ),
            "otherwise": "top5_ex_aequo_or_priorite_non_tranchee",
        },
        "multi_lane_supplier_common_cause": common_cause_manifest,
    }
    _write_json(manifest_path, manifest)
    _write_csv(output_dir / "active_lane_reference.csv", lane_reference_rows(lanes, args.days))
    _write_csv(
        output_dir / "scenario_design.csv",
        scenario_design_rows(scenarios, chain_by_id, reference_by_chain),
    )
    _write_csv(
        output_dir / "multi_lane_supplier_common_cause_design.csv",
        common_cause_rows,
    )
    _write_json(
        output_dir / "multi_lane_supplier_common_cause_manifest.json",
        common_cause_manifest,
    )
    risk_inputs = _risk_inputs(output_dir, scenarios, args.days, reference_by_chain)
    config = campaign_core.RunConfig(
        repo_root=repo_root,
        output_dir=output_dir,
        engine=engine_path,
        graph=graph_path,
        supplier_floors=prepared_floor_path,
        factory_capacities=None,
        profile_args=profile_args,
        scenario_id=args.scenario_id,
        days=args.days,
        retention=args.retention,
        physical_capacity_by_lane=physical_map,
    )
    all_metric_rows: list[dict[str, Any]] = []
    screening_summary: list[dict[str, Any]] = []
    confirmation_rows: list[dict[str, Any]] = []
    confirmation_summary: list[dict[str, Any]] = []
    final_stability: list[dict[str, Any]] = []
    priority_set_stabilized = False
    rank3_rank4_separated = False
    release_gate_audit: dict[str, Any] = {}
    confirmation_seed_count = 0
    selected_ids: tuple[str, ...] = ()
    scenario_by_id = {item.scenario_id: item for item in scenarios}
    if args.mode == "smoke":
        smoke_scenarios = select_smoke_scenarios(
            lanes,
            scenarios,
            lane_count=args.smoke_lanes,
            component_labels=tuple(
                value.strip()
                for value in str(args.smoke_components or "").split(",")
                if value.strip()
            ),
            include_all_levels=bool(args.smoke_all_levels),
        )
        all_metric_rows = execute_stage(
            config=config,
            graph=graph,
            chains=chains,
            reference_by_chain=reference_by_chain,
            scenarios=smoke_scenarios,
            seeds=(args.screening_seed,),
            stage="smoke",
            risk_inputs=risk_inputs,
            metric_path=output_dir / "smoke_metrics.csv",
            workers=args.workers,
        )
        screening_summary = aggregate_scenarios(
            all_metric_rows, smoke_scenarios, chain_by_id
        )
    elif args.mode in {"screening", "full"}:
        all_metric_rows = execute_stage(
            config=config,
            graph=graph,
            chains=chains,
            reference_by_chain=reference_by_chain,
            scenarios=scenarios,
            seeds=(args.screening_seed,),
            stage="screening",
            risk_inputs=risk_inputs,
            metric_path=output_dir / "screening_metrics.csv",
            workers=args.workers,
        )
        screening_summary = aggregate_scenarios(
            all_metric_rows, scenarios, chain_by_id
        )
        if args.mode == "full":
            selected_ids = select_predeclared_family_confirmation_scenarios(
                scenarios, lanes
            )
            confirmation_scenarios = [scenarios[0]] + [
                scenario_by_id[scenario_id] for scenario_id in selected_ids
            ]
            confirmation_rows = execute_stage(
                config=config,
                graph=graph,
                chains=chains,
                reference_by_chain=reference_by_chain,
                scenarios=confirmation_scenarios,
                seeds=confirmation_seeds,
                stage="confirmation",
                risk_inputs=risk_inputs,
                metric_path=output_dir / "confirmation_metrics.csv",
                workers=args.workers,
            )
            confirmation_summary = aggregate_scenarios(
                confirmation_rows, confirmation_scenarios, chain_by_id
            )
            _write_csv(output_dir / "confirmation_summary.csv", confirmation_summary)
            _write_json(
                output_dir / "confirmation_selection.json",
                {
                    "selected_scenario_ids": list(selected_ids),
                    "selected_stress_scenario_count": len(selected_ids),
                    "confirmed_unique_chain_ids": sorted(
                        {scenario_by_id[item].chain_id for item in selected_ids}
                    ),
                    "confirmed_unique_lane_count": len(
                        {scenario_by_id[item].chain_id for item in selected_ids}
                    ),
                    "mathematical_families": dict(
                        CONFIRMATION_MATHEMATICAL_FAMILIES
                    ),
                    "rule": (
                        "two_predeclared_severe_mathematical_families_on_all_18_active_"
                        "lanes_independent_of_one_seed_screening"
                    ),
                    "one_seed_worst_scenario_selection_used": False,
                },
            )
            all_metric_rows = list(all_metric_rows) + list(confirmation_rows)
    if screening_summary:
        _write_csv(output_dir / "scenario_summary.csv", screening_summary)
        _write_csv(output_dir / "screening_scenario_summary.csv", screening_summary)
        stressed = [
            row for row in screening_summary if str(row.get("failure_mode")) != "baseline"
        ]
        screening_stage = (
            "smoke_1_realisation" if args.mode == "smoke" else "screening_1_realisation"
        )
        screening_supplier_ranking = rank_suppliers(
            stressed, evidence_stage=screening_stage
        )
        screening_mode_summary = summarize_failure_modes(
            stressed, evidence_stage=screening_stage
        )
        _write_csv(
            output_dir / "screening_supplier_sensitivity_ranking.csv",
            screening_supplier_ranking,
        )
        _write_csv(
            output_dir / "screening_failure_mode_sensitivity_summary.csv",
            screening_mode_summary,
        )
        if args.mode == "full" and confirmation_summary:
            confirmed_stressed = [
                row
                for row in confirmation_summary
                if str(row.get("failure_mode")) != "baseline"
            ]
            confirmation_seed_count = len(
                {
                    _to_int(row.get("seed"))
                    for row in confirmation_rows
                    if str(row.get("scenario_id")) != "baseline_nominal"
                }
            )
            confirmed_stage = f"confirmation_{confirmation_seed_count}_realisations"
            confirmed_supplier_ranking = rank_suppliers(
                confirmed_stressed, evidence_stage=confirmed_stage
            )
            stability = confirmed_top3_stability(
                confirmation_rows,
                scenario_by_id=scenario_by_id,
                chain_by_id=chain_by_id,
                aggregate_ranking=confirmed_supplier_ranking,
            )
            final_stability = stability
            release_gate_audit = scientific_release_gate_audit(
                confirmation_rows,
                selected_scenario_ids=selected_ids,
                scenario_by_id=scenario_by_id,
                minimum_flow_seed_count=29,
            )
            statistical_set_pass = bool(stability) and all(
                campaign_core.as_bool(row.get("priority_set_stabilized"))
                for row in stability
            )
            release_ready = statistical_set_pass and campaign_core.as_bool(
                release_gate_audit.get("all_release_gates_pass")
            )
            for row in stability:
                row["statistical_priority_set_pass"] = statistical_set_pass
                row["scientific_release_gates_pass"] = campaign_core.as_bool(
                    release_gate_audit.get("all_release_gates_pass")
                )
                row["priority_set_stabilized"] = release_ready
                row["top3_set_validated"] = release_ready
                aggregate_top3 = campaign_core.as_bool(row.get("aggregate_top3"))
                row["stable_confirmed_top3"] = release_ready and aggregate_top3
                row["stabilized_priority_rank"] = (
                    row.get("aggregate_confirmation_rank")
                    if release_ready and aggregate_top3
                    else ""
                )
                if not release_ready and aggregate_top3:
                    row["top3_status"] = (
                        "groupe_top5_ex_aequo_priorite_non_tranchee"
                        if confirmation_seed_count >= 30
                        else "preselection_a_approfondir_30_graines"
                    )
            stability_by_supplier = {
                str(row.get("supplier_id")): row for row in stability
            }
            for row in confirmed_supplier_ranking:
                audit = stability_by_supplier[str(row.get("supplier_id"))]
                for field in (
                    "top3_presence_seed_count",
                    "top3_presence_fraction",
                    "minimum_required_fraction",
                    "top3_presence_wilson95_lower",
                    "top3_presence_wilson95_upper",
                    "individual_top3_stability_pass",
                    "stabilized_presence_required_seed_count",
                    "stabilized_presence_pass",
                    "bootstrap_resample_count",
                    "bootstrap_pairing_unit",
                    "bootstrap_rank_ci95_low",
                    "bootstrap_rank_ci95_high",
                    "rank3_rank4_interval_separated",
                    "priority_set_stabilized",
                    "top3_set_validated",
                    "stable_confirmed_top3",
                    "final_top3_rank",
                    "stabilized_priority_rank",
                    "provisional_priority_rank",
                    "top3_status",
                ):
                    row[field] = audit.get(field)
            selected_scenario_mode_summary = summarize_failure_modes(
                confirmed_stressed, evidence_stage=confirmed_stage
            )
            for row in selected_scenario_mode_summary:
                row["comparison_scope"] = (
                    "two_predeclared_mathematical_families_balanced_on_all_18_lanes; "
                    "not_a_global_comparison_of_four_business_causes"
                )
                row["is_global_failure_mode_comparison"] = False
            _write_csv(
                output_dir / "confirmation_supplier_sensitivity_ranking.csv",
                confirmed_supplier_ranking,
            )
            _write_csv(
                output_dir / "confirmation_selected_scenario_mode_summary.csv",
                selected_scenario_mode_summary,
            )
            _write_csv(
                output_dir / "confirmation_mathematical_family_summary.csv",
                selected_scenario_mode_summary,
            )
            _write_csv(output_dir / "confirmed_top3_stability.csv", stability)
            _write_json(
                output_dir / "scientific_release_gates.json",
                release_gate_audit,
            )
            _write_csv(
                output_dir / "active_window_flow_release_gate_by_lane.csv",
                release_gate_audit.get("active_window_flow_gate_by_lane", []),
            )
            priority_set_stabilized = bool(stability) and all(
                campaign_core.as_bool(row.get("priority_set_stabilized"))
                for row in stability
            )
            rank3_rank4_separated = bool(stability) and all(
                campaign_core.as_bool(row.get("rank3_rank4_interval_separated"))
                for row in stability
            )
            stabilized_supplier_ids = [
                str(row.get("supplier_id"))
                for row in stability
                if row.get("stabilized_priority_rank") not in {"", None}
            ]
            priority_group_supplier_ids = [
                str(row.get("supplier_id"))
                for row in stability
                if _to_int(row.get("aggregate_confirmation_rank"), 99) <= 5
            ]
            _write_json(
                output_dir / "final_top3_decision.json",
                {
                    "status": (
                        "priorites_simulees_stabilisees_dans_test_voie_par_voie"
                        if priority_set_stabilized
                        else "groupe_top5_ex_aequo_priorite_non_tranchee"
                    ),
                    "industrial_criticality_claimed": False,
                    "historical_occurrence_probability": "not_estimated",
                    "confirmation_seed_count": confirmation_seed_count,
                    "minimum_presence_rule": (
                        "au_moins_29_graines_sur_30_pour_chacune_des_3_priorites"
                    ),
                    "paired_seed_block_bootstrap_resamples": 10_000,
                    "rank3_rank4_interval_separated": rank3_rank4_separated,
                    "priority_set_stabilized": priority_set_stabilized,
                    "scientific_release_gates": release_gate_audit,
                    "baseline_service_gate_pass": campaign_core.as_bool(
                        release_gate_audit.get(
                            "baseline_both_products_on_due_at_least_95_all_seeds_pass"
                        )
                    ),
                    "pairing_integrity_gate_pass": bool(
                        campaign_core.as_bool(
                            release_gate_audit.get("all_metric_rows_valid_pass")
                        )
                        and campaign_core.as_bool(
                            release_gate_audit.get(
                                "j0_state_hash_pairing_100pct_pass"
                            )
                        )
                        and campaign_core.as_bool(
                            release_gate_audit.get(
                                "input_graph_hash_pairing_100pct_pass"
                            )
                        )
                    ),
                    "active_lane_flow_gate_pass": campaign_core.as_bool(
                        release_gate_audit.get(
                            "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass"
                        )
                    ),
                    "top3_set_validated": priority_set_stabilized,
                    "stabilized_priority_supplier_ids": stabilized_supplier_ids,
                    "final_supplier_ids": stabilized_supplier_ids,
                    "priority_group_top5_supplier_ids": priority_group_supplier_ids,
                    "non_release_reason": (
                        ""
                        if priority_set_stabilized
                        else "presence_29_sur_30_et_separation_bootstrap_rang3_rang4_non_"
                        "satisfaites_ensemble"
                    ),
                },
            )
            confirmed_lane_ranking = rank_lanes(
                confirmed_stressed,
                evidence_stage=confirmed_stage,
            )
            lane_stability = confirmed_lane_preselection_stability(
                confirmation_rows,
                scenario_by_id=scenario_by_id,
                chain_by_id=chain_by_id,
                aggregate_ranking=confirmed_lane_ranking,
            )
            _write_csv(
                output_dir / "confirmation_lane_sensitivity_ranking.csv",
                confirmed_lane_ranking,
            )
            _write_csv(
                output_dir / "lane_sensitivity_ranking.csv",
                confirmed_lane_ranking,
            )
            _write_csv(
                output_dir / "lane_priority_membership_stability.csv",
                lane_stability,
            )
            temporal_design, severe_mode_design, extension_manifest = (
                post_priority_extension_designs(
                    lane_ranking=confirmed_lane_ranking,
                    scenarios=scenarios,
                    chain_by_id=chain_by_id,
                    confirmation_seeds=confirmation_seeds,
                )
            )
            _write_csv(
                output_dir / "temporal_robustness_extension_design.csv",
                temporal_design,
            )
            _write_csv(
                output_dir / "priority_severe_mode_extension_design.csv",
                severe_mode_design,
            )
            _write_json(
                output_dir / "post_priority_extensions_manifest.json",
                extension_manifest,
            )
            _write_csv(
                output_dir / "lane_evidence_status.csv",
                lane_evidence_status_rows(
                    lanes,
                    selected_scenario_ids=selected_ids,
                    scenario_by_id=scenario_by_id,
                    confirmation_seed_count=confirmation_seed_count,
                ),
            )
            # In a complete campaign, the generic final files contain only
            # multi-seed confirmed evidence.  The 1-seed ranking remains in
            # explicitly named screening files above.
            _write_csv(
                output_dir / "supplier_sensitivity_ranking.csv",
                confirmed_supplier_ranking,
            )
            _write_csv(
                output_dir / "failure_mode_sensitivity_summary.csv",
                screening_mode_summary,
            )
        else:
            _write_csv(
                output_dir / "supplier_sensitivity_ranking.csv",
                screening_supplier_ranking,
            )
            _write_csv(
                output_dir / "failure_mode_sensitivity_summary.csv",
                screening_mode_summary,
            )
    status_counts = Counter(
        str(row.get("effect_status") or "")
        for row in all_metric_rows
        if str(row.get("scenario_id")) != "baseline_nominal"
    )
    lot_proof_summary = summarize_lot_proof_campaign(all_metric_rows)
    report = _report_text_v4(
        mode=args.mode,
        lane_count=len(lanes),
        supplier_count=len({lane.chain.affected_lanes[0].supplier_id for lane in lanes}),
        scenario_count=len(scenarios),
        executed_runs=len(all_metric_rows),
        status_counts=status_counts,
        lot_proof_summary=lot_proof_summary,
        output_dir=output_dir,
        run_budget=run_budget,
    )
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    compact_retention_audit = retention_audit(output_dir, args.retention)
    if args.mode != "plan" and not campaign_core.as_bool(
        compact_retention_audit.get("summary_retention_pass")
    ):
        raise RuntimeError(
            "L'audit de rétention summary a trouvé un répertoire ou fichier lourd inattendu"
        )
    manifest.update(
        {
            "status": "planned" if args.mode == "plan" else "complete",
            "completed_at_utc": utc_now(),
            "active_lane_count": len(lanes),
            "distinct_supplier_count": len(
                {lane.chain.affected_lanes[0].supplier_id for lane in lanes}
            ),
            "scenario_count": len(scenarios),
            "executed_or_reextracted_run_count": len(all_metric_rows),
            "effect_status_counts": dict(sorted(status_counts.items())),
            "lot_proof": lot_proof_summary,
            "retention_audit": compact_retention_audit,
            "planned_confirmed_unique_lane_count": len(lanes),
            "planned_confirmed_stress_scenario_count": (
                len(lanes) * len(CONFIRMATION_MATHEMATICAL_FAMILIES)
            ),
            "confirmed_stress_scenario_count": len(selected_ids),
            "confirmed_lane_count": len(
                {scenario_by_id[item].chain_id for item in selected_ids}
            ),
            "screening_only_lane_count": (
                len(lanes)
                - len({scenario_by_id[item].chain_id for item in selected_ids})
                if args.mode == "full"
                else len(lanes)
            ),
            "confirmation_seed_count": confirmation_seed_count,
            "minimum_top3_presence_seed_count": (
                29 if confirmation_seed_count == 30 else 0
            ),
            "paired_seed_block_bootstrap_resamples": (
                10_000 if confirmation_seed_count >= 30 else 0
            ),
            "rank3_rank4_interval_separated": rank3_rank4_separated,
            "priority_set_stabilized": priority_set_stabilized,
            "scientific_release_gates": release_gate_audit,
            "baseline_service_gate_pass": campaign_core.as_bool(
                release_gate_audit.get(
                    "baseline_both_products_on_due_at_least_95_all_seeds_pass"
                )
            ),
            "pairing_integrity_gate_pass": bool(
                campaign_core.as_bool(
                    release_gate_audit.get("all_metric_rows_valid_pass")
                )
                and campaign_core.as_bool(
                    release_gate_audit.get("j0_state_hash_pairing_100pct_pass")
                )
                and campaign_core.as_bool(
                    release_gate_audit.get("input_graph_hash_pairing_100pct_pass")
                )
            ),
            "active_lane_flow_gate_pass": campaign_core.as_bool(
                release_gate_audit.get(
                    "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass"
                )
            ),
            "extensions_required": {
                "multi_lane_supplier_common_cause": (
                    "planned_separate_not_executed"
                ),
                "temporal_robustness": "planned_separate_not_executed",
                "four_business_cause_confirmation": (
                    "planned_separate_not_executed"
                ),
                "causal_lot_attribution": (
                    "required_not_available_genealogy_only"
                ),
            },
            "statistical_validation": {
                "confirmation_seed_count": confirmation_seed_count,
                "minimum_presence_seed_count": (
                    29 if confirmation_seed_count == 30 else 0
                ),
                "bootstrap_pairing_unit": "paired_seed_block",
                "bootstrap_resample_count": (
                    10_000 if confirmation_seed_count >= 30 else 0
                ),
                "rank3_rank4_separation_pass": rank3_rank4_separated,
                "p05_reporting_policy": (
                    "not_reported_below_100_realisations"
                ),
            },
            "stable_confirmed_top3_supplier_count": sum(
                campaign_core.as_bool(row.get("stable_confirmed_top3"))
                for row in final_stability
            ),
            "final_top3_conclusion_status": (
                "priorites_simulees_stabilisees_dans_test_voie_par_voie"
                if priority_set_stabilized
                else (
                    "groupe_top5_ex_aequo_priorite_non_tranchee"
                    if args.mode == "full"
                    else "non_disponible_avant_confirmation"
                )
            ),
        }
    )
    _write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
