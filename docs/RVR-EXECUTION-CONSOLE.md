# RVR Scientific Execution Console — ECP-EVAL-RVR-1

**Status:** PREREGISTERED — EXECUTION LOCKED (frozen package `ECP-REG-RVR-V1`, registration commit `10e9cc5`) → **EXECUTION BOUND** (this surface, binding `ECP-REG-RVR-BINDING-V1`)
**Campaign:** `ECP-EVAL-RVR-1` — Reasoning vs Retrieval (24 MVS = 96 cases = 96 one-shot executions)
**Target (owner-designated, pre-execution, data-blind):** `google/gemma-4-26b-a4b-it:free` @ OpenRouter
**Condition:** `ECP-COND-RVR-1` — MODEL-ENABLED, L1 model-only, temperature 0.0, max_tokens 1024, transport timeout 90 s, retrieval NONE, tools NONE, system prompt NONE

---

## What this surface is

`run_rvr_console.py` is the registered CLI execution surface for the RVR
campaign, mirroring the M3-ELR console discipline (one engine, one surface,
byte-compatible artifacts). It executes exactly the frozen registration
package against the bound target, in the frozen registered case order, ONE
attempt per case, retry NONE.

Boundaries (identical to M3, enforced in code):

* the model input is ONLY the rendered registered case presentation — the
  frozen package is the sole prompt authority; no client prompt exists;
* the credential (`OPENROUTER_API_KEY`) enters ONLY through the in-process
  session credential gateway at launch — never a file, never Git, never
  evidence;
* the sealed ground truth is compared ONLY in-process by the frozen
  `RVR-CLASSIFIER-1`; classifications (never GT) are persisted;
* execution/transport success is NEVER converted into behavioral success
  and vice versa;
* evidence + audit + ledger persist under the evidence root OUTSIDE the
  repository;
* ONE campaign per evidence root: the console refuses to start if a
  campaign ledger already exists there (one-shot discipline).

## Prerequisites (already in place in this environment)

1. Frozen package: `registration/RVR-REGISTRATION-V1.json` (hash `c84a9832…`, verified at launch).
2. Execution binding: `registration/RVR-EXECUTION-BINDING-V1.json` (hash `25f85907…`, verified at launch).
3. Private GT sidecar (NEVER in the repository): resolved as a sibling
   `ecp-rvr-private/RVR-PRIVATE-GT-SIDECAR-V1.json` next to the repository
   checkout, or via `ECP_RVR_GT_SIDECAR`, or `--gt-sidecar`.
   Every sealed answer is verified against its public `gt_commitment` at load.

## Owner launch sequence

```bash
cd <repository checkout>

# 0) wiring proof (optional, no credential, no call):
python run_rvr_console.py --verify-only

# 1) the campaign (the owner supplies the OpenRouter credential at launch):
OPENROUTER_API_KEY=sk-or-… python run_rvr_console.py \
    --evidence-root /home/z/ecp-rvr-evidence

# 2) post-campaign mechanical adjudication (frozen §G rules, no GT needed):
python tools/rvr_adjudicate.py --evidence-root /home/z/ecp-rvr-evidence
```

The adjudication report (`rvr-adjudication.json` under the evidence root)
carries the CFTR primary endpoint, the nine labeled secondaries, the STP
table, the per-family table, the G-0 gate evaluation, the final
**Pattern R / M / I** determination and the frozen claim-boundary language
(Pattern R is a Claim-C statement only; INDETERMINATE is a valid scientific
outcome; nothing licenses "the model reasons" or "memorization excluded").

## Tests

`tests/test_rvr_campaign.py` — 14 hermetic offline tests (zero network):
engine artifact shapes and frozen order, transport-failure path
(INVALID_EXECUTION, never converted), NON_ANSWER / abstention / malformed
routing, fail-closed loaders (package / sidecar / binding tampering), and
the adjudicator's mechanical G-0 / R / M / I determinations on synthetic
ledgers (including the association-override M1 signature and the mixed-
profile INDETERMINATE middle). Full repository regression: **1202 passed**
(1188 prior + 14 new), zero failures.

## File map (all additive; zero M3 files touched)

| File | Role |
|---|---|
| `registration/RVR-EXECUTION-BINDING-V1.json` | owner-authorized pre-execution target + condition + surface binding (hash-sealed) |
| `src/ecp/rvr_registration.py` | fail-closed loaders: package, binding, GT sidecar; frozen prompt rendering |
| `src/ecp/rvr_campaign.py` | the ONE campaign engine (evidence / audit / ledger) |
| `src/ecp/rvr_classifier.py` | RVR-CLASSIFIER-1 (frozen at registration commit `10e9cc5`) |
| `run_rvr_console.py` | the registered CLI execution surface |
| `tools/rvr_adjudicate.py` | post-campaign mechanical adjudication (frozen §G rules; CP 95% precision aids) |
| `tests/test_rvr_campaign.py` | hermetic offline test battery |
