import json

import pytest

from ecp.console import AuthorizedEvaluation, AuthorizedTest, GatewayConfig, LocalGateway
from ecp.credential_binding import AuthorizationGrant, CredentialBinding
from ecp.credentials import CredentialGateway, CredentialIdentity, SecretLease
from ecp.runtime_adapters import (
    AnthropicMessagesAdapter,
    GeminiGenerateContentAdapter,
    OpenAIResponsesAdapter,
    OpenRouterChatCompletionsAdapter,
    RuntimeAdapterBindingError,
    RuntimeAdapterRegistry,
    RuntimeAdapterTransportError,
    RuntimeAdapterUnavailable,
    anthropic_conformance_adapter,
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
    latency_ms = result.pop("latency_ms")
    assert isinstance(latency_ms, int) and latency_ms >= 0
    assert result == {
        "provider_status": "RECEIVED",
        "response_id": "resp-test",
        "model": "test-model",
        "output_text": "ECP-CONFORMANCE-OK",
        "request_id": "request-1",
        "transport_kind": "http",
        "endpoint": "https://provider.invalid/responses",
        "http_status": 200,
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
    latency_ms = result.pop("latency_ms")
    assert isinstance(latency_ms, int) and latency_ms >= 0
    assert result == {
        "provider_status": "RECEIVED",
        "response_id": None,
        "model": "gemini-test",
        "output_text": "ECP-CONFORMANCE-OK",
        "request_id": "request-gemini",
        "transport_kind": "http",
        "endpoint": "https://provider.invalid/v1beta/models/gemini-test:generateContent",
        "http_status": 200,
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


def test_openrouter_adapter_normalizes_chat_completion_without_credential():
    def transport(endpoint, headers, payload, timeout):
        assert endpoint.endswith("/chat/completions")
        assert headers["Authorization"] == "Bearer synthetic-secret"
        request = json.loads(payload)
        assert request["model"] == "openrouter/free"
        assert request["stream"] is False
        assert request["messages"][0]["role"] == "user"
        return 200, json.dumps({"id": "gen-test", "choices": [{"message": {"role": "assistant", "content": "ECP-CONFORMANCE-OK"}}]}).encode()

    adapter = OpenRouterChatCompletionsAdapter(model="openrouter/free", endpoint="https://openrouter.invalid/api/v1/chat/completions", transport=transport)
    result = adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-openrouter"})
    latency_ms = result.pop("latency_ms")
    assert isinstance(latency_ms, int) and latency_ms >= 0
    assert result == {
        "provider_status": "RECEIVED",
        "response_id": "gen-test",
        "model": "openrouter/free",
        "output_text": "ECP-CONFORMANCE-OK",
        "request_id": "request-openrouter",
        "transport_kind": "http",
        "endpoint": "https://openrouter.invalid/api/v1/chat/completions",
        "http_status": 200,
    }
    assert "synthetic-secret" not in json.dumps(result)


def test_openrouter_adapter_maps_provider_failures_safely():
    def transport(endpoint, headers, payload, timeout):
        return 429, b"provider body may contain sensitive details"

    adapter = OpenRouterChatCompletionsAdapter(model="openrouter/free", endpoint="https://openrouter.invalid/api/v1/chat/completions", transport=transport)
    with pytest.raises(RuntimeAdapterTransportError, match="PROVIDER_RATE_LIMITED") as exc_info:
        adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-openrouter-429"})
    assert "sensitive details" not in str(exc_info.value)
    assert "synthetic-secret" not in str(exc_info.value)


# Gateway-header dialect (generic OpenAI-compatible chat-completions gateways)


def test_openrouter_adapter_default_contract_is_byte_identical():
    seen = {}

    def transport(endpoint, headers, payload, timeout):
        seen["headers"] = dict(headers)
        return 200, json.dumps({"id": "gen-default", "choices": [{"message": {"content": "ECP-CONFORMANCE-OK"}}]}).encode()

    adapter = OpenRouterChatCompletionsAdapter(model="dialect-model", endpoint="https://gateway.invalid/api/v1/chat/completions", transport=transport)
    adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-dialect-default"})
    assert seen["headers"] == {"Authorization": "Bearer synthetic-secret", "Content-Type": "application/json"}


def test_openrouter_adapter_places_lease_in_configured_gateway_header():
    seen = {}

    def transport(endpoint, headers, payload, timeout):
        seen["headers"] = dict(headers)
        request = json.loads(payload)
        assert request["model"] == "dialect-model"
        assert request["stream"] is False
        return 200, json.dumps({"id": "gen-gateway", "choices": [{"message": {"content": "ECP-CONFORMANCE-OK"}}]}).encode()

    adapter = OpenRouterChatCompletionsAdapter(
        model="dialect-model",
        endpoint="https://gateway.invalid/api/v1/chat/completions",
        transport=transport,
        token_header="X-Gateway-Token",
        bearer_value="public-product-marker",
        extra_headers={"X-Gateway-Route": "route-1"},
    )
    result = adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-dialect-gateway"})
    assert seen["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer public-product-marker",
        "X-Gateway-Token": "synthetic-secret",
        "X-Gateway-Route": "route-1",
    }
    assert result["provider_status"] == "RECEIVED"
    assert result["output_text"] == "ECP-CONFORMANCE-OK"
    assert "synthetic-secret" not in json.dumps(result)


def test_openrouter_adapter_gateway_failures_never_leak_lease():
    def transport(endpoint, headers, payload, timeout):
        return 403, b"gateway rejection body"

    adapter = OpenRouterChatCompletionsAdapter(
        model="dialect-model",
        endpoint="https://gateway.invalid/api/v1/chat/completions",
        transport=transport,
        token_header="X-Gateway-Token",
        bearer_value="public-product-marker",
    )
    with pytest.raises(RuntimeAdapterTransportError, match="PROVIDER_AUTHENTICATION_FAILED") as exc_info:
        adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-dialect-403"})
    assert "synthetic-secret" not in str(exc_info.value)
    assert "gateway rejection body" not in str(exc_info.value)


def test_openrouter_adapter_rejects_invalid_gateway_header_configuration():
    base = {"model": "dialect-model", "endpoint": "https://gateway.invalid/api/v1/chat/completions"}
    with pytest.raises(ValueError, match="token_header"):
        OpenRouterChatCompletionsAdapter(**base, token_header="Bad Header Name")
    with pytest.raises(ValueError, match="token_header"):
        OpenRouterChatCompletionsAdapter(**base, token_header="Authorization")
    with pytest.raises(ValueError, match="token_header"):
        OpenRouterChatCompletionsAdapter(**base, token_header="Content-Type")
    with pytest.raises(ValueError, match="bearer_value requires token_header"):
        OpenRouterChatCompletionsAdapter(**base, bearer_value="orphan-marker")
    with pytest.raises(ValueError, match="bearer_value"):
        OpenRouterChatCompletionsAdapter(**base, token_header="X-Gateway-Token", bearer_value="  ")
    with pytest.raises(ValueError, match="extra_headers"):
        OpenRouterChatCompletionsAdapter(**base, extra_headers={"X-Gateway-Route": ""})
    with pytest.raises(ValueError, match="extra_headers"):
        OpenRouterChatCompletionsAdapter(**base, extra_headers={"Authorization": "shadow"})
    with pytest.raises(ValueError, match="extra_headers"):
        OpenRouterChatCompletionsAdapter(**base, token_header="X-Gateway-Token", extra_headers={"x-gateway-token": "shadow"})


def test_openai_adapter_exposes_safe_transport_reason():
    def transport(endpoint, headers, payload, timeout):
        raise OSError("network unreachable")

    adapter = OpenAIResponsesAdapter(model="test-model", endpoint="https://api.openai.com/v1/responses", transport=transport)
    with pytest.raises(RuntimeAdapterTransportError, match=r"PROVIDER_CONNECTION_FAILED host=api\.openai\.com reason=network unreachable"):
        adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-3"})


def test_anthropic_adapter_normalizes_messages_response_without_credential():
    def transport(endpoint, headers, payload, timeout):
        assert endpoint.endswith("/messages")
        assert headers["x-api-key"] == "synthetic-secret"
        assert headers["anthropic-version"] == "2023-06-01"
        body = json.loads(payload)
        assert body["model"] == "claude-test"
        assert body["messages"][0]["role"] == "user"
        return 200, json.dumps({"id": "msg-1", "content": [{"type": "text", "text": "ECP-CONFORMANCE-OK"}]}).encode()

    adapter = AnthropicMessagesAdapter(model="claude-test", endpoint="https://provider.invalid/v1/messages", transport=transport)
    result = adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-anthropic"})
    latency_ms = result.pop("latency_ms")
    assert isinstance(latency_ms, int) and latency_ms >= 0
    assert result == {
        "provider_status": "RECEIVED",
        "response_id": "msg-1",
        "model": "claude-test",
        "output_text": "ECP-CONFORMANCE-OK",
        "request_id": "request-anthropic",
        "transport_kind": "http",
        "endpoint": "https://provider.invalid/v1/messages",
        "http_status": 200,
    }
    assert "synthetic-secret" not in json.dumps(result)


def test_anthropic_adapter_maps_provider_failures_safely():
    def transport(endpoint, headers, payload, timeout):
        return 401, b"provider body may contain sensitive details"

    adapter = AnthropicMessagesAdapter(model="claude-test", endpoint="https://provider.invalid/v1/messages", transport=transport)
    with pytest.raises(RuntimeAdapterTransportError, match="PROVIDER_AUTHENTICATION_FAILED") as exc_info:
        adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-anthropic-401"})
    assert "sensitive details" not in str(exc_info.value)
    assert "synthetic-secret" not in str(exc_info.value)


def test_anthropic_adapter_rejects_malformed_responses():
    def transport(endpoint, headers, payload, timeout):
        return 200, json.dumps({"content": [{"type": "tool_use", "id": "x"}]}).encode()

    adapter = AnthropicMessagesAdapter(model="claude-test", endpoint="https://provider.invalid/v1/messages", transport=transport)
    with pytest.raises(RuntimeAdapterTransportError, match="MALFORMED_PROVIDER_RESPONSE"):
        adapter.execute(SecretLease("synthetic-secret", {}), {"request_id": "request-anthropic-malformed"})


def test_anthropic_conformance_factory_reads_configuration():
    adapter = anthropic_conformance_adapter(model="claude-factory-test", endpoint="https://provider.invalid/custom")
    assert adapter.endpoint == "https://provider.invalid/custom/messages"
    assert adapter.model == "claude-factory-test"


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
