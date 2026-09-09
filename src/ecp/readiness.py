"""ECP registration-readiness & owner-adjudication layer (M3-CA1 v1, 0.6.0).

This module implements the registration-readiness assessment ordered by
M3-CA1 v1:

- a **15-point per-case mechanical check battery** (order §7) executed over the
  preserved qualification artifacts of a qualified pool — schema/contract
  validity, qualification decision, content-hash binding, authoring-provenance
  completeness, explicit independence status, mechanical ground-truth
  verification and class consistency, artifact chain integrity, N3/N4/N5/N6
  novelty statuses, the six-class leakage pre-screen, and the §9/§10
  disclosures;
- an **owner-decision-register evaluation** (order §4–§6): the O-01..O-04
  items are validated for explicitness (implicit defaults are a loud error),
  evidence-classified where the order demands it (§5: SUPPORTED / UNRESOLVED /
  INSUFFICIENT-EVIDENCE — never inferred into NOVEL), and reduced to a
  blocking determination for registration;
- a **population-decision evaluation** (order §8): the explicit 30-only /
  18-only / 30+18 / other decision with mechanical re-derivation of the
  cross-population facts (duplication, overlap, prior-pool contract facts) and
  a hard refusal to register material that never passed qualification;
- a **set-class designation validation** (order §10): per-case
  PUBLIC/PROTECTED/HIDDEN/ROTATING with pre-execution publication forbidden,
  HIDDEN/ROTATING requiring a set-binding reference, PROTECTED the default
  evaluation-candidate class;
- a **registration-authorization gate** (order §11/§12): the manifest can be
  built ONLY when every owner item that blocks registration is resolved, every
  finding requiring an owner ruling is ruled, every case in scope is REGISTER,
  and the population decision is explicit. Otherwise the gate REFUSES —
  loudly, never silently.

Like every ECP engine this module is deterministic (a pure function of its
inputs), integrity-only in verification, and contains NO model adapters, NO
execution machinery, NO scoring. It does not write to the registration ledger;
the ledger ceremony remains the separate, full-contract instrument.

Decision semantics (order §7 + §14):

- REGISTER  — all 15 checks pass AND nothing blocks the case (no unresolved
  blocking owner item, no unresolved owner-ruling finding, valid set class,
  in the explicit population scope). The case is immediately registrable.
- HOLD      — all 15 checks pass but a blocking owner item or unresolved
  owner-ruling finding binds the case. Registration-ready in every mechanical
  dimension; held ONLY on owner adjudication.
- REVISE    — a revise-class mechanical check failed (provenance/disclosure
  completeness): the candidate needs re-authoring before it can register.
- REJECT    — a reject-class mechanical check failed (contract, identity,
  ground-truth, chain, novelty or leakage defect), or the set-class
  designation is forbidden (e.g. PUBLIC pre-execution).

Precedence: REJECT > REVISE > HOLD > REGISTER.
"""

from __future__ import annotations

import re

from .canonical import canonical_bytes  # noqa: F401  (re-exported convenience)
from .candidates import normalize_tokens
from .hashing import hash_document, hash_document_excluding
from .qualification import _jaccard
from .validate import validate_document
from .versions import version_issues

# ---------------------------------------------------------------------------
# Engine identity and frozen vocabularies
# ---------------------------------------------------------------------------

ENGINE_ID = "ECP-READINESS-ENGINE-1"
ENGINE_VERSION = "0.6.0"
ENGINE_PROFILES = ("0.6.0",)

READINESS_STATES = ("REGISTER", "HOLD", "REVISE", "REJECT")

#: The 15 per-case registration-readiness checks (order §7), frozen.
#: (code, key, description, failure_class)
REGISTRATION_READINESS_CHECKS = (
    ("C-01", "candidate-contract", "candidate cites the case-candidate contract with accepted versions", "REJECT"),
    ("C-02", "qualification-decision", "qualification artifact contract valid and decision ACCEPT (recorded findings carried)", "REJECT"),
    ("C-03", "content-hash-binding", "candidate == artifact == run entry content-hash identity", "REJECT"),
    ("C-04", "provenance-completeness", "section-3 authoring-independence record complete (13 fields)", "REVISE"),
    ("C-05", "independence-explicitness", "explicit non-bare independence status with declared limitations", "REVISE"),
    ("C-06", "ground-truth-mechanical", "Q3 mechanical ground-truth verification PASS", "REJECT"),
    ("C-07", "ground-truth-class-consistency", "authored ground-truth class equals mechanically derived class", "REJECT"),
    ("C-08", "artifact-chain-integrity", "qualification artifact hash recomputes and chain link holds", "REJECT"),
    ("C-09", "novelty-within-pool", "N3 renaming-invariant structural skeleton UNIQUE in pool", "REJECT"),
    ("C-10", "novelty-cross-population", "N4 cross-population overlap CLEAR against the prior pool", "REJECT"),
    ("C-11", "novelty-implementation-encoding", "N5 implementation-encoding CLEAR", "REJECT"),
    ("C-12", "novelty-fixture-leakage", "N6 fixture-leakage CLEAR", "REJECT"),
    ("C-13", "leakage-pre-screen", "six-class leakage pre-screen CLEAR (model class N.A. pre-execution)", "REJECT"),
    ("C-14", "disclosure-representation-bias", "section-9 representation-bias disclosure present (record + dimension)", "REVISE"),
    ("C-15", "disclosure-environmental-precheck", "section-10 environmental pre-check present (record + dimension)", "REVISE"),
)

CHECK_KEYS = tuple(key for _code, key, _desc, _cls in REGISTRATION_READINESS_CHECKS)
REJECT_CHECKS = frozenset(key for _code, key, _desc, cls in REGISTRATION_READINESS_CHECKS if cls == "REJECT")
REVISE_CHECKS = frozenset(key for _code, key, _desc, cls in REGISTRATION_READINESS_CHECKS if cls == "REVISE")

#: Set classes (order §10; G0 architecture doc section 3 table).
SET_CLASSES = ("PUBLIC", "PROTECTED", "HIDDEN", "ROTATING")

#: Population decisions (order §8).
POPULATION_DECISIONS = ("30-ONLY", "18-ONLY", "30+18", "OTHER-EXPLICIT")

#: Owner-decision-item states (order §4/§6: explicit, never implicit).
OWNER_ITEM_STATES = ("RESOLVED", "REMAINS-OPEN")

#: O-01 evidence classes (order §5).
O01_EVIDENCE_CLASSES = ("SUPPORTED", "UNRESOLVED", "INSUFFICIENT-EVIDENCE")

