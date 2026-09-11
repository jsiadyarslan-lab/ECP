"""CLI tests for the M3-CA0 case review pipeline commands."""

import json

import pytest

from ca0_fixtures import CASE_A, CASE_B, RESOLVE_ALL, build_sidecar, build_source_text

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
def review_area(tmp_path):
    source_path = tmp_path / "source" / "synthetic-test-source.md"
    source_path.parent.mkdir(parents=True)
    source_text = build_source_text([CASE_A, CASE_B])
    source_path.write_bytes(source_text.encode("utf-8"))
    sidecar_path = tmp_path / "sidecar.json"
    sidecar_path.write_text(
        json.dumps(build_sidecar(sha256_hex(source_text.encode("utf-8")))),
        encoding="utf-8",
    )
    return tmp_path, source_path, sidecar_path


def test_cli_review_extract(repo_root, review_area):
    tmp_path, source_path, sidecar_path = review_area
    result = _run(
        repo_root,
        "review-extract",
        "--source", str(source_path),
        "--provenance", str(sidecar_path),
        "--out", str(tmp_path / "area"),
        "--source-label", "synthetic-test-source.md",
    )
    assert result.returncode == 0, result.stderr
    assert "EXTRACTED: 2 candidates" in result.stdout
    assert "coverage: PASS" in result.stdout
    candidates_dir = tmp_path / "area" / "candidates"
    assert (candidates_dir / "ECP-CAND-000001.json").is_file()
    assert (candidates_dir / "ECP-CAND-000002.json").is_file()
    assert (tmp_path / "area" / "source" / "source-provenance.json").is_file()


def test_cli_review_extract_sidecar_mismatch(repo_root, review_area):
    tmp_path, source_path, _ = review_area
    bad = tmp_path / "bad-sidecar.json"
    sidecar = build_sidecar("0" * 64)
    bad.write_text(json.dumps(sidecar), encoding="utf-8")
    result = _run(
        repo_root,
        "review-extract",
        "--source", str(source_path),
        "--provenance", str(bad),
        "--out", str(tmp_path / "area2"),
    )
    assert result.returncode == 1
    assert "EXTRACTION FAILED" in result.stderr


def test_cli_review_run_and_verify_roundtrip(repo_root, review_area):
    tmp_path, source_path, sidecar_path = review_area
    area = tmp_path / "area"
    extract = _run(
        repo_root, "review-extract",
        "--source", str(source_path), "--provenance", str(sidecar_path),
        "--out", str(area),
    )
    assert extract.returncode == 0, extract.stderr
    # copy the source into the review area for chain verification
    (area / "source" / "synthetic-test-source.md").write_bytes(source_path.read_bytes())
    run = _run(
        repo_root, "review-run",
        "--review-root", str(area),
        "--run-id", "ECP-REVRUN-CLI",
        "--reviewer", "ECP Review Test Executor",
        "--at", "2026-01-03T00:00:00Z",
    )
    assert run.returncode == 0, run.stderr
    assert "requires_review: 2" in run.stdout
    assert "adjudications applied: 0" in run.stdout

    verify = _run(repo_root, "review-verify", "--review-root", str(area))
    assert verify.returncode == 0, verify.stdout
    assert "REVIEW RUN INTACT" in verify.stdout

    scan = _run(repo_root, "boundary-scan", "--review-root", str(area))
    assert scan.returncode == 0, scan.stdout
    assert "REVIEW TREE CLEAN" in scan.stdout


def test_cli_review_verify_detects_tampering(repo_root, review_area):
    tmp_path, source_path, sidecar_path = review_area
    area = tmp_path / "area"
    _run(repo_root, "review-extract", "--source", str(source_path),
         "--provenance", str(sidecar_path), "--out", str(area))
    (area / "source" / "synthetic-test-source.md").write_bytes(source_path.read_bytes())
    _run(repo_root, "review-run", "--review-root", str(area),
         "--run-id", "ECP-REVRUN-CLI", "--reviewer", "ECP Review Test Executor",
         "--at", "2026-01-03T00:00:00Z")
    # tamper with one review artifact
    artifact_path = area / "reviews" / "ECP-REVIEW-000001.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["reason_codes"] = ["ELIGIBLE-ALL-GATES-PASS"]
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    verify = _run(repo_root, "review-verify", "--review-root", str(area))
    assert verify.returncode == 1
    assert "REVIEW VERIFICATION ISSUES" in verify.stdout


