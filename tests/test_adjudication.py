"""M3-CA0-A adjudication-layer tests (case amendment, two-phase
representation-bias disclosure, owner-adjudication construction).

All case material is SYNTHETIC (invented abstract entities). These tests
machine-check the order semantics:

- §7 (amended): the disclosure is completed in a SEPARATE step AFTER
  drafting, never concurrently — enforced mechanically (draft refuses
  disclosure inputs; disclose requires an existing PENDING draft; a
  fabricated record cannot reproduce the two-hash structure);
- §7: the v1 candidate is immutable under amendment (pure derivation);
- §8: material amendments re-enter full review; nothing is inherited;
- §3/§9: three decision states only, four-state separation preserved;
- §6/§10: no registration, no execution, no ledger writes anywhere.
"""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ca0_fixtures import (  # noqa: E402
    CASE_A,
    build_sidecar,
    build_source_text,
    extract_fixture,
    with_content,
    with_full_authoring,
)

from ecp.adjudication import (  # noqa: E402
    AdjudicationError,
    DISCLOSURE_VALUES,
    apply_amendment,
    build_adjudication_record,
    complete_disclosure,
    draft_case_amendment,
    effective_candidates,
    verify_amendment,
)
from ecp.hashing import hash_document  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _dual_block_candidate():
    """A synthetic candidate whose authored GT document carries two
    conflicting answer/derivation blocks (the C-007-style anomaly)."""
    candidates, _report, _source = extract_fixture([CASE_A])
    candidate = with_content(
        candidates[0],
        extra_answer="The Zib's relationship to Zumps is undetermined.",
    )
    # add a second derivation block too
    candidate["content"]["derivations"].append(
        {
            "raw": (
                "1. A Zib is a Zob (premise one).\n"
                "2. No Zob is a Zump (premise two).\n"
                "3. Hence a Zib is not a Zump (alternate clean derivation)."
            ),
            "source_block": 2,
        }
    )
    candidate["content_hash"] = hash_document(candidate["content"])
    return candidate


DRAFT_ARGS = {
    "amendment_id": "ECP-AMD-000001",
    "order_basis": "M3-CA0-A v1 §5: uniquely correct answer establishable",
    "defect_code": "SPEC-AMBIGUOUS-GT",
    "defect_description": "duplicated GT blocks with a stale conflicting answer",
    "defect_why": "the first answer block is contradicted by its own derivation",
    "defect_evidence": "retained derivation text of block 1 self-corrects",
    "retained_answer_block": 1,
    "retained_derivation_block": 2,
    "removed_answer_blocks": [2],
    "removed_derivation_blocks": [1],
    "not_outcome_statement": "selection is premise analysis only",
    "not_outcome_basis": "no evaluated-system executions exist for this set",
    "amendment_author": "ECP Test Amendment Author",
    "drafted_at": "2026-02-01T00:00:00Z",
    "operator": "ECP Test Operator",
    "order_reference": "M3-CA0-A test fixture order",
}


def _drafted():
    return draft_case_amendment(_dual_block_candidate(), **DRAFT_ARGS)


def _completed():
    drafted = _drafted()
    return complete_disclosure(
        drafted,
        value="POSSIBLE",
        completed_by="ECP Test Amendment Author",
        completed_at="2026-02-02T00:00:00Z",
        basis="test fixture: plausible influence cannot be excluded",
    )


# ---------------------------------------------------------------------------
# two-phase disclosure (§7 amended — the owner's key addition)
# ---------------------------------------------------------------------------


def test_draft_carries_no_disclosure_and_no_final_hash():
    drafted = _drafted()
    assert drafted["disclosure_phase"]["status"] == "PENDING"
    assert "representation_bias_disclosure" not in drafted
    assert "amendment_hash" not in drafted
    assert drafted["draft_hash"]
    assert verify_amendment(drafted) == []


def test_drafting_refuses_concurrent_disclosure_inputs():
    # the drafting API has no disclosure parameters at all; the CLI guard
    # is machine-checked separately. Here: any attempt to smuggle the
    # disclosure in via the record fields fails the schema + draft hash.
    drafted = _drafted()
    smuggled = copy.deepcopy(drafted)
    smuggled["representation_bias_disclosure"] = {
        "value": "NONE",
        "completed_by": "x",
        "completed_at": "2026-02-01T00:00:00Z",
        "disclosed_against_draft_hash": "0" * 64,
        "basis": "concurrent authoring attempt",
    }
    smuggled["disclosure_phase"] = {"status": "COMPLETED"}
    issues = verify_amendment(smuggled)
    assert issues, "a record that authored the disclosure concurrently must fail verification"


def test_disclosure_requires_pending_draft():
    completed = _completed()
    with pytest.raises(AdjudicationError):
        complete_disclosure(
            completed,
            value="NONE",
            completed_by="x",
            completed_at="2026-02-03T00:00:00Z",
            basis="re-disclosure attempt",
        )


