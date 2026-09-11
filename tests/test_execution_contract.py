"""Universal Experiment Execution Contract v1 — invariant battery.

Covers the owner order's invariants A–J and the sixteen contract-test
categories (request construction, internal resolution, adapter resolution,
model configuration substitution, normalized result, provider metadata
normalization, client-boundary enforcement, ground-truth isolation,
prompt/case authority, Evidence compatibility, Audit compatibility,
adapter/provider separation, no adapter creation per model, and mock
compatibility for OpenAI / OpenRouter / Gemini).

Everything here is OFFLINE: mock adapters, local fixtures, fake responses.
No network, no real provider, no credential.
"""

import json
from dataclasses import fields as dataclass_fields

import pytest

from ecp.console import (
    AuthorizedEvaluation,
    AuthorizedTest,
    ConsoleError,
    ExecutionAuthorizationError,
    GatewayConfig,
    LocalGateway,
    ProviderAdapter,
)
from ecp.credential_binding import AuthorizationGrant, CredentialBinding
from ecp.credentials import CredentialGateway, CredentialIdentity
from ecp.execution_contract import (
    ClientExecutionIntent,
    ContractViolation,
    ExecutionContractResolver,
    ExecutionNotAuthorizedError,
    ExperimentIdentity,
    RegisteredCaseArtifact,
    ResolvedUniversalExecutionRequest,
    UniversalExecutionResult,
    UnknownCredentialError,
    UnknownEvaluationError,
    UnknownTestError,
)
from ecp.hashing import hash_document
from ecp.runtime_adapters import (
    GeminiGenerateContentAdapter,
    OpenAIResponsesAdapter,
    OpenRouterChatCompletionsAdapter,
    RuntimeAdapterRegistry,
)


# ---------------------------------------------------------------------------
# Fixtures — synthetic, offline
# ---------------------------------------------------------------------------

INTENT = ClientExecutionIntent(
    evaluation_id="ECP-EVAL-CONTRACT",
    test_id="test-contract-1",
    system_id="ECP-SYSTEM-CONTRACT",
    credential_ref="cred-contract",
    request_id="request-contract-1",
)

CASE_PROMPT = "Registered case prompt: the ember is above the stone."

CASE = RegisteredCaseArtifact.for_prompt("ECP-CASE-CONTRACT-1", CASE_PROMPT)


class RecordingAdapter(ProviderAdapter):
    """A mock provider adapter that records what it was asked to execute."""

    provider = "synthetic-provider"
    adapter_id = "synthetic-adapter"

    def __init__(self, *, model="model-alpha", payload=None):
        self.model = model
        self.calls = []

    def execute(self, lease, request):
        self.calls.append(dict(request))
        return {
            "provider_status": "RECEIVED",
            "response_id": "resp-1",
            "model": self.model,
            "output_text": "ECP-CONFORMANCE-OK",
            "request_id": request["request_id"],
        }


def build_evaluation(*, with_authorization=True, with_case=False, adapter_id="synthetic-adapter"):
    identity = CredentialIdentity("cred-contract", "synthetic-provider", "test", frozenset({"execute"}))
    binding = CredentialBinding(
        "ECP-BIND-CONTRACT", "ECP-REQ-CONTRACT", "ECP-SYSTEM-CONTRACT",
        "synthetic-provider", "test-interface", "execute", "cred-contract",
        frozenset({"execute"}),
    )
    grant = AuthorizationGrant(
        "ECP-AUTH-CONTRACT", "ECP-BIND-CONTRACT", "ECP-SYSTEM-CONTRACT",
        "execute", frozenset({"execute"}), "2099-01-01T00:00:00Z",
    )
    return AuthorizedEvaluation(
        "ECP-EVAL-CONTRACT", "ECP-SYSTEM-CONTRACT", "synthetic-provider",
        adapter_id, identity,
        (AuthorizedTest("test-contract-1", "Contract test", "execute"),),
        binding if with_authorization else None,
        grant if with_authorization else None,
    )


