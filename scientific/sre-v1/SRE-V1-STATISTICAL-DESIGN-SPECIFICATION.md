# SRE-V1-STATISTICAL-DESIGN-SPECIFICATION.md — Scientific Reasoning Evaluation v1: Statistical Design

**Status:** REGISTERED STATISTICAL DESIGN (frozen by owner order `SRE-v1 STATISTICAL NULL MODEL RECONCILIATION & PRE-REGISTRATION CLOSURE v1`, 2026-09-12)
**Mode:** STATISTICAL DESIGN / PRE-REGISTRATION — no scientific execution authorized or performed by this artifact
**Repository:** `jsiadyarslan-lab/ECP`, branch `main`
**Design baseline commit:** `5fc90484f1fc4b7fa0cf21a92b41274414c24d24`
**Design-phase source artifact:** `SCIENTIFIC-REASONING-EVALUATION-v1-PREREGISTRATION.json` (SHA-256 `0cd5bea53c72dff2f7c49e10fd79874cd28ac16982d1b28370719f02f0002d30`)
**Change control:** preregistration-locked; amendments per `SRE-V1-PREREGISTRATION-STATISTICAL-SECTION.md` §5 only.

---

## 1. Purpose and scope

This specification freezes the complete statistical design of the future SRE-v1 evaluation: inference type, interval procedure, primary decision rule, effect-size definition, sample-size and power derivation, multiplicity policy, dependence treatment, system-comparison boundary, simulation verification, and the data-integrity rules (void / missing / rerun / stopping) that carry statistical consequences. Together with `SRE-V1-NULL-MODEL-SPECIFICATION.md` (the null model) and `SRE-V1-PREREGISTRATION-STATISTICAL-SECTION.md` (the frozen lock), it completes the statistical section of the SRE-v1 pre-registration inside the repository.

Every value below was independently re-derived during the closure order from the authoritative pool material and first principles (exact rational arithmetic; two independent implementations; exhaustive combinatorial verification) — no value was adopted from the design-phase artifact or from the non-authoritative file because it appeared there. Reconciliation against both is recorded in `SRE-V1-RECONCILIATION-MATRIX.md`.

## 2. Exact vs asymptotic inference (frozen choice)

**Frozen: exact binomial inference.** Normal or any other asymptotic approximation is rejected for the primary analysis.

| Item | Record |
|---|---|
| Chosen method | exact one-sided binomial test (survival function of Bin(N_obs, p0)); exact Clopper-Pearson bounds |
| Reason | at N = 9 (and the degradation case N_obs = 8) the normal approximation to the binomial is invalid by any textbook rule of thumb (np0 = 3 < 5, n(1-p0) = 6 < 10 at p0 = 1/3); discreteness and skew at p0 = 1/3 make continuity corrections unreliable; the exact test is available in closed rational form, so there is no reason to accept approximation error where zero error is achievable |
| Assumptions | the binomial null model of `SRE-V1-NULL-MODEL-SPECIFICATION.md` §2.2/§4 (exchangeable independent Bernoulli(1/3) under H0) |
| Alternative considered | (a) normal-approximation z-test — rejected: invalid at this N and p0; (b) score test (Wilson) — rejected: asymptotic ordering not guaranteed at N=9 and offers no exactness gain over the exact test; (c) permutation test — rejected: wrong null (see null-model spec §9) |
| Reason alternatives rejected | exactness at small N is achievable and free of charge; every asymptotic alternative strictly dominates nothing and risks mis-sizing |

The choice was made **before any outcome exists** (zero executions project-wide at design time) and is frozen: no switch to an asymptotic method is permitted after outcomes are observed.

## 3. Confidence-interval procedure (frozen)

```text
confidence level      : 95% (one-sided) for the DECISION bound; 90% two-sided for
                        the DESCRIPTIVE interval — these are the same lower bound
estimator            : X / N_obs (observed success proportion; point estimate of theta_bar)
decision interval    : one-sided 95% Clopper-Pearson LOWER bound on X/N_obs
                        (0 if X = 0; else Beta.ppf(0.05; X, N_obs - X + 1))
decision criterion   : reject H0 iff one-sided 95% CP lower bound > p0 = 1/3
descriptive interval : two-sided 90% Clopper-Pearson interval for X/N_obs
                        (its lower bound IS the one-sided 95% lower bound)
boundary handling    : X = 0 -> lower bound 0 (no rejection); X = N_obs -> upper
                        bound 1; both handled by the standard Beta form
two-sided / one-sided: the DECISION is one-sided (H1 is directional); the
                        DESCRIPTIVE interval is two-sided 90% — never re-interpreted
                        as two-sided 95%, whose lower bound would correspond to
                        one-sided alpha = 0.025 (a different, unregistered test)
```

