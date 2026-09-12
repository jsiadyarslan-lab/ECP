"""Runtime adapter boundary for controlled external execution.

The metadata registry in :mod:`ecp.adapters` remains the source of registered
adapter identities. This module contains only the runtime dispatch seam and
provider-specific transport implementation; it never changes authorization or
credential ownership.
"""
from __future__ import annotations

import json
import os
import re
import time
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
    """The external transport failed without exposing request credentials.

    Carries the provider HTTP status code when the failure IS an HTTP-level
    response (401/403/429/5xx), so execution records can display the real
    provider verdict. Connection-level failures carry no status.
    """

    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


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


def _transport_facts(endpoint: str, http_status: int, started: float) -> dict[str, Any]:
    """Non-secret transport attribution for one real external HTTP call.

    Real executions must be distinguishable from offline demonstrations in
    every record, result and evidence document (owner order: UNIVERSAL REAL
    PROVIDER EXECUTION BINDING v1). These four scalar facts — the transport
    kind, the exact endpoint URL, the provider HTTP status and the round-trip
    latency — prove that the request left for the provider and what the
    provider answered. None of them is secret; the credential value is never
    included.
    """
    return {
        "transport_kind": "http",
        "endpoint": endpoint,
        "http_status": int(http_status),
        "latency_ms": max(0, int(round((time.monotonic() - started) * 1000))),
    }


def normalize_gateway_headers(
    token_header: str | None,
    bearer_value: str | None,
    extra_headers: Mapping[str, str] | None,
) -> "tuple[str | None, str | None, dict[str, str]]":
    """Validate and normalize owner-supplied non-secret gateway headers.

    Public seam over the same validation used by the adapter constructor, so
    discovery probes, console sessions and runtime adapters share ONE header
    placement contract. Returns the normalized
    ``(token_header, bearer_value, extra_headers)`` triple; deterministic
    ValueError on anything that could displace the credential or shadow
    the transport's own headers.
    """
    return _validate_gateway_headers(token_header, bearer_value, extra_headers)


class OpenAIResponsesAdapter:
    """One controlled OpenAI Responses API conformance implementation."""

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
        started = time.monotonic()
        try:
            status, body = self._transport(self.endpoint, headers, payload, 30.0)
        except (OSError, urllib_error.URLError, TimeoutError) as exc:
            raise RuntimeAdapterTransportError(_transport_failure_message(self.endpoint, exc)) from exc
        if status < 200 or status >= 300:
            if status in {401, 403}:
                category = "PROVIDER_AUTHENTICATION_FAILED"
            elif status == 408 or status == 504:
                category = "PROVIDER_TIMEOUT"
            elif status == 429:
                category = _rate_limit_failure_category(body)
            else:
                category = "PROVIDER_REQUEST_FAILED"
            raise RuntimeAdapterTransportError(category, http_status=status)
        try:
            response = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeAdapterTransportError("MALFORMED_PROVIDER_RESPONSE", http_status=status) from exc
        output = _response_text(response)
        if not output:
            raise RuntimeAdapterTransportError("MALFORMED_PROVIDER_RESPONSE", http_status=status)
        return {
            "provider_status": "RECEIVED",
            "response_id": response.get("id") if isinstance(response, dict) else None,
            "model": self.model,
            "output_text": output,
            "request_id": request["request_id"],
            **_transport_facts(self.endpoint, status, started),
        }


