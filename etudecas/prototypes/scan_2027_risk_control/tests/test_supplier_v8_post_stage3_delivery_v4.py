from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_post_stage3_delivery_v4 as delivery,
)


STOCK_ENTITIES = (
    "M-1810|099439",
    "M-1430|730384",
    "M-1810|016332",
    "M-1810|001848",
    "M-1810|029313",
    "M-1430|708073",
    "M-1430|038005",
    "M-1810|049371",
    "M-1430|333362",
    "M-1810|338928",
    "M-1810|001893",
    "M-1810|055703",
    "M-1810|338929",
    "M-1430|042342",
    "M-1810|001757",
    "M-1810|426331",
    "M-1430|344135",
    "M-1430|734545",
)


def _nominal_subjects() -> list[tuple[str, str, str, int, str]]:
    rows = [
        ("service", entity, metric, window, unit)
        for entity in ("global", "268091", "268967")
        for metric, window, unit in (
            ("service_a_l_heure", 28, "%"),
            ("retard_client", 7, "UN"),
        )
    ]
    rows.extend(
        ("production", entity, metric, window, unit)
        for entity in ("268091", "268967")
        for metric, window, unit in (
            ("production_liberee", 28, "UN/jour"),
            ("production_achevee", 28, "UN/jour"),
            ("encours", 7, "UN"),
            ("stock_produit_fini", 7, "UN"),
        )
    )
    rows.extend(
        ("stock_entrant", entity, "stock_entrant", 7, "UN") for entity in STOCK_ENTITIES
    )
    rows.extend(
        ("contrainte", entity, metric, window, unit)
        for entity in ("268091", "268967")
        for metric, window, unit in (
            ("ecart_plan_lot", 28, "UN/jour"),
            ("penurie_entree", 7, "part_de_jours"),
        )
    )
    assert len(rows) == 36
    return rows


def _curve_payload() -> dict[str, Any]:
    series = []
    for state_index, state in enumerate(delivery.STATE_ORDER):
        for subject_index, (domain, entity, metric, window, unit) in enumerate(
            _nominal_subjects()
        ):
            centre = 10.0 + state_index + subject_index / 10
            points = [
                [day, centre, centre - 2, centre, centre + 2]
                for day in range(window - 1, 720)
            ]
            series.append(
                {
                    "state": state,
                    "domain": domain,
                    "entity": entity,
                    "metric": metric,
                    "unit": unit,
                    "rolling_window_days": window,
                    "sample_count": 30,
                    "columns": ["day", "mean", "p10", "median", "p90"],
                    "points": points,
                }
            )
    return {
        "scope": {"case_count": 90},
        "series": series,
    }


def _aggregate_rows() -> list[dict[str, Any]]:
    rows = []
    for state in delivery.STATE_ORDER:
        for mechanism in delivery.MECHANISM_ORDER:
            rows.append(
                {
                    "state": state,
                    "mechanism": mechanism,
                    "lane_id": delivery.FOCUS_IDENTITY["lane_id"],
                    "supplier_id": delivery.FOCUS_IDENTITY["supplier_id"],
                    "item_id": "item:338929",
                    "dst_node_id": delivery.FOCUS_IDENTITY["dst_node_id"],
                    "target_product_id": "item:268091",
                    "priority_status": "dossier_to_investigate",
                    "physically_exercised_seed_count": 30,
                    "signed_baseline_minus_incident_service_pp": {
                        "mean": 1.5,
                        "p10": 0.2,
                        "p90": 2.8,
                        "ci95_low": 0.1,
                        "ci95_high": 2.9,
                    },
                }
            )
    return rows


