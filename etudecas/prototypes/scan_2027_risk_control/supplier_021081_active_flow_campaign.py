#!/usr/bin/env python3
"""Replay the active 2025 order book for item 021081 and stress it explicitly.

This campaign is additive: it writes scenario-specific graph overlays in its
own output directory and never edits the source graph, the cold-start profile,
an older campaign, or an HTML demonstration.  The overlays retain every firm
order in the source graph.  Only the 23 observed purchase orders for 021081 to
SDC-1450 are transformed, with a row-by-row before/after ledger.

The reusable engine now has an opt-in supplier-risk path for firm orders that
were already placed in the opening order book.  Consequently each scenario
keeps two explicit, separately audited flow classes:

* the 23 observed firm orders, transformed natively at initialization when the
  mechanism is supported (or through an explicit FIFO overlay for the one
  unsupported capacity-calendar hypothesis); and
* any new dynamic MRP order released in the same period.

The results keep those two flow classes separate.  A reference run is valid
only when the observed order book creates positive pulled and shipped quantity
and positive receipts inside the tested horizon.
"""

from __future__ import annotations

import argparse
import copy
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
DEFAULT_ENGINE = REPO_ROOT / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"
DEFAULT_PROFILE = (
    REPO_ROOT
    / "etudecas"
    / "prototypes"
    / "scan_2027_risk_control"
    / "config"
    / "canonical_real_baseline_engine_profile.json"
)
V10_BASELINE_DIR = (
    ARTIFACT_PARENT
    / "c1_quality_recalibration_20260828_v10"
    / "normal_seed_330281"
)
V10_MASKING_EVIDENCE_FILES = (
    V10_BASELINE_DIR / "data" / "production_lot_events.csv",
    V10_BASELINE_DIR / "data" / "production_lot_genealogy.csv",
    V10_BASELINE_DIR / "data" / "production_output_products_daily.csv",
    V10_BASELINE_DIR / "data" / "production_input_stocks_daily.csv",
    V10_BASELINE_DIR / "summaries" / "first_simulation_summary.json",
)

