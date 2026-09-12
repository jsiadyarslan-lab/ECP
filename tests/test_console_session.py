"""Synthetic tests for the universal console credential sessions.

Covers the owner order §8 battery for the visual console: session credential
lifecycle, discovery wiring, model selection/onboarding through the existing
universal fabric, execution evidence/audit creation, secret non-leakage
(in artifacts AND HTTP responses), network boundary, and localhost security.
Everything runs offline: the discovery transport and the runtime adapter are
injected fakes; no real credential, no network.
"""

from __future__ import annotations

import http.client
import json
import socket
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ecp.adapters import AdapterRegistry
from ecp.console import ConsoleError, GatewayConfig, LocalGateway
from ecp.console_session import (
    DEFAULT_SESSION_TTL_SECONDS,
    ConsoleSessionManager,
    SessionConsoleError,
    SessionCredentialGateway,
)
from ecp.credentials import CredentialIdentity, SecretStore
from ecp.discovery import ProviderDiscoveryService, builtin_discovery_registry
from ecp.onboarding import TargetOnboardingService
from ecp.runtime_adapters import RuntimeAdapterRegistry
from ecp.targets import ProviderRegistry, TargetRegistry

ORIGIN = "http://127.0.0.1:8766"
SECRET = "sk-session-OWNER-SECRET-DO-NOT-LEAK-0001"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
OPENAI_MODELS_BODY = {
    "data": [
        {"id": "gpt-4o", "object": "model", "owned_by": "system"},
        {"id": "gpt-4o-mini", "object": "model", "owned_by": "system"},
    ]
}


class DictSecretStore(SecretStore):
    """Minimal backing store for configuration credentials."""

    def __init__(self):
        self.values = {}

    def _read(self, credential_id, version):
        return self.values.get((credential_id, version))

    def _write(self, credential_id, version, secret):
        self.values[(credential_id, version)] = secret

    def _delete(self, credential_id, version):
        self.values.pop((credential_id, version), None)


class FakeProbeTransport:
    def __init__(self, routes=None):
        self.routes = dict(routes or {})
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, dict(headers)))
        route = self.routes.get(url)
        if route is None:
            return 404, b"{}"
        if isinstance(route, Exception):
            raise route
        return route


class MockSessionAdapter:
    """Offline runtime adapter behind the universal adapter contract."""

    def __init__(self, *, model, endpoint, provider, adapter_id):
        self.model = model
        self.endpoint = endpoint
        self.provider = provider
        self.adapter_id = adapter_id
        self.calls = 0

    def execute(self, lease, request):
        self.calls += 1
        return {
            "provider_status": "RECEIVED",
            "response_id": "session-" + request["request_id"],
            "model": self.model,
            "output_text": "ECP-CONFORMANCE-OK",
            "request_id": request["request_id"],
        }


def mock_adapter_factory(kind, *, model, endpoint, provider, adapter_id, token_header=None, bearer_value=None, extra_headers=None):
    assert kind in {"openai-responses", "gemini-generate-content", "anthropic-messages", "openrouter-chat-completions"}
    return MockSessionAdapter(model=model, endpoint=endpoint, provider=provider, adapter_id=adapter_id)


def build_stack(tmp_path, routes=None, clock=None):
    """Full session stack over the existing universal fabric (all offline)."""
    transport = FakeProbeTransport(routes or {OPENAI_MODELS_URL: (200, json.dumps(OPENAI_MODELS_BODY).encode())})
    backing = DictSecretStore()
    mutable_clock = {"now": datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)}
    if clock is None:
        clock = lambda: mutable_clock["now"]
    session_credentials = SessionCredentialGateway(backing, {}, clock=clock)
    providers = ProviderRegistry()
    targets = TargetRegistry(providers)
    adapters = AdapterRegistry()
    runtime = RuntimeAdapterRegistry()
    service = TargetOnboardingService(providers, targets, adapters, runtime, session_credentials, clock=clock)
    gateway = LocalGateway(
        GatewayConfig(frozenset({ORIGIN}), artifact_root=Path(tmp_path)),
        service.evaluations,
        session_credentials,
        runtime,
    )
    manager = ConsoleSessionManager(
        gateway=gateway,
        session_credentials=session_credentials,
        discovery=ProviderDiscoveryService(builtin_discovery_registry(), transport=transport, clock=clock),
        onboarding=service,
        adapter_factory=mock_adapter_factory,
        ttl_seconds=3600,
        clock=clock,
    )
    gateway.enable_session_console(manager)
    return {
        "gateway": gateway,
        "manager": manager,
        "service": service,
        "session_credentials": session_credentials,
        "transport": transport,
        "backing": backing,
        "clock": mutable_clock,
        "runtime": runtime,
    }


def request(gateway, method, path, payload=None, token=None, origin=ORIGIN):
    connection = http.client.HTTPConnection("127.0.0.1", gateway._httpd.server_port)
    headers = {"Origin": origin}
    if token:
        headers["X-ECP-Session"] = token
    if payload is not None:
        headers["Content-Type"] = "application/json"
    body = json.dumps(payload).encode() if payload is not None else None
    if isinstance(payload, bytes):
        body = payload
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body, headers)
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    return response.status, json.loads(raw or b"{}"), dict(response.headers), raw.decode("utf-8", "replace")


@pytest.fixture
def running_stack(tmp_path):
    stack = build_stack(tmp_path)
    server = stack["gateway"].make_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield stack
    finally:
        server.shutdown()
        server.server_close()


def pair(gateway):
    return gateway.pair(gateway.pairing_code)


def pair_over_http(gateway):
    status, payload, _, _ = request(gateway, "POST", "/api/v1/pair", {"pairing_code": gateway.pairing_code})
    assert status == 200
    return payload["session"]


def open_session(stack, secret=SECRET):
    return stack["manager"].open_session({"credential_secret": secret})


def discover(stack, **overrides):
    payload = {"credential_ref": open_session(stack)["credential_ref"], **overrides}
    return stack["manager"].discover(payload)


