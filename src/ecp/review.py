"""Case Review Engine — deterministic three-state eligibility gate (M3-CA0).

This module implements the review half of the M3-CA0 order: a deterministic
pipeline that answers, per candidate case,

    "Is this candidate sufficiently specified, provenance-traceable,
     novelty-safe, leakage-safe, and reproducible enough to become
     registration-eligible?"

and produces exactly one of three decisions — ``ELIGIBLE``, ``REJECTED``,
``REQUIRES_REVIEW`` — plus a hash-chained, tamper-evident review artifact
per candidate and a run manifest. There is NO fourth state: ambiguous
decision inputs abort the run loudly (:class:`InvalidReviewState`) instead
of producing "probably eligible" / "looks fine" / "pending".

Review dimensions implemented (order §4):

- **R1 identity** — deterministic content hash recomputation;
- **R2 provenance** — declared provenance completeness + honest
  NOT-AVAILABLE fields + source-report flags;
- **R3 specification completeness** — authored content present; duplicate /
  conflicting ground-truth blocks are flagged, never reconciled;
  registration-contract authoring (constraints, success criterion,
  verification rule) must be AUTHORED — the engine never infers it;
- **R4 novelty** — within-set exact/canonical/source/signature/overlap
  detection plus the honest external status
  ``NOT_ESTABLISHABLE_MECHANICALLY`` (recorded as an open question for the
  owner, never guessed — external checks would need model invocation or
  retrieval, both forbidden at CA0);
- **R5 leakage** — registry- and containment-based detectors
  (answer-in-task, eval-material-in-task, real-world entities, known
  benchmark/puzzle patterns, metadata labels); a confirmed answer/eval
  leak is disqualifying, risks are open questions;
- **R6 provenance integrity** — candidate → source → transformation →
  canonical artifact recomputed byte-exactly against the retained source
  document;
- **R7 reproducibility** — the artifact embeds the candidate content so
  another operator can reconstruct the definition from retained review
  artifacts alone.

The **human review seam** (§9): every important condition that cannot be
resolved mechanically is an *open question* (recorded with evidence and a
proposed disposition). Owner decisions enter ONLY through explicit
``review-adjudication`` records (never fabricated here); a re-run consumes
them and records the decision inside the affected open questions.

The **output boundary** (§10): ELIGIBLE candidates may carry a
``registration_ready`` representation — a mapping and a STOP marker, NOT a
registration. No ECP-CASE id is assigned, no ground truth is sealed, no
ledger append happens. The engine has no code path to the ledger, the
store, or any model.

Determinism: the review is a pure function of the explicit inputs
(candidates, source text, adjudications, run id, reviewer, reviewed_at
timestamp). No wall-clock, no randomness, no network, no subprocess.
"""

import re
from pathlib import Path

from .canonical import canonical_bytes
from .candidates import (
    SOURCE_FORMAT,
    normalize_text,
    normalize_tokens,
    parse_case_set,
)
from .hashing import hash_document, hash_document_excluding, sha256_hex
from .validate import validate_document
from .versions import PROTOCOL_VERSIONS, version_issues

ENGINE_ID = "ECP-REVIEW-ENGINE-1"
ENGINE_VERSION = "0.4.0"


class ReviewError(Exception):
    """Raised when a review run cannot proceed honestly (bad inputs,
    coverage failure, invalid records — always loud, never silent)."""


class InvalidReviewState(ReviewError):
    """Raised when the engine would need a fourth decision state or an
    out-of-enum input (fail-loud guard)."""


#: Engine behavior profiles (M3-CA0-A): a run recorded by an earlier
#: engine version must remain byte-identically re-derivable by the current
#: toolchain (verification is version-aware). Profile ``0.3.0`` reproduces
#: the exact M3-CA0 question set and never applies amendments; profile
#: ``0.4.0`` adds the adjudication-layer open questions and the case
#: amendment / re-review machinery.
ENGINE_PROFILES = ("0.3.0", "0.4.0")


def profile_versions(engine_profile: str) -> "tuple[str, str, str]":
    """Map an engine profile to the (protocol, schema, engine) versions it
    records on every produced artifact and manifest."""
    if engine_profile not in ENGINE_PROFILES:
        raise InvalidReviewState(
            f"unknown engine profile {engine_profile!r}; "
            f"known: {list(ENGINE_PROFILES)}"
        )
    return (engine_profile, engine_profile, engine_profile)


def profile_has_adjudication_layer(engine_profile: str) -> bool:
    """Whether the profile emits the 0.4.0 adjudication-layer open
    questions (OQ-SPEC-GT-CONFLICT, OQ-SPEC-AUTHORING) and applies case
    amendments."""
    return engine_profile == "0.4.0"

#: Token-set Jaccard similarity at or above which a within-set overlap
#: suspicion is raised (documented engine parameter, recorded in the run).
JACCARD_OVERLAP_THRESHOLD = 0.75

#: Minimum normalized-token length of an answer sentence for the
#: answer-in-task containment detector (shorter sentences are skipped:
#: they false-positive on connective text).
ANSWER_SENTENCE_MIN_TOKENS = 4

#: Minimum normalized-token length of a derivation sentence for the
#: eval-material-in-task detector.
EVAL_SENTENCE_MIN_TOKENS = 6

#: Registry of real-world proper nouns / organizations / known dataset and
#: model names. Registry-driven, honest, deliberately small and
#: extensible: a miss does NOT prove absence of real-world content.
REAL_WORLD_TERMS = (
    "socrates", "plato", "aristotle", "kant", "hegel", "nietzsche",
    "descartes", "shakespeare", "einstein", "newton", "galileo", "tesla",
    "edison", "turing", "darwin", "pythagoras", "euclid",
    "paris", "london", "berlin", "rome", "madrid", "lisbon", "amsterdam",
    "vienna", "prague", "moscow", "kyiv", "istanbul", "cairo", "athens",
    "tokyo", "osaka", "beijing", "shanghai", "seoul", "delhi", "mumbai",
    "boston", "chicago", "seattle", "austin", "dallas",
    "google", "microsoft", "apple", "amazon", "meta", "openai",
    "anthropic", "deepmind", "ibm", "oracle", "nvidia", "tesla",
    "chatgpt", "claude", "gemini", "llama", "bert", "gpt", "glm",
    "imagenet", "mnist", "cifar", "squad", "glue", "superglue",
    "winogrande", "hellaswag", "mmlu", "gsm8k", "truthfulqa", "bigbench",
    "triviaqa", "wikipedia", "stackexchange", "reddit", "arxiv",
)

#: Registry of well-known puzzle / benchmark textual signatures.
KNOWN_PATTERNS = (
    "all men are mortal", "socrates is a man", "monty hall", "three doors",
    "trolley problem", "zebra puzzle", "einstein riddle", "five houses",
    "knights and knaves", "knaves and knights", "river crossing",
    "wolf goat cabbage", "cabbage and wolf", "tower of hanoi",
    "hanoi tower", "blue eyed islanders", "blue eyes puzzle",
    "hardest logic puzzle", "two guards two doors", "heaven and hell doors",
    "100 prisoners", "prisoners and light bulb", "sum and product puzzle",
    "freudenthal", "cheryl birthday", "cheryl s birthday", "gedanken",
)

#: Format label strings that must never appear inside task text
#: (metadata-leakage detector).
METADATA_LABEL_STRINGS = (
    "INTENDED_CORRECT_ANSWER", "DERIVATION:", "DIFFICULTY:",
    "RETRIEVAL_RISK", "AMBIGUITY_RISK", "SELF_REVIEW", "CASE ID:",
    "STRUCTURAL_UNIQUENESS_RATIONALE", "PROPOSED_REASONING_FAMILY",
    "STRUCTURAL_SIGNATURE", "PREMISES:",
)

