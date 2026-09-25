"""Profils explicites des lanceurs V5-V8 et finaliseurs V5-V7.

Les calculs restent dans les implementations V4 et les contrats scientifiques
versionnes. Ces objets partagent uniquement le raccordement et restaurent chaque
variable modifiee, y compris en cas d'exception. Les anciens modules/empreintes
sont des identites historiques, pas des modules recrees dynamiquement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from uuid import uuid4

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_campaign_source_revision as _source_revision,
    launch_supplier_operating_point_full_campaign_v4 as launcher_v4,
    finalize_supplier_operating_point_full_campaign_v4 as finalizer_v4,
    build_validated_operating_points_v5 as bridge_v5,
    build_validated_operating_points_v6 as bridge_v6,
    build_validated_operating_points_v7 as bridge_v7,
    supplier_v7_campaign_trace_package as trace_package,
    supplier_operating_point_full_campaign_v8 as campaign_v8,
)

MODULE_NAME = "etudecas.prototypes.scan_2027_risk_control.supplier_campaign_adapters"
ROOT = Path(__file__).resolve().parent


class LauncherAdapterError(RuntimeError):
    """The reviewed launcher graph or its runner binding changed."""


class FinalizerAdapterError(RuntimeError):
    """The reviewed finalizer graph or its scientific binding changed."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class AdapterProfile:
    version: int
    mode: str
    implementation_v4: Any
    bridge: Any
    historical_base_sha256: str
    error_type: type[RuntimeError]

    @property
    def RUNNER(self) -> Path:
        return ROOT / f"supplier_operating_point_full_campaign_v{self.version}.py"

    @property
    def __file__(self) -> str:
        return __file__

    _sha256_file = staticmethod(_sha256_file)

    def validate_frozen_implementation(self) -> Path:
        path = Path(self.implementation_v4.__file__).resolve()
        digest = _sha256_file(path)
        if (
            digest != self.historical_base_sha256
            and not _source_revision.accepts_current_revision(
                path, self.historical_base_sha256, digest
            )
        ):
            raise self.error_type(f"Reviewed V4 {self.mode} source changed")
        try:
            _source_revision.current_revision()
        except (OSError, ValueError) as exc:
            raise self.error_type("Campaign adapter source revision changed") from exc
        if self.version >= 7:
            trace_package.validate_frozen_v7_protocol()
        if self.version == 8:
            campaign_v8.validate_frozen_implementation()
        if not self.RUNNER.is_file():
            raise self.error_type(
                f"Missing V{self.version} campaign runner: {self.RUNNER}"
            )
        return path

    def bindings(self) -> dict[str, Any]:
        values = {"v4_bridge": self.bridge}
        if self.mode == "launch":
            values["RUNNER"] = self.RUNNER
            if self.version >= 7:
                values["EXPECTED_CAMPAIGN_SEEDS"] = trace_package.CAMPAIGN_SEEDS
        else:
            values["SOURCE_RUNNER_SHA256"] = _sha256_file(self.RUNNER)
            if self.version >= 7:
                values["EXPECTED_SEEDS"] = trace_package.CAMPAIGN_SEEDS
        return values

    @contextmanager
    def patched_context(self) -> Iterator[None]:
        self.validate_frozen_implementation()
        values = self.bindings()
        previous = {name: getattr(self.implementation_v4, name) for name in values}
        try:
            for name, value in values.items():
                setattr(self.implementation_v4, name, value)
            yield
        finally:
            for name, value in previous.items():
                setattr(self.implementation_v4, name, value)

    # Existing Python consumers keep their context contract after explicit import migration.
    patched_v5_context = patched_context
    patched_v6_context = patched_context
    patched_v7_context = patched_context
    patched_v8_context = patched_context

    def main(self, argv: Sequence[str] | None = None) -> int:
        with self.patched_context():
            return int(self.implementation_v4.main(argv))


