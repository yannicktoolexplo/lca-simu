from __future__ import annotations

from operator import ge, gt, le, lt, eq, ne
from typing import Any, Callable

import pandas as pd

from etudecas.validation.report import ValidationReport

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
        for column in spec.get("columns", []):
            if column not in df.columns:
                continue
            bad = df[(df[column] < low) | (df[column] > high)]
            if not bad.empty:
                report.add_issue("critical", f"Score out of bounds: {column}", column=column, count=len(bad))

    def _check_no_nan(self, df: pd.DataFrame, report: ValidationReport) -> None:
        spec = self.rules.get("no_nan", {})
        if not spec.get("enabled", False):
            return
        counts = df.isna().sum()
        for column, count in counts[counts > 0].items():
            report.add_issue("critical", f"NaN found in result column: {column}", column=column, count=int(count))

    def _check_temporal_order(self, df: pd.DataFrame, report: ValidationReport) -> None:
        spec = self.rules.get("temporal_order", {})
        if not spec.get("enabled", False):
            return
        time_column = spec.get("time_column")
        entity_column = spec.get("entity_column")
        if time_column not in df.columns:
            return
        frame = df.copy()
        frame[time_column] = pd.to_datetime(frame[time_column])
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
