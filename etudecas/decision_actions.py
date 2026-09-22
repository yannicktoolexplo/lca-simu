"""Reproducible exploratory controls on a risk run; no industrial recommendation."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from etudecas.testing.map_delivery import file_hash
from etudecas.simulation.source_fingerprint import implementation_fingerprint

REPO = Path(__file__).resolve().parents[1]


def execute_action(reference: Path, output: Path, action: str, targets: list[dict]) -> Path:
    """Replay the reference command with one measured-day control schedule."""
    if action not in {"safety_150", "expedite_50"}:
        raise ValueError("Unknown exploratory action")
    if not targets or any(not all(t.get(k) for k in ("item_id", "dst_node_id", "supplier_id")) for t in targets):
        raise ValueError("Action requires non-empty, fully identified targets")
    manifest = json.loads((reference / "run_manifest.json").read_text(encoding="utf-8"))
    command = list(manifest["simulator_command"])
    engine = REPO / "etudecas/simulation/engine/run_first_simulation.py"
    if Path(command[1]).as_posix() != "etudecas/simulation/engine/run_first_simulation.py":
        raise ValueError("Reference must use the canonical engine")
    if any(arg.split("=", 1)[0] in {"--control-schedule-csv", "--control-policy-json", "--control-policy-v2-json", "--control-policy-v3-json"} for arg in command):
        raise ValueError("Reference already has controls")
    graph = (REPO / command[command.index("--input") + 1]).resolve()
    days = int(command[command.index("--days") + 1])
    root = output / action
    schedule = output / f"{action}.csv"
    field = "safety_stock_multiplier" if action == "safety_150" else "expedite_level"
    columns = ["day", "node_id", "supplier_id", "item_id", "dst_node_id", field]
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for day in range(days):
        for target in targets:
            row = {"day": day, "item_id": target["item_id"], field: 1.5 if action == "safety_150" else .5}
            if action == "safety_150":
                row["node_id"] = target["dst_node_id"]
            else:
                row.update(supplier_id=target["supplier_id"], dst_node_id=target["dst_node_id"])
            writer.writerow(row)
    payload = buffer.getvalue().encode("utf-8")
    command[0] = sys.executable
    command[command.index("--output-dir") + 1] = str(root.resolve())
    command.extend(["--control-schedule-csv", str(schedule.resolve())])
    dependency_hashes = {}
    for index, token in enumerate(command[2:], 2):
        if command[index - 1] in {"--output-dir", "--control-schedule-csv"}:
            continue
        candidate = REPO / str(token).split("=", 1)[-1]
        if candidate.is_file():
            dependency_hashes[str(candidate.resolve())] = file_hash(candidate)
    signature = {"dependencies": dependency_hashes, "command": command, "graph_sha256": file_hash(graph),
                 "engine_sha256": file_hash(engine), "implementation_sha256": implementation_fingerprint(engine), "reference_manifest_sha256": file_hash(reference / "run_manifest.json"),
                 "schedule_sha256": hashlib.sha256(payload).hexdigest()}
    record = output / f"{action}-execution.json"
    if record.exists():
        previous = json.loads(record.read_text(encoding="utf-8"))
        summary = root / "summaries/first_simulation_summary.json"
        if (previous.get("signature") == signature and previous.get("returncode") == 0
                and summary.exists() and file_hash(summary) == previous.get("summary_sha256")
                and schedule.is_file() and file_hash(schedule) == signature["schedule_sha256"]
                and previous.get("artifacts")
                and all((root / name).is_file() and file_hash(root / name) == expected
                        for name, expected in previous["artifacts"].items())):
            return root
        raise ValueError(f"Existing action differs or is incomplete; use a new delivery directory: {root}")
    if root.exists():
        raise ValueError(f"Untracked action directory already exists: {root}")
    output.mkdir(parents=True, exist_ok=True)
    schedule.write_bytes(payload)
    with (output / f"{action}.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
    data = {"signature": signature, "returncode": result.returncode, "targets": targets,
            "scope": "Same configured risks and reference seed; state-dependent events may change with controls."}
    if result.returncode == 0:
        data["summary_sha256"] = file_hash(root / "summaries/first_simulation_summary.json")
        data["artifacts"] = {p.relative_to(root).as_posix(): file_hash(p)
                             for folder in ("data", "summaries")
                             for p in sorted((root / folder).rglob("*")) if p.is_file()}
        required = {"data/first_simulation_daily.csv", "data/production_demand_service_daily.csv",
                    "data/production_output_products_daily.csv", "data/production_lot_events.csv",
                    "data/production_lot_genealogy.csv"}
        missing = sorted(required - data["artifacts"].keys())
        if missing:
            data["returncode"] = 1
            data["missing_artifacts"] = missing
    record.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if data["returncode"]:
        raise RuntimeError(f"Action failed: see {output / (action + '.log')}")
    return root
