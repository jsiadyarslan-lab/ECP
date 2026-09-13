"""RVR registration loaders — verified access to the frozen campaign records.

Serves campaign ``ECP-EVAL-RVR-1`` (registration package ``ECP-REG-RVR-V1``,
frozen by the order *ECP — REASONING vs RETRIEVAL PREREGISTRATION FREEZE v1*
and committed as the single additive registration commit on baseline
``562e188``). Every loader is FAIL-CLOSED: identity fields are checked, every
registered hash rule is re-derived, and any mismatch aborts the surface
before a credential can be resolved or a provider called.

Three authorities, three verification surfaces:

* the FROZEN REGISTRATION PACKAGE (``registration/RVR-REGISTRATION-V1.json``,
  public in the repository) — cases, order, thresholds, decision rules,
  gt_commitments. ``package_hash`` = SHA-256 over ECP-CANONICAL-JSON-1.0 of
  the package with the ``integrity.package_hash`` field excluded (the frozen
  rule). Per-case ``case_sha256`` = canonical case record with the
  ``case_sha256`` field excluded; ``prompt_sha256`` = SHA-256 of the exact
  rendered prompt bytes; ``ordered_case_hash`` = canonical
  ``[{index, case_id, case_sha256}, …]`` list hash.
* the EXECUTION BINDING RECORD (``registration/RVR-EXECUTION-BINDING-V1.json``,
  public, additive) — the owner-authorized PRE-EXECUTION binding of the
  evaluated system, the frozen execution condition and the execution-surface
  identity. ``binding_hash`` = canonical record with the ``binding_hash``
  field excluded.
* the PRIVATE GROUND-TRUTH SIDECAR (owner-held, NEVER in the repository) —
  plaintext answers sealed by the public ``gt_commitment`` hashes
  (SHA-256 over canonical ``{case_id, ground_truth}``). The loader verifies
  every commitment before returning the in-process answer view; the answers
  reach ONLY the frozen classifier call site.

No M3 file is read or modified by this module; M3 mechanisms are reused by
pattern (OD-02), not by reference.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from .canonical import load_json
from .execution_contract import RegisteredCaseArtifact
from .hashing import hash_document

# ---------------------------------------------------------------------------
# Registered identities (frozen by the registration package + binding record)
# ---------------------------------------------------------------------------

#: The campaign these loaders serve.
EVALUATION_ID = "ECP-EVAL-RVR-1"

#: The frozen registration package identity.
PACKAGE_ID = "ECP-REG-RVR-V1"

#: The owner-authorized pre-execution binding record identity.
BINDING_ID = "ECP-REG-RVR-BINDING-V1"

#: The evaluated-system identity carried by the binding record.
SYSTEM_ID = "ECP-SYSTEM-RVR-001"

#: Provider / adapter identities (M3 fabric, reused by pattern).
PROVIDER_ID = "ECP-PROVIDER-OPENROUTER"
ADAPTER_ID = "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS"
RUNTIME_IDENTITY = "ECP-RUNTIME-LOCAL-GATEWAY-1"

#: The frozen execution condition identity (binding record).
CONDITION_ID = "ECP-COND-RVR-1"

#: The credential environment variable (launch-time only; never persisted).
CREDENTIAL_ENV_VAR = "OPENROUTER_API_KEY"

#: The pinned external endpoint (frozen by the binding record).
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# ---------------------------------------------------------------------------
# Frozen prompt rendering (RVR-ENVELOPE-1) — the sole prompt authority
# ---------------------------------------------------------------------------

#: The registered envelope tail; must equal the package's
#: ``prompt_envelope.template`` byte-for-byte (verified at load).
ENVELOPE_TAIL = (
    "Think as needed, then give your final answer as the LAST line of your "
    "reply, in exactly this format:\n"
    "ANSWER: <token>\n"
    "where <token> is one of: {tokens}\n"
    "You may optionally add one line 'CITED: <premise numbers>' immediately "
    "before the final line; it is optional and never affects scoring."
)


def render_prompt(case: Mapping[str, Any]) -> str:
    """Render the registered prompt for one case (frozen rule).

    Structure: ``Premises:`` header, numbered premises, the optional
    registered lure note (V-LURE only) set off by a blank line, a blank line,
    the registered question, a blank line, then the constant envelope tail
    with the case's registered grammar tokens substituted. This is the exact
    rule the frozen generator used; the loader enforces that the rendered
    prompt reproduces the registered ``prompt_sha256`` for every case.
    """
    lines = ["Premises:"]
    lines += [f"{i + 1}. {p}" for i, p in enumerate(case["premises"])]
    if case.get("lure_note"):
        lines += ["", case["lure_note"]]
    lines += ["", f"Question: {case['question']}", ""]
    tail = ENVELOPE_TAIL.format(tokens=" | ".join(case["answer_grammar"]["tokens"]))
    lines += tail.split("\n")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Frozen package loader (fail-closed on every registered hash rule)
# ---------------------------------------------------------------------------

def load_verified_package(package_path: "str | Path") -> dict:
    """Load the frozen RVR registration package with fail-closed verification.

    Verifies, in order: package identity; ``package_hash`` (canonical bytes
    with the hash field excluded); the envelope template hash; per-case
    identity, ``case_sha256``, ``prompt_sha256`` (full prompt re-rendering)
    and grammar sanity; the registered order list; and the
    ``ordered_case_hash``. Any mismatch raises ``SystemExit`` before the
    caller can resolve a credential or issue a provider call.
    """
    package = load_json(Path(package_path))
    if package.get("ecp_object") != "rvr-registration-package" or package.get("package_id") != PACKAGE_ID:
        raise SystemExit(f"FATAL: registration package identity mismatch ({package.get('package_id')!r})")
    claimed = package.get("integrity", {}).get("package_hash")
    recomputed = hash_document({k: v for k, v in package.items() if k != "integrity"} | {
        "integrity": {k: v for k, v in package.get("integrity", {}).items() if k != "package_hash"}
    })
    if claimed != recomputed:
        raise SystemExit("FATAL: registration package hash mismatch — the frozen package is not intact")

    envelope = package.get("prompt_envelope") or {}
    template_sha = hashlib.sha256((envelope.get("template") or "").encode("utf-8")).hexdigest()
    if template_sha != envelope.get("template_sha256") or (envelope.get("template") or "") != ENVELOPE_TAIL:
        raise SystemExit("FATAL: registered envelope template does not match the frozen rendering rule")

    cases = package.get("cases") or []
    if not cases:
        raise SystemExit("FATAL: the registration package carries no cases")
    seen_ids: set[str] = set()
    for case in cases:
        case_id = case.get("case_id")
        if not case_id or case_id in seen_ids:
            raise SystemExit(f"FATAL: malformed or duplicate case_id {case_id!r}")
        seen_ids.add(case_id)
        case_claimed = case.get("case_sha256")
        case_recomputed = hash_document({k: v for k, v in case.items() if k != "case_sha256"})
        if case_claimed != case_recomputed:
            raise SystemExit(f"FATAL: case_sha256 mismatch for {case_id}")
        grammar = case.get("answer_grammar") or {}
        tokens = grammar.get("tokens") or []
        if not tokens or len(set(tokens)) != len(tokens):
            raise SystemExit(f"FATAL: malformed answer grammar for {case_id}")
        prompt_recomputed = hashlib.sha256(render_prompt(case).encode("utf-8")).hexdigest()
        if prompt_recomputed != case.get("prompt_sha256"):
            raise SystemExit(f"FATAL: prompt_sha256 mismatch for {case_id} — the rendering rule diverges from the frozen rule")
        if case.get("variant") not in ("V-BASE", "V-RPT", "V-FLIP", "V-LURE"):
            raise SystemExit(f"FATAL: unregistered variant for {case_id}")

    ordered_recomputed = hash_document([
        {"index": i + 1, "case_id": c["case_id"], "case_sha256": c["case_sha256"]}
        for i, c in enumerate(cases)
    ])
    if ordered_recomputed != package.get("integrity", {}).get("ordered_case_hash"):
        raise SystemExit("FATAL: ordered_case_hash mismatch — the registered order is not intact")
    return package


def registered_case_order(package: Mapping[str, Any]) -> list[str]:
    """The frozen execution order: the package's registered case list."""
    return [c["case_id"] for c in package["cases"]]