ADJ_DISPOSITIONS = ("RESOLVE-CLEAN", "ACCEPT-RISK", "CONFIRM-DEFECT", "UPHOLD-OPEN")

GENESIS_HASH = "0" * 64

# Allowed enum values per decision input — anything else aborts the run
# (no fourth state can ever be emitted).
_ALLOWED = {
    "identity_status": ("PASS", "FAIL"),
    "provenance_status": ("COMPLETE", "PARTIAL", "MISSING", "BROKEN"),
    "spec_status": ("SATISFIED", "AMBIGUOUS", "MISSING", "INCOMPLETE"),
    "novelty_status": ("NOVEL_WITHIN_SET", "DUPLICATE", "OVERLAP_SUSPECTED", "UNRESOLVED"),
    "leakage_status": ("CLEAN", "CONFIRMED", "UNRESOLVED"),
    "provenance_integrity_status": ("INTACT", "BROKEN", "UNVERIFIED"),
    "reproducibility_status": ("RECONSTRUCTIBLE", "FAILED"),
    "duplicate_status": (
        "UNIQUE", "EXACT_DUPLICATE", "CANONICAL_DUPLICATE",
        "SOURCE_DUPLICATE", "OVERLAP_SUSPECTED",
    ),
    "decision": ("ELIGIBLE", "REJECTED", "REQUIRES_REVIEW"),
}


# --- text utilities ----------------------------------------------------------


def _sentences(text: str) -> "list[str]":
    """Split text into sentence-ish chunks (period, newline, semicolon)."""
    parts = re.split(r"[.\n;]+", text)
    return [part.strip() for part in parts if part.strip()]


def _task_text(content: dict) -> str:
    return "\n".join(list(content.get("premises", [])) + [content.get("question", "")])


# --- leakage detectors (R5) --------------------------------------------------


def _detect_answer_in_task(content: dict) -> "dict":
    """L1: normalized answer sentences appearing contiguously in the task."""
    task_norm = " " + " ".join(normalize_tokens(_task_text(content))) + " "
    for answer in content.get("intended_correct_answers", []):
        value = answer.get("value", "")
        candidates = [value] + _sentences(value)
        for chunk in candidates:
            tokens = normalize_tokens(chunk)
            if len(tokens) < ANSWER_SENTENCE_MIN_TOKENS:
                continue
            needle = " " + " ".join(tokens) + " "
            if needle in task_norm:
                return {
                    "detector": "L1-ANSWER-IN-TASK",
                    "result": "FLAGGED",
                    "evidence": f"answer sentence {chunk[:80]!r} appears in premises/question",
                }
    return {"detector": "L1-ANSWER-IN-TASK", "result": "CLEAN"}


def _detect_eval_in_task(content: dict) -> "dict":
    """L2: derivation sentences appearing contiguously in the task, where the
    sentence is NOT explainable as a premise/question quotation.

    Derivations legitimately cite premises; a derivation sentence that
    appears inside an individual premise is a citation, not leakage.
    Derivation content inside the QUESTION is genuine evaluation-material
    leakage (the question must not carry derivation text), so the citation
    exclusion covers premises only."""
    normalized_units = [
        " " + " ".join(normalize_tokens(p)) + " " for p in content.get("premises", [])
    ]
    task_norm = " " + " ".join(normalize_tokens(_task_text(content))) + " "
    for derivation in content.get("derivations", []):
        for sentence in _sentences(derivation.get("raw", "")):
            tokens = normalize_tokens(sentence)
            if len(tokens) < EVAL_SENTENCE_MIN_TOKENS:
                continue
            needle = " " + " ".join(tokens) + " "
            if needle not in task_norm:
                continue
            if any(needle in unit for unit in normalized_units):
                continue  # premise/question citation, not leakage
            return {
                "detector": "L2-EVAL-IN-TASK",
                "result": "FLAGGED",
                "evidence": f"derivation sentence {sentence[:80]!r} appears in premises/question without being a premise citation",
            }
    return {"detector": "L2-EVAL-IN-TASK", "result": "CLEAN"}


def _detect_real_world(content: dict) -> "dict":
    """L3: registry-based real-world entity detection (honest small registry)."""
    task_tokens = set(normalize_tokens(_task_text(content)))
    hits = sorted(term for term in REAL_WORLD_TERMS if term in task_tokens)
    if hits:
        return {
            "detector": "L3-REAL-WORLD",
            "result": "FLAGGED",
            "evidence": f"real-world registry terms present: {', '.join(hits)}",
        }
    return {"detector": "L3-REAL-WORLD", "result": "CLEAN"}


def _detect_known_pattern(content: dict) -> "dict":
    """L4: registry-based known puzzle/benchmark signature detection."""
    task_norm = normalize_text(_task_text(content))
    hits = sorted(
        pattern for pattern in KNOWN_PATTERNS if pattern in task_norm
    )
    if hits:
        return {
            "detector": "L4-KNOWN-PATTERN",
            "result": "FLAGGED",
            "evidence": f"known pattern signatures present: {', '.join(hits)}",
        }
    return {"detector": "L4-KNOWN-PATTERN", "result": "CLEAN"}


def _detect_metadata_in_task(candidate: dict) -> "dict":
    """L5: format labels / candidate id leaking into task text (raw,
    case-sensitive containment — precise, no false positives)."""
    task = _task_text(candidate.get("content", {}))
    case_id = candidate.get("source", {}).get("case_id", "")
    needles = list(METADATA_LABEL_STRINGS)
    if case_id:
        needles.append(case_id)
    hits = [needle for needle in needles if needle in task]
    if hits:
        return {
            "detector": "L5-METADATA",
            "result": "FLAGGED",
            "evidence": f"metadata strings present in task text: {', '.join(hits)}",
        }
    return {"detector": "L5-METADATA", "result": "CLEAN"}


def _check_leakage(candidate: dict) -> "tuple[str, list[dict]]":
    """Run all leakage detectors; derive the leakage status.

    CONFIRMED (disqualifying): L1/L2 positive (answer or eval material
    actually inside the task). UNRESOLVED: L3/L4/L5 flagged (risk —
    human weighing required). CLEAN otherwise (external contamination
    remains a separate open question).
    """
    detectors = [
        _detect_answer_in_task(candidate["content"]),
        _detect_eval_in_task(candidate["content"]),
        _detect_real_world(candidate["content"]),
        _detect_known_pattern(candidate["content"]),
        _detect_metadata_in_task(candidate),
    ]
    confirmed = any(
        d["result"] == "FLAGGED" and d["detector"].startswith(("L1", "L2"))
        for d in detectors
    )
    if confirmed:
        return "CONFIRMED", detectors
    if any(d["result"] == "FLAGGED" for d in detectors):
        return "UNRESOLVED", detectors
    return "CLEAN", detectors


# --- specification completeness (R3) -----------------------------------------


