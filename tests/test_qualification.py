"""M3-CA0 v1 qualification-engine tests.

Covers:
- the four ground-truth verification backends (relational closure incl. the
  conflict-on-existing-atom regression, propositional truth-table,
  constraint enumeration, default extensions) — deterministic, model-free;
- renaming-invariant structural skeletons (order §7);
- the four-state decision mapping (ACCEPT / REVISE / REJECT / INCONCLUSIVE)
  with every trigger path;
- run-level chaining, tallies, determinism re-derivation, tamper detection;
- the format-illustration examples' real, recomputable hashes.
"""

import json

import pytest

from qual_fixtures import _DELETE, make_candidate

from ecp.hashing import hash_document, hash_document_excluding
from ecp import qualification as qual
from ecp.qualification import (
    InvalidQualificationState,
    QualificationError,
    qualify_candidate,
    run_qualification,
    structural_skeleton,
    verify_artifact,
    verify_run,
    verify_ground_truth,
    verify_constraint_enumeration,
    verify_default_extensions,
    verify_propositional,
    verify_relational_closure,
)

RUN = "ECP-QUALRUN-TEST"
AT = "2026-09-09T00:00:00Z"
OP = "test operator <test@ecp.local>"


# ---------------------------------------------------------------------------
# Backend: relational closure
# ---------------------------------------------------------------------------

def test_relational_chain_derivable():
    result = verify_relational_closure({
        "semantics": "relational-closure",
        "entities": ["a", "b", "c"],
        "premises": [
            {"kind": "rel_fact", "relation": "t", "args": ["a", "b"]},
            {"kind": "rel_fact", "relation": "t", "args": ["b", "c"]},
            {"kind": "rel_rule", "vars": ["x", "y", "z"],
             "if": [{"relation": "t", "args": ["x", "y"]}, {"relation": "t", "args": ["y", "z"]}],
             "then": {"relation": "t", "args": ["x", "z"]}},
        ],
        "query": {"relation": "t", "args": ["a", "c"]},
    })
    assert result["derived_class"] == "DERIVABLE"


def test_relational_broken_chain_indeterminate():
    result = verify_relational_closure({
        "semantics": "relational-closure",
        "entities": ["a", "b", "c", "d"],
        "premises": [
            {"kind": "rel_fact", "relation": "t", "args": ["a", "b"]},
            {"kind": "rel_fact", "relation": "t", "args": ["c", "d"]},
            {"kind": "rel_rule", "vars": ["x", "y", "z"],
             "if": [{"relation": "t", "args": ["x", "y"]}, {"relation": "t", "args": ["y", "z"]}],
             "then": {"relation": "t", "args": ["x", "z"]}},
        ],
        "query": {"relation": "t", "args": ["a", "d"]},
    })
    assert result["derived_class"] == "INDETERMINATE"


def test_relational_reversed_query_contradicted():
    result = verify_relational_closure({
        "semantics": "relational-closure",
        "entities": ["a", "b", "c"],
        "premises": [
            {"kind": "rel_fact", "relation": "t", "args": ["a", "b"]},
            {"kind": "rel_fact", "relation": "t", "args": ["b", "c"]},
            {"kind": "rel_rule", "vars": ["x", "y"],
             "if": [{"relation": "t", "args": ["x", "y"]}],
             "then": {"relation": "t", "args": ["y", "x"], "negated": True}},
            {"kind": "rel_rule", "vars": ["x", "y", "z"],
             "if": [{"relation": "t", "args": ["x", "y"]}, {"relation": "t", "args": ["y", "z"]}],
             "then": {"relation": "t", "args": ["x", "z"]}},
        ],
        "query": {"relation": "t", "args": ["c", "a"]},
    })
    assert result["derived_class"] == "CONTRADICTED"


