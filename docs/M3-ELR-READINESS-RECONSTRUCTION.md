# M3-ELR Readiness Reconstruction Record (2026-09-13)

**Order context:** owner delivery directive 2026-09-13 — "push the changes",
issued after the executive evaluation of the M3-ELR READINESS phase and the
BLOCKED execution report (baseline loss). This document is the honest
reconstruction record required by the project's custody-recovery precedent.

## 1. What was lost (custody event D-01, recurrence #7)

The M3-ELR READINESS phase originally completed at local commit **c49b18f**
(20 files, +6046/−12): the logical classifier, the registration contract,
the registered-case loader, the §22 gate, the scientific launcher, the
schema, 49 tests, the phase doc, and the two frozen registration artifacts.
The commit was local-only at phase close (push blocked by GitHub token
custody absence, D-01 #6), and the subsequent environment reset destroyed
the clone holding it. `origin/main` remained at `5c14d2a` with zero M3-ELR
artifacts; no byte-exact copy of any c49b18f file survived (tool-results
audit: only worklog reads and pre-existing module reads). The SRE-v1
evaluated-system & DEME owner decision gate (commit `6fefa0a`) was lost the
same way.

## 2. What was recovered byte-exact (hash-proven)

| Artifact | Recovery method | Verification |
|---|---|---|
| `owner-decision-sre-v1-evaluated-system-deme.json` | surviving deterministic builder over the 5c14d2a baseline + pinned-hash timestamp search | registration_hash `461bba57d524d8ec1fc90408b61fb099e787cba9bcfc3f91c3486fa5833ef119` verified from disk; original `decision_timestamp` recovered as `2026-09-12T15:29:29Z`; validator 15/15 PASS; delivered at commit `0e19f6d` |
| CA0v1 case material (30 cases + GT) | `scripts/ecp_ca1_ca0v1_rederive.py` (surviving, byte-stable) + `authoring-intake` with the original parameters | source doc `8144818c…425d` MATCH; sidecar `0f4e2318…` MATCH; intake report `fc8a3532…` MATCH |
| F-01b stratified ordering | re-derivation of the documented rule over the recovered case material | first three registered tests **ECP-TEST-M3-ELR-006 / -008 / -015** — exactly the sequence quoted by the readiness report §H and the owner's execution order §7 |

## 3. What was re-implemented (reconstruction, honestly labeled)

The machinery was re-implemented to the documented contracts (worklog +
readiness report + surviving builder API):

- `src/ecp/logical_classifier.py` — M3-ELR-LOGICAL-CLASSIFIER-1: three-way
  classification (DERIVABLE / CONTRADICTED / INDETERMINATE, never collapsed),
  answer-state taxonomy (7 states), premise-citation rule (index or >= 5
  consecutive verbatim words), TERNARY/BINARY/VALUE answer spaces with frozen
  value-matching normalization, infrastructure/reasoning separation.
- `src/ecp/m3_registration.py` — intake battery (re-runs the qualification
  engine's own `verify_ground_truth` + symbol coverage + value agreement),
  package builder/verifier, F-01b ordering, frozen identities.
- `src/ecp/registered_cases.py` — fail-closed four-surface hash loader
  (canonical == embedded == package == manifest), deterministic
  PREMISES/QUESTION presentation, protected GT access.
- `src/ecp/m3_readiness.py` — the §22 pre-run integrity gate (18 checks).
- `run_m3_elr_console.py` — the scientific execution surface
  (`--verify-only` proves the wiring without a credential).
- `schemas/m3-registration-package.schema.json` — registered additively in
  the 0.8.0 bundle (`validate.py` + `versions.py`).
- `OpenRouterChatCompletionsAdapter` extension — registered-case prompt
  authority + optional frozen sampling policy (temperature / max_tokens /
  timeout; `None` defaults preserve the historical payload byte-for-byte —
  tested).
- Session-gateway clock fix (reproduction of the original engineering fix):
  console-session tests were wall-clock dependent (17 failures at the
  5c14d2a baseline, reproduced this session); `SessionCredentialGateway`
  gained an optional injected clock (production default unchanged) and the
  fixture injects the frozen clock into the session gateway + onboarding
  service.
- 50 tests across 4 files (15 + 15 + 13 + 7).

## 4. The re-frozen registration package

- **Package:** ECP-PKG-M3-ELR-V1 (same registered identity).
- **Operative package hash (this reconstruction):**
  `6f5c57a3e6b5a8fb1360036207d20868e31d2b409087645a25da4491c7ccd6b4`
- **Historical package hash (lost original, permanently historical):**
  `a6e560930c8014122709a30e74b6e9c334f6069f2552290cd9d4307c54613191`
  — verification against it is impossible by construction; it is recorded
  in the package's RECONSTRUCTION disclosure and here.
- **Target discovery record hash (this reconstruction):**
  `7d5cf39eb7d6b6a9c148389c607544365f4744e338b0305656cc38dfb9041b7c`
- Registered content matches the documented original distributions
  exactly: 30 cases; 6 families x 5; SHALLOW 6 / MEDIUM 19 / DEEP 5;
  TERNARY 21 / BINARY 5 / VALUE 4; ternary keys YES 8 / NO 6 /
  CANNOT-DETERMINE 7; 14 strata; F-01b first test ECP-TEST-M3-ELR-006.
- Intake battery this run: 30/30 PASS, 0 fatal issues, 59 carried findings
  (the lost original recorded 58; the one-finding difference is a
  reconstruction artifact of the battery's finding composition, disclosed
  here).

**Why the hash differs:** the package embeds `registered_at` (a live
timestamp at freeze time); the original timestamp died with the lost commit.
The scientific content (case material, GT commitments, ordering, target,
condition) is byte-exact re-derived; only the wrapper fields (timestamp,
disclosure wording) are reconstructed.

**Scientific validity of the reconstruction:** pre-execution and
outcome-blind. Zero model calls, zero provider calls, and zero outcomes
existed project-wide at reconstruction time — no observation could have
influenced any registered value. The reconstruction is recorded in the
package's RECONSTRUCTION disclosure.

## 5. Boundary accounting at reconstruction close

- Scientific executions: 0; provider calls: 0; model calls: 0; outcomes: 0.
- Protected ground truth: sealed in the private qualification area; the
  repository carries commitments only; boundary discipline unchanged.
- Credential: `OPENROUTER_API_KEY` is an owner-side launch input; it enters
  only the in-process session credential gateway; never a file, never Git,
  never evidence.
- Historical artifacts: SRE-v1 (5/5), owner decision gates, native
  registration set, provenance, scientific/, spec/ — untouched (the only
  repo-root change besides this reconstruction is the byte-exact DEME gate
  recovery commit `0e19f6d`).

## 6. Running the registered campaign (owner-side)

```bash
cd /home/z/ecp-repo
OPENROUTER_API_KEY=<owner key> python run_m3_elr_console.py
# wiring proof without a credential:
python run_m3_elr_console.py --verify-only
```

Evidence persists under `/home/z/ecp-m3-elr-evidence/` (outside the
repository; per-execution evidence + audit + campaign ledger).
