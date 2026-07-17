"""Read and resolve artifacts from a generic simulation run package."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class RunPackage:
    package_dir: Path
    manifest: dict[str, Any]
    artifacts: list[dict[str, Any]]

    @property
    def output_dir(self) -> Path:
        value = self.manifest.get("output_dir")
        if value:
            return Path(str(value))
        return self.package_dir.parent

    def artifact(self, *, name: str | None = None, domain: str | None = None) -> dict[str, Any] | None:
        for row in self.artifacts:
            if not isinstance(row, dict) or not row.get("exists"):
                continue
            if name and row.get("name") == name:
                return row
            if domain and row.get("domain") == domain:
                return row
        return None

    def artifact_path(self, *, name: str | None = None, domain: str | None = None) -> Path | None:
        row = self.artifact(name=name, domain=domain)
        if not row:
            return None
        raw_path = Path(str(row.get("path") or ""))
        if raw_path.is_absolute():
            return raw_path
        return self.output_dir / raw_path

    def require_artifact_path(self, *, name: str | None = None, domain: str | None = None) -> Path:
        path = self.artifact_path(name=name, domain=domain)
        if path and path.exists():
            return path
        label = name or domain or "artifact"
        raise FileNotFoundError(f"Run package artifact not found: {label}")


def load_run_package(package_dir: Path | str) -> RunPackage:
    root = Path(package_dir)
    manifest = _read_json(root / "run_manifest.json")
    artifacts = _read_json(root / "artifact_index.json")
    if not isinstance(manifest, dict):
        raise ValueError(f"Invalid run manifest: {root / 'run_manifest.json'}")
    if not isinstance(artifacts, list):
        raise ValueError(f"Invalid artifact index: {root / 'artifact_index.json'}")
    return RunPackage(package_dir=root, manifest=manifest, artifacts=artifacts)
