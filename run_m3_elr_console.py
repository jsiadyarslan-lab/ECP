#!/usr/bin/env python3
"""M3-ELR scientific execution console — the registered execution surface.

Executes exactly the frozen M3-ELR registration package
(registration/M3-ELR-REGISTRATION-V1.json, ECP-PKG-M3-ELR-V1) against the
pinned external target (inclusionai/ling-3.0-flash-sante:free @ OpenRouter)
under the frozen condition ECP-COND-M3-ELR-1 (MODEL-ENABLED, L1 model-only,
temperature 0.0, max_tokens 1024, transport timeout 30s), in the frozen
F-01b stratified order, one attempt per registered test, no retries.

Reconstructed 2026-09-13 (custody event D-01 #7 destroyed the original
launcher with commit c49b18f; pre-execution, outcome-blind reconstruction —
zero model calls existed project-wide). See
docs/M3-ELR-READINESS-RECONSTRUCTION.md.

Usage:
    OPENROUTER_API_KEY=... python run_m3_elr_console.py            # campaign
    python run_m3_elr_console.py --verify-only                     # wiring proof
    python run_m3_elr_console.py --evidence-root DIR               # override

Boundaries enforced here:
* the model input is ONLY the registered case presentation
  (RegisteredCaseArtifact — sole prompt authority; no client prompt exists);
* the credential enters ONLY through the in-process session credential
  gateway (environment at launch; never a file, never Git, never evidence);
* the protected ground truth is compared ONLY in-process by the frozen
  logical classifier; classifications (never GT) are persisted;
* execution/transport success is NEVER converted into reasoning success
  and vice versa (state separation preserved end-to-end);
* every executed test produces case-bound evidence + audit + persistence
  under the evidence root (default: /home/z/ecp-m3-elr-evidence — OUTSIDE
  the repository).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from ecp.canonical import load_json  # noqa: E402
from ecp.console import AuthorizedTest  # noqa: E402
from ecp.console_session import SessionCredentialGateway  # noqa: E402
from ecp.credentials import EnvironmentSecretStore  # noqa: E402
from ecp.credential_binding import AuthorizationGrant, CredentialBinding, ScopedReleaseRequest  # noqa: E402
from ecp.execution_contract import (  # noqa: E402
    ClientExecutionIntent,
    ExecutionContractResolver,
    UniversalExecutionResult,
)
from ecp.hashing import hash_document  # noqa: E402
from ecp.logical_classifier import classify_response  # noqa: E402
from ecp.m3_registration import (  # noqa: E402
    ADAPTER_ID,
    CONDITION_ID,
    CREDENTIAL_REF,
    EVALUATION_ID,
    PACKAGE_ID,
    POPULATION_ID,
    PROVIDER_ID,
    SYSTEM_ID,
    TARGET_MODEL_IDENTIFIER,
)
from ecp.m3_readiness import CREDENTIAL_ENV_VAR, run_readiness_gate  # noqa: E402
from ecp.registered_cases import (  # noqa: E402
    candidate_manifest_index,
    load_case_contents,
    load_registered_cases,
)  # noqa: E402
from ecp.runtime_adapters import (  # noqa: E402
    OpenRouterChatCompletionsAdapter,
    RuntimeAdapterRegistry,
    RuntimeAdapterTransportError,
)

PACKAGE_PATH = REPO / "registration" / "M3-ELR-REGISTRATION-V1.json"
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
SCIENTIFIC_PURPOSE = "conformance-evaluation"  # the universal execution fabric's evaluation purpose (session scope)
ADAPTER_REGISTRY_KEY = "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS"
DEFAULT_EVIDENCE_ROOT = Path("/home/z/ecp-m3-elr-evidence")


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


def _build_evaluation(credential_ref: str, binding: CredentialBinding, grant: AuthorizationGrant, test_ids: list):
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


def load_package() -> dict:
    package = load_json(PACKAGE_PATH)
    if package.get("package_id") != PACKAGE_ID:
        raise SystemExit(f"FATAL: registration package identity mismatch ({package.get('package_id')!r})")
    claimed = package.get("package_hash")
    recomputed = hash_document({k: v for k, v in package.items() if k != "package_hash"})
    if claimed != recomputed:
        raise SystemExit("FATAL: registration package hash mismatch — the frozen package is not intact")
    return package


def main() -> int:
    parser = argparse.ArgumentParser(description="M3-ELR scientific execution console (registered surface)")
    parser.add_argument("--verify-only", action="store_true", help="prove the wiring without any credential or call")
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help="evidence persistence root (outside the repository)")
    parser.add_argument("--case-area", default="/home/z/ecp-ca0v1", help="private qualification area")
    args = parser.parse_args()

    print("=== M3-ELR SCIENTIFIC EXECUTION CONSOLE (registered surface) ===")
    package = load_package()
    package_hash = package["package_hash"]
    print(f"package      : {package['package_id']} (hash {package_hash[:16]}… verified)")

    manifest = load_json(REPO / "provenance" / "m3-population-namespace-manifest.json")
    manifest_index = candidate_manifest_index(manifest, POPULATION_ID)

    artifacts = load_registered_cases(package, case_area=args.case_area, manifest_index=manifest_index)
    contents = load_case_contents(package, case_area=args.case_area)
    ordered_test_ids = package["ordered_test_ids"]
    print(f"cases        : {len(artifacts)} registered, four-surface verified")
    print(f"order        : F-01b frozen ({ordered_test_ids[0]} … {ordered_test_ids[-1]})")

    gate = run_readiness_gate(repo=REPO, package_path=PACKAGE_PATH, case_area=args.case_area)
    print(f"§22 gate     : {gate['summary']['pass']} PASS / {gate['summary']['pending']} PENDING / {gate['summary']['fail']} FAIL")
    for check in gate["checks"]:
        if check["status"] == "FAIL":
            print(f"  FAIL {check['id']}: {check['description']} — {check['evidence']}")
    if gate["summary"]["fail"]:
        return 1

    adapter = OpenRouterChatCompletionsAdapter(
        model=TARGET_MODEL_IDENTIFIER,
        endpoint=OPENROUTER_ENDPOINT,
        temperature=package["condition"]["temperature"],
        max_tokens=package["condition"]["max_tokens"],
        timeout=float(package["condition"]["transport_timeout_seconds"]),
    )
    registry = RuntimeAdapterRegistry({ADAPTER_REGISTRY_KEY: adapter})

    suffix = uuid.uuid4().hex[:16].upper()
    binding = CredentialBinding(
        f"ECP-BINDING-M3ELR-{suffix}",
        f"ECP-REQUIREMENT-M3ELR-{suffix}",
        f"ECP-TARGET-M3ELR-{suffix}",
        PROVIDER_ID,
        "openrouter-chat-completions-api",
        SCIENTIFIC_PURPOSE,
        CREDENTIAL_REF,
        frozenset({SCIENTIFIC_PURPOSE}),
    )

    if args.verify_only:
        grant = AuthorizationGrant(
            f"ECP-AUTH-M3ELR-{suffix}", binding.binding_id, binding.target_id,
            SCIENTIFIC_PURPOSE, frozenset({SCIENTIFIC_PURPOSE}), _iso(),
        )
        evaluation = _build_evaluation(CREDENTIAL_REF, binding, grant, ordered_test_ids)
        resolver = ExecutionContractResolver({EVALUATION_ID: evaluation}, cases=artifacts, runtime_registry=registry)
        probe_test = ordered_test_ids[0]
        intent = ClientExecutionIntent(
            evaluation_id=EVALUATION_ID, test_id=probe_test, system_id=SYSTEM_ID,
            credential_ref=CREDENTIAL_REF, request_id=f"ECP-REQ-VERIFY-{suffix}",
        )
        resolved = resolver.resolve(intent)
        transport_request = resolved.transport_request()
        print(f"resolver     : intent resolved for {probe_test}")
        print(f"prompt authority : {resolved.prompt_reference} (RegisteredCaseArtifact; no client prompt path exists)")
        print(f"model input  : {len(transport_request['prompt'])} chars of registered presentation (hash {resolved.experiment.prompt_hash[:16]}…)")
        missing = [c for c in gate["checks"] if c["status"] == "PENDING"]
        for check in missing:
            print(f"  PENDING {check['id']}: {check['evidence']}")
        print("WIRING VERIFIED — no credential resolved, no provider call, no model call, no outcome.")
        return 0

    secret = os.environ.get(CREDENTIAL_ENV_VAR, "").strip()
    if not secret:
        print(f"FATAL: {CREDENTIAL_ENV_VAR} is not set — the credential must be supplied at launch "
              "(outside Git, outside records; it enters only the in-process gateway).")
        return 1

    gateway = SessionCredentialGateway(EnvironmentSecretStore(CREDENTIAL_ENV_VAR), {})
    handle = gateway.open_session(secret, ttl_seconds=86400)
    credential_ref = handle["credential_ref"]
    session_identity = gateway.bind_discovered_provider(credential_ref, PROVIDER_ID)
    expires_at = handle["expires_at"]
    grant = AuthorizationGrant(
        f"ECP-AUTH-M3ELR-{suffix}", binding.binding_id, binding.target_id,
        SCIENTIFIC_PURPOSE, frozenset({SCIENTIFIC_PURPOSE}), expires_at,
    )
    binding = CredentialBinding(
        binding.binding_id, binding.requirement_id, binding.target_id, PROVIDER_ID,
        "openrouter-chat-completions-api", SCIENTIFIC_PURPOSE, credential_ref,
        frozenset({SCIENTIFIC_PURPOSE}),
    )
    evaluation = _build_evaluation(credential_ref, binding, grant, ordered_test_ids)
    resolver = ExecutionContractResolver({EVALUATION_ID: evaluation}, cases=artifacts, runtime_registry=registry)

    evidence_root = Path(args.evidence_root)
    executions_dir = evidence_root / "executions"
    executions_dir.mkdir(parents=True, exist_ok=True)
    print(f"evidence     : {evidence_root} (outside the repository)")

    ledger = []
    for position, test_id in enumerate(ordered_test_ids, start=1):
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
        ledger.append({
            "position": position, "test_id": test_id, "execution_id": execution_id,
            "execution_status": execution_status, "provider_status": provider_status,
            "response_status": response_status, "answer_state": classification["answer_state"],
            "task_outcome": classification["task_outcome"],
            "evidence_hash": evidence["evidence_hash"],
        })
        print(f"  [{position:02d}/30] {test_id}: execution={execution_status} answer={classification['answer_state']} outcome={classification['task_outcome']}")

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
    (evidence_root / "m3-elr-campaign-ledger.json").write_text(
        json.dumps(campaign, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"campaign ledger: {evidence_root / 'm3-elr-campaign-ledger.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
