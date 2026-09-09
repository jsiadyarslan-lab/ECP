# ECP Specification

**Version 0.3.0-draft — M3-CA0 Case Review Pipeline (additive over R1-I)**

Status: normative for the repository foundation at schema bundle 0.3.0.
This document uses RFC 2119-style language (MUST / MUST NOT / SHOULD /
MAY). The repository root `ECP-IDENTITY.json` pins the versions this
specification is normative for:

```
protocol_name      ECP
protocol_title     Evidentiary Evaluation Protocol
protocol_version   0.3.0
protocol_status    draft
schema_version     0.3.0
repository_version 0.3.0
canonicalization   ECP-CANONICAL-JSON-1.0
hash_algorithm     sha256
```

ECP is a protocol for **cross-system evidentiary evaluation** of AI
systems: registered cases, sealed ground truth, versioned system
identity, immutable registration, preserved execution evidence, an
honest two-auditor audit model, cryptographic provenance, and a strict
separation between verification (integrity) and scientific adjudication
(validity). This specification defines the foundation contracts and the
deterministic machinery they rely on.

The 0.2.0 revision (R1-I) was **additive**: it introduced the protected
evidence store (§15), the registration ledger (§16), external anchoring
(§17) and the explicit version-compatibility policy (§18), per the
architecture decision recorded in
`docs/M3-R1-ARCHITECTURE-DECISION.md` (Option C — minimal coupled
foundation). No 0.1.0 contract is modified and no 0.1.x artifact is
reinterpreted (§18).

The 0.3.0 revision (M3-CA0) is likewise **additive**: it introduces the
case review pipeline (§19) — the deterministic pre-registration review
and eligibility gate for candidate cases — with four new review-layer
contracts (`case-candidate`, `case-review`, `review-run`,
`review-adjudication`). No earlier contract is modified and no 0.1.x or
0.2.x artifact is reinterpreted (§18). The review layer is a
**review/eligibility gate ONLY**: it never executes models, never scores,
never registers, and never writes to the public ledger.

---

## 1. Conformance

An artifact or tool **conforms to ECP 0.1.0-draft** when it satisfies the
normative statements of this document and validates against the schema
bundle of `schema_version` 0.1.0 (directory `schemas/`). A tool that
produces artifacts MUST stamp them with the `protocol_version` (and where
defined, `schema_version`) it produced them under; a consumer MUST NOT
apply implicit "current version" semantics when interpreting an artifact.

## 2. Protocol identity and versioning

1. The repository root `ECP-IDENTITY.json` is the single pinned identity
   document; it MUST validate against `schemas/protocol.schema.json`.
2. Identity has four distinct version axes:
   - `protocol_version` — semantics of the protocol itself;
   - `schema_version` — the schema bundle in `schemas/`;
   - `repository_version` — the content release of this repository;
   - the git commit id — exact source provenance of any checkout.
   These MUST NOT be conflated: a schema change requires a
   `schema_version` bump; a protocol-semantics change requires a
   `protocol_version` bump; both may ride on the same commit.
3. Every evaluation artifact (case, registration, execution, evidence,
   audit, manifest) MUST carry `protocol_version`, and where its schema
   defines it, `schema_version`. Artifacts with no version citation are
   non-conforming.
4. `protocol_status: draft` means: the contracts are stable enough to
   build on, but no scientific result may be claimed *from the protocol
   itself* regardless of status — validity comes only from properly
   registered, executed, audited evaluations, none of which exist yet.

## 3. Object hierarchy

```
Evaluation
    └── System
         └── Case
              └── Execution
                   └── Evidence
```

with `Registration` freezing the evaluation/case/target tuple before
execution, and `Audit` reviewing evidence after execution.

1. Each level is a **distinct object with distinct provenance**. A case
   is not an execution; an execution is not a result; a result is not
   evidence. Implementations MUST NOT collapse them into one record.
