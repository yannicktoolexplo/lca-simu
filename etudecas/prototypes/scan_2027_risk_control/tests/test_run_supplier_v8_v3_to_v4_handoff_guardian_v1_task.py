from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / (
    "etudecas/prototypes/scan_2027_risk_control/"
    "run_supplier_v8_v3_to_v4_handoff_guardian_v1_task.ps1"
)
V3 = SCRIPT.with_name("run_supplier_v8_v2_to_stage3_v3_chain_task.ps1")
V4 = SCRIPT.with_name("run_supplier_v8_v2_to_stage3_v4_chain_task.ps1")
GO = (
    Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
    / "supplier_v8_stage3_go_20260906_v4.json"
)
V3_SHA256 = "451e3ab5e7a5f737db6d9375242ca88a179aff65aa2db39bd7ced63c217529b6"
V4_SHA256 = "b322e47b8820e7cc714ab9436555bc4607b193e11c397a6cf7dfbc76cd6ef642"
GO_SHA256 = "255e5bb6d8f6be3473ab4622ea0d5faa9ff1529b65d497f405dc4975c8332a93"


def _powershell() -> str:
    return str(
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )


def _run_ps(
    command: str, environment: dict[str, str]
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=60,
    )


def test_guardian_parses_and_has_no_direct_engine_or_task_creation() -> None:
    environment = dict(os.environ)
    environment["GUARDIAN_SCRIPT"] = str(SCRIPT)
    command = r"""
$tokens=$null; $errors=$null
[System.Management.Automation.Language.Parser]::ParseFile(
    $env:GUARDIAN_SCRIPT,[ref]$tokens,[ref]$errors) | Out-Null
if($errors.Count){$errors|%{[Console]::Error.WriteLine($_.Message)};exit 1}
Write-Output 'PARSE_OK'
"""
    completed = _run_ps(command, environment)
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"PARSE_OK" in completed.stdout

    source = SCRIPT.read_text(encoding="utf-8")
    assert '$GuardianTaskName = "Codex-Supplier-V8-V3-To-V4-Guardian-V1"' in source
    assert '$TargetTaskName = "Codex-Supplier-V8-V2-To-Stage3-V3"' in source
    assert "$LegacyWrapperPid = 26160" in source
    assert "$LegacySupervisorPid = 34588" in source
    assert source.count("Start-ScheduledTask -TaskName $TargetTaskName") == 1
    for forbidden in (
        "Register-ScheduledTask",
        "Stop-ScheduledTask",
        "Start-Process",
        "Stop-Process",
        "Diagnostics.Process",
    ):
        assert forbidden not in source


def test_guardian_binds_the_three_frozen_artifacts() -> None:
    assert hashlib.sha256(V3.read_bytes()).hexdigest() == V3_SHA256
    assert hashlib.sha256(V4.read_bytes()).hexdigest() == V4_SHA256
    assert hashlib.sha256(GO.read_bytes()).hexdigest() == GO_SHA256
    go = json.loads(GO.read_text(encoding="utf-8"))
    assert go["decision"] == "GO_STAGE3_V4"
    assert go["chain_wrapper_sha256"] == V4_SHA256
    assert go["superseded_chain_wrapper_sha256"] == V3_SHA256
    assert go["change_scope"] == "atomic_status_write_compatibility_only"


def test_atomic_status_and_at_most_once_marker_in_powershell_5(
    tmp_path: Path,
) -> None:
    environment = dict(os.environ)
    environment["GUARDIAN_SCRIPT"] = str(SCRIPT)
    environment["GUARDIAN_STATUS"] = str(tmp_path / "status.json")
    environment["GUARDIAN_ONCE"] = str(tmp_path / "start_once.json")
    command = r"""
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile(
    $env:GUARDIAN_SCRIPT,[ref]$tokens,[ref]$errors)
foreach($name in @('Get-FullPath','Write-JsonAtomic','Write-JsonCreateNewAtomic')){
    $node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
    Invoke-Expression $node.Extent.Text
}
Write-JsonAtomic -Path $env:GUARDIAN_STATUS -Payload ([ordered]@{sequence=1})
Write-JsonAtomic -Path $env:GUARDIAN_STATUS -Payload ([ordered]@{sequence=2})
Write-JsonCreateNewAtomic -Path $env:GUARDIAN_ONCE -Payload ([ordered]@{once=1})
$refused=$false
try { Write-JsonCreateNewAtomic -Path $env:GUARDIAN_ONCE -Payload ([ordered]@{once=2}) }
catch { $refused=$true }
if(-not $refused){exit 11}
if((Get-Content -Raw $env:GUARDIAN_STATUS|ConvertFrom-Json).sequence -ne 2){exit 12}
if((Get-Content -Raw $env:GUARDIAN_ONCE|ConvertFrom-Json).once -ne 1){exit 13}
if(@(Get-ChildItem -Force $env:TMP|?{$_.Name -like '*.tmp.*' -or $_.Name -like '*.bak.*'}).Count){exit 14}
Write-Output 'ATOMIC_ONCE_OK'
"""
    environment["TMP"] = str(tmp_path)
    completed = _run_ps(command, environment)
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"ATOMIC_ONCE_OK" in completed.stdout


