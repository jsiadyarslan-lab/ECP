"""RVR world builders — edit-aware deterministic case-world construction.

Part of the registered authoring instrument for campaign ECP-EVAL-RVR-1
(order: ECP — REASONING vs RETRIEVAL PREREGISTRATION FREEZE v1, 2026-09-13).

Each builder constructs ONE case world for one family/depth and can apply
exactly ONE registered premise edit (the V-FLIP mechanism). The builder
computes the world's ground truth with the generator-side solver; the
registration validator re-derives it with an INDEPENDENT solver over the
rendered premise text (dual-implementation cross-check, M1 oracle pattern).

Registered edit classes (V-FLIP search space):
  F1: relation_reversal            (premise "A Rer B" -> "B Rer A")
  F2: stated_value_change / multiplier_change / delta_change
  F3: relation_reversal / entity_substitution
  F4: instance_family_reassignment (premise "X is a POS" -> "X is a NEG")
"""

from __future__ import annotations

from typing import Any, Optional

# ---------------------------------------------------------------- solvers

def f1_extreme(entities: list, edges: "list[tuple[str,str]]", extreme: str):
    """Unique top (most) / unique bottom (least) via closure; None if not unique."""
    dom = {e: set() for e in entities}          # e -> set of entities below e
    for a, b in edges:
        dom[a].add(b)
    changed = True
    while changed:
        changed = False
        for a in entities:
            new = set(dom[a])
            for b in list(dom[a]):
                new |= dom[b]
            if new != dom[a]:
                dom[a] = new
                changed = True
    if extreme == "most":
        tops = [e for e in entities if all((x in dom[e]) or (x == e) for x in entities)]
        return tops[0] if len(tops) == 1 else None
    bottoms = [e for e in entities if all((e in dom[x]) or (x == e) for x in entities)]
    return bottoms[0] if len(bottoms) == 1 else None


def f2_value(x: str, stated: dict, mult: dict, delta: dict) -> int:
    if x in stated:
        return stated[x]
    for (a, b), k in mult.items():
        if a == x:
            return k * f2_value(b, stated, mult, delta)
    for (a, b), (d, s) in delta.items():
        if a == x:
            base = f2_value(b, stated, mult, delta)
            return base + d if s == "+" else base - d
    raise KeyError(x)


def f3_solve(edges: "list[tuple[str,str]]", x: str = None, z: str = None) -> str:
    """Consistency / cross-pair solver over a directed R-edge list."""
    nodes = sorted({n for e in edges for n in e})
    adj = {n: [] for n in nodes}
    for a, b in edges:
        adj[a].append(b)

    def reach(start: str) -> set:
        seen, stack = set(), [start]
        while stack:
            cur = stack.pop()
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    if x is None:  # consistency question: cycle detection
        for n in nodes:
            if n in reach(n):
                return "yes"          # a contradiction exists
        return "no"
    if z in reach(x):
        return "yes"
    if x in reach(z):
        return "no"
    return "cannot"


def f4_solve(pos_fam: str, neg_fam: str, chain: list, x_fam: str) -> str:
    """Rule-chain solver: instance family -> attribute closure."""
    if x_fam == pos_fam:
        return "yes"          # positive chain entails every chain attribute
    if x_fam == neg_fam:
        return "no"           # negative rule at the asked (terminal) attribute
    return "cannot"


# ---------------------------------------------------------------- F1

def build_f1(key: str, names: list, rel: tuple, depth: int, extreme: str,
             paraphrase: bool, edit: Optional[dict] = None) -> dict:
    n = depth + 2
    ents = names[:n]
    edges = [(ents[i], ents[i + 1]) for i in range(n - 1)]
    premise_pairs = [(ents[i], ents[i + 1]) for i in range(n - 1)]
    if edit is not None:
        i = edit["premise_index"]
        a, b = premise_pairs[i]
        premise_pairs[i] = (b, a)            # relation_reversal
        edges[i] = (b, a)
    if paraphrase:
        premises = [f"The {b} is {rel[2]} than the {a}." for a, b in premise_pairs]
    else:
        premises = [f"The {a} is {rel[0]} than the {b}." for a, b in premise_pairs]
    listing = ", ".join(ents[:-1]) + f", or {ents[-1]}"
    if extreme == "most":
        gt = f1_extreme(ents, edges, "most")
        question = (f"Of the items listed, {rel[4]}: {listing}?" if paraphrase
                    else f"Which of these is the {rel[1]}: {listing}?")
    else:
        gt = f1_extreme(ents, edges, "least")
        least_q = {"lightest": "which one weighs the least",
                   "slowest": "which one moves the slowest",
                   "youngest": "which one has the smallest age",
                   "shortest": "which one stands the shortest"}[rel[3]]
        question = (f"Of the items listed, {least_q}: {listing}?" if paraphrase
                    else f"Which of these is the {rel[3]}: {listing}?")
    return {
        "premises": premises, "question": question,
        "grammar": {"type": "value_enum", "tokens": list(ents)},
        "gt": gt, "entities": list(ents),
        "sem": {"family": "F1", "extreme": extreme, "rel": rel[0],
                "edges": [list(e) for e in edges], "edit": edit},
    }