2. Objects reference each other by **versioned identifiers**
   (`ECP-EVAL-…`, `ECP-SYSTEM-…`, `ECP-CASE-…`, `ECP-REG-…`,
   `ECP-EXEC-…`, `ECP-EVID-…`, `ECP-AUDIT-…`), never by name alone.
3. Cross-document consistency is checkable mechanically
   (`src/ecp/linkage.py`); linkage says nothing about scientific quality.

## 4. Object contracts

The machine-validatable contracts live in `schemas/` (draft 2020-12).
Normative semantics per object:

- **Protocol** — §2 above.
- **System** — a versioned *system configuration*, not a model name.
  `identity_mode` distinguishes:
  - `model-only`: model `{name, provider, model_version, api_version}`
    pinned; a `configuration` block is structurally disallowed;
  - `complete-system`: model + `configuration` (system prompt, agent
    framework, tools, retrieval, external services — all five declared,
    emptiness expressed explicitly) + `runtime` + `adapter`.
  A bare model name MUST NOT be accepted as a complete system identity.
  Provider-specific integration MUST live outside the protocol core.
- **Evaluation** — binds one versioned system to one versioned case set
  under an explicit lifecycle (`defined → registered → in-progress →
  complete → sealed`, or `invalidated`).
- **Case** — the public representation: `case_id`, `case_version`,
  `case_family`, `case_definition`, `input`, `condition`,
  `success_criterion`, `verification_rule` (public rule id/type only),
  `ground_truth_reference` (commitment only), `authoring_provenance`.
  The case schema structurally excludes expected-answer and derivation
  fields (§6).
- **Ground truth (protected format)** — `expected_answer`,
  `derivation` (ordered steps), `verification_rule` (full semantics),
  plus `content_class` (`sealed` or `format-illustration`). Real sealed
  ground truth MUST live outside the public repository (§6).
- **Registration** — freezes protocol version, case version, target
  version, condition, success criterion and verification rule with a
  registration timestamp and `registration_hash` (§7). Registration is
  **append-only**: a correction is a new record that supersedes, never an
  edit.
- **Execution** — one execution of one case by one system: runtime,
  environment (isolation/network declared), verbatim `input`, verbatim
  `raw_output`, model/tool access paths, timestamps, and
  `execution_status`.
- **Evidence** — the bundle for one execution: hashed artifact
  references (raw input/output, trace, tool log, environment, system
  identity), `model_path_status`, an integrity anchor (manifest hash),
  a preservation declaration, provenance, optional classification and
  audit reference.
- **Audit** — `audit_mode` (`two-auditor` default;
  `single-auditor-fallback` allowed only with an explicit declaration
  that personal independence is NOT maintained), auditors with
  per-auditor independence flags, evidence reviewed (by id + canonical
  hash), classification, disagreement, adjudication.
- **Manifest** — a deterministic, path-sorted, hashed listing of an
  artifact set (§7).

## 5. Canonicalization — ECP-CANONICAL-JSON-1.0

All commitments and document hashes are computed over the canonical form:

1. Input is a parsed JSON value (RFC 8259). `NaN` and infinities are
   forbidden.
2. Object keys are sorted by Unicode code point ascending, recursively.
3. Serialization uses no insignificant whitespace; separators are
   exactly `,` and `:`.
4. Strings: minimal escaping; non-ASCII characters appear literally
   (UTF-8, no BOM, no `\uXXXX` folding).
5. Integers: minimal decimal. Floats, if used at all: shortest
   round-trip IEEE 754 double representation. Artifacts that need exact
   cross-language reproducibility SHOULD prefer integers or strings.
6. The canonical form of a document is the UTF-8 encoding of its
   canonical serialization.

The reference implementation is `src/ecp/canonical.py`
(`canonical_bytes`). Implementations MUST reproduce it byte-for-byte;
the test suite pins this behavior, including cross-process determinism.

## 6. Public/protected boundary and ground-truth sealing

1. The public Git repository is a **provenance and distribution layer**,
   not the complete scientific trust boundary.
