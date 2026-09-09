"""ECP case amendment & owner-adjudication construction (M3-CA0-A, 0.4.0).

This module implements the ADJUDICATION layer of the case review pipeline:

- :func:`build_adjudication_record` — deterministic construction of a
  ``review-adjudication`` record (the owner seam; the record content is
  the operator's transcription of an owner decision or of an
  owner-written rule from an execution order, applied to preserved
  evidence). Nothing here fabricates an owner decision: the caller
  supplies the decision basis and the rationale verbatim.

- :func:`draft_case_amendment` / :func:`complete_disclosure` — the
  TWO-STEP case amendment process (order M3-CA0-A §7, amended):

  1. DRAFTING — the amendment content (defect, change,
     not-outcome-dependent rationale, hashes, provenance) is authored.
     The representation-bias disclosure is NOT completed here; supplying
     disclosure inputs to the drafting step is a hard error.
  2. DISCLOSURE — a strictly separate step, run afterwards against the
     fully-formed draft. It records ``disclosed_against_draft_hash`` =
     the draft's ``draft_hash``, so the record carries machine evidence
     that the disclosure was completed AFTER drafting (never
     concurrently).

  A fabricated record that tries to author the disclosure concurrently
  with the amendment cannot reproduce this two-hash structure and fails
  :func:`verify_amendment`.

- :func:`apply_amendment` — deterministic derivation of the amended
  candidate (v2): a PURE function of (v1 candidate, amendment record).
  The v1 record is never mutated; the v2 view exists only inside a
  review run that applies the amendment (§8 re-review).

- :func:`effective_candidates` — the review-time substitution: for each
  candidate, if a COMPLETED, hash-verified, correctly-targeted amendment
  exists, the derived v2 replaces the v1 for review purposes. Invalid,
  PENDING or mis-targeted amendments abort loudly (never silently
  ignored).

The disclosure value is an AUDIT/PROVENANCE field, never an eligibility
decision: a ``POSSIBLE``/``KNOWN`` disclosure does not disqualify an
amendment, but it travels with every artifact that applies it and is
never silently treated as unbiased.
"""

import copy

from .hashing import hash_document, hash_document_excluding
from .validate import validate_document

#: Allowed representation-bias disclosure values (M3-CA0-A §7 amended).
DISCLOSURE_VALUES = ("NONE", "POSSIBLE", "KNOWN")

#: Amendment change kinds understood by this version.
AMENDMENT_CHANGE_KINDS = ("GT-DOCUMENT-CONSOLIDATION",)

#: Adjudication dispositions (mirrors review-adjudication.schema.json).
ADJ_DISPOSITIONS = ("RESOLVE-CLEAN", "ACCEPT-RISK", "CONFIRM-DEFECT", "UPHOLD-OPEN")


class AdjudicationError(Exception):
    """Raised when an adjudication/amendment operation would violate the
    M3-CA0-A order semantics (loud failures, never silent degradation)."""


# ---------------------------------------------------------------------------
# owner adjudication records (the human seam)
# ---------------------------------------------------------------------------


def build_adjudication_record(
    *,
    adjudication_id: str,
    owner_identity: str,
    recorded_by_operator: str,
    at: str,
    question_code: str,
    disposition: str,
    rationale: str,
    candidate_id: "str | None" = None,
    protocol_version: str = "0.4.0",
    schema_version: str = "0.4.0",
) -> dict:
    """Deterministically construct a ``review-adjudication`` record.

    The caller supplies the decision content (owner identity, decision
    rule source, rationale). This function only structures and hashes it;
    it never invents, infers or defaults a decision.
    """
    if disposition not in ADJ_DISPOSITIONS:
        raise AdjudicationError(
            f"disposition {disposition!r} outside allowed set {ADJ_DISPOSITIONS}"
        )
    if not rationale or not rationale.strip():
        raise AdjudicationError("rationale must carry the decision basis (non-empty)")
    applies_to: dict = {"question_code": question_code}
    if candidate_id:
        applies_to["candidate_id"] = candidate_id
    record = {
        "ecp_object": "review-adjudication",
        "adjudication_id": adjudication_id,
        "owner_identity": owner_identity,
        "recorded_by_operator": recorded_by_operator,
        "at": at,
        "applies_to": applies_to,
        "disposition": disposition,
        "rationale": rationale,
        "protocol_version": protocol_version,
        "schema_version": schema_version,
    }
    record["adjudication_hash"] = hash_document_excluding(record, "adjudication_hash")
    issues = validate_document(record, "review-adjudication")
    if issues:
        raise AdjudicationError(
            "constructed adjudication record is schema-invalid: "
            + "; ".join(issues[:5])
        )
    return record


