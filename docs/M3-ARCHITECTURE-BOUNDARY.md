# M3-ARCHITECTURE-BOUNDARY.md — M3 Architecture & Boundary Design

**Status:** G0 design document (frozen by order M3-G0 v3)
**Mode:** READ-ONLY DISCOVERY + SCIENTIFIC DESIGN + AUTHORIZATION
**Baseline:** `5449951586f9e91b4ba9950cbb66086c304337f0` (ECP 0.4.0)
**Companion documents:** `M3-CHARTER.md`, `M3-THREAT-INDEPENDENCE.md`

---

## 1. Purpose and scope

This document freezes the M3 architecture boundary: repository architecture,
case lifecycle, execution lifecycle, evidence model, provenance,
reproducibility, the public/protected boundary, the trust model, and the
open-core/commercial boundary. It is a *design* document: no implementation,
no case authoring, no registration, no execution. Every element marked
**[exists]** is already implemented at the baseline commit; elements marked
**[designed]** require a separate implementation order before use.

## 2. Current foundation inventory (at `5449951`, ECP 0.4.0)

| Layer | Component | Status |
|---|---|---|
| Identity | `ECP-IDENTITY.json` pinned protocol/schema versions | **[exists]** |
| Contracts | 18 schemas: protocol, system, evaluation, case, ground-truth (format only), registration, execution, evidence, audit, manifest, ledger-entry, store-manifest, case-candidate, case-review, review-run, review-adjudication, case-amendment | **[exists]** |
| Canonicalization | ECP-CANONICAL-JSON-1.0 (`src/ecp/canonical.py`) | **[exists]** |
| Hashing/commitments | sha256 document/artifact/self-referential hashes (`src/ecp/hashing.py`) | **[exists]** |
| Verification boundary | integrity-only verification, never scientific adjudication (`src/ecp/verification.py`) | **[exists]** |
| Public/protected boundary | reserved dirs, GT sealing, boundary-scan (`src/ecp/boundaries.py`) | **[exists]** |
| Linkage | cross-document provenance checks (`src/ecp/linkage.py`) | **[exists]** |
| Manifests | deterministic artifact-set manifests (`src/ecp/manifest.py`) | **[exists]** |
| Protected store | content-addressed store + store-manifest (`src/ecp/store.py`) | **[exists]** |
| Registration ledger | append-only, hash-chained, anchored; **at genesis (0 entries)** (`src/ecp/ledger.py`) | **[exists]** |
| Case review pipeline | candidate intake → deterministic three-state review → review-run with determinism re-derivation + engine profiles (`src/ecp/review.py`, `src/ecp/candidates.py`) | **[exists]** |
| Adjudication & amendment | owner-adjudication records; versioned amendments with two-phase representation-bias disclosure (`src/ecp/adjudication.py`) | **[exists]** |
| Version compatibility | 0.1.x → 0.2.0 → 0.3.0 → 0.4.0 explicit matrix (`src/ecp/versions.py`) | **[exists]** |
| Provider neutrality | no provider assumptions in core (spec §12) | **[exists]** |
| Tests | 482/482 at baseline | **[exists]** |
| Execution orchestration | stage runner, per-layer policy enforcement, adapter contracts | **[designed]** — this document |
| Audit orchestration | dual-auditor workflow, κ computation, audit freeze tooling | **[designed]** — this document |
| Analysis pipeline | preregistered analysis configurations | **[designed]** — charter §8 |
| System admission | identity-record capture, eligibility evidence intake | **[designed]** — threat doc §3/§5 |

## 3. Case population principle (order §8)

The case ecosystem supports: multiple reasoning families; difficulty
levels; case sizes; system types; rotating cases; hidden cases; public
development cases; preregistered evaluation sets; future expansion.

**The mechanism that makes case growth a data change, not a protocol
change:** cases enter through the existing intake pipeline
(candidate → review → qualification/adjudication) and freeze through
ledger registration. Case families, difficulty, and size are *fields of
case data*, not code paths. Adding a new reasoning family or a thousand
more cases touches zero schemas, zero core modules, and zero spec
sections. The 20-case qualification set and T1's 43 are pilot
populations — **not architectural constants** (§12, §14).

Case-set classes and their boundary:

