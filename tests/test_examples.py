"""End-to-end example integrity tests: every hash and commitment embedded in
the examples is REAL and recomputes exactly."""

import pytest

from helpers import set_path

from ecp.hashing import hash_document, hash_document_excluding, hash_file
from ecp.manifest import compute_manifest_hash
from ecp.verification import verify_commitment, verify_evidence_reference

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
]


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_cites_pinned_protocol_versions(filename, examples, ident):
    document = examples[filename]
    assert document["protocol_version"] == ident["protocol_version"]
    if "schema_version" in document:
        assert document["schema_version"] == ident["schema_version"]


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