def test_relational_cycle_consistency_contradicted():
    """Regression: the asymmetry rule firing onto an already-asserted atom
    (the cycle case) MUST be recorded as a conflict — never skipped."""
    result = verify_relational_closure({
        "semantics": "relational-closure",
        "entities": ["a", "b", "c"],
        "premises": [
            {"kind": "rel_fact", "relation": "h", "args": ["a", "b"]},
            {"kind": "rel_fact", "relation": "h", "args": ["b", "c"]},
            {"kind": "rel_fact", "relation": "h", "args": ["c", "a"]},
            {"kind": "rel_rule", "vars": ["x", "y"],
             "if": [{"relation": "h", "args": ["x", "y"]}],
             "then": {"relation": "h", "args": ["y", "x"], "negated": True}},
            {"kind": "rel_rule", "vars": ["x", "y", "z"],
             "if": [{"relation": "h", "args": ["x", "y"]}, {"relation": "h", "args": ["y", "z"]}],
             "then": {"relation": "h", "args": ["x", "z"]}},
        ],
        "query": {"kind": "consistency"},
    })
    assert result["derived_class"] == "CONTRADICTED"
    assert result["conflicts"]


def test_relational_repair_count():
    """Cycle + detached pair + both rules: exactly five of six single
    removals restore consistency (everything except the detached pair)."""
    result = verify_relational_closure({
        "semantics": "relational-closure",
        "entities": ["a", "b", "c", "d", "e"],
        "premises": [
            {"kind": "rel_fact", "relation": "o", "args": ["a", "b"]},
            {"kind": "rel_fact", "relation": "o", "args": ["b", "c"]},
            {"kind": "rel_fact", "relation": "o", "args": ["c", "a"]},
            {"kind": "rel_fact", "relation": "o", "args": ["d", "e"]},
            {"kind": "rel_rule", "vars": ["x", "y", "z"],
             "if": [{"relation": "o", "args": ["x", "y"]}, {"relation": "o", "args": ["y", "z"]}],
             "then": {"relation": "o", "args": ["x", "z"]}},
            {"kind": "rel_rule", "vars": ["x", "y"],
             "if": [{"relation": "o", "args": ["x", "y"]}],
             "then": {"relation": "o", "args": ["y", "x"], "negated": True}},
        ],
        "query": {"kind": "repair_count"},
    })
    assert result["derived_class"] == "DERIVABLE"
    assert result["value"] == 5
    assert result["removals"] == [1, 2, 3, 5, 6]


def test_relational_unsupported_premise_kind_is_loud():
    with pytest.raises(InvalidQualificationState):
        verify_relational_closure({
            "semantics": "relational-closure",
            "entities": ["a"],
            "premises": [{"kind": "prop_fact", "prop": "p", "value": True}],
            "query": {"relation": "t", "args": ["a", "a"]},
        })


# ---------------------------------------------------------------------------
# Backend: propositional truth-table
# ---------------------------------------------------------------------------

def test_propositional_mp_chain_derivable():
    result = verify_propositional({
        "semantics": "propositional-truth-table",
        "props": ["p", "q", "r"],
        "premises": [
            {"kind": "impl", "if": ["p"], "then": "q"},
            {"kind": "impl", "if": ["q"], "then": "r"},
            {"kind": "prop_fact", "prop": "p", "value": True},
        ],
        "query": {"prop": "r", "value": True},
    })
    assert result["derived_class"] == "DERIVABLE"


def test_propositional_mt_refuted():
    result = verify_propositional({
        "semantics": "propositional-truth-table",
        "props": ["p", "q"],
        "premises": [
            {"kind": "impl", "if": ["p"], "then": "q"},
            {"kind": "prop_fact", "prop": "q", "value": False},
        ],
        "query": {"prop": "p", "value": True},
    })
    assert result["derived_class"] == "CONTRADICTED"


