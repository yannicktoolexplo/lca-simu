"""Generic sensitivity study contracts and result normalization."""

from .designs import ScenarioDesign, build_scenario_designs, write_scenario_design_csv
from .discovery import consolidate_case_csvs, discover_case_csvs
from .materialize import materialize_cases
from .results import ingest_case_csvs, normalize_metric_row, summarize_metrics
from .schema import ParameterSpec, StudySpec

__all__ = [
    "ParameterSpec",
    "ScenarioDesign",
    "StudySpec",
    "build_scenario_designs",
    "consolidate_case_csvs",
    "discover_case_csvs",
    "ingest_case_csvs",
    "materialize_cases",
    "normalize_metric_row",
    "summarize_metrics",
    "write_scenario_design_csv",
]
