"""Universal Target Onboarding Fabric v1 — full verification battery.

Implements the owner-order test matrix:

* A — existing-target onboarding through the full pipeline, resolution
  through the universal execution contract, and execution through the
  EXISTING gateway path (offline mock);
* B — new-target proof: a new target is pure configuration (registry
  entries + a configured adapter instance); no core code knows it;
* C — idempotency: same configuration -> same canonical identity, same
  registrations, same linkage, no duplicates, byte-identical records;
* D — negative cases: every failure is safe, deterministic, diagnostic and
  secret-free;
* provider-neutrality: the universal core seam carries no per-model or
  per-provider routing;
* security: secrets never reach registries, records, evidence, audit, the
  catalog or errors; the client boundary cannot be bypassed; arbitrary
  adapter code execution from configuration is rejected;
* launcher: the configuration-driven console entry builds the same gateway
  and console registry dynamically (offline only in this phase).
"""

from __future__ import annotations

import copy
import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ecp import (
    AdapterRegistry,
    ClientExecutionIntent,
    ContractViolation,
    ExecutionContractResolver,
    ProviderRegistry,
    TargetRegistry,
    adapter_document,
    provider_document,
    target_hash,
)
from ecp.console import AuthorizedTest, GatewayConfig, LocalGateway
from ecp.credential_binding import AuthorizationGrant, CredentialBinding
from ecp.credentials import CredentialGateway, CredentialIdentity
from ecp.onboarding import (
    AuthorizationNotResolved,
    CredentialNotResolved,
    DuplicateTargetConfiguration,
    EvaluationConflict,
    InvalidTargetConfiguration,
    OnboardedTarget,
    OnboardingError,
    OnboardingNotReady,
    ProviderIntegrationMismatch,
    READINESS_CHECKS,
    RuntimeAdapterMismatch,
    TargetOnboardingService,
    TargetReadiness,
    AuthorizedTestNotResolved,
)
from ecp.runtime_adapters import RuntimeAdapterRegistry
from ecp.validate import is_valid

PROVIDER = "ECP-PROVIDER-SYNTH"
INTERFACE = "synthetic-model-api"
ADAPTER = "ECP-ADAPTER-SYNTH-1"
CREDENTIAL = "ECP-CRED-ONBOARD-SYNTH"
SECRET_VALUE = "synthetic-secret-value-onboarding"

UNIVERSAL_CORE_MODULES = (
    "ecp.targets",
    "ecp.adapters",
    "ecp.execution_contract",
    "ecp.console",
    "ecp.credentials",
    "ecp.credential_binding",
    "ecp.onboarding",
)

PROVIDER_LITERALS = ("openai", "gemini", "anthropic", "openrouter", "grok", "xai")


class MockRuntimeAdapter:
    """Offline mock provider adapter behind the universal adapter contract."""

    provider = PROVIDER

    def __init__(self, *, adapter_id: str = ADAPTER, model: str = "mock-model-1",
                 reply: str = "ECP-CONFORMANCE-OK") -> None:
        self.adapter_id = adapter_id
        self.model = model
        self.reply = reply
        self.calls: "list[dict]" = []

    def execute(self, lease, request):
        self.calls.append(dict(request))
        return {
            "provider_status": "RECEIVED",
            "response_id": "resp-onboard-mock",
            "model": self.model,
            "output_text": self.reply,
            "request_id": request["request_id"],
        }


def build_service(**overrides):
    """Fresh onboarding universe: existing registries + gateway, empty wiring."""
    providers = ProviderRegistry()
    targets = TargetRegistry(providers)
    adapters = AdapterRegistry()
    runtime = RuntimeAdapterRegistry()
    identities = {
        CREDENTIAL: CredentialIdentity(
            CREDENTIAL, PROVIDER, "onboarding verification", frozenset({"execute"})
        )
    }
    for extra in overrides.get("extra_identities", []) or []:
        identities[extra.credential_id] = extra
    gateway, _store = CredentialGateway.for_testing(identities)
    gateway.provision_for_testing(CREDENTIAL, SECRET_VALUE)
    for extra in overrides.get("extra_identities", []) or []:
        gateway.provision_for_testing(extra.credential_id, f"secret-{extra.credential_id.lower()}")
    if not overrides.get("skip_integration_metadata"):
        providers.register(provider_document(PROVIDER, "1.0.0", [INTERFACE]))
        adapters.register(
            adapter_document(ADAPTER, "1.0.0", PROVIDER, INTERFACE, ["model-only"], ["text-generation"])
        )
    clock = overrides.get("clock")
    service = TargetOnboardingService(
        providers, targets, adapters, runtime, gateway,
        protocol_version="0.7.0", clock=clock,
    )
    parts = {"providers": providers, "targets": targets, "adapters": adapters,
             "runtime": runtime, "gateway": gateway, "identity": identities[CREDENTIAL]}
    return service, parts


def target_config(target_id: str = "ECP-TARGET-ONBOARD-1", *,
                  adapter_id: str = ADAPTER,
                  credential: str = CREDENTIAL,
                  evaluation_id: str = "ECP-EVAL-ONBOARD-1",
                  test_id: str = "ECP-TEST-ONBOARD-1") -> dict:
    suffix = target_id.rsplit("-", 1)[-1]
    return {
        "ecp_object": "target",
        "target_id": target_id,
        "target_version": "1.0.0",
        "system": {
            "system_id": f"ECP-SYSTEM-ONBOARD-{suffix}",
            "system_version": "1.0.0",
            "system_kind": "model-only",
            "configuration_ref": None,
        },
        "provider": {
            "provider_id": PROVIDER,
            "provider_version": "1.0.0",
            "interface": INTERFACE,
        },
        "adapter": {
            "adapter_id": adapter_id,
            "adapter_version": "1.0.0",
            "provider_id": PROVIDER,
        },
        "credential_ref": credential,
        "authorization_ref": f"ECP-AUTH-ONBOARD-{suffix}",
        "evaluation_bindings": [evaluation_id],
        "test_bindings": [test_id],
        "execution_environment": {
            "environment_id": "onboarding-verification",
            "runtime_version": "python>=3.10",
            "network": "disabled",
        },
        "required_capabilities": ["text-generation"],
    }


