[CmdletBinding()]
param(
    [string]$Repo = "C:\dev\lca-simu-pr40",
    [string]$Python = "C:\Users\yannick.martz\AppData\Local\Programs\Python\Python311\python.exe",
    [string]$Stage3SupervisionDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_supervision_20260906_v3",
    [string]$ClosureReport = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_closure_supervision_20260906_v1\closure_report.json",
    [string]$FocusRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_post_stage3_focus_338929_20260906_v1",
    [string]$DeliveryRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_post_stage3_delivery_20260906_v4",
    [string]$SupervisionDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_post_stage3_delivery_supervision_20260906_v1",
    [string]$PowerShellExecutable = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe",
    [string]$TaskName = "Codex-Supplier-V8-Post-Stage3-Final-V4",
    [string]$TaskPath = "\",
    [ValidateRange(1, 60)]
    [int]$PollSeconds = 60,
    [ValidateRange(1, 720)]
    [double]$MaxWaitHours = 240,
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$SchemaVersion = "etudecas.supplier_v8_post_stage3_final_v4_wrapper.v1"
$ExpectedTaskName = "Codex-Supplier-V8-Post-Stage3-Final-V4"
$FocusModule = "etudecas.prototypes.scan_2027_risk_control.supplier_v8_post_stage3_focus_338929"
$DeliveryModule = "etudecas.prototypes.scan_2027_risk_control.supplier_v8_post_stage3_delivery_v4"
$MaxFocusArms = 4

# BEGIN POST_STAGE3_FROZEN_HASHES
# Update only this small block after an independently reviewed source correction.
$ExpectedSourceSha256 = [ordered]@{
    "etudecas\prototypes\scan_2027_risk_control\supplier_v8_post_stage3_focus_338929.py" = "fc97dfa4c4c06d82594efb91767d0a6d2dd7f23b23d4e2ce0ca4c56d5b11cabe"
    "etudecas\prototypes\scan_2027_risk_control\supplier_v8_post_stage3_delivery_v4.py" = "8d39815f0ed90192b355bd3c15ef10245d35739b22a12303f5e83cba1530f9d2"
    "etudecas\prototypes\scan_2027_risk_control\verify_supplier_v8_stage3_closure.py" = "004ab109ac4d396cc50501b17b58fc0b64798352e97d08cadb941aff0ce6de1a"
}
# END POST_STAGE3_FROZEN_HASHES

$script:WakeActive = $false
$script:WakeStartedAtUtc = ""
$script:WakeStoppedAtUtc = ""

function Get-UtcTimestamp {
    return [DateTimeOffset]::UtcNow.ToString("o")
}

function Get-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [IO.Path]::GetFullPath($Path)
}

function Open-CrossSessionLock {
    $directory = Get-FullPath $SupervisionDir
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $path = [IO.Path]::Combine($directory, ".post_stage3_final_v4.lock")
    try {
        return [IO.File]::Open(
            $path,
            [IO.FileMode]::OpenOrCreate,
            [IO.FileAccess]::ReadWrite,
            [IO.FileShare]::None
        )
    }
    catch {
        throw "Une autre instance apres-Stage3 detient deja le verrou inter-session."
    }
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
    $first = (Get-FullPath $Left).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    $second = (Get-FullPath $Right).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    $separator = [IO.Path]::DirectorySeparatorChar
    return (
        [string]::Equals($first, $second, [StringComparison]::OrdinalIgnoreCase) -or
        $first.StartsWith($second + $separator, [StringComparison]::OrdinalIgnoreCase) -or
        $second.StartsWith($first + $separator, [StringComparison]::OrdinalIgnoreCase)
    )
}

function Get-KeepAwakePayload {
    return [ordered]@{
        requested = $true
        active = $script:WakeActive
        method = "windows_SetThreadExecutionState"
        started_at_utc = $script:WakeStartedAtUtc
        stopped_at_utc = $script:WakeStoppedAtUtc
        coverage = "closure_wait_focus_338929_and_final_delivery_v4"
    }
}

function Start-PostStage3KeepAwake {
    if ($script:WakeActive) {
        throw "Le maintien en eveil de l'apres-Stage3 est deja actif."
    }
    $script:WakeStartedAtUtc = Get-UtcTimestamp
    $state = [Convert]::ToUInt32("80000001", 16)
    $result = [Etudecas.PostStage3FinalV4.NativeMethods]::SetThreadExecutionState(
        $state
    )
    if ($result -eq 0) {
        throw "Windows a refuse le maintien en eveil de l'apres-Stage3."
    }
    $script:WakeActive = $true
}

function Stop-PostStage3KeepAwake {
    if ($script:WakeActive) {
        $continuous = [Convert]::ToUInt32("80000000", 16)
        [void][Etudecas.PostStage3FinalV4.NativeMethods]::SetThreadExecutionState(
            $continuous
        )
    }
    $script:WakeActive = $false
    $script:WakeStoppedAtUtc = Get-UtcTimestamp
}