# ---------------------------------------------------------------------------
# Session credential gateway lifecycle
# ---------------------------------------------------------------------------


def test_open_session_returns_reference_only_never_the_value():
    stack = build_stack("/tmp/ecp-session-test")
    handle = open_session(stack)
    assert handle["status"] == "OPEN"
    assert handle["credential_ref"].startswith("ECP-SESSION-CREDENTIAL-")
    assert handle["credential_ref"].isupper() or handle["credential_ref"].split("-")[-1].isupper()
    blob = json.dumps(handle)
    assert SECRET not in blob
    assert "storage" in handle


@pytest.mark.parametrize(
    "bad",
    ["", "short", "has space", "has\nnewline", "has\ttp", "tab\tand newline\n", "üñïçödé-key-value", 123, None, "x" * 5000],
)
def test_open_session_rejects_unsafe_credential_values(bad):
    stack = build_stack("/tmp/ecp-session-test")
    with pytest.raises(SessionConsoleError):
        stack["manager"].open_session({"credential_secret": bad})


def test_discovery_release_flows_through_the_existing_release_path():
    stack = build_stack("/tmp/ecp-session-test")
    handle = open_session(stack)
    lease = stack["session_credentials"].discovery_lease(handle["credential_ref"], request_id="lease-test")
    assert lease.value == SECRET
    assert lease.metadata["binding_id"].startswith("ECP-BINDING-DISCOVERY-")
    assert lease.metadata["authorization_ref"].startswith("ECP-AUTH-DISCOVERY-")


def test_unknown_credential_reference_is_rejected():
    stack = build_stack("/tmp/ecp-session-test")
    with pytest.raises(SessionConsoleError):
        stack["manager"].discover({"credential_ref": "ECP-SESSION-CREDENTIAL-DEADBEEF00000000"})


def test_revoked_session_cannot_release():
    stack = build_stack("/tmp/ecp-session-test")
    handle = open_session(stack)
    stack["manager"].revoke_session({"credential_ref": handle["credential_ref"]})
    with pytest.raises(Exception):
        stack["session_credentials"].discovery_lease(handle["credential_ref"], request_id="after-revoke")
    with pytest.raises(SessionConsoleError):
        stack["manager"].discover({"credential_ref": handle["credential_ref"]})


def test_expired_session_cannot_release():
    stack = build_stack("/tmp/ecp-session-test")
    handle = open_session(stack)
    stack["clock"]["now"] = stack["clock"]["now"] + timedelta(seconds=3601)
    with pytest.raises(Exception):
        stack["session_credentials"].discovery_lease(handle["credential_ref"], request_id="after-expiry", now=stack["clock"]["now"])


def test_provider_binding_keeps_discovery_release_working():
    stack = build_stack("/tmp/ecp-session-test")
    handle = open_session(stack)
    document = stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    assert document["status"] == "DISCOVERED"
    identity = stack["session_credentials"].current_identity(handle["credential_ref"])
    assert identity.provider == "ECP-PROVIDER-OPENAI"
    assert "provider-discovery" in identity.scope and "conformance-evaluation" in identity.scope
    # re-discovery still releases through release() with the regenerated binding
    document2 = stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    assert document2["status"] == "DISCOVERED"


def test_invalid_discovered_provider_id_is_rejected():
    stack = build_stack("/tmp/ecp-session-test")
    handle = open_session(stack)
    with pytest.raises(SessionConsoleError):
        stack["session_credentials"].bind_discovered_provider(handle["credential_ref"], "not-a-provider")


def test_backing_store_credentials_remain_readable_through_composite():
    backing = DictSecretStore()
    backing.values[("config-cred", "1")] = "config-secret-value"
    gateway = SessionCredentialGateway(backing, {})
    handle = gateway.open_session("session-secret-value-123", ttl_seconds=3600)
    store = gateway._store
    assert store._read("config-cred", "1") == "config-secret-value"
    assert store._read(handle["credential_ref"], "1") == "session-secret-value-123"
    with pytest.raises(PermissionError):
        store._write("x", "1", "y")


# ---------------------------------------------------------------------------
# Full synthetic flow through the existing universal fabric
# ---------------------------------------------------------------------------


def test_full_session_flow_executes_through_the_existing_path(tmp_path):
    stack = build_stack(tmp_path)
    handle = open_session(stack)
    document = stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    assert document["status"] == "DISCOVERED"
    assert document["provider"]["provider_id"] == "ECP-PROVIDER-OPENAI"
    identifiers = {m["model_identifier"] for m in document["models"]}
    assert identifiers == {"gpt-4o", "gpt-4o-mini"}
    selection = stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-4o-mini"})
    assert selection["ready"] == "READY"
    assert selection["model_identifier"] == "gpt-4o-mini"
    record = stack["gateway"].execute({
        "evaluation_id": selection["evaluation_id"],
        "system_id": selection["system_id"],
        "credential_ref": selection["credential_ref"],
        "test_id": selection["test_id"],
        "request_id": "session-execution-1",
    })
    assert record["status"] == "SUCCESS"
    assert record["execution_status"] == "SUCCESS"
    assert record["result"]["normalized_output"] == "ECP-CONFORMANCE-OK"
    assert record["evidence_status"] == "GENERATED"
    assert record["audit_status"] == "GENERATED"
    assert record["persistence_status"] == "PERSISTED_LOCALLY"
    assert record["evidence_id"].startswith("ECP-EVID-CONSOLE-")
    assert record["audit_id"].startswith("ECP-AUDIT-CONSOLE-")
    # the execution happened exactly once through the runtime adapter
    adapter = stack["runtime"].get(selection["adapter_id"])
    assert adapter.calls == 1
    assert adapter.model == "gpt-4o-mini"
    assert adapter.endpoint == "https://api.openai.com/v1/responses"


