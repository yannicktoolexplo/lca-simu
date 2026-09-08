from __future__ import annotations

import copy
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_delivery as subject,
)


def _base_payload() -> dict[str, Any]:
    return {
        "schema_version": "etudecas.supplier_v7_stage2_delivery.v1",
        "status": "complete_validated",
        "payload_signature": "old-signature",
        "title": "old",
        "view_count": 3,
        "terminology": {
            "OBSERVÉ": "donnée industrielle",
            "SIMULÉ": "résultat du modèle",
            "SIGNAL DE PRIORITÉ": "dossier à examiner",
            "HYPOTHÈSE": "condition imposée",
        },
        "campaign": {
            "mechanisms": [
                {"id": "transport_delay"},
                {"id": "planned_delivery_shortfall"},
            ],
            "multiple_incidents_combined": False,
        },
        "focus": {
            "lane_id": subject.FOCUS_LANE_ID,
            "item_id": "338929",
            "requested_338929_present": True,
        },
        "nominal_curves": {"population": "old", "series": []},
        "cascade": {"detailed_replays": []},
        "actions": {"actions": []},
        "limits": {
            "quality_incident_included": False,
            "capacity_or_availability_modified": False,
            "automatic_regulation": False,
        },
        "bindings": {"v7_result_signature": "a" * 64},
    }


def _overlay() -> dict[str, Any]:
    return {
        "status": "complete_validated_v8_overlay",
        "overlay_signature": "b" * 64,
        "v8_comparability_checks": {
            "complete_3330_case_matrix_reconstructed": True,
            "quality_capacity_availability_stock_or_state_risk_incident_count": 0,
        },
    }


def test_adaptation_is_additive_and_focuses_338929() -> None:
    source = _base_payload()
    before = copy.deepcopy(source)
    payload = subject._adapt_payload(source, _overlay())  # noqa: SLF001
    assert source == before
    assert payload["schema_version"] == subject.SCHEMA_VERSION
    assert payload["focus"]["lane_id"] == subject.FOCUS_LANE_ID
    assert payload["presentation"]["view_order"] == [
        "focus_338929",
        "network_cascades",
        "decisions",
    ]
    assert payload["presentation"]["future_or_placeholder_results_displayed"] is False
    assert payload["bindings"]["v8_result_overlay_signature"] == "b" * 64
    subject.common.verify_signature(payload, "payload_signature", "payload test V8")


def test_adaptation_refuses_missing_focus_or_extra_mechanism() -> None:
    missing = _base_payload()
    missing["focus"]["requested_338929_present"] = False
    with pytest.raises(subject.Stage2DeliveryError, match="338929"):
        subject._adapt_payload(missing, _overlay())  # noqa: SLF001
    extra = _base_payload()
    extra["campaign"]["mechanisms"].append({"id": "quality_hold"})
    with pytest.raises(subject.Stage2DeliveryError, match="hypothèses"):
        subject._adapt_payload(extra, _overlay())  # noqa: SLF001


def test_html_has_exactly_three_views_and_starts_with_338929() -> None:
    payload = subject._adapt_payload(_base_payload(), _overlay())  # noqa: SLF001
    document = subject.render_html(payload)
    assert document.count('class="view') == 3
    assert (
        '<button class="active" data-tab="cascade">1 · 338929 et lots</button>'
        in document
    )
    assert '<section class="view active" id="cascade">' in document
    assert "DÉMONSTRATION AUTONOME V8" in document
    assert "future_or_placeholder_results_displayed" in document
    assert "quality_hold" not in document
    assert "https://" not in document
    assert "http://" not in document


def test_dashboard_reader_requires_v8_overlay_inside_both_contexts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    @contextmanager
    def finalizer_context():
        calls.append("enter-finalizer")
        yield
        calls.append("exit-finalizer")

    @contextmanager
    def dashboard_context():
        calls.append("enter-dashboard")
        yield
        calls.append("exit-dashboard")

    monkeypatch.setattr(subject.finalizer_v8, "patched_v8_context", finalizer_context)
    monkeypatch.setattr(
        subject.finalizer_v8,
        "validate_v8_overlay",
        lambda campaign_root, results_dir: calls.append("overlay") or _overlay(),
    )
    monkeypatch.setattr(subject.dashboard_v7, "patched_v7_context", dashboard_context)
    monkeypatch.setattr(
        subject.dashboard_v7.implementation_v4,
        "load_dashboard_data",
        lambda **_kwargs: calls.append("dashboard") or {"repetitions": 30},
    )
    result = subject._V8DashboardReader(tmp_path).load_dashboard_data(  # noqa: SLF001
        results_dir=tmp_path,
        target_registry_path=tmp_path / "registry.json",
    )
    assert result == {"repetitions": 30}
    assert calls == [
        "enter-finalizer",
        "overlay",
        "enter-dashboard",
        "dashboard",
        "exit-dashboard",
        "exit-finalizer",
    ]


def test_reducer_binding_uses_v8_contract_builder_and_restores(
    tmp_path: Path,
) -> None:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_pipeline as pipeline_v7,
    )
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage2_pipeline as pipeline_v8,
    )

    original = pipeline_v7._contract_payload  # noqa: SLF001
    paths = SimpleNamespace(campaign_root=tmp_path)
    with subject._v8_reducer_binding(paths):  # noqa: SLF001
        assert pipeline_v7._contract_payload is pipeline_v8._contract_payload_v8  # noqa: SLF001
    assert pipeline_v7._contract_payload is original  # noqa: SLF001


def test_manifest_declares_no_future_result_or_quality(tmp_path: Path) -> None:
    payload = subject._adapt_payload(_base_payload(), _overlay())  # noqa: SLF001
    document = subject.render_html(payload)
    paths = SimpleNamespace(final_html=tmp_path / "v8.html")
    manifest = subject._manifest_payload(paths, payload, [], document)  # noqa: SLF001
    contract = manifest["scientific_contract"]
    assert manifest["view_count"] == 3
    assert contract["quality"] is False
    assert contract["future_or_placeholder_results_displayed"] is False
    assert contract["focus_lane"] == subject.FOCUS_LANE_ID
