# M3-THREAT-INDEPENDENCE.md — M3 Independence & Threat Model

**Status:** G0 design document (frozen by order M3-G0 v3)
**Mode:** READ-ONLY DISCOVERY + SCIENTIFIC DESIGN + AUTHORIZATION
**Baseline:** `5449951586f9e91b4ba9950cbb66086c304337f0` (ECP 0.4.0)
**Companion documents:** `M3-CHARTER.md`, `M3-ARCHITECTURE-BOUNDARY.md`

---

## 1. Purpose and scope

This document freezes the independence model, the system identity and
eligibility rules, the knowledge/leakage boundary, the contamination model,
the execution boundary, the adversarial model, the anti-Goodhart controls,
and the audit model for all M3 stages. It binds every later M3 artifact:
any execution, audit, or analysis record that violates a rule in this
document is invalid for its intended evidentiary use, regardless of its
mechanical integrity.

Nothing in this document is executed in G0. No system is selected, no case
authored, no audit performed.

## 2. Independence model (six dimensions)

M3 NEVER uses the bare label "independent". Independence is declared per
dimension, per participant, with an explicit class:

```text
personal independence      — different natural persons
procedural independence    — isolated tooling/information channels, enforced
                             by machine boundary, not by promise
organizational independence — different controlling organizations
architectural independence — separation enforced by protocol structure
                             (e.g. commitments, sealed GT, ledger append)
```

### 2.1 The six dimensions

| Dim | Question | Declaration required from |
|---|---|---|
| A. System independence | who built and controls the evaluated system? | system identity record (§5) |
| B. Case-author independence | who created the evaluation cases? | authoring provenance (`M3-ARCHITECTURE-BOUNDARY.md` §4) |
| C. Operator independence | who executed the evaluation? | execution record |
| D. Auditor independence | who classified the evidence? | audit record (§11) |
| E. Analysis independence | who performed the statistical analysis? | analysis configuration record |
| F. Information independence | what case/GT/prior-result information was available to each participant? | per-participant information inventory (§7) |

### 2.2 Honest baseline: T1/M1

In T1, dimensions B, C, D, and E were all filled by the same party (the
researcher), and A was partially collapsed (the researcher built/knew JARVIS
and selected all systems). M1 documented this honestly. M3's design target
is: A genuinely diverse for Stratum A; B/C/D/E separated by *procedural*
and *architectural* controls wherever *personal* separation is impossible
(single-researcher constraint is a recorded fact, not a hidden assumption);
F inventoried per §7. Where personal independence cannot be achieved, the
bounded claim rule applies: the artifact says exactly which independence
classes it does and does not have.

### 2.3 The bounded-claim rule

Every M3 result artifact carries an independence declaration block listing
the six dimensions with achieved classes. A claim in prose that exceeds
that block is a protocol violation. This is the mechanism that prevents
the single word "independent" from doing unaudited work.

## 3. Stratum A — independent systems (eligibility BEFORE outcome execution)

Candidate systems are admitted only against the following criteria, all
evaluated before any outcome execution on preregistered cases:

| # | Criterion (from order §6) | Evidence required at admission |
|---|---|---|
| 1 | identifiable version | pinned version tag/commit + retrievability statement |
| 2 | reproducible environment | environment spec (image/pins) restorable |
| 3 | explicit system boundary | written boundary: what is inside the evaluated system |
| 4 | model/provider identity | model name, version, provider, API version (§5) |
| 5 | prompt/configuration identity | pinned system prompt + configuration hash |
| 6 | tool boundary | enumerated tools, with versions |
| 7 | retrieval boundary | declared retrieval/corpus access, or none |
| 8 | runtime identity | runtime/OS/host class, pinned |
| 9 | reproducible I/O | deterministic or explicitly characterized nondeterminism (temperature/seed policy recorded) |
| 10 | evidence preservation | adapter can emit the §6 minimum bundle (`M3-ARCHITECTURE-BOUNDARY.md`) |
| 11 | execution controls | operator can enforce §6 policies (network, FS, timeouts) |
| 12 | GT isolation | demonstrated inability to reach sealed GT / hidden cases (§7, §9) |

**Admission rule.** Selection of candidate systems is recorded with
criteria evidence and a declaration that no outcome data was consulted
(no outcome data exists at admission time — admission precedes execution
by construction). The executor MUST NOT select systems because they appear
likely to produce favorable results; any admission-time material that
references expected performance is disqualifying.