# ---------------------------------------------------------------------------
# case amendment: step 1 — DRAFTING (no disclosure here, ever)
# ---------------------------------------------------------------------------


def draft_case_amendment(
    candidate: dict,
    *,
    amendment_id: str,
    order_basis: str,
    defect_code: str,
    defect_description: str,
    defect_why: str,
    defect_evidence: str,
    retained_answer_block: int,
    retained_derivation_block: int,
    removed_answer_blocks: "list[int]",
    removed_derivation_blocks: "list[int]",
    not_outcome_statement: str,
    not_outcome_basis: str,
    amendment_author: str,
    drafted_at: str,
    operator: str,
    order_reference: str,
    protocol_version: str = "0.4.0",
    schema_version: str = "0.4.0",
) -> dict:
    """Draft a case amendment (STEP 1 — disclosure NOT completed here).

    The retained/removed blocks refer to 1-based ``source_block`` indices
    in the candidate content. The resulting v2 content and its hash are
    derived deterministically here (never hand-composed by the caller).

    Refuses any attempt to supply disclosure content at drafting time
    (the disclosure is a strictly separate later step; M3-CA0-A §7
    amended).
    """
    content = candidate.get("content")
    if not isinstance(content, dict):
        raise AdjudicationError("candidate carries no content object")

    answers = content.get("intended_correct_answers", [])
    derivations = content.get("derivations", [])
    answer_indices = [a.get("source_block") for a in answers]
    derivation_indices = [d.get("source_block") for d in derivations]

    if len(answers) < 2 or len(derivations) < 2:
        raise AdjudicationError(
            "GT-document consolidation requires a multi-block GT document "
            f"(found {len(answers)} answer block(s), {len(derivations)} "
            "derivation block(s)); nothing to consolidate"
        )
    if retained_answer_block not in answer_indices:
        raise AdjudicationError(
            f"retained answer block {retained_answer_block!r} not present "
            f"in candidate content blocks {answer_indices}"
        )
    if retained_derivation_block not in derivation_indices:
        raise AdjudicationError(
            f"retained derivation block {retained_derivation_block!r} not "
            f"present in candidate content blocks {derivation_indices}"
        )
    for removed in removed_answer_blocks:
        if removed not in answer_indices or removed == retained_answer_block:
            raise AdjudicationError(
                f"removed answer block {removed!r} is not a removable "
                "defective block (must exist and differ from the retained one)"
            )
    for removed in removed_derivation_blocks:
        if removed not in derivation_indices or removed == retained_derivation_block:
            raise AdjudicationError(
                f"removed derivation block {removed!r} is not a removable "
                "defective block (must exist and differ from the retained one)"
            )

    prior_content_hash = candidate.get("content_hash")
    if prior_content_hash != hash_document(content):
        raise AdjudicationError(
            "candidate content_hash does not match its content (intake "
            "corrupt; refusing to amend)"
        )

    v2_content = _consolidate_content(
        content,
        retained_answer_block,
        retained_derivation_block,
    )
    new_content_hash = hash_document(v2_content)

    record = {
        "ecp_object": "case-amendment",
        "amendment_id": amendment_id,
        "candidate_id": candidate["candidate_id"],
        "order_basis": order_basis,
        "prior": {"case_version": 1, "content_hash": prior_content_hash},
        "new": {"case_version": 2, "content_hash": new_content_hash},
        "defect": {
            "code": defect_code,
            "description": defect_description,
            "why_defect": defect_why,
            "evidence": defect_evidence,
        },
        "change": {
            "kind": "GT-DOCUMENT-CONSOLIDATION",
            "retained_answer_block": retained_answer_block,
            "retained_derivation_block": retained_derivation_block,
            "removed_answer_blocks": list(removed_answer_blocks),
            "removed_derivation_blocks": list(removed_derivation_blocks),
        },
        "not_outcome_dependent": {
            "statement": not_outcome_statement,
            "basis": not_outcome_basis,
        },
        "provenance": {
            "amendment_author": amendment_author,
            "drafted_at": drafted_at,
            "operator": operator,
            "order_reference": order_reference,
        },
        "disclosure_phase": {"status": "PENDING"},
        "re_review": {
            "required": True,
            "dimensions": [
                "identity",
                "provenance",
                "specification-completeness",
                "novelty",
                "leakage",
                "duplication",
                "reproducibility",
            ],
            "novelty_leakage_recheck": "REQUIRED",
        },
        "protocol_version": protocol_version,
        "schema_version": schema_version,
    }
    # STEP 1 invariant: the draft carries NO disclosure and NO final hash.
    record["draft_hash"] = hash_document_excluding(record, "draft_hash")
    issues = validate_document(record, "case-amendment")
    if issues:
        raise AdjudicationError(
            "drafted amendment is schema-invalid: " + "; ".join(issues[:5])
        )
    return record


