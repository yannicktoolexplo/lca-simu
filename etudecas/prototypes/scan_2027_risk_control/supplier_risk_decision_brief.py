#!/usr/bin/env python3
"""Build a compact supplier-risk decision brief from existing evidence.

The brief deliberately keeps four evidence classes separate:

* ``real``: observed 2025 case-study data;
* ``simulated``: outputs of the physical supply simulation;
* ``proxy``: prioritisation indicators that are not calibrated probabilities;
* ``hypothesis``: candidate parameterisations awaiting industrial validation.

No historical page or simulation result is modified.  The command only writes
new files below the output directory supplied on the command line.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import html
import json
import math
import re
import shutil
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from etudecas.prototypes.scan_2027_risk_control.incident_lot_explorer import (
    HTML_OUTPUT_NAME as INCIDENT_LOT_HTML_OUTPUT_NAME,
    JSON_OUTPUT_NAME as INCIDENT_LOT_JSON_OUTPUT_NAME,
    build_incident_lot_payload,
    write_incident_lot_explorer,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT_ROOT = Path(
    r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
)
DEFAULT_CAMPAIGN_ROOT = DEFAULT_ARTIFACT_ROOT / "supplier_risk_influence_20260829_v1"
DEFAULT_OUTPUT_DIR = DEFAULT_CAMPAIGN_ROOT / "decision_brief"
DEFAULT_NETWORK_MAP_HTML = (
    DEFAULT_ARTIFACT_ROOT
    / "industrial_demo_offline_20260828_v6"
    / "assets"
    / "carte_reseau.html"
)
DEFAULT_NETWORK_MAP_PLOTLY = (
    DEFAULT_ARTIFACT_ROOT
    / "industrial_demo_offline_20260828_v6"
    / "assets"
    / "plotly-2.32.0.min.js"
)
DEFAULT_NETWORK_MAP_TOPOJSON = (
    DEFAULT_ARTIFACT_ROOT
    / "industrial_demo_offline_20260828_v6"
    / "assets"
    / "world_110m.json"
)
DEFAULT_STRESS_TEST_HTML = (
    DEFAULT_ARTIFACT_ROOT
    / "industrial_demo_executive_light_20260829_v9"
    / "index.html"
)

VIEWS_DIR_NAME = "views"
NETWORK_MAP_OUTPUT_NAME = "carte_reseau_lots.html"
QUALITY_RISK_MAP_OUTPUT_NAME = "carte_qualite_incident_lots.html"
DELAY_RISK_MAP_OUTPUT_NAME = "carte_retard_338929_incident_lots.html"
STRESS_TEST_OUTPUT_NAME = "stress_tests_incidents_lots.html"
PLOTLY_CDN_URL = "https://cdn.plot.ly/plotly-2.32.0.min.js"

PRODUCTS: dict[str, dict[str, Any]] = {
    "268091": {
        "family": "Cosmétique",
        "factory": "M-1810",
        "service_target": 0.93,
        "component_stock_file": "Stock_Composants_Immobilisé_Cos.csv",
        "component_stock_rule": "excess_all_direct_components",
    },
    "268967": {
        "family": "Pharma",
        "factory": "M-1430",
        "service_target": 0.80,
        "component_stock_file": "Stock_Composants_Immobilisé_Pharma.csv",
        "component_stock_rule": "excess_finance_subset",
    },
}

M1430_FINANCE_SUBSET = {
    "item:038005",
    "item:333362",
    "item:344135",
    "item:734545",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--calibration-root",
        type=Path,
        default=DEFAULT_CAMPAIGN_ROOT / "calibration_probe",
        help="Root containing the non-destructive 365-day calibration probes.",
    )
    parser.add_argument(
        "--network-map-html",
        type=Path,
        default=DEFAULT_NETWORK_MAP_HTML,
        help="Offline network/lot map to bundle as a distinct exploratory run.",
    )
    parser.add_argument(
        "--network-map-plotly",
        type=Path,
        default=DEFAULT_NETWORK_MAP_PLOTLY,
        help="Local Plotly runtime used by the bundled network map.",
    )
    parser.add_argument(
        "--network-map-topojson",
        type=Path,
        default=DEFAULT_NETWORK_MAP_TOPOJSON,
        help="Local world topology used when the bundled map is served over HTTP.",
    )
    parser.add_argument(
        "--stress-test-html",
        type=Path,
        default=DEFAULT_STRESS_TEST_HTML,
        help="Standalone detail page aligned with the two ten-repetition stress tests.",
    )
    parser.add_argument(
        "--quality-risk-map-html",
        type=Path,
        default=None,
        help="Optional map generated from the detailed quality-incident run.",
    )
    parser.add_argument(
        "--delay-risk-map-html",
        type=Path,
        default=None,
        help="Optional map generated from the detailed 338929-delay run.",
    )
    return parser.parse_args()


def read_csv_rows(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle, delimiter=delimiter))
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def _add_return_link(document: str, href: str, label: str) -> str:
    """Add a small offline return link without changing the source artifact."""

    marker = "data-supplier-brief-return"
    if marker in document:
        return document
    snippet = f"""
    <style>
      .supplierBriefReturn{{position:fixed;right:16px;bottom:16px;z-index:10000;
        padding:10px 14px;border-radius:999px;background:#081f3b;color:#fff;
        text-decoration:none;font:700 13px/1.2 Segoe UI,Arial,sans-serif;
        box-shadow:0 8px 24px rgba(15,23,42,.28)}}
      .supplierBriefReturn:hover{{background:#0f766e}}
    </style>
    <a class="supplierBriefReturn" data-supplier-brief-return
       href="{html.escape(href, quote=True)}">{html.escape(label)}</a>
    """
    if "</body>" not in document:
        raise ValueError("Linked HTML view has no closing body tag")
    return document.replace("</body>", snippet + "</body>", 1)


def _localize_network_map(document: str, topojson: Path) -> str:
    """Keep a generated Plotly map usable without network access."""

    document = document.replace(PLOTLY_CDN_URL, "plotly-2.32.0.min.js")
    local_script = '<script src="plotly-2.32.0.min.js"></script>'
    if local_script not in document:
        raise ValueError("Local Plotly script tag not found in network map")
    if "Plotly.setPlotConfig({topojsonURL:" not in document:
        encoded_topology = base64.b64encode(topojson.read_bytes()).decode("ascii")
        offline_config = (
            "<script>Plotly.setPlotConfig({topojsonURL:'./'});"
            "if(location.protocol==='file:'){Plotly.setPlotConfig({topojsonURL:"
            f"'data:application/json;base64,{encoded_topology}#'"
            "});}</script>"
        )
        document = document.replace(
            local_script,
            local_script + "\n  " + offline_config,
            1,
        )
    return document


def bundle_offline_views(
    output_dir: Path,
    *,
    network_map_html: Path,
    network_map_plotly: Path,
    network_map_topojson: Path,
    stress_test_html: Path,
    quality_risk_map_html: Path | None = None,
    delay_risk_map_html: Path | None = None,
) -> list[Path]:
    """Bundle only the lightweight HTML/runtime files needed for the meeting.

    The 1.79 GB scientific trajectory CSV and the historical packages are not
    copied.  The map and the stress-test page remain two explicitly different
    simulation scopes.
    """

    views_dir = output_dir / VIEWS_DIR_NAME
    views_dir.mkdir(parents=True, exist_ok=True)
    map_output = views_dir / NETWORK_MAP_OUTPUT_NAME
    stress_output = views_dir / STRESS_TEST_OUTPUT_NAME
    plotly_output = views_dir / network_map_plotly.name
    topojson_output = views_dir / network_map_topojson.name

    map_document = _localize_network_map(
        network_map_html.read_text(encoding="utf-8"),
        network_map_topojson,
    )
    map_document = _add_return_link(
        map_document,
        "../index.html#access",
        "Retour a la synthese fournisseurs",
    )
    map_output.write_text(map_document, encoding="utf-8")

    stress_document = stress_test_html.read_text(encoding="utf-8")
    stress_document = _add_return_link(
        stress_document,
        "../index.html#cascades",
        "Retour a la synthese fournisseurs",
    )
    stress_output.write_text(stress_document, encoding="utf-8")

    shutil.copyfile(network_map_plotly, plotly_output)
    shutil.copyfile(network_map_topojson, topojson_output)
    outputs = [map_output, stress_output, plotly_output, topojson_output]
    for source, output_name in (
        (quality_risk_map_html, QUALITY_RISK_MAP_OUTPUT_NAME),
        (delay_risk_map_html, DELAY_RISK_MAP_OUTPUT_NAME),
    ):
        if source is None:
            continue
        document = _localize_network_map(
            source.read_text(encoding="utf-8"),
            network_map_topojson,
        )
        document = _add_return_link(
            document,
            "../index.html#access",
            "Retour a la synthese fournisseurs",
        )
        destination = views_dir / output_name
        destination.write_text(document, encoding="utf-8")
        outputs.append(destination)
    return outputs


def json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, set):
        return [json_safe(item) for item in sorted(value)]
    return value


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def to_optional_float(value: Any) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def percentile(values: Iterable[float], q: float) -> float | None:
    clean = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    pos = min(1.0, max(0.0, q)) * (len(clean) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(clean) - 1)
    return clean[lo] + (clean[hi] - clean[lo]) * (pos - lo)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_one(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No file matching {pattern!r} below {root}")
    return matches[0]


def real_2025_metrics(repo_root: Path) -> dict[str, Any]:
    source = repo_root / "etudecas" / "data" / "source"
    revenue_path = discover_one(source, "CA_Perdu*.csv")
    revenue_rows = read_csv_rows(revenue_path, delimiter=";")
    revenue: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "delivered": 0.0,
            "lost": 0.0,
            "days": 0.0,
            "loss_days": 0.0,
            "minimum_lost": math.inf,
            "minimum_lost_date": "",
        }
    )
    for row in revenue_rows:
        values = list(row.values())
        if len(values) < 5:
            continue
        product = str(values[0]).strip()
        delivered = to_float(values[2])
        lost = to_float(values[3])
        revenue[product]["delivered"] += delivered
        revenue[product]["lost"] += lost
        revenue[product]["days"] += 1
        revenue[product]["loss_days"] += 1 if lost > 0 else 0
        if lost < revenue[product]["minimum_lost"]:
            revenue[product]["minimum_lost"] = lost
            revenue[product]["minimum_lost_date"] = str(values[1]).strip()

    stock_summary: dict[str, dict[str, float]] = {}
    for product, config in PRODUCTS.items():
        stock_path = source / str(config["component_stock_file"])
        rows = read_csv_rows(stock_path, delimiter=";")
        values = [to_float(list(row.values())[-1], math.nan) for row in rows]
        values = [value for value in values if math.isfinite(value)]
        stock_summary[product] = {
            "component_stock_mean": statistics.mean(values),
            "component_stock_min": min(values),
            "component_stock_max": max(values),
            "component_stock_weeks": float(len(values)),
        }

    fg_path = discover_one(source, "Stock_PF_Immobilis*.csv")
    fg_rows = read_csv_rows(fg_path, delimiter=";")
    fg_values: dict[str, list[float]] = defaultdict(list)
    for row in fg_rows:
        values = list(row.values())
        if len(values) >= 3:
            fg_values[str(values[0]).strip()].append(to_float(values[-1], math.nan))

    products: list[dict[str, Any]] = []
    for product, config in PRODUCTS.items():
        delivered = revenue[product]["delivered"]
        lost = revenue[product]["lost"]
        potential = delivered + lost
        fg = [value for value in fg_values[product] if math.isfinite(value)]
        products.append(
            {
                "product": product,
                "family": config["family"],
                "factory": config["factory"],
                "evidence": "real",
                "ca_delivered_2025": delivered,
                "ca_lost_2025": lost,
                "ca_potential_2025": potential,
                "ca_service_rate": delivered / potential if potential else 0.0,
                "ca_service_definition": "CA_livre / (CA_livre + CA_perdu)",
                "days_with_lost_ca": int(revenue[product]["loss_days"]),
                "minimum_daily_lost_ca": revenue[product]["minimum_lost"],
                "minimum_daily_lost_ca_date": revenue[product]["minimum_lost_date"],
                "service_target_business": config["service_target"],
                "target_numerically_close_to_ca_rate": (
                    abs(delivered / potential - float(config["service_target"])) <= 0.015
                    if potential
                    else False
                ),
                "target_definition_confirmed": False,
                "component_stock_mean_2025": stock_summary[product]["component_stock_mean"],
                "component_stock_min_2025": stock_summary[product]["component_stock_min"],
                "component_stock_max_2025": stock_summary[product]["component_stock_max"],
                "finished_goods_stock_mean_2025": statistics.mean(fg) if fg else None,
            }
        )

    total_delivered = sum(row["ca_delivered_2025"] for row in products)
    total_lost = sum(row["ca_lost_2025"] for row in products)
    total_potential = sum(row["ca_potential_2025"] for row in products)
    return {
        "evidence": "real",
        "source": str(revenue_path),
        "products": products,
        "total_ca_delivered_2025": total_delivered,
        "total_ca_lost_2025": total_lost,
        "total_ca_potential_2025": total_potential,
        "total_ca_service_rate": total_delivered / total_potential if total_potential else 0.0,
        "limits": [
            "Aucun fournisseur, client, ordre ou lot dans le fichier de CA.",
            "La devise et la definition exacte du CA perdu restent a confirmer.",
            "Une correction negative existe et ne doit pas etre interpretee comme un gain.",
        ],
    }


def graph_price_and_product_maps(graph_path: Path) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], str], dict[str, set[str]]]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    prices: dict[tuple[str, str], list[float]] = defaultdict(list)
    lane_products: dict[tuple[str, str], str] = {}
    supplier_products: dict[str, set[str]] = defaultdict(set)
    for edge in graph.get("edges") or []:
        dst = str(edge.get("to") or "")
        src = str(edge.get("from") or "")
        terms = edge.get("order_terms") or {}
        price = to_float(terms.get("sell_price")) / max(1e-12, to_float(terms.get("price_base"), 1.0))
        product = str((edge.get("attrs") or {}).get("product_code") or "")
        for item in edge.get("items") or []:
            item = str(item)
            if dst in {"M-1430", "M-1810"}:
                prices[(dst, item)].append(price)
            if product:
                lane_products[(src, item)] = product
                supplier_products[src].add(product)
    median_prices = {key: statistics.median(values) for key, values in prices.items() if values}
    return median_prices, lane_products, supplier_products


def service_metrics(service_path: Path) -> dict[str, dict[str, float]]:
    rows = read_csv_rows(service_path)
    grouped: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "demand": 0.0,
            "served": 0.0,
            "served_on_due_date_proxy": 0.0,
            "ending_backlog": 0.0,
            "max_backlog": 0.0,
            "backlog_days": 0.0,
        }
    )
    backlog_by_day: dict[tuple[str, int], float] = defaultdict(float)
    ending_by_lane: dict[tuple[str, str], tuple[int, float]] = {}
    for row in rows:
        item = str(row.get("item_id") or "")
        stats = grouped[item]
        day = int(to_float(row.get("day")))
        demand = to_float(row.get("demand_qty"))
        served = to_float(row.get("served_qty"))
        required = to_float(row.get("required_with_backlog_qty"), demand)
        starting_backlog = max(0.0, required - demand)
        stats["demand"] += demand
        stats["served"] += served
        # Backlog is served before same-day demand in this engine.  This proxy
        # measures volume served on its due day; it is not an order-line OTIF.
        stats["served_on_due_date_proxy"] += min(
            demand, max(0.0, served - starting_backlog)
        )
        backlog = to_float(row.get("backlog_end_qty"))
        node = str(row.get("node_id") or "")
        backlog_by_day[(item, day)] += backlog
        previous = ending_by_lane.get((item, node))
        if previous is None or day >= previous[0]:
            ending_by_lane[(item, node)] = (day, backlog)
    for (item, _day), backlog in backlog_by_day.items():
        stats = grouped[item]
        stats["max_backlog"] = max(stats["max_backlog"], backlog)
        stats["backlog_days"] += float(backlog > 1e-9)
    for (item, _node), (_day, backlog) in ending_by_lane.items():
        grouped[item]["ending_backlog"] += backlog
    for stats in grouped.values():
        stats["fill_rate"] = stats["served"] / stats["demand"] if stats["demand"] else 1.0
        stats["on_due_date_volume_proxy"] = (
            stats["served_on_due_date_proxy"] / stats["demand"]
            if stats["demand"]
            else 1.0
        )
    return dict(grouped)


def component_stock_metrics(data_dir: Path, prices: dict[tuple[str, str], float]) -> dict[str, Any]:
    stock_path = data_dir / "production_input_stocks_daily.csv"
    mrp_path = data_dir / "mrp_trace_daily.csv"
    if not stock_path.exists() or not mrp_path.exists():
        return {}
    stock_rows = read_csv_rows(stock_path)
    targets: dict[tuple[int, str, str], float] = {}
    for row in read_csv_rows(mrp_path):
        node = str(row.get("node_id") or "")
        if node not in {"M-1430", "M-1810"}:
            continue
        targets[(int(to_float(row.get("day"))), node, str(row.get("item_id") or ""))] = to_float(
            row.get("target_stock_qty")
        )
    daily: dict[tuple[int, str], float] = defaultdict(float)
    used_items: dict[str, set[str]] = defaultdict(set)
    unpriced_items: dict[str, set[str]] = defaultdict(set)
    for row in stock_rows:
        node = str(row.get("node_id") or "")
        item = str(row.get("item_id") or "")
        if node not in {"M-1430", "M-1810"}:
            continue
        if node == "M-1430" and item not in M1430_FINANCE_SUBSET:
            continue
        day = int(to_float(row.get("day")))
        quantity = to_float(row.get("stock_end_of_day"))
        target = targets.get((day, node, item), 0.0)
        excess = max(0.0, quantity - target)
        price = prices.get((node, item), 0.0)
        if excess > 0:
            used_items[node].add(item)
            if price <= 0:
                unpriced_items[node].add(item)
        daily[(day, node)] += excess * price
    values: dict[str, list[float]] = defaultdict(list)
    for (_day, node), value in daily.items():
        values[node].append(value)
    return {
        "component_stock_sim_268091": statistics.mean(values["M-1810"]) if values["M-1810"] else 0.0,
        "component_stock_sim_268967": statistics.mean(values["M-1430"]) if values["M-1430"] else 0.0,
        "component_stock_sim_definition_268091": "exces positif au-dessus de la cible MRP, tous composants directs, valorise aux prix fournisseur medians",
        "component_stock_sim_definition_268967": "exces positif au-dessus de la cible MRP, sous-ensemble finance 038005/333362/344135/734545, valorise aux prix fournisseur medians",
        "component_stock_unpriced_items_268091": sorted(unpriced_items["M-1810"]),
        "component_stock_unpriced_items_268967": sorted(unpriced_items["M-1430"]),
        "component_stock_priced_item_count_268091": len(used_items["M-1810"] - unpriced_items["M-1810"]),
        "component_stock_priced_item_count_268967": len(used_items["M-1430"] - unpriced_items["M-1430"]),
    }


def calibration_cases(calibration_root: Path, graph_path: Path, real: dict[str, Any]) -> list[dict[str, Any]]:
    prices, _lane_products, _supplier_products = graph_price_and_product_maps(graph_path)
    real_by_product = {row["product"]: row for row in real["products"]}
    candidates: list[dict[str, Any]] = []
    service_files = sorted(calibration_root.rglob("production_demand_service_daily.csv"))
    for service_path in service_files:
        if any(part.startswith("paired_replays") for part in service_path.parts):
            continue
        data_dir = service_path.parent
        run_dir = data_dir.parent
        case_dir = run_dir.parent if run_dir.name == "run" else run_dir
        try:
            case_id = case_dir.relative_to(calibration_root).as_posix()
        except ValueError:
            case_id = case_dir.name
        if case_id.lower().startswith("oat2/demand_"):
            # These early probes changed an unused top-level field instead of
            # the nested demand profile.  They are preserved on disk but are
            # deliberately excluded from the scientific brief.
            continue
        metrics = service_metrics(service_path)
        if not {"item:268091", "item:268967"}.issubset(metrics):
            continue
        stock = component_stock_metrics(data_dir, prices)
        row: dict[str, Any] = {
            "case_id": case_id,
            "evidence": "hypothesis",
            "fill_268091": metrics["item:268091"]["fill_rate"],
            "fill_268967": metrics["item:268967"]["fill_rate"],
            "on_due_date_volume_proxy_268091": metrics["item:268091"]["on_due_date_volume_proxy"],
            "on_due_date_volume_proxy_268967": metrics["item:268967"]["on_due_date_volume_proxy"],
            "backlog_days_268091": int(metrics["item:268091"]["backlog_days"]),
            "backlog_days_268967": int(metrics["item:268967"]["backlog_days"]),
            "ending_backlog_268091": metrics["item:268091"]["ending_backlog"],
            "ending_backlog_268967": metrics["item:268967"]["ending_backlog"],
            **stock,
            "run_dir": str(run_dir),
            "service_metric_definition": "volume servi cumule / demande cumulee sur 365 jours; un retard rattrape avant la fin est compte servi",
            "on_due_date_proxy_limit": "proxy volumique journalier, pas OTIF commande",
        }
        row["service_gap"] = abs(row["fill_268091"] - 0.93) + abs(row["fill_268967"] - 0.80)
        stock_gap = 0.0
        stock_terms = 0
        for product in ("268091", "268967"):
            sim = to_float(row.get(f"component_stock_sim_{product}"), math.nan)
            observed = to_float(real_by_product[product]["component_stock_mean_2025"])
            if math.isfinite(sim) and observed > 0:
                stock_gap += abs(sim / observed - 1.0)
                stock_terms += 1
        row["stock_relative_gap"] = stock_gap / stock_terms if stock_terms else None
        row["multiobjective_score"] = row["service_gap"] + 0.15 * to_float(row["stock_relative_gap"])
        candidates.append(row)
    return sorted(candidates, key=lambda row: (row["multiobjective_score"], row["case_id"]))


def paired_replay_summary(calibration_root: Path, graph_path: Path) -> dict[str, Any]:
    root = calibration_root / "paired_replays_v2"
    results_path = root / "paired_replay_results.csv"
    manifest_path = root / "campaign_manifest.json"
    if not results_path.exists() or not manifest_path.exists():
        return {
            "available": False,
            "source": str(root),
            "reason": "paired_replays_v2 not complete",
        }
    rows = read_csv_rows(results_path)
    prices, _lane_products, _supplier_products = graph_price_and_product_maps(graph_path)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        run_dir = Path(str(row.get("run_dir") or ""))
        service_path = run_dir / "data" / "production_demand_service_daily.csv"
        service = service_metrics(service_path)
        stock = component_stock_metrics(run_dir / "data", prices)
        run_summary = json.loads(
            (run_dir / "summaries" / "first_simulation_summary.json").read_text(
                encoding="utf-8"
            )
        )
        record: dict[str, Any] = {
            "variant": str(row.get("variant") or ""),
            "seed": int(to_float(row.get("seed"))),
            "run_dir": str(run_dir),
            "common_random_numbers": bool(
                (run_summary.get("policy") or {}).get("common_random_numbers")
            ),
            "stochastic_lead_times": bool(
                (run_summary.get("policy") or {}).get("stochastic_lead_times")
            ),
            "supplier_floor_override_enabled": bool(
                (run_summary.get("policy") or {})
                .get("supplier_neutral_floor_test", {})
                .get("enabled")
            ),
            **stock,
        }
        for product in ("268091", "268967"):
            metrics = service[f"item:{product}"]
            record[f"fill_{product}"] = metrics["fill_rate"]
            record[f"on_due_date_volume_proxy_{product}"] = metrics[
                "on_due_date_volume_proxy"
            ]
            record[f"backlog_days_{product}"] = metrics["backlog_days"]
            record[f"ending_backlog_{product}"] = metrics["ending_backlog"]
        enriched.append(record)

    variants: dict[str, Any] = {}
    for variant in sorted({str(row["variant"]) for row in enriched}):
        selected = [row for row in enriched if row["variant"] == variant]
        summary: dict[str, Any] = {"runs": len(selected)}
        for product in ("268091", "268967"):
            target = float(PRODUCTS[product]["service_target"])
            for metric in (
                "fill",
                "on_due_date_volume_proxy",
                "backlog_days",
                "ending_backlog",
                "component_stock_sim",
            ):
                key = f"{metric}_{product}"
                values = [to_float(row.get(key), math.nan) for row in selected]
                values = [value for value in values if math.isfinite(value)]
                if not values:
                    continue
                summary[f"{key}_mean"] = statistics.mean(values)
                summary[f"{key}_p10"] = percentile(values, 0.10)
                summary[f"{key}_p50"] = percentile(values, 0.50)
                summary[f"{key}_p90"] = percentile(values, 0.90)
                summary[f"{key}_min"] = min(values)
                summary[f"{key}_max"] = max(values)
                summary[f"{key}_stdev"] = statistics.stdev(values) if len(values) > 1 else 0.0
            summary[f"fill_{product}_within_one_point_of_target"] = sum(
                abs(to_float(row.get(f"fill_{product}")) - target) <= 0.01
                for row in selected
            )
        variants[variant] = summary

    paired: list[dict[str, Any]] = []
    by_key = {(row["seed"], row["variant"]): row for row in enriched}
    common_seeds = sorted(
        set(seed for seed, variant in by_key if variant == "physical_nominal")
        & set(seed for seed, variant in by_key if variant == "target_hypothesis")
    )
    for seed in common_seeds:
        nominal = by_key[(seed, "physical_nominal")]
        hypothesis = by_key[(seed, "target_hypothesis")]
        paired.append(
            {
                "seed": seed,
                **{
                    f"delta_{metric}_{product}": hypothesis[f"{metric}_{product}"]
                    - nominal[f"{metric}_{product}"]
                    for product in ("268091", "268967")
                    for metric in (
                        "fill",
                        "on_due_date_volume_proxy",
                        "component_stock_sim",
                    )
                },
            }
        )
    delta_summary: dict[str, Any] = {"paired_seed_count": len(paired)}
    if paired:
        for key in paired[0]:
            if not key.startswith("delta_"):
                continue
            values = [to_float(row[key]) for row in paired]
            delta_summary[f"{key}_mean"] = statistics.mean(values)
            delta_summary[f"{key}_min"] = min(values)
            delta_summary[f"{key}_max"] = max(values)
    candidate_rows = [
        row for row in enriched if row["variant"] == "target_hypothesis"
    ]
    capacity_apply_errors: list[float] = []
    if candidate_rows:
        input_rows = read_csv_rows(
            root / "inputs" / "target_hypothesis_supplier_floors.csv"
        )
        applied_rows = read_csv_rows(
            Path(candidate_rows[0]["run_dir"])
            / "data"
            / "supplier_nominal_parameters.csv"
        )
        applied_by_lane = {
            (
                str(row.get("supplier_id") or ""),
                str(row.get("item_id") or ""),
                str(row.get("dst_node_id") or ""),
            ): row
            for row in applied_rows
        }
        for row in input_rows:
            if str(row.get("dst_node_id") or "") != "M-1430":
                continue
            lane = (
                str(row.get("supplier_id") or ""),
                str(row.get("item_id") or ""),
                str(row.get("dst_node_id") or ""),
            )
            applied = applied_by_lane.get(lane)
            if applied is None:
                capacity_apply_errors.append(math.inf)
                continue
            expected = to_float(
                row.get("tested_capacity_floor_qty_per_day")
                or row.get("neutral_capacity_floor_qty_per_day")
            )
            capacity_apply_errors.append(
                abs(to_float(applied.get("effective_capacity_qty_per_day")) - expected)
            )
    return {
        "available": True,
        "evidence": "hypothesis",
        "source": str(root),
        "manifest": json.loads(manifest_path.read_text(encoding="utf-8")),
        "variants": variants,
        "paired_deltas": delta_summary,
        "validation": {
            "result_rows": len(enriched),
            "unique_seeds": len({row["seed"] for row in enriched}),
            "complete_variant_pairs": len(paired) * 2 == len(enriched),
            "all_common_random_numbers": all(
                row["common_random_numbers"] for row in enriched
            ),
            "all_supplier_floor_overrides_enabled": all(
                row["supplier_floor_override_enabled"] for row in enriched
            ),
            "candidate_m1430_capacity_max_application_error": (
                max(capacity_apply_errors) if capacity_apply_errors else None
            ),
        },
        "rows": enriched,
        "limits": [
            "Dix graines exploratoires ne donnent pas une probabilite industrielle.",
            "Le scenario cible inclut +4% de demande 268967: c'est un stress de demande, pas une calibration physique pure.",
            "Le taux de service volumique cumule n'est ni un OTIF commande ni le taux de service calcule sur le CA.",
        ],
    }


def target_lever_analysis(cases: list[dict[str, Any]]) -> dict[str, Any]:
    def closest(rows: list[dict[str, Any]], product: str, target: float) -> dict[str, Any] | None:
        if not rows:
            return None
        return min(rows, key=lambda row: abs(to_float(row.get(f"fill_{product}")) - target))

    lead_rows = [
        row
        for row in cases
        if "338929" in str(row.get("case_id") or "").lower()
        and "lead" in str(row.get("case_id") or "").lower()
    ]
    m1430_capacity_rows = [
        row
        for row in cases
        if "m1430" in str(row.get("case_id") or "").lower()
        and "cap" in str(row.get("case_id") or "").lower()
        and "demand" not in str(row.get("case_id") or "").lower()
    ]
    demand_stress_rows = [
        row
        for row in cases
        if "m1430" in str(row.get("case_id") or "").lower()
        and "demand268967" in str(row.get("case_id") or "").lower()
    ]
    target_80 = 0.80
    below = sorted(
        (row for row in m1430_capacity_rows if to_float(row.get("fill_268967")) <= target_80),
        key=lambda row: to_float(row.get("fill_268967")),
        reverse=True,
    )
    above = sorted(
        (row for row in m1430_capacity_rows if to_float(row.get("fill_268967")) >= target_80),
        key=lambda row: to_float(row.get("fill_268967")),
    )
    lead_best = closest(lead_rows, "268091", 0.93)
    demand_best = closest(demand_stress_rows, "268967", target_80)
    return {
        "evidence": "hypothesis",
        "service_metric": "volumetric horizon fill",
        "target_definition_confirmed": False,
        "268091": {
            "target": 0.93,
            "closest_lead_case": lead_best,
            "interpretation": (
                "Le point proche de 93% est un effet lotifie et non monotone. "
                "La reduction du delai ne doit pas etre presentee comme causalement degradante."
            ),
        },
        "268967": {
            "target": target_80,
            "capacity_only_lower_bracket": below[0] if below else None,
            "capacity_only_upper_bracket": above[0] if above else None,
            "closest_demand_stress_case": demand_best,
            "interpretation": (
                "Avec demande fixe, la production par lots cree un plateau de service autour de la cible. "
                "Le cas le plus proche utilisant une hausse de demande est un stress, pas une calibration pure."
            ),
        },
        "metric_warning": (
            "Les cibles 80/93 peuvent designer OTIF, lignes completes, quantites a date ou service CA; "
            "ces definitions ne sont pas interchangeables."
        ),
    }


def response_curve_rows(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    curves: list[dict[str, Any]] = []
    for row in cases:
        case_id = str(row.get("case_id") or "")
        lowered = case_id.lower()
        lever = ""
        product = ""
        unit = "facteur"
        match: re.Match[str] | None = None
        if "338929_lead_" in lowered or "lead338929_" in lowered:
            lever = "Delai du composant 338929"
            product = "268091"
            match = re.search(r"_(\d+p\d+)$", lowered)
        elif "338929_stock_" in lowered:
            lever = "Stock fournisseur cible du 338929"
            product = "268091"
            unit = "unites"
            match = re.search(r"_(\d+)$", lowered)
        elif "m1430_capacity_" in lowered and "demand" not in lowered:
            lever = "Capacites fournisseurs vers M-1430"
            product = "268967"
            match = re.search(r"_(\d+p\d+)$", lowered)
        elif "m1810_capacity_" in lowered:
            lever = "Capacite de production M-1810"
            product = "268091"
            match = re.search(r"_(\d+p\d+)$", lowered)
        if not lever or match is None:
            continue
        level_text = match.group(1)
        level = float(level_text.replace("p", "."))
        curves.append(
            {
                "lever": lever,
                "level": level,
                "level_unit": unit,
                "product": product,
                "fill_rate": to_float(row.get(f"fill_{product}")),
                "on_due_date_volume_proxy": to_float(
                    row.get(f"on_due_date_volume_proxy_{product}")
                ),
                "backlog_days": int(to_float(row.get(f"backlog_days_{product}"))),
                "case_id": case_id,
                "evidence": "hypothesis",
            }
        )
    deduplicated: dict[tuple[str, float], dict[str, Any]] = {}
    for row in sorted(curves, key=lambda item: item["case_id"]):
        deduplicated.setdefault((row["lever"], row["level"]), row)
    return sorted(deduplicated.values(), key=lambda row: (row["lever"], row["level"]))


def sensitivity_ranking(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = (
        repo_root
        / "etudecas"
        / "simulation"
        / "sensibility"
        / "active_supplier_parameter_result_60_75_guarded"
        / "supplier_parameter_sensitivity_cases.csv"
    )
    rows = [row for row in read_csv_rows(path) if str(row.get("status") or "ok") == "ok"]
    baseline = next((row for row in rows if row.get("case_id") == "baseline"), {})
    base_fill = to_float(baseline.get("kpi::fill_rate"), 1.0)
    base_cost = to_float(baseline.get("kpi::total_cost"))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("case_id") == "baseline":
            continue
        grouped[str(row.get("parameter_key") or row.get("parameter_label") or "unknown")].append(row)
    ranking: list[dict[str, Any]] = []
    for key, variants in grouped.items():
        fills = [to_float(row.get("kpi::fill_rate"), base_fill) for row in variants]
        costs = [to_float(row.get("kpi::total_cost"), base_cost) for row in variants]
        worst = min(variants, key=lambda row: to_float(row.get("kpi::fill_rate"), base_fill))
        ranking.append(
            {
                "parameter_key": key,
                "parameter_label": str(worst.get("parameter_label") or key),
                "parameter_group": str(worst.get("parameter_group") or ""),
                "supplier_id": next(
                    (token for token in key.replace("::", " ").split() if token.startswith("SDC-")),
                    "",
                ),
                "baseline_fill_rate": base_fill,
                "minimum_fill_rate_tested": min(fills),
                "maximum_fill_drop": max(0.0, base_fill - min(fills)),
                "worst_tested_level": to_float(worst.get("level"), math.nan),
                "maximum_absolute_cost_change": max((abs(cost - base_cost) for cost in costs), default=0.0),
                "case_count": len(variants),
                "evidence": "simulated",
                "interpretation_limit": "one_factor_or_predefined_combination; baseline fill=100%; nonlinear thresholds",
            }
        )
    ranking.sort(key=lambda row: (-row["maximum_fill_drop"], row["parameter_label"]))
    meta = {
        "source": str(path),
        "case_count": len(rows),
        "baseline_fill_rate": base_fill,
        "method": "deterministic one-factor and predefined-combination screening",
        "not_sobol": True,
    }
    return ranking, meta


def monte_carlo_inventory(repo_root: Path) -> dict[str, Any]:
    active_dir = repo_root / "etudecas" / "simulation" / "montecarlo" / "active_mrp_physical_uncertainty"
    legacy_dir = repo_root / "etudecas" / "simulation" / "montecarlo" / "result"
    active = json.loads((active_dir / "montecarlo_summary.json").read_text(encoding="utf-8"))
    legacy = json.loads((legacy_dir / "montecarlo_summary.json").read_text(encoding="utf-8"))
    active_rows = [
        row
        for row in read_csv_rows(active_dir / "montecarlo_samples.csv")
        if str(row.get("is_baseline") or "").lower() not in {"true", "1"}
        and str(row.get("status") or "ok") == "ok"
    ]
    factor_count = len(
        [
            key
            for key in (active_rows[0].keys() if active_rows else [])
            if key.startswith(("factor::", "capacity_node::", "demand_item::", "supplier_"))
        ]
    )
    fills = [to_float(row.get("kpi::fill_rate"), math.nan) for row in active_rows]
    fills = [value for value in fills if math.isfinite(value)]
    legacy_rows = [
        row
        for row in read_csv_rows(legacy_dir / "montecarlo_samples.csv")
        if str(row.get("is_baseline") or "").lower() not in {"true", "1"}
        and str(row.get("status") or "ok") == "ok"
    ]
    return {
        "active": {
            "source": str(active_dir),
            "runs": len(active_rows),
            "simulated_days": 1825,
            "factor_columns": factor_count,
            "fill_mean": statistics.mean(fills) if fills else None,
            "fill_p05": percentile(fills, 0.05),
            "fill_p50": percentile(fills, 0.50),
            "fill_p95": percentile(fills, 0.95),
            "driver_ranking_valid": len(active_rows) >= max(50, 5 * factor_count),
            "reading": "distribution de stress conditionnelle; facteurs trop nombreux pour classer les causes",
            "summary_schema": active.get("schema_version"),
        },
        "legacy": {
            "source": str(legacy_dir),
            "runs": len(legacy_rows),
            "simulated_days": 30,
            "driver_ranking_valid_for_active_model": False,
            "reading": "exploration court terme sur un ancien graphe; le cold-start interdit de l'utiliser comme cible 80%",
            "summary_schema": legacy.get("schema_version"),
        },
    }


def supplier_decision_table(
    repo_root: Path,
    graph_path: Path,
    sensitivity: list[dict[str, Any]],
) -> dict[str, Any]:
    path = (
        repo_root
        / "etudecas"
        / "risk"
        / "supplier_criticality"
        / "result"
        / "data"
        / "supplier_item_risk_kpi.csv"
    )
    rows = read_csv_rows(path)
    _prices, lane_products, _supplier_products = graph_price_and_product_maps(graph_path)
    consequence: dict[str, float] = {}
    for row in sensitivity:
        supplier = str(row.get("supplier_id") or "")
        if supplier:
            consequence[supplier] = max(
                consequence.get(supplier, 0.0),
                to_float(row.get("maximum_fill_drop")),
            )
    table: list[dict[str, Any]] = []
    for row in rows:
        supplier = str(row.get("supplier_id") or "")
        if not supplier.startswith("SDC-VD"):
            continue
        item = str(row.get("item_id") or "")
        factory = str(row.get("dst_node_id") or "")
        product = lane_products.get((supplier, item), "")
        product_source = "graph_supplier_item_lane"
        if not product and factory in {"M-1810", "M-1430"}:
            product = "268091" if factory == "M-1810" else "268967"
            product_source = "factory_fallback_due_to_identifier_mismatch"
        tested = supplier in consequence
        table.append(
            {
                "supplier_id": supplier,
                "supplier_name": str(row.get("supplier_name") or ""),
                "item_id": item,
                "factory": factory,
                "product": product,
                "product_mapping_source": product_source,
                "occurrence_indicator_proxy_4w": to_optional_float(row.get("risk_probability_proxy_4w")),
                "occurrence_indicator_high_proxy_4w": to_optional_float(row.get("risk_probability_high_proxy_4w")),
                "action_priority_proxy": to_optional_float(row.get("action_priority_score")),
                "structural_criticality_proxy": to_optional_float(row.get("criticality_score")),
                "mono_source_score": to_optional_float(row.get("mono_source_score")),
                "lead_days_q90": to_optional_float(row.get("lead_days_q90")),
                "stock_coverage_days": to_optional_float(row.get("stock_coverage_days")),
                "resilience_proxy": to_optional_float(row.get("resilience_score")),
                "conditional_fill_drop_tested": consequence.get(supplier),
                "conditional_consequence_tested": tested,
                "conditional_consequence_scope": "maximum supplier-level fill drop in separate guarded screening; repeated on supplier-item rows for display",
                "decision_zone_proxy": str(row.get("decision_zone") or ""),
                "recommended_action_proxy": str(row.get("robust_decision") or ""),
                "evidence_occurrence": "proxy",
                "evidence_consequence": "simulated" if tested else "not_tested",
            }
        )
    table.sort(
        key=lambda row: (
            -(row["conditional_fill_drop_tested"] if row["conditional_fill_drop_tested"] is not None else -1.0),
            -(row["action_priority_proxy"] if row["action_priority_proxy"] is not None else -1.0),
            row["supplier_id"],
        )
    )
    return {
        "source": str(path),
        "rows": table,
        "ranking_rule": "two separate axes: occurrence proxy and conditional consequence; no combined probability of loss",
        "configuration_compatibility": "not demonstrated: criticality proxy and guarded sensitivity were produced by separate studies",
        "occurrence_probability_calibrated": False,
        "untested_supplier_ids": sorted(
            {row["supplier_id"] for row in table if not row["conditional_consequence_tested"]}
        ),
        "identifier_fallback_rows": sum(
            row["product_mapping_source"] != "graph_supplier_item_lane" for row in table
        ),
        "focus_item_ids": ["item:338929", "item:344135", "item:333362"],
    }


def lot_and_cascade_summary(artifact_root: Path) -> dict[str, Any]:
    path = artifact_root / "industrial_demo_executive_light_20260829_v9" / "brief_results.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "source": str(path),
        "scenario_selection": payload.get("scenario_selection") or {},
        "quality": payload.get("quality") or {},
        "delay": payload.get("delay") or {},
        "definitions": payload.get("definitions") or {},
        "decision_policy": payload.get("decision_policy") or {},
        "supplier_risk_forecast": payload.get("supplier_risk_forecast") or {},
        "incident_identities": {
            "quality": {
                "label": "Retenue qualite demonstrative sur la chaine 021081 -> 773474 -> 268967",
                "historical_incident": False,
            },
            "delay": {
                "label": "Retard demonstratif du composant 338929, fournisseur SDC-VD0914360C, vers M-1810 -> 268091",
                "historical_incident": False,
            },
        },
    }


def fr_number(value: Any, decimals: int = 0) -> str:
    number = to_optional_float(value)
    if number is None:
        return "n.d."
    rendered = f"{number:,.{decimals}f}"
    return rendered.replace(",", "\u202f").replace(".", ",")


def fr_percent(value: Any, decimals: int = 1) -> str:
    number = to_optional_float(value)
    return "n.d." if number is None else f"{fr_number(100.0 * number, decimals)} %"


def fr_money(value: Any, decimals: int = 0) -> str:
    number = to_optional_float(value)
    return "n.d." if number is None else f"{fr_number(number, decimals)} EUR*"


def compact_money(value: Any) -> str:
    number = to_optional_float(value)
    if number is None:
        return "n.d."
    if abs(number) >= 1_000_000:
        return f"{fr_number(number / 1_000_000, 2)} M EUR*"
    if abs(number) >= 1_000:
        return f"{fr_number(number / 1_000, 0)} k EUR*"
    return fr_money(number)


def evidence_register(payload: dict[str, Any]) -> list[dict[str, Any]]:
    real = payload["real_2025"]
    sensitivity = payload["sensitivity"]
    monte_carlo = payload["monte_carlo"]
    suppliers = payload["suppliers"]
    cascades = payload["cascades"]
    paired = payload["paired_replays"]
    return [
        {
            "bloc": "CA et stocks 2025",
            "niveau_de_preuve": "observe_2025",
            "ce_que_lon_peut_dire": "Montants agreges par produit et niveaux hebdomadaires de stock.",
            "ce_que_lon_ne_peut_pas_dire": "Quel fournisseur ou lot a cause chaque perte.",
            "source": real["source"],
        },
        {
            "bloc": "Objectifs 80% / 93%",
            "niveau_de_preuve": "regle_metier_a_confirmer",
            "ce_que_lon_peut_dire": "Deux niveaux demandes existent dans les scripts de preparation.",
            "ce_que_lon_ne_peut_pas_dire": "Qu'ils representent le meme KPI que le fill rate ou le service CA.",
            "source": "etudecas/simulation_prep/prepare_simulation_graph.py",
        },
        {
            "bloc": "Reglage 365 jours",
            "niveau_de_preuve": "hypothese_simulee",
            "ce_que_lon_peut_dire": "Quels jeux de parametres produisent des niveaux de service proches ou encadrants.",
            "ce_que_lon_ne_peut_pas_dire": "Qu'un jeu est la vraie baseline industrielle.",
            "source": payload["calibration_root"],
        },
        {
            "bloc": "Rejeux apparies multi-graines",
            "niveau_de_preuve": "hypothese_simulee",
            "ce_que_lon_peut_dire": "Dispersion liee aux delais stochastiques sous les hypotheses testees.",
            "ce_que_lon_ne_peut_pas_dire": "Probabilite industrielle ou performance certifiee.",
            "source": paired.get("source", ""),
        },
        {
            "bloc": "Sensibilite",
            "niveau_de_preuve": "screening_simule",
            "ce_que_lon_peut_dire": "Seuils et leviers qui changent fortement le resultat dans cette baseline.",
            "ce_que_lon_ne_peut_pas_dire": "Importance causale globale de type Sobol.",
            "source": sensitivity["meta"]["source"],
        },
        {
            "bloc": "Monte-Carlo actif",
            "niveau_de_preuve": "enveloppe_de_stress_simulee",
            "ce_que_lon_peut_dire": "Dispersion conditionnelle de dix combinaisons de stress.",
            "ce_que_lon_ne_peut_pas_dire": "Classer 131 facteurs ou estimer une probabilite fournisseur.",
            "source": monte_carlo["active"]["source"],
        },
        {
            "bloc": "Priorite fournisseurs",
            "niveau_de_preuve": "proxy_plus_consequence_simulee",
            "ce_que_lon_peut_dire": "Ou concentrer la collecte et les stress tests.",
            "ce_que_lon_ne_peut_pas_dire": "Probabilite reelle d'incident ou perte historique attribuable.",
            "source": suppliers["source"],
        },
        {
            "bloc": "Cascades et lots",
            "niveau_de_preuve": "demonstrateurs_simules",
            "ce_que_lon_peut_dire": "Propagation conditionnelle et genealogie FIFO simulee de bout en bout.",
            "ce_que_lon_ne_peut_pas_dire": "Qu'il s'agit des deux risques les plus probables ou de vrais lots 2025.",
            "source": cascades["source"],
        },
    ]


def report_markdown(payload: dict[str, Any]) -> str:
    real_rows = {row["product"]: row for row in payload["real_2025"]["products"]}
    target = payload["target_analysis"]
    sensitivity = payload["sensitivity"]
    mc = payload["monte_carlo"]["active"]
    suppliers = payload["suppliers"]["rows"]
    cascades = payload["cascades"]
    paired = payload["paired_replays"]
    navigation = payload["navigation"]
    nominal = paired.get("variants", {}).get("physical_nominal", {})
    hypothesis = paired.get("variants", {}).get("target_hypothesis", {})
    quality = cascades["quality"]
    delay = cascades["delay"]
    lead_case = target["268091"].get("closest_lead_case") or {}
    lower = target["268967"].get("capacity_only_lower_bracket") or {}
    upper = target["268967"].get("capacity_only_upper_bracket") or {}
    demand_case = target["268967"].get("closest_demand_stress_case") or {}
    aligned_map_lines = []
    for key, label in (
        ("quality_incident_lot_map", "Carte retenue qualité et lots"),
        ("delay_incident_lot_map", "Carte retard 338929 et lots"),
    ):
        if key in navigation:
            aligned_map_lines.append(
                f"- [{label}]({navigation[key]['href']}) : incident, flux et "
                "généalogie issus du même run détaillé seed 330281."
            )
    lines = [
        "# De l'alerte fournisseur a la decision",
        "",
        "Cette synthese relie les donnees 2025, les leviers de simulation, les fournisseurs, les cascades et les lots. Chaque resultat est classe comme **observe**, **simule**, **proxy** ou **hypothese a valider**.",
        "",
        "## Acces hors ligne",
        "",
        f"- [Comparer normal, incident et solution]({navigation['incident_lot_explorer']['href']}) : généalogie détaillée seed 330281 et comparaison estimée par ordre de production entre trois futurs simulés.",
        *aligned_map_lines,
        f"- [Stress tests detailles]({navigation['aligned_stress_tests']['href']}) : memes deux incidents et memes dix repetitions que cette synthese.",
        f"- [Carte historique du reseau]({navigation['network_lot_map']['href']}) : run state-dependent distinct de 365 jours (seed 320270), avec 3 620 lots et 5 194 liens de genealogie.",
        "",
        "Les nouvelles cartes associent physiquement un incident à ses lots dans une même simulation. La carte historique montre un autre run et reste séparée.",
        "",
        "## Conclusion en une minute",
        "",
        f"- **Observe en 2025 :** {compact_money(payload['real_2025']['total_ca_lost_2025'])} de CA perdu declare au total. Le produit 268091 concentre {compact_money(real_rows['268091']['ca_lost_2025'])}; le 268967, {compact_money(real_rows['268967']['ca_lost_2025'])}.",
        "- **Leviers simules :** la capacite fournisseur domine le screening lorsque les marges passent sous un seuil. Pour 268091, le composant mono-source 338929 et son delai sont le point de vigilance local le plus net. Pour 268967, le goulot observe est le composant 344135 dans les essais de capacite M-1430.",
        "- **80% / 93% :** on sait produire des cas proches ou encadrants, mais pas encore prouver qu'ils correspondent au KPI industriel. Le service CA, le volume finalement servi et l'OTIF ne sont pas la meme mesure.",
        "- **Prevision fournisseur :** le modele prevoit deja les consequences d'un incident impose. La probabilite d'apparition n'est pas encore calibree faute d'historique OTIF, qualite, capacite et incidents.",
        "- **Lots :** la genealogie fournisseur -> reception -> campagne -> lot fini -> client fonctionne dans la simulation. Elle doit maintenant etre raccordee aux vrais identifiants ASN/WMS/OF/livraison.",
        "",
        "## 1. Situation observee en 2025",
        "",
        "| Produit | Famille / usine | CA livre | CA perdu | Service calcule sur le CA | Stock composants moyen | Stock PF moyen |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for product in ("268091", "268967"):
        row = real_rows[product]
        lines.append(
            "| {product} | {family} / {factory} | {delivered} | {lost} | {service} | {components} | {fg} |".format(
                product=product,
                family=row["family"],
                factory=row["factory"],
                delivered=compact_money(row["ca_delivered_2025"]),
                lost=compact_money(row["ca_lost_2025"]),
                service=fr_percent(row["ca_service_rate"], 2),
                components=compact_money(row["component_stock_mean_2025"]),
                fg=compact_money(row["finished_goods_stock_mean_2025"]),
            )
        )
    lines.extend(
        [
            "",
            "`EUR*` signifie que les fichiers sont traites comme des euros, mais la devise doit etre confirmee. Ces donnees n'ont aucun identifiant fournisseur ou lot : elles valident des niveaux produit, pas une cause.",
            "",
            "## 2. Comment lire les objectifs 80% et 93%",
            "",
            f"- **268091 / objectif 93% :** le cas de delai 338929 le plus proche est `{lead_case.get('case_id', 'n.d.')}`, avec {fr_percent(lead_case.get('fill_268091'), 2)} de volume servi sur l'horizon et {fr_percent(lead_case.get('on_due_date_volume_proxy_268091'), 2)} sur le proxy servi a date. La reponse n'est pas monotone a cause des lots et du calendrier.",
            f"- **268967 / objectif 80% :** avec demande fixe, les essais de capacite encadrent la cible entre {fr_percent(lower.get('fill_268967'), 2)} (`{lower.get('case_id', 'n.d.')}`) et {fr_percent(upper.get('fill_268967'), 2)} (`{upper.get('case_id', 'n.d.')}`). Le lot fixe de 107 800 unites vaut environ 6,84 points de service annuel.",
            f"- Le cas `{demand_case.get('case_id', 'n.d.')}` atteint {fr_percent(demand_case.get('fill_268967'), 2)}, mais en augmentant la demande. C'est un **stress de demande**, pas une preuve de baseline.",
            "",
            "La cible 93% est numeriquement proche du service CA 2025 du 268091 (92,87%). La cible 80% ne l'est pas pour le 268967, dont le service CA calcule vaut 95,40%. Il faut donc faire definir l'indicateur par l'industriel avant calibration finale.",
            "",
            f"Sur dix graines appariées, l'hypothese cible donne en moyenne {fr_percent(hypothesis.get('fill_268091_mean'),2)} pour 268091 et {fr_percent(hypothesis.get('fill_268967_mean'),2)} pour 268967. Elle contient toujours une hausse de demande de 4% et reste donc une hypothese de stress.",
            "",
            f"Le plancher physique infere donne un stock composants simule moyen de {compact_money(nominal.get('component_stock_sim_268091_mean'))} pour 268091 contre {compact_money(real_rows['268091']['component_stock_mean_2025'])} observe, et {compact_money(nominal.get('component_stock_sim_268967_mean'))} pour 268967 contre {compact_money(real_rows['268967']['component_stock_mean_2025'])}. La proximite est encourageante, mais la definition de stock immobilise reste un proxy et l'article 693055 n'est pas valorise.",
            "",
            "## 3. Leviers les plus influents dans les analyses existantes",
            "",
            "Les courbes locales jointes dans `product_lever_response_curves.csv` montrent quatre faits : une falaise de capacite vers M-1430; une reponse non monotone du delai 338929; un plateau rapide du stock cible 338929; et aucune amelioration quand la capacite M-1810 est multipliee jusqu'a trois, ce qui situe le goulot en amont de l'usine dans ces essais.",
            "",
            "| Rang | Levier teste | Niveau le plus defavorable | Baisse maximale du service global | Lecture |",
            "|---:|---|---:|---:|---|",
        ]
    )
    for index, row in enumerate(
        [item for item in sensitivity["ranking"] if item["maximum_fill_drop"] > 1e-9][
            :12
        ],
        start=1,
    ):
        lines.append(
            f"| {index} | {row['parameter_label']} | {fr_number(row['worst_tested_level'], 2)} | {fr_percent(row['maximum_fill_drop'], 1)} | Seuil conditionnel, un facteur a la fois |"
        )
    lines.extend(
        [
            "",
            f"Le screening contient {sensitivity['meta']['case_count']} cas valides et part d'une baseline a {fr_percent(sensitivity['meta']['baseline_fill_rate'], 1)}. Il montre des **falaises de capacite** : un levier peut etre sans effet tant que la marge suffit, puis devenir dominant. Ce classement n'est pas une analyse Sobol et ne se transpose pas automatiquement a la future baseline calibree.",
            "",
            "## 4. Dispersion des stress combines",
            "",
            f"Le Monte-Carlo actif contient {mc['runs']} repetitions sur {mc['simulated_days']} jours avec environ {mc['factor_columns']} facteurs varies ensemble. Le service global va de P05 {fr_percent(mc['fill_p05'], 1)} a P95 {fr_percent(mc['fill_p95'], 1)}, mediane {fr_percent(mc['fill_p50'], 1)} et moyenne {fr_percent(mc['fill_mean'], 1)}.",
            "",
            "Cette enveloppe repond a 'que peut produire ce jeu de stress ?', pas a 'quelle est la probabilite reelle ?'. Dix repetitions pour plus de cent facteurs ne permettent pas de classer les causes.",
            "",
            "## 5. Fournisseurs a instruire en premier",
            "",
            "Les deux axes restent separes : le **signal d'alerte proxy** et la **gravite conditionnelle simulee**. Ils ne sont pas multiplies en une fausse perte attendue.",
            "",
            "| Fournisseur | Article | Produit | Signal proxy 4 sem. | Consequence testee | Mono-source | Delai Q90 |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in suppliers[:12]:
        lines.append(
            f"| {row['supplier_id']} | {row['item_id'].replace('item:', '')} | {row['product'] or 'a rapprocher'} | {fr_percent(row['occurrence_indicator_proxy_4w'], 1)} | {fr_percent(row['conditional_fill_drop_tested'], 1) if row['conditional_consequence_tested'] else 'non teste'} | {fr_number(row['mono_source_score'], 2)} | {fr_number(row['lead_days_q90'], 0)} j |"
        )
    lines.extend(
        [
            "",
            "Le signal 4 semaines n'est pas une probabilite calibree. Il sert uniquement a prioriser la collecte et les stress tests. Les donnees reelles actuelles ne contiennent ni OTIF, ni retard reel, ni non-conformite, ni note de criticite fournisseur.",
            "",
            "## 6. Deux cascades demonstratives et leurs solutions",
            "",
            "### Retenue qualite vers 268967 — simulee si l'incident survient",
            "",
            f"L'effet client apparait dans {quality.get('customer_delay_count', 0)}/{quality.get('simulation_count', 0)} repetitions. L'ecart moyen apparait d'abord sur le stock a J{quality.get('conditional_impact_timeline', {}).get('first_stock_effect_day', 'n.d.')}, sur la production a J{quality.get('conditional_impact_timeline', {}).get('first_production_effect_day', 'n.d.')} puis sur le client a J{quality.get('conditional_impact_timeline', {}).get('first_customer_backlog_day', 'n.d.')}.",
            f"Le plan combine laisse {fr_percent(quality.get('combined', {}).get('remaining_ratio'), 1)} du retard et recupere {fr_number(quality.get('combined', {}).get('days_recovered'), 0)} jours en moyenne dans les cas touches. Le transport accelere laisse {fr_percent(quality.get('expedited', {}).get('remaining_ratio'), 1)} et recupere {fr_number(quality.get('expedited', {}).get('days_recovered'), 1)} jours, mais aggrave une repetition.",
            "",
            "### Retard 338929 vers M-1810 / 268091 — simule si l'incident survient",
            "",
            f"Le retard est absorbe avant le client dans {delay.get('absorbed_count', 0)}/{delay.get('simulation_count', 0)} repetitions. Dans les cas touches, l'acceleration transport supprime le retard client teste et recupere {fr_number(delay.get('expedited', {}).get('days_recovered'), 0)} jours pour un cout moyen de {fr_number(delay.get('expedited', {}).get('incremental_cost'), 0)} unites monetaires simulees. Le plan combine obtient le meme service pour un cout plus eleve; la replanification proxy testee aggrave le retard et doit etre revue.",
            "",
            "Ces deux incidents sont des **demonstrateurs choisis a l'avance**, ni des incidents historiques ni les deux risques les plus probables du reseau.",
            "",
            "## 7. Lecture lot par lot",
            "",
            f"- Qualite : {fr_number(quality.get('traceability_example', {}).get('exposed_shipped_qty'), 0)} {quality.get('traceability_example', {}).get('exposed_shipped_uom', '')} exposees, {quality.get('traceability_example', {}).get('finished_lot_count', 0)} lots finis 268967 et {quality.get('traceability_example', {}).get('client_lot_count', 0)} allocations de lots au client dans l'exemple detaille.",
            f"- Retard 338929 : {fr_number(delay.get('traceability_example', {}).get('exposed_shipped_qty'), 0)} {delay.get('traceability_example', {}).get('exposed_shipped_uom', '')} exposees, {delay.get('traceability_example', {}).get('finished_lot_count', 0)} lots finis 268091 et {delay.get('traceability_example', {}).get('client_lot_count', 0)} allocations de lots au client.",
            "",
            "`Expose` signifie que le flux de l'incident entre dans la genealogie du lot; cela ne prouve pas que l'incident a cause son retard. Il faut comparer le meme lot entre normal, incident et action avec la meme graine. Les lots sont simules en FIFO et ne sont pas encore les lots reels 2025.",
            "",
            "## 8. Fil rouge propose a l'industriel",
            "",
            "1. Confirmer le KPI 80/93 et le mapping finance/operations.",
            "2. Charger les commandes fournisseurs avec dates promises/reelles, ASN, lots, controles qualite et capacites.",
            "3. Calibrer plusieurs jeux de parametres equivalents sur service, stocks hebdomadaires, ruptures et CA perdu 2025.",
            "4. Faire un screening Morris groupe, puis une analyse globale sur les 8 a 12 leviers retenus et 500 a 1 000 simulations appariées.",
            "5. Relier alertes fournisseur -> lots/OF -> clients -> CA/marge, puis comparer les actions avec leurs vrais couts et delais de mise en oeuvre.",
            "",
            "La promesse defendable aujourd'hui est : **prevoir l'impact aval conditionnel d'un risque fournisseur et montrer quoi proteger**. La prochaine etape de donnees permet de passer a : **prevoir aussi la probabilite d'apparition et declencher la bonne action au bon moment**.",
        ]
    )
    return "\n".join(lines) + "\n"


def html_bar(label: str, value: float, maximum: float, displayed: str, color: str) -> str:
    width = 0.0 if maximum <= 0 else min(100.0, max(0.0, 100.0 * value / maximum))
    return (
        '<div class="bar-row">'
        f'<div class="bar-label">{html.escape(label)}</div>'
        '<div class="bar-track">'
        f'<div class="bar-fill" style="width:{width:.3f}%;background:{color}"></div>'
        "</div>"
        f'<div class="bar-value">{html.escape(displayed)}</div>'
        "</div>"
    )


def paired_scatter_svg(rows: list[dict[str, Any]]) -> str:
    width, height = 680, 330
    left, right, top, bottom = 72, 28, 24, 54
    x_min, x_max = 0.88, 1.005
    y_min, y_max = 0.65, 1.02

    def x_pos(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * (width - left - right)

    def y_pos(value: float) -> float:
        return height - bottom - (value - y_min) / (y_max - y_min) * (height - top - bottom)

    parts = [
        f'<svg class="scatter" viewBox="0 0 {width} {height}" role="img" aria-label="Service simule des deux produits pour dix graines">',
        '<rect x="0" y="0" width="100%" height="100%" rx="16" fill="#f8fafc"/>',
    ]
    for tick in (0.90, 0.93, 0.96, 1.00):
        x = x_pos(tick)
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height-bottom}" stroke="#d9e2ec"/>')
        parts.append(f'<text x="{x:.1f}" y="{height-23}" text-anchor="middle" class="axis">{100*tick:.0f}%</text>')
    for tick in (0.70, 0.80, 0.90, 1.00):
        y = y_pos(tick)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#d9e2ec"/>')
        parts.append(f'<text x="{left-13}" y="{y+4:.1f}" text-anchor="end" class="axis">{100*tick:.0f}%</text>')
    target_x, target_y = x_pos(0.93), y_pos(0.80)
    parts.extend(
        [
            f'<line x1="{target_x-9:.1f}" y1="{target_y:.1f}" x2="{target_x+9:.1f}" y2="{target_y:.1f}" stroke="#dc2626" stroke-width="3"/>',
            f'<line x1="{target_x:.1f}" y1="{target_y-9:.1f}" x2="{target_x:.1f}" y2="{target_y+9:.1f}" stroke="#dc2626" stroke-width="3"/>',
            f'<text x="{target_x+13:.1f}" y="{target_y-10:.1f}" class="target-label">cible demandee</text>',
        ]
    )
    colors = {"physical_nominal": "#64748b", "target_hypothesis": "#2563eb"}
    for row in rows:
        variant = str(row.get("variant") or "")
        x = x_pos(to_float(row.get("fill_268091")))
        y = y_pos(to_float(row.get("fill_268967")))
        color = colors.get(variant, "#0f766e")
        title = html.escape(
            f"{variant}, graine {row.get('seed')}: 268091 {fr_percent(row.get('fill_268091'), 2)}, 268967 {fr_percent(row.get('fill_268967'), 2)}"
        )
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{color}" fill-opacity="0.78"><title>{title}</title></circle>')
    parts.extend(
        [
            f'<text x="{(left+width-right)/2:.1f}" y="{height-3}" text-anchor="middle" class="axis-title">Service volumique 268091</text>',
            f'<text x="15" y="{(top+height-bottom)/2:.1f}" text-anchor="middle" transform="rotate(-90 15 {(top+height-bottom)/2:.1f})" class="axis-title">Service volumique 268967</text>',
            "</svg>",
        ]
    )
    return "".join(parts)


def response_curve_svg(rows: list[dict[str, Any]], lever: str, target: float) -> str:
    selected = [row for row in rows if row["lever"] == lever]
    if not selected:
        return ""
    width, height = 570, 245
    left, right, top, bottom = 54, 20, 20, 44
    x_values = [to_float(row["level"]) for row in selected]
    x_min, x_max = min(x_values), max(x_values)
    if abs(x_max - x_min) < 1e-12:
        x_max = x_min + 1.0
    y_min = min(0.65, min(to_float(row["fill_rate"]) for row in selected) - 0.03)
    y_max = 1.01

    def xp(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * (width - left - right)

    def yp(value: float) -> float:
        return height - bottom - (value - y_min) / (y_max - y_min) * (height - top - bottom)

    points = " ".join(
        f"{xp(to_float(row['level'])):.1f},{yp(to_float(row['fill_rate'])):.1f}"
        for row in selected
    )
    due_points = " ".join(
        f"{xp(to_float(row['level'])):.1f},{yp(to_float(row['on_due_date_volume_proxy'])):.1f}"
        for row in selected
    )
    parts = [
        f'<svg class="curve" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(lever)}">',
        '<rect width="100%" height="100%" rx="14" fill="#f8fafc"/>',
    ]
    for tick in (0.70, 0.80, 0.90, 1.00):
        if tick < y_min:
            continue
        y = yp(tick)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#d9e2ec"/>')
        parts.append(f'<text x="{left-9}" y="{y+4:.1f}" text-anchor="end" class="axis">{tick*100:.0f}%</text>')
    target_y = yp(target)
    parts.append(f'<line x1="{left}" y1="{target_y:.1f}" x2="{width-right}" y2="{target_y:.1f}" stroke="#dc2626" stroke-dasharray="5 4"/>')
    parts.append(f'<polyline points="{points}" fill="none" stroke="#2563eb" stroke-width="3"/>')
    parts.append(f'<polyline points="{due_points}" fill="none" stroke="#0f766e" stroke-width="2" stroke-dasharray="4 3"/>')
    for row in selected:
        x = xp(to_float(row["level"]))
        y = yp(to_float(row["fill_rate"]))
        title = html.escape(
            f"niveau {fr_number(row['level'], 2)}: horizon {fr_percent(row['fill_rate'], 2)}, a date {fr_percent(row['on_due_date_volume_proxy'], 2)}"
        )
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#2563eb"><title>{title}</title></circle>')
    for tick in (x_min, x_max) if len(selected) > 1 else (x_min,):
        x = xp(tick)
        decimals = 0 if selected[0]["level_unit"] == "unites" else 2
        parts.append(f'<text x="{x:.1f}" y="{height-17}" text-anchor="middle" class="axis">{fr_number(tick, decimals)}</text>')
    parts.append(f'<text x="{width/2:.1f}" y="{height-2}" text-anchor="middle" class="axis-title">{html.escape(selected[0]["level_unit"])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def report_html(payload: dict[str, Any]) -> str:
    real_rows = {row["product"]: row for row in payload["real_2025"]["products"]}
    sensitivity = payload["sensitivity"]
    paired = payload["paired_replays"]
    suppliers = payload["suppliers"]
    cascades = payload["cascades"]
    response_curves = payload["response_curves"]
    quality = cascades["quality"]
    delay = cascades["delay"]
    target = payload["target_analysis"]
    navigation = payload["navigation"]
    stress_view = navigation["aligned_stress_tests"]
    network_view = navigation["network_lot_map"]
    lot_impact_view = navigation.get("incident_lot_explorer") or stress_view
    quality_map_view = navigation.get("quality_incident_lot_map")
    delay_map_view = navigation.get("delay_incident_lot_map")
    aligned_map_buttons = "".join(
        f'<a class="launch-button primary" href="{html.escape(view["href"], quote=True)}" target="_blank" rel="noopener">{html.escape(label)}</a>'
        for view, label in (
            (quality_map_view, "Carte qualite + lots"),
            (delay_map_view, "Carte retard 338929 + lots"),
        )
        if view
    )
    aligned_map_cards = "".join(
        '<article class="launch-card"><span class="badge simulated">Meme simulation</span>'
        f'<h3>{html.escape(title)}</h3><p>{html.escape(description)}</p>'
        f'<a class="launch-button primary" href="{html.escape(view["href"], quote=True)}" target="_blank" rel="noopener">Ouvrir la carte et ses lots</a></article>'
        for view, title, description in (
            (
                quality_map_view,
                "Carte de la retenue qualite",
                "La cascade qualite et le suivi de lots utilisent exactement la meme realisation detaillee.",
            ),
            (
                delay_map_view,
                "Carte du retard 338929",
                "Le retard fournisseur, ses flux et les lots aval utilisent exactement la meme realisation detaillee.",
            ),
        )
        if view
    )
    lead_case = target["268091"].get("closest_lead_case") or {}
    lower = target["268967"].get("capacity_only_lower_bracket") or {}
    upper = target["268967"].get("capacity_only_upper_bracket") or {}
    demand_case = target["268967"].get("closest_demand_stress_case") or {}
    nominal = paired.get("variants", {}).get("physical_nominal", {})
    hypothesis = paired.get("variants", {}).get("target_hypothesis", {})

    ca_bars = []
    max_ca = max(row["ca_potential_2025"] for row in real_rows.values())
    for product in ("268091", "268967"):
        row = real_rows[product]
        delivered_width = 100.0 * row["ca_delivered_2025"] / max_ca
        lost_width = 100.0 * row["ca_lost_2025"] / max_ca
        ca_bars.append(
            '<div class="stack-row">'
            f'<div class="stack-label"><strong>{product}</strong><span>{html.escape(row["family"])}</span></div>'
            '<div class="stack-track">'
            f'<div class="stack-delivered" style="width:{delivered_width:.3f}%"></div>'
            f'<div class="stack-lost" style="width:{lost_width:.3f}%"></div>'
            "</div>"
            f'<div class="stack-value">{compact_money(row["ca_delivered_2025"])} livre<br><b>{compact_money(row["ca_lost_2025"])} perdu</b></div>'
            "</div>"
        )

    stock_bars: list[str] = []
    max_stock = max(
        max(row["component_stock_mean_2025"], row["finished_goods_stock_mean_2025"])
        for row in real_rows.values()
    )
    for product in ("268091", "268967"):
        row = real_rows[product]
        stock_bars.append(
            html_bar(
                f"{product} - composants",
                row["component_stock_mean_2025"],
                max_stock,
                compact_money(row["component_stock_mean_2025"]),
                "#0f766e",
            )
        )
        stock_bars.append(
            html_bar(
                f"{product} - produits finis",
                row["finished_goods_stock_mean_2025"],
                max_stock,
                compact_money(row["finished_goods_stock_mean_2025"]),
                "#38bdf8",
            )
        )

    service_rows = [
        ("268091 - service CA observe", real_rows["268091"]["ca_service_rate"], "#0f766e"),
        ("268091 - objectif demande", 0.93, "#dc2626"),
        ("268091 - hypothese, moyenne 10 graines", hypothesis.get("fill_268091_mean", math.nan), "#2563eb"),
        ("268967 - service CA observe", real_rows["268967"]["ca_service_rate"], "#0f766e"),
        ("268967 - objectif demande", 0.80, "#dc2626"),
        ("268967 - hypothese, moyenne 10 graines", hypothesis.get("fill_268967_mean", math.nan), "#2563eb"),
    ]
    service_bars = "".join(
        html_bar(label, value if math.isfinite(to_float(value, math.nan)) else 0.0, 1.0, fr_percent(value, 1), color)
        for label, value, color in service_rows
    )

    top_levers = [
        row for row in sensitivity["ranking"] if row["maximum_fill_drop"] > 1e-9
    ][:12]
    max_drop = max((row["maximum_fill_drop"] for row in top_levers), default=1.0)
    lever_bars = "".join(
        html_bar(
            str(row["parameter_label"]),
            row["maximum_fill_drop"],
            max_drop,
            f"-{fr_percent(row['maximum_fill_drop'], 1)}",
            "#f97316" if index < 4 else "#f59e0b",
        )
        for index, row in enumerate(top_levers)
    )
    curve_specs = [
        ("Capacites fournisseurs vers M-1430", 0.80),
        ("Delai du composant 338929", 0.93),
        ("Stock fournisseur cible du 338929", 0.93),
        ("Capacite de production M-1810", 0.93),
    ]
    curve_cards = "".join(
        '<div class="curve-card">'
        f'<h3>{html.escape(lever)}</h3>'
        f'{response_curve_svg(response_curves, lever, target_value)}'
        "</div>"
        for lever, target_value in curve_specs
        if any(row["lever"] == lever for row in response_curves)
    )
    stock_gap_268091 = (
        to_float(nominal.get("component_stock_sim_268091_mean"))
        / real_rows["268091"]["component_stock_mean_2025"]
        - 1.0
    )
    stock_gap_268967 = (
        to_float(nominal.get("component_stock_sim_268967_mean"))
        / real_rows["268967"]["component_stock_mean_2025"]
        - 1.0
    )

    supplier_rows = []
    for row in suppliers["rows"][:15]:
        consequence = (
            fr_percent(row["conditional_fill_drop_tested"], 1)
            if row["conditional_consequence_tested"]
            else "non teste"
        )
        coverage = (
            f"{fr_number(row['stock_coverage_days'], 0)} j"
            if row["stock_coverage_days"] is not None
            else "n.d."
        )
        supplier_rows.append(
            "<tr>"
            f"<td><strong>{html.escape(row['supplier_id'])}</strong><small>{html.escape(row['supplier_name'])}</small></td>"
            f"<td>{html.escape(row['item_id'].replace('item:', ''))}</td>"
            f"<td>{html.escape(row['product'] or 'a rapprocher')}</td>"
            f"<td>{fr_percent(row['occurrence_indicator_proxy_4w'], 1)}</td>"
            f"<td>{consequence}</td>"
            f"<td>{fr_number(row['lead_days_q90'], 0)} j</td>"
            f"<td>{coverage}</td>"
            "</tr>"
        )
    focus_reasons = {
        "item:338929": (
            "Composant mono-source au coeur du demonstrateur retard; verifier OTIF, capacite, stock cible et solution de secours."
        ),
        "item:344135": (
            "Premier composant liant observe dans le stress de capacite M-1430; confirmer capacite reelle, MOQ et calendrier de lots."
        ),
        "item:333362": (
            "Mono-source avec le signal proxy quatre semaines le plus eleve de la selection Pharma; collecter historique et plan de continuite."
        ),
    }
    focus_cards: list[str] = []
    for item, reason in focus_reasons.items():
        row = next((candidate for candidate in suppliers["rows"] if candidate["item_id"] == item), None)
        if row is None:
            continue
        focus_cards.append(
            '<div class="card">'
            f'<div class="kpi">{html.escape(item.replace("item:", ""))}</div>'
            f'<p><strong>{html.escape(row["supplier_id"])}</strong> — signal proxy {fr_percent(row["occurrence_indicator_proxy_4w"],1)}.</p>'
            f'<p>{html.escape(reason)}</p>'
            "</div>"
        )

    matrix_dots: list[str] = []
    tested_rows = [
        row
        for row in suppliers["rows"]
        if row["conditional_consequence_tested"]
        and row["occurrence_indicator_proxy_4w"] is not None
    ]
    max_consequence = max(
        (to_float(row["conditional_fill_drop_tested"]) for row in tested_rows),
        default=1.0,
    )
    for index, row in enumerate(tested_rows):
        x = min(98.0, max(2.0, 100.0 * to_float(row["occurrence_indicator_proxy_4w"])))
        y = min(96.0, max(3.0, 92.0 * to_float(row["conditional_fill_drop_tested"]) / max(1e-9, max_consequence)))
        label = html.escape(f"{row['supplier_id']} / {row['item_id'].replace('item:', '')}")
        title = html.escape(
            f"{label}: signal proxy {fr_percent(row['occurrence_indicator_proxy_4w'], 1)}, baisse conditionnelle {fr_percent(row['conditional_fill_drop_tested'], 1)}"
        )
        matrix_dots.append(
            f'<span class="matrix-dot" style="left:{x:.2f}%;bottom:{y:.2f}%;--dot:{index % 6}" title="{title}"></span>'
        )

    mc = payload["monte_carlo"]["active"]
    range_left = 100.0 * to_float(mc["fill_p05"])
    range_right = 100.0 * to_float(mc["fill_p95"])
    median_pos = 100.0 * to_float(mc["fill_p50"])
    mean_pos = 100.0 * to_float(mc["fill_mean"])

    quality_timeline = quality.get("conditional_impact_timeline") or {}
    delay_timeline = delay.get("conditional_impact_timeline") or {}
    scatter = paired_scatter_svg(paired.get("rows", [])) if paired.get("available") else ""

    style = """
    :root{--ink:#0b1f3a;--muted:#52667e;--line:#d9e3ee;--panel:#fff;--bg:#f1f5f9;--blue:#2563eb;--teal:#0f766e;--red:#dc2626;--amber:#f59e0b}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,Segoe UI,Arial,sans-serif;line-height:1.5}a{color:inherit}.wrap{max-width:1240px;margin:auto;padding:0 24px 64px}.hero{background:linear-gradient(135deg,#081f3b,#123e70 60%,#0f766e);color:white;padding:46px 0 38px}.hero h1{font-size:clamp(2rem,4vw,3.5rem);line-height:1.02;margin:0 0 14px}.hero p{max-width:900px;font-size:1.12rem;color:#dbeafe;margin:0}.hero-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}.launch-button{display:inline-flex;align-items:center;justify-content:center;text-decoration:none;border-radius:999px;padding:11px 17px;font-weight:800;border:1px solid #cbd5e1;background:#fff;color:#123e70}.launch-button.primary{background:#22c55e;border-color:#22c55e;color:#052e16}.launch-button.secondary{background:#e0f2fe;border-color:#bae6fd;color:#075985}.launch-button:hover{filter:brightness(.96);transform:translateY(-1px)}.nav{position:sticky;top:0;z-index:5;background:rgba(255,255,255,.94);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);overflow:auto;white-space:nowrap}.nav .wrap{padding:10px 24px}.nav a{display:inline-block;text-decoration:none;padding:7px 12px;border-radius:18px;color:#24425f}.nav a:hover{background:#e2e8f0}section{scroll-margin-top:64px;margin-top:28px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:24px;box-shadow:0 12px 35px rgba(15,23,42,.05)}.grid{display:grid;gap:16px}.grid.cards{grid-template-columns:repeat(auto-fit,minmax(210px,1fr));margin-top:22px}.card{background:#fff;color:var(--ink);border:1px solid rgba(255,255,255,.55);border-radius:16px;padding:18px}.card .kpi{font-size:1.8rem;font-weight:800;line-height:1.1}.card p{margin:7px 0 0;color:var(--muted);font-size:.92rem}.hero .card{background:rgba(255,255,255,.96)}h2{font-size:1.65rem;margin:0 0 8px}h3{margin:22px 0 8px}.lead{color:var(--muted);max-width:920px}.badges{display:flex;flex-wrap:wrap;gap:8px;margin:17px 0}.badge{font-size:.75rem;font-weight:750;letter-spacing:.03em;text-transform:uppercase;padding:5px 9px;border-radius:999px}.observed{background:#dcfce7;color:#166534}.simulated{background:#dbeafe;color:#1d4ed8}.proxy{background:#fef3c7;color:#92400e}.hypothesis{background:#fee2e2;color:#991b1b}.verdict{border-left:5px solid var(--blue);background:#eff6ff;padding:16px 18px;border-radius:10px;margin:18px 0}.warning{border-left:5px solid var(--amber);background:#fffbeb;padding:14px 17px;border-radius:10px;margin:16px 0}.launch-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}.launch-card{border:1px solid var(--line);border-radius:16px;padding:18px;background:#f8fafc}.launch-card h3{margin:10px 0 6px}.launch-card p{color:var(--muted);min-height:72px}.launch-card .launch-button{margin-top:6px}.stack-row,.bar-row{display:grid;grid-template-columns:minmax(160px,1.2fr) minmax(220px,3fr) minmax(125px,1fr);gap:12px;align-items:center;margin:12px 0}.stack-label span,.supplier-table small{display:block;color:var(--muted);font-size:.78rem}.stack-track,.bar-track{height:17px;background:#e8eef5;border-radius:999px;display:flex;overflow:hidden}.stack-delivered{background:#0f766e}.stack-lost{background:#ef4444}.stack-value,.bar-value{text-align:right;font-size:.84rem}.stack-value b{color:#b91c1c}.bar-label{font-size:.87rem}.bar-fill{height:100%;min-width:2px;border-radius:999px}.split{display:grid;grid-template-columns:1fr 1fr;gap:18px}.metric-note{font-size:.83rem;color:var(--muted)}table{width:100%;border-collapse:collapse;font-size:.86rem}th,td{text-align:left;padding:10px 9px;border-bottom:1px solid var(--line);vertical-align:top}th{color:#36536f;background:#f8fafc;position:sticky;top:46px}.table-wrap{overflow:auto}.range{position:relative;height:80px;margin:28px 12px 8px}.range-axis{position:absolute;left:0;right:0;top:35px;height:8px;background:#e2e8f0;border-radius:999px}.range-band{position:absolute;top:35px;height:8px;background:#60a5fa;border-radius:999px}.range-mark{position:absolute;top:25px;width:3px;height:29px;background:#0f172a}.range-mark.mean{background:#dc2626}.range-label{position:absolute;top:57px;transform:translateX(-50%);font-size:.75rem}.matrix{height:310px;position:relative;margin:28px 10px 44px 48px;border-left:2px solid #94a3b8;border-bottom:2px solid #94a3b8;background:linear-gradient(135deg,#ecfdf5,#fff7ed)}.matrix:before{content:'gravite conditionnelle simulee';position:absolute;left:-44px;top:50%;transform:translate(-50%,-50%) rotate(-90deg);font-size:.76rem;color:var(--muted)}.matrix:after{content:'signal d alerte proxy →';position:absolute;left:50%;bottom:-31px;transform:translateX(-50%);font-size:.76rem;color:var(--muted)}.matrix-dot{position:absolute;width:11px;height:11px;border-radius:50%;background:hsl(calc(205 + var(--dot)*18),70%,45%);border:2px solid white;box-shadow:0 0 0 1px rgba(15,23,42,.25)}.timeline{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:18px 0}.step{background:#f8fafc;border:1px solid var(--line);padding:13px;border-radius:12px;text-align:center}.step b{display:block;font-size:1.2rem}.actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}.action{border:1px solid var(--line);border-radius:12px;padding:14px}.action.good{border-color:#86efac;background:#f0fdf4}.action.warn{border-color:#fdba74;background:#fff7ed}.flow{display:flex;align-items:stretch;gap:7px;overflow:auto;padding:12px 0}.flow-box{min-width:132px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:12px;padding:13px;text-align:center;font-size:.83rem}.arrow{align-self:center;color:#64748b;font-size:1.4rem}.scatter,.curve{width:100%;max-height:390px}.curves{display:grid;grid-template-columns:1fr 1fr;gap:14px}.curve-card{border:1px solid var(--line);border-radius:14px;padding:12px}.curve-card h3{margin:3px 7px 7px;font-size:1rem}.axis{fill:#64748b;font:12px Segoe UI,Arial}.axis-title{fill:#334155;font:600 13px Segoe UI,Arial}.target-label{fill:#b91c1c;font:600 12px Segoe UI,Arial}.source-note{font-size:.76rem;color:#64748b;margin-top:22px}.footer{margin-top:30px;color:#64748b;font-size:.8rem}.two-axis{display:grid;grid-template-columns:1fr 1fr;gap:14px}.axis-card{border-radius:13px;padding:15px}.axis-card.proxy-card{background:#fffbeb;border:1px solid #fde68a}.axis-card.impact-card{background:#eff6ff;border:1px solid #bfdbfe}@media(max-width:800px){.split,.two-axis,.curves,.launch-grid{grid-template-columns:1fr}.stack-row,.bar-row{grid-template-columns:1fr}.stack-value,.bar-value{text-align:left}.timeline{grid-template-columns:1fr 1fr}.launch-card p{min-height:0}.wrap{padding-left:14px;padding-right:14px}th{position:static}}
    """
    body = f"""
    <header class="hero"><div class="wrap">
      <h1>De l'alerte fournisseur a la decision</h1>
      <p>Quels fournisseurs peuvent fragiliser la supply, quels lots et clients seraient exposes, et quelle action protege le mieux l'activite ?</p>
      <div class="badges"><span class="badge observed">Observe 2025</span><span class="badge simulated">Simule si l'incident survient</span><span class="badge proxy">Indicateur proxy</span><span class="badge hypothesis">Hypothese a valider</span></div>
      <div class="grid cards">
        <div class="card"><div class="kpi">{compact_money(payload['real_2025']['total_ca_lost_2025'])}</div><p>CA perdu declare en 2025, deux produits</p></div>
        <div class="card"><div class="kpi">{fr_percent(real_rows['268091']['ca_service_rate'],2)}</div><p>Service calcule sur le CA du 268091</p></div>
        <div class="card"><div class="kpi">{fr_percent(real_rows['268967']['ca_service_rate'],2)}</div><p>Service calcule sur le CA du 268967</p></div>
        <div class="card"><div class="kpi">Impact oui<br>occurrence non</div><p>La propagation est simulee; la probabilite fournisseur n'est pas encore calibree</p></div>
      </div>
      <div class="hero-actions">{aligned_map_buttons}<a class="launch-button secondary" href="{html.escape(lot_impact_view['href'], quote=True)}" target="_blank" rel="noopener">Comparer normal, incident et solution (estimation)</a><a class="launch-button secondary" href="{html.escape(stress_view['href'], quote=True)}" target="_blank" rel="noopener">Voir les courbes des stress tests</a><a class="launch-button secondary" href="{html.escape(network_view['href'], quote=True)}" target="_blank" rel="noopener">Explorer la carte historique</a></div>
    </div></header>
    <nav class="nav"><div class="wrap"><a href="#access">Acces aux vues</a><a href="#bilan">Bilan 2025</a><a href="#cibles">80 / 93</a><a href="#leviers">Leviers</a><a href="#fournisseurs">Fournisseurs</a><a href="#cascades">Cascades</a><a href="#lots">Lots</a><a href="#suite">Suite</a></div></nav>
    <main class="wrap">
      <section><div class="panel">
        <h2>Ce que l'on sait aujourd'hui</h2>
        <div class="verdict"><strong>Le modele sait deja calculer la consequence aval d'un incident fournisseur impose.</strong> Il peut suivre les stocks, la production, le retard client et les lots simules. Il ne sait pas encore estimer la probabilite reelle d'apparition de l'incident, car l'historique de performance fournisseur n'est pas dans les donnees.</div>
        <p class="lead">Le fil rouge defendable est : <b>signal fournisseur → incident → composants et lots exposes → production → clients et CA menaces → solutions → jours recuperes, cout et risque restant.</b></p>
      </div></section>

      <section id="access"><div class="panel">
        <h2>Ouvrir la bonne vue sans melanger les simulations</h2>
        <p class="lead">Les vues prioritaires relient maintenant la carte et le suivi de lots à la même simulation d'incident. La carte historique reste disponible séparément.</p>
        <div class="launch-grid">
          {aligned_map_cards}
          <article class="launch-card"><span class="badge proxy">Comparaison estimée</span><h3>Comparer trois futurs simulés</h3><p>Cette vue compare fonctionnement normal, incident et transport accéléré. Les 22/180 lots du registre sont attribués quantitativement, mais leurs jours sont rapprochés par ordre de production : ce ne sont pas les mêmes lots physiques entre les futurs.</p><a class="launch-button secondary" href="{html.escape(lot_impact_view['href'], quote=True)}" target="_blank" rel="noopener">Ouvrir la comparaison estimée</a></article>
          <article class="launch-card"><span class="badge simulated">Donnees alignees</span><h3>Stress tests, courbes et effets sur les lots</h3><p>Les memes dix repetitions et les memes deux incidents que dans cette synthese : retenue qualite et retard du composant 338929.</p><a class="launch-button primary" href="{html.escape(stress_view['href'], quote=True)}" target="_blank" rel="noopener">Ouvrir les resultats detailles</a></article>
          <article class="launch-card"><span class="badge proxy">Run historique distinct</span><h3>Ancienne carte interactive du reseau</h3><p>{fr_number(network_view['lot_count'],0)} lots, {fr_number(network_view['event_count'],0)} evenements et {fr_number(network_view['genealogy_count'],0)} liens de genealogie dans le run state-dependent historique de 365 jours.</p><a class="launch-button secondary" href="{html.escape(network_view['href'], quote=True)}" target="_blank" rel="noopener">Ouvrir l'ancienne carte</a></article>
        </div>
        <div class="warning"><strong>Point de rigueur :</strong> dans chaque nouvelle carte, l'incident, les flux et les lots proviennent exactement du même run détaillé seed 330281. La comparaison entre fonctionnement normal, incident et solution reste une comparaison entre futurs simulés distincts.</div>
        <p class="metric-note">Paquet de navigation leger : aucun CSV scientifique de 1,79 Go n'est copie ni charge par ces vues.</p>
      </div></section>

      <section id="bilan"><div class="panel">
        <span class="badge observed">Observe 2025</span><h2>Bilan factuel : CA et stocks</h2>
        <p class="lead">Les montants ci-dessous viennent des fichiers de l'industriel. Ils sont disponibles au niveau produit, sans fournisseur ni lot.</p>
        <h3>CA livre et CA perdu</h3>{''.join(ca_bars)}
        <h3>Stocks hebdomadaires moyens</h3>{''.join(stock_bars)}
        <div class="warning"><strong>Limite :</strong> les fichiers financiers sont interpretes comme des euros, mais la devise doit etre confirmee. Une correction de -45,86 apparait le 9 octobre 2025 sur le 268091.</div>
      </div></section>

      <section id="cibles"><div class="panel">
        <span class="badge hypothesis">Hypothese a valider</span><h2>Pourquoi 80 % et 93 % ne sont pas encore une baseline prouvee</h2>
        <p class="lead">Trois mesures differentes coexistent : le service calcule sur le CA, le volume finalement servi dans la simulation, et un proxy du volume servi le jour demande. L'OTIF par commande n'est pas disponible.</p>
        {service_bars}
        <div class="split">
          <div><h3>268091 / objectif 93 %</h3><p>Le cas le plus proche agit sur le delai du composant mono-source 338929 : <b>{fr_percent(lead_case.get('fill_268091'),2)}</b> de service horizon, mais <b>{fr_percent(lead_case.get('on_due_date_volume_proxy_268091'),2)}</b> sur le proxy servi a date. La reponse est non monotone a cause des lots et du calendrier.</p></div>
          <div><h3>268967 / objectif 80 %</h3><p>Avec demande fixe, la capacite seule encadre 80 % entre <b>{fr_percent(lower.get('fill_268967'),2)}</b> et <b>{fr_percent(upper.get('fill_268967'),2)}</b>. Un lot fixe de 107 800 unites represente environ 6,84 points annuels. Le cas a {fr_percent(demand_case.get('fill_268967'),2)} inclut +4 % de demande : c'est un stress, pas une calibration pure.</p></div>
        </div>
        <h3>Dix rejeux apparies de l'hypothese cible</h3>
        {scatter}
        <p class="metric-note">Gris : plancher physique infere. Bleu : hypothese delai 338929 x0,88 + capacites fournisseurs M-1430 x0,20 + demande 268967 x1,04. Rouge : valeurs demandees 93/80. Les dix graines explorent les delais aleatoires; elles ne mesurent pas une probabilite industrielle.</p>
        <div class="grid cards">
          <div class="card"><div class="kpi">{fr_percent(hypothesis.get('fill_268091_mean'),2)}</div><p>268091, moyenne hypothese; {int(hypothesis.get('fill_268091_within_one_point_of_target',0))}/10 dans ±1 point</p></div>
          <div class="card"><div class="kpi">{fr_percent(hypothesis.get('fill_268967_mean'),2)}</div><p>268967, moyenne hypothese; plateau lotifie identique sur les dix graines</p></div>
          <div class="card"><div class="kpi">{fr_percent(nominal.get('fill_268091_mean'),2)}</div><p>268091 avec planchers physiques inferes, avant hypothese cible</p></div>
          <div class="card"><div class="kpi">{fr_percent(nominal.get('fill_268967_mean'),2)}</div><p>268967 avec planchers physiques inferes</p></div>
        </div>
        <h3>Controle croise sur les stocks composants 2025</h3>
        <div class="grid cards">
          <div class="card"><div class="kpi">{compact_money(nominal.get('component_stock_sim_268091_mean'))}</div><p>Proxy simule 268091 contre {compact_money(real_rows['268091']['component_stock_mean_2025'])} observe, ecart {fr_percent(stock_gap_268091,1)}.</p></div>
          <div class="card"><div class="kpi">{compact_money(nominal.get('component_stock_sim_268967_mean'))}</div><p>Proxy simule 268967 contre {compact_money(real_rows['268967']['component_stock_mean_2025'])} observe, ecart {fr_percent(stock_gap_268967,1)}.</p></div>
        </div>
        <p class="metric-note">Le proxy simule valorise l'exces de stock au-dessus de la cible MRP avec des prix fournisseurs medians. Sa proximite est encourageante, mais la definition finance de « stock immobilise » doit encore etre confirmee; l'article 693055 n'est pas valorise.</p>
      </div></section>

      <section id="leviers"><div class="panel">
        <span class="badge simulated">Screening simule</span><h2>Les leviers les plus influents</h2>
        <p class="lead">La capacite fournisseur domine lorsque les marges tombent sous un seuil. Le graphique montre la plus forte baisse de service global rencontree pour chaque levier teste.</p>
        <h3>Reponses locales par produit</h3>
        <div class="curves">{curve_cards}</div>
        <p class="metric-note">Bleu continu : volume finalement servi sur 365 jours. Vert pointille : proxy du volume servi le jour demande. Rouge : objectif demande. Les ruptures de pente et plateaux viennent notamment des tailles de lot.</p>
        <h3>Screening global cinq ans</h3>
        {lever_bars}
        <div class="warning"><strong>Lecture correcte :</strong> ce sont des stress un facteur a la fois sur une baseline a 100 % de service. Ils detectent des seuils et des falaises, mais ne constituent ni un classement causal Sobol ni une recommandation de reduction de capacite.</div>
        <h3>Enveloppe Monte-Carlo existante</h3>
        <div class="range"><div class="range-axis"></div><div class="range-band" style="left:{range_left:.2f}%;width:{max(0.0,range_right-range_left):.2f}%"></div><span class="range-mark" style="left:{median_pos:.2f}%"></span><span class="range-mark mean" style="left:{mean_pos:.2f}%"></span><span class="range-label" style="left:{range_left:.2f}%">P05 {fr_percent(mc['fill_p05'],1)}</span><span class="range-label" style="left:{median_pos:.2f}%">mediane {fr_percent(mc['fill_p50'],1)}</span><span class="range-label" style="left:{range_right:.2f}%">P95 {fr_percent(mc['fill_p95'],1)}</span></div>
        <p class="metric-note">Dix repetitions, environ {mc['factor_columns']} facteurs varies ensemble, horizon {mc['simulated_days']} jours. Suffisant pour illustrer une enveloppe de stress; insuffisant pour identifier statistiquement les causes.</p>
      </div></section>

      <section id="fournisseurs"><div class="panel">
        <span class="badge proxy">Proxy + consequence simulee</span><h2>Quels fournisseurs instruire en premier ?</h2>
        <div class="two-axis"><div class="axis-card proxy-card"><strong>Axe 1 — signal d'alerte</strong><p>Indicateur construit a partir des etats simules. Ce n'est pas une probabilite d'incident calibree.</p></div><div class="axis-card impact-card"><strong>Axe 2 — consequence si le choc survient</strong><p>Baisse de service conditionnelle dans un stress test. « Non teste » reste distinct de « aucun effet ».</p></div></div>
        <h3>Trois dossiers fournisseur-article a ouvrir maintenant</h3>
        <div class="grid cards">{''.join(focus_cards)}</div>
        <div class="matrix">{''.join(matrix_dots)}</div>
        <div class="table-wrap"><table class="supplier-table"><thead><tr><th>Fournisseur</th><th>Article</th><th>Produit</th><th>Signal proxy 4 sem.</th><th>Baisse conditionnelle</th><th>Delai Q90</th><th>Couverture</th></tr></thead><tbody>{''.join(supplier_rows)}</tbody></table></div>
        <div class="warning">La criticite proxy et la sensibilite proviennent de deux etudes dont la compatibilite de configuration n'est pas demontree. Cette vue sert a prioriser la collecte, pas a annoncer une perte attendue.</div>
      </div></section>

      <section id="cascades"><div class="panel">
        <span class="badge simulated">Deux demonstrateurs simules</span><h2>Si l'incident survient, jusqu'ou se propage-t-il ?</h2>
        <p class="lead">Ces cas ont ete choisis pour illustrer deux mecanismes complementaires. Ils ne sont ni des incidents historiques ni les risques les plus probables du reseau.</p>
        <h3>Retenue qualite — chaine 021081 → 773474 → 268967</h3>
        <div class="timeline"><div class="step"><span>Incident</span><b>J{quality_timeline.get('incident_start_day','?')}</b></div><div class="step"><span>Premier effet stock</span><b>J{quality_timeline.get('first_stock_effect_day','?')}</b></div><div class="step"><span>Production</span><b>J{quality_timeline.get('first_production_effect_day','?')}</b></div><div class="step"><span>Client</span><b>J{quality_timeline.get('first_customer_backlog_day','?')}</b></div></div>
        <p>L'effet client apparait dans <b>{quality.get('customer_delay_count',0)}/{quality.get('simulation_count',0)}</b> repetitions. Le stock donne, dans ce stress test, environ {quality_timeline.get('stock_to_customer_interval_days','?')} jours de fenetre avant l'effet client.</p>
        <div class="actions"><div class="action good"><strong>Plan combine prepare</strong><p>{fr_number(quality.get('combined',{}).get('days_recovered'),0)} jours recuperes en moyenne dans les cas touches; {fr_percent(quality.get('combined',{}).get('remaining_ratio'),1)} du retard reste.</p></div><div class="action"><strong>Transport accelere</strong><p>{fr_number(quality.get('expedited',{}).get('days_recovered'),1)} jours recuperes; cout plus faible, mais une repetition est aggravee de 16 jours.</p></div></div>
        <h3>Retard 338929 → M-1810 → 268091</h3>
        <div class="timeline"><div class="step"><span>Incident</span><b>J{delay_timeline.get('incident_start_day','?')}</b></div><div class="step"><span>Premier effet stock</span><b>J{delay_timeline.get('first_stock_effect_day','?')}</b></div><div class="step"><span>Production</span><b>J{delay_timeline.get('first_production_effect_day','?')}</b></div><div class="step"><span>Client</span><b>J{delay_timeline.get('first_customer_backlog_day','?')}</b></div></div>
        <p>Le retard est absorbe avant le client dans <b>{delay.get('absorbed_count',0)}/{delay.get('simulation_count',0)}</b> repetitions. Une action declenchee seulement quand les protections deviennent insuffisantes peut donc etre plus pertinente qu'une depense permanente.</p>
        <div class="actions"><div class="action good"><strong>Transport accelere</strong><p>Retard client supprime dans les deux cas touches; {fr_number(delay.get('expedited',{}).get('days_recovered'),0)} jours recuperes; cout moyen {fr_number(delay.get('expedited',{}).get('incremental_cost'),0)} unites monetaires simulees.</p></div><div class="action"><strong>Plan combine</strong><p>Meme service teste, mais cout moyen {fr_number(delay.get('combined',{}).get('incremental_cost'),0)} : aucun gain supplementaire observe.</p></div><div class="action warn"><strong>Replanification proxy</strong><p>Retard multiplie par {fr_number(delay.get('replanning',{}).get('remaining_ratio'),2)}. Ce reglage doit etre rejete ou refait; il ne condamne pas une vraie replanification APS.</p></div></div>
      </div></section>

      <section id="lots"><div class="panel">
        <span class="badge simulated">Genealogie de lots simulee</span><h2>Suivre chaque lot, du fournisseur au client</h2>
        <div class="flow"><div class="flow-box">Evenement fournisseur</div><div class="arrow">→</div><div class="flow-box">Expedition / reception</div><div class="arrow">→</div><div class="flow-box">Stock composant</div><div class="arrow">→</div><div class="flow-box">Campagne / batch</div><div class="arrow">→</div><div class="flow-box">Lot produit fini</div><div class="arrow">→</div><div class="flow-box">Lot servi au client</div></div>
        <div class="grid cards"><div class="card"><div class="kpi">{quality.get('traceability_example',{}).get('finished_lot_count',0)} lots PF</div><p>268967 relies a la matiere exposee dans l'exemple qualite; {quality.get('traceability_example',{}).get('client_lot_count',0)} allocations de lots client.</p></div><div class="card"><div class="kpi">{delay.get('traceability_example',{}).get('finished_lot_count',0)} lots PF</div><p>268091 relies au flux 338929 expose; {delay.get('traceability_example',{}).get('client_lot_count',0)} allocations de lots client.</p></div></div>
        <div class="warning"><strong>Expose ne signifie pas retarde a cause de l'incident.</strong> Cela signifie que le flux de l'incident entre dans la genealogie. L'effet causal exige la comparaison normal / incident / action avec la meme graine. Les identifiants sont simules en FIFO, pas les vrais lots 2025.</div>
      </div></section>

      <section id="suite"><div class="panel">
        <h2>Le programme qui transforme ce prototype en outil industriel</h2>
        <ol><li><strong>Definir le KPI 80/93 :</strong> OTIF, ligne complete, quantite a date, volume rattrape ou service CA.</li><li><strong>Charger l'historique fournisseur :</strong> commande, date promise/reelle, ASN, lot, qualite, capacite et incidents.</li><li><strong>Calibrer sur plusieurs objectifs :</strong> 52 semaines de stocks, ruptures, backlog, service et CA perdu, en conservant plusieurs jeux de parametres plausibles.</li><li><strong>Quantifier les leviers :</strong> screening Morris groupe, puis analyse globale sur 8 a 12 facteurs et 500 a 1 000 simulations appariées.</li><li><strong>Passer aux vrais lots et vrais euros :</strong> WMS, OF/batches, commandes clients, marge, penalites et cout reel des actions.</li></ol>
        <div class="verdict"><strong>Proposition de valeur :</strong> ne pas seulement dire « ce fournisseur est a risque », mais montrer <b>quels composants, lots, productions, clients et euros proteger, par quelle action et avant quelle date</b>.</div>
        <p class="source-note">Paquet autonome genere le {html.escape(payload['generated_at_utc'])}. Les details techniques et la provenance sont disponibles dans les CSV, le JSON et le manifeste joints.</p>
      </div></section>
      <div class="footer">Etude de cas — resultats exploratoires. Aucune occurrence fournisseur ni cout industriel n'est presente comme calibre sans donnees historiques correspondantes.</div>
    </main>
    """
    return "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>De l'alerte fournisseur a la decision</title><style>" + style + "</style></head><body>" + body + "</body></html>"


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    artifact_root = args.artifact_root.resolve()
    output_dir = args.output_dir.resolve()
    calibration_root = args.calibration_root.resolve()
    network_map_html = args.network_map_html.resolve()
    network_map_plotly = args.network_map_plotly.resolve()
    network_map_topojson = args.network_map_topojson.resolve()
    stress_test_html = args.stress_test_html.resolve()
    quality_risk_map_html = (
        args.quality_risk_map_html.resolve() if args.quality_risk_map_html else None
    )
    delay_risk_map_html = (
        args.delay_risk_map_html.resolve() if args.delay_risk_map_html else None
    )
    graph_path = (
        repo_root
        / "etudecas"
        / "simulation_prep"
        / "result"
        / "reference_baseline"
        / "_mrp_bom_tests"
        / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
    )
    required = [
        repo_root,
        artifact_root,
        calibration_root,
        graph_path,
        network_map_html,
        network_map_plotly,
        network_map_topojson,
        stress_test_html,
        *(
            path
            for path in (quality_risk_map_html, delay_risk_map_html)
            if path is not None
        ),
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required input(s): " + ", ".join(missing))

    real = real_2025_metrics(repo_root)
    candidates = calibration_cases(calibration_root, graph_path, real)
    target_analysis = target_lever_analysis(candidates)
    response_curves = response_curve_rows(candidates)
    paired = paired_replay_summary(calibration_root, graph_path)
    sensitivity_rows, sensitivity_meta = sensitivity_ranking(repo_root)
    monte_carlo = monte_carlo_inventory(repo_root)
    suppliers = supplier_decision_table(repo_root, graph_path, sensitivity_rows)
    cascades = lot_and_cascade_summary(artifact_root)
    incident_lot_payload = build_incident_lot_payload(artifact_root)
    incident_lot_counts = {
        scenario["id"]: scenario["counts"]
        for scenario in incident_lot_payload["scenarios"]
    }
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload: dict[str, Any] = {
        "schema_version": "etudecas.supplier_risk_decision_brief.v2",
        "generated_at_utc": generated_at,
        "language": "fr",
        "purpose": "Relier faits 2025, leviers, fournisseurs, cascades, actions et lots sans confondre observation, simulation, proxy et hypothese.",
        "repo_root": str(repo_root),
        "artifact_root": str(artifact_root),
        "calibration_root": str(calibration_root),
        "graph": str(graph_path),
        "real_2025": real,
        "calibration_candidates": candidates,
        "response_curves": response_curves,
        "target_analysis": target_analysis,
        "paired_replays": paired,
        "sensitivity": {"meta": sensitivity_meta, "ranking": sensitivity_rows},
        "monte_carlo": monte_carlo,
        "suppliers": suppliers,
        "cascades": cascades,
        "navigation": {
            "incident_lot_explorer": {
                "href": f"{VIEWS_DIR_NAME}/{INCIDENT_LOT_HTML_OUTPUT_NAME}",
                "data_href": f"{VIEWS_DIR_NAME}/{INCIDENT_LOT_JSON_OUTPUT_NAME}",
                "alignment": "same_two_cascades_detailed_seed_330281_and_ten_repetition_summary",
                "map": False,
                "offline": True,
                "counts": incident_lot_counts,
            },
            **(
                {
                    "quality_incident_lot_map": {
                        "href": f"{VIEWS_DIR_NAME}/{QUALITY_RISK_MAP_OUTPUT_NAME}",
                        "source": str(quality_risk_map_html),
                        "source_sha256": sha256(quality_risk_map_html),
                        "alignment": "quality_incident_and_lots_same_run_seed_330281",
                        "map": True,
                        "offline": True,
                    }
                }
                if quality_risk_map_html is not None
                else {}
            ),
            **(
                {
                    "delay_incident_lot_map": {
                        "href": f"{VIEWS_DIR_NAME}/{DELAY_RISK_MAP_OUTPUT_NAME}",
                        "source": str(delay_risk_map_html),
                        "source_sha256": sha256(delay_risk_map_html),
                        "alignment": "delay_338929_incident_and_lots_same_run_seed_330281",
                        "map": True,
                        "offline": True,
                    }
                }
                if delay_risk_map_html is not None
                else {}
            ),
            "aligned_stress_tests": {
                "href": f"{VIEWS_DIR_NAME}/{STRESS_TEST_OUTPUT_NAME}",
                "source": str(stress_test_html),
                "source_sha256": sha256(stress_test_html),
                "alignment": "same_two_cascades_same_ten_repetitions",
                "map": False,
                "offline": True,
            },
            "network_lot_map": {
                "href": f"{VIEWS_DIR_NAME}/{NETWORK_MAP_OUTPUT_NAME}",
                "source": str(network_map_html),
                "source_sha256": sha256(network_map_html),
                "alignment": "distinct_365_day_state_dependent_run_seed_320270",
                "map": True,
                "offline": True,
                "lot_count": 3620,
                "event_count": 10489,
                "genealogy_count": 5194,
                "campaign_count": 136,
                "traceable_lot_count": 357,
            },
        },
        "excluded_artifacts": [
            {
                "path": str(calibration_root / "paired_replays"),
                "status": "invalid_preparation_probe_preserved_not_used",
                "reason": "The first launcher scaled neutral capacity but not the tested capacity column preferred by the engine; M-1430 capacity was therefore unchanged.",
            },
            {
                "path": str(calibration_root / "oat2"),
                "status": "three_demand_probes_excluded",
                "reason": "Cases prefixed demand_ changed an unused top-level field rather than the nested demand profile.",
            },
        ],
        "core_conclusions": [
            "La capacite fournisseur presente des seuils non lineaires et domine le screening global lorsque la marge disparait.",
            "Le composant 338929, mono-source SDC-VD0914360C vers M-1810, est le levier local principal identifie pour 268091.",
            "Le composant 344135 est le premier manque liant dans le stress de capacite M-1430 pour 268967.",
            "Les cibles 80/93 ne peuvent pas etre declarees calibrees avant definition du KPI industriel.",
            "La probabilite d'incident fournisseur reste non calibree; la consequence conditionnelle et la genealogie de lots sont deja simulables.",
        ],
        "industrial_data_needed": [
            "Commandes fournisseurs avec date promise, date confirmee, date ASN et date de reception reelle.",
            "Identifiants de lots fournisseurs, statuts qualite, quarantaine, liberation et rebut.",
            "Stocks WMS par article, site, statut, age et lot.",
            "Ordres de fabrication, batches et consommations de lots.",
            "Commandes et livraisons clients, OTIF, CA, marge et penalites.",
            "Scorecards fournisseur, capacites, incidents, plans de continuite et criticite metier existante.",
        ],
    }
    payload["evidence_register"] = evidence_register(payload)

    output_dir.mkdir(parents=True, exist_ok=True)
    bundled_view_paths = bundle_offline_views(
        output_dir,
        network_map_html=network_map_html,
        network_map_plotly=network_map_plotly,
        network_map_topojson=network_map_topojson,
        stress_test_html=stress_test_html,
        quality_risk_map_html=quality_risk_map_html,
        delay_risk_map_html=delay_risk_map_html,
    )
    incident_lot_paths, _ = write_incident_lot_explorer(
        output_dir / VIEWS_DIR_NAME,
        artifact_root,
        payload=incident_lot_payload,
    )
    observed_path = output_dir / "observed_2025.csv"
    calibration_path = output_dir / "calibration_hypotheses.csv"
    paired_path = output_dir / "paired_replays_v2.csv"
    response_path = output_dir / "product_lever_response_curves.csv"
    sensitivity_path = output_dir / "lever_sensitivity_ranking.csv"
    suppliers_path = output_dir / "supplier_priority_two_axes.csv"
    evidence_path = output_dir / "evidence_register.csv"
    json_path = output_dir / "supplier_risk_decision_brief.json"
    markdown_path = output_dir / "supplier_risk_decision_brief.md"
    html_path = output_dir / "index.html"

    write_csv(observed_path, real["products"])
    write_csv(calibration_path, candidates)
    write_csv(paired_path, paired.get("rows", []))
    write_csv(response_path, response_curves)
    write_csv(sensitivity_path, sensitivity_rows)
    write_csv(suppliers_path, suppliers["rows"])
    write_csv(evidence_path, payload["evidence_register"])
    write_json(json_path, payload)
    markdown_path.write_text(report_markdown(payload), encoding="utf-8")
    html_path.write_text(report_html(payload), encoding="utf-8")

    generated_files = [
        observed_path,
        calibration_path,
        paired_path,
        response_path,
        sensitivity_path,
        suppliers_path,
        evidence_path,
        json_path,
        markdown_path,
        html_path,
        *bundled_view_paths,
        *incident_lot_paths,
    ]
    manifest = {
        "schema_version": "etudecas.supplier_risk_decision_brief_manifest.v2",
        "generated_at_utc": generated_at,
        "output_dir": str(output_dir),
        "standalone_html": str(html_path),
        "historical_outputs_modified": False,
        "linked_views": payload["navigation"],
        "files": [
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in generated_files
        ],
        "key_inputs": [
            {"path": str(graph_path), "sha256": sha256(graph_path)},
            {"path": real["source"], "sha256": sha256(Path(real["source"]))},
            {
                "path": sensitivity_meta["source"],
                "sha256": sha256(Path(sensitivity_meta["source"])),
            },
            {"path": suppliers["source"], "sha256": sha256(Path(suppliers["source"]))},
            {"path": cascades["source"], "sha256": sha256(Path(cascades["source"]))},
            {"path": str(network_map_html), "sha256": sha256(network_map_html)},
            {"path": str(network_map_plotly), "sha256": sha256(network_map_plotly)},
            {"path": str(network_map_topojson), "sha256": sha256(network_map_topojson)},
            {"path": str(stress_test_html), "sha256": sha256(stress_test_html)},
            *[
                {"path": str(path), "sha256": sha256(path)}
                for path in (quality_risk_map_html, delay_risk_map_html)
                if path is not None
            ],
            {
                "path": str(
                    Path(incident_lot_payload["sources"]["full_trace"])
                    / "canonical_cascade_runs.csv"
                ),
                "sha256": sha256(
                    Path(incident_lot_payload["sources"]["full_trace"])
                    / "canonical_cascade_runs.csv"
                ),
            },
            *[
                {
                    "path": str(
                        Path(incident_lot_payload["sources"][source_key])
                        / "risk_impact_quality.json"
                    ),
                    "sha256": sha256(
                        Path(incident_lot_payload["sources"][source_key])
                        / "risk_impact_quality.json"
                    ),
                }
                for source_key in ("quality_registry", "delay_registry")
            ],
        ],
        "total_generated_bytes_excluding_manifest": sum(
            path.stat().st_size for path in generated_files
        ),
    }
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    print(f"[OK] Standalone brief: {html_path}")
    print(f"[OK] Markdown report: {markdown_path}")
    print(f"[OK] Structured results: {json_path}")
    print(
        "[OK] Lightweight package bytes: "
        f"{sum(path.stat().st_size for path in [*generated_files, manifest_path])}"
    )


if __name__ == "__main__":
    main()
