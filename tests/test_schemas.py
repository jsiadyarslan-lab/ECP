"""Schema-validity tests: every schema is machine-validatable, every example
validates against its schema, and the identity document is schema-valid."""

import json

import pytest

from ecp.validate import SCHEMA_FILES, load_schema, validate_document

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
]


@pytest.mark.parametrize("schema_name", sorted(SCHEMA_FILES))
def test_schema_is_valid_draft_2020_12(schema_name):
    # load_schema meta-validates against the 2020-12 meta-schema (raises on error)
    schema = load_schema(schema_name)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


@pytest.mark.parametrize("schema_name", sorted(SCHEMA_FILES))
def test_schema_declares_stable_id(schema_name):
    schema = load_schema(schema_name)
    assert schema["$id"].startswith("https://schemas.ecp-protocol.org/0.1.0/")


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
