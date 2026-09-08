# M3-R1 — Protected Evidence & Registration Architecture Decision

**Document type:** Architecture Decision Record (discovery + decision only).
**Status:** DECIDED — awaiting separate implementation order (M3-R1-I).
**Parent phase:** M3-R0 (repository foundation, commit `7e51c7579a430689aa1ba1a164ce22950e6e808d`).
**Scope of this document:** the minimum architecture required to move ECP from a
*public repository foundation* to a *reproducible evaluation infrastructure*,
restricted to the two components named by the phase gate: the **Protected
Evidence Store** and the **Registration Authority**.

> **Nothing is implemented by this document.** No schema is mutated, no
> database is created, no registration record is created, no case is authored,
> no execution occurs, no ground truth is generated, no evidence is ingested.
> This document records discovery, threat analysis, options, and one explicit
> architectural decision, per the M3-R1 order (§10 implementation prohibition).
> The scientific status of ECP is unchanged: **zero registered cases, zero
> executions, zero results, zero scientific claims.**

---

## 0. Execution record — baseline verification

The following checks were performed *before* any content was produced for this
document, per the M3-R1 order §0–§1. All passed.

| Check | Result |
|---|---|
| `HEAD` == local `main` == `origin/main` == `ls-remote origin` | `7e51c7579a430689aa1a164ce22950e6e808d` — all four equal — **PASS** |
| Worktree | clean (no modified, staged, or untracked files) — **PASS** |
| `git fsck --full` | no output — **PASS** |
| Commit count / history shape | exactly 1 commit (the R0 foundation commit); no history rewrite possible to observe — **PASS** |
| Committer identity | `ECP Foundation Executor <foundation@ecp-protocol.local>` — **PASS** |
| Foundation test suite re-run at R1 start | **229 / 229 PASS** |
| `tools/ecp_cli.py boundary-scan` | **CLEAN** |
| External frozen systems (evaluated-system repository at its frozen baseline; candidate case pools; all historical evaluation records from earlier milestones) | verified untouched at their recorded baselines (hashes recorded in the phase execution worklog, outside this repository) — **PASS** |
| No M3 case / registration / execution exists in ECP | true by construction — the repository has exactly the R0 commit and no reserved-directory content — **PASS** |

Any single failure above would have halted this phase with
`M3-R1 BASELINE MISMATCH`. None occurred.

---

## 1. Current-state discovery

### 1.1 What R0 provides (inventory relevant to the two R1 targets)

| Capability delivered at R0 | Where | Relevance to R1 |
|---|---|---|
| Versioned protocol identity (protocol / schema / repository versions, canonicalization, hash algorithm) | `ECP-IDENTITY.json`, `schemas/protocol.schema.json` | Every future store and ledger artifact cites these versions |
| Public case contract with commitment-only ground-truth reference | `schemas/case.schema.json` | The public half of the case/ground-truth seam already exists |
| Protected ground-truth *format* contract (structure only; sealed content forbidden in the public tree) | `schemas/ground-truth.schema.json` | The protected half of the seam has a format but no home and no custody |
| Registration *contract* (append-only, `registration_hash`, supersession-not-edit) | `schemas/registration.schema.json` | The registration record format exists; no authority operates it |
| Execution / evidence / audit / manifest contracts | `schemas/*.schema.json` | Downstream consumers of the two R1 components are already specified |
| Deterministic canonicalization + hashing | `src/ecp/canonical.py`, `src/ecp/hashing.py` | Commitments and ledger hashes inherit byte-level determinism |
| Deterministic manifests | `src/ecp/manifest.py` | Extends naturally to store manifests |
| Integrity verification (recomputation, not trust) | `src/ecp/verification.py` | The verification half of "independent re-verification" exists |
| Public/protected boundary enforcement (R1–R5 rules) | `src/ecp/boundaries.py`, CLI `boundary-scan` | Currently enforces the *public repository* side only |
| Cross-document linkage checking | `src/ecp/linkage.py` | Will extend across ledger and store artifacts |
| Foundation tests | `tests/` (229) | Regression safety net for R1-I changes |

### 1.2 What R0 deliberately does not provide

The R0 gap list, restated with R1 scope assignment:

| Gap | Owner of the gap | In R1 scope? |
|---|---|---|
| Protected Evidence Store | future store component | **yes — this document** |
| Registration Authority | future authority component | **yes — this document** |
| Execution harness / adapters | execution phase | no |
| Case review pipeline (leakage/novelty/independent review before registration of real cases) | case-authoring phase | no (but its *existence* constrains the ledger design — see §3.4) |
| Execution-time isolation / network enforcement | execution phase | no (threat model must state the residual risk honestly — §5) |
| CI | infrastructure phase | no |
| Cross-language platform | future | no (R1 designs must be language-neutral *formats*) |
| Version-migration tooling | future | no (R1 must minimize future migration surface — §11) |

### 1.3 The circular dependency (the discovery finding that decides the phase)

The two R1 targets are **mutually dependent at the semantic level**:

1. A Registration Authority cannot perform a *real* registration without a
   custodian for the sealed ground truth. The registration freezes the
   success criterion and the verification rule and binds the case to its
   ground truth via the commitment — but the commitment is only meaningful if
   the sealed document it commits to is *held somewhere that guarantees it is
   the same bytes later*. Without a store, a registration authority can only
   compute commitments over ad-hoc files with no custody, no write-once
   enforcement, and no availability guarantee. The freeze would be
   cryptographically detectable-as-broken but operationally unenforced.
2. A Protected Store without registration semantics is a vault. It can keep
   bytes immutable, but it has no notion of *which* commitments are live,
   which sealed ground truths are bound to which public cases, what
   lifecycle a sealed object has, or what an amendment means. Nothing public
   would reference it, so nothing about it would be independently
   verifiable — the exact failure mode ECP exists to prevent.

The conclusion is not "pick one first" but **the seam is the product**: the
scientific guarantees ECP promises (freeze-before-execution, immutable ground
truth, independent re-verification) live in the *binding* between the ledger
and the store, not in either component alone. This finding drives the
recommended architecture (§8) and directly answers the phase question
"Protected Store first or Registration Authority first?" — see §8.3.

### 1.4 Inherited design invariants (constraints any R1 architecture must respect)

These are load-bearing decisions from R0 (spec, architecture, trust model)
that R1 may *build on* but must not *violate*:

- **I1 — The public Git repository is a provenance and distribution layer,
  never the trust boundary.** Protected content never enters it (spec §6).
- **I2 — Public cases carry commitments, never answers.** The commitment is
  one-directional (spec §6.4); the protected side holds no back-pointer that
  creates circular hashing.
