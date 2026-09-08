from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / (
    "etudecas/prototypes/scan_2027_risk_control/"
    "run_supplier_v8_op100_checkpoint_10_task.ps1"
)
ADAPTER = SCRIPT.with_name("supplier_v8_op100_checkpoint_10.py")
FROZEN_CHAIN_WRAPPER = SCRIPT.with_name(
    "run_supplier_v8_v2_to_stage3_v3_chain_task.ps1"
)
EXPECTED_ADAPTER_SHA256 = (
    "4c8a672869073cd9193357c0bfd4086f224f7f215c8d6d8818eae194ae9199c8"
)
EXPECTED_FROZEN_WRAPPER_SHA256 = (
    "451e3ab5e7a5f737db6d9375242ca88a179aff65aa2db39bd7ced63c217529b6"
)
EXPECTED_STAGE3_INVENTORY = (
    "d56761c3cdd704ec9d31bb2b452ee5dea25e9cdcf1e87c67d787a09e20b5a442"
)


def _powershell() -> str:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    return str(
        system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )


def _powershell_command(
    command: str, *, environment: dict[str, str]
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=60,
    )


def test_wrapper_parses_and_contains_only_the_checkpoint_sequence() -> None:
    environment = dict(os.environ)
    environment["CHECKPOINT10_SCRIPT"] = str(SCRIPT)
    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:CHECKPOINT10_SCRIPT,[ref]$tokens,[ref]$errors) | Out-Null; "
        "if ($errors.Count) { $errors | ForEach-Object { "
        "[Console]::Error.WriteLine($_.Message) }; exit 1 }; "
        "Write-Output 'PARSE_OK'"
    )
    completed = _powershell_command(command, environment=environment)
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"PARSE_OK" in completed.stdout

    source = SCRIPT.read_text(encoding="utf-8-sig")
    assert (
        '$AdapterModule = "etudecas.prototypes.scan_2027_risk_control.'
        'supplier_v8_op100_checkpoint_10"' in source
    )
    assert '$TaskName = "Codex-Supplier-V8-Op100-Checkpoint10"' in source
    assert "if ($PollSeconds -lt 1 -or $PollSeconds -gt 60)" in source
    assert 'Invoke-CheckpointMode -Mode "readiness"' in source
    assert 'Invoke-CheckpointMode -Mode "build"' in source
    assert 'Invoke-CheckpointMode -Mode "validate"' in source
    assert "run-shard" not in source
    assert "launch_supplier_operating_point" not in source
    assert "Register-ScheduledTask" not in source
    assert "Start-ScheduledTask" not in source


def test_validate_only_is_inert_and_revalidates_frozen_inputs(tmp_path: Path) -> None:
    campaign_root = tmp_path / "campaign"
    output_dir = tmp_path / "output"
    supervision_dir = tmp_path / "supervision"
    campaign_root.mkdir()
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
            "-Repo",
            str(REPO),
            "-Python",
            sys.executable,
            "-CampaignRoot",
            str(campaign_root),
            "-OutputDir",
            str(output_dir),
            "-SupervisionDir",
            str(supervision_dir),
            "-PollSeconds",
            "60",
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    payload = json.loads(completed.stdout.decode("utf-8-sig"))
    assert payload["status"] == "valid"
    assert payload["mode"] == "validate_only"
    assert payload["launch_performed"] is False
    assert payload["build_performed"] is False
    assert payload["scheduled_task_changed"] is False
    assert payload["filesystem_mutation_performed"] is False
    assert payload["task_name"] == "Codex-Supplier-V8-Op100-Checkpoint10"
    assert payload["poll_seconds"] == 60
    assert payload["planned_steps"] == [
        "readiness",
        "build",
        "validate",
        "disable_own_task_after_success",
    ]
    assert payload["validation"] == {
        "adapter_sha256": EXPECTED_ADAPTER_SHA256,
        "frozen_chain_wrapper_sha256": EXPECTED_FROZEN_WRAPPER_SHA256,
        "stage3_inventory_signature": EXPECTED_STAGE3_INVENTORY,
    }
    assert hashlib.sha256(ADAPTER.read_bytes()).hexdigest() == EXPECTED_ADAPTER_SHA256
    assert (
        hashlib.sha256(FROZEN_CHAIN_WRAPPER.read_bytes()).hexdigest()
        == EXPECTED_FROZEN_WRAPPER_SHA256
    )
    assert not output_dir.exists()
    assert not supervision_dir.exists()


