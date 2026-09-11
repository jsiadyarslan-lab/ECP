"""Non-scientific, no-network tests for the first provider adapter boundary."""

from dataclasses import asdict

import pytest

from ecp import (
    AdapterRegistry,
    AuthorizationGrant,
    BindingScopeError,
    CredentialBinding,
    CredentialDefinition,
    CredentialRequirement,
    ProviderRegistry,
    TargetRegistry,
    TargetResolver,
    adapter_document,
    provider_document,
    validate_binding,
)
from ecp.openai_adapter import (
    INTEGRATION_EVALUATION_REF,
    INTEGRATION_TEST_REF,
    OPENAI_ADAPTER_ID,
    OPENAI_ADAPTER_VERSION,
    OPENAI_AUTHORIZATION_REF,
    OPENAI_CREDENTIAL_REF,
    OPENAI_INTERFACE,
    OPENAI_PROVIDER_ID,
    OPENAI_PROVIDER_VERSION,
    integration_target,
    openai_adapter,
    openai_provider,
    register_openai,
)


def test_openai_metadata_is_secret_free():
    provider = openai_provider()
    adapter = openai_adapter()
    assert provider["provider_id"] == OPENAI_PROVIDER_ID
    assert provider["provider_version"] == OPENAI_PROVIDER_VERSION
    assert provider["interfaces"] == [OPENAI_INTERFACE]
    assert adapter["adapter_id"] == OPENAI_ADAPTER_ID
    assert adapter["adapter_version"] == OPENAI_ADAPTER_VERSION
    assert adapter["provider_id"] == OPENAI_PROVIDER_ID
    assert adapter["provider_interface"] == OPENAI_INTERFACE
    assert all(key not in provider for key in ("api_key", "token", "secret"))
    assert all(key not in adapter for key in ("api_key", "token", "secret"))


def test_openai_registration_is_explicit_and_non_global():
    providers = ProviderRegistry()
    adapters = AdapterRegistry()
    register_openai(providers, adapters)
    assert providers.get(OPENAI_PROVIDER_ID)["provider_version"] == OPENAI_PROVIDER_VERSION
    assert adapters.get(OPENAI_ADAPTER_ID, OPENAI_ADAPTER_VERSION)["provider_id"] == OPENAI_PROVIDER_ID
    assert ProviderRegistry().list() == []
    assert AdapterRegistry().list() == []


def _resolved_target(target_id="ECP-TARGET-INTEGRATION-A"):
    providers = ProviderRegistry()
    adapters = AdapterRegistry()
    register_openai(providers, adapters)
    targets = TargetRegistry(providers)
    targets.register(integration_target(
        target_id,
        configuration_ref="ECP-CONFIG-INTEGRATION-MODEL-A",
    ))
    return TargetResolver(providers, targets, adapters).resolve(target_id)


def test_openai_target_resolves_without_execution_or_credential_access():
    resolved = _resolved_target()
    assert resolved.provider_id == OPENAI_PROVIDER_ID
    assert resolved.provider_interface == OPENAI_INTERFACE
    assert resolved.adapter_id == OPENAI_ADAPTER_ID
    assert resolved.verified_capabilities == ("text-generation",)
    assert OPENAI_CREDENTIAL_REF not in repr(resolved)
    assert "secret" not in repr(resolved).lower()


def test_integration_fixture_identities_are_operational_only():
    target = integration_target(
        "ECP-TARGET-INTEGRATION-A",
        configuration_ref="ECP-CONFIG-INTEGRATION-MODEL-A",
    )
    assert target["target_id"].startswith("ECP-TARGET-INTEGRATION-")
    assert target["system"]["system_id"].startswith("ECP-SYSTEM-INTEGRATION-")
    assert target["system"]["configuration_ref"].startswith("ECP-CONFIG-INTEGRATION-")
    assert target["evaluation_bindings"] == [INTEGRATION_EVALUATION_REF]
    assert target["test_bindings"] == [INTEGRATION_TEST_REF]
    assert target["execution_environment"]["network"] == "disabled"
    with pytest.raises(ValueError):
        integration_target("ECP-TARGET-SCIENTIFIC-1", configuration_ref="ECP-CONFIG-INTEGRATION-MODEL-A")
    with pytest.raises(ValueError):
        integration_target("ECP-TARGET-INTEGRATION-B", configuration_ref="ECP-CONFIG-SCIENTIFIC-1")


