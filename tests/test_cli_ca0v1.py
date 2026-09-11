"""CLI tests for the M3-CA0 v1 authoring + qualification commands.

End-to-end round trip on a synthetic qualification area:
authoring-intake -> qualify-run -> qualify-verify (INTACT), plus tamper
detection and the prior-population cross-novelty path.
"""

import json

import pytest

from qual_fixtures import (
    CASE_BLOCK_T1,
    CASE_BLOCK_T1_RENAMED,
    CASE_BLOCK_X1,
    build_sidecar_v2,
    build_source_text_v2,
)

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
def qualify_area(tmp_path):
    """A three-case area: one valid, one renamed duplicate (REVISE), one
    wrong ground truth (REJECT)."""
    source_path = tmp_path / "source" / "synthetic-v2-source.md"
    source_path.parent.mkdir(parents=True)
    source_text = build_source_text_v2([CASE_BLOCK_T1, CASE_BLOCK_T1_RENAMED, CASE_BLOCK_X1])
    source_path.write_bytes(source_text.encode("utf-8"))
    sidecar_path = tmp_path / "sidecar.json"
    sidecar_path.write_text(
        json.dumps(build_sidecar_v2(sha256_hex(source_text.encode("utf-8")))),
        encoding="utf-8",
    )
    return tmp_path, source_path, sidecar_path


def test_cli_authoring_intake(repo_root, qualify_area):
    tmp_path, source_path, sidecar_path = qualify_area
    result = _run(
        repo_root,
        "authoring-intake",
        "--source", str(source_path),
        "--sidecar", str(sidecar_path),
        "--out", str(tmp_path / "area"),
        "--source-label", "synthetic-v2-source.md",
    )
    assert result.returncode == 0, result.stderr
    assert "AUTHORING INTAKE COMPLETE: 3 candidates" in result.stdout
    candidates_dir = tmp_path / "area" / "candidates"
    assert (candidates_dir / "ECP-CAND-000101.json").is_file()
    assert (candidates_dir / "ECP-CAND-000103.json").is_file()
    assert (tmp_path / "area" / "intake-report.json").is_file()
    report = json.loads((tmp_path / "area" / "intake-report.json").read_text())
    assert report["coverage"]["status"] == "PASS"


def test_cli_authoring_intake_sidecar_mismatch(repo_root, qualify_area):
    tmp_path, source_path, _ = qualify_area
    bad = tmp_path / "bad-sidecar.json"
    bad.write_text(json.dumps(build_sidecar_v2("0" * 64)), encoding="utf-8")
    result = _run(
        repo_root,
        "authoring-intake",
        "--source", str(source_path),
        "--sidecar", str(bad),
        "--out", str(tmp_path / "area2"),
    )
    assert result.returncode == 1
    assert "does not match" in result.stderr