def test_readiness_exit_two_means_waiting_and_other_error_fails_closed() -> None:
    environment = dict(os.environ)
    environment["CHECKPOINT10_SCRIPT"] = str(SCRIPT)
    command = r"""
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile(
    $env:CHECKPOINT10_SCRIPT,[ref]$tokens,[ref]$errors)
foreach ($name in @('ConvertFrom-CheckpointJson','Get-ReadinessDecision')) {
    $node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
    Invoke-Expression $node.Extent.Text
}
$waiting=Get-ReadinessDecision -Invocation ([ordered]@{
    exit_code=2; stdout='{"ready":false,"status":"running_target_shards"}'; stderr=''
})
if ($waiting.disposition -ne 'waiting') { exit 2 }
$ready=Get-ReadinessDecision -Invocation ([ordered]@{
    exit_code=0; stdout='{"ready":true,"status":"ready_two_complete_shards"}'; stderr=''
})
if ($ready.disposition -ne 'ready') { exit 3 }
$failedClosed=$false
try {
    Get-ReadinessDecision -Invocation ([ordered]@{
        exit_code=1; stdout='{"status":"failed_closed"}'; stderr='failure'
    }) | Out-Null
}
catch { $failedClosed=$true }
if (-not $failedClosed) { exit 4 }
Write-Output 'DECISIONS_OK'
"""
    completed = _powershell_command(command, environment=environment)
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"DECISIONS_OK" in completed.stdout


def test_atomic_status_writer_replaces_without_leaving_temporary_files(
    tmp_path: Path,
) -> None:
    environment = dict(os.environ)
    environment["CHECKPOINT10_SCRIPT"] = str(SCRIPT)
    environment["CHECKPOINT10_STATUS"] = str(tmp_path / "status.json")
    command = r"""
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile(
    $env:CHECKPOINT10_SCRIPT,[ref]$tokens,[ref]$errors)
foreach ($name in @('Get-FullPath','Write-JsonAtomic')) {
    $node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
    Invoke-Expression $node.Extent.Text
}
Write-JsonAtomic -Path $env:CHECKPOINT10_STATUS -Payload ([ordered]@{status='first'})
Write-JsonAtomic -Path $env:CHECKPOINT10_STATUS -Payload ([ordered]@{status='second'})
$payload=Get-Content -LiteralPath $env:CHECKPOINT10_STATUS -Raw | ConvertFrom-Json
if ($payload.status -ne 'second') { exit 2 }
$temporary=@(Get-ChildItem -LiteralPath ([IO.Path]::GetDirectoryName($env:CHECKPOINT10_STATUS)) -Filter '.status.json.tmp.*')
if ($temporary.Count -ne 0) { exit 3 }
$backup=@(Get-ChildItem -LiteralPath ([IO.Path]::GetDirectoryName($env:CHECKPOINT10_STATUS)) -Filter '.status.json.backup.*')
if ($backup.Count -ne 0) { exit 4 }
Write-Output 'ATOMIC_OK'
"""
    completed = _powershell_command(command, environment=environment)
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"ATOMIC_OK" in completed.stdout


def test_task_disable_targets_only_the_dedicated_task() -> None:
    environment = dict(os.environ)
    environment["CHECKPOINT10_SCRIPT"] = str(SCRIPT)
    command = r"""
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile(
    $env:CHECKPOINT10_SCRIPT,[ref]$tokens,[ref]$errors)
$node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Disable-OwnScheduledTask'},$true)
Invoke-Expression $node.Extent.Text
$TaskName='Codex-Supplier-V8-Op100-Checkpoint10'; $TaskPath='\'
$script:disableCalls=0; $script:observedName=''; $script:observedPath=''
function Assert-OwnScheduledTask { [pscustomobject]@{State='Ready'} }
function Disable-ScheduledTask {
    param($TaskName,$TaskPath,$ErrorAction)
    $script:disableCalls++; $script:observedName=$TaskName; $script:observedPath=$TaskPath
}
function Get-ScheduledTask {
    param($TaskName,$TaskPath,$ErrorAction)
    [pscustomobject]@{State='Running';Settings=[pscustomobject]@{Enabled=$false}}
}
function Export-ScheduledTask { throw 'fallback must not be used' }
$proof=Disable-OwnScheduledTask
if ($script:disableCalls -ne 1) { exit 2 }
if ($script:observedName -ne 'Codex-Supplier-V8-Op100-Checkpoint10') { exit 3 }
if ($script:observedPath -ne '\') { exit 4 }
if ($proof.definition_enabled -ne $false) { exit 5 }
Write-Output 'TASK_OK'
"""
    completed = _powershell_command(command, environment=environment)
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"TASK_OK" in completed.stdout
