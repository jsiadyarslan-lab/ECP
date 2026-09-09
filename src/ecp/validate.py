"""Machine-validatable schema access for all ECP foundation objects.

Schemas live in ``<repo>/schemas/`` as JSON Schema (draft 2020-12) and are
validated against the draft 2020-12 meta-schema on first load (a broken
schema fails loudly, not silently). There are no provider-specific schemas
in the scientific core.
"""

import json
from pathlib import Path

import jsonschema

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"

SCHEMA_FILES = {
    "protocol": "protocol.schema.json",
    "system": "system.schema.json",
    "evaluation": "evaluation.schema.json",
    "case": "case.schema.json",
    "ground-truth": "ground-truth.schema.json",
    "registration": "registration.schema.json",
    "execution": "execution.schema.json",
    "evidence": "evidence.schema.json",
    "audit": "audit.schema.json",
    "manifest": "manifest.schema.json",
    # 0.2.0 additive contracts (R1-I, Option C):
    "ledger-entry": "ledger-entry.schema.json",
    "store-manifest": "store-manifest.schema.json",
    # 0.3.0 additive contracts (M3-CA0 case review):
    "case-candidate": "case-candidate.schema.json",
    "case-review": "case-review.schema.json",
    "review-run": "review-run.schema.json",
    "review-adjudication": "review-adjudication.schema.json",
}

_CACHE: dict = {}


def load_schema(name: str) -> dict:
    """Load (and meta-validate) a foundation schema by object name.

    Raises:
        KeyError: for an unknown schema name.
        ValueError: if the file is not a valid draft 2020-12 schema.
    """
    if name not in SCHEMA_FILES:
        raise KeyError(
            f"unknown schema {name!r}; available: {sorted(SCHEMA_FILES)}"
        )
    if name not in _CACHE:
        path = SCHEMA_DIR / SCHEMA_FILES[name]
        with open(path, "r", encoding="utf-8") as fh:
            schema = json.load(fh)
        try:
            jsonschema.Draft202012Validator.check_schema(schema)
        except jsonschema.SchemaError as exc:  # pragma: no cover - guards authoring
            raise ValueError(f"schema {name} is not valid draft 2020-12: {exc.message}")
        _CACHE[name] = schema
    return _CACHE[name]


def validate_document(document: object, schema_name: str) -> "list[str]":
    """Validate *document* against schema *schema_name*.

    Returns:
        A list of human-readable issues (empty list = valid). Each issue is
        ``"<json-pointer-ish path>: <message>"``.
    """
    validator = jsonschema.Draft202012Validator(load_schema(schema_name))
    errors = sorted(
        validator.iter_errors(document), key=lambda e: list(e.absolute_path)
    )
    issues = []
    for error in errors:
        pointer = "/".join(str(part) for part in error.absolute_path) or "<root>"
        issues.append(f"{pointer}: {error.message}")
    return issues


def is_valid(document: object, schema_name: str) -> bool:
    """True iff *document* validates against *schema_name*."""
    return not validate_document(document, schema_name)
