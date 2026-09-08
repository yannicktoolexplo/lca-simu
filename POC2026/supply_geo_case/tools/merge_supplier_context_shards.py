#!/usr/bin/env python3
"""Merge independent supplier-context SERP shards into the production cache."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from enrich_supplier_context import (
    DEFAULT_PATHS,
    DEFAULT_SITES,
    RESULT_FIELDS,
    SEARCH_ATTEMPT_FIELDS,
    SUMMARY_FIELDS,
    canonicalize_url,
    clean,
    read_csv,
    safe_float,
    write_csv,
)
from rescore_supplier_context_cache import rescore_cache


def deduplicate(
    rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
    *,
    score_field: str = "",
) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(clean(row.get(field)) for field in key_fields)
        if not any(key):
            continue
        previous = by_key.get(key)
        if previous is None or (
            score_field
            and safe_float(row.get(score_field)) > safe_float(previous.get(score_field))
        ):
            by_key[key] = row
    return list(by_key.values())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shards-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sites", type=Path, default=DEFAULT_SITES)
    parser.add_argument("--paths", type=Path, default=DEFAULT_PATHS)
    return parser.parse_args()


def deduplicate_attempts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    status_priority = {"ok": 3, "no_results": 2, "error": 1}
    by_query: dict[str, dict[str, Any]] = {}
    for row in rows:
        query_id = clean(row.get("query_id"))
        if not query_id:
            continue
        previous = by_query.get(query_id)
        candidate_key = (
            status_priority.get(clean(row.get("status")), 0),
            clean(row.get("requested_at_utc")),
        )
        previous_key = (
            status_priority.get(clean(previous.get("status")), 0),
            clean(previous.get("requested_at_utc")),
        ) if previous else (-1, "")
        if previous is None or candidate_key > previous_key:
            by_query[query_id] = row
    return list(by_query.values())


def main() -> int:
    args = parse_args()
    shard_dirs = sorted(
        path
        for path in args.shards_root.iterdir()
        if path.is_dir() and (path / "supplier_context_summary.csv").exists()
    )
    if not shard_dirs:
        raise SystemExit(f"No shard directories found in {args.shards_root}")

    summaries: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for shard in shard_dirs:
        summaries.extend(read_csv(shard / "supplier_context_summary.csv"))
        results.extend(read_csv(shard / "supplier_context_results.csv"))
        attempts.extend(read_csv(shard / "supplier_context_search_attempts.csv"))

    summaries = deduplicate(summaries, ("site_uid",), score_field="data_confidence_score")
    for row in results:
        row["canonical_url"] = clean(row.get("canonical_url")) or canonicalize_url(row.get("url"))
    results = deduplicate(results, ("site_uid", "query_family", "canonical_url"), score_field="evidence_strength_score")
    attempts = deduplicate_attempts(attempts)

    summaries.sort(key=lambda row: clean(row.get("supplier")))
    results.sort(
        key=lambda row: (
            clean(row.get("supplier")),
            clean(row.get("query_family")),
            safe_float(row.get("serp_rank_original"), 999.0),
        )
    )
    attempts.sort(key=lambda row: (clean(row.get("supplier")), clean(row.get("query_family"))))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "supplier_context_summary.csv", summaries, SUMMARY_FIELDS)
    write_csv(args.output_dir / "supplier_context_results.csv", results, RESULT_FIELDS)
    write_csv(args.output_dir / "supplier_context_search_attempts.csv", attempts, SEARCH_ATTEMPT_FIELDS)
    result_count, evidence_count, summary_count = rescore_cache(args.sites, args.paths, args.output_dir)
    print(
        f"Merged {len(shard_dirs)} shards: {summary_count} sites, "
        f"{result_count} results, {evidence_count} evidence rows, {len(attempts)} attempts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
