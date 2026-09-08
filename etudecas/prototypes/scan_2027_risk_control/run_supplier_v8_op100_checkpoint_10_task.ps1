[CmdletBinding()]
param(
    [string]$Repo = "C:\dev\lca-simu-pr40",
    [string]$Python = "C:\Users\yannick.martz\AppData\Local\Programs\Python\Python311\python.exe",
    [string]$CampaignRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2",
    [string]$OutputDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_checkpoint_10_20260906_v1",
    [string]$SupervisionDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_checkpoint_10_supervision_20260906_v1",
    [string]$PowerShellExecutable = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe",
    [int]$PollSeconds = 30,
    [double]$MaxWaitHours = 240,
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$SchemaVersion = "etudecas.supplier_v8.op100_checkpoint10_task.v1"
$AdapterModule = "etudecas.prototypes.scan_2027_risk_control.supplier_v8_op100_checkpoint_10"
$AdapterRelativePath = "etudecas\prototypes\scan_2027_risk_control\supplier_v8_op100_checkpoint_10.py"
$ExpectedAdapterSha256 = "4c8a672869073cd9193357c0bfd4086f224f7f215c8d6d8818eae194ae9199c8"
$FrozenChainWrapperRelativePath = "etudecas\prototypes\scan_2027_risk_control\run_supplier_v8_v2_to_stage3_v3_chain_task.ps1"
$ExpectedFrozenChainWrapperSha256 = "451e3ab5e7a5f737db6d9375242ca88a179aff65aa2db39bd7ced63c217529b6"
$ExpectedStage3InventorySignature = "d56761c3cdd704ec9d31bb2b452ee5dea25e9cdcf1e87c67d787a09e20b5a442"
$TaskName = "Codex-Supplier-V8-Op100-Checkpoint10"
$TaskPath = "\"
$ExpectedRepo = "C:\dev\lca-simu-pr40"
$ExpectedCampaignRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
$ExpectedOutputDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_checkpoint_10_20260906_v1"
$ExpectedSupervisionDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_checkpoint_10_supervision_20260906_v1"

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

function Assert-SamePath {
    param(
        [Parameter(Mandatory = $true)][string]$Observed,
        [Parameter(Mandatory = $true)][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Label
    )
    if (-not [string]::Equals(
        (Get-FullPath $Observed),
        (Get-FullPath $Expected),
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Chemin $Label non autorisé : $Observed"
    }
}

function Test-PathOverlap {
    param(
        [Parameter(Mandatory = $true)][string]$Left,
        [Parameter(Mandatory = $true)][string]$Right
    )
    $leftPath = (Get-FullPath $Left).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $rightPath = (Get-FullPath $Right).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $leftPrefix = $leftPath + [IO.Path]::DirectorySeparatorChar
    $rightPrefix = $rightPath + [IO.Path]::DirectorySeparatorChar
    return (
        [string]::Equals($leftPath, $rightPath, [StringComparison]::OrdinalIgnoreCase) -or
        $leftPath.StartsWith($rightPrefix, [StringComparison]::OrdinalIgnoreCase) -or
        $rightPath.StartsWith($leftPrefix, [StringComparison]::OrdinalIgnoreCase)
    )
}

function Assert-FixedRuntimeContract {
    Assert-SamePath -Observed $Repo -Expected $ExpectedRepo -Label "Repo"
    Assert-SamePath -Observed $CampaignRoot -Expected $ExpectedCampaignRoot -Label "CampaignRoot"
    Assert-SamePath -Observed $OutputDir -Expected $ExpectedOutputDir -Label "OutputDir"
    Assert-SamePath -Observed $SupervisionDir -Expected $ExpectedSupervisionDir -Label "SupervisionDir"
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
            throw "Impossible de démarrer le contrôle Python."
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        [Threading.Tasks.Task]::WaitAll(
            [Threading.Tasks.Task[]]@($stdoutTask, $stderrTask)
        )
        return [ordered]@{
            exit_code = [int]$process.ExitCode
            stdout = $stdoutTask.Result.Trim()
            stderr = $stderrTask.Result.Trim()
        }
    }
    finally {
        $process.Dispose()
    }
}

function ConvertFrom-CheckpointJson {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Label
    )
    if ([string]::IsNullOrWhiteSpace($Text)) {
        throw "Réponse JSON absente pour $Label."
    }
    try {
        return ($Text | ConvertFrom-Json -ErrorAction Stop)
    }
    catch {
        throw "Réponse JSON invalide pour $Label."
    }
}

function Get-ReadinessDecision {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Invocation)
    $payload = ConvertFrom-CheckpointJson -Text ([string]$Invocation.stdout) -Label "readiness"
    if ([int]$Invocation.exit_code -eq 2) {
        if ($payload.ready -ne $false -or [string]::IsNullOrWhiteSpace([string]$payload.status)) {
            throw "Readiness code 2 incohérente."
        }
        return [ordered]@{ disposition = "waiting"; payload = $payload }
    }
    if ([int]$Invocation.exit_code -eq 0) {
        if ($payload.ready -ne $true -or $payload.status -ne "ready_two_complete_shards") {
            throw "Readiness code 0 incohérente."
        }
        return [ordered]@{ disposition = "ready"; payload = $payload }
    }
    throw "Readiness en erreur (code $($Invocation.exit_code)) : $($Invocation.stderr)"
}

