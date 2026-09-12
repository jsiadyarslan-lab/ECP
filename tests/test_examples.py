"""End-to-end example integrity tests: every hash and commitment embedded in
the examples is REAL and recomputes exactly."""

import json

import pytest

from helpers import set_path

from ecp.hashing import hash_document, hash_document_excluding, hash_file
from ecp.manifest import compute_manifest_hash
from ecp.verification import verify_commitment, verify_evidence_reference
from ecp.versions import allowed_schema_versions, PROTOCOL_VERSIONS

EXAMPLE_FILES = [
    "case.development.example.json",
    "ground-truth.format-example.json",
    "system.model-only.example.json",
    "system.complete-system.example.json",
    "evaluation.example.json",
    "registration.example.json",
    "execution.example.json",
    "evidence.example.json",
    "manifest.example.json",
    "audit.two-auditor.example.json",
    "audit.single-auditor-fallback.example.json",
    "ledger-entry.example.json",
    "store-manifest.example.json",
    "case-candidate.example.json",
    "case-review.example.json",
    "review-run.example.json",
    "review-adjudication.example.json",
    "case-amendment.example.json",
    "case-qualification.example.json",
    "qualification-run.example.json",
    "owner-decision-register.example.json",
    "case-readiness.example.json",
    "readiness-run.example.json",
    "registration-manifest.example.json",
    "registration-gate-state.example.json",
    "owner-gate-order.example.json",
    "registration-package.example.json",
    "trust-registration.example.json",
    "registration-amendment.example.json",
    "lineage-event.example.json",
    "trust-store-manifest.example.json",
    "runtime-observation.example.json",
    "onboarding.example.json",
]


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_cites_compatible_protocol_versions(filename, examples, ident):
    # 0.2.0 additive bundle: examples may cite the original 0.1.0 contracts
    # (historical R0 artifacts, unchanged) or the 0.2.0 bundle versions for
    # unchanged contracts; new 0.2.0 object types must cite 0.2.0. This is
    # the explicit compatibility policy (ecp.versions).
    document = examples[filename]
    assert document["protocol_version"] in PROTOCOL_VERSIONS, filename
    allowed = allowed_schema_versions(document.get("ecp_object"))
    if "schema_version" in document:
        assert document["schema_version"] in allowed, filename


def test_case_commitment_is_real(examples):
    case = examples["case.development.example.json"]
    gt = examples["ground-truth.format-example.json"]
    assert case["ground_truth_reference"]["commitment"] == hash_document(gt)


def test_case_commitment_verification_end_to_end(examples):
    assert verify_commitment(
        examples["case.development.example.json"],
        examples["ground-truth.format-example.json"],
    ) == []


def test_registration_hash_is_real(examples):
    registration = examples["registration.example.json"]
    recomputed = hash_document_excluding(registration, "registration_hash")
    assert registration["registration_hash"] == recomputed


def test_registration_hash_excludes_only_hash_field(examples):
    registration = examples["registration.example.json"]
    other = set_path(registration, "success_criterion", "different frozen text")
    assert hash_document_excluding(other, "registration_hash") != registration["registration_hash"]


def test_evidence_bundle_hashes_are_real(repo_root, examples):
    bundle = examples["evidence.example.json"]["bundle"]
    for key in ("raw_output", "execution_trace", "system_identity"):
        reference = bundle[key]
        assert hash_file(repo_root / reference["path"]) == reference["sha256"], key


def test_evidence_manifest_hash_is_real(examples):
    evidence = examples["evidence.example.json"]
    manifest = examples["manifest.example.json"]
    assert evidence["integrity"]["manifest_hash"] == compute_manifest_hash(manifest)


def test_evidence_manifest_covers_referenced_artifacts(examples):
    evidence = examples["evidence.example.json"]
    manifest = examples["manifest.example.json"]
    manifest_paths = {entry["path"] for entry in manifest["entries"]}
    for key in ("raw_output", "execution_trace", "system_identity"):
        assert evidence["bundle"][key]["path"] in manifest_paths, key


