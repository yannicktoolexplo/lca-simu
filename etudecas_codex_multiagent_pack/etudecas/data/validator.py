from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from etudecas.validation.report import ValidationReport


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
            return converted
        if rule.type == "datetime":
            converted = pd.to_datetime(series, errors="coerce")
            invalid = int(converted.isna().sum() - series.isna().sum())
            if invalid:
                report.add_issue("critical", f"Invalid datetime values in {rule.name}", column=rule.name, count=invalid)
            return converted
        return series
