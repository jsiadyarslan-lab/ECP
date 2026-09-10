"""M3-CA1 v1 registration-readiness engine tests.

Covers:
- the frozen 15-point battery definition (codes, keys, failure classes);
- the four readiness states (REGISTER / HOLD / REVISE / REJECT) with every
  trigger path, over a synthetic pool produced through the REAL
  qualification engine;
- the owner-decision-register contract: explicitness enforced (implicit
  defaults are loud errors), RESOLVED requires ruling+basis, O-01 evidence
  classification, blocking determination;
- the population gate: never-qualified prior material refused loudly;
  scope-outside → HOLD;
- the set-class rules: PUBLIC forbidden pre-execution (loud), HIDDEN/
  ROTATING require a set-binding reference, PROTECTED default;
- the registration-authorization gate + manifest builder: REFUSED loudly
  while anything blocks; built + verified under a fully resolved synthetic
  state;
- run-level chaining, tallies, authorization/verdict consistency, tamper
  detection, determinism re-derivation, schema validity of outputs.
"""

import pytest

from readiness_fixtures import (
    AT,
    OP,
    RUN_ID,
    make_population,
    make_qualified_pool,
    make_register,
    make_set_class,
    rehash_artifact,
)

from ecp.hashing import hash_document_excluding
from ecp.readiness import (
    ENGINE_ID,
    REGISTRATION_READINESS_CHECKS,
    InvalidReadinessState,
    RegistrationManifestRefused,
    assess_registration_authorization,
    build_registration_manifest,
    run_readiness,
    validate_decision_register,
    verify_readiness_record,
    verify_readiness_run,
    verify_registration_manifest,
)
from ecp.validate import validate_document


@pytest.fixture(scope="module")
def pool():
    return make_qualified_pool(count=3)


@pytest.fixture(scope="module")
def open_register():
    return make_register("open-blocking")


@pytest.fixture(scope="module")
def resolved_register():
    return make_register("resolved")


