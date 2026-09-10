"""Deterministic manifest construction and verification.

A manifest is an ordered, hashed listing of an artifact set
(``schemas/manifest.schema.json``):

- entries are sorted by path (ascending) — order is part of the hash;
- every entry hash is SHA-256 over the raw bytes of the artifact file;
- ``manifest_hash`` is SHA-256 over the canonical serialization of the
  manifest document minus its own ``manifest_hash`` field.

Determinism: for a fixed artifact set, fixed versions and a pinned
``generated_at`` timestamp, construction is fully deterministic and yields
a byte-identical document (exercised by the test suite).
"""

from .canonical import CANONICALIZATION_ID
from .hashing import hash_document_excluding

MANIFEST_HASH_FIELD = "manifest_hash"


def build_manifest(
    items: "list[dict]",
    *,
    manifest_type: str,
    protocol_version: str,
    schema_version: str,
    generated_at: str,
    note: "str | None" = None,
) -> dict:
    """Build a deterministic manifest document.

    Args:
        items: iterable of ``{"role": str, "path": str, "hash": str}``
            (hash = SHA-256 hex over the artifact's raw file bytes). Order
            of *items* is irrelevant — entries are sorted by path.
        manifest_type: one of the manifest schema enum values.
        protocol_version / schema_version: pinned versions (from the
            repository identity).
        generated_at: ISO-8601 UTC timestamp; pin it for deterministic
            regeneration.

    Returns:
        A manifest document (valid against ``manifest`` schema) including
        its ``manifest_hash``.

    Raises:
        ValueError: on duplicate paths or missing item fields.
    """
    entries = []
    seen = set()
    for item in sorted(items, key=lambda x: x["path"]):
        path = item["path"]
        if path in seen:
            raise ValueError(f"duplicate manifest path: {path}")
        seen.add(path)
        entries.append(
            {
                "role": item["role"],
                "path": path,
                "algorithm": "sha256",
                "hash": item["hash"],
            }
        )
    document = {
        "ecp_object": "manifest",
        "manifest_type": manifest_type,
        "protocol_version": protocol_version,
        "schema_version": schema_version,
        "canonicalization": CANONICALIZATION_ID,
        "hash_algorithm": "sha256",
        "generated_at": generated_at,
        "entries": entries,
        "manifest_hash": "",
    }
    if note is not None:
        document["note"] = note
    document["manifest_hash"] = compute_manifest_hash(document)
    return document


def compute_manifest_hash(manifest: dict) -> str:
    """SHA-256 over the canonical manifest minus its ``manifest_hash`` field."""
    return hash_document_excluding(manifest, MANIFEST_HASH_FIELD)