One interval method is used for all primary analyses, fixed before execution. The mechanical equivalence between the CP-bound formulation and the critical-count formulation `X >= k*` is proven (verified for every x and n in {8,9}); the two are the same inference and are never mixed.

## 4. Primary decision rule (frozen)

```text
test statistic        : X = successes among N_obs valid executions
null parameter        : p0 = 1/3 (strategy-proof balanced-ternary null)
alternative           : H1: theta_bar > p0 (one-sided, upper)
alpha                 : 0.05 one-sided (nominal); actual size 835/19683 = 0.042423
                        (exact-test conservatism, disclosed)
tail direction        : upper
rejection criterion   : X >= k*(N_obs);  k*(9) = 6;  k*(8) = 6 at p0_miss = 3/8
```

Verdict mapping (single, unambiguous, frozen):

| Verdict | Condition |
|---|---|
| **SUPPORTED** (reject H0) | N_obs >= 8 AND X >= k*(N_obs) |
| **NOT SUPPORTED** (fail to reject H0) | N_obs >= 8 AND X < k*(N_obs) — the claimed capability is not established by this design; this is not proof of incapability |
| **INCONCLUSIVE — PROTOCOL FAILURE** | N_obs <= 7 (two or more missing cases; infrastructure reliability below 8/9 invalidates the execution-layer premise; no capability verdict is issued; a full re-run requires a new owner order) |

The INCONCLUSIVE verdict is used only where permitted by this preregistered protocol (infrastructure failure floor), never as an outcome-driven escape hatch. No new decision rule may be introduced after results are observed.

## 5. Effect size (frozen estimand and measure)

```text
estimand            : theta_bar = mean over the 9 frozen SRE-v1 cases of the
                      per-case success probability of the single frozen evaluated
                      system under the frozen execution protocol
scope               : finite, enumerated evaluation universe (9 cases x 1 system);
                      NO cross-system generalization; NO case-population inference
                      beyond the frozen enumeration
primary effect measure: the observed success proportion X/N_obs (point estimate of
                      theta_bar), reported with the one-sided 95% CP lower bound
secondary (descriptive) contrast: absolute difference X/N_obs - p0
rejected as primary : risk ratio and odds ratio (no actionable interpretation for a
                      capability-vs-null question at these margins); any theta_min
                      inferiority region (would add a second decision surface —
                      a multiplicity violation)
```

The estimand is defined independently of observed results and is the only estimand justified by the scientific question (does the system reason above the non-reasoning rate on this frozen universe). Effect measures were chosen before any outcome exists; the measure that makes a eventual result appear strongest may not be promoted post-hoc.

## 6. Sample size and power (derived, not chosen)

### 6.1 Inputs (all independently derived)

```text
alpha               : 0.05, one-sided (directional-superiority convention for a
                      capability claim; exact test)
target power        : 0.80 (confirmatory convention, beta:alpha = 4:1; the primary
                      scientific risk is a FALSE capability claim, guarded by exact
                      alpha and preregistration; a missed true capability can be
                      re-examined under a new order, a false claim corrupts the record)
null parameter p0   : 1/3 (SRE-V1-NULL-MODEL-SPECIFICATION.md §3)
alternative p1      : 0.80 — derived from (a) the capable-system profile over the
                      frozen difficulty composition (1 SHALLOW x 0.95 + 7 MEDIUM x
                      0.80 + 1 DEEP x 0.50)/9 = 0.7833 -> nearest conventional
                      capability bar 0.80, and (b) the criterion-referenced mastery
                      convention (reliable capability = 4-of-5 success on
                      individually verifiable problems = 0.80)
test                : exact one-sided binomial (the frozen rule itself — power is
                      computed FOR the exact rule, not a surrogate)
direction           : upper
```

### 6.2 Derivation

The strategy-proof null REQUIRES key balance 3/3/3, so the admissible sample sizes are N ≡ 0 (mod 3). This structural constraint is frozen BEFORE the sample-size search (it is part of the null construction, not a tuning knob). Minimum-N search under the frozen rule (smallest admissible N whose exact-rule power at p1 = 0.80 meets 0.80):

| N | k* | actual alpha | power at p1 = 0.80 | verdict |
|---|---|---|---|---|
| 3 | 3 | 0.037037 (= 1/27) | 0.512000 | admissible — fails power |
| 6 | 5 | 0.017833 (= 13/729) | 0.655360 | admissible — fails power |
| **9** | **6** | **0.042423 (= 835/19683)** | **0.914358** | **minimum admissible N meeting target** |

