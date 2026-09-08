# ECP Architecture

Version 0.1.0-draft (R0 foundation). Normative contract details live in
[spec/ECP-SPEC.md](../spec/ECP-SPEC.md); this document explains the
*shape* of the system.

## 1. Design premise

ECP evaluates AI systems under evidentiary discipline: every claim must
be traceable to versioned, hash-anchored artifacts, and every layer of
the pipeline must be separable from the others. The architecture
therefore optimizes for three properties, in this order:

1. **Separation of concerns** — case ≠ execution ≠ result ≠ evidence;
   public ≠ protected; verification ≠ adjudication; protocol core ≠
   system integration.
2. **Deterministic provenance** — canonical serialization, fixed hash
   rules, manifests; the same inputs always yield the same bytes.
3. **Provider neutrality** — nothing in the core knows anything about
   any specific model, provider, framework, or cloud.

## 2. Layered view

```
┌────────────────────────────────────────────────────────────────┐
│  PUBLIC REPOSITORY (this repository — provenance/distribution) │
│                                                                │
│  spec/          normative protocol specification               │
│  schemas/       machine-validatable object contracts (2020-12) │
│  src/ecp/       reference core:                                │
│      identity       pinned protocol identity                   │
│      canonical       ECP-CANONICAL-JSON-1.0                    │
│      hashing         deterministic sha256 (docs/files/fields)  │
│      manifest        deterministic manifests                   │
│      validate        schema validation                         │
│      verification    integrity checks (NOT adjudication)       │
│      boundaries      public/protected boundary enforcement     │
│      linkage         cross-document provenance linkage         │
│  tools/         ecp_cli.py — identity/validate/hash/manifest/   │
│                 boundary-scan/verify-commitment                │
│  examples/      format illustrations (clearly marked)          │
│  cases/ evaluation/ evidence/ verification/  RESERVED (empty)   │
└────────────────────────────────────────────────────────────────┘
                    no data flows, only contracts
┌────────────────────────────────────────────────────────────────┐
│  PROTECTED STORE (outside this repository — future phase)      │
│  sealed ground truth · hidden cases · scoring commitments ·    │
│  protected evidence · controlled execution metadata            │
└────────────────────────────────────────────────────────────────┘
                    bound by sha256 commitments only
┌────────────────────────────────────────────────────────────────┐
│  INTEGRATION LAYER (outside the core — future phase)           │
│  adapters for concrete systems/models (any provider)           │
└────────────────────────────────────────────────────────────────┘
```

At R0 only the public repository layer exists. The other two layers are
architectural placeholders with contracts (system identity, evidence
references) but no implementation — deliberately.

## 3. Object hierarchy and lifecycle

```
Evaluation ──binds──> System (versioned configuration)
        │              └─ executes > Case (public) ──sealed by──> Ground Truth (protected)
        ├─ freezes ──> Registration (append-only, hash-stamped)
        └─ produces ─> Execution ──bundles──> Evidence ──reviewed by──> Audit ──> Classification
```

Each arrow is a versioned-identifier reference, checkable by
`src/ecp/linkage.py`. The lifecycle statuses (`case_status`,
`evaluation_status`) are explicit and monotone where possible;
`quarantined` and `invalidated` allow removing things from use without
deleting history.

## 4. Deterministic core

Everything the core computes is a pure function of its inputs:

- `canonical_bytes(document)` — byte-identical for equal documents
  regardless of key order, process, or platform;
- `hash_document / hash_file / hash_document_excluding` — sha256 over
  exactly defined byte sequences;
- `build_manifest(...)` — for fixed items, versions and a pinned
  timestamp, a byte-identical manifest.

This determinism is what makes a *commitment* meaningful: the public
case can promise the protected ground truth without seeing it, and a
third party can later recompute the seal.

## 5. Boundary enforcement as code

The public/protected boundary is not a convention — it is executable:

- `schemas/case.schema.json` structurally excludes ground-truth fields
  (`additionalProperties: false` + no expected-answer/derivation keys);
- `src/ecp/boundaries.py` scans the tree and flags any violation
  (reserved-dir contents, ground-truth content outside `examples/`,
  non-illustration ground truth in examples, cases without commitments);
- the test suite runs both on every change.

## 6. Repository topology

| Path | Role | R0 state |
|---|---|---|
| `spec/` | normative specification | complete for foundation |
| `schemas/` | 10 versioned JSON Schemas | complete, tested |
| `src/ecp/` | reference core | complete, tested |
| `tests/` | foundation tests | 229 tests, all passing |
| `tools/` | CLI | complete |
| `examples/` | format illustrations | valid, hashes real |
| `docs/` | architecture/trust/repro/security/open-core/contributing | complete |
| `cases/`, `evaluation/`, `evidence/`, `verification/` | reserved | **empty** (README only) |

## 7. Extension points (future, separately gated)

1. **Case pipeline** — authoring → independent review → leakage/novelty
   gates → registration. The case schema already carries
   `authoring_provenance` (author role, information boundary,
   environment), `difficulty`, `structural_signature`, and
   `proposed_reasoning_family` as optional fields so authored candidates
   have a contract to land in.
2. **Registration authority** — an append-only registry implementing the
   registration contract.
3. **Execution harness** — outside the core; adapters translate the
   system identity contract into concrete invocations.
4. **Protected store** — holds sealed ground truth; publishes
   commitments into public cases.
5. **Verification service** — records verification results into the
   reserved `verification/` area.
6. **Analysis layer** — only after evidence exists.

None of these exist at R0; all have contracts ready.

## 8. What deliberately does not exist

Model adapters, execution machinery, scoring, leaderboards, case data,
ground-truth data, commercial features, and any claim of scientific
validation. The repository is a protocol foundation, and its README
states this in the strongest terms at the top.
