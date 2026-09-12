"""M3-ELR logical answer classifier — M3-ELR-LOGICAL-CLASSIFIER-1.

Scores normalized model answers against the PROTECTED ground truth of
registered M3-ELR cases (owner orders 2026-09-12/13: READINESS + EXECUTION).

Contract (frozen; reconstructed 2026-09-13 after custody loss D-01 #7,
pre-execution, outcome-blind — zero model calls existed project-wide at
reconstruction time):

* Three-way logical classification is preserved end-to-end:
  ``DERIVABLE`` / ``CONTRADICTED`` / ``INDETERMINATE`` (plus ``IMPOSSIBLE``
  for the authored pool's fourth GT class). ``CANNOT-DETERMINE`` (the model
  abstaining) is NEVER collapsed into ``CONTRADICTED`` and vice versa.
* Answer-state taxonomy separates the answer from its correctness:
  ``CORRECT`` / ``INCORRECT`` / ``CORRECT_ABSTENTION`` / ``INCORRECT_ABSTENTION``
  / ``NON_ANSWER`` / ``MALFORMED_ANSWER`` / ``UNOBSERVABLE``.
* Infrastructure failures (no response to classify) are ``UNOBSERVABLE`` —
  an execution fact, never a reasoning failure.
* Premise-citation rule (per-case success criterion): the answer must cite
  at least one premise by index (e.g. "premise 2") or by a verbatim fragment
  of >= 5 consecutive words of a premise.
* Answer spaces: ``TERNARY`` (yes / no / cannot-be-determined), ``BINARY``
  (yes / no), ``VALUE`` (case-specific value) — each with frozen
  value-matching normalization. Correctness is NEVER redefined after
  observing model outputs.

The classifier receives the protected ground truth only in the protected
in-process context; it never persists it (callers persist classifications,
not GT).
"""
from __future__ import annotations

import re
from typing import Any, Mapping

#: Frozen classifier identity (registered in the M3-ELR package).
CLASSIFIER_ID = "M3-ELR-LOGICAL-CLASSIFIER-1"
CLASSIFIER_VERSION = 1

#: The three-way logical classes of a model's declared answer verdict.
LOGICAL_CLASSES = ("DERIVABLE", "CONTRADICTED", "INDETERMINATE")

#: The authored pool's ground-truth classes (superset for GT side).
GT_CLASSES = ("DERIVABLE", "CONTRADICTED", "IMPOSSIBLE", "INDETERMINATE")

#: Answer-state taxonomy (answer correctness, separate from execution state).
ANSWER_STATES = (
    "CORRECT",
    "INCORRECT",
    "CORRECT_ABSTENTION",
    "INCORRECT_ABSTENTION",
    "NON_ANSWER",
    "MALFORMED_ANSWER",
    "UNOBSERVABLE",
)

#: Task outcomes for classified answers.
TASK_OUTCOMES = ("SUCCESS", "FAIL")

_ABSTAIN_RE = re.compile(r"cannot[- ]be[- ]determined|cannot\s+be\s+determined|undetermined", re.IGNORECASE)
_YES_RE = re.compile(r"\byes\b", re.IGNORECASE)
_NO_RE = re.compile(r"\bno\b", re.IGNORECASE)
_PREMISE_INDEX_RE = re.compile(r"premise\s*(?:number\s*)?(\d+)", re.IGNORECASE)

_TERNARY_KEYS = ("YES", "NO", "CANNOT-DETERMINE")
_BINARY_KEYS = ("YES", "NO")


# ---------------------------------------------------------------------------
# Answer-space detection (frozen: derived from the registered question text)
# ---------------------------------------------------------------------------

def answer_space_of(question: str) -> str:
    """Detect the registered answer space from the question's format clause.

    Frozen rule (matches the authored pool exactly): ``BINARY`` for
    "yes or no" clauses; ``TERNARY`` for "yes, no, or cannot be
    determined" clauses; ``VALUE`` for every other explicit answer-format
    clause (domain values, numbers, slots, …).
    """
    text = " ".join((question or "").split()).lower()
    if "yes or no" in text:
        return "BINARY"
    if re.search(r"yes,?\s+no,?\s+or\s+cannot\s+be\s+determined", text):
        return "TERNARY"
    if "answer with" in text:
        return "VALUE"
    return "TERNARY"


