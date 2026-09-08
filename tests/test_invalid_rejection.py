"""Invalid-object rejection battery (§24 'invalid object rejection').

Every test feeds a deliberately broken document to the validator and
asserts rejection. The controls (valid variants) pin the semantics: e.g.
NOT_ASSESSED is legitimate on any validity, but SUCCESS/FAIL only on VALID.
"""

import pytest

from helpers import del_path, set_path

from ecp.validate import validate_document

pytestmark = pytest.mark.usefixtures("examples")


def _invalid(document, schema_name):
    assert validate_document(document, schema_name) != []


# ---------------------------------------------------------------- case

def test_case_missing_ground_truth_reference(examples):
    _invalid(del_path(examples["case.development.example.json"], "ground_truth_reference"), "case")


def test_case_inline_ground_truth_structurally_impossible(examples):
    _invalid(set_path(examples["case.development.example.json"], "expected_answer", 5), "case")


def test_case_inline_derivation_structurally_impossible(examples):
    _invalid(set_path(examples["case.development.example.json"], "derivation", []), "case")


def test_case_bad_verification_rule_type(examples):
    _invalid(set_path(examples["case.development.example.json"], "verification_rule.rule_type", "magic"), "case")


def test_case_nonsemver_version(examples):
    _invalid(set_path(examples["case.development.example.json"], "case_version", "1.0"), "case")


def test_case_commitment_must_be_sha256_hex(examples):
    _invalid(set_path(examples["case.development.example.json"], "ground_truth_reference.commitment", "deadbeef"), "case")


def test_case_constraints_cannot_be_empty(examples):
    _invalid(set_path(examples["case.development.example.json"], "condition.constraints", []), "case")


def test_case_bad_status(examples):
    _invalid(set_path(examples["case.development.example.json"], "case_status", "live"), "case")


# ---------------------------------------------------------------- system

def test_system_model_only_forbids_configuration(examples):
    base = examples["system.model-only.example.json"]
    complete = examples["system.complete-system.example.json"]
    mixed = dict(base, configuration=complete["configuration"])
    _invalid(mixed, "system")


def test_system_complete_system_requires_configuration(examples):
    _invalid(del_path(examples["system.complete-system.example.json"], "configuration"), "system")


def test_system_complete_system_requires_runtime(examples):
    _invalid(del_path(examples["system.complete-system.example.json"], "runtime"), "system")


def test_system_complete_system_requires_adapter(examples):
    _invalid(del_path(examples["system.complete-system.example.json"], "adapter"), "system")


def test_system_model_name_alone_is_not_identity(examples):
    _invalid(del_path(examples["system.model-only.example.json"], "model.api_version"), "system")


def test_system_model_requires_provider(examples):
    _invalid(del_path(examples["system.model-only.example.json"], "model.provider"), "system")


def test_system_bad_identity_mode(examples):
    _invalid(set_path(examples["system.model-only.example.json"], "identity_mode", "model"), "system")


def test_system_configuration_requires_all_five_components(examples):
    _invalid(del_path(examples["system.complete-system.example.json"], "configuration.retrieval"), "system")


# ---------------------------------------------------------------- evaluation

def test_evaluation_bad_status(examples):
    _invalid(set_path(examples["evaluation.example.json"], "evaluation_status", "running"), "evaluation")


def test_evaluation_system_requires_version(examples):
    _invalid(del_path(examples["evaluation.example.json"], "system.system_version"), "evaluation")


def test_evaluation_bad_case_id_pattern(examples):
    _invalid(set_path(examples["evaluation.example.json"], "case_set.case_ids", ["case-1"]), "evaluation")


# ---------------------------------------------------------------- execution

def test_execution_success_requires_valid(examples):
    doc = set_path(examples["execution.example.json"], "execution_status.validity", "INVALID")
    _invalid(doc, "execution")


def test_execution_fail_requires_valid(examples):
    doc = set_path(examples["execution.example.json"], "execution_status.validity", "INCONCLUSIVE")
    _invalid(doc, "execution")