def _check_specification(content: dict, candidate: dict) -> "tuple[str, list[str]]":
    """Specification findings. Findings are reason-code level details;
    the mapping from findings to decisions is the documented rule in
    :func:`_decide` (never inferred here)."""
    findings: "list[str]" = []
    answers = content.get("intended_correct_answers", [])
    derivations = content.get("derivations", [])

    if not answers:
        findings.append("SPEC-MISSING-ANSWER")
    if not derivations:
        findings.append("SPEC-MISSING-DERIVATION")

    distinct_answers = {
        normalize_text(a.get("value", "")) for a in answers
    } - {""}
    distinct_derivations = {
        normalize_text(d.get("raw", "")) for d in derivations
    } - {""}

    if len(distinct_answers) > 1:
        findings.append(
            "SPEC-AMBIGUOUS-GT: conflicting INTENDED_CORRECT_ANSWER values "
            f"({len(distinct_answers)} distinct authored answers retained)"
        )
    if len(distinct_derivations) > 1:
        findings.append(
            "SPEC-AMBIGUOUS-GT: conflicting DERIVATION versions "
            f"({len(distinct_derivations)} distinct authored derivations retained)"
        )
    if len(distinct_answers) == 1 and len(answers) > 1:
        findings.append(
            "SPEC-DUPLICATE-GT: identical answer duplicated across "
            f"{len(answers)} blocks (ground-truth document needs consolidation)"
        )
    if (
        len(distinct_derivations) == 1
        and len(derivations) > 1
        and len(distinct_answers) <= 1
        and len(answers) <= 1
    ):
        findings.append(
            "SPEC-DUPLICATE-GT: identical derivation duplicated across "
            f"{len(derivations)} blocks"
        )

    self_review = content.get("self_review", {})
    negative = sorted(
        key for key, value in self_review.items() if value == "No"
    )
    if negative:
        findings.append(
            "SPEC-SELFREVIEW-NEGATIVE: author self-review reports No for "
            f"{', '.join(negative)}"
        )

    authoring = candidate.get("registration_authoring") or {}
    for field in ("constraints", "success_criterion", "verification_rule"):
        if field not in authoring or not authoring.get(field):
            findings.append(f"SPEC-REG-AUTHORING-MISSING: {field} not authored")

    if not findings:
        return "SATISFIED", []
    if any(f.startswith("SPEC-AMBIGUOUS-GT") for f in findings):
        return "AMBIGUOUS", findings
    if any(
        f.startswith(
            ("SPEC-MISSING-", "SPEC-REG-AUTHORING-MISSING")
        )
        for f in findings
    ):
        return "INCOMPLETE", findings
    return "AMBIGUOUS", findings


# --- novelty / duplicates (R4, §7) -------------------------------------------


def _canonical_fingerprint(content: dict) -> str:
    """Lossy canonical-equivalence fingerprint (whitespace/case/punctuation
    insensitive) over the task + answers."""
    material = {
        "premises": [normalize_text(p) for p in content.get("premises", [])],
        "question": normalize_text(content.get("question", "")),
        "answers": [
            normalize_text(a.get("value", ""))
            for a in content.get("intended_correct_answers", [])
        ],
    }
    return hash_document(material)


def _task_token_set(content: dict) -> "set[str]":
    return set(normalize_tokens(_task_text(content)))


def _jaccard(a: "set[str]", b: "set[str]") -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _check_duplicate(candidate: dict, prior: "list[dict]") -> "tuple[dict, str, list[str]]":
    """Duplicate detection against previously reviewed candidates.

    Returns (duplicate_finding, novelty_status, overlap_evidence).
    Duplicates are never deleted; evidence is retained.
    """
    content = candidate["content"]
    evidence: "list[str]" = []
    for other in prior:
        if other["content_hash"] == candidate["content_hash"]:
            return (
                {
                    "status": "EXACT_DUPLICATE",
                    "of_candidate_id": other["candidate_id"],
                    "evidence": "identical content_hash (byte-identical canonical content)",
                },
                "DUPLICATE",
                ["exact content duplicate of " + other["candidate_id"]],
            )
        if _canonical_fingerprint(other["content"]) == _canonical_fingerprint(content):
            return (
                {
                    "status": "CANONICAL_DUPLICATE",
                    "of_candidate_id": other["candidate_id"],
                    "evidence": "identical canonical-equivalence fingerprint (same case modulo whitespace/case/punctuation)",
                },
                "DUPLICATE",
                ["canonical-equivalent duplicate of " + other["candidate_id"]],
            )
        same_source = (
            other.get("source", {}).get("source_document", {}).get("sha256")
            == candidate.get("source", {}).get("source_document", {}).get("sha256")
            and other.get("source", {}).get("case_id")
            == candidate.get("source", {}).get("case_id")
        )
        if same_source:
            return (
                {
                    "status": "SOURCE_DUPLICATE",
                    "of_candidate_id": other["candidate_id"],
                    "evidence": "same source document and same source case id",
                },
                "DUPLICATE",
                ["source duplicate of " + other["candidate_id"]],
            )

    signature = normalize_text(content.get("structural_signature", ""))
    for other in prior:
        other_signature = normalize_text(other["content"].get("structural_signature", ""))
        if signature and other_signature and signature == other_signature:
            evidence.append(
                f"STRUCTURAL-SIGNATURE collision with {other['candidate_id']} "
                f"({content.get('structural_signature', '')[:60]!r})"
            )
    for other in prior:
        score = _jaccard(_task_token_set(content), _task_token_set(other["content"]))
        if score >= JACCARD_OVERLAP_THRESHOLD:
            evidence.append(
                f"TOKEN-JACCARD {score:.3f} >= {JACCARD_OVERLAP_THRESHOLD} with "
                f"{other['candidate_id']}"
            )

    if evidence:
        return (
            {
                "status": "OVERLAP_SUSPECTED",
                "evidence": "; ".join(evidence[:5]),
            },
            "OVERLAP_SUSPECTED",
            evidence,
        )
    return ({"status": "UNIQUE"}, "NOVEL_WITHIN_SET", [])


# --- provenance (R2, R6) ------------------------------------------------------


def _check_provenance_integrity(
    candidate: dict,
    source_text: "str | None",
    source_sha: "str | None",
    parsed_source_cases: "dict[str, dict] | None",
    amendment_record: "dict | None" = None,
) -> "tuple[str, bool, list[str]]":
    """R6: candidate → source → transformation → canonical artifact chain.

    For a derived v2 candidate (M3-CA0-A), the chain extends through the
    amendment record: source → v1 (raw block, byte-exact) → amendment
    (two-phase-disclosure hashes) → v2 content (recomputed at derivation).

    Returns (status, chain_verified, findings).
    """
    findings: "list[str]" = []
    source = candidate.get("source", {})
    declared_sha = source.get("source_document", {}).get("sha256")

    if source_text is None:
        return "UNVERIFIED", False, [
            "source document not supplied to this run; chain not verifiable here"
        ]

    if declared_sha != source_sha:
        findings.append(
            f"declared source sha256 {declared_sha!r} != run source {source_sha!r}"
        )
        return "BROKEN", False, findings

    if parsed_source_cases is None:
        findings.append("source document unparseable")
        return "BROKEN", False, findings

    case_id = source.get("case_id")
    parsed_case = parsed_source_cases.get(case_id)
    if parsed_case is None:
        findings.append(f"source case id {case_id!r} not found in source document")
        return "BROKEN", False, findings

    if parsed_case.get("raw_block") != candidate.get("raw_block"):
        findings.append(
            "raw_block differs from the source document block at the declared "
            "position (candidate → source chain broken)"
        )
        return "BROKEN", False, findings

    # 0.4.0 amendment-aware extension (M3-CA0-A §8): for a derived v2
    # candidate the chain is source → v1 (raw, byte-exact above) →
    # amendment record (two-phase-disclosure evidence) → v2 content.
    linkage = candidate.get("amendment")
    if linkage is not None:
        if amendment_record is None:
            findings.append(
                "candidate carries an amendment linkage but no amendment "
                "record was supplied to this run (chain not verifiable)"
            )
            return "BROKEN", False, findings
        if amendment_record.get("amendment_id") != linkage.get("amendment_id"):
            findings.append(
                "supplied amendment record does not match the candidate's "
                "amendment linkage id"
            )
            return "BROKEN", False, findings
        if amendment_record.get("amendment_hash") != linkage.get("amendment_hash"):
            findings.append(
                "supplied amendment record hash != candidate linkage hash "
                "(amendment → v2 chain broken)"
            )
            return "BROKEN", False, findings
        if amendment_record.get("prior", {}).get("content_hash") != linkage.get(
            "prior_content_hash"
        ):
            findings.append(
                "amendment prior content_hash != candidate linkage prior hash "
                "(v1 → amendment chain broken)"
            )
            return "BROKEN", False, findings
        # the retained authored material (premises/question) must equal the
        # source block: consolidation touches GT blocks only — everything
        # the raw_block carries is verbatim from the source, which the
        # comparison above already proves.

    # transformation history: non-decreasing timestamps
    history = candidate.get("provenance", {}).get("transformation_history", [])
    times = [event.get("at", "") for event in history]
    if times != sorted(times):
        findings.append("transformation history timestamps are not non-decreasing")
        return "BROKEN", False, findings

    return "INTACT", True, findings


