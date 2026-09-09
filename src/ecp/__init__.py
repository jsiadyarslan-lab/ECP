"""ECP — Evidentiary Evaluation Protocol: provider-neutral scientific core.

This package implements the repository's scientific core:

- protocol identity (:mod:`ecp.identity`);
- canonical JSON serialization (:mod:`ecp.canonical`);
- deterministic hashing (:mod:`ecp.hashing`);
- manifest construction (:mod:`ecp.manifest`);
- schema validation (:mod:`ecp.validate`);
- explicit protocol/schema version compatibility (:mod:`ecp.versions`);
- verification primitives — integrity only, never scientific adjudication
  (:mod:`ecp.verification`);
- public/protected boundary enforcement (:mod:`ecp.boundaries`);
- cross-document provenance linkage (:mod:`ecp.linkage`);
- protected evidence store — CAS write-once custody (:mod:`ecp.store`);
- registration ledger — append-only hash-chained authority
  (:mod:`ecp.ledger`);
- case-candidate extraction — faithful, coverage-checked intake
  (:mod:`ecp.candidates`, M3-CA0); authored case-set intake for the
  structured format 2 (:mod:`ecp.authoring`, M3-CA0 v1);
- case review engine — deterministic three-state eligibility gate
  (:mod:`ecp.review`, M3-CA0);
- case qualification engine — deterministic four-state authoring-layer
  gate with mechanical ground-truth verification (:mod:`ecp.qualification`,
  M3-CA0 v1).

It deliberately contains NO model adapters, NO execution machinery, NO scoring
logic and NO provider-specific code (see spec/ECP-SPEC.md, "Provider neutrality").
"""

__version__ = "0.5.0"

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
