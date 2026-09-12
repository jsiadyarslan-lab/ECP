"""M3-ELR campaign engine + browser campaign console tests (hermetic).

Hermetic: synthetic cases (relational-closure semantics the frozen logical
classifier understands), synthetic registration-package view, an OFFLINE
deterministic adapter (zero network), and a real SessionCredentialGateway.
Proves the shared engine produces the registered evidence/audit/ledger
artifacts and the browser console component drives it through the existing
LocalGateway session-route seam with the frozen single-attempt discipline.
"""
import json
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecp.console import ConsoleError, GatewayConfig, LocalGateway
from ecp.console_session import SessionConsoleError, SessionCredentialGateway
from ecp.credentials import SecretStore
from ecp.execution_contract import RegisteredCaseArtifact
from ecp.hashing import hash_document
from ecp.m3_elr_campaign import (
    OPENROUTER_ENDPOINT,
    build_campaign_binding,
    build_runtime_registry,
    build_scientific_evaluation,
    execute_campaign,
    load_verified_package,
)
from ecp.m3_elr_campaign_console import M3ELRCampaignConsole
from ecp.m3_registration import EVALUATION_ID, PACKAGE_ID
from ecp.runtime_adapters import RuntimeAdapterTransportError

TERNARY_Q = "Is the a taller than the c? Answer with: yes, no, or cannot be determined."
SECRET = "test-session-secret-12345678"


class _EmptyBackingStore(SecretStore):
    def _read(self, credential_id, version):
        return None

    def _write(self, credential_id, version, secret):
        raise PermissionError("no backing credentials in tests")

    def _delete(self, credential_id, version):
        return None


class OfflineReplyAdapter:
    """Deterministic offline adapter: same contract, zero network."""

    provider = "ECP-PROVIDER-OPENROUTER"
    adapter_id = "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS"

    def __init__(self, reply="yes — premise 1 and premise 2 establish it by transitivity", fail=False):
        self.reply = reply
        self.fail = fail
        self.calls = 0

    def execute(self, lease, request):
        assert lease.value == SECRET
        self.calls += 1
        if self.fail:
            exc = RuntimeAdapterTransportError(f"provider transport failed (HTTP 401)")
            exc.http_status = 401
            raise exc
        return {
            "provider_status": "RECEIVED",
            "response_id": f"offline-{request['request_id']}",
            "model": "offline-test-model",
            "output_text": self.reply,
            "request_id": request["request_id"],
            "transport_kind": "offline-mock",
            "network": "none",
        }


def make_content(gt_class="DERIVABLE", value="Yes — the a is taller than the c."):
    return {
        "premises": ["The a is taller than the b.", "The b is taller than the c."],
        "question": TERNARY_Q,
        "proposed_reasoning_family": "alpha-family",
        "difficulty": "MEDIUM",
        "ground_truth": {"class": gt_class, "statement": "the a is taller than the c"},
        "intended_correct_answers": [{"source_block": 1, "value": value}],
        "derivations": [{"raw": "premises 1 and 2 by transitivity"}],
    }


def make_campaign_inputs(count=3):
    """Synthetic package view + artifacts + contents (engine-compatible)."""
    cases, artifacts, contents, ordered = [], {}, {}, []
    for n in range(1, count + 1):
        test_id = f"ECP-TEST-M3-ELR-{n:03d}"
        case_id = f"ECP-CASE-M3-ELR-{n:03d}"
        content = make_content()
        prompt = "PREMISES:\n1. The a is taller than the b.\n2. The b is taller than the c.\n\nQUESTION: " + TERNARY_Q + "\n"
        cases.append({
            "test_id": test_id,
            "case_id": case_id,
            "gt_commitment": "sha256:" + hash_document(content),
            "content_hash": hash_document(content),
        })
        artifacts[test_id] = RegisteredCaseArtifact.for_prompt(case_id, prompt)
        contents[test_id] = content
        ordered.append(test_id)
    package = {
        "package_id": "ECP-PKG-M3-ELR-TEST",
        "package_hash": "0" * 64,
        "ordered_test_ids": ordered,
        "cases": cases,
        "condition": {
            "condition_id": "ECP-COND-M3-ELR-1",
            "model_state": "MODEL-ENABLED",
            "level": "L1 model-only",
            "temperature": 0.0,
            "max_tokens": 1024,
            "transport_timeout_seconds": 30,
        },
        "evaluation": {"evaluation_id": EVALUATION_ID, "case_count": count},
        "target": {
            "provider": "ECP-PROVIDER-OPENROUTER",
            "adapter_id": "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS",
            "exact_model_api_identifier": "offline-test-model",
        },
        "execution_contract": {"attempts_per_test": 1},
        "registered_at": "2026-09-13T00:00:00Z",
    }
    return package, artifacts, contents


