"""Fixture builders for the M3-CA0 v1 authoring + qualification tests.

Provides:
- synthetic format-2 case blocks (``build_source_text_v2``) mirroring the
  authored case-set document format (M3-CA0V1-case-set-md-2);
- a provenance sidecar with a complete §3 authoring-independence record
  (``build_sidecar_v2``);
- in-memory candidate builders (``make_candidate``) with targeted defect
  mutation helpers for the four-state decision tests.
"""

import json

from ecp.hashing import hash_document, sha256_hex

VALID_INDEPENDENCE = {
    "author_identity": "test authoring executor (synthetic fixture)",
    "authoring_environment": "test host; Python toolchain; no network",
    "model_tool": "synthetic fixture generator (no model invoked)",
    "model_version": "NOT AVAILABLE (fixture)",
    "prompt_instructions": {"reference": "order M3-CA0 v1 (test fixture)", "sha256": "0" * 64},
    "information_available": ["test fixtures only"],
    "information_unavailable": ["all evaluated-system performance data (none exists)"],
    "relationship_to_ecp_developers": "fixture party, not independent",
    "relationship_to_evaluated_systems": "none (no system accessed)",
    "access_to_prior_ecp_results": "qualification-stage records only; no outcome data exists",
    "independence_status": {
        "label": "NOT-INDEPENDENT — FIXTURE-AUTHORED, PERFORMANCE-BLIND, SYSTEM-NEUTRAL",
        "case_author_independence": "NOT-INDEPENDENT (fixture party)",
        "performance_blindness": "YES-BY-CONSTRUCTION (no outcome data exists)",
        "system_neutrality": "YES-DECLARED (no system access)",
        "note": "fixture record per order §3",
    },
    "validation_procedure": "engine verification only (fixture)",
    "independence_limitations": ["fixture-authored"],
}

VALID_RB = {
    "status": "DISCLOSED",
    "evidence": "fixture evidence: natural-language presentation; formal layer protected",
    "known_limitation": "fixture limitation: representation-sensitive access",
}

VALID_ENV = {
    "knowledge_sources": "fixture: classic logic patterns in public corpora (bounded, declared)",
    "fixtures": "NONE",
    "implementation_artifacts": "NONE",
    "memory_paths": "NOT-APPLICABLE (no execution has occurred)",
    "model_access_paths": "NOT-APPLICABLE (no execution has occurred)",
    "answer_bearing_artifacts": "fixture: GT and formal layer stay in the private area",
}

#: A minimal valid relational-closure case (transitive chain, DERIVABLE).
CASE_BLOCK_T1 = """CASE ID: T-001
PROPOSED_REASONING_FAMILY: transitive-relational
STRUCTURAL_SIGNATURE: fixture 3-entity chain, transitivity + asymmetry
PREMISES:
1. The vex is taller than the lum.
2. The lum is taller than the tor.
3. For any two objects, if the first is taller than the second, then the second is not taller than the first.
4. For any three objects, if the first is taller than the second and the second is taller than the third, then the first is taller than the third.
QUESTION: Is the vex taller than the tor? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A determinate verdict following from the stated relations alone.
INTENDED_CORRECT_ANSWER: Yes — the vex is taller than the tor.
DERIVATION:
1. From premises 1 and 2, by transitivity (premise 4): the vex is taller than the tor.
2. The answer is yes.
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the vex is taller than the tor
FORBIDDEN_SHORTCUTS:
- Do not infer from mention order.
FORMAL:
```json
{
  "semantics": "relational-closure",
  "entities": ["vex", "lum", "tor"],
  "premises": [
    {"kind": "rel_fact", "relation": "taller", "args": ["vex", "lum"]},
    {"kind": "rel_fact", "relation": "taller", "args": ["lum", "tor"]},
    {"kind": "rel_rule", "vars": ["x", "y"], "if": [{"relation": "taller", "args": ["x", "y"]}], "then": {"relation": "taller", "args": ["y", "x"], "negated": true}},
    {"kind": "rel_rule", "vars": ["x", "y", "z"], "if": [{"relation": "taller", "args": ["x", "y"]}, {"relation": "taller", "args": ["y", "z"]}], "then": {"relation": "taller", "args": ["x", "z"]}}
  ],
  "query": {"relation": "taller", "args": ["vex", "tor"]}
}
```
DIFFICULTY: SHALLOW
RETRIEVAL_RISK: fixture: classic transitivity shape, invented entities.
AMBIGUITY_RISK: Low (fixture).
STRUCTURAL_UNIQUENESS_RATIONALE: fixture: minimal three-entity chain.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: fixture evidence: natural-language presentation; formal layer protected.
KNOWN_LIMITATION: fixture limitation: representation-sensitive access.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: fixture: classic logic patterns in public corpora (bounded, declared).
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred).
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred).
ANSWER_BEARING_ARTIFACTS: fixture: GT and formal layer stay in the private area.
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
"""

