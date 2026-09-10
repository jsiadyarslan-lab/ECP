"""CLI smoke tests for the R1-I commands (store / ledger / anchoring).

Runs the real CLI as a subprocess against temporary directories — the
operator's exact shell path. Fixtures are synthetic and clearly marked.
"""

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


def _write(path, document):
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def _gt(case_id="ECP-CASE-SYNTH-0001", answer=6):
    return {
        "ecp_object": "ground-truth",
        "content_class": "sealed",
        "case_id": case_id,
        "case_version": "0.1.0",
        "expected_answer": {"answer_kind": "single-value", "value": answer},
        "derivation": [
            {"step": 1, "statement": "SYNTHETIC FIXTURE - not scientific data"},
            {"step": 2, "statement": "double the input value"},
        ],
        "verification_rule": {
            "rule_id": "synth-0001-int",
            "rule_type": "exact-match",
        },
        "seal_note": "SYNTHETIC TEST FIXTURE - never scientific evidence",
        "protocol_version": "0.2.0",
        "schema_version": "0.2.0",
    }


def _public_case(gt, commitment):
    return {
        "ecp_object": "case",
        "case_id": gt["case_id"],
        "case_version": gt["case_version"],
        "case_status": "candidate",
        "case_family": "synthetic",
        "case_definition": {"statement": "SYNTHETIC - not scientific data"},
        "input": {"prompt": "SYNTHETIC - not scientific data"},
        "condition": {"constraints": ["synthetic"], "permitted_resources": []},
        "success_criterion": "synthetic success criterion",
        "verification_rule": {
            "rule_id": "synth-0001-int",
            "rule_type": "exact-match",
            "description": "SYNTHETIC - public description of the synthetic rule",
        },
        "ground_truth_reference": {
            "commitment": commitment,
            "hash_algorithm": "sha256",
            "canonicalization": "ECP-CANONICAL-JSON-1.0",
            "committed_object": "ground-truth",
            "sealing_status": "sealed",
        },
        "authoring_provenance": {
            "authored_at": "2026-09-09T00:00:00Z",
            "author_role": "internal-author",
            "information_boundary": "isolated",
        },
        "protocol_version": "0.2.0",
        "schema_version": "0.2.0",
    }


_SYSTEM = {
    "ecp_object": "system",
    "identity_mode": "model-only",
    "system_id": "ECP-SYSTEM-SYNTH-0001",
    "system_version": "0.1.0",
    "model": {
        "name": "synthetic-model",
        "provider": "synthetic",
        "model_version": "1.0.0",
        "api_version": "1",
    },
    "protocol_version": "0.2.0",
    "schema_version": "0.2.0",
    "case_set_version": "0.1.0",
}


def test_cli_store_roundtrip(repo_root, tmp_path):
    store_root = tmp_path / "store"
    result = _run(
        repo_root, "store-init", "--root", str(store_root),
        "--store-id", "ECP-STORE-CLI-0001", "--scope", "development",
    )
    assert result.returncode == 0, result.stderr

    gt_path = tmp_path / "gt.json"
    _write(gt_path, _gt())
    result = _run(
        repo_root, "store-seal", "--root", str(store_root), "--gt", str(gt_path)
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout[result.stdout.index("{"):])
    assert summary["idempotent"] is False

    result = _run(repo_root, "store-verify", "--root", str(store_root))
    assert result.returncode == 0, result.stdout
    assert "STORE VERIFIED" in result.stdout


def test_cli_store_rejects_write_once_violation(repo_root, tmp_path):
    store_root = tmp_path / "store"
    _run(
        repo_root, "store-init", "--root", str(store_root),
        "--store-id", "ECP-STORE-CLI-0001", "--scope", "development",
    )
    _write(tmp_path / "gt.json", _gt())
    _write(tmp_path / "gt2.json", _gt(answer=999))
    assert _run(
        repo_root, "store-seal", "--root", str(store_root),
        "--gt", str(tmp_path / "gt.json"),
    ).returncode == 0
    result = _run(
        repo_root, "store-seal", "--root", str(store_root),
        "--gt", str(tmp_path / "gt2.json"),
    )
    assert result.returncode == 1
    assert "REJECTED" in result.stderr
    assert "write-once" in result.stderr


def test_cli_full_ceremony(repo_root, tmp_path):
    """store-init → store-seal → ledger-init → register → anchor → verify."""
    store_root = tmp_path / "store"
    ledger_root = tmp_path / "ledger"
    cases = tmp_path / "cases"
    cases.mkdir()

    assert _run(
        repo_root, "store-init", "--root", str(store_root),
        "--store-id", "ECP-STORE-CLI-0001", "--scope", "development",
    ).returncode == 0

    gt_path = tmp_path / "gt.json"
    _write(gt_path, _gt())
    result = _run(
        repo_root, "store-seal", "--root", str(store_root), "--gt", str(gt_path)
    )
    assert result.returncode == 0
    commitment = json.loads(result.stdout[result.stdout.index("{"):])["commitment"]

    case_path = cases / "case.json"
    _write(case_path, _public_case(_gt(), commitment))
    system_path = tmp_path / "system.json"
    _write(system_path, _SYSTEM)

    assert _run(
        repo_root, "ledger-init", "--root", str(ledger_root),
        "--ledger-id", "ECP-LEDGER-CLI-0001",
    ).returncode == 0

    result = _run(
        repo_root, "register", "--ledger", str(ledger_root),
        "--registrar", "ECP-REGISTRAR-CLI-0001", "--case", str(case_path),
        "--store", str(store_root), "--system", str(system_path),
        "--evaluation-id", "ECP-EVAL-CLI-0001",
        "--note", "DEV LEDGER - synthetic fixture - not scientific evidence",
    )
    assert result.returncode == 0, result.stderr
    assert "registered: ECP-REG-000001" in result.stdout

    result = _run(
        repo_root, "anchor-publish", "--ledger", str(ledger_root)
    )
    assert result.returncode == 0, result.stderr
    assert "ANCHOR PUBLISHED" in result.stdout

    result = _run(
        repo_root, "ledger-verify", "--ledger", str(ledger_root),
        "--cases", str(cases),
    )
    assert result.returncode == 0, result.stdout
    assert "LEDGER VERIFIED" in result.stdout
    assert "public-case commitment checks: 1" in result.stdout

    result = _run(
        repo_root, "store-verify", "--root", str(store_root),
        "--cases", str(cases),
    )
    assert result.returncode == 0


