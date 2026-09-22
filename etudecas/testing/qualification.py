"""Fail-closed delivery gate using independent CSV and offline browser evidence.

This qualifies only the checked invariants, never the scientific calibration.
Reports are bound to the exact source and output bytes inspected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .independent_review import audit_run


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_run_invariants(run: Path) -> dict:
    result = audit_run(run)
    if not result["ok"]:
        failed = {name: row["failed"] for name, row in result["checks"].items() if row["failed"]}
        raise ValueError(f"Delivery refused: independent invariants failed for {run}: {failed}")
    return result


def qualify(runs: list[Path], output: Path, html: Path | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    report = {"schema": "etudecas.delivery-qualification.v1", "runs": [], "hashes": {},
              "scope": "Physical quantities, balances, exported stocks, identities, and optional offline lot display. Source truth and risk calibration are not certified."}
    for run in runs:
        try:
            result = audit_run(run)
        except (OSError, ValueError, KeyError) as exc:
            result = {"run": str(run), "ok": False, "error": str(exc)}
        report["runs"].append(result)
        for directory in (run / "data", run / "summaries"):
            for path in sorted(directory.glob("*")):
                if path.is_file():
                    report["hashes"][str(path.resolve())] = sha256(path)
    if html is not None:
        from .lot_browser_review import review
        report["browser"] = review(html, output / "browser", runs[0] if runs else None)
        report["hashes"][str(html.resolve())] = sha256(html)
    from etudecas.simulation.source_fingerprint import implementation_fingerprint
    engine = Path(__file__).resolve().parents[1] / "simulation/engine/run_first_simulation.py"
    report["implementation_sha256"] = implementation_fingerprint(engine)
    report["ok"] = bool(runs) and all(r["ok"] for r in report["runs"]) and report.get("browser", {"ok": True})["ok"]
    report["display_verified"] = html is not None and report["browser"]["ok"]
    (output / "qualification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--html", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = qualify(args.run, args.output, args.html)
    print(json.dumps({"ok": result["ok"], "display_verified": result["display_verified"]}))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
