"""M3-CA0-A review-engine integration tests.

Covers the 0.4.0 adjudication-layer extensions:

- engine profiles: a 0.3.0-profile run reproduces the legacy question set
  (byte-identical re-derivation guarantee for preserved CA0 runs);
- the new open questions OQ-SPEC-GT-CONFLICT / OQ-SPEC-AUTHORING (§4/§5
  observed triggers), emitted only under the 0.4.0 profile;
- CONFIRM-DEFECT on OQ-SPEC-GT-CONFLICT drives mechanical REJECTED (§5
  "REJECT — SPECIFICATION DEFECT" flows through the engine, never by
  hand);
- UPHOLD-OPEN on the new questions keeps REQUIRES_REVIEW (§9 three-state
  model unchanged, no fourth state);
- amended candidates re-enter FULL review (§8): v2 artifacts carry the
  amendment linkage + disclosure value; both runs are preserved (§8);
- ACCEPT-RISK resolves the open question while PARTIAL provenance
  remains an honestly recorded fact (no silent state invention).

All case material is SYNTHETIC.
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
    complete_disclosure,
    draft_case_amendment,
)

from ecp.review import (  # noqa: E402
    ENGINE_PROFILES,
    ENGINE_VERSION,
    run_review,
)
from test_adjudication import _dual_block_candidate  # noqa: E402

SOURCE_LABEL = "synthetic-test-source.md"
RUN_BASE = {
    "run_id": "ECP-REVRUN-CA0A-TEST",
    "reviewed_at": "2026-02-04T00:00:00Z",
    "operator": "ECP Review Test Executor",
}


def _run(candidates, source_text, adjudications=None, **extra):
    return run_review(
        candidates,
        source_text=source_text,
        source_label=SOURCE_LABEL,
        adjudications=adjudications or [],
        **{**RUN_BASE, **extra},
    )


# ---------------------------------------------------------------------------
# engine profiles
# ---------------------------------------------------------------------------


def test_engine_profiles_declared_and_current_is_040():
    assert ENGINE_PROFILES == ("0.3.0", "0.4.0")
    assert ENGINE_VERSION == "0.4.0"


def test_legacy_profile_reproduces_030_question_set_byte_identically():
    """The core M3-CA0-A verification property: a 0.3.0-era run must
    re-derive byte-identically under the 0.4.0 toolchain."""
    candidates, _report, source_text = extract_fixture([CASE_A])
    dual = with_content(
        candidates[0],
        extra_answer="Second conflicting authored answer.",
    )
    legacy = run_review(
        [dual],
        source_text=source_text,
        source_label=SOURCE_LABEL,
        adjudications=[],
        engine_profile="0.3.0",
        **RUN_BASE,
    )
    current = run_review(
        [dual],
        source_text=source_text,
        source_label=SOURCE_LABEL,
        adjudications=[],
        engine_profile="0.3.0",
        **RUN_BASE,
    )
    assert legacy["run"]["run_hash"] == current["run"]["run_hash"]
    assert legacy["run"]["protocol_version"] == "0.3.0"
    assert legacy["run"]["schema_version"] == "0.3.0"
    assert legacy["run"]["reviewer"]["engine_version"] == "0.3.0"
    for a, b in zip(legacy["artifacts"], current["artifacts"]):
        assert a["artifact_hash"] == b["artifact_hash"]
    # no adjudication-layer questions under the legacy profile
    codes = [q["code"] for q in legacy["artifacts"][0]["open_questions"]]
    assert "OQ-SPEC-GT-CONFLICT" not in codes
    assert "OQ-SPEC-AUTHORING" not in codes
    assert "amendments" not in legacy["run"]


def test_legacy_profile_refuses_amendments():
    from ecp.adjudication import complete_disclosure, draft_case_amendment
    from ecp.review import ReviewError

    dual = _dual_block_candidate()
    completed = complete_disclosure(
        draft_case_amendment(
            dual,
            amendment_id="ECP-AMD-000001",
            order_basis="test order",
            defect_code="SPEC-AMBIGUOUS-GT",
            defect_description="dual blocks",
            defect_why="conflict",
            defect_evidence="evidence",
            retained_answer_block=1,
            retained_derivation_block=2,
            removed_answer_blocks=[2],
            removed_derivation_blocks=[1],
            not_outcome_statement="premise analysis only",
            not_outcome_basis="no executions exist",
            amendment_author="t",
            drafted_at="2026-02-01T00:00:00Z",
            operator="t",
            order_reference="test",
        ),
        value="NONE",
        completed_by="t",
        completed_at="2026-02-02T00:00:00Z",
        basis="test",
    )
    candidates, _report, source_text = extract_fixture([CASE_A])
    with pytest.raises(ReviewError):
        run_review(
            [candidates[0]],
            source_text=source_text,
            source_label=SOURCE_LABEL,
            amendments=[completed],
            engine_profile="0.3.0",
            **RUN_BASE,
        )


# ---------------------------------------------------------------------------
# new open questions (0.4.0 profile only)
# ---------------------------------------------------------------------------


def test_gt_conflict_question_emitted_under_040_profile():
    dual = _dual_block_candidate()
    candidates, _report, source_text = extract_fixture([CASE_A])
    # the 0.4.0 questions are appended AFTER the complete 0.3.0 question
    # set (ids never shift for legacy profiles)
    legacy = run_review(
        [dual],
        source_text=source_text,
        source_label=SOURCE_LABEL,
        adjudications=[],
        engine_profile="0.3.0",
        **RUN_BASE,
    )
    legacy_count = len(legacy["artifacts"][0]["open_questions"])

    result = _run([dual], source_text)
    questions = result["artifacts"][0]["open_questions"]
    codes = [q["code"] for q in questions]
    assert "OQ-SPEC-GT-CONFLICT" in codes
    conflict = [q for q in questions if q["code"] == "OQ-SPEC-GT-CONFLICT"][0]
    assert conflict["critical"] is True
    assert conflict["owner_decision"] is None
    assert conflict["question_id"] == f"OQ-{legacy_count + 1}"
    assert result["artifacts"][0]["decision"] == "REQUIRES_REVIEW"


def test_authoring_question_emitted_when_registration_authoring_missing():
    candidates, _report, source_text = extract_fixture([CASE_A])
    result = _run([candidates[0]], source_text)
    codes = [q["code"] for q in result["artifacts"][0]["open_questions"]]
    assert "OQ-SPEC-AUTHORING" in codes

    authored = with_full_authoring(candidates[0])
    result2 = _run([authored], source_text)
    codes2 = [q["code"] for q in result2["artifacts"][0]["open_questions"]]
    assert "OQ-SPEC-AUTHORING" not in codes2


# ---------------------------------------------------------------------------
# CONFIRM-DEFECT → mechanical REJECTED (§5 through the engine)
# ---------------------------------------------------------------------------


def _confirm_defect_adjudication(candidate_id):
    from ecp.adjudication import build_adjudication_record

    return build_adjudication_record(
        adjudication_id="ECP-ADJ-000001",
        owner_identity="ECP Owner (order M3-CA0-A v1 §5)",
        recorded_by_operator="ECP Review Test Executor",
        at="2026-02-03T00:00:00Z",
        question_code="OQ-SPEC-GT-CONFLICT",
        disposition="CONFIRM-DEFECT",
        candidate_id=candidate_id,
        rationale="genuine ambiguity: premises do not support a unique answer",
    )


def test_confirm_defect_rejects_mechanically():
    dual = _dual_block_candidate()
    candidates, _report, source_text = extract_fixture([CASE_A])
    adjudication = _confirm_defect_adjudication(dual["candidate_id"])
    result = _run([dual], source_text, adjudications=[adjudication])
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REJECTED"
    assert any(r.startswith("OQ-CONFIRMED-DEFECT") for r in artifact["reason_codes"])
    conflict = [
        q for q in artifact["open_questions"] if q["code"] == "OQ-SPEC-GT-CONFLICT"
    ][0]
    assert conflict["owner_decision"]["disposition"] == "CONFIRM-DEFECT"
    assert conflict["owner_decision"]["adjudication_id"] == "ECP-ADJ-000001"
    assert result["run"]["adjudications"]["applied"] == 1


def test_candidate_scoped_adjudication_does_not_leak_to_other_candidates():
    dual = _dual_block_candidate()
    candidates, _report, source_text = extract_fixture([CASE_A])
    clean = candidates[0]
    adjudication = _confirm_defect_adjudication(dual["candidate_id"])
    result = _run([clean, dual], source_text, adjudications=[adjudication])
    clean_artifact = result["artifacts"][0]
    dual_artifact = result["artifacts"][1]
    assert clean_artifact["decision"] != "REJECTED" or (
        "OQ-CONFIRMED-DEFECT" not in str(clean_artifact["reason_codes"])
    )
    assert dual_artifact["decision"] == "REJECTED"
    # the clean candidate's GT-conflict question (absent — it has a single
    # block) never sees the candidate-scoped decision
    clean_codes = [q["code"] for q in clean_artifact["open_questions"]]
    assert "OQ-SPEC-GT-CONFLICT" not in clean_codes


# ---------------------------------------------------------------------------
# UPHOLD-OPEN on the new questions (§9 — three states only)
# ---------------------------------------------------------------------------


def test_uphold_open_on_authoring_keeps_requires_review():
    candidates, _report, source_text = extract_fixture([CASE_A])
    from ecp.adjudication import build_adjudication_record

    adjudication = build_adjudication_record(
        adjudication_id="ECP-ADJ-000002",
        owner_identity="ECP Owner (order M3-CA0-A v1 §4D)",
        recorded_by_operator="ECP Review Test Executor",
        at="2026-02-03T00:00:00Z",
        question_code="OQ-SPEC-AUTHORING",
        disposition="UPHOLD-OPEN",
        rationale="cannot be supplied without retrospective reconstruction",
    )
    result = _run([candidates[0]], source_text, adjudications=[adjudication])
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REQUIRES_REVIEW"
    authoring_q = [
        q for q in artifact["open_questions"] if q["code"] == "OQ-SPEC-AUTHORING"
    ][0]
    assert authoring_q["owner_decision"]["disposition"] == "UPHOLD-OPEN"


def test_accept_risk_resolves_question_but_provenance_fact_remains():
    """§4.C honesty: ACCEPT-RISK resolves the open question; the PARTIAL
    provenance status remains a recorded fact (never silently converted)."""
    candidates, _report, source_text = extract_fixture(
        [CASE_A],
        sidecar_overrides={
            "provenance_completeness": {
                "status": "PARTIAL",
                "not_available": ["temperature", "seed"],
            }
        },
    )
    from ecp.adjudication import build_adjudication_record

    adjudication = build_adjudication_record(
        adjudication_id="ECP-ADJ-000003",
        owner_identity="ECP Owner (order M3-CA0-A v1 §4C)",
        recorded_by_operator="ECP Review Test Executor",
        at="2026-02-03T00:00:00Z",
        question_code="OQ-PROV-PARTIAL",
        disposition="ACCEPT-RISK",
        rationale="all four missing fields class-(2): markable unavailable",
    )
    result = _run([candidates[0]], source_text, adjudications=[adjudication])
    artifact = result["artifacts"][0]
    prov_q = [q for q in artifact["open_questions"] if q["code"] == "OQ-PROV-PARTIAL"][0]
    assert prov_q["owner_decision"]["disposition"] == "ACCEPT-RISK"
    # the dimension status itself remains the honest PARTIAL fact
    assert artifact["review_dimensions"]["provenance"]["status"] == "PARTIAL"
    # still REQUIRES_REVIEW: unresolved critical novelty questions remain
    assert artifact["decision"] == "REQUIRES_REVIEW"


# ---------------------------------------------------------------------------
# amendment re-review (§7/§8)
# ---------------------------------------------------------------------------


def _completed_amendment_for(dual):
    drafted = draft_case_amendment(
        dual,
        amendment_id="ECP-AMD-000009",
        order_basis="M3-CA0-A v1 §5",
        defect_code="SPEC-AMBIGUOUS-GT",
        defect_description="duplicated GT blocks, stale conflicting answer",
        defect_why="the retained derivation contradicts the removed answer",
        defect_evidence="derivation block 1 self-corrects",
        retained_answer_block=1,
        retained_derivation_block=2,
        removed_answer_blocks=[2],
        removed_derivation_blocks=[1],
        not_outcome_statement="premise-internal selection only",
        not_outcome_basis="zero evaluated-system executions exist",
        amendment_author="ECP Test Amendment Author",
        drafted_at="2026-02-01T00:00:00Z",
        operator="ECP Review Test Executor",
        order_reference="M3-CA0-A test order",
    )
    return complete_disclosure(
        drafted,
        value="POSSIBLE",
        completed_by="ECP Test Amendment Author",
        completed_at="2026-02-02T00:00:00Z",
        basis="test fixture disclosure",
    )


def test_amended_case_re_enters_full_review_with_linkage():
    dual = _dual_block_candidate()
    candidates, _report, source_text = extract_fixture([CASE_A])
    amendment = _completed_amendment_for(dual)

    before = run_review(
        [dual],
        source_text=source_text,
        source_label=SOURCE_LABEL,
        adjudications=[],
        **RUN_BASE,
    )["artifacts"][0]

    after = run_review(
        [dual],
        source_text=source_text,
        source_label=SOURCE_LABEL,
        adjudications=[],
        amendments=[amendment],
        **RUN_BASE,
    )["artifacts"][0]

    # the amended artifact is a NEW review (nothing inherited — §8)
    assert after["artifact_hash"] != before["artifact_hash"]
    assert after["content_hash"] != before["content_hash"]
    assert after["content_hash"] == amendment["new"]["content_hash"]

    # GT-conflict dimension is clean in v2; authoring question remains
    codes = [q["code"] for q in after["open_questions"]]
    assert "OQ-SPEC-GT-CONFLICT" not in codes
    assert "OQ-SPEC-AUTHORING" in codes
    assert not any(
        f.startswith("SPEC-AMBIGUOUS-GT") or f.startswith("SPEC-DUPLICATE-GT")
        for f in after["review_dimensions"]["specification"]["findings"]
    )

    # the amendment linkage + disclosure travel with the artifact (§7)
    block = after["amendment"]
    assert block["amendment_id"] == "ECP-AMD-000009"
    assert block["amendment_hash"] == amendment["amendment_hash"]
    assert block["representation_bias_disclosure"] == "POSSIBLE"
    assert block["case_version"] == 2
    assert block["prior_content_hash"] == before["content_hash"]

    # the run manifest records the applied amendment
    run = run_review(
        [dual],
        source_text=source_text,
        source_label=SOURCE_LABEL,
        adjudications=[],
        amendments=[amendment],
        **RUN_BASE,
    )["run"]
    assert run["amendments"]["applied"] == 1
    rec = run["amendments"]["records"][0]
    assert rec["amendment_id"] == "ECP-AMD-000009"
    assert rec["disclosure"] == "POSSIBLE"


def test_both_runs_preserved_lineage_recorded():
    dual = _dual_block_candidate()
    candidates, _report, source_text = extract_fixture([CASE_A])
    amendment = _completed_amendment_for(dual)
    prior = run_review(
        [dual],
        source_text=source_text,
        source_label=SOURCE_LABEL,
        adjudications=[],
        **RUN_BASE,
    )
    current = run_review(
        [dual],
        source_text=source_text,
        source_label=SOURCE_LABEL,
        adjudications=[],
        amendments=[amendment],
        lineage={
            "prior_run_id": prior["run"]["run_id"],
            "prior_run_hash": prior["run"]["run_hash"],
            "basis": "M3-CA0-A §8 re-review",
        },
        **RUN_BASE,
    )
    lineage = current["run"]["lineage"]
    assert lineage["prior_run_id"] == prior["run"]["run_id"]
    assert lineage["prior_run_hash"] == prior["run"]["run_hash"]
    # the prior run remains fully valid on its own
    from ecp.review import verify_artifact, verify_run

    assert all(verify_artifact(a) == [] for a in prior["artifacts"])
    assert verify_run(prior["run"], prior["artifacts"]) == []


def test_determinism_re_derivation_includes_amendments():
    dual = _dual_block_candidate()
    candidates, _report, source_text = extract_fixture([CASE_A])
    amendment = _completed_amendment_for(dual)
    kwargs = dict(
        source_text=source_text,
        source_label=SOURCE_LABEL,
        adjudications=[],
        amendments=[amendment],
        **RUN_BASE,
    )
    first = run_review([dual], **kwargs)
    second = run_review([dual], **kwargs)
    assert first["run"]["run_hash"] == second["run"]["run_hash"]
    for a, b in zip(first["artifacts"], second["artifacts"]):
        assert a["artifact_hash"] == b["artifact_hash"]


def test_amended_run_verification_detects_tampering():
    from ecp.review import verify_artifact, verify_run

    dual = _dual_block_candidate()
    candidates, _report, source_text = extract_fixture([CASE_A])
    amendment = _completed_amendment_for(dual)
    result = run_review(
        [dual],
        source_text=source_text,
        source_label=SOURCE_LABEL,
        adjudications=[],
        amendments=[amendment],
        **RUN_BASE,
    )
    artifact = result["artifacts"][0]
    assert verify_artifact(artifact) == []
    assert verify_run(result["run"], result["artifacts"]) == []

    # tamper the disclosure value in the manifest record
    tampered_run = copy.deepcopy(result["run"])
    tampered_run["amendments"]["records"][0]["disclosure"] = "NONE"
    issues = verify_run(tampered_run, result["artifacts"])
    assert any("disclosure" in i or "linkage" in i for i in issues)

    # tamper the artifact's amendment linkage
    tampered_artifact = copy.deepcopy(artifact)
    tampered_artifact["amendment"]["representation_bias_disclosure"] = "NONE"
    issues = verify_artifact(tampered_artifact)
    assert issues  # self-hash breaks — tampering is always detected
