"""OpenAI Responses API integration boundary.

This module is intentionally provider-specific and must be imported explicitly;
it is not part of the public provider-neutral ECP core API. It contains only
registration metadata and a non-scientific integration fixture. It performs no
transport, SDK, credential access, authorization decision, or evaluation.
"""

from __future__ import annotations

from typing import Any

from .adapters import AdapterRegistry, adapter_document
from .targets import ProviderRegistry, TargetRegistry, provider_document

OPENAI_PROVIDER_ID = "ECP-PROVIDER-OPENAI"
OPENAI_PROVIDER_VERSION = "1.0.0"
OPENAI_INTERFACE = "openai-responses-api"
OPENAI_ADAPTER_ID = "ECP-ADAPTER-OPENAI-RESPONSES"
OPENAI_ADAPTER_VERSION = "1.0.0"
OPENAI_CREDENTIAL_REF = "ECP-INTEGRATION-CREDENTIAL-OPENAI"
OPENAI_AUTHORIZATION_REF = "ECP-INTEGRATION-AUTHORIZATION-OPENAI"
INTEGRATION_EVALUATION_REF = "ECP-INTEGRATION-EVALUATION-OPENAI"
INTEGRATION_TEST_REF = "ECP-INTEGRATION-TEST-OPENAI"

_INTEGRATION_TARGET_PREFIX = "ECP-TARGET-INTEGRATION-"
_INTEGRATION_CONFIG_PREFIX = "ECP-CONFIG-INTEGRATION-"


def openai_provider() -> dict[str, Any]:
    """Return non-secret metadata for the OpenAI Responses interface."""
    return provider_document(
        OPENAI_PROVIDER_ID,
        OPENAI_PROVIDER_VERSION,
        [OPENAI_INTERFACE],
        description="OpenAI Responses API provider metadata; transport is external to this integration boundary.",
    )


def openai_adapter() -> dict[str, Any]:
    """Return the transport-independent OpenAI adapter contract."""
    return adapter_document(
        OPENAI_ADAPTER_ID,
        OPENAI_ADAPTER_VERSION,
        OPENAI_PROVIDER_ID,
        OPENAI_INTERFACE,
        ["model-only", "complete-system", "agent", "hybrid"],
        ["text-generation"],
    )


def register_openai(
    providers: ProviderRegistry,
    adapters: AdapterRegistry,
) -> None:
    """Explicitly register the OpenAI provider and adapter in supplied registries.

    This is an integration extension hook. It does not create a global registry,
    perform network I/O, access credentials, or authorize execution.
    """
    providers.register(openai_provider())
    adapters.register(openai_adapter())


def integration_target(
    target_id: str,
    *,
    configuration_ref: str,
    target_version: str = "1.0.0",
) -> dict[str, Any]:
    """Build a non-scientific integration target with operational-only identities."""
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
            "provider_id": OPENAI_PROVIDER_ID,
            "provider_version": OPENAI_PROVIDER_VERSION,
            "interface": OPENAI_INTERFACE,
        },
        "adapter": {
            "adapter_id": OPENAI_ADAPTER_ID,
            "adapter_version": OPENAI_ADAPTER_VERSION,
            "provider_id": OPENAI_PROVIDER_ID,
        },
        "credential_ref": OPENAI_CREDENTIAL_REF,
        "authorization_ref": OPENAI_AUTHORIZATION_REF,
        "evaluation_bindings": [INTEGRATION_EVALUATION_REF],
        "test_bindings": [INTEGRATION_TEST_REF],
        "execution_environment": {
            "environment_id": "ecp-openai-integration-test",
            "runtime_version": "python>=3.10",
            "network": "disabled",
        },
        "required_capabilities": ["text-generation"],
    }


__all__ = [
    "INTEGRATION_EVALUATION_REF",
    "INTEGRATION_TEST_REF",
    "OPENAI_ADAPTER_ID",
    "OPENAI_ADAPTER_VERSION",
    "OPENAI_AUTHORIZATION_REF",
    "OPENAI_CREDENTIAL_REF",
    "OPENAI_INTERFACE",
    "OPENAI_PROVIDER_ID",
    "OPENAI_PROVIDER_VERSION",
    "integration_target",
    "openai_adapter",
    "openai_provider",
    "register_openai",
]
