from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / (
    "etudecas/prototypes/scan_2027_risk_control/"
    "run_supplier_v8_v2_to_stage3_v3_chain_task.ps1"
)
GO_TEMPLATE = SCRIPT.with_name("supplier_v8_stage3_go_20260906_v3.template.json")
ARTIFACT_ROOT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
CAMPAIGN_ROOT = ARTIFACT_ROOT / (
    "supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
)
RESULTS_DIR = ARTIFACT_ROOT / (
    "supplier_operating_point_full_campaign_v8_results_20260906_v2"
)
STAGE3_SUPERVISION_DIR = ARTIFACT_ROOT / "supplier_v8_stage3_supervision_20260906_v3"
FINAL_HTML = ARTIFACT_ROOT / (
    "OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_V8_STAGE2_20260906_V3.html"
)
INVENTORY_SIGNATURE = "d56761c3cdd704ec9d31bb2b452ee5dea25e9cdcf1e87c67d787a09e20b5a442"
BASE_V8_LAUNCHER = SCRIPT.with_name(
    "launch_supplier_operating_point_full_campaign_v8.py"
)
BASE_V8_LAUNCHER_SHA256 = (
    "bd8f39d03f97766e193a683076884739bdb72dabcc51fe06b2eadd4e9a146405"
)


def _powershell() -> str:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    return str(
        system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )


def _go_payload() -> dict[str, str]:
    return {
        "schema_version": (
            "etudecas.supplier_v8_v2_to_stage3_v3_chain.v1.stage3_go.v1"
        ),
        "decision": "GO_STAGE3_V3",
        "approved_by": "automated-test",
        "approved_at_utc": "2026-09-06T12:30:00+00:00",
        "stage3_inventory_signature": INVENTORY_SIGNATURE,
        "chain_wrapper_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
        "campaign_root": str(CAMPAIGN_ROOT),
        "results_dir": str(RESULTS_DIR),
        "stage3_supervision_dir": str(STAGE3_SUPERVISION_DIR),
        "final_html": str(FINAL_HTML),
    }


def test_go_template_is_inert_and_bound_to_the_frozen_chain() -> None:
    payload = json.loads(GO_TEMPLATE.read_text(encoding="utf-8"))

    assert payload["decision"] == "WAIT_FOR_EXPLICIT_GO"
    assert payload["approved_by"] == ""
    assert payload["approved_at_utc"] == ""
    assert payload["stage3_inventory_signature"] == INVENTORY_SIGNATURE
    assert (
        payload["chain_wrapper_sha256"]
        == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    )


def _validate_only(
    *,
    chain_supervision: Path,
    go_file: Path,
    extra_arguments: list[str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-ValidateOnly",
            "-ChainSupervisionDir",
            str(chain_supervision),
            "-Stage3GoFile",
            str(go_file),
            *(extra_arguments or []),
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        timeout=90,
    )


def test_chain_wrapper_parses_in_windows_powershell() -> None:
    environment = dict(os.environ)
    environment["V8_CHAIN_PARSE_TARGET"] = str(SCRIPT)
    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:V8_CHAIN_PARSE_TARGET,[ref]$tokens,[ref]$errors) | Out-Null; "
        "if ($errors.Count) { $errors | ForEach-Object { "
        "[Console]::Error.WriteLine($_.Message) }; exit 1 }; "
        "[Console]::Out.WriteLine('PARSE_OK')"
    )

    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"PARSE_OK" in completed.stdout


def test_chain_hashes_the_base_launcher_imported_by_resilient_adapter() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    relative_path = (
        r"etudecas\prototypes\scan_2027_risk_control"
        r"\launch_supplier_operating_point_full_campaign_v8.py"
    )

    assert BASE_V8_LAUNCHER.is_file()
    assert hashlib.sha256(BASE_V8_LAUNCHER.read_bytes()).hexdigest() == (
        BASE_V8_LAUNCHER_SHA256
    )
    assert f'"{relative_path}" = "{BASE_V8_LAUNCHER_SHA256}"' in source


