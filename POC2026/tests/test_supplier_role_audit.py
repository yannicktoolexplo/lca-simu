from copy import deepcopy

import pytest

from POC2026.supply_geo_case.supplier_role_audit import build_supplier_role_audit


def _site(uid="a@48,2", supplier_ids="A|B", roles="T2|T3", name="Example SA"):
    return {"site_uid": uid, "supplier_ids": supplier_ids, "roles": roles,
            "name": name, "lat": 48, "lon": 2}


def test_all_103_nodes_are_covered_without_automatic_reclassification():
    sites = [_site(uid=f"site-{i}@48,2", supplier_ids=f"S{i}") for i in range(103)]
    result = build_supplier_role_audit(sites, [], [], [])
    assert result["summary"]["site_count"] == result["summary"]["row_count"] == 103
    assert result["summary"]["status_counts"] == {"a_documenter": 103}
    assert [row["site_uid"] for row in result["rows"]] == [site["site_uid"] for site in sites]
    assert all(row["roles_model"] == "T2|T3" for row in result["rows"])
    assert all(row["multiple_roles"] for row in result["rows"])
    assert "pas des liens commerciaux prouves" in result["summary"]["model_scope"]


def test_decisions_propagate_by_exact_ids_not_name_or_substring():
    sites = [_site(), _site("b@48,2", "A"), _site("c@48,2", "AA")]
    decisions = [{"supplier_id": "A", "role_assessment": "review_role", "proposed_role": "T1"},
                 {"site_uid": "c@48,2", "role_assessment": "review_identity"},
                 {"supplier_id": "Example", "role_assessment": "coherent_function"},
                 {"site_uid": "c@48,2", "supplier_id": "A", "role_assessment": "review_role"},
                 {"role_assessment": "assumption_only"}]
    result = build_supplier_role_audit(sites, [], [], decisions)
    assert [row["decision_count"] for row in result["rows"]] == [1, 1, 1]
    assert [row["status"] for row in result["rows"]] == ["review_role", "review_role", "review_identity"]
    assert result["rows"][0]["roles_model"] == "T2|T3"
    assert result["rows"][0]["proposed_role"] == "T1"
    assert result["rows"][2]["identity_ambiguous"] is True
    assert result["summary"]["unmatched_decision_indexes"] == [2, 3, 4]


@pytest.mark.parametrize("name,nature", [
    ("Acme INTERNAL", "synthetic_process"), ("Acme process", "synthetic_process"),
    ("Acme package", "synthetic_process"), ("Acme assumption", "assumption"),
    ("Acme candidate process", "assumption"), ("market basket", "assumption"),
    ("Example SA", "identified_organization"),
    ("Safran Seats / Safran internal group", "identified_organization"),
    ("Ensinger - material intermediate sourcing", "synthetic_process"),
])
def test_nature_is_only_a_name_heuristic(name, nature):
    row = build_supplier_role_audit([_site(name=name)], [], [], [])["rows"][0]
    assert row["nature"] == nature
    assert row["synthetic_node"] == (nature != "identified_organization")
    assert row["status"] == "a_documenter"
    assert row["inferred_upstream"] is False


def test_primary_paths_are_counted_once_per_site_and_families_are_exact():
    paths = [
        {"path_id": "P1", "path_type": "primary", "family": "metal",
         "t4_site_uid": "a@48,2", "t3_site_uid": "a@48,2", "t3_status": "baseline_assumed"},
        {"path_id": "P1", "path_type": "primary", "family": "metal", "t2_site_uid": "a@48,2"},
        {"path_id": "P2", "path_type": "primary", "family": "foam", "t1_site_uid": "a@48,2"},
        {"path_id": "P3", "path_type": "alternative", "family": "excluded", "t4_site_uid": "a@48,2"},
        {"path_id": "P4", "path_type": "primary", "family": "excluded", "t4_site_uid": "aa@48,2"},
    ]
    row = build_supplier_role_audit([_site()], paths, [], [])["rows"][0]
    # Manual oracle: only P1 and P2 touch this exact UID in primary paths.
    assert row["primary_path_count"] == 2
    assert row["families"] == ["foam", "metal"]
    assert row["inferred_upstream"] is True


@pytest.mark.parametrize("uid,lat,lon,expected", [
    ("prefix@@site@48,2", 48.1, 2.1, False),
    ("site@48,2", 48.10001, 2, True),
    ("site@48,2", 48, 2.10001, True),
    ("site@48,2", "nan", 2, None),
    ("site", 48, 2, None), ("site@91,2", 48, 2, None),
])
def test_coordinate_uid_tolerance_and_unknowns(uid, lat, lon, expected):
    site = {**_site(uid), "lat": lat, "lon": lon}
    assert build_supplier_role_audit([site], [], [], [])["rows"][0]["coordinates_uid_disagree"] is expected


