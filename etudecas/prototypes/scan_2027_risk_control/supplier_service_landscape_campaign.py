#!/usr/bin/env python3
"""Explore supplier-risk service cliffs, then confirm selected cases.

The campaign is intentionally additive.  It never edits the reference graph,
the engine profile, or historical results.  It runs two stages:

* one-seed screening of seven operational supplier-risk mechanisms; and
* paired multi-seed confirmation of deterministic, scientifically useful
  candidates selected from the screening results.

The intermittent-delay family deserves special care.  Editing Erlang stages
in the graph before warm-up changes the state at measured day zero and breaks
the paired comparison.  This campaign therefore keeps the graph unchanged and
uses deterministic post-J0 grouped-delay windows.  The windows cover about
half the measured horizon at twice the corresponding constant extra delay, so
their temporal mean is comparable.  These are grouped-delay profiles, not
fitted supplier CVs or OTIF estimates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_PARENT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
DEFAULT_GRAPH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
DEFAULT_BASELINE_RUN = (
    ARTIFACT_PARENT
    / "supplier_service_landscape_calibration_20260831_v10"
)
DEFAULT_PROFILE = (
    REPO_ROOT
    / "etudecas"
    / "prototypes"
    / "scan_2027_risk_control"
    / "config"
    / "canonical_real_baseline_engine_profile.json"
)
DEFAULT_ENGINE = REPO_ROOT / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"
PRODUCTS = ("268091", "268967")
INCIDENT_START_DAY = 45
INCIDENT_DURATION_DAYS = 180
WARMUP_DAYS = 240
RECOVERY_STABILITY_DAYS = 28
BASELINE_MIN_SERVICE = 0.95
PHYSICAL_CAPACITY_OVERRIDE_PAIRS = frozenset(
    {
        ("SDC-VD0914360C", "item:338929"),
        ("SDC-VD0993480A", "item:344135"),
    }
)
DYNAMIC_MRP_REQUIREMENT_PAIRS = frozenset(
    {
        "M-1810|item:338929",
        "M-1430|item:344135",
        "SDC-1450|item:021081",
    }
)
SMOOTHED_COVER_REQUIREMENT_PAIRS = frozenset({"M-1430|item:344135"})
RISK_CSV_FIELDS = (
    "event_id",
    "risk_type",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "edge_id",
    "start_day",
    "end_day",
    "multiplier",
    "notes",
)
RETENTION_DIRECTORY_ALLOWLIST = frozenset({"data", "plots", "maps", "run"})
CAMPAIGN_PROTOCOL_ARGS = (
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
class Lane:
    supplier_id: str
    item_id: str
    dst_node_id: str
    label: str
    planned_lead_days: float

    @property
    def key(self) -> tuple[str, str, str]:
        return self.supplier_id, self.item_id, self.dst_node_id


@dataclass(frozen=True)
class Chain:
    chain_id: str
    label: str
    component_label: str
    target_product_id: str
    client_node_id: str
    affected_lanes: tuple[Lane, ...]
    healthy_lanes: tuple[Lane, ...] = ()


@dataclass(frozen=True)
class Mechanism:
    key: str
    label: str
    risk_type: str
    values: tuple[float, ...]
    unit: str
    no_op_value: float
    evidence_note: str


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    execution_scenario_id: str
    chain_id: str
    mechanism_key: str
    level_index: int
    level_code: str
    level_label: str
    value: float
    unit: str
    target_product_id: str
    client_node_id: str
    is_campaign_baseline: bool = False
    is_baseline_alias: bool = False
    is_not_applicable: bool = False


@dataclass(frozen=True)
class RunConfig:
    repo_root: Path
    output_dir: Path
    engine: Path
    graph: Path
    supplier_floors: Path
    factory_capacities: Path | None
    profile_args: tuple[str, ...]
    scenario_id: str
    days: int
    retention: str
    physical_capacity_by_lane: Mapping[tuple[str, str, str], float]


LEVELS: tuple[tuple[str, str], ...] = (
    ("excellent", "Excellent"),
    ("tres_bon", "Très bon"),
    ("bon", "Bon"),
    ("vigilance", "Vigilance"),
    ("degrade", "Dégradé"),
    ("severe", "Sévère"),
    ("critique", "Critique"),
)

# The input floor is recalibrated from a corrected, unconstrained baseline as
# 2.5 x the measured peak daily pull. Pair-specific lower levels then bracket
# the service cliffs found by targeted pilots. These are exploratory capacity
# hypotheses, not contractual capacities or supplier forecasts.
CAPACITY_LEVELS_338929 = (1.00, 0.20, 0.10, 0.08, 0.07, 0.06, 0.05)
CAPACITY_LEVELS_344135 = (1.00, 0.10, 0.05, 0.025, 0.015, 0.010, 0.005)
CAPACITY_LEVELS_NOT_APPLICABLE = CAPACITY_LEVELS_338929
LEAD_EXTRA_LEVELS = (0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0)
RELIABILITY_LEVELS = (1.0, 0.90, 0.70, 0.50, 0.30, 0.20, 0.10)
AVAILABILITY_LEVELS = (1.0, 0.80, 0.50, 0.25, 0.10, 0.05, 0.01)
QUALITY_DELAY_LEVELS = LEAD_EXTRA_LEVELS
QUALITY_YIELD_LEVELS = (1.0, 0.98, 0.90, 0.75, 0.50, 0.25, 0.10)

MECHANISMS: tuple[Mechanism, ...] = (
    Mechanism(
        "capacity",
        "Capacité fournisseur",
        "capacity",
        CAPACITY_LEVELS_NOT_APPLICABLE,
        "ratio",
        1.0,
        "Stress exploratoire autour du pic fonctionnel; ce n'est pas une capacité contractuelle.",
    ),
    Mechanism(
        "lead_extra",
        "Retard fournisseur constant",
        "lead_time_extra_days",
        LEAD_EXTRA_LEVELS,
        "jours",
        0.0,
        "Retard additionnel constant pendant l'horizon mesuré.",
    ),
    Mechanism(
        "reliability",
        "Fiabilité d'expédition",
        "reliability",
        RELIABILITY_LEVELS,
        "ratio",
        1.0,
        "Part utile des quantités expédiées dans le moteur.",
    ),
    Mechanism(
        "availability",
        "Disponibilité fournisseur",
        "availability",
        AVAILABILITY_LEVELS,
        "ratio",
        1.0,
        "Disponibilité opérationnelle de la voie d'approvisionnement.",
    ),
    Mechanism(
        "quality_delay",
        "Délai de libération qualité",
        "quality_delay",
        QUALITY_DELAY_LEVELS,
        "jours",
        0.0,
        "Temps de quarantaine/libération ajouté aux expéditions concernées.",
    ),
    Mechanism(
        "quality_yield",
        "Rendement qualité",
        "quality_yield",
        QUALITY_YIELD_LEVELS,
        "ratio",
        1.0,
        "Part des quantités reçues qui reste utilisable.",
    ),
    Mechanism(
        "intermittent_delay",
        "Retards intermittents groupés",
        "lead_time_extra_days",
        LEAD_EXTRA_LEVELS,
        "jours_moyens_ajoutes",
        0.0,
        "Épisodes post-J0 à charge temporelle comparable; profil hypothétique, pas OTIF mesuré.",
    ),
)
MECHANISM_BY_KEY = {item.key: item for item in MECHANISMS}

CHAINS: tuple[Chain, ...] = (
    Chain(
        "338929_m1810_268091",
        "338929 / SDC-VD0914360C → M-1810 → 268091",
        "338929",
        "268091",
        "C-XXXXX",
        (
            Lane(
                "SDC-VD0914360C",
                "item:338929",
                "M-1810",
                "338929 vers M-1810",
                42.0,
            ),
        ),
    ),
    Chain(
        "344135_m1430_268967",
        "344135 / SDC-VD0993480A → M-1430 → 268967",
        "344135",
        "268967",
        "C-XXXXX",
        (
            Lane(
                "SDC-VD0993480A",
                "item:344135",
                "M-1430",
                "344135 vers M-1430",
                35.0,
            ),
        ),
    ),
    Chain(
        "021081_sdc1450_268967",
        "021081 multisource → SDC-1450 → 268967",
        "021081",
        "268967",
        "C-XXXXX",
        (
            Lane("SDC-VD0949099A", "item:021081", "SDC-1450", "021081 source A", 120.0),
            Lane("SDC-VD0960508A", "item:021081", "SDC-1450", "021081 source B", 120.0),
            Lane("SDC-VD0972460A", "item:021081", "SDC-1450", "021081 source C", 120.0),
        ),
        (
            Lane(
                "SDC-VD0975221A",
                "item:021081",
                "SDC-1450",
                "021081 source témoin maintenue saine",
                120.0,
            ),
        ),
    ),
)
CHAIN_BY_ID = {item.chain_id: item for item in CHAINS}


class CaseValidationError(RuntimeError):
    """Raised when a run is not scientifically comparable or incomplete."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_output_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ARTIFACT_PARENT / "supplier_service_landscape_campaign" / stamp


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "oui"}


def slug_number(value: float) -> str:
    text = format(float(value), ".12g")
    return text.replace("-", "m").replace(".", "p")


def values_equal(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)


def parse_seeds(specification: str) -> list[int]:
    seeds: list[int] = []
    for raw_chunk in str(specification or "").split(","):
        chunk = raw_chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            first, last = (int(part.strip()) for part in chunk.split("-", 1))
            step = 1 if last >= first else -1
            seeds.extend(range(first, last + step, step))
        else:
            seeds.append(int(chunk))
    unique = list(dict.fromkeys(seeds))
    if not unique:
        raise ValueError("At least one seed is required")
    return unique


def mechanism_values_for_chain(chain: Chain, mechanism: Mechanism) -> tuple[float, ...]:
    if mechanism.key != "capacity":
        return mechanism.values
    if chain.chain_id == "338929_m1810_268091":
        return CAPACITY_LEVELS_338929
    if chain.chain_id == "344135_m1430_268967":
        return CAPACITY_LEVELS_344135
    return CAPACITY_LEVELS_NOT_APPLICABLE


def mechanism_is_applicable(chain: Chain, mechanism: Mechanism) -> bool:
    # The 021081 source rows have a zero physical supplier-capacity floor and
    # no observed measured-period pull.  A supplier-capacity ratio would be a
    # numerical label without an identifiable physical denominator.
    return not (
        chain.chain_id == "021081_sdc1450_268967"
        and mechanism.key == "capacity"
    )


def build_scenario_design() -> list[Scenario]:
    """Return the stable full design, including one shared campaign baseline."""

    scenarios = [
        Scenario(
            scenario_id="baseline_nominal",
            execution_scenario_id="baseline_nominal",
            chain_id="all",
            mechanism_key="baseline",
            level_index=-1,
            level_code="baseline",
            level_label="Référence nominale commune",
            value=1.0,
            unit="reference",
            target_product_id="all",
            client_node_id="C-XXXXX",
            is_campaign_baseline=True,
        )
    ]
    for chain in CHAINS:
        for mechanism in MECHANISMS:
            values = mechanism_values_for_chain(chain, mechanism)
            if len(values) != len(LEVELS):
                raise ValueError(f"Mechanism {mechanism.key} does not have seven levels")
            for level_index, ((level_code, level_label), value) in enumerate(
                zip(LEVELS, values)
            ):
                scenario_id = (
                    f"{chain.chain_id}__{mechanism.key}__"
                    f"l{level_index}_{slug_number(value)}"
                )
                baseline_alias = values_equal(value, mechanism.no_op_value)
                not_applicable = not mechanism_is_applicable(chain, mechanism)
                scenarios.append(
                    Scenario(
                        scenario_id=scenario_id,
                        execution_scenario_id=(
                            "baseline_nominal" if baseline_alias else scenario_id
                        ),
                        chain_id=chain.chain_id,
                        mechanism_key=mechanism.key,
                        level_index=level_index,
                        level_code=level_code,
                        level_label=level_label,
                        value=float(value),
                        unit=mechanism.unit,
                        target_product_id=chain.target_product_id,
                        client_node_id=chain.client_node_id,
                        is_baseline_alias=baseline_alias,
                        is_not_applicable=not_applicable,
                    )
                )
    return scenarios


def executable_scenarios(scenarios: Sequence[Scenario]) -> list[Scenario]:
    """Deduplicate all neutral mechanism levels onto the one shared baseline."""

    return [
        scenario
        for scenario in scenarios
        if scenario.is_campaign_baseline
        or (not scenario.is_baseline_alias and not scenario.is_not_applicable)
    ]


