"""Replay one native case with the explicit hypothesis of an earlier lot."""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from etudecas.simulation import current_reference as reference
from etudecas.simulation.analysis.programme_advance_trial import ProgrammeAdvance, programme_advance_trial
from etudecas.toolbox.cli import code_fingerprint


def run(case_path: Path, scenario_path: Path) -> Path:
    case_path = case_path.resolve()
    scenario_path = scenario_path.resolve()
    case = reference.read(case_path)
    scenario = ProgrammeAdvance(**reference.read(scenario_path))
    graph_path = Path(case["graph"]).resolve()
    output = Path(case["output"]).resolve()
    profile_path = Path(case["replay_profile_path"]).resolve()
    arguments = case["engine_arguments"]
    days = case["days"]
    if type(days) is not int or not 1 <= days <= 362 or case["scan3_mode"] != "fixed_residual_replay":
        raise ValueError("Expected a bounded native case with a fixed residual replay profile")
    if "--production-frozen-horizon-policy" not in arguments or "--production-capacity-planning-policy" not in arguments:
        raise ValueError("The case requires its native frozen-order and manufacturing-calendar policies")
    audit_path = output.parent / "programme_advance_audit.json"
    if output.exists() or audit_path.exists():
        raise ValueError("Use a new run and audit path")
    config, protocol, _, inputs, frozen_path, _ = reference.resolve_inputs()
    for path in (case_path, scenario_path, graph_path, profile_path):
        inputs[reference.rel(path)] = reference.sha(path)
    for flag, value in zip(arguments, arguments[1:]):
        if flag.startswith("--") and flag.endswith("-csv"):
            path = (reference.ROOT / value).resolve()
            inputs[reference.rel(path)] = reference.sha(path)
    graph = reference.read(graph_path)
    before = code_fingerprint()
    started = time.monotonic()
    output.mkdir(parents=True)
    failure = None
    runtime = None
    audit = []
    try:
        with programme_advance_trial(scenario) as audit:
            runtime = reference.run_engine(graph, protocol, config, frozen_path,
                arguments, output, days, scan3_mode=case["scan3_mode"], replay_profile_path=profile_path)
        if not any(row["event"] == "native_freeze_confirmed" for row in audit):
            raise ValueError("The intervention did not reach its declared native freeze")
    except Exception as exc:
        failure = repr(exc)
        raise
    finally:
        stable = before == code_fingerprint() and all(
            reference.sha(reference.ROOT / path) == digest for path, digest in inputs.items())
        with audit_path.open("x", encoding="utf-8") as stream:
            json.dump(dict(scenario=asdict(scenario), decisions=audit), stream, ensure_ascii=False, indent=2)
        manifest = dict(status="passed_execution" if failure is None and stable else "failed_execution",
            returncode=0 if failure is None and stable else 1, reference=config["reference_id"],
            graph=reference.rel(graph_path), output=reference.rel(output), days=days,
            engine_arguments=arguments, code=before, inputs=inputs, code_and_inputs_unchanged=stable,
            runtime=runtime, error=failure, seconds=time.monotonic() - started,
            runtime_entrypoint="etudecas.simulation.current_reference.run_engine",
            scan3_mode=case["scan3_mode"], replay_profile_path=reference.rel(profile_path),
            intervention=reference.rel(audit_path), hypothesis="existing_unstarted_lot_dated_from_known_source_signal")
        with (output / "run_manifest.json").open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2, default=str)
    if not stable:
        raise ValueError("Source or run inputs changed during execution")
    return output / "run_manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--scenario", type=Path, required=True)
    args = parser.parse_args()
    manifest = run(args.case, args.scenario)
    print(json.dumps(dict(status="passed_execution", manifest=str(manifest))))


if __name__ == "__main__":
    main()
