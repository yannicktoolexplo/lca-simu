[CmdletBinding()]
param(
    [switch]$ConfirmerLancement,
    [switch]$SansSuivi,
    [ValidateRange(10, 300)][int]$RafraichissementSecondes = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$commonLauncher = Join-Path $PSScriptRoot "LANCER_TRANCHE_A_SANS_CODEX.ps1"
if (-not (Test-Path -LiteralPath $commonLauncher -PathType Leaf)) {
    throw "Lanceur commun introuvable. Aucun calcul n'a ete lance."
}

$parameters = @{
    Tranche = "B"
    RafraichissementSecondes = $RafraichissementSecondes
}
if ($ConfirmerLancement) { $parameters["ConfirmerLancement"] = $true }
if ($SansSuivi) { $parameters["SansSuivi"] = $true }

& $commonLauncher @parameters
if (-not $?) {
    exit 1
}
exit 0
