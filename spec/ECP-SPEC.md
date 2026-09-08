# ECP Specification

**Version 0.1.0-draft — R0 Repository Foundation**

Status: normative for the R0 repository foundation. This document uses
RFC 2119-style language (MUST / MUST NOT / SHOULD / MAY). The repository
root `ECP-IDENTITY.json` pins the versions this specification is normative
for:

```
protocol_name      ECP
protocol_title     Evidentiary Evaluation Protocol
protocol_version   0.1.0
protocol_status    draft
schema_version     0.1.0
repository_version 0.1.0
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

## 13. R0 scope boundary

R0 provides the foundation only. The following do not exist and MUST NOT
be claimed: model adapters, benchmark execution, external model calls,
scientific case generation, case registration, scoring, hidden benchmark
publication, commercial features, and M3 validation. Anything beyond the
foundation is a future gate, recorded explicitly — never silently
implemented.

## 14. Change policy

Changes to canonicalization, hashing, sealing, or any schema require a
version bump (`schema_version` and/or `protocol_version`) and updated
tests. Canonicalization and hashing rules are stability-critical: any
change to them invalidates every existing commitment by definition, and
MUST be treated as a protocol major-version event.