def test_session_execution_evidence_and_audit_are_secret_free(tmp_path):
    stack = build_stack(tmp_path)
    handle = open_session(stack)
    stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    selection = stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-4o"})
    record = stack["gateway"].execute({
        "evaluation_id": selection["evaluation_id"],
        "system_id": selection["system_id"],
        "credential_ref": selection["credential_ref"],
        "test_id": selection["test_id"],
        "request_id": "session-execution-secret-scan",
    })
    assert record["status"] == "SUCCESS"
    onboarding_records = stack["service"].records
    blobs = [json.dumps(record), json.dumps(onboarding_records), json.dumps(selection)]
    for path in Path(tmp_path).rglob("*.json"):
        blobs.append(path.read_text())
    for blob in blobs:
        assert SECRET not in blob


def test_session_target_onboards_through_the_universal_onboarding_records(tmp_path):
    stack = build_stack(tmp_path)
    handle = open_session(stack)
    stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    selection = stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-4o"})
    records = stack["service"].records
    assert len(records) == 1
    record = records[0]
    assert record["target_id"] == selection["target_id"]
    assert record["model_identifier"] == "gpt-4o"
    assert record["provider_id"] == "ECP-PROVIDER-OPENAI"
    assert record["readiness_state"] == "READY"
    assert record["credential_ref"] == handle["credential_ref"]


def test_model_selection_is_idempotent_and_cached(tmp_path):
    stack = build_stack(tmp_path)
    handle = open_session(stack)
    stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    first = stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-4o"})
    second = stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-4o"})
    assert first == second
    assert len(stack["service"].records) == 1


def test_selecting_unknown_model_is_model_unavailable(tmp_path):
    stack = build_stack(tmp_path)
    handle = open_session(stack)
    stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    with pytest.raises(SessionConsoleError, match="not in the discovered model list"):
        stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-invisible"})


def test_selecting_before_discovery_is_rejected(tmp_path):
    stack = build_stack(tmp_path)
    handle = open_session(stack)
    with pytest.raises(SessionConsoleError, match="run discovery first"):
        stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-4o"})


def test_selection_after_failed_discovery_is_rejected(tmp_path):
    stack = build_stack(tmp_path, routes={OPENAI_MODELS_URL: (401, b'{"error":"bad key"}')})
    handle = open_session(stack)
    document = stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    assert document["status"] == "DISCOVERY_FAILED"
    assert document["identification"] == "UNKNOWN"
    with pytest.raises(SessionConsoleError):
        stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-4o"})


def test_two_models_onboard_two_targets_and_both_execute(tmp_path):
    stack = build_stack(tmp_path)
    handle = open_session(stack)
    stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    first = stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-4o"})
    second = stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-4o-mini"})
    assert first["target_id"] != second["target_id"]
    assert first["adapter_id"] != second["adapter_id"]
    assert len(stack["service"].records) == 2
    catalog_ids = [e["evaluation_id"] for e in stack["gateway"].catalog()["evaluations"]]
    assert first["evaluation_id"] in catalog_ids and second["evaluation_id"] in catalog_ids
    for selection in (first, second):
        record = stack["gateway"].execute({
            "evaluation_id": selection["evaluation_id"],
            "system_id": selection["system_id"],
            "credential_ref": selection["credential_ref"],
            "test_id": selection["test_id"],
            "request_id": "dual-" + selection["model_identifier"],
        })
        assert record["status"] == "SUCCESS"


def test_different_credentials_get_different_targets_for_the_same_model(tmp_path):
    stack = build_stack(tmp_path)
    handle_a = stack["manager"].open_session({"credential_secret": "sk-owner-AAAAAAAAAAAAAAAA0001"})
    handle_b = stack["manager"].open_session({"credential_secret": "sk-owner-BBBBBBBBBBBBBBBB0002"})
    stack["manager"].discover({"credential_ref": handle_a["credential_ref"]})
    stack["manager"].discover({"credential_ref": handle_b["credential_ref"]})
    selection_a = stack["manager"].select_target({"credential_ref": handle_a["credential_ref"], "model_identifier": "gpt-4o"})
    selection_b = stack["manager"].select_target({"credential_ref": handle_b["credential_ref"], "model_identifier": "gpt-4o"})
    assert selection_a["target_id"] != selection_b["target_id"]
    assert selection_a["adapter_id"] != selection_b["adapter_id"]


def test_discovery_probes_only_the_provider_models_endpoints(tmp_path):
    stack = build_stack(tmp_path)
    handle = open_session(stack)
    stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    assert stack["transport"].calls
    for url, headers in stack["transport"].calls:
        assert url.startswith("https://")
        assert url.endswith("/models")
        carried = headers.get("Authorization", "") + headers.get("x-api-key", "") + headers.get("x-goog-api-key", "")
        assert SECRET in carried
    urls = [call[0] for call in stack["transport"].calls]
    # every fixed builtin endpoint probed is a /models path; identification
    # stopped at the first match (openai) so later dialects were not probed
    assert OPENAI_MODELS_URL in urls
    assert "https://openrouter.ai/api/v1/models" not in urls
    assert all("/models" in url for url in urls)


def test_manager_descriptors_view_is_registry_driven(tmp_path):
    stack = build_stack(tmp_path)
    view = stack["manager"].descriptors()
    assert len(view) == 6
    assert stack["gateway"].session_descriptors() == view


# ---------------------------------------------------------------------------
# Gateway registration seam
# ---------------------------------------------------------------------------


def test_register_evaluation_is_idempotent_for_the_same_object(tmp_path):
    stack = build_stack(tmp_path)
    handle = open_session(stack)
    stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    selection = stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-4o"})
    evaluation = stack["gateway"].evaluations[selection["evaluation_id"]]
    stack["gateway"].register_evaluation(evaluation)  # no-op
    assert stack["gateway"].evaluations[selection["evaluation_id"]] is evaluation


def test_register_evaluation_rejects_divergent_wiring(tmp_path):
    stack = build_stack(tmp_path)
    handle = open_session(stack)
    stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    selection = stack["manager"].select_target({"credential_ref": handle["credential_ref"], "model_identifier": "gpt-4o"})
    original = stack["gateway"].evaluations[selection["evaluation_id"]]
    from copy import deepcopy
    impostor = deepcopy(original)
    with pytest.raises(ConsoleError):
        stack["gateway"].register_evaluation(impostor)
    assert stack["gateway"].evaluations[selection["evaluation_id"]] is original


