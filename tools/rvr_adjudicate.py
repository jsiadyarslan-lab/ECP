#!/usr/bin/env python3
"""RVR post-campaign mechanical adjudication — the frozen §G decision rules
applied mechanically to the sealed execution outputs of campaign
ECP-EVAL-RVR-1.

Runs ONLY after a completed campaign (it reads the campaign ledger and the
per-execution evidence under the evidence root; it never calls a provider,
never reads the private GT sidecar, and never re-classifies anything —
classifications are already frozen in evidence). Every threshold and every
decision rule is read from the FROZEN REGISTRATION PACKAGE
(registration/RVR-REGISTRATION-V1.json, owner_freeze.thresholds +
decision_rules); nothing is configurable from the command line except paths.

Endpoints computed (exact registered numerator/denominator rules):

* BCR  — V-BASE CORRECT / V-BASE attempted & VALID (context gate)
* CFTR — evaluable MVS with V-FLIP CORRECT / registered MVS with V-BASE
         CORRECT, both executions VALID, V-FLIP classifiable (PRIMARY;
         abstentions, malformed and non-answers counted in the denominator)
* RIR  — V-BASE-CORRECT sets with V-RPT CORRECT / V-BASE-CORRECT sets, both
         executions VALID
* LRR  — V-LURE CORRECT / V-LURE evaluable (V-BASE CORRECT, both VALID)
* LCR  — V-LURE declared token == registered lure answer / LRR denominator
* EFR  — (MALFORMED_ANSWER + NON_ANSWER) / attempted & VALID
* IVR  — (INVALID_EXECUTION + UNOBSERVABLE) / attempted
* STP  — distribution of four-variant outcome vectors over MVS
* ECCE-RVR — complete-bundle + unambiguous mechanical classification / attempted
* CIT  — CITED-line presence and full-registered-premise-set citation among
         responses carrying a CITED line (provenance aid; never scoring)

CIT frozen rule: the correct premise set is the case's FULL registered
premise set {1..N} (the premises are the only inferential material; the
V-LURE note is non-inferential by construction). Cited == full set counts
as correct; anything else does not.

Exact Clopper-Pearson 95% intervals are attached to every bounded rate as
DESCRIPTIVE PRECISION AIDS ONLY (descriptive statistics mode; no NHST, no
p-values, no inferential population claims).

Claim boundary (H-RVR-1, frozen): a Pattern R outcome states ONLY that the
observed behavioral pattern is more consistent with reasoning-type structure
tracking than with the registered retrieval/memorization/surface alternatives
under these controls. It is never evidence that the model reasons, never
proof that reasoning occurred, and never proof that memorization is absent.

Usage:
    python tools/rvr_adjudicate.py --evidence-root DIR [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ecp.canonical import load_json  # noqa: E402
from ecp.hashing import hash_document  # noqa: E402

CLASSIFIABLE = ("CORRECT", "INCORRECT", "CORRECT_ABSTENTION", "INCORRECT_ABSTENTION",
                "MALFORMED_ANSWER", "NON_ANSWER")
INVALID_STATES = ("INVALID_EXECUTION", "UNOBSERVABLE")
VARIANTS = ("V-BASE", "V-RPT", "V-FLIP", "V-LURE")

#: Numeric constants used by the R/M pattern rules. The frozen package
#: carries M1/M3/R3 as rule STRINGS (owner_freeze.thresholds); this tuple is
#: verified against those strings at adjudication start (fail-closed) so the
#: literals below are provably the frozen values, never a re-selection.
_RULE_STRING_EXPECTATIONS = (
    ("M1_rule", "CFTR <= 0.40"),
    ("M3_rule", "RIR <= 0.50"),
    ("R3_rule", "LCR <= 0.25"),
    ("R3_rule", "BCR - 0.15"),
    ("R4_EFR_max", 0.15),
    ("R1_CFTR_min", 0.7),
    ("R2_RIR_min", 0.7),
    ("M2_LCR_min", 0.5),
    ("G0_BCR_min", 0.6),
)


# ---------------------------------------------------------------------------
# Exact Clopper-Pearson 95% interval (pure Python; descriptive precision aid)
# ---------------------------------------------------------------------------

def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b) via the continued fraction."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = _log_beta(a, b)
    front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - lbeta)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(b * math.log(1.0 - x) + a * math.log(x) - lbeta) * _betacf(b, a, 1.0 - x) / b


def _betacf(a: float, b: float, x: float) -> float:
    MAXIT, EPS, FPMIN = 200, 3e-12, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d, h = 1.0 / d, 1.0 / d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def _beta_ppf(p: float, a: float, b: float) -> float:
    """Inverse of I_x(a, b) by bisection (deterministic)."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def cp_interval(k: int, n: int) -> "tuple[float, float] | None":
    """Exact Clopper-Pearson 95% interval for k successes in n trials."""
    if n <= 0:
        return None
    alpha = 0.05
    lower = 0.0 if k == 0 else _beta_ppf(alpha / 2.0, k, n - k + 1)
    upper = 1.0 if k == n else _beta_ppf(1.0 - alpha / 2.0, k + 1, n - k)
    return round(lower, 4), round(upper, 4)


