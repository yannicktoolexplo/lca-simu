from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


CAMPAIGN_ROOT = Path(
    r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
    r"\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
)
MEASUREMENTS_CSV = Path(
    r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
    r"\supplier_v8_op100_checkpoint_30_autonome_20260907T195728Z"
    r"\mesures_simulees_1110_op_100_30_sur_30.csv"
)
OUTPUT_ROOT = Path(
    r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
    r"\supplier_v8_op100_top4_causal_lot_replays_20260908_v1"
)
REPO_ROOT = Path(r"C:\dev\lca-simu-pr40")


@dataclass(frozen=True)
class ReplayTarget:
    supplier_slug: str
    supplier_id: str
    item_id: str
    destination_id: str
    target_product_id: str
    seed: int
    shard_id: str
    selection_label: str

    @property
    def lane_slug(self) -> str:
        return (
            f"{self.supplier_slug}_{self.item_id}_{self.destination_id.lower().replace('-', '_')}"
        )

    @property
    def case_key(self) -> str:
        return (
            f"op_100__{self.lane_slug}__transport_delay__seed_{self.seed}"
        )

    @property
    def source_case_dir(self) -> Path:
        return (
            CAMPAIGN_ROOT
            / "shards"
            / self.shard_id
            / "cases"
            / f"probe__{self.case_key}__h720"
        )

    @property
    def output_dir(self) -> Path:
        return OUTPUT_ROOT / (
            f"{self.item_id}_{self.supplier_id}_vers_{self.destination_id}_seed_{self.seed}"
        )