def test_process_identity_and_handoff_state_machine_are_fail_closed() -> None:
    environment = dict(os.environ)
    environment["GUARDIAN_SCRIPT"] = str(SCRIPT)
    command = r"""
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile(
    $env:GUARDIAN_SCRIPT,[ref]$tokens,[ref]$errors)
foreach($name in @(
    'Get-FullPath','Test-SamePath','Normalize-CommandLine','Assert-ExactCommandLine',
    'Resolve-LegacyProcessObservation','Resolve-OldOwnerProcessObservation',
    'Resolve-V4ProcessObservation','Assert-V4HandoffCorrelation','Get-HandoffDecision'
)){
    $node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
    Invoke-Expression $node.Extent.Text
}
$LegacyWrapperPid=26160; $LegacySupervisorPid=34588
$ExpectedLegacyWrapperCommandLine='powershell.exe -File v3.ps1'
$ExpectedLegacySupervisorCommandLine='python.exe -m supervisor'
$ExpectedPowerShellExecutable='C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$ExpectedSupervisorExecutable='C:\Python\python.exe'
$ExpectedLegacyWrapperCreatedUtc='2026-09-06T11:02:42.5987970Z'
$ExpectedLegacySupervisorCreatedUtc='2026-09-06T11:03:07.0281980Z'
$Repo='C:\repo'; $V4RelativePath='v4.ps1'; $CampaignRoot='C:\campaign'
$ExpectedTargetV4ProcessCommandLine='powershell.exe -File C:\repo\v4.ps1'
$legacy=Resolve-LegacyProcessObservation -ProcessRecords @(
    [pscustomobject]@{ProcessId=26160;ParentProcessId=1;Name='powershell.exe';ExecutablePath=$ExpectedPowerShellExecutable;CreationDate=[datetime]'2026-09-06T11:02:42.5987970Z';CommandLine='powershell.exe   -File v3.ps1'},
    [pscustomobject]@{ProcessId=34588;ParentProcessId=26160;Name='python.exe';ExecutablePath=$ExpectedSupervisorExecutable;CreationDate=[datetime]'2026-09-06T11:03:07.0281980Z';CommandLine='python.exe -m supervisor'}
)
if(-not $legacy.blocking){exit 11}
$mismatch=$false
try {
    Resolve-LegacyProcessObservation -ProcessRecords @(
        [pscustomobject]@{ProcessId=26160;ParentProcessId=1;Name='powershell.exe';ExecutablePath=$ExpectedPowerShellExecutable;CreationDate=[datetime]'2026-09-06T11:02:42.5987970Z';CommandLine='powershell.exe -File other.ps1'}
    ) | Out-Null
}
catch {$mismatch=$true}
if(-not $mismatch){exit 12}
$v4=Resolve-V4ProcessObservation -ProcessRecords @(
    [pscustomobject]@{ProcessId=900;Name='powershell.exe';ExecutablePath=$ExpectedPowerShellExecutable;CreationDate=[datetime]'2026-09-06T12:00:00Z';CommandLine='powershell.exe -File C:\repo\v4.ps1'}
)
if(-not $v4.present -or $v4.process_id -ne 900){exit 13}
$wrongExecutable=$false
try {
    Resolve-V4ProcessObservation -ProcessRecords @(
        [pscustomobject]@{ProcessId=901;Name='powershell.exe';ExecutablePath='C:\bad\powershell.exe';CreationDate=[datetime]'2026-09-06T12:00:00Z';CommandLine='powershell.exe -File C:\repo\v4.ps1'}
    ) | Out-Null
}
catch {$wrongExecutable=$true}
if(-not $wrongExecutable){exit 14}
$owners=Resolve-OldOwnerProcessObservation -ProcessRecords @(
    [pscustomobject]@{ProcessId=800;ParentProcessId=1;Name='python.exe';ExecutablePath='C:\Python\python.exe';CreationDate=[datetime]'2026-09-06T11:00:00Z';CommandLine='python.exe --output C:\campaign\shard'}
) -CutoffUtc ([DateTimeOffset]'2026-09-06T12:00:00Z')
if(-not $owners.blocking -or $owners.count -ne 1){exit 15}
$targetEvidence=[ordered]@{state='Running';last_run_time_utc='2026-09-06T12:00:00Z'}
$v4Evidence=[ordered]@{present=$true;created_at_utc='2026-09-06T12:00:01Z'}
$marker=[pscustomobject]@{created_at_utc='2026-09-06T11:59:59Z';target_last_run_time_before_start_utc='2026-09-06T11:02:42Z'}
Assert-V4HandoffCorrelation -TargetTask $targetEvidence -V4Process $v4Evidence -StartMarker $marker | Out-Null
$oldV4=$false
try {
    $v4Evidence.created_at_utc='2026-09-06T11:59:00Z'
    Assert-V4HandoffCorrelation -TargetTask $targetEvidence -V4Process $v4Evidence -StartMarker $marker | Out-Null
}
catch {$oldV4=$true}
if(-not $oldV4){exit 16}
if((Get-HandoffDecision $true 'Running' 0 $false $false $false) -ne 'wait_legacy'){exit 17}
if((Get-HandoffDecision $false 'Ready' 0 $false $false $false) -ne 'wait_quiescence'){exit 18}
if((Get-HandoffDecision $false 'Ready' 0 $false $false $true) -ne 'start_once'){exit 19}
if((Get-HandoffDecision $false 'Running' 1 $false $false $true) -ne 'handoff_validated'){exit 20}
if((Get-HandoffDecision $false 'Ready' 0 $true $false $true) -ne 'wait_v4_confirmation'){exit 21}
$expired=$false
try { Get-HandoffDecision $false 'Ready' 0 $true $true $true | Out-Null }
catch {$expired=$true}
if(-not $expired){exit 22}
Write-Output 'STATE_MACHINE_OK'
"""
    completed = _run_ps(command, environment)
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"STATE_MACHINE_OK" in completed.stdout