def test_propositional_converse_indeterminate():
    result = verify_propositional({
        "semantics": "propositional-truth-table",
        "props": ["p", "q"],
        "premises": [
            {"kind": "impl", "if": ["p"], "then": "q"},
            {"kind": "prop_fact", "prop": "q", "value": True},
        ],
        "query": {"prop": "p", "value": True},
    })
    assert result["derived_class"] == "INDETERMINATE"


def test_propositional_consistency_sat_and_unsat():
    sat = verify_propositional({
        "semantics": "propositional-truth-table",
        "question_kind_note": "consistency via query.kind",
        "props": ["p"],
        "premises": [{"kind": "prop_fact", "prop": "p", "value": True}],
        "query": {"kind": "consistency"},
    })
    assert sat["derived_class"] == "DERIVABLE"
    unsat = verify_propositional({
        "semantics": "propositional-truth-table",
        "props": ["p"],
        "premises": [
            {"kind": "prop_fact", "prop": "p", "value": True},
            {"kind": "prop_fact", "prop": "p", "value": False},
        ],
        "query": {"kind": "consistency"},
    })
    assert unsat["derived_class"] == "CONTRADICTED"


def test_propositional_statement_query_on_unsat_premises_flagged():
    result = verify_propositional({
        "semantics": "propositional-truth-table",
        "props": ["p"],
        "premises": [
            {"kind": "prop_fact", "prop": "p", "value": True},
            {"kind": "prop_fact", "prop": "p", "value": False},
        ],
        "query": {"prop": "p", "value": True},
    })
    assert result["derived_class"] is None
    assert "PREMISES-INCONSISTENT" in result["status_note"]


def test_propositional_repair_count():
    result = verify_propositional({
        "semantics": "propositional-truth-table",
        "props": ["p"],
        "premises": [
            {"kind": "prop_fact", "prop": "p", "value": True},
            {"kind": "prop_fact", "prop": "p", "value": False},
            {"kind": "prop_fact", "prop": "p", "value": True},
        ],
        "query": {"kind": "repair_count"},
    })
    # removing premise 2 (the p=False fact) leaves [p=T, p=T]: satisfiable;
    # removing premise 1 or 3 leaves [p=T, p=F] or [p=F, p=T]: unsatisfiable
    assert result["derived_class"] == "DERIVABLE"
    assert result["value"] == 1
    assert result["removals"] == [2]


# ---------------------------------------------------------------------------
# Backend: constraint enumeration
# ---------------------------------------------------------------------------

def test_constraint_unique_value_derivable():
    result = verify_constraint_enumeration({
        "semantics": "constraint-enumeration",
        "variables": ["x", "y", "z"],
        "domains": {"x": ["a", "b", "c"], "y": ["a", "b", "c"], "z": ["a", "b", "c"]},
        "premises": [
            {"kind": "all_different", "vars": ["x", "y", "z"]},
            {"kind": "not_equal", "var": "x", "value": "a"},
            {"kind": "equals", "var": "y", "value": "b"},
        ],
        "query": {"kind": "value_of", "var": "z"},
    })
    assert result["derived_class"] == "DERIVABLE"
    assert result["value"] == "a"


def test_constraint_multi_value_indeterminate():
    result = verify_constraint_enumeration({
        "semantics": "constraint-enumeration",
        "variables": ["x", "y"],
        "domains": {"x": ["a", "b"], "y": ["a", "b"]},
        "premises": [{"kind": "not_equal", "var": "x", "value": "a"}],
        "query": {"kind": "value_of", "var": "y"},
    })
    assert result["derived_class"] == "INDETERMINATE"


def test_constraint_truth_of_mixed_indeterminate():
    result = verify_constraint_enumeration({
        "semantics": "constraint-enumeration",
        "variables": ["x", "y"],
        "domains": {"x": ["a", "b"], "y": ["a", "b"]},
        "premises": [{"kind": "all_different", "vars": ["x", "y"]}],
        "query": {"kind": "truth_of", "var": "y", "value": "a"},
    })
    assert result["derived_class"] == "INDETERMINATE"


