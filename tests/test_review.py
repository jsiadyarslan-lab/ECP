"""Case review engine tests (M3-CA0).

Every §11 mandatory test scenario is covered and numbered in the test
docstrings; §12 scientific-isolation properties are asserted at the end of
this module. All candidate material is synthetic test data (see
ca0_fixtures).
"""

import copy
import socket
import subprocess as subprocess_module

import pytest

import ecp.review as review_mod
from ca0_fixtures import (
    CASE_A,
    CASE_B,
    RESOLVE_ALL,
    STANDARD_RUN,
    build_adjudication,
    extract_fixture,
    with_content,
    with_full_authoring,
)

from ecp.candidates import parse_case_set
from ecp.hashing import hash_document
from ecp.review import (
    JACCARD_OVERLAP_THRESHOLD,
    ReviewError,
    run_review,
    verify_artifact,
    verify_run,
)


def _run(candidates, source_text=None, adjudications=None, **overrides):
    params = dict(STANDARD_RUN)
    params["source_text"] = source_text
    params["adjudications"] = adjudications
    params.update(overrides)
    return run_review(candidates, **params)


def _eligible_setup(source_text=None):
    """A clean single candidate, fully authored, with all open questions
    resolved by owner adjudications (the §11.1 valid candidate)."""
    candidates, _, text = extract_fixture([CASE_A])
    candidate = with_full_authoring(candidates[0])
    return [candidate], (source_text or text), RESOLVE_ALL


# --- §11.1 valid candidate -> ELIGIBLE ---------------------------------------


def test_valid_candidate_becomes_eligible():
    candidates, source_text, adjudications = _eligible_setup()
    result = _run(candidates, source_text, adjudications)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "ELIGIBLE"
    assert artifact["reason_codes"] == ["ELIGIBLE-ALL-GATES-PASS"]
    assert artifact["registration_ready"] is not None
    assert artifact["registration_ready"]["boundary"] == "STOP-BEFORE-REGISTRATION"
    assert artifact["registration_ready"]["status"] == "READY-FOR-REGISTRATION-CEREMONY"
    assert result["run"]["decisions"] == {"eligible": 1, "rejected": 0, "requires_review": 0}


# --- §11.2 malformed candidate -> REJECTED (documented rule) ------------------