def make_gate():
    return {
        "summary": {"pass": 17, "pending": 1, "fail": 0},
        "checks": [
            {"id": "R13", "status": "PENDING", "description": "owner-side launch input", "evidence": "PENDING until supplied at execution launch"},
        ],
    }


class StubSessionManager:
    """Delegates the session lifecycle to the real session credential gateway."""

    def __init__(self, session_credentials):
        self._credentials = session_credentials

    def descriptors(self):
        return []

    def open_session(self, payload):
        return self._credentials.open_session(payload.get("credential_secret"), ttl_seconds=3600)

    def discover(self, payload):
        raise SessionConsoleError("discovery is not wired in the test stub")

    def select_target(self, payload):
        raise SessionConsoleError("target selection is not wired in the test stub")

    def revoke_session(self, payload):
        return self._credentials.revoke_session(payload.get("credential_ref"))


def open_test_session():
    gateway = SessionCredentialGateway(_EmptyBackingStore(), {})
    handle = gateway.open_session(SECRET, ttl_seconds=3600)
    return gateway, handle["credential_ref"]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def test_engine_executes_frozen_order_and_persists_artifacts(tmp_path):
    package, artifacts, contents = make_campaign_inputs(3)
    gateway, credential_ref = open_test_session()
    adapter = OfflineReplyAdapter()
    campaign = execute_campaign(
        package=package, artifacts=artifacts, contents=contents, adapter=adapter,
        gateway=gateway, credential_ref=credential_ref, evidence_root=tmp_path,
    )
    assert [e["test_id"] for e in campaign["ledger"]] == package["ordered_test_ids"]
    assert [e["position"] for e in campaign["ledger"]] == [1, 2, 3]
    assert adapter.calls == 3
    assert campaign["summary"]["attempted"] == 3
    assert campaign["summary"]["execution_valid"] == 3
    assert campaign["summary"]["execution_invalid"] == 0
    ledger_path = tmp_path / "m3-elr-campaign-ledger.json"
    assert ledger_path.is_file()
    assert json.loads(ledger_path.read_text())["summary"]["attempted"] == 3
    executions = list((tmp_path / "executions").glob("*-evidence.json"))
    assert len(executions) == 3
    assert len(list((tmp_path / "executions").glob("*-audit.json"))) == 3
    ordered_evidence = [(json.loads(path.read_text()), path) for path in executions]
    ordered_evidence.sort(key=lambda pair: pair[0]["ordering_position"])
    for position, (evidence, path) in enumerate(ordered_evidence, start=1):
        assert evidence["ecp_object"] == "m3-elr-execution-evidence"
        assert evidence["ordering_position"] == position
        assert evidence["execution_status"] == "VALID"
        assert evidence["response_status"] == "RECEIVED"
        assert evidence["answer_state"] == "CORRECT"
        assert evidence["task_outcome"] == "SUCCESS"
        assert evidence["classifier_id"]
        assert evidence["registration_reference"]["package_id"] == PACKAGE_ID
        assert evidence["transport"]["transport_kind"] == "offline-mock"
        # protected ground truth never persists
        assert "ground_truth" not in evidence
        assert "intended_correct_answers" not in evidence
        audit_path = tmp_path / "executions" / Path(path).name.replace("-evidence.json", "-audit.json")
        audit = json.loads(audit_path.read_text())
        assert audit["audit_status"] == "PENDING_HUMAN_REVIEW"
        assert audit["evidence_hash"] == evidence["evidence_hash"]