#: Cross-population text-overlap suspicion threshold (inherited from the
#: qualification engine's N4 parameter — same value, same semantics).
CROSS_POP_JACCARD_THRESHOLD = 0.5

#: Required authoring-independence record fields (section 3, M3-CA0 v1).
INDEPENDENCE_FIELDS = (
    "author_identity",
    "authoring_environment",
    "model_tool",
    "model_version",
    "prompt_instructions",
    "information_available",
    "information_unavailable",
    "relationship_to_ecp_developers",
    "relationship_to_evaluated_systems",
    "access_to_prior_ecp_results",
    "independence_status",
    "validation_procedure",
    "independence_limitations",
)

#: Section-9 disclosure fields.
RB_FIELDS = ("status", "evidence", "known_limitation")

#: Section-10 environmental pre-check fields.
ENV_FIELDS = (
    "knowledge_sources",
    "fixtures",
    "implementation_artifacts",
    "memory_paths",
    "model_access_paths",
    "answer_bearing_artifacts",
)

OWNER_ITEM_IDS = ("O-01", "O-02", "O-03", "O-04")


class ReadinessError(Exception):
    """Base class for readiness-layer errors (always loud)."""


class InvalidReadinessState(ReadinessError):
    """Raised when an input document violates the frozen readiness contract.

    Input errors are LOUD: the engine never silently repairs, defaults or
    drops a malformed input (order §4: implicit defaults are forbidden).
    """


class RegistrationManifestRefused(ReadinessError):
    """Raised when the manifest builder is invoked while the gate REFUSES."""


# ---------------------------------------------------------------------------
# Input validation (loud)
# ---------------------------------------------------------------------------

def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidReadinessState(message)


def _as_hex64(value) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def validate_decision_register(register: dict) -> "list[str]":
    """Structural issues for an owner-decision-register document.

    Returns an issue list (integrity-only validation used by verify paths);
    :func:`_require`-style hard validation happens inside the run.
    """
    issues: "list[str]" = []
    if not isinstance(register, dict):
        return ["<root>: expected a JSON object"]
    if register.get("ecp_object") != "owner-decision-register":
        issues.append("ecp_object: expected 'owner-decision-register'")
    rid = register.get("register_id", "")
    if not isinstance(rid, str) or not re.fullmatch(r"ECP-OWNDEC-[A-Za-z0-9][A-Za-z0-9._:-]*", rid):
        issues.append("register_id: expected an ECP-OWNDEC-… identifier")
    items = register.get("items", [])
    if not isinstance(items, list) or len(items) != len(OWNER_ITEM_IDS):
        issues.append(f"items: expected exactly the {len(OWNER_ITEM_IDS)} carried items {OWNER_ITEM_IDS}")
    else:
        seen = [item.get("item_id") for item in items if isinstance(item, dict)]
        if tuple(seen) != OWNER_ITEM_IDS:
            issues.append(f"items: expected ids in order {OWNER_ITEM_IDS}, got {seen}")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            issues.append("items: expected objects")
            continue
        iid = item.get("item_id", "?")
        if item.get("state") not in OWNER_ITEM_STATES:
            issues.append(f"{iid}: state must be one of {OWNER_ITEM_STATES} (implicit defaults forbidden)")
        if item.get("state") == "RESOLVED":
            if not item.get("ruling"):
                issues.append(f"{iid}: state RESOLVED requires an explicit ruling")
            if not item.get("ruling_basis"):
                issues.append(f"{iid}: state RESOLVED requires a ruling_basis")
        if iid == "O-01":
            if item.get("evidence_classification") not in O01_EVIDENCE_CLASSES:
                issues.append(f"{iid}: evidence_classification must be one of {O01_EVIDENCE_CLASSES}")
        if item.get("blocking_for_registration") and not item.get("blocking_basis"):
            issues.append(f"{iid}: blocking_for_registration=true requires a blocking_basis")
        options = item.get("options", [])
        if not isinstance(options, list) or len(options) < 2:
            issues.append(f"{iid}: options: at least two permitted rulings required")
    register_hash = register.get("register_hash")
    if not _as_hex64(register_hash):
        issues.append("register_hash: not a sha256 hex string")
    else:
        recomputed = hash_document_excluding(register, "register_hash")
        if recomputed != register_hash:
            issues.append("register_hash: recomputation mismatch (tampering or corruption)")
    return issues


def evaluate_decision_register(register: dict) -> dict:
    """Validate (loudly) and reduce the register to blocking determinations.

    Returns ``{blocking_items, unresolved_findings, summary}`` where
    ``blocking_items`` is a list of ``{item_id, reason}`` for every item that
    is REMAINS-OPEN and blocking-for-registration, and ``unresolved_findings``
    lists findings that require an owner ruling and do not yet carry one.
    """
    _require(isinstance(register, dict), "decision register: expected a JSON object")
    _require(register.get("ecp_object") == "owner-decision-register",
             "decision register: ecp_object must be 'owner-decision-register'")
    issues = validate_decision_register(register)
    _require(not issues, "decision register violates the frozen contract:\n  - " + "\n  - ".join(issues))

    blocking_items: "list[dict]" = []
    item_states: "dict[str, str]" = {}
    for item in register["items"]:
        iid = item["item_id"]
        item_states[iid] = item["state"]
        if item["state"] == "REMAINS-OPEN" and item.get("blocking_for_registration"):
            blocking_items.append({
                "item_id": iid,
                "reason": item.get("blocking_basis", "unresolved and blocking"),
            })

    unresolved_findings: "list[dict]" = []
    for finding in register.get("findings", []) or []:
        if finding.get("requires_owner_ruling") and not finding.get("ruling"):
            unresolved_findings.append({
                "finding_id": finding.get("finding_id", "?"),
                "reason": finding.get("description", "requires owner ruling"),
            })

    return {
        "blocking_items": blocking_items,
        "unresolved_findings": unresolved_findings,
        "item_states": item_states,
    }


