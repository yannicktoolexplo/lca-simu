from __future__ import annotations

import json
import shutil

from PIL import Image

from etudecas_agentkit.cli import run

from .conftest import ROOT


def test_end_to_end_case_runs(tmp_path):
    # A clean case cannot accidentally pass because of an old global report.
    for name in ("configs", "data"):
        shutil.copytree(ROOT / name, tmp_path / name)
    first = run(tmp_path / "configs/cases/example_minimal.yaml")
    second = run(tmp_path / "configs/cases/example_minimal.yaml")
    assert first != second
    for output in (first, second):
        assert output.is_relative_to(tmp_path / "outputs/example_minimal")
        result = json.loads((output / "validation_report.json").read_text(encoding="utf-8"))
        assert result["status"] != "reject"
        with Image.open(output / "trajectory_3d.png") as image:
            image.verify()
    assert not (tmp_path / "outputs/reports/validation_report.json").exists()