# ---------------------------------------------------------------------------
# Declared-answer extraction (frozen normalization)
# ---------------------------------------------------------------------------

def _first_keyword(text: str, pattern: re.Pattern) -> "tuple[int, int] | None":
    match = pattern.search(text)
    return (match.start(), match.end()) if match else None


def extract_declared_answer(text: str, answer_space: str) -> dict[str, Any]:
    """Extract the declared answer token from a normalized model response.

    Returns ``{token, conflicts}``. ``token`` is one of the space's keys or
    ``None`` when no declaration is present; ``conflicts`` lists the keys
    that ALSO appear (a response declaring both yes and no is malformed,
    never silently resolved).
    """
    if not isinstance(text, str) or not text.strip():
        return {"token": None, "conflicts": []}
    keys = _TERNARY_KEYS if answer_space == "TERNARY" else _BINARY_KEYS
    found: dict[str, "tuple[int, int]"] = {}
    abstain = _first_keyword(text, _ABSTAIN_RE)
    if abstain is not None and answer_space == "TERNARY":
        found["CANNOT-DETERMINE"] = abstain
    yes = _first_keyword(text, _YES_RE)
    if yes is not None:
        found["YES"] = yes
    no = _first_keyword(text, _NO_RE)
    if no is not None:
        found["NO"] = no
    if not found:
        return {"token": None, "conflicts": []}
    # earliest span wins; the others are conflicts
    ordered = sorted(found.items(), key=lambda kv: kv[1][0])
    token = ordered[0][0]
    conflicts = [k for k, _ in ordered[1:]]
    # a yes/no token inside the abstention phrase is part of it, not a conflict
    if token == "CANNOT-DETERMINE":
        span = found[token]
        conflicts = [
            k for k, sp in found.items()
            if k != token and not (span[0] <= sp[0] <= span[1])
        ]
    return {"token": token, "conflicts": conflicts}


# ---------------------------------------------------------------------------
# Premise citation (per-case success criterion)
# ---------------------------------------------------------------------------

def _premise_fragments(premises: "list[str]") -> "list[list[str]]":
    fragments = []
    for premise in premises or []:
        words = re.findall(r"[a-z0-9]+", premise.lower())
        fragments.append(words)
    return fragments


def premise_citation(text: str, premises: "list[str]") -> dict[str, Any]:
    """Check the premise-citation rule on a normalized response.

    Citation is satisfied by an explicit premise index or by a verbatim
    fragment of >= 5 consecutive words of any premise.
    """
    if not isinstance(text, str) or not text.strip():
        return {"cited": False, "mode": None, "evidence": None}
    index_match = _PREMISE_INDEX_RE.search(text)
    if index_match is not None:
        number = int(index_match.group(1))
        if 1 <= number <= len(premises or []):
            return {
                "cited": True,
                "mode": "index",
                "evidence": f"premise {number}",
            }
    response_words = re.findall(r"[a-z0-9]+", text.lower())
    for premise_words in _premise_fragments(premises):
        if len(premise_words) < 5:
            continue
        for start in range(len(response_words) - 4):
            window = response_words[start : start + 5]
            for p_start in range(len(premise_words) - 4):
                if window == premise_words[p_start : p_start + 5]:
                    return {
                        "cited": True,
                        "mode": "verbatim",
                        "evidence": " ".join(window),
                    }
    return {"cited": False, "mode": None, "evidence": None}


# ---------------------------------------------------------------------------
# Ground-truth key derivation (protected context only)
# ---------------------------------------------------------------------------

def expected_answer_key(content: Mapping[str, Any]) -> "str | None":
    """The registered answer key: the leading key of the intended answer.

    Works on the PROTECTED case content (never persisted by callers).
    For TERNARY/BINARY spaces this is YES / NO / CANNOT-DETERMINE; for VALUE
    spaces the intended answer text itself is the match target.
    """
    answers = content.get("intended_correct_answers") or []
    if not answers:
        return None
    value = str(answers[0].get("value", "")).strip()
    lowered = value.lower()
    if lowered.startswith("cannot"):
        return "CANNOT-DETERMINE"
    if lowered.startswith("yes"):
        return "YES"
    if lowered.startswith("no") and (len(lowered) == 2 or lowered[2] in " .,-—:"):
        return "NO"
    return value


