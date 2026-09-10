"""Shared fixtures for the M3-CA0 case review tests.

All candidate material here is SYNTHETIC test data (invented, abstract
entities) — none of it is real candidate material, and none of it derives
from the delivered M3-CA0 candidate set. The synthetic documents follow
the M3-CA0-case-set-md-1 format so the real parser/extraction/engine
paths are exercised end-to-end.
"""

import copy

from ecp.candidates import extract_candidates
from ecp.hashing import hash_document

SYNTHETIC_CASE_TEMPLATE = """CASE ID: {case_id}

PROPOSED_REASONING_FAMILY: {family}
STRUCTURAL_SIGNATURE: {signature}
PREMISES:
{premises}

QUESTION:

{question}

INTENDED_CORRECT_ANSWER:

{answer}

DERIVATION:
{derivation}

DIFFICULTY:

{difficulty}

RETRIEVAL_RISK:

{retrieval_risk}

AMBIGUITY_RISK:

Low. Synthetic test fixture; abstract entities only.

STRUCTURAL_UNIQUENESS_RATIONALE:

{rationale}

SELF_REVIEW:
- Derivable: {derivable}
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes

---
"""

CASE_A = {
    "case_id": "S-001",
    "family": "Synthetic Categorical Logic",
    "signature": "synthetic two-premise exclusion chain",
    "premises": "1. All Zibs are Zobs.\n2. No Zob is a Zump.",
    "question": "If a Zib is selected, what can be concluded about its relationship to Zumps?",
    "answer": "It is not a Zump.",
    "derivation": "1. A Zib is a Zob by premise one.\n2. No Zob is a Zump by premise two.\n3. Therefore a Zib is not a Zump.",
    "difficulty": "SHALLOW",
    "retrieval_risk": "Synthetic fixture with invented abstract entities.",
    "rationale": "Synthetic fixture rationale: simple exclusion chain.",
    "derivable": "Yes",
}

CASE_B = {
    "case_id": "S-002",
    "family": "Synthetic Conditional Flow",
    "signature": "synthetic conditional activation chain",
    "premises": "1. If a Widget is engaged, it emits a pulse.\n2. Widget W7 is engaged.",
    "question": "Does Widget W7 emit a pulse?",
    "answer": "Yes, Widget W7 emits a pulse.",
    "derivation": "1. Widget W7 is engaged by premise two.\n2. Engaged widgets emit pulses by premise one.\n3. Therefore Widget W7 emits a pulse.",
    "difficulty": "SHALLOW",
    "retrieval_risk": "Synthetic fixture with invented abstract entities.",
    "rationale": "Synthetic fixture rationale: single conditional application.",
    "derivable": "Yes",
}

FULL_AUTHORING = {
    "case_version": "1.0.0",
    "constraints": ["premises-only reasoning", "no external lookup"],
    "success_criterion": "The evaluated system states the correct conclusion.",
    "verification_rule": {
        "rule_id": "SYN-EXACT-1",
        "rule_type": "exact-match",
        "description": "Synthetic fixture rule: exact answer match.",
        "binding": "public",
    },
    "required_artifacts": ["raw-output"],
}


def build_source_text(cases: "list[dict]") -> str:
    """Assemble a synthetic M3-CA0 case-set document from case dicts."""
    body = "".join(
        SYNTHETIC_CASE_TEMPLATE.format(
            case_id=case["case_id"],
            family=case["family"],
            signature=case["signature"],
            premises=case["premises"],
            question=case["question"],
            answer=case.get("answer", ""),
            derivation=case.get("derivation", ""),
            difficulty=case.get("difficulty", "SHALLOW"),
            retrieval_risk=case.get("retrieval_risk", "Synthetic fixture."),
            rationale=case.get("rationale", "Synthetic fixture rationale."),
            derivable=case.get("derivable", "Yes"),
        )
        for case in cases
    )
    tail = (
        "AUTHORING PROVENANCE\n\nNOT AVAILABLE\n\n---\n\n"
        "CASE SET SUMMARY\n\n"
        f"Candidate cases: {len(cases)}\n"
    )
    return "```text\n" + body + tail + "```\n"


