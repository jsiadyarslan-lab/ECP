"""Deterministic hashing for ECP provenance (sha256 only, at R0).

What is hashed, and in what canonical representation — the two questions
spec/ECP-SPEC.md answers normatively:

- A *document hash* (used for ground-truth commitments, evidence references
  and audit references) is SHA-256 over the document's
  ``ECP-CANONICAL-JSON-1.0`` bytes (see :mod:`ecp.canonical`).
- An *artifact/file hash* (used in manifests and evidence bundle refs) is
  SHA-256 over the raw bytes of the file.
- A *self-referential field hash* (``manifest_hash``, ``registration_hash``)
  is SHA-256 over the canonical bytes of the document with exactly one
  top-level field removed (the field that carries the hash itself).

Hashes are lowercase hexadecimal. Having a hash on a file is not integrity
by itself — integrity is a *verification* claim established by recomputation
(see :mod:`ecp.verification`).
"""

import hashlib
from pathlib import Path

SUPPORTED_ALGORITHMS = ("sha256",)


def _algorithm_or_raise(algorithm: str) -> str:
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"unsupported hash algorithm {algorithm!r}; supported: {SUPPORTED_ALGORITHMS}"
        )
    return algorithm


def sha256_hex(data: bytes) -> str:
    """SHA-256 over *data*, as lowercase hex."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("sha256_hex expects bytes")
    return hashlib.sha256(bytes(data)).hexdigest()


def hash_file(path: "str | Path", algorithm: str = "sha256") -> str:
    """SHA-256 over the raw bytes of the file at *path*."""
    _algorithm_or_raise(algorithm)
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def hash_document(document: object, algorithm: str = "sha256") -> str:
    """SHA-256 over the ECP-CANONICAL-JSON-1.0 bytes of *document*."""
    from .canonical import canonical_bytes

    _algorithm_or_raise(algorithm)
    return hashlib.sha256(canonical_bytes(document)).hexdigest()


def hash_document_excluding(
    document: dict, excluded_key: str, algorithm: str = "sha256"
) -> str:
    """SHA-256 over the canonical bytes of *document* with one top-level
    field removed.

    This is the normative rule for self-referential hashes
    (``manifest_hash``, ``registration_hash``): the hash covers every field
    of the document except the field that carries the hash itself. Nested
    occurrences of *excluded_key* are NOT removed — the exclusion is exactly
    one top-level field.
    """
    _algorithm_or_raise(algorithm)
    if not isinstance(document, dict):
        raise TypeError("hash_document_excluding expects a JSON object (dict)")
    stripped = {k: v for k, v in document.items() if k != excluded_key}
    return hash_document(stripped, algorithm=algorithm)