def build_resolver(adapter=None, *, with_case=False, with_authorization=True, adapter_id="synthetic-adapter"):
    adapter = adapter or RecordingAdapter()
    registry = RuntimeAdapterRegistry({adapter_id: adapter})
    cases = {"test-contract-1": CASE} if with_case else None
    resolver = ExecutionContractResolver(
        {"ECP-EVAL-CONTRACT": build_evaluation(with_authorization=with_authorization, adapter_id=adapter_id)},
        cases,
        registry,
        protocol_version="0.7.0",
    )
    return resolver, adapter, registry


def build_gateway(tmp_path, *, adapter=None, with_case=False, adapter_id="synthetic-adapter"):
    adapter = adapter or RecordingAdapter()
    identity = CredentialIdentity("cred-contract", "synthetic-provider", "test", frozenset({"execute"}))
    credentials, _store = CredentialGateway.for_testing({identity.credential_id: identity})
    credentials.provision_for_testing("cred-contract", "synthetic-secret-value")
    cases = {"test-contract-1": CASE} if with_case else None
    gateway = LocalGateway(
        GatewayConfig(frozenset({"http://127.0.0.1:8766"}), artifact_root=tmp_path),
        {"ECP-EVAL-CONTRACT": build_evaluation(adapter_id=adapter_id)},
        credentials,
        RuntimeAdapterRegistry({adapter_id: adapter}),
        cases=cases,
    )
    return gateway, adapter


def mock_transport(status, body):
    def transport(endpoint, headers, payload, timeout):
        return status, json.dumps(body).encode("utf-8")

    return transport


# ---------------------------------------------------------------------------
# 1–3. Client boundary / request construction (Invariant C)
# ---------------------------------------------------------------------------


def test_intent_accepts_exactly_the_authorized_identifiers():
    intent = ClientExecutionIntent.from_client_payload(
        {
            "evaluation_id": "ECP-EVAL-CONTRACT",
            "test_id": "test-contract-1",
            "system_id": "ECP-SYSTEM-CONTRACT",
            "credential_ref": "cred-contract",
            "request_id": "request-contract-1",
        }
    )
    assert intent == INTENT


@pytest.mark.parametrize(
    "payload",
    [
        {"shell_command": "whoami"},
        {"prompt": "arbitrary client prompt"},
        {"ground_truth": "yes"},
        {"model_endpoint": "https://evil.example/v1"},
        {"model": "attacker-model"},
        {"expected_class": "DERIVABLE"},
        {"score": 1},
        {"authorization": "Bearer attacker"},
        dict(zip(
            ("evaluation_id", "test_id", "system_id", "credential_ref", "request_id", "prompt"),
            ("ECP-EVAL-CONTRACT", "test-contract-1", "ECP-SYSTEM-CONTRACT", "cred-contract", "r-1", "injected"),
        )),
    ],
)
def test_intent_rejects_any_non_identifier_field(payload):
    with pytest.raises(ContractViolation):
        ClientExecutionIntent.from_client_payload(payload)


def test_intent_rejects_non_string_and_empty_identifiers():
    base = dict(zip(
        ("evaluation_id", "test_id", "system_id", "credential_ref", "request_id"),
        ("ECP-EVAL-CONTRACT", "test-contract-1", "ECP-SYSTEM-CONTRACT", "cred-contract", "r-1"),
    ))
    with pytest.raises(ContractViolation):
        ClientExecutionIntent.from_client_payload({**base, "request_id": 42})
    with pytest.raises(ContractViolation):
        ClientExecutionIntent.from_client_payload({**base, "request_id": "   "})
    with pytest.raises(ContractViolation):
        ClientExecutionIntent.from_client_payload([1, 2, 3])


# ---------------------------------------------------------------------------
# Internal resolution (categories 2/3; §5)
# ---------------------------------------------------------------------------