| Class | GT handling | Visibility | Use |
|---|---|---|---|
| development (public) | none or public illustrative | public repo, clearly marked | builders, tooling tests — **never scoring** |
| preregistered evaluation | sealed (commitment public) | content private until execution | M3 stages |
| hidden (held-out) | sealed, commitment-only | never public | rotation/adversarial defense |
| retired | sealed, archived | manifest-only | leak/incident response |

## 4. Case lifecycle (design)

```text
authoring ── validation ── review ── qualification ── registration ── frozen versioning
     │                        (three-state)   (adjudication)      (ledger append)
     │                                                                 │
     └── amendment (two-phase disclosure) ←────────────────────────────┘
                                         └── retirement (incident path)
```

### 4.1 Authoring (future stage; O-02/B2 owner authorization)

Every authored case carries an **authoring provenance** record:

```text
author identity class   (person/role/independence class — threat doc §2)
authoring model/system  (model, version, provider — or "human")
prompt                  (pinned prompt text/hash used at authoring)
available information   (what the author could see: dev cases? spec? prior results? — inventory)
authoring environment   (pinned environment)
validation procedure    (how the case was checked before intake)
independence limitations (declared, e.g. model-family overlap — a fact, not a disqualifier per se)
```

Hard prohibitions (machine-checkable where possible):

- no author access to hidden execution outcomes (none exist at authoring
  by construction — outcomes postdate authoring);
- no outcome-driven case modification after registration (amendments
  carry `not-outcome-dependent` statements — the CA0-A mechanism);
- no post-hoc Ground Truth changes (GT sealed at registration; changes
  require new case versions with full disclosure);
- no contamination from implementation details (authors of eval cases
  work from the public spec face, not from runner internals);
- no leakage from private repositories (information inventory declares
  exposure);
- no accidental encoding of the expected solution (validation procedure
  includes a solution-leak review dimension — review dimension of the
  existing pipeline).

Authoring provenance receives its own version identity; newly authored
material is **never** retroactively represented as pre-existing
(M3-CA0-B §3 rule, carried forward).

### 4.2 Validation & intake **[exists]** — candidate schema, extraction, deterministic review (three-state), engine-profile re-derivation.

### 4.3 Qualification/adjudication **[exists]** — owner-adjudication records applying written rules to preserved evidence; amendments with two-phase representation-bias disclosure (`draft_hash` + `amendment_hash` machine-enforce post-draft disclosure timing).

### 4.4 Registration **[exists — machinery; zero entries]** — the registration freezes the (evaluation, case version, target identity) tuple in the append-only ledger *before* execution. Registration is the anti-Goodhart immutability point.

### 4.5 Frozen versioning **[exists]** — case versions are content-hashed; v2 views preserve v1 records (CA0-A precedent).

### 4.6 Amendment **[exists]** — two-phase disclosure; full re-review; nothing inherited.

### 4.7 Ground-truth validation stage (design; O-04/B4 owner authorization)

