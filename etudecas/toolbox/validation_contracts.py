"""Contrats génériques de données, résultats et moyennes pondérées.

Ces validations conservent les règles de l'ancienne démonstration ; elles ne
définissent pas les KPI du moteur et ne certifient pas sa calibration industrielle.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import json
import pandas as pd
import numpy as np
from operator import ge, gt, le, lt, eq, ne
import math


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


@dataclass(frozen=True)
class ColumnRule:
    name: str
    type: str = "string"
    required: bool = False
    min: float | None = None
    max: float | None = None


class DataValidator:
    """Valide un DataFrame à partir d’un schema YAML.

    Aucun nom métier n’est codé en dur ici : toutes les règles viennent du schema.
    """

    def __init__(self, schema: dict[str, Any]):
        self.schema = schema
        self.rules = self._parse_rules(schema)

    def validate(self, df: pd.DataFrame) -> ValidationReport:
        report = ValidationReport(name="data_validation")
        for rule in self.rules:
            if rule.name not in df.columns:
                if rule.required:
                    report.add_issue("critical", f"Missing required column: {rule.name}", column=rule.name)
                continue

            series = df[rule.name]
            missing_count = int(series.isna().sum())
            if rule.required and missing_count:
                report.add_issue(
                    "critical",
                    f"Required column contains missing values: {rule.name}",
                    column=rule.name,
                    count=missing_count,
                )

            converted = self._coerce(series, rule, report)
            if rule.min is not None:
                count = int((converted < rule.min).sum())
                if count:
                    report.add_issue(
                        "critical",
                        f"Values below min for {rule.name}: min={rule.min}",
                        column=rule.name,
                        count=count,
                    )
            if rule.max is not None:
                count = int((converted > rule.max).sum())
                if count:
                    report.add_issue(
                        "critical",
                        f"Values above max for {rule.name}: max={rule.max}",
                        column=rule.name,
                        count=count,
                    )

        if not report.issues:
            report.add_check("schema", "passed")
        return report

    def validate_or_raise(self, df: pd.DataFrame) -> pd.DataFrame:
        report = self.validate(df)
        if report.status == "reject":
            raise ValueError(report.to_dict())
        return df

    @staticmethod
    def _parse_rules(schema: dict[str, Any]) -> list[ColumnRule]:
        columns = schema.get("columns", {})
        if not isinstance(columns, dict):
            raise ValueError("schema.columns must be a mapping")
        return [
            ColumnRule(
                name=name,
                type=str(rule.get("type", "string")),
                required=bool(rule.get("required", False)),
                min=rule.get("min"),
                max=rule.get("max"),
            )
            for name, rule in columns.items()
        ]

    @staticmethod
    def _coerce(series: pd.Series, rule: ColumnRule, report: ValidationReport) -> pd.Series:
        if rule.type in {"float", "number", "int", "integer"}:
            converted = pd.to_numeric(series, errors="coerce")
            invalid = int(converted.isna().sum() - series.isna().sum())
            if invalid:
                report.add_issue("critical", f"Invalid numeric values in {rule.name}", column=rule.name, count=invalid)
            nonfinite = converted.notna() & ~np.isfinite(converted)
            fractional = converted.notna() & (converted % 1 != 0) if rule.type in {"int", "integer"} else pd.Series(False, index=series.index)
            if bool((nonfinite | fractional).any()):
                report.add_issue("critical", f"Non-finite or non-integer values in {rule.name}", column=rule.name, count=int((nonfinite | fractional).sum()))
            return converted
        if rule.type == "datetime":
            converted = pd.to_datetime(series, errors="coerce")
            invalid = int(converted.isna().sum() - series.isna().sum())
            if invalid:
                report.add_issue("critical", f"Invalid datetime values in {rule.name}", column=rule.name, count=invalid)
            return converted
        if rule.type != "string":
            raise ValueError(f"Unsupported schema type: {rule.type}")
        return series


OPS: dict[str, Callable[[Any, Any], Any]] = {
    ">": gt,
    ">=": ge,
    "<": lt,
    "<=": le,
    "==": eq,
    "!=": ne,
}


class ResultValidator:
    """Validation automatique des résultats numériques et métier."""

    def __init__(self, rules: dict[str, Any]):
        self.rules = rules

    def validate(self, df: pd.DataFrame) -> ValidationReport:
        report = ValidationReport(name="result_validation")
        self._check_score_bounds(df, report)
        self._check_no_nan(df, report)
        self._check_temporal_order(df, report)
        self._check_business_rules(df, report)
        if not report.issues:
            report.add_check("result_rules", "passed")
        return report

    def _check_score_bounds(self, df: pd.DataFrame, report: ValidationReport) -> None:
        spec = self.rules.get("score_bounds", {})
        if not spec.get("enabled", False):
            return
        low = float(spec.get("min", 0.0))
        high = float(spec.get("max", 1.0))
        if not np.isfinite([low, high]).all() or low > high:
            report.add_issue("critical", "Invalid score bounds")
            return
        for column in spec.get("columns", []):
            if column not in df.columns:
                report.add_issue("critical", f"Missing score column: {column}")
                continue
            values = pd.to_numeric(df[column], errors="coerce")
            bad = df[~np.isfinite(values) | (values < low) | (values > high)]
            if not bad.empty:
                report.add_issue("critical", f"Score out of bounds: {column}", column=column, count=len(bad))

    def _check_no_nan(self, df: pd.DataFrame, report: ValidationReport) -> None:
        spec = self.rules.get("no_nan", {})
        if not spec.get("enabled", False):
            return
        counts = df.isna().sum()
        for column in df.select_dtypes(include="number"):
            count = int((~np.isfinite(df[column])).sum())
            if count:
                report.add_issue("critical", f"Non-finite result: {column}", count=count)
        for column, count in counts[counts > 0].items():
            report.add_issue("critical", f"NaN found in result column: {column}", column=column, count=int(count))

    def _check_temporal_order(self, df: pd.DataFrame, report: ValidationReport) -> None:
        spec = self.rules.get("temporal_order", {})
        if not spec.get("enabled", False):
            return
        time_column = spec.get("time_column")
        entity_column = spec.get("entity_column")
        if time_column not in df.columns or (entity_column and entity_column not in df.columns):
            report.add_issue("critical", "Missing temporal validation columns")
            return
        frame = df.copy()
        frame[time_column] = pd.to_datetime(frame[time_column], errors="coerce")
        if frame[time_column].isna().any():
            report.add_issue("critical", "Invalid temporal values")
        if entity_column in frame.columns:
            groups = frame.groupby(entity_column)
            for label, group in groups:
                if not group[time_column].is_monotonic_increasing:
                    report.add_issue("warning", "Temporal order is not increasing", entity=label)
        elif not frame[time_column].is_monotonic_increasing:
            report.add_issue("warning", "Temporal order is not increasing")

    def _check_business_rules(self, df: pd.DataFrame, report: ValidationReport) -> None:
        for rule in self.rules.get("business_rules", []):
            condition = rule.get("when", {})
            forbidden = rule.get("then_not", {})
            if condition.get("column") not in df.columns or forbidden.get("column") not in df.columns:
                report.add_issue("critical", "Missing business rule columns", rule_id=rule.get("id"))
                continue
            if condition.get("operator", "==") not in OPS or forbidden.get("operator", "==") not in OPS:
                report.add_issue("critical", "Unknown business rule operator", rule_id=rule.get("id"))
                continue
            op_when = OPS[condition.get("operator", "==")]
            op_not = OPS[forbidden.get("operator", "==")]
            mask = op_when(df[condition["column"]], condition.get("value")) & op_not(
                df[forbidden["column"]], forbidden.get("value")
            )
            if bool(mask.any()):
                report.add_issue(
                    rule.get("severity", "warning"),
                    rule.get("description", rule.get("id", "business_rule_failed")),
                    rule_id=rule.get("id"),
                    count=int(mask.sum()),
                )


def weighted_mean(frame: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    missing = [column for column in weights if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns for weighted mean: {missing}")
    if any(type(w) not in (int, float) or not math.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError("Weights must be finite and non-negative")
    if not np.isfinite(frame[list(weights)].to_numpy(dtype=float)).all():
        raise ValueError("Weighted inputs must be finite")
    total = float(sum(weights.values()))
    if total <= 0:
        raise ValueError("Sum of weights must be positive")
    result = sum(frame[column] * weight for column, weight in weights.items()) / total
    return result


def simple_mean(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns for mean: {missing}")
    return frame[columns].mean(axis=1)

