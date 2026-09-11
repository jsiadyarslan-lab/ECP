# M3-CA0v1 Qualification Provenance Restoration & Authoritative Population Re-Adjudication v1

**Status:** COMPLETE — governance record · **Mode:** provenance recovery / historical evidence verification / scientific governance
**Order baseline:** `8873cb4` (ECP `main`, worktree CLEAN) · **Record date:** 2026-09-11T22:12:34Z
**Machine-checkable companion:** `provenance/m3-ca0v1-qualification-evidence-matrix.json` · **Tests:** `tests/test_ca0v1_evidence.py`

> **Artifact class: NEW GOVERNANCE/RECOVERY ARTIFACT.** This record was created during
> the recovery phase. It is not a historical artifact, not a qualification record, and
> not evidence of any historical execution. No timestamp was backdated. No
> reconstruction was executed in this phase. No historical artifact was created,
> rewritten, or re-qualified.

---

## 1. Prior state and question

The previous phase (population governance v1, commit `8873cb4`) closed with:

```text
NAMESPACE DECISION = COLLISION ISOLATED / NAMESPACES VALID
POPULATION DECISION = BLOCKED — NO AUTHORITATIVE POPULATION
```

The primary block reason was `CA0v1 qualification traceability = UNKNOWN`: the CA0v1
qualification artifact layer was absent from every durable custody location, and no
provenance investigation had yet separated *artifact recovery*, *provenance recovery*,
*historical execution provenance*, and *deterministic reconstruction*.

This phase performed exactly that separation — without re-running qualification,
without executing any experiment, and without modifying any historical record.

## 2. Repository state (verified at execution)

```text
ECP            HEAD = origin/main = 8873cb4  · branch main · worktree CLEAN
UEC v1         7420eac surfaces byte-unchanged (diff 7420eac..8873cb4 = the four
               population-governance files only, +1404/−0)
protected-store HEAD = 8a5b922  · 21/21 artifacts hash-verified · CLEAN
JARVIS         pinned ref 14b3d5d · READ-ONLY · m3_cases.md git blob d48ee57b
               IDENTICAL at the pinned ref and the externally-advanced remote tip
               0e396c86 (the advance does not touch pilots/)
ledger         GENESIS b5aef6b · 0 entries
```

## 3. Custody event history of the CA0v1 qualification layer

| When (UTC) | Event | Durable evidence |
|---|---|---|
| 2026-09-09 04:38:30 | `qualify-run ECP-QUALRUN-CA0V1-R1` executed (ACCEPT=30) | executor report (see next row) |
| 2026-09-09 04:39:30 | machinery committed & pushed | ECP commit `e849b13`, still reachable |
| 2026-09-09 04:44:30 | executor report with **all seven anchors** committed to session custody | session commit `d6c456c`; report byte-identical today (sha256 `c0a58291…`) |
| 2026-09-09 ~05–13h | **custody loss D-01 #1** — private area `/home/z/ecp-ca0v1` wiped | CA1V1 report §A |
| 2026-09-09 14:04 | **byte-exact re-derivation #1** incl. the qualification layer; `qualify-verify` INTACT; six anchors MATCH | CA1V1 report §A (chain head `f137598d`, run file `0bb9eeee`, run_hash `1678694c`, ACCEPT=30) |
| 2026-09-09 15:11 | qualification layer verified INTACT | ADJ-01 battery (34/34) |
| 2026-09-09 ~15–20h | **custody loss D-01 #2** | OWNDEC-000003 finding F-03 |
| 2026-09-09 20:15 / 20:25 | **byte-exact re-derivation #2**; `qualify-verify` INTACT twice | ADJ-02 battery (40/40 ×2) |
| 2026-09-09 21:59 / 23:02 / 23:23 | qualification layer verified INTACT | ADJ-03 (63/63), ADJ-04 (96/96), RG0 batteries |
| 2026-09-10 | **custody loss D-01 #3+**; **byte-exact re-derivation #3** (anchors `0bb9eeee` / `f137598d` / `1678694c`) | OWNDEC-000005 / OWNDEC-000006 custody records |
| 2026-09-11 20:26 | partial re-derivation (source/sidecar/intake/candidates ONLY — qualification out of order scope) | AIR v1.1 evidence bundle (commit `abde4a4`) |
| 2026-09-11 22:12 | **absence confirmed from ALL durable custody** (this investigation) | `m3_qpr_inventory.py`: 21,049 files; 4,176 git blobs across 5 repositories; zero pin matches |

## 4. Four-layer recovery separation (order §4)

### A. Artifact Recovery

