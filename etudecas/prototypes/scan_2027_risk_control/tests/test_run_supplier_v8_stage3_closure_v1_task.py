from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / (
    "etudecas/prototypes/scan_2027_risk_control/"
    "run_supplier_v8_stage3_closure_v1_task.ps1"
)
VERIFIER = SCRIPT.with_name("verify_supplier_v8_stage3_closure.py")
CHAIN_WRAPPER = SCRIPT.with_name("run_supplier_v8_v2_to_stage3_v3_chain_task.ps1")
EXPECTED_VERIFIER_SHA256 = (
    "004ab109ac4d396cc50501b17b58fc0b64798352e97d08cadb941aff0ce6de1a"
)
EXPECTED_CHAIN_SHA256 = (
    "451e3ab5e7a5f737db6d9375242ca88a179aff65aa2db39bd7ced63c217529b6"
)
EXPECTED_INVENTORY_SIGNATURE = (
    "d56761c3cdd704ec9d31bb2b452ee5dea25e9cdcf1e87c67d787a09e20b5a442"
)


def _powershell() -> str:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    return str(
        system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )


def test_wrapper_parses_in_windows_powershell() -> None:
    environment = dict(os.environ)
    environment["CLOSURE_WRAPPER_PARSE_TARGET"] = str(SCRIPT)
    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:CLOSURE_WRAPPER_PARSE_TARGET,[ref]$tokens,[ref]$errors) | Out-Null; "
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


def test_validate_only_is_inert_and_checks_frozen_hashes(tmp_path: Path) -> None:
    closure_dir = tmp_path / "new-closure-root"
    report = closure_dir / "closure_report.json"
    absent_stage3 = tmp_path / "absent-stage3"
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
            "-ClosureDir",
            str(closure_dir),
            "-ReportJson",
            str(report),
            "-Stage3SupervisionDir",
            str(absent_stage3),
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    payload = json.loads(completed.stdout.decode("utf-8-sig"))
    assert payload["status"] == "valid"
    assert payload["launch_performed"] is False
    assert payload["simulation_engine_started"] is False
    assert payload["scheduled_task_changed"] is False
    assert payload["filesystem_mutation_performed"] is False
    assert payload["validation"]["stage3_inventory_signature"] == (
        EXPECTED_INVENTORY_SIGNATURE
    )
    assert (
        payload["validation"]["frozen_source_sha256"][
            "etudecas\\prototypes\\scan_2027_risk_control\\verify_supplier_v8_stage3_closure.py"
        ]
        == EXPECTED_VERIFIER_SHA256
    )
    assert not closure_dir.exists()
    assert not absent_stage3.exists()


def test_runtime_polls_only_signed_status_then_runs_verifier_once() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    runtime = source.split("# Runtime starts only", maxsplit=1)[1]
    readiness_index = runtime.index("$readiness = Get-Stage3Readiness")
    verifier_index = runtime.index("$verifierResult = Invoke-ClosureVerifier")
    validate_index = runtime.index("$reportValidation = Validate-ClosureReport")
    disable_index = runtime.index("$disableProof = Disable-OwnScheduledTask")

    assert readiness_index < verifier_index < validate_index < disable_index
    assert runtime.count("Invoke-ClosureVerifier") == 1
    assert "Start-Sleep -Seconds $PollSeconds" in runtime
    assert "[ValidateRange(1, 60)]" in source
    assert 'status.get("status") == "complete"' in source
    assert 'status.get("step") == "termine"' in source
    assert "verify_signature(status" in source
    assert "verify_signature(contract" in source


def test_wrapper_is_additive_has_atomic_status_and_never_creates_tasks() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    assert "[IO.File]::Replace($temporary, $destination" in source
    assert "[IO.File]::Move($temporary, $destination)" in source
    assert "[Threading.Mutex]::new" in source
    assert "SetThreadExecutionState" in source
    assert "Register-ScheduledTask" not in source
    assert "New-ScheduledTask" not in source
    assert "Unregister-ScheduledTask" not in source
    assert 'supplier_operating_point_full_campaign_v8.py"' not in source
    assert "supplier_v8_stage3_pipeline --" not in source
    assert "no_simulation_engine_started = $true" in source