# --- open questions + adjudications (§9) ---------------------------------------


def _owner_decision(adjudications: "list[dict]", code: str, candidate_id: str) -> "dict | None":
    """The effective adjudication for (question code, candidate).

    When several adjudications match, the one with the latest ``at``
    (ties broken by adjudication_id — deterministic) applies; every
    matched id is recorded by the caller (override semantics, documented).
    """
    matching = [
        adj
        for adj in adjudications
        if adj.get("applies_to", {}).get("question_code") == code
        and (
            not adj.get("applies_to", {}).get("candidate_id")
            or adj["applies_to"]["candidate_id"] == candidate_id
        )
    ]
    if not matching:
        return None
    matching.sort(
        key=lambda adj: (adj.get("at", ""), adj.get("adjudication_id", ""))
    )
    return matching[-1]


def _build_open_questions(
    candidate: dict,
    spec_findings: "list[str]",
    leakage_status: str,
    provenance_status: str,
    provenance_integrity_status: str,
    adjudications: "list[dict]",
    include_adjudication_layer: bool = False,
) -> "tuple[list[dict], list[str], bool, list[str]]":
    """Construct the open questions (the human seam).

    Returns (open_questions, applied_adjudication_ids,
    has_unresolved_critical, confirmed_defect_codes).
    """
    questions: "list[dict]" = []
    applied: "list[str]" = []
    confirmed_defects: "list[str]" = []
    unresolved_critical = False

    def add(code: str, category: str, question: str, evidence: str, critical: bool):
        nonlocal unresolved_critical
        owner_decision = _owner_decision(adjudications, code, candidate["candidate_id"])
        entry = {
            "question_id": f"OQ-{len(questions) + 1}",
            "category": category,
            "code": code,
            "question": question,
            "evidence": evidence,
            "critical": critical,
            "proposed_disposition": "OWNER_ADJUDICATION_REQUIRED",
            "owner_decision": None,
        }
        if owner_decision is not None:
            adj_id = owner_decision["adjudication_id"]
            if adj_id not in applied:
                applied.append(adj_id)
            disposition = owner_decision["disposition"]
            if disposition not in ADJ_DISPOSITIONS:
                raise InvalidReviewState(
                    f"adjudication {adj_id} disposition {disposition!r} outside "
                    f"allowed set {ADJ_DISPOSITIONS}"
                )
            entry["owner_decision"] = {
                "adjudication_id": adj_id,
                "disposition": disposition,
                "recorded_by": owner_decision.get("owner_identity", ""),
                "at": owner_decision.get("at", ""),
                "rationale": owner_decision.get("rationale", ""),
            }
            if disposition == "CONFIRM-DEFECT":
                confirmed_defects.append(code)
            elif disposition == "UPHOLD-OPEN":
                if critical:
                    unresolved_critical = True
            # RESOLVE-CLEAN / ACCEPT-RISK: resolved — does not block
        elif critical:
            unresolved_critical = True
        questions.append(entry)

    # --- always-present external questions (cannot be established
    # mechanically at CA0; guessing is forbidden) ---
    add(
        "OQ-NOV-EXTERNAL",
        "NOVELTY",
        "Is the candidate novel with respect to external corpora (published "
        "benchmarks, training data)? This cannot be established mechanically "
        "at CA0 (model invocation and retrieval are forbidden); a local hash "
        "difference is NOT a novelty claim.",
        "external novelty status: NOT_ESTABLISHABLE_MECHANICALLY",
        True,
    )
    add(
        "OQ-LKG-CONTAMINATION",
        "LEAKAGE",
        "Is the case free of training-data contamination? Undecidable "
        "mechanically at CA0; requires owner adjudication.",
        "no corpus access available to the review engine",
        True,
    )

    # --- conditional questions ---
    flags = candidate.get("provenance", {}).get("source_report_flags", []) or []
    if "model-family-overlap" in flags:
        add(
            "OQ-LKG-SOURCE-CONTAMINATION",
            "LEAKAGE",
            "The authoring model family overlaps the project's execution "
            "agent family (flagged by the source report). Does the owner "
            "accept this authorship provenance for registration eligibility?",
            "source_report_flags include 'model-family-overlap'",
            True,
        )
    if provenance_status == "PARTIAL":
        add(
            "OQ-PROV-PARTIAL",
            "PROVENANCE",
            "Provenance is honest but PARTIAL (fields recorded NOT AVAILABLE). "
            "Does the owner accept this provenance completeness level?",
            "provenance_completeness: PARTIAL "
            f"({len(candidate.get('provenance', {}).get('provenance_completeness', {}).get('not_available', []))} "
            "fields not available)",
            True,
        )
    if provenance_status == "MISSING":
        add(
            "OQ-PROV-MISSING",
            "PROVENANCE",
            "Provenance substance is declared MISSING for this candidate.",
            "provenance_completeness: MISSING",
            True,
        )
    if provenance_integrity_status == "UNVERIFIED":
        add(
            "OQ-PROV-CHAIN-UNVERIFIED",
            "PROVENANCE",
            "The candidate → source chain could not be verified in this run "
            "(source document not supplied).",
            "provenance_integrity: UNVERIFIED",
            True,
        )
    if leakage_status == "UNRESOLVED":
        add(
            "OQ-LKG-FLAGGED",
            "LEAKAGE",
            "A leakage detector raised a risk flag that requires human "
            "weighing (not a confirmed answer/eval leak).",
            "leakage status: UNRESOLVED (see detectors)",
            True,
        )

    # --- 0.4.0 adjudication-layer questions (M3-CA0-A §4/§5; profile-
    # gated so that 0.3.0-era runs re-derive byte-identically). Emitted
    # AFTER the 0.3.0 question set so earlier question ids never shift. ---
    if include_adjudication_layer:
        gt_conflict = any(
            f.startswith(("SPEC-AMBIGUOUS-GT", "SPEC-DUPLICATE-GT"))
            for f in spec_findings
        )
        if gt_conflict:
            add(
                "OQ-SPEC-GT-CONFLICT",
                "SPECIFICATION",
                "The authored ground-truth document carries multiple GT "
                "blocks (conflicting answers and/or derivations, flagged "
                "by the specification-completeness checks). Can the "
                "conflict be resolved from the preserved case material "
                "(premises + retained derivations) without "
                "outcome-dependent reasoning — or is it a specification "
                "defect / genuine ambiguity requiring rejection?",
                "; ".join(
                    f for f in spec_findings
                    if f.startswith(("SPEC-AMBIGUOUS-GT", "SPEC-DUPLICATE-GT"))
                ),
                True,
            )
        authoring_missing = any(
            f.startswith("SPEC-REG-AUTHORING-MISSING") for f in spec_findings
        )
        if authoring_missing:
            add(
                "OQ-SPEC-AUTHORING",
                "SPECIFICATION",
                "Registration-contract fields (constraints, "
                "success_criterion, verification_rule) were not authored "
                "for this candidate. Can they be supplied as a legitimate "
                "versioned case amendment WITHOUT retrospective "
                "reconstruction or outcome-dependent information — or "
                "must they be authored in a separately authorized "
                "registration-authoring stage?",
                "; ".join(
                    f for f in spec_findings
                    if f.startswith("SPEC-REG-AUTHORING-MISSING")
                ),
                True,
            )

    return questions, applied, unresolved_critical, confirmed_defects