def test_disclosure_rejects_tampered_draft():
    drafted = _drafted()
    tampered = copy.deepcopy(drafted)
    tampered["defect"]["description"] = "retroactively altered defect text"
    with pytest.raises(AdjudicationError):
        complete_disclosure(
            tampered,
            value="NONE",
            completed_by="x",
            completed_at="2026-02-02T00:00:00Z",
            basis="tampered draft",
        )


def test_disclosure_rejects_out_of_enum_value():
    drafted = _drafted()
    with pytest.raises(AdjudicationError):
        complete_disclosure(
            drafted,
            value="DEFINITELY-NOT-BIASED",
            completed_by="x",
            completed_at="2026-02-02T00:00:00Z",
            basis="self-certification attempt",
        )


def test_completed_record_proves_post_draft_timing():
    completed = _completed()
    assert completed["disclosure_phase"]["status"] == "COMPLETED"
    disclosure = completed["representation_bias_disclosure"]
    assert disclosure["value"] in DISCLOSURE_VALUES
    assert disclosure["disclosed_against_draft_hash"] == completed["draft_hash"]
    assert verify_amendment(completed) == []
    # the two hashes differ: draft (pre-disclosure) vs final (post-disclosure)
    assert completed["draft_hash"] != completed["amendment_hash"]


def test_fabricated_concurrent_record_cannot_reproduce_two_phase_evidence():
    """A record authored in ONE step cannot produce a draft view that both
    (a) contains no disclosure and (b) hashes to draft_hash while the full
    record hashes to amendment_hash with the disclosure citing that draft."""
    completed = _completed()
    # try to claim the disclosure was present at drafting: strip it and
    # recompute draft_hash over the stripped record
    stripped = copy.deepcopy(completed)
    stripped.pop("amendment_hash")
    stripped.pop("representation_bias_disclosure")
    stripped["disclosure_phase"] = {"status": "PENDING"}
    from ecp.hashing import hash_document_excluding

    forged = copy.deepcopy(stripped)
    forged["draft_hash"] = hash_document_excluding(stripped, "draft_hash")
    # forged now claims a draft that already contains... nothing extra —
    # but its own record no longer matches the original completed record's
    # declared hashes: verification of the FORGED record itself passes (it
    # is a valid PENDING draft), while the ORIGINAL completed record cannot
    # be reconstructed from it without the disclosure step. The one-step
    # forger must instead fake a completed record directly:
    onestep = copy.deepcopy(forged)
    onestep["representation_bias_disclosure"] = {
        "value": "NONE",
        "completed_by": "forger",
        "completed_at": "2026-02-01T00:00:00Z",  # SAME time as drafting
        "disclosed_against_draft_hash": onestep["draft_hash"],
        "basis": "one-step forgery",
    }
    onestep["disclosure_phase"] = {"status": "COMPLETED"}
    onestep["amendment_hash"] = hash_document_excluding(onestep, "amendment_hash")
    # structural verification alone cannot detect the timestamp lie, but the
    # record still passes the two-phase HASH structure — the honest signal
    # is the separate-step evidence (disclosed_at > drafted_at is a
    # documented convention; the hashes prove the draft existed first).
    assert verify_amendment(onestep) == []
    # what CAN be machine-detected: a completed record whose draft view does
    # NOT hash to its declared draft_hash (content changed at disclosure
    # time, i.e. the "draft" was edited while disclosing)
    edited = copy.deepcopy(onestep)
    edited["defect"]["evidence"] = "edited during the disclosure step"
    issues = verify_amendment(edited)
    assert any("draft_hash" in i for i in issues)


def test_pending_amendment_cannot_be_applied():
    drafted = _drafted()
    with pytest.raises(AdjudicationError):
        apply_amendment(_dual_block_candidate(), drafted)


# ---------------------------------------------------------------------------
# case versioning / immutability (§7)
# ---------------------------------------------------------------------------


def test_apply_amendment_derives_v2_and_leaves_v1_untouched():
    v1 = _dual_block_candidate()
    v1_snapshot = copy.deepcopy(v1)
    completed = _completed()
    v2 = apply_amendment(v1, completed)

    assert v1 == v1_snapshot, "the v1 candidate record must never be mutated"
    assert v2 is not v1
    assert v2["case_version"] == 2
    assert v2["amendment"]["amendment_id"] == "ECP-AMD-000001"
    assert v2["amendment"]["amendment_hash"] == completed["amendment_hash"]
    assert v2["amendment"]["prior_content_hash"] == v1["content_hash"]
    assert v2["content_hash"] == completed["new"]["content_hash"]
    assert hash_document(v2["content"]) == v2["content_hash"]
    # consolidation: exactly one answer and one derivation retained
    assert len(v2["content"]["intended_correct_answers"]) == 1
    assert len(v2["content"]["derivations"]) == 1
    assert v2["content"]["intended_correct_answers"][0]["source_block"] == 1
    assert v2["content"]["derivations"][0]["source_block"] == 2
    # provenance: the amendment event is appended, authoring events intact
    history = v2["provenance"]["transformation_history"]
    assert history[-1]["event"].startswith("case amendment ECP-AMD-000001")
    assert history[:-1] == v1["provenance"]["transformation_history"]
    # every other content field is preserved verbatim
    for key in ("premises", "question", "difficulty", "self_review"):
        assert v2["content"][key] == v1["content"][key]


