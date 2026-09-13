#!/usr/bin/env python3
"""RVR scientific execution console — the registered execution surface.

Executes exactly the frozen RVR registration package
(registration/RVR-REGISTRATION-V1.json, ECP-REG-RVR-V1) for campaign
ECP-EVAL-RVR-1 against the target bound by the owner-authorized pre-execution
binding record (registration/RVR-EXECUTION-BINDING-V1.json:
google/gemma-4-26b-a4b-it:free @ OpenRouter) under the frozen condition
ECP-COND-RVR-1 (MODEL-ENABLED, L1 model-only, temperature 0.0,
max_tokens 1024, transport timeout 90 s), in the frozen registered case
order, ONE attempt per registered case, no retries.

Boundaries enforced here (the M3 console discipline, reused by pattern):

* the model input is ONLY the rendered registered case presentation
  (the frozen package is the sole prompt authority; no client prompt exists);
* the credential enters ONLY through the in-process session credential
  gateway (environment at launch; never a file, never Git, never evidence);
* the sealed ground truth is compared ONLY in-process by the frozen
  RVR-CLASSIFIER-1; classifications (never GT) are persisted;
* execution/transport success is NEVER converted into behavioral success
  and vice versa (state separation preserved end-to-end);
* every executed case produces case-bound evidence + audit + persistence
  under the evidence root (default: /home/z/ecp-rvr-evidence — OUTSIDE
  the repository);
* the campaign is ONE per evidence root: if a campaign ledger already
  exists there, the console refuses (one-shot discipline — use a fresh
  --evidence-root for a new campaign).

Usage:
    OPENROUTER_API_KEY=... python run_rvr_console.py            # campaign
    python run_rvr_console.py --verify-only                     # wiring proof
    python run_rvr_console.py --evidence-root DIR               # override

Ground-truth sidecar resolution (portable, owner-side): --gt-sidecar,
else the ECP_RVR_GT_SIDECAR environment variable, else a sibling
'ecp-rvr-private' directory next to the repository checkout, else the
executor-sandbox default /home/z/ecp-rvr-private.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from ecp.console_session import SessionCredentialGateway  # noqa: E402
from ecp.credentials import EnvironmentSecretStore  # noqa: E402
from ecp.credential_binding import AuthorizationGrant, CredentialBinding  # noqa: E402
from ecp.execution_contract import (  # noqa: E402
    ClientExecutionIntent,
    ExecutionContractResolver,
)
from ecp.rvr_campaign import (  # noqa: E402
    OPENROUTER_ENDPOINT,
    SCIENTIFIC_PURPOSE,
    build_runtime_registry,
    build_scientific_evaluation,
    execute_campaign,
)
from ecp.rvr_registration import (  # noqa: E402
    ADAPTER_ID,
    BINDING_ID,
    CREDENTIAL_ENV_VAR,
    EVALUATION_ID,
    PACKAGE_ID,
    PROVIDER_ID,
    SYSTEM_ID,
    binding_condition,
    binding_model,
    build_case_artifacts,
    load_verified_binding,
    load_verified_gt_sidecar,
    load_verified_package,
    public_case_views,
    registered_case_order,
    render_prompt,
)
from ecp.runtime_adapters import OpenRouterChatCompletionsAdapter  # noqa: E402

PACKAGE_PATH = REPO / "registration" / "RVR-REGISTRATION-V1.json"
BINDING_PATH = REPO / "registration" / "RVR-EXECUTION-BINDING-V1.json"
DEFAULT_EVIDENCE_ROOT = Path("/home/z/ecp-rvr-evidence")

#: Executor-sandbox private sidecar placement (last resolution step; the
#: sibling/env resolutions above make the launcher portable owner-side).
SANDBOX_GT_SIDECAR = Path("/home/z/ecp-rvr-private/RVR-PRIVATE-GT-SIDECAR-V1.json")


def _resolve_gt_sidecar(explicit: "str | None") -> Path:
    """Resolve the private GT sidecar (never inside the repository).

    Order: explicit --gt-sidecar, then ECP_RVR_GT_SIDECAR, then a sibling
    'ecp-rvr-private' directory next to the repository checkout (the
    documented owner-side placement), then the executor-sandbox default.
    """
    if explicit:
        return Path(explicit)
    env_sidecar = os.environ.get("ECP_RVR_GT_SIDECAR", "").strip()
    if env_sidecar:
        return Path(env_sidecar)
    sibling = REPO.parent / "ecp-rvr-private" / "RVR-PRIVATE-GT-SIDECAR-V1.json"
    if sibling.is_file():
        return sibling
    return SANDBOX_GT_SIDECAR


def _iso() -> str:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return now.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="RVR scientific execution console (registered surface, campaign ECP-EVAL-RVR-1)")
    parser.add_argument("--verify-only", action="store_true", help="prove the wiring without any credential or call")
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT), help="evidence persistence root (outside the repository; must not already contain a campaign ledger)")
    parser.add_argument("--gt-sidecar", default=None,
                        help="private GT sidecar (default: ECP_RVR_GT_SIDECAR env, else sibling 'ecp-rvr-private' "
                             "next to the repository, else the executor-sandbox default)")
    args = parser.parse_args()

    print("=== RVR SCIENTIFIC EXECUTION CONSOLE (registered surface) ===")
    print(f"campaign    : {EVALUATION_ID} — Reasoning vs Retrieval (ECP-EVAL-RVR-1)")

    sidecar_path = _resolve_gt_sidecar(args.gt_sidecar)
    if not sidecar_path.is_file():
        print(f"FATAL: the private GT sidecar was not found at {sidecar_path}.")
        print("The sealed answers are private scientific instruments: they are delivered")
        print("OUTSIDE the repository and are never committed/pushed. Fix ONE of:")
        print("  1. place the delivered sidecar at a sibling 'ecp-rvr-private' directory")
        print("     next to the repository checkout;")
        print("  2. set the environment variable ECP_RVR_GT_SIDECAR to its path;")
        print("  3. pass --gt-sidecar <path-to-RVR-PRIVATE-GT-SIDECAR-V1.json>.")
        return 1
    print(f"GT sidecar  : {sidecar_path} (private, outside the repository)")

    package = load_verified_package(PACKAGE_PATH)
    package_hash = package["integrity"]["package_hash"]
    print(f"package     : {package['package_id']} (hash {package_hash[:16]}… verified)")

    binding = load_verified_binding(BINDING_PATH, package)
    condition = binding_condition(binding)
    model_identifier = binding_model(binding)
    print(f"binding     : {binding['binding_id']} (hash {binding['binding_hash'][:16]}… verified)")
    print(f"target      : {model_identifier} @ {binding['target']['provider']}")
    print(f"condition   : {condition.get('condition_id')} — temp {condition.get('temperature')}, "
          f"max_tokens {condition.get('max_tokens')}, timeout {condition.get('transport_timeout_seconds')}s")

    gt_answers = load_verified_gt_sidecar(sidecar_path, package)
    artifacts = build_case_artifacts(package)
    case_views = public_case_views(package)
    ordered_case_ids = registered_case_order(package)
    print(f"cases       : {len(artifacts)} registered, prompt hashes verified, GT commitments verified")
    print(f"order       : frozen registered order ({ordered_case_ids[0]} … {ordered_case_ids[-1]})")

    evidence_root = Path(args.evidence_root)
    if REPO == evidence_root or REPO in evidence_root.parents:
        print("FATAL: the evidence root must be OUTSIDE the repository.")
        return 1
    if (evidence_root / "rvr-campaign-ledger.json").is_file():
        print(f"FATAL: a campaign ledger already exists at {evidence_root / 'rvr-campaign-ledger.json'}.")
        print("The registered contract is ONE campaign per evidence root (one attempt per")
        print("case, retry NONE). Start a NEW campaign with a fresh --evidence-root.")
        return 1

    adapter = OpenRouterChatCompletionsAdapter(
        model=model_identifier,
        endpoint=OPENROUTER_ENDPOINT,
        temperature=condition["temperature"],
        max_tokens=condition["max_tokens"],
        timeout=float(condition["transport_timeout_seconds"]),
    )
    registry = build_runtime_registry(adapter)

    suffix = uuid.uuid4().hex[:16].upper()

    if args.verify_only:
        binding_obj = CredentialBinding(
            f"ECP-BINDING-RVR-{suffix}",
            f"ECP-REQUIREMENT-RVR-{suffix}",
            f"ECP-TARGET-RVR-{suffix}",
            PROVIDER_ID,
            "openrouter-chat-completions-api",
            SCIENTIFIC_PURPOSE,
            "ECP-VERIFY-ONLY",
            frozenset({SCIENTIFIC_PURPOSE}),
        )
        grant = AuthorizationGrant(
            f"ECP-AUTH-RVR-{suffix}", binding_obj.binding_id, binding_obj.target_id,
            SCIENTIFIC_PURPOSE, frozenset({SCIENTIFIC_PURPOSE}), _iso(),
        )
        evaluation = build_scientific_evaluation("ECP-VERIFY-ONLY", binding_obj, grant, ordered_case_ids)
        resolver = ExecutionContractResolver({EVALUATION_ID: evaluation}, cases=artifacts, runtime_registry=registry)
        probe_case = ordered_case_ids[0]
        intent = ClientExecutionIntent(
            evaluation_id=EVALUATION_ID, test_id=probe_case, system_id=SYSTEM_ID,
            credential_ref="ECP-VERIFY-ONLY", request_id=f"ECP-REQ-VERIFY-{suffix}",
        )
        resolved = resolver.resolve(intent)
        transport_request = resolved.transport_request()
        print(f"resolver    : intent resolved for {probe_case}")
        print(f"prompt authority : {resolved.prompt_reference} (frozen package case record; no client prompt path exists)")
        print(f"model input : {len(transport_request['prompt'])} chars of registered presentation")
        print("wiring      : classifier RVR-CLASSIFIER-1 import verified; adapter endpoint "
              f"{OPENROUTER_ENDPOINT}")
        print("WIRING VERIFIED — no credential resolved, no provider call, no model call, no outcome.")
        return 0

    secret = os.environ.get(CREDENTIAL_ENV_VAR, "").strip()
    if not secret:
        print(f"FATAL: {CREDENTIAL_ENV_VAR} is not set — the credential must be supplied at launch "
              "(outside Git, outside records; it enters only the in-process gateway).")
        return 1

    gateway = SessionCredentialGateway(EnvironmentSecretStore(CREDENTIAL_ENV_VAR), {})
    handle = gateway.open_session(secret, ttl_seconds=86400)

    print(f"evidence    : {evidence_root} (outside the repository)")
    print(f"executing   : {len(ordered_case_ids)} one-shot cases against {model_identifier} …")

    campaign = execute_campaign(
        package=package,
        execution_binding=binding,
        artifacts=artifacts,
        case_views=case_views,
        gt_answers=gt_answers,
        adapter=adapter,
        gateway=gateway,
        credential_ref=handle["credential_ref"],
        evidence_root=evidence_root,
        log=print,
    )

    print(json.dumps(campaign["summary"], indent=2, sort_keys=True))
    print(f"campaign ledger: {evidence_root / 'rvr-campaign-ledger.json'}")
    print("next step    : post-campaign mechanical adjudication —")
    print(f"  python tools/rvr_adjudicate.py --evidence-root {evidence_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