def test_constraint_pigeonhole_impossible():
    result = verify_constraint_enumeration({
        "semantics": "constraint-enumeration",
        "variables": ["x", "y", "z"],
        "domains": {"x": ["s", "m"], "y": ["s", "m"], "z": ["s", "m"]},
        "premises": [{"kind": "all_different", "vars": ["x", "y", "z"]}],
        "query": {"kind": "solution_exists"},
    })
    assert result["derived_class"] == "IMPOSSIBLE"


def test_constraint_linear_arithmetic():
    result = verify_constraint_enumeration({
        "semantics": "constraint-enumeration",
        "variables": ["jal", "kiv", "hox"],
        "domains": {"jal": {"range": [0, 20]}, "kiv": {"range": [0, 20]}, "hox": {"range": [0, 20]}},
        "premises": [
            {"kind": "equals", "var": "jal", "value": 5},
            {"kind": "linear", "expr": "kiv - jal = 3"},
            {"kind": "linear", "expr": "hox - 2 * kiv = 0"},
        ],
        "query": {"kind": "value_of", "var": "hox"},
    })
    assert result["derived_class"] == "DERIVABLE"
    assert result["value"] == 16


def test_constraint_immediately_before():
    result = verify_constraint_enumeration({
        "semantics": "constraint-enumeration",
        "variables": ["w", "e", "s", "p"],
        "domains": {v: {"range": [1, 4]} for v in ("w", "e", "s", "p")},
        "premises": [
            {"kind": "all_different", "vars": ["w", "e", "s", "p"]},
            {"kind": "immediately_before", "a": "w", "b": "e"},
            {"kind": "immediately_before", "a": "s", "b": "p"},
            {"kind": "not_equal", "var": "s", "value": 1},
        ],
        "query": {"kind": "value_of", "var": "s"},
    })
    assert result["derived_class"] == "DERIVABLE"
    assert result["value"] == 3


def test_constraint_search_space_cap_is_loud():
    with pytest.raises(InvalidQualificationState, match="200000"):
        verify_constraint_enumeration({
            "semantics": "constraint-enumeration",
            "variables": ["a", "b", "c", "d", "e", "f", "g", "h"],
            "domains": {v: {"range": [0, 20]} for v in "abcdefgh"},
            "premises": [{"kind": "equals", "var": "a", "value": 0}],
            "query": {"kind": "value_of", "var": "a"},
        })


# ---------------------------------------------------------------------------
# Backend: default extensions
# ---------------------------------------------------------------------------

def test_default_applies():
    result = verify_default_extensions({
        "semantics": "default-extensions",
        "props": ["wob", "flies", "fen"],
        "premises": [
            {"kind": "prop_fact", "prop": "wob", "value": True},
            {"kind": "prop_fact", "prop": "fen", "value": False},
            {"kind": "default", "if": [{"prop": "wob", "value": True}],
             "normally": {"prop": "flies", "value": True},
             "unless": [{"prop": "fen", "value": True}]},
        ],
        "query": {"prop": "flies", "value": True},
    })
    assert result["derived_class"] == "DERIVABLE"
    assert result["extension_count"] == 1


def test_default_blocked_exception_indeterminate():
    result = verify_default_extensions({
        "semantics": "default-extensions",
        "props": ["kar", "blue", "dul"],
        "premises": [
            {"kind": "prop_fact", "prop": "kar", "value": True},
            {"kind": "prop_fact", "prop": "dul", "value": True},
            {"kind": "default", "if": [{"prop": "kar", "value": True}],
             "normally": {"prop": "blue", "value": True},
             "unless": [{"prop": "dul", "value": True}]},
        ],
        "query": {"prop": "blue", "value": True},
    })
    assert result["derived_class"] == "INDETERMINATE"


