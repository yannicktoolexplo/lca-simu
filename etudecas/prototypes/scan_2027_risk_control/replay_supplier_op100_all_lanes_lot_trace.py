from __future__ import annotations

import csv
import hashlib
import json
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.lot_trace.risk_impact_registry import (
    build_risk_impact_registry_from_directory,
    write_risk_impact_registry,
)


ARTIFACT_ROOT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
CAMPAIGN_ROOT = ARTIFACT_ROOT / "supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
MEASUREMENTS_CSV = ARTIFACT_ROOT / "supplier_v8_op100_checkpoint_30_autonome_20260907T195728Z" / "mesures_simulees_1110_op_100_30_sur_30.csv"
TOP4_ROOT = ARTIFACT_ROOT / "supplier_v8_op100_top4_causal_lot_replays_20260908_v1"
OUTPUT_ROOT = ARTIFACT_ROOT / "supplier_v8_op100_all18_causal_lot_replays_20260908_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def load_incident_rows() -> list[dict[str, str]]:
    with MEASUREMENTS_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            row for row in csv.DictReader(handle)
            if row.get("operating_point_id") == "op_100"
            and row.get("mechanism") == "transport_delay"
            and row.get("valid", "").lower() == "true"
        ]


def select_representatives(rows: list[dict[str, str]]) -> list[dict]:
    preferred_seed_by_item = {
        "016332": 329497621,
        "029313": 93565101,
        "344135": 1106445449,
        "099439": 300975168,
    }
    groups: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (
            row["lane_id"], row["supplier_id"], row["item_id"],
            row["dst_node_id"], row["target_product_id"],
        )
        groups.setdefault(key, []).append(row)
    targets = []
    for key, group in sorted(groups.items()):
        losses = [as_float(row.get("impact_service_loss_fed_product_pp")) for row in group]
        positive = [row for row in group if as_float(row.get("impact_service_loss_fed_product_pp")) > 1e-9]
        all_median = statistics.median(losses)
        if all_median > 1e-9:
            reference = all_median
            pool = group
            metric = "impact_service_loss_fed_product_pp"
            label = "cas le plus proche de la baisse médiane des 30 répétitions"
        elif positive:
            reference = statistics.median(
                as_float(row.get("impact_service_loss_fed_product_pp")) for row in positive
            )
            pool = positive
            metric = "impact_service_loss_fed_product_pp"
            label = "cas médian parmi les répétitions où le service baisse"
        else:
            exercised = [
                row for row in group
                if row.get("incident_physically_exercised", "").lower() == "true"
            ] or group
            dose_values = [as_float(row.get("incident_effective_dose_qty_days")) for row in exercised]
            reference = statistics.median(dose_values)
            pool = exercised
            metric = "incident_effective_dose_qty_days"
            label = "cas médian d’exposition physique ; aucune baisse de service dans les 30 répétitions"
        plain_item_id = key[2].replace("item:", "")
        preferred_seed = preferred_seed_by_item.get(plain_item_id)
        chosen = min(
            pool,
            key=lambda row: (
                round(abs(as_float(row.get(metric)) - reference), 9),
                0 if int(row["seed"]) == preferred_seed else 1,
                int(row["seed"]),
            ),
        )
        targets.append({
            "lane_id": key[0],
            "supplier_id": key[1],
            "item_id": plain_item_id,
            "destination_id": key[3],
            "target_product_id": key[4],
            "seed": int(chosen["seed"]),
            "selection_label": label,
            "selection_metric": metric,
            "selection_reference": reference,
            "measurement_30_of_30": chosen,
        })
    if len(targets) != 18:
        raise RuntimeError(f"18 voies attendues, {len(targets)} obtenues")
    return targets


def case_key(target: dict) -> str:
    return f"op_100__{target['lane_id']}__transport_delay__seed_{target['seed']}"


def source_case_dir(target: dict) -> Path:
    matches = list(
        (CAMPAIGN_ROOT / "shards").glob(
            f"*/cases/probe__{case_key(target)}__h*"
        )
    )
    if len(matches) != 1:
        raise RuntimeError(f"Cas source non univoque pour {case_key(target)}: {len(matches)}")
    return matches[0]


def top4_outputs() -> dict[str, Path]:
    manifest_path = TOP4_ROOT / "manifest.json"
    if not manifest_path.is_file():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        str(target["case_key"]): Path(target["output_dir"])
        for target in manifest.get("targets", [])
    }


def target_output_dir(target: dict, reusable: dict[str, Path]) -> Path:
    if case_key(target) in reusable:
        return reusable[case_key(target)]
    return OUTPUT_ROOT / (
        f"{target['item_id']}_{target['supplier_id']}_vers_"
        f"{target['destination_id']}_seed_{target['seed']}"
    )


