from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etudecas.simulation.initial_state_policy import merge_living_initial_state_args  # noqa: E402

SIM_SCRIPT = ROOT / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"
INPUT_JSON = (
    ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
OUT_ROOT = ROOT / "etudecas" / "simulation" / "result" / "risk_amplitude_duration_sweep_5y"
RISK_DIR = OUT_ROOT / "risk_csv"
REPORT_DIR = OUT_ROOT / "reports"
SUMMARY_JSON = OUT_ROOT / "risk_amplitude_duration_sweep_summary.json"
SUMMARY_CSV = OUT_ROOT / "risk_amplitude_duration_sweep_summary.csv"
REPORT_MD = REPORT_DIR / "risk_amplitude_duration_sweep_report.md"


@dataclass(frozen=True)
class RiskLane:
    supplier_id: str
    item_id: str
    dst_node_id: str
    label: str


@dataclass(frozen=True)
class RiskEvent:
    event_id: str
    risk_type: str
    lane: RiskLane
    start_day: int
    end_day: int
    multiplier: float
    notes: str


@dataclass(frozen=True)
class Case:
    case_id: str
    label: str
    family: str
    severity: str
    events: tuple[RiskEvent, ...] = ()
    state_dependent: bool = False
    extra_args: tuple[str, ...] = ()


PF_268967_LANES = (
    RiskLane("SDC-VD0520132A", "item:038005", "M-1430", "038005 MP"),
    RiskLane("SDC-VD0914690A", "item:042342", "M-1430", "042342 composant"),
    RiskLane("SDC-VD0525412A", "item:333362", "M-1430", "333362 composant"),
    RiskLane("SDC-VD0993480A", "item:344135", "M-1430", "344135 composant"),
    RiskLane("SDC-VD0520115A", "item:708073", "M-1430", "708073 composant"),
    RiskLane("SDC-VD0508918A", "item:730384", "M-1430", "730384 composant"),
    RiskLane("SDC-VD1095770A", "item:734545", "M-1430", "734545 composant"),
    RiskLane("SDC-1450", "item:773474", "M-1430", "773474 PFI"),
)

PF_268091_KEY_LANES = (
    RiskLane("SDC-VD0951020A", "item:007923", "M-1810", "007923 gros flux"),
    RiskLane("SDC-VD0525412A", "item:333362", "M-1810", "333362 composant"),
    RiskLane("SDC-VD0989480A", "item:426331", "M-1810", "426331 composant"),
    RiskLane("SDC-1450", "item:693055", "M-1810", "693055 PFI"),
)

FACTORY_DC_PF_LANE = RiskLane("M-1430", "item:268967", "DC-1920", "transport usine -> DC 268967")
DC_CLIENT_PF_LANE = RiskLane("DC-1920", "item:268967", "C-XXXXX", "transport DC -> client 268967")


def slug(value: Any) -> str:
    text = str(value).replace("item:", "").replace("SDC-", "SDC_")
    out = []
    for ch in text:
        out.append(ch if ch.isalnum() else "_")
    return "_".join(part for part in "".join(out).split("_") if part)


def event(
    case_id: str,
    risk_type: str,
    lane: RiskLane,
    multiplier: float,
    *,
    duration: int,
    start_day: int = 0,
    suffix: str = "",
) -> RiskEvent:
    end_day = start_day + max(1, int(duration)) - 1
    suffix_part = f"_{suffix}" if suffix else ""
    event_id = f"{case_id}_{risk_type}_{slug(lane.supplier_id)}_{slug(lane.item_id)}{suffix_part}"
    return RiskEvent(
        event_id=event_id,
        risk_type=risk_type,
        lane=lane,
        start_day=start_day,
        end_day=end_day,
        multiplier=float(multiplier),
        notes=f"{case_id}: {risk_type} on {lane.label} for {duration}d",
    )


def events_for_lanes(
    case_id: str,
    risk_type: str,
    lanes: tuple[RiskLane, ...],
    multiplier: float,
    *,
    duration: int,
    start_day: int = 0,
) -> tuple[RiskEvent, ...]:
    return tuple(
        event(case_id, risk_type, lane, multiplier, duration=duration, start_day=start_day, suffix=str(idx + 1))
        for idx, lane in enumerate(lanes)
    )


def combined_events(
    case_id: str,
    lanes: tuple[RiskLane, ...],
    *,
    duration: int,
    capacity: float,
    availability: float,
    lead_extra: float,
    quality_yield: float,
    start_day: int = 0,
) -> tuple[RiskEvent, ...]:
    out: list[RiskEvent] = []
    for idx, lane in enumerate(lanes):
        out.append(event(case_id, "capacity", lane, capacity, duration=duration, start_day=start_day, suffix=f"{idx+1}_cap"))
        out.append(event(case_id, "availability", lane, availability, duration=duration, start_day=start_day, suffix=f"{idx+1}_avl"))
        out.append(event(case_id, "lead_time_extra_days", lane, lead_extra, duration=duration, start_day=start_day, suffix=f"{idx+1}_lead"))
        out.append(event(case_id, "quality_yield", lane, quality_yield, duration=duration, start_day=start_day, suffix=f"{idx+1}_qty"))
    return tuple(out)


def build_cases() -> list[Case]:
    cases: list[Case] = [
        Case("baseline_nominal", "Nominal sans risque", "reference", "baseline"),
        Case("state_only", "State-dependent seul", "state-dependent", "auto", state_dependent=True),
    ]
    for duration in (30, 90):
        for mult in (0.70, 0.40, 0.20):
            cid = f"pf268967_capacity_{int(mult*100)}_{duration}d"
            cases.append(
                Case(
                    cid,
                    f"PF268967 capacite x{mult:g} {duration}j",
                    "capacity",
                    f"x{mult:g}_{duration}d",
                    events_for_lanes(cid, "capacity", PF_268967_LANES, mult, duration=duration),
                    state_dependent=True,
                )
            )
    for duration in (30, 90):
        for mult in (0.70, 0.40, 0.10):
            cid = f"pf268967_availability_{int(mult*100)}_{duration}d"
            cases.append(
                Case(
                    cid,
                    f"PF268967 disponibilite x{mult:g} {duration}j",
                    "availability",
                    f"x{mult:g}_{duration}d",
                    events_for_lanes(cid, "availability", PF_268967_LANES, mult, duration=duration),
                    state_dependent=True,
                )
            )
    for duration in (60, 180):
        for extra_days in (14, 45, 90):
            cid = f"pf268967_delay_plus_{extra_days}_{duration}d"
            cases.append(
                Case(
                    cid,
                    f"PF268967 delai +{extra_days}j {duration}j",
                    "lead_time_extra_days",
                    f"+{extra_days}d_{duration}d",
                    events_for_lanes(cid, "lead_time_extra_days", PF_268967_LANES, extra_days, duration=duration),
                    state_dependent=True,
                )
            )
    for duration in (60, 180):
        for mult in (0.90, 0.75, 0.50):
            cid = f"pf268967_quality_yield_{int(mult*100)}_{duration}d"
            cases.append(
                Case(
                    cid,
                    f"PF268967 qualite rendement x{mult:g} {duration}j",
                    "quality_yield",
                    f"x{mult:g}_{duration}d",
                    events_for_lanes(cid, "quality_yield", PF_268967_LANES, mult, duration=duration),
                    state_dependent=True,
                )
            )
    for frac in (0.25, 0.50, 0.80):
        cid = f"pf268967_stock_writeoff_{int(frac*100)}_j0"
        cases.append(
            Case(
                cid,
                f"PF268967 perte stock fournisseur {int(frac*100)}% J0",
                "stock_writeoff",
                f"{int(frac*100)}pct",
                events_for_lanes(cid, "stock_writeoff", PF_268967_LANES, frac, duration=1),
                state_dependent=True,
            )
        )
    for extra_days in (7, 21, 45):
        cid = f"factory_dc_pf_delay_plus_{extra_days}_90d"
        cases.append(
            Case(
                cid,
                f"Transport usine->DC 268967 +{extra_days}j 90j",
                "transport_factory_dc",
                f"+{extra_days}d",
                (event(cid, "lead_time_extra_days", FACTORY_DC_PF_LANE, extra_days, duration=90),),
                state_dependent=True,
            )
        )
        cid = f"dc_customer_pf_delay_plus_{extra_days}_90d"
        cases.append(
            Case(
                cid,
                f"Transport DC->client 268967 +{extra_days}j 90j",
                "transport_dc_customer",
                f"+{extra_days}d",
                (event(cid, "lead_time_extra_days", DC_CLIENT_PF_LANE, extra_days, duration=90),),
                state_dependent=True,
            )
        )
    for mult in (0.40, 0.20):
        cid = f"pf268091_key_capacity_{int(mult*100)}_90d"
        cases.append(
            Case(
                cid,
                f"PF268091 composants clefs capacite x{mult:g} 90j",
                "capacity_268091",
                f"x{mult:g}_90d",
                events_for_lanes(cid, "capacity", PF_268091_KEY_LANES, mult, duration=90),
                state_dependent=True,
            )
        )
    cases.extend(
        [
            Case(
                "pf268967_combined_moderate_60d",
                "PF268967 combine modere 60j",
                "combined",
                "moderate_60d",
                combined_events(
                    "pf268967_combined_moderate_60d",
                    PF_268967_LANES,
                    duration=60,
                    capacity=0.70,
                    availability=0.70,
                    lead_extra=14,
                    quality_yield=0.90,
                ),
                state_dependent=True,
            ),
            Case(
                "pf268967_combined_severe_120d",
                "PF268967 combine severe 120j",
                "combined",
                "severe_120d",
                combined_events(
                    "pf268967_combined_severe_120d",
                    PF_268967_LANES,
                    duration=120,
                    capacity=0.40,
                    availability=0.40,
                    lead_extra=45,
                    quality_yield=0.75,
                ),
                state_dependent=True,
            ),
            Case(
                "pf268967_combined_extreme_180d_no_external",
                "PF268967 combine extreme 180j sans appro fournisseur",
                "combined_no_external",
                "extreme_180d",
                combined_events(
                    "pf268967_combined_extreme_180d_no_external",
                    PF_268967_LANES,
                    duration=180,
                    capacity=0.20,
                    availability=0.20,
                    lead_extra=90,
                    quality_yield=0.50,
                ),
                state_dependent=True,
                extra_args=("--no-external-procurement-enabled",),
            ),
            Case(
                "network_transport_block_120d",
                "Transport usine/DC/client 268967 +45j 120j",
                "transport_network",
                "+45d_120d",
                (
                    event("network_transport_block_120d", "lead_time_extra_days", FACTORY_DC_PF_LANE, 45, duration=120, suffix="factory_dc"),
                    event("network_transport_block_120d", "lead_time_extra_days", DC_CLIENT_PF_LANE, 45, duration=120, suffix="dc_client"),
                ),
                state_dependent=True,
            ),
        ]
    )
    return cases


def write_risk_csv(case: Case) -> Path | None:
    if not case.events:
        return None
    RISK_DIR.mkdir(parents=True, exist_ok=True)
    path = RISK_DIR / f"{case.case_id}.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
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
            ],
        )
        writer.writeheader()
        for ev in case.events:
            writer.writerow(
                {
                    "event_id": ev.event_id,
                    "risk_type": ev.risk_type,
                    "supplier_id": ev.lane.supplier_id,
                    "item_id": ev.lane.item_id,
                    "dst_node_id": ev.lane.dst_node_id,
                    "edge_id": "",
                    "start_day": ev.start_day,
                    "end_day": ev.end_day,
                    "multiplier": ev.multiplier,
                    "notes": ev.notes,
                }
            )
    return path


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        val = float(value)
        if not math.isfinite(val):
            return default
        return val
    except Exception:
        return default