def scenario_design_rows(scenarios: Sequence[Scenario]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        if scenario.is_campaign_baseline:
            rows.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "execution_scenario_id": scenario.execution_scenario_id,
                    "is_campaign_baseline": True,
                    "is_baseline_alias": False,
                    "is_not_applicable": False,
                    "chain_id": "all",
                    "chain_label": "Référence commune aux trois chaînes",
                    "target_product_id": "all",
                    "client_node_id": scenario.client_node_id,
                    "component_item_id": "",
                    "affected_supplier_ids": "",
                    "healthy_supplier_ids": "",
                    "mechanism": "baseline",
                    "mechanism_label": "Référence nominale",
                    "risk_type": "",
                    "level_index": -1,
                    "level_code": "baseline",
                    "level_label": scenario.level_label,
                    "mechanism_value": 1.0,
                    "mechanism_unit": "reference",
                    "intermittent_delay_mean_extra_days": "",
                    "evidence_class": "simulated_reference",
                    "interpretation": "Une seule exécution de référence par graine, partagée entre les mécanismes.",
                }
            )
            continue
        chain = CHAIN_BY_ID[scenario.chain_id]
        mechanism = MECHANISM_BY_KEY[scenario.mechanism_key]
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "execution_scenario_id": scenario.execution_scenario_id,
                "is_campaign_baseline": False,
                "is_baseline_alias": scenario.is_baseline_alias,
                "is_not_applicable": scenario.is_not_applicable,
                "chain_id": scenario.chain_id,
                "chain_label": chain.label,
                "target_product_id": scenario.target_product_id,
                "client_node_id": scenario.client_node_id,
                "component_item_id": chain.component_label,
                "affected_supplier_ids": "|".join(
                    lane.supplier_id for lane in chain.affected_lanes
                ),
                "healthy_supplier_ids": "|".join(
                    lane.supplier_id for lane in chain.healthy_lanes
                ),
                "mechanism": mechanism.key,
                "mechanism_label": mechanism.label,
                "risk_type": mechanism.risk_type,
                "level_index": scenario.level_index,
                "level_code": scenario.level_code,
                "level_label": scenario.level_label,
                "mechanism_value": scenario.value,
                "mechanism_unit": scenario.unit,
                "intermittent_delay_mean_extra_days": (
                    scenario.value
                    if scenario.mechanism_key == "intermittent_delay"
                    else ""
                ),
                "evidence_class": "exploratory_stress_hypothesis",
                "interpretation": (
                    "Non applicable: capacité physique non identifiable (plancher nul, "
                    "aucun pull observé); scénario non exécuté."
                    if scenario.is_not_applicable
                    else mechanism.evidence_note
                ),
            }
        )
    return rows


def incident_window(days: int) -> tuple[int, int]:
    if days <= 0:
        raise ValueError("days must be positive")
    start = min(INCIDENT_START_DAY, max(0, days - 1))
    end = min(days - 1, start + INCIDENT_DURATION_DAYS - 1)
    return start, end


def grouped_delay_windows(days: int) -> tuple[tuple[int, int], ...]:
    """Return four grouped windows covering about half the incident period."""

    start, end = incident_window(days)
    incident_days = end - start + 1
    boundaries = [
        start + int(round(index * incident_days / 8.0)) for index in range(9)
    ]
    windows: list[tuple[int, int]] = []
    for index in (0, 2, 4, 6):
        window_start = boundaries[index]
        stop_exclusive = boundaries[index + 1]
        if window_start < stop_exclusive:
            windows.append((window_start, stop_exclusive - 1))
    return tuple(windows)


def build_risk_event_rows(scenario: Scenario, days: int) -> list[dict[str, Any]]:
    """Build exact-lane risk rows without touching demand or service directly."""

    if scenario.is_campaign_baseline or scenario.is_baseline_alias:
        return []
    if days <= 0:
        raise ValueError("days must be positive")
    chain = CHAIN_BY_ID[scenario.chain_id]
    mechanism = MECHANISM_BY_KEY[scenario.mechanism_key]
    rows: list[dict[str, Any]] = []
    if scenario.mechanism_key == "intermittent_delay":
        mean_extra = scenario.value
        if mean_extra <= 0:
            return []
        for lane_index, lane in enumerate(chain.affected_lanes, 1):
            for window_index, (start_day, end_day) in enumerate(
                grouped_delay_windows(days), 1
            ):
                rows.append(
                    {
                        "event_id": (
                            f"{scenario.scenario_id}__lane{lane_index}__"
                            f"burst{window_index}"
                        ),
                        "risk_type": "lead_time_extra_days",
                        "supplier_id": lane.supplier_id,
                        "item_id": lane.item_id,
                        "dst_node_id": lane.dst_node_id,
                        "edge_id": "",
                        "start_day": start_day,
                        "end_day": end_day,
                        "multiplier": 2.0 * mean_extra,
                        "notes": (
                            "Retards irréguliers groupés post-J0; charge moyenne "
                            f"≈ +{mean_extra:g} j; indice de lissage "
                            "profil hypothétique, pas un CV/OTIF mesuré."
                        ),
                    }
                )
        return rows
    event_start, event_end = incident_window(days)
    for lane_index, lane in enumerate(chain.affected_lanes, 1):
        rows.append(
            {
                "event_id": f"{scenario.scenario_id}__lane{lane_index}",
                "risk_type": mechanism.risk_type,
                "supplier_id": lane.supplier_id,
                "item_id": lane.item_id,
                "dst_node_id": lane.dst_node_id,
                "edge_id": "",
                "start_day": event_start,
                "end_day": event_end,
                "multiplier": scenario.value,
                "notes": f"{mechanism.label}; niveau {scenario.level_label}.",
            }
        )
    return rows


def validate_graph_scope(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Ensure every stressed and healthy witness lane exists exactly once."""

    edges = list(graph.get("edges") or [])
    audit_rows: list[dict[str, Any]] = []
    for chain in CHAINS:
        affected_keys = {lane.key for lane in chain.affected_lanes}
        healthy_keys = {lane.key for lane in chain.healthy_lanes}
        if affected_keys & healthy_keys:
            raise ValueError(f"Healthy and affected lanes overlap for {chain.chain_id}")
        for role, lanes in (
            ("affected", chain.affected_lanes),
            ("healthy_witness", chain.healthy_lanes),
        ):
            for lane in lanes:
                matches = [
                    edge
                    for edge in edges
                    if str(edge.get("from") or "") == lane.supplier_id
                    and str(edge.get("to") or "") == lane.dst_node_id
                    and lane.item_id in {str(item) for item in (edge.get("items") or [])}
                ]
                if len(matches) != 1:
                    raise ValueError(
                        f"Graph scope mismatch for {lane.key}: expected 1 edge, "
                        f"found {len(matches)}"
                    )
                audit_rows.append(
                    {
                        "chain_id": chain.chain_id,
                        "role": role,
                        "supplier_id": lane.supplier_id,
                        "item_id": lane.item_id,
                        "dst_node_id": lane.dst_node_id,
                        "edge_id": str(matches[0].get("id") or ""),
                    }
                )
    return {
        "validated": True,
        "lane_count": len(audit_rows),
        "lanes": audit_rows,
    }


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ordered_fields(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(str(key))
                seen.add(str(key))
    return fields


def write_csv_atomic(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(fields or ordered_fields(rows))
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def engine_profile_args(path: Path) -> list[str]:
    payload = read_json(path)
    values = payload.get("args") if isinstance(payload, dict) else payload
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"Invalid engine profile: {path}")
    return list(values)


def build_prepared_physical_floor_rows(
    source_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Override only the two positive, identifiable supplier capacities.

    Zero tested floors in the corrected baseline calibration mean "not
    identified", not zero
    physical capacity.  They must therefore never be copied into the engine
    override file.
    """

    source_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for source in source_rows:
        supplier_id = str(source.get("supplier_id") or "").strip()
        item_id = str(source.get("item_id") or "").strip()
        if not supplier_id or not item_id:
            raise ValueError("Physical floor source has a row without supplier_id/item_id")
        pair = (supplier_id, item_id)
        if pair in source_by_pair:
            raise ValueError(f"Duplicate physical floor pair: {pair}")
        neutral = max(
            0.0, to_float(source.get("neutral_capacity_floor_qty_per_day"), 0.0)
        )
        tested_text = str(source.get("tested_capacity_floor_qty_per_day") or "").strip()
        physical = max(0.0, to_float(tested_text, neutral)) if tested_text else neutral
        source_by_pair[pair] = {
            "source": source,
            "neutral": neutral,
            "tested_text": tested_text,
            "physical": physical,
        }

    missing = sorted(PHYSICAL_CAPACITY_OVERRIDE_PAIRS - set(source_by_pair))
    if missing:
        raise ValueError(f"Physical floor source is missing target pairs: {missing}")

    prepared: list[dict[str, Any]] = []
    for pair in sorted(PHYSICAL_CAPACITY_OVERRIDE_PAIRS):
        values = source_by_pair[pair]
        source = values["source"]
        physical = float(values["physical"])
        if physical <= 0.0:
            raise ValueError(f"Target physical capacity floor must be positive: {pair}")
        prepared.append(
            {
                "supplier_id": pair[0],
                "item_id": pair[1],
                "dst_node_id": str(source.get("dst_node_id") or ""),
                "neutral_capacity_floor_qty_per_day": format(physical, ".12g"),
                "tested_capacity_floor_qty_per_day": format(physical, ".12g"),
                "effective_capacity_qty_per_day": format(physical, ".12g"),
                "applied_capacity_scale": "1",
                "capacity_floor_basis": (
                    "corrected_baseline_measured_peak_daily_pull_x2.5"
                ),
                "source_neutral_capacity_floor_qty_per_day": format(
                    float(values["neutral"]), ".12g"
                ),
                "source_tested_capacity_floor_qty_per_day": values["tested_text"],
            }
        )

    relevant: list[dict[str, Any]] = []
    for chain in CHAINS:
        for lane in (*chain.affected_lanes, *chain.healthy_lanes):
            pair = (lane.supplier_id, lane.item_id)
            if pair not in source_by_pair:
                raise ValueError(f"Physical floor audit source does not contain {pair}")
            relevant.append(
                {
                    "chain_id": chain.chain_id,
                    "supplier_id": lane.supplier_id,
                    "item_id": lane.item_id,
                    "dst_node_id": lane.dst_node_id,
                    "source_neutral_capacity_qty_per_day": source_by_pair[pair][
                        "neutral"
                    ],
                    "source_tested_capacity_qty_per_day": source_by_pair[pair][
                        "physical"
                    ],
                    "override_applied": pair in PHYSICAL_CAPACITY_OVERRIDE_PAIRS,
                }
            )
    chain_021081 = [
        item["source_tested_capacity_qty_per_day"]
        for item in relevant
        if item["chain_id"] == "021081_sdc1450_268967"
    ]
    if any(value > 1e-9 for value in chain_021081):
        raise ValueError(
            "021081 capacity became positive; revisit its non-applicable capacity design"
        )
    return prepared, {
        "policy": "two-pair positive physical-capacity override only",
        "stock_columns_included": False,
        "source_row_count": len(source_by_pair),
        "override_row_count": len(prepared),
        "override_pairs": [list(pair) for pair in sorted(PHYSICAL_CAPACITY_OVERRIDE_PAIRS)],
        "zero_or_unidentified_source_pairs_not_overridden": sum(
            values["physical"] <= 0.0 and pair not in PHYSICAL_CAPACITY_OVERRIDE_PAIRS
            for pair, values in source_by_pair.items()
        ),
        "tested_equals_neutral_all_rows": all(
            values_equal(
                to_float(row["tested_capacity_floor_qty_per_day"]),
                to_float(row["neutral_capacity_floor_qty_per_day"]),
            )
            for row in prepared
        ),
        "relevant_lanes": relevant,
        "limitations": (
            "Only 338929 and 344135 have positive functional floors in the "
            "corrected 720-day calibration. Unrelated pairs and all zero 021081 "
            "audit "
            "values remain governed by the reference graph; the baseline is re-audited."
        ),
    }


def physical_capacity_by_lane(
    prepared_rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], float]:
    by_pair = {
        (str(row.get("supplier_id")), str(row.get("item_id"))): to_float(
            row.get("tested_capacity_floor_qty_per_day")
        )
        for row in prepared_rows
    }
    return {
        lane.key: by_pair[(lane.supplier_id, lane.item_id)]
        for chain in CHAINS
        for lane in (*chain.affected_lanes, *chain.healthy_lanes)
        if (lane.supplier_id, lane.item_id) in by_pair
    }


def write_risk_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write an empty non-baseline risk file: {path}")
    write_csv_atomic(path, rows, RISK_CSV_FIELDS)