def test_multiple_configurations_reuse_one_adapter():
    providers = ProviderRegistry()
    adapters = AdapterRegistry()
    register_openai(providers, adapters)
    targets = TargetRegistry(providers)
    targets.register(integration_target(
        "ECP-TARGET-INTEGRATION-A", configuration_ref="ECP-CONFIG-INTEGRATION-MODEL-A",
    ))
    targets.register(integration_target(
        "ECP-TARGET-INTEGRATION-B", configuration_ref="ECP-CONFIG-INTEGRATION-MODEL-B",
    ))
    resolver = TargetResolver(providers, targets, adapters)
    assert resolver.resolve("ECP-TARGET-INTEGRATION-A").adapter_id == OPENAI_ADAPTER_ID
    assert resolver.resolve("ECP-TARGET-INTEGRATION-B").adapter_id == OPENAI_ADAPTER_ID


def test_credential_binding_and_authorization_remain_separate():
    resolved = _resolved_target()
    definition = CredentialDefinition(
        definition_id="ECP-CREDDEF-OPENAI-INTEGRATION",
        provider_id=OPENAI_PROVIDER_ID,
        interface=OPENAI_INTERFACE,
        access_mechanism="windows-credential-manager-via-gateway",
        purpose="non-scientific integration smoke authorization",
    )
    requirement = CredentialRequirement(
        requirement_id="ECP-REQ-OPENAI-INTEGRATION",
        target_id=resolved.target_id,
        definition_id=definition.definition_id,
        purpose="non-scientific integration smoke authorization",
        scope=frozenset({"integration-smoke"}),
    )
    binding = CredentialBinding(
        binding_id="ECP-BIND-OPENAI-INTEGRATION",
        requirement_id=requirement.requirement_id,
        target_id=resolved.target_id,
        provider_id=OPENAI_PROVIDER_ID,
        interface=OPENAI_INTERFACE,
        purpose=requirement.purpose,
        credential_ref=OPENAI_CREDENTIAL_REF,
        scope=frozenset({"integration-smoke"}),
    )
    validate_binding(definition, requirement, binding)
    resolved.assert_binding(binding)
    grant = AuthorizationGrant(
        authorization_ref=OPENAI_AUTHORIZATION_REF,
        binding_id=binding.binding_id,
        target_id=binding.target_id,
        purpose=binding.purpose,
        scope=binding.scope,
        expires_at="2099-01-01T00:00:00Z",
    )
    assert grant.authorization_ref == OPENAI_AUTHORIZATION_REF
    assert grant.binding_id != binding.credential_ref
    assert "credential_value" not in repr(asdict(grant))


def test_fail_closed_for_wrong_provider_interface_and_capability():
    providers = ProviderRegistry()
    adapters = AdapterRegistry()
    register_openai(providers, adapters)
    targets = TargetRegistry(providers)
    document = integration_target(
        "ECP-TARGET-INTEGRATION-FAIL",
        configuration_ref="ECP-CONFIG-INTEGRATION-MODEL-FAIL",
    )
    document["required_capabilities"] = ["vision"]
    targets.register(document)
    with pytest.raises(Exception, match="lacks required capabilities"):
        TargetResolver(providers, targets, adapters).resolve("ECP-TARGET-INTEGRATION-FAIL")


def test_synthetic_provider_neutrality_uses_the_same_core_registries():
    providers = ProviderRegistry()
    adapters = AdapterRegistry()
    register_openai(providers, adapters)
    providers.register(provider_document(
        "ECP-PROVIDER-SYNTHETIC-B", "1.0.0", ["synthetic-interface"],
    ))
    targets = TargetRegistry(providers)
    synthetic = integration_target(
        "ECP-TARGET-SYNTHETIC-B", configuration_ref="ECP-CONFIG-SYNTHETIC-B",
    )
    synthetic["provider"] = {
        "provider_id": "ECP-PROVIDER-SYNTHETIC-B",
        "provider_version": "1.0.0",
        "interface": "synthetic-interface",
    }
    synthetic["adapter"] = {
        "adapter_id": "ECP-ADAPTER-SYNTHETIC-B",
        "adapter_version": "1.0.0",
        "provider_id": "ECP-PROVIDER-SYNTHETIC-B",
    }
    targets.register(synthetic)
    adapters.register(adapter_document(
        "ECP-ADAPTER-SYNTHETIC-B", "1.0.0", "ECP-PROVIDER-SYNTHETIC-B",
        "synthetic-interface", ["model-only"], ["text-generation"],
    ))
    resolved = TargetResolver(providers, targets, adapters).resolve("ECP-TARGET-SYNTHETIC-B")
    assert resolved.adapter_id == "ECP-ADAPTER-SYNTHETIC-B"


def test_no_transport_modules_are_imported_by_adapter_boundary():
    import importlib

    module = importlib.import_module("ecp.openai_adapter")
    source = open(module.__file__, encoding="utf-8").read()
    forbidden = ("requests", "httpx", "urllib", "openai", "socket", "subprocess")
    assert not any(f"import {name}" in source or f"from {name}" in source for name in forbidden)