def _stage3_payload() -> dict[str, Any]:
    states = []
    for index, state in enumerate(delivery.STATE_ORDER):
        states.append(
            {
                "id": state,
                "label": state,
                "measures": [
                    {"id": entity, "service_pct": 99 - 5 * index, "interval": {}}
                    for entity in ("global", "268091", "268967")
                ],
                "planned_lead_offset_days": {
                    "268091": 10 * index,
                    "268967": 12 * index,
                },
            }
        )
    lane_rows = []
    for mechanism in delivery.MECHANISM_ORDER:
        lane_rows.append(
            {
                "mechanism": mechanism,
                "lane_id": delivery.FOCUS_IDENTITY["lane_id"],
                "supplier_id": delivery.FOCUS_IDENTITY["supplier_id"],
                "target_product_id": "268091",
                "state_comparison_valid": True,
                "comparable_seed_count": 30,
                "required_comparable_seed_count": 30,
                "interpretation_fr": "Effet apparié comparable.",
                "states": {
                    state: {
                        "effect_mean_pp": float(index),
                        "priority_status": "dossier_to_investigate",
                        "rank_min": 1,
                        "rank_max": 2,
                    }
                    for index, state in enumerate(delivery.STATE_ORDER)
                },
                "paired_changes_vs_reference_pp": {
                    state: {
                        "mean": float(index),
                        "ci95_low": float(index) - 0.2,
                        "ci95_high": float(index) + 0.2,
                    }
                    for index, state in enumerate(delivery.STATE_ORDER)
                },
            }
        )
    stability = [
        {
            "mechanism": mechanism,
            "supplier_id": delivery.FOCUS_IDENTITY["supplier_id"],
            "same_dominant_lane": True,
            "stability_status": "priority_all_states",
            "states": {
                state: {
                    "priority_status": "dossier_to_investigate",
                    "rank_min": 1,
                    "rank_max": 2,
                }
                for state in delivery.STATE_ORDER
            },
        }
        for mechanism in delivery.MECHANISM_ORDER
    ]
    unsigned = {
        "schema_version": delivery.delivery_v3.SCHEMA_VERSION,
        "status": "complete_validated",
        "view_count": 3,
        "terminology": {
            "OBSERVÉ": "donnée industrielle",
            "SIMULÉ": "résultat du moteur",
            "SIGNAL DE PRIORITÉ": "dossier à examiner",
            "HYPOTHÈSE": "paramètre à confirmer",
        },
        "validation": {"states": states, "seed_blocks": 150, "physical_cases": 450},
        "campaign": {
            "incident_case_count": 3_240,
            "multiple_incidents_combined": False,
            "mechanisms": [
                {
                    "id": "transport_delay",
                    "label": "Retard de transport +120 jours",
                    "hypothesis": "Les départs planifiés arrivent 120 jours plus tard.",
                },
                {
                    "id": "planned_delivery_shortfall",
                    "label": "Quantité normalement livrable × 0,5 pendant 42 jours",
                    "hypothesis": "La quantité normalement livrable est divisée par deux.",
                },
            ],
        },
        "observed_2025": None,
        "lane_sensitivity": lane_rows,
        "supplier_stability": stability,
        "portfolio": {"mechanisms": []},
        "focus": {
            "lane_id": delivery.FOCUS_IDENTITY["lane_id"],
            "item_id": "338929",
            "aggregate_incident_results": _aggregate_rows(),
        },
        "nominal_curves": {"series": []},
        "cascade": {"detailed_replays": []},
        "actions": {"actions": [], "refusals": []},
        "limits": {
            "quality_incident_included": False,
            "capacity_or_availability_modified": False,
            "automatic_regulation": False,
        },
        "bindings": {},
    }
    return delivery.common.signed(unsigned, "payload_signature")


def _focus_detail(mechanism: str, position: int) -> dict[str, Any]:
    trace = {
        "shipment_to_mp_lots": [
            {
                "risk_decision_day": 214,
                "shipment_id": f"SHIP-{position}",
                "receipt_lot_id": f"incident::MP-{position}",
                "child_qty": 50.0,
                "uom_guard": "validated",
            }
        ],
        "exposed_consumption_wip": [],
        "exposed_finished_lots": [],
        "exposed_client_events": [],
    }
    curves = []
    for metric, label, unit, window in delivery.FOCUS_CURVE_DEFINITIONS:
        raw = [[day, 10.0, 9.0] for day in range(35)]
        smooth = [[day, 10.0, 9.0] for day in range(window - 1, 35)]
        curves.append(
            {
                "metric": metric,
                "label_fr": label,
                "unit": unit,
                "rolling_window_days": window,
                "raw": raw,
                "smooth": smooth,
            }
        )
    return {
        "trajectory_label_fr": f"Trajectoire {position}",
        "dossier_id": f"FOCUS-{position}",
        "mode": "new_focus",
        "selection_basis": delivery.focus_v1.SELECTION_BASIS,
        "operating_point_id": "op_93",
        "mechanism": mechanism,
        **delivery.FOCUS_IDENTITY,
        "risk_window_start_day": 214,
        "risk_window_end_day": 255,
        "impact_window_start_day": 214,
        "impact_window_end_day": 248,
        "single_trajectory": True,
        "trajectory_selection_uses_service_outcomes": False,
        "trajectory_interpretation_fr": "Trajectoire illustrative.",
        "curves": {"horizon_days": 35, "series": curves},
        "kpis": {
            "impact_window_start_day": 214,
            "impact_window_end_day": 248,
            "service_loss_pp": 1.2,
            "on_due_units_lost": 15.0,
            "production_released_loss_qty": 20.0,
            "backlog_recovery_day": None,
        },
        "equal_cumulative_volume_lags": [
            {
                "baseline_volume_fraction": 0.5,
                "baseline_reach_day": 220,
                "incident_reach_day": 222,
                "lag_days": 2,
                "status": "calculated",
            }
        ],
        "trace_completeness": "partial_native_contact_trace",
        "trace_counts": {key: len(value) for key, value in trace.items()},
        "trace": trace,
        "cross_arm_lot_matching_used": False,
    }


