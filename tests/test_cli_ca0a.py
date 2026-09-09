"""CLI tests for the M3-CA0-A case qualification commands.

Covers the physically separate two-step amendment process:

- ``amendment-draft`` (STEP 1) — refuses to be run with disclosure
  inputs; produces a PENDING draft that the review pipeline REFUSES;
- ``amendment-disclose`` (STEP 2) — completes the disclosure on the
  existing draft (machine-evidenced post-draft timing); re-running it
  on a completed record is refused;
- ``review-run`` with amendments + lineage → full re-review of the
  derived v2 view; ``review-verify`` re-derives deterministically
  under the stored engine profile and validates amendment records;
- the boundary scan accepts ``amendments/`` and case-amendment objects;
- the public repo boundary still rejects real review material outside
  a private review area (no leak of GT-class content).

All case material is SYNTHETIC.
"""

import json

import pytest

from ca0_fixtures import CASE_A, build_sidecar, build_source_text

from ecp.hashing import sha256_hex


def _run(repo_root, *argv):
    import subprocess
    import sys

    return subprocess.run(
        [sys.executable, "tools/ecp_cli.py", *argv],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )


@pytest.fixture()
def dual_review_area(repo_root, tmp_path):
    """A review area whose candidate ECP-CAND-000001 carries a dual-block
    GT document (conflicting authored answers — the C-007-style anomaly)."""
    from test_adjudication import _dual_block_candidate

    source_text = build_source_text([CASE_A])
    source_path = tmp_path / "source" / "synthetic-test-source.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(source_text, encoding="utf-8")
    sidecar_path = tmp_path / "sidecar.json"
    sidecar_path.write_text(
        json.dumps(build_sidecar(sha256_hex(source_text.encode("utf-8")))),
        encoding="utf-8",
    )
    area = tmp_path / "area"
    extract = _run(
        repo_root, "review-extract",
        "--source", str(source_path), "--provenance", str(sidecar_path),
        "--out", str(area),
    )
    assert extract.returncode == 0, extract.stderr
    # splice the dual-block variant over the extracted candidate
    dual = _dual_block_candidate()
    (area / "candidates" / "ECP-CAND-000001.json").write_text(
        json.dumps(dual, indent=2, sort_keys=True), encoding="utf-8"
    )
    (area / "source" / "synthetic-test-source.md").write_text(
        source_text, encoding="utf-8"
    )
    return area


DRAFT_ARGS = [
    "--amendment-id", "ECP-AMD-000001",
    "--order-basis", "M3-CA0-A v1 §5",
    "--defect-code", "SPEC-AMBIGUOUS-GT",
    "--defect-description", "duplicated GT blocks, stale conflicting answer",
    "--defect-why", "the removed block is contradicted by its own derivation",
    "--defect-evidence", "retained derivation self-corrects to the retained answer",
    "--retained-answer-block", "1",
    "--retained-derivation-block", "2",
    "--removed-answer-blocks", "2",
    "--removed-derivation-blocks", "1",
    "--not-outcome-statement", "selection is case-internal premise analysis only",
    "--not-outcome-basis", "zero evaluated-system executions exist for this set",
    "--amendment-author", "ECP Test Amendment Author",
    "--drafted-at", "2026-02-01T00:00:00Z",
    "--operator", "ECP Review Test Executor",
    "--order-reference", "M3-CA0-A test order",
]


def test_cli_amendment_draft_then_pending_refused_by_run(repo_root, dual_review_area):
    area = dual_review_area
    draft = _run(
        repo_root, "amendment-draft",
        "--candidate", str(area / "candidates" / "ECP-CAND-000001.json"),
        *DRAFT_ARGS,
        "--review-root", str(area),
    )
    assert draft.returncode == 0, draft.stderr
    assert "AMENDMENT DRAFTED (STEP 1" in draft.stdout
    assert "disclosure PENDING" in draft.stdout
    draft_path = area / "amendments" / "ECP-AMD-000001.json"
    assert draft_path.is_file()
    record = json.loads(draft_path.read_text(encoding="utf-8"))
    assert record["disclosure_phase"]["status"] == "PENDING"
    assert "representation_bias_disclosure" not in record

    # a PENDING amendment cannot be applied by a review run
    run = _run(
        repo_root, "review-run",
        "--review-root", str(area),
        "--run-id", "ECP-REVRUN-CA0A-CLI",
        "--reviewer", "ECP Review Test Executor",
        "--at", "2026-02-04T00:00:00Z",
    )
    assert run.returncode == 1
    assert "REVIEW RUN FAILED" in run.stderr
    assert "PENDING" in run.stderr