# --- forwarded flags (later stages, never resolved here) ----------------------


def _forwarded_flags(candidate: dict, spec_findings: "list[str]") -> "list[dict]":
    flags: "list[dict]" = [
        {
            "code": "FWD-GT-VERIFICATION",
            "note": "Ground-truth correctness verification is a LATER pipeline "
            "stage (after review, before registration); not performed at CA0.",
            "target_stage": "ground-truth-verification",
        }
    ]
    authoring = candidate.get("registration_authoring") or {}
    missing = [
        field
        for field in ("constraints", "success_criterion", "verification_rule")
        if field not in authoring or not authoring.get(field)
    ]
    if missing:
        flags.append(
            {
                "code": "FWD-REG-AUTHORING",
                "note": "Registration-contract fields must be AUTHORED (never "
                f"inferred): {', '.join(missing)}.",
                "target_stage": "registration-authoring",
            }
        )
    candidate_flags = candidate.get("provenance", {}).get("candidate_flags", []) or []
    if "nondeterminate-answer-design" in candidate_flags:
        flags.append(
            {
                "code": "FWD-GT-NONDETERMINATE",
                "note": "Source report flags this case as deliberately "
                "non-determinate ('cannot be determined' design); the "
                "ground-truth verification stage must confirm this reading.",
                "target_stage": "ground-truth-verification",
            }
        )
    return flags


# --- decision logic (§6) -------------------------------------------------------


def _decide(
    dimensions: dict,
    duplicate: dict,
    unresolved_critical: bool,
    confirmed_defects: "list[str]",
) -> "tuple[str, list[str]]":
    """The explicit three-state decision rule.

    REJECTED: a disqualifying condition is positively established.
    REQUIRES_REVIEW: an important condition cannot be resolved mechanically
    (or awaits owner adjudication).
    ELIGIBLE: all mandatory gates pass and no unresolved critical issue
    exists. Ambiguous inputs abort the run (never a fourth state).
    """
    # --- fail loud on any out-of-enum decision input ---
    if dimensions["identity"]["status"] not in _ALLOWED["identity_status"]:
        raise InvalidReviewState("identity status outside allowed enum")
    if dimensions["provenance"]["status"] not in _ALLOWED["provenance_status"]:
        raise InvalidReviewState("provenance status outside allowed enum")
    if dimensions["specification"]["status"] not in _ALLOWED["spec_status"]:
        raise InvalidReviewState("specification status outside allowed enum")
    if dimensions["novelty"]["status"] not in _ALLOWED["novelty_status"]:
        raise InvalidReviewState("novelty status outside allowed enum")
    if dimensions["leakage"]["status"] not in _ALLOWED["leakage_status"]:
        raise InvalidReviewState("leakage status outside allowed enum")
    if dimensions["provenance_integrity"]["status"] not in _ALLOWED["provenance_integrity_status"]:
        raise InvalidReviewState("provenance_integrity status outside allowed enum")
    if dimensions["reproducibility"]["status"] not in _ALLOWED["reproducibility_status"]:
        raise InvalidReviewState("reproducibility status outside allowed enum")
    if duplicate["status"] not in _ALLOWED["duplicate_status"]:
        raise InvalidReviewState("duplicate status outside allowed enum")

    reasons: "list[str]" = []

    # --- REJECTED: positively established disqualifiers ---
    if dimensions["identity"]["status"] == "FAIL":
        reasons.append("R1-HASH-MISMATCH")
    if dimensions["provenance"]["status"] == "BROKEN":
        reasons.append("R2-PROV-BROKEN-DECLARED")
    if dimensions["provenance_integrity"]["status"] == "BROKEN":
        reasons.append("R6-PROV-BROKEN-CHAIN")
    if dimensions["leakage"]["status"] == "CONFIRMED":
        reasons.append("R5-LKG-CONFIRMED")
    if dimensions["reproducibility"]["status"] == "FAILED":
        reasons.append("R7-REPRO-BROKEN")
    if duplicate["status"] in ("EXACT_DUPLICATE", "CANONICAL_DUPLICATE", "SOURCE_DUPLICATE"):
        reasons.append("R4-DUP-" + duplicate["status"])
    if confirmed_defects:
        reasons.append("OQ-CONFIRMED-DEFECT: " + ", ".join(sorted(confirmed_defects)))

    if reasons:
        return "REJECTED", reasons

    # --- REQUIRES_REVIEW: mechanically unresolved important conditions ---
    if dimensions["specification"]["status"] in ("AMBIGUOUS", "INCOMPLETE", "MISSING"):
        reasons.extend(
            finding if ":" in finding else finding
            for finding in dimensions["specification"]["findings"]
        )
    if dimensions["provenance"]["status"] == "MISSING":
        reasons.append("OQ-PROV-MISSING")
    if dimensions["provenance"]["status"] == "PARTIAL":
        reasons.append("OQ-PROV-PARTIAL")
    if dimensions["provenance_integrity"]["status"] == "UNVERIFIED":
        reasons.append("OQ-PROV-CHAIN-UNVERIFIED")
    if dimensions["novelty"]["status"] == "OVERLAP_SUSPECTED":
        reasons.append("R4-NOV-OVERLAP-SUSPECTED")
    if dimensions["leakage"]["status"] == "UNRESOLVED":
        reasons.append("OQ-LKG-FLAGGED")
    if unresolved_critical:
        reasons.append("OQ-UNRESOLVED-CRITICAL")

    if reasons:
        return "REQUIRES_REVIEW", reasons

    return "ELIGIBLE", ["ELIGIBLE-ALL-GATES-PASS"]


# --- artifact construction ------------------------------------------------------


def _registration_ready(candidate: dict, forwarded: "list[dict]") -> "dict | None":
    """The §10 registration-ready representation (ELIGIBLE only). This is a
    mapping plus a STOP marker — NOT a registration: no ECP-CASE id, no
    sealed ground truth, no ledger append."""
    outstanding = [
        "ECP-CASE id assignment (registration ceremony)",
        "case_version proposal (registration ceremony)",
        "ground-truth sealing into the protected store (registration ceremony)",
        "registration ledger append — requires separate owner authorization",
    ]
    for flag in forwarded:
        if flag["code"] == "FWD-GT-VERIFICATION":
            outstanding.append("ground-truth verification stage (before registration)")
    return {
        "status": "READY-FOR-REGISTRATION-CEREMONY",
        "candidate_id": candidate["candidate_id"],
        "content_hash": candidate["content_hash"],
        "field_mapping": {
            "premises": "case.input.prompt (composed at the registration ceremony)",
            "question": "case.input.prompt (composed at the registration ceremony)",
            "intended_answer": "ground-truth.expected_answer.value (sealed in the protected store at the registration ceremony)",
            "derivation": "ground-truth.derivation (sealed in the protected store at the registration ceremony)",
            "difficulty": "case.difficulty",
            "family": "case.proposed_reasoning_family",
            "structural_signature": "case.structural_signature",
        },
        "requirements_outstanding": outstanding,
        "boundary": "STOP-BEFORE-REGISTRATION",
    }


