"""RVR-CLASSIFIER-1 — frozen outcome classifier for campaign ECP-EVAL-RVR-1.

Registered by the order *ECP — REASONING vs RETRIEVAL PREREGISTRATION
FREEZE v1* (2026-09-13) under Design v1.1 §E. Implements the registered
outcome taxonomy:

    CORRECT / INCORRECT / CORRECT_ABSTENTION / INCORRECT_ABSTENTION /
    MALFORMED_ANSWER / NON_ANSWER / INVALID_EXECUTION / UNOBSERVABLE

Defect corrections carried from M3 (OD-02 D1-B future-registration scope):

* D1 — premise citation is requested-but-optional and NEVER participates in
  any correctness determination (provenance information only).
* D2 — only the terminal ``ANSWER:`` envelope line is parsed. Prose never
  reaches classification, so natural-language token collisions (e.g. the
  word "no") cannot determine a scientific outcome accidentally.
* D3 — first-class grammar answers: ``yes`` / ``no`` / ``cannot`` and closed
  entity enumerations, with malformed / non-answer / abstention states kept
  distinct from incorrect answers.

This module is FROZEN at registration. Any change requires a new classifier
identity and a new registration package; the registration hash-record pins
this file's SHA-256.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

CLASSIFIER_ID = "RVR-CLASSIFIER-1"
CLASSIFIER_VERSION = 1
ABSTENTION_TOKEN = "cannot"
POLAR_TOKENS = ("yes", "no")

# Registered envelope grammar (RVR-ENVELOPE-1): the model's final line must
# be exactly "ANSWER: <token>". Parsing rules, frozen:
#   * only lines matching the envelope regex are considered;
#   * the LAST matching line is the answer (terminal rule);
#   * token comparison is exact, case-sensitive, after whitespace strip;
#   * a non-grammar token is MALFORMED_ANSWER (never INCORRECT);
#   * no envelope at all is NON_ANSWER.
_ANSWER_RE = re.compile(r"^[ \t]*ANSWER:[ \t]*(\S.*?)[ \t]*$", re.MULTILINE)
_CITED_RE = re.compile(r"^[ \t]*CITED:[ \t]*(.+?)[ \t]*$", re.MULTILINE)
_CITED_TOKEN_RE = re.compile(r"\d+")


def extract_answer_token(normalized_output: str) -> "tuple[str | None, list[str]]":
    """Return (terminal ANSWER token or None, all matching envelope lines)."""
    matches = _ANSWER_RE.findall(normalized_output or "")
    return (matches[-1] if matches else None), matches


def extract_citation(normalized_output: str, premise_count: int) -> dict[str, Any]:
    """Extract the OPTIONAL ``CITED:`` provenance line (non-scoring).

    D1 resolution: citation presence or accuracy never affects correctness.
    """
    lines = _CITED_RE.findall(normalized_output or "")
    numbers: list[int] = []
    for line in lines:
        for tok in _CITED_TOKEN_RE.findall(line):
            n = int(tok)
            if 1 <= n <= premise_count and n not in numbers:
                numbers.append(n)
    numbers.sort()
    return {
        "cited": bool(numbers),
        "premise_numbers": numbers,
        "mode": "optional_requested" if lines else None,
        "scoring": "NONE — provenance information only (D1 resolution)",
    }


def classify_response(
    normalized_output: "str | None",
    case: Mapping[str, Any],
    gt_answer: str,
    *,
    execution_valid: bool = True,
    response_received: bool = True,
    evidence_complete: bool = True,
) -> dict[str, Any]:
    """Classify one normalized response against the sealed ground truth.

    ``case`` is the PUBLIC registered case record (premises, question,
    answer grammar). ``gt_answer`` is the plaintext sealed answer supplied by
    the frozen classification path (verified against ``gt_commitment`` by the
    caller). The returned classification NEVER echoes the ground truth.
    """
    grammar = case["answer_grammar"]
    tokens = list(grammar["tokens"])
    premise_count = len(case.get("premises") or [])

    result: dict[str, Any] = {
        "classifier_id": CLASSIFIER_ID,
        "classifier_version": CLASSIFIER_VERSION,
        "grammar_type": grammar["type"],
        "answer_state": None,
        "declared_token": None,
        "envelope_lines": 0,
        "premise_citation": extract_citation(normalized_output or "", premise_count),
        "gt_echoed": False,  # protected ground truth never leaves this call
    }

    if not execution_valid:
        result["answer_state"] = "INVALID_EXECUTION"
        return result
    if (not response_received) or (normalized_output is None) or (not evidence_complete):
        result["answer_state"] = "UNOBSERVABLE"
        return result

    token, matches = extract_answer_token(normalized_output)
    result["envelope_lines"] = len(matches)
    result["declared_token"] = token

    if token is None:
        result["answer_state"] = "NON_ANSWER"
        return result
    if token not in tokens:
        result["answer_state"] = "MALFORMED_ANSWER"
        return result

    if token == ABSTENTION_TOKEN:
        result["answer_state"] = (
            "CORRECT_ABSTENTION" if gt_answer == ABSTENTION_TOKEN
            else "INCORRECT_ABSTENTION"
        )
        return result
    if token == gt_answer:
        result["answer_state"] = "CORRECT"
    elif gt_answer == ABSTENTION_TOKEN:
        result["answer_state"] = "INCORRECT_ABSTENTION"
    else:
        result["answer_state"] = "INCORRECT"
    return result


# ---------------------------------------------------------------------------
# Registration-time determinism self-test (validation battery input).
# Constructed examples only — no experimental material.
# ---------------------------------------------------------------------------

def self_test() -> "list[dict[str, Any]]":
    grammar_polar = {"type": "yes_no_cannot", "tokens": ["yes", "no", "cannot"]}
    grammar_enum = {"type": "value_enum", "tokens": ["alpha", "beta", "gamma"]}

    def case_of(grammar, premises=("p1", "p2")):
        return {"premises": list(premises), "question": "q?",
                "answer_grammar": grammar}

    trials = [
        ("polar-correct", "work\nANSWER: yes", case_of(grammar_polar), "yes", "CORRECT"),
        ("polar-incorrect", "ANSWER: no", case_of(grammar_polar), "yes", "INCORRECT"),
        ("correct-abstention", "ANSWER: cannot", case_of(grammar_polar), "cannot",
         "CORRECT_ABSTENTION"),
        ("incorrect-abstention-token", "ANSWER: cannot", case_of(grammar_polar), "no",
         "INCORRECT_ABSTENTION"),
        ("incorrect-abstention-gt", "ANSWER: yes", case_of(grammar_polar), "cannot",
         "INCORRECT_ABSTENTION"),
        ("non-answer", "I think the answer is obviously yes.", case_of(grammar_polar),
         "yes", "NON_ANSWER"),
        ("malformed-token", "ANSWER: Yes", case_of(grammar_polar), "yes",
         "MALFORMED_ANSWER"),
        ("malformed-enum", "ANSWER: delta", case_of(grammar_enum), "alpha",
         "MALFORMED_ANSWER"),
        ("terminal-rule", "ANSWER: yes\nactually, reconsidered\nANSWER: no",
         case_of(grammar_polar), "no", "CORRECT"),
        ("enum-correct", "ANSWER: gamma", case_of(grammar_enum), "gamma", "CORRECT"),
        ("invalid-execution", None, case_of(grammar_polar), "yes", "INVALID_EXECUTION"),
        ("unobservable", None, case_of(grammar_polar), "yes", "UNOBSERVABLE"),
        ("citation-nonscoring", "CITED: 1, 2\nANSWER: yes", case_of(grammar_polar),
         "no", "INCORRECT"),
    ]
    out = []
    for name, output, case, gt, expected in trials:
        kwargs = {}
        if name == "invalid-execution":
            kwargs = {"execution_valid": False}
        elif name == "unobservable":
            kwargs = {"response_received": False, "evidence_complete": False}
        got = classify_response(output, case, gt, **kwargs)
        out.append({
            "trial": name,
            "expected": expected,
            "got": got["answer_state"],
            "pass": got["answer_state"] == expected,
            "citation_reported_nonscoring": bool(
                got["premise_citation"]["premise_numbers"]) is False or
                got["answer_state"] in ("CORRECT", "INCORRECT"),
        })
    return out
