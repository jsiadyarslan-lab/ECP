# ECP Security Foundation — Threat Boundary

Version 0.1.0-draft (R0 foundation).

## 1. Status

At R0 the security posture is **documented, not implemented**. This file
enumerates the threats the future evaluation architecture must address
and states, for each, the boundary decision already taken. Per the R0
order, no adversarial sandbox is built now; implementation belongs to
later, separately gated phases. Nothing here is a claim of current
protection.

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
distribution mechanics, protected-store hardening, access-control and
audit logging for the protected layer, adversarial-input review for
public contributions (see CONTRIBUTING).

## 6. Reporting

Security-relevant defects in the foundation (canonicalization
ambiguity, schema bypass, boundary-scanner evasion) should be treated
as protocol-level issues and reported per
[CONTRIBUTING.md](CONTRIBUTING.md).