def test_resolution_requires_registered_evaluation_system_credential_and_test():
    resolver, _, _ = build_resolver()
    resolved = resolver.resolve(INTENT)
    assert isinstance(resolved, ResolvedUniversalExecutionRequest)
    assert resolved.evaluation_id == "ECP-EVAL-CONTRACT"
    assert resolved.test_scope == "execute"
    assert resolved.binding_id == "ECP-BIND-CONTRACT"
    assert resolved.grant_id == "ECP-AUTH-CONTRACT"
    with pytest.raises(UnknownEvaluationError):
        resolver.resolve(
            ClientExecutionIntent("ECP-EVAL-NOPE", INTENT.test_id, INTENT.system_id, INTENT.credential_ref, "r-2")
        )
    with pytest.raises(UnknownEvaluationError):
        resolver.resolve(
            ClientExecutionIntent(INTENT.evaluation_id, INTENT.test_id, "ECP-SYSTEM-NOPE", INTENT.credential_ref, "r-3")
        )
    with pytest.raises(UnknownCredentialError):
        resolver.resolve(
            ClientExecutionIntent(INTENT.evaluation_id, INTENT.test_id, INTENT.system_id, "cred-nope", "r-4")
        )
    with pytest.raises(UnknownTestError):
        resolver.resolve(
            ClientExecutionIntent(INTENT.evaluation_id, "test-nope", INTENT.system_id, INTENT.credential_ref, "r-5")
        )


def test_resolution_reports_missing_authorization_as_execution_not_authorized():
    resolver, _, _ = build_resolver(with_authorization=False)
    with pytest.raises(ExecutionNotAuthorizedError):
        resolver.resolve(INTENT)


def test_resolved_request_carries_registered_identity_not_client_values():
    resolver, adapter, _ = build_resolver()
    resolved = resolver.resolve(INTENT)
    experiment = resolved.experiment
    assert isinstance(experiment, ExperimentIdentity)
    assert experiment.model_identifier == "model-alpha"  # from the registered runtime adapter
    assert experiment.adapter_id == "synthetic-adapter"
    assert experiment.provider_id == "synthetic-provider"
    assert experiment.protocol_version == "0.7.0"
    assert experiment.system_id == INTENT.system_id
    assert experiment.configuration_hash == hash_document({
        "adapter_id": "synthetic-adapter",
        "provider_id": "synthetic-provider",
        "model_identifier": "model-alpha",
        "endpoint_host": None,
    })
    # the client sent none of these; they are all registration-derived
    transport = resolved.transport_request()
    assert transport["model_identifier"] == "model-alpha"
    assert transport["adapter_id"] == "synthetic-adapter"
    assert transport["provider_id"] == "synthetic-provider"
    assert transport["protocol_version"] == "0.7.0"


def test_resolver_is_pure_and_deterministic():
    resolver, _, _ = build_resolver()
    first = resolver.resolve(INTENT)
    second = resolver.resolve(INTENT)
    assert first == second
    assert first.experiment.identity_hash() == second.experiment.identity_hash()


# ---------------------------------------------------------------------------
# Prompt / case authority (Invariant D; category 9)
# ---------------------------------------------------------------------------


def test_prompt_authority_comes_from_registered_case_artifact():
    resolver, adapter, _ = build_resolver(with_case=True)
    resolved = resolver.resolve(INTENT)
    assert resolved.prompt == CASE_PROMPT
    assert resolved.prompt_reference == f"protected:ECP-CASE-CONTRACT-1:{CASE.prompt_hash}"
    assert resolved.experiment.case_id == "ECP-CASE-CONTRACT-1"
    assert resolved.experiment.case_artifact_hash == CASE.case_artifact_hash
    assert resolved.experiment.prompt_hash == CASE.prompt_hash
    transport = resolved.transport_request()
    assert transport["prompt"] == CASE_PROMPT
    assert transport["prompt_hash"] == CASE.prompt_hash
    assert transport["case_id"] == "ECP-CASE-CONTRACT-1"


def test_case_artifact_hash_is_pinned_and_prompt_hash_is_verifiable():
    assert CASE.prompt_hash == hash_document({"prompt": CASE_PROMPT})
    assert CASE.case_artifact_hash == hash_document({"case_id": CASE.case_id, "prompt_hash": CASE.prompt_hash})
    with pytest.raises(ContractViolation):
        RegisteredCaseArtifact(
            CASE.case_id, CASE.case_artifact_hash, CASE_PROMPT + "tampered", CASE.prompt_hash, CASE.protected
        )


def test_without_registered_case_artifact_there_is_no_prompt():
    resolver, adapter, _ = build_resolver(with_case=False)
    resolved = resolver.resolve(INTENT)
    assert resolved.prompt is None
    assert resolved.prompt_reference is None
    assert resolved.experiment.case_id is None
    assert "prompt" not in resolved.transport_request()


# ---------------------------------------------------------------------------
# Ground-truth isolation (Invariant E; category 8)
# ---------------------------------------------------------------------------


