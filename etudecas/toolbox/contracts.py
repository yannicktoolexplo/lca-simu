"""Strict local handoff contracts; declarations are checked, not sandboxed."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


def text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Expected nonempty string: {name}")
    return value


def strings(value: Any, name: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"Expected {'nonempty ' if nonempty else ''}list: {name}")
    return [text(item, name) for item in value]


def fields(data: Any, expected: set[str]) -> None:
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError(f"Expected exactly these contract fields: {sorted(expected)}")


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    role: str
    objective: str
    inputs: list[str]
    writable: list[str]
    forbidden: list[str]
    required_evidence: list[str]

    @classmethod
    def parse(cls, data: Any, roles: tuple[str, ...], kinds: tuple[str, ...]) -> TaskSpec:
        fields(data, set(cls.__dataclass_fields__))
        result = cls(**{name: text(data[name], name) if name in ("task_id", "role", "objective")
                        else strings(data[name], name, nonempty=name == "required_evidence") for name in cls.__dataclass_fields__})
        if result.role not in roles or not set(result.required_evidence).issubset(kinds):
            raise ValueError("Unsupported role or required evidence kind")
        return result


@dataclass(frozen=True)
class AgentResult:
    task_id: str
    role: str
    status: str
    changed_files: list[str]
    manifests: list[str]
    summary: str
    limitations: list[str]

    @classmethod
    def parse(cls, data: Any) -> AgentResult:
        fields(data, set(cls.__dataclass_fields__))
        result = cls(**{name: strings(data[name], name) if name in ("changed_files", "manifests", "limitations")
                        else text(data[name], name) for name in cls.__dataclass_fields__})
        if result.status not in ("complete", "refused", "incomplete"):
            raise ValueError("Unsupported agent status")
        return result


def resolve(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Contract path escapes repository: {name}")
    return path


def validate_handoff(task: TaskSpec, result: AgentResult, root: Path) -> None:
    if (task.task_id, task.role) != (result.task_id, result.role):
        raise ValueError("Task/result identity mismatch")
    if result.status != "complete":
        raise ValueError(f"Agent did not complete task: {result.status}")
    allowed = [resolve(root, name) for name in task.writable]
    forbidden = [resolve(root, name) for name in task.forbidden]
    for name in task.inputs:
        if not resolve(root, name).exists():
            raise ValueError(f"Missing declared task input: {name}")
    for name in result.changed_files:
        path = resolve(root, name)
        if not any(path.is_relative_to(base) for base in allowed) or any(path.is_relative_to(base) for base in forbidden):
            raise ValueError(f"Declared change outside task scope: {name}")
    if not result.manifests:
        raise ValueError("Agent supplied no evidence manifests")
