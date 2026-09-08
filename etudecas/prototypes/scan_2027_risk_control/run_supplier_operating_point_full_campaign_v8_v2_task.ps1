$ErrorActionPreference = "Stop"

$repo = "C:\dev\lca-simu-pr40"
$python = "C:\Users\yannick.martz\AppData\Local\Programs\Python\Python311\python.exe"
$campaignRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
$runner = "$repo\etudecas\prototypes\scan_2027_risk_control\supplier_operating_point_full_campaign_v8.py"

# Child runners are invoked by their absolute script path.  Keep the repository
# on PYTHONPATH so those children can import the etudecas package as well.
$env:PYTHONPATH = $repo
Set-Location -LiteralPath $repo

$campaignArgs = @(
    "-m",
    "etudecas.prototypes.scan_2027_risk_control.launch_supplier_operating_point_full_campaign_v8",
    "--campaign-root",
    $campaignRoot,
    "--runner",
    $runner,
    "--parallel-shards",
    "2",
    "--workers-per-shard",
    "2",
    "--poll-seconds",
    "5",
    "--detached-child"
)

& $python @campaignArgs
exit $LASTEXITCODE
