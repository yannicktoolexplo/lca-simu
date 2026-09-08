[CmdletBinding()]
param(
    [string]$ControlRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_autonomous_runs"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$CampaignRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
$ExpectedSignature = "fae9219a5cc59bcf9efd07b50b19009a1c7fd36b68fa81774c976b40a68c3598"
$ShardIds = @("op_100__seed_block_03", "op_100__seed_block_04")
$TrancheLabel = "A"

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    return Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
}

function Get-LatestRunDirectory {
    if (-not (Test-Path -LiteralPath $ControlRoot -PathType Container)) {
        return $null
    }
    return Get-ChildItem -LiteralPath $ControlRoot -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
}

function Format-Duration {
    param([double]$Seconds)
    if ($Seconds -lt 0) { $Seconds = 0 }
    $span = [TimeSpan]::FromSeconds($Seconds)
    if ($span.TotalHours -ge 1) {
        return ("{0} h {1:D2} min" -f [math]::Floor($span.TotalHours), $span.Minutes)
    }
    return ("{0} min" -f [math]::Ceiling($span.TotalMinutes))
}

function Format-ProgressBar {
    param([double]$Percent, [int]$Width = 30)
    $bounded = [math]::Max(0.0, [math]::Min(100.0, $Percent))
    $filled = [int][math]::Floor(($bounded / 100.0) * $Width)
    return ("[" + ("#" * $filled) + ("-" * ($Width - $filled)) + "]")
}

$latest = Get-LatestRunDirectory
if ($null -ne $latest) {
    $latestRequest = Read-JsonFile (Join-Path $latest.FullName "request.json")
    if ($null -ne $latestRequest -and @($latestRequest.shard_ids).Count -eq 2) {
        $ShardIds = @([string]$latestRequest.shard_ids[0], [string]$latestRequest.shard_ids[1])
        if ($null -ne $latestRequest.tranche_id) {
            $TrancheLabel = [string]$latestRequest.tranche_id
        }
        elseif ([int]$latestRequest.simulation_count -eq 30) {
            $TrancheLabel = "B"
        }
    }
}
Write-Host "ETAT DE LA CAMPAGNE FOURNISSEURS V8"
Write-Host "=================================="
if ($null -eq $latest) {
    $preflight = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -match "LANCER_TRANCHE_[AB]_SANS_CODEX\.ps1" -and
            $_.CommandLine -match "-ConfirmerLancement"
        } |
        Select-Object -First 1
    if ($null -ne $preflight) {
        Write-Host ("Controle initial en cours (PID " + [string]$preflight.ProcessId + ").")
        Write-Host "La simulation commencera seulement apres validation de ce controle."
    }
    else {
        Write-Host "Aucune execution autonome enregistree."
        Write-Host "La campagne n'est pas lancee par ces nouveaux scripts."
    }
}
else {
    $metadata = Read-JsonFile (Join-Path $latest.FullName "launcher_metadata.json")
    $state = Read-JsonFile (Join-Path $latest.FullName "state.json")
    $request = Read-JsonFile (Join-Path $latest.FullName "request.json")
    $controllerPid = if ($null -eq $metadata) { 0 } else { [int]$metadata.controller_pid }
    $controllerAlive = $controllerPid -gt 0 -and $null -ne (Get-Process -Id $controllerPid -ErrorAction SilentlyContinue)
    $reportedStatus = if ($null -eq $state) { "starting" } else { [string]$state.status }
    if (-not $controllerAlive -and $reportedStatus -in @("starting", "running")) {
        $reportedStatus = "interrupted_or_stale"
    }
    Write-Host ("Execution : " + $latest.Name)
    Write-Host ("Statut : " + $reportedStatus)
    Write-Host ("Processus local actif : " + $(if ($controllerAlive) { "OUI" } else { "NON" }))
    if ($null -ne $state -and $null -ne $state.message_fr) {
        Write-Host ("Message : " + [string]$state.message_fr)
    }
    if ($null -ne $request) {
        Write-Host ("Futur bilan : " + [string]$request.checkpoint_output_dir)
        $html = Get-ChildItem -LiteralPath ([string]$request.checkpoint_output_dir) -Filter *.html -File -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $html) {
            Write-Host ("HTML disponible : " + $html.FullName)
        }
    }
    Write-Host ("Dossier de suivi : " + $latest.FullName)
}

