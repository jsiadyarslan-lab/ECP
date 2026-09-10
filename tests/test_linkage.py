"""Provenance linkage tests (§24 provenance linkage)."""

import copy

from helpers import set_path

from ecp.linkage import check_linkage


def _document_set(examples):
    return {
        "evaluation": examples["evaluation.example.json"],
        "system": examples["system.complete-system.example.json"],
        "case": examples["case.development.example.json"],
        "registration": examples["registration.example.json"],
        "execution": examples["execution.example.json"],
        "evidence": examples["evidence.example.json"],
        "audit": examples["audit.two-auditor.example.json"],
    }


def test_example_document_set_is_consistent(examples):
    assert check_linkage(_document_set(examples)) == []


def test_execution_system_mismatch_is_flagged(examples):
    documents = _document_set(examples)
    documents["execution"] = set_path(documents["execution"], "system.system_id", "ECP-SYSTEM-OTHER")
    assert check_linkage(documents) != []


def test_execution_case_mismatch_is_flagged(examples):
    documents = _document_set(examples)
    documents["execution"] = set_path(documents["execution"], "case.case_id", "ECP-CASE-DEV-9999")
    assert check_linkage(documents) != []


def test_execution_evaluation_mismatch_is_flagged(examples):
    documents = _document_set(examples)
    documents["execution"] = set_path(documents["execution"], "evaluation_id", "ECP-EVAL-DEMO-9999")
    assert check_linkage(documents) != []


def test_registration_case_mismatch_is_flagged(examples):
    documents = _document_set(examples)
    documents["registration"] = set_path(documents["registration"], "case.case_id", "ECP-CASE-DEV-9999")
    assert check_linkage(documents) != []


def test_evidence_execution_mismatch_is_flagged(examples):
    documents = _document_set(examples)
    documents["evidence"] = set_path(documents["evidence"], "execution_id", "ECP-EXEC-DEMO-9999")
    assert check_linkage(documents) != []


def test_evaluation_system_mismatch_is_flagged(examples):
    documents = _document_set(examples)
    documents["evaluation"] = set_path(documents["evaluation"], "system.system_id", "ECP-SYSTEM-DEMO-RAWMODEL")
    assert check_linkage(documents) != []


def test_case_not_in_case_set_is_flagged(examples):
    documents = _document_set(examples)
    documents["case"] = set_path(documents["case"], "case_id", "ECP-CASE-DEV-0002")
    assert check_linkage(documents) != []


def test_audit_evidence_hash_tamper_is_flagged(examples):
    documents = _document_set(examples)
    documents["evidence"] = set_path(documents["evidence"], "provenance.notes", ["tampered"])
    issues = check_linkage(documents)
    assert any("evidence_reviewed hash" in issue for issue in issues)


def test_audit_missing_evidence_reference_is_flagged(examples):
    documents = _document_set(examples)
    documents["audit"] = set_path(
        documents["audit"],
        "evidence_reviewed",
        [{"evidence_id": "ECP-EVID-DEMO-9999", "evidence_hash": "0" * 64}],
    )
    issues = check_linkage(documents)
    assert any("evidence_reviewed" in issue for issue in issues)


def test_unknown_document_kind_rejected(examples):
    try:
        check_linkage({"model": {}})
        raised = False
    except KeyError:
        raised = True
    assert raised


def test_subset_linkage_runs(examples):
    documents = _document_set(examples)
    subset = {"execution": copy.deepcopy(documents["execution"]), "case": documents["case"]}
    assert check_linkage(subset) == []