A **GT validation stage** sits between qualification and registration (or
between registration and execution, per the owner's ruling):

```text
sealed GT claim ── validation procedure (independent re-derivation / dual-auditor)
                          │
            ┌─────────────┼──────────────┐
            ▼             ▼              ▼
       CONFIRMED      REJECTED      retained-forwarded
   (GT defensible)  (defect — case   (nondeterminate designs:
                     rejected/needs   a separate reading rule)
                     amendment)
```

For **designed-nondeterminate** cases (C-004 class): the GT reading
"contradiction → cannot be determined" must be *confirmed as a defensible
GT* by the validation procedure — never silently converted. The forwarded
flag `FWD-GT-NONDETERMINATE` persists until the owner-authorized procedure
runs. The C-004 blocker (O-04) is resolved by authorizing this stage with
an explicit reading rule for nondeterminate designs.

### 4.8 Novelty evidence (design; O-01/B1 owner decision)

Admissible shapes for an external novelty-evidence mechanism:

```text
(a) third-party attestation   — an external party certifies bounded novelty against a declared corpus/method
(b) registered-corpus method  — novelty bounded against a pinned, dated corpus with method disclosed
(c) bounded-novelty acceptance — owner accepts an explicitly bounded basis (e.g., "novel within the declared corpus")
(d) NO MECHANISM              — OQ-NOV-EXTERNAL stays OPEN, absence explicit, no eligibility by inference
```

Under (d), no candidate becomes eligible through novelty; that is a
permanent honest state, not a failure. The executor may not invent or
reconstruct historical novelty evidence.

## 5. Execution lifecycle (design)

```text
stage authorization (owner order)
        │
system admission (threat doc §3 eligibility evidence + identity record)
        │
case-set binding (registered set + versions)
        │
preregistration freeze (stage plan: policies, repetitions, analysis config)
        │
controlled execution loop:
    execution declaration (layer L1–L5 + policy set + identity)
        → controlled run (policies enforced; attempts logged)
        → raw evidence capture (verbatim)
        → evidence bundle assembly + manifest + hash chain
        → store (protected)
        │
(post-execution) audit (dual) ─ adjudication ─ classification ─ analysis
```

Every stage's runner, adapter, and policy set are pinned by digest in the
preregistration freeze (anti-tamper, threat doc §9). Executions produce
attempts; retries are separate logged attempts; the final attempt's
evidence is the bundle of record with the attempt history preserved.

## 6. Evidence model (order §13)

Minimum evidence bundle per execution:

```text
Protocol Version       Case Version          Target Version (identity record)
Configuration          Environment           Input
Raw Output             Execution Trace       Tool Log
Runtime Metadata       Evidence Manifest     Cryptographic Hashes
Outcome Classification Audit Record          Analysis Configuration
```

Input is the frozen case content as delivered; Raw Output is verbatim
(no post-hoc correction — spec §9.4). Execution Trace and Tool Log capture
the L3–L5 machinery when present (L1: trace = API call record).

### 6.1 The five evidence properties (distinct, never interchangeable)

| Property | Meaning | Minimum basis |
|---|---|---|
| **re-runnable** | the execution can be run again in the pinned environment | pinned environment + input + policy set |
| **reproducible** | re-running yields equivalent (or bit-identical, if claimed) output | re-run comparison record |
| **auditable** | a third party can follow the chain and check every claim | full bundle + provenance chain (§7) |
| **cryptographically verifiable** | integrity of every artifact is hash-checkable | manifest + hash chain + store |
| **publicly inspectable** | anyone can inspect (possibly via commitments rather than content) | public commitments / redacted public view |

A bundle may be auditable without being re-runnable (opaque API);
cryptographically verifiable without being publicly inspectable (sealed
content + public commitments). M3 artifacts MUST state exactly which
properties they claim — mirroring the R0 rule that these classes are never
used interchangeably (spec §11).

## 7. Provenance chain (order §14)

```text
Case ── Registration ── Execution ── Raw Evidence ── Manifest ── Audit ── Classification ── Analysis
```

| Transition | Artifact (mechanism) | Status |
|---|---|---|
| Case | case object, content hash, sealed GT commitment | **[exists]** |
| Registration | ledger entry (append-only, hash-chained) | **[exists]** |
| Execution | execution record + identity record + policy set | **[designed]** (schema **[exists]**) |
| Raw Evidence | evidence objects, verbatim preservation | **[designed]** (schema **[exists]**, store **[exists]**) |
| Manifest | deterministic manifest + hash chain | **[exists]** |
| Audit | audit records, dual-auditor + κ + freeze | **[designed]** (schema **[exists]**) |
| Classification | mechanical classification from sealed GT + audit adjudication | **[designed]** |
| Analysis | preregistered analysis configuration → outputs | **[designed]** |

**Rule (order §14):** no result may depend solely on an unverified
narrative report. Every link above is a machine-checkable artifact; the
existing linkage checker pattern (`src/ecp/linkage.py`) extends to the full
chain as each designed stage is implemented under separate order.

## 8. Reproducibility architecture

Three verification levels, all integrity-only (never adjudication):

1. **Re-derivation** — deterministic recomputation from retained inputs
   (the pattern proven by `review-verify`: engine profiles + bit-exact
   re-derivation of preserved runs — INTACT checks on R1/R2 today).
2. **Re-run** — executing again under the pinned environment (produces a
   *new* execution unit with its own identity; equivalence is measured
   and reported, never assumed).
3. **Third-party verification** — an external party, given the bundle +
   public tools, re-derives hashes and classification. Public tools
   (validators, boundary-scan, manifest verification, linkage) are part
   of the public core (§9). For protected content, the third party
   verifies commitments rather than content.

## 9. Public/protected boundary (order §20)

### 9.1 Public scientific core (this repository)

```text
specification        schemas            reference runner (future impl.)
validators           verification tools public examples
reproducibility utilities            documentation
```

The repository is a **provenance and distribution layer, not the complete
scientific trust boundary** (spec §6.1 — [exists]). Sealed-GT commitments
are published here; sealed values never are (boundary-scan enforced).

### 9.2 Protected evaluation layer

```text
hidden cases         sealed Ground Truth      private case vault
protected scoring    controlled execution     protected evidence
private evaluation metadata
```

The protected layer lives outside the public repository (local CAS store
+ anchored ledger commitments **[exists]**; vault management **[designed]**).

### 9.3 Trust model

Trust chain: (1) protocol correctness — public, reviewable core + tests;
(2) integrity — hashes/manifests/ledger (cryptographic); (3) process —
preregistration before execution, audit after (procedural); (4) humans —
independence declarations per dimension (declarative, bounded by §2.3
bounded-claim rule); (5) environment — pinned and residue-scanned
(operational). Residual trust assumptions are stated, not hidden
(threat doc §14). The public repo is trusted for distribution; the
scientific trust boundary is the *protocol + protected layer + declared
independence structure*.

## 10. Open core / future commercial boundary (order §21 — conceptual only)

**Open scientific core (never closed):** the reproducible scientific
protocol and its public verification infrastructure — spec, schemas,
canonicalization, hashing, verification tools, public examples,
reproducibility utilities, public documentation. Commitment: the
verification path for any published result remains fully public; a result
that cannot be verified with public tools is never presented as
scientifically established by ECP.

**Future commercial layer (no implementation authorized in G0):**
private evaluations; hosted execution; enterprise workspaces; private
case vaults; continuous evaluation; advanced dashboards; API services;
governance/access control. Boundary rule: the commercial layer may add
convenience, hosting, and privacy — it may never remove or weaken the
public verification path, the sealing rules, or the provenance chain for
any artifact presented as an ECP result. Pricing/implementation are out
of G0 scope.

## 11. Case-count and population scalability (SQ6)

Growth is data: no schema field, code constant, or spec rule caps the
number of cases, systems, providers, executions, or repetitions. Costs
scale (ledger verification is O(n) in entries; store is content-addressed
and unbounded; review determinism is per-run). The pilot populations
(43 / 20) appear in this design **only** as historical context. The
§26 audit (order) confirms: no design element makes 20 cases, JARVIS,
one model, one provider, one benchmark, or one environment a permanent
constraint — strata, layers, families, and rotation are structural;
counts never are.

## 12. Repository architecture (public repo shape)

```text
spec/        — normative protocol (public)
schemas/     — machine-validatable contracts (public)
src/ecp/     — provider-neutral core (public)
tools/       — CLI: validate, boundary-scan, manifest, store, ledger, review, review-verify (public)
examples/    — format illustrations only (public, marked)
cases/       — reserved: registered public cases (ledger-referenced) — dev class only
evaluation/  — reserved: stage records (preregistration plans, public parts)
evidence/    — reserved: public/commitment side of evidence (protected content never here)
verification/— reserved: public verification instructions/results
docs/        — this document set
```

Reserved-directory discipline is machine-checked (boundary-scan **[exists]**);
the reserved dirs hold README.md only at the current state and fill only
under separate implementation orders.

## 13. Cross-document consistency

- Charter §5 units ↔ this doc §5 execution lifecycle ↔ threat doc §6
  layers/policies: the execution unit is the crossing point; consistent.
- Charter §8 endpoints ↔ this doc §6 evidence properties ↔ threat doc
  §11 audit model: ECCE counts units with complete bundles + valid
  identity + mechanical classification; consistent.
- Charter §7 case population ↔ this doc §3/§4 lifecycle ↔ threat doc
  §10 anti-Goodhart: hidden/rotating/dev classes exist in one place
  (§3 table); consistent.
- Open decisions O-01…O-04 (charter §12) ↔ this doc §4.7/§4.8 + threat
  doc §8.4: each open decision has exactly one resolution framework;
  no duplicates, no gaps.

## 14. G0 boundary compliance

This document adds no code, no schemas, no registrations, no executions.
It commits to the repository as design documentation only (the M3-R1
precedent: decision-only stages commit documents additively; the public
protocol code and contracts are untouched). Historical integrity of
T1/M1/M2/frozen manuscript/submission/M3-R0…M3-CA0-A is verified in the
G0 executor report (§26 of the order).