def compute_service_metrics(
    rows: Iterable[Mapping[str, Any]],
    *,
    client_node_id: str,
    products: Sequence[str],
    days: int,
) -> dict[str, dict[str, Any]]:
    """Compute horizon and temporary-disruption client service metrics."""

    grouped: dict[str, dict[str, Any]] = {
        product: {
            "demand_qty": 0.0,
            "served_qty": 0.0,
            "served_on_due_proxy_qty": 0.0,
            "starting_backlog_qty": 0.0,
            "backlog_by_day": defaultdict(float),
            "demand_by_day": defaultdict(float),
            "served_by_day": defaultdict(float),
            "on_due_by_day": defaultdict(float),
            "days_seen": set(),
        }
        for product in products
    }
    for row in rows:
        if str(row.get("node_id") or "") != client_node_id:
            continue
        item = str(row.get("item_id") or "").replace("item:", "")
        if item not in grouped:
            continue
        day = to_int(row.get("day"), -1)
        if day < 0 or day >= days:
            continue
        demand = max(0.0, to_float(row.get("demand_qty")))
        served = max(0.0, to_float(row.get("served_qty")))
        required = max(demand, to_float(row.get("required_with_backlog_qty"), demand))
        starting_backlog = max(0.0, required - demand)
        backlog = max(0.0, to_float(row.get("backlog_end_qty")))
        stats = grouped[item]
        stats["demand_qty"] += demand
        stats["served_qty"] += served
        stats["served_on_due_proxy_qty"] += min(
            demand, max(0.0, served - starting_backlog)
        )
        if day == 0:
            stats["starting_backlog_qty"] += starting_backlog
        stats["backlog_by_day"][day] += backlog
        stats["demand_by_day"][day] += demand
        stats["served_by_day"][day] += served
        stats["on_due_by_day"][day] += min(
            demand, max(0.0, served - starting_backlog)
        )
        stats["days_seen"].add(day)
    result: dict[str, dict[str, Any]] = {}
    expected_days = set(range(days))
    for product, raw in grouped.items():
        demand = float(raw["demand_qty"])
        backlog_by_day = dict(raw["backlog_by_day"])
        backlog_values = [backlog_by_day.get(day, 0.0) for day in range(days)]
        demand_values = [raw["demand_by_day"].get(day, 0.0) for day in range(days)]
        served_values = [raw["served_by_day"].get(day, 0.0) for day in range(days)]
        on_due_values = [raw["on_due_by_day"].get(day, 0.0) for day in range(days)]
        days_seen = set(raw["days_seen"])
        first_backlog_day = next(
            (day for day, value in enumerate(backlog_values) if value > 1e-9), -1
        )
        backlog_peak_day = (
            max(range(days), key=lambda day: (backlog_values[day], -day))
            if backlog_values and max(backlog_values) > 1e-9
            else -1
        )
        _incident_start, incident_end = incident_window(days)
        recovery_day = -1
        for candidate in range(incident_end + 1, days):
            stop = min(days, candidate + RECOVERY_STABILITY_DAYS)
            if stop - candidate < min(RECOVERY_STABILITY_DAYS, days - incident_end - 1):
                continue
            if all(value <= 1e-9 for value in backlog_values[candidate:stop]):
                recovery_day = candidate
                break
        rolling_window = min(28, days)
        worst_fill = 1.0
        worst_fill_start = 0
        worst_due = 1.0
        worst_due_start = 0
        for start in range(0, days - rolling_window + 1):
            stop = start + rolling_window
            window_demand = sum(demand_values[start:stop])
            if window_demand <= 1e-12:
                continue
            window_fill = min(1.0, sum(served_values[start:stop]) / window_demand)
            window_due = min(1.0, sum(on_due_values[start:stop]) / window_demand)
            if (window_fill, start) < (worst_fill, worst_fill_start):
                worst_fill, worst_fill_start = window_fill, start
            if (window_due, start) < (worst_due, worst_due_start):
                worst_due, worst_due_start = window_due, start
        incident_start, incident_end = incident_window(days)
        ending_backlog = backlog_values[-1] if backlog_values else 0.0
        horizon_service = (
            min(1.0, max(0.0, demand - ending_backlog) / demand)
            if demand
            else 1.0
        )
        result[product] = {
            "demand_qty": demand,
            "served_qty": float(raw["served_qty"]),
            "starting_backlog_qty": float(raw["starting_backlog_qty"]),
            "fill_rate": horizon_service,
            "on_due_volume_proxy": (
                float(raw["served_on_due_proxy_qty"]) / demand if demand else 1.0
            ),
            "backlog_qty_days": sum(backlog_values),
            "backlog_days": sum(value > 1e-9 for value in backlog_values),
            "backlog_max_qty": max(backlog_values) if backlog_values else 0.0,
            "backlog_end_qty": ending_backlog,
            "first_backlog_day": first_backlog_day,
            "backlog_peak_day": backlog_peak_day,
            "incident_backlog_qty_days": sum(
                backlog_values[incident_start : incident_end + 1]
            ),
            "post_incident_backlog_qty_days": sum(backlog_values[incident_end + 1 :]),
            "recovery_day_after_incident": recovery_day,
            "recovered_within_horizon": recovery_day >= 0,
            "worst_rolling_28d_fill_catchup_contaminated": worst_fill,
            "worst_rolling_28d_fill_catchup_start_day": worst_fill_start,
            "worst_rolling_28d_on_due_proxy": worst_due,
            "worst_rolling_28d_on_due_start_day": worst_due_start,
            "horizon_day_count": len(days_seen),
            "horizon_complete": days_seen == expected_days,
        }
    return result


def _lane_matches(row: Mapping[str, Any], lane: Lane, *, shipment: bool) -> bool:
    source_field = "src_node_id" if shipment else "supplier_id"
    return (
        str(row.get(source_field) or "") == lane.supplier_id
        and str(row.get("item_id") or "") == lane.item_id
        and str(row.get("dst_node_id") or "") == lane.dst_node_id
    )


def compute_supplier_shipment_metrics(
    rows: Iterable[Mapping[str, Any]],
    *,
    lanes: Sequence[Lane],
    days: int,
) -> dict[str, float]:
    matched: list[Mapping[str, Any]] = []
    for row in rows:
        day = to_int(row.get("day"), -1)
        if 0 <= day < days and any(
            _lane_matches(row, lane, shipment=True) for lane in lanes
        ):
            matched.append(row)
    incident_start, incident_end = incident_window(days)
    incident_rows = [
        row
        for row in matched
        if incident_start <= to_int(row.get("day"), -1) <= incident_end
    ]
    max_reference_lead = max((lane.planned_lead_days for lane in lanes), default=0.0)
    extended_end = min(days - 1, incident_end + int(math.ceil(max_reference_lead)))
    incident_plus_lead_rows = [
        row
        for row in matched
        if incident_start <= to_int(row.get("day"), -1) <= extended_end
    ]
    shipped = sum(max(0.0, to_float(row.get("shipped_qty"))) for row in matched)
    pulled = sum(max(0.0, to_float(row.get("pulled_qty"))) for row in matched)
    weighted_lead = sum(
        max(0.0, to_float(row.get("shipped_qty")))
        * max(0.0, to_float(row.get("lead_days")))
        for row in matched
    )
    weighted_reliability = sum(
        max(0.0, to_float(row.get("shipped_qty")))
        * max(0.0, to_float(row.get("reliability"), 1.0))
        for row in matched
    )
    on_due_qty = 0.0
    for row in matched:
        lane = next(
            (candidate for candidate in lanes if _lane_matches(row, candidate, shipment=True)),
            None,
        )
        if lane is not None and to_float(row.get("lead_days"), math.inf) <= lane.planned_lead_days + 1e-9:
            on_due_qty += max(0.0, to_float(row.get("shipped_qty")))
    return {
        "shipment_rows": float(len(matched)),
        "shipped_qty": shipped,
        "pulled_qty": pulled,
        "weighted_mean_lead_days": weighted_lead / shipped if shipped else 0.0,
        "max_lead_days": max(
            (max(0.0, to_float(row.get("lead_days"))) for row in matched),
            default=0.0,
        ),
        "weighted_reliability": (
            weighted_reliability / shipped if shipped else 1.0
        ),
        "service_horizon": min(1.0, shipped / pulled) if pulled else 1.0,
        "on_due_date_proxy": min(1.0, on_due_qty / pulled) if pulled else 1.0,
        "incident_shipped_qty": sum(
            max(0.0, to_float(row.get("shipped_qty"))) for row in incident_rows
        ),
        "incident_pulled_qty": sum(
            max(0.0, to_float(row.get("pulled_qty"))) for row in incident_rows
        ),
        "incident_plus_lead_shipped_qty": sum(
            max(0.0, to_float(row.get("shipped_qty")))
            for row in incident_plus_lead_rows
        ),
        "incident_plus_lead_pulled_qty": sum(
            max(0.0, to_float(row.get("pulled_qty")))
            for row in incident_plus_lead_rows
        ),
        "arriving_after_horizon_qty": sum(
            max(0.0, to_float(row.get("shipped_qty")))
            for row in matched
            if to_int(row.get("arrival_day"), -1) >= days
        ),
    }


def compute_supplier_capacity_metrics(
    rows: Iterable[Mapping[str, Any]],
    *,
    lanes: Sequence[Lane],
    days: int,
    incident_start_day: int,
    incident_end_day: int,
) -> dict[str, float]:
    pairs = {(lane.supplier_id, lane.item_id) for lane in lanes}
    matched = [
        row
        for row in rows
        if 0 <= to_int(row.get("day"), -1) < days
        and (str(row.get("node_id") or ""), str(row.get("item_id") or ""))
        in pairs
    ]
    incident = [
        row
        for row in matched
        if incident_start_day <= to_int(row.get("day"), -1) <= incident_end_day
    ]
    binding_rows = [
        row
        for row in incident
        if to_float(row.get("used_qty")) > 1e-9
        and to_float(row.get("remaining_capacity_qty")) <= 1e-6
    ]
    capacities = [to_float(row.get("capacity_qty_per_day")) for row in matched]
    incident_capacities = [
        to_float(row.get("capacity_qty_per_day")) for row in incident
    ]
    return {
        "capacity_rows": float(len(matched)),
        "capacity_min_qty_per_day": min(capacities) if capacities else 0.0,
        "capacity_max_qty_per_day": max(capacities) if capacities else 0.0,
        "incident_capacity_min_qty_per_day": (
            min(incident_capacities) if incident_capacities else 0.0
        ),
        "incident_capacity_max_qty_per_day": (
            max(incident_capacities) if incident_capacities else 0.0
        ),
        "incident_capacity_binding_days": float(
            len({to_int(row.get("day")) for row in binding_rows})
        ),
        "incident_capacity_binding_rows": float(len(binding_rows)),
        "incident_capacity_peak_utilization": max(
            (to_float(row.get("utilization")) for row in incident), default=0.0
        ),
        "incident_capacity_used_qty": sum(
            max(0.0, to_float(row.get("used_qty"))) for row in incident
        ),
    }


def compute_risk_application_metrics(
    rows: Iterable[Mapping[str, Any]],
    *,
    affected_lanes: Sequence[Lane],
    healthy_lanes: Sequence[Lane],
    days: int,
) -> dict[str, int]:
    affected_rows = 0
    healthy_rows = 0
    event_ids: set[str] = set()
    for row in rows:
        day = to_int(row.get("day"), -1)
        if not 0 <= day < days:
            continue
        if any(_lane_matches(row, lane, shipment=False) for lane in affected_lanes):
            affected_rows += 1
            event_ids.update(
                part.strip()
                for part in str(row.get("event_ids") or "").split("|")
                if part.strip()
            )
        if any(_lane_matches(row, lane, shipment=False) for lane in healthy_lanes):
            healthy_rows += 1
    return {
        "risk_applied_rows": affected_rows,
        "risk_applied_event_ids": len(event_ids),
        "healthy_risk_applied_rows": healthy_rows,
    }


def _all_affected_lanes() -> tuple[Lane, ...]:
    unique: dict[tuple[str, str, str], Lane] = {}
    for chain in CHAINS:
        for lane in chain.affected_lanes:
            unique[lane.key] = lane
    return tuple(unique[key] for key in sorted(unique))