def validate_population_decision(decision: dict, candidates: "list[dict]", prior_candidates: "list[dict]") -> dict:
    """Loud validation + mechanical re-derivation of the population decision.

    Returns the evaluated population block recorded in the run manifest. The
    engine REFUSES (loudly) any decision that would put never-qualified
    material in registration scope: prior-pool candidates lack the 0.5.0
    registration prerequisites (formal layer, ground-truth class, authoring
    independence) — registering them would bypass the frozen pipeline.
    """
    _require(isinstance(decision, dict), "population decision: expected a JSON object")
    choice = decision.get("decision")
    _require(choice in POPULATION_DECISIONS,
             f"population decision: must be one of {POPULATION_DECISIONS} (explicit, order §8)")
    _require(isinstance(decision.get("rationale"), str) and decision.get("rationale"),
             "population decision: rationale is required (no silent choices)")

    qualified_ids = [c.get("candidate_id") for c in candidates]

    # --- prior-pool contract facts (mechanical, re-derived) ---
    prior_facts = _prior_pool_facts(prior_candidates)

    # --- cross-population overlap re-derivation (N4 basis) ---
    overlap = _cross_population_overlap(candidates, prior_candidates)

    scope_ids: "list[str]"
    if choice in ("18-ONLY", "30+18"):
        # Registering prior-pool pilot material would bypass the frozen pipeline
        # (candidates enter through intake -> review -> qualification). The
        # engine refuses loudly unless the prior material satisfies the 0.5.0
        # registration prerequisites (a future re-authored pool would arrive as
        # new, separately qualified candidate versions — never retroactively).
        unqualified = max(
            prior_facts["without_formal"],
            prior_facts["without_gt_class"],
            prior_facts["without_independence"],
        )
        if prior_facts["count"] and unqualified:
            raise InvalidReadinessState(
                "population decision REFUSED: registering prior-pool pilot material would bypass "
                "the frozen pipeline (candidates enter through intake -> review -> qualification; "
                f"the prior format-1 pool never passed qualification): {prior_facts['count']} prior "
                f"candidates, {prior_facts['without_formal']} without a formal layer, "
                f"{prior_facts['without_gt_class']} without a ground-truth class, "
                f"{prior_facts['without_independence']} without an authoring-independence record. "
                "Any future registration use of that material requires re-authoring into the "
                "current candidate format under a separate owner order (new candidate versions "
                "with their own provenance — never retroactive registration)."
            )
        scope_ids = (
            [c.get("candidate_id") for c in prior_candidates]
            if choice == "18-ONLY"
            else qualified_ids + [c.get("candidate_id") for c in prior_candidates]
        )
    elif choice == "OTHER-EXPLICIT":
        scope_ids = decision.get("explicit_scope", [])
        _require(isinstance(scope_ids, list) and scope_ids,
                 "population decision: OTHER-EXPLICIT requires a non-empty explicit_scope")
    else:  # 30-ONLY
        scope_ids = qualified_ids

    unknown = [cid for cid in scope_ids if cid not in qualified_ids]
    _require(not unknown,
             f"population decision: scope contains ids outside the qualified pool: {unknown}")

    return {
        "decision": choice,
        "rationale": decision.get("rationale"),
        "analysis_blocks": decision.get("analysis", {}),
        "scope_candidate_ids": scope_ids,
        "prior_pool_facts": prior_facts,
        "cross_population": overlap,
    }


def _prior_pool_facts(prior_candidates: "list[dict]") -> dict:
    count = len(prior_candidates)
    without_formal = 0
    without_gt_class = 0
    without_independence = 0
    protocol_versions: "set[str]" = set()
    for cand in prior_candidates:
        content = cand.get("content", {}) or {}
        if not isinstance(content.get("formal"), dict):
            without_formal += 1
        gt = content.get("ground_truth")
        if not (isinstance(gt, dict) and gt.get("class")):
            without_gt_class += 1
        if not isinstance(cand.get("authoring_independence"), dict):
            without_independence += 1
        protocol_versions.add(str(cand.get("protocol_version")))
    return {
        "count": count,
        "candidate_ids": [c.get("candidate_id") for c in prior_candidates],
        "protocol_versions": sorted(protocol_versions),
        "without_formal": without_formal,
        "without_gt_class": without_gt_class,
        "without_independence": without_independence,
        "note": "prior format-1 pilot pool (R2 area): re-derived mechanical facts",
    }


def _cross_population_overlap(candidates: "list[dict]", prior_candidates: "list[dict]") -> dict:
    """Re-derive the N4 text-overlap basis: max premise/signature Jaccard."""
    max_premise = 0.0
    max_signature = 0.0
    max_pair = None
    for cand in candidates:
        content = cand.get("content", {}) or {}
        case_tokens = normalize_tokens(" ".join(content.get("premises", [])))
        sig_tokens = normalize_tokens(content.get("structural_signature", ""))
        for prior in prior_candidates:
            pcontent = prior.get("content", {}) or {}
            prior_tokens = normalize_tokens(" ".join(pcontent.get("premises", [])))
            overlap = _jaccard(case_tokens, prior_tokens)
            sig_overlap = _jaccard(sig_tokens, normalize_tokens(pcontent.get("structural_signature", "")))
            if max(overlap, sig_overlap) > max(max_premise, max_signature):
                max_premise = max(max_premise, overlap)
                max_signature = max(max_signature, sig_overlap)
                max_pair = [cand.get("candidate_id"), prior.get("candidate_id")]
    return {
        "method": "text-normalized premise/signature Jaccard vs the prior format-1 pool (N4 basis, re-derived)",
        "threshold": CROSS_POP_JACCARD_THRESHOLD,
        "max_premise_jaccard": round(max_premise, 4),
        "max_signature_jaccard": round(max_signature, 4),
        "max_pair": max_pair,
        "status": "CLEAR" if max(max_premise, max_signature) < CROSS_POP_JACCARD_THRESHOLD else "SUSPICION",
    }


def validate_set_class_designation(designation: dict, candidates: "list[dict]", zero_executions: bool = True) -> dict:
    """Loud validation of the per-case set-class designation (order §10).

    Rules (frozen):

    - every candidate in the pool must carry exactly one class;
    - PUBLIC is FORBIDDEN for evaluation-pool material while zero executions
      exist project-wide (pre-execution publication is a leakage channel that
      would destroy the case's evaluation validity);
    - HIDDEN and ROTATING require a set-binding reference (the hidden/rotation
      split is a function of the registered-set composition and statistical
      plan — deliberately deferred, charter §8.11; an unbound designation now
      would be arbitrary);
    - PROTECTED is the preregistered-evaluation-candidate default class.
    """
    _require(isinstance(designation, dict), "set-class designation: expected a JSON object")
    assignments = designation.get("assignments", {})
    _require(isinstance(assignments, dict) and assignments,
             "set-class designation: assignments map required (per-case classification, order §10)")
    candidate_ids = [c.get("candidate_id") for c in candidates]
    missing = [cid for cid in candidate_ids if cid not in assignments]
    _require(not missing, f"set-class designation: cases without a class: {missing}")
    extra = [cid for cid in assignments if cid not in candidate_ids]
    _require(not extra, f"set-class designation: unknown candidate ids: {extra}")

    binding_ref = designation.get("set_binding_reference")
    for cid, cls in assignments.items():
        _require(cls in SET_CLASSES,
                 f"set-class designation: {cid}: class {cls!r} outside {SET_CLASSES}")
        if cls == "PUBLIC" and zero_executions:
            raise InvalidReadinessState(
                f"set-class designation REFUSED: {cid}: PUBLIC is forbidden for evaluation-pool "
                "material while zero executions exist project-wide (pre-execution publication is "
                "a leakage channel; public development-class cases are a separately authored "
                "population, never the qualified evaluation pool)"
            )
        if cls in ("HIDDEN", "ROTATING"):
            _require(isinstance(binding_ref, str) and binding_ref,
                     f"set-class designation: {cid}: HIDDEN/ROTATING require a set_binding_reference "
                     "(composition and statistical plan deferred per charter §8.11; unbound "
                     "designation would be arbitrary)")

    rationale = designation.get("rationale")
    _require(isinstance(rationale, str) and rationale,
             "set-class designation: rationale required (order §10: explicit, never silent)")
    return {
        "assignments": {cid: assignments[cid] for cid in candidate_ids},
        "rationale": rationale,
        "set_binding_reference": binding_ref,
        "public_preexecution_forbidden": zero_executions,
    }