def test_resolver_register_rejects_objects_without_identity():
    from ecp.execution_contract import ContractViolation, ExecutionContractResolver
    resolver = ExecutionContractResolver({}, None, None)
    with pytest.raises(ContractViolation):
        resolver.register(object())


def test_gateway_without_session_console_fails_closed(tmp_path):
    gateway = LocalGateway(GatewayConfig(frozenset({ORIGIN}), artifact_root=Path(tmp_path)), {}, None, None)
    with pytest.raises(ConsoleError, match="session console is not enabled"):
        gateway.execute_session_route("/api/v1/discovery", {})
    with pytest.raises(ConsoleError, match="session console is not enabled"):
        gateway.session_descriptors()


# ---------------------------------------------------------------------------
# HTTP boundary: origin, authentication, leakage, localhost binding
# ---------------------------------------------------------------------------


def test_server_binds_loopback_only(running_stack):
    address = running_stack["gateway"]._httpd.server_address
    assert address[0] == "127.0.0.1"


def test_session_routes_require_allowed_origin(running_stack):
    gateway = running_stack["gateway"]
    status, payload, headers, raw = request(gateway, "POST", "/api/v1/credentials/session", {"credential_secret": SECRET}, origin="https://evil.example")
    assert status == 403
    assert payload["state"] == "SECURITY_BLOCKED"
    assert "Access-Control-Allow-Origin" not in headers
    assert SECRET not in raw


def test_session_routes_require_authentication(running_stack):
    gateway = running_stack["gateway"]
    for path, body in (
        ("/api/v1/credentials/session", {"credential_secret": SECRET}),
        ("/api/v1/discovery", {"credential_ref": "ECP-SESSION-CREDENTIAL-0"}),
        ("/api/v1/session/targets", {"credential_ref": "ECP-SESSION-CREDENTIAL-0", "model_identifier": "x"}),
        ("/api/v1/credentials/session/revoke", {"credential_ref": "ECP-SESSION-CREDENTIAL-0"}),
    ):
        status, payload, _, raw = request(gateway, "POST", path, body)
        assert status == 401, path
        assert payload["state"] == "AUTHENTICATION_REQUIRED"
        assert SECRET not in raw
    status, payload, _, _ = request(gateway, "GET", "/api/v1/discovery/descriptors")
    assert status == 401


def test_http_session_flow_never_leaks_the_credential(running_stack):
    gateway = running_stack["gateway"]
    token = pair_over_http(gateway)
    status, payload, _, raw = request(gateway, "GET", "/api/v1/discovery/descriptors", token=token)
    assert status == 200
    assert len(payload["descriptors"]) == 6
    status, payload, _, raw = request(gateway, "POST", "/api/v1/credentials/session", {"credential_secret": SECRET}, token=token)
    assert status == 200
    assert payload["credential_ref"].startswith("ECP-SESSION-CREDENTIAL-")
    assert SECRET not in raw
    credential_ref = payload["credential_ref"]
    status, payload, _, raw = request(gateway, "POST", "/api/v1/discovery", {"credential_ref": credential_ref}, token=token)
    assert status == 200
    assert payload["status"] == "DISCOVERED"
    assert payload["provider"]["provider_id"] == "ECP-PROVIDER-OPENAI"
    assert {m["model_identifier"] for m in payload["models"]} == {"gpt-4o", "gpt-4o-mini"}
    assert SECRET not in raw
    status, payload, _, raw = request(gateway, "POST", "/api/v1/session/targets", {"credential_ref": credential_ref, "model_identifier": "gpt-4o"}, token=token)
    assert status == 200
    assert payload["ready"] == "READY"
    assert SECRET not in raw
    record_request = {
        "evaluation_id": payload["evaluation_id"],
        "system_id": payload["system_id"],
        "credential_ref": payload["credential_ref"],
        "test_id": payload["test_id"],
        "request_id": "http-session-execution-1",
    }
    status, record, _, raw = request(gateway, "POST", "/api/v1/executions", record_request, token=token)
    assert status == 200
    assert record["status"] == "SUCCESS"
    assert record["evidence_status"] == "GENERATED"
    assert record["audit_status"] == "GENERATED"
    assert record["evidence_id"].startswith("ECP-EVID-CONSOLE-")
    assert record["audit_id"].startswith("ECP-AUDIT-CONSOLE-")
    assert SECRET not in raw
    status, payload, _, raw = request(gateway, "POST", "/api/v1/credentials/session/revoke", {"credential_ref": credential_ref}, token=token)
    assert status == 200
    assert payload["status"] == "REVOKED"
    assert SECRET not in raw


def test_http_invalid_session_payloads_are_rejected(running_stack):
    gateway = running_stack["gateway"]
    token = pair_over_http(gateway)
    status, payload, _, _ = request(gateway, "POST", "/api/v1/credentials/session", {"credential_secret": ""}, token=token)
    assert status == 400 and payload["state"] == "INVALID"
    status, payload, _, _ = request(gateway, "POST", "/api/v1/credentials/session", {}, token=token)
    assert status == 400 and payload["state"] == "INVALID"
    status, payload, _, _ = request(gateway, "POST", "/api/v1/discovery", {"credential_ref": ""}, token=token)
    assert status == 400 and payload["state"] == "INVALID"
    status, payload, _, _ = request(gateway, "POST", "/api/v1/discovery", {"credential_ref": "ECP-SESSION-CREDENTIAL-UNKNOWN00000"}, token=token)
    assert status == 400 and payload["state"] == "INVALID"
    status, payload, _, _ = request(gateway, "POST", "/api/v1/session/targets", {"credential_ref": "ECP-SESSION-CREDENTIAL-UNKNOWN00000", "model_identifier": "x"}, token=token)
    assert status == 400 and payload["state"] == "INVALID"