class GeminiGenerateContentAdapter:
    """One controlled Gemini generateContent conformance implementation."""

    provider = "example-provider"
    adapter_id = "example-adapter"

    def __init__(
        self,
        *,
        model: str,
        endpoint: str,
        provider: str = "ECP-PROVIDER-GEMINI",
        adapter_id: str = "ECP-ADAPTER-GEMINI-GENERATE-CONTENT",
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
        payload = json.dumps({"contents": [{"parts": [{"text": self.prompt}]}]}).encode("utf-8")
        headers = {"x-goog-api-key": lease.value, "Content-Type": "application/json"}
        started = time.monotonic()
        try:
            status, body = self._transport(self.endpoint, headers, payload, 30.0)
        except (OSError, urllib_error.URLError, TimeoutError) as exc:
            raise RuntimeAdapterTransportError(_transport_failure_message(self.endpoint, exc)) from exc
        if status < 200 or status >= 300:
            if status in {401, 403}:
                category = "PROVIDER_AUTHENTICATION_FAILED"
            elif status == 408 or status == 504:
                category = "PROVIDER_TIMEOUT"
            elif status == 429:
                category = "PROVIDER_RATE_LIMITED"
            else:
                category = "PROVIDER_REQUEST_FAILED"
            raise RuntimeAdapterTransportError(category, http_status=status)
        try:
            response = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeAdapterTransportError("MALFORMED_PROVIDER_RESPONSE", http_status=status) from exc
        output = _gemini_response_text(response)
        if not output:
            raise RuntimeAdapterTransportError("MALFORMED_PROVIDER_RESPONSE", http_status=status)
        return {
            "provider_status": "RECEIVED",
            "response_id": None,
            "model": self.model,
            "output_text": output,
            "request_id": request["request_id"],
            **_transport_facts(self.endpoint, status, started),
        }


class OpenRouterChatCompletionsAdapter:
    """One controlled OpenRouter Chat Completions API conformance implementation.

    The chat-completions HTTP dialect is shared by many OpenAI-compatible
    gateways. Some of those gateways place the released credential in a
    provider-specific header (instead of, or alongside, the standard bearer
    header) and require additional static, non-secret routing headers. To keep
    ONE protocol implementation for all of them (build once, configure many),
    the constructor accepts three OPTIONAL, provider-neutral configuration
    knobs; their values always come from target configuration and never from
    source code:

    * ``token_header`` — name of the header that carries the credential
      lease value (e.g. ``"X-Token"``). When ``None`` (default) the lease
      value is sent as ``Authorization: Bearer <lease>``, exactly the
      historical contract.
    * ``bearer_value`` — non-secret literal for the ``Authorization`` header
      when ``token_header`` is used (some gateways expect a public product
      marker there). Requires ``token_header``; never accepts the secret.
    * ``extra_headers`` — additional static, non-secret headers (routing or
      product markers) merged into the request.

    The secret itself continues to flow ONLY through the credential lease; it
    is never stored on the adapter and never appears in results or errors.
    """

    provider = "example-provider"
    adapter_id = "example-adapter"

    def __init__(
        self,
        *,
        model: str,
        endpoint: str,
        provider: str = "ECP-PROVIDER-OPENROUTER",
        adapter_id: str = "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS",
        transport: Callable[[str, Mapping[str, str], bytes, float], tuple[int, bytes]] | None = None,
        prompt: str = "ECP controlled conformance probe. Reply with exactly: ECP-CONFORMANCE-OK",
        token_header: str | None = None,
        bearer_value: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        if not model or not endpoint:
            raise ValueError("model and endpoint are required")
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.provider = provider
        self.adapter_id = adapter_id
        self.prompt = prompt
        self._transport = transport or _post_json
        self._token_header, self._bearer_value, self._extra_headers = _validate_gateway_headers(
            token_header, bearer_value, extra_headers
        )

    def execute(self, lease: Any, request: Mapping[str, str]) -> Mapping[str, Any]:
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": self.prompt}],
            "stream": False,
        }).encode("utf-8")
        headers = _chat_completions_headers(
            lease, self._token_header, self._bearer_value, self._extra_headers
        )
        started = time.monotonic()
        try:
            status, body = self._transport(self.endpoint, headers, payload, 30.0)
        except (OSError, urllib_error.URLError, TimeoutError) as exc:
            raise RuntimeAdapterTransportError(_transport_failure_message(self.endpoint, exc)) from exc
        if status < 200 or status >= 300:
            if status in {401, 403}:
                category = "PROVIDER_AUTHENTICATION_FAILED"
            elif status == 408 or status == 504:
                category = "PROVIDER_TIMEOUT"
            elif status == 429:
                category = "PROVIDER_RATE_LIMITED"
            else:
                category = "PROVIDER_REQUEST_FAILED"
            raise RuntimeAdapterTransportError(category, http_status=status)
        try:
            response = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeAdapterTransportError("MALFORMED_PROVIDER_RESPONSE", http_status=status) from exc
        output = _openrouter_response_text(response)
        if not output:
            raise RuntimeAdapterTransportError("MALFORMED_PROVIDER_RESPONSE", http_status=status)
        return {
            "provider_status": "RECEIVED",
            "response_id": response.get("id") if isinstance(response, dict) else None,
            "model": self.model,
            "output_text": output,
            "request_id": request["request_id"],
            **_transport_facts(self.endpoint, status, started),
        }


