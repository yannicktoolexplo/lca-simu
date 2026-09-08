from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / (
    "etudecas/prototypes/scan_2027_risk_control/"
    "run_supplier_v8_post_stage3_final_v4_task.ps1"
)


def _powershell() -> str:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    return str(
        system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )


def _frozen_hashes(source: str) -> dict[str, str]:
    block = source.split("# BEGIN POST_STAGE3_FROZEN_HASHES", maxsplit=1)[1].split(
        "# END POST_STAGE3_FROZEN_HASHES", maxsplit=1
    )[0]
    pairs = re.findall(r'^\s*"([^"]+\.py)"\s*=\s*"([0-9a-f]{64})"\s*$', block, re.M)
    return dict(pairs)


def test_wrapper_parses_in_windows_powershell_5() -> None:
    environment = dict(os.environ)
    environment["POST_STAGE3_WRAPPER"] = str(SCRIPT)
    command = (
        "$tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:POST_STAGE3_WRAPPER,[ref]$tokens,[ref]$errors) | Out-Null; "
        "if($errors.Count){$errors|ForEach-Object{"
        "[Console]::Error.WriteLine($_.Message)};exit 1}; "
        "Write-Output 'PARSE_PS5_OK'"
    )
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"PARSE_PS5_OK" in completed.stdout


def test_validate_only_is_strictly_inert(tmp_path: Path) -> None:
    root = tmp_path / "must-stay-absent"
    focus = root / "focus"
    delivery = root / "delivery"
    supervision = root / "supervision"
    stage3 = root / "stage3"
    closure = root / "closure" / "closure_report.json"
    completed = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-ValidateOnly",
            "-Stage3SupervisionDir",
            str(stage3),
            "-ClosureReport",
            str(closure),
            "-FocusRoot",
            str(focus),
            "-DeliveryRoot",
            str(delivery),
            "-SupervisionDir",
            str(supervision),
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    output_text = completed.stdout.decode("utf-8-sig")
    assert all(marker not in output_text for marker in ("Ã", "Â", "\ufffd"))
    payload = json.loads(output_text)
    assert payload["status"] == "valid"
    assert payload["mode"] == "validate_only"
    assert payload["launch_performed"] is False
    assert payload["simulation_engine_started"] is False
    assert payload["scheduled_task_changed"] is False
    assert payload["filesystem_mutation_performed"] is False
    assert payload["validation"]["focus_execution_sequential"] is True
    assert payload["validation"]["maximum_focus_arms"] == 4
    assert not root.exists()


def test_real_ps5_simulated_status_is_utf8_without_mojibake(tmp_path: Path) -> None:
    supervision = tmp_path / "supervision"
    status_path = supervision / "status.json"
    environment = dict(os.environ)
    environment["POST_STAGE3_WRAPPER"] = str(SCRIPT)
    environment["POST_STAGE3_STATUS_ROOT"] = str(supervision)
    environment["POST_STAGE3_TEMP_ROOT"] = str(tmp_path)
    command = (
        "$tokens=$null;$errors=$null;"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:POST_STAGE3_WRAPPER,[ref]$tokens,[ref]$errors);"
        "foreach($name in @('Get-UtcTimestamp','Get-FullPath','Get-KeepAwakePayload',"
        "'Write-BytesAtomic','Write-TextAtomic','Write-JsonAtomic',"
        "'Write-PostStage3Status')){"
        "$node=$ast.Find({param($n)$n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq $name},$true);Invoke-Expression $node.Extent.Text};"
        "$SchemaVersion='test.post_stage3';"
        "$TaskName='Codex-Supplier-V8-Post-Stage3-Final-V4';$TaskPath='\\';"
        "$Stage3SupervisionDir=Join-Path $env:POST_STAGE3_TEMP_ROOT 'stage3';"
        "$ClosureReport=Join-Path $env:POST_STAGE3_TEMP_ROOT "
        "'closure\\closure_report.json';"
        "$FocusRoot=Join-Path $env:POST_STAGE3_TEMP_ROOT 'focus';"
        "$DeliveryRoot=Join-Path $env:POST_STAGE3_TEMP_ROOT 'delivery';"
        "$SupervisionDir=$env:POST_STAGE3_STATUS_ROOT;$MaxFocusArms=4;"
        "$script:WakeActive=$false;$script:WakeStartedAtUtc='';"
        "$script:WakeStoppedAtUtc='';"
        "Write-PostStage3Status -Status 'complete' -Step 'complete' "
        "-Message 'Cloture validee; livraison prete.' "
        "-Details @{proof='recu exact; aucune donnee alteree.'};"
        "Write-Output 'STATUS_PS5_OK'"
    )
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    stdout = completed.stdout.decode("utf-8-sig")
    assert "STATUS_PS5_OK" in stdout
    assert all(marker not in stdout for marker in ("Ã", "Â", "\ufffd"))
    raw = status_path.read_bytes().decode("utf-8-sig", errors="strict")
    assert all(marker not in raw for marker in ("Ã", "Â", "\ufffd"))
    payload = json.loads(raw)
    assert payload["message_fr"] == "Cloture validee; livraison prete."
    assert payload["proof"] == "recu exact; aucune donnee alteree."