def test_http_discovery_failure_reports_unknown_without_guessing(running_stack):
    running_stack["transport"].routes[OPENAI_MODELS_URL] = (401, b'{"error":"bad"}')
    gateway = running_stack["gateway"]
    token = pair_over_http(gateway)
    _, payload, _, _ = request(gateway, "POST", "/api/v1/credentials/session", {"credential_secret": SECRET}, token=token)
    credential_ref = payload["credential_ref"]
    status, document, _, _ = request(gateway, "POST", "/api/v1/discovery", {"credential_ref": credential_ref}, token=token)
    assert status == 200
    assert document["status"] == "DISCOVERY_FAILED"
    assert document["identification"] == "UNKNOWN"
    assert document["provider"]["identification"] == "UNKNOWN"
    assert document["models"] == []
    outcomes = {probe["outcome"] for probe in document["probes"]}
    assert "CREDENTIAL_REJECTED" in outcomes


def test_http_error_messages_redact_submitted_secrets(running_stack):
    gateway = running_stack["gateway"]
    token = pair_over_http(gateway)
    leak = "sk-leak-attempt-VALUE-123456"
    status, payload, _, raw = request(gateway, "POST", "/api/v1/credentials/session", {"credential_secret": leak + "\nInjected: Header"}, token=token)
    assert status == 400
    assert leak not in raw and "Injected" not in raw


def test_http_preflight_allows_session_routes(running_stack):
    gateway = running_stack["gateway"]
    status, _, headers = request(gateway, "OPTIONS", "/api/v1/discovery")[:3]
    assert status == 204
    assert "X-ECP-Session" in headers.get("Access-Control-Allow-Headers", "")


def test_http_oversized_session_body_is_rejected(running_stack):
    gateway = running_stack["gateway"]
    token = pair_over_http(gateway)
    huge = {"credential_secret": "x" * 20000}
    status, payload, _, _ = request(gateway, "POST", "/api/v1/credentials/session", huge, token=token)
    assert status == 400


def test_session_catalog_integration_shows_session_targets(running_stack):
    gateway = running_stack["gateway"]
    token = pair_over_http(gateway)
    _, payload, _, _ = request(gateway, "POST", "/api/v1/credentials/session", {"credential_secret": SECRET}, token=token)
    credential_ref = payload["credential_ref"]
    _, payload, _, _ = request(gateway, "POST", "/api/v1/discovery", {"credential_ref": credential_ref}, token=token)
    _, selection, _, _ = request(gateway, "POST", "/api/v1/session/targets", {"credential_ref": credential_ref, "model_identifier": "gpt-4o"}, token=token)
    _, catalog, _, _ = request(gateway, "GET", "/api/v1/catalog", token=token)
    evaluation_ids = [e["evaluation_id"] for e in catalog["evaluations"]]
    assert selection["evaluation_id"] in evaluation_ids
    entry = [e for e in catalog["evaluations"] if e["evaluation_id"] == selection["evaluation_id"]][0]
    assert entry["provider"] == "ECP-PROVIDER-OPENAI"
    assert entry["credential"]["credential_id"] == credential_ref
    assert entry["credential"]["status"] == "PROVISIONED"


def test_default_session_ttl_is_sane():
    assert 60 <= DEFAULT_SESSION_TTL_SECONDS <= 86400


# ---------------------------------------------------------------------------
# UNIVERSAL REAL PROVIDER EXECUTION BINDING v1 (owner order 2026-09-12)
#
# These tests pin the exact binding the owner doubted: RUN EVALUATION must
# execute the SELECTED discovered model through the REAL provider adapter
# class with the REAL credential-session lease, at the REAL provider endpoint,
# with transport attribution that makes a real external call unmistakable —
# and the offline demo must never be reachable from that path.
# ---------------------------------------------------------------------------

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_MODELS_BODY = {
    "data": [
        {"id": "~z-ai/glm-flash-latest", "object": "model", "owned_by": "z-ai"},
        {"id": "inclusionai/ling-3.0-flash-sante:free", "object": "model", "owned_by": "inclusionai"},
    ]
}


class RecordingExecutionTransport:
    """Fake POST transport recording every (endpoint, headers, payload)."""

    def __init__(self, respond):
        self.calls = []
        self._respond = respond

    def __call__(self, endpoint, headers, payload, timeout):
        self.calls.append((endpoint, dict(headers), json.loads(payload.decode("utf-8"))))
        return self._respond()


def _openrouter_chat_response(model, text="ECP-CONFORMANCE-OK"):
    return (
        200,
        json.dumps(
            {
                "id": "gen-binding-" + uuid.uuid4().hex[:8],
                "model": model,
                "choices": [{"message": {"role": "assistant", "content": text}}],
            }
        ).encode(),
    )


def build_real_adapter_stack(tmp_path, execution):
    """Session stack whose adapter factory builds the REAL chat-completions adapter.

    Discovery probes are fakes (offline); the execution adapter is the genuine
    OpenRouterChatCompletionsAdapter over the given recording fake transport,
    so the exact endpoint, headers and body of the real dialect are asserted
    without any network access.
    """
    from ecp.runtime_adapters import OpenRouterChatCompletionsAdapter

    def factory(kind, *, model, endpoint, provider, adapter_id, token_header=None, bearer_value=None, extra_headers=None):
        assert kind == "openrouter-chat-completions"
        return OpenRouterChatCompletionsAdapter(
            model=model,
            endpoint=endpoint,
            provider=provider,
            adapter_id=adapter_id,
            transport=execution,
            token_header=token_header,
            bearer_value=bearer_value,
            extra_headers=extra_headers,
        )

    stack = build_stack(
        tmp_path,
        routes={OPENROUTER_MODELS_URL: (200, json.dumps(OPENROUTER_MODELS_BODY).encode())},
    )
    stack["manager"]._adapter_factory = factory
    stack["execution"] = execution
    return stack