def test_audit_evidence_hashes_are_real(examples):
    evidence = examples["evidence.example.json"]
    expected = hash_document(evidence)
    for filename in ("audit.two-auditor.example.json", "audit.single-auditor-fallback.example.json"):
        reviewed = examples[filename]["evidence_reviewed"]
        assert all(item["evidence_hash"] == expected for item in reviewed), filename


def test_audit_evidence_reference_verification(examples):
    assert verify_evidence_reference(
        examples["audit.two-auditor.example.json"],
        examples["evidence.example.json"],
    ) == []


def test_execution_and_case_prompt_agree(examples):
    # the executed input is the case input, verbatim
    assert (
        examples["execution.example.json"]["input"]["prompt"]
        == examples["case.development.example.json"]["input"]["prompt"]
    )


def test_example_documents_are_flagged_as_examples(examples):
    # every example carries an explicit non-scientific marker somewhere in its text
    markers = ("FORMAT EXAMPLE", "DEVELOPMENT EXAMPLE", "format example", "FORMAT ILLUSTRATION")
    for filename, document in examples.items():
        text = str(document)
        assert any(marker in text for marker in markers), filename


# --- R1-I examples: real, recomputable hashes ------------------------------


def test_ledger_entry_example_hashes_are_real(examples):
    entry = examples["ledger-entry.example.json"]
    registration = examples["registration.example.json"]
    case = examples["case.development.example.json"]
    # record_hash is the canonical document hash of the wrapped record
    assert entry["record_ref"]["record_hash"] == hash_document(registration)
    # the frozen commitment is the public case's real commitment
    assert (
        entry["ground_truth_commitments"][0]["commitment"]
        == case["ground_truth_reference"]["commitment"]
    )
    # genesis chaining + self-hash recompute
    assert entry["prev_entry_hash"] == "0" * 64
    assert entry["entry_hash"] == hash_document_excluding(entry, "entry_hash")


def test_store_manifest_example_is_deterministic_rebuild(tmp_path, ident):
    # byte-identical to a fresh init_store run with the same pinned arguments
    from ecp import store

    manifest = store.init_store(
        tmp_path,
        "ECP-STORE-EXAMPLE-0001",
        "development",
        at="1970-01-01T00:00:00Z",
    )
    shipped = json.load(open("examples/store-manifest.example.json"))
    # the shipped file additionally carries a notes field; compare the
    # state fields and determinism of the underlying machinery
    for key in (
        "store_id", "scope", "created_at", "zones", "seals", "oplog",
        "hash_algorithm", "canonicalization",
    ):
        assert shipped[key] == manifest[key], key
    assert shipped["manifest_hash"] == hash_document_excluding(
        shipped, "manifest_hash"
    )


def test_store_manifest_example_oplog_head_is_real(tmp_path):
    # the oplog head in the example equals the real init oplog entry hash
    from ecp import store

    root = tmp_path
    store.init_store(
        root, "ECP-STORE-EXAMPLE-0001", "development",
        at="1970-01-01T00:00:00Z",
    )
    entry = json.loads((root / "oplog" / "00000001.json").read_text())
    shipped = json.load(open("examples/store-manifest.example.json"))
    assert shipped["oplog"]["head_oplog_hash"] == entry["oplog_hash"]


# --- M3-CA0 review-layer examples: real, recomputable hashes ------------------


def test_case_candidate_example_hash_is_real(examples):
    candidate = examples["case-candidate.example.json"]
    assert candidate["content_class"] == "format-illustration"
    assert candidate["content_hash"] == hash_document(candidate["content"])


def test_case_review_example_hashes_are_real(examples):
    artifact = examples["case-review.example.json"]
    assert artifact["content_class"] == "format-illustration"
    assert artifact["artifact_hash"] == hash_document_excluding(
        artifact, "artifact_hash"
    )
    # R7: the embedded candidate snapshot reconstructs to the content hash
    assert hash_document(artifact["candidate_content"]) == artifact["content_hash"]
    # §10 boundary: ELIGIBLE example carries an explicit STOP marker
    assert artifact["decision"] == "ELIGIBLE"
    assert artifact["registration_ready"]["boundary"] == "STOP-BEFORE-REGISTRATION"
    assert artifact["prev_artifact_hash"] == "0" * 64


