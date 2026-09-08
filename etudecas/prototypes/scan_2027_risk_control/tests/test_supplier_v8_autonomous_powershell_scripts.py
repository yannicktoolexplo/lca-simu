from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "LANCER_TRANCHE_A_SANS_CODEX.ps1"
STATUS = ROOT / "VOIR_STATUT_CAMPAGNE.ps1"
STOP = ROOT / "ARRETER_PROPREMENT_CAMPAGNE.ps1"
LAUNCHER_B = ROOT / "LANCER_TRANCHE_B_SANS_CODEX.ps1"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_launcher_is_safe_by_default_and_pins_tranche_a() -> None:
    text = _text(LAUNCHER)
    assert "[switch]$ConfirmerLancement" in text
    assert "if (-not $ConfirmerLancement)" in text
    assert "AUCUN CALCUL LANCE" in text
    assert '"op_100__seed_block_03", "op_100__seed_block_04"' in text
    assert '$SimulationCount = 20' in text
    assert "--execute" in text
    assert "Start-Process" in text
    assert "-WindowStyle Hidden" in text
    assert "Invoke-PreflightWithTimeout" in text
    assert "WaitForExit($TimeoutSeconds * 1000)" in text
    assert "$process.Refresh()" in text
    assert "$preflightExitCode = [int]$process.ExitCode" in text
    assert "$exitCode = [int]$child.ExitCode" in text
    assert '"checkpoint_created_and_validated"' in text
    assert "$scientificSuccess" in text
    assert "initial_probe_work_completed = $initialProbeCompleted" in text
    assert "openai_or_codex_api = $false" in text
    assert "$IndicativeRuntimeSeconds = 32400" in text
    assert "indicative_full_runtime_seconds = $IndicativeRuntimeSeconds" in text
    assert '[ValidateSet("A", "B")][string]$Tranche = "A"' in text
    assert '"op_100__seed_block_05", "op_100__seed_block_06"' in text
    assert "[switch]$SansSuivi" in text
    assert "RafraichissementSecondes = 30" in text
    assert "& $statusScript" in text
    assert "Ctrl+C ferme seulement" in text
    assert "codex exec" not in text.casefold()


def test_launcher_uses_new_checkpoint_and_never_runs_downstream_steps() -> None:
    text = _text(LAUNCHER)
    assert '"supplier_v8_op100_checkpoint_" + $SimulationCount + "_autonome_"' in text
    assert "orchestrate_supplier_v8_bounded_tranche" in text
    forbidden = (
        "finalize_supplier_operating_point",
        "supplier_priority_lot_replay",
        "stage3_pipeline",
        "fred_api",
    )
    for value in forbidden:
        assert value not in text.casefold()


def test_tranche_b_launcher_delegates_to_validated_common_launcher() -> None:
    text = _text(LAUNCHER_B)
    assert "LANCER_TRANCHE_A_SANS_CODEX.ps1" in text
    assert 'Tranche = "B"' in text
    assert "& $commonLauncher @parameters" in text
    assert "[switch]$ConfirmerLancement" in text
    assert '$parameters["ConfirmerLancement"] = $true' in text
    assert "$LASTEXITCODE" not in text
    assert "if (-not $?)" in text
    assert "Start-Process" not in text


def test_status_is_read_only_for_campaign_results() -> None:
    text = _text(STATUS)
    assert "Get-Content" in text
    assert "Get-Process" in text
    assert "Controle initial en cours" in text
    assert "incident_probe_progress.json" in text
    assert "AVANCEMENT GLOBAL DE LA TRANCHE " in text
    assert "Temps restant estime" in text
    assert "Fin estimee" in text
    assert "Format-ProgressBar" in text
    assert "Set-Content" not in text
    assert "Remove-Item" not in text
    assert "Start-Process" not in text


def test_stop_requires_confirmation_and_targets_verified_process_tree() -> None:
    text = _text(STOP)
    assert "[switch]$ConfirmerArret" in text
    assert "if (-not $ConfirmerArret)" in text
    assert "AUCUN ARRET EFFECTUE" in text
    assert "-ModeInterne" in text
    assert '"taskkill.exe"' in text
    assert '"/T"' in text
    assert '"/F"' not in text
    assert "Remove-Item" in text  # Atomic control-file cleanup only.
    assert "files_deleted = $false" in text