# ---------------------------------------------------------------------------
# Per-case 15-point checks
# ---------------------------------------------------------------------------

def _check_candidate_contract(candidate: dict) -> "tuple[bool, str]":
    if candidate.get("ecp_object") != "case-candidate":
        return False, f"ecp_object {candidate.get('ecp_object')!r} != 'case-candidate'"
    issues = version_issues(candidate)
    if issues:
        return False, "; ".join(issues)
    return True, "case-candidate contract + version citations accepted"


def _check_qualification_decision(artifact: dict) -> "tuple[bool, str]":
    if artifact.get("ecp_object") != "case-qualification":
        return False, f"ecp_object {artifact.get('ecp_object')!r} != 'case-qualification'"
    if artifact.get("decision") != "ACCEPT":
        return False, f"qualification decision {artifact.get('decision')!r} != ACCEPT"
    # Reason codes may accompany ACCEPT as recorded, non-blocking findings
    # (e.g. Q3-CORRESPONDENCE-GAP: partial mechanical NL↔formal correspondence,
    # author-attested, disclosed at phase close). They are carried verbatim on
    # the readiness record — never re-adjudicated here (integrity-only).
    issues = version_issues(artifact)
    if issues:
        return False, "; ".join(issues)
    carried = artifact.get("reason_codes") or []
    note = f"; carried findings: {carried}" if carried else ""
    return True, f"qualification artifact contract valid; decision ACCEPT{note}"


def _check_content_hash_binding(candidate: dict, artifact: dict, run_entry: "dict | None") -> "tuple[bool, str]":
    ch = candidate.get("content_hash")
    ah = artifact.get("content_hash")
    if ch != ah:
        return False, f"candidate content_hash {ch} != artifact content_hash {ah}"
    if run_entry is not None and run_entry.get("content_hash") not in (None, ch):
        return False, "run entry content_hash does not match the candidate"
    if run_entry is not None and run_entry.get("candidate_id") != candidate.get("candidate_id"):
        return False, "run entry candidate_id does not match the candidate"
    return True, "candidate == artifact == run-entry content-hash identity"


def _check_provenance_completeness(candidate: dict) -> "tuple[bool, str]":
    record = candidate.get("authoring_independence")
    if not isinstance(record, dict):
        return False, "authoring_independence record absent"
    missing = [f for f in INDEPENDENCE_FIELDS if f not in record]
    if missing:
        return False, f"missing section-3 fields: {missing}"
    return True, f"all {len(INDEPENDENCE_FIELDS)} section-3 fields present"


def _check_independence_explicitness(candidate: dict) -> "tuple[bool, str]":
    record = candidate.get("authoring_independence", {})
    status = record.get("independence_status")
    if not isinstance(status, dict):
        return False, "independence_status absent (a bare 'independent' claim is never accepted)"
    label = status.get("label", "")
    if not isinstance(label, str) or not label:
        return False, "independence_status.label absent"
    if re.fullmatch(r"(?i)independent", label.strip()):
        return False, "bare 'INDEPENDENT' label rejected (explicit limitations required)"
    needed = ("case_author_independence", "performance_blindness", "system_neutrality")
    missing = [f for f in needed if f not in status]
    if missing:
        return False, f"independence_status missing: {missing}"
    limitations = record.get("independence_limitations")
    if not isinstance(limitations, list) or not limitations:
        return False, "independence_limitations empty (limitations must be declared, never implied absent)"
    return True, f"explicit status: {label}"


def _check_ground_truth_mechanical(artifact: dict) -> "tuple[bool, str]":
    gt = artifact.get("dimensions", {}).get("ground_truth", {})
    if not isinstance(gt, dict) or gt.get("status") != "PASS":
        return False, f"Q3 status {gt.get('status') if isinstance(gt, dict) else 'absent'} != PASS"
    return True, "Q3 mechanical ground-truth verification PASS"


def _check_gt_class_consistency(artifact: dict) -> "tuple[bool, str]":
    gt = artifact.get("dimensions", {}).get("ground_truth", {})
    authored = gt.get("authored_class")
    derived = gt.get("derived_class")
    if authored != derived:
        return False, f"authored class {authored!r} != derived class {derived!r}"
    if not authored:
        return False, "ground-truth classes absent"
    return True, f"authored == derived == {authored}"


def _check_artifact_chain(artifact: dict, prev_hash: str) -> "tuple[bool, str]":
    stored = artifact.get("artifact_hash")
    if not _as_hex64(stored):
        return False, "artifact_hash not a sha256 hex string"
    recomputed = hash_document_excluding(artifact, "artifact_hash")
    if recomputed != stored:
        return False, "artifact_hash recomputation mismatch"
    prev = artifact.get("prev_qualification_hash")
    if prev != prev_hash:
        return False, "chain link broken (prev_qualification_hash mismatch)"
    return True, "artifact hash recomputes; chain link holds"


def _check_novelty_status(artifact: dict, key: str, want: str) -> "tuple[bool, str]":
    novelty = artifact.get("dimensions", {}).get("novelty", {})
    if not isinstance(novelty, dict):
        return False, "novelty dimension absent"
    value = novelty.get(key)
    if isinstance(value, dict):
        value = value.get("status")
    if value != want:
        return False, f"{key} = {value!r} (expected {want!r})"
    return True, f"{key} = {want}"


