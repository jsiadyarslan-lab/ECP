# SRE-V1-NULL-MODEL-SPECIFICATION.md — Scientific Reasoning Evaluation v1: Statistical Null Model

**Status:** REGISTERED STATISTICAL DESIGN (frozen by owner order `SRE-v1 STATISTICAL NULL MODEL RECONCILIATION & PRE-REGISTRATION CLOSURE v1`, 2026-09-12)
**Mode:** STATISTICAL DESIGN / PRE-REGISTRATION — no scientific execution authorized or performed by this artifact
**Repository:** `jsiadyarslan-lab/ECP`, branch `main`
**Design baseline commit:** `5fc90484f1fc4b7fa0cf21a92b41274414c24d24` (worktree clean; HEAD == origin/main)
**Design-phase source artifact:** `SCIENTIFIC-REASONING-EVALUATION-v1-PREREGISTRATION.json` (SHA-256 `0cd5bea53c72dff2f7c49e10fd79874cd28ac16982d1b28370719f02f0002d30`, external design package, order SRE-v1 v4)
**Change control:** every frozen field in this specification is preregistration-locked. Changes require a formal amendment (see `SRE-V1-PREREGISTRATION-STATISTICAL-SECTION.md` §5) that preserves this version and records what changed, why, when, who authorized it, whether execution had begun, and whether results had been observed.

---

## 1. Purpose and scope

This specification defines — operationally and unambiguously — the statistical null model for the future SRE-v1 evaluation. It exists to close one specific scientific-integrity gap: before this artifact, the SRE-v1 statistical design lived outside the repository (design package, order SRE-v1 v4) and a non-authoritative, non-preregistered statistical file (`scientific/sre-v1/power/power-analysis.json`, SHA-256 `330aa46e2283c46227972c4f41c23636d08c620bc045787d092d44426465e693`, removed from the working tree and preserved externally as NON-AUTHORITATIVE / NOT PREREGISTERED / NOT USED FOR SCIENTIFIC DESIGN under owner decision D3) had appeared at this path. This specification supersedes that ghost path with a registered, hash-frozen, independently derived null model.

