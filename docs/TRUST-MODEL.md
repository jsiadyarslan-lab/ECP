# ECP Trust Model

Version 0.1.0-draft (R0 foundation).

## 1. The question this document answers

Before any evaluation runs, the protocol must be explicit about **who
and what is trusted, for what, and to what degree**. ECP's answer is
conservative: trust is narrow, declared, and verifiable; everything
else is treated as untrusted input.

## 2. Baseline: the evaluated side is never trusted

An evaluated agent may be:

```
honest        — did the task as asked;
mistaken      — believes it succeeded, did not;
adversarial   — actively games the evaluation;
contaminated  — already saw the case or the answer.
```

The protocol MUST NOT distinguish these by the agent's own testimony.
Consequently the following are **never blindly trusted**:

- evaluated agents' self-reports;
- evaluated models' claimed reasoning;
- client-provided scores or classifications;
- client-provided evidence bundles;
- self-reported execution claims ("I ran it, it passed");
- raw repository contents (see §4).

Controls that follow from this at the contract level: verbatim raw
output preservation (no post-hoc correction), declared model/tool
access paths, declared environment isolation, integrity anchors
(manifests) on evidence, and audit records that carry per-auditor
independence declarations rather than a blanket "independent" label.

## 3. Provenance as the trust currency

What ECP trusts instead is **deterministic provenance**: identities
(protocol/system/case versions), commitments (case ↔ ground truth),
manifests (evidence ↔ artifacts), and append-only registration. These
are recomputable by anyone with the public repository — that is the
point of `ECP-CANONICAL-JSON-1.0` and the fixed hash rules in
[spec/ECP-SPEC.md](../spec/ECP-SPEC.md) §7.

Note the limit: recomputation proves *integrity* (these are the same
bytes), never *validity* (this is a good measurement). See §5.

## 4. The public repository is not the trust boundary

The public Git repository is a provenance and distribution layer.
Specifically:

- it does **not** hold hidden cases or sealed ground truth — those live
  in a protected store outside the repository, bound to public cases by
  sha256 commitments;
- it does not itself certify anything: a document being present in the
  repository says only that it validated against a schema, not that its
  claims are true;
- the boundary is machine-enforced (`tools/ecp_cli.py boundary-scan`):
  no ground-truth content outside `examples/` format illustrations,
  reserved directories empty, every case commitment-bearing.

## 5. Verification ≠ adjudication

The verification layer answers integrity questions only:

```
"Is this the artifact it claims to be?"    — verification (code, now)
"Is this result scientifically valid?"     — adjudication (audit, later)
```

A cryptographically intact result is not automatically a scientifically
valid result. The reference implementation marks this boundary in its
docstrings, and the specification forbids presenting verification
outcomes as scientific judgments. No code in this repository adjudicates
anything.

## 6. Audit independence

The audit contract encodes two honest modes:

- **two-auditor** (default): two auditors, each with declared
  independence along procedural / personal (optionally organizational)
  axes;
- **single-auditor-fallback**: permitted, but the record MUST declare
  `personal_independence_maintained: false` with a justification. A
  single-auditor record MUST NOT be labeled or presented as personally
  independent — the schema makes the honest declaration the only valid
  encoding of that mode.

Disagreements are recorded, not smoothed over; adjudication is mandatory
when a disagreement exists.

## 7. Trust in this repository's own contents (R0 self-assessment)

At R0 the repository contains contracts and tooling only — no cases, no
executions, no evidence. Its trustworthiness currently rests on: the
test suite (229 tests), the boundary scanner, and the determinism of
the core. It claims nothing else. In particular it does not claim that
the protocol itself has been scientifically validated (see README
status banner).

## 8. Threat boundary

The concrete threats this model must eventually withstand — hidden-file
inspection, ground-truth access, scoring-code access, benchmark
tampering, evidence modification, unauthorized model invocation,
unauthorized network access, result exfiltration, environment
manipulation, repository exploitation — are enumerated with their R0
status (documented, implementation deferred) in
[SECURITY.md](SECURITY.md).

## 9. Reader's summary

- Trust the recomputation, not the claim.
- Trust the commitment, not the answer's neighborhood.
- Trust the declaration of independence mode, never its absence.
- Trust integrity checks only as integrity checks.
- And at R0: trust that nothing has been evaluated yet — because
  nothing has.
