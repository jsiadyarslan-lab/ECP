# SRE-V1-PREREGISTRATION-STATISTICAL-SECTION.md — Frozen Pre-Registration Statistical Section

**Status:** FROZEN PRE-REGISTRATION (statistical section), registered into `jsiadyarslan-lab/ECP` by owner order `SRE-v1 STATISTICAL NULL MODEL RECONCILIATION & PRE-REGISTRATION CLOSURE v1` (2026-09-12)
**Repository:** `jsiadyarslan-lab/ECP`, branch `main`
**Design baseline commit:** `5fc90484f1fc4b7fa0cf21a92b41274414c24d24`
**Design-phase source artifact:** `SCIENTIFIC-REASONING-EVALUATION-v1-PREREGISTRATION.json` (SHA-256 `0cd5bea53c72dff2f7c49e10fd79874cd28ac16982d1b28370719f02f0002d30`)
**Machine-readable companion:** `SRE-V1-STATISTICAL-PARAMETERS.json` (same directory; hash-frozen with this document)

---

## 1. Registration statement

This document freezes the statistical section of the SRE-v1 pre-registration. From this point, the fields in §2 are **locked**: any change requires a formal amendment (§5). The statistical design was reconciled and independently re-derived before this lock (see `SRE-V1-RECONCILIATION-MATRIX.md`); zero scientific executions, zero model calls, and zero outcomes exist project-wide for SRE-v1 at the moment of freezing. The non-authoritative file that previously occupied this path namespace (`scientific/sre-v1/power/power-analysis.json`) is NOT part of this registration and is explicitly superseded by it.

This registration covers the **statistical design**. Execution-phase registration mechanics (DEME declaration and sealing, execution-order machinery) remain subject to a separate owner order, as fixed by the design-phase order v4 §20.

## 2. Frozen fields (order §21)

| Field | Frozen value |
|---|---|
| **primary endpoint** | X = number of successes among the N_obs valid executions of the 9-case frozen set; per-case success = declared final answer in {YES, NO, CANNOT-BE-DETERMINED} matching the preregistered key class AND explicit citation of at least one premise (premise index or verbatim fragment >= 5 consecutive words); mechanical, auditor-replayable coding |
| **null model** | scientific null: the system does not exceed the content-blind rate on the key-balanced frozen set; statistical null: theta_i = 1/3 for every frozen case i, hence X ~ Binomial(N_obs, 1/3) — full operational statement in `SRE-V1-NULL-MODEL-SPECIFICATION.md` §2 |
| **p0** | 1/3 (strategy-proof balanced-ternary null; keys 3/3/3) |
| **N** | 9 frozen cases (minimum admissible N meeting target power under the frozen rule; derived, not chosen) |
| **threshold** | k*(9) = 6; k*(8) = 6 at the degraded null p0_miss = 3/8 |
| **alpha** | 0.05, one-sided (upper); actual size 835/19683 = 0.042423 (exact-test conservatism, disclosed) |
| **power target** | 0.80 (confirmatory convention, beta:alpha = 4:1); achieved 1785856/1953125 = 0.914358 under the exact rule at p1 = 0.80 |
| **effect-size definition** | estimand theta_bar (mean per-case success probability of the single frozen system over the frozen 9-case universe); primary measure X/N_obs with one-sided 95% CP lower bound; descriptive contrast X/N_obs - p0; no theta_min region; RR/OR not primary |
| **test** | exact one-sided binomial test of H0: X ~ Bin(N_obs, 1/3); single decision surface; reject iff X >= k*(N_obs) |
| **CI method** | decision: one-sided 95% Clopper-Pearson lower bound on X/N_obs, reject iff > p0; descriptive: two-sided 90% Clopper-Pearson interval (identical lower bound; never re-interpreted as two-sided 95%) |
| **multiplicity rule** | single primary endpoint; all other quantities descriptive (two-sided 90% CP interval, per-case table, family x outcome / difficulty x outcome cross-tabs); no post-hoc promotion; no alpha reallocation |
| **decision rule** | SUPPORTED iff N_obs >= 8 AND X >= k*(N_obs); NOT SUPPORTED iff N_obs >= 8 AND X < k*(N_obs); INCONCLUSIVE — PROTOCOL FAILURE iff N_obs <= 7 (no capability verdict; re-run requires a new owner order) |

