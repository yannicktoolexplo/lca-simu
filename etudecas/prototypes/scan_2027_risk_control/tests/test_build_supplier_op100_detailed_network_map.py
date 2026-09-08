from pathlib import Path

from etudecas.prototypes.scan_2027_risk_control import (
    build_supplier_op100_detailed_network_map as subject,
)


def test_render_is_standalone_and_business_readable() -> None:
    payload = {
        "lanes": [],
        "campaign_signature": subject.EXPECTED_CAMPAIGN_SIGNATURE,
        "source_package_signature": subject.EXPECTED_PACKAGE_SIGNATURE,
    }
    document = subject.render_html(payload)
    assert "Carte du réseau" in document
    assert "Fournisseurs → sites" not in document  # Copy lives in header, not a claim of geography.
    assert "Service dégradé" in document
    assert "Effet de seuil" in document
    assert "états 93 et 80" in document
    assert "https://" not in document
    assert "<script>" in document


def test_output_is_new_only(tmp_path: Path) -> None:
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    try:
        subject.build(tmp_path, tmp_path / "lanes.csv", occupied)
    except subject.DetailedMapError as exc:
        assert "déjà existante" in str(exc)
    else:
        raise AssertionError("An existing destination must be refused")