def test_default_fact_wins_contradicted():
    result = verify_default_extensions({
        "semantics": "default-extensions",
        "props": ["vel", "sinks"],
        "premises": [
            {"kind": "prop_fact", "prop": "vel", "value": True},
            {"kind": "prop_fact", "prop": "sinks", "value": False},
            {"kind": "default", "if": [{"prop": "vel", "value": True}],
             "normally": {"prop": "sinks", "value": True},
             "unless": []},
        ],
        "query": {"prop": "sinks", "value": True},
    })
    assert result["derived_class"] == "CONTRADICTED"


def test_default_conflicting_twin_defaults_two_extensions():
    """The designed ambiguity: two applicable defaults with opposite
    conclusions and no precedence — two maximal extensions, INDETERMINATE."""
    result = verify_default_extensions({
        "semantics": "default-extensions",
        "props": ["gwil", "hed", "unwell", "sings"],
        "premises": [
            {"kind": "prop_fact", "prop": "gwil", "value": True},
            {"kind": "prop_fact", "prop": "hed", "value": True},
            {"kind": "prop_fact", "prop": "unwell", "value": False},
            {"kind": "default", "if": [{"prop": "gwil", "value": True}],
             "normally": {"prop": "sings", "value": True},
             "unless": [{"prop": "unwell", "value": True}]},
            {"kind": "default", "if": [{"prop": "hed", "value": True}],
             "normally": {"prop": "sings", "value": False},
             "unless": [{"prop": "unwell", "value": True}]},
        ],
        "query": {"prop": "sings", "value": True},
    })
    assert result["derived_class"] == "INDETERMINATE"
    assert result["extension_count"] == 2


def test_default_chained_derivable():
    result = verify_default_extensions({
        "semantics": "default-extensions",
        "props": ["ser", "blooms", "fragrant"],
        "premises": [
            {"kind": "prop_fact", "prop": "ser", "value": True},
            {"kind": "default", "if": [{"prop": "ser", "value": True}],
             "normally": {"prop": "blooms", "value": True},
             "unless": []},
            {"kind": "default", "if": [{"prop": "blooms", "value": True}],
             "normally": {"prop": "fragrant", "value": True},
             "unless": []},
        ],
        "query": {"prop": "fragrant", "value": True},
    })
    assert result["derived_class"] == "DERIVABLE"


def test_verify_ground_truth_dispatch():
    unknown = verify_ground_truth({"semantics": "quantum", "premises": [], "query": {}})
    assert unknown["derived_class"] is None
    assert "UNVERIFIABLE" in unknown["status_note"]
    malformed = verify_ground_truth({
        "semantics": "relational-closure",
        "entities": [],
        "premises": [{"kind": "rel_fact", "relation": "t", "args": ["a", "b"]}],
        "query": {"relation": "t", "args": ["a", "b"]},
    })
    assert malformed["derived_class"] is None
    assert "MALFORMED" in malformed["status_note"]


# ---------------------------------------------------------------------------
# Skeletons (renaming invariance)
# ---------------------------------------------------------------------------

def test_skeleton_is_renaming_invariant():
    a = make_candidate("ECP-CAND-000101")
    b = make_candidate("ECP-CAND-000102")
    # rename entities (props) and relations — structure unchanged
    rename = {
        "content__formal__props": ["sun", "moon", "star", "comet"],
    }
    b = make_candidate("ECP-CAND-000102", **rename)
    assert structural_skeleton(a) == structural_skeleton(b)


def test_skeleton_differs_on_structure():
    a = make_candidate("ECP-CAND-000101")
    b = make_candidate(
        "ECP-CAND-000102",
        content__formal__premises=[
            {"kind": "impl", "if": ["beacon"], "then": "gate"},
            {"kind": "impl", "if": ["gate"], "then": "horn"},
            {"kind": "prop_fact", "prop": "beacon", "value": False},
        ],
        content__formal__query={"prop": "beacon", "value": True},
        content__ground_truth={"class": "INDETERMINATE", "statement": "different"},
    )
    assert structural_skeleton(a) != structural_skeleton(b)


