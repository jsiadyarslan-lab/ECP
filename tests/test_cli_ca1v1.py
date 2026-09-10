"""CLI tests for the M3-CA1 v1 registration-readiness commands.

End-to-end round trip on a synthetic readiness area built over a REAL
qualification run: readiness-run (HOLD verdict with the open register) ->
readiness-verify (INTACT) -> registration-manifest (REFUSED loudly under
the open register). Also covers the missing-input path and the resolved-
register path (manifest BUILT).
"""

import json

import pytest

from readiness_fixtures import (
    AT,
    OP,
    QUAL_RUN_ID,
    make_population,
    make_qualified_pool,
    make_register,
    make_set_class,
)

from ecp.canonical import canonical_bytes


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
def readiness_area(tmp_path):
    """A synthetic readiness area over a real qualification run."""
    candidates, qrun, artifacts = make_qualified_pool(count=3)

    qualify_root = tmp_path / "qualify"
    (qualify_root / "candidates").mkdir(parents=True)
    (qualify_root / "qualification").mkdir(parents=True)
    for candidate in candidates:
        path = qualify_root / "candidates" / f"{candidate['candidate_id']}.json"
        path.write_bytes(canonical_bytes(candidate))
    for artifact in artifacts:
        path = qualify_root / "qualification" / f"{artifact['qualification_id']}.json"
        path.write_bytes(canonical_bytes(artifact))
    (qualify_root / "qualification-run.json").write_bytes(canonical_bytes(qrun))

    readiness_root = tmp_path / "readiness"
    (readiness_root / "decisions").mkdir(parents=True)
    (readiness_root / "population").mkdir(parents=True)
    register = make_register("open-blocking")
    (readiness_root / "decisions" / "ECP-OWNDEC-000002.json").write_bytes(
        canonical_bytes(register)
    )
    (readiness_root / "population" / "population-decision.json").write_bytes(
        canonical_bytes(make_population("30-ONLY"))
    )
    (readiness_root / "population" / "set-class-designation.json").write_bytes(
        canonical_bytes(make_set_class(candidates))
    )
    return tmp_path, readiness_root, qualify_root, register


def test_cli_readiness_run_then_verify(repo_root, readiness_area):
    tmp_path, readiness_root, qualify_root, _register = readiness_area

    result = _run(
        repo_root,
        "readiness-run",
        "--readiness-root", str(readiness_root),
        "--qualify-root", str(qualify_root),
        "--run-id", "ECP-RDNYRUN-CLI-TEST",
        "--operator", OP,
        "--at", AT,
    )
    assert result.returncode == 0, result.stderr
    assert "READINESS RUN COMPLETE: ECP-RDNYRUN-CLI-TEST" in result.stdout
    assert "REGISTER=0 HOLD=3 REVISE=0 REJECT=0" in result.stdout
    assert "registration authorization: REFUSED" in result.stdout
    assert "verdict: OWNER-DECISION-REQUIRED" in result.stdout
    assert (readiness_root / "readiness-run.json").is_file()
    records = sorted((readiness_root / "readiness").glob("ECP-RDNY-*.json"))
    assert len(records) == 3

    verify = _run(
        repo_root,
        "readiness-verify",
        "--readiness-root", str(readiness_root),
        "--qualify-root", str(qualify_root),
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "READINESS RUN INTACT: ECP-RDNYRUN-CLI-TEST" in verify.stdout
    assert "3 record(s)" in verify.stdout


def test_cli_readiness_run_detects_tampering(repo_root, readiness_area):
    tmp_path, readiness_root, qualify_root, _register = readiness_area
    _run(
        repo_root,
        "readiness-run",
        "--readiness-root", str(readiness_root),
        "--qualify-root", str(qualify_root),
        "--run-id", "ECP-RDNYRUN-CLI-TEST",
        "--operator", OP,
        "--at", AT,
    )
    record_path = sorted((readiness_root / "readiness").glob("ECP-RDNY-*.json"))[0]
    record = json.loads(record_path.read_text())
    record["checks_passed"] = 1  # tamper
    record_path.write_text(json.dumps(record), encoding="utf-8")

    verify = _run(
        repo_root,
        "readiness-verify",
        "--readiness-root", str(readiness_root),
        "--qualify-root", str(qualify_root),
    )
    assert verify.returncode == 1
    assert "READINESS VERIFICATION ISSUES" in verify.stdout


def test_cli_registration_manifest_refuses_under_open_register(repo_root, readiness_area):
    tmp_path, readiness_root, qualify_root, _register = readiness_area
    _run(
        repo_root,
        "readiness-run",
        "--readiness-root", str(readiness_root),
        "--qualify-root", str(qualify_root),
        "--run-id", "ECP-RDNYRUN-CLI-TEST",
        "--operator", OP,
        "--at", AT,
    )
    result = _run(
        repo_root,
        "registration-manifest",
        "--readiness-root", str(readiness_root),
        "--registrar", "ECP-REGISTRAR-TEST",
        "--at", AT,
    )
    assert result.returncode == 1
    assert "REGISTRATION MANIFEST REFUSED" in result.stderr
    assert "O-01" in result.stderr
    assert not (readiness_root / "registration-manifest.json").exists()


def test_cli_registration_manifest_built_under_resolved_register(repo_root, readiness_area):
    tmp_path, readiness_root, qualify_root, _register = readiness_area
    # swap in the resolved register (nothing blocks)
    resolved = make_register("resolved")
    (readiness_root / "decisions" / "ECP-OWNDEC-000002.json").write_bytes(
        canonical_bytes(resolved)
    )
    run_result = _run(
        repo_root,
        "readiness-run",
        "--readiness-root", str(readiness_root),
        "--qualify-root", str(qualify_root),
        "--run-id", "ECP-RDNYRUN-CLI-TEST",
        "--operator", OP,
        "--at", AT,
    )
    assert run_result.returncode == 0, run_result.stderr
    assert "REGISTER=3" in run_result.stdout
    assert "verdict: REGISTRATION-AUTHORIZED" in run_result.stdout

    result = _run(
        repo_root,
        "registration-manifest",
        "--readiness-root", str(readiness_root),
        "--registrar", "ECP-REGISTRAR-TEST",
        "--at", AT,
        "--registration-id", "ECP-REGSET-CLI-TEST-0001",
    )
    assert result.returncode == 0, result.stderr
    assert "REGISTRATION MANIFEST BUILT: ECP-REGSET-CLI-TEST-0001" in result.stdout
    manifest_path = readiness_root / "registration-manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text())
    assert len(manifest["cases"]) == 3
    assert manifest["registrar"] == "ECP-REGISTRAR-TEST"


def test_cli_readiness_run_missing_inputs(repo_root, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = _run(
        repo_root,
        "readiness-run",
        "--readiness-root", str(empty),
        "--qualify-root", str(tmp_path / "nonexistent"),
        "--run-id", "ECP-RDNYRUN-CLI-TEST",
        "--operator", OP,
        "--at", AT,
    )
    assert result.returncode == 2
    assert "missing readiness input" in result.stderr
