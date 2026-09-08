[CmdletBinding()]
param(
    [string]$Repo = "C:\dev\lca-simu-pr40",
    [string]$GoFile = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_go_20260906_v4.json",
    [string]$SupervisionDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_v3_to_v4_handoff_guardian_supervision_20260906_v1",
    [string]$PowerShellExecutable = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe",
    [int]$LegacyWrapperPid = 26160,
    [int]$LegacySupervisorPid = 34588,
    [ValidateRange(1, 60)]
    [int]$PollSeconds = 30,
    [ValidateRange(5, 600)]
    [int]$ConfirmationSeconds = 120,
    [double]$MaxWaitHours = 240,
    [string]$ValidationFixtureJson = "",
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$SchemaVersion = "etudecas.supplier_v8_v3_to_v4_handoff_guardian.v1"
$TaskPath = "\"
$TargetTaskName = "Codex-Supplier-V8-V2-To-Stage3-V3"
$GuardianTaskName = "Codex-Supplier-V8-V3-To-V4-Guardian-V1"
$ExpectedRepo = "C:\dev\lca-simu-pr40"
$ExpectedGoFile = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_stage3_go_20260906_v4.json"
$ExpectedSupervisionDir = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_v3_to_v4_handoff_guardian_supervision_20260906_v1"
$ExpectedPowerShellExecutable = "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe"
$ExpectedSupervisorExecutable = "C:\Users\yannick.martz\AppData\Local\Programs\Python\Python311\python.exe"
$ExpectedLegacyWrapperCreatedUtc = "2026-09-06T11:02:42.5987970Z"
$ExpectedLegacySupervisorCreatedUtc = "2026-09-06T11:03:07.0281980Z"
$V3RelativePath = "etudecas\prototypes\scan_2027_risk_control\run_supplier_v8_v2_to_stage3_v3_chain_task.ps1"
$V4RelativePath = "etudecas\prototypes\scan_2027_risk_control\run_supplier_v8_v2_to_stage3_v4_chain_task.ps1"
$ExpectedV3Sha256 = "451e3ab5e7a5f737db6d9375242ca88a179aff65aa2db39bd7ced63c217529b6"
$ExpectedV4Sha256 = "b322e47b8820e7cc714ab9436555bc4607b193e11c397a6cf7dfbc76cd6ef642"
$ExpectedGoSha256 = "255e5bb6d8f6be3473ab4622ea0d5faa9ff1529b65d497f405dc4975c8332a93"
$ExpectedStage3InventorySignature = "d56761c3cdd704ec9d31bb2b452ee5dea25e9cdcf1e87c67d787a09e20b5a442"
$ExpectedTargetWorkingDirectory = "C:\dev\lca-simu-pr40"
$CampaignRoot = "C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
$ExpectedTargetArguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "C:\dev\lca-simu-pr40\etudecas\prototypes\scan_2027_risk_control\run_supplier_v8_v2_to_stage3_v4_chain_task.ps1"'
$ExpectedLegacyWrapperCommandLine = '"C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "C:\dev\lca-simu-pr40\etudecas\prototypes\scan_2027_risk_control\run_supplier_v8_v2_to_stage3_v3_chain_task.ps1"'
$ExpectedLegacySupervisorCommandLine = '"C:\Users\yannick.martz\AppData\Local\Programs\Python\Python311\python.exe" -m etudecas.prototypes.scan_2027_risk_control.supervise_supplier_operating_point_full_campaign_v8_v2 --repo C:\dev\lca-simu-pr40 --campaign-root C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2 --runner C:\dev\lca-simu-pr40\etudecas\prototypes\scan_2027_risk_control\supplier_operating_point_full_campaign_v8.py --python C:\Users\yannick.martz\AppData\Local\Programs\Python\Python311\python.exe --supervision-dir C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_operating_point_full_campaign_v8_v2_recovery_supervision_20260906_v1 --process-poll-seconds 30 --max-wait-hours 240 --parallel-shards 2 --workers-per-shard 2 --launcher-poll-seconds 5'
$ExpectedTargetV4ProcessCommandLine = '"C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "C:\dev\lca-simu-pr40\etudecas\prototypes\scan_2027_risk_control\run_supplier_v8_v2_to_stage3_v4_chain_task.ps1"'

$script:WakeActive = $false
$script:WakeStartedAtUtc = ""
$script:WakeStoppedAtUtc = ""
$script:TargetStartCalled = $false

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
    $leftPath = (Get-FullPath $Left).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $rightPath = (Get-FullPath $Right).TrimEnd([IO.Path]::DirectorySeparatorChar)
    return (
        [string]::Equals($leftPath, $rightPath, [StringComparison]::OrdinalIgnoreCase) -or
        $leftPath.StartsWith(
            $rightPath + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        $rightPath.StartsWith(
            $leftPath + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase
        )
    )
}

function Normalize-CommandLine {
    param([Parameter(Mandatory = $true)][string]$CommandLine)
    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        throw "CommandLine absent; identite du processus impossible a etablir."
    }
    return (($CommandLine.Trim() -replace '\s+', ' ').ToLowerInvariant())
}

