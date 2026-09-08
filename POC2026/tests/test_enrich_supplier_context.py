from __future__ import annotations

from POC2026.supply_geo_case.tools.enrich_supplier_context import (
    build_evidence_rows,
    build_query_plan,
    canonicalize_url,
    parse_args,
    score_result,
    summarize_site,
)


SITE = {
    "site_uid": "supplier-a@@site",
    "name": "Acme Metals",
    "roles": "T2",
    "location": "Toulouse, France",
    "country_code": "FR",
    "allocated_mass_kg": "12",
    "path_count": "3",
}


def result(title: str, description: str = "", domain: str = "acme-metals.com") -> dict[str, str]:
    return {
        "title": title,
        "description": description,
        "domain": domain,
        "url": f"https://{domain}/article",
    }


def test_evidence_query_plan_covers_business_families() -> None:
    plan = build_query_plan(
        SITE,
        '"{supplier}" aerospace supplier {location}',
        {"families": "aluminium", "components": "seat frame"},
        "evidence",
    )

    assert {row["query_family"] for row in plan} == {
        "identite_specialite",
        "certification_qualite",
        "incident_operationnel",
        "fragilite_financiere",
        "capacite_resilience",
        "dependance_substitution",
        "exposition_climatique",
    }
    assert len({row["query_id"] for row in plan}) == len(plan)
    defaults = parse_args([])
    assert defaults.query_profile == "evidence"
    assert defaults.max_queries_per_site == 0
    assert defaults.max_results >= len(plan) * defaults.results_per_query


def test_keyword_boundaries_and_positive_context_remove_known_false_positives() -> None:
    for title in (
        "Acme Metals hardware and software",
        "Acme Metals office in Delaware",
        "Acme Metals moves towards aerospace",
        "Acme Metals fire protection barrier",
    ):
        scored = score_result(SITE, result(title), "incident_operationnel")
        assert scored["signal_categories"] == ""
        assert scored["weak_signal_score"] == 0.0
    positive_compliance = score_result(
        SITE,
        result("Acme Metals strict compliance with safety standards"),
        "certification_qualite",
    )
    assert positive_compliance["signal_categories"] == ""
    assert positive_compliance["weak_signal_score"] == 0.0


def test_actual_supplier_factory_fire_is_kept_as_unverified_serp_evidence() -> None:
    scored = score_result(
        SITE,
        result("Acme Metals plant shutdown after fire in Toulouse in 2024"),
        "incident_operationnel",
    )

    assert scored["signal_categories"] == "incident_industriel"
    assert scored["identity_match_score"] >= 0.45
    assert scored["publication_date_hint"] == "2024"
    assert scored["verification_status"] != "identite_non_confirmee"
    assert "capacite" in scored["potential_sdd_effects"]


def test_irrelevant_company_signal_is_rejected_by_identity_gate() -> None:
    scored = score_result(
        SITE,
        result("Other Company plant shutdown after fire", domain="other-company.com"),
        "incident_operationnel",
    )

    assert scored["identity_match_score"] < 0.35
    assert scored["signal_categories"] == ""
    assert scored["verification_status"] == "identite_non_confirmee"


def test_place_name_and_competitor_mentions_do_not_become_supplier_events() -> None:
    alcoa = {**SITE, "name": "Alcoa", "location": "United States"}
    highway = score_result(
        alcoa,
        result(
            "Alcoa Highway was shutdown after a crash involving four vehicles",
            domain="wate.com",
        ),
        "incident_operationnel",
    )
    amag = {**SITE, "name": "AMAG Austria Metall", "location": "Austria"}
    competitor = score_result(
        amag,
        result(
            "Competitor annual filing",
            "Main competitors are AMAG Austria Metall and Trimet. Bankruptcy Court entered an order for the issuer.",
            domain="sec.gov",
        ),
        "fragilite_financiere",
    )

    assert highway["signal_categories"] == ""
    assert competitor["signal_categories"] == ""


def test_positive_evidence_requires_supplier_and_claim_in_same_segment() -> None:
    scored = score_result(
        SITE,
        result(
            "Aerospace supplier overview",
            "Acme Metals supplies seat frames. OtherCorp announced a new plant and capacity expansion.",
            domain="trade-press.example",
        ),
        "capacite_resilience",
    )

    assert scored["positive_signal_categories"] == ""
    assert scored["resilience_evidence_score"] == 0.0


def test_rejected_categories_do_not_inflate_accepted_incident_score() -> None:
    scored = score_result(
        SITE,
        result("Acme Metals plant shutdown after fire; unrelated bankruptcy market report"),
        "incident_operationnel",
    )

    assert scored["signal_categories"] == "incident_industriel"
    assert scored["weak_signal_score"] < 0.2


def test_url_canonicalization_removes_tracking_and_fragment() -> None:
    assert canonicalize_url("http://Example.com/page?utm_source=x&id=2#section") == "https://example.com/page?id=2"


def test_unknown_evidence_does_not_increase_documentary_risk() -> None:
    scored = score_result(
        SITE,
        result("Unrelated market outlook", domain="example.com"),
        "fragilite_financiere",
    )
    summary = summarize_site(
        SITE,
        "query",
        "test",
        "ok",
        "2026-07-24T00:00:00+00:00",
        [scored],
        max_mass=12,
        max_path_count=3,
    )

    assert summary["documentary_criticality_score"] == 0.0
    assert summary["observed_fragility_score"] == 0.0


def test_evidence_rows_remain_candidates_until_source_page_validation() -> None:
    scored = score_result(
        SITE,
        result("Acme Metals plant shutdown after fire in Toulouse in 2024"),
        "incident_operationnel",
    )
    row = {
        **SITE,
        "supplier": SITE["name"],
        "query_family": "incident_operationnel",
        "retrieved_at_utc": "2026-07-24T00:00:00+00:00",
        **scored,
    }
    evidence = build_evidence_rows([row])

    assert len(evidence) == 1
    assert evidence[0]["evidence_category"] == "incident_industriel"
    assert evidence[0]["verification_status"] in {"indice_serp_a_confirmer", "indice_fort_a_verifier"}
