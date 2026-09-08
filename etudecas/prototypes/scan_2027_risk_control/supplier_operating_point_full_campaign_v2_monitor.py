"""Read-only progress monitor for the supplier operating-point V2 campaign.

The monitor discovers ``shards/*/progress.json`` below a campaign directory.
It never writes into the campaign and does not import or invoke the simulation
runner.  The small alias layer makes it usable while a runner is being upgraded,
provided every shard exposes the same basic progress counters.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_EXPECTED_SHARDS = 18
DEFAULT_PARALLEL_WORKERS = 4
DEFAULT_INTERVAL_SECONDS = 30.0
DEFAULT_STALE_AFTER_SECONDS = 30.0 * 60.0


def _first(payload: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


def _nonnegative_int(value: Any, *, field: str, path: Path) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}: {field} is not an integer") from exc
    if number < 0:
        raise ValueError(f"{path}: {field} is negative")
    return number


def _optional_nonnegative_float(value: Any, *, field: str, path: Path) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}: {field} is not numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{path}: {field} must be finite and non-negative")
    return number


def _parse_utc(value: Any, *, field: str, path: Path) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{path}: {field} is not an ISO timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _running_count(value: Any, *, path: Path) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return _nonnegative_int(value, field="running", path=path)


@dataclass(frozen=True)
class ShardProgress:
    path: str
    shard_id: str
    campaign_signature: str
    operating_point_id: str
    seed_block: str
    status: str
    planned: int
    completed: int
    failed: int
    running: int
    updated_at_utc: str
    started_at_utc: str
    elapsed_seconds: float | None
    mean_completed_case_seconds: float | None
    eta_seconds: float | None
    error_count: int
    stale: bool


def read_shard_progress(
    path: Path,
    *,
    now: datetime,
    stale_after_seconds: float,
) -> ShardProgress:
    """Read and normalize one shard progress document."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: unreadable progress JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: progress JSON must be an object")

    planned = _nonnegative_int(
        _first(payload, "planned_case_count", "planned", default=0),
        field="planned",
        path=path,
    )
    completed = _nonnegative_int(
        _first(payload, "completed_case_count", "completed", default=0),
        field="completed",
        path=path,
    )
    failed = _nonnegative_int(
        _first(payload, "failed_case_count", "failed", default=0),
        field="failed",
        path=path,
    )
    running = _running_count(
        _first(payload, "running_case_keys", "running", default=[]), path=path
    )
    if completed > planned:
        raise ValueError(f"{path}: completed exceeds planned")
    if failed > planned:
        raise ValueError(f"{path}: failed exceeds planned")

    updated = _parse_utc(
        _first(payload, "updated_at_utc", "updated_at"),
        field="updated_at_utc",
        path=path,
    )
    started = _parse_utc(
        _first(payload, "started_at_utc", "started_at"),
        field="started_at_utc",
        path=path,
    )
    stale = bool(
        updated is not None
        and str(payload.get("status") or "").lower() == "running"
        and (now - updated).total_seconds() > stale_after_seconds
    )
    errors = payload.get("errors") or []
    error_count = len(errors) if isinstance(errors, list) else 1

    return ShardProgress(
        path=str(path.resolve()),
        shard_id=str(payload.get("shard_id") or path.parent.name),
        campaign_signature=str(payload.get("campaign_signature") or ""),
        operating_point_id=str(payload.get("operating_point_id") or ""),
        seed_block=str(payload.get("seed_block") or ""),
        status=str(payload.get("status") or "unknown").lower(),
        planned=planned,
        completed=completed,
        failed=failed,
        running=running,
        updated_at_utc=updated.isoformat() if updated else "",
        started_at_utc=started.isoformat() if started else "",
        elapsed_seconds=_optional_nonnegative_float(
            _first(payload, "elapsed_seconds", "elapsed"),
            field="elapsed_seconds",
            path=path,
        ),
        mean_completed_case_seconds=_optional_nonnegative_float(
            payload.get("mean_completed_case_seconds"),
            field="mean_completed_case_seconds",
            path=path,
        ),
        eta_seconds=_optional_nonnegative_float(
            _first(payload, "eta_seconds", "ETA", "eta"),
            field="eta_seconds",
            path=path,
        ),
        error_count=error_count,
        stale=stale,
    )