def run_case(case: Case, *, force: bool = False) -> dict[str, Any]:
    case_dir = OUT_ROOT / "cases" / case.case_id
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    if summary_path.exists() and not force:
        return load_json(summary_path)
    risk_csv = write_risk_csv(case)
    case_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(SIM_SCRIPT),
        "--input",
        str(INPUT_JSON),
        "--output-dir",
        str(case_dir),
        "--scenario-id",
        "scn:BASE",
        "--days",
        "1825",
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
        "--seed",
        "42",
    ]
    if case.state_dependent:
        cmd.append("--supplier-state-dependent-risks")
    if risk_csv is not None:
        cmd.extend(["--supplier-risk-events-csv", str(risk_csv)])
    cmd.extend(merge_living_initial_state_args(case.extra_args))
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        details = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part)
        raise RuntimeError(f"Simulation failed for {case.case_id}\n{details}")
    return load_json(summary_path)


def backlog_metrics(case_dir: Path) -> dict[str, float]:
    rows = read_rows(case_dir / "data" / "production_demand_service_daily.csv")
    by_day: dict[int, float] = defaultdict(float)
    required_by_day: dict[int, float] = defaultdict(float)
    served_by_day: dict[int, float] = defaultdict(float)
    for row in rows:
        day = int(to_float(row.get("day")))
        by_day[day] += max(0.0, to_float(row.get("backlog_end_qty")))
        required_by_day[day] += max(0.0, to_float(row.get("required_with_backlog_qty")))
        served_by_day[day] += max(0.0, to_float(row.get("served_qty")))
    startup_days = 0
    while by_day.get(startup_days, 0.0) > 1e-9:
        startup_days += 1
    decision_values = [value for day, value in by_day.items() if day >= startup_days and value > 1e-9]
    service_short_days = sum(1 for day, required in required_by_day.items() if day >= startup_days and served_by_day.get(day, 0.0) + 1e-6 < required)
    return {
        "backlog_days_ex_startup": float(len(decision_values)),
        "backlog_max_ex_startup": max(decision_values) if decision_values else 0.0,
        "startup_backlog_days": float(startup_days),
        "service_short_days_ex_startup": float(service_short_days),
    }


