[CmdletBinding()]
param(
    [switch]$ConfirmerLancement,
    [switch]$SansSuivi,
    [ValidateRange(10, 300)][int]$RafraichissementSecondes = 30,
    [ValidateSet("A", "B")][string]$Tranche = "A",
    [switch]$ModeInterne,
    [string]$RunDirectory = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = "C:\dev\lca-simu-pr40"
$CampaignRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
$ControlRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_autonomous_runs"
$ExpectedSignature = "fae9219a5cc59bcf9efd07b50b19009a1c7fd36b68fa81774c976b40a68c3598"
$Module = "etudecas.prototypes.scan_2027_risk_control.orchestrate_supplier_v8_bounded_tranche"
$OperatingPoint = "op_100"
if ($Tranche -eq "A") {
    $SimulationCount = 20
    $ShardIds = @("op_100__seed_block_03", "op_100__seed_block_04")
    $IndicativeRuntimeSeconds = 25200
}
else {
    $SimulationCount = 30
    $ShardIds = @("op_100__seed_block_05", "op_100__seed_block_06")
    $IndicativeRuntimeSeconds = 32400
}
$TrancheLower = $Tranche.ToLowerInvariant()

function Get-UtcNow {
    return [DateTime]::UtcNow.ToString("o")
}

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $temporary = Join-Path $parent (([IO.Path]::GetFileName($Path)) + ".tmp." + [Guid]::NewGuid().ToString("N"))
    try {
        $Value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temporary -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Get-PythonCommand {
    $candidate = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $candidate) {
        $candidate = Get-Command python -ErrorAction SilentlyContinue
    }
    if ($null -eq $candidate) {
        throw "Python est introuvable dans PATH. Aucun calcul n'a ete lance."
    }
    return $candidate.Source
}

function Get-RequestArguments {
    param([Parameter(Mandatory = $true)][string]$CheckpointOutputDir)
    return @(
        "-m", $Module,
        "--campaign-root", $CampaignRoot,
        "--operating-point-id", $OperatingPoint,
        "--simulation-count", $SimulationCount.ToString(),
        "--shard-id", $ShardIds[0],
        "--shard-id", $ShardIds[1],
        "--checkpoint-output-dir", $CheckpointOutputDir,
        "--expected-campaign-signature", $ExpectedSignature
    )
}

function Assert-NoActiveAutonomousRun {
    if (-not (Test-Path -LiteralPath $ControlRoot -PathType Container)) {
        return
    }
    foreach ($metadataPath in Get-ChildItem -LiteralPath $ControlRoot -Filter launcher_metadata.json -Recurse -File -ErrorAction SilentlyContinue) {
        try {
            $metadata = Get-Content -Raw -LiteralPath $metadataPath.FullName | ConvertFrom-Json
            $pidValue = [int]$metadata.controller_pid
            if (Get-Process -Id $pidValue -ErrorAction SilentlyContinue) {
                throw "Une execution autonome est deja active (PID $pidValue). Aucun second lancement."
            }
        }
        catch [System.Management.Automation.RuntimeException] {
            throw
        }
        catch {
            # Un ancien dossier incomplet ne doit pas masquer l'inspection Python.
        }
    }
}

function Invoke-PreflightWithTimeout {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][object[]]$Arguments,
        [int]$TimeoutSeconds = 300
    )
    $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $tempDir = Join-Path $tempBase ("etudecas_v8_preflight_" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tempDir -ErrorAction Stop | Out-Null
    $stdoutPath = Join-Path $tempDir "stdout.log"
    $stderrPath = Join-Path $tempDir "stderr.log"
    $process = $null
    try {
        $process = Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Start-Process -FilePath "taskkill.exe" -ArgumentList @("/PID", $process.Id.ToString(), "/T") -WindowStyle Hidden -Wait | Out-Null
            throw "Le controle a blanc a depasse $TimeoutSeconds secondes et a ete interrompu. Aucun calcul n'a ete lance."
        }
        # Avec Windows PowerShell 5.1, l'appel temporise peut laisser la
        # propriete ExitCode non rafraichie, meme si le processus est fini.
        $process.WaitForExit()
        $process.Refresh()
        $preflightExitCode = [int]$process.ExitCode
        return [pscustomobject]@{
            ExitCode = $preflightExitCode
            Stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -Raw -LiteralPath $stdoutPath } else { "" }
            Stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -Raw -LiteralPath $stderrPath } else { "" }
        }
    }
    finally {
        foreach ($path in @($stdoutPath, $stderrPath)) {
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                Remove-Item -LiteralPath $path -Force
            }
        }
        $resolvedTempDir = [IO.Path]::GetFullPath($tempDir)
        if ($resolvedTempDir.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase) -and
            (Test-Path -LiteralPath $resolvedTempDir -PathType Container)) {
            Remove-Item -LiteralPath $resolvedTempDir -Force
        }
    }
}

