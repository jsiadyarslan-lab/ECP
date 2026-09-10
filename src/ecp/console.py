"""Secure local execution console boundary for ECP.

This module is deliberately an integration shell around the existing credential
boundary. It never exposes secret values to HTTP responses or persisted records.
The default adapter is fail-closed: a real provider adapter must be registered
out-of-band before any external call can occur.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from .canonical import canonical_bytes
from .credentials import CredentialError, CredentialGateway, CredentialIdentity, SecretLease, SecretRedactionFilter, safe_exception_message
from .hashing import hash_document

DEFAULT_PORT = 8765
DEFAULT_CONSOLE_ORIGINS = (
    "https://jsiadyarslan-lab.github.io",
    "http://127.0.0.1:8766",
    "http://localhost:8766",
)
PAIRING_TTL_SECONDS = 600
POLL_INTERVAL_MS = 1500
EXECUTION_TIMEOUT_SECONDS = 120
_ALLOWED_REQUEST_KEYS = {"evaluation_id", "test_id", "system_id", "credential_ref", "request_id"}


class ConsoleError(Exception):
    """Safe, client-facing console error."""


class AuthorizationError(ConsoleError):
    pass


class AdapterUnavailable(ConsoleError):
    pass


class AdapterFailure(ConsoleError):
    def __init__(self, category: str, message: str = "provider adapter failed") -> None:
        self.category = category
        super().__init__(message)


@dataclass(frozen=True)
class AuthorizedTest:
    test_id: str
    label: str
    scope: str


@dataclass(frozen=True)
class AuthorizedEvaluation:
    evaluation_id: str
    system_id: str
    provider: str
    adapter: str
    credential: CredentialIdentity
    tests: tuple[AuthorizedTest, ...]

    def safe_metadata(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "system_id": self.system_id,
            "provider": self.provider,
            "adapter": self.adapter,
            "credential": self.credential.metadata(),
            "tests": [{"test_id": t.test_id, "label": t.label, "scope": t.scope} for t in self.tests],
        }


class ProviderAdapter:
    provider = "unknown"
    adapter_id = "unknown"

    def execute(self, lease: SecretLease, request: Mapping[str, str]) -> Mapping[str, Any]:
        raise NotImplementedError


class UnconfiguredAdapter(ProviderAdapter):
    """Fail-closed adapter used until the owner registers a real adapter."""

    provider = "unconfigured"
    adapter_id = "unconfigured"

    def execute(self, lease: SecretLease, request: Mapping[str, str]) -> Mapping[str, Any]:
        del lease, request
        raise AdapterUnavailable("no provider adapter is registered")


class ExecutionStore:
    """In-memory status plus safe local artifact persistence."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root
        self._records: dict[str, dict[str, Any]] = {}
        self._idempotency: dict[str, str] = {}
        self._lock = threading.RLock()

    def get(self, execution_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._records.get(execution_id)
            return json.loads(json.dumps(record)) if record else None

    def by_request(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            execution_id = self._idempotency.get(request_id)
            return self.get(execution_id) if execution_id else None

    def create(self, request_id: str, safe_request: Mapping[str, str]) -> dict[str, Any]:
        with self._lock:
            existing = self.by_request(request_id)
            if existing:
                return existing
            execution_id = f"ECP-EXEC-CONSOLE-{uuid.uuid4().hex}"
            now = _utc_now()
            record = {
                "execution_id": execution_id,
                "request_id": request_id,
                "system_id": safe_request["system_id"],
                "evaluation_id": safe_request["evaluation_id"],
                "test_id": safe_request["test_id"],
                "credential_ref": safe_request["credential_ref"],
                "status": "REQUESTED",
                "execution_status": "NOT_STARTED",
                "response_status": "NOT_RECEIVED",
                "evidence_status": "NOT_GENERATED",
                "audit_status": "NOT_GENERATED",
                "persistence_status": "NOT_PERSISTED",
                "created_at": now,
                "updated_at": now,
            }
            self._records[execution_id] = record
            self._idempotency[request_id] = execution_id
            return json.loads(json.dumps(record))

    def update(self, execution_id: str, **fields: Any) -> dict[str, Any]:
        with self._lock:
            self._records[execution_id].update(fields, updated_at=_utc_now())
            return json.loads(json.dumps(self._records[execution_id]))

    def persist(self, execution_id: str, evidence: Mapping[str, Any], audit: Mapping[str, Any]) -> tuple[str, str]:
        if self.root is None:
            return "PUSH_PENDING", "not configured"
        target = self.root / "external-executions" / execution_id
        target.mkdir(parents=True, exist_ok=True)
        evidence_path = target / "evidence.json"
        audit_path = target / "audit.json"
        evidence_path.write_bytes(canonical_bytes(dict(evidence)))
        audit_path.write_bytes(canonical_bytes(dict(audit)))
        return "PERSISTED_LOCALLY", str(target.relative_to(self.root))


@dataclass
class GatewayConfig:
    allowed_origins: frozenset[str]
    port: int = DEFAULT_PORT
    pairing_ttl_seconds: int = PAIRING_TTL_SECONDS
    artifact_root: Path | None = None


class LocalGateway:
    """Loopback-only authenticated gateway for registered evaluations."""

    def __init__(
        self,
        config: GatewayConfig,
        evaluations: Mapping[str, AuthorizedEvaluation],
        credential_gateway: CredentialGateway,
        adapters: Mapping[str, ProviderAdapter] | None = None,
        store: ExecutionStore | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not config.allowed_origins:
            raise ValueError("at least one explicit console origin is required")
        if config.port < 1 or config.port > 65535:
            raise ValueError("port must be between 1 and 65535")
        self.config = config
        self.evaluations = dict(evaluations)
        self.credential_gateway = credential_gateway
        self.adapters = dict(adapters or {})
        self.store = store or ExecutionStore(config.artifact_root)
        self._pairing_code = secrets.token_urlsafe(24)
        self._pairing_expires = (clock or __import__("time").time)() + config.pairing_ttl_seconds
        self._session_token: str | None = None
        self._clock = clock or __import__("time").time
        self._httpd: ThreadingHTTPServer | None = None

    @property
    def pairing_code(self) -> str:
        return self._pairing_code

    def pair(self, code: str) -> str:
        if not secrets.compare_digest(str(code), self._pairing_code) or self._clock() >= self._pairing_expires:
            raise AuthorizationError("pairing code is invalid or expired")
        self._session_token = secrets.token_urlsafe(32)
        return self._session_token

    def authenticate(self, token: str | None) -> None:
        if not token or self._session_token is None or not secrets.compare_digest(token, self._session_token):
            raise AuthorizationError("authentication required")

    def catalog(self) -> dict[str, Any]:
        return {"evaluations": [e.safe_metadata() for e in self.evaluations.values()], "poll_interval_ms": POLL_INTERVAL_MS, "timeout_seconds": EXECUTION_TIMEOUT_SECONDS}

    def execute(self, request: Mapping[str, Any]) -> dict[str, Any]:
        _validate_request(request)
        evaluation = self.evaluations.get(request["evaluation_id"])
        if evaluation is None or evaluation.system_id != request["system_id"]:
            raise ConsoleError("unknown evaluation or system")
        if evaluation.credential.credential_id != request["credential_ref"]:
            raise ConsoleError("unknown credential_ref")
        test = next((item for item in evaluation.tests if item.test_id == request["test_id"]), None)
        if test is None:
            raise ConsoleError("unknown test")
        safe_request = {key: str(request[key]) for key in ("evaluation_id", "test_id", "system_id", "credential_ref", "request_id")}
        record = self.store.create(safe_request["request_id"], safe_request)
        if record["status"] != "REQUESTED":
            return record
        execution_id = record["execution_id"]
        self.store.update(execution_id, status="AUTHORIZED", execution_status="RUNNING")
        lease: SecretLease | None = None
        try:
            lease = self.credential_gateway.retrieve(evaluation.credential.credential_id, test.scope)
            adapter = self.adapters.get(evaluation.adapter)
            if adapter is None:
                adapter = UnconfiguredAdapter()
            result = dict(adapter.execute(lease, safe_request))
            result.pop("secret", None)
            result.pop("credential_value", None)
            self.store.update(execution_id, status="COMPLETED", execution_status="SUCCESS", response_status="RECEIVED", result=_safe_result(result, (lease.value,)))
            try:
                self._finalize(execution_id, evaluation, safe_request, result, "SUCCESS", (lease.value,))
            except Exception as exc:
                self.store.update(execution_id, status="PARTIAL_SUCCESS", evidence_status="FAILED", audit_status="FAILED", persistence_status="FAILED", failure_stage="evidence_audit_or_persistence", error=_safe_exception_message(exc, lease))
        except CredentialError as exc:
            self.store.update(execution_id, status="FAILED", execution_status="INVALID", response_status="NOT_RECEIVED", error_classification="CREDENTIAL_ERROR", error=_safe_exception_message(exc, lease))
        except AdapterFailure as exc:
            self.store.update(execution_id, status="FAILED", execution_status=exc.category, response_status="NOT_RECEIVED", error_classification=exc.category, error=_safe_exception_message(exc, lease))
        except AdapterUnavailable as exc:
            self.store.update(execution_id, status="FAILED", execution_status="INCONCLUSIVE", response_status="NOT_RECEIVED", error_classification="ADAPTER_UNAVAILABLE", error=_safe_exception_message(exc, lease))
        except Exception as exc:  # fail closed and redact
            self.store.update(execution_id, status="FAILED", execution_status="ERROR", response_status="NOT_RECEIVED", error_classification="ADAPTER_ERROR", error=_safe_exception_message(exc, lease))
        return self.store.get(execution_id) or {}

    def _finalize(self, execution_id: str, evaluation: AuthorizedEvaluation, request: Mapping[str, str], result: Mapping[str, Any], outcome: str, secrets_to_redact: tuple[str, ...] = ()) -> None:
        evidence_id = f"ECP-EVID-CONSOLE-{execution_id.rsplit('-', 1)[-1]}"
        audit_id = f"ECP-AUDIT-CONSOLE-{execution_id.rsplit('-', 1)[-1]}"
        evidence = {"ecp_object": "console-evidence", "evidence_id": evidence_id, "execution_id": execution_id, "evaluation_id": request["evaluation_id"], "system_id": request["system_id"], "test_id": request["test_id"], "provider": evaluation.provider, "adapter": evaluation.adapter, "credential_ref": request["credential_ref"], "outcome": outcome, "result": _safe_result(result, secrets_to_redact), "created_at": _utc_now()}
        evidence["evidence_hash"] = hash_document(evidence)
        audit = {"ecp_object": "console-audit", "audit_id": audit_id, "execution_id": execution_id, "evidence_id": evidence_id, "evidence_hash": evidence["evidence_hash"], "audit_status": "PENDING_HUMAN_REVIEW", "created_at": _utc_now()}
        persistence, location = self.store.persist(execution_id, evidence, audit)
        evidence_status = "GENERATED"
        audit_status = "GENERATED"
        final_status = "SUCCESS" if persistence in {"PERSISTED_LOCALLY", "PUSH_PENDING"} else "PARTIAL_SUCCESS"
        self.store.update(execution_id, status=final_status, evidence_status=evidence_status, audit_status=audit_status, persistence_status=persistence, persistence_location=location, evidence_id=evidence_id, audit_id=audit_id)

    def make_server(self) -> ThreadingHTTPServer:
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "ECP-Local-Gateway/1.0"

            def _origin(self) -> str | None:
                return self.headers.get("Origin")

            def _check_origin(self) -> bool:
                origin = self._origin()
                if origin not in gateway.config.allowed_origins:
                    self._json(403, {"error": "origin denied", "state": "SECURITY_BLOCKED"}, include_cors=False)
                    return False
                return True

            def _json(self, status: int, payload: Mapping[str, Any], *, include_cors: bool = True) -> None:
                data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                if include_cors and self._origin() in gateway.config.allowed_origins:
                    self.send_header("Access-Control-Allow-Origin", self._origin() or "")
                    self.send_header("Vary", "Origin")
                    self.send_header("Access-Control-Allow-Headers", "Content-Type, X-ECP-Session")
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.end_headers()
                self.wfile.write(data)

            def do_OPTIONS(self) -> None:
                if self._check_origin():
                    self._json(204, {})

            def do_GET(self) -> None:
                if not self._check_origin():
                    return
                path = urlparse(self.path).path
                if path == "/api/v1/status":
                    self._json(200, {"gateway": "CONNECTED", "authentication": "PAIRED" if gateway._session_token else "AUTHENTICATION_REQUIRED", "binding": "127.0.0.1", "port": gateway.config.port})
                    return
                try:
                    gateway.authenticate(self.headers.get("X-ECP-Session"))
                    if path == "/api/v1/catalog":
                        self._json(200, gateway.catalog())
                    elif path.startswith("/api/v1/executions/"):
                        execution = gateway.store.get(path.rsplit("/", 1)[-1])
                        self._json(200 if execution else 404, execution or {"error": "execution not found"})
                    else:
                        self._json(404, {"error": "not found"})
                except AuthorizationError as exc:
                    self._json(401, {"error": str(exc), "state": "AUTHENTICATION_REQUIRED"})

            def do_POST(self) -> None:
                if not self._check_origin():
                    return
                path = urlparse(self.path).path
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length > 16_384:
                        raise ConsoleError("request too large")
                    body = json.loads(self.rfile.read(length) or b"{}")
                    if not isinstance(body, dict):
                        raise ConsoleError("request must be a JSON object")
                    if path == "/api/v1/pair":
                        token = gateway.pair(body.get("pairing_code", ""))
                        self._json(200, {"session": token})
                        return
                    gateway.authenticate(self.headers.get("X-ECP-Session"))
                    if path == "/api/v1/executions":
                        self._json(200, gateway.execute(body))
                    else:
                        self._json(404, {"error": "not found"})
                except AuthorizationError as exc:
                    self._json(401, {"error": str(exc), "state": "AUTHENTICATION_REQUIRED"})
                except (ConsoleError, ValueError, json.JSONDecodeError) as exc:
                    self._json(400, {"error": safe_exception_message(exc), "state": "INVALID"})

            def log_message(self, fmt: str, *args: Any) -> None:
                # Do not log request bodies or headers; method/path only.
                print("ECP gateway: " + fmt % tuple(args))

        self._httpd = ThreadingHTTPServer(("127.0.0.1", self.config.port), Handler)
        return self._httpd

    def serve_forever(self) -> None:
        self.make_server().serve_forever()


def _validate_request(request: Mapping[str, Any]) -> None:
    if set(request) != _ALLOWED_REQUEST_KEYS:
        raise ConsoleError("request fields are not exactly the authorized identifiers")
    if any(not isinstance(request[key], str) or not request[key].strip() for key in _ALLOWED_REQUEST_KEYS):
        raise ConsoleError("request identifiers must be non-empty strings")


def _safe_result(result: Mapping[str, Any], secrets_to_redact: tuple[str, ...] = ()) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    redactor = SecretRedactionFilter(secrets_to_redact)
    for key, value in result.items():
        if key.lower() in {"secret", "secret_value", "api_key", "token", "authorization", "password"}:
            continue
        if isinstance(value, str):
            safe[key] = redactor.redact(value)
        elif isinstance(value, (int, float, bool)) or value is None:
            safe[key] = value
    return safe


def _safe_exception_message(error: BaseException, lease: SecretLease | None = None) -> str:
    message = safe_exception_message(error)
    if lease is not None:
        message = SecretRedactionFilter((lease.value,)).redact(message)
    return message


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_gateway_config() -> GatewayConfig:
    origins = frozenset(filter(None, os.environ.get("ECP_CONSOLE_ALLOWED_ORIGINS", ",".join(DEFAULT_CONSOLE_ORIGINS)).split(",")))
    port = int(os.environ.get("ECP_GATEWAY_PORT", str(DEFAULT_PORT)))
    root = os.environ.get("ECP_ARTIFACT_ROOT")
    return GatewayConfig(origins, port, PAIRING_TTL_SECONDS, Path(root) if root else None)


def build_demo_gateway(config: GatewayConfig | None = None) -> LocalGateway:
    identity = CredentialIdentity("credential-ref-example", "example-provider", "console integration", frozenset({"execute"}), status="PROVISIONED")
    gateway = CredentialGateway.from_environment(identity, os.environ.get("ECP_EXAMPLE_CREDENTIAL_ENV", "ECP_EXAMPLE_CREDENTIAL"))
    evaluation = AuthorizedEvaluation("ECP-EVAL-CONSOLE-EXAMPLE", "ECP-SYSTEM-CONSOLE-EXAMPLE", "example-provider", "example-adapter", identity, (AuthorizedTest("connectivity-probe", "Registered connectivity probe", "execute"),))
    return LocalGateway(config or default_gateway_config(), {evaluation.evaluation_id: evaluation}, gateway, {"example-adapter": UnconfiguredAdapter()})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the loopback-only ECP local evaluation gateway")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--artifact-root", default=None)
    args = parser.parse_args(argv)
    config = default_gateway_config()
    if args.port is not None:
        config.port = args.port
    if args.artifact_root is not None:
        config.artifact_root = Path(args.artifact_root)
    gateway = build_demo_gateway(config)
    print(f"ECP Local Gateway listening on 127.0.0.1:{config.port}")
    print(f"PAIRING CODE (expires in {config.pairing_ttl_seconds}s): {gateway.pairing_code}")
    print("Allowed origins: " + ", ".join(sorted(config.allowed_origins)))
    gateway.serve_forever()
    return 0


__all__ = ["AdapterFailure", "AdapterUnavailable", "AuthorizedEvaluation", "AuthorizedTest", "ExecutionStore", "GatewayConfig", "LocalGateway", "ProviderAdapter", "build_demo_gateway", "default_gateway_config"]

if __name__ == "__main__":
    raise SystemExit(main())