def production_metrics(case_dir: Path) -> dict[str, float]:
    rows = read_rows(case_dir / "data" / "production_plan_events.csv")
    delay_rows = [
        row for row in rows if row.get("event_type") == "delay_input_shortage" or row.get("reason") == "input_shortage"
    ]
    weekly_rows = [
        row for row in rows if row.get("event_type") == "delay_weekly_lot_limit" or row.get("reason") == "weekly_lot_limit"
    ]
    return {
        "input_delay_count": float(len(delay_rows)),
        "input_delay_days": float(len({int(to_float(row.get("day"))) for row in delay_rows})),
        "input_delay_volume": sum(max(0.0, to_float(row.get("shortfall_vs_lot_plan_qty"))) for row in delay_rows),
        "weekly_lot_delay_count": float(len(weekly_rows)),
    }


def risk_metrics(case_dir: Path) -> dict[str, float]:
    rows = read_rows(case_dir / "data" / "supplier_risk_events_applied_daily.csv")
    state_rows = read_rows(case_dir / "data" / "supplier_state_dependent_risk_events.csv")
    families = Counter()
    for row in rows:
        if to_float(row.get("capacity_multiplier"), 1.0) != 1.0:
            families["capacity"] += 1
        if to_float(row.get("stock_multiplier"), 1.0) != 1.0 or to_float(row.get("stock_writeoff_fraction"), 0.0) != 0.0:
            families["stock"] += 1
        if to_float(row.get("lead_time_multiplier"), 1.0) != 1.0 or to_float(row.get("lead_time_extra_days"), 0.0) != 0.0:
            families["delay"] += 1
        if (
            to_float(row.get("quality_delay_days"), 0.0) != 0.0
            or to_float(row.get("quality_yield_multiplier"), 1.0) != 1.0
            or to_float(row.get("external_quality_yield_multiplier"), 1.0) != 1.0
        ):
            families["quality"] += 1
        if to_float(row.get("availability_multiplier"), 1.0) != 1.0 or to_float(row.get("external_availability_multiplier"), 1.0) != 1.0:
            families["availability"] += 1
        if (
            to_float(row.get("purchase_cost_multiplier"), 1.0) != 1.0
            or to_float(row.get("transport_cost_multiplier"), 1.0) != 1.0
            or to_float(row.get("external_cost_multiplier"), 1.0) != 1.0
        ):
            families["cost"] += 1
    out = {
        "risk_applied_rows": float(len(rows)),
        "risk_applied_suppliers": float(len({row.get("supplier_id") for row in rows if row.get("supplier_id")})),
        "state_events_generated": float(len(state_rows)),
    }
    out.update({f"risk_family_{key}_rows": float(value) for key, value in families.items()})
    return out


