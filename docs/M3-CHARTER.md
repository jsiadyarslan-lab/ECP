# M3-CHARTER.md — M3 Scientific Charter

**Status:** G0 design document (frozen by order M3-G0 v3)
**Mode:** READ-ONLY DISCOVERY + SCIENTIFIC DESIGN + AUTHORIZATION
**Order:** M3-G0 — EXTERNAL CROSS-SYSTEM EVALUATION: SCIENTIFIC DESIGN & AUTHORIZATION GATE v3
**Baseline:** `5449951586f9e91b4ba9950cbb66086c304337f0` (ECP 0.4.0)
**Companion documents:** `M3-THREAT-INDEPENDENCE.md`, `M3-ARCHITECTURE-BOUNDARY.md`
**Change control:** this charter is frozen at G0; any refinement of the frozen
question requires a formally justified owner amendment with its own record.

---

## 1. Scientific objective

M3 is a new scientific validation state for ECP (Evidentiary Evaluation
Protocol). Its purpose is **NOT** to increase the number of JARVIS
experiments. Its primary purpose is to determine whether ECP can operate as:

> a reproducible, auditable, externally applicable evaluation protocol
> across independently configured AI systems.

M3 is a *study about the protocol*, not a leaderboard about the systems. The
evaluated systems are instruments for probing the protocol, exactly as the
cases are. This inversion — protocol as subject, systems as instruments — is
the defining property of M3 and the reason its endpoints (§8) are
protocol-level, not performance-level.

M3 must directly address the weaknesses exposed by T1/M1:

| Weakness exposed by T1/M1 | M3 design response |
|---|---|
| Limited external validity (one researcher's environment, one lineage of systems) | Stratum A independent systems (§5; `M3-THREAT-INDEPENDENCE.md` §3) + external-validity taxonomy (§6) |
| Limited personal/organizational independence (author, operator, auditor, analyst all one party) | Six-dimension independence model with per-role declarations (`M3-THREAT-INDEPENDENCE.md` §2) |
| System/case dependence and system identity ambiguity | Versioned identity records with evidentiary consequences (`M3-THREAT-INDEPENDENCE.md` §5) |
| Contamination and leakage uncontrolled | Knowledge/leakage boundary with channel inventory and classification states (`M3-THREAT-INDEPENDENCE.md` §7–§8) |
| Evidence integrity unverifiable by third parties | Evidence bundle + provenance chain + reproducibility classes (`M3-ARCHITECTURE-BOUNDARY.md` §6–§8) |
| Audit independence absent (single auditor) | Dual-auditor model with agreement measurement (`M3-THREAT-INDEPENDENCE.md` §11) |
| Attribution of outcomes weak | Full provenance chain, no narrative-only results (`M3-ARCHITECTURE-BOUNDARY.md` §7) |
| Trust in externally generated evidence undefined | Trust model with explicit residual assumptions (`M3-ARCHITECTURE-BOUNDARY.md` §10) |

The historical T1 and M1 records remain closed. M3 does not re-adjudicate
them, does not extend them, and does not use M3 statistics to rewrite them
(§8.13).

## 2. Relationship to prior stages

### 2.1 T1 — pilot study (CLOSED)

T1 executed a pilot population of 43 registered cases across six pinned
systems (A1: z3 5.1.0.0; A2: sympy 1.14.0; B1: JARVIS `618fdc5`; B2
`21b8279`; B3 `cd3a8a7`; B4 `80d3d61`) under a frozen evaluation semantics.
What T1 established: that the evidentiary approach is *feasible* at pilot
scale — registration, execution, raw evidence preservation, and audit could
be carried through end-to-end. What T1 could not establish: external
validity beyond the authoring researcher, independence in any dimension,
and protocol applicability to systems not built or selected by that
researcher. T1 remains closed and immutable.

### 2.2 M1 — independent audit (CLOSED)

M1 audited T1: evidence freeze (12/12 checks), an independent oracle
re-derivation of task-level semantics, anomaly accounting, and
system-pinned verification. M1's honest finding — that the pilot's
scientific claims were bounded by its single-party structure — is the direct
ancestor of this charter's independence requirements. M1 remains closed and
immutable.

### 2.3 M2 — feasibility & decision gate (CLOSED)

M2 evaluated a further experimental stage within the then-current window and
decided **NOT JUSTIFIED / HOLD** — external validity and statistical value
were LOW under the freeze then in force. That decision redirected effort to
building the protocol itself, which became M3-R0. M2 remains closed and
immutable.

### 2.4 M3 foundation chain — R0 → R1 → R1-I → CA0 → CA0-A (LIVE)

The ECP repository now provides, additively and without history rewrite:

| Stage | Commit | What it froze |
|---|---|---|
| M3-R0 | `7e51c75` | protocol identity, object hierarchy, 10 schemas, canonical JSON, hashing/commitments, verification boundary, public/protected boundary, GT sealing, tests |
| M3-R1 | `75422ed` | protected-evidence & registration architecture decision (Option C: local CAS store + hash-chained ledger) |
| M3-R1-I | `b57c812` | protected store (CAS) + registration ledger (append-only, hash-chained) + anchoring; ledger at genesis, zero registrations |
| M3-CA0 | `9e8d446` | case review pipeline: candidate intake, deterministic three-state eligibility review, review-adjudication human seam, engine profiles |
| M3-CA0-A | `5449951` | owner adjudication & case qualification: versioned amendments with two-phase representation-bias disclosure; qualification inventory 0 ELIGIBLE / 2 REJECTED / 18 REQUIRES_REVIEW |

Current state: public ledger at genesis (zero registered cases, zero
executions, zero results, zero scientific claims). The 20-case candidate set
is a qualification-stage test population — **it is not the ECP design** (§7).

### 2.5 Open decision record ECP-OWNDEC-000001 (M3-CA0-B)

Four genuine blockers remain `OWNER DECISION REQUIRED`:
B1 external novelty evidence; B2 registration authoring; B3 contamination
disposition; B4 C-004 GT validation. M3-G0 does **not** resolve them — it
designs the framework within which each will be resolved, and carries them
as open entries in the decision register (§12). Nothing in this charter
makes any of the 18 surviving candidates eligible; eligibility remains
impossible until the owner disposes of the blockers.

### 2.6 JARVIS

JARVIS (pinned `337cde4` for the current revision) is a complex real system
from the T1 lineage. In M3 it belongs to Stratum B (secondary,
operational-applicability validation), never to Stratum A. JARVIS results
are never independent replication and are always separately labeled
(§5.3; `M3-THREAT-INDEPENDENCE.md` §4).

## 3. Primary research question (FROZEN)

> **Can ECP be operationally applied across independently configured AI
> systems using common preregistered evaluation cases, controlled execution,
> preserved evidence, independent auditing, and reproducible outcome
> classification?**

Each clause is load-bearing and has an operational counterpart:

| Clause | Operational counterpart |
|---|---|
| "operationally applied" | a complete registration → execution → evidence → audit → classification pass under the protocol, with no ad-hoc manual shortcuts (§8 endpoints) |
| "across independently configured AI systems" | Stratum A systems satisfying §3 of `M3-THREAT-INDEPENDENCE.md`; independence declared per dimension, never as a bare label |
| "common preregistered evaluation cases" | one registered case set (ledger-frozen versions) executed by all systems in a stage |
| "controlled execution" | declared execution layer + policy set (`M3-THREAT-INDEPENDENCE.md` §6) |
| "preserved evidence" | the minimum evidence bundle (`M3-ARCHITECTURE-BOUNDARY.md` §6) with manifest and hashes |
| "independent auditing" | dual-auditor model with measured agreement (`M3-THREAT-INDEPENDENCE.md` §11) |
| "reproducible outcome classification" | classification derived mechanically from preserved artifacts and re-derivable by a third party (`M3-ARCHITECTURE-BOUNDARY.md` §8) |

**Forbidden replacements.** The question MUST NOT be replaced by: which
model is best; which system gets the highest score; can JARVIS solve more
cases; can ECP make a particular model look better. Those are secondary
questions at most, and none of them may become a primary endpoint
(§8.2). Any analysis artifact that promotes them to primary status is a
protocol violation.

## 4. Secondary questions (defined, not executed)

### SQ1 — Generalizability
Can the same ECP protocol be applied across materially different AI
systems? *Operationalization:* the fraction of Stratum A systems admitted
under §3 eligibility that complete the full protocol pass without
protocol waivers; every waiver is itself a recorded finding, not noise.

### SQ2 — Evidence integrity
Can execution evidence remain attributable, complete, and verifiable
across systems? *Operationalization:* evidence-bundle completeness rate
and third-party verification success rate on sampled bundles
(`M3-ARCHITECTURE-BOUNDARY.md` §8).

### SQ3 — Independence
Can the study achieve measurable independence across system selection,
case authoring, execution, auditing, analysis? *Operationalization:*
per-dimension independence declarations with class labels; measured
auditor agreement; any dimension collapsed to one party is recorded as a
bounded claim, never silently.

### SQ4 — Reproducibility
Can an external party reproduce or independently verify an ECP result
from the preserved artifact bundle? *Operationalization:* independent
verification runs using only public tools + preserved bundle; success =
bit-identical hash re-derivation and identical classification.

### SQ5 — JARVIS applicability
Can ECP be applied to current JARVIS systems without treating
JARVIS-specific results as independent replication? *Operationalization:*
Stratum B executes under the same registration/execution/evidence
pipeline; results are labeled `STRATUM-B` / `NON-INDEPENDENT-LINEAGE` in
every artifact, and no Stratum B result enters a Stratum A aggregate.

### SQ6 — Scalability
Can the ECP architecture support substantially more than the current
pilot population without making the number of cases a structural
constraint? *Operationalization:* architecture audit — no constant in
code, schema, or spec caps case/system/execution counts; load-shaped
growth is data, not structure (`M3-ARCHITECTURE-BOUNDARY.md` §12).

None of SQ1–SQ6 is executed in G0. They are frozen as measurement targets
so later phases cannot redefine them opportunistically.

## 5. Units of analysis

The following units are frozen. They MUST NOT be collapsed into a single
score.

| Unit | Definition | Primary use |
|---|---|---|
| **Case** | one versioned evaluation case (`ECP-CASE-…`), ground truth sealed | the common input across systems |
| **Execution** | one controlled run of one case against one declared system configuration (`ECP-EXEC-…`), with repetition index | the atomic evidentiary unit |
| **System Configuration** | one versioned identity record (`ECP-SYSTEM-…` + §5 identity fields) | the evaluated instrument |
| **System × Case** | the crossed pair (with repetition index when repeated) | **the primary experimental unit** for the primary endpoint |
| **System Family** | a declared grouping of configurations sharing provider/lineage/architecture | aggregation level for external validity claims |
| **Audit Decision** | one auditor's classification of one execution, plus any adjudication record | the audit-agreement unit |
| **Study** | one preregistered M3 stage: frozen case set × admitted system set × protocol version | the highest-level unit; preregistration boundary |

The architecture MUST permit: one case → many systems; one system → many
cases; one case → repeated controlled executions (repetition index
explicit, between-repetition agreement itself a reproducibility measure);
many cases → one evaluation family. The current pilot populations (T1's
43; the 20-case qualification set) MUST NOT become architectural limits
(§7; `M3-ARCHITECTURE-BOUNDARY.md` §12).

## 6. External validity standard

Diversity is claimed only along declared axes. M3 distinguishes:

```text
model diversity        — different underlying models
provider diversity     — different providers/organizations serving the model
architecture diversity — different model/agent architectures (e.g. transformer LM vs tool-using agent vs symbolic solver)
framework diversity    — different agent frameworks/harnesses
organizational diversity — different controlling organizations for the evaluated system
execution-environment diversity — different runtimes/hosts/operators
```

**Rule (non-collapsing):** different model versions of one model family,
or one model served through two thin wrappers, do NOT constitute
independent systems. Independence is a property of the six-dimension
model (`M3-THREAT-INDEPENDENCE.md` §2), not of a name. Every
external-validity claim states the axes along which diversity was
achieved and those along which it was not.

Minimum diversity thresholds for a meaningful "cross-system" claim are set
at registration time under the registration order (not in G0 — G0 does
not fix sample sizes or thresholds; §8.11).

## 7. Case population principle

The current T1 population and the 20-case qualification set do NOT define
the architecture. The case ecosystem MUST support:

- multiple reasoning families (logical, quantitative, constraint,
  procedural, multi-step hybrid, …);
- multiple difficulty levels and case sizes;
- multiple system types (LLM, agent+tools, symbolic solver, deployed
  system, …);
- rotating cases (staged replacement across study stages);
- hidden cases (sealed GT, commitment-published only);
- public development cases (clearly marked, never scoring);
- preregistered evaluation sets (ledger-frozen before execution);
- future case expansion (new families added without protocol change).

The mechanism for "cases can be added without changing the protocol" is
the existing registration path: candidate → review (three-state) →
qualification/adjudication → registration (ledger append) → frozen
version. Case-set growth is ledger data, not schema or code change
(`M3-ARCHITECTURE-BOUNDARY.md` §3–§4).

## 8. Statistical design framework

The full statistical design (sample sizes, concrete thresholds) is NOT
selected in G0 — that belongs to the registration/execution planning
order. G0 freezes the *framework* so later phases cannot improvise it.

### 8.1 Primary endpoint

**Evidence-Complete Classified Execution rate (ECCE):** among all
attempted `System × Case × repetition` units in a preregistered stage, the
fraction that produce (a) a complete minimum evidence bundle, (b) a valid
identity record, and (c) an unambiguous, mechanically derived outcome
classification (VALID/SUCCESS-FAIL, or VALID/INCONCLUSIVE, or INVALID —
all three count as *classified*; the endpoint is about the protocol
delivering classifiable evidence, not about systems succeeding).

### 8.2 Secondary endpoints (exploratory-labeled, never promoted post-hoc)

- audit agreement (per-dimension; Cohen's κ between auditors A and B);
- independent-verification success rate on sampled bundles (SQ4);
- evidence-bundle completeness and manifest-integrity rates (SQ2);
- invalid-execution and inconclusive rates (diagnostic, not failures of
  the endpoint);
- between-repetition classification agreement (reproducibility of the
  *system-under-protocol*, reported per stratum);
- protocol-waiver count per system admission (SQ1 generalizability
  cost).

Model performance (success rates by system) is reported only as
descriptive stratum- and family-level summaries. It is never an
endpoint of M3.

### 8.3 Estimands

- ECCE: population = attempted units in the stage; estimand = stage-level
  proportion with exact Clopper–Pearson 95% two-sided CI;
- κ: per audit-dimension, with CI; population = audited executions;
- verification success: sampled-bundle proportion with CI; sampling plan
  preregistered with the stage.

### 8.4 Confidence level
95%, two-sided, prespecified. No level shopping.

### 8.5 Missing-data policy
A missing bundle element, missing identity field, or missing audit record
counts as a protocol failure for that unit (counted in the ECCE
denominator as not-complete). No convenience exclusion.

### 8.6 Invalid-execution treatment
INVALID executions remain in the denominator; they are classified
outcomes of the protocol (§8.1), not data to drop.

### 8.7 Inconclusive treatment
VALID/INCONCLUSIVE is a legitimate, separately reported outcome class —
distinguished from INVALID (execution defect) and from missing data.
The three-way distinction is schema-enforced
(`execution_status.validity` × `execution_status.outcome`, spec §9).

### 8.8 Dependence structure
Crossed design: cases × system configurations. Executions nested within
System × Case (repetitions); audit decisions nested within executions;
systems nested within families. Any variance/CI method used at
case- or family-level must account for clustering (cluster-robust or
mixed-model framing); unit-level proportions use exact intervals. The
dependence map is part of the preregistered stage plan.

### 8.9 Repeated observations
Repetitions of the same case by the same system configuration are
explicitly indexed Execution units; between-repetition agreement is
reported (8.2). Repetitions never silently pool.

### 8.10 Multiplicity
Primary endpoint: single, stage-level. Secondaries: labeled exploratory;
no post-hoc promotion; no alpha reallocation schemes.

### 8.11 Stopping rule
Stages run to their preregistered plan (fixed case set × admitted system
set × planned repetitions). No interim outcome peeking. Early stop only
for predefined integrity reasons (evidence-integrity failure, safety,
historical-integrity failure) and is itself recorded as an audit finding.
Sample sizes and thresholds are chosen under the registration order with
recorded rationale — never selected merely to obtain a desired outcome.

### 8.12 Anti-rewrite rule
M3 statistics MUST NOT be used to reinterpret or rewrite T1 or M1.

### 8.13 T1/M1 boundary
T1/M1 numbers may appear only as historical context, always labeled as
closed records from a different protocol state.

## 9. Human calibration arm (decision: NOT adopted in the core design)

**Decision:** a human/reference calibration arm is NOT part of the core
M3 design, and MUST NOT become an artificial blocker.

**Rationale:** the primary question is protocol applicability; human
performance is neither the instrument nor the comparison class for that
question. Forcing a human arm would add an execution layer with its own
identity/contamination problems without improving the validity of the
protocol-level endpoint.

**Reopening condition:** if a later phase needs human-performance anchoring
for a specific scientific claim, the arm is added as a *separately
preregistered auxiliary arm*: its protocol is frozen before any human
execution, kept separate from model outcomes, and never used for
post-hoc score tuning. Absence of the arm in the core design is recorded
as a bounded scope decision, not as evidence about human performance.

## 10. Success criteria (multidimensional — no single percentage)

| Dimension | Success criterion (stage-level) |
|---|---|
| Protocol applicability | ≥1 preregistered stage completes the full registration → execution → evidence → audit → classification pass across ≥2 admitted Stratum A systems with zero protocol waivers required to finish |
| Evidence integrity | 100% of counted units have complete bundles + verified manifests; zero post-hoc mutations detected (tamper checks green) |
| Execution validity | INVALID rate reported and attributable — every INVALID execution has a recorded cause class |
| Attribution integrity | every classification traceable case→registration→execution→evidence→audit→analysis with zero broken links (linkage checks green) |
| Reproducibility | independent verification reproduces classification for 100% of sampled bundles; re-derivation bit-identical |
| Auditability | dual-auditor executed; κ reported with CI; disagreements adjudicated and frozen |
| Independence | per-dimension declarations recorded; no claim exceeds its declared independence class; JARVIS results never labeled independent |
| External validity | achieved diversity axes explicitly reported vs. the taxonomy (§6); unachieved axes explicitly listed |
| Scalability | architecture audit: no structural caps (case/system/provider/execution counts are data); growth plan executable without protocol change |

A stage may pass on some dimensions and fail others; all nine are
reported. Reducing M3 to one success percentage is a protocol violation.

## 11. Scope boundary of G0

G0 produces exactly three design documents (this charter,
`M3-THREAT-INDEPENDENCE.md`, `M3-ARCHITECTURE-BOUNDARY.md`). G0 does NOT:
author cases; register cases; execute models; collect experimental data;
select systems; fix sample sizes or thresholds beyond the framework;
implement code or schemas; resolve B1–B4. Every subsequent phase (case
authoring protocol, registration, execution, evaluation, statistical
analysis, any commercial layer) requires a separate owner order
(§13 of the order; M3-G0 §28).

## 12. Decision register

Resolved by G0 under the approved methodology (rationale recorded;
alternatives considered; executor-resolvable per order §24):

| # | Decision | Selected option | Rationale (summary) | Alternatives rejected | Consequence |
|---|---|---|---|---|---|
| D-01 | Primary endpoint is protocol-level, not performance-level | ECCE (§8.1) | primary question is protocol applicability; performance endpoints would Goodhart the study | system success-rate primary; hybrid score | system scores stay descriptive |
| D-02 | Unit of primary analysis | System × Case (×repetition) | crossed design preserves attribution; finer units would explode multiplicity; coarser units would collapse strata | case-only; system-only; study-only | dependence map fixed at §8.8 |
| D-03 | Validity vs outcome separation in all reporting | three-way classes (§8.7) | spec §9 already schema-enforces; collapsing loses diagnostic value | binary pass/fail | INVALID/INCONCLUSIVE rates reportable |
| D-04 | Human calibration arm | not in core design (§9) | not required for protocol-applicability endpoint | mandatory human arm | reopenable under preregistered auxiliary arm |
| D-05 | Statistical framework | exact intervals for proportions; cluster-aware for aggregates | small-N honesty; dependence structure requires clustering | asymptotic-only CI | framework frozen; sizes deferred |
| D-06 | Rotating/hidden/dev case classes | part of design (§7) | anti-Goodhart + scalability both require them | single static public set | case lifecycle in architecture doc |
| D-07 | JARVIS placement | Stratum B, separately labeled | JARVIS shares lineage with ECP development — never independent | include as independent; exclude entirely | Stratum B shows operational applicability only |
| D-08 | Success reporting | nine-dimension table (§10) | single-percentage reduction is a protocol violation | composite index score | stage report format fixed |
| D-09 | Confidence level & multiplicity | 95% two-sided; exploratory secondaries | prespecification prevents shopping | adjustable levels | frozen in this charter |

Open (genuine owner decisions — not manufactured; carried from
ECP-OWNDEC-000001):

| # | Open decision | Carried from | Resolution framework |
|---|---|---|---|
| O-01 (B1) | external novelty-evidence mechanism | M3-CA0-B §2 | `M3-ARCHITECTURE-BOUNDARY.md` §9.3 defines the admissible mechanism shapes; owner selects or declines |
| O-02 (B2) | registration-authoring authorization | M3-CA0-B §3 | authoring protocol defined in `M3-ARCHITECTURE-BOUNDARY.md` §4; owner authorizes the stage |
| O-03 (B3) | contamination disposition at system selection | M3-CA0-B §4 | disposition options defined in `M3-THREAT-INDEPENDENCE.md` §8.4; owner rules at selection time |
| O-04 (B4) | C-004 GT validation | M3-CA0-B §5 | GT validation procedure defined in `M3-ARCHITECTURE-BOUNDARY.md` §4.7; owner authorizes |

## 13. Question freeze

The primary question (§3) and secondary questions (§4) are frozen. Any
refinement requires a formally justified owner amendment record stating:
what changed, why the change is scientifically necessary, that no
collected data motivated it, and the new frozen text. Absent such a
record, this charter is the binding definition of M3.
