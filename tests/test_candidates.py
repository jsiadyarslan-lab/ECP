"""Case-candidate extraction tests (M3-CA0 §0–§2 of the review layer).

Covers: faithful parsing, anomaly retention (multi-block answers/
derivations are NEVER silently reconciled), the coverage check (no
silently dropped content), sidecar provenance validation, deterministic
hashing, and schema validity of extracted candidates.
"""

import pytest

from ca0_fixtures import CASE_A, CASE_B, build_source_text, extract_fixture

from ecp.candidates import (
    ExtractionError,
    extract_candidates,
    normalize_text,
    parse_case_set,
)
from ecp.hashing import hash_document, sha256_hex
from ecp.validate import validate_document


def test_parse_two_synthetic_cases():
    parsed = parse_case_set(build_source_text([CASE_A, CASE_B]))
    assert [c["case_id"] for c in parsed["cases"]] == ["S-001", "S-002"]
    assert parsed["coverage"]["status"] == "PASS"
    assert [t["title"] for t in parsed["tail_blocks"]] == [
        "AUTHORING PROVENANCE",
        "CASE SET SUMMARY",
    ]


def test_extract_candidates_deterministic_hashing():
    candidates_a, _, _ = extract_fixture([CASE_A, CASE_B])
    candidates_b, _, _ = extract_fixture([CASE_A, CASE_B])
    assert candidates_a == candidates_b
    for doc in candidates_a:
        # §11.12: deterministic hashing — recomputation equals the recorded hash
        assert doc["content_hash"] == hash_document(doc["content"])


def test_extracted_candidates_schema_valid():
    candidates, _, _ = extract_fixture([CASE_A, CASE_B])
    for doc in candidates:
        assert validate_document(doc, "case-candidate") == []
    assert candidates[0]["candidate_id"] == "ECP-CAND-000001"
    assert candidates[1]["candidate_id"] == "ECP-CAND-000002"


def test_extraction_preserves_multi_block_anomalies():
    # a case with TWO conflicting answer blocks and two derivations
    dual = dict(CASE_A)
    dual["answer"] = "It is not a Zump."
    dual_source = build_source_text([CASE_A])
    # craft the raw text by hand: append a second, conflicting answer block
    text = build_source_text([dual])
    marker = "DIFFICULTY:"
    extra = (
        "INTENDED_CORRECT_ANSWER:\n\nCannot be determined.\n\n"
        "DERIVATION:\n1. A second, conflicting derivation block.\n\n"
    )
    assert marker in text
    text = text.replace(marker, extra + marker, 1)
    parsed = parse_case_set(text)
    case = parsed["cases"][0]
    assert len(case["sections"]["INTENDED_CORRECT_ANSWER"]) == 2
    assert len(case["sections"]["DERIVATION"]) == 2
    assert parsed["coverage"]["status"] == "PASS"
    assert [b["text"] for b in case["sections"]["INTENDED_CORRECT_ANSWER"]] == [
        "It is not a Zump.",
        "Cannot be determined.",
    ]


def test_coverage_check_fails_on_unaccounted_content():
    # a stray line between the opening fence and the first case is not
    # attributable to any case, tail block or structural element
    text = build_source_text([CASE_A])
    text = text.replace("```text\n", "```text\nSTRAY UNACCOUNTED LINE\n", 1)
    parsed = parse_case_set(text)
    assert parsed["coverage"]["status"] == "FAIL"
    assert parsed["coverage"]["unaccounted_lines"]


def test_extraction_fails_loudly_on_coverage_failure(tmp_path):
    source = tmp_path / "bad-source.md"
    text = build_source_text([CASE_A]).replace("```text\n", "```text\nSTRAY LINE\n", 1)
    source.write_text(text, encoding="utf-8")
    from ca0_fixtures import build_sidecar

    sidecar = build_sidecar(sha256_hex(source.read_bytes()))
    with pytest.raises(ExtractionError, match="coverage"):
        extract_candidates(source, sidecar)


def test_extraction_fails_loudly_on_sidecar_hash_mismatch(tmp_path):
    source = tmp_path / "synthetic-test-source.md"
    source.write_text(build_source_text([CASE_A]), encoding="utf-8")
    from ca0_fixtures import build_sidecar

    sidecar = build_sidecar("0" * 64)
    with pytest.raises(ExtractionError, match="does not match"):
        extract_candidates(source, sidecar)


def test_extraction_fails_on_missing_sidecar_keys(tmp_path):
    source = tmp_path / "synthetic-test-source.md"
    source.write_text(build_source_text([CASE_A]), encoding="utf-8")
    with pytest.raises(ExtractionError, match="missing required key"):
        extract_candidates(source, {"authored_by": {"model": "x", "provider": "y"}})


def test_raw_block_retained_verbatim():
    candidates, _, source_text = extract_fixture([CASE_A])
    parsed = parse_case_set(source_text)
    assert candidates[0]["raw_block"] == parsed["cases"][0]["raw_block"]
    assert candidates[0]["raw_block"].startswith("CASE ID: S-001")


def test_candidate_flags_applied_per_case():
    from ca0_fixtures import build_sidecar

    source_text = build_source_text([CASE_A, CASE_B])
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        source_path = Path(tmp) / "synthetic-test-source.md"
        source_path.write_text(source_text, encoding="utf-8")
        sidecar = build_sidecar(sha256_hex(source_text.encode("utf-8")))
        sidecar["candidate_flags"] = {"S-002": ["nondeterminate-answer-design"]}
        candidates, _ = extract_candidates(source_path, sidecar)
    assert "candidate_flags" not in candidates[0]["provenance"]
    assert candidates[1]["provenance"]["candidate_flags"] == [
        "nondeterminate-answer-design"
    ]


def test_indented_premise_continuations():
    cont = dict(CASE_B)
    cont["premises"] = (
        "1. A registry lists exactly three widgets:\n"
        "    *   Widget A: engaged, pulse-emitting\n"
        "    *   Widget B: idle, silent\n"
        "2. Only engaged widgets emit pulses."
    )
    candidates, _, _ = extract_fixture([cont])
    premises = candidates[0]["content"]["premises"]
    assert len(premises) == 2
    assert "Widget A: engaged, pulse-emitting" in premises[0]
    assert "Widget C" not in premises[0]


def test_normalize_text_is_lossy_and_stable():
    assert normalize_text("  All   Zibs—are ZOBS!!  ") == "all zibs are zobs"
    assert normalize_text("No change") == normalize_text("no   CHANGE")


def test_self_review_negative_recorded():
    neg = dict(CASE_A)
    neg["derivable"] = "No"
    candidates, _, _ = extract_fixture([neg])
    assert candidates[0]["content"]["self_review"]["derivable"] == "No"
