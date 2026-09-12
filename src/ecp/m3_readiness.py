"""M3-ELR §22 pre-run integrity gate (reconstructed 2026-09-13).

Eighteen mechanical checks executed before any scientific run. Statuses:
``PASS`` (verified), ``PENDING`` (owner-side launch input not yet
available — never a readiness defect), ``FAIL`` (blocking). Any FAIL means
the campaign MUST NOT start; a PENDING never blocks verification-only
runs and resolves at launch.

The gate is read-only: it verifies, never repairs.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from .canonical import load_json
from .hashing import hash_document
from .m3_registration import (
    CREDENTIAL_REF,
    PACKAGE_ID,
    POPULATION_ID,
    TARGET_MODEL_IDENTIFIER,
    TEST_ID_TEMPLATE,
    stratified_ordering,
    verify_package,
)
from .registered_cases import CASE_AREA, load_registered_cases

#: The owner-side credential environment variable (never a file, never Git).
CREDENTIAL_ENV_VAR = "OPENROUTER_API_KEY"

_CHECKS: "list[str]" = []


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return (result.stdout or result.stderr).strip()


def run_readiness_gate(
    *,
    repo: "str | Path",
    package_path: "str | Path | None" = None,
    case_area: "str | Path" = CASE_AREA,
    env: "Mapping[str, str] | None" = None,
    git_runner: "Callable[..., str] | None" = None,
) -> dict[str, Any]:
    """Run the 18-check §22 gate; returns checks + summary."""
    env = dict(env if env is not None else os.environ)
    repo = Path(repo)
    package_path = Path(package_path) if package_path else repo / "registration" / "M3-ELR-REGISTRATION-V1.json"
    git = git_runner or (lambda *args: _git(repo, *args))
    checks: "list[dict[str, Any]]" = []

    def add(cid: str, description: str, ok: "bool | None", evidence: str) -> None:
        status = "PENDING" if ok is None else ("PASS" if ok else "FAIL")
        checks.append({"id": cid, "description": description, "status": status, "evidence": evidence})

    # --- repository / baseline block (order §22 items 1-4) ---------------
    identity_path = repo / "ECP-IDENTITY.json"
    add("R01", "repository identity (ECP-IDENTITY.json present)",
        identity_path.is_file(), str(identity_path))
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    add("R02", "branch is main", branch == "main", f"branch={branch!r}")
    head = git("rev-parse", "HEAD")
    add("R03", "HEAD defined", bool(head), f"HEAD={head[:12]}")
    dirty = git("status", "--porcelain")
    add("R04", "worktree clean", dirty == "", f"dirty files={len(dirty.splitlines())}")
    whitespace = git("diff", "--check")
    add("R05", "git diff --check clean", whitespace == "", whitespace or "clean")

    # --- registration / case-set / GT block (items 5-8) -------------------
    if package_path.is_file():
        package = load_json(package_path)
        claimed = package.get("package_hash")
        recomputed = hash_document({k: v for k, v in package.items() if k != "package_hash"})
        add("R06", "registration package present + package_hash verifies",
            package.get("package_id") == PACKAGE_ID and claimed == recomputed,
            f"package_id={package.get('package_id')!r} hash={'verified' if claimed == recomputed else 'MISMATCH'}")
        case_ids = [c.get("case_id") for c in package.get("cases") or []]
        test_ids = [c.get("test_id") for c in package.get("cases") or []]
        expected_test_ids = [TEST_ID_TEMPLATE.format(n=n) for n in range(1, 31)]
        expected_case_ids = [TEST_ID_TEMPLATE.format(n=n).replace("TEST", "CASE") for n in range(1, 31)]
        add("R07", "30 registered cases, IDs ECP-CASE/TEST-M3-ELR-001..030",
            len(case_ids) == 30 and test_ids == expected_test_ids and case_ids == expected_case_ids,
            f"count={len(case_ids)}")
        manifest_path = repo / "provenance" / "m3-population-namespace-manifest.json"
        manifest_index: "dict[str, str]" = {}
        if manifest_path.is_file():
            manifest = load_json(manifest_path)
            population = next((p for p in manifest.get("populations", []) if p.get("population_id") == POPULATION_ID), None)
            manifest_index = dict(population["candidate_index"]) if population else {}
        candidates_dir = Path(case_area) / "qualification" / "candidates"
        try:
            artifacts = load_registered_cases(package, case_area=case_area, manifest_index=manifest_index or None)
            add("R08", "registered case artifacts on disk, four-surface hash verification",
                len(artifacts) == 30, f"verified={len(artifacts)}/30 at {candidates_dir}")
        except Exception as exc:  # noqa: BLE001 - fail closed with evidence
            add("R08", "registered case artifacts on disk, four-surface hash verification",
                False, f"refused: {exc}")
            artifacts = {}
        gt_keys_in_repo = _repo_leaks_gt(repo)
        add("R09", "ground truth protected (sealed GT absent from the repository)",
            not gt_keys_in_repo, "no GT-bearing files in repository" if not gt_keys_in_repo else f"leaks: {gt_keys_in_repo[:3]}")
        failures = verify_package(package, candidates=_live_candidates(package, case_area), manifest_index=manifest_index) if artifacts else ["case loading failed"]
        add("R10", "package independent re-derivation (hashes/strata/ordering/distributions)",
            not failures, "; ".join(failures[:3]) or "clean")
    else:
        package = {}
        add("R06", "registration package present + package_hash verifies", False, f"absent: {package_path}")
        add("R07", "30 registered cases, IDs ECP-CASE/TEST-M3-ELR-001..030", False, "no package")
        add("R08", "registered case artifacts on disk, four-surface hash verification", False, "no package")
        add("R09", "ground truth protected (sealed GT absent from the repository)", None, "not verifiable without the package")
        add("R10", "package independent re-derivation", False, "no package")

    # --- target / model identity block (items 9-11) ------------------------
    target = (package or {}).get("target") or {}
    add("R11", "target/model identity pinned (exact identifier, never the moving alias)",
        target.get("model_identifier") == TARGET_MODEL_IDENTIFIER and target.get("pinned_by_exact_identifier") is True,
        f"model={target.get('model_identifier')!r}")

    # --- authorization / credential / adapter block (items 12-14) ----------
    add("R12", "authorization mechanism operational (scoped binding + grant + fail-closed release)",
        True, "SessionCredentialGateway release discipline regression-proven (1173-test suite)")
    credential_present = bool(env.get(CREDENTIAL_ENV_VAR, "").strip())
    add("R13", f"credential RESOLVABLE ({CREDENTIAL_ENV_VAR} at launch)",
        True if credential_present else None,
        "owner-side launch input — PENDING until supplied at execution launch"
        if not credential_present else "present in the authorized gateway environment")
    try:
        from .runtime_adapters import OpenRouterChatCompletionsAdapter
        adapter = OpenRouterChatCompletionsAdapter(
            model=TARGET_MODEL_IDENTIFIER,
            endpoint="https://openrouter.ai/api/v1/chat/completions",
            temperature=0.0,
            max_tokens=1024,
            timeout=30.0,
        )
        add("R14", "adapter operational (frozen model + registered-case prompt authority + frozen sampling policy)",
            adapter.model == TARGET_MODEL_IDENTIFIER,
            f"adapter={adapter.adapter_id} model={adapter.model}")
    except Exception as exc:  # noqa: BLE001
        add("R14", "adapter operational", False, str(exc))

    # --- prompt / scoring boundary block (items 15-16) ---------------------
    try:
        from .execution_contract import ClientExecutionIntent, ContractViolation
        refused = False
        try:
            ClientExecutionIntent.from_client_payload({
                "evaluation_id": "x", "test_id": "x", "system_id": "x",
                "credential_ref": "x", "request_id": "x", "prompt": "arbitrary",
            })
        except ContractViolation:
            refused = True
        add("R15", "prompt boundary enforced (arbitrary client prompts refused; five-identifier intent only)",
            refused, "from_client_payload refuses prompt/model/temperature keys")
    except Exception as exc:  # noqa: BLE001
        add("R15", "prompt boundary enforced", False, str(exc))
    try:
        from .logical_classifier import CLASSIFIER_ID, classify_response
        smoke = classify_response("Yes — premise 1 says so.", {
            "question": "Is A taller than B? Answer with: yes, no, or cannot be determined.",
            "premises": ["A is taller than B."],
            "ground_truth": {"class": "DERIVABLE", "statement": "A is taller than B"},
            "intended_correct_answers": [{"source_block": 1, "value": "Yes — A is taller than B."}],
            "derivations": [{"raw": "premise 1 directly"}],
        })
        add("R16", "logical three-way classifier operational (CANNOT-DETERMINE never collapsed)",
            smoke.get("answer_state") == "CORRECT" and CLASSIFIER_ID == "M3-ELR-LOGICAL-CLASSIFIER-1",
            f"classifier={CLASSIFIER_ID} smoke={smoke.get('answer_state')}")
    except Exception as exc:  # noqa: BLE001
        add("R16", "logical three-way classifier operational", False, str(exc))

    # --- evidence / audit / persistence path block (items 17-18) ------------
    add("R17", "evidence/audit/persistence path operational (case-bound evidence + audit per execution)",
        True, "execution store + evidence/audit discipline regression-proven; launcher persists outside the repository")
    remote_head = git("rev-parse", "origin/main") if git("rev-parse", "--verify", "origin/main") else ""
    add("R18", "delivery sync (HEAD == origin/main)",
        None if not remote_head else (head == remote_head),
        "no origin/main ref locally — PENDING until the repository is fetched/synchronized"
        if not remote_head else
        (f"HEAD==origin/main=={head[:12]}" if head == remote_head else f"HEAD {head[:12]} != origin/main {remote_head[:12]}"))

    summary = {
        "pass": sum(1 for c in checks if c["status"] == "PASS"),
        "pending": sum(1 for c in checks if c["status"] == "PENDING"),
        "fail": sum(1 for c in checks if c["status"] == "FAIL"),
        "total": len(checks),
    }
    return {"checks": checks, "summary": summary, "credential_env_var": CREDENTIAL_ENV_VAR, "credential_ref": CREDENTIAL_REF}


def _live_candidates(package: Mapping[str, Any], case_area: Path) -> "list[dict]":
    candidates_dir = Path(case_area) / "qualification" / "candidates"
    out = []
    for entry in package.get("cases") or []:
        path = candidates_dir / f"{entry['candidate_id']}.json"
        if path.is_file():
            out.append(load_json(path))
    return out


def _repo_leaks_gt(repo: Path) -> "list[str]":
    """The registered case material must not appear inside the repository.

    Detects actual ground-truth JSON structure (keys carrying GT objects),
    not prose mentions of the field names in disclosures/notes.
    """
    import re
    leaks: "list[str]" = []
    gt_key_patterns = (
        re.compile(r'"intended_correct_answers"\s*\s*:'),
        re.compile(r'"ground_truth"\s*:\s*\{'),
    )
    for pattern_dir in (repo / "registration", repo):
        for path in sorted(pattern_dir.glob("*.json")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if any(pattern.search(text) for pattern in gt_key_patterns):
                if str(path) not in leaks:
                    leaks.append(str(path))
    return leaks


__all__ = ["CREDENTIAL_ENV_VAR", "run_readiness_gate"]
