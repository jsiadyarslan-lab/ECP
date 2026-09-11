"""Explicit OpenRouter conformance wiring for one operational integration target."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from .console import AuthorizedEvaluation, AuthorizedTest, GatewayConfig, LocalGateway
from .credential_binding import AuthorizationGrant, CredentialBinding
from .credentials import CredentialGateway, CredentialIdentity
from .openrouter_adapter import (
    INTEGRATION_EVALUATION_REF,
    INTEGRATION_TEST_REF,
    OPENROUTER_ADAPTER_ID,
    OPENROUTER_AUTHORIZATION_REF,
    OPENROUTER_CREDENTIAL_REF,
    OPENROUTER_INTERFACE,
    OPENROUTER_PROVIDER_ID,
)
from .runtime_adapters import OpenRouterChatCompletionsAdapter, RuntimeAdapterRegistry

OPENROUTER_SYSTEM_ID = "ECP-SYSTEM-INTEGRATION-OPENROUTER"
OPENROUTER_BINDING_ID = "ECP-BIND-INTEGRATION-OPENROUTER"
OPENROUTER_REQUIREMENT_ID = "ECP-REQ-OPENROUTER-INTEGRATION"


def build_openrouter_conformance_gateway(
    config: GatewayConfig,
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> LocalGateway:
    """Build one controlled OpenRouter real-execution gateway."""
    secret = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY")
    if not secret:
        raise RuntimeError("OPENROUTER_API_KEY is required for the conformance execution")
    # HTTP Authorization headers are Latin-1/ASCII constrained. Fail closed
    # before starting the execution surface instead of leaking a low-level
    # UnicodeEncodeError into the browser execution record.
    try:
        secret.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RuntimeError("OPENROUTER_API_KEY must contain only ASCII characters") from exc
    identity = CredentialIdentity(
        OPENROUTER_CREDENTIAL_REF,
        OPENROUTER_PROVIDER_ID,
        "non-scientific integration smoke authorization",
        frozenset({"integration-smoke"}),
    )
    credentials, _store = CredentialGateway.for_testing({identity.credential_id: identity})
    credentials.provision_for_testing(identity.credential_id, secret)
    binding = CredentialBinding(
        OPENROUTER_BINDING_ID,
        OPENROUTER_REQUIREMENT_ID,
        OPENROUTER_SYSTEM_ID,
        OPENROUTER_PROVIDER_ID,
        OPENROUTER_INTERFACE,
        "integration-smoke",
        OPENROUTER_CREDENTIAL_REF,
        frozenset({"integration-smoke"}),
    )
    grant = AuthorizationGrant(
        OPENROUTER_AUTHORIZATION_REF,
        OPENROUTER_BINDING_ID,
        OPENROUTER_SYSTEM_ID,
        "integration-smoke",
        frozenset({"integration-smoke"}),
        (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    evaluation = AuthorizedEvaluation(
        INTEGRATION_EVALUATION_REF,
        OPENROUTER_SYSTEM_ID,
        OPENROUTER_PROVIDER_ID,
        OPENROUTER_ADAPTER_ID,
        identity,
        (AuthorizedTest(INTEGRATION_TEST_REF, "Registered OpenRouter integration conformance probe", "integration-smoke"),),
        binding,
        grant,
    )
    model_name = model or os.environ.get("ECP_OPENROUTER_MODEL", "openrouter/free")
    base = os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1").rstrip("/")
    adapter = OpenRouterChatCompletionsAdapter(
        model=model_name,
        endpoint=f"{base}/chat/completions",
    )
    registry = RuntimeAdapterRegistry({OPENROUTER_ADAPTER_ID: adapter})
    return LocalGateway(config, {evaluation.evaluation_id: evaluation}, credentials, registry)


__all__ = ["OPENROUTER_SYSTEM_ID", "build_openrouter_conformance_gateway"]
