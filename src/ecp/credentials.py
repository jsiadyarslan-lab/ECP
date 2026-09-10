"""Provider-neutral credential boundary for ECP runtime integrations.

This module deliberately keeps secret values outside ECP documents and public
artifacts.  Callers obtain a short-lived :class:`SecretLease` only through
:class:`CredentialGateway`; metadata is safe to persist, while the secret value
is intentionally non-serializable and redacted from representations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import re
from threading import RLock
from typing import Mapping, Protocol, Sequence, runtime_checkable


class CredentialError(Exception):
    """Base class for credential-boundary failures without secret payloads."""


class CredentialNotFound(CredentialError):
    """The logical credential has no provisioned value."""


class CredentialExpired(CredentialError):
    """The credential is outside its allowed lifetime."""


class CredentialRevoked(CredentialError):
    """The credential has been revoked."""


class CredentialScopeError(CredentialError):
    """The requested operation is outside the credential's declared scope."""


class CredentialStateError(CredentialError):
    """The requested lifecycle transition is invalid."""


_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(api[_ -]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(bearer\s+)[^\s,;]+"),
)


def redact_secrets(value: object) -> str:
    """Return text safe for logs and exceptions without exposing credentials."""

    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", text)
    return text


class SecretRedactionFilter:
    """Small logging-compatible filter that redacts known secret strings."""

    def __init__(self, secrets: Sequence[str] = ()) -> None:
        self._secrets = tuple(secret for secret in secrets if secret)

    def redact(self, value: object) -> str:
        text = redact_secrets(value)
        for secret in self._secrets:
            text = text.replace(secret, "[REDACTED]")
        return text