def binding_for(document: dict) -> CredentialBinding:
    suffix = document["target_id"].rsplit("-", 1)[-1]
    return CredentialBinding(
        f"ECP-BIND-ONBOARD-{suffix}",
        f"ECP-REQ-ONBOARD-{suffix}",
        document["target_id"],
        PROVIDER,
        INTERFACE,
        "execute",
        document["credential_ref"],
        frozenset({"execute"}),
    )


def grant_for(document: dict, binding: CredentialBinding) -> AuthorizationGrant:
    return AuthorizationGrant(
        document["authorization_ref"],
        binding.binding_id,
        binding.target_id,
        "execute",
        frozenset({"execute"}),
        "2099-01-01T00:00:00Z",
    )


def authorized_tests_for(document: dict) -> dict:
    test_id = document["test_bindings"][0]
    return {test_id: AuthorizedTest(test_id, "Onboarding conformance probe", "execute")}


def standard_onboard(service, document=None, *, adapter=None):
    document = document or target_config()
    adapter = adapter or MockRuntimeAdapter()
    return service.onboard(
        document,
        runtime_adapter=adapter,
        credential_identity=_identity_of(service),
        binding=binding_for(document),
        grant=grant_for(document, binding_for(document)),
        tests=authorized_tests_for(document),
    )


def _identity_of(service):
    return CredentialIdentity(
        CREDENTIAL, PROVIDER, "onboarding verification", frozenset({"execute"})
    )


def build_gateway(service, parts, tmp_path):
    config = GatewayConfig(frozenset({"http://127.0.0.1:8766"}), artifact_root=tmp_path)
    return LocalGateway(config, service.evaluations, parts["gateway"], parts["runtime"])


# ---------------------------------------------------------------------------
# A — Existing target: full pipeline, resolution, execution (offline)
# ---------------------------------------------------------------------------


def test_pipeline_end_to_end():
    service, parts = build_service()
    document = target_config()
    adapter = MockRuntimeAdapter()
    binding = binding_for(document)
    onboarded = service.onboard(
        document,
        runtime_adapter=adapter,
        credential_identity=_identity_of(service),
        binding=binding,
        grant=grant_for(document, binding),
        tests=authorized_tests_for(document),
    )
    assert isinstance(onboarded, OnboardedTarget)
    digest = target_hash(document)
    assert onboarded.target_hash == digest
    assert onboarded.onboarding_id == f"ECP-ONBOARD-{digest[:16]}"
    assert onboarded.resolved.adapter_id == ADAPTER
    assert onboarded.resolved.provider_id == PROVIDER
    assert onboarded.model_identifier == "mock-model-1"
    assert onboarded.readiness.state == "READY"
    assert [c.result for c in onboarded.readiness.checks] == ["PASS"] * len(READINESS_CHECKS)
    # target + runtime registration happened through the existing registries
    assert parts["targets"].get("ECP-TARGET-ONBOARD-1")["target_id"] == "ECP-TARGET-ONBOARD-1"
    assert parts["runtime"].resolve(ADAPTER, PROVIDER) is adapter
    # infrastructure registration: the evaluation registry is wired
    assert list(service.evaluations) == ["ECP-EVAL-ONBOARD-1"]
    # persisted target record: schema-valid, deterministic, retrievable
    record = onboarded.record_document(protocol_version="0.7.0")
    assert is_valid(record, "onboarding-record")
    assert service.record(onboarded.onboarding_id) == record


def test_onboarded_target_resolves_through_the_execution_contract():
    service, parts = build_service()
    standard_onboard(service)
    resolver = ExecutionContractResolver(service.evaluations, None, parts["runtime"])
    resolved = resolver.resolve(
        ClientExecutionIntent(
            evaluation_id="ECP-EVAL-ONBOARD-1",
            test_id="ECP-TEST-ONBOARD-1",
            system_id="ECP-SYSTEM-ONBOARD-1",
            credential_ref=CREDENTIAL,
            request_id="request-onboard-1",
        )
    )
    assert resolved.model_identifier == "mock-model-1"
    assert resolved.adapter_id == ADAPTER
    assert resolved.provider_id == PROVIDER
    assert resolved.experiment.system_id == "ECP-SYSTEM-ONBOARD-1"
    assert resolved.binding_id == "ECP-BIND-ONBOARD-1"
    assert resolved.grant_id == "ECP-AUTH-ONBOARD-1"


def test_onboarded_target_executes_through_the_existing_gateway(tmp_path):
    service, parts = build_service()
    standard_onboard(service)
    gateway = build_gateway(service, parts, tmp_path)
    record = gateway.execute({
        "evaluation_id": "ECP-EVAL-ONBOARD-1",
        "test_id": "ECP-TEST-ONBOARD-1",
        "system_id": "ECP-SYSTEM-ONBOARD-1",
        "credential_ref": CREDENTIAL,
        "request_id": "request-onboard-1",
    })
    assert record["status"] == "SUCCESS"
    assert record["execution_status"] == "SUCCESS"
    assert record["evidence_status"] == "GENERATED"
    assert record["audit_status"] == "GENERATED"
    assert record["persistence_status"] == "PERSISTED_LOCALLY"
    assert record["result"]["normalized_output"] == "ECP-CONFORMANCE-OK"
    evidence_path = tmp_path / record["persistence_location"] / "evidence.json"
    audit_path = tmp_path / record["persistence_location"] / "audit.json"
    assert evidence_path.exists() and audit_path.exists()
    evidence = json.loads(evidence_path.read_text())
    assert evidence["experiment_identity"]["model_identifier"] == "mock-model-1"
    assert evidence["provider"] == PROVIDER
    assert evidence["adapter"] == ADAPTER


