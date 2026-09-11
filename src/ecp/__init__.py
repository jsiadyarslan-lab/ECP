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
  M3-CA0 v1);
- registration-readiness engine — 15-point per-case readiness battery,
  owner-decision-register evaluation, population decision, set-class
  designation and the registration-authorization manifest gate
  (:mod:`ecp.readiness`, M3-CA1 v1);
- protected evaluation + registration trust layer — ownership-explicit
  protected store (authoritative / operational / evidence zones),
  Registration Authority, immutable registration records, state /
  reference-truth separation, cryptographic commitments, append-only
  provenance lineage, controlled access seams and full registration
  integrity verification (:mod:`ecp.trust`, M3-RG0).

 It deliberately contains NO model adapters, NO execution machinery, NO scoring
 logic and NO provider-specific code (see spec/ECP-SPEC.md, "Provider neutrality").
 The credential module is an infrastructure boundary only; it does not call
 providers or execute evaluated systems.
"""

__version__ = "0.7.0"

from .canonical import CANONICALIZATION_ID, canonical_bytes, canonical_dumps
from .hashing import (
    SUPPORTED_ALGORITHMS,
    hash_document,
    hash_document_excluding,
    hash_file,
    sha256_hex,
)
from .identity import IDENTITY_FILE, REPO_ROOT, get_identity, load_identity
from .credentials import (
    CredentialGateway,
    CredentialIdentity,
    CredentialError,
    CredentialExpired,
    CredentialNotFound,
    CredentialRevoked,
    CredentialScopeError,
    CredentialStateError,
    EnvironmentSecretStore,
    ExternalSystemAdapter,
    SecretLease,
    SecretRedactionFilter,
    SecretStore,
    redact_secrets,
    safe_exception_message,
)
from .targets import (
    DuplicateProvider,
    DuplicateTarget,
    InvalidTarget,
    ProviderRegistry,
    TargetRegistry,
    UnknownProvider,
    provider_document,
    target_hash,
)
from .adapters import (
    AdapterError,
    AdapterRegistry,
    DuplicateAdapter,
    ResolutionError,
    ResolvedTarget,
    TargetResolver,
    UnknownAdapter,
    adapter_document,
)

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
    "CredentialGateway",
    "CredentialIdentity",
    "CredentialError",
    "CredentialExpired",
    "CredentialNotFound",
    "CredentialRevoked",
    "CredentialScopeError",
    "CredentialStateError",
    "EnvironmentSecretStore",
    "ExternalSystemAdapter",
    "SecretLease",
    "SecretRedactionFilter",
    "SecretStore",
    "redact_secrets",
    "safe_exception_message",
    "DuplicateProvider",
    "DuplicateTarget",
    "InvalidTarget",
    "ProviderRegistry",
    "TargetRegistry",
    "UnknownProvider",
    "provider_document",
    "target_hash",
    "AdapterError",
    "AdapterRegistry",
    "DuplicateAdapter",
    "ResolutionError",
    "ResolvedTarget",
    "TargetResolver",
    "UnknownAdapter",
    "adapter_document",
]
