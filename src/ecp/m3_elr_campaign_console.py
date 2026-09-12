"""M3-ELR scientific campaign console component v1 (browser surface).

Owner order 2026-09-13: the registered M3-ELR execution surface exposed in
the EXISTING evaluation console — the owner pastes the provider credential
in the browser, presses RUN CAMPAIGN, and the frozen 30-case campaign
executes with live results while evidence, audit and the campaign ledger
persist exactly as the registered CLI surface produces them.

The component owns NO new authority:

* it is a session-console component exactly like
  :class:`ecp.console_session.ConsoleSessionManager` (the five standard
  session routes are DELEGATED to the wrapped manager — credential
  sessions, discovery, target onboarding all keep their existing wiring);
* the campaign executes through the shared frozen engine
  (:func:`ecp.m3_elr_campaign.execute_campaign`) — the same engine the
  registered CLI launcher consumes; there is no second execution loop;
* the credential value NEVER enters this component — the campaign engine
  releases it per test through the session credential gateway's existing
  ``release()`` path, exactly like the CLI surface;
* the protected ground truth NEVER leaves the process — the frozen
  logical classifier runs in-process and only classifications are exposed
  to the browser and persisted;
* one campaign per launcher process (frozen single-attempt discipline);
  a second start is refused until the launcher is restarted.

Routes served (dispatched by the existing LocalGateway session-route
seam, behind pairing authentication, with submitted-secret redaction):

    POST /api/v1/m3elr/campaign/status  -> registration facts + live campaign state
    POST /api/v1/m3elr/campaign         -> start the frozen campaign {credential_ref}
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .console_session import SessionConsoleError
from .credentials import safe_exception_message
from .m3_elr_campaign import execute_campaign

#: Status values of a browser campaign.
CAMPAIGN_RUNNING = "RUNNING"
CAMPAIGN_COMPLETED = "COMPLETED"
CAMPAIGN_FAILED = "FAILED"


def _iso(moment: "datetime | None" = None) -> str:
    now = moment or datetime.now(timezone.utc)
    return now.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class M3ELRCampaignConsole:
    """Session-console component adding the M3-ELR campaign routes.

    Wraps the standard :class:`ConsoleSessionManager` (delegation for the
    existing session routes) and adds the two campaign routes. Holds the
    frozen registration facts loaded by the launcher (hash-verified
    package, four-surface-verified cases, §22 readiness gate result) and
    the frozen adapter built under the frozen condition.
    """

    def __init__(
        self,
        *,
        session_manager: Any,
        session_credentials: Any,
        package: Mapping[str, Any],
        artifacts: Mapping[str, Any],
        contents: Mapping[str, Mapping[str, Any]],
        adapter: Any,
        evidence_root: Any,
        gate: Mapping[str, Any],
        clock: "Callable[[], datetime] | None" = None,
    ) -> None:
        for method in ("open_session", "revoke_session", "discover", "select_target", "descriptors"):
            if not callable(getattr(session_manager, method, None)):
                raise ValueError(f"wrapped session manager requires a callable {method}()")
        self._session_manager = session_manager
        self._session_credentials = session_credentials
        self._package = package
        self._artifacts = artifacts
        self._contents = contents
        self._adapter = adapter
        self._evidence_root = evidence_root
        self._gate = gate
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._campaign: "dict[str, Any] | None" = None
        self._thread: "threading.Thread | None" = None

    # ------------------------------------------------------------------
    # Delegated standard session routes (existing wiring, unchanged)
    # ------------------------------------------------------------------

    def descriptors(self):
        return self._session_manager.descriptors()

    def open_session(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._session_manager.open_session(payload)

    def discover(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._session_manager.discover(payload)

    def select_target(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._session_manager.select_target(payload)

    def revoke_session(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._session_manager.revoke_session(payload)

    # ------------------------------------------------------------------
    # M3-ELR campaign routes
    # ------------------------------------------------------------------

    def m3elr_campaign_status(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Registration facts, readiness gate and the live campaign state."""
        del payload
        return {
            "m3elr_console": True,
            "registration": self._registration_view(),
            "gate": self._gate_view(),
            "evidence_root": str(self._evidence_root),
            "campaign": self._campaign_view(),
        }

    def m3elr_campaign(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Start the frozen campaign (one per launcher process)."""
        credential_ref = payload.get("credential_ref")
        if not isinstance(credential_ref, str) or not credential_ref.strip():
            raise SessionConsoleError(
                "credential_ref is required — open a credential session first, then run the campaign"
            )
        if self._gate.get("summary", {}).get("fail"):
            raise SessionConsoleError(
                "the §22 readiness gate has failing checks — the campaign surface is closed"
            )
        # Fail closed on an unknown/expired session BEFORE any campaign state
        # exists (the engine re-validates per test through release()).
        self._session_credentials.current_identity(credential_ref)
        with self._lock:
            if self._campaign is not None:
                raise SessionConsoleError(
                    "an M3-ELR campaign has already been started in this launcher process; "
                    "restart the launcher to execute a new campaign (frozen single-attempt "
                    "discipline: one campaign per process)"
                )
            self._campaign = {
                "campaign_id": f"ECP-CAMPAIGN-M3ELR-{uuid.uuid4().hex[:16].upper()}",
                "status": CAMPAIGN_RUNNING,
                "started_at": _iso(self._clock()),
                "credential_ref": credential_ref,
                "position": 0,
                "total": len(self._package["ordered_test_ids"]),
                "current_test_id": None,
                "entries": [],
                "summary": None,
                "ledger_path": None,
                "error": None,
            }
            self._thread = threading.Thread(
                target=self._run_campaign, args=(credential_ref,), daemon=True, name="m3-elr-campaign"
            )
            self._thread.start()
            return {"m3elr_console": True, "campaign": self._campaign_view()}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_campaign(self, credential_ref: str) -> None:
        try:
            execute_campaign(
                package=self._package,
                artifacts=self._artifacts,
                contents=self._contents,
                adapter=self._adapter,
                gateway=self._session_credentials,
                credential_ref=credential_ref,
                evidence_root=self._evidence_root,
                on_event=self._on_event,
            )
        except Exception as exc:  # honest failure surface — never fabricated success
            message = safe_exception_message(exc)
            with self._lock:
                if self._campaign is not None:
                    self._campaign["status"] = CAMPAIGN_FAILED
                    self._campaign["error"] = message
                    self._campaign["current_test_id"] = None

    def _on_event(self, event: Mapping[str, Any]) -> None:
        kind = event.get("event")
        with self._lock:
            campaign = self._campaign
            if campaign is None:
                return
            if kind == "test_start":
                campaign["current_test_id"] = event["test_id"]
            elif kind == "test_complete":
                campaign["entries"].append(dict(event["entry"]))
                campaign["position"] = event["entry"]["position"]
                campaign["current_test_id"] = None
            elif kind == "campaign_complete":
                campaign["status"] = CAMPAIGN_COMPLETED
                campaign["summary"] = dict(event["summary"])
                campaign["ledger_path"] = event["ledger_path"]
                campaign["current_test_id"] = None

    def _registration_view(self) -> dict[str, Any]:
        package = self._package
        condition = dict(package.get("condition") or {})
        target = dict(package.get("target") or {})
        return {
            "package_id": package.get("package_id"),
            "package_hash": package.get("package_hash"),
            "evaluation_id": package.get("evaluation", {}).get("evaluation_id"),
            "condition_id": condition.get("condition_id"),
            "condition": {
                "model_state": condition.get("model_state"),
                "level": condition.get("level"),
                "temperature": condition.get("temperature"),
                "max_tokens": condition.get("max_tokens"),
                "transport_timeout_seconds": condition.get("transport_timeout_seconds"),
            },
            "target_model_identifier": target.get("exact_model_api_identifier"),
            "provider": target.get("provider"),
            "adapter": target.get("adapter_id"),
            "case_count": len(package.get("cases") or []),
            "ordered_test_ids": list(package.get("ordered_test_ids") or []),
            "attempts_per_test": (package.get("execution_contract") or {}).get("attempts_per_test", 1),
            "registered_at": package.get("registered_at"),
        }

    def _gate_view(self) -> dict[str, Any]:
        summary = dict((self._gate.get("summary") or {}))
        pending = [
            {"id": check.get("id"), "evidence": check.get("evidence")}
            for check in (self._gate.get("checks") or [])
            if check.get("status") == "PENDING"
        ]
        return {"pass": summary.get("pass", 0), "pending": summary.get("pending", 0), "fail": summary.get("fail", 0), "pending_checks": pending}

    def _campaign_view(self) -> "dict[str, Any] | None":
        with self._lock:
            if self._campaign is None:
                return None
            import json as _json
            return _json.loads(_json.dumps(self._campaign))


__all__ = ["M3ELRCampaignConsole"]