def review_candidate(
    candidate: dict,
    prior: "list[dict]",
    source_text: "str | None",
    source_sha: "str | None",
    parsed_source_cases: "dict[str, dict] | None",
    adjudications: "list[dict]",
    run_id: str,
    reviewed_at: str,
    operator: str,
    entry_index: int,
    prev_artifact_hash: str,
    amendment_record: "dict | None" = None,
    engine_profile: str = ENGINE_VERSION,
) -> "tuple[dict, str]":
    """Review one candidate; returns (artifact, artifact_hash).

    ``candidate`` may be a derived v2 view (M3-CA0-A): then
    ``amendment_record`` must be the amendment it was derived from and the
    artifact carries the amendment linkage + disclosure value.

    A REJECTED intake is still materialized as a full artifact with the
    rejection evidence (no silent discards).
    """
    protocol_v, schema_v, engine_v = profile_versions(engine_profile)

    # --- intake validation (schema + versions) ---
    schema_issues = validate_document(candidate, "case-candidate")
    version_problems = version_issues(candidate)
    if schema_issues or version_problems:
        content = candidate.get("content")
        if not isinstance(content, dict):
            content = {}
        dimensions = _empty_dimensions()
        dimensions["specification"] = {
            "status": "INCOMPLETE",
            "findings": ["INTAKE-SCHEMA-INVALID"],
        }
        dimensions["reproducibility"]["reconstruction_hash"] = hash_document(content)
        decision, reasons = "REJECTED", [
            "INTAKE-SCHEMA-INVALID: " + "; ".join((schema_issues + version_problems)[:5])
        ]
        artifact = _assemble_artifact(
            candidate=candidate,
            content=content,
            dimensions=dimensions,
            duplicate={"status": "UNIQUE"},
            open_questions=[],
            forwarded=[
                {
                    "code": "FWD-INTAKE-INVALID",
                    "note": "intake record failed schema/version validation; "
                    "raw record retained as evidence",
                    "target_stage": "registration-authoring",
                }
            ],
            adjudications_applied=[],
            reviewed_at=reviewed_at,
            operator=operator,
            run_id=run_id,
            entry_index=entry_index,
            prev_artifact_hash=prev_artifact_hash,
            decision=decision,
            reason_codes=reasons,
            registration_ready=None,
            amendment_record=amendment_record,
            protocol_version=protocol_v,
            schema_version=schema_v,
            engine_version=engine_v,
        )
        return artifact, artifact["artifact_hash"]

    if candidate.get("content_class") == "format-illustration":
        raise ReviewError(
            f"candidate {candidate.get('candidate_id', '?')!r} is "
            "content_class 'format-illustration': public illustration "
            "material cannot be reviewed (real review material only)"
        )

    content = candidate["content"]

    # --- R1 identity ---
    recomputed = hash_document(content)
    identity_ok = recomputed == candidate["content_hash"]
    identity = {
        "status": "PASS" if identity_ok else "FAIL",
        "content_hash_verified": identity_ok,
        "canonicalization": "ECP-CANONICAL-JSON-1.0",
    }

    # --- R2 provenance ---
    provenance = candidate.get("provenance", {})
    completeness = provenance.get("provenance_completeness", {})
    provenance_block = {
        "status": completeness.get("status", "MISSING"),
        "not_available": completeness.get("not_available", []),
        "source_report_flags": provenance.get("source_report_flags", []),
    }

    # --- R6 provenance integrity ---
    pi_status, chain_verified, chain_findings = _check_provenance_integrity(
        candidate, source_text, source_sha, parsed_source_cases, amendment_record
    )
    provenance_integrity = {
        "status": pi_status,
        "chain_verified": chain_verified,
        "chain_findings": chain_findings,
    }

    # --- R3 specification ---
    spec_status, spec_findings = _check_specification(content, candidate)
    specification = {"status": spec_status, "findings": spec_findings}

    # --- R4/R7 duplicates + within-set novelty ---
    duplicate, novelty_status, overlap_evidence = _check_duplicate(candidate, prior)
    novelty = {
        "status": novelty_status,
        "within_set": {
            "distinct_from_prior": novelty_status == "NOVEL_WITHIN_SET",
            "overlap_evidence": overlap_evidence,
        },
        "external": "NOT_ESTABLISHABLE_MECHANICALLY",
    }

    # --- R5 leakage ---
    leakage_status, detectors = _check_leakage(candidate)
    leakage = {"status": leakage_status, "detectors": detectors}

    # --- R7 reproducibility (embedded snapshot) ---
    reconstruction_hash = hash_document(content)
    reproducibility = {
        "status": "RECONSTRUCTIBLE" if reconstruction_hash == candidate["content_hash"] else "FAILED",
        "reconstruction_hash": reconstruction_hash,
    }

    dimensions = {
        "identity": identity,
        "provenance": provenance_block,
        "specification": specification,
        "novelty": novelty,
        "leakage": leakage,
        "provenance_integrity": provenance_integrity,
        "reproducibility": reproducibility,
    }

    # --- open questions (the human seam) + adjudications ---
    questions, applied, unresolved_critical, confirmed_defects = _build_open_questions(
        candidate,
        spec_findings,
        leakage_status,
        provenance_block["status"],
        pi_status,
        adjudications,
        include_adjudication_layer=profile_has_adjudication_layer(engine_profile),
    )
    forwarded = _forwarded_flags(candidate, spec_findings)

    decision, reasons = _decide(
        dimensions, duplicate, unresolved_critical, confirmed_defects
    )

    registration_ready = (
        _registration_ready(candidate, forwarded) if decision == "ELIGIBLE" else None
    )

    artifact = _assemble_artifact(
        candidate=candidate,
        content=content,
        dimensions=dimensions,
        duplicate=duplicate,
        open_questions=questions,
        forwarded=forwarded,
        adjudications_applied=sorted(set(applied)),
        reviewed_at=reviewed_at,
        operator=operator,
        run_id=run_id,
        entry_index=entry_index,
        prev_artifact_hash=prev_artifact_hash,
        decision=decision,
        reason_codes=reasons,
        registration_ready=registration_ready,
        amendment_record=amendment_record,
        protocol_version=protocol_v,
        schema_version=schema_v,
        engine_version=engine_v,
    )
    return artifact, artifact["artifact_hash"]


def _empty_dimensions() -> dict:
    return {
        "identity": {
            "status": "FAIL",
            "content_hash_verified": False,
            "canonicalization": "ECP-CANONICAL-JSON-1.0",
        },
        "provenance": {"status": "MISSING", "not_available": [], "source_report_flags": []},
        "specification": {"status": "INCOMPLETE", "findings": []},
        "novelty": {
            "status": "UNRESOLVED",
            "within_set": {"distinct_from_prior": False, "overlap_evidence": []},
            "external": "NOT_ESTABLISHABLE_MECHANICALLY",
        },
        "leakage": {"status": "UNRESOLVED", "detectors": []},
        "provenance_integrity": {"status": "UNVERIFIED", "chain_verified": False, "chain_findings": []},
        "reproducibility": {"status": "FAILED", "reconstruction_hash": GENESIS_HASH},
    }


