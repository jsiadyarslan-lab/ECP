"""Provider-neutral adapter contracts and deterministic target resolution.

Phase B registers capability metadata only. No adapter implementation, network
transport, credential access, authorization, or provider execution exists here.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from .targets import (
    InvalidTarget,
    ProviderRegistry,
    TargetRegistry,
    UnknownProvider,
    _contains_secret_key,
)
from .validate import validate_document


class AdapterError(ValueError):
    """Base error for adapter metadata and resolution failures."""


class DuplicateAdapter(AdapterError):
    pass


class UnknownAdapter(AdapterError):
    pass


class ResolutionError(AdapterError):
    pass


def adapter_document(
    adapter_id: str,
    adapter_version: str,
    provider_id: str,
    provider_interface: str,
    supported_system_kinds: list[str],
    supported_capabilities: list[str] | None = None,
    *,
    status: str = "active",
) -> dict[str, Any]:
    document = {
        "ecp_object": "adapter",
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "provider_id": provider_id,
        "provider_interface": provider_interface,
        "supported_system_kinds": list(supported_system_kinds),
        "supported_capabilities": list(supported_capabilities or []),
        "status": status,
    }
    issues = validate_document(document, "adapter")
    if _contains_secret_key(document):
        issues.append("<root>: secret-bearing fields are forbidden")
    if issues:
        raise AdapterError("invalid adapter: " + "; ".join(issues))
    return document


class AdapterRegistry:
    """In-memory exact-version adapter contract registry."""

    def __init__(self) -> None:
        self._adapters: dict[tuple[str, str], dict[str, Any]] = {}

    def register(self, adapter: Mapping[str, Any]) -> dict[str, Any]:
        document = deepcopy(dict(adapter))
        issues = validate_document(document, "adapter")
        if _contains_secret_key(document):
            issues.append("<root>: secret-bearing fields are forbidden")
        if issues:
            raise AdapterError("invalid adapter: " + "; ".join(issues))
        key = (document["adapter_id"], document["adapter_version"])
        if key in self._adapters:
            raise DuplicateAdapter(f"{key[0]}@{key[1]}")
        self._adapters[key] = document
        return deepcopy(document)

    def get(self, adapter_id: str, version: str) -> dict[str, Any]:
        try:
            return deepcopy(self._adapters[(adapter_id, version)])
        except KeyError as exc:
            raise UnknownAdapter(f"{adapter_id}@{version}") from exc

    def list(self) -> list[dict[str, Any]]:
        return [deepcopy(self._adapters[key]) for key in sorted(self._adapters)]


@dataclass(frozen=True)
class ResolvedTarget:
    """Immutable, non-authorizing result of successful compatibility checks."""

    target_id: str
    target_version: str
    provider_id: str
    provider_interface: str
    adapter_id: str
    adapter_version: str
    system_kind: str
    verified_capabilities: tuple[str, ...]
    resolution_status: str = "resolved"


class TargetResolver:
    """Resolve only an explicitly requested, exactly compatible adapter."""

    def __init__(self, providers: ProviderRegistry, targets: TargetRegistry, adapters: AdapterRegistry) -> None:
        self.providers = providers
        self.targets = targets
        self.adapters = adapters

    def resolve(self, target_id: str, target_version: str | None = None) -> ResolvedTarget:
        try:
            target = self.targets.get(target_id, target_version)
            provider_id = target["provider"]["provider_id"]
            provider_interface = target["provider"]["interface"]
            provider = self.providers.get(provider_id)
            if provider["status"] != "active":
                raise ResolutionError(f"provider {provider_id} is inactive")
            if provider_interface not in provider["interfaces"]:
                raise ResolutionError("target interface is not declared by provider")
            requested = target["adapter"]
            adapter = self.adapters.get(requested["adapter_id"], requested["adapter_version"])
            if adapter["status"] != "active":
                raise ResolutionError(f"adapter {requested['adapter_id']} is inactive")
            if adapter["provider_id"] != provider_id:
                raise ResolutionError("provider and adapter provider mismatch")
            if adapter["provider_interface"] != provider_interface:
                raise ResolutionError("provider interface and adapter interface mismatch")
            system_kind = target["system"]["system_kind"]
            if system_kind not in adapter["supported_system_kinds"]:
                raise ResolutionError("adapter does not support target system kind")
            required = tuple(target.get("required_capabilities", []))
            unsupported = sorted(set(required) - set(adapter["supported_capabilities"]))
            if unsupported:
                raise ResolutionError("adapter lacks required capabilities: " + ", ".join(unsupported))
            return ResolvedTarget(
                target_id=target["target_id"],
                target_version=target["target_version"],
                provider_id=provider_id,
                provider_interface=provider_interface,
                adapter_id=adapter["adapter_id"],
                adapter_version=adapter["adapter_version"],
                system_kind=system_kind,
                verified_capabilities=required,
            )
        except (InvalidTarget, UnknownAdapter, UnknownProvider) as exc:
            raise ResolutionError(str(exc)) from exc


__all__ = [
    "AdapterError", "AdapterRegistry", "DuplicateAdapter", "ResolutionError",
    "ResolvedTarget", "TargetResolver", "UnknownAdapter", "adapter_document",
]
