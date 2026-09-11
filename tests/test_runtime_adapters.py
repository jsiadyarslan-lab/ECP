import json

import pytest

from ecp.console import AuthorizedEvaluation, AuthorizedTest, GatewayConfig, LocalGateway
from ecp.credential_binding import AuthorizationGrant, CredentialBinding
from ecp.credentials import CredentialGateway, CredentialIdentity, SecretLease
from ecp.runtime_adapters import (
    GeminiGenerateContentAdapter,
    OpenAIResponsesAdapter,
    RuntimeAdapterBindingError,
    RuntimeAdapterRegistry,
    RuntimeAdapterTransportError,
    RuntimeAdapterUnavailable,
)


class AdapterA:
    provider = "provider-a"
    adapter_id = "adapter-a"

    def execute(self, lease, request):
        assert lease.value == "synthetic-secret"
        return {"kind": "a", "request_id": request["request_id"], "secret": lease.value}


class AdapterB:
    provider = "provider-b"
    adapter_id = "adapter-b"

    def execute(self, lease, request):
        assert lease.value == "synthetic-secret"
        return {"kind": "b", "request_id": request["request_id"]}


def test_runtime_registry_supports_distinct_provider_neutral_adapters():
    registry = RuntimeAdapterRegistry({"adapter-a": AdapterA(), "adapter-b": AdapterB()})
    assert registry.resolve("adapter-a", "provider-a").execute
    assert registry.resolve("adapter-b", "provider-b").execute
    with pytest.raises(RuntimeAdapterBindingError):
        registry.resolve("adapter-a", "provider-b")
    registry.clear()
    with pytest.raises(RuntimeAdapterUnavailable):
        registry.resolve("adapter-a", "provider-a")


def test_openai_adapter_normalizes_response_and_never_returns_credential():
    def transport(endpoint, headers, payload, timeout):
        assert endpoint.endswith("/responses")
        assert headers["Authorization"] == "Bearer synthetic-secret"
        assert json.loads(payload)["model"] == "test-model"
        return 200, json.dumps({"id": "resp-test", "output_text": "ECP-CONFORMANCE-OK"}).encode()

    adapter = OpenAIResponsesAdapter(model="test-model", endpoint="https://provider.invalid/responses", transport=transport)
    result = adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-1"})
    assert result == {
        "provider_status": "RECEIVED",
        "response_id": "resp-test",
        "model": "test-model",
        "output_text": "ECP-CONFORMANCE-OK",
        "request_id": "request-1",
    }
    assert "synthetic-secret" not in json.dumps(result)


def test_openai_adapter_maps_provider_failures_without_response_body():
    def transport(endpoint, headers, payload, timeout):
        return 401, b"provider body may contain sensitive details"

    adapter = OpenAIResponsesAdapter(model="test-model", endpoint="https://provider.invalid/responses", transport=transport)
    with pytest.raises(RuntimeAdapterTransportError, match="PROVIDER_AUTHENTICATION_FAILED"):
        adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-2"})


def test_openai_adapter_classifies_rate_limit_without_exposing_provider_body():
    body = json.dumps({"error": {"message": "sensitive provider detail", "type": "rate_limit_exceeded", "code": "rate_limit_exceeded"}}).encode()

    def transport(endpoint, headers, payload, timeout):
        return 429, body

    adapter = OpenAIResponsesAdapter(model="test-model", endpoint="https://api.openai.com/v1/responses", transport=transport)
    with pytest.raises(RuntimeAdapterTransportError, match="PROVIDER_RATE_LIMITED") as exc_info:
        adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-429"})
    assert "sensitive provider detail" not in str(exc_info.value)
    assert "synthetic-secret" not in str(exc_info.value)


def test_openai_adapter_classifies_insufficient_quota():
    body = json.dumps({"error": {"type": "insufficient_quota", "code": "insufficient_quota"}}).encode()

    def transport(endpoint, headers, payload, timeout):
        return 429, body

    adapter = OpenAIResponsesAdapter(model="test-model", endpoint="https://api.openai.com/v1/responses", transport=transport)
    with pytest.raises(RuntimeAdapterTransportError, match="PROVIDER_QUOTA_EXCEEDED"):
        adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-quota"})