def test_real_ps5_captures_parses_and_logs_python_utf8(tmp_path: Path) -> None:
    supervision = tmp_path / "logs"
    environment = dict(os.environ)
    environment["POST_STAGE3_WRAPPER"] = str(SCRIPT)
    environment["POST_STAGE3_UTF8_LOG_ROOT"] = str(supervision)
    environment["POST_STAGE3_PYTHON"] = os.environ.get(
        "POST_STAGE3_TEST_PYTHON", os.sys.executable
    )
    environment["POST_STAGE3_REPO"] = str(REPO)
    command = (
        "$tokens=$null;$errors=$null;"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:POST_STAGE3_WRAPPER,[ref]$tokens,[ref]$errors);"
        "foreach($name in @('Get-UtcTimestamp','Get-FullPath',"
        "'ConvertTo-WindowsArgument','New-PythonProcessStartInfo',"
        "'Invoke-PythonCapture','Write-BytesAtomic','Write-TextAtomic',"
        "'Invoke-LoggedPythonStep')){"
        "$node=$ast.Find({param($n)$n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq $name},$true);Invoke-Expression $node.Extent.Text};"
        "$Python=$env:POST_STAGE3_PYTHON;$Repo=$env:POST_STAGE3_REPO;"
        "$SupervisionDir=$env:POST_STAGE3_UTF8_LOG_ROOT;"
        "$code=\"import json; print(json.dumps({'message':"
        "'r\\u00e9sum\\u00e9'}, ensure_ascii=False))\";"
        "$result=Invoke-LoggedPythonStep -Step 'utf8_probe' -ParseJson "
        "-Arguments @('-c',$code);"
        "$expected='r'+[char]0x00e9+'sum'+[char]0x00e9;"
        "if($result.payload.message -ne $expected){exit 14};"
        "Write-Output 'PYTHON_UTF8_PS5_OK'"
    )
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"PYTHON_UTF8_PS5_OK" in completed.stdout
    log = (supervision / "utf8_probe.stdout.log").read_text(encoding="utf-8")
    assert "résumé" in log
    assert all(marker not in log for marker in ("Ã", "Â", "\ufffd"))


def test_frozen_hash_block_is_small_exact_and_current() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    frozen = _frozen_hashes(source)
    assert set(frozen) == {
        "etudecas\\prototypes\\scan_2027_risk_control\\supplier_v8_post_stage3_focus_338929.py",
        "etudecas\\prototypes\\scan_2027_risk_control\\supplier_v8_post_stage3_delivery_v4.py",
        "etudecas\\prototypes\\scan_2027_risk_control\\verify_supplier_v8_stage3_closure.py",
    }
    for relative, expected in frozen.items():
        path = REPO / Path(relative.replace("\\", "/"))
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    assert source.count("# BEGIN POST_STAGE3_FROZEN_HASHES") == 1
    assert source.count("# END POST_STAGE3_FROZEN_HASHES") == 1
    assert source.isascii()


def test_runtime_order_and_maximum_four_sequential_arms() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    runtime = source.split("# Runtime starts only", maxsplit=1)[1]
    ordered_calls = [
        "$closureReadiness = Wait-TechnicallyConformingClosure",
        'Invoke-LoggedPythonStep -Step "02_focus_plan"',
        'Invoke-LoggedPythonStep -Step "03_focus_preflight"',
        'Invoke-LoggedPythonStep -Step "04_focus_run_execute"',
        'Invoke-LoggedPythonStep -Step "05_focus_finalize"',
        'Invoke-LoggedPythonStep -Step "06_focus_validate"',
        'Invoke-LoggedPythonStep -Step "07_delivery_build"',
        'Invoke-LoggedPythonStep -Step "08_delivery_validate"',
        "$disableProof = Disable-OwnScheduledTask",
    ]
    positions = [runtime.index(value) for value in ordered_calls]
    assert positions == sorted(positions)
    assert runtime.count('Invoke-LoggedPythonStep -Step "04_focus_run_execute"') == 1
    assert '"--execute"' in runtime
    assert "$MaxFocusArms = 4" in source
    assert "[int]$plannedArms -gt $MaxFocusArms" in runtime
    assert "single_python_process_sequential" in runtime
    assert "Start-Job" not in runtime
    assert "ForEach-Object -Parallel" not in runtime
    assert "Start-Process" not in runtime


