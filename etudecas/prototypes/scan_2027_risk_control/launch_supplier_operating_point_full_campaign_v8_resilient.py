#!/usr/bin/env python3
"""Run the signed V8 launcher with a resilient additive progress writer.

The V4/V7/V8 launcher sources remain untouched.  This adapter enters the
validated V8 context first and only then replaces the launcher's JSON writer
for the lifetime of the process.  The replacement uses a per-write temporary
file and bounded retries for transient Windows sharing violations.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v8 as launcher_v8,
)


SCHEMA_VERSION = "etudecas.supplier_campaign_v8.resilient_launcher.v1"
MODULE_NAME = (
    "etudecas.prototypes.scan_2027_risk_control."
    "launch_supplier_operating_point_full_campaign_v8_resilient"
)
ADAPTER_PATH = Path(__file__).resolve()
DEFAULT_REPLACE_ATTEMPTS = 12
DEFAULT_REPLACE_BASE_DELAY_SECONDS = 0.05
DEFAULT_REPLACE_MAX_DELAY_SECONDS = 1.0
RETRYABLE_WINDOWS_ERRORS = frozenset({5, 32, 33})

implementation_v4 = launcher_v8.implementation_v4
ReplaceFunction = Callable[
    [str | bytes | os.PathLike[str], str | bytes | os.PathLike[str]],
    Any,
]


def _retryable_replace_error(exc: OSError, *, platform_name: str) -> bool:
    """Return whether *exc* is a transient Windows destination-file collision."""

    if platform_name != "nt":
        return False
    return isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in (
        RETRYABLE_WINDOWS_ERRORS
    )


def resilient_write_json_atomic(
    path: Path,
    payload: Mapping[str, Any],
    *,
    replace: ReplaceFunction = os.replace,
    sleep: Callable[[float], None] = time.sleep,
    token_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
    platform_name: str = os.name,
    attempts: int = DEFAULT_REPLACE_ATTEMPTS,
    base_delay_seconds: float = DEFAULT_REPLACE_BASE_DELAY_SECONDS,
    max_delay_seconds: float = DEFAULT_REPLACE_MAX_DELAY_SECONDS,
) -> None:
    """Write JSON atomically despite bounded transient Windows read locks."""

    if attempts < 1:
        raise ValueError("attempts must be at least one")
    if base_delay_seconds < 0 or max_delay_seconds < 0:
        raise ValueError("retry delays must be non-negative")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    token = token_factory()
    if not token or any(character in token for character in "\\/\0"):
        raise ValueError("token_factory returned an unsafe temporary-file token")
    temporary = destination.with_name(f".{destination.name}.tmp.{os.getpid()}.{token}")
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt_index in range(attempts):
            try:
                replace(temporary, destination)
                return
            except OSError as exc:
                final_attempt = attempt_index + 1 >= attempts
                if final_attempt or not _retryable_replace_error(
                    exc, platform_name=platform_name
                ):
                    raise
                delay = min(
                    max_delay_seconds,
                    base_delay_seconds * (2**attempt_index),
                )
                sleep(delay)
    finally:
        # Do not let cleanup hide the original replace exception.  A unique
        # name also prevents one writer from deleting another writer's temp.
        with suppress(OSError):
            temporary.unlink(missing_ok=True)


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    """Two-argument shim matching the frozen launcher's private callable."""

    resilient_write_json_atomic(path, payload)


def _resilient_detached_command(args: Any) -> list[str]:
    """Ensure optional detachment re-enters this additive adapter."""

    command = [
        implementation_v4.sys.executable,
        str(ADAPTER_PATH),
        "--campaign-root",
        str(args.campaign_root.resolve()),
        "--runner",
        str(args.runner.resolve()),
        "--parallel-shards",
        str(args.parallel_shards),
        "--workers-per-shard",
        str(args.workers_per_shard),
        "--poll-seconds",
        str(args.poll_seconds),
        "--detached-child",
    ]
    for source in args.reuse_evidence_dir:
        command.extend(["--reuse-evidence-dir", str(source.resolve())])
    return command


@contextmanager
def patched_resilient_v8_context() -> Iterator[None]:
    """Validate frozen V8 first, then install and finally restore the patch."""

    # Entering this context performs the complete frozen V8 validation before
    # yielding.  Only code after this line is allowed to monkeypatch V4.
    with launcher_v8.patched_v8_context():
        previous_writer = implementation_v4._write_json_atomic  # noqa: SLF001
        previous_detached_command = implementation_v4._detached_command  # noqa: SLF001
        implementation_v4._write_json_atomic = _write_json_atomic  # noqa: SLF001
        implementation_v4._detached_command = (  # noqa: SLF001
            _resilient_detached_command
        )
        try:
            yield
        finally:
            implementation_v4._write_json_atomic = previous_writer  # noqa: SLF001
            implementation_v4._detached_command = (  # noqa: SLF001
                previous_detached_command
            )


def validate_frozen_implementation() -> Path:
    """Expose the signed V8 validation without installing the additive patch."""

    return launcher_v8.validate_frozen_implementation()


def main(argv: Sequence[str] | None = None) -> int:
    with patched_resilient_v8_context():
        return int(implementation_v4.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
