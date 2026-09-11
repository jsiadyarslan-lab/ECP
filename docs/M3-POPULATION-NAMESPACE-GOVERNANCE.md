# M3 Population Namespace Governance & Collision Closure (v1)

**Order:** M3 AUTHORITATIVE SCIENTIFIC POPULATION GOVERNANCE & NAMESPACE COLLISION CLOSURE v1
**Date:** 2026-09-12 · **Mode:** scientific artifact governance / provenance reconciliation / namespace isolation
**Baseline:** `7420eac` (Universal Experiment Execution Contract v1 — unchanged by this phase)
**Machinery:** `src/ecp/populations.py` · manifest: `provenance/m3-population-namespace-manifest.json` · tests: `tests/test_populations.py` (34)

---

## 1. Context

The M3 artifact-identity reconciliation (AIR v1.1, 2026-09-11) proved a
**candidate-ID namespace collision**: `ECP-CAND-000101..000103` denote
different content in the CA0v1 authored 30-candidate pool and in the
registered 3-case ECP-native corpus. Both chains are individually
hash-consistent; no artifact is mutated, renamed, or deleted by this
governance phase. The purpose here is to *prove identity, relationship,
and boundaries between artifacts as they actually are*, and to make the
collision structurally impossible to exploit.

Chronology (proven from artifact timestamps and git history): the CA0v1
pool was authored `2026-09-09T03:55:45Z` (machinery committed `e849b13`,
2026-09-09); the native corpus was authored 2026-09-10 (ECP registration
commits `fa1b6a7..6f58381`, 2026-09-10) and **re-used the already
occupied ID range**. No artifact on either side declares a relationship
(replacement, derivation, or equivalence) toward the other:
`RELATIONSHIP = UNKNOWN` on both sides, and no relationship is invented.

## 2. Population inventory

| | Population A — Native | Population B — CA0v1 | Reference — JARVIS |
|---|---|---|---|
| population_id | `ECP-POP-M3-NATIVE-V1` | `ECP-POP-M3-CA0V1-V1` | — (not an ECP population) |
| case_pack_id / version | `ECP-CASEPACK-M3-NATIVE` / 1 | `ECP-CASEPACK-M3-CA0V1` / 1 | — |
| candidate_count | 3 (`ECP-CAND-000101..103`) | 30 (`ECP-CAND-000101..130`) | 23 authored cases (`M3-S30-*`) |
| authored_at | 2026-09-10T17:02:00Z (artifact clock; see §7 note) | 2026-09-09T03:55:45Z | historical, sha-pinned `cc867e97…` |
| source artifact sha256 | `1ef751de…` (native-case-set.md, protected store) | `8144818c…` (candidate case-set, private area) | `cc867e97…` (`pilots/m3/m3_cases.md`) |
| qualification | ACCEPT ×3 — **persisted** (protected store) | ACCEPT ×30 — **recorded only** (artifacts not persistently present) | never qualified in ECP |
| registration | registered (`ECP-REGSET-M3-NATIVE-V1`, 3 records) | none (pool material by design) | excluded by the native registration scope |
| status | HISTORICAL-PRESERVED-READ-ONLY | HISTORICAL-PRESERVED-READ-ONLY | READ-ONLY external reference |

Population C (future) is a **conceptual namespace only**; nothing is
created, registered, or reserved for it in this phase.

## 3. Namespace model

A bare `candidate_id` is **not** a complete scientific artifact identity.
The addressable identity is the five-part tuple:

```text
population_id + case_pack_id + case_pack_version + candidate_id + content_hash
```

The only permitted resolution path is the population-qualified lookup:

```text
lookup(population_id, case_pack_id, case_pack_version, candidate_id)
    -> identity, then verify content_hash
```

Unqualified `lookup(candidate_id)` is **rejected fail-closed**
(`AMBIGUOUS_ID -> REJECTED`) whenever multiple populations are
registered — regardless of how many populations currently contain the
id. Today's unique id is tomorrow's collision: the native corpus proved
exactly this failure mode when it silently re-used `ECP-CAND-000101..103`.

Machine-enforced invariants (`src/ecp/populations.py`):

```text
same namespace + same candidate_id + different content_hash = COLLISION   (load-time rejection)
same candidate_id + different population namespace           = distinct identities
```

## 4. Collision record (machine evidence)

```text
collision detected = YES
collision type     = cross-population candidate-ID overlap with divergent content hashes
affected IDs       = ECP-CAND-000101, ECP-CAND-000102, ECP-CAND-000103

ECP-CAND-000101 : CA0v1 28562c5c…  !=  native 8e8feb01…
ECP-CAND-000102 : CA0v1 17fcf09c…  !=  native 73fbb990…
ECP-CAND-000103 : CA0v1 06ab98eb…  !=  native 0d054c99…

provenance        = independent (no cross-declaration on either side)
isolation         = namespaces distinct; population-qualified lookup only;
                    unqualified lookup rejected; no artifact modified
```

## 5. NAMESPACE DECISION

```text
NAMESPACE DECISION = COLLISION ISOLATED / NAMESPACES VALID
```

Machine-checkable answers (order §8): overlapping IDs — yes; content
different — yes; hashes different — yes; provenance independent — yes;
representable in independent namespaces — yes (implemented); protected
cross-population lookup — yes (fail-closed); historical IDs preserved —
yes; collision isolated without artifact modification — yes.

Per the order's decision discipline (§24): namespace validity is NOT
scientific authoritativeness. Nothing about this decision authorizes
either population for scientific use.

## 6. Population assessments (evidence only)

### Population A — Native (`ECP-POP-M3-NATIVE-V1`)

