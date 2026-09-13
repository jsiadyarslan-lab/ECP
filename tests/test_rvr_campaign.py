"""RVR campaign engine + registration loaders + adjudication tests (hermetic).

Hermetic: a synthetic mini registration package built with the REAL frozen
hash rules (case_sha256 / prompt_sha256 / ordered_case_hash / package_hash /
gt_commitment / binding_hash), the REAL frozen prompt rendering rule, the
REAL RVR-CLASSIFIER-1, a real SessionCredentialGateway, and an OFFLINE
deterministic adapter (zero network). Proves the engine produces the
registered evidence/audit/ledger artifacts with the frozen single-attempt
discipline, that every loader fails closed on tampering, that sealed ground
truth never persists, and that the post-campaign adjudicator applies the
frozen G-0 / R / M / I rules mechanically.
"""
import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from ecp.console_session import SessionCredentialGateway  # noqa: E402
from ecp.credentials import SecretStore  # noqa: E402
from ecp.hashing import hash_document  # noqa: E402
from ecp.rvr_campaign import execute_campaign  # noqa: E402
from ecp.rvr_registration import (  # noqa: E402
    BINDING_ID,
    ENVELOPE_TAIL,
    EVALUATION_ID,
    PACKAGE_ID,
    build_case_artifacts,
    load_verified_binding,
    load_verified_gt_sidecar,
    load_verified_package,
    public_case_views,
    render_prompt,
)
from ecp.runtime_adapters import RuntimeAdapterTransportError  # noqa: E402

SECRET = "test-session-secret-12345678"

FROZEN_THRESHOLDS = {
    "G0_BCR_min": 0.6,
    "G0_evaluable_CFTR_denominator_min": 15,
    "G0_IVR_plus_EFR_max": 0.25,
    "R1_CFTR_min": 0.7,
    "R2_RIR_min": 0.7,
    "R3_rule": "LCR <= 0.25 OR LRR >= BCR - 0.15 (one compound rule)",
    "R4_EFR_max": 0.15,
    "M1_rule": "BCR >= 0.60 AND CFTR <= 0.40",
    "M2_LCR_min": 0.5,
    "M3_rule": "BCR >= 0.60 AND RIR <= 0.50",
}


class _EmptyBackingStore(SecretStore):
    def _read(self, credential_id, version):
        return None

    def _write(self, credential_id, version, secret):
        raise PermissionError("no backing credentials in tests")

    def _delete(self, credential_id, version):
        return None


class OfflineScriptedAdapter:
    """Deterministic offline adapter: replies scripted per case_id."""

    provider = "ECP-PROVIDER-OPENROUTER"
    adapter_id = "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS"
    model = "offline-test-model"

    def __init__(self, replies, fail_cases=()):
        self.replies = dict(replies)
        self.fail_cases = set(fail_cases)
        self.calls = []

    def execute(self, lease, request):
        assert lease.value == SECRET
        case_id = request["test_id"]
        self.calls.append(case_id)
        if case_id in self.fail_cases:
            exc = RuntimeAdapterTransportError("PROVIDER_REQUEST_FAILED")
            exc.http_status = 500
            raise exc
        return {
            "provider_status": "RECEIVED",
            "response_id": f"offline-{request['request_id']}",
            "model": self.model,
            "output_text": self.replies[case_id],
            "request_id": request["request_id"],
            "transport_kind": "offline-mock",
            "endpoint": "https://openrouter.ai/api/v1/chat/completions",
            "http_status": 200,
            "latency_ms": 1,
        }


# ---------------------------------------------------------------------------
# Synthetic mini-package builder (real frozen hash rules)
# ---------------------------------------------------------------------------

def _mini_world(n):
    """Deterministic synthetic world: chain a > b > c( > d)."""
    names = [f"entity{n}x{i}" for i in range(4)]
    rel = "taller than" if n % 2 == 0 else "heavier than"
    if n % 2 == 0:
        premises = [
            f"The {names[0]} is {rel} the {names[1]}.",
            f"The {names[1]} is {rel} the {names[2]}.",
            f"The {names[2]} is {rel} the {names[3]}.",
        ]
    else:
        premises = [
            f"The {names[1]} is {rel} the {names[0]}.",
            f"The {names[2]} is {rel} the {names[1]}.",
            f"The {names[3]} is {rel} the {names[2]}.",
        ]
    order = names if n % 2 == 0 else names[::-1]
    return names, premises, order