def test_skeleton_none_without_formal_layer():
    a = make_candidate("ECP-CAND-000101", content__formal=None)
    assert structural_skeleton(a) is None


# ---------------------------------------------------------------------------
# Per-candidate decisions (the four states)
# ---------------------------------------------------------------------------

def _qualify(candidate, prior_in_pool=(), prior_population=()):
    artifact, _ = qualify_candidate(
        candidate,
        prior_in_pool=list(prior_in_pool),
        prior_population=list(prior_population),
        run_id=RUN,
        qualified_at=AT,
        operator=OP,
        entry_index=1,
        prev_artifact_hash="0" * 64,
    )
    return artifact


def test_valid_candidate_accepts():
    artifact = _qualify(make_candidate())
    assert artifact["decision"] == "ACCEPT"
    assert artifact["reason_codes"] == []
    assert artifact["dimensions"]["identity"]["status"] == "PASS"
    assert artifact["dimensions"]["ground_truth"]["status"] == "PASS"
    assert artifact["dimensions"]["leakage"]["status"] == "CLEAN"
    assert artifact["boundary"].startswith("QUALIFIED-POOL-ONLY")


def test_identity_tamper_rejects():
    artifact = _qualify(make_candidate(content_hash="0" * 64))
    assert artifact["decision"] == "REJECT"
    assert "Q1-IDENTITY-FAIL" in artifact["reason_codes"]
    assert artifact["dimensions"]["identity"]["status"] == "FAIL"


def test_ground_truth_mismatch_rejects():
    artifact = _qualify(
        make_candidate(content__ground_truth={"class": "CONTRADICTED", "statement": "wrong"})
    )
    assert artifact["decision"] == "REJECT"
    assert "Q3-GT-MISMATCH" in artifact["reason_codes"]
    assert artifact["dimensions"]["ground_truth"]["status"] == "MISMATCH"


def test_missing_formal_layer_is_inconclusive():
    artifact = _qualify(make_candidate(content__formal=_DELETE))
    assert artifact["decision"] == "INCONCLUSIVE"
    assert "Q3-GT-UNVERIFIABLE" in artifact["reason_codes"]


def test_direct_answer_leak_rejects():
    """The queried statement asserted directly by a premise fact: the case
    does not test reasoning (order §8 — DO NOT QUALIFY)."""
    artifact = _qualify(
        make_candidate(
            content__formal__premises=[
                {"kind": "impl", "if": ["beacon"], "then": "gate"},
                {"kind": "prop_fact", "prop": "beacon", "value": True},
                {"kind": "prop_fact", "prop": "bridge", "value": True},
            ]
        )
    )
    assert artifact["decision"] == "REJECT"
    assert "Q5-DIRECT-LEAK-CONFIRMED" in artifact["reason_codes"]
    assert artifact["dimensions"]["leakage"]["classes"]["direct_answer"] == "CONFIRMED"


def test_within_pool_duplicate_revise_later_candidate():
    first = make_candidate("ECP-CAND-000101")
    renamed = make_candidate(
        "ECP-CAND-000102",
        content__formal__props=["sun", "moon", "star", "comet"],
    )
    # renamed duplicate arrives later in the pool -> flagged REVISE
    artifact = _qualify(renamed, prior_in_pool=[first])
    assert artifact["decision"] == "REVISE"
    assert "Q4-N3-DUPLICATE" in artifact["reason_codes"]
    assert any("renaming is not a new case" in f for f in artifact["dimensions"]["novelty"]["findings"])


def test_cross_population_exact_duplicate_rejects():
    prior = make_candidate("ECP-CAND-000001", content__structural_signature="same sig")
    twin = make_candidate("ECP-CAND-000101", content__structural_signature="same sig")
    # identical premise text -> exact cross-population duplication
    artifact = _qualify(twin, prior_population=[prior])
    assert artifact["decision"] == "REJECT"
    assert "Q4-N4-DUPLICATE" in artifact["reason_codes"]