function Assert-ExactCommandLine {
    param(
        [Parameter(Mandatory = $true)][string]$Observed,
        [Parameter(Mandatory = $true)][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Label
    )
    if ((Normalize-CommandLine $Observed) -ne (Normalize-CommandLine $Expected)) {
        throw "Identite CommandLine inattendue pour $Label."
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

function Assert-StaticInputs {
    $resolvedRepo = Get-FullPath $Repo
    if (-not [IO.Directory]::Exists($resolvedRepo)) {
        throw "Depot absent : $resolvedRepo"
    }
    if (-not [IO.File]::Exists((Get-FullPath $PowerShellExecutable))) {
        throw "PowerShell absent : $PowerShellExecutable"
    }
    if ($LegacyWrapperPid -ne 26160 -or $LegacySupervisorPid -ne 34588) {
        throw "Les PID de la releve sont figes a 26160 et 34588."
    }
    if ($PollSeconds -lt 1 -or $PollSeconds -gt 60) {
        throw "PollSeconds doit rester entre 1 et 60 secondes."
    }
    if ($ConfirmationSeconds -lt 5 -or $ConfirmationSeconds -gt 600) {
        throw "ConfirmationSeconds doit rester entre 5 et 600 secondes."
    }
    if ($MaxWaitHours -le 0) {
        throw "MaxWaitHours doit etre strictement positif."
    }
    if (-not [string]::IsNullOrWhiteSpace($ValidationFixtureJson)) {
        if (-not $ValidateOnly) {
            throw "Une fixture d'observation est interdite en mode runtime."
        }
        if (-not [IO.File]::Exists((Get-FullPath $ValidationFixtureJson))) {
            throw "Fixture d'observation absente."
        }
    }
    if (Test-PathOverlap -Left $SupervisionDir -Right $Repo) {
        throw "La supervision doit rester hors du depot."
    }

    $v3Path = [IO.Path]::Combine($resolvedRepo, $V3RelativePath)
    $v4Path = [IO.Path]::Combine($resolvedRepo, $V4RelativePath)
    $expected = [ordered]@{
        v3_wrapper = [ordered]@{ path = $v3Path; sha256 = $ExpectedV3Sha256 }
        v4_wrapper = [ordered]@{ path = $v4Path; sha256 = $ExpectedV4Sha256 }
        v4_go = [ordered]@{ path = (Get-FullPath $GoFile); sha256 = $ExpectedGoSha256 }
    }
    $actualHashes = [ordered]@{}
    foreach ($name in $expected.Keys) {
        $item = $expected[$name]
        if (-not [IO.File]::Exists($item.path)) {
            throw "Artefact absent ($name) : $($item.path)"
        }
        $actual = (Get-FileHash -LiteralPath $item.path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $item.sha256) {
            throw "Empreinte differente ($name) : $actual"
        }
        $actualHashes[$name] = $actual
    }

    try {
        $go = Get-Content -Raw -LiteralPath (Get-FullPath $GoFile) |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "GO V4 illisible ou invalide."
    }
    if ((Get-JsonProperty $go "schema_version") -ne "etudecas.supplier_v8_v2_to_stage3_v4_chain.v1.stage3_go.v1") {
        throw "Schema du GO V4 inattendu."
    }
    if ((Get-JsonProperty $go "decision") -ne "GO_STAGE3_V4") {
        throw "Decision du GO V4 inattendue."
    }
    if ((Get-JsonProperty $go "chain_wrapper_sha256") -ne $ExpectedV4Sha256) {
        throw "Le GO V4 ne designe pas le wrapper V4 fige."
    }
    if ((Get-JsonProperty $go "superseded_chain_wrapper_sha256") -ne $ExpectedV3Sha256) {
        throw "Le GO V4 ne designe pas le wrapper V3 remplace."
    }
    if ((Get-JsonProperty $go "stage3_inventory_signature") -ne $ExpectedStage3InventorySignature) {
        throw "Signature inventaire Stage3 inattendue."
    }
    if ((Get-JsonProperty $go "change_scope") -ne "atomic_status_write_compatibility_only") {
        throw "Perimetre de changement du GO V4 inattendu."
    }
    if ([string]::IsNullOrWhiteSpace([string](Get-JsonProperty $go "approved_by"))) {
        throw "Approbateur du GO V4 absent."
    }
    try {
        [void][DateTimeOffset]::Parse([string](Get-JsonProperty $go "approved_at_utc"))
    }
    catch {
        throw "Horodatage du GO V4 invalide."
    }
    return [ordered]@{
        artifact_sha256 = $actualHashes
        stage3_inventory_signature = $ExpectedStage3InventorySignature
    }
}

function Read-ValidationFixture {
    if ([string]::IsNullOrWhiteSpace($ValidationFixtureJson)) { return $null }
    if (-not $ValidateOnly) {
        throw "Fixture d'observation interdite hors ValidateOnly."
    }
    try {
        return Get-Content -Raw -LiteralPath (Get-FullPath $ValidationFixtureJson) |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Fixture d'observation invalide."
    }
}

function Assert-FixedRuntimeContract {
    if (-not (Test-SamePath -Left $Repo -Right $ExpectedRepo)) {
        throw "Repo runtime non autorise."
    }
    if (-not (Test-SamePath -Left $GoFile -Right $ExpectedGoFile)) {
        throw "GO runtime non autorise."
    }
    if (-not (Test-SamePath -Left $SupervisionDir -Right $ExpectedSupervisionDir)) {
        throw "Supervision runtime non autorisee."
    }
    if (-not (Test-SamePath -Left $PowerShellExecutable -Right $ExpectedPowerShellExecutable)) {
        throw "Executable PowerShell runtime non autorise."
    }
}

function Resolve-LegacyProcessObservation {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [object[]]$ProcessRecords
    )
    $byPid = @{}
    foreach ($record in $ProcessRecords) {
        $processId = [int]$record.ProcessId
        if ($processId -notin @($LegacyWrapperPid, $LegacySupervisorPid)) { continue }
        if ($byPid.ContainsKey($processId)) {
            throw "PID duplique dans la table des processus : $processId"
        }
        $byPid[$processId] = $record
    }

    if ($byPid.ContainsKey($LegacyWrapperPid)) {
        $wrapper = $byPid[$LegacyWrapperPid]
        if ([string]$wrapper.Name -ne "powershell.exe") {
            throw "PID $LegacyWrapperPid reutilise par un executable inattendu."
        }
        if (-not (Test-SamePath -Left ([string]$wrapper.ExecutablePath) -Right $ExpectedPowerShellExecutable)) {
            throw "Executable inattendu pour le PID V3 $LegacyWrapperPid."
        }
        $createdUtc = ([DateTime]$wrapper.CreationDate).ToUniversalTime().ToString("o")
        if ($createdUtc -ne $ExpectedLegacyWrapperCreatedUtc) {
            throw "Date de creation inattendue pour le PID V3 $LegacyWrapperPid."
        }
        Assert-ExactCommandLine -Observed ([string]$wrapper.CommandLine) -Expected $ExpectedLegacyWrapperCommandLine -Label "wrapper V3 PID $LegacyWrapperPid"
    }
    if ($byPid.ContainsKey($LegacySupervisorPid)) {
        $supervisor = $byPid[$LegacySupervisorPid]
        if ([string]$supervisor.Name -ne "python.exe") {
            throw "PID $LegacySupervisorPid reutilise par un executable inattendu."
        }
        if (-not (Test-SamePath -Left ([string]$supervisor.ExecutablePath) -Right $ExpectedSupervisorExecutable)) {
            throw "Executable inattendu pour le PID superviseur $LegacySupervisorPid."
        }
        $createdUtc = ([DateTime]$supervisor.CreationDate).ToUniversalTime().ToString("o")
        if ($createdUtc -ne $ExpectedLegacySupervisorCreatedUtc) {
            throw "Date de creation inattendue pour le PID superviseur $LegacySupervisorPid."
        }
        if ([int]$supervisor.ParentProcessId -ne $LegacyWrapperPid) {
            throw "Le superviseur historique n'a plus le parent V3 attendu."
        }
        Assert-ExactCommandLine -Observed ([string]$supervisor.CommandLine) -Expected $ExpectedLegacySupervisorCommandLine -Label "superviseur V3 PID $LegacySupervisorPid"
    }
    return [ordered]@{
        wrapper_pid = $LegacyWrapperPid
        wrapper_present = $byPid.ContainsKey($LegacyWrapperPid)
        supervisor_pid = $LegacySupervisorPid
        supervisor_present = $byPid.ContainsKey($LegacySupervisorPid)
        blocking = (
            $byPid.ContainsKey($LegacyWrapperPid) -or
            $byPid.ContainsKey($LegacySupervisorPid)
        )
    }
}

function Get-LegacyProcessObservation {
    $records = @(
        Get-CimInstance -ClassName Win32_Process -Filter (
            "ProcessId = $LegacyWrapperPid OR ProcessId = $LegacySupervisorPid"
        ) -ErrorAction Stop
    )
    return Resolve-LegacyProcessObservation -ProcessRecords $records
}

function Resolve-OldOwnerProcessObservation {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [object[]]$ProcessRecords,
        [Parameter(Mandatory = $true)][DateTimeOffset]$CutoffUtc
    )
    $owners = @()
    foreach ($record in $ProcessRecords) {
        $commandLine = [string]$record.CommandLine
        if ([string]::IsNullOrWhiteSpace($commandLine)) { continue }
        if ($commandLine.IndexOf(
            (Get-FullPath $CampaignRoot),
            [StringComparison]::OrdinalIgnoreCase
        ) -lt 0) { continue }
        if ($null -eq $record.CreationDate) {
            throw "Date de creation absente pour un ancien proprietaire potentiel."
        }
        $createdUtc = ([DateTime]$record.CreationDate).ToUniversalTime()
        if ($createdUtc -ge $CutoffUtc.UtcDateTime) { continue }
        $owners += [ordered]@{
            process_id = [int]$record.ProcessId
            parent_process_id = [int]$record.ParentProcessId
            name = [string]$record.Name
            executable_path = [string]$record.ExecutablePath
            created_at_utc = $createdUtc.ToString("o")
        }
    }
    return [ordered]@{
        cutoff_utc = $CutoffUtc.ToUniversalTime().ToString("o")
        count = $owners.Count
        blocking = ($owners.Count -gt 0)
        processes = $owners
    }
}

function Get-OldOwnerProcessObservation {
    param([Parameter(Mandatory = $true)][DateTimeOffset]$CutoffUtc)
    $records = @(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop)
    return Resolve-OldOwnerProcessObservation -ProcessRecords $records -CutoffUtc $CutoffUtc
}

function Resolve-V4ProcessObservation {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [object[]]$ProcessRecords
    )
    $matching = @()
    foreach ($record in $ProcessRecords) {
        $commandLine = [string]$record.CommandLine
        if ([string]::IsNullOrWhiteSpace($commandLine)) { continue }
        $mentionsV4 = $commandLine.IndexOf(
            (Get-FullPath ([IO.Path]::Combine($Repo, $V4RelativePath))),
            [StringComparison]::OrdinalIgnoreCase
        ) -ge 0
        if (-not $mentionsV4) { continue }
        if ([string]$record.Name -ne "powershell.exe") {
            throw "Un processus mentionne V4 depuis un executable inattendu."
        }
        if (-not (Test-SamePath -Left ([string]$record.ExecutablePath) -Right $ExpectedPowerShellExecutable)) {
            throw "Executable inattendu pour un processus V4."
        }
        if ($null -eq $record.CreationDate) {
            throw "Date de creation absente pour un processus V4."
        }
        Assert-ExactCommandLine -Observed $commandLine -Expected $ExpectedTargetV4ProcessCommandLine -Label "processus V4"
        $matching += $record
    }
    if ($matching.Count -gt 1) {
        throw "Plusieurs processus V4 exacts sont actifs."
    }
    return [ordered]@{
        count = $matching.Count
        present = ($matching.Count -eq 1)
        process_id = if ($matching.Count -eq 1) { [int]$matching[0].ProcessId } else { $null }
        created_at_utc = if ($matching.Count -eq 1) {
            ([DateTime]$matching[0].CreationDate).ToUniversalTime().ToString("o")
        }
        else { "" }
    }
}