# ---------------------------------------------------------------------------
# Execution binding loader (owner-authorized pre-execution target binding)
# ---------------------------------------------------------------------------

def load_verified_binding(binding_path: "str | Path", package: Mapping[str, Any]) -> dict:
    """Load the execution binding record with fail-closed verification.

    Verifies: binding identity; ``binding_hash`` (canonical bytes with the
    hash field excluded); agreement with the frozen package (campaign,
    package id, package hash, classifier hash); presence and well-formedness
    of the target system, the frozen condition, and the execution-surface
    identity block. Raises ``SystemExit`` on any mismatch.
    """
    binding = load_json(Path(binding_path))
    if binding.get("binding_id") != BINDING_ID:
        raise SystemExit(f"FATAL: execution binding identity mismatch ({binding.get('binding_id')!r})")
    claimed = binding.get("binding_hash")
    recomputed = hash_document({k: v for k, v in binding.items() if k != "binding_hash"})
    if claimed != recomputed:
        raise SystemExit("FATAL: execution binding hash mismatch — the binding record is not intact")
    if binding.get("campaign_id") != package.get("campaign_id") or binding.get("package_id") != package.get("package_id"):
        raise SystemExit("FATAL: execution binding does not reference this registration package")
    if binding.get("package_hash") != package.get("integrity", {}).get("package_hash"):
        raise SystemExit("FATAL: execution binding references a different package hash than the frozen package")
    classifier_sha = binding.get("classifier_sha256")
    if classifier_sha and classifier_sha != package.get("integrity", {}).get("classifier_hash"):
        raise SystemExit("FATAL: execution binding classifier hash disagrees with the frozen package")

    target = binding.get("target") or {}
    if not target.get("exact_model_api_identifier"):
        raise SystemExit("FATAL: execution binding carries no exact model identifier")
    condition = binding.get("condition") or {}
    for key, minimum in (("temperature", None), ("max_tokens", 1), ("transport_timeout_seconds", 1)):
        if key not in condition:
            raise SystemExit(f"FATAL: frozen condition is missing {key}")
    surface = binding.get("execution_surface_identity") or {}
    if not surface.get("files"):
        raise SystemExit("FATAL: execution binding carries no execution-surface file hashes")
    return binding