def _assemble_artifact(
    candidate: dict,
    content: dict,
    dimensions: dict,
    duplicate: dict,
    open_questions: "list[dict]",
    forwarded: "list[dict]",
    adjudications_applied: "list[str]",
    reviewed_at: str,
    operator: str,
    run_id: str,
    entry_index: int,
    prev_artifact_hash: str,
    decision: str,
    reason_codes: "list[str]",
    registration_ready: "dict | None",
    amendment_record: "dict | None" = None,
    protocol_version: str = "0.4.0",
    schema_version: str = "0.4.0",
    engine_version: str = ENGINE_VERSION,
) -> dict:
    # sanitize identity fields: an invalid intake may carry unusable values,
    # but the produced artifact itself must remain schema-valid and
    # self-consistent (the rejection evidence lives in reason_codes and the
    # retained raw intake record).
    candidate_id = candidate.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        candidate_id = "ECP-CAND-UNKNOWN"
    source_case_id = candidate.get("source", {}).get("case_id")
    if not isinstance(source_case_id, str) or not source_case_id:
        source_case_id = "UNKNOWN"
    content_hash = candidate.get("content_hash")
    if not isinstance(content_hash, str) or not re.fullmatch(
        r"[0-9a-f]{64}", content_hash
    ):
        content_hash = hash_document(content)

    artifact = {
        "ecp_object": "case-review",
        "content_class": "review",
        "review_id": f"ECP-REVIEW-{entry_index:06d}",
        "run_id": run_id,
        "entry_index": entry_index,
        "candidate_id": candidate_id,
        "source_case_id": source_case_id,
        "content_hash": content_hash,
        "candidate_content": content,
        "review_dimensions": dimensions,
        "duplicate": duplicate,
        "open_questions": open_questions,
        "forwarded_flags": forwarded,
        "adjudications_applied": adjudications_applied,
        "reviewer": {
            "kind": "deterministic-pipeline",
            "pipeline": ENGINE_ID,
            "engine_version": engine_version,
            "operator": operator,
        },
        "reviewed_at": reviewed_at,
        "decision": decision,
        "reason_codes": reason_codes,
        "registration_ready": registration_ready,
        "protocol_version": protocol_version,
        "schema_version": schema_version,
        "prev_artifact_hash": prev_artifact_hash,
    }
    if amendment_record is not None:
        linkage = candidate.get("amendment") or {}
        disclosure = (amendment_record.get("representation_bias_disclosure") or {}).get(
            "value"
        )
        artifact["amendment"] = {
            "amendment_id": amendment_record.get("amendment_id"),
            "amendment_hash": amendment_record.get("amendment_hash"),
            "case_version": candidate.get("case_version", 2),
            "prior_case_version": linkage.get("prior_case_version", 1),
            "prior_content_hash": linkage.get("prior_content_hash"),
            "representation_bias_disclosure": disclosure,
        }
    artifact["artifact_hash"] = hash_document_excluding(artifact, "artifact_hash")
    return artifact


# --- the run -----------------------------------------------------------------


def run_review(
    candidates: "list[dict]",
    run_id: str,
    reviewed_at: str,
    operator: str,
    source_text: "str | None" = None,
    source_label: "str | None" = None,
    adjudications: "list[dict] | None" = None,
    amendments: "list[dict] | None" = None,
    engine_profile: "str | None" = None,
    lineage: "dict | None" = None,
) -> dict:
    """Run the review over *candidates* (intake order = list order).

    M3-CA0-A (0.4.0 profile): *amendments* are validated (two-phase
    disclosure evidence included) and applied deterministically — an
    amended candidate is reviewed as its derived v2 view with full
    re-review (§8; nothing inherits eligibility). *lineage* records the
    prior preserved run this run re-reviews/amends.

    *engine_profile* selects behavior: the default (current engine
    version) uses the 0.4.0 adjudication layer; profile ``0.3.0``
    reproduces the exact M3-CA0 question set and refuses amendments
    (used to re-verify legacy runs byte-identically).

    Returns ``{run, artifacts}``. Deterministic pure function of the
    explicit inputs. Writes nothing (persistence is the caller's concern).
    """
    engine_profile = engine_profile or ENGINE_VERSION
    protocol_v, schema_v, engine_v = profile_versions(engine_profile)
    adjudications = list(adjudications or [])
    amendment_records = list(amendments or [])
    if amendment_records and not profile_has_adjudication_layer(engine_profile):
        raise ReviewError(
            "amendments require the 0.4.0 engine profile (profile "
            f"{engine_profile!r} predates the amendment machinery)"
        )

    source_sha = None
    parsed_source_cases = None
    coverage = None
    if source_text is not None:
        source_sha = sha256_hex(source_text.encode("utf-8"))
        parsed = parse_case_set(source_text)
        if parsed["coverage"]["status"] != "PASS":
            raise ReviewError(
                "source coverage check FAILED on engine re-parse: "
                f"{parsed['coverage']['unaccounted_lines'][:10]} lines unaccounted "
                "(the review refuses unaccounted source content)"
            )
        parsed_source_cases = {c["case_id"]: c for c in parsed["cases"]}
        coverage = parsed["coverage"]["status"]

    # 0.4.0: deterministic amendment application (v1 → derived v2 views)
    if profile_has_adjudication_layer(engine_profile) and amendment_records:
        from .adjudication import effective_candidates

        effective, applied_amendments = effective_candidates(
            candidates, amendment_records
        )
    else:
        effective = candidates
        applied_amendments = []
    applied_by_candidate = {
        rec["candidate_id"]: rec for rec in applied_amendments
    }

    artifacts: "list[dict]" = []
    prior: "list[dict]" = []
    prev_hash = GENESIS_HASH
    for candidate in effective:
        amendment_record = applied_by_candidate.get(candidate.get("candidate_id"))
        if amendment_record is not None and "amendment" not in candidate:
            # defensive: effective_candidates guarantees linkage presence
            raise ReviewError(
                "internal inconsistency: amendment selected for "
                f"{candidate.get('candidate_id')!r} but the derived view "
                "carries no linkage"
            )
        artifact, artifact_hash = review_candidate(
            candidate=candidate,
            prior=prior,
            source_text=source_text,
            source_sha=source_sha,
            parsed_source_cases=parsed_source_cases,
            adjudications=adjudications,
            run_id=run_id,
            reviewed_at=reviewed_at,
            operator=operator,
            entry_index=len(artifacts) + 1,
            prev_artifact_hash=prev_hash,
            amendment_record=amendment_record,
            engine_profile=engine_profile,
        )
        artifacts.append(artifact)
        prior.append(candidate)
        prev_hash = artifact_hash

    tally = {"eligible": 0, "rejected": 0, "requires_review": 0}
    entries = []
    for artifact in artifacts:
        decision = artifact["decision"]
        key = {
            "ELIGIBLE": "eligible",
            "REJECTED": "rejected",
            "REQUIRES_REVIEW": "requires_review",
        }[decision]
        tally[key] += 1
        entries.append(
            {
                "review_id": artifact["review_id"],
                "candidate_id": artifact["candidate_id"],
                "source_case_id": artifact["source_case_id"],
                "content_hash": artifact["content_hash"],
                "decision": decision,
                "artifact_hash": artifact["artifact_hash"],
            }
        )

    applied_ids = sorted(
        {adj_id for artifact in artifacts for adj_id in artifact["adjudications_applied"]}
    )

    run = {
        "ecp_object": "review-run",
        "run_id": run_id,
        "run_kind": "case-review",
        "input": {"candidates_inspected": len(effective)},
        "review_parameters": {
            "engine": ENGINE_ID,
            "engine_version": engine_v,
            "jaccard_overlap_threshold": JACCARD_OVERLAP_THRESHOLD,
            "real_world_registry_size": len(REAL_WORLD_TERMS),
            "known_pattern_registry_size": len(KNOWN_PATTERNS),
        },
        "reviewer": {
            "kind": "deterministic-pipeline",
            "pipeline": ENGINE_ID,
            "engine_version": engine_v,
            "operator": operator,
        },
        "reviewed_at": reviewed_at,
        "adjudications": {
            "applied": len(applied_ids),
            "ids": applied_ids,
        },
        "decisions": tally,
        "entries": entries,
        "chain_head": artifacts[-1]["artifact_hash"] if artifacts else GENESIS_HASH,
        "notes": [
            "review-layer run: no registration, no execution, no scoring; "
            "the public ledger is untouched by design (no code path to it)"
        ],
        "protocol_version": protocol_v,
        "schema_version": schema_v,
    }
    if profile_has_adjudication_layer(engine_profile):
        run["amendments"] = {
            "applied": len(applied_amendments),
            "records": [
                {
                    "amendment_id": rec["amendment_id"],
                    "amendment_hash": rec["amendment_hash"],
                    "candidate_id": rec["candidate_id"],
                    "disclosure": rec["representation_bias_disclosure"]["value"],
                }
                for rec in applied_amendments
            ],
        }
        if lineage is not None:
            run["lineage"] = {
                "prior_run_id": lineage["prior_run_id"],
                "prior_run_hash": lineage["prior_run_hash"],
                "basis": lineage["basis"],
            }
    if source_text is not None:
        run["input"]["source_document"] = {
            "label": source_label or "source",
            "sha256": source_sha,
        }
        run["input"]["extraction"] = {
            "extractor": "source-reparsed-by-review-engine",
            "coverage": coverage,
        }
    run["run_hash"] = hash_document_excluding(run, "run_hash")
    return {"run": run, "artifacts": artifacts}