function Get-V4ProcessObservation {
    $records = @(
        Get-CimInstance -ClassName Win32_Process -Filter (
            "Name = 'powershell.exe' OR Name = 'pwsh.exe'"
        ) -ErrorAction Stop
    )
    return Resolve-V4ProcessObservation -ProcessRecords $records
}

function Get-TaskEnabled {
    param(
        [Parameter(Mandatory = $true)][object]$Task,
        [Parameter(Mandatory = $true)][string]$TaskName
    )
    $property = $Task.Settings.PSObject.Properties["Enabled"]
    if ($null -ne $property) {
        if ($property.Value -is [bool]) { return [bool]$property.Value }
        return [string]::Equals(
            [string]$property.Value,
            "True",
            [StringComparison]::OrdinalIgnoreCase
        )
    }
    [xml]$xml = Export-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction Stop
    return [string]::Equals(
        [string]$xml.Task.Settings.Enabled,
        "True",
        [StringComparison]::OrdinalIgnoreCase
    )
}

function Assert-SingleTaskAction {
    param(
        [Parameter(Mandatory = $true)][object]$Task,
        [Parameter(Mandatory = $true)][string]$ExpectedArguments,
        [Parameter(Mandatory = $true)][string]$ExpectedWorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $actions = @($Task.Actions)
    if ($actions.Count -ne 1) {
        throw "$Label doit avoir exactement une action."
    }
    $action = $actions[0]
    if (-not (Test-SamePath -Left ([string]$action.Execute) -Right $PowerShellExecutable)) {
        throw "Executable inattendu pour $Label."
    }
    if (-not [string]::Equals(
        ([string]$action.Arguments).Trim(),
        $ExpectedArguments,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Arguments inattendus pour $Label."
    }
    if (-not (Test-SamePath -Left ([string]$action.WorkingDirectory) -Right $ExpectedWorkingDirectory)) {
        throw "WorkingDirectory inattendu pour $Label."
    }
    return [ordered]@{
        execute = Get-FullPath ([string]$action.Execute)
        arguments = ([string]$action.Arguments).Trim()
        working_directory = Get-FullPath ([string]$action.WorkingDirectory)
    }
}

function Assert-TargetScheduledTask {
    param(
        [AllowNull()][object]$TaskOverride = $null,
        [AllowNull()][object]$TaskInfoOverride = $null
    )
    if (($null -eq $TaskOverride) -ne ($null -eq $TaskInfoOverride)) {
        throw "TaskOverride et TaskInfoOverride doivent etre fournis ensemble."
    }
    if ($null -eq $TaskOverride) {
        Import-Module ScheduledTasks -ErrorAction Stop
        $task = Get-ScheduledTask -TaskName $TargetTaskName -TaskPath $TaskPath -ErrorAction Stop
        $taskInfo = Get-ScheduledTaskInfo -TaskName $TargetTaskName -TaskPath $TaskPath -ErrorAction Stop
    }
    else {
        $task = $TaskOverride
        $taskInfo = $TaskInfoOverride
    }
    $action = Assert-SingleTaskAction -Task $task -ExpectedArguments $ExpectedTargetArguments -ExpectedWorkingDirectory $ExpectedTargetWorkingDirectory -Label "tache cible V4"
    $enabled = Get-TaskEnabled -Task $task -TaskName $TargetTaskName
    if (-not $enabled) {
        throw "La tache cible V4 n'est pas activee."
    }
    if ([string]$task.Settings.MultipleInstances -ne "IgnoreNew") {
        throw "La tache cible doit conserver MultipleInstances=IgnoreNew."
    }
    $lastRunTimeUtc = ([DateTime]$taskInfo.LastRunTime).ToUniversalTime().ToString("o")
    return [ordered]@{
        name = $TargetTaskName
        path = $TaskPath
        state = [string]$task.State
        enabled = $enabled
        multiple_instances = [string]$task.Settings.MultipleInstances
        last_run_time_utc = $lastRunTimeUtc
        action = $action
    }
}

function Assert-V4HandoffCorrelation {
    param(
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$TargetTask,
        [Parameter(Mandatory = $true)][System.Collections.IDictionary]$V4Process,
        [AllowNull()][object]$StartMarker
    )
    if ($TargetTask.state -ne "Running" -or -not $V4Process.present) {
        throw "Tache Running et processus V4 exact requis pour la correlation."
    }
    $processCreated = [DateTimeOffset]::Parse([string]$V4Process.created_at_utc)
    $lastRun = [DateTimeOffset]::Parse([string]$TargetTask.last_run_time_utc)
    if ($null -ne $StartMarker) {
        $markerCreated = [DateTimeOffset]::Parse([string]$StartMarker.created_at_utc)
        $previousLastRun = [DateTimeOffset]::Parse(
            [string]$StartMarker.target_last_run_time_before_start_utc
        )
        if ($processCreated -lt $markerCreated) {
            throw "Le processus V4 est anterieur a la demande guardian."
        }
        if ($lastRun -le $previousLastRun -or $lastRun -lt $markerCreated) {
            throw "LastRunTime ne prouve pas un nouveau lancement V4."
        }
    }
    if ([Math]::Abs(($processCreated - $lastRun).TotalSeconds) -gt 30) {
        throw "Creation du processus V4 non correlee au LastRunTime de la tache."
    }
    return [ordered]@{
        process_created_at_utc = $processCreated.ToUniversalTime().ToString("o")
        target_last_run_time_utc = $lastRun.ToUniversalTime().ToString("o")
        start_marker_correlated = ($null -ne $StartMarker)
    }
}

function Assert-OwnGuardianScheduledTask {
    param([AllowNull()][object]$TaskOverride = $null)
    if ($null -eq $TaskOverride) {
        Import-Module ScheduledTasks -ErrorAction Stop
        $task = Get-ScheduledTask -TaskName $GuardianTaskName -TaskPath $TaskPath -ErrorAction Stop
    }
    else { $task = $TaskOverride }
    $expectedArguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
        (Get-FullPath $PSCommandPath) + '"'
    [void](Assert-SingleTaskAction -Task $task -ExpectedArguments $expectedArguments -ExpectedWorkingDirectory $ExpectedTargetWorkingDirectory -Label "tache guardian")
    if (-not (Get-TaskEnabled -Task $task -TaskName $GuardianTaskName)) {
        throw "La tache guardian n'est pas activee."
    }
    if ([string]$task.Settings.MultipleInstances -ne "IgnoreNew") {
        throw "La tache guardian doit conserver MultipleInstances=IgnoreNew."
    }
    return $task
}

function Get-HandoffDecision {
    param(
        [Parameter(Mandatory = $true)][bool]$LegacyBlocking,
        [Parameter(Mandatory = $true)][string]$TargetTaskState,
        [Parameter(Mandatory = $true)][int]$V4ProcessCount,
        [Parameter(Mandatory = $true)][bool]$StartRecorded,
        [Parameter(Mandatory = $true)][bool]$ConfirmationExpired,
        [Parameter(Mandatory = $true)][bool]$QuiescenceConfirmed
    )
    if ($LegacyBlocking) { return "wait_legacy" }
    if ($V4ProcessCount -lt 0 -or $V4ProcessCount -gt 1) {
        throw "Nombre de processus V4 incoherent."
    }
    if ($V4ProcessCount -eq 1 -and $TargetTaskState -eq "Running") {
        return "handoff_validated"
    }
    if ($ConfirmationExpired) {
        throw "Delai de confirmation du processus V4 depasse."
    }
    if ($StartRecorded) { return "wait_v4_confirmation" }
    if ($TargetTaskState -in @("Running", "Queued")) {
        return "wait_existing_start"
    }
    if ($TargetTaskState -eq "Ready") {
        if (-not $QuiescenceConfirmed) { return "wait_quiescence" }
        return "start_once"
    }
    throw "Etat de la tache cible incompatible : $TargetTaskState"
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
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(
        ($Payload | ConvertTo-Json -Depth 16) + [Environment]::NewLine
    )
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
            Start-Sleep -Milliseconds ([int][Math]::Min(
                1000,
                50 * [Math]::Pow(2, $attempt)
            ))
        }
    }
    finally {
        if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
        if ([IO.File]::Exists($backup)) { [IO.File]::Delete($backup) }
    }
}