| Artifact | Pin (sha256) | Status | Historical status |
|---|---|---|---|
| Authored case-set source | `8144818c…` | **FOUND** | RECONSTRUCTED-BYTE-VERIFIED (present, == pin) |
| Provenance sidecar | `0f4e2318…` | **FOUND** | RECONSTRUCTED-BYTE-VERIFIED |
| Intake report | `fc8a3532…` | **FOUND** | RECONSTRUCTED-BYTE-VERIFIED (+ git-tracked evidence copy) |
| Candidates ×30 | content hashes in intake + namespace manifest | **FOUND** | RECONSTRUCTED-BYTE-VERIFIED (30/30 triple-hash) |
| Order reference (text) | `2695594b…` | **NOT FOUND** | ABSENT (PIN-RECORDED) — text unrecoverable, hash only |
| Qualification artifacts ×30 | chain head `f137598d…` | **NOT FOUND** | ABSENT (PIN-RECORDED, RECONSTRUCTION-PROVEN) |
| Qualification run manifest | file `0bb9eeee…` / run_hash `1678694c…` | **NOT FOUND** | ABSENT (PIN-RECORDED, RECONSTRUCTION-PROVEN) |

Finding an artifact file was never conflated with proving provenance: every FOUND row
above is a **byte-verified re-derivation** whose content equals the contemporaneous
pin — the original file objects were destroyed by the D-01 custody losses.

### B. Provenance Recovery — **PARTIALLY VERIFIED**

The chain *artifact → CA0v1 → qualification process* is proven at its machinery and
input layers (engine at `e849b13` — 5/5 pinned file hashes re-verified from git
history; candidates — 30/30 canonical-hash consistent; anchors durably pinned in a
report committed six minutes after the run and byte-identical today) and is documented
across six subsequent verification sessions. It is **not** proven at the qualification
artifact layer (absent), and every attestation is executor-party — no independent
attestation exists anywhere in durable custody.

### C. Historical Execution Provenance — **PARTIALLY VERIFIED**

The qualification script exists (durable, hash-pinned). The qualification report
exists (durable, git-anchored contemporaneously). Neither was treated as automatic
proof of execution. What supports that the qualification process actually ran:
machine-timestamped contemporaneous custody commits (report at 04:44:30, six minutes
after the claimed run time 04:38:30; machinery commit at 04:39:30), and ≥3 later
sessions that re-derived the layer byte-identically and verified it INTACT. What
limits it: all attestations are same-party; the execution artifacts themselves do not
survive; no independent (non-executor) evidence exists.

### D. Deterministic Reconstruction — **RECONSTRUCTIBLE**

The qualification result is reproducible from durable inputs alone: engine @
`e849b13` (byte-verified), candidates (byte-verified), prior-pool R2 re-derivation
scripts (preserved), pinned run timestamp `2026-09-09T04:38:30Z` and operator
(recorded). Reconstruction was **proven byte-exact on at least three independent
occasions** (CA1V1, ADJ-02, owner-operational-gate re-derivations after successive
wipes), each with `qualify-verify` INTACT and identical chain head / run file /
run_hash. It was **not re-executed in this phase** — re-qualification is forbidden by
the order. **RECONSTRUCTIBLE ≠ HISTORICALLY RESTORED.**

## 5. Overall qualification recovery classification (order §5)

```text
RECONSTRUCTIBLE BUT NOT HISTORICALLY RESTORED
```

The qualification result can be reproduced deterministically and its content identity
to the contemporaneous pins is multiply proven, but the historical record objects do
not exist in any durable custody and cannot be presented as historical evidence. The
authoring/intake/candidate layer is precisely identified as byte-verified recovered
content (a PARTIALLY RESTORED sub-layer, never conflated with the qualification layer).

## 6. CA0v1 qualification traceability decision (order §8)

```text
CA0v1 QUALIFICATION TRACEABILITY = PARTIALLY VERIFIED
```

Basis: machinery, inputs, run anchors, and the subsequent verification chain are
proven from durable custody; the qualification artifact layer is absent and not
verifiable today; execution attestation is contemporaneous and machine-anchored but
same-party only; content identity of the reproducible result to the pinned historical
outputs is proven (three independent byte-exact re-derivations). This upgrades the
previous blanket `UNKNOWN` to a precisely-scoped `PARTIALLY VERIFIED` — and it does
**not** reach `VERIFIED`.

## 7. KNOWN / INFERRED / UNKNOWN (order §6, per decisive claim)

| Claim | Class | Why |
|---|---|---|
| Source / sidecar / intake / 30 candidates content == pins | **KNOWN** | byte-verified today |
| Machinery @ e849b13 == pins | **KNOWN** | git objects, re-hashed today |
| Negative existence (no original qualification objects anywhere) | **KNOWN** | exhaustive hunt (files + all git blobs) |
| Native artifacts unchanged; JARVIS m3_cases unchanged; UEC v1 unchanged | **KNOWN** | re-verified today |
| `ECP-QUALRUN-CA0V1-R1` ran at 04:38:30Z | **INFERRED** | contemporaneous same-party records only |
| 30/30 ACCEPT; GT mechanically verified ×30 | **INFERRED** | documented ×6 sessions; artifacts absent; not re-runnable |
| Chain head / run file / run_hash pins describe the historical outputs | **INFERRED** | pins + three byte-exact reproductions |
| Native ↔ CA0v1 relationship (REPLACEMENT / DERIVED / INDEPENDENT) | **UNKNOWN** | fail-closed: no provenance evidence either way |

