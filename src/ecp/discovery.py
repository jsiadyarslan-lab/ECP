"""Universal Provider & Model Discovery Fabric v1 — identify, never guess.

Governing principle (owner order 2026-09-12, UNIVERSAL VISUAL PROVIDER &
MODEL EVALUATION CONSOLE v1):

    Owner enters a credential
        -> ONE unified discovery mechanism probes candidate provider
           dialects (descriptor DATA, not per-provider code)
        -> provider identity + available models are REPORTED
        -> the owner selects a model
        -> the target is onboarded through the EXISTING universal
           onboarding fabric and executed through the EXISTING universal
           execution fabric.

This module is the discovery seam of the provider adapter contract. It adds
NO new execution path and NO parallel registry for execution: descriptors
are data recipes that describe how to ask ONE provider dialect for its
model list. Provider specifics (endpoints, header styles, response shapes)
live in descriptor DATA; the probing mechanics stay provider-neutral.

Design invariants:

* **Identification, not guessing.** A provider is reported IDENTIFIED only
  when its models endpoint answered with a parseable model list. When no
  candidate answers, the report states ``DISCOVERY_FAILED`` with
  identification ``UNKNOWN`` and per-probe reasons — the fabric never
  guesses a provider identity from the credential shape.
* **Secret discipline.** The released credential value is used ONLY to
  build probe headers. It is never stored on the service, never echoed in
  reports, never embedded in probe details (which carry status codes and
  host names only).
* **Provider-neutral representation.** Every discovered model is reported
  as ``(provider, model_identifier, display_name, capabilities,
  availability, discovered_at, adapter_kind, protocol)`` regardless of
  which dialect produced it.
* **Extensibility.** Adding a provider means adding a descriptor (data)
  and — only for a genuinely different transport dialect — one adapter
  class. No per-model code anywhere.

Following the execution-side convention (``ecp.console``,
``ecp.runtime_adapters``, ``ecp.onboarding``) this module is imported
explicitly and is not part of the lightweight ``ecp`` package root import
graph.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from .credentials import SecretLease


#: Outcome codes for one discovery probe (non-secret diagnostics only).
PROBE_IDENTIFIED = "IDENTIFIED"
PROBE_CREDENTIAL_REJECTED = "CREDENTIAL_REJECTED"
PROBE_UNREACHABLE = "UNREACHABLE"
PROBE_NOT_SUPPORTED = "NOT_SUPPORTED"
PROBE_MALFORMED = "MALFORMED"
PROBE_NO_MODELS = "NO_MODELS"
PROBE_RATE_LIMITED = "RATE_LIMITED"

#: Report statuses (owner order §2: never guess — UNKNOWN is explicit).
STATUS_DISCOVERED = "DISCOVERED"
STATUS_DISCOVERY_FAILED = "DISCOVERY_FAILED"
IDENTIFICATION_IDENTIFIED = "IDENTIFIED"
IDENTIFICATION_UNKNOWN = "UNKNOWN"

#: Default probe timeout (seconds).
DEFAULT_PROBE_TIMEOUT_SECONDS = 15.0

#: Upper bound on models carried in one report (browser response safety).
MAX_MODELS_PER_REPORT = 250

_DISCOVERY_ID = re.compile(r"^ECP-DISCOVERY-[A-Za-z0-9][A-Za-z0-9._:-]*$")
_HEADER_NAME = re.compile(r"^[A-Za-z0-9-]+$")
_AUTH_STYLES = frozenset({"bearer", "header"})
_RESPONSE_SHAPES = frozenset({"openai-models", "gemini-models", "anthropic-models"})
_MODEL_ID = re.compile(r"^[^\s\x00-\x1f\x7f]{1,128}$")
_PATH_SAFE_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")


class DiscoveryError(ValueError):
    """Base error for discovery-fabric failures (diagnostic, secret-free)."""


class InvalidDiscoveryDescriptor(DiscoveryError):
    """A discovery descriptor is malformed or internally inconsistent."""


class UnknownDiscoveryDescriptor(DiscoveryError):
    """A requested discovery descriptor is not registered."""


class InvalidCustomEndpoint(DiscoveryError):
    """An owner-supplied endpoint is not a usable http(s) base URL."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _nonempty(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidDiscoveryDescriptor(f"{name} must be a non-empty string")
    return value


