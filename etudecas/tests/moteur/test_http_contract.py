from contextlib import contextmanager
import http.client
import json
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace

import pytest

from etudecas.simulation.engine import server as service
from etudecas.simulation.engine.http_contract import ENGINE, request_from_http
from etudecas.simulation.engine.bounded_execution import run_simulation_bounded


def payload():
    return {"days": 7, "input_graph": {"items": [], "nodes": [], "edges": [],
                                      "scenarios": [{"id": "scn:BASE"}]}}


@pytest.mark.parametrize("field,value", [("run_script", "evil.py"), ("output_dir", "elsewhere"),
    ("run_id", "../escape"), ("skip_map", False), ("overrides", {"engine_args": ["--input", "x"]}),
    ("days", 0), ("days", 3661), ("scenario_id", "missing")])
def test_http_rejects_internal_fields_and_unbounded_horizon(tmp_path, field, value):
    data = payload()
    data[field] = value
    with pytest.raises(ValueError):
        request_from_http(data, input_root=tmp_path, output_root=tmp_path / "out")
    assert list(tmp_path.iterdir()) == []


def test_http_assigns_engine_and_unique_output_without_writing(tmp_path):
    a = request_from_http(payload(), input_root=tmp_path, output_root=tmp_path / "out")
    b = request_from_http(payload(), input_root=tmp_path, output_root=tmp_path / "out")
    assert a.run_script == ENGINE
    assert a.output_dir != b.output_dir
    assert a.output_dir.is_relative_to((tmp_path / "out").resolve())
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("field", ["input_path", "control_schedule_csv", "control_policy_json", "demand_perturbation_csv"])
def test_http_paths_cannot_escape_input_root(tmp_path, field):
    root = tmp_path / "allowed"
    root.mkdir()
    suffix = ".json" if field in {"input_path", "control_policy_json"} else ".csv"
    outside = tmp_path / ("outside" + suffix)
    outside.write_text(json.dumps(payload()["input_graph"]))
    data = payload()
    if field == "input_path":
        data.pop("input_graph")
    for name in (str(outside), "../" + outside.name):
        data[field] = name
        with pytest.raises(ValueError, match="outside"):
            request_from_http(data, input_root=root, output_root=root / "out")


def test_http_reads_confined_graph_and_rejects_nonfinite_graph(tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload()["input_graph"]))
    request = request_from_http({"input_path": "input.json", "days": 7}, input_root=tmp_path, output_root=tmp_path / "out")
    assert request.input_path is None
    assert request.input_graph == payload()["input_graph"]
    data = payload()
    data["input_graph"]["meta"] = {"invalid": float("nan")}
    with pytest.raises(ValueError, match="Non-finite"):
        request_from_http(data, input_root=tmp_path, output_root=tmp_path / "out")


@contextmanager
def running_server(tmp_path, **kwargs):
    with service.SimulationApiServer(("127.0.0.1", 0), input_root=tmp_path,
                                    output_root=tmp_path / "out", **kwargs) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(timeout=5)


def post(server, *, headers=None, body=None, method="POST"):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    defaults = {"Content-Type": "application/json", "X-Etudecas-Token": server.token}
    defaults.update(headers or {})
    try:
        connection.request(method, "/simulate", body=body if body is not None else json.dumps(payload()), headers=defaults)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


@pytest.mark.parametrize("headers,status", [
    ({"X-Etudecas-Token": "wrong"}, 401), ({"X-Etudecas-Token": ""}, 401),
    ({"Origin": "https://foreign.example"}, 403), ({"Origin": "null"}, 403),
    ({"Host": "foreign.example"}, 403), ({"Content-Type": "text/plain"}, 415),
    ({"Content-Length": "-1"}, 400), ({"Content-Length": "9999999"}, 413),
    ({"Transfer-Encoding": "chunked"}, 400),
    ({"Content-Length": "²"}, 400), ({"Content-Length": "9" * 50}, 400),
])
def test_http_rejects_before_simulation(tmp_path, monkeypatch, headers, status):
    def forbidden(*args, **kwargs):
        pytest.fail("Rejected request must never invoke the simulator")
    monkeypatch.setattr(service, "simulate", forbidden)
    with running_server(tmp_path) as server:
        code, response_headers, _ = post(server, headers=headers)
        assert code == status
        assert "Access-Control-Allow-Origin" not in response_headers
    assert not (tmp_path / "out").exists()


def test_allowed_origin_preflight_and_authenticated_post(tmp_path, monkeypatch):
    calls = []
    def simulate(request, **kwargs):
        calls.append(request)
        return SimpleNamespace(to_dict=lambda: {"run_id": request.run_id})
    monkeypatch.setattr(service, "simulate", simulate)
    with running_server(tmp_path, allowed_origins=["null"]) as server:
        code, headers, _ = post(server, headers={"Origin": "null", "X-Etudecas-Token": ""}, method="OPTIONS")
        assert code == 204
        assert headers["Access-Control-Allow-Origin"] == "null"
        assert post(server, headers={"Origin": "null", "X-Etudecas-Token": ""})[0] == 401
        assert post(server, headers={"Origin": "null"})[0] == 200
        assert len(calls) == 1


