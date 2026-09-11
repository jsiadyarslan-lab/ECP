"""Explicit first-provider conformance wiring for one operational integration target."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from .console import AuthorizedEvaluation, AuthorizedTest, GatewayConfig, LocalGateway
from .credential_binding import AuthorizationGrant, CredentialBinding
from .credentials import CredentialGateway, CredentialIdentity
from .openai_adapter import (
    INTEGRATION_EVALUATION_REF,
    INTEGRATION_TEST_REF,
    OPENAI_ADAPTER_ID,
    OPENAI_AUTHORIZATION_REF,
    OPENAI_CREDENTIAL_REF,
    OPENAI_INTERFACE,
    OPENAI_PROVIDER_ID,
)
from .runtime_adapters import OpenAIResponsesAdapter, RuntimeAdapterRegistry

OPENAI_SYSTEM_ID = "ECP-SYSTEM-INTEGRATION-A"
OPENAI_BINDING_ID = "ECP-BIND-INTEGRATION-OPENAI"
OPENAI_REQUIREMENT_ID = "ECP-REQ-OPENAI-INTEGRATION"


def build_openai_conformance_gateway(
    config: GatewayConfig,
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> LocalGateway:
    """Build one controlled, non-scientific real-execution gateway.

    The API key is read only into the private test credential store and is never
    returned by this function or included in any registry, request, record, or
    browser payload.
    """
    secret = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
    if not secret:
        raise RuntimeError("OPENAI_API_KEY is required for the conformance execution")
    identity = CredentialIdentity(
        OPENAI_CREDENTIAL_REF,
        OPENAI_PROVIDER_ID,
        "non-scientific integration smoke authorization",
        frozenset({"integration-smoke"}),
    )
    credentials, _store = CredentialGateway.for_testing({identity.credential_id: identity})
    credentials.provision_for_testing(identity.credential_id, secret)
    binding = CredentialBinding(
        OPENAI_BINDING_ID,
        OPENAI_REQUIREMENT_ID,
        OPENAI_SYSTEM_ID,
        OPENAI_PROVIDER_ID,
        OPENAI_INTERFACE,
        "integration-smoke",
        OPENAI_CREDENTIAL_REF,
        frozenset({"integration-smoke"}),
    )
    grant = AuthorizationGrant(
        OPENAI_AUTHORIZATION_REF,
        OPENAI_BINDING_ID,
        OPENAI_SYSTEM_ID,
        "integration-smoke",
        frozenset({"integration-smoke"}),
        (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    evaluation = AuthorizedEvaluation(
        INTEGRATION_EVALUATION_REF,
        OPENAI_SYSTEM_ID,
        OPENAI_PROVIDER_ID,
        OPENAI_ADAPTER_ID,
        identity,
        (AuthorizedTest(INTEGRATION_TEST_REF, "Registered OpenAI integration conformance probe", "integration-smoke"),),
        binding,
        grant,
    )
    adapter = OpenAIResponsesAdapter(model=model or os.environ.get("ECP_CONFORMANCE_MODEL", "gpt-5-mini"), endpoint=f"{os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1').rstrip('/')}/responses")
    registry = RuntimeAdapterRegistry({OPENAI_ADAPTER_ID: adapter})
    return LocalGateway(config, {evaluation.evaluation_id: evaluation}, credentials, registry)


__all__ = ["OPENAI_SYSTEM_ID", "build_openai_conformance_gateway"]