def test_frozen_focus_implementation_itself_executes_jobs_sequentially() -> None:
    focus = SCRIPT.with_name("supplier_v8_post_stage3_focus_338929.py").read_text(
        encoding="utf-8-sig"
    )
    execute = focus.split("def _execute_locked(", maxsplit=1)[1].split(
        "def finalize(", maxsplit=1
    )[0]
    run = focus.split("def run(", maxsplit=1)[1].split(
        "def _validate_receipt(", maxsplit=1
    )[0]
    assert 'MECHANISMS = ("transport_delay", "planned_delivery_shortfall")' in focus
    assert 'for arm in ("baseline", "incident")' in run
    assert "for dossier, arm in jobs:" in execute
    assert "subprocess.run(" in execute
    assert "subprocess.Popen(" not in execute
    assert "ThreadPoolExecutor" not in execute
    assert "ProcessPoolExecutor" not in execute


def test_closure_wait_is_exact_signed_technical_and_fails_closed() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    assert "report == expected" in source
    assert 'technical.get("code") == "CONFORME_TECHNIQUE"' in source
    assert 'technical.get("conforme") is True' in source
    assert 'report.get("no_simulation_engine_started") is True' in source
    assert '"readiness": "WAIT", "reason": "closure_report_absent"' in source
    assert "closure validation failed closed" in source
    assert "Get-ClosureReadiness" in source
    assert "Wait-TechnicallyConformingClosure" in source
    assert "Start-Sleep -Seconds $PollSeconds" in source


def test_status_and_logs_use_atomic_new_or_replace_writes() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    assert "function Write-BytesAtomic" in source
    assert "function Write-TextAtomic" in source
    assert "function Write-JsonAtomic" in source
    assert "[IO.File]::Replace($temporary, $destination, $backup, $true)" in source
    assert "[IO.File]::Move($temporary, $destination)" in source
    assert "Write-TextAtomic -Path $stdoutPath" in source
    assert "Write-TextAtomic -Path $stderrPath" in source
    assert '"status.json"' in source


def test_atomic_json_and_text_survive_two_real_ps5_writes(tmp_path: Path) -> None:
    destination_json = tmp_path / "status.json"
    destination_log = tmp_path / "step.log"
    environment = dict(os.environ)
    environment["POST_STAGE3_WRAPPER"] = str(SCRIPT)
    environment["POST_STAGE3_ATOMIC_JSON"] = str(destination_json)
    environment["POST_STAGE3_ATOMIC_LOG"] = str(destination_log)
    command = (
        "$tokens=$null;$errors=$null;"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:POST_STAGE3_WRAPPER,[ref]$tokens,[ref]$errors);"
        "foreach($name in @('Get-FullPath','Write-BytesAtomic',"
        "'Write-TextAtomic','Write-JsonAtomic')){"
        "$node=$ast.Find({param($n)$n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq $name},$true);Invoke-Expression $node.Extent.Text};"
        "Write-JsonAtomic -Path $env:POST_STAGE3_ATOMIC_JSON "
        "-Payload ([ordered]@{sequence=1;value='first'});"
        "Write-JsonAtomic -Path $env:POST_STAGE3_ATOMIC_JSON "
        "-Payload ([ordered]@{sequence=2;value='second'});"
        "Write-TextAtomic -Path $env:POST_STAGE3_ATOMIC_LOG -Text 'first';"
        "Write-TextAtomic -Path $env:POST_STAGE3_ATOMIC_LOG -Text 'second';"
        "$j=Get-Content -Raw -LiteralPath $env:POST_STAGE3_ATOMIC_JSON|ConvertFrom-Json;"
        "$t=Get-Content -Raw -LiteralPath $env:POST_STAGE3_ATOMIC_LOG;"
        "if($j.sequence -ne 2 -or $j.value -ne 'second' -or $t -ne 'second'){exit 12};"
        "$left=@(Get-ChildItem -LiteralPath ([IO.Path]::GetDirectoryName("
        "$env:POST_STAGE3_ATOMIC_JSON)) -Force|Where-Object{"
        "$_.Name -match '\\.(tmp|bak)\\.'});if($left.Count){exit 13};"
        "Write-Output 'ATOMIC_TWO_WRITES_PS5_OK'"
    )
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"ATOMIC_TWO_WRITES_PS5_OK" in completed.stdout
    assert json.loads(destination_json.read_text(encoding="utf-8")) == {
        "sequence": 2,
        "value": "second",
    }
    assert destination_log.read_text(encoding="utf-8") == "second"