- **I3 — Registration is append-only; corrections supersede, never
  overwrite** (spec §4, registration schema).
- **I4 — Hashes are integrity only after recomputation**; verification is
  distinct from adjudication (spec §7.6, §8).
- **I5 — Provider neutrality**: nothing in the core may assume any specific
  model, provider, framework, cloud, or evaluated system (spec §12).
- **I6 — Versioned identity everywhere**: every artifact cites protocol and
  schema versions; no implicit "current version" (spec §2).
- **I7 — Stability-critical rules**: changes to canonicalization, hashing, or
  sealing are protocol major-version events; schema additions require a
  `schema_version` bump (spec §14).
- **I8 — Open-core boundary**: the scientific core stays open and
  provider-neutral; commercial capability (hosted services, private vaults)
  lives outside and must remain *architecturally* possible without
  protocol changes (docs/OPEN-CORE.md).

---

## 2. Protected Evidence Store — requirements discovery

### 2.1 Artifact classification (PUBLIC / PROTECTED / SECRET / DERIVED / AUDIT-ONLY)

Classification semantics (these five classes are not synonyms):

- **PUBLIC** — may live in or be published from the public repository;
  anyone may read it; its integrity is publicly recomputable.
- **PROTECTED** — content must remain outside the public repository; its
  *existence* is publicly acknowledged (typically via a commitment); access
  is restricted to authorized roles under the trust model.
- **SECRET** — even its *existence or count* must not be revealed publicly
  (no commitment published, no metadata that discloses it).
- **DERIVED** — computable from public and/or protected inputs; publication
  is governed by a disclosure decision, not by secrecy of computation.
- **AUDIT-ONLY** — released to independent auditors for adjudication but not
  to the public at large (at least not until a future disclosure decision).

| Artifact | Class | Rationale / custody notes |
|---|---|---|
| Protocol spec, schemas, reference core, CLI, docs | PUBLIC | provenance/distribution layer |
| Public case documents (with commitments) | PUBLIC | never contain answers (structurally excluded) |
| Registration ledger entries (public ledger) | PUBLIC | the whole point: freeze visible to anyone (see §3) |
| Ledger anchor digests (chain HEAD) | PUBLIC | external tamper-evidence for the ledger |
| Sealed ground-truth documents (expected answer, derivation, full rule semantics) | PROTECTED | existence public via commitment; content never public pre-disclosure |
| Hidden case documents (non-public case definitions) | PROTECTED (pool composition SECRET) | individual hidden cases become PROTECTED when executed (their prompts necessarily reach the executor); the *pool membership list* stays SECRET while an evaluation is running to prevent gaming by enumeration |
| Store master index / seal records | PROTECTED | reveals case count and sealing timeline; existence-level metadata is acceptable, content-level is not |
| Store operation log (op log) | AUDIT-ONLY | reveals operational patterns; auditors may read it; public cannot (pre-disclosure) |
| Raw execution evidence (verbatim outputs, traces, tool logs) | PROTECTED → AUDIT-ONLY until disclosure | preserved verbatim; auditors get full access; public sees only what a disclosure decision releases |
| Evidence bundle manifests (artifact hashes + roles) | AUDIT-ONLY (public form possible) | hashes may be published later in redacted form; paths/roles audited first |
| Scoring/verification results per execution | DERIVED | computed from protected evidence + protected ground truth; publication governed by disclosure policy |
| Evaluation-level statistics, comparisons, leaderboards | DERIVED | same; also subject to the reproducibility-class rules (docs/REPRODUCIBILITY.md) |
| Store encryption keys (if encryption-at-rest is enabled — open decision O3) | SECRET | existence may be acknowledged; material never leaves operator custody |
| Amendment drafts (pre-publication supersession records) | SECRET until appended | drafts are not records; only appended ledger entries exist |

The classification is enforced in layers: the public side by the existing
boundary scanner (extended in R1-I to cover ledger rules), the protected side
by store access policy and disclosure control (§2.4).

### 2.2 Functional requirements

**Store layout and content addressing (PS-1..PS-4)**

- **PS-1 — The store lives OUTSIDE the public repository** (a sibling
  directory at the operator site; path configurable; never a submodule or
  subtree of the public repo). The public repository links to store content
  exclusively through commitments and (for the ledger) published record
  hashes.
- **PS-2 — Content-addressed storage (CAS)**: sealed documents are stored as
  blobs whose storage path is a function of their own content hash
  (`sha256` of the canonical bytes, sharded for filesystem hygiene, e.g.
  `zones/sealed-gt/ab/abcd1234….json`). Immutability then becomes *physical*:
  "modifying" a blob produces a different path; the original bytes remain.
- **PS-3 — Zones**: the store separates `sealed-gt/` (sealed ground truth),
  `hidden-cases/`, `evidence/` (post-execution bundles; reserved at R1,
  ingest contract designed in §2.6), `exports/` (controlled disclosure
  outputs), plus a `registry/` (indexes) and an `oplog/` (append-only
  operation log). Zones exist so that disclosure rules differ per class
  without path-sharing.
- **PS-4 — Write-once semantics per seal target**: exactly one sealed blob
  per `(case_id, case_version)` ground-truth document. A second seal attempt
  with *different* content is rejected; a second seal attempt with *identical*
  content is idempotent and recorded as such.

**Immutability, audit trail, provenance (PS-5..PS-8)**

- **PS-5 — Append-only operation log**: every store operation (init, seal,
  read-for-audit, export, rejection, error) is appended to a hash-chained op
  log: each entry contains the previous entry's hash. The op log is the
  store's own tamper-evidence; its HEAD digest is checkpointed into the
  registration ledger anchor (§3.3) so store operations inherit the ledger's
  external anchoring.
- **PS-6 — Atomic writes**: all writes are two-phase (temporary file + atomic
  rename). A crashed operation leaves either no trace or a complete,
  validatable record — never a partial blob or partial index (partial-write
  threat T7).
- **PS-7 — Store manifest**: a deterministic manifest (existing
  `src/ecp/manifest.py` machinery, reused) over each zone; the manifest hash
  is recorded in the op log. Full-store integrity verification is a single
  recursive recomputation (`store-verify`).
- **PS-8 — Provenance cross-checking**: the store registry records, per seal:
  `case_id`, `case_version`, commitment, blob hash, claimed seal time, op-log
  position, and (once registered) the `registration_id` that bound it. The
  linkage checker extends to verify case ↔ commitment ↔ blob ↔ registration
  consistency in both directions.

**Access control and disclosure (PS-9..PS-11)**