def test_selected_model_reaches_the_real_openrouter_adapter_literally(tmp_path):
    execution_transport = RecordingExecutionTransport(lambda: _openrouter_chat_response("~z-ai/glm-flash-latest"))
    stack = build_real_adapter_stack(tmp_path, execution_transport)
    handle = open_session(stack)
    document = stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    assert document["status"] == "DISCOVERED"
    assert document["provider"]["provider_id"] == "ECP-PROVIDER-OPENROUTER"
    selection = stack["manager"].select_target(
        {"credential_ref": handle["credential_ref"], "model_identifier": "~z-ai/glm-flash-latest"}
    )
    assert selection["ready"] == "READY"
    assert selection["model_identifier"] == "~z-ai/glm-flash-latest"
    record = stack["gateway"].execute({
        "evaluation_id": selection["evaluation_id"],
        "system_id": selection["system_id"],
        "credential_ref": selection["credential_ref"],
        "test_id": selection["test_id"],
        "request_id": "binding-real-openrouter-1",
    })
    # THE binding proof: exactly one real-dialect HTTP request, to the real
    # OpenRouter chat-completions endpoint, with the session credential lease
    # as the bearer credential and the SELECTED model identifier verbatim.
    assert len(execution_transport.calls) == 1
    endpoint, headers, payload = execution_transport.calls[0]
    assert endpoint == "https://openrouter.ai/api/v1/chat/completions"
    assert headers["Authorization"] == f"Bearer {SECRET}"
    assert payload["model"] == "~z-ai/glm-flash-latest"
    assert payload["stream"] is False
    assert payload["messages"][0]["role"] == "user"
    # Transport attribution on the record: real external call, unmistakable.
    assert record["status"] == "SUCCESS"
    assert record["provider"] == "ECP-PROVIDER-OPENROUTER"
    assert record["model"] == "~z-ai/glm-flash-latest"
    assert record["adapter"] == selection["adapter_id"]
    assert record["endpoint"] == "https://openrouter.ai/api/v1/chat/completions"
    assert record["result"]["transport_kind"] == "http"
    assert record["result"]["http_status"] == 200
    assert isinstance(record["result"]["latency_ms"], int) and record["result"]["latency_ms"] >= 0
    assert record["result"]["response_id"].startswith("gen-binding-")
    # Transport attribution on the persisted evidence document.
    evidence_path = Path(tmp_path) / "external-executions" / record["execution_id"] / "evidence.json"
    evidence = json.loads(evidence_path.read_text())
    assert evidence["provider"] == "ECP-PROVIDER-OPENROUTER"
    assert evidence["model"] == "~z-ai/glm-flash-latest"
    assert evidence["transport_kind"] == "http"
    assert evidence["endpoint"] == "https://openrouter.ai/api/v1/chat/completions"
    assert evidence["http_status"] == 200
    assert evidence["result"]["transport_kind"] == "http"
    # No credential anywhere.
    for blob in (json.dumps(record), json.dumps(evidence), json.dumps(selection)):
        assert SECRET not in blob


def test_session_execution_never_invokes_the_offline_demo(tmp_path):
    """The demo/offline evaluation must be unreachable from RUN EVALUATION."""
    import run_console as launcher

    execution_transport = RecordingExecutionTransport(lambda: _openrouter_chat_response("~z-ai/glm-flash-latest"))
    from ecp.runtime_adapters import OpenRouterChatCompletionsAdapter

    def factory(kind, *, model, endpoint, provider, adapter_id, token_header=None, bearer_value=None, extra_headers=None):
        return OpenRouterChatCompletionsAdapter(
            model=model, endpoint=endpoint, provider=provider, adapter_id=adapter_id,
            transport=execution_transport,
            token_header=token_header, bearer_value=bearer_value, extra_headers=extra_headers,
        )

    configuration = json.loads(json.dumps(launcher.BUILTIN_DEMO_CONFIGURATION))
    gateway, service = launcher.build_gateway(
        configuration,
        GatewayConfig(frozenset({ORIGIN}), artifact_root=Path(tmp_path)),
        session_adapter_factory=factory,
    )
    manager = gateway._session_console
    # Offline demo adapter tripwire: any invocation fails the test loudly.
    demo_adapter = gateway.adapters.get("ECP-ADAPTER-DEMO-OFFLINE")
    assert demo_adapter is not None
    original_demo_execute = demo_adapter.execute
    tripwire_fired = []

    def tripwire(lease, request):
        tripwire_fired.append(True)
        raise AssertionError("the offline demo adapter was invoked by the session execution path")

    demo_adapter.execute = tripwire
    # Discovery probes stay offline (fake transport injection).
    manager._discovery._transport = FakeProbeTransport(
        {OPENROUTER_MODELS_URL: (200, json.dumps(OPENROUTER_MODELS_BODY).encode())}
    )
    handle = manager.open_session({"credential_secret": SECRET})
    document = manager.discover({"credential_ref": handle["credential_ref"]})
    assert document["status"] == "DISCOVERED"
    selection = manager.select_target(
        {"credential_ref": handle["credential_ref"], "model_identifier": "~z-ai/glm-flash-latest"}
    )
    record = gateway.execute({
        "evaluation_id": selection["evaluation_id"],
        "system_id": selection["system_id"],
        "credential_ref": selection["credential_ref"],
        "test_id": selection["test_id"],
        "request_id": "binding-no-demo-1",
    })
    assert record["status"] == "SUCCESS"
    assert record["evaluation_id"] == selection["evaluation_id"]
    assert record["evaluation_id"] != "ECP-EVAL-DEMO-OFFLINE-1"
    assert record["provider"] == "ECP-PROVIDER-OPENROUTER"
    assert record["result"]["transport_kind"] == "http"
    assert SECRET not in json.dumps(record)
    assert not tripwire_fired  # the demo adapter was never touched by the session flow
    # And the demo evaluation itself, when explicitly run, labels itself offline.
    demo_adapter.execute = original_demo_execute
    demo_record = gateway.execute({
        "evaluation_id": "ECP-EVAL-DEMO-OFFLINE-1",
        "system_id": "ECP-SYSTEM-DEMO-OFFLINE-1",
        "credential_ref": "ECP-DEMO-CREDENTIAL-OFFLINE",
        "test_id": "ECP-TEST-DEMO-OFFLINE-1",
        "request_id": "binding-demo-explicit-1",
    })
    assert demo_record["status"] == "SUCCESS"
    assert demo_record["result"]["transport_kind"] == "offline-mock"
    assert demo_record["result"]["network"] == "none"