def test_console_catalog_lists_onboarded_targets_dynamically(tmp_path):
    service, parts = build_service()
    standard_onboard(service)
    gateway = build_gateway(service, parts, tmp_path)
    catalog = gateway.catalog()
    evaluations = [e["evaluation_id"] for e in catalog["evaluations"]]
    assert evaluations == ["ECP-EVAL-ONBOARD-1"]
    entry = catalog["evaluations"][0]
    assert entry["provider"] == PROVIDER
    assert entry["adapter"] == ADAPTER
    assert [t["test_id"] for t in entry["tests"]] == ["ECP-TEST-ONBOARD-1"]


# ---------------------------------------------------------------------------
# B — New target proof: pure configuration, no core knowledge
# ---------------------------------------------------------------------------


def test_new_target_is_pure_configuration_with_no_core_knowledge():
    import ecp.adapters as adapters_module
    import ecp.credential_binding as binding_module
    import ecp.credentials as credentials_module
    import ecp.execution_contract as contract_module
    import ecp.onboarding as onboarding_module
    import ecp.targets as targets_module

    service, parts = build_service()
    standard_onboard(service)

    # A NEW target on the SAME provider: new registry entries + a configured
    # adapter instance. No new code, no core change.
    new_adapter_id = "ECP-ADAPTER-SYNTH-2"
    parts["adapters"].register(
        adapter_document(new_adapter_id, "1.0.0", PROVIDER, INTERFACE, ["model-only"], ["text-generation"])
    )
    document = target_config(
        "ECP-TARGET-ONBOARD-2",
        adapter_id=new_adapter_id,
        evaluation_id="ECP-EVAL-ONBOARD-2",
        test_id="ECP-TEST-ONBOARD-2",
    )
    binding = binding_for(document)
    onboarded = service.onboard(
        document,
        runtime_adapter=MockRuntimeAdapter(adapter_id=new_adapter_id, model="mock-model-2"),
        credential_identity=_identity_of(service),
        binding=binding,
        grant=grant_for(document, binding),
        tests=authorized_tests_for(document),
    )
    assert onboarded.readiness.state == "READY"
    assert onboarded.model_identifier == "mock-model-2"
    assert len(service.evaluations) == 2

    # the universal core modules know NOTHING about the new target/model:
    for module in (targets_module, adapters_module, contract_module,
                   credentials_module, binding_module, onboarding_module):
        source = inspect.getsource(module)
        assert "ECP-TARGET-ONBOARD-2" not in source
        assert "mock-model-2" not in source
        assert new_adapter_id not in source


def test_model_is_configuration_not_adapter_identity():
    service, parts = build_service()
    first = standard_onboard(service)
    new_adapter_id = "ECP-ADAPTER-SYNTH-2"
    parts["adapters"].register(
        adapter_document(new_adapter_id, "1.0.0", PROVIDER, INTERFACE, ["model-only"], ["text-generation"])
    )
    document = target_config(
        "ECP-TARGET-ONBOARD-2",
        adapter_id=new_adapter_id,
        evaluation_id="ECP-EVAL-ONBOARD-2",
        test_id="ECP-TEST-ONBOARD-2",
    )
    binding = binding_for(document)
    second = service.onboard(
        document,
        runtime_adapter=MockRuntimeAdapter(adapter_id=new_adapter_id, model="mock-model-2"),
        credential_identity=_identity_of(service),
        binding=binding,
        grant=grant_for(document, binding),
        tests=authorized_tests_for(document),
    )
    # Same adapter implementation class, same execution path, different model
    # identifiers carried purely as configuration identity.
    assert type(second.model_identifier) is str
    assert first.model_identifier != second.model_identifier
    assert first.resolved.adapter_id != second.resolved.adapter_id


# ---------------------------------------------------------------------------
# C — Idempotency
# ---------------------------------------------------------------------------


def test_repeated_onboarding_is_idempotent():
    service, parts = build_service()
    document = target_config()
    adapter = MockRuntimeAdapter()
    binding = binding_for(document)
    grant = grant_for(document, binding)
    first = service.onboard(
        document, runtime_adapter=adapter, credential_identity=_identity_of(service),
        binding=binding, grant=grant, tests=authorized_tests_for(document),
    )
    state_after_first = (
        len(parts["targets"].list()), len(parts["runtime"]),
        sorted(service.evaluations), len(service.records),
    )
    second = service.onboard(
        copy.deepcopy(document), runtime_adapter=MockRuntimeAdapter(),
        credential_identity=_identity_of(service), binding=binding,
        grant=grant, tests=authorized_tests_for(document),
    )
    # same canonical identity, same registration, same linkage, no duplicate
    assert second.onboarding_id == first.onboarding_id
    assert second.target_hash == first.target_hash
    assert second.registered_now is False
    assert (len(parts["targets"].list()), len(parts["runtime"]),
            sorted(service.evaluations), len(service.records)) == state_after_first
    # byte-identical persisted record
    assert service.record(second.onboarding_id) == service.record(first.onboarding_id)


def test_records_are_deterministic_across_service_instances():
    service_a, _parts_a = build_service()
    service_b, _parts_b = build_service()
    document = target_config()
    for service in (service_a, service_b):
        binding = binding_for(document)
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=grant_for(document, binding), tests=authorized_tests_for(document),
        )
    record_a = service_a.records[0]
    record_b = service_b.records[0]
    assert record_a == record_b
    assert json.dumps(record_a, sort_keys=True) == json.dumps(record_b, sort_keys=True)


