#!/usr/bin/env python3
"""Build an offline incident-to-lot explorer from the paired cascade evidence.

The view keeps two questions separate:

* physical exposure: which simulated lots contain material carried by an
  incident-affected shipment;
* counterfactual effect: how the production position of a lot changes between
  the paired normal, untreated-incident and expedited-transport runs.

No historical page or simulation output is modified.  The generated files are
small derivatives of the detailed seed-330281 registries and of the ten-seed
executive summary.
"""

from __future__ import annotations

import csv
import html
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "etudecas.incident_lot_explorer.v1"
HTML_OUTPUT_NAME = "incidents_risques_lots.html"
JSON_OUTPUT_NAME = "incidents_risques_lots.json"


@dataclass(frozen=True)
class CascadeSpec:
    cascade_id: str
    registry_dir_name: str
    title: str
    short_title: str
    incident_kind: str
    route: tuple[str, ...]
    target_item_id: str
    target_node_id: str
    brief_key: str


CASCADE_SPECS: tuple[CascadeSpec, ...] = (
    CascadeSpec(
        cascade_id="quality_quarantine_021081_to_268967",
        registry_dir_name="industrial_registry_quality_seed330281_20260828_v2_units",
        title="Retenue qualité sur la chaîne 021081 → 773474 → 268967",
        short_title="Retenue qualité 021081",
        incident_kind="Délai de libération qualité sur les nouvelles réceptions",
        route=(
            "3 fournisseurs de 021081",
            "SDC-1450",
            "PFI 773474",
            "M-1430",
            "Produit 268967",
            "DC-1920",
            "Client",
        ),
        target_item_id="item:268967",
        target_node_id="M-1430",
        brief_key="quality",
    ),
    CascadeSpec(
        cascade_id="lead_time_delay_338929_to_268091",
        registry_dir_name="industrial_registry_delay_seed330281_20260828_v2_units",
        title="Retard du composant 338929 vers M-1810 et le produit 268091",
        short_title="Retard du composant 338929",
        incident_kind="Ajout de 35 jours sur les nouvelles expéditions fournisseur",
        route=(
            "Fournisseur SDC-VD0914360C",
            "Composant 338929",
            "Usine M-1810",
            "Produit 268091",
            "DC-1920",
            "Client",
        ),
        target_item_id="item:268091",
        target_node_id="M-1810",
        brief_key="delay",
    ),
)


REGISTRY_FILES = {
    "incidents": "risk_impact_incidents.csv",
    "bundles": "risk_impact_exposure_bundles.csv",
    "entities": "risk_impact_entities.csv",
    "edges": "risk_impact_edges.csv",
    "clients": "risk_impact_client_service.csv",
}


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


def _clean_item(value: str) -> str:
    return value.removeprefix("item:")


def _select(row: dict[str, str], fields: Iterable[str]) -> dict[str, Any]:
    numeric_fields = {
        "day",
        "trigger_day",
        "start_day",
        "end_day",
        "risk_decision_day",
        "shipment_day",
        "arrival_day",
        "event_count",
        "lead_days",
        "pulled_qty",
        "shipped_qty",
        "unreliable_loss_qty",
        "attributed_qty_lower",
        "attributed_qty_upper",
        "entity_total_qty",
        "attributed_share_lower",
        "attributed_share_upper",
        "source_qty_lower",
        "source_qty_upper",
        "target_qty_lower",
        "target_qty_upper",
        "served_qty_actual",
        "served_exposed_qty_lower",
        "served_exposed_qty_upper",
        "demand_qty_actual",
        "backlog_end_qty_actual",
        "quality_delay_days",
        "lead_time_extra_days",
        "exposure_bundle_count",
        "exposed_lot_count",
        "exposed_finished_lot_count",
    }
    result: dict[str, Any] = {}
    for field in fields:
        value: Any = row.get(field, "")
        if field in numeric_fields:
            value = _number(value)
        result[field] = value
    return result


def _load_registry(registry_dir: Path) -> dict[str, list[dict[str, Any]]]:
    field_map = {
        "incidents": (
            "incident_id",
            "start_day",
            "end_day",
            "supplier_id",
            "dst_node_id",
            "item_id",
            "risk_type",
            "causality_level",
            "exposure_bundle_count",
            "exposed_lot_count",
            "exposed_finished_lot_count",
            "exposed_client_ids",
            "exposed_shipment_qty_by_uom_json",
            "notes",
        ),
        "bundles": (
            "exposure_bundle_id",
            "shipment_id",
            "risk_decision_day",
            "shipment_day",
            "arrival_day",
            "supplier_id",
            "dst_node_id",
            "item_id",
            "event_ids",
            "shipped_qty",
            "uom",
            "lead_days",
            "quality_delay_days",
            "lead_time_extra_days",
            "causality_level",
        ),
        "entities": (
            "incident_id",
            "exposure_bundle_id",
            "entity_type",
            "entity_id",
            "lot_id",
            "node_id",
            "item_id",
            "day",
            "attributed_qty_lower",
            "attributed_qty_upper",
            "entity_total_qty",
            "attributed_share_lower",
            "attributed_share_upper",
            "uom",
            "causality_level",
            "pre_horizon_origin",
        ),
        "edges": (
            "incident_id",
            "exposure_bundle_id",
            "day",
            "link_type",
            "source_lot_id",
            "target_lot_id",
            "source_node_id",
            "source_item_id",
            "target_node_id",
            "target_item_id",
            "source_qty_lower",
            "source_qty_upper",
            "source_uom",
            "target_qty_lower",
            "target_qty_upper",
            "target_uom",
            "shipment_id",
            "production_campaign_id",
            "causality_level",
        ),
        "clients": (
            "incident_id",
            "client_service_event_id",
            "client_lot_id",
            "day",
            "client_node_id",
            "item_id",
            "served_qty_actual",
            "served_exposed_qty_lower",
            "served_exposed_qty_upper",
            "uom",
            "demand_qty_actual",
            "backlog_end_qty_actual",
            "causality_level",
            "service_impact_claim",
        ),
    }
    return {
        key: [_select(row, field_map[key]) for row in _rows(registry_dir / filename)]
        for key, filename in REGISTRY_FILES.items()
    }


