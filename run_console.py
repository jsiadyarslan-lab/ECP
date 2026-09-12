"""Universal, configuration-driven evaluation console entry (v1).

ONE launcher for every target. It reads an onboarding configuration (JSON),
onboards every declared target through the universal onboarding fabric
(``ecp.onboarding.TargetOnboardingService`` — which composes the existing
provider/target/adapter registries, credential gateway, resolver and
execution contract), and then serves the EXISTING evaluation console and the
EXISTING local gateway endpoint. No per-provider launcher is needed for a new
target: a new target is a configuration entry plus an already-registered
provider adapter.

    Target configuration (JSON)
        -> validation -> provider resolution -> adapter resolution
        -> credential resolution -> authorization resolution
        -> readiness -> infrastructure registration -> persisted record
        -> LocalGateway (existing endpoint 127.0.0.1:8765)
        -> console/ (existing static UI, dynamic /api/v1/catalog)

Built-in adapter kinds ONLY — the configuration selects an adapter kind by
name; there is no dynamic import of configured modules or classes, so a
configuration can never trigger arbitrary code execution:

    offline-mock                  deterministic offline reply (no network)
    openai-responses              OpenAI Responses API adapter (real calls;
                                  requires the separately authorized real
                                  external evaluation phase)
    gemini-generate-content       Gemini generateContent adapter (real; same gate)
    openrouter-chat-completions   generic OpenAI-compatible chat-completions
                                  adapter (real; same gate). Optional
                                  provider-neutral gateway knobs from the
                                  target entry: ``token_header`` (header name
                                  that carries the credential lease),
                                  ``bearer_value`` (non-secret literal sent
                                  as the bearer credential when token_header
                                  is used) and ``extra_headers`` (additional
                                  static non-secret routing headers).

Secrets are read ONLY from environment variables into the credential
gateway's private store (existing boundary); they never appear in the
configuration file, the registries, the onboarding records, the browser
payload, evidence or audit.

Usage:
    python run_console.py [--config onboarding-config.json]
                          [--gateway-port 8765] [--console-port 8766]
                          [--artifact-root DIR]

Without ``--config`` a built-in OFFLINE demo configuration is served: one
synthetic offline-mock target, zero network calls, zero real providers.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets as pysecrets
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent
CONSOLE_PORT = 8766
GATEWAY_PORT = 8765
ARTIFACT_ROOT = REPO_ROOT / "local-browser-artifacts"

sys.path.insert(0, str(REPO_ROOT / "src"))

from ecp.console import GatewayConfig, LocalGateway  # noqa: E402
from ecp.credential_binding import AuthorizationGrant, CredentialBinding  # noqa: E402
from ecp.credentials import CredentialGateway, CredentialIdentity, SecretStore  # noqa: E402
from ecp.onboarding import TargetOnboardingService  # noqa: E402
from ecp.runtime_adapters import (  # noqa: E402
    GeminiGenerateContentAdapter,
    OpenAIResponsesAdapter,
    OpenRouterChatCompletionsAdapter,
    RuntimeAdapterRegistry,
)
from ecp.adapters import AdapterRegistry  # noqa: E402
from ecp.targets import ProviderRegistry, TargetRegistry  # noqa: E402
from ecp.console import AuthorizedTest  # noqa: E402


class OfflineMockAdapter:
    """Deterministic offline conformance adapter: no transport, no network.

    Returns a fixed provider payload through the same universal adapter
    contract used by real providers, so the full execution path (intent ->
    resolution -> lease -> adapter -> universal result -> evidence -> audit)
    can be exercised with zero external calls.
    """

    provider = "unconfigured"
    adapter_id = "unconfigured"

    def __init__(self, *, model: str, provider: str, adapter_id: str,
                 reply: str = "ECP-CONFORMANCE-OK") -> None:
        if not model or not provider or not adapter_id:
            raise ValueError("offline-mock adapter requires model, provider and adapter_id")
        self.model = model
        self.provider = provider
        self.adapter_id = adapter_id
        self.reply = reply or "ECP-CONFORMANCE-OK"

    def execute(self, lease: Any, request: Mapping[str, str]) -> Mapping[str, Any]:
        return {
            "provider_status": "RECEIVED",
            "response_id": f"offline-{request['request_id']}",
            "model": self.model,
            "output_text": self.reply,
            "request_id": request["request_id"],
        }


#: Built-in adapter kinds. The configuration selects a kind BY NAME; unknown
#: kinds are rejected deterministically (no dynamic imports, no arbitrary
#: code execution from configuration).
BUILTIN_ADAPTER_KINDS = frozenset({
    "offline-mock",
    "openai-responses",
    "gemini-generate-content",
    "openrouter-chat-completions",
})

_REAL_KIND_ENV = {
    "openai-responses": "OPENAI_API_KEY",
    "gemini-generate-content": "GEMINI_API_KEY",
    "openrouter-chat-completions": "OPENROUTER_API_KEY",
}

#: Built-in OFFLINE demonstration configuration (zero network, zero real
#: providers; the shipped default for this phase — real external provider
#: execution is a separately authorized phase).
BUILTIN_DEMO_CONFIGURATION: dict[str, Any] = {
    "configuration_version": "1.0.0",
    "note": "FORMAT EXAMPLE — built-in offline demonstration configuration "
            "(universal target onboarding; no real provider, no network).",
    "providers": [
        {
            "ecp_object": "provider",
            "provider_id": "ECP-PROVIDER-DEMO-OFFLINE",
            "provider_version": "1.0.0",
            "interfaces": ["offline-conformance"],
            "status": "active",
            "description": "Offline demonstration provider; deterministic mock transport.",
        }
    ],
    "adapters": [
        {
            "ecp_object": "adapter",
            "adapter_id": "ECP-ADAPTER-DEMO-OFFLINE",
            "adapter_version": "1.0.0",
            "provider_id": "ECP-PROVIDER-DEMO-OFFLINE",
            "provider_interface": "offline-conformance",
            "supported_system_kinds": ["model-only"],
            "supported_capabilities": ["text-generation"],
            "status": "active",
        }
    ],
    "credentials": [
        {
            "credential_id": "ECP-DEMO-CREDENTIAL-OFFLINE",
            "provider": "ECP-PROVIDER-DEMO-OFFLINE",
            "purpose": "offline demonstration smoke",
            "scope": ["offline-smoke"],
            "secret_environment_variable": None,
        }
    ],
    "targets": [
        {
            "target": {
                "ecp_object": "target",
                "target_id": "ECP-TARGET-DEMO-OFFLINE-1",
                "target_version": "1.0.0",
                "system": {
                    "system_id": "ECP-SYSTEM-DEMO-OFFLINE-1",
                    "system_version": "1.0.0",
                    "system_kind": "model-only",
                    "configuration_ref": None,
                },
                "provider": {
                    "provider_id": "ECP-PROVIDER-DEMO-OFFLINE",
                    "provider_version": "1.0.0",
                    "interface": "offline-conformance",
                },
                "adapter": {
                    "adapter_id": "ECP-ADAPTER-DEMO-OFFLINE",
                    "adapter_version": "1.0.0",
                    "provider_id": "ECP-PROVIDER-DEMO-OFFLINE",
                },
                "credential_ref": "ECP-DEMO-CREDENTIAL-OFFLINE",
                "authorization_ref": "ECP-AUTH-DEMO-OFFLINE-1",
                "evaluation_bindings": ["ECP-EVAL-DEMO-OFFLINE-1"],
                "test_bindings": ["ECP-TEST-DEMO-OFFLINE-1"],
                "execution_environment": {
                    "environment_id": "offline-demo",
                    "runtime_version": "python>=3.10",
                    "network": "disabled",
                },
                "required_capabilities": ["text-generation"],
            },
            "adapter_kind": "offline-mock",
            "model": "offline-demo-model-1",
            "reply": "ECP-CONFORMANCE-OK",
            "binding": {
                "binding_id": "ECP-BIND-DEMO-OFFLINE-1",
                "requirement_id": "ECP-REQ-DEMO-OFFLINE-1",
                "target_id": "ECP-TARGET-DEMO-OFFLINE-1",
                "provider_id": "ECP-PROVIDER-DEMO-OFFLINE",
                "interface": "offline-conformance",
                "purpose": "offline-smoke",
                "credential_ref": "ECP-DEMO-CREDENTIAL-OFFLINE",
                "scope": ["offline-smoke"],
            },
            "grant": {
                "authorization_ref": "ECP-AUTH-DEMO-OFFLINE-1",
                "binding_id": "ECP-BIND-DEMO-OFFLINE-1",
                "target_id": "ECP-TARGET-DEMO-OFFLINE-1",
                "purpose": "offline-smoke",
                "scope": ["offline-smoke"],
                "expires_at": "2099-01-01T00:00:00Z",
            },
            "tests": [
                {
                    "test_id": "ECP-TEST-DEMO-OFFLINE-1",
                    "label": "Offline demonstration conformance probe",
                    "scope": "offline-smoke",
                }
            ],
        }
    ],
}


class _ConfigurationSecretStore(SecretStore):
    """Launcher-level secret store over the existing SecretStore seam.

    Resolves each configured credential from its declared environment
    variable (real kinds) or holds a generated synthetic value (offline-mock
    credentials). Secret values never leave this store except through the
    credential gateway's authorized release.
    """

    def __init__(self, sources: Mapping[str, "tuple[str | None, str]"]) -> None:
        # credential_id -> (environment variable or None, synthetic fallback)
        self._sources = dict(sources)

    def _read(self, credential_id: str, version: str) -> "str | None":
        del version
        entry = self._sources.get(credential_id)
        if entry is None:
            return None
        variable, synthetic = entry
        if variable is not None:
            return os.environ.get(variable)
        return synthetic

    def _write(self, credential_id: str, version: str, secret: str) -> None:
        raise PermissionError("configuration secret store is read-only")

    def _delete(self, credential_id: str, version: str) -> None:
        raise PermissionError("configuration secret store is read-only")


def load_configuration(path: "str | Path | None") -> dict[str, Any]:
    """Load an onboarding configuration (built-in offline demo by default)."""
    if path is None:
        return json.loads(json.dumps(BUILTIN_DEMO_CONFIGURATION))
    with open(Path(path), "r", encoding="utf-8") as fh:
        configuration = json.load(fh)
    if not isinstance(configuration, dict):
        raise ValueError("onboarding configuration must be a JSON object")
    return configuration


def _require_keys(section: str, document: Mapping[str, Any], keys: "tuple[str, ...]") -> None:
    missing = [key for key in keys if key not in document]
    if missing:
        raise ValueError(f"{section}: missing required keys: {', '.join(missing)}")


def _build_runtime_adapter(entry: Mapping[str, Any], target: Mapping[str, Any]) -> Any:
    """Build the runtime adapter instance for one target entry (by kind).

    Only built-in kinds are constructible; anything else — including module
    paths, class names or shell fragments — is rejected deterministically.

    The ``openrouter-chat-completions`` kind (the generic OpenAI-compatible
    chat-completions dialect) additionally accepts three OPTIONAL
    provider-neutral gateway knobs read straight from configuration:
    ``token_header``, ``bearer_value`` and ``extra_headers``. They exist so
    that chat-completions gateways which place the credential in a custom
    header and/or require additional static non-secret routing headers can be
    onboarded through configuration alone — no source-code change per target.
    All values are non-secret; the secret continues to flow only through the
    credential gateway's environment-variable store.
    """
    kind = entry.get("adapter_kind")
    if not isinstance(kind, str) or kind not in BUILTIN_ADAPTER_KINDS:
        raise ValueError(
            f"unknown adapter kind {kind!r}; built-in kinds: "
            + ", ".join(sorted(BUILTIN_ADAPTER_KINDS))
        )
    model = entry.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("target entry requires a non-empty 'model' configuration")
    provider = target["provider"]["provider_id"]
    adapter_id = target["adapter"]["adapter_id"]
    endpoint = entry.get("endpoint")
    if kind == "offline-mock":
        reply = entry.get("reply", "ECP-CONFORMANCE-OK")
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("offline-mock 'reply' must be a non-empty string")
        return OfflineMockAdapter(model=model, provider=provider, adapter_id=adapter_id, reply=reply)
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError(f"adapter kind {kind!r} requires a non-empty 'endpoint'")
    if kind == "openai-responses":
        return OpenAIResponsesAdapter(model=model, endpoint=endpoint, provider=provider, adapter_id=adapter_id)
    if kind == "gemini-generate-content":
        return GeminiGenerateContentAdapter(model=model, endpoint=endpoint, provider=provider, adapter_id=adapter_id)
    # kind == "openrouter-chat-completions": the generic chat-completions
    # dialect; optional non-secret gateway-header knobs from configuration.
    token_header = entry.get("token_header")
    if token_header is not None and not isinstance(token_header, str):
        raise ValueError("'token_header' must be a header-name string or null")
    bearer_value = entry.get("bearer_value")
    if bearer_value is not None and not isinstance(bearer_value, str):
        raise ValueError("'bearer_value' must be a non-secret string or null")
    extra_headers = entry.get("extra_headers")
    if extra_headers is not None and not isinstance(extra_headers, dict):
        raise ValueError("'extra_headers' must be an object of non-secret header values or null")
    return OpenRouterChatCompletionsAdapter(
        model=model,
        endpoint=endpoint,
        provider=provider,
        adapter_id=adapter_id,
        token_header=token_header,
        bearer_value=bearer_value,
        extra_headers=extra_headers,
    )


def build_gateway(
    configuration: Mapping[str, Any],
    gateway_config: GatewayConfig,
) -> "tuple[LocalGateway, TargetOnboardingService]":
    """Onboard every configured target and build the existing LocalGateway.

    The gateway is the SAME universal execution path (single endpoint,
    existing console contract); only its evaluation registry is populated —
    dynamically, from configuration, through the onboarding fabric.
    """
    providers = ProviderRegistry()
    targets = TargetRegistry(providers)
    adapters = AdapterRegistry()
    runtime = RuntimeAdapterRegistry()

    # --- credentials (references + env-var sources only) ---------------
    identities: dict[str, CredentialIdentity] = {}
    sources: dict[str, "tuple[str | None, str]"] = {}
    for entry in configuration.get("credentials", []) or []:
        _require_keys("credentials entry", entry, ("credential_id", "provider", "purpose", "scope"))
        variable = entry.get("secret_environment_variable")
        if variable is not None and not isinstance(variable, str):
            raise ValueError("secret_environment_variable must be a string or null")
        credential_id = entry["credential_id"]
        identities[credential_id] = CredentialIdentity(
            credential_id,
            entry["provider"],
            entry["purpose"],
            frozenset(entry["scope"]),
        )
        # Offline credentials (no environment variable) get a generated
        # synthetic value that is never printed, persisted or exposed.
        sources[credential_id] = (variable, pysecrets.token_urlsafe(32))
    # Fail closed BEFORE any wiring: a real-provider credential whose
    # environment variable is absent makes the whole launch fail
    # deterministically (real external execution is a separately authorized
    # phase and never silently degrades).
    for credential_id, (variable, _synthetic) in sources.items():
        if variable is not None and not os.environ.get(variable):
            raise RuntimeError(
                f"environment variable {variable} is required for credential "
                f"{credential_id} (real provider execution is a separately "
                "authorized phase)"
            )
    credential_gateway = CredentialGateway(_ConfigurationSecretStore(sources), identities)

    service = TargetOnboardingService(
        providers, targets, adapters, runtime, credential_gateway
    )

    # --- provider + adapter metadata registration -----------------------
    # Registries start empty in this launcher; the registries' own register
    # seams perform full contract validation with deterministic errors.
    for provider_entry in configuration.get("providers", []) or []:
        providers.register(dict(provider_entry))
    for adapter_entry in configuration.get("adapters", []) or []:
        adapters.register(dict(adapter_entry))

    # --- target onboarding ----------------------------------------------
    for entry in configuration.get("targets", []) or []:
        _require_keys("target entry", entry, ("target", "adapter_kind", "model", "binding", "grant", "tests"))
        target = entry["target"]
        binding_entry = entry["binding"]
        _require_keys("binding", binding_entry, ("binding_id", "requirement_id", "target_id", "provider_id", "interface", "purpose", "credential_ref", "scope"))
        binding = CredentialBinding(
            binding_entry["binding_id"],
            binding_entry["requirement_id"],
            binding_entry["target_id"],
            binding_entry["provider_id"],
            binding_entry["interface"],
            binding_entry["purpose"],
            binding_entry["credential_ref"],
            frozenset(binding_entry["scope"]),
        )
        grant_entry = entry["grant"]
        _require_keys("grant", grant_entry, ("authorization_ref", "binding_id", "target_id", "purpose", "scope", "expires_at"))
        grant = AuthorizationGrant(
            grant_entry["authorization_ref"],
            grant_entry["binding_id"],
            grant_entry["target_id"],
            grant_entry["purpose"],
            frozenset(grant_entry["scope"]),
            grant_entry["expires_at"],
        )
        tests = {
            test_entry["test_id"]: AuthorizedTest(
                test_entry["test_id"], test_entry["label"], test_entry["scope"]
            )
            for test_entry in entry["tests"]
        }
        runtime_adapter = _build_runtime_adapter(entry, target)
        service.onboard(
            target,
            runtime_adapter=runtime_adapter,
            credential_identity=identities[target["credential_ref"]],
            binding=binding,
            grant=grant,
            tests=tests,
        )

    gateway = LocalGateway(
        gateway_config,
        service.evaluations,
        credential_gateway,
        runtime,
    )
    return gateway, service


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description="Universal configuration-driven ECP evaluation console "
                    "(offline by default; real providers require the "
                    "separately authorized real external evaluation phase)"
    )
    parser.add_argument("--config", default=None, help="onboarding configuration JSON path")
    parser.add_argument("--gateway-port", type=int, default=GATEWAY_PORT)
    parser.add_argument("--console-port", type=int, default=CONSOLE_PORT)
    parser.add_argument("--artifact-root", default=None, help="execution artifact root")
    args = parser.parse_args(argv)

    configuration = load_configuration(args.config)
    config = GatewayConfig(
        allowed_origins=frozenset({
            f"http://127.0.0.1:{args.console_port}",
            f"http://localhost:{args.console_port}",
        }),
        port=args.gateway_port,
        artifact_root=Path(args.artifact_root) if args.artifact_root else ARTIFACT_ROOT,
    )
    gateway, service = build_gateway(configuration, config)

    gateway_server = gateway.make_server()
    threading.Thread(target=gateway_server.serve_forever, daemon=True).start()

    onboarded = len(service.evaluations)
    print(f"ECP universal gateway listening on 127.0.0.1:{config.port}")
    print(f"Onboarded targets (configuration-driven): {onboarded}")
    print(f"PAIRING CODE: {gateway.pairing_code}")
    print(f"Console: http://127.0.0.1:{args.console_port}/")
    print("Press Ctrl+C to stop.")

    os.chdir(REPO_ROOT / "console")
    console_server = ThreadingHTTPServer(
        ("127.0.0.1", args.console_port),
        SimpleHTTPRequestHandler,
    )
    try:
        console_server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        console_server.server_close()
        gateway_server.shutdown()
        gateway_server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