def test_contract_types_structurally_carry_no_ground_truth_or_scoring():
    forbidden = {"ground_truth", "ground_truth_class", "expected_class", "expected_property", "score",
                 "scientific_score", "adjudication", "correct_answer", "answer_key"}
    for cls in (ClientExecutionIntent, ResolvedUniversalExecutionRequest, UniversalExecutionResult, ExperimentIdentity):
        names = {f.name for f in dataclass_fields(cls)}
        assert not (names & forbidden), cls.__name__


def test_universal_result_rejects_scientific_keys_loudly():
    for scientific in (
        {"ground_truth": "yes"},
        {"expected_class": "DERIVABLE"},
        {"score": 0.9},
        {"adjudication": "PASS"},
        {"output_text": "ok", "ground_truth": "yes"},
    ):
        with pytest.raises(ContractViolation):
            UniversalExecutionResult.from_provider_payload(scientific, request_id="r-1")


def test_universal_result_drops_secret_bearing_keys():
    unified = UniversalExecutionResult.from_provider_payload(
        {"provider_status": "RECEIVED", "output_text": "ok", "secret": "leak", "api_key": "leak",
         "request_id": "r-1"},
        request_id="r-1",
    )
    record = unified.to_record_dict()
    assert "secret" not in record and "api_key" not in record


# ---------------------------------------------------------------------------
# Normalized result + provider metadata normalization (categories 5/6; Invariants F/I)
# ---------------------------------------------------------------------------


def test_universal_result_normalizes_provider_payload_to_transport_facts():
    unified = UniversalExecutionResult.from_provider_payload(
        {"provider_status": "RECEIVED", "response_id": "resp-9", "model": "model-x",
         "output_text": "provider said", "request_id": "r-1", "extra_flag": True},
        request_id="r-1",
    )
    assert unified.transport_status == "RECEIVED"
    assert unified.provider_status == "RECEIVED"
    assert unified.normalized_output == "provider said"
    assert unified.response_metadata == {"response_id": "resp-9", "model": "model-x"}
    assert unified.execution_metadata == {"request_id": "r-1"}
    assert unified.provider_extras == {"extra_flag": True}
    record = unified.to_record_dict()
    assert record["normalized_output"] == "provider said"
    assert record["response_id"] == "resp-9"
    assert record["request_id"] == "r-1"
    # provider transport structures never leak into the universal record
    assert "output" not in record and "choices" not in record and "candidates" not in record


def test_universal_result_rejects_non_scalar_extras_and_bad_types():
    with pytest.raises(ContractViolation):
        UniversalExecutionResult.from_provider_payload({"provider_status": 5}, request_id="r-1")
    with pytest.raises(ContractViolation):
        UniversalExecutionResult.from_provider_payload({"output_text": 5}, request_id="r-1")
    unified = UniversalExecutionResult.from_provider_payload(
        {"nested": {"a": 1}}, request_id="r-1"
    )
    assert "nested" not in unified.to_record_dict()


# ---------------------------------------------------------------------------
# Adapter / model separation (Invariants A/B/I; categories 12/13)
# ---------------------------------------------------------------------------


def test_model_configuration_substitution_requires_no_new_adapter():
    # the SAME registered adapter instance, three different model identifiers
    resolver, adapter, registry = build_resolver()
    assert len(registry) == 1
    base = resolver.resolve(INTENT)
    adapter.model = "model-beta"
    beta = resolver.resolve(INTENT)
    adapter.model = "model-gamma"
    gamma = resolver.resolve(INTENT)
    assert len(registry) == 1  # no adapter was created or re-registered
    assert base.adapter_id == beta.adapter_id == gamma.adapter_id == "synthetic-adapter"
    assert {base.model_identifier, beta.model_identifier, gamma.model_identifier} == {
        "model-alpha", "model-beta", "model-gamma"
    }
    # only the model identifier and the configuration hash move
    assert base.experiment.identity_document() != beta.experiment.identity_document()
    doc_base, doc_beta = base.experiment.identity_document(), beta.experiment.identity_document()
    diff = {k for k in doc_base if doc_base[k] != doc_beta[k]}
    assert diff == {"model_identifier", "configuration_hash"}


