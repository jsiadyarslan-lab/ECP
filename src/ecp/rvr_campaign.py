"""RVR frozen scientific campaign engine v1 (single source of truth).

The ONE implementation of the registered ECP-EVAL-RVR-1 execution loop,
consumed by the registered CLI surface ``run_rvr_console.py``. It executes
exactly the frozen registration package (``registration/RVR-REGISTRATION-V1.json``,
``ECP-REG-RVR-V1``, package hash pinned in the package's ``integrity`` block)
against the target bound by the owner-authorized pre-execution binding record
(``registration/RVR-EXECUTION-BINDING-V1.json``) under the frozen condition
``ECP-COND-RVR-1``, in the frozen registered case order, ONE attempt per
registered case, no retries.

Boundaries enforced here (the M3 engine discipline, reused by pattern per
OD-02 — no M3 file is read or modified):

* the model input is ONLY the rendered registered case presentation
  (frozen ``render_prompt`` rule — sole prompt authority; no client prompt);
* the credential enters ONLY through the in-process session credential
  gateway and is released per case through the existing ``release()`` path;
* the sealed ground truth is compared ONLY in-process by the frozen
  RVR-CLASSIFIER-1; classifications (never GT) are persisted;
* execution/transport success is NEVER converted into behavioral success
  and vice versa (state separation preserved end-to-end);
* every executed case produces case-bound evidence + audit under the
  evidence root (OUTSIDE the repository) and the campaign ledger is
  written ONCE, after the loop.

Adjudication (CFTR and the frozen §G decision rules) is a DOWNSTREAM,
post-campaign layer over these sealed outputs — never part of execution.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .console import AuthorizedTest
from .credential_binding import AuthorizationGrant, CredentialBinding, ScopedReleaseRequest
from .execution_contract import (
    ClientExecutionIntent,
    ExecutionContractResolver,
    UniversalExecutionResult,
)
from .hashing import hash_document
from .rvr_classifier import classify_response
from .rvr_registration import (
    ADAPTER_ID,
    EVALUATION_ID,
    PROVIDER_ID,
    SYSTEM_ID,
)
from .runtime_adapters import (
    RuntimeAdapterRegistry,
    RuntimeAdapterTransportError,
)

#: The universal execution fabric's evaluation purpose (session scope; the
#: M3 session-gateway scope constant, reused verbatim).
SCIENTIFIC_PURPOSE = "conformance-evaluation"

#: The pinned external endpoint (frozen by the binding record).
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
    case_ids: "list[str] | tuple[str, ...]",
) -> _ScientificEvaluation:
    """Build the duck-typed RVR evaluation for the contract resolver."""
    tests = [
        AuthorizedTest(case_id, "ECP-EVAL-RVR-1 registered matched-variant case", SCIENTIFIC_PURPOSE)
        for case_id in case_ids
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
        f"ECP-BINDING-RVR-{suffix}",
        f"ECP-REQUIREMENT-RVR-{suffix}",
        f"ECP-TARGET-RVR-{suffix}",
        PROVIDER_ID,
        "openrouter-chat-completions-api",
        SCIENTIFIC_PURPOSE,
        credential_ref,
        frozenset({SCIENTIFIC_PURPOSE}),
    )
    grant = AuthorizationGrant(
        f"ECP-AUTH-RVR-{suffix}",
        binding.binding_id,
        binding.target_id,
        SCIENTIFIC_PURPOSE,
        frozenset({SCIENTIFIC_PURPOSE}),
        expires_at,
    )
    return binding, grant


def execute_campaign(
    *,
    package: Mapping[str, Any],
    execution_binding: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    case_views: Mapping[str, Mapping[str, Any]],
    gt_answers: Mapping[str, str],
    adapter: Any,
    gateway: Any,
    credential_ref: str,
    evidence_root: "str | Path",
    on_event: "CampaignEvent | None" = None,
    log: "CampaignLog | None" = None,
) -> dict:
    """Execute the frozen RVR campaign (one attempt per registered case).

    Per case: intent resolution, scoped credential release, adapter
    execution, frozen RVR-CLASSIFIER-1 classification against the sealed
    answer, case-bound evidence + audit persistence outside the repository,
    and the campaign ledger written once after the loop. Returns the
    campaign document ``{"summary": ..., "ledger": ...}``.
    """
    package_hash = package["integrity"]["package_hash"]
    binding_hash = execution_binding["binding_hash"]
    condition = execution_binding["condition"]
    target = execution_binding["target"]
    model_identifier = target["exact_model_api_identifier"]
    ordered_case_ids = [c["case_id"] for c in package["cases"]]
    total = len(ordered_case_ids)

    # Session preparation: bind the session identity to the registered
    # provider and build the campaign binding/grant with the live expiry.
    gateway.bind_discovered_provider(credential_ref, PROVIDER_ID)
    expires_at = gateway.session_expiry(credential_ref)
    binding, grant = build_campaign_binding(credential_ref, expires_at)
    evaluation = build_scientific_evaluation(credential_ref, binding, grant, ordered_case_ids)
    registry = build_runtime_registry(adapter)
    resolver = ExecutionContractResolver({EVALUATION_ID: evaluation}, cases=artifacts, runtime_registry=registry)

    evidence_root = Path(evidence_root)
    executions_dir = evidence_root / "executions"
    executions_dir.mkdir(parents=True, exist_ok=True)

    ledger: "list[dict]" = []
    for position, case_id in enumerate(ordered_case_ids, start=1):
        if on_event is not None:
            on_event({"event": "case_start", "position": position, "case_id": case_id})
        execution_id = f"ECP-EXEC-RVR-{uuid.uuid4().hex[:16].upper()}"
        intent = ClientExecutionIntent(
            evaluation_id=EVALUATION_ID, test_id=case_id, system_id=SYSTEM_ID,
            credential_ref=credential_ref, request_id=execution_id,
        )
        resolved = resolver.resolve(intent)
        release = ScopedReleaseRequest(
            request_id=execution_id, binding_id=binding.binding_id, target_id=binding.target_id,
            credential_ref=credential_ref, purpose=SCIENTIFIC_PURPOSE,
            scope=frozenset({SCIENTIFIC_PURPOSE}), lease_seconds=120, requested_at=_iso(),
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
            classification = classify_response(
                normalized_output,
                case_views[case_id],
                gt_answers[case_id],
                execution_valid=True,
                response_received=True,
                evidence_complete=True,
            )
        except RuntimeAdapterTransportError as exc:
            execution_status = "INVALID"
            provider_status = str(exc)
            response_status = "NOT_RECEIVED"
            normalized_output = ""
            transport_facts = {"transport_kind": "http", "endpoint": OPENROUTER_ENDPOINT, "http_status": getattr(exc, "http_status", None)}
            response_id = None
            classification = classify_response(
                None,
                case_views[case_id],
                gt_answers[case_id],
                execution_valid=False,
                response_received=False,
                evidence_complete=False,
            )

        case_entry = next(c for c in package["cases"] if c["case_id"] == case_id)
        evidence = {
            "ecp_object": "rvr-execution-evidence",
            "execution_id": execution_id,
            "request_id": execution_id,
            "evaluation_id": EVALUATION_ID,
            "system_id": SYSTEM_ID,
            "case_id": case_id,
            "set_id": case_entry["set_id"],
            "variant": case_entry["variant"],
            "family": case_entry["family"],
            "depth": case_entry["depth"],
            "ordering_position": position,
            "target": {
                "provider": PROVIDER_ID,
                "adapter": ADAPTER_ID,
                "model_identifier": model_identifier,
                "credential_ref": credential_ref,
            },
            "condition_id": condition.get("condition_id", "ECP-COND-RVR-1"),
            "registration_reference": {
                "package_id": package["package_id"],
                "package_hash": package_hash,
                "binding_id": execution_binding["binding_id"],
                "binding_hash": binding_hash,
            },
            "execution_status": execution_status,
            "provider_status": provider_status,
            "response_status": response_status,
            "response_id": response_id,
            "normalized_answer": normalized_output,
            "answer_state": classification["answer_state"],
            "declared_token": classification["declared_token"],
            "envelope_lines": classification["envelope_lines"],
            "premise_citation": classification["premise_citation"],
            "classifier_id": classification["classifier_id"],
            "classifier_version": classification["classifier_version"],
            "gt_commitment_reference": case_entry["gt_commitment"],
            "transport": transport_facts,
            "created_at": _iso(),
        }
        evidence["evidence_hash"] = hash_document(evidence)
        audit = {
            "ecp_object": "rvr-execution-audit",
            "audit_id": f"ECP-AUDIT-RVR-{uuid.uuid4().hex[:16].upper()}",
            "execution_id": execution_id,
            "evidence_id": f"ECP-EVID-RVR-{execution_id.rsplit('-', 1)[-1]}",
            "evidence_hash": evidence["evidence_hash"],
            "audit_status": "PENDING_HUMAN_REVIEW",
            "registration_reference": {
                "package_id": package["package_id"],
                "package_hash": package_hash,
                "binding_id": execution_binding["binding_id"],
                "binding_hash": binding_hash,
            },
            "created_at": _iso(),
        }
        (executions_dir / f"{execution_id}-evidence.json").write_text(
            json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        (executions_dir / f"{execution_id}-audit.json").write_text(
            json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        entry = {
            "position": position, "case_id": case_id, "set_id": case_entry["set_id"],
            "variant": case_entry["variant"], "family": case_entry["family"], "depth": case_entry["depth"],
            "execution_id": execution_id, "execution_status": execution_status,
            "provider_status": provider_status, "response_status": response_status,
            "answer_state": classification["answer_state"],
            "declared_token": classification["declared_token"],
            "evidence_hash": evidence["evidence_hash"],
        }
        ledger.append(entry)
        if log is not None:
            log(f"  [{position:02d}/{total}] {case_id} ({case_entry['variant']}): "
                f"execution={entry['execution_status']} answer={entry['answer_state']}")
        if on_event is not None:
            on_event({"event": "case_complete", "entry": dict(entry)})

    answer_states = {}
    for entry in ledger:
        answer_states[entry["answer_state"]] = answer_states.get(entry["answer_state"], 0) + 1
    summary = {
        "package_id": package["package_id"],
        "package_hash": package_hash,
        "binding_id": execution_binding["binding_id"],
        "binding_hash": binding_hash,
        "evaluation_id": EVALUATION_ID,
        "model_identifier": model_identifier,
        "attempted": len(ledger),
        "execution_valid": sum(1 for x in ledger if x["execution_status"] == "VALID"),
        "execution_invalid": sum(1 for x in ledger if x["execution_status"] == "INVALID"),
        "answer_states": dict(sorted(answer_states.items())),
        "note": "taxonomy counts only; endpoint computation and §G adjudication are downstream over sealed outputs",
        "completed_at": _iso(),
    }
    campaign = {"summary": summary, "ledger": ledger}
    ledger_path = evidence_root / "rvr-campaign-ledger.json"
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
]