* **Provenance — UNKNOWN.** The chain inside the protected store is
  hash-complete (re-verified this phase), but the authoring-order pin is
  **NULL** (all-zero sha256 in the native sidecar — the authoring
  instruction reference is not hash-pinned), and the relationship toward
  the CA0v1 pool is **undeclared** while it re-uses that pool's ID range.
* **Scientific fitness — FAIL** *as the M3 research population.* Its own
  classification closure records the scope limitation verbatim: "the
  corpus is three native cases and is not the historical 23-case
  artifact", "a future target-system validation requires a separately
  authorized execution contract". Three deterministic demonstration
  cases across three semantic families do not constitute the M3
  research population (the CA0v1 pool was authored precisely because a
  larger multi-family pool is required).
* **Integrity — PASS.** All 21/21 protected-store artifacts re-verified
  against the store manifest; registration and qualification hash
  formulas re-verified; no unexplained mutation.
* **Namespace uniqueness / historical integrity / reproducibility —
  PASS** (under the namespace model; artifacts untouched; custody
  durable).

### Population B — CA0v1 (`ECP-POP-M3-CA0V1-V1`)

* **Provenance — UNKNOWN.** The authoring chain is fully pinned and
  present (source `8144818c…`, sidecar `0f4e2318…`, intake `fc8a3532…`,
  order reference `2695594b…`), but the qualification artifact layer
  (`ECP-QUAL-000101..130`, `qualification-run.json`) is **absent from
  all durable custody** — wiped by environment resets; the layer is
  recorded in the historical session report only (chain head
  `f137598d…`, run manifest `0bb9eeee…` / run_hash `1678694c…`). The
  relationship toward the native corpus is **undeclared** (it predates
  it).
* **Scientific fitness — PASS.** 30 candidates across 6 reasoning
  families (5 each); ground-truth class distribution 14 DERIVABLE /
  8 CONTRADICTED / 1 IMPOSSIBLE / 7 INDETERMINATE; difficulty spread
  5 DEEP / 19 MEDIUM / 6 SHALLOW; mechanical ground-truth verification
  ×30 and leakage/novelty screens recorded; designed indeterminacy
  reported, never forced; no known semantic defect inside this pool
  (M3-S30-LINF-01 is JARVIS-only); authored performance-blind as M3
  pool material. Declared authoring-independence limitations
  (executor-authored, model-family overlap, author-attested NL↔FORMAL)
  remain on record and bind any future registration.
* **Integrity — PARTIAL.** Authoring/intake layer hash-verified and
  byte-reproducible; qualification artifact layer not verifiable
  (absent). Under the order's §19 rule, PARTIAL is not PASS.
* **Namespace uniqueness / historical integrity — PASS.**
* **Reproducibility / traceability — UNKNOWN.** The authoring chain is
  byte-reproducible, but the qualification layer cannot be re-verified
  this phase: requalification is forbidden by the governing order, and
  the prior-pool reference area required by `qualify-verify` is absent
  as well.

## 7. POPULATION DECISION

```text
POPULATION DECISION = BLOCKED — NO AUTHORITATIVE POPULATION
```

Basis (order §19 — any element not PASS blocks):

* CA0v1: qualification artifact layer not persistently present →
  reproducibility/traceability UNKNOWN; provenance relationship
  UNKNOWN; integrity PARTIAL.
* Native: authoring-order pin NULL; provenance relationship UNKNOWN;
  scientific fitness as the M3 research population not established
  (scope-limited demonstration corpus per its own closure record).

Per §20, no data was modified to make the decision possible; BLOCKED is
the correct outcome for the evidence as it stands.

**Observed anomaly (recorded, not blocking, hashes unaffected):** the
native population's artifact timestamps run a consistent ~+2h ahead of
the git commit timestamps of their own registration commits
(`fa1b6a7..6f58381`, 2026-09-10 15:09–15:40 UTC vs artifact clock
17:02–17:39 "Z") — consistent with a UTC+2 local time mislabelled as Z.
The offset cannot invert any chronology relevant to this decision
(CA0v1 precedes native by ~27h).

## 8. Historical integrity

```text
Native historical artifacts = unchanged (protected store @ 8a5b922, 21/21 hash-verified)
CA0v1 historical artifacts  = unchanged (source/sidecar/intake/candidates re-verified vs pins)
JARVIS                      = unchanged (m3_cases.md sha256 cc867e97…, 23 cases, worktree clean)
M3-S30-LINF-01              = unchanged (defect preserved verbatim in JARVIS; not repaired,
                               not re-authored, not re-qualified, not executed — order §15)
candidate IDs               = no renames anywhere
UEC v1 (7420eac)            = unchanged (see §9)
```

## 9. UEC v1 status

```text
7420eac = UNCHANGED (VERIFIED)
```

No defect in the Universal Experiment Execution Contract was
identified or is claimed. The namespace model is additive governance
machinery: `src/ecp/populations.py` imports nothing from the execution
path (`console`, `adapters`, `runtime_adapters`, `execution_contract`,
credential modules), creates no runner, and no adapter/provider
registry. The complete change of this phase is four new files; the diff
against `7420eac` touches zero existing files.

## 10. Remaining gates (what actually remains after this phase)

1. **CA0v1 qualification-layer persistence** — restore or explicitly
   re-establish durable custody of the qualification artifacts (a
   separate order; requalification is forbidden within this one).
2. **Relationship declaration** — an explicit owner-side declaration
   (or ruling) of the intended relationship between the native corpus
   and the CA0v1 pool (independent / superseded / derived), resolving
   the intent behind the ID-range re-use.
3. **Population re-assessment** — re-run the §19 criterion table once
   gates 1–2 are resolved; only then can an AUTHORITATIVE POPULATION be
   issued.
4. M3-S30-LINF-01 repair — only relevant if the JARVIS pack is ever
   adopted; separate order.