function Write-BytesAtomic {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][byte[]]$Bytes
    )
    $destination = Get-FullPath $Path
    $parent = [IO.Path]::GetDirectoryName($destination)
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $leaf = [IO.Path]::GetFileName($destination)
    $temporary = [IO.Path]::Combine(
        $parent,
        "." + $leaf + ".tmp." + $PID + "." + [Guid]::NewGuid().ToString("N")
    )
    $backup = [IO.Path]::Combine(
        $parent,
        "." + $leaf + ".bak." + $PID + "." + [Guid]::NewGuid().ToString("N")
    )
    $stream = [IO.File]::Open(
        $temporary,
        [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,
        [IO.FileShare]::None
    )
    try {
        $stream.Write($Bytes, 0, $Bytes.Length)
        $stream.Flush($true)
    }
    finally {
        $stream.Dispose()
    }
    try {
        for ($attempt = 0; $attempt -lt 12; $attempt++) {
            try {
                if ([IO.File]::Exists($destination)) {
                    [IO.File]::Replace($temporary, $destination, $backup, $true)
                }
                else {
                    [IO.File]::Move($temporary, $destination)
                }
                return
            }
            catch [UnauthorizedAccessException] {
                if ($attempt -eq 11) { throw }
            }
            catch [IO.IOException] {
                if ($attempt -eq 11) { throw }
            }
            Start-Sleep -Milliseconds ([int][Math]::Min(
                1000,
                50 * [Math]::Pow(2, $attempt)
            ))
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

function Write-TextAtomic {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [AllowEmptyString()][Parameter(Mandatory = $true)][string]$Text
    )
    $encoding = [Text.UTF8Encoding]::new($false)
    Write-BytesAtomic -Path $Path -Bytes $encoding.GetBytes($Text)
}

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object]$Payload
    )
    $json = ($Payload | ConvertTo-Json -Depth 20) + [Environment]::NewLine
    Write-TextAtomic -Path $Path -Text $json
}