The unconstrained minimum is N = 7 (power 0.851968) — **inadmissible**: 7 % 3 != 0, so key balance is impossible and the strategy-proof null could not be constructed. N = 9 is therefore the minimum admissible sample size: a consequence of the design, not an input. N was not chosen as a round number and then justified; the scan table and the admissibility argument are the complete derivation record.

Exact values at N = 9: alpha_actual = P(Bin(9,1/3) >= 6) = 835/19683 = 0.0424227…; power = P(Bin(9,4/5) >= 6) = 1785856/1953125 = 0.9143584…; boundary P(Bin(9,1/3) >= 5) = 2851/19683 = 0.1448497… >= 0.05 (k* = 5 correctly rejected).

### 6.3 Frozen-set mechanical selection (performance-blind)

Universe: the 21 ternary-answer-space qualified candidates (key strata YES = 8, NO = 6, CANNOT-DETERMINE = 7). Constraint: exactly 3/3/3 keys (null construction). Objective hierarchy, frozen before search: (1) maximize distinct reasoning families; (2) minimize the maximum per-family count (no family may dominate the capability claim); (3) maximize distinct difficulty levels; (4) lexicographically smallest sorted candidate-ID tuple (deterministic tiebreak). Exhaustive search over all 39,200 key-balanced subsets (C(8,3)·C(6,3)·C(7,3)) yields the unique frozen set of `SRE-V1-NULL-MODEL-SPECIFICATION.md` §10 (families 2/2/2/1/2 across five families; difficulty 1 SHALLOW / 7 MEDIUM / 1 DEEP). Selection used only structural metadata; no outcome data existed.

### 6.4 Robustness (recorded, not exploited)

- N* = 9 is unchanged under target power 0.90 (achieved power 0.914358 >= 0.90) — the power-target choice is non-consequential for this design;
- N* = 9 is unchanged for p1 anywhere in [0.75, 0.85] at alpha = 0.05;
- exact-test power is non-monotonic in N (power(7) = 0.852 > power(8) = 0.797) — a property of exact critical values, documented, not exploited;
- feasibility: required N (9) <= eligible pool (21); 12 ternary candidates remain as reserve material.

## 7. Multiplicity (frozen policy)

| Endpoint | Class | Treatment |
|---|---|---|
| X vs k* — capability above the strategy-proof null | **primary** (the only confirmatory endpoint) | exact one-sided alpha = 0.05; no correction (single primary) |
| two-sided 90% CP interval for X/N_obs | descriptive companion of the primary | no separate claim |
| per-case outcome table; family x outcome and difficulty x outcome cross-tabs | descriptive | no tests; no post-hoc promotion |
| infrastructure rates (void / missing) | protocol diagnostics | govern the INCONCLUSIVE floor, not capability claims |

There is exactly one hypothesis/end point that can produce a formal inferential claim in SRE-v1. No multiplicity correction is required, and none would be meaningful: a second "confirmatory" surface (e.g., a theta_min NOT-SUPPORTED region as in the non-authoritative file) would split the error budget and is explicitly rejected. The primary endpoint may not be moved after results are observed.

## 8. Dependence and repeated measures (frozen treatment)

- **Same system across cases**: the single frozen system is the fixed subject of the estimand, not a varying factor; its capability is the latent quantity measured. No system-level clustering exists with one system.
- **Same case across systems**: does not occur (one system).
- **Same provider / model / configuration / evaluator**: constant by design (the DEME configuration is frozen before execution and sealed; the evaluator is the frozen mechanical coding rule plus the execution-phase auditor independence rules).
- **Repeated execution**: only the single preregistered VOID-retry exists (§11); completed executions are never rerun; there is no within-case replication.
- **Paired comparisons / clustered observations**: none exist in this design.
- **Independence justification for the binomial model**: sealed per-case contexts, one execution per case, no cross-case channel, no adaptive selection after outcomes — under H0 the nine Bernoulli(1/3) indicators are independent (full argument in `SRE-V1-NULL-MODEL-SPECIFICATION.md` §6). Under H1, shared-capability dependence affects power only, and the preregistered power is computed under the i.i.d. design alternative theta_i = 0.80.

## 9. Model/system comparison boundary

SRE-v1 is a single-system capability study. The estimand makes no cross-system claim, so no comparison null (paired binary, independent-group, clustered, per-system, or hierarchical) is instantiated. Should a future order evaluate multiple systems: each system is a distinct versioned system configuration (identity = complete configuration, not model name); each requires its own preregistered single-system test; any between-system claim requires its own design and multiplicity treatment, preregistered before execution. Nothing in this specification transfers automatically.

## 10. Simulation / operating-characteristics verification (design verification only)

Monte Carlo verification of the exact rule's operating characteristics (order §18 compliance — parameters derived from this preregistered design; no real or historical outcomes used; not tuned to any observed result):