def test_execution_not_assessed_allowed_on_valid(examples):
    doc = set_path(examples["execution.example.json"], "execution_status.outcome", "NOT_ASSESSED")
    assert validate_document(doc, "execution") == []


def test_execution_not_assessed_allowed_on_invalid(examples):
    doc = set_path(examples["execution.example.json"], "execution_status.validity", "INVALID")
    doc = set_path(doc, "execution_status.outcome", "NOT_ASSESSED")
    assert validate_document(doc, "execution") == []


def test_execution_bad_validity_enum(examples):
    _invalid(set_path(examples["execution.example.json"], "execution_status.validity", "BROKEN"), "execution")


def test_execution_bad_outcome_enum(examples):
    _invalid(set_path(examples["execution.example.json"], "execution_status.outcome", "MAYBE"), "execution")


def test_execution_raw_output_requires_truncated_flag(examples):
    _invalid(del_path(examples["execution.example.json"], "raw_output.truncated"), "execution")


def test_execution_environment_bad_isolation(examples):
    _invalid(set_path(examples["execution.example.json"], "environment.isolation", "airgap"), "execution")


def test_execution_bad_timestamp_format(examples):
    _invalid(set_path(examples["execution.example.json"], "timestamps.submitted_at", "2026-09-09 00:00:02"), "execution")


# ---------------------------------------------------------------- registration

def test_registration_missing_hash(examples):
    _invalid(del_path(examples["registration.example.json"], "registration_hash"), "registration")


def test_registration_hash_must_be_hex64(examples):
    _invalid(set_path(examples["registration.example.json"], "registration_hash", "zzz"), "registration")


def test_registration_missing_immutability(examples):
    _invalid(del_path(examples["registration.example.json"], "immutability"), "registration")


def test_registration_immutability_is_append_only(examples):
    _invalid(set_path(examples["registration.example.json"], "immutability", "editable"), "registration")


def test_registration_bad_canonicalization(examples):
    _invalid(set_path(examples["registration.example.json"], "canonicalization", "JSON-RAW"), "registration")


def test_registration_missing_case(examples):
    _invalid(del_path(examples["registration.example.json"], "case"), "registration")


# ---------------------------------------------------------------- evidence

def test_evidence_post_hoc_correction_forbidden(examples):
    _invalid(set_path(examples["evidence.example.json"], "preservation.post_hoc_correction", True), "evidence")


def test_evidence_raw_output_preserved_required_true(examples):
    _invalid(set_path(examples["evidence.example.json"], "preservation.raw_output_preserved", False), "evidence")


def test_evidence_bundle_requires_model_path_status(examples):
    _invalid(del_path(examples["evidence.example.json"], "bundle.model_path_status"), "evidence")


def test_evidence_artifact_ref_needs_hash(examples):
    doc = set_path(examples["evidence.example.json"], "bundle.raw_output", {"path": "examples/artifacts/raw-output.demo.txt"})
    _invalid(doc, "evidence")


def test_evidence_artifact_ref_hash_must_be_hex64(examples):
    _invalid(set_path(examples["evidence.example.json"], "bundle.raw_output.sha256", "nope"), "evidence")


def test_evidence_not_captured_requires_reason(examples):
    doc = set_path(examples["evidence.example.json"], "bundle.tool_log", {"not_captured": True})
    _invalid(doc, "evidence")


def test_evidence_integrity_requires_manifest_hash(examples):
    _invalid(del_path(examples["evidence.example.json"], "integrity.manifest_hash"), "evidence")


# ---------------------------------------------------------------- audit

def test_audit_two_auditor_mode_requires_two(examples):
    doc = del_path(examples["audit.two-auditor.example.json"], "auditors")
    doc = set_path(doc, "auditors", [examples["audit.two-auditor.example.json"]["auditors"][0]])
    _invalid(doc, "audit")