function Write-JsonCreateNewAtomic {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object]$Payload
    )
    $destination = Get-FullPath $Path
    if ([IO.File]::Exists($destination)) {
        throw "La preuve de demarrage unique existe deja."
    }
    $parent = [IO.Path]::GetDirectoryName($destination)
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temporary = [IO.Path]::Combine(
        $parent,
        "." + [IO.Path]::GetFileName($destination) + ".tmp." +
            $PID + "." + [Guid]::NewGuid().ToString("N")
    )
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(
        ($Payload | ConvertTo-Json -Depth 16) + [Environment]::NewLine
    )
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
        [IO.File]::Move($temporary, $destination)
    }
    finally {
        if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
    }
}

function Get-KeepAwakePayload {
    return [ordered]@{
        requested = $true
        active = $script:WakeActive
        method = "windows_SetThreadExecutionState"
        started_at_utc = $script:WakeStartedAtUtc
        stopped_at_utc = $script:WakeStoppedAtUtc
        coverage = "wait_legacy_then_confirm_v4_handoff"
    }
}

function Start-GuardianKeepAwake {
    if ($script:WakeActive) { throw "Keep-awake deja actif." }
    if (-not ("Etudecas.V8V4Handoff.NativeMethods" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
namespace Etudecas.V8V4Handoff {
    public static class NativeMethods {
        [DllImport("kernel32.dll")]
        public static extern UInt32 SetThreadExecutionState(UInt32 executionState);
    }
}
"@ | Out-Null
    }
    $script:WakeStartedAtUtc = Get-UtcTimestamp
    $result = [Etudecas.V8V4Handoff.NativeMethods]::SetThreadExecutionState(
        [Convert]::ToUInt32("80000001", 16)
    )
    if ($result -eq 0) { throw "Windows a refuse le maintien en eveil." }
    $script:WakeActive = $true
}

function Stop-GuardianKeepAwake {
    if ($script:WakeActive) {
        [void][Etudecas.V8V4Handoff.NativeMethods]::SetThreadExecutionState(
            [Convert]::ToUInt32("80000000", 16)
        )
    }
    $script:WakeActive = $false
    $script:WakeStoppedAtUtc = Get-UtcTimestamp
}

function Write-GuardianStatus {
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
        business_message_fr = $Message
        updated_at_utc = Get-UtcTimestamp
        no_simulation_engine_started_directly = $true
        target_task = [ordered]@{ name = $TargetTaskName; path = $TaskPath }
        guardian_task = [ordered]@{
            name = $GuardianTaskName
            path = $TaskPath
            self_disable_pending = ($Status -ne "complete")
        }
        keep_awake = Get-KeepAwakePayload
    }
    foreach ($key in $Details.Keys) { $payload[$key] = $Details[$key] }
    Write-JsonAtomic -Path ([IO.Path]::Combine(
        (Get-FullPath $SupervisionDir),
        "status.json"
    )) -Payload $payload
}

