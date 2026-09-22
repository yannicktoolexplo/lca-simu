from __future__ import annotations

import argparse
import re
from uuid import uuid4
from pathlib import Path

from etudecas_agentkit.core.case import CaseStudy
from etudecas_agentkit.core.config_loader import load_yaml
from etudecas_agentkit.data.loader import DataLoader
from etudecas_agentkit.data.validator import DataValidator
from etudecas_agentkit.kpi.engine import KPIEngine
from etudecas_agentkit.trajectory.builder import TrajectoryBuilder
from etudecas_agentkit.validation.result_checks import ResultValidator
from etudecas_agentkit.validation.visual_checks import VisualValidator
from etudecas_agentkit.visualization.figure_factory import FigureFactory


def run(case_path: str | Path) -> Path:
    case = CaseStudy.from_yaml(case_path)
    case_slug = re.sub(r"[^A-Za-z0-9_-]", "_", case.case_id)
    run_dir = case.resolve_path("outputs") / case_slug / uuid4().hex
    run_dir.mkdir(parents=True)
    df = DataLoader.load_csv(case.resolve_path(case.data_config["path"]))

    schema = load_yaml(case.resolve_path(case.data_config["schema"]))
    data_report = DataValidator(schema).validate(df)
    data_report.write_json(run_dir / "data_validation.json")
    if data_report.status == "reject":
        raise SystemExit(f"Dataset rejeté: {data_report.to_dict()}")

    kpi_df = KPIEngine(case.kpi_tree).compute(df)
    trajectory = TrajectoryBuilder(case.trajectory_config).build(kpi_df)

    validation_rules = load_yaml(case.resolve_path(case.validation_rules_path))
    validation_report = ResultValidator(validation_rules).validate(kpi_df)
    validation_report.write_json(run_dir / "validation_report.json")

    if validation_report.status == "reject":
        raise SystemExit(f"Results rejected: {validation_report.to_dict()}")

    for visual_path in case.visuals.values():
        spec = load_yaml(case.resolve_path(visual_path))
        spec["output"]["path"] = str(run_dir / Path(spec["output"]["path"]).name)
        figure = FigureFactory(spec).render(trajectory, base_dir=case.base_dir)
        visual_report = VisualValidator().validate(figure, spec)
        visual_report.write_json(run_dir / (figure.stem + "_validation.json"))
        if visual_report.status == "reject":
            raise SystemExit(f"Figure rejected: {visual_report.to_dict()}")

    print("Case executed")
    print(f"output_dir={run_dir}")
    print(f"case_id={case.case_id}")
    print(f"data_status={data_report.status}")
    print(f"validation_status={validation_report.status}")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an etudecas case study.")
    parser.add_argument("case", help="Path to case YAML file")
    args = parser.parse_args()
    run(args.case)


if __name__ == "__main__":
    main()