def test_adapter_registry_is_keyed_by_provider_adapter_not_by_model():
    adapter = RecordingAdapter(model="model-alpha")
    registry = RuntimeAdapterRegistry({"synthetic-adapter": adapter})
    assert registry.resolve("synthetic-adapter", "synthetic-provider") is adapter
    adapter.model = "another-model-entirely"
    assert registry.resolve("synthetic-adapter", "synthetic-provider") is adapter


def test_gateway_and_resolver_share_the_single_runtime_registry():
    gateway, adapter = build_gateway(pytest.path if False else __import__("tempfile").mkdtemp())
    assert gateway.contract_resolver.runtime_registry is gateway.adapters


# ---------------------------------------------------------------------------
# Mock provider compatibility (categories 14/15/16; Invariant B) — OFFLINE
# ---------------------------------------------------------------------------


OPENAI_MOCK = mock_transport(200, {"id": "resp-openai", "output_text": "ECP-CONFORMANCE-OK"})
GEMINI_MOCK = mock_transport(200, {"candidates": [{"content": {"parts": [{"text": "ECP-GEMINI-OK"}]}}]})
OPENROUTER_MOCK = mock_transport(200, {"id": "resp-or", "choices": [{"message": {"content": "ECP-OR-OK"}}]})


def _mock_adapters():
    return {
        "openai": OpenAIResponsesAdapter(model="mock-openai-model", endpoint="https://mock.invalid/v1/responses", transport=OPENAI_MOCK, provider="synthetic-provider"),
        "gemini": GeminiGenerateContentAdapter(model="mock-gemini-model", endpoint="https://mock.invalid/v1beta/models/mock-gemini-model:generateContent", transport=GEMINI_MOCK, provider="synthetic-provider"),
        "openrouter": OpenRouterChatCompletionsAdapter(model="mock-openrouter-model", endpoint="https://mock.invalid/api/v1/chat/completions", transport=OPENROUTER_MOCK, provider="synthetic-provider"),
    }


@pytest.mark.parametrize("provider_name", ["openai", "gemini", "openrouter"])
def test_every_existing_adapter_flows_through_the_same_universal_contract(provider_name):
    adapter = _mock_adapters()[provider_name]
    unified = UniversalExecutionResult.from_provider_payload(
        adapter.execute(
            type("Lease", (), {"value": "mock-secret"})(),
            {"request_id": "r-1"},
        ),
        request_id="r-1",
    )
    assert unified.transport_status == "RECEIVED"
    assert unified.normalized_output in {"ECP-CONFORMANCE-OK", "ECP-GEMINI-OK", "ECP-OR-OK"}
    assert "mock-secret" not in json.dumps(unified.to_record_dict())


@pytest.mark.parametrize("provider_name", ["openai", "gemini", "openrouter"])
def test_provider_transport_structures_never_leak_into_the_universal_record(provider_name):
    adapter = _mock_adapters()[provider_name]
    unified = UniversalExecutionResult.from_provider_payload(
        adapter.execute(type("Lease", (), {"value": "mock-secret"})(), {"request_id": "r-1"}),
        request_id="r-1",
    )
    record = unified.to_record_dict()
    for provider_key in ("output", "choices", "candidates", "contents", "messages", "parts"):
        assert provider_key not in record


@pytest.mark.parametrize(
    "provider_name,expected_model",
    [
        ("openai", "mock-openai-model"),
        ("gemini", "mock-gemini-model"),
        ("openrouter", "mock-openrouter-model"),
    ],
)
def test_model_identifier_is_configuration_not_adapter_identity(provider_name, expected_model):
    adapters = _mock_adapters()
    adapter_ids = {a.adapter_id for a in adapters.values()}
    # one adapter implementation per provider TRANSPORT contract, not per model
    assert len(adapters) == 3 and len(adapter_ids) == 3
    assert adapters[provider_name].model == expected_model
    # swapping the model identifier keeps the same adapter implementation
    adapters[provider_name].model = "a-different-model"
    assert adapters[provider_name].adapter_id == {
        "openai": "ECP-ADAPTER-OPENAI-RESPONSES",
        "gemini": "ECP-ADAPTER-GEMINI-GENERATE-CONTENT",
        "openrouter": "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS",
    }[provider_name]


