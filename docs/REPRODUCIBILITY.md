# ECP Reproducibility Model

Version 0.1.0-draft (R0 foundation).

## 1. The four classes are NOT synonyms

ECP defines and keeps distinct four claims that evaluation literature
often conflates:

| Class | Claim | What it requires |
|---|---|---|
| **Reproducible** | An independent party, starting from the *same artifacts*, recomputes the *same committed bytes and hashes*, and (for results) obtains the same adjudicated outcome under the frozen conditions. | pinned protocol/case/system versions, frozen conditions, sealed ground truth, preserved evidence, verification tooling |
| **Re-runnable** | An independent party can *execute the same evaluation again* (new invocations) under the declared system identity and conditions. | system identity contract (model+provider+API+prompt+framework+tools+adapter+runtime), execution harness (future), environment description |
| **Auditable** | An independent auditor can *verify what was done* — integrity of every artifact, linkage of every reference, immutability of registration — without re-executing anything. | manifests, commitments, append-only registration, evidence bundles, audit records |
| **Publicly inspectable** | Anyone can read the protocol, schemas, tooling and (public) records and understand what the evaluation claims to measure. | this repository: spec, schemas, source, docs, examples |

A statement about an ECP result MUST name the class it claims. "Anyone
can reproduce this" is three different statements; conflating them is a
protocol violation, and the specification (§11) makes the distinction
normative.

## 2. Why the distinction matters here

- **Reproducible without re-runnable**: hashes and commitments verify
  (audit-grade) even when the model endpoint no longer exists — the
  *record* is reproducible, the *run* is not.
- **Re-runnable without reproducible**: same system identity, new
  invocations — legitimate for stochastic systems, but then outcome
  stability is a statistical claim, not a bitwise one.
- **Auditable without either**: integrity and linkage hold even when
  neither recomputation nor re-execution is available.
- **Publicly inspectable without any of the above**: the protocol text
  is open even while no evaluation exists — which is exactly the R0
  state.

## 3. Minimum artifact set for external reproduction/audit

For a future ECP result to be auditable (and reproducible where
possible) by an external researcher, the evaluation must expose:

1. **Protocol identity** — `protocol_version`/`schema_version` the
   artifacts were produced under (pinned in `ECP-IDENTITY.json` of that
   release).
2. **System identity record** — the full versioned system configuration
   (`schemas/system.schema.json`), not a model name.
3. **Case set with commitments** — public case documents, each binding
   its protected ground truth by sha256 commitment.
4. **Registration record(s)** — the frozen tuple (protocol, case,
   target, condition, success criterion, verification rule) with
   `registration_hash` and timestamp.
5. **Execution record(s)** — verbatim input, verbatim raw output,
   declared environment and access paths, validity/outcome.
6. **Evidence bundle(s) + manifest** — hashed artifacts and the
   manifest anchoring them.
7. **Audit record(s)** — auditor independence declarations,
   classification, disagreement/adjudication.
8. **Verification tooling** — this repository at the matching
   `repository_version`/commit, so canonicalization and hashing are
   byte-identical.
9. **Environment description** — sufficient runtime description to
   understand (not necessarily repeat) the execution context.

Items 1–8 have contracts at R0; item 9 has a schema slot. None of the
*content* (cases, executions, evidence) exists yet — that is the R0
scope boundary.

## 4. What R0 already guarantees

- **Byte-level determinism**: canonical serialization and hashing are
  pure functions of content — pinned by tests including cross-process
  determinism.
- **Manifest determinism**: fixed inputs + pinned timestamp →
  byte-identical manifests.
- **Recomputable seals**: the example case's commitment recomputes
  exactly from the example ground truth — the mechanism an external
  party will use on real cases later.
- **Auditable tooling**: the verification layer re-verifies every
  integrity claim from public data alone.

## 5. What R0 explicitly does not guarantee

- No re-runnability (no adapters, no execution machinery).
- No outcome reproducibility (no results exist).
- No claim that the protocol itself is validated (see README status).
- Float-exact cross-language canonicalization beyond the shortest
  round-trip convention — spec §5 recommends integers/strings for
  stability-critical fields.