def min_stock_metrics(case_dir: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for label, rel in [
        ("dc", "production_dc_stocks_daily.csv"),
        ("input", "production_input_stocks_daily.csv"),
        ("supplier", "production_supplier_stocks_daily.csv"),
    ]:
        rows = read_rows(case_dir / "data" / rel)
        mins: dict[tuple[str, str], float] = {}
        zero_days = 0
        for row in rows:
            key = (row.get("node_id") or "", row.get("item_id") or "")
            stock = to_float(row.get("stock_end_of_day"))
            if key not in mins or stock < mins[key]:
                mins[key] = stock
            if stock <= 1e-9:
                zero_days += 1
        out[f"{label}_pairs_zero_or_negative"] = float(sum(1 for value in mins.values() if value <= 1e-9))
        out[f"{label}_zero_stock_rows"] = float(zero_days)
    return out


def extract_case(case: Case, summary: dict[str, Any]) -> dict[str, Any]:
    case_dir = OUT_ROOT / "cases" / case.case_id
    kpis = summary.get("kpis") or {}
    policy = summary.get("policy") or {}
    supplier_risk = policy.get("supplier_risk") or {}
    state_risk = policy.get("supplier_state_dependent_risk") or {}
    row: dict[str, Any] = {
        "case_id": case.case_id,
        "label": case.label,
        "family": case.family,
        "severity": case.severity,
        "configured_events": len(case.events),
        "state_dependent_enabled": bool(case.state_dependent),
        "explicit_events_loaded": int(to_float(supplier_risk.get("event_count"))),
        "state_events_summary": int(to_float(state_risk.get("generated_event_count"))),
        "fill_rate": to_float(kpis.get("fill_rate"), 1.0),
        "ending_backlog": to_float(kpis.get("ending_backlog")),
        "total_demand": to_float(kpis.get("total_demand")),
        "total_served": to_float(kpis.get("total_served")),
        "total_produced": to_float(kpis.get("total_produced")),
        "total_shipped": to_float(kpis.get("total_shipped")),
        "total_cost": to_float(kpis.get("total_cost")),
        "transport_cost": to_float(kpis.get("total_transport_cost")),
        "holding_cost": to_float(kpis.get("total_holding_cost")),
        "warehouse_cost": to_float(kpis.get("total_warehouse_operating_cost")),
        "inventory_risk_cost": to_float(kpis.get("total_inventory_risk_cost")),
        "purchase_cost": to_float(kpis.get("total_purchase_cost")),
        "production_cost": to_float(kpis.get("total_production_cost")),
        "external_procurement_cost": to_float(kpis.get("total_external_procurement_cost")),
        "external_procured_qty": to_float(kpis.get("total_external_procured_qty")),
        "external_procured_rejected_qty": to_float(kpis.get("total_external_procured_rejected_qty")),
        "unreliable_loss_qty": to_float(kpis.get("total_unreliable_loss_qty")),
        "avg_inventory": to_float(kpis.get("avg_inventory")),
        "ending_inventory": to_float(kpis.get("ending_inventory")),
    }
    row.update(backlog_metrics(case_dir))
    row.update(production_metrics(case_dir))
    row.update(risk_metrics(case_dir))
    row.update(min_stock_metrics(case_dir))
    return row


def add_impacts(rows: list[dict[str, Any]]) -> None:
    nominal = next(row for row in rows if row["case_id"] == "baseline_nominal")
    for row in rows:
        row["fill_rate_delta_pp"] = (row["fill_rate"] - nominal["fill_rate"]) * 100.0
        row["cost_delta"] = row["total_cost"] - nominal["total_cost"]
        row["external_cost_delta"] = row["external_procurement_cost"] - nominal["external_procurement_cost"]
        row["loss_delta"] = row["unreliable_loss_qty"] - nominal["unreliable_loss_qty"]
        row["input_delay_delta"] = row["input_delay_count"] - nominal["input_delay_count"]
        row["input_delay_volume_delta"] = row["input_delay_volume"] - nominal["input_delay_volume"]
        row["produced_delta"] = row["total_produced"] - nominal["total_produced"]
        row["shipped_delta"] = row["total_shipped"] - nominal["total_shipped"]
        row["inventory_delta"] = row["avg_inventory"] - nominal["avg_inventory"]
        row["stock_zero_delta"] = (
            row["input_zero_stock_rows"]
            + row["supplier_zero_stock_rows"]
            + row["dc_zero_stock_rows"]
            - nominal["input_zero_stock_rows"]
            - nominal["supplier_zero_stock_rows"]
            - nominal["dc_zero_stock_rows"]
        )
        row["impact_score"] = (
            max(0.0, -row["fill_rate_delta_pp"]) * 1_000_000.0
            + row["backlog_max_ex_startup"] * 25.0
            + max(0.0, row["input_delay_volume_delta"]) * 0.20
            + max(0.0, row["input_delay_delta"]) * 50_000.0
            + max(0.0, row["cost_delta"]) * 0.08
            + max(0.0, row["loss_delta"]) * 0.06
            + max(0.0, row["external_cost_delta"]) * 0.05
            + max(0.0, row["stock_zero_delta"]) * 1_000.0
        )


def write_csv(rows: list[dict[str, Any]]) -> None:
    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row.keys()})
    priority = [
        "case_id",
        "label",
        "family",
        "severity",
        "impact_score",
        "fill_rate",
        "fill_rate_delta_pp",
        "backlog_days_ex_startup",
        "backlog_max_ex_startup",
        "input_delay_count",
        "input_delay_delta",
        "input_delay_volume",
        "input_delay_volume_delta",
        "total_cost",
        "cost_delta",
        "external_procurement_cost",
        "external_cost_delta",
        "unreliable_loss_qty",
        "loss_delta",
        "risk_applied_rows",
        "state_events_generated",
    ]
    ordered = [field for field in priority if field in fields] + [field for field in fields if field not in priority]
    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ordered)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Any, digits: int = 1) -> str:
    val = to_float(value)
    if abs(val) >= 1_000_000:
        return f"{val/1_000_000:.{digits}f}M"
    if abs(val) >= 1_000:
        return f"{val/1_000:.{digits}f}k"
    return f"{val:.{digits}f}"