2. **Public**: specification, schemas, reference implementation, tools,
   documentation, format examples, development cases (clearly marked).
   **Protected (never in the public repository)**: hidden cases, sealed
   ground truth, scoring commitments, protected evidence, private
   evaluations, controlled execution metadata.
3. Sealing procedure for a case:
   a. the protected ground-truth document is serialized canonically
      (§5);
   b. `commitment = sha256(canonical bytes)` is recorded in the public
      case's `ground_truth_reference` together with the algorithm and
      canonicalization identifiers;
   c. the ground-truth values remain in the protected store.
4. The commitment is one-directional: the public case holds the hash;
   the protected document holds no back-pointer that would create
   circular hashing.
5. The boundary is machine-checked (`src/ecp/boundaries.py`, exposed as
   `tools/ecp_cli.py boundary-scan`):
   - reserved directories (`cases/`, `evaluation/`, `evidence/`,
     `verification/`) contain only `README.md` at R0;
   - no `ecp_object: ground-truth` document and no `expected_answer` /
     `derivation` key anywhere in the public tree outside `examples/`;
   - inside `examples/`, ground-truth documents MUST be
     `content_class: format-illustration`;
   - every public case MUST carry a 64-hex commitment.
6. `content_class: sealed` documents MUST NOT ever be committed to this
   repository, under any path.

## 7. Hashing, commitments, and manifests

1. `hash_algorithm` is `sha256` at R0. Hashes are lowercase hex.
2. **Document hash** — sha256 over the document's canonical bytes
   (§5). Used for: ground-truth commitments, audit→evidence references.
3. **Artifact hash** — sha256 over the raw bytes of the artifact file.
   Used in manifests and evidence bundle references.
4. **Self-referential field hashes** — `manifest_hash` and
   `registration_hash` are sha256 over the canonical bytes of the
   document with **exactly one top-level field removed**: the field
   carrying the hash itself. Nested keys of the same name are not
   removed.
5. **Manifests** — entries sorted by path ascending; each entry
   `{role, path, algorithm, hash}`; `manifest_hash` per rule 4. For a
   fixed artifact set, fixed versions and a pinned `generated_at`, the
   manifest document is fully deterministic (byte-identical across
   runs). Path uniqueness within a manifest is required and enforced by
   the builder and verifier.
6. Having a hash on a file is not integrity. Integrity is established
   only by **recomputation and comparison** (§8).

## 8. Verification vs. scientific adjudication

1. **Verification** (integrity): artifact identity, manifest integrity,
   case/execution identity, evidence integrity, protocol-version
   compatibility. Reference: `src/ecp/verification.py`.
2. **Scientific adjudication** (validity): whether a result is
   *correct*, whether an execution measured what it claims, whether a
   case was well authorized. This belongs to the audit/classification
   layer under independent auditors — it does not exist in code at R0.
3. A cryptographically intact result is **not** automatically a
   scientifically valid result. Tools MUST NOT present verification
   outcomes as scientific judgments.

## 9. Execution validity vs. task outcome

1. `execution_status.validity` ∈ {`VALID`, `INVALID`, `INCONCLUSIVE`} —
   whether a faithful, interpretable execution occurred.
2. `execution_status.outcome` ∈ {`SUCCESS`, `FAIL`, `NOT_ASSESSED`} —
   the task result.
3. `SUCCESS`/`FAIL` are expressible **only** on `VALID` executions
   (schema-enforced). `NOT_ASSESSED` marks pending or non-assessable
   outcomes and is legal with any validity.
4. Raw output MUST be preserved verbatim; post-hoc correction is
   forbidden (schema-level `preservation` declaration + evidence
   integrity recomputation).

## 10. Audit independence model

1. Default mode is `two-auditor`: two auditors with per-auditor
   independence declarations (procedural, personal, optionally
   organizational).
2. A `single-auditor-fallback` is permitted but MUST declare
   `personal_independence_maintained: false` with a justification; it
   MUST NOT be labeled or presented as personally independent.
3. Disagreement is recorded, and adjudication is required when
   disagreement is present.