- **PS-9 — Role-scoped access**: read/write rights per role per zone per the
  trust boundary matrix (§4.2). The store enforces the matrix at the tool
  layer (CLI refuses out-of-role operations) — the filesystem layer is a
  second enforcement point, not the only one.
- **PS-10 — Disclosure control**: leaving the store happens only through the
  `exports/` zone; every export is itself an op-logged, manifest-hashed event
  naming what left, for whom, and under which disclosure decision. No bulk
  copy of protected content without an export record.
- **PS-11 — Ground-truth read path**: sealed ground truth is readable only by
  (a) the registration authority operator, as opaque bytes, for commitment
  computation and verification, and (b) auditors, at adjudication time, for
  the specific cases assigned to them. The *evaluated system never has any
  read path to the sealed-gt or hidden-cases zones* (enforced at execution
  time by the future isolation gate; declared in the threat model §5 T4/T5).

**Recovery and portability (PS-12..PS-14)**

- **PS-12 — Recovery**: because the store is CAS + append-only logs + zone
  manifests, recovery from a crash mid-write is: discard temp files, re-run
  `store-verify`, and reconcile the op log against the registry. A verified
  store state is exactly reproducible from {blobs + op log + registry}; blobs
  are byte-addressed, so no rebuild ambiguity exists.
- **PS-13 — Backup/restore**: the store is a plain directory tree with no
  database and no external service; backup = copy; restore = copy + verify.
  Restore procedures must re-run full verification before any new operation
  is accepted (a restored store starts in a quarantined state until
  `store-verify` passes).
- **PS-14 — Export/reproducibility boundary**: an external party reproducing
  an ECP result (auditable class, docs/REPRODUCIBILITY.md §1) needs the
  public ledger, public cases, and — where a disclosure decision authorizes
  it — export packages containing exactly the sealed ground truths and
  evidence bundles for the disclosed evaluation, each with recomputable
  commitments and manifests. The store must be able to produce such packages
  without ever granting blanket store access.

### 2.3 What must STAY public (the anti-vault requirement)

