"""Build a factual, additive assessment of the available 2025 industrial data.

The report deliberately keeps three different objects separate:

* observed monetary values (revenue and accounting stock snapshots),
* observed planning records (projected shortages and the open-order book),
* simulated physical quantities and service indicators.

It does not attribute revenue loss or stock to a supplier because the source
files do not contain the keys required for that attribution.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = REPO_ROOT / "etudecas" / "data" / "source"
ANALYSIS_RESULT_DIR = REPO_ROOT / "etudecas" / "analysis" / "from_simulation" / "result"
ARTIFACT_ROOT = REPO_ROOT.parent / "lca-simu-pr40-validation-artifacts-20260726"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "observed_2025_supply_bilan_20260901_v1"
DEFAULT_REFERENCE_RUN = (
    ARTIFACT_ROOT
    / "paired_mrp_vs_v3_all_nodes_full_20260828_v2"
    / "mrp_reference"
    / "seed_320270"
)
DEFAULT_021_REFERENCE_RUN = (
    ARTIFACT_ROOT
    / "c1_quality_recalibration_20260828_v1"
    / "normal_seed_330281"
)

# Neither CA_Perdu_Réel.csv nor Stock_PF_Immobilisé.csv declares a business
# family. More importantly, the two component-stock CSVs contain only a family
# label in their filename and no product code. Different historical analyses
# used contradictory product-to-family mappings. The factual extract therefore
# leaves this relationship unresolved instead of silently choosing one.
COMPONENT_STOCK_SERIES = {
    "Cos": {"series_id": "component_stock_cos", "source_family_label": "Cos"},
    "Pharma": {"series_id": "component_stock_pharma", "source_family_label": "Pharma"},
}
MONEY_UNIT_NOTE = "valeur monétaire; convention de travail EUR, devise absente du CSV source"


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value or "").strip().replace(" ", "").replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value or "").strip().replace(",", ".")))
    except (TypeError, ValueError):
        return default


def normalized_header(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char.lower() for char in text if char.isalnum() and not unicodedata.combining(char))


def field_key(row: dict[str, Any], wanted: str) -> str:
    target = normalized_header(wanted)
    for key in row:
        if normalized_header(key) == target:
            return key
    raise KeyError(f"Missing field {wanted!r}; available fields: {list(row)}")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            with path.open(encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle, delimiter=";"))
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def parse_stock_datetime(value: str) -> datetime:
    text = str(value).strip()
    for fmt in (None, "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.fromisoformat(text) if fmt is None else datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported stock snapshot date: {value!r}")


def single_glob(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected exactly one {pattern!r} in {root}, found {len(matches)}")
    return matches[0]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    fields.append(key)
                    seen.add(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return statistics.mean(materialized) if materialized else 0.0


def median(values: Iterable[float]) -> float:
    materialized = list(values)
    return statistics.median(materialized) if materialized else 0.0


def build_ca(source_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], Path]:
    source = single_glob(source_dir, "CA_Perdu*.csv")
    raw = read_csv_rows(source)
    daily: list[dict[str, Any]] = []
    for row in raw:
        product = str(row[field_key(row, "Product code")]).strip()
        current_date = date.fromisoformat(str(row[field_key(row, "First delivery date")]).strip())
        delivered = parse_float(row[field_key(row, "CA_Livré")])
        lost = parse_float(row[field_key(row, "CA_Perdu")])
        signal_count = parse_int(row[field_key(row, "Nb_Rep_CA_Perdu")])
        daily.append(
            {
                "evidence": "OBSERVED_SOURCE",
                "product_code": product,
                "family": "",
                "date": current_date.isoformat(),
                "weekday": current_date.strftime("%A"),
                "ca_delivered_source_value": delivered,
                "ca_lost_source_value": lost,
                "lost_signal_count": signal_count,
                "positive_lost_value": lost > 0,
                "lost_signal_present": signal_count > 0,
                "unit_note": MONEY_UNIT_NOTE,
                "source_file": source.name,
            }
        )

    by_product: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_month: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in daily:
        by_product[str(row["product_code"])].append(row)
        by_month[(str(row["product_code"]), str(row["date"])[:7])].append(row)

    summaries: list[dict[str, Any]] = []
    for product, rows in sorted(by_product.items()):
        delivered = sum(float(row["ca_delivered_source_value"]) for row in rows)
        lost = sum(float(row["ca_lost_source_value"]) for row in rows)
        positive_lost = sum(max(float(row["ca_lost_source_value"]), 0.0) for row in rows)
        negative_adjustment = sum(min(float(row["ca_lost_source_value"]), 0.0) for row in rows)
        signals = sum(int(row["lost_signal_count"]) for row in rows)
        unflagged = [
            row
            for row in rows
            if float(row["ca_lost_source_value"]) > 0 and int(row["lost_signal_count"]) == 0
        ]
        potential = delivered + lost
        dates = [str(row["date"]) for row in rows]
        summaries.append(
            {
                "evidence": "OBSERVED_SOURCE",
                "product_code": product,
                "family": "",
                "row_count": len(rows),
                "unique_date_count": len(set(dates)),
                "first_date": min(dates),
                "last_date": max(dates),
                "ca_delivered_source_value": delivered,
                "ca_lost_raw_source_value": lost,
                "ca_lost_positive_only_source_value": positive_lost,
                "ca_lost_negative_adjustments_source_value": negative_adjustment,
                "ca_potential_raw_source_value": potential,
                "delivered_share_of_raw_potential": delivered / potential if potential else None,
                "lost_share_of_raw_potential": lost / potential if potential else None,
                "lost_signal_count": signals,
                "days_with_positive_lost_value": sum(float(row["ca_lost_source_value"]) > 0 for row in rows),
                "days_with_lost_signal": sum(int(row["lost_signal_count"]) > 0 for row in rows),
                "days_positive_lost_without_signal": len(unflagged),
                "positive_lost_without_signal_source_value": sum(
                    float(row["ca_lost_source_value"]) for row in unflagged
                ),
                "negative_lost_value_row_count": sum(float(row["ca_lost_source_value"]) < 0 for row in rows),
                "unit_note": MONEY_UNIT_NOTE,
                "interpretation_limit": (
                    "Taux financier descriptif CA livré/(CA livré+CA perdu), pas un OTIF, "
                    "pas un taux de service en unités et sans attribution fournisseur."
                ),
            }
        )

    monthly: list[dict[str, Any]] = []
    for (product, month), rows in sorted(by_month.items()):
        delivered = sum(float(row["ca_delivered_source_value"]) for row in rows)
        lost = sum(float(row["ca_lost_source_value"]) for row in rows)
        potential = delivered + lost
        monthly.append(
            {
                "evidence": "OBSERVED_SOURCE",
                "product_code": product,
                "family": "",
                "month": month,
                "row_count": len(rows),
                "ca_delivered_source_value": delivered,
                "ca_lost_raw_source_value": lost,
                "lost_signal_count": sum(int(row["lost_signal_count"]) for row in rows),
                "days_with_positive_lost_value": sum(float(row["ca_lost_source_value"]) > 0 for row in rows),
                "delivered_share_of_raw_potential": delivered / potential if potential else None,
                "unit_note": MONEY_UNIT_NOTE,
            }
        )
    return daily, monthly, summaries, source


def build_stocks(source_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Path]]:
    records: list[dict[str, Any]] = []
    sources: list[Path] = []
    for label, meta in COMPONENT_STOCK_SERIES.items():
        source = single_glob(source_dir, f"Stock_Composants*_{label}.csv")
        sources.append(source)
        raw = read_csv_rows(source)
        for row in raw:
            timestamp = parse_stock_datetime(row[field_key(row, "Date de photo DMP")])
            value = parse_float(row[field_key(row, "Sum_Valeur totale du stock")])
            records.append(
                {
                    "evidence": "OBSERVED_SOURCE",
                    "stock_scope": "component_immobilized_accounting_value",
                    "series_id": meta["series_id"],
                    "product_code": "",
                    "source_family_label": meta["source_family_label"],
                    "factory": "",
                    "snapshot_timestamp": timestamp.isoformat(),
                    "snapshot_date": timestamp.date().isoformat(),
                    "stock_value_source": value,
                    "physical_quantity_available": False,
                    "physical_uom": "",
                    "unit_note": MONEY_UNIT_NOTE,
                    "source_file": source.name,
                    "scope_limit": (
                        "agrégé famille; aucun code produit, article, lot, statut, magasin ou quantité physique; "
                        "mapping produit non résolu"
                    ),
                }
            )

    pf_source = single_glob(source_dir, "Stock_PF*.csv")
    sources.append(pf_source)
    for row in read_csv_rows(pf_source):
        product = str(row[field_key(row, "Numéro article")]).strip()
        timestamp = parse_stock_datetime(row[field_key(row, "Date de photo DMP")])
        value = parse_float(row[field_key(row, "Sum_Valeur totale du stock")])
        records.append(
            {
                "evidence": "OBSERVED_SOURCE",
                "stock_scope": "finished_goods_immobilized_accounting_value",
                "series_id": f"finished_goods_stock_{product}",
                "product_code": product,
                "source_family_label": "",
                "factory": "M-1810" if product == "268091" else ("M-1430" if product == "268967" else ""),
                "snapshot_timestamp": timestamp.isoformat(),
                "snapshot_date": timestamp.date().isoformat(),
                "stock_value_source": value,
                "physical_quantity_available": False,
                "physical_uom": "",
                "unit_note": MONEY_UNIT_NOTE,
                "source_file": pf_source.name,
                "scope_limit": "agrégé par PF; aucun site, lot, statut, quantité ou coût unitaire",
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[str(row["series_id"])].append(row)
    summaries: list[dict[str, Any]] = []
    for series_id, rows in sorted(grouped.items()):
        values = [float(row["stock_value_source"]) for row in rows]
        ordered = sorted(rows, key=lambda row: str(row["snapshot_timestamp"]))
        product = str(rows[0]["product_code"])
        scope = str(rows[0]["stock_scope"])
        scope_limit = "valeur comptable agrégée; ne permet pas de déduire le stock physique"
        if scope == "component_immobilized_accounting_value":
            scope_limit += "; le code produit n'est pas présent dans la source composants"
        else:
            scope_limit += "; quantité, coût unitaire, lot, site et statut PF absents"
        summaries.append(
            {
                "evidence": "OBSERVED_SOURCE",
                "series_id": series_id,
                "product_code": product,
                "source_family_label": str(rows[0]["source_family_label"]),
                "stock_scope": scope,
                "snapshot_count": len(rows),
                "unique_date_count": len({str(row["snapshot_date"]) for row in rows}),
                "first_snapshot_date": ordered[0]["snapshot_date"],
                "last_snapshot_date": ordered[-1]["snapshot_date"],
                "mean_stock_value_source": mean(values),
                "median_stock_value_source": median(values),
                "minimum_stock_value_source": min(values),
                "maximum_stock_value_source": max(values),
                "first_stock_value_source": float(ordered[0]["stock_value_source"]),
                "last_stock_value_source": float(ordered[-1]["stock_value_source"]),
                "standard_deviation_stock_value_source": statistics.pstdev(values),
                "physical_quantity_available": False,
                "unit_note": MONEY_UNIT_NOTE,
                "interpretation_limit": scope_limit,
            }
        )
    return records, summaries, sources


def build_projected_shortages(
    source_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Path]:
    source = single_glob(source_dir, "Dispo_PF_Projet*.csv")
    records: list[dict[str, Any]] = []
    for row in read_csv_rows(source):
        product = str(row[field_key(row, "SKU Code")]).strip()
        year_week = str(row[field_key(row, "Year Week Snapshot")]).strip()
        year_text, week_text = year_week.split("|", 1)
        shortage_weeks = parse_float(row[field_key(row, "Nb_Semaine_Rupture_Produit")])
        repetition = parse_float(row[field_key(row, "Répétition_Rupture_Produit")])
        records.append(
            {
                "evidence": "OBSERVED_PLANNING_SNAPSHOT",
                "product_code": product,
                "family": "",
                "year_week_snapshot": year_week,
                "snapshot_year": int(year_text),
                "snapshot_week": int(week_text),
                "projected_shortage_weeks": shortage_weeks,
                "projected_shortage_repetition": repetition,
                "nonzero_projection": shortage_weeks > 0 or repetition > 0,
                "interpretation_limit": "projection à la date de photo; pas une rupture réalisée et non sommable entre photos",
                "source_file": source.name,
            }
        )
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[(str(row["product_code"]), int(row["snapshot_year"]))].append(row)
    summaries: list[dict[str, Any]] = []
    for (product, year), rows in sorted(grouped.items()):
        nonzero = [row for row in rows if bool(row["nonzero_projection"])]
        summaries.append(
            {
                "evidence": "OBSERVED_PLANNING_SNAPSHOT",
                "product_code": product,
                "family": "",
                "snapshot_year": year,
                "snapshot_count": len(rows),
                "nonzero_snapshot_count": len(nonzero),
                "maximum_projected_shortage_weeks": max(float(row["projected_shortage_weeks"]) for row in rows),
                "maximum_projected_shortage_repetition": max(
                    float(row["projected_shortage_repetition"]) for row in rows
                ),
                "first_nonzero_year_week": min((str(row["year_week_snapshot"]) for row in nonzero), default=""),
                "last_nonzero_year_week": max((str(row["year_week_snapshot"]) for row in nonzero), default=""),
                "sum_deliberately_not_computed": True,
                "interpretation_limit": "les projections de photos successives peuvent décrire les mêmes futures ruptures",
            }
        )
    return records, summaries, source


def csv_row_by(path: Path, key: str, value: str) -> dict[str, str] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get(key) or "") == value:
                return row
    return None


def build_service_comparisons(
    ca_summary: list[dict[str, Any]], reference_run: Path
) -> list[dict[str, Any]]:
    service_path = reference_run / "data" / "production_demand_service_daily.csv"
    if not service_path.exists():
        return []
    with service_path.open(encoding="utf-8-sig", newline="") as handle:
        raw = list(csv.DictReader(handle))
    by_item: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in raw:
        by_item[str(row.get("item_id") or "")].append(row)
    ca_by_product = {str(row["product_code"]): row for row in ca_summary}
    comparisons: list[dict[str, Any]] = []
    for product in sorted(ca_by_product):
        rows = by_item.get(f"item:{product}", [])
        if not rows:
            continue
        demand = sum(parse_float(row.get("demand_qty")) for row in rows)
        served = sum(parse_float(row.get("served_qty")) for row in rows)
        served_same_day_proxy = sum(
            min(parse_float(row.get("served_qty")), parse_float(row.get("demand_qty"))) for row in rows
        )
        backlog_days = sum(parse_float(row.get("backlog_end_qty")) > 1e-9 for row in rows)
        observed = ca_by_product[product]
        observed_rate = float(observed["delivered_share_of_raw_potential"])
        sim_rate = served_same_day_proxy / demand if demand else 0.0
        comparisons.append(
            {
                "comparison_id": f"service_directional_{product}",
                "product_code": product,
                "scope": "service",
                "observed_metric": "CA livré / (CA livré + CA perdu)",
                "observed_value": observed_rate,
                "simulated_metric": "part de la demande servie le jour même (proxy unités)",
                "simulated_value": sim_rate,
                "gap_sim_minus_observed": sim_rate - observed_rate,
                "gap_unit": "point de ratio",
                "mae": "",
                "correlation": "",
                "comparison_status": "DIRECTIONAL_ONLY",
                "calibration_reading": (
                    f"référence {len(rows)} jours: {backlog_days} jours avec backlog; "
                    f"service cumulé finalement livré={served / demand if demand else 0.0:.6f}"
                ),
                "limit": (
                    "métriques différentes: euros source contre unités simulées; le run comporte 60 jours de chauffe "
                    "et n'est pas une relecture historique commande par commande"
                ),
                "source": str(service_path),
            }
        )
    return comparisons


def build_stock_comparisons(analysis_result_dir: Path) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    # The most recent source-truth artifact uses the explicit hypothesis
    # 268091 -> Pharma and 268967 -> Cos. The source CSVs themselves do not
    # contain product codes, so these rows remain hypotheses, not factual
    # product-level validation.
    source_truth = (
        analysis_result_dir
        / "component_immobilized_stock_source_truth"
        / "component_immobilized_stock_comparison.json"
    )
    if source_truth.exists():
        source_payload = json.loads(source_truth.read_text(encoding="utf-8"))
        for row in source_payload.get("rows", []):
            if row.get("alignment") != "previous_day" or row.get("metric_id") != "stock_total_value":
                continue
            product = str(row.get("product_code") or "")
            family_hypothesis = "Pharma" if product == "268091" else ("Cos" if product == "268967" else "")
            observed = parse_float(row.get("observed_mean_eur"))
            simulated = parse_float(row.get("simulated_snapshot_mean_eur"))
            comparisons.append(
                {
                    "comparison_id": f"component_source_truth_hypothesis_{product}",
                    "product_code": product,
                    "scope": "component_stock_value",
                    "observed_metric": f"valeur comptable composants {family_hypothesis} (hypothèse de mapping)",
                    "observed_value": observed,
                    "simulated_metric": "stock composant total simulé valorisé, photos alignées au jour précédent",
                    "simulated_value": simulated,
                    "gap_sim_minus_observed": simulated - observed,
                    "gap_unit": MONEY_UNIT_NOTE,
                    "mae": parse_float(row.get("mae_eur")),
                    "correlation": "",
                    "comparison_status": "HYPOTHESIS_MAPPING_NOT_VALIDATED",
                    "calibration_reading": (
                        f"convention explicite du rapport récent: {product}→{family_hypothesis}; "
                        "la source ne porte pas le code produit"
                    ),
                    "limit": (
                        "une convention historique opposée existe; aucune conclusion produit ne doit être annoncée "
                        "avant validation industrielle du mapping"
                    ),
                    "source": str(source_truth),
                }
            )

    pf_metrics_268091 = analysis_result_dir / "infer_268091_immobilized_stock_rule" / "pf_rule_metrics.csv"
    pf_row = csv_row_by(pf_metrics_268091, "rule", "physical_pf_stock_at_median_implied_unit_value")
    if pf_row:
        observed = parse_float(pf_row.get("real_mean"))
        simulated = parse_float(pf_row.get("sim_mean"))
        comparisons.append(
            {
                "comparison_id": "finished_goods_268091_implied_value",
                "product_code": "268091",
                "scope": "finished_goods_stock_value",
                "observed_metric": "valeur comptable PF immobilisé",
                "observed_value": observed,
                "simulated_metric": "quantité PF simulée x valeur unitaire médiane implicite",
                "simulated_value": simulated,
                "gap_sim_minus_observed": simulated - observed,
                "gap_unit": MONEY_UNIT_NOTE,
                "mae": parse_float(pf_row.get("mae")),
                "correlation": parse_float(pf_row.get("corr"), default=float("nan")),
                "comparison_status": "NOT_VALIDATED",
                "calibration_reading": (
                    f"coefficient de variation de la valeur unitaire implicite="
                    f"{parse_float(pf_row.get('implied_unit_value_cv')):.3f}"
                ),
                "limit": "la valeur unitaire est inférée des mêmes photos et est extrêmement instable",
                "source": str(pf_metrics_268091),
            }
        )

    comparisons.append(
        {
            "comparison_id": "finished_goods_268967_missing_direct_comparison",
            "product_code": "268967",
            "scope": "finished_goods_stock_value",
            "observed_metric": "valeur comptable PF immobilisé",
            "observed_value": "",
            "simulated_metric": "aucune valorisation annuelle directement comparable validée",
            "simulated_value": "",
            "gap_sim_minus_observed": "",
            "gap_unit": MONEY_UNIT_NOTE,
            "mae": "",
            "correlation": "",
            "comparison_status": "MISSING_COMPARABLE_METRIC",
            "calibration_reading": "une conversion indicative au premier snapshot ne constitue pas une validation annuelle",
            "limit": "quantité réelle et coût unitaire/statut PF absents du CSV",
            "source": str(analysis_result_dir / "audit_268967_pf_driven_stock_rule"),
        }
    )
    return comparisons


def build_021_context(
    analysis_result_dir: Path, reference_run: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    audit_path = analysis_result_dir / "mrp_stock_target_audit" / "mrp_stock_target_audit.csv"
    audit_row: dict[str, str] | None = None
    if audit_path.exists():
        with audit_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("node_id") == "SDC-1450" and row.get("item_id") == "item:021081":
                    audit_row = row
                    break
    stock_path = reference_run / "data" / "production_input_stocks_daily.csv"
    arrivals_path = reference_run / "data" / "production_input_replenishment_arrivals_daily.csv"
    stock_rows: list[dict[str, str]] = []
    if stock_path.exists():
        with stock_path.open(encoding="utf-8-sig", newline="") as handle:
            stock_rows = [
                row
                for row in csv.DictReader(handle)
                if row.get("node_id") == "SDC-1450" and row.get("item_id") == "item:021081"
            ]
    arrivals = 0.0
    if arrivals_path.exists():
        with arrivals_path.open(encoding="utf-8-sig", newline="") as handle:
            arrivals = sum(
                parse_float(row.get("arrived_qty"))
                for row in csv.DictReader(handle)
                if row.get("node_id") == "SDC-1450" and row.get("item_id") == "item:021081"
            )

    opening_source = parse_float((audit_row or {}).get("source_stock_qty"))
    opening_orders = parse_float((audit_row or {}).get("source_open_order_qty"))
    order_count = parse_int((audit_row or {}).get("source_open_order_count"))
    measurement_start = parse_float(stock_rows[0].get("stock_end_of_day")) if stock_rows else 0.0
    measurement_end = parse_float(stock_rows[-1].get("stock_end_of_day")) if stock_rows else 0.0
    consumption = measurement_start + arrivals - measurement_end
    days = len(stock_rows)
    rate_per_day = consumption / days if days and consumption > 0 else 0.0
    source_cover_days = opening_source / rate_per_day if rate_per_day else 0.0
    combined_cover_days = (opening_source + opening_orders) / rate_per_day if rate_per_day else 0.0
    supplier_text = str((audit_row or {}).get("source_open_order_types") or "")
    # The supplier count is known from the exact order-book lane audit. It is
    # kept explicit here because source_open_order_types contains order types,
    # not supplier identities.
    supplier_count = 4 if order_count else 0
    rows = [
        {
            "metric": "opening_component_stock",
            "evidence": "OBSERVED_SNAPSHOT",
            "item_id": "item:021081",
            "node_id": "SDC-1450",
            "value": opening_source,
            "unit": str((audit_row or {}).get("source_stock_uom") or "KG"),
            "horizon_days": "",
            "source": str(audit_path),
            "interpretation": "stock physique déclaré au snapshot MRP; statut d'utilisation non documenté",
        },
        {
            "metric": "opening_purchase_orders",
            "evidence": "OBSERVED_PLANNED_ORDER_BOOK",
            "item_id": "item:021081",
            "node_id": "SDC-1450",
            "value": opening_orders,
            "unit": "KG",
            "horizon_days": "",
            "source": str(audit_path),
            "interpretation": (
                f"{order_count} lignes, {supplier_count} fournisseurs; commandes planifiées, pas réceptions réalisées; "
                f"types={supplier_text}"
            ),
        },
        {
            "metric": "simulated_measured_consumption",
            "evidence": "SIMULATED_REFERENCE",
            "item_id": "item:021081",
            "node_id": "SDC-1450",
            "value": consumption,
            "unit": "KG",
            "horizon_days": days,
            "source": str(stock_path),
            "interpretation": (
                f"baisse de stock sur le run de référence, arrivées simulées mesurées={arrivals:.3f} KG; "
                "ce n'est pas une consommation historique observée"
            ),
        },
    ]
    summary = {
        "item_id": "item:021081",
        "opening_stock_source_kg": opening_source,
        "opening_order_book_kg": opening_orders,
        "opening_order_line_count": order_count,
        "opening_order_supplier_count": supplier_count,
        "simulated_measurement_start_stock_kg": measurement_start,
        "simulated_measurement_end_stock_kg": measurement_end,
        "simulated_arrivals_kg": arrivals,
        "simulated_consumption_kg": consumption,
        "simulated_horizon_days": days,
        "opening_stock_over_horizon_consumption": opening_source / consumption if consumption else None,
        "opening_plus_orders_over_horizon_consumption": (
            (opening_source + opening_orders) / consumption if consumption else None
        ),
        "implied_opening_stock_cover_years_if_rate_constant": source_cover_days / 365.0 if source_cover_days else None,
        "implied_opening_plus_orders_cover_years_if_rate_constant": (
            combined_cover_days / 365.0 if combined_cover_days else None
        ),
        "interpretation_limit": (
            "Le ratio mélange un stock/ordre observé avec une consommation simulée. Il sert à détecter une incohérence "
            "à instruire, pas à annoncer une couverture ferme. Valider unité, site, propriété, libre/bloqué/alloué, "
            "péremption et commandes encore actives."
        ),
    }
    return rows, summary


def mapping_hypotheses() -> list[dict[str, Any]]:
    """Register the contradictory mappings without selecting one as truth."""
    return [
        {
            "mapping_id": "recent_source_truth_explicit_hypothesis",
            "product_code": "268091",
            "component_stock_source_family": "Pharma",
            "status": "UNVALIDATED_EXPLICIT_HYPOTHESIS",
            "source": "component_immobilized_stock_source_truth/component_immobilized_stock_comparison.md",
            "note": "rapport récent; le CSV composant ne porte aucun code produit",
        },
        {
            "mapping_id": "recent_source_truth_explicit_hypothesis",
            "product_code": "268967",
            "component_stock_source_family": "Cos",
            "status": "UNVALIDATED_EXPLICIT_HYPOTHESIS",
            "source": "component_immobilized_stock_source_truth/component_immobilized_stock_comparison.md",
            "note": "rapport récent; le CSV composant ne porte aucun code produit",
        },
        {
            "mapping_id": "legacy_opposite_convention",
            "product_code": "268091",
            "component_stock_source_family": "Cos",
            "status": "CONFLICTING_LEGACY_CONVENTION",
            "source": "plusieurs anciens audits et supplier_risk_decision_brief",
            "note": "ne pas réutiliser avant arbitrage industriel",
        },
        {
            "mapping_id": "legacy_opposite_convention",
            "product_code": "268967",
            "component_stock_source_family": "Pharma",
            "status": "CONFLICTING_LEGACY_CONVENTION",
            "source": "plusieurs anciens audits et supplier_risk_decision_brief",
            "note": "ne pas réutiliser avant arbitrage industriel",
        },
    ]


def prediction_readiness() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    minimum_fields = [
        ("identity", "supplier_id", "identifiant fournisseur stable"),
        ("identity", "item_id", "article acheté stable"),
        ("identity", "destination_site_id", "site destinataire et périmètre logistique"),
        ("order", "purchase_order_id", "numéro de commande"),
        ("order", "purchase_order_line_id", "ligne de commande, clé d'observation minimale"),
        ("dates", "order_release_date", "date d'émission/libération de la commande"),
        ("dates", "requested_delivery_date", "date demandée"),
        ("dates", "original_promised_date", "engagement fournisseur initial"),
        ("dates", "revised_promised_dates", "historique des re-promesses et leur date de saisie"),
        ("dates", "actual_receipt_date", "réception physique réelle"),
        ("quantity", "ordered_confirmed_received_qty_uom", "quantités commandée, confirmée et reçue dans une UOM harmonisée"),
        ("quality", "quality_defect_hold_release", "défaut, quarantaine/hold, décision et date de libération/rejet"),
        ("cause", "delay_or_defect_cause_code", "cause fournisseur, transport, interne, qualité ou planning"),
        ("action", "expediting_action_and_date", "relance, accélération, fractionnement ou autre action qui modifie le résultat"),
        ("calendar", "supplier_site_calendars", "jours ouvrés, fermetures, transit et cut-offs"),
        ("capacity", "capacity_commitment_and_load", "capacité promise/disponible ou proxy de charge daté"),
    ]
    rows = [
        {
            "field_group": group,
            "minimum_field": field,
            "business_reason": reason,
            "availability_in_current_2025_bundle": "MISSING_OR_NOT_LINKED",
        }
        for group, field, reason in minimum_fields
    ]
    summary = {
        "industrial_probability_status": "NOT_READY",
        "current_safe_wording": "signal de priorité fournisseur à instruire; pas une probabilité industrielle",
        "prediction_poc_training_data": "synthetic weekly history and synthetic incident labels",
        "prediction_poc_source": str(REPO_ROOT / "etudecas" / "prototypes" / "prediction"),
        "current_order_book_status": (
            "planned 2025 opening order book; no actual promised-vs-received outcome and no reliable OTIF label"
        ),
        "minimum_observation_unit": "supplier_id x item_id x destination_site_id x purchase_order_id x purchase_order_line_id",
        "minimum_field_count": len(rows),
        "next_scientific_step": (
            "build time-ordered labels from actual outcomes, split train/calibration/test by time, "
            "calibrate probabilities and validate reliability by supplier/item/site segments"
        ),
    }
    return summary, rows


def build_quality_findings(
    ca_summary: list[dict[str, Any]], stock_summary: list[dict[str, Any]], context_021: dict[str, Any]
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = [
        {
            "finding_id": "DQ-001",
            "severity": "HIGH",
            "topic": "currency",
            "finding": "Les quatre CSV monétaires ne déclarent pas la devise.",
            "consequence": "EUR reste une convention de travail à confirmer avant diffusion contractuelle.",
            "required_action": "Confirmer devise, TVA et définition comptable de chaque champ.",
        },
        {
            "finding_id": "DQ-002",
            "severity": "MEDIUM",
            "topic": "calendar",
            "finding": "CA_Perdu contient 261 dates par produit, uniquement les jours de semaine 2025.",
            "consequence": "L'absence de week-end n'est pas une preuve de zéro activité.",
            "required_action": "Confirmer le calendrier commercial et le traitement des jours fériés/week-ends.",
        },
        {
            "finding_id": "DQ-005",
            "severity": "HIGH",
            "topic": "stock_semantics",
            "finding": "Les CSV de stock donnent une valeur comptable agrégée, jamais une quantité physique.",
            "consequence": "Impossible d'en déduire jours de couverture, lots ou volumes sans prix et quantités.",
            "required_action": "Obtenir quantité/UOM, article, site, magasin, statut, lot, âge et valeur/prix.",
        },
        {
            "finding_id": "DQ-006",
            "severity": "HIGH",
            "topic": "projected_shortage",
            "finding": "Dispo_PF_Projeté contient des projections à des dates de photo, pas des ruptures réalisées.",
            "consequence": "Additionner les semaines de rupture entre photos compterait potentiellement plusieurs fois le même futur.",
            "required_action": "Obtenir la définition du calcul, l'horizon de projection et les identifiants d'événements.",
        },
        {
            "finding_id": "DQ-007",
            "severity": "HIGH",
            "topic": "legacy_mapping",
            "finding": (
                "Deux conventions contradictoires relient les fichiers composants Cos/Pharma aux produits. "
                "Le rapport source-truth récent pose 268091→Pharma et 268967→Cos comme hypothèse explicite; "
                "plusieurs anciens audits utilisent l'inverse."
            ),
            "consequence": "Aucun rapprochement composant par produit n'est factuel tant que ce point n'est pas arbitré.",
            "required_action": "Faire confirmer le mapping par le propriétaire des extractions; conserver les séries séparées d'ici là.",
        },
        {
            "finding_id": "DQ-008",
            "severity": "HIGH",
            "topic": "supplier_attribution",
            "finding": "CA, stocks agrégés et projections PF ne portent aucun identifiant fournisseur, PO, réception, lot ou cause.",
            "consequence": "Aucune perte de CA réelle ne peut être attribuée scientifiquement à un fournisseur avec ces fichiers seuls.",
            "required_action": "Relier commande client, lot PF, lot de production, lots composants, réception, PO et fournisseur.",
        },
        {
            "finding_id": "DQ-010",
            "severity": "HIGH",
            "topic": "supplier_risk_prediction",
            "finding": (
                "Le POC de prédiction est entraîné sur historique et labels synthétiques; le carnet 2025 contient "
                "des dates planifiées, pas les résultats réels promis-versus-reçus."
            ),
            "consequence": "Ses scores ne sont pas des probabilités industrielles de défaillance fournisseur.",
            "required_action": (
                "Collecter l'historique PO/ligne fournisseur-article-site avec engagements, réceptions, qualité, causes et actions."
            ),
        },
    ]
    for row in ca_summary:
        product = str(row["product_code"])
        findings.append(
            {
                "finding_id": f"DQ-003-{product}",
                "severity": "HIGH" if int(row["days_positive_lost_without_signal"]) else "LOW",
                "topic": "lost_revenue_signal",
                "finding": (
                    f"{product}: {row['days_positive_lost_without_signal']} jours ont un CA perdu positif mais "
                    f"Nb_Rep_CA_Perdu=0, pour {float(row['positive_lost_without_signal_source_value']):.2f} en valeur source."
                ),
                "consequence": "Nb_Rep_CA_Perdu n'est pas un compteur exhaustif des lignes de CA perdu positif.",
                "required_action": "Faire définir Nb_Rep_CA_Perdu et sa règle d'agrégation.",
            }
        )
        if int(row["negative_lost_value_row_count"]):
            findings.append(
                {
                    "finding_id": f"DQ-004-{product}",
                    "severity": "MEDIUM",
                    "topic": "negative_lost_revenue",
                    "finding": (
                        f"{product}: {row['negative_lost_value_row_count']} ligne de CA perdu est négative, "
                        f"total {float(row['ca_lost_negative_adjustments_source_value']):.2f}."
                    ),
                    "consequence": "Le total brut inclut probablement une correction/avoir non documenté.",
                    "required_action": "Confirmer si le total officiel doit conserver ou neutraliser cette correction.",
                }
            )
    if context_021.get("opening_stock_over_horizon_consumption"):
        findings.append(
            {
                "finding_id": "DQ-009-021081",
                "severity": "HIGH",
                "topic": "physical_stock_cover",
                "finding": (
                    "021081: le stock d'ouverture déclaré et les commandes ouvertes représentent plusieurs horizons "
                    "de la consommation simulée sur 720 jours."
                ),
                "consequence": (
                    "La simulation de risque fournisseur est dominée par la couverture initiale tant que unité, "
                    "disponibilité et périmètre ne sont pas validés."
                ),
                "required_action": (
                    "Confirmer KG, site, propriété, stock libre/bloqué/alloué/périmé, durée de vie et statut des 23 commandes."
                ),
            }
        )
    assert all(row["physical_quantity_available"] is False for row in stock_summary)
    return findings


def validation_checks(
    ca_daily: list[dict[str, Any]],
    ca_summary: list[dict[str, Any]],
    stock_records: list[dict[str, Any]],
    stock_summary: list[dict[str, Any]],
    shortage_records: list[dict[str, Any]],
    context_021: dict[str, Any],
) -> list[dict[str, Any]]:
    def check(check_id: str, passed: bool, detail: str) -> dict[str, Any]:
        return {"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail}

    ca_products = {str(row["product_code"]) for row in ca_daily}
    stock_groups = {str(row["series_id"]) for row in stock_records}
    shortage_counts = defaultdict(int)
    for row in shortage_records:
        shortage_counts[str(row["product_code"])] += 1
    return [
        check("CA_ROWS", len(ca_daily) == 522, f"rows={len(ca_daily)}"),
        check("CA_PRODUCTS", ca_products == {"268091", "268967"}, f"products={sorted(ca_products)}"),
        check(
            "CA_UNIQUE_DATES",
            all(int(row["row_count"]) == int(row["unique_date_count"]) == 261 for row in ca_summary),
            "261 dates uniques attendues par produit",
        ),
        check("STOCK_ROWS", len(stock_records) == 208, f"rows={len(stock_records)}"),
        check("STOCK_GROUPS", len(stock_groups) == 4, f"groups={sorted(stock_groups)}"),
        check(
            "STOCK_VALUE_NOT_QTY",
            all(row["physical_quantity_available"] is False for row in stock_records + stock_summary),
            "aucune quantité physique revendiquée",
        ),
        check(
            "STOCK_WEEKLY_COUNTS",
            all(int(row["snapshot_count"]) == int(row["unique_date_count"]) == 52 for row in stock_summary),
            "52 photos uniques attendues pour chacune des 4 séries",
        ),
        check("SHORTAGE_ROWS", len(shortage_records) == 64, f"rows={len(shortage_records)}"),
        check(
            "SHORTAGE_PRODUCT_COUNTS",
            shortage_counts == {"268091": 32, "268967": 32},
            f"counts={dict(shortage_counts)}",
        ),
        check(
            "021_OPENING_STOCK",
            math.isclose(float(context_021.get("opening_stock_source_kg") or 0.0), 1_142_100.0),
            f"kg={context_021.get('opening_stock_source_kg')}",
        ),
        check(
            "021_OPEN_ORDERS",
            math.isclose(float(context_021.get("opening_order_book_kg") or 0.0), 1_320_000.0)
            and int(context_021.get("opening_order_line_count") or 0) == 23,
            f"kg={context_021.get('opening_order_book_kg')}, lines={context_021.get('opening_order_line_count')}",
        ),
        check(
            "021_REFERENCE_CONSUMPTION",
            math.isclose(float(context_021.get("simulated_consumption_kg") or 0.0), 257_472.0, abs_tol=1e-6)
            and int(context_021.get("simulated_horizon_days") or 0) == 720,
            f"kg={context_021.get('simulated_consumption_kg')}, days={context_021.get('simulated_horizon_days')}",
        ),
    ]


def eur(value: Any) -> str:
    return f"{parse_float(value):,.0f}".replace(",", " ")


def pct(value: Any) -> str:
    return f"{parse_float(value) * 100:.2f}%"


def comparison_report_rows(comparisons: list[dict[str, Any]], product: str) -> list[str]:
    lines: list[str] = []
    for row in comparisons:
        if str(row["product_code"]) != product:
            continue
        observed = row.get("observed_value")
        simulated = row.get("simulated_value")
        if row["scope"] == "service" and observed != "" and simulated != "":
            values = f"{pct(observed)} → {pct(simulated)}"
        elif observed != "" and simulated != "":
            values = f"{eur(observed)} → {eur(simulated)}"
        else:
            values = "non comparable actuellement"
        lines.append(
            f"| {row['scope']} | {values} | {row['comparison_status']} | {row['calibration_reading']} |"
        )
    return lines


def render_report(payload: dict[str, Any]) -> str:
    ca = {str(row["product_code"]): row for row in payload["ca_summary"]}
    stocks = {str(row["series_id"]): row for row in payload["stock_summary"]}
    shortages = {
        (str(row["product_code"]), int(row["snapshot_year"])): row
        for row in payload["projected_shortage_summary"]
    }
    c021 = payload["component_021081_context"]
    lines = [
        "# Bilan factuel des données industrielles 2025",
        "",
        "## Réponse courte",
        "",
        "Les fichiers 2025 permettent de mesurer des montants de chiffre d'affaires livré/perdu, "
        "des valeurs comptables hebdomadaires de stock et des signaux de rupture PF projetés. "
        "Ils ne permettent pas encore d'attribuer une perte réelle à un fournisseur ni de suivre un lot: "
        "les identifiants fournisseur, commande, réception, lot, cause et client ne sont pas reliés dans ces CSV.",
        "",
        "Les mots importants sont donc:",
        "",
        "- **Observé**: valeur présente dans un fichier industriel, avec son périmètre exact.",
        "- **Projeté**: résultat du système de planification à une date de photo; ce n'est pas un incident réalisé.",
        "- **Simulé**: résultat du moteur; utile pour tester des hypothèses, pas une observation 2025.",
        "- **À confirmer**: devise, règle de stock immobilisé et définition des signaux de perte/rupture.",
        "",
        "## Chiffre d'affaires livré et perdu",
        "",
        "Convention de travail: les montants sont présentés comme EUR, mais la devise n'est pas déclarée dans le CSV.",
        "Le ratio ci-dessous est un ratio financier descriptif, pas un OTIF ni un taux de service en unités.",
        "",
        "| Produit | CA livré | CA perdu brut | Part livrée | Signaux Nb_Rep | Jours montant perdu > 0 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for product in ("268091", "268967"):
        row = ca[product]
        lines.append(
            f"| {product} | {eur(row['ca_delivered_source_value'])} | "
            f"{eur(row['ca_lost_raw_source_value'])} | {pct(row['delivered_share_of_raw_potential'])} | "
            f"{row['lost_signal_count']} | {row['days_with_positive_lost_value']} |"
        )
    lines.extend(
        [
            "",
            f"- 268091: {ca['268091']['days_positive_lost_without_signal']} jours ont un montant perdu positif "
            f"mais aucun signal Nb_Rep; une correction négative de "
            f"{ca['268091']['ca_lost_negative_adjustments_source_value']:.2f} est aussi présente.",
            f"- 268967: {ca['268967']['days_positive_lost_without_signal']} jours ont un montant perdu positif "
            f"mais aucun signal Nb_Rep, représentant {eur(ca['268967']['positive_lost_without_signal_source_value'])} "
            "en valeur source.",
            "- Conclusion: le montant perdu et Nb_Rep doivent être analysés séparément tant que la règle Nb_Rep n'est pas fournie.",
            "",
            "## Stocks 2025: ce sont des valeurs, pas des quantités",
            "",
            "Chaque série contient 52 photos hebdomadaires du 6 janvier au 29 décembre 2025.",
            "Aucun de ces CSV ne donne les unités physiques, les lots, les statuts qualité, les magasins ou les prix unitaires.",
            "",
            "| Série source | Code produit présent dans ce CSV | Moyenne | Minimum | Maximum |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for series_id, label, product_from_source in (
        ("component_stock_cos", "Composants immobilisés — fichier Cos", "non"),
        ("component_stock_pharma", "Composants immobilisés — fichier Pharma", "non"),
        ("finished_goods_stock_268091", "PF immobilisé 268091", "268091"),
        ("finished_goods_stock_268967", "PF immobilisé 268967", "268967"),
    ):
        row = stocks[series_id]
        lines.append(
            f"| {label} | {product_from_source} | {eur(row['mean_stock_value_source'])} | "
            f"{eur(row['minimum_stock_value_source'])} | {eur(row['maximum_stock_value_source'])} |"
        )
    lines.extend(
        [
            "",
            "Le lien entre les deux fichiers composants et les deux produits n'est pas présent dans les CSV. "
            "Deux conventions contradictoires existent: le rapport source-truth récent pose explicitement l'hypothèse "
            "268091→Pharma et 268967→Cos, tandis que plusieurs anciens audits utilisent l'inverse. Le présent bilan "
            "ne choisit pas entre elles: ce mapping doit être confirmé par le propriétaire des extractions.",
            "",
            "## Ruptures PF projetées",
            "",
            "Ces chiffres sont des projections prises à plusieurs dates. On ne les additionne pas, car deux photos "
            "peuvent parler de la même future rupture.",
            "",
            "| Produit | Année des photos | Photos non nulles | Maximum semaines projetées | Maximum répétitions |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for product in ("268091", "268967"):
        for year in (2025, 2026):
            row = shortages[(product, year)]
            lines.append(
                f"| {product} | {year} | {row['nonzero_snapshot_count']} / {row['snapshot_count']} | "
                f"{row['maximum_projected_shortage_weeks']:.0f} | "
                f"{row['maximum_projected_shortage_repetition']:.0f} |"
            )
    lines.extend(
        [
            "",
            "Lecture: 268091 porte un signal projeté en début 2025 (maximum 3 semaines), puis plus rien dans les "
            "photos fournies. 268967 n'a pas de signal en 2025 mais un signal projeté récurrent à partir de 2026-S09, "
            "maximum 11 semaines. Cela décrit le plan, pas les ruptures réellement vécues.",
            "",
            "## Point physique à instruire: composant 021081",
            "",
            f"- Stock d'ouverture déclaré: **{eur(c021['opening_stock_source_kg'])} KG**.",
            f"- Commandes ouvertes: **{eur(c021['opening_order_book_kg'])} KG**, "
            f"{c021['opening_order_line_count']} lignes et 4 fournisseurs; ce sont des commandes planifiées, pas des réceptions réalisées.",
            f"- Consommation dans une référence simulée sur {c021['simulated_horizon_days']} jours: "
            f"**{eur(c021['simulated_consumption_kg'])} KG**; aucune arrivée simulée pendant la mesure.",
            f"- Le stock d'ouverture représente {c021['opening_stock_over_horizon_consumption']:.2f} fois cette consommation "
            f"de 720 jours; stock + commandes représentent {c021['opening_plus_orders_over_horizon_consumption']:.2f} fois.",
            "",
            "Si les unités, le périmètre et le rythme simulé sont tous justes, cela correspondrait à plusieurs années de couverture. "
            "C'est d'abord un point de données à valider: stock libre/bloqué/alloué/périmé, site, propriété, durée de vie, "
            "commandes encore actives et unité KG. Ce stock physique ne doit jamais être comparé directement aux CSV de stock "
            "immobilisé en valeur monétaire.",
            "",
            "## Écarts simulation / réel déjà disponibles",
            "",
            "### 268091",
            "",
            "| Périmètre | Observé → simulé | Statut | Lecture |",
            "|---|---:|---|---|",
        ]
    )
    lines.extend(comparison_report_rows(payload["comparisons"], "268091"))
    lines.extend(
        [
            "",
            "### 268967",
            "",
            "| Périmètre | Observé → simulé | Statut | Lecture |",
            "|---|---:|---|---|",
        ]
    )
    lines.extend(comparison_report_rows(payload["comparisons"], "268967"))
    lines.extend(
        [
            "",
            "Lecture de calibration:",
            "",
            "- Le service simulé de référence reste plus optimiste que le ratio financier observé. L'écart est un signal de "
            "calibration, pas une preuve, car euros et unités ne mesurent pas la même chose.",
            "- Sous l'hypothèse récente 268091→Pharma et 268967→Cos, les valeurs composant simulées sont respectivement "
            "environ 44% et 94% au-dessus des moyennes observées appariées. Ces écarts ne sont pas interprétables par produit "
            "tant que le mapping et la définition financière du stock immobilisé ne sont pas confirmés.",
            "- Les anciens résultats fondés sur la convention opposée ne sont pas repris comme vérité dans ce bilan.",
            "- La valeur PF ne valide pas la quantité PF: les CSV réels ne fournissent ni quantité ni coût unitaire.",
            "",
            "## Prévision du risque fournisseur: état de préparation",
            "",
            "Le POC actuel de prédiction apprend sur un historique hebdomadaire et des labels d'incident synthétiques. "
            "Les probabilités qu'il affiche démontrent une chaîne de calcul, pas une fréquence industrielle calibrée. "
            "Le carnet 2025 contient des commandes et dates planifiées; il ne donne pas, ligne par ligne, l'engagement "
            "fournisseur initial puis la réception réelle. Le terme sûr aujourd'hui est donc **signal de priorité à instruire**, "
            "pas **probabilité de défaillance fournisseur**.",
            "",
            "Pour entraîner une probabilité fournisseur × article × site, l'unité minimale doit être la ligne de PO, avec: "
            "identifiants fournisseur/article/site/PO/ligne; dates d'émission, demandée, promise initiale et re-promises; "
            "date de réception réelle; quantités commandée/confirmée/reçue et UOM; défauts, quarantaine et libération; "
            "cause du retard/défaut; actions d'accélération; calendriers et capacité/charge datée.",
            "",
            "## Ce qu'il faut demander à l'industriel",
            "",
            "1. Devise et définition exacte de CA_Livré, CA_Perdu et Nb_Rep_CA_Perdu.",
            "2. Détail stock par article, site, magasin, statut libre/qualité/bloqué, lot, âge/péremption, quantité, UOM, prix et valeur.",
            "3. Définition de Nb_Semaine_Rupture_Produit, horizon de projection et identifiants des ruptures projetées.",
            "4. Chaîne de clés: commande client → lot PF → ordre/lot de production → lots composants → réception → PO → fournisseur.",
            "5. Pour 021081: validation spécifique du million de KG d'ouverture et des 1,32 million de KG de commandes ouvertes.",
            "6. Arbitrage documenté du mapping entre les fichiers composants Cos/Pharma et les codes produit.",
            "",
            "## Fichiers générés",
            "",
            "- `observed_ca_daily_2025.csv` et `observed_ca_monthly_2025.csv`",
            "- `observed_ca_product_summary_2025.csv`",
            "- `observed_stock_value_snapshots_2025.csv` et `observed_stock_value_summary_2025.csv`",
            "- `projected_finished_goods_shortages.csv` et `projected_finished_goods_shortage_summary.csv`",
            "- `component_021081_physical_context.csv`",
            "- `existing_simulation_real_comparisons.csv`",
            "- `component_stock_mapping_hypotheses.csv` et `supplier_risk_prediction_readiness.csv`",
            "- `data_quality_findings.csv`, `validation_checks.csv`, `bilan_observed_2025.json` et `manifest.json`",
            "",
        ]
    )
    return "\n".join(lines)


def build_bilan(
    *,
    source_dir: Path,
    analysis_result_dir: Path,
    reference_run: Path,
    reference_021_run: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ca_daily, ca_monthly, ca_summary, ca_source = build_ca(source_dir)
    stock_records, stock_summary, stock_sources = build_stocks(source_dir)
    shortage_records, shortage_summary, shortage_source = build_projected_shortages(source_dir)
    comparisons = build_service_comparisons(ca_summary, reference_run)
    comparisons.extend(build_stock_comparisons(analysis_result_dir))
    context_rows, context_summary = build_021_context(analysis_result_dir, reference_021_run)
    mapping_rows = mapping_hypotheses()
    prediction_summary, prediction_rows = prediction_readiness()
    findings = build_quality_findings(ca_summary, stock_summary, context_summary)
    checks = validation_checks(
        ca_daily,
        ca_summary,
        stock_records,
        stock_summary,
        shortage_records,
        context_summary,
    )
    payload = {
        "schema_version": "etudecas.observed_2025_supply_bilan.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "scope": (
            "factual 2025 industrial data, planning projections, existing model comparisons and 021081 physical context"
        ),
        "currency_status": "not_declared_in_source; EUR_is_working_convention",
        "supplier_attribution_status": "not_supported_by_available_observed_files",
        "component_stock_product_mapping_status": "unresolved_conflicting_hypotheses",
        "ca_summary": ca_summary,
        "stock_summary": stock_summary,
        "projected_shortage_summary": shortage_summary,
        "component_021081_context": context_summary,
        "component_stock_mapping_hypotheses": mapping_rows,
        "supplier_risk_prediction_readiness": prediction_summary,
        "comparisons": comparisons,
        "data_quality_findings": findings,
        "validation_checks": checks,
    }

    write_csv(output_dir / "observed_ca_daily_2025.csv", ca_daily)
    write_csv(output_dir / "observed_ca_monthly_2025.csv", ca_monthly)
    write_csv(output_dir / "observed_ca_product_summary_2025.csv", ca_summary)
    write_csv(output_dir / "observed_stock_value_snapshots_2025.csv", stock_records)
    write_csv(output_dir / "observed_stock_value_summary_2025.csv", stock_summary)
    write_csv(output_dir / "projected_finished_goods_shortages.csv", shortage_records)
    write_csv(output_dir / "projected_finished_goods_shortage_summary.csv", shortage_summary)
    write_csv(output_dir / "component_021081_physical_context.csv", context_rows)
    write_csv(output_dir / "existing_simulation_real_comparisons.csv", comparisons)
    write_csv(output_dir / "component_stock_mapping_hypotheses.csv", mapping_rows)
    write_csv(output_dir / "supplier_risk_prediction_readiness.csv", prediction_rows)
    write_csv(output_dir / "data_quality_findings.csv", findings)
    write_csv(output_dir / "validation_checks.csv", checks)
    (output_dir / "bilan_observed_2025.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output_dir / "REPORT.md").write_text(render_report(payload), encoding="utf-8")

    source_paths = [ca_source, *stock_sources, shortage_source]
    source_provenance = [
        {
            "source": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "role": "industrial_source",
        }
        for path in source_paths
    ]
    write_csv(output_dir / "source_provenance.csv", source_provenance)
    output_paths = sorted(path for path in output_dir.iterdir() if path.name != "manifest.json")
    manifest = {
        "schema_version": "etudecas.observed_2025_supply_bilan.manifest.v1",
        "generated_at": payload["generated_at"],
        "generator": str(Path(__file__).resolve()),
        "output_dir": str(output_dir.resolve()),
        "all_validation_checks_pass": all(row["status"] == "PASS" for row in checks),
        "files": [
            {"name": path.name, "size_bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in output_paths
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--analysis-result-dir", type=Path, default=ANALYSIS_RESULT_DIR)
    parser.add_argument("--reference-run", type=Path, default=DEFAULT_REFERENCE_RUN)
    parser.add_argument("--reference-021-run", type=Path, default=DEFAULT_021_REFERENCE_RUN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_bilan(
        source_dir=args.source_dir,
        analysis_result_dir=args.analysis_result_dir,
        reference_run=args.reference_run,
        reference_021_run=args.reference_021_run,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir.resolve()),
                "ca_products": len(payload["ca_summary"]),
                "stock_series": len(payload["stock_summary"]),
                "quality_findings": len(payload["data_quality_findings"]),
                "all_checks_pass": all(row["status"] == "PASS" for row in payload["validation_checks"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