# ---------------------------------------------------------------------------
# Gateway end-to-end (categories 1/4/7/10/11) — Evidence / Audit neutrality (G/H)
# ---------------------------------------------------------------------------


def test_gateway_executes_through_the_universal_contract_and_records_evidence_metadata(tmp_path):
    gateway, adapter = build_gateway(tmp_path, with_case=True)
    record = gateway.execute(
        {
            "evaluation_id": "ECP-EVAL-CONTRACT",
            "system_id": "ECP-SYSTEM-CONTRACT",
            "credential_ref": "cred-contract",
            "test_id": "test-contract-1",
            "request_id": "request-e2e-1",
        }
    )
    assert record["status"] == "SUCCESS"
    assert record["response_status"] == "RECEIVED"
    assert record["evidence_status"] == "GENERATED"
    assert record["audit_status"] == "GENERATED"
    # the adapter received the transport request from the resolved layer
    assert adapter.calls[0]["prompt"] == CASE_PROMPT
    assert adapter.calls[0]["model_identifier"] == "model-alpha"
    assert adapter.calls[0]["request_id"] == "request-e2e-1"
    # the stored result is the normalized universal record
    assert record["result"]["transport_status"] == "RECEIVED"
    assert record["result"]["normalized_output"] == "ECP-CONFORMANCE-OK"
    # evidence carries the contract metadata, never the protected prompt text
    evidence = json.loads((tmp_path / "external-executions" / record["execution_id"] / "evidence.json").read_text())
    assert evidence["model"] == "model-alpha"
    assert evidence["adapter_version"] == "RUNTIME-UNVERSIONED"
    assert evidence["protocol_version"] == "0.7.0"
    assert evidence["case_id"] == "ECP-CASE-CONTRACT-1"
    assert evidence["prompt_hash"] == CASE.prompt_hash
    assert evidence["prompt_reference"].startswith("protected:")
    assert CASE_PROMPT not in json.dumps(evidence)
    assert evidence["experiment_identity"]["model_identifier"] == "model-alpha"
    assert evidence["experiment_identity_hash"] == hash_document(evidence["experiment_identity"])


def test_gateway_evidence_and_audit_schemas_are_provider_neutral(tmp_path):
    """Evidence/Audit keep the same shape for OpenAI, Gemini and OpenRouter."""
    adapter_ids = {
        "openai": "ECP-ADAPTER-OPENAI-RESPONSES",
        "gemini": "ECP-ADAPTER-GEMINI-GENERATE-CONTENT",
        "openrouter": "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS",
    }
    evidence_keys, audit_keys = set(), set()
    for provider_name, adapter in _mock_adapters().items():
        gateway, _ = build_gateway(
            tmp_path / provider_name, adapter=adapter, adapter_id=adapter_ids[provider_name]
        )
        record = gateway.execute(
            {
                "evaluation_id": "ECP-EVAL-CONTRACT",
                "system_id": "ECP-SYSTEM-CONTRACT",
                "credential_ref": "cred-contract",
                "test_id": "test-contract-1",
                "request_id": f"request-{provider_name}",
            }
        )
        assert record["status"] == "SUCCESS"
        directory = tmp_path / provider_name / "external-executions" / record["execution_id"]
        evidence = json.loads((directory / "evidence.json").read_text())
        audit = json.loads((directory / "audit.json").read_text())
        evidence_keys = evidence_keys or set(evidence)
        audit_keys = audit_keys or set(audit)
        assert set(evidence) == evidence_keys
        assert set(audit) == audit_keys
        assert evidence["provider"] == "synthetic-provider"
        assert evidence["model"] == adapter.model
    assert "ecp_object" in evidence_keys and "evidence_hash" in evidence_keys
    assert "audit_id" in audit_keys and "evidence_hash" in audit_keys