def test_engine_records_transport_failures_and_continues(tmp_path):
    package, artifacts, contents = make_campaign_inputs(3)
    gateway, credential_ref = open_test_session()
    adapter = OfflineReplyAdapter(fail=True)
    campaign = execute_campaign(
        package=package, artifacts=artifacts, contents=contents, adapter=adapter,
        gateway=gateway, credential_ref=credential_ref, evidence_root=tmp_path,
    )
    assert adapter.calls == 3  # one attempt per test, no retries, campaign continues
    assert campaign["summary"]["execution_valid"] == 0
    assert campaign["summary"]["execution_invalid"] == 3
    for entry in campaign["ledger"]:
        assert entry["execution_status"] == "INVALID"
        assert entry["response_status"] == "NOT_RECEIVED"
        assert entry["answer_state"] == "UNOBSERVABLE"
        assert entry["task_outcome"] == "FAIL"
    evidence_files = list((tmp_path / "executions").glob("*-evidence.json"))
    for path in evidence_files:
        evidence = json.loads(path.read_text())
        assert evidence["transport"] == {"transport_kind": "http", "endpoint": OPENROUTER_ENDPOINT, "http_status": 401}
        assert "401" in evidence["provider_status"]


def test_engine_events_and_log_stream(tmp_path):
    package, artifacts, contents = make_campaign_inputs(2)
    gateway, credential_ref = open_test_session()
    events, logs = [], []
    execute_campaign(
        package=package, artifacts=artifacts, contents=contents, adapter=OfflineReplyAdapter(),
        gateway=gateway, credential_ref=credential_ref, evidence_root=tmp_path,
        on_event=events.append, log=logs.append,
    )
    kinds = [e["event"] for e in events]
    assert kinds == ["test_start", "test_complete", "test_start", "test_complete", "campaign_complete"]
    assert events[-1]["summary"]["attempted"] == 2
    assert events[-1]["ledger_path"].endswith("m3-elr-campaign-ledger.json")
    assert len(logs) == 2 and "[01/2]" in logs[0] and "[02/2]" in logs[1]


def test_engine_credential_never_reaches_artifacts(tmp_path):
    package, artifacts, contents = make_campaign_inputs(2)
    gateway, credential_ref = open_test_session()
    execute_campaign(
        package=package, artifacts=artifacts, contents=contents, adapter=OfflineReplyAdapter(),
        gateway=gateway, credential_ref=credential_ref, evidence_root=tmp_path,
    )
    for path in tmp_path.rglob("*.json"):
        assert SECRET not in path.read_text()


def test_binding_helpers():
    binding, grant = build_campaign_binding("ECP-SESSION-CREDENTIAL-ABC123", "2099-01-01T00:00:00Z")
    assert binding.credential_ref == "ECP-SESSION-CREDENTIAL-ABC123"
    assert grant.expires_at == "2099-01-01T00:00:00Z"
    assert grant.binding_id == binding.binding_id
    evaluation = build_scientific_evaluation("ECP-SESSION-CREDENTIAL-ABC123", binding, grant, ["t-1"])
    assert evaluation.evaluation_id == EVALUATION_ID
    assert evaluation.credential.credential_id == "ECP-SESSION-CREDENTIAL-ABC123"
    registry = build_runtime_registry(OfflineReplyAdapter())
    assert registry.get("ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS") is not None


def test_load_verified_package_rejects_tampering(tmp_path):
    package, _, _ = make_campaign_inputs(1)
    package["package_id"] = "ECP-PKG-M3-ELR-V1"
    package["package_hash"] = hash_document({k: v for k, v in package.items() if k != "package_hash"})
    path = tmp_path / "package.json"
    path.write_text(json.dumps(package), encoding="utf-8")
    loaded = load_verified_package(path)
    assert loaded["package_id"] == "ECP-PKG-M3-ELR-V1"
    package["condition"] = {"temperature": 9.9}
    path.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(SystemExit):
        load_verified_package(path)


