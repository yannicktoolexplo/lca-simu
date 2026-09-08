[CmdletBinding()]
param(
    [string]$Repo = "C:\dev\lca-simu-pr40",
    [string]$Python = "C:\Users\yannick.martz\AppData\Local\Programs\Python\Python311\python.exe",
    [string]$Stage3SupervisionDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_supervision_20260906_v3",
    [string]$ClosureDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_closure_supervision_20260906_v1",
    [string]$ReportJson = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_closure_supervision_20260906_v1\closure_report.json",
    [string]$PowerShellExecutable = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe",
    [string]$TaskName = "Codex-Supplier-V8-Stage3-Closure-V1",
    [string]$TaskPath = "\",
    [ValidateRange(1, 60)]
    [int]$PollSeconds = 60,
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$SchemaVersion = "etudecas.supplier_v8_stage3_closure_wrapper.v1"
$ExpectedTaskName = "Codex-Supplier-V8-Stage3-Closure-V1"
$ExpectedStage3InventorySignature = "d56761c3cdd704ec9d31bb2b452ee5dea25e9cdcf1e87c67d787a09e20b5a442"
$VerifierModule = "etudecas.prototypes.scan_2027_risk_control.verify_supplier_v8_stage3_closure"
$ExpectedSourceSha256 = [ordered]@{
    "etudecas\prototypes\scan_2027_risk_control\verify_supplier_v8_stage3_closure.py" = "004ab109ac4d396cc50501b17b58fc0b64798352e97d08cadb941aff0ce6de1a"
    "etudecas\prototypes\scan_2027_risk_control\run_supplier_v8_v2_to_stage3_v3_chain_task.ps1" = "451e3ab5e7a5f737db6d9375242ca88a179aff65aa2db39bd7ced63c217529b6"
    "etudecas\prototypes\scan_2027_risk_control\launch_supplier_operating_point_full_campaign_v8_resilient.py" = "82c78d47b2fb8e37f028d3568c0697a1c21172df62bf83a30e16ba80655fb3b7"
    "etudecas\prototypes\scan_2027_risk_control\supervise_supplier_operating_point_full_campaign_v8_v2.py" = "2ad3309ca0db131f54998337d663afd9512300fad97fe27b7ec707d31187c254"
}

$script:WakeActive = $false
$script:WakeStartedAtUtc = ""
$script:WakeStoppedAtUtc = ""

if (-not ("Etudecas.Stage3Closure.NativeMethods" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
namespace Etudecas.Stage3Closure {
    public static class NativeMethods {
        [DllImport("kernel32.dll")]
        public static extern UInt32 SetThreadExecutionState(UInt32 executionState);
    }
}
"@ | Out-Null
}

function Get-UtcTimestamp {
    return [DateTimeOffset]::UtcNow.ToString("o")
}

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [IO.Path]::GetFullPath($Path)
}

function Test-SamePath {
    param(
        [Parameter(Mandatory = $true)][string]$Left,
        [Parameter(Mandatory = $true)][string]$Right
    )
    return [string]::Equals(
        (Get-FullPath $Left),
        (Get-FullPath $Right),
        [StringComparison]::OrdinalIgnoreCase
    )
}

function Test-PathOverlap {
    param(
        [Parameter(Mandatory = $true)][string]$Left,
        [Parameter(Mandatory = $true)][string]$Right
    )
    $first = (Get-FullPath $Left).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $second = (Get-FullPath $Right).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $firstPrefix = $first + [IO.Path]::DirectorySeparatorChar
    $secondPrefix = $second + [IO.Path]::DirectorySeparatorChar
    return (
        [string]::Equals($first, $second, [StringComparison]::OrdinalIgnoreCase) -or
        $first.StartsWith($secondPrefix, [StringComparison]::OrdinalIgnoreCase) -or
        $second.StartsWith($firstPrefix, [StringComparison]::OrdinalIgnoreCase)
    )
}

function Get-KeepAwakePayload {
    return [ordered]@{
        requested = $true
        active = $script:WakeActive
        method = "windows_SetThreadExecutionState"
        started_at_utc = $script:WakeStartedAtUtc
        stopped_at_utc = $script:WakeStoppedAtUtc
        coverage = "wait_stage3_and_closure_verification"
    }
}

function Start-ClosureKeepAwake {
    if ($script:WakeActive) {
        throw "Keep-awake is already active."
    }
    $script:WakeStartedAtUtc = Get-UtcTimestamp
    $state = [Convert]::ToUInt32("80000001", 16)
    $result = [Etudecas.Stage3Closure.NativeMethods]::SetThreadExecutionState($state)
    if ($result -eq 0) {
        throw "Windows refused the keep-awake request."
    }
    $script:WakeActive = $true
}

function Stop-ClosureKeepAwake {
    if ($script:WakeActive) {
        $continuous = [Convert]::ToUInt32("80000000", 16)
        [void][Etudecas.Stage3Closure.NativeMethods]::SetThreadExecutionState(
            $continuous
        )
    }
    $script:WakeActive = $false
    $script:WakeStoppedAtUtc = Get-UtcTimestamp
}

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object]$Payload
    )
    $destination = Get-FullPath $Path
    $parent = [IO.Path]::GetDirectoryName($destination)
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temporary = [IO.Path]::Combine(
        $parent,
        "." + [IO.Path]::GetFileName($destination) + ".tmp." +
            $PID + "." + [Guid]::NewGuid().ToString("N")
    )
    $backup = [IO.Path]::Combine(
        $parent,
        "." + [IO.Path]::GetFileName($destination) + ".bak." +
            $PID + "." + [Guid]::NewGuid().ToString("N")
    )
    $json = ($Payload | ConvertTo-Json -Depth 16) + [Environment]::NewLine
    $encoding = [Text.UTF8Encoding]::new($false)
    $bytes = $encoding.GetBytes($json)
    $stream = [IO.File]::Open(
        $temporary,
        [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,
        [IO.FileShare]::None
    )
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    }
    finally {
        $stream.Dispose()
    }
    try {
        if ([IO.File]::Exists($destination)) {
            [IO.File]::Replace($temporary, $destination, $backup, $true)
        }
        else {
            [IO.File]::Move($temporary, $destination)
        }
    }
    finally {
        if ([IO.File]::Exists($temporary)) {
            [IO.File]::Delete($temporary)
        }
        if ([IO.File]::Exists($backup)) {
            [IO.File]::Delete($backup)
        }
    }
}