# ---------------------------------------------------------------- F2

def build_f2(key: str, names: list, noun: str, depth: int, subform: str,
             paraphrase: bool, edit: Optional[dict] = None) -> dict:
    A, B, C = names[0], names[1], names[2]
    stated: "dict[str,int]" = {}
    mult: "dict[tuple[str,str],int]" = {}
    delta: "dict[tuple[str,str],tuple[int,str]]" = {}
    qkind, thresh = "more", None

    if subform == "yes_no":
        if depth == 1:
            v1 = _ki(key, "v1", 3, 18)
            v2 = _ki(key, "v2", 3, 18)
            while v2 == v1:
                v2 = _ki(key, f"v2:{v2}", 3, 18)
            stated[A], stated[B] = v1, v2
            qkind = "more"
        else:
            v = _ki(key, "v", 3, 9)
            k = _kc(key, "k", [2, 3])
            stated[C] = v
            mult[(B, C)] = k
            if depth == 3:
                mult[(A, B)] = _kc(key, "k2", [2, 3])
            else:
                d = _ki(key, "d", 2, 6)
                s = _kc(key, "sign", ["+", "-"])
                if s == "-" and k * v - d < 1:
                    s = "+"
                delta[(A, B)] = (d, s)
            thresh = _ki(key, "T", 4, 45)
            qkind = "threshold"
    else:
        if depth == 1:
            vals = set()
            i = 0
            while len(vals) < 3:
                vals.add(_ki(key, f"v:x{i}", 2, 20))
                i += 1
            vals = sorted(vals)
            # registered hash-derived assignment permutation (avoids a fixed
            # positional bias of the extremum over the entity slots)
            perms = [(2, 1, 0), (2, 0, 1), (1, 2, 0), (1, 0, 2), (0, 2, 1), (0, 1, 2)]
            pa, pb, pc = perms[_ki(key, "assign", 0, 5)]
            stated[A], stated[B], stated[C] = vals[pa], vals[pb], vals[pc]
            qkind = "most"
        elif depth == 2:
            stated[C] = _ki(key, "v", 4, 14)
            d = _ki(key, "d", 2, 6)
            s = _kc(key, "sign", ["+", "-"])
            delta[(B, C)] = (d, s)
            avoid = {stated[C], stated[C] + d if s == "+" else stated[C] - d}
            av = _ki(key, "av", 2, 25)
            while av in avoid:
                av = _ki(key, f"av:{av}", 2, 25)
            stated[A] = av
            qkind = "most"
        else:
            stated[C] = _ki(key, "v", 3, 8)
            mult[(B, C)] = _kc(key, "k", [2, 3])
            d = _ki(key, "d", 2, 5)
            s = _kc(key, "sign", ["+", "-"])
            delta[(A, B)] = (d, s)
            qkind = "most"

    # ---- apply the single registered edit (V-FLIP search space)
    if edit is not None:
        cls, pi = edit["class"], edit["premise_index"]
        ordered = _f2_premise_order(stated, mult, delta)
        target = ordered[pi]
        if cls == "stated_value_change":
            stated[target[1][0]] = edit["new_value"]
        elif cls == "multiplier_change":
            mult[(target[1][0], target[1][1])] = edit["new_value"]
        elif cls == "delta_change":
            delta[(target[1][0], target[1][1])] = (edit["new_value"][0],
                                                   edit["new_value"][1])
        else:
            raise ValueError(cls)

    # ---- render premises (deterministic order: stated, mult, delta)
    def p_stat(x, v):
        return (f"The {x} {noun} has a capacity of {v} units." if paraphrase
                else f"The {x} {noun} holds {v} units.")

    def p_mult(x, y, k):
        return (f"The {x} {noun}'s unit count is {k} times the {y} {noun}'s."
                if paraphrase else
                f"The {x} {noun} holds {k} times as many units as the {y} {noun}.")

    def p_delta(x, y, d, s):
        word = "more" if s == "+" else "fewer"
        return (f"The {x} {noun} holds {d} units {word} than the {y} {noun} does."
                if paraphrase else
                f"The {x} {noun} holds {d} {word} units than the {y} {noun}.")

    premises = [p_stat(x, v) for x, v in stated.items()] + \
               [p_mult(x, y, k) for (x, y), k in mult.items()] + \
               [p_delta(x, y, d, s) for (x, y), (d, s) in delta.items()]

    ents = [A, B, C]
    if subform == "yes_no":
        av = f2_value(A, stated, mult, delta)
        if qkind == "more":
            bv = f2_value(B, stated, mult, delta)
            gt = "yes" if av > bv else ("no" if av < bv else None)
            question = (f"Is the number of units in the {A} {noun} greater than the "
                        f"number in the {B} {noun}?" if paraphrase else
                        f"Does the {A} {noun} hold more units than the {B} {noun}?")
        else:
            gt = "yes" if av > thresh else ("no" if av < thresh else None)
            question = (f"Is the unit count of the {A} {noun} greater than {thresh}?"
                        if paraphrase else
                        f"Does the {A} {noun} hold more than {thresh} units?")
        grammar = {"type": "yes_no_cannot", "tokens": ["yes", "no", "cannot"]}
    else:
        values = {x: f2_value(x, stated, mult, delta) for x in ents}
        if len(set(values.values())) != 3:
            gt = None
        else:
            gt = max(values, key=lambda x: values[x])
        listing = f"{A}, {B}, or {C}"
        question = (f"Which {noun} holds the most units: {listing}?" if not paraphrase
                    else f"Of these {noun}s, which one holds the greatest number of "
                         f"units: {listing}?")
        grammar = {"type": "value_enum", "tokens": list(ents)}
    return {
        "premises": premises, "question": question, "grammar": grammar,
        "gt": gt, "entities": list(ents),
        "sem": {"family": "F2", "subform": subform, "noun": noun,
                "stated": dict(stated),
                "mult": {f"{x}|{y}": k for (x, y), k in mult.items()},
                "delta": {f"{x}|{y}": [d, s] for (x, y), (d, s) in delta.items()},
                "qkind": qkind, "thresh": thresh, "edit": edit},
    }