# ---------------------------------------------------------------------------
# Descriptor contract (pure data — one provider dialect recipe)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveryDescriptor:
    """One provider-neutral discovery recipe.

    Everything provider-specific about HOW to ask for a model list lives
    here as data: candidate base URLs, the models path, the credential
    header style, and the response shape name. The probing mechanics in
    :class:`ProviderDiscoveryService` never branch on provider identity.
    """

    discovery_id: str
    display_name: str
    protocol: str
    adapter_kind: str
    endpoint_template: str
    base_urls: tuple[str, ...]
    models_path: str
    auth: Mapping[str, Any]
    response_shape: str
    provider_document: Mapping[str, Any]
    adapter_document: Mapping[str, Any]
    model_in_path: bool = False
    requires_base_url: bool = False

    def __post_init__(self) -> None:
        _nonempty("discovery_id", self.discovery_id)
        if not _DISCOVERY_ID.fullmatch(self.discovery_id):
            raise InvalidDiscoveryDescriptor("discovery_id must match ^ECP-DISCOVERY-[A-Za-z0-9][A-Za-z0-9._:-]*$")
        _nonempty("display_name", self.display_name)
        _nonempty("protocol", self.protocol)
        _nonempty("adapter_kind", self.adapter_kind)
        _nonempty("endpoint_template", self.endpoint_template)
        _nonempty("models_path", self.models_path)
        if not self.endpoint_template.startswith("{base}") or "/" not in self.endpoint_template:
            raise InvalidDiscoveryDescriptor("endpoint_template must start with {base} and contain a path")
        if "{model}" in self.endpoint_template and not self.model_in_path:
            raise InvalidDiscoveryDescriptor("endpoint_template carries {model} but model_in_path is false")
        if self.model_in_path and "{model}" not in self.endpoint_template:
            raise InvalidDiscoveryDescriptor("model_in_path requires {model} in endpoint_template")
        if not isinstance(self.base_urls, tuple):
            raise InvalidDiscoveryDescriptor("base_urls must be a tuple of strings")
        for url in self.base_urls:
            _validate_endpoint_url(url, "base_urls entry")
        if self.requires_base_url and self.base_urls:
            raise InvalidDiscoveryDescriptor("requires_base_url descriptors carry no fixed base_urls")
        if not self.requires_base_url and not self.base_urls:
            raise InvalidDiscoveryDescriptor("at least one fixed base_url is required unless requires_base_url")
        auth = self.auth
        if not isinstance(auth, Mapping):
            raise InvalidDiscoveryDescriptor("auth must be a mapping")
        style = auth.get("style")
        if style not in _AUTH_STYLES:
            raise InvalidDiscoveryDescriptor("auth style must be 'bearer' or 'header'")
        if style == "header":
            header = auth.get("header")
            if not isinstance(header, str) or not _HEADER_NAME.fullmatch(header):
                raise InvalidDiscoveryDescriptor("auth header must be a valid HTTP header name")
            extra = auth.get("extra", {})
            if not isinstance(extra, Mapping):
                raise InvalidDiscoveryDescriptor("auth extra headers must be a mapping")
            for name, value in extra.items():
                if not isinstance(name, str) or not _HEADER_NAME.fullmatch(name):
                    raise InvalidDiscoveryDescriptor("auth extra header names must be valid HTTP header names")
                if not isinstance(value, str) or not value.strip():
                    raise InvalidDiscoveryDescriptor("auth extra header values must be non-empty strings")
        if self.response_shape not in _RESPONSE_SHAPES:
            raise InvalidDiscoveryDescriptor("response_shape must be one of: " + ", ".join(sorted(_RESPONSE_SHAPES)))
        for document_name, document in (("provider_document", self.provider_document), ("adapter_document", self.adapter_document)):
            if not isinstance(document, Mapping):
                raise InvalidDiscoveryDescriptor(f"{document_name} must be a mapping")

    def probe_url(self, base_url: str) -> str:
        return base_url.rstrip("/") + self.models_path

    def execution_endpoint(self, base_url: str, model_identifier: str) -> str:
        """The execution endpoint for one model at one discovered base."""
        if self.model_in_path:
            if not _PATH_SAFE_MODEL_ID.fullmatch(model_identifier):
                raise DiscoveryError(
                    "model identifier is not path-safe for this protocol"
                )
            return self.endpoint_template.format(base=base_url.rstrip("/"), model=model_identifier)
        return self.endpoint_template.format(base=base_url.rstrip("/"))

    def provider_id(self) -> str:
        return str(self.provider_document["provider_id"])

    def interface(self) -> str:
        return str(self.provider_document["interfaces"][0])

    def descriptors_view(self) -> dict[str, Any]:
        """Secret-free summary used by console UIs (registry-driven)."""
        return {
            "discovery_id": self.discovery_id,
            "display_name": self.display_name,
            "protocol": self.protocol,
            "adapter_kind": self.adapter_kind,
            "requires_base_url": self.requires_base_url,
            "fixed_endpoints": [urlparse(url).hostname or "" for url in self.base_urls],
        }


