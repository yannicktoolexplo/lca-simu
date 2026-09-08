#!/usr/bin/env python3
"""Reapply current identity and evidence rules to cached SERP results."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from enrich_supplier_context import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PATHS,
    DEFAULT_SITES,
    EVIDENCE_FIELDS,
    RESULT_FIELDS,
    SUMMARY_FIELDS,
    build_evidence_rows,
    build_structural_context,
    canonicalize_url,
    clean,
    read_csv,
    rerank_result_rows,
    safe_float,
    score_result,
    summarize_site,
    write_csv,
    write_summary_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sites", type=Path, default=DEFAULT_SITES)
    parser.add_argument("--paths", type=Path, default=DEFAULT_PATHS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def rescore_cache(sites_path: Path, paths_path: Path, output_dir: Path) -> tuple[int, int, int]:
    sites = read_csv(sites_path)
    site_by_uid = {clean(row.get("site_uid")): row for row in sites}
    previous_summaries = {
        clean(row.get("site_uid")): row
        for row in read_csv(output_dir / "supplier_context_summary.csv")
        if clean(row.get("site_uid"))
    }
    cached_results = read_csv(output_dir / "supplier_context_results.csv")
    rescored_by_site: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in cached_results:
        site_uid = clean(row.get("site_uid"))
        site = site_by_uid.get(site_uid)
        if not site:
            continue
        query_family = clean(row.get("query_family"))
        if not query_family:
            legacy = {
                **row,
                "query_family": "legacy_unclassified",
                "canonical_url": canonicalize_url(row.get("url")),
                "verification_status": "legacy_a_revoir",
                "evidence_strength_score": 0.0,
                "positive_signal_categories": "",
                "positive_signal_hits": "{}",
                "resilience_evidence_score": 0.0,
            }
            rescored_by_site[site_uid].append(legacy)
            continue
        rescored = score_result(
            site,
            {
                "title": row.get("title", ""),
                "description": row.get("description", ""),
                "domain": row.get("domain", ""),
                "url": row.get("url", ""),
            },
            query_family,
        )
        rescored_by_site[site_uid].append({**row, **rescored})

    structural_by_site = build_structural_context(read_csv(paths_path))
    max_mass = max((safe_float(site.get("allocated_mass_kg")) for site in sites), default=1.0)
    max_path_count = max((safe_float(site.get("path_count")) for site in sites), default=1.0)
    summaries: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for site in sites:
        site_uid = clean(site.get("site_uid"))
        rows = rescored_by_site.get(site_uid, [])
        rerank_result_rows(rows)
        results.extend(rows)
        previous = previous_summaries.get(site_uid, {})
        summaries.append(
            summarize_site(
                site,
                clean(previous.get("query")),
                clean(previous.get("provider")) or (clean(rows[0].get("provider")) if rows else ""),
                clean(previous.get("context_search_status")) or ("ok" if rows else "no_results"),
                clean(previous.get("retrieved_at_utc")) or (clean(rows[0].get("retrieved_at_utc")) if rows else ""),
                rows,
                max_mass=max_mass,
                max_path_count=max_path_count,
                structural_context=structural_by_site.get(site_uid, {}),
            )
        )

    evidence = build_evidence_rows(results)
    summaries.sort(key=lambda row: clean(row.get("supplier")))
    results.sort(
        key=lambda row: (
            clean(row.get("supplier")),
            safe_float(row.get("result_rank"), 999.0),
        )
    )
    write_csv(output_dir / "supplier_context_summary.csv", summaries, SUMMARY_FIELDS)
    write_csv(output_dir / "supplier_context_results.csv", results, RESULT_FIELDS)
    write_csv(output_dir / "supplier_context_evidence.csv", evidence, EVIDENCE_FIELDS)
    write_summary_json(
        output_dir.parent / "summaries" / "supplier_context_summary.json",
        summaries,
        results,
        evidence,
    )
    return len(results), len(evidence), len(summaries)


def main() -> int:
    args = parse_args()
    result_count, evidence_count, summary_count = rescore_cache(args.sites, args.paths, args.output_dir)
    print(
        f"Rescored {result_count} cached results into {evidence_count} evidence rows "
        f"for {summary_count} sites"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
