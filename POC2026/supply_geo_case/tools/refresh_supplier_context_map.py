#!/usr/bin/env python3
"""Refresh supplier context in the existing map without rerunning SDD or Brightway."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from POC2026.supply_geo_case.adapter import (
    clean,
    read_csv_rows,
    safe_float,
    supplier_context_payload,
    write_enriched_base_map_html,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs",
    )
    return parser.parse_args()


def embedded_map_payload(path: Path) -> dict | None:
    if not path.exists():
        return None
    document = path.read_text(encoding="utf-8")
    marker = "const SDD_MAP_PAYLOAD = "
    start = document.find(marker)
    if start < 0:
        return None
    start += len(marker)
    try:
        value, _ = json.JSONDecoder().raw_decode(document[start:])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def main() -> int:
    args = parse_args()
    output_root = args.output_root
    data = output_root / "data"
    summaries = output_root / "summaries"
    maps = output_root / "maps"

    context = supplier_context_payload(
        read_csv_rows(data / "supplier_context_summary.csv"),
        read_csv_rows(data / "supplier_context_results.csv"),
        read_csv_rows(data / "supplier_context_evidence.csv"),
    )
    attempts = read_csv_rows(data / "supplier_context_search_attempts.csv")
    dashboard_path = summaries / "general_kpis.json"
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    dashboard["supplier_context"] = {
        "available": context["available"],
        "summary_rows": context["summary_rows"],
        "result_rows": context["result_rows"],
        "evidence_rows": context["evidence_rows"],
        "signal_counts": context["signal_counts"],
        "top_context_criticality": context["top_context_criticality"],
    }

    exposure: dict[str, dict[str, object]] = {}
    for row in read_csv_rows(data / "supplier_risk_event_seed.csv"):
        site_uid = clean(row.get("site_uid"))
        item = exposure.setdefault(
            site_uid,
            {
                "label": clean(row.get("supplier")) or site_uid,
                "meta": clean(row.get("country_code")),
                "value": 0.0,
                "events": 0,
            },
        )
        item["value"] = safe_float(item.get("value")) + safe_float(row.get("intensity"))
        item["events"] = int(safe_float(item.get("events"))) + 1
    event_exposure_all = sorted(
        exposure.values(),
        key=lambda row: (-safe_float(row.get("value")), clean(row.get("label"))),
    )
    for row in event_exposure_all:
        row["value"] = round(safe_float(row.get("value")), 3)
    dashboard["event_exposure_all"] = event_exposure_all
    dashboard["event_exposure"] = event_exposure_all[:15]

    context_labels = {
        "Fournisseurs documentes",
        "Resultats contexte",
        "Familles signaux faibles",
        "Preuves fournisseur",
        "Sources officielles",
        "Recherches SERP reussies",
        "Incidents a confirmer",
    }
    cards = [
        row
        for row in dashboard.get("cards", [])
        if clean(row.get("label")) not in context_labels
    ]
    cards.extend(
        [
            {"label": "Fournisseurs documentes", "value": len(context["summary_rows"]), "unit": ""},
            {"label": "Resultats contexte", "value": len(context["result_rows"]), "unit": ""},
            {"label": "Preuves fournisseur", "value": len(context["evidence_rows"]), "unit": ""},
            {
                "label": "Sources officielles",
                "value": sum(
                    1
                    for row in context["summary_rows"]
                    if safe_float(row.get("official_source_candidate")) > 0
                ),
                "unit": "sites",
            },
            {
                "label": "Recherches SERP reussies",
                "value": sum(1 for row in attempts if clean(row.get("status")) == "ok"),
                "unit": f"/ {len(attempts)}",
            },
            {
                "label": "Incidents a confirmer",
                "value": sum(
                    1
                    for row in context["evidence_rows"]
                    if clean(row.get("evidence_kind")) == "risque"
                ),
                "unit": "",
            },
        ]
    )
    sdd_brightway_dashboard = dashboard.get("sdd_brightway") or {}
    sdd_summary = {
        clean(row.get("label")): row
        for row in sdd_brightway_dashboard.get("summary", [])
    }
    allocated_delta = safe_float(
        sdd_summary.get("Surimpact ACV net", {}).get("value")
    )
    static_program = safe_float(
        sdd_summary.get("Production ACV statique programme", {}).get("value")
    )
    retained_delta = sum(
        safe_float(row.get("retained_delta_kgco2e"))
        for row in sdd_brightway_dashboard.get("exchange_lcia_monthly", [])
    )
    exact_status = (
        sdd_brightway_dashboard.get("exchange_lcia_status") or [{}]
    )[0]
    dynamic_labels = {
        "Surimpact ACV net",
        "Inventaire SDD avant recalcul",
        "Recalcul Brightway partiel",
        "Resultat dynamique hybride Brightway",
        "Facteurs ACV recalcules",
        "Facteurs Brightway exacts",
        "Surimpact / production",
        "Resultat hybride / production",
        "Part du resultat calculee exactement",
        "Cycle BW corrige",
        "Production + usage avant FdV",
        "Cycle rapproche STELIA/BW",
        "Empreinte BW attributionnelle",
        "Effet masse ecoconception",
    }
    dynamic_index = next(
        (
            index
            for index, row in enumerate(cards)
            if clean(row.get("label")) in dynamic_labels
        ),
        len(cards),
    )
    cards = [
        row
        for row in cards
        if clean(row.get("label")) not in dynamic_labels
    ]
    dynamic_cards = [
        {
            "label": "Inventaire SDD avant recalcul",
            "value": round(allocated_delta / 1000.0, 1),
            "unit": "tCO2e",
        },
        {
            "label": "Resultat dynamique hybride Brightway",
            "value": round(retained_delta / 1000.0, 1),
            "unit": "tCO2e",
        },
        {
            "label": "Part du resultat calculee exactement",
            "value": round(
                safe_float(
                    exact_status.get("exact_retained_impact_share_pct")
                ),
                1,
            ),
            "unit": "%",
        },
        {
            "label": "Facteurs Brightway exacts",
            "value": safe_float(exact_status.get("exact_factor_count")),
            "unit": "",
        },
        {
            "label": "Resultat hybride / production",
            "value": round(100.0 * retained_delta / static_program, 1)
            if static_program
            else 0.0,
            "unit": "%",
        },
    ]
    lifecycle_comparison = next(
        (
            row
            for row in (dashboard.get("brightway_model") or {}).get(
                "excel_runtime_comparison", []
            )
            if clean(row.get("scope_id")) == "lifecycle_excel_aligned"
        ),
        {},
    )
    dynamic_cards.append(
        {
            "label": "Cycle rapproche STELIA/BW",
            "value": round(
                safe_float(lifecycle_comparison.get("runtime_kgco2e")) / 1000.0,
                1,
            ),
            "unit": "tCO2e",
        }
    )
    aircraft_audit_scenarios = {
        clean(row.get("scenario_id")): row
        for row in ((dashboard.get("brightway_model") or {}).get(
            "raw_aircraft_use_audit", {}
        ).get("scenarios", []))
    }
    attributional = aircraft_audit_scenarios.get(
        "brightway_fuel_mass_corrected", {}
    )
    marginal = aircraft_audit_scenarios.get(
        "brightway_marginal_weight_central", {}
    )
    dynamic_cards.extend(
        [
            {
                "label": "Empreinte BW attributionnelle",
                "value": round(
                    safe_float(attributional.get("lifecycle_kgco2e")) / 1000.0,
                    1,
                ),
                "unit": "tCO2e avant FdV",
            },
            {
                "label": "Effet masse ecoconception",
                "value": round(
                    safe_float(marginal.get("lifecycle_kgco2e")) / 1000.0,
                    1,
                ),
                "unit": "tCO2e avant FdV",
            },
        ]
    )
    cards[dynamic_index:dynamic_index] = dynamic_cards
    dashboard["cards"] = cards

    map_path = maps / "supply_geo_base_results_map.html"
    prebuilt_payload = embedded_map_payload(map_path)
    if prebuilt_payload is not None:
        sdd_results = {}
        sdd_brightway = dashboard.get("sdd_brightway") or {}
    else:
        sdd_results = {
            "sdd_node_state": read_csv_rows(data / "sdd_node_state.csv"),
            "sdd_lane_state": read_csv_rows(data / "sdd_lane_state.csv"),
            "sdd_event_ledger": read_csv_rows(data / "sdd_event_ledger.csv"),
        }
        sdd_brightway = {
            **(dashboard.get("sdd_brightway") or {}),
            "inventory_delta": read_csv_rows(
                data / "sdd_brightway_inventory_delta.csv"
            ),
            "exchange_delta": read_csv_rows(
                data / "sdd_brightway_exchange_delta.csv"
            ),
        }
    scenario_suite_path = summaries / "scenario_suite.json"
    scenario_suite = (
        json.loads(scenario_suite_path.read_text(encoding="utf-8"))
        if scenario_suite_path.exists()
        else dashboard.get("scenario_resilience", {})
    )
    scenario_suite["cascades_by_scenario"] = {}
    for scenario_dir in sorted((output_root / "scenarios").glob("*")):
        cascade_path = scenario_dir / "risk_cascades.json"
        if cascade_path.exists():
            scenario_suite["cascades_by_scenario"][scenario_dir.name] = (
                json.loads(cascade_path.read_text(encoding="utf-8"))
            )
    source_ref = json.loads((maps / "source_map_reference.json").read_text(encoding="utf-8"))
    write_enriched_base_map_html(
        map_path,
        source_map=Path(source_ref["source_map_html"]),
        site_rows=read_csv_rows(data / "primary_supply_sites.csv"),
        sdd_results=sdd_results,
        node_operational_rows=read_csv_rows(data / "node_operational_state.csv"),
        environmental_event_rows=read_csv_rows(data / "supplier_risk_event_seed.csv"),
        dashboard_payload=dashboard,
        sdd_brightway_payload=sdd_brightway,
        supplier_context=context,
        scenario_suite=scenario_suite,
        prebuilt_map_payload=prebuilt_payload,
    )
    write_json(dashboard_path, dashboard)
    print(
        f"Refreshed map: {len(context['summary_rows'])} sites, "
        f"{len(context['result_rows'])} results, {len(context['evidence_rows'])} evidence rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