A store that swallows everything defeats ECP's public verifiability. The
following remain public, always: protocol, schemas, tools, public cases,
registration records, ledger digests, and all *verification semantics* (how to
recompute every hash and check every chain). The protected side holds
*content*; the public side holds *the means to check the protected side's
integrity*. This split is inherited from the R0 trust model ("trust the
recomputation, not the claim") and is non-negotiable.

### 2.4 Enforcement layers summary

| Layer | Enforces | Mechanism |
|---|---|---|
| Schema | public artifacts structurally cannot carry answers | `additionalProperties: false`, commitment-only `ground_truth_reference` |
| Boundary scanner (public side) | no protected content in the public tree; ledger rules (R1-I extension) | `boundary-scan` in tests + future CI |
| Store tooling (protected side) | write-once, role matrix, atomic writes, op logging | CLI refuses invalid operations; CAS paths |
| Cryptographic | tamper detection | commitments, chain hashes, manifests — recomputable |
| Disclosure | what leaves the store | export records, audit-only zones |
| Governance | who may register/seal/export | registrar identity in ledger entries; owner policy (open decisions §10) |

### 2.5 Non-requirements at R1 (deliberately deferred)

Encryption at rest (open decision O3); multi-site replication; concurrent
multi-operator writes; a service API of any kind (the store is a local,
tool-operated directory tree); evidence *ingestion* implementation (execution
phase); hidden-case *distribution* mechanics (execution phase); network
isolation (execution phase).

### 2.6 Evidence zone — designed now, implemented later

The `evidence/` zone is reserved at R1 with a designed ingest contract so the
future execution phase does not have to re-open store architecture:

- ingestion is **append-only via a write-only channel** (the executor submits
  a bundle; it cannot read back or modify);
- each bundle carries a manifest of artifact hashes (existing manifest
  machinery) and is assigned an `ECP-EVID-…` id by the store, not the
  executor;
- the ingestion event is op-logged and the bundle manifest hash is recorded
  there (evidence-replacement threat T2 becomes detectable);
- bundles for hidden-case executions land in the protected zone with
  AUDIT-ONLY default disclosure.

---

## 3. Registration Authority — requirements discovery

### 3.1 What the authority must do (minimal functional set)

**RA-1 — Create a registration record.** From a submitted
`(public case document, sealed ground-truth blob reference, system identity
reference, evaluation identity, condition, success criterion, verification
rule reference)`, produce a schema-valid `registration` document
(`schemas/registration.schema.json`, unchanged semantics) whose frozen fields
are *copied from the case at registration time* — not referenced by pointer,
so later case edits cannot silently drift a registration.

**RA-2 — Freeze the ground truth.** Compute the commitment
(`sha256` over `ECP-CANONICAL-JSON-1.0` bytes of the sealed document —
existing machinery) and store it in the registration record; verify that the
public case's `ground_truth_reference.commitment` equals it. A registration
where the public case commitment and the sealed blob commitment diverge is
rejected before the ledger is ever appended.

**RA-3 — Freeze the tuple.** The record fixes protocol version, schema
version, case id + version, system id + version, condition constraints,
success criterion, and verification rule id/type — the full pre-execution
freeze already required by the schema. The authority adds one thing the
schema assumes but R0 could not provide: **an immutable, publicly verifiable
place for the record to live** (the ledger, §3.2).

**RA-4 — Generate the registration identity.** `registration_id` is assigned
by the authority (registrar-controlled, monotone, pattern-checked), never
chosen by the case author, so that id collisions and cherry-picked ids are
not author-attackable (duplicate/replay threats T8/T9).

**RA-5 — Make registration immutable after append.** No edit path exists.
The only post-append operation is *supersession*: a new record with
`supersedes: <prior registration_id>` plus a machine-checkable reason class.
Supersession MUST NOT be able to silently change the frozen tuple of a case
that already has executions; if executions exist, the only legal supersession
is an explicit *invalidation* (which the evidence/audit layer can then see
and quarantine against).

**RA-6 — Amendment without history erasure.** All supersessions are new
ledger entries; the superseded record remains in the ledger verbatim; the
chain makes removal detectable; the ledger verifier reports the full
supersession graph.

**RA-7 — Independent verification.** Any third party, given only public data
(the ledger, the public cases, the anchor digests), can: recompute every
registration hash, recompute every commitment against the published public
case, verify the chain end-to-end, and verify the anchor. No store access,
no trusted service, no keys required. This is the property that makes
pre-registration *scientifically meaningful*.

**RA-8 — Establish (claimed) time and (provable) order.** Claimed
timestamps are recorded but are *assertions, not evidence* (clock threat
T10). Canonical order is the **chain position**. External anchoring (§3.3)
provides the independent time evidence.

### 3.2 Architectural alternative analysis: what "authority" means

The phase order explicitly forbids assuming a central service or cloud. Four
realizations were examined:

| Realization | Description | Assessment |
|---|---|---|
| **(a) Cloud/central service** | hosted registration API with accounts | **REJECTED.** Violates I5 (provider neutrality) and I8 (open-core: hosted services belong to a future commercial layer, and the *protocol* must not require one); adds an always-online trust dependency; unnecessary at current scale; the open scientific core must be operable offline by anyone. |
| **(b) Local service/daemon + database** | a background service owning a DB | **REJECTED.** Databases add mutable-state semantics that fight append-only; audit requires DB dumps, not plain files; operational complexity with zero scientific gain; harder to verify independently. |
| **(c) CLI ceremony + file ledger + verification tooling** | the authority is a *procedure*: an offline command run by an authorized registrar; the ledger is a directory of chained entry files; anyone can verify with public tooling | **ADOPTED.** Matches every inherited invariant: offline, provider-neutral, plain files, hash-verify chains, git-compatible, no service to attack or operate. The "authority" is (role + procedure + tool + public verification), not a machine. |
| **(d) Federated multi-registrar / threshold signatures** | multiple independent registrars, quorum-signed entries | **DEFERRED, designed-for.** The entry format records a registrar identity and the chain design is registrar-count-agnostic; multi-registrar is an additive future extension, not a rewrite. Single-registrar operation now (open decision O4). |

### 3.3 The ledger (the authority's artifact)

**L1 — Ledger entry.** Each append wraps one record:

```text
{
  "ecp_object": "ledger-entry",        # new object type (schema in R1-I)
  "ledger_id": "ECP-LEDGER-MAIN",
  "entry_index": <int, monotone>,
  "entry_kind": "registration" | "invalidation" | "anchor" | "store-checkpoint",
  "registrar": "ECP-REGISTRAR-<id>",
  "record_ref": { ...record id + record document hash... },
  "claimed_at": "<ISO8601Z assertion, not evidence>",
  "prev_entry_hash": "<entry_hash of the previous entry>",
  "entry_hash": "<sha256 over canonical entry with entry_hash removed>"
}
```

(Format illustration only. No such entry exists; no ledger exists; nothing
is registered. Entry field set is finalized in the R1-I schema.)

**L2 — Chain.** `entry_hash` covers the full entry including
`prev_entry_hash`, so the chain is both content-tamper-evident and
order-tamper-evident: inserting, removing, reordering, or editing any
historical entry breaks every subsequent `entry_hash`.

**L3 — Ledger HEAD and anchoring.** The HEAD digest
(`ledger_id, entry_count, head_entry_hash`) is *anchored* outside the ledger
by the registrar: committed to a public Git repository (open decision O1:
inside the ECP repository vs a dedicated public ledger repository) and pushed
to the public remote. The external push event (host-side timestamps) is the
independent time evidence backing the claimed timestamps (T10). Anchoring is
op-logged on the store side; each anchor entry may also checkpoint the store
op-log HEAD (PS-5), binding the two components' tamper-evidence together.

**L4 — Ledger verification (public).** A public CLI subcommand
(`ledger-verify`) recomputes the entire chain from plain files, checks the
anchor digest equality, and cross-checks every `registration` entry against
the public case commitment (recompute from the public case document). This
closes decision-rule #5 (independent re-verification) with public data only.

**L5 — Duplicate and replay control.** The ledger verifier enforces:
unique `entry_index` sequence; unique `registration_id` (no re-append);
at most one *live* registration per
`(evaluation_id, case_id+case_version, system_id+system_version,
condition-hash)` tuple (duplicates beyond one live registration are flagged
as violations; re-registration after invalidation is a new superseding entry,
not a silent duplicate) (T8/T9).

**L6 — Registration-before-execution.** The evidence ingestion contract
(§2.6) requires a registration reference: the store refuses evidence bundles
whose `execution_id` cannot be linked to a live registration entry. This is
the mechanical enforcement of "protect the record before execution" —
execution output cannot even *land* without a prior public freeze.

### 3.4 Relationship to the future case review pipeline

Real (non-development) case registration is *gated upstream*: a case must
pass independent review (leakage, novelty, difficulty) before its
registration is accepted. R1 does not build that pipeline, but the ledger
design must accommodate it: the registration record's `notes` and the
ledger entry's `entry_kind`/registrar identity provide the surface a future
review-approval citation attaches to, without schema changes now
(review-gate evidence becomes additional referenced artifacts, added
additively later).

---

## 4. Trust boundaries

### 4.1 Boundary diagram

```
Case Author                    (authors case + ground truth draft)
     │  submission (case doc + GT draft)         MUST NOT execute, MUST NOT audit own cases
     ▼
Registration Authority         (registrar role: offline CLI ceremony)
     │  computes commitment over sealed GT bytes (treated as opaque)
     │  appends chained entry to the ledger
     │
     ├──> PUBLIC METADATA       ledger entries · anchor digests · public case docs
     │        (public Git repository; anyone may read/verify)
     │
     └──> PROTECTED ARTIFACTS   sealed GT blob (CAS, write-once)
              │                 store registry · op log
              ▼
        Execution Environment   (FUTURE phase — untrusted)
     │  receives ONLY the public case (prompt/attachments/condition)
     │  NEVER any path to sealed-gt/ or hidden-cases/
     │  submits bundle via write-only evidence channel
     ▼
Raw Evidence Store             (protected zone, append-only ingestion, manifests)
     │
     ▼
Independent Audit              (two-auditor default; reads evidence +,
                               at adjudication time, sealed GT for assigned cases)
     │  writes audit records; disagreement → mandatory adjudication
     ▼
Classification / Results      (DERIVED; disclosure-governed publication)
```

### 4.2 Read/write matrix (per role per zone)

| Zone / artifact | Case Author | Registrar (RA operator) | Executor | Auditor | Public |
|---|---|---|---|---|---|
| Public case docs | write drafts (pre-registration) | read + verify | read (execution input) | read | read |
| Sealed GT blob | submit draft (own case, pre-seal only) | read as **opaque bytes** (commitment + verification) | **FORBIDDEN** | read, **adjudication time only**, assigned cases only | **FORBIDDEN** |
| Hidden-case pool | **FORBIDDEN** | admin read (existence-level) | the single case being executed, at execution time, only | read, assigned only | **FORBIDDEN** (pool composition SECRET) |
| Registration ledger | read | **append only** | **FORBIDDEN** | read | read + verify |
| Ledger anchors | read | write (publish) | **FORBIDDEN** | read | read + verify |
| Evidence zone | **FORBIDDEN** | admin read | **append-only write channel**, no read-back | read, assigned bundles | AUDIT-ONLY until disclosure |
| Store op log | **FORBIDDEN** | append | **FORBIDDEN** | read | AUDIT-ONLY |
| Exports | **FORBIDDEN** | create (disclosure-governed) | **FORBIDDEN** | receive per assignment | post-disclosure only |
| Store registry index | **FORBIDDEN** | read + update on legal ops | **FORBIDDEN** | read (existence-level) | **FORBIDDEN** |

### 4.3 The no-path rules (attack-path elimination)

The following paths MUST NOT exist anywhere in the R1 architecture:

1. **No write path from execution to anything except the evidence ingestion
   channel.** The executor cannot touch the ledger, the sealed-gt zone, the
   registry, or the op log.
2. **No read path from execution to sealed ground truth, the hidden-case
   pool (beyond the case being executed), or the store registry.**
   (Enforcement of *runtime* isolation is a future gate; the *store-side*
   enforcement — the tooling simply has no command that serves GT to an
   execution context — exists from R1-I onward. Residual risk stated in §5.)
3. **No edit path to any ledger entry or any sealed blob.** The only
   mutations in the entire architecture are *appends* (ledger entries, op-log
   entries, new CAS blobs, registry additions) and *explicit supersessions*
   (new entries, old entries retained).
4. **No path that modifies ground truth after execution.** Three independent
   locks: (i) CAS write-once (PS-4) — modification creates a new blob, not a
   changed one; (ii) the commitment frozen in the public ledger — any GT
   substitution breaks public recomputation at the exact registration;
   (iii) audit-time verification re-runs both checks and the op log proves
   no re-seal event ever occurred. To change ground truth undetected an
   attacker must simultaneously rewrite the store blob, the store registry,
   the op log, the ledger, *and* the public anchor — and the public anchor is
   on an external public Git host outside their mutable zone.
5. **No silent amendment path.** Supersessions are visible ledger entries
   with reason classes; post-execution amendments can only be invalidations,
   never tuple rewrites.
6. **No bulk-disclosure path.** Everything leaving the store is an
   op-logged export bound to a disclosure decision (PS-10).

---

## 5. Threat model

Format per threat: **Threat / Attack surface / Required control / Residual
risk**. T-numbers are referenced from §2–§4 and will be referenced by the
R1-I acceptance criteria. This model extends the R0 SECURITY.md boundary
(that document remains normative for the public side).

**T1 — Registration tampering**
*Surface:* ledger files; any writable copy of the ledger.
*Control:* hash chain (L2) — any edit breaks all subsequent entries; anchor
digest published to an external host (L3); public `ledger-verify`; append-only
policy with no force-push on the ledger remote.
*Residual:* inside the *anchor window* (entries appended but not yet
anchored), a registrar-machine compromise could rewrite the unanchored tail
consistently. Mitigation: anchor after every registration at current scale
(open decision O2). Accepted.

**T2 — Evidence replacement**
*Surface:* evidence zone post-execution.
*Control:* CAS write-once blobs; bundle manifests with artifact hashes
recorded in the op log; bundle ids assigned by the store (not the executor);
audit re-verification. Replacement requires op-log and manifest rewrite —
chained to the anchor.
*Residual:* anchor window, as T1. Accepted.

**T3 — Hash substitution (consistent rewrite)**
*Surface:* the entire mutable zone (store + ledger) on the operator machine.
*Control:* external anchoring is the *only* sufficient defense — the anchor
lives outside the mutable zone on the public host; two-auditor independence
(both must be compromised to paper over a scientific inconsistency);
store-verify + ledger-verify as routine checks.
*Residual:* within the anchor window, a fully compromised operator machine
can rewrite everything it holds. This is a *fundamental* limit of any
single-operator architecture and is stated honestly: ECP at this scale is
tamper-*evident with bounded latency*, not tamper-*proof instantaneously*.
Multi-registrar federation (d) is the designed escalation path.

**T4 — Ground-truth exposure**
*Surface:* store filesystem; exports; auditors; logs; the commitment itself.
*Control:* store outside the public repo; boundary scanner (public side);
role matrix (§4.2); disclosure control; GT readable by auditors only at
adjudication; commitment preimage-resistance (public hash reveals nothing
computationally); export records.
*Residual:* anyone with operator-machine filesystem access can read sealed
GT. Encryption at rest is deferred (O3) and even then key custody sits with
the operator. Accepted at current scale; documented.

**T5 — Premature answer leakage (to the evaluated system)**
*Surface:* prompt construction (author embeds hints); execution environment
file access; logs; timing channels.
*Control:* case-author information-boundary declaration (already in the case
schema's `authoring_provenance`); case review pipeline gate before real
registration (future phase, §3.4); executor has no store read path
(§4.3.2); verbatim output preservation (everything the system emitted is
auditable); two-auditor leakage review.
*Residual:* runtime isolation is NOT yet enforced — this is precisely why
execution remains forbidden after R1 until the isolation gate closes. Any
R1 acceptance of "ready for execution" is explicitly withheld.

**T6 — Unauthorized amendment**
*Surface:* the supersession path.
*Control:* supersession rules (RA-5): no silent tuple change; post-execution
amendment = invalidation only; reason classes machine-checked; registrar
identity per entry; chain + anchor make hidden amendments detectable.
*Residual:* registrar credential compromise; mitigated by registrar identity
being recorded (attribution) and anchors being public.

**T7 — Partial write**
*Surface:* filesystem during any ceremony.
*Control:* two-phase atomic writes (PS-6); ledger entries validate (schema +
chain) before the append is acknowledged; `store-verify` reconciliation
(PS-12); recovery procedure.
*Residual:* none beyond POSIX rename atomicity assumptions. Accepted.

**T8 — Replay**
*Surface:* ingestion channels; ledger appends.
*Control:* unique `entry_index` + unique `registration_id` (L5); evidence
bundles bound to execution ids which are bound to live registrations (L6);
chain position.
*Residual:* predictable-id attacks — ids are registrar-assigned and
pattern-checked, not author-supplied. Accepted.

**T9 — Duplicate registration (cherry-picking)**
*Surface:* RA append.
*Control:* one live registration per frozen tuple (L5); duplicates flagged
by the verifier; supersession-not-duplication policy.
*Residual:* same tuple under distinct `evaluation_id`s is structurally
possible; detected by cross-ledger analytics; governed by owner policy.
Documented as a policy control, not a mechanical one.

**T10 — Clock/timestamp manipulation**
*Surface:* operator machine clock.
*Control:* chain position is the canonical order (RA-8); claimed timestamps
are assertions; external anchoring provides host-side event time;
verification flags large claimed-vs-anchor divergence.
*Residual:* fine-grained time within an anchor window is trust-based. ECP
treats time as *anchored claims*, not proof. Honest limit, documented.

**T11 — Provenance loss**
*Surface:* any reorganization, rename, migration, or manual file operation.
*Control:* versioned-id references + extended linkage checking (PS-8);
manifest-anchored zones; every operation op-logged; migrations must re-run
full verification (future migration tooling gap acknowledged).
*Residual:* manual operations outside the tools are undetectable by
construction — minimized by making the tools the only sanctioned path
(governance, not code).

**T12 — Compromised executor**
*Surface:* the future execution environment.
*Control:* executor sees only the public case; everything it writes is
evidence (append-only, store-assigned ids); system identity pinned;
two-auditor review; validity ≠ outcome (execution may be VALID as an
execution and still FAIL).
*Residual:* a compromised executor can fabricate plausible raw outputs;
detection is audit consistency + future re-execution capability; fundamental
residual, quarantine path exists. This is why the audit layer is mandatory,
not decorative.

**T13 — Compromised author**
*Surface:* case + GT authoring.
*Control:* role separation (author ≠ registrar ≠ executor ≠ auditor);
review pipeline before real registration (future); minimum derivation depth
in the GT contract (schema-recommended ≥ 2 steps); difficulty review;
leakage review by a second party.
*Residual:* author + reviewer collusion — the two-auditor audit at
adjudication is the backstop; at small-team scale this is a documented
human-trust limit (mirrors R0 trust model §6 honesty about single-auditor
fallback).

**T14 — Compromised auditor**
*Surface:* the audit layer.
*Control:* two-auditor default; per-auditor independence declarations;
disagreement + mandatory adjudication; audit records publicly
hash-anchored; auditors have zero write paths (§4.2).
*Residual:* two-auditor collusion at small scale — organizational growth
path is the designed escalation. Honest single-auditor fallback encoding
already exists in the schema.

---

## 6. Architecture options

Three options were developed to decision-grade specificity. All three respect
the inherited invariants (§1.4); they differ in *what is built first* and
*where the scientific guarantee actually lands*.

### Option A — Registration-first

Build the Registration Authority now: ledger, chain, anchoring, ceremony CLI,
public verification. The Protected Store is deferred; commitments are
computed over ground-truth files kept wherever the operator chooses, with
custody as an unenforced convention.

- *Scientific integrity:* the freeze is public and verifiable, but sealed
  ground-truth custody is a convention. GT availability and write-once are
  not enforced; a GT file that changes or disappears is only caught at audit
  time (if it still exists at all).
- *Implementation complexity:* lowest initial surface (one component).
- *Reproducibility:* public verification of the ledger — yes; GT binding —
  detection-only, no custody.
- *Security:* weakest of the three (decision criteria #2 and #3 only
  partially realized).
- *Portability / open-source / open-core:* good.
- *Migration cost:* when the store finally arrives, already-registered cases
  must be retro-fitted with custody (re-seal ceremony, ledger annotations) —
  the ledger gains post-hoc store bindings it was not designed to carry.

### Option B — Protected-store-first

Build the Protected Store now: CAS, zones, op log, access policy, disclosure
control. The Registration Authority is deferred; nothing public references
the store yet.

- *Scientific integrity:* sealed content custody is strong, but there is no
  public freeze at all. Nothing about the store is independently verifiable
  from public data. The store is a vault with no protocol meaning.
- *Implementation complexity:* highest standalone (security machinery) with
  the lowest immediate scientific yield.
- *Reproducibility:* weak publicly — by construction nothing public exists
  to verify.
- *Security:* strong for confidentiality; vacuous for pre-registration.
- *Portability / open-source / open-core:* good.
- *Migration cost:* when the authority arrives, "sealed" objects already
  exist with no registration lifecycle semantics — ambiguous states
  (sealed-but-never-registered, sealed-then-modified-before-any-ledger)
  must be retro-classified.

### Option C — Minimal coupled foundation (the vertical seam)

Build **both components minimally, as one review unit, around one shared
seam**: the store provides custody (CAS write-once, op log); the authority
provides the public freeze (chained ledger, anchoring); the seam is the
commitment + cross-registry binding, verified in both directions. Each
component is minimal: no service, no encryption, no multi-registrar, no
evidence ingestion implementation, no CI — exactly the PS/RA/L requirements
above and nothing more.

- *Scientific integrity:* decision criteria #1–#4 realized at minimum size;
  the binding — which is where the guarantees live — is built first-class.
- *Implementation complexity:* medium (two small components + their seam);
  strictly bounded by the non-requirements lists (§2.5, §3).
- *Reproducibility:* full public verification path (ledger-verify +
  commitment recomputation) plus protected-side custody.
- *Security:* enforcement + detection in depth (three locks on GT, §4.3.4).
- *Portability / open-source / open-core:* good — plain files, offline CLI,
  Apache-2.0 core, commercial layer remains possible without protocol change
  (a hosted vault or hosted registrar can wrap the same formats).
- *Migration cost:* lowest — the seam is the stable interface; every later
  phase (execution, review pipeline, federation) attaches to it additively.

---

## 7. Comparative matrix

Decision criteria are the owner's eight decision rules (§8 of the phase
order), restated; plus two cost axes. `●` = fully realized, `◐` = partially,
`○` = not realized / deferred.

| # | Criterion | Option A (reg-first) | Option B (store-first) | Option C (coupled seam) |
|---|---|---|---|---|
| 1 | Protects the record before execution | ● (public freeze) | ○ (no freeze at all) | ● (freeze + ingestion requires it, L6) |
| 2 | Prevents GT modification after registration | ◐ (detectable, unenforced; no custody) | ◐ (enforced custody, no binding) | ● (enforced + detectable + available, §4.3.4) |
| 3 | Raw evidence preserved auditably | ○ (deferred entirely) | ◐ (zone + manifests, no binding to freeze) | ● (zone + ingest contract bound to registration, §2.6/L6) |
| 4 | Provenance maintained | ◐ (one-sided: ledger only) | ◐ (one-sided: store only) | ● (cross-checked both directions, PS-8) |
| 5 | Independent re-verification | ● (public ledger) | ○ (nothing public) | ● (ledger + commitments + anchor, public data only) |
| 6 | No forced commercial provider | ● | ● | ● |
| 7 | Public metadata never mixed with protected evidence | ● | ● | ● (machine-checked on both sides) |
| 8 | Scales to cross-system evaluation | ● | ● | ● (formats language-neutral; registrar-count-agnostic) |
| — | Implementation complexity | low | high | medium (bounded by non-requirements) |
| — | Migration cost to the full platform | medium (retrofit custody) | medium (retrofit lifecycle) | low (seam is the stable interface) |

Options A and B each fail exactly the criteria that the *other* one
satisfies — the visible signature of the circular dependency (§1.3). Option C
is the only option with no `◐`/`○` in the decision-rule rows.

---

## 8. Recommended architecture

### 8.1 Decision

> **DECISION: Option C — minimal coupled foundation.**
> The Protected Evidence Store and the Registration Authority are built
> together, minimally, as one vertical slice whose center of gravity is the
> seam between them: the commitment-bound, ledger-anchored, write-once
> custody of sealed ground truth, with the public registration freeze
> verifiable from public data alone.

### 8.2 Why (decision-rule traceability)

1. *Protects the record before execution* — the ledger exists and evidence
   ingestion is impossible without a live registration (L6).
2. *Prevents GT modification after registration* — three independent locks
   (§4.3.4): CAS write-once, commitment frozen in the public ledger, op-log
   proof of no re-seal.
3. *Raw evidence preserved auditably* — evidence zone + append-only ingest
   contract designed now (§2.6), implemented at the execution gate.
4. *Provenance maintained* — bidirectional cross-checking (PS-8).
5. *Independent re-verification* — `ledger-verify` from public data only (L4).
6. *No forced commercial provider* — offline CLI, plain files, no service,
   no cloud (§3.2 realization (c)).
7. *Public metadata never mixed with protected evidence* — zones +
   boundary scanner on the public side + role matrix on the store side.
8. *Cross-system scalability* — provider-neutral formats, additive
   federation path (§3.2 (d)).

### 8.3 Answer to the phase question

> **"Protected Store first or Registration Authority first?"**
> **Neither — the seam first.** Building either component alone either
> defers custody (A) or defers the public freeze (B), and in both cases the
> missing half must later be retrofitted into records/states that were never
> designed to carry it. In the coupled slice there is still a *build order*:
> the store's CAS lands first (the commitment ceremony needs a custody
> target), then the registration ceremony binds to it, then anchoring, then
> the public verification tooling — but they are one review unit with one
> acceptance gate.

