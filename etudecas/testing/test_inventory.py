import hashlib
import json

import pytest

from etudecas.testing.inventory import compare_inventory


def reference(tmp_path, rows, repo=None):
    payload = {"entries": rows, "entry_count": len(rows), "repo": str(repo or tmp_path)}
    signature = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                          separators=(",", ":")).encode()).hexdigest()
    payload["inventory_signature"] = signature
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, signature


def test_inventory_distinguishes_representation_content_and_missing_without_writes(tmp_path):
    rows = []
    for name, raw in [("exact.py", b"x\n"), ("windows.py", b"x\r\n"),
                      ("changed.py", b"y\n"), ("missing.py", None)]:
        if raw is not None:
            (tmp_path / name).write_bytes(raw)
        rows.append({"relative_path": name, "sha256": hashlib.sha256(b"x\n").hexdigest(), "size_bytes": 2})
    path, signature = reference(tmp_path, rows, repo="historical-root")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = compare_inventory(tmp_path, path, signature)
    assert result["counts"] == {"exact_match": 1, "line_endings_only": 1, "content_mismatch": 1, "missing": 1}
    assert not result["repo_matches"] and not result["exact_match"]
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="signature"):
        compare_inventory(tmp_path, path, "0" * 64)


@pytest.mark.parametrize("name", ["../outside.py", "C:/outside.py", "/outside.py"])
def test_inventory_rejects_escaping_paths(tmp_path, name):
    path, signature = reference(tmp_path, [{"relative_path": name, "sha256": "0" * 64, "size_bytes": 0}])
    with pytest.raises(ValueError, match="path"):
        compare_inventory(tmp_path, path, signature)