def test_audit_single_auditor_fallback_requires_declaration(examples):
    _invalid(del_path(examples["audit.single-auditor-fallback.example.json"], "fallback_declaration"), "audit")


def test_audit_fallback_cannot_claim_personal_independence(examples):
    doc = set_path(examples["audit.single-auditor-fallback.example.json"], "fallback_declaration.personal_independence_maintained", True)
    _invalid(doc, "audit")


def test_audit_fallback_allows_at_most_one_auditor(examples):
    doc = examples["audit.single-auditor-fallback.example.json"]
    two = set_path(doc, "auditors", doc["auditors"] + [dict(doc["auditors"][0], auditor_id="auditor-demo-b", role="secondary")])
    _invalid(two, "audit")


def test_audit_disagreement_requires_adjudication(examples):
    doc = set_path(examples["audit.two-auditor.example.json"], "disagreement.present", True)
    _invalid(doc, "audit")


def test_audit_disagreement_requires_description(examples):
    doc = set_path(examples["audit.two-auditor.example.json"], "disagreement.present", True)
    doc["adjudication"] = {"method": "tiebreak", "decided_by": "auditor-demo-a"}
    _invalid(doc, "audit")


def test_audit_bad_mode(examples):
    _invalid(set_path(examples["audit.two-auditor.example.json"], "audit_mode", "one-auditor"), "audit")


def test_audit_auditor_requires_independence(examples):
    _invalid(del_path(examples["audit.two-auditor.example.json"], "auditors"), "audit")
    doc = examples["audit.two-auditor.example.json"]
    stripped = set_path(doc, "auditors", [dict(doc["auditors"][0])])
    del stripped["auditors"][0]["independence"]
    _invalid(stripped, "audit")


def test_audit_evidence_hash_must_be_hex64(examples):
    _invalid(set_path(examples["audit.two-auditor.example.json"], "evidence_reviewed", [{"evidence_id": "ECP-EVID-DEMO-0001", "evidence_hash": "x"}]), "audit")


# ---------------------------------------------------------------- manifest

def test_manifest_missing_canonicalization(examples):
    _invalid(del_path(examples["manifest.example.json"], "canonicalization"), "manifest")


def test_manifest_entries_cannot_be_empty(examples):
    _invalid(set_path(examples["manifest.example.json"], "entries", []), "manifest")


def test_manifest_entry_requires_role(examples):
    doc = set_path(examples["manifest.example.json"], "entries", [{k: v for k, v in examples["manifest.example.json"]["entries"][0].items() if k != "role"}])
    _invalid(doc, "manifest")


def test_manifest_hash_must_be_hex64(examples):
    _invalid(set_path(examples["manifest.example.json"], "manifest_hash", "coffee"), "manifest")


def test_manifest_bad_type(examples):
    _invalid(set_path(examples["manifest.example.json"], "manifest_type", "bag"), "manifest")


# ---------------------------------------------------------------- ground-truth

def test_ground_truth_requires_content_class(examples):
    _invalid(del_path(examples["ground-truth.format-example.json"], "content_class"), "ground-truth")


def test_ground_truth_bad_answer_kind(examples):
    _invalid(set_path(examples["ground-truth.format-example.json"], "expected_answer.answer_kind", "numeric"), "ground-truth")


def test_ground_truth_requires_derivation(examples):
    _invalid(set_path(examples["ground-truth.format-example.json"], "derivation", []), "ground-truth")


def test_ground_truth_step_numbers_start_at_one(examples):
    _invalid(set_path(examples["ground-truth.format-example.json"], "derivation", [{"step": 0, "statement": "x"}]), "ground-truth")


# ---------------------------------------------------------------- protocol

def test_protocol_wrong_name(ident):
    _invalid(dict(ident, protocol_name="OTHER"), "protocol")


def test_protocol_wrong_object(ident):
    _invalid(dict(ident, ecp_object="metadata"), "protocol")


def test_protocol_nonsemver(ident):
    _invalid(dict(ident, schema_version="v1"), "protocol")
