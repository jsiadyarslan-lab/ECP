"""Protocol identity: single pinned source of protocol/schema/repository versions.

The identity document lives at the repository root (``ECP-IDENTITY.json``)
and is validated against ``schemas/protocol.schema.json`` on load. There is
no implicit "current version" anywhere: every artifact must cite versions
explicitly, and the tooling compares them against this identity
(see :func:`ecp.verification.verify_protocol_compatibility`).

Resolution note (R0): the identity file is resolved relative to this file's
location (``<repo>/src/ecp/identity.py`` -> ``<repo>/ECP-IDENTITY.json``),
i.e. repository-root-relative. R0 usage is repository checkout based.
"""

import json
from pathlib import Path

from .validate import validate_document

REPO_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_FILE = REPO_ROOT / "ECP-IDENTITY.json"


def load_identity(repo_root: "str | Path | None" = None) -> dict:
    """Load and schema-validate the protocol identity document.

    Args:
        repo_root: optional repository root; defaults to this checkout.

    Returns:
        The identity document (dict).

    Raises:
        FileNotFoundError: if ``ECP-IDENTITY.json`` is absent.
        ValueError: if the document does not validate against the protocol
            schema.
    """
    path = Path(repo_root) / "ECP-IDENTITY.json" if repo_root else IDENTITY_FILE
    with open(path, "r", encoding="utf-8") as fh:
        document = json.load(fh)
    issues = validate_document(document, "protocol")
    if issues:
        raise ValueError(
            "ECP-IDENTITY.json failed protocol schema validation:\n  - "
            + "\n  - ".join(issues)
        )
    return document


def get_identity() -> dict:
    """Convenience alias for :func:`load_identity`."""
    return load_identity()


def protocol_version() -> str:
    return load_identity()["protocol_version"]


def schema_version() -> str:
    return load_identity()["schema_version"]


def repository_version() -> str:
    return load_identity()["repository_version"]