def _delivery_payload() -> dict[str, Any]:
    stage3 = _stage3_payload()
    nominal = delivery._prepare_nominal_curves(_curve_payload())  # noqa: SLF001
    details = [
        _focus_detail(mechanism, index)
        for index, mechanism in enumerate(delivery.MECHANISM_ORDER, start=1)
    ]
    unsigned = {
        "schema_version": delivery.SCHEMA_VERSION,
        "status": "complete_validated",
        "title": "fixture réaliste",
        "view_count": 3,
        "terminology": copy.deepcopy(stage3["terminology"]),
        "stage3": stage3,
        "stage3_preservation": {
            "payload_signature": stage3["payload_signature"],
            "canonical_payload_sha256": hashlib.sha256(
                delivery.common.canonical_json_bytes(stage3)
            ).hexdigest(),
            "selection_signature": "a" * 64,
            "selection_sha256": hashlib.sha256(b"[]").hexdigest(),
            "selection": [],
            "selection_order_preserved": True,
            "selection_modified": False,
            "focus_inserted_into_scientific_selection": False,
            "stage3_html_sha256": "b" * 64,
        },
        "requested_focus_338929": {
            "selection_basis": delivery.focus_v1.SELECTION_BASIS,
            "focus_is_user_requested": True,
            "focus_is_priority_claim": False,
            "identity": copy.deepcopy(delivery.FOCUS_IDENTITY),
            "operating_point_id": "op_93",
            "common_seed": 17,
            "plan_signature": "c" * 64,
            "validation_signature": "d" * 64,
            "mechanisms": list(delivery.MECHANISM_ORDER),
            "details": details,
            "aggregate_results": _aggregate_rows(),
            "action_results": [],
            "focus_actions_simulated_by_this_step": False,
            "focus_has_existing_signed_stage3_action": False,
            "full_dynamic_cascade_claimed": False,
        },
        "nominal_curves_full": nominal,
        "presentation": {
            "view_order": list(delivery.VIEW_IDS),
            "language": "fr",
            "standalone": True,
        },
        "limits": {},
        "bindings": {},
    }
    return delivery.common.signed(unsigned, "payload_signature")


class _PageProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.view_ids: list[str] = []
        self.active_views = 0
        self.tab_ids: list[str] = []
        self.ids: list[str] = []
        self.csp: list[str] = []
        self.canvas_count = 0
        self.external_attributes: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.append(values["id"])
        classes = set(values.get("class", "").split())
        if tag == "section" and "view" in classes:
            self.view_ids.append(values.get("id", ""))
            self.active_views += int("active" in classes)
        if tag == "button" and values.get("data-tab"):
            self.tab_ids.append(values["data-tab"])
        if tag == "meta" and values.get("http-equiv", "").casefold() == (
            "content-security-policy"
        ):
            self.csp.append(values.get("content", ""))
        if tag == "canvas":
            self.canvas_count += 1
        for name in ("src", "href", "action"):
            value = values.get(name, "")
            if value.startswith(("http:", "https:", "//", "file:")):
                self.external_attributes.append((name, value))


@pytest.fixture(scope="module")
def nominal_payload() -> dict[str, Any]:
    return _curve_payload()


@pytest.fixture(scope="module")
def delivery_payload() -> dict[str, Any]:
    return _delivery_payload()


def test_curve_inventory_is_exact_108_series_36_subjects(
    nominal_payload: dict[str, Any],
) -> None:
    result = delivery._prepare_nominal_curves(nominal_payload)  # noqa: SLF001
    series = result["series"]
    subjects = result["subjects"]
    assert result["source_series_count"] == 108
    assert result["logical_subject_count"] == 36
    assert len(series) == 108
    assert len(subjects) == 36
    assert (
        len(
            {
                (
                    row["state"],
                    row["domain"],
                    row["entity"],
                    row["metric"],
                    row["rolling_window_days"],
                )
                for row in series
            }
        )
        == 108
    )
    assert {row["state"] for row in series} == set(delivery.STATE_ORDER)
    assert sum(row["domain"] == "stock_entrant" for row in subjects) == 18
    assert any(row["entity"] == "M-1810|338929" for row in subjects)
    assert all(row["sample_count"] == 30 for row in series)
    assert all(row["points"][-1][0] == 719 for row in series)


