"""M3-ELR scientific execution path tests (reconstructed §23 traversal).

Full offline traversal with a FAKE transport (no network, no real provider
call — the scientific campaign itself requires the owner's execution order
and live credential): registered case -> pinned target -> authorization ->
credential gateway -> adapter -> normalized response -> classification ->
case-bound evidence -> audit -> persistence semantics.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecp.console import AuthorizedTest  # noqa: E402
from ecp.console_session import SessionCredentialGateway  # noqa: E402
from ecp.credentials import EnvironmentSecretStore  # noqa: E402
from ecp.credential_binding import AuthorizationGrant, CredentialBinding, ScopedReleaseRequest  # noqa: E402
from ecp.execution_contract import (  # noqa: E402
    ClientExecutionIntent,
    ContractViolation,
    ExecutionContractResolver,
    UniversalExecutionResult,
)
from ecp.hashing import hash_document  # noqa: E402
from ecp.logical_classifier import classify_response  # noqa: E402
from ecp.registered_cases import load_registered_cases  # noqa: E402
from ecp.runtime_adapters import (  # noqa: E402
    OpenRouterChatCompletionsAdapter,
    RuntimeAdapterRegistry,
    RuntimeAdapterTransportError,
)

MODEL = "inclusionai/ling-3.0-flash-sante:free"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
PURPOSE = "conformance-evaluation"

CASE_PACKAGE = {
    "cases": [
        {
            "case_id": "ECP-CASE-M3-ELR-001",
            "test_id": "ECP-TEST-M3-ELR-001",
            "candidate_id": "ECP-CAND-000101",
            "content_hash": None,  # filled by fixture
            "gt_commitment": "f" * 64,
        }
    ]
}

CANDIDATE_CONTENT = {
    "premises": ["The vex is taller than the lum.", "The lum is taller than the qid."],
    "question": "Is the vex taller than the qid? Answer with: yes, no, or cannot be determined.",
    "ground_truth": {"class": "DERIVABLE", "statement": "the vex is taller than the qid"},
    "intended_correct_answers": [{"source_block": 1, "value": "Yes — the vex is taller than the qid."}],
    "derivations": [{"raw": "premises 1 and 2 by transitivity"}],
}


class FakeLease:
    value = "test-lease-value"


class FakeTransport:
    def __init__(self, body: bytes, status: int = 200):
        self.body = body
        self.status = status
        self.calls: "list[dict]" = []

    def __call__(self, endpoint, headers, payload, timeout):
        self.calls.append({
            "endpoint": endpoint,
            "headers": dict(headers),
            "payload": json.loads(payload.decode("utf-8")),
            "timeout": timeout,
        })
        return self.status, self.body


def openrouter_body(text: str) -> bytes:
    return json.dumps({
        "id": "gen-test-1",
        "model": MODEL,
        "choices": [{"message": {"role": "assistant", "content": text}}],
    }).encode("utf-8")


@pytest.fixture()
def case_area(tmp_path):
    from ecp.hashing import hash_document as hd

    content_hash = hd(CANDIDATE_CONTENT)
    candidate = {
        "ecp_object": "case-candidate",
        "candidate_id": "ECP-CAND-000101",
        "content": CANDIDATE_CONTENT,
        "content_hash": content_hash,
    }
    candidates_dir = tmp_path / "qualification" / "candidates"
    candidates_dir.mkdir(parents=True)
    (candidates_dir / "ECP-CAND-000101.json").write_text(json.dumps(candidate), encoding="utf-8")
    package = {"cases": [dict(CASE_PACKAGE["cases"][0], content_hash=content_hash)]}
    return tmp_path, package, {"ECP-CAND-000101": content_hash}


@pytest.fixture()
def artifacts(case_area):
    area, package, index = case_area
    return load_registered_cases(package, case_area=area, manifest_index=index)


class _CredentialRef:
    def __init__(self, credential_id="ECP-SESSION-TEST"):
        self.credential_id = credential_id


class _Evaluation:
    evaluation_id = "ECP-EVAL-M3-ELR-1"
    system_id = "ECP-SYSTEM-M3-ELR-001"
    provider = "ECP-PROVIDER-OPENROUTER"
    adapter = "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS"
    credential = _CredentialRef()
    tests = [AuthorizedTest("ECP-TEST-M3-ELR-001", "registered logical case", PURPOSE)]


def _binding_grant(credential_ref):
    binding = CredentialBinding(
        "ECP-BINDING-T1", "ECP-REQ-T1", "ECP-TARGET-T1", "ECP-PROVIDER-OPENROUTER",
        "openrouter-chat-completions-api", PURPOSE, credential_ref, frozenset({PURPOSE}),
    )
    grant = AuthorizationGrant("ECP-AUTH-T1", binding.binding_id, binding.target_id, PURPOSE, frozenset({PURPOSE}), "2999-01-01T00:00:00Z")
    return binding, grant


def _gateway():
    return SessionCredentialGateway(EnvironmentSecretStore("OPENROUTER_API_KEY"), {})


def _intent(request_id="ECP-EXEC-T1"):
    return ClientExecutionIntent(
        evaluation_id="ECP-EVAL-M3-ELR-1", test_id="ECP-TEST-M3-ELR-001",
        system_id="ECP-SYSTEM-M3-ELR-001", credential_ref="ECP-SESSION-TEST",
        request_id=request_id,
    )


def _resolve(artifacts, adapter, credential_ref="ECP-SESSION-TEST"):
    binding, grant = _binding_grant(credential_ref)
    evaluation = _Evaluation()
    evaluation.credential = _CredentialRef(credential_ref)
    evaluation.credential_binding = binding
    evaluation.authorization_grant = grant
    registry = RuntimeAdapterRegistry({adapter.adapter_id: adapter})
    resolver = ExecutionContractResolver({"ECP-EVAL-M3-ELR-1": evaluation}, cases=artifacts, runtime_registry=registry)
    return resolver, binding, grant


def test_registered_presentation_is_deterministic_premises_question(artifacts):
    prompt = artifacts["ECP-TEST-M3-ELR-001"].prompt
    assert prompt.startswith("PREMISES:\n1. The vex is taller than the lum.\n2. The lum is taller than the qid.\n\nQUESTION: ")


def test_client_intent_boundary_refuses_prompt_model_temperature():
    with pytest.raises(ContractViolation):
        ClientExecutionIntent.from_client_payload({
            "evaluation_id": "a", "test_id": "b", "system_id": "c",
            "credential_ref": "d", "request_id": "e", "prompt": "arbitrary",
        })
    with pytest.raises(ContractViolation):
        ClientExecutionIntent.from_client_payload({
            "evaluation_id": "a", "test_id": "b", "system_id": "c",
            "credential_ref": "d", "request_id": "e", "model": "openrouter/free",
        })
    intent = ClientExecutionIntent.from_client_payload({
        "evaluation_id": "a", "test_id": "b", "system_id": "c",
        "credential_ref": "d", "request_id": "e",
    })
    assert set(intent.identifiers()) == {"evaluation_id", "test_id", "system_id", "credential_ref", "request_id"}


def test_resolved_request_carries_the_registered_prompt_not_a_client_prompt(artifacts):
    transport = FakeTransport(openrouter_body("Yes — premise 1."))
    adapter = OpenRouterChatCompletionsAdapter(model=MODEL, endpoint=ENDPOINT, transport=transport, temperature=0.0, max_tokens=1024)
    resolver, _, _ = _resolve(artifacts, adapter)
    resolved = resolver.resolve(_intent())
    request = resolved.transport_request()
    assert request["prompt"] == artifacts["ECP-TEST-M3-ELR-001"].prompt
    assert request["model_identifier"] == MODEL
    assert resolved.prompt_reference.startswith("protected:ECP-CASE-M3-ELR-001:")


def test_full_traversal_with_fake_transport(artifacts):
    transport = FakeTransport(openrouter_body("Yes — the vex is taller than the qid, from premise 1 and premise 2."))
    adapter = OpenRouterChatCompletionsAdapter(model=MODEL, endpoint=ENDPOINT, transport=transport, temperature=0.0, max_tokens=1024, timeout=30.0)
    resolver, binding, grant = _resolve(artifacts, adapter)
    gateway = _gateway()
    handle = gateway.open_session("test-secret-value-1234", ttl_seconds=3600)
    ref = handle["credential_ref"]
    gateway.bind_discovered_provider(ref, "ECP-PROVIDER-OPENROUTER")
    binding, grant = _binding_grant(ref)
    evaluation = _Evaluation()
    evaluation.credential = _CredentialRef(ref)
    evaluation.credential_binding = binding
    evaluation.authorization_grant = grant
    registry = RuntimeAdapterRegistry({adapter.adapter_id: adapter})
    resolver = ExecutionContractResolver({"ECP-EVAL-M3-ELR-1": evaluation}, cases=artifacts, runtime_registry=registry)
    intent = ClientExecutionIntent("ECP-EVAL-M3-ELR-1", "ECP-TEST-M3-ELR-001", "ECP-SYSTEM-M3-ELR-001", ref, "ECP-EXEC-T1")
    resolved = resolver.resolve(intent)
    release = ScopedReleaseRequest("ECP-EXEC-T1", binding.binding_id, binding.target_id, ref, PURPOSE, frozenset({PURPOSE}), 60, "2026-09-13T00:00:00Z")
    lease = gateway.release(release, binding, grant)
    payload = dict(adapter.execute(lease, resolved.transport_request()))
    result = UniversalExecutionResult.from_provider_payload(payload, request_id="ECP-EXEC-T1")
    classification = classify_response(result.normalized_output, CANDIDATE_CONTENT)
    assert result.transport_status == "RECEIVED"
    assert classification["answer_state"] == "CORRECT"
    assert classification["task_outcome"] == "SUCCESS"
    assert payload["model"] == MODEL
    assert payload["http_status"] == 200
    assert len(transport.calls) == 1


def test_frozen_sampling_policy_reaches_the_provider_payload(artifacts):
    transport = FakeTransport(openrouter_body("Yes — premise 1."))
    adapter = OpenRouterChatCompletionsAdapter(model=MODEL, endpoint=ENDPOINT, transport=transport, temperature=0.0, max_tokens=1024, timeout=30.0)
    resolver, binding, grant = _resolve(artifacts, adapter)
    resolved = resolver.resolve(_intent())
    adapter.execute(FakeLease(), resolved.transport_request())
    body = transport.calls[0]["payload"]
    assert body["temperature"] == 0.0
    assert body["max_tokens"] == 1024
    assert transport.calls[0]["timeout"] == 30.0
    assert body["model"] == MODEL


def test_none_defaults_preserve_the_historical_payload_byte_compatibility():
    transport = FakeTransport(openrouter_body("ECP-CONFORMANCE-OK"))
    adapter = OpenRouterChatCompletionsAdapter(model=MODEL, endpoint=ENDPOINT, transport=transport)
    adapter.execute(FakeLease(), {"request_id": "r1"})
    body = transport.calls[0]["payload"]
    assert set(body) == {"model", "messages", "stream"}
    assert body["messages"] == [{"role": "user", "content": adapter.prompt}]
    assert transport.calls[0]["timeout"] == 30.0


def test_api_success_with_wrong_answer_stays_execution_success_reasoning_failure(artifacts):
    transport = FakeTransport(openrouter_body("No — premise 1 contradicts it."))
    adapter = OpenRouterChatCompletionsAdapter(model=MODEL, endpoint=ENDPOINT, transport=transport, temperature=0.0, max_tokens=1024)
    resolver, _, _ = _resolve(artifacts, adapter)
    resolved = resolver.resolve(_intent())
    payload = dict(adapter.execute(FakeLease(), resolved.transport_request()))
    result = UniversalExecutionResult.from_provider_payload(payload, request_id="ECP-EXEC-T2")
    classification = classify_response(result.normalized_output, CANDIDATE_CONTENT)
    assert result.transport_status == "RECEIVED" and payload["http_status"] == 200
    assert classification["answer_state"] == "INCORRECT"
    assert classification["task_outcome"] == "FAIL"


def test_transport_failure_is_execution_invalid_unobservable_no_retry(artifacts):
    def failing(endpoint, headers, payload, timeout):
        raise OSError("connection refused")

    adapter = OpenRouterChatCompletionsAdapter(model=MODEL, endpoint=ENDPOINT, transport=failing, temperature=0.0, max_tokens=1024)
    resolver, _, _ = _resolve(artifacts, adapter)
    resolved = resolver.resolve(_intent())
    with pytest.raises(RuntimeAdapterTransportError):
        adapter.execute(FakeLease(), resolved.transport_request())
    classification = classify_response(None, CANDIDATE_CONTENT, response_received=False)
    assert classification["answer_state"] == "UNOBSERVABLE"
    assert classification["infrastructure_separation"] is True


def test_provider_payload_scientific_keys_are_refused():
    with pytest.raises(ContractViolation):
        UniversalExecutionResult.from_provider_payload(
            {"provider_status": "RECEIVED", "ground_truth": {"class": "DERIVABLE"}}, request_id="x"
        )


def test_evidence_is_case_bound_and_never_carries_gt_or_secret(artifacts):
    transport = FakeTransport(openrouter_body("Yes — the vex is taller than the qid, from premise 1."))
    adapter = OpenRouterChatCompletionsAdapter(model=MODEL, endpoint=ENDPOINT, transport=transport, temperature=0.0, max_tokens=1024)
    resolver, _, _ = _resolve(artifacts, adapter)
    resolved = resolver.resolve(_intent())
    payload = dict(adapter.execute(FakeLease(), resolved.transport_request()))
    result = UniversalExecutionResult.from_provider_payload(payload, request_id="ECP-EXEC-T3")
    classification = classify_response(result.normalized_output, CANDIDATE_CONTENT)
    evidence = {
        "execution_id": "ECP-EXEC-T3",
        "test_id": resolved.test_id,
        "case_id": resolved.experiment.case_id,
        "normalized_answer": result.normalized_output,
        "answer_state": classification["answer_state"],
        "gt_commitment_reference": "f" * 64,
    }
    evidence["evidence_hash"] = hash_document(evidence)
    serialized = json.dumps(evidence)
    assert evidence["case_id"] == "ECP-CASE-M3-ELR-001"
    assert "intended_correct_answers" not in serialized
    assert "ground_truth" not in serialized
    assert "the vex is taller than the qid" in serialized  # the model's own answer IS persisted
    assert hash_document({k: v for k, v in evidence.items() if k != "evidence_hash"}) == evidence["evidence_hash"]


def test_session_secret_never_appears_in_transport_or_results(artifacts):
    secret = "super-secret-openrouter-key"
    transport = FakeTransport(openrouter_body("Yes — premise 1."))
    adapter = OpenRouterChatCompletionsAdapter(model=MODEL, endpoint=ENDPOINT, transport=transport, temperature=0.0, max_tokens=1024)
    gateway = _gateway()
    handle = gateway.open_session(secret, ttl_seconds=3600)
    ref = handle["credential_ref"]
    gateway.bind_discovered_provider(ref, "ECP-PROVIDER-OPENROUTER")
    binding, grant = _binding_grant(ref)
    evaluation = _Evaluation()
    evaluation.credential = _CredentialRef(ref)
    evaluation.credential_binding = binding
    evaluation.authorization_grant = grant
    registry = RuntimeAdapterRegistry({adapter.adapter_id: adapter})
    resolver = ExecutionContractResolver({"ECP-EVAL-M3-ELR-1": evaluation}, cases=artifacts, runtime_registry=registry)
    intent = ClientExecutionIntent("ECP-EVAL-M3-ELR-1", "ECP-TEST-M3-ELR-001", "ECP-SYSTEM-M3-ELR-001", ref, "ECP-EXEC-T4")
    resolved = resolver.resolve(intent)
    release = ScopedReleaseRequest("ECP-EXEC-T4", binding.binding_id, binding.target_id, ref, PURPOSE, frozenset({PURPOSE}), 60, "2026-09-13T00:00:00Z")
    lease = gateway.release(release, binding, grant)
    payload = dict(adapter.execute(lease, resolved.transport_request()))
    # the secret legitimately rides ONLY the Authorization header toward the
    # provider; it must never appear in the payload body, results or records
    headers = transport.calls[0]["headers"]
    assert secret in headers.get("Authorization", "")  # authorized placement
    assert secret not in json.dumps(transport.calls[0]["payload"])
    assert secret not in json.dumps(payload)
    result = UniversalExecutionResult.from_provider_payload(payload, request_id="ECP-EXEC-T4")
    assert secret not in json.dumps(result.to_record_dict())


def test_alias_model_identity_is_never_the_pinned_target():
    from ecp.m3_registration import TARGET_MODEL_IDENTIFIER

    assert TARGET_MODEL_IDENTIFIER == MODEL
    assert TARGET_MODEL_IDENTIFIER != "openrouter/free"
    assert ":" in TARGET_MODEL_IDENTIFIER  # exact provider-pinned identifier, not a router alias


def test_frozen_order_drives_execution_sequence(case_area):
    from ecp.m3_registration import stratified_ordering

    area, package, index = case_area
    ordering = stratified_ordering([{
        "candidate_id": "ECP-CAND-000101",
        "content": {"proposed_reasoning_family": "f", "difficulty": "MEDIUM"},
    }])
    assert ordering["ordered_case_numbers"] == [1]