def test_review_run_example_is_consistent(examples):
    run = examples["review-run.example.json"]
    artifact = examples["case-review.example.json"]
    candidate = examples["case-candidate.example.json"]
    assert run["run_hash"] == hash_document_excluding(run, "run_hash")
    entry = run["entries"][0]
    assert entry["artifact_hash"] == artifact["artifact_hash"]
    assert entry["content_hash"] == candidate["content_hash"]
    assert entry["candidate_id"] == candidate["candidate_id"]
    assert run["chain_head"] == artifact["artifact_hash"]
    assert run["decisions"] == {"eligible": 1, "rejected": 0, "requires_review": 0}
    assert run["adjudications"]["applied"] == 2


def test_review_adjudication_example_hash_is_real(examples):
    adjudication = examples["review-adjudication.example.json"]
    assert adjudication["adjudication_hash"] == hash_document_excluding(
        adjudication, "adjudication_hash"
    )
    assert adjudication["applies_to"]["question_code"] == "OQ-NOV-EXTERNAL"


def test_case_amendment_example_two_phase_hashes_are_real(examples):
    """M3-CA0-A: the amendment example carries BOTH hashes — draft_hash
    over the disclosure-free draft and amendment_hash over the completed
    record — machine evidence that the disclosure was completed in a
    separate step AFTER drafting (never concurrently)."""
    amendment = examples["case-amendment.example.json"]
    import copy as _copy

    from ecp.hashing import hash_document_excluding

    assert amendment["ecp_object"] == "case-amendment"
    assert amendment["disclosure_phase"]["status"] == "COMPLETED"
    disclosure = amendment["representation_bias_disclosure"]
    assert disclosure["value"] in ("NONE", "POSSIBLE", "KNOWN")
    assert disclosure["disclosed_against_draft_hash"] == amendment["draft_hash"]

    # the full record hashes to amendment_hash
    assert amendment["amendment_hash"] == hash_document_excluding(
        amendment, "amendment_hash"
    )
    # the disclosure-free draft view hashes to draft_hash
    draft_view = _copy.deepcopy(amendment)
    draft_view.pop("amendment_hash", None)
    draft_view.pop("representation_bias_disclosure", None)
    draft_view["disclosure_phase"] = {"status": "PENDING"}
    assert amendment["draft_hash"] == hash_document_excluding(
        draft_view, "draft_hash"
    )
    assert amendment["draft_hash"] != amendment["amendment_hash"]
    # §7: material amendments never inherit review state
    assert amendment["re_review"]["required"] is True


# ---------------------------------------------------------------------------
# M3-CA1 v1 registration-readiness examples (real, recomputable hashes)
# ---------------------------------------------------------------------------


def test_readiness_example_hashes_are_real(examples):
    register = examples["owner-decision-register.example.json"]
    record = examples["case-readiness.example.json"]
    run = examples["readiness-run.example.json"]
    manifest = examples["registration-manifest.example.json"]

    assert register["register_hash"] == hash_document_excluding(register, "register_hash")
    assert record["record_hash"] == hash_document_excluding(record, "record_hash")
    assert run["run_hash"] == hash_document_excluding(run, "run_hash")
    assert manifest["manifest_hash"] == hash_document_excluding(manifest, "manifest_hash")

    # the register is the run's recorded input
    assert run["inputs"]["decision_register"]["register_hash"] == register["register_hash"]
    # the record is the run's chain
    assert run["chain_head"] == record["record_hash"]
    assert run["entries"][0]["record_hash"] == record["record_hash"]
    # the record binds the 0.5.0 qualification example
    qualification = examples["case-qualification.example.json"]
    assert record["qualification_artifact_hash"] == qualification["artifact_hash"]
    # the manifest binds the run and the case
    assert manifest["readiness_run"]["run_hash"] == run["run_hash"]
    assert manifest["cases"][0]["qualification_artifact_hash"] == qualification["artifact_hash"]


