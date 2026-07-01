from __future__ import annotations

import argparse
from pathlib import Path

from etudecas_agentkit.core.case import CaseStudy
from etudecas_agentkit.core.config_loader import load_yaml
from etudecas_agentkit.data.loader import DataLoader
from etudecas_agentkit.data.validator import DataValidator
from etudecas_agentkit.kpi.engine import KPIEngine
from etudecas_agentkit.trajectory.builder import TrajectoryBuilder
from etudecas_agentkit.validation.result_checks import ResultValidator
from etudecas_agentkit.visualization.figure_factory import FigureFactory


def run(case_path: str | Path) -> None:
    case = CaseStudy.from_yaml(case_path)
    df = DataLoader.load_csv(case.resolve_path(case.data_config["path"]))

    schema = load_yaml(case.resolve_path(case.data_config["schema"]))
    data_report = DataValidator(schema).validate(df)
    if data_report.status == "reject":
        raise SystemExit(f"Dataset rejeté: {data_report.to_dict()}")

    kpi_df = KPIEngine(case.kpi_tree).compute(df)
    trajectory = TrajectoryBuilder(case.trajectory_config).build(kpi_df)

    validation_rules = load_yaml(case.resolve_path(case.validation_rules_path))
    validation_report = ResultValidator(validation_rules).validate(kpi_df)
    validation_report.write_json(case.resolve_path("outputs/reports/validation_report.json"))

    for visual_path in case.visuals.values():
        spec = load_yaml(case.resolve_path(visual_path))
        FigureFactory(spec).render(trajectory, base_dir=case.base_dir)

    print("Case executed")
    print(f"case_id={case.case_id}")
    print(f"data_status={data_report.status}")
    print(f"validation_status={validation_report.status}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an etudecas case study.")
    parser.add_argument("case", help="Path to case YAML file")
    args = parser.parse_args()
    run(args.case)


if __name__ == "__main__":
    main()
