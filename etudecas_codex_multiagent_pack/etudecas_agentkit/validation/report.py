from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass
class ValidationReport:
    name: str = "validation"
    issues: list[dict[str, Any]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)

    def add_issue(self, severity: str, message: str, **metadata: Any) -> None:
        self.issues.append({"severity": severity, "message": message, **metadata})

    def add_check(self, name: str, status: str, **metadata: Any) -> None:
        self.checks.append({"name": name, "status": status, **metadata})

    @property
    def status(self) -> str:
        if any(issue["severity"] == "critical" for issue in self.issues):
            return "reject"
        if self.issues:
            return "warning"
        return "ok"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "issues": self.issues, "checks": self.checks}

    def write_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path