Write-Host ""
Write-Host "PROGRESSION DES DEUX BLOCS"
$probeCompletedTotal = 0
$probePlannedTotal = 0
$finalCompletedTotal = 0
$finalPlannedTotal = 0
foreach ($shardId in $ShardIds) {
    $shardRoot = Join-Path $CampaignRoot ("shards\" + $shardId)
    $progress = Read-JsonFile (Join-Path $shardRoot "progress.json")
    $probe = Read-JsonFile (Join-Path $shardRoot "incident_probe_progress.json")
    if ($null -eq $progress) {
        Write-Host ("- " + $shardId + " : aucun fichier de progression")
        continue
    }
    if ([string]$progress.campaign_signature -ne $ExpectedSignature) {
        Write-Host ("- " + $shardId + " : signature inattendue, lecture refusee")
        continue
    }
    $finalText = ([string]$progress.completed_case_count + "/" + [string]$progress.planned_case_count + " resultats finalises")
    $finalCompletedTotal += [int]$progress.completed_case_count
    $finalPlannedTotal += [int]$progress.planned_case_count
    $probeText = if ($null -eq $probe) {
        "preparations d'incident inconnues"
    }
    else {
        $probeCompletedTotal += [int]$probe.completed
        $probePlannedTotal += [int]$probe.planned
        ([string]$probe.completed + "/" + [string]$probe.planned + " preparations d'incident reutilisables")
    }
    $freshness = "mise a jour " + [string]$progress.updated_at_utc
    Write-Host ("- " + $shardId + " : " + $finalText + "; " + $probeText + "; " + $freshness)
}

$workCompleted = $probeCompletedTotal + $finalCompletedTotal
$workTotal = $probePlannedTotal + $finalPlannedTotal
if ($workTotal -gt 0) {
    $percent = 100.0 * $workCompleted / $workTotal
    Write-Host ""
    Write-Host ("AVANCEMENT GLOBAL DE LA TRANCHE " + $TrancheLabel)
    Write-Host ((Format-ProgressBar -Percent $percent) + (" {0:N1} %" -f $percent))
    Write-Host ("Travail valide : " + $workCompleted + "/" + $workTotal + " etapes")

    $controllerIsActive = $false
    $launchTime = $null
    $initialCompleted = 36
    $indicativeRuntime = 25200.0
    if ($null -ne $latest) {
        $metadataForEta = Read-JsonFile (Join-Path $latest.FullName "launcher_metadata.json")
        $requestForEta = Read-JsonFile (Join-Path $latest.FullName "request.json")
        if ($null -ne $metadataForEta) {
            $etaPid = [int]$metadataForEta.controller_pid
            $controllerIsActive = $etaPid -gt 0 -and $null -ne (Get-Process -Id $etaPid -ErrorAction SilentlyContinue)
            try { $launchTime = [DateTimeOffset]::Parse([string]$metadataForEta.launched_at_utc) } catch { $launchTime = $null }
        }
        if ($null -ne $requestForEta -and $null -ne $requestForEta.progress_contract) {
            $contract = $requestForEta.progress_contract
            $initialCompleted = [int]$contract.initial_probe_work_completed + [int]$contract.initial_final_case_work_completed
            $indicativeRuntime = [double]$contract.indicative_full_runtime_seconds
        }
    }

    if ($controllerIsActive -and $null -ne $launchTime -and $percent -lt 100.0) {
        $elapsed = ([DateTimeOffset]::Now - $launchTime).TotalSeconds
        $newlyCompleted = [math]::Max(0, $workCompleted - $initialCompleted)
        if ($newlyCompleted -ge 4 -and $elapsed -ge 60) {
            $secondsPerStep = $elapsed / $newlyCompleted
            $remainingSeconds = ($workTotal - $workCompleted) * $secondsPerStep
            $basis = "rythme mesure depuis le lancement"
        }
        else {
            $remainingAtLaunch = [math]::Max(1, $workTotal - $initialCompleted)
            $remainingSeconds = [math]::Max(300.0, $indicativeRuntime * $remainingAtLaunch / $workTotal)
            $basis = "duree observee lors de la tranche precedente"
        }
        $estimatedEnd = [DateTimeOffset]::Now.AddSeconds($remainingSeconds).ToLocalTime()
        Write-Host ("Temps restant estime : " + (Format-Duration -Seconds $remainingSeconds))
        Write-Host ("Fin estimee : " + $estimatedEnd.ToString("dd/MM/yyyy HH:mm"))
        Write-Host ("Base de l'estimation : " + $basis + ".")
    }
    elseif ($percent -ge 100.0) {
        Write-Host "Temps restant estime : termine."
    }
    else {
        $remainingRatio = [math]::Max(0.0, 1.0 - ($percent / 100.0))
        Write-Host ("Duree indicative si relancee maintenant : " + (Format-Duration -Seconds ($indicativeRuntime * $remainingRatio)))
        Write-Host "Aucune heure de fin : le processus autonome n'est pas actif."
    }
    Write-Host "Cette estimation reste indicative : les incidents ne prennent pas tous le meme temps de calcul."
}

if ($null -ne $latest) {
    $stdoutPath = Join-Path $latest.FullName "simulation_stdout.log"
    $stderrPath = Join-Path $latest.FullName "simulation_stderr.log"
    if (Test-Path -LiteralPath $stderrPath -PathType Leaf) {
        $errors = @(Get-Content -LiteralPath $stderrPath -Tail 12 -ErrorAction SilentlyContinue)
        if ($errors.Count -gt 0) {
            Write-Host ""
            Write-Host "DERNIERES LIGNES D'ERREUR"
            $errors | ForEach-Object { Write-Host $_ }
        }
    }
    if (Test-Path -LiteralPath $stdoutPath -PathType Leaf) {
        Write-Host ""
        Write-Host "DERNIERES LIGNES DU JOURNAL"
        Get-Content -LiteralPath $stdoutPath -Tail 12 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
    }
}