### 8.4 Concrete shape (design sketch, nothing implemented)

```
operator site
├── ECP/                       public repo (contracts, schemas, tools)  [exists, R0]
├── ecp-ledger/                public ledger repo (O1: vs path in ECP)  [R1-I]
│     entries/000001.json …   chained ledger entries                    [R1-I]
│     ANCHOR.json              {ledger_id, count, head_entry_hash}      [R1-I]
└── protected-store/           OUTSIDE both repos                        [R1-I]
      store.json               identity + zone manifests               [R1-I]
      zones/sealed-gt/         CAS blobs  ab/<sha256>.json             [R1-I]
      zones/hidden-cases/      reserved                                [R1-I]
      zones/evidence/          reserved + ingest contract              [R1-I, deferred impl]
      zones/exports/           disclosure-governed outputs             [R1-I]
      registry/seals.json      case↔commitment↔blob↔registration index  [R1-I]
      oplog/000001.json …      hash-chained operation log              [R1-I]
```

Ceremonies (CLI, offline): `store-init` → `store-seal` (GT draft → CAS blob
+ seal record + op-log append) → `register` (case + seal → registration
record → ledger append) → `anchor-publish` (ledger HEAD → public repo commit
+ push). Verification (public): `ledger-verify`, `verify-commitment`
(exists), `boundary-scan` (exists, extended). Verification (protected):
`store-verify` (blobs ↔ registry ↔ op log ↔ zone manifests).