def test_busy_and_timeout_release_slot(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("fixed-engine", 1)
    monkeypatch.setattr(service, "simulate", timeout)
    with running_server(tmp_path) as server:
        server.execution_slot.acquire()
        assert post(server)[0] == 429
        server.execution_slot.release()
        code, _, body = post(server)
        assert code == 504
        assert json.loads(body)["error"] == "simulation_timeout"
        # Receipt of response bytes can precede the handler's finally block.
        # Wait on the semaphore itself: a missing release still fails this test.
        assert server.execution_slot.acquire(timeout=5)
        server.execution_slot.release()


def test_partial_body_times_out_and_releases_slot(tmp_path):
    with running_server(tmp_path, read_timeout=.2) as server:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("POST", "/simulate", body="{", headers={"Content-Type": "application/json",
                     "Content-Length": "20", "X-Etudecas-Token": server.token})
        response = conn.getresponse()
        assert response.status == 408
        response.read()
        conn.close()
        assert server.execution_slot.acquire(timeout=5)
        server.execution_slot.release()


def test_real_subprocess_timeout(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text("import time\ntime.sleep(60)\n")
    with pytest.raises(subprocess.TimeoutExpired):
        run_simulation_bounded(script, tmp_path / "input.json", tmp_path / "out",
                               "scn:BASE", timeout_seconds=.2)


@pytest.mark.parametrize("kwargs", [{"execution_timeout": float("nan")}, {"max_days": 0},
    {"allowed_origins": ["*"]}, {"allowed_origins": ["https://example.org/path"]}])
def test_invalid_server_policy_is_rejected(kwargs):
    with pytest.raises(ValueError):
        service.SimulationApiServer(("127.0.0.1", 0), **kwargs)


@pytest.mark.parametrize("layout", ["legacy", "structured"])
@pytest.mark.parametrize("state_mode", ["default", "explicit", "disabled"])
def test_shared_runner_preserves_command_and_summary(tmp_path, monkeypatch, layout, state_mode):
    import sys
    from etudecas.simulation import analysis_batch_common as batch
    from etudecas.simulation.engine import bounded_execution as bounded
    from etudecas.simulation.initial_state_policy import ERP_SNAPSHOT_INITIAL_STATE_ARGS

    output = tmp_path / "out"
    output.mkdir()
    legacy = output / "first_simulation_summary.json"
    legacy.write_text(json.dumps({"layout": "legacy"}))
    if layout == "structured":
        preferred = batch.summary_path(output, legacy.name)
        preferred.parent.mkdir(parents=True, exist_ok=True)
        preferred.write_text(json.dumps({"layout": "structured"}))
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="unchanged stdout\n", stderr="")

    # The historical HTTP monkeypatch path must still reach the shared runner.
    monkeypatch.setattr(bounded.subprocess, "run", fake_run)
    extra = ["--seed", "17"]
    if state_mode == "explicit":
        extra += ["--initial-state-scale", "2"]
    script, graph = tmp_path / "engine.py", tmp_path / "graph.json"
    arguments = dict(days=7, skip_map=True, skip_plots=False, extra_args=extra,
                     use_living_initial_state=state_mode != "disabled")
    expected = [sys.executable, str(script), "--input", str(graph), "--output-dir",
                str(output), "--scenario-id", "scn:BASE", "--days", "7", "--skip-map"]
    if state_mode == "default":
        expected += list(ERP_SNAPSHOT_INITIAL_STATE_ARGS)
    expected += extra
    assert batch.run_simulation(script, graph, output, "scn:BASE", **arguments) == (
        {"layout": layout}, "unchanged stdout\n")
    assert bounded.run_simulation_bounded(
        script, graph, output, "scn:BASE", timeout_seconds=3, **arguments
    ) == ({"layout": layout}, "unchanged stdout\n")
    assert calls == [(expected, {"capture_output": True, "text": True}),
                     (expected, {"capture_output": True, "text": True, "timeout": 3})]


@pytest.mark.parametrize("bounded", [False, True])
def test_shared_runner_preserves_failure_and_timeout(tmp_path, monkeypatch, bounded):
    from etudecas.simulation import analysis_batch_common as batch

    runner = run_simulation_bounded if bounded else batch.run_simulation
    options = {"timeout_seconds": .1} if bounded else {}
    graph = tmp_path / "graph.json"
    args = (tmp_path / "engine.py", graph, tmp_path / "out", "scn:BASE")

    def failed(command, **kwargs):
        return SimpleNamespace(returncode=2, stdout=" output \n", stderr=" error \n")

    monkeypatch.setattr(batch.subprocess, "run", failed)
    with pytest.raises(RuntimeError) as failure:
        runner(*args, **options)
    assert str(failure.value) == f"Simulation failed for {graph}:\noutput\nerror"
    expired = subprocess.TimeoutExpired("engine", .1, output="partial")

    def timed_out(command, **kwargs):
        raise expired

    monkeypatch.setattr(batch.subprocess, "run", timed_out)
    with pytest.raises(subprocess.TimeoutExpired) as failure:
        runner(*args, **options)
    assert failure.value is expired
