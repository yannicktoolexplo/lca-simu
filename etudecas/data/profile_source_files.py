#!/usr/bin/env python3
"""Profile canonical source files for the Etudecas case.

The script is intentionally lightweight: it does not transform business data.
It inventories source files, detects CSV structure, and writes a human-readable
report so new inputs can be reviewed before being wired into simulation KPIs.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "source"
REPORTS_DIR = ROOT / "reports"
MANIFEST_PATH = ROOT / "MANIFEST.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def detect_encoding(path: Path) -> str:
    sample = path.read_bytes()[:8192]
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def detect_delimiter(text: str) -> str:
    try:
        return csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        return ";"


def normalize_cell(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_float(value: str) -> float | None:
    text = normalize_cell(value)
    if not text:
        return None
    text = text.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_date_prefix(value: str) -> str | None:
    text = normalize_cell(value)
    if not text:
        return None
    # Keep the business date as text; source formats are mixed.
    return text[:10]


def is_identifier_column(column: str) -> bool:
    lowered = column.lower()
    identifier_terms = ("code", "article", "sku", "item", "id", "numero", "numéro")
    return any(term in lowered for term in identifier_terms)


def csv_profile(path: Path) -> dict[str, Any]:
    encoding = detect_encoding(path)
    text = path.read_text(encoding=encoding, errors="replace")
    delimiter = detect_delimiter(text)
    rows: list[dict[str, str]] = []
    with path.open("r", encoding=encoding, newline="", errors="replace") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            rows.append({str(key): normalize_cell(value) for key, value in row.items()})

    non_empty_by_column: dict[str, int] = defaultdict(int)
    numeric_stats: dict[str, dict[str, Any]] = {}
    date_ranges: dict[str, dict[str, Any]] = {}
    unique_counts: dict[str, int] = {}
    for column in fieldnames:
        values = [normalize_cell(row.get(column)) for row in rows]
        non_empty = [value for value in values if value]
        non_empty_by_column[column] = len(non_empty)
        unique_counts[column] = len(set(non_empty))
        numeric_values = [parsed for value in non_empty if (parsed := parse_float(value)) is not None]
        if (
            not is_identifier_column(column)
            and numeric_values
            and len(numeric_values) >= max(2, int(0.5 * len(non_empty)))
        ):
            numeric_stats[column] = {
                "count": len(numeric_values),
                "min": min(numeric_values),
                "max": max(numeric_values),
                "sum": sum(numeric_values),
            }
        if "date" in column.lower() or "week" in column.lower():
            dates = sorted({parsed for value in non_empty if (parsed := parse_date_prefix(value))})
            if dates:
                date_ranges[column] = {
                    "min": dates[0],
                    "max": dates[-1],
                    "unique": len(dates),
                }

    return {
        "type": "csv",
        "encoding": encoding,
        "delimiter": delimiter,
        "row_count": len(rows),
        "columns": fieldnames,
        "non_empty_by_column": dict(non_empty_by_column),
        "unique_counts": unique_counts,
        "numeric_stats": numeric_stats,
        "date_ranges": date_ranges,
        "sample_rows": rows[:3],
    }


def basic_file_profile(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return csv_profile(path)
    return {
        "type": suffix.lstrip(".") or "file",
        "row_count": None,
        "columns": [],
        "note": "Not profiled deeply by this lightweight source profiler.",
    }


def profile_sources(manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    source_files = [str(name) for name in manifest.get("canonical_source_files") or []]
    business_refs = manifest.get("business_reference_files") if isinstance(manifest.get("business_reference_files"), dict) else {}
    profiles: list[dict[str, Any]] = []
    for name in source_files:
        path = SOURCE_DIR / name
        entry: dict[str, Any] = {
            "name": name,
            "path": str(path).replace("\\", "/"),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "business_reference": business_refs.get(name, {}),
        }
        if path.exists():
            entry.update(basic_file_profile(path))
        profiles.append(entry)
    return {
        "schema_version": "etudecas.source_profile.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path).replace("\\", "/"),
        "source_dir": str(SOURCE_DIR).replace("\\", "/"),
        "file_count": len(profiles),
        "missing_count": sum(1 for item in profiles if not item["exists"]),
        "business_reference_count": sum(1 for item in profiles if item.get("business_reference")),
        "files": profiles,
    }


def format_number(value: Any) -> str:
    if isinstance(value, (int, float)):
        if abs(float(value)) >= 1000:
            return f"{float(value):,.1f}".replace(",", " ")
        return f"{float(value):.3g}"
    return str(value)


def format_row_count(value: Any) -> str:
    return "n/a" if value is None else str(value)


def describe_product_scope(scope: Any) -> str | None:
    if not isinstance(scope, dict):
        return None
    parts: list[str] = []
    business_name = scope.get("business_name")
    if business_name:
        parts.append(f"domaine {business_name}")
    finished_code = scope.get("finished_product_code")
    if finished_code:
        parts.append(f"PF {finished_code}")
    finished_codes = scope.get("finished_product_codes")
    if isinstance(finished_codes, list) and finished_codes:
        parts.append("PF " + ", ".join(str(code) for code in finished_codes))
    item_id = scope.get("finished_product_item_id")
    if item_id:
        parts.append(str(item_id))
    item_ids = scope.get("finished_product_item_ids")
    if isinstance(item_ids, list) and item_ids:
        parts.append(", ".join(str(item) for item in item_ids))
    scope_text = scope.get("scope")
    if scope_text:
        parts.append(str(scope_text))
    assumption = scope.get("assumption")
    if assumption:
        parts.append("Hypothese: " + str(assumption))
    return "; ".join(parts) if parts else None


def markdown_report(profile: dict[str, Any]) -> str:
    lines = [
        "# Profil des sources Etudecas",
        "",
        f"- Fichiers inventoriés: {profile.get('file_count', 0)}",
        f"- Fichiers métier de référence: {profile.get('business_reference_count', 0)}",
        f"- Fichiers manquants: {profile.get('missing_count', 0)}",
        "",
        "## Synthèse",
        "",
        "| Fichier | Type | Lignes | Colonnes | Période | Rôle |",
        "|---|---:|---:|---:|---|---|",
    ]
    for item in profile.get("files", []):
        date_ranges = item.get("date_ranges") if isinstance(item.get("date_ranges"), dict) else {}
        period = "n/a"
        if date_ranges:
            first_range = next(iter(date_ranges.values()))
            period = f"{first_range.get('min')} -> {first_range.get('max')}"
        role = (item.get("business_reference") or {}).get("role", "")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("name", "")),
                    str(item.get("type", "missing") if item.get("exists") else "missing"),
                    format_row_count(item.get("row_count")),
                    str(len(item.get("columns") or [])),
                    period,
                    role or "source canonique",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Fichiers métier de référence", ""])
    for item in profile.get("files", []):
        business = item.get("business_reference") or {}
        if not business:
            continue
        lines.extend(
            [
                f"### {item.get('name')}",
                "",
                f"- Rôle: {business.get('role', 'n/a')}",
                f"- Usage prévu: {business.get('intended_use', 'n/a')}",
                f"- Mesure: {business.get('measurement', 'n/a')}",
                f"- Lignes: {format_row_count(item.get('row_count'))}",
                f"- Colonnes: {', '.join(item.get('columns') or [])}",
            ]
        )
        product_scope = describe_product_scope(business.get("product_scope"))
        if product_scope:
            lines.append(f"- Périmètre produit: {product_scope}")
        comparison_note = business.get("comparison_note")
        if comparison_note:
            lines.append(f"- Comparaison simulation: {comparison_note}")
        numeric_stats = item.get("numeric_stats") if isinstance(item.get("numeric_stats"), dict) else {}
        if numeric_stats:
            lines.extend(["", "| Colonne numérique | Min | Max | Somme |", "|---|---:|---:|---:|"])
            for column, stats in numeric_stats.items():
                lines.append(
                    f"| {column} | {format_number(stats.get('min'))} | {format_number(stats.get('max'))} | {format_number(stats.get('sum'))} |"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--output-json", type=Path, default=REPORTS_DIR / "source_data_profile.json")
    parser.add_argument("--output-md", type=Path, default=REPORTS_DIR / "source_data_profile.md")
    args = parser.parse_args()

    profile = profile_sources(args.manifest)
    write_json(args.output_json, profile)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_report(profile), encoding="utf-8")
    print(f"[OK] Source profile JSON: {args.output_json}")
    print(f"[OK] Source profile MD: {args.output_md}")


if __name__ == "__main__":
    main()