def test_provider_integration_registration_is_idempotent():
    service, _parts = build_service()
    provider = provider_document(PROVIDER, "1.0.0", [INTERFACE])
    adapter = adapter_document(ADAPTER, "1.0.0", PROVIDER, INTERFACE, ["model-only"], ["text-generation"])
    service.register_provider_integration(provider, adapter)  # no-op re-registration
    divergent = provider_document(PROVIDER, "1.0.0", [INTERFACE, "second-interface"])
    with pytest.raises(ProviderIntegrationMismatch):
        service.register_provider_integration(divergent, adapter)


def test_divergent_configuration_under_same_target_id_rejected():
    service, parts = build_service()
    standard_onboard(service)
    original_hash = target_hash(parts["targets"].get("ECP-TARGET-ONBOARD-1"))
    divergent = target_config()
    divergent["required_capabilities"] = ["text-generation", "vision"]
    with pytest.raises(DuplicateTargetConfiguration):
        standard_onboard(service, document=divergent)
    # the frozen registration is untouched
    assert target_hash(parts["targets"].get("ECP-TARGET-ONBOARD-1")) == original_hash


def test_divergent_runtime_configuration_under_same_adapter_id_rejected():
    service, _parts = build_service()
    standard_onboard(service)
    document = target_config()
    binding = binding_for(document)
    with pytest.raises(RuntimeAdapterMismatch):
        service.onboard(
            document,
            runtime_adapter=MockRuntimeAdapter(model="different-model-entirely"),
            credential_identity=_identity_of(service),
            binding=binding,
            grant=grant_for(document, binding),
            tests=authorized_tests_for(document),
        )


# ---------------------------------------------------------------------------
# D — Negative cases: safe, deterministic, diagnostic, secret-free
# ---------------------------------------------------------------------------


def test_unknown_provider_rejected_deterministically():
    service, _parts = build_service()
    document = target_config()
    document["provider"]["provider_id"] = "ECP-PROVIDER-MISSING"
    document["adapter"]["provider_id"] = "ECP-PROVIDER-MISSING"
    binding = CredentialBinding(
        "ECP-BIND-ONBOARD-1", "ECP-REQ-ONBOARD-1", document["target_id"],
        "ECP-PROVIDER-MISSING", INTERFACE, "execute", document["credential_ref"],
        frozenset({"execute"}),
    )
    with pytest.raises(OnboardingError, match="unknown provider ECP-PROVIDER-MISSING"):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=grant_for(document, binding), tests=authorized_tests_for(document),
        )


def test_unknown_adapter_rejected_deterministically():
    service, _parts = build_service()
    document = target_config(adapter_id="ECP-ADAPTER-MISSING")
    binding = binding_for(document)
    with pytest.raises(OnboardingError, match="adapter resolution failed"):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(adapter_id="ECP-ADAPTER-MISSING"),
            credential_identity=_identity_of(service), binding=binding,
            grant=grant_for(document, binding), tests=authorized_tests_for(document),
        )


def test_unknown_model_rejected_as_not_ready():
    service, _parts = build_service()
    document = target_config()
    binding = binding_for(document)
    with pytest.raises(OnboardingNotReady) as excinfo:
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(model="UNCONFIGURED"),
            credential_identity=_identity_of(service), binding=binding,
            grant=grant_for(document, binding), tests=authorized_tests_for(document),
        )
    assert any("model_identified" in reason for reason in excinfo.value.reasons)
    # no evaluation wiring was created (fail-safe: no execution capability)
    assert service.evaluations == {}
    assert service.records == []


def test_missing_credential_ref_rejected_at_validation():
    service, _parts = build_service()
    document = target_config()
    binding = binding_for(document)
    grant = grant_for(document, binding)
    del document["credential_ref"]
    with pytest.raises(InvalidTargetConfiguration):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=grant, tests=authorized_tests_for(document),
        )


def test_invalid_credential_ref_rejected():
    service, _parts = build_service()
    document = target_config(credential="ECP-CRED-NOT-REGISTERED")
    binding = binding_for(document)
    with pytest.raises(CredentialNotResolved):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=CredentialIdentity(
                "ECP-CRED-NOT-REGISTERED", PROVIDER, "x", frozenset({"execute"})
            ),
            binding=binding, grant=grant_for(document, binding), tests=authorized_tests_for(document),
        )


def test_invalid_interface_rejected():
    service, _parts = build_service()
    document = target_config()
    document["provider"]["interface"] = "interface-not-declared"
    binding = binding_for(document)
    binding = CredentialBinding(
        binding.binding_id, binding.requirement_id, binding.target_id,
        binding.provider_id, "interface-not-declared", binding.purpose,
        binding.credential_ref, binding.scope,
    )
    with pytest.raises(OnboardingError, match="adapter resolution failed"):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=grant_for(document, binding), tests=authorized_tests_for(document),
        )


def test_missing_authorization_rejected():
    service, _parts = build_service()
    document = target_config()
    binding = binding_for(document)
    with pytest.raises(AuthorizationNotResolved, match="OWNER DECISION REQUIRED"):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=None, tests=authorized_tests_for(document),
        )


def test_revoked_or_mismatched_authorization_rejected():
    service, _parts = build_service()
    document = target_config()
    binding = binding_for(document)
    revoked = AuthorizationGrant(
        document["authorization_ref"], binding.binding_id, binding.target_id,
        "execute", frozenset({"execute"}), "2099-01-01T00:00:00Z", status="REVOKED",
    )
    with pytest.raises(AuthorizationNotResolved, match="REVOKED"):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=revoked, tests=authorized_tests_for(document),
        )
    other_binding = CredentialBinding(
        "ECP-BIND-OTHER", "ECP-REQ-OTHER", "ECP-TARGET-OTHER",
        PROVIDER, INTERFACE, "execute", CREDENTIAL, frozenset({"execute"}),
    )
    mismatched = AuthorizationGrant(
        document["authorization_ref"], other_binding.binding_id, other_binding.target_id,
        "execute", frozenset({"execute"}), "2099-01-01T00:00:00Z",
    )
    with pytest.raises(AuthorizationNotResolved, match="does not match the binding"):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=mismatched, tests=authorized_tests_for(document),
        )


