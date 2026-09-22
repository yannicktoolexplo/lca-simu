import json

import pytest

from . import batch, test_builder as single
from .builder import DocumentationError


@pytest.fixture
def workspace():
    case = single.DocumentationTest()
    case.setUp()
    root = case.root.resolve()
    case.root = root
    rules = root / "etudecas/docs/rules"
    rules.mkdir(parents=True)
    catalog = {"schema_version": "etudecas.documentation.catalog.v1", "registries": []}
    for name in ("first", "second"):
        registry = rules / f"{name}.json"
        registry.write_bytes(case.registry_path.read_bytes())
        catalog["registries"].append({"registry": registry.relative_to(root).as_posix(), "output": f"out/{name}"})
    (root / batch.CATALOG).write_text(json.dumps(catalog), encoding="utf-8")
    try:
        yield case
    finally:
        case.doCleanups()


def test_batch_build_check_and_business_drift_never_accept_fingerprints(workspace):
    root = workspace.root
    assert batch.run_all("build", root) == 0
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert batch.run_all("check", root) == 0
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    (root / "business.md").write_text("Changed business rule.", encoding="utf-8")
    assert batch.run_all("build", root) == 1
    assert batch.run_all("check", root) == 1
    for registry, _output in batch.entries(root):
        assert registry.read_bytes() == before[registry.relative_to(root)]


def test_batch_reports_invalid_registry_and_still_processes_others(workspace):
    root = workspace.root
    (root / "etudecas/docs/rules/first.json").write_text("{}")
    assert batch.run_all("build", root) == 2
    assert (root / "out/second/index.md").is_file()
    (root / "etudecas/docs/rules/unlisted.json").write_text("{}")
    with pytest.raises(DocumentationError, match="exactly every"):
        batch.entries(root)


def test_batch_watch_detects_business_edit_and_stops_cleanly(workspace, monkeypatch):
    root = workspace.root
    calls = []

    def tick(_interval):
        calls.append(1)
        if len(calls) == 1:
            (root / "business.md").write_text("Changed in watcher.")
        else:
            raise KeyboardInterrupt

    monkeypatch.setattr(batch.time, "sleep", tick)
    assert batch.watch_all(root, 1) == 0
    manifest = json.loads((root / "out/first/manifest.json").read_text())
    assert manifest["rules"][0]["changed_business_sources"] == ["business.md"]


def test_project_catalog_is_current():
    assert batch.run_all("check", single.REPO_ROOT) == 0