def build_mini_package(mvs_count=16):
    """Build a hash-valid synthetic mini package + sidecar + binding."""
    cases, mvs, gt_map = [], [], {}
    families = ["F1", "F2", "F3", "F4"]
    for s in range(1, mvs_count + 1):
        names, base_premises, order = _mini_world(s)
        rel = "taller than" if s % 2 == 0 else "heavier than"
        fam = families[s % 4]
        base_gt = order[0]
        rpt_names = [f"renamed{s}x{i}" for i in range(4)]
        set_id = f"ECP-MVS-RVR-{s:03d}"
        variants = {}

        def make_case(case_id, variant, premises, tokens, lure=None, lure_note=None):
            question = f"Which of these is the tallest: {tokens[0]}, {tokens[1]}, or {tokens[2]}?"
            case = {
                "case_id": case_id, "set_id": set_id, "variant": variant,
                "family": fam, "family_name": f"family-{fam}", "depth": 1 + (s % 3),
                "premises": premises, "question": question,
                "answer_grammar": {"type": "value_enum", "tokens": list(tokens)},
                "prompt_envelope": "RVR-ENVELOPE-1",
                "provenance": {"generator": "test", "seed": "test-seed", "set_key": set_id},
                "gt_commitment": hash_document(
                    {"case_id": case_id, "ground_truth": gt_for(variant, tokens)}),
            }
            if lure:
                case["lure"] = lure
            if lure_note:
                case["lure_note"] = lure_note
            case["case_sha256"] = hash_document(
                {k: v for k, v in case.items() if k != "case_sha256"})
            case["prompt_sha256"] = None  # set below (needs final fields)
            case["prompt_sha256"] = __import__("hashlib").sha256(
                render_prompt(case).encode("utf-8")).hexdigest()
            # case_sha256 must cover the final record: recompute with the
            # prompt hash included (prompt_sha256 is a registered field).
            case.pop("case_sha256")
            case["case_sha256"] = hash_document(
                {k: v for k, v in case.items() if k != "case_sha256"})
            return case

        def gt_for(variant, tokens):
            if variant == "V-BASE":
                return tokens[0]
            if variant == "V-RPT":
                return rpt_names[0]
            if variant == "V-FLIP":
                return tokens[1]
            return tokens[0]

        base = make_case(f"ECP-CASE-RVR-{s * 4 - 3:03d}", "V-BASE", base_premises, names)
        rpt_premises = [
            f"The {rpt_names[0]} is taller than the {rpt_names[1]}.",
            f"The {rpt_names[1]} is taller than the {rpt_names[2]}.",
            f"The {rpt_names[2]} is taller than the {rpt_names[3]}.",
        ]
        rpt = make_case(f"ECP-CASE-RVR-{s * 4 - 2:03d}", "V-RPT", rpt_premises, rpt_names)
        # registered flip: premise 1 with its pair swapped (minimal edit;
        # the mini package tests engine/adjudicator mechanics, not world logic)
        flip_premises = list(base_premises)
        flip_premises[0] = f"The {names[1]} is {rel} the {names[0]}."
        flip = make_case(f"ECP-CASE-RVR-{s * 4 - 1:03d}", "V-FLIP", flip_premises, names)
        lure = {"class": "LC-1", "template_id": "L-TEST-1", "lure_answer": names[1],
                "note": "(test lure)"}
        lure_case = make_case(f"ECP-CASE-RVR-{s * 4:03d}", "V-LURE", base_premises, names,
                              lure=lure, lure_note="(Note: for test purposes only.)")
        for c in (base, rpt, flip, lure_case):
            cases.append(c)
            gt_map[c["case_id"]] = {
                "answer": gt_for(c["variant"], c["answer_grammar"]["tokens"]),
                "gt_commitment": c["gt_commitment"],
            }
        mvs.append({
            "set_id": set_id, "family": fam, "family_name": f"family-{fam}",
            "depth": 1 + (s % 3), "cell_index": s,
            "variants": {"V-BASE": base["case_id"], "V-RPT": rpt["case_id"],
                         "V-FLIP": flip["case_id"], "V-LURE": lure_case["case_id"]},
            "mvs_sha256": hash_document({
                "V-BASE": base["case_id"], "V-RPT": rpt["case_id"],
                "V-FLIP": flip["case_id"], "V-LURE": lure_case["case_id"]}),
        })

    ordered_case_hash = hash_document([
        {"index": i + 1, "case_id": c["case_id"], "case_sha256": c["case_sha256"]}
        for i, c in enumerate(cases)])
    package = {
        "ecp_object": "rvr-registration-package",
        "package_id": PACKAGE_ID,
        "package_version": 1,
        "campaign_id": EVALUATION_ID,
        "schema_version": "RVR-REG-1.0",
        "registered_at": "2026-09-13",
        "order_reference": "test",
        "campaign_size": {"mvs_count": mvs_count, "case_count": len(cases),
                          "execution_count": len(cases), "attempts_per_case": 1,
                          "retry_policy": "NONE"},
        "grid": {"families": ["F1", "F2", "F3", "F4"], "depths": [1, 2, 3],
                 "mvs_per_cell": mvs_count // 12},
        "owner_freeze": {"frozen_by": "test", "thresholds": dict(FROZEN_THRESHOLDS)},
        "decision_rules": {
            "gate_G0": "BCR >= 0.60 AND evaluable CFTR denominator >= 15 AND IVR + EFR <= 0.25",
            "pattern_R": "CFTR >= 0.70 AND RIR >= 0.70 AND (LCR <= 0.25 OR LRR >= BCR - 0.15) AND EFR <= 0.15",
            "pattern_M": "(BCR >= 0.60 AND CFTR <= 0.40) OR LCR >= 0.50 OR (BCR >= 0.60 AND RIR <= 0.50)",
            "pattern_I": "everything else",
            "firewalls": ["INDETERMINATE is a legitimate scientific outcome"],
        },
        "endpoints": {
            "primary": {"name": "CFTR — Counterfactual Flip-Tracking Rate"},
            "secondary_labeled_never_promoted": {},
            "promotion_rule": "secondary endpoints are never promoted post-hoc",
        },
        "prompt_envelope": {
            "id": "RVR-ENVELOPE-1", "template": ENVELOPE_TAIL,
            "template_sha256": __import__("hashlib").sha256(
                ENVELOPE_TAIL.encode("utf-8")).hexdigest(),
            "note": "constant across all cases",
        },
        "cases": cases,
        "mvs": mvs,
        "mvs_binding_map": {m["set_id"]: m["variants"] for m in mvs},
        "answer_space_distribution": {},
        "hypotheses": {}, "claim_boundaries": {}, "m3_separation": {},
        "generation": {}, "baseline": {}, "design_reference": {},
        "execution_lock": {"status": "PREREGISTERED — EXECUTION LOCKED"},
        "integrity": {
            "canonicalization": "ECP-CANONICAL-JSON-1.0",
            "case_hash_rule": "sha256 over canonical case record with the case_sha256 field excluded",
            "gt_commitment_rule": "sha256 over canonical {case_id, ground_truth}",
            "ordered_case_hash": ordered_case_hash,
            "classifier_hash": "test-classifier-hash",
            "package_hash_rule": "SHA-256 over ECP-CANONICAL-JSON-1.0 of the package document with the integrity.package_hash field excluded",
        },
    }
    package["integrity"]["package_hash"] = hash_document(
        {k: v for k, v in package.items() if k != "integrity"} | {
            "integrity": {k: v for k, v in package["integrity"].items() if k != "package_hash"}})

    sidecar = {
        "sidecar_id": "RVR-PRIVATE-GT-SIDECAR-V1",
        "campaign_id": EVALUATION_ID,
        "note": "test sidecar",
        "gt": gt_map,
        "flip_gt": {},
    }
    binding = {
        "binding_id": BINDING_ID,
        "campaign_id": EVALUATION_ID,
        "package_id": PACKAGE_ID,
        "package_hash": package["integrity"]["package_hash"],
        "classifier_sha256": None,
        "binding_class": "PRE-EXECUTION TARGET AND CONDITION BINDING (owner-authorized, data-blind)",
        "target": {
            "system_id": "ECP-SYSTEM-RVR-001",
            "provider": "ECP-PROVIDER-OPENROUTER",
            "adapter": "ECP-ADAPTER-OPENROUTER-CHAT-COMPLETIONS",
            "exact_model_api_identifier": "offline-test-model",
            "official_name": "Offline Test Model",
        },
        "condition": {
            "condition_id": "ECP-COND-RVR-1",
            "model_state": "MODEL-ENABLED",
            "level": "L1 model-only",
            "temperature": 0.0,
            "max_tokens": 1024,
            "transport_timeout_seconds": 90,
        },
        "execution_contract": {
            "attempts_per_case": 1, "retry_policy": "NONE",
            "case_order": "the frozen package registered case order, unmodified",
        },
        "execution_surface_identity": {"files": {"run_rvr_console.py": "0" * 64}},
    }
    binding["binding_hash"] = hash_document(
        {k: v for k, v in binding.items() if k != "binding_hash"})
    return package, sidecar, binding


def write_mini_package(tmp_path, mvs_count=16):
    package, sidecar, binding = build_mini_package(mvs_count)
    pkg_path = tmp_path / "RVR-REGISTRATION-V1.json"
    side_path = tmp_path / "RVR-PRIVATE-GT-SIDECAR-V1.json"
    bind_path = tmp_path / "RVR-EXECUTION-BINDING-V1.json"
    for path, doc in ((pkg_path, package), (side_path, sidecar), (bind_path, binding)):
        path.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return package, sidecar, binding, pkg_path, side_path, bind_path


def open_test_session():
    gateway = SessionCredentialGateway(_EmptyBackingStore(), {})
    handle = gateway.open_session(SECRET, ttl_seconds=3600)
    return gateway, handle["credential_ref"]


def run_engine(package, binding, sidecar, adapter, tmp_path):
    gateway, credential_ref = open_test_session()
    return execute_campaign(
        package=package,
        execution_binding=binding,
        artifacts=build_case_artifacts(package),
        case_views=public_case_views(package),
        gt_answers={cid: e["answer"] for cid, e in sidecar["gt"].items()},
        adapter=adapter,
        gateway=gateway,
        credential_ref=credential_ref,
        evidence_root=tmp_path,
    )


def reply_for(state, gt, wrong_token=None, lure_answer=None):
    if state == "CORRECT":
        return f"Reasoning...\nCITED: 1, 2\nANSWER: {gt}"
    if state == "INCORRECT":
        return f"Reasoning...\nANSWER: {wrong_token}"
    if state == "OVERRIDE":
        return f"Reasoning...\nANSWER: {gt}"  # repeats the base-associated answer
    if state == "INCORRECT_LURE":
        return f"Reasoning...\nANSWER: {lure_answer}"
    if state == "ABSTAIN":
        return "Reasoning...\nANSWER: cannot"
    if state == "NON_ANSWER":
        return "I believe the first entity is the tallest."
    return "Reasoning...\nANSWER: yes"


# ---------------------------------------------------------------------------
# Loaders (fail-closed)
# ---------------------------------------------------------------------------

def test_loaders_accept_hash_valid_package_and_sidecar(tmp_path):
    package, sidecar, binding, pkg_path, side_path, bind_path = write_mini_package(tmp_path)
    loaded = load_verified_package(pkg_path)
    assert loaded["package_id"] == PACKAGE_ID
    assert loaded["integrity"]["package_hash"] == package["integrity"]["package_hash"]
    loaded_binding = load_verified_binding(bind_path, loaded)
    assert loaded_binding["binding_id"] == BINDING_ID
    answers = load_verified_gt_sidecar(side_path, loaded)
    assert len(answers) == len(package["cases"])
    for case in package["cases"]:
        assert answers[case["case_id"]] == sidecar["gt"][case["case_id"]]["answer"]


def test_package_loader_fails_closed_on_tampered_case(tmp_path):
    package, _, _, pkg_path, _, _ = write_mini_package(tmp_path)
    doc = json.loads(pkg_path.read_text())
    doc["cases"][0]["premises"][0] += " TAMPERED"
    pkg_path.write_text(json.dumps(doc))
    with pytest.raises(SystemExit):
        load_verified_package(pkg_path)


def test_package_loader_fails_closed_on_tampered_prompt_rule(tmp_path):
    package, _, _, pkg_path, _, _ = write_mini_package(tmp_path)
    doc = json.loads(pkg_path.read_text())
    doc["prompt_envelope"]["template"] = "ANSWER: whatever"
    pkg_path.write_text(json.dumps(doc))
    with pytest.raises(SystemExit):
        load_verified_package(pkg_path)


def test_sidecar_loader_fails_closed_on_wrong_answer(tmp_path):
    package, sidecar, _, pkg_path, side_path, _ = write_mini_package(tmp_path)
    loaded = load_verified_package(pkg_path)
    doc = json.loads(side_path.read_text())
    first_id = doc["cases"] if False else package["cases"][0]["case_id"]
    doc["gt"][first_id]["answer"] = package["cases"][0]["answer_grammar"]["tokens"][-1]
    side_path.write_text(json.dumps(doc))
    with pytest.raises(SystemExit):
        load_verified_gt_sidecar(side_path, loaded)


def test_binding_loader_fails_closed_on_tampered_hash(tmp_path):
    package, _, _, pkg_path, _, bind_path = write_mini_package(tmp_path)
    loaded = load_verified_package(pkg_path)
    doc = json.loads(bind_path.read_text())
    doc["condition"]["temperature"] = 1.5
    bind_path.write_text(json.dumps(doc))
    with pytest.raises(SystemExit):
        load_verified_binding(bind_path, loaded)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def test_engine_executes_frozen_order_and_persists_artifacts(tmp_path):
    package, sidecar, binding, *_ = write_mini_package(tmp_path, mvs_count=2)
    gt = {cid: e["answer"] for cid, e in sidecar["gt"].items()}
    replies = {}
    for case in package["cases"]:
        lure = case.get("lure", {}).get("lure_answer")
        replies[case["case_id"]] = reply_for("CORRECT", gt[case["case_id"]], lure_answer=lure)
    adapter = OfflineScriptedAdapter(replies)
    campaign = run_engine(package, binding, sidecar, adapter, tmp_path)
    ordered = [c["case_id"] for c in package["cases"]]
    assert [e["case_id"] for e in campaign["ledger"]] == ordered
    assert [e["position"] for e in campaign["ledger"]] == list(range(1, len(ordered) + 1))
    assert adapter.calls == ordered
    assert campaign["summary"]["attempted"] == len(ordered)
    assert campaign["summary"]["execution_valid"] == len(ordered)
    ledger_path = tmp_path / "rvr-campaign-ledger.json"
    assert ledger_path.is_file()
    evidence_files = sorted((tmp_path / "executions").glob("*-evidence.json"))
    assert len(evidence_files) == len(ordered)
    assert len(list((tmp_path / "executions").glob("*-audit.json"))) == len(ordered)
    for path in evidence_files:
        ev = json.loads(path.read_text())
        assert ev["ecp_object"] == "rvr-execution-evidence"
        assert ev["answer_state"] == "CORRECT"
        assert ev["classifier_id"] == "RVR-CLASSIFIER-1"
        assert ev["registration_reference"]["package_hash"] == package["integrity"]["package_hash"]
        # sealed ground truth never persists: no plaintext GT field exists
        assert "ground_truth" not in ev
        assert "gt_answer" not in ev
        assert ev["gt_commitment_reference"]  # commitment (hash), not the answer
        audit_path = path.parent / path.name.replace("-evidence.json", "-audit.json")
        audit = json.loads(audit_path.read_text())
        assert audit["audit_status"] == "PENDING_HUMAN_REVIEW"
        assert audit["evidence_hash"] == ev["evidence_hash"]


def test_engine_records_transport_failure_as_invalid_and_continues(tmp_path):
    package, sidecar, binding, *_ = write_mini_package(tmp_path, mvs_count=2)
    gt = {cid: e["answer"] for cid, e in sidecar["gt"].items()}
    replies, fail_cases = {}, set()
    for case in package["cases"]:
        replies[case["case_id"]] = reply_for("CORRECT", gt[case["case_id"]])
        if case["variant"] == "V-FLIP" and len(fail_cases) < 1:
            fail_cases.add(case["case_id"])
    adapter = OfflineScriptedAdapter(replies, fail_cases=fail_cases)
    campaign = run_engine(package, binding, sidecar, adapter, tmp_path)
    assert campaign["summary"]["execution_invalid"] == 1
    failed = [e for e in campaign["ledger"] if e["execution_status"] == "INVALID"]
    assert len(failed) == 1
    assert failed[0]["answer_state"] == "INVALID_EXECUTION"
    assert failed[0]["provider_status"] == "PROVIDER_REQUEST_FAILED"
    # the engine never aborts on transport failure: all cases attempted once
    assert campaign["summary"]["attempted"] == len(package["cases"])
    assert len(adapter.calls) == len(package["cases"])


def test_engine_classifies_nonanswer_and_abstention_distinctly(tmp_path):
    package, sidecar, binding, *_ = write_mini_package(tmp_path, mvs_count=1)
    gt = {cid: e["answer"] for cid, e in sidecar["gt"].items()}
    replies = {}
    for case in package["cases"]:
        if case["variant"] == "V-RPT":
            replies[case["case_id"]] = reply_for("NON_ANSWER", gt[case["case_id"]])
        elif case["variant"] == "V-LURE":
            replies[case["case_id"]] = reply_for("ABSTAIN", gt[case["case_id"]])
        else:
            replies[case["case_id"]] = reply_for("CORRECT", gt[case["case_id"]])
    adapter = OfflineScriptedAdapter(replies)
    campaign = run_engine(package, binding, sidecar, adapter, tmp_path)
    states = {e["variant"]: e["answer_state"] for e in campaign["ledger"]}
    assert states["V-RPT"] == "NON_ANSWER"
    # frozen semantics: the enum answer space does not include 'cannot', so
    # an abstention token on an enum case violates the registered envelope
    # grammar -> MALFORMED_ANSWER (never INCORRECT, never silently flipped)
    assert states["V-LURE"] == "MALFORMED_ANSWER"
    assert states["V-BASE"] == "CORRECT"


def test_classifier_polar_abstention_paths():
    from ecp.rvr_classifier import classify_response
    polar_case = {"premises": ["p1", "p2"], "question": "q?",
                  "answer_grammar": {"type": "yes_no_cannot", "tokens": ["yes", "no", "cannot"]}}
    assert classify_response("ANSWER: cannot", polar_case, "cannot")["answer_state"] == "CORRECT_ABSTENTION"
    assert classify_response("ANSWER: cannot", polar_case, "yes")["answer_state"] == "INCORRECT_ABSTENTION"
    assert classify_response("ANSWER: yes", polar_case, "cannot")["answer_state"] == "INCORRECT_ABSTENTION"
    # prose collision firewall (D2): prose never reaches classification
    assert classify_response("no comment; the answer follows\nANSWER: yes", polar_case, "yes")["answer_state"] == "CORRECT"


# ---------------------------------------------------------------------------
# Adjudication (frozen G-0 / R / M / I rules applied mechanically)
# ---------------------------------------------------------------------------

def _adjudicate_with(tmp_path, scenario):
    import rvr_adjudicate as adj
    package, sidecar, binding, *_ = write_mini_package(tmp_path, mvs_count=16)
    gt = {cid: e["answer"] for cid, e in sidecar["gt"].items()}
    base_gt_by_set = {}
    wrong_by_case, lure_by_case = {}, {}
    for case in package["cases"]:
        if case["variant"] == "V-BASE":
            base_gt_by_set[case["set_id"]] = gt[case["case_id"]]
    for case in package["cases"]:
        wrong_by_case[case["case_id"]] = case["answer_grammar"]["tokens"][-1]
        lure_by_case[case["case_id"]] = case.get("lure", {}).get("lure_answer")
    replies = {}
    for case in package["cases"]:
        state = scenario(case)
        effective_gt = base_gt_by_set[case["set_id"]] if state == "OVERRIDE" else gt[case["case_id"]]
        replies[case["case_id"]] = reply_for(
            state, effective_gt, wrong_token=wrong_by_case[case["case_id"]],
            lure_answer=lure_by_case[case["case_id"]])
    adapter = OfflineScriptedAdapter(replies)
    run_engine(package, binding, sidecar, adapter, tmp_path)
    return adj.adjudicate(package, tmp_path), package


def test_adjudicator_yields_pattern_r_when_all_track(tmp_path):
    report, _ = _adjudicate_with(tmp_path, lambda case: "CORRECT")
    d = report["decision"]
    assert d["gate_G0"]["passed"] is True
    assert d["final_pattern"] == "R"
    assert report["endpoints"]["primary_CFTR"]["rate"] == 1.0
    assert report["endpoints"]["secondary"]["BCR"]["rate"] == 1.0
    assert report["endpoints"]["secondary"]["LCR"]["rate"] == 0.0
    assert "NOT evidence that the model reasons" in d["interpretation"]  # claim-boundary language present


def test_adjudicator_yields_pattern_m_on_association_override(tmp_path):
    def scenario(case):
        if case["variant"] == "V-FLIP":
            return "OVERRIDE"  # repeats the base-associated answer on the flip
        return "CORRECT"
    report, _ = _adjudicate_with(tmp_path, scenario)
    d = report["decision"]
    assert d["gate_G0"]["passed"] is True
    assert d["final_pattern"] == "M"
    assert report["endpoints"]["primary_CFTR"]["rate"] == 0.0
    # M1: BCR >= 0.60 AND CFTR <= 0.40 — association override signature


def test_adjudicator_yields_indeterminate_on_mixed_profile(tmp_path):
    # exactly half the flips track, half fail to flip: CFTR = 8/16 = 0.5,
    # strictly between the M1 (<= 0.40) and R1 (>= 0.70) thresholds, with
    # no other registered signature -> INDETERMINATE (the valid middle).
    def scenario(case):
        v = case["variant"]
        if v == "V-BASE":
            return "CORRECT"
        if v == "V-FLIP":
            set_no = int(case["set_id"].rsplit("-", 1)[-1])
            return "CORRECT" if set_no > 8 else "INCORRECT"
        return "CORRECT"
    report, _ = _adjudicate_with(tmp_path, scenario)
    d = report["decision"]
    assert d["final_pattern"] == "I"
    # CFTR strictly between 0.40 and 0.70 with no other signature
    assert 0.40 < report["endpoints"]["primary_CFTR"]["rate"] < 0.70


def test_adjudicator_gate_fails_when_evaluable_n_too_small(tmp_path):
    import rvr_adjudicate as adj
    package, sidecar, binding, *_ = write_mini_package(tmp_path, mvs_count=2)
    gt = {cid: e["answer"] for cid, e in sidecar["gt"].items()}
    replies = {c["case_id"]: reply_for("CORRECT", gt[c["case_id"]])
               for c in package["cases"]}
    adapter = OfflineScriptedAdapter(replies)
    run_engine(package, binding, sidecar, adapter, tmp_path)
    report = adj.adjudicate(package, tmp_path)
    assert report["decision"]["gate_G0"]["passed"] is False
    assert report["decision"]["final_pattern"] == "I"


def test_cp_interval_extremes():
    import rvr_adjudicate as adj
    lo, hi = adj.cp_interval(0, 10)
    assert lo == 0.0 and hi < 0.31
    lo, hi = adj.cp_interval(10, 10)
    assert lo > 0.69 and hi == 1.0
    lo, hi = adj.cp_interval(5, 10)
    assert 0.0 <= lo < 0.5 < hi <= 1.0