def _check_leakage_pre_screen(artifact: dict) -> "tuple[bool, str]":
    leakage = artifact.get("dimensions", {}).get("leakage", {})
    if not isinstance(leakage, dict):
        return False, "leakage dimension absent"
    classes = leakage.get("classes", {})
    if not isinstance(classes, dict) or len(classes) != 6:
        return False, f"expected the six leakage classes, got {sorted(classes) if isinstance(classes, dict) else type(classes).__name__}"
    for key, value in classes.items():
        if key == "model":
            if not str(value).startswith("NOT-APPLICABLE-PRE-EXECUTION"):
                return False, f"model class {value!r} — expected NOT-APPLICABLE-PRE-EXECUTION (zero executions project-wide)"
        elif value != "CLEAR":
            return False, f"leakage class {key} = {value!r} (expected CLEAR)"
    if leakage.get("status") != "CLEAN":
        return False, f"leakage status {leakage.get('status')!r} != CLEAN"
    return True, "six classes CLEAR; model N.A. pre-execution; status CLEAN"


def _check_disclosure(candidate: dict, artifact: dict, which: str) -> "tuple[bool, str]":
    if which == "representation_bias":
        record = candidate.get("representation_bias_disclosure")
        fields = RB_FIELDS
        dimension = artifact.get("dimensions", {}).get("representation_bias", {})
        want = "PRESENT"
    else:
        record = candidate.get("environmental_pre_check")
        fields = ENV_FIELDS
        dimension = artifact.get("dimensions", {}).get("environmental_pre_check", {})
        want = "PRESENT"
    if not isinstance(record, dict):
        return False, f"{which} record absent on the candidate"
    missing = [f for f in fields if f not in record]
    if missing:
        return False, f"{which} missing fields: {missing}"
    if not isinstance(dimension, dict) or dimension.get("status") != want:
        return False, f"{which} qualification-dimension status {dimension.get('status') if isinstance(dimension, dict) else 'absent'} != {want}"
    return True, f"{which} record complete; dimension {want}"


def run_case_checks(candidate: dict, artifact: dict, run_entry: "dict | None", prev_hash: str) -> "list[dict]":
    """Execute the 15-point battery for one candidate; returns check records."""
    results: "list[dict]" = []

    def add(code: str, key: str, ok: bool, evidence: str) -> None:
        results.append({
            "code": code,
            "check": key,
            "status": "PASS" if ok else "FAIL",
            "evidence": evidence,
        })

    checks = [
        ("C-01", "candidate-contract", _check_candidate_contract(candidate)),
        ("C-02", "qualification-decision", _check_qualification_decision(artifact)),
        ("C-03", "content-hash-binding", _check_content_hash_binding(candidate, artifact, run_entry)),
        ("C-04", "provenance-completeness", _check_provenance_completeness(candidate)),
        ("C-05", "independence-explicitness", _check_independence_explicitness(candidate)),
        ("C-06", "ground-truth-mechanical", _check_ground_truth_mechanical(artifact)),
        ("C-07", "ground-truth-class-consistency", _check_gt_class_consistency(artifact)),
        ("C-08", "artifact-chain-integrity", _check_artifact_chain(artifact, prev_hash)),
        ("C-09", "novelty-within-pool", _check_novelty_status(artifact, "n3_within_pool", "UNIQUE")),
        ("C-10", "novelty-cross-population", _check_novelty_status(artifact, "n4_cross_population", "CLEAR")),
        ("C-11", "novelty-implementation-encoding", _check_novelty_status(artifact, "n5_implementation_encoding", "CLEAR")),
        ("C-12", "novelty-fixture-leakage", _check_novelty_status(artifact, "n6_fixture_leakage", "CLEAR")),
        ("C-13", "leakage-pre-screen", _check_leakage_pre_screen(artifact)),
        ("C-14", "disclosure-representation-bias", _check_disclosure(candidate, artifact, "representation_bias")),
        ("C-15", "disclosure-environmental-precheck", _check_disclosure(candidate, artifact, "environmental_pre_check")),
    ]
    for code, key, (ok, evidence) in checks:
        add(code, key, ok, evidence)
    return results


def _gt_validation_track(candidate: dict, artifact: dict) -> str:
    forwarded = artifact.get("forwarded") or []
    if any(f.get("code") == "FWD-GT-DESIGNED-AMBIGUITY" for f in forwarded if isinstance(f, dict)):
        return "DESIGNED-AMBIGUITY-FORWARDED"
    gt = artifact.get("dimensions", {}).get("ground_truth", {})
    if gt.get("derived_class") == "INDETERMINATE":
        return "NONDETERMINATE-READING-RULE-TRACK"
    return "CONFIRMED-TRACK"


# ---------------------------------------------------------------------------
# The readiness run (deterministic, hash-chained)
# ---------------------------------------------------------------------------

def _current_operator() -> str:
    return "ECP Foundation Executor <foundation@ecp-protocol.local>"