# ---------------------------------------------------------------------------
# case amendment: step 2 — DISCLOSURE (strictly separate, post-draft)
# ---------------------------------------------------------------------------


def complete_disclosure(
    drafted: dict,
    *,
    value: str,
    completed_by: str,
    completed_at: str,
    basis: str,
) -> dict:
    """Complete the representation-bias disclosure (STEP 2).

    Only valid on an existing PENDING draft. The disclosure is recorded
    against the draft's exact ``draft_hash`` (machine evidence that it
    was completed AFTER the amendment was fully drafted, never
    concurrently). Returns the completed record (the draft is not
    mutated).
    """
    if value not in DISCLOSURE_VALUES:
        raise AdjudicationError(
            f"disclosure value {value!r} outside allowed set {DISCLOSURE_VALUES}"
        )
    if drafted.get("disclosure_phase", {}).get("status") != "PENDING":
        raise AdjudicationError(
            "disclosure can only be completed on a PENDING draft (this "
            "record is not a draft, or was already disclosed)"
        )
    draft_hash = drafted.get("draft_hash")
    if not draft_hash:
        raise AdjudicationError("draft record carries no draft_hash")
    # the supplied record must BE the exact draft it claims to be
    probe = copy.deepcopy(drafted)
    probe.pop("draft_hash", None)
    if hash_document_excluding(probe, "draft_hash") != draft_hash:
        raise AdjudicationError(
            "draft record does not hash to its declared draft_hash "
            "(tampered or malformed draft; refusing to disclose)"
        )

    completed = copy.deepcopy(drafted)
    completed["representation_bias_disclosure"] = {
        "value": value,
        "completed_by": completed_by,
        "completed_at": completed_at,
        "disclosed_against_draft_hash": draft_hash,
        "basis": basis,
    }
    completed["disclosure_phase"] = {"status": "COMPLETED"}
    completed["amendment_hash"] = hash_document_excluding(
        completed, "amendment_hash"
    )
    issues = validate_document(completed, "case-amendment")
    if issues:
        raise AdjudicationError(
            "completed amendment is schema-invalid: " + "; ".join(issues[:5])
        )
    return completed


# ---------------------------------------------------------------------------
# verification (structural + the two-phase machine evidence)
# ---------------------------------------------------------------------------