A historical report saying X was never converted into "independently verified X".

## 8. Native ↔ CA0v1 relationship (order §9)

```text
RELATIONSHIP = UNKNOWN
```

No artifact on either side declares replacement, derivation, or independence. The
candidate-ID overlap (`ECP-CAND-000101..000103`), the second qualification-ID-range
overlap (native restarts at `ECP-QUAL-000100`; CA0v1 occupied `ECP-QUAL-000101..000130`),
and the chronology (CA0v1 2026-09-09 → native 2026-09-10) are recorded facts, but the
order's fail-closed rule forbids inferring a relationship from numbering, chronology,
similarity, or registration order. The native authoring-order pin remains NULL.

## 9. Namespace integrity & collision rule (order §10–§11)

The namespace model adopted at `8873cb4` is intact and re-verified:

- identity = `population_id + case_pack_id/version + candidate_id` verified against
  `content_hash`;
- bare `lookup(candidate_id)` is ALWAYS rejected while >1 population is registered
  (`AmbiguousCandidateIdError`, machine-enforced in `src/ecp/populations.py`);
- same candidate_id + same namespace + different content_hash ⇒ **COLLISION** (exactly
  the three recorded divergent IDs);
- same candidate_id + different population namespace + different content_hash ⇒
  **VALID CROSS-POPULATION ID REUSE** (distinct identities);
- `tests/test_populations.py` 34/34 PASS (re-run this session).

## 10. Historical immutability (order §12)

```text
Native      UNCHANGED  (protected-store 21/21 hash-verified; registration records intact)
CA0v1       UNCHANGED  (all recoverable content byte-identical to contemporaneous pins)
JARVIS      READ-ONLY  (m3_cases.md blob d48ee57b identical at pinned ref and remote tip)
LINF-01     PRESERVED-UNREPAIRED (M3-S30-LINF-01 defect present, untouched)
UEC v1      UNCHANGED  (7420eac surfaces byte-identical at 8873cb4)
```

## 11. Five-gate population eligibility (order §13–§15)

| Gate | Status | Basis |
|---|---|---|
| 1 — Provenance | **PARTIAL** | traceability PARTIALLY VERIFIED; artifact layer absent; same-party attestation only |
| 2 — Scientific Fitness | **PARTIAL** | case-content layer KNOWN and byte-verified; qualification-outcome evidence INFERRED (documented, artifact-absent); re-qualification forbidden; population size not a criterion |
| 3 — Integrity | **PARTIAL** | authoring/intake/candidate integrity fully machine-verified today; qualification-layer integrity unverifiable today |
| 4 — Namespace Uniqueness | **PASS** | namespace-qualified identity machine-enforced; collision isolated; ambiguous lookup rejected |
| 5 — Historical Integrity | **PASS** | Native / CA0v1 / JARVIS / LINF-01 / UEC v1 verified unchanged |

**Rule:** all five gates must be PASS. Four PASS out of five is insufficient.

```text
POPULATION DECISION = BLOCKED — NO AUTHORITATIVE POPULATION
```

Scientific Fitness PASS alone would not suffice; 30 candidates confer no priority;
neither population's age confers priority. The decision rests on all five gates
jointly, and three of them remain PARTIAL because the qualification record layer —
the very object this phase investigated — does not exist in durable custody as
historical evidence.

## 12. Recovery-artifact constraints honored (order §16)

No artifact was created with an old date; no timestamp was edited; no qualification
report was rewritten or re-labeled; no hash was re-created without provenance source;
no reconstruction was converted into historical evidence; nothing was hidden. The two
new governance files carry the explicit `NEW GOVERNANCE/RECOVERY ARTIFACT` class.

## 13. UEC preservation (order §17)

```text
UEC STATUS = UNCHANGED
```

No defect was found in the UEC v1 surfaces, adapters, runtime adapters, gateway, or
credential/auth layer during this verification. Nothing was modified.

## 14. Network / credential safety (order §18)

```text
M3 executions = 0 · provider calls = 0 · qualification reruns = 0 · credential access = 0
```

Investigation executed offline (local verification only). Secret scan of the full
commit diff: zero hits. The new tests invoke no provider and no network (proven by a
full suite re-run under an outbound-socket guard).

## 15. What would change the decision

Recorded for the owner — no ruling is made here: the population decision becomes
re-eligible only if the qualification record layer is restored **as historical
evidence** (e.g. the owner produces durable custody of the original artifacts or an
owner-side attestation satisfying Gate 1), or if the owner explicitly rules that
deterministic reconstruction plus contemporaneous pins satisfy the provenance
standard. Neither is within this order's authority.

## 16. Hard stop

Per the order §22–§23: no M3 execution, no provider call, no qualification, no case
execution, no population registration, no manuscript update, no automatic next phase.
Even an authoritative population (not reached here) would not start M3 under this
order.