def test_context_counts_remain_declarations_not_role_evidence():
    contexts = [
        {"site_uid": "a@48,2", "source_count": "3", "verified_evidence_count": "2",
         "top_url": "https://example.test/context"},
        {"site_uid": "aa@48,2", "source_count": 100, "verified_evidence_count": 99},
    ]
    row = build_supplier_role_audit([_site()], [], contexts, [])["rows"][0]
    assert row["context_source_count"] == 3
    assert row["context_verified_count"] == 2
    assert row["context_urls"] == ["https://example.test/context"]
    assert row["status"] == "a_documenter"
    assert row["documented_activity"] == ""
    assert "sans validation de preuve" in row["context_scope"]


def test_multiple_decisions_are_retained_and_inputs_and_outputs_are_detached():
    decisions = [
        {"supplier_id": "B", "documented_activity": "Machining", "role_assessment": "coherent_function",
         "proposed_role": "T2", "confidence": "low", "rationale": "To verify",
         "source_urls": ["https://example.test/activity"], "source_scope": "organization only",
         "identity_ambiguous": "false"},
        {"site_uid": "a@48,2", "role_assessment": "review_identity", "identity_ambiguous": True},
    ]
    inputs = ([_site()], [], [], decisions)
    before = deepcopy(inputs)
    result = build_supplier_role_audit(*inputs)
    assert inputs == before
    row = result["rows"][0]
    assert row["status"] == "multiple_decisions"
    assert row["decision_count"] == 2
    assert row["proposed_role"] == ""
    assert row["identity_ambiguous"] is True
    assert row["decisions"][0]["role_assessment_label"] == "Fonction modelisee coherente"
    row["decisions"][0]["source_urls"].append("extra")
    assert inputs == before


def test_empty_inputs_and_explicit_identity_flag():
    assert build_supplier_role_audit([], [], [], [])["rows"] == []
    decision = {"supplier_id": "A", "role_assessment": "assumption_only", "identity_ambiguous": "false"}
    row = build_supplier_role_audit([_site()], [], [], [decision])["rows"][0]
    assert row["identity_ambiguous"] is False
    assert row["role_assessment_label"] == "Hypothese uniquement"


def test_node_geometry_collision_counts_occurrences_not_distinct_paths():
    nodes = [
        {"site_uid": "mitsubishi@35,139", "lat": 51, "lon": 3, "country_code": "BE",
         "location": "Tielt", "path_id": f"BE{i}"} for i in range(7)
    ] + [
        {"site_uid": "mitsubishi@35,139", "lat": 35, "lon": 139, "country_code": "JP",
         "location": "Japan", "path_id": f"JP{i // 2}"} for i in range(17)
    ]
    before = deepcopy(nodes)
    site = {**_site("mitsubishi@35,139"), "lat": 51, "lon": 3}
    row = build_supplier_role_audit([site], [], [], [], node_rows=nodes)["rows"][0]
    assert row["node_geometry_collision"] is True
    assert row["node_occurrence_count"] == 24
    assert row["node_distinct_path_count"] == 16
    assert [group["occurrence_count"] for group in row["node_geometry_groups"]] == [7, 17]
    assert nodes == before
    row["node_geometry_groups"][0]["path_ids"].append("extra")
    assert nodes == before


def test_old_uid_disagreement_is_not_a_current_geometry_collision():
    site = {**_site("toray@35,139"), "lat": 48, "lon": 2}
    nodes = [{"site_uid": site["site_uid"], "lat": 48, "lon": 2, "path_id": "P1"}]
    row = build_supplier_role_audit([site], [], [], [], nodes)["rows"][0]
    assert row["coordinates_uid_disagree"] is True
    assert row["node_geometry_collision"] is False
    assert "ne prouve pas" in row["coordinates_uid_scope"]
    nodes.append({"site_uid": site["site_uid"], "lat": 33, "lon": 132, "path_id": "P2"})
    assert build_supplier_role_audit([site], [], [], [], nodes)["rows"][0]["node_geometry_collision"] is True
    assert build_supplier_role_audit([site], [], [], [])["rows"][0]["node_geometry_collision"] is None


def test_french_labels_and_source_urls_always_list():
    decisions = [
        {"supplier_id": "A", "role_assessment": "review_role", "source_urls": "https://example.test/a"},
        {"supplier_id": "B", "role_assessment": "review_identity", "source_urls": ["https://example.test/b"]},
    ]
    row = build_supplier_role_audit([_site()], [], [], decisions)["rows"][0]
    assert row["status_label"] == "Plusieurs decisions a examiner"
    assert row["nature_label"] == "Organisation nommee (identite non validee)"
    assert row["source_urls"] == ["https://example.test/a", "https://example.test/b"]
    assert row["decisions"][0]["source_urls"] == ["https://example.test/a"]
