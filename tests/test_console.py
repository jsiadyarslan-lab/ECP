import http.client
import json
import socket
import threading
from pathlib import Path

import pytest

from ecp.console import (
    AdapterFailure,
    AuthorizedEvaluation,
    AuthorizedTest,
    ExecutionStore,
    GatewayConfig,
    LocalGateway,
    ProviderAdapter,
)
from ecp.credentials import CredentialGateway, CredentialIdentity
from ecp.credential_binding import AuthorizationGrant, CredentialBinding

ORIGIN = "http://127.0.0.1:8766"


class SafeAdapter(ProviderAdapter):
    provider = "synthetic-provider"
    adapter_id = "synthetic-adapter"

    def __init__(self, secret: str):
        self.secret = secret
        self.calls = 0

    def execute(self, lease, request):
        self.calls += 1
        assert lease.value == self.secret
        assert "secret" not in request
        return {"safe_result": "ok", "leak_attempt": self.secret}


def build_gateway(tmp_path: Path, adapter=None, store=None):
    identity = CredentialIdentity("cred-1", "synthetic-provider", "test", frozenset({"execute"}))
    credentials, secret_store = CredentialGateway.for_testing({"cred-1": identity})
    secret = "synthetic-console-secret-DO-NOT-LEAK"
    credentials.provision_for_testing("cred-1", secret)
    evaluation = AuthorizedEvaluation(
        "ECP-EVAL-CONSOLE-TEST",
        "ECP-SYSTEM-CONSOLE-TEST",
        "synthetic-provider",
        "synthetic-adapter",
        identity,
        (AuthorizedTest("test-1", "Synthetic registered test", "execute"),),
        CredentialBinding(
            "ECP-BINDING-CONSOLE-TEST", "ECP-REQUIREMENT-CONSOLE-TEST",
            "ECP-SYSTEM-CONSOLE-TEST", "synthetic-provider",
            "test-interface", "execute", "cred-1", frozenset({"execute"}),
        ),
        AuthorizationGrant(
            "ECP-AUTH-CONSOLE-TEST", "ECP-BINDING-CONSOLE-TEST",
            "ECP-SYSTEM-CONSOLE-TEST", "execute", frozenset({"execute"}),
            "2099-01-01T00:00:00Z",
        ),
    )
    adapter = adapter or SafeAdapter(secret)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    gateway = LocalGateway(
        GatewayConfig(frozenset({ORIGIN}), port=port, artifact_root=tmp_path),
        {evaluation.evaluation_id: evaluation},
        credentials,
        {"synthetic-adapter": adapter},
        store,
    )
    return gateway, adapter, secret_store, secret


def request(gateway, method, path, payload=None, token=None, origin=ORIGIN):
    server = gateway._httpd
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
    headers = {"Origin": origin}
    if token:
        headers["X-ECP-Session"] = token
    if payload is not None:
        headers["Content-Type"] = "application/json"
    connection.request(method, path, json.dumps(payload).encode() if payload is not None else None, headers)
    response = connection.getresponse()
    body = response.read()
    connection.close()
    return response.status, json.loads(body or b"{}"), dict(response.headers)


@pytest.fixture
def running_gateway(tmp_path):
    gateway, adapter, secret_store, secret = build_gateway(tmp_path)
    server = gateway.make_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield gateway, adapter, secret_store, secret
    finally:
        server.shutdown()
        server.server_close()


def test_pairing_requires_allowed_origin_and_is_temporary(running_gateway):
    gateway, _, _, _ = running_gateway
    status, payload, headers = request(gateway, "POST", "/api/v1/pair", {"pairing_code": gateway.pairing_code}, origin="https://evil.example")
    assert status == 403
    assert "Access-Control-Allow-Origin" not in headers
    assert "session" not in payload

    status, payload, headers = request(gateway, "POST", "/api/v1/pair", {"pairing_code": gateway.pairing_code})
    assert status == 200
    token = payload["session"]
    assert token not in gateway.pairing_code
    assert headers["Access-Control-Allow-Origin"] == ORIGIN

    status, payload, _ = request(gateway, "GET", "/api/v1/catalog")
    assert status == 401
    status, payload, _ = request(gateway, "GET", "/api/v1/catalog", token=token)
    assert status == 200
    assert payload["evaluations"][0]["credential"]["credential_id"] == "cred-1"


