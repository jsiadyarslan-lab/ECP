import copy

import pytest

from ecp import (
    DuplicateProvider,
    DuplicateTarget,
    InvalidTarget,
    ProviderRegistry,
    TargetRegistry,
    provider_document,
    target_hash,
)
from ecp.validate import is_valid


def provider(provider_id, interface="model-api"):
    return provider_document(provider_id, "1.0.0", [interface])


def target(target_id, provider_id, *, adapter_provider=None, credential="ECP-CRED-TEST-A"):
    return {
        "ecp_object": "target",
        "target_id": target_id,
        "target_version": "1.0.0",
        "system": {
            "system_id": f"ECP-SYSTEM-{target_id.rsplit('-', 1)[-1]}",
            "system_version": "1.0.0",
            "system_kind": "model-only",
            "configuration_ref": None,
        },
        "provider": {
            "provider_id": provider_id,
            "provider_version": "1.0.0",
            "interface": "model-api",
        },
        "adapter": {
            "adapter_id": "ECP-ADAPTER-SHARED-1",
            "adapter_version": "1.0.0",
            "provider_id": adapter_provider or provider_id,
        },
        "credential_ref": credential,
        "authorization_ref": "ECP-AUTH-TEST-A",
        "evaluation_bindings": ["ECP-EVAL-TEST-A"],
        "test_bindings": ["ECP-TEST-TEST-A"],
        "execution_environment": {
            "environment_id": "synthetic",
            "runtime_version": "1.0.0",
            "network": "disabled",
        },
    }


def test_provider_and_target_schema_are_registered():
    assert is_valid(provider("ECP-PROVIDER-A"), "provider")
    assert is_valid(target("ECP-TARGET-A1", "ECP-PROVIDER-A"), "target")


def test_multiple_providers_and_targets_share_one_registry():
    providers = ProviderRegistry()
    providers.register(provider("ECP-PROVIDER-A"))
    providers.register(provider("ECP-PROVIDER-B", "agent-api"))
    registry = TargetRegistry(providers)
    registry.register(target("ECP-TARGET-A1", "ECP-PROVIDER-A"))
    registry.register(target("ECP-TARGET-A2", "ECP-PROVIDER-A", credential="ECP-CRED-TEST-B"))
    registry.register(target("ECP-TARGET-B1", "ECP-PROVIDER-B", adapter_provider="ECP-PROVIDER-B"))
    assert [item["target_id"] for item in registry.list()] == [
        "ECP-TARGET-A1", "ECP-TARGET-A2", "ECP-TARGET-B1"
    ]


def test_duplicate_provider_and_target_rejected():
    providers = ProviderRegistry()
    providers.register(provider("ECP-PROVIDER-A"))
    with pytest.raises(DuplicateProvider):
        providers.register(provider("ECP-PROVIDER-A"))
    registry = TargetRegistry(providers)
    registry.register(target("ECP-TARGET-A1", "ECP-PROVIDER-A"))
    with pytest.raises(DuplicateTarget):
        registry.register(target("ECP-TARGET-A1", "ECP-PROVIDER-A"))


def test_version_and_retrieval_are_deterministic():
    providers = ProviderRegistry({"a": provider("ECP-PROVIDER-A")})
    registry = TargetRegistry(providers)
    document = target("ECP-TARGET-A1", "ECP-PROVIDER-A")
    registry.register(document)
    assert registry.get("ECP-TARGET-A1", "1.0.0") == document
    assert registry.hash("ECP-TARGET-A1") == target_hash(document)
    assert registry.hash("ECP-TARGET-A1") == registry.hash("ECP-TARGET-A1")
    with pytest.raises(InvalidTarget):
        registry.get("ECP-TARGET-A1", "2.0.0")


def test_complete_system_target_is_supported_without_provider_specific_fields():
    providers = ProviderRegistry({"a": provider("ECP-PROVIDER-A")})
    registry = TargetRegistry(providers)
    document = target("ECP-TARGET-AGENT", "ECP-PROVIDER-A")
    document["system"]["system_kind"] = "complete-system"
    document["system"]["configuration_ref"] = "ECP-CONFIG-AGENT-1"
    registry.register(document)
    assert registry.get("ECP-TARGET-AGENT")["system"]["system_kind"] == "complete-system"


def test_secret_bearing_target_is_rejected_and_reference_survives():
    providers = ProviderRegistry({"a": provider("ECP-PROVIDER-A")})
    registry = TargetRegistry(providers)
    document = target("ECP-TARGET-A1", "ECP-PROVIDER-A")
    document["api_key"] = "synthetic-secret-must-not-be-accepted"
    with pytest.raises(InvalidTarget):
        registry.register(document)
    safe = target("ECP-TARGET-A2", "ECP-PROVIDER-A", credential="ECP-CRED-REF-ONLY")
    registered = registry.register(safe)
    assert registered["credential_ref"] == "ECP-CRED-REF-ONLY"
    assert "api_key" not in registered


def test_provider_adapter_mismatch_and_missing_bindings_rejected():
    providers = ProviderRegistry({"a": provider("ECP-PROVIDER-A"), "b": provider("ECP-PROVIDER-B")})
    registry = TargetRegistry(providers)
    with pytest.raises(InvalidTarget):
        registry.register(target("ECP-TARGET-MISMATCH", "ECP-PROVIDER-A", adapter_provider="ECP-PROVIDER-B"))
    missing = target("ECP-TARGET-MISSING", "ECP-PROVIDER-A")
    missing["test_bindings"] = []
    with pytest.raises(InvalidTarget):
        registry.register(missing)


def test_registry_returns_copies_and_cannot_mutate_stored_target():
    providers = ProviderRegistry({"a": provider("ECP-PROVIDER-A")})
    registry = TargetRegistry(providers)
    registry.register(target("ECP-TARGET-A1", "ECP-PROVIDER-A"))
    returned = registry.get("ECP-TARGET-A1")
    returned["target_version"] = "9.9.9"
    assert registry.get("ECP-TARGET-A1")["target_version"] == "1.0.0"