def test_task_disable_accepts_running_instance_when_definition_is_disabled() -> None:
    environment = dict(os.environ)
    environment["V8_CHAIN_PARSE_TARGET"] = str(SCRIPT)
    command = (
        "$tokens=$null; $errors=$null; "
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:V8_CHAIN_PARSE_TARGET,[ref]$tokens,[ref]$errors); "
        "$node=$ast.Find({param($n) $n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq 'Disable-OwnScheduledTask'},$true); "
        "Invoke-Expression $node.Extent.Text; "
        "$TaskName='fixture'; $TaskPath='\\'; $script:disableCalls=0; "
        "$script:definitionEnabled=$false; "
        "function Assert-OwnScheduledTask { "
        "[pscustomobject]@{State='Running'} }; "
        "function Disable-ScheduledTask { "
        "param($TaskName,$TaskPath,$ErrorAction); $script:disableCalls++ }; "
        "function Get-ScheduledTask { "
        "param($TaskName,$TaskPath,$ErrorAction); "
        "[pscustomobject]@{State='Running'; Settings=[pscustomobject]@{"
        "Enabled=$script:definitionEnabled}} }; "
        "function Export-ScheduledTask { throw 'fallback must not be used' }; "
        "$proof=Disable-OwnScheduledTask; "
        "if ($script:disableCalls -ne 1 -or $proof.definition_enabled -ne $false "
        "-or $proof.observed_runtime_state -ne 'Running' "
        "-or $proof.running_state_accepted -ne $true) { exit 2 }; "
        "$script:definitionEnabled=$true; $refused=$false; "
        "try { Disable-OwnScheduledTask | Out-Null } catch { $refused=$true }; "
        "if (-not $refused) { exit 3 }; Write-Output 'MOCK_OK'"
    )

    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"MOCK_OK" in completed.stdout


def test_validate_only_is_read_only_and_reports_the_complete_chain(
    tmp_path: Path,
) -> None:
    untouched_supervision = tmp_path / "must-not-be-created"
    go_file = tmp_path / "independent-stage3-go.json"
    go_file.write_text(json.dumps(_go_payload()), encoding="utf-8")

    completed = _validate_only(
        chain_supervision=untouched_supervision,
        go_file=go_file,
    )

    stderr = completed.stderr.decode("utf-8", errors="replace")
    assert completed.returncode == 0, stderr
    payload = json.loads(completed.stdout.decode("utf-8-sig"))
    assert payload["status"] == "valid"
    assert payload["mode"] == "validate_only"
    assert payload["launch_performed"] is False
    assert payload["scheduled_task_changed"] is False
    assert payload["filesystem_mutation_performed"] is False
    assert payload["planned_steps"] == [
        "01_supervisor",
        "02_finalizer_v8",
        "wait_independent_stage3_go",
        "03_stage3_v3_foreground",
        "04_validate_html",
        "disable_own_task_after_success",
    ]
    assert payload["stage3_go_present"] is True
    assert payload["stage3_go"]["stage3_inventory_signature"] == (INVENTORY_SIGNATURE)
    assert (
        payload["stage3_go"]["chain_wrapper_sha256"]
        == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    )
    assert payload["validation"]["stage3_inventory_signature"] == (INVENTORY_SIGNATURE)
    assert not untouched_supervision.exists()


@pytest.mark.parametrize(
    ("field", "binding"),
    [
        ("stage3_inventory_signature", "missing"),
        ("stage3_inventory_signature", "wrong"),
        ("chain_wrapper_sha256", "missing"),
        ("chain_wrapper_sha256", "wrong"),
    ],
)
def test_validate_only_rejects_unbound_go(
    tmp_path: Path,
    field: str,
    binding: str,
) -> None:
    payload = _go_payload()
    if binding == "missing":
        payload.pop(field)
    else:
        payload[field] = "0" * 64
    go_file = tmp_path / f"bad-go-{field}-{binding}.json"
    go_file.write_text(json.dumps(payload), encoding="utf-8")
    untouched_supervision = tmp_path / "must-not-be-created"

    completed = _validate_only(
        chain_supervision=untouched_supervision,
        go_file=go_file,
    )

    output = (completed.stdout + completed.stderr).decode("utf-8", errors="replace")
    assert completed.returncode != 0
    assert field in output
    assert not untouched_supervision.exists()


def test_validate_only_accepts_absent_go_without_authorizing_stage3(
    tmp_path: Path,
) -> None:
    untouched_supervision = tmp_path / "must-not-be-created"
    absent_go = tmp_path / "no-go-file.json"

    completed = _validate_only(
        chain_supervision=untouched_supervision,
        go_file=absent_go,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout.decode("utf-8-sig"))
    assert payload["status"] == "valid"
    assert payload["stage3_go_present"] is False
    assert payload["stage3_go"] is None
    assert payload["launch_performed"] is False
    assert not untouched_supervision.exists()


def test_validate_only_rejects_missing_required_stage3_input(
    tmp_path: Path,
) -> None:
    untouched_supervision = tmp_path / "must-not-be-created"
    absent_go = tmp_path / "no-go-file.json"
    missing_plan = tmp_path / "missing-v7-plan"

    completed = _validate_only(
        chain_supervision=untouched_supervision,
        go_file=absent_go,
        extra_arguments=["-V7PlanDir", str(missing_plan)],
    )

    assert completed.returncode != 0
    assert b"V7PlanDir" in completed.stderr + completed.stdout
    assert not untouched_supervision.exists()