---

## 9. Explicit rejected alternatives

1. **Option A (registration-first)** — rejected: leaves ground-truth custody
   as convention; decision criteria #2/#3 only partially realized; retrofit
   cost on real registrations.
2. **Option B (protected-store-first)** — rejected: a vault without a public
   freeze has no protocol meaning; nothing independently verifiable; worst
   scientific yield per unit of security machinery.
3. **Cloud / central registration service** — rejected (provider neutrality,
   open-core boundary, offline operability, attack surface; §3.2 (a)).
4. **Local service/daemon + database authority** — rejected (mutable-state
   semantics vs append-only; auditability of plain files; §3.2 (b)).
5. **Blockchain / external consensus for the ledger** — rejected: an
   external trust dependency (directly violates decision rule #6 in spirit:
   it *does* force a specific external provider/infrastructure); consensus
   adds nothing a hash chain + public Git anchoring does not already provide
   at this scale; fees/infrastructure conflict with open scientific core.
6. **Ledger inside the ECP repository (vs separate ledger repo)** — rejected
   *as default*, kept as open decision O1 with a recommendation: mixing
   protocol contracts and growing data history in one repo couples release
   cadences and bloats the contract repo; a dedicated public ledger repo
   keeps ECP contract-only. (Owner ratifies.)
