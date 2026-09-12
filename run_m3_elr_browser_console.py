#!/usr/bin/env python3
"""M3-ELR scientific campaign BROWSER console — the registered browser surface.

Owner order 2026-09-13: the registered M3-ELR execution surface exposed in
the EXISTING evaluation console. The owner opens
http://127.0.0.1:8766/ in the browser, pairs with the code this launcher
prints, submits the OpenRouter credential through the existing credential
session gateway (the value is held in-process only), and presses RUN
CAMPAIGN: the frozen 30-case campaign executes through the SAME engine the
registered CLI launcher consumes (ecp.m3_elr_campaign.execute_campaign) —
same frozen package, same F-01b order, same condition, same frozen
classifier, same evidence/audit/ledger artifacts OUTSIDE the repository.

The launcher never sees, asks for or stores the credential value; it is
submitted once in the browser and held by the session credential gateway.
ONE campaign per launcher process (frozen single-attempt discipline): a
completed or failed campaign requires a launcher restart before a new one.

The pinned target never changes: the campaign always executes
inclusionai/ling-3.0-flash-sante:free @ OpenRouter under the frozen
condition. The discovery section of the console is informational (the owner
can verify the pinned model is listed and AVAILABLE before running).

Usage:
    python run_m3_elr_browser_console.py [--evidence-root DIR]
                                         [--case-area DIR]
                                         [--gateway-port 8765]
                                         [--console-port 8766]

Case-area resolution (portable, owner-side):
    --case-area DIR          explicit path wins
    ECP_CASE_AREA env var    otherwise
    <repo-parent>/ecp-ca0v1  otherwise (the documented owner-side placement:
                             unzip the delivered private area NEXT TO the repo)
    /home/z/ecp-ca0v1        last (executor-sandbox default)
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent
CONSOLE_PORT = 8766
GATEWAY_PORT = 8765
ARTIFACT_ROOT = REPO / "local-browser-artifacts"
DEFAULT_EVIDENCE_ROOT = REPO.parent / "ecp-m3-elr-evidence"

sys.path.insert(0, str(REPO / "src"))

from ecp.adapters import AdapterRegistry  # noqa: E402
from ecp.canonical import load_json  # noqa: E402
from ecp.console import GatewayConfig, LocalGateway  # noqa: E402
from ecp.console_session import (  # noqa: E402
    ConsoleSessionManager,
    SessionCredentialGateway,
)
from ecp.credentials import SecretStore  # noqa: E402
from ecp.discovery import ProviderDiscoveryService, builtin_discovery_registry  # noqa: E402
from ecp.m3_elr_campaign import (  # noqa: E402
    OPENROUTER_ENDPOINT,
    build_runtime_registry,
    load_verified_package,
)
from ecp.m3_elr_campaign_console import M3ELRCampaignConsole  # noqa: E402
from ecp.m3_registration import POPULATION_ID, TARGET_MODEL_IDENTIFIER  # noqa: E402
from ecp.m3_readiness import run_readiness_gate  # noqa: E402
from ecp.onboarding import TargetOnboardingService  # noqa: E402
from ecp.registered_cases import (  # noqa: E402
    candidate_manifest_index,
    load_case_contents,
    load_registered_cases,
)
from ecp.runtime_adapters import (  # noqa: E402
    AnthropicMessagesAdapter,
    GeminiGenerateContentAdapter,
    OpenAIResponsesAdapter,
    OpenRouterChatCompletionsAdapter,
    RuntimeAdapterRegistry,
)
from ecp.targets import ProviderRegistry, TargetRegistry  # noqa: E402

PACKAGE_PATH = REPO / "registration" / "M3-ELR-REGISTRATION-V1.json"

#: Executor-sandbox private qualification area (recovered byte-exact). Only
#: used as the LAST resolution step; the sibling/env resolutions above make
#: the launcher portable to the owner's machine.
SANDBOX_CASE_AREA = "/home/z/ecp-ca0v1"


def _resolve_case_area(explicit: "str | None") -> Path:
    """Resolve the private qualification area (never inside the repository).

    Order: explicit --case-area, then ECP_CASE_AREA, then a sibling
    'ecp-ca0v1' directory next to the repository checkout (the documented
    owner-side placement), then the executor-sandbox default.
    """
    if explicit:
        return Path(explicit)
    env_area = os.environ.get("ECP_CASE_AREA", "").strip()
    if env_area:
        return Path(env_area)
    sibling = REPO.parent / "ecp-ca0v1"
    if sibling.is_dir():
        return sibling
    return Path(SANDBOX_CASE_AREA)


class _NoBackingStore(SecretStore):
    """Browser-only credential backing: no environment credentials exist.

    Session credentials (owner-submitted in the browser) live in the
    session store; the backing store simply has nothing else to offer.
    """

    def _read(self, credential_id: str, version: str) -> "str | None":
        return None

    def _write(self, credential_id: str, version: str, secret: str) -> None:
        raise PermissionError("no backing credentials exist in the browser console")

    def _delete(self, credential_id: str, version: str) -> None:
        return None


def _session_adapter_factory(
    adapter_kind,
    *,
    model,
    endpoint,
    provider,
    adapter_id,
    token_header=None,
    bearer_value=None,
    extra_headers=None,
):
    """Build the runtime adapter for a session-discovered target (real kinds).

    Mirrors the universal launcher's factory for the four real provider
    dialects; offline demonstration kinds have no session here (the owner
    submits a REAL provider credential for discovery).
    """
    if adapter_kind == "openai-responses":
        return OpenAIResponsesAdapter(model=model, endpoint=endpoint, provider=provider, adapter_id=adapter_id)
    if adapter_kind == "gemini-generate-content":
        return GeminiGenerateContentAdapter(model=model, endpoint=endpoint, provider=provider, adapter_id=adapter_id)
    if adapter_kind == "anthropic-messages":
        return AnthropicMessagesAdapter(model=model, endpoint=endpoint, provider=provider, adapter_id=adapter_id)
    if adapter_kind == "openrouter-chat-completions":
        return OpenRouterChatCompletionsAdapter(
            model=model,
            endpoint=endpoint,
            provider=provider,
            adapter_id=adapter_id,
            token_header=token_header,
            bearer_value=bearer_value,
            extra_headers=extra_headers,
        )
    raise ValueError(f"session adapter kind {adapter_kind!r} is not available in the M3-ELR console")


def main() -> int:
    parser = argparse.ArgumentParser(description="M3-ELR scientific campaign browser console (registered surface)")
    parser.add_argument("--evidence-root", default=str(DEFAULT_EVIDENCE_ROOT),
                        help="evidence persistence root, OUTSIDE the repository (default: sibling of the repo)")
    parser.add_argument("--case-area", default=None,
                        help="private qualification area (default: ECP_CASE_AREA env, else sibling 'ecp-ca0v1' "
                             "next to the repository, else the executor-sandbox default)")
    parser.add_argument("--gateway-port", type=int, default=GATEWAY_PORT)
    parser.add_argument("--console-port", type=int, default=CONSOLE_PORT)
    args = parser.parse_args()

    print("=== M3-ELR SCIENTIFIC CAMPAIGN BROWSER CONSOLE (registered surface) ===")
    case_area = _resolve_case_area(args.case_area)
    if not (case_area / "qualification" / "candidates").is_dir():
        print(f"FATAL: the private qualification case area was not found at {case_area}.")
        print("The 30 registered case artifacts are private scientific instruments: they are")
        print("delivered OUTSIDE the repository and are never committed/pushed. Fix ONE of:")
        print("  1. unzip the delivered 'ecp-ca0v1' archive as a SIBLING of the repo")
        print("     (e.g. .../Documents/GitHub/ecp-ca0v1 next to .../Documents/GitHub/ECP);")
        print("  2. set the environment variable ECP_CASE_AREA to the ecp-ca0v1 path;")
        print("  3. pass --case-area <path-to-ecp-ca0v1>.")
        return 1
    print(f"case area   : {case_area} (private, outside the repository)")
    package = load_verified_package(PACKAGE_PATH)
    print(f"package      : {package['package_id']} (hash {package['package_hash'][:16]}… verified)")

    manifest = load_json(REPO / "provenance" / "m3-population-namespace-manifest.json")
    manifest_index = candidate_manifest_index(manifest, POPULATION_ID)

    artifacts = load_registered_cases(package, case_area=case_area, manifest_index=manifest_index)
    contents = load_case_contents(package, case_area=case_area)
    ordered_test_ids = package["ordered_test_ids"]
    print(f"cases        : {len(artifacts)} registered, four-surface verified")
    print(f"order        : F-01b frozen ({ordered_test_ids[0]} … {ordered_test_ids[-1]})")

    gate = run_readiness_gate(repo=REPO, package_path=PACKAGE_PATH, case_area=case_area)
    print(f"§22 gate     : {gate['summary']['pass']} PASS / {gate['summary']['pending']} PENDING / {gate['summary']['fail']} FAIL")
    for check in gate["checks"]:
        if check["status"] == "FAIL":
            print(f"  FAIL {check['id']}: {check['description']} — {check['evidence']}")
    for check in gate["checks"]:
        if check["status"] == "PENDING":
            print(f"  PENDING {check['id']}: {check['evidence']}")
    if gate["summary"]["fail"]:
        print("FATAL: the readiness gate has failing checks — refusing to serve the campaign surface.")
        return 1

    adapter = OpenRouterChatCompletionsAdapter(
        model=TARGET_MODEL_IDENTIFIER,
        endpoint=OPENROUTER_ENDPOINT,
        temperature=package["condition"]["temperature"],
        max_tokens=package["condition"]["max_tokens"],
        timeout=float(package["condition"]["transport_timeout_seconds"]),
    )
    evidence_root = Path(args.evidence_root)
    print(f"evidence     : {evidence_root} (outside the repository)")

    session_credentials = SessionCredentialGateway(_NoBackingStore(), {})
    providers = ProviderRegistry()
    targets = TargetRegistry(providers)
    adapters = AdapterRegistry()
    runtime = RuntimeAdapterRegistry()
    service = TargetOnboardingService(providers, targets, adapters, runtime, session_credentials)

    config = GatewayConfig(
        allowed_origins=frozenset({
            f"http://127.0.0.1:{args.console_port}",
            f"http://localhost:{args.console_port}",
        }),
        port=args.gateway_port,
        artifact_root=ARTIFACT_ROOT,
    )
    gateway = LocalGateway(config, service.evaluations, session_credentials, runtime)

    session_manager = ConsoleSessionManager(
        gateway=gateway,
        session_credentials=session_credentials,
        discovery=ProviderDiscoveryService(builtin_discovery_registry()),
        onboarding=service,
        adapter_factory=_session_adapter_factory,
    )
    campaign_console = M3ELRCampaignConsole(
        session_manager=session_manager,
        session_credentials=session_credentials,
        package=package,
        artifacts=artifacts,
        contents=contents,
        adapter=adapter,
        evidence_root=evidence_root,
        gate=gate,
    )
    gateway.enable_session_console(campaign_console)

    # Keep the frozen adapter reachable under its declared identity for the
    # engine (the gateway registry serves session-discovered targets).
    build_runtime_registry(adapter)

    gateway_server = gateway.make_server()
    threading.Thread(target=gateway_server.serve_forever, daemon=True).start()

    print(f"ECP gateway listening on 127.0.0.1:{config.port}")
    print(f"Console: http://127.0.0.1:{args.console_port}/")
    print(f"PAIRING CODE: {gateway.pairing_code}")
    print("Flow: PAIR with the code -> paste the OpenRouter credential -> OPEN CREDENTIAL SESSION -> RUN CAMPAIGN.")
    print("ONE campaign per launcher process (frozen single-attempt discipline); restart for a new campaign.")
    print("Press Ctrl+C to stop.")

    os.chdir(REPO / "console")
    console_server = ThreadingHTTPServer(("127.0.0.1", args.console_port), SimpleHTTPRequestHandler)
    try:
        console_server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        console_server.server_close()
        gateway_server.shutdown()
        gateway_server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
