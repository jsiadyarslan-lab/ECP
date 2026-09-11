"""CLI smoke tests: the foundation tooling works end-to-end from the shell."""

import json
import subprocess
import sys


def _run(repo_root, *argv):
    return subprocess.run(
        [sys.executable, "tools/ecp_cli.py", *argv],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )


def test_cli_identity(repo_root):
    result = _run(repo_root, "identity")
    assert result.returncode == 0
    document = json.loads(result.stdout)
    assert document["protocol_name"] == "ECP"
    # Protocol identity remains 0.7.0; official schema bundle is 0.8.0.
    assert document["protocol_version"] == "0.7.0"
    assert document["schema_version"] == "0.8.0"


def test_cli_validate_valid_document(repo_root):
    result = _run(repo_root, "validate", "--schema", "case", "--file", "examples/case.development.example.json")
    assert result.returncode == 0
    assert "VALID" in result.stdout


def test_cli_validate_invalid_document(repo_root, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"ecp_object": "case"}), encoding="utf-8")
    result = _run(repo_root, "validate", "--schema", "case", "--file", str(bad))
    assert result.returncode == 1
    assert "INVALID" in result.stdout


def test_cli_hash_document(repo_root):
    result = _run(repo_root, "hash", "--doc", "examples/ground-truth.format-example.json")
    assert result.returncode == 0
    assert "sha256" in result.stdout


def test_cli_hash_file(repo_root):
    result = _run(repo_root, "hash", "--file", "examples/artifacts/raw-output.demo.txt")
    assert result.returncode == 0
    assert "sha256" in result.stdout


def test_cli_hash_requires_exactly_one_input(repo_root):
    result = _run(repo_root, "hash")
    assert result.returncode == 2


def test_cli_boundary_scan(repo_root):
    result = _run(repo_root, "boundary-scan")
    assert result.returncode == 0
    assert "CLEAN" in result.stdout


def test_cli_verify_commitment(repo_root):
    result = _run(
        repo_root,
        "verify-commitment",
        "--case", "examples/case.development.example.json",
        "--ground-truth", "examples/ground-truth.format-example.json",
    )
    assert result.returncode == 0
    assert "COMMITMENT VERIFIED" in result.stdout


def test_cli_verify_commitment_detects_tampering(repo_root, tmp_path):
    tampered = tmp_path / "gt.json"
    tampered.write_text(json.dumps({"ecp_object": "ground-truth", "content_class": "format-illustration", "expected_answer": {"answer_kind": "single-value", "value": 999}}), encoding="utf-8")
    result = _run(
        repo_root,
        "verify-commitment",
        "--case", "examples/case.development.example.json",
        "--ground-truth", str(tampered),
    )
    assert result.returncode == 1
    assert "MISMATCH" in result.stdout


def test_cli_manifest_build_and_verify_roundtrip(repo_root, tmp_path):
    out = tmp_path / "manifest.json"
    built = _run(repo_root, "manifest", "build", "--dir", "examples/artifacts", "--out", str(out), "--root", str(repo_root))
    assert built.returncode == 0
    verified = _run(repo_root, "manifest", "verify", "--manifest", str(out), "--root", str(repo_root))
    assert verified.returncode == 0
    assert "INTACT" in verified.stdout