function Read-StartMarker {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not [IO.File]::Exists((Get-FullPath $Path))) { return $null }
    try {
        $marker = Get-Content -Raw -LiteralPath (Get-FullPath $Path) |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Preuve de demarrage unique illisible."
    }
    if ((Get-JsonProperty $marker "schema_version") -ne "$SchemaVersion.start_once.v1") {
        throw "Schema de preuve de demarrage inattendu."
    }
    if ((Get-JsonProperty $marker "target_task_name") -ne $TargetTaskName) {
        throw "Cible de la preuve de demarrage inattendue."
    }
    if ((Get-JsonProperty $marker "v4_wrapper_sha256") -ne $ExpectedV4Sha256) {
        throw "Empreinte V4 de la preuve de demarrage inattendue."
    }
    if ((Get-JsonProperty $marker "go_sha256") -ne $ExpectedGoSha256) {
        throw "Empreinte GO de la preuve de demarrage inattendue."
    }
    try {
        [void][DateTimeOffset]::Parse([string](Get-JsonProperty $marker "created_at_utc"))
        [void][DateTimeOffset]::Parse(
            [string](Get-JsonProperty $marker "target_last_run_time_before_start_utc")
        )
    }
    catch {
        throw "Horodatage de preuve de demarrage invalide."
    }
    return $marker
}

