"""Explicit Gemini conformance wiring for one operational integration target."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from .console import AuthorizedEvaluation, AuthorizedTest, GatewayConfig, LocalGateway
from .credential_binding import AuthorizationGrant, CredentialBinding
from .credentials import CredentialGateway, CredentialIdentity
from .gemini_adapter import (
    GEMINI_ADAPTER_ID,
    GEMINI_AUTHORIZATION_REF,
    GEMINI_CREDENTIAL_REF,
    GEMINI_INTERFACE,
    GEMINI_PROVIDER_ID,
    INTEGRATION_EVALUATION_REF,
    INTEGRATION_TEST_REF,
)
from .runtime_adapters import GeminiGenerateContentAdapter, RuntimeAdapterRegistry

GEMINI_SYSTEM_ID = "ECP-SYSTEM-INTEGRATION-GEMINI"
GEMINI_BINDING_ID = "ECP-BIND-INTEGRATION-GEMINI"
GEMINI_REQUIREMENT_ID = "ECP-REQ-GEMINI-INTEGRATION"


def build_gemini_conformance_gateway(
    config: GatewayConfig,
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> LocalGateway:
    """Build one controlled Gemini real-execution gateway."""
    secret = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
    if not secret:
        raise RuntimeError("GEMINI_API_KEY is required for the conformance execution")
    identity = CredentialIdentity(
        GEMINI_CREDENTIAL_REF,
        GEMINI_PROVIDER_ID,
        "non-scientific integration smoke authorization",
        frozenset({"integration-smoke"}),
    )
    credentials, _store = CredentialGateway.for_testing({identity.credential_id: identity})
    credentials.provision_for_testing(identity.credential_id, secret)
    binding = CredentialBinding(
        GEMINI_BINDING_ID,
        GEMINI_REQUIREMENT_ID,
        GEMINI_SYSTEM_ID,
        GEMINI_PROVIDER_ID,
        GEMINI_INTERFACE,
        "integration-smoke",
        GEMINI_CREDENTIAL_REF,
        frozenset({"integration-smoke"}),
    )
    grant = AuthorizationGrant(
        GEMINI_AUTHORIZATION_REF,
        GEMINI_BINDING_ID,
        GEMINI_SYSTEM_ID,
        "integration-smoke",
        frozenset({"integration-smoke"}),
        (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    evaluation = AuthorizedEvaluation(
        INTEGRATION_EVALUATION_REF,
        GEMINI_SYSTEM_ID,
        GEMINI_PROVIDER_ID,
        GEMINI_ADAPTER_ID,
        identity,
        (AuthorizedTest(INTEGRATION_TEST_REF, "Registered Gemini integration conformance probe", "integration-smoke"),),
        binding,
        grant,
    )
    model_name = model or os.environ.get("ECP_GEMINI_MODEL", "gemini-3.8-flash")
    base = os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    adapter = GeminiGenerateContentAdapter(
        model=model_name,
        endpoint=f"{base}/models/{model_name}:generateContent",
    )
    registry = RuntimeAdapterRegistry({GEMINI_ADAPTER_ID: adapter})
    return LocalGateway(config, {evaluation.evaluation_id: evaluation}, credentials, registry)


__all__ = ["GEMINI_SYSTEM_ID", "build_gemini_conformance_gateway"]
