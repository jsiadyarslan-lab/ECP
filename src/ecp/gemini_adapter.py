"""Gemini generateContent integration metadata boundary."""
from __future__ import annotations

from typing import Any

from .adapters import AdapterRegistry, adapter_document
from .targets import ProviderRegistry, TargetRegistry, provider_document

GEMINI_PROVIDER_ID = "ECP-PROVIDER-GEMINI"
GEMINI_PROVIDER_VERSION = "1.0.0"
GEMINI_INTERFACE = "gemini-generate-content-api"
GEMINI_ADAPTER_ID = "ECP-ADAPTER-GEMINI-GENERATE-CONTENT"
GEMINI_ADAPTER_VERSION = "1.0.0"
GEMINI_CREDENTIAL_REF = "ECP-INTEGRATION-CREDENTIAL-GEMINI"
GEMINI_AUTHORIZATION_REF = "ECP-INTEGRATION-AUTHORIZATION-GEMINI"
INTEGRATION_EVALUATION_REF = "ECP-INTEGRATION-EVALUATION-GEMINI"
INTEGRATION_TEST_REF = "ECP-INTEGRATION-TEST-GEMINI"

_INTEGRATION_TARGET_PREFIX = "ECP-TARGET-INTEGRATION-"
_INTEGRATION_CONFIG_PREFIX = "ECP-CONFIG-INTEGRATION-"


def gemini_provider() -> dict[str, Any]:
    return provider_document(
        GEMINI_PROVIDER_ID,
        GEMINI_PROVIDER_VERSION,
        [GEMINI_INTERFACE],
        description="Google Gemini generateContent API provider metadata; transport is external to this integration boundary.",
    )


def gemini_adapter() -> dict[str, Any]:
    return adapter_document(
        GEMINI_ADAPTER_ID,
        GEMINI_ADAPTER_VERSION,
        GEMINI_PROVIDER_ID,
        GEMINI_INTERFACE,
        ["model-only", "complete-system", "agent", "hybrid"],
        ["text-generation"],
    )


def register_gemini(providers: ProviderRegistry, adapters: AdapterRegistry) -> None:
    providers.register(gemini_provider())
    adapters.register(gemini_adapter())


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
            "provider_id": GEMINI_PROVIDER_ID,
            "provider_version": GEMINI_PROVIDER_VERSION,
            "interface": GEMINI_INTERFACE,
        },
        "adapter": {
            "adapter_id": GEMINI_ADAPTER_ID,
            "adapter_version": GEMINI_ADAPTER_VERSION,
            "provider_id": GEMINI_PROVIDER_ID,
        },
        "credential_ref": GEMINI_CREDENTIAL_REF,
        "authorization_ref": GEMINI_AUTHORIZATION_REF,
        "evaluation_bindings": [INTEGRATION_EVALUATION_REF],
        "test_bindings": [INTEGRATION_TEST_REF],
        "execution_environment": {
            "environment_id": "ecp-gemini-integration-test",
            "runtime_version": "python>=3.10",
            "network": "disabled",
        },
        "required_capabilities": ["text-generation"],
    }


__all__ = [
    "GEMINI_ADAPTER_ID",
    "GEMINI_ADAPTER_VERSION",
    "GEMINI_AUTHORIZATION_REF",
    "GEMINI_CREDENTIAL_REF",
    "GEMINI_INTERFACE",
    "GEMINI_PROVIDER_ID",
    "GEMINI_PROVIDER_VERSION",
    "INTEGRATION_EVALUATION_REF",
    "INTEGRATION_TEST_REF",
    "gemini_adapter",
    "gemini_provider",
    "integration_target",
    "register_gemini",
]