def read_source_command(target: dict) -> list[str]:
    log_path = source_case_dir(target) / "campaign_engine.log"
    lines = [
        line.split(" COMMAND ", 1)[1]
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if " COMMAND " in line
    ]
    if len(lines) != 1:
        raise RuntimeError(f"Commande source non univoque dans {log_path}")
    command = [str(value) for value in json.loads(lines[0])]
    if "--no-lot-trace" not in command:
        raise RuntimeError(f"--no-lot-trace absent de {log_path}")
    return command


def complete(output_dir: Path) -> bool:
    return all(
        (output_dir / "data" / filename).is_file()
        for filename in (
            "production_lot_events.csv",
            "production_lot_genealogy.csv",
            "production_plan_events.csv",
            "production_campaigns.csv",
        )
    )


def ensure_registry(output_dir: Path) -> dict:
    registry_dir = output_dir / "risk_lot_registry"
    quality_path = registry_dir / "risk_impact_quality.json"
    if quality_path.is_file():
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        return {"status": "reused", "counts": quality.get("counts", {})}
    registry = build_risk_impact_registry_from_directory(output_dir)
    write_risk_impact_registry(registry, registry_dir)
    return {"status": "completed", "counts": registry.quality.get("counts", {})}


def run_one(target: dict, reusable: dict[str, Path]) -> dict:
    started = time.monotonic()
    output_dir = target_output_dir(target, reusable)
    run_status = "reused"
    if not complete(output_dir):
        if output_dir.exists():
            raise RuntimeError(f"Sortie partielle refusée, sans écrasement: {output_dir}")
        command = read_source_command(target)
        command[command.index("--output-dir") + 1] = str(output_dir)
        command[command.index("--no-lot-trace")] = "--lot-trace"
        log_dir = OUTPUT_ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{target['item_id']}_{target['seed']}"
        (log_dir / f"{stem}_command.json").write_text(
            json.dumps(command, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with (log_dir / f"{stem}_stdout.log").open("w", encoding="utf-8") as stdout_handle, (
            log_dir / f"{stem}_stderr.log"
        ).open("w", encoding="utf-8") as stderr_handle:
            result = subprocess.run(
                command, cwd=REPO_ROOT, stdout=stdout_handle, stderr=stderr_handle,
                text=True, check=False,
            )
        if result.returncode != 0:
            raise RuntimeError(f"Rejeu {target['item_id']} en échec: code {result.returncode}")
        if not complete(output_dir):
            raise RuntimeError(f"Trace de lots incomplète: {output_dir}")
        run_status = "completed"
    registry = ensure_registry(output_dir)
    return {
        "item_id": target["item_id"],
        "status": run_status,
        "registry_status": registry["status"],
        "registry_counts": registry["counts"],
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "output_dir": str(output_dir),
    }


def main() -> int:
    rows = load_incident_rows()
    targets = select_representatives(rows)
    reusable = top4_outputs()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    print(
        "Traçage représentatif des 18 voies op_100 : 4 rejeux réutilisés, 14 au maximum à calculer.",
        flush=True,
    )
    results = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(run_one, target, reusable): target for target in targets}
        for future in as_completed(futures):
            target = futures[future]
            result = future.result()
            results.append(result)
            print(
                f"[{len(results)}/18] {target['item_id']} {result['status']} ; "
                f"registre {result['registry_status']} ; {result['elapsed_seconds']} s",
                flush=True,
            )
    by_item = {row["item_id"]: row for row in results}
    manifest_targets = []
    for target in targets:
        result = by_item[target["item_id"]]
        source_log = source_case_dir(target) / "campaign_engine.log"
        manifest_targets.append({
            **target,
            "case_key": case_key(target),
            "source_case_dir": str(source_case_dir(target)),
            "source_campaign_log_sha256": sha256(source_log),
            "output_dir": result["output_dir"],
            "registry_counts": result["registry_counts"],
        })
    manifest = {
        "schema_version": "etudecas.supplier_v8.op100_all18_lot_replay.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "une réalisation représentative avec trace causale pour chacune des 18 voies op_100",
        "incident_hypothesis": "retard de transport imposé de 120 jours",
        "lane_count": 18,
        "new_engine_run_count": sum(row["status"] == "completed" for row in results),
        "reused_engine_run_count": sum(row["status"] == "reused" for row in results),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_files_modified": False,
        "source_measurements_csv": str(MEASUREMENTS_CSV),
        "source_measurements_sha256": sha256(MEASUREMENTS_CSV),
        "targets": manifest_targets,
        "results": sorted(results, key=lambda row: row["item_id"]),
    }
    manifest_path = OUTPUT_ROOT / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(str(manifest_path), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
