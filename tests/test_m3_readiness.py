"""M3-ELR §22 readiness gate tests (reconstructed).

Hermetic: a synthetic repository tree + 30-case synthetic package + fake git
runner; verifies PASS/PENDING/FAIL semantics and fail-closed behavior.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecp.hashing import hash_document  # noqa: E402
from ecp.m3_readiness import CREDENTIAL_ENV_VAR, run_readiness_gate  # noqa: E402
from ecp.m3_registration import build_package, intake_verify_candidates  # noqa: E402

TERNARY_Q = "Is the a taller than the c? Answer with: yes, no, or cannot be determined."


def make_candidate(n: int, family: str, depth: str) -> dict:
    content = {
        "premises": ["The a is taller than the b.", "The b is taller than the c."],
        "question": TERNARY_Q,
        "proposed_reasoning_family": family,
        "difficulty": depth,
        "ground_truth": {"class": "DERIVABLE", "statement": "the a is taller than the c"},
        "intended_correct_answers": [{"source_block": 1, "value": "Yes — the a is taller than the c."}],
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


def make_pool_30() -> "list[dict]":
    families = ["f1-family", "f2-family", "f3-family", "f4-family", "f5-family", "f6-family"]
    depths = ["DEEP", "MEDIUM", "SHALLOW"]
    pool = []
    n = 1
    for family in families:
        for i, depth in enumerate(depths + ["MEDIUM", "SHALLOW"]):
            pool.append(make_candidate(n, family=family, depth=depth))
            n += 1
    return pool


@pytest.fixture()
def site(tmp_path):
    """Synthetic repository + private case area carrying a 30-case package."""
    repo = tmp_path / "repo"
    (repo / "registration").mkdir(parents=True)
    (repo / "provenance").mkdir()
    (repo / "ECP-IDENTITY.json").write_text(json.dumps({"protocol": "ecp"}), encoding="utf-8")
    area = tmp_path / "area"
    candidates_dir = area / "qualification" / "candidates"
    candidates_dir.mkdir(parents=True)
    pool = make_pool_30()
    index = {}
    for candidate in pool:
        (candidates_dir / f"{candidate['candidate_id']}.json").write_text(json.dumps(candidate), encoding="utf-8")
        index[candidate["candidate_id"]] = candidate["content_hash"]
    manifest = {"populations": [{"population_id": "ECP-POP-M3-CA0V1-V1", "candidate_index": index}]}
    (repo / "provenance" / "m3-population-namespace-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    intake = intake_verify_candidates(pool, index)
    package = build_package(candidates=pool, manifest_index=index, registered_at="2026-09-13T00:00:00Z", intake=intake)
    package_path = repo / "registration" / "M3-ELR-REGISTRATION-V1.json"
    package_path.write_text(json.dumps(package, indent=2, sort_keys=True), encoding="utf-8")

    head = "a" * 40

    def clean_git(*args):
        if args[:2] == ("rev-parse", "--abbrev-ref"):
            return "main"
        if args[:2] == ("rev-parse", "HEAD"):
            return head
        if args[:2] == ("status", "--porcelain"):
            return ""
        if args[:2] == ("diff", "--check"):
            return ""
        if args[:2] == ("rev-parse", "--verify"):
            return head
        if args[:2] == ("rev-parse", "origin/main"):
            return head
        return ""

    return {"repo": repo, "area": area, "package": package, "package_path": package_path, "git": clean_git, "head": head}


def run(site, **kwargs):
    return run_readiness_gate(
        repo=site["repo"],
        package_path=site["package_path"],
        case_area=site["area"],
        env=kwargs.pop("env", {}),
        git_runner=kwargs.pop("git", site["git"]),
    )


def test_gate_reports_eighteen_checks_with_expected_ids(site):
    gate = run(site)
    ids = [c["id"] for c in gate["checks"]]
    assert len(ids) == 18 and ids[0] == "R01" and ids[-1] == "R18"
    assert gate["summary"]["total"] == 18


def test_clean_site_yields_17_pass_1_pending_0_fail(site):
    gate = run(site)
    assert gate["summary"] == {"pass": 17, "pending": 1, "fail": 0, "total": 18}
    pending = [c for c in gate["checks"] if c["status"] == "PENDING"]
    assert [c["id"] for c in pending] == ["R13"]  # credential is an owner-side launch input


def test_credential_pending_resolves_to_pass_when_env_supplied(site):
    gate = run(site, env={CREDENTIAL_ENV_VAR: "sk-live-key"})
    assert gate["summary"] == {"pass": 18, "pending": 0, "fail": 0, "total": 18}


def test_dirty_worktree_fails_the_gate(site):
    def dirty_git(*args):
        if args[:2] == ("status", "--porcelain"):
            return " M src/ecp/console.py"
        return site["git"](*args)

    gate = run(site, git=dirty_git)
    assert gate["summary"]["fail"] >= 1
    by_id = {c["id"]: c for c in gate["checks"]}
    assert by_id["R04"]["status"] == "FAIL"


def test_tampered_package_hash_fails_the_gate(site):
    tampered = dict(site["package"])
    tampered["condition"] = dict(site["package"]["condition"], temperature=1.5)
    site["package_path"].write_text(json.dumps(tampered, indent=2, sort_keys=True), encoding="utf-8")
    gate = run(site)
    by_id = {c["id"]: c for c in gate["checks"]}
    assert by_id["R06"]["status"] == "FAIL"


def test_missing_case_artifacts_fail_closed(site):
    import shutil

    shutil.rmtree(site["area"] / "qualification")
    gate = run(site)
    by_id = {c["id"]: c for c in gate["checks"]}
    assert by_id["R08"]["status"] == "FAIL"


def test_delivery_sync_pending_without_remote_and_fail_on_divergence(site):
    def no_remote_git(*args):
        if args[:2] == ("rev-parse", "--verify"):
            return ""  # no origin/main ref
        return site["git"](*args)

    gate = run(site, git=no_remote_git)
    by_id = {c["id"]: c for c in gate["checks"]}
    assert by_id["R18"]["status"] == "PENDING"

    def diverged_git(*args):
        if args[:2] == ("rev-parse", "origin/main"):
            return "b" * 40
        return site["git"](*args)

    gate2 = run(site, git=diverged_git)
    by_id2 = {c["id"]: c for c in gate2["checks"]}
    assert by_id2["R18"]["status"] == "FAIL"