def test_gemini_adapter_normalizes_generate_content_response_without_credential():
    def transport(endpoint, headers, payload, timeout):
        assert endpoint.endswith("/models/gemini-test:generateContent")
        assert headers["x-goog-api-key"] == "synthetic-secret"
        assert json.loads(payload)["contents"][0]["parts"][0]["text"]
        return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": "ECP-CONFORMANCE-OK"}]}}]}).encode()

    adapter = GeminiGenerateContentAdapter(model="gemini-test", endpoint="https://provider.invalid/v1beta/models/gemini-test:generateContent", transport=transport)
    result = adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-gemini"})
    assert result == {
        "provider_status": "RECEIVED",
        "response_id": None,
        "model": "gemini-test",
        "output_text": "ECP-CONFORMANCE-OK",
        "request_id": "request-gemini",
    }
    assert "synthetic-secret" not in json.dumps(result)


def test_gemini_adapter_maps_provider_failures_safely():
    def transport(endpoint, headers, payload, timeout):
        return 429, b"provider body may contain sensitive details"

    adapter = GeminiGenerateContentAdapter(model="gemini-test", endpoint="https://provider.invalid/generateContent", transport=transport)
    with pytest.raises(RuntimeAdapterTransportError, match="PROVIDER_RATE_LIMITED") as exc_info:
        adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-gemini-429"})
    assert "sensitive details" not in str(exc_info.value)
    assert "synthetic-secret" not in str(exc_info.value)


def test_openai_adapter_exposes_safe_transport_reason():
    def transport(endpoint, headers, payload, timeout):
        raise OSError("network unreachable")

    adapter = OpenAIResponsesAdapter(model="test-model", endpoint="https://api.openai.com/v1/responses", transport=transport)
    with pytest.raises(RuntimeAdapterTransportError, match=r"PROVIDER_CONNECTION_FAILED host=api\.openai\.com reason=network unreachable"):
        adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-3"})


def test_gateway_uses_runtime_registry_and_preserves_safe_record(tmp_path):
    identity = CredentialIdentity("cred-runtime", "provider-a", "test", frozenset({"execute"}))
    credentials, _store = CredentialGateway.for_testing({identity.credential_id: identity})
    credentials.provision_for_testing(identity.credential_id, "synthetic-secret")
    binding = CredentialBinding("ECP-BIND-RUNTIME", "ECP-REQ-RUNTIME", "ECP-SYSTEM-RUNTIME", "provider-a", "interface", "execute", identity.credential_id, frozenset({"execute"}))
    grant = AuthorizationGrant("ECP-AUTH-RUNTIME", binding.binding_id, binding.target_id, "execute", frozenset({"execute"}), "2099-01-01T00:00:00Z")
    evaluation = AuthorizedEvaluation("ECP-EVAL-RUNTIME", binding.target_id, "provider-a", "adapter-a", identity, (AuthorizedTest("ECP-TEST-RUNTIME", "runtime", "execute"),), binding, grant)
    gateway = LocalGateway(GatewayConfig(frozenset({"http://localhost:8766"}), artifact_root=tmp_path), {evaluation.evaluation_id: evaluation}, credentials, RuntimeAdapterRegistry({"adapter-a": AdapterA()}))
    result = gateway.execute({"evaluation_id": "ECP-EVAL-RUNTIME", "system_id": "ECP-SYSTEM-RUNTIME", "credential_ref": "cred-runtime", "test_id": "ECP-TEST-RUNTIME", "request_id": "ECP-REQUEST-RUNTIME"})
    assert result["status"] == "SUCCESS"
    assert result["response_status"] == "RECEIVED"
    assert result["evidence_status"] == "GENERATED"
    assert "synthetic-secret" not in json.dumps(result)
    assert all("synthetic-secret" not in path.read_text() for path in tmp_path.rglob("*.json"))