class AnthropicMessagesAdapter:
    """One controlled Anthropic Messages API conformance implementation.

    The Anthropic messages dialect places the released credential in the
    ``x-api-key`` header and requires the static, non-secret
    ``anthropic-version`` header. The secret itself continues to flow only
    through the credential lease; it is never stored on the adapter and
    never appears in results or errors.
    """

    provider = "example-provider"
    adapter_id = "example-adapter"

    def __init__(
        self,
        *,
        model: str,
        endpoint: str,
        provider: str = "ECP-PROVIDER-ANTHROPIC",
        adapter_id: str = "ECP-ADAPTER-ANTHROPIC-MESSAGES",
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
        payload = json.dumps({
            "model": self.model,
            "max_tokens": 64,
            "messages": [{"role": "user", "content": self.prompt}],
        }).encode("utf-8")
        headers = {
            "x-api-key": lease.value,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        started = time.monotonic()
        try:
            status, body = self._transport(self.endpoint, headers, payload, 30.0)
        except (OSError, urllib_error.URLError, TimeoutError) as exc:
            raise RuntimeAdapterTransportError(_transport_failure_message(self.endpoint, exc)) from exc
        if status < 200 or status >= 300:
            if status in {401, 403}:
                category = "PROVIDER_AUTHENTICATION_FAILED"
            elif status == 408 or status == 504:
                category = "PROVIDER_TIMEOUT"
            elif status == 429:
                category = "PROVIDER_RATE_LIMITED"
            else:
                category = "PROVIDER_REQUEST_FAILED"
            raise RuntimeAdapterTransportError(category, http_status=status)
        try:
            response = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeAdapterTransportError("MALFORMED_PROVIDER_RESPONSE", http_status=status) from exc
        output = _anthropic_response_text(response)
        if not output:
            raise RuntimeAdapterTransportError("MALFORMED_PROVIDER_RESPONSE", http_status=status)
        return {
            "provider_status": "RECEIVED",
            "response_id": response.get("id") if isinstance(response, dict) else None,
            "model": self.model,
            "output_text": output,
            "request_id": request["request_id"],
            **_transport_facts(self.endpoint, status, started),
        }


def _validate_gateway_headers(
    token_header: str | None,
    bearer_value: str | None,
    extra_headers: Mapping[str, str] | None,
) -> "tuple[str | None, str | None, dict[str, str]]":
    """Validate provider-neutral gateway header configuration.

    Returns the normalized ``(token_header, bearer_value, extra_headers)``
    triple. Rejects anything that could displace the credential, shadow the
    transport's own headers, or smuggle an empty value.
    """

    if token_header is not None and (not isinstance(token_header, str) or not _valid_header_name(token_header)):
        raise ValueError("token_header must be a valid HTTP header name")
    if bearer_value is not None:
        if token_header is None:
            raise ValueError("bearer_value requires token_header; without it the lease is the bearer credential")
        if not isinstance(bearer_value, str) or not bearer_value.strip():
            raise ValueError("bearer_value must be a non-empty non-secret string")
    normalized_extra: dict[str, str] = {}
    if extra_headers is not None:
        if not isinstance(extra_headers, Mapping):
            raise ValueError("extra_headers must be a mapping of header names to non-secret values")
        for name, value in extra_headers.items():
            if not isinstance(name, str) or not _valid_header_name(name):
                raise ValueError("extra_headers keys must be valid HTTP header names")
            if not isinstance(value, str) or not value.strip():
                raise ValueError("extra_headers values must be non-empty non-secret strings")
            normalized_extra[name] = value
    reserved = {name.lower() for name in ("Authorization", "Content-Type")}
    if token_header is not None and token_header.lower() in reserved:
        raise ValueError("token_header must not shadow the Authorization or Content-Type headers")
    for name in normalized_extra:
        if name.lower() in reserved:
            raise ValueError("extra_headers must not shadow the Authorization or Content-Type headers")
        if token_header is not None and name.lower() == token_header.lower():
            raise ValueError("extra_headers must not shadow the configured token_header")
    return token_header, bearer_value, normalized_extra


def _valid_header_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9-]+", name))


def _chat_completions_headers(
    lease: Any,
    token_header: str | None,
    bearer_value: str | None,
    extra_headers: Mapping[str, str],
) -> dict[str, str]:
    """Build request headers for the chat-completions dialect.

    Default (``token_header is None``): exactly the historical contract
    ``Authorization: Bearer <lease>`` plus JSON content type. With a
    configured ``token_header`` the lease value is placed in that header and
    the ``Authorization`` header carries the configured non-secret literal.
    """

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token_header is None:
        headers["Authorization"] = f"Bearer {lease.value}"
    else:
        headers["Authorization"] = f"Bearer {bearer_value}"
        headers[token_header] = lease.value
    headers.update(extra_headers)
    return headers


def _post_json(endpoint: str, headers: Mapping[str, str], payload: bytes, timeout: float) -> tuple[int, bytes]:
    req = urllib_request.Request(endpoint, data=payload, headers=dict(headers), method="POST")
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read()
    except urllib_error.HTTPError as exc:
        return exc.code, exc.read()


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


def _rate_limit_failure_category(body: bytes) -> str:
    """Classify HTTP 429 using only non-secret provider error identifiers."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "PROVIDER_RATE_LIMITED"
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return "PROVIDER_RATE_LIMITED"
    error_type = error.get("type")
    error_code = error.get("code")
    if error_type == "insufficient_quota" or error_code == "insufficient_quota":
        return "PROVIDER_QUOTA_EXCEEDED"
    return "PROVIDER_RATE_LIMITED"


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


def _gemini_response_text(response: Any) -> str | None:
    if not isinstance(response, dict):
        return None
    chunks: list[str] = []
    for candidate in response.get("candidates", []):
        content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        for part in content.get("parts", []) if isinstance(content, dict) else []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    return "".join(chunks).strip() or None


def _openrouter_response_text(response: Any) -> str | None:
    if not isinstance(response, dict):
        return None
    choices = response.get("choices", [])
    chunks: list[str] = []
    for choice in choices:
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
    return "".join(chunks).strip() or None


def _anthropic_response_text(response: Any) -> str | None:
    if not isinstance(response, dict):
        return None
    chunks: list[str] = []
    for block in response.get("content", []):
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            chunks.append(block["text"])
    return "".join(chunks).strip() or None


def openai_conformance_adapter(*, model: str | None = None, endpoint: str | None = None) -> OpenAIResponsesAdapter:
    base = endpoint or os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
    return OpenAIResponsesAdapter(model=model or os.environ.get("ECP_CONFORMANCE_MODEL", "gpt-5-mini"), endpoint=f"{base}/responses")


def gemini_conformance_adapter(*, model: str | None = None, endpoint: str | None = None) -> GeminiGenerateContentAdapter:
    model_name = model or os.environ.get("ECP_GEMINI_MODEL", "gemini-3.8-flash")
    base = endpoint or os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    return GeminiGenerateContentAdapter(model=model_name, endpoint=f"{base}/models/{model_name}:generateContent")


def openrouter_conformance_adapter(*, model: str | None = None, endpoint: str | None = None) -> OpenRouterChatCompletionsAdapter:
    model_name = model or os.environ.get("ECP_OPENROUTER_MODEL", "openrouter/free")
    base = endpoint or os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1").rstrip("/")
    return OpenRouterChatCompletionsAdapter(model=model_name, endpoint=f"{base}/chat/completions")


def anthropic_conformance_adapter(*, model: str | None = None, endpoint: str | None = None) -> AnthropicMessagesAdapter:
    model_name = model or os.environ.get("ECP_ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    base = endpoint or os.environ.get("ANTHROPIC_API_BASE", "https://api.anthropic.com/v1").rstrip("/")
    return AnthropicMessagesAdapter(model=model_name, endpoint=f"{base}/messages")


__all__ = [
    "AnthropicMessagesAdapter",
    "GeminiGenerateContentAdapter",
    "OpenAIResponsesAdapter",
    "OpenRouterChatCompletionsAdapter",
    "RuntimeAdapterBindingError",
    "RuntimeAdapterError",
    "RuntimeAdapterRegistry",
    "RuntimeAdapterTransportError",
    "RuntimeAdapterUnavailable",
    "gemini_conformance_adapter",
    "normalize_gateway_headers",
    "openai_conformance_adapter",
    "openrouter_conformance_adapter",
    "anthropic_conformance_adapter",
]