class V8LaunchProfile(AdapterProfile):
    V8LauncherAdapterError = LauncherAdapterError

    def bindings(self) -> dict[str, Any]:
        return {
            **super().bindings(),
            "EXPECTED_DISCOVERY_RUNS": 0,
            "load_campaign_plan": self._load_v8_campaign_plan,
            "_detached_command": self._v8_detached_command,
            "_discovery_completion_state": self._v8_discovery_completion_state,
        }

    def _load_v8_campaign_plan(
        self, campaign_root: Path, runner: Path = None
    ) -> tuple[dict[str, Any], list[Any]]:
        """Validate a native V8 plan without weakening the mature shard checks."""
        runner = self.RUNNER if runner is None else runner
        campaign_root = campaign_root.resolve()
        manifest_path = campaign_root / "campaign_manifest.json"
        shard_plan_path = campaign_root / "shard_plan.csv"
        if not manifest_path.is_file() or not shard_plan_path.is_file():
            raise FileNotFoundError(
                "Run the V8 runner in --mode plan before launching shards"
            )
        manifest = self.implementation_v4._read_json(manifest_path)
        if (
            manifest.get("schema_version")
            != self.implementation_v4.INPUT_SCHEMA_VERSION
        ):
            raise ValueError("Unsupported V8 campaign manifest schema")
        if (
            manifest.get("contract_revision")
            != self.implementation_v4.EXPECTED_CONTRACT_REVISION
        ):
            raise ValueError("Campaign manifest does not preserve the mature contract")
        if str(manifest.get("status") or "") not in {"planned", "running", "complete"}:
            raise ValueError("Campaign manifest is not launchable")
        signature = str(manifest.get("campaign_signature") or "")
        if len(signature) != 64:
            raise ValueError("Campaign signature is missing")
        self.implementation_v4._verify_signed_design(manifest)
        counts = manifest.get("expected_counts") or {}
        required_counts = {
            "auxiliary_discovery_runs": 0,
            "design_window_engine_runs": 0,
            "target_selection_engine_runs": 0,
            "operating_point_validation_engine_runs": 0,
            "imported_v4_holdout_service_proofs": 90,
            "imported_v4_holdout_shipment_traces": 90,
            "imported_v7_campaign_baseline_service_proofs": 90,
            "imported_v7_campaign_baseline_shipment_traces": 90,
            "baseline_rows": 90,
            "incident_rows": 3240,
            "shard_count": self.implementation_v4.EXPECTED_SHARD_COUNT,
            "rows_per_shard": self.implementation_v4.EXPECTED_CASES_PER_SHARD,
            "total_rows": self.implementation_v4.EXPECTED_TOTAL_CASES,
        }
        if not isinstance(counts, Mapping) or any(
            (
                int(counts.get(key, -1)) != value
                for key, value in required_counts.items()
            )
        ):
            raise ValueError("Campaign expected counts do not match the V8 matrix")
        if (
            manifest.get("target_selection_revision")
            != campaign_v8.TARGET_SELECTION_REVISION
        ):
            raise ValueError("V8 target-selection revision changed")
        if manifest.get("target_selection_engine_runs") != 0:
            raise ValueError("V8 target selection must not run the engine")
        cohort = manifest.get("v8_target_selection_cohort") or {}
        if (
            cohort.get("campaign_baselines_used_for_exposure_stratification")
            != list(trace_package.CAMPAIGN_SEEDS)
            or cohort.get("source_trace_count") != 90
            or cohort.get("reserved_target_design_cohort_used") is not False
            or (cohort.get("incident_outcomes_used") is not False)
        ):
            raise ValueError("V8 exposure-stratification cohort changed")
        for flag in (
            "quality_branch_included",
            "quality_incident_included",
            "availability_incident_included",
            "capacity_incident_included",
            "stock_incident_included",
            "supplier_state_dependent_risks_enabled",
        ):
            if manifest.get(flag) is not False:
                raise ValueError(f"Campaign must explicitly declare {flag}=false")
        if tuple((int(value) for value in manifest.get("seeds") or [])) != tuple(
            trace_package.CAMPAIGN_SEEDS
        ):
            raise ValueError("Campaign does not preserve the 30 V7 campaign seeds")
        mechanisms = manifest.get("mechanisms") or []
        if (
            not isinstance(mechanisms, list)
            or {
                str(row.get("key") or "")
                for row in mechanisms
                if isinstance(row, Mapping)
            }
            != self.implementation_v4.EXPECTED_MECHANISMS
        ):
            raise ValueError("Campaign mechanisms are not the signed incident pair")
        self.implementation_v4._validate_manifest_sources(manifest)
        self.implementation_v4._validate_operating_point_source_contract(manifest)
        runner = runner.resolve()
        if not runner.is_file():
            raise FileNotFoundError(f"Missing V8 shard runner: {runner}")
        planned_runner = Path(str(manifest.get("runner") or "")).resolve()
        if planned_runner != runner:
            raise ValueError(
                "Launcher runner path differs from the signed campaign runner"
            )
        if self.implementation_v4._sha256_file(runner) != str(
            manifest.get("runner_sha256") or ""
        ):
            raise ValueError("Signed V8 campaign runner changed after planning")
        shards = self.implementation_v4._load_shards(manifest)
        plan_rows = self.implementation_v4._read_csv(shard_plan_path)
        if len(plan_rows) != self.implementation_v4.EXPECTED_SHARD_COUNT or {
            row.get("shard_id") for row in plan_rows
        } != {shard.shard_id for shard in shards}:
            raise ValueError("shard_plan.csv does not match campaign_manifest.json")
        by_id = {shard.shard_id: shard for shard in shards}
        for row in plan_rows:
            shard = by_id[str(row["shard_id"])]
            if (
                int(row.get("shard_index") or 0) != shard.shard_index
                or str(row.get("operating_point_id") or "") != shard.operating_point_id
                or int(row.get("seed_block") or 0) != shard.seed_block
                or (
                    int(row.get("total_rows") or 0)
                    != self.implementation_v4.EXPECTED_CASES_PER_SHARD
                )
            ):
                raise ValueError(f"shard_plan.csv row changed for {shard.shard_id}")
        return (manifest, shards)

    def _v8_detached_command(self, args: Any) -> list[str]:
        """Ensure a detached child re-enters this V8 adapter, not the V4 module."""
        command = [
            self.implementation_v4.sys.executable,
            "-m",
            MODULE_NAME,
            "launch",
            "v8",
            "--campaign-root",
            str(args.campaign_root.resolve()),
            "--runner",
            str(args.runner.resolve()),
            "--parallel-shards",
            str(args.parallel_shards),
            "--workers-per-shard",
            str(args.workers_per_shard),
            "--poll-seconds",
            str(args.poll_seconds),
            "--detached-child",
        ]
        for source in args.reuse_evidence_dir:
            command.extend(["--reuse-evidence-dir", str(source.resolve())])
        return command

    def _v8_discovery_completion_state(
        self, campaign_root: Path, *, manifest: Mapping[str, Any]
    ) -> tuple[str, str]:
        """Use the V8 registry validator instead of the obsolete design-seed gate."""
        status = str(manifest.get("target_discovery_status") or "")
        binding_status = str(manifest.get("state_validation_binding_status") or "")
        if status == "rejected" or binding_status == "rejected":
            return ("rejected", "V8 target-exposure comparability rejected the design")
        if not status and (not binding_status):
            return ("missing", "")
        if (
            status != "complete"
            or binding_status != self.implementation_v4.EXPECTED_PREFLIGHT_STATUS
        ):
            return ("resumable", f"discovery={status!r}, binding={binding_status!r}")
        try:
            with campaign_v8.patched_v8_context():
                lanes = campaign_v8.implementation_v4.load_lanes(
                    Path(str(manifest.get("lane_reference_source") or ""))
                )
                campaign_v8.implementation_v4.load_target_registry(
                    output_dir=campaign_root, manifest=manifest, lanes=lanes
                )
        except FileNotFoundError as exc:
            return ("resumable", str(exc))
        except (KeyError, TypeError, ValueError) as exc:
            return ("invalid", str(exc))
        return ("complete", "")