def build_sidecar(source_sha256: str, **overrides) -> dict:
    """A COMPLETE, flag-free provenance sidecar for synthetic sources."""
    sidecar = {
        "authored_by": {"model": "synthetic-test-author", "provider": "test-fixture"},
        "authored_at": "2026-01-01T00:00:00Z",
        "information_boundary": "isolated",
        "acquisition": {
            "label": "synthetic-test-source.md",
            "sha256": source_sha256,
            "acquired_at": "2026-01-02T00:00:00Z",
        },
        "transformation_history": [
            {
                "event": "synthetic generation",
                "at": "2026-01-01T00:00:00Z",
                "evidence": "test fixture",
            },
            {
                "event": "synthetic delivery",
                "at": "2026-01-02T00:00:00Z",
                "evidence": "test fixture",
            },
        ],
        "originating_artifacts": [
            {"name": "synthetic-prompt", "label": "test fixture"}
        ],
        "provenance_completeness": {"status": "COMPLETE", "not_available": []},
    }
    sidecar.update(overrides)
    return sidecar


def extract_fixture(cases: "list[dict]", sidecar_overrides: "dict | None" = None) -> "tuple[list[dict], dict, str]":
    """Extract candidates from a synthetic source (tmp_path-backed).

    Returns (candidates, source_report, source_text).
    """
    import tempfile
    from pathlib import Path

    from ecp.hashing import sha256_hex

    source_text = build_source_text(cases)
    with tempfile.TemporaryDirectory() as tmp:
        source_path = Path(tmp) / "synthetic-test-source.md"
        source_path.write_text(source_text, encoding="utf-8")
        sidecar = build_sidecar(sha256_hex(source_text.encode("utf-8")))
        if sidecar_overrides:
            sidecar.update(sidecar_overrides)
        candidates, report = extract_candidates(source_path, sidecar)
    return candidates, report, source_text


def with_full_authoring(candidate: dict) -> dict:
    """Deep copy with the full registration authoring block attached."""
    doc = copy.deepcopy(candidate)
    doc["registration_authoring"] = copy.deepcopy(FULL_AUTHORING)
    return doc


def with_content(candidate: dict, **changes) -> dict:
    """Deep copy with content fields changed and the content hash recomputed.

    Convenience conversions: a ``premises`` string is split into numbered
    premise items; a ``derivation`` string becomes a single derivation block.
    """
    doc = copy.deepcopy(candidate)
    content = doc["content"]
    for key, value in changes.items():
        if key == "answer":
            content["intended_correct_answers"] = [
                {"value": value, "source_block": block["source_block"]}
                for block in content["intended_correct_answers"]
            ]
        elif key == "extra_answer":
            content["intended_correct_answers"].append(
                {"value": value, "source_block": len(content["intended_correct_answers"]) + 1}
            )
        elif key == "premises" and isinstance(value, str):
            content["premises"] = [
                line.split(". ", 1)[1]
                for line in value.split("\n")
                if line.strip()
            ]
        elif key == "derivation" and isinstance(value, str):
            content["derivations"] = [{"raw": value, "source_block": 1}]
        else:
            content[key] = value
    doc["content_hash"] = hash_document(content)
    return doc


STANDARD_RUN = {
    "run_id": "ECP-REVRUN-TEST",
    "reviewed_at": "2026-01-03T00:00:00Z",
    "operator": "ECP Review Test Executor",
}


def build_adjudication(
    adjudication_id: str,
    question_code: str,
    disposition: str,
    candidate_id: "str | None" = None,
    at: str = "2026-01-02T12:00:00Z",
    rationale: str = "test fixture owner decision",
) -> dict:
    from ecp.hashing import hash_document_excluding

    adjudication = {
        "ecp_object": "review-adjudication",
        "adjudication_id": adjudication_id,
        "owner_identity": "ECP-OWNER-TEST",
        "recorded_by_operator": "ECP Review Test Executor",
        "at": at,
        "applies_to": {"question_code": question_code},
        "disposition": disposition,
        "rationale": rationale,
        "protocol_version": "0.3.0",
        "schema_version": "0.3.0",
    }
    if candidate_id:
        adjudication["applies_to"]["candidate_id"] = candidate_id
    adjudication["adjudication_hash"] = hash_document_excluding(
        adjudication, "adjudication_hash"
    )
    return adjudication


RESOLVE_ALL = [
    build_adjudication("ECP-ADJ-000001", "OQ-NOV-EXTERNAL", "RESOLVE-CLEAN"),
    build_adjudication("ECP-ADJ-000002", "OQ-LKG-CONTAMINATION", "RESOLVE-CLEAN"),
    build_adjudication("ECP-ADJ-000003", "OQ-LKG-SOURCE-CONTAMINATION", "ACCEPT-RISK"),
    build_adjudication("ECP-ADJ-000004", "OQ-PROV-PARTIAL", "RESOLVE-CLEAN"),
]
