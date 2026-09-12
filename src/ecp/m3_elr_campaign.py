"""M3-ELR frozen scientific campaign engine v1 (single source of truth).

The ONE implementation of the registered M3-ELR campaign execution loop.
Both registered surfaces consume it and produce IDENTICAL artifacts:

* ``run_m3_elr_console.py`` — the registered CLI surface (credential
  supplied at launch through the environment);
* ``run_m3_elr_browser_console.py`` — the registered browser surface
  (owner order 2026-09-13: the owner pastes the provider credential into
  the existing evaluation console and presses RUN CAMPAIGN).

The engine executes exactly the frozen registration package
(registration/M3-ELR-REGISTRATION-V1.json, ECP-PKG-M3-ELR-V1) against the
pinned external target (inclusionai/ling-3.0-flash-sante:free @ OpenRouter)
under the frozen condition ECP-COND-M3-ELR-1 (MODEL-ENABLED, L1 model-only,
temperature 0.0, max_tokens 1024, transport timeout 30s), in the frozen
F-01b stratified order, ONE attempt per registered test, no retries.

Boundaries enforced here (identical to the registered CLI surface):

* the model input is ONLY the registered case presentation
  (RegisteredCaseArtifact — sole prompt authority; no client prompt);
* the credential enters ONLY through the in-process session credential
  gateway and is released per test through the existing ``release()`` path;
* the protected ground truth is compared ONLY in-process by the frozen
  logical classifier; classifications (never GT) are persisted;
* execution/transport success is NEVER converted into reasoning success
  and vice versa (state separation preserved end-to-end);
* every executed test produces case-bound evidence + audit + persistence
  under the evidence root (OUTSIDE the repository) and the campaign ledger
  is written once, after the loop.

Reconstructed 2026-09-13; engine factored 2026-09-13 (owner order: the
browser console surface) with byte-compatible evidence/audit/ledger
artifacts — see docs/M3-ELR-BROWSER-CONSOLE.md.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .canonical import load_json
from .console import AuthorizedTest
from .credential_binding import AuthorizationGrant, CredentialBinding, ScopedReleaseRequest
from .execution_contract import (
    ClientExecutionIntent,
    ExecutionContractResolver,
    UniversalExecutionResult,
)
from .hashing import hash_document
from .logical_classifier import classify_response
from .m3_registration import (
    ADAPTER_ID,
    CONDITION_ID,
    EVALUATION_ID,
    PACKAGE_ID,
    PROVIDER_ID,
    SYSTEM_ID,
    TARGET_MODEL_IDENTIFIER,
)
from .runtime_adapters import (
    RuntimeAdapterRegistry,
    RuntimeAdapterTransportError,
)

#: The universal execution fabric's evaluation purpose (session scope).
SCIENTIFIC_PURPOSE = "conformance-evaluation"

#: The pinned external endpoint (frozen by the registration package).
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

#: The runtime adapter registry key (the declared adapter identity).
ADAPTER_REGISTRY_KEY = ADAPTER_ID

#: Event callback signature (progress notifications; secret-free).
CampaignEvent = Callable[[Mapping[str, Any]], None]

#: Log callback signature (plain human-readable lines; secret-free).
CampaignLog = Callable[[str], None]


def _iso(moment: "datetime | None" = None) -> str:
    now = moment or datetime.now(timezone.utc)
    return now.replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class _CredentialRef:
    credential_id: str


@dataclass(frozen=True)
class _ScientificEvaluation:
    """Duck-typed evaluation surface for the ExecutionContractResolver."""

    evaluation_id: str
    system_id: str
    provider: str
    adapter: str
    credential: Any
    tests: Any
    credential_binding: Any
    authorization_grant: Any


def build_scientific_evaluation(
    credential_ref: str,
    binding: CredentialBinding,
    grant: AuthorizationGrant,
    test_ids: "list[str] | tuple[str, ...]",
) -> _ScientificEvaluation:
    """Build the duck-typed M3-ELR evaluation for the contract resolver."""
    tests = [
        AuthorizedTest(test_id, "M3-ELR registered logical reasoning case", SCIENTIFIC_PURPOSE)
        for test_id in test_ids
    ]
    return _ScientificEvaluation(
        evaluation_id=EVALUATION_ID,
        system_id=SYSTEM_ID,
        provider=PROVIDER_ID,
        adapter=ADAPTER_REGISTRY_KEY,
        credential=_CredentialRef(credential_ref),
        tests=tests,
        credential_binding=binding,
        authorization_grant=grant,
    )


def build_runtime_registry(adapter: Any) -> RuntimeAdapterRegistry:
    """Register the frozen adapter under its declared adapter identity."""
    return RuntimeAdapterRegistry({ADAPTER_REGISTRY_KEY: adapter})


def build_campaign_binding(
    credential_ref: str, expires_at: str
) -> "tuple[CredentialBinding, AuthorizationGrant]":
    """Build the campaign binding + grant bound to the live credential ref."""
    suffix = uuid.uuid4().hex[:16].upper()
    binding = CredentialBinding(
        f"ECP-BINDING-M3ELR-{suffix}",
        f"ECP-REQUIREMENT-M3ELR-{suffix}",
        f"ECP-TARGET-M3ELR-{suffix}",
        PROVIDER_ID,
        "openrouter-chat-completions-api",
        SCIENTIFIC_PURPOSE,
        credential_ref,
        frozenset({SCIENTIFIC_PURPOSE}),
    )
    grant = AuthorizationGrant(
        f"ECP-AUTH-M3ELR-{suffix}",
        binding.binding_id,
        binding.target_id,
        SCIENTIFIC_PURPOSE,
        frozenset({SCIENTIFIC_PURPOSE}),
        expires_at,
    )
    return binding, grant


def load_verified_package(package_path: "str | Path") -> dict:
    """Load the frozen registration package with fail-closed verification."""
    package = load_json(Path(package_path))
    if package.get("package_id") != PACKAGE_ID:
        raise SystemExit(f"FATAL: registration package identity mismatch ({package.get('package_id')!r})")
    claimed = package.get("package_hash")
    recomputed = hash_document({k: v for k, v in package.items() if k != "package_hash"})
    if claimed != recomputed:
        raise SystemExit("FATAL: registration package hash mismatch — the frozen package is not intact")
    return package


def execute_campaign(
    *,
    package: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    contents: Mapping[str, Mapping[str, Any]],
    adapter: Any,
    gateway: Any,
    credential_ref: str,
    evidence_root: "str | Path",
    on_event: "CampaignEvent | None" = None,
    log: "CampaignLog | None" = None,
) -> dict:
    """Execute the frozen M3-ELR campaign (one attempt per registered test).

    Mirrors the registered CLI surface exactly: per-test intent resolution,
    scoped credential release, adapter execution, frozen classification,
    case-bound evidence + audit persistence outside the repository, and the
    campaign ledger written once after the loop. Returns the campaign
    document ``{"summary": ..., "ledger": ...}``.
    """
    package_hash = package["package_hash"]
    ordered_test_ids = list(package["ordered_test_ids"])
    total = len(ordered_test_ids)

    # Same session preparation the CLI surface performs: bind the session
    # identity to the registered provider (expands the scope to evaluation
    # scope) and build the campaign binding/grant with the live expiry.
    gateway.bind_discovered_provider(credential_ref, PROVIDER_ID)
    expires_at = gateway.session_expiry(credential_ref)
    binding, grant = build_campaign_binding(credential_ref, expires_at)
    evaluation = build_scientific_evaluation(credential_ref, binding, grant, ordered_test_ids)
    registry = build_runtime_registry(adapter)
    resolver = ExecutionContractResolver({EVALUATION_ID: evaluation}, cases=artifacts, runtime_registry=registry)

    evidence_root = Path(evidence_root)
    executions_dir = evidence_root / "executions"
    executions_dir.mkdir(parents=True, exist_ok=True)

    ledger: "list[dict]" = []
    for position, test_id in enumerate(ordered_test_ids, start=1):
        if on_event is not None:
            on_event({"event": "test_start", "position": position, "test_id": test_id})
        execution_id = f"ECP-EXEC-M3ELR-{uuid.uuid4().hex[:16].upper()}"
        intent = ClientExecutionIntent(
            evaluation_id=EVALUATION_ID, test_id=test_id, system_id=SYSTEM_ID,
            credential_ref=credential_ref, request_id=execution_id,
        )
        resolved = resolver.resolve(intent)
        release = ScopedReleaseRequest(
            request_id=execution_id, binding_id=binding.binding_id, target_id=binding.target_id,
            credential_ref=credential_ref, purpose=SCIENTIFIC_PURPOSE,
            scope=frozenset({SCIENTIFIC_PURPOSE}), lease_seconds=60, requested_at=_iso(),
        )
        lease = gateway.release(release, binding, grant)
        try:
            payload = dict(adapter.execute(lease, resolved.transport_request()))
            result = UniversalExecutionResult.from_provider_payload(payload, request_id=execution_id)
            execution_status = "VALID"
            provider_status = result.provider_status
            response_status = "RECEIVED"
            normalized_output = result.normalized_output or ""
            transport_facts = {k: v for k, v in payload.items() if k in {"transport_kind", "endpoint", "http_status", "latency_ms"}}
            response_id = result.response_metadata.get("response_id")
            classification = classify_response(normalized_output, contents[test_id], response_received=True)
        except RuntimeAdapterTransportError as exc:
            execution_status = "INVALID"
            provider_status = str(exc)
            response_status = "NOT_RECEIVED"
            normalized_output = ""
            transport_facts = {"transport_kind": "http", "endpoint": OPENROUTER_ENDPOINT, "http_status": getattr(exc, "http_status", None)}
            response_id = None
            classification = classify_response(None, contents[test_id], response_received=False)

        case_entry = next(c for c in package["cases"] if c["test_id"] == test_id)
        evidence = {
            "ecp_object": "m3-elr-execution-evidence",
            "execution_id": execution_id,
            "request_id": execution_id,
            "evaluation_id": EVALUATION_ID,
            "system_id": SYSTEM_ID,
            "test_id": test_id,
            "case_id": case_entry["case_id"],
            "ordering_position": position,
            "target": {
                "provider": PROVIDER_ID,
                "adapter": ADAPTER_ID,
                "model_identifier": TARGET_MODEL_IDENTIFIER,
                "credential_ref": credential_ref,
            },
            "condition_id": CONDITION_ID,
            "registration_reference": {"package_id": PACKAGE_ID, "package_hash": package_hash},
            "execution_status": execution_status,
            "provider_status": provider_status,
            "response_status": response_status,
            "response_id": response_id,
            "normalized_answer": normalized_output,
            "answer_state": classification["answer_state"],
            "declared_key": classification["declared_key"],
            "premise_citation": classification["premise_citation"],
            "task_outcome": classification["task_outcome"],
            "classifier_id": classification["classifier_id"],
            "gt_commitment_reference": case_entry["gt_commitment"],
            "transport": transport_facts,
            "created_at": _iso(),
        }
        evidence["evidence_hash"] = hash_document(evidence)
        audit = {
            "ecp_object": "m3-elr-execution-audit",
            "audit_id": f"ECP-AUDIT-M3ELR-{uuid.uuid4().hex[:16].upper()}",
            "execution_id": execution_id,
            "evidence_id": f"ECP-EVID-M3ELR-{execution_id.rsplit('-', 1)[-1]}",
            "evidence_hash": evidence["evidence_hash"],
            "audit_status": "PENDING_HUMAN_REVIEW",
            "registration_reference": {"package_id": PACKAGE_ID, "package_hash": package_hash},
            "created_at": _iso(),
        }
        (executions_dir / f"{execution_id}-evidence.json").write_text(
            json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        (executions_dir / f"{execution_id}-audit.json").write_text(
            json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        entry = {
            "position": position, "test_id": test_id, "execution_id": execution_id,
            "execution_status": execution_status, "provider_status": provider_status,
            "response_status": response_status, "answer_state": classification["answer_state"],
            "task_outcome": classification["task_outcome"],
            "evidence_hash": evidence["evidence_hash"],
        }
        ledger.append(entry)
        if log is not None:
            log(f"  [{position:02d}/{total}] {test_id}: execution={entry['execution_status']} answer={entry['answer_state']} outcome={entry['task_outcome']}")
        if on_event is not None:
            on_event({"event": "test_complete", "entry": dict(entry)})

    summary = {
        "package_id": PACKAGE_ID,
        "package_hash": package_hash,
        "evaluation_id": EVALUATION_ID,
        "attempted": len(ledger),
        "execution_valid": sum(1 for x in ledger if x["execution_status"] == "VALID"),
        "execution_invalid": sum(1 for x in ledger if x["execution_status"] == "INVALID"),
        "answer_states": {s: sum(1 for x in ledger if x["answer_state"] == s) for s in sorted({x["answer_state"] for x in ledger})},
        "task_outcomes": {s: sum(1 for x in ledger if x["task_outcome"] == s) for s in sorted({x["task_outcome"] for x in ledger})},
        "completed_at": _iso(),
    }
    campaign = {"summary": summary, "ledger": ledger}
    ledger_path = evidence_root / "m3-elr-campaign-ledger.json"
    ledger_path.write_text(
        json.dumps(campaign, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    if on_event is not None:
        on_event({"event": "campaign_complete", "summary": dict(summary), "ledger_path": str(ledger_path)})
    return campaign


__all__ = [
    "ADAPTER_REGISTRY_KEY",
    "OPENROUTER_ENDPOINT",
    "SCIENTIFIC_PURPOSE",
    "build_campaign_binding",
    "build_runtime_registry",
    "build_scientific_evaluation",
    "execute_campaign",
    "load_verified_package",
]