@dataclass(frozen=True)
class CredentialIdentity:
    """Non-secret logical identity and policy for one credential."""

    credential_id: str
    provider: str
    purpose: str
    scope: frozenset[str] = field(default_factory=frozenset)
    version: str = "1"
    status: str = "PROVISIONED"
    created_at: str = ""
    expires_at: str | None = None

    def __post_init__(self) -> None:
        required = {
            "credential_id": self.credential_id,
            "provider": self.provider,
            "purpose": self.purpose,
            "version": self.version,
        }
        if any(not isinstance(value, str) or not value.strip() for value in required.values()):
            raise ValueError("credential identity fields must be non-empty strings")
        if self.status not in {"PROVISIONED", "ACTIVE", "USED", "ROTATED", "REVOKED", "EXPIRED"}:
            raise ValueError("unsupported credential status")
        if self.expires_at is not None:
            _parse_time(self.expires_at)

    def metadata(self) -> dict[str, object]:
        """Return persistable metadata; never includes a secret value."""

        return {
            "credential_id": self.credential_id,
            "provider": self.provider,
            "purpose": self.purpose,
            "scope": sorted(self.scope),
            "version": self.version,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("credential timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


class SecretStore(ABC):
    """Internal store seam; secret retrieval is intentionally not public API."""

    @abstractmethod
    def _read(self, credential_id: str, version: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def _write(self, credential_id: str, version: str, secret: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def _delete(self, credential_id: str, version: str) -> None:
        raise NotImplementedError


class _MemorySecretStore(SecretStore):
    """Test/local store; production deployments should replace this seam."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, str], str] = {}
        self._lock = RLock()

    def _read(self, credential_id: str, version: str) -> str | None:
        with self._lock:
            return self._values.get((credential_id, version))

    def _write(self, credential_id: str, version: str, secret: str) -> None:
        if not isinstance(secret, str) or not secret:
            raise ValueError("secret must be a non-empty string")
        with self._lock:
            self._values[(credential_id, version)] = secret

    def _delete(self, credential_id: str, version: str) -> None:
        with self._lock:
            self._values.pop((credential_id, version), None)


class EnvironmentSecretStore(SecretStore):
    """Read-only runtime source backed by an injected environment variable."""

    def __init__(self, variable_name: str) -> None:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", variable_name):
            raise ValueError("environment variable name must be uppercase POSIX style")
        self.variable_name = variable_name

    def _read(self, credential_id: str, version: str) -> str | None:
        del credential_id, version
        return os.environ.get(self.variable_name)

    def _write(self, credential_id: str, version: str, secret: str) -> None:
        del credential_id, version, secret
        raise CredentialStateError("environment secret source is read-only")

    def _delete(self, credential_id: str, version: str) -> None:
        del credential_id, version
        raise CredentialStateError("environment secret source is read-only")


class SecretLease:
    """Short-lived in-memory access object; repr/str never reveal its value."""

    __slots__ = ("_value", "metadata")

    def __init__(self, value: str, metadata: Mapping[str, object]) -> None:
        self._value = value
        self.metadata = dict(metadata)

    @property
    def value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretLease(value=[REDACTED], metadata=<non-secret>)"

    __str__ = __repr__


@runtime_checkable
class ExternalSystemAdapter(Protocol):
    """Provider-neutral contract for a future adapter boundary.

    Implementations receive a scoped lease from the gateway.  This protocol
    intentionally performs no provider call and stores no credential itself.
    """

    provider: str

    def execute(self, lease: SecretLease, request: object) -> object:
        """Use the lease for one controlled adapter operation."""
        ...


class CredentialGateway:
    """The only public ECP boundary for obtaining a scoped credential lease."""

    def __init__(self, store: SecretStore, identities: Mapping[str, CredentialIdentity]) -> None:
        self._store = store
        self._identities = dict(identities)

    @classmethod
    def from_environment(cls, identity: CredentialIdentity, variable_name: str) -> "CredentialGateway":
        return cls(EnvironmentSecretStore(variable_name), {identity.credential_id: identity})

    @classmethod
    def for_testing(cls, identities: Mapping[str, CredentialIdentity]) -> tuple["CredentialGateway", _MemorySecretStore]:
        store = _MemorySecretStore()
        return cls(store, identities), store

    def metadata(self, credential_id: str) -> dict[str, object]:
        return self._identity(credential_id).metadata()

    def retrieve(self, credential_id: str, requested_scope: str, *, now: datetime | None = None) -> SecretLease:
        identity = self._identity(credential_id)
        self._check_policy(identity, requested_scope, now or datetime.now(timezone.utc))
        value = self._store._read(identity.credential_id, identity.version)
        if not value:
            raise CredentialNotFound(f"credential {identity.credential_id} is not provisioned")
        return SecretLease(value, identity.metadata())

    def provision_for_testing(self, credential_id: str, secret: str) -> None:
        """Provision only into the private synthetic/test store seam."""

        identity = self._identity(credential_id)
        if not isinstance(self._store, _MemorySecretStore):
            raise CredentialStateError("runtime store does not permit in-process provisioning")
        self._store._write(identity.credential_id, identity.version, secret)

    def rotate_for_testing(self, identity: CredentialIdentity, secret: str) -> "CredentialGateway":
        if not isinstance(self._store, _MemorySecretStore):
            raise CredentialStateError("runtime store does not permit in-process rotation")
        self._store._write(identity.credential_id, identity.version, secret)
        return CredentialGateway(self._store, {**self._identities, identity.credential_id: identity})

    def revoke(self, credential_id: str) -> None:
        identity = self._identity(credential_id)
        if not isinstance(self._store, _MemorySecretStore):
            raise CredentialStateError("runtime store does not permit in-process revocation")
        self._store._delete(identity.credential_id, identity.version)
        self._identities[credential_id] = CredentialIdentity(**{**identity.metadata(), "status": "REVOKED", "scope": frozenset(identity.scope)})

    def _identity(self, credential_id: str) -> CredentialIdentity:
        try:
            return self._identities[credential_id]
        except KeyError as exc:
            raise CredentialNotFound(f"unknown credential {credential_id}") from exc

    @staticmethod
    def _check_policy(identity: CredentialIdentity, requested_scope: str, now: datetime) -> None:
        if identity.status in {"REVOKED", "EXPIRED"}:
            raise CredentialRevoked(f"credential {identity.credential_id} is unavailable")
        if requested_scope not in identity.scope:
            raise CredentialScopeError(f"scope denied for credential {identity.credential_id}")
        if identity.expires_at is not None and now.astimezone(timezone.utc) >= _parse_time(identity.expires_at):
            raise CredentialExpired(f"credential {identity.credential_id} has expired")


def safe_exception_message(error: BaseException) -> str:
    """Convert an exception to a report-safe message."""

    return redact_secrets(error)


__all__ = [
    "CredentialError",
    "CredentialExpired",
    "CredentialGateway",
    "CredentialIdentity",
    "CredentialNotFound",
    "CredentialRevoked",
    "CredentialScopeError",
    "CredentialStateError",
    "EnvironmentSecretStore",
    "ExternalSystemAdapter",
    "SecretLease",
    "SecretRedactionFilter",
    "SecretStore",
    "redact_secrets",
    "safe_exception_message",
]