def test_cli_review_adjudicate_and_rerun(repo_root, review_area):
    tmp_path, source_path, sidecar_path = review_area
    area = tmp_path / "area"
    _run(repo_root, "review-extract", "--source", str(source_path),
         "--provenance", str(sidecar_path), "--out", str(area))
    (area / "source" / "synthetic-test-source.md").write_bytes(source_path.read_bytes())
    # attach full registration authoring to both candidates
    from ca0_fixtures import FULL_AUTHORING

    for path in sorted((area / "candidates").glob("*.json")):
        candidate = json.loads(path.read_text(encoding="utf-8"))
        candidate["registration_authoring"] = FULL_AUTHORING
        path.write_text(json.dumps(candidate), encoding="utf-8")

    _run(repo_root, "review-run", "--review-root", str(area),
         "--run-id", "ECP-REVRUN-CLI", "--reviewer", "ECP Review Test Executor",
         "--at", "2026-01-03T00:00:00Z")

    # install owner adjudications (the §9 seam) via the CLI
    for index, adjudication in enumerate(RESOLVE_ALL, start=1):
        adj_path = tmp_path / f"adj-{index}.json"
        adj_path.write_text(json.dumps(adjudication), encoding="utf-8")
        recorded = _run(
            repo_root, "review-adjudicate",
            "--review-root", str(area), "--adjudication", str(adj_path),
        )
        assert recorded.returncode == 0, recorded.stderr
        assert "ADJUDICATION RECORDED" in recorded.stdout

    rerun = _run(repo_root, "review-run", "--review-root", str(area),
                 "--run-id", "ECP-REVRUN-CLI", "--reviewer", "ECP Review Test Executor",
                 "--at", "2026-01-04T00:00:00Z")
    assert rerun.returncode == 0, rerun.stderr
    assert "adjudications applied: 2" in rerun.stdout
    # after owner adjudication the fully authored candidates become ELIGIBLE
    assert "eligible: 2" in rerun.stdout

    verify = _run(repo_root, "review-verify", "--review-root", str(area))
    assert verify.returncode == 0, verify.stdout


def test_cli_review_adjudicate_rejects_duplicate(repo_root, review_area):
    tmp_path, source_path, sidecar_path = review_area
    area = tmp_path / "area"
    _run(repo_root, "review-extract", "--source", str(source_path),
         "--provenance", str(sidecar_path), "--out", str(area))
    adj_path = tmp_path / "adj.json"
    adj_path.write_text(json.dumps(RESOLVE_ALL[0]), encoding="utf-8")
    first = _run(repo_root, "review-adjudicate", "--review-root", str(area),
                 "--adjudication", str(adj_path))
    assert first.returncode == 0
    second = _run(repo_root, "review-adjudicate", "--review-root", str(area),
                  "--adjudication", str(adj_path))
    assert second.returncode == 1
    assert "already recorded" in second.stderr


def test_cli_review_adjudicate_rejects_invalid_hash(repo_root, review_area):
    tmp_path, _, _ = review_area
    area = tmp_path / "area"
    (area / "candidates").mkdir(parents=True)
    tampered = dict(RESOLVE_ALL[0])
    tampered["rationale"] = "tampered rationale changes the hash"
    adj_path = tmp_path / "bad-adj.json"
    adj_path.write_text(json.dumps(tampered), encoding="utf-8")
    result = _run(repo_root, "review-adjudicate", "--review-root", str(area),
                  "--adjudication", str(adj_path))
    assert result.returncode == 1
    assert "adjudication_hash mismatch" in result.stdout


def test_cli_review_run_requires_explicit_timestamp(repo_root, review_area):
    tmp_path, source_path, sidecar_path = review_area
    area = tmp_path / "area"
    _run(repo_root, "review-extract", "--source", str(source_path),
         "--provenance", str(sidecar_path), "--out", str(area))
    result = _run(repo_root, "review-run", "--review-root", str(area),
                  "--run-id", "ECP-REVRUN-CLI", "--reviewer", "X")
    assert result.returncode == 2  # argparse: --at is required (no wall clock)
