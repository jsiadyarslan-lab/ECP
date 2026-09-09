"""Explicit version-compatibility tests (0.3.0 → 0.4.0 → 0.5.0 → 0.6.0 additive bundle).

0.1.x, 0.2.x, 0.3.x, 0.4.x and 0.5.x artifacts are NOT silently reinterpreted
and NOT invalidated: the matrix in ecp.versions is the single normative
statement of what cites what. Provenance identity checks (protocol version,
schema version, object identity) are covered here for every object type,
including the four M3-CA0 review-layer contracts introduced at 0.3.0, the
M3-CA0-A case-amendment contract introduced at 0.4.0, the two M3-CA0 v1
authoring-layer contracts introduced at 0.5.0, and the four M3-CA1 v1
registration-readiness contracts introduced at 0.6.0.
"""

import pytest

from ecp.versions import (
    PROTOCOL_VERSIONS,
    SCHEMA_VERSIONS,
    V010_CONTRACTS,
    V020_CONTRACTS,
    V030_CONTRACTS,
    V040_CONTRACTS,
    V050_CONTRACTS,
    V060_CONTRACTS,
    allowed_schema_versions,
    version_issues,
)


def test_matrix_covers_all_known_object_types():
    assert set(SCHEMA_VERSIONS) == (
        set(V010_CONTRACTS)
        | set(V020_CONTRACTS)
        | set(V030_CONTRACTS)
        | set(V040_CONTRACTS)
        | set(V050_CONTRACTS)
        | set(V060_CONTRACTS)
    )
    assert len(SCHEMA_VERSIONS) == 23


def test_v010_contracts_accept_all_bundle_versions():
    for name in V010_CONTRACTS:
        assert allowed_schema_versions(name) == (
            "0.1.0",
            "0.2.0",
            "0.3.0",
            "0.4.0",
            "0.5.0",
            "0.6.0",
        ), name


def test_v020_contracts_accept_020_through_060():
    for name in V020_CONTRACTS:
        assert allowed_schema_versions(name) == (
            "0.2.0",
            "0.3.0",
            "0.4.0",
            "0.5.0",
            "0.6.0",
        ), name


def test_v030_contracts_accept_030_through_060():
    for name in V030_CONTRACTS:
        assert allowed_schema_versions(name) == ("0.3.0", "0.4.0", "0.5.0", "0.6.0"), name


def test_v040_contracts_accept_040_through_060():
    for name in V040_CONTRACTS:
        assert allowed_schema_versions(name) == ("0.4.0", "0.5.0", "0.6.0"), name


def test_v050_contracts_accept_050_and_060():
    for name in V050_CONTRACTS:
        assert allowed_schema_versions(name) == ("0.5.0", "0.6.0"), name


def test_v060_contracts_accept_only_060():
    for name in V060_CONTRACTS:
        assert allowed_schema_versions(name) == ("0.6.0",), name


def test_unknown_object_type_falls_back_to_union():
    assert allowed_schema_versions("not-a-type") == PROTOCOL_VERSIONS


def test_protocol_axis_accepts_010_through_060():
    assert PROTOCOL_VERSIONS == ("0.1.0", "0.2.0", "0.3.0", "0.4.0", "0.5.0", "0.6.0")


def test_version_issues_accepts_010_citations():
    document = {
        "ecp_object": "case",
        "protocol_version": "0.1.0",
        "schema_version": "0.1.0",
    }
    assert version_issues(document) == []


def test_version_issues_accepts_020_citations_on_unchanged_contracts():
    document = {
        "ecp_object": "case",
        "protocol_version": "0.2.0",
        "schema_version": "0.2.0",
    }
    assert version_issues(document) == []


def test_version_issues_accepts_030_citations_on_unchanged_contracts():
    document = {
        "ecp_object": "case",
        "protocol_version": "0.3.0",
        "schema_version": "0.3.0",
    }
    assert version_issues(document) == []


