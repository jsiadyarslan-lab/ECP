"""CLI smoke tests for the M3-RG0 trust-layer commands.

Runs the real CLI as a subprocess against temporary directories — the
operator's exact shell path. All fixtures are SYNTHETIC DEVELOPMENT
material (format-illustration); the registration-gate refusal path is
exercised exactly as an operator would hit it (order §10: the gate
REFUSES; a successful development-scope test is never an authorization
to register real cases).
"""

import json
import subprocess
import sys
from pathlib import Path

from trust_fixtures import AT, RULINGS, build_observation, build_order, build_package


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


def _example_case(repo_root):
    return json.loads((Path(repo_root) / "examples" / "case.development.example.json").read_text())


def test_cli_trust_init_and_gate(repo_root, tmp_path):
    root = tmp_path / "trust"
    result = _run(repo_root, "trust-init", "--root", str(root), "--trust-id", "ECP-TRUST-CLI-0001", "--scope", "development", "--at", AT)
    assert result.returncode == 0, result.stderr
    manifest = json.loads(result.stdout.split("trust store initialized", 1)[0] + result.stdout[result.stdout.index("{"):])
    assert manifest["ecp_object"] == "trust-store-manifest"
    gate = _run(repo_root, "trust-gate", "--root", str(root))
    assert gate.returncode == 0, gate.stderr
    state = json.loads(gate.stdout[gate.stdout.index("{"):])
    assert state["registration_gate"] == "CLOSED"
    assert state["model_execution_gate"] == "CLOSED"
    assert state["scientific_results"] == "NONE"


def test_cli_trust_verify_clean(repo_root, tmp_path):
    root = tmp_path / "trust"
    _run(repo_root, "trust-init", "--root", str(root), "--trust-id", "ECP-TRUST-CLI-0002", "--scope", "development", "--at", AT)
    result = _run(repo_root, "trust-verify", "--root", str(root))
    assert result.returncode == 0, result.stderr
    assert "TRUST STORE VERIFIED" in result.stdout
    assert "gate CLOSED/CLOSED/NONE" in result.stdout


def test_cli_trust_register_refused_while_closed(repo_root, tmp_path):
    root = tmp_path / "trust"
    _run(repo_root, "trust-init", "--root", str(root), "--trust-id", "ECP-TRUST-CLI-0003", "--scope", "development", "--at", AT)
    package_path = tmp_path / "package.json"
    _write(package_path, build_package(_example_case(repo_root)))
    result = _run(
        repo_root,
        "trust-register",
        "--root", str(root),
        "--registrar", "ECP-REGISTRAR-CLI-0001",
        "--package", str(package_path),
        "--at", AT,
    )
    assert result.returncode == 1
    assert "REFUSED" in result.stderr
    assert "gate is CLOSED" in result.stderr
    # zero registrations exist; the refusal is lineage-logged and the
    # store still verifies clean
    verify = _run(repo_root, "trust-verify", "--root", str(root))
    assert verify.returncode == 0, verify.stderr
    assert "0 registration(s)" in verify.stdout


def test_cli_trust_gate_apply_then_register_then_resolve(repo_root, tmp_path):
    root = tmp_path / "trust"
    _run(repo_root, "trust-init", "--root", str(root), "--trust-id", "ECP-TRUST-CLI-0004", "--scope", "development", "--at", AT)
    order_path = tmp_path / "order.json"
    _write(order_path, build_order())
    applied = _run(repo_root, "trust-gate-apply", "--root", str(root), "--order", str(order_path), "--at", AT)
    assert applied.returncode == 0, applied.stderr
    assert "registration -> OPEN" in applied.stdout

    package_path = tmp_path / "package.json"
    _write(package_path, build_package(_example_case(repo_root)))
    registered = _run(
        repo_root,
        "trust-register",
        "--root", str(root),
        "--registrar", "ECP-REGISTRAR-CLI-0002",
        "--package", str(package_path),
        "--at", AT,
    )
    assert registered.returncode == 0, registered.stderr
    assert "registered: ECP-TREG-000001" in registered.stdout
    summary = json.loads(registered.stdout[registered.stdout.index("{"):])
    assert summary["commitments"]["algorithm"] == "sha256"

    resolved = _run(repo_root, "trust-resolve", "--root", str(root), "--registration", "ECP-TREG-000001")
    assert resolved.returncode == 0, resolved.stderr
    doc = json.loads(resolved.stdout[resolved.stdout.index("{"):])
    assert doc["what_was_registered"]["registration_id"] == "ECP-TREG-000001"
    assert doc["current_state"] == "LIVE"

    verify = _run(repo_root, "trust-verify", "--root", str(root))
    assert verify.returncode == 0, verify.stderr
    assert "1 registration(s)" in verify.stdout


def test_cli_trust_gate_apply_scope_mismatch(repo_root, tmp_path):
    root = tmp_path / "trust"
    _run(repo_root, "trust-init", "--root", str(root), "--trust-id", "ECP-TRUST-CLI-0005", "--scope", "development", "--at", AT)
    order_path = tmp_path / "order.json"
    _write(order_path, build_order(scope="operational"))
    result = _run(repo_root, "trust-gate-apply", "--root", str(root), "--order", str(order_path), "--at", AT)
    assert result.returncode == 1
    assert "scope mismatch" in result.stderr