def test_readiness_examples_are_honest_about_the_gate(examples):
    run = examples["readiness-run.example.json"]
    record = examples["case-readiness.example.json"]
    # the illustration records the honest REFUSED state, never a fake pass
    assert run["registration_authorization"]["status"] == "REFUSED"
    assert run["verdict"] == "OWNER-DECISION-REQUIRED"
    assert run["registration_authorization"]["reasons"]
    assert record["decision"] == "HOLD"
    assert record["mechanical_state"] == "PASS"
    assert record["checks_passed"] == 15


# ---------------------------------------------------------------------------
# M3-RG0 trust-layer examples: every embedded hash is REAL and the
# cross-references recompute exactly (order §7/§11).
# ---------------------------------------------------------------------------


def test_gate_state_example_hash_is_real(examples):
    gate = examples["registration-gate-state.example.json"]
    assert gate["gate_hash"] == hash_document_excluding(gate, "gate_hash")
    assert gate["registration_gate"] == "CLOSED"
    assert gate["owner_ruling_citations"] == {
        slot: None for slot in ("O-01", "O-02", "O-04", "F-01a", "F-01b", "POP")
    }


def test_registration_package_example_hash_is_real(examples):
    package = examples["registration-package.example.json"]
    assert package["package_hash"] == hash_document_excluding(package, "package_hash")


def test_registration_package_example_case_seam_is_real(examples):
    package = examples["registration-package.example.json"]
    case = examples["case.development.example.json"]
    gt = examples["ground-truth.format-example.json"]
    assert package["case_document"] == case
    assert package["success_criterion"] == case["success_criterion"]
    assert package["ground_truth"]["commitment"] == hash_document(gt)
    assert package["ground_truth"]["commitment"] == case["ground_truth_reference"]["commitment"]


def test_trust_registration_example_hash_is_real(examples):
    record = examples["trust-registration.example.json"]
    assert record["registration_hash"] == hash_document_excluding(record, "registration_hash")


def test_trust_registration_example_commitments_recompute(examples):
    record = examples["trust-registration.example.json"]
    package = examples["registration-package.example.json"]
    c = record["commitments"]
    assert c["case"] == hash_document(package["case_document"])
    assert c["ground_truth"] == package["ground_truth"]["commitment"]
    assert c["criterion"] == hash_document({"success_criterion": package["success_criterion"]})
    assert c["environment"] == hash_document(package["environment"])
    assert c["provenance"] == hash_document(package["provenance"])
    assert c["package"] == package["package_hash"]


def test_lineage_event_example_hash_is_real_and_binds_record(examples):
    event = examples["lineage-event.example.json"]
    record = examples["trust-registration.example.json"]
    assert event["event_hash"] == hash_document_excluding(event, "event_hash")
    assert event["payload"]["record_hash"] == hash_document(record)
    assert event["payload"]["registration_id"] == record["registration_id"]


def test_registration_amendment_example_hash_is_real_and_binds_target(examples):
    amendment = examples["registration-amendment.example.json"]
    record = examples["trust-registration.example.json"]
    assert amendment["amendment_hash"] == hash_document_excluding(amendment, "amendment_hash")
    assert amendment["target_registration_hash"] == hash_document(record)


def test_trust_store_manifest_example_hash_is_real(examples):
    manifest = examples["trust-store-manifest.example.json"]
    event = examples["lineage-event.example.json"]
    gate = examples["registration-gate-state.example.json"]
    assert manifest["manifest_hash"] == hash_document_excluding(manifest, "manifest_hash")
    assert manifest["lineage"]["head_event_hash"] == event["event_hash"]
    assert manifest["gate"]["gate_hash"] != gate["gate_hash"]  # the manifest illustrates an OPEN gate


def test_runtime_observation_example_hash_is_real_and_non_authoritative(examples):
    obs = examples["runtime-observation.example.json"]
    assert obs["observation_hash"] == hash_document_excluding(obs, "observation_hash")
    assert obs["authority_class"] == "NON-AUTHORITATIVE"
    assert obs["zone"] == "operational"
