"""OpenAI Responses API adapter metadata boundary.

This module deliberately contains no transport, SDK, credential access,
authorization decision, or evaluation logic. It supplies provider-specific
metadata and a non-scientific integration-target fixture for the generic ECP
registries and resolver.
"""

from __future__ import annotations

from typing import Any

from .adapters import adapter_document
from .targets import provider_document

OPENAI_PROVIDER_ID = "ECP-PROVIDER-OPENAI"
OPENAI_PROVIDER_VERSION = "1.0.0"
OPENAI_INTERFACE = "openai-responses-api"
OPENAI_ADAPTER_ID = "ECP-ADAPTER-OPENAI-RESPONSES"
OPENAI_ADAPTER_VERSION = "1.0.0"
OPENAI_CREDENTIAL_REF = "ECP-CRED-OPENAI-INTEGRATION-REF"
OPENAI_AUTHORIZATION_REF = "ECP-AUTH-OPENAI-INTEGRATION-TEST"
INTEGRATION_EVALUATION_REF = "ECP-EVAL-INTEGRATION-ONLY"
INTEGRATION_TEST_REF = "ECP-TEST-INTEGRATION-ONLY"


def openai_provider() -> dict[str, Any]:
    """Return non-secret metadata for the OpenAI Responses interface."""
    return provider_document(
        OPENAI_PROVIDER_ID,
        OPENAI_PROVIDER_VERSION,
        [OPENAI_INTERFACE],
        description="OpenAI Responses API provider metadata; transport is external to this foundation.",
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


def integration_target(
    target_id: str,
    *,
    configuration_ref: str,
    target_version: str = "1.0.0",
) -> dict[str, Any]:
    """Build a clearly non-scientific target for registry/resolution tests.

    ``configuration_ref`` is an opaque reference to a later model/configuration
    record. It is intentionally not a model name, credential, or secret.
    """
    return {
        "ecp_object": "target",
        "target_id": target_id,
        "target_version": target_version,
        "system": {
            "system_id": f"ECP-SYSTEM-INTEGRATION-{target_id.rsplit('-', 1)[-1]}",
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
]