def test_missing_independence_record_rejects():
    artifact = _qualify(make_candidate(authoring_independence=_DELETE))
    assert artifact["decision"] == "REJECT"
    assert "Q6-INDEPENDENCE-MISSING" in artifact["reason_codes"]


def test_bare_independent_claim_flagged():
    candidate = make_candidate()
    candidate["authoring_independence"]["independence_status"] = "INDEPENDENT"
    artifact = _qualify(candidate)
    assert "Q6-BARE-INDEPENDENT-CLAIM" in artifact["reason_codes"]
    assert artifact["decision"] == "REVISE"


def test_missing_auxiliary_fields_revise():
    artifact = _qualify(make_candidate(content__forbidden_shortcuts=_DELETE))
    assert artifact["decision"] == "REVISE"
    assert "Q2-AUX-INCOMPLETE" in artifact["reason_codes"]


def test_missing_disclosure_blocks_revise():
    artifact = _qualify(
        make_candidate(
            representation_bias_disclosure=_DELETE,
            environmental_pre_check=_DELETE,
        )
    )
    assert artifact["decision"] == "REVISE"
    assert "Q7-DISCLOSURE-MISSING" in artifact["reason_codes"]
    assert "Q8-ENVIRONMENTAL-MISSING" in artifact["reason_codes"]


def test_format_illustration_refused():
    with pytest.raises(QualificationError, match="format-illustration"):
        _qualify(make_candidate(content_class="format-illustration"))


def test_unknown_engine_profile_is_loud():
    with pytest.raises(InvalidQualificationState, match="unknown engine profile"):
        qualify_candidate(
            make_candidate(),
            prior_in_pool=[],
            prior_population=[],
            run_id=RUN,
            qualified_at=AT,
            operator=OP,
            entry_index=1,
            prev_artifact_hash="0" * 64,
            engine_profile="0.0.9",
        )


def test_designed_ambiguity_forwarded():
    candidate = make_candidate(
        content__ground_truth={
            "class": "INDETERMINATE",
            "statement": "the nor sings at dawn",
            "ambiguity_note": "conflicting-defaults-two-extensions (designed)",
        },
        content__formal={
            "semantics": "default-extensions",
            "props": ["gwil", "hed", "unwell", "sings"],
            "premises": [
                {"kind": "prop_fact", "prop": "gwil", "value": True},
                {"kind": "prop_fact", "prop": "hed", "value": True},
                {"kind": "prop_fact", "prop": "unwell", "value": False},
                {"kind": "default", "if": [{"prop": "gwil", "value": True}],
                 "normally": {"prop": "sings", "value": True},
                 "unless": [{"prop": "unwell", "value": True}]},
                {"kind": "default", "if": [{"prop": "hed", "value": True}],
                 "normally": {"prop": "sings", "value": False},
                 "unless": [{"prop": "unwell", "value": True}]},
            ],
            "query": {"prop": "sings", "value": True},
        },
    )
    artifact = _qualify(candidate)
    assert artifact["decision"] == "ACCEPT"
    codes = [f["code"] for f in artifact["forwarded"]]
    assert "FWD-GT-DESIGNED-AMBIGUITY" in codes


# ---------------------------------------------------------------------------
# Run-level: chain, tallies, determinism, tamper detection
# ---------------------------------------------------------------------------

def _two_candidate_run():
    a = make_candidate("ECP-CAND-000101")
    # b carries no formal layer -> ground truth unverifiable -> INCONCLUSIVE
    b = make_candidate("ECP-CAND-000102", content__formal=_DELETE)
    return run_qualification(
        [a, b], run_id=RUN, qualified_at=AT, operator=OP,
        source_label="fixture.md", source_sha="0" * 64,
    )