7. **Encryption-at-rest at R1-I** — rejected for now (O3): adds key-custody
   complexity with no effect on the *integrity* guarantees (the actual R1
   subject); confidentiality at current scale rests on machine access
   control; documented as hardening escalation.
8. **Multi-registrar federation at R1-I** — rejected for now (O4): designed
   for, additive later; single-registrar with recorded identity suffices at
   current scale.
9. **Designing the store as a service API "for future flexibility"** —
   rejected: speculative generality; the R0 architecture principle (minimum
   walking skeleton, contracts first) forbids it.
10. **Deviating from / extending `schemas/registration.schema.json`
    semantics in R1-I** — rejected: the registration record contract is
    stable; the ledger *wraps* records, it does not change them. Additive
    `ledger-entry` + `store-manifest` schemas only, under a `schema_version`
    bump (I7).

---

## 10. Open owner decisions

Each decision is required before (or at) the M3-R1-I order. Recommendations
are the executor's; ratification is the owner's.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| O1 | Ledger home | (a) dedicated public ledger repository `ecp-ledger`; (b) `ledger/` path inside the ECP repository | **(a)** — keeps the contract repository clean; ledger scales independently; anchor push is one commit per registration |
| O2 | Anchor cadence | per-registration push vs periodic batch | **per-registration** at current scale (minimizes T1/T2/T3 anchor windows); revisit at volume |
| O3 | Store encryption at rest | now vs deferred | **deferred** — integrity is the R1 subject; document as hardening item with escalation trigger (multi-party access) |
| O4 | Registrar model | single registrar (identity recorded per entry) vs multi-registrar keys now | **single registrar now**; federation is additive (§3.2 (d)) |
| O5 | Development registrations | dev entries inside the public ledger (marked `scope: development`) vs separate throwaway dev ledger | **separate dev ledger, never pushed**; the public ledger starts empty and is reserved for real registrations — the scientific record is never polluted by infrastructure testing |
| O6 | GT disclosure timing | per-case at adjudication vs batch post-evaluation | **per-case at adjudication** (matches the audit contract); batch disclosure only as an explicit later decision |
| O7 | Evidence-zone implementation | design-only at R1-I (recommended) vs full ingest implementation | **design-only** — ingestion lands with the execution gate, which owns the executor-side half of the contract |
| O8 | Schema bundle version | additive bump `0.1.0 → 0.2.0` in R1-I (ledger-entry + store-manifest schemas) vs internal formats without schemas | **additive bump** — every artifact deserves a machine-validatable contract (R0 principle); additive-only per spec §14 |

