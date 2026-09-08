[CmdletBinding()]
param(
    [switch]$ConfirmerArret,
    [string]$ControlRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_autonomous_runs"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedLauncher = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "LANCER_TRANCHE_A_SANS_CODEX.ps1"))

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $parent = Split-Path -Parent $Path
    $temporary = Join-Path $parent (([IO.Path]::GetFileName($Path)) + ".tmp." + [Guid]::NewGuid().ToString("N"))
    try {
        $Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temporary -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $Path -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

if (-not (Test-Path -LiteralPath $ControlRoot -PathType Container)) {
    Write-Host "Aucune execution autonome a arreter."
    exit 0
}

$candidates = Get-ChildItem -LiteralPath $ControlRoot -Filter launcher_metadata.json -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTimeUtc -Descending
$active = $null
foreach ($candidate in $candidates) {
    try {
        $metadata = Get-Content -Raw -LiteralPath $candidate.FullName | ConvertFrom-Json
        $pidValue = [int]$metadata.controller_pid
        $process = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $pidValue) -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            $active = [pscustomobject]@{
                Metadata = $metadata
                MetadataPath = $candidate.FullName
                RunDirectory = $candidate.Directory.FullName
                Process = $process
            }
            break
        }
    }
    catch {
        continue
    }
}

if ($null -eq $active) {
    Write-Host "Aucun processus autonome actif. Rien n'a ete modifie."
    exit 0
}

$commandLine = [string]$active.Process.CommandLine
$controllerPid = [int]$active.Process.ProcessId
if ($commandLine -notmatch [Regex]::Escape($ExpectedLauncher) -or $commandLine -notmatch "-ModeInterne") {
    throw "Arret refuse : le PID enregistre ne correspond pas au controleur autonome attendu."
}

Write-Host ("Processus autonome trouve : PID " + $controllerPid)
Write-Host ("Dossier : " + $active.RunDirectory)
if (-not $ConfirmerArret) {
    Write-Host "AUCUN ARRET EFFECTUE."
    Write-Host ("Pour interrompre uniquement cet arbre de processus : powershell -ExecutionPolicy Bypass -File `"" + $PSCommandPath + "`" -ConfirmerArret")
    exit 0
}

Write-JsonAtomic -Path (Join-Path $active.RunDirectory "stop_request.json") -Value ([ordered]@{
    requested_at_utc = [DateTime]::UtcNow.ToString("o")
    controller_pid = $controllerPid
    scope = "exact_autonomous_process_tree_only"
    files_deleted = $false
})

# taskkill /T cible uniquement le controleur verifie et ses enfants Python.
# Aucun fichier de campagne n'est supprime. Les preuves partielles restent sur
# disque et devront repasser le controle de reprise avant un prochain lancement.
$taskkill = Start-Process -FilePath "taskkill.exe" -ArgumentList @("/PID", $controllerPid.ToString(), "/T") -WindowStyle Hidden -Wait -PassThru
Start-Sleep -Milliseconds 750
$stillAlive = Get-Process -Id $controllerPid -ErrorAction SilentlyContinue
if ($null -ne $stillAlive) {
    throw "Le processus n'a pas accepte l'interruption. Aucun arret force supplementaire n'a ete applique."
}

Write-JsonAtomic -Path (Join-Path $active.RunDirectory "stopped.json") -Value ([ordered]@{
    stopped_at_utc = [DateTime]::UtcNow.ToString("o")
    controller_pid = $controllerPid
    taskkill_exit_code = $taskkill.ExitCode
    files_deleted = $false
    next_step = "Relancer d'abord le controle a blanc; il validera les resultats reutilisables."
})
Write-Host "Execution locale interrompue. Aucun fichier de resultat n'a ete supprime."
Write-Host "La prochaine reprise revalidera les elements partiels avant de les reutiliser."

