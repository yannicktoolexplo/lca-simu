"""Test the real GO readers without loading either orchestration script body."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("version", ["v3", "v4"])
@pytest.mark.parametrize("case", ["valid", "inventory", "wrapper", "path", "approver", "date", "decision", "missing_binding"])
def test_go_reader_isolated_from_historical_campaign(tmp_path, version, case):
    executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not executable.is_file():
        pytest.skip("Windows PowerShell 5.1 is required for the GO reader")
    source = Path(__file__).parents[1] / f"run_supplier_v8_v2_to_stage3_{version}_chain_task.ps1"
    payload = {
        "schema_version": f"etudecas.supplier_v8_v2_to_stage3_{version}_chain.v1.stage3_go.v1",
        "decision": f"GO_STAGE3_{version.upper()}", "approved_by": "isolated-test-only",
        "approved_at_utc": "2026-09-06T12:30:00+00:00",
        "stage3_inventory_signature": "d56761c3cdd704ec9d31bb2b452ee5dea25e9cdcf1e87c67d787a09e20b5a442",
        "chain_wrapper_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "campaign_root": str(tmp_path / "campaign"), "results_dir": str(tmp_path / "results"),
        "stage3_supervision_dir": str(tmp_path / "supervision"), "final_html": str(tmp_path / "final.html"),
    }
    if case == "inventory": payload["stage3_inventory_signature"] = "0" * 64
    if case == "wrapper": payload["chain_wrapper_sha256"] = "0" * 64
    if case == "path": payload["campaign_root"] = str(tmp_path / "other")
    if case == "approver": payload["approved_by"] = ""
    if case == "date": payload["approved_at_utc"] = "invalid"
    if case == "decision": payload["decision"] = "WAIT_FOR_EXPLICIT_GO"
    if case == "missing_binding": del payload["chain_wrapper_sha256"]
    go = tmp_path / "test-go.json"
    go.write_text(json.dumps(payload), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    command = r'''
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($env:TEST_WRAPPER,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Source parse failed'}
foreach($name in @('Get-FullPath','Read-JsonShared','Get-JsonProperty','Assert-SamePath','Read-AndValidateStage3Go')) {
    $node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
    if($null -eq $node){throw "Missing function: $name"}
    # An extracted function has no defining script path. Supply that context
    # explicitly; preserve the original validation statements and file hash.
    $definition=$node.Extent.Text.Replace('$PSCommandPath','$env:TEST_WRAPPER')
    Invoke-Expression $definition
}
$Stage3GoSchemaVersion=$env:TEST_SCHEMA
$ExpectedStage3InventorySignature='d56761c3cdd704ec9d31bb2b452ee5dea25e9cdcf1e87c67d787a09e20b5a442'
$CampaignRoot=Join-Path $env:TEST_ROOT 'campaign'
$ResultsDir=Join-Path $env:TEST_ROOT 'results'
$Stage3SupervisionDir=Join-Path $env:TEST_ROOT 'supervision'
$FinalHtml=Join-Path $env:TEST_ROOT 'final.html'
try { Read-AndValidateStage3Go -Path $env:TEST_GO | ConvertTo-Json -Compress }
catch { [Console]::Error.WriteLine($_.Exception.Message); exit 7 }
'''
    result = subprocess.run(
        [str(executable), "-NoProfile", "-NonInteractive", "-Command", command],
        env={**os.environ, "TEST_WRAPPER": str(source), "TEST_ROOT": str(tmp_path),
             "TEST_SCHEMA": payload["schema_version"], "TEST_GO": str(go)},
        cwd=tmp_path, capture_output=True, timeout=30,
    )
    assert result.returncode == (0 if case == "valid" else 7), result.stderr.decode(errors="replace")
    if case == "valid":
        decision = json.loads(result.stdout.decode("utf-8-sig"))
        assert decision["chain_wrapper_sha256"] == payload["chain_wrapper_sha256"]
        assert decision["approved_by"] == "isolated-test-only"
    else:
        expected = {"inventory": b"stage3_inventory_signature", "wrapper": b"chain_wrapper_sha256",
                    "missing_binding": b"chain_wrapper_sha256", "path": b"campaign_root",
                    "approver": b"approbateur", "date": b"Horodatage", "decision": b"GO_STAGE3"}
        assert expected[case] in result.stderr
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
