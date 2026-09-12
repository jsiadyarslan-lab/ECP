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

Engine factored 2026-09-13 (owner order: the browser console surface): the
campaign loop now lives in ecp.m3_elr_campaign.execute_campaign — the ONE
engine also consumed by run_m3_elr_browser_console.py — with byte-compatible
evidence/audit/ledger artifacts. No scientific execution changed.

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
import os
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from ecp.canonical import load_json  # noqa: E402
from ecp.console_session import SessionCredentialGateway  # noqa: E402
from ecp.credentials import EnvironmentSecretStore  # noqa: E402
from ecp.credential_binding import AuthorizationGrant, CredentialBinding  # noqa: E402
from ecp.execution_contract import (  # noqa: E402
    ClientExecutionIntent,
    ExecutionContractResolver,
)
from ecp.m3_elr_campaign import (  # noqa: E402
    OPENROUTER_ENDPOINT,
    SCIENTIFIC_PURPOSE,
    build_runtime_registry,
    build_scientific_evaluation,
    execute_campaign,
    load_verified_package,
)
from ecp.m3_registration import (  # noqa: E402
    CREDENTIAL_REF,
    EVALUATION_ID,
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
)
from ecp.runtime_adapters import OpenRouterChatCompletionsAdapter  # noqa: E402

PACKAGE_PATH = REPO / "registration" / "M3-ELR-REGISTRATION-V1.json"
DEFAULT_EVIDENCE_ROOT = Path("/home/z/ecp-m3-elr-evidence")


def _iso() -> str:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return now.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="M3-ELR scientific execution console (registered surface)")
    parser.add_argument("--verify-only", action="store_true", help="prove the wiring without any credential or call")
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help="evidence persistence root (outside the repository)")
    parser.add_argument("--case-area", default="/home/z/ecp-ca0v1", help="private qualification area")
    args = parser.parse_args()

    print("=== M3-ELR SCIENTIFIC EXECUTION CONSOLE (registered surface) ===")
    package = load_verified_package(PACKAGE_PATH)
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
    registry = build_runtime_registry(adapter)

    suffix = uuid.uuid4().hex[:16].upper()

    if args.verify_only:
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
        grant = AuthorizationGrant(
            f"ECP-AUTH-M3ELR-{suffix}", binding.binding_id, binding.target_id,
            SCIENTIFIC_PURPOSE, frozenset({SCIENTIFIC_PURPOSE}), _iso(),
        )
        evaluation = build_scientific_evaluation(CREDENTIAL_REF, binding, grant, ordered_test_ids)
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

    evidence_root = Path(args.evidence_root)
    print(f"evidence     : {evidence_root} (outside the repository)")

    campaign = execute_campaign(
        package=package,
        artifacts=artifacts,
        contents=contents,
        adapter=adapter,
        gateway=gateway,
        credential_ref=handle["credential_ref"],
        evidence_root=evidence_root,
        log=print,
    )
    import json

    print(json.dumps(campaign["summary"], indent=2, sort_keys=True))
    print(f"campaign ledger: {evidence_root / 'm3-elr-campaign-ledger.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