def binding_condition(binding: Mapping[str, Any]) -> dict:
    """The frozen execution condition (sampling + transport constants)."""
    return dict(binding["condition"])


def binding_model(binding: Mapping[str, Any]) -> str:
    """The pinned exact model identifier (never the moving alias identity)."""
    return binding["target"]["exact_model_api_identifier"]


# ---------------------------------------------------------------------------
# Private ground-truth sidecar loader (sealed answers; never persisted)
# ---------------------------------------------------------------------------

def load_verified_gt_sidecar(sidecar_path: "str | Path", package: Mapping[str, Any]) -> dict:
    """Load the PRIVATE GT sidecar and verify every sealed commitment.

    For each registered case the sidecar must carry exactly one entry whose
    recomputed commitment — SHA-256 over canonical ``{case_id, ground_truth}``
    — equals the public ``gt_commitment`` in the frozen package, and whose
    answer is a token of the case's registered grammar. Returns the
    in-process answer view ``{case_id: answer}``; the plaintext answers are
    consumed ONLY by the frozen classifier call site and are never persisted.
    """
    sidecar = load_json(Path(sidecar_path))
    if sidecar.get("sidecar_id") != "RVR-PRIVATE-GT-SIDECAR-V1":
        raise SystemExit(f"FATAL: unknown GT sidecar identity ({sidecar.get('sidecar_id')!r})")
    if sidecar.get("campaign_id") != package.get("campaign_id"):
        raise SystemExit("FATAL: GT sidecar campaign mismatch")
    gt_map = sidecar.get("gt") or {}
    answers: dict[str, str] = {}
    for case in package["cases"]:
        case_id = case["case_id"]
        entry = gt_map.get(case_id)
        if not isinstance(entry, dict) or "answer" not in entry:
            raise SystemExit(f"FATAL: GT sidecar entry missing for {case_id}")
        answer = entry["answer"]
        tokens = case["answer_grammar"]["tokens"]
        if answer not in tokens:
            raise SystemExit(f"FATAL: GT sidecar answer is not a registered token for {case_id}")
        commitment = hash_document({"case_id": case_id, "ground_truth": answer})
        if commitment != case.get("gt_commitment") or entry.get("gt_commitment") != case.get("gt_commitment"):
            raise SystemExit(f"FATAL: gt_commitment mismatch for {case_id} — the sealed answer does not match the frozen commitment")
        answers[case_id] = answer
    extra = set(gt_map) - {c["case_id"] for c in package["cases"]}
    if extra:
        raise SystemExit(f"FATAL: GT sidecar carries unregistered cases ({sorted(extra)[:3]} …)")
    return answers


