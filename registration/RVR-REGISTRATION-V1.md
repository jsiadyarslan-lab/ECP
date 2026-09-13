# ECP — RVR PREREGISTRATION FREEZE v1 — Registration Record

**Campaign:** `ECP-EVAL-RVR-1` · **Registered:** 2026-09-13 ·
**Status:** **PREREGISTERED — EXECUTION LOCKED**

Registered under the owner order *ECP — REASONING vs RETRIEVAL
PREREGISTRATION FREEZE v1* from Design v1.1 (PASS — DESIGN COMPLETE).
Baseline: `jsiadyarslan-lab/ECP` @ `main` = `562e18809bcb448bd2e1717e73c2fd9386a7fa8a` (verified
HEAD == origin/main, tracked tree clean before the registration write).

## Campaign (owner freeze §3 — default, no expansion)

24 matched variant sets = **96 cases = 96 one-shot executions**
(retry NONE). Grid: 4 families (F1 transitive-compositional relational,
F2 quantitative comparison, F3 consistency/contradiction, F4 multi-premise
evidence integration) × 3 depth strata (D1–D3) × 2 MVS per cell. Each MVS
= V-BASE / V-RPT / V-FLIP / V-LURE.

## Frozen thresholds (§3)

| Rule | Frozen value |
|---|---|
| G-0 | BCR ≥ 0.60 AND evaluable CFTR denominator ≥ 15 AND IVR+EFR ≤ 0.25 |
| R1 | CFTR ≥ 0.70 |
| R2 | RIR ≥ 0.70 |
| R3 | LCR ≤ 0.25 OR LRR ≥ BCR − 0.15 |
| R4 | EFR ≤ 0.15 |
| M1 | BCR ≥ 0.60 AND CFTR ≤ 0.40 |
| M2 | LCR ≥ 0.50 |
| M3 | BCR ≥ 0.60 AND RIR ≤ 0.50 |

All values adopted verbatim from Design v1.1 §G (owner review confirmed
without change; no amendment). No threshold may be selected or altered
after any experimental execution.

## Hypotheses (§4) and interpretation boundary

H-RVR-1 (behavioral structure-tracking), H-RVR-2 (attribution compound),
H-RVR-3 (protocol integrity). Frozen boundary: failure of H-RVR-1 does
not by itself prove retrieval/memorization/surface matching; Pattern M
requires its own registered criteria; Pattern R remains bounded to
behavioral evidence more consistent with reasoning-like structure-tracking
than with the registered alternatives. Prohibited phrasings: "the model
reasons"; "reasoning has been proven"; "memorization has been proven
absent".

## Primary endpoint (§9)

**CFTR — Counterfactual Flip-Tracking Rate** (numerator: evaluable MVS
with V-FLIP CORRECT; denominator: registered MVS with V-BASE CORRECT,
both executions VALID, V-FLIP classifiable; exclusions reported, never
silent). Secondary endpoints frozen as labeled, never promotable: RIR,
LRR, LCR, BCR, STP, EFR, IVR, ECCE-RVR, CIT (provenance only).

## Decision rules (§10)

G-0 gate → Pattern R / Pattern M / Pattern I (INDETERMINATE is a
legitimate outcome; family-contradiction dominance rule; full STP
disclosure; Claim-C ceiling; Claim-D prohibited).

## Classifier (§8)

`RVR-CLASSIFIER-1` — `src/ecp/rvr_classifier.py`
(sha256 `901a90ac53714974…`): terminal ANSWER-envelope parsing
only; ten-state taxonomy; D1/D2/D3 resolutions carried; CITATION
non-scoring.

## Validation (§7/§11)

`RVR-VALIDATION-V1.json`: **23/23 checks PASS; 0 failures** — independent
dual-implementation GT derivation (96/96), matched-variant battery
(MV-01..MV-08), leakage audit (LK-01..LK-10; 172 generated names with
zero M3 collisions; 1571 composed 5-grams with zero M3-corpus overlap;
shared function/predicate vocabulary disclosed as registered template
language), classifier self-test CL-01, integrity checks INT-01..INT-04.

## Ground truth (§6)

Sealed as `gt_commitment` (SHA-256 over canonical
{case_id, ground_truth}) for all 96 cases; plaintext GT lives ONLY in
the owner-held private sidecar `RVR-PRIVATE-GT-SIDECAR-V1`
(sha256 `115005be8b4677e5…`), delivered at freeze, never committed.
GT is mechanically derivable from the registered premises and was
independently validator-derived for all 96 cases.

## M3 separation (§2/§6/§17)

No M3 case, entity, premise, GT value, surface, or historical outcome is
imported; the M3-exposed 18 remain REQUIRES REAUTHORING — PENDING OWNER
DECISION (default INELIGIBLE); no M3 file was modified (strictly
additive registration).

## Cryptographic freeze (§12)

Package hash (ECP-CANONICAL-JSON-1.0, integrity.package_hash excluded):
`c84a98321562ccd5…`. Full record: `RVR-HASH-RECORD-V1.json`; machine
manifest: `RVR-REGISTRATION-MANIFEST-V1.json`. The registration Git
commit is recorded in the delivered final report and session worklog.

## Stop (§14)

No provider call, no model execution, no case execution, no GT exposure,
no CFTR/RIR/LCR computation, no outcome inspection. The next phase
requires a separate owner order: **REGISTRATION → EXECUTION**.