def rate(k: int, n: int) -> "float | None":
    return None if n == 0 else round(k / n, 4)


# ---------------------------------------------------------------------------
# Adjudication
# ---------------------------------------------------------------------------

def _rate_block(k: int, n: int, label: str) -> dict:
    return {"label": label, "numerator": k, "denominator": n,
            "rate": rate(k, n), "cp95_precision_aid": cp_interval(k, n)}


def _verify_frozen_rule_strings(thresholds: dict) -> None:
    """Fail-closed coupling of the code's pattern literals to the frozen rules."""
    for key, expected in _RULE_STRING_EXPECTATIONS:
        value = thresholds.get(key)
        if isinstance(expected, str):
            if not isinstance(value, str) or expected not in value:
                raise SystemExit(f"FATAL: frozen rule string mismatch for {key!r} — expected {expected!r} inside {value!r}")
        elif value != expected:
            raise SystemExit(f"FATAL: frozen threshold mismatch for {key!r}: {value!r} != {expected!r}")


def adjudicate(package: dict, evidence_root: Path) -> dict:
    thresholds = package["owner_freeze"]["thresholds"]
    _verify_frozen_rule_strings(thresholds)
    ledger_path = evidence_root / "rvr-campaign-ledger.json"
    campaign = load_json(ledger_path)
    ledger = campaign["ledger"]
    attempted = len(ledger)

    # ---- integrity: every ledger entry must have a matching, hash-equal
    # evidence file on disk (ECCE-RVR's complete-bundle term).
    complete, hash_mismatch, missing_files = 0, [], []
    by_case: dict[str, dict] = {}
    for entry in ledger:
        by_case[entry["case_id"]] = entry
        p = evidence_root / "executions" / f"{entry['execution_id']}-evidence.json"
        if not p.is_file():
            missing_files.append(entry["execution_id"])
            continue
        ev = load_json(p)
        recomputed = hash_document({k: v for k, v in ev.items() if k != "evidence_hash"})
        if recomputed != ev.get("evidence_hash") or ev.get("evidence_hash") != entry["evidence_hash"]:
            hash_mismatch.append(entry["execution_id"])
            continue
        if ev.get("case_id") != entry["case_id"] or ev.get("answer_state") != entry["answer_state"]:
            hash_mismatch.append(entry["execution_id"])
            continue
        complete += 1

    # ---- per-case view: answer_state, declared_token, execution validity
    states = {e["case_id"]: e["answer_state"] for e in ledger}
    tokens = {e["case_id"]: e.get("declared_token") for e in ledger}
    valid = {e["case_id"]: e["execution_status"] == "VALID" for e in ledger}

    package_cases = {c["case_id"]: c for c in package["cases"]}
    mvs_list = package["mvs"]
    attempted_valid = sum(1 for e in ledger if e["execution_status"] == "VALID")

    # ---- BCR (V-BASE context)
    base_cases = [c for c in package["cases"] if c["variant"] == "V-BASE"]
    base_valid = [c for c in base_cases if valid.get(c["case_id"])]
    bcr_k = sum(1 for c in base_valid if states.get(c["case_id"]) == "CORRECT")
    bcr = rate(bcr_k, len(base_valid))

    # ---- set-level endpoints (CFTR primary + RIR/LRR/LCR)
    cftr_n = cftr_k = 0
    rir_n = rir_k = 0
    lrr_n = lrr_k = 0
    lcr_k = 0
    stp: dict[str, int] = {}
    per_family: dict[str, dict] = {}
    for mvs in mvs_list:
        fam = mvs["family"]
        vmap = mvs["variants"]
        base_id, rpt_id = vmap["V-BASE"], vmap["V-RPT"]
        flip_id, lure_id = vmap["V-FLIP"], vmap["V-LURE"]
        base_ok = states.get(base_id) == "CORRECT"
        # STP vector over the four variants
        vec = "|".join(states.get(vmap[v], "ABSENT") for v in VARIANTS)
        stp[vec] = stp.get(vec, 0) + 1

        famstats = per_family.setdefault(fam, {
            "family": fam, "family_name": mvs.get("family_name", fam),
            "sets": 0, "base_correct": 0, "cftr_n": 0, "cftr_k": 0,
            "rir_n": 0, "rir_k": 0, "lrr_n": 0, "lrr_k": 0, "lcr_k": 0,
        })
        famstats["sets"] += 1
        if base_ok:
            famstats["base_correct"] += 1
            # CFTR denominator: V-BASE CORRECT, both VALID, V-FLIP classifiable
            if valid.get(base_id) and valid.get(flip_id) and states.get(flip_id) in CLASSIFIABLE:
                cftr_n += 1
                famstats["cftr_n"] += 1
                if states.get(flip_id) == "CORRECT":
                    cftr_k += 1
                    famstats["cftr_k"] += 1
            # RIR denominator: V-BASE CORRECT, both VALID
            if valid.get(base_id) and valid.get(rpt_id):
                rir_n += 1
                famstats["rir_n"] += 1
                if states.get(rpt_id) == "CORRECT":
                    rir_k += 1
                    famstats["rir_k"] += 1
            # LRR / LCR denominator: V-BASE CORRECT, both VALID
            if valid.get(base_id) and valid.get(lure_id):
                lrr_n += 1
                famstats["lrr_n"] += 1
                if states.get(lure_id) == "CORRECT":
                    lrr_k += 1
                    famstats["lrr_k"] += 1
                lure_answer = (package_cases.get(lure_id) or {}).get("lure", {}).get("lure_answer")
                if lure_answer is not None and tokens.get(lure_id) == lure_answer:
                    lcr_k += 1
                    famstats["lcr_k"] += 1

    cftr = rate(cftr_k, cftr_n)
    rir = rate(rir_k, rir_n)
    lrr = rate(lrr_k, lrr_n)
    lcr = rate(lcr_k, lrr_n)

    # ---- EFR / IVR / ECCE-RVR (EFR also decomposed per family for the
    # family-level pattern rows)
    efr_k = sum(1 for e in ledger if e["answer_state"] in ("MALFORMED_ANSWER", "NON_ANSWER"))
    ivr_k = sum(1 for e in ledger if e["answer_state"] in INVALID_STATES)
    efr = rate(efr_k, attempted_valid)
    ivr = rate(ivr_k, attempted)
    ecce = rate(complete, attempted)
    family_efr: dict[str, dict] = {}
    for e in ledger:
        f = family_efr.setdefault(e["family"], {"valid": 0, "efr_k": 0})
        if e["execution_status"] == "VALID":
            f["valid"] += 1
            if e["answer_state"] in ("MALFORMED_ANSWER", "NON_ANSWER"):
                f["efr_k"] += 1

    # ---- CIT (provenance aid; never scoring). Frozen rule: correct = the
    # cited set equals the case's FULL registered premise set.
    cit_with_line = 0
    cit_correct = 0
    for entry in ledger:
        p = evidence_root / "executions" / f"{entry['execution_id']}-evidence.json"
        if not p.is_file():
            continue
        ev = load_json(p)
        citation = ev.get("premise_citation") or {}
        if not citation.get("cited"):
            continue
        cit_with_line += 1
        case = package_cases.get(entry["case_id"]) or {}
        full_set = set(range(1, len(case.get("premises") or []) + 1))
        if set(citation.get("premise_numbers") or []) == full_set:
            cit_correct += 1
    cit_presence = rate(cit_with_line, attempted_valid)
    cit_accuracy = rate(cit_correct, cit_with_line)

    # ---- G-0 gate (study level)
    g0_bcr = bcr is not None and bcr >= thresholds["G0_BCR_min"]
    g0_n = cftr_n >= thresholds["G0_evaluable_CFTR_denominator_min"]
    g0_artifact = (ivr is not None and efr is not None
                   and (ivr + (efr or 0.0)) <= thresholds["G0_IVR_plus_EFR_max"])
    g0_pass = g0_bcr and g0_n and g0_artifact

    # ---- Pattern determination (study level, pooled)
    def pattern_of(b, c, r, lcr_v, lrr_v, e) -> "str | None":
        """Apply the frozen R/M rules; None when rates are unobservable."""
        if b is None or c is None or r is None or e is None:
            return None
        m_hit = ((b >= thresholds["G0_BCR_min"] and c <= 0.40)
                 or (lcr_v is not None and lcr_v >= thresholds["M2_LCR_min"])
                 or (b >= thresholds["G0_BCR_min"] and r <= 0.50))
        if m_hit:
            return "M"
        r3 = (lcr_v is not None and lcr_v <= 0.25) or (lrr_v is not None and b - lrr_v <= 0.15)
        if (c >= thresholds["R1_CFTR_min"] and r >= thresholds["R2_RIR_min"]
                and r3 and e <= thresholds["R4_EFR_max"]):
            return "R"
        return "I"

    pooled_pattern = pattern_of(bcr, cftr, rir, lcr, lrr, efr) if g0_pass else "I"

    # ---- family-level patterns (dominance rule inputs)
    family_rows = []
    for fam in sorted(per_family):
        s = per_family[fam]
        f_bcr = rate(s["base_correct"], s["sets"])
        f_cftr = rate(s["cftr_k"], s["cftr_n"])
        f_rir = rate(s["rir_k"], s["rir_n"])
        f_lrr = rate(s["lrr_k"], s["lrr_n"])
        f_lcr = rate(s["lcr_k"], s["lrr_n"])
        fe = family_efr.get(fam) or {"valid": 0, "efr_k": 0}
        f_efr = rate(fe["efr_k"], fe["valid"])
        fam_pattern = pattern_of(f_bcr, f_cftr, f_rir, f_lcr, f_lrr, f_efr)
        family_rows.append({
            "family": fam, "family_name": s["family_name"],
            "sets": s["sets"], "base_correct": s["base_correct"],
            "BCR": f_bcr, "CFTR": f_cftr, "CFTR_denominator": s["cftr_n"],
            "RIR": f_rir, "LRR": f_lrr, "LCR": f_lcr, "EFR": f_efr,
            "family_pattern": fam_pattern if fam_pattern is not None else "NOT-DETERMINABLE",
            "note": "small-cell descriptive counts only (design B.7); no inferential claim",
        })

    if pooled_pattern in ("R", "M"):
        contradicting = [f["family"] for f in family_rows
                         if f["family_pattern"] not in ("NOT-DETERMINABLE", pooled_pattern, "I")]
        if len(contradicting) >= 2:
            final_pattern = "I"
            dominance_note = (f"pooled {pooled_pattern} overturned: {len(contradicting)} families "
                              f"meet different patterns ({', '.join(contradicting)})")
        else:
            final_pattern = pooled_pattern
            dominance_note = (f"pooled {pooled_pattern} upheld; contradicting families: "
                              f"{contradicting if contradicting else 'none'} (dominance rule: "
                              "pooled pattern matches and at most one family contradicts)")
    else:
        final_pattern = "I"
        dominance_note = "pooled pattern is INDETERMINATE (or G-0 failed); dominance rule not applicable"

    # ---- claim-boundary language (H-RVR-1 frozen wording)
    interpretation = {
        "R": ("Pattern R: the observed behavioral pattern is more consistent with "
              "reasoning-type structure tracking than with the registered "
              "retrieval/memorization/surface-matching alternatives, under the "
              "registered controls. This is a Claim-C statement ONLY. It is NOT "
              "evidence that the model reasons, NOT proof that reasoning occurred, "
              "and NOT proof that memorization or retrieval is absent."),
        "M": ("Pattern M: performance on these cases is surface/association-driven "
              "under the registered controls; the conclusion is bounded to the "
              "registered lure/flip/surface classes and is NOT a universal "
              "retrieval diagnosis."),
        "I": ("INDETERMINATE: the evidence does not distinguish the registered "
              "explanation classes at the registered thresholds. This is a valid "
              "scientific outcome and MUST NOT be converted into evidence for "
              "either explanation class."),
    }[final_pattern]

    report = {
        "ecp_object": "rvr-post-campaign-adjudication",
        "adjudicator": "RVR-ADJUDICATE-1 (frozen §G decision rules, mechanical application)",
        "campaign_id": package["campaign_id"],
        "package_id": package["package_id"],
        "package_hash": package["integrity"]["package_hash"],
        "binding_reference": campaign["summary"].get("binding_id"),
        "model_identifier": campaign["summary"].get("model_identifier"),
        "evidence_root": str(evidence_root),
        "ledger_completed_at": campaign["summary"].get("completed_at"),
        "integrity": {
            "ledger_entries": attempted,
            "complete_bundles": complete,
            "missing_evidence_files": missing_files,
            "evidence_hash_mismatches": hash_mismatch,
        },
        "endpoints": {
            "primary_CFTR": _rate_block(cftr_k, cftr_n, "Counterfactual Flip-Tracking Rate (pooled)"),
            "secondary": {
                "BCR": _rate_block(bcr_k, len(base_valid), "Base Correctness Rate (context)"),
                "RIR": _rate_block(rir_k, rir_n, "RPT Invariance Rate"),
                "LRR": _rate_block(lrr_k, lrr_n, "Lure Resistance Rate"),
                "LCR": _rate_block(lcr_k, lrr_n, "Lure Capture Rate"),
                "EFR": _rate_block(efr_k, attempted_valid, "Envelope-Failure Rate"),
                "IVR": _rate_block(ivr_k, attempted, "Invalid/Unobservable Rate"),
                "ECCE_RVR": _rate_block(complete, attempted, "Evidence-Complete Classified Execution rate"),
                "CIT_presence": _rate_block(cit_with_line, attempted_valid, "CITED-line presence (provenance aid)"),
                "CIT_full_set_accuracy": _rate_block(cit_correct, cit_with_line,
                                                     "CITED == full registered premise set (frozen CIT rule)"),
            },
            "promotion_rule": package["endpoints"]["promotion_rule"],
        },
        "structure_tracking_profile": {
            "vectors": dict(sorted(stp.items(), key=lambda kv: (-kv[1], kv[0]))),
            "note": "four-variant outcome vectors (V-BASE|V-RPT|V-FLIP|V-LURE) over the 24 registered MVS",
        },
        "family_table": family_rows,
        "decision": {
            "gate_G0": {
                "BCR_ge_0.60": g0_bcr, "evaluable_CFTR_denominator_ge_15": g0_n,
                "IVR_plus_EFR_le_0.25": g0_artifact, "passed": g0_pass,
                "evaluable_CFTR_denominator": cftr_n,
            },
            "pooled_pattern": pooled_pattern if pooled_pattern is not None else "NOT-DETERMINABLE",
            "final_pattern": final_pattern,
            "dominance_rule": dominance_note,
            "interpretation": interpretation,
            "firewalls": package["decision_rules"]["firewalls"],
        },
        "statistics_mode": ("DESCRIPTIVE ONLY — no null-hypothesis testing, no p-values, "
                            "no inferential population claims; Clopper-Pearson 95% intervals "
                            "are descriptive precision aids only"),
        "thresholds_source": "frozen registration package owner_freeze.thresholds (verbatim; never re-selected)",
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="RVR post-campaign mechanical adjudication (frozen §G rules)")
    ap.add_argument("--evidence-root", required=True, help="campaign evidence root (contains rvr-campaign-ledger.json)")
    ap.add_argument("--package", default=str(REPO / "registration" / "RVR-REGISTRATION-V1.json"),
                    help="frozen registration package (thresholds + decision rules source)")
    ap.add_argument("--out", default=None, help="output report path (default: <evidence-root>/rvr-adjudication.json)")
    args = ap.parse_args()

    evidence_root = Path(args.evidence_root)
    ledger_path = evidence_root / "rvr-campaign-ledger.json"
    if not ledger_path.is_file():
        print(f"FATAL: no campaign ledger at {ledger_path} — adjudication runs only after a completed campaign.")
        return 1
    package = load_json(Path(args.package))
    claimed = package.get("integrity", {}).get("package_hash")
    recomputed = hash_document({k: v for k, v in package.items() if k != "integrity"} | {
        "integrity": {k: v for k, v in package.get("integrity", {}).items() if k != "package_hash"}
    })
    if claimed != recomputed:
        print("FATAL: registration package hash mismatch — the frozen package is not intact.")
        return 1

    report = adjudicate(package, evidence_root)
    out_path = Path(args.out) if args.out else evidence_root / "rvr-adjudication.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    d = report["decision"]
    print("=== RVR POST-CAMPAIGN ADJUDICATION (mechanical, frozen §G rules) ===")
    print(f"pattern     : {d['final_pattern']}  (pooled: {d['pooled_pattern']}; G-0 passed: {d['gate_G0']['passed']})")
    print(f"CFTR        : {report['endpoints']['primary_CFTR']['rate']} "
          f"({report['endpoints']['primary_CFTR']['numerator']}/{report['endpoints']['primary_CFTR']['denominator']})")
    sec = report["endpoints"]["secondary"]
    print(f"BCR/RIR/LRR/LCR: {sec['BCR']['rate']} / {sec['RIR']['rate']} / {sec['LRR']['rate']} / {sec['LCR']['rate']}")
    print(f"EFR/IVR/ECCE: {sec['EFR']['rate']} / {sec['IVR']['rate']} / {sec['ECCE_RVR']['rate']}")
    print(f"interpretation:\n  {d['interpretation']}")
    print(f"report      : {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