function Invoke-CheckpointMode {
    param([Parameter(Mandatory = $true)][string]$Mode)
    $arguments = @("-m", $AdapterModule, "--mode", $Mode)
    if ($Mode -in @("readiness", "build")) {
        $arguments += @("--campaign-root", (Get-FullPath $CampaignRoot))
    }
    if ($Mode -in @("build", "validate")) {
        $arguments += @("--output-dir", (Get-FullPath $OutputDir))
    }
    return Invoke-PythonCapture -Arguments $arguments
}

function Get-KeepAwakePayload {
    return [ordered]@{
        requested = $true
        active = $script:WakeActive
        method = "windows_SetThreadExecutionState"
        started_at_utc = $script:WakeStartedAtUtc
        stopped_at_utc = $script:WakeStoppedAtUtc
        coverage = "waiting_readiness_build_validate"
    }
}

function Start-CheckpointKeepAwake {
    if ($script:WakeActive) {
        throw "Le maintien en éveil est déjà actif."
    }
    if (-not ("Etudecas.V8Checkpoint10.NativeMethods" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
namespace Etudecas.V8Checkpoint10 {
    public static class NativeMethods {
        [DllImport("kernel32.dll")]
        public static extern UInt32 SetThreadExecutionState(UInt32 executionState);
    }
}
"@ | Out-Null
    }
    $script:WakeStartedAtUtc = Get-UtcTimestamp
    $state = [Convert]::ToUInt32("80000001", 16)
    $result = [Etudecas.V8Checkpoint10.NativeMethods]::SetThreadExecutionState($state)
    if ($result -eq 0) {
        throw "Windows a refusé le maintien en éveil."
    }
    $script:WakeActive = $true
}

function Stop-CheckpointKeepAwake {
    if ($script:WakeActive) {
        $continuous = [Convert]::ToUInt32("80000000", 16)
        [void][Etudecas.V8Checkpoint10.NativeMethods]::SetThreadExecutionState($continuous)
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
        "." + [IO.Path]::GetFileName($destination) + ".backup." +
            $PID + "." + [Guid]::NewGuid().ToString("N")
    )
    $json = ($Payload | ConvertTo-Json -Depth 12) + [Environment]::NewLine
    [IO.File]::WriteAllText($temporary, $json, [Text.UTF8Encoding]::new($false))
    for ($attempt = 0; $attempt -lt 12; $attempt++) {
        try {
            if ([IO.File]::Exists($destination)) {
                [IO.File]::Replace($temporary, $destination, $backup, $true)
                [IO.File]::Delete($backup)
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
        Start-Sleep -Milliseconds ([Math]::Min(1000, 50 * [Math]::Pow(2, $attempt)))
    }
}

function Write-CheckpointStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][string]$Message,
        [string]$Step = "",
        [System.Collections.IDictionary]$Details = @{}
    )
    $payload = [ordered]@{
        schema_version = "$SchemaVersion.status.v1"
        status = $Status
        business_message_fr = $Message
        step = $Step
        updated_at_utc = Get-UtcTimestamp
        campaign_root = Get-FullPath $CampaignRoot
        output_dir = Get-FullPath $OutputDir
        entrypoint = [IO.Path]::Combine(
            (Get-FullPath $OutputDir),
            "OUVRIR_BILAN_PROVISOIRE_REFERENCE_10_SUR_30.html"
        )
        task = [ordered]@{
            name = $TaskName
            path = $TaskPath
            self_disable_pending = ($Status -ne "complete")
        }
        keep_awake = Get-KeepAwakePayload
    }
    foreach ($key in $Details.Keys) {
        $payload[$key] = $Details[$key]
    }
    Write-JsonAtomic -Path ([IO.Path]::Combine(
        (Get-FullPath $SupervisionDir), "status.json"
    )) -Payload $payload
}