def extract_case_metrics(
    *,
    case_dir: Path,
    scenario: Scenario,
    seed: int,
    stage: str,
    status: str,
    days: int,
    configured_event_count: int,
    physical_capacity_by_lane_map: Mapping[tuple[str, str, str], float],
) -> dict[str, Any]:
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    service_path = case_dir / "data" / "production_demand_service_daily.csv"
    shipment_path = case_dir / "data" / "production_supplier_shipments_daily.csv"
    capacity_path = case_dir / "data" / "production_supplier_capacity_daily.csv"
    risk_path = case_dir / "data" / "supplier_risk_events_applied_daily.csv"
    if not summary_path.exists() or not service_path.exists():
        raise CaseValidationError(
            f"Missing summary or service data for {scenario.scenario_id}/seed_{seed}"
        )
    summary = read_json(summary_path)
    service = compute_service_metrics(
        read_csv_rows(service_path),
        client_node_id="C-XXXXX",
        products=PRODUCTS,
        days=days,
    )
    if scenario.is_campaign_baseline:
        affected_lanes = _all_affected_lanes()
        healthy_lanes: tuple[Lane, ...] = ()
    else:
        chain = CHAIN_BY_ID[scenario.chain_id]
        affected_lanes = chain.affected_lanes
        healthy_lanes = chain.healthy_lanes
    shipment_metrics = compute_supplier_shipment_metrics(
        read_csv_rows(shipment_path),
        lanes=affected_lanes,
        days=days,
    )
    healthy_shipment_metrics = compute_supplier_shipment_metrics(
        read_csv_rows(shipment_path),
        lanes=healthy_lanes,
        days=days,
    )
    risk_metrics = compute_risk_application_metrics(
        read_csv_rows(risk_path),
        affected_lanes=affected_lanes,
        healthy_lanes=healthy_lanes,
        days=days,
    )
    event_start, event_end = incident_window(days)
    capacity_rows = read_csv_rows(capacity_path)
    capacity_metrics = compute_supplier_capacity_metrics(
        capacity_rows,
        lanes=affected_lanes,
        days=days,
        incident_start_day=event_start,
        incident_end_day=event_end,
    )
    policy = summary.get("policy") or {}
    supplier_risk = policy.get("supplier_risk") or {}
    supplier_state_dependent_risk = (
        policy.get("supplier_state_dependent_risk") or {}
    )
    warmup_audit = policy.get("warmup_boundary_audit") or {}
    initialization_policy = policy.get("initialization_policy") or {}
    economic_policy = policy.get("economic_policy") or {}
    opening_stock_scale = policy.get("opening_observed_stock_scale") or {}
    kpis = summary.get("kpis") or {}
    row: dict[str, Any] = {
        "stage": stage,
        "scenario_id": scenario.scenario_id,
        "execution_scenario_id": scenario.execution_scenario_id,
        "chain_id": scenario.chain_id,
        "mechanism": scenario.mechanism_key,
        "level_index": scenario.level_index,
        "level_code": scenario.level_code,
        "level_label": scenario.level_label,
        "mechanism_value": scenario.value,
        "mechanism_unit": scenario.unit,
        "target_product_id": scenario.target_product_id,
        "client_node_id": scenario.client_node_id,
        "seed": seed,
        "status": status,
        "valid": False,
        "validation_errors": "",
        "run_dir": str(case_dir.resolve()),
        "input_sha256": str(summary.get("input_sha256") or ""),
        "j0_state_sha256": str(warmup_audit.get("core_state_sha256") or ""),
        "summary_sim_days": to_int(summary.get("sim_days"), -1),
        "summary_timeline_days": to_int(summary.get("timeline_days"), -1),
        "summary_warmup_days": to_int(summary.get("warmup_days"), -1),
        "summary_total_simulated_timeline_days": to_int(
            summary.get("total_simulated_timeline_days"), -1
        ),
        "resolved_mrp_demand_signal_smoothing_days": to_int(
            initialization_policy.get("mrp_demand_signal_smoothing_days"), -1
        ),
        "resolved_mrp_static_requirement_pairs": ";".join(
            sorted(initialization_policy.get("mrp_static_requirement_pairs") or [])
        ),
        "resolved_mrp_dynamic_requirement_pairs": ";".join(
            sorted(initialization_policy.get("mrp_dynamic_requirement_pairs") or [])
        ),
        "resolved_mrp_smoothed_cover_requirement_pairs": ";".join(
            sorted(
                initialization_policy.get(
                    "mrp_smoothed_cover_requirement_pairs"
                )
                or []
            )
        ),
        "resolved_mrp_multisource_policy": str(
            policy.get("mrp_multisource_policy") or ""
        ),
        "resolved_initial_state_scale": to_float(
            initialization_policy.get("state_scale"), math.nan
        ),
        "resolved_opening_observed_stock_scale_enabled": as_bool(
            opening_stock_scale.get("enabled")
        ),
        "resolved_opening_observed_stock_scale_factor": to_float(
            opening_stock_scale.get("factor"), math.nan
        ),
        "resolved_opening_observed_stock_scale_source_csv": str(
            opening_stock_scale.get("source_csv") or ""
        ),
        "resolved_warmup_profile_mode": str(
            policy.get("warmup_profile_mode") or ""
        ),
        "resolved_restore_opening_stock_after_warmup": as_bool(
            initialization_policy.get("restore_opening_stock_after_warmup")
        ),
        "resolved_seed_open_orders_from_january_snapshot": as_bool(
            initialization_policy.get("seed_open_orders_from_january_snapshot")
        ),
        "resolved_external_procurement_enabled": as_bool(
            economic_policy.get("external_procurement_enabled")
        ),
        "resolved_external_procurement_proactive_replenishment": as_bool(
            economic_policy.get("external_procurement_proactive_replenishment")
        ),
        "resolved_external_procurement_lead_mode": str(
            economic_policy.get("external_procurement_lead_mode") or ""
        ),
        "resolved_external_procurement_capacity_mode": str(
            economic_policy.get("external_procurement_capacity_mode") or ""
        ),
        "resolved_external_procurement_nominal_capacity_scale": to_float(
            economic_policy.get("external_procurement_nominal_capacity_scale"),
            math.nan,
        ),
        "resolved_supplier_risk_loss_gross_up": as_bool(
            economic_policy.get("supplier_risk_loss_gross_up", True)
        ),
        "resolved_supplier_state_dependent_risks_enabled": as_bool(
            supplier_state_dependent_risk.get("enabled")
        ),
        "incident_start_day": event_start,
        "incident_end_day": event_end,
        "configured_event_count": configured_event_count,
        "loaded_event_count": to_int(supplier_risk.get("event_count"), 0),
        **risk_metrics,
        "total_cost": to_float(kpis.get("total_cost")),
        "total_transport_cost": to_float(kpis.get("total_transport_cost")),
        "total_purchase_cost": to_float(kpis.get("total_purchase_cost")),
        "total_production_cost": to_float(kpis.get("total_production_cost")),
        "total_holding_cost": to_float(kpis.get("total_holding_cost")),
        "total_inventory_risk_cost": to_float(kpis.get("total_inventory_risk_cost")),
        "total_external_procurement_cost": to_float(
            kpis.get("total_external_procurement_cost")
        ),
        "total_supplier_capacity_binding_qty": to_float(
            kpis.get("total_supplier_capacity_binding_qty")
        ),
    }
    for key, value in shipment_metrics.items():
        row[f"supplier_{key}"] = value
    for key, value in healthy_shipment_metrics.items():
        row[f"healthy_supplier_{key}"] = value
    for key, value in capacity_metrics.items():
        row[f"supplier_{key}"] = value
    for product in PRODUCTS:
        stats = service[product]
        for key, value in stats.items():
            row[f"{key}_{product}"] = value
    if scenario.target_product_id in PRODUCTS:
        target = service[scenario.target_product_id]
    else:
        target = min(service.values(), key=lambda item: item["fill_rate"])
    for key in (
        "demand_qty",
        "served_qty",
        "starting_backlog_qty",
        "fill_rate",
        "on_due_volume_proxy",
        "backlog_qty_days",
        "backlog_days",
        "backlog_max_qty",
        "backlog_end_qty",
        "first_backlog_day",
        "backlog_peak_day",
        "incident_backlog_qty_days",
        "post_incident_backlog_qty_days",
        "recovery_day_after_incident",
        "recovered_within_horizon",
        "worst_rolling_28d_fill_catchup_contaminated",
        "worst_rolling_28d_fill_catchup_start_day",
        "worst_rolling_28d_on_due_proxy",
        "worst_rolling_28d_on_due_start_day",
    ):
        row[f"target_{key}"] = target[key]
    row["supplier_service_horizon"] = shipment_metrics["service_horizon"]
    row["supplier_on_due_date_proxy"] = shipment_metrics["on_due_date_proxy"]
    row["product_service_horizon"] = target["fill_rate"]
    row["product_on_due_date_proxy"] = target["on_due_volume_proxy"]
    expected_capacities = [
        physical_capacity_by_lane_map[lane.key]
        for lane in affected_lanes
        if physical_capacity_by_lane_map.get(lane.key, 0.0) > 0.0
    ]
    expected_incident = (
        min(expected_capacities) * scenario.value
        if expected_capacities
        and scenario.mechanism_key in {"capacity", "availability"}
        else (min(expected_capacities) if expected_capacities else 0.0)
    )
    row["expected_physical_capacity_qty_per_day"] = (
        min(expected_capacities) if expected_capacities else 0.0
    )
    row["expected_incident_capacity_qty_per_day"] = expected_incident
    if scenario.is_campaign_baseline:
        floor_match = True
        for lane in _all_affected_lanes():
            expected = physical_capacity_by_lane_map.get(lane.key, 0.0)
            if expected <= 0.0:
                continue
            observed = {
                to_float(item.get("capacity_qty_per_day"))
                for item in capacity_rows
                if str(item.get("node_id") or "") == lane.supplier_id
                and str(item.get("item_id") or "") == lane.item_id
                and 0 <= to_int(item.get("day"), -1) < days
            }
            if not observed or any(not values_equal(value, expected) for value in observed):
                floor_match = False
                break
        row["applied_physical_capacity_matches_expected"] = floor_match
    else:
        row["applied_physical_capacity_matches_expected"] = (
            values_equal(
                capacity_metrics["incident_capacity_min_qty_per_day"],
                expected_incident,
            )
            if expected_capacities
            else True
        )
    if scenario.is_campaign_baseline:
        for chain in CHAINS:
            chain_shipments = compute_supplier_shipment_metrics(
                read_csv_rows(shipment_path), lanes=chain.affected_lanes, days=days
            )
            chain_capacity = compute_supplier_capacity_metrics(
                capacity_rows,
                lanes=chain.affected_lanes,
                days=days,
                incident_start_day=event_start,
                incident_end_day=event_end,
            )
            prefix = f"baseline_chain__{chain.chain_id}__"
            for key, value in chain_shipments.items():
                row[f"{prefix}{key}"] = value
            for key, value in chain_capacity.items():
                row[f"{prefix}{key}"] = value
    row["all_product_horizons_complete"] = all(
        bool(service[product]["horizon_complete"]) for product in PRODUCTS
    )
    return row