def test_atomic_json_supports_two_real_windows_powershell_5_writes(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "status.json"
    environment = dict(os.environ)
    environment["CLOSURE_WRAPPER_PARSE_TARGET"] = str(SCRIPT)
    environment["CLOSURE_ATOMIC_TEST_TARGET"] = str(destination)
    command = (
        "$tokens=$null; $errors=$null; "
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:CLOSURE_WRAPPER_PARSE_TARGET,[ref]$tokens,[ref]$errors); "
        "foreach($name in @('Get-FullPath','Write-JsonAtomic')) { "
        "$node=$ast.Find({param($n) $n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq $name},$true); Invoke-Expression $node.Extent.Text }; "
        "Write-JsonAtomic -Path $env:CLOSURE_ATOMIC_TEST_TARGET "
        "-Payload ([ordered]@{sequence=1; value='first'}); "
        "Write-JsonAtomic -Path $env:CLOSURE_ATOMIC_TEST_TARGET "
        "-Payload ([ordered]@{sequence=2; value='second'}); "
        "$result=Get-Content -Raw -LiteralPath $env:CLOSURE_ATOMIC_TEST_TARGET "
        "| ConvertFrom-Json; "
        "if($result.sequence -ne 2 -or $result.value -ne 'second'){exit 12}; "
        "$parent=[IO.Path]::GetDirectoryName($env:CLOSURE_ATOMIC_TEST_TARGET); "
        "$leaf=[IO.Path]::GetFileName($env:CLOSURE_ATOMIC_TEST_TARGET); "
        "if(@(Get-ChildItem -LiteralPath $parent -Force | Where-Object { "
        "$_.Name -like ('.'+$leaf+'.tmp.*') -or "
        "$_.Name -like ('.'+$leaf+'.bak.*') }).Count -ne 0){exit 13}; "
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


def test_frozen_hash_bindings_are_exact() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    assert hashlib.sha256(VERIFIER.read_bytes()).hexdigest() == EXPECTED_VERIFIER_SHA256
    assert (
        hashlib.sha256(CHAIN_WRAPPER.read_bytes()).hexdigest() == EXPECTED_CHAIN_SHA256
    )
    assert f' = "{EXPECTED_INVENTORY_SIGNATURE}"' in source
    assert f' = "{EXPECTED_VERIFIER_SHA256}"' in source
    assert f' = "{EXPECTED_CHAIN_SHA256}"' in source


def test_task_disable_occurs_only_after_revalidated_technical_verdict() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    runtime = source.split("# Runtime starts only", maxsplit=1)[1]
    assert runtime.index("$reportValidation = Validate-ClosureReport") < runtime.index(
        "$disableProof = Disable-OwnScheduledTask"
    )
    assert 'technical not in {"CONFORME_TECHNIQUE", "NON_CONFORME_TECHNIQUE"}' in source
    assert "report_revalidated = $true" in runtime
    assert '$ExpectedTaskName = "Codex-Supplier-V8-Stage3-Closure-V1"' in source
    assert "$TaskName -ne $ExpectedTaskName" in source


def test_disable_function_targets_only_the_mocked_exact_task() -> None:
    environment = dict(os.environ)
    environment["CLOSURE_WRAPPER_PARSE_TARGET"] = str(SCRIPT)
    command = (
        "$tokens=$null; $errors=$null; "
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:CLOSURE_WRAPPER_PARSE_TARGET,[ref]$tokens,[ref]$errors); "
        "$node=$ast.Find({param($n) $n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq 'Disable-OwnScheduledTask'},$true); "
        "Invoke-Expression $node.Extent.Text; "
        "$TaskName='Codex-Supplier-V8-Stage3-Closure-V1'; $TaskPath='\\'; "
        "$script:disableCalls=0; "
        "function Assert-OwnScheduledTask { [pscustomobject]@{State='Running'} }; "
        "function Disable-ScheduledTask { param($TaskName,$TaskPath,$ErrorAction); "
        "$script:disableCalls++; if($TaskName -ne 'Codex-Supplier-V8-Stage3-Closure-V1'){exit 8} }; "
        "function Get-ScheduledTask { param($TaskName,$TaskPath,$ErrorAction); "
        "[pscustomobject]@{State='Running'; Settings=[pscustomobject]@{Enabled=$false}} }; "
        "$proof=Disable-OwnScheduledTask; "
        "if($script:disableCalls -ne 1 -or $proof.definition_enabled -ne $false "
        "-or $proof.running_state_accepted -ne $true){exit 9}; "
        "Write-Output 'MOCK_OK'"
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