def _campaign_status_by_lot(data_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _rows(data_dir / "production_campaigns.csv"):
        lot_ids = [
            value.strip()
            for value in re.split(r"[;|]", row.get("completed_lot_ids", ""))
            if value.strip()
        ]
        for lot_id in lot_ids:
            result[lot_id] = {
                "operational_status": row.get("status", ""),
                "operational_status_label": row.get("status_label", ""),
                "delay_day_count": _integer(row.get("delay_day_count")),
                "first_delay_day": _integer(row.get("first_delay_day")),
                "last_delay_day": _integer(row.get("last_delay_day")),
                "blocked_lot_qty": _number(row.get("blocked_lot_qty")),
                "binding_input_item_ids": row.get("binding_input_item_ids", ""),
            }
    return result


def _production_sequence(data_dir: Path, spec: CascadeSpec) -> list[dict[str, Any]]:
    path = data_dir / "production_lot_events.csv"
    campaign_by_lot = _campaign_status_by_lot(data_dir)
    selected: list[dict[str, Any]] = []
    for row in _rows(path):
        if (
            row.get("event_type") != "production_output"
            or row.get("item_id") != spec.target_item_id
            or row.get("node_id") != spec.target_node_id
        ):
            continue
        lot_id = row.get("lot_id", "")
        selected.append(
            {
                "lot_id": lot_id,
                "day": _integer(row.get("day")),
                "qty": _number(row.get("qty")),
                "uom": row.get("uom", ""),
                "campaign_id": row.get("production_campaign_id", ""),
                "event_id": row.get("event_id", ""),
                **campaign_by_lot.get(lot_id, {}),
            }
        )
    selected.sort(
        key=lambda row: (
            row["day"] if row["day"] is not None else 10**9,
            row["campaign_id"],
            row["event_id"],
        )
    )
    for position, row in enumerate(selected, start=1):
        row["production_position"] = position
    return selected


def pair_finished_lots(
    entity_rows: list[dict[str, Any]],
    *,
    target_item_id: str,
    normal_sequence: list[dict[str, Any]],
    incident_sequence: list[dict[str, Any]],
    action_sequence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pair simulated product lots by their production position.

    Lot identifiers are generated inside each run and are not stable after the
    first divergent event.  The paired position is therefore explicit and is
    never presented as a shared physical identifier.
    """

    entity_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entity_rows:
        if row.get("entity_type") != "finished_product_lot":
            continue
        if row.get("item_id") != target_item_id or not row.get("lot_id"):
            continue
        entity_groups[str(row["lot_id"])].append(row)

    incident_index = {
        str(row["lot_id"]): (position, row)
        for position, row in enumerate(incident_sequence)
        if row.get("lot_id")
    }
    result: list[dict[str, Any]] = []
    for lot_id, rows in entity_groups.items():
        paired = incident_index.get(lot_id)
        if paired is None:
            position = None
            incident = {
                "lot_id": lot_id,
                "day": _integer(rows[0].get("day")),
                "qty": _number(rows[0].get("entity_total_qty")),
                "uom": rows[0].get("uom", ""),
                "campaign_id": "",
            }
        else:
            position, incident = paired
        normal = normal_sequence[position] if position is not None and position < len(normal_sequence) else None
        action = action_sequence[position] if position is not None and position < len(action_sequence) else None
        incident_day = _integer(incident.get("day"))
        normal_day = _integer(normal.get("day")) if normal else None
        action_day = _integer(action.get("day")) if action else None
        delay_vs_normal = (
            incident_day - normal_day
            if incident_day is not None and normal_day is not None
            else None
        )
        days_recovered = (
            incident_day - action_day
            if incident_day is not None and action_day is not None
            else None
        )
        if delay_vs_normal is None:
            status = "non_apparie"
        elif delay_vs_normal > 0:
            status = "retarde"
        elif delay_vs_normal < 0:
            status = "avance_ou_reordonne"
        else:
            status = "meme_jour"

        by_incident: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_incident[str(row.get("incident_id") or "incident")].append(row)
        lower_candidates = [
            max((_number(row.get("attributed_qty_lower")) or 0.0) for row in group)
            for group in by_incident.values()
        ]
        upper_candidates = [
            max((_number(row.get("attributed_qty_upper")) or 0.0) for row in group)
            for group in by_incident.values()
        ]
        entity_total = max(
            (_number(row.get("entity_total_qty")) or 0.0 for row in rows),
            default=0.0,
        )
        exposure_lower = max(lower_candidates, default=0.0)
        exposure_upper = min(entity_total, sum(upper_candidates))
        result.append(
            {
                "lot_id": lot_id,
                "production_position": None if position is None else position + 1,
                "incident_day": incident_day,
                "normal_day": normal_day,
                "action_day": action_day,
                "delay_vs_normal_days": delay_vs_normal,
                "days_recovered_by_action": days_recovered,
                "status": status,
                "incident_qty": _number(incident.get("qty")),
                "uom": incident.get("uom") or rows[0].get("uom", ""),
                "campaign_id": incident.get("campaign_id", ""),
                "operational_status": incident.get("operational_status", ""),
                "operational_status_label": incident.get(
                    "operational_status_label", ""
                ),
                "constrained_before_release": incident.get("operational_status")
                == "completed_after_delay",
                "delay_day_count": incident.get("delay_day_count"),
                "first_delay_day": incident.get("first_delay_day"),
                "last_delay_day": incident.get("last_delay_day"),
                "blocked_lot_qty": incident.get("blocked_lot_qty"),
                "binding_input_item_ids": incident.get(
                    "binding_input_item_ids", ""
                ),
                "normal_counterpart_lot_id": normal.get("lot_id", "") if normal else "",
                "action_counterpart_lot_id": action.get("lot_id", "") if action else "",
                "exposure_qty_lower": exposure_lower,
                "exposure_qty_upper": exposure_upper,
                "entity_total_qty": entity_total,
                "exposure_share_lower": exposure_lower / entity_total if entity_total else None,
                "exposure_share_upper": exposure_upper / entity_total if entity_total else None,
                "incident_ids": sorted(by_incident),
            }
        )
    result.sort(
        key=lambda row: (
            row["incident_day"] if row["incident_day"] is not None else 10**9,
            row["production_position"] or 10**9,
            row["lot_id"],
        )
    )
    return result


def _run_metrics(campaign_rows: list[dict[str, str]], cascade_id: str) -> dict[str, Any]:
    wanted = {"normal", "incident_no_action", "incident_expedited_transport"}
    selected: dict[str, Any] = {}
    for row in campaign_rows:
        if row.get("cascade_id") != cascade_id or row.get("variant_id") not in wanted:
            continue
        selected[str(row["variant_id"])] = {
            "customer_shortage_days": _number(row.get("customer_shortage_days")),
            "customer_backlog_qty_days": _number(row.get("customer_backlog_qty_days")),
            "production_qty": _number(row.get("production_qty")),
            "production_lot_count": _number(row.get("production_lot_count")),
            "blocked_lot_qty": _number(row.get("blocked_lot_qty")),
            "decision_total_cost": _number(row.get("decision_total_cost")),
            "incident_validation_status": row.get("incident_validation_status", ""),
            "pairing_status": row.get("pairing_status", ""),
        }
    return selected


def _counts(registry: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    lot_ids_by_type: dict[str, set[str]] = defaultdict(set)
    for row in registry["entities"]:
        lot_id = str(row.get("lot_id") or "")
        if lot_id:
            lot_ids_by_type[str(row.get("entity_type") or "autre")].add(lot_id)
    return {
        "incident_count": len(registry["incidents"]),
        "exposure_bundle_count": len(
            {row.get("exposure_bundle_id") for row in registry["bundles"]}
        ),
        "entity_row_count": len(registry["entities"]),
        "edge_row_count": len(registry["edges"]),
        "client_event_row_count": len(registry["clients"]),
        "unique_lot_count": len(
            {
                row.get("lot_id")
                for row in registry["entities"]
                if row.get("lot_id")
            }
        ),
        "unique_lots_by_type": {
            entity_type: len(lot_ids)
            for entity_type, lot_ids in sorted(lot_ids_by_type.items())
        },
    }


def build_incident_lot_payload(artifact_root: Path) -> dict[str, Any]:
    artifact_root = artifact_root.resolve()
    trace_root = artifact_root / "industrial_cascade_full_trace_seed330281_20260828_v1"
    campaign_rows = _rows(trace_root / "canonical_cascade_runs.csv")
    brief_results_path = (
        artifact_root / "industrial_demo_executive_light_20260829_v9" / "brief_results.json"
    )
    brief_results = json.loads(brief_results_path.read_text(encoding="utf-8"))
    scenarios: list[dict[str, Any]] = []
    for spec in CASCADE_SPECS:
        registry_dir = artifact_root / spec.registry_dir_name
        registry = _load_registry(registry_dir)
        run_root = trace_root / "runs" / spec.cascade_id
        sequences = {
            variant: _production_sequence(
                run_root / variant / "seed_330281" / "data", spec
            )
            for variant in (
                "normal",
                "incident_no_action",
                "incident_expedited_transport",
            )
        }
        finished_lots = pair_finished_lots(
            registry["entities"],
            target_item_id=spec.target_item_id,
            normal_sequence=sequences["normal"],
            incident_sequence=sequences["incident_no_action"],
            action_sequence=sequences["incident_expedited_transport"],
        )
        status_counts = Counter(row["status"] for row in finished_lots)
        constrained_count = sum(
            bool(row["constrained_before_release"]) for row in finished_lots
        )
        scenarios.append(
            {
                "id": spec.cascade_id,
                "title": spec.title,
                "short_title": spec.short_title,
                "incident_kind": spec.incident_kind,
                "route": list(spec.route),
                "target_item_id": spec.target_item_id,
                "target_node_id": spec.target_node_id,
                "seed": 330281,
                "horizon_days": 720,
                "aggregate_ten_repetitions": brief_results.get(spec.brief_key, {}),
                "run_metrics": _run_metrics(campaign_rows, spec.cascade_id),
                "counts": {
                    **_counts(registry),
                    "exposed_finished_lot_count": len(finished_lots),
                    "constrained_finished_lot_count": constrained_count,
                    "finished_lot_status_counts": dict(status_counts),
                },
                "finished_lots": finished_lots,
                **registry,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "language": "fr",
        "scope": {
            "detailed_seed": 330281,
            "detailed_variants": [
                "normal",
                "incident_no_action",
                "incident_expedited_transport",
            ],
            "aggregate_repetitions": 10,
            "historical_incidents": False,
            "real_lot_identifiers": False,
            "incident_occurrence_probability_estimated": False,
            "closed_loop_regulation_active": False,
        },
        "definitions": {
            "exposed": (
                "Le flux touché par l'incident entre dans la généalogie physique du lot. "
                "Cela ne suffit pas à prouver un retard causé."
            ),
            "counterfactual_position_shift": (
                "Estimation de l'écart de jour de production entre le rang du lot dans le "
                "run incident et le même rang dans le run normal apparié. Ce n'est pas "
                "l'identité certifiée du même lot physique."
            ),
            "paired_position": (
                "Les identifiants de lots étant recréés dans chaque simulation, les runs sont "
                "comparés par rang de production du même produit, avec la même graine."
            ),
            "customer_exposure": (
                "Matière exposée servie dans un lot client; la dégradation de service est "
                "mesurée séparément par la comparaison avec le run normal."
            ),
        },
        "sources": {
            "full_trace": str(trace_root),
            "brief_results": str(brief_results_path),
            "quality_registry": str(
                artifact_root
                / "industrial_registry_quality_seed330281_20260828_v2_units"
            ),
            "delay_registry": str(
                artifact_root
                / "industrial_registry_delay_seed330281_20260828_v2_units"
            ),
        },
        "scenarios": scenarios,
    }


def _safe_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def render_incident_lot_html(
    payload: dict[str, Any],
    *,
    return_href: str = "../index.html#lots",
    map_href: str = "carte_reseau_lots.html",
    stress_href: str = "stress_tests_incidents_lots.html",
) -> str:
    data = _safe_json(payload)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Incidents, cascades et effets sur les lots</title>
<style>
:root{{--ink:#0b1f3a;--muted:#5b6b7f;--line:#dbe4ee;--bg:#eef3f8;--panel:#fff;--blue:#1d4ed8;--teal:#0f766e;--red:#dc2626;--amber:#d97706;--green:#15803d}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,Segoe UI,Arial,sans-serif;line-height:1.45}}button,input,select{{font:inherit}}a{{color:inherit}}
.top{{background:linear-gradient(130deg,#071f3a,#123d6b 62%,#0f766e);color:#fff;padding:24px 28px 20px;position:sticky;top:0;z-index:20;box-shadow:0 8px 25px #0f172a33}}.topline{{display:flex;align-items:center;gap:18px;flex-wrap:wrap}}h1{{font-size:clamp(1.45rem,3vw,2.25rem);margin:0;flex:1}}.scope{{color:#dbeafe;font-size:.88rem}}.links{{display:flex;gap:8px;flex-wrap:wrap}}.links a,.pillbtn{{text-decoration:none;border:1px solid #ffffff55;background:#ffffff16;color:#fff;padding:8px 12px;border-radius:999px;font-weight:750;cursor:pointer}}.links a.primary{{background:#fff;color:#123d6b}}
.toolbar{{display:grid;grid-template-columns:minmax(280px,2fr) repeat(3,minmax(165px,1fr));gap:12px;margin-top:18px}}label{{font-size:.78rem;font-weight:800;color:#dbeafe}}select,input{{width:100%;margin-top:4px;padding:10px 11px;border:1px solid #b9c8d8;border-radius:10px;background:#fff;color:#102a45}}input[type=range]{{padding:8px 0;border:0;background:transparent}}#dayValue{{display:block;text-align:right;color:#fff;font-size:.73rem}}.wrap{{max-width:1500px;margin:auto;padding:22px}}
.notice{{background:#eff6ff;border-left:5px solid var(--blue);padding:13px 16px;border-radius:10px;margin-bottom:16px}}.warning{{background:#fffbeb;border-left:5px solid var(--amber);padding:12px 15px;border-radius:10px;margin:14px 0}}.grid{{display:grid;gap:14px}}.kpis{{grid-template-columns:repeat(auto-fit,minmax(175px,1fr))}}.card,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:16px;box-shadow:0 8px 25px #0f172a0b}}.card{{padding:16px}}.kpi{{font-size:1.7rem;font-weight:850;line-height:1.05}}.card p{{margin:7px 0 0;color:var(--muted);font-size:.86rem}}.panel{{padding:18px;margin-top:16px}}h2{{font-size:1.25rem;margin:0 0 10px}}h3{{font-size:1rem;margin:14px 0 7px}}.muted{{color:var(--muted)}}
.route{{display:flex;align-items:stretch;gap:7px;overflow:auto;padding:10px 2px}}.stage{{min-width:150px;padding:12px;border:1px solid #bfdbfe;background:#eff6ff;border-radius:12px;text-align:center;font-weight:750;font-size:.84rem}}.arrow{{align-self:center;color:#64748b;font-size:1.4rem}}.timeline{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px}}.time{{padding:11px;border:1px solid var(--line);border-radius:11px;text-align:center;background:#f8fafc}}.time b{{display:block;font-size:1.16rem}}
.tabs{{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 0;position:sticky;top:148px;z-index:10;background:var(--bg);padding:9px 0}}.tab{{border:1px solid #b9c8d8;background:#fff;padding:9px 13px;border-radius:999px;font-weight:800;cursor:pointer;color:#29445f}}.tab.active{{background:#0b1f3a;color:#fff;border-color:#0b1f3a}}.view{{display:none}}.view.active{{display:block}}
.filters{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px;margin:12px 0}}.tablewrap{{overflow:auto;border:1px solid var(--line);border-radius:12px;max-height:590px}}table{{width:100%;border-collapse:collapse;font-size:.81rem}}th,td{{padding:9px 8px;border-bottom:1px solid #e5edf5;text-align:left;vertical-align:top;white-space:nowrap}}th{{position:sticky;top:0;background:#f1f5f9;z-index:2;color:#36516d}}tbody tr{{cursor:pointer}}tbody tr:hover{{background:#eff6ff}}.status{{display:inline-block;padding:3px 7px;border-radius:999px;font-size:.72rem;font-weight:850}}.retarde{{background:#fee2e2;color:#991b1b}}.meme_jour{{background:#dcfce7;color:#166534}}.avance_ou_reordonne{{background:#fef3c7;color:#92400e}}.non_apparie{{background:#e2e8f0;color:#475569}}.pager{{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:9px}}.pager button{{border:1px solid #b9c8d8;background:#fff;padding:7px 11px;border-radius:9px;cursor:pointer}}
.detail{{display:none;border:2px solid #93c5fd;background:#fff;margin-top:14px;border-radius:15px;padding:16px}}.detail.open{{display:block}}.detailhead{{display:flex;align-items:start;gap:12px}}.detailhead>div:first-child{{flex:1}}.close{{border:0;background:#e2e8f0;border-radius:999px;padding:7px 11px;cursor:pointer}}.detailgrid{{grid-template-columns:repeat(auto-fit,minmax(170px,1fr));margin:12px 0}}.fact{{padding:11px;background:#f8fafc;border:1px solid var(--line);border-radius:10px}}.fact small{{display:block;color:var(--muted)}}.lineage{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.lineage-list{{max-height:330px;overflow:auto;border:1px solid var(--line);border-radius:10px;padding:8px}}.lineage-row{{padding:8px;border-bottom:1px solid #e5edf5;font-size:.79rem}}.lineage-row:last-child{{border-bottom:0}}
.two{{grid-template-columns:1fr 1fr}}.action{{padding:14px;border:1px solid var(--line);border-radius:12px;background:#f8fafc}}.action.good{{background:#f0fdf4;border-color:#86efac}}.raw-note{{font-size:.78rem;color:var(--muted)}}.badge{{display:inline-block;padding:4px 8px;border-radius:999px;background:#dbeafe;color:#1e40af;font-size:.72rem;font-weight:850;margin-right:5px}}.empty{{padding:24px;text-align:center;color:var(--muted)}}
@media(max-width:900px){{.top{{position:static}}.toolbar,.filters,.two,.lineage{{grid-template-columns:1fr}}.tabs{{top:0}}.timeline{{grid-template-columns:1fr 1fr}}.wrap{{padding:12px}}}}
</style></head><body>
<header class="top"><div class="topline"><h1>Incidents, cascades et effets sur les lots</h1><div class="links"><a class="primary" href="{html.escape(return_href, quote=True)}">Retour à la synthèse</a><a href="{html.escape(map_href, quote=True)}">Carte globale</a><a href="{html.escape(stress_href, quote=True)}">Courbes des stress tests</a></div></div>
<div class="scope">Vue alignée : mêmes cascades que les résultats industriels, détail seed 330281, synthèse sur dix répétitions.</div>
<div class="toolbar"><label>Incident ou cascade<select id="scenarioSelect"></select></label><label>Lot à retrouver<input id="globalSearch" placeholder="LOT-…, article, site, client"></label><label>Lecture<select id="readingSelect"><option value="all">Tout afficher</option><option value="constrained">Contrainte avant libération</option><option value="retarde">Rang produit plus tard</option><option value="meme_jour">Même rang, même jour</option><option value="avance_ou_reordonne">Avancés ou réordonnés</option></select></label><label>Avancement de la cascade<input id="dayRange" type="range" min="0" max="719" value="719"><span id="dayValue">Tout l'horizon · J719</span></label></div></header>
<main class="wrap"><div class="notice"><strong>Ce que montre cette page :</strong> le chemin physique complet de l'incident jusqu'aux lots et au client, puis l'écart avec le fonctionnement normal apparié. Les identifiants sont des lots simulés, pas les lots WMS 2025.</div>
<section id="summary"></section>
<nav class="tabs"><button class="tab active" data-view="lots">Lots finis : exposition et contraintes</button><button class="tab" data-view="genealogy">Toute la généalogie</button><button class="tab" data-view="flows">Flux et événements</button><button class="tab" data-view="clients">Clients et solutions</button></nav>
<section id="view-lots" class="view active"></section><section id="view-genealogy" class="view"></section><section id="view-flows" class="view"></section><section id="view-clients" class="view"></section>
</main><script id="payload" type="application/json">{data}</script><script>
const DATA=JSON.parse(document.getElementById('payload').textContent);let scenario=DATA.scenarios[0];
const state={{lotsPage:1,entitiesPage:1,edgesPage:1,bundlesPage:1,clientsPage:1,selectedLot:null}};const PAGE=60;
const fmt=(v,d=0)=>v===null||v===undefined||v===''?'—':Number(v).toLocaleString('fr-FR',{{maximumFractionDigits:d,minimumFractionDigits:d}});
const pct=v=>v===null||v===undefined?'—':fmt(100*Number(v),1)+' %';const day=v=>v===null||v===undefined?'—':'J'+fmt(v,0);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const typeLabel=t=>({{supplier_source_lot:'Lot source fournisseur',physical_lot:'Lot physique',plant_material_lot:'Lot matière usine',production_campaign:'Campagne de production',finished_product_lot:'Lot de produit fini',distribution_receipt_lot:'Lot au centre de distribution',customer_receipt_lot:'Lot alloué au client'}}[t]||t);
const statusLabel=s=>({{retarde:'Retardé dans le run incident',meme_jour:'Même rang, même jour',avance_ou_reordonne:'Avancé ou réordonné',non_apparie:'Non apparié'}}[s]||s);
function selectedScenario(){{return DATA.scenarios.find(s=>s.id===document.getElementById('scenarioSelect').value)||DATA.scenarios[0]}}
function routeHtml(){{return scenario.route.map((r,i)=>`<div class="stage">${{esc(r)}}</div>${{i<scenario.route.length-1?'<div class="arrow">→</div>':''}}`).join('')}}
function renderSummary(){{const a=scenario.aggregate_ten_repetitions||{{}},t=a.conditional_impact_timeline||{{}},c=scenario.counts,rm=scenario.run_metrics.incident_no_action||{{}};document.getElementById('summary').innerHTML=`
<div class="panel"><h2>${{esc(scenario.title)}}</h2><p class="muted">${{esc(scenario.incident_kind)}}. Ce sont des scénarios démonstratifs, pas des incidents historiques sélectionnés par une probabilité prédite.</p><div class="route">${{routeHtml()}}</div><div class="timeline"><div class="time"><span>Début incident</span><b>${{day(t.incident_start_day)}}</b></div><div class="time"><span>Premier effet stock</span><b>${{day(t.first_stock_effect_day)}}</b></div><div class="time"><span>Production</span><b>${{day(t.first_production_effect_day)}}</b></div><div class="time"><span>Client</span><b>${{day(t.first_customer_backlog_day)}}</b></div></div></div>
<div class="grid kpis" style="margin-top:14px"><div class="card"><div class="kpi">${{fmt(c.exposed_finished_lot_count)}}</div><p>lots finis contenant un flux exposé</p></div><div class="card"><div class="kpi">${{fmt(c.constrained_finished_lot_count)}}</div><p>lots exposés libérés après une contrainte observée dans ce run</p></div><div class="card"><div class="kpi">${{fmt(c.unique_lot_count)}}</div><p>lots uniques visibles dans toute la généalogie</p></div><div class="card"><div class="kpi">${{fmt(c.exposure_bundle_count)}}</div><p>expéditions fournisseur touchées, comptées une fois</p></div><div class="card"><div class="kpi">${{fmt(rm.customer_shortage_days)}}</div><p>jours avec retard client dans le cas détaillé sans action</p></div><div class="card"><div class="kpi">${{a.customer_delay_count??'—'}} / ${{a.simulation_count??'—'}}</div><p>répétitions où l'incident atteint le client</p></div></div>`}}
function filters(){{return {{q:(document.getElementById('globalSearch').value||'').toLowerCase(),status:document.getElementById('readingSelect').value,maxDay:Number(document.getElementById('dayRange').value)}}}}
function filteredLots(){{const f=filters();return scenario.finished_lots.filter(r=>(r.incident_day===null||r.incident_day<=f.maxDay)&&(f.status==='all'||(f.status==='constrained'?r.constrained_before_release:r.status===f.status))&&(!f.q||JSON.stringify(r).toLowerCase().includes(f.q)))}}
function pager(kind,total,page){{const pages=Math.max(1,Math.ceil(total/PAGE));return `<div class="pager"><button data-page-kind="${{kind}}" data-page="${{Math.max(1,page-1)}}" ${{page<=1?'disabled':''}}>← Précédent</button><span>${{fmt(total)}} lignes · page ${{page}} / ${{pages}}</span><button data-page-kind="${{kind}}" data-page="${{Math.min(pages,page+1)}}" ${{page>=pages?'disabled':''}}>Suivant →</button></div>`}}
function renderLots(){{const rows=filteredLots(),page=Math.min(state.lotsPage,Math.max(1,Math.ceil(rows.length/PAGE)));state.lotsPage=page;const slice=rows.slice((page-1)*PAGE,page*PAGE);document.getElementById('view-lots').innerHTML=`<div class="panel"><h2>Lots finis reliés à l'incident</h2><p class="muted">Chaque ligne sépare l'exposition physique, la contrainte observée avant libération et l'écart estimé entre futurs alternatifs. Cliquez sur un lot pour voir ses ascendants, ses descendants et les événements client.</p><div class="warning"><strong>Lecture correcte :</strong> « exposé » décrit la généalogie. « libéré après contrainte » est observé dans le run incident mais n'en prouve pas seul la cause. L'écart normal / incident est une estimation par rang de production, car les identifiants sont recréés dans chaque run.</div><div class="tablewrap"><table><thead><tr><th>Lot incident</th><th>Article</th><th>Libération dans le run</th><th>Produit J</th><th>Normal J estimé</th><th>Écart de rang</th><th>Action J estimé</th><th>Jours récupérés estimés</th><th>Part exposée</th></tr></thead><tbody>${{slice.map(r=>`<tr data-lot="${{esc(r.lot_id)}}"><td><strong>${{esc(r.lot_id)}}</strong><br><small>rang ${{fmt(r.production_position)}}</small></td><td>${{esc(scenario.target_item_id.replace('item:',''))}}</td><td>${{r.constrained_before_release?'<span class="status retarde">Libéré après contrainte</span>':'<span class="status meme_jour">Sans contrainte avant libération</span>'}}${{r.binding_input_item_ids?`<br><small>intrant : ${{esc(r.binding_input_item_ids.replaceAll('item:',''))}}</small>`:''}}</td><td>${{day(r.incident_day)}}</td><td>${{day(r.normal_day)}}</td><td><span class="status ${{esc(r.status)}}">${{r.delay_vs_normal_days===null?'—':(r.delay_vs_normal_days>0?'+':'')+fmt(r.delay_vs_normal_days)+' j'}}</span></td><td>${{day(r.action_day)}}</td><td>${{r.days_recovered_by_action===null?'—':fmt(r.days_recovered_by_action)+' j'}}</td><td>${{pct(r.exposure_share_lower)}} – ${{pct(r.exposure_share_upper)}}</td></tr>`).join('')}}</tbody></table></div>${{pager('lots',rows.length,page)}}<div id="lotDetail" class="detail"></div></div>`;bindRows()}}
function graphForLot(lotId){{const incoming=new Map(),outgoing=new Map();scenario.edges.forEach(e=>{{if(e.source_lot_id&&e.target_lot_id){{if(!outgoing.has(e.source_lot_id))outgoing.set(e.source_lot_id,[]);outgoing.get(e.source_lot_id).push(e);if(!incoming.has(e.target_lot_id))incoming.set(e.target_lot_id,[]);incoming.get(e.target_lot_id).push(e)}}}});const lots=new Set([lotId]),chosen=[];let frontier=[lotId];for(let depth=0;depth<4;depth++){{const next=[];frontier.forEach(id=>(incoming.get(id)||[]).forEach(e=>{{chosen.push(e);if(e.source_lot_id&&!lots.has(e.source_lot_id)){{lots.add(e.source_lot_id);next.push(e.source_lot_id)}}}}));frontier=next}}frontier=[lotId];for(let depth=0;depth<5;depth++){{const next=[];frontier.forEach(id=>(outgoing.get(id)||[]).forEach(e=>{{chosen.push(e);if(e.target_lot_id&&!lots.has(e.target_lot_id)){{lots.add(e.target_lot_id);next.push(e.target_lot_id)}}}}));frontier=next}}return {{lots,edges:[...new Map(chosen.map(e=>[JSON.stringify(e),e])).values()]}}}}
function showLot(lotId){{const lot=scenario.finished_lots.find(r=>r.lot_id===lotId);if(!lot)return;state.selectedLot=lotId;const g=graphForLot(lotId);const entities=scenario.entities.filter(e=>g.lots.has(e.lot_id)).sort((a,b)=>(a.day??9999)-(b.day??9999));const clients=scenario.clients.filter(c=>g.lots.has(c.client_lot_id));const detail=document.getElementById('lotDetail');detail.classList.add('open');detail.innerHTML=`<div class="detailhead"><div><span class="badge">Lot simulé</span><h2 style="margin-top:7px">${{esc(lot.lot_id)}} · produit ${{esc(scenario.target_item_id.replace('item:',''))}}</h2><p class="muted">Rang de production ${{fmt(lot.production_position)}} dans le cas incident. Les jours normal et action sont des appariements estimés par rang, pas l'identité d'un même lot persistant.</p></div><button class="close" id="closeDetail">Fermer</button></div><div class="grid detailgrid"><div class="fact"><small>Libération dans le run incident</small><strong>${{esc(lot.operational_status_label||lot.operational_status||'—')}}</strong></div><div class="fact"><small>Jours de contrainte observés</small><strong>${{fmt(lot.delay_day_count)}}</strong></div><div class="fact"><small>Jour normal estimé</small><strong>${{day(lot.normal_day)}}</strong></div><div class="fact"><small>Jour avec incident</small><strong>${{day(lot.incident_day)}}</strong></div><div class="fact"><small>Écart estimé par rang</small><strong>${{lot.delay_vs_normal_days===null?'—':fmt(lot.delay_vs_normal_days)+' jours'}}</strong></div><div class="fact"><small>Avec transport accéléré, estimé</small><strong>${{day(lot.action_day)}}</strong></div><div class="fact"><small>Jours récupérés estimés</small><strong>${{lot.days_recovered_by_action===null?'—':fmt(lot.days_recovered_by_action)}}</strong></div><div class="fact"><small>Matière exposée dans le lot</small><strong>${{fmt(lot.exposure_qty_lower,1)}} – ${{fmt(lot.exposure_qty_upper,1)}} ${{esc(lot.uom)}}</strong></div></div><div class="lineage"><div><h3>Lots et campagnes dans le chemin</h3><div class="lineage-list">${{entities.length?entities.map(e=>`<div class="lineage-row"><b>${{esc(typeLabel(e.entity_type))}}</b> · ${{esc(e.lot_id||e.entity_id||'—')}}<br>${{day(e.day)}} · ${{esc(e.node_id)}} · ${{esc((e.item_id||'').replace('item:',''))}} · exposition ${{fmt(e.attributed_qty_lower,1)}}–${{fmt(e.attributed_qty_upper,1)}} ${{esc(e.uom)}}</div>`).join(''):'<div class="empty">Aucune entité reliée</div>'}}</div></div><div><h3>Flux physiques et service client</h3><div class="lineage-list">${{g.edges.map(e=>`<div class="lineage-row"><b>${{esc(e.link_type)}}</b> · ${{day(e.day)}}<br>${{esc(e.source_lot_id)}} → ${{esc(e.target_lot_id)}}<br>${{esc((e.source_item_id||'').replace('item:',''))}} → ${{esc((e.target_item_id||'').replace('item:',''))}}</div>`).join('')}}${{clients.map(c=>`<div class="lineage-row"><b>Service client</b> · ${{day(c.day)}}<br>lot ${{esc(c.client_lot_id)}} · servi ${{fmt(c.served_qty_actual,1)}} · exposé ${{fmt(c.served_exposed_qty_lower,1)}} ${{esc(c.uom)}} · backlog ${{fmt(c.backlog_end_qty_actual,1)}}</div>`).join('')}}</div></div></div>`;document.getElementById('closeDetail').onclick=()=>detail.classList.remove('open');detail.scrollIntoView({{behavior:'smooth',block:'nearest'}})}}
function entityRows(){{const f=filters();return scenario.entities.filter(r=>(r.day===null||r.day<=f.maxDay)&&(!f.q||JSON.stringify(r).toLowerCase().includes(f.q)))}}
function renderGenealogy(){{const rows=entityRows(),page=Math.min(state.entitiesPage,Math.max(1,Math.ceil(rows.length/PAGE))),slice=rows.slice((page-1)*PAGE,page*PAGE);state.entitiesPage=page;document.getElementById('view-genealogy').innerHTML=`<div class="panel"><h2>Toutes les entités de la cascade</h2><p class="muted">Aucun échantillonnage : lots fournisseur, matière, campagnes, produits finis, distribution et client. La recherche du bandeau filtre cette table.</p><div class="tablewrap"><table><thead><tr><th>Type</th><th>Lot / entité</th><th>Jour</th><th>Site</th><th>Article</th><th>Quantité exposée</th><th>Total entité</th><th>Incident</th></tr></thead><tbody>${{slice.map(e=>`<tr ${{e.lot_id?`data-lot="${{esc(e.lot_id)}}"`:''}}><td>${{esc(typeLabel(e.entity_type))}}</td><td><strong>${{esc(e.lot_id||e.entity_id||'—')}}</strong></td><td>${{day(e.day)}}</td><td>${{esc(e.node_id)}}</td><td>${{esc((e.item_id||'').replace('item:',''))}}</td><td>${{fmt(e.attributed_qty_lower,2)}} – ${{fmt(e.attributed_qty_upper,2)}} ${{esc(e.uom)}}</td><td>${{fmt(e.entity_total_qty,2)}} ${{esc(e.uom)}}</td><td>${{esc(e.incident_id)}}</td></tr>`).join('')}}</tbody></table></div>${{pager('entities',rows.length,page)}}<p class="raw-note">Les lignes de plusieurs incidents qualité peuvent se recouvrir. Les totaux réseau sont calculés par expédition unique, pas par addition des lignes incident.</p></div>`;bindRows()}}
function renderFlows(){{const f=filters(),bundles=scenario.bundles.filter(r=>(r.shipment_day===null||r.shipment_day<=f.maxDay)&&(!f.q||JSON.stringify(r).toLowerCase().includes(f.q))),edges=scenario.edges.filter(r=>(r.day===null||r.day<=f.maxDay)&&(!f.q||JSON.stringify(r).toLowerCase().includes(f.q)));const bp=Math.min(state.bundlesPage,Math.max(1,Math.ceil(bundles.length/PAGE))),ep=Math.min(state.edgesPage,Math.max(1,Math.ceil(edges.length/PAGE)));state.bundlesPage=bp;state.edgesPage=ep;document.getElementById('view-flows').innerHTML=`<div class="grid two"><div class="panel"><h2>Incidents injectés</h2>${{scenario.incidents.map(i=>`<div class="action"><b>${{esc(i.incident_id)}}</b><p>${{esc(i.supplier_id)}} → ${{esc(i.dst_node_id)}} · article ${{esc((i.item_id||'').replace('item:',''))}}</p><p>${{day(i.start_day)}} à ${{day(i.end_day)}} · ${{esc(i.notes)}}</p></div>`).join('')}}</div><div class="panel"><h2>Règle de comptage</h2><p>Une expédition touchée est comptée une seule fois par <em>bundle</em>. Les quantités ne sont jamais additionnées entre unités différentes. Les trois événements qualité ne sont pas additionnés comme trois impacts réseau indépendants.</p></div></div><div class="panel"><h2>Expéditions fournisseur touchées</h2><div class="tablewrap"><table><thead><tr><th>Expédition</th><th>Fournisseur</th><th>Article</th><th>Départ</th><th>Arrivée</th><th>Quantité</th><th>Effet</th></tr></thead><tbody>${{bundles.slice((bp-1)*PAGE,bp*PAGE).map(b=>`<tr><td>${{esc(b.shipment_id)}}</td><td>${{esc(b.supplier_id)}}</td><td>${{esc((b.item_id||'').replace('item:',''))}}</td><td>${{day(b.shipment_day)}}</td><td>${{day(b.arrival_day)}}</td><td>${{fmt(b.shipped_qty,1)}} ${{esc(b.uom)}}</td><td>${{b.quality_delay_days?fmt(b.quality_delay_days)+' j qualité':b.lead_time_extra_days?fmt(b.lead_time_extra_days)+' j transport':'—'}}</td></tr>`).join('')}}</tbody></table></div>${{pager('bundles',bundles.length,bp)}}</div><div class="panel"><h2>Tous les liens de généalogie</h2><div class="tablewrap"><table><thead><tr><th>Jour</th><th>Type</th><th>Lot source</th><th>Lot cible</th><th>Article source</th><th>Article cible</th><th>Quantités</th></tr></thead><tbody>${{edges.slice((ep-1)*PAGE,ep*PAGE).map(e=>`<tr data-lot="${{esc(e.target_lot_id)}}"><td>${{day(e.day)}}</td><td>${{esc(e.link_type)}}</td><td>${{esc(e.source_lot_id)}}</td><td>${{esc(e.target_lot_id)}}</td><td>${{esc((e.source_item_id||'').replace('item:',''))}}</td><td>${{esc((e.target_item_id||'').replace('item:',''))}}</td><td>${{fmt(e.source_qty_lower,2)}}–${{fmt(e.source_qty_upper,2)}} ${{esc(e.source_uom)}} → ${{fmt(e.target_qty_lower,2)}}–${{fmt(e.target_qty_upper,2)}} ${{esc(e.target_uom)}}</td></tr>`).join('')}}</tbody></table></div>${{pager('edges',edges.length,ep)}}</div>`;bindRows()}}
function renderClients(){{const f=filters(),rows=scenario.clients.filter(r=>(r.day===null||r.day<=f.maxDay)&&(!f.q||JSON.stringify(r).toLowerCase().includes(f.q))),page=Math.min(state.clientsPage,Math.max(1,Math.ceil(rows.length/PAGE)));state.clientsPage=page;const a=scenario.aggregate_ten_repetitions||{{}},ex=a.expedited||{{}},co=a.combined||{{}},rp=a.replanning||{{}};document.getElementById('view-clients').innerHTML=`<div class="grid two"><div class="panel"><h2>Effet client sur dix répétitions</h2><div class="grid kpis"><div class="card"><div class="kpi">${{a.customer_delay_count??'—'}} / ${{a.simulation_count??'—'}}</div><p>cas où l'incident atteint le client</p></div><div class="card"><div class="kpi">${{fmt(a.no_action_backlog_qty_days_mean,0)}}</div><p>unités × jours de retard, sans action</p></div></div></div><div class="panel"><h2>Solutions comparées</h2><div class="action good"><b>Transport accéléré</b><p>${{fmt(ex.days_recovered,1)}} jours récupérés en moyenne dans les cas touchés; ${{pct(ex.remaining_ratio)}} du retard reste.</p></div><div class="action"><b>Plan combiné</b><p>${{co.days_recovered!==undefined?fmt(co.days_recovered,1)+' jours récupérés; ':''}}retard restant ${{pct(co.remaining_ratio)}}.</p></div>${{rp.remaining_ratio!==undefined?`<div class="action"><b>Replanification seule</b><p>Retard restant ${{pct(rp.remaining_ratio)}}; elle peut déplacer le problème au lieu de le résoudre.</p></div>`:''}}</div></div><div class="panel"><h2>Toutes les allocations de lots au client</h2><p class="muted">Ces lignes montrent qu'un flux exposé a été servi. Le retard causé est établi par la comparaison globale appariée, pas par cette colonne seule.</p><div class="tablewrap"><table><thead><tr><th>Jour</th><th>Lot client</th><th>Article</th><th>Servi</th><th>Part exposée</th><th>Demande</th><th>Backlog fin de jour</th></tr></thead><tbody>${{rows.slice((page-1)*PAGE,page*PAGE).map(c=>`<tr data-lot="${{esc(c.client_lot_id)}}"><td>${{day(c.day)}}</td><td>${{esc(c.client_lot_id)}}</td><td>${{esc((c.item_id||'').replace('item:',''))}}</td><td>${{fmt(c.served_qty_actual,2)}} ${{esc(c.uom)}}</td><td>${{fmt(c.served_exposed_qty_lower,2)}}–${{fmt(c.served_exposed_qty_upper,2)}} ${{esc(c.uom)}}</td><td>${{fmt(c.demand_qty_actual,2)}}</td><td>${{fmt(c.backlog_end_qty_actual,2)}}</td></tr>`).join('')}}</tbody></table></div>${{pager('clients',rows.length,page)}}</div>`;bindRows()}}
function bindRows(){{document.querySelectorAll('[data-lot]').forEach(el=>el.onclick=()=>{{const id=el.dataset.lot;if(scenario.finished_lots.some(r=>r.lot_id===id))showLot(id)}});document.querySelectorAll('[data-page-kind]').forEach(b=>b.onclick=()=>{{state[b.dataset.pageKind+'Page']=Number(b.dataset.page);renderAllViews()}})}}
function renderAllViews(){{renderSummary();renderLots();renderGenealogy();renderFlows();renderClients()}}
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById('view-'+b.dataset.view).classList.add('active')}});
const select=document.getElementById('scenarioSelect');select.innerHTML=DATA.scenarios.map(s=>`<option value="${{esc(s.id)}}">${{esc(s.short_title)}}</option>`).join('');select.onchange=()=>{{scenario=selectedScenario();Object.keys(state).forEach(k=>{{if(k.endsWith('Page'))state[k]=1}});document.getElementById('dayRange').value=719;document.getElementById('dayValue').textContent="Tout l'horizon · J719";renderAllViews()}};document.getElementById('globalSearch').oninput=()=>{{state.lotsPage=state.entitiesPage=state.edgesPage=state.bundlesPage=state.clientsPage=1;renderAllViews()}};document.getElementById('readingSelect').onchange=()=>{{state.lotsPage=1;renderLots()}};document.getElementById('dayRange').oninput=e=>{{document.getElementById('dayValue').textContent='J0 → J'+e.target.value;state.lotsPage=state.entitiesPage=state.edgesPage=state.bundlesPage=state.clientsPage=1;renderAllViews()}};renderAllViews();
</script></body></html>"""


def write_incident_lot_explorer(
    output_dir: Path,
    artifact_root: Path,
    *,
    payload: dict[str, Any] | None = None,
) -> tuple[list[Path], dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = payload or build_incident_lot_payload(artifact_root)
    json_path = output_dir / JSON_OUTPUT_NAME
    html_path = output_dir / HTML_OUTPUT_NAME
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    html_path.write_text(render_incident_lot_html(payload), encoding="utf-8")
    return [html_path, json_path], payload


__all__ = [
    "HTML_OUTPUT_NAME",
    "JSON_OUTPUT_NAME",
    "build_incident_lot_payload",
    "pair_finished_lots",
    "render_incident_lot_html",
    "write_incident_lot_explorer",
]