def aggregate_progress(
    campaign_root: Path,
    *,
    expected_shards: int = DEFAULT_EXPECTED_SHARDS,
    parallel_workers: int = DEFAULT_PARALLEL_WORKERS,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Aggregate all shard progress files without modifying the campaign."""

    if expected_shards <= 0:
        raise ValueError("expected_shards must be positive")
    if parallel_workers <= 0:
        raise ValueError("parallel_workers must be positive")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    paths = sorted((campaign_root / "shards").glob("*/progress.json"))
    shards: list[ShardProgress] = []
    read_errors: list[str] = []
    for path in paths:
        try:
            shards.append(
                read_shard_progress(
                    path,
                    now=now,
                    stale_after_seconds=stale_after_seconds,
                )
            )
        except ValueError as exc:
            read_errors.append(str(exc))

    planned = sum(item.planned for item in shards)
    completed = sum(item.completed for item in shards)
    failed = sum(item.failed for item in shards)
    running = sum(item.running for item in shards)
    remaining = max(0, planned - completed)
    weighted_samples = [
        (item.mean_completed_case_seconds, item.completed)
        for item in shards
        if item.mean_completed_case_seconds is not None and item.completed > 0
    ]
    weighted_count = sum(count for _, count in weighted_samples)
    weighted_mean = (
        sum(float(mean) * count for mean, count in weighted_samples) / weighted_count
        if weighted_count
        else None
    )
    projected_eta = (
        remaining * weighted_mean / parallel_workers
        if weighted_mean is not None
        else None
    )
    runner_wave_eta = max(
        (item.eta_seconds for item in shards if item.eta_seconds is not None),
        default=None,
    )
    signatures = sorted(
        {item.campaign_signature for item in shards if item.campaign_signature}
    )
    status_counts = Counter(item.status for item in shards)
    complete = bool(
        len(shards) == expected_shards
        and not read_errors
        and len(signatures) <= 1
        and all(item.status == "complete" for item in shards)
        and completed == planned
        and failed == 0
    )

    return {
        "schema_version": "etudecas.supplier_operating_point_full_campaign_v2_monitor.v1",
        "read_only": True,
        "observed_at_utc": now.isoformat(),
        "campaign_root": str(campaign_root.resolve()),
        "expected_shard_count": expected_shards,
        "discovered_shard_count": len(shards),
        "missing_shard_count": max(0, expected_shards - len(shards)),
        "read_error_count": len(read_errors),
        "read_errors": read_errors,
        "campaign_signature_count": len(signatures),
        "campaign_signatures": signatures,
        "mixed_campaign_signatures": len(signatures) > 1,
        "status_counts": dict(sorted(status_counts.items())),
        "planned_case_count": planned,
        "completed_case_count": completed,
        "failed_case_count": failed,
        "running_case_count": running,
        "remaining_case_count": remaining,
        "completion_ratio": completed / planned if planned else 0.0,
        "stale_running_shard_count": sum(item.stale for item in shards),
        "parallel_workers_for_projection": parallel_workers,
        "weighted_mean_completed_case_seconds": weighted_mean,
        "projected_campaign_eta_seconds": projected_eta,
        "runner_reported_wave_eta_seconds": runner_wave_eta,
        "complete": complete,
        "shards": [asdict(item) for item in shards],
    }


def _duration(value: float | None) -> str:
    if value is None:
        return "indisponible"
    seconds = max(0, int(round(value)))
    days, seconds = divmod(seconds, 86_400)
    hours, seconds = divmod(seconds, 3_600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days} j")
    if hours or days:
        parts.append(f"{hours} h")
    if minutes or hours or days:
        parts.append(f"{minutes} min")
    if not parts:
        parts.append(f"{seconds} s")
    return " ".join(parts)


def render_text(summary: Mapping[str, Any]) -> str:
    """Render a concise French console report."""

    ratio = 100.0 * float(summary["completion_ratio"])
    lines = [
        "Campagne fournisseurs V2 — suivi en lecture seule",
        (
            f"Progression : {summary['completed_case_count']} / "
            f"{summary['planned_case_count']} cas ({ratio:.1f} %)"
        ),
        (
            f"Shards : {summary['discovered_shard_count']} découverts / "
            f"{summary['expected_shard_count']} attendus; "
            f"{summary['missing_shard_count']} manquants"
        ),
        (
            f"En cours : {summary['running_case_count']} cas; "
            f"échecs : {summary['failed_case_count']}; "
            f"shards sans mise à jour : {summary['stale_running_shard_count']}"
        ),
        (
            "Temps restant projeté sur tous les cas : "
            f"{_duration(summary['projected_campaign_eta_seconds'])} "
            f"({summary['parallel_workers_for_projection']} moteurs)"
        ),
        (
            "Temps restant annoncé par la vague active : "
            f"{_duration(summary['runner_reported_wave_eta_seconds'])}"
        ),
    ]
    if summary["mixed_campaign_signatures"]:
        lines.append("ALERTE : plusieurs signatures de campagne sont mélangées.")
    if summary["read_error_count"]:
        lines.append(f"ALERTE : {summary['read_error_count']} progress.json illisible(s).")
    for shard in summary["shards"]:
        lines.append(
            f"- {shard['shard_id']}: {shard['completed']}/{shard['planned']} "
            f"| {shard['status']} | échecs={shard['failed']} "
            f"| ETA={_duration(shard['eta_seconds'])}"
            + (" | SANS MISE À JOUR" if shard["stale"] else "")
        )
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--expected-shards", type=int, default=DEFAULT_EXPECTED_SHARDS)
    parser.add_argument(
        "--parallel-workers", type=int, default=DEFAULT_PARALLEL_WORKERS
    )
    parser.add_argument(
        "--stale-after-seconds", type=float, default=DEFAULT_STALE_AFTER_SECONDS
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=DEFAULT_INTERVAL_SECONDS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    try:
        while True:
            summary = aggregate_progress(
                args.campaign_root,
                expected_shards=args.expected_shards,
                parallel_workers=args.parallel_workers,
                stale_after_seconds=args.stale_after_seconds,
            )
            if args.format == "json":
                print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
            else:
                print(render_text(summary), flush=True)
            if not args.watch:
                return 1 if summary["read_error_count"] else 0
            time.sleep(args.interval_seconds)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
