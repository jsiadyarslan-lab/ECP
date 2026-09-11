"""Non-secret credential control-plane contracts for Phase C.

These value objects carry identity, scope, purpose, and authorization context
only. They never carry credential material and do not implement an
authorization engine or a production lease service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any


_REF = re.compile(r"^ECP-[A-Za-z0-9][A-Za-z0-9._:-]*$")
_CREDENTIAL_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class CredentialContractError(ValueError):
    """Invalid or incomplete non-secret credential control-plane contract."""


class BindingScopeError(CredentialContractError):
    """A binding or release request does not match its declared scope."""


class AuthorizationRequired(CredentialContractError):
    """A release request lacks a matching explicit authorization grant."""


def _nonempty(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CredentialContractError(f"{name} must be a non-empty string")
    return value


def _ref(name: str, value: str, pattern: re.Pattern[str] = _REF) -> str:
    _nonempty(name, value)
    if not pattern.fullmatch(value):
        raise CredentialContractError(f"{name} must be an opaque ECP reference")
    return value


def _scope(scope: frozenset[str] | set[str] | tuple[str, ...]) -> frozenset[str]:
    result = frozenset(scope)
    if not result or any(not isinstance(item, str) or not item.strip() for item in result):
        raise CredentialContractError("scope must contain at least one non-empty purpose")
    return result


def _time(name: str, value: str) -> str:
    _nonempty(name, value)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CredentialContractError(f"{name} must include a timezone")
    return value


@dataclass(frozen=True)
class CredentialDefinition:
    definition_id: str
    provider_id: str
    interface: str
    access_mechanism: str
    purpose: str

    def __post_init__(self) -> None:
        _ref("definition_id", self.definition_id)
        _nonempty("provider_id", self.provider_id)
        _nonempty("interface", self.interface)
        _nonempty("access_mechanism", self.access_mechanism)
        _nonempty("purpose", self.purpose)

    def metadata(self) -> dict[str, Any]:
        return {"definition_id": self.definition_id, "provider_id": self.provider_id,
                "interface": self.interface, "access_mechanism": self.access_mechanism,
                "purpose": self.purpose}


@dataclass(frozen=True)
class CredentialRequirement:
    requirement_id: str
    target_id: str
    definition_id: str
    purpose: str
    scope: frozenset[str]

    def __post_init__(self) -> None:
        _ref("requirement_id", self.requirement_id)
        _ref("target_id", self.target_id)
        _ref("definition_id", self.definition_id)
        _nonempty("purpose", self.purpose)
        _scope(self.scope)

    def metadata(self) -> dict[str, Any]:
        return {"requirement_id": self.requirement_id, "target_id": self.target_id,
                "definition_id": self.definition_id, "purpose": self.purpose,
                "scope": sorted(self.scope)}


@dataclass(frozen=True)
class CredentialBinding:
    binding_id: str
    requirement_id: str
    target_id: str
    provider_id: str
    interface: str
    purpose: str
    credential_ref: str
    scope: frozenset[str]

    def __post_init__(self) -> None:
        _ref("binding_id", self.binding_id)
        _ref("requirement_id", self.requirement_id)
        _ref("target_id", self.target_id)
        _nonempty("provider_id", self.provider_id)
        _nonempty("interface", self.interface)
        _nonempty("purpose", self.purpose)
        _ref("credential_ref", self.credential_ref, _CREDENTIAL_REF)
        _scope(self.scope)

    def metadata(self) -> dict[str, Any]:
        return {"binding_id": self.binding_id, "requirement_id": self.requirement_id,
                "target_id": self.target_id, "provider_id": self.provider_id,
                "interface": self.interface, "purpose": self.purpose,
                "credential_ref": self.credential_ref, "scope": sorted(self.scope)}


@dataclass(frozen=True)
class AuthorizationGrant:
    authorization_ref: str
    binding_id: str
    target_id: str
    purpose: str
    scope: frozenset[str]
    expires_at: str
    status: str = "GRANTED"

    def __post_init__(self) -> None:
        _ref("authorization_ref", self.authorization_ref)
        _ref("binding_id", self.binding_id)
        _ref("target_id", self.target_id)
        _nonempty("purpose", self.purpose)
        _scope(self.scope)
        _time("expires_at", self.expires_at)
        if self.status not in {"GRANTED", "REVOKED", "EXPIRED"}:
            raise CredentialContractError("unsupported authorization status")

    def metadata(self) -> dict[str, Any]:
        return {"authorization_ref": self.authorization_ref, "binding_id": self.binding_id,
                "target_id": self.target_id, "purpose": self.purpose,
                "scope": sorted(self.scope), "expires_at": self.expires_at,
                "status": self.status}


@dataclass(frozen=True)
class ScopedReleaseRequest:
    request_id: str
    binding_id: str
    target_id: str
    credential_ref: str
    purpose: str
    scope: frozenset[str]
    lease_seconds: int
    requested_at: str
    one_use: bool = False

    def __post_init__(self) -> None:
        _nonempty("request_id", self.request_id)
        _ref("binding_id", self.binding_id)
        _ref("target_id", self.target_id)
        _ref("credential_ref", self.credential_ref, _CREDENTIAL_REF)
        _nonempty("purpose", self.purpose)
        _scope(self.scope)
        if not isinstance(self.lease_seconds, int) or not 0 < self.lease_seconds <= 3600:
            raise CredentialContractError("lease_seconds must be between 1 and 3600")
        _time("requested_at", self.requested_at)

    def metadata(self) -> dict[str, Any]:
        return {"request_id": self.request_id, "binding_id": self.binding_id,
                "target_id": self.target_id, "credential_ref": self.credential_ref,
                "purpose": self.purpose, "scope": sorted(self.scope),
                "lease_seconds": self.lease_seconds, "requested_at": self.requested_at,
                "one_use": self.one_use}


def validate_binding(definition: CredentialDefinition, requirement: CredentialRequirement,
                     binding: CredentialBinding) -> None:
    if requirement.definition_id != definition.definition_id:
        raise BindingScopeError("requirement does not reference definition")
    if binding.requirement_id != requirement.requirement_id:
        raise BindingScopeError("binding does not satisfy requirement")
    if binding.target_id != requirement.target_id:
        raise BindingScopeError("binding target mismatch")
    if binding.provider_id != definition.provider_id or binding.interface != definition.interface:
        raise BindingScopeError("binding provider/interface mismatch")
    if binding.purpose != requirement.purpose or not binding.scope.issubset(requirement.scope):
        raise BindingScopeError("binding purpose or scope exceeds requirement")


__all__ = [
    "AuthorizationGrant", "AuthorizationRequired", "BindingScopeError",
    "CredentialBinding", "CredentialContractError", "CredentialDefinition",
    "CredentialRequirement", "ScopedReleaseRequest", "validate_binding",
]
