"""M3-ELR registration contract tests (reconstructed).

Hermetic: builds synthetic CA0v1-style candidates (relational-closure
semantics the qualification engine verifies mechanically) and exercises the
package contract end-to-end without touching the private case area.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecp.hashing import hash_document  # noqa: E402
from ecp.logical_classifier import answer_space_of  # noqa: E402
from ecp.m3_registration import (  # noqa: E402
    HISTORICAL_PACKAGE_HASH,
    OWNER_RULINGS,
    PACKAGE_ID,
    TARGET_MODEL_IDENTIFIER,
    build_package,
    candidate_number,
    gt_commitment,
    intake_verify_candidates,
    load_candidate,
    stratified_ordering,
    verify_package,
)
from ecp.validate import validate_document  # noqa: E402

TERNARY_Q = "Is the a taller than the c? Answer with: yes, no, or cannot be determined."


def make_candidate(n: int, *, family: str, depth: str, gt_class: str = "DERIVABLE", question: str = TERNARY_Q, value: str = "Yes — the a is taller than the c.") -> dict:
    content = {
        "premises": [f"The a is taller than the b.", "The b is taller than the c."],
        "question": question,
        "proposed_reasoning_family": family,
        "difficulty": depth,
        "ground_truth": {"class": gt_class, "statement": "the a is taller than the c"},
        "intended_correct_answers": [{"source_block": 1, "value": value}],
        "derivations": [{"raw": "premises 1 and 2 by transitivity"}],
        "formal": {
            "semantics": "relational-closure",
            "entities": ["a", "b", "c"],
            "premises": [
                {"kind": "rel_fact", "relation": "taller", "args": ["a", "b"]},
                {"kind": "rel_fact", "relation": "taller", "args": ["b", "c"]},
                {
                    "kind": "rel_rule",
                    "vars": ["x", "y", "z"],
                    "if": [
                        {"relation": "taller", "args": ["x", "y"]},
                        {"relation": "taller", "args": ["y", "z"]},
                    ],
                    "then": {"relation": "taller", "args": ["x", "z"]},
                },
            ],
            "query": {"kind": "statement", "relation": "taller", "args": ["a", "c"]},
        },
    }
    return {
        "ecp_object": "case-candidate",
        "candidate_id": f"ECP-CAND-{100 + n:06d}",
        "content": content,
        "content_hash": hash_document(content),
    }


def make_pool() -> "list[dict]":
    families = ["alpha-family", "beta-family"]
    depths = ["DEEP", "MEDIUM", "SHALLOW"]
    pool = []
    n = 1
    for family in families:
        for depth in depths:
            for _ in range(2):
                pool.append(make_candidate(n, family=family, depth=depth))
                n += 1
    return pool


def make_index(pool: "list[dict]") -> dict:
    return {c["candidate_id"]: c["content_hash"] for c in pool}


@pytest.fixture(scope="module")
def pool() -> "list[dict]":
    return make_pool()


@pytest.fixture(scope="module")
def manifest_index(pool) -> dict:
    return make_index(pool)


@pytest.fixture(scope="module")
def package(pool, manifest_index):
    intake = intake_verify_candidates(pool, manifest_index)
    return build_package(
        candidates=pool,
        manifest_index=manifest_index,
        registered_at="2026-09-13T00:00:00Z",
        intake=intake,
    )


def test_load_candidate_verifies_embedded_hash(tmp_path, pool):
    path = tmp_path / f"{pool[0]['candidate_id']}.json"
    path.write_text(__import__("json").dumps(pool[0]), encoding="utf-8")
    loaded = load_candidate(path)
    assert loaded["candidate_id"] == pool[0]["candidate_id"]
    tampered = dict(pool[0])
    tampered["content_hash"] = "0" * 64
    bad = tmp_path / "bad.json"
    bad.write_text(__import__("json").dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError):
        load_candidate(bad)


def test_candidate_number_maps_the_registered_numbering(pool):
    assert candidate_number(pool[0]) == 1
    assert pool[0]["candidate_id"] == "ECP-CAND-000101"


def test_intake_battery_passes_clean_candidates(pool, manifest_index):
    intake = intake_verify_candidates(pool, manifest_index)
    assert all(not v["issues"] for v in intake.values())
    assert all(v["gt_commitment"] and len(v["gt_commitment"]) == 64 for v in intake.values())


def test_intake_battery_flags_manifest_hash_mismatch(pool):
    index = make_index(pool)
    index[pool[0]["candidate_id"]] = "0" * 64
    intake = intake_verify_candidates([pool[0]], index)
    assert any("manifest" in i for i in intake[pool[0]["candidate_id"]]["issues"])


def test_intake_battery_flags_gt_class_mismatch():
    bad = make_candidate(1, family="alpha-family", depth="MEDIUM", gt_class="CONTRADICTED")
    index = {bad["candidate_id"]: bad["content_hash"]}
    intake = intake_verify_candidates([bad], index)
    assert any("does not match" in i for i in intake[bad["candidate_id"]]["issues"])


def test_gt_commitment_is_deterministic_and_content_bound(pool):
    first = gt_commitment(pool[0]["content"])
    second = gt_commitment(dict(pool[0]["content"]))
    assert first == second
    changed = dict(pool[0]["content"])
    changed["ground_truth"] = {"class": "DERIVABLE", "statement": "different"}
    assert gt_commitment(changed) != first


def test_stratified_ordering_rule(pool):
    ordering = stratified_ordering(pool)
    assert [s["reasoning_family"] for s in ordering["strata"]][:2] == ["alpha-family", "alpha-family"]
    assert [s["reasoning_depth"] for s in ordering["strata"]][:3] == ["DEEP", "MEDIUM", "SHALLOW"]
    assert sorted(ordering["ordered_case_numbers"]) == list(range(1, len(pool) + 1))
    # round 1 takes the first member of EACH stratum in stratum order
    assert ordering["ordered_case_numbers"][:6] == [1, 3, 5, 7, 9, 11]
    assert ordering["ordered_case_numbers"][6:] == [2, 4, 6, 8, 10, 12]


def test_package_structure_and_frozen_identities(package):
    assert package["package_id"] == PACKAGE_ID
    assert package["target"]["model_identifier"] == TARGET_MODEL_IDENTIFIER
    assert package["target"]["pinned_by_exact_identifier"] is True
    assert package["condition"]["model_state"] == "MODEL-ENABLED"
    assert package["condition"]["temperature"] == 0.0
    assert package["condition"]["max_tokens"] == 1024
    assert package["condition"]["transport_timeout_seconds"] == 30


def test_package_two_component_population_never_merged(package):
    population = package["population"]
    assert population["component_1"]["registered_count"] == len(package["cases"])
    assert population["component_2"]["registered_count"] == 0
    assert "48" in population["never_merged_into"]


def test_package_cases_carry_commitments_not_ground_truth(package):
    for entry in package["cases"]:
        assert entry["gt_commitment"]
        assert "ground_truth" not in entry
        assert "intended_correct_answers" not in entry
        assert entry["answer_space"] == answer_space_of(
            next(c for c in package["cases"] if c["test_id"] == entry["test_id"]).get("question", TERNARY_Q) if False else TERNARY_Q
        )


def test_package_hash_verifies_and_is_removed_from_digest(package):
    recomputed = hash_document({k: v for k, v in package.items() if k != "package_hash"})
    assert package["package_hash"] == recomputed


def test_verify_package_clean_and_tamper_detecting(package, pool, manifest_index):
    assert verify_package(package, candidates=pool, manifest_index=manifest_index) == []
    tampered = dict(package)
    tampered["target"] = dict(package["target"], model_identifier="openrouter/free")
    failures = verify_package(tampered, candidates=pool, manifest_index=manifest_index)
    assert any("model_identifier" in f for f in failures)
    reordered = dict(package, ordered_test_ids=list(reversed(package["ordered_test_ids"])))
    assert any("ordered_test_ids" in f for f in verify_package(reordered, candidates=pool, manifest_index=manifest_index))


def test_package_validates_against_the_registered_schema(package):
    assert validate_document(package, "m3-registration-package") == []


def test_package_carries_owner_rulings_verbatim_and_historical_hash(package):
    assert package["owner_rulings"]["rulings"] == OWNER_RULINGS["rulings"]
    assert any(d["id"] == "RECONSTRUCTION" and HISTORICAL_PACKAGE_HASH in d["text"] for d in package["disclosures"])
    lock = package["scientific_execution_lock"]
    assert all(lock[k] == "NO" for k in ("case_execution", "provider_call", "model_call", "scoring"))


def test_execution_contract_freezes_single_attempt_and_no_retry(package):
    contract = package["execution_contract"]
    assert contract["attempts_per_test"] == 1
    assert contract["retry_policy"].startswith("NONE")
    assert contract["execution_surface"] == "python run_m3_elr_console.py"