## 11. Reproducibility classes

`Reproducible`, `Re-runnable`, `Auditable`, and `Publicly inspectable`
are distinct claims (definitions and the minimum artifact set:
`docs/REPRODUCIBILITY.md`). Tools and documents MUST NOT use them
interchangeably.

## 12. Provider neutrality

The scientific core (schemas, canonicalization, hashing, manifests,
verification, boundaries, linkage) MUST NOT assume any model, provider,
API, agent framework, cloud, or specific evaluated system. Integrations
with concrete systems live outside the core and are future work under
separate authorization.

## 13. Scope boundary (R0 → R1-I → M3-CA0)

R0 provided the foundation only. R1-I (0.2.0) added the protected store
(§15), the registration ledger (§16), anchoring (§17) and the version
compatibility policy (§18) — infrastructure only, per the M3-R1
architecture decision. M3-CA0 (0.3.0) added the case review pipeline
(§19) — the deterministic review/eligibility gate for candidate cases. The following still do not exist and MUST NOT be
claimed: model adapters, benchmark execution, external model calls,
scientific case generation, case registration as a scientific experiment,
scoring, hidden benchmark publication, commercial features, and M3
validation. Anything beyond the implemented foundation is a future gate,
recorded explicitly — never silently implemented. In particular: the
public ledger contains ZERO registrations, no case is registered, and no
evaluation has been executed.

## 14. Change policy

Changes to canonicalization, hashing, sealing, or any schema require a
version bump (`schema_version` and/or `protocol_version`) and updated
tests. Canonicalization and hashing rules are stability-critical: any
change to them invalidates every existing commitment by definition, and
MUST be treated as a protocol major-version event.

---

## 15. Protected Evidence Store (0.2.0 / R1-I)

The protected store is the **custody half** of the coupled seam: it holds
sealed ground truth outside the public repository, in content-addressed,
write-once storage, under an append-only operation log.

1. **Location.** The store lives OUTSIDE the public Git repository (its
   root is an operator parameter). Nothing in the store is ever committed
   to the public repository or to the public ledger repository. A store
   with `scope: development` holds only synthetic, clearly-marked
   fixtures and MUST NOT be treated as scientific evidence (mirroring the
   dev/public ledger separation, §16.6).
2. **Content addressing.** Sealed ground truth is stored as exactly its
   `ECP-CANONICAL-JSON-1.0` bytes at
   `zones/sealed-gt/<sha256[:2]>/<sha256>.json`, where the path hash IS
   the commitment (§6.3). The storage path is a function of content:
   "modifying" a blob produces a different path, leaving the original
   bytes in place.
3. **Write-once.** There is exactly one seal per `(case_id, case_version)`.
   Sealing identical content again is idempotent (and op-logged as such);
   sealing different content for an existing target MUST be rejected, and
   the rejected attempt MUST be recorded in the operation log.
4. **Operation log.** Every store operation (init, seal, idempotent seal,
   rejected seal) is appended to a hash-chained log
   (`oplog/NNNNNNNN.json`): each entry carries the previous entry's hash,
   and its own `oplog_hash` follows the self-referential rule of §7.4.
   The oplog head MAY be checkpointed into the ledger anchoring (§17).
5. **Manifest.** `store.json` (contract: `store-manifest`, 0.2.0) is a
   deterministic, derived index of seals + oplog head with a
   `manifest_hash` (§7.4 rule). For a fixed operation sequence and pinned
   timestamps it is byte-identical across runs. It is a derived index,
   never a trust anchor: integrity is established by recomputation
   (`store-verify`).
6. **Atomic writes.** All writes are two-phase (temp file + atomic
   rename). A crashed operation leaves either no trace or a complete
   record, never a partial write.
7. **Verification.** `store-verify` recomputes: manifest schema + hash;
   the oplog chain; the seal index rebuilt from the oplog; every blob's
   file hash, canonical form, ground-truth contract validity and
   `content_class: sealed`; zone layout (reserved zones README-only,
   sealed-gt CAS-pattern only, no orphan blobs); and — when public cases
   are supplied — the case↔seal commitment equality. A seal with no
   public case document is legitimate (hidden cases).
