"""ECP — Evidentiary Evaluation Protocol: provider-neutral scientific core (R0).

This package implements the repository's scientific core:

- protocol identity (:mod:`ecp.identity`);
- canonical JSON serialization (:mod:`ecp.canonical`);
- deterministic hashing (:mod:`ecp.hashing`);
- manifest construction (:mod:`ecp.manifest`);
- schema validation (:mod:`ecp.validate`);
- verification primitives — integrity only, never scientific adjudication
  (:mod:`ecp.verification`);
- public/protected boundary enforcement (:mod:`ecp.boundaries`);
- cross-document provenance linkage (:mod:`ecp.linkage`).

It deliberately contains NO model adapters, NO execution machinery, NO scoring
logic and NO provider-specific code (see spec/ECP-SPEC.md, "Provider neutrality").
"""

__version__ = "0.1.0"

from .canonical import CANONICALIZATION_ID, canonical_bytes, canonical_dumps
from .hashing import (
    SUPPORTED_ALGORITHMS,
    hash_document,
    hash_document_excluding,
    hash_file,
    sha256_hex,
)
from .identity import IDENTITY_FILE, REPO_ROOT, get_identity, load_identity

__all__ = [
    "__version__",
    "CANONICALIZATION_ID",
    "canonical_bytes",
    "canonical_dumps",
    "SUPPORTED_ALGORITHMS",
    "hash_document",
    "hash_document_excluding",
    "hash_file",
    "sha256_hex",
    "IDENTITY_FILE",
    "REPO_ROOT",
    "get_identity",
    "load_identity",
]