def _f2_premise_order(stated, mult, delta):
    """Premise list order (stated, mult, delta) -> [(kind, payload)].

    payload: (entity, value) for stated; (x, y) entity pair for mult/delta.
    """
    order = [("stated", (x, v)) for x, v in stated.items()]
    order += [("mult", key) for key in mult.keys()]
    order += [("delta", key) for key in delta.keys()]
    return order


def _ki(key: str, tag: str, lo: int, hi: int) -> int:
    import hashlib
    n = int.from_bytes(hashlib.sha256(f"{key}::{tag}".encode()).digest(), "big")
    return lo + (n % (hi - lo + 1))


def _kc(key: str, tag: str, seq: list):
    return seq[_ki(key, tag, 0, len(seq) - 1)]


# ---------------------------------------------------------------- F3

def build_f3(key: str, names: list, rel: tuple, depth: int, subform: str,
             paraphrase: bool, edit: Optional[dict] = None) -> dict:
    def prem_pair(a, b):
        return (a, b)

    if subform == "consistency":
        if depth == 1:
            contradictory = _ki(key, "mode", 0, 1) == 1
            if contradictory:
                ents = names[:2]
                pairs = [prem_pair(ents[0], ents[1]), prem_pair(ents[1], ents[0])]
            else:
                ents = names[:3]
                pairs = [prem_pair(ents[0], ents[1]), prem_pair(ents[1], ents[2])]
        elif depth == 2:
            contradictory = _ki(key, "mode", 0, 1) == 1
            ents = names[:3]
            if contradictory:
                pairs = [prem_pair(ents[0], ents[1]), prem_pair(ents[1], ents[2]),
                         prem_pair(ents[2], ents[0])]
            else:
                pairs = [prem_pair(ents[0], ents[1]), prem_pair(ents[1], ents[2])]
        else:
            contradictory = _ki(key, "mode", 0, 1) == 1
            ents = names[:4]
            if contradictory:
                pairs = [prem_pair(ents[i], ents[(i + 1) % 4]) for i in range(4)]
            else:
                pairs = [prem_pair(ents[i], ents[i + 1]) for i in range(3)]
        if edit is not None:
            pi, cls = edit["premise_index"], edit["class"]
            a, b = pairs[pi]
            if cls == "relation_reversal":
                pairs[pi] = (b, a)
            elif cls == "entity_substitution":
                pos, new = edit["position"], edit["new_entity"]
                if pos == "b":
                    pairs[pi] = (a, new)
                else:
                    pairs[pi] = (new, b)
            else:
                raise ValueError(cls)
        edges = [tuple(p) for p in pairs]
        gt = f3_solve(edges)
        if paraphrase:
            premises = [f"The {b} is {rel[2]} than the {a}." for a, b in pairs]
        else:
            premises = [f"The {a} is {rel[0]} than the {b}." for a, b in pairs]
        question = ("Do any of these statements conflict with one another?"
                    if paraphrase else
                    "Do these premises contradict each other?")
        ents_ordered = list(dict.fromkeys([e for p in pairs for e in p]))
        return {
            "premises": premises, "question": question,
            "grammar": {"type": "yes_no_cannot", "tokens": ["yes", "no", "cannot"]},
            "gt": gt, "entities": ents_ordered,
            "sem": {"family": "F3", "subform": "consistency",
                    "edges": [list(e) for e in edges], "edit": edit},
        }

    # underdetermined subform: two disjoint chains + cross-pair question
    n = 2 if depth == 1 else 3
    chain1 = names[:n]
    chain2 = names[n:2 * n]
    pairs = [prem_pair(chain1[i], chain1[i + 1]) for i in range(n - 1)]
    pairs += [prem_pair(chain2[i], chain2[i + 1]) for i in range(n - 1)]
    if edit is not None:
        pi, cls = edit["premise_index"], edit["class"]
        a, b = pairs[pi]
        if cls == "relation_reversal":
            pairs[pi] = (b, a)
        elif cls == "entity_substitution":
            pos, new = edit["position"], edit["new_entity"]
            if pos == "b":
                pairs[pi] = (a, new)
            else:
                pairs[pi] = (new, b)
        else:
            raise ValueError(cls)
    edges = [tuple(p) for p in pairs]
    X, Z = chain1[0], chain2[0]
    gt = f3_solve(edges, X, Z)
    if paraphrase:
        premises = [f"The {b} is {rel[2]} than the {a}." for a, b in pairs]
        question = f"Is the {Z} {rel[2]} than the {X}?"
    else:
        premises = [f"The {a} is {rel[0]} than the {b}." for a, b in pairs]
        question = f"Is the {X} {rel[0]} than the {Z}?"
    return {
        "premises": premises, "question": question,
        "grammar": {"type": "yes_no_cannot", "tokens": ["yes", "no", "cannot"]},
        "gt": gt, "entities": chain1 + chain2,
        "sem": {"family": "F3", "subform": "underdetermined",
                "edges": [list(e) for e in edges], "x": X, "z": Z, "edit": edit},
    }


