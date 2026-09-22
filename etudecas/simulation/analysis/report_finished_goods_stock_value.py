"""Compare real finished-goods stock snapshots with simulated PF stock value."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


SOURCE_DIR = REPO_ROOT / "etudecas" / "data" / "source"
SIM_START_DATE = date(2025, 1, 1)
ALIGNMENTS = {"same_day": 0, "previous_day": -1}


@dataclass(frozen=True)
class Stats:
    count: int
    mean: float
    median: float
    minimum: float
    maximum: float


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(" ", "").replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def stats(values: list[float]) -> Stats:
    if not values:
        return Stats(0, 0.0, 0.0, 0.0, 0.0)
    return Stats(len(values), statistics.mean(values), statistics.median(values), min(values), max(values))


def read_csv_rows(path: Path, *, delimiter: str | None = None) -> list[dict[str, str]]:
    encodings = ("utf-8-sig", "cp1252", "latin1")
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            with path.open(encoding=encoding, newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                if delimiter:
                    return list(csv.DictReader(handle, delimiter=delimiter))
                else:
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
                    except csv.Error:
                        dialect = csv.excel
                return list(csv.DictReader(handle, dialect=dialect))
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def find_source_file(pattern: str) -> Path:
    matches = sorted(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one source file for {pattern}, found {len(matches)}")
    return matches[0]


def read_observed_pf_stock(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in read_csv_rows(path):
        keys = list(row)
        item_key = next((key for key in keys if "article" in key.lower()), keys[0] if keys else "")
        date_key = next((key for key in keys if "date" in key.lower()), keys[1] if len(keys) > 1 else "")
        value_key = next((key for key in keys if "valeur" in key.lower()), keys[-1] if keys else "")
        if not item_key or not date_key or not value_key:
            continue
        try:
            snapshot_date = datetime.fromisoformat(str(row[date_key])).date()
        except ValueError:
            continue
        rows.append(
            {
                "product_code": str(row[item_key]).strip(),
                "date": snapshot_date.isoformat(),
                "day": (snapshot_date - SIM_START_DATE).days,
                "observed_stock_value_eur": parse_float(row[value_key]),
            }
        )
    return [row for row in rows if int(row["day"]) >= 0 and row["product_code"]]


def read_simulated_pf_stock(run_dir: Path) -> dict[str, dict[int, dict[str, Any]]]:
    path = run_dir / "data" / "finished_goods_stock_value_daily.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing finished-goods valuation artifact: {path}")
    out: dict[str, dict[int, dict[str, Any]]] = {}
    for row in read_csv_rows(path):
        if str(row.get("location_type") or "") != "total":
            continue
        product_code = str(row.get("product_code") or "")
        day = int(parse_float(row.get("day")))
        out.setdefault(product_code, {})[day] = {
            "sim_stock_qty": parse_float(row.get("stock_qty")),
            "sim_stock_value_eur": parse_float(row.get("stock_value_eur")),
            "unit_value_eur": parse_float(row.get("unit_value_eur")),
            "value_source": row.get("value_source") or "",
            "is_fallback_unit_value": str(row.get("is_fallback_unit_value") or "").lower() == "true",
            "valuation_status": row.get("valuation_status") or "",
            "missing_component_count": parse_float(row.get("missing_component_count")),
            "missing_components": row.get("missing_components") or "",
        }
    return out


def pair_snapshots(
    observed: list[dict[str, Any]],
    simulated: dict[str, dict[int, dict[str, Any]]],
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for row in observed:
        product_code = str(row["product_code"])
        for alignment, offset in ALIGNMENTS.items():
            sim_day = int(row["day"]) + offset
            sim = simulated.get(product_code, {}).get(sim_day)
            if not sim:
                continue
            qty = float(sim["sim_stock_qty"])
            observed_value = float(row["observed_stock_value_eur"])
            pairs.append(
                {
                    "product_code": product_code,
                    "alignment": alignment,
                    "snapshot_date": row["date"],
                    "source_day": row["day"],
                    "sim_day": sim_day,
                    "observed_stock_value_eur": observed_value,
                    "sim_stock_qty": qty,
                    "sim_stock_value_eur": sim["sim_stock_value_eur"],
                    "sim_unit_value_eur": sim["unit_value_eur"],
                    "observed_implied_unit_value_eur": observed_value / qty if qty > 0 else 0.0,
                    "value_source": sim["value_source"],
                    "is_fallback_unit_value": sim["is_fallback_unit_value"],
                    "valuation_status": sim.get("valuation_status", ""),
                    "missing_component_count": sim.get("missing_component_count", 0.0),
                    "missing_components": sim.get("missing_components", ""),
                }
            )
    return pairs


def comparison_rows(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in pairs:
        groups.setdefault((str(row["product_code"]), str(row["alignment"])), []).append(row)
    for (product_code, alignment), scoped in sorted(groups.items()):
        observed = [float(row["observed_stock_value_eur"]) for row in scoped]
        simulated = [float(row["sim_stock_value_eur"]) for row in scoped]
        qty = [float(row["sim_stock_qty"]) for row in scoped]
        implied = [float(row["observed_implied_unit_value_eur"]) for row in scoped if float(row["observed_implied_unit_value_eur"]) > 0]
        observed_stats = stats(observed)
        simulated_stats = stats(simulated)
        implied_stats = stats(implied)
        mean_gap = simulated_stats.mean - observed_stats.mean
        sim_unit_value = parse_float(scoped[0].get("sim_unit_value_eur"))
        implied_unit_value = implied_stats.mean
        rows.append(
            {
                "product_code": product_code,
                "alignment": alignment,
                "snapshot_count": len(scoped),
                "observed_mean_eur": observed_stats.mean,
                "observed_median_eur": observed_stats.median,
                "simulated_mean_eur": simulated_stats.mean,
                "mean_gap_eur": mean_gap,
                "mean_gap_pct": (mean_gap / observed_stats.mean * 100.0) if observed_stats.mean else 0.0,
                "mean_sim_stock_qty": statistics.mean(qty) if qty else 0.0,
                "sim_unit_value_eur": sim_unit_value,
                "observed_implied_unit_mean_eur": implied_stats.mean,
                "observed_implied_unit_min_eur": implied_stats.minimum,
                "observed_implied_unit_max_eur": implied_stats.maximum,
                "unit_value_gap_eur": implied_unit_value - sim_unit_value,
                "unit_value_gap_pct": ((implied_unit_value - sim_unit_value) / implied_unit_value * 100.0)
                if implied_unit_value
                else 0.0,
                "value_source": scoped[0].get("value_source", ""),
                "fallback_unit_value": any(bool(row.get("is_fallback_unit_value")) for row in scoped),
                "valuation_status": scoped[0].get("valuation_status", ""),
                "missing_component_count": scoped[0].get("missing_component_count", 0.0),
                "missing_components": scoped[0].get("missing_components", ""),
            }
        )
    return rows


def euro(value: Any) -> str:
    return f"{parse_float(value):,.0f} EUR".replace(",", " ")


def write_markdown(path: Path, rows: list[dict[str, Any]], pairs: list[dict[str, Any]], source_path: Path, run_dir: Path) -> None:
    previous = [row for row in rows if row["alignment"] == "previous_day"]
    lines = [
        "# Stock PF immobilise - verification source vs simulation",
        "",
        f"- Run: `{run_dir}`",
        f"- Source PF: `{source_path}`",
        "",
        "## Lecture metier",
        "",
        "- Le CSV source donne une valeur de stock PF par article, pas la quantite.",
        "- La simulation donne la quantite de PF en usine + DC.",
        "- La valorisation simulation applique la regle metier: PF = cout de production, MP/composants = cout d'achat.",
        "- Si le cout de production PF est partiel ou retombe sur une valeur fallback, le rapport l'indique explicitement.",
        "- L'alignement `previous_day` est prioritaire car les photos DMP sont prises vers 00:05/00:06.",
        "",
        "## Resultat principal",
        "",
        "| Produit | Alignement | Reel moyen | Simulation moyenne | Ecart | Ecart % | Qte sim moyenne | Cout PF sim | Cout source implicite | Ecart cout/unite | Lecture cout | Manquants |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in previous:
        source = str(row["value_source"])
        if row["fallback_unit_value"]:
            source += " (fallback)"
        missing = str(row.get("missing_components") or "")
        status = str(row.get("valuation_status") or source)
        lines.append(
            f"| {row['product_code']} | {row['alignment']} | {euro(row['observed_mean_eur'])} | "
            f"{euro(row['simulated_mean_eur'])} | {euro(row['mean_gap_eur'])} | "
            f"{parse_float(row['mean_gap_pct']):.1f}% | {parse_float(row['mean_sim_stock_qty']):,.0f} | "
            f"{parse_float(row['sim_unit_value_eur']):.4f} | "
            f"{parse_float(row['observed_implied_unit_mean_eur']):.4f} | "
            f"{parse_float(row['unit_value_gap_eur']):.4f} | {status} / {source} | {missing or '-'} |".replace(",", " ")
        )
    lines.extend(
        [
            "",
            "## Point de vigilance",
            "",
            "Si `Source valeur` contient `fallback`, l'ecart ne prouve pas un ecart de stock physique: il peut venir de la valorisation PF.",
            "Si `Lecture cout` contient `partial_production_cost`, le PF est valorise par le cout BOM disponible mais un ou plusieurs composants n'ont pas encore de prix fiable.",
            "L'ecart cout/unite compare le cout PF simule au cout unitaire implicite de la source; il sert a quantifier le cout manquant ou l'overhead non encore modele.",
            "La regle cible est: PF = cout de production; MP/composants = cout d'achat.",
            "",
            "## Fichiers generes",
            "",
            f"- Snapshot pairs: `{path.with_name('finished_goods_stock_snapshot_pairs.csv')}`",
            f"- Comparaison CSV: `{path.with_name('finished_goods_stock_comparison.csv')}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(*, run_dir: Path, output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = output_dir or run_dir / "reports" / "source_truth_finished_goods_stock"
    source_path = find_source_file("Stock_PF_Immobilis*.csv")
    observed = read_observed_pf_stock(source_path)
    simulated = read_simulated_pf_stock(run_dir)
    pairs = pair_snapshots(observed, simulated)
    rows = comparison_rows(pairs)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "finished_goods_stock_snapshot_pairs.csv", pairs)
    write_csv(output_dir / "finished_goods_stock_comparison.csv", rows)
    write_markdown(output_dir / "finished_goods_stock_comparison.md", rows, pairs, source_path, run_dir)
    payload = {
        "schema_version": "etudecas.finished_goods_stock_comparison.v1",
        "run_dir": str(run_dir.resolve(strict=False)),
        "source": str(source_path.resolve(strict=False)),
        "rows": rows,
        "snapshot_pairs": pairs,
    }
    (output_dir / "finished_goods_stock_comparison.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "rows": len(rows),
        "snapshot_pairs": len(pairs),
        "markdown": str(output_dir / "finished_goods_stock_comparison.md"),
        "csv": str(output_dir / "finished_goods_stock_comparison.csv"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    summary = build_report(run_dir=args.run_dir, output_dir=args.output_dir)
    print(
        "[OK] finished_goods_stock_report "
        f"rows={summary['rows']} snapshot_pairs={summary['snapshot_pairs']}"
    )


if __name__ == "__main__":
    main()