function Invoke-TargetTaskStartOnce {
    if ($script:TargetStartCalled) {
        throw "Start-ScheduledTask a deja ete appele par cette instance guardian."
    }
    $script:TargetStartCalled = $true
    Start-ScheduledTask -TaskName $TargetTaskName -TaskPath $TaskPath -ErrorAction Stop
    return [ordered]@{
        target_task_name = $TargetTaskName
        requested_at_utc = Get-UtcTimestamp
        call_count_this_process = 1
    }
}

function Disable-OwnGuardianScheduledTask {
    [void](Assert-OwnGuardianScheduledTask)
    Disable-ScheduledTask -TaskName $GuardianTaskName -TaskPath $TaskPath -ErrorAction Stop |
        Out-Null
    $after = Get-ScheduledTask -TaskName $GuardianTaskName -TaskPath $TaskPath -ErrorAction Stop
    if (Get-TaskEnabled -Task $after -TaskName $GuardianTaskName) {
        throw "La tache guardian reste activee."
    }
    return [ordered]@{
        name = $GuardianTaskName
        path = $TaskPath
        definition_enabled = $false
        observed_runtime_state = [string]$after.State
    }
}

if ($ValidateOnly) {
    $validation = Assert-StaticInputs
    $fixture = Read-ValidationFixture
    if ($null -eq $fixture) {
        $legacy = Get-LegacyProcessObservation
        $target = Assert-TargetScheduledTask
        [void](Assert-OwnGuardianScheduledTask)
        $v4Process = Get-V4ProcessObservation
        $allProcesses = @(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop)
    }
    else {
        $allProcesses = @($fixture.processes)
        $legacy = Resolve-LegacyProcessObservation -ProcessRecords $allProcesses
        $target = Assert-TargetScheduledTask -TaskOverride $fixture.target_task -TaskInfoOverride $fixture.target_task_info
        [void](Assert-OwnGuardianScheduledTask -TaskOverride $fixture.guardian_task)
        $v4Process = Resolve-V4ProcessObservation -ProcessRecords $allProcesses
    }
    $markerPath = [IO.Path]::Combine((Get-FullPath $SupervisionDir), "start_once.json")
    $marker = Read-StartMarker -Path $markerPath
    $ownerCutoff = if ($null -ne $marker) {
        [DateTimeOffset]::Parse([string]$marker.created_at_utc)
    }
    elseif ($v4Process.present) {
        [DateTimeOffset]::Parse([string]$v4Process.created_at_utc)
    }
    else { [DateTimeOffset]::UtcNow }
    $oldOwners = Resolve-OldOwnerProcessObservation -ProcessRecords $allProcesses -CutoffUtc $ownerCutoff
    $oldBlocking = ([bool]$legacy.blocking -or [bool]$oldOwners.blocking)
    $decision = Get-HandoffDecision -LegacyBlocking $oldBlocking -TargetTaskState ([string]$target.state) -V4ProcessCount ([int]$v4Process.count) -StartRecorded ($null -ne $marker) -ConfirmationExpired $false -QuiescenceConfirmed $false
    if ($decision -eq "handoff_validated") {
        [void](Assert-V4HandoffCorrelation -TargetTask $target -V4Process $v4Process -StartMarker $marker)
    }
    [ordered]@{
        schema_version = "$SchemaVersion.validation.v1"
        status = "valid"
        mode = "validate_only"
        launch_performed = $false
        simulation_engine_started = $false
        scheduled_task_changed = $false
        filesystem_mutation_performed = $false
        validation_fixture_used = ($null -ne $fixture)
        planned_decision = $decision
        legacy_processes = $legacy
        old_campaign_owners = $oldOwners
        target_task = $target
        v4_process = $v4Process
        start_once_recorded = ($null -ne $marker)
        validation = $validation
    } | ConvertTo-Json -Depth 16
    exit 0
}