function Assert-StaticInputs {
    $resolvedRepo = Get-FullPath $Repo
    if (-not [IO.Directory]::Exists($resolvedRepo)) {
        throw "Dépôt absent : $resolvedRepo"
    }
    if (-not [IO.Directory]::Exists((Get-FullPath $CampaignRoot))) {
        throw "Campagne absente : $CampaignRoot"
    }
    if (-not [IO.File]::Exists((Get-FullPath $Python))) {
        throw "Interpréteur Python absent : $Python"
    }
    if (-not [IO.File]::Exists((Get-FullPath $PowerShellExecutable))) {
        throw "Exécutable PowerShell absent : $PowerShellExecutable"
    }
    if ($PollSeconds -lt 1 -or $PollSeconds -gt 60) {
        throw "PollSeconds doit être compris entre 1 et 60 secondes."
    }
    if ($MaxWaitHours -le 0) {
        throw "MaxWaitHours doit être strictement positif."
    }
    if (
        (Test-PathOverlap -Left $OutputDir -Right $SupervisionDir) -or
        (Test-PathOverlap -Left $OutputDir -Right $CampaignRoot) -or
        (Test-PathOverlap -Left $SupervisionDir -Right $CampaignRoot) -or
        (Test-PathOverlap -Left $OutputDir -Right $Repo) -or
        (Test-PathOverlap -Left $SupervisionDir -Right $Repo)
    ) {
        throw "Les sources, la sortie et la supervision doivent rester disjointes."
    }

    $adapterPath = [IO.Path]::Combine($resolvedRepo, $AdapterRelativePath)
    $chainWrapperPath = [IO.Path]::Combine(
        $resolvedRepo, $FrozenChainWrapperRelativePath
    )
    foreach ($source in @(
        [ordered]@{ path = $adapterPath; expected = $ExpectedAdapterSha256; label = "adaptateur" },
        [ordered]@{ path = $chainWrapperPath; expected = $ExpectedFrozenChainWrapperSha256; label = "wrapper gelé" }
    )) {
        if (-not [IO.File]::Exists($source.path)) {
            throw "Source absente ($($source.label)) : $($source.path)"
        }
        $actual = (Get-FileHash -LiteralPath $source.path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $source.expected) {
            throw "Empreinte différente ($($source.label)) : $actual"
        }
    }

    $inventoryCode = @"
import sys
from pathlib import Path
from etudecas.prototypes.scan_2027_risk_control import supplier_v8_stage3_common as common
inventory = common.build_source_inventory(Path(sys.argv[1]))
common.verify_source_inventory(inventory)
print(inventory["inventory_signature"])
"@
    $inventoryInvocation = Invoke-PythonCapture -Arguments @(
        "-c", $inventoryCode, $resolvedRepo
    )
    if ($inventoryInvocation.exit_code -ne 0) {
        throw "Validation de l'inventaire Stage3 en erreur : $($inventoryInvocation.stderr)"
    }
    if ($inventoryInvocation.stdout -ne $ExpectedStage3InventorySignature) {
        throw "Inventaire Stage3 différent : $($inventoryInvocation.stdout)"
    }
    return [ordered]@{
        adapter_sha256 = $ExpectedAdapterSha256
        frozen_chain_wrapper_sha256 = $ExpectedFrozenChainWrapperSha256
        stage3_inventory_signature = $ExpectedStage3InventorySignature
    }
}

