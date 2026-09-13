"""RVR case generator — deterministic authoring for campaign ECP-EVAL-RVR-1.

Registered authoring instrument under the order
*ECP — REASONING vs RETRIEVAL PREREGISTRATION FREEZE v1* (2026-09-13).

Determinism: every selection derives from
SHA-256("ECP-EVAL-RVR-1::SEED-V1::<decision key>") — no runtime PRNG.

Grid: 4 families x 3 depth strata x 2 MVS per cell = 24 matched variant
sets; each set = {V-BASE, V-RPT, V-FLIP, V-LURE} => 96 cases / 96 one-shot
executions (owner freeze §3).

V-FLIP mechanism: a deterministic REGISTERED SEARCH over single-premise
edits accepts the first edit (in registered enumeration order) that
provably changes the world's ground truth while keeping the world
well-formed. The validator independently re-derives every GT from the
rendered premise text with its own solver.

Ground truth is emitted ONLY to the private sidecar (owner-held, never
committed); the public package carries gt_commitment hashes.

Usage:
    python3 tools/rvr_case_generator.py \
        --exclude-file <m3-exclusion-tokens.json> --out-dir <build>
Outputs: rvr-package-core.json / rvr-private-gt-sidecar.json /
         rvr-build-log.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from ecp.canonical import canonical_dumps  # noqa: E402

sys.path.insert(0, str(_REPO_ROOT / "tools"))
from rvr_worlds import (  # noqa: E402
    build_f1, build_f2, build_f3, build_f4, f2_value,
)

SEED = "ECP-EVAL-RVR-1::SEED-V1"
ENVELOPE_ID = "RVR-ENVELOPE-1"
ENVELOPE_TAIL = (
    "Think as needed, then give your final answer as the LAST line of your "
    "reply, in exactly this format:\n"
    "ANSWER: <token>\n"
    "where <token> is one of: {tokens}\n"
    "You may optionally add one line 'CITED: <premise numbers>' immediately "
    "before the final line; it is optional and never affects scoring."
)

# registered relation vocabulary (comparative, superlative, antonym
# comparative, antonym superlative, most-question paraphrase)
RELATIONS = [
    ("heavier", "heaviest", "lighter", "lightest", "which one weighs the most"),
    ("faster", "fastest", "slower", "slowest", "which one moves the fastest"),
    ("older", "oldest", "younger", "youngest", "which one has the greatest age"),
    ("taller", "tallest", "shorter", "shortest", "which one stands the tallest"),
]

F4_ATTRIBUTE_CHAINS = [
    ("magnetic", "gleaming", "humming"),
    ("buoyant", "drifting", "whistling"),
    ("translucent", "shimmering", "resonating"),
]

NOUNS = ["tank", "container", "vessel"]

# ------------------------------------------------------------------ hashes

def _h(*parts: str) -> bytes:
    return hashlib.sha256(("::".join(parts)).encode("utf-8")).digest()


def _hi(*parts: str, lo: int, hi: int) -> int:
    return lo + (int.from_bytes(_h(*parts), "big") % (hi - lo + 1))


def _doc_sha256(doc) -> str:
    return hashlib.sha256(canonical_dumps(doc).encode("utf-8")).hexdigest()


def _gt_commitment(case_id: str, gt: str) -> str:
    return _doc_sha256({"case_id": case_id, "ground_truth": gt})


# ------------------------------------------------------------------ names

ONSETS = ["b", "br", "c", "cr", "d", "dr", "f", "g", "gr", "j", "k", "kl",
          "l", "m", "n", "p", "pr", "r", "s", "st", "t", "tr", "v", "z", "th", "sh"]
NUCLEI = ["a", "e", "i", "o", "u", "ai", "au", "ea", "ee", "ou"]
CODAS = ["", "n", "r", "l", "m", "s", "k", "th", "nd", "lt", "rn", "sk"]

CURATED_SCREEN = {
    "answer", "note", "premise", "premises", "question", "units", "unit",
    "tank", "container", "vessel", "tanks", "containers", "vessels", "holds",
    "hold", "capacity", "every", "each", "nothing", "none", "member",
    "family", "belongs", "which", "these", "those", "item", "items",
    "collection", "legend", "yes", "no", "cannot", "cited",
    "heavier", "heaviest", "lighter", "lightest", "faster", "fastest",
    "slower", "slowest", "older", "oldest", "younger", "youngest", "taller",
    "tallest", "shorter", "shortest", "more", "most", "fewer", "fewest",
    "less", "least", "than", "times", "double", "triple", "magnetic",
    "gleaming", "humming", "buoyant", "drifting", "whistling", "translucent",
    "shimmering", "resonating", "proverb", "region", "saying", "famous",
    "prize", "fair", "modest", "record", "season", "observed", "standing",
    "veteran", "collectors", "rank", "nearly", "always", "dispute", "filed",
    "certified", "authentic", "registry", "talked", "alice", "bob", "carol",
    "dave", "eve", "mallory", "trent", "charlie", "olivia", "emma", "liam",
    "noah", "john", "mary", "james", "sarah", "michael", "jennifer", "robert",
    "linda", "william", "elizabeth", "david", "barbara", "richard", "jessica",
    "joseph", "susan", "paris", "london", "berlin", "tokyo", "cairo", "sydney",
    "rome", "madrid", "moon", "sun", "star", "earth", "mars", "venus",
    "jupiter", "zeus", "hera", "apollo", "athena", "odin", "thor", "loki",
    "opal", "ruby", "pearl", "coral", "amber", "jade", "onyx", "quartz", "topaz",
}


def _load_dict_words() -> "set[str]":
    p = Path("/usr/share/dict/words")
    if not p.exists():
        return set()
    out = set()
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            w = line.strip().lower()
            if len(w) >= 4 and w.isalpha():
                out.add(w)
    return out


class NameFactory:
    def __init__(self, exclude_tokens: "set[str]"):
        self.exclude = set(exclude_tokens)
        self.dict_words = _load_dict_words()
        self.used: "set[str]" = set()
        self.attempts = 0

    def _candidate(self, key: str, attempt: int) -> str:
        n_syl = _hi(key, str(attempt), "syl", lo=2, hi=3)
        parts = []
        for i in range(n_syl):
            onset = ONSETS[_hi(key, str(attempt), "on", str(i), lo=0, hi=len(ONSETS) - 1)]
            nucleus = NUCLEI[_hi(key, str(attempt), "nu", str(i), lo=0, hi=len(NUCLEI) - 1)]
            coda = (CODAS[_hi(key, str(attempt), "co", str(i), lo=0, hi=len(CODAS) - 1)]
                    if i == n_syl - 1 else "")
            parts.append(onset + nucleus + coda)
        name = "".join(parts)
        return name if 5 <= len(name) <= 9 and name.isalpha() else ""

    def fresh(self, key: str) -> str:
        for attempt in range(100000):
            self.attempts += 1
            cand = self._candidate(key, attempt)
            if (cand and cand not in self.used
                    and cand not in CURATED_SCREEN and cand not in self.exclude
                    and not (self.dict_words and cand in self.dict_words)):
                self.used.add(cand)
                return cand
        raise RuntimeError(f"name generation exhausted for {key!r}")


# ------------------------------------------------------------------ flips

def _f2_sem_values(sem: dict, entities: list) -> "dict[str,int]":
    stated = dict(sem["stated"])
    mult = {tuple(k.split("|")): v for k, v in sem["mult"].items()}
    delta = {tuple(k.split("|")): tuple(v) for k, v in sem["delta"].items()}
    out = {}
    for x in entities:
        try:
            out[x] = f2_value(x, stated, mult, delta)
        except KeyError:
            continue        # entity carries no quantity in this subform
    return out


def flip_search(set_key: str, family: str, build_base, build_with_edit,
                base_world: dict, cfg: dict) -> "tuple[dict, dict]":
    """Registered deterministic search: first single-premise edit whose
    application changes GT on a well-formed world wins."""
    candidates: "list[dict]" = []
    n_prem = len(base_world["premises"])
    if family == "F1":
        for i in range(n_prem):
            candidates.append({"premise_index": i, "class": "relation_reversal"})
    elif family == "F2":
        sem = base_world["sem"]
        order = ([("stated", x) for x in sem["stated"]] +
                 [("mult", tuple(k.split("|"))) for k in sem["mult"]] +
                 [("delta", tuple(k.split("|"))) for k in sem["delta"]])
        for pi, (kind, payload) in enumerate(order):
            if kind == "stated":
                v = sem["stated"][payload]
                for dv in (1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 8, -8,
                           10, -10, 12, -12, 15, -15, 16, -16):
                    nv = v + dv
                    if 2 <= nv <= 30:
                        candidates.append({"premise_index": pi,
                                           "class": "stated_value_change",
                                           "new_value": nv})
            elif kind == "mult":
                k = sem["mult"]["|".join(payload)]
                for nk in (2, 3, 4):
                    if nk != k:
                        candidates.append({"premise_index": pi,
                                           "class": "multiplier_change",
                                           "new_value": nk})
            else:
                d, s = sem["delta"]["|".join(payload)]
                combos = []
                for nd in (d + 1, d - 1, d + 2, d - 2, d + 3, d - 3, d + 4,
                           d - 4, d + 5, d - 5, d + 6, d - 6, d + 7, d - 8):
                    if 1 <= nd <= 9:
                        combos.append((nd, s))
                        combos.append((nd, "+" if s == "-" else "-"))
                for nd, ns in combos:
                    candidates.append({"premise_index": pi,
                                       "class": "delta_change",
                                       "new_value": [nd, ns]})
    elif family == "F3":
        ents = base_world["entities"]
        pairs = base_world["sem"]["edges"]
        for i, (a, b) in enumerate(pairs):
            candidates.append({"premise_index": i, "class": "relation_reversal"})
            for pos in ("b", "a"):
                for new in ents:
                    if new != (a if pos == "b" else b):
                        candidates.append({"premise_index": i,
                                           "class": "entity_substitution",
                                           "position": pos, "new_entity": new})
    else:  # F4
        candidates.append({"premise_index": n_prem - 1,
                           "class": "instance_family_reassignment"})

    for cand in candidates:
        world = build_with_edit(cand)
        gt_new = world["gt"]
        if gt_new is None or gt_new == base_world["gt"]:
            continue
        if family == "F2":
            vals = _f2_sem_values(world["sem"], base_world["entities"])
            if any(v < 1 for v in vals.values()):
                continue
        if family == "F3" and base_world["sem"]["subform"] == "underdetermined":
            if gt_new == "cannot":
                continue
        return cand, world
    raise RuntimeError(f"flip search failed for {set_key}")


# ------------------------------------------------------------------ lures

def build_lure(set_key: str, family: str, base_world: dict, cfg: dict) -> dict:
    sem = base_world["sem"]
    gt = base_world["gt"]
    if family == "F1":
        ents = base_world["entities"]
        mid = ents[len(ents) // 2]
        assert mid != gt
        note = f"(Note: the {mid} is the most talked-about item in the collection.)"
        return {"class": "LC-1", "template_id": "L-F1-ENUM-1", "lure_answer": mid,
                "note": note}
    if family == "F2":
        if sem["subform"] == "yes_no":
            noun = sem["noun"]
            if sem["qkind"] == "more":
                A, B = base_world["entities"][0], base_world["entities"][1]
                target = B if gt == "yes" else A
                note = (f"(Note: the {target} {noun} has taken first prize at "
                        f"every fair for years.)")
                return {"class": "LC-2", "template_id": "L-F2YN-PRIZE-1",
                        "lure_answer": "no" if gt == "yes" else "yes", "note": note}
            A = base_world["entities"][0]
            if gt == "yes":
                note = (f"(Note: judges at every fair have praised the {A} "
                        f"{noun} for its modest size.)")
                return {"class": "LC-2", "template_id": "L-F2YN-MODEST-1",
                        "lure_answer": "no", "note": note}
            note = (f"(Note: the {A} {noun} has taken first prize at every "
                    f"fair for years.)")
            return {"class": "LC-2", "template_id": "L-F2YN-PRIZE-1",
                    "lure_answer": "yes", "note": note}
        stated = dict(sem["stated"])
        mult = {tuple(k.split("|")): v for k, v in sem["mult"].items()}
        delta = {tuple(k.split("|")): tuple(v) for k, v in sem["delta"].items()}
        values = {x: f2_value(x, stated, mult, delta)
                  for x in base_world["entities"]}
        lure_e = min(values, key=lambda x: values[x])
        assert lure_e != gt
        noun = sem["noun"]
        K = _hi(set_key, "lureK", lo=40, hi=90)
        note = (f"(Note: the {lure_e} {noun} was observed {K} times last "
                f"season — a standing record.)")
        return {"class": "LC-2", "template_id": "L-F2-ENUM-1",
                "lure_answer": lure_e, "note": note}
    if family == "F3":
        if sem["subform"] == "consistency":
            if gt == "yes":
                note = "(Note: both records are certified authentic by the registry.)"
                return {"class": "LC-3", "template_id": "L-F3A-AUTHENTIC-1",
                        "lure_answer": "no", "note": note}
            note = "(Note: these records were filed in a long-standing dispute.)"
            return {"class": "LC-3", "template_id": "L-F3A-DISPUTE-1",
                    "lure_answer": "yes", "note": note}
        X, Z = sem["x"], sem["z"]
        note = (f"(Note: veteran collectors nearly always rank the {X} "
                f"above the {Z}.)")
        return {"class": "LC-3", "template_id": "L-F3B-RANK-1",
                "lure_answer": "yes", "note": note}
    # F4
    neg_fam, asked = sem["neg_fam"], sem["chain"][-1]
    note = (f"(Note: the saying 'no {neg_fam} is ever {asked}' is the "
            f"best-known proverb of the region.)")
    return {"class": "LC-1", "template_id": "L-F4-PROVERB-1",
            "lure_answer": "no", "note": note}


# ------------------------------------------------------------------ prompts

def render_prompt(case: dict) -> str:
    lines = ["Premises:"]
    lines += [f"{i + 1}. {p}" for i, p in enumerate(case["premises"])]
    if case.get("lure_note"):
        lines += ["", case["lure_note"]]
    lines += ["", f"Question: {case['question']}", ""]
    tail = ENVELOPE_TAIL.format(tokens=" | ".join(case["answer_grammar"]["tokens"]))
    lines += tail.split("\n")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ assembly

FAMILY_NAMES = {"F1": "transitive-compositional-relational",
                "F2": "quantitative-comparison",
                "F3": "consistency-contradiction",
                "F4": "multi-premise-evidence-integration"}


def _f3_subform(depth: int, cell_idx: int) -> str:
    if depth == 2:
        return "consistency"
    return "consistency" if cell_idx == 0 else "underdetermined"


def assemble(out_dir: Path, exclude_tokens: "set[str]") -> dict:
    nf = NameFactory(exclude_tokens)
    cases: "list[dict]" = []
    mvs_list: "list[dict]" = []
    gt_map: "dict[str,str]" = {}
    flip_gt_map: "dict[str,dict]" = {}
    build_log: "list[dict]" = []
    set_seq = 0
    case_seq = 0
    name_counts = {"F1": 5, "F2": 3, "F3": 6, "F4": 1}

    for family in ("F1", "F2", "F3", "F4"):
        for depth in (1, 2, 3):
            for cell_idx in (0, 1):
                set_seq += 1
                set_id = f"ECP-MVS-RVR-{set_seq:03d}"
                set_key = f"{SEED}::MVS::{set_seq:03d}"
                rel_idx = _hi(set_key, "rel", lo=0, hi=3)
                rel = RELATIONS[rel_idx]
                noun = NOUNS[_hi(set_key, "noun", lo=0, hi=len(NOUNS) - 1)]
                attrs = F4_ATTRIBUTE_CHAINS[_hi(set_key, "attrs", lo=0, hi=2)]

                base_names = [nf.fresh(f"{set_key}::base::{i}")
                              for i in range(name_counts[family])]
                rpt_names = [nf.fresh(f"{set_key}::rpt::{i}")
                             for i in range(name_counts[family])]
                if family == "F4":
                    fam_base = (nf.fresh(f"{set_key}::fam::0"),
                                nf.fresh(f"{set_key}::fam::1"))
                    fam_rpt = (nf.fresh(f"{set_key}::famr::0"),
                               nf.fresh(f"{set_key}::famr::1"))
                subform = None
                if family == "F1":
                    extreme = "most" if cell_idx == 0 else "least"
                    cfg = {"rel": rel, "extreme": extreme}
                    build_base = lambda: build_f1(set_key, base_names, rel, depth,
                                                  extreme, paraphrase=False)
                    build_edit = lambda e: build_f1(set_key, base_names, rel, depth,
                                                    extreme, paraphrase=False, edit=e)
                    build_rpt = lambda: build_f1(set_key, rpt_names, rel, depth,
                                                 extreme, paraphrase=True)
                elif family == "F2":
                    subform = "yes_no" if cell_idx == 0 else "enum"
                    cfg = {"noun": noun, "subform": subform}
                    build_base = lambda: build_f2(set_key, base_names, noun, depth,
                                                   subform, paraphrase=False)
                    build_edit = lambda e: build_f2(set_key, base_names, noun, depth,
                                                    subform, paraphrase=False, edit=e)
                    build_rpt = lambda: build_f2(set_key, rpt_names, noun, depth,
                                                 subform, paraphrase=True)
                elif family == "F3":
                    subform = _f3_subform(depth, cell_idx)
                    cfg = {"rel": rel, "subform": subform}
                    build_base = lambda: build_f3(set_key, base_names, rel, depth,
                                                   subform, paraphrase=False)
                    build_edit = lambda e: build_f3(set_key, base_names, rel, depth,
                                                    subform, paraphrase=False, edit=e)
                    build_rpt = lambda: build_f3(set_key, rpt_names, rel, depth,
                                                 subform, paraphrase=True)
                else:
                    cfg = {"attrs": attrs}
                    build_base = lambda: build_f4(set_key, base_names, fam_base,
                                                  attrs, depth, paraphrase=False)
                    build_edit = lambda e: build_f4(set_key, base_names, fam_base,
                                                    attrs, depth, paraphrase=False,
                                                    edit=e)
                    build_rpt = lambda: build_f4(set_key, rpt_names, fam_rpt,
                                                 attrs, depth, paraphrase=True)

                base_world = build_base()
                assert base_world["gt"] is not None, f"{set_id}: ill-formed base"
                edit, flip_world = flip_search(set_key, family, build_base,
                                               build_edit, base_world, cfg)
                rpt_world = build_rpt()
                n_prem = len(rpt_world["premises"])
                order = list(range(n_prem))
                for i in range(n_prem - 1, 0, -1):
                    j = _hi(set_key, "perm", str(i), lo=0, hi=i)
                    order[i], order[j] = order[j], order[i]
                rpt_premises = [rpt_world["premises"][k] for k in order]
                rpt_question = rpt_world["question"]
                lure = build_lure(set_key, family, base_world, cfg)

                rename_map = {b: r for b, r in
                              zip(base_world["entities"], rpt_world["entities"])}
                if family == "F4":
                    rename_map.update({fam_base[0]: fam_rpt[0],
                                       fam_base[1]: fam_rpt[1]})
                flip_old = base_world["premises"][edit["premise_index"]]
                flip_new = flip_world["premises"][edit["premise_index"]]

                variant_worlds = {
                    "V-BASE": (base_world["premises"], base_world["question"],
                               base_world["gt"], base_world["grammar"], None),
                    "V-RPT": (rpt_premises, rpt_question, rpt_world["gt"],
                              rpt_world["grammar"],
                              {"rename_map": rename_map,
                               "paraphrase": True,
                               "premise_order": order}),
                    "V-FLIP": (flip_world["premises"], flip_world["question"],
                               flip_world["gt"], flip_world["grammar"],
                               {"premise_index": edit["premise_index"],
                                "class": edit["class"],
                                "old": flip_old, "new": flip_new}),
                    "V-LURE": (base_world["premises"], base_world["question"],
                               base_world["gt"], base_world["grammar"], None),
                }
                set_case_ids = {}
                for variant in ("V-BASE", "V-RPT", "V-FLIP", "V-LURE"):
                    case_seq += 1
                    case_id = f"ECP-CASE-RVR-{case_seq:03d}"
                    premises, question, gt, grammar, extra = variant_worlds[variant]
                    rec = {
                        "case_id": case_id, "set_id": set_id, "variant": variant,
                        "family": family, "family_name": FAMILY_NAMES[family],
                        "depth": depth, "premises": premises, "question": question,
                        "answer_grammar": grammar,
                    }
                    if variant == "V-RPT":
                        rec["transform"] = extra
                    elif variant == "V-FLIP":
                        rec["flip"] = extra
                    elif variant == "V-LURE":
                        rec["lure"] = {"class": lure["class"],
                                       "template_id": lure["template_id"],
                                       "lure_answer": lure["lure_answer"]}
                        rec["lure_note"] = lure["note"]
                    rec["prompt_envelope"] = ENVELOPE_ID
                    rec["provenance"] = {
                        "generator": "tools/rvr_case_generator.py",
                        "seed": SEED, "set_key": set_key,
                        "decision_log_index": set_seq,
                    }
                    rec["prompt_sha256"] = hashlib.sha256(
                        render_prompt(rec).encode("utf-8")).hexdigest()
                    rec["gt_commitment"] = _gt_commitment(case_id, gt)
                    rec["case_sha256"] = _doc_sha256(
                        {k: v for k, v in rec.items() if k != "case_sha256"})
                    cases.append(rec)
                    set_case_ids[variant] = case_id
                    gt_map[case_id] = gt
                flip_gt_map[set_id] = {
                    "gt_before": gt_map[set_case_ids["V-BASE"]],
                    "gt_after": gt_map[set_case_ids["V-FLIP"]]}
                mvs_list.append({
                    "set_id": set_id, "family": family,
                    "family_name": FAMILY_NAMES[family], "depth": depth,
                    "cell_index": cell_idx,
                    "variants": set_case_ids,
                    "mvs_sha256": _doc_sha256(set_case_ids),
                })
                build_log.append({
                    "set_id": set_id, "family": family, "depth": depth,
                    "subform": subform, "config": {k: str(v) for k, v in cfg.items()},
                    "flip": {"premise_index": edit["premise_index"],
                             "class": edit["class"]},
                    "lure": {"class": lure["class"],
                             "template_id": lure["template_id"]},
                    "rpt_premise_order": order,
                })

    ordered_case_hash = _doc_sha256(
        [{"index": i + 1, "case_id": c["case_id"], "case_sha256": c["case_sha256"]}
         for i, c in enumerate(cases)])
    enum_cases = sum(1 for c in cases if c["answer_grammar"]["type"] == "value_enum")
    cannot_gt = sum(1 for cid, gt in gt_map.items() if gt == "cannot")
    yes_gt = sum(1 for cid, gt in gt_map.items() if gt == "yes")
    no_gt = sum(1 for cid, gt in gt_map.items() if gt == "no")

    core = {
        "campaign_id": "ECP-EVAL-RVR-1",
        "schema_version": "RVR-REG-1.0",
        "package_id": "ECP-REG-RVR-V1",
        "ecp_object": "rvr-registration-package",
        "generation": {
            "tool": "tools/rvr_case_generator.py",
            "worlds_module": "tools/rvr_worlds.py",
            "seed": SEED,
            "determinism": "SHA-256 decision derivation from the registered seed; "
                           "no runtime PRNG; reproducible across Python versions",
            "name_screens": ["M3 exclusion tokens (file sha256 recorded in the "
                             "validation record)", "curated benchmark/common-word "
                             "screen", "/usr/share/dict/words when present",
                             "registered vocabulary screen"],
        },
        "campaign_size": {
            "mvs_count": len(mvs_list), "case_count": len(cases),
            "execution_count": len(cases), "attempts_per_case": 1,
            "retry_policy": "NONE",
        },
        "grid": {"families": ["F1", "F2", "F3", "F4"], "depths": [1, 2, 3],
                 "mvs_per_cell": 2,
                 "family_names": FAMILY_NAMES,
                 "f3_subform_assignment": {"D1": ["consistency", "underdetermined"],
                                           "D2": ["consistency", "consistency"],
                                           "D3": ["consistency", "underdetermined"]}},
        "prompt_envelope": {
            "id": ENVELOPE_ID,
            "template": ENVELOPE_TAIL,
            "template_sha256": hashlib.sha256(
                ENVELOPE_TAIL.encode("utf-8")).hexdigest(),
            "note": "constant across all cases; only registered fields vary",
        },
        "answer_space_distribution": {
            "value_enum_cases": enum_cases,
            "yes_no_cannot_cases": len(cases) - enum_cases,
            "gt_yes": yes_gt, "gt_no": no_gt, "gt_cannot": cannot_gt,
        },
        "mvs": mvs_list,
        "cases": cases,
        "mvs_binding_map": {m["set_id"]: m["variants"] for m in mvs_list},
        "integrity": {
            "canonicalization": "ECP-CANONICAL-JSON-1.0 (src/ecp/canonical.py)",
            "case_hash_rule": "sha256 over canonical case record with the "
                              "case_sha256 field excluded",
            "mvs_hash_rule": "sha256 over canonical {variant: case_id} map",
            "gt_commitment_rule": "sha256 over canonical {case_id, ground_truth}",
            "ordered_case_hash": ordered_case_hash,
            "note": "package_hash and classifier hash are recorded by the "
                    "registration freeze orchestrator after assembly",
        },
    }
    sidecar = {
        "sidecar_id": "RVR-PRIVATE-GT-SIDECAR-V1",
        "campaign_id": "ECP-EVAL-RVR-1",
        "note": "SEALED GROUND TRUTH — classification path only; never committed "
                "to the public repository; each entry verified against its "
                "gt_commitment in the public package",
        "gt": {cid: {"answer": gt, "gt_commitment": _gt_commitment(cid, gt)}
               for cid, gt in gt_map.items()},
        "flip_gt": flip_gt_map,
    }
    log = {"seed": SEED, "sets": build_log,
           "name_generation_attempts": nf.attempts,
           "dict_words_loaded": len(nf.dict_words)}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "rvr-package-core.json").write_text(
        json.dumps(core, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "rvr-private-gt-sidecar.json").write_text(
        json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "rvr-build-log.json").write_text(
        json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"mvs": len(mvs_list), "cases": len(cases), "cannot_gt": cannot_gt,
            "enum_cases": enum_cases}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exclude-file", required=True,
                    help="JSON file: list of M3 exclusion tokens (session-side)")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    tokens = set(json.loads(Path(args.exclude_file).read_text(encoding="utf-8")))
    stats = assemble(Path(args.out_dir), tokens)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