def test_cli_qualify_run_and_verify_round_trip(repo_root, qualify_area):
    tmp_path, source_path, sidecar_path = qualify_area
    area = tmp_path / "area"
    intake = _run(
        repo_root, "authoring-intake",
        "--source", str(source_path), "--sidecar", str(sidecar_path),
        "--out", str(area), "--source-label", "synthetic-v2-source.md",
    )
    assert intake.returncode == 0, intake.stderr

    run = _run(
        repo_root, "qualify-run",
        "--qualify-root", str(area),
        "--run-id", "ECP-QUALRUN-TEST-R1",
        "--operator", "test operator <test@ecp.local>",
        "--at", "2026-09-09T00:00:00Z",
    )
    assert run.returncode == 0, run.stderr
    assert "ACCEPT=1 REVISE=1 REJECT=1 INCONCLUSIVE=0 (of 3 candidates)" in run.stdout
    run_doc = json.loads((area / "qualification-run.json").read_text())
    assert run_doc["run_id"] == "ECP-QUALRUN-TEST-R1"
    assert run_doc["decisions"] == {"accept": 1, "revise": 1, "reject": 1, "inconclusive": 0}
    decisions = {e["candidate_id"]: e["decision"] for e in run_doc["entries"]}
    assert decisions == {
        "ECP-CAND-000101": "ACCEPT",
        "ECP-CAND-000102": "REVISE",   # renamed duplicate of 101
        "ECP-CAND-000103": "REJECT",   # wrong ground truth (cycle vs DERIVABLE claim)
    }

    verify = _run(
        repo_root, "qualify-verify", "--qualify-root", str(area),
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "QUALIFICATION RUN INTACT" in verify.stdout
    assert "determinism re-derivation all verified" in verify.stdout


def test_cli_qualify_verify_detects_tampering(repo_root, qualify_area):
    tmp_path, source_path, sidecar_path = qualify_area
    area = tmp_path / "area"
    assert _run(repo_root, "authoring-intake",
                "--source", str(source_path), "--sidecar", str(sidecar_path),
                "--out", str(area)).returncode == 0
    assert _run(repo_root, "qualify-run",
                "--qualify-root", str(area), "--run-id", "ECP-QUALRUN-TEST-R2",
                "--operator", "test operator <test@ecp.local>",
                "--at", "2026-09-09T00:00:00Z").returncode == 0

    # 1) tamper a stored artifact's decision field (hash not recomputed)
    artifact_path = area / "qualification" / "ECP-QUAL-000102.json"
    artifact = json.loads(artifact_path.read_text())
    artifact["decision"] = "ACCEPT"
    artifact_path.write_text(json.dumps(artifact, sort_keys=True), encoding="utf-8")

    result = _run(repo_root, "qualify-verify", "--qualify-root", str(area))
    assert result.returncode == 1
    assert "recomputation mismatch" in result.stdout

    # 2) tamper a RETAINED INPUT (candidate premises): the stored artifacts
    #    no longer re-derive from the inputs -> DETERMINISM VIOLATION
    assert _run(repo_root, "qualify-run",
                "--qualify-root", str(area), "--run-id", "ECP-QUALRUN-TEST-R2",
                "--operator", "test operator <test@ecp.local>",
                "--at", "2026-09-09T00:00:00Z").returncode == 0
    candidate_path = area / "candidates" / "ECP-CAND-000101.json"
    candidate = json.loads(candidate_path.read_text())
    candidate["content"]["premises"][0] = "The vex is shorter than the lum."
    candidate_path.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")

    result2 = _run(repo_root, "qualify-verify", "--qualify-root", str(area))
    assert result2.returncode == 1
    assert "DETERMINISM VIOLATION" in result2.stdout


def test_cli_qualify_run_with_prior_population(repo_root, qualify_area, tmp_path):
    """The prior-population path: an exact cross-population duplicate is
    REJECTED with N4 evidence."""
    tmp_path, source_path, sidecar_path = qualify_area
    area = tmp_path / "area"
    prior_dir = tmp_path / "prior"
    prior_dir.mkdir()
    assert _run(repo_root, "authoring-intake",
                "--source", str(source_path), "--sidecar", str(sidecar_path),
                "--out", str(area)).returncode == 0

    # a prior-pool candidate with identical premise text to ECP-CAND-000101
    candidate = json.loads((area / "candidates" / "ECP-CAND-000101.json").read_text())
    prior = json.loads(json.dumps(candidate))
    prior["candidate_id"] = "ECP-CAND-000001"
    prior["content"]["structural_signature"] = "prior sig"
    from ecp.hashing import hash_document

    prior["content_hash"] = hash_document(prior["content"])
    (prior_dir / "ECP-CAND-000001.json").write_text(
        json.dumps(prior, sort_keys=True), encoding="utf-8"
    )

    result = _run(
        repo_root, "qualify-run",
        "--qualify-root", str(area),
        "--run-id", "ECP-QUALRUN-TEST-R3",
        "--operator", "test operator <test@ecp.local>",
        "--at", "2026-09-09T00:00:00Z",
        "--prior-candidates", str(prior_dir),
    )
    assert result.returncode == 0, result.stderr
    run_doc = json.loads((area / "qualification-run.json").read_text())
    assert run_doc["prior_population"]["count"] == 1
    decisions = {e["candidate_id"]: e["decision"] for e in run_doc["entries"]}
    assert decisions["ECP-CAND-000101"] == "REJECT"  # exact cross-pop duplicate
    assert decisions["ECP-CAND-000103"] == "REJECT"

    verify = _run(
        repo_root, "qualify-verify",
        "--qualify-root", str(area), "--prior-candidates", str(prior_dir),
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "QUALIFICATION RUN INTACT" in verify.stdout


def test_cli_qualify_run_requires_candidates(repo_root, tmp_path):
    empty = tmp_path / "empty-area"
    (empty / "candidates").mkdir(parents=True)
    result = _run(
        repo_root, "qualify-run",
        "--qualify-root", str(empty),
        "--run-id", "ECP-QUALRUN-TEST-R4",
        "--operator", "test operator <test@ecp.local>",
        "--at", "2026-09-09T00:00:00Z",
    )
    assert result.returncode == 2
    assert "no candidates" in result.stderr