function Write-ClosureStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][string]$Step,
        [Parameter(Mandatory = $true)][string]$Message,
        [System.Collections.IDictionary]$Details = @{}
    )
    $payload = [ordered]@{
        schema_version = "$SchemaVersion.status.v1"
        status = $Status
        step = $Step
        message = $Message
        updated_at_utc = Get-UtcTimestamp
        no_simulation_engine_started = $true
        task = [ordered]@{
            name = $TaskName
            path = $TaskPath
        }
        stage3_supervision_dir = Get-FullPath $Stage3SupervisionDir
        closure_dir = Get-FullPath $ClosureDir
        report_json = Get-FullPath $ReportJson
        keep_awake = Get-KeepAwakePayload
    }
    foreach ($key in $Details.Keys) {
        $payload[$key] = $Details[$key]
    }
    Write-JsonAtomic -Path ([IO.Path]::Combine(
        (Get-FullPath $ClosureDir),
        "status.json"
    )) -Payload $payload
}

function ConvertTo-WindowsArgument {
    param([AllowEmptyString()][string]$Value)
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') {
        return $Value
    }
    $builder = [Text.StringBuilder]::new()
    [void]$builder.Append('"')
    $backslashes = 0
    foreach ($character in $Value.ToCharArray()) {
        if ([int]$character -eq 0x5c) {
            $backslashes++
            continue
        }
        if ([int]$character -eq 0x22) {
            if ($backslashes -gt 0) {
                [void]$builder.Append((('\') * (2 * $backslashes) -join ""))
            }
            [void]$builder.Append('\"')
            $backslashes = 0
            continue
        }
        if ($backslashes -gt 0) {
            [void]$builder.Append((('\') * $backslashes -join ""))
            $backslashes = 0
        }
        [void]$builder.Append($character)
    }
    if ($backslashes -gt 0) {
        [void]$builder.Append((('\') * (2 * $backslashes) -join ""))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function New-PythonProcessStartInfo {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = Get-FullPath $Python
    $startInfo.WorkingDirectory = Get-FullPath $Repo
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.Arguments = (
        $Arguments | ForEach-Object { ConvertTo-WindowsArgument $_ }
    ) -join " "
    $startInfo.EnvironmentVariables["PYTHONPATH"] = Get-FullPath $Repo
    $startInfo.EnvironmentVariables["PYTHONUTF8"] = "1"
    $startInfo.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8"
    return $startInfo
}

function Invoke-PythonCapture {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $process = [Diagnostics.Process]::new()
    try {
        $process.StartInfo = New-PythonProcessStartInfo -Arguments $Arguments
        if (-not $process.Start()) {
            throw "Unable to start Python."
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        [Threading.Tasks.Task]::WaitAll(
            [Threading.Tasks.Task[]]@($stdoutTask, $stderrTask)
        )
        return [ordered]@{
            exit_code = $process.ExitCode
            stdout = $stdoutTask.Result
            stderr = $stderrTask.Result
        }
    }
    finally {
        $process.Dispose()
    }
}

function Add-LogText {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Text
    )
    $fullPath = Get-FullPath $Path
    $parent = [IO.Path]::GetDirectoryName($fullPath)
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $line = "[" + (Get-UtcTimestamp) + "] " + $Text + [Environment]::NewLine
    $bytes = [Text.Encoding]::UTF8.GetBytes($line)
    $stream = [IO.File]::Open(
        $fullPath,
        [IO.FileMode]::Append,
        [IO.FileAccess]::Write,
        [IO.FileShare]::ReadWrite
    )
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush()
    }
    finally {
        $stream.Dispose()
    }
}

function Invoke-ClosureVerifier {
    $arguments = @(
        "-m",
        $VerifierModule,
        "--supervision-dir", (Get-FullPath $Stage3SupervisionDir),
        "--output-json", (Get-FullPath $ReportJson)
    )
    $result = Invoke-PythonCapture -Arguments $arguments
    Add-LogText -Path ([IO.Path]::Combine(
        (Get-FullPath $ClosureDir),
        "verifier.stdout.log"
    )) -Text (($result.stdout).Trim())
    Add-LogText -Path ([IO.Path]::Combine(
        (Get-FullPath $ClosureDir),
        "verifier.stderr.log"
    )) -Text (($result.stderr).Trim())
    return $result
}

function Get-Stage3Readiness {
    $readinessCode = @'
import json, sys
from pathlib import Path
from etudecas.prototypes.scan_2027_risk_control import supplier_v8_stage3_common as c
from etudecas.prototypes.scan_2027_risk_control import supplier_v8_stage3_pipeline as p
root = Path(sys.argv[1]).resolve()
contract_path = root / p.CONTRACT_NAME
status_path = root / p.STATUS_NAME
if not contract_path.is_file() or not status_path.is_file():
    print(json.dumps({"readiness": "WAIT", "reason": "contract_or_status_absent"}))
    raise SystemExit(0)
contract = c.read_json(contract_path)
c.verify_signature(contract, "contract_signature", "Stage3 V3 readiness contract")
status = c.read_json(status_path)
c.verify_signature(status, "status_signature", "Stage3 V3 readiness status")
ready = (
    contract.get("schema_version") == f"{p.SCHEMA_VERSION}.contract.v1"
    and status.get("schema_version") == f"{p.SCHEMA_VERSION}.status.v1"
    and status.get("contract_signature") == contract.get("contract_signature")
    and status.get("status") == "complete"
    and status.get("step") == "termine"
    and isinstance(status.get("results"), dict)
)
print(json.dumps({"readiness": "READY" if ready else "WAIT", "reason": "signed_final" if ready else "signed_not_final", "contract_signature": contract.get("contract_signature"), "status_signature": status.get("status_signature")}))
'@
    $result = Invoke-PythonCapture -Arguments @(
        "-c", $readinessCode, (Get-FullPath $Stage3SupervisionDir)
    )
    if ($result.exit_code -ne 0) {
        throw "Signed Stage3 readiness validation failed: $($result.stderr)"
    }
    try {
        return ([string]$result.stdout).Trim() | ConvertFrom-Json
    }
    catch {
        throw "Stage3 readiness receipt is not JSON."
    }
}

function Assert-StaticInputs {
    $resolvedRepo = Get-FullPath $Repo
    if (-not [IO.Directory]::Exists($resolvedRepo)) {
        throw "Repository is absent: $resolvedRepo"
    }
    if (-not [IO.File]::Exists((Get-FullPath $Python))) {
        throw "Python is absent: $Python"
    }
    if (-not [IO.File]::Exists((Get-FullPath $PowerShellExecutable))) {
        throw "PowerShell is absent: $PowerShellExecutable"
    }
    if ($TaskName -ne $ExpectedTaskName -or $TaskPath -ne "\") {
        throw "Only the exact closure task identity is allowed."
    }
    $expectedReport = [IO.Path]::Combine(
        (Get-FullPath $ClosureDir),
        "closure_report.json"
    )
    if (-not (Test-SamePath -Left $ReportJson -Right $expectedReport)) {
        throw "ReportJson must be closure_report.json inside ClosureDir."
    }
    $existingRoots = @(
        $resolvedRepo,
        "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2",
        "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_results_20260906_v2",
        "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_lot_replays_20260906_v3",
        "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_physical_qualification_20260906_v3",
        "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_action_replays_20260906_v3",
        "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_nominal_curves_20260906_v3",
        "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_incident_lot_registry_20260906_v3",
        "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_v2_to_stage3_v3_chain_supervision_20260906_v1",
        (Get-FullPath $Stage3SupervisionDir),
        "C:\dev\lca-simu-pr40-validation-artifacts-20260726\OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_V8_STAGE2_20260906_V3.html"
    )
    foreach ($root in $existingRoots) {
        if (Test-PathOverlap -Left $ClosureDir -Right $root) {
            throw "ClosureDir overlaps an existing source or output root: $root"
        }
    }

    $actualHashes = [ordered]@{}
    foreach ($relativePath in $ExpectedSourceSha256.Keys) {
        $path = [IO.Path]::Combine($resolvedRepo, $relativePath)
        if (-not [IO.File]::Exists($path)) {
            throw "Required frozen source is absent: $path"
        }
        $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $ExpectedSourceSha256[$relativePath]) {
            throw "Frozen source hash differs: $relativePath ($actual)"
        }
        $actualHashes[$relativePath] = $actual
    }

    $inventoryCode = "from pathlib import Path; from etudecas.prototypes.scan_2027_risk_control import supplier_v8_stage3_common as c; x=c.build_source_inventory(Path(__import__('sys').argv[1])); print(x['inventory_signature'])"
    $inventoryResult = Invoke-PythonCapture -Arguments @(
        "-c", $inventoryCode, $resolvedRepo
    )
    if ($inventoryResult.exit_code -ne 0) {
        throw "Stage3 source inventory validation failed: $($inventoryResult.stderr)"
    }
    $inventorySignature = ([string]$inventoryResult.stdout).Trim()
    if ($inventorySignature -ne $ExpectedStage3InventorySignature) {
        throw "Stage3 source inventory signature differs: $inventorySignature"
    }
    return [ordered]@{
        stage3_inventory_signature = $inventorySignature
        frozen_source_sha256 = $actualHashes
        verifier_module = $VerifierModule
        no_simulation_engine_command = $true
        poll_seconds = $PollSeconds
    }
}

function Assert-OwnScheduledTask {
    Import-Module ScheduledTasks -ErrorAction Stop
    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop
    $actions = @($task.Actions)
    if ($actions.Count -ne 1) {
        throw "The closure task must have exactly one action."
    }
    $action = $actions[0]
    if (-not (Test-SamePath -Left ([string]$action.Execute) -Right $PowerShellExecutable)) {
        throw "The closure task action uses an unexpected executable."
    }
    $scriptPath = Get-FullPath $PSCommandPath
    $expectedArguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
        $scriptPath + '"'
    if (-not [string]::Equals(
        ([string]$action.Arguments).Trim(),
        $expectedArguments,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "The closure task action is not bound exactly to this wrapper."
    }
    return $task
}

function Disable-OwnScheduledTask {
    [void](Assert-OwnScheduledTask)
    Disable-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop |
        Out-Null
    $after = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop
    $enabledProperty = $after.Settings.PSObject.Properties["Enabled"]
    if ($null -ne $enabledProperty) {
        $enabledText = [string]$enabledProperty.Value
    }
    else {
        [xml]$taskXml = Export-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop
        $enabledText = [string]$taskXml.Task.Settings.Enabled
    }
    if (-not [string]::Equals(
        $enabledText,
        "False",
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "The closure task definition remains enabled."
    }
    return [ordered]@{
        task_name = $TaskName
        task_path = $TaskPath
        definition_enabled = $false
        observed_runtime_state = [string]$after.State
        running_state_accepted = ([string]$after.State -eq "Running")
    }
}

function Validate-ClosureReport {
    if (-not [IO.File]::Exists((Get-FullPath $ReportJson))) {
        throw "The closure report was not published."
    }
    $validationCode = @'
import hashlib, json, sys
from pathlib import Path
from etudecas.prototypes.scan_2027_risk_control import verify_supplier_v8_stage3_closure as v
p = Path(sys.argv[1]).resolve()
x = json.loads(p.read_text(encoding="utf-8-sig"))
signature = str(x.pop("closure_signature", ""))
if x.get("schema_version") != v.SCHEMA_VERSION or signature != v._stable_sha256(x):
    raise SystemExit("invalid closure report signature")
technical = (x.get("technical_verdict") or {}).get("code")
business = (x.get("business_verdict") or {}).get("code")
if technical not in {"CONFORME_TECHNIQUE", "NON_CONFORME_TECHNIQUE"}:
    raise SystemExit("technical verdict was not calculated")
if not isinstance(business, str) or not business:
    raise SystemExit("business verdict is absent")
if Path(str((x.get("source") or {}).get("supervision_dir") or "")).resolve() != Path(sys.argv[2]).resolve():
    raise SystemExit("closure report belongs to another Stage3 supervision")
print(json.dumps({"technical_verdict": technical, "business_verdict": business, "closure_signature": signature, "report_sha256": hashlib.sha256(p.read_bytes()).hexdigest()}))
'@
    $result = Invoke-PythonCapture -Arguments @(
        "-c",
        $validationCode,
        (Get-FullPath $ReportJson),
        (Get-FullPath $Stage3SupervisionDir)
    )
    if ($result.exit_code -ne 0) {
        throw "Closure report revalidation failed: $($result.stderr)"
    }
    try {
        return ([string]$result.stdout).Trim() | ConvertFrom-Json
    }
    catch {
        throw "Closure report validation receipt is not JSON."
    }
}

if ($ValidateOnly) {
    $validation = Assert-StaticInputs
    [ordered]@{
        schema_version = "$SchemaVersion.validation.v1"
        status = "valid"
        mode = "validate_only"
        launch_performed = $false
        simulation_engine_started = $false
        scheduled_task_changed = $false
        filesystem_mutation_performed = $false
        task_name = $TaskName
        task_path = $TaskPath
        expected_task_arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
            (Get-FullPath $PSCommandPath) + '"'
        closure_dir = Get-FullPath $ClosureDir
        report_json = Get-FullPath $ReportJson
        planned_steps = @(
            "poll_only_signed_stage3_contract_and_status",
            "run_closure_verifier_once",
            "revalidate_signed_report",
            "disable_exact_closure_task_after_technical_verdict"
        )
        validation = $validation
    } | ConvertTo-Json -Depth 16
    exit 0
}

# Runtime starts only from an externally created scheduled task. This wrapper
# never registers a task and never invokes a simulation or campaign runner.
[void](Assert-OwnScheduledTask)
$mutexName = "Local\Codex-Supplier-V8-Stage3-Closure-V1"
$createdNew = $false
$mutex = [Threading.Mutex]::new($true, $mutexName, [ref]$createdNew)
if (-not $createdNew) {
    $mutex.Dispose()
    throw "Another closure wrapper instance already owns the mutex."
}

$completed = $false
$failure = $null
try {
    Start-ClosureKeepAwake
    $startupValidation = Assert-StaticInputs
    Write-ClosureStatus -Status "waiting_stage3" -Step "readiness" -Message (
        "Waiting for the signed final Stage3 V3 status. No downstream output " +
        "is read before the verifier accepts final readiness."
    ) -Details @{
        source_validation = $startupValidation
        report_published = $false
        scheduled_task_disabled = $false
    }

    $readiness = $null
    while ($true) {
        $readiness = Get-Stage3Readiness
        if ([string]$readiness.readiness -eq "READY") {
            break
        }
        Write-ClosureStatus -Status "waiting_stage3" -Step "readiness" -Message (
            "Stage3 V3 is not final yet; only its minimal signed contract and status " +
            "were inspected."
        ) -Details @{
            readiness = $readiness
            report_published = $false
            scheduled_task_disabled = $false
        }
        Start-Sleep -Seconds $PollSeconds
    }

    $preAuditValidation = Assert-StaticInputs
    Write-ClosureStatus -Status "auditing" -Step "closure" -Message (
        "Stage3 V3 is signed and final; running the closure verifier once."
    ) -Details @{
        readiness = $readiness
        report_published = $false
        source_validation = $preAuditValidation
        scheduled_task_disabled = $false
    }
    $verifierResult = Invoke-ClosureVerifier
    if ($verifierResult.exit_code -notin @(0, 2, 3)) {
        throw "Closure verifier failed before publishing a valid verdict: $($verifierResult.exit_code)"
    }
    $reportHash = (Get-FileHash -LiteralPath (Get-FullPath $ReportJson) -Algorithm SHA256).Hash.ToLowerInvariant()
    $reportValidation = Validate-ClosureReport
    if ([string]$reportValidation.report_sha256 -ne $reportHash) {
        throw "The report validation receipt has a different SHA256."
    }

    Write-ClosureStatus -Status "report_validated" -Step "task_disable" -Message (
        "Technical and business verdicts are present and the immutable report was revalidated."
    ) -Details @{
        technical_verdict = [string]$reportValidation.technical_verdict
        business_verdict = [string]$reportValidation.business_verdict
        closure_signature = [string]$reportValidation.closure_signature
        report_sha256 = [string]$reportValidation.report_sha256
        verifier_exit_code = $verifierResult.exit_code
        report_published = $true
        report_revalidated = $true
        scheduled_task_disabled = $false
    }
    $disableProof = Disable-OwnScheduledTask
    Write-ClosureStatus -Status "complete" -Step "complete" -Message (
        "Closure report published and revalidated; the exact closure task is disabled."
    ) -Details @{
        technical_verdict = [string]$reportValidation.technical_verdict
        business_verdict = [string]$reportValidation.business_verdict
        closure_signature = [string]$reportValidation.closure_signature
        report_sha256 = [string]$reportValidation.report_sha256
        report_published = $true
        report_revalidated = $true
        scheduled_task_disabled = $true
        task_disable_proof = $disableProof
    }
    $completed = $true
}
catch {
    $failure = $_
    try {
        Write-ClosureStatus -Status "failed_resumable" -Step "failed" -Message (
            [string]$_.Exception.Message
        ) -Details @{
            report_published = [IO.File]::Exists((Get-FullPath $ReportJson))
            scheduled_task_disabled = $false
            error_type = $_.Exception.GetType().FullName
        }
    }
    catch {
        # Preserve the original failure; the exact task remains enabled.
    }
}
finally {
    Stop-ClosureKeepAwake
    if ($null -ne $mutex) {
        try { $mutex.ReleaseMutex() } catch { }
        $mutex.Dispose()
    }
}

if (-not $completed) {
    [Console]::Error.WriteLine([string]$failure.Exception.Message)
    exit 1
}
exit 0
