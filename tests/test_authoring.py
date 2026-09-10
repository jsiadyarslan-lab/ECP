"""M3-CA0 v1 authoring-layer tests (format M3-CA0V1-case-set-md-2 intake).

Covers the format-2 parser (coverage accounting, fenced FORMAL capture,
sub-key disclosure blocks, premises/bullets/self-review parsing, loud
failures) and the candidate builder (schema-valid 0.5.0 documents, real
content hashes, §3 independence transcription, determinism).
"""

import json

import pytest

from qual_fixtures import (
    CASE_BLOCK_P1,
    CASE_BLOCK_T1,
    CASE_BLOCK_T1_RENAMED,
    build_sidecar_v2,
    build_source_text_v2,
)

from ecp.authoring import (
    ExtractionError,
    build_candidate_v2,
    extract_candidates_v2,
    parse_case_set_v2,
)
from ecp.hashing import hash_document, sha256_hex
from ecp.validate import validate_document


def test_parse_valid_document_coverage_pass():
    text = build_source_text_v2([CASE_BLOCK_T1, CASE_BLOCK_P1])
    parsed = parse_case_set_v2(text)
    assert parsed["coverage"]["status"] == "PASS"
    assert parsed["coverage"]["unaccounted_lines"] == []
    assert [c["case_id"] for c in parsed["cases"]] == ["T-001", "P-001"]
    assert parsed["coverage"]["header_lines"] == [1]


def test_parse_captures_formal_fence_json():
    parsed = parse_case_set_v2(build_source_text_v2([CASE_BLOCK_T1]))
    formal_block = parsed["cases"][0]["sections"]["FORMAL"][0]
    assert formal_block["fence_lang"] == "json"
    formal = json.loads(formal_block["fence"])
    assert formal["semantics"] == "relational-closure"
    assert formal["query"] == {"relation": "taller", "args": ["vex", "tor"]}


def test_parse_captures_disclosure_sub_blocks():
    parsed = parse_case_set_v2(build_source_text_v2([CASE_BLOCK_T1]))
    sections = parsed["cases"][0]["sections"]
    rb = sections["REPRESENTATION_BIAS_DISCLOSURE"][0]["sub"]
    assert rb["STATUS"] == "DISCLOSED"
    assert "EVIDENCE" in rb and "KNOWN_LIMITATION" in rb
    env = sections["ENVIRONMENTAL_PRE_CHECK"][0]["sub"]
    assert set(env) == {
        "KNOWLEDGE_SOURCES", "FIXTURES", "IMPLEMENTATION_ARTIFACTS",
        "MEMORY_PATHS", "MODEL_ACCESS_PATHS", "ANSWER_BEARING_ARTIFACTS",
    }


def test_parse_premises_bullets_and_self_review():
    parsed = parse_case_set_v2(build_source_text_v2([CASE_BLOCK_T1]))
    sections = parsed["cases"][0]["sections"]
    assert len(sections["PREMISES"][0]["text"].split("\n")) >= 4
    assert sections["FORBIDDEN_SHORTCUTS"][0]["text"].startswith("- ")
    assert "Derivable: Yes" in sections["SELF_REVIEW"][0]["text"]


def test_parse_unknown_label_recorded_as_anomaly():
    text = build_source_text_v2([CASE_BLOCK_T1]).replace(
        "DIFFICULTY: SHALLOW", "WEIRD_LABEL: X\nDIFFICULTY: SHALLOW"
    )
    parsed = parse_case_set_v2(text)
    assert parsed["coverage"]["status"] == "PASS"  # accounted, flagged, never dropped
    assert parsed["cases"][0]["unknown_labels"][0]["label"] == "WEIRD_LABEL"


def test_parse_unaccounted_line_fails_coverage():
    # a stray non-blank line between the case separator and the tail title
    # is genuinely unaccountable -> coverage FAIL (loud, never dropped)
    text = build_source_text_v2([CASE_BLOCK_T1]).replace(
        "AUTHORING PROVENANCE", "orphan line\nAUTHORING PROVENANCE"
    )
    parsed = parse_case_set_v2(text)
    assert parsed["coverage"]["status"] == "FAIL"


def test_parse_tail_blocks_retained():
    parsed = parse_case_set_v2(build_source_text_v2([CASE_BLOCK_T1]))
    tails = {t["title"]: t["text"] for t in parsed["tail_blocks"]}
    assert "AUTHORING PROVENANCE" in tails
    assert "synthetic fixture author" in tails["AUTHORING PROVENANCE"]