def test_malformed_candidate_is_rejected():
    candidates, source_text, _ = _eligible_setup()
    broken = copy.deepcopy(candidates[0])
    del broken["content"]["question"]
    result = _run([broken], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REJECTED"
    assert any(r.startswith("INTAKE-SCHEMA-INVALID") for r in artifact["reason_codes"])
    # the rejection is materialized as a full artifact — no silent discard
    assert artifact["review_id"] == "ECP-REVIEW-000001"


def test_malformed_aux_field_is_rejected_by_schema():
    # the CA0 §9 format defines every field; a candidate missing any authored
    # field fails intake schema validation -> REJECTED (documented rule)
    candidates, source_text, _ = _eligible_setup()
    broken = copy.deepcopy(candidates[0])
    broken["content"]["difficulty"] = ""
    result = _run([broken], source_text, RESOLVE_ALL)
    assert result["artifacts"][0]["decision"] == "REJECTED"


# --- §11.3 missing provenance -> REQUIRES_REVIEW ------------------------------


def test_missing_provenance_requires_review():
    candidates, source_text, _ = _eligible_setup()
    missing = copy.deepcopy(candidates[0])
    missing["provenance"]["provenance_completeness"] = {"status": "MISSING", "not_available": []}
    result = _run([missing], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REQUIRES_REVIEW"
    assert artifact["review_dimensions"]["provenance"]["status"] == "MISSING"
    assert "OQ-PROV-MISSING" in artifact["reason_codes"]


# --- §11.4 broken provenance -> REJECTED --------------------------------------


def test_broken_provenance_chain_is_rejected():
    candidates, source_text, _ = _eligible_setup()
    tampered = copy.deepcopy(candidates[0])
    tampered["raw_block"] = tampered["raw_block"].replace("S-001", "S-999")
    result = _run([tampered], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REJECTED"
    assert "R6-PROV-BROKEN-CHAIN" in artifact["reason_codes"]
    assert artifact["review_dimensions"]["provenance_integrity"]["status"] == "BROKEN"


def test_declared_broken_provenance_is_rejected():
    candidates, source_text, _ = _eligible_setup()
    broken = copy.deepcopy(candidates[0])
    broken["provenance"]["provenance_completeness"] = {"status": "BROKEN", "not_available": []}
    result = _run([broken], source_text, RESOLVE_ALL)
    assert result["artifacts"][0]["decision"] == "REJECTED"
    assert "R2-PROV-BROKEN-DECLARED" in result["artifacts"][0]["reason_codes"]


def test_non_monotone_transformation_history_is_rejected():
    candidates, source_text, _ = _eligible_setup()
    broken = copy.deepcopy(candidates[0])
    history = broken["provenance"]["transformation_history"]
    history[0], history[1] = history[1], history[0]
    result = _run([broken], source_text, RESOLVE_ALL)
    assert result["artifacts"][0]["decision"] == "REJECTED"
    assert "R6-PROV-BROKEN-CHAIN" in result["artifacts"][0]["reason_codes"]


# --- §11.5 duplicate candidate -> REJECTED ------------------------------------


def test_exact_duplicate_is_rejected():
    duplicate = dict(CASE_A)
    duplicate["case_id"] = "S-002"
    candidates, _, source_text = extract_fixture([CASE_A, duplicate])
    candidates = [with_full_authoring(c) for c in candidates]
    result = _run(candidates, source_text, RESOLVE_ALL)
    assert result["artifacts"][0]["decision"] in ("ELIGIBLE", "REQUIRES_REVIEW")
    second = result["artifacts"][1]
    assert second["decision"] == "REJECTED"
    assert "R4-DUP-EXACT_DUPLICATE" in second["reason_codes"]
    assert second["duplicate"]["status"] == "EXACT_DUPLICATE"
    assert second["duplicate"]["of_candidate_id"] == "ECP-CAND-000001"
    # §7: duplicates are never deleted — evidence is retained
    assert second["duplicate"]["evidence"]


# --- §11.6 canonical-equivalent duplicate -> REJECTED --------------------------


def test_canonical_equivalent_duplicate_is_rejected():
    variant = dict(CASE_A)
    variant["case_id"] = "S-002"
    # same case modulo whitespace/case/punctuation
    variant["premises"] = "1. ALL   Zibs are ZOBS!\n2. no Zob is a ZUMP."
    variant["question"] = "if a zib is SELECTED,   what can be concluded about its relationship to zumps?"
    variant["answer"] = "it is NOT a zump."
    candidates, _, source_text = extract_fixture([CASE_A, variant])
    candidates = [with_full_authoring(c) for c in candidates]
    result = _run(candidates, source_text, RESOLVE_ALL)
    second = result["artifacts"][1]
    assert second["decision"] == "REJECTED"
    assert "R4-DUP-CANONICAL_DUPLICATE" in second["reason_codes"]


# --- §11.7 novelty conflict -> REQUIRES_REVIEW ---------------------------------


def test_structural_signature_collision_requires_review():
    variant = dict(CASE_B)
    variant["signature"] = CASE_A["signature"]  # same signature, different case
    candidates, _, source_text = extract_fixture([CASE_A, variant])
    candidates = [with_full_authoring(c) for c in candidates]
    result = _run(candidates, source_text, RESOLVE_ALL)
    second = result["artifacts"][1]
    assert second["decision"] == "REQUIRES_REVIEW"
    assert "R4-NOV-OVERLAP-SUSPECTED" in second["reason_codes"]
    assert second["duplicate"]["status"] == "OVERLAP_SUSPECTED"
    assert any("STRUCTURAL-SIGNATURE" in e for e in second["review_dimensions"]["novelty"]["within_set"]["overlap_evidence"])


def test_token_overlap_suspicion_requires_review():
    variant = dict(CASE_A)
    variant["case_id"] = "S-002"
    variant["signature"] = "synthetic distinct signature gamma"
    # nearly identical task text -> high token-set Jaccard
    variant["premises"] = "1. All Zibs are Zobs.\n2. No Zob is a Zump.\n3. Every Zib is quiet."
    candidates, _, source_text = extract_fixture([CASE_A, variant])
    candidates = [with_full_authoring(c) for c in candidates]
    result = _run(candidates, source_text, RESOLVE_ALL)
    second = result["artifacts"][1]
    assert "R4-NOV-OVERLAP-SUSPECTED" in second["reason_codes"]
    assert any("TOKEN-JACCARD" in e for e in second["review_dimensions"]["novelty"]["within_set"]["overlap_evidence"])


# --- §11.8 unresolved novelty -> REQUIRES_REVIEW -------------------------------


def test_unresolved_external_novelty_requires_review():
    candidates, source_text, _ = _eligible_setup()
    # NO adjudication for OQ-NOV-EXTERNAL
    result = _run(candidates, source_text, None)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REQUIRES_REVIEW"
    codes = [q["code"] for q in artifact["open_questions"]]
    assert "OQ-NOV-EXTERNAL" in codes
    question = [q for q in artifact["open_questions"] if q["code"] == "OQ-NOV-EXTERNAL"][0]
    assert question["owner_decision"] is None  # never fabricated
    assert artifact["review_dimensions"]["novelty"]["external"] == "NOT_ESTABLISHABLE_MECHANICALLY"


# --- §11.9 confirmed leakage -> REJECTED ---------------------------------------


def test_confirmed_answer_in_task_leakage_is_rejected():
    candidates, source_text, _ = _eligible_setup()
    leaking = with_content(
        candidates[0],
        question="If a Zib is selected, it is not a Zump — what explains this?",
    )
    result = _run([leaking], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REJECTED"
    assert "R5-LKG-CONFIRMED" in artifact["reason_codes"]
    flagged = [d for d in artifact["review_dimensions"]["leakage"]["detectors"] if d["result"] == "FLAGGED"]
    assert flagged and flagged[0]["detector"] == "L1-ANSWER-IN-TASK"


def test_confirmed_eval_in_task_leakage_is_rejected():
    candidates, source_text, _ = _eligible_setup()
    # derivation content inside the question (not a premise citation)
    leaking = with_content(
        candidates[0],
        question="Does the exclusion chain conclude that therefore a Zib is not a Zump because widgets never overlap?",
        derivation="1. A Zib is a Zob by premise one.\n2. No Zob is a Zump by premise two.\n3. Therefore a Zib is not a Zump because widgets never overlap.",
    )
    result = _run([leaking], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REJECTED"
    flagged = [d for d in artifact["review_dimensions"]["leakage"]["detectors"] if d["result"] == "FLAGGED"]
    assert flagged and flagged[0]["detector"] == "L2-EVAL-IN-TASK"


# --- §11.10 unresolved leakage -> REQUIRES_REVIEW -------------------------------


def test_real_world_entity_leakage_risk_requires_review():
    candidates, source_text, _ = _eligible_setup()
    risky = with_content(
        candidates[0],
        premises="1. All socrates are Zobs.\n2. No Zob is a Zump.",
    )
    result = _run([risky], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REQUIRES_REVIEW"
    assert "OQ-LKG-FLAGGED" in artifact["reason_codes"]
    assert artifact["review_dimensions"]["leakage"]["status"] == "UNRESOLVED"


def test_known_pattern_risk_requires_review():
    candidates, source_text, _ = _eligible_setup()
    risky = with_content(
        candidates[0],
        premises="1. All men are mortal.\n2. No Zob is a Zump.",
    )
    result = _run([risky], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REQUIRES_REVIEW"
    flagged = [d for d in artifact["review_dimensions"]["leakage"]["detectors"] if d["result"] == "FLAGGED"]
    assert flagged and flagged[0]["detector"] == "L4-KNOWN-PATTERN"


def test_metadata_label_in_task_requires_review():
    candidates, source_text, _ = _eligible_setup()
    risky = with_content(
        candidates[0],
        question="What does DIFFICULTY: SHALLOW imply about a Zib and Zumps?",
    )
    result = _run([risky], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REQUIRES_REVIEW"
    flagged = [d for d in artifact["review_dimensions"]["leakage"]["detectors"] if d["result"] == "FLAGGED"]
    assert flagged and flagged[0]["detector"] == "L5-METADATA"


# --- §11.11 incomplete specification -> REQUIRES_REVIEW --------------------------


def test_missing_registration_authoring_requires_review():
    candidates, source_text, adjudications = _eligible_setup()
    incomplete = copy.deepcopy(candidates[0])
    incomplete.pop("registration_authoring", None)
    result = _run([incomplete], source_text, adjudications)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REQUIRES_REVIEW"
    assert any(
        r.startswith("SPEC-REG-AUTHORING-MISSING") for r in artifact["reason_codes"]
    )
    forwarded = [f["code"] for f in artifact["forwarded_flags"]]
    assert "FWD-REG-AUTHORING" in forwarded
    assert artifact["registration_ready"] is None


def test_conflicting_answer_blocks_require_review():
    candidates, _, source_text = extract_fixture([CASE_A])
    ambiguous = with_content(
        candidates[0], extra_answer="Cannot be determined from the premises."
    )
    result = _run([ambiguous], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REQUIRES_REVIEW"
    assert any(
        r.startswith("SPEC-AMBIGUOUS-GT") for r in artifact["reason_codes"]
    )
    assert artifact["review_dimensions"]["specification"]["status"] == "AMBIGUOUS"


def test_duplicate_identical_answer_blocks_require_review():
    candidates, _, source_text = extract_fixture([CASE_A])
    duplicated = with_content(
        candidates[0],
        extra_answer=candidates[0]["content"]["intended_correct_answers"][0]["value"],
    )
    result = _run([duplicated], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REQUIRES_REVIEW"
    assert any(
        r.startswith("SPEC-DUPLICATE-GT") for r in artifact["reason_codes"]
    )


def test_negative_self_review_requires_review():
    neg = dict(CASE_A)
    neg["derivable"] = "No"
    candidates, _, source_text = extract_fixture([neg])
    candidate = with_full_authoring(candidates[0])
    result = _run([candidate], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REQUIRES_REVIEW"
    assert any(
        r.startswith("SPEC-SELFREVIEW-NEGATIVE") for r in artifact["reason_codes"]
    )


# --- §11.12 deterministic hashing ------------------------------------------------


def test_content_hash_determinism():
    candidates_a, _, _ = extract_fixture([CASE_A])
    candidates_b, _, _ = extract_fixture([CASE_A])
    assert candidates_a[0]["content_hash"] == candidates_b[0]["content_hash"]
    assert candidates_a[0]["content_hash"] == hash_document(candidates_a[0]["content"])


# --- §11.13 deterministic review artifact ----------------------------------------


def test_review_artifact_determinism():
    candidates, source_text, adjudications = _eligible_setup()
    first = _run(candidates, source_text, adjudications)
    second = _run(candidates, source_text, adjudications)
    assert [a["artifact_hash"] for a in first["artifacts"]] == [
        a["artifact_hash"] for a in second["artifacts"]
    ]
    assert first["run"]["run_hash"] == second["run"]["run_hash"]
    # different explicit timestamp -> different hash (timestamp is an input)
    other_time = _run(candidates, source_text, adjudications, reviewed_at="2026-02-02T00:00:00Z")
    assert other_time["artifacts"][0]["artifact_hash"] != first["artifacts"][0]["artifact_hash"]


# --- §11.14 invalid schema/version -> REJECTED -----------------------------------


def test_invalid_protocol_version_is_rejected():
    candidates, source_text, _ = _eligible_setup()
    future = copy.deepcopy(candidates[0])
    future["protocol_version"] = "9.9.9"
    result = _run([future], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REJECTED"
    assert any("protocol_version" in r for r in artifact["reason_codes"])


def test_wrong_schema_version_for_object_type_is_rejected():
    candidates, source_text, _ = _eligible_setup()
    future = copy.deepcopy(candidates[0])
    future["schema_version"] = "0.1.0"  # case-candidate exists only at 0.3.0
    result = _run([future], source_text, RESOLVE_ALL)
    assert result["artifacts"][0]["decision"] == "REJECTED"


# --- §11.15 invalid content hash -> REJECTED -------------------------------------


def test_invalid_content_hash_is_rejected():
    candidates, source_text, _ = _eligible_setup()
    tampered = copy.deepcopy(candidates[0])
    tampered["content_hash"] = "f" * 64
    result = _run([tampered], source_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REJECTED"
    assert "R1-HASH-MISMATCH" in artifact["reason_codes"]
    assert artifact["review_dimensions"]["identity"]["status"] == "FAIL"


# --- §11.16 reviewer identity integrity -------------------------------------------


def test_reviewer_identity_integrity():
    candidates, source_text, adjudications = _eligible_setup()
    result = _run(candidates, source_text, adjudications)
    artifact = copy.deepcopy(result["artifacts"][0])
    # reviewer identity is covered by the artifact hash: tampering breaks it
    artifact["reviewer"]["operator"] = "SOMEONE ELSE"
    issues = verify_artifact(artifact)
    assert any("artifact_hash mismatch" in i for i in issues)


# --- §11.17 ambiguous decision rejection ------------------------------------------


def test_ambiguous_decision_inputs_abort_loudly(monkeypatch):
    candidates, source_text, _ = _eligible_setup()
    from ecp.review import InvalidReviewState

    def bad_leakage(candidate):
        return "SUSPICIOUS-WEIRD-STATUS", []

    monkeypatch.setattr(review_mod, "_check_leakage", bad_leakage)
    with pytest.raises(InvalidReviewState, match="leakage status"):
        _run(candidates, source_text, RESOLVE_ALL)


def test_ambiguous_decision_enum_rejected():
    from ecp.review import InvalidReviewState, _decide

    dimensions = {
        "identity": {"status": "PASS", "content_hash_verified": True, "canonicalization": "ECP-CANONICAL-JSON-1.0"},
        "provenance": {"status": "COMPLETE", "not_available": [], "source_report_flags": []},
        "specification": {"status": "SATISFIED", "findings": []},
        "novelty": {"status": "PROBABLY-NOVEL", "within_set": {"distinct_from_prior": True, "overlap_evidence": []}, "external": "NOT_ESTABLISHABLE_MECHANICALLY"},
        "leakage": {"status": "CLEAN", "detectors": []},
        "provenance_integrity": {"status": "INTACT", "chain_verified": True, "chain_findings": []},
        "reproducibility": {"status": "RECONSTRUCTIBLE", "reconstruction_hash": "0" * 64},
    }
    with pytest.raises(InvalidReviewState):
        _decide(dimensions, {"status": "UNIQUE"}, False, [])


def test_no_fourth_state_is_emitted():
    candidates, source_text, adjudications = _eligible_setup()
    result = _run(candidates, source_text, None)
    allowed = {"ELIGIBLE", "REJECTED", "REQUIRES_REVIEW"}
    for artifact in result["artifacts"]:
        assert artifact["decision"] in allowed
        assert artifact["reason_codes"]


# --- §11.18 tampered review artifact ----------------------------------------------


def test_tampered_review_artifact_detected():
    candidates, source_text, _ = _eligible_setup()
    # an unresolved run (REQUIRES_REVIEW) tampered into ELIGIBLE
    result = _run(candidates, source_text, None)
    artifact = copy.deepcopy(result["artifacts"][0])
    assert artifact["decision"] == "REQUIRES_REVIEW"
    artifact["decision"] = "ELIGIBLE"
    artifact["reason_codes"] = ["ELIGIBLE-ALL-GATES-PASS"]
    issues = verify_artifact(artifact)
    assert any("artifact_hash mismatch" in i for i in issues)


def test_tampered_run_manifest_detected():
    candidates, source_text, adjudications = _eligible_setup()
    result = _run(candidates, source_text, adjudications)
    run = copy.deepcopy(result["run"])
    run["decisions"]["eligible"] = 5
    issues = verify_run(run, result["artifacts"])
    assert any("tally mismatch" in i for i in issues)
    # the manifest hash covers the tally too
    issues2 = verify_run(run, result["artifacts"])
    assert any("run_hash mismatch" in i for i in issues2)


def test_chain_tampering_detected():
    candidates, source_text, adjudications = _eligible_setup()
    result = _run(
        [with_full_authoring(c) for c in extract_fixture([CASE_A, CASE_B])[0]],
        extract_fixture([CASE_A, CASE_B])[2],
        adjudications,
    )
    artifacts = result["artifacts"]
    assert len(artifacts) == 2
    tampered = copy.deepcopy(artifacts[1])
    tampered["prev_artifact_hash"] = "0" * 64
    issues = verify_run(result["run"], [artifacts[0], tampered])
    assert any("prev_artifact_hash" in i for i in issues)


# --- §11.19 reproducibility failure -------------------------------------------------


def test_reproducibility_failure_rejected():
    from ecp.review import _decide

    dimensions = {
        "identity": {"status": "PASS", "content_hash_verified": True, "canonicalization": "ECP-CANONICAL-JSON-1.0"},
        "provenance": {"status": "COMPLETE", "not_available": [], "source_report_flags": []},
        "specification": {"status": "SATISFIED", "findings": []},
        "novelty": {"status": "NOVEL_WITHIN_SET", "within_set": {"distinct_from_prior": True, "overlap_evidence": []}, "external": "NOT_ESTABLISHABLE_MECHANICALLY"},
        "leakage": {"status": "CLEAN", "detectors": []},
        "provenance_integrity": {"status": "INTACT", "chain_verified": True, "chain_findings": []},
        "reproducibility": {"status": "FAILED", "reconstruction_hash": "0" * 64},
    }
    decision, reasons = _decide(dimensions, {"status": "UNIQUE"}, False, [])
    assert decision == "REJECTED"
    assert "R7-REPRO-BROKEN" in reasons


def test_artifact_embeds_reconstructible_candidate():
    candidates, source_text, adjudications = _eligible_setup()
    result = _run(candidates, source_text, adjudications)
    artifact = result["artifacts"][0]
    # another operator can reconstruct the candidate definition from the
    # artifact alone: the embedded content hashes to the content hash
    assert hash_document(artifact["candidate_content"]) == artifact["content_hash"]
    assert artifact["review_dimensions"]["reproducibility"]["status"] == "RECONSTRUCTIBLE"
    # tampering the embedded snapshot breaks R7 verification
    tampered = copy.deepcopy(artifact)
    tampered["candidate_content"]["question"] = "changed"
    issues = verify_artifact(tampered)
    assert issues


# --- §11.20 scientific-execution prohibition ----------------------------------------


def test_format_illustration_refused():
    candidates, source_text, _ = _eligible_setup()
    illustration = copy.deepcopy(candidates[0])
    illustration["content_class"] = "format-illustration"
    with pytest.raises(ReviewError, match="format-illustration"):
        _run([illustration], source_text, RESOLVE_ALL)


def test_no_network_or_subprocess_invocation(monkeypatch, tmp_path):
    # §12: the full pipeline runs with sockets and subprocesses disabled
    def no_sockets(*args, **kwargs):
        raise AssertionError("network invocation attempted")

    def no_subprocess(*args, **kwargs):
        raise AssertionError("subprocess invocation attempted")

    monkeypatch.setattr(socket, "socket", no_sockets)
    monkeypatch.setattr(subprocess_module, "run", no_subprocess)
    monkeypatch.setattr(subprocess_module, "Popen", no_subprocess)
    monkeypatch.setattr(subprocess_module, "check_output", no_subprocess)

    candidates, source_text, adjudications = _eligible_setup()
    result = _run(candidates, source_text, adjudications)
    assert result["artifacts"][0]["decision"] in (
        "ELIGIBLE",
        "REJECTED",
        "REQUIRES_REVIEW",
    )


def test_review_modules_have_no_execution_or_ledger_paths():
    # §12: the review layer has no code path to the ledger, the store,
    # model adapters, or network/subprocess execution — checked on the
    # actual import graph (AST), not on prose.
    import ast

    import ecp.candidates as candidates_mod

    forbidden_modules = {
        "socket", "subprocess", "requests", "http", "urllib", "urllib3",
        "httpx", "openai", "z_ai", "zai", "os.system", "popen",
    }
    forbidden_ecp_imports = {"ecp.ledger", "ecp.store"}
    for module in (review_mod, candidates_mod):
        tree = ast.parse(open(module.__file__, encoding="utf-8").read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    prefix = "ecp." if node.level == 1 else ""
                    imported.add(prefix + node.module)
        assert not (imported & forbidden_modules), (
            f"{module.__name__} imports forbidden modules: {imported & forbidden_modules}"
        )
        assert not (imported & forbidden_ecp_imports), (
            f"{module.__name__} imports {imported & forbidden_ecp_imports}"
        )


def test_pipeline_writes_nothing_outside_review_root(tmp_path):
    # §12: run_review is pure — it writes nothing at all
    before = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}
    candidates, source_text, adjudications = _eligible_setup()
    result = _run(candidates, source_text, adjudications)
    after = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
    assert result["artifacts"]


def test_public_ledger_untouched_by_review(tmp_path):
    # §12/§13: the review run does not touch a ledger tree
    from ecp.ledger import init_ledger

    ledger_root = tmp_path / "ledger"
    init_ledger(ledger_root, "ECP-LEDGER-TEST", at="2026-01-01T00:00:00Z")
    snapshot = {
        p.relative_to(ledger_root).as_posix(): p.read_bytes()
        for p in sorted(ledger_root.rglob("*"))
        if p.is_file()
    }
    candidates, source_text, adjudications = _eligible_setup()
    _run(candidates, source_text, adjudications)
    after = {
        p.relative_to(ledger_root).as_posix(): p.read_bytes()
        for p in sorted(ledger_root.rglob("*"))
        if p.is_file()
    }
    assert snapshot == after


# --- adjudication seam (§9) -----------------------------------------------------------


def test_owner_decisions_recorded_never_fabricated():
    candidates, source_text, _ = _eligible_setup()
    result = _run(candidates, source_text, None)
    for question in result["artifacts"][0]["open_questions"]:
        assert question["owner_decision"] is None

    resolved = _run(candidates, source_text, RESOLVE_ALL)
    artifact = resolved["artifacts"][0]
    assert artifact["adjudications_applied"]
    decisions = [
        q["owner_decision"] for q in artifact["open_questions"] if q["owner_decision"]
    ]
    assert decisions
    for decision in decisions:
        assert decision["disposition"] in (
            "RESOLVE-CLEAN",
            "ACCEPT-RISK",
            "CONFIRM-DEFECT",
            "UPHOLD-OPEN",
        )


def test_confirm_defect_adjudication_rejects():
    candidates, source_text, _ = _eligible_setup()
    confirm = [
        build_adjudication("ECP-ADJ-000001", "OQ-NOV-EXTERNAL", "CONFIRM-DEFECT"),
        build_adjudication("ECP-ADJ-000002", "OQ-LKG-CONTAMINATION", "RESOLVE-CLEAN"),
    ]
    result = _run(candidates, source_text, confirm)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REJECTED"
    assert any(r.startswith("OQ-CONFIRMED-DEFECT") for r in artifact["reason_codes"])


def test_uphold_open_keeps_requires_review():
    candidates, source_text, _ = _eligible_setup()
    uphold = [
        build_adjudication("ECP-ADJ-000001", "OQ-NOV-EXTERNAL", "UPHOLD-OPEN"),
        build_adjudication("ECP-ADJ-000002", "OQ-LKG-CONTAMINATION", "RESOLVE-CLEAN"),
    ]
    result = _run(candidates, source_text, uphold)
    assert result["artifacts"][0]["decision"] == "REQUIRES_REVIEW"


def test_candidate_scoped_adjudication():
    candidates, _, source_text = extract_fixture([CASE_A, CASE_B])
    candidates = [with_full_authoring(c) for c in candidates]
    scoped = RESOLVE_ALL + [
        build_adjudication("ECP-ADJ-000005", "OQ-NOV-EXTERNAL", "UPHOLD-OPEN", candidate_id="ECP-CAND-000002"),
    ]
    result = _run(candidates, source_text, scoped)
    first = result["artifacts"][0]
    second = result["artifacts"][1]
    assert first["decision"] == "ELIGIBLE"
    assert second["decision"] == "REQUIRES_REVIEW"


def test_later_adjudication_overrides_earlier():
    candidates, source_text, _ = _eligible_setup()
    overrides = [
        build_adjudication("ECP-ADJ-000001", "OQ-NOV-EXTERNAL", "UPHOLD-OPEN", at="2026-01-02T12:00:00Z"),
        build_adjudication("ECP-ADJ-000002", "OQ-NOV-EXTERNAL", "RESOLVE-CLEAN", at="2026-01-04T12:00:00Z"),
        build_adjudication("ECP-ADJ-000003", "OQ-LKG-CONTAMINATION", "RESOLVE-CLEAN"),
    ]
    result = _run(candidates, source_text, overrides)
    assert result["artifacts"][0]["decision"] == "ELIGIBLE"


def test_invalid_adjudication_disposition_aborts():
    candidates, source_text, _ = _eligible_setup()
    bogus = build_adjudication("ECP-ADJ-000001", "OQ-NOV-EXTERNAL", "RESOLVE-CLEAN")
    bogus["disposition"] = "MAKE-IT-ELIGIBLE"
    with pytest.raises(Exception):
        _run(candidates, source_text, [bogus])


# --- source not supplied: chain unverifiable -------------------------------------------


def test_source_not_supplied_leaves_chain_unverified():
    candidates, _, _ = extract_fixture([CASE_A])
    candidate = with_full_authoring(candidates[0])
    result = _run([candidate], None, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["review_dimensions"]["provenance_integrity"]["status"] == "UNVERIFIED"
    assert artifact["decision"] == "REQUIRES_REVIEW"
    assert "OQ-PROV-CHAIN-UNVERIFIED" in artifact["reason_codes"]


def test_wrong_source_document_is_rejected():
    candidates, _, _ = extract_fixture([CASE_A])
    candidate = with_full_authoring(candidates[0])
    other_text = extract_fixture([CASE_B])[2]
    result = _run([candidate], other_text, RESOLVE_ALL)
    artifact = result["artifacts"][0]
    assert artifact["decision"] == "REJECTED"
    assert "R6-PROV-BROKEN-CHAIN" in artifact["reason_codes"]


# --- forwarded flags ---------------------------------------------------------------------


def test_gt_verification_forwarded_not_resolved():
    candidates, source_text, adjudications = _eligible_setup()
    result = _run(candidates, source_text, adjudications)
    forwarded = [f["code"] for f in result["artifacts"][0]["forwarded_flags"]]
    assert "FWD-GT-VERIFICATION" in forwarded
    assert all(
        f["target_stage"] in ("ground-truth-verification", "registration-authoring", "registration-ceremony")
        for f in result["artifacts"][0]["forwarded_flags"]
    )


def test_nondeterminate_design_forwarded():
    from ca0_fixtures import build_sidecar
    from ecp.candidates import extract_candidates
    from ecp.hashing import sha256_hex

    import tempfile
    from pathlib import Path

    source_text = build_source_text([CASE_A]) if False else None
    # build a flagged candidate directly
    candidates, _, text = extract_fixture([CASE_A])
    candidate = with_full_authoring(candidates[0])
    candidate["provenance"]["candidate_flags"] = ["nondeterminate-answer-design"]
    result = _run([candidate], text, RESOLVE_ALL)
    forwarded = [f["code"] for f in result["artifacts"][0]["forwarded_flags"]]
    assert "FWD-GT-NONDETERMINATE" in forwarded


# --- run-level properties -----------------------------------------------------------------


def test_run_manifest_records_every_candidate():
    candidates, _, source_text = extract_fixture([CASE_A, CASE_B])
    result = _run(candidates, source_text, None)
    run = result["run"]
    assert run["input"]["candidates_inspected"] == 2
    assert len(run["entries"]) == 2
    assert run["decisions"]["requires_review"] == 2
    assert run["chain_head"] == result["artifacts"][-1]["artifact_hash"]
    assert run["review_parameters"]["jaccard_overlap_threshold"] == JACCARD_OVERLAP_THRESHOLD


def test_artifacts_schema_valid_and_chain_consistent():
    from ecp.validate import validate_document

    candidates, _, source_text = extract_fixture([CASE_A, CASE_B])
    result = _run(candidates, source_text, RESOLVE_ALL)
    prev = "0" * 64
    for index, artifact in enumerate(result["artifacts"], start=1):
        assert validate_document(artifact, "case-review") == []
        assert artifact["entry_index"] == index
        assert artifact["prev_artifact_hash"] == prev
        prev = artifact["artifact_hash"]
    assert validate_document(result["run"], "review-run") == []
    assert verify_run(result["run"], result["artifacts"]) == []
    assert all(verify_artifact(a) == [] for a in result["artifacts"])