def test_cli_amendment_disclose_completes_and_re_review(repo_root, dual_review_area):
    area = dual_review_area
    draft = _run(
        repo_root, "amendment-draft",
        "--candidate", str(area / "candidates" / "ECP-CAND-000001.json"),
        *DRAFT_ARGS,
        "--review-root", str(area),
    )
    assert draft.returncode == 0, draft.stderr

    disclose = _run(
        repo_root, "amendment-disclose",
        "--amendment", str(area / "amendments" / "ECP-AMD-000001.json"),
        "--value", "POSSIBLE",
        "--completed-by", "ECP Test Amendment Author",
        "--completed-at", "2026-02-02T00:00:00Z",
        "--basis", "test fixture: plausible influence cannot be excluded",
    )
    assert disclose.returncode == 0, disclose.stderr
    assert "AMENDMENT DISCLOSURE COMPLETED (STEP 2)" in disclose.stdout
    assert "never silently treated as unbiased" in disclose.stdout
    record = json.loads(
        (area / "amendments" / "ECP-AMD-000001.json").read_text(encoding="utf-8")
    )
    assert record["disclosure_phase"]["status"] == "COMPLETED"
    assert record["representation_bias_disclosure"]["value"] == "POSSIBLE"

    # re-disclosing a completed record is refused
    again = _run(
        repo_root, "amendment-disclose",
        "--amendment", str(area / "amendments" / "ECP-AMD-000001.json"),
        "--value", "NONE",
        "--completed-by", "x",
        "--completed-at", "2026-02-03T00:00:00Z",
        "--basis", "re-disclosure attempt",
    )
    assert again.returncode == 1

    # full re-review with the amendment + lineage
    run = _run(
        repo_root, "review-run",
        "--review-root", str(area),
        "--run-id", "ECP-REVRUN-CA0A-CLI",
        "--reviewer", "ECP Review Test Executor",
        "--at", "2026-02-04T00:00:00Z",
        "--prior-run-id", "ECP-REVRUN-PRIOR",
        "--prior-run-hash", "a" * 64,
    )
    assert run.returncode == 0, run.stderr
    assert "amendments applied: 1" in run.stdout
    assert "ECP-AMD-000001" in run.stdout
    assert "lineage: ECP-REVRUN-PRIOR" in run.stdout

    # the amended artifact carries v2 + linkage + disclosure
    artifact = json.loads(
        (area / "reviews" / "ECP-REVIEW-000001.json").read_text(encoding="utf-8")
    )
    assert artifact["amendment"]["amendment_id"] == "ECP-AMD-000001"
    assert artifact["amendment"]["representation_bias_disclosure"] == "POSSIBLE"
    assert artifact["amendment"]["case_version"] == 2
    gt_conflict_codes = [
        q["code"] for q in artifact["open_questions"]
        if q["code"] == "OQ-SPEC-GT-CONFLICT"
    ]
    assert gt_conflict_codes == []

    # verification: re-derivation incl. amendment is byte-identical
    verify = _run(repo_root, "review-verify", "--review-root", str(area))
    assert verify.returncode == 0, verify.stdout
    assert "REVIEW RUN INTACT" in verify.stdout

    # boundary scan accepts the amendments directory
    scan = _run(repo_root, "boundary-scan", "--review-root", str(area))
    assert scan.returncode == 0, scan.stdout
    assert "REVIEW TREE CLEAN" in scan.stdout


def test_cli_amendment_draft_refuses_disclosure_value(repo_root, dual_review_area):
    area = dual_review_area
    draft = _run(
        repo_root, "amendment-draft",
        "--candidate", str(area / "candidates" / "ECP-CAND-000001.json"),
        *DRAFT_ARGS,
        "--review-root", str(area),
        "--disclosure-value", "NONE",  # the forbidden concurrent disclosure
    )
    # argparse rejects the unknown flag outright: drafting has NO
    # disclosure parameter at all
    assert draft.returncode != 0


def test_cli_amendment_disclose_rejects_bad_value(repo_root, dual_review_area):
    area = dual_review_area
    draft = _run(
        repo_root, "amendment-draft",
        "--candidate", str(area / "candidates" / "ECP-CAND-000001.json"),
        *DRAFT_ARGS,
        "--review-root", str(area),
    )
    assert draft.returncode == 0, draft.stderr
    disclose = _run(
        repo_root, "amendment-disclose",
        "--amendment", str(area / "amendments" / "ECP-AMD-000001.json"),
        "--value", "CERTAINLY-NOT",  # outside the enum
        "--completed-by", "x",
        "--completed-at", "2026-02-02T00:00:00Z",
        "--basis", "self-certification attempt",
    )
    assert disclose.returncode != 0