def test_extract_rejects_sidecar_hash_mismatch(tmp_path):
    source = tmp_path / "source.md"
    text = build_source_text_v2([CASE_BLOCK_T1])
    source.write_text(text, encoding="utf-8")
    sidecar = build_sidecar_v2("0" * 64)
    with pytest.raises(ExtractionError, match="does not match"):
        extract_candidates_v2(source, sidecar)


def test_extract_rejects_missing_independence_block(tmp_path):
    source = tmp_path / "source.md"
    text = build_source_text_v2([CASE_BLOCK_T1])
    source.write_text(text, encoding="utf-8")
    sidecar = build_sidecar_v2(sha256_hex(text.encode("utf-8")))
    del sidecar["authoring_independence"]
    with pytest.raises(ExtractionError, match="authoring_independence"):
        extract_candidates_v2(source, sidecar)


def test_extract_produces_schema_valid_candidates(tmp_path):
    source = tmp_path / "source.md"
    text = build_source_text_v2([CASE_BLOCK_T1, CASE_BLOCK_P1])
    source.write_text(text, encoding="utf-8")
    sidecar = build_sidecar_v2(sha256_hex(text.encode("utf-8")))
    candidates, report = extract_candidates_v2(source, sidecar)
    assert len(candidates) == 2
    assert report["coverage"]["status"] == "PASS"
    assert report["source"]["format"] == "M3-CA0V1-case-set-md-2"
    for candidate in candidates:
        assert validate_document(candidate, "case-candidate") == []
        assert candidate["protocol_version"] == "0.5.0"
        assert candidate["schema_version"] == "0.5.0"
        # §3 independence record transcribed verbatim
        assert candidate["authoring_independence"]["independence_status"]["label"].startswith(
            "NOT-INDEPENDENT"
        )
        # §9/§10 blocks present and separate
        assert candidate["representation_bias_disclosure"]["status"] == "DISCLOSED"
        assert "knowledge_sources" in candidate["environmental_pre_check"]
    assert candidates[0]["candidate_id"] == "ECP-CAND-000101"
    assert candidates[1]["candidate_id"] == "ECP-CAND-000102"


def test_extract_is_deterministic(tmp_path):
    source = tmp_path / "source.md"
    text = build_source_text_v2([CASE_BLOCK_T1, CASE_BLOCK_P1])
    source.write_text(text, encoding="utf-8")
    sidecar = build_sidecar_v2(sha256_hex(text.encode("utf-8")))
    first, _ = extract_candidates_v2(source, sidecar)
    second, _ = extract_candidates_v2(source, sidecar)
    assert first == second


def test_extract_flags_renamed_duplicate_as_distinct_intake(tmp_path):
    """Renaming entities produces a distinct intake record (byte-distinct),
    but the QUALIFICATION engine's skeleton check is what flags it as a
    structural duplicate — the intake layer never adjudicates novelty."""
    source = tmp_path / "source.md"
    text = build_source_text_v2([CASE_BLOCK_T1, CASE_BLOCK_T1_RENAMED])
    source.write_text(text, encoding="utf-8")
    sidecar = build_sidecar_v2(sha256_hex(text.encode("utf-8")))
    candidates, report = extract_candidates_v2(source, sidecar)
    assert len(candidates) == 2
    assert candidates[0]["content_hash"] != candidates[1]["content_hash"]


def test_extract_loud_failure_on_malformed_formal_json(tmp_path):
    broken = CASE_BLOCK_T1.replace('"args": ["vex", "lum"]', '"args": ["vex", "lum"', 1)
    source = tmp_path / "source.md"
    text = build_source_text_v2([broken])
    source.write_text(text, encoding="utf-8")
    sidecar = build_sidecar_v2(sha256_hex(text.encode("utf-8")))
    with pytest.raises(ExtractionError, match="FORMAL"):
        extract_candidates_v2(source, sidecar)


def test_build_candidate_content_hash_is_real():
    parsed = parse_case_set_v2(build_source_text_v2([CASE_BLOCK_T1]))
    sidecar = build_sidecar_v2("0" * 64)
    provenance = dict(sidecar)
    provenance.pop("authoring_independence", None)
    candidate, anomalies = build_candidate_v2(
        parsed["cases"][0],
        source_label="fixture",
        source_sha256="0" * 64,
        provenance=provenance,
        candidate_id="ECP-CAND-000101",
        authoring_independence=sidecar["authoring_independence"],
    )
    assert candidate["content_hash"] == hash_document(candidate["content"])
    # raw_block retention: candidate -> source chain byte-exact
    assert candidate["raw_block"] in build_source_text_v2([CASE_BLOCK_T1])
    assert anomalies == []