def test_expired_authorization_rejected():
    service, _parts = build_service(clock=lambda: datetime(2100, 1, 1, tzinfo=timezone.utc))
    document = target_config()
    binding = binding_for(document)
    with pytest.raises(AuthorizationNotResolved, match="expired"):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=grant_for(document, binding), tests=authorized_tests_for(document),
        )


def test_malformed_target_configuration_rejected():
    service, _parts = build_service()
    document = target_config()
    binding = binding_for(document)
    grant = grant_for(document, binding)
    tests = authorized_tests_for(document)
    malformed = copy.deepcopy(document)
    malformed["unexpected_field"] = "forbidden"
    with pytest.raises(InvalidTargetConfiguration):
        service.onboard(
            malformed, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=grant, tests=tests,
        )
    malformed = copy.deepcopy(document)
    malformed["target_id"] = "not-a-valid-target-id"
    with pytest.raises(InvalidTargetConfiguration):
        service.onboard(
            malformed, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=grant, tests=tests,
        )


def test_unsupported_capability_rejected():
    service, _parts = build_service()
    document = target_config()
    document["required_capabilities"] = ["vision"]
    binding = binding_for(document)
    with pytest.raises(OnboardingError, match="adapter lacks required capabilities: vision"):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=grant_for(document, binding), tests=authorized_tests_for(document),
        )


def test_secret_bearing_configuration_rejected():
    service, _parts = build_service()
    document = target_config()
    document["api_key"] = "sk-should-never-enter"
    with pytest.raises(InvalidTargetConfiguration, match="secret-bearing"):
        standard_onboard(service, document=document)


def test_missing_test_binding_rejected():
    service, _parts = build_service()
    document = target_config()
    binding = binding_for(document)
    with pytest.raises(AuthorizedTestNotResolved):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=binding,
            grant=grant_for(document, binding), tests={},
        )


def test_evaluation_conflict_on_divergent_wiring():
    service, _parts = build_service()
    standard_onboard(service)
    document = target_config()
    other_binding = CredentialBinding(
        "ECP-BIND-ONBOARD-OTHER", "ECP-REQ-ONBOARD-OTHER", document["target_id"],
        PROVIDER, INTERFACE, "execute", CREDENTIAL, frozenset({"execute"}),
    )
    other_grant = AuthorizationGrant(
        "ECP-AUTH-ONBOARD-OTHER", other_binding.binding_id, other_binding.target_id,
        "execute", frozenset({"execute"}), "2099-01-01T00:00:00Z",
    )
    with pytest.raises(EvaluationConflict):
        service.onboard(
            document, runtime_adapter=MockRuntimeAdapter(),
            credential_identity=_identity_of(service), binding=other_binding,
            grant=other_grant, tests=authorized_tests_for(document),
        )


def test_failures_are_deterministic_and_diagnostic():
    service, _parts = build_service()
    document = target_config(credential="ECP-CRED-NOT-REGISTERED")
    binding = binding_for(document)
    identity = CredentialIdentity(
        "ECP-CRED-NOT-REGISTERED", PROVIDER, "x", frozenset({"execute"})
    )
    errors = []
    for _ in range(2):
        with pytest.raises(CredentialNotResolved) as excinfo:
            service.onboard(
                document, runtime_adapter=MockRuntimeAdapter(),
                credential_identity=identity, binding=binding,
                grant=grant_for(document, binding), tests=authorized_tests_for(document),
            )
        errors.append(str(excinfo.value))
    assert errors[0] == errors[1]
    assert SECRET_VALUE not in errors[0]


# ---------------------------------------------------------------------------
# Readiness drift detection (read-only re-check)
# ---------------------------------------------------------------------------


def test_readiness_recheck_detects_credential_revocation():
    service, parts = build_service()
    standard_onboard(service)
    assert service.readiness("ECP-TARGET-ONBOARD-1").state == "READY"
    parts["gateway"].revoke(CREDENTIAL)
    readiness = service.readiness("ECP-TARGET-ONBOARD-1")
    assert readiness.state == "NOT_READY"
    assert "credential_resolved" in " ".join(readiness.failed_details())


def test_readiness_recheck_detects_grant_expiry():
    now = {"value": datetime(2025, 1, 1, tzinfo=timezone.utc)}
    service, _parts = build_service(clock=lambda: now["value"])
    standard_onboard(service)
    assert service.readiness("ECP-TARGET-ONBOARD-1").state == "READY"
    now["value"] = datetime(2100, 1, 1, tzinfo=timezone.utc)
    readiness = service.readiness("ECP-TARGET-ONBOARD-1")
    assert readiness.state == "NOT_READY"
    assert "authorization_valid" in " ".join(readiness.failed_details())


def test_execution_fails_closed_after_credential_revocation(tmp_path):
    service, parts = build_service()
    standard_onboard(service)
    gateway = build_gateway(service, parts, tmp_path)
    parts["gateway"].revoke(CREDENTIAL)
    record = gateway.execute({
        "evaluation_id": "ECP-EVAL-ONBOARD-1",
        "test_id": "ECP-TEST-ONBOARD-1",
        "system_id": "ECP-SYSTEM-ONBOARD-1",
        "credential_ref": CREDENTIAL,
        "request_id": "request-after-revoke",
    })
    assert record["status"] == "FAILED"
    assert record["error_classification"] == "CREDENTIAL_ERROR"
    assert SECRET_VALUE not in json.dumps(record)


def test_readiness_for_unknown_target_is_diagnostic():
    service, _parts = build_service()
    with pytest.raises(OnboardingError, match="has not been onboarded"):
        service.readiness("ECP-TARGET-NEVER-ONBOARDED")


# ---------------------------------------------------------------------------
# Provider neutrality (owner order §18)
# ---------------------------------------------------------------------------