def run_readiness(
    candidates: "list[dict]",
    qualification_run: dict,
    qualification_artifacts: "list[dict]",
    decision_register: dict,
    population_decision: dict,
    set_class_designation: dict,
    prior_candidates: "list[dict] | None" = None,
    run_id: str = "ECP-RDNYRUN-CA1V1-R1",
    assessed_at: str = "1970-01-01T00:00:00Z",
    operator: "str | None" = None,
    zero_executions: bool = True,
    engine_profile: str = ENGINE_VERSION,
) -> dict:
    """Run the deterministic registration-readiness assessment.

    Returns ``{records, run}``. Pure function of the inputs.
    """
    if engine_profile not in ENGINE_PROFILES:
        raise InvalidReadinessState(
            f"unknown engine profile {engine_profile!r}; known: {list(ENGINE_PROFILES)}"
        )
    operator = operator or _current_operator()
    prior_candidates = prior_candidates or []

    _require(isinstance(qualification_run, dict) and qualification_run.get("ecp_object") == "qualification-run",
             "readiness inputs: qualification_run must be a qualification-run manifest")
    _require(qualification_run.get("decisions", {}).get("accept") == len(candidates),
             "readiness inputs: the qualification run must ACCEPT exactly the supplied candidate pool")
    _require(len(qualification_artifacts) == len(candidates),
             "readiness inputs: one qualification artifact per candidate required")

    register_eval = evaluate_decision_register(decision_register)
    population = validate_population_decision(population_decision, candidates, prior_candidates)
    set_classes = validate_set_class_designation(set_class_designation, candidates, zero_executions)

    entries_by_id = {e.get("candidate_id"): e for e in qualification_run.get("entries", [])}
    artifacts_by_id = {a.get("candidate_id"): a for a in qualification_artifacts}

    # global blockers bind every case in scope
    global_blockers = [
        f"{item['item_id']}: {item['reason']}" for item in register_eval["blocking_items"]
    ] + [
        f"{f['finding_id']}: {f['reason']}" for f in register_eval["unresolved_findings"]
    ]
    scope = set(population["scope_candidate_ids"])

    records: "list[dict]" = []
    prev_hash = "0" * 64  # readiness record chain
    prev_qual_hash = "0" * 64  # qualification artifact chain (C-08 basis)
    for index, candidate in enumerate(candidates, start=1):
        cid = candidate.get("candidate_id")
        artifact = artifacts_by_id.get(cid)
        _require(artifact is not None, f"{cid}: no qualification artifact found")
        run_entry = entries_by_id.get(cid)
        checks = run_case_checks(candidate, artifact, run_entry, prev_qual_hash)
        failed = [c for c in checks if c["status"] == "FAIL"]

        set_class = set_classes["assignments"][cid]
        track = _gt_validation_track(candidate, artifact)

        holding_reasons: "list[str]" = []
        if cid in scope:
            holding_reasons.extend(global_blockers)
            if track == "DESIGNED-AMBIGUITY-FORWARDED":
                holding_reasons.append(
                    "O-04/GT: designed-ambiguacy forwarded flag persists (FWD-GT-DESIGNED-AMBIGUITY); "
                    "the nondeterminate ground-truth reading requires the owner-authorized validation "
                    "procedure — never silently converted"
                )
            elif track == "NONDETERMINATE-READING-RULE-TRACK":
                holding_reasons.append(
                    "O-04/GT: INDETERMINATE ground truth is C-004-class material — the "
                    "nondeterminate reading rule requires the owner-authorized validation procedure"
                )

        if any(c["check"] in REJECT_CHECKS for c in failed):
            decision = "REJECT"
        elif failed:
            decision = "REVISE"
        elif cid in scope and holding_reasons:
            decision = "HOLD"
        elif cid in scope:
            decision = "REGISTER"
        else:
            decision = "HOLD"
            holding_reasons.append("population: candidate outside the explicit registration scope")

        forwarded_note = []
        for f in (artifact.get("forwarded") or []):
            if isinstance(f, dict) and f.get("code") == "FWD-GT-DESIGNED-AMBIGUITY":
                forwarded_note.append({
                    "code": f.get("code"),
                    "note": f.get("note"),
                    "target_stage": "gt-validation (O-04 owner-authorized stage)",
                })

        carried_codes = list(artifact.get("reason_codes") or [])
        gt_correspondence_note = None
        if "Q3-CORRESPONDENCE-GAP" in carried_codes:
            gt_correspondence_note = (
                "carried qualification finding: partial mechanical NL↔formal correspondence "
                "(Q3-CORRESPONDENCE-GAP; full semantic correspondence is author-attested, a "
                "declared limitation from phase close). Non-blocking at readiness; the O-04 "
                "owner-authorized GT validation stage must scrutinize this case's GT "
                "defensibility against the natural-language presentation."
            )

        record = {
            "ecp_object": "case-readiness",
            "readiness_id": f"ECP-RDNY-{cid.split('-')[-1]}" if cid else f"ECP-RDNY-{index:06d}",
            "candidate_id": cid,
            "source_case_id": artifact.get("source_case_id"),
            "run_id": run_id,
            "assessed_at": assessed_at,
            "operator": operator,
            "qualification_id": artifact.get("qualification_id"),
            "content_hash": candidate.get("content_hash"),
            "qualification_artifact_hash": artifact.get("artifact_hash"),
            "entry_index": index,
            "prev_readiness_hash": prev_hash,
            "engine": {"id": ENGINE_ID, "version": engine_profile, "profile": engine_profile},
            "checks": checks,
            "mechanical_state": "PASS" if not failed else "FAIL",
            "checks_passed": sum(1 for c in checks if c["status"] == "PASS"),
            "set_class": set_class,
            "gt_validation_track": track,
            "holding_reasons": holding_reasons,
            "forwarded": forwarded_note,
            "carried_qualification_reason_codes": carried_codes,
            "gt_correspondence_note": gt_correspondence_note,
            "decision": decision,
            "reason_codes": [
                f"CHECK-FAIL:{c['code']}/{c['check']}" for c in failed
            ],
            "boundary": "REGISTRATION READINESS ASSESSMENT ONLY — NOT A REGISTRATION (order §11/§12)",
            "protocol_version": engine_profile,
            "schema_version": engine_profile,
        }
        record["record_hash"] = hash_document_excluding(record, "record_hash")
        records.append(record)
        prev_hash = record["record_hash"]
        prev_qual_hash = artifact.get("artifact_hash")

    tallies = {state.lower(): sum(1 for r in records if r["decision"] == state) for state in READINESS_STATES}

    authorization = assess_registration_authorization(
        decision_register, population, records
    )

    verdict = "REGISTRATION-AUTHORIZED" if authorization["status"] == "AUTHORIZED" else "OWNER-DECISION-REQUIRED"

    run = {
        "ecp_object": "readiness-run",
        "run_id": run_id,
        "assessed_at": assessed_at,
        "operator": operator,
        "engine": {"id": ENGINE_ID, "version": engine_profile, "profile": engine_profile},
        "inputs": {
            "qualification_run_id": qualification_run.get("run_id"),
            "qualification_run_hash": qualification_run.get("run_hash"),
            "qualification_chain_head": qualification_run.get("chain_head"),
            "candidate_count": len(candidates),
            "decision_register": {
                "register_id": decision_register.get("register_id"),
                "register_hash": decision_register.get("register_hash"),
                "item_states": register_eval["item_states"],
            },
            "population_decision": {
                "decision": population["decision"],
                "rationale": population["rationale"],
            },
            "set_class_designation": {
                "rationale": set_classes["rationale"],
                "set_binding_reference": set_classes["set_binding_reference"],
                "public_preexecution_forbidden": set_classes["public_preexecution_forbidden"],
            },
            "prior_population": {
                "count": len(prior_candidates),
                "candidate_ids": [c.get("candidate_id") for c in prior_candidates],
            },
        },
        "checks": [
            {"code": code, "check": key, "description": desc, "failure_class": cls}
            for code, key, desc, cls in REGISTRATION_READINESS_CHECKS
        ],
        "decision_rules": {
            "precedence": "REJECT > REVISE > HOLD > REGISTER",
            "reject": [
                "any reject-class check of the 15-point battery fails",
                "set class PUBLIC while zero executions exist project-wide",
            ],
            "revise": [
                "a revise-class check fails (provenance/disclosure completeness)",
            ],
            "hold": [
                "all 15 checks pass but an unresolved blocking owner item binds the case",
                "an owner-ruling finding is unresolved",
                "candidate outside the explicit population scope",
            ],
            "register": [
                "all 15 checks pass; no blocking item; valid set class; inside the explicit scope",
            ],
        },
        "parameters": {
            "zero_executions_project_wide": zero_executions,
            "cross_population_jaccard_threshold": CROSS_POP_JACCARD_THRESHOLD,
            "implicit_defaults": "FORBIDDEN (order §4): every owner item carries an explicit state",
        },
        "population": population,
        "set_classes": {
            "assignments": set_classes["assignments"],
            "rationale": set_classes["rationale"],
        },
        "owner_decision_register": {
            "register_id": decision_register.get("register_id"),
            "item_states": register_eval["item_states"],
            "blocking_items": register_eval["blocking_items"],
            "unresolved_findings": register_eval["unresolved_findings"],
        },
        "entries": [
            {
                "readiness_id": r["readiness_id"],
                "candidate_id": r["candidate_id"],
                "source_case_id": r["source_case_id"],
                "content_hash": r["content_hash"],
                "qualification_id": r["qualification_id"],
                "qualification_artifact_hash": r["qualification_artifact_hash"],
                "set_class": r["set_class"],
                "gt_validation_track": r["gt_validation_track"],
                "checks_passed": r["checks_passed"],
                "decision": r["decision"],
                "record_hash": r["record_hash"],
            }
            for r in records
        ],
        "decisions": tallies,
        "chain_head": records[-1]["record_hash"] if records else "0" * 64,
        "registration_authorization": authorization,
        "verdict": verdict,
        "boundary": (
            "REGISTRATION REMAINS CLOSED — READINESS ASSESSMENT ONLY; the manifest gate "
            "REFUSES while unresolved blocking owner items exist (order §11/§12)"
            if authorization["status"] == "REFUSED" else
            "REGISTRATION AUTHORIZED AT SET LEVEL — manifest construction permitted under this "
            "order; the ledger ceremony remains the separate full-contract instrument"
        ),
        "execution_isolation": (
            "NO evaluated model execution; NO case execution; NO results collection; NO scoring; "
            "NO statistical testing; NO ledger writes (order §12)"
        ),
        "determinism": (
            "pure function of (candidates, qualification run + artifacts, decision register, "
            "population decision, set-class designation, prior population content, run metadata)"
        ),
        "protocol_version": engine_profile,
        "schema_version": engine_profile,
    }
    run["run_hash"] = hash_document_excluding(run, "run_hash")
    return {"records": records, "run": run}


