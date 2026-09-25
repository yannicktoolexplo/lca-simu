from concurrent.futures import ThreadPoolExecutor
import csv
import json
from pathlib import Path

import pytest

from etudecas import atomic_io


def windows_error(code):
    error = PermissionError("simulated Windows refusal")
    error.winerror = code
    return error


@pytest.mark.parametrize("code", [5, 32, 33])
def test_transient_replacement_preserves_old_file_until_success(tmp_path, monkeypatch, code):
    destination = tmp_path / "ledger.json"
    destination.write_text('{"old": true}', encoding="utf-8")
    replace = atomic_io.os.replace
    attempts = []
    sleeps = []

    def locked(source, target):
        attempts.append(Path(source))
        assert json.loads(destination.read_text()) == {"old": True}
        assert json.loads(Path(source).read_text()) == {"new": True}
        if len(attempts) < 3:
            raise windows_error(code)
        replace(source, target)

    monkeypatch.setattr(atomic_io.os, "replace", locked)
    monkeypatch.setattr(atomic_io.time, "sleep", sleeps.append)
    atomic_io.write_json_atomic(destination, {"new": True})
    assert json.loads(destination.read_text()) == {"new": True}
    assert sleeps == [0.05, 0.10]
    assert len(set(attempts)) == 1
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize("code,attempt_count", [(5, 6), (32, 6), (33, 6), (112, 1), (None, 1)])
def test_persistent_or_unrelated_failure_propagates(tmp_path, monkeypatch, code, attempt_count):
    destination = tmp_path / "ledger.json"
    destination.write_bytes(b"unchanged")
    error = windows_error(code)
    attempts = []
    sleeps = []

    def fail(source, target):
        attempts.append(source)
        raise error

    monkeypatch.setattr(atomic_io.os, "replace", fail)
    monkeypatch.setattr(atomic_io.time, "sleep", sleeps.append)
    with pytest.raises(PermissionError) as caught:
        atomic_io.write_json_atomic(destination, {"new": True})
    assert caught.value is error
    assert len(attempts) == attempt_count
    assert len(sleeps) == attempt_count - 1
    assert destination.read_bytes() == b"unchanged"
    assert list(tmp_path.iterdir()) == [destination]


def test_serialization_failure_preserves_destination(tmp_path):
    destination = tmp_path / "ledger.json"
    destination.write_bytes(b"unchanged")
    with pytest.raises(TypeError):
        atomic_io.write_json_atomic(destination, {"bad": object()})
    assert destination.read_bytes() == b"unchanged"
    assert list(tmp_path.iterdir()) == [destination]


def test_flush_failure_does_not_publish(tmp_path, monkeypatch):
    destination = tmp_path / "ledger.json"
    def fail(fd):
        raise OSError("disk full")
    monkeypatch.setattr(atomic_io.os, "fsync", fail)
    with pytest.raises(OSError, match="disk full"):
        atomic_io.write_json_atomic(destination, {"new": True})
    assert list(tmp_path.iterdir()) == []


def test_cleanup_failure_keeps_original_exception(tmp_path, monkeypatch):
    def fail_unlink(self, **kwargs):
        raise OSError("cleanup refused")
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(TypeError) as caught:
        atomic_io.write_json_atomic(tmp_path / "ledger.json", {"bad": object()})
    assert "cleanup refused" in caught.value.__notes__[0]


def test_concurrent_writers_publish_complete_payloads(tmp_path):
    destination = tmp_path / "ledger.json"
    payloads = [{"writer": i, "text": str(i) * 10000} for i in range(12)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda payload: atomic_io.write_json_atomic(destination, payload), payloads))
    assert json.loads(destination.read_text()) in payloads
    assert list(tmp_path.iterdir()) == [destination]


def test_csv_columns_quoting_unicode_and_newlines(tmp_path):
    destination = tmp_path / "nested" / "table.csv"
    rows = [{"article": "pièce, A", "note": "ligne 1\nligne 2"}, {"article": "B", "qty": 2}]
    atomic_io.write_csv_atomic(destination, rows)
    with destination.open(encoding="utf-8", newline="") as handle:
        actual = list(csv.DictReader(handle))
    assert actual == [
        {"article": "pièce, A", "note": "ligne 1\nligne 2", "qty": ""},
        {"article": "B", "note": "", "qty": "2"},
    ]
