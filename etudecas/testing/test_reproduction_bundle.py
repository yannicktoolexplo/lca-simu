"""Regression tests grouped by business responsibility; original cases retained."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import sys
import zipfile
import pytest
from etudecas import reproduction_bundle as rb
from etudecas import regenerate as regen
from etudecas.testing.report import main, summarize


# Reproduction bundle

def test_comparison_source_inventory_is_pure_and_excludes_excel_owner_markers():
    assert rb._source_name('etudecas/visualization/maps/source_comparison_view.html')
    assert rb._source_name('etudecas/data/source/Flow_Data_MRP_results.xlsx')
    assert not rb._source_name('etudecas/data/source/~$Flow_Data_MRP_results.xlsx')
    assert not rb._source_name('etudecas/resultats/02_carte_lots_recente.html')


def test_comparison_marker_removal_preserves_original_map_in_memory():
    from etudecas.visualization.maps.portable_diagnostic import (
        COMPARISON_START, COMPARISON_END, strip_comparison,
    )
    original = '<html>\r\n<script>const s="</html>";</script><body>lots</body>\r\n</html>\r\n'
    head, marker, tail = original.rpartition('</html>')
    enriched = head + COMPARISON_START + '<script>comparison</script>' + COMPARISON_END + marker + tail
    assert strip_comparison(enriched) == original
    assert strip_comparison(original) == original
    with pytest.raises(ValueError, match='Ambiguous'):
        strip_comparison(enriched + COMPARISON_START)


def test_comparison_commands_keep_nominal_and_bound_the_two_diagnostics():
    # Read retained inputs only; this path is never created or executed.
    output = regen.ROOT / 'etudecas/artifacts/testing/not_executed_comparison_command'
    commands = regen._comparison_commands(output, 1825)
    assert [name for name, _, _ in commands] == ['nominal', 'retrait_statique_338929', 'dynamique_338929']
    def normalized(command):
        command = command[:]
        command[command.index('--output-dir') + 1] = 'OUTPUT'
        return command
    nominal = normalized(commands[0][2])
    retained = regen._command('nominal', output, 1825)
    retained[retained.index('--output-profile') + 1] = 'full'
    assert nominal == normalized(retained)
    without = nominal[:]
    at = next(i for i in range(len(without)-1) if without[i:i+2] == ['--mrp-static-requirement-pair', 'M-1810,item:338929'])
    del without[at:at+2]
    assert normalized(commands[1][2]) == without
    assert normalized(commands[2][2]) == without + ['--mrp-dynamic-requirement-pair', 'M-1810,item:338929']

def workspace(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    inputs = {
        "etudecas/core.py": b"value = 'current working tree'\n",
        "etudecas/run_campaign.ps1": b"Write-Output 'source script'\r\n",
        "etudecas/data/source/demand.csv": b"day,qty\n0,1\n",
        "etudecas/visualization/maps/vendor/plotly.min.js": b"const offline = true;",
        "etudecas/config/reproduction_20260920/nominal.json": b"{}",
        "etudecas/simulation_prep/result/graph.json": b'{"nodes": []}',
        "etudecas/artifacts/old.csv": b"old results",
        "etudecas/analysis/first_pass/results/old.json": b"{}",
        "etudecas/resultats/old.html": b"old presentation",
        "etudecas/config/reproduction_historique/old.zip": b"not a nested archive",
    }
    for name, content in inputs.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (root / rb.MANIFEST).write_text(json.dumps({"schema": rb.SCHEMA,
                                               "files": [{"path": name} for name in inputs]}))
    command = ["python", "-m", "etudecas.core", "--input",
               str(root / "etudecas/simulation_prep/result/graph.json"),
               "--output-dir", str(root / "etudecas/simulation/result/new")]
    return root, command


def test_capture_extract_recapture_without_git_preserves_inputs_not_outputs(tmp_path):
    root, command = workspace(tmp_path)
    bundle = tmp_path / "bundle.zip"
    result = rb.capture(bundle, [command], root=root)
    assert result["ok"]
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        assert "etudecas/simulation_prep/result/graph.json" in names
        assert "etudecas/data/source/demand.csv" in names
        assert "etudecas/visualization/maps/vendor/plotly.min.js" in names
        assert archive.read("etudecas/run_campaign.ps1") == b"Write-Output 'source script'\r\n"
        assert not any("old" in name for name in names)
        manifest = json.loads(archive.read(rb.MANIFEST))
        assert "${ROOT}/etudecas/simulation_prep/result/graph.json" in manifest["commands"][0]
        assert manifest["commands"][0][-1] == "${RUN_OUTPUT_0}"
    copy = tmp_path / "copy"
    rb.extract(bundle, copy, workspace=tmp_path)
    assert not (copy / ".git").exists()
    assert (copy / "etudecas/run_campaign.ps1").read_bytes() == b"Write-Output 'source script'\r\n"
    (copy / "etudecas/core.py").write_text("value = 'new current bytes'\n")
    moved_command = [v.replace(str(root), str(copy)) for v in command]
    second = tmp_path / "second.zip"
    rb.capture(second, [moved_command], root=copy)
    with zipfile.ZipFile(second) as archive:
        assert b"new current bytes" in archive.read("etudecas/core.py")
        assert archive.read("etudecas/run_campaign.ps1") == b"Write-Output 'source script'\r\n"


def test_refuses_missing_external_input_and_existing_output(tmp_path):
    root, command = workspace(tmp_path)
    with pytest.raises(FileNotFoundError):
        rb.capture(tmp_path / "missing.zip", [command[:4] + ["absent.json"]], root=root)
    external = tmp_path / "external.json"
    external.write_text("{}")
    bad = command.copy()
    bad[4] = str(external)
    with pytest.raises(ValueError, match="outside"):
        rb.capture(tmp_path / "external.zip", [bad], root=root)
    output = tmp_path / "existing.zip"
    output.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        rb.capture(output, [command], root=root)
    assert output.read_bytes() == b"keep"


def test_joined_options_cannot_silently_omit_inputs_or_keep_old_output_paths(tmp_path):
    root, command = workspace(tmp_path)
    joined = command[:3] + [f"--input={command[4]}", f"--output-dir={command[6]}"]
    output = tmp_path / "joined.zip"
    with pytest.raises(ValueError, match="separate argv entries"):
        rb.capture(output, [joined], root=root)
    assert not output.exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/drive", "a\\..\\escape", "a:stream", "CON.txt", "name."])
def test_extract_rejects_unsafe_paths_before_writing(tmp_path, name):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(name, b"bad")
    target = tmp_path / "new"
    with pytest.raises(ValueError):
        rb.extract(archive, target, workspace=tmp_path)
    assert not target.exists()


def test_refuses_symlink_archive_checksum_tampering_and_nonempty_target(tmp_path):
    root, command = workspace(tmp_path)
    bundle = tmp_path / "valid.zip"
    rb.capture(bundle, [command], root=root)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(tampered, "w") as output:
        for name in source.namelist():
            output.writestr(name, b"tampered" if name.endswith("core.py") else source.read(name))
    with pytest.raises(ValueError, match="checksum"):
        rb.verify(tampered)
    symlink = tmp_path / "symlink.zip"
    with zipfile.ZipFile(symlink, "w") as output:
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        output.writestr(info, "elsewhere")
    with pytest.raises(ValueError, match="regular"):
        rb.verify(symlink)
    with pytest.raises(FileExistsError):
        rb.extract(bundle, root, workspace=tmp_path)
    with pytest.raises(ValueError, match="workspace"):
        rb.extract(bundle, tmp_path.parent / "elsewhere", workspace=tmp_path)


def test_concurrent_source_mutation_refuses_and_removes_only_new_archive(tmp_path, monkeypatch):
    root, command = workspace(tmp_path)
    original = rb._inventory
    calls = 0
    def inventory(path):
        nonlocal calls
        calls += 1
        result = original(path)
        if calls == 2:
            (root / "etudecas/new.py").write_text("added = True")
            result[0].add("etudecas/new.py")
        return result
    monkeypatch.setattr(rb, "_inventory", inventory)
    archive = tmp_path / "refused.zip"
    with pytest.raises(ValueError, match="inventory changed"):
        rb.capture(archive, [command], root=root)
    assert not archive.exists()


@pytest.mark.parametrize("names", [("a", "a/b"), ("A", "a")])
def test_ambiguous_windows_member_names_rejected(tmp_path, names):
    archive = tmp_path / "ambiguous.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name in names:
            output.writestr(name, b"content")
    with pytest.raises(ValueError):
        rb.verify(archive)


@pytest.mark.parametrize("scenario", ["nominal", "risques", "securite_150", "acceleration_50"])
def test_regeneration_preserves_every_retained_model_argument(tmp_path, scenario):
    saved = json.loads((regen.CONFIG / f"{scenario}.json").read_text(encoding="utf-8"))
    expected = saved["simulator_command"][:]
    expected[0] = sys.executable
    expected[expected.index("--output-dir") + 1] = str(tmp_path / "new")
    expected.insert(1, "-B")
    assert regen._command(scenario, tmp_path / "new", None) == expected
    assert expected[expected.index("--days") + 1] == "1825"


@pytest.mark.parametrize("delivery", [False, True])
def test_capture_failure_stops_regeneration_before_any_simulation(tmp_path, monkeypatch, delivery):
    def refused(*args, **kwargs):
        raise ValueError("source capture deliberately refused")
    def must_not_run(*args, **kwargs):
        pytest.fail("A simulation started despite the failed source capture")
    output = tmp_path / "new"
    monkeypatch.setattr(regen, "_capture_sources", refused)
    monkeypatch.setattr(regen.subprocess, "run", must_not_run)
    monkeypatch.setattr(sys, "argv", ["regenerate", "--output-dir", str(output)] +
                        (["--delivery", "lots"] if delivery else []))
    with pytest.raises(ValueError, match="deliberately refused"):
        regen.main()
    assert not output.exists()


@pytest.mark.parametrize("delivery", [False, True])
def test_dry_run_neither_captures_sources_nor_creates_outputs(tmp_path, monkeypatch, capsys, delivery):
    def forbidden(*args, **kwargs):
        pytest.fail("A dry run wrote a source bundle or launched a subprocess")
    output = tmp_path / "new"
    monkeypatch.setattr(regen, "_capture_sources", forbidden)
    monkeypatch.setattr(regen.subprocess, "run", forbidden)
    monkeypatch.setattr(sys, "argv", ["regenerate", "--dry-run", "--output-dir", str(output)] +
                        (["--delivery", "lots"] if delivery else []))
    regen.main()
    plan = json.loads(capsys.readouterr().out)
    if delivery:
        assert len(plan["commands"]) == 4
    else:
        assert "--input" in plan
    assert not output.exists()


def test_delivery_bundle_preserves_all_inputs_outside_disposable_results(tmp_path, monkeypatch):
    root, command = workspace(tmp_path)
    monkeypatch.setattr(regen, "ROOT", root)
    monkeypatch.setattr(regen, "CONFIG", root / "etudecas/config/reproduction_20260920")
    commands = []
    inputs = []
    for i in range(4):
        graph = root / f"etudecas/simulation_prep/result/graph_{i}.json"
        graph.write_text(json.dumps({"physical_input": i}))
        inputs.append(graph)
        argv = command.copy()
        argv[4], argv[6] = str(graph), str(root / f"etudecas/simulation/result/run_{i}")
        commands.append(argv)
    output = root / "etudecas/simulation/result/new"
    result = regen._capture_sources(output, commands)
    archive = root / result["archive"]
    assert archive.is_relative_to(regen.CONFIG / "sources")
    assert not archive.is_relative_to(output)
    assert result["archive_sha256"] == rb.verify(archive)["archive_sha256"]
    assert json.loads((output / "source-bundle.json").read_text()) == result
    with zipfile.ZipFile(archive) as zipped:
        manifest = json.loads(zipped.read(rb.MANIFEST))
        assert len(manifest["commands"]) == 4
        for graph in inputs:
            assert zipped.read(graph.relative_to(root).as_posix()) == graph.read_bytes()


@pytest.mark.parametrize("name", ["etudecas/core.py", "etudecas/run_campaign.ps1", "etudecas/simulation_prep/result/graph.json"])
@pytest.mark.parametrize("operation", ["modify", "remove"])
def test_verify_current_refuses_changed_or_missing_captured_file(tmp_path, name, operation):
    root, command = workspace(tmp_path)
    archive = tmp_path / "current.zip"
    rb.capture(archive, [command], root=root)
    assert rb.verify_current(archive, root=root)["current_sources_verified"]
    target = root / name
    if operation == "modify":
        target.write_bytes(target.read_bytes() + b"changed")
    else:
        target.unlink()
    with pytest.raises(ValueError, match="changed|missing"):
        rb.verify_current(archive, root=root)


@pytest.mark.parametrize("name", ["etudecas/new.py", "etudecas/new_campaign.ps1", "etudecas/visualization/new.js", "etudecas/config/new.json", "etudecas/data/source/new.csv"])
def test_verify_current_refuses_new_runtime_or_input(tmp_path, name):
    root, command = workspace(tmp_path)
    archive = tmp_path / "current.zip"
    rb.capture(archive, [command], root=root)
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("new file")
    with pytest.raises(ValueError, match="New runtime/source files"):
        rb.verify_current(archive, root=root)


@pytest.mark.parametrize("relative", [True, False])
def test_verify_current_accepts_declared_outputs_without_masking_other_additions(tmp_path, relative):
    root, command = workspace(tmp_path)
    output = root / "etudecas/custom_output"
    command[-1] = "etudecas/unused/../custom_output" if relative else str(output)
    archive = tmp_path / "current.zip"
    rb.capture(archive, [command], root=root)
    output.mkdir()
    (output / "summary.json").write_text("{}")
    (output / "daily.csv").write_text("day,qty\n0,1\n")
    (output / "viewer.js").write_text("const generated = true;")
    assert rb.verify_current(archive, root=root)["ok"]
    sibling = root / "etudecas/custom_output_extra.py"
    sibling.write_text("new_source = True")
    with pytest.raises(ValueError, match="New runtime/source files"):
        rb.verify_current(archive, root=root)


def test_verify_current_does_not_exempt_captured_sources_inside_output_directory(tmp_path):
    root, command = workspace(tmp_path)
    command[-1] = str(root / "etudecas")
    archive = tmp_path / "current.zip"
    rb.capture(archive, [command], root=root)
    (root / "etudecas/core.py").write_text("changed_source = True")
    with pytest.raises(ValueError, match="Captured source or input changed"):
        rb.verify_current(archive, root=root)


def test_changed_input_during_run_prevents_recording_a_successful_reproduction(tmp_path, monkeypatch):
    from types import SimpleNamespace

    root, command = workspace(tmp_path)
    config = root / "etudecas/config/reproduction_20260920"
    (config / "nominal.json").write_text(json.dumps({"simulator_command": command + ["--days", "1"]}))
    output = root / "etudecas/simulation/result/new"
    def altered_during_simulation(*args, **kwargs):
        Path(command[4]).write_text('{"nodes": ["altered while running"]}')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(regen, "ROOT", root)
    monkeypatch.setattr(regen, "CONFIG", config)
    monkeypatch.setattr(regen.subprocess, "run", altered_during_simulation)
    monkeypatch.setattr(sys, "argv", ["regenerate", "--output-dir", str(output)])
    with pytest.raises(ValueError, match="Captured source or input changed"):
        regen.main()
    assert (output / "source-bundle.json").is_file()
    assert not (output / "run_manifest.json").exists()


# Report

def test_report_preserves_setup_errors_failures_skips_and_successes(tmp_path):
    source = tmp_path / "results.xml"
    source.write_text('''<testsuites><testsuite>
      <testcase classname="engine" name="ok"/>
      <testcase classname="engine" name="wrong"><failure message="assertion">trace</failure></testcase>
      <testcase classname="fixtures" name="setup"><error message="missing file">details</error></testcase>
      <testcase classname="historical" name="old"><skipped message="explicit opt-in"/></testcase>
    </testsuite></testsuites>''', encoding="utf-8")
    output = tmp_path / "summary.json"
    assert main(["--junit", str(source), "--output", str(output)]) == 1
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["counts"] == {"passed": 1, "failure": 1, "error": 1, "skipped": 1}
    assert result["failures"][0]["detail"] == "trace"
    assert result["failures"][1]["name"] == "setup"
    assert result["skip_reasons"] == {"explicit opt-in": 1}


def test_empty_or_invalid_report_is_not_success(tmp_path):
    source = tmp_path / "results.xml"
    for content in ("<broken", "<testsuite/>", "<other/>"):
        source.write_text(content, encoding="utf-8")
        assert main(["--junit", str(source), "--output", str(tmp_path / "report.json")]) == 2


def test_single_suite_and_parameterized_names_are_preserved(tmp_path):
    source = tmp_path / "results.xml"
    source.write_text('<testsuite><testcase classname="module.Class" name="test[a-b]"/></testsuite>', encoding="utf-8")
    assert summarize(source)["counts"] == {"passed": 1}
    assert main(["--junit", str(source), "--output", str(tmp_path / "report.json")]) == 0


def test_multiple_failure_diagnostics_are_not_lost(tmp_path):
    source = tmp_path / "results.xml"
    source.write_text('<testsuite><testcase name="subtests"><failure message="first"/>'
                      '<failure message="second"/></testcase></testsuite>', encoding="utf-8")
    result = summarize(source)
    assert result["counts"] == {"failure": 1}
    assert [row["message"] for row in result["failures"]] == ["first", "second"]
