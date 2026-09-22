"""Exercise historical-test opt-in through real isolated pytest sessions."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("mode", ["default", "missing", "present", "exclude"])
def test_historical_fixture_policy(tmp_path, mode):
    (tmp_path / "conftest.py").write_bytes(Path(__file__).with_name("conftest.py").read_bytes())
    (tmp_path / "test_sample.py").write_text(
        "def test_external(historical_artifact):\n"
        "    assert historical_artifact('evidence.txt').read_text() == 'fixture'\n"
        "def test_local():\n"
        "    assert True\n", encoding="utf-8",
    )
    arguments = []
    if mode in ("missing", "present"):
        evidence = tmp_path / "artifacts"
        evidence.mkdir()
        if mode == "present":
            (evidence / "evidence.txt").write_text("fixture", encoding="utf-8")
        arguments = ["--historical-artifacts", str(evidence)]
    if mode == "exclude":
        arguments = ["-m", "not historical"]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "test_sample.py", "-q", *arguments],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTEST_ADDOPTS": ""},
    )
    assert result.returncode == (1 if mode == "missing" else 0), result.stdout + result.stderr
    expected = {"default": "1 passed, 1 skipped", "missing": "1 failed, 1 passed",
                "present": "2 passed", "exclude": "1 passed, 1 deselected"}
    assert expected[mode] in result.stdout, result.stdout


@pytest.mark.parametrize("mode", ["default", "no_repo", "relocated"])
def test_frozen_wrapper_environment_requires_explicit_original_paths(tmp_path, mode):
    (tmp_path / "conftest.py").write_bytes(Path(__file__).with_name("conftest.py").read_bytes())
    (tmp_path / "test_sample.py").write_text(
        "def test_wrapper(frozen_wrapper_environment):\n    assert False, 'must not reach wrapper'\n",
        encoding="utf-8",
    )
    arguments = []
    if mode != "default":
        root = tmp_path / "artifacts"
        root.mkdir()
        arguments = ["--historical-artifacts", str(root)]
        if mode == "relocated":
            arguments += ["--historical-wrapper-repo", str(tmp_path)]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "test_sample.py", "-q", *arguments],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTEST_ADDOPTS": ""},
    )
    assert result.returncode == (0 if mode == "default" else 1), result.stdout + result.stderr
    expected = {"default": "1 skipped", "no_repo": "also requires --historical-wrapper-repo",
                "relocated": "relocation is not supported"}
    assert expected[mode] in result.stdout
