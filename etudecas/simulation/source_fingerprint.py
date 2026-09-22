"""Conservative source inventory for cache invalidation (not qualification)."""
from __future__ import annotations

import hashlib
from pathlib import Path


def implementation_files(run_script: Path) -> list[Path]:
    script = run_script.resolve()
    # Include sibling packages and case configuration, including dynamically
    # imported modules. An unrelated source edit may invalidate a cache; omitting
    # a runtime dependency must not leave an old result reusable.
    root = next((p for p in script.parents if p.name == "etudecas"), script.parent)
    excluded = {"result", "results", "artifacts", "__pycache__", ".venv", "tests"}
    return sorted(p for p in root.rglob("*.py")
                  if not excluded.intersection(p.relative_to(root).parts)
                  and not p.name.startswith("test_"))


def implementation_fingerprint(run_script: Path) -> str:
    digest = hashlib.sha256(b"etudecas.application-sources.v2\0")
    for path in implementation_files(run_script):
        digest.update(str(path.resolve()).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