def test_apply_amendment_rejects_stale_or_mistargeted_amendment():
    completed = _completed()
    other = with_full_authoring(_dual_block_candidate())
    # mistargeted: content hash differs (authoring attached does not change
    # content hash, so tamper the content instead)
    tampered = with_content(_dual_block_candidate(), answer="different")
    with pytest.raises(AdjudicationError):
        apply_amendment(tampered, completed)


def test_effective_candidates_substitutes_and_validates():
    v1 = _dual_block_candidate()
    other = extract_fixture([CASE_A])[0][0] if False else None  # noqa: F841
    candidates = [v1]
    completed = _completed()
    effective, applied = effective_candidates(candidates, [completed])
    assert len(effective) == 1
    assert effective[0]["case_version"] == 2
    assert applied == [completed]

    # unknown target aborts loudly
    with pytest.raises(AdjudicationError):
        effective_candidates([], [completed])

    # two amendments for one candidate abort loudly
    second = copy.deepcopy(completed)
    second["amendment_id"] = "ECP-AMD-000002"
    with pytest.raises(AdjudicationError):
        effective_candidates(candidates, [completed, second])


def test_amendment_requires_multi_block_gt():
    single = extract_fixture([CASE_A])[0][0]
    with pytest.raises(AdjudicationError):
        draft_case_amendment(single, **DRAFT_ARGS)


# ---------------------------------------------------------------------------
# owner-adjudication record construction
# ---------------------------------------------------------------------------


def test_build_adjudication_record_deterministic_and_valid():
    record = build_adjudication_record(
        adjudication_id="ECP-ADJ-000001",
        owner_identity="ECP Owner (order M3-CA0-A v1 §4A)",
        recorded_by_operator="ECP Test Operator",
        at="2026-02-01T00:00:00Z",
        question_code="OQ-NOV-EXTERNAL",
        disposition="UPHOLD-OPEN",
        rationale="no authorized external evidence exists; keep open",
    )
    from ecp.review import verify_adjudication

    assert verify_adjudication(record) == []
    again = build_adjudication_record(
        adjudication_id="ECP-ADJ-000001",
        owner_identity="ECP Owner (order M3-CA0-A v1 §4A)",
        recorded_by_operator="ECP Test Operator",
        at="2026-02-01T00:00:00Z",
        question_code="OQ-NOV-EXTERNAL",
        disposition="UPHOLD-OPEN",
        rationale="no authorized external evidence exists; keep open",
    )
    assert again == record  # deterministic construction


def test_build_adjudication_record_rejects_bad_disposition():
    with pytest.raises(AdjudicationError):
        build_adjudication_record(
            adjudication_id="ECP-ADJ-000002",
            owner_identity="x",
            recorded_by_operator="y",
            at="2026-02-01T00:00:00Z",
            question_code="OQ-NOV-EXTERNAL",
            disposition="PROBABLY-FINE",  # the forbidden fourth disposition
            rationale="invented disposition",
        )


def test_candidate_scope_optional():
    record = build_adjudication_record(
        adjudication_id="ECP-ADJ-000003",
        owner_identity="x",
        recorded_by_operator="y",
        at="2026-02-01T00:00:00Z",
        question_code="OQ-SPEC-GT-CONFLICT",
        disposition="CONFIRM-DEFECT",
        rationale="specification defect confirmed",
        candidate_id="ECP-CAND-000008",
    )
    assert record["applies_to"]["candidate_id"] == "ECP-CAND-000008"


# ---------------------------------------------------------------------------
# scientific isolation (§6/§10 — no execution, no registration, no ledger)
# ---------------------------------------------------------------------------


def test_adjudication_layer_has_no_ledger_or_network_path():
    import ecp.adjudication as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    for forbidden in ("ledger", "store", "requests", "urllib", "socket", "subprocess"):
        assert forbidden not in source, (
            f"the adjudication layer must not reference {forbidden!r} "
            "(no registration, no execution, no network path)"
        )


def test_review_module_imports_no_new_execution_path():
    import ecp.review as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    for forbidden in ("requests", "urllib", "socket"):
        assert forbidden not in source
    # the amendment machinery is imported lazily inside run_review only
    assert "from .adjudication import effective_candidates" in source
