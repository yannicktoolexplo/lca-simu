"""Explicit opt-in for tests consuming historical campaign deliveries."""

from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption("--historical-artifacts", type=Path, default=None,
                     help="Root of historical deliveries for explicitly dependent tests")
    parser.addoption("--historical-wrapper-repo", type=Path, default=None,
                     help="Original checkout for path-bound historical PowerShell wrappers")


def pytest_configure(config):
    config.addinivalue_line("markers", "historical: requires historical campaign artifacts")


def pytest_collection_modifyitems(items):
    for item in items:
        if "historical_artifact" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.historical)


@pytest.fixture(scope="session")
def historical_artifact(pytestconfig):
    """Resolve required evidence; explicit but incomplete input must fail."""
    root = pytestconfig.getoption("--historical-artifacts")
    if root is None:
        pytest.skip("Historical integration: supply --historical-artifacts PATH")
    root = root.resolve()
    if not root.is_dir():
        pytest.fail(f"Historical artifact root is not a directory: {root}")

    def require(relative: str) -> Path:
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.exists():
            pytest.fail(f"Required historical artifact unavailable: {path}")
        return path

    return require


@pytest.fixture
def frozen_wrapper_environment(historical_artifact, pytestconfig, monkeypatch, request):
    """Use the original signed environment only when explicitly requested."""
    root = historical_artifact(".")
    repo = pytestconfig.getoption("--historical-wrapper-repo")
    if repo is None:
        pytest.fail("Frozen wrapper integration also requires --historical-wrapper-repo PATH")
    repo = repo.resolve()
    if root != Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726").resolve():
        pytest.fail("These frozen wrappers require their original artifact paths; relocation is not supported")
    if repo != Path(r"C:\dev\lca-simu-pr40").resolve() or not repo.is_dir():
        pytest.fail("These frozen wrappers require the original C:/dev/lca-simu-pr40 checkout")
    module = request.module
    current_repo = module.REPO
    for name in ("SCRIPT", "V3", "V4", "ADAPTER", "VERIFIER", "CHAIN_WRAPPER", "FROZEN_CHAIN_WRAPPER"):
        value = getattr(module, name, None)
        if value is not None:
            original = repo / value.relative_to(current_repo)
            if not original.is_file():
                pytest.fail(f"Missing frozen wrapper: {original}")
            monkeypatch.setattr(module, name, original)
    monkeypatch.setattr(module, "REPO", repo)
    return root
