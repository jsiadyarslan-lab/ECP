"""M3-ELR registration package contract — ECP-PKG-M3-ELR-V1.

Reconstructed 2026-09-13 (custody event D-01 #7 destroyed the original
commit c49b18f before delivery; see docs/M3-ELR-READINESS-RECONSTRUCTION.md).
The reconstruction is pre-execution and outcome-blind: zero model calls and
zero outcomes existed project-wide at reconstruction time. Case material is
byte-exact re-derived (CA0v1 pins verified); the machinery is re-implemented
to the documented contracts; the re-frozen package carries a NEW package
hash with the historical hash preserved in the reconstruction disclosure.

Contract surface (pinned by scripts/build_m3_elr_registration.py):

* :data:`POPULATION_ID` / :data:`CASE_PACK_ID` — the CA0v1 qualified pool.
* :data:`TARGET_MODEL_IDENTIFIER` — the pinned external model identity
  (never the ``openrouter/free`` moving alias).
* :func:`load_candidate` — load + hash-verify one private-area candidate.
* :func:`intake_verify_candidates` — the order §5 intake battery: re-runs
  the qualification engine's own ``verify_ground_truth`` + symbol coverage
  + value agreement; any fatal issue => CASE INVALID — refuse to register.
* :func:`build_package` — assemble the frozen registration package
  (two-component POP 30+18, identity-mapped families, F-01b stratified
  ordering, pinned target, MODEL-ENABLED L1 condition, charter endpoints,
  frozen missing-data rules, disclosures).
* :func:`verify_package` — full independent re-derivation (hashes, strata,
  ordering, distributions, target/condition constants, lock fields).
* :func:`stratified_ordering` — F-01b: family x depth strata
  (family and depth both sorted by name), within-stratum candidate_id
  ascending, round-robin interleave; pure function of registered metadata.

NO model call, NO provider call, NO scoring, NO scientific execution.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .canonical import load_json
from .hashing import hash_document
from .logical_classifier import answer_space_of
from .qualification import (
    _symbol_coverage_issues,
    _value_agrees,
    verify_ground_truth,
)

# ---------------------------------------------------------------------------
# Registered identities (frozen)
# ---------------------------------------------------------------------------

POPULATION_ID = "ECP-POP-M3-CA0V1-V1"
CASE_PACK_ID = "ECP-CASEPACK-M3-CA0V1"
CASE_PACK_VERSION = 1
PACKAGE_ID = "ECP-PKG-M3-ELR-V1"
PACKAGE_VERSION = 1
DISCOVERY_RECORD_ID = "M3-ELR-TARGET-DISCOVERY-V1"
EVALUATION_ID = "ECP-EVAL-M3-ELR-1"
SYSTEM_ID = "ECP-SYSTEM-M3-ELR-001"
CONDITION_ID = "ECP-COND-M3-ELR-1"
PROVIDER_ID = "ECP-PROVIDER-OPENROUTER"
ADAPTER_ID = "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS"
ADAPTER_VERSION = "1.0.0"
RUNTIME_IDENTITY = "ECP-RUNTIME-LOCAL-GATEWAY-1"
TARGET_MODEL_IDENTIFIER = "inclusionai/ling-3.0-flash-sante:free"
CREDENTIAL_REF = "ECP-M3-ELR-CREDENTIAL-OPENROUTER"
CLASSIFIER_ID = "M3-ELR-LOGICAL-CLASSIFIER-1"

#: Historical hash of the LOST original package (custody event D-01 #7):
#: permanently historical — verification against it is impossible by
#: construction; recorded for provenance only.
HISTORICAL_PACKAGE_HASH = (
    "a6e560930c8014122709a30e74b6e9c334f6069f2552290cd9d4307c54613191"
)

#: Owner rulings cited verbatim (ECP-OWNDEC-000006, file sha256 verified).
OWNER_RULINGS = {
    "register_id": "ECP-OWNDEC-000006",
    "file_sha256": "5d7a518c42a4059feb356de27d4390843feda94342e377217ce473752fa2d2e5",
    "register_hash_prefix": "9ea325d1aa0241fd",
    "rulings": {
        "O-01": "O-01-C",
        "O-02": "AUTHORIZE",
        "O-04": "AUTHORIZED",
        "F-01a": "AUTHORIZE-NOW",
        "F-01b": "STRATIFIED",
        "POP": "30+18",
    },
}

TEST_ID_TEMPLATE = "ECP-TEST-M3-ELR-{n:03d}"
CASE_ID_TEMPLATE = "ECP-CASE-M3-ELR-{n:03d}"
CANDIDATE_ID_TEMPLATE = "ECP-CAND-{n:06d}"

#: F-01b ordering rule text (frozen).
ORDERING_RULE = (
    "F-01b STRATIFIED: family x depth strata (family and depth both sorted "
    "by registered name), within-stratum candidate_id ascending, round-robin "
    "interleave across the strata; a pure function of registered metadata; "
    "deterministic and bit-reproducible; never derived from model "
    "performance, reputation, observed responses, or prior runs"
)

#: Frozen missing-data / execution rules (charter §8.5–§8.7 + owner order §11).
MISSING_DATA_RULES = {
    "missing_bundle_element": "counts as a protocol failure for that unit (charter §8.5); no convenience exclusion",
    "invalid_execution": "remains in the denominator as a classified outcome (charter §8.6), never dropped",
    "inconclusive": "legitimate separately reported outcome class (charter §8.7), distinct from INVALID and from missing data",
    "execution_attempts": "ONE attempt per registered test; no retries (the registered retry policy is NONE)",
    "fabrication": "forbidden: a provider timeout/error/malformed response is never converted into a logical answer",
    "silent_retry": "forbidden: any retry would violate the frozen execution contract",
}


# ---------------------------------------------------------------------------
# Candidate loading + verification
# ---------------------------------------------------------------------------

def load_candidate(path: "str | Path") -> dict:
    """Load one private-area candidate JSON and verify its content hash."""
    candidate = load_json(Path(path))
    if not isinstance(candidate, dict) or "content" not in candidate:
        raise ValueError(f"{path}: not a case-candidate document")
    embedded = candidate.get("content_hash")
    derived = hash_document(candidate["content"])
    if not isinstance(embedded, str) or embedded != derived:
        raise ValueError(f"{path}: embedded content_hash does not match canonical content hash")
    return candidate


def candidate_number(candidate: Mapping[str, Any]) -> int:
    """The 1-based case number of a CA0v1 candidate (ECP-CAND-0001NN -> NN)."""
    cid = str(candidate.get("candidate_id", ""))
    if not cid.startswith("ECP-CAND-") or not cid[9:].isdigit():
        raise ValueError(f"malformed candidate_id {cid!r}")
    return int(cid[9:]) - 100


def gt_commitment(content: Mapping[str, Any]) -> str:
    """SHA-256 commitment over the canonical sealed ground-truth sub-object."""
    return hash_document({
        "ground_truth": content.get("ground_truth"),
        "intended_correct_answers": content.get("intended_correct_answers"),
        "derivations": content.get("derivations"),
    })


# ---------------------------------------------------------------------------
# §5 intake battery (re-runs the qualification engine's own checks)
# ---------------------------------------------------------------------------

def intake_verify_candidates(
    candidates: "list[dict]",
    manifest_index: Mapping[str, str],
) -> dict[str, dict]:
    """Run the order §5 intake battery over the candidate pool.

    Returns ``{candidate_id: {"issues": [...], "findings": [...],
    "gt_commitment": ...}}``. ``issues`` are FATAL (any issue => CASE
    INVALID — the builder refuses to register); ``findings`` are carried,
    non-fatal records (disclosed, never silently resolved).
    """
    results: dict[str, dict] = {}
    for candidate in candidates:
        cid = candidate["candidate_id"]
        content = candidate["content"]
        issues: "list[str]" = []
        findings: "list[str]" = []

        # structural presence (order §5 field battery, structural subset)
        for field in (
            "premises", "question", "proposed_reasoning_family", "difficulty",
            "ground_truth", "intended_correct_answers", "derivations", "formal",
        ):
            value = content.get(field)
            if value in (None, "", [], {}):
                issues.append(f"{cid}: missing/empty registered field {field}")

        # hash binding: canonical == embedded == manifest (fail-closed)
        derived = hash_document(content)
        embedded = candidate.get("content_hash")
        if embedded != derived:
            issues.append(f"{cid}: embedded content_hash mismatch")
        manifest_hash = manifest_index.get(cid)
        if manifest_hash is None:
            issues.append(f"{cid}: absent from population manifest candidate_index")
        elif manifest_hash != derived:
            issues.append(f"{cid}: manifest candidate_index hash mismatch")

        # engine re-run: mechanical ground-truth verification (Q3 core)
        authored_class = (content.get("ground_truth") or {}).get("class")
        verification = verify_ground_truth(content.get("formal") or {})
        derived_class = verification.get("derived_class")
        if derived_class is None:
            findings.append(
                f"{cid}: {verification.get('status_note')} (engine {verification.get('method')})"
            )
        elif derived_class != authored_class:
            issues.append(
                f"{cid}: authored ground-truth class {authored_class!r} does not match "
                f"mechanically derived class {derived_class!r} ({verification.get('method')})"
            )
        else:
            derived_value = verification.get("value")
            if derived_value is not None:
                agrees = _value_agrees(derived_value, candidate)
                if agrees is False:
                    issues.append(
                        f"{cid}: derived value {derived_value!r} does not appear in the "
                        "authored answer/statement"
                    )
            if derived_class == "INDETERMINATE" and (content.get("ground_truth") or {}).get("ambiguity_note"):
                findings.append(
                    f"{cid}: designed indeterminacy recorded and mechanically verified "
                    f"({content['ground_truth']['ambiguity_note']})"
                )

        # engine re-run: symbol coverage (correspondence, carried findings)
        for note in _symbol_coverage_issues(candidate):
            findings.append(f"{cid}: {note}")

        results[cid] = {
            "issues": issues,
            "findings": findings,
            "gt_commitment": gt_commitment(content),
        }
    return results


# ---------------------------------------------------------------------------
# F-01b stratified ordering (pure function of registered metadata)
# ---------------------------------------------------------------------------

def stratified_ordering(candidates: "list[dict]") -> dict:
    """F-01b STRATIFIED ordering over the registered cases.

    Strata = (family, depth) for family in sorted(families) and depth in
    sorted(depths) — both sorted by REGISTERED NAME — keeping only non-empty
    strata; within each stratum candidates are ordered by candidate_id
    ascending; the output interleaves the strata round-robin.
    """
    entries = [
        (candidate_number(c), c["content"]["proposed_reasoning_family"], c["content"]["difficulty"])
        for c in candidates
    ]
    families = sorted({f for _, f, _ in entries})
    depths = sorted({d for _, _, d in entries})
    groups: "dict[tuple[str, str], list[int]]" = {}
    for number, family, depth in entries:
        groups.setdefault((family, depth), []).append(number)
    for members in groups.values():
        members.sort()
    strata = [
        {
            "reasoning_family": family,
            "reasoning_depth": depth,
            "case_numbers": list(groups[(family, depth)]),
        }
        for family in families
        for depth in depths
        if (family, depth) in groups
    ]
    # round-robin interleave over working copies (strata stay intact)
    pools = {key: list(members) for key, members in groups.items()}
    ordered: "list[int]" = []
    active = [(s["reasoning_family"], s["reasoning_depth"]) for s in strata]
    while active:
        for key in list(active):
            ordered.append(pools[key].pop(0))
            if not pools[key]:
                active.remove(key)
    return {"strata": strata, "ordered_case_numbers": ordered}


# ---------------------------------------------------------------------------
# Package assembly
# ---------------------------------------------------------------------------

def _case_entry(candidate: Mapping[str, Any], commitment: str) -> dict:
    content = candidate["content"]
    return {
        "case_id": CASE_ID_TEMPLATE.format(n=candidate_number(candidate)),
        "test_id": TEST_ID_TEMPLATE.format(n=candidate_number(candidate)),
        "candidate_id": candidate["candidate_id"],
        "population_id": POPULATION_ID,
        "case_pack_id": CASE_PACK_ID,
        "case_pack_version": CASE_PACK_VERSION,
        "content_hash": candidate["content_hash"],
        "reasoning_family": content["proposed_reasoning_family"],
        "reasoning_depth": content["difficulty"],
        "answer_space": answer_space_of(content["question"]),
        "gt_commitment": commitment,
    }


def _distribution(cases: "list[dict]", key: str) -> "dict[str, int]":
    dist: "dict[str, int]" = {}
    for case in cases:
        dist[case[key]] = dist.get(case[key], 0) + 1
    return dict(sorted(dist.items()))


def build_package(
    *,
    candidates: "list[dict]",
    manifest_index: Mapping[str, str],
    registered_at: str,
    intake: Mapping[str, Mapping[str, Any]],
) -> dict:
    """Assemble the M3-ELR registration package (hash computed last)."""
    case_entries = [
        _case_entry(c, intake[c["candidate_id"]]["gt_commitment"])
        for c in sorted(candidates, key=candidate_number)
    ]
    ordering = stratified_ordering(candidates)
    ternary_keys = {"YES": 0, "NO": 0, "CANNOT-DETERMINE": 0}
    for candidate in candidates:
        from .logical_classifier import answer_space_of, expected_answer_key
        if answer_space_of(candidate["content"].get("question", "")) != "TERNARY":
            continue
        key = expected_answer_key(candidate["content"])
        if key in ternary_keys:
            ternary_keys[key] += 1
    findings_total = sum(len(v.get("findings", [])) for v in intake.values())
    fatal_total = sum(1 for v in intake.values() if v.get("issues"))

    package = {
        "ecp_object": "m3-registration-package",
        "package_id": PACKAGE_ID,
        "package_version": PACKAGE_VERSION,
        "content_class": "registration",
        "protocol_version": "0.7.0",
        "schema_version": "0.8.0",
        "registered_at": registered_at,
        "order_reference": {
            "title": "M3 REAL EXTERNAL LOGICAL REASONING EVALUATION — READINESS, TARGET BINDING & REGISTRATION v1",
            "repository": "jsiadyarslan-lab/ECP",
            "branch": "main",
        },
        "evaluation": {
            "evaluation_id": EVALUATION_ID,
            "case_count": len(case_entries),
            "test_ids": [c["test_id"] for c in case_entries],
            "case_ids": [c["case_id"] for c in case_entries],
            "classifier": CLASSIFIER_ID,
        },
        "population": {
            "representation": "TWO-COMPONENT (owner ruling POP = 30+18, ECP-OWNDEC-000006)",
            "component_1": {
                "source": POPULATION_ID,
                "case_pack_id": CASE_PACK_ID,
                "case_pack_version": CASE_PACK_VERSION,
                "registered_count": len(case_entries),
                "status": "REGISTERED",
            },
            "component_2": {
                "source": "prior 20-candidate pool surviving candidates (readiness-engine refusal intact)",
                "candidate_count": 18,
                "registered_count": 0,
                "status": "PENDING-REAUTHORIZATION (requires its own owner order)",
            },
            "never_merged_into": "a single undifferentiated 48-case campaign",
            "counts": {
                "prior_pool": 20,
                "component_2_surviving": 18,
                "component_2_registered": 0,
                "component_2_executed": 0,
            },
        },
        "cases": case_entries,
        "family_distribution": _distribution(case_entries, "reasoning_family"),
        "family_reconciliation": {
            "rule": "identity-mapped: existing CA0v1 family names are registered as-is; no silent renames",
            "order_example_correspondences_asserted": False,
        },
        "reasoning_depth": {
            "distribution": _distribution(case_entries, "reasoning_depth"),
            "rule": "registered case property, authored and qualification-verified; never inferred from answer length; never changed after observing results",
        },
        "answer_space_distribution": _distribution(case_entries, "answer_space"),
        "answer_space_metadata": {
            "ternary_key_distribution": dict(sorted(ternary_keys.items())),
            "note": "aggregate public metadata; per-case keys are sealed ground truth carried only as gt_commitment (SHA-256 over canonical {ground_truth, intended_correct_answers, derivations})",
        },
        "ordering": {
            "rule": ORDERING_RULE,
            "strata": ordering["strata"],
            "strata_count": len(ordering["strata"]),
        },
        "ordered_test_ids": [
            TEST_ID_TEMPLATE.format(n=n) for n in ordering["ordered_case_numbers"]
        ],
        "target": {
            "system_id": SYSTEM_ID,
            "system_type": "model-only",
            "official_name": "InclusionAI Ling 3.0 Flash (Sante edition) served via OpenRouter",
            "provider": PROVIDER_ID,
            "provider_organization": "OpenRouter",
            "model_identifier": TARGET_MODEL_IDENTIFIER,
            "exact_model_api_identifier": TARGET_MODEL_IDENTIFIER,
            "api_interface": "openrouter-chat-completions-api (POST /api/v1/chat/completions, OpenAI-compatible dialect)",
            "adapter_id": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            "runtime_identity": RUNTIME_IDENTITY,
            "independence_classification": "EXTERNAL-INDEPENDENT",
            "credential_ref": CREDENTIAL_REF,
            "pinned_by_exact_identifier": True,
            "model_identity_rule": "the openrouter/free moving alias is NEVER a scientific model identity; the exact identifier is pinned and frozen",
            "conformance_evidence": "ECP-EXEC-CONSOLE-6f73b46447ab4f4da9f1bb2e68f4b2d6 (real external OpenRouter round trip, 2026-09-12): CONFORMANCE ONLY — never a scientific result, never relabeled",
            "independence_basis": [
                "system lineage: InclusionAI Ling 3.0 Flash served via OpenRouter — outside ECP/JARVIS lineage",
                "case selection: performed by qualification/registration only, no target-side participation",
                "evaluation ownership: ECP-side, protocol-controlled",
                "information access: the target receives only the registered case presentation",
                "ground-truth access: none — sealed GT lives in the private qualification area, absent from the execution environment",
                "benchmark access: none — no retrieval, no tools, no network beyond the single chat-completions endpoint",
                "execution control: the ECP local gateway enforces the registered intent contract and frozen adapter configuration",
                "no author-model overlap: InclusionAI Ling is outside the GLM family that authored the CA0v1 pool (O-03 consequence recorded)",
            ],
        },
        "condition": {
            "condition_id": CONDITION_ID,
            "model_state": "MODEL-ENABLED",
            "level": "L1 model-only",
            "system_prompt": "NONE",
            "tools": "NONE",
            "retrieval": "NONE",
            "external_context_injection": "NONE",
            "temperature": 0.0,
            "max_tokens": 1024,
            "transport_timeout_seconds": 30,
            "provider_nondeterminism": "disclosed: provider-side sampling nondeterminism may persist at temperature 0.0; recorded per execution",
            "prompt_authority": "RegisteredCaseArtifact is the sole prompt authority; the model input is exactly the registered case presentation (which embeds the authored answer-format instruction)",
        },
        "endpoints": {
            "primary": {
                "name": "ECCE (Evidence-Complete Classified Execution rate)",
                "definition": "charter §8.1: among all attempted System x Case x repetition units in a preregistered stage, the fraction producing a complete minimum evidence bundle, a valid identity record, and an unambiguous mechanically derived outcome classification",
            },
            "secondary": {
                "label": "exploratory-labeled, never promoted post-hoc (charter §8.2)",
                "definition": "audit agreement; independent-verification success; evidence-bundle completeness; invalid-execution and inconclusive rates; between-repetition classification agreement; protocol-waiver count",
            },
            "descriptive": "model performance (success rates) is reported only as descriptive stratum- and family-level summaries (charter §8.2); it is never an endpoint of M3",
            "missing_data": MISSING_DATA_RULES,
        },
        "execution_contract": {
            "execution_surface": "python run_m3_elr_console.py",
            "attempts_per_test": 1,
            "retry_policy": "NONE (a retry would violate the frozen execution contract)",
            "case_order": "the frozen F-01b ordered_test_ids sequence, unmodified",
            "missing_data": MISSING_DATA_RULES,
            "credential": "OPENROUTER_API_KEY resolved at launch through the authorized credential gateway only; never in Git, records, source, evidence, or logs",
        },
        "owner_rulings": dict(OWNER_RULINGS),
        "intake_battery": {
            "candidates_verified": len(candidates),
            "fatal_issues": fatal_total,
            "carried_findings": findings_total,
            "method": "re-run of the qualification engine's own verify_ground_truth + symbol coverage + value agreement over the live recovered candidate artifacts",
        },
        "disclosures": [
            {
                "id": "O-01-C",
                "state": "OPEN / ABSENT",
                "text": "the novelty-evidence mechanism does not exist; in-repo mechanical screens are context, not external novelty evidence; no novelty claim is manufactured",
            },
            {
                "id": "O-03",
                "state": "RECORDED",
                "text": "CA0v1 author-model overlap (GLM family); the admitted target is non-GLM; glm-4-plus requires an owner disposition before admission",
            },
            {
                "id": "QUALIFICATION-PROVENANCE",
                "state": "PARTIALLY VERIFIED",
                "text": "artifact layer absent from durable custody; content layer byte-verified; five-gate BLOCKED record carried verbatim; registration proceeds under the owner's explicit directive",
            },
            {
                "id": "SRE-V1-RELATIONSHIP",
                "state": "SEPARATE",
                "text": "SRE-v1 is a separate frozen registration (N=9 single-system); its 9-case set is a subset of the 30; never conflated; its DEME owner decision gate remains OPEN",
            },
            {
                "id": "COMPONENT-2",
                "state": "PENDING-REAUTHORIZATION",
                "text": "the 18 prior-pool surviving candidates remain pending their own re-authoring owner order; never merged into component 1",
            },
            {
                "id": "RECONSTRUCTION",
                "state": "DISCLOSED",
                "text": (
                    "this package is the 2026-09-13 reconstruction of ECP-PKG-M3-ELR-V1 after "
                    "custody event D-01 #7 destroyed the original (unpushed) commit c49b18f; the "
                    f"historical package hash {HISTORICAL_PACKAGE_HASH} is permanently historical "
                    "(no surviving artifact copy; verification against it is impossible); the case "
                    "material is byte-exact re-derived (CA0v1 source/sidecar/intake pins verified); "
                    "the machinery is re-implemented to the documented contracts; the F-01b ordering "
                    "reproduction is anchor-verified (first three registered tests "
                    "ECP-TEST-M3-ELR-006 / -008 / -015); the reconstruction is pre-execution and "
                    "outcome-blind (zero model calls, zero outcomes existed project-wide); this "
                    "package's own hash is the operative frozen registration"
                ),
            },
        ],
        "scientific_execution_lock": {
            "case_execution": "NO",
            "provider_call": "NO",
            "model_call": "NO",
            "scoring": "NO",
            "outcome_extraction": "NO",
            "statistical_analysis": "NO",
            "note": "execution requires the separate owner order (M3 — REAL EXTERNAL LOGICAL REASONING EXECUTION v1)",
        },
    }
    package["package_hash"] = hash_document(
        {k: v for k, v in package.items() if k != "package_hash"}
    )
    return package


# ---------------------------------------------------------------------------
# Independent re-derivation (verify_package)
# ---------------------------------------------------------------------------

def verify_package(
    package: Mapping[str, Any],
    *,
    candidates: "list[dict]",
    manifest_index: Mapping[str, str],
) -> "list[str]":
    """Re-derive the package end-to-end; empty list = clean."""
    failures: "list[str]" = []
    if package.get("package_id") != PACKAGE_ID:
        failures.append(f"package_id: expected {PACKAGE_ID!r}")
    claimed = package.get("package_hash")
    recomputed = hash_document({k: v for k, v in package.items() if k != "package_hash"})
    if claimed != recomputed:
        failures.append("package_hash: embedded hash does not match canonical re-derivation")

    by_number = {candidate_number(c): c for c in candidates}
    if len(by_number) != len(candidates):
        failures.append("candidates: duplicate case numbers")
    case_entries = package.get("cases") or []
    if len(case_entries) != len(candidates):
        failures.append(f"cases: count {len(case_entries)} != candidate count {len(candidates)}")

    seen_numbers: set[int] = set()
    for entry in case_entries:
        number = int(str(entry["test_id"]).rsplit("-", 1)[-1])
        if number in seen_numbers:
            failures.append(f"cases: duplicate case number {number}")
        seen_numbers.add(number)
        candidate = by_number.get(number)
        if candidate is None:
            failures.append(f"cases: no candidate for case number {number}")
            continue
        content = candidate["content"]
        if entry["content_hash"] != candidate["content_hash"]:
            failures.append(f"case {number}: content_hash mismatch vs live candidate")
        if entry["content_hash"] != manifest_index.get(candidate["candidate_id"]):
            failures.append(f"case {number}: content_hash mismatch vs manifest candidate_index")
        if entry["reasoning_family"] != content["proposed_reasoning_family"]:
            failures.append(f"case {number}: reasoning_family mismatch")
        if entry["reasoning_depth"] != content["difficulty"]:
            failures.append(f"case {number}: reasoning_depth mismatch")
        if entry["answer_space"] != answer_space_of(content["question"]):
            failures.append(f"case {number}: answer_space mismatch")
        if entry["gt_commitment"] != gt_commitment(content):
            failures.append(f"case {number}: gt_commitment mismatch")
        if entry["case_id"] != CASE_ID_TEMPLATE.format(n=number):
            failures.append(f"case {number}: case_id template mismatch")
        if entry["test_id"] != TEST_ID_TEMPLATE.format(n=number):
            failures.append(f"case {number}: test_id template mismatch")

    if _distribution(case_entries, "reasoning_family") != package.get("family_distribution"):
        failures.append("family_distribution: mismatch vs re-derivation")
    if _distribution(case_entries, "reasoning_depth") != package.get("reasoning_depth", {}).get("distribution"):
        failures.append("reasoning_depth.distribution: mismatch vs re-derivation")
    if _distribution(case_entries, "answer_space") != package.get("answer_space_distribution"):
        failures.append("answer_space_distribution: mismatch vs re-derivation")

    ordering = stratified_ordering(candidates)
    if [TEST_ID_TEMPLATE.format(n=n) for n in ordering["ordered_case_numbers"]] != package.get("ordered_test_ids"):
        failures.append("ordered_test_ids: F-01b ordering mismatch vs re-derivation")
    if package.get("ordering", {}).get("strata_count") != len(ordering["strata"]):
        failures.append("ordering.strata_count: mismatch vs re-derivation")
    if package.get("ordering", {}).get("strata") != ordering["strata"]:
        failures.append("ordering.strata: mismatch vs re-derivation")

    target = package.get("target") or {}
    if target.get("model_identifier") != TARGET_MODEL_IDENTIFIER:
        failures.append("target.model_identifier: not the pinned exact identifier")
    if target.get("system_id") != SYSTEM_ID or target.get("provider") != PROVIDER_ID:
        failures.append("target: system/provider identity mismatch")
    if target.get("adapter_id") != ADAPTER_ID or target.get("adapter_version") != ADAPTER_VERSION:
        failures.append("target: adapter identity/version mismatch")

    condition = package.get("condition") or {}
    if condition.get("condition_id") != CONDITION_ID or condition.get("model_state") != "MODEL-ENABLED":
        failures.append("condition: identity/model_state mismatch")
    if condition.get("temperature") != 0.0 or condition.get("max_tokens") != 1024:
        failures.append("condition: frozen sampling policy mismatch")
    if condition.get("transport_timeout_seconds") != 30:
        failures.append("condition: transport timeout mismatch")

    population = package.get("population") or {}
    if population.get("representation", "").startswith("TWO-COMPONENT") is False:
        failures.append("population: representation is not TWO-COMPONENT")
    if population.get("component_2", {}).get("registered_count") != 0:
        failures.append("population: component 2 must register zero cases in this package")

    if package.get("evaluation", {}).get("evaluation_id") != EVALUATION_ID:
        failures.append("evaluation: evaluation_id mismatch")
    if package.get("evaluation", {}).get("case_count") != len(case_entries):
        failures.append("evaluation: case_count mismatch")

    lock = package.get("scientific_execution_lock") or {}
    for field in ("case_execution", "provider_call", "model_call", "scoring", "outcome_extraction", "statistical_analysis"):
        if lock.get(field) != "NO":
            failures.append(f"scientific_execution_lock.{field}: must be NO")

    rulings = (package.get("owner_rulings") or {}).get("rulings") or {}
    if rulings != OWNER_RULINGS["rulings"]:
        failures.append("owner_rulings: ruling values do not match ECP-OWNDEC-000006 verbatim")
    return failures


__all__ = [
    "ADAPTER_ID",
    "ADAPTER_VERSION",
    "CASE_ID_TEMPLATE",
    "CASE_PACK_ID",
    "CASE_PACK_VERSION",
    "CLASSIFIER_ID",
    "CONDITION_ID",
    "CREDENTIAL_REF",
    "DISCOVERY_RECORD_ID",
    "EVALUATION_ID",
    "HISTORICAL_PACKAGE_HASH",
    "MISSING_DATA_RULES",
    "ORDERING_RULE",
    "OWNER_RULINGS",
    "PACKAGE_ID",
    "PACKAGE_VERSION",
    "POPULATION_ID",
    "PROVIDER_ID",
    "RUNTIME_IDENTITY",
    "SYSTEM_ID",
    "TARGET_MODEL_IDENTIFIER",
    "TEST_ID_TEMPLATE",
    "build_package",
    "candidate_number",
    "gt_commitment",
    "intake_verify_candidates",
    "load_candidate",
    "stratified_ordering",
    "verify_package",
]