def verify_amendment(record: dict) -> "list[str]":
    """Verify a case-amendment record.

    Checks (issue list, empty = valid):

    - schema validity;
    - the DRAFT view (record minus disclosure, status PENDING, minus
      amendment_hash) hashes exactly to ``draft_hash`` — machine proof
      that the disclosure was completed against a fully-formed,
      disclosure-free draft (never authored concurrently);
    - when COMPLETED: the full record hashes to ``amendment_hash`` and
      the disclosure cites the draft it completed against;
    - when PENDING: no disclosure and no final hash may be present.
    """
    issues = validate_document(record, "case-amendment")
    if issues:
        return ["schema: " + i for i in issues[:5]]

    draft_view = copy.deepcopy(record)
    draft_view.pop("amendment_hash", None)
    draft_view.pop("representation_bias_disclosure", None)
    draft_view["disclosure_phase"] = {"status": "PENDING"}
    recomputed_draft = hash_document_excluding(draft_view, "draft_hash")
    if recomputed_draft != record.get("draft_hash"):
        issues.append(
            "draft_hash: the disclosure-free draft view does not hash to "
            "draft_hash (the two-step draft-then-disclose evidence is "
            "broken; concurrent authoring or tampering is indicated)"
        )

    status = record.get("disclosure_phase", {}).get("status")
    if status == "COMPLETED":
        recomputed_full = hash_document_excluding(record, "amendment_hash")
        if recomputed_full != record.get("amendment_hash"):
            issues.append(
                "amendment_hash: completed record does not hash to its "
                "declared amendment_hash"
            )
        disclosure = record.get("representation_bias_disclosure", {})
        if disclosure.get("disclosed_against_draft_hash") != record.get(
            "draft_hash"
        ):
            issues.append(
                "disclosure: disclosed_against_draft_hash does not equal the "
                "draft_hash of this record (the disclosure did not complete "
                "against this draft)"
            )
    elif status == "PENDING":
        if "representation_bias_disclosure" in record:
            issues.append(
                "disclosure: a PENDING draft must not carry a disclosure"
            )
        if "amendment_hash" in record:
            issues.append(
                "amendment_hash: a PENDING draft must not carry a final hash"
            )
    return issues


# ---------------------------------------------------------------------------
# deterministic amendment application (v2 derivation)
# ---------------------------------------------------------------------------


def _consolidate_content(
    content: dict, retained_answer_block: int, retained_derivation_block: int
) -> dict:
    """Apply a GT-DOCUMENT-CONSOLIDATION change to candidate content.

    Pure: returns a new content dict with the retained answer and
    derivation blocks; every other field is copied verbatim.
    """
    answers = [
        copy.deepcopy(a)
        for a in content.get("intended_correct_answers", [])
        if a.get("source_block") == retained_answer_block
    ]
    derivations = [
        copy.deepcopy(d)
        for d in content.get("derivations", [])
        if d.get("source_block") == retained_derivation_block
    ]
    if len(answers) != 1 or len(derivations) != 1:
        raise AdjudicationError(
            "consolidation must retain exactly one answer block and one "
            "derivation block"
        )
    new_content = copy.deepcopy(content)
    new_content["intended_correct_answers"] = answers
    new_content["derivations"] = derivations
    return new_content