def test_chain_is_foreground_gated_idempotent_and_non_destructive() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    runtime = source.split("# Runtime starts only", maxsplit=1)[1]

    supervisor_index = runtime.index(
        "supervise_supplier_operating_point_full_campaign_v8_v2"
    )
    finalizer_index = runtime.index(
        "finalize_supplier_operating_point_full_campaign_v8"
    )
    go_index = runtime.index("$goEvidence = Wait-Stage3Go")
    delivery_arguments_index = runtime.index("supplier_v8_stage3_delivery")
    existing_html_validation_index = runtime.index(
        'Invoke-LoggedPythonStep -Step "03_existing_html_validation"'
    )
    stage3_index = runtime.index("supplier_v8_stage3_watcher")
    html_validation_index = runtime.index(
        'Invoke-LoggedPythonStep -Step "04_validate_html"'
    )
    disable_index = runtime.index("Disable-OwnScheduledTask")
    assert (
        supervisor_index
        < finalizer_index
        < go_index
        < delivery_arguments_index
        < existing_html_validation_index
        < stage3_index
        < html_validation_index
        < disable_index
    )
    assert '"--detach"' not in runtime
    assert "campaign_validation_v8.json" in runtime
    assert "existing_v8_overlay_revalidated_by_finalizer" in runtime
    assert "existing_html_and_manifest_revalidated" in runtime
    assert "03_stage3_v3_foreground.stdout.log" not in source
    assert '"$Step.stdout.log"' in source
    assert '"$Step.stderr.log"' in source
    assert "Register-ScheduledTask" not in source
    assert "New-ScheduledTask" not in source
    assert "Unregister-ScheduledTask" not in source
    assert "Remove-Item" not in source
    assert "[IO.File]::Delete" not in source
    assert "$actions.Count -ne 1" in source
    assert "expectedTaskArguments" in source
    assert "options ou paramètres non autorisés" in source
    assert 'Settings.PSObject.Properties["Enabled"]' in source
    assert "observed_runtime_state" in source
    assert "stage3_inventory_signature" in source
    assert "chain_wrapper_sha256" in source
    assert "03_existing_html_validation" in source
    assert "[MANUAL_INTERVENTION_REQUIRED]" in source
    assert "manual_intervention_required.json" in source
    assert "aucun écrasement ou suppression automatique" in source
    assert source.count("$preFinalizerValidation = Assert-StaticInputs") == 1
    assert source.count("$preStage3Validation = Assert-StaticInputs") == 1
    assert source.count("$preHtmlValidation = Assert-StaticInputs") == 1


def test_chain_defaults_reproduce_the_stage3_v3_runbook_paths() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    runbook = SCRIPT.with_name("supplier_v8_stage3_runbook_20260906_v3.md").read_text(
        encoding="utf-8"
    )
    required_flags = (
        "--v7-plan-dir",
        "--v7-run-dir",
        "--trace-package-dir",
        "--bridge-json",
        "--campaign-root",
        "--results-dir",
        "--stage1-supervision-dir",
        "--observed-2025-dir",
        "--lot-replay-root",
        "--qualification-dir",
        "--action-replay-root",
        "--curves-dir",
        "--registry-dir",
        "--final-html",
        "--supervision-dir",
    )
    for flag in required_flags:
        assert flag in source
        assert flag in runbook
    for output_name in (
        "supplier_v8_stage3_lot_replays_20260906_v3",
        "supplier_v8_stage3_physical_qualification_20260906_v3",
        "supplier_v8_stage3_action_replays_20260906_v3",
        "supplier_v8_stage3_nominal_curves_20260906_v3",
        "supplier_v8_stage3_incident_lot_registry_20260906_v3",
        "supplier_v8_stage3_supervision_20260906_v3",
        "OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_V8_STAGE2_20260906_V3.html",
    ):
        assert output_name in source
        assert output_name in runbook


def test_chain_source_is_utf8_bom_and_contains_no_mojibake() -> None:
    raw = SCRIPT.read_bytes()
    source = raw.decode("utf-8-sig")
    bad_markers = (
        chr(0x00C3),
        chr(0x00C2),
        chr(0x00E2) + chr(0x20AC),
    )

    assert raw.startswith(b"\xef\xbb\xbf")
    assert not any(marker in source for marker in bad_markers)
    assert "Cha\u00eene termin\u00e9e" in source