class DiscoveryRegistry:
    """Small registry of discovery descriptors (data recipes only)."""

    def __init__(self, descriptors: "list[DiscoveryDescriptor] | None" = None) -> None:
        self._entries: dict[str, DiscoveryDescriptor] = {}
        for descriptor in descriptors or []:
            self.register(descriptor)

    def register(self, descriptor: DiscoveryDescriptor) -> None:
        if not isinstance(descriptor, DiscoveryDescriptor):
            raise InvalidDiscoveryDescriptor("only DiscoveryDescriptor instances are registrable")
        if descriptor.discovery_id in self._entries:
            raise InvalidDiscoveryDescriptor(f"discovery descriptor already registered: {descriptor.discovery_id}")
        self._entries[descriptor.discovery_id] = descriptor

    def get(self, discovery_id: str) -> DiscoveryDescriptor:
        try:
            return self._entries[discovery_id]
        except KeyError as exc:
            raise UnknownDiscoveryDescriptor(f"unknown discovery descriptor {discovery_id}") from exc

    def descriptors(self) -> "list[DiscoveryDescriptor]":
        return [self._entries[key] for key in sorted(self._entries)]

    def __len__(self) -> int:
        return len(self._entries)

    def view(self) -> "list[dict[str, Any]]":
        return [descriptor.descriptors_view() for descriptor in self.descriptors()]


# ---------------------------------------------------------------------------
# Report contracts (provider-neutral representation, owner order §7)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveredModel:
    """One discovered model in the provider-neutral representation."""

    model_identifier: str
    display_name: str
    capabilities: tuple[str, ...] = ()
    discovered_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.model_identifier, str) or not _MODEL_ID.fullmatch(self.model_identifier):
            raise DiscoveryError("discovered model identifier is invalid")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise DiscoveryError("discovered model display name is invalid")
        if not all(isinstance(item, str) and item.strip() for item in self.capabilities):
            raise DiscoveryError("discovered model capabilities must be non-empty strings")

    def to_document(self, *, provider_id: str, adapter_kind: str, protocol: str, availability: str = "AVAILABLE") -> dict[str, Any]:
        return {
            "provider": provider_id,
            "model_identifier": self.model_identifier,
            "display_name": self.display_name,
            "capabilities": list(self.capabilities),
            "availability": availability,
            "discovered_at": self.discovered_at,
            "adapter_kind": adapter_kind,
            "protocol": protocol,
        }


