#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .enrichers import enrich_graph_from_excel
from .excel_template import write_excel_template
from .io import load_graph, save_graph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create/apply a generic Excel enrichment workbook for a supply graph JSON.")
    parser.add_argument("--input-json", default="etudecas/donnees/supply_graph_poc.json")
    parser.add_argument("--excel", default="etudecas/config/cases/data_poc_enrichment_input.xlsx")
    parser.add_argument("--output-json", default="etudecas/donnees/supply_graph_poc_enriched_from_excel.json")
    parser.add_argument("--report-json", default="etudecas/donnees/supply_graph_excel_enrichment_report.json")
    parser.add_argument(
        "--case-config-json",
        default="",
        help="Optional case config JSON merged under graph.case_config before creating or applying the workbook.",
    )
    parser.add_argument("--create-template", action="store_true", help="Create the Excel workbook from the input JSON.")
    parser.add_argument("--apply", action="store_true", help="Apply the Excel workbook to the input JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    graph = load_graph(args.input_json)
    if args.case_config_json:
        graph["case_config"] = _load_case_config(args.case_config_json)
    if args.create_template:
        write_excel_template(args.excel, graph)
        print(f"[OK] Excel template written: {Path(args.excel).resolve()}")
    if args.apply:
        enriched, report = enrich_graph_from_excel(graph, args.excel)
        save_graph(args.output_json, enriched)
        Path(args.report_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] Enriched graph written: {Path(args.output_json).resolve()}")
        print(f"[OK] Report written: {Path(args.report_json).resolve()}")
    if not args.create_template and not args.apply:
        raise SystemExit("Nothing to do. Pass --create-template and/or --apply.")


def _load_case_config(path: str) -> dict[str, object]:
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Case config must be a JSON object: {config_path}")
    return data


if __name__ == "__main__":
    main()
