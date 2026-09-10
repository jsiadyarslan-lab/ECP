"""Schema-validity tests: every schema is machine-validatable, every example
validates against its schema, and the identity document is schema-valid."""

import json

import pytest

from ecp.validate import SCHEMA_FILES, load_schema, validate_document
from ecp.versions import SCHEMA_VERSIONS

EXAMPLE_SCHEMA_MAP = [
    ("case.development.example.json", "case"),
    ("ground-truth.format-example.json", "ground-truth"),
    ("system.model-only.example.json", "system"),
    ("system.complete-system.example.json", "system"),
    ("evaluation.example.json", "evaluation"),
    ("registration.example.json", "registration"),
    ("execution.example.json", "execution"),
    ("evidence.example.json", "evidence"),
    ("manifest.example.json", "manifest"),
    ("audit.two-auditor.example.json", "audit"),
    ("audit.single-auditor-fallback.example.json", "audit"),
    ("ledger-entry.example.json", "ledger-entry"),
    ("store-manifest.example.json", "store-manifest"),
    ("case-candidate.example.json", "case-candidate"),
    ("case-review.example.json", "case-review"),
    ("review-run.example.json", "review-run"),
    ("review-adjudication.example.json", "review-adjudication"),
    ("case-amendment.example.json", "case-amendment"),
    ("case-qualification.example.json", "case-qualification"),
    ("qualification-run.example.json", "qualification-run"),
    ("owner-decision-register.example.json", "owner-decision-register"),
    ("case-readiness.example.json", "case-readiness"),
    ("readiness-run.example.json", "readiness-run"),
    ("registration-manifest.example.json", "registration-manifest"),
    ("registration-gate-state.example.json", "registration-gate-state"),
    ("owner-gate-order.example.json", "owner-gate-order"),
    ("registration-package.example.json", "registration-package"),
    ("trust-registration.example.json", "trust-registration"),
    ("registration-amendment.example.json", "registration-amendment"),
    ("lineage-event.example.json", "lineage-event"),
    ("trust-store-manifest.example.json", "trust-store-manifest"),
    ("runtime-observation.example.json", "runtime-observation"),
]


@pytest.mark.parametrize("schema_name", sorted(SCHEMA_FILES))
def test_schema_is_valid_draft_2020_12(schema_name):
    # load_schema meta-validates against the 2020-12 meta-schema (raises on error)
    schema = load_schema(schema_name)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


@pytest.mark.parametrize("schema_name", sorted(SCHEMA_FILES))
def test_schema_declares_stable_id(schema_name):
    schema = load_schema(schema_name)
    # $id pins the contract version: 0.1.0 contracts keep their original
    # $id (files unchanged in the 0.2.0 bundle); 0.2.0 contracts (new
    # object types) carry the 0.2.0 bundle version. The accepted set is
    # the explicit compatibility matrix.
    contract_version = SCHEMA_VERSIONS[schema_name][0]
    assert schema["$id"].startswith(
        f"https://schemas.ecp-protocol.org/{contract_version}/"
    )
    assert schema["$id"].endswith(f"/{SCHEMA_FILES[schema_name]}")


@pytest.mark.parametrize("schema_name", sorted(SCHEMA_FILES))
def test_schema_declares_ecp_object_const(schema_name):
    schema = load_schema(schema_name)
    ecp_object = schema["properties"]["ecp_object"]
    assert "const" in ecp_object
    assert ecp_object["const"] == schema_name


def test_schema_directory_has_no_foreign_schemas(repo_root):
    files = sorted(p.name for p in (repo_root / "schemas").glob("*.schema.json"))
    assert files == sorted(SCHEMA_FILES.values())


@pytest.mark.parametrize("example_file,schema_name", EXAMPLE_SCHEMA_MAP)
def test_example_validates_against_its_schema(repo_root, example_file, schema_name):
    with open(repo_root / "examples" / example_file, encoding="utf-8") as fh:
        document = json.load(fh)
    issues = validate_document(document, schema_name)
    assert issues == [], f"{example_file}: {issues}"


def test_root_identity_document_is_valid(repo_root):
    with open(repo_root / "ECP-IDENTITY.json", encoding="utf-8") as fh:
        document = json.load(fh)
    assert validate_document(document, "protocol") == []


def test_schemas_are_strict_no_additional_properties():
    for schema_name in sorted(SCHEMA_FILES):
        schema = load_schema(schema_name)
        assert schema.get("additionalProperties") is False, schema_name
