# ECP Security Foundation — Threat Boundary

Version 0.2.0-draft (R1-I minimal coupled foundation, additive over R0).

## 1. Status

The full security posture remains **documented, not fully implemented**.
R1-I implemented the integrity half of the boundary decisions below
(hash-chained append-only ledger, CAS write-once store, atomic writes,
external anchoring, duplicate/replay control, tamper-evidence verified by
tests). Confidentiality enforcement at the filesystem/host level
(encryption at rest, access control beyond tool-enforced role rules,
runtime isolation) remains deferred per the M3-R1 decision (O3) and the
threat model in
[docs/M3-R1-ARCHITECTURE-DECISION.md](M3-R1-ARCHITECTURE-DECISION.md)
(T1–T14, each with residual risk stated honestly). Nothing here is a
claim of complete current protection.

## 2. Asset model

| Asset | Where it lives (future) | Primary risk |
|---|---|---|
| hidden cases | protected store | leakage into public artifacts or evaluated systems |
| sealed ground truth | protected store | answer extraction via commitments, side channels, or store compromise |
| scoring commitments | protected store | pre-registration subversion |
| protected evidence | protected store | tampering, selective disclosure |
| public contracts/schemas | this repository | benchmark tampering, protocol drift |
| execution environments | future harness | environment manipulation, escape |

## 3. Threat boundary

1. **Hidden-file inspection** — an evaluated system reading test files
   from the execution environment. *Boundary decision:* the case/ground-truth
   split with commitments exists precisely so public artifacts never
   carry answers; execution-time isolation is a future-gate item
   (environment declaration fields already exist in the execution
   contract).
2. **Ground-truth access** — any path from an evaluated system or a
   public consumer to expected answers. *Boundary decision:* ground
   truth lives outside the public repository, bound only by sha256
   commitments (preimage resistance makes the commitment non-inverting);
   boundary scanner enforces zero ground-truth content in the public
   tree.
3. **Scoring-code access** — reading verification/scoring rules to game
   them. *Boundary decision:* the public case carries rule id/type only;
   full rule semantics are part of protected ground truth
   (`verification_rule.binding: "protected"`).
4. **Benchmark modification** — altering cases, conditions or
   registered tuples after the fact. *Boundary decision:* registration
   is append-only with `registration_hash`; case documents are
   versioned; the git history of the public repository adds tamper
   evidence on the public side.
5. **Evidence modification** — editing raw outputs or traces
   post hoc. *Boundary decision:* `preservation` declaration
   (`post_hoc_correction: false`) plus artifact hashes and manifests;
   any edit breaks recomputation.
6. **Unauthorized model invocation** — the evaluated system invoking
   models not declared in its identity. *Boundary decision:* system
   identity pins model/provider/API; `model_access.access_path` is
   recorded per execution; enforcement is future work.
7. **Unauthorized network access** — retrieval or exfiltration channels
   during execution. *Boundary decision:* `environment.network`
   (enabled/disabled/controlled) is a declared, auditable field;
   enforcement is future work.
8. **Result exfiltration** — smuggling answers out through outputs,
   logs, or timing. *Boundary decision:* verbatim raw output
   preservation means everything the system emitted is reviewable by
   auditors; nothing is summarized away.
9. **Environment manipulation** — runtime/configuration drift between
   declared and actual execution environment. *Boundary decision:*
   runtime and environment are part of the versioned system identity
   and execution record; drift detection is future work.
10. **Repository exploitation** — using the public repository itself as
    an attack or leakage channel (e.g., via schemas, examples, issues).
    *Boundary decision:* schemas are strict (`additionalProperties:
    false` everywhere), examples carry dummy values only, the boundary
    scanner runs in CI, and no executable content processes
    untrusted input at R0.

## 4. Residual risks accepted at R0

- The repository contains no secrets, no tokens, no keys; its
  compromise would affect integrity of public contracts, mitigated by
  git history and version pinning.
- Commitments protect ground truth *content*, not the *existence or
  count* of cases; metadata-level leakage (how many cases, when sealed)
  is public by design in the public layer and must be managed by the
  future protected layer.
- The scanner enforces *this* repository's tree; it cannot see what
  other repositories or stores do.

## 5. Deferred implementations (future gates)

Execution-time sandboxing, network egress control, sealed-case
distribution mechanics, protected-store hardening beyond the tool layer
(encryption at rest — decision O3), multi-registrar federation (O4),
evidence ingestion implementation (O7), adversarial-input review for
public contributions (see CONTRIBUTING).

## 6. Implemented at R1-I (for the record)

For threats 1, 4 and 5 of §3 above (benchmark modification,
ground-truth access via public artifacts, evidence modification): the
ledger chain + anchoring, the case/ground-truth commitment seam enforced
at registration time, and the CAS write-once store with op-logged
rejections. Tamper detection for these paths is pinned by the test suite
(edit / remove / reorder / duplicate / partial-write / commitment-swap
batteries). Residual risks (anchor window, single-operator limits) are
documented in the M3-R1 decision record §5 (T1–T3) and remain accepted
at this scale.

## 6. Reporting

Security-relevant defects in the foundation (canonicalization
ambiguity, schema bypass, boundary-scanner evasion) should be treated
as protocol-level issues and reported per
[CONTRIBUTING.md](CONTRIBUTING.md).
