# ECP Specification

**Version 0.4.0-draft — M3-CA0-A Case Qualification & Amendment (additive over M3-CA0)**

Status: normative for the repository foundation at schema bundle 0.4.0.
This document uses RFC 2119-style language (MUST / MUST NOT / SHOULD /
MAY). The repository root `ECP-IDENTITY.json` pins the versions this
specification is normative for:

```
protocol_name      ECP
protocol_title     Evidentiary Evaluation Protocol
protocol_version   0.4.0
protocol_status    draft
schema_version     0.4.0
repository_version 0.4.0
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

## 13. Scope boundary (R0 → R1-I → M3-CA0 → M3-CA0-A)

R0 provided the foundation only. R1-I (0.2.0) added the protected store
(§15), the registration ledger (§16), anchoring (§17) and the version
compatibility policy (§18) — infrastructure only, per the M3-R1
architecture decision. M3-CA0 (0.3.0) added the case review pipeline
(§19) — the deterministic review/eligibility gate for candidate cases.
M3-CA0-A (0.4.0) added the owner-adjudication and case-amendment layer
(§20): explicit owner decision records, versioned case amendments with
the two-phase representation-bias disclosure, and amendment re-review —
the qualification seam between mechanical review and registration. The following still do not exist and MUST NOT be
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

## 18. Version compatibility (0.1.x → 0.2.0 → 0.3.0 → 0.4.0)

1. The 0.2.0, 0.3.0 and 0.4.0 schema bundles are **additive**: the ten
   0.1.0 contract files are unchanged; 0.2.0 added two contracts
   (`ledger-entry`, `store-manifest`); 0.3.0 added four review-layer
   contracts (`case-candidate`, `case-review`, `review-run`,
   `review-adjudication`); 0.4.0 adds one adjudication-layer contract
   (`case-amendment`) and extends the 0.3.0 review contracts with
   OPTIONAL fields only (`case_version`/`amendment` on case-candidate,
   `amendment` linkage on case-review, `amendments`/`lineage` on
   review-run). The protocol version advances because each revision
   adds normative mechanisms.
2. Compatibility is an explicit, machine-checkable matrix
   (`ecp.versions`): every object type defined at 0.1.0 accepts
   `schema_version` in {`0.1.0`, `0.2.0`, `0.3.0`, `0.4.0`} (the
   contract content is identical); object types introduced at 0.2.0
   accept {`0.2.0`, `0.3.0`, `0.4.0`}; object types introduced at
   0.3.0 accept {`0.3.0`, `0.4.0`} (0.4.0 extensions are optional
   fields); object types introduced at 0.4.0 accept only `0.4.0`;
   `protocol_version` in {`0.1.0`, `0.2.0`, `0.3.0`, `0.4.0`} is valid
   for every artifact.
3. 0.1.x, 0.2.x and 0.3.x artifacts MUST NOT be silently reinterpreted
   and MUST NOT be invalidated by a bundle bump. The R0 examples (0.1.0
   citations), R1-I examples (0.2.0 citations) and CA0 review artifacts
   (0.3.0 citations) remain valid artifacts — this is pinned by tests,
   including byte-identical re-derivation of 0.3.0-era review runs under
   the 0.4.0 engine via the recorded engine profile.
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

---

## 20. Case Qualification: Adjudication & Amendment (0.4.0 / M3-CA0-A)

M3-CA0-A adds the layer between mechanical review and registration:
**owner adjudication of open questions** and **versioned case
amendment** of documented authoring defects. Four concepts remain
strictly separate: CA0 mechanical review ≠ owner adjudication ≠ case
repair/versioning ≠ registration eligibility. An owner decision is
never directly converted into a registration.

### 20.1 Owner adjudication records

Open questions surfaced by CA0 are resolved only by explicit
`review-adjudication` records (§19.5) carrying the decision basis, the
rationale and (when scoped) the target candidate. The executor applies
the owner's WRITTEN rules from an execution order to preserved evidence
and records the application — never an invented decision. Questions
that cannot be resolved from preserved evidence stay open
(`owner_decision: null`); guessing is forbidden. The 0.4.0 engine
surfaces two additional adjudicable question classes with observed
triggers from the CA0 real run: `OQ-SPEC-GT-CONFLICT` (the authored GT
document carries multiple/conflicting blocks — emitted when
SPEC-AMBIGUOUS-GT / SPEC-DUPLICATE-GT findings exist) and
`OQ-SPEC-AUTHORING` (registration-contract fields not authored —
emitted when SPEC-REG-AUTHORING-MISSING findings exist). A
`CONFIRM-DEFECT` disposition on `OQ-SPEC-GT-CONFLICT` produces a
mechanical REJECTED with the adjudication cited in the artifact: the
"REJECT — SPECIFICATION DEFECT" path flows through the engine, never
by hand.

### 20.2 Case versioning and the amendment record

A legitimate correction of a documented authoring defect is a
**versioned case amendment** (`case-amendment` contract): the prior
candidate version is immutable; the amendment record is the only
representation of the change; the derived v2 view exists only inside a
review run that applies the amendment. The record MUST carry: the
exact defect and why it is a defect; the exact, mechanically applicable
change (GT-document consolidation: retained/removed source blocks);
the reason the change is not outcome-dependent; the new canonical
content hash; new provenance (amendment author, drafted-at, order
reference); and whether novelty/leakage review must be repeated.
Outcome-dependent selection is forbidden: no expected performance,
anticipated difficulty, expected statistical effect, or any future
execution result may influence qualification.

### 20.3 Two-phase representation-bias disclosure (amendment level)

Every case amendment MUST record a representation-bias disclosure
(`NONE` / `POSSIBLE` / `KNOWN`) that is completed **AFTER the amendment
has been drafted, in a separate step**, never concurrently with
authoring. This is enforced mechanically: the drafting step has no
disclosure parameter at all; the disclosure step operates only on an
existing PENDING draft; and the record carries TWO hashes —
`draft_hash` (over the disclosure-free draft) and `amendment_hash`
(over the completed record) — so a one-step forgery cannot reproduce
the structure. The disclosure addresses whether the amendment author
had knowledge of the evaluated system's internal representation,
architecture, reasoning behavior, implementation constraints or other
system-specific characteristics that could have influenced the
amendment's constraints, success criteria, verification rules, wording,
difficulty, expected outcome, or acceptance boundary. The disclosure is
an audit/provenance field, NEVER an eligibility decision: `NONE` is not
a self-certification of bias absence; `POSSIBLE`/`KNOWN` amendments
remain fully usable but MUST remain traceable to the disclosure — every
review artifact applying the amendment carries the disclosure value,
and it is never silently treated as unbiased.

### 20.4 Amendment application and re-review

Applying an amendment is a deterministic, pure derivation: v2 content
= consolidation of v1 content per the record's change; the v1 record
and the source document are never modified; the v2 candidate carries
`case_version` and an `amendment` linkage block; the provenance
transformation history gains the amendment event. A material amendment
MUST NOT inherit review state: the amended candidate re-enters the
FULL review (identity, provenance, specification completeness,
novelty, leakage, duplication, reproducibility) in a new run, and both
the original review and the post-amendment review are preserved (the
run manifest records the prior run via the `lineage` block). A PENDING
amendment (disclosure not yet completed) is refused loudly by the
review pipeline; a stale, mis-targeted or tampered amendment aborts the
run.

### 20.5 Engine profiles and preserved-run re-verification

The review engine records its version on every artifact and manifest.
A run produced by an earlier engine version MUST remain byte-identically
re-derivable by the current toolchain: `review-verify` re-derives under
the engine profile the stored run cites. Profile `0.3.0` reproduces the
exact M3-CA0 question set and refuses amendments; profile `0.4.0` adds
the adjudication-layer questions and the amendment machinery. There is
no silent reinterpretation of preserved runs.

### 20.6 Qualification output boundary (STOP)

The qualification layer establishes which candidates, if any, are
registration-ready. It MUST STOP before: ECP registration, public
ledger append, ground-truth publication, model execution, evidence
collection, scoring, and statistics — even for candidates that become
ELIGIBLE. Registration remains a separately authorized stage with its
own ceremony (§16).

## 21. Case Authoring + Qualification Layer (0.5.0 / M3-CA0 v1)

The M3-CA0 v1 layer sits BEFORE registration and AFTER (or alongside) the
§19 review pipeline: it authors a candidate population under the frozen G0
scientific design and qualifies it with a deterministic four-state gate.
It executes no model, registers nothing, and leaves the ledger untouched.

### 21.1 Authored case-set intake (format 2)

Authored candidate material arrives as a case-set document in format
`M3-CA0V1-case-set-md-2` (the structured extension of the §19.2 format):
per-case sections for the family, structural signature, numbered premises,
question, expected property, intended answer, derivation, ground-truth class
and statement (with an optional ambiguity note for designed-indeterminate
cases), forbidden shortcuts, a fenced machine-checkable FORMAL layer, risk
notes, representation-bias disclosure (order §9 sub-keys), environmental
pre-check (order §10 sub-keys) and self-review; tail blocks carry the
authoring provenance (order §3) and the case-set summary (pool design).

`authoring-intake` (src/ecp/authoring.py) parses this format with the same
guarantees as §19.2: line-complete coverage accounting (nothing silently
dropped), verbatim `raw_block` retention including fence lines, loud
failure on malformed FORMAL JSON, provenance sidecar acquisition-hash
binding, and byte-identical re-extraction. The sidecar additionally carries
the §3 authoring-independence record (author identity, environment,
model/tool, prompt/instructions with hash, information available and
explicitly unavailable, relationships to ECP developers and evaluated
systems, prior-result access, and an EXPLICIT independence status label).
A bare `INDEPENDENT` label is rejected by the qualification engine:
independence is declared per dimension, never as an unaudited word.

### 21.2 The formal verification layer (protected material)

Every 0.5.0 candidate carries a `formal` object — a machine-checkable
encoding of its premises and query under one of four finite semantics:

- `relational-closure` — facts and grounded rules over a finite entity
  domain, forward-chained to a fixpoint (statement, consistency and
  repair-count queries);
- `propositional-truth-table` — implications and facts over propositions,
  verified by exhaustive model enumeration (modus ponens and modus tollens
  fall out classically; statement, consistency and repair-count queries);
- `constraint-enumeration` — finite-domain assignment problems
  (all-different, equals, not-equal, linear arithmetic,
  immediately-before) verified by exhaustive enumeration with a declared
  search-space cap;
- `default-extensions` — normal-case rules with exceptions, verified by
  enumerating maximal consistent default subsets; conflicting defaults
  yield multiple extensions and a designed indeterminacy that is REPORTED,
  never resolved (the §19.3 honesty rule applied at authoring time).

The formal layer is PROTECTED qualification material: it is never shown to
an evaluated system, never published, and exists so that ground truth is
established and verified independently of any evaluated system (order §6)
by deterministic computation alone. NL-to-formal correspondence is checked
mechanically in part (symbol coverage: every declared formal symbol must
appear in the NL task text) and is otherwise author-attested — a declared
limitation, never a silently assumed property.

### 21.3 The four-state qualification gate

`qualify-run` (src/ecp/qualification.py) produces exactly one of
`ACCEPT`, `REVISE`, `REJECT`, `INCONCLUSIVE` per candidate — there is no
fifth state; ambiguous engine inputs abort the run loudly. Dimensions:

- **Q1 identity** — content hash recomputation;
- **Q2 structural** — the order §5 field set (core content fields vs
  auxiliary fields distinguished);
- **Q3 ground truth** — mechanical verification of the formal layer against
  the authored class (and value, where the query yields one); a mismatch,
  an inconsistent premise set under a statement query, or a malformed
  formal layer are findings, never silent repairs; a missing formal layer
  yields the honest INCONCLUSIVE (cannot qualify now), not a forced
  ACCEPT;
- **Q4 novelty N1–N6** — N1/N2 recorded as OPEN questions (external
  novelty NOT_ESTABLISHABLE_MECHANICALLY without model invocation or
  retrieval, both forbidden at this stage); N3 within-pool duplication via
  renaming-invariant structural skeletons (entity and relation names are
  abstracted away — a superficial rename is NOT a new case); N4
  cross-population replay against a prior pool (text-level, with the
  prior pool's content hashes recorded for tamper evidence); N5/N6
  identifier-registry checks over case-content symbols;
- **Q5 leakage pre-screen** — the six §8-classes; a CONFIRMED direct
  answer leak (the queried statement is itself a premise fact) is
  disqualifying; model leakage is NOT-APPLICABLE-PRE-EXECUTION with the
  permanent pretraining-exposure declaration (§19 threat model);
- **Q6 independence** — the §3 record complete with an explicit bounded
  status;
- **Q7 representation-bias disclosure** — present per candidate, recorded
  separately from novelty, uncertainty preserved;
- **Q8 environmental pre-check** — present per candidate.

Decision precedence is fixed and recorded in every run manifest:
REJECT > REVISE > INCONCLUSIVE > ACCEPT. REJECTED and INCONCLUSIVE
candidates remain fully traceable (no silent discards).

### 21.4 Qualification runs, determinism and verification

A qualification run is a pure function of (candidates, run metadata,
prior population content). Artifacts are hash-chained in candidate order
(`prev_qualification_hash`, genesis all-zero); the run manifest records
the engine identity and profile, the decision-rule table, the engine
parameters, the prior-population reference, per-candidate entries, the
four-state tallies, the chain head, and `run_hash` (self-referential
SHA-256 over the canonical serialization). `qualify-verify` re-derives
every artifact and the manifest from retained inputs and reports INTACT
or the exact violations (hash mismatch, chain break, tally drift,
determinism violation). Verification is integrity-only: it never
adjudicates science.

### 21.5 Boundary (STOP)

The qualification layer MUST STOP before: registration, public ledger
append, ground-truth publication, hidden/dev set designation, model
execution, evidence collection, scoring, and statistics — even for
ACCEPTED candidates. The qualified pool is pool material only; partition
into public development / preregistered / hidden / rotating / private
sets is a registration-gate decision under owner authorization. The
rotation architecture is preserved by construction: no set-class is
assigned at authoring, and qualification is performance-blind (no
outcome data exists anywhere in the project at this stage).

## 22. Registration Readiness & Owner Adjudication Layer (0.6.0 / M3-CA1 v1)

The M3-CA1 v1 layer sits between qualification (§21) and registration
(§16): it assesses whether a qualified candidate pool may be converted
into Registered ECP Evaluation Cases, and it gates that conversion behind
explicit owner adjudication. It executes no model, registers nothing,
writes no ledger entry, and collects no result. The layer's own verdict
vocabulary is honest by construction: a run ends in either
`REGISTRATION-AUTHORIZED` (nothing blocks; the manifest gate may open)
or `OWNER-DECISION-REQUIRED` (one or more owner items remain open and
blocking — never a silent default).

### 22.1 The owner-decision register

The carried owner decisions (O-01 external novelty evidence; O-02
authoring authorization incl. the registration-contract authoring pass;
O-03 contamination disposition; O-04 ground-truth validation stage) are
recorded in an `owner-decision-register` document
(schemas/owner-decision-register.schema.json). Per item, the register
records the question, the framework reference, every permitted ruling
with its consequence, the scientific consequences, the threats, the
EXPLICIT state (`RESOLVED` — which requires a `ruling` and a
`ruling_basis` — or `REMAINS-OPEN`), the blocking determination for
registration with its basis, and the registration impact. For O-01 the
register additionally carries the evidence classification
(`SUPPORTED` / `UNRESOLVED` / `INSUFFICIENT-EVIDENCE`) with an
inference-prohibition note: UNRESOLVED or INSUFFICIENT evidence is never
inferred as NOVEL, and model performance is not admissible evidence.
Implicit defaults are a loud input error — the engine refuses a register
whose items are not explicitly stated. Phase findings (custody events;
structural discoveries that require an owner ruling) are recorded
separately from the four carried items and gate the manifest exactly
like unresolved items when they require a ruling.

### 22.2 The 15-point readiness battery

`readiness-run` (src/ecp/readiness.py) executes, per case, a frozen
15-point check battery over the PRESERVED qualification artifacts
(`case-candidate` + `case-qualification` + the run manifest):

- C-01 candidate contract; C-02 qualification decision (ACCEPT; recorded
  findings carried verbatim, never re-adjudicated); C-03 content-hash
  binding across candidate, artifact and run entry;
- C-04 provenance completeness (the §21.1 §3 record, all fields);
  C-05 independence explicitness (non-bare status label with declared
  limitations; a bare `INDEPENDENT` is rejected);
- C-06 mechanical ground-truth verification PASS; C-07 authored vs
  derived ground-truth class consistency; C-08 qualification artifact
  hash and chain-link integrity;
- C-09 N3 within-pool structural uniqueness; C-10 N4 cross-population
  overlap; C-11 N5 implementation encoding; C-12 N6 fixture leakage;
- C-13 six-class leakage pre-screen (the model class must be
  `NOT-APPLICABLE-PRE-EXECUTION` while zero executions exist
  project-wide);
- C-14 §9 representation-bias disclosure; C-15 §10 environmental
  pre-check (candidate record AND qualification dimension).

Checks are classified REJECT-class (contract, identity, ground-truth,
chain, novelty, leakage defects) or REVISE-class (provenance/disclosure
completeness). Each case ends in exactly one of `REGISTER`, `HOLD`,
`REVISE`, `REJECT` (precedence REJECT > REVISE > HOLD > REGISTER):

- REGISTER — all 15 checks pass AND nothing blocks (no unresolved
  blocking owner item, no unresolved owner-ruling finding, valid set
  class, inside the explicit population scope);
- HOLD — all 15 checks pass but a blocking owner item or owner-ruling
  finding binds the case: registration-ready in every mechanical
  dimension, held ONLY on owner adjudication;
- REVISE — a revise-class check failed;
- REJECT — a reject-class check failed, or a forbidden set class.

The battery is integrity-only: it never re-adjudicates the scientific
qualification decisions (that is the §20 owner-adjudication seam); it
verifies that the preserved state supports registration.

### 22.3 Ground-truth validation tracks

Every readiness record carries a `gt_validation_track`:
`CONFIRMED-TRACK` (determinate ground truths: DERIVABLE, CONTRADICTED,
IMPOSSIBLE), `NONDETERMINATE-READING-RULE-TRACK` (INDETERMINATE ground
truths — C-004-class material whose reading requires the owner-
authorized validation procedure), or `DESIGNED-AMBIGUITY-FORWARDED`
(the §21 FWD-GT-DESIGNED-AMBIGUITY flag, re-targeted to the O-04 stage).
Forwarded flags are never silently converted to CONFIRMED or REJECTED;
the track annotation makes the O-04 dependency per case explicit.
Carried qualification findings (e.g. Q3-CORRESPONDENCE-GAP: partial
mechanical NL↔formal correspondence) ride the record as
`gt_correspondence_note` — visible, non-blocking at readiness, and
flagged for O-04-stage scrutiny of GT defensibility against the
natural-language presentation.

### 22.4 Population decision

The registration population is an EXPLICIT decision
(`30-ONLY` / `18-ONLY` / `30+18` / `OTHER-EXPLICIT`) recorded with a
rationale and analysis blocks (duplication, template sharing, semantic
overlap, leakage, statistical dependence, prior-pool eligibility). The
engine re-derives the mechanical facts: prior-pool contract facts
(format-1 pools carry no formal layer, no ground-truth class, no
authoring-independence record — counted exactly) and the
cross-population text-overlap statistics (premise and signature Jaccard,
the N4 basis). The engine REFUSES any decision that would put
never-qualified material into registration scope: candidates enter
through intake → review → qualification, and prior-pool pilot material
that never passed qualification cannot be registered retroactively —
any future use requires re-authoring into the current candidate format
under a separate owner order, arriving as new candidate versions with
their own provenance.

### 22.5 Set-class designation

Per case, a class is designated from `PUBLIC` / `PROTECTED` / `HIDDEN` /
`ROTATING`. `PUBLIC` is FORBIDDEN for evaluation-pool material while
zero executions exist project-wide (pre-execution publication is a
leakage channel that destroys evaluation validity; public
development-class cases are a separately authored population).
`HIDDEN` and `ROTATING` require a set-binding reference — the
hidden/rotation split is a function of the registered-set composition
and the statistical plan, both deliberately deferred (charter §8.11);
an unbound designation now would be arbitrary. `PROTECTED` is the
preregistered-evaluation-candidate default. The open core is never
closed by a designation: protected content stays in the private
readiness area, and boundary-scan continues to enforce that the public
repository and the ledger tree carry no protected content.

### 22.6 The registration-authorization gate and the manifest

`assess_registration_authorization` reduces the register + population +
records to `AUTHORIZED` or `REFUSED` with every reason listed. The gate
is AUTHORIZED only when: every owner item that blocks registration is
RESOLVED, every finding requiring an owner ruling carries one, every
in-scope case is REGISTER, and the population decision is explicit.
`build_registration_manifest` REFUSES (loudly, as
`RegistrationManifestRefused`) unless the gate is AUTHORIZED and every
record is REGISTER — the order §12 rule "registering cases with
unresolved gates is forbidden" is machine-enforced. The manifest
(`registration-manifest` contract) freezes the set: per-case content
hashes, qualification artifact hashes, set classes, GT validation
tracks, the readiness-run binding, the population decision, and the
immutability rule (changes only through the §20 amendment protocol;
ground truth sealed at registration; no post-hoc changes). The manifest
is the set-level freeze; the §16 ledger ceremony remains the separate
full-contract instrument binding (evaluation, case version, target
system) tuples, and the manifest builder never writes the ledger.

### 22.7 Determinism and verification

`readiness-run` is a pure function of (candidates, qualification run +
artifacts, decision register, population decision, set-class
designation, prior population content, run metadata). Timestamps are
pinned explicitly (no wall clock). `readiness-verify` re-derives every
record and the run manifest bit-identically from retained inputs and
checks record hashes, the record chain, tallies, the
authorization/verdict consistency, and the schema validity of every
output. Real readiness material lives only in a private readiness area;
the public examples are format-illustration records with real
recomputable hashes.

## 23. Protected Evaluation + Registration Trust Layer (0.7.0 / M3-RG0)

0.7.0 is an **additive** bundle: the eight new trust-layer contracts are
added (`registration-gate-state`, `owner-gate-order`,
`registration-package`, `trust-registration`,
`registration-amendment`, `lineage-event`, `trust-store-manifest`,
`runtime-observation`); no earlier contract file is modified and
0.1.x–0.6.x artifacts remain exactly as valid as they were. The layer
implements the trust boundary that ADJ-06 (ECP-OWNDEC-000004, ADOPTED —
ARCHITECTURAL LAYER, IMMUTABLE) makes a **hard precondition** for ever
opening registration: *no registration, and no scientific execution,
before the trust boundary exists and is verified*. Implementation module:
`src/ecp/trust.py` (`ecp.trust`); CLI: the `trust-*` subcommands.

### 23.1 The protected store and its three ownership-explicit zones

A trust store is a root directory **outside the public repository** with
three zones whose ownership is explicit and machine-checked (order
M3-RG0 §3):

- `authoritative/` — **registered reference truth**: the gate state
  (`gate.json`), immutable registration records
  (`registrations/ECP-TREG-NNNNNN.json`), append-only amendments
  (`amendments/ECP-TAMND-NNNNNN.json`) and the hash-chained lineage
  (`lineage/NNNNNNNN.json`). Governed-mutation-only: the Registration
  Authority ceremony and the owner gate-order seam are the only writers;
  there is no write path from ordinary evaluation code.
- `operational/` — **mutable operational state**: runtime observations
  (`runtime/ECP-OBS-*.json`), each carrying `authority_class:
  NON-AUTHORITATIVE` and `zone: operational` by contract; the zone is
  never a source of reference truth and may be archived or pruned
  without affecting registered truth.
- `evidence/` — **scientific execution evidence**: reserved; **no writer
  exists at 0.7.0** (model execution gate CLOSED; execution cannot occur
  merely because the infrastructure exists — any non-README file here is
  a verification issue).

`trust.json` (the `trust-store-manifest` contract) is the derived index
over all three zones: never a trust anchor — `verify_trust_store`
cross-checks it against the disk state and reports drift as issues.
Writes are two-phase (temp file + atomic rename) everywhere.

### 23.2 The registration gate and its only transition instrument

`init_trust_store` writes the authoritative gate state as
`REGISTRATION = CLOSED`, `MODEL EXECUTION = CLOSED`,
`SCIENTIFIC RESULTS = NONE`, with the six Owner-bound operational
citations (O-01/O-02/O-04/F-01a/F-01b/POP) **null — unresolved, never
inferred**. The basis cites ADJ-06 and the M3-RG0 §10 rule verbatim.

The ONLY legal gate transition is `apply_owner_gate_order` with an
explicit `owner-gate-order` instrument. The seam validates (fail-closed;
the gate is untouched on any rejection): schema + versions; **scope
binding** (a development-scope order can never govern an
operational-scope store and vice versa); duplicate `order_id` rejection;
**ruling completeness** (all six Owner-bound rulings non-empty — an
incomplete order is refused, never completed by inference); and
transition legality (model execution may not open while the registration
gate is closed; CLOSED→CLOSED no-ops and OPEN→OPEN re-opens are
rejected; a re-open requires an explicit close first — a clean audit
trail). On success the new gate state freezes the six citations to the
order's values, pins `gate_order_reference` (order id + order hash) and
a lineage `gate-transition` event is appended.

### 23.3 The Registration Authority (fail-closed acceptance)

`RegistrationAuthority.submit_registration` (order §4) refuses — each
refusal recorded as a lineage `registration-refused` event, never
silent — on: **closed gate** (checked first: the cheapest fail-closed
exit); malformed package (schema/version); **package_hash
non-recomputation** (altered-submission detection); Owner-bound
citation absence or divergence from the authoritative gate (never
merged, never reinterpreted); invalid embedded case document;
unsealed or malformed ground-truth reference; **ground-truth
commitment divergence** (the seam: the package never carries
ground-truth content, only the commitment); **success-criterion
divergence** between the package's frozen copy and the case document;
duplicate frozen tuple (evaluation, case id, case version, environment
id) among live registrations; and write-once violations. Acceptance
assigns the deterministic identity `ECP-TREG-NNNNNN` (monotone,
authority-assigned, never author-chosen), recomputes the full
commitment set (never trusting package-supplied values), and appends
the `registration-accepted` lineage event whose payload carries the
record hash — bidirectional binding without circular hashing (the
record cites the event by index; the event cites the record by hash).

### 23.4 Immutable records and amendments

Accepted records are write-once files; `verify_trust_store` recomputes
`registration_hash` (self-referential, exclusion rule) and the full
record hash for every record. Corrections are **new events**
(`amend_registration`), never edits: the amendment document
(`registration-amendment`) binds `target_registration_hash` to the
EXACT original record, requires an explicit non-empty motivation, and
may replace only **environment** or **provenance** content — case
content and ground truth are never amendable; explicit **invalidation**
is the only retirement path, and nothing can amend an invalidated
registration. The original record and its commitments remain
independently verifiable forever.

### 23.5 State / reference-truth separation

`store_reference_truth` answers **WHAT WAS REGISTERED** from the
authoritative zone alone (pure, deterministic, hash-verified);
`store_runtime_state` answers **WHAT LATER HAPPENED** from the
operational zone alone (explicitly marked `non_authoritative`);
`resolve_registration` returns the two answers side by side, never
merged, with the accepting event, the amendments and the runtime
observations listed separately. Runtime execution can never become an
implicit source of truth for what was registered: operational documents
carry mandatory NON-AUTHORITATIVE/zone markers, the operational writer
cannot touch the authoritative zone, and the verifier rejects any
operational document claiming an authoritative object type. The
operational writer (`record_runtime_observation`) also refuses
fabricated registration references and duplicate observation ids.

### 23.6 Cryptographic commitments

All commitments are deterministic SHA-256 over `ECP-CANONICAL-JSON-1.0`
bytes (order §7): case content, ground truth, success criterion
(wrapped as `{"success_criterion": …}` when the criterion is the case
contract's plain string), environment, provenance, package
(`package_hash`) and record (`registration_hash`). Self-referential
hashes use the established exclusion mechanism
(`hash_document_excluding`) — the document's own hash field is removed
before hashing, never hashed populated. The commitment set is
sufficient to detect case, ground-truth, criterion, environment,
provenance, package and registration-record modification (all exercised
by the test battery).

### 23.7 Provenance / lineage

The lineage chain is append-only and hash-chained
(`event_hash` covers the event including `prev_event_hash`, minus its
own field). Event kinds: `trust-init`, `gate-transition`,
`registration-accepted`, `registration-refused`,
`amendment-recorded`. Every accepted registration can answer, from the
chain alone: where it originated (package id), which artifact and
version were registered, which commitments identify it, which event
accepted it, and whether it was subsequently amended. **No execution
result may overwrite registration provenance**: execution-side material
is not an event kind, has no authoritative writer, and lives (when a
future owner gate authorizes execution) only in the evidence zone.

### 23.8 Verification (order §11) and the fail-closed posture

`verify_trust_store` re-derives everything from the files alone:
manifest cross-check (derived index, drift = issues), gate state
(schema, self-hash, OPEN-state citation completeness, and a
**gate-history replay** over the lineage — every acceptance must fall
inside an OPEN window and the replayed final state must equal
`gate.json`), every record (schema, self-hash, record hash, lineage
binding, monotone-identity discipline, duplicate control, citation
completeness), every amendment (schema, self-hash, lineage binding,
target binding, invalidation rules), the lineage chain (contiguity,
chaining, per-event hashes), zone ownership markers, the evidence-zone
writer prohibition, and the reference-truth end-to-end re-derivation.
Every missing or contradictory mandatory trust input is an issue — the
layer never infers.

### 23.9 Scope boundary

The layer is infrastructure only: it registers nothing scientific (the
gate is CLOSED and no operational owner order exists), executes no
model, produces no results, and creates no case authoring, statistical
or product functionality. Real trust material lives only in a private
trust area; the public examples are format-illustration records with
real recomputable hashes. A successful infrastructure test in
development scope is never an authorization to register real cases
(order §10).