def test_real_provider_failure_surfaces_honestly(tmp_path):
    """A provider rejection is a REAL failure with provider/model/status — never a fake SUCCESS."""
    rejected = RecordingExecutionTransport(
        lambda: (401, json.dumps({"error": {"message": "No auth credentials found in request", "code": 401}}).encode())
    )
    stack = build_real_adapter_stack(tmp_path, rejected)
    handle = open_session(stack)
    stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    selection = stack["manager"].select_target(
        {"credential_ref": handle["credential_ref"], "model_identifier": "inclusionai/ling-3.0-flash-sante:free"}
    )
    record = stack["gateway"].execute({
        "evaluation_id": selection["evaluation_id"],
        "system_id": selection["system_id"],
        "credential_ref": selection["credential_ref"],
        "test_id": selection["test_id"],
        "request_id": "binding-real-failure-1",
    })
    assert record["status"] == "FAILED"
    assert record["execution_status"] == "PROVIDER_AUTHENTICATION_FAILED"
    assert record["error_classification"] == "PROVIDER_AUTHENTICATION_FAILED"
    assert record["http_status"] == 401
    assert record["provider"] == "ECP-PROVIDER-OPENROUTER"
    assert record["model"] == "inclusionai/ling-3.0-flash-sante:free"
    assert record["endpoint"] == "https://openrouter.ai/api/v1/chat/completions"
    assert record["response_status"] == "NOT_RECEIVED"
    assert record["evidence_status"] == "NOT_GENERATED"
    # No evidence artifacts for the failed execution; no secret anywhere.
    assert not (Path(tmp_path) / "external-executions" / record["execution_id"]).exists()
    assert SECRET not in json.dumps(record)
    assert SECRET not in record["error"]


def test_execution_request_after_session_open_carries_identifiers_only(tmp_path):
    """After the session opens, the execution request payload is identifiers only."""
    stack = build_real_adapter_stack(tmp_path, RecordingExecutionTransport(lambda: _openrouter_chat_response("~z-ai/glm-flash-latest")))
    handle = open_session(stack)
    stack["manager"].discover({"credential_ref": handle["credential_ref"]})
    selection = stack["manager"].select_target(
        {"credential_ref": handle["credential_ref"], "model_identifier": "~z-ai/glm-flash-latest"}
    )
    request = {
        "evaluation_id": selection["evaluation_id"],
        "system_id": selection["system_id"],
        "credential_ref": selection["credential_ref"],
        "test_id": selection["test_id"],
        "request_id": "binding-identifiers-only-1",
    }
    record = stack["gateway"].execute(request)
    assert record["status"] == "SUCCESS"
    assert set(request) == {"evaluation_id", "system_id", "credential_ref", "test_id", "request_id"}
    assert SECRET not in json.dumps(request)
    # The browser builds exactly this identifier set (static contract pin).
    app = (Path(__file__).resolve().parents[1] / "console" / "app.js").read_text()
    assert "const request = { evaluation_id: target.evaluation_id, system_id: target.system_id, credential_ref: target.credential_ref, test_id: target.test_id, request_id: requestId };" in app


# ---------------------------------------------------------------------------
# Custom-endpoint gateway header knobs (non-secret configuration)
# ---------------------------------------------------------------------------


CUSTOM_BASE = "http://127.0.0.1:9099/v1"
CUSTOM_MODELS_BODY = {"data": [{"id": "gateway-model-a", "object": "model"}]}


def test_gateway_headers_flow_from_discovery_probe_to_execution_headers(tmp_path):
    execution_transport = RecordingExecutionTransport(lambda: _openrouter_chat_response("gateway-model-a"))
    stack = build_stack(tmp_path, routes={CUSTOM_BASE + "/models": (200, json.dumps(CUSTOM_MODELS_BODY).encode())})
    from ecp.runtime_adapters import OpenRouterChatCompletionsAdapter

    def factory(kind, *, model, endpoint, provider, adapter_id, token_header=None, bearer_value=None, extra_headers=None):
        return OpenRouterChatCompletionsAdapter(
            model=model, endpoint=endpoint, provider=provider, adapter_id=adapter_id,
            transport=execution_transport,
            token_header=token_header, bearer_value=bearer_value, extra_headers=extra_headers,
        )

    stack["manager"]._adapter_factory = factory
    handle = open_session(stack)
    document = stack["manager"].discover({
        "credential_ref": handle["credential_ref"],
        "base_url": CUSTOM_BASE,
        "gateway_headers": {"token_header": "X-Token", "bearer_value": "public-marker", "extra_headers": {"X-Route": "alpha"}},
    })
    assert document["status"] == "DISCOVERED"
    # Probe headers carried the placement contract.
    probe_url, probe_headers = stack["transport"].calls[-1]
    assert probe_url == CUSTOM_BASE + "/models"
    assert probe_headers["X-Token"] == SECRET
    assert probe_headers["Authorization"] == "Bearer public-marker"
    assert probe_headers["X-Route"] == "alpha"
    # The report echoes the non-secret configuration for the owner.
    assert document["gateway_headers"] == {"token_header": "X-Token", "bearer_value": "public-marker", "extra_headers": {"X-Route": "alpha"}}
    selection = stack["manager"].select_target(
        {"credential_ref": handle["credential_ref"], "model_identifier": "gateway-model-a"}
    )
    record = stack["gateway"].execute({
        "evaluation_id": selection["evaluation_id"],
        "system_id": selection["system_id"],
        "credential_ref": selection["credential_ref"],
        "test_id": selection["test_id"],
        "request_id": "binding-gateway-headers-1",
    })
    assert record["status"] == "SUCCESS"
    # Execution headers use the SAME placement: lease in X-Token, public marker as bearer.
    endpoint, headers, payload = execution_transport.calls[0]
    assert endpoint == CUSTOM_BASE + "/chat/completions"
    assert headers["X-Token"] == SECRET
    assert headers["Authorization"] == "Bearer public-marker"
    assert headers["X-Route"] == "alpha"
    assert payload["model"] == "gateway-model-a"
    assert record["result"]["transport_kind"] == "http"
    assert SECRET not in json.dumps(record)