# Runtime is permitted only from an externally registered dedicated task.
# This wrapper never creates a task and never directly starts a simulation engine.
Assert-FixedRuntimeContract
$startupValidation = Assert-StaticInputs
[void](Assert-OwnGuardianScheduledTask)
[void](Assert-TargetScheduledTask)
[void](Get-LegacyProcessObservation)
[IO.Directory]::CreateDirectory((Get-FullPath $SupervisionDir)) | Out-Null
$lockPath = [IO.Path]::Combine((Get-FullPath $SupervisionDir), ".guardian.lock")
try {
    $guardianLock = [IO.File]::Open(
        $lockPath,
        [IO.FileMode]::OpenOrCreate,
        [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None
    )
}
catch {
    throw "Une autre instance guardian detient deja le verrou."
}

$completed = $false
$failure = $null
$terminalDetails = [ordered]@{}
$markerPath = [IO.Path]::Combine((Get-FullPath $SupervisionDir), "start_once.json")
$confirmationDeadline = $null
$quietObservations = 0
$globalDeadline = [DateTimeOffset]::UtcNow.AddHours($MaxWaitHours)
try {
    Start-GuardianKeepAwake
    while (-not $completed) {
        $validation = Assert-StaticInputs
        $legacy = Get-LegacyProcessObservation
        $target = Assert-TargetScheduledTask
        $v4Process = Get-V4ProcessObservation
        $marker = Read-StartMarker -Path $markerPath
        $ownerCutoff = if ($null -ne $marker) {
            [DateTimeOffset]::Parse([string]$marker.created_at_utc)
        }
        elseif ($v4Process.present) {
            [DateTimeOffset]::Parse([string]$v4Process.created_at_utc)
        }
        else { [DateTimeOffset]::UtcNow }
        $oldOwners = Get-OldOwnerProcessObservation -CutoffUtc $ownerCutoff
        $oldBlocking = ([bool]$legacy.blocking -or [bool]$oldOwners.blocking)

        if ($oldBlocking) {
            $confirmationDeadline = $null
            $quietObservations = 0
        }
        else {
            $quietObservations = [Math]::Min(2, $quietObservations + 1)
            if ($null -ne $marker -and $null -eq $confirmationDeadline) {
                $createdAt = [DateTimeOffset]::Parse([string]$marker.created_at_utc)
                $confirmationDeadline = $createdAt.AddSeconds($ConfirmationSeconds)
            }
            elseif (
                $null -eq $marker -and
                $target.state -in @("Running", "Queued") -and
                $null -eq $confirmationDeadline
            ) {
                $confirmationDeadline = [DateTimeOffset]::UtcNow.AddSeconds(
                    $ConfirmationSeconds
                )
            }
        }
        $confirmationExpired = (
            $null -ne $confirmationDeadline -and
            [DateTimeOffset]::UtcNow -ge $confirmationDeadline
        )
        $decision = Get-HandoffDecision -LegacyBlocking $oldBlocking -TargetTaskState ([string]$target.state) -V4ProcessCount ([int]$v4Process.count) -StartRecorded ($null -ne $marker) -ConfirmationExpired $confirmationExpired -QuiescenceConfirmed ($quietObservations -ge 2)

        if ($decision -eq "wait_legacy") {
            Write-GuardianStatus -Status "waiting_legacy" -Step "wait_legacy" -Message "Attente de la fin naturelle de V3 et de son superviseur; aucune relance n'est demandee." -Details @{
                legacy_processes = $legacy
                old_campaign_owners = $oldOwners
                target_task = $target
                start_once_recorded = ($null -ne $marker)
            }
        }
        elseif ($decision -in @("wait_existing_start", "wait_v4_confirmation", "wait_quiescence")) {
            Write-GuardianStatus -Status $decision -Step "confirm_v4" -Message "Une transition de la tache est deja visible; attente de la preuve processus V4 sans nouvel appel." -Details @{
                legacy_processes = $legacy
                old_campaign_owners = $oldOwners
                target_task = $target
                v4_process = $v4Process
                start_once_recorded = ($null -ne $marker)
                confirmation_deadline_utc = if ($null -ne $confirmationDeadline) { $confirmationDeadline.ToString("o") } else { "" }
            }
        }
        elseif ($decision -eq "start_once") {
            # Recheck every safety condition immediately before the sole start call.
            $validation = Assert-StaticInputs
            $legacy = Get-LegacyProcessObservation
            $target = Assert-TargetScheduledTask
            $v4Process = Get-V4ProcessObservation
            $oldOwners = Get-OldOwnerProcessObservation -CutoffUtc ([DateTimeOffset]::UtcNow)
            if ($legacy.blocking -or $oldOwners.blocking -or $target.state -ne "Ready" -or $v4Process.present) {
                throw "Etat modifie pendant le controle final; aucun demarrage n'est demande."
            }
            $createdAt = Get-UtcTimestamp
            Write-JsonCreateNewAtomic -Path $markerPath -Payload ([ordered]@{
                schema_version = "$SchemaVersion.start_once.v1"
                status = "start_requested_at_most_once"
                created_at_utc = $createdAt
                target_task_name = $TargetTaskName
                target_task_path = $TaskPath
                v4_wrapper_sha256 = $ExpectedV4Sha256
                go_sha256 = $ExpectedGoSha256
                legacy_wrapper_present = $false
                legacy_supervisor_present = $false
                action_arguments = $ExpectedTargetArguments
                target_last_run_time_before_start_utc = $target.last_run_time_utc
            })
            Write-GuardianStatus -Status "start_once_recorded" -Step "start_v4" -Message "Fin de V3 confirmee; demande unique de demarrage de la tache V4 enregistree." -Details @{
                legacy_processes = $legacy
                old_campaign_owners = $oldOwners
                target_task = $target
                start_once_marker = $markerPath
            }
            $startEvidence = Invoke-TargetTaskStartOnce
            $confirmationDeadline = ([DateTimeOffset]::Parse($createdAt)).AddSeconds(
                $ConfirmationSeconds
            )
            Write-GuardianStatus -Status "start_requested" -Step "confirm_v4" -Message "Demarrage V4 demande une seule fois; confirmation du processus et de l'Action en cours." -Details @{
                start = $startEvidence
                start_once_marker = $markerPath
                confirmation_deadline_utc = $confirmationDeadline.ToString("o")
            }
        }
        elseif ($decision -eq "handoff_validated") {
            # Final proof immediately before disabling only the guardian.
            $validation = Assert-StaticInputs
            $legacy = Get-LegacyProcessObservation
            $target = Assert-TargetScheduledTask
            $v4Process = Get-V4ProcessObservation
            $marker = Read-StartMarker -Path $markerPath
            $ownerCutoff = if ($null -ne $marker) {
                [DateTimeOffset]::Parse([string]$marker.created_at_utc)
            }
            else { [DateTimeOffset]::Parse([string]$v4Process.created_at_utc) }
            $oldOwners = Get-OldOwnerProcessObservation -CutoffUtc $ownerCutoff
            if (
                $legacy.blocking -or
                $oldOwners.blocking -or
                $target.state -ne "Running" -or
                -not $v4Process.present
            ) {
                throw "La preuve finale de releve V4 n'est plus valide."
            }
            $correlation = Assert-V4HandoffCorrelation -TargetTask $target -V4Process $v4Process -StartMarker $marker
            Write-GuardianStatus -Status "handoff_validated" -Step "disable_guardian" -Message "Processus V4 et Action V4 confirmes; desactivation de la seule tache guardian." -Details @{
                legacy_processes = $legacy
                old_campaign_owners = $oldOwners
                target_task = $target
                v4_process = $v4Process
                handoff_correlation = $correlation
                start_once_recorded = ([IO.File]::Exists($markerPath))
            }
            $disableProof = Disable-OwnGuardianScheduledTask
            $terminalDetails = [ordered]@{
                validation = $validation
                legacy_processes = $legacy
                old_campaign_owners = $oldOwners
                target_task = $target
                v4_process = $v4Process
                handoff_correlation = $correlation
                start_once_recorded = ([IO.File]::Exists($markerPath))
                guardian_disable = $disableProof
            }
            $completed = $true
        }

        if (-not $completed) {
            if ([DateTimeOffset]::UtcNow -ge $globalDeadline) {
                throw "Delai maximal de releve V3 vers V4 depasse."
            }
            Start-Sleep -Seconds $PollSeconds
        }
    }
}
catch {
    $failure = $_
}
finally {
    Stop-GuardianKeepAwake
    try {
        if ($completed) {
            Write-GuardianStatus -Status "complete" -Step "complete" -Message "Releve V4 confirmee; guardian desactive. Aucun moteur n'a ete lance directement." -Details $terminalDetails
        }
        else {
            Write-GuardianStatus -Status "failed" -Step "failed" -Message "Guardian arrete sur une erreur reelle; aucune nouvelle tentative automatique de demarrage." -Details @{
                error = [ordered]@{
                    type = $failure.Exception.GetType().FullName
                    message = $failure.Exception.Message
                }
                start_once_recorded = ([IO.File]::Exists($markerPath))
                guardian_disabled = $false
            }
        }
    }
    finally {
        $guardianLock.Dispose()
    }
}

if ($null -ne $failure) { throw $failure }
exit 0