#: Same structure with renamed entities + relations — identical skeleton
#: (renaming is NOT a new case, order §7).
CASE_BLOCK_T1_RENAMED = CASE_BLOCK_T1.replace("T-001", "T-002").replace("vex", "zib").replace("lum", "pax").replace("tor", "quu").replace("taller", "older")

#: A propositional case (contrapositive, CONTRADICTED).
CASE_BLOCK_P1 = """CASE ID: P-001
PROPOSED_REASONING_FAMILY: conditional-chaining
STRUCTURAL_SIGNATURE: fixture 2-link chain + negated consequent, MT root query
PREMISES:
1. If the mill turns, then the well fills.
2. If the well fills, then the lantern glows.
3. The lantern does not glow.
QUESTION: Does the mill turn? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A refutation via modus tollens through the chain.
INTENDED_CORRECT_ANSWER: No — the mill does not turn.
DERIVATION:
1. If the mill turned, the lantern would glow (premises 1 and 2), contradicting premise 3.
2. The answer is no.
GROUND_TRUTH_CLASS: CONTRADICTED
GROUND_TRUTH_STATEMENT: the mill turns
FORBIDDEN_SHORTCUTS:
- Do not answer cannot be determined.
FORMAL:
```json
{
  "semantics": "propositional-truth-table",
  "props": ["mill", "well", "glow"],
  "premises": [
    {"kind": "impl", "if": ["mill"], "then": "well"},
    {"kind": "impl", "if": ["well"], "then": "glow"},
    {"kind": "prop_fact", "prop": "glow", "value": false}
  ],
  "query": {"prop": "mill", "value": true}
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: fixture: standard MT shape, invented content.
AMBIGUITY_RISK: Low (fixture).
STRUCTURAL_UNIQUENESS_RATIONALE: fixture: two-link MT chain.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: fixture evidence: natural-language presentation; formal layer protected.
KNOWN_LIMITATION: fixture limitation: representation-sensitive access.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: fixture: standard logic shape.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred).
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred).
ANSWER_BEARING_ARTIFACTS: fixture: GT and formal layer stay in the private area.
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
"""

#: A WRONG-GT case: authored class DERIVABLE but the formal layer yields
#: CONTRADICTED (cycle under transitivity + asymmetry).
CASE_BLOCK_X1 = """CASE ID: X-001
PROPOSED_REASONING_FAMILY: transitive-relational
STRUCTURAL_SIGNATURE: fixture 3-entity cycle, mismatched authored class
PREMISES:
1. The fel is heavier than the gam.
2. The gam is heavier than the hup.
3. The hup is heavier than the fel.
4. For any two objects, if the first is heavier than the second, then the second is not heavier than the first.
5. For any three objects, if the first is heavier than the second and the second is heavier than the third, then the first is heavier than the third.
QUESTION: Is the fel heavier than the hup? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A determinate verdict following from the stated relations alone.
INTENDED_CORRECT_ANSWER: Yes — the fel is heavier than the hup.
DERIVATION:
1. From premises 1 and 2, by transitivity: the fel is heavier than the hup.
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the fel is heavier than the hup
FORBIDDEN_SHORTCUTS:
- Do not infer from mention order.
FORMAL:
```json
{
  "semantics": "relational-closure",
  "entities": ["fel", "gam", "hup"],
  "premises": [
    {"kind": "rel_fact", "relation": "heavier", "args": ["fel", "gam"]},
    {"kind": "rel_fact", "relation": "heavier", "args": ["gam", "hup"]},
    {"kind": "rel_fact", "relation": "heavier", "args": ["hup", "fel"]},
    {"kind": "rel_rule", "vars": ["x", "y"], "if": [{"relation": "heavier", "args": ["x", "y"]}], "then": {"relation": "heavier", "args": ["y", "x"], "negated": true}},
    {"kind": "rel_rule", "vars": ["x", "y", "z"], "if": [{"relation": "heavier", "args": ["x", "y"]}, {"relation": "heavier", "args": ["y", "z"]}], "then": {"relation": "heavier", "args": ["x", "z"]}}
  ],
  "query": {"relation": "heavier", "args": ["fel", "hup"]}
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: fixture: cycle shape.
AMBIGUITY_RISK: Low (fixture).
STRUCTURAL_UNIQUENESS_RATIONALE: fixture: three-cycle.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: fixture evidence.
KNOWN_LIMITATION: fixture limitation.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: fixture.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred).
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred).
ANSWER_BEARING_ARTIFACTS: fixture.
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
"""


def build_source_text_v2(case_blocks: "list[str]") -> str:
    """Assemble a format-2 source document from case blocks."""
    parts = ["# synthetic test case-set (format M3-CA0V1-case-set-md-2)", ""]
    for block in case_blocks:
        parts.append(block.rstrip("\n"))
        parts.append("---")
        parts.append("")
    parts.append("AUTHORING PROVENANCE")
    parts.append("author identity: synthetic fixture author")
    parts.append("authored_at: 2026-09-09T00:00:00Z")
    parts.append("")
    return "\n".join(parts)