Every parameter value in this document was **independently re-derived from the authoritative pool material and first-principles statistical reasoning** during the closure order (derivation engine: exact rational arithmetic, two independent implementations, exhaustive combinatorial verification; record: `sre_v1_closure_derivation_result.json` in the executor's design record). No value was adopted because it appeared in any file. Where a derived value coincides numerically with a value in the non-authoritative file, the coincidence is disclosed and the independent derivation is recorded (order §5 compliance; see `SRE-V1-RECONCILIATION-MATRIX.md`).

This specification determines the statistical design for the **future SRE-v1 evaluation only**. It is not a post-hoc correction of any historical result. T1, M1, M2, the frozen manuscript, and all historical classifications remain immutable and are not reinterpreted here (historical separation: `SRE-V1-RECONCILIATION-MATRIX.md` §6).

## 2. Scientific null vs statistical null

The two nulls are stated separately and are never conflated.

### 2.1 Scientific null (H0-scientific)

> The evaluated SRE-v1 system (a single frozen DEME configuration, to be sealed at the execution phase prior to any case execution), solving sealed, novel, non-retrievable, multi-step scientific-reasoning cases under the ECP protocol, does **not** achieve the preregistered success criterion beyond what a non-reasoning (content-blind) answering process achieves on the frozen key-balanced case set.

The scientific null mechanism is **incapability of content-dependent reasoning**: the system's answers are statistically indistinguishable from a process that does not read or exploit the case content. It is NOT a statement about "random chance" in any vague sense — it is the precise operational claim that no per-case success probability exceeds the content-blind rate (§3).

### 2.2 Statistical null (H0-statistical)

```text
H0:                 theta_i = 1/3 for every frozen case i = 1..9
                    (theta_i = per-case success probability of the frozen system)
Null mechanism:     content-blind answering under the sealed key lottery of the
                    key-balanced (3/3/3) frozen ternary answer space (§3)
Test statistic:     X = number of successful cases among the N_obs valid executions
Null distribution:  X ~ Binomial(N_obs, p0) with p0 = 1/3 (exactly; §4)
Sampling unit:      ONE case execution (one frozen case x one frozen system
                    configuration x one execution) — §5
Exchangeability:    under H0 the 9 outcome indicators are exchangeable Bernoulli(1/3)
                    (sealed contexts, no cross-case channel, identical null rate) — §6
Independence:       under H0 the per-case outcomes are mutually independent
                    (sealed per-case contexts; §6) — and this is the ONLY independence
                    the test requires
Directionality:     one-sided, upper (H1: theta_bar > 1/3; §7)
Decision rule:      reject H0 iff X >= k*(N_obs), with k*(9) = 6 and k*(8) = 6
                    (mechanically equivalent to: one-sided 95% Clopper-Pearson
                    lower bound on X/N_obs exceeds p0) — §8
```

The aggregate implication `X ~ Bin(9, 1/3)` under H0 follows from the per-case statement: nine exchangeable, mutually independent Bernoulli(1/3) indicators sum to a Binomial(9, 1/3).

## 3. Null mechanism: the strategy-proof balanced-ternary construction

### 3.1 The answer space

Every frozen case's question carries the identical answer contract: **"Answer with: yes, no, or cannot be determined."** The permitted answer space is the three-element set {YES, NO, CANNOT-BE-DETERMINED}. This was verified mechanically on the frozen set (all 9 cases carry the ternary instruction; key classes are 3 YES / 3 NO / 3 CANNOT-DETERMINE).

### 3.2 Sealed keys, public balance

The **key balance 3/3/3 is preregistered public structure**; the **per-case key assignment is sealed ground truth**. A non-reasoning system therefore faces a symmetric lottery over key positions: for every position j, P(key_j = c) = 3/9 = 1/3 for each class c.

### 3.3 The strategy-invariance argument (derivation of p0)

For ANY answering process sigma that does not process case content (pure, mixed, constant, or position-keyed):

```text
E[score | sigma] = sum_j P_sigma(answer_j = key_j)
                 = sum_j P_sigma(answer_j = c) * P(key_j = c) summed over c
                 = sum_j (1/3)        [because P(key_j = c) = 3/9 for every c,
                                      and P_sigma(answer_j = c) sums to 1 over c]
                 = 9/3 = 3  successes out of 9  ->  E[rate] = 1/3
```

No content-blind strategy can achieve an expected success rate above 1/3 on the key-balanced frozen set. The value was verified exhaustively during the closure derivation:

- **(i) constant pure strategies** — always-YES, always-NO, always-CANNOT-DETERMINE each score exactly 3/9 = 1/3;
- **(ii-a) direct permutation averages** — for 5 representative deterministic answer vectors (including all three constant vectors), the exact average score over all 1,680 = 9!/(3!·3!·3!) uniform permutations of the sealed 3/3/3 key multiset is exactly 3/9;
- **(ii-b) analytic exhaustive coverage** — the marginal argument covers all 3^9 = 19,683 deterministic position-keyed answer vectors: expected score exactly 1/3 for every one;
- **(iii) mixed strategies** — every i.i.d. answer distribution (a_YES, a_NO, a_CBD) with a_YES + a_NO + a_CBD = 1 (231-point grid) scores exactly 1/3.

**Frozen value: p0 = 1/3.**

The null is therefore **strategy-invariant by construction** of the frozen set: uniform guessing, any fixed answer, any mixture, and any position-keyed pattern all have the same expected success rate. This is what makes "non-reasoning" operational — there is no way to beat 1/3 without processing case content.

### 3.4 Why p0 = 0.5 is rejected for this design

A binary fair-coin null (p0 = 0.5) presupposes a two-element answer space. The actual answer space of every eligible SRE-v1 case is ternary. On a key-balanced ternary set the content-blind rate is exactly 1/3, not 1/2; adopting 0.5 would misstate the null mechanism and would simultaneously misstate the difficulty of the capability claim (a system must clear 1/3, not 1/2, by blind luck). The value 0.5 appears in the non-authoritative power-analysis file with a justification ("free-form numeric answers") that is factually false for this pool: 21 of 30 qualified candidates are ternary, and the frozen evaluation universe is drawn exclusively from them. Independent derivation, not preference, fixes p0 = 1/3.

## 4. Test statistic and its exact null distribution

The primary test statistic is `X = number of successful cases among the N_obs valid executions` (planned N_obs = 9). Under H0:

```text
X ~ Binomial(N_obs, 1/3)      (exact; no approximation)
```

Per-case success is the binary, mechanically coded criterion preregistered in the design-phase artifact (`analysis_rule.success_criterion_per_case`): the response's declared final answer is one of {YES, NO, CANNOT-BE-DETERMINED} AND matches the preregistered key class of the case, AND the response explicitly cites at least one premise of the case (by premise index or a verbatim fragment of >= 5 consecutive words). Both checks are replayable by an auditor from the raw response payload alone.

## 5. Unit of analysis

The registered scientific unit is the **CASE**, established in the hypothesis specification. This design reconciles the statistical units to it explicitly:

```text
primary observational unit  = one case execution
primary statistical unit    = the case execution (the Bernoulli trial that enters X)
independent replicate        = a case execution under the frozen sealed-context protocol
```

N is NOT inflated by counting execution logs, intermediate steps, evidence records, audit records, or derivation steps as scientific observations. Each frozen case contributes exactly one Bernoulli observation to X (or zero, if the execution is void/missing under the frozen rules in `SRE-V1-STATISTICAL-DESIGN-SPECIFICATION.md` §11).

If repeated executions exist, their classification under this design is fixed in advance:

- the single permitted re-execution of a VOID case (infrastructure failure, no captured response) is a **retry of the same observation**, not a new independent replicate — it replaces the void attempt, it does not add an observation;
- any execution with a captured model response (success or failure) is a **terminal repeated measurement that may NOT be rerun** — a second execution of a completed case would be a non-independent observation and is forbidden by the frozen rerun rule;
- there is no within-case replication: execution randomness is absorbed into theta_i (per-case success probability), which is a latent component of the estimand, not itself estimated.

## 6. Exchangeability and independence assumptions

**Under H0 (the only world in which the test's size is controlled):** the 9 outcome indicators are exchangeable — each is Bernoulli(1/3) with the identical content-blind rate, by the strategy-invariance of §3 — and mutually independent, because each case executes in a sealed context containing only that case's content, with one execution per case and no cross-case information channel. The binomial null distribution follows exactly.

**Under H1 (power considerations only):** outcomes may be positively dependent through the system's shared latent capability (a common factor across cases). This does not affect the validity of the test of H0; it affects only the power computation, which is preregistered under the i.i.d. design alternative theta_i = 0.80 for all i (the design-target capability bar). The dependence structure is disclosed rather than assumed away: the estimand is the finite-universe success probability, and the test remains an exact test of the stated H0.

**What is NOT assumed:** no clustering correction is needed at N=9 for the primary test because the primary test models the trials themselves (not a superpopulation of systems); family clustering (max 2/9 per reasoning family in the frozen set) is a design stratification axis for descriptive reporting, not an interference channel — no case's execution is affected by any other case's existence.

## 7. Directionality

The alternative is **one-sided, upper**: H1: theta_bar > 1/3.

Scientific justification: the capability claim is directional superiority over the non-reasoning null. A system performing BELOW 1/3 would exhibit a systematic answering pathology (an execution-integrity concern to be investigated as an anomaly), not a performance hypothesis; theta < 1/3 has no capability interpretation. Testing both directions would spend alpha on a scientifically meaningless lower tail and would misrepresent the claim. The one-sided form is frozen before any outcome exists; switching sides after observing results is prohibited (§4 of `SRE-V1-PREREGISTRATION-STATISTICAL-SECTION.md`).

## 8. Decision rule (mechanical form)

```text
reject H0  iff  X >= k*(N_obs)

k*(n) = min{ k : P(Bin(n, p0) >= k) < alpha },  alpha = 0.05 one-sided

k*(9) = 6   because P(Bin(9,1/3) >= 6) = 835/19683  = 0.042423 <  0.05
                 P(Bin(9,1/3) >= 5) = 2851/19683 = 0.144850 >= 0.05
k*(8) = 6   at the degraded null p0_miss = 3/8 (one missing case; see
                 SRE-V1-STATISTICAL-DESIGN-SPECIFICATION.md §11)
```

Mechanical equivalence (proven, not assumed): rejecting H0 iff X >= k*(n) is **identical** to the one-sided 95% Clopper-Pearson lower bound on X/N_obs exceeding p0 — the standard identity `Beta.ppf(0.05; x, n-x+1) > p0  <=>  P(Bin(n,p0) >= x) < 0.05` was verified for every x and n in {8, 9} during the closure derivation. The two formulations are the same inference and are never mixed (no two-sided-95%-lower-bound interpretation, which would correspond to one-sided alpha = 0.025).

Tie impossibility: for p0 = 1/3 the survival function is a rational with denominator 3^n, and alpha = 1/20; equality would require 20 | 3^n, which is impossible for all n (verified for n in [1,60]). The strict-vs-non-strict distinction in the definition of k* is therefore immaterial.

## 9. Why no randomization or permutation test

The design uses **no randomization- or permutation-based null**, and the reason is principled, not convenient:

- a permutation test would permute outcome labels across cases, testing **exchangeability of observed outcomes across cases** — that is not the scientific null. The scientific null is a fully specified **generative mechanism** (content-blind answering at rate 1/3 under the sealed key lottery), not an exchangeability claim about data rows;
- the parametric binomial null is **exact** at this sample size (no asymptotics, no approximation), so a nonparametric alternative buys nothing in validity and would obscure the mechanism;
- the only stochastic element under H0 is the system's own answer process, which the strategy-proof construction pins at exactly 1/3 — there is no residual randomization to permute.

No randomization seed, permutation count, or tail definition is therefore required; the exact rational computation replaces all of them. (The Monte Carlo verification of the operating characteristics in `SRE-V1-STATISTICAL-DESIGN-SPECIFICATION.md` §10 is design verification only, with a fixed disclosed seed, and plays no role in the decision rule.)

## 10. Frozen null-construction material

The null model is inseparable from the frozen case set that realizes the key balance. The frozen set (mechanically selected, performance-blind; selection rule in `SRE-V1-STATISTICAL-DESIGN-SPECIFICATION.md` §6.3):

| # | Candidate ID | Key class | Reasoning family | Difficulty | GT class | Content SHA-256 |
|---|---|---|---|---|---|---|
| 1 | ECP-CAND-000101 | YES | transitive-relational | MEDIUM | DERIVABLE | `28562c5ca5bedc911f7a124e7ca31103703c5ae27df401e1c0672cf5a275ecd9` |
| 2 | ECP-CAND-000102 | CANNOT-DETERMINE | transitive-relational | SHALLOW | INDETERMINATE | `17fcf09cd9826ace859e4349fd46479417258022f9a87d180167b5a4d891d2bf` |
| 3 | ECP-CAND-000106 | YES | conditional-chaining | MEDIUM | DERIVABLE | `8cfe7c6489de605965156ecdec479179a1a6bd4ae49094ed1fef3a1dc61484fb` |
| 4 | ECP-CAND-000107 | NO | conditional-chaining | MEDIUM | CONTRADICTED | `6b039d54864235b7cf19c4c98f4aa31a17e6704561ba3b66ff2a351678a63bc1` |
| 5 | ECP-CAND-000116 | NO | relational-discrimination | MEDIUM | CONTRADICTED | `f9db2a4eb8734761b76ff5cc6efe3f52a675dc33588b26aef032e83c6104ecb9` |
| 6 | ECP-CAND-000117 | YES | relational-discrimination | MEDIUM | DERIVABLE | `dd267e6df60e4b492eeff22cd5b5038d042934132c28d025b07a97a802b7017c` |
| 7 | ECP-CAND-000123 | CANNOT-DETERMINE | constraint-quantitative | MEDIUM | INDETERMINATE | `99a53a6d194a55fae3d4240f10da81a17b50e2c349c213243699acc2799664d8` |
| 8 | ECP-CAND-000128 | NO | default-exception | MEDIUM | CONTRADICTED | `043b1fec80836f4d8fd83ef8db4ee0a2779597067b6fb298f07bfa4cb5aa38f9` |
| 9 | ECP-CAND-000129 | CANNOT-DETERMINE | default-exception | DEEP | INDETERMINATE | `35cd41b5cb29e30e42aa5533705092cefed7b65947e90d0a8206b4ee20df9199` |

Key balance: 3 YES / 3 NO / 3 CANNOT-DETERMINE. Pool provenance: ECP-CA0v1 qualified candidate pool (30 candidates, Q3 PASS x30, qualification run ECP-QUALRUN-CA0V1-R1); all 9 content hashes were re-derived from the pool files on disk with the repository's own canonical hashing (`ecp.hashing.hash_document`) during the closure derivation (9/9 exact match). Source material: candidate set document SHA-256 `8144818cc37f0aa8b41d99c4a3cfacb5d5082aa1a97170fd1f61c4f86b0f425d`, provenance sidecar `0f4e2318a1a086aae87fcd792b64920463c70f53887e7d9138f40c3f14579e80`, intake report `fc8a35320c2a54e9cb9bafbd3fe971fc7b29c2748bd04fa3fdb4ccc16d2077a4`.

## 11. System comparison boundary

SRE-v1 evaluates **one** frozen system configuration (DEME, sealed at the execution phase). There is no second system, no paired comparison, no between-system contrast, and no cross-system generalization claim in this design (the estimand's scope is the frozen universe of 9 cases x 1 system). The single-system binomial null model is therefore the correct and complete null model for this study; a paired binary analysis, independent-group comparison, clustered analysis, or hierarchical model would presuppose multiple systems and would be inadmissible here.

For clarity about future work: if a later order evaluates multiple systems on this case set, the single-system null does NOT transfer — each system requires its own preregistered test with its own multiplicity treatment, and any between-system comparison requires its own design (the system identity must distinguish the complete versioned system configuration, not merely the model name, per the M3 versioned-system-configuration requirement). No comparison method may be selected for convenience; none is selected here because none is needed.

## 12. Provenance

```text
Order:              SRE-v1 STATISTICAL NULL MODEL RECONCILIATION & PRE-REGISTRATION CLOSURE v1
Designed:           2026-09-12
Design baseline:    jsiadyarslan-lab/ECP main @ 5fc90484f1fc4b7fa0cf21a92b41274414c24d24
Design source:      SCIENTIFIC-REASONING-EVALUATION-v1-PREREGISTRATION.json
                    (sha256 0cd5bea53c72dff2f7c49e10fd79874cd28ac16982d1b28370719f02f0002d30)
Derivation engine:  exact rational arithmetic (fractions.Fraction); two independent
                    implementations cross-checked; scipy.stats cross-check;
                    Clopper-Pearson equivalence proof; exhaustive strategy verification;
                    1,680-permutation exact averages; 19,683-vector analytic coverage
Companion artifacts: SRE-V1-STATISTICAL-DESIGN-SPECIFICATION.md
                     SRE-V1-RECONCILIATION-MATRIX.md
                     SRE-V1-PREREGISTRATION-STATISTICAL-SECTION.md
                     SRE-V1-STATISTICAL-PARAMETERS.json (machine-readable frozen fields)
Execution status:   NO scientific execution performed; NO provider/model calls;
                    NO outcomes exist. Execution requires a separate owner order.
```