TARGETS = (
    ReplayTarget(
        "sdc_vd0514881a", "SDC-VD0514881A", "016332", "M-1810", "268091",
        329497621, "op_100__seed_block_01",
        "cas le plus proche de la baisse médiane des 30 répétitions",
    ),
    ReplayTarget(
        "sdc_vd0519670a", "SDC-VD0519670A", "029313", "M-1810", "268091",
        93565101, "op_100__seed_block_01",
        "cas médian parmi les répétitions où le service baisse",
    ),
    ReplayTarget(
        "sdc_vd0993480a", "SDC-VD0993480A", "344135", "M-1430", "268967",
        1106445449, "op_100__seed_block_02",
        "cas le plus proche de la baisse médiane des 30 répétitions",
    ),
    ReplayTarget(
        "sdc_vd0505677a", "SDC-VD0505677A", "099439", "M-1810", "268091",
        300975168, "op_100__seed_block_02",
        "cas le plus proche de la baisse médiane des 30 répétitions",
    ),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_original_command(target: ReplayTarget) -> list[str]:
    log_path = target.source_case_dir / "campaign_engine.log"
    if not log_path.is_file():
        raise FileNotFoundError(log_path)
    command_lines = [
        line.split(" COMMAND ", 1)[1]
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if " COMMAND " in line
    ]
    if len(command_lines) != 1:
        raise RuntimeError(f"Commande source non univoque dans {log_path}: {len(command_lines)}")
    command = json.loads(command_lines[0])
    if "--no-lot-trace" not in command:
        raise RuntimeError(f"Option --no-lot-trace absente de {log_path}")
    return [str(value) for value in command]


def _replay_command(target: ReplayTarget) -> list[str]:
    command = _read_original_command(target)
    output_index = command.index("--output-dir") + 1
    command[output_index] = str(target.output_dir)
    command[command.index("--no-lot-trace")] = "--lot-trace"
    return command


def _measurement(target: ReplayTarget) -> dict[str, str]:
    with MEASUREMENTS_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (
                row.get("operating_point_id") == "op_100"
                and row.get("mechanism") == "transport_delay"
                and row.get("supplier_id") == target.supplier_id
                and row.get("item_id") == f"item:{target.item_id}"
                and int(row.get("seed") or -1) == target.seed
            ):
                keep = (
                    "case_key", "seed", "supplier_id", "item_id", "dst_node_id",
                    "target_product_id", "impact_service_loss_fed_product_pp",
                    "impact_on_due_loss_fed_product_qty",
                    "impact_production_loss_fed_product_qty",
                    "incident_physically_exercised", "risk_event_ids",
                    "target_shipment_ids", "target_decision_day",
                    "target_release_day", "target_arrival_day",
                )
                return {key: row.get(key, "") for key in keep}
    raise RuntimeError(f"Mesure 30/30 introuvable pour {target.case_key}")


def _is_complete(target: ReplayTarget) -> bool:
    required = (
        target.output_dir / "data" / "production_lot_events.csv",
        target.output_dir / "data" / "production_lot_genealogy.csv",
        target.output_dir / "data" / "production_plan_events.csv",
        target.output_dir / "data" / "production_campaigns.csv",
    )
    return all(path.is_file() and path.stat().st_size > 0 for path in required)


def _run_one(target: ReplayTarget) -> dict[str, object]:
    started = time.monotonic()
    if _is_complete(target):
        return {
            "target": target.item_id,
            "status": "reused",
            "elapsed_seconds": 0.0,
            "output_dir": str(target.output_dir),
        }
    if target.output_dir.exists():
        raise RuntimeError(
            f"Sortie partielle existante refusee (aucun ecrasement): {target.output_dir}"
        )
    target.output_dir.parent.mkdir(parents=True, exist_ok=True)
    log_dir = OUTPUT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    command = _replay_command(target)
    command_path = log_dir / f"{target.item_id}_{target.seed}_command.json"
    command_path.write_text(
        json.dumps(command, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    stdout_path = log_dir / f"{target.item_id}_{target.seed}_stdout.log"
    stderr_path = log_dir / f"{target.item_id}_{target.seed}_stderr.log"
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            check=False,
        )
    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"Rejeu {target.item_id} en echec ({completed.returncode}); voir {stderr_path}"
        )
    if not _is_complete(target):
        raise RuntimeError(f"Trace de lots incomplete apres rejeu: {target.output_dir}")
    return {
        "target": target.item_id,
        "status": "completed",
        "elapsed_seconds": round(elapsed, 3),
        "output_dir": str(target.output_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rejoue quatre cas op_100 representatifs avec la genealogie de lots activee."
    )
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("--workers doit etre compris entre 1 et 4")
    if not MEASUREMENTS_CSV.is_file():
        raise FileNotFoundError(MEASUREMENTS_CSV)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    source_hashes = {
        str(target.source_case_dir / "campaign_engine.log"): _sha256(
            target.source_case_dir / "campaign_engine.log"
        )
        for target in TARGETS
    }
    print(
        "Rejeu cible: 4 cas representatifs, traces de lots actives, aucun fichier source modifie.",
        flush=True,
    )
    results: list[dict[str, object]] = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_run_one, target): target for target in TARGETS}
        for future in as_completed(futures):
            target = futures[future]
            result = future.result()
            results.append(result)
            print(
                f"[{len(results)}/4] {target.item_id} {result['status']} "
                f"en {result['elapsed_seconds']} s",
                flush=True,
            )
    manifest = {
        "schema_version": "etudecas.supplier_v8.op100_top4_lot_replay.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "quatre voies les plus sensibles au retard transport dans op_100",
        "incident_hypothesis": "retard de transport impose de 120 jours",
        "simulation_count": 4,
        "parallel_workers": args.workers,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_campaign_root": str(CAMPAIGN_ROOT),
        "source_measurements_csv": str(MEASUREMENTS_CSV),
        "source_measurements_sha256": _sha256(MEASUREMENTS_CSV),
        "source_log_sha256": source_hashes,
        "source_files_modified": False,
        "targets": [
            {
                **asdict(target),
                "case_key": target.case_key,
                "source_case_dir": str(target.source_case_dir),
                "output_dir": str(target.output_dir),
                "measurement_30_of_30": _measurement(target),
            }
            for target in TARGETS
        ],
        "results": sorted(results, key=lambda row: str(row["target"])),
    }
    manifest_path = OUTPUT_ROOT / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(str(manifest_path), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