8. **No execution read path.** No store operation serves ground-truth
   content to an execution context. The only readers are the registration
   ceremony (opaque bytes, commitment recomputation) and — at a future
   gate — adjudication-time audit under disclosure control.

## 16. Registration Ledger (0.2.0 / R1-I)

The ledger is the **authority half** of the coupled seam: an append-only,
hash-chained, plain-file record of registration freezes. The Registration
Authority is a procedure + tooling + public verification — NOT a service
(cloud, daemon and database realizations were examined and rejected in
the architecture decision record).

1. **Structure.** A ledger repository contains `entries/NNNNNNNN.json`
   (chained entries, contract `ledger-entry` 0.2.0),
   `records/ECP-REG-….json` (full registration records, stored as
   canonical bytes) and `ANCHOR.json` (the published chain checkpoint).
2. **Chain.** `entry_hash` follows §7.4 and covers the entry including
   `prev_entry_hash` (genesis: 64 zeros at index 1). Inserting, removing,
   reordering or editing any historical entry breaks every subsequent
   entry. Canonical order is the chain position; `claimed_at` is an
   assertion, not evidence (§17).
3. **Registration ceremony.** `register` MUST, before any append:
   validate the public case (schema, versions, registrable status, sealed
   commitment); verify the store seal exists for the exact
   `(case_id, case_version)` and that its commitment equals the public
   case's commitment (the seam check); validate the system identity;
   reject duplicates (at most one LIVE registration per frozen tuple of
   evaluation, case version, system version and condition hash); assign
   the `registration_id` itself (registrar-controlled, monotone, never
   author-chosen); copy the frozen fields from the case into the record
   (frozen copies, not pointers); compute `registration_hash`; append the
   chained entry with the frozen ground-truth commitments recorded ON the
   entry. A rejection MUST leave the ledger untouched.
4. **Append-only semantics.** Records and entries are never edited or
   removed. A correction is a new record with `supersedes`. An
   invalidation is an explicit entry of kind `invalidation` referencing
   the invalidated record with a reason. A registration is LIVE until
   superseded or invalidated; double invalidation and duplicate
   supersession MUST be rejected.
5. **Public verification.** `ledger-verify` recomputes, from public data
   alone: the chain; every record's document hash and internal
   `registration_hash`; the duplicate rules; the supersession graph; the
   anchor consistency; and — when public cases are supplied — the frozen
   commitments against the public case commitments. Protected content is
   never required for public verification.
6. **Clean state / dev separation.** The public ledger begins EMPTY
   (genesis anchor, zero entries). Development ledgers are initialized
   identically but MUST NOT be published, MUST NOT be confused with the
   public ledger, and MUST NOT become scientific evidence.

## 17. Anchoring (0.2.0 / R1-I)

1. **Mechanism.** `anchor-publish` verifies the chain, then atomically
   writes `ANCHOR.json` = `{ledger_id, entry_count, head_entry_hash,
   anchored_at}`. The operator then commits and pushes the ledger
   repository (one commit per anchor; historical anchors are never
   rewritten — past anchor states are preserved by the Git history, and
   force-push is forbidden). The public host's push event is the
   independent time evidence backing the claimed timestamps.
2. **Anchor verification.** `ledger-verify` checks that the anchored head
   matches the chain at the recorded `entry_count`. Entries beyond the
   anchor are an unanchored tail (reported, not failed); at current scale
   the policy is per-registration anchoring to minimize the tail window.
3. **Prohibitions.** No continuous cloud service, no blockchain/external
   consensus, no over-engineering: a hash chain + public Git anchoring is
   the approved mechanism (decision rule: no forced commercial provider).

## 18. Version compatibility (0.1.x → 0.2.0 → 0.3.0)