function Write-PostStage3Status {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][string]$Step,
        [Parameter(Mandatory = $true)][string]$Message,
        [System.Collections.IDictionary]$Details = @{}
    )
    $selfDisablePending = ($Status -ne "complete")
    if (
        $Status -eq "complete" -and
        $Details.Contains("scheduled_task_disabled") -and
        $Details["scheduled_task_disabled"] -ne $true
    ) {
        $selfDisablePending = $true
    }
    $payload = [ordered]@{
        schema_version = "$SchemaVersion.status.v1"
        status = $Status
        step = $Step
        message_fr = $Message
        updated_at_utc = Get-UtcTimestamp
        task = [ordered]@{
            name = $TaskName
            path = $TaskPath
            self_disable_pending = $selfDisablePending
        }
        stage3_supervision_dir = Get-FullPath $Stage3SupervisionDir
        closure_report = Get-FullPath $ClosureReport
        focus_root = Get-FullPath $FocusRoot
        delivery_root = Get-FullPath $DeliveryRoot
        supervision_dir = Get-FullPath $SupervisionDir
        focus_execution = [ordered]@{
            sequential = $true
            maximum_arms = $MaxFocusArms
            automatic_control = $false
        }
        keep_awake = Get-KeepAwakePayload
    }
    foreach ($key in $Details.Keys) {
        $payload[$key] = $Details[$key]
    }
    Write-JsonAtomic -Path ([IO.Path]::Combine(
        (Get-FullPath $SupervisionDir),
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
    $utf8 = [Text.UTF8Encoding]::new($false)
    $startInfo.StandardOutputEncoding = $utf8
    $startInfo.StandardErrorEncoding = $utf8
    $startInfo.Arguments = (
        $Arguments | ForEach-Object { ConvertTo-WindowsArgument $_ }
    ) -join " "
    $startInfo.EnvironmentVariables["PYTHONPATH"] = Get-FullPath $Repo
    $startInfo.EnvironmentVariables["PYTHONUTF8"] = "1"
    $startInfo.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8"
    $startInfo.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"] = "1"
    return $startInfo
}

function Invoke-PythonCapture {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $process = [Diagnostics.Process]::new()
    try {
        $process.StartInfo = New-PythonProcessStartInfo -Arguments $Arguments
        if (-not $process.Start()) {
            throw "Impossible de demarrer Python."
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

function Invoke-LoggedPythonStep {
    param(
        [Parameter(Mandatory = $true)][string]$Step,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$ParseJson
    )
    $result = Invoke-PythonCapture -Arguments $Arguments
    $directory = Get-FullPath $SupervisionDir
    $header = "[" + (Get-UtcTimestamp) + "] " + $Step + " " + (
        ($Arguments | ForEach-Object { ConvertTo-WindowsArgument $_ }) -join " "
    ) + [Environment]::NewLine
    $stdoutPath = [IO.Path]::Combine($directory, "$Step.stdout.log")
    $stderrPath = [IO.Path]::Combine($directory, "$Step.stderr.log")
    Write-TextAtomic -Path $stdoutPath -Text ($header + [string]$result.stdout)
    Write-TextAtomic -Path $stderrPath -Text ($header + [string]$result.stderr)
    if ($result.exit_code -ne 0) {
        throw "L'etape $Step a echoue (code $($result.exit_code)); voir les journaux atomiques."
    }
    $payload = $null
    if ($ParseJson) {
        try {
            $payload = ([string]$result.stdout).Trim() | ConvertFrom-Json
        }
        catch {
            throw "La sortie de l'etape $Step n'est pas un recu JSON valide."
        }
    }
    return [ordered]@{
        exit_code = $result.exit_code
        stdout_log = $stdoutPath
        stderr_log = $stderrPath
        stdout_sha256 = (Get-FileHash -LiteralPath $stdoutPath -Algorithm SHA256).Hash.ToLowerInvariant()
        stderr_sha256 = (Get-FileHash -LiteralPath $stderrPath -Algorithm SHA256).Hash.ToLowerInvariant()
        payload = $payload
    }
}

function Assert-StaticInputs {
    $resolvedRepo = Get-FullPath $Repo
    if (-not [IO.Directory]::Exists($resolvedRepo)) {
        throw "Depot absent : $resolvedRepo"
    }
    if (-not [IO.File]::Exists((Get-FullPath $Python))) {
        throw "Interpreteur Python absent : $Python"
    }
    if (-not [IO.File]::Exists((Get-FullPath $PowerShellExecutable))) {
        throw "Executable PowerShell absent : $PowerShellExecutable"
    }
    if ($TaskName -ne $ExpectedTaskName -or $TaskPath -ne "\") {
        throw "Seule l'identite exacte de la tache apres-Stage3 est autorisee."
    }
    if ($MaxFocusArms -ne 4) {
        throw "La borne de securite du focus doit rester fixee a quatre bras."
    }
    if ([IO.Path]::GetFileName((Get-FullPath $ClosureReport)) -ne "closure_report.json") {
        throw "ClosureReport doit designer exactement un fichier closure_report.json."
    }

    $mutableRoots = [ordered]@{
        FocusRoot = Get-FullPath $FocusRoot
        DeliveryRoot = Get-FullPath $DeliveryRoot
        SupervisionDir = Get-FullPath $SupervisionDir
    }
    $mutableNames = @($mutableRoots.Keys)
    for ($left = 0; $left -lt $mutableNames.Count; $left++) {
        for ($right = $left + 1; $right -lt $mutableNames.Count; $right++) {
            $leftName = $mutableNames[$left]
            $rightName = $mutableNames[$right]
            if (Test-PathOverlap -Left $mutableRoots[$leftName] -Right $mutableRoots[$rightName]) {
                throw "$leftName et $rightName ne doivent pas se chevaucher."
            }
        }
    }
    $protectedPaths = [ordered]@{
        Repo = $resolvedRepo
        Stage3SupervisionDir = Get-FullPath $Stage3SupervisionDir
        ClosureReport = Get-FullPath $ClosureReport
        CampaignRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
        CampaignResults = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_results_20260906_v2"
        V7Plan = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_plan_20260905_v7"
        V7Run = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_run_20260905_v7"
        V7Trace = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v7_campaign_trace_package_20260905_v1"
        Observed2025 = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\observed_2025_supply_bilan_20260901_v1"
        Stage3Lots = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_lot_replays_20260906_v3"
        Stage3Qualification = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_physical_qualification_20260906_v3"
        Stage3Actions = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_action_replays_20260906_v3"
        Stage3Curves = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_nominal_curves_20260906_v3"
        Stage3Registry = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_incident_lot_registry_20260906_v3"
        Stage3Html = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_V8_STAGE2_20260906_V3.html"
        PriorMeetingDemo = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\DEMONSTRATION_REUNION_1500_20260904_v1\OUVRIR_DEMONSTRATION_RESILIENCE_SCAN.html"
        PriorNetworkMap = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\industrial_supply_preliminary_consolidated_20260904_v4\assets\carte_reseau_existante_hors_ligne.html"
    }
    foreach ($mutable in $mutableRoots.GetEnumerator()) {
        foreach ($protected in $protectedPaths.GetEnumerator()) {
            if (Test-PathOverlap -Left ([string]$mutable.Value) -Right ([string]$protected.Value)) {
                throw "$($mutable.Key) chevauche la preuve protegee $($protected.Key)."
            }
        }
    }

    $actualHashes = [ordered]@{}
    foreach ($relativePath in $ExpectedSourceSha256.Keys) {
        $sourcePath = [IO.Path]::Combine($resolvedRepo, $relativePath)
        if (-not [IO.File]::Exists($sourcePath)) {
            throw "Source figee absente : $sourcePath"
        }
        $actual = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $ExpectedSourceSha256[$relativePath]) {
            throw "Hash de source figee different : $relativePath ($actual)"
        }
        $actualHashes[$relativePath] = $actual
    }
    return [ordered]@{
        frozen_source_sha256 = $actualHashes
        focus_module = $FocusModule
        delivery_module = $DeliveryModule
        focus_execution_sequential = $true
        maximum_focus_arms = $MaxFocusArms
        automatic_control = $false
        output_policy = "new_or_identical_no_delete_no_overwrite"
    }
}

function Get-FocusRecoveryAssessment {
    param(
        [string]$FailedStep = "",
        [bool]$FocusValidationSucceeded = $false
    )
    try {
        $root = Get-FullPath $FocusRoot
        if (-not [IO.Directory]::Exists($root)) {
            return [ordered]@{
                state = "focus_absent_retry_plan"
                manual_intervention_required = $false
                automatic_deletion_allowed = $false
            }
        }
        $plan = [IO.File]::Exists([IO.Path]::Combine($root, "focus_plan.json"))
        $receipt = [IO.File]::Exists([IO.Path]::Combine($root, "focus_run_receipt.json"))
        $validation = [IO.File]::Exists([IO.Path]::Combine($root, "focus_validation.json"))
        $runsRoot = [IO.Path]::Combine($root, "runs")
        $armDirectories = @()
        if ([IO.Directory]::Exists($runsRoot)) {
            $armDirectories = @(
                [IO.Directory]::GetDirectories(
                    $runsRoot,
                    "baseline",
                    [IO.SearchOption]::AllDirectories
                )
            ) + @(
                [IO.Directory]::GetDirectories(
                    $runsRoot,
                    "incident",
                    [IO.SearchOption]::AllDirectories
                )
            )
        }
        $rootHasEntries = @([IO.Directory]::EnumerateFileSystemEntries($root)).Count -gt 0
        $state = "focus_plan_only_retry_run"
        $manual = $false
        if (-not $plan -and $rootHasEntries) {
            $state = "focus_root_nonempty_without_plan_manual_intervention"
            $manual = $true
        }
        elseif ($validation -and (-not $receipt -or -not $plan)) {
            $state = "focus_validation_without_complete_chain_manual_intervention"
            $manual = $true
        }
        elseif ($receipt -and -not $plan) {
            $state = "focus_receipt_without_plan_manual_intervention"
            $manual = $true
        }
        elseif ($armDirectories.Count -gt 0 -and -not $receipt) {
            $state = "partial_focus_arm_without_receipt_manual_intervention"
            $manual = $true
        }
        elseif ($validation -and $receipt -and $plan) {
            if (
                $FailedStep -in @("05_focus_finalize", "06_focus_validate") -and
                -not $FocusValidationSucceeded
            ) {
                $state = "focus_validation_present_but_rejected_manual_intervention"
                $manual = $true
            }
            else {
                $state = "focus_complete_files_present_revalidate"
            }
        }
        elseif ($receipt -and $plan) {
            $state = "focus_receipt_present_retry_finalize"
        }
        elseif ($plan) {
            $state = "focus_plan_only_retry_run"
        }
        else {
            $state = "focus_empty_retry_plan"
        }
        return [ordered]@{
            state = $state
            manual_intervention_required = $manual
            plan_present = $plan
            run_receipt_present = $receipt
            validation_present = $validation
            detected_arm_directory_count = $armDirectories.Count
            automatic_partial_arm_repair = $false
            automatic_deletion_allowed = $false
        }
    }
    catch {
        return [ordered]@{
            state = "focus_recovery_assessment_unreadable_manual_intervention"
            manual_intervention_required = $true
            assessment_error = [string]$_.Exception.Message
            automatic_partial_arm_repair = $false
            automatic_deletion_allowed = $false
        }
    }
}

function Get-ClosureReadiness {
    $code = @'
import json, sys
from pathlib import Path
from etudecas.prototypes.scan_2027_risk_control import verify_supplier_v8_stage3_closure as v
stage3 = Path(sys.argv[1]).resolve()
report_path = Path(sys.argv[2]).resolve()
if not report_path.is_file():
    print(json.dumps({"readiness": "WAIT", "reason": "closure_report_absent"}))
    raise SystemExit(0)
try:
    context = v.load_final_context(stage3)
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    expected = v.build_closure_report(context)
    technical = report.get("technical_verdict") or {}
    source = report.get("source") or {}
    valid = (
        report == expected
        and report.get("schema_version") == v.SCHEMA_VERSION
        and report.get("status") == "complete_audited"
        and technical.get("code") == "CONFORME_TECHNIQUE"
        and technical.get("conforme") is True
        and report.get("no_simulation_engine_started") is True
        and Path(str(source.get("supervision_dir") or "")).resolve() == stage3
    )
    if not valid:
        raise RuntimeError("closure report is not the exact technically conforming reconstruction")
    print(json.dumps({
        "readiness": "READY",
        "reason": "signed_exact_technical_closure",
        "closure_signature": report.get("closure_signature"),
        "technical_verdict": technical.get("code"),
        "stage3_contract_signature": context.contract.get("contract_signature"),
        "stage3_status_signature": context.status.get("status_signature"),
    }))
except Exception as exc:
    print(f"closure validation failed closed: {exc}", file=sys.stderr)
    raise SystemExit(3)
'@
    $result = Invoke-PythonCapture -Arguments @(
        "-c", $code, (Get-FullPath $Stage3SupervisionDir), (Get-FullPath $ClosureReport)
    )
    if ($result.exit_code -ne 0) {
        throw "Le rapport de cloture present n'est pas une preuve technique conforme : $($result.stderr)"
    }
    try {
        return ([string]$result.stdout).Trim() | ConvertFrom-Json
    }
    catch {
        throw "Le recu de disponibilite de la cloture n'est pas un JSON valide."
    }
}

function Wait-TechnicallyConformingClosure {
    $deadline = [DateTimeOffset]::UtcNow.AddHours($MaxWaitHours)
    while ($true) {
        $readiness = Get-ClosureReadiness
        if ([string]$readiness.readiness -eq "READY") {
            return $readiness
        }
        if ([DateTimeOffset]::UtcNow -ge $deadline) {
            throw "Delai d'attente du rapport de cloture techniquement conforme depasse."
        }
        Write-PostStage3Status -Status "waiting_closure" -Step "01_wait_closure" -Message (
            "Attente du rapport de cloture Stage3 signe et techniquement conforme. " +
            "Aucun focus et aucune livraison finale ne sont lances."
        ) -Details @{ closure_readiness = $readiness; scheduled_task_disabled = $false }
        Start-Sleep -Seconds $PollSeconds
    }
}

function Assert-OwnScheduledTask {
    Import-Module ScheduledTasks -ErrorAction Stop
    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop
    $actions = @($task.Actions)
    if ($actions.Count -ne 1) {
        throw "La tache apres-Stage3 doit avoir exactement une action."
    }
    if (-not [string]::Equals(
        [string]$task.Settings.MultipleInstances,
        "IgnoreNew",
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "La tache apres-Stage3 doit appliquer MultipleInstances=IgnoreNew."
    }
    $action = $actions[0]
    if (-not (Test-SamePath -Left ([string]$action.Execute) -Right $PowerShellExecutable)) {
        throw "L'action de la tache utilise un executable inattendu."
    }
    $scriptPath = Get-FullPath $PSCommandPath
    $expectedArguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
        $scriptPath + '"'
    if (-not [string]::Equals(
        ([string]$action.Arguments).Trim(),
        $expectedArguments,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "L'action de la tache n'est pas liee exactement a ce wrapper."
    }
    return $task
}

function Disable-OwnScheduledTask {
    $task = Assert-OwnScheduledTask
    $disableCommandSucceeded = ([string]$task.State -eq "Disabled")
    $disableCommandIssued = $false
    if ([string]$task.State -ne "Disabled") {
        $disableCommandIssued = $true
        Disable-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop |
            Out-Null
        # No fallible proof operation may turn a successful disabling mutation
        # into a failed workflow which can no longer resume.
        $disableCommandSucceeded = $true
    }
    $after = $null
    $enabledText = $null
    $postcheck = "not_run"
    $postcheckError = ""
    try {
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
            # The disabling command already succeeded: an enabled/stale read is
            # recorded but never rolls the validated delivery back to failure.
            $postcheck = "unexpected_enabled_after_successful_disable_command"
        }
        else {
            $postcheck = "definition_disabled_confirmed"
        }
    }
    catch {
        $postcheckError = [string]$_.Exception.Message
        if (-not $disableCommandSucceeded) {
            throw
        }
        # Disable-ScheduledTask already returned success. Failure of a subsequent
        # read-only proof must not strand a valid delivery behind a disabled task.
        $postcheck = "unavailable_after_successful_disable_command"
    }
    return [ordered]@{
        task_name = $TaskName
        task_path = $TaskPath
        disable_command_issued = $disableCommandIssued
        disable_command_succeeded = $disableCommandSucceeded
        postcheck = $postcheck
        postcheck_error = $postcheckError
        definition_enabled = if ($enabledText -eq "False") {
            $false
        }
        elseif ($enabledText -eq "True") {
            $true
        }
        else {
            $null
        }
        observed_runtime_state = if ($null -ne $after) { [string]$after.State } else { "unavailable" }
        running_state_accepted = ($null -ne $after -and [string]$after.State -eq "Running")
    }
}

function Get-FocusPlanArguments {
    return @(
        "-m", $FocusModule,
        "plan",
        "--stage3-supervision", (Get-FullPath $Stage3SupervisionDir),
        "--closure-report", (Get-FullPath $ClosureReport),
        "--output-root", (Get-FullPath $FocusRoot)
    )
}

function Get-DeliveryArguments {
    param([Parameter(Mandatory = $true)][string]$Command)
    if ($Command -notin @("build", "validate")) {
        throw "Commande de livraison non autorisee : $Command"
    }
    return @(
        "-m", $DeliveryModule,
        $Command,
        "--stage3-supervision-dir", (Get-FullPath $Stage3SupervisionDir),
        "--closure-report", (Get-FullPath $ClosureReport),
        "--focus-root", (Get-FullPath $FocusRoot),
        "--output-root", (Get-FullPath $DeliveryRoot)
    )
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
        stage3_supervision_dir = Get-FullPath $Stage3SupervisionDir
        closure_report = Get-FullPath $ClosureReport
        focus_root = Get-FullPath $FocusRoot
        delivery_root = Get-FullPath $DeliveryRoot
        supervision_dir = Get-FullPath $SupervisionDir
        planned_steps = @(
            "01_wait_exact_signed_technical_closure",
            "02_focus_plan_new_or_identical",
            "03_focus_preflight_maximum_four_sequential_arms",
            "04_focus_run_execute_once",
            "05_focus_finalize",
            "06_focus_validate",
            "07_delivery_v4_build_new_or_identical",
            "08_delivery_v4_validate",
            "09_disable_only_exact_own_task_after_success"
        )
        validation = $validation
    } | ConvertTo-Json -Depth 20
    exit 0
}

# Runtime starts only from an externally registered scheduled task. This file
# never creates, registers, replaces or unregisters a scheduled task.
[void](Assert-StaticInputs)
[void](Assert-OwnScheduledTask)

if (-not ("Etudecas.PostStage3FinalV4.NativeMethods" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
namespace Etudecas.PostStage3FinalV4 {
    public static class NativeMethods {
        [DllImport("kernel32.dll")]
        public static extern UInt32 SetThreadExecutionState(UInt32 executionState);
    }
}
"@ | Out-Null
}

$mutexName = "Local\Codex-Supplier-V8-Post-Stage3-Final-V4"
$createdNew = $false
$mutex = [Threading.Mutex]::new($true, $mutexName, [ref]$createdNew)
if (-not $createdNew) {
    $mutex.Dispose()
    throw "Une autre instance apres-Stage3 detient deja le mutex."
}
$crossSessionLock = $null
try {
    $crossSessionLock = Open-CrossSessionLock
}
catch {
    try { $mutex.ReleaseMutex() } catch { }
    $mutex.Dispose()
    throw
}

$completed = $false
$failure = $null
$terminalDetails = [ordered]@{}
$currentStep = "startup"
$focusValidationSucceeded = $false
try {
    Start-PostStage3KeepAwake
    $startupValidation = Assert-StaticInputs
    $currentStep = "01_wait_closure"
    Write-PostStage3Status -Status "waiting_closure" -Step "01_wait_closure" -Message (
        "Supervision demarree ; attente d'une cloture Stage3 exacte et techniquement conforme."
    ) -Details @{
        source_validation = $startupValidation
        scheduled_task_disabled = $false
    }
    $closureReadiness = Wait-TechnicallyConformingClosure

    $preFocusValidation = Assert-StaticInputs
    $currentStep = "02_focus_plan"
    Write-PostStage3Status -Status "planning_focus" -Step "02_focus_plan" -Message (
        "Cloture conforme recue ; creation ou reprise sans ecrasement du focus demande 338929."
    ) -Details @{
        closure_readiness = $closureReadiness
        source_validation = $preFocusValidation
        scheduled_task_disabled = $false
    }
    $focusPlan = Invoke-LoggedPythonStep -Step "02_focus_plan" -ParseJson -Arguments (
        Get-FocusPlanArguments
    )

    [void](Assert-StaticInputs)
    $currentStep = "03_focus_preflight"
    $focusPreflight = Invoke-LoggedPythonStep -Step "03_focus_preflight" -ParseJson -Arguments @(
        "-m", $FocusModule, "run", "--root", (Get-FullPath $FocusRoot)
    )
    $plannedArms = $focusPreflight.payload.planned_engine_runs
    if (
        $null -eq $plannedArms -or
        ($plannedArms -isnot [int] -and $plannedArms -isnot [long]) -or
        [int]$plannedArms -lt 0 -or
        [int]$plannedArms -gt $MaxFocusArms -or
        ([int]$plannedArms % 2) -ne 0 -or
        [string]$focusPreflight.payload.status -ne "validated_not_executed"
    ) {
        throw "Le precontrole du focus ne prouve pas un nombre pair de zero a quatre bras."
    }

    $preRunValidation = Assert-StaticInputs
    $currentStep = "04_focus_run_execute"
    Write-PostStage3Status -Status "running_focus" -Step "04_focus_run_execute" -Message (
        "Execution sequentielle du focus 338929 : $([int]$plannedArms) bras au maximum, sans parallelisme."
    ) -Details @{
        closure_readiness = $closureReadiness
        planned_focus_arms = [int]$plannedArms
        execution_mode = "single_python_process_sequential"
        source_validation = $preRunValidation
        scheduled_task_disabled = $false
    }
    $focusRun = Invoke-LoggedPythonStep -Step "04_focus_run_execute" -Arguments @(
        "-m", $FocusModule, "run", "--root", (Get-FullPath $FocusRoot), "--execute"
    )

    [void](Assert-StaticInputs)
    $currentStep = "05_focus_finalize"
    Write-PostStage3Status -Status "finalizing_focus" -Step "05_focus_finalize" -Message (
        "Bras du focus termines ; construction additive des traces lots."
    ) -Details @{ planned_focus_arms = [int]$plannedArms; scheduled_task_disabled = $false }
    $focusFinalize = Invoke-LoggedPythonStep -Step "05_focus_finalize" -ParseJson -Arguments @(
        "-m", $FocusModule, "finalize", "--root", (Get-FullPath $FocusRoot)
    )
    if ([string]$focusFinalize.payload.status -ne "complete_validated") {
        throw "La finalisation du focus n'a pas produit le statut complete_validated."
    }

    [void](Assert-StaticInputs)
    $currentStep = "06_focus_validate"
    $focusValidate = Invoke-LoggedPythonStep -Step "06_focus_validate" -ParseJson -Arguments @(
        "-m", $FocusModule, "validate", "--root", (Get-FullPath $FocusRoot)
    )
    if ([string]$focusValidate.payload.status -ne "complete_validated") {
        throw "La validation independante du focus n'est pas complete."
    }
    $focusValidationSucceeded = $true

    $preDeliveryValidation = Assert-StaticInputs
    $closureBeforeDelivery = Get-ClosureReadiness
    if ([string]$closureBeforeDelivery.readiness -ne "READY") {
        throw "La cloture n'est plus conforme avant la livraison V4."
    }
    $currentStep = "07_delivery_build"
    Write-PostStage3Status -Status "building_delivery" -Step "07_delivery_build" -Message (
        "Focus valide ; construction nouvelle-ou-identique du paquet HTML autonome V4."
    ) -Details @{
        focus_validation_signature = [string]$focusValidate.payload.validation_signature
        source_validation = $preDeliveryValidation
        scheduled_task_disabled = $false
    }
    $deliveryBuild = Invoke-LoggedPythonStep -Step "07_delivery_build" -ParseJson -Arguments (
        Get-DeliveryArguments -Command "build"
    )
    if ($deliveryBuild.payload.valid -ne $true -or [int]$deliveryBuild.payload.engine_runs_performed -ne 0) {
        throw "La construction de la livraison V4 n'a pas rendu un recu valide sans moteur."
    }

    $preFinalValidation = Assert-StaticInputs
    $currentStep = "08_delivery_validate"
    Write-PostStage3Status -Status "validating_delivery" -Step "08_delivery_validate" -Message (
        "Paquet V4 construit ; reproduction complete et validation finale avant desactivation."
    ) -Details @{ source_validation = $preFinalValidation; scheduled_task_disabled = $false }
    $deliveryValidate = Invoke-LoggedPythonStep -Step "08_delivery_validate" -ParseJson -Arguments (
        Get-DeliveryArguments -Command "validate"
    )
    if (
        $deliveryValidate.payload.valid -ne $true -or
        [int]$deliveryValidate.payload.engine_runs_performed -ne 0 -or
        [int]$deliveryValidate.payload.view_count -ne 3
    ) {
        throw "La validation finale V4 ne prouve pas le paquet autonome a trois vues."
    }
    [void](Assert-StaticInputs)
    $closureBeforeDisable = Get-ClosureReadiness
    if ([string]$closureBeforeDisable.readiness -ne "READY") {
        throw "La cloture n'est plus conforme apres la validation de la livraison V4."
    }

    $finalHtml = [string]$deliveryValidate.payload.html
    $finalManifest = [string]$deliveryValidate.payload.manifest
    if (
        -not [IO.File]::Exists((Get-FullPath $finalHtml)) -or
        -not [IO.File]::Exists((Get-FullPath $finalManifest)) -or
        -not (Test-PathOverlap -Left $DeliveryRoot -Right $finalHtml) -or
        -not (Test-PathOverlap -Left $DeliveryRoot -Right $finalManifest)
    ) {
        throw "Le recu final pointe hors de la racine de livraison ou vers une preuve absente."
    }
    $observedHtmlSha256 = (
        Get-FileHash -LiteralPath (Get-FullPath $finalHtml) -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    if ($observedHtmlSha256 -ne [string]$deliveryValidate.payload.html_sha256) {
        throw "Le HTML final a change apres sa validation reproductible."
    }
    try {
        $observedManifest = Get-Content -Raw -LiteralPath (Get-FullPath $finalManifest) |
            ConvertFrom-Json
    }
    catch {
        throw "Le manifeste final n'est plus un JSON lisible."
    }
    if (
        [string]$observedManifest.manifest_signature -ne
            [string]$deliveryValidate.payload.manifest_signature -or
        [string]$observedManifest.html_sha256 -ne $observedHtmlSha256
    ) {
        throw "Le manifeste final a change apres sa validation reproductible."
    }

    Write-PostStage3Status -Status "validated_before_task_disable" -Step "09_disable_own_task" -Message (
        "Livraison V4 reproduite et validee ; seule cette tache va maintenant etre desactivee."
    ) -Details @{
        final_html = Get-FullPath $finalHtml
        final_html_sha256 = $observedHtmlSha256
        final_manifest = Get-FullPath $finalManifest
        manifest_signature = [string]$deliveryValidate.payload.manifest_signature
        scheduled_task_disabled = $false
    }
    $terminalDetails = [ordered]@{
        closure_readiness = $closureReadiness
        planned_focus_arms = [int]$plannedArms
        focus_plan_log = [ordered]@{
            stdout_log = [string]$focusPlan.stdout_log
            stderr_log = [string]$focusPlan.stderr_log
            stdout_sha256 = [string]$focusPlan.stdout_sha256
            stderr_sha256 = [string]$focusPlan.stderr_sha256
        }
        focus_run_log = [ordered]@{
            stdout_log = [string]$focusRun.stdout_log
            stderr_log = [string]$focusRun.stderr_log
            stdout_sha256 = [string]$focusRun.stdout_sha256
            stderr_sha256 = [string]$focusRun.stderr_sha256
        }
        focus_validation_signature = [string]$focusValidate.payload.validation_signature
        final_html = Get-FullPath $finalHtml
        final_html_sha256 = $observedHtmlSha256
        final_manifest = Get-FullPath $finalManifest
        manifest_signature = [string]$deliveryValidate.payload.manifest_signature
        view_count = [int]$deliveryValidate.payload.view_count
        scheduled_task_disabled = $false
    }
    Write-JsonAtomic -Path ([IO.Path]::Combine(
        (Get-FullPath $SupervisionDir),
        "completion_receipt.json"
    )) -Payload ([ordered]@{
        schema_version = "$SchemaVersion.completion_receipt.v1"
        status = "delivery_validated_self_disable_authorized"
        created_at_utc = Get-UtcTimestamp
        task_name = $TaskName
        task_path = $TaskPath
        closure_signature = [string]$closureBeforeDisable.closure_signature
        focus_validation_signature = [string]$focusValidate.payload.validation_signature
        final_html = Get-FullPath $finalHtml
        final_html_sha256 = $observedHtmlSha256
        final_manifest = Get-FullPath $finalManifest
        manifest_signature = [string]$deliveryValidate.payload.manifest_signature
        delivery_view_count = [int]$deliveryValidate.payload.view_count
        self_disable_authorized_only_after_delivery_validation = $true
    })
    $currentStep = "09_disable_own_task"
    $disableProof = Disable-OwnScheduledTask
    # Disable-ScheduledTask success is the terminal transition. Nothing after
    # this assignment may turn the already validated delivery into a failure.
    $completed = $true
    $terminalDetails["task_disable_proof"] = $disableProof
    $terminalDetails["scheduled_task_disabled"] = (
        $disableProof.definition_enabled -eq $false
    )
    try {
        Write-JsonAtomic -Path ([IO.Path]::Combine(
            (Get-FullPath $SupervisionDir),
            "task_disable_receipt.json"
        )) -Payload ([ordered]@{
            schema_version = "$SchemaVersion.task_disable_receipt.v1"
            status = "disable_command_terminal"
            created_at_utc = Get-UtcTimestamp
            completion_receipt = [IO.Path]::Combine(
                (Get-FullPath $SupervisionDir),
                "completion_receipt.json"
            )
            task_disable_proof = $disableProof
        })
    }
    catch {
        $terminalDetails["task_disable_receipt_warning"] = [string]$_.Exception.Message
    }
}
catch {
    $failure = $_
}
finally {
    $keepAwakeStopError = ""
    try {
        Stop-PostStage3KeepAwake
    }
    catch {
        # Never mask the scientific failure or skip lock release because the
        # Windows keep-awake reset itself failed. Windows clears it on thread exit.
        $keepAwakeStopError = [string]$_.Exception.Message
    }
    try {
        if ($completed) {
            if ($keepAwakeStopError) {
                $terminalDetails["keep_awake_stop_warning"] = $keepAwakeStopError
            }
            if ($terminalDetails.scheduled_task_disabled) {
                $completionMessage = "Focus 338929 et paquet autonome V4 valides ; tache exacte desactivee."
            }
            elseif (
                $terminalDetails.task_disable_proof.postcheck -eq
                "unexpected_enabled_after_successful_disable_command"
            ) {
                $completionMessage = (
                    "Focus 338929 et paquet autonome V4 valides ; commande de " +
                    "desactivation acceptee mais definition encore observee active. " +
                    "Une prochaine execution idempotente retentera la desactivation."
                )
            }
            else {
                $completionMessage = (
                    "Focus 338929 et paquet autonome V4 valides ; commande de " +
                    "desactivation acceptee, relecture de la definition indisponible."
                )
            }
            Write-PostStage3Status -Status "complete" -Step "complete" -Message $completionMessage -Details $terminalDetails
        }
        else {
            $focusRecovery = Get-FocusRecoveryAssessment -FailedStep $currentStep -FocusValidationSucceeded $focusValidationSucceeded
            $failureDetails = [ordered]@{
                error = [ordered]@{
                    type = $failure.Exception.GetType().FullName
                    message = $failure.Exception.Message
                }
                failed_step = $currentStep
                focus_recovery_assessment = $focusRecovery
                recovery_policy = "reuse_only_fully_validated_outputs_partial_arm_requires_manual_intervention_never_delete"
                automatic_partial_arm_repair = $false
                scheduled_task_disabled = $false
            }
            if ($keepAwakeStopError) {
                $failureDetails["keep_awake_stop_warning"] = $keepAwakeStopError
            }
            if ($focusRecovery.manual_intervention_required) {
                Write-PostStage3Status -Status "manual_intervention_required" -Step "failed" -Message (
                    "Sortie focus partielle ou non validable detectee ; intervention manuelle " +
                    "requise. Aucune suppression ou reparation automatique n'est autorisee."
                ) -Details $failureDetails
            }
            else {
                Write-PostStage3Status -Status "failed_fail_closed" -Step "failed" -Message (
                    "Arret fail-closed ; seules les sorties entierement valides seront reutilisees. " +
                    "Aucune suppression automatique."
                ) -Details $failureDetails
            }
        }
    }
    catch {
        # Preserve the original failure if even the atomic status cannot be written.
    }
    if ($null -ne $crossSessionLock) {
        try { $crossSessionLock.Dispose() } catch { }
    }
    if ($null -ne $mutex) {
        try { $mutex.ReleaseMutex() } catch { }
        try { $mutex.Dispose() } catch { }
    }
}

if (-not $completed) {
    [Console]::Error.WriteLine([string]$failure.Exception.Message)
    exit 1
}
exit 0
