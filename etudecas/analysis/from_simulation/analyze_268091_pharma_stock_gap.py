"""Detailed gap analysis for 268091 Cos immobilized component stock."""

from __future__ import annotations

import csv
import json
import statistics
from datetime import date, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_DIR = (
    REPO_ROOT
    / "etudecas"
    / "simulation"
    / "result"
    / "_reruns"
    / "active_mrp_physical_state_dependent_5y_20260702_213259"
)
GRAPH_PATH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
SOURCE_DIR = REPO_ROOT / "etudecas" / "data" / "source"
REPORT_DIR = RUN_DIR / "reports" / "cos_268091_gap"
START_DATE = date(2025, 1, 1)
PRODUCT_CODE = "268091"
FACTORY = "M-1810"

THRESHOLD_MODES = (
    "target_stock",
    "coverage",
    "safety_plus_coverage",
    "demand_90d",
    "demand_180d",
)


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def source_file(pattern: str) -> Path:
    matches = sorted(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one file for {pattern}, found {matches}")
    return matches[0]


def read_csv_dicts(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with path.open(encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle, delimiter=delimiter))
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def read_real_pharma_stock() -> list[dict[str, Any]]:
    path = source_file("Stock_Composants*_Cos.csv")
    rows: list[dict[str, Any]] = []
    for row in read_csv_dicts(path, delimiter=";"):
        snapshot_date = datetime.fromisoformat(row["Date de photo DMP"]).date()
        rows.append(
            {
                "date": snapshot_date.isoformat(),
                "day": (snapshot_date - START_DATE).days,
                "real_component_immobilized_value": parse_float(row["Sum_Valeur totale du stock"]),
            }
        )
    return [row for row in rows if 0 <= row["day"] <= 1824]


def read_real_pf_stock() -> list[dict[str, Any]]:
    path = source_file("Stock_PF_Immobilisé.csv")
    rows: list[dict[str, Any]] = []
    for row in read_csv_dicts(path, delimiter=";"):
        if str(row.get("Numéro article", "")).strip() != PRODUCT_CODE:
            continue
        snapshot_date = datetime.fromisoformat(row["Date de photo DMP"]).date()
        rows.append(
            {
                "date": snapshot_date.isoformat(),
                "day": (snapshot_date - START_DATE).days,
                "real_pf_immobilized_value": parse_float(row["Sum_Valeur totale du stock"]),
            }
        )
    return [row for row in rows if 0 <= row["day"] <= 1824]


def read_genealogy_component_items() -> set[str]:
    path = RUN_DIR / "data" / "production_lot_genealogy.csv"
    items: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (
                row.get("link_type") == "production"
                and row.get("child_node_id") == FACTORY
                and row.get("child_item_id") == f"item:{PRODUCT_CODE}"
            ):
                item_id = row.get("parent_item_id")
                if item_id:
                    items.add(item_id)
    return items


def read_component_prices() -> dict[str, dict[str, Any]]:
    graph = read_json(GRAPH_PATH)
    component_items = read_genealogy_component_items()
    by_item: dict[str, list[dict[str, Any]]] = {}
    fallback_by_item: dict[str, list[dict[str, Any]]] = {}

    def price_row(edge: dict[str, Any], scope: str) -> dict[str, Any] | None:
        attrs = edge.get("attrs") if isinstance(edge.get("attrs"), dict) else {}
        terms = edge.get("order_terms") if isinstance(edge.get("order_terms"), dict) else {}
        item_id = (edge.get("items") or [None])[0]
        if not item_id:
            return None
        sell_price = parse_float(terms.get("sell_price"), default=float("nan"))
        price_base = parse_float(terms.get("price_base"), default=1.0) or 1.0
        unit_price = None if sell_price != sell_price else sell_price / price_base
        return {
            "supplier": edge.get("from"),
            "sell_price": None if sell_price != sell_price else sell_price,
            "price_base": price_base,
            "unit_price": unit_price,
            "unit": terms.get("quantity_unit") or attrs.get("standard_order_uom"),
            "standard_order_qty": attrs.get("standard_order_qty"),
            "price_scope": scope,
        }

    for edge in graph.get("edges", []):
        attrs = edge.get("attrs") if isinstance(edge.get("attrs"), dict) else {}
        if edge.get("type") != "transport" or edge.get("to") != FACTORY:
            continue
        item_id = (edge.get("items") or [None])[0]
        if not item_id:
            continue
        if attrs.get("product_code") == PRODUCT_CODE:
            row = price_row(edge, "product_code")
            if row:
                by_item.setdefault(item_id, []).append(row)
        elif item_id in component_items and not attrs.get("product_code"):
            row = price_row(edge, "factory_item_fallback")
            if row:
                fallback_by_item.setdefault(item_id, []).append(row)

    for item_id in component_items:
        if item_id not in by_item and item_id in fallback_by_item:
            by_item[item_id] = fallback_by_item[item_id]
        else:
            by_item.setdefault(item_id, [])

    prices: dict[str, dict[str, Any]] = {}
    for item_id, rows in by_item.items():
        positive = [float(row["unit_price"]) for row in rows if row.get("unit_price") and float(row["unit_price"]) > 0]
        prices[item_id] = {
            "unit_price": statistics.median(positive) if positive else None,
            "source_count": len(rows),
            "zero_or_missing_sources": len(rows) - len(positive),
            "price_scope": "mixed"
            if any(row.get("price_scope") != rows[0].get("price_scope") for row in rows)
            else (rows[0].get("price_scope") if rows else "missing"),
            "sources": rows,
        }
    return prices


def read_stock_rows() -> dict[tuple[int, str], float]:
    out: dict[tuple[int, str], float] = {}
    path = RUN_DIR / "data" / "production_input_stocks_daily.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["node_id"] == FACTORY:
                out[(int(row["day"]), row["item_id"])] = parse_float(row["stock_end_of_day"])
    return out


def read_initial_stock() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    path = RUN_DIR / "data" / "initialization_observed_stock.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["node_id"] == FACTORY:
                out[row["item_id"]] = {
                    "opening_stock_qty": parse_float(row["opening_stock_qty"]),
                    "uom": row["uom"],
                    "source": row["source"],
                }
    return out


def read_mrp_trace() -> dict[tuple[int, str], dict[str, float]]:
    fields = (
        "target_stock_qty",
        "coverage_target_qty",
        "safety_stock_qty",
        "soft_safety_target_qty",
        "target_demand_signal_qty",
        "planned_receipt_qty",
        "inventory_position_qty",
    )
    out: dict[tuple[int, str], dict[str, float]] = {}
    path = RUN_DIR / "data" / "mrp_trace_daily.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["node_id"] != FACTORY:
                continue
            out[(int(row["day"]), row["item_id"])] = {field: parse_float(row.get(field)) for field in fields}
    return out


def threshold(values: dict[str, float], mode: str) -> float:
    if mode == "target_stock":
        return values["target_stock_qty"]
    if mode == "coverage":
        return values["coverage_target_qty"]
    if mode == "safety_plus_coverage":
        return values["coverage_target_qty"] + values["safety_stock_qty"]
    if mode == "demand_90d":
        return values["target_demand_signal_qty"] * 90.0
    if mode == "demand_180d":
        return values["target_demand_signal_qty"] * 180.0
    raise ValueError(mode)


def metric(values: list[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.pstdev(values),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def eur(value: float) -> str:
    return f"{value:,.0f} EUR".replace(",", " ")


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def build_analysis() -> dict[str, Any]:
    real_components = read_real_pharma_stock()
    real_pf = {row["day"]: row for row in read_real_pf_stock()}
    prices = read_component_prices()
    stocks = read_stock_rows()
    initial = read_initial_stock()
    mrp = read_mrp_trace()

    snapshot_rows: list[dict[str, Any]] = []
    component_snapshot_rows: list[dict[str, Any]] = []
    component_average: dict[str, dict[str, list[float]]] = {
        mode: {item_id: [] for item_id in prices} for mode in THRESHOLD_MODES
    }

    for real in real_components:
        day = int(real["day"])
        row = {
            "date": real["date"],
            "day": day,
            "real_component_immobilized_value": real["real_component_immobilized_value"],
            "real_pf_immobilized_value": real_pf.get(day, {}).get("real_pf_immobilized_value"),
        }
        for mode in THRESHOLD_MODES:
            total = 0.0
            for item_id, price_info in prices.items():
                unit_price = price_info.get("unit_price")
                if unit_price is None:
                    continue
                stock_qty = stocks.get((day, item_id), 0.0)
                mrp_values = mrp.get((day, item_id))
                if not mrp_values:
                    continue
                useful_qty = threshold(mrp_values, mode)
                excess_qty = max(stock_qty - useful_qty, 0.0)
                value = excess_qty * float(unit_price)
                total += value
                component_average[mode][item_id].append(value)
                component_snapshot_rows.append(
                    {
                        "mode": mode,
                        "date": real["date"],
                        "day": day,
                        "item_id": item_id,
                        "stock_qty": stock_qty,
                        "useful_qty": useful_qty,
                        "excess_qty": excess_qty,
                        "unit_price": unit_price,
                        "simulated_immobilized_value": value,
                    }
                )
            row[f"simulated_{mode}"] = total
            row[f"gap_{mode}"] = total - float(real["real_component_immobilized_value"])
        snapshot_rows.append(row)

    metrics: list[dict[str, Any]] = []
    observed = [float(row["real_component_immobilized_value"]) for row in snapshot_rows]
    for mode in THRESHOLD_MODES:
        sims = [float(row[f"simulated_{mode}"]) for row in snapshot_rows]
        diffs = [sim - obs for sim, obs in zip(sims, observed)]
        metrics.append(
            {
                "mode": mode,
                "observed_mean": statistics.mean(observed),
                "simulated_mean": statistics.mean(sims),
                "ratio": statistics.mean(sims) / statistics.mean(observed),
                "bias_pct": statistics.mean(diffs) / statistics.mean(observed),
                "mae_pct": statistics.mean(abs(diff) for diff in diffs) / statistics.mean(observed),
                "simulated_min": min(sims),
                "simulated_max": max(sims),
            }
        )

    component_rows: list[dict[str, Any]] = []
    for mode in THRESHOLD_MODES:
        for item_id, values in component_average[mode].items():
            if not values:
                continue
            price_info = prices[item_id]
            init = initial.get(item_id, {})
            first_mrp = mrp.get((0, item_id), {})
            component_rows.append(
                {
                    "mode": mode,
                    "item_id": item_id,
                    "avg_immobilized_value": statistics.mean(values),
                    "max_immobilized_value": max(values),
                    "unit_price": price_info.get("unit_price"),
                    "source_count": price_info.get("source_count"),
                    "price_scope": price_info.get("price_scope"),
                    "opening_stock_qty": init.get("opening_stock_qty"),
                    "uom": init.get("uom"),
                    "day0_target_stock_qty": first_mrp.get("target_stock_qty"),
                    "day0_coverage_target_qty": first_mrp.get("coverage_target_qty"),
                    "day0_target_demand_signal_qty": first_mrp.get("target_demand_signal_qty"),
                }
            )
    component_rows.sort(key=lambda row: (row["mode"], -float(row["avg_immobilized_value"])))

    return {
        "schema_version": "etudecas.cos_268091_gap_analysis.v1",
        "product_code": PRODUCT_CODE,
        "factory": FACTORY,
        "real_component_stats": metric(observed),
        "real_pf_stats": metric([float(row["real_pf_immobilized_value"]) for row in snapshot_rows if row.get("real_pf_immobilized_value") is not None]),
        "metrics": metrics,
        "components_without_price": [item_id for item_id, info in prices.items() if info.get("unit_price") is None],
        "multi_source_components": [item_id for item_id, info in prices.items() if int(info.get("source_count") or 0) > 1],
        "snapshot_rows": snapshot_rows,
        "component_rows": component_rows,
        "component_snapshot_rows": component_snapshot_rows,
        "price_info": prices,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    best = min(report["metrics"], key=lambda row: row["mae_pct"])
    lines = [
        "# Analyse ecart stock immobilise Cos 268091",
        "",
        f"Produit fini: `{PRODUCT_CODE}`. Usine: `{FACTORY}`.",
        "",
        "## Synthese",
        "",
        f"- Reference composant Cos moyenne: {eur(report['real_component_stats']['mean'])}.",
        f"- Reference PF Cos moyenne: {eur(report['real_pf_stats']['mean'])}.",
        f"- Meilleur seuil simule: `{best['mode']}` avec {eur(best['simulated_mean'])}, ratio {best['ratio']:.2f}, erreur moyenne {pct(best['mae_pct'])}.",
        "- Le calcul d'immobilise reduit l'ecart, mais ne l'annule pas: le stock simule reste trop haut pour 268091.",
        "",
        "## Tests de definition du stock immobilise",
        "",
        "| Mode | Reel moyen | Simule moyen | Ratio | Biais | Erreur moyenne |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["metrics"]:
        lines.append(
            f"| {row['mode']} | {eur(row['observed_mean'])} | {eur(row['simulated_mean'])} | "
            f"{row['ratio']:.2f} | {pct(row['bias_pct'])} | {pct(row['mae_pct'])} |"
        )
    lines.extend(
        [
            "",
            "## Principaux composants responsables",
            "",
            "Top composants pour le meilleur seuil.",
            "",
            "| Composant | Valeur immobilisee moyenne | Stock initial | Unite | Prix unitaire | Source prix | Cible J0 | Couverture J0 |",
            "|---|---:|---:|---|---:|---|---:|---:|",
        ]
    )
    top = [row for row in report["component_rows"] if row["mode"] == best["mode"]][:12]
    for row in top:
        lines.append(
            f"| {row['item_id']} | {eur(float(row['avg_immobilized_value']))} | "
            f"{float(row['opening_stock_qty'] or 0):,.1f} | {row.get('uom') or ''} | "
            f"{float(row['unit_price'] or 0):,.5g} | {row.get('price_scope') or ''} | "
            f"{float(row['day0_target_stock_qty'] or 0):,.1f} | "
            f"{float(row['day0_coverage_target_qty'] or 0):,.1f} |".replace(",", " ")
        )
    lines.extend(
        [
            "",
            "## Hypotheses les plus probables",
            "",
            "1. Le CSV reel ne couvre probablement pas tout le stock composant BOM 268091; il mesure un sous-ensemble immobilise selon une regle metier SAP/finance.",
            "2. Le stock initial simule M-1810 est trop eleve sur plusieurs composants Cos, surtout par rapport aux consommations utiles.",
            "3. Certains composants multi-sources sont valorises par un prix median; une valorisation au fournisseur effectivement consomme peut bouger le niveau mais ne suffit pas a expliquer un facteur x5.",
            "4. Le composant interne `item:693055` n'est pas valorise; l'ecart simule est donc plutot sous-estime, pas surestime, sur ce point.",
            "",
            "## Diagnostic consolide",
            "",
            "- Le fichier reel `Stock_Composants_Immobilise_Cos.csv` est un KPI hebdomadaire agrege: il n'a pas de colonne article, composant, lot, age, statut ou motif. Il doit etre lu comme une valeur filtree de stock immobilise/excedentaire Cos, pas comme le stock total composants.",
            "- La dynamique simulation 268091 est coherente: demande servie a 100%, lots de production coherents avec les consommations, transports sans perte significative. Le probleme n'est donc pas une rupture de lotification ou une sous-consommation buggee.",
            "- Le run demarre avec un gros pre-horizon: stock DC et pipeline initial couvrent une partie importante de la demande. Les composants associes aux produits deja en stock ou deja en pipeline ne sont pas consommes dans l'horizon; si on compare aux composants physiques restants, cela gonfle mecaniquement l'exces composant.",
            "- Le parametrage MRP maintient trop les niveaux physiques initiaux sur `M-1810`: plusieurs cibles reprennent le stock observe initial ou restent tres superieures a la couverture utile, ce qui empeche la purge du surstock.",
            "- `item:007923` est dans le BOM `268091` mais n'est pas valorise via les lignes FIA taggees `268091`; il a des prix hors ce perimetre. `item:693055` est interne et a prix fournisseur nul. Ces deux points rendent la valorisation incomplete et doivent etre traites explicitement.",
            "- Les composants `001848`, `055703`, `002612` sont multi-sources. La mediane non ponderee est acceptable pour un audit rapide, mais une comparaison finance doit utiliser le fournisseur reellement commande ou un prix moyen pondere.",
            "",
            "## Corrections recommandees",
            "",
            "1. Definir officiellement le perimetre du KPI reel: stock bloque, stock dormant, stock excedentaire vs cible, ou stock total filtre Cos.",
            "2. Ajouter une sortie simulation `immobilized_component_stock_value` dans le pipeline principal, avec la meme definition que le KPI reel.",
            "3. Pour `M-1810`, tester un scenario de calibration sans floor physique strict sur composants, ou avec un floor decroissant permettant de purger le stock initial.",
            "4. Separer les ordres fermes pre-horizon du pilotage MRP courant: ils doivent expliquer le service initial, mais ne doivent pas forcer une reconstitution durable des composants.",
            "5. Completer la valorisation de `007923` et `693055`, puis refaire la comparaison composant par composant.",
            "",
            "## Fichiers generes",
            "",
            "- `cos_268091_gap_summary.json`",
            "- `cos_268091_gap_snapshots.csv`",
            "- `cos_268091_gap_components.csv`",
            "- `cos_268091_gap_component_snapshots.csv`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_analysis()
    (REPORT_DIR / "cos_268091_gap_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_csv(REPORT_DIR / "cos_268091_gap_snapshots.csv", report["snapshot_rows"])
    write_csv(REPORT_DIR / "cos_268091_gap_components.csv", report["component_rows"])
    write_csv(REPORT_DIR / "cos_268091_gap_component_snapshots.csv", report["component_snapshot_rows"])
    write_markdown(report, REPORT_DIR / "cos_268091_gap_report.md")
    best = min(report["metrics"], key=lambda row: row["mae_pct"])
    print(
        f"[OK] 268091 best={best['mode']} observed={best['observed_mean']:.1f} "
        f"simulated={best['simulated_mean']:.1f} ratio={best['ratio']:.2f} report={REPORT_DIR}"
    )


if __name__ == "__main__":
    main()