def test_universal_core_modules_have_no_provider_or_model_routing():
    import importlib
    for module_name in UNIVERSAL_CORE_MODULES:
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
        for pattern in (r"if\s+[^:\n]*\bmodel\b\s*==", r"if\s+[^:\n]*\bprovider\b\s*=="):
            assert not __import__("re").search(pattern, source), (module_name, pattern)
        for literal in PROVIDER_LITERALS:
            assert literal not in source.lower(), (module_name, literal)


def test_runtime_dispatch_seam_is_provider_neutral():
    from ecp.runtime_adapters import RuntimeAdapterRegistry as registry_class
    source = inspect.getsource(registry_class)
    for pattern in (r"if\s+[^:\n]*\bmodel\b\s*==", r"if\s+[^:\n]*\bprovider\b\s*=="):
        assert not __import__("re").search(pattern, source)
    for literal in PROVIDER_LITERALS:
        assert literal not in source.lower()


def test_onboarding_is_provider_agnostic():
    # The SAME service structure onboards two synthetic providers identically:
    # no provider-specific branch exists anywhere in the path.
    other_provider = "ECP-PROVIDER-SYNTH-B"
    other_interface = "synthetic-model-api-b"
    other_adapter = "ECP-ADAPTER-SYNTH-B-1"
    other_credential = "ECP-CRED-ONBOARD-SYNTH-B"
    other_identity = CredentialIdentity(
        other_credential, other_provider, "second provider", frozenset({"execute"})
    )
    service, parts = build_service(extra_identities=[other_identity])
    standard_onboard(service)  # provider A
    parts["providers"].register(provider_document(other_provider, "1.0.0", [other_interface]))
    parts["adapters"].register(
        adapter_document(other_adapter, "1.0.0", other_provider, other_interface, ["model-only"], ["text-generation"])
    )
    document = target_config(
        "ECP-TARGET-ONBOARD-B1",
        adapter_id=other_adapter,
        credential=other_credential,
        evaluation_id="ECP-EVAL-ONBOARD-B1",
        test_id="ECP-TEST-ONBOARD-B1",
    )
    document["provider"]["provider_id"] = other_provider
    document["provider"]["interface"] = other_interface
    document["adapter"]["provider_id"] = other_provider
    binding = CredentialBinding(
        "ECP-BIND-ONBOARD-B1", "ECP-REQ-ONBOARD-B1", document["target_id"],
        other_provider, other_interface, "execute", other_credential,
        frozenset({"execute"}),
    )
    grant = AuthorizationGrant(
        "ECP-AUTH-ONBOARD-B1", binding.binding_id, binding.target_id,
        "execute", frozenset({"execute"}), "2099-01-01T00:00:00Z",
    )

    class OtherProviderAdapter(MockRuntimeAdapter):
        provider = other_provider

    onboarded = service.onboard(
        document,
        runtime_adapter=OtherProviderAdapter(adapter_id=other_adapter, model="mock-model-b"),
        credential_identity=other_identity,
        binding=binding,
        grant=grant,
        tests=authorized_tests_for(document),
    )
    assert onboarded.readiness.state == "READY"
    assert onboarded.resolved.provider_id == other_provider
    assert len(service.evaluations) == 2


# ---------------------------------------------------------------------------
# Security (owner order §21)
# ---------------------------------------------------------------------------


def test_no_secret_material_in_any_surface(tmp_path):
    service, parts = build_service()
    standard_onboard(service)
    gateway = build_gateway(service, parts, tmp_path)
    execution = gateway.execute({
        "evaluation_id": "ECP-EVAL-ONBOARD-1",
        "test_id": "ECP-TEST-ONBOARD-1",
        "system_id": "ECP-SYSTEM-ONBOARD-1",
        "credential_ref": CREDENTIAL,
        "request_id": "request-secret-scan",
    })
    surfaces = [
        json.dumps(execution),
        json.dumps(gateway.catalog()),
        json.dumps([t for t in parts["targets"].list()]),
        json.dumps(service.records),
        json.dumps(parts["adapters"].list()),
    ]
    for persisted in Path(tmp_path).rglob("*.json"):
        surfaces.append(persisted.read_text())
    for surface in surfaces:
        assert SECRET_VALUE not in surface
    for record in service.records:
        assert "credential_value" not in json.dumps(record).lower()


def test_client_cannot_inject_beyond_the_authorized_identifiers(tmp_path):
    service, parts = build_service()
    standard_onboard(service)
    gateway = build_gateway(service, parts, tmp_path)
    with pytest.raises(ContractViolation):
        gateway.execute({
            "evaluation_id": "ECP-EVAL-ONBOARD-1",
            "test_id": "ECP-TEST-ONBOARD-1",
            "system_id": "ECP-SYSTEM-ONBOARD-1",
            "credential_ref": CREDENTIAL,
            "request_id": "request-injection",
            "endpoint": "https://attacker.invalid/",
            "prompt": "injected prompt",
        })


def test_unauthenticated_session_rejected(tmp_path):
    service, parts = build_service()
    standard_onboard(service)
    gateway = build_gateway(service, parts, tmp_path)
    from ecp.console import AuthorizationError
    with pytest.raises(AuthorizationError):
        gateway.authenticate("not-a-session-token")
    with pytest.raises(AuthorizationError):
        gateway.authenticate(None)


# ---------------------------------------------------------------------------
# Launcher: configuration-driven console entry (offline)
# ---------------------------------------------------------------------------


def _import_launcher(repo_root):
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    import run_console
    return run_console


def test_launcher_default_configuration_is_offline(repo_root):
    launcher = _import_launcher(repo_root)
    configuration = launcher.load_configuration(None)
    assert configuration["targets"][0]["adapter_kind"] == "offline-mock"
    for credential in configuration["credentials"]:
        assert credential["secret_environment_variable"] is None