function Invoke-Worker {
    if ([string]::IsNullOrWhiteSpace($RunDirectory)) {
        throw "Mode interne refuse : dossier de controle absent."
    }
    $resolvedRun = [IO.Path]::GetFullPath($RunDirectory)
    $resolvedControl = [IO.Path]::GetFullPath($ControlRoot)
    if (-not $resolvedRun.StartsWith($resolvedControl + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Mode interne refuse : dossier de controle hors perimetre."
    }
    $requestPath = Join-Path $resolvedRun "request.json"
    if (-not (Test-Path -LiteralPath $requestPath -PathType Leaf)) {
        throw "Mode interne refuse : requete absente."
    }
    $request = Get-Content -Raw -LiteralPath $requestPath | ConvertFrom-Json
    if ($request.campaign_signature -ne $ExpectedSignature -or
        $request.campaign_root -ne $CampaignRoot -or
        $request.operating_point_id -ne $OperatingPoint -or
        [int]$request.simulation_count -ne $SimulationCount -or
        $request.shard_ids.Count -ne 2 -or
        $request.shard_ids[0] -ne $ShardIds[0] -or
        $request.shard_ids[1] -ne $ShardIds[1]) {
        throw ("Mode interne refuse : requete differente de la tranche " + $Tranche + " figee.")
    }

    $statePath = Join-Path $resolvedRun "state.json"
    $stdoutPath = Join-Path $resolvedRun "simulation_stdout.log"
    $stderrPath = Join-Path $resolvedRun "simulation_stderr.log"
    $python = Get-PythonCommand
    $arguments = Get-RequestArguments -CheckpointOutputDir ([string]$request.checkpoint_output_dir)
    $arguments += "--execute"
    $child = $null
    try {
        Write-JsonAtomic -Path $statePath -Value ([ordered]@{
            status = "starting"
            updated_at_utc = Get-UtcNow
            controller_pid = $PID
            child_pid = $null
            ai_api_called = $false
            message_fr = "Le processus Windows local prepare la tranche $Tranche."
        })
        $child = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
        Write-JsonAtomic -Path $statePath -Value ([ordered]@{
            status = "running"
            updated_at_utc = Get-UtcNow
            controller_pid = $PID
            child_pid = $child.Id
            ai_api_called = $false
            message_fr = "Calcul Python local en cours. Aucun appel OpenAI/Codex."
        })
        $child.WaitForExit()
        $child.Refresh()
        $exitCode = [int]$child.ExitCode
        $resultPayload = $null
        try {
            $resultPayload = Get-Content -Raw -LiteralPath $stdoutPath | ConvertFrom-Json
        }
        catch {
            $resultPayload = $null
        }
        $validatedEntrypoint = if ($null -eq $resultPayload) { "" } else { [string]$resultPayload.entrypoint }
        $scientificSuccess = (
            $exitCode -eq 0 -and
            $null -ne $resultPayload -and
            [string]$resultPayload.status -eq "checkpoint_created_and_validated" -and
            -not [string]::IsNullOrWhiteSpace($validatedEntrypoint) -and
            (Test-Path -LiteralPath $validatedEntrypoint -PathType Leaf)
        )
        $effectiveExitCode = if ($scientificSuccess) { 0 } else { 98 }
        $status = if ($scientificSuccess) { "complete" } else { "failed" }
        $message = if ($scientificSuccess) {
            "Tranche $Tranche terminee et bilan $SimulationCount/30 construit."
        }
        else {
            "Tranche non validee ou bilan absent. Consulter les journaux."
        }
        Write-JsonAtomic -Path $statePath -Value ([ordered]@{
            status = $status
            updated_at_utc = Get-UtcNow
            controller_pid = $PID
            child_pid = $child.Id
            exit_code = $effectiveExitCode
            process_exit_code = $exitCode
            validated_result_status = if ($null -eq $resultPayload) { "unreadable" } else { [string]$resultPayload.status }
            validated_entrypoint = $validatedEntrypoint
            ai_api_called = $false
            message_fr = $message
        })
        exit $effectiveExitCode
    }
    catch {
        Write-JsonAtomic -Path $statePath -Value ([ordered]@{
            status = "failed"
            updated_at_utc = Get-UtcNow
            controller_pid = $PID
            child_pid = if ($null -eq $child) { $null } else { $child.Id }
            exit_code = 99
            ai_api_called = $false
            message_fr = $_.Exception.Message
        })
        exit 99
    }
}

if ($ModeInterne) {
    Invoke-Worker
    exit 0
}

Set-Location -LiteralPath $RepoRoot
$python = Get-PythonCommand
if (-not (Test-Path -LiteralPath $CampaignRoot -PathType Container)) {
    throw "Campagne source introuvable. Aucun calcul n'a ete lance."
}
Assert-NoActiveAutonomousRun

$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$candidateCheckpoint = Join-Path (Split-Path -Parent $CampaignRoot) ("supplier_v8_op100_checkpoint_" + $SimulationCount + "_autonome_" + $stamp)
$preflightArguments = Get-RequestArguments -CheckpointOutputDir $candidateCheckpoint

Write-Host ("Controle de securite de la tranche " + $Tranche + " (aucun calcul)...")
$preflight = Invoke-PreflightWithTimeout -Python $python -Arguments $preflightArguments
if ($preflight.ExitCode -ne 0) {
    if (-not [string]::IsNullOrWhiteSpace($preflight.Stdout)) { Write-Host $preflight.Stdout }
    if (-not [string]::IsNullOrWhiteSpace($preflight.Stderr)) { Write-Host $preflight.Stderr }
    throw "Controle refuse. Aucun calcul n'a ete lance."
}

if (-not $ConfirmerLancement) {
    Write-Host "CONTROLE OK - AUCUN CALCUL LANCE."
    Write-Host "Pour lancer en dehors de Codex :"
    Write-Host ("  powershell -ExecutionPolicy Bypass -File `"" + $PSCommandPath + "`" -ConfirmerLancement")
    exit 0
}

$runId = "tranche_" + $TrancheLower + "_" + $stamp + "_" + [Guid]::NewGuid().ToString("N").Substring(0, 8)
$runDir = Join-Path $ControlRoot $runId
New-Item -ItemType Directory -Path $runDir -ErrorAction Stop | Out-Null
$requestPath = Join-Path $runDir "request.json"
$initialProbeCompleted = 0
$initialFinalCompleted = 0
foreach ($shardId in $ShardIds) {
    $shardRoot = Join-Path $CampaignRoot ("shards\" + $shardId)
    $probePath = Join-Path $shardRoot "incident_probe_progress.json"
    $progressPath = Join-Path $shardRoot "progress.json"
    if (Test-Path -LiteralPath $probePath -PathType Leaf) {
        $initialProbeCompleted += [int](Get-Content -Raw -LiteralPath $probePath | ConvertFrom-Json).completed
    }
    if (Test-Path -LiteralPath $progressPath -PathType Leaf) {
        $initialFinalCompleted += [int](Get-Content -Raw -LiteralPath $progressPath | ConvertFrom-Json).completed_case_count
    }
}
Write-JsonAtomic -Path $requestPath -Value ([ordered]@{
    schema_version = "etudecas.supplier_v8.autonomous_run.v1"
    run_id = $runId
    tranche_id = $Tranche
    created_at_utc = Get-UtcNow
    repo_root = $RepoRoot
    campaign_root = $CampaignRoot
    campaign_signature = $ExpectedSignature
    operating_point_id = $OperatingPoint
    simulation_count = $SimulationCount
    shard_ids = $ShardIds
    checkpoint_output_dir = $candidateCheckpoint
    execution_engine = "local_python_only"
    openai_or_codex_api = $false
    progress_contract = [ordered]@{
        probe_work_total = 360
        final_case_work_total = 370
        work_total = 730
        initial_probe_work_completed = $initialProbeCompleted
        initial_final_case_work_completed = $initialFinalCompleted
        indicative_full_runtime_seconds = $IndicativeRuntimeSeconds
        interpretation = "Une unite de progression correspond a une preparation d'incident ou a un resultat finalise."
    }
})

$workerArguments = @(
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy", "Bypass",
    "-File", ('"{0}"' -f $PSCommandPath),
    "-Tranche", $Tranche,
    "-ModeInterne",
    "-RunDirectory", ('"{0}"' -f $runDir)
)
$controller = Start-Process -FilePath "powershell.exe" -ArgumentList $workerArguments -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru
Write-JsonAtomic -Path (Join-Path $runDir "launcher_metadata.json") -Value ([ordered]@{
    schema_version = "etudecas.supplier_v8.autonomous_launcher.v1"
    run_id = $runId
    launched_at_utc = Get-UtcNow
    controller_pid = $controller.Id
    launcher_script = $PSCommandPath
    campaign_root = $CampaignRoot
    checkpoint_output_dir = $candidateCheckpoint
})

Write-Host ("TRANCHE " + $Tranche + " LANCEE EN PROCESSUS WINDOWS LOCAL.")
Write-Host ("PID controleur : " + $controller.Id)
Write-Host ("Dossier de suivi : " + $runDir)
Write-Host "Vous pouvez fermer Codex : le calcul ne depend plus de cette conversation."
$statusScript = Join-Path $PSScriptRoot "VOIR_STATUT_CAMPAGNE.ps1"
Write-Host ("Statut : powershell -ExecutionPolicy Bypass -File `"" + $statusScript + "`"")

if (-not $SansSuivi) {
    Write-Host "Le suivi automatique va maintenant s'afficher dans cette fenetre."
    Write-Host "Ctrl+C ferme seulement l'affichage : le calcul autonome continue."
    Start-Sleep -Seconds 2
    while ($null -ne (Get-Process -Id $controller.Id -ErrorAction SilentlyContinue)) {
        Clear-Host
        & $statusScript
        Write-Host ""
        Write-Host ("Actualisation automatique toutes les " + $RafraichissementSecondes + " secondes.")
        Write-Host "Ctrl+C ferme seulement cet affichage; la simulation continue en arriere-plan."
        Start-Sleep -Seconds $RafraichissementSecondes
    }
    Clear-Host
    & $statusScript
    Write-Host ""
    Write-Host "Le processus autonome est termine. Le resultat final est affiche ci-dessus."
}