def write_report(rows: list[dict[str, Any]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ranked = sorted(rows, key=lambda row: row["impact_score"], reverse=True)
    nominal = next(row for row in rows if row["case_id"] == "baseline_nominal")
    top = [row for row in ranked if row["case_id"] != "baseline_nominal"][:12]
    by_id = {row["case_id"]: row for row in rows}
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["case_id"] != "baseline_nominal":
            by_family[row["family"]].append(row)
    lines = [
        "# Risk amplitude / duration sweep",
        "",
        f"- Cases run: `{len(rows)}`",
        f"- Horizon: `1825` days",
        f"- Input: `{INPUT_JSON.relative_to(ROOT)}`",
        f"- Baseline cost: `{fmt(nominal['total_cost'], 2)}`",
        f"- Baseline input delay volume: `{fmt(nominal['input_delay_volume'], 2)}`",
        "",
        "## Top perturbing cases",
        "",
        "| Rank | Case | Family | Fill rate | Backlog max hors amorcage | Delay volume delta | Cost delta | Loss delta | Supplier appro cost delta | Score |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(top, 1):
        lines.append(
            "| {rank} | `{case}` | {family} | {fill:.4f} | {backlog} | {delay} | {cost} | {loss} | {ext} | {score} |".format(
                rank=idx,
                case=row["case_id"],
                family=row["family"],
                fill=row["fill_rate"],
                backlog=fmt(row["backlog_max_ex_startup"], 1),
                delay=fmt(row["input_delay_volume_delta"], 1),
                cost=fmt(row["cost_delta"], 1),
                loss=fmt(row["loss_delta"], 1),
                ext=fmt(row["external_cost_delta"], 1),
                score=fmt(row["impact_score"], 1),
            )
        )
    lines.extend(["", "## Best case by family", ""])
    lines.append("| Family | Worst case | Main signal | Fill rate | Delay volume delta | Cost delta | Loss delta |")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for family, items in sorted(by_family.items()):
        worst = max(items, key=lambda row: row["impact_score"])
        signals = []
        if worst["backlog_max_ex_startup"] > 0:
            signals.append(f"backlog {fmt(worst['backlog_max_ex_startup'], 1)}")
        if worst["input_delay_volume_delta"] > 0:
            signals.append(f"reports +{fmt(worst['input_delay_volume_delta'], 1)}")
        if worst["cost_delta"] > 0:
            signals.append(f"cout +{fmt(worst['cost_delta'], 1)}")
        if worst["loss_delta"] > 0:
            signals.append(f"pertes +{fmt(worst['loss_delta'], 1)}")
        if not signals:
            signals.append("pas de degradation nette vs nominal")
        lines.append(
            f"| {family} | `{worst['case_id']}` | {'; '.join(signals)} | {worst['fill_rate']:.4f} | {fmt(worst['input_delay_volume_delta'], 1)} | {fmt(worst['cost_delta'], 1)} | {fmt(worst['loss_delta'], 1)} |"
        )

    extreme = by_id.get("pf268967_combined_extreme_180d_no_external")
    severe = by_id.get("pf268967_combined_severe_120d")
    delay14 = by_id.get("pf268967_delay_plus_14_60d")
    delay90 = by_id.get("pf268967_delay_plus_90_60d")
    avail10 = by_id.get("pf268967_availability_10_90d")
    capacity20 = by_id.get("pf268967_capacity_20_90d")
    quality50 = by_id.get("pf268967_quality_yield_50_180d")
    transport45 = by_id.get("dc_customer_pf_delay_plus_45_90d")
    writeoff80 = by_id.get("pf268967_stock_writeoff_80_j0")
    state_only = by_id.get("state_only")

    lines.extend(["", "## Lecture metier", ""])
    if extreme is not None:
        lines.append(
            "- Service client vraiment degrade uniquement dans le cas extreme sans appro fournisseur: "
            f"fill rate {extreme['fill_rate']:.4f}, backlog max {fmt(extreme['backlog_max_ex_startup'], 1)}, "
            f"{fmt(extreme['input_delay_volume_delta'], 1)} de volume reporte et {fmt(extreme['loss_delta'], 1)} de pertes fournisseur."
        )
    if delay14 is not None and delay90 is not None:
        lines.append(
            "- Risque le plus perturbateur hors rupture service: allongement des delais fournisseurs. "
            f"Meme +14 jours cree deja {fmt(delay14['input_delay_volume_delta'], 1)} de volume reporte; "
            f"+90 jours monte a {fmt(delay90['input_delay_volume_delta'], 1)} et environ {fmt(delay90['cost_delta'], 1)} de cout additionnel."
        )
    if severe is not None:
        lines.append(
            "- Les cascades combinees sont plus realistes que les chocs unitaires: le scenario severe garde le service a 100%, "
            f"mais cree {fmt(severe['input_delay_volume_delta'], 1)} de reports, {fmt(severe['loss_delta'], 1)} de pertes "
            f"et {fmt(severe['external_cost_delta'], 1)} de cout d'appro fournisseur supplementaire."
        )
    if quality50 is not None:
        lines.append(
            "- Le risque qualite/rendement est surtout economique: rendement x0.5 ne casse pas le service, "
            f"mais genere {fmt(quality50['loss_delta'], 1)} de pertes et davantage d'appro fournisseur."
        )
    if avail10 is not None:
        lines.append(
            "- L'indisponibilite fournisseur doit etre tres forte pour se voir nettement: disponibilite x0.1 pendant 90 jours "
            f"ajoute {fmt(avail10['input_delay_volume_delta'], 1)} de reports, sans backlog client."
        )
    if capacity20 is not None and writeoff80 is not None:
        lines.append(
            "- Les baisses de capacite et write-off de stock testes seuls sont absorbes: capacite x0.2 et write-off 80% "
            "ne degradent pas le service ni les reports versus nominal. Cela indique un effet tampon important "
            "des stocks, pipelines et approvisionnements fournisseur."
        )
    if transport45 is not None:
        lines.append(
            "- Les retards transport aval sont visibles mais contenus: DC -> client +45 jours cree "
            f"{fmt(transport45['input_delay_volume_delta'], 1)} de reports et {fmt(transport45['cost_delta'], 1)} de cout, "
            "sans backlog durable."
        )
    if state_only is not None:
        lines.append(
            "- Le state-dependent seul declenche des evenements locaux, mais reste absorbe dans cette configuration. "
            "Il est utile comme signal dynamique, pas suffisant seul pour un stress severe."
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The score is a screening score, not a probability. It combines service degradation, backlog, production delay volume, cost delta, supplier loss, supplier replenishment cost, and zero-stock stress.",
            "- If fill rate stays at 1.0, the risk is absorbed by stock, pipeline, replanning, or supplier replenishment. Those cases are still perturbing if they increase delay volume, losses, cost, or stock stress.",
            f"- Full CSV: `{SUMMARY_CSV.relative_to(ROOT)}`",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    cases = build_cases()
    rows: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, 1):
        print(f"[{idx}/{len(cases)}] {case.case_id}", flush=True)
        summary = run_case(case)
        rows.append(extract_case(case, summary))
    add_impacts(rows)
    rows = sorted(rows, key=lambda row: row["impact_score"], reverse=True)
    SUMMARY_JSON.write_text(json.dumps({"cases": rows}, indent=2), encoding="utf-8")
    write_csv(rows)
    write_report(rows)
    print(f"[OK] Summary CSV: {SUMMARY_CSV}")
    print(f"[OK] Report: {REPORT_MD}")


if __name__ == "__main__":
    main()
