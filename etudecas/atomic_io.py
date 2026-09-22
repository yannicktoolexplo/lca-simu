"""Single-file atomic publication with bounded retries for Windows locks.

This is not a multi-file transaction or a substitute for a campaign lock.
The destination is never removed before replacement. Persistent errors propagate.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Mapping, Sequence, TextIO

POLICY_VERSION = "etudecas.atomic_io.v1"
# Six replacement attempts, with at most 1.55 seconds of requested waiting.
RETRY_DELAYS = (0.05, 0.10, 0.20, 0.40, 0.80)
WINDOWS_RETRY_ERRORS = frozenset({5, 32, 33})


def _replace_with_retry(temporary: Path, destination: Path) -> None:
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            os.replace(temporary, destination)
            return
        except OSError as exc:
            if (
                getattr(exc, "winerror", None) not in WINDOWS_RETRY_ERRORS
                or attempt == len(RETRY_DELAYS)
            ):
                raise
            time.sleep(RETRY_DELAYS[attempt])


def _write_atomic(path: Path, serialize: Callable[[TextIO], None], *, newline: str | None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # Same directory keeps replacement on the same filesystem; unique names
        # prevent two writers from sharing a partially written temporary file.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline=newline,
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            serialize(handle)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_retry(temporary, path)
    except BaseException as exc:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as cleanup_error:
                exc.add_note(f"Temporary file cleanup failed: {temporary}: {cleanup_error}")
        raise


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    _write_atomic(
        path,
        lambda handle: json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True),
        newline=None,
    )


def write_csv_atomic(
    path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] | None = None,
) -> None:
    fieldnames = list(fields) if fields is not None else list(dict.fromkeys(
        str(key) for row in rows for key in row
    ))

    def serialize(handle: TextIO) -> None:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    _write_atomic(path, serialize, newline="")
