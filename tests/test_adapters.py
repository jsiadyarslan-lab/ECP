import copy

import pytest

from ecp import (
    AdapterError,
    AdapterRegistry,
    DuplicateAdapter,
    ProviderRegistry,
    ResolutionError,
    ResolvedTarget,
    TargetRegistry,
    TargetResolver,
    adapter_document,
)
from tests.test_targets import provider, target


def adapter(adapter_id, provider_id="ECP-PROVIDER-A", interface="model-api", *, kinds=None, capabilities=None):
    return adapter_document(
        adapter_id, "1.0.0", provider_id, interface,
        kinds or ["model-only", "complete-system"], capabilities or ["text"],
    )


def setup():
    providers = ProviderRegistry({"a": provider("ECP-PROVIDER-A"), "b": provider("ECP-PROVIDER-B")})
    targets = TargetRegistry(providers)
    adapters = AdapterRegistry()
    return providers, targets, adapters


def register_target(targets, target_id="ECP-TARGET-A1", provider_id="ECP-PROVIDER-A", adapter_id="ECP-ADAPTER-A1", version="1.0.0"):
    document = target(target_id, provider_id)
    document["adapter"] = {"adapter_id": adapter_id, "adapter_version": version, "provider_id": provider_id}
    return targets.register(document)


def test_adapter_contract_and_exact_retrieval():
    registry = AdapterRegistry()
    document = adapter("ECP-ADAPTER-A1")
    registry.register(document)
    assert registry.get("ECP-ADAPTER-A1", "1.0.0") == document
    with pytest.raises(Exception):
        registry.get("ECP-ADAPTER-A1", "2.0.0")


def test_duplicate_adapter_id_and_version_rejected():
    registry = AdapterRegistry()
    registry.register(adapter("ECP-ADAPTER-A1"))
    with pytest.raises(DuplicateAdapter):
        registry.register(adapter("ECP-ADAPTER-A1"))


def test_resolver_accepts_multiple_targets_on_one_adapter():
    providers, targets, adapters = setup()
    adapters.register(adapter("ECP-ADAPTER-A1"))
    register_target(targets, "ECP-TARGET-A1")
    register_target(targets, "ECP-TARGET-A2")
    resolved = TargetResolver(providers, targets, adapters)
    assert isinstance(resolved.resolve("ECP-TARGET-A1"), ResolvedTarget)
    assert resolved.resolve("ECP-TARGET-A2").adapter_id == "ECP-ADAPTER-A1"


def test_resolver_rejects_provider_interface_and_kind_mismatches():
    providers, targets, adapters = setup()
    adapters.register(adapter("ECP-ADAPTER-A1", interface="model-api", kinds=["agent"]))
    register_target(targets, "ECP-TARGET-A1")
    with pytest.raises(ResolutionError):
        TargetResolver(providers, targets, adapters).resolve("ECP-TARGET-A1")


def test_resolver_rejects_unknown_adapter_and_unknown_provider():
    providers, targets, adapters = setup()
    register_target(targets, "ECP-TARGET-A1", adapter_id="ECP-ADAPTER-MISSING")
    with pytest.raises(ResolutionError):
        TargetResolver(providers, targets, adapters).resolve("ECP-TARGET-A1")
    document = target("ECP-TARGET-UNKNOWN", "ECP-PROVIDER-A")
    document["provider"]["provider_id"] = "ECP-PROVIDER-MISSING"
    document["adapter"]["provider_id"] = "ECP-PROVIDER-MISSING"
    # Target registration itself is fail-closed against an unknown provider.
    with pytest.raises(Exception):
        targets.register(document)


def test_resolver_rejects_capability_mismatch_and_does_not_fallback():
    providers, targets, adapters = setup()
    adapters.register(adapter("ECP-ADAPTER-A1", capabilities=["text"]))
    document = target("ECP-TARGET-CAP", "ECP-PROVIDER-A")
    document["required_capabilities"] = ["vision"]
    targets.register(document)
    with pytest.raises(ResolutionError):
        TargetResolver(providers, targets, adapters).resolve("ECP-TARGET-CAP")


def test_resolver_requires_exact_adapter_version():
    providers, targets, adapters = setup()
    adapters.register(adapter("ECP-ADAPTER-A1"))
    register_target(targets, "ECP-TARGET-V2", version="2.0.0")
    with pytest.raises(ResolutionError):
        TargetResolver(providers, targets, adapters).resolve("ECP-TARGET-V2")


def test_inactive_provider_or_adapter_fails_closed():
    providers = ProviderRegistry({"a": provider("ECP-PROVIDER-A")})
    targets = TargetRegistry(providers)
    adapters = AdapterRegistry()
    inactive = provider("ECP-PROVIDER-INACTIVE")
    inactive["status"] = "inactive"
    providers.register(inactive)
    adapters.register(adapter("ECP-ADAPTER-A1"))
    register_target(targets, "ECP-TARGET-A1")
    adapters_inactive = adapter("ECP-ADAPTER-A2")
    adapters_inactive["status"] = "inactive"
    adapters.register(adapters_inactive)
    document = target("ECP-TARGET-A2", "ECP-PROVIDER-A")
    document["adapter"]["adapter_id"] = "ECP-ADAPTER-A2"
    targets.register(document)
    with pytest.raises(ResolutionError):
        TargetResolver(providers, targets, adapters).resolve("ECP-TARGET-A2")


def test_registry_and_resolved_target_never_materialize_secrets():
    providers, targets, adapters = setup()
    adapters.register(adapter("ECP-ADAPTER-A1"))
    document = target("ECP-TARGET-REF", "ECP-PROVIDER-A")
    document["adapter"]["adapter_id"] = "ECP-ADAPTER-A1"
    document["credential_ref"] = "ECP-CRED-REFERENCE-ONLY"
    targets.register(document)
    resolved = TargetResolver(providers, targets, adapters).resolve("ECP-TARGET-REF")
    assert "credential_ref" not in resolved.__dict__
    assert "secret" not in repr(resolved).lower()
    bad = adapter("ECP-ADAPTER-BAD")
    bad["token"] = "must-reject"
    with pytest.raises(AdapterError):
        adapters.register(bad)