class V7FinalizerProfile(AdapterProfile):
    V7FinalizerAdapterError = FinalizerAdapterError
    V7_RESULT_OVERLAY_SCHEMA_VERSION = (
        "etudecas.supplier_operating_point_full_campaign.v7.result_overlay.v1"
    )
    V7_RESULT_OVERLAY_NAME = "campaign_validation_v7.json"
    _ORIGINAL_VALIDATE_PROVENANCE = staticmethod(
        finalizer_v4._validate_operating_point_provenance
    )

    @property
    def V7_CAMPAIGN_RUNNER(self) -> Path:
        return self.RUNNER

    def bindings(self) -> dict[str, Any]:
        return {
            **super().bindings(),
            "_validate_operating_point_provenance": self._v7_provenance,
        }

    def _v7_provenance(self, evidence: Any, manifest: Any) -> dict[str, Any]:
        payload = dict(self._ORIGINAL_VALIDATE_PROVENANCE(evidence, manifest))
        holdout = payload.get("holdout_contract") or {}
        validation = holdout.get("validation_protocol") or {}
        baseline = holdout.get("campaign_baseline_contract") or {}
        if (
            validation.get("role") != "sole_scientific_authorization_for_fixed_triplet"
            or validation.get("accepted") is not True
            or validation.get("validation_seed_count") != 150
            or (validation.get("fresh_physical_evidence_case_count") != 450)
            or (validation.get("prior_version_simulation_evidence_reused") is not False)
            or (baseline.get("role") != "campaign_initial_conditions_and_pairing_only")
            or (baseline.get("seeds") != list(trace_package.CAMPAIGN_SEEDS))
            or (baseline.get("physical_case_count") != 90)
            or (baseline.get("acceptance_gate") is not False)
            or (baseline.get("used_for_operating_point_retuning") is not False)
        ):
            raise self.V7FinalizerAdapterError("Final V7 provenance separation changed")
        legacy = str(payload.get("producer") or "")
        payload.update(
            {
                "producer": "v7_fixed_triplet_confirmation_bridge",
                "legacy_v4_producer_dispatch_key": legacy,
                "legacy_v4_producer_is_compatibility_alias": True,
                "scientific_provenance_v7": {
                    "scientific_authorization": "accepted_official_v7_fixed_triplet_confirmation",
                    "v7_plan_signature": validation["plan_signature"],
                    "v7_result_signature": validation["result_signature"],
                    "validation_seed_count": 150,
                    "fresh_validation_case_count": 450,
                    "campaign_baseline_seed_count": 30,
                    "campaign_baseline_trace_count": 90,
                    "campaign_baseline_subset_is_acceptance_gate": False,
                    "same_30_seeds_for_baseline_and_incidents": True,
                    "prior_version_simulation_evidence_reused": False,
                    "retuning_after_v7": False,
                },
            }
        )
        return payload

    def _overlay_payload(self, campaign_root: Path, output_dir: Path) -> dict[str, Any]:
        campaign_root = campaign_root.resolve()
        output_dir = output_dir.resolve()
        base_path = output_dir / "campaign_validation.json"
        binding_path = output_dir / "state_validation_binding.json"
        manifest_path = campaign_root / "campaign_manifest.json"
        base = self.implementation_v4._read_json(base_path)
        binding = self.implementation_v4._read_json(binding_path)
        manifest = self.implementation_v4._read_json(manifest_path)
        self.implementation_v4._verify_payload_signature(
            binding, "binding_signature", label="V7 final state binding"
        )
        self.implementation_v4._verify_manifest_signature(manifest)
        provenance = (base.get("inputs") or {}).get("operating_point_provenance") or {}
        science = binding.get("scientific_provenance_v7") or {}
        comparisons = base.get("comparability_checks") or {}
        expected = base.get("expected_contract") or {}
        source_manifest = (base.get("inputs") or {}).get("campaign_manifest")
        if (
            base.get("status") != "complete_validated"
            or Path(str(source_manifest or "")).resolve() != manifest_path
            or (base.get("inputs") or {}).get("campaign_manifest_sha256")
            != self.implementation_v4._sha256(manifest_path)
            or (provenance.get("producer") != "v7_fixed_triplet_confirmation_bridge")
            or (provenance.get("legacy_v4_producer_is_compatibility_alias") is not True)
            or (provenance.get("scientific_provenance_v7") != science)
            or (
                science.get("scientific_authorization")
                != "accepted_official_v7_fixed_triplet_confirmation"
            )
            or (
                not trace_package.campaign_contract.is_sha256(
                    science.get("v7_plan_signature")
                )
            )
            or (
                not trace_package.campaign_contract.is_sha256(
                    science.get("v7_result_signature")
                )
            )
            or (science.get("validation_seed_count") != 150)
            or (science.get("fresh_validation_case_count") != 450)
            or (science.get("campaign_baseline_seed_count") != 30)
            or (science.get("campaign_baseline_trace_count") != 90)
            or (science.get("campaign_baseline_subset_is_acceptance_gate") is not False)
            or (science.get("same_30_seeds_for_baseline_and_incidents") is not True)
            or (science.get("prior_version_simulation_evidence_reused") is not False)
            or (science.get("retuning_after_v7") is not False)
            or (binding.get("campaign_seeds") != list(trace_package.CAMPAIGN_SEEDS))
            or (expected.get("repetition_ids") != list(trace_package.CAMPAIGN_SEEDS))
            or (expected.get("baseline_row_count") != 90)
            or (expected.get("incident_row_count") != 3240)
            or (
                expected.get("mechanisms")
                != ["transport_delay", "planned_delivery_shortfall"]
            )
            or (expected.get("quality_branch_included") is not False)
            or (expected.get("availability_incident_included") is not False)
            or (
                comparisons.get("v4_holdout_state_binding_signed_and_accepted")
                is not True
            )
            or (
                comparisons.get("v4_holdout_shipment_traces_reused_without_rerun")
                is not True
            )
            or (
                comparisons.get(
                    "all_3330_metrics_reconstructed_from_signed_case_evidence"
                )
                is not True
            )
            or (comparisons.get("quality_or_availability_incident_count") != 0)
            or any(
                (
                    manifest.get(flag) is not False
                    for flag in (
                        "quality_branch_included",
                        "quality_incident_included",
                        "availability_incident_included",
                        "capacity_incident_included",
                        "stock_incident_included",
                        "supplier_state_dependent_risks_enabled",
                    )
                )
            )
        ):
            raise self.V7FinalizerAdapterError(
                "Base V4 envelope cannot authorize V7 release"
            )
        unsigned = {
            "schema_version": self.V7_RESULT_OVERLAY_SCHEMA_VERSION,
            "status": "complete_validated_v7_overlay",
            "base_campaign_validation": {
                "path": str(base_path),
                "sha256": self.implementation_v4._sha256(base_path),
                "schema_version": base["schema_version"],
                "status": base["status"],
            },
            "campaign_manifest": {
                "path": str(manifest_path),
                "sha256": self.implementation_v4._sha256(manifest_path),
                "campaign_signature": manifest["campaign_signature"],
            },
            "state_validation_binding": {
                "path": str(binding_path),
                "sha256": self.implementation_v4._sha256(binding_path),
                "binding_signature": binding["binding_signature"],
            },
            "scientific_provenance_v7": science,
            "v7_comparability_checks": {
                "v7_confirmation_150_seeds_450_cases_signed_and_accepted": True,
                "v7_first30_90_shipment_traces_used_for_pairing_without_rerun": True,
                "same_30_seeds_for_baseline_and_incidents": True,
                "campaign_subset_used_as_v7_acceptance_gate": False,
                "all_3330_metrics_reconstructed_from_signed_case_evidence": True,
                "quality_capacity_availability_stock_or_state_risk_incident_count": 0,
            },
            "legacy_reader_aliases": {
                "v4_holdout_state_binding_signed_and_accepted": "compatibility alias; scientific source is accepted V7 confirmation",
                "v4_holdout_shipment_traces_reused_without_rerun": "compatibility alias; traces are derived from first 30 V7 seed blocks",
                "legacy_keys_are_scientific_v4_evidence_claims": False,
            },
            "counts": {
                "validation_seed_count": 150,
                "validation_case_count": 450,
                "campaign_seed_count": 30,
                "baseline_row_count": 90,
                "incident_row_count": 3240,
                "campaign_row_count": 3330,
            },
        }
        return {
            **unsigned,
            "overlay_signature": self.implementation_v4._stable_sha256(unsigned),
        }

    def validate_v7_overlay(
        self, campaign_root: Path, output_dir: Path
    ) -> dict[str, Any]:
        expected = self._overlay_payload(campaign_root, output_dir)
        path = output_dir.resolve() / self.V7_RESULT_OVERLAY_NAME
        actual = self.implementation_v4._read_json(path)
        self.implementation_v4._verify_payload_signature(
            actual, "overlay_signature", label="V7 result overlay"
        )
        if actual != expected:
            raise self.V7FinalizerAdapterError(
                "V7 result overlay differs from signed sources"
            )
        return actual

    def write_v7_overlay(
        self,
        campaign_root: Path,
        output_dir: Path,
        *,
        validated_base: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Publish only beside the base result validated in this same invocation."""
        output_dir = output_dir.resolve()
        path = output_dir / self.V7_RESULT_OVERLAY_NAME
        if path.exists():
            return self.validate_v7_overlay(campaign_root, output_dir)
        base_path = output_dir / "campaign_validation.json"
        if self.implementation_v4._read_json(base_path) != dict(validated_base):
            raise self.V7FinalizerAdapterError(
                "V4 compatibility result differs from the just-validated in-memory result"
            )
        payload = self._overlay_payload(campaign_root, output_dir)
        raw = (
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        ).encode("utf-8")
        temporary = path.with_name(f".{path.name}.building-{uuid4().hex}")
        try:
            with temporary.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return self.validate_v7_overlay(campaign_root, output_dir)

    def main(self, argv: Sequence[str] | None = None) -> int:
        args = self.implementation_v4.parse_args(argv)
        try:
            base = args.output_dir.resolve() / "campaign_validation.json"
            overlay_path = args.output_dir.resolve() / self.V7_RESULT_OVERLAY_NAME
            if base.is_file():
                if not overlay_path.is_file():
                    raise self.V7FinalizerAdapterError(
                        "A mature result exists without its V7 overlay; refusing to retrofit scientific authorization. Use a new results directory."
                    )
                overlay = self.validate_v7_overlay(args.campaign_root, args.output_dir)
            else:
                with self.patched_v7_context():
                    validated_base = self.implementation_v4.finalize_campaign(
                        campaign_root=args.campaign_root,
                        manifest_path=args.campaign_manifest,
                        metrics_paths=args.metrics_csv,
                        output_dir=args.output_dir,
                    )
                overlay = self.write_v7_overlay(
                    args.campaign_root, args.output_dir, validated_base=validated_base
                )
        except (
            self.implementation_v4.CampaignValidationError,
            self.V7FinalizerAdapterError,
            FileExistsError,
            OSError,
        ) as exc:
            print(f"CAMPAGNE V7 INVALIDE : {exc}")
            return 2
        print(json.dumps(overlay, ensure_ascii=False, indent=2))
        return 0


# Explicit objects, not modules or generated callables. Shared implementations
# preserve each scientific profile and restore their globals at context exit.
launch_v5 = AdapterProfile(
    5,
    "launch",
    launcher_v4,
    bridge_v5,
    "ee79cfc4d61ca98e7030217bdbf52886402e68074b66f7c7380d5e9890838e4c",
    LauncherAdapterError,
)
launch_v6 = AdapterProfile(
    6,
    "launch",
    launcher_v4,
    bridge_v6,
    launch_v5.historical_base_sha256,
    LauncherAdapterError,
)
launch_v7 = AdapterProfile(
    7,
    "launch",
    launcher_v4,
    bridge_v7,
    launch_v5.historical_base_sha256,
    LauncherAdapterError,
)
launch_v8 = V8LaunchProfile(
    8,
    "launch",
    launcher_v4,
    bridge_v7,
    launch_v5.historical_base_sha256,
    LauncherAdapterError,
)
finalize_v5 = AdapterProfile(
    5,
    "finalize",
    finalizer_v4,
    bridge_v5,
    "0a71a62a3ede37df18024ee9349e6f96e0fbfe80e6dd371f253215bac13e5984",
    FinalizerAdapterError,
)
finalize_v6 = AdapterProfile(
    6,
    "finalize",
    finalizer_v4,
    bridge_v6,
    finalize_v5.historical_base_sha256,
    FinalizerAdapterError,
)
finalize_v7 = V7FinalizerProfile(
    7,
    "finalize",
    finalizer_v4,
    bridge_v7,
    finalize_v5.historical_base_sha256,
    FinalizerAdapterError,
)

PROFILES = {
    ("launch", "v5"): launch_v5,
    ("launch", "v6"): launch_v6,
    ("launch", "v7"): launch_v7,
    ("launch", "v8"): launch_v8,
    ("finalize", "v5"): finalize_v5,
    ("finalize", "v6"): finalize_v6,
    ("finalize", "v7"): finalize_v7,
}


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "finalize"))
    parser.add_argument("profile", choices=("v5", "v6", "v7", "v8"))
    if not argv or argv[0] in ("-h", "--help"):
        parser.print_help()
        return 0
    args = parser.parse_args(argv[:2])
    profile = PROFILES.get((args.mode, args.profile))
    if profile is None:
        parser.error("V8 finalization has its own scientific module")
    return profile.main(argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
