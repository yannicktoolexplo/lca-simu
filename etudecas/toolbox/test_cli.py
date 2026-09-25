from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from etudecas.toolbox import cli


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    (tmp_path / "etudecas").mkdir()
    (tmp_path / "etudecas/source.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "pytest-reference.ini").write_text("[pytest]\n", encoding="utf-8")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    return tmp_path


def invoke(workspace, *arguments):
    args = cli.parser().parse_args([*arguments, "--output", str(workspace / "etudecas/artifacts/testing/proofs")])
    return cli.execute(args)


@pytest.mark.parametrize("relative", [
    "etudecas/prototypes/scan_2027_risk_control/supplier_campaign_source_revision.json",
    ".gitattributes",
])
def test_gate_rejects_changed_provenance_inputs(workspace, relative):
    revision = workspace / relative
    revision.parent.mkdir(parents=True, exist_ok=True)
    revision.write_text('{"revision":"before"}', encoding="utf-8")
    test = workspace / "etudecas/test_good.py"
    test.write_text("def test_good():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    manifest, result = invoke(workspace, "tests", "--path", str(test))
    assert result["status"] == "passed", result
    assert str(revision) in result["code"]
    revision.write_text('{"revision":"after"}', encoding="utf-8")
    _, refused = invoke(workspace, "gate", "--manifest", str(manifest), "--require", "tests")
    assert refused["status"] == "refused"
    assert "code" in refused["error"].lower()


def test_real_pytest_and_gate_then_reject_tampered_proof(workspace):
    test = workspace / "etudecas/test_good.py"
    test.write_text("def test_sum():\n    assert sum([1, 2]) == 3\n", encoding="utf-8")
    manifest, result = invoke(workspace, "tests", "--path", str(test))
    assert result["status"] == "passed", result
    _, accepted = invoke(workspace, "gate", "--manifest", str(manifest), "--require", "tests")
    assert accepted["status"] == "passed", accepted
    proof = manifest.parent / "result.json"
    proof.write_text("{}", encoding="utf-8")
    _, refused = invoke(workspace, "gate", "--manifest", str(manifest), "--require", "tests")
    assert refused["status"] == "refused"
    assert "Stale or changed proofs" in refused["error"]


def test_real_failing_pytest_cannot_pass_gate(workspace):
    test = workspace / "etudecas/test_bad.py"
    test.write_text("def test_false_claim():\n    assert 1 == 2\n", encoding="utf-8")
    manifest, result = invoke(workspace, "tests", "--path", str(test))
    assert result["status"] == "refused"
    assert result["exit_code"] == 1
    assert (manifest.parent / "junit.xml").exists()
    _, verdict = invoke(workspace, "gate", "--manifest", str(manifest), "--require", "tests")
    assert verdict["status"] == "refused"


def test_all_skipped_is_not_positive_evidence(workspace):
    test = workspace / "etudecas/test_skip.py"
    test.write_text("import pytest\n@pytest.mark.skip(reason='no fixture')\ndef test_skipped():\n    pass\n", encoding="utf-8")
    _, result = invoke(workspace, "tests", "--path", str(test))
    assert result["exit_code"] == 0
    assert result["status"] == "refused"


def test_missing_qualification_inputs_refuses_with_manifest(workspace):
    manifest, result = invoke(workspace, "qualify", "--run", str(workspace / "missing"))
    assert manifest.exists()
    assert result["status"] == "refused"
    assert "Missing input" in result["error"]


def test_timeout_is_recorded_as_refused(workspace, monkeypatch):
    test = workspace / "etudecas/test_wait.py"
    test.write_text("def test_wait(): pass\n", encoding="utf-8")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1)

    monkeypatch.setattr(cli.subprocess, "run", timeout)
    manifest, result = invoke(workspace, "tests", "--path", str(test))
    assert result["status"] == "refused"
    assert "TimeoutExpired" in result["error"]
    assert manifest.exists()


def test_missing_required_kind_and_changed_code_refuse(workspace):
    proof = workspace / "proof.json"
    proof.write_text('{"ok":true}', encoding="utf-8")
    manifest = workspace / "manifest.json"
    cli.write_json(manifest, {"schema": cli.SCHEMA, "run_id": "example", "status": "passed", "command": "tests",
                              "inputs": {}, "code": cli.code_fingerprint(), "proofs": cli.fingerprint([proof])})
    _, missing = invoke(workspace, "gate", "--manifest", str(manifest), "--require", "qualify")
    assert missing["status"] == "refused"
    assert "Required evidence missing" in missing["error"]
    (workspace / "etudecas/new_source.py").write_text("NEW = 2", encoding="utf-8")
    _, changed = invoke(workspace, "gate", "--manifest", str(manifest), "--require", "tests")
    assert changed["status"] == "refused"
    assert "Source set changed" in changed["error"]


def test_doctor_reports_staging_without_claiming_installation(workspace):
    actual = Path(__file__).resolve().parents[2] / "etudecas_codex_multiagent_pack/native"
    staging = workspace / "stage"
    shutil.copytree(actual, staging)
    _, result = invoke(workspace, "doctor", "--native-root", str(staging))
    assert result["status"] == "passed", result
    data = json.loads(Path(next(p for p in result["proofs"] if p.endswith("result.json"))).read_text(encoding="utf-8"))
    assert data["installed_at_repository_root"] is False


def test_arbitrary_cli_options_are_not_test_paths(workspace):
    _, result = invoke(workspace, "tests", "--path=-p")
    assert result["status"] == "refused"


@pytest.mark.parametrize('changed', ['business_source', 'catalog'])
def test_documentation_gate_rejects_changed_business_text_or_catalog(workspace, changed):
    docs = workspace / 'etudecas/docs'
    (docs / 'rules').mkdir(parents=True)
    (docs / 'generated').mkdir()
    source = workspace / 'etudecas/business.md'
    source.write_text('Safety days: Monday-Friday', encoding='utf-8')
    catalog = docs / 'catalog.json'
    catalog.write_text('{}', encoding='utf-8')
    (docs / 'rules/domain.json').write_text(json.dumps({'business_source_fingerprints': {'etudecas/business.md': 'a'*64}}), encoding='utf-8')
    proof = workspace / 'proof.json'
    proof.write_text('{"ok":true}', encoding='utf-8')
    manifest = workspace / 'manifest.json'
    inputs = cli.documentation_inputs()
    cli.write_json(manifest, dict(schema=cli.SCHEMA, run_id='doc-example', status='passed', command='docs',
                   inputs=cli.fingerprint(inputs), input_roots=[str(path) for path in inputs],
                   code=cli.code_fingerprint(), proofs=cli.fingerprint([proof])))
    assert cli.check_manifest(manifest)['status'] == 'passed'
    (source if changed == 'business_source' else catalog).write_text('Changed rule', encoding='utf-8')
    _, refused = invoke(workspace, 'gate', '--manifest', str(manifest), '--require', 'docs')
    assert refused['status'] == 'refused'
    assert 'Stale or changed inputs' in refused['error']


def test_output_cannot_overwrite_application(workspace):
    args = cli.parser().parse_args(["doctor", "--output", str(workspace / "etudecas")])
    with pytest.raises(ValueError, match="Evidence output"):
        cli.execute(args)


def test_handoff_binds_role_task_and_scope(workspace):
    test = workspace / "etudecas/test_contract.py"
    test.write_text("def test_sum():\n    assert 2 + 2 == 4\n", encoding="utf-8")
    manifest, evidence = invoke(workspace, "tests", "--path", str(test), "--task-id", "T1", "--owner", "etudecas_validator")
    assert evidence["status"] == "passed", evidence
    spec = workspace / "task.json"
    result = workspace / "agent.json"
    cli.write_json(spec, {"task_id": "T1", "role": "etudecas_validator", "objective": "Verify arithmetic",
                          "inputs": ["etudecas/source.py"], "writable": ["etudecas/artifacts/testing"],
                          "forbidden": ["etudecas/source.py"], "required_evidence": ["tests"]})
    answer = {"task_id": "T1", "role": "etudecas_validator", "status": "complete", "changed_files": [],
              "manifests": [str(manifest)], "summary": "Independent arithmetic passes", "limitations": ["No model qualification"]}
    cli.write_json(result, answer)
    _, accepted = invoke(workspace, "handoff", "--task-spec", str(spec), "--agent-result", str(result))
    assert accepted["status"] == "passed", accepted
    answer["changed_files"] = ["etudecas/source.py"]
    cli.write_json(result, answer)
    _, outside = invoke(workspace, "handoff", "--task-spec", str(spec), "--agent-result", str(result))
    assert outside["status"] == "refused"
    assert "outside task scope" in outside["error"]
    answer["changed_files"] = []
    answer["task_id"] = "other"
    cli.write_json(result, answer)
    _, mismatch = invoke(workspace, "handoff", "--task-spec", str(spec), "--agent-result", str(result))
    assert mismatch["status"] == "refused"
    assert "identity mismatch" in mismatch["error"]


def test_staged_doctor_cannot_establish_installation(workspace):
    actual = Path(__file__).resolve().parents[2] / "etudecas_codex_multiagent_pack/native"
    staging = workspace / "stage"
    shutil.copytree(actual, staging)
    manifest, result = invoke(workspace, "doctor", "--native-root", str(staging))
    assert result["status"] == "passed", result
    _, gate = invoke(workspace, "gate", "--manifest", str(manifest), "--require", "doctor")
    assert gate["status"] == "refused"
    assert "does not establish repository installation" in gate["error"]


@pytest.mark.parametrize("relative", ["etudecas/map.js", "etudecas/map.css", "etudecas/run_campaign.ps1", "etudecas/config/policy.json", "etudecas/docs/rules/rule.json"])
@pytest.mark.parametrize("already_existed", [False, True])
def test_changed_or_added_presentation_and_configuration_invalidate_evidence(workspace, relative, already_existed):
    source = workspace / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    if already_existed:
        source.write_text("old", encoding="utf-8")
    proof = workspace / "proof.json"
    proof.write_text('{"ok":true}', encoding="utf-8")
    manifest = workspace / "manifest.json"
    cli.write_json(manifest, {"schema": cli.SCHEMA, "run_id": "example", "status": "passed", "command": "tests",
                              "inputs": {}, "code": cli.code_fingerprint(), "proofs": cli.fingerprint([proof])})
    source.write_text("new", encoding="utf-8")
    _, verdict = invoke(workspace, "gate", "--manifest", str(manifest), "--require", "tests")
    assert verdict["status"] == "refused"
    assert "Source set changed" in verdict["error"] or "Stale or changed code" in verdict["error"]