def test_launcher_rejects_unknown_adapter_kinds(repo_root):
    launcher = _import_launcher(repo_root)
    target = launcher.BUILTIN_DEMO_CONFIGURATION["targets"][0]["target"]
    for evil in ("evil.module.ClassName", "openai-responses; import os", "os.system"):
        with pytest.raises(ValueError, match="unknown adapter kind"):
            launcher._build_runtime_adapter({"adapter_kind": evil, "model": "m"}, target)


def test_launcher_builds_gateway_from_configuration_file(repo_root, tmp_path):
    launcher = _import_launcher(repo_root)
    config_path = tmp_path / "onboarding-config.json"
    config_path.write_text(json.dumps(launcher.BUILTIN_DEMO_CONFIGURATION))
    configuration = launcher.load_configuration(config_path)
    gateway_config = GatewayConfig(
        frozenset({"http://127.0.0.1:8766"}), artifact_root=tmp_path
    )
    gateway, service = launcher.build_gateway(configuration, gateway_config)
    catalog_ids = [e["evaluation_id"] for e in gateway.catalog()["evaluations"]]
    assert catalog_ids == ["ECP-EVAL-DEMO-OFFLINE-1"]
    record = gateway.execute({
        "evaluation_id": "ECP-EVAL-DEMO-OFFLINE-1",
        "test_id": "ECP-TEST-DEMO-OFFLINE-1",
        "system_id": "ECP-SYSTEM-DEMO-OFFLINE-1",
        "credential_ref": "ECP-DEMO-CREDENTIAL-OFFLINE",
        "request_id": "request-launcher-offline",
    })
    assert record["status"] == "SUCCESS"
    assert record["result"]["normalized_output"] == "ECP-CONFORMANCE-OK"
    assert record["evidence_status"] == "GENERATED"
    onboarding_records = service.records
    assert len(onboarding_records) == 1
    assert onboarding_records[0]["readiness_state"] == "READY"
    assert onboarding_records[0]["model_identifier"] == "offline-demo-model-1"


