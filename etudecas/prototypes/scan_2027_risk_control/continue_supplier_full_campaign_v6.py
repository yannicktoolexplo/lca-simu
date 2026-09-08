#!/usr/bin/env python3
"""Fail-closed V6 relay from accepted holdout to the complete client package.

Calibration remains a read-only input.  The mature V5/V4 downstream machinery
is reused for the 3,330-row incident campaign, lot replay, physical
qualification, actions, nominal curves, dashboard and standalone HTML.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import traceback
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v6 as bridge_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v5 as implementation_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v6 as launcher_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_holdout_v6 as holdout_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v6 as sidecar_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v6 as campaign_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_final_standalone_delivery as delivery_v6,
)


relay_v4 = implementation_v5.relay_v4
V6RelayConfig = implementation_v5.V5RelayConfig
FullCampaignRelayError = implementation_v5.FullCampaignRelayError
ScientificNoGo = implementation_v5.ScientificNoGo

SCHEMA_VERSION = "etudecas.supplier_full_campaign_relay.v6"
MODULE_NAME = (
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v6"
)
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract.v1"
STATUS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.status.v1"
RESERVATION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.reservations.v1"
EXPECTED_DEVELOPMENT_CASES = 150
EXPECTED_NEW_DEVELOPMENT_ENGINE_RUNS = 60
EXPECTED_HOLDOUT_CASES = 90

CORE_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_fresh_holdout_v6"
)
BRIDGE_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.build_validated_operating_points_v6"
)
SIDECAR_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_holdout_curve_sidecar_v6"
)
CAMPAIGN_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_operating_point_full_campaign_v6"
)
LAUNCHER_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.launch_supplier_operating_point_full_campaign_v6"
)
FINALIZER_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.finalize_supplier_operating_point_full_campaign_v6"
)
DELIVERY_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_v6_final_standalone_delivery"
)
FROZEN_REUSED_V5_SHA256 = {
    "etudecas.prototypes.scan_2027_risk_control.supplier_balanced_product_delay_multiseed_refinement_v5": "46bc479466edfe9e1610abbf84aa3f0a6ff039b9066c9a395599494d0b4ed922",
    "etudecas.prototypes.scan_2027_risk_control.build_validated_operating_points_v5": "41492d5b66835028b7aed9977a4e21f4214e7d6e85d98c6a5ae535a7b2cbacb2",
    "etudecas.prototypes.scan_2027_risk_control.supplier_holdout_curve_sidecar_v5": "cdb5c110c847e39a189d87b93a2aca08295913b593c039307b7006b1341ded8a",
    "etudecas.prototypes.scan_2027_risk_control.supplier_operating_point_full_campaign_v5": "302c59d76d9bf490886ba3f100075992566292b1761b71bed9fd27746e6e7b12",
    "etudecas.prototypes.scan_2027_risk_control.launch_supplier_operating_point_full_campaign_v5": "59f1c33552f19bcf09c773733ece132e0e04d341c98807ca9c7087a2de1f4d13",
    "etudecas.prototypes.scan_2027_risk_control.finalize_supplier_operating_point_full_campaign_v5": "2bbfd696b0654f5837da0a51d0022ec1cf4cc9b9eaf98dfd6207a95603898c82",
    "etudecas.prototypes.scan_2027_risk_control.supplier_physical_cascade_qualification_v5": "0bba07f024d1d3f29774bea6945be5d61a85153422c3dd6fac3c86b16fb739e9",
    "etudecas.prototypes.scan_2027_risk_control.supplier_v5_final_standalone_delivery": "19174dc30c28ddfd4143f573414cc76279d1d5b384022b3c2d62d8962fa903be",
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v5": "4a42e97e20233c7907a1cd5e6b202aa4f3a24b56e5da3b029d2ab4bc11cb21cd",
}
V6_MODULES = (
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v6",
    "etudecas.prototypes.scan_2027_risk_control.supplier_balanced_product_delay_multiseed_refinement_v6",
    CORE_MODULE,
    BRIDGE_MODULE,
    SIDECAR_MODULE,
    CAMPAIGN_MODULE,
    LAUNCHER_MODULE,
    FINALIZER_MODULE,
    DELIVERY_MODULE,
)


@contextmanager
def _v6_downstream_binding() -> Iterator[None]:
    names: dict[str, Any] = {
        "__doc__": __doc__,
        "refinement_v5": holdout_v6,
        "bridge_v5": bridge_v6,
        "campaign_v5": campaign_v6,
        "launcher_v5": launcher_v6,
        "CORE_MODULE": CORE_MODULE,
        "BRIDGE_MODULE": BRIDGE_MODULE,
        "SIDECAR_MODULE": SIDECAR_MODULE,
        "CAMPAIGN_MODULE": CAMPAIGN_MODULE,
        "LAUNCHER_MODULE": LAUNCHER_MODULE,
        "FINALIZER_MODULE": FINALIZER_MODULE,
        "DELIVERY_MODULE": DELIVERY_MODULE,
        "CONTRACT_SCHEMA_VERSION": CONTRACT_SCHEMA_VERSION,
        "STATUS_SCHEMA_VERSION": STATUS_SCHEMA_VERSION,
        "RESERVATION_SCHEMA_VERSION": RESERVATION_SCHEMA_VERSION,
    }
    previous = {name: getattr(implementation_v5, name) for name in names}
    with (  # noqa: SLF001
        sidecar_v6._v6_binding(),
        delivery_v6._v6_binding(),
    ):
        try:
            for name, value in names.items():
                setattr(implementation_v5, name, value)
            yield
        finally:
            for name, value in previous.items():
                setattr(implementation_v5, name, value)


class FullCampaignRelayV6(implementation_v5.FullCampaignRelayV5):
    """Downstream-only V6 relay; it cannot run or retune calibration."""

    @staticmethod
    def _calibration_forbidden() -> None:
        raise FullCampaignRelayError(
            "Relais V6 aval uniquement : aucune planification ou exécution calibration"
        )

    def prepare_v5_plan(self) -> None:
        self._calibration_forbidden()

    def run_development(self) -> None:
        self._calibration_forbidden()

    def finalize_development(self) -> dict[str, Any]:
        self._calibration_forbidden()

    def ensure_sidecar_watcher(self) -> int:
        self._calibration_forbidden()

    def run_holdout(self, watcher_pid: int) -> None:
        del watcher_pid
        self._calibration_forbidden()

    def finalize_holdout(self) -> dict[str, Any]:
        self._calibration_forbidden()

    def _module_inventory_v5(self) -> list[dict[str, Any]]:
        modules = (
            *V6_MODULES,
            implementation_v5.QUALIFICATION_MODULE,
            *FROZEN_REUSED_V5_SHA256,
            *implementation_v5.FROZEN_V4_SHA256,
        )
        rows: list[dict[str, Any]] = []
        for module in dict.fromkeys(modules):
            path = relay_v4._module_path(self.config.repo, module).resolve()  # noqa: SLF001
            if not path.is_file():
                raise FullCampaignRelayError(f"Module V6 requis absent : {module}")
            digest = relay_v4.sha256_file(path)
            frozen = implementation_v5.FROZEN_V4_SHA256.get(
                module
            ) or FROZEN_REUSED_V5_SHA256.get(module)
            if frozen is not None and digest != frozen:
                raise FullCampaignRelayError(
                    f"Dépendance aval figée modifiée : {module} ({digest})"
                )
            rows.append({"module": module, "path": str(path), "sha256": digest})
        return rows

    def _v4_source_inventory(self) -> dict[str, Any]:
        paths = (
            self.config.v4_plan_dir / "refinement_plan.json",
            self.config.v4_run_dir / "run_manifest.json",
            self.config.v4_run_dir / "development_progress.json",
            self.config.v4_run_dir / "development_selection.json",
        )
        rows = []
        for path in paths:
            if not path.is_file():
                raise FullCampaignRelayError(f"Preuve développement V6 absente : {path}")
            rows.append(
                {
                    "path": str(path.resolve()),
                    "size_bytes": path.stat().st_size,
                    "sha256": relay_v4.sha256_file(path),
                }
            )
        sidecar_empty = implementation_v5._is_empty_or_absent(  # noqa: SLF001
            self.config.v4_sidecar_root
        )
        if not sidecar_empty:
            raise FullCampaignRelayError(
                "Le sidecar interdit du développement V6 doit être absent ou vide"
            )
        return {
            "files": rows,
            "source_sidecar_root": str(self.config.v4_sidecar_root),
            "source_sidecar_absent_or_empty": True,
        }

    def _build_contract(
        self, calibration_handoff: Mapping[str, Any]
    ) -> dict[str, Any]:
        payload = super()._build_contract(calibration_handoff)
        unsigned = dict(payload)
        unsigned.pop("contract_signature", None)
        science = copy.deepcopy(unsigned["scientific_contract"])
        science.update(
            {
                "v4_source_status": "v5_no_go_then_v6_selected",
                "development_evidence_cases_required": EXPECTED_DEVELOPMENT_CASES,
                "source_new_development_engine_runs_required": (
                    EXPECTED_NEW_DEVELOPMENT_ENGINE_RUNS
                ),
                "holdout_evidence_cases_required": EXPECTED_HOLDOUT_CASES,
                "holdout_is_separate_v6_protocol": True,
                "holdout_retuning": False,
            }
        )
        unsigned["scientific_contract"] = science
        return {**unsigned, "contract_signature": relay_v4.stable_sha256(unsigned)}

    def _validated_plan(self) -> Any:
        return holdout_v6.validate_plan(
            self.config.calibration_plan_dir,
            verify_runtime_dependencies=True,
        )

    def _load_or_create_status(self) -> None:
        super()._load_or_create_status()
        # A detached parent may have created the initial status.  Publish the
        # long-lived child PID immediately instead of waiting for the next step.
        if self.status.get("relay_pid") != os.getpid():
            self._write_status()

    def validate_finalized_sidecar_handoff(self) -> dict[str, Any]:
        result = super().validate_finalized_sidecar_handoff()
        inventory = sidecar_v6.validate_inventory(self.config.sidecar_dir)
        return {
            **result,
            "v6_inventory_schema": inventory["schema_version"],
            "v6_inventory_producer": copy.deepcopy(inventory["producer"]),
        }

    def _validate_transitive_output_separation(self, plan: Any) -> None:
        inherited_sources = holdout_v6._protected_holdout_sources(  # noqa: SLF001
            plan, allow_test_source=False
        )
        protected = (
            *inherited_sources,
            self.config.calibration_run_dir,
            self.config.sidecar_dir,
            self.config.v4_sidecar_root,
        )
        output_dirs = (
            self.config.campaign_root,
            self.config.results_dir,
            self.config.lot_replay_root,
            self.config.qualification_dir,
            self.config.supervision_dir,
            self.config.action_replay_root,
        )
        output_files = (
            self.config.bridge_json,
            self.config.dashboard_html,
            self.config.final_html,
            Path(str(self.config.final_html) + ".manifest.json"),
        )
        if any(
            implementation_v5._paths_overlap(output, source)  # noqa: SLF001
            for output in (*output_dirs, *output_files)
            if output is not None
            for source in protected
        ):
            raise FullCampaignRelayError(
                "Une sortie aval V6 chevauche une source transitive V4/V5/V6"
            )
        if any(
            implementation_v5._paths_overlap(  # noqa: SLF001
                self.config.v4_sidecar_root, source
            )
            for source in (*inherited_sources, self.config.calibration_run_dir, self.config.sidecar_dir)
        ):
            raise FullCampaignRelayError(
                "Le sentinel sidecar du développement V6 doit être vide et distinct"
            )

    def validate_calibration_handoff(self) -> dict[str, Any]:
        plan = self._validated_plan()
        self._validate_transitive_output_separation(plan)
        run_dir = self.config.calibration_run_dir
        source = plan.manifest["v6_development_source"]
        if (
            Path(source["plan_dir"]).resolve() != self.config.v4_plan_dir
            or Path(source["run_dir"]).resolve() != self.config.v4_run_dir
        ):
            raise FullCampaignRelayError(
                "Le relais V6 ne référence pas le développement qui a figé le holdout"
            )
        mode = holdout_v6._registered_execution_mode(plan, run_dir)  # noqa: SLF001
        if mode != holdout_v6.OFFICIAL_EXECUTION_MODE:
            raise FullCampaignRelayError("Le relais aval exige un holdout V6 officiel")
        selection = holdout_v6._load_development_selection(  # noqa: SLF001
            plan, run_dir
        )
        evidence = holdout_v6._load_stage_evidence(  # noqa: SLF001
            plan, run_dir, "holdout"
        )
        result = holdout_v6._build_holdout_result(  # noqa: SLF001
            plan, evidence, selection, execution_mode=mode
        )
        result_path = run_dir / "holdout_result.json"
        if not result_path.is_file() or relay_v4._read_json(result_path) != result:  # noqa: SLF001
            raise FullCampaignRelayError("Décision holdout V6 absente ou non reproductible")
        if result.get("accepted") is not True:
            raise ScientificNoGo("Le holdout V6 est rejeté; aucune campagne aval")
        if (
            result.get("status") != holdout_v6.ACCEPTED_HOLDOUT_STATUS
            or result.get("publishable") is not True
            or result.get("retuning_after_holdout") is not False
            or result.get("holdout_evidence_case_count") != EXPECTED_HOLDOUT_CASES
        ):
            raise FullCampaignRelayError("Acceptation holdout V6 incohérente")
        sidecar = self.validate_finalized_sidecar_handoff()
        run_manifest_path = run_dir / "run_manifest.json"
        progress_path = run_dir / "holdout_progress.json"
        selection_path = run_dir / "development_selection.json"
        run_manifest = relay_v4._read_json(run_manifest_path)  # noqa: SLF001
        progress = relay_v4._read_json(progress_path)  # noqa: SLF001
        return {
            "status": "accepted_read_only_handoff",
            "plan": str((plan.plan_dir / "refinement_plan.json").resolve()),
            "plan_sha256": relay_v4.sha256_file(
                plan.plan_dir / "refinement_plan.json"
            ),
            "source_development_plan": source["plan_dir"],
            "source_development_run": source["run_dir"],
            "development_evidence_case_count": EXPECTED_DEVELOPMENT_CASES,
            "source_new_development_engine_run_count": (
                EXPECTED_NEW_DEVELOPMENT_ENGINE_RUNS
            ),
            "development_selection_signature": source[
                "development_selection_signature"
            ],
            "holdout_run_manifest": str(run_manifest_path.resolve()),
            "holdout_run_manifest_sha256": relay_v4.sha256_file(run_manifest_path),
            "holdout_run_signature": run_manifest["run_signature"],
            "holdout_authorization": str(selection_path.resolve()),
            "holdout_authorization_sha256": relay_v4.sha256_file(selection_path),
            "holdout_authorization_signature": selection["selection_signature"],
            "holdout_progress": str(progress_path.resolve()),
            "holdout_progress_sha256": relay_v4.sha256_file(progress_path),
            "holdout_progress_signature": progress["progress_signature"],
            "holdout_evidence_case_count": EXPECTED_HOLDOUT_CASES,
            "holdout_evidence_signature_set_sha256": result[
                "holdout_evidence_signature_set_sha256"
            ],
            "holdout_result": str(result_path.resolve()),
            "holdout_result_sha256": relay_v4.sha256_file(result_path),
            "holdout_signature": result["holdout_signature"],
            "holdout_status": result["status"],
            "holdout_accepted": True,
            "retuning_after_holdout": False,
            "sidecar": sidecar,
            "relay_development_engine_runs": 0,
            "relay_holdout_engine_runs": 0,
            "calibration_plan_or_run_artifacts_written": False,
            "source_sidecar_inventories_rewritten": False,
        }

    def execute(self) -> int:
        self.prepare()
        self.validate_downstream_corridor_preflight()
        self.build_and_validate_bridge()
        self.plan_campaign()
        self.launch_campaign()
        self.finalize_campaign()
        selection = self._lot_selection()
        self.run_lot_replays(selection)
        self.qualify_physical_cascades()
        self.process_optional_action_replay()
        self.validate_required_action_outcome()
        self.process_optional_curves()
        self.validate_required_curves_outcome()
        self.build_dashboard()
        self.build_final_delivery(len(selection))
        curves_ok = (self.status.get("nominal_curves") or {}).get("status") == "complete_validated"
        action_status = str(
            (self.status.get("action_replay") or {}).get("status") or "not_configured"
        )
        self.status["active_command"] = {}
        self.status["completed_at_utc"] = relay_v4._now()  # noqa: SLF001
        self.update_status(
            "traitement_v6_termine",
            "Relais V6 terminé : campagne 3 330 lignes, lots, qualification, actions et HTML.",
            status=("complete" if curves_ok else "complete_with_limits"),
            progress={
                "validated_upstream_development_cases": EXPECTED_DEVELOPMENT_CASES,
                "validated_upstream_holdout_cases": EXPECTED_HOLDOUT_CASES,
                "campaign_rows": implementation_v5.EXPECTED_CAMPAIGN_ROWS,
                "lot_replay_dossiers": len(selection),
                "physical_qualification": "complete_validated",
                "nominal_curves_available": curves_ok,
                "action_replay_status": action_status,
            },
        )
        return 0


def _child_command(args: Any) -> list[str]:
    command = implementation_v5._child_command(args)  # noqa: SLF001
    if len(command) < 3 or command[:2] != [sys.executable, "-m"]:
        raise FullCampaignRelayError("Commande enfant héritée invalide")
    command[2] = MODULE_NAME
    if "--detached-child" not in command or "--detach" in command:
        raise FullCampaignRelayError("Commande enfant V6 non détachable")
    return command


def _stop_detached_tree(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            stopped = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=30.0,
            )
            if stopped.returncode != 0:
                process.terminate()
        except (OSError, subprocess.TimeoutExpired):
            process.terminate()
    else:  # pragma: no cover
        import signal

        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=30.0)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:  # pragma: no cover
            import signal

            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=30.0)


def detach(args: Any) -> dict[str, Any]:
    """Preflight fully, then start exactly one hidden V6 child process."""

    config = implementation_v5._config_from_args(args)  # noqa: SLF001
    relay = FullCampaignRelayV6(config)
    # No directory, log, receipt or process may be created before both checks.
    config.validate()
    relay.validate_calibration_handoff()
    receipt_path = config.supervision_dir / "detached.json"
    if receipt_path.exists():
        previous = relay_v4._read_json(receipt_path)  # noqa: SLF001
        pid = int(previous.get("pid") or 0)
        state = "actif" if relay_v4._process_running(pid) else "historique"  # noqa: SLF001
        raise FullCampaignRelayError(
            f"Un reçu détaché V6 {state} existe déjà (PID {pid}); utiliser une nouvelle supervision"
        )
    relay.prepare()
    command = _child_command(args)
    log_path = config.supervision_dir / "detached_relay.log"
    reserved_unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.detached.v1",
        "status": "detached_start_reserved",
        "pid": 0,
        "command": command,
        "command_sha256": relay_v4.stable_sha256(command),
        "log_path": str(log_path),
        "status_path": str(relay.status_path),
        "started_at_utc": relay_v4._now(),  # noqa: SLF001
        "preflight_completed_before_process_start": True,
    }
    reserved = {
        **reserved_unsigned,
        "receipt_signature": relay_v4.stable_sha256(reserved_unsigned),
    }
    try:
        with receipt_path.open("x", encoding="utf-8", newline="\n") as receipt_stream:
            json.dump(reserved, receipt_stream, ensure_ascii=False, indent=2)
            receipt_stream.write("\n")
            receipt_stream.flush()
            os.fsync(receipt_stream.fileno())
    except FileExistsError as exc:
        raise FullCampaignRelayError(
            "A concurrent V6 detached relay already reserved this supervision"
        ) from exc
    try:
        with log_path.open("ab") as stream:
            kwargs: dict[str, Any] = {
                "cwd": config.repo,
                "stdin": subprocess.DEVNULL,
                "stdout": stream,
                "stderr": subprocess.STDOUT,
                "shell": False,
                "close_fds": True,
            }
            if os.name == "nt":
                kwargs["creationflags"] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NO_WINDOW
                )
            else:  # pragma: no cover
                kwargs["start_new_session"] = True
            process = subprocess.Popen(command, **kwargs)
    except BaseException as exc:
        failed_unsigned = {
            **reserved_unsigned,
            "status": "detached_start_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        relay_v4._atomic_json(  # noqa: SLF001
            receipt_path,
            {
                **failed_unsigned,
                "receipt_signature": relay_v4.stable_sha256(failed_unsigned),
            },
        )
        raise
    unsigned = {
        **reserved_unsigned,
        "status": "detached_relay_started",
        "pid": process.pid,
    }
    payload = {**unsigned, "receipt_signature": relay_v4.stable_sha256(unsigned)}
    try:
        relay_v4._atomic_json(receipt_path, payload)  # noqa: SLF001
    except BaseException:
        _stop_detached_tree(process)
        raise
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    with _v6_downstream_binding():
        args = implementation_v5._parser().parse_args(argv)  # noqa: SLF001
        if args.detach:
            try:
                print(json.dumps(detach(args), ensure_ascii=False, indent=2))
                return 0
            except ScientificNoGo as exc:
                print(f"RELAIS V6 ARRÊT SCIENTIFIQUE : {exc}", file=sys.stderr)
                return 3
            except Exception as exc:
                print(f"RELAIS V6 NON LANCÉ : {exc}", file=sys.stderr)
                return 2
        config = implementation_v5._config_from_args(args)  # noqa: SLF001
        relay = FullCampaignRelayV6(config)
        relay_v4._prevent_sleep(True)  # noqa: SLF001
        try:
            config.validate()
            relay.validate_calibration_handoff()
            with implementation_v5._relay_lock(  # noqa: SLF001
                config.supervision_dir / ".relay.lock"
            ):
                return relay.execute()
        except ScientificNoGo as exc:
            print(f"RELAIS V6 ARRÊT SCIENTIFIQUE : {exc}", file=sys.stderr)
            return 3
        except KeyboardInterrupt:
            print("RELAIS V6 INTERROMPU; consulter status.json", file=sys.stderr)
            return 130
        except Exception as exc:  # pragma: no cover - process boundary diagnostics
            if relay.contract:
                relay.status["error"] = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": "".join(traceback.format_exception(exc)),
                }
                relay.update_status("echec_v6", str(exc), status="failed")
            print(f"RELAIS V6 EN ÉCHEC : {exc}", file=sys.stderr)
            return 1
        finally:
            relay_v4._prevent_sleep(False)  # noqa: SLF001


if __name__ == "__main__":
    raise SystemExit(main())