def _run(pool, register, population=None, set_class=None, **kwargs):
    candidates, qrun, artifacts = pool
    return run_readiness(
        candidates,
        qrun,
        artifacts,
        decision_register=register,
        population_decision=population or make_population("30-ONLY"),
        set_class_designation=set_class or make_set_class(candidates),
        prior_candidates=[],
        run_id=RUN_ID,
        assessed_at=AT,
        operator=OP,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Frozen battery
# ---------------------------------------------------------------------------


def test_battery_has_fifteen_frozen_checks():
    assert len(REGISTRATION_READINESS_CHECKS) == 15
    codes = [c[0] for c in REGISTRATION_READINESS_CHECKS]
    assert codes == [f"C-{i:02d}" for i in range(1, 16)]
    classes = {c[3] for c in REGISTRATION_READINESS_CHECKS}
    assert classes == {"REJECT", "REVISE"}
    reject_class = {c[1] for c in REGISTRATION_READINESS_CHECKS if c[3] == "REJECT"}
    assert "candidate-contract" in reject_class
    assert "ground-truth-mechanical" in reject_class
    revise_class = {c[1] for c in REGISTRATION_READINESS_CHECKS if c[3] == "REVISE"}
    assert revise_class == {
        "provenance-completeness",
        "independence-explicitness",
        "disclosure-representation-bias",
        "disclosure-environmental-precheck",
    }


# ---------------------------------------------------------------------------
# HOLD: mechanically ready, held on owner adjudication (the honest state)
# ---------------------------------------------------------------------------


def test_all_hold_when_register_open_and_blocking(pool, open_register):
    result = _run(pool, open_register)
    run, records = result["run"], result["records"]
    assert run["decisions"] == {"register": 0, "hold": 3, "revise": 0, "reject": 0}
    for record in records:
        assert record["decision"] == "HOLD"
        assert record["mechanical_state"] == "PASS"
        assert record["checks_passed"] == 15
        assert any("O-01" in reason for reason in record["holding_reasons"])
        assert any("O-04" in reason for reason in record["holding_reasons"])
    assert run["registration_authorization"]["status"] == "REFUSED"
    assert run["verdict"] == "OWNER-DECISION-REQUIRED"
    blocking = {item["item_id"] for item in run["owner_decision_register"]["blocking_items"]}
    assert blocking == {"O-01", "O-02", "O-03", "O-04"}


def test_open_mixed_register_blocks_on_open_items_only(pool):
    register = make_register("open-mixed")
    result = _run(pool, register)
    run = result["run"]
    blocking = {item["item_id"] for item in run["owner_decision_register"]["blocking_items"]}
    assert blocking == {"O-01", "O-04"}
    assert run["decisions"]["hold"] == 3
    for record in result["records"]:
        assert any("O-01" in r for r in record["holding_reasons"])
        assert any("O-04" in r for r in record["holding_reasons"])
        assert not any("O-02" in r for r in record["holding_reasons"])


def test_unresolved_finding_blocks_like_an_open_item(pool):
    register = make_register("resolved")
    register["findings"] = [
        {
            "finding_id": "F-01",
            "title": "fixture finding",
            "description": "requires an owner ruling (fixture)",
            "requires_owner_ruling": True,
            "ruling": None,
            "ruling_basis": None,
        }
    ]
    register["register_hash"] = hash_document_excluding(register, "register_hash")
    result = _run(pool, register)
    run = result["run"]
    assert run["registration_authorization"]["status"] == "REFUSED"
    assert run["decisions"]["hold"] == 3
    assert any("F-01" in reason for reason in result["records"][0]["holding_reasons"])


def test_ruled_finding_does_not_block(pool):
    register = make_register("resolved")
    register["findings"] = [
        {
            "finding_id": "F-01",
            "title": "fixture finding",
            "description": "requires an owner ruling (fixture)",
            "requires_owner_ruling": True,
            "ruling": "RULED (fixture)",
            "ruling_basis": "fixture basis",
        }
    ]
    register["register_hash"] = hash_document_excluding(register, "register_hash")
    result = _run(pool, register)
    assert result["run"]["decisions"]["register"] == 3


# ---------------------------------------------------------------------------
# REGISTER + the manifest gate
# ---------------------------------------------------------------------------


def test_register_state_when_fully_resolved(pool, resolved_register):
    result = _run(pool, resolved_register)
    run, records = result["run"], result["records"]
    assert run["decisions"] == {"register": 3, "hold": 0, "revise": 0, "reject": 0}
    assert run["registration_authorization"] == {"status": "AUTHORIZED", "reasons": []}
    assert run["verdict"] == "REGISTRATION-AUTHORIZED"
    for record in records:
        assert record["decision"] == "REGISTER"
        assert record["holding_reasons"] == []
        assert record["gt_validation_track"] == "CONFIRMED-TRACK"

    manifest = build_registration_manifest(
        records,
        run,
        registrar="ECP-REGISTRAR-TEST",
        registered_at=AT,
        registration_id="ECP-REGSET-TEST-0001",
    )
    assert manifest["ecp_object"] == "registration-manifest"
    assert len(manifest["cases"]) == 3
    assert validate_document(manifest, "registration-manifest") == []
    issues = verify_registration_manifest(manifest, records, run)
    assert issues == []


def test_manifest_refused_when_gate_refused(pool, open_register):
    result = _run(pool, open_register)
    with pytest.raises(RegistrationManifestRefused) as excinfo:
        build_registration_manifest(
            result["records"],
            result["run"],
            registrar="ECP-REGISTRAR-TEST",
            registered_at=AT,
        )
    message = str(excinfo.value)
    assert "REFUSED" in message
    assert "O-01" in message


def test_manifest_refused_when_not_all_register(pool, resolved_register):
    population = make_population("OTHER-EXPLICIT")
    population["explicit_scope"] = ["ECP-CAND-000101"]
    result = _run(pool, resolved_register, population=population)
    run, records = result["run"], result["records"]
    # case 1 in scope and REGISTER; cases 2-3 out of scope → HOLD
    assert run["decisions"] == {"register": 1, "hold": 2, "revise": 0, "reject": 0}
    with pytest.raises(RegistrationManifestRefused):
        build_registration_manifest(records, run, registrar="ECP-REGISTRAR-TEST", registered_at=AT)


def test_authorization_assessment_lists_every_reason(pool, open_register):
    candidates, qrun, artifacts = pool
    records = [
        {"candidate_id": c["candidate_id"], "decision": "HOLD"} for c in candidates
    ]
    population_block = {
        "scope_candidate_ids": [c["candidate_id"] for c in candidates],
    }
    assessment = assess_registration_authorization(open_register, population_block, records)
    assert assessment["status"] == "REFUSED"
    reasons = "\n".join(assessment["reasons"])
    for iid in ("O-01", "O-02", "O-03", "O-04"):
        assert iid in reasons
    assert reasons.count("readiness decision HOLD") == 3


# ---------------------------------------------------------------------------
# REVISE and REJECT paths
# ---------------------------------------------------------------------------


def test_revise_on_missing_representation_bias_disclosure(pool, open_register):
    candidates, qrun, artifacts = pool
    broken = [dict(c) for c in candidates]
    del broken[0]["representation_bias_disclosure"]
    result = _run((broken, qrun, artifacts), open_register)
    record = result["records"][0]
    assert record["decision"] == "REVISE"
    failed = {c["check"] for c in record["checks"] if c["status"] == "FAIL"}
    assert failed == {"disclosure-representation-bias"}
    assert record["mechanical_state"] == "FAIL"
    assert record["checks_passed"] == 14


def test_reject_on_qualification_decision_flip(pool, open_register):
    candidates, qrun, artifacts = pool
    mutated = [dict(a) for a in artifacts]
    mutated[-1]["decision"] = "REJECT"
    rehash_artifact(mutated[-1])
    result = _run((candidates, qrun, mutated), open_register)
    record = result["records"][-1]
    assert record["decision"] == "REJECT"
    failed = {c["check"] for c in record["checks"] if c["status"] == "FAIL"}
    assert failed == {"qualification-decision"}
    assert result["run"]["decisions"]["reject"] == 1


def test_reject_on_ground_truth_verification_failure(pool, open_register):
    candidates, qrun, artifacts = pool
    mutated = [dict(a) for a in artifacts]
    gt = dict(mutated[-1]["dimensions"]["ground_truth"])
    gt["status"] = "FAIL"
    mutated[-1]["dimensions"] = dict(mutated[-1]["dimensions"])
    mutated[-1]["dimensions"]["ground_truth"] = gt
    rehash_artifact(mutated[-1])
    result = _run((candidates, qrun, mutated), open_register)
    record = result["records"][-1]
    assert record["decision"] == "REJECT"
    failed = {c["check"] for c in record["checks"] if c["status"] == "FAIL"}
    assert "ground-truth-mechanical" in failed


def test_reject_on_bare_independent_label(pool, open_register):
    candidates, qrun, artifacts = pool
    broken = [dict(c) for c in candidates]
    status = dict(broken[0]["authoring_independence"]["independence_status"])
    status["label"] = "INDEPENDENT"
    broken[0]["authoring_independence"] = dict(broken[0]["authoring_independence"])
    broken[0]["authoring_independence"]["independence_status"] = status
    result = _run((broken, qrun, artifacts), open_register)
    record = result["records"][0]
    assert record["decision"] == "REVISE"
    failed = {c["check"] for c in record["checks"] if c["status"] == "FAIL"}
    assert failed == {"independence-explicitness"}


# ---------------------------------------------------------------------------
# GT validation tracks
# ---------------------------------------------------------------------------


def test_nondeterminate_track_annotation(pool, open_register):
    candidates, qrun, artifacts = pool
    mutated = [dict(a) for a in artifacts]
    gt = dict(mutated[-1]["dimensions"]["ground_truth"])
    gt["authored_class"] = "INDETERMINATE"
    gt["derived_class"] = "INDETERMINATE"
    mutated[-1]["dimensions"] = dict(mutated[-1]["dimensions"])
    mutated[-1]["dimensions"]["ground_truth"] = gt
    rehash_artifact(mutated[-1])
    result = _run((candidates, qrun, mutated), open_register)
    record = result["records"][-1]
    assert record["gt_validation_track"] == "NONDETERMINATE-READING-RULE-TRACK"
    assert any("INDETERMINATE ground truth" in r for r in record["holding_reasons"])


def test_designed_ambiguity_forwarded_track(pool, open_register):
    candidates, qrun, artifacts = pool
    mutated = [dict(a) for a in artifacts]
    mutated[-1]["forwarded"] = [
        {
            "code": "FWD-GT-DESIGNED-AMBIGUITY",
            "note": "fixture: designed two-extension ambiguity",
            "target_stage": "registration-readiness",
        }
    ]
    rehash_artifact(mutated[-1])
    result = _run((candidates, qrun, mutated), open_register)
    record = result["records"][-1]
    assert record["gt_validation_track"] == "DESIGNED-AMBIGUITY-FORWARDED"
    assert record["forwarded"][0]["code"] == "FWD-GT-DESIGNED-AMBIGUITY"
    assert record["forwarded"][0]["target_stage"] == "gt-validation (O-04 owner-authorized stage)"
    assert any("FWD-GT-DESIGNED-AMBIGUITY" in r for r in record["holding_reasons"])


def test_correspondence_gap_carried_not_blocking(pool, open_register):
    candidates, qrun, artifacts = pool
    mutated = [dict(a) for a in artifacts]
    mutated[-1]["reason_codes"] = ["Q3-CORRESPONDENCE-GAP"]
    rehash_artifact(mutated[-1])
    result = _run((candidates, qrun, mutated), open_register)
    record = result["records"][-1]
    # C-02 PASSES (ACCEPT with recorded findings is a legal state)
    checks = {c["check"]: c["status"] for c in record["checks"]}
    assert checks["qualification-decision"] == "PASS"
    assert record["carried_qualification_reason_codes"] == ["Q3-CORRESPONDENCE-GAP"]
    assert record["gt_correspondence_note"] is not None
    assert "O-04" in record["gt_correspondence_note"]
    # still HOLD via the owner blockers, not via the carried finding
    assert record["decision"] == "HOLD"


# ---------------------------------------------------------------------------
# Set-class rules
# ---------------------------------------------------------------------------


def test_public_set_class_refused_loudly_pre_execution(pool, open_register):
    candidates = pool[0]
    designation = make_set_class(candidates, uniform="PROTECTED")
    designation["assignments"][candidates[-1]["candidate_id"]] = "PUBLIC"
    with pytest.raises(InvalidReadinessState, match="PUBLIC is forbidden"):
        _run(pool, open_register, set_class=designation)


def test_hidden_requires_set_binding_reference(pool, open_register):
    candidates = pool[0]
    designation = make_set_class(candidates, uniform="PROTECTED")
    designation["assignments"][candidates[-1]["candidate_id"]] = "HIDDEN"
    with pytest.raises(InvalidReadinessState, match="set_binding_reference"):
        _run(pool, open_register, set_class=designation)


def test_hidden_allowed_with_binding_reference(pool, open_register):
    candidates = pool[0]
    designation = make_set_class(
        candidates,
        uniform="PROTECTED",
        binding_ref="fixture set-binding plan ECP-BIND-TEST-0001",
    )
    designation["assignments"][candidates[-1]["candidate_id"]] = "HIDDEN"
    result = _run(pool, open_register, set_class=designation)
    record = result["records"][-1]
    assert record["set_class"] == "HIDDEN"
    assert record["decision"] == "HOLD"  # still held on the open register


def test_set_class_designation_must_cover_every_case(pool, open_register):
    designation = make_set_class(pool[0][:-1])  # one case missing
    with pytest.raises(InvalidReadinessState, match="without a class"):
        _run(pool, open_register, set_class=designation)


# ---------------------------------------------------------------------------
# Population gate
# ---------------------------------------------------------------------------


def test_prior_pool_population_refused_loudly(pool, open_register):
    prior = [
        {
            "candidate_id": f"ECP-CAND-{i:06d}",
            "protocol_version": "0.3.0",
            "content": {"premises": ["fixture prior premise"], "structural_signature": "prior"},
        }
        for i in range(1, 3)
    ]
    candidates, qrun, artifacts = pool
    for decision in ("18-ONLY", "30+18"):
        population = make_population(decision)
        with pytest.raises(InvalidReadinessState, match="bypass the frozen pipeline"):
            run_readiness(
                candidates,
                qrun,
                artifacts,
                decision_register=open_register,
                population_decision=population,
                set_class_designation=make_set_class(candidates),
                prior_candidates=prior,
                run_id=RUN_ID,
                assessed_at=AT,
                operator=OP,
            )


def test_population_must_be_explicit(pool, open_register):
    population = make_population("30-ONLY")
    population["decision"] = "SILENT-DEFAULT"
    with pytest.raises(InvalidReadinessState, match="must be one of"):
        _run(pool, open_register, population=population)


def test_other_explicit_scope_outside_candidates_hold(pool, resolved_register):
    population = make_population("OTHER-EXPLICIT")
    population["explicit_scope"] = ["ECP-CAND-000101"]
    result = _run(pool, resolved_register, population=population)
    decisions = {r["candidate_id"]: r["decision"] for r in result["records"]}
    assert decisions["ECP-CAND-000101"] == "REGISTER"
    assert decisions["ECP-CAND-000102"] == "HOLD"
    assert decisions["ECP-CAND-000103"] == "HOLD"
    out_reasons = [
        r["holding_reasons"] for r in result["records"]
        if r["candidate_id"] == "ECP-CAND-000102"
    ][0]
    assert any("outside the explicit registration scope" in reason for reason in out_reasons)


def test_prior_pool_facts_and_overlap_re_derived(pool, open_register):
    prior = [
        {
            "candidate_id": "ECP-CAND-000001",
            "protocol_version": "0.3.0",
            "content": {
                "premises": ["completely unrelated fixture premise text"],
                "structural_signature": "unrelated",
            },
        }
    ]
    candidates, qrun, artifacts = pool
    result = run_readiness(
        candidates,
        qrun,
        artifacts,
        decision_register=open_register,
        population_decision=make_population("30-ONLY"),
        set_class_designation=make_set_class(candidates),
        prior_candidates=prior,
        run_id=RUN_ID,
        assessed_at=AT,
        operator=OP,
    )
    population = result["run"]["population"]
    assert population["prior_pool_facts"]["count"] == 1
    assert population["prior_pool_facts"]["without_formal"] == 1
    assert population["prior_pool_facts"]["without_gt_class"] == 1
    assert population["prior_pool_facts"]["without_independence"] == 1
    assert population["cross_population"]["status"] == "CLEAR"
    assert population["cross_population"]["max_premise_jaccard"] < 0.5


# ---------------------------------------------------------------------------
# Owner-decision-register contract (explicitness)
# ---------------------------------------------------------------------------


def test_register_with_missing_item_is_a_loud_error(pool):
    register = make_register("open-blocking")
    register["items"] = register["items"][:3]
    with pytest.raises(InvalidReadinessState):
        _run(pool, register)


def test_register_resolved_without_ruling_is_a_loud_error(pool):
    register = make_register("resolved")
    register["items"][0]["ruling"] = None
    with pytest.raises(InvalidReadinessState, match="RESOLVED requires an explicit ruling"):
        _run(pool, register)


def test_register_o01_without_evidence_class_is_a_loud_error(pool):
    register = make_register("open-blocking")
    del register["items"][0]["evidence_classification"]
    with pytest.raises(InvalidReadinessState, match="evidence_classification"):
        _run(pool, register)


def test_register_implicit_default_state_is_a_loud_error(pool):
    register = make_register("open-blocking")
    del register["items"][0]["state"]
    with pytest.raises(InvalidReadinessState, match="implicit defaults forbidden"):
        _run(pool, register)


def test_register_blocking_without_basis_is_a_loud_error(pool):
    register = make_register("open-blocking")
    register["items"][0]["blocking_basis"] = None
    with pytest.raises(InvalidReadinessState, match="blocking_basis"):
        _run(pool, register)


def test_validate_decision_register_detects_hash_mismatch():
    register = make_register("open-blocking")
    register["question_of_tampering"] = "injected"
    issues = validate_decision_register(register)
    assert any("recomputation mismatch" in issue for issue in issues)


# ---------------------------------------------------------------------------
# Verification, tamper detection, determinism, schema validity
# ---------------------------------------------------------------------------


def test_verification_clean_on_valid_run(pool, open_register):
    result = _run(pool, open_register)
    for record in result["records"]:
        assert verify_readiness_record(record) == []
    assert verify_readiness_run(result["run"], result["records"]) == []


def test_tampered_record_detected(pool, open_register):
    result = _run(pool, open_register)
    record = dict(result["records"][0])
    record["checks_passed"] = 3  # tamper
    issues = verify_readiness_record(record)
    assert any("checks_passed" in issue for issue in issues)


def test_tampered_run_manifest_detected(pool, open_register):
    result = _run(pool, open_register)
    run = dict(result["run"])
    run["verdict"] = "REGISTRATION-AUTHORIZED"  # inconsistent with REFUSED
    issues = verify_readiness_run(run, result["records"])
    assert any("verdict" in issue for issue in issues)
    run2 = dict(result["run"])
    run2["decisions"] = {"register": 99, "hold": 0, "revise": 0, "reject": 0}
    issues2 = verify_readiness_run(run2, result["records"])
    assert any("tallies" in issue for issue in issues2)


def test_determinism_re_derivation(pool, open_register):
    first = _run(pool, open_register)
    second = _run(pool, open_register)
    assert [r["record_hash"] for r in first["records"]] == [r["record_hash"] for r in second["records"]]
    assert first["run"]["run_hash"] == second["run"]["run_hash"]
    assert first["run"]["chain_head"] == second["run"]["chain_head"]


def test_chain_links_and_genesis(pool, open_register):
    result = _run(pool, open_register)
    records = result["records"]
    assert records[0]["prev_readiness_hash"] == "0" * 64
    for previous, record in zip(records, records[1:]):
        assert record["prev_readiness_hash"] == previous["record_hash"]
    assert result["run"]["chain_head"] == records[-1]["record_hash"]


def test_outputs_are_schema_valid(pool, open_register, resolved_register):
    for register in (open_register, resolved_register):
        assert validate_document(register, "owner-decision-register") == []
    result = _run(pool, open_register)
    assert validate_document(result["run"], "readiness-run") == []
    for record in result["records"]:
        assert validate_document(record, "case-readiness") == []


def test_engine_identity_and_boundary(pool, open_register):
    result = _run(pool, open_register)
    run = result["run"]
    assert run["engine"]["id"] == ENGINE_ID
    assert run["engine"]["profile"] == "0.6.0"
    assert "NO ledger writes" in run["execution_isolation"]
    assert "REFUSES" in run["boundary"]
    assert run["parameters"]["zero_executions_project_wide"] is True
    assert run["inputs"]["decision_register"]["item_states"]["O-01"] == "REMAINS-OPEN"
