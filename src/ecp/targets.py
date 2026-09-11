"""Provider-neutral external target control-plane foundation.

This module stores operational metadata and references only. It deliberately
contains no provider transport, credential retrieval, authorization decision,
or scientific result logic.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from .canonical import canonical_bytes
from .hashing import sha256_hex
from .validate import validate_document


class TargetError(ValueError):
    """Base error for invalid provider/target metadata."""


class DuplicateProvider(TargetError):
    pass


class DuplicateTarget(TargetError):
    pass


class UnknownProvider(TargetError):
    pass


class InvalidTarget(TargetError):
    pass


_SECRET_KEYS = {
    "secret", "secret_value", "api_key", "apikey", "token", "password",
    "private_key", "authorization", "credential_value",
}


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).lower() in _SECRET_KEYS or _contains_secret_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_secret_key(item) for item in value)
    return False


def _issues(document: Mapping[str, Any], schema: str) -> list[str]:
    if _contains_secret_key(document):
        return ["<root>: secret-bearing fields are forbidden"]
    return validate_document(document, schema)


def provider_document(
    provider_id: str,
    provider_version: str,
    interfaces: list[str],
    *,
    status: str = "active",
    description: str | None = None,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "ecp_object": "provider",
        "provider_id": provider_id,
        "provider_version": provider_version,
        "interfaces": list(interfaces),
        "status": status,
    }
    if description is not None:
        document["description"] = description
    issues = _issues(document, "provider")
    if issues:
        raise InvalidTarget("invalid provider: " + "; ".join(issues))
    return document


def target_hash(target: Mapping[str, Any]) -> str:
    """Return the deterministic operational hash of a validated target."""
    issues = _issues(target, "target")
    if issues:
        raise InvalidTarget("cannot hash invalid target: " + "; ".join(issues))
    return sha256_hex(canonical_bytes(target))


class ProviderRegistry:
    """In-memory provider metadata registry; no network or secret access."""

    def __init__(self, providers: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self._providers: dict[str, dict[str, Any]] = {}
        for document in (providers or {}).values():
            self.register(document)

    def register(self, provider: Mapping[str, Any]) -> dict[str, Any]:
        document = deepcopy(dict(provider))
        issues = _issues(document, "provider")
        if issues:
            raise InvalidTarget("invalid provider: " + "; ".join(issues))
        provider_id = document["provider_id"]
        if provider_id in self._providers:
            raise DuplicateProvider(provider_id)
        self._providers[provider_id] = document
        return deepcopy(document)

    def get(self, provider_id: str) -> dict[str, Any]:
        try:
            return deepcopy(self._providers[provider_id])
        except KeyError as exc:
            raise UnknownProvider(provider_id) from exc

    def list(self) -> list[dict[str, Any]]:
        return [deepcopy(self._providers[key]) for key in sorted(self._providers)]


class TargetRegistry:
    """Minimal multi-target registry for operational metadata and references."""

    def __init__(self, providers: ProviderRegistry) -> None:
        self.providers = providers
        self._targets: dict[str, dict[str, Any]] = {}

    def register(self, target: Mapping[str, Any]) -> dict[str, Any]:
        document = deepcopy(dict(target))
        issues = _issues(document, "target")
        if issues:
            raise InvalidTarget("invalid target: " + "; ".join(issues))
        target_id = document["target_id"]
        if target_id in self._targets:
            raise DuplicateTarget(target_id)
        provider = document["provider"]["provider_id"]
        registered_provider = self.providers.get(provider)
        if registered_provider["status"] != "active":
            raise InvalidTarget(f"provider {provider} is not active")
        adapter = document["adapter"]
        if adapter["provider_id"] != provider:
            raise InvalidTarget("target provider and adapter provider must match")
        if document["credential_ref"] in {"", "null"}:
            raise InvalidTarget("credential_ref must be a reference")
        if not document["evaluation_bindings"] or not document["test_bindings"]:
            raise InvalidTarget("evaluation and test bindings are required")
        if document["authorization_ref"] == document["credential_ref"]:
            raise InvalidTarget("authorization_ref and credential_ref must remain distinct")
        self._targets[target_id] = document
        return deepcopy(document)

    def get(self, target_id: str, version: str | None = None) -> dict[str, Any]:
        try:
            target = self._targets[target_id]
        except KeyError as exc:
            raise InvalidTarget(f"unknown target {target_id}") from exc
        if version is not None and target["target_version"] != version:
            raise InvalidTarget(f"target {target_id} version mismatch")
        return deepcopy(target)

    def list(self) -> list[dict[str, Any]]:
        return [deepcopy(self._targets[key]) for key in sorted(self._targets)]

    def hash(self, target_id: str) -> str:
        return target_hash(self.get(target_id))


__all__ = [
    "DuplicateProvider", "DuplicateTarget", "InvalidTarget", "ProviderRegistry",
    "TargetError", "TargetRegistry", "UnknownProvider", "provider_document",
    "target_hash",
]