def test_version_issues_accepts_030_review_contracts():
    document = {
        "ecp_object": "case-review",
        "protocol_version": "0.3.0",
        "schema_version": "0.3.0",
    }
    assert version_issues(document) == []


def test_version_issues_accepts_040_citations_on_unchanged_contracts():
    document = {
        "ecp_object": "case",
        "protocol_version": "0.4.0",
        "schema_version": "0.4.0",
    }
    assert version_issues(document) == []


def test_version_issues_accepts_040_amendment_contract():
    document = {
        "ecp_object": "case-amendment",
        "protocol_version": "0.4.0",
        "schema_version": "0.4.0",
    }
    assert version_issues(document) == []


def test_version_issues_accepts_050_citations_on_unchanged_contracts():
    document = {
        "ecp_object": "case",
        "protocol_version": "0.5.0",
        "schema_version": "0.5.0",
    }
    assert version_issues(document) == []


def test_version_issues_accepts_050_candidate_and_qualification_contracts():
    for object_type in ("case-candidate", "case-qualification", "qualification-run"):
        document = {
            "ecp_object": object_type,
            "protocol_version": "0.5.0",
            "schema_version": "0.5.0",
        }
        assert version_issues(document) == [], object_type


def test_version_issues_rejects_010_citation_on_new_contract():
    document = {
        "ecp_object": "ledger-entry",
        "protocol_version": "0.1.0",
        "schema_version": "0.1.0",
    }
    issues = version_issues(document)
    assert any("schema_version" in issue for issue in issues)


def test_version_issues_rejects_020_citation_on_review_contract():
    document = {
        "ecp_object": "case-candidate",
        "protocol_version": "0.2.0",
        "schema_version": "0.2.0",
    }
    issues = version_issues(document)
    assert any("schema_version" in issue for issue in issues)


def test_version_issues_rejects_future_schema_version():
    document = {
        "ecp_object": "case",
        "protocol_version": "0.4.0",
        "schema_version": "9.9.9",
    }
    issues = version_issues(document)
    assert any("schema_version" in issue for issue in issues)


def test_version_issues_rejects_030_citation_on_amendment_contract():
    document = {
        "ecp_object": "case-amendment",
        "protocol_version": "0.3.0",
        "schema_version": "0.3.0",
    }
    issues = version_issues(document)
    assert any("schema_version" in issue for issue in issues)


def test_version_issues_rejects_future_protocol_version():
    document = {"ecp_object": "case", "protocol_version": "0.7.0"}
    issues = version_issues(document)
    assert any("protocol_version" in issue for issue in issues)


def test_version_issues_rejects_040_citation_on_qualification_contracts():
    document = {
        "ecp_object": "case-qualification",
        "protocol_version": "0.4.0",
        "schema_version": "0.4.0",
    }
    issues = version_issues(document)
    assert any("schema_version" in issue for issue in issues)


def test_version_issues_accepts_060_citations_on_unchanged_contracts():
    document = {
        "ecp_object": "case",
        "protocol_version": "0.6.0",
        "schema_version": "0.6.0",
    }
    assert version_issues(document) == []


def test_version_issues_accepts_060_readiness_contracts():
    for object_type in (
        "case-readiness",
        "readiness-run",
        "owner-decision-register",
        "registration-manifest",
    ):
        document = {
            "ecp_object": object_type,
            "protocol_version": "0.6.0",
            "schema_version": "0.6.0",
        }
        assert version_issues(document) == [], object_type


def test_version_issues_rejects_050_citation_on_readiness_contracts():
    document = {
        "ecp_object": "case-readiness",
        "protocol_version": "0.5.0",
        "schema_version": "0.5.0",
    }
    issues = version_issues(document)
    assert any("schema_version" in issue for issue in issues)


def test_version_issues_requires_protocol_version():
    issues = version_issues({"ecp_object": "case"})
    assert any("missing protocol_version" in issue for issue in issues)


def test_version_issues_rejects_non_dict():
    assert version_issues([1, 2, 3]) != []