# ---------------------------------------------------------------- F4

def build_f4(key: str, names: list, fam_names: "tuple[str, str]", attrs: tuple,
             depth: int, paraphrase: bool, edit: Optional[dict] = None) -> dict:
    pos_fam, neg_fam = fam_names
    X = names[0]
    chain = list(attrs[:depth])
    asked = chain[-1]
    x_fam = pos_fam
    if edit is not None and edit["class"] == "instance_family_reassignment":
        x_fam = neg_fam
    gt = f4_solve(pos_fam, neg_fam, chain, x_fam)
    premises = []
    for i, attr in enumerate(chain):
        if i == 0:
            premises.append(f"Each member of the {pos_fam} family is {attr}."
                            if paraphrase else f"Every {pos_fam} is {attr}.")
        else:
            premises.append(f"Every item that is {chain[i - 1]} is also {attr}.")
    premises.append(f"Nothing in the {neg_fam} family is {asked}." if paraphrase
                    else f"No {neg_fam} is {asked}.")
    premises.append(f"The {X} belongs to the {x_fam} family." if paraphrase
                    else f"The {X} is a {x_fam}.")
    question = (f"Does the {X} have the property of being {asked}?" if paraphrase
                else f"Is the {X} {asked}?")
    return {
        "premises": premises, "question": question,
        "grammar": {"type": "yes_no_cannot", "tokens": ["yes", "no", "cannot"]},
        "gt": gt, "entities": [X],
        "sem": {"family": "F4", "pos_fam": pos_fam, "neg_fam": neg_fam,
                "chain": chain, "x": X, "x_fam": x_fam, "depth": depth,
                "edit": edit},
    }