def apply_amendment(candidate: dict, amendment: dict) -> dict:
    """Derive the amended (v2) candidate from (v1 candidate, amendment).

    Pure function: the v1 candidate is never mutated. Verifies the
    amendment (two-phase disclosure evidence included) and the full
    hash chain prior → change → new before deriving.
    """
    issues = verify_amendment(amendment)
    if issues:
        raise AdjudicationError(
            "amendment record is not valid: " + "; ".join(issues[:5])
        )
    if amendment.get("disclosure_phase", {}).get("status") != "COMPLETED":
        raise AdjudicationError(
            "amendment disclosure phase is PENDING: a drafted amendment "
            "cannot be applied before its separate disclosure step "
            "(M3-CA0-A §7 amended)"
        )
    if amendment.get("candidate_id") != candidate.get("candidate_id"):
        raise AdjudicationError(
            f"amendment targets candidate {amendment.get('candidate_id')!r}, "
            f"but it was applied to {candidate.get('candidate_id')!r}"
        )

    prior = amendment.get("prior", {})
    if prior.get("content_hash") != candidate.get("content_hash"):
        raise AdjudicationError(
            "amendment prior content_hash does not match the candidate "
            "(stale or mis-targeted amendment)"
        )
    if prior.get("case_version") != candidate.get("case_version", 1):
        raise AdjudicationError(
            "amendment prior case_version does not match the candidate "
            "(stale or mis-targeted amendment)"
        )

    change = amendment.get("change", {})
    v2_content = _consolidate_content(
        candidate["content"],
        change.get("retained_answer_block"),
        change.get("retained_derivation_block"),
    )
    if hash_document(v2_content) != amendment.get("new", {}).get("content_hash"):
        raise AdjudicationError(
            "derived v2 content does not hash to the amendment's declared "
            "new content_hash (amendment does not describe this change)"
        )

    disclosure = amendment["representation_bias_disclosure"]
    v2 = copy.deepcopy(candidate)
    v2["content"] = v2_content
    v2["content_hash"] = amendment["new"]["content_hash"]
    v2["case_version"] = amendment["new"]["case_version"]
    v2["amendment"] = {
        "amendment_id": amendment["amendment_id"],
        "amendment_hash": amendment["amendment_hash"],
        "prior_case_version": prior["case_version"],
        "prior_content_hash": prior["content_hash"],
    }
    # provenance: append the amendment event (the authoring events are
    # preserved verbatim; the review-layer amendment is recorded as the
    # latest transformation, keeping timestamps non-decreasing)
    history = copy.deepcopy(candidate.get("provenance", {}).get("transformation_history", []))
    history.append(
        {
            "at": amendment["provenance"]["drafted_at"],
            "event": (
                "case amendment "
                + amendment["amendment_id"]
                + " applied (GT document consolidation; representation-bias "
                "disclosure "
                + disclosure["value"]
                + ")"
            ),
            "evidence": (
                "amendments/"
                + amendment["amendment_id"]
                + ".json (amendment_hash "
                + amendment["amendment_hash"][:16]
                + "...)"
            ),
        }
    )
    v2["provenance"] = copy.deepcopy(candidate.get("provenance", {}))
    v2["provenance"]["transformation_history"] = history
    v2["protocol_version"] = amendment["protocol_version"]
    v2["schema_version"] = amendment["schema_version"]

    issues = validate_document(v2, "case-candidate")
    if issues:
        raise AdjudicationError(
            "derived v2 candidate is schema-invalid: " + "; ".join(issues[:5])
        )
    return v2


def effective_candidates(
    candidates: "list[dict]", amendments: "list[dict]"
) -> "tuple[list[dict], list[dict]]":
    """Compute the review-time effective candidate set.

    For every candidate, exactly zero or one COMPLETED amendment may
    apply; the derived v2 view replaces the v1 for review purposes. Any
    inconsistency (PENDING amendment, hash mismatch, two amendments for
    one candidate, amendment without its candidate) aborts loudly.

    Returns (effective_candidates, applied_amendments) — the applied
    list contains the amendment records in candidate order.
    """
    by_candidate: "dict[str, list[dict]]" = {}
    for amendment in amendments or []:
        target = amendment.get("candidate_id")
        by_candidate.setdefault(target, []).append(amendment)

    known_ids = {c.get("candidate_id") for c in candidates}
    for target, records in by_candidate.items():
        if target not in known_ids:
            raise AdjudicationError(
                f"amendment {records[0].get('amendment_id')!r} targets "
                f"unknown candidate {target!r}"
            )
        if len(records) > 1:
            raise AdjudicationError(
                f"candidate {target!r} has {len(records)} amendments; "
                "one amendment per candidate per run (chained versioning "
                "is not part of 0.4.0)"
            )

    effective: "list[dict]" = []
    applied: "list[dict]" = []
    for candidate in candidates:
        records = by_candidate.get(candidate.get("candidate_id"), [])
        if not records:
            effective.append(candidate)
            continue
        amendment = records[0]
        v2 = apply_amendment(candidate, amendment)
        effective.append(v2)
        applied.append(amendment)
    return effective, applied