def test_validate_only_is_strict_and_does_not_mutate(tmp_path: Path) -> None:
    supervision = tmp_path / "must-not-exist"
    fixture = tmp_path / "observations.json"
    fixture.write_text(
        json.dumps(
            {
                "processes": [],
                "target_task": {
                    "State": "Ready",
                    "Actions": [
                        {
                            "Execute": _powershell(),
                            "Arguments": (
                                "-NoProfile -NonInteractive -ExecutionPolicy Bypass "
                                f'-File "{V4}"'
                            ),
                            "WorkingDirectory": str(REPO),
                        }
                    ],
                    "Settings": {"Enabled": True, "MultipleInstances": "IgnoreNew"},
                },
                "target_task_info": {"LastRunTime": "2026-09-06T11:02:42Z"},
                "guardian_task": {
                    "State": "Running",
                    "Actions": [
                        {
                            "Execute": _powershell(),
                            "Arguments": (
                                "-NoProfile -NonInteractive -ExecutionPolicy Bypass "
                                f'-File "{SCRIPT}"'
                            ),
                            "WorkingDirectory": str(REPO),
                        }
                    ],
                    "Settings": {"Enabled": True, "MultipleInstances": "IgnoreNew"},
                },
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
            "-Repo",
            str(REPO),
            "-SupervisionDir",
            str(supervision),
            "-ValidationFixtureJson",
            str(fixture),
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        timeout=60,
    )
    assert completed.returncode == 0, (completed.stdout + completed.stderr).decode(
        errors="replace"
    )
    payload = json.loads(completed.stdout.decode("utf-8-sig"))
    assert payload["status"] == "valid"
    assert payload["mode"] == "validate_only"
    assert payload["planned_decision"] == "wait_quiescence"
    assert payload["launch_performed"] is False
    assert payload["simulation_engine_started"] is False
    assert payload["scheduled_task_changed"] is False
    assert payload["filesystem_mutation_performed"] is False
    assert payload["validation_fixture_used"] is True
    assert not supervision.exists()


def test_start_is_once_and_only_guardian_can_be_disabled() -> None:
    environment = dict(os.environ)
    environment["GUARDIAN_SCRIPT"] = str(SCRIPT)
    command = r"""
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile(
    $env:GUARDIAN_SCRIPT,[ref]$tokens,[ref]$errors)
foreach($name in @('Invoke-TargetTaskStartOnce','Disable-OwnGuardianScheduledTask')){
    $node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
    Invoke-Expression $node.Extent.Text
}
$TargetTaskName='target-v4'; $GuardianTaskName='guardian'; $TaskPath='\'
$script:TargetStartCalled=$false; $script:startCalls=0; $script:disableCalls=0
function Start-ScheduledTask { param($TaskName,$TaskPath,$ErrorAction); if($TaskName -ne 'target-v4'){exit 11}; $script:startCalls++ }
function Assert-OwnGuardianScheduledTask { return [pscustomobject]@{State='Running'} }
function Disable-ScheduledTask { param($TaskName,$TaskPath,$ErrorAction); if($TaskName -ne 'guardian'){exit 12}; $script:disableCalls++ }
function Get-ScheduledTask { return [pscustomobject]@{State='Running';Settings=[pscustomobject]@{Enabled=$false}} }
function Get-TaskEnabled { return $false }
Invoke-TargetTaskStartOnce | Out-Null
$secondRefused=$false
try { Invoke-TargetTaskStartOnce | Out-Null } catch {$secondRefused=$true}
if($script:startCalls -ne 1 -or -not $secondRefused){exit 13}
$proof=Disable-OwnGuardianScheduledTask
if($script:disableCalls -ne 1 -or $proof.name -ne 'guardian'){exit 14}
Write-Output 'TASK_GUARDS_OK'
"""
    completed = _run_ps(command, environment)
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"TASK_GUARDS_OK" in completed.stdout