# ---------------------------------------------------------------------------
# Registration-authorization gate + manifest (order §11/§12)
# ---------------------------------------------------------------------------

def assess_registration_authorization(
    decision_register: dict, population: dict, records: "list[dict]"
) -> dict:
    """Assess whether the manifest gate may open (order §11/§14).

    REFUSED when: any owner item REMAINS-OPEN and blocking; any finding
    requiring an owner ruling is unrated; any in-scope case is not REGISTER.
    AUTHORIZED only when literally nothing blocks.
    """
    reasons: "list[str]" = []
    register_eval = evaluate_decision_register(decision_register)
    for item in register_eval["blocking_items"]:
        reasons.append(f"{item['item_id']} REMAINS-OPEN and blocking: {item['reason']}")
    for finding in register_eval["unresolved_findings"]:
        reasons.append(f"{finding['finding_id']} requires an owner ruling: {finding['reason']}")

    scope = set(population.get("scope_candidate_ids", []))
    for record in records:
        if record.get("candidate_id") in scope and record.get("decision") != "REGISTER":
            reasons.append(
                f"{record.get('candidate_id')}: readiness decision {record.get('decision')} "
                "(cases with unresolved gates may not register — order §12)"
            )
    status = "AUTHORIZED" if not reasons else "REFUSED"
    return {"status": status, "reasons": reasons}


def build_registration_manifest(
    records: "list[dict]",
    run: dict,
    registrar: str,
    registered_at: str,
    registration_id: str = "ECP-REGSET-CA1V1-0001",
    set_binding_reference: "str | None" = None,
) -> dict:
    """Build the Registration Manifest (order §11) — REFUSES unless authorized.

    The manifest freezes the registered set: per-case content hashes,
    qualification artifact hashes, set classes, GT validation tracks, the
    readiness run binding, timestamps, and the immutability rule (changes only
    via the amendment protocol). It is the set-level freeze document; the
    ledger ceremony remains the separate full-contract instrument (evaluation
    + system + case binding). This builder never writes the ledger.
    """
    authorization = run.get("registration_authorization", {})
    if authorization.get("status") != "AUTHORIZED":
        raise RegistrationManifestRefused(
            "REGISTRATION MANIFEST REFUSED (order §11: only when ALL gates pass; order §12: "
            "registering cases with unresolved gates is forbidden):\n  - "
            + "\n  - ".join(authorization.get("reasons", ["authorization status not AUTHORIZED"]))
        )
    not_ready = [r for r in records if r.get("decision") != "REGISTER"]
    if not_ready:
        raise RegistrationManifestRefused(
            "REGISTRATION MANIFEST REFUSED: records outside the REGISTER state: "
            + ", ".join(f"{r.get('candidate_id')}={r.get('decision')}" for r in not_ready)
        )
    if not re.fullmatch(r"ECP-REGSET-[A-Za-z0-9][A-Za-z0-9._:-]*", registration_id):
        raise InvalidReadinessState("registration_id: expected an ECP-REGSET-… identifier")

    manifest = {
        "ecp_object": "registration-manifest",
        "registration_id": registration_id,
        "registrar": registrar,
        "registered_at": registered_at,
        "readiness_run": {
            "run_id": run.get("run_id"),
            "run_hash": run.get("run_hash"),
            "assessed_at": run.get("assessed_at"),
            "engine": run.get("engine"),
        },
        "population_decision": run.get("population", {}).get("decision"),
        "set_binding_reference": set_binding_reference,
        "cases": [
            {
                "candidate_id": r["candidate_id"],
                "source_case_id": r["source_case_id"],
                "content_hash": r["content_hash"],
                "qualification_id": r["qualification_id"],
                "qualification_artifact_hash": r["qualification_artifact_hash"],
                "set_class": r["set_class"],
                "gt_validation_track": r["gt_validation_track"],
            }
            for r in records
        ],
        "immutability": (
            "append-only freeze: the manifest may change only through the amendment protocol "
            "(two-phase disclosure, full re-review, nothing inherited); ground truth sealed at "
            "registration; no post-hoc changes (order §11/§12)"
        ),
        "execution_isolation": (
            "manifest freeze only: NO evaluated model execution; NO case execution; NO results"
        ),
        "protocol_version": ENGINE_VERSION,
        "schema_version": ENGINE_VERSION,
    }
    manifest["manifest_hash"] = hash_document_excluding(manifest, "manifest_hash")
    return manifest