@dataclass(frozen=True)
class DiscoveryProbe:
    """One probe attempt against one candidate endpoint (non-secret)."""

    discovery_id: str
    base_url: str
    outcome: str
    detail: str

    def to_document(self) -> dict[str, str]:
        return {
            "discovery_id": self.discovery_id,
            "base_url": self.base_url,
            "outcome": self.outcome,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DiscoveryReport:
    """The outcome of one unified discovery run (identification or UNKNOWN)."""

    status: str
    discovered_at: str
    probes: tuple[DiscoveryProbe, ...]
    discovery_id: str | None = None
    display_name: str | None = None
    protocol: str | None = None
    adapter_kind: str | None = None
    provider_id: str | None = None
    provider_display_name: str | None = None
    matched_base_url: str | None = None
    models: tuple[DiscoveredModel, ...] = ()
    models_truncated: bool = False
    total_models: int = 0
    identification: str = IDENTIFICATION_UNKNOWN
    identification_basis: str = "no candidate endpoint produced a parseable model list"

    def to_document(self) -> dict[str, Any]:
        provider_block: dict[str, Any] = {
            "identification": self.identification,
            "identification_basis": self.identification_basis,
        }
        if self.provider_id is not None:
            provider_block["provider_id"] = self.provider_id
            provider_block["display_name"] = self.provider_display_name
        adapter_block: dict[str, Any] = {}
        if self.adapter_kind is not None:
            adapter_block = {
                "adapter_kind": self.adapter_kind,
                "protocol": self.protocol,
                "discovery_id": self.discovery_id,
                "endpoint_base": self.matched_base_url,
            }
        return {
            "status": self.status,
            "discovered_at": self.discovered_at,
            "identification": self.identification,
            "provider": provider_block,
            "adapter": adapter_block,
            "models": [
                model.to_document(
                    provider_id=self.provider_id or "UNKNOWN",
                    adapter_kind=self.adapter_kind or "UNKNOWN",
                    protocol=self.protocol or "UNKNOWN",
                )
                for model in self.models
            ],
            "models_truncated": self.models_truncated,
            "total_models": self.total_models,
            "probes": [probe.to_document() for probe in self.probes],
        }


# ---------------------------------------------------------------------------
# Response shape parsers (keyed by SHAPE, never by provider identity)
# ---------------------------------------------------------------------------


def _parse_openai_models(payload: Any) -> "list[tuple[str, str, tuple[str, ...]]]":
    """Parse the OpenAI-compatible ``{"data": [{"id": ...}]}`` model list."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise DiscoveryError("openai-models response must carry a 'data' list")
    models: "list[tuple[str, str, tuple[str, ...]]]" = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            continue
        # Entries that declare a non-model object type are not models; entries
        # without an object field (some compatible gateways) are kept.
        if item.get("object") not in (None, "model"):
            continue
        identifier = item.get("id")
        if isinstance(identifier, str) and _MODEL_ID.fullmatch(identifier):
            owned_by = item.get("owned_by")
            capabilities: tuple[str, ...] = ()
            if isinstance(owned_by, str) and owned_by.strip():
                capabilities = (f"owned_by:{owned_by}",)
            models.append((identifier, identifier, capabilities))
    return models


def _parse_gemini_models(payload: Any) -> "list[tuple[str, str, tuple[str, ...]]]":
    """Parse the Gemini ``{"models": [{"name": "models/...", ...}]}`` list."""
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise DiscoveryError("gemini-models response must carry a 'models' list")
    models: "list[tuple[str, str, tuple[str, ...]]]" = []
    for item in payload["models"]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        identifier = name.split("/", 1)[-1] if "/" in name else name
        if not _MODEL_ID.fullmatch(identifier):
            continue
        display = item.get("displayName")
        display_name = display.strip() if isinstance(display, str) and display.strip() else identifier
        methods = item.get("supportedGenerationMethods")
        capabilities = tuple(
            method for method in methods if isinstance(method, str) and method.strip()
        ) if isinstance(methods, list) else ()
        models.append((identifier, display_name, capabilities))
    return models


def _parse_anthropic_models(payload: Any) -> "list[tuple[str, str, tuple[str, ...]]]":
    """Parse the Anthropic ``{"data": [{"id": ..., "display_name": ...}]}`` list."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise DiscoveryError("anthropic-models response must carry a 'data' list")
    models: "list[tuple[str, str, tuple[str, ...]]]" = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            continue
        identifier = item.get("id")
        if isinstance(identifier, str) and _MODEL_ID.fullmatch(identifier):
            display = item.get("display_name")
            display_name = display.strip() if isinstance(display, str) and display.strip() else identifier
            models.append((identifier, display_name, ()))
    return models


_RESPONSE_PARSERS: dict[str, Callable[[Any], "list[tuple[str, str, tuple[str, ...]]]"]] = {
    "openai-models": _parse_openai_models,
    "gemini-models": _parse_gemini_models,
    "anthropic-models": _parse_anthropic_models,
}


#: Models whose capabilities must include this method when the dialect
#: advertises generation methods (the execution adapter calls it).
_GENERATION_CAPABILITY_FILTER = {
    "gemini-models": "generateContent",
}


# ---------------------------------------------------------------------------
# Default probe transport (GET; injectable for offline tests)
# ---------------------------------------------------------------------------


def _get_json(url: str, headers: Mapping[str, str], timeout: float) -> tuple[int, bytes]:
    request_ = urllib_request.Request(url, headers=dict(headers), method="GET")
    try:
        with urllib_request.urlopen(request_, timeout=timeout) as response:
            return response.status, response.read()
    except urllib_error.HTTPError as exc:
        return exc.code, exc.read()


def _transport_failure_detail(url: str, error: BaseException) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "unknown-host"
    reason = getattr(error, "reason", None)
    detail = str(reason) if reason is not None else str(error)
    detail = detail.replace("\r", " ").replace("\n", " ").strip()
    if not detail:
        detail = error.__class__.__name__
    return f"host={host} reason={detail[:240]}"


def _validate_endpoint_url(url: Any, name: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise InvalidDiscoveryDescriptor(f"{name} must be a non-empty string")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidDiscoveryDescriptor(f"{name} must be an absolute http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise InvalidDiscoveryDescriptor(f"{name} must not carry userinfo, query or fragment")
    return url


def validate_custom_base_url(url: Any) -> str:
    """Validate an owner-supplied discovery/execution base URL.

    Allows loopback and private hosts (local model servers are legitimate
    targets) but rejects credential-in-URL smuggling, non-http(s) schemes
    and cloud metadata endpoints.
    """
    if not isinstance(url, str) or not url.strip():
        raise InvalidCustomEndpoint("custom endpoint must be a non-empty string")
    if len(url) > 512:
        raise InvalidCustomEndpoint("custom endpoint is too long")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidCustomEndpoint("custom endpoint must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise InvalidCustomEndpoint("custom endpoint must not embed credentials in the URL")
    if parsed.query or parsed.fragment:
        raise InvalidCustomEndpoint("custom endpoint must not carry a query or fragment")
    host = parsed.hostname.lower()
    if host == "metadata.google.internal" or host.startswith("169.254."):
        raise InvalidCustomEndpoint("cloud metadata endpoints are not valid model providers")
    return url.rstrip("/")


# ---------------------------------------------------------------------------
# The unified discovery service (owner order §2)
# ---------------------------------------------------------------------------


class ProviderDiscoveryService:
    """One unified provider/model discovery mechanism over descriptors.

    Given a released credential lease, probes the registered descriptor
    dialects and reports the identified provider and its available models.
    Never guesses: an unidentified credential yields ``DISCOVERY_FAILED``
    with identification ``UNKNOWN`` and per-probe diagnostics.
    """

    def __init__(
        self,
        registry: DiscoveryRegistry,
        *,
        transport: Callable[[str, Mapping[str, str], float], tuple[int, bytes]] | None = None,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
        max_models: int = MAX_MODELS_PER_REPORT,
    ) -> None:
        self._registry = registry
        self._transport = transport or _get_json
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout = timeout_seconds
        self._max_models = max_models

    @property
    def registry(self) -> DiscoveryRegistry:
        return self._registry

    def descriptors_view(self) -> "list[dict[str, Any]]":
        return self._registry.view()

    def discover(
        self,
        lease: SecretLease,
        *,
        provider_hint: str | None = None,
        custom_base_url: str | None = None,
    ) -> DiscoveryReport:
        """Run one unified discovery pass and return the honest report."""
        candidates = self._candidates(provider_hint, custom_base_url)
        discovered_at = self._now()
        probes: list[DiscoveryProbe] = []
        for descriptor, base_url in candidates:
            outcome, detail, models = self._probe(descriptor, base_url, lease)
            probes.append(DiscoveryProbe(descriptor.discovery_id, base_url, outcome, detail))
            if outcome == PROBE_IDENTIFIED:
                return self._report_for_match(
                    descriptor, base_url, models, discovered_at, probes
                )
        return DiscoveryReport(
            status=STATUS_DISCOVERY_FAILED,
            discovered_at=discovered_at,
            probes=tuple(probes),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _candidates(
        self, provider_hint: str | None, custom_base_url: str | None
    ) -> "list[tuple[DiscoveryDescriptor, str]]":
        if custom_base_url is not None:
            custom_base_url = validate_custom_base_url(custom_base_url)
        if provider_hint is not None:
            if not isinstance(provider_hint, str) or not provider_hint.strip():
                raise DiscoveryError("provider hint must be a non-empty string or null")
            descriptor = self._registry.get(provider_hint)
            if custom_base_url is not None:
                return [(descriptor, custom_base_url)]
            if descriptor.requires_base_url:
                raise DiscoveryError(
                    f"discovery descriptor {descriptor.discovery_id} requires an explicit endpoint"
                )
            return [(descriptor, base) for base in descriptor.base_urls]
        if custom_base_url is not None:
            for descriptor in self._registry.descriptors():
                if descriptor.requires_base_url:
                    return [(descriptor, custom_base_url)]
            raise DiscoveryError("no registered descriptor accepts a custom endpoint")
        return [
            (descriptor, base)
            for descriptor in self._registry.descriptors()
            if not descriptor.requires_base_url
            for base in descriptor.base_urls
        ]

    def _probe(
        self, descriptor: DiscoveryDescriptor, base_url: str, lease: SecretLease
    ) -> "tuple[str, str, list[tuple[str, str, tuple[str, ...]]]]":
        url = descriptor.probe_url(base_url)
        headers = _probe_headers(descriptor.auth, lease.value)
        try:
            status, body = self._transport(url, headers, self._timeout)
        except (OSError, urllib_error.URLError, TimeoutError) as exc:
            return PROBE_UNREACHABLE, f"connection failed {_transport_failure_detail(url, exc)}", []
        if status in {401, 403}:
            return PROBE_CREDENTIAL_REJECTED, f"endpoint rejected the credential (HTTP {status})", []
        if status == 429:
            return PROBE_RATE_LIMITED, "endpoint is rate limiting the probe (HTTP 429)", []
        if status != 200:
            return PROBE_NOT_SUPPORTED, f"endpoint does not serve the models path (HTTP {status})", []
        try:
            payload = json_loads(body)
        except DiscoveryError:
            return PROBE_MALFORMED, "response body is not valid JSON", []
        parser = _RESPONSE_PARSERS[descriptor.response_shape]
        try:
            models = parser(payload)
        except DiscoveryError as exc:
            return PROBE_MALFORMED, f"response does not match the {descriptor.response_shape} shape: {exc}", []
        filter_method = _GENERATION_CAPABILITY_FILTER.get(descriptor.response_shape)
        if filter_method is not None:
            models = [item for item in models if filter_method in item[2]]
        if not models:
            return PROBE_NO_MODELS, "endpoint returned no usable models", []
        return PROBE_IDENTIFIED, f"identified via {descriptor.response_shape} model list", models

    def _report_for_match(
        self,
        descriptor: DiscoveryDescriptor,
        base_url: str,
        models: "list[tuple[str, str, tuple[str, ...]]]",
        discovered_at: str,
        probes: "list[DiscoveryProbe]",
    ) -> DiscoveryReport:
        total = len(models)
        truncated = total > self._max_models
        kept = models[: self._max_models]
        kept.sort(key=lambda item: item[0])
        discovered = tuple(
            DiscoveredModel(
                model_identifier=identifier,
                display_name=display,
                capabilities=capabilities,
                discovered_at=discovered_at,
            )
            for identifier, display, capabilities in kept
        )
        return DiscoveryReport(
            status=STATUS_DISCOVERED,
            discovered_at=discovered_at,
            probes=tuple(probes),
            discovery_id=descriptor.discovery_id,
            display_name=descriptor.display_name,
            protocol=descriptor.protocol,
            adapter_kind=descriptor.adapter_kind,
            provider_id=descriptor.provider_id(),
            provider_display_name=descriptor.display_name,
            matched_base_url=base_url,
            models=discovered,
            models_truncated=truncated,
            total_models=total,
            identification=IDENTIFICATION_IDENTIFIED,
            identification_basis=(
                f"the endpoint at {urlparse(base_url).hostname or 'unknown-host'} answered "
                f"the {descriptor.response_shape} models query with a parseable model list"
            ),
        )

    def _now(self) -> str:
        return (
            self._clock()
            .astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )


def _probe_headers(auth: Mapping[str, Any], lease_value: str) -> dict[str, str]:
    style = auth.get("style")
    headers: dict[str, str] = {"Accept": "application/json"}
    if style == "bearer":
        headers["Authorization"] = f"Bearer {lease_value}"
    elif style == "header":
        headers[str(auth["header"])] = lease_value
        extra = auth.get("extra", {})
        for name, value in extra.items():
            headers[str(name)] = str(value)
    else:  # pragma: no cover - descriptor validation rejects earlier
        raise DiscoveryError("unsupported auth style")
    return headers


def json_loads(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise DiscoveryError("response body is not valid JSON") from exc


# ---------------------------------------------------------------------------
# Built-in descriptor set (DATA — the provider spectrum of this phase)
# ---------------------------------------------------------------------------
#
# Adding one more provider is a new entry here (plus, only for a genuinely
# different transport dialect, one adapter class in the runtime seam). No
# per-model entries exist anywhere.

_BUILTIN_DESCRIPTOR_DATA: "list[dict[str, Any]]" = [
    {
        "discovery_id": "ECP-DISCOVERY-OPENAI-RESPONSES",
        "display_name": "OpenAI",
        "protocol": "openai-responses",
        "adapter_kind": "openai-responses",
        "endpoint_template": "{base}/responses",
        "base_urls": ("https://api.openai.com/v1",),
        "models_path": "/models",
        "auth": {"style": "bearer"},
        "response_shape": "openai-models",
        "provider_document": {
            "ecp_object": "provider",
            "provider_id": "ECP-PROVIDER-OPENAI",
            "provider_version": "1.0.0",
            "interfaces": ["openai-responses-api"],
            "status": "active",
            "description": "OpenAI Responses API provider (discovered via the /v1/models endpoint).",
        },
        "adapter_document": {
            "ecp_object": "adapter",
            "adapter_id": "ECP-ADAPTER-OPENAI-RESPONSES",
            "adapter_version": "1.0.0",
            "provider_id": "ECP-PROVIDER-OPENAI",
            "provider_interface": "openai-responses-api",
            "supported_system_kinds": ["model-only"],
            "supported_capabilities": ["text-generation"],
            "status": "active",
            "description": "OpenAI Responses API conformance adapter (execution through the universal fabric).",
        },
    },
    {
        "discovery_id": "ECP-DISCOVERY-ANTHROPIC-MESSAGES",
        "display_name": "Anthropic",
        "protocol": "anthropic-messages",
        "adapter_kind": "anthropic-messages",
        "endpoint_template": "{base}/messages",
        "base_urls": ("https://api.anthropic.com/v1",),
        "models_path": "/models",
        "auth": {"style": "header", "header": "x-api-key", "extra": {"anthropic-version": "2023-06-01"}},
        "response_shape": "anthropic-models",
        "provider_document": {
            "ecp_object": "provider",
            "provider_id": "ECP-PROVIDER-ANTHROPIC",
            "provider_version": "1.0.0",
            "interfaces": ["anthropic-messages-api"],
            "status": "active",
            "description": "Anthropic Messages API provider (discovered via the /v1/models endpoint).",
        },
        "adapter_document": {
            "ecp_object": "adapter",
            "adapter_id": "ECP-ADAPTER-ANTHROPIC-MESSAGES",
            "adapter_version": "1.0.0",
            "provider_id": "ECP-PROVIDER-ANTHROPIC",
            "provider_interface": "anthropic-messages-api",
            "supported_system_kinds": ["model-only"],
            "supported_capabilities": ["text-generation"],
            "status": "active",
            "description": "Anthropic Messages API conformance adapter (execution through the universal fabric).",
        },
    },
    {
        "discovery_id": "ECP-DISCOVERY-GEMINI-GENERATE-CONTENT",
        "display_name": "Google Gemini",
        "protocol": "gemini-generate-content",
        "adapter_kind": "gemini-generate-content",
        "endpoint_template": "{base}/models/{model}:generateContent",
        "base_urls": ("https://generativelanguage.googleapis.com/v1beta",),
        "models_path": "/models",
        "auth": {"style": "header", "header": "x-goog-api-key"},
        "response_shape": "gemini-models",
        "model_in_path": True,
        "provider_document": {
            "ecp_object": "provider",
            "provider_id": "ECP-PROVIDER-GEMINI",
            "provider_version": "1.0.0",
            "interfaces": ["gemini-generate-content-api"],
            "status": "active",
            "description": "Google Gemini API provider (discovered via the /v1beta/models endpoint).",
        },
        "adapter_document": {
            "ecp_object": "adapter",
            "adapter_id": "ECP-ADAPTER-GEMINI-GENERATE-CONTENT",
            "adapter_version": "1.0.0",
            "provider_id": "ECP-PROVIDER-GEMINI",
            "provider_interface": "gemini-generate-content-api",
            "supported_system_kinds": ["model-only"],
            "supported_capabilities": ["text-generation"],
            "status": "active",
            "description": "Gemini generateContent conformance adapter (execution through the universal fabric).",
        },
    },
    {
        "discovery_id": "ECP-DISCOVERY-GROQ-CHAT-COMPLETIONS",
        "display_name": "Groq",
        "protocol": "openai-chat-completions",
        "adapter_kind": "openrouter-chat-completions",
        "endpoint_template": "{base}/chat/completions",
        "base_urls": ("https://api.groq.com/openai/v1",),
        "models_path": "/models",
        "auth": {"style": "bearer"},
        "response_shape": "openai-models",
        "provider_document": {
            "ecp_object": "provider",
            "provider_id": "ECP-PROVIDER-GROQ",
            "provider_version": "1.0.0",
            "interfaces": ["groq-chat-completions-api"],
            "status": "active",
            "description": "Groq OpenAI-compatible chat-completions provider (discovered via the /openai/v1/models endpoint).",
        },
        "adapter_document": {
            "ecp_object": "adapter",
            "adapter_id": "ECP-ADAPTER-GROQ-CHAT-COMPLETIONS",
            "adapter_version": "1.0.0",
            "provider_id": "ECP-PROVIDER-GROQ",
            "provider_interface": "groq-chat-completions-api",
            "supported_system_kinds": ["model-only"],
            "supported_capabilities": ["text-generation"],
            "status": "active",
            "description": "Groq chat-completions conformance adapter over the generic chat-completions dialect.",
        },
    },
    {
        "discovery_id": "ECP-DISCOVERY-OPENROUTER-CHAT-COMPLETIONS",
        "display_name": "OpenRouter",
        "protocol": "openai-chat-completions",
        "adapter_kind": "openrouter-chat-completions",
        "endpoint_template": "{base}/chat/completions",
        "base_urls": ("https://openrouter.ai/api/v1",),
        "models_path": "/models",
        "auth": {"style": "bearer"},
        "response_shape": "openai-models",
        "provider_document": {
            "ecp_object": "provider",
            "provider_id": "ECP-PROVIDER-OPENROUTER",
            "provider_version": "1.0.0",
            "interfaces": ["openrouter-chat-completions-api"],
            "status": "active",
            "description": "OpenRouter OpenAI-compatible chat-completions provider (discovered via the /api/v1/models endpoint).",
        },
        "adapter_document": {
            "ecp_object": "adapter",
            "adapter_id": "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS",
            "adapter_version": "1.0.0",
            "provider_id": "ECP-PROVIDER-OPENROUTER",
            "provider_interface": "openrouter-chat-completions-api",
            "supported_system_kinds": ["model-only"],
            "supported_capabilities": ["text-generation"],
            "status": "active",
            "description": "OpenRouter chat-completions conformance adapter over the generic chat-completions dialect.",
        },
    },
    {
        "discovery_id": "ECP-DISCOVERY-CUSTOM-OPENAI-COMPATIBLE",
        "display_name": "Custom OpenAI-compatible endpoint",
        "protocol": "openai-chat-completions",
        "adapter_kind": "openrouter-chat-completions",
        "endpoint_template": "{base}/chat/completions",
        "base_urls": (),
        "models_path": "/models",
        "auth": {"style": "bearer"},
        "response_shape": "openai-models",
        "requires_base_url": True,
        "provider_document": {
            "ecp_object": "provider",
            "provider_id": "ECP-PROVIDER-CUSTOM-COMPATIBLE",
            "provider_version": "1.0.0",
            "interfaces": ["custom-chat-completions-api"],
            "status": "active",
            "description": "Owner-declared OpenAI-compatible endpoint (any host the owner supplies; loopback and private hosts are allowed for local model servers).",
        },
        "adapter_document": {
            "ecp_object": "adapter",
            "adapter_id": "ECP-ADAPTER-CUSTOM-CHAT-COMPLETIONS",
            "adapter_version": "1.0.0",
            "provider_id": "ECP-PROVIDER-CUSTOM-COMPATIBLE",
            "provider_interface": "custom-chat-completions-api",
            "supported_system_kinds": ["model-only"],
            "supported_capabilities": ["text-generation"],
            "status": "active",
            "description": "Generic chat-completions adapter for owner-declared OpenAI-compatible endpoints.",
        },
    },
]


def builtin_discovery_registry() -> DiscoveryRegistry:
    """The built-in descriptor registry (one entry per supported dialect)."""
    return DiscoveryRegistry(
        [DiscoveryDescriptor(**{**entry}) for entry in _BUILTIN_DESCRIPTOR_DATA]
    )


__all__ = [
    "DiscoveryDescriptor",
    "DiscoveryRegistry",
    "DiscoveryReport",
    "DiscoveryError",
    "DiscoveredModel",
    "DiscoveryProbe",
    "InvalidCustomEndpoint",
    "InvalidDiscoveryDescriptor",
    "ProviderDiscoveryService",
    "UnknownDiscoveryDescriptor",
    "builtin_discovery_registry",
    "validate_custom_base_url",
    "MAX_MODELS_PER_REPORT",
    "STATUS_DISCOVERED",
    "STATUS_DISCOVERY_FAILED",
    "IDENTIFICATION_IDENTIFIED",
    "IDENTIFICATION_UNKNOWN",
]