---

## 11. Implementation boundary (scope of the future M3-R1-I order)

**IN scope for M3-R1-I (nothing of which is implemented by this document):**

- `src/ecp/store.py` (or package): store identity, CAS write-once seal,
  zones, registry index, hash-chained op log, atomic writes, `store-verify`.
- `src/ecp/ledger.py`: entry construction, chain append, chain + anchor +
  duplicate verification.
- CLI: `store-init`, `store-seal`, `store-verify`, `register`,
  `ledger-verify`, `anchor-publish`.
- New schemas (additive, `schema_version` 0.2.0 pending O8):
  `ledger-entry.schema.json`, `store-manifest.schema.json`.
- `boundaries.py` extension: ledger rules on the public side (anchor
  consistency, no sealed content in any public path, reserved-dir rules
  updated for the ledger repo layout).
- Tests for all of the above, including tamper-detection batteries (edit /
  reorder / remove / duplicate / partial-write) and cross-component
  round-trips.
- Docs addenda: ARCHITECTURE, TRUST-MODEL, SECURITY, REPRODUCIBILITY
  updated from "future phase" to "R1-I implemented" where applicable.
- The public ledger repository created empty (O1) with its README and
  anchor file, containing **zero** registration entries.

**OUT of scope for M3-R1-I (explicitly forbidden, same list as this phase
plus):**

```text
NO execution · NO adapters · NO model invocation
NO case authoring · NO real case registration · NO development-case registration into the public ledger
NO ground-truth generation beyond test fixtures (synthetic, clearly marked, never sealed as real)
NO evidence ingestion implementation
NO CI changes · NO JARVIS changes · NO CA0 changes · NO import of any historical artifact into ECP
NO commercial features · NO service APIs · NO encryption · NO multi-registrar
NO history rewrite of any repository
```

**Migration-surface minimization:** every R1-I artifact is a new file or a
new additive schema; no existing R0 file's semantics change. The
`schema_version` bump (O8) follows spec §14 (additive = minor bump).

---

## 12. Acceptance criteria

### 12.1 For this document (M3-R1 discovery + decision — checked now)

| # | Criterion | Status |
|---|---|---|
| 1 | Baseline integrity (HEAD == origin/main == remote; worktree clean; fsck clean) | **PASS** (§0) |
| 2 | Scientific isolation (frozen external systems, candidate pools, historical records untouched; nothing imported into ECP) | **PASS** (§0) |
| 3 | Protected-store discovery complete (classification, PS-1..PS-14, zones, access, disclosure, recovery, export boundary) | **PASS** (§2) |
| 4 | Registration discovery complete (RA-1..RA-8, alternatives incl. non-service realizations, ledger L1..L6) | **PASS** (§3) |
| 5 | Trust boundaries explicit (diagram, read/write matrix, no-path rules) | **PASS** (§4) |
| 6 | Threat analysis complete (T1–T14, each with surface/control/residual) | **PASS** (§5) |
| 7 | Architecture options A/B/C complete, each on all evaluation axes | **PASS** (§6) |
| 8 | Comparative matrix against the owner's eight decision rules | **PASS** (§7) |
| 9 | Decision EXPLICIT (Option C) with rule-by-rule traceability | **PASS** (§8) |
| 10 | Rejected alternatives EXPLICIT (10 items, with reasons) | **PASS** (§9) |
| 11 | Open owner decisions EXPLICIT (O1–O8 with recommendations) | **PASS** (§10) |
| 12 | Implementation boundary EXPLICIT (IN/OUT lists, migration note) | **PASS** (§11) |
| 13 | Implementation prohibition respected by this phase (no schema/code/db/registration/case/execution changes; one commit containing this document only — the execution worklog lives outside this repository) | **PASS** |
| 14 | Worktree clean after the single commit; remote synchronized | verified at commit time |

### 12.2 For the future M3-R1-I gate (defined now, checked then)

1. `store-init` → `store-seal` → `store-verify` round-trip on a synthetic
   fixture; second seal of the same target with different content REJECTED;
   identical content idempotent.
2. `register` produces a schema-valid registration record whose commitment
   matches the sealed blob and the public case commitment; divergent
   commitments REJECTED before any ledger append.
3. Ledger chain verifies; tamper battery (edit / remove / reorder / duplicate
   / partial-write on entries) all DETECTED by `ledger-verify`.
4. `anchor-publish` produces the public anchor; independent verification from
   public data only succeeds; tampered ledger-with-stale-anchor DETECTED.
5. `boundary-scan` extended and CLEAN on the ECP repo and the ledger repo;
   synthetic violations DETECTED.
6. Op log chain verifies; cross-component checks (case ↔ commitment ↔ blob ↔
   registration) pass; tamper variants DETECTED.
7. Full test suite green (229 existing + new), run before and after the R1-I
   commit.
8. Zero real cases, zero real registrations, zero executions, zero sealed
   real ground truths; public ledger repository exists and is EMPTY of
   entries.
9. JARVIS / external frozen systems / candidate pools untouched (hash
   verification).
10. ONE commit policy respected; no force-push; no history rewrite;
    remote synchronized after push.

### 12.3 Scientific status statement (unchanged by this phase)

Nothing in this document or its parent phase constitutes, implies, or claims
any experimental result. The architecture decided here is infrastructure.
ECP's scientific validity remains **unproven and unclaimed** until properly
registered, executed, audited evaluations exist — none do.
