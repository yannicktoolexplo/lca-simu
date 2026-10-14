"""Assemble the complete offline map for a current-reference simulation.

The world-map builder remains the owner of the simulation payload and of both
lot-trace interfaces.  This module only adds the source comparison and a
clearly scoped annual summary.  A previous run can be supplied explicitly for
comparison; it is never discovered from neighbouring result directories.
"""
from __future__ import annotations

from collections import defaultdict
import csv
from datetime import date, timedelta
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ORIGIN = date(2025, 1, 1)
PRODUCTS = {
    "item:268091": "Cicalfate 268091",
    "item:268967": "Permixon 268967",
}


def _records(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def _physical_quantity(row: dict[str, str], field: str) -> int:
    value = float(row[field])
    if value < 0 or not value.is_integer():
        raise ValueError(f"Invalid physical integer quantity: {field}={value}")
    return int(value)


def annual_metrics(run: Path, label: str) -> list[dict]:
    """Aggregate executed demand, service, dispatch and DC stock by year.

    Demand and service come from the executed service ledger.  Pending demand
    is based on executed departures from Muret and therefore excludes stock
    already in client transport.  No observation after 2025 is inferred.
    """
    summary = json.loads(
        (run / "summaries/first_simulation_summary.json").read_text(encoding="utf-8")
    )
    horizon = int(summary["sim_days"])
    services: dict[tuple[str, int], tuple[int, int]] = {}
    stocks: dict[tuple[str, int], int] = {}
    clients: set[str] = set()
    for row in _records(run / "data/production_demand_service_daily.csv"):
        if row["item_id"] not in PRODUCTS:
            continue
        key = row["item_id"], int(row["day"])
        if key in services:
            raise ValueError("Annual panel expects one documented client per product/day")
        clients.add(row["node_id"])
        services[key] = (
            _physical_quantity(row, "demand_qty"),
            _physical_quantity(row, "served_qty"),
        )
    for row in _records(run / "data/production_stock_availability_daily.csv"):
        if row["node_id"] == "DC-1920" and row["item_id"] in PRODUCTS:
            key = row["item_id"], int(row["day"])
            if key in stocks:
                raise ValueError("Duplicate DC daily stock")
            stocks[key] = _physical_quantity(row, "physical_qty")
    graph = json.loads((run / "input_graph.json").read_text(encoding="utf-8"))
    routes = {
        edge["id"]
        for edge in graph["edges"]
        if edge.get("type") == "transport"
        and edge.get("from") == "DC-1920"
        and edge.get("to") in clients
    }
    if not routes:
        raise ValueError("No documented DC-to-client route")
    shipments: dict[tuple[str, int], int] = defaultdict(int)
    event_ids: set[str] = set()
    for row in _records(run / "data/production_lot_events.csv"):
        if row["item_id"] not in PRODUCTS:
            continue
        if row["event_id"] in event_ids:
            raise ValueError("Duplicate executed lot event")
        event_ids.add(row["event_id"])
        if (
            row["node_id"] in clients
            and row["event_type"] == "opening_stock"
            and _physical_quantity(row, "qty")
        ):
            raise ValueError("Initial client stock needs a separate annual interpretation")
        if (
            row["node_id"] == "DC-1920"
            and row["event_type"] == "lane_ship"
            and row["source_id"] in routes
        ):
            shipments[row["item_id"], int(row["day"])] += _physical_quantity(row, "qty")

    result: list[dict] = []
    expected_days = set(range(horizon))
    for item in PRODUCTS:
        if {day for row_item, day in services if row_item == item} != expected_days:
            raise ValueError("Incomplete customer daily ledger")
        if {day for row_item, day in stocks if row_item == item} != expected_days:
            raise ValueError("Incomplete DC stock ledger")
        cumulative_demand = 0
        cumulative_shipment = 0
        years: dict[int, dict] = {}
        for day in range(horizon):
            when = ORIGIN + timedelta(days=day)
            record = years.setdefault(
                when.year,
                {
                    "product": item,
                    "product_label": PRODUCTS[item],
                    "run": str(run),
                    "label": label,
                    "year": when.year,
                    "days": 0,
                    "demand_qty": 0,
                    "served_qty": 0,
                    "days_with_unshipped_demand": 0,
                    "max_unshipped_qty": 0,
                    "final_dc_physical_qty": 0,
                },
            )
            demand, served = services[item, day]
            cumulative_demand += demand
            cumulative_shipment += shipments[item, day]
            pending = cumulative_demand - cumulative_shipment
            if pending < 0:
                raise ValueError("More client dispatches than known demand")
            record["days"] += 1
            record["demand_qty"] += demand
            record["served_qty"] += served
            record["days_with_unshipped_demand"] += int(pending > 0)
            record["max_unshipped_qty"] = max(record["max_unshipped_qty"], pending)
            record["final_dc_physical_qty"] = stocks[item, day]
        for record in years.values():
            record["served_over_demand_pct"] = (
                100 * record["served_qty"] / record["demand_qty"]
                if record["demand_qty"]
                else None
            )
            result.append(record)
    return result

def _annual_panel(rows: list[dict]) -> str:
    def number(value):
        return "—" if value is None else f"{value:,.0f}".replace(",", " ")

    body = "".join(
        "<tr>"
        + "".join(
            f'<td style="padding:6px;border-bottom:1px solid #dbe3ec">{html.escape(str(value))}</td>'
            for value in (
                row["product_label"],
                row["year"],
                row["label"],
                number(row["demand_qty"]),
                number(row["served_qty"]),
                f'{row["served_over_demand_pct"]:.2f} %'
                if row["served_over_demand_pct"] is not None
                else "—",
                number(row["final_dc_physical_qty"]),
                row["days_with_unshipped_demand"],
                number(row["max_unshipped_qty"]),
            )
        )
        + "</tr>"
        for row in sorted(rows, key=lambda row: (row["product"], row["year"], row["label"]))
    )
    columns = (
        "Produit",
        "Année",
        "Calcul",
        "Demandé UN",
        "Livré UN",
        "Livré / demandé annuel",
        "Stock final Muret UN",
        "Jours avec demande non expédiée",
        "Non expédié maximal UN",
    )
    return (
        '<details id="currentReferenceAnnualComparison" '
        'style="position:fixed;bottom:12px;left:12px;z-index:9998;max-width:94vw;max-height:85vh;overflow:auto;background:white;color:#142b3f;border:1px solid #64748b;border-radius:8px;padding:10px;font:14px system-ui;box-shadow:0 2px 10px #0003">'
        '<summary style="cursor:pointer;font-weight:650">Référence courante · bilan annuel et hypothèses</summary>'
        "<p><strong>À partir de 2026, les valeurs sont celles du scénario prospectif déclaré ; elles ne sont pas des observations industrielles.</strong> Les comparaisons avec les sources industrielles restent limitées à 2025.</p>"
        "<p>Le ratio annuel mesure les quantités servies, pas la ponctualité. Les jours non expédiés comptent les journées où une demande cumulée attend encore son départ de Muret ; les quantités déjà en transport client sont exclues. Ces retards ne sont pas automatiquement des ventes perdues.</p>"
        '<table style="border-collapse:collapse;font-size:12px"><thead><tr>'
        + "".join(f'<th style="padding:6px;text-align:left">{column}</th>' for column in columns)
        + "</tr></thead><tbody>"
        + body
        + "</tbody></table>"
        "<p>Sources : registres simulés quotidiens de service, stock physique total à Muret et départs exécutés du registre de lots. Les quantités physiques en UN restent entières.</p>"
        "<p>Aucune campagne de risques, sensibilité ou Monte Carlo n’est attachée automatiquement à cette carte. Les impacts affichés restent descriptifs, sans attribution causale.</p>"
        "</details>"
    )


def _mode(run: Path) -> str:
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    return manifest.get("forecast_mode", "source_priority")


def _label(run: Path, *, current: bool) -> str:
    mode = _mode(run)
    if current and mode == "coherent_scenario":
        return "Référence courante · scénario prospectif cohérent"
    if current:
        return "Référence courante · prévisions sources prioritaires"
    if mode == "coherent_scenario":
        return "Comparaison explicite · scénario prospectif cohérent"
    return "Référence antérieure · prévisions sources prioritaires"


def build_complete_current_map(
    base_map: Path,
    run: Path,
    output: Path,
    *,
    comparison_run: Path | None = None,
) -> dict:
    """Add annual and 2025 comparisons to a newly built current map."""
    from etudecas.visualization.maps.portable_diagnostic import build_comparison_map
    from etudecas.visualization.maps.source_comparison import build_comparison_payload

    base_map = base_map.resolve()
    run = run.resolve()
    output = output.resolve()
    comparison_run = comparison_run.resolve() if comparison_run is not None else None
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    if comparison_run == run:
        raise ValueError("The explicit comparison run must differ from the current run")
    document = base_map.read_text(encoding="utf-8")
    if 'id="lotTraceModal"' not in document or 'id="lotJourneyModal"' not in document:
        raise ValueError("The base map must contain both lot-trace interfaces")

    # The source-comparison contract requires a ``nominal`` anchor.  When an
    # explicit previous run is supplied it remains that anchor and the current
    # run is the separate ``corrected`` variant, matching the retained map.
    # With no previous run, the current calculation itself is the nominal
    # anchor; labels below still identify it unambiguously as current.
    if comparison_run is None:
        runs = {"nominal": run}
        current_key = "nominal"
    else:
        runs = {"nominal": comparison_run, "corrected": run}
        current_key = "corrected"
    source = ROOT / "etudecas/data/source"
    payload = build_comparison_payload(
        source / "Flow_Data_Inventory_and_Replenishment_rules.xlsx",
        source / "Flow_Data_MRP_results.xlsx",
        runs,
        customer_demand_path=source / "Flow_Data_Customer_Demand.xlsx",
        movements_path=source / "Flow_Data_Inventory_movements.xlsx",
        demand_pf_path=source / "demand_PF.xlsx",
    )
    if not payload.get("demand_pf") or not payload.get("observed_customer_response"):
        raise ValueError("Both native customer source contracts are required")
    payload["runs"][current_key].update(label=_label(run, current=True))
    if comparison_run is not None:
        payload["runs"]["nominal"].update(label=_label(comparison_run, current=False))
    payload.update(
        default_pair="268091/1920",
        default_tab="customer",
        default_runs=[current_key],
    )

    annual = []
    if comparison_run is not None:
        annual.extend(annual_metrics(comparison_run, _label(comparison_run, current=False)))
    annual.extend(annual_metrics(run, _label(run, current=True)))
    payload["five_year_comparison"] = {
        "rows": annual,
        "scope": "Scénarios simulés ; observations industrielles limitées à 2025",
    }
    payload["conventions"].insert(
        0,
        "Carte principale : référence courante. Les courbes industrielles des comparaisons sont limitées à 2025 ; les années suivantes sont des scénarios simulés et ne remplacent aucune observation.",
    )

    head, closing, tail = document.rpartition("</body>")
    if not closing:
        raise ValueError("Missing map closing body tag")
    scoped = output.with_name(f".{output.name}.annual.tmp")
    if scoped.exists():
        raise ValueError(f"Temporary assembly path already exists: {scoped}")
    try:
        scoped.write_text(head + _annual_panel(annual) + closing + tail, encoding="utf-8")
        result = build_comparison_map(scoped, payload, output)
    finally:
        if scoped.exists():
            scoped.unlink()
    result.update(
        current_run=str(run),
        comparison_run=str(comparison_run) if comparison_run is not None else None,
        forecast_mode=_mode(run),
        annual_rows=len(annual),
        source_observations_end="2025-12-31",
        lot_views_preserved=True,
    )
    return result