def test_wrapper_is_additive_fail_closed_and_never_manages_other_tasks() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    runtime = source.split("# Runtime starts only", maxsplit=1)[1]
    assert "[Threading.Mutex]::new" in runtime
    assert "SetThreadExecutionState" in source
    assert "Register-ScheduledTask" not in source
    assert "New-ScheduledTask" not in source
    assert "Unregister-ScheduledTask" not in source
    assert "Remove-Item" not in source
    assert "failed_fail_closed" in runtime
    assert (
        "reuse_only_fully_validated_outputs_partial_arm_requires_manual_intervention_never_delete"
        in runtime
    )
    assert "automatic_partial_arm_repair = $false" in runtime
    assert "[IO.FileShare]::None" in source
    assert "Open-CrossSessionLock" in runtime
    assert '"IgnoreNew"' in source
    assert runtime.index("[void](Assert-StaticInputs)") < runtime.index(
        "$crossSessionLock = Open-CrossSessionLock"
    )
    assert runtime.index(
        '$deliveryValidate = Invoke-LoggedPythonStep -Step "08_delivery_validate"'
    ) < runtime.index("$disableProof = Disable-OwnScheduledTask")
    assert runtime.index('"completion_receipt.json"') < runtime.index(
        "$disableProof = Disable-OwnScheduledTask"
    )
    assert runtime.index("$disableProof = Disable-OwnScheduledTask") < runtime.index(
        "$completed = $true"
    )
    assert runtime.count("Disable-OwnScheduledTask") == 1


def test_real_file_lock_rejects_a_second_owner_then_allows_resume(
    tmp_path: Path,
) -> None:
    environment = dict(os.environ)
    environment["POST_STAGE3_WRAPPER"] = str(SCRIPT)
    environment["POST_STAGE3_LOCK_ROOT"] = str(tmp_path / "supervision")
    command = (
        "$tokens=$null;$errors=$null;"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:POST_STAGE3_WRAPPER,[ref]$tokens,[ref]$errors);"
        "foreach($name in @('Get-FullPath','Open-CrossSessionLock')){"
        "$node=$ast.Find({param($n)$n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq $name},$true);Invoke-Expression $node.Extent.Text};"
        "$SupervisionDir=$env:POST_STAGE3_LOCK_ROOT;$first=Open-CrossSessionLock;"
        "$rejected=$false;try{$second=Open-CrossSessionLock;$second.Dispose()}"
        "catch{$rejected=$true};if(-not $rejected){exit 15};"
        "$first.Dispose();$third=Open-CrossSessionLock;$third.Dispose();"
        "Write-Output 'FILE_LOCK_RESUME_OK'"
    )
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"FILE_LOCK_RESUME_OK" in completed.stdout


def test_partial_focus_arm_is_classified_manual_without_deletion(
    tmp_path: Path,
) -> None:
    focus = tmp_path / "focus"
    (focus / "runs" / "dossier" / "baseline").mkdir(parents=True)
    (focus / "focus_plan.json").write_text("{}", encoding="utf-8")
    environment = dict(os.environ)
    environment["POST_STAGE3_WRAPPER"] = str(SCRIPT)
    environment["POST_STAGE3_PARTIAL_FOCUS"] = str(focus)
    command = (
        "$tokens=$null;$errors=$null;"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:POST_STAGE3_WRAPPER,[ref]$tokens,[ref]$errors);"
        "foreach($name in @('Get-FullPath','Get-FocusRecoveryAssessment')){"
        "$node=$ast.Find({param($n)$n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq $name},$true);Invoke-Expression $node.Extent.Text};"
        "$FocusRoot=$env:POST_STAGE3_PARTIAL_FOCUS;"
        "$assessment=Get-FocusRecoveryAssessment;"
        "$assessment|ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assessment = json.loads(completed.stdout.decode("utf-8-sig"))
    assert assessment["state"] == (
        "partial_focus_arm_without_receipt_manual_intervention"
    )
    assert assessment["manual_intervention_required"] is True
    assert assessment["automatic_partial_arm_repair"] is False
    assert assessment["automatic_deletion_allowed"] is False
    assert (focus / "runs" / "dossier" / "baseline").is_dir()
    assert (focus / "focus_plan.json").is_file()


