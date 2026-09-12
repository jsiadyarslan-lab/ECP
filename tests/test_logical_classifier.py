"""M3-ELR logical classifier tests — M3-ELR-LOGICAL-CLASSIFIER-1 (reconstructed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecp.logical_classifier import (  # noqa: E402
    ANSWER_STATES,
    CLASSIFIER_ID,
    answer_space_of,
    classify_response,
    expected_answer_key,
    extract_declared_answer,
    premise_citation,
)

TERNARY_Q = "Is the vex taller than the qid? Answer with: yes, no, or cannot be determined."
BINARY_Q = "Are the statements mutually consistent? Answer with: yes or no."
VALUE_Q = "How many beads does the hox hold? Answer with a number, or cannot be determined."
CONTENT = {
    "premises": ["The vex is taller than the lum.", "The lum is taller than the qid."],
    "question": TERNARY_Q,
    "ground_truth": {"class": "DERIVABLE", "statement": "the vex is taller than the qid"},
    "intended_correct_answers": [{"source_block": 1, "value": "Yes — the vex is taller than the qid."}],
    "derivations": [{"raw": "premises 1 and 2 by transitivity"}],
}
CONTENT_INDETERMINATE = {
    **CONTENT,
    "ground_truth": {"class": "INDETERMINATE", "statement": "not derivable"},
    "intended_correct_answers": [{"source_block": 1, "value": "Cannot be determined from the premises."}],
}


def test_classifier_identity_is_frozen():
    assert CLASSIFIER_ID == "M3-ELR-LOGICAL-CLASSIFIER-1"


def test_answer_space_detection_matches_the_authored_pool_formats():
    assert answer_space_of(TERNARY_Q) == "TERNARY"
    assert answer_space_of(BINARY_Q) == "BINARY"
    assert answer_space_of(VALUE_Q) == "VALUE"
    assert answer_space_of(
        "Which gem does the cu hold? Answer with exactly one of: opal, rust, sage, or cannot be determined."
    ) == "VALUE"


def test_ternary_extraction_takes_first_declaration():
    assert extract_declared_answer("Yes — the vex is taller.", "TERNARY")["token"] == "YES"
    assert extract_declared_answer("No, it does not follow.", "TERNARY")["token"] == "NO"
    assert extract_declared_answer("It cannot be determined from the premises.", "TERNARY")["token"] == "CANNOT-DETERMINE"


def test_conflicting_declarations_are_malformed_never_resolved():
    result = extract_declared_answer("Yes. Also no.", "TERNARY")
    assert result["token"] is not None and result["conflicts"]


def test_premise_citation_by_index():
    citation = premise_citation("The answer follows from premise 2.", CONTENT["premises"])
    assert citation == {"cited": True, "mode": "index", "evidence": "premise 2"}


def test_premise_citation_by_verbatim_fragment():
    citation = premise_citation("Since the vex is taller than the lum, the chain holds.", CONTENT["premises"])
    assert citation["cited"] and citation["mode"] == "verbatim"


def test_premise_citation_absent_when_no_reference():
    citation = premise_citation("The answer is yes.", CONTENT["premises"])
    assert citation["cited"] is False


def test_expected_answer_key_derives_from_intended_answer():
    assert expected_answer_key(CONTENT) == "YES"
    assert expected_answer_key(CONTENT_INDETERMINATE) == "CANNOT-DETERMINE"


def test_correct_answer_with_citation_is_success():
    result = classify_response("Yes — premise 1 establishes it.", CONTENT)
    assert result["answer_state"] == "CORRECT"
    assert result["task_outcome"] == "SUCCESS"
    assert result["declared_logical_class"] == "DERIVABLE"


def test_correct_answer_without_citation_fails_the_success_criterion():
    result = classify_response("Yes.", CONTENT)
    assert result["answer_state"] == "CORRECT"
    assert result["task_outcome"] == "FAIL"


def test_wrong_answer_is_incorrect_but_execution_success():
    result = classify_response("No — premise 1 says otherwise.", CONTENT)
    assert result["answer_state"] == "INCORRECT"
    assert result["declared_logical_class"] == "CONTRADICTED"


def test_abstention_states_are_distinguished():
    correct_abstain = classify_response("It cannot be determined — the premises are silent.", CONTENT_INDETERMINATE)
    assert correct_abstain["answer_state"] == "CORRECT_ABSTENTION"
    incorrect_abstain = classify_response("It cannot be determined from the premises.", CONTENT)
    assert incorrect_abstain["answer_state"] == "INCORRECT_ABSTENTION"


def test_cannot_determine_is_never_collapsed_into_contradicted():
    result = classify_response("Cannot be determined from the given premises.", CONTENT_INDETERMINATE)
    assert result["declared_logical_class"] == "INDETERMINATE"
    assert result["declared_logical_class"] != "CONTRADICTED"


def test_non_answer_and_infrastructure_failure_separation():
    non_answer = classify_response("The premises describe heights.", CONTENT)
    assert non_answer["answer_state"] == "NON_ANSWER"
    unobservable = classify_response(None, CONTENT, response_received=False)
    assert unobservable["answer_state"] == "UNOBSERVABLE"
    assert unobservable["task_outcome"] == "FAIL"
    assert unobservable["infrastructure_separation"] is True
    assert set(ANSWER_STATES) >= {"CORRECT", "INCORRECT", "CORRECT_ABSTENTION", "INCORRECT_ABSTENTION", "NON_ANSWER", "MALFORMED_ANSWER", "UNOBSERVABLE"}


def test_classification_never_carries_protected_ground_truth():
    result = classify_response("Yes — premise 1.", CONTENT)
    assert result["expected_key"] is None
    assert result["gt_logical_class"] is None