def test_cli_amendment_draft_rejects_append_overwrite(repo_root, dual_review_area):
    area = dual_review_area
    first = _run(
        repo_root, "amendment-draft",
        "--candidate", str(area / "candidates" / "ECP-CAND-000001.json"),
        *DRAFT_ARGS,
        "--review-root", str(area),
    )
    assert first.returncode == 0, first.stderr
    second = _run(
        repo_root, "amendment-draft",
        "--candidate", str(area / "candidates" / "ECP-CAND-000001.json"),
        *DRAFT_ARGS,
        "--review-root", str(area),
    )
    assert second.returncode == 1
    assert "already exists" in second.stderr


def test_cli_verify_detects_tampered_amendment(repo_root, dual_review_area):
    area = dual_review_area
    draft = _run(
        repo_root, "amendment-draft",
        "--candidate", str(area / "candidates" / "ECP-CAND-000001.json"),
        *DRAFT_ARGS,
        "--review-root", str(area),
    )
    assert draft.returncode == 0, draft.stderr
    _run(
        repo_root, "amendment-disclose",
        "--amendment", str(area / "amendments" / "ECP-AMD-000001.json"),
        "--value", "POSSIBLE",
        "--completed-by", "ECP Test Amendment Author",
        "--completed-at", "2026-02-02T00:00:00Z",
        "--basis", "test fixture",
    )
    run = _run(
        repo_root, "review-run",
        "--review-root", str(area),
        "--run-id", "ECP-REVRUN-CA0A-CLI",
        "--reviewer", "ECP Review Test Executor",
        "--at", "2026-02-04T00:00:00Z",
    )
    assert run.returncode == 0, run.stderr

    # tamper the amendment record's defect evidence
    path = area / "amendments" / "ECP-AMD-000001.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["defect"]["evidence"] = "retroactively altered evidence"
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    verify = _run(repo_root, "review-verify", "--review-root", str(area))
    assert verify.returncode == 1
    combined = (verify.stdout + verify.stderr).lower()
    assert "amendment" in combined


def test_cli_legacy_run_still_verifies_after_engine_bump(repo_root, review_area_030):
    """A 0.3.0-profile run manifest re-verifies under the 0.4.0 toolchain
    (byte-identical re-derivation via the stored engine profile)."""
    area = review_area_030
    verify = _run(repo_root, "review-verify", "--review-root", str(area))
    assert verify.returncode == 0, verify.stdout
    assert "REVIEW RUN INTACT" in verify.stdout


@pytest.fixture()
def review_area_030(repo_root, tmp_path):
    """A review area whose run manifest was produced by the 0.3.0 engine
    profile (simulating a preserved M3-CA0-era run)."""
    source_text = build_source_text([CASE_A])
    source_path = tmp_path / "source" / "synthetic-test-source.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(source_text, encoding="utf-8")
    sidecar_path = tmp_path / "sidecar.json"
    sidecar_path.write_text(
        json.dumps(build_sidecar(sha256_hex(source_text.encode("utf-8")))),
        encoding="utf-8",
    )
    area = tmp_path / "area"
    extract = _run(
        repo_root, "review-extract",
        "--source", str(source_path), "--provenance", str(sidecar_path),
        "--out", str(area),
    )
    assert extract.returncode == 0, extract.stderr
    (area / "source" / "synthetic-test-source.md").write_text(
        source_text, encoding="utf-8"
    )
    # produce the run under the legacy profile via the module API
    import sys

    sys.path.insert(0, str(repo_root / "src"))
    from ecp.canonical import canonical_bytes, load_json
    from ecp.review import run_review

    candidates = [
        load_json(p) for p in sorted((area / "candidates").glob("*.json"))
    ]
    result = run_review(
        candidates,
        run_id="ECP-REVRUN-LEGACY",
        reviewed_at="2026-01-03T00:00:00Z",
        operator="ECP Review Test Executor",
        source_text=source_text,
        source_label="source/synthetic-test-source.md",
        engine_profile="0.3.0",
    )
    reviews_dir = area / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    for artifact in result["artifacts"]:
        (reviews_dir / f"{artifact['review_id']}.json").write_bytes(
            canonical_bytes(artifact)
        )
    (area / "review-run.json").write_bytes(canonical_bytes(result["run"]))
    return area