function Assert-OwnScheduledTask {
    Import-Module ScheduledTasks -ErrorAction Stop
    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop
    $actions = @($task.Actions)
    if ($actions.Count -ne 1) {
        throw "La tâche doit avoir exactement une action."
    }
    $action = $actions[0]
    if (-not [string]::Equals(
        (Get-FullPath ([string]$action.Execute)),
        (Get-FullPath $PowerShellExecutable),
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "L'action de la tâche n'utilise pas le PowerShell attendu."
    }
    $scriptPath = Get-FullPath $PSCommandPath
    $expectedArguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
        $scriptPath + '"'
    if (-not [string]::Equals(
        ([string]$action.Arguments).Trim(),
        $expectedArguments,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "La tâche ne pointe pas exclusivement vers ce wrapper."
    }
    return $task
}

function Disable-OwnScheduledTask {
    $task = Assert-OwnScheduledTask
    if ([string]$task.State -ne "Disabled") {
        Disable-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop | Out-Null
    }
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
        $enabledText, "False", [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "La définition de la tâche reste activée."
    }
    return [ordered]@{
        name = $TaskName
        path = $TaskPath
        definition_enabled = $false
        observed_runtime_state = [string]$after.State
    }
}

if ($ValidateOnly) {
    $validation = Assert-StaticInputs
    [ordered]@{
        schema_version = "$SchemaVersion.validation.v1"
        status = "valid"
        mode = "validate_only"
        launch_performed = $false
        build_performed = $false
        scheduled_task_changed = $false
        filesystem_mutation_performed = $false
        task_name = $TaskName
        task_path = $TaskPath
        poll_seconds = $PollSeconds
        campaign_root = Get-FullPath $CampaignRoot
        output_dir = Get-FullPath $OutputDir
        supervision_dir = Get-FullPath $SupervisionDir
        planned_steps = @("readiness", "build", "validate", "disable_own_task_after_success")
        validation = $validation
    } | ConvertTo-Json -Depth 12
    exit 0
}

Assert-FixedRuntimeContract
[IO.Directory]::CreateDirectory((Get-FullPath $SupervisionDir)) | Out-Null
$lockPath = [IO.Path]::Combine((Get-FullPath $SupervisionDir), ".checkpoint10.lock")
try {
    $checkpointLock = [IO.File]::Open(
        $lockPath,
        [IO.FileMode]::OpenOrCreate,
        [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None
    )
}
catch {
    throw "Une autre instance du bilan provisoire détient déjà le verrou."
}

$failure = $null
$completed = $false
$terminalDetails = [ordered]@{}
try {
    [void](Assert-OwnScheduledTask)
    Start-CheckpointKeepAwake
    $sourceValidation = Assert-StaticInputs
    $deadline = [DateTimeOffset]::UtcNow.AddHours($MaxWaitHours)

    while (-not $completed) {
        Write-CheckpointStatus -Status "checking" -Message "Vérification sûre de la fin des deux blocs de référence." -Step "readiness" -Details @{
            source_validation = $sourceValidation
        }
        $readinessInvocation = Invoke-CheckpointMode -Mode "readiness"
        $decision = Get-ReadinessDecision -Invocation $readinessInvocation
        if ($decision.disposition -eq "waiting") {
            Write-CheckpointStatus -Status "waiting" -Message "Les deux blocs ne sont pas encore tous les deux terminés ; aucun bilan n'est construit." -Step "readiness" -Details @{
                readiness = $decision.payload
                readiness_exit_code = 2
            }
            if ([DateTimeOffset]::UtcNow -ge $deadline) {
                throw "Délai maximal d'attente des deux blocs dépassé."
            }
            Start-Sleep -Seconds $PollSeconds
            continue
        }

        Write-CheckpointStatus -Status "building" -Message "Les deux blocs sont terminés ; construction atomique du bilan provisoire." -Step "build" -Details @{
            readiness = $decision.payload
        }
        $buildInvocation = Invoke-CheckpointMode -Mode "build"
        if ($buildInvocation.exit_code -eq 2) {
            $buildPayload = ConvertFrom-CheckpointJson -Text $buildInvocation.stdout -Label "build en attente"
            Write-CheckpointStatus -Status "waiting" -Message "Une activité a repris pendant le contrôle ; nouvelle attente sans publication partielle." -Step "build" -Details @{
                build = $buildPayload
                build_exit_code = 2
            }
            if ([DateTimeOffset]::UtcNow -ge $deadline) {
                throw "Délai maximal d'attente après reprise d'activité dépassé."
            }
            Start-Sleep -Seconds $PollSeconds
            continue
        }
        if ($buildInvocation.exit_code -ne 0) {
            throw "Construction en erreur (code $($buildInvocation.exit_code)) : $($buildInvocation.stderr)"
        }
        $buildPayload = ConvertFrom-CheckpointJson -Text $buildInvocation.stdout -Label "build"
        if (
            $buildPayload.status -notin @("created", "already_identical") -or
            [int]$buildPayload.case_count -ne 370 -or
            [int]$buildPayload.engine_runs_started -ne 0
        ) {
            throw "Contrat de construction incohérent."
        }
        Assert-SamePath -Observed ([string]$buildPayload.output_dir) -Expected $OutputDir -Label "sortie du build"

        Write-CheckpointStatus -Status "validating" -Message "Bilan construit ; validation indépendante du paquet autonome." -Step "validate" -Details @{
            build = $buildPayload
        }
        $validateInvocation = Invoke-CheckpointMode -Mode "validate"
        if ($validateInvocation.exit_code -ne 0) {
            throw "Validation en erreur (code $($validateInvocation.exit_code)) : $($validateInvocation.stderr)"
        }
        $validatePayload = ConvertFrom-CheckpointJson -Text $validateInvocation.stdout -Label "validate"
        if ($validatePayload.status -ne "valid") {
            throw "Le paquet n'est pas déclaré valide."
        }
        Assert-SamePath -Observed ([string]$validatePayload.output_dir) -Expected $OutputDir -Label "sortie validée"
        if ($validatePayload.package_signature -ne $buildPayload.package_signature) {
            throw "La signature du paquet diffère entre construction et validation."
        }

        Write-CheckpointStatus -Status "validated_before_task_disable" -Message "Paquet validé ; désactivation de cette tâche uniquement." -Step "disable_own_task" -Details @{
            build = $buildPayload
            validation = $validatePayload
        }
        $taskDisable = Disable-OwnScheduledTask
        $terminalDetails = [ordered]@{
            source_validation = $sourceValidation
            readiness = $decision.payload
            build = $buildPayload
            validation = $validatePayload
            task_disable = $taskDisable
            scheduled_task_disabled = $true
        }
        $completed = $true
    }
}
catch {
    $failure = $_
}
finally {
    Stop-CheckpointKeepAwake
    try {
        if ($completed) {
            Write-CheckpointStatus -Status "complete" -Message "Bilan provisoire construit, validé et tâche dédiée désactivée." -Step "complete" -Details $terminalDetails
        }
        else {
            Write-CheckpointStatus -Status "failed" -Message "Chaîne arrêtée sur une erreur réelle ; la tâche dédiée reste disponible." -Step "failed" -Details @{
                error = [ordered]@{
                    type = $failure.Exception.GetType().FullName
                    message = $failure.Exception.Message
                }
                scheduled_task_disabled = $false
            }
        }
    }
    finally {
        $checkpointLock.Dispose()
    }
}

if ($null -ne $failure) {
    throw $failure
}
exit 0
