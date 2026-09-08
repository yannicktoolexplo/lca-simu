#!/usr/bin/env python3
"""Retry failed supplier-context SERP attempts without repeating successful queries."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from enrich_supplier_context import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PATHS,
    DEFAULT_SITES,
    RESULT_FIELDS,
    SCORING_RULES_VERSION,
    SEARCH_ATTEMPT_FIELDS,
    SEARCH_PLAN_VERSION,
    clean,
    read_csv,
    score_result,
    search_results,
    write_csv,
)
from rescore_supplier_context_cache import rescore_cache


ATTEMPT_HISTORY_FIELDS = [
    "attempt_sequence_id",
    "parent_query_id",
    *SEARCH_ATTEMPT_FIELDS,
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sites", type=Path, default=DEFAULT_SITES)
    parser.add_argument("--paths", type=Path, default=DEFAULT_PATHS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--provider", default="brightdata_serp_api")
    parser.add_argument("--serp-engine", default="google")
    parser.add_argument("--region", default="fr-fr")
    parser.add_argument("--results-per-query", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--statuses", default="error")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--simplify-no-results", action="store_true")
    return parser.parse_args()


def simplified_query(attempt: dict[str, Any]) -> str:
    supplier = clean(attempt.get("supplier"))
    family = clean(attempt.get("query_family"))
    suffixes = {
        "identite_specialite": "company aerospace supplier products",
        "certification_qualite": "aerospace certification AS9100 EN9100",
        "incident_operationnel": "plant incident fire disruption shutdown",
        "fragilite_financiere": "company restructuring insolvency financial",
        "capacite_resilience": "investment expansion capacity aerospace",
        "dependance_substitution": "supply shortage sole source dependency",
        "exposition_climatique": "site flood storm heatwave weather disruption",
    }
    return f'"{supplier}" {suffixes.get(family, "aerospace supplier")}'


def execute_attempt(
    args: argparse.Namespace,
    attempt: dict[str, Any],
    query: str,
) -> tuple[list[dict[str, str]], str, str, str, float]:
    if args.delay > 0:
        time.sleep(args.delay)
    started = time.monotonic()
    requested_at = datetime.now(timezone.utc).isoformat()
    try:
        raw_results = search_results(
            args.provider,
            query,
            max(1, args.results_per_query),
            args.region,
            args.serp_engine,
        )
        status = "ok" if raw_results else "no_results"
        error_type = ""
    except Exception as exc:  # Network/provider errors must remain auditable in the attempt row.
        raw_results = []
        status = "error"
        error_type = type(exc).__name__
    return raw_results, status, error_type, requested_at, round(time.monotonic() - started, 4)


def main() -> int:
    args = parse_args()
    site_by_uid = {
        clean(row.get("site_uid")): row
        for row in read_csv(args.sites)
        if clean(row.get("site_uid"))
    }
    attempt_path = args.output_dir / "supplier_context_search_attempts.csv"
    history_path = args.output_dir / "supplier_context_search_attempt_history.csv"
    result_path = args.output_dir / "supplier_context_results.csv"
    attempts = read_csv(attempt_path)
    history = read_csv(history_path)
    history_ids = {clean(row.get("attempt_sequence_id")) for row in history}
    for current in attempts:
        current["search_plan_version"] = clean(current.get("search_plan_version")) or SEARCH_PLAN_VERSION
        current["scoring_rules_version"] = clean(current.get("scoring_rules_version")) or SCORING_RULES_VERSION
        digest = hashlib.sha1(
            "|".join(
                [
                    clean(current.get("query_id")),
                    clean(current.get("requested_at_utc")),
                    clean(current.get("status")),
                ]
            ).encode("utf-8")
        ).hexdigest()[:16]
        sequence_id = f"try-{digest}"
        if sequence_id in history_ids:
            continue
        history.append(
            {
                "attempt_sequence_id": sequence_id,
                "parent_query_id": clean(current.get("query_id")),
                **current,
            }
        )
        history_ids.add(sequence_id)
    results = read_csv(result_path)
    retry_statuses = {token.strip() for token in args.statuses.split(",") if token.strip()}
    targets = [row for row in attempts if clean(row.get("status")) in retry_statuses]
    result_query_ids = {clean(row.get("query_id")) for row in results}

    planned: list[tuple[dict[str, Any], dict[str, str], str]] = []
    for attempt in targets:
        site = site_by_uid.get(clean(attempt.get("site_uid")))
        if not site:
            continue
        query = (
            simplified_query(attempt)
            if args.simplify_no_results and clean(attempt.get("status")) == "no_results"
            else clean(attempt.get("query"))
        )
        planned.append((attempt, site, query))

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        outcomes = list(
            executor.map(
                lambda item: execute_attempt(args, item[0], item[2]),
                planned,
            )
        )

    success_count = 0
    for index, ((attempt, site, executed_query), outcome) in enumerate(zip(planned, outcomes), 1):
        original_attempt = dict(attempt)
        original_query_id = clean(attempt.get("query_id"))
        site_uid = clean(attempt.get("site_uid"))
        query_id = original_query_id
        if executed_query != clean(attempt.get("query")):
            digest = hashlib.sha1(
                "|".join(
                    [
                        SEARCH_PLAN_VERSION,
                        site_uid,
                        clean(attempt.get("query_family")),
                        executed_query,
                    ]
                ).encode("utf-8")
            ).hexdigest()[:16]
            query_id = f"qry-{digest}"
        raw_results, status, error_type, requested_at, duration = outcome
        if error_type:
            print(f"[{index}/{len(targets)}] {attempt.get('supplier')} -> error:{error_type}")
        original_sequence = hashlib.sha1(
            "|".join(
                [
                    original_query_id,
                    clean(original_attempt.get("requested_at_utc")),
                    clean(original_attempt.get("status")),
                ]
            ).encode("utf-8")
        ).hexdigest()[:16]
        if f"try-{original_sequence}" not in history_ids:
            history.append(
                {
                    "attempt_sequence_id": f"try-{original_sequence}",
                    "parent_query_id": original_query_id,
                    **original_attempt,
                }
            )
            history_ids.add(f"try-{original_sequence}")
        attempt.update(
            {
                "query_id": query_id,
                "search_plan_version": SEARCH_PLAN_VERSION,
                "scoring_rules_version": SCORING_RULES_VERSION,
                "query": executed_query,
                "provider": args.provider,
                "serp_engine": args.serp_engine,
                "search_region": args.region,
                "requested_at_utc": requested_at,
                "duration_seconds": duration,
                "status": status,
                "error_type": error_type,
                "result_count": len(raw_results),
            }
        )
        retry_sequence = hashlib.sha1(
            "|".join([query_id, requested_at, status]).encode("utf-8")
        ).hexdigest()[:16]
        history.append(
            {
                "attempt_sequence_id": f"try-{retry_sequence}",
                "parent_query_id": original_query_id,
                **attempt,
            }
        )
        if status == "ok" and (original_query_id in result_query_ids or query_id in result_query_ids):
            results = [
                row
                for row in results
                if clean(row.get("query_id")) not in {original_query_id, query_id}
            ]
            result_query_ids.discard(original_query_id)
            result_query_ids.discard(query_id)
        for original_rank, raw in enumerate(raw_results, 1):
            scored = score_result(site, raw, clean(attempt.get("query_family")))
            results.append(
                {
                    "site_uid": site_uid,
                    "supplier": site.get("name", ""),
                    "roles": site.get("roles", ""),
                    "country_code": site.get("country_code", ""),
                    "location": site.get("location", ""),
                    "lat": site.get("lat", ""),
                    "lon": site.get("lon", ""),
                    "query": executed_query,
                    "query_id": query_id,
                    "query_family": attempt.get("query_family", ""),
                    "search_plan_version": clean(attempt.get("search_plan_version")) or SEARCH_PLAN_VERSION,
                    "provider": args.provider,
                    "serp_engine": args.serp_engine,
                    "search_region": args.region,
                    "search_status": status,
                    "retrieved_at_utc": requested_at,
                    "result_rank": original_rank,
                    "serp_rank_original": original_rank,
                    **scored,
                }
            )
        if status == "ok":
            success_count += 1

    write_csv(result_path, results, RESULT_FIELDS)
    write_csv(attempt_path, attempts, SEARCH_ATTEMPT_FIELDS)
    write_csv(history_path, history, ATTEMPT_HISTORY_FIELDS)
    result_count, evidence_count, summary_count = rescore_cache(args.sites, args.paths, args.output_dir)
    print(
        f"Retried {len(planned)} attempts: {success_count} successful; "
        f"rescored {result_count} results, {evidence_count} evidence rows, {summary_count} sites"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