def test_launcher_fails_closed_when_real_credential_missing(repo_root, tmp_path):
    launcher = _import_launcher(repo_root)
    configuration = copy.deepcopy(launcher.BUILTIN_DEMO_CONFIGURATION)
    configuration["credentials"][0]["secret_environment_variable"] = "OPENAI_API_KEY"
    import os
    os.environ.pop("OPENAI_API_KEY", None)
    gateway_config = GatewayConfig(
        frozenset({"http://127.0.0.1:8766"}), artifact_root=tmp_path
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        launcher.build_gateway(configuration, gateway_config)


def test_launcher_builds_session_console_enabled_gateway(repo_root, tmp_path):
    # The SAME launcher now serves the visual provider discovery console on
    # the SAME gateway: registry-driven descriptors + credential sessions,
    # with the offline demonstration target still fully functional.
    launcher = _import_launcher(repo_root)
    configuration = launcher.load_configuration(None)
    gateway_config = GatewayConfig(
        frozenset({"http://127.0.0.1:8766"}), artifact_root=tmp_path
    )
    gateway, service = launcher.build_gateway(configuration, gateway_config)
    descriptors = gateway.session_descriptors()
    assert len(descriptors) == 6
    session_secret = "sk-launcher-session-TESTKEY-DO-NOT-LEAK-0001"
    handle = gateway.execute_session_route(
        "/api/v1/credentials/session", {"credential_secret": session_secret}
    )
    assert handle["credential_ref"].startswith("ECP-SESSION-CREDENTIAL-")
    assert session_secret not in json.dumps(handle)
    # offline regression: the configured demo target still executes intact
    record = gateway.execute({
        "evaluation_id": "ECP-EVAL-DEMO-OFFLINE-1",
        "test_id": "ECP-TEST-DEMO-OFFLINE-1",
        "system_id": "ECP-SYSTEM-DEMO-OFFLINE-1",
        "credential_ref": "ECP-DEMO-CREDENTIAL-OFFLINE",
        "request_id": "request-launcher-session-regression",
    })
    assert record["status"] == "SUCCESS"
    assert record["result"]["normalized_output"] == "ECP-CONFORMANCE-OK"


def test_launcher_builds_anthropic_messages_adapter_kind(repo_root):
    launcher = _import_launcher(repo_root)
    target = {"provider": {"provider_id": "ECP-PROVIDER-ANTHROPIC-TEST"}, "adapter": {"adapter_id": "ECP-ADAPTER-ANTHROPIC-TEST"}}
    adapter = launcher._build_runtime_adapter(
        {"adapter_kind": "anthropic-messages", "model": "claude-test", "endpoint": "https://provider.invalid/v1"},
        target,
    )
    assert isinstance(adapter, launcher.AnthropicMessagesAdapter)
    assert adapter.model == "claude-test"
    assert adapter.provider == "ECP-PROVIDER-ANTHROPIC-TEST"
    assert adapter.adapter_id == "ECP-ADAPTER-ANTHROPIC-TEST"


# ---------------------------------------------------------------------------
# Shipped example integrity
# ---------------------------------------------------------------------------


def test_shipped_onboarding_example_is_recomputable(repo_root):
    example_path = repo_root / "examples" / "onboarding.example.json"
    example = json.loads(example_path.read_text())
    synthetic_target = {
        "ecp_object": "target",
        "target_id": "ECP-TARGET-ONBOARD-EXAMPLE-1",
        "target_version": "1.0.0",
        "system": {
            "system_id": "ECP-SYSTEM-ONBOARD-EXAMPLE-1",
            "system_version": "1.0.0",
            "system_kind": "model-only",
            "configuration_ref": None,
        },
        "provider": {
            "provider_id": "ECP-PROVIDER-ONBOARD-EXAMPLE",
            "provider_version": "1.0.0",
            "interface": "offline-conformance",
        },
        "adapter": {
            "adapter_id": "ECP-ADAPTER-ONBOARD-EXAMPLE",
            "adapter_version": "1.0.0",
            "provider_id": "ECP-PROVIDER-ONBOARD-EXAMPLE",
        },
        "credential_ref": "ECP-ONBOARD-EXAMPLE-CREDENTIAL",
        "authorization_ref": "ECP-ONBOARD-EXAMPLE-AUTH",
        "evaluation_bindings": ["ECP-EVAL-ONBOARD-EXAMPLE-1"],
        "test_bindings": ["ECP-ONBOARD-EXAMPLE-TEST-1"],
        "execution_environment": {
            "environment_id": "offline-example",
            "runtime_version": "python>=3.10",
            "network": "disabled",
        },
        "required_capabilities": ["text-generation"],
    }
    digest = target_hash(synthetic_target)
    assert example["target_hash"] == digest
    assert example["onboarding_id"] == f"ECP-ONBOARD-{digest[:16]}"
    assert example["readiness_state"] == "READY"
    assert all(c["result"] == "PASS" for c in example["readiness_checks"])
    assert [c["check"] for c in example["readiness_checks"]] == list(READINESS_CHECKS)
    assert is_valid(example, "onboarding-record")


# ---------------------------------------------------------------------------
# Launcher: generic chat-completions gateway dialect (real kind, offline tests)
# ---------------------------------------------------------------------------


def test_launcher_builds_gateway_target_from_shipped_gateway_example(repo_root, tmp_path, monkeypatch):
    launcher = _import_launcher(repo_root)
    example_path = repo_root / "examples" / "launcher" / "onboarding-chat-completions-gateway.example.json"
    configuration = launcher.load_configuration(example_path)
    monkeypatch.setenv("EXAMPLE_GATEWAY_TOKEN", "example-synthetic-token")
    gateway_config = GatewayConfig(
        frozenset({"http://127.0.0.1:8766"}), artifact_root=tmp_path
    )
    gateway, service = launcher.build_gateway(configuration, gateway_config)
    catalog_ids = [e["evaluation_id"] for e in gateway.catalog()["evaluations"]]
    assert catalog_ids == ["ECP-EVAL-EXAMPLE-GATEWAY-1"]
    # The runtime adapter carries the generic gateway knobs from configuration.
    adapter = service.runtime.get("ECP-ADAPTER-EXAMPLE-GATEWAY-CHAT-COMPLETIONS")
    assert adapter.model == "example-gateway-model-1"
    assert adapter.endpoint == "https://gateway.example.invalid/api/v1/chat/completions"
    assert adapter._token_header == "X-Example-Token"
    assert adapter._bearer_value == "example-public-marker"
    assert adapter._extra_headers == {"X-Example-Route": "example-route", "X-Example-Client": "example-client"}
    # Readiness is fully offline: the onboarding record is READY without any
    # provider call (the real call is a separately authorized phase).
    records = service.records
    assert len(records) == 1
    assert records[0]["readiness_state"] == "READY"
    assert records[0]["model_identifier"] == "example-gateway-model-1"


def test_launcher_gateway_example_fails_closed_without_environment_credential(repo_root, tmp_path, monkeypatch):
    launcher = _import_launcher(repo_root)
    example_path = repo_root / "examples" / "launcher" / "onboarding-chat-completions-gateway.example.json"
    configuration = launcher.load_configuration(example_path)
    monkeypatch.delenv("EXAMPLE_GATEWAY_TOKEN", raising=False)
    gateway_config = GatewayConfig(
        frozenset({"http://127.0.0.1:8766"}), artifact_root=tmp_path
    )
    with pytest.raises(RuntimeError, match="EXAMPLE_GATEWAY_TOKEN"):
        launcher.build_gateway(configuration, gateway_config)


def test_shipped_gateway_example_is_schematic_and_secret_free(repo_root):
    example_path = repo_root / "examples" / "launcher" / "onboarding-chat-completions-gateway.example.json"
    text = example_path.read_text()
    example = json.loads(text)
    entry = example["targets"][0]
    # Generic gateway knobs are present and come from configuration only.
    assert entry["adapter_kind"] == "openrouter-chat-completions"
    assert entry["token_header"] == "X-Example-Token"
    assert entry["bearer_value"] == "example-public-marker"
    assert entry["extra_headers"] == {"X-Example-Route": "example-route", "X-Example-Client": "example-client"}
    # Placeholder endpoint only (reserved .invalid TLD): no real host.
    assert entry["endpoint"].endswith(".invalid/api/v1/chat/completions")
    # The credential references an environment variable NAME only.
    credential = example["credentials"][0]
    assert credential["secret_environment_variable"] == "EXAMPLE_GATEWAY_TOKEN"
    assert credential["credential_id"] == entry["target"]["credential_ref"]
    # No secret-shaped material anywhere in the shipped file.
    for forbidden in ("sk-", "Bearer ", "api_key", "secret-"):
        assert forbidden not in text, forbidden


def test_launcher_rejects_malformed_gateway_header_configuration(repo_root):
    launcher = _import_launcher(repo_root)
    target = launcher.BUILTIN_DEMO_CONFIGURATION["targets"][0]["target"]
    good = {"adapter_kind": "openrouter-chat-completions", "model": "m", "endpoint": "https://gateway.invalid/api/v1/chat/completions"}
    with pytest.raises(ValueError, match="token_header"):
        launcher._build_runtime_adapter({**good, "token_header": 7}, target)
    with pytest.raises(ValueError, match="bearer_value"):
        launcher._build_runtime_adapter({**good, "bearer_value": []}, target)
    with pytest.raises(ValueError, match="extra_headers"):
        launcher._build_runtime_adapter({**good, "extra_headers": "not-an-object"}, target)
    with pytest.raises(ValueError, match="token_header"):
        launcher._build_runtime_adapter({**good, "token_header": "Bad Name"}, target)