def test_rejected_existing_focus_validation_is_classified_manual(
    tmp_path: Path,
) -> None:
    focus = tmp_path / "focus"
    focus.mkdir()
    for name in (
        "focus_plan.json",
        "focus_run_receipt.json",
        "focus_validation.json",
    ):
        (focus / name).write_text("{}", encoding="utf-8")
    environment = dict(os.environ)
    environment["POST_STAGE3_WRAPPER"] = str(SCRIPT)
    environment["POST_STAGE3_REJECTED_FOCUS"] = str(focus)
    command = (
        "$tokens=$null;$errors=$null;"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:POST_STAGE3_WRAPPER,[ref]$tokens,[ref]$errors);"
        "foreach($name in @('Get-FullPath','Get-FocusRecoveryAssessment')){"
        "$node=$ast.Find({param($n)$n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq $name},$true);Invoke-Expression $node.Extent.Text};"
        "$FocusRoot=$env:POST_STAGE3_REJECTED_FOCUS;"
        "$assessment=Get-FocusRecoveryAssessment -FailedStep "
        "'06_focus_validate' -FocusValidationSucceeded $false;"
        "$assessment|ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assessment = json.loads(completed.stdout.decode("utf-8-sig"))
    assert assessment["state"] == (
        "focus_validation_present_but_rejected_manual_intervention"
    )
    assert assessment["manual_intervention_required"] is True
    assert {path.name for path in focus.iterdir()} == {
        "focus_plan.json",
        "focus_run_receipt.json",
        "focus_validation.json",
    }


def test_disable_function_targets_only_the_mocked_exact_task() -> None:
    environment = dict(os.environ)
    environment["POST_STAGE3_WRAPPER"] = str(SCRIPT)
    command = (
        "$tokens=$null;$errors=$null;"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:POST_STAGE3_WRAPPER,[ref]$tokens,[ref]$errors);"
        "$node=$ast.Find({param($n)$n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq 'Disable-OwnScheduledTask'},$true);"
        "Invoke-Expression $node.Extent.Text;"
        "$TaskName='Codex-Supplier-V8-Post-Stage3-Final-V4';$TaskPath='\\';"
        "$script:disableCalls=0;"
        "function Assert-OwnScheduledTask{[pscustomobject]@{State='Running'}};"
        "function Disable-ScheduledTask{param($TaskName,$TaskPath,$ErrorAction);"
        "$script:disableCalls++;if($TaskName -ne "
        "'Codex-Supplier-V8-Post-Stage3-Final-V4' -or $TaskPath -ne '\\'){exit 8}};"
        "function Get-ScheduledTask{param($TaskName,$TaskPath,$ErrorAction);"
        "[pscustomobject]@{State='Running';Settings=[pscustomobject]@{Enabled=$false}}};"
        "$proof=Disable-OwnScheduledTask;"
        "if($script:disableCalls -ne 1 -or $proof.definition_enabled -ne $false "
        "-or $proof.task_name -ne 'Codex-Supplier-V8-Post-Stage3-Final-V4'){exit 9};"
        "Write-Output 'SELF_DISABLE_MOCK_OK'"
    )
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"SELF_DISABLE_MOCK_OK" in completed.stdout


