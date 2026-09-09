"""Fixture builders for the M3-CA1 v1 registration-readiness tests.

Provides:
- a synthetic qualified pool (candidates + qualification artifacts + run
  manifest) produced through the REAL qualification engine, so the readiness
  layer is tested against genuine 0.5.0 artifact shapes;
- an owner-decision-register builder with an open-blocking variant (the
  honest undecided state) and a resolved variant (owner rulings supplied);
- population-decision and set-class-designation builders with mutation
  helpers.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # repo src

from ecp.hashing import hash_document_excluding  # noqa: E402
from ecp import qualification as qual  # noqa: E402

from qual_fixtures import make_candidate  # noqa: E402

QUAL_RUN_ID = "ECP-QUALRUN-TEST-CA1"
QUAL_AT = "2026-09-09T00:00:00Z"
OP = "test operator <test@ecp.local>"
RUN_ID = "ECP-RDNYRUN-TEST-CA1"
AT = "2026-09-09T01:00:00Z"

ITEM_QUESTIONS = {
    "O-01": "External novelty-evidence mechanism (fixture question)?",
    "O-02": "Authoring authorization incl. registration-contract pass (fixture question)?",
    "O-03": "Contamination disposition (fixture question)?",
    "O-04": "Ground-truth validation stage (fixture question)?",
}


def _item(item_id: str, state: str, blocking: bool, **overrides) -> dict:
    item = {
        "item_id": item_id,
        "question": ITEM_QUESTIONS[item_id],
        "framework_reference": "fixture framework reference (architecture/threat docs)",
        "options": [
            {"ruling": "AUTHORIZED (fixture)", "consequence": "fixture consequence"},
            {"ruling": "NOT AUTHORIZED (fixture)", "consequence": "fixture consequence"},
            {"ruling": "OWNER DECISION REQUIRED", "consequence": "undecided (honest state)"},
        ],
        "scientific_consequences": "fixture scientific consequences",
        "threats": "fixture threats",
        "state": state,
        "ruling": None,
        "ruling_basis": None,
        "blocking_for_registration": blocking,
        "blocking_basis": "fixture blocking basis" if blocking else None,
        "registration_impact": "fixture registration impact",
        "rationale": "fixture rationale",
    }
    if item_id == "O-01":
        item["evidence_classification"] = "INSUFFICIENT-EVIDENCE"
        item["evidence_basis"] = "fixture evidence basis"
        item["inference_prohibition"] = "fixture: UNRESOLVED is never inferred as NOVEL"
    if state == "RESOLVED":
        item["ruling"] = "AUTHORIZED (fixture ruling)"
        item["ruling_basis"] = "fixture ruling basis"
        item["blocking_for_registration"] = False
        item["blocking_basis"] = None
    for key, value in overrides.items():
        item[key] = value
    return item


def make_register(variant: str = "open-blocking", **overrides) -> dict:
    """An owner-decision-register fixture.

    variant:
      - 'open-blocking'  — all four items REMAINS-OPEN, all blocking (the
        honest undecided state; authorization REFUSED);
      - 'resolved'       — all four items RESOLVED with rulings (nothing
        blocks; authorization may be AUTHORIZED);
      - 'open-mixed'     — O-01/O-04 open+blocking, O-02/O-03 resolved
        (partial progress state).
    """
    if variant == "resolved":
        items = [_item(iid, "RESOLVED", False) for iid in ("O-01", "O-02", "O-03", "O-04")]
    elif variant == "open-mixed":
        items = [
            _item("O-01", "REMAINS-OPEN", True),
            _item("O-02", "RESOLVED", False),
            _item("O-03", "RESOLVED", False),
            _item("O-04", "REMAINS-OPEN", True),
        ]
    else:
        items = [_item(iid, "REMAINS-OPEN", True) for iid in ("O-01", "O-02", "O-03", "O-04")]
    register = {
        "ecp_object": "owner-decision-register",
        "content_class": "review",
        "register_id": "ECP-OWNDEC-000002",
        "order_basis": {"reference": "fixture order reference", "order_reference_sha256": "0" * 64},
        "recorded_at": AT,
        "recorded_by": OP,
        "items": items,
        "findings": [],
        "protocol_version": "0.6.0",
        "schema_version": "0.6.0",
    }
    for key, value in overrides.items():
        if key == "findings":
            register["findings"] = value
        else:
            register[key] = value
    register["register_hash"] = hash_document_excluding(register, "register_hash")
    return register


def make_population(decision: str = "30-ONLY", **overrides) -> dict:
    pop = {
        "ecp_object": "population-decision",
        "decision": decision,
        "rationale": "fixture population rationale",
        "analysis": {"fixture": "analysis blocks"},
    }
    if decision == "OTHER-EXPLICIT":
        pop["explicit_scope"] = overrides.pop("explicit_scope", ["ECP-CAND-000101"])
    for key, value in overrides.items():
        pop[key] = value
    return pop


def make_set_class(candidates: "list[dict]", uniform: str = "PROTECTED", binding_ref=None, overrides_map: "dict | None" = None, **overrides) -> dict:
    designation = {
        "ecp_object": "set-class-designation",
        "assignments": {
            c["candidate_id"]: uniform for c in candidates
        },
        "rationale": "fixture set-class rationale",
        "set_binding_reference": binding_ref,
    }
    if overrides_map:
        designation["assignments"].update(overrides_map)
    for key, value in overrides.items():
        designation[key] = value
    return designation


def make_distinct_candidate(candidate_id: str, chain_len: int, tag: str) -> dict:
    """A distinct DERIVABLE propositional-chain candidate (distinct skeleton:
    different chain length; prop names are renaming-invariant for N3)."""
    prop_names = [f"{tag}_p{i}" for i in range(chain_len + 1)]
    premises_nl = [f"If the {tag} stage {i} completes, then stage {i + 1} begins." for i in range(chain_len)]
    premises_nl.append(f"The {tag} stage 0 completes.")
    formal = {
        "semantics": "propositional-truth-table",
        "props": prop_names,
        "premises": [
            {"kind": "impl", "if": [prop_names[i]], "then": prop_names[i + 1]}
            for i in range(chain_len)
        ]
        + [{"kind": "prop_fact", "prop": prop_names[0], "value": True}],
        "query": {"prop": prop_names[-1], "value": True},
    }
    content = {
        "proposed_reasoning_family": "conditional-chaining",
        "structural_signature": f"fixture {chain_len}-link {tag} chain + true antecedent, forward query",
        "premises": premises_nl,
        "question": f"Does the {tag} stage {chain_len} begin? Answer with: yes, no, or cannot be determined.",
        "intended_correct_answers": [{"value": f"Yes — the {tag} stage {chain_len} begins.", "source_block": 1}],
        "derivations": [
            {"raw": f"1. From the stage-0 fact and the chain: stage {chain_len} begins.", "source_block": 1}
        ],
        "difficulty": "MEDIUM",
        "retrieval_risk": f"fixture: {tag} chained conditional shape, invented content.",
        "ambiguity_risk": "Low (fixture).",
        "structural_uniqueness_rationale": f"fixture: {chain_len}-link forward chain ({tag}).",
        "self_review": {
            "derivable": "Yes",
            "unique": "Yes",
            "self_contained": "Yes",
            "no_external_knowledge": "Yes",
            "no_real_world_dependency": "Yes",
            "structurally_distinct": "Yes",
        },
        "expected_property": f"A {chain_len}-step modus-ponens chain to the terminal stage.",
        "forbidden_shortcuts": ["Do not conclude without using the antecedent fact."],
        "ground_truth": {"class": "DERIVABLE", "statement": f"the {tag} stage {chain_len} begins"},
        "formal": formal,
    }
    candidate = make_candidate(candidate_id=candidate_id)
    candidate["content"] = content
    candidate["source"] = {
        "case_id": f"F-{tag}",
        "source_position": 1,
        "source_document": {
            "label": "fixture-source.md",
            "sha256": "0" * 64,
            "format": "M3-CA0V1-case-set-md-2",
        },
    }
    candidate["raw_block"] = f"CASE ID: F-{tag}\n(fixture raw block {tag})"
    from ecp.hashing import hash_document
    candidate["content_hash"] = hash_document(content)
    return candidate


def make_qualified_pool(count: int = 3, start: int = 101):
    """A synthetic accepted pool (distinct skeletons) through the REAL
    qualification engine.

    Returns (candidates, qualification_run, artifacts).
    """
    specs = [
        ("alpha", 3),
        ("beta", 2),
        ("gamma", 4),
        ("delta", 5),
        ("epsilon", 6),
    ]
    candidates = [
        make_distinct_candidate(f"ECP-CAND-{start + i:06d}", spec[1], spec[0])
        for i, spec in enumerate(specs[:count])
    ]
    result = qual.run_qualification(
        candidates,
        run_id=QUAL_RUN_ID,
        qualified_at=QUAL_AT,
        operator=OP,
        prior_population=[],
    )
    if result["run"]["decisions"]["accept"] != count:
        raise AssertionError("fixture pool did not fully ACCEPT — fixture bug")
    return candidates, result["run"], result["artifacts"]


def rehash_artifact(artifact: dict) -> dict:
    """Recompute an artifact's self hash after a deliberate test mutation."""
    artifact["artifact_hash"] = hash_document_excluding(artifact, "artifact_hash")
    return artifact
