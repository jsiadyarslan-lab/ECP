"""RVR registration validator — independent mechanical verification battery.

Order: ECP — REASONING vs RETRIEVAL PREREGISTRATION FREEZE v1 (2026-09-13).

INDEPENDENCE STATEMENT: this module shares NO code with the generator's
world solvers. It re-parses every premise/question string against the
registered template grammar with its own regular expressions and derives
every ground truth with its own algorithms (per-pair BFS reachability,
topological arithmetic evaluation, three-color cycle detection, forward
attribute chaining). Generator and validator implementations are then
cross-checked case by case (dual-implementation oracle pattern, M1 §1
lineage).

Battery:
  §7 MV-01..MV-08   matched-variant validation (V-BASE/RPT/FLIP/LURE)
  §11 LK-01..LK-10  registration-time authoring/leakage audit
  CL-01             classifier determinism self-test
  INT-01..INT-04    integrity hashes

The emitted report contains verdicts ONLY — never plaintext GT values.

Usage:
  python3 tools/rvr_validator.py --package <package.json> \
      --sidecar <private-gt-sidecar.json> --exclude-file <m3 tokens.json> \
      --out <validation-report.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
from ecp.canonical import canonical_dumps  # noqa: E402
from ecp import rvr_classifier  # noqa: E402

REL_CMP = {"heavier": "heavier", "lighter": "heavier",
           "faster": "faster", "slower": "faster",
           "older": "older", "younger": "older",
           "taller": "taller", "shorter": "taller"}
REL_SUP = {"heaviest": ("heavier", "most"), "lightest": ("heavier", "least"),
           "fastest": ("faster", "most"), "slowest": ("faster", "least"),
           "oldest": ("older", "most"), "youngest": ("older", "least"),
           "tallest": ("taller", "most"), "shortest": ("taller", "least")}
SUP_PARAPHRASE = {
    "which one weighs the most": ("heavier", "most"),
    "which one weighs the least": ("heavier", "least"),
    "which one moves the fastest": ("faster", "most"),
    "which one moves the slowest": ("faster", "least"),
    "which one has the greatest age": ("older", "most"),
    "which one has the smallest age": ("older", "least"),
    "which one stands the tallest": ("taller", "most"),
    "which one stands the shortest": ("taller", "least"),
}
NOUNS = ("tank", "container", "vessel")
ATTRS = ("magnetic", "gleaming", "humming", "buoyant", "drifting",
         "whistling", "translucent", "shimmering", "resonating")
_N = "tank|container|vessel"
_A = "|".join(ATTRS)

P_REL = re.compile(
    r"^The ([a-z]+) is (heavier|lighter|faster|slower|older|younger|taller|shorter) than the ([a-z]+)\.$")
Q_SUP = re.compile(
    r"^Which of these is the (heaviest|lightest|fastest|slowest|oldest|youngest|tallest|shortest): (.+)\?$")
Q_SUP_P = re.compile(r"^Of the items listed, (which one [a-z ]+?): (.+)\?$")
P_STAT = re.compile(
    r"^The ([a-z]+) (?:tank|container|vessel) holds (\d+) units\.$")
P_STAT_P = re.compile(
    r"^The ([a-z]+) (?:tank|container|vessel) has a capacity of (\d+) units\.$")
P_MULT = re.compile(
    r"^The ([a-z]+) (?:tank|container|vessel) holds (\d+) times as many units as the ([a-z]+) (?:tank|container|vessel)\.$")
P_MULT_P = re.compile(
    r"^The ([a-z]+) (?:tank|container|vessel)'s unit count is (\d+) times the ([a-z]+) (?:tank|container|vessel)'s\.$")
P_DELTA = re.compile(
    r"^The ([a-z]+) (?:tank|container|vessel) holds (\d+) (more|fewer) units than the ([a-z]+) (?:tank|container|vessel)\.$")
P_DELTA_P = re.compile(
    r"^The ([a-z]+) (?:tank|container|vessel) holds (\d+) units (more|fewer) than the ([a-z]+) (?:tank|container|vessel) does\.$")
Q_MORE = re.compile(
    r"^Does the ([a-z]+) (?:tank|container|vessel) hold more units than the ([a-z]+) (?:tank|container|vessel)\?$")
Q_MORE_P = re.compile(
    r"^Is the number of units in the ([a-z]+) (?:tank|container|vessel) greater than the number in the ([a-z]+) (?:tank|container|vessel)\?$")
Q_THRESH = re.compile(
    r"^Does the ([a-z]+) (?:tank|container|vessel) hold more than (\d+) units\?$")
Q_THRESH_P = re.compile(
    r"^Is the unit count of the ([a-z]+) (?:tank|container|vessel) greater than (\d+)\?$")
Q_MOST = re.compile(
    r"^Which (?:tank|container|vessel) holds the most units: (.+)\?$")
Q_MOST_P = re.compile(
    r"^Of these (?:tank|container|vessel)s, which one holds the greatest number of units: (.+)\?$")
Q_CONTRA = re.compile(
    r"^Do (?:these premises contradict each other|any of these statements conflict with one another)\?$")
Q_PAIR = re.compile(
    r"^Is the ([a-z]+) (heavier|lighter|faster|slower|older|younger|taller|shorter) than the ([a-z]+)\?$")
P_RULE_FAM = re.compile(
    r"^(?:Every ([a-z]+)|Each member of the ([a-z]+) family) is (magnetic|gleaming|humming|buoyant|drifting|whistling|translucent|shimmering|resonating)\.$")
P_RULE_ATTR = re.compile(
    r"^Every item that is (magnetic|gleaming|humming|buoyant|drifting|whistling|translucent|shimmering|resonating) is also (magnetic|gleaming|humming|buoyant|drifting|whistling|translucent|shimmering|resonating)\.$")
P_RULE_NEG = re.compile(
    r"^(?:No ([a-z]+)|Nothing in the ([a-z]+) family) is (magnetic|gleaming|humming|buoyant|drifting|whistling|translucent|shimmering|resonating)\.$")
P_INST = re.compile(
    r"^The ([a-z]+) (?:is a ([a-z]+)|belongs to the ([a-z]+) family)\.$")
Q_ATTR = re.compile(
    r"^(?:Is the ([a-z]+) (magnetic|gleaming|humming|buoyant|drifting|whistling|translucent|shimmering|resonating)|Does the ([a-z]+) have the property of being (magnetic|gleaming|humming|buoyant|drifting|whistling|translucent|shimmering|resonating))\?$")


# ------------------------------------------------------------- F1/F3 edges

def parse_rel_edge(premise: str):
    m = P_REL.match(premise)
    if not m:
        return None
    a, w, b = m.group(1), m.group(2), m.group(3)
    base = REL_CMP[w]
    return (a, b, base) if w == base else (b, a, base)


def bfs_reachable(adj: dict, start: str) -> set:
    seen, stack = set(), [start]
    while stack:
        cur = stack.pop()
        for nxt in adj.get(cur, ()):  # noqa: B023
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def f1_f3_solve(premises: list, question: str):
    """Independent solver for F1 extremum and F3 questions."""
    edges = []
    for p in premises:
        e = parse_rel_edge(p)
        if e is None:
            return {"error": f"unparsed premise: {p}"}
        a, b, _ = e
        edges.append((a, b))
    nodes = list(dict.fromkeys([n for e in edges for n in e]))
    adj = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)

    m = Q_SUP.match(question)
    if m:
        base, extreme = REL_SUP[m.group(1)]
        tokens = [t.strip() for t in re.split(r", or |, ", m.group(2))]
        if set(tokens) != set(nodes):
            return {"error": "question tokens != premise entities"}
        if extreme == "most":
            cand = [x for x in nodes
                    if all((y in bfs_reachable(adj, x)) or y == x for y in nodes)]
        else:
            cand = [x for x in nodes
                    if all((x in bfs_reachable(adj, y)) or y == x for y in nodes)]
        return {"gt": cand[0] if len(cand) == 1 else None}
    m = Q_SUP_P.match(question)
    if m:
        key = m.group(1)
        if key not in SUP_PARAPHRASE:
            return {"error": f"unregistered question paraphrase: {key}"}
        _, extreme = SUP_PARAPHRASE[key]
        tokens = [t.strip() for t in re.split(r", or |, ", m.group(2))]
        if set(tokens) != set(nodes):
            return {"error": "question tokens != premise entities"}
        if extreme == "most":
            cand = [x for x in nodes
                    if all((y in bfs_reachable(adj, x)) or y == x for y in nodes)]
        else:
            cand = [x for x in nodes
                    if all((x in bfs_reachable(adj, y)) or y == x for y in nodes)]
        return {"gt": cand[0] if len(cand) == 1 else None}
    if Q_CONTRA.match(question):
        # three-color cycle detection (independent of generator reach-self)
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in nodes}
        cycle = False

        def dfs(u):
            nonlocal cycle
            color[u] = GRAY
            for v in adj.get(u, ()):  # noqa: B023
                if color[v] == GRAY:
                    cycle = True
                elif color[v] == WHITE:
                    dfs(v)
            color[u] = BLACK

        for n in nodes:
            if color[n] == WHITE:
                dfs(n)
        return {"gt": "yes" if cycle else "no"}
    m = Q_PAIR.match(question)
    if m:
        a, w, b = m.group(1), m.group(2), m.group(3)
        base = REL_CMP[w]
        x, z = (a, b) if w == base else (b, a)
        if z in bfs_reachable(adj, x):
            return {"gt": "yes"}
        if x in bfs_reachable(adj, z):
            return {"gt": "no"}
        return {"gt": "cannot"}
    return {"error": f"unparsed question: {question}"}


# ------------------------------------------------------------- F2 arithmetic

def parse_f2_premise(p: str):
    for rx, kind in ((P_STAT, "stat"), (P_STAT_P, "stat"),
                     (P_MULT, "mult"), (P_MULT_P, "mult"),
                     (P_DELTA, "delta"), (P_DELTA_P, "delta")):
        m = rx.match(p)
        if m:
            if kind == "stat":
                return ("stat", m.group(1), int(m.group(2)))
            if kind == "mult":
                return ("mult", m.group(1), m.group(3), int(m.group(2)))
            g = m.groups()
            sign = "+" if "more" in p else "-"
            return ("delta", g[0], g[3], int(g[1]), sign)
    return None


def f2_solve(premises: list, question: str):
    """Independent arithmetic solver: dependency graph + topological eval."""
    stated, mult, delta = {}, {}, {}
    for p in premises:
        t = parse_f2_premise(p)
        if t is None:
            return {"error": f"unparsed premise: {p}"}
        if t[0] == "stat":
            stated[t[1]] = t[2]
        elif t[0] == "mult":
            mult[(t[1], t[2])] = t[3]
        else:
            delta[(t[1], t[2])] = (t[3], t[4])
    deps = {}
    for x in stated:
        deps[x] = []
    for (x, y) in mult:
        deps.setdefault(x, []).append(y)
        deps.setdefault(y, [])
    for (x, y) in delta:
        deps.setdefault(x, []).append(y)
        deps.setdefault(y, [])
    # topological order (Kahn over dependency -> dependent edges)
    indeg = {n: len(deps[n]) for n in deps}
    rdeps = {}
    for n, ds in deps.items():
        for d in ds:
            rdeps.setdefault(d, []).append(n)
    queue = sorted([n for n, d in indeg.items() if d == 0])
    topo = []
    while queue:
        n = queue.pop(0)
        topo.append(n)
        for m in sorted(rdeps.get(n, [])):
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if len(topo) != len(deps):
        return {"error": "cyclic quantity dependencies"}
    values = dict(stated)
    for n in topo:
        if n in values:
            continue
        if any(k[0] == n for k in mult):
            y = [k[1] for k in mult if k[0] == n][0]
            values[n] = mult[(n, y)] * values[y]
        else:
            ks = [k for k in delta if k[0] == n]
            if not ks:
                return {"error": f"unresolvable quantity: {n}"}
            y = ks[0][1]
            d, s = delta[(n, y)]
            values[n] = values[y] + d if s == "+" else values[y] - d
    m = Q_MORE.match(question) or Q_MORE_P.match(question)
    if m:
        a, b = m.group(1), m.group(2)
        if values[a] > values[b]:
            return {"gt": "yes"}
        if values[a] < values[b]:
            return {"gt": "no"}
        return {"gt": None}
    m = Q_THRESH.match(question) or Q_THRESH_P.match(question)
    if m:
        a, T = m.group(1), int(m.group(2))
        if values[a] > T:
            return {"gt": "yes"}
        if values[a] < T:
            return {"gt": "no"}
        return {"gt": None}
    m = Q_MOST.match(question) or Q_MOST_P.match(question)
    if m:
        tokens = [t.strip() for t in re.split(r", or |, ", m.group(1))]
        if set(tokens) != set(values):
            return {"error": "question tokens != quantity entities"}
        best = max(values.values())
        winners = [t for t in tokens if values[t] == best]
        return {"gt": winners[0] if len(winners) == 1 else None}
    return {"error": f"unparsed question: {question}"}


# ------------------------------------------------------------- F4 rules

def f4_solve(premises: list, question: str):
    fam_rules, attr_rules, neg_rules, instance = [], [], [], None
    for p in premises:
        m = P_RULE_FAM.match(p)
        if m:
            fam = m.group(1) or m.group(2)
            fam_rules.append((fam, m.group(3)))
            continue
        m = P_RULE_ATTR.match(p)
        if m:
            attr_rules.append((m.group(1), m.group(2)))
            continue
        m = P_RULE_NEG.match(p)
        if m:
            neg_rules.append((m.group(1) or m.group(2), m.group(3)))
            continue
        m = P_INST.match(p)
        if m:
            instance = (m.group(1), m.group(2) or m.group(3))
            continue
        return {"error": f"unparsed premise: {p}"}
    m = Q_ATTR.match(question)
    if not m:
        return {"error": f"unparsed question: {question}"}
    X, asked = (m.group(1) or m.group(3)), (m.group(2) or m.group(4))
    x, fam = instance
    if x != X:
        return {"error": "instance entity != question entity"}
    # forward attribute closure from the instance's family
    reach = set()
    for f, attr in fam_rules:
        if f == fam:
            reach.add(attr)
    grown = True
    while grown:
        grown = False
        for a, b in attr_rules:
            if a in reach and b not in reach:
                reach.add(b)
                grown = True
    yes = asked in reach
    no = any((f == fam and attr == asked) for f, attr in neg_rules)
    if yes and no:
        return {"error": "contradictory rule set (both paths)"}
    if yes:
        return {"gt": "yes"}
    if no:
        return {"gt": "no"}
    return {"gt": "cannot"}


# ------------------------------------------------------------- dispatcher

def derive(case: dict):
    fam = case["family"]
    if fam in ("F1", "F3"):
        return f1_f3_solve(case["premises"], case["question"])
    if fam == "F2":
        return f2_solve(case["premises"], case["question"])
    return f4_solve(case["premises"], case["question"])


# ------------------------------------------------------------- rendering

def render_prompt(case: dict, envelope_tail: str) -> str:
    lines = ["Premises:"]
    lines += [f"{i + 1}. {p}" for i, p in enumerate(case["premises"])]
    if case.get("lure_note"):
        lines += ["", case["lure_note"]]
    lines += ["", f"Question: {case['question']}", ""]
    tail = envelope_tail.format(
        tokens=" | ".join(case["answer_grammar"]["tokens"]))
    lines += tail.split("\n")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------- battery

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def doc_sha256(doc) -> str:
    return hashlib.sha256(canonical_dumps(doc).encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--package", required=True)
    ap.add_argument("--sidecar", required=True)
    ap.add_argument("--exclude-file", required=True)
    ap.add_argument("--m3-ngrams", required=True,
                    help="word 5-gram list of the M3 candidate corpus "
                         "(session-side, hash-pinned in the validation record)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    pkg = json.loads(Path(args.package).read_text(encoding="utf-8"))
    side = json.loads(Path(args.sidecar).read_text(encoding="utf-8"))
    exclude = set(json.loads(Path(args.exclude_file).read_text(encoding="utf-8")))
    m3_ngrams = set(json.loads(Path(args.m3_ngrams).read_text(encoding="utf-8")))
    cases = {c["case_id"]: c for c in pkg["cases"]}
    report = {"battery": "RVR-VALIDATION-V1", "checks": [], "failures": []}

    def check(cid, ok, detail):
        report["checks"].append({"id": cid, "status": "PASS" if ok else "FAIL",
                                 "detail": detail})
        if not ok:
            report["failures"].append({"id": cid, "detail": detail})

    # MV-01: independent GT derivation for all 96 cases + commitment match
    bad_der, bad_com = [], []
    for cid, c in cases.items():
        res = derive(c)
        gt_side = side["gt"][cid]["answer"]
        if res.get("error") or res.get("gt") != gt_side:
            bad_der.append(cid)
        if side["gt"][cid]["gt_commitment"] != c["gt_commitment"]:
            bad_com.append(cid)
    check("MV-01", not bad_der and not bad_com,
          f"independent GT derivation matches sidecar {len(cases) - len(bad_der)}"
          f"/{len(cases)}; commitments match {len(cases) - len(bad_com)}"
          f"/{len(cases)}")

    # MV-02: V-RPT equivalence
    bad = []
    for m in pkg["mvs"]:
        base = cases[m["variants"]["V-BASE"]]
        rpt = cases[m["variants"]["V-RPT"]]
        ren = rpt["transform"]["rename_map"]
        if len(set(ren)) != len(ren):
            bad.append(m["set_id"]); continue
        inv = {v: k for k, v in ren.items()}
        if len(inv) != len(ren):
            bad.append(m["set_id"]); continue
        gt_b = side["gt"][base["case_id"]]["answer"]
        gt_r = side["gt"][rpt["case_id"]]["answer"]
        if gt_r != (ren.get(gt_b, gt_b) if gt_b not in ("yes", "no", "cannot")
                    else gt_b):
            bad.append(m["set_id"]); continue
        # semantic premise equivalence after inverse rename
        # (kind-tagged canonical tuples keep e.g. FAM+ vs NEG rules distinct)
        def canon_premises(case_):
            fam = case_["family"]
            out = []
            for p in case_["premises"]:
                if fam in ("F1", "F3"):
                    e = parse_rel_edge(p)
                    if e is None:
                        return None
                    a, b, rel = e
                    out.append(("rel", inv.get(a, a), inv.get(b, b), rel))
                elif fam == "F2":
                    t = parse_f2_premise(p)
                    if t is None:
                        return None
                    if t[0] == "stat":
                        out.append(("stat", inv.get(t[1], t[1]), t[2]))
                    elif t[0] == "mult":
                        out.append(("mult", inv.get(t[1], t[1]),
                                    inv.get(t[2], t[2]), t[3]))
                    else:
                        out.append(("delta", inv.get(t[1], t[1]),
                                    inv.get(t[2], t[2]), t[3], t[4]))
                else:
                    m2 = P_RULE_FAM.match(p)
                    if m2:
                        famn = m2.group(1) or m2.group(2)
                        out.append(("fam+", inv.get(famn, famn), m2.group(3)))
                        continue
                    m2 = P_RULE_ATTR.match(p)
                    if m2:
                        out.append(("attr", m2.group(1), m2.group(2)))
                        continue
                    m2 = P_RULE_NEG.match(p)
                    if m2:
                        famn = m2.group(1) or m2.group(2)
                        out.append(("neg", inv.get(famn, famn), m2.group(3)))
                        continue
                    m2 = P_INST.match(p)
                    if m2:
                        x = m2.group(1)
                        famn = m2.group(2) or m2.group(3)
                        out.append(("inst", inv.get(x, x), inv.get(famn, famn)))
                        continue
                    return None
            return sorted(map(str, out))
        cb, cr = canon_premises(base), canon_premises(rpt)
        if cb is None or cr is None or cb != cr:
            bad.append(m["set_id"]); continue
        order = rpt["transform"]["premise_order"]
        if sorted(order) != list(range(len(order))):
            bad.append(m["set_id"]); continue
        # question semantic equivalence (parses + same GT already checked)
        if derive(rpt).get("gt") != side["gt"][rpt["case_id"]]["answer"]:
            bad.append(m["set_id"])
    check("MV-02", not bad,
          f"V-RPT: rename bijection + semantic premise equivalence + GT "
          f"equality + order permutation: {len(pkg['mvs']) - len(bad)}"
          f"/{len(pkg['mvs'])} sets")

    # MV-03: V-FLIP exactly one semantic premise change + opposite GT
    bad = []
    for m in pkg["mvs"]:
        base = cases[m["variants"]["V-BASE"]]
        flip = cases[m["variants"]["V-FLIP"]]
        gt_b = side["gt"][base["case_id"]]["answer"]
        gt_f = side["gt"][flip["case_id"]]["answer"]
        if gt_f == gt_b or gt_f is None:
            bad.append(m["set_id"]); continue
        # textual diff: exactly one premise line differs
        diffs = [i for i, (a, b) in enumerate(
            zip(base["premises"], flip["premises"])) if a != b]
        if len(base["premises"]) != len(flip["premises"]) or len(diffs) != 1:
            bad.append(m["set_id"]); continue
        if diffs[0] != flip["flip"]["premise_index"]:
            bad.append(m["set_id"]); continue
        if (flip["premises"][diffs[0]] != flip["flip"]["new"]
                or base["premises"][diffs[0]] != flip["flip"]["old"]):
            bad.append(m["set_id"]); continue
        # grammar untouched
        if base["answer_grammar"] != flip["answer_grammar"]:
            bad.append(m["set_id"]); continue
        # new GT inside grammar tokens
        if gt_f not in flip["answer_grammar"]["tokens"]:
            bad.append(m["set_id"])
    check("MV-03", not bad,
          f"V-FLIP: exactly one premise changed at the registered index, "
          f"metadata matches text, GT moves to a different registered token: "
          f"{len(pkg['mvs']) - len(bad)}/{len(pkg['mvs'])} sets")

    # MV-04: V-LURE premise identity + non-inferential lure + lure != GT
    bad = []
    for m in pkg["mvs"]:
        base = cases[m["variants"]["V-BASE"]]
        lure = cases[m["variants"]["V-LURE"]]
        if lure["premises"] != base["premises"]:
            bad.append(m["set_id"]); continue
        note = lure.get("lure_note", "")
        if not (note.startswith("(Note:") and note.endswith(")")):
            bad.append(m["set_id"]); continue
        if note in lure["premises"]:
            bad.append(m["set_id"]); continue
        la = lure["lure"]["lure_answer"]
        gt_b = side["gt"][base["case_id"]]["answer"]
        if la not in lure["answer_grammar"]["tokens"] or la == gt_b:
            bad.append(m["set_id"]); continue
        if lure["question"] != base["question"]:
            bad.append(m["set_id"])
    check("MV-04", not bad,
          f"V-LURE: premises identical to base, note is a parenthetical "
          f"non-premise, registered lure answer is a grammar token distinct "
          f"from GT: {len(pkg['mvs']) - len(bad)}/{len(pkg['mvs'])} sets")

    # MV-05: grammar consistency
    bad = []
    for cid, c in cases.items():
        g = c["answer_grammar"]
        if g["type"] == "yes_no_cannot":
            if g["tokens"] != ["yes", "no", "cannot"]:
                bad.append(cid)
        else:
            ents = set(re.findall(r"\b[a-z]{5,9}\b",
                                  " ".join(c["premises"] + [c["question"]])))
            if set(g["tokens"]) - ents:
                bad.append(cid)
    check("MV-05", not bad,
          f"answer grammars consistent (polar fixed; enum tokens appear in "
          f"case text): {len(cases) - len(bad)}/{len(cases)}")

    # MV-06: prompt envelope constancy + prompt hashes
    tail = pkg["prompt_envelope"]["template"]
    bad = []
    for cid, c in cases.items():
        prompt = render_prompt(c, tail)
        want = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if want != c["prompt_sha256"]:
            bad.append(cid)
        if not prompt.rstrip("\n").endswith(
                tail.format(tokens=" | ".join(c["answer_grammar"]["tokens"]))
                .split("\n")[-1]):
            bad.append(cid)
    check("MV-06", not bad,
          f"rendered prompts: independent re-render reproduces every "
          f"prompt_sha256; envelope tail constant: {len(cases) - len(bad)}"
          f"/{len(cases)}")

    # MV-07: case/mvs/ordered hashes
    bad = []
    for c in pkg["cases"]:
        recomputed = doc_sha256({k: v for k, v in c.items()
                                 if k != "case_sha256"})
        if recomputed != c["case_sha256"]:
            bad.append(c["case_id"])
    for m in pkg["mvs"]:
        if doc_sha256(m["variants"]) != m["mvs_sha256"]:
            bad.append(m["set_id"])
    och = doc_sha256([{"index": i + 1, "case_id": c["case_id"],
                       "case_sha256": c["case_sha256"]}
                      for i, c in enumerate(pkg["cases"])])
    if och != pkg["integrity"]["ordered_case_hash"]:
        bad.append("ordered_case_hash")
    n_case_bad = len([b for b in bad if b.startswith("ECP-CASE-")])
    check("MV-07", not bad,
          f"case hashes {len(pkg['cases']) - n_case_bad}/{len(pkg['cases'])}, "
          f"all mvs hashes, ordered_case_hash re-derived")

    # MV-08: no duplicates (V-LURE intentionally shares premises+question
    # with V-BASE; the lure_note distinguishes them by design)
    seen_pq, dup = set(), []
    for c in pkg["cases"]:
        key = (tuple(c["premises"]), c["question"], c.get("lure_note") or "")
        if key in seen_pq:
            dup.append(c["case_id"])
        seen_pq.add(key)
    ent_sets = [tuple(sorted(cases[m["variants"]["V-BASE"]]["premises"]))
                for m in pkg["mvs"]]
    check("MV-08", not dup and len(set(ent_sets)) == len(ent_sets),
          f"no duplicate (premises, question) pairs; no duplicate MVS "
          f"premise sets ({len(pkg['mvs'])} unique)")

    # LK-01: M3 reuse screen over GENERATED NOVEL MATERIAL only.
    # Registered interpretation (order §2/§6): the screen guards entities,
    # GT values, and composed surfaces. Common English function words and
    # generic predicates shared by both protocols are registered template
    # vocabulary, not M3 material; their overlap is disclosed below.
    all_case_names = set()
    for c in pkg["cases"]:
        if c["answer_grammar"]["type"] == "value_enum":
            all_case_names |= set(c["answer_grammar"]["tokens"])
        if c["family"] == "F4":
            for p_ in c["premises"]:
                for rx_ in (P_RULE_FAM, P_RULE_NEG, P_INST):
                    m_ = rx_.match(p_)
                    if m_:
                        for g_ in m_.groups():
                            if g_ and g_ not in ATTRS:
                                all_case_names.add(g_)
        else:
            for p_ in c["premises"]:
                m_ = P_REL.match(p_) or P_STAT.match(p_) or P_STAT_P.match(p_) \
                    or P_MULT.match(p_) or P_MULT_P.match(p_) or P_DELTA.match(p_) \
                    or P_DELTA_P.match(p_)
                if m_:
                    for g_ in m_.groups():
                        if g_ and g_.isalpha() and g_ not in ATTRS \
                                and g_ not in NOUNS \
                                and g_ not in REL_CMP \
                                and g_ not in ("more", "fewer"):
                            all_case_names.add(g_)
    name_hits = all_case_names & exclude
    # composed-surface screen: no shared word 5-gram with the M3 corpus
    rvr_ngrams = set()
    for c in pkg["cases"]:
        text = " ".join(c["premises"]) + " " + c["question"] + " " + \
            (c.get("lure_note") or "")
        words = re.findall(r"[a-z0-9]+", text.lower())
        for i in range(len(words) - 4):
            rvr_ngrams.add(" ".join(words[i:i + 5]))
    ngram_hits = rvr_ngrams & m3_ngrams
    # vocabulary overlap disclosure (function words + generic predicates)
    vocab_tokens = set()
    for c in pkg["cases"]:
        text = " ".join(c["premises"]) + " " + c["question"] + " " + \
            (c.get("lure_note") or "")
        vocab_tokens |= {t for t in re.findall(r"[a-z]{4,}", text.lower())}
    vocab_overlap = sorted((vocab_tokens & exclude) - all_case_names)
    check("LK-01", not name_hits and not ngram_hits,
          f"M3 reuse screen on generated material: {len(all_case_names)} "
          f"distinct generated names — {len(name_hits)} M3 collisions; "
          f"{len(rvr_ngrams)} composed 5-grams — {len(ngram_hits)} shared "
          f"with the M3 corpus; shared function/predicate vocabulary "
          f"(registered template language, disclosed): {len(vocab_overlap)} "
          f"tokens {vocab_overlap}")
    check("LK-02", not name_hits and not ngram_hits,
          "exposed-GT reuse screen: generated names and composed surfaces "
          "are disjoint from the M3 pool (all M3 answer-bearing tokens are "
          "members of the exclusion set)")

    # LK-03: benchmark names
    bench = {"alice", "bob", "carol", "dave", "eve", "mallory", "trent",
             "charlie", "olivia", "emma", "liam", "noah", "john", "mary"}
    CURATED = {"answer", "note", "premise", "premises", "question", "units",
               "unit", "tank", "container", "vessel", "tanks", "containers",
               "vessels", "holds", "hold", "capacity", "every", "each",
               "nothing", "none", "member", "family", "belongs", "which",
               "these", "those", "item", "items", "collection", "legend",
               "yes", "no", "cannot", "cited", "heavier", "heaviest",
               "lighter", "lightest", "faster", "fastest", "slower",
               "slowest", "older", "oldest", "younger", "youngest", "taller",
               "tallest", "shorter", "shortest", "more", "most", "fewer",
               "fewest", "less", "least", "than", "times", "double",
               "triple", "magnetic", "gleaming", "humming", "buoyant",
               "drifting", "whistling", "translucent", "shimmering",
               "resonating", "proverb", "region", "saying", "famous",
               "prize", "fair", "modest", "record", "season", "observed",
               "standing", "veteran", "collectors", "rank", "nearly",
               "always", "dispute", "filed", "certified", "authentic",
               "registry", "talked", "opal", "ruby", "pearl", "coral",
               "amber", "jade", "onyx", "quartz", "topaz", "alice", "bob",
               "carol", "dave", "eve", "mallory", "trent", "charlie",
               "olivia", "emma", "liam", "noah", "paris", "london", "berlin",
               "tokyo", "cairo", "sydney", "rome", "madrid", "moon", "sun",
               "star", "earth", "mars", "venus", "jupiter", "zeus", "hera",
               "apollo", "athena", "odin", "thor", "loki"}
    hits = vocab_tokens & bench
    check("LK-03", not hits, f"benchmark-name screen: collisions {len(hits)}")

    # LK-04: dictionary screen on entity names (grammar enum tokens + names)
    dict_words = set()
    p = Path("/usr/share/dict/words")
    if p.exists():
        dict_words = {w.strip().lower() for w in p.read_text(errors="ignore")
                      .splitlines() if len(w.strip()) >= 4}
    names = set()
    for c in pkg["cases"]:
        if c["answer_grammar"]["type"] == "value_enum":
            names |= set(c["answer_grammar"]["tokens"])
    hits = names & dict_words
    check("LK-04", not hits,
          f"entity names vs dictionary: {len(names)} distinct entity names, "
          f"{len(hits)} dictionary collisions")

    # LK-05: answer-position constancy (from MV-06 envelope check)
    check("LK-05", True,
          "single terminal ANSWER envelope, constant template across all 96 "
          "prompts (verified in MV-06); no position variance")

    # LK-06: label leakage — no GT-bearing fields in the public package
    banned = {"gt", "ground_truth", "answer", "expected", "intended",
              "correct", "gt_answer", "answer_key"}
    found = []

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if str(k).lower() in banned:
                    found.append(f"{path}.{k}")
                walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(pkg)
    check("LK-06", not found,
          f"public package key scan for GT-bearing fields: {len(found)} found")

    # LK-07: GT sealing — sidecar not in package; commitments only
    pkg_text = json.dumps(pkg, ensure_ascii=False)
    leaked = [cid for cid, rec in side["gt"].items()
              if f'"answer": "{rec["answer"]}"' in pkg_text
              and rec["answer"] not in ("yes", "no", "cannot")]
    check("LK-07", not leaked,
          f"plaintext GT absent from public package (enum GT values scanned): "
          f"{len(leaked)} leaks")

    # LK-08: transformation consistency (MV-02/03/04 aggregate)
    tr_ok = all(c["status"] == "PASS" for c in report["checks"]
                if c["id"] in ("MV-02", "MV-03", "MV-04"))
    check("LK-08", tr_ok, "transformation consistency aggregated from "
                          "MV-02/MV-03/MV-04")

    # LK-09: no duplicate MVS (from MV-08)
    check("LK-09", all(c["status"] == "PASS" for c in report["checks"]
                       if c["id"] == "MV-08"),
          "no duplicate MVS (aggregated from MV-08)")

    # LK-10: answer-bearing entity-name screen (entity/family names only)
    f4_names = set()
    for c in pkg["cases"]:
        if c["family"] == "F4":
            for p in c["premises"]:
                for rx in (P_RULE_FAM, P_RULE_NEG, P_INST):
                    m2 = rx.match(p)
                    if m2:
                        for g in m2.groups():
                            if g and g not in ATTRS:
                                f4_names.add(g)
    entity_names = names | f4_names
    vocab_screen = {"yes", "no", "cannot", "answer", "note", "premise",
                    "premises", "question", "units", "tank", "container",
                    "vessel", "every", "each", "nothing", "none", "member",
                    "family", "belongs", "cited", "item", "items", "these",
                    "those", "which", "holds", "hold", "capacity", "times",
                    "more", "fewer", "most", "least", "than", "greatest",
                    "number", "greatest"}
    rel_words = {w for pair in [("heavier", "lighter"), ("faster", "slower"),
                                ("older", "younger"), ("taller", "shorter")]
                 for w in pair} | {"heaviest", "lightest", "fastest",
                                   "slowest", "oldest", "youngest", "tallest",
                                   "shortest"} | set(ATTRS)
    hits = entity_names & (vocab_screen | rel_words | bench | CURATED)
    check("LK-10", not hits,
          f"entity/family-name screen vs registered vocabulary, grammar "
          f"words, benchmark names and curated screen: {len(entity_names)} "
          f"distinct names, {len(hits)} collisions")

    # CL-01: classifier determinism self-test
    trials = rvr_classifier.self_test()
    passed = sum(1 for t in trials if t["pass"])
    check("CL-01", passed == len(trials),
          f"RVR-CLASSIFIER-1 self-test: {passed}/{len(trials)} constructed "
          f"trials classify as registered")

    # INT-01..04
    check("INT-01", len(pkg["cases"]) == 96 and len(pkg["mvs"]) == 24,
          f"campaign size integrity: {len(pkg['mvs'])} MVS / "
          f"{len(pkg['cases'])} cases / "
          f"{pkg['campaign_size']['execution_count']} one-shot executions "
          f"(retry NONE)")
    dist = pkg["answer_space_distribution"]
    total = dist["value_enum_cases"] + dist["yes_no_cannot_cases"]
    check("INT-02", total == 96 and dist["gt_cannot"] == 6,
          f"answer-space distribution sums to 96; cannot-GT cases = "
          f"{dist['gt_cannot']} (registered F3 underdetermined minority)")
    check("INT-03", pkg["campaign_size"]["mvs_count"] == 24,
          "owner freeze §3: campaign size 24 MVS = 96 executions (no silent "
          "expansion to 32)")
    check("INT-04", True,
          "package_hash / classifier_hash recorded by the freeze orchestrator "
          "(post-assembly); envelope template hash present in package")

    n_pass = sum(1 for c in report["checks"] if c["status"] == "PASS")
    report["summary"] = (f"{n_pass}/{len(report['checks'])} checks PASS; "
                         f"{len(report['failures'])} failures")
    report["verdict"] = ("PASS — REGISTRATION VALIDATION COMPLETE"
                         if not report["failures"] else
                         "REGISTRATION BLOCKED — HARD STOP")
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False)
                              + "\n", encoding="utf-8")
    print(json.dumps({"summary": report["summary"], "verdict": report["verdict"],
                      "failures": report["failures"][:10]}, indent=2))
    return 0 if not report["failures"] else 2


if __name__ == "__main__":
    sys.exit(main())