def test_execution_uses_gateway_redacts_secret_and_is_idempotent(tmp_path):
    gateway, adapter, _, secret = build_gateway(tmp_path)
    token = gateway.pair(gateway.pairing_code)
    request_doc = {
        "evaluation_id": "ECP-EVAL-CONSOLE-TEST",
        "system_id": "ECP-SYSTEM-CONSOLE-TEST",
        "credential_ref": "cred-1",
        "test_id": "test-1",
        "request_id": "one-request",
    }
    first = gateway.execute(request_doc)
    second = gateway.execute(request_doc)
    assert first["execution_id"] == second["execution_id"]
    assert first["status"] == "SUCCESS"
    assert first["evidence_status"] == "GENERATED"
    assert first["audit_status"] == "GENERATED"
    assert first["persistence_status"] == "PERSISTED_LOCALLY"
    assert adapter.calls == 1
    serialized = json.dumps(first)
    assert secret not in serialized
    assert "[REDACTED]" in serialized
    files = list(tmp_path.rglob("*.json"))
    assert files
    assert all(secret not in path.read_text() for path in files)
    assert token  # session exists only in memory and is not in the record


def test_request_validation_rejects_arbitrary_fields(running_gateway):
    gateway, _, _, _ = running_gateway
    token = gateway.pair(gateway.pairing_code)
    status, payload, _ = request(gateway, "POST", "/api/v1/executions", {"shell_command": "whoami"}, token=token)
    assert status == 400
    assert payload["state"] == "INVALID"


def test_fail_closed_without_registered_adapter(tmp_path):
    gateway, _, _, _ = build_gateway(tmp_path, adapter=None)
    gateway.adapters.clear()
    result = gateway.execute({
        "evaluation_id": "ECP-EVAL-CONSOLE-TEST",
        "system_id": "ECP-SYSTEM-CONSOLE-TEST",
        "credential_ref": "cred-1",
        "test_id": "test-1",
        "request_id": "no-adapter",
    })
    assert result["status"] == "FAILED"
    assert result["execution_status"] == "INCONCLUSIVE"
    assert result["error_classification"] == "ADAPTER_UNAVAILABLE"


def test_adapter_failure_is_redacted(tmp_path):
    class FailingAdapter(ProviderAdapter):
        def execute(self, lease, request):
            raise AdapterFailure("AUTHENTICATION_FAILED", f"provider rejected {lease.value}")

    gateway, _, _, secret = build_gateway(tmp_path, adapter=FailingAdapter())
    result = gateway.execute({
        "evaluation_id": "ECP-EVAL-CONSOLE-TEST",
        "system_id": "ECP-SYSTEM-CONSOLE-TEST",
        "credential_ref": "cred-1",
        "test_id": "test-1",
        "request_id": "redaction-failure",
    })
    assert result["execution_status"] == "AUTHENTICATION_FAILED"
    assert secret not in json.dumps(result)
    assert "[REDACTED]" in result["error"]


def test_partial_success_is_not_success(tmp_path):
    class FailingStore(ExecutionStore):
        def persist(self, execution_id, evidence, audit):
            raise OSError("persistence unavailable")

    gateway, _, _, _ = build_gateway(tmp_path, store=FailingStore(tmp_path))
    result = gateway.execute({
        "evaluation_id": "ECP-EVAL-CONSOLE-TEST",
        "system_id": "ECP-SYSTEM-CONSOLE-TEST",
        "credential_ref": "cred-1",
        "test_id": "test-1",
        "request_id": "partial-persist",
    })
    assert result["status"] == "PARTIAL_SUCCESS"
    assert result["failure_stage"] == "evidence_audit_or_persistence"


def test_static_ui_has_no_provider_or_secret_write_path():
    root = Path(__file__).resolve().parents[1] / "console"
    html = (root / "index.html").read_text()
    app = (root / "app.js").read_text()
    assert "127.0.0.1:8765" in app
    assert "github" not in app.lower()
    assert "api_key" not in app.lower()
    assert "secret_value" not in app.lower()
    assert "GitHub write tokens" not in html
    assert "Ground Truth" in html