**Eligibility ≠ registration.** Admission to the M3 design does not
register any case or system for execution; execution requires the separate
owner order (charter §11).

## 4. Stratum B — JARVIS real-system validation

JARVIS-lineage systems (current JARVIS; Security/Cybersecurity capability;
Engineering capability; Digital Operations capability; other eligible
JARVIS-lineage targets) demonstrate *operational applicability on complex
real systems* — ECP's machinery exercised on a non-toy system.

Rules (non-negotiable):

```text
JARVIS results ≠ independent replication
```

1. Every Stratum B artifact, manifest, and analysis row carries the label
   `STRATUM-B / NON-INDEPENDENT-LINEAGE`.
2. Stratum B results never enter Stratum A aggregates, never count toward
   external-validity claims, and are never averaged with Stratum A.
3. The ECP-side operator's prior JARVIS knowledge (from M1) is declared as
   an operator-independence limitation for Stratum B executions (dim C).
4. Stratum B uses the same registration/execution/evidence/audit pipeline
   as Stratum A — no separate easier path — otherwise it would not even
   demonstrate operational applicability.
5. Stratum B system identity follows §5 like any other target.

## 5. Model / agent / system identity

Every evaluated target MUST carry a versioned identity record containing
at minimum:

```text
system_id            system_version      model              model_version
provider             api_version         system_prompt      agent_framework
tools                retrieval           external_services  adapter
runtime              protocol_version    case_set_version   environment_version
```

Field semantics:

- `system_prompt`: hash + retrieval path of the pinned prompt text (not
  the text inline, unless it is public);
- `tools` / `retrieval` / `external_services`: enumerated inventories with
  versions and boundaries (a service not listed is not permitted — see
  §6 policies);
- `adapter`: the ECP-side adapter identity + version (the adapter is part
  of the measurement apparatus and is itself pinned);
- `case_set_version` / `environment_version`: the frozen set and
  environment this identity is admitted against.

**Evidentiary consequence.** A result whose identity record is
insufficient (missing/ambiguous fields) MUST NOT receive the same
evidentiary status as a fully identified result: it is classified
`INVALID — IDENTITY-DEFICIENT` for primary-endpoint purposes (charter
§8.1), retained and disclosed, never dropped. Partial identity is never
silently patched post-hoc — missing fields stay missing (they are facts
about the execution, mirroring the CA0-A OQ-PROV-PARTIAL principle:
disclosure, not reconstruction).

## 6. Execution boundary

### 6.1 The five evaluation layers

Every execution explicitly declares exactly one layer:

```text
L1 model-only            — raw model API, fixed prompt, no tools
L2 model + prompt        — pinned prompt configuration beyond default
L3 agent                 — model inside an agent loop/framework
L4 agent + tools         — with enumerated tool access
L5 complete deployed system — full operating system as deployed
```

Cross-layer comparisons are forbidden: L1 results never aggregate with L4;
a system is admitted per layer, and the layer is part of the system
configuration identity (§5). Stratum B JARVIS targets are typically L5.

### 6.2 Execution policies (declared per stage, enforced per execution)

| Policy | Content |
|---|---|
| permitted operations | whitelist per layer (e.g. L1: single completion call) |
| prohibited operations | blacklist with detection (§9) — e.g. GT access, eval-code access, unauthorized model invocation |
| network policy | off by default; any access logged + declared in `external_services` |
| filesystem policy | scratch-only by default; reads outside scratch prohibited |
| tool policy | enumerated tools only; tool versions pinned |
| model policy | declared model/version only; any fallback/model switch = INVALID + incident record |
| timeout policy | per-case timeout, fixed per stage |
| retry policy | bounded retries, each logged as a separate attempt; retry storms = INVALID |
| failure policy | crash/timeout → INVALID execution with cause class; never silently dropped |

## 7. Knowledge / leakage boundary

### 7.1 Channel inventory

For every M3 stage, each channel is classified:

```text
public repository | private repository | local filesystem | runtime database
memory            | fixtures           | environment variables | network access
external APIs     | model pretraining exposure | retrieval systems | caches
logs              | previous evaluation artifacts
```

### 7.2 Classification states

```text
Known-to-target          — information the evaluated system can legitimately see
Unknown-to-target        — information assumed absent (with basis stated)
Protected                — sealed by protocol (GT, hidden cases): commitment-published, content-sealed
Public                   — intentionally open (spec, schemas, dev cases)
Potentially contaminated — exposure plausible, not excluded
Verified uncontaminated — positive verification recorded (method cited)
```

