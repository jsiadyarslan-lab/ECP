"""OpenRouter Chat Completions integration boundary.

This provider-specific module contains registration metadata only. Runtime
transport and credential ownership remain behind the controlled gateway.
"""
from __future__ import annotations

from typing import Any

from .adapters import AdapterRegistry, adapter_document
from .targets import ProviderRegistry, provider_document

OPENROUTER_PROVIDER_ID = "ECP-PROVIDER-OPENROUTER"
OPENROUTER_PROVIDER_VERSION = "1.0.0"
OPENROUTER_INTERFACE = "openrouter-chat-completions-api"
OPENROUTER_ADAPTER_ID = "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS"
OPENROUTER_ADAPTER_VERSION = "1.0.0"
OPENROUTER_CREDENTIAL_REF = "ECP-INTEGRATION-CREDENTIAL-OPENROUTER"
OPENROUTER_AUTHORIZATION_REF = "ECP-INTEGRATION-AUTHORIZATION-OPENROUTER"
INTEGRATION_EVALUATION_REF = "ECP-INTEGRATION-EVALUATION-OPENROUTER"
INTEGRATION_TEST_REF = "ECP-INTEGRATION-TEST-OPENROUTER"

_INTEGRATION_TARGET_PREFIX = "ECP-TARGET-INTEGRATION-"
_INTEGRATION_CONFIG_PREFIX = "ECP-CONFIG-INTEGRATION-"


def openrouter_provider() -> dict[str, Any]:
    return provider_document(
        OPENROUTER_PROVIDER_ID,
        OPENROUTER_PROVIDER_VERSION,
        [OPENROUTER_INTERFACE],
        description="OpenRouter Chat Completions provider metadata; transport is external to this integration boundary.",
    )


def openrouter_adapter() -> dict[str, Any]:
    return adapter_document(
        OPENROUTER_ADAPTER_ID,
        OPENROUTER_ADAPTER_VERSION,
        OPENROUTER_PROVIDER_ID,
        OPENROUTER_INTERFACE,
        ["model-only", "complete-system", "agent", "hybrid"],
        ["text-generation"],
    )


def register_openrouter(providers: ProviderRegistry, adapters: AdapterRegistry) -> None:
    providers.register(openrouter_provider())
    adapters.register(openrouter_adapter())


def integration_target(
    target_id: str,
    *,
    configuration_ref: str,
    target_version: str = "1.0.0",
) -> dict[str, Any]:
    if not target_id.startswith(_INTEGRATION_TARGET_PREFIX):
        raise ValueError("integration target_id must use the operational integration prefix")
    if not configuration_ref.startswith(_INTEGRATION_CONFIG_PREFIX):
        raise ValueError("integration configuration_ref must use the operational integration prefix")
    return {
        "ecp_object": "target",
        "target_id": target_id,
        "target_version": target_version,
        "system": {
            "system_id": f"ECP-SYSTEM-INTEGRATION-{target_id[len(_INTEGRATION_TARGET_PREFIX):]}",
            "system_version": "1.0.0",
            "system_kind": "model-only",
            "configuration_ref": configuration_ref,
        },
        "provider": {
            "provider_id": OPENROUTER_PROVIDER_ID,
            "provider_version": OPENROUTER_PROVIDER_VERSION,
            "interface": OPENROUTER_INTERFACE,
        },
        "adapter": {
            "adapter_id": OPENROUTER_ADAPTER_ID,
            "adapter_version": OPENROUTER_ADAPTER_VERSION,
            "provider_id": OPENROUTER_PROVIDER_ID,
        },
        "credential_ref": OPENROUTER_CREDENTIAL_REF,
        "authorization_ref": OPENROUTER_AUTHORIZATION_REF,
        "evaluation_bindings": [INTEGRATION_EVALUATION_REF],
        "test_bindings": [INTEGRATION_TEST_REF],
        "execution_environment": {
            "environment_id": "ecp-openrouter-integration-test",
            "runtime_version": "python>=3.10",
            "network": "disabled",
        },
        "required_capabilities": ["text-generation"],
    }


__all__ = [
    "INTEGRATION_EVALUATION_REF",
    "INTEGRATION_TEST_REF",
    "OPENROUTER_ADAPTER_ID",
    "OPENROUTER_ADAPTER_VERSION",
    "OPENROUTER_AUTHORIZATION_REF",
    "OPENROUTER_CREDENTIAL_REF",
    "OPENROUTER_INTERFACE",
    "OPENROUTER_PROVIDER_ID",
    "OPENROUTER_PROVIDER_VERSION",
    "integration_target",
    "openrouter_adapter",
    "openrouter_provider",
    "register_openrouter",
]