def test_gateway_rejects_client_injection_with_invalid_state(tmp_path):
    import http.client
    import socket
    import threading

    gateway, _ = build_gateway(tmp_path)
    server = gateway.make_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        token = gateway.pair(gateway.pairing_code)
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        headers = {"Origin": "http://127.0.0.1:8766", "X-ECP-Session": token, "Content-Type": "application/json"}
        injected = {
            "evaluation_id": "ECP-EVAL-CONTRACT",
            "system_id": "ECP-SYSTEM-CONTRACT",
            "credential_ref": "cred-contract",
            "test_id": "test-contract-1",
            "request_id": "injection-attempt",
            "prompt": "client-injected prompt",
            "ground_truth": "yes",
            "model_endpoint": "https://evil.example/v1",
        }
        connection.request("POST", "/api/v1/executions", json.dumps(injected).encode(), headers)
        response = connection.getresponse()
        body = json.loads(response.read())
        connection.close()
        assert response.status == 400
        assert body["state"] == "INVALID"
    finally:
        server.shutdown()
        server.server_close()


def test_gateway_unknown_evaluation_maps_to_console_error(tmp_path):
    gateway, _ = build_gateway(tmp_path)
    with pytest.raises(ConsoleError):
        gateway.execute(
            {
                "evaluation_id": "ECP-EVAL-NOPE",
                "system_id": "ECP-SYSTEM-CONTRACT",
                "credential_ref": "cred-contract",
                "test_id": "test-contract-1",
                "request_id": "unknown-eval",
            }
        )


def test_gateway_unauthorized_evaluation_maps_to_execution_authorization_error(tmp_path):
    identity = CredentialIdentity("cred-contract", "synthetic-provider", "test", frozenset({"execute"}))
    credentials, _store = CredentialGateway.for_testing({identity.credential_id: identity})
    unwired = AuthorizedEvaluation(
        "ECP-EVAL-CONTRACT", "ECP-SYSTEM-CONTRACT", "synthetic-provider",
        "synthetic-adapter", identity, (AuthorizedTest("test-contract-1", "Contract test", "execute"),),
    )
    gateway = LocalGateway(
        GatewayConfig(frozenset({"http://127.0.0.1:8766"}), artifact_root=tmp_path),
        {"ECP-EVAL-CONTRACT": unwired},
        credentials,
        RuntimeAdapterRegistry({"synthetic-adapter": RecordingAdapter()}),
    )
    with pytest.raises(ExecutionAuthorizationError):
        gateway.execute(
            {
                "evaluation_id": "ECP-EVAL-CONTRACT",
                "system_id": "ECP-SYSTEM-CONTRACT",
                "credential_ref": "cred-contract",
                "test_id": "test-contract-1",
                "request_id": "unauthorized",
            }
        )


# ---------------------------------------------------------------------------
# Scientific-key violation at the gateway boundary (Invariant F, end to end)
# ---------------------------------------------------------------------------


class AdjudicatingAdapter(ProviderAdapter):
    """A (forbidden) adapter that tries to smuggle adjudication into results."""

    provider = "synthetic-provider"
    adapter_id = "synthetic-adapter"

    def execute(self, lease, request):
        return {"provider_status": "RECEIVED", "output_text": "ok", "ground_truth": "yes", "score": 1.0}


def test_gateway_fails_closed_on_scientific_keys_in_provider_payload(tmp_path):
    gateway, _ = build_gateway(tmp_path, adapter=AdjudicatingAdapter())
    record = gateway.execute(
        {
            "evaluation_id": "ECP-EVAL-CONTRACT",
            "system_id": "ECP-SYSTEM-CONTRACT",
            "credential_ref": "cred-contract",
            "test_id": "test-contract-1",
            "request_id": "scientific-smuggle",
        }
    )
    assert record["status"] == "FAILED"
    assert record["execution_status"] == "INVALID"
    assert record["error_classification"] == "CONTRACT_VIOLATION"
    assert "ground_truth" in record["error"]


# ---------------------------------------------------------------------------
# Historical integrity (Invariant J) — the contract layer writes nothing
# ---------------------------------------------------------------------------


def test_contract_module_performs_no_repository_or_history_writes(tmp_path, monkeypatch):
    """Resolution and normalization are pure: no filesystem or ledger writes."""
    opened = []
    real_open = open

    def tracking_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", tracking_open)
    resolver, _, _ = build_resolver(with_case=True)
    resolved = resolver.resolve(INTENT)
    unified = UniversalExecutionResult.from_provider_payload(
        {"provider_status": "RECEIVED", "output_text": "ok"}, request_id="r-1"
    )
    resolved.transport_request()
    unified.to_record_dict()
    resolved.experiment.identity_hash()
    assert opened == []  # no reads/writes outside constructor-time identity resolution
