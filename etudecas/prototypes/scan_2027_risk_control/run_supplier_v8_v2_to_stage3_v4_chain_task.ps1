[CmdletBinding()]
param(
    [string]$Repo = "C:\dev\lca-simu-pr40",
    [string]$Python = "C:\Users\yannick.martz\AppData\Local\Programs\Python\Python311\python.exe",
    [string]$CampaignRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2",
    [string]$CampaignRunner = "C:\dev\lca-simu-pr40\etudecas\prototypes\scan_2027_risk_control\supplier_operating_point_full_campaign_v8.py",
    [string]$RecoverySupervisionDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_v2_recovery_supervision_20260906_v1",
    [string]$ResultsDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_results_20260906_v2",
    [string]$V7PlanDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_plan_20260905_v7",
    [string]$V7RunDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_run_20260905_v7",
    [string]$TracePackageDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v7_campaign_trace_package_20260905_v1",
    [string]$BridgeJson = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\validated_operating_points_v7_20260905_v1.json",
    [string]$Observed2025Dir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\observed_2025_supply_bilan_20260901_v1",
    [string]$LotReplayRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_lot_replays_20260906_v3",
    [string]$QualificationDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_physical_qualification_20260906_v3",
    [string]$ActionReplayRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_action_replays_20260906_v3",
    [string]$CurvesDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_nominal_curves_20260906_v3",
    [string]$RegistryDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_incident_lot_registry_20260906_v3",
    [string]$FinalHtml = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\OUVRIR_DEMONSTRATION_RISQUES_FOURNISSEURS_V8_STAGE2_20260906_V3.html",
    [string]$Stage3SupervisionDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_supervision_20260906_v3",
    [string]$Stage3GoFile = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_go_20260906_v5.json",
    [string]$ChainSupervisionDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_v2_to_stage3_v4_chain_supervision_20260906_v1",
    [string]$PowerShellExecutable = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe",
    [string]$TaskName = "Codex-Supplier-V8-V2-To-Stage3-V3",
    [string]$TaskPath = "\",
    [double]$ProcessPollSeconds = 30,
    [double]$Stage3GoPollSeconds = 60,
    [double]$MaxWaitHours = 240,
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$SchemaVersion = "etudecas.supplier_v8_v2_to_stage3_v4_chain.v1"
$Stage3GoSchemaVersion = "$SchemaVersion.stage3_go.v1"
$ExpectedStage3InventorySignature = "d56761c3cdd704ec9d31bb2b452ee5dea25e9cdcf1e87c67d787a09e20b5a442"
$ExpectedSourceSha256 = [ordered]@{
    "etudecas\prototypes\scan_2027_risk_control\launch_supplier_operating_point_full_campaign_v8_resilient.py" = "82c78d47b2fb8e37f028d3568c0697a1c21172df62bf83a30e16ba80655fb3b7"
    "etudecas\prototypes\scan_2027_risk_control\launch_supplier_operating_point_full_campaign_v8.py" = "bd8f39d03f97766e193a683076884739bdb72dabcc51fe06b2eadd4e9a146405"
    "etudecas\prototypes\scan_2027_risk_control\supervise_supplier_operating_point_full_campaign_v8_v2.py" = "2ad3309ca0db131f54998337d663afd9512300fad97fe27b7ec707d31187c254"
    "etudecas\prototypes\scan_2027_risk_control\supplier_operating_point_full_campaign_v8.py" = "3dd8835992c9d97093fc6eaa0ba52dabfd0574fb775bbf8c62c2a26c9950bd39"
    "etudecas\prototypes\scan_2027_risk_control\finalize_supplier_operating_point_full_campaign_v8.py" = "a3cc635a8adc30522ecf2dbbb066bd81a3c4ac9bedf0a1d4552a14ec65f7c7ec"
    "etudecas\prototypes\scan_2027_risk_control\finalize_supplier_operating_point_full_campaign_v8_compat.py" = "87718a8349d9f8318136af27c7a8507c6e23d0d0b93e255cd71a3d8dbdda6523"
    "etudecas\prototypes\scan_2027_risk_control\supplier_v8_stage3_common.py" = "7be27751d4c38ee89a742771d34053dedad014d18381151991bf1a6a2fe05b2c"
    "etudecas\prototypes\scan_2027_risk_control\supplier_v8_stage3_pipeline.py" = "e6775ad6e5b94bdf51b1544c7a62522d496fb9c6b607f98d8c7329f7e46c218c"
    "etudecas\prototypes\scan_2027_risk_control\supplier_v8_stage3_dashboard.py" = "1c85162fd6440f907fe02b65dcde3c770dfc859b6de5c36829bd8abee65b747b"
    "etudecas\prototypes\scan_2027_risk_control\supplier_v8_stage3_delivery.py" = "45ab46efef50b3f0f7aef003b8e095e36510aea783e2f724b39e0521d0131d33"
    "etudecas\prototypes\scan_2027_risk_control\supplier_v8_stage3_watcher.py" = "e4043b4bc237b08e67a7ca2b4e38451577f33558e9de30852b09c401fab0ec4f"
    "etudecas\prototypes\scan_2027_risk_control\supplier_v8_stage3_runbook_20260906_v3.md" = "df0a65db2d6c90fdddbb8fcd60de0f2950163d360ae8ba6fdf12b4af64259a3d"
}

$script:WakeActive = $false
$script:WakeStartedAtUtc = ""
$script:WakeStoppedAtUtc = ""

if (-not ("Etudecas.V8Chain.NativeMethods" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
namespace Etudecas.V8Chain {
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

function Get-KeepAwakePayload {
    return [ordered]@{
        requested = $true
        active = $script:WakeActive
        method = "windows_SetThreadExecutionState"
        started_at_utc = $script:WakeStartedAtUtc
        stopped_at_utc = $script:WakeStoppedAtUtc
        coverage = "supervisor_finalizer_stage3_html_validation"
    }
}

function Start-ChainKeepAwake {
    if ($script:WakeActive) {
        throw "Le maintien en éveil de la chaîne est déjà actif."
    }
    $script:WakeStartedAtUtc = Get-UtcTimestamp
    $state = [Convert]::ToUInt32("80000001", 16)
    $result = [Etudecas.V8Chain.NativeMethods]::SetThreadExecutionState($state)
    if ($result -eq 0) {
        throw "Windows a refusé le maintien en éveil de la chaîne."
    }
    $script:WakeActive = $true
}

function Stop-ChainKeepAwake {
    if ($script:WakeActive) {
        $continuous = [Convert]::ToUInt32("80000000", 16)
        [void][Etudecas.V8Chain.NativeMethods]::SetThreadExecutionState($continuous)
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
    $json = ($Payload | ConvertTo-Json -Depth 12) + [Environment]::NewLine
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
            $delayMilliseconds = [Math]::Min(1000, 50 * [Math]::Pow(2, $attempt))
            Start-Sleep -Milliseconds ([int]$delayMilliseconds)
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

function Write-ChainStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][string]$BusinessStatus,
        [Parameter(Mandatory = $true)][string]$Message,
        [string]$Step = "",
        [System.Collections.IDictionary]$Details = @{}
    )
    $payload = [ordered]@{
        schema_version = "$SchemaVersion.status.v1"
        status = $Status
        business_status = $BusinessStatus
        business_message_fr = $Message
        step = $Step
        updated_at_utc = Get-UtcTimestamp
        task = [ordered]@{
            name = $TaskName
            path = $TaskPath
            self_disable_pending = ($BusinessStatus -ne "complete")
        }
        campaign_root = Get-FullPath $CampaignRoot
        results_dir = Get-FullPath $ResultsDir
        final_html = Get-FullPath $FinalHtml
        stage3_go_file = Get-FullPath $Stage3GoFile
        keep_awake = Get-KeepAwakePayload
    }
    foreach ($key in $Details.Keys) {
        $payload[$key] = $Details[$key]
    }
    $statusPath = [IO.Path]::Combine(
        (Get-FullPath $ChainSupervisionDir),
        "status.json"
    )
    Write-JsonAtomic -Path $statusPath -Payload $payload
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

function Add-Utf8LogHeader {
    param(
        [Parameter(Mandatory = $true)][IO.Stream]$Stream,
        [Parameter(Mandatory = $true)][string]$Step,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    $header = [Environment]::NewLine + "[" + (Get-UtcTimestamp) + "] " +
        $Step + " " + (($Arguments | ForEach-Object {
            ConvertTo-WindowsArgument $_
        }) -join " ") + [Environment]::NewLine
    $bytes = [Text.Encoding]::UTF8.GetBytes($header)
    $Stream.Write($bytes, 0, $bytes.Length)
    $Stream.Flush()
}

function Invoke-LoggedPythonStep {
    param(
        [Parameter(Mandatory = $true)][string]$Step,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    $directory = Get-FullPath $ChainSupervisionDir
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $stdoutPath = [IO.Path]::Combine($directory, "$Step.stdout.log")
    $stderrPath = [IO.Path]::Combine($directory, "$Step.stderr.log")
    $stdout = [IO.File]::Open(
        $stdoutPath,
        [IO.FileMode]::Append,
        [IO.FileAccess]::Write,
        [IO.FileShare]::ReadWrite
    )
    $stderr = [IO.File]::Open(
        $stderrPath,
        [IO.FileMode]::Append,
        [IO.FileAccess]::Write,
        [IO.FileShare]::ReadWrite
    )
    $process = $null
    try {
        Add-Utf8LogHeader -Stream $stdout -Step $Step -Arguments $Arguments
        Add-Utf8LogHeader -Stream $stderr -Step $Step -Arguments $Arguments
        $process = [Diagnostics.Process]::new()
        $process.StartInfo = New-PythonProcessStartInfo -Arguments $Arguments
        if (-not $process.Start()) {
            throw "Impossible de démarrer l'étape $Step."
        }
        $stdoutCopy = $process.StandardOutput.BaseStream.CopyToAsync($stdout)
        $stderrCopy = $process.StandardError.BaseStream.CopyToAsync($stderr)
        $process.WaitForExit()
        [Threading.Tasks.Task]::WaitAll(
            [Threading.Tasks.Task[]]@($stdoutCopy, $stderrCopy)
        )
        if ($process.ExitCode -ne 0) {
            throw "L'étape $Step a retourné le code $($process.ExitCode)."
        }
        return [ordered]@{
            exit_code = $process.ExitCode
            stdout_log = $stdoutPath
            stderr_log = $stderrPath
        }
    }
    finally {
        if ($null -ne $process) { $process.Dispose() }
        $stdout.Dispose()
        $stderr.Dispose()
    }
}

function Write-SkippedStepLogs {
    param(
        [Parameter(Mandatory = $true)][string]$Step,
        [Parameter(Mandatory = $true)][string]$Reason
    )
    $directory = Get-FullPath $ChainSupervisionDir
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    foreach ($streamName in @("stdout", "stderr")) {
        $path = [IO.Path]::Combine($directory, "$Step.$streamName.log")
        $line = "[" + (Get-UtcTimestamp) + "] SKIPPED: " + $Reason +
            [Environment]::NewLine
        $bytes = [Text.Encoding]::UTF8.GetBytes($line)
        $stream = [IO.File]::Open(
            $path,
            [IO.FileMode]::Append,
            [IO.FileAccess]::Write,
            [IO.FileShare]::ReadWrite
        )
        try {
            $stream.Write($bytes, 0, $bytes.Length)
        }
        finally {
            $stream.Dispose()
        }
    }
}

function Invoke-PythonCapture {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $process = [Diagnostics.Process]::new()
    try {
        $process.StartInfo = New-PythonProcessStartInfo -Arguments $Arguments
        if (-not $process.Start()) {
            throw "Impossible de démarrer la validation Python."
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        [Threading.Tasks.Task]::WaitAll(
            [Threading.Tasks.Task[]]@($stdoutTask, $stderrTask)
        )
        if ($process.ExitCode -ne 0) {
            throw "Validation Python refusée : $($stderrTask.Result)"
        }
        return $stdoutTask.Result.Trim()
    }
    finally {
        $process.Dispose()
    }
}

function Assert-StaticInputs {
    $resolvedRepo = Get-FullPath $Repo
    if (-not [IO.Directory]::Exists($resolvedRepo)) {
        throw "Dépôt absent : $resolvedRepo"
    }
    if (-not [IO.File]::Exists((Get-FullPath $Python))) {
        throw "Interpréteur Python absent : $Python"
    }
    if (-not [IO.File]::Exists((Get-FullPath $PowerShellExecutable))) {
        throw "Executable PowerShell absent : $PowerShellExecutable"
    }
    if (-not [IO.Directory]::Exists((Get-FullPath $CampaignRoot))) {
        throw "Campagne V8-v2 absente : $CampaignRoot"
    }
    $requiredDirectories = [ordered]@{
        V7PlanDir = $V7PlanDir
        V7RunDir = $V7RunDir
        TracePackageDir = $TracePackageDir
        Observed2025Dir = $Observed2025Dir
    }
    foreach ($entry in $requiredDirectories.GetEnumerator()) {
        if (-not [IO.Directory]::Exists((Get-FullPath ([string]$entry.Value)))) {
            throw "Repertoire obligatoire absent ($($entry.Key)) : $($entry.Value)"
        }
    }
    if (-not [IO.File]::Exists((Get-FullPath $BridgeJson))) {
        throw "Fichier bridge obligatoire absent : $BridgeJson"
    }
    $expectedRunnerPath = [IO.Path]::Combine(
        $resolvedRepo,
        "etudecas\prototypes\scan_2027_risk_control\supplier_operating_point_full_campaign_v8.py"
    )
    if (-not [string]::Equals(
        (Get-FullPath $CampaignRunner),
        (Get-FullPath $expectedRunnerPath),
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "CampaignRunner doit etre le runner V8 fige dans le depot audite."
    }
    if ($ProcessPollSeconds -le 0 -or $ProcessPollSeconds -gt 300) {
        throw "ProcessPollSeconds doit être dans ]0, 300]."
    }
    if ($Stage3GoPollSeconds -lt 1 -or $Stage3GoPollSeconds -gt 60) {
        throw "Stage3GoPollSeconds doit être dans [1, 60]."
    }
    if ($MaxWaitHours -le 0) {
        throw "MaxWaitHours doit être strictement positif."
    }
    if ([string]::IsNullOrWhiteSpace($TaskName)) {
        throw "Le nom de la tâche planifiée est obligatoire."
    }

    $protectedInputs = @(
        $resolvedRepo,
        (Get-FullPath $CampaignRoot),
        (Get-FullPath $V7PlanDir),
        (Get-FullPath $V7RunDir),
        (Get-FullPath $TracePackageDir),
        (Get-FullPath $Observed2025Dir)
    )
    $outputLocations = @(
        (Get-FullPath $RecoverySupervisionDir),
        (Get-FullPath $ResultsDir),
        (Get-FullPath $LotReplayRoot),
        (Get-FullPath $QualificationDir),
        (Get-FullPath $ActionReplayRoot),
        (Get-FullPath $CurvesDir),
        (Get-FullPath $RegistryDir),
        (Get-FullPath $Stage3SupervisionDir),
        (Get-FullPath $ChainSupervisionDir),
        (Get-FullPath $FinalHtml)
    )
    $normalizedOutputs = @(
        $outputLocations | ForEach-Object {
            $_.TrimEnd([IO.Path]::DirectorySeparatorChar).ToLowerInvariant()
        }
    )
    if (@($normalizedOutputs | Select-Object -Unique).Count -ne $normalizedOutputs.Count) {
        throw "Les sorties V8, Stage3 et supervision doivent etre distinctes."
    }
    for ($leftIndex = 0; $leftIndex -lt $outputLocations.Count; $leftIndex++) {
        for (
            $rightIndex = $leftIndex + 1;
            $rightIndex -lt $outputLocations.Count;
            $rightIndex++
        ) {
            $left = $outputLocations[$leftIndex].TrimEnd(
                [IO.Path]::DirectorySeparatorChar
            )
            $right = $outputLocations[$rightIndex].TrimEnd(
                [IO.Path]::DirectorySeparatorChar
            )
            $leftPrefix = $left + [IO.Path]::DirectorySeparatorChar
            $rightPrefix = $right + [IO.Path]::DirectorySeparatorChar
            if (
                $left.StartsWith(
                    $rightPrefix,
                    [StringComparison]::OrdinalIgnoreCase
                ) -or
                $right.StartsWith(
                    $leftPrefix,
                    [StringComparison]::OrdinalIgnoreCase
                )
            ) {
                throw "Deux sorties V8, Stage3 ou supervision se chevauchent."
            }
        }
    }
    foreach ($output in $outputLocations) {
        foreach ($protected in $protectedInputs) {
            $prefix = $protected.TrimEnd([IO.Path]::DirectorySeparatorChar) +
                [IO.Path]::DirectorySeparatorChar
            $outputPrefix = $output.TrimEnd(
                [IO.Path]::DirectorySeparatorChar
            ) + [IO.Path]::DirectorySeparatorChar
            if (
                [string]::Equals(
                    $output,
                    $protected,
                    [StringComparison]::OrdinalIgnoreCase
                ) -or
                $output.StartsWith(
                    $prefix,
                    [StringComparison]::OrdinalIgnoreCase
                ) -or
                $protected.StartsWith(
                    $outputPrefix,
                    [StringComparison]::OrdinalIgnoreCase
                )
            ) {
                throw "Une sortie est confondue avec une source protegee : $output"
            }
        }
    }

    $actualHashes = [ordered]@{}
    foreach ($relativePath in $ExpectedSourceSha256.Keys) {
        $path = [IO.Path]::Combine($resolvedRepo, $relativePath)
        if (-not [IO.File]::Exists($path)) {
            throw "Source obligatoire absente : $path"
        }
        $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        $expected = $ExpectedSourceSha256[$relativePath]
        if ($actual -ne $expected) {
            throw "Empreinte source différente pour $relativePath : $actual"
        }
        $actualHashes[$relativePath] = $actual
    }

    $inventoryCode = @"
import sys
from pathlib import Path
from etudecas.prototypes.scan_2027_risk_control import supplier_v8_stage3_common as common
inventory = common.build_source_inventory(Path(sys.argv[1]))
common.verify_source_inventory(inventory)
print(inventory["inventory_signature"])
"@
    $inventorySignature = Invoke-PythonCapture -Arguments @(
        "-c", $inventoryCode, $resolvedRepo
    )
    if ($inventorySignature -ne $ExpectedStage3InventorySignature) {
        throw "Inventaire transitif Stage3 V3 différent : $inventorySignature"
    }
    return [ordered]@{
        source_hashes = $actualHashes
        stage3_inventory_signature = $inventorySignature
    }
}

function Read-JsonShared {
    param([Parameter(Mandatory = $true)][string]$Path)
    $share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $stream = [IO.File]::Open(
        (Get-FullPath $Path),
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        $share
    )
    try {
        $reader = [IO.StreamReader]::new(
            $stream,
            [Text.Encoding]::UTF8,
            $true,
            4096,
            $true
        )
        try {
            return ($reader.ReadToEnd() | ConvertFrom-Json)
        }
        finally {
            $reader.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
}

function Get-JsonProperty {
    param(
        [Parameter(Mandatory = $true)][object]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
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
        throw "Le GO Stage3 ne correspond pas au chemin $Label."
    }
}

function Read-AndValidateStage3Go {
    param([Parameter(Mandatory = $true)][string]$Path)
    $go = Read-JsonShared -Path $Path
    if ((Get-JsonProperty $go "schema_version") -ne $Stage3GoSchemaVersion) {
        throw "Schéma du GO Stage3 invalide."
    }
    if ((Get-JsonProperty $go "decision") -ne "GO_STAGE3_V4") {
        throw "La décision indépendante Stage3 n'est pas GO_STAGE3_V4."
    }
    $goInventorySignature = [string](
        Get-JsonProperty $go "stage3_inventory_signature"
    )
    if ($goInventorySignature -ne $ExpectedStage3InventorySignature) {
        throw "Le champ stage3_inventory_signature du GO Stage3 est absent ou différent du gel audité."
    }
    $goWrapperSha256 = [string](
        Get-JsonProperty $go "chain_wrapper_sha256"
    )
    $actualWrapperSha256 = (
        Get-FileHash -LiteralPath (Get-FullPath $PSCommandPath) -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    if ($goWrapperSha256 -ne $actualWrapperSha256) {
        throw "Le champ chain_wrapper_sha256 du GO Stage3 ne correspond pas à ce wrapper."
    }
    $approvedBy = [string](Get-JsonProperty $go "approved_by")
    if ([string]::IsNullOrWhiteSpace($approvedBy)) {
        throw "Le GO Stage3 doit identifier l'approbateur."
    }
    try {
        $approvedAt = [DateTimeOffset]::Parse(
            [string](Get-JsonProperty $go "approved_at_utc"),
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind
        )
    }
    catch {
        throw "Horodatage du GO Stage3 invalide."
    }
    Assert-SamePath -Observed ([string](Get-JsonProperty $go "campaign_root")) -Expected $CampaignRoot -Label "campaign_root"
    Assert-SamePath -Observed ([string](Get-JsonProperty $go "results_dir")) -Expected $ResultsDir -Label "results_dir"
    Assert-SamePath -Observed ([string](Get-JsonProperty $go "stage3_supervision_dir")) -Expected $Stage3SupervisionDir -Label "stage3_supervision_dir"
    Assert-SamePath -Observed ([string](Get-JsonProperty $go "final_html")) -Expected $FinalHtml -Label "final_html"
    return [ordered]@{
        approved_by = $approvedBy
        approved_at_utc = $approvedAt.ToUniversalTime().ToString("o")
        stage3_inventory_signature = $goInventorySignature
        chain_wrapper_sha256 = $goWrapperSha256
        go_file = Get-FullPath $Path
    }
}

function Wait-Stage3Go {
    $deadline = [DateTimeOffset]::UtcNow.AddHours($MaxWaitHours)
    while ($true) {
        if ([IO.File]::Exists((Get-FullPath $Stage3GoFile))) {
            return Read-AndValidateStage3Go -Path $Stage3GoFile
        }
        if ([DateTimeOffset]::UtcNow -ge $deadline) {
            throw "Délai d'attente du GO indépendant Stage3 dépassé."
        }
        Write-ChainStatus -Status "waiting_stage3_go" -BusinessStatus "waiting_stage3_go" -Message "Campagne finalisée ; attente de l'accord indépendant avant Stage3." -Step "stage3_go"
        Start-Sleep -Seconds $Stage3GoPollSeconds
    }
}

function Assert-OwnScheduledTask {
    Import-Module ScheduledTasks -ErrorAction Stop
    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop
    $actions = @($task.Actions)
    if ($actions.Count -ne 1) {
        throw "La tache doit avoir exactement une action."
    }
    $action = $actions[0]
    if (-not [string]::Equals(
        (Get-FullPath ([string]$action.Execute)),
        (Get-FullPath $PowerShellExecutable),
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "L'action unique doit utiliser l'executable PowerShell attendu."
    }
    $scriptPath = Get-FullPath $PSCommandPath
    $fileMatches = [Text.RegularExpressions.Regex]::Matches(
        [string]$action.Arguments,
        '(?i)(?:^|\s)-File\s+(?:"([^"]+)"|([^\s"]+))(?=\s|$)'
    )
    if ($fileMatches.Count -ne 1) {
        throw "L'action unique doit contenir un seul argument -File."
    }
    if ($fileMatches[0].Groups[1].Success) {
        $fileArgument = $fileMatches[0].Groups[1].Value
    }
    else {
        $fileArgument = $fileMatches[0].Groups[2].Value
    }
    if (-not [string]::Equals(
        (Get-FullPath $fileArgument),
        $scriptPath,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "L'argument -File ne pointe pas exactement vers ce wrapper."
    }
    $expectedTaskArguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
        $scriptPath + '"'
    if (-not [string]::Equals(
        ([string]$action.Arguments).Trim(),
        $expectedTaskArguments,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "L'action contient des options ou paramètres non autorisés."
    }
    $matchingActions = @(
        $task.Actions | Where-Object {
            -not [string]::IsNullOrWhiteSpace($_.Arguments) -and
            $_.Arguments.IndexOf(
                $scriptPath,
                [StringComparison]::OrdinalIgnoreCase
            ) -ge 0
        }
    )
    if ($matchingActions.Count -ne 1) {
        throw "La tâche indiquée ne pointe pas de façon unique vers ce wrapper."
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
        $enabledText,
        "False",
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "La définition de la tâche reste activée après la demande de désactivation."
    }
    return [ordered]@{
        definition_enabled = $false
        observed_runtime_state = [string]$after.State
        running_state_accepted = ([string]$after.State -eq "Running")
    }
}

function Get-Stage3PathArguments {
    return @(
        "--repo", (Get-FullPath $Repo),
        "--v7-plan-dir", (Get-FullPath $V7PlanDir),
        "--v7-run-dir", (Get-FullPath $V7RunDir),
        "--trace-package-dir", (Get-FullPath $TracePackageDir),
        "--bridge-json", (Get-FullPath $BridgeJson),
        "--campaign-root", (Get-FullPath $CampaignRoot),
        "--results-dir", (Get-FullPath $ResultsDir),
        "--stage1-supervision-dir", (Get-FullPath $CampaignRoot),
        "--observed-2025-dir", (Get-FullPath $Observed2025Dir),
        "--lot-replay-root", (Get-FullPath $LotReplayRoot),
        "--qualification-dir", (Get-FullPath $QualificationDir),
        "--action-replay-root", (Get-FullPath $ActionReplayRoot),
        "--curves-dir", (Get-FullPath $CurvesDir),
        "--registry-dir", (Get-FullPath $RegistryDir),
        "--final-html", (Get-FullPath $FinalHtml),
        "--supervision-dir", (Get-FullPath $Stage3SupervisionDir)
    )
}

$goPresent = [IO.File]::Exists((Get-FullPath $Stage3GoFile))
$goEvidence = $null
if ($ValidateOnly -and $goPresent) {
    $goEvidence = Read-AndValidateStage3Go -Path $Stage3GoFile
}

if ($ValidateOnly) {
    $validation = Assert-StaticInputs
    [ordered]@{
        schema_version = "$SchemaVersion.validation.v1"
        status = "valid"
        mode = "validate_only"
        launch_performed = $false
        scheduled_task_changed = $false
        filesystem_mutation_performed = $false
        stage3_go_present = $goPresent
        stage3_go = $goEvidence
        task_name = $TaskName
        task_path = $TaskPath
        expected_task_execute = Get-FullPath $PowerShellExecutable
        expected_task_arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
            (Get-FullPath $PSCommandPath) + '"'
        campaign_root = Get-FullPath $CampaignRoot
        results_dir = Get-FullPath $ResultsDir
        final_html = Get-FullPath $FinalHtml
        planned_steps = @(
            "01_supervisor",
            "02_finalizer_v8",
            "wait_independent_stage3_go",
            "03_stage3_v3_foreground",
            "04_validate_html",
            "disable_own_task_after_success"
        )
        validation = $validation
    } | ConvertTo-Json -Depth 12
    exit 0
}

# Runtime starts only after an external scheduled task has been explicitly armed.
# This wrapper never creates a task and disables only its verified own task.
[void](Assert-OwnScheduledTask)
[IO.Directory]::CreateDirectory((Get-FullPath $ChainSupervisionDir)) | Out-Null
$lockPath = [IO.Path]::Combine(
    (Get-FullPath $ChainSupervisionDir),
    ".chain.lock"
)
try {
    $chainLock = [IO.File]::Open(
        $lockPath,
        [IO.FileMode]::OpenOrCreate,
        [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None
    )
}
catch {
    throw "Une autre chaîne V8-v2 vers Stage3 V3 détient déjà le verrou."
}

$manualHoldPath = [IO.Path]::Combine(
    (Get-FullPath $ChainSupervisionDir),
    "manual_intervention_required.json"
)
if ([IO.File]::Exists($manualHoldPath)) {
    Write-ChainStatus -Status "manual_intervention_required" -BusinessStatus "manual_intervention_required" -Message "Intervention manuelle requise ; aucune relance lourde automatique." -Step "manual_hold" -Details @{
        manual_hold = $manualHoldPath
        scheduled_task_disabled = $false
    }
    $chainLock.Dispose()
    exit 5
}

$failure = $null
$completed = $false
$terminalDetails = [ordered]@{}
try {
    Start-ChainKeepAwake
    $validation = Assert-StaticInputs
    $overlayPath = [IO.Path]::Combine(
        (Get-FullPath $ResultsDir),
        "campaign_validation_v8.json"
    )
    if (-not [IO.File]::Exists($overlayPath)) {
        Write-ChainStatus -Status "waiting_orphans" -BusinessStatus "waiting_orphans" -Message "Attente sécurisée des calculs V8-v2 existants." -Step "01_supervisor"
        $supervisorArguments = @(
            "-m",
            "etudecas.prototypes.scan_2027_risk_control.supervise_supplier_operating_point_full_campaign_v8_v2",
            "--repo", (Get-FullPath $Repo),
            "--campaign-root", (Get-FullPath $CampaignRoot),
            "--runner", (Get-FullPath $CampaignRunner),
            "--python", (Get-FullPath $Python),
            "--supervision-dir", (Get-FullPath $RecoverySupervisionDir),
            "--process-poll-seconds", [string]$ProcessPollSeconds,
            "--max-wait-hours", [string]$MaxWaitHours,
            "--parallel-shards", "2",
            "--workers-per-shard", "2",
            "--launcher-poll-seconds", "5"
        )
        $supervisorLog = Invoke-LoggedPythonStep -Step "01_supervisor" -Arguments $supervisorArguments
    }
    else {
        Write-SkippedStepLogs -Step "01_supervisor" -Reason "La surcouche V8 existe; le finalizer va la revalider."
        $supervisorLog = [ordered]@{
            skipped = $true
            reason = "existing_v8_overlay_revalidated_by_finalizer"
        }
    }

    $preFinalizerValidation = Assert-StaticInputs
    Write-ChainStatus -Status "finalizing_campaign" -BusinessStatus "finalizing_campaign" -Message "Validation et finalisation des résultats V8-v2." -Step "02_finalizer_v8" -Details @{
        supervisor = $supervisorLog
        source_validation = $preFinalizerValidation
    }
    $finalizerArguments = @(
        "-m",
        "etudecas.prototypes.scan_2027_risk_control.finalize_supplier_operating_point_full_campaign_v8_compat",
        "--campaign-root", (Get-FullPath $CampaignRoot),
        "--output-dir", (Get-FullPath $ResultsDir)
    )
    $finalizerLog = Invoke-LoggedPythonStep -Step "02_finalizer_v8" -Arguments $finalizerArguments
    if (-not [IO.File]::Exists($overlayPath)) {
        throw "Le finalizer n'a pas produit la surcouche campaign_validation_v8.json."
    }

    $goEvidence = Wait-Stage3Go
    $preStage3Validation = Assert-StaticInputs
    if (
        $preStage3Validation.stage3_inventory_signature -ne
        $goEvidence.stage3_inventory_signature
    ) {
        throw "L'inventaire Stage3 a dérivé entre le GO indépendant et l'exécution."
    }
    $htmlManifest = (Get-FullPath $FinalHtml) + ".manifest.json"
    $htmlExistsBeforeStage3 = [IO.File]::Exists((Get-FullPath $FinalHtml))
    $manifestExistsBeforeStage3 = [IO.File]::Exists($htmlManifest)
    if ($manifestExistsBeforeStage3 -and -not $htmlExistsBeforeStage3) {
        throw "[MANUAL_INTERVENTION_REQUIRED] Manifeste HTML orphelin ; aucun écrasement ou suppression automatique autorisé."
    }
    $stage3DeliveryArguments = @(
        "-m",
        "etudecas.prototypes.scan_2027_risk_control.supplier_v8_stage3_delivery"
    )
    $stage3DeliveryArguments += Get-Stage3PathArguments
    $existingHtmlValidated = $false
    $existingHtmlValidationError = ""
    if ($htmlExistsBeforeStage3 -and $manifestExistsBeforeStage3) {
        Write-ChainStatus -Status "checking_existing_html" -BusinessStatus "validating_html" -Message "Validation de la paire HTML/manifeste existante avant toute décision de reprise." -Step "03_existing_html_validation"
        try {
            $existingHtmlValidationLog = Invoke-LoggedPythonStep -Step "03_existing_html_validation" -Arguments $stage3DeliveryArguments
            $existingHtmlValidated = $true
        }
        catch {
            $existingHtmlValidationError = $_.Exception.Message
        }
    }
    if ($existingHtmlValidated) {
        Write-SkippedStepLogs -Step "03_stage3_v3_foreground" -Reason "Le HTML et son manifeste existent; validation intégrale à l'étape suivante."
        $stage3Log = [ordered]@{
            skipped = $true
            reason = "existing_html_and_manifest_revalidated"
            preflight_validation = $existingHtmlValidationLog
        }
    }
    else {
        Write-ChainStatus -Status "running_stage3" -BusinessStatus "running_stage3" -Message "Accord Stage3 reçu ; construction des résultats aval V3." -Step "03_stage3_v3_foreground" -Details @{ stage3_go = $goEvidence }
        $stage3Arguments = @(
            "-m",
            "etudecas.prototypes.scan_2027_risk_control.supplier_v8_stage3_watcher"
        )
        $stage3Arguments += Get-Stage3PathArguments
        $stage3Arguments += @(
            "--poll-seconds", "60",
            "--max-wait-hours", [string]$MaxWaitHours,
            "--startup-timeout-seconds", "600"
        )
        try {
            $stage3Log = Invoke-LoggedPythonStep -Step "03_stage3_v3_foreground" -Arguments $stage3Arguments
        }
        catch {
            if ($htmlExistsBeforeStage3 -or $manifestExistsBeforeStage3) {
                throw "[MANUAL_INTERVENTION_REQUIRED] Artefact HTML existant non réparable sous contrat immuable. Préflight: $existingHtmlValidationError ; reprise: $($_.Exception.Message)"
            }
            throw
        }
    }

    if (
        -not [IO.File]::Exists((Get-FullPath $FinalHtml)) -or
        -not [IO.File]::Exists($htmlManifest)
    ) {
        throw "Stage3 n'a pas produit le HTML autonome et son manifeste."
    }
    $preHtmlValidation = Assert-StaticInputs
    if (
        $preHtmlValidation.stage3_inventory_signature -ne
        $goEvidence.stage3_inventory_signature
    ) {
        throw "L'inventaire Stage3 a dérivé avant la validation finale du HTML."
    }
    Write-ChainStatus -Status "validating_html" -BusinessStatus "validating_html" -Message "Validation reproductible du HTML autonome et de ses preuves." -Step "04_validate_html"
    $htmlValidationLog = Invoke-LoggedPythonStep -Step "04_validate_html" -Arguments $stage3DeliveryArguments

    Write-ChainStatus -Status "validated_before_task_disable" -BusinessStatus "validated_html" -Message "HTML validé ; désactivation de cette tâche uniquement maintenant." -Step "disable_own_task"
    $finalHtmlSha256 = (
        Get-FileHash -LiteralPath (Get-FullPath $FinalHtml) -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    $terminalDetails = [ordered]@{
        supervisor = $supervisorLog
        finalizer = $finalizerLog
        stage3 = $stage3Log
        html_validation = $htmlValidationLog
        stage3_go = $goEvidence
        final_html_sha256 = $finalHtmlSha256
        scheduled_task_disabled = $true
    }
    $taskDisableEvidence = Disable-OwnScheduledTask
    $terminalDetails["task_disable"] = $taskDisableEvidence
    $completed = $true
}
catch {
    $failure = $_
}
finally {
    Stop-ChainKeepAwake
    try {
        if ($completed) {
            Write-ChainStatus -Status "complete" -BusinessStatus "complete" -Message "Chaîne terminée, HTML validé et tâche désactivée." -Step "complete" -Details $terminalDetails
        }
        else {
            $manualIntervention = (
                $null -ne $failure -and
                $failure.Exception.Message.StartsWith(
                    "[MANUAL_INTERVENTION_REQUIRED]",
                    [StringComparison]::Ordinal
                )
            )
            if ($manualIntervention) {
                if (-not [IO.File]::Exists($manualHoldPath)) {
                    Write-JsonAtomic -Path $manualHoldPath -Payload ([ordered]@{
                        schema_version = "$SchemaVersion.manual_intervention.v1"
                        status = "manual_intervention_required"
                        created_at_utc = Get-UtcTimestamp
                        reason = $failure.Exception.Message
                        final_html = Get-FullPath $FinalHtml
                        html_manifest = (Get-FullPath $FinalHtml) + ".manifest.json"
                        automatic_overwrite_or_delete = $false
                    })
                }
                Write-ChainStatus -Status "manual_intervention_required" -BusinessStatus "manual_intervention_required" -Message "Artefact final immuable incomplet ou divergent ; intervention manuelle requise." -Step "manual_intervention" -Details @{
                    error = [ordered]@{
                        type = $failure.Exception.GetType().FullName
                        message = $failure.Exception.Message
                    }
                    manual_hold = $manualHoldPath
                    scheduled_task_disabled = $false
                }
            }
            else {
            Write-ChainStatus -Status "failed" -BusinessStatus "failed" -Message "Chaîne arrêtée en erreur ; aucune désactivation par le chemin de succès." -Step "failed" -Details @{
                error = [ordered]@{
                    type = $failure.Exception.GetType().FullName
                    message = $failure.Exception.Message
                }
                scheduled_task_disabled = $false
            }
            }
        }
    }
    finally {
        $chainLock.Dispose()
    }
}

if ($null -ne $failure) {
    throw $failure
}
exit 0