def test_cli_trust_amend_and_truth(repo_root, tmp_path):
    root = tmp_path / "trust"
    _run(repo_root, "trust-init", "--root", str(root), "--trust-id", "ECP-TRUST-CLI-0006", "--scope", "development", "--at", AT)
    order_path = tmp_path / "order.json"
    _write(order_path, build_order())
    _run(repo_root, "trust-gate-apply", "--root", str(root), "--order", str(order_path), "--at", AT)
    package_path = tmp_path / "package.json"
    package = build_package(_example_case(repo_root))
    _write(package_path, package)
    registered = _run(
        repo_root, "trust-register", "--root", str(root),
        "--registrar", "ECP-REGISTRAR-CLI-0003", "--package", str(package_path), "--at", AT,
    )
    assert registered.returncode == 0, registered.stderr
    summary = json.loads(registered.stdout[registered.stdout.index("{"):])

    amendment_path = tmp_path / "amendment.json"
    _write(
        amendment_path,
        {
            "target_registration_id": "ECP-TREG-000001",
            "target_registration_hash": summary["record_hash"],
            "amendment_kind": "environment-revision",
            "motivation": "cli fixture: environment pin refresh",
            "replacement": {
                "environment": {
                    "environment_id": "ENV-DEV-001",
                    "description": "development fixture environment v2",
                    "pins": {"python": "3.12", "ecp": "0.7.0"},
                }
            },
        },
    )
    amended = _run(
        repo_root, "trust-amend", "--root", str(root),
        "--registrar", "ECP-REGISTRAR-CLI-0003", "--amendment", str(amendment_path), "--at", AT,
    )
    assert amended.returncode == 0, amended.stderr
    assert "amendment recorded: ECP-TAMND-000001" in amended.stdout

    truth = _run(repo_root, "trust-truth", "--root", str(root))
    assert truth.returncode == 0, truth.stderr
    doc = json.loads(truth.stdout[truth.stdout.index("{"):])
    assert len(doc["registrations"]) == 1
    assert len(doc["amendments"]) == 1
    resolved = _run(repo_root, "trust-resolve", "--root", str(root), "--registration", "ECP-TREG-000001")
    state = json.loads(resolved.stdout[resolved.stdout.index("{"):])
    assert state["current_state"] == "AMENDED"
    assert len(state["what_later_happened"]["amendments"]) == 1


def test_cli_trust_runtime_observation(repo_root, tmp_path):
    root = tmp_path / "trust"
    _run(repo_root, "trust-init", "--root", str(root), "--trust-id", "ECP-TRUST-CLI-0007", "--scope", "development", "--at", AT)
    obs_path = tmp_path / "obs.json"
    _write(obs_path, build_observation())
    result = _run(repo_root, "trust-runtime", "--root", str(root), "--observation", str(obs_path), "--at", AT)
    assert result.returncode == 0, result.stderr
    assert "NON-AUTHORITATIVE" in result.stdout
    verify = _run(repo_root, "trust-verify", "--root", str(root))
    assert verify.returncode == 0, verify.stderr
    assert "1 runtime observation(s)" in verify.stdout


def test_cli_trust_runtime_refuses_authoritative_object(repo_root, tmp_path):
    root = tmp_path / "trust"
    _run(repo_root, "trust-init", "--root", str(root), "--trust-id", "ECP-TRUST-CLI-0008", "--scope", "development", "--at", AT)
    bad_path = tmp_path / "bad.json"
    _write(bad_path, {"ecp_object": "trust-registration"})
    result = _run(repo_root, "trust-runtime", "--root", str(root), "--observation", str(bad_path), "--at", AT)
    assert result.returncode == 1
    assert "BOUNDARY VIOLATION" in result.stderr


def test_cli_trust_verify_flags_tampered_record(repo_root, tmp_path):
    root = tmp_path / "trust"
    _run(repo_root, "trust-init", "--root", str(root), "--trust-id", "ECP-TRUST-CLI-0009", "--scope", "development", "--at", AT)
    order_path = tmp_path / "order.json"
    _write(order_path, build_order())
    _run(repo_root, "trust-gate-apply", "--root", str(root), "--order", str(order_path), "--at", AT)
    package_path = tmp_path / "package.json"
    _write(package_path, build_package(_example_case(repo_root)))
    _run(repo_root, "trust-register", "--root", str(root), "--registrar", "ECP-REGISTRAR-CLI-0004", "--package", str(package_path), "--at", AT)
    record_path = root / "authoritative" / "registrations" / "ECP-TREG-000001.json"
    record = json.loads(record_path.read_text())
    record["commitments"]["case"] = "0" * 64
    _write(record_path, record)
    result = _run(repo_root, "trust-verify", "--root", str(root))
    assert result.returncode == 1
    assert "TRUST STORE ISSUES" in result.stdout
    assert "registration_hash does not recompute" in result.stdout


def test_cli_trust_init_refuses_bad_id(repo_root, tmp_path):
    result = _run(repo_root, "trust-init", "--root", str(tmp_path / "x"), "--trust-id", "BAD", "--scope", "development", "--at", AT)
    assert result.returncode == 1
    assert "REJECTED" in result.stderr