# ---------------------------------------------------------------------------
# Verification (integrity-only; never scientific adjudication)
# ---------------------------------------------------------------------------

def verify_readiness_record(record: dict) -> "list[str]":
    """Integrity issues for one readiness record (issue list)."""
    issues: "list[str]" = []
    if not isinstance(record, dict):
        return ["<root>: expected a JSON object"]
    if record.get("ecp_object") != "case-readiness":
        issues.append("ecp_object: expected 'case-readiness'")
    if record.get("decision") not in READINESS_STATES:
        issues.append(f"decision {record.get('decision')!r} outside the four states")
    stored = record.get("record_hash")
    if not _as_hex64(stored):
        issues.append("record_hash: not a sha256 hex string")
        return issues
    recomputed = hash_document_excluding(record, "record_hash")
    if recomputed != stored:
        issues.append("record_hash: recomputation mismatch (tampering or corruption)")
    checks = record.get("checks", [])
    if not isinstance(checks, list) or len(checks) != len(REGISTRATION_READINESS_CHECKS):
        issues.append(f"checks: expected the {len(REGISTRATION_READINESS_CHECKS)}-point battery")
    else:
        expected = {key: code for code, key, _d, _c in REGISTRATION_READINESS_CHECKS}
        for check in checks:
            if expected.get(check.get("check")) != check.get("code"):
                issues.append(f"checks: unexpected check {check.get('code')}/{check.get('check')}")
                break
    if record.get("set_class") not in SET_CLASSES:
        issues.append(f"set_class {record.get('set_class')!r} outside {SET_CLASSES}")
    if record.get("checks_passed") != sum(1 for c in checks if isinstance(c, dict) and c.get("status") == "PASS"):
        issues.append("checks_passed: tally does not match the check list")
    return issues


def verify_readiness_run(run: dict, records: "list[dict]") -> "list[str]":
    """Integrity issues for the readiness run manifest (issue list)."""
    issues: "list[str]" = []
    if not isinstance(run, dict):
        return ["<root>: expected a JSON object"]
    if run.get("ecp_object") != "readiness-run":
        issues.append("ecp_object: expected 'readiness-run'")
    stored = run.get("run_hash")
    if not _as_hex64(stored):
        issues.append("run_hash: not a sha256 hex string")
        return issues
    recomputed = hash_document_excluding(run, "run_hash")
    if recomputed != stored:
        issues.append("run_hash: recomputation mismatch (tampering or corruption)")

    entries = run.get("entries", [])
    if len(entries) != len(records):
        issues.append(f"entries: manifest lists {len(entries)} but {len(records)} records provided")
    for entry, record in zip(entries, records):
        if entry.get("record_hash") != record.get("record_hash"):
            issues.append(f"{entry.get('candidate_id', '?')}: entry record_hash does not match the record")
        if entry.get("decision") != record.get("decision"):
            issues.append(f"{entry.get('candidate_id', '?')}: entry decision does not match the record")
        if entry.get("content_hash") != record.get("content_hash"):
            issues.append(f"{entry.get('candidate_id', '?')}: entry content_hash does not match the record")

    tallies = {state.lower(): sum(1 for r in records if r.get("decision") == state) for state in READINESS_STATES}
    if run.get("decisions") != tallies:
        issues.append(f"decisions: tallies {run.get('decisions')} do not match records {tallies}")

    if records:
        head = records[-1].get("record_hash")
        if run.get("chain_head") != head:
            issues.append("chain_head: does not match the last record hash")
        prev = "0" * 64
        for record in records:
            if record.get("prev_readiness_hash") != prev:
                issues.append(
                    f"{record.get('readiness_id', '?')}: chain link broken "
                    "(prev_readiness_hash does not match the previous record)"
                )
            prev = record.get("record_hash", "")
    elif run.get("chain_head") != "0" * 64:
        issues.append("chain_head: expected genesis hash for an empty run")

    # authorization consistency: REFUSED must carry reasons; AUTHORIZED must not
    authorization = run.get("registration_authorization", {})
    if authorization.get("status") == "AUTHORIZED" and authorization.get("reasons"):
        issues.append("registration_authorization: AUTHORIZED with non-empty reasons")
    if authorization.get("status") == "REFUSED" and not authorization.get("reasons"):
        issues.append("registration_authorization: REFUSED without reasons")
    verdict = run.get("verdict")
    if authorization.get("status") == "AUTHORIZED" and verdict != "REGISTRATION-AUTHORIZED":
        issues.append("verdict: AUTHORIZED runs must carry verdict REGISTRATION-AUTHORIZED")
    if authorization.get("status") == "REFUSED" and verdict != "OWNER-DECISION-REQUIRED":
        issues.append("verdict: REFUSED runs must carry verdict OWNER-DECISION-REQUIRED")
    return issues


def verify_registration_manifest(manifest: dict, records: "list[dict]", run: dict) -> "list[str]":
    """Integrity issues for a registration manifest (issue list)."""
    issues: "list[str]" = []
    if not isinstance(manifest, dict):
        return ["<root>: expected a JSON object"]
    if manifest.get("ecp_object") != "registration-manifest":
        issues.append("ecp_object: expected 'registration-manifest'")
    stored = manifest.get("manifest_hash")
    if not _as_hex64(stored):
        issues.append("manifest_hash: not a sha256 hex string")
        return issues
    recomputed = hash_document_excluding(manifest, "manifest_hash")
    if recomputed != stored:
        issues.append("manifest_hash: recomputation mismatch (tampering or corruption)")
    if manifest.get("readiness_run", {}).get("run_hash") != run.get("run_hash"):
        issues.append("readiness_run.run_hash: does not match the readiness run")
    by_id = {r.get("candidate_id"): r for r in records}
    cases = manifest.get("cases", [])
    if len(cases) != len(records):
        issues.append(f"cases: manifest lists {len(cases)} but {len(records)} records provided")
    for case in cases:
        record = by_id.get(case.get("candidate_id"))
        if record is None:
            issues.append(f"cases: {case.get('candidate_id')} not present in the readiness records")
            continue
        for field in ("content_hash", "qualification_artifact_hash", "set_class", "gt_validation_track"):
            if case.get(field) != record.get(field):
                issues.append(f"cases: {case.get('candidate_id')}: {field} does not match the readiness record")
        if record.get("decision") != "REGISTER":
            issues.append(f"cases: {case.get('candidate_id')}: readiness decision is not REGISTER")
    return issues
