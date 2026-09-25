"""Typed, local command catalogue. Every execution has fresh, hash-bound evidence.

This is a verification runner, not a model orchestrator or a security boundary.
Native Codex performs delegation; this module never starts an LLM or a shell.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tomllib
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "etudecas.toolbox.evidence.v1"
KINDS = ("doctor", "tests", "qualify", "browser", "docs")
PROFILES = ("etudecas_explorer", "etudecas_simulation", "etudecas_map", "etudecas_validator")
SKILLS = ("etudecas-orchestrate", "etudecas-qualify", "etudecas-map-review")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def local_path(value: str | Path, *, exists: bool = True) -> Path:
    path = Path(value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Path outside repository: {path}")
    if exists and not path.exists():
        raise ValueError(f"Missing input: {path}")
    return path


def fingerprint(paths: list[Path]) -> dict[str, str]:
    result = {}
    for path in paths:
        if path.is_dir():
            files = sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        else:
            files = [path]
        for file in files:
            file = local_path(file)
            result[str(file)] = digest(file)
    return result


def code_fingerprint() -> dict[str, str]:
    # Exclude generated/historical runs and test evidence. Include tests: their
    # expectations are part of the proof, as are this runner and native config.
    excluded = {"artifacts", "result", "outputs", "archive", "archives", "__pycache__", "native", "vendor", "node_modules"}
    files = []
    for directory in (ROOT / "etudecas",):
        for folder, directories, names in os.walk(directory):
            directories[:] = sorted(name for name in directories if name not in excluded)
            files.extend(Path(folder) / name for name in names if Path(name).suffix.lower() in {".py", ".js", ".css", ".ps1"})
    for directory in (ROOT / "etudecas/config", ROOT / "etudecas/docs/rules"):
        files.extend(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in {".json", ".yaml", ".yml", ".toml", ".csv"})
    # This executable revision contract lives beside its research adapters.
    # Editing it must invalidate qualification just like editing their Python.
    revision = ROOT / "etudecas/prototypes/scan_2027_risk_control/supplier_campaign_source_revision.json"
    if revision.is_file():
        files.append(revision)
    files.extend((ROOT / ".codex/agents").glob("*.toml"))
    files.extend((ROOT / ".agents/skills").glob("*/SKILL.md"))
    for path in (ROOT / "AGENTS.md", ROOT / ".gitattributes", ROOT / ".codex/config.toml", ROOT / "pytest-reference.ini", ROOT / "requirements-etudecas.txt", ROOT / "requirements-etudecas-test.txt"):
        if path.is_file():
            files.append(path)
    return fingerprint(files)


def doctor(native_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append({"name": "python_3_11", "ok": sys.version_info >= (3, 11), "value": platform.python_version()})
    for package in ("pytest", "pandas", "numpy", "PyYAML", "matplotlib", "Pillow", "playwright"):
        try:
            value = version(package)
        except PackageNotFoundError:
            value = None
        checks.append({"name": package, "ok": value is not None, "version": value})
    config = native_root / ".codex/config.toml"
    try:
        agents = tomllib.loads(config.read_text(encoding="utf-8"))["agents"]
        good = agents.get("enabled") is True and type(agents.get("max_concurrent_threads_per_session")) is int and agents["max_concurrent_threads_per_session"] > 0
        checks.append({"name": "native_config", "ok": good})
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        checks.append({"name": "native_config", "ok": False, "error": str(exc)})
    for name in PROFILES:
        try:
            data = tomllib.loads((native_root / f".codex/agents/{name}.toml").read_text(encoding="utf-8"))
            good = data.get("name") == name and all(isinstance(data.get(k), str) and data[k].strip() for k in ("description", "developer_instructions"))
            checks.append({"name": name, "ok": bool(good)})
        except (OSError, tomllib.TOMLDecodeError) as exc:
            checks.append({"name": name, "ok": False, "error": str(exc)})
    for name in SKILLS:
        path = native_root / f".agents/skills/{name}/SKILL.md"
        try:
            import yaml
            text = path.read_text(encoding="utf-8")
            metadata = yaml.safe_load(text.split("---", 2)[1]) if text.startswith("---\n") else {}
            good = isinstance(metadata, dict) and metadata.get("name") == name and bool(metadata.get("description"))
            checks.append({"name": name, "ok": good})
        except Exception as exc:
            checks.append({"name": name, "ok": False, "error": str(exc)})
    checks.append({"name": "root_instructions", "ok": (native_root / "AGENTS.md").is_file()})
    return {"ok": all(row["ok"] for row in checks), "checks": checks,
            "native_root": str(native_root), "installed_at_repository_root": native_root == ROOT,
            "codex_on_path": shutil.which("codex"), "python": sys.executable,
            "scope": "Dependency and native file structure checks; runtime discovery, authentication and browser launch are not certified."}


def documentation_inputs() -> list[Path]:
    """Bind documentation proofs to the catalog and every reviewed business source."""
    docs = ROOT / "etudecas/docs"
    paths = [docs / "catalog.json", docs / "rules", docs / "generated"]
    for registry in sorted((docs / "rules").glob("*.json")):
        data = json.loads(registry.read_text(encoding="utf-8-sig"))
        for source in data.get("business_source_fingerprints", {}):
            paths.append(local_path(ROOT / source))
    return sorted(set(paths))


def check_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or data.get("status") != "passed" or data.get("command") not in KINDS:
        raise ValueError(f"Unsuccessful or unsupported evidence: {path}")
    if not data.get("proofs") or not data.get("code"):
        raise ValueError(f"Empty evidence: {path}")
    for group in ("inputs", "code", "proofs"):
        for name, expected in data.get(group, {}).items():
            source = local_path(name)
            if not source.is_file() or digest(source) != expected:
                raise ValueError(f"Stale or changed {group}: {name}")
    if data.get("input_roots") and fingerprint([local_path(p) for p in data["input_roots"]]) != data["inputs"]:
        raise ValueError(f"Input file set changed since evidence: {path}")
    if data["code"] != code_fingerprint():
        raise ValueError(f"Source set changed since evidence: {path}")
    return data


def execute(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    root = local_path(args.output, exists=False)
    if not root.is_relative_to(ROOT / "etudecas/artifacts/testing"):
        raise ValueError("Evidence output must be inside etudecas/artifacts/testing")
    run = root / f"{args.command}-{uuid4().hex}"
    run.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {"schema": SCHEMA, "run_id": run.name, "command": args.command,
        "task_id": args.task_id, "owner": args.owner,
        "started_at": datetime.now(timezone.utc).isoformat(), "status": "running", "inputs": {},
        "code": code_fingerprint(), "proofs": {}, "scope": "Only the explicitly executed checks; no scientific or industrial certification."}
    write_json(run / "manifest.json", report)
    try:
        input_paths: list[Path] = []
        command: list[str] | None = None
        result: dict[str, Any] | None = None
        result_file = run / "result.json"
        if args.command == "doctor":
            native = local_path(args.native_root)
            input_paths = [p for p in (native / "AGENTS.md", native / ".codex", native / ".agents") if p.exists()]
            report["inputs"] = fingerprint(input_paths)
            result = doctor(native)
        elif args.command in ("gate", "handoff"):
            required = args.require if args.command == "gate" else []
            if args.command == "handoff":
                from .contracts import AgentResult, TaskSpec, resolve, validate_handoff
                task_path, result_path = local_path(args.task_spec), local_path(args.agent_result)
                task = TaskSpec.parse(json.loads(task_path.read_text(encoding="utf-8")), PROFILES, KINDS)
                agent = AgentResult.parse(json.loads(result_path.read_text(encoding="utf-8")))
                validate_handoff(task, agent, ROOT)
                manifests = [local_path(resolve(ROOT, p)) for p in agent.manifests]
                input_paths = [task_path, result_path, *manifests]
                required = task.required_evidence
                report["task_id"] = task.task_id
            else:
                manifests = [local_path(p) for p in args.manifest]
                input_paths = manifests
            report["inputs"] = fingerprint(input_paths)
            evidence = [check_manifest(p) for p in manifests]
            if args.command == "handoff" and any(row.get("task_id") != task.task_id or row.get("owner") != task.role for row in evidence):
                raise ValueError("Evidence does not belong to the declared task and role")
            for row in evidence:
                if row["command"] == "doctor":
                    result_paths = [Path(p) for p in row["proofs"] if Path(p).name == "result.json"]
                    if len(result_paths) != 1 or json.loads(result_paths[0].read_text(encoding="utf-8")).get("installed_at_repository_root") is not True:
                        raise ValueError("Staged doctor evidence does not establish repository installation")
            missing = sorted(set(required) - {row["command"] for row in evidence})
            if missing:
                raise ValueError(f"Required evidence missing: {missing}")
            result = {"ok": bool(evidence), "required": required,
                      "evidence": [{"run_id": row["run_id"], "command": row["command"]} for row in evidence]}
        elif args.command == "tests":
            selectors = []
            for selector in args.path:
                file_name, *nodes = selector.split("::")
                path = local_path(file_name)
                if not path.is_file() or path.suffix != ".py" or not path.name.startswith("test") or "artifacts" in path.relative_to(ROOT).parts:
                    raise ValueError("Select explicit test*.py files or node IDs outside artifacts")
                input_paths.append(path)
                selectors.append(str(path) + ("::" + "::".join(nodes) if nodes else ""))
            command = [sys.executable, "-B", "-m", "pytest", "-c", str(ROOT / "pytest-reference.ini"),
                       "-o", "addopts=", "-p", "no:cacheprovider", "-q", "--tb=short",
                       f"--junitxml={run / 'junit.xml'}", *selectors]
        elif args.command == "qualify":
            runs = [local_path(p) for p in args.run]
            for source in runs:
                if not source.is_dir():
                    raise ValueError(f"Run is not a directory: {source}")
                for child in ("data", "summaries"):
                    if not (source / child).is_dir():
                        raise ValueError(f"Missing required run directory: {source / child}")
                    input_paths.append(source / child)
                input_paths.extend(p for p in source.glob("*.json") if p.is_file())
            command = [sys.executable, "-B", "-m", "etudecas.testing.qualification", "--output", str(run / "qualification")]
            for source in runs:
                command.extend(("--run", str(source)))
            if args.html:
                html = local_path(args.html)
                input_paths.append(html)
                command.extend(("--html", str(html)))
        elif args.command == "browser":
            html = local_path(args.html)
            if not html.is_file() or html.suffix.lower() != ".html":
                raise ValueError("Expected a local HTML file")
            input_paths.append(html)
            command = [sys.executable, "-B", "-m", "etudecas.testing.map_browser", "--html", str(html), "--output-dir", str(run / "browser")]
        elif args.command == "docs":
            input_paths = documentation_inputs()
            command = [sys.executable, "-B", "-m", "etudecas.documentation", "check-all"]
        if command is not None:
            report["inputs"] = fingerprint(input_paths)
            report["input_roots"] = [str(p) for p in input_paths]
            report["argv"] = command
            write_json(run / "manifest.json", report)
            with (run / "execution.log").open("w", encoding="utf-8") as log:
                environment = os.environ.copy()
                environment["PYTHONPATH"] = os.pathsep.join((str(ROOT), environment.get("PYTHONPATH", "")))
                completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                           timeout=args.timeout, shell=False, check=False, env=environment)
            report["exit_code"] = completed.returncode
            if completed.returncode != 0:
                raise ValueError(f"Command failed with exit code {completed.returncode}; see execution.log")
            if args.command == "tests":
                from etudecas.testing.report import summarize
                result = summarize(run / "junit.xml")
                result["ok"] = not result["failures"] and result["counts"].get("passed", 0) > 0
            elif args.command == "qualify":
                result = json.loads((run / "qualification/qualification.json").read_text(encoding="utf-8"))
                result["ok"] = result.get("ok") is True and bool(result.get("runs")) and all(bool(row.get("checks")) for row in result["runs"])
            elif args.command == "browser":
                result = json.loads((run / "browser/browser-review.json").read_text(encoding="utf-8"))
                result["ok"] = result.get("ok") is True and bool(result.get("checks"))
            else:
                result = {"ok": (run / "execution.log").stat().st_size > 0, "scope": "Existing documentation check-all exit code and nonempty log."}
        if result is None:
            raise ValueError("Missing structured result")
        report["input_roots"] = [str(p) for p in input_paths]
        write_json(result_file, result)
        if result.get("ok") is not True:
            raise ValueError("Checks did not establish a positive result; see result.json")
        for name, before in report["inputs"].items():
            if not Path(name).is_file() or digest(Path(name)) != before:
                raise ValueError(f"Input changed during verification: {name}")
        if input_paths and fingerprint(input_paths) != report["inputs"]:
            raise ValueError("Input file set changed during verification")
        if code_fingerprint() != report["code"]:
            raise ValueError("Code changed during verification; rerun on a stable working tree")
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "refused"
        report["error"] = f"{type(exc).__name__}: {exc}"
    report["proofs"] = fingerprint([p for p in run.rglob("*") if p.is_file() and p.name != "manifest.json"])
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    write_json(run / "manifest.json", report)
    return run / "manifest.json", report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    for name in (*KINDS, "gate", "handoff"):
        sub = commands.add_parser(name)
        sub.add_argument("--output", type=Path, default=ROOT / "etudecas/artifacts/testing/toolbox")
        sub.add_argument("--timeout", type=int, default=1800)
        sub.add_argument("--task-id", default="ad-hoc")
        sub.add_argument("--owner", default="local")
        if name == "doctor":
            sub.add_argument("--native-root", type=Path, default=ROOT)
        elif name == "tests":
            sub.add_argument("--path", action="append", required=True)
        elif name == "qualify":
            sub.add_argument("--run", type=Path, action="append", required=True)
            sub.add_argument("--html", type=Path)
        elif name == "browser":
            sub.add_argument("--html", type=Path, required=True)
        elif name == "gate":
            sub.add_argument("--manifest", type=Path, action="append", required=True)
            sub.add_argument("--require", choices=KINDS, action="append", required=True)
        elif name == "handoff":
            sub.add_argument("--task-spec", type=Path, required=True)
            sub.add_argument("--agent-result", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("timeout must be positive")
    try:
        manifest, report = execute(args)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}))
        return 2
    print(json.dumps({"status": report["status"], "manifest": str(manifest), "error": report.get("error")}))
    return 0 if report["status"] == "passed" else 1