def test_run_builds_chain_and_tallies():
    result = _two_candidate_run()
    artifacts, run = result["artifacts"], result["run"]
    assert len(artifacts) == 2
    assert artifacts[0]["prev_qualification_hash"] == "0" * 64
    assert artifacts[1]["prev_qualification_hash"] == artifacts[0]["artifact_hash"]
    assert run["chain_head"] == artifacts[1]["artifact_hash"]
    assert run["decisions"] == {"accept": 1, "revise": 0, "reject": 0, "inconclusive": 1}
    assert run["run_hash"] == hash_document_excluding(run, "run_hash")
    assert run["boundary"].startswith("STOP-BEFORE-REGISTRATION")
    assert run["execution_isolation"].startswith("NO evaluated model execution")


def test_run_deterministic_rederivation():
    result = _two_candidate_run()
    again = run_qualification(
        [make_candidate("ECP-CAND-000101"),
         make_candidate("ECP-CAND-000102", content__formal=_DELETE)],
        run_id=RUN, qualified_at=AT, operator=OP,
        source_label="fixture.md", source_sha="0" * 64,
    )
    assert [a["artifact_hash"] for a in again["artifacts"]] == [
        a["artifact_hash"] for a in result["artifacts"]
    ]
    assert again["run"]["run_hash"] == result["run"]["run_hash"]


def test_verify_artifact_detects_tampering():
    result = _two_candidate_run()
    artifact = result["artifacts"][0]
    assert verify_artifact(artifact) == []
    tampered = json.loads(json.dumps(artifact))
    tampered["decision"] = "INCONCLUSIVE"
    issues = verify_artifact(tampered)
    assert any("recomputation mismatch" in i for i in issues)


def test_verify_run_detects_tally_drift_and_chain_break():
    result = _two_candidate_run()
    artifacts, run = result["artifacts"], result["run"]
    assert verify_run(run, artifacts) == []
    drifted = json.loads(json.dumps(run))
    drifted["decisions"]["accept"] = 2
    issues = verify_run(drifted, artifacts)
    assert any("tallies" in i for i in issues)
    broken = json.loads(json.dumps(artifacts[1]))
    broken["prev_qualification_hash"] = "1" * 64
    issues = verify_run(run, [artifacts[0], broken])
    assert any("chain link broken" in i for i in issues)


def test_verify_run_rejects_bad_decision_state():
    result = _two_candidate_run()
    artifacts, run = result["artifacts"], result["run"]
    bad = json.loads(json.dumps(artifacts[0]))
    bad["decision"] = "MAYBE"
    issues = verify_artifact(bad)
    assert any("outside the four states" in i for i in issues)


# ---------------------------------------------------------------------------
# Examples: real, recomputable hashes
# ---------------------------------------------------------------------------

def test_case_qualification_example_hash_is_real(examples):
    artifact = examples["case-qualification.example.json"]
    assert artifact["content_class"] == "format-illustration"
    assert artifact["artifact_hash"] == hash_document_excluding(artifact, "artifact_hash")
    assert artifact["decision"] == "ACCEPT"
    assert artifact["prev_qualification_hash"] == "0" * 64


def test_qualification_run_example_is_consistent(examples):
    run = examples["qualification-run.example.json"]
    artifact = examples["case-qualification.example.json"]
    candidate = examples["case-candidate.example.json"]
    assert run["run_hash"] == hash_document_excluding(run, "run_hash")
    entry = run["entries"][0]
    assert entry["artifact_hash"] == artifact["artifact_hash"]
    assert entry["content_hash"] == candidate["content_hash"]
    assert entry["candidate_id"] == candidate["candidate_id"]
    assert run["chain_head"] == artifact["artifact_hash"]
    assert run["decisions"] == {"accept": 1, "revise": 0, "reject": 0, "inconclusive": 0}
