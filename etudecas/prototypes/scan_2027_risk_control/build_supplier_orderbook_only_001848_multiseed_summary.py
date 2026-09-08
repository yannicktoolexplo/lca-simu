#!/usr/bin/env python3
"""Build a compact audited summary of the 001848 paired multi-seed campaign.

This reporting-only step never reruns the simulation.  It accepts exactly ten
paired seeds (two stock states, baseline and availability-25 % stress), checks
the retained execution provenance, and exports distributions and paired-effect
counts.  The reported fractions describe only the tested simulations; they are
not historical incident frequencies or supplier probabilities.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


EXPECTED_STATES = ("prospective_001848_90d", "prospective_001848_30d")
BASELINE = "baseline_orderbook_replay"
STRESS = "delivery_availability_0p25"
EXPECTED_SCENARIOS = (BASELINE, STRESS)
EXPECTED_SEED_COUNT = 10


class SummaryValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise SummaryValidationError(f"Expected JSON object: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes"}


def _float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SummaryValidationError(f"Expected finite number, got {value!r}") from exc
    if not math.isfinite(number):
        raise SummaryValidationError(f"Expected finite number, got {value!r}")
    return number


def _distribution(values: Sequence[float], prefix: str) -> dict[str, float]:
    if not values:
        raise SummaryValidationError(f"Empty distribution: {prefix}")
    return {
        f"{prefix}_mean": statistics.fmean(values),
        f"{prefix}_sample_standard_deviation": statistics.stdev(values)
        if len(values) > 1
        else 0.0,
        f"{prefix}_minimum": min(values),
        f"{prefix}_maximum": max(values),
    }


def _validate_source(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    required = (
        "campaign_manifest.json",
        "confirmation_metrics.csv",
        "screening_seed_exact_comparison.csv",
        "execution_provenance_audit.json",
    )
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise SummaryValidationError(f"Missing source files: {missing}")
    manifest = _read_json(root / "campaign_manifest.json")
    audit = _read_json(root / "execution_provenance_audit.json")
    rows = _read_csv(root / "confirmation_metrics.csv")
    seeds = sorted({int(float(row.get("seed") or -1)) for row in rows})
    expected_keys = {
        (state, scenario, seed)
        for state in EXPECTED_STATES
        for scenario in EXPECTED_SCENARIOS
        for seed in seeds
    }
    actual_keys = {
        (
            str(row.get("state_id") or ""),
            str(row.get("scenario_id") or ""),
            int(float(row.get("seed") or -1)),
        )
        for row in rows
    }
    if str(manifest.get("status") or "") != "complete":
        raise SummaryValidationError("Multi-seed source campaign is not complete")
    if not _truthy(audit.get("reproducibility_wording_allowed")):
        raise SummaryValidationError("Multi-seed execution provenance is not valid")
    if len(seeds) != EXPECTED_SEED_COUNT:
        raise SummaryValidationError(
            f"Expected {EXPECTED_SEED_COUNT} seeds, found {len(seeds)}"
        )
    if len(rows) != 40 or actual_keys != expected_keys:
        raise SummaryValidationError(
            "Expected exactly 2 states × 2 scenarios × 10 paired seeds"
        )
    if int(manifest.get("physical_engine_run_count") or -1) != 40:
        raise SummaryValidationError("Manifest physical run count is not 40")
    if int(audit.get("physical_case_count") or -1) != 40:
        raise SummaryValidationError("Provenance physical run count is not 40")
    return manifest, rows


def _validate_trigger(root: Path) -> dict[str, Any]:
    manifest_path = root / "campaign_manifest.json"
    comparison_path = root / "screening_seed_exact_comparison.csv"
    audit_path = root / "execution_provenance_audit.json"
    if not all(path.is_file() for path in (manifest_path, comparison_path, audit_path)):
        raise SummaryValidationError("Missing second-seed trigger evidence")
    manifest = _read_json(manifest_path)
    audit = _read_json(audit_path)
    comparisons = _read_csv(comparison_path)
    if (
        str(manifest.get("status") or "") != "complete"
        or _truthy(manifest.get("new_seed_exactly_matches_screening_for_every_case"))
        or not _truthy(audit.get("reproducibility_wording_allowed"))
        or int(manifest.get("physical_engine_run_count") or -1) != 4
        or len(comparisons) != 4
        or not all(not _truthy(row.get("exact_outcome_match")) for row in comparisons)
    ):
        raise SummaryValidationError("Second-seed trigger evidence is not the audited divergent precheck")
    return {
        "directory": str(root.resolve()),
        "seed": int((manifest.get("seeds") or [-1])[0]),
        "physical_engine_run_count": 4,
        "all_four_outcomes_differ_from_screening_seed": True,
        "campaign_manifest_sha256": _sha(manifest_path),
        "comparison_sha256": _sha(comparison_path),
        "execution_provenance_audit_sha256": _sha(audit_path),
    }


def _state_summary(rows: Sequence[Mapping[str, Any]], state: str) -> dict[str, Any]:
    selected = [row for row in rows if str(row.get("state_id") or "") == state]
    baseline = {
        int(float(row["seed"])): row
        for row in selected
        if str(row.get("scenario_id") or "") == BASELINE
    }
    stresses = {
        int(float(row["seed"])): row
        for row in selected
        if str(row.get("scenario_id") or "") == STRESS
    }
    if set(baseline) != set(stresses) or len(baseline) != EXPECTED_SEED_COUNT:
        raise SummaryValidationError(f"Unpaired rows for {state}")
    ordered_seeds = sorted(baseline)
    base_service = [_float(baseline[seed]["product_on_due_volume_proxy"]) for seed in ordered_seeds]
    stress_service = [_float(stresses[seed]["product_on_due_volume_proxy"]) for seed in ordered_seeds]
    service_delta = [
        _float(stresses[seed]["product_on_due_volume_proxy_delta_vs_paired_baseline"])
        for seed in ordered_seeds
    ]
    released_delta = [
        _float(stresses[seed]["product_released_qty_delta_vs_paired_baseline"])
        for seed in ordered_seeds
    ]
    backlog_delta = [
        _float(stresses[seed]["product_backlog_qty_days_delta_vs_paired_baseline"])
        for seed in ordered_seeds
    ]
    receipt_count = sum(_truthy(stresses[seed].get("causal_effect_on_receipt")) for seed in ordered_seeds)
    descendant_count = sum(
        _truthy(stresses[seed].get("causal_effect_on_descendants")) for seed in ordered_seeds
    )
    client_count = sum(_truthy(stresses[seed].get("causal_effect_on_client")) for seed in ordered_seeds)
    return {
        "state_id": state,
        "stock_cover_hypothesis_days": 90 if state.endswith("90d") else 30,
        "paired_seed_count": len(ordered_seeds),
        "seed_minimum": min(ordered_seeds),
        "seed_maximum": max(ordered_seeds),
        "receipt_effect_seed_count": receipt_count,
        "receipt_effect_share_of_tested_seeds": receipt_count / len(ordered_seeds),
        "descendant_lot_effect_seed_count": descendant_count,
        "descendant_lot_effect_share_of_tested_seeds": descendant_count / len(ordered_seeds),
        "client_effect_seed_count": client_count,
        "client_effect_share_of_tested_seeds": client_count / len(ordered_seeds),
        "unique_baseline_outcome_signature_count": len(
            {str(baseline[seed].get("outcome_signature_sha256") or "") for seed in ordered_seeds}
        ),
        "unique_stress_outcome_signature_count": len(
            {str(stresses[seed].get("outcome_signature_sha256") or "") for seed in ordered_seeds}
        ),
        **_distribution(base_service, "baseline_service"),
        **_distribution(stress_service, "stress_service"),
        **_distribution(service_delta, "paired_service_delta"),
        **_distribution(released_delta, "paired_released_qty_delta"),
        **_distribution(backlog_delta, "paired_backlog_qty_days_delta"),
        "interpretation": (
            f"Sur {len(ordered_seeds)} simulations appariées testées, l'incident change "
            f"la généalogie aval dans {descendant_count} cas et un indicateur client "
            f"dans {client_count} cas. Ces parts ne sont ni une fréquence historique "
            "ni une probabilité fournisseur."
        ),
    }


def build_summary(
    source_dir: Path,
    output_dir: Path,
    *,
    trigger_dir: Path | None = None,
) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SummaryValidationError(f"Output must be new or empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    source_manifest, rows = _validate_source(source_dir)
    trigger = _validate_trigger(trigger_dir.resolve()) if trigger_dir else None
    summaries = [_state_summary(rows, state) for state in EXPECTED_STATES]
    summary = {
        "schema_version": "supplier-orderbook-only-001848-multiseed-summary.v2",
        "evidence_class": "simulated_paired_seed_confirmation",
        "lane_id": "vd0951020a_001848_m1810",
        "failure_mode": "availability 25 % of planned opening-order quantity",
        "paired_seed_count_per_state": EXPECTED_SEED_COUNT,
        "physical_engine_run_count": 40,
        "state_summaries": summaries,
        "statistical_scope": (
            "Descriptive results over the ten tested paired seeds. Effect shares are "
            "not historical recurrence rates and not supplier probabilities."
        ),
        "business_conclusion": (
            "La variabilité du moteur justifie la confirmation multi-graines. "
            "La décision se lit sur les écarts appariés incident moins référence, "
            "séparément pour 90 et 30 jours de couverture hypothétique."
        ),
        "ten_seed_confirmation_trigger": trigger,
    }
    _write_csv(output_dir / "paired_seed_statistical_summary.csv", summaries)
    _write_json(output_dir / "statistical_summary.json", summary)
    source_files = {
        name: _sha(source_dir / name)
        for name in (
            "campaign_manifest.json",
            "confirmation_metrics.csv",
            "screening_seed_exact_comparison.csv",
            "execution_provenance_audit.json",
        )
    }
    output_files = {
        "paired_seed_statistical_summary.csv": _sha(
            output_dir / "paired_seed_statistical_summary.csv"
        ),
        "statistical_summary.json": _sha(output_dir / "statistical_summary.json"),
    }
    manifest = {
        "schema_version": "supplier-orderbook-only-001848-multiseed-package.v2",
        "status": "complete",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "report_builder": str(Path(__file__).resolve()),
        "report_builder_sha256": _sha(Path(__file__).resolve()),
        "simulation_rerun_by_builder": False,
        "source_campaign_dir": str(source_dir),
        "source_campaign_manifest_sha256": source_files["campaign_manifest.json"],
        "source_engine_sha256": source_manifest.get("engine_sha256"),
        "source_graph_sha256": source_manifest.get("source_graph_sha256"),
        "source_orchestrator_sha256_at_process_start": source_manifest.get(
            "orchestrator_sha256_at_process_start"
        ),
        "source_file_sha256": source_files,
        "second_seed_trigger_evidence": trigger,
        "output_sha256": output_files,
        "paired_seed_count_per_state": EXPECTED_SEED_COUNT,
        "physical_engine_run_count": 40,
        "execution_provenance_audit": {
            "reproducibility_wording_allowed": True,
            "source_campaign_provenance_reproducible": True,
            "source_physical_case_count": 40,
            "reporting_only_no_engine_rerun": True,
        },
        "scientific_wording": {
            "allowed": "part des dix simulations appariées testées produisant un effet",
            "not_allowed": "récurrence historique ou probabilité fournisseur",
        },
    }
    _write_json(output_dir / "campaign_manifest.json", manifest)
    print(f"[OK] Multi-seed summary: {output_dir}")
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--trigger-dir")
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    build_summary(
        Path(args.source_dir),
        Path(args.output_dir),
        trigger_dir=Path(args.trigger_dir) if args.trigger_dir else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