def gt_logical_class(content: Mapping[str, Any]) -> "str | None":
    """The authored ground-truth class (protected context only)."""
    gt = content.get("ground_truth") or {}
    return gt.get("class")


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _logical_class_of_token(token: "str | None") -> "str | None":
    if token == "YES":
        return "DERIVABLE"
    if token == "NO":
        return "CONTRADICTED"
    if token == "CANNOT-DETERMINE":
        return "INDETERMINATE"
    return None


def classify_response(
    normalized_output: "str | None",
    content: Mapping[str, Any],
    *,
    response_received: bool = True,
) -> dict[str, Any]:
    """Classify one normalized model response against protected ground truth.

    ``content`` is the PROTECTED registered case content (premises, question,
    intended answers, ground truth). The returned classification carries the
    answer state, the declared and expected logical classes, premise-citation
    status, and the task outcome — never the ground truth itself.
    """
    question = str(content.get("question", ""))
    premises = list(content.get("premises") or [])
    space = answer_space_of(question)
    expected_key = expected_answer_key(content)
    gt_class = gt_logical_class(content)

    if not response_received or normalized_output is None:
        return {
            "classifier_id": CLASSIFIER_ID,
            "classifier_version": CLASSIFIER_VERSION,
            "answer_space": space,
            "answer_state": "UNOBSERVABLE",
            "declared_key": None,
            "declared_logical_class": None,
            "expected_key": None,  # protected; never echoed in classifications
            "gt_logical_class": None,  # protected
            "premise_citation": {"cited": False, "mode": None, "evidence": None},
            "task_outcome": "FAIL",
            "infrastructure_separation": True,
        }

    declared = extract_declared_answer(normalized_output, space)
    token = declared["token"]
    citation = premise_citation(normalized_output, premises)

    if token is None and not declared["conflicts"]:
        answer_state = "NON_ANSWER"
    elif declared["conflicts"]:
        answer_state = "MALFORMED_ANSWER"
    elif space == "VALUE":
        answer_state = "CORRECT" if _value_matches(normalized_output, expected_key) else "INCORRECT"
    elif token == expected_key:
        abstention = token == "CANNOT-DETERMINE"
        gt_abstention = expected_key == "CANNOT-DETERMINE"
        if abstention and gt_abstention:
            answer_state = "CORRECT_ABSTENTION"
        elif abstention or gt_abstention:
            answer_state = "INCORRECT_ABSTENTION"
        else:
            answer_state = "CORRECT"
    else:
        one_side_abstains = "CANNOT-DETERMINE" in (token, expected_key)
        answer_state = "INCORRECT_ABSTENTION" if one_side_abstains else "INCORRECT"

    outcome = "SUCCESS" if answer_state in ("CORRECT", "CORRECT_ABSTENTION") and citation["cited"] else "FAIL"

    return {
        "classifier_id": CLASSIFIER_ID,
        "classifier_version": CLASSIFIER_VERSION,
        "answer_space": space,
        "answer_state": answer_state,
        "declared_key": token,
        "declared_logical_class": _logical_class_of_token(token),
        "expected_key": None,  # protected ground truth never leaves this call
        "gt_logical_class": None,  # protected
        "premise_citation": citation,
        "task_outcome": outcome,
        "infrastructure_separation": True,
    }


def _value_matches(text: str, expected: "str | None") -> bool:
    """Frozen VALUE-space normalization: numeric equality or verbatim value."""
    if expected is None:
        return False
    expected_norm = " ".join(str(expected).lower().split())
    text_norm = " ".join((text or "").lower().split())
    if expected_norm and expected_norm in text_norm:
        return True
    expected_nums = re.findall(r"-?\d+(?:\.\d+)?", expected_norm)
    text_nums = re.findall(r"-?\d+(?:\.\d+)?", text_norm)
    if expected_nums and text_nums:
        try:
            return any(abs(float(e) - float(t)) < 1e-9 for e in expected_nums for t in text_nums)
        except ValueError:
            return False
    return False


__all__ = [
    "ANSWER_STATES",
    "CLASSIFIER_ID",
    "CLASSIFIER_VERSION",
    "GT_CLASSES",
    "LOGICAL_CLASSES",
    "TASK_OUTCOMES",
    "answer_space_of",
    "classify_response",
    "expected_answer_key",
    "extract_declared_answer",
    "gt_logical_class",
    "premise_citation",
]