1. The 0.2.0 and 0.3.0 schema bundles are **additive**: the ten 0.1.0
   contract files are unchanged; 0.2.0 added two contracts
   (`ledger-entry`, `store-manifest`); 0.3.0 adds four review-layer
   contracts (`case-candidate`, `case-review`, `review-run`,
   `review-adjudication`). The protocol version advances because each
   revision adds normative mechanisms.
2. Compatibility is an explicit, machine-checkable matrix
   (`ecp.versions`): every object type defined at 0.1.0 accepts
   `schema_version` in {`0.1.0`, `0.2.0`, `0.3.0`} (the contract content
   is identical); object types introduced at 0.2.0 accept {`0.2.0`,
   `0.3.0`}; object types introduced at 0.3.0 accept only `0.3.0`;
   `protocol_version` in {`0.1.0`, `0.2.0`, `0.3.0`} is valid for every
   artifact.
3. 0.1.x and 0.2.x artifacts MUST NOT be silently reinterpreted and MUST
   NOT be invalidated by a bundle bump. The R0 examples (0.1.0
   citations) and R1-I examples (0.2.0 citations) remain valid
   artifacts — this is pinned by tests.
4. Anything outside the matrix is a compatibility violation reported as
   an issue by the verification tooling.

---

## 19. Case Review Pipeline (0.3.0 / M3-CA0)

The case review pipeline is the **deterministic pre-registration review
and eligibility gate** for candidate cases. It answers, per candidate:
"is this candidate sufficiently specified, provenance-traceable,
novelty-safe, leakage-safe, and reproducible enough to become
registration-eligible?" — and it produces a review decision, NEVER an
experimental result. This section is normative for the 0.3.0 review-layer
contracts.

### 19.1 Position and boundary

The pipeline sits BEFORE the registration ceremony in the case
lifecycle:

```
candidate source document
   → extraction (case-candidate records)
   → deterministic review (case-review artifacts)
   → eligibility decision (three states)
   → registration-ready representation (§10 boundary: STOP)
   → [registration — separate authorization, NOT this layer]
```

The review layer MUST NOT execute models, call providers, score
benchmarks, collect results, perform statistical analysis, register
cases, or write to the public ledger. There is no code path from
`ecp.review` or `ecp.candidates` to `ecp.ledger` or `ecp.store` — this
is pinned by tests (import-graph checks) and by construction.

### 19.2 Candidate intake (`case-candidate`)

Candidates enter as source documents in the M3-CA0 case-set format
(`M3-CA0-case-set-md-1`), extracted by `ecp.candidates` into canonical
`case-candidate` records (schema 0.3.0). Extraction is faithful and
total:

1. **Coverage check.** Every line of the source document MUST be
   accounted for (case blocks, separators, fences, tail sections). A
   coverage failure aborts extraction loudly — content is never
   silently dropped.
2. **Anomaly retention.** Authored anomalies (multiple
   `INTENDED_CORRECT_ANSWER` / `DERIVATION` blocks, unknown labels,
   non-numbered premise lines) are retained verbatim and recorded; the
   extractor never reconciles, repairs, or drops them. Resolution is a
   human act.
3. **Provenance sidecar.** Author, provider, acquisition path,
   transformation history and honest NOT-AVAILABLE fields are supplied
   by the operator as a provenance sidecar (transcribed from the source
   report); the extractor never invents provenance. The sidecar's
   acquisition hash MUST match the actual source document or extraction
   fails.
4. **Identity.** `candidate_id` is assigned deterministically by intake
   order (`ECP-CAND-NNNNNN`); `content_hash` is the SHA-256 over the
   canonical `content` object. The review layer MUST NOT assign
   `ECP-CASE-*` or `ECP-REG-*` identities (machine-checked by the
   review-area boundary scan).
5. **Class.** Real review material carries `content_class: review` and
   lives only in a private/local review area; public illustrations
   carry `content_class: format-illustration` and live only under
   `examples/`. The engine refuses illustration inputs.

### 19.3 Review dimensions

