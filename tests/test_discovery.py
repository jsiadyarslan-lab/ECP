"""Synthetic tests for the universal provider & model discovery fabric.

All tests are offline: the probe transport is always an injected fake. No
real credential and no network access is ever required (owner order §8).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from ecp.credentials import SecretLease
from ecp.discovery import (
    DiscoveryDescriptor,
    DiscoveryRegistry,
    DiscoveryReport,
    DiscoveredModel,
    InvalidCustomEndpoint,
    InvalidDiscoveryDescriptor,
    ProviderDiscoveryService,
    UnknownDiscoveryDescriptor,
    builtin_discovery_registry,
    validate_custom_base_url,
    STATUS_DISCOVERED,
    STATUS_DISCOVERY_FAILED,
)
from ecp.validate import validate_document

SECRET = "synthetic-discovery-lease-DO-NOT-LEAK"
LEASE = SecretLease(SECRET, {"request_id": "discovery-test"})

OPENAI_BODY = {
    "data": [
        {"id": "gpt-4o-mini", "object": "model", "owned_by": "system"},
        {"id": "gpt-4o", "object": "model", "owned_by": "openai"},
        {"id": "not-a-model", "object": "other"},
    ]
}
ANTHROPIC_BODY = {
    "data": [
        {"id": "claude-3-5-haiku-latest", "display_name": "Claude 3.5 Haiku"},
        {"id": "claude-3-7-sonnet-latest", "display_name": "Claude 3.7 Sonnet"},
    ]
}
GEMINI_BODY = {
    "models": [
        {
            "name": "models/gemini-2.0-flash",
            "displayName": "Gemini 2.0 Flash",
            "supportedGenerationMethods": ["generateContent", "countTokens"],
        },
        {
            "name": "models/text-embedding-004",
            "displayName": "Text Embedding",
            "supportedGenerationMethods": ["embedContent"],
        },
    ]
}


class FakeTransport:
    """Recording probe transport: routes map URL -> (status, body) | Exception."""

    def __init__(self, routes=None):
        self.routes = dict(routes or {})
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, dict(headers)))
        route = self.routes.get(url)
        if route is None:
            return 404, b'{"error":{"message":"no such endpoint"}}'
        if isinstance(route, Exception):
            raise route
        return route

    def bodies(self):
        return json.dumps(
            {"calls": [call[0] for call in self.calls], "headers": [call[1] for call in self.calls]}
        )


def fixed_clock():
    moment = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    return lambda: moment


def service(transport, registry=None):
    return ProviderDiscoveryService(
        registry or builtin_discovery_registry(),
        transport=transport,
        clock=fixed_clock(),
    )


# ---------------------------------------------------------------------------
# Descriptor registry integrity
# ---------------------------------------------------------------------------


def test_builtin_registry_loads_one_entry_per_dialect():
    registry = builtin_discovery_registry()
    ids = [d.discovery_id for d in registry.descriptors()]
    assert len(registry) == 6
    assert len(set(ids)) == 6
    kinds = {d.adapter_kind for d in registry.descriptors()}
    assert kinds == {"openai-responses", "gemini-generate-content", "anthropic-messages", "openrouter-chat-completions"}


def test_builtin_provider_and_adapter_documents_are_schema_valid():
    for descriptor in builtin_discovery_registry().descriptors():
        assert validate_document(dict(descriptor.provider_document), "provider") == []
        assert validate_document(dict(descriptor.adapter_document), "adapter") == []


def test_registry_rejects_duplicate_and_non_descriptors():
    registry = builtin_discovery_registry()
    descriptor = registry.descriptors()[0]
    with pytest.raises(InvalidDiscoveryDescriptor):
        registry.register(descriptor)
    with pytest.raises(InvalidDiscoveryDescriptor):
        registry.register("not-a-descriptor")


def test_descriptor_validation_rejects_non_http_base_urls():
    with pytest.raises(InvalidDiscoveryDescriptor):
        DiscoveryDescriptor(
            discovery_id="ECP-DISCOVERY-BAD",
            display_name="Bad",
            protocol="p",
            adapter_kind="k",
            endpoint_template="{base}/x",
            base_urls=("ftp://only-ftp.example",),
            models_path="/models",
            auth={"style": "bearer"},
            response_shape="openai-models",
            provider_document={},
            adapter_document={},
        )


def test_descriptor_template_consistency_is_enforced():
    base = dict(
        discovery_id="ECP-DISCOVERY-T",
        display_name="T",
        protocol="p",
        adapter_kind="k",
        endpoint_template="{base}/x",
        base_urls=("https://t.example",),
        models_path="/models",
        auth={"style": "bearer"},
        response_shape="openai-models",
        provider_document={"provider_id": "ECP-PROVIDER-T", "interfaces": ["i"]},
        adapter_document={},
    )
    with pytest.raises(InvalidDiscoveryDescriptor):
        DiscoveryDescriptor(**{**base, "endpoint_template": "{base}/models/{model}", "model_in_path": False})
    with pytest.raises(InvalidDiscoveryDescriptor):
        DiscoveryDescriptor(**{**base, "model_in_path": True})
    with pytest.raises(InvalidDiscoveryDescriptor):
        DiscoveryDescriptor(**{**base, "auth": {"style": "cookie"}})
    with pytest.raises(InvalidDiscoveryDescriptor):
        DiscoveryDescriptor(**{**base, "response_shape": "xml"})


# ---------------------------------------------------------------------------
# Discovery per adapter/descriptor (owner order §8: "Discovery per Adapter")
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "discovery_id,url,body,expected_provider,expected_kind,expected_protocol",
    [
        ("ECP-DISCOVERY-OPENAI-RESPONSES", "https://api.openai.com/v1/models", OPENAI_BODY, "ECP-PROVIDER-OPENAI", "openai-responses", "openai-responses"),
        ("ECP-DISCOVERY-ANTHROPIC-MESSAGES", "https://api.anthropic.com/v1/models", ANTHROPIC_BODY, "ECP-PROVIDER-ANTHROPIC", "anthropic-messages", "anthropic-messages"),
        ("ECP-DISCOVERY-GEMINI-GENERATE-CONTENT", "https://generativelanguage.googleapis.com/v1beta/models", GEMINI_BODY, "ECP-PROVIDER-GEMINI", "gemini-generate-content", "gemini-generate-content"),
        ("ECP-DISCOVERY-GROQ-CHAT-COMPLETIONS", "https://api.groq.com/openai/v1/models", OPENAI_BODY, "ECP-PROVIDER-GROQ", "openrouter-chat-completions", "openai-chat-completions"),
        ("ECP-DISCOVERY-OPENROUTER-CHAT-COMPLETIONS", "https://openrouter.ai/api/v1/models", OPENAI_BODY, "ECP-PROVIDER-OPENROUTER", "openrouter-chat-completions", "openai-chat-completions"),
    ],
)
def test_discovery_identifies_each_builtin_dialect(discovery_id, url, body, expected_provider, expected_kind, expected_protocol):
    transport = FakeTransport({url: (200, json.dumps(body).encode())})
    report = service(transport).discover(LEASE, provider_hint=discovery_id)
    assert report.status == STATUS_DISCOVERED
    assert report.provider_id == expected_provider
    assert report.adapter_kind == expected_kind
    assert report.protocol == expected_protocol
    assert report.identification == "IDENTIFIED"
    assert report.matched_base_url == url.rsplit("/models", 1)[0]
    assert report.models
    assert SECRET not in json.dumps(report.to_document())


def test_gemini_discovery_filters_non_generative_models_and_uses_display_names():
    transport = FakeTransport({"https://generativelanguage.googleapis.com/v1beta/models": (200, json.dumps(GEMINI_BODY).encode())})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-GEMINI-GENERATE-CONTENT")
    identifiers = [m.model_identifier for m in report.models]
    assert identifiers == ["gemini-2.0-flash"]
    model = report.models[0]
    assert model.display_name == "Gemini 2.0 Flash"
    assert "generateContent" in model.capabilities


def test_models_are_sorted_and_provider_neutral_documents_are_complete():
    transport = FakeTransport({"https://api.openai.com/v1/models": (200, json.dumps(OPENAI_BODY).encode())})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-OPENAI-RESPONSES")
    identifiers = [m.model_identifier for m in report.models]
    assert identifiers == ["gpt-4o", "gpt-4o-mini"]
    document = report.models[0].to_document(provider_id=report.provider_id, adapter_kind=report.adapter_kind, protocol=report.protocol)
    for key in ("provider", "model_identifier", "display_name", "capabilities", "availability", "discovered_at", "adapter_kind", "protocol"):
        assert key in document
    assert document["discovered_at"] == "2026-09-12T12:00:00Z"


# ---------------------------------------------------------------------------
# Probe auth styles and network boundary recording
# ---------------------------------------------------------------------------


def test_bearer_probe_headers_carry_the_lease_only_where_expected():
    transport = FakeTransport({"https://api.openai.com/v1/models": (200, json.dumps(OPENAI_BODY).encode())})
    service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-OPENAI-RESPONSES")
    (url, headers), = transport.calls
    assert url == "https://api.openai.com/v1/models"
    assert headers["Authorization"] == f"Bearer {SECRET}"
    assert headers["Accept"] == "application/json"


def test_header_style_probe_headers_carry_lease_and_static_version_header():
    transport = FakeTransport({"https://api.anthropic.com/v1/models": (200, json.dumps(ANTHROPIC_BODY).encode())})
    service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-ANTHROPIC-MESSAGES")
    (url, headers), = transport.calls
    assert headers["x-api-key"] == SECRET
    assert headers["anthropic-version"] == "2023-06-01"
    assert "Authorization" not in headers


def test_only_the_probed_provider_endpoints_are_contacted():
    # No hint and no custom endpoint probes EVERY builtin dialect once.
    routes = {
        "https://api.openai.com/v1/models": (200, json.dumps(OPENAI_BODY).encode()),
        "https://api.anthropic.com/v1/models": (401, b'{"error":"auth"}'),
        "https://api.groq.com/openai/v1/models": (404, b"{}"),
        "https://generativelanguage.googleapis.com/v1beta/models": (403, b"{}"),
        "https://openrouter.ai/api/v1/models": (200, json.dumps(OPENAI_BODY).encode()),
    }
    transport = FakeTransport(routes)
    report = service(transport).discover(LEASE)
    # Registry order is alphabetical: the anthropic probe runs first and is
    # rejected, then the gemini probe, then groq, then openai identifies first.
    assert report.status == STATUS_DISCOVERED
    assert report.provider_id == "ECP-PROVIDER-OPENAI"
    probed = {call[0] for call in transport.calls}
    assert probed  # all calls went to fixed provider endpoints only
    for url in probed:
        assert url.startswith("https://") and url.endswith("/models")
    # the openrouter probe never happened: identification stopped at openai
    assert "https://openrouter.ai/api/v1/models" not in probed


# ---------------------------------------------------------------------------
# Honest failure states (owner order §2 — never guess)
# ---------------------------------------------------------------------------


def test_unknown_provider_is_reported_as_unknown_not_guessed():
    transport = FakeTransport()  # every probe 404s
    report = service(transport).discover(LEASE)
    assert report.status == STATUS_DISCOVERY_FAILED
    assert report.identification == "UNKNOWN"
    assert report.provider_id is None
    assert report.models == ()
    document = report.to_document()
    assert document["provider"]["identification"] == "UNKNOWN"
    assert document["models"] == []
    outcomes = {probe.outcome for probe in report.probes}
    assert outcomes == {"NOT_SUPPORTED"}


def test_invalid_credential_is_credential_rejected():
    routes = {url: (401, b'{"error":"invalid api key"}') for url in (
        "https://api.openai.com/v1/models",
        "https://api.anthropic.com/v1/models",
        "https://api.groq.com/openai/v1/models",
        "https://generativelanguage.googleapis.com/v1beta/models",
        "https://openrouter.ai/api/v1/models",
    )}
    transport = FakeTransport(routes)
    report = service(transport).discover(LEASE)
    assert report.status == STATUS_DISCOVERY_FAILED
    assert report.identification == "UNKNOWN"
    assert all(probe.outcome == "CREDENTIAL_REJECTED" for probe in report.probes)
    assert SECRET not in json.dumps(report.to_document())


def test_provider_unavailable_is_unreachable():
    transport = FakeTransport({"https://api.openai.com/v1/models": OSError("connection refused")})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-OPENAI-RESPONSES")
    assert report.status == STATUS_DISCOVERY_FAILED
    assert report.probes[0].outcome == "UNREACHABLE"
    assert "api.openai.com" in report.probes[0].detail
    assert SECRET not in report.probes[0].detail


def test_malformed_and_empty_responses_are_not_matches():
    transport = FakeTransport({"https://api.openai.com/v1/models": (200, b"not json at all")})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-OPENAI-RESPONSES")
    assert report.status == STATUS_DISCOVERY_FAILED
    assert report.probes[0].outcome == "MALFORMED"
    transport = FakeTransport({"https://api.openai.com/v1/models": (200, b'{"data": []}')})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-OPENAI-RESPONSES")
    assert report.probes[0].outcome == "NO_MODELS"
    transport = FakeTransport({"https://api.openai.com/v1/models": (200, b'{"unexpected": true}')})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-OPENAI-RESPONSES")
    assert report.probes[0].outcome == "MALFORMED"


def test_rate_limited_probe_is_inconclusive_not_identified():
    transport = FakeTransport({"https://api.openai.com/v1/models": (429, b'{"error":"rate limited"}')})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-OPENAI-RESPONSES")
    assert report.status == STATUS_DISCOVERY_FAILED
    assert report.probes[0].outcome == "RATE_LIMITED"


def test_wrong_shape_body_is_not_a_match_for_the_hinted_dialect():
    # The gemini shape ("models" list) does not satisfy the openai-models
    # dialect ("data" list): the probe is MALFORMED, never a false match.
    transport = FakeTransport({"https://api.openai.com/v1/models": (200, json.dumps(GEMINI_BODY).encode())})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-OPENAI-RESPONSES")
    assert report.status == STATUS_DISCOVERY_FAILED
    assert report.probes[0].outcome == "MALFORMED"
    transport = FakeTransport({"https://generativelanguage.googleapis.com/v1beta/models": (200, json.dumps(OPENAI_BODY).encode())})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-GEMINI-GENERATE-CONTENT")
    assert report.status == STATUS_DISCOVERY_FAILED
    assert report.probes[0].outcome == "MALFORMED"


# ---------------------------------------------------------------------------
# Hints, custom endpoints and validation
# ---------------------------------------------------------------------------


def test_unknown_hint_is_a_deterministic_error():
    transport = FakeTransport()
    with pytest.raises(UnknownDiscoveryDescriptor):
        service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-NOPE")


def test_custom_endpoint_descriptor_identifies_openai_compatible_dialects():
    transport = FakeTransport({"http://127.0.0.1:8000/v1/models": (200, json.dumps(OPENAI_BODY).encode())})
    report = service(transport).discover(LEASE, custom_base_url="http://127.0.0.1:8000/v1")
    assert report.status == STATUS_DISCOVERED
    assert report.provider_id == "ECP-PROVIDER-CUSTOM-COMPATIBLE"
    assert report.adapter_kind == "openrouter-chat-completions"
    assert report.matched_base_url == "http://127.0.0.1:8000/v1"
    descriptor = service(transport).registry.get("ECP-DISCOVERY-CUSTOM-OPENAI-COMPATIBLE")
    assert descriptor.execution_endpoint("http://127.0.0.1:8000/v1", "gpt-4o") == "http://127.0.0.1:8000/v1/chat/completions"


def test_hint_with_custom_endpoint_uses_the_hinted_dialect_at_that_endpoint():
    transport = FakeTransport({"https://gateway.internal/v1/models": (200, json.dumps(GEMINI_BODY).encode())})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-GEMINI-GENERATE-CONTENT", custom_base_url="https://gateway.internal/v1")
    assert report.status == STATUS_DISCOVERED
    assert report.provider_id == "ECP-PROVIDER-GEMINI"
    descriptor = service(transport).registry.get(report.discovery_id)
    endpoint = descriptor.execution_endpoint(report.matched_base_url, "gemini-2.0-flash")
    assert endpoint == "https://gateway.internal/v1/models/gemini-2.0-flash:generateContent"


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "ftp://files.example/v1",
        "https://user:pass@provider.example/v1",
        "https://provider.example/v1?token=x",
        "https://provider.example/v1#frag",
        "http://169.254.169.254/v1",
        "http://metadata.google.internal/v1",
        "",
    ],
)
def test_invalid_custom_endpoints_are_rejected(url):
    with pytest.raises(InvalidCustomEndpoint):
        validate_custom_base_url(url)


@pytest.mark.parametrize(
    "url",
    ["https://provider.example/v1", "http://127.0.0.1:11434/v1", "http://10.0.0.5:8000"],
)
def test_valid_custom_endpoints_include_loopback_and_private_hosts(url):
    assert validate_custom_base_url(url) == url


def test_custom_endpoint_with_trailing_slash_is_normalized():
    transport = FakeTransport({"http://127.0.0.1:9000/v1/models": (200, json.dumps(OPENAI_BODY).encode())})
    report = service(transport).discover(LEASE, custom_base_url="http://127.0.0.1:9000/v1/")
    assert report.status == STATUS_DISCOVERED


# ---------------------------------------------------------------------------
# Secret discipline and reporting limits
# ---------------------------------------------------------------------------


def test_report_documents_never_contain_the_credential_value():
    transport = FakeTransport({"https://api.openai.com/v1/models": (200, json.dumps(OPENAI_BODY).encode())})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-OPENAI-RESPONSES")
    blob = json.dumps(report.to_document()) + json.dumps([p.to_document() for p in report.probes])
    assert SECRET not in blob
    assert "Bearer " not in blob


def test_model_list_is_capped_with_an_honest_truncation_flag():
    big = {"data": [{"id": f"model-{i:04d}"} for i in range(300)]}
    transport = FakeTransport({"https://api.openai.com/v1/models": (200, json.dumps(big).encode())})
    report = service(transport).discover(LEASE, provider_hint="ECP-DISCOVERY-OPENAI-RESPONSES")
    assert report.total_models == 300
    assert report.models_truncated is True
    assert len(report.models) == 250
    document = report.to_document()
    assert document["models_truncated"] is True and document["total_models"] == 300


def test_discovered_model_validation_rejects_whitespace_identifiers():
    with pytest.raises(ValueError):
        DiscoveredModel(model_identifier="bad model", display_name="x")
    with pytest.raises(ValueError):
        DiscoveredModel(model_identifier="ok", display_name="")


def test_path_safe_model_identifiers_are_enforced_for_url_path_protocols():
    descriptor = builtin_discovery_registry().get("ECP-DISCOVERY-GEMINI-GENERATE-CONTENT")
    with pytest.raises(Exception):
        descriptor.execution_endpoint("https://x.example/v1beta", "../../admin")
    assert descriptor.execution_endpoint("https://x.example/v1beta", "gemini-2.0-flash").endswith(":generateContent")


def test_descriptors_view_is_registry_driven_and_secret_free():
    view = builtin_discovery_registry().view()
    assert len(view) == 6
    for entry in view:
        assert set(entry) == {"discovery_id", "display_name", "protocol", "adapter_kind", "requires_base_url", "fixed_endpoints"}
    custom = [entry for entry in view if entry["requires_base_url"]][0]
    assert custom["fixed_endpoints"] == []


def test_discovery_report_defaults_are_failure_shaped():
    report = DiscoveryReport(status=STATUS_DISCOVERY_FAILED, discovered_at="2026-09-12T12:00:00Z", probes=())
    document = report.to_document()
    assert document["status"] == STATUS_DISCOVERY_FAILED
    assert document["provider"]["identification"] == "UNKNOWN"
    assert document["adapter"] == {}
    assert document["models"] == []
