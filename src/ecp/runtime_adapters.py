"""Runtime adapter boundary for controlled external execution.

The metadata registry in :mod:`ecp.adapters` remains the source of registered
adapter identities. This module contains only the runtime dispatch seam and
provider-specific transport implementation; it never changes authorization or
credential ownership.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse


class RuntimeAdapterError(Exception):
    """Base class for controlled runtime adapter failures."""


class RuntimeAdapterUnavailable(RuntimeAdapterError):
    """The requested runtime adapter is not registered or enabled."""


class RuntimeAdapterBindingError(RuntimeAdapterError):
    """The runtime adapter does not match the registered provider binding."""


class RuntimeAdapterTransportError(RuntimeAdapterError):
    """The external transport failed without exposing request credentials."""


@dataclass(frozen=True)
class RuntimeAdapterRegistration:
    adapter_id: str
    provider: str
    adapter: Any
    enabled: bool = True


class RuntimeAdapterRegistry:
    """Small provider-neutral registry for executable adapter instances."""

    def __init__(self, adapters: Mapping[str, Any] | None = None) -> None:
        self._entries: dict[str, RuntimeAdapterRegistration] = {}
        for adapter_id, adapter in (adapters or {}).items():
            self.register(adapter_id, adapter)

    def register(self, adapter_id: str, adapter: Any, *, enabled: bool = True) -> None:
        declared = getattr(adapter, "adapter_id", adapter_id)
        provider = getattr(adapter, "provider", "")
        if declared not in {adapter_id, "unknown", "unconfigured"} or not isinstance(provider, str):
            raise ValueError("runtime adapter identity is invalid")
        if adapter_id in self._entries:
            raise ValueError(f"runtime adapter already registered: {adapter_id}")
        self._entries[adapter_id] = RuntimeAdapterRegistration(adapter_id, provider, adapter, enabled)

    def get(self, adapter_id: str, default: Any = None) -> Any:
        entry = self._entries.get(adapter_id)
        return default if entry is None else entry.adapter

    def resolve(self, adapter_id: str, provider: str) -> Any:
        entry = self._entries.get(adapter_id)
        if entry is None or not entry.enabled:
            raise RuntimeAdapterUnavailable(f"runtime adapter {adapter_id} is unavailable")
        if entry.provider not in {"", "unknown", "unconfigured"} and entry.provider != provider:
            raise RuntimeAdapterBindingError("runtime adapter provider binding mismatch")
        return entry.adapter

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


class OpenAIResponsesAdapter:
    """One controlled OpenAI Responses API conformance implementation.

    The API key is supplied only as a ``SecretLease`` by the execution layer.
    The adapter stores no credential and returns a small normalized result.
    """

    provider = "example-provider"
    adapter_id = "example-adapter"

    def __init__(
        self,
        *,
        model: str,
        endpoint: str,
        provider: str = "ECP-PROVIDER-OPENAI",
        adapter_id: str = "ECP-ADAPTER-OPENAI-RESPONSES",
        transport: Callable[[str, Mapping[str, str], bytes, float], tuple[int, bytes]] | None = None,
        prompt: str = "ECP controlled conformance probe. Reply with exactly: ECP-CONFORMANCE-OK",
    ) -> None:
        if not model or not endpoint:
            raise ValueError("model and endpoint are required")
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.provider = provider
        self.adapter_id = adapter_id
        self.prompt = prompt
        self._transport = transport or _post_json

    def execute(self, lease: Any, request: Mapping[str, str]) -> Mapping[str, Any]:
        payload = json.dumps({"model": self.model, "input": self.prompt}).encode("utf-8")
        headers = {"Authorization": f"Bearer {lease.value}", "Content-Type": "application/json"}
        try:
            status, body = self._transport(self.endpoint, headers, payload, 30.0)
        except (OSError, urllib_error.URLError, TimeoutError) as exc:
            raise RuntimeAdapterTransportError(_transport_failure_message(self.endpoint, exc)) from exc
        if status < 200 or status >= 300:
            if status in {401, 403}:
                category = "PROVIDER_AUTHENTICATION_FAILED"
            elif status == 408 or status == 504:
                category = "PROVIDER_TIMEOUT"
            else:
                category = "PROVIDER_REQUEST_FAILED"
            raise RuntimeAdapterTransportError(category)
        try:
            response = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeAdapterTransportError("MALFORMED_PROVIDER_RESPONSE") from exc
        output = _response_text(response)
        if not output:
            raise RuntimeAdapterTransportError("MALFORMED_PROVIDER_RESPONSE")
        return {
            "provider_status": "RECEIVED",
            "response_id": response.get("id") if isinstance(response, dict) else None,
            "model": self.model,
            "output_text": output,
            "request_id": request["request_id"],
        }


def _post_json(endpoint: str, headers: Mapping[str, str], payload: bytes, timeout: float) -> tuple[int, bytes]:
    req = urllib_request.Request(endpoint, data=payload, headers=dict(headers), method="POST")
    with urllib_request.urlopen(req, timeout=timeout) as response:
        return response.status, response.read()


def _transport_failure_message(endpoint: str, error: BaseException) -> str:
    """Return actionable transport diagnostics without request secrets."""
    parsed = urlparse(endpoint)
    host = parsed.hostname or "unknown-host"
    reason = getattr(error, "reason", None)
    if isinstance(reason, BaseException):
        detail = str(reason)
    elif reason is not None:
        detail = str(reason)
    else:
        detail = str(error)
    detail = detail.replace("\r", " ").replace("\n", " ").strip()
    if not detail:
        detail = error.__class__.__name__
    return f"PROVIDER_CONNECTION_FAILED host={host} reason={detail[:240]}"


def _response_text(response: Any) -> str | None:
    if isinstance(response, dict) and isinstance(response.get("output_text"), str):
        return response["output_text"].strip()
    if not isinstance(response, dict):
        return None
    chunks: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "".join(chunks).strip() or None


def openai_conformance_adapter(*, model: str | None = None, endpoint: str | None = None) -> OpenAIResponsesAdapter:
    """Build the isolated first-provider adapter from runtime configuration."""
    base = endpoint or os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
    return OpenAIResponsesAdapter(model=model or os.environ.get("ECP_CONFORMANCE_MODEL", "gpt-5-mini"), endpoint=f"{base}/responses")


__all__ = [
    "OpenAIResponsesAdapter",
    "RuntimeAdapterBindingError",
    "RuntimeAdapterError",
    "RuntimeAdapterRegistry",
    "RuntimeAdapterTransportError",
    "RuntimeAdapterUnavailable",
    "openai_conformance_adapter",
]
