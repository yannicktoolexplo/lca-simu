#!/usr/bin/env python3
"""Inventory and archive or delete heavy sensitivity simulation outputs.

The script is safe by default: it performs a dry-run and writes a manifest.
Use ``--execute`` to move ``simulation_output`` directories to an archive root,
or ``--delete --execute`` to remove them after the manifest has been written.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive heavy etudecas sensitivity outputs.")
    parser.add_argument(
        "--root",
        default="etudecas/simulation/sensibility",
        help="Sensitivity root to scan.",
    )
    parser.add_argument(
        "--archive-root",
        default="etudecas/simulation/sensibility_archives",
        help="Archive root used with --execute.",
    )
    parser.add_argument(
        "--manifest",
        default="etudecas/simulation/sensibility/sensibility_artifact_manifest.csv",
        help="CSV manifest path.",
    )
    parser.add_argument(
        "--json-summary",
        default="etudecas/simulation/sensibility/sensibility_artifact_manifest.json",
        help="JSON summary path.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually apply the selected action. Default is dry-run.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete simulation_output directories instead of archiving them.",
    )
    parser.add_argument(
        "--keep",
        action="append",
        default=[],
        help="Substring of paths to keep in place. Can be passed multiple times.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of simulation_output directories to move. 0 means no limit.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing destination directory.",
    )
    return parser.parse_args()


def safe_resolve(path: Path) -> Path:
    return path.expanduser().resolve()


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def dir_size(path: Path) -> tuple[int, int]:
    size = 0
    count = 0
    for item in path.rglob("*"):
        if item.is_file():
            count += 1
            try:
                size += item.stat().st_size
            except OSError:
                pass
    return size, count


def load_case_summary(output_dir: Path) -> dict[str, Any]:
    candidates = [
        output_dir / "summaries" / "first_simulation_summary.json",
        output_dir / "first_simulation_summary.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return {
            "sim_days": data.get("sim_days"),
            "fill_rate": (data.get("kpis") or {}).get("fill_rate"),
            "ending_backlog": (data.get("kpis") or {}).get("ending_backlog"),
            "total_cost": (data.get("kpis") or {}).get("total_cost"),
            "total_produced": (data.get("kpis") or {}).get("total_produced"),
            "lot_count": ((data.get("production_tracking") or {}).get("lot_trace") or {}).get("lot_count"),
        }
    return {}


def discover_outputs(root: Path, keep_tokens: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for output_dir in sorted(root.rglob("simulation_output")):
        if not output_dir.is_dir():
            continue
        text_path = str(output_dir)
        keep = any(token and token in text_path for token in keep_tokens)
        size, count = dir_size(output_dir)
        summary = load_case_summary(output_dir)
        rows.append(
            {
                "output_dir": str(output_dir),
                "case_dir": str(output_dir.parent),
                "size_bytes": size,
                "size_mb": round(size / 1024 / 1024, 3),
                "file_count": count,
                "keep": keep,
                "sim_days": summary.get("sim_days", ""),
                "fill_rate": summary.get("fill_rate", ""),
                "ending_backlog": summary.get("ending_backlog", ""),
                "total_cost": summary.get("total_cost", ""),
                "total_produced": summary.get("total_produced", ""),
                "lot_count": summary.get("lot_count", ""),
            }
        )
    return rows


def write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "output_dir",
        "case_dir",
        "size_bytes",
        "size_mb",
        "file_count",
        "keep",
        "sim_days",
        "fill_rate",
        "ending_backlog",
        "total_cost",
        "total_produced",
        "lot_count",
        "archive_destination",
        "action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def apply_output_retention(
    rows: list[dict[str, Any]],
    *,
    root: Path,
    archive_root: Path,
    execute: bool,
    delete: bool,
    limit: int,
    overwrite: bool,
) -> list[dict[str, Any]]:
    root_resolved = safe_resolve(root)
    archive_resolved = safe_resolve(archive_root)
    if not delete:
        archive_resolved.mkdir(parents=True, exist_ok=True)

    moved = 0
    for row in rows:
        src = safe_resolve(Path(str(row["output_dir"])))
        if not is_relative_to(src, root_resolved):
            row["action"] = "skip_outside_root"
            continue
        if row.get("keep"):
            row["action"] = "keep"
            continue
        if limit and moved >= limit:
            row["action"] = "skip_limit"
            continue
        if delete:
            row["archive_destination"] = ""
            if not execute:
                row["action"] = "dry_run_delete"
                moved += 1
                continue
            shutil.rmtree(src)
            row["action"] = "deleted"
            moved += 1
            continue
        relative = src.relative_to(root_resolved)
        dst = archive_resolved / relative
        if not is_relative_to(dst, archive_resolved):
            row["action"] = "skip_bad_destination"
            continue
        row["archive_destination"] = str(dst)
        if not execute:
            row["action"] = "dry_run_move"
            moved += 1
            continue
        if dst.exists():
            if not overwrite:
                row["action"] = "skip_destination_exists"
                continue
            shutil.rmtree(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        row["action"] = "moved"
        moved += 1
    return rows


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    archive_root = Path(args.archive_root)
    manifest_path = Path(args.manifest)
    json_summary_path = Path(args.json_summary)

    rows = discover_outputs(root, args.keep)
    rows = apply_output_retention(
        rows,
        root=root,
        archive_root=archive_root,
        execute=bool(args.execute),
        delete=bool(args.delete),
        limit=max(0, int(args.limit)),
        overwrite=bool(args.overwrite),
    )
    write_manifest(manifest_path, rows)
    total_size = sum(int(row.get("size_bytes") or 0) for row in rows)
    actions: dict[str, int] = {}
    for row in rows:
        action = str(row.get("action") or "")
        actions[action] = actions.get(action, 0) + 1
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "archive_root": str(archive_root),
        "execute": bool(args.execute),
        "delete": bool(args.delete),
        "output_count": len(rows),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 3),
        "actions": actions,
        "manifest": str(manifest_path),
    }
    json_summary_path.parent.mkdir(parents=True, exist_ok=True)
    json_summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"[{mode}] outputs={len(rows)} total={summary['total_size_mb']} MB actions={actions}")
    print(f"[OK] Manifest: {manifest_path.resolve()}")
    print(f"[OK] Summary: {json_summary_path.resolve()}")


if __name__ == "__main__":
    main()