def test_successful_disable_is_terminal_even_if_read_only_postcheck_fails() -> None:
    environment = dict(os.environ)
    environment["POST_STAGE3_WRAPPER"] = str(SCRIPT)
    command = (
        "$tokens=$null;$errors=$null;"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:POST_STAGE3_WRAPPER,[ref]$tokens,[ref]$errors);"
        "$node=$ast.Find({param($n)$n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq 'Disable-OwnScheduledTask'},$true);"
        "Invoke-Expression $node.Extent.Text;"
        "$TaskName='Codex-Supplier-V8-Post-Stage3-Final-V4';$TaskPath='\\';"
        "$script:disableCalls=0;$script:getCalls=0;"
        "function Assert-OwnScheduledTask{[pscustomobject]@{State='Running'}};"
        "function Disable-ScheduledTask{param($TaskName,$TaskPath,$ErrorAction);"
        "$script:disableCalls++};"
        "function Get-ScheduledTask{param($TaskName,$TaskPath,$ErrorAction);"
        "$script:getCalls++;throw 'postcheck unavailable'};"
        "$proof=Disable-OwnScheduledTask;"
        "if($script:disableCalls -ne 1 -or $script:getCalls -ne 1 "
        "-or $proof.disable_command_succeeded -ne $true "
        "-or $proof.definition_enabled -ne $null "
        "-or $proof.postcheck -ne "
        "'unavailable_after_successful_disable_command'){exit 16};"
        "Write-Output 'DISABLE_POSTCHECK_FAILURE_TERMINAL_OK'"
    )
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"DISABLE_POSTCHECK_FAILURE_TERMINAL_OK" in completed.stdout


def test_successful_disable_is_terminal_even_if_postcheck_reads_enabled() -> None:
    environment = dict(os.environ)
    environment["POST_STAGE3_WRAPPER"] = str(SCRIPT)
    command = (
        "$tokens=$null;$errors=$null;"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:POST_STAGE3_WRAPPER,[ref]$tokens,[ref]$errors);"
        "$node=$ast.Find({param($n)$n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq 'Disable-OwnScheduledTask'},$true);"
        "Invoke-Expression $node.Extent.Text;"
        "$TaskName='Codex-Supplier-V8-Post-Stage3-Final-V4';$TaskPath='\\';"
        "$script:disableCalls=0;"
        "function Assert-OwnScheduledTask{[pscustomobject]@{State='Running'}};"
        "function Disable-ScheduledTask{param($TaskName,$TaskPath,$ErrorAction);"
        "$script:disableCalls++};"
        "function Get-ScheduledTask{param($TaskName,$TaskPath,$ErrorAction);"
        "[pscustomobject]@{State='Ready';Settings=[pscustomobject]@{Enabled=$true}}};"
        "$proof=Disable-OwnScheduledTask;"
        "if($script:disableCalls -ne 1 "
        "-or $proof.disable_command_succeeded -ne $true "
        "-or $proof.definition_enabled -ne $true "
        "-or $proof.postcheck -ne "
        "'unexpected_enabled_after_successful_disable_command'){exit 17};"
        "Write-Output 'DISABLE_ENABLED_POSTCHECK_TERMINAL_OK'"
    )
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=REPO,
        env=environment,
        check=False,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"DISABLE_ENABLED_POSTCHECK_TERMINAL_OK" in completed.stdout


def test_keep_awake_stop_failure_cannot_skip_status_or_lock_release() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    runtime = source.split("# Runtime starts only", maxsplit=1)[1]
    finalizer = runtime.rsplit("finally {", maxsplit=1)[1]
    stop = finalizer.index("Stop-PostStage3KeepAwake")
    status = finalizer.index("Write-PostStage3Status")
    file_lock = finalizer.index("$crossSessionLock.Dispose()")
    mutex = finalizer.index("$mutex.ReleaseMutex()")
    assert stop < status < file_lock < mutex
    assert '$keepAwakeStopError = ""' in finalizer
    assert "$keepAwakeStopError = [string]$_.Exception.Message" in finalizer
    assert "try { $crossSessionLock.Dispose() } catch { }" in finalizer
    assert "try { $mutex.ReleaseMutex() } catch { }" in finalizer
    assert "try { $mutex.Dispose() } catch { }" in finalizer


def test_defaults_point_to_the_dedicated_additive_roots() -> None:
    source = SCRIPT.read_text(encoding="utf-8-sig")
    assert "supplier_v8_stage3_supervision_20260906_v3" in source
    assert (
        "supplier_v8_stage3_closure_supervision_20260906_v1\\closure_report.json"
        in source
    )
    assert "supplier_v8_post_stage3_focus_338929_20260906_v1" in source
    assert "supplier_v8_post_stage3_delivery_20260906_v4" in source
    assert "supplier_v8_post_stage3_delivery_supervision_20260906_v1" in source
    assert '$ExpectedTaskName = "Codex-Supplier-V8-Post-Stage3-Final-V4"' in source
    assert "$TaskName -ne $ExpectedTaskName" in source
    assert "DEMONSTRATION_REUNION_1500_20260904_v1" in source
    assert "industrial_supply_preliminary_consolidated_20260904_v4" in source
    assert "supplier_operating_point_full_campaign_v8_results_20260906_v2" in source
