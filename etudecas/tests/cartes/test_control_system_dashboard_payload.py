import csv
import json
from pathlib import Path

from etudecas.visualization.maps.control_system_dashboard_payload import (
    CONTROL_SYSTEM_DASHBOARD_SCHEMA_VERSION,
    build_control_system_dashboard_section,
)
from etudecas.visualization.maps.scan_dashboard_payload import (
    build_scan_dashboard_payload,
)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_scan_manifest(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "run_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "scan.test.v1",
                "source": {
                    "mode": "test",
                    "days": 30,
                    "baseline_industrial_status": "non_industrial",
                },
                "limitations": ["Paquet de test."],
            }
        ),
        encoding="utf-8",
    )


def _write_control_system_package(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "canonical_control_system_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "scan.canonical_control_system.v1",
                "status": "complete",
                "claim_scope": "modèle linéarisé autour du régime fournisseur stressé",
                "operating_point": {"condition": "supplier_stress"},
                "dimensions": {"states": 4, "inputs": 2, "outputs": 3},
                "claims": {
                    "local_linear_model_validated": True,
                    "poles_validated": True,
                    "local_stability_demonstrated": True,
                },
                "controllability": {"rank": 4, "condition_number": 120.0},
                "observability": {"rank": 3, "condition_number": 450.0},
                "limitations": [
                    "La linéarisation ne couvre pas les commutations de régime."
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (path / "canonical_control_system_report.md").write_text(
        "# Analyse système\n\nRésultats locaux et limites documentées.\n\n"
        "Les pôles sont validés.",
        encoding="utf-8",
    )
    _write_csv(
        path / "canonical_control_system_poles.csv",
        [
            {
                "mode": "slow",
                "real": -0.1,
                "imag": 0.2,
                "magnitude": 0.95,
                "validated": "true",
                "status": "validated",
            },
            {
                "mode": "spurious",
                "real": 1.2,
                "imag": 0,
                "magnitude": 1.2,
                "validated": "true",
                "status": "rejected_exploratory_fit",
            },
        ],
    )
    _write_csv(
        path / "canonical_control_system_controllability.csv",
        [{"rank": 4, "dimension": 4, "condition_number": 120.0}],
    )
    (path / "canonical_control_system_poles.png").write_bytes(
        b"\x89PNG\r\n\x1a\ncontrol-system-test"
    )


def test_control_system_section_requires_manifest_and_report(
    tmp_path: Path,
) -> None:
    unavailable = {
        "schema_version": CONTROL_SYSTEM_DASHBOARD_SCHEMA_VERSION,
        "available": False,
        "status": "control_system_results_not_provided",
        "html": "",
        "figure_count": 0,
    }
    assert build_control_system_dashboard_section(None) == unavailable

    (tmp_path / "canonical_control_system_manifest.json").write_text(
        "{}", encoding="utf-8"
    )
    assert build_control_system_dashboard_section(tmp_path) == unavailable

    (tmp_path / "canonical_control_system_manifest.json").write_text(
        json.dumps({"status": "complete"}), encoding="utf-8"
    )
    assert build_control_system_dashboard_section(tmp_path) == unavailable


def test_control_system_section_renders_metrics_tables_and_figures_conservatively(
    tmp_path: Path,
) -> None:
    _write_control_system_package(tmp_path)

    payload = build_control_system_dashboard_section(tmp_path)

    assert payload["available"] is True
    assert payload["status"] == "ready"
    assert payload["figure_count"] == 1
    assert payload["metrics"]["state_dimension"] == 4
    assert payload["metrics"]["input_dimension"] == 2
    assert payload["metrics"]["output_dimension"] == 3
    assert payload["metrics"]["controllability_rank"] == 4
    assert payload["metrics"]["controllability_full_rank"] is True
    assert payload["metrics"]["observability_rank"] == 3
    assert payload["metrics"]["observability_full_rank"] is False
    assert payload["metrics"]["pole_count"] == 2
    assert payload["metrics"]["validated_pole_count"] == 1
    assert payload["metrics"]["rejected_pole_count"] == 1
    assert payload["metrics"]["pole_claim_conflict"] is True
    assert payload["metrics"]["local_stability_demonstrated"] is False
    assert "Contrôlabilité" in payload["html"]
    assert "Observabilité" in payload["html"]
    assert "Validé pour le modèle local documenté" in payload["html"]
    assert "Rejeté / non validé" in payload["html"]
    assert "1 / 2" in payload["html"]
    assert "Stabilité locale" in payload["html"]
    assert "non démontrée" in payload["html"]
    assert "La carte refuse donc cette généralisation" in payload["html"]
    assert "data:image/png;base64," in payload["html"]
    assert "Résultats locaux et limites documentées" in payload["html"]
    assert "Les pôles sont validés" not in payload["html"]
    assert "Assertion positive sur les pôles masquée" in payload["html"]
    assert "scanControlSystemReport" in payload["html"]
    assert "white-space:pre-wrap" in payload["html"]
    assert str(tmp_path) not in payload["html"]


def test_exploratory_model_never_promotes_its_poles_or_rank(
    tmp_path: Path,
) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "canonical_control_system_manifest.json").write_text(
        json.dumps(
            {
                "status": "validated",
                "dimensions": {"states": 2, "inputs": 1, "outputs": 1},
                "claims": {
                    "local_linear_model_validated": False,
                    "local_stability_demonstrated": True,
                },
                "controllability": {"rank": 2},
                "observability": {"rank": 2},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "canonical_control_system_report.md").write_text(
        "Exploration locale.", encoding="utf-8"
    )
    _write_csv(
        tmp_path / "canonical_control_system_eigenvalues.csv",
        [
            {
                "real": -0.2,
                "imag": 0,
                "validated": "true",
                "status": "validated",
            }
        ],
    )

    payload = build_control_system_dashboard_section(tmp_path)

    assert payload["metrics"]["local_model_validated"] is False
    assert payload["metrics"]["validated_pole_count"] == 0
    assert payload["metrics"]["exploratory_pole_count"] == 1
    assert payload["metrics"]["local_stability_demonstrated"] is False
    assert "analyse disponible — modèle local non validé" in payload["html"]
    assert "Exploratoire / validation absente" in payload["html"]
    assert "rang calculé; portée exploratoire" in payload["html"]
    assert "démontrée sur le modèle local" not in payload["html"]


def test_scan_dashboard_adds_control_system_pane_without_changing_legacy_html(
    tmp_path: Path,
) -> None:
    scan_root = tmp_path / "scan"
    control_root = tmp_path / "control"
    _write_scan_manifest(scan_root)
    _write_control_system_package(control_root)

    legacy = build_scan_dashboard_payload(scan_root)
    explicit_legacy = build_scan_dashboard_payload(
        scan_root, None, None, None, None
    )
    combined = build_scan_dashboard_payload(
        scan_root, None, None, None, control_root
    )

    assert explicit_legacy == legacy
    assert "control_system_available" not in legacy["metrics"]
    assert 'data-scan-dashboard-tab="control-system"' not in legacy["html"]
    assert combined["figure_count"] == legacy["figure_count"] + 1
    assert combined["metrics"]["control_system_available"] is True
    assert combined["metrics"]["control_system_controllability_rank"] == 4
    assert combined["metrics"]["control_system_validated_pole_count"] == 1
    assert combined["metrics"]["control_system_pole_claim_conflict"] is True
    assert 'data-scan-dashboard-tab="control-system"' in combined["html"]
    assert 'data-scan-dashboard-pane="control-system"' in combined["html"]
    assert "Analyse système" in combined["html"]

    invalid = build_scan_dashboard_payload(
        scan_root, None, None, None, tmp_path / "missing"
    )
    assert invalid["metrics"]["control_system_available"] is False
    assert 'data-scan-dashboard-tab="control-system"' not in invalid["html"]
    assert invalid["html"] == legacy["html"]
    assert invalid["figure_count"] == legacy["figure_count"]


def test_worldmap_cli_accepts_control_system_results_dir(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from etudecas.visualization.maps.build_supplychain_worldmap import parse_args

    monkeypatch.setattr(
        "sys.argv",
        [
            "build_supplychain_worldmap.py",
            "--scan-control-system-results-dir",
            str(tmp_path / "control"),
        ],
    )

    args = parse_args()

    assert args.scan_control_system_results_dir == str(tmp_path / "control")