Frozen data-integrity rules governing the analysis set (full statements in `SRE-V1-STATISTICAL-DESIGN-SPECIFICATION.md` §11): captured-response failures are VALID failures (never void, never rerun); no-response executions are VOID with exactly one permitted retry under the identical frozen configuration; a case whose retry is also VOID is MISSING (N_obs = 9 - #missing; one-missing recompute at p0_miss = 3/8 with k*(8) = 6); missingness is infrastructure-caused only, never outcome-based; fixed N = 9, no interim analyses, no early stopping for outcomes.

Frozen case-set identity (the null-construction material): the 9 candidates with content hashes listed in `SRE-V1-NULL-MODEL-SPECIFICATION.md` §10, selected mechanically and performance-blind from the 21 ternary qualified candidates (selection rule in `SRE-V1-STATISTICAL-DESIGN-SPECIFICATION.md` §6.3).

## 3. Verdict semantics (frozen)

- **SUPPORTED (reject H0)**: the observed successes exceed what any content-blind process can achieve in expectation on the frozen key-balanced universe, at one-sided alpha = 0.05 under the exact rule. Bounded claim: capability on THIS frozen universe under THIS frozen protocol; no cross-system or case-population generalization.
- **NOT SUPPORTED (fail to reject H0)**: the claimed capability is not established by this design. This is not proof of incapability and must not be reported as such.
- **INCONCLUSIVE — PROTOCOL FAILURE**: infrastructure reliability fell below the 8/9 execution floor; no capability verdict is issued; a full re-run requires a new owner order.

## 4. No post-hoc statistical repair (order §22 — prohibitions)

After any SRE-v1 outcome is observed, the following are PROHIBITED (each would invalidate this registration):

```text
changing N after seeing outcomes
changing p0 after seeing outcomes
changing alpha after seeing outcomes
switching one-sided / two-sided after seeing outcomes
switching CI method after seeing outcomes
changing the primary endpoint after seeing outcomes
removing failed cases
reclassifying failed cases to improve power
selective reruns
outcome-driven case exclusion
```

Additional frozen prohibitions: no re-execution of any completed (captured-response) case; no missingness triggered by response content; no promotion of descriptive cross-tabs to inferential claims; no re-interpretation of the two-sided 90% descriptive interval as the decision bound.

## 5. Amendment procedure (order §21)

Any change to a frozen field requires a formal amendment record that:

1. preserves this document and the machine-readable companion unchanged in the repository history (append-only governance: the amended text lives in a NEW versioned file; this file is never edited in place);
2. states what changed, why the change is scientifically necessary, when it was made, and who authorized it (the owner, or an owner-delegated authority recorded in the amendment);
3. declares whether execution had begun and whether any results had been observed at the time of the amendment;
4. carries a fresh SHA-256 for the amended artifact and a cross-reference to this registration.

An amendment made after outcomes were observed bears the label POST-OUTCOME AMENDMENT and may not be used to convert a NOT SUPPORTED or INCONCLUSIVE verdict into SUPPORTED, nor to strengthen any claim; it can only narrow claims.

## 6. Execution boundary

This registration authorizes NO execution. Real case execution, model calls, external provider calls, new scoring, and any audit execution remain forbidden until a separate owner order. The evaluated system's DEME configuration must be frozen and sealed BEFORE the first case execution of the execution phase; the execution-phase artifact set must reference this registration by its commit and hashes.

## 7. Hash-freeze manifest

The statistical design is frozen as the following artifact set (this directory); SHA-256 values are recorded in the closure execution report and the repository commit of this order:

```text
SRE-V1-NULL-MODEL-SPECIFICATION.md
SRE-V1-STATISTICAL-DESIGN-SPECIFICATION.md
SRE-V1-RECONCILIATION-MATRIX.md
SRE-V1-PREREGISTRATION-STATISTICAL-SECTION.md   (this document)
SRE-V1-STATISTICAL-PARAMETERS.json              (machine-readable frozen fields)
```

Any byte-level change to any of these files (other than via the §5 amendment procedure) invalidates this registration.