```text
simulation assumptions : X ~ Bin(9, 1/3) under H0; X ~ Bin(9, 0.8) under the design
                         alternative; rejection iff X >= 6 (the frozen rule)
replicates             : 200,000 per scenario
seed policy            : numpy RandomState(20260912) [H0]; RandomState(20260913) [p1]
                         — deterministic, disclosed, reproducible
empirical size         : 0.042325 +- 0.000450 (exact 0.042423) — within 4 sigma
empirical power        : 0.914990 +- 0.000624 (exact 0.914358) — within 4 sigma
Monte Carlo uncertainty: binomial standard errors reported above; agreement within
                         4 standard errors in both scenarios
```

The simulation confirms the exact computation; it plays no role in the decision rule and cannot be re-run with different parameters to justify a different N (any such use is prohibited by §4 of the pre-registration lock).

## 11. Data-integrity rules with statistical consequences (frozen)

These rules are statistical design: they define what counts as an observation before any execution exists.

- **Valid execution failure**: a captured model response whose declared final answer is unparseable or non-conforming is a VALID observation with outcome FAILURE — it is never void and never re-executed. (The system failed to meet the success criterion.)
- **Void execution**: an execution with NO captured model response (transport error, timeout before any model token, adapter crash without payload) is VOID — infrastructure, not an observation of the system. Exactly ONE re-execution is permitted per VOID case, under the identical frozen DEME configuration.
- **Missing case**: a case whose single permitted retry also ends VOID is MISSING; N_obs = 9 - #missing.
- **Degraded-null recompute (one missing case, N_obs = 8)**: remaining keys are 3/3/2 for any missing key class, so the balance degrades to p0_miss = max(remaining key counts)/N_obs = 3/8 >= 1/3; k*(8) = min{k : P(Bin(8, 3/8) >= k) < 0.05} = 6 (identical critical count to N = 9); achieved power at N_obs = 8 is 0.796918 (within 0.4% of target — the design degrades gracefully).
- **Floor**: N_obs <= 7 (two or more missing) -> verdict INCONCLUSIVE — PROTOCOL FAILURE; no capability verdict; a full re-run requires a new owner order.
- **No outcome-based selection**: voids are infrastructure-caused only, by this frozen taxonomy; missingness can never be triggered by response content; no case may be excluded or reclassified on the basis of its outcome.
- **Stopping rule**: fixed N = 9; no interim analyses; no early stopping for outcomes; the study terminates when all 9 frozen cases hold a terminal status (success | failure | missing).

## 12. Sensitivity analysis (recorded at design time)

Design-consistent grid (balanced domain N % 3 == 0), minimum admissible N meeting target power:

| alpha / target \ p1 | 0.70 | 0.75 | 0.80 | 0.85 | 0.90 |
|---|---|---|---|---|---|
| 0.05 / 0.80 | 15 | 9 | 9 | 9 | 6 |
| 0.05 / 0.90 | 18 | 15 | 9 | 9 | 9 |
| 0.025 / 0.80 | 18 | 12 | 12 | 9 | 6 |
| 0.025 / 0.90 | 21 | 18 | 12 | 12 | 9 |

Counterfactual null constructions (unconstrained N*, recorded to show the null drives the sample size): binary answer space p0 = 0.5 -> N* >= 18 (and would misrepresent the actual ternary answer space); unbalanced full-pool modal null 8/21 -> N* = 10.

The primary configuration (p0 = 1/3, p1 = 0.80, alpha = 0.05 one-sided, target 0.80 -> N* = 9) was frozen independently of this grid; no combination was selected for favorability.

## 13. Provenance

```text
Order:              SRE-v1 STATISTICAL NULL MODEL RECONCILIATION & PRE-REGISTRATION CLOSURE v1
Designed:           2026-09-12
Design baseline:    jsiadyarslan-lab/ECP main @ 5fc90484f1fc4b7fa0cf21a92b41274414c24d24
Derivation engine:  exact rational arithmetic; two independent implementations;
                    scipy cross-checks; CP-equivalence proof; exhaustive 39,200-subset
                    selection; 1,680-permutation strategy verification; seeded MC
                    verification (200k replicates per scenario)
Companion artifacts: SRE-V1-NULL-MODEL-SPECIFICATION.md
                     SRE-V1-RECONCILIATION-MATRIX.md
                     SRE-V1-PREREGISTRATION-STATISTICAL-SECTION.md
                     SRE-V1-STATISTICAL-PARAMETERS.json (machine-readable frozen fields)
Execution status:   NO scientific execution performed; NO provider/model calls;
                    NO outcomes exist. Execution requires a separate owner order.
```