The engine (`ecp.review`, `ECP-REVIEW-ENGINE-1`) evaluates, per
candidate: **R1 identity** (content-hash recomputation), **R2
provenance** (declared completeness, NOT-AVAILABLE fields, source-report
flags), **R3 specification completeness** (authored content present;
conflicting or duplicated ground-truth blocks flagged, never reconciled;
registration-contract fields — constraints, success criterion,
verification rule — MUST be authored, never inferred), **R4 novelty**
(within-set exact/canonical/source/signature/overlap detection plus the
honest external status `NOT_ESTABLISHABLE_MECHANICALLY`), **R5 leakage**
(detectors: answer-in-task, eval-material-in-task, real-world entities
[registry-driven, small, honest], known benchmark/puzzle patterns,
metadata labels; confirmed answer/eval leaks are disqualifying), **R6
provenance integrity** (candidate → source → transformation → canonical
artifact recomputed byte-exactly against the retained source document),
**R7 reproducibility** (the artifact embeds the candidate content so
another operator can reconstruct the definition from retained review
artifacts alone).

### 19.4 The three-state decision model

Every candidate terminates in exactly one of: **ELIGIBLE** (all
mandatory gates pass and no unresolved critical issue exists),
**REJECTED** (a disqualifying condition is positively established), or
**REQUIRES_REVIEW** (an important condition cannot be resolved
mechanically). There is NO fourth state: ambiguous decision inputs
(out-of-enum check results) abort the run loudly
(`InvalidReviewState`) — "probably eligible", "looks fine" and
"pending" do not exist. No candidate is silently discarded and no
candidate is silently upgraded.

### 19.5 The human review seam (`review-adjudication`)

Important conditions that cannot be resolved mechanically are recorded
as **open questions** (with evidence and a proposed disposition) inside
every review artifact. Owner decisions enter ONLY through explicit
`review-adjudication` records — the engine never fabricates, infers, or
defaults an owner decision. Adjudication dispositions:
`RESOLVE-CLEAN` (resolved; no longer blocks), `ACCEPT-RISK` (owner
explicitly accepts the recorded risk), `CONFIRM-DEFECT` (the finding is
confirmed as disqualifying — the candidate is mechanically REJECTED),
`UPHOLD-OPEN` (explicitly kept open). When several adjudications match
one question, the latest (by `at`, ties by id) applies and every
matched id is recorded (override semantics, never silent).

### 19.6 Determinism and verification

The review is a pure function of its explicit inputs (candidates,
source text, adjudications, run id, reviewer, `reviewed_at` timestamp —
no wall clock, no randomness, no network, no subprocess). Artifacts are
hash-chained per run (`prev_artifact_hash` / `artifact_hash`); the run
manifest (`review-run`) records the retained inputs, engine parameters,
decision tally, artifact chain and a self-referential `run_hash`.
`review-verify` recomputes every hash, the chain, the manifest
cross-references AND re-derives the entire run from the retained inputs,
requiring byte-identical artifact hashes (a determinism violation is a
verification failure).

### 19.7 Review-area boundary

Review material lives in a private/local review area with a fixed
layout (`candidates/`, `reviews/`, `adjudications/`, `source/`,
`review-run.json`, ops files). The boundary scanner
(`boundary-scan --review-root`) enforces: expected locations only;
per-type object placement; no foreign ECP object types (ledger,
registration, case, system, execution, evaluation, evidence, audit,
ground-truth, store objects do not belong here); no `ECP-CASE-` /
`ECP-REG-` identity strings anywhere (the review layer never fabricates
registration-layer identities); JSON parseability and schema validity.

### 19.8 Output boundary (STOP)

For ELIGIBLE candidates the pipeline MAY produce a
`registration_ready` block: a field mapping and an explicit
`STOP-BEFORE-REGISTRATION` marker. This is a representation, NOT a
registration: no ECP-CASE id is assigned, no ground truth is sealed, no
ledger append occurs. Crossing into registration, execution or results
requires separate owner authorization — the review layer ends here.