# ---------------------------------------------------------------------------
# Case artifacts (the sole prompt authority for the resolver)
# ---------------------------------------------------------------------------

def build_case_artifacts(package: Mapping[str, Any]) -> "dict[str, RegisteredCaseArtifact]":
    """Build the resolver's case artifacts from the frozen package.

    The prompt is rendered by the frozen rule (already verified against
    ``prompt_sha256`` by the package loader); the artifact hash binds the
    case identity to the registered case hash and gt commitment.
    """
    artifacts: "dict[str, RegisteredCaseArtifact]" = {}
    for case in package["cases"]:
        artifact = RegisteredCaseArtifact.for_prompt(
            case["case_id"],
            render_prompt(case),
            case_artifact_hash=hash_document({
                "case_id": case["case_id"],
                "case_sha256": case["case_sha256"],
                "gt_commitment": case["gt_commitment"],
            }),
        )
        artifacts[case["case_id"]] = artifact
    return artifacts


def public_case_view(case: Mapping[str, Any]) -> dict:
    """The public classification-facing view of one registered case.

    Carries only material already public in the frozen package (premises,
    question, grammar, variant, family, depth, lure registry) — never any
    ground truth.
    """
    view = {
        "case_id": case["case_id"],
        "set_id": case["set_id"],
        "variant": case["variant"],
        "family": case["family"],
        "depth": case["depth"],
        "premises": list(case["premises"]),
        "question": case["question"],
        "answer_grammar": dict(case["answer_grammar"]),
    }
    if case.get("lure"):
        view["lure"] = dict(case["lure"])
    return view


def public_case_views(package: Mapping[str, Any]) -> "dict[str, dict]":
    """Public classification-facing views for every registered case."""
    return {c["case_id"]: public_case_view(c) for c in package["cases"]}


__all__ = [
    "ADAPTER_ID",
    "BINDING_ID",
    "CONDITION_ID",
    "CREDENTIAL_ENV_VAR",
    "ENVELOPE_TAIL",
    "EVALUATION_ID",
    "OPENROUTER_ENDPOINT",
    "PACKAGE_ID",
    "PROVIDER_ID",
    "RUNTIME_IDENTITY",
    "SYSTEM_ID",
    "binding_condition",
    "binding_model",
    "build_case_artifacts",
    "load_verified_binding",
    "load_verified_gt_sidecar",
    "load_verified_package",
    "public_case_view",
    "public_case_views",
    "registered_case_order",
    "render_prompt",
]
