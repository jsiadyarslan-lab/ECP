"""Universal console credential sessions & discovery orchestration v1.

Composition layer for the UNIVERSAL VISUAL PROVIDER & MODEL EVALUATION
CONSOLE (owner order 2026-09-12). It owns NO new authority:

* the owner-submitted credential value enters ONLY through
  :class:`SessionCredentialGateway` — a subclass of the EXISTING
  :class:`ecp.credentials.CredentialGateway` — and is releasable ONLY
  through the existing ``release()`` path with real bindings and grants
  (never through a parallel secret path);
* provider/model identification flows ONLY through the unified discovery
  service (:mod:`ecp.discovery`) using a gateway-released lease;
* model selection produces a plain TARGET CONFIGURATION which is onboarded
  through the EXISTING :class:`ecp.onboarding.TargetOnboardingService`
  (validation, registries, resolver, readiness battery, freeze);
* execution is NOT implemented here at all: the console registers the
  onboarded evaluation on the existing :class:`ecp.console.LocalGateway`
  and every run flows through the single existing ``/api/v1/executions``
  contract with its evidence/audit/persistence writers.

Session lifecycle:

    owner submits credential (browser -> loopback gateway, once)
        -> SessionCredentialGateway.open_session: in-process protected
           store + identity + discovery binding/grant (session TTL)
        -> returns credential_ref ONLY (a session handle; the value is
           never echoed, logged or persisted)
        -> discovery probes release the lease through release()
        -> on identification the identity is re-bound to the discovered
           provider and its scope is expanded to evaluation scope
        -> model selection builds the target configuration and onboards it
        -> execution flows through the existing universal path
"""

from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .console import AuthorizedTest, LocalGateway
from .credential_binding import AuthorizationGrant, CredentialBinding, ScopedReleaseRequest
from .credentials import CredentialGateway, CredentialIdentity, SecretLease, SecretRedactionFilter, SecretStore
from .discovery import DiscoveryReport, ProviderDiscoveryService, STATUS_DISCOVERED
from .hashing import hash_document
from .onboarding import TargetOnboardingService

#: Provider identity of an unbound session credential (pre-discovery).
SESSION_PROVIDER_ID = "ECP-PROVIDER-OWNER-SESSION"

#: Default session lifetime (seconds) for owner-entered credentials.
DEFAULT_SESSION_TTL_SECONDS = 28800

#: Discovery purpose/scope for the pre-onboarding release path.
DISCOVERY_PURPOSE = "provider-discovery"

#: Evaluation purpose/scope for session-onboarded targets.
EVALUATION_PURPOSE = "conformance-evaluation"

#: The submitted credential must be printable ASCII without whitespace
#: (it is placed in HTTP headers; this also blocks header injection).
_SESSION_SECRET = re.compile(r"[!-~]{8,4096}")

_PROVIDER_ID = re.compile(r"^ECP-PROVIDER-[A-Za-z0-9][A-Za-z0-9._:-]*$")

_CREDENTIAL_REF = re.compile(r"^ECP-[A-Z0-9][A-Z0-9._:-]*$")

_SESSION_ENVIRONMENT = {
    "environment_id": "ecp-owner-console-session",
    "runtime_version": "python>=3.10",
    "network": "controlled",
}


class SessionConsoleError(ValueError):
    """Deterministic, diagnostic session-console failure (secret-free)."""


