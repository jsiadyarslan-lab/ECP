# ECP Architecture

Version 0.4.0-draft (M3-CA0-A case qualification & amendment, additive over M3-CA0).
Normative contract details live in
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
│  PUBLIC CONTRACT REPOSITORY (this repository)                  │
│                                                                │
│  spec/          normative protocol specification (§1–§19)      │
│  schemas/       16 machine-validatable contracts (2020-12)     │
│  src/ecp/       reference core:                                │
│      identity       pinned protocol identity                   │
│      canonical       ECP-CANONICAL-JSON-1.0                    │
│      hashing         deterministic sha256 (docs/files/fields)  │
│      manifest        deterministic manifests                   │
│      validate        schema validation                         │
│      versions        explicit 0.1.x↔0.2.x↔0.3.x compatibility │
│      verification    integrity checks (NOT adjudication)       │
│      boundaries      public/protected + ledger-tree scanning   │
│      linkage         cross-document provenance linkage         │
│      store           protected store core (R1-I)              │
│      ledger          registration ledger core (R1-I)          │
│      candidates      case-candidate extraction (M3-CA0)       │
│      review          deterministic review engine (M3-CA0)     │
│  tools/         ecp_cli.py — identity/validate/hash/manifest/   │
│                 boundary-scan/verify-commitment + store-init/  │
│                 seal/verify, ledger-init/register/invalidate/  │
│                 ledger-verify/anchor-publish + review-extract/ │
│                 review-run/review-verify/review-adjudicate     │
│  examples/      format illustrations (clearly marked)          │
│  cases/ evaluation/ evidence/ verification/  RESERVED (empty)   │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│  PUBLIC LEDGER REPOSITORY (separate repo — R1-I, starts EMPTY) │
│  chained entries/ · records/ · ANCHOR.json                     │
│  public verification from public data alone                    │
└────────────────────────────────────────────────────────────────┘
                    the seam: sha256 commitments
┌────────────────────────────────────────────────────────────────┐
│  PROTECTED STORE (outside all repositories — R1-I implemented) │
│  zones/sealed-gt/ CAS write-once blobs (canonical bytes)       │
│  registry manifest (store.json, deterministic)                 │
│  oplog/ hash-chained append-only operation log                 │
│  hidden-cases/ evidence/ exports/  RESERVED (R1-I)             │
└────────────────────────────────────────────────────────────────┘
                    bound by sha256 commitments only
┌────────────────────────────────────────────────────────────────┐
│  INTEGRATION LAYER (outside the core — future phase)           │
│  adapters for concrete systems/models (any provider)           │
└────────────────────────────────────────────────────────────────┘
```

At R1-I the public contract repository, the (empty) public ledger
repository and the protected store machinery exist; the integration layer
remains a placeholder. The store and the ledger form the **coupled seam**
decided in M3-R1 (Option C): the store provides custody (write-once CAS),
the ledger provides the public freeze (chained appends + anchoring), and
the seam — the commitment — is verified in both directions at
registration time and by public verification.

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
| `tests/` | foundation tests | 482 tests, all passing |
| `tools/` | CLI | complete |
| `examples/` | format illustrations | valid, hashes real |
| `docs/` | architecture/trust/repro/security/open-core/contributing | complete |
| `cases/`, `evaluation/`, `evidence/`, `verification/` | reserved | **empty** (README only) |

## 7. Extension points (status after R1-I)

1. **Case pipeline** — authoring → independent review → leakage/novelty
   gates → registration. The case schema already carries
   `authoring_provenance` (author role, information boundary,
   environment), `difficulty`, `structural_signature`, and
   `proposed_reasoning_family` as optional fields so authored candidates
   have a contract to land in. Status: **future gate** (a real-case
   registration is not possible before the review pipeline exists).
2. **Registration authority** — an append-only registry implementing the
   registration contract. Status: **implemented at R1-I** as the CLI
   ceremony + chained file ledger + public verification (`ecp.ledger`);
   the public ledger exists and is empty.
3. **Execution harness** — outside the core; adapters translate the
   system identity contract into concrete invocations. Status: **future
   gate**.
4. **Protected store** — holds sealed ground truth; publishes
   commitments into public cases. Status: **implemented at R1-I**
   (`ecp.store`: CAS write-once, op log, manifest, verification).
5. **Verification service** — records verification results into the
   reserved `verification/` area. Status: **future gate**.
6. **Analysis layer** — only after evidence exists. Status: **future
   gate**.

Contracts are ready for all of them; machinery exists for 1 (review half),
2 and 4.

## 8. What deliberately does not exist

Model adapters, execution machinery, scoring, leaderboards, case data,
ground-truth data, commercial features, and any claim of scientific
validation. The repository is a protocol foundation, and its README
states this in the strongest terms at the top.

## 9. M3-CA0-A extension (adjudication & amendment layer)

Bundle 0.4.0 adds a fifth layer above the review pipeline: the
qualification layer (`src/ecp/adjudication.py`, the `case-amendment`
contract, `amendment-draft`/`amendment-disclose` CLI commands, and the
amendment-aware review engine under the `0.4.0` profile). Data flow:

```
source case-set (immutable) → case-candidate v1 (immutable intake)
        ↓ owner adjudication records (review-adjudication, the seam)
        ↓ case-amendment (STEP 1 draft → STEP 2 separate disclosure)
        ↓ deterministic v2 derivation (pure function, never persisted)
review-run (0.4.0 profile: amendments + lineage; v1 runs preserved)
```

The four-state separation (mechanical review ≠ owner adjudication ≠
case repair/versioning ≠ registration eligibility) is structural: the
amendment layer has no import path to the ledger or the store, and
engine profiles guarantee preserved-run re-verification. Extension
point status: adjudication/amendment IMPLEMENTED (0.4.0); registration
of real cases, GT verification, execution, evidence ingest remain
FUTURE gates.