def attach_paired_baseline_metrics(
    row: dict[str, Any],
    *,
    scenario: Scenario,
    baseline_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Attach same-chain flow denominators from the same-seed baseline."""

    quantitative = to_float(row.get("supplier_service_horizon"), 1.0)
    lead_proxy = to_float(row.get("supplier_on_due_date_proxy"), 1.0)
    if scenario.is_campaign_baseline:
        row["paired_baseline_supplier_shipped_qty"] = to_float(
            row.get("supplier_shipped_qty")
        )
        row["supplier_flow_coverage_vs_paired_baseline"] = 1.0
        row["supplier_incident_flow_coverage_vs_paired_baseline"] = 1.0
        row["supplier_quantitative_conformity_proxy"] = quantitative
        row["supplier_lead_on_due_proxy"] = lead_proxy
        return row
    if baseline_row is None:
        return row
    prefix = f"baseline_chain__{scenario.chain_id}__"
    baseline_shipped = to_float(baseline_row.get(f"{prefix}shipped_qty"))
    baseline_pulled = to_float(baseline_row.get(f"{prefix}pulled_qty"))
    baseline_on_due = to_float(baseline_row.get(f"{prefix}on_due_date_proxy"), 1.0)
    baseline_incident_shipped = to_float(
        baseline_row.get(f"{prefix}incident_shipped_qty")
    )
    baseline_incident_pulled = to_float(
        baseline_row.get(f"{prefix}incident_pulled_qty")
    )
    flow_coverage = (
        min(1.0, max(0.0, to_float(row.get("supplier_shipped_qty"))) / baseline_shipped)
        if baseline_shipped > 1e-12
        else 1.0
    )
    row["paired_baseline_supplier_shipped_qty"] = baseline_shipped
    row["paired_baseline_supplier_pulled_qty"] = baseline_pulled
    row["paired_baseline_supplier_on_due_date_proxy"] = baseline_on_due
    row["supplier_flow_coverage_vs_paired_baseline"] = flow_coverage
    incident_flow_coverage = (
        min(
            1.0,
            max(0.0, to_float(row.get("supplier_incident_shipped_qty")))
            / baseline_incident_shipped,
        )
        if baseline_incident_shipped > 1e-12
        else 1.0
    )
    row["paired_baseline_supplier_incident_shipped_qty"] = baseline_incident_shipped
    row["paired_baseline_supplier_incident_pulled_qty"] = baseline_incident_pulled
    row["paired_baseline_supplier_incident_flow_exercised"] = (
        baseline_incident_pulled > 1e-12
        and baseline_incident_shipped > 1e-12
    )
    row["paired_baseline_supplier_incident_flow_status"] = (
        "positive_baseline_incident_flow"
        if row["paired_baseline_supplier_incident_flow_exercised"]
        else "zero_baseline_incident_flow"
    )
    row["supplier_incident_flow_coverage_vs_paired_baseline"] = incident_flow_coverage
    row["supplier_quantitative_conformity_proxy"] = quantitative
    row["supplier_lead_on_due_proxy"] = lead_proxy
    # Dashboard-compatible aliases.  The service alias deliberately combines
    # quantitative conformity with flow coverage so capacity-constrained need
    # cannot disappear from the pulled-quantity denominator.
    row["supplier_service_horizon"] = min(quantitative, incident_flow_coverage)
    row["supplier_on_due_date_proxy"] = min(lead_proxy, incident_flow_coverage)
    product = scenario.target_product_id
    baseline_product_service = to_float(baseline_row.get(f"fill_rate_{product}"), 1.0)
    baseline_product_on_due = to_float(
        baseline_row.get(f"on_due_volume_proxy_{product}"), 1.0
    )
    baseline_backlog_qty_days = to_float(
        baseline_row.get(f"backlog_qty_days_{product}")
    )
    baseline_worst_rolling_on_due = to_float(
        baseline_row.get(f"worst_rolling_28d_on_due_proxy_{product}"), 1.0
    )
    row["paired_baseline_product_service_horizon"] = baseline_product_service
    row["paired_baseline_product_on_due_date_proxy"] = baseline_product_on_due
    row["paired_baseline_target_backlog_qty_days"] = baseline_backlog_qty_days
    row["paired_baseline_target_worst_rolling_28d_on_due_proxy"] = (
        baseline_worst_rolling_on_due
    )
    row["incremental_target_backlog_qty_days"] = (
        to_float(row.get("target_backlog_qty_days")) - baseline_backlog_qty_days
    )
    row["target_on_due_date_proxy_delta_vs_paired_baseline"] = (
        to_float(row.get("product_on_due_date_proxy"), 1.0) - baseline_product_on_due
    )
    row["target_worst_rolling_28d_on_due_delta_vs_paired_baseline"] = (
        to_float(row.get("target_worst_rolling_28d_on_due_proxy"), 1.0)
        - baseline_worst_rolling_on_due
    )
    return row


def validation_errors(
    row: Mapping[str, Any],
    *,
    scenario: Scenario,
    days: int,
    baseline_row: Mapping[str, Any] | None,
) -> list[str]:
    """Return every comparability error; callers must not silently continue."""

    errors: list[str] = []
    if to_int(row.get("summary_sim_days"), -1) != days:
        errors.append("summary_sim_days differs from requested horizon")
    warmup_days = to_int(row.get("summary_warmup_days"), -1)
    timeline_days = to_int(row.get("summary_timeline_days"), -1)
    total_timeline_days = to_int(
        row.get("summary_total_simulated_timeline_days"), -1
    )
    if warmup_days != WARMUP_DAYS:
        errors.append("resolved warm-up differs from the 240-day protocol")
    if timeline_days != days:
        errors.append("measured timeline_days differs from requested horizon")
    if total_timeline_days != days + WARMUP_DAYS:
        errors.append("total simulated timeline is not measured days plus warm-up")
    if to_int(row.get("resolved_mrp_demand_signal_smoothing_days"), -1) != 7:
        errors.append("resolved MRP demand smoothing differs from seven days")
    static_pairs = {
        value
        for value in str(
            row.get("resolved_mrp_static_requirement_pairs") or ""
        ).split(";")
        if value
    }
    dynamic_pairs = {
        value
        for value in str(
            row.get("resolved_mrp_dynamic_requirement_pairs") or ""
        ).split(";")
        if value
    }
    if static_pairs & DYNAMIC_MRP_REQUIREMENT_PAIRS:
        errors.append("a studied supplier pair still uses a forced static MRP requirement")
    if dynamic_pairs != DYNAMIC_MRP_REQUIREMENT_PAIRS:
        errors.append("targeted dynamic MRP requirement pairs differ from protocol")
    smoothed_cover_pairs = {
        value
        for value in str(
            row.get("resolved_mrp_smoothed_cover_requirement_pairs") or ""
        ).split(";")
        if value
    }
    if smoothed_cover_pairs != SMOOTHED_COVER_REQUIREMENT_PAIRS:
        errors.append("smoothed lead-cover pairs differ from protocol")
    if str(row.get("resolved_mrp_multisource_policy") or "") != "legacy":
        errors.append("resolved multisource policy differs from legacy")
    if not values_equal(to_float(row.get("resolved_initial_state_scale"), math.nan), 0.1):
        errors.append("resolved initial-state scale differs from 0.1")
    if not as_bool(row.get("resolved_opening_observed_stock_scale_enabled")):
        errors.append("observed opening-stock scale is not explicitly enabled")
    if not values_equal(
        to_float(row.get("resolved_opening_observed_stock_scale_factor"), math.nan),
        1.0,
    ):
        errors.append("observed opening-stock scale differs from one")
    if str(row.get("resolved_opening_observed_stock_scale_source_csv") or ""):
        errors.append("an opening-stock scale CSV unexpectedly mutates the baseline")
    if str(row.get("resolved_warmup_profile_mode") or "") != "preperiod":
        errors.append("resolved warm-up profile mode differs from preperiod")
    if as_bool(row.get("resolved_restore_opening_stock_after_warmup")):
        errors.append("opening stock was restored after warm-up")
    if as_bool(row.get("resolved_seed_open_orders_from_january_snapshot")):
        errors.append("January snapshot open orders were seeded")
    if not as_bool(row.get("resolved_external_procurement_enabled")):
        errors.append("external procurement is not enabled")
    if not as_bool(
        row.get("resolved_external_procurement_proactive_replenishment")
    ):
        errors.append("normal proactive supplier replenishment is not enabled")
    if str(row.get("resolved_external_procurement_lead_mode") or "") != "supplier_material":
        errors.append("external procurement lead mode differs from supplier material")
    if str(row.get("resolved_external_procurement_capacity_mode") or "") != "supplier_nominal":
        errors.append("external procurement capacity mode differs from supplier nominal")
    if not values_equal(
        to_float(
            row.get("resolved_external_procurement_nominal_capacity_scale"),
            math.nan,
        ),
        1.0,
    ):
        errors.append("external procurement nominal capacity scale differs from one")
    if as_bool(row.get("resolved_supplier_risk_loss_gross_up")):
        errors.append("temporary supplier-risk losses are still perfectly grossed up")
    if as_bool(row.get("resolved_supplier_state_dependent_risks_enabled")):
        errors.append("supplier state-dependent risks are not disabled")
    if not as_bool(row.get("all_product_horizons_complete")):
        errors.append("daily client service horizon is incomplete")
    if not str(row.get("j0_state_sha256") or ""):
        errors.append("missing J0 core-state SHA-256 audit")
    if not str(row.get("input_sha256") or ""):
        errors.append("missing input graph SHA-256")
    if not as_bool(row.get("applied_physical_capacity_matches_expected")):
        errors.append("applied supplier capacity differs from prepared physical floor")
    if scenario.is_campaign_baseline:
        for product in PRODUCTS:
            horizon_service = to_float(row.get(f"fill_rate_{product}"), math.nan)
            on_due_service = to_float(
                row.get(f"on_due_volume_proxy_{product}"), math.nan
            )
            if not math.isfinite(horizon_service) or horizon_service < BASELINE_MIN_SERVICE:
                errors.append(
                    f"baseline product {product} horizon service is below "
                    f"{BASELINE_MIN_SERVICE:.0%}"
                )
            if not math.isfinite(on_due_service) or on_due_service < BASELINE_MIN_SERVICE:
                errors.append(
                    f"baseline product {product} on-due proxy is below "
                    f"{BASELINE_MIN_SERVICE:.0%}"
                )
        return errors
    if scenario.is_baseline_alias:
        errors.append("baseline alias must not be executed")
        return errors
    if to_int(row.get("configured_event_count"), 0) <= 0:
        errors.append("non-baseline scenario has no configured risk event")
    if to_int(row.get("loaded_event_count"), 0) <= 0:
        errors.append("engine did not load the non-baseline risk events")
    if to_int(row.get("risk_applied_rows"), 0) <= 0:
        errors.append("non-baseline risk produced no applied event row")
    if to_int(row.get("healthy_risk_applied_rows"), 0) != 0:
        errors.append("healthy multisource witness received a risk event")
    if baseline_row is None:
        errors.append("missing same-seed baseline for paired validation")
        return errors
    if str(row.get("j0_state_sha256") or "") != str(
        baseline_row.get("j0_state_sha256") or ""
    ):
        errors.append("J0 core-state SHA-256 differs from same-seed baseline")
    if str(row.get("input_sha256") or "") != str(
        baseline_row.get("input_sha256") or ""
    ):
        errors.append("input graph SHA-256 differs from baseline")
    # Do not require a configured degradation to reduce flow or service.  A
    # correctly applied stress can legitimately be absorbed by spare capacity;
    # that no-effect region is one of the sensitivity campaign's results.
    return errors


def validate_metric_row(
    row: dict[str, Any],
    *,
    scenario: Scenario,
    days: int,
    baseline_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    errors = validation_errors(
        row,
        scenario=scenario,
        days=days,
        baseline_row=baseline_row,
    )
    row["valid"] = not errors
    row["validation_errors"] = " | ".join(errors)
    if errors:
        raise CaseValidationError(
            f"Invalid case {scenario.scenario_id}/seed_{row.get('seed')}: "
            + "; ".join(errors)
        )
    return row


def retention_targets(case_dir: Path) -> tuple[Path, ...]:
    if not case_dir.exists():
        return ()
    return tuple(
        child
        for child in case_dir.iterdir()
        if child.is_dir() and child.name in RETENTION_DIRECTORY_ALLOWLIST
    )


def prune_case_artifacts(case_dir: Path) -> list[str]:
    """Delete only generated bulky directories; keep summaries/reports/logs."""

    removed: list[str] = []
    resolved_case = case_dir.resolve()
    for target in retention_targets(case_dir):
        resolved_target = target.resolve()
        if target.name not in RETENTION_DIRECTORY_ALLOWLIST:
            raise RuntimeError(f"Unsafe retention target: {target}")
        if resolved_target.parent != resolved_case:
            raise RuntimeError(f"Retention target escaped case directory: {target}")
        shutil.rmtree(resolved_target)
        removed.append(target.name)
    return sorted(removed)


def percentile(values: Sequence[float], quantile: float) -> float:
    cleaned = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not cleaned:
        return math.nan
    if len(cleaned) == 1:
        return cleaned[0]
    q = min(1.0, max(0.0, float(quantile)))
    position = q * (len(cleaned) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return cleaned[lower]
    weight = position - lower
    return cleaned[lower] * (1.0 - weight) + cleaned[upper] * weight


def _mean(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = [to_float(row.get(field), math.nan) for row in rows]
    clean = [value for value in values if math.isfinite(value)]
    return sum(clean) / len(clean) if clean else math.nan


def _aggregate_for_selection(
    rows: Sequence[Mapping[str, Any]], scenario: Scenario
) -> dict[str, float]:
    relevant = [row for row in rows if str(row.get("scenario_id")) == scenario.scenario_id]
    return {
        "on_due_mean": _mean(relevant, "product_on_due_date_proxy"),
        "on_due_p05": percentile(
            [
                to_float(row.get("product_on_due_date_proxy"), math.nan)
                for row in relevant
            ],
            0.05,
        ),
        "incremental_backlog_qty_days_mean": _mean(
            relevant, "incremental_target_backlog_qty_days"
        ),
        "worst_rolling_on_due_mean": _mean(
            relevant, "target_worst_rolling_28d_on_due_proxy"
        ),
        "recovered_fraction": _mean(relevant, "target_recovered_within_horizon"),
        "recovery_day_mean": _mean(relevant, "target_recovery_day_after_incident"),
        "fill_mean": _mean(relevant, "product_service_horizon"),
        "backlog_qty_days_mean": _mean(relevant, "target_backlog_qty_days"),
    }


def _selection_severity_key(
    scenario: Scenario, aggregate: Mapping[str, float]
) -> tuple[Any, ...]:
    """Lexicographic business-impact order; lower is more severe."""

    return (
        to_float(aggregate.get("on_due_mean"), math.inf),
        -to_float(aggregate.get("incremental_backlog_qty_days_mean"), -math.inf),
        to_float(aggregate.get("worst_rolling_on_due_mean"), math.inf),
        to_float(aggregate.get("recovered_fraction"), 1.0),
        -to_float(aggregate.get("recovery_day_mean"), -1.0),
        to_float(aggregate.get("fill_mean"), math.inf),
        scenario.scenario_id,
    )


def baseline_chain_incident_flow_audit(
    baseline_rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Classify whether each chain is physically exercised during the incident.

    A supplier stress can only support a sensitivity conclusion when the paired
    baseline both calls and ships a positive quantity on that chain during the
    J45--J224 incident window.  Missing evidence is deliberately not treated as
    positive flow.
    """

    expected_rows = len(baseline_rows)
    audit: dict[str, dict[str, Any]] = {}
    for chain in CHAINS:
        prefix = f"baseline_chain__{chain.chain_id}__"
        pulled_values = [
            to_float(row.get(f"{prefix}incident_pulled_qty"), math.nan)
            for row in baseline_rows
        ]
        shipped_values = [
            to_float(row.get(f"{prefix}incident_shipped_qty"), math.nan)
            for row in baseline_rows
        ]
        pulled = [value for value in pulled_values if math.isfinite(value)]
        shipped = [value for value in shipped_values if math.isfinite(value)]
        complete = (
            expected_rows > 0
            and len(pulled) == expected_rows
            and len(shipped) == expected_rows
        )
        exercised = bool(
            complete
            and all(value > 1e-12 for value in pulled)
            and all(value > 1e-12 for value in shipped)
        )
        if not complete:
            reason = "missing_baseline_incident_flow"
        elif exercised:
            reason = "positive_baseline_incident_flow"
        else:
            reason = "zero_baseline_incident_flow"
        audit[chain.chain_id] = {
            "chain_id": chain.chain_id,
            "target_product_id": chain.target_product_id,
            "baseline_row_count": expected_rows,
            "evidence_complete": complete,
            "incident_pulled_qty_mean": (
                sum(pulled) / len(pulled) if pulled else math.nan
            ),
            "incident_pulled_qty_min": min(pulled) if pulled else math.nan,
            "incident_shipped_qty_mean": (
                sum(shipped) / len(shipped) if shipped else math.nan
            ),
            "incident_shipped_qty_min": min(shipped) if shipped else math.nan,
            "exercised": exercised,
            "reason": reason,
        }
    return audit


def select_confirmation_scenarios(
    screening_rows: Sequence[Mapping[str, Any]],
    scenarios: Sequence[Scenario],
    *,
    targets: Sequence[float] = (0.80, 0.93),
) -> dict[str, tuple[str, ...]]:
    """Select deterministic on-due targets, cliffs, and mechanism witnesses."""

    baseline_rows = [
        row for row in screening_rows if str(row.get("scenario_id")) == "baseline_nominal"
    ]
    if not baseline_rows:
        raise ValueError("Screening baseline is required for confirmation selection")
    flow_audit = baseline_chain_incident_flow_audit(baseline_rows)
    selected: dict[str, set[str]] = defaultdict(set)
    for chain in CHAINS:
        if not bool(flow_audit[chain.chain_id]["exercised"]):
            continue
        candidates = [
            scenario
            for scenario in scenarios
            if scenario.chain_id == chain.chain_id
            and not scenario.is_baseline_alias
            and not scenario.is_campaign_baseline
            and any(
                str(row.get("scenario_id")) == scenario.scenario_id
                for row in screening_rows
            )
        ]
        if not candidates:
            continue
        aggregates = {
            scenario.scenario_id: _aggregate_for_selection(screening_rows, scenario)
            for scenario in candidates
        }
        usable = [
            scenario
            for scenario in candidates
            if math.isfinite(aggregates[scenario.scenario_id]["on_due_mean"])
        ]
        if not usable:
            continue
        strongest = min(
            usable,
            key=lambda item: _selection_severity_key(
                item, aggregates[item.scenario_id]
            ),
        )
        selected[strongest.scenario_id].add("strongest_chain_multi_metric")

        # Every operational cause retains at least one multi-seed witness.  This
        # prevents a cross-mechanism ranking from resting on the screening seed.
        for mechanism in MECHANISMS:
            mechanism_candidates = [
                item for item in usable if item.mechanism_key == mechanism.key
            ]
            if not mechanism_candidates:
                continue
            mechanism_strongest = min(
                mechanism_candidates,
                key=lambda item: _selection_severity_key(
                    item, aggregates[item.scenario_id]
                ),
            )
            selected[mechanism_strongest.scenario_id].add(
                "strongest_level_for_mechanism"
            )

        for target in targets:
            closest = min(
                usable,
                key=lambda item: (
                    abs(aggregates[item.scenario_id]["on_due_mean"] - target),
                    aggregates[item.scenario_id]["on_due_mean"],
                    item.scenario_id,
                ),
            )
            target_code = int(round(target * 100))
            selected[closest.scenario_id].add(
                f"closest_product_on_due_{target_code}pct"
            )
            same_mechanism = sorted(
                [item for item in usable if item.mechanism_key == closest.mechanism_key],
                key=lambda item: (item.level_index, item.scenario_id),
            )
            closest_index = same_mechanism.index(closest)
            for neighbor_index in (closest_index - 1, closest_index + 1):
                if 0 <= neighbor_index < len(same_mechanism):
                    selected[same_mechanism[neighbor_index].scenario_id].add(
                        f"neighbor_product_on_due_{target_code}pct"
                    )

        # Confirm both sides of each mechanism's steepest adjacent on-due drop.
        for mechanism in MECHANISMS:
            ordered = sorted(
                [item for item in usable if item.mechanism_key == mechanism.key],
                key=lambda item: (item.level_index, item.scenario_id),
            )
            if len(ordered) < 2:
                continue
            left, right = max(
                zip(ordered, ordered[1:]),
                key=lambda pair: (
                    aggregates[pair[0].scenario_id]["on_due_mean"]
                    - aggregates[pair[1].scenario_id]["on_due_mean"],
                    -pair[0].level_index,
                    pair[0].scenario_id,
                ),
            )
            selected[left.scenario_id].add("adjacent_to_steepest_on_due_cliff")
            selected[right.scenario_id].add("adjacent_to_steepest_on_due_cliff")

        baseline_on_due = _mean(
            baseline_rows, f"on_due_volume_proxy_{chain.target_product_id}"
        )
        baseline_backlog = _mean(
            baseline_rows, f"backlog_qty_days_{chain.target_product_id}"
        )
        stressed = [scenario for scenario in usable if scenario.level_index >= 4]
        witness_pool = stressed or usable
        absorbed = min(
            witness_pool,
            key=lambda item: (
                abs(aggregates[item.scenario_id]["on_due_mean"] - baseline_on_due),
                abs(
                    aggregates[item.scenario_id]["backlog_qty_days_mean"]
                    - baseline_backlog
                ),
                -item.level_index,
                item.scenario_id,
            ),
        )
        selected[absorbed.scenario_id].add("absorbed_witness")
    return {
        scenario_id: tuple(sorted(reasons))
        for scenario_id, reasons in sorted(selected.items())
    }


def _statistics(values: Sequence[float]) -> dict[str, float]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return {key: math.nan for key in ("mean", "p05", "p50", "min", "max")}
    return {
        "mean": sum(clean) / len(clean),
        "p05": percentile(clean, 0.05),
        "p50": percentile(clean, 0.50),
        "min": min(clean),
        "max": max(clean),
    }


def aggregate_metric_rows(
    rows: Sequence[Mapping[str, Any]], scenario: Scenario, *, evidence_stage: str
) -> dict[str, Any]:
    relevant = [row for row in rows if str(row.get("scenario_id")) == scenario.scenario_id]
    if not relevant:
        return {}
    output: dict[str, Any] = {
        "scenario_id": scenario.scenario_id,
        "execution_scenario_id": scenario.execution_scenario_id,
        "chain_id": scenario.chain_id,
        "mechanism": scenario.mechanism_key,
        "level_index": scenario.level_index,
        "level_code": scenario.level_code,
        "level_label": scenario.level_label,
        "mechanism_value": scenario.value,
        "mechanism_unit": scenario.unit,
        "target_product_id": scenario.target_product_id,
        "is_campaign_baseline": scenario.is_campaign_baseline,
        "is_baseline_alias": scenario.is_baseline_alias,
        "evidence_stage": evidence_stage,
        "n_seeds": len({to_int(row.get("seed")) for row in relevant}),
        "seeds": "|".join(
            str(seed) for seed in sorted({to_int(row.get("seed")) for row in relevant})
        ),
        "all_runs_valid": all(as_bool(row.get("valid")) for row in relevant),
    }
    metric_fields = (
        "supplier_service_horizon",
        "supplier_on_due_date_proxy",
        "supplier_quantitative_conformity_proxy",
        "supplier_lead_on_due_proxy",
        "supplier_flow_coverage_vs_paired_baseline",
        "supplier_incident_flow_coverage_vs_paired_baseline",
        "product_service_horizon",
        "product_on_due_date_proxy",
        "target_fill_rate",
        "target_on_due_volume_proxy",
        "target_starting_backlog_qty",
        "target_backlog_qty_days",
        "target_backlog_days",
        "target_backlog_max_qty",
        "target_backlog_end_qty",
        "target_first_backlog_day",
        "target_backlog_peak_day",
        "target_incident_backlog_qty_days",
        "target_post_incident_backlog_qty_days",
        "target_recovery_day_after_incident",
        "target_recovered_within_horizon",
        "target_worst_rolling_28d_fill_catchup_contaminated",
        "target_worst_rolling_28d_on_due_proxy",
        "incremental_target_backlog_qty_days",
        "target_on_due_date_proxy_delta_vs_paired_baseline",
        "target_worst_rolling_28d_on_due_delta_vs_paired_baseline",
        "total_cost",
        "supplier_shipped_qty",
        "supplier_pulled_qty",
        "supplier_incident_shipped_qty",
        "supplier_incident_pulled_qty",
        "paired_baseline_supplier_incident_shipped_qty",
        "paired_baseline_supplier_incident_pulled_qty",
        "supplier_incident_plus_lead_shipped_qty",
        "supplier_incident_plus_lead_pulled_qty",
        "supplier_weighted_mean_lead_days",
        "supplier_weighted_reliability",
        "supplier_incident_capacity_binding_days",
        "supplier_incident_capacity_peak_utilization",
        "healthy_supplier_shipped_qty",
    )
    for field in metric_fields:
        stats = _statistics([to_float(row.get(field), math.nan) for row in relevant])
        for stat, value in stats.items():
            output[f"{field}_{stat}"] = value
    for product in PRODUCTS:
        for field in (
            "fill_rate",
            "on_due_volume_proxy",
            "starting_backlog_qty",
            "backlog_qty_days",
            "backlog_days",
            "backlog_max_qty",
            "backlog_end_qty",
            "incident_backlog_qty_days",
            "post_incident_backlog_qty_days",
            "recovery_day_after_incident",
            "recovered_within_horizon",
            "worst_rolling_28d_on_due_proxy",
        ):
            source = f"{field}_{product}"
            stats = _statistics(
                [to_float(row.get(source), math.nan) for row in relevant]
            )
            output[f"{source}_mean"] = stats["mean"]
            output[f"{source}_p05"] = stats["p05"]
    output["supplier_service_horizon"] = output.get(
        "supplier_service_horizon_mean", math.nan
    )
    output["supplier_on_due_date_proxy"] = output.get(
        "supplier_on_due_date_proxy_mean", math.nan
    )
    output["product_service_horizon"] = output.get(
        "product_service_horizon_mean", math.nan
    )
    output["product_on_due_date_proxy"] = output.get(
        "product_on_due_date_proxy_mean", math.nan
    )
    flow_flags = [
        as_bool(row.get("paired_baseline_supplier_incident_flow_exercised"))
        for row in relevant
        if row.get("paired_baseline_supplier_incident_flow_exercised") is not None
    ]
    if flow_flags:
        flow_exercised = all(flow_flags)
    else:
        # Compatibility with screening rows produced immediately before this
        # guard was added: they already contain the paired shipped denominator.
        paired_shipped = [
            to_float(
                row.get("paired_baseline_supplier_incident_shipped_qty"),
                math.nan,
            )
            for row in relevant
        ]
        finite_shipped = [value for value in paired_shipped if math.isfinite(value)]
        flow_exercised = bool(finite_shipped) and all(
            value > 1e-12 for value in finite_shipped
        )
    output["paired_baseline_supplier_incident_flow_exercised"] = flow_exercised
    output["paired_baseline_supplier_incident_flow_status"] = (
        "positive_baseline_incident_flow"
        if flow_exercised
        else "zero_or_missing_baseline_incident_flow"
    )
    return output


def summarize_scenarios(
    screening_rows: Sequence[Mapping[str, Any]],
    confirmation_rows: Sequence[Mapping[str, Any]],
    scenarios: Sequence[Scenario],
    selection: Mapping[str, Sequence[str]],
) -> list[dict[str, Any]]:
    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    baseline = by_id["baseline_nominal"]
    confirmation_ids = {str(row.get("scenario_id")) for row in confirmation_rows}
    baseline_source = (
        confirmation_rows if "baseline_nominal" in confirmation_ids else screening_rows
    )
    baseline_summary = aggregate_metric_rows(
        baseline_source,
        baseline,
        evidence_stage="confirmation" if confirmation_rows else "screening",
    )
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        if scenario.is_not_applicable:
            rows.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "execution_scenario_id": "",
                    "chain_id": scenario.chain_id,
                    "mechanism": scenario.mechanism_key,
                    "level_index": scenario.level_index,
                    "level_code": scenario.level_code,
                    "level_label": scenario.level_label,
                    "mechanism_value": scenario.value,
                    "mechanism_unit": scenario.unit,
                    "target_product_id": scenario.target_product_id,
                    "is_campaign_baseline": False,
                    "is_baseline_alias": scenario.is_baseline_alias,
                    "is_not_applicable": True,
                    "evidence_stage": "not_applicable",
                    "n_seeds": 0,
                    "seeds": "",
                    "all_runs_valid": True,
                    "confirmation_selected": False,
                    "confirmation_reasons": "not_applicable_zero_physical_capacity_denominator",
                    "supplier_service_horizon": math.nan,
                    "supplier_on_due_date_proxy": math.nan,
                    "product_service_horizon": math.nan,
                    "product_on_due_date_proxy": math.nan,
                }
            )
            continue
        if scenario.is_baseline_alias:
            row = dict(baseline_summary)
            row.update(
                {
                    "scenario_id": scenario.scenario_id,
                    "execution_scenario_id": "baseline_nominal",
                    "chain_id": scenario.chain_id,
                    "mechanism": scenario.mechanism_key,
                    "level_index": scenario.level_index,
                    "level_code": scenario.level_code,
                    "level_label": scenario.level_label,
                    "mechanism_value": scenario.value,
                    "mechanism_unit": scenario.unit,
                    "target_product_id": scenario.target_product_id,
                    "is_campaign_baseline": False,
                    "is_baseline_alias": True,
                    "is_not_applicable": False,
                    "evidence_stage": "shared_baseline",
                    "confirmation_selected": False,
                    "confirmation_reasons": "shared_baseline_no_execution",
                }
            )
            product = scenario.target_product_id
            row["target_fill_rate_mean"] = row.get(f"fill_rate_{product}_mean")
            row["target_fill_rate_p05"] = row.get(f"fill_rate_{product}_p05")
            row["target_on_due_volume_proxy_mean"] = row.get(
                f"on_due_volume_proxy_{product}_mean"
            )
            row["target_backlog_qty_days_mean"] = row.get(
                f"backlog_qty_days_{product}_mean"
            )
            row["product_service_horizon"] = row["target_fill_rate_mean"]
            row["product_on_due_date_proxy"] = row[
                "target_on_due_volume_proxy_mean"
            ]
            prefix = f"baseline_chain__{scenario.chain_id}__"
            supplier_fields = {
                "supplier_service_horizon": "service_horizon",
                "supplier_on_due_date_proxy": "on_due_date_proxy",
                "supplier_quantitative_conformity_proxy": "service_horizon",
                "supplier_lead_on_due_proxy": "on_due_date_proxy",
                "supplier_flow_coverage_vs_paired_baseline": None,
                "supplier_incident_flow_coverage_vs_paired_baseline": None,
            }
            for output_field, source_suffix in supplier_fields.items():
                if source_suffix is None:
                    stats = _statistics([1.0 for _ in baseline_source])
                else:
                    stats = _statistics(
                        [
                            to_float(
                                item.get(f"{prefix}{source_suffix}"), math.nan
                            )
                            for item in baseline_source
                            if str(item.get("scenario_id")) == "baseline_nominal"
                        ]
                    )
                row[output_field] = stats["mean"]
                for stat, value in stats.items():
                    row[f"{output_field}_{stat}"] = value
            incident_pulled = _statistics(
                [
                    to_float(
                        item.get(f"{prefix}incident_pulled_qty"), math.nan
                    )
                    for item in baseline_source
                    if str(item.get("scenario_id")) == "baseline_nominal"
                ]
            )
            incident_shipped = _statistics(
                [
                    to_float(
                        item.get(f"{prefix}incident_shipped_qty"), math.nan
                    )
                    for item in baseline_source
                    if str(item.get("scenario_id")) == "baseline_nominal"
                ]
            )
            row["paired_baseline_supplier_incident_pulled_qty_mean"] = (
                incident_pulled["mean"]
            )
            row["paired_baseline_supplier_incident_shipped_qty_mean"] = (
                incident_shipped["mean"]
            )
            flow_exercised = (
                math.isfinite(incident_pulled["min"])
                and math.isfinite(incident_shipped["min"])
                and incident_pulled["min"] > 1e-12
                and incident_shipped["min"] > 1e-12
            )
            row["paired_baseline_supplier_incident_flow_exercised"] = (
                flow_exercised
            )
            row["paired_baseline_supplier_incident_flow_status"] = (
                "positive_baseline_incident_flow"
                if flow_exercised
                else "zero_or_missing_baseline_incident_flow"
            )
            rows.append(row)
            continue
        source = (
            confirmation_rows
            if scenario.scenario_id in confirmation_ids
            else screening_rows
        )
        stage = "confirmation" if scenario.scenario_id in confirmation_ids else "screening"
        row = aggregate_metric_rows(source, scenario, evidence_stage=stage)
        if not row:
            raise ValueError(f"Missing metrics for designed scenario {scenario.scenario_id}")
        row["confirmation_selected"] = scenario.scenario_id in selection
        row["confirmation_reasons"] = "|".join(selection.get(scenario.scenario_id, ()))
        row["is_not_applicable"] = False
        rows.append(row)
    return rows