def test_curve_inventory_rejects_missing_series(
    nominal_payload: dict[str, Any],
) -> None:
    bad = copy.deepcopy(nominal_payload)
    bad["series"].pop()
    with pytest.raises(delivery.DeliveryV4Error, match="108"):
        delivery._prepare_nominal_curves(bad)  # noqa: SLF001


def test_rendered_page_has_three_real_views_and_strict_csp(
    delivery_payload: dict[str, Any],
) -> None:
    document = delivery.render_html(delivery_payload)
    probe = _PageProbe()
    probe.feed(document)
    assert probe.view_ids == list(delivery.VIEW_IDS)
    assert probe.tab_ids == list(delivery.VIEW_IDS)
    assert probe.active_views == 1
    assert len(probe.ids) == len(set(probe.ids))
    assert probe.canvas_count >= 3
    assert len(probe.csp) == 1
    for directive in (
        "default-src 'none'",
        "script-src 'unsafe-inline'",
        "style-src 'unsafe-inline'",
        "connect-src 'none'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ):
        assert directive in probe.csp[0]
    assert document.index("Content-Security-Policy") < document.index("<style>")
    assert not probe.external_attributes
    assert not delivery._NETWORK_API_RE.search(document)  # noqa: SLF001
    assert not delivery._WINDOWS_PATH_RE.search(document)  # noqa: SLF001


def test_embedded_javascript_is_syntactically_valid(
    tmp_path: Path, delivery_payload: dict[str, Any]
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js absent : contrôle syntaxique JavaScript non disponible")
    document = delivery.render_html(delivery_payload)
    script = document.split("<script>", 1)[1].split("</script>", 1)[0]
    path = tmp_path / "delivery.js"
    path.write_text(script, encoding="utf-8")
    result = subprocess.run(
        [node, "--check", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_safe_json_escapes_script_breakout_and_line_separators() -> None:
    encoded = delivery._safe_json(  # noqa: SLF001
        {"value": "</script>&>\u2028\u2029"}
    )
    assert "</script>" not in encoded
    assert "\\u003c/script\\u003e" in encoded
    assert "\\u0026" in encoded
    assert "\\u2028" in encoded
    assert "\\u2029" in encoded


def test_render_rejects_local_path_in_embedded_payload(
    delivery_payload: dict[str, Any],
) -> None:
    bad = copy.deepcopy(delivery_payload)
    bad["leak"] = "C:\\private\\supplier.csv"
    with pytest.raises(delivery.DeliveryV4Error, match="chemin local"):
        delivery.render_html(bad)


def test_render_rejects_unc_path_in_embedded_payload(
    delivery_payload: dict[str, Any],
) -> None:
    bad = copy.deepcopy(delivery_payload)
    bad["leak"] = r"\\serveur\partage\supplier.csv"
    with pytest.raises(delivery.DeliveryV4Error, match="chemin local"):
        delivery.render_html(bad)


def _collected(payload: dict[str, Any], source: Path) -> delivery.CollectedEvidence:
    raw = source.read_bytes()
    return delivery.CollectedEvidence(
        payload=copy.deepcopy(payload),
        sources=[
            {
                "role": "fixture_signée",
                "name": source.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        ],
        snapshots={source.resolve(): raw},
    )


def test_build_validate_is_idempotent_and_preserves_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    delivery_payload: dict[str, Any],
) -> None:
    source = tmp_path / "preuve.json"
    source.write_text('{"status":"signed"}\n', encoding="utf-8")
    evidence = _collected(delivery_payload, source)
    monkeypatch.setattr(delivery, "_validate_output_separation", lambda *_a, **_k: None)
    monkeypatch.setattr(delivery, "collect_evidence", lambda *_a, **_k: evidence)
    output = tmp_path / "delivery-v4"
    before = source.read_bytes()
    first = delivery.build_delivery(tmp_path / "s3", source, tmp_path / "f", output)
    html = output / delivery.OUTPUT_NAME
    manifest_path = output / delivery.MANIFEST_NAME
    first_bytes = (html.read_bytes(), manifest_path.read_bytes())
    first_times = (html.stat().st_mtime_ns, manifest_path.stat().st_mtime_ns)
    second = delivery.build_delivery(tmp_path / "s3", source, tmp_path / "f", output)
    assert first == second
    assert source.read_bytes() == before
    assert {path.name for path in output.iterdir()} == {
        delivery.OUTPUT_NAME,
        delivery.MANIFEST_NAME,
    }
    assert (html.read_bytes(), manifest_path.read_bytes()) == first_bytes
    assert (html.stat().st_mtime_ns, manifest_path.stat().st_mtime_ns) == first_times
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["view_count"] == 3
    assert manifest["nominal_series_count"] == 108
    assert manifest["nominal_subject_count"] == 36
    assert manifest["engine_runs_performed"] == 0
    public = html.read_text(encoding="utf-8") + manifest_path.read_text(
        encoding="utf-8"
    )
    assert not delivery._WINDOWS_PATH_RE.search(public)  # noqa: SLF001


@pytest.mark.parametrize(
    "orphan", [delivery.OUTPUT_NAME, delivery.MANIFEST_NAME, "foreign.txt"]
)
def test_build_refuses_orphan_or_foreign_output_without_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    delivery_payload: dict[str, Any],
    orphan: str,
) -> None:
    source = tmp_path / "proof.bin"
    source.write_bytes(b"proof")
    evidence = _collected(delivery_payload, source)
    monkeypatch.setattr(delivery, "_validate_output_separation", lambda *_a, **_k: None)
    monkeypatch.setattr(delivery, "collect_evidence", lambda *_a, **_k: evidence)
    output = tmp_path / "output"
    output.mkdir()
    target = output / orphan
    target.write_bytes(b"do-not-overwrite")
    with pytest.raises(delivery.DeliveryV4Error):
        delivery.build_delivery(tmp_path / "s", source, tmp_path / "f", output)
    assert target.read_bytes() == b"do-not-overwrite"
    assert len(list(output.iterdir())) == 1


def test_validate_reconstructs_instead_of_trusting_a_resigned_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    delivery_payload: dict[str, Any],
) -> None:
    source = tmp_path / "proof.bin"
    source.write_bytes(b"proof")
    evidence = _collected(delivery_payload, source)
    monkeypatch.setattr(delivery, "_validate_output_separation", lambda *_a, **_k: None)
    monkeypatch.setattr(delivery, "collect_evidence", lambda *_a, **_k: evidence)
    output = tmp_path / "output"
    delivery.build_delivery(tmp_path / "s", source, tmp_path / "f", output)
    html_path = output / delivery.OUTPUT_NAME
    manifest_path = output / delivery.MANIFEST_NAME
    html_path.write_text(
        html_path.read_text(encoding="utf-8") + "<!-- altéré -->", encoding="utf-8"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    unsigned = {
        key: value for key, value in manifest.items() if key != "manifest_signature"
    }
    raw = html_path.read_bytes()
    unsigned["html_sha256"] = hashlib.sha256(raw).hexdigest()
    unsigned["html_bytes"] = len(raw)
    resigned = delivery.common.signed(unsigned, "manifest_signature")
    manifest_path.write_text(
        json.dumps(resigned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with pytest.raises(delivery.DeliveryV4Error, match="reproduit"):
        delivery.validate_delivery(tmp_path / "s", source, tmp_path / "f", output)


def test_snapshot_guard_refuses_toctou_before_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    delivery_payload: dict[str, Any],
) -> None:
    source = tmp_path / "proof.bin"
    source.write_bytes(b"before")
    evidence = _collected(delivery_payload, source)
    monkeypatch.setattr(delivery, "_validate_output_separation", lambda *_a, **_k: None)
    monkeypatch.setattr(delivery, "collect_evidence", lambda *_a, **_k: evidence)
    original_render = delivery.render_html

    def mutate(payload: dict[str, Any]) -> str:
        result = original_render(payload)
        source.write_bytes(b"after")
        return result

    monkeypatch.setattr(delivery, "render_html", mutate)
    output = tmp_path / "output"
    with pytest.raises(delivery.DeliveryV4Error, match="changé"):
        delivery.build_delivery(tmp_path / "s", source, tmp_path / "f", output)
    assert not output.exists()


def test_snapshot_guard_quarantines_just_published_root_and_allows_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    delivery_payload: dict[str, Any],
) -> None:
    source = tmp_path / "proof.bin"
    source.write_bytes(b"before")
    evidence = _collected(delivery_payload, source)
    monkeypatch.setattr(delivery, "_validate_output_separation", lambda *_a, **_k: None)
    monkeypatch.setattr(delivery, "collect_evidence", lambda *_a, **_k: evidence)
    original_publish = delivery._publish_root_new_or_identical  # noqa: SLF001

    def publish_then_mutate(*args, **kwargs) -> bool:
        created = original_publish(*args, **kwargs)
        source.write_bytes(b"after")
        return created

    monkeypatch.setattr(delivery, "_publish_root_new_or_identical", publish_then_mutate)
    output = tmp_path / "output"
    with pytest.raises(delivery.DeliveryV4Error, match="changé"):
        delivery.build_delivery(tmp_path / "s", source, tmp_path / "f", output)
    assert not output.exists()
    rejected = list(tmp_path.glob(".output.rejected.*"))
    assert len(rejected) == 1
    assert {path.name for path in rejected[0].iterdir()} == {
        delivery.OUTPUT_NAME,
        delivery.MANIFEST_NAME,
    }

    source.write_bytes(b"before")
    monkeypatch.setattr(delivery, "_publish_root_new_or_identical", original_publish)
    monkeypatch.setattr(
        delivery,
        "validate_delivery",
        lambda *_a, **_k: {"valid": True, "retry": True},
    )
    assert delivery.build_delivery(tmp_path / "s", source, tmp_path / "f", output)[
        "retry"
    ]
    assert output.is_dir()


def test_every_dynamic_stage3_source_is_added_to_snapshot_guard() -> None:
    source = Path(delivery.__file__).read_text(encoding="utf-8")
    collect = source.split("def collect_evidence", 1)[1].split("def _safe_json", 1)[0]
    collected = collect.index("stage3_payload, stage3_sources")
    snapshotted = collect.index("snapshots.update(_snapshot(stage3_source_paths))")
    final_guard = collect.rindex("_assert_snapshots_unchanged(snapshots)")
    assert collected < snapshotted < final_guard
    assert "for source in stage3_sources:" in collect
    assert "len(stage3_source_paths) != len(set(stage3_source_paths))" in collect


def test_stage3_selection_is_checked_without_mutation() -> None:
    payload = _stage3_payload()
    before = copy.deepcopy(payload)
    delivery._validate_stage3_payload(payload, [])  # noqa: SLF001
    assert payload == before
    bad = copy.deepcopy(payload)
    bad["focus"]["item_id"] = "OTHER"
    bad = delivery.common.signed(
        {key: value for key, value in bad.items() if key != "payload_signature"},
        "payload_signature",
    )
    with pytest.raises(delivery.DeliveryV4Error, match="modifiée"):
        delivery._validate_stage3_payload(bad, [])  # noqa: SLF001


def _focus_plan(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    dossiers = []
    validation_rows = []
    for index, mechanism in enumerate(delivery.MECHANISM_ORDER, start=1):
        dossier_id = f"FOCUS-{index}"
        priority = {
            **delivery.FOCUS_IDENTITY,
            "item_id": "item:338929",
            "target_product_id": "item:268091",
            "operating_point_id": "op_93",
            "mechanism": mechanism,
        }
        dossier = {
            "dossier_id": dossier_id,
            "priority": priority,
            "risk_row": {"start_day": 214, "end_day": 255},
            "incident_metric": {
                "impact_window_start_day": 0,
                "impact_window_end_day": 34,
            },
            "seed": 17,
            "horizon_days": 35,
            "arms": {
                arm: {"run_dir": str(tmp_path / dossier_id / arm)}
                for arm in ("baseline", "incident")
            },
        }
        dossiers.append(
            {
                "mode": "new_focus",
                "selection_basis": delivery.focus_v1.SELECTION_BASIS,
                "dossier": dossier,
            }
        )
        trace = {
            "shipment_to_mp_lots": [],
            "exposed_consumption_wip": [],
            "exposed_finished_lots": [],
            "exposed_client_events": [],
        }
        validation_rows.append(
            {
                "dossier_id": dossier_id,
                "mode": "new_focus",
                "counts": {key: 0 for key in trace},
                "trace_completeness": "partial_native_contact_trace",
                "trace": trace,
            }
        )
    plan = {
        "schema_version": delivery.focus_v1.PLAN_SCHEMA,
        "selection_basis": delivery.focus_v1.SELECTION_BASIS,
        "supplier_id": delivery.FOCUS_IDENTITY["supplier_id"],
        "item_id": "item:338929",
        "common_seed": 17,
        "scientific_contract": {
            "priority_claimed": False,
            "quality_included": False,
            "state_dependent_risks_enabled": False,
            "capacity_or_availability_modified": False,
            "common_random_numbers": True,
            "seed_selection_uses_outcomes": False,
        },
        "dossiers": dossiers,
        "plan_signature": "a" * 64,
    }
    validation = {
        "schema_version": delivery.focus_v1.VALIDATION_SCHEMA,
        "status": "complete_validated",
        "selection_basis": delivery.focus_v1.SELECTION_BASIS,
        "dossiers": validation_rows,
        "validation_signature": "b" * 64,
    }
    return plan, validation


def test_focus_reducer_keeps_two_mechanisms_wip_and_partial_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, validation = _focus_plan(tmp_path)
    horizon = 35
    curve_rows = [
        {
            "day": day,
            "metric": metric,
            "baseline_value": 10.0,
            # Demand is an exogenous paired input and must remain identical.
            "incident_value": 10.0 if metric == "demand" else 9.0,
        }
        for metric in (
            "component_stock",
            "production_released",
            "wip",
            "demand",
            "served_on_due",
            "backlog",
        )
        for day in range(horizon)
    ]
    kpis = {
        "impact_window_start_day": 0,
        "impact_window_end_day": 34,
        "service_loss_pp": 1.0,
        "on_due_units_lost": 2.0,
        "production_released_loss_qty": 3.0,
        "backlog_recovery_day": None,
    }
    monkeypatch.setattr(delivery.lot_v4, "_validate_pair", lambda _d: None)
    monkeypatch.setattr(
        delivery.lot_v4,
        "_paired_curves_and_kpis",
        lambda *_a, **_k: (curve_rows, [], kpis),
    )
    result = delivery._prepare_focus(plan, validation)  # noqa: SLF001
    assert [row["mechanism"] for row in result["details"]] == list(
        delivery.MECHANISM_ORDER
    )
    assert all(
        any(series["metric"] == "wip" for series in row["curves"]["series"])
        for row in result["details"]
    )
    assert all(
        row["trace_completeness"] == "partial_native_contact_trace"
        for row in result["details"]
    )
    assert result["action_results"] == []


def test_focus_loader_rejects_plan_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        delivery.focus_v1,
        "validate",
        lambda _root: {"status": "valid_plan_only"},
    )
    with pytest.raises(delivery.DeliveryV4Error, match="complètement validé"):
        delivery._load_complete_focus(tmp_path)  # noqa: SLF001


def test_focus_common_seed_and_complete_physical_predicate_are_recomputed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, _ = _focus_plan(tmp_path)
    metric_rows = []
    for mechanism in delivery.MECHANISM_ORDER:
        row = {
            "stage": "incident",
            "operating_point_id": "op_93",
            "mechanism": mechanism,
            "supplier_id": delivery.FOCUS_IDENTITY["supplier_id"],
            "item_id": f"item:{delivery.FOCUS_IDENTITY['item_id']}",
            "dst_node_id": delivery.FOCUS_IDENTITY["dst_node_id"],
            "edge_id": delivery.FOCUS_IDENTITY["edge_id"],
            "lane_id": delivery.FOCUS_IDENTITY["lane_id"],
            "target_product_id": delivery.FOCUS_IDENTITY["target_product_id"],
            "seed": 17,
            "status": "valid",
            "valid": True,
            "incident_physically_exercised": True,
            "risk_applied_row_count": 1,
            "risk_applied_event_count": 1,
            "target_planned_qty": 10,
            "target_shipped_qty": 9,
            "incident_effective_dose_qty_days": 90,
            "incident_effective_dose_qty": 9,
            "baseline_lane_shipped_qty_state_window": 10,
        }
        metric_rows.append(row)
    for plan_row, metric in zip(plan["dossiers"], metric_rows, strict=True):
        plan_row["dossier"]["incident_metric"] = copy.deepcopy(metric)
    monkeypatch.setattr(delivery.lot_v4, "_verify_campaign_manifest", lambda _path: {})
    monkeypatch.setattr(
        delivery.lot_v4,
        "_validate_campaign_results",
        lambda **_kwargs: ({}, {}, [tmp_path / "metrics.csv"]),
    )
    monkeypatch.setattr(
        delivery.lot_v4, "_load_metric_rows", lambda _paths: metric_rows
    )
    context = SimpleNamespace(
        paths=SimpleNamespace(campaign_root=tmp_path, results_dir=tmp_path)
    )
    delivery._revalidate_focus_selection(context, plan)  # noqa: SLF001
    plan["dossiers"][0]["dossier"]["incident_metric"]["risk_applied_event_count"] = 0
    with pytest.raises(delivery.DeliveryV4Error, match="prédicat physique complet"):
        delivery._revalidate_focus_selection(context, plan)  # noqa: SLF001


@pytest.mark.parametrize(
    "fragment",
    [
        '<script src="https://example.invalid/a.js"></script>',
        "<script>fetch('/x')</script>",
        "<p>C:\\private\\source.csv</p>",
        "<p>C:private\\source.csv</p>",
        '<img srcset="https://example.invalid/a.png 1x">',
        '<meta http-equiv="refresh" content="0;url=https://example.invalid">',
        "<script>window.location='https://example.invalid'</script>",
        "<script>location.href='//example.invalid'</script>",
        "<p>https://example.invalid/a</p>",
        "<p>\\\\server\\share\\source.csv</p>",
        "<p>//server/share/source.csv</p>",
    ],
)
def test_static_offline_validator_rejects_external_or_local_content(
    delivery_payload: dict[str, Any], fragment: str
) -> None:
    document = delivery.render_html(delivery_payload).replace(
        "</body>", fragment + "</body>"
    )
    with pytest.raises(delivery.DeliveryV4Error, match="hors ligne"):
        delivery.validate_document(document)


def test_lane_chart_uses_categorical_points_and_paired_ci() -> None:
    source = Path(delivery.__file__).read_text(encoding="utf-8")
    lane_block = source.split("function drawStatePoints", 1)[1].split(
        "const selected=", 1
    )[0]
    assert "labels=['100 %','93 %','80 %']" in lane_block
    assert "paired_changes_vs_reference_pp" in lane_block
    assert "ci95_low" in lane_block
    assert "ci95_high" in lane_block
    assert "drawLines('laneChart'" not in lane_block


def test_trace_never_uses_uom_guard_as_a_unit() -> None:
    source = Path(delivery.__file__).read_text(encoding="utf-8")
    trace_block = source.split("function traceUnit", 1)[1].split(
        "function renderFocus", 1
    )[0]
    assert "uom_guard" not in trace_block
    assert "r.uom||((r.child_qty" in trace_block
    assert "?'UN':'')" in trace_block


def _direct_closure_report(*, technical: bool, exploitable: bool) -> dict[str, Any]:
    unsigned = {
        "schema_version": delivery.closure_v1.SCHEMA_VERSION,
        "status": "complete_audited",
        "scope": "supplier_v8_v2_and_stage3_v3_final_outputs_only",
        "no_simulation_engine_started": True,
        "source": {"supervision_dir": "stage3"},
        "technical_verdict": {"conforme": technical},
        "business_verdict": {
            "code": "EXPLOITABLE_METIER" if exploitable else "INSUFFISANT_METIER",
            "exploitable": exploitable,
        },
    }
    return delivery.common.signed(unsigned, "closure_signature")


def test_direct_closure_accepts_technical_and_insufficient_business(
    tmp_path: Path, monkeypatch
) -> None:
    report = _direct_closure_report(technical=True, exploitable=False)
    path = tmp_path / "closure.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    context = object()
    monkeypatch.setattr(delivery.closure_v1, "load_final_context", lambda _p: context)
    monkeypatch.setattr(
        delivery.closure_v1, "build_closure_report", lambda _context: report
    )
    assert delivery._validate_closure(tmp_path, path) == (context, report)  # noqa: SLF001


def test_direct_closure_rejects_technical_nonconformity(
    tmp_path: Path, monkeypatch
) -> None:
    report = _direct_closure_report(technical=False, exploitable=True)
    path = tmp_path / "closure.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(delivery.closure_v1, "load_final_context", lambda _p: object())
    monkeypatch.setattr(
        delivery.closure_v1, "build_closure_report", lambda _context: report
    )
    with pytest.raises(delivery.DeliveryV4Error, match="techniquement conforme"):
        delivery._validate_closure(tmp_path, path)  # noqa: SLF001


def test_direct_closure_rejects_reproduced_source_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    report = _direct_closure_report(technical=True, exploitable=False)
    expected = copy.deepcopy(report)
    expected["source"]["supervision_dir"] = "another-stage3"
    expected = delivery.common.signed(
        {key: value for key, value in expected.items() if key != "closure_signature"},
        "closure_signature",
    )
    path = tmp_path / "closure.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(delivery.closure_v1, "load_final_context", lambda _p: object())
    monkeypatch.setattr(
        delivery.closure_v1, "build_closure_report", lambda _context: expected
    )
    with pytest.raises(delivery.DeliveryV4Error, match="reproductible"):
        delivery._validate_closure(tmp_path, path)  # noqa: SLF001


def test_optional_browser_walks_three_views_without_network_or_canvas_error(
    tmp_path: Path, delivery_payload: dict[str, Any]
) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    html = tmp_path / "delivery.html"
    html.write_text(delivery.render_html(delivery_payload), encoding="utf-8")
    requests: list[str] = []
    errors: list[str] = []
    try:
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))

            def reject_network(route) -> None:
                url = route.request.url
                if url.startswith(("http://", "https://", "//")):
                    requests.append(url)
                    route.abort()
                else:
                    route.continue_()

            page.route("**/*", reject_network)
            page.goto(html.as_uri())
            for tab in ("focus", "network", "decisions"):
                page.locator(f'button[data-tab="{tab}"]').click()
                assert page.locator("section.view.active").count() == 1
                assert page.locator(f"section#{tab}.active").count() == 1
            page.locator('button[data-tab="focus"]').click()
            page.locator("#focusRaw").click()
            page.locator("#focusRaw").click()
            page.locator("#traceNext").click(force=True)
            painted = page.locator("canvas").evaluate_all(
                "els => els.map(c => Array.from(c.getContext('2d').getImageData(0,0,c.width,c.height).data).some(v => v !== 0))"
            )
            assert painted == [True, True, True]
            browser.close()
    except playwright.Error as exc:
        pytest.skip(f"navigateur Playwright indisponible: {exc}")
    assert requests == []
    assert errors == []