# --- verification --------------------------------------------------------------


def verify_artifact(artifact: dict) -> "list[str]":
    """Integrity issues for one review artifact (schema, self-hash)."""
    issues: "list[str]" = []
    schema_issues = validate_document(artifact, "case-review")
    if schema_issues:
        issues.extend(schema_issues)
        return issues
    version_problems = version_issues(artifact)
    issues.extend(version_problems)
    recomputed = hash_document_excluding(artifact, "artifact_hash")
    if recomputed != artifact.get("artifact_hash"):
        issues.append(
            f"{artifact.get('review_id', '?')}: artifact_hash mismatch "
            f"(declared {artifact.get('artifact_hash')!r}, recomputed {recomputed!r}) "
            "— tampered or corrupted artifact"
        )
    embedded = artifact.get("candidate_content")
    if isinstance(embedded, dict):
        content_hash = hash_document(embedded)
        if content_hash != artifact.get("content_hash"):
            issues.append(
                f"{artifact.get('review_id', '?')}: embedded candidate_content "
                "does not hash to the declared content_hash (R7 broken)"
            )
    # 0.4.0: amended-case artifacts must carry the disclosure value (a
    # POSSIBLE/KNOWN disclosure is never silently dropped — M3-CA0-A §7)
    amendment_block = artifact.get("amendment")
    if amendment_block is not None:
        if amendment_block.get("representation_bias_disclosure") not in (
            "NONE",
            "POSSIBLE",
            "KNOWN",
        ):
            issues.append(
                f"{artifact.get('review_id', '?')}: amended-case artifact carries "
                "no valid representation-bias disclosure value (the disclosure "
                "must travel with every artifact applying the amendment)"
            )
    return issues


def verify_run(run: dict, artifacts: "list[dict]") -> "list[str]":
    """Run-level integrity issues: manifest hash, chain linkage, tally,
    cross-references between manifest and artifacts."""
    issues: "list[str]" = []
    schema_issues = validate_document(run, "review-run")
    if schema_issues:
        issues.extend(schema_issues)
        return issues
    issues.extend(version_issues(run))
    recomputed = hash_document_excluding(run, "run_hash")
    if recomputed != run.get("run_hash"):
        issues.append(
            "run_hash mismatch (tampered or corrupted run manifest)"
        )

    prev = GENESIS_HASH
    for index, artifact in enumerate(artifacts, start=1):
        if artifact.get("entry_index") != index:
            issues.append(f"artifact {artifact.get('review_id', '?')}: entry_index {artifact.get('entry_index')} != expected {index}")
        if artifact.get("prev_artifact_hash") != prev:
            issues.append(
                f"artifact {artifact.get('review_id', '?')}: prev_artifact_hash "
                "breaks the chain"
            )
        if artifact.get("run_id") != run.get("run_id"):
            issues.append(
                f"artifact {artifact.get('review_id', '?')}: run_id differs from manifest"
            )
        prev = artifact.get("artifact_hash", "")
    if artifacts and run.get("chain_head") != artifacts[-1].get("artifact_hash"):
        issues.append("chain_head does not match the last artifact hash")

    entries = run.get("entries", [])
    if len(entries) != len(artifacts):
        issues.append(
            f"manifest lists {len(entries)} entries but {len(artifacts)} artifacts exist"
        )
    for entry, artifact in zip(entries, artifacts):
        for field in ("review_id", "candidate_id", "content_hash", "decision", "artifact_hash"):
            if entry.get(field) != artifact.get(field):
                issues.append(
                    f"manifest/artifact mismatch on {field} for {entry.get('review_id', '?')}"
                )

    tally = {"eligible": 0, "rejected": 0, "requires_review": 0}
    for artifact in artifacts:
        key = {
            "ELIGIBLE": "eligible",
            "REJECTED": "rejected",
            "REQUIRES_REVIEW": "requires_review",
        }.get(artifact.get("decision"))
        if key is None:
            issues.append(
                f"artifact {artifact.get('review_id', '?')}: decision "
                f"{artifact.get('decision')!r} outside the three allowed states"
            )
        else:
            tally[key] += 1
    if tally != run.get("decisions"):
        issues.append(f"decision tally mismatch: manifest {run.get('decisions')} vs recomputed {tally}")

    # 0.4.0: manifest amendments block must agree with the artifacts that
    # applied amendments (linkage + disclosure values never silently altered)
    manifest_amendments = run.get("amendments")
    if manifest_amendments is not None:
        records = manifest_amendments.get("records", [])
        if manifest_amendments.get("applied") != len(records):
            issues.append(
                "manifest amendments.applied != number of amendment records"
            )
        by_amendment = {rec.get("amendment_id"): rec for rec in records}
        artifact_links = [
            (a.get("amendment", {}).get("amendment_id"), a)
            for a in artifacts
            if a.get("amendment") is not None
        ]
        for amendment_id, artifact in artifact_links:
            rec = by_amendment.get(amendment_id)
            if rec is None:
                issues.append(
                    f"artifact {artifact.get('review_id', '?')}: amendment "
                    f"{amendment_id!r} not present in the manifest amendments block"
                )
                continue
            block = artifact["amendment"]
            if (
                rec.get("amendment_hash") != block.get("amendment_hash")
                or rec.get("candidate_id") != artifact.get("candidate_id")
                or rec.get("disclosure") != block.get("representation_bias_disclosure")
            ):
                issues.append(
                    f"artifact {artifact.get('review_id', '?')}: amendment linkage "
                    "(hash/candidate/disclosure) differs from the manifest record"
                )
        if len(artifact_links) != len(records):
            issues.append(
                f"manifest lists {len(records)} amendment record(s) but "
                f"{len(artifact_links)} artifact(s) carry amendment linkage"
            )
    return issues


def verify_adjudication(adjudication: dict) -> "list[str]":
    """Integrity issues for one adjudication record (schema, versions, hash)."""
    issues: "list[str]" = []
    schema_issues = validate_document(adjudication, "review-adjudication")
    if schema_issues:
        return schema_issues
    issues.extend(version_issues(adjudication))
    recomputed = hash_document_excluding(adjudication, "adjudication_hash")
    if recomputed != adjudication.get("adjudication_hash"):
        issues.append(
            f"{adjudication.get('adjudication_id', '?')}: adjudication_hash mismatch"
        )
    return issues