The default state for anything not positively verified is **potentially
contaminated** — absence of evidence is never treated as cleanliness
(same principle as CA0-A ECP-ADJ-000002).

### 7.3 Per-channel controls

| Channel | Control |
|---|---|
| public repo | dev/public cases only; sealed GT excluded by boundary-scan |
| private repo / vault | access-logged; never mounted during execution |
| local FS / runtime DB / caches / logs | scratch-scope enforcement; post-run residue scan |
| memory (agent) | scratch memory only; no persistence across executions unless declared |
| fixtures | hash-pinned; no GT content |
| env vars | allowlist; secrets absent from bundles |
| network / external APIs | default-off; enabled only with logged justification |
| pretraining exposure | declared as permanent open limitation (see §8.2) — cannot be excluded, only bounded |
| retrieval systems | corpus inventory declared; retrieval of sealed content = incident |
| previous artifacts | dev-stage artifacts only available in dev environment (§10) |

## 8. Contamination model

### 8.1 Established facts (from closed records — not reopened)

- **Author–model overlap (FACT).** The 20-case qualification population was
  authored with glm-4-plus (Z.ai) — the same model family as the ECP-side
  authoring agent; flags `model-family-overlap`, `sampling-non-reproducible`
  (ECP-ADJ-000003, UPHOLD-OPEN). Whether overlap exists is NOT reopenable.
- **Training-data contamination (permanently open).** No corpus access
  exists; unresolvable, kept distinct from source contamination
  (ECP-ADJ-000002's four-concept separation: environmental leakage ≠
  source contamination ≠ author-model overlap ≠ training-data
  contamination).
- **Sampling non-reproducibility (accepted risk).** Temperature/seed absent
  at candidate generation; accepted as permanent honest disclosure
  (ECP-ADJ-000004), never reconstructed.

### 8.2 Pretraining exposure as a bounded limitation

For any evaluated model, "the case content was absent from pretraining
data" is **unverifiable**. M3 therefore never claims it. Cases are
defended by structure, not by absence claims: sealed GT (content never
public), commitment-only publication, dev/eval separation, rotating sets
(§10). Residual leakage risk via pretraining is declared per stage.

### 8.3 What G0 does not decide

The disposition of the author-model overlap for future case populations is
**O-03 (B3)** — an owner decision at system-selection time. G0 defines the
framework only (§8.4).

### 8.4 Disposition framework (applies at registration/system-selection)

When the owner rules on O-03, the disposition must be one of:

```text
EXCLUDE                       — affected candidates barred from registration
DISCLOSE + RETAIN             — retained with permanent explicit disclosure
REQUIRE INDEPENDENT EVALUATION — a defined independent-evaluation mechanism
OTHER EXPLICIT DISPOSITION    — any rule stated with the four parameters
```

and must specify: eligibility effect; blocking or non-blocking; required
evidence; scope (all candidates vs affected only). Post-hoc dispositions
derived from expected results are forbidden (order §4). The
representation-bias disclosure layer (capability absence vs capability
inaccessible through tested representation/interface) remains mandatory in
all affected records — disclosure, never erasure (preserved from
M3-CA0-A §7).

## 9. Adversarial / security model

Assumed threat actors: an evaluated target (model or deployed system, L1–L5)
that intentionally or accidentally attempts any of the following; a
malicious operator-side component (adapter, runner); a network attacker
during execution.

| Threat | Control | Residual risk |
|---|---|---|
| access hidden cases | sealed GT + hidden cases never present in execution environment; commitment-only | pretraining leakage (§8.2) — bounded, declared |
| access Ground Truth | sealed GT in protected store; not mounted; boundary-scan | same |
| inspect scoring | classification derives from sealed GT post-execution; scorer not present at runtime | insider with store access — mitigated by dual-auditor + logs |
| modify evaluation code | eval code pinned by hash in stage preregistration; runner verifies before/after | supply-chain attack on pinned deps — pinned digests |
| alter evidence | append-only evidence + manifest hash chain; tamper detection (482-test suite precedent) | store key compromise — logged, auditable |
| access prior results | dev/eval environment separation (§10); prior results not mounted in eval env | operator error — procedural control |
| invoke unauthorized models | model policy + call-logging; unexpected model id = incident + INVALID | wrapper spoofing — adapter pinned + logged |
| access the network | default-off network policy; egress logging | misconfig — post-run residue scan |
| access leaked cases | rotating sets; leak = audit incident with case retirement rule | leaks via pretraining — bounded |
| manipulate execution state | scratch-only FS; state reset per execution; repetition isolation | host compromise — out of scope, declared |
| exploit the repository | repo is public provenance layer only (order §20); no secrets in tree | none beyond public content |
| exploit the evaluation runner | runner is public, reviewed, versioned; stage pins runner digest | runner bug — dual-auditor + verification pass |