def test_cli_register_rejects_duplicate(repo_root, tmp_path):
    store_root = tmp_path / "store"
    ledger_root = tmp_path / "ledger"
    cases = tmp_path / "cases"
    cases.mkdir()
    _run(
        repo_root, "store-init", "--root", str(store_root),
        "--store-id", "ECP-STORE-CLI-0001", "--scope", "development",
    )
    gt_path = tmp_path / "gt.json"
    _write(gt_path, _gt())
    result = _run(
        repo_root, "store-seal", "--root", str(store_root), "--gt", str(gt_path)
    )
    commitment = json.loads(result.stdout[result.stdout.index("{"):])["commitment"]
    case_path = cases / "case.json"
    _write(case_path, _public_case(_gt(), commitment))
    system_path = tmp_path / "system.json"
    _write(system_path, _SYSTEM)
    _run(
        repo_root, "ledger-init", "--root", str(ledger_root),
        "--ledger-id", "ECP-LEDGER-CLI-0001",
    )
    argv = [
        "register", "--ledger", str(ledger_root),
        "--registrar", "ECP-REGISTRAR-CLI-0001", "--case", str(case_path),
        "--store", str(store_root), "--system", str(system_path),
        "--evaluation-id", "ECP-EVAL-CLI-0001",
    ]
    assert _run(repo_root, *argv).returncode == 0
    result = _run(repo_root, *argv)
    assert result.returncode == 1
    assert "REJECTED" in result.stderr


def test_cli_ledger_verify_detects_tamper(repo_root, tmp_path):
    store_root = tmp_path / "store"
    ledger_root = tmp_path / "ledger"
    cases = tmp_path / "cases"
    cases.mkdir()
    _run(
        repo_root, "store-init", "--root", str(store_root),
        "--store-id", "ECP-STORE-CLI-0001", "--scope", "development",
    )
    gt_path = tmp_path / "gt.json"
    _write(gt_path, _gt())
    result = _run(
        repo_root, "store-seal", "--root", str(store_root), "--gt", str(gt_path)
    )
    commitment = json.loads(result.stdout[result.stdout.index("{"):])["commitment"]
    case_path = cases / "case.json"
    _write(case_path, _public_case(_gt(), commitment))
    system_path = tmp_path / "system.json"
    _write(system_path, _SYSTEM)
    _run(
        repo_root, "ledger-init", "--root", str(ledger_root),
        "--ledger-id", "ECP-LEDGER-CLI-0001",
    )
    _run(
        repo_root, "register", "--ledger", str(ledger_root),
        "--registrar", "ECP-REGISTRAR-CLI-0001", "--case", str(case_path),
        "--store", str(store_root), "--system", str(system_path),
        "--evaluation-id", "ECP-EVAL-CLI-0001",
    )
    # tamper: backdate the entry without re-hashing
    entry_path = ledger_root / "entries" / "00000001.json"
    entry = json.loads(entry_path.read_text())
    entry["claimed_at"] = "2001-01-01T00:00:00Z"
    entry_path.write_text(json.dumps(entry), encoding="utf-8")
    result = _run(repo_root, "ledger-verify", "--ledger", str(ledger_root))
    assert result.returncode == 1
    assert "entry_hash does not recompute" in result.stdout


def test_cli_boundary_scan_with_ledger_root(repo_root, tmp_path):
    ledger_root = tmp_path / "ledger"
    _run(
        repo_root, "ledger-init", "--root", str(ledger_root),
        "--ledger-id", "ECP-LEDGER-CLI-0001",
    )
    result = _run(
        repo_root, "boundary-scan", "--ledger-root", str(ledger_root)
    )
    assert result.returncode == 0, result.stdout
    assert "LEDGER TREE CLEAN" in result.stdout

    # protected content planted in the ledger tree → detected
    bad = ledger_root / "records" / "leak.json"
    bad.write_text(json.dumps({"expected_answer": {"value": 42}}), encoding="utf-8")
    result = _run(
        repo_root, "boundary-scan", "--ledger-root", str(ledger_root)
    )
    assert result.returncode == 1
    assert "ledger-ground-truth-content" in result.stdout
    bad.unlink()


def test_cli_validate_new_schemas(repo_root):
    result = _run(
        repo_root, "validate", "--schema", "ledger-entry",
        "--file", "examples/ledger-entry.example.json",
    )
    assert result.returncode == 0
    result = _run(
        repo_root, "validate", "--schema", "store-manifest",
        "--file", "examples/store-manifest.example.json",
    )
    assert result.returncode == 0
