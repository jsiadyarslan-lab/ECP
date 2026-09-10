# Public Provenance Metadata Boundary

This directory contains **public provenance metadata only** for external artifacts and private/local ECP-native work products. It does not contain case artifacts, case bodies, private review material, formal reasoning, expected answers, derivations, sidecars, or qualification inputs.

The public ECP repository is distinct from the private M3 review corpus:

```text
ECP public repository != private M3 review corpus
```

The historical M3 artifact was recovered from JARVIS and remains excluded from ECP. The native M3 corpus is independently authored; its full content, formal layers, candidates, and qualification artifacts are retained in the private protected store `jsiadyarslan-lab/ecp-protected-store`. Public records contain only source identity, integrity hashes, counts, status, immutable artifact IDs, and non-sensitive reproducibility metadata.

## Protected retention boundary

The protected store is a separate **private Git-backed repository**, not `ecp-ledger` and not the public ECP repository. It retains complete M3-native case, provenance, qualification, review, and audit-related artifacts under a write-once versioned contract. Each record has an artifact ID, type, optional case ID, SHA-256, protocol version, provenance, storage class, retention status, version, and registry path.

A protected-store recovery is performed from a fresh private clone. It recomputes every registry hash and confirms the native case IDs and qualification records without using the temporary authoring workspace. Changes are represented by new versions and new hashes; silent overwrite is prohibited.

Qualification, registration, execution, and model calls remain outside the scope of this public metadata boundary.