def build_worst_cases(
    summary_rows: Sequence[Mapping[str, Any]], *, top_per_chain: int = 5
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for chain in CHAINS:
        candidates = [
            dict(row)
            for row in summary_rows
            if str(row.get("chain_id")) == chain.chain_id
            and as_bool(row.get("confirmation_selected"))
            and not as_bool(row.get("is_baseline_alias"))
            and not as_bool(row.get("is_not_applicable"))
        ]
        candidates.sort(
            key=lambda row: (
                to_float(row.get("product_on_due_date_proxy_p05"), math.inf),
                to_float(row.get("product_on_due_date_proxy_mean"), math.inf),
                -to_float(
                    row.get("incremental_target_backlog_qty_days_mean"), 0.0
                ),
                to_float(
                    row.get("target_worst_rolling_28d_on_due_proxy_mean"), math.inf
                ),
                to_float(row.get("target_recovered_within_horizon_mean"), 1.0),
                -to_float(row.get("target_recovery_day_after_incident_mean"), -1.0),
                to_float(row.get("product_service_horizon_mean"), math.inf),
                str(row.get("scenario_id") or ""),
            )
        )
        for rank, row in enumerate(candidates[: max(1, top_per_chain)], 1):
            row["worst_rank_within_chain"] = rank
            output.append(row)
    return output


def campaign_signature(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_engine_command(
    config: RunConfig,
    *,
    case_dir: Path,
    seed: int,
    risk_csv: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(config.engine),
        "--input",
        str(config.graph),
        "--output-dir",
        str(case_dir),
        "--scenario-id",
        config.scenario_id,
        "--days",
        str(config.days),
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
        str(config.supplier_floors),
        *(
            [
                "--factory-nominal-capacities-csv",
                str(config.factory_capacities),
            ]
            if config.factory_capacities is not None
            else []
        ),
        *config.profile_args,
        # Managed protocol arguments must be last: the profile contains older
        # smoothing, initial-state and January-order settings.
        *CAMPAIGN_PROTOCOL_ARGS,
    ]
    if risk_csv is not None:
        command.extend(["--supplier-risk-events-csv", str(risk_csv)])
    return command


def run_and_extract_case(
    config: RunConfig,
    *,
    scenario: Scenario,
    seed: int,
    stage: str,
    risk_csv: Path | None,
    configured_event_count: int,
    baseline_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    case_dir = config.output_dir / "cases" / scenario.execution_scenario_id / f"seed_{seed}"
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    service_path = case_dir / "data" / "production_demand_service_daily.csv"
    status = "reextracted" if summary_path.exists() and service_path.exists() else "executed"
    if status == "executed":
        case_dir.mkdir(parents=True, exist_ok=True)
        command = build_engine_command(
            config,
            case_dir=case_dir,
            seed=seed,
            risk_csv=risk_csv,
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
                f"Engine failed for {scenario.scenario_id}/seed_{seed}; see {log_path}"
            )
    row = extract_case_metrics(
        case_dir=case_dir,
        scenario=scenario,
        seed=seed,
        stage=stage,
        status=status,
        days=config.days,
        configured_event_count=configured_event_count,
        physical_capacity_by_lane_map=config.physical_capacity_by_lane,
    )
    attach_paired_baseline_metrics(
        row, scenario=scenario, baseline_row=baseline_row
    )
    validate_metric_row(
        row,
        scenario=scenario,
        days=config.days,
        baseline_row=baseline_row,
    )
    if config.retention == "summary":
        removed = prune_case_artifacts(case_dir)
        row["retention_removed"] = "|".join(removed)
    else:
        row["retention_removed"] = ""
    return row


def _row_key(row: Mapping[str, Any]) -> tuple[str, int]:
    return str(row.get("scenario_id") or ""), to_int(row.get("seed"), -1)


def _write_metric_ledger(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    ordered = sorted(rows, key=lambda row: (to_int(row.get("seed")), str(row.get("scenario_id"))))
    write_csv_atomic(path, ordered)


def _reuse_metric_row(
    row: Mapping[str, Any],
    *,
    scenario: Scenario,
    stage: str,
    days: int,
    baseline_row: Mapping[str, Any] | None,
    status: str,
) -> dict[str, Any]:
    reused = dict(row)
    reused["stage"] = stage
    reused["status"] = status
    attach_paired_baseline_metrics(
        reused, scenario=scenario, baseline_row=baseline_row
    )
    validate_metric_row(
        reused,
        scenario=scenario,
        days=days,
        baseline_row=baseline_row,
    )
    return reused


def run_stage_baselines(
    config: RunConfig,
    *,
    stage: str,
    seeds: Sequence[int],
    metric_path: Path,
    existing_rows: list[dict[str, Any]],
    fallback_rows: Sequence[Mapping[str, Any]] = (),
    workers: int,
) -> list[dict[str, Any]]:
    baseline = build_scenario_design()[0]
    ledger = {_row_key(row): dict(row) for row in existing_rows}
    fallback = {_row_key(row): row for row in fallback_rows}
    jobs: list[int] = []
    for seed in seeds:
        key = (baseline.scenario_id, seed)
        if key in ledger:
            ledger[key] = _reuse_metric_row(
                ledger[key],
                scenario=baseline,
                stage=stage,
                days=config.days,
                baseline_row=None,
                status="reused_metric",
            )
        elif key in fallback:
            ledger[key] = _reuse_metric_row(
                fallback[key],
                scenario=baseline,
                stage=stage,
                days=config.days,
                baseline_row=None,
                status="reused_screening",
            )
        else:
            jobs.append(seed)
    if jobs:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(
                    run_and_extract_case,
                    config,
                    scenario=baseline,
                    seed=seed,
                    stage=stage,
                    risk_csv=None,
                    configured_event_count=0,
                    baseline_row=None,
                ): seed
                for seed in jobs
            }
            for future in as_completed(futures):
                row = future.result()
                ledger[_row_key(row)] = row
                _write_metric_ledger(metric_path, list(ledger.values()))
                print(
                    f"[{stage.upper()}] baseline seed={row['seed']} "
                    f"268091={to_float(row['fill_rate_268091']):.2%} "
                    f"268967={to_float(row['fill_rate_268967']):.2%}",
                    flush=True,
                )
    _write_metric_ledger(metric_path, list(ledger.values()))
    return list(ledger.values())


def run_stage_scenarios(
    config: RunConfig,
    *,
    stage: str,
    scenarios: Sequence[Scenario],
    seeds: Sequence[int],
    metric_path: Path,
    rows: list[dict[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    risk_inputs: Mapping[str, tuple[Path, int]],
    fallback_rows: Sequence[Mapping[str, Any]] = (),
    workers: int,
) -> list[dict[str, Any]]:
    ledger = {_row_key(row): dict(row) for row in rows}
    fallback = {_row_key(row): row for row in fallback_rows}
    baselines = {
        to_int(row.get("seed")): row
        for row in baseline_rows
        if str(row.get("scenario_id")) == "baseline_nominal"
    }
    jobs: list[tuple[Scenario, int]] = []
    for scenario in scenarios:
        if scenario.is_campaign_baseline or scenario.is_baseline_alias:
            continue
        risk_csv, _event_count = risk_inputs[scenario.scenario_id]
        for seed in seeds:
            baseline_row = baselines.get(seed)
            if baseline_row is None:
                raise CaseValidationError(f"Missing baseline for seed {seed}")
            key = (scenario.scenario_id, seed)
            if key in ledger:
                ledger[key] = _reuse_metric_row(
                    ledger[key],
                    scenario=scenario,
                    stage=stage,
                    days=config.days,
                    baseline_row=baseline_row,
                    status="reused_metric",
                )
            elif key in fallback:
                ledger[key] = _reuse_metric_row(
                    fallback[key],
                    scenario=scenario,
                    stage=stage,
                    days=config.days,
                    baseline_row=baseline_row,
                    status="reused_screening",
                )
            else:
                jobs.append((scenario, seed))
    if jobs:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {}
            for scenario, seed in jobs:
                risk_csv, event_count = risk_inputs[scenario.scenario_id]
                futures[
                    pool.submit(
                        run_and_extract_case,
                        config,
                        scenario=scenario,
                        seed=seed,
                        stage=stage,
                        risk_csv=risk_csv,
                        configured_event_count=event_count,
                        baseline_row=baselines[seed],
                    )
                ] = (scenario, seed)
            for future in as_completed(futures):
                row = future.result()
                ledger[_row_key(row)] = row
                _write_metric_ledger(metric_path, list(ledger.values()))
                print(
                    f"[{stage.upper()}] {row['scenario_id']} seed={row['seed']} "
                    f"service={to_float(row['target_fill_rate']):.2%}",
                    flush=True,
                )
    _write_metric_ledger(metric_path, list(ledger.values()))
    return list(ledger.values())


def prepare_risk_inputs(
    output_dir: Path, scenarios: Sequence[Scenario], days: int
) -> dict[str, tuple[Path, int]]:
    result: dict[str, tuple[Path, int]] = {}
    risk_dir = output_dir / "inputs" / "risk_events"
    for scenario in scenarios:
        if scenario.is_campaign_baseline or scenario.is_baseline_alias:
            continue
        rows = build_risk_event_rows(scenario, days)
        if not rows:
            raise ValueError(f"Non-baseline scenario has no events: {scenario.scenario_id}")
        path = risk_dir / f"{scenario.scenario_id}.csv"
        write_risk_csv(path, rows)
        result[scenario.scenario_id] = (path, len(rows))
    return result


def _required_path(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Missing {label}: {resolved}")
    return resolved


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument(
        "--supplier-floors",
        type=Path,
        default=(
            DEFAULT_BASELINE_RUN
            / "data"
            / "supplier_capacity_calibration_measured_period.csv"
        ),
    )
    parser.add_argument(
        "--factory-capacities",
        type=Path,
        default=None,
        help=(
            "Optional explicit factory-capacity override. By default factory "
            "physics stays in the reference graph to avoid confounding supplier risks."
        ),
    )
    parser.add_argument("--engine-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--scenario-id", default="scn:BASE")
    parser.add_argument("--days", type=int, default=720)
    parser.add_argument("--screening-seed", type=int, default=330281)
    parser.add_argument("--confirmation-seeds", default="330282-330291")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--retention",
        choices=("summary", "full"),
        default="summary",
        help="summary removes only generated data/plots/maps/run directories after validated extraction.",
    )
    parser.add_argument("--worst-per-chain", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.days <= 0:
        raise ValueError("--days must be positive")
    if args.workers <= 0:
        raise ValueError("--workers must be positive")
    repo_root = args.repo_root.resolve()
    output_dir = (args.output_dir or default_output_dir()).resolve()
    graph = _required_path(args.graph, "reference graph")
    engine = _required_path(args.engine, "simulation engine")
    supplier_floors_source = _required_path(args.supplier_floors, "supplier floors")
    factory_capacities = (
        _required_path(args.factory_capacities, "factory nominal capacities")
        if args.factory_capacities is not None
        else None
    )
    engine_profile = _required_path(args.engine_profile, "engine profile")
    graph_payload = read_json(graph)
    graph_audit = validate_graph_scope(graph_payload)
    profile_args = tuple(engine_profile_args(engine_profile))
    screening_seed = int(args.screening_seed)
    confirmation_seeds = parse_seeds(args.confirmation_seeds)
    if screening_seed in confirmation_seeds:
        raise ValueError(
            "The screening seed must not be repeated in --confirmation-seeds"
        )
    prepared_floor_rows, physical_floor_audit = build_prepared_physical_floor_rows(
        read_csv_rows(supplier_floors_source)
    )
    prepared_capacity_map = physical_capacity_by_lane(prepared_floor_rows)
    prepared_floors_path = (
        output_dir / "inputs" / "prepared_physical_supplier_floors.csv"
    )
    scenarios = build_scenario_design()
    executable = executable_scenarios(scenarios)
    signature_payload = {
        "schema_version": "etudecas.supplier_service_landscape_campaign.v1",
        "graph": str(graph),
        "graph_sha256": sha256_file(graph),
        "engine": str(engine),
        "engine_sha256": sha256_file(engine),
        "supplier_floors_source": str(supplier_floors_source),
        "supplier_floors_source_sha256": sha256_file(supplier_floors_source),
        "prepared_supplier_floors": str(prepared_floors_path),
        "prepared_supplier_floors_content_sha256": campaign_signature(
            {"rows": prepared_floor_rows}
        ),
        "factory_capacity_source": (
            "explicit_override" if factory_capacities is not None else "reference_graph"
        ),
        "factory_capacities": (
            str(factory_capacities) if factory_capacities is not None else ""
        ),
        "factory_capacities_sha256": (
            sha256_file(factory_capacities)
            if factory_capacities is not None
            else ""
        ),
        "engine_profile": str(engine_profile),
        "engine_profile_sha256": sha256_file(engine_profile),
        "scenario_id": args.scenario_id,
        "days": args.days,
        "screening_seed": screening_seed,
        "confirmation_seeds": confirmation_seeds,
        "common_random_numbers": True,
        "warmup_boundary_audit": True,
        "incident_window": {
            "start_day": incident_window(args.days)[0],
            "end_day": incident_window(args.days)[1],
            "duration_days": incident_window(args.days)[1]
            - incident_window(args.days)[0]
            + 1,
        },
        "managed_protocol_args_applied_after_profile": list(CAMPAIGN_PROTOCOL_ARGS),
        "expected_resolved_protocol": {
            "initial_state_scale": 0.1,
            "mrp_demand_signal_smoothing_days": 7,
            "dynamic_mrp_requirement_pairs": sorted(
                DYNAMIC_MRP_REQUIREMENT_PAIRS
            ),
            "smoothed_cover_requirement_pairs": sorted(
                SMOOTHED_COVER_REQUIREMENT_PAIRS
            ),
            "opening_observed_stock_scale": 1.0,
            "opening_observed_stock_scale_csv": "",
            "warmup_days": WARMUP_DAYS,
            "warmup_profile_mode": "preperiod",
            "restore_opening_stock_after_warmup": False,
            "seed_open_orders_from_january_snapshot": False,
            "mrp_multisource_policy": "legacy",
            "external_procurement_enabled": True,
            "external_procurement_proactive_replenishment": True,
            "external_procurement_lead_mode": "supplier_material",
            "external_procurement_capacity_mode": "supplier_nominal",
            "external_procurement_nominal_capacity_scale": 1.0,
            "supplier_risk_loss_gross_up": False,
            "supplier_state_dependent_risks_enabled": False,
        },
        "intermittent_delay_method": (
            "four deterministic post-J0 grouped windows covering about 50% of "
            "the temporary incident at twice the declared mean extra delay"
        ),
        "physical_floor_audit": physical_floor_audit,
        "scenario_design": scenario_design_rows(scenarios),
    }
    signature = campaign_signature(signature_payload)
    manifest_path = output_dir / "campaign_manifest.json"
    if output_dir.exists() and any(output_dir.iterdir()):
        if not manifest_path.exists():
            raise RuntimeError(
                f"Refusing to use non-empty output without campaign manifest: {output_dir}"
            )
        previous = read_json(manifest_path)
        if str(previous.get("campaign_signature") or "") != signature:
            raise RuntimeError(
                "Existing output was created with a different campaign signature; "
                "choose a new additive --output-dir."
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    design_path = output_dir / "scenario_design.csv"
    screening_path = output_dir / "screening_metrics.csv"
    confirmation_path = output_dir / "confirmation_metrics.csv"
    summary_path = output_dir / "scenario_summary.csv"
    worst_path = output_dir / "worst_cases.csv"
    manifest: dict[str, Any] = {
        **signature_payload,
        "campaign_signature": signature,
        "status": "running",
        "started_or_resumed_at_utc": utc_now(),
        "output_dir": str(output_dir),
        "graph_mutated": False,
        "demand_mutated": False,
        "service_mutated": False,
        "evidence_class": "exploratory_simulation_hypothesis",
        "capacity_warning": (
            "Capacity ratios are exploratory cliff-finding stresses around a "
            "functional reference equal to 2.5 times the corrected baseline's "
            "measured daily pull peak. These are not contractual capacities. "
            "Only 338929 and 344135 are overridden; unrelated supplier pairs "
            "and factory capacities remain governed by the reference graph."
        ),
        "baseline_quality_guard": {
            "minimum_product_horizon_service": BASELINE_MIN_SERVICE,
            "minimum_product_on_due_proxy": BASELINE_MIN_SERVICE,
            "products": list(PRODUCTS),
            "timing": "validated before any stressed scenario is executed",
        },
        "intermittent_delay_warning": (
            "Grouped post-J0 delays have the declared temporal mean; they are "
            "hypothetical intermittent delays, not fitted CV or OTIF."
        ),
        "mechanism_equivalence_warning": (
            "In the current engine, reliability and quality_yield are near-"
            "equivalent algebraic quantity-loss mechanisms. They remain "
            "separate business causes but must not be ranked as independent drivers."
        ),
        "graph_scope_audit": graph_audit,
        "retention": {
            "mode": args.retention,
            "deleted_directories_if_summary": sorted(RETENTION_DIRECTORY_ALLOWLIST),
            "kept": ["summaries", "reports", "campaign_engine.log", "campaign CSV/JSON"],
        },
        "outputs": {
            "scenario_design_csv": str(design_path),
            "screening_metrics_csv": str(screening_path),
            "confirmation_metrics_csv": str(confirmation_path),
            "scenario_summary_csv": str(summary_path),
            "worst_cases_csv": str(worst_path),
        },
    }
    write_json_atomic(manifest_path, manifest)
    write_csv_atomic(prepared_floors_path, prepared_floor_rows)
    write_csv_atomic(design_path, scenario_design_rows(scenarios))
    config = RunConfig(
        repo_root=repo_root,
        output_dir=output_dir,
        engine=engine,
        graph=graph,
        supplier_floors=prepared_floors_path,
        factory_capacities=factory_capacities,
        profile_args=profile_args,
        scenario_id=str(args.scenario_id),
        days=int(args.days),
        retention=str(args.retention),
        physical_capacity_by_lane=prepared_capacity_map,
    )
    try:
        risk_inputs = prepare_risk_inputs(output_dir, executable, args.days)
        screening_existing = read_csv_rows(screening_path)
        screening_rows = run_stage_baselines(
            config,
            stage="screening",
            seeds=[screening_seed],
            metric_path=screening_path,
            existing_rows=screening_existing,
            workers=args.workers,
        )
        screening_rows = run_stage_scenarios(
            config,
            stage="screening",
            scenarios=executable,
            seeds=[screening_seed],
            metric_path=screening_path,
            rows=screening_rows,
            baseline_rows=screening_rows,
            risk_inputs=risk_inputs,
            workers=args.workers,
        )
        baseline_flow_audit = baseline_chain_incident_flow_audit(
            [
                row
                for row in screening_rows
                if str(row.get("scenario_id")) == "baseline_nominal"
            ]
        )
        selection = select_confirmation_scenarios(screening_rows, scenarios)
        selected_scenarios = [
            scenario
            for scenario in executable
            if scenario.scenario_id in selection
        ]
        confirmation_existing = read_csv_rows(confirmation_path)
        confirmation_rows = run_stage_baselines(
            config,
            stage="confirmation",
            seeds=confirmation_seeds,
            metric_path=confirmation_path,
            existing_rows=confirmation_existing,
            fallback_rows=screening_rows,
            workers=args.workers,
        )
        confirmation_rows = run_stage_scenarios(
            config,
            stage="confirmation",
            scenarios=selected_scenarios,
            seeds=confirmation_seeds,
            metric_path=confirmation_path,
            rows=confirmation_rows,
            baseline_rows=confirmation_rows,
            risk_inputs=risk_inputs,
            fallback_rows=screening_rows,
            workers=args.workers,
        )
        summary_rows = summarize_scenarios(
            screening_rows,
            confirmation_rows,
            scenarios,
            selection,
        )
        worst_rows = build_worst_cases(
            summary_rows, top_per_chain=max(1, int(args.worst_per_chain))
        )
        write_csv_atomic(summary_path, summary_rows)
        write_csv_atomic(worst_path, worst_rows)
        baseline_hashes = {
            str(to_int(row.get("seed"))): str(row.get("j0_state_sha256") or "")
            for row in confirmation_rows
            if str(row.get("scenario_id")) == "baseline_nominal"
        }
        manifest.update(
            {
                "status": "complete",
                "completed_at_utc": utc_now(),
                "screening_valid_rows": len(screening_rows),
                "confirmation_valid_rows": len(confirmation_rows),
                "selected_scenarios": {
                    key: list(value) for key, value in selection.items()
                },
                "selected_scenario_count": len(selection),
                "baseline_chain_incident_flow_audit": baseline_flow_audit,
                "baseline_j0_sha256_by_seed": baseline_hashes,
                "validation_rules": [
                    "non-baseline applied risk rows > 0",
                    "same J0 core-state SHA-256 as same-seed baseline",
                    "same input graph SHA-256 as baseline",
                    "complete daily client service horizon for both products",
                    "baseline horizon service and on-due proxy >= 95% for both products",
                    "confirmation only for chains with positive paired-baseline incident pull and shipment",
                    "healthy 021081 witness receives no explicit risk row",
                ],
            }
        )
        write_json_atomic(manifest_path, manifest)
        print(f"[OK] Supplier service landscape: {output_dir}", flush=True)
        return 0
    except Exception as exc:
        manifest.update(
            {
                "status": "failed",
                "failed_at_utc": utc_now(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        write_json_atomic(manifest_path, manifest)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