def test_gateway_headers_require_a_custom_endpoint(tmp_path):
    stack = build_stack(tmp_path)
    handle = open_session(stack)
    with pytest.raises(SessionConsoleError, match="requires a custom endpoint"):
        stack["manager"].discover({
            "credential_ref": handle["credential_ref"],
            "gateway_headers": {"token_header": "X-Token"},
        })


def test_gateway_headers_reject_invalid_configuration(tmp_path):
    stack = build_stack(tmp_path, routes={CUSTOM_BASE + "/models": (200, json.dumps(CUSTOM_MODELS_BODY).encode())})
    handle = open_session(stack)
    with pytest.raises(SessionConsoleError, match="gateway_headers is invalid"):
        stack["manager"].discover({
            "credential_ref": handle["credential_ref"],
            "base_url": CUSTOM_BASE,
            "gateway_headers": {"token_header": "Authorization"},
        })
    with pytest.raises(SessionConsoleError, match="gateway_headers is invalid"):
        stack["manager"].discover({
            "credential_ref": handle["credential_ref"],
            "base_url": CUSTOM_BASE,
            "gateway_headers": {"bearer_value": "orphan-marker"},
        })
    with pytest.raises(SessionConsoleError, match="unknown keys"):
        stack["manager"].discover({
            "credential_ref": handle["credential_ref"],
            "base_url": CUSTOM_BASE,
            "gateway_headers": {"unexpected": "value"},
        })


def test_re_discovery_with_different_headers_does_not_replay_cached_selection(tmp_path):
    first = RecordingExecutionTransport(lambda: _openrouter_chat_response("gateway-model-a"))
    second = RecordingExecutionTransport(lambda: _openrouter_chat_response("gateway-model-a"))
    stack = build_stack(tmp_path, routes={CUSTOM_BASE + "/models": (200, json.dumps(CUSTOM_MODELS_BODY).encode())})
    from ecp.runtime_adapters import OpenRouterChatCompletionsAdapter

    current = {"transport": first}

    def factory(kind, *, model, endpoint, provider, adapter_id, token_header=None, bearer_value=None, extra_headers=None):
        return OpenRouterChatCompletionsAdapter(
            model=model, endpoint=endpoint, provider=provider, adapter_id=adapter_id,
            transport=current["transport"],
            token_header=token_header, bearer_value=bearer_value, extra_headers=extra_headers,
        )

    stack["manager"]._adapter_factory = factory
    handle = open_session(stack)
    stack["manager"].discover({
        "credential_ref": handle["credential_ref"], "base_url": CUSTOM_BASE,
        "gateway_headers": {"token_header": "X-Token", "bearer_value": "marker-one"},
    })
    first_selection = stack["manager"].select_target(
        {"credential_ref": handle["credential_ref"], "model_identifier": "gateway-model-a"}
    )
    # Re-discover with different non-secret header placement; same model.
    stack["manager"].discover({
        "credential_ref": handle["credential_ref"], "base_url": CUSTOM_BASE,
        "gateway_headers": {"token_header": "X-Token", "bearer_value": "marker-two"},
    })
    current["transport"] = second
    second_selection = stack["manager"].select_target(
        {"credential_ref": handle["credential_ref"], "model_identifier": "gateway-model-a"}
    )
    assert second_selection["target_id"] != first_selection["target_id"]
    record = stack["gateway"].execute({
        "evaluation_id": second_selection["evaluation_id"],
        "system_id": second_selection["system_id"],
        "credential_ref": second_selection["credential_ref"],
        "test_id": second_selection["test_id"],
        "request_id": "binding-rebind-1",
    })
    assert record["status"] == "SUCCESS"
    _, headers, _ = second.calls[0]
    assert headers["Authorization"] == "Bearer marker-two"


def test_custom_endpoint_without_headers_keeps_the_bearer_contract(tmp_path):
    execution_transport = RecordingExecutionTransport(lambda: _openrouter_chat_response("gateway-model-a"))
    stack = build_stack(tmp_path, routes={CUSTOM_BASE + "/models": (200, json.dumps(CUSTOM_MODELS_BODY).encode())})
    from ecp.runtime_adapters import OpenRouterChatCompletionsAdapter

    def factory(kind, *, model, endpoint, provider, adapter_id, token_header=None, bearer_value=None, extra_headers=None):
        assert token_header is None and bearer_value is None and extra_headers is None
        return OpenRouterChatCompletionsAdapter(
            model=model, endpoint=endpoint, provider=provider, adapter_id=adapter_id, transport=execution_transport
        )

    stack["manager"]._adapter_factory = factory
    handle = open_session(stack)
    document = stack["manager"].discover({"credential_ref": handle["credential_ref"], "base_url": CUSTOM_BASE})
    assert document["status"] == "DISCOVERED"
    assert "gateway_headers" not in document
    selection = stack["manager"].select_target(
        {"credential_ref": handle["credential_ref"], "model_identifier": "gateway-model-a"}
    )
    stack["gateway"].execute({
        "evaluation_id": selection["evaluation_id"],
        "system_id": selection["system_id"],
        "credential_ref": selection["credential_ref"],
        "test_id": selection["test_id"],
        "request_id": "binding-bearer-default-1",
    })
    _, headers, _ = execution_transport.calls[0]
    assert headers["Authorization"] == f"Bearer {SECRET}"
