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
