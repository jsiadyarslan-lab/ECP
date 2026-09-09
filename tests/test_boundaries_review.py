"""Review-area boundary tests (M3-CA0 §13) and public-repository review rules."""

import json

import pytest

from ca0_fixtures import CASE_A, RESOLVE_ALL, STANDARD_RUN, extract_fixture, with_full_authoring

from ecp.boundaries import scan_repository, scan_review_tree
from ecp.review import run_review


@pytest.fixture()
def review_root(tmp_path):
    """A fully populated, valid review area."""
    root = tmp_path / "review-area"
    candidates, _, source_text = extract_fixture([CASE_A])
    candidate = with_full_authoring(candidates[0])
    result = run_review(
        [candidate],
        source_text=source_text,
        adjudications=RESOLVE_ALL[:2],
        **STANDARD_RUN,
    )
    (root / "candidates").mkdir(parents=True)
    (root / "reviews").mkdir(parents=True)
    (root / "source").mkdir(parents=True)
    (root / "adjudications").mkdir(parents=True)
    (root / "candidates" / "ECP-CAND-000001.json").write_text(
        json.dumps(candidate), encoding="utf-8"
    )
    (root / "source" / "source.md").write_text(source_text, encoding="utf-8")
    (root / "source" / "source-provenance.json").write_text(
        json.dumps({"authored_by": {"model": "synthetic", "provider": "test"}}),
        encoding="utf-8",
    )
    (root / "reviews" / "ECP-REVIEW-000001.json").write_text(
        json.dumps(result["artifacts"][0]), encoding="utf-8"
    )
    (root / "review-run.json").write_text(
        json.dumps(result["run"]), encoding="utf-8"
    )
    (root / "extraction-report.json").write_text(
        json.dumps({"coverage": "PASS"}), encoding="utf-8"
    )
    (root / "README.md").write_text("private review area\n", encoding="utf-8")
    return root


def test_clean_review_root_has_no_violations(review_root):
    assert scan_review_tree(review_root) == []


def test_missing_review_root_is_a_violation(tmp_path):
    violations = scan_review_tree(tmp_path / "does-not-exist")
    assert violations and violations[0]["rule"] == "review-root-missing"


def test_object_in_wrong_directory_is_flagged(review_root):
    # move the candidate artifact to the root (wrong location)
    misplaced = review_root / "ECP-CAND-000001.json"
    misplaced.write_text(
        (review_root / "candidates" / "ECP-CAND-000001.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    violations = scan_review_tree(review_root)
    assert any(v["rule"] == "review-object-wrong-location" for v in violations)


def test_foreign_ecp_object_is_flagged(review_root):
    foreign = review_root / "candidates" / "foreign.json"
    foreign.write_text(
        json.dumps({"ecp_object": "ledger-entry", "ledger_id": "X"}), encoding="utf-8"
    )
    violations = scan_review_tree(review_root)
    assert any(v["rule"] == "review-foreign-ecp-object" for v in violations)


def test_case_object_is_foreign_in_review_area(review_root):
    foreign = review_root / "reviews" / "case.json"
    foreign.write_text(json.dumps({"ecp_object": "case"}), encoding="utf-8")
    violations = scan_review_tree(review_root)
    assert any(v["rule"] == "review-foreign-ecp-object" for v in violations)


def test_fabricated_case_identity_is_flagged(review_root):
    readme = review_root / "README.md"
    readme.write_text("notes: a future ECP-CASE-000001 might exist\n", encoding="utf-8")
    violations = scan_review_tree(review_root)
    assert any(v["rule"] == "review-fabricated-identity" for v in violations)


def test_fabricated_registration_identity_is_flagged(review_root):
    notes = review_root / "extraction-report.json"
    notes.write_text(
        json.dumps({"note": "ECP-REG-000001 must not appear here"}),
        encoding="utf-8",
    )
    violations = scan_review_tree(review_root)
    assert any(v["rule"] == "review-fabricated-identity" for v in violations)


def test_unparseable_json_is_flagged(review_root):
    (review_root / "reviews" / "broken.json").write_text("{not json", encoding="utf-8")
    violations = scan_review_tree(review_root)
    assert any(v["rule"] == "review-invalid-json" for v in violations)


def test_unexpected_top_entry_is_flagged(review_root):
    (review_root / "mystery-dir").mkdir()
    violations = scan_review_tree(review_root)
    assert any(v["rule"] == "review-unexpected-top-entry" for v in violations)


def test_unexpected_ops_file_is_flagged(review_root):
    (review_root / "stray.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    violations = scan_review_tree(review_root)
    assert any(v["rule"] in ("review-unexpected-ops-file", "review-unexpected-top-entry") for v in violations)


def test_schema_invalid_object_is_flagged(review_root):
    bad = review_root / "candidates" / "ECP-CAND-000002.json"
    candidate = json.loads(
        (review_root / "candidates" / "ECP-CAND-000001.json").read_text(encoding="utf-8")
    )
    candidate["candidate_id"] = "ECP-CAND-000002"
    candidate.pop("raw_block")
    bad.write_text(json.dumps(candidate), encoding="utf-8")
    violations = scan_review_tree(review_root)
    assert any(v["rule"] == "review-object-schema-invalid" for v in violations)


# --- public repository rules (R6/R7) ------------------------------------------


def test_public_repo_rejects_review_objects_outside_examples(tmp_path):
    root = tmp_path
    (root / "cases").mkdir()
    (root / "evaluation").mkdir()
    (root / "evidence").mkdir()
    (root / "verification").mkdir()
    for directory in ("cases", "evaluation", "evidence", "verification"):
        (root / directory / "README.md").write_text("reserved\n", encoding="utf-8")
    (root / "candidate.json").write_text(
        json.dumps({"ecp_object": "case-candidate", "content_class": "review"}),
        encoding="utf-8",
    )
    violations = scan_repository(root)
    assert any(v["rule"] == "review-object-outside-examples" for v in violations)


def test_public_repo_examples_must_be_format_illustration(tmp_path):
    root = tmp_path
    (root / "cases").mkdir()
    (root / "evaluation").mkdir()
    (root / "evidence").mkdir()
    (root / "verification").mkdir()
    for directory in ("cases", "evaluation", "evidence", "verification"):
        (root / directory / "README.md").write_text("reserved\n", encoding="utf-8")
    (root / "examples").mkdir()
    (root / "examples" / "candidate.example.json").write_text(
        json.dumps({"ecp_object": "case-candidate", "content_class": "review"}),
        encoding="utf-8",
    )
    violations = scan_repository(root)
    assert any(v["rule"] == "example-review-object-not-illustration" for v in violations)