ITEM_ID = "item:021081"
DESTINATION_ID = "SDC-1450"
INTERMEDIATE_ITEM_ID = "item:773474"
TARGET_PRODUCT_ID = "item:268967"
TARGET_CLIENT_ID = "C-XXXXX"
SUPPLIER_IDS = (
    "SDC-VD0960508A",
    "SDC-VD0949099A",
    "SDC-VD0972460A",
    "SDC-VD0975221A",
)
EXPECTED_ORDER_COUNT = 23
EXPECTED_ORDER_QTY_KG = 1_320_000.0
EXPECTED_QTY_BY_SUPPLIER = {
    "SDC-VD0960508A": 820_000.0,
    "SDC-VD0949099A": 300_000.0,
    "SDC-VD0972460A": 100_000.0,
    "SDC-VD0975221A": 100_000.0,
}
EXPECTED_PHYSICAL_DAY_RANGE = (6, 139)
EXPECTED_USABLE_DAY_RANGE = (112, 261)
# The prospective envelope is anchored in the existing 720-day simulated
# branch: nine 3.2-million-g lots consume 28,608 kg each, i.e. 357.6 kg/day.
# This is simulated model evidence, not an observed industrial consumption
# rate.  One year of that signal is an explicit reduced-cover hypothesis.
MODELLED_REFERENCE_LOT_INPUT_KG = 28_608.0
MODELLED_REFERENCE_LOTS_PER_720_DAYS = 9
MODELLED_REFERENCE_DAILY_CONSUMPTION_KG = (
    MODELLED_REFERENCE_LOT_INPUT_KG
    * MODELLED_REFERENCE_LOTS_PER_720_DAYS
    / 720.0
)
# Literal BOM evidence from 773474.xlsx: 8.94 KG of 021081 for an output row
# declared as 1000 G (description: ELSSR CONT. 1000 L).  The graph therefore
# executes 8.94 kg/kg and consumes 28,608 kg for a 3.2-million-g lot.  A unit
# interpretation of 8.94 kg per 1000 kg/L would divide this ratio by 1000, but
# that is only a validation hypothesis; neither interpretation is silently
# corrected in this campaign.
BOM_021081_INPUT_QTY_KG = 8.94
BOM_773474_OUTPUT_QTY_G = 1000.0
BOM_LITERAL_INPUT_KG_PER_OUTPUT_KG = 8.94
BOM_UNIT_ALTERNATIVE_RATIO_DIVISOR = 1000.0
INTERMEDIATE_773474_STOCK_SDC_G = 9_600_000.0
INTERMEDIATE_773474_STOCK_M1430_G = 14_593_000.0
INTERMEDIATE_773474_TOTAL_STOCK_G = (
    INTERMEDIATE_773474_STOCK_SDC_G + INTERMEDIATE_773474_STOCK_M1430_G
)
INTERMEDIATE_268967_RELEASED_LOT_COUNT = 29
INTERMEDIATE_773474_HORIZON_NEED_G = 30_182_579.4116
INTERMEDIATE_773474_PER_268967_LOT_G = (
    INTERMEDIATE_773474_HORIZON_NEED_G
    / INTERMEDIATE_268967_RELEASED_LOT_COUNT
)
INTERMEDIATE_773474_HORIZON_PRODUCTION_G = 28_800_000.0
INTERMEDIATE_773474_STOCK_COVER_LOTS = (
    INTERMEDIATE_773474_TOTAL_STOCK_G
    / INTERMEDIATE_773474_PER_268967_LOT_G
)
INTERMEDIATE_773474_STOCK_TO_HORIZON_NEED = 0.8015550848
INTERMEDIATE_773474_STOCK_PLUS_PRODUCTION_TO_NEED = 1.7557478861
COMPONENT_021081_STOCK_TO_HORIZON_CONSUMPTION = 4.4358221477
COMPONENT_021081_ORDER_BOOK_TO_HORIZON_CONSUMPTION = 5.1267710664
PROSPECTIVE_COVER_LEVELS_DAYS = (365.0, 180.0, 90.0, 30.0)
# The firm-order replay is aligned to the 2025-01-01 ERP snapshot.  A 240-day
# prospective warm-up would consume stock first and only then inject January
# orders, which would no longer be a faithful snapshot replay.  Prospective
# campaigns must use a separate protocol.
WARMUP_DAYS = 0
DEFAULT_DAYS = 720
MINIMUM_REPLAY_DAYS = EXPECTED_USABLE_DAY_RANGE[1] + 1
SCREENING_SEED = 421081
REQUIRED_QUALITY_ANCHOR_IDS = (
    "all_021081__quality_hold__180",
    "sdc_vd0960508a__quality_hold__180",
)
RISK_FIELDS = (
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

# Managed arguments are deliberately last so they override older settings in
# the reusable profile without changing that profile on disk.
ACTIVE_021081_PROTOCOL_ARGS = (
    "--initial-state-scale",
    "1",
    "--opening-observed-stock-scale",
    "1",
    "--warmup-days",
    str(WARMUP_DAYS),
    "--warmup-profile-mode",
    "preperiod",
    "--no-restore-opening-stock-after-warmup",
    "--warmup-boundary-audit",
    "--initial-seed-open-orders-from-january-snapshot",
    "--initial-seed-estimated-source-pipeline",
    "--external-procurement-enabled",
    "--external-procurement-proactive-replenishment",
    "--external-procurement-lead-mode",
    "supplier_material",
    "--external-procurement-capacity-mode",
    "supplier_nominal",
    "--external-procurement-upstream-pipeline-fill-ratio",
    "1",
    "--external-procurement-nominal-capacity-scale",
    "1",
    "--mrp-demand-signal-smoothing-days",
    "7",
    "--mrp-dynamic-requirement-pair",
    "SDC-1450,item:021081",
    "--mrp-smoothed-cover-requirement-pair",
    "SDC-1450,item:021081",
    "--mrp-base-stock-floor-factor-pair",
    "SDC-1450,item:021081,0",
    "--no-supplier-risk-loss-gross-up",
    "--no-supplier-state-dependent-risks",
)


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    scope_id: str
    mechanism: str
    value: float
    value_unit: str
    label: str
    is_baseline: bool = False


@dataclass(frozen=True)
class StateRegime:
    regime_id: str
    label: str
    evidence_class: str
    opening_stock_qty_kg: float
    stock_scale: float
    target_cover_days: float | None = None


MECHANISM_LEVELS: dict[str, tuple[tuple[float, str], ...]] = {
    "delivery_delay": ((30.0, "jours"), (90.0, "jours"), (180.0, "jours")),
    "intermittent_delay": ((30.0, "jours_moyens"), (90.0, "jours_moyens"), (180.0, "jours_moyens")),
    "quality_hold": ((30.0, "jours"), (90.0, "jours"), (180.0, "jours")),
    "usable_yield": ((0.90, "ratio"), (0.50, "ratio"), (0.10, "ratio")),
    "delivery_availability": ((0.75, "ratio"), (0.50, "ratio"), (0.25, "ratio")),
    "capacity_rationing": ((0.75, "ratio"), (0.50, "ratio"), (0.25, "ratio")),
}
MECHANISM_LABELS = {
    "delivery_delay": "Retard de livraison continu",
    "intermittent_delay": "Retards intermittents",
    "quality_hold": "Allongement de la libération qualité",
    "usable_yield": "Quantité reçue mais non utilisable",
    "delivery_availability": "Commandes non livrées",
    "capacity_rationing": "Capacité fournisseur temporairement rationnée",
}


class CampaignValidationError(RuntimeError):
    """Raised when a case cannot support the claimed comparison."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_output_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ARTIFACT_PARENT / "supplier_021081_active_flow_campaign" / stamp


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


def slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")


def slug_number(value: float) -> str:
    return format(float(value), ".12g").replace("-", "m").replace(".", "p")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


PROCESS_ORCHESTRATOR_SHA256 = sha256_file(Path(__file__).resolve())


def intermediate_masking_evidence(
    source_graph_path: Path,
) -> dict[str, Any]:
    evidence_files = [source_graph_path.resolve(), *V10_MASKING_EVIDENCE_FILES]
    return {
        "sources": [
            {
                "path": str(path.resolve()),
                "sha256": sha256_file(path) if path.exists() else "",
                "available": path.exists(),
            }
            for path in evidence_files
        ],
        "formulas": {
            "opening_stock_total_g": "9,600,000 + 14,593,000",
            "approx_773474_per_268967_lot_g": (
                "30,182,579.4116 / 29 = 1,040,778.6004"
            ),
            "stock_cover_lots": (
                "24,193,000 / 1,040,778.6004 = 23.2450974594"
            ),
            "stock_multiple_of_horizon_need": (
                "24,193,000 / 30,182,579.4116 = 0.8015550848"
            ),
            "stock_plus_production_multiple_of_horizon_need": (
                "(24,193,000 + 28,800,000) / 30,182,579.4116 = 1.7557478861"
            ),
            "021081_stock_multiple_of_horizon_intermediate_consumption": (
                "1,142,100 / 257,472 = 4.4358221477"
            ),
            "021081_order_book_multiple_of_horizon_intermediate_consumption": (
                "1,320,000 / 257,472 = 5.1267710664"
            ),
            "horizon_773474_production_g": "9 production lots * 3,200,000 G",
            "horizon_021081_consumption_kg": "9 production lots * 28,608 KG",
        },
        "interpretation_status": (
            "audited_simulation_and_graph_evidence_not_observed_physical_stock_validation"
        ),
    }


def json_sha256(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(raw.encode("utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def ordered_fields(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(str(key))
                result.append(str(key))
    return result


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(fields or ordered_fields(rows))
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def engine_profile_args(path: Path) -> list[str]:
    payload = read_json(path)
    values = payload.get("args") if isinstance(payload, dict) else payload
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"Invalid engine profile: {path}")
    return list(values)


def opening_order_payload(graph: Mapping[str, Any]) -> dict[str, Any]:
    meta = graph.get("meta") or {}
    payload = meta.get("opening_open_orders") if isinstance(meta, Mapping) else None
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise ValueError("Graph has no meta.opening_open_orders.rows payload")
    return payload


def is_target_order(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("order_type") or "") == "purchase_open_order"
        and str(row.get("item_id") or "") == ITEM_ID
        and str(row.get("dst_node_id") or "") == DESTINATION_ID
        and str(row.get("src_node_id") or "") in SUPPLIER_IDS
    )


def observed_orders(graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in opening_order_payload(graph)["rows"] if isinstance(row, Mapping) and is_target_order(row)]


def observed_opening_stock_021081(graph: Mapping[str, Any]) -> float:
    matches: list[float] = []
    for node in graph.get("nodes") or []:
        if not isinstance(node, Mapping) or str(node.get("id") or "") != DESTINATION_ID:
            continue
        inventory = node.get("inventory") if isinstance(node.get("inventory"), Mapping) else {}
        for state in inventory.get("states") or []:
            if (
                isinstance(state, Mapping)
                and str(state.get("item_id") or "") == ITEM_ID
            ):
                matches.append(max(0.0, to_float(state.get("initial"))))
    if len(matches) != 1 or matches[0] <= 1e-9:
        raise ValueError(
            f"Expected exactly one positive observed stock for {DESTINATION_ID}/{ITEM_ID}"
        )
    return matches[0]


def build_state_regimes(graph: Mapping[str, Any]) -> list[StateRegime]:
    observed = observed_opening_stock_021081(graph)
    regimes = [
        StateRegime(
            regime_id="observed_2025",
            label="Stock observé à l'instantané du 01-01-2025",
            evidence_class="observed_2025_snapshot_state",
            opening_stock_qty_kg=observed,
            stock_scale=1.0,
            target_cover_days=None,
        ),
    ]
    for cover_days in PROSPECTIVE_COVER_LEVELS_DAYS:
        prospective_qty = MODELLED_REFERENCE_DAILY_CONSUMPTION_KG * cover_days
        regimes.append(
            StateRegime(
                regime_id=f"prospective_{int(cover_days)}d_cover",
                label=(
                    "Hypothèse prospective 021081 seule : "
                    f"{int(cover_days)} jours de couverture modélisée; "
                    "ce n'est pas un état supply global lean"
                ),
                evidence_class="simulated_reduced_cover_hypothesis_not_observed",
                opening_stock_qty_kg=prospective_qty,
                stock_scale=prospective_qty / observed,
                target_cover_days=cover_days,
            )
        )
    return regimes


def state_regime_rows(regimes: Sequence[StateRegime]) -> list[dict[str, Any]]:
    return [
        {
            "state_regime": regime.regime_id,
            "label": regime.label,
            "evidence_class": regime.evidence_class,
            "opening_stock_qty_kg": regime.opening_stock_qty_kg,
            "measurement_start_stock_scale": regime.stock_scale,
            "target_cover_days": (
                regime.target_cover_days
                if regime.target_cover_days is not None
                else ""
            ),
            "modelled_daily_consumption_reference_kg": (
                MODELLED_REFERENCE_DAILY_CONSUMPTION_KG
                if regime.target_cover_days is not None
                else ""
            ),
            "interpretation": (
                "Observed snapshot state; no reduced-cover assumption."
                if regime.target_cover_days is None
                else (
                    "Prospective sensitivity assumption based on the existing "
                    "model's 9 lots / 720 days; not an observed stock policy."
                )
            ),
        }
        for regime in regimes
    ]


def order_id(row: Mapping[str, Any]) -> str:
    return f"Extract_En_cours.xlsx:{to_int(row.get('source_row'), -1)}"


def audit_observed_order_book(rows: Sequence[Mapping[str, Any]], *, strict: bool = True) -> dict[str, Any]:
    quantities: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    source_rows: set[int] = set()
    for row in rows:
        if not is_target_order(row):
            raise ValueError("Order-book audit received a row outside the 021081 scope")
        supplier = str(row.get("src_node_id") or "")
        quantities[supplier] += max(0.0, to_float(row.get("quantity")))
        counts[supplier] += 1
        source_row = to_int(row.get("source_row"), -1)
        if source_row in source_rows:
            raise ValueError(f"Duplicate source row in 021081 order book: {source_row}")
        source_rows.add(source_row)
        if str(row.get("uom") or "").upper() != "KG":
            raise ValueError(f"Unexpected 021081 unit for source row {source_row}")
    total = sum(quantities.values())
    physical_days = [to_int(row.get("physical_delivery_day"), -1) for row in rows]
    usable_days = [to_int(row.get("usable_day"), -1) for row in rows]
    shares = {
        supplier: (quantities.get(supplier, 0.0) / total if total > 0 else 0.0)
        for supplier in SUPPLIER_IDS
    }
    errors: list[str] = []
    if strict:
        if len(rows) != EXPECTED_ORDER_COUNT:
            errors.append(f"expected {EXPECTED_ORDER_COUNT} orders, found {len(rows)}")
        if not math.isclose(total, EXPECTED_ORDER_QTY_KG, rel_tol=0.0, abs_tol=1e-6):
            errors.append(f"expected {EXPECTED_ORDER_QTY_KG:g} kg, found {total:g}")
        for supplier, expected in EXPECTED_QTY_BY_SUPPLIER.items():
            actual = quantities.get(supplier, 0.0)
            if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-6):
                errors.append(f"{supplier}: expected {expected:g} kg, found {actual:g}")
        if physical_days and (min(physical_days), max(physical_days)) != EXPECTED_PHYSICAL_DAY_RANGE:
            errors.append("physical-delivery range differs from the 2025 source audit")
        if usable_days and (min(usable_days), max(usable_days)) != EXPECTED_USABLE_DAY_RANGE:
            errors.append("usable-day range differs from the 2025 source audit")
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "validated": not errors,
        "source": "Extract_En_cours.xlsx embedded in graph metadata",
        "item_id": ITEM_ID,
        "destination_id": DESTINATION_ID,
        "order_count": len(rows),
        "quantity_kg": total,
        "physical_delivery_day_min": min(physical_days) if physical_days else None,
        "physical_delivery_day_max": max(physical_days) if physical_days else None,
        "usable_day_min": min(usable_days) if usable_days else None,
        "usable_day_max": max(usable_days) if usable_days else None,
        "supplier_rows": [
            {
                "supplier_id": supplier,
                "order_count": counts.get(supplier, 0),
                "quantity_kg": quantities.get(supplier, 0.0),
                "observed_order_book_share": shares[supplier],
            }
            for supplier in SUPPLIER_IDS
        ],
    }


def observed_order_export_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "observed_order_id": order_id(row),
            "evidence_class": "observed_2025",
            "date_semantics": "planned_dates_in_snapshot_not_actual_delivery_history",
            **dict(row),
        }
        for row in sorted(
            rows,
            key=lambda item: (
                to_int(item.get("physical_delivery_day")),
                str(item.get("src_node_id") or ""),
                to_int(item.get("source_row")),
            ),
        )
    ]


def build_scenarios() -> list[Scenario]:
    scenarios = [
        Scenario(
            scenario_id="baseline_observed_order_book",
            scope_id="all_021081",
            mechanism="baseline",
            value=1.0,
            value_unit="reference",
            label="Référence : carnet 2025 rejoué sans dégradation",
            is_baseline=True,
        )
    ]
    scopes = (*SUPPLIER_IDS, "all_021081")
    for scope_id in scopes:
        for mechanism, levels in MECHANISM_LEVELS.items():
            for value, unit in levels:
                scenarios.append(
                    Scenario(
                        scenario_id=(
                            f"{slug(scope_id)}__{mechanism}__{slug_number(value)}"
                        ),
                        scope_id=scope_id,
                        mechanism=mechanism,
                        value=value,
                        value_unit=unit,
                        label=(
                            f"{MECHANISM_LABELS[mechanism]} — "
                            f"{'quatre sources' if scope_id == 'all_021081' else scope_id} — {value:g} {unit}"
                        ),
                    )
                )
    return scenarios


def scenario_design_rows(scenarios: Sequence[Scenario]) -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": scenario.scenario_id,
            "scope_id": scenario.scope_id,
            "scope_type": "common_cause_multisource" if scenario.scope_id == "all_021081" else "isolated_supplier",
            "mechanism": scenario.mechanism,
            "mechanism_label": "Référence" if scenario.is_baseline else MECHANISM_LABELS[scenario.mechanism],
            "mechanism_value": scenario.value,
            "mechanism_unit": scenario.value_unit,
            "is_baseline": scenario.is_baseline,
            "evidence_class": "simulated_hypothesis" if not scenario.is_baseline else "simulated_reference_replaying_observed_orders",
            "label": scenario.label,
        }
        for scenario in scenarios
    ]


def _affected(row: Mapping[str, Any], scenario: Scenario) -> bool:
    if not is_target_order(row) or scenario.is_baseline:
        return False
    return scenario.scope_id == "all_021081" or str(row.get("src_node_id") or "") == scenario.scope_id


def stable_uniform(seed: int, row: Mapping[str, Any], salt: str) -> float:
    payload = f"{seed}|{order_id(row)}|{salt}".encode("utf-8")
    integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return integer / float(2**64)


def _capacity_rescheduled_days(
    rows: Sequence[Mapping[str, Any]], ratio: float
) -> tuple[dict[int, int], dict[str, float]]:
    """FIFO schedule with daily capacity reset; never splits an observed order."""

    result: dict[int, int] = {}
    reference_capacity_by_supplier: dict[str, float] = {}
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("src_node_id") or "")].append(row)
    for supplier, supplier_rows in grouped.items():
        daily_totals: dict[int, float] = defaultdict(float)
        for row in supplier_rows:
            daily_totals[to_int(row.get("physical_delivery_day"))] += max(
                0.0, to_float(row.get("quantity"))
            )
        reference_capacity = max(daily_totals.values(), default=0.0)
        capacity = reference_capacity * max(0.0, ratio)
        if capacity <= 1e-9:
            raise ValueError("Capacity-rationing ratio must leave positive capacity")
        reference_capacity_by_supplier[supplier] = reference_capacity
        current_day: int | None = None
        capacity_left = capacity
        for row in sorted(
            supplier_rows,
            key=lambda item: (
                to_int(item.get("physical_delivery_day")),
                to_int(item.get("source_row")),
            ),
        ):
            original_day = to_int(row.get("physical_delivery_day"))
            if current_day is None or original_day > current_day:
                current_day = original_day
                capacity_left = capacity
            remaining = max(0.0, to_float(row.get("quantity")))
            while remaining > capacity_left + 1e-9:
                remaining -= capacity_left
                current_day += 1
                capacity_left = capacity
            capacity_left = max(0.0, capacity_left - remaining)
            result[to_int(row.get("source_row"), -1)] = current_day
    return result, reference_capacity_by_supplier


def transform_order_book(
    source_rows: Sequence[Mapping[str, Any]],
    scenario: Scenario,
    *,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply one declared hypothesis and return engine rows plus an audit ledger."""

    rows = [dict(row) for row in source_rows]
    capacity_days: dict[int, int] = {}
    reference_capacity: dict[str, float] = {}
    if scenario.mechanism == "capacity_rationing":
        affected_rows = [row for row in rows if _affected(row, scenario)]
        capacity_days, reference_capacity = _capacity_rescheduled_days(
            affected_rows, scenario.value
        )

    ledger: list[dict[str, Any]] = []
    transformed: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        before_qty = max(0.0, to_float(row.get("quantity")))
        before_physical = to_int(row.get("physical_delivery_day"))
        before_usable = to_int(row.get("usable_day"))
        random_score: float | str = ""
        affected = _affected(row, scenario)
        if affected:
            if scenario.mechanism == "delivery_delay":
                delay = int(round(scenario.value))
                row["physical_delivery_day"] = before_physical + delay
                row["usable_day"] = before_usable + delay
            elif scenario.mechanism == "intermittent_delay":
                random_score = stable_uniform(seed, row, scenario.scenario_id)
                if random_score < 0.5:
                    delay = int(round(2.0 * scenario.value))
                    row["physical_delivery_day"] = before_physical + delay
                    row["usable_day"] = before_usable + delay
            elif scenario.mechanism == "quality_hold":
                row["usable_day"] = before_usable + int(round(scenario.value))
            elif scenario.mechanism == "usable_yield":
                row["quantity"] = before_qty * scenario.value
            elif scenario.mechanism == "delivery_availability":
                random_score = stable_uniform(seed, row, scenario.scenario_id)
                if random_score >= scenario.value:
                    row["quantity"] = 0.0
            elif scenario.mechanism == "capacity_rationing":
                new_physical = capacity_days[to_int(row.get("source_row"), -1)]
                release_gap = max(0, before_usable - before_physical)
                row["physical_delivery_day"] = new_physical
                row["usable_day"] = new_physical + release_gap
            else:
                raise ValueError(f"Unknown mechanism: {scenario.mechanism}")

        after_qty = max(0.0, to_float(row.get("quantity")))
        after_physical = to_int(row.get("physical_delivery_day"))
        after_usable = to_int(row.get("usable_day"))
        if after_qty > 1e-9:
            transformed.append(row)
        ledger.append(
            {
                "scenario_id": scenario.scenario_id,
                "seed": seed,
                "observed_order_id": order_id(source),
                "source_row": to_int(source.get("source_row"), -1),
                "supplier_id": str(source.get("src_node_id") or ""),
                "item_id": str(source.get("item_id") or ""),
                "dst_node_id": str(source.get("dst_node_id") or ""),
                "affected_by_hypothesis": affected,
                "mechanism": scenario.mechanism,
                "mechanism_value": scenario.value,
                "mechanism_unit": scenario.value_unit,
                "stable_random_score": random_score,
                "observed_quantity_kg": before_qty,
                "simulated_usable_quantity_kg": after_qty,
                "simulated_quantity_loss_kg": max(0.0, before_qty - after_qty),
                "source_planned_physical_delivery_day": before_physical,
                "simulated_physical_delivery_day": after_physical,
                "planned_physical_date_shift_days": after_physical - before_physical,
                "source_planned_usable_day": before_usable,
                "simulated_usable_day": after_usable,
                "planned_usable_date_shift_days": after_usable - before_usable,
                "simulated_order_received": after_qty > 1e-9,
                "reference_observed_peak_daily_qty_kg": reference_capacity.get(
                    str(source.get("src_node_id") or ""), ""
                ),
                "assumption_not_observation": not scenario.is_baseline,
            }
        )
    return transformed, ledger


def native_opening_order_risk_supported(scenario: Scenario) -> bool:
    """Whether the opt-in engine has an honest firm-order interpretation."""

    # Capacity needs a dated supplier capacity calendar.  The engine correctly
    # reports it as unsupported for pre-placed firm orders; the campaign keeps
    # its explicit FIFO overlay for that one mechanism.
    return scenario.is_baseline or scenario.mechanism != "capacity_rationing"


def raw_order_book_ledger(
    source_rows: Sequence[Mapping[str, Any]],
    scenario: Scenario,
    *,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    baseline_view = Scenario(
        scenario_id=scenario.scenario_id,
        scope_id=scenario.scope_id,
        mechanism="baseline",
        value=1.0,
        value_unit="reference",
        label=scenario.label,
        is_baseline=True,
    )
    rows, ledger = transform_order_book(source_rows, baseline_view, seed=seed)
    for source, item in zip(source_rows, ledger):
        item.update(
            {
                "scenario_id": scenario.scenario_id,
                "affected_by_hypothesis": _affected(source, scenario),
                "mechanism": scenario.mechanism,
                "mechanism_value": scenario.value,
                "mechanism_unit": scenario.value_unit,
                "assumption_not_observation": not scenario.is_baseline,
                "order_risk_application_layer": "engine_native_at_seed",
                "pre_engine_overlay_transformed": False,
            }
        )
    return rows, ledger


def graph_without_target_order_rows(graph: Mapping[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(dict(graph))
    order_payload = opening_order_payload(payload)
    order_payload["rows"] = [
        row for row in order_payload["rows"] if not isinstance(row, Mapping) or not is_target_order(row)
    ]
    order_payload.pop("campaign_overlay", None)
    return payload


def build_graph_overlay(
    graph: Mapping[str, Any],
    scenario: Scenario,
    *,
    seed: int,
    opening_order_risk_mode: str = "overlay",
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    source_orders = observed_orders(graph)
    use_native = (
        opening_order_risk_mode == "engine"
        and native_opening_order_risk_supported(scenario)
    )
    if use_native:
        transformed, ledger = raw_order_book_ledger(
            source_orders, scenario, seed=seed
        )
        application_layer = "engine_native_at_seed"
    else:
        transformed, ledger = transform_order_book(
            source_orders, scenario, seed=seed
        )
        application_layer = (
            "campaign_overlay_capacity_fallback"
            if opening_order_risk_mode == "engine"
            and scenario.mechanism == "capacity_rationing"
            else "campaign_graph_overlay"
        )
        for item in ledger:
            item["order_risk_application_layer"] = application_layer
            item["pre_engine_overlay_transformed"] = not scenario.is_baseline
    overlay = copy.deepcopy(dict(graph))
    payload = opening_order_payload(overlay)
    untouched_rows = [
        copy.deepcopy(row)
        for row in payload["rows"]
        if not isinstance(row, Mapping) or not is_target_order(row)
    ]
    payload["rows"] = [*untouched_rows, *transformed]
    payload["campaign_overlay"] = {
        "schema_version": "supplier-021081-order-overlay.v1",
        "scenario_id": scenario.scenario_id,
        "seed": seed,
        "source_order_count": len(source_orders),
        "simulated_positive_order_count": len(transformed),
        "source_order_qty_kg": sum(to_float(row.get("quantity")) for row in source_orders),
        "simulated_usable_order_qty_kg": sum(to_float(row.get("quantity")) for row in transformed),
        "mechanism": scenario.mechanism,
        "mechanism_value": scenario.value,
        "scope_id": scenario.scope_id,
        "observed_rows_preserved_outside_target": True,
        "order_risk_application_layer": application_layer,
        "engine_native_opening_order_risk_enabled": use_native,
    }
    core_before = json_sha256(graph_without_target_order_rows(graph))
    core_after = json_sha256(graph_without_target_order_rows(overlay))
    if core_before != core_after:
        raise CampaignValidationError("Overlay changed graph content outside the target order rows")
    audit = {
        "source_graph_core_without_target_orders_sha256": core_before,
        "overlay_graph_core_without_target_orders_sha256": core_after,
        "non_target_graph_and_order_book_preserved": True,
        "target_source_order_count": len(source_orders),
        "target_overlay_positive_order_count": len(transformed),
        "target_source_qty_kg": sum(to_float(row.get("quantity")) for row in source_orders),
        "target_overlay_usable_qty_kg": sum(to_float(row.get("quantity")) for row in transformed),
        "order_risk_application_layer": application_layer,
        "engine_native_opening_order_risk_enabled": use_native,
    }
    return overlay, ledger, audit


def risk_event_rows(scenario: Scenario, days: int) -> list[dict[str, Any]]:
    """Risk layer for new MRP orders; the order-book layer is handled above."""

    if scenario.is_baseline:
        return []
    suppliers = SUPPLIER_IDS if scenario.scope_id == "all_021081" else (scenario.scope_id,)
    type_and_value = {
        "delivery_delay": ("lead_time_extra_days", scenario.value),
        "quality_hold": ("quality_delay", scenario.value),
        "usable_yield": ("quality_yield", scenario.value),
        "delivery_availability": ("availability", scenario.value),
        "capacity_rationing": ("capacity", scenario.value),
    }
    rows: list[dict[str, Any]] = []
    if scenario.mechanism == "intermittent_delay":
        # Four active 23-day windows among alternating 23-day blocks give a
        # declared temporal mean close to the order-overlay construction.
        start = 0
        block = 23
        for supplier in suppliers:
            for window_index in range(4):
                window_start = start + window_index * 2 * block
                rows.append(
                    {
                        "event_id": f"{scenario.scenario_id}__{slug(supplier)}__w{window_index + 1}",
                        "risk_type": "lead_time_extra_days",
                        "supplier_id": supplier,
                        "item_id": ITEM_ID,
                        "dst_node_id": DESTINATION_ID,
                        "edge_id": "",
                        "start_day": window_start,
                        "end_day": min(days - 1, window_start + block - 1),
                        "multiplier": 2.0 * scenario.value,
                        "notes": "Dynamic MRP orders only; observed firm orders are transformed in the overlay ledger.",
                    }
                )
        return rows
    risk_type, multiplier = type_and_value[scenario.mechanism]
    for supplier in suppliers:
        rows.append(
            {
                "event_id": f"{scenario.scenario_id}__{slug(supplier)}",
                "risk_type": risk_type,
                "supplier_id": supplier,
                "item_id": ITEM_ID,
                "dst_node_id": DESTINATION_ID,
                "edge_id": "",
                "start_day": 0,
                "end_day": min(days - 1, EXPECTED_USABLE_DAY_RANGE[1]),
                "multiplier": multiplier,
                "notes": "Dynamic MRP orders only; observed firm orders are transformed in the overlay ledger.",
            }
        )
    return rows


def build_engine_command(
    *,
    engine: Path,
    graph: Path,
    output_dir: Path,
    profile_args: Sequence[str],
    days: int,
    seed: int,
    risk_csv: Path | None,
    apply_risk_to_opening_orders: bool = False,
    measurement_start_stock_scale_csv: Path | None = None,
) -> list[str]:
    command = [
        sys.executable,
        str(engine),
        "--input",
        str(graph),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        "scn:SUPPLIER_021081_ACTIVE_FLOW",
        "--days",
        str(days),
        "--seed",
        str(seed),
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--lot-trace",
        "--skip-lot-audit",
        "--common-random-numbers",
        *profile_args,
        *ACTIVE_021081_PROTOCOL_ARGS,
        *(
            ["--supplier-risk-events-apply-to-opening-purchase-orders"]
            if apply_risk_to_opening_orders
            else ["--no-supplier-risk-events-apply-to-opening-purchase-orders"]
        ),
    ]
    if risk_csv is not None:
        command.extend(["--supplier-risk-events-csv", str(risk_csv)])
    if measurement_start_stock_scale_csv is not None:
        command.extend(
            [
                "--measurement-start-stock-scale-csv",
                str(measurement_start_stock_scale_csv),
            ]
        )
    return command


def normalized_engine_command(command: Sequence[str]) -> list[str]:
    """Normalize case-local paths while preserving every engine option/value."""

    path_options = {
        "--input": "<CASE_GRAPH_OVERLAY>",
        "--output-dir": "<CASE_OUTPUT_DIR>",
        "--supplier-risk-events-csv": "<CASE_RISK_CSV>",
        "--measurement-start-stock-scale-csv": "<STATE_STOCK_SCALE_CSV>",
    }
    output = ["<PYTHON_EXECUTABLE>", "<ENGINE_SCRIPT>"]
    index = 2
    while index < len(command):
        value = str(command[index])
        output.append(value)
        if value in path_options and index + 1 < len(command):
            output.append(path_options[value])
            index += 2
        else:
            index += 1
    return output


def _target_shipments(rows: Iterable[Mapping[str, Any]], days: int) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    target = [
        row
        for row in rows
        if str(row.get("src_node_id") or "") in SUPPLIER_IDS
        and str(row.get("dst_node_id") or "") == DESTINATION_ID
        and str(row.get("item_id") or "") == ITEM_ID
        and 0 <= to_int(row.get("arrival_day"), -1) < days
    ]
    replayed = [row for row in target if str(row.get("transport_cost_basis") or "") == "opening_order_book"]
    dynamic = [row for row in target if row not in replayed]
    return replayed, dynamic


def _sum(rows: Iterable[Mapping[str, Any]], field: str) -> float:
    return sum(max(0.0, to_float(row.get(field))) for row in rows)


def intermediate_measurement_start_qty(
    *,
    node_id: str,
    adjustment_rows: Sequence[Mapping[str, Any]],
    opening_lot_events: Sequence[Mapping[str, Any]],
    input_stock_rows: Sequence[Mapping[str, Any]],
) -> float:
    """Resolve J0 773474 stock from the correct physical evidence layer.

    A measurement-start adjustment is authoritative when a hypothesis scales
    stock. Otherwise the native opening-stock lot is used. The input-stock
    extract is only a final fallback because 773474 is an output at SDC-1450
    and is consequently absent from that extract there.
    """

    adjustment = next(
        (
            item
            for item in adjustment_rows
            if str(item.get("node_id") or "") == node_id
        ),
        None,
    )
    if adjustment is not None:
        return to_float(adjustment.get("stock_after_qty"), math.nan)
    opening_qty = sum(
        max(0.0, to_float(item.get("qty")))
        for item in opening_lot_events
        if str(item.get("event_type") or "") == "opening_stock"
        and str(item.get("item_id") or "") == INTERMEDIATE_ITEM_ID
        and str(item.get("node_id") or "") == node_id
    )
    if opening_qty > 1e-9:
        return opening_qty
    node_rows = sorted(
        (
            item
            for item in input_stock_rows
            if str(item.get("node_id") or "") == node_id
        ),
        key=lambda item: to_int(item.get("day"), -1),
    )
    return (
        to_float(node_rows[0].get("stock_before_production"), math.nan)
        if node_rows
        else math.nan
    )


def intermediate_production_supply_quantities(
    lot_events: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    dynamic_qty = sum(
        max(0.0, to_float(item.get("qty")))
        for item in lot_events
        if str(item.get("event_type") or "") == "production_output"
        and str(item.get("item_id") or "") == INTERMEDIATE_ITEM_ID
        and str(item.get("node_id") or "") == DESTINATION_ID
    )
    opening_order_qty = sum(
        max(0.0, to_float(item.get("qty")))
        for item in lot_events
        if str(item.get("event_type") or "") == "opening_production_order"
        and str(item.get("item_id") or "") == INTERMEDIATE_ITEM_ID
        and str(item.get("node_id") or "") == DESTINATION_ID
    )
    return {
        "dynamic_production_qty_g": dynamic_qty,
        "opening_production_order_receipt_qty_g": opening_order_qty,
        "total_production_supply_qty_g": dynamic_qty + opening_order_qty,
    }


def reconcile_replayed_receipts(
    initialization_rows: Sequence[Mapping[str, Any]],
    arrival_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], float]:
    """Reconcile planned firm receipts against aggregate engine arrivals by day.

    The aggregate arrival CSV does not carry an opening-order identifier.  We
    therefore reconcile the initialized firm pipeline and the measured target
    receipts day by day.  Any excess remains classified as dynamic/other and
    can never inflate the replay gate.
    """

    planned_by_day: dict[int, float] = defaultdict(float)
    actual_by_day: dict[int, float] = defaultdict(float)
    for row in initialization_rows:
        planned_by_day[to_int(row.get("usable_day"), -1)] += max(
            0.0, to_float(row.get("seeded_pipeline_qty"))
        )
    for row in arrival_rows:
        actual_by_day[to_int(row.get("day"), -1)] += max(
            0.0, to_float(row.get("arrived_qty"))
        )
    evidence: list[dict[str, Any]] = []
    reconciled_total = 0.0
    for day in sorted(set(planned_by_day) | set(actual_by_day)):
        planned = planned_by_day.get(day, 0.0)
        actual = actual_by_day.get(day, 0.0)
        reconciled = min(planned, actual)
        reconciled_total += reconciled
        evidence.append(
            {
                "day": day,
                "replayed_pipeline_planned_receipt_qty_kg": planned,
                "aggregate_target_arrival_qty_kg": actual,
                "replayed_receipt_reconciled_qty_kg": reconciled,
                "dynamic_or_other_arrival_qty_kg": max(0.0, actual - reconciled),
                "unreconciled_replayed_receipt_qty_kg": max(0.0, planned - actual),
            }
        )
    return evidence, reconciled_total


def _service_metrics(rows: Iterable[Mapping[str, Any]], days: int) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if str(row.get("node_id") or "") == TARGET_CLIENT_ID
        and str(row.get("item_id") or "") == TARGET_PRODUCT_ID
        and 0 <= to_int(row.get("day"), -1) < days
    ]
    demand = _sum(selected, "demand_qty")
    served = _sum(selected, "served_qty")
    backlog_values = [max(0.0, to_float(row.get("backlog_end_qty"))) for row in selected]
    on_due = sum(
        min(max(0.0, to_float(row.get("demand_qty"))), max(0.0, to_float(row.get("served_qty"))))
        for row in selected
    )
    return {
        "product_demand_qty": demand,
        "product_served_qty": served,
        "product_service_horizon": min(1.0, served / demand) if demand else 1.0,
        "product_on_due_volume_proxy": min(1.0, on_due / demand) if demand else 1.0,
        "product_backlog_qty_days": sum(backlog_values),
        "product_backlog_days": sum(value > 1e-9 for value in backlog_values),
        "product_max_backlog_qty": max(backlog_values, default=0.0),
        "product_service_day_count": len(selected),
    }


def _filtered_lot_proof(case_dir: Path, proof_dir: Path) -> dict[str, Any]:
    event_rows = read_csv_rows(case_dir / "data" / "production_lot_events.csv")
    genealogy_rows = read_csv_rows(case_dir / "data" / "production_lot_genealogy.csv")
    chain_items = {ITEM_ID, INTERMEDIATE_ITEM_ID, TARGET_PRODUCT_ID}
    selected_events = [row for row in event_rows if str(row.get("item_id") or "") in chain_items]
    selected_genealogy = [
        row
        for row in genealogy_rows
        if str(row.get("parent_item_id") or "") in chain_items
        or str(row.get("child_item_id") or "") in chain_items
    ]
    write_csv(proof_dir / "lot_events_021081_773474_268967.csv", selected_events)
    write_csv(proof_dir / "lot_genealogy_021081_773474_268967.csv", selected_genealogy)
    receipt_lots = [
        row
        for row in selected_events
        if str(row.get("node_id") or "") == DESTINATION_ID
        and str(row.get("item_id") or "") == ITEM_ID
        and str(row.get("event_type") or "")
        in {"lane_receipt", "create", "opening_purchase_order_receipt"}
    ]
    return {
        "chain_lot_event_rows": len(selected_events),
        "chain_lot_genealogy_rows": len(selected_genealogy),
        "target_component_receipt_lot_rows": len(receipt_lots),
        "target_component_receipt_lot_qty": _sum(receipt_lots, "qty"),
        "native_open_order_supplier_identity_on_receipt_lot": all(
            str(row.get("source_id") or "").strip() for row in receipt_lots
        ) if receipt_lots else False,
    }


def extract_case(
    *,
    case_dir: Path,
    scenario: Scenario,
    seed: int,
    stage: str,
    days: int,
    overlay_ledger: Sequence[Mapping[str, Any]],
    overlay_audit: Mapping[str, Any],
) -> dict[str, Any]:
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    if not summary_path.exists():
        raise CampaignValidationError(f"Missing engine summary: {summary_path}")
    summary = read_json(summary_path)
    policy = summary.get("policy") if isinstance(summary.get("policy"), Mapping) else {}
    initialization = (
        policy.get("initialization_policy")
        if isinstance(policy.get("initialization_policy"), Mapping)
        else {}
    )
    economic = (
        policy.get("economic_policy")
        if isinstance(policy.get("economic_policy"), Mapping)
        else {}
    )
    shipments = read_csv_rows(case_dir / "data" / "production_supplier_shipments_daily.csv")
    replayed, dynamic = _target_shipments(shipments, days)
    arrivals = [
        row
        for row in read_csv_rows(case_dir / "data" / "production_input_replenishment_arrivals_daily.csv")
        if str(row.get("node_id") or "") == DESTINATION_ID
        and str(row.get("item_id") or "") == ITEM_ID
        and 0 <= to_int(row.get("day"), -1) < days
    ]
    init_pipeline = [
        row
        for row in read_csv_rows(case_dir / "data" / "initialization_pipeline.csv")
        if str(row.get("category") or "") == "opening_open_order_book_real"
        and str(row.get("node_id") or "") == DESTINATION_ID
        and str(row.get("item_id") or "") == ITEM_ID
    ]
    opening_order_risk_audit = [
        row
        for row in read_csv_rows(
            case_dir
            / "data"
            / "opening_purchase_order_supplier_risk_audit.csv"
        )
        if str(row.get("supplier_id") or "") in SUPPLIER_IDS
        and str(row.get("dst_node_id") or "") == DESTINATION_ID
        and str(row.get("item_id") or "") == ITEM_ID
    ]
    all_service_rows = read_csv_rows(
        case_dir / "data" / "production_demand_service_daily.csv"
    )
    service = _service_metrics(all_service_rows, days)
    target_service_daily = [
        row
        for row in all_service_rows
        if str(row.get("node_id") or "") == TARGET_CLIENT_ID
        and str(row.get("item_id") or "") == TARGET_PRODUCT_ID
        and 0 <= to_int(row.get("day"), -1) < days
    ]
    all_input_stock_rows = read_csv_rows(
        case_dir / "data" / "production_input_stocks_daily.csv"
    )
    stock_rows = [
        row
        for row in all_input_stock_rows
        if str(row.get("node_id") or "") == DESTINATION_ID
        and str(row.get("item_id") or "") == ITEM_ID
        and 0 <= to_int(row.get("day"), -1) < days
    ]
    intermediate_stock_rows = [
        row
        for row in all_input_stock_rows
        if str(row.get("node_id") or "")
        in {DESTINATION_ID, "M-1430"}
        and str(row.get("item_id") or "") == INTERMEDIATE_ITEM_ID
        and 0 <= to_int(row.get("day"), -1) < days
    ]
    component_consumed_qty = sum(
        max(
            0.0,
            to_float(item.get("stock_before_production"))
            - to_float(item.get("stock_end_of_day")),
        )
        for item in stock_rows
    )
    all_measurement_stock_adjustments = read_csv_rows(
        case_dir / "data" / "measurement_start_stock_adjustments.csv"
    )
    measurement_stock_adjustments = [
        row
        for row in all_measurement_stock_adjustments
        if str(row.get("node_id") or "") == DESTINATION_ID
        and str(row.get("item_id") or "") == ITEM_ID
    ]
    intermediate_stock_adjustments = [
        row
        for row in all_measurement_stock_adjustments
        if str(row.get("node_id") or "")
        in {DESTINATION_ID, "M-1430"}
        and str(row.get("item_id") or "") == INTERMEDIATE_ITEM_ID
    ]
    output_product_rows = [
        row
        for row in read_csv_rows(
            case_dir / "data" / "production_output_products_daily.csv"
        )
        if str(row.get("item_id") or "")
        in {INTERMEDIATE_ITEM_ID, TARGET_PRODUCT_ID}
        and 0 <= to_int(row.get("day"), -1) < days
    ]
    proof_dir = case_dir / "proofs"
    lot_metrics = _filtered_lot_proof(case_dir, proof_dir)
    chain_lot_events = read_csv_rows(
        proof_dir / "lot_events_021081_773474_268967.csv"
    )
    write_csv(proof_dir / "target_supplier_shipments_replayed.csv", replayed)
    write_csv(proof_dir / "target_supplier_shipments_dynamic.csv", dynamic)
    write_csv(proof_dir / "target_component_receipts.csv", arrivals)
    write_csv(proof_dir / "opening_order_initialization_rows.csv", init_pipeline)
    write_csv(proof_dir / "order_book_overlay_ledger.csv", list(overlay_ledger))
    write_csv(
        proof_dir / "opening_purchase_order_supplier_risk_audit_021081.csv",
        opening_order_risk_audit,
    )
    write_csv(
        proof_dir / "measurement_start_stock_adjustment_021081.csv",
        measurement_stock_adjustments,
    )
    write_csv(
        proof_dir / "measurement_start_stock_adjustment_773474.csv",
        intermediate_stock_adjustments,
    )
    write_csv(
        proof_dir / "production_outputs_773474_268967.csv",
        output_product_rows,
    )
    receipt_reconciliation, replayed_received_qty = reconcile_replayed_receipts(
        init_pipeline, arrivals
    )
    write_csv(
        proof_dir / "replayed_receipt_reconciliation_by_day.csv",
        receipt_reconciliation,
    )

    observed_qty = _sum(overlay_ledger, "observed_quantity_kg")
    overlay_usable_qty = _sum(overlay_ledger, "simulated_usable_quantity_kg")
    native_audit_planned_qty = _sum(
        opening_order_risk_audit, "planned_qty_before"
    )
    native_audit_usable_qty = _sum(
        opening_order_risk_audit, "usable_qty_after"
    )
    native_weighted_usable_shift = (
        sum(
            max(0.0, to_float(item.get("planned_qty_before")))
            * max(
                0.0,
                to_float(item.get("usable_day_after"))
                - to_float(item.get("usable_day_before")),
            )
            for item in opening_order_risk_audit
        )
        / native_audit_planned_qty
        if native_audit_planned_qty > 1e-9
        else 0.0
    )
    realization_signature = json_sha256(
        {
            "opening_orders": [
                {
                    key: row.get(key, "")
                    for key in (
                        "source_row",
                        "supplier_id",
                        "planned_qty_before",
                        "physical_shipped_qty_after",
                        "usable_qty_after",
                        "physical_delivery_day_after",
                        "usable_day_after",
                    )
                }
                for row in opening_order_risk_audit
            ]
            if opening_order_risk_audit
            else [
                {
                    key: row.get(key, "")
                    for key in (
                        "source_row",
                        "supplier_id",
                        "simulated_usable_quantity_kg",
                        "simulated_physical_delivery_day",
                        "simulated_usable_day",
                    )
                }
                for row in overlay_ledger
            ],
            "target_service_daily": target_service_daily,
            "component_stock_daily": stock_rows,
        }
    )
    application_layer = str(
        overlay_audit.get("order_risk_application_layer") or ""
    )
    if application_layer == "engine_native_at_seed":
        order_book_usable_qty = native_audit_usable_qty
        order_book_quantity_loss = max(
            0.0, native_audit_planned_qty - native_audit_usable_qty
        )
        order_book_weighted_shift = native_weighted_usable_shift
        order_book_after_horizon_qty = sum(
            max(0.0, to_float(item.get("usable_qty_after")))
            for item in opening_order_risk_audit
            if to_int(item.get("usable_day_after"), -1) >= days
        )
        order_book_after_horizon_rows = sum(
            to_int(item.get("usable_day_after"), -1) >= days
            for item in opening_order_risk_audit
        )
    else:
        order_book_usable_qty = overlay_usable_qty
        order_book_quantity_loss = max(0.0, observed_qty - overlay_usable_qty)
        order_book_weighted_shift = (
            sum(
                to_float(item.get("observed_quantity_kg"))
                * max(
                    0.0,
                    to_float(
                        item.get("planned_usable_date_shift_days")
                    ),
                )
                for item in overlay_ledger
            )
            / observed_qty
            if observed_qty > 0
            else 0.0
        )
        order_book_after_horizon_qty = sum(
            max(0.0, to_float(item.get("simulated_usable_quantity_kg")))
            for item in overlay_ledger
            if to_int(item.get("simulated_usable_day"), -1) >= days
        )
        order_book_after_horizon_rows = sum(
            to_int(item.get("simulated_usable_day"), -1) >= days
            for item in overlay_ledger
        )

    intermediate_by_node: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    intermediate_total_end_by_day: dict[int, float] = defaultdict(float)
    for item in intermediate_stock_rows:
        node_id = str(item.get("node_id") or "")
        intermediate_by_node[node_id].append(item)
        intermediate_total_end_by_day[to_int(item.get("day"), -1)] += to_float(
            item.get("stock_end_of_day")
        )

    def measurement_start_for_intermediate(node_id: str) -> float:
        return intermediate_measurement_start_qty(
            node_id=node_id,
            adjustment_rows=intermediate_stock_adjustments,
            opening_lot_events=chain_lot_events,
            input_stock_rows=intermediate_stock_rows,
        )

    intermediate_sdc_rows = intermediate_by_node.get(DESTINATION_ID, [])
    intermediate_m1430_rows = intermediate_by_node.get("M-1430", [])
    intermediate_production_supply = intermediate_production_supply_quantities(
        chain_lot_events
    )
    row: dict[str, Any] = {
        "stage": stage,
        "scenario_id": scenario.scenario_id,
        "scope_id": scenario.scope_id,
        "mechanism": scenario.mechanism,
        "mechanism_value": scenario.value,
        "mechanism_unit": scenario.value_unit,
        "seed": seed,
        "days": days,
        "observed_order_count": len(overlay_ledger),
        "observed_order_qty_kg": observed_qty,
        "simulation_outcome_sha256": realization_signature,
        "opening_order_risk_application_layer": application_layer,
        "opening_order_native_risk_audit_rows": len(opening_order_risk_audit),
        "opening_order_native_planned_qty_kg": native_audit_planned_qty,
        "opening_order_native_usable_qty_kg": native_audit_usable_qty,
        "opening_order_native_unsupported_risk_rows": sum(
            bool(str(item.get("unsupported_risk_types") or "").strip())
            for item in opening_order_risk_audit
        ),
        "opening_order_native_risk_applied_rows": sum(
            bool(str(item.get("risk_event_ids") or "").strip())
            for item in opening_order_risk_audit
        ),
        "overlay_positive_order_count": sum(
            to_float(item.get("simulated_usable_quantity_kg")) > 1e-9 for item in overlay_ledger
        ),
        "overlay_usable_order_qty_kg": overlay_usable_qty,
        "order_book_simulated_usable_qty_kg": order_book_usable_qty,
        "order_book_simulated_quantity_loss_kg": order_book_quantity_loss,
        "order_book_weighted_planned_usable_date_shift_days": order_book_weighted_shift,
        "order_book_after_horizon_qty_kg": order_book_after_horizon_qty,
        "order_book_after_horizon_rows": order_book_after_horizon_rows,
        "recovery_interpretation": (
            "receipt_outside_horizon_no_recovery_day_claimed"
            if order_book_after_horizon_qty > 1e-9
            else "all_simulated_firm_receipts_within_horizon"
        ),
        # Backward-compatible internal names consumed by the summary helpers.
        "overlay_quantity_loss_kg": order_book_quantity_loss,
        "overlay_weighted_usable_delay_days": order_book_weighted_shift,
        "replayed_shipment_rows": len(replayed),
        "replayed_pulled_qty_kg": _sum(replayed, "pulled_qty"),
        "replayed_shipped_qty_kg": _sum(replayed, "shipped_qty"),
        "dynamic_shipment_rows": len(dynamic),
        "dynamic_pulled_qty_kg": _sum(dynamic, "pulled_qty"),
        "dynamic_shipped_qty_kg": _sum(dynamic, "shipped_qty"),
        "measured_receipt_rows": len(arrivals),
        "measured_received_qty_kg": _sum(arrivals, "arrived_qty"),
        "replayed_received_reconciled_qty_kg": replayed_received_qty,
        "dynamic_or_other_received_qty_kg": max(
            0.0, _sum(arrivals, "arrived_qty") - replayed_received_qty
        ),
        "opening_pipeline_proof_rows": len(init_pipeline),
        "opening_pipeline_seeded_qty_kg": _sum(init_pipeline, "seeded_pipeline_qty"),
        "component_stock_min_qty_kg": min(
            (to_float(item.get("stock_end_of_day")) for item in stock_rows), default=math.nan
        ),
        "component_stock_final_qty_kg": (
            to_float(stock_rows[-1].get("stock_end_of_day")) if stock_rows else math.nan
        ),
        "component_consumed_qty_kg": component_consumed_qty,
        "component_consumed_avg_qty_per_day": (
            component_consumed_qty / len(stock_rows) if stock_rows else math.nan
        ),
        "intermediate_773474_measurement_start_sdc_1450_qty_g": (
            measurement_start_for_intermediate(DESTINATION_ID)
        ),
        "intermediate_773474_measurement_start_m_1430_qty_g": (
            measurement_start_for_intermediate("M-1430")
        ),
        "intermediate_773474_measurement_start_total_qty_g": (
            measurement_start_for_intermediate(DESTINATION_ID)
            + measurement_start_for_intermediate("M-1430")
        ),
        "intermediate_773474_min_sdc_1450_qty_g": min(
            (
                to_float(item.get("stock_end_of_day"))
                for item in intermediate_sdc_rows
            ),
            default=math.nan,
        ),
        "intermediate_773474_min_m_1430_qty_g": min(
            (
                to_float(item.get("stock_end_of_day"))
                for item in intermediate_m1430_rows
            ),
            default=math.nan,
        ),
        "intermediate_773474_min_total_qty_g": min(
            intermediate_total_end_by_day.values(), default=math.nan
        ),
        "intermediate_773474_final_total_qty_g": (
            intermediate_total_end_by_day[
                max(intermediate_total_end_by_day)
            ]
            if intermediate_total_end_by_day
            else math.nan
        ),
        "intermediate_773474_produced_qty_g": sum(
            max(0.0, to_float(item.get("produced_qty")))
            for item in output_product_rows
            if str(item.get("item_id") or "") == INTERMEDIATE_ITEM_ID
        ),
        "intermediate_773474_dynamic_production_qty_g": (
            intermediate_production_supply["dynamic_production_qty_g"]
        ),
        "intermediate_773474_opening_production_order_receipt_qty_g": (
            intermediate_production_supply[
                "opening_production_order_receipt_qty_g"
            ]
        ),
        "intermediate_773474_total_production_supply_qty_g": (
            intermediate_production_supply["total_production_supply_qty_g"]
        ),
        "intermediate_773474_production_semantics": (
            "dynamic production + already-open production-order receipt; "
            "the 28.8M G reference control applies only to dynamic production"
        ),
        "intermediate_773474_released_qty_g": sum(
            max(0.0, to_float(item.get("released_qty")))
            for item in output_product_rows
            if str(item.get("item_id") or "") == INTERMEDIATE_ITEM_ID
        ),
        "product_268967_produced_qty": sum(
            max(0.0, to_float(item.get("produced_qty")))
            for item in output_product_rows
            if str(item.get("item_id") or "") == TARGET_PRODUCT_ID
        ),
        "product_268967_released_qty": sum(
            max(0.0, to_float(item.get("released_qty")))
            for item in output_product_rows
            if str(item.get("item_id") or "") == TARGET_PRODUCT_ID
        ),
        "measurement_start_stock_adjustment_rows": len(
            measurement_stock_adjustments
        ),
        "measurement_start_stock_before_qty_kg": (
            to_float(measurement_stock_adjustments[0].get("stock_before_qty"))
            if measurement_stock_adjustments
            else to_float(stock_rows[0].get("stock_before_production"), math.nan)
            if stock_rows
            else math.nan
        ),
        "measurement_start_stock_after_qty_kg": (
            to_float(measurement_stock_adjustments[0].get("stock_after_qty"))
            if measurement_stock_adjustments
            else to_float(stock_rows[0].get("stock_before_production"), math.nan)
            if stock_rows
            else math.nan
        ),
        "non_target_graph_and_order_book_preserved": bool(
            overlay_audit.get("non_target_graph_and_order_book_preserved")
        ),
        "resolved_warmup_days": to_int(summary.get("warmup_days"), -1),
        "resolved_initial_state_scale": to_float(
            initialization.get("state_scale"), math.nan
        ),
        "resolved_seed_open_orders_from_snapshot": bool(
            initialization.get("seed_open_orders_from_january_snapshot")
        ),
        "resolved_opening_open_order_source": str(
            initialization.get("opening_open_order_source") or ""
        ),
        "resolved_seed_estimated_source_pipeline": bool(
            initialization.get("seed_estimated_source_pipeline")
        ),
        "resolved_mrp_dynamic_requirement_pairs": ";".join(
            sorted(initialization.get("mrp_dynamic_requirement_pairs") or [])
        ),
        "resolved_mrp_smoothed_cover_requirement_pairs": ";".join(
            sorted(
                initialization.get("mrp_smoothed_cover_requirement_pairs") or []
            )
        ),
        "resolved_external_procurement_seed_upstream_pipeline": bool(
            economic.get("external_procurement_seed_upstream_pipeline")
        ),
        "resolved_external_procurement_pipeline_fill_ratio": to_float(
            economic.get("external_procurement_upstream_pipeline_fill_ratio"),
            math.nan,
        ),
        "resolved_lot_trace_enabled": bool(
            policy.get("lot_trace_enabled")
            if "lot_trace_enabled" in policy
            else summary.get("production_tracking", {})
            .get("lot_trace", {})
            .get("enabled")
        ),
        **service,
        **lot_metrics,
    }
    return row


def reference_flow_gate(row: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if to_int(row.get("observed_order_count")) != EXPECTED_ORDER_COUNT:
        errors.append("the 23 observed orders were not present in the overlay ledger")
    if to_float(row.get("replayed_pulled_qty_kg")) <= 1e-9:
        errors.append("replayed pulled_qty is zero")
    if to_float(row.get("replayed_shipped_qty_kg")) <= 1e-9:
        errors.append("replayed shipped_qty is zero")
    if to_float(row.get("replayed_received_reconciled_qty_kg")) <= 1e-9:
        errors.append("reconciled replayed 021081 receipts are zero")
    if to_int(row.get("opening_pipeline_proof_rows")) != EXPECTED_ORDER_COUNT:
        errors.append("initialization pipeline does not contain the 23 target orders")
    for field in (
        "observed_order_qty_kg",
        "replayed_pulled_qty_kg",
        "replayed_shipped_qty_kg",
        "replayed_received_reconciled_qty_kg",
        "opening_pipeline_seeded_qty_kg",
    ):
        if not math.isclose(
            to_float(row.get(field)), EXPECTED_ORDER_QTY_KG, rel_tol=0.0, abs_tol=1e-4
        ):
            errors.append(f"{field} does not reconcile to {EXPECTED_ORDER_QTY_KG:g} kg")
    if not bool(row.get("non_target_graph_and_order_book_preserved")):
        errors.append("the overlay preservation audit failed")
    if to_int(row.get("resolved_warmup_days"), -1) != 0:
        errors.append("snapshot replay was shifted behind a prospective warm-up")
    if not math.isclose(
        to_float(row.get("resolved_initial_state_scale"), math.nan),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        errors.append("snapshot replay did not preserve state scale x1")
    if not bool(row.get("resolved_seed_open_orders_from_snapshot")):
        errors.append("engine did not seed the snapshot open order book")
    if "Extract_En_cours.xlsx" not in str(
        row.get("resolved_opening_open_order_source") or ""
    ):
        errors.append("engine did not report Extract_En_cours.xlsx as order source")
    if "SDC-1450|item:021081" not in str(
        row.get("resolved_mrp_dynamic_requirement_pairs") or ""
    ).split(";"):
        errors.append("021081 is not a dynamic MRP requirement pair")
    if "SDC-1450|item:021081" not in str(
        row.get("resolved_mrp_smoothed_cover_requirement_pairs") or ""
    ).split(";"):
        errors.append("021081 cover requirement is not smoothed")
    if not bool(row.get("resolved_seed_estimated_source_pipeline")):
        errors.append("native estimated-source pipeline was not enabled")
    if not bool(row.get("resolved_external_procurement_seed_upstream_pipeline")):
        errors.append("native upstream supplier pipeline was not enabled")
    if not math.isclose(
        to_float(
            row.get("resolved_external_procurement_pipeline_fill_ratio"),
            math.nan,
        ),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        errors.append("upstream supplier pipeline fill ratio is not x1")
    if not bool(row.get("resolved_lot_trace_enabled")):
        errors.append("native lot trace is disabled")
    if str(row.get("opening_order_risk_application_layer") or "") == "engine_native_at_seed":
        if to_int(row.get("opening_order_native_risk_audit_rows")) != EXPECTED_ORDER_COUNT:
            errors.append("native opening-order audit does not contain the 23 target orders")
        if not math.isclose(
            to_float(row.get("opening_order_native_planned_qty_kg")),
            EXPECTED_ORDER_QTY_KG,
            rel_tol=0.0,
            abs_tol=1e-4,
        ):
            errors.append("native opening-order audit does not reconcile planned quantity")
    return {
        "validated": not errors,
        "errors": errors,
        "window_definition": (
            "firm order-book planned delivery dates J6-J139 and planned usable "
            "dates J112-J261; these are snapshot dates, not actual-delivery history"
        ),
        "replayed_pulled_qty_kg": to_float(row.get("replayed_pulled_qty_kg")),
        "replayed_shipped_qty_kg": to_float(row.get("replayed_shipped_qty_kg")),
        "replayed_received_reconciled_qty_kg": to_float(
            row.get("replayed_received_reconciled_qty_kg")
        ),
        "aggregate_received_qty_kg": to_float(row.get("measured_received_qty_kg")),
        "dynamic_or_other_received_qty_kg": to_float(
            row.get("dynamic_or_other_received_qty_kg")
        ),
        "dynamic_pulled_qty_kg": to_float(row.get("dynamic_pulled_qty_kg")),
        "dynamic_shipped_qty_kg": to_float(row.get("dynamic_shipped_qty_kg")),
    }


def paired_metrics(row: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["paired_baseline_product_on_due_volume_proxy"] = to_float(
        baseline.get("product_on_due_volume_proxy"), 1.0
    )
    result["product_on_due_delta_vs_paired_baseline"] = to_float(
        row.get("product_on_due_volume_proxy"), 1.0
    ) - to_float(baseline.get("product_on_due_volume_proxy"), 1.0)
    result["product_backlog_qty_days_delta_vs_paired_baseline"] = to_float(
        row.get("product_backlog_qty_days")
    ) - to_float(baseline.get("product_backlog_qty_days"))
    result["component_stock_min_delta_vs_paired_baseline_kg"] = to_float(
        row.get("component_stock_min_qty_kg")
    ) - to_float(baseline.get("component_stock_min_qty_kg"))
    result["replayed_received_delta_vs_observed_kg"] = to_float(
        row.get("replayed_received_reconciled_qty_kg")
    ) - EXPECTED_ORDER_QTY_KG
    return result


def scenario_score(
    row: Mapping[str, Any],
) -> tuple[float, float, float, float, str]:
    return (
        max(0.0, -to_float(row.get("product_on_due_delta_vs_paired_baseline"))),
        max(0.0, to_float(row.get("product_backlog_qty_days_delta_vs_paired_baseline"))),
        to_float(row.get("overlay_quantity_loss_kg")),
        to_float(row.get("overlay_weighted_usable_delay_days")),
        str(row.get("scenario_id") or ""),
    )


def select_confirmation_scenarios(
    rows: Sequence[Mapping[str, Any]],
    scenarios: Sequence[Scenario],
    *,
    top_per_scope: int,
) -> list[Scenario]:
    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    grouped: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        scenario = by_id.get(str(row.get("scenario_id") or ""))
        if scenario is not None and not scenario.is_baseline:
            previous = grouped[scenario.scope_id].get(scenario.scenario_id)
            if previous is None or scenario_score(row) > scenario_score(previous):
                grouped[scenario.scope_id][scenario.scenario_id] = row
    selected: list[Scenario] = []
    for scope_id in (*SUPPLIER_IDS, "all_021081"):
        candidates = sorted(
            grouped.get(scope_id, {}).values(),
            key=scenario_score,
            reverse=True,
        )
        chosen: list[Mapping[str, Any]] = []
        seen_mechanisms: set[str] = set()
        seen_outcomes: set[str] = set()
        for row in candidates:
            scenario = by_id[str(row.get("scenario_id"))]
            if scenario.mechanism in seen_mechanisms:
                continue
            outcome = str(row.get("simulation_outcome_sha256") or "")
            if outcome and outcome in seen_outcomes:
                continue
            chosen.append(row)
            seen_mechanisms.add(scenario.mechanism)
            if outcome:
                seen_outcomes.add(outcome)
            if len(chosen) >= max(1, top_per_scope):
                break
        if len(chosen) < max(1, top_per_scope):
            chosen_ids = {str(row.get("scenario_id")) for row in chosen}
            for row in candidates:
                if str(row.get("scenario_id")) in chosen_ids:
                    continue
                outcome = str(row.get("simulation_outcome_sha256") or "")
                if outcome and outcome in seen_outcomes:
                    continue
                chosen.append(row)
                if outcome:
                    seen_outcomes.add(outcome)
        for row in chosen[: max(1, top_per_scope)]:
            selected.append(by_id[str(row.get("scenario_id"))])
    return list({scenario.scenario_id: scenario for scenario in selected}.values())


def add_required_scenarios(
    selected: Sequence[Scenario],
    scenarios: Sequence[Scenario],
    required_ids: Sequence[str] = REQUIRED_QUALITY_ANCHOR_IDS,
) -> tuple[list[Scenario], int]:
    """Append methodological anchors even when their outcome hash duplicates another mode."""

    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    missing_design = [scenario_id for scenario_id in required_ids if scenario_id not in by_id]
    if missing_design:
        raise CampaignValidationError(
            "Required quality anchors are absent from the scenario design: "
            + ", ".join(missing_design)
        )
    output = list(selected)
    present = {scenario.scenario_id for scenario in output}
    added = 0
    for scenario_id in required_ids:
        if scenario_id not in present:
            output.append(by_id[scenario_id])
            present.add(scenario_id)
            added += 1
    return output, added


def parse_seeds(specification: str) -> list[int]:
    result: list[int] = []
    for chunk in str(specification or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            first, last = (int(value.strip()) for value in chunk.split("-", 1))
            step = 1 if last >= first else -1
            result.extend(range(first, last + step, step))
        else:
            result.append(int(chunk))
    unique = list(dict.fromkeys(result))
    if not unique:
        raise ValueError("At least one seed is required")
    return unique


def _case_key(scenario: Scenario, seed: int) -> str:
    return f"{scenario.scenario_id}/seed_{seed}"


def run_case(
    *,
    source_graph: Mapping[str, Any],
    source_graph_path: Path,
    engine: Path,
    profile_args: Sequence[str],
    output_root: Path,
    scenario: Scenario,
    seed: int,
    stage: str,
    days: int,
    retention: str,
    opening_order_risk_mode: str,
    state_regime: StateRegime,
    measurement_start_stock_scale_csv: Path | None,
) -> dict[str, Any]:
    case_dir = (
        output_root
        / "cases"
        / state_regime.regime_id
        / scenario.scenario_id
        / f"seed_{seed}"
    )
    case_dir.mkdir(parents=True, exist_ok=True)
    overlay, ledger, overlay_audit = build_graph_overlay(
        source_graph,
        scenario,
        seed=seed,
        opening_order_risk_mode=opening_order_risk_mode,
    )
    inputs_dir = case_dir / "campaign_inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    graph_path = inputs_dir / "graph_overlay.json"
    risk_path = inputs_dir / "dynamic_mrp_risk_events.csv"
    ledger_path = inputs_dir / "observed_order_overlay_ledger.csv"
    overlay_audit_path = inputs_dir / "overlay_audit.json"
    graph_path.write_text(json.dumps(overlay, ensure_ascii=False), encoding="utf-8")
    write_csv(ledger_path, ledger)
    write_json(overlay_audit_path, overlay_audit)
    risks = risk_event_rows(scenario, days)
    if risks:
        write_csv(risk_path, risks, RISK_FIELDS)
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    required_extract_path = (
        case_dir / "data" / "production_demand_service_daily.csv"
    )
    command = build_engine_command(
        engine=engine,
        graph=graph_path,
        output_dir=case_dir,
        profile_args=profile_args,
        days=days,
        seed=seed,
        risk_csv=risk_path if risks else None,
        apply_risk_to_opening_orders=bool(
            overlay_audit.get("engine_native_opening_order_risk_enabled")
        ),
        measurement_start_stock_scale_csv=measurement_start_stock_scale_csv,
    )
    if not summary_path.exists() or not required_extract_path.exists():
        log_path = case_dir / "campaign_engine.log"
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"[{utc_now()}] SOURCE_GRAPH {source_graph_path}\n")
            log.write(f"[{utc_now()}] COMMAND {json.dumps(command, ensure_ascii=False)}\n")
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(f"Engine failed for {_case_key(scenario, seed)}; see {log_path}")
    result = extract_case(
        case_dir=case_dir,
        scenario=scenario,
        seed=seed,
        stage=stage,
        days=days,
        overlay_ledger=ledger,
        overlay_audit=overlay_audit,
    )
    result["source_graph_sha256"] = sha256_file(source_graph_path)
    result["overlay_graph_sha256"] = sha256_file(graph_path)
    result["orchestrator_sha256_at_process_start"] = (
        PROCESS_ORCHESTRATOR_SHA256
    )
    result["engine_sha256_at_case"] = sha256_file(engine)
    result["engine_profile_args_sha256"] = json_sha256(list(profile_args))
    result["engine_command_normalized_sha256"] = json_sha256(
        normalized_engine_command(command)
    )
    result["engine_command_normalized_json"] = json.dumps(
        normalized_engine_command(command),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    result["dynamic_risk_csv_sha256"] = (
        sha256_file(risk_path) if risks and risk_path.exists() else ""
    )
    result["observed_order_ledger_sha256"] = sha256_file(ledger_path)
    result["overlay_audit_sha256"] = sha256_file(overlay_audit_path)
    result["measurement_start_stock_scale_csv_sha256"] = (
        sha256_file(measurement_start_stock_scale_csv)
        if measurement_start_stock_scale_csv is not None
        else ""
    )
    result["dynamic_risk_event_count"] = len(risks)
    result["state_regime"] = state_regime.regime_id
    result["state_regime_evidence_class"] = state_regime.evidence_class
    result["state_regime_target_cover_days"] = (
        state_regime.target_cover_days
        if state_regime.target_cover_days is not None
        else ""
    )
    result["state_regime_configured_opening_stock_qty_kg"] = (
        state_regime.opening_stock_qty_kg
    )
    result["state_regime_stock_scale"] = state_regime.stock_scale
    if bool(overlay_audit.get("engine_native_opening_order_risk_enabled")):
        if to_int(result.get("opening_order_native_risk_audit_rows")) != EXPECTED_ORDER_COUNT:
            raise CampaignValidationError(
                "Native opening-order risk audit does not contain the 23 target rows"
            )
        if (
            not scenario.is_baseline
            and to_int(result.get("opening_order_native_risk_applied_rows")) <= 0
        ):
            raise CampaignValidationError(
                f"Native risk was not applied to any target opening order for {scenario.scenario_id}"
            )
        if to_int(result.get("opening_order_native_unsupported_risk_rows")) > 0:
            raise CampaignValidationError(
                f"Native opening-order audit reports unsupported risk for {scenario.scenario_id}"
            )
    result["valid"] = True
    if retention == "summary":
        graph_path.unlink(missing_ok=True)
        # All target order/flow/lot evidence needed for review has already been
        # copied to the small proofs directory.  Remove bulky generic extracts
        # only inside this exact generated case directory.
        for directory_name in ("data", "plots", "maps", "run"):
            directory = case_dir / directory_name
            if directory.is_dir():
                shutil.rmtree(directory)
    return result


def _run_cases(
    *,
    source_graph: Mapping[str, Any],
    source_graph_path: Path,
    engine: Path,
    profile_args: Sequence[str],
    output_root: Path,
    scenarios: Sequence[Scenario],
    seeds: Sequence[int],
    stage: str,
    days: int,
    workers: int,
    retention: str,
    metric_path: Path,
    opening_order_risk_mode: str,
    state_regime: StateRegime,
    measurement_start_stock_scale_csv: Path | None,
    resume: bool = False,
) -> list[dict[str, Any]]:
    requested_scenario_ids = {scenario.scenario_id for scenario in scenarios}
    requested_seeds = {int(seed) for seed in seeds}
    results: list[dict[str, Any]] = []
    if resume and metric_path.exists():
        results = [
            dict(row)
            for row in read_csv_rows(metric_path)
            if str(row.get("state_regime") or "") == state_regime.regime_id
            and str(row.get("scenario_id") or "") in requested_scenario_ids
            and to_int(row.get("seed")) in requested_seeds
            and str(row.get("valid") or "").strip().lower()
            in {"1", "true", "yes"}
        ]
    completed = {
        (str(row.get("scenario_id") or ""), to_int(row.get("seed")))
        for row in results
    }
    jobs = [
        (scenario, seed)
        for seed in seeds
        for scenario in scenarios
        if (scenario.scenario_id, int(seed)) not in completed
    ]
    if completed:
        print(
            f"[RESUME] {stage} {state_regime.regime_id}: "
            f"{len(completed)} completed case(s) reused, {len(jobs)} missing case(s)",
            flush=True,
        )
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(
                run_case,
                source_graph=source_graph,
                source_graph_path=source_graph_path,
                engine=engine,
                profile_args=profile_args,
                output_root=output_root,
                scenario=scenario,
                seed=seed,
                stage=stage,
                days=days,
                retention=retention,
                opening_order_risk_mode=opening_order_risk_mode,
                state_regime=state_regime,
                measurement_start_stock_scale_csv=(
                    measurement_start_stock_scale_csv
                ),
            ): (scenario, seed)
            for scenario, seed in jobs
        }
        for future in as_completed(futures):
            scenario, seed = futures[future]
            row = future.result()
            results.append(row)
            write_csv(
                metric_path,
                sorted(results, key=lambda item: (to_int(item.get("seed")), str(item.get("scenario_id")))),
            )
            print(
                f"[{stage.upper()}] {scenario.scenario_id} seed={seed} "
                f"replayed={to_float(row.get('replayed_shipped_qty_kg')):,.0f} kg "
                f"268967_on_due={to_float(row.get('product_on_due_volume_proxy')):.2%}",
                flush=True,
            )
    return results


def _baseline_by_seed(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, int], Mapping[str, Any]]:
    return {
        (str(row.get("state_regime") or "observed_2025"), to_int(row.get("seed"))): row
        for row in rows
        if str(row.get("scenario_id") or "") == "baseline_observed_order_book"
    }


def attach_pairs(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    baselines = _baseline_by_seed(rows)
    output: list[dict[str, Any]] = []
    for row in rows:
        baseline = baselines.get(
            (
                str(row.get("state_regime") or "observed_2025"),
                to_int(row.get("seed")),
            )
        )
        if baseline is None:
            raise CampaignValidationError("Every stress result needs a same-seed reference")
        output.append(paired_metrics(row, baseline))
    return output


SUMMARY_METRICS = (
    "product_on_due_volume_proxy",
    "product_on_due_delta_vs_paired_baseline",
    "product_backlog_qty_days_delta_vs_paired_baseline",
    "component_stock_min_qty_kg",
    "component_stock_min_delta_vs_paired_baseline_kg",
    "overlay_quantity_loss_kg",
    "overlay_weighted_usable_delay_days",
    "order_book_after_horizon_qty_kg",
    "order_book_after_horizon_rows",
    "replayed_received_reconciled_qty_kg",
    "dynamic_pulled_qty_kg",
    "dynamic_shipped_qty_kg",
    "intermediate_773474_min_total_qty_g",
    "intermediate_773474_final_total_qty_g",
    "intermediate_773474_produced_qty_g",
    "intermediate_773474_released_qty_g",
    "product_268967_produced_qty",
    "product_268967_released_qty",
)


def summarize_results(
    rows: Sequence[Mapping[str, Any]], scenarios: Sequence[Scenario]
) -> list[dict[str, Any]]:
    by_scenario: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_scenario[
            (
                str(row.get("state_regime") or "observed_2025"),
                str(row.get("scenario_id") or ""),
            )
        ].append(row)
    scenario_by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    output: list[dict[str, Any]] = []
    for (state_regime, scenario_id), group in sorted(by_scenario.items()):
        scenario = scenario_by_id[scenario_id]
        result: dict[str, Any] = {
            "scenario_id": scenario_id,
            "state_regime": state_regime,
            "state_regime_evidence_class": str(
                group[0].get("state_regime_evidence_class") or ""
            ),
            "state_regime_target_cover_days": group[0].get(
                "state_regime_target_cover_days", ""
            ),
            "scope_id": scenario.scope_id,
            "scope_type": (
                "common_cause_multisource"
                if scenario.scope_id == "all_021081"
                else "isolated_supplier"
            ),
            "mechanism": scenario.mechanism,
            "mechanism_label": (
                "Référence" if scenario.is_baseline else MECHANISM_LABELS[scenario.mechanism]
            ),
            "mechanism_value": scenario.value,
            "mechanism_unit": scenario.value_unit,
            "n_simulations": len(group),
            "seed_min": min(to_int(row.get("seed")) for row in group),
            "seed_max": max(to_int(row.get("seed")) for row in group),
        }
        for metric in SUMMARY_METRICS:
            values = [to_float(row.get(metric), math.nan) for row in group]
            values = [value for value in values if math.isfinite(value)]
            result[f"{metric}_mean"] = sum(values) / len(values) if values else math.nan
            result[f"{metric}_min"] = min(values) if values else math.nan
            result[f"{metric}_max"] = max(values) if values else math.nan
        output.append(result)
    return output


def supplier_criticality_rows(
    summaries: Sequence[Mapping[str, Any]],
    order_audit: Mapping[str, Any],
) -> list[dict[str, Any]]:
    supplier_evidence = {
        str(row.get("supplier_id") or ""): row
        for row in order_audit.get("supplier_rows", [])
        if isinstance(row, Mapping)
    }
    output: list[dict[str, Any]] = []
    state_regime = (
        str(summaries[0].get("state_regime") or "observed_2025")
        if summaries
        else ""
    )
    for supplier in SUPPLIER_IDS:
        candidates = [
            row
            for row in summaries
            if str(row.get("scope_id") or "") == supplier
            and str(row.get("mechanism") or "") != "baseline"
        ]
        candidates.sort(
            key=lambda row: (
                max(
                    0.0,
                    -to_float(
                        row.get("product_on_due_delta_vs_paired_baseline_mean")
                    ),
                ),
                max(
                    0.0,
                    to_float(
                        row.get(
                            "product_backlog_qty_days_delta_vs_paired_baseline_mean"
                        )
                    ),
                ),
                to_float(row.get("overlay_quantity_loss_kg_mean")),
                to_float(row.get("overlay_weighted_usable_delay_days_mean")),
            ),
            reverse=True,
        )
        worst = candidates[0] if candidates else {}
        product_effect_count = sum(
            -to_float(
                row.get("product_on_due_delta_vs_paired_baseline_mean")
            )
            > 1e-9
            or to_float(
                row.get("product_backlog_qty_days_delta_vs_paired_baseline_mean")
            )
            > 1e-9
            for row in candidates
        )
        evidence = supplier_evidence.get(supplier, {})
        output.append(
            {
                "state_regime": state_regime,
                "supplier_id": supplier,
                "observed_open_order_count": to_int(evidence.get("order_count")),
                "observed_open_order_qty_kg": to_float(evidence.get("quantity_kg")),
                "observed_open_order_book_share": to_float(
                    evidence.get("observed_order_book_share")
                ),
                "tested_scenario_count": len(candidates),
                "scenarios_with_downstream_product_effect": product_effect_count,
                "worst_scenario_id": str(worst.get("scenario_id") or ""),
                "worst_mechanism": str(worst.get("mechanism") or ""),
                "worst_product_on_due_loss_mean": max(
                    0.0,
                    -to_float(
                        worst.get("product_on_due_delta_vs_paired_baseline_mean")
                    ),
                ),
                "worst_incremental_backlog_qty_days_mean": max(
                    0.0,
                    to_float(
                        worst.get(
                            "product_backlog_qty_days_delta_vs_paired_baseline_mean"
                        )
                    ),
                ),
                "worst_order_book_quantity_loss_kg_mean": to_float(
                    worst.get("overlay_quantity_loss_kg_mean")
                ),
                "worst_weighted_planned_usable_date_shift_days_mean": to_float(
                    worst.get("overlay_weighted_usable_delay_days_mean")
                ),
                "interpretation_status": (
                    "downstream_product_effect_observed_in_simulation"
                    if product_effect_count
                    else "order_book_exposure_only_downstream_effect_masked_by_state"
                ),
            }
        )
    output.sort(
        key=lambda row: (
            to_float(row.get("worst_product_on_due_loss_mean")),
            to_float(row.get("worst_incremental_backlog_qty_days_mean")),
            to_float(row.get("observed_open_order_book_share")),
        ),
        reverse=True,
    )
    for rank, row in enumerate(output, 1):
        row["criticality_rank_within_021081"] = rank
    return output


def mechanism_summary_rows(
    summaries: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    state_regime = (
        str(summaries[0].get("state_regime") or "observed_2025")
        if summaries
        else ""
    )
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in summaries:
        mechanism = str(row.get("mechanism") or "")
        if mechanism and mechanism != "baseline":
            grouped[mechanism].append(row)
    output: list[dict[str, Any]] = []
    for mechanism, group in sorted(grouped.items()):
        on_due_losses = [
            max(
                0.0,
                -to_float(
                    row.get("product_on_due_delta_vs_paired_baseline_mean")
                ),
            )
            for row in group
        ]
        output.append(
            {
                "state_regime": state_regime,
                "mechanism": mechanism,
                "mechanism_label": MECHANISM_LABELS[mechanism],
                "tested_scope_level_cases": len(group),
                "cases_with_downstream_product_effect": sum(
                    value > 1e-9 for value in on_due_losses
                ),
                "mean_product_on_due_loss": (
                    sum(on_due_losses) / len(on_due_losses) if on_due_losses else 0.0
                ),
                "max_product_on_due_loss": max(on_due_losses, default=0.0),
                "max_order_book_quantity_loss_kg": max(
                    (
                        to_float(row.get("overlay_quantity_loss_kg_mean"))
                        for row in group
                    ),
                    default=0.0,
                ),
                "max_weighted_planned_usable_date_shift_days": max(
                    (
                        to_float(
                            row.get("overlay_weighted_usable_delay_days_mean")
                        )
                        for row in group
                    ),
                    default=0.0,
                ),
            }
        )
    output.sort(
        key=lambda row: (
            to_float(row.get("cases_with_downstream_product_effect")),
            to_float(row.get("max_product_on_due_loss")),
            to_float(row.get("max_order_book_quantity_loss_kg")),
            to_float(
                row.get("max_weighted_planned_usable_date_shift_days")
            ),
        ),
        reverse=True,
    )
    return output


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_GRAPH))
    parser.add_argument("--engine", default=str(DEFAULT_ENGINE))
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--output-dir", default=str(default_output_dir()))
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--screening-seed", type=int, default=SCREENING_SEED)
    parser.add_argument("--confirmation-seeds", default="421082-421091")
    parser.add_argument("--top-per-scope", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retention", choices=["summary", "full"], default="summary")
    parser.add_argument(
        "--opening-order-risk-mode",
        choices=["engine", "overlay"],
        default="engine",
        help=(
            "engine uses the opt-in native risk-aware firm-order replay and lot "
            "lineage; capacity rationing falls back to the explicit FIFO overlay."
        ),
    )
    parser.add_argument(
        "--prospective-coverage-study",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "After the full observed-state screening, test selected distinct "
            "configurations at 365/180/90/30 days of simulated cover."
        ),
    )
    parser.add_argument(
        "--quality-anchors-only",
        action="store_true",
        help=(
            "Run only the baseline and mandatory 180-day quality-hold anchors "
            "in a distinct provenance artifact."
        ),
    )
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Reuse validated row-level metrics already present in the same "
            "additive output directory and run only missing regime/scenario/seed keys."
        ),
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run only the reference and one isolated delay case; no confirmation.",
    )
    return parser.parse_args(argv)


def write_state_regime_input(
    output_root: Path, regime: StateRegime
) -> Path | None:
    if math.isclose(regime.stock_scale, 1.0, rel_tol=0.0, abs_tol=1e-12):
        return None
    path = (
        output_root
        / "inputs"
        / f"measurement_start_stock_scale_{regime.regime_id}.csv"
    )
    write_csv(
        path,
        [
            {
                "node_id": DESTINATION_ID,
                "item_id": ITEM_ID,
                "scale": format(regime.stock_scale, ".12g"),
            }
        ],
        ("node_id", "item_id", "scale"),
    )
    return path


def most_discriminating_regime_id(
    rows: Sequence[Mapping[str, Any]],
    prospective_regimes: Sequence[StateRegime],
) -> str:
    scores: dict[str, tuple[float, float]] = {}
    for regime in prospective_regimes:
        regime_rows = [
            row
            for row in rows
            if str(row.get("state_regime") or "") == regime.regime_id
            and str(row.get("scenario_id") or "")
            != "baseline_observed_order_book"
        ]
        scores[regime.regime_id] = (
            max(
                (
                    max(
                        0.0,
                        -to_float(
                            row.get(
                                "product_on_due_delta_vs_paired_baseline"
                            )
                        ),
                    )
                    for row in regime_rows
                ),
                default=0.0,
            ),
            max(
                (
                    max(
                        0.0,
                        to_float(
                            row.get(
                                "product_backlog_qty_days_delta_vs_paired_baseline"
                            )
                        ),
                    )
                    for row in regime_rows
                ),
                default=0.0,
            ),
        )
    return max(
        prospective_regimes,
        key=lambda regime: (*scores.get(regime.regime_id, (0.0, 0.0)), -float(regime.target_cover_days or 0.0)),
    ).regime_id


def summary_severity(
    row: Mapping[str, Any],
) -> tuple[float, float, float, float, str]:
    """Lexicographic business severity without mixing unlike units."""

    return (
        max(
            0.0,
            -to_float(
                row.get("product_on_due_delta_vs_paired_baseline_mean")
            ),
        ),
        max(
            0.0,
            to_float(
                row.get(
                    "product_backlog_qty_days_delta_vs_paired_baseline_mean"
                )
            ),
        ),
        max(0.0, to_float(row.get("overlay_quantity_loss_kg_mean"))),
        max(
            0.0,
            to_float(row.get("overlay_weighted_usable_delay_days_mean")),
        ),
        str(row.get("scenario_id") or ""),
    )


def top_case_rows(
    summaries: Sequence[Mapping[str, Any]],
    *,
    limit: int = 3,
    selection_basis: str,
) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in summaries
        if str(row.get("mechanism") or "") != "baseline"
    ]
    candidates.sort(key=summary_severity, reverse=True)
    output: list[dict[str, Any]] = []
    for rank, row in enumerate(candidates[: max(0, limit)], 1):
        on_due_loss = max(
            0.0,
            -to_float(
                row.get("product_on_due_delta_vs_paired_baseline_mean")
            ),
        )
        backlog = max(
            0.0,
            to_float(
                row.get(
                    "product_backlog_qty_days_delta_vs_paired_baseline_mean"
                )
            ),
        )
        after_horizon = max(
            0.0, to_float(row.get("order_book_after_horizon_qty_kg_mean"))
        )
        output.append(
            {
                "rank": rank,
                "selection_basis": selection_basis,
                "state_regime": str(row.get("state_regime") or ""),
                "evidence_class": str(
                    row.get("state_regime_evidence_class") or ""
                ),
                "scenario_id": str(row.get("scenario_id") or ""),
                "scope_id": str(row.get("scope_id") or ""),
                "scope_type": str(row.get("scope_type") or ""),
                "mechanism": str(row.get("mechanism") or ""),
                "mechanism_label": str(row.get("mechanism_label") or ""),
                "hypothesis_value": row.get("mechanism_value", ""),
                "hypothesis_unit": str(row.get("mechanism_unit") or ""),
                "n_simulations": to_int(row.get("n_simulations")),
                "product_on_due_loss_percentage_points_mean": on_due_loss
                * 100.0,
                "incremental_backlog_qty_days_mean": backlog,
                "order_book_quantity_loss_kg_mean": max(
                    0.0, to_float(row.get("overlay_quantity_loss_kg_mean"))
                ),
                "weighted_planned_usable_date_shift_days_mean": max(
                    0.0,
                    to_float(
                        row.get("overlay_weighted_usable_delay_days_mean")
                    ),
                ),
                "order_book_after_horizon_qty_kg_mean": after_horizon,
                "recovery_statement": (
                    "availability_after_test_horizon_no_recovery_day_claimed"
                    if after_horizon > 1e-9
                    else "all_replayed_order_quantity_resolves_within_test_horizon"
                ),
                "interpretation_status": (
                    "simulated_downstream_product_effect"
                    if on_due_loss > 1e-9 or backlog > 1e-9
                    else "supplier_order_book_effect_masked_downstream_by_tested_state"
                ),
            }
        )
    return output


def _format_fr(value: Any, digits: int = 0) -> str:
    number = to_float(value, math.nan)
    if not math.isfinite(number):
        return "non calculable"
    rendered = f"{number:,.{digits}f}"
    return rendered.replace(",", "\u00a0").replace(".", ",")


def write_business_outputs(
    *,
    output_root: Path,
    source_audit: Mapping[str, Any],
    active_regimes: Sequence[StateRegime],
    summaries: Sequence[Mapping[str, Any]],
    confirmation_summaries: Sequence[Mapping[str, Any]],
    criticality: Sequence[Mapping[str, Any]],
    mechanisms: Sequence[Mapping[str, Any]],
    flow_gates: Mapping[str, Any],
    masking_audit: Mapping[str, Any],
    confirmation_regime: StateRegime | None,
    days: int,
    intermediate_masking_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Write compact decision material for the future autonomous page."""

    observed_summaries = [
        row
        for row in summaries
        if str(row.get("state_regime") or "") == "observed_2025"
    ]
    observed_top = top_case_rows(
        observed_summaries,
        selection_basis="full_91_case_screening_observed_2025_state",
    )
    decision_source = list(confirmation_summaries)
    if not decision_source:
        decision_source = [
            row
            for row in summaries
            if str(row.get("state_regime") or "") != "observed_2025"
        ]
    if not decision_source:
        decision_source = observed_summaries
    decision_top = top_case_rows(
        decision_source,
        selection_basis=(
            "ten_paired_seeds_in_most_discriminating_reduced_cover_hypothesis"
            if confirmation_summaries
            and confirmation_regime is not None
            and confirmation_regime.regime_id != "observed_2025"
            else "available_screening_results"
        ),
    )
    write_csv(
        output_root / "top_3_cases_observed_state_021081.csv", observed_top
    )
    write_csv(
        output_root / "top_3_cases_decision_021081.csv", decision_top
    )

    regime_effects: list[dict[str, Any]] = []
    regime_by_id = {regime.regime_id: regime for regime in active_regimes}
    for regime_id in regime_by_id:
        stress = [
            row
            for row in summaries
            if str(row.get("state_regime") or "") == regime_id
            and str(row.get("mechanism") or "") != "baseline"
        ]
        impacted = [
            row
            for row in stress
            if summary_severity(row)[0] > 1e-9
            or summary_severity(row)[1] > 1e-9
        ]
        regime_effects.append(
            {
                "state_regime": regime_id,
                "evidence_class": regime_by_id[regime_id].evidence_class,
                "target_cover_days": (
                    regime_by_id[regime_id].target_cover_days
                    if regime_by_id[regime_id].target_cover_days is not None
                    else ""
                ),
                "tested_stress_configurations": len(stress),
                "configurations_with_simulated_downstream_product_effect": len(
                    impacted
                ),
                "interpretation": (
                    "at_least_one_simulated_downstream_effect"
                    if impacted
                    else "no_downstream_effect_in_tested_cases_not_proof_of_resilience"
                ),
            }
        )
    write_csv(output_root / "state_regime_effect_summary.csv", regime_effects)

    quality_cover_sensitivity: list[dict[str, Any]] = []
    for scenario_id in REQUIRED_QUALITY_ANCHOR_IDS:
        by_cover: dict[float, Mapping[str, Any]] = {}
        for row in summaries:
            if str(row.get("scenario_id") or "") != scenario_id:
                continue
            cover = to_float(row.get("state_regime_target_cover_days"), math.nan)
            if math.isfinite(cover):
                by_cover[cover] = row
        impacted_covers = sorted(
            (
                cover
                for cover, row in by_cover.items()
                if summary_severity(row)[0] > 1e-9
                or summary_severity(row)[1] > 1e-9
            ),
            reverse=True,
        )
        unaffected_covers = sorted(
            (cover for cover in by_cover if cover not in impacted_covers)
        )
        largest_impacted = impacted_covers[0] if impacted_covers else math.nan
        nearest_higher_unaffected = (
            min(
                (
                    cover
                    for cover in unaffected_covers
                    if cover > largest_impacted
                ),
                default=math.nan,
            )
            if math.isfinite(largest_impacted)
            else math.nan
        )
        if not by_cover:
            threshold_status = "not_tested_in_this_artifact"
            interval_text = (
                "retenue qualité non testée dans les régimes de couverture de "
                "cet artefact; voir le paquet d'ancres qualité séparé"
            )
        elif math.isfinite(largest_impacted) and math.isfinite(
            nearest_higher_unaffected
        ):
            threshold_status = "transition_interval_to_confirm"
            interval_text = (
                f"basculement entre {largest_impacted:g} et "
                f"{nearest_higher_unaffected:g} jours à confirmer"
            )
        elif math.isfinite(largest_impacted):
            threshold_status = "effect_at_highest_tested_cover_no_upper_bound"
            interval_text = (
                f"effet déjà présent à {largest_impacted:g} jours; borne "
                "supérieure non localisée"
            )
        else:
            threshold_status = "no_effect_at_tested_cover_levels"
            interval_text = (
                "aucun basculement entre 30, 90, 180 et 365 jours; seuil "
                "non localisé"
            )
        quality_cover_sensitivity.append(
            {
                "scenario_id": scenario_id,
                "scope_id": (
                    "all_021081"
                    if scenario_id.startswith("all_021081")
                    else "SDC-VD0960508A"
                ),
                "quality_hold_days": 180,
                "tested_stock_cover_days": ";".join(
                    format(value, "g") for value in sorted(by_cover)
                ),
                "stock_cover_days_with_downstream_effect": ";".join(
                    format(value, "g") for value in sorted(impacted_covers)
                ),
                "threshold_status": threshold_status,
                "transition_interval_business_text": interval_text,
                "scientific_limit": (
                    "Interval sensitivity only; not an optimum or an observed "
                    "industrial stock target."
                ),
            }
        )
    write_csv(
        output_root / "quality_hold_cover_sensitivity_021081.csv",
        quality_cover_sensitivity,
    )

    payload: dict[str, Any] = {
        "schema_version": "supplier-021081-autonomous-page-payload.v1",
        "title": "Composant 021081 : carnet fournisseur, risques et lots exposés",
        "page_story": [
            "1. Ce que le carnet 2025 montre réellement",
            "2. Ce que les incidents simulés changent sur les commandes et les lots",
            "3. À quel niveau de stock la perturbation atteint le produit et le client",
        ],
        "lexicon": {
            "observed": (
                "Valeur présente dans l'instantané ERP du 01-01-2025. Les dates "
                "du carnet sont planifiées, pas des livraisons réelles mesurées."
            ),
            "simulated": "Réponse calculée par le moteur pour une hypothèse déclarée.",
            "priority_signal": (
                "Cas à vérifier avec les équipes achats/qualité/production; ce n'est "
                "ni une probabilité de panne ni une note fournisseur observée."
            ),
            "hypothesis": (
                "Dégradation ou niveau de stock testé pour apprendre où la chaîne "
                "devient vulnérable."
            ),
        },
        "coherence_with_clean_dynamic_reference": {
            "clean_dynamic_reference": (
                "0 arrival for 021081 when no opening order book is replayed"
            ),
            "this_campaign_reference": (
                "23 planned open orders from the 2025 snapshot are deliberately replayed"
            ),
            "why_not_a_contradiction": (
                "The clean dynamic reference and the active-order-book replay answer "
                "different questions. Replayed and newly generated MRP flows remain separate."
            ),
            "dynamic_pulled_qty_kg_in_this_campaign_reference": to_float(
                flow_gates.get("observed_2025", {}).get(
                    "dynamic_pulled_qty_kg"
                )
            ),
            "dynamic_shipped_qty_kg_in_this_campaign_reference": to_float(
                flow_gates.get("observed_2025", {}).get(
                    "dynamic_shipped_qty_kg"
                )
            ),
        },
        "quantity_unit_provenance": (
            "The campaign reads the graph's already-standardized quantity field; "
            "the 23 target rows declare uom=KG. No new unit conversion is applied."
        ),
        "critical_bom_unit_validation": {
            "status": "unité à valider avec l'industriel",
            "source": "773474.xlsx BOM",
            "declared_output": "1000 G — ELSSR CONT. 1000 L",
            "declared_021081_input": "8,94 KG",
            "literal_graph_execution": (
                "8,94 kg de 021081 par kg de 773474; 28 608 kg pour un lot "
                "de 3,2 millions de grammes"
            ),
            "why_critical": (
                "The kg/g/L interpretation is physically suspect and may create a "
                "factor-1000 error in consumption and cover."
            ),
            "alternative_sensitivity_only": (
                "ratio literal versus ratio divided by 1000; neither is asserted "
                "as the certain correction"
            ),
        },
        "intermediate_773474_masking_audit": {
            "opening_stock_sdc_1450_g": INTERMEDIATE_773474_STOCK_SDC_G,
            "opening_stock_m_1430_g": INTERMEDIATE_773474_STOCK_M1430_G,
            "opening_stock_total_g": INTERMEDIATE_773474_TOTAL_STOCK_G,
            "approx_773474_per_268967_lot_g": (
                INTERMEDIATE_773474_PER_268967_LOT_G
            ),
            "released_268967_lot_count": (
                INTERMEDIATE_268967_RELEASED_LOT_COUNT
            ),
            "approx_horizon_need_g": INTERMEDIATE_773474_HORIZON_NEED_G,
            "horizon_773474_production_g": (
                INTERMEDIATE_773474_HORIZON_PRODUCTION_G
            ),
            "stock_cover_lots": INTERMEDIATE_773474_STOCK_COVER_LOTS,
            "stock_multiple_of_horizon_need": (
                INTERMEDIATE_773474_STOCK_TO_HORIZON_NEED
            ),
            "stock_plus_production_multiple_of_horizon_need": (
                INTERMEDIATE_773474_STOCK_PLUS_PRODUCTION_TO_NEED
            ),
            "021081_stock_multiple_of_horizon_intermediate_consumption": (
                COMPONENT_021081_STOCK_TO_HORIZON_CONSUMPTION
            ),
            "021081_order_book_multiple_of_horizon_intermediate_consumption": (
                COMPONENT_021081_ORDER_BOOK_TO_HORIZON_CONSUMPTION
            ),
            "business_warning": (
                "Masking is cumulative across intermediate stock and production, "
                "021081 stock and oversized open orders. The 021081-only cover study "
                "is not a global lean-supply state."
            ),
            **dict(intermediate_masking_provenance),
        },
        "observed_2025_order_book": dict(source_audit),
        "observed_stock_masking_audit": dict(masking_audit),
        "reference_flow_gates": dict(flow_gates),
        "state_regime_effects": regime_effects,
        "quality_hold_cover_sensitivity": quality_cover_sensitivity,
        "quality_post_receipt_operational_interpretation": {
            "transport_is_not_a_release_lever": (
                "Once material is physically received and held for quality, faster "
                "transport cannot shorten the release hold."
            ),
            "realistic_levers_to_test": [
                "lot déjà libéré ou stock libre prépositionné avant l'incident",
                "commandes des sources non touchées",
                "alternative déjà approuvée",
                "allocation et replanification opérationnelles explicites",
            ],
        },
        "top_three_observed_state_exposures": observed_top,
        "top_three_decision_cases": decision_top,
        "supplier_criticality": list(criticality),
        "sensitivity_to_tested_modes": list(mechanisms),
        "technical_compatibility_alias": {
            "mechanism_recurrence": (
                "Deprecated technical name only; these counts are simulated "
                "scenario sensitivity, not historical recurrence."
            )
        },
        "chart_contracts": [
            {
                "chart": "23 commandes : quantité et date utilisable avant/après",
                "source": "cases/**/proofs/order_book_overlay_ledger.csv",
                "encoding": "une ligne ERP par commande; couleur par fournisseur",
            },
            {
                "chart": "Effet par couverture de stock",
                "source": "state_regime_effect_summary.csv",
                "encoding": "séparer strictement observé 2025 et hypothèses 365/180/90/30 jours",
            },
            {
                "chart": "Traçabilité lots 021081 → 773474 → 268967",
                "source": "cases/**/proofs/lot_genealogy_021081_773474_268967.csv",
                "encoding": "source_row est une ligne ERP technique, pas un numéro de lot industriel",
            },
        ],
        "limitations": [
            "L'unité de la BOM 773474/021081 est à valider; le ratio littéral peut être décalé d'un facteur 1000.",
            "Les couvertures 30/90/180/365 réduisent 021081 seule; elles ne représentent pas une supply globale lean car 773474 reste fortement stocké.",
            "Le carnet observé est un instantané de commandes ouvertes; il ne fournit pas l'OTIF historique.",
            "Les fréquences simulées ne sont pas des probabilités d'incident fournisseur observées.",
            "Une disponibilité repoussée après l'horizon ne reçoit aucun faux jour de récupération.",
            "L'impact nul avec 1 142 100 kg au J0 est un masquage par l'état testé, pas une preuve de résilience.",
            "Valider l'unité KG, le stock libre/bloqué/alloué/périmé, le site/propriétaire et la durée de vie.",
        ],
        "data_files": {
            "observed_orders": "inputs/observed_open_orders_021081.csv",
            "scenario_design": "scenario_design.csv",
            "scenario_summary": "scenario_summary.csv",
            "supplier_ranking": "supplier_criticality_ranking_021081.csv",
            "mechanism_sensitivity": "mechanism_sensitivity_summary_021081.csv",
            "mechanism_summary_legacy_alias": "mechanism_recurrence_summary_021081.csv",
            "top_cases": "top_3_cases_decision_021081.csv",
            "quality_cover_sensitivity": "quality_hold_cover_sensitivity_021081.csv",
        },
    }
    write_json(output_root / "future_autonomous_page_payload.json", payload)

    observed_effects = next(
        (
            row["configurations_with_simulated_downstream_product_effect"]
            for row in regime_effects
            if row["state_regime"] == "observed_2025"
        ),
        0,
    )
    observed_tested_stress_count = next(
        (
            row["tested_stress_configurations"]
            for row in regime_effects
            if row["state_regime"] == "observed_2025"
        ),
        0,
    )
    cover_days = to_float(
        masking_audit.get("physical_cover_days_at_simulated_average_consumption"),
        math.nan,
    )
    stock_multiple = to_float(
        masking_audit.get("observed_stock_multiple_of_horizon_consumption"),
        math.nan,
    )
    lines = [
        "# Bilan métier — composant 021081",
        "",
        "## Ce qui est réellement observé",
        "",
        (
            f"L'instantané ERP du 01-01-2025 contient **{to_int(source_audit.get('order_count'))} "
            f"commandes ouvertes**, soit **{_format_fr(source_audit.get('quantity_kg'))} kg**, "
            "réparties entre quatre sources. Les dates J6–J139 (livraison physique prévue) "
            "et J112–J261 (matière prévue utilisable) sont des dates planifiées : elles ne "
            "prouvent ni la livraison réelle ni l'OTIF fournisseur."
        ),
        "",
        (
            "Les quantités sont lues dans le champ déjà standardisé du graphe; les 23 lignes "
            "ciblées portent l'unité KG. La campagne ne leur applique aucune nouvelle conversion."
        ),
        "",
        "## Pourquoi ce replay n'est pas la référence dynamique propre",
        "",
        (
            "La référence dynamique propre du rapport produit **0 arrivée de 021081** lorsqu'aucun "
            "carnet initial n'est injecté. Ici, la référence de campagne rejoue volontairement les "
            "**23 commandes planifiées** du carnet 2025. Ce ne sont pas deux résultats contradictoires : "
            "ils répondent à deux questions différentes, et les flux rejoués restent séparés des "
            f"nouveaux flux MRP (tiré : {_format_fr(flow_gates.get('observed_2025', {}).get('dynamic_pulled_qty_kg'))} kg; "
            f"expédié : {_format_fr(flow_gates.get('observed_2025', {}).get('dynamic_shipped_qty_kg'))} kg dans la référence de campagne)."
        ),
        "",
        "## Alerte critique — unité de la nomenclature à valider",
        "",
        (
            "La nomenclature source 773474 déclare une sortie **1000 G** (description "
            "« ELSSR CONT. 1000 L ») et une entrée 021081 de **8,94 KG**. Le graphe "
            "l'exécute littéralement comme **8,94 kg de 021081 par kg de 773474** : "
            "un lot de 3,2 millions de grammes consomme ainsi **28 608 kg**. Cette "
            "cohérence g/kg/L est physiquement suspecte et peut représenter un facteur "
            "1000. Statut : **unité à valider avec l'industriel**."
        ),
        "",
        (
            "Une sensibilité séparée comparera le ratio tel que modélisé au ratio divisé "
            "par 1000 (hypothèse 8,94 kg pour 1000 kg/L). Aucune des deux lectures ne sera "
            "présentée comme correction certaine et le graphe source n'est pas modifié."
        ),
        "",
        "## Le résultat structurant",
        "",
        (
            f"Le stock J0 observé est de **{_format_fr(masking_audit.get('observed_opening_stock_qty_kg'))} kg**. "
            f"Au rythme de consommation du modèle, il représente environ **{_format_fr(cover_days, 0)} jours** "
            f"de couverture, soit **{_format_fr(stock_multiple, 2)} fois** la consommation de l'horizon "
            f"de {days} jours, avant même les commandes ouvertes. Cette réserve masque les incidents "
            "dans le modèle; elle ne démontre pas une résilience industrielle acquise."
        ),
        "",
        "## Deuxième couche de masquage — stock intermédiaire 773474",
        "",
        (
            f"Le graphe contient **{_format_fr(INTERMEDIATE_773474_STOCK_SDC_G)} G** à SDC-1450 et "
            f"**{_format_fr(INTERMEDIATE_773474_STOCK_M1430_G)} G** à M-1430, soit "
            f"**{_format_fr(INTERMEDIATE_773474_TOTAL_STOCK_G)} G**. La baseline libère "
            f"**{INTERMEDIATE_268967_RELEASED_LOT_COUNT} lots** de 268967; chacun consomme environ "
            f"**{_format_fr(INTERMEDIATE_773474_PER_268967_LOT_G)} G** de 773474 : le stock intermédiaire "
            f"couvre environ **{_format_fr(INTERMEDIATE_773474_STOCK_COVER_LOTS, 3)} lots**, soit "
            f"**{_format_fr(100 * INTERMEDIATE_773474_STOCK_TO_HORIZON_NEED, 2)} %** du besoin "
            f"de **{_format_fr(INTERMEDIATE_773474_HORIZON_NEED_G, 1)} G** sur 720 jours."
        ),
        "",
        (
            f"La production ajoute **{_format_fr(INTERMEDIATE_773474_HORIZON_PRODUCTION_G)} G** : stock "
            f"initial + production représentent **{_format_fr(INTERMEDIATE_773474_STOCK_PLUS_PRODUCTION_TO_NEED, 3)} fois** "
            f"le besoin. En amont, le stock 021081 vaut **{_format_fr(COMPONENT_021081_STOCK_TO_HORIZON_CONSUMPTION, 3)} fois** "
            f"la consommation intermédiaire et le carnet ouvert **{_format_fr(COMPONENT_021081_ORDER_BOOK_TO_HORIZON_CONSUMPTION, 3)} fois**. "
            "Le masquage vient donc du **cumul des couches et des commandes surdimensionnées**. Les régimes "
            "30/90/180/365 jours de cette campagne sont donc une **sensibilité de 021081 seule**, "
            "jamais une configuration supply globale lean. Une étude de démasquage séparée doit "
            "réduire 773474 aux deux sites, seule puis conjointement avec 021081."
        ),
        "",
        (
            f"Dans l'état observé testé, **{observed_effects} configuration(s)** sur les "
            f"**{observed_tested_stress_count} dégradation(s) exécutée(s)** "
            "atteignent le produit fini ou le client. Les autres peuvent néanmoins décaler ou réduire "
            "les commandes fournisseur et les lots entrants."
        ),
        "",
        "## Ce que l'étude prospective ajoute",
        "",
        (
            "Les niveaux 365, 180, 90 et 30 jours sont des **hypothèses de sensibilité**, pas des "
            "stocks historiques. Ils servent à localiser le seuil où un même incident cesse d'être "
            "absorbé et atteint la production. Les configurations retenues sont ensuite rejouées avec "
            "10 graines appariées; les cas strictement identiques ne sont pas dupliqués."
        ),
        "",
        "## Les trois dossiers à regarder en premier",
        "",
    ]
    if decision_top:
        for row in decision_top:
            scope = (
                "les quatre sources simultanément"
                if row["scope_id"] == "all_021081"
                else row["scope_id"]
            )
            lines.extend(
                [
                    (
                        f"{row['rank']}. **{row['mechanism_label']} — {scope}** "
                        f"({row['hypothesis_value']} {row['hypothesis_unit']}). "
                        f"Perte moyenne de service à date : **{_format_fr(row['product_on_due_loss_percentage_points_mean'], 3)} point(s)**; "
                        f"quantité du carnet non utilisable : **{_format_fr(row['order_book_quantity_loss_kg_mean'])} kg**; "
                        f"décalage moyen pondéré : **{_format_fr(row['weighted_planned_usable_date_shift_days_mean'], 1)} jours**."
                    ),
                    "",
                ]
            )
    else:
        lines.extend(["Aucun dossier de décision n'a été calculé.", ""])
    lines.extend(
        [
            "## Lecture spécifique de la retenue qualité",
            "",
            (
                "Les couvertures 30, 90, 180 et 365 jours sont des niveaux de stock "
                "prépositionné **avant** l'incident. Si le service bascule entre deux "
                "niveaux, l'étude donne seulement cet intervalle à confirmer; elle ne "
                "calcule ni optimum exact ni stock-cible observé."
            ),
            "",
        ]
    )
    for row in quality_cover_sensitivity:
        lines.extend(
            [
                f"- **{row['scope_id']}** : {row['transition_interval_business_text']}.",
                "",
            ]
        )
    lines.extend(
        [
            (
                "Quand la matière est déjà physiquement reçue et retenue, accélérer le "
                "transport ne la libère pas. Les leviers réalistes à tester sont : lot "
                "déjà libéré ou stock libre préventif, commandes des sources non touchées, "
                "alternative approuvée, allocation et replanification réelles."
            ),
            "",
        ]
    )
    lines.extend(
        [
            "## Validation demandée à l'industriel",
            "",
            "Confirmer l'unité KG, la part réellement libre du stock, les quantités bloquées/allouées/périmées, le site et le propriétaire, la durée de vie, puis fournir les réceptions réelles et les motifs de retard/rejet. C'est ce qui transformera ces signaux simulés en criticité fournisseur mesurée.",
            "",
            "## Limite de récupération",
            "",
            f"L'horizon est de {days} jours. Lorsqu'une disponibilité est repoussée au-delà, le résultat est marqué **hors horizon** : aucun délai de récupération fictif n'est annoncé.",
            "",
        ]
    )
    (output_root / "RESUME_METIER_021081.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    source_graph_path = Path(args.input).resolve()
    engine = Path(args.engine).resolve()
    profile = Path(args.profile).resolve()
    output_root = Path(args.output_dir).resolve()
    if args.days < MINIMUM_REPLAY_DAYS:
        raise ValueError(
            f"--days must be >= {MINIMUM_REPLAY_DAYS} to include every observed usable receipt"
        )
    for path, label in ((source_graph_path, "graph"), (engine, "engine"), (profile, "profile")):
        if not path.exists():
            raise FileNotFoundError(f"Missing {label}: {path}")
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "campaign_manifest.json"
    previous_manifest: dict[str, Any] = {}
    if args.resume:
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"--resume requires an existing campaign manifest: {manifest_path}"
            )
        previous_manifest = read_json(manifest_path)
    source_graph = read_json(source_graph_path)
    target_orders = observed_orders(source_graph)
    source_audit = audit_observed_order_book(target_orders, strict=True)
    intermediate_masking_provenance = intermediate_masking_evidence(
        source_graph_path
    )
    scenarios = build_scenarios()
    all_state_regimes = build_state_regimes(source_graph)
    observed_regime = next(
        regime for regime in all_state_regimes if regime.regime_id == "observed_2025"
    )
    prospective_regimes = [
        regime for regime in all_state_regimes if regime.regime_id != "observed_2025"
    ]
    if not args.prospective_coverage_study or args.smoke:
        prospective_regimes = []
    active_regimes = [observed_regime, *prospective_regimes]
    regime_input_paths = {
        regime.regime_id: write_state_regime_input(output_root, regime)
        for regime in active_regimes
    }
    write_csv(output_root / "inputs" / "observed_open_orders_021081.csv", observed_order_export_rows(target_orders))
    write_csv(output_root / "scenario_design.csv", scenario_design_rows(scenarios))
    write_csv(
        output_root / "state_regime_design.csv",
        state_regime_rows(active_regimes),
    )
    write_json(output_root / "observed_order_book_audit.json", source_audit)
    manifest: dict[str, Any] = {
        "schema_version": "supplier-021081-active-flow-campaign.v1",
        "status": "prepared" if args.prepare_only else "running",
        "created_at_utc": utc_now(),
        "orchestrator": str(Path(__file__).resolve()),
        "orchestrator_sha256_at_process_start": (
            PROCESS_ORCHESTRATOR_SHA256
        ),
        "source_graph": str(source_graph_path),
        "source_graph_sha256": sha256_file(source_graph_path),
        "engine": str(engine),
        "engine_sha256": sha256_file(engine),
        "profile": str(profile),
        "profile_sha256": sha256_file(profile),
        "days": args.days,
        "warmup_days": WARMUP_DAYS,
        "observed_order_book_audit": source_audit,
        "scenario_count": len(scenarios),
        "scenario_design_count": len(scenarios),
        "planned_observed_state_screening_case_count": (
            1 + len(REQUIRED_QUALITY_ANCHOR_IDS)
            if args.quality_anchors_only
            else len(scenarios)
        ),
        "campaign_mode": (
            "quality_anchors_only_distinct_provenance_artifact"
            if args.quality_anchors_only
            else "full_021081_landscape"
        ),
        "state_regimes": state_regime_rows(active_regimes),
        "scientific_scope": {
            "observed": (
                "23 open purchase orders observed in the 2025-01-01 ERP snapshot; "
                "delivery and usable dates are planned dates, not actual receipts"
            ),
            "simulated": "counterfactual dates and usable quantities plus downstream engine response",
            "isolated_supplier_scopes": list(SUPPLIER_IDS),
            "common_cause_scope": "all four suppliers",
            "flow_classes_kept_separate": ["opening_order_book_replayed", "dynamic_mrp"],
            "coherence_with_clean_dynamic_reference": (
                "The clean dynamic reference has zero 021081 arrival when no opening "
                "order book is seeded. This campaign deliberately replays 23 planned "
                "open orders, so it is a different reference, not a contradiction."
            ),
            "quantity_unit_provenance": (
                "Order quantities come from the graph's already-standardized quantity "
                "field; every target row declares uom=KG and the campaign does not "
                "apply a new conversion."
            ),
            "mechanism_sensitivity_interpretation": (
                "Counts and shares describe which tested scenarios create an effect. "
                "They are not historical incident recurrence or supplier probabilities."
            ),
            "quality_warning": (
                "Observed 021081 stock and modeled consumption imply unusually long cover. "
                "This campaign reports the masking effect; it does not silently normalize stock."
            ),
            "critical_bom_unit_validation": {
                "status": "unit_to_validate_with_industrial_owner",
                "source": "773474.xlsx BOM",
                "output_declared_quantity_g": BOM_773474_OUTPUT_QTY_G,
                "output_description": "ELSSR CONT. 1000 L",
                "input_item": ITEM_ID,
                "input_declared_quantity_kg": BOM_021081_INPUT_QTY_KG,
                "literal_graph_ratio_kg_per_kg": (
                    BOM_LITERAL_INPUT_KG_PER_OUTPUT_KG
                ),
                "example_3_2m_g_lot_consumption_kg": (
                    MODELLED_REFERENCE_LOT_INPUT_KG
                ),
                "alternative_hypothesis": (
                    "Interpret output as 1000 kg/L-equivalent, divide the literal "
                    "ratio by 1000; this is not an asserted correction."
                ),
                "source_graph_unchanged": True,
            },
            "intermediate_773474_masking_audit": {
                "opening_stock_sdc_1450_g": INTERMEDIATE_773474_STOCK_SDC_G,
                "opening_stock_m_1430_g": INTERMEDIATE_773474_STOCK_M1430_G,
                "opening_stock_total_g": INTERMEDIATE_773474_TOTAL_STOCK_G,
                "approx_773474_per_268967_lot_g": (
                    INTERMEDIATE_773474_PER_268967_LOT_G
                ),
                "released_268967_lot_count": (
                    INTERMEDIATE_268967_RELEASED_LOT_COUNT
                ),
                "approx_horizon_need_g": (
                    INTERMEDIATE_773474_HORIZON_NEED_G
                ),
                "horizon_773474_production_g": (
                    INTERMEDIATE_773474_HORIZON_PRODUCTION_G
                ),
                "stock_cover_lots": INTERMEDIATE_773474_STOCK_COVER_LOTS,
                "stock_multiple_of_horizon_need": (
                    INTERMEDIATE_773474_STOCK_TO_HORIZON_NEED
                ),
                "stock_plus_production_multiple_of_horizon_need": (
                    INTERMEDIATE_773474_STOCK_PLUS_PRODUCTION_TO_NEED
                ),
                "021081_stock_multiple_of_horizon_intermediate_consumption": (
                    COMPONENT_021081_STOCK_TO_HORIZON_CONSUMPTION
                ),
                "021081_order_book_multiple_of_horizon_intermediate_consumption": (
                    COMPONENT_021081_ORDER_BOOK_TO_HORIZON_CONSUMPTION
                ),
                "interpretation": (
                    "Masking is cumulative across opening intermediate stock, "
                    "intermediate production, oversized component stock and the open "
                    "order book. Reducing only 021081 is not a coherent global lean state."
                ),
                **intermediate_masking_provenance,
            },
            "observed_stock_validation_questions": [
                "Is item 021081 really expressed in KG throughout the source systems?",
                "Is the J0 quantity free stock, or does it include blocked, allocated or expired stock?",
                "Is the stock owned and physically available at SDC-1450?",
                "What shelf life and quality-release status apply to this quantity?",
            ],
            "lot_trace_capability_and_limit": (
                "The opt-in native replay preserves supplier_id, source_row, shipment_id "
                "and risk IDs on opening-purchase receipt lots. source_row is a technical "
                "line from the ERP snapshot, not an observed industrial batch/lot identifier."
            ),
        },
        "protocol_args": list(ACTIVE_021081_PROTOCOL_ARGS),
        "opening_order_risk_mode": args.opening_order_risk_mode,
        "capacity_opening_order_fallback": (
            "explicit_fifo_overlay_because_native_engine_requires_a_dated_supplier_capacity_calendar"
        ),
    }
    if previous_manifest:
        manifest["created_at_utc"] = previous_manifest.get(
            "created_at_utc", manifest["created_at_utc"]
        )
        manifest["resume_history"] = [
            *(previous_manifest.get("resume_history") or []),
            {
                "resumed_at_utc": utc_now(),
                "previous_status": previous_manifest.get("status", ""),
                "top_per_scope": args.top_per_scope,
                "required_quality_anchor_ids": list(
                    REQUIRED_QUALITY_ANCHOR_IDS
                ),
            },
        ]
    write_json(manifest_path, manifest)
    if args.prepare_only:
        print(f"[OK] Prepared 021081 campaign at {output_root}")
        return 0

    profile_args = engine_profile_args(profile)
    baseline = scenarios[0]
    observed_screening_scenarios = scenarios
    if args.quality_anchors_only:
        anchor_scenarios, _ = add_required_scenarios([], scenarios)
        observed_screening_scenarios = [baseline, *anchor_scenarios]
    elif args.smoke:
        smoke_stress = next(
            scenario
            for scenario in scenarios
            if scenario.scope_id == "SDC-VD0960508A"
            and scenario.mechanism == "delivery_delay"
            and math.isclose(scenario.value, 30.0)
        )
        observed_screening_scenarios = [baseline, smoke_stress]

    observed_rows = _run_cases(
        source_graph=source_graph,
        source_graph_path=source_graph_path,
        engine=engine,
        profile_args=profile_args,
        output_root=output_root,
        scenarios=observed_screening_scenarios,
        seeds=[args.screening_seed],
        stage="smoke" if args.smoke else "screening_observed_state",
        days=args.days,
        workers=min(args.workers, 1 if args.smoke else args.workers),
        retention=args.retention,
        metric_path=output_root / "screening_metrics_observed_2025.csv",
        opening_order_risk_mode=args.opening_order_risk_mode,
        state_regime=observed_regime,
        measurement_start_stock_scale_csv=regime_input_paths[
            observed_regime.regime_id
        ],
        resume=args.resume,
    )
    observed_rows = attach_pairs(observed_rows)
    write_csv(
        output_root / "screening_metrics_observed_2025.csv", observed_rows
    )
    screening_rows: list[dict[str, Any]] = list(observed_rows)

    # The observed state receives the exhaustive 91-case screening.  The
    # prospective envelope is intentionally smaller: it replays distinct,
    # decision-relevant configurations selected from that exhaustive pass at
    # four explicit stock-cover levels.
    prospective_scenarios: list[Scenario] = []
    prospective_quality_anchor_added_count = 0
    if prospective_regimes:
        if args.quality_anchors_only:
            prospective_selected, _ = add_required_scenarios([], scenarios)
        else:
            prospective_selected = select_confirmation_scenarios(
                observed_rows,
                scenarios,
                top_per_scope=args.top_per_scope,
            )
            (
                prospective_selected,
                prospective_quality_anchor_added_count,
            ) = add_required_scenarios(prospective_selected, scenarios)
        prospective_scenarios = [
            baseline,
            *prospective_selected,
        ]
        prospective_scenarios = list(
            {scenario.scenario_id: scenario for scenario in prospective_scenarios}.values()
        )
        for regime in prospective_regimes:
            regime_rows = _run_cases(
                source_graph=source_graph,
                source_graph_path=source_graph_path,
                engine=engine,
                profile_args=profile_args,
                output_root=output_root,
                scenarios=prospective_scenarios,
                seeds=[args.screening_seed],
                stage="screening_prospective_cover",
                days=args.days,
                workers=args.workers,
                retention=args.retention,
                metric_path=(
                    output_root
                    / f"screening_metrics_{regime.regime_id}.csv"
                ),
                opening_order_risk_mode=args.opening_order_risk_mode,
                state_regime=regime,
                measurement_start_stock_scale_csv=regime_input_paths[
                    regime.regime_id
                ],
                resume=args.resume,
            )
            regime_rows = attach_pairs(regime_rows)
            write_csv(
                output_root / f"screening_metrics_{regime.regime_id}.csv",
                regime_rows,
            )
            screening_rows.extend(regime_rows)
    write_csv(output_root / "screening_metrics.csv", screening_rows)

    baselines = _baseline_by_seed(screening_rows)
    flow_gates: dict[str, Any] = {}
    for regime in active_regimes:
        reference_row = baselines[(regime.regime_id, args.screening_seed)]
        gate = reference_flow_gate(reference_row)
        if regime.target_cover_days is not None:
            actual_j0 = to_float(
                reference_row.get("measurement_start_stock_after_qty_kg"),
                math.nan,
            )
            gate["configured_reduced_cover_stock_qty_kg"] = (
                regime.opening_stock_qty_kg
            )
            gate["measured_j0_stock_qty_kg"] = actual_j0
            gate["reduced_cover_stock_matches_configuration"] = math.isclose(
                actual_j0,
                regime.opening_stock_qty_kg,
                rel_tol=0.0,
                abs_tol=1e-3,
            )
            if not gate["reduced_cover_stock_matches_configuration"]:
                gate["errors"].append(
                    "prospective J0 stock does not match the declared cover hypothesis"
                )
                gate["validated"] = False
        flow_gates[regime.regime_id] = gate
    write_json(output_root / "reference_flow_gate.json", flow_gates)
    invalid_gates = {
        regime: gate for regime, gate in flow_gates.items() if not gate["validated"]
    }
    if invalid_gates:
        manifest.update(
            {"status": "invalid_reference", "reference_flow_gates": flow_gates}
        )
        write_json(output_root / "campaign_manifest.json", manifest)
        raise CampaignValidationError(
            "Reference flow gate failed: "
            + json.dumps(invalid_gates, ensure_ascii=False)
        )

    observed_reference = baselines[(observed_regime.regime_id, args.screening_seed)]
    observed_daily_consumption = to_float(
        observed_reference.get("component_consumed_avg_qty_per_day"), math.nan
    )
    observed_physical_cover_days = (
        observed_regime.opening_stock_qty_kg / observed_daily_consumption
        if observed_daily_consumption > 1e-9
        else math.inf
    )
    observed_horizon_consumption = to_float(
        observed_reference.get("component_consumed_qty_kg"), math.nan
    )
    observed_stock_to_horizon_consumption = (
        observed_regime.opening_stock_qty_kg / observed_horizon_consumption
        if observed_horizon_consumption > 1e-9
        else math.inf
    )

    confirmation_rows: list[dict[str, Any]] = []
    selected: list[Scenario] = []
    confirmation_quality_anchor_added_count = 0
    confirmation_regime: StateRegime | None = None
    if not args.smoke:
        if args.quality_anchors_only:
            selected, _ = add_required_scenarios([], scenarios)
        else:
            selected = select_confirmation_scenarios(
                screening_rows, scenarios, top_per_scope=args.top_per_scope
            )
            (
                selected,
                confirmation_quality_anchor_added_count,
            ) = add_required_scenarios(selected, scenarios)
        if prospective_regimes:
            confirmation_regime_id = most_discriminating_regime_id(
                screening_rows, prospective_regimes
            )
            confirmation_regime = next(
                regime
                for regime in prospective_regimes
                if regime.regime_id == confirmation_regime_id
            )
        else:
            confirmation_regime = observed_regime
        confirmation_scenarios = [baseline, *selected]
        confirmation_rows = _run_cases(
            source_graph=source_graph,
            source_graph_path=source_graph_path,
            engine=engine,
            profile_args=profile_args,
            output_root=output_root,
            scenarios=confirmation_scenarios,
            seeds=parse_seeds(args.confirmation_seeds),
            stage="confirmation_paired",
            days=args.days,
            workers=args.workers,
            retention=args.retention,
            metric_path=output_root / "confirmation_metrics.csv",
            opening_order_risk_mode=args.opening_order_risk_mode,
            state_regime=confirmation_regime,
            measurement_start_stock_scale_csv=regime_input_paths[
                confirmation_regime.regime_id
            ],
            resume=args.resume,
        )
        confirmation_rows = attach_pairs(confirmation_rows)
        write_csv(output_root / "confirmation_metrics.csv", confirmation_rows)

    screening_summaries = summarize_results(screening_rows, scenarios)
    confirmation_summaries = summarize_results(confirmation_rows, scenarios)
    summary_by_key = {
        (str(row.get("state_regime")), str(row.get("scenario_id"))): row
        for row in screening_summaries
    }
    for row in confirmation_summaries:
        summary_by_key[
            (str(row.get("state_regime")), str(row.get("scenario_id")))
        ] = row
    summaries = list(summary_by_key.values())
    summaries.sort(
        key=lambda row: (
            str(row.get("state_regime")), str(row.get("scenario_id"))
        )
    )
    criticality: list[dict[str, Any]] = []
    mechanisms: list[dict[str, Any]] = []
    for regime in active_regimes:
        regime_summaries = [
            row
            for row in summaries
            if str(row.get("state_regime") or "") == regime.regime_id
        ]
        criticality.extend(
            supplier_criticality_rows(regime_summaries, source_audit)
        )
        mechanisms.extend(mechanism_summary_rows(regime_summaries))
    write_csv(output_root / "scenario_summary.csv", summaries)
    write_csv(
        output_root / "supplier_criticality_ranking_021081.csv", criticality
    )
    write_csv(
        output_root / "mechanism_sensitivity_summary_021081.csv", mechanisms
    )
    # Compatibility alias for existing technical consumers.  The word
    # "recurrence" must not be used in business interpretation: no historical
    # incident frequencies are present in this campaign.
    write_csv(
        output_root / "mechanism_recurrence_summary_021081.csv", mechanisms
    )
    write_csv(
        output_root / "prospective_reduced_cover_summary.csv",
        [
            row
            for row in summaries
            if str(row.get("state_regime") or "") != "observed_2025"
        ],
    )

    masking_audit = {
        "observed_opening_stock_qty_kg": observed_regime.opening_stock_qty_kg,
        "simulated_horizon_days": args.days,
        "simulated_horizon_consumption_qty_kg": observed_horizon_consumption,
        "observed_stock_multiple_of_horizon_consumption": (
            observed_stock_to_horizon_consumption
        ),
        "simulated_average_consumption_qty_per_day": (
            observed_daily_consumption
        ),
        "physical_cover_days_at_simulated_average_consumption": (
            observed_physical_cover_days
        ),
        "interpretation": (
            "Masking by opening stock, not acquired resilience. Validate KG, "
            "free/blocked/allocated/expired status, ownership/site and shelf life."
        ),
    }
    write_business_outputs(
        output_root=output_root,
        source_audit=source_audit,
        active_regimes=active_regimes,
        summaries=summaries,
        confirmation_summaries=confirmation_summaries,
        criticality=criticality,
        mechanisms=mechanisms,
        flow_gates=flow_gates,
        masking_audit=masking_audit,
        confirmation_regime=confirmation_regime,
        days=args.days,
        intermediate_masking_provenance=intermediate_masking_provenance,
    )

    manifest.update(
        {
            "status": "smoke_complete" if args.smoke else "complete",
            "completed_at_utc": utc_now(),
            "reference_flow_gates": flow_gates,
            "screening_case_count": len(screening_rows),
            "observed_state_screening_case_count": len(observed_rows),
            "prospective_reduced_cover_screening_case_count": (
                len(screening_rows) - len(observed_rows)
            ),
            "prospective_screening_scenario_ids": [
                scenario.scenario_id for scenario in prospective_scenarios
            ],
            "selected_confirmation_scenario_ids": [item.scenario_id for item in selected],
            "required_quality_anchor_audit": {
                "required_scenario_ids": list(REQUIRED_QUALITY_ANCHOR_IDS),
                "prospective_present_scenario_ids": [
                    scenario_id
                    for scenario_id in REQUIRED_QUALITY_ANCHOR_IDS
                    if scenario_id
                    in {item.scenario_id for item in prospective_scenarios}
                ],
                "confirmation_present_scenario_ids": [
                    scenario_id
                    for scenario_id in REQUIRED_QUALITY_ANCHOR_IDS
                    if scenario_id in {item.scenario_id for item in selected}
                ],
                "prospective_anchor_scenarios_added_beyond_ranked_selection": (
                    prospective_quality_anchor_added_count
                ),
                "confirmation_anchor_scenarios_added_beyond_ranked_selection": (
                    confirmation_quality_anchor_added_count
                ),
                "validated": (
                    not prospective_regimes
                    or all(
                        scenario_id
                        in {item.scenario_id for item in prospective_scenarios}
                        and scenario_id in {item.scenario_id for item in selected}
                        for scenario_id in REQUIRED_QUALITY_ANCHOR_IDS
                    )
                ),
                "interpretation": (
                    "Quality hold is a mandatory methodological anchor even when "
                    "its strict outcome signature matches a delivery-delay case."
                ),
            },
            "confirmation_state_regime": (
                confirmation_regime.regime_id
                if confirmation_regime is not None
                else ""
            ),
            "confirmation_case_count": len(confirmation_rows),
            "observed_stock_masking_audit": masking_audit,
            "business_outputs": {
                "summary_markdown": "RESUME_METIER_021081.md",
                "future_page_payload": "future_autonomous_page_payload.json",
                "top_observed_state_cases": "top_3_cases_observed_state_021081.csv",
                "top_decision_cases": "top_3_cases_decision_021081.csv",
            },
            "supplier_ranking_status": (
                "downstream_effect_and_order_book_exposure"
                if any(
                    to_int(row.get("scenarios_with_downstream_product_effect")) > 0
                    for row in criticality
                )
                else "order_book_exposure_only_downstream_effect_masked_by_state"
            ),
            "supplier_criticality_ranking": criticality,
            "mechanism_summary": mechanisms,
        }
    )
    write_json(output_root / "campaign_manifest.json", manifest)
    print(f"[OK] 021081 active-flow campaign: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
