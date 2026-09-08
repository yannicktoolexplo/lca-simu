from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / (
    "etudecas/prototypes/scan_2027_risk_control/"
    "run_supplier_v8_v2_to_stage3_v4_chain_task.ps1"
)
TEMPLATE = SCRIPT.with_name("supplier_v8_stage3_go_20260906_v5.template.json")
ARCHIVED_TEMPLATE = SCRIPT.with_name(
    "supplier_v8_stage3_go_20260906_v4.template.json"
)
V3_SCRIPT = SCRIPT.with_name("run_supplier_v8_v2_to_stage3_v3_chain_task.ps1")
V3_SHA256 = "451e3ab5e7a5f737db6d9375242ca88a179aff65aa2db39bd7ced63c217529b6"
INVENTORY_SIGNATURE = "d56761c3cdd704ec9d31bb2b452ee5dea25e9cdcf1e87c67d787a09e20b5a442"
ARTIFACT_ROOT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")


def _powershell() -> str:
    return str(
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )


def test_v4_preserves_prior_material_and_has_a_new_inert_bound_go() -> None:
    assert hashlib.sha256(V3_SCRIPT.read_bytes()).hexdigest() == V3_SHA256
    archived_payload = json.loads(ARCHIVED_TEMPLATE.read_text(encoding="utf-8"))
    assert archived_payload["decision"] == "WAIT_FOR_EXPLICIT_GO"
    assert archived_payload["chain_wrapper_sha256"] == (
        "b322e47b8820e7cc714ab9436555bc4607b193e11c397a6cf7dfbc76cd6ef642"
    )
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert payload["schema_version"] == (
        "etudecas.supplier_v8_v2_to_stage3_v4_chain.v1.stage3_go.v1"
    )
    assert payload["decision"] == "WAIT_FOR_EXPLICIT_GO"
    assert payload["approved_by"] == ""
    assert payload["approved_at_utc"] == ""
    assert payload["stage3_inventory_signature"] == INVENTORY_SIGNATURE
    assert payload["change_scope"] == (
        "signed_v8_comparability_projection_for_validation_only"
    )
    assert (
        payload["chain_wrapper_sha256"]
        == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    )


def test_v4_parses_in_windows_powershell_5() -> None:
    environment = dict(os.environ)
    environment["V8_CHAIN_V4_PARSE_TARGET"] = str(SCRIPT)
    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:V8_CHAIN_V4_PARSE_TARGET,[ref]$tokens,[ref]$errors) | Out-Null; "
        "if($errors.Count){$errors|%{[Console]::Error.WriteLine($_.Message)};exit 1}; "
        "Write-Output 'PARSE_OK'"
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


def test_v4_atomic_json_supports_two_real_powershell_5_writes(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "status.json"
    environment = dict(os.environ)
    environment["V8_CHAIN_V4_PARSE_TARGET"] = str(SCRIPT)
    environment["V8_CHAIN_V4_ATOMIC_TARGET"] = str(destination)
    command = (
        "$tokens=$null; $errors=$null; "
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:V8_CHAIN_V4_PARSE_TARGET,[ref]$tokens,[ref]$errors); "
        "foreach($name in @('Get-FullPath','Write-JsonAtomic')){"
        "$node=$ast.Find({param($n) $n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq $name},$true); Invoke-Expression $node.Extent.Text}; "
        "Write-JsonAtomic -Path $env:V8_CHAIN_V4_ATOMIC_TARGET "
        "-Payload ([ordered]@{sequence=1;value='first'}); "
        "Write-JsonAtomic -Path $env:V8_CHAIN_V4_ATOMIC_TARGET "
        "-Payload ([ordered]@{sequence=2;value='second'}); "
        "$result=Get-Content -Raw -LiteralPath $env:V8_CHAIN_V4_ATOMIC_TARGET|"
        "ConvertFrom-Json; if($result.sequence -ne 2){exit 12}; "
        "$parent=[IO.Path]::GetDirectoryName($env:V8_CHAIN_V4_ATOMIC_TARGET); "
        "$leaf=[IO.Path]::GetFileName($env:V8_CHAIN_V4_ATOMIC_TARGET); "
        "if(@(Get-ChildItem -LiteralPath $parent -Force|?{"
        "$_.Name -like ('.'+$leaf+'.tmp.*') -or "
        "$_.Name -like ('.'+$leaf+'.bak.*')}).Count -ne 0){exit 13}; "
        "Write-Output 'ATOMIC_PS5_OK'"
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
    assert b"ATOMIC_PS5_OK" in completed.stdout
    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "sequence": 2,
        "value": "second",
    }


def test_v4_validate_only_accepts_its_own_explicit_go(tmp_path: Path) -> None:
    supervision = tmp_path / "must-not-be-created"
    go_file = tmp_path / "go-v4.json"
    go_file.write_text(
        json.dumps(
            {
                "schema_version": (
                    "etudecas.supplier_v8_v2_to_stage3_v4_chain.v1.stage3_go.v1"
                ),
                "decision": "GO_STAGE3_V4",
                "approved_by": "automated-test",
                "approved_at_utc": "2026-09-06T12:30:00+00:00",
                "stage3_inventory_signature": INVENTORY_SIGNATURE,
                "chain_wrapper_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
                "campaign_root": str(
                    ARTIFACT_ROOT
                    / "supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
                ),
                "results_dir": str(
                    ARTIFACT_ROOT
                    / "supplier_operating_point_full_campaign_v8_results_20260906_v2"
                ),
                "stage3_supervision_dir": str(
                    ARTIFACT_ROOT / "supplier_v8_stage3_supervision_20260906_v3"
                ),
                "final_html": str(
                    ARTIFACT_ROOT
                    / "OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_V8_STAGE2_20260906_V3.html"
                ),
            }
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
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
            str(supervision),
            "-Stage3GoFile",
            str(go_file),
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        timeout=90,
    )
    assert completed.returncode == 0, (completed.stdout + completed.stderr).decode(
        errors="replace"
    )
    payload = json.loads(completed.stdout.decode("utf-8-sig"))
    assert payload["status"] == "valid"
    assert payload["mode"] == "validate_only"
    assert (
        payload["stage3_go"]["chain_wrapper_sha256"]
        == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    )
    assert payload["launch_performed"] is False
    assert payload["filesystem_mutation_performed"] is False
    assert not supervision.exists()
