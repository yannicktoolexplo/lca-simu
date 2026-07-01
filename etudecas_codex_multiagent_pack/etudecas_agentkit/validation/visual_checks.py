from __future__ import annotations

from pathlib import Path
from typing import Any

from etudecas_agentkit.validation.report import ValidationReport


class VisualValidator:
    """Validation objective des fichiers visuels générés."""

    def validate(self, path: str | Path, spec: dict[str, Any] | None = None) -> ValidationReport:
        path = Path(path)
        report = ValidationReport(name="visual_validation")
        if not path.exists():
            report.add_issue("critical", f"Figure file does not exist: {path}")
            return report
        if path.stat().st_size == 0:
            report.add_issue("critical", f"Figure file is empty: {path}")
        if spec:
            labels = spec.get("labels", {})
            if not labels.get("title"):
                report.add_issue("warning", "Figure spec has no title")
            data = spec.get("data", {})
            for axis in ["x", "y"]:
                if axis not in labels and axis not in data:
                    report.add_issue("warning", f"Figure spec has no {axis} axis information")
        if not report.issues:
            report.add_check("visual_file", "passed", path=str(path), size=path.stat().st_size)
        return report