def build_sidecar_v2(source_sha: str) -> dict:
    """A complete format-2 provenance sidecar (§3 record included)."""
    return {
        "authored_by": {
            "model": "synthetic fixture generator",
            "provider": "test",
            "model_version": "NOT AVAILABLE (fixture)",
            "api_version": "NOT AVAILABLE (fixture)",
        },
        "authored_at": "2026-09-09T00:00:00Z",
        "information_boundary": "isolated",
        "acquisition": {
            "label": "synthetic-test-source.md",
            "sha256": source_sha,
            "acquired_at": "2026-09-09T00:00:00Z",
        },
        "transformation_history": [
            {
                "event": "authored (fixture)",
                "at": "2026-09-09T00:00:00Z",
                "evidence": "tests/qual_fixtures.py",
            }
        ],
        "provenance_completeness": {"status": "COMPLETE", "not_available": []},
        "source_report_flags": ["fixture-authored"],
        "candidate_flags": {},
        "authoring_independence": json.loads(json.dumps(VALID_INDEPENDENCE)),
    }


def make_candidate(candidate_id: str = "ECP-CAND-000101", **overrides) -> dict:
    """A minimal VALID 0.5.0 case-candidate for engine-level tests."""
    formal = {
        "semantics": "propositional-truth-table",
        "props": ["beacon", "gate", "horn", "bridge"],
        "premises": [
            {"kind": "impl", "if": ["beacon"], "then": "gate"},
            {"kind": "impl", "if": ["gate"], "then": "horn"},
            {"kind": "impl", "if": ["horn"], "then": "bridge"},
            {"kind": "prop_fact", "prop": "beacon", "value": True},
        ],
        "query": {"prop": "bridge", "value": True},
    }
    content = {
        "proposed_reasoning_family": "conditional-chaining",
        "structural_signature": "fixture 3-link chain + true antecedent, forward query",
        "premises": [
            "If the beacon is lit, then the gate opens.",
            "If the gate opens, then the horn sounds.",
            "If the horn sounds, then the bridge lowers.",
            "The beacon is lit.",
        ],
        "question": "Does the bridge lower? Answer with: yes, no, or cannot be determined.",
        "intended_correct_answers": [{"value": "Yes — the bridge lowers.", "source_block": 1}],
        "derivations": [
            {"raw": "1. From premise 4 and premise 1: the gate opens.\n2. Thence the horn sounds; thence the bridge lowers.", "source_block": 1}
        ],
        "difficulty": "MEDIUM",
        "retrieval_risk": "fixture: chained conditional shape, invented content.",
        "ambiguity_risk": "Low (fixture).",
        "structural_uniqueness_rationale": "fixture: three-link forward chain.",
        "self_review": {
            "derivable": "Yes",
            "unique": "Yes",
            "self_contained": "Yes",
            "no_external_knowledge": "Yes",
            "no_real_world_dependency": "Yes",
            "structurally_distinct": "Yes",
        },
        "expected_property": "A three-step modus-ponens chain to the terminal consequent.",
        "forbidden_shortcuts": ["Do not conclude without using the antecedent fact."],
        "ground_truth": {"class": "DERIVABLE", "statement": "the bridge lowers"},
        "formal": formal,
    }
    candidate = {
        "ecp_object": "case-candidate",
        "content_class": "review",
        "candidate_id": candidate_id,
        "source": {
            "case_id": "F-001",
            "source_position": 1,
            "source_document": {
                "label": "fixture-source.md",
                "sha256": "0" * 64,
                "format": "M3-CA0V1-case-set-md-2",
            },
        },
        "raw_block": "CASE ID: F-001\n(fixture raw block)",
        "provenance": {
            "authored_by": {"model": "fixture", "provider": "test"},
            "authored_at": "2026-09-09T00:00:00Z",
            "information_boundary": "isolated",
            "acquisition": {"label": "fixture", "sha256": "0" * 64, "acquired_at": "2026-09-09T00:00:00Z"},
            "transformation_history": [
                {"event": "fixture", "at": "2026-09-09T00:00:00Z", "evidence": "tests"}
            ],
            "provenance_completeness": {"status": "COMPLETE", "not_available": []},
        },
        "authoring_independence": json.loads(json.dumps(VALID_INDEPENDENCE)),
        "representation_bias_disclosure": json.loads(json.dumps(VALID_RB)),
        "environmental_pre_check": json.loads(json.dumps(VALID_ENV)),
        "content": content,
        "content_hash": hash_document(content),
        "protocol_version": "0.5.0",
        "schema_version": "0.5.0",
    }
    for dotted_path, value in overrides.items():
        node = candidate
        keys = dotted_path.replace("__", ".").split(".")
        # allow "content__formal__query" style keys for mutation convenience
        for key in keys[:-1]:
            node = node[key]
        if value is _DELETE:
            del node[keys[-1]]
        else:
            node[keys[-1]] = value
    # recompute identity unless the test explicitly tampered with it
    if overrides.get("content_hash") is None and "content_hash" not in overrides:
        candidate["content_hash"] = hash_document(candidate["content"])
    return candidate


class _Delete:
    """Sentinel for field deletion in overrides."""


_DELETE = _Delete()
