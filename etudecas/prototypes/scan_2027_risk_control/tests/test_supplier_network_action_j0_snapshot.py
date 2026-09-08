from __future__ import annotations

import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_action_j0_snapshot as snapshot,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_exploratory_action_runner as action,
)


def _row() -> dict[str, str]:
    return snapshot._canonical_row(
        {
            "schema_version": action.J0_SNAPSHOT_SCHEMA_VERSION,
            "seed": "340282",
            "seed_prefix_index": "1",
            "baseline_case_key": "baseline::case",
            "baseline_evidence_relative_path": "ledger_cases/case.json",
            "baseline_evidence_sha256": "evidence-sha",
            "source_runner_signature": "runner-signature",
            "chain_id": "chain",
            "supplier_id": "supplier",
            "node_id": "factory",
            "item_id": "item:component",
            "uom": "UN",
            "stock_before_production_day0_qty": "120",
            "arrival_day0_qty": "20",
            "cutover_stock_before_day0_flows_qty": "100",
            "reconstruction": "day0_stock_before_production_minus_day0_arrival",
            "summary_sha256": "summary-sha",
            "stocks_daily_sha256": "stocks-sha",
            "arrivals_daily_sha256": "arrivals-sha",
            "lot_events_sha256": "lot-events-sha",
            "lot_genealogy_sha256": "lot-genealogy-sha",
            "source_lot_trace_enabled": "False",
            "warmup_core_state_sha256": "j0-sha",
            "warmup_component_sha256_json": json.dumps(
                {"stock": "stock-sha", "lot_ledger": "lot-sha"},
                sort_keys=True,
                separators=(",", ":"),
            ),
        }
    )


def _write_snapshot(root: Path, row: dict[str, str]) -> None:
    root.mkdir()
    rows_path = root / action.J0_SNAPSHOT_ROWS
    action._write_csv(rows_path, [row])
    manifest = action._signed_payload(
        {
            "schema_version": action.J0_SNAPSHOT_SCHEMA_VERSION,
            "contract_revision": action.CONTRACT_REVISION,
            "rows_file": action.J0_SNAPSHOT_ROWS,
            "rows_sha256": action._sha256(rows_path),
            "row_count": 1,
        },
        "snapshot_signature",
    )
    action._write_json(root / action.J0_SNAPSHOT_MANIFEST, manifest)


def test_snapshot_reader_checks_exact_inventory_hash_and_row_signature(
    tmp_path: Path,
) -> None:
    root = tmp_path / "snapshot"
    original = _row()
    _write_snapshot(root, original)
    manifest, rows = snapshot._read_snapshot_rows(root)
    assert manifest["row_count"] == 1
    assert rows == [original]

    changed = {**original, "arrival_day0_qty": "21"}
    rows_path = root / action.J0_SNAPSHOT_ROWS
    action._write_csv(rows_path, [changed])
    changed_manifest = action._signed_payload(
        {
            key: value
            for key, value in manifest.items()
            if key not in {"snapshot_signature", "rows_sha256"}
        }
        | {"rows_sha256": action._sha256(rows_path)},
        "snapshot_signature",
    )
    action._write_json(root / action.J0_SNAPSHOT_MANIFEST, changed_manifest)
    with pytest.raises(ValueError, match="Base J0 snapshot is invalid"):
        snapshot._read_snapshot_rows(root)


def test_capture_wait_mode_polls_without_writing_until_sources_are_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = 0
    sleeps: list[float] = []

    def capture(**_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise action.SourcesNotReadyError("seed 340297 absent")
        return {"status": "complete_30_of_30", "row_count": 120}

    monkeypatch.setattr(snapshot, "capture_snapshot", capture)
    monkeypatch.setattr(snapshot.time, "sleep", sleeps.append)
    exit_code = snapshot.main(
        [
            "--mode",
            "capture",
            "--expected-seed-count",
            "30",
            "--output-dir",
            str(tmp_path / "new-snapshot"),
            "--wait-for-sources",
            "--poll-seconds",
            "5",
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 0
    assert calls == 2
    assert sleeps == [5.0]
    assert '"status": "waiting_for_sources"' in output
    assert '"snapshot_written": false' in output
    assert '"status": "complete_30_of_30"' in output


def test_capture_without_wait_fails_closed_when_sources_are_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        snapshot,
        "capture_snapshot",
        lambda **_kwargs: (_ for _ in ()).throw(
            action.SourcesNotReadyError("seed 340297 absent")
        ),
    )
    exit_code = snapshot.main(
        [
            "--mode",
            "capture",
            "--expected-seed-count",
            "30",
            "--output-dir",
            str(tmp_path / "new-snapshot"),
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 2
    assert '"status": "sources_not_ready"' in output
    assert '"snapshot_written": false' in output
