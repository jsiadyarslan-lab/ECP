"""Verification layer tests (§15: verification boundary, integrity only).

These tests double as the semantic guard that verification NEVER adjudicates:
every function returns integrity findings, and the module documents the
distinction explicitly.
"""

import inspect

from helpers import set_path

from ecp import verification
from ecp.hashing import hash_document, hash_document_excluding
from ecp.manifest import compute_manifest_hash


def test_commitment_verification_passes(examples):
    case = examples["case.development.example.json"]
    gt = examples["ground-truth.format-example.json"]
    assert verification.verify_commitment(case, gt) == []


def test_commitment_detects_ground_truth_tampering(examples):
    case = examples["case.development.example.json"]
    tampered = set_path(examples["ground-truth.format-example.json"], "expected_answer.value", 6)
    issues = verification.verify_commitment(case, tampered)
    assert issues and "does not match" in issues[0]


def test_commitment_missing_reference_reported(examples):
    issues = verification.verify_commitment({}, examples["ground-truth.format-example.json"])
    assert issues and "no commitment" in issues[0]


def test_protocol_compatibility_passes_for_examples(examples, ident):
    for filename, document in examples.items():
        issues = verification.verify_protocol_compatibility(document, ident)
        assert issues == [], f"{filename}: {issues}"


def test_protocol_compatibility_detects_version_mismatch(ident):
    document = {"protocol_version": "0.0.1", "schema_version": "0.1.0"}
    issues = verification.verify_protocol_compatibility(document, ident)
    assert any("protocol_version" in issue for issue in issues)


def test_protocol_compatibility_rejects_missing_version(ident):
    document = {"schema_version": "0.1.0"}
    issues = verification.verify_protocol_compatibility(document, ident)
    assert any("missing protocol_version" in issue for issue in issues)


def test_protocol_compatibility_detects_schema_mismatch(ident):
    document = {"protocol_version": "0.1.0", "schema_version": "9.9.9"}
    issues = verification.verify_protocol_compatibility(document, ident)
    assert any("schema_version" in issue for issue in issues)


def test_artifact_hash_verification_passes(repo_root, examples):
    reference = examples["evidence.example.json"]["bundle"]["raw_output"]
    path = repo_root / reference["path"]
    assert verification.verify_artifact_hash(path, reference["sha256"]) == []


def test_artifact_hash_detects_tampering(repo_root, examples, tmp_path):
    reference = examples["evidence.example.json"]["bundle"]["raw_output"]
    tampered = tmp_path / "raw-output.demo.txt"
    tampered.write_text("999\n", encoding="utf-8")
    issues = verification.verify_artifact_hash(tampered, reference["sha256"])
    assert issues and "expected sha256" in issues[0]


def test_artifact_hash_reports_missing_file(repo_root, examples):
    issues = verification.verify_artifact_hash(repo_root / "no-such-file.txt", "0" * 64)
    assert issues and "not found" in issues[0]


def test_manifest_verification_passes_on_example(repo_root, examples):
    manifest = examples["manifest.example.json"]
    file_hashes = {
        entry["path"]: verification.hash_file(repo_root / entry["path"])
        for entry in manifest["entries"]
    }
    assert verification.verify_manifest(manifest, file_hashes) == []


def test_manifest_verification_detects_tampered_artifact(repo_root, examples, tmp_path):
    manifest = examples["manifest.example.json"]
    file_hashes = {
        entry["path"]: verification.hash_file(repo_root / entry["path"])
        for entry in manifest["entries"]
    }
    file_hashes["examples/artifacts/raw-output.demo.txt"] = "0" * 64
    issues = verification.verify_manifest(manifest, file_hashes)
    assert any("raw-output.demo.txt" in issue for issue in issues)


def test_manifest_verification_detects_missing_artifact(repo_root, examples):
    manifest = examples["manifest.example.json"]
    file_hashes = {
        entry["path"]: verification.hash_file(repo_root / entry["path"])
        for entry in manifest["entries"]
    }
    del file_hashes["examples/artifacts/raw-output.demo.txt"]
    issues = verification.verify_manifest(manifest, file_hashes)
    assert any("no hash provided" in issue for issue in issues)


def test_manifest_verification_detects_hash_field_corruption(examples):
    manifest = examples["manifest.example.json"]
    corrupted = set_path(manifest, "manifest_hash", "0" * 64)
    issues = verification.verify_manifest(corrupted, {})
    assert any("manifest_hash" in issue for issue in issues)


def test_manifest_verification_rejects_schema_invalid_manifest():
    issues = verification.verify_manifest({"ecp_object": "manifest"}, {})
    assert issues  # schema-invalid manifests fail before hash semantics


def test_evidence_reference_verification_passes(examples):
    audit = examples["audit.two-auditor.example.json"]
    evidence = examples["evidence.example.json"]
    assert verification.verify_evidence_reference(audit, evidence) == []


def test_evidence_reference_detects_tampering(examples):
    audit = examples["audit.two-auditor.example.json"]
    tampered = set_path(examples["evidence.example.json"], "provenance.notes", ["x"])
    issues = verification.verify_evidence_reference(audit, tampered)
    assert issues and "recomputed" in issues[0]


def test_verification_module_declares_adjudication_boundary():
    source = inspect.getsource(verification)
    assert "adjudication" in source
    assert "not automatically" in source or "NEVER" in source
