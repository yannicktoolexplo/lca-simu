from __future__ import annotations

from etudecas_agentkit.validation.visual_checks import VisualValidator


def test_visual_validator_rejects_fake_image(tmp_path):
    path = tmp_path / "figure.png"
    path.write_bytes(b"not really an image but non-empty")
    report = VisualValidator().validate(path, {"labels": {"title": "X"}, "data": {"x": "a", "y": "b"}})
    assert report.status == "reject"


def test_visual_validator_rejects_missing_file(tmp_path):
    report = VisualValidator().validate(tmp_path / "missing.png")
    assert report.status == "reject"


def test_visual_validator_accepts_decodable_image(tmp_path):
    from PIL import Image
    path = tmp_path / "figure.png"
    Image.new("RGB", (20, 20), "white").save(path)
    assert VisualValidator().validate(path).status == "ok"