Residual risks are permanent stage-report content; none are silently
accepted — each is either bounded with a stated mechanism or declared
unbounded.

## 10. Anti-Goodhart controls

The objective of M3 is protocol validity, not scores. Controls (structural,
not aspirational):

1. **hidden cases** — eval-set cases with sealed GT, never public;
2. **rotating cases** — staged replacement prevents longitudinal
   overfitting by target developers;
3. **sealed Ground Truth** — commitments public, values protected;
4. **limited public scoring** — public artifacts carry validity/
   classification, not leaderboard aggregates;
5. **dev/eval separation** — public development cases for builders;
   preregistered eval cases never available pre-execution;
6. **immutable registration** — ledger append-only (hash-chained);
   registration precedes execution;
7. **audit logs** — every operator/auditor action logged;
8. **provenance** — full chain (architecture doc §7);
9. **independent case authoring** — authoring protocol (architecture doc
   §4) with information inventory;
10. **independent auditing** — §11.

A target system optimizing against the public face of ECP (dev cases,
spec) optimizes something structurally different from the evaluation —
that is the design property, and it is stated as such rather than
claimed as perfection.

## 11. Audit model

```text
Auditor A  ──┐
             ├── independent classifications ── agreement measurement
Auditor B  ──┘              │
                            ▼
                adjudication when required (owner seam)
                            │
                            ▼
                       audit freeze
```

1. **Two auditors, independent classification.** Each auditor produces a
   classification of each execution's evidence (validity class, outcome
   class, evidence-completeness) with an independence declaration per §2
   (personal/procedural/organizational).
2. **Agreement measurement.** Per-dimension agreement, Cohen's κ with CI
   (charter §8.3). Agreement is reported even when high — it is a validity
   measure of the *protocol's classification machinery*, not a nuisance.
3. **Adjudication when required.** Disagreement or ambiguity goes to an
   adjudication record (the `review-adjudication` seam pattern from
   M3-CA0-A: written rules applied to preserved evidence; no invented
   decisions).
4. **Audit freeze.** Post-adjudication, audit records are frozen and
   hash-chained; re-openings create new versions, never overwrite.
5. **Single-auditor fallback (honest labeling).** If only one auditor is
   available: the fact is recorded; **procedural independence is
   distinguished from personal independence** (spec §10.2); the result is
   explicitly not described as fully independently adjudicated. This
   mirrors the existing schema-level contract (`single-auditor-fallback`
   with `personal_independence_maintained: false` + justification).
6. **Audit decisions are units of analysis** (charter §5) — never pooled
   away.

## 12. Attribution integrity

Attribution = the property that any reported outcome can be traced to its
causes: which case version, which system configuration (identity record),
which execution layer, which policy set, which evidence bundle, which
auditors. Mechanisms: versioned identifiers everywhere (spec §3.2);
linkage checks (`src/ecp/linkage.py`); manifest hash chains; the
independence declaration block (§2.3) on every result artifact.

Attribution attacks and their controls: outcome relabeling (audit freeze),
execution swapping (identity + evidence hashes), case substitution
(registration immutability), layer confusion (per-layer admission §6.1),
post-hoc identity patching (§5 evidentiary rule).

## 13. Dependence risk register

| Dependence | Risk | Mitigation |
|---|---|---|
| case-dependence | one case family dominating the set | case population principle (charter §7); family-level reporting |
| system-dependence | one provider dominating "cross-system" claims | diversity taxonomy (charter §6); axes reported |
| operator-dependence | single operator biases executions | policy tables + logging; declared as dim C limitation where personal separation impossible |
| auditor-dependence | correlated auditor errors | procedural separation of auditor tooling; κ monitoring; adjudication seam |
| analysis-dependence | analyst choices shape conclusions | analysis preregistration (charter §8); frozen estimands |
| information-dependence | hidden info flows between roles | §7 inventories; default contaminated |

## 14. Residual risk summary

Unbounded (declared, permanent): pretraining contamination (§8.2);
host-level compromise (§9). Bounded with mechanism: all others per §9
table. This summary must appear verbatim-updated in every M3 stage report.