class SessionCredentialGateway(CredentialGateway):
    """The existing credential gateway extended with owner console sessions.

    The store seam composes an in-process session store in front of the
    launcher's backing store, so configuration credentials (environment
    variables) and session credentials (owner-entered) are releasable
    through the SAME gateway and the SAME ``release()`` discipline. The
    session store holds values in process memory only: never written to
    disk, never serialized, never stringified.
    """

    def __init__(self, backing_store: SecretStore, identities: Mapping[str, CredentialIdentity]) -> None:
        self._session_values = _SessionSecretStore()
        self._session_lock = threading.RLock()
        self._sessions: dict[str, _SessionState] = {}
        super().__init__(_CompositeSecretStore(self._session_values, backing_store), identities)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def open_session(
        self,
        credential_secret: Any,
        *,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Accept one owner-submitted credential and return the session handle.

        Returns the credential reference and expiry ONLY. The value goes
        into the in-process protected store; it is never echoed, logged or
        persisted anywhere.
        """
        if not isinstance(credential_secret, str) or not _SESSION_SECRET.fullmatch(credential_secret):
            raise SessionConsoleError(
                "credential secret must be 8-4096 printable ASCII characters without whitespace"
            )
        if not isinstance(ttl_seconds, int) or not 60 <= ttl_seconds <= 86400:
            raise SessionConsoleError("session ttl must be between 60 and 86400 seconds")
        current = now or datetime.now(timezone.utc)
        expires_at = (
            current.astimezone(timezone.utc) + _ttl_delta(ttl_seconds)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        credential_id = "ECP-SESSION-CREDENTIAL-" + uuid.uuid4().hex[:16].upper()
        identity = CredentialIdentity(
            credential_id,
            SESSION_PROVIDER_ID,
            "owner console session credential",
            frozenset({DISCOVERY_PURPOSE}),
            expires_at=expires_at,
        )
        binding, grant = _discovery_binding_grant(credential_id, SESSION_PROVIDER_ID, expires_at)
        with self._session_lock:
            self._identities[credential_id] = identity
            self._session_values.write(credential_id, identity.version, credential_secret)
            self._sessions[credential_id] = _SessionState(
                credential_id=credential_id,
                identity=identity,
                discovery_binding=binding,
                discovery_grant=grant,
                expires_at=expires_at,
            )
        return {
            "credential_ref": credential_id,
            "session_provider": SESSION_PROVIDER_ID,
            "status": "OPEN",
            "expires_at": expires_at,
            "storage": "in-process protected store (never persisted, never echoed)",
        }

    def discovery_lease(
        self, credential_ref: str, *, request_id: str, now: datetime | None = None
    ) -> SecretLease:
        """Release the discovery-scoped lease through the EXISTING release path."""
        state = self._require_session(credential_ref)
        request = ScopedReleaseRequest(
            request_id=request_id,
            binding_id=state.discovery_binding.binding_id,
            target_id=state.discovery_binding.target_id,
            credential_ref=credential_ref,
            purpose=DISCOVERY_PURPOSE,
            scope=frozenset({DISCOVERY_PURPOSE}),
            lease_seconds=60,
            requested_at=_iso(now or datetime.now(timezone.utc)),
        )
        return self.release(request, state.discovery_binding, state.discovery_grant, now=now)

    def bind_discovered_provider(
        self, credential_ref: str, provider_id: str
    ) -> CredentialIdentity:
        """Re-bind the session identity to the DISCOVERED provider.

        Called only after a successful identification. The credential
        value never moves; only the non-secret identity record gains the
        discovered provider binding and the evaluation scope, and the
        discovery binding/grant are regenerated under the discovered
        provider so re-discovery keeps releasing through ``release()``.
        """
        if not isinstance(provider_id, str) or not _PROVIDER_ID.fullmatch(provider_id):
            raise SessionConsoleError("discovered provider id is invalid")
        state = self._require_session(credential_ref)
        identity = CredentialIdentity(
            credential_ref,
            provider_id,
            "owner console session credential (provider identified)",
            frozenset({DISCOVERY_PURPOSE, EVALUATION_PURPOSE}),
            expires_at=state.expires_at,
        )
        binding, grant = _discovery_binding_grant(credential_ref, provider_id, state.expires_at)
        with self._session_lock:
            self._identities[credential_ref] = identity
            state.identity = identity
            state.discovery_binding = binding
            state.discovery_grant = grant
            state.discovered_provider = provider_id
        return identity

    def current_identity(self, credential_ref: str) -> CredentialIdentity:
        return self._require_session(credential_ref).identity

    def revoke_session(self, credential_ref: str) -> dict[str, Any]:
        """Forget the owner credential immediately (value + identity + state)."""
        if not isinstance(credential_ref, str):
            raise SessionConsoleError("credential_ref must be a string")
        with self._session_lock:
            state = self._sessions.pop(credential_ref, None)
            identity = self._identities.get(credential_ref)
            if state is None and identity is None:
                raise SessionConsoleError(f"unknown session credential {credential_ref}")
            if identity is not None:
                self._identities[credential_ref] = CredentialIdentity(
                    credential_ref,
                    identity.provider,
                    identity.purpose,
                    identity.scope,
                    status="REVOKED",
                    expires_at=identity.expires_at,
                )
            if state is not None:
                self._session_values.delete(credential_ref, state.identity.version)
        return {"credential_ref": credential_ref, "status": "REVOKED"}

    def session_expiry(self, credential_ref: str) -> str:
        return self._require_session(credential_ref).expires_at

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_session(self, credential_ref: str) -> _SessionState:
        if not isinstance(credential_ref, str) or not _CREDENTIAL_REF.fullmatch(credential_ref):
            raise SessionConsoleError("credential_ref must be an ECP session reference")
        with self._session_lock:
            state = self._sessions.get(credential_ref)
        if state is None:
            raise SessionConsoleError(f"unknown or expired session credential {credential_ref}")
        return state


@dataclass
class _SessionState:
    credential_id: str
    identity: CredentialIdentity
    discovery_binding: CredentialBinding
    discovery_grant: AuthorizationGrant
    expires_at: str
    discovered_provider: str | None = None


class _SessionSecretStore(SecretStore):
    """In-process session secret values (never persisted, never stringified)."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, str], str] = {}
        self._lock = threading.RLock()

    def _read(self, credential_id: str, version: str) -> "str | None":
        with self._lock:
            return self._values.get((credential_id, version))

    def _write(self, credential_id: str, version: str, secret: str) -> None:
        raise PermissionError("session store writes go through the session gateway only")

    def _delete(self, credential_id: str, version: str) -> None:
        with self._lock:
            self._values.pop((credential_id, version), None)

    def write(self, credential_id: str, version: str, secret: str) -> None:
        """Controlled session provisioning seam (values never leave the process)."""
        if not isinstance(secret, str) or not secret:
            raise ValueError("session secret must be a non-empty string")
        with self._lock:
            self._values[(credential_id, version)] = secret

    def delete(self, credential_id: str, version: str) -> None:
        self._delete(credential_id, version)


class _CompositeSecretStore(SecretStore):
    """Session values first, then the launcher's backing store."""

    def __init__(self, session: _SessionSecretStore, backing: SecretStore) -> None:
        self._session = session
        self._backing = backing

    def _read(self, credential_id: str, version: str) -> "str | None":
        value = self._session._read(credential_id, version)
        if value is not None:
            return value
        return self._backing._read(credential_id, version)

    def _write(self, credential_id: str, version: str, secret: str) -> None:
        raise PermissionError("composite store writes go through the session gateway only")

    def _delete(self, credential_id: str, version: str) -> None:
        self._session._delete(credential_id, version)


def _discovery_binding_grant(
    credential_ref: str, provider_id: str, expires_at: str
) -> "tuple[CredentialBinding, AuthorizationGrant]":
    suffix = credential_ref.rsplit("-", 1)[-1]
    binding = CredentialBinding(
        binding_id=f"ECP-BINDING-DISCOVERY-{suffix}",
        requirement_id=f"ECP-REQUIREMENT-DISCOVERY-{suffix}",
        target_id=f"ECP-TARGET-DISCOVERY-{suffix}",
        provider_id=provider_id,
        interface=DISCOVERY_PURPOSE,
        purpose=DISCOVERY_PURPOSE,
        credential_ref=credential_ref,
        scope=frozenset({DISCOVERY_PURPOSE}),
    )
    grant = AuthorizationGrant(
        authorization_ref=f"ECP-AUTH-DISCOVERY-{suffix}",
        binding_id=binding.binding_id,
        target_id=binding.target_id,
        purpose=DISCOVERY_PURPOSE,
        scope=frozenset({DISCOVERY_PURPOSE}),
        expires_at=expires_at,
    )
    return binding, grant


def _ttl_delta(ttl_seconds: int):
    from datetime import timedelta

    return timedelta(seconds=ttl_seconds)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


#: Signature of the injected runtime-adapter factory (the launcher owns the
#: single built-in kind mapping; the session layer never builds adapters itself).
AdapterFactory = Callable[..., Any]


class ConsoleSessionManager:
    """Thin orchestrator for the browser-facing session flow.

    dict-in / dict-out operations behind the LocalGateway session routes.
    Holds no secrets (values stay inside the session credential gateway),
    performs no execution (execution stays on the existing path), and adds
    no second registry (targets go through the onboarding service's own
    registries).
    """

    def __init__(
        self,
        *,
        gateway: LocalGateway,
        session_credentials: SessionCredentialGateway,
        discovery: ProviderDiscoveryService,
        onboarding: TargetOnboardingService,
        adapter_factory: AdapterFactory,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._gateway = gateway
        self._session_credentials = session_credentials
        self._discovery = discovery
        self._onboarding = onboarding
        self._adapter_factory = adapter_factory
        self._ttl = ttl_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._reports: dict[str, DiscoveryReport] = {}
        self._selections: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Route operations (dict in, dict out; secret-free)
    # ------------------------------------------------------------------

    def descriptors(self) -> "list[dict[str, Any]]":
        """Registry-driven provider descriptor view for the console UI."""
        return self._discovery.descriptors_view()

    def open_session(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        credential_secret = payload.get("credential_secret")
        handle = self._session_credentials.open_session(
            credential_secret, ttl_seconds=self._ttl, now=self._clock()
        )
        return handle

    def discover(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        credential_ref = _required_string(payload, "credential_ref")
        provider_hint = _optional_string(payload, "provider_hint")
        base_url = _optional_string(payload, "base_url")
        request_id = "ECP-DISCOVERY-" + uuid.uuid4().hex[:12].upper()
        lease = self._session_credentials.discovery_lease(
            credential_ref, request_id=request_id, now=self._clock()
        )
        report = self._discovery.discover(
            lease, provider_hint=provider_hint, custom_base_url=base_url
        )
        if report.status == STATUS_DISCOVERED and report.provider_id is not None:
            self._session_credentials.bind_discovered_provider(credential_ref, report.provider_id)
        with self._lock:
            self._reports[credential_ref] = report
        document = report.to_document()
        document["credential_ref"] = credential_ref
        document["request_id"] = request_id
        redactor = SecretRedactionFilter((lease.value,))
        return _redact_document(document, redactor)

    def select_target(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        credential_ref = _required_string(payload, "credential_ref")
        model_identifier = _required_string(payload, "model_identifier")
        with self._lock:
            report = self._reports.get(credential_ref)
            cache_key = f"{credential_ref}\n{model_identifier}"
            cached = self._selections.get(cache_key)
        if report is None or report.status != STATUS_DISCOVERED:
            raise SessionConsoleError(
                "no successful provider discovery report for this credential; run discovery first"
            )
        if cached is not None:
            return dict(cached)
        identifiers = self._onboard_session_target(credential_ref, report, model_identifier)
        with self._lock:
            self._selections[cache_key] = dict(identifiers)
        return identifiers

    def revoke_session(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        credential_ref = _required_string(payload, "credential_ref")
        result = self._session_credentials.revoke_session(credential_ref)
        with self._lock:
            self._reports.pop(credential_ref, None)
            self._selections = {
                key: value
                for key, value in self._selections.items()
                if not key.startswith(credential_ref + "\n")
            }
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _onboard_session_target(
        self, credential_ref: str, report: DiscoveryReport, model_identifier: str
    ) -> dict[str, Any]:
        if report.discovery_id is None or report.matched_base_url is None:
            raise SessionConsoleError("discovery report is incomplete; run discovery again")
        descriptor = self._discovery.registry.get(report.discovery_id)
        if not any(model.model_identifier == model_identifier for model in report.models):
            raise SessionConsoleError(
                f"model {model_identifier!r} is not in the discovered model list"
            )
        try:
            endpoint = descriptor.execution_endpoint(report.matched_base_url, model_identifier)
        except Exception as exc:
            raise SessionConsoleError(str(exc)) from None
        provider_id = report.provider_id or ""
        interface = descriptor.interface()
        identity = self._session_credentials.current_identity(credential_ref)
        h16 = hash_document(
            {
                "provider": provider_id,
                "model": model_identifier,
                "endpoint": endpoint,
                "credential_ref": credential_ref,
                "adapter_kind": descriptor.adapter_kind,
            }
        )[:16].upper()
        target_id = f"ECP-TARGET-SESSION-{h16}"
        evaluation_id = f"ECP-EVAL-SESSION-{h16}"
        system_id = f"ECP-SYSTEM-SESSION-{h16}"
        test_id = f"ECP-TEST-SESSION-{h16}"
        adapter_id = f"ECP-ADAPTER-SESSION-{h16}"
        binding_id = f"ECP-BINDING-SESSION-{h16}"
        requirement_id = f"ECP-REQUIREMENT-SESSION-{h16}"
        authorization_ref = f"ECP-AUTH-SESSION-{h16}"

        provider_document = dict(descriptor.provider_document)
        adapter_document = {
            **dict(descriptor.adapter_document),
            "adapter_id": adapter_id,
        }
        self._onboarding.register_provider_integration(provider_document, adapter_document)

        runtime_adapter = self._adapter_factory(
            descriptor.adapter_kind,
            model=model_identifier,
            endpoint=endpoint,
            provider=provider_id,
            adapter_id=adapter_id,
        )

        target_document = {
            "ecp_object": "target",
            "target_id": target_id,
            "target_version": "1.0.0",
            "system": {
                "system_id": system_id,
                "system_version": "1.0.0",
                "system_kind": "model-only",
                "configuration_ref": None,
            },
            "provider": {
                "provider_id": provider_id,
                "provider_version": provider_document["provider_version"],
                "interface": interface,
            },
            "adapter": {
                "adapter_id": adapter_id,
                "adapter_version": adapter_document["adapter_version"],
                "provider_id": provider_id,
            },
            "credential_ref": credential_ref,
            "authorization_ref": authorization_ref,
            "evaluation_bindings": [evaluation_id],
            "test_bindings": [test_id],
            "execution_environment": dict(_SESSION_ENVIRONMENT),
            "required_capabilities": list(adapter_document["supported_capabilities"]),
        }
        binding = CredentialBinding(
            binding_id,
            requirement_id,
            target_id,
            provider_id,
            interface,
            EVALUATION_PURPOSE,
            credential_ref,
            frozenset({EVALUATION_PURPOSE}),
        )
        grant = AuthorizationGrant(
            authorization_ref,
            binding_id,
            target_id,
            EVALUATION_PURPOSE,
            frozenset({EVALUATION_PURPOSE}),
            identity.expires_at or _iso(self._clock()),
        )
        tests = {test_id: AuthorizedTest(test_id, "Universal console conformance probe", EVALUATION_PURPOSE)}

        try:
            onboarded = self._onboarding.onboard(
                target_document,
                runtime_adapter=runtime_adapter,
                credential_identity=identity,
                binding=binding,
                grant=grant,
                tests=tests,
            )
        except Exception as exc:
            raise SessionConsoleError(str(exc)) from None
        self._gateway.register_evaluation(onboarded.evaluation)
        return {
            "credential_ref": credential_ref,
            "target_id": target_id,
            "evaluation_id": evaluation_id,
            "system_id": system_id,
            "test_id": test_id,
            "provider_id": provider_id,
            "adapter_id": adapter_id,
            "model_identifier": model_identifier,
            "endpoint": endpoint,
            "ready": onboarded.readiness.state,
        }


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SessionConsoleError(f"{key} is required")
    return value


def _optional_string(payload: Mapping[str, Any], key: str) -> "str | None":
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SessionConsoleError(f"{key} must be a non-empty string or null")
    return value


def _redact_document(document: Any, redactor: SecretRedactionFilter) -> Any:
    """Recursively redact secret values from a document (defense in depth)."""
    if isinstance(document, str):
        return redactor.redact(document)
    if isinstance(document, dict):
        return {key: _redact_document(value, redactor) for key, value in document.items()}
    if isinstance(document, list):
        return [_redact_document(item, redactor) for item in document]
    return document


__all__ = [
    "AdapterFactory",
    "ConsoleSessionManager",
    "DEFAULT_SESSION_TTL_SECONDS",
    "DISCOVERY_PURPOSE",
    "EVALUATION_PURPOSE",
    "SESSION_PROVIDER_ID",
    "SessionConsoleError",
    "SessionCredentialGateway",
]