# ---------------------------------------------------------------------------
# Browser campaign console component
# ---------------------------------------------------------------------------

def build_component(tmp_path, adapter=None, gate=None):
    package, artifacts, contents = make_campaign_inputs(3)
    session_credentials = SessionCredentialGateway(_EmptyBackingStore(), {})
    manager = StubSessionManager(session_credentials)
    console = M3ELRCampaignConsole(
        session_manager=manager,
        session_credentials=session_credentials,
        package=package,
        artifacts=artifacts,
        contents=contents,
        adapter=adapter or OfflineReplyAdapter(),
        evidence_root=tmp_path / "evidence",
        gate=gate or make_gate(),
    )
    return console, session_credentials


def wait_for_campaign(console, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = console.m3elr_campaign_status({})
        campaign = status["campaign"]
        if campaign is not None and campaign["status"] in {"COMPLETED", "FAILED"}:
            return campaign
        time.sleep(0.02)
    raise AssertionError("campaign did not finish in time")


def test_component_status_view():
    console, _ = build_component(Path("/tmp/x-does-not-matter"))
    status = console.m3elr_campaign_status({})
    assert status["m3elr_console"] is True
    assert status["campaign"] is None
    registration = status["registration"]
    assert registration["package_id"] == "ECP-PKG-M3-ELR-TEST"
    assert registration["case_count"] == 3
    assert registration["ordered_test_ids"][0] == "ECP-TEST-M3-ELR-001"
    assert registration["condition"]["temperature"] == 0.0
    assert registration["target_model_identifier"] == "offline-test-model"
    assert registration["attempts_per_test"] == 1
    assert status["gate"]["pass"] == 17 and status["gate"]["fail"] == 0
    assert status["gate"]["pending_checks"][0]["id"] == "R13"


def test_component_requires_credential_ref_and_known_session(tmp_path):
    console, _ = build_component(tmp_path)
    with pytest.raises(SessionConsoleError):
        console.m3elr_campaign({})
    with pytest.raises(SessionConsoleError):
        console.m3elr_campaign({"credential_ref": "ECP-SESSION-CREDENTIAL-NOTOPEN"})


def test_component_refuses_campaign_when_gate_fails(tmp_path):
    failing_gate = {"summary": {"pass": 10, "pending": 1, "fail": 1}, "checks": []}
    console, credentials = build_component(tmp_path, gate=failing_gate)
    handle = credentials.open_session(SECRET, ttl_seconds=3600)
    with pytest.raises(SessionConsoleError):
        console.m3elr_campaign({"credential_ref": handle["credential_ref"]})


def test_component_runs_campaign_once_and_persists(tmp_path):
    console, credentials = build_component(tmp_path)
    handle = credentials.open_session(SECRET, ttl_seconds=3600)
    started = console.m3elr_campaign({"credential_ref": handle["credential_ref"]})
    assert started["campaign"]["status"] == "RUNNING"
    assert started["campaign"]["total"] == 3
    campaign = wait_for_campaign(console)
    assert campaign["status"] == "COMPLETED"
    assert campaign["position"] == 3
    assert [e["test_id"] for e in campaign["entries"]] == [
        "ECP-TEST-M3-ELR-001", "ECP-TEST-M3-ELR-002", "ECP-TEST-M3-ELR-003",
    ]
    assert campaign["summary"]["attempted"] == 3
    assert campaign["ledger_path"].endswith("m3-elr-campaign-ledger.json")
    assert (tmp_path / "evidence" / "m3-elr-campaign-ledger.json").is_file()
    assert len(list((tmp_path / "evidence" / "executions").glob("*-evidence.json"))) == 3
    # frozen single-attempt discipline: exactly one campaign per process
    handle2 = credentials.open_session(SECRET, ttl_seconds=3600)
    with pytest.raises(SessionConsoleError):
        console.m3elr_campaign({"credential_ref": handle2["credential_ref"]})


def test_component_failed_campaign_records_honest_error(tmp_path):
    console, credentials = build_component(tmp_path, adapter=OfflineReplyAdapter(fail=True))
    handle = credentials.open_session(SECRET, ttl_seconds=3600)
    console.m3elr_campaign({"credential_ref": handle["credential_ref"]})
    campaign = wait_for_campaign(console)
    assert campaign["status"] == "COMPLETED"
    assert campaign["summary"]["execution_invalid"] == 3  # transport failures are honest INVALID executions


def test_component_delegates_standard_session_routes(tmp_path):
    console, credentials = build_component(tmp_path)
    handle = console.open_session({"credential_secret": SECRET})
    assert handle["status"] == "OPEN"
    assert console.descriptors() == []
    with pytest.raises(SessionConsoleError):
        console.discover({"credential_ref": handle["credential_ref"]})
    revoked = console.revoke_session({"credential_ref": handle["credential_ref"]})
    assert revoked["status"] == "REVOKED"


# ---------------------------------------------------------------------------
# Gateway session-route integration (the existing seam serves the campaign)
# ---------------------------------------------------------------------------

def _request(gateway, method, path, payload=None, token=None, origin="http://127.0.0.1:8766"):
    import http.client

    connection = http.client.HTTPConnection("127.0.0.1", gateway._httpd.server_port)
    headers = {"Origin": origin}
    if token:
        headers["X-ECP-Session"] = token
    if payload is not None:
        headers["Content-Type"] = "application/json"
    connection.request(method, path, json.dumps(payload).encode() if payload is not None else None, headers)
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, json.loads(body or b"{}") or {}


def test_gateway_session_routes_serve_m3elr_campaign(tmp_path):
    console, credentials = build_component(tmp_path)
    config = GatewayConfig(frozenset({"http://127.0.0.1:8766"}), artifact_root=tmp_path / "artifacts")
    gateway = LocalGateway(config, {}, credentials, {}, session_console=console)
    server = gateway.make_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # unauthenticated access is rejected
        status, payload = _request(gateway, "POST", "/api/v1/m3elr/campaign/status", {})
        assert status == 401
        status, payload = _request(gateway, "POST", "/api/v1/pair", {"pairing_code": gateway.pairing_code})
        assert status == 200
        token = payload["session"]
        # status route serves the registration view
        status, payload = _request(gateway, "POST", "/api/v1/m3elr/campaign/status", {}, token=token)
        assert status == 200
        assert payload["m3elr_console"] is True
        assert payload["registration"]["case_count"] == 3
        # campaign start requires an open credential session
        status, payload = _request(gateway, "POST", "/api/v1/m3elr/campaign", {"credential_ref": "x"}, token=token)
        assert status == 400
        # open a credential session through the delegated route
        status, handle = _request(gateway, "POST", "/api/v1/credentials/session", {"credential_secret": SECRET}, token=token)
        assert status == 200
        credential_ref = handle["credential_ref"]
        # start the campaign through the gateway seam
        status, payload = _request(gateway, "POST", "/api/v1/m3elr/campaign", {"credential_ref": credential_ref}, token=token)
        assert status == 200
        assert payload["campaign"]["status"] == "RUNNING"
        campaign = wait_for_campaign(console)
        assert campaign["status"] == "COMPLETED"
        # second start is refused (one campaign per process)
        status, payload = _request(gateway, "POST", "/api/v1/m3elr/campaign", {"credential_ref": credential_ref}, token=token)
        assert status == 400
        assert "already been started" in payload["error"]
        # the secret never appears in any route response
        status, payload = _request(gateway, "POST", "/api/v1/m3elr/campaign/status", {}, token=token)
        assert SECRET not in json.dumps(payload)
    finally:
        server.shutdown()
        server.server_close()


def test_gateway_session_route_dispatch_is_the_existing_seam(tmp_path):
    console, credentials = build_component(tmp_path)
    gateway = LocalGateway(
        GatewayConfig(frozenset({"http://127.0.0.1:8766"}), artifact_root=tmp_path), {}, credentials, {}, session_console=console
    )
    status = gateway.execute_session_route("/api/v1/m3elr/campaign/status", {})
    assert status["m3elr_console"] is True
    with pytest.raises(ConsoleError):
        gateway.execute_session_route("/api/v1/m3elr/campaign/unknown", {})
