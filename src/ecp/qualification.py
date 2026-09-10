"""Case Qualification Engine — deterministic four-state gate (M3-CA0 v1).

This module implements the qualification half of the M3-CA0 v1 order: a
deterministic pipeline that answers, per candidate case,

    "Is this authored candidate structurally complete, ground-truth
     verifiable, novel within and across populations, leakage-safe,
     provenance-complete and honestly disclosed enough to be ACCEPTED
     into the qualified candidate pool (still NOT registered)?"

and produces exactly one of four decisions — ``ACCEPT``, ``REVISE``,
``REJECT``, ``INCONCLUSIVE`` — plus a hash-chained qualification artifact
per candidate and a run manifest. Ambiguous ENGINE inputs abort the run
loudly (:class:`InvalidQualificationState`) instead of producing a fifth
state.

Qualification dimensions (order §§5–§11, §15):

- **Q1 identity** — deterministic content hash recomputation;
- **Q2 structural** — the §5 field set present and well-formed (core
  fields vs auxiliary fields distinguished);
- **Q3 ground truth** — MECHANICAL verification of the machine-checkable
  formal layer against the authored ground truth, by one of four finite
  semantics:

  * ``relational-closure``     — forward-chaining closure over facts and
    grounded rules (statement / consistency / repair-count queries);
  * ``propositional-truth-table`` — exhaustive model enumeration for
    implications and facts (statement / consistency / repair-count);
  * ``constraint-enumeration`` — finite-domain assignment enumeration
    (all-different / equals / not-equal / linear / immediately-before);
  * ``default-extensions``     — maximal-consistent default subsets
    (normal-case rules with exceptions; conflicting defaults yield
    multiple extensions and a designed indeterminacy).

  The engine never consults a model: ground truth is established
  independently of any evaluated system (order §6) by deterministic
  computation only. NL-to-formal correspondence is partially checked
  mechanically (symbol coverage) and otherwise author-attested — a
  declared limitation, never a silently assumed one;
- **Q4 novelty N1–N6** — N1 direct retrieval and N2 solution retrieval are
  recorded as honest OPEN questions (external novelty is
  NOT_ESTABLISHABLE_MECHANICALLY without model invocation or retrieval,
  both forbidden at CA0 — the O-01 stance); N3 within-pool duplication via
  structure-abstracted skeletons (entity- and relation-renaming invariant,
  per order §7 "a superficial change of entity names does NOT constitute a
  new case"); N4 cross-population rule replay against a prior candidate
  pool (text-normalized premise/signature overlap; the prior pool carries
  no formal layer, so the cross-check is text-level and says so); N5
  implementation encoding (identifier registry); N6 test-fixture leakage
  (answer-bearing / evaluation-implementation tokens in identifiers);
- **Q5 leakage pre-screen** — the six §8 classes; a CONFIRMED direct
  answer leak (the queried statement present as a premise fact) is
  disqualifying; semantic/solution overlaps are recorded risks;
  model leakage is NOT-APPLICABLE-PRE-EXECUTION with the permanent
  pretraining-exposure declaration (threat model §8.2);
- **Q6 independence** — the §3 authoring-independence record complete,
  with an explicit bounded status label (a bare "INDEPENDENT" claim is
  rejected as an unaudited claim);
- **Q7 representation-bias disclosure** — present per candidate,
  separate from novelty (order §9), uncertainty preserved;
- **Q8 environmental pre-check** — the §10 record present per candidate.

Decision rules (deterministic precedence, recorded in every run manifest):

- REJECT: identity failure; authored ground truth contradicted by the
  mechanical derivation; confirmed direct answer leakage; missing §5 core
  content fields; missing authoring-independence record; exact
  cross-population duplication.
- REVISE: within-pool structural duplication (the later of the pair);
  cross-population replay suspicion; confirmed semantic/solution leakage
  overlap; missing auxiliary §5 fields or disclosure blocks; malformed
  formal-layer shapes.
- INCONCLUSIVE: ground truth not mechanically verifiable (formal layer
  absent) — the honest "cannot qualify now", never forced into ACCEPT.
- ACCEPT: none of the above; open risk questions (N1/N2, pretraining
  exposure) remain recorded, non-blocking.

The engine is a pure function of (candidates, run metadata, prior
population content): no wall-clock, no randomness, no network, no model
calls. ``qualify-verify`` re-derives every artifact and the run manifest
bit-identically from retained inputs.
"""

import itertools
import json
import re

from .canonical import canonical_bytes
from .candidates import normalize_text, normalize_tokens
from .hashing import hash_document, hash_document_excluding
from .validate import validate_document
from .versions import version_issues

ENGINE_ID = "ECP-QUALIFICATION-ENGINE-1"
ENGINE_VERSION = "0.5.0"

#: Engine behavior profiles (mirrors the review-engine convention). Profile
#: 0.5.0 is the initial qualification-engine behavior set.
ENGINE_PROFILES = ("0.5.0",)

#: Decision states (order §11) — exactly four, no fifth state.
QUALIFICATION_STATES = ("ACCEPT", "REVISE", "REJECT", "INCONCLUSIVE")

#: Ground-truth classes (order §6.4).
GT_CLASSES = ("DERIVABLE", "CONTRADICTED", "IMPOSSIBLE", "INDETERMINATE")

#: Supported formal semantics.
SEMANTICS = (
    "relational-closure",
    "propositional-truth-table",
    "constraint-enumeration",
    "default-extensions",
)

#: Deterministic engine parameters (recorded in every run manifest).
WITHIN_POOL_SKELETON = "exact-structure-abstracted"
CROSS_POP_JACCARD_THRESHOLD = 0.5
SEMANTIC_ANSWER_JACCARD_THRESHOLD = 0.8
SOLUTION_CONTAINMENT_MIN_TOKENS = 6
ANSWER_CORE_MIN_TOKENS = 4

#: Numeric words 0..20 for prose-value agreement checks.
_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

#: N5/N6 identifier registry: evaluation-implementation and answer-bearing
#: tokens that must NOT appear inside case identifiers (entities, relations,
#: propositions, variables) or NL content.
IMPLEMENTATION_TOKENS = (
    "ecp", "jarvis", "candidate", "qualif", "registration", "register",
    "execut", "benchmark", "fixture", "score", "evaluat", "groundtruth",
    "ground_truth", "leakage", "adjudicat", "amendment", "review",
)
ANSWER_BEARING_TOKENS = (
    "answer", "solution", "correct", "expected", "gt_", "groundtruth",
    "derivable", "contradicted", "impossible", "indeterminate",
    "verdict", "label", "truth",
)
_PATH_TOKENS = (".py", ".json", ".md", "ECP-", "src/", "tools/", "schemas/")


class QualificationError(Exception):
    """Raised when a qualification run cannot proceed honestly (bad
    inputs, malformed records — always loud, never silent)."""


class InvalidQualificationState(QualificationError):
    """Raised when the engine would need a fifth decision state or receives
    out-of-enum input (fail-loud guard)."""


# ---------------------------------------------------------------------------
# Ground-truth verification backends
# ---------------------------------------------------------------------------


def _atom_key(relation: str, args: "list[str]") -> tuple:
    return (relation, tuple(args))


def _closure_relational(entities: "list[str]", premises: "list[dict]") -> dict:
    """Forward-chaining closure over relational facts and grounded rules.

    Returns ``{facts, trace, conflicts}`` where ``facts`` maps
    ``(relation, args) -> bool`` (True = asserted, False = explicitly
    negated), ``trace`` records every derivation step with justification,
    and ``conflicts`` lists atoms asserted both ways.
    """
    facts: "dict[tuple, bool]" = {}
    trace: "list[dict]" = []
    conflicts: "list[tuple]" = []
    rules: "list[dict]" = []

    def _assert(key: tuple, value: bool, justification: dict):
        if key in facts:
            if facts[key] != value and key not in conflicts:
                conflicts.append(key)
            return
        facts[key] = value
        trace.append({"atom": [key[0], list(key[1])], "value": value, "justification": justification})

    for index, premise in enumerate(premises):
        if premise.get("kind") == "rel_fact":
            _assert(
                _atom_key(premise["relation"], premise["args"]),
                not premise.get("negated", False),
                {"type": "premise", "premise_index": index},
            )
        elif premise.get("kind") == "rel_rule":
            rules.append((index, premise))
        else:
            raise InvalidQualificationState(
                f"relational-closure: premise {index} has unsupported kind {premise.get('kind')!r}"
            )

    # ground rules over the finite entity domain
    ground_rules: "list[tuple[int, list[tuple[tuple, bool]], tuple, bool]]" = []
    for rule_index, rule in rules:
        variables = rule.get("vars", [])
        for assignment in itertools.product(entities, repeat=len(variables)):
            binding = dict(zip(variables, assignment))
            if_atoms = []
            ok = True
            for cond in rule["if"]:
                args = tuple(binding.get(a, a) for a in cond["args"])
                if any(a not in entities and a not in binding for a in args):
                    ok = False
                    break
                if_atoms.append((_atom_key(cond["relation"], list(args)), not cond.get("negated", False)))
            if not ok:
                continue
            then = rule["then"]
            then_args = tuple(binding.get(a, a) for a in then["args"])
            if any(a not in entities for a in then_args):
                continue
            ground_rules.append(
                (rule_index, if_atoms, _atom_key(then["relation"], list(then_args)), not then.get("negated", False))
            )

    changed = True
    while changed:
        changed = False
        for rule_index, if_atoms, then_key, then_value in ground_rules:
            if all(facts.get(key) == value for key, value in if_atoms):
                existing = facts.get(then_key)
                if existing is None:
                    _assert(
                        then_key,
                        then_value,
                        {"type": "rule", "rule_index": rule_index, "from": [[k[0], list(k[1])] for k, _ in if_atoms]},
                    )
                    changed = True
                elif existing != then_value and then_key not in conflicts:
                    # the rule fires onto an atom already asserted the other
                    # way: a genuine closure conflict (recorded, never skipped)
                    conflicts.append(then_key)

    return {"facts": facts, "trace": trace, "conflicts": conflicts}


def _query_trace_relational(facts: "dict[tuple, bool]", trace: "list[dict]", key: tuple) -> "list[dict]":
    """Walk the justification DAG backwards from *key* (best-effort compact
    trace for the artifact; the full trace is already deterministic)."""
    steps = {json.dumps([step["atom"][0], step["atom"][1]]): step for step in trace}
    target = json.dumps([key[0], list(key[1])])
    if target not in steps:
        return []
    out: "list[dict]" = []
    stack = [steps[target]]
    seen = set()
    while stack:
        step = stack.pop()
        marker = json.dumps([step["atom"][0], step["atom"][1]])
        if marker in seen:
            continue
        seen.add(marker)
        out.append(step)
        just = step.get("justification", {})
        if just.get("type") == "rule":
            for atom in just.get("from", []):
                marker2 = json.dumps([atom[0], atom[1]])
                if marker2 in steps:
                    stack.append(steps[marker2])
    out.reverse()
    return out


def verify_relational_closure(formal: dict) -> dict:
    """Verify a relational-closure formal layer against its query.

    Query kinds: statement (``{relation, args}``), ``consistency``, and
    ``repair_count`` (single-premise removals that restore consistency).
    """
    entities = formal.get("entities", [])
    premises = formal.get("premises", [])
    if not entities:
        raise InvalidQualificationState("relational-closure: no entities declared")
    closure = _closure_relational(entities, premises)
    query = formal.get("query", {})

    if query.get("kind") == "consistency":
        derived = "CONTRADICTED" if closure["conflicts"] else "DERIVABLE"
        return {
            "derived_class": derived,
            "method": "relational-closure-consistency",
            "value": None,
            "conflicts": [[c[0], list(c[1])] for c in closure["conflicts"]],
            "closure_size": len(closure["facts"]),
            "trace": closure["trace"][-12:],
        }

    if query.get("kind") == "repair_count":
        count = 0
        removals = []
        for i in range(len(premises)):
            reduced = [p for j, p in enumerate(premises) if j != i]
            sub = _closure_relational(entities, reduced)
            if not sub["conflicts"]:
                count += 1
                removals.append(i + 1)
        return {
            "derived_class": "DERIVABLE",
            "method": "relational-closure-repair-count",
            "value": count,
            "removals": removals,
            "closure_size": len(closure["facts"]),
            "trace": closure["trace"][-12:],
        }

    key = _atom_key(query["relation"], query["args"])
    if any(a not in entities for a in query.get("args", [])):
        raise InvalidQualificationState(
            f"relational-closure: query references undeclared entity {query['args']!r}"
        )
    value = closure["facts"].get(key)
    if key in closure["conflicts"]:
        return {
            "derived_class": None,
            "status_note": "PREMISES-INCONSISTENT-WRT-QUERY (statement query on a conflicted atom)",
            "method": "relational-closure-statement",
            "value": None,
            "closure_size": len(closure["facts"]),
            "trace": _query_trace_relational(closure["facts"], closure["trace"], key),
        }
    derived = {True: "DERIVABLE", False: "CONTRADICTED", None: "INDETERMINATE"}[value]
    return {
        "derived_class": derived,
        "method": "relational-closure-statement",
        "value": None,
        "closure_size": len(closure["facts"]),
        "trace": _query_trace_relational(closure["facts"], closure["trace"], key),
    }


def _propositional_models(props: "list[str]", premises: "list[dict]") -> "list[dict]":
    """All assignments (as prop->bool maps) satisfying the premises."""
    models = []
    for values in itertools.product((True, False), repeat=len(props)):
        assignment = dict(zip(props, values))
        if all(_prop_premise_holds(premise, assignment) for premise in premises):
            models.append(assignment)
    return models


def _prop_premise_holds(premise: dict, assignment: "dict[str, bool]") -> bool:
    kind = premise.get("kind")
    if kind == "prop_fact":
        return assignment.get(premise["prop"]) == premise.get("value", True)
    if kind == "impl":
        if all(assignment.get(p) is True for p in premise.get("if", [])):
            return assignment.get(premise["then"]) == premise.get("then_value", True)
        return True
    raise InvalidQualificationState(
        f"propositional-truth-table: premise kind {kind!r} unsupported"
    )


def verify_propositional(formal: dict) -> dict:
    """Verify a propositional formal layer by exhaustive model enumeration."""
    props = formal.get("props", [])
    premises = formal.get("premises", [])
    for premise in premises:
        if premise.get("kind") == "prop_fact" and premise["prop"] not in props:
            raise InvalidQualificationState(
                f"propositional: fact references undeclared prop {premise['prop']!r}"
            )
        if premise.get("kind") == "impl":
            for p in premise.get("if", []) + [premise["then"]]:
                if p not in props:
                    raise InvalidQualificationState(
                        f"propositional: implication references undeclared prop {p!r}"
                    )
    models = _propositional_models(props, premises)
    query = formal.get("query", {})

    if query.get("kind") == "consistency":
        derived = "DERIVABLE" if models else "CONTRADICTED"
        return {
            "derived_class": derived,
            "method": "propositional-truth-table-consistency",
            "value": None,
            "model_count": len(models),
            "prop_count": len(props),
            "trace": [{"model_count": len(models), "total_assignments": 2 ** len(props)}],
        }

    if query.get("kind") == "repair_count":
        count = 0
        removals = []
        for i in range(len(premises)):
            reduced = [p for j, p in enumerate(premises) if j != i]
            if _propositional_models(props, reduced):
                count += 1
                removals.append(i + 1)
        return {
            "derived_class": "DERIVABLE",
            "method": "propositional-truth-table-repair-count",
            "value": count,
            "removals": removals,
            "model_count": len(models),
            "trace": [{"model_count": len(models), "removals": removals}],
        }

    if not models:
        return {
            "derived_class": None,
            "status_note": "PREMISES-INCONSISTENT (statement query on unsatisfiable premises)",
            "method": "propositional-truth-table-statement",
            "value": None,
            "model_count": 0,
            "trace": [],
        }
    want = query.get("value", True)
    prop = query.get("prop")
    if prop not in props:
        raise InvalidQualificationState(
            f"propositional: query references undeclared prop {prop!r}"
        )
    truth = [m[prop] for m in models]
    if all(t == want for t in truth):
        derived = "DERIVABLE"
    elif all(t != want for t in truth):
        derived = "CONTRADICTED"
    else:
        derived = "INDETERMINATE"
    return {
        "derived_class": derived,
        "method": "propositional-truth-table-statement",
        "value": None,
        "model_count": len(models),
        "prop_count": len(props),
        "trace": [
            {"model_count": len(models), "total_assignments": 2 ** len(props)},
            {"query_true_in": sum(1 for t in truth if t == want), "query_false_in": sum(1 for t in truth if t != want)},
        ],
    }


def _eval_linear(expr: str, assignment: "dict[str, object]") -> "float | None":
    """Evaluate a whitelisted linear expression ``lhs = rhs`` under an
    assignment. Supports +, -, * over variable names and int constants."""
    import ast

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in assignment:
                raise ValueError(f"undeclared variable {node.id!r} in linear expression")
            return assignment[node.id]
        if isinstance(node, ast.BinOp):
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
        raise ValueError(f"unsupported expression element {ast.dump(node)}")

    left, _, right = expr.partition("=")
    if not right:
        raise ValueError(f"linear expression missing '=': {expr!r}")
    try:
        return _eval(ast.parse(left.strip(), mode="eval")) - _eval(ast.parse(right.strip(), mode="eval"))
    except (ValueError, SyntaxError) as exc:
        raise InvalidQualificationState(f"linear constraint {expr!r}: {exc}") from exc


def _domain_values(spec) -> "list":
    if isinstance(spec, dict) and "range" in spec:
        lo, hi = spec["range"]
        return list(range(lo, hi + 1))
    if isinstance(spec, dict) and "values" in spec:
        return list(spec["values"])
    if isinstance(spec, list):
        if len(spec) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in spec):
            # documented convention: a bare [lo, hi] integer pair is an
            # inclusive range; any other list is an explicit value list
            return list(range(spec[0], spec[1] + 1))
        return list(spec)
    raise InvalidQualificationState(f"constraint domain spec not understood: {spec!r}")


def _constraint_holds(constraint: dict, assignment: "dict[str, object]") -> bool:
    import ast

    kind = constraint.get("kind")
    if kind == "all_different":
        values = [assignment[v] for v in constraint["vars"]]
        return len(set(values)) == len(values)
    if kind == "equals":
        return assignment[constraint["var"]] == constraint["value"]
    if kind == "not_equal":
        return assignment[constraint["var"]] != constraint["value"]
    if kind == "linear":
        return _eval_linear(constraint["expr"], assignment) == 0
    if kind == "immediately_before":
        a, b = constraint["a"], constraint["b"]
        return assignment[b] == assignment[a] + 1
    raise InvalidQualificationState(f"constraint kind {kind!r} unsupported")


def verify_constraint_enumeration(formal: dict) -> dict:
    """Verify a constraint formal layer by exhaustive enumeration."""
    variables = formal.get("variables", [])
    domains = formal.get("domains", {})
    premises = formal.get("premises", [])
    if not variables or set(domains) != set(variables):
        raise InvalidQualificationState(
            "constraint-enumeration: variables and domains do not match"
        )
    value_lists = [_domain_values(domains[v]) for v in variables]
    total_space = 1
    for values in value_lists:
        total_space *= len(values)
    if total_space > 200000:
        raise InvalidQualificationState(
            f"constraint-enumeration: search space {total_space} exceeds the 200000 cap"
        )

    solutions = []
    for combo in itertools.product(*value_lists):
        assignment = dict(zip(variables, combo))
        if all(_constraint_holds(c, assignment) for c in premises):
            solutions.append(assignment)

    query = formal.get("query", {})
    kind = query.get("kind")
    if kind == "solution_exists":
        derived = "DERIVABLE" if solutions else "IMPOSSIBLE"
        return {
            "derived_class": derived,
            "method": "constraint-enumeration-solution-existence",
            "value": len(solutions),
            "solution_count": len(solutions),
            "search_space": total_space,
            "trace": [{"search_space": total_space, "solution_count": len(solutions)}],
        }
    if not solutions:
        return {
            "derived_class": "IMPOSSIBLE",
            "method": f"constraint-enumeration-{kind}",
            "value": None,
            "solution_count": 0,
            "search_space": total_space,
            "trace": [{"search_space": total_space, "solution_count": 0}],
        }
    if kind == "value_of":
        var = query["var"]
        distinct = {s[var] for s in solutions}
        if len(distinct) == 1:
            value = next(iter(distinct))
            return {
                "derived_class": "DERIVABLE",
                "method": "constraint-enumeration-value-of",
                "value": value,
                "solution_count": len(solutions),
                "search_space": total_space,
                "trace": [{"search_space": total_space, "solution_count": len(solutions), "unique_value": value}],
            }
        return {
            "derived_class": "INDETERMINATE",
            "method": "constraint-enumeration-value-of",
            "value": sorted(distinct, key=str),
            "solution_count": len(solutions),
            "search_space": total_space,
            "trace": [{"search_space": total_space, "solution_count": len(solutions), "values": sorted(map(str, distinct))}],
        }
    if kind == "truth_of":
        var, want = query["var"], query["value"]
        holds = [s[var] == want for s in solutions]
        if all(holds):
            derived = "DERIVABLE"
        elif not any(holds):
            derived = "CONTRADICTED"
        else:
            derived = "INDETERMINATE"
        return {
            "derived_class": derived,
            "method": "constraint-enumeration-truth-of",
            "value": None,
            "solution_count": len(solutions),
            "search_space": total_space,
            "trace": [
                {"search_space": total_space, "solution_count": len(solutions)},
                {"holds_in": sum(1 for h in holds if h), "fails_in": sum(1 for h in holds if not h)},
            ],
        }
    raise InvalidQualificationState(f"constraint query kind {kind!r} unsupported")


def _strict_entailed(props: "list[str]", strict: "list[dict]") -> "dict[str, bool]":
    """Props entailed true/false by the strict premises (truth-table)."""
    models = _propositional_models(props, strict)
    entailed: "dict[str, bool]" = {}
    if not models:
        return {p: True for p in props}  # vacuous under inconsistency; callers detect
    for prop in props:
        values = {m[prop] for m in models}
        if values == {True}:
            entailed[prop] = True
        elif values == {False}:
            entailed[prop] = False
    return entailed


def verify_default_extensions(formal: dict) -> dict:
    """Verify a default-extensions formal layer.

    Semantics (deterministic): strict premises (prop_fact / impl) are
    evaluated by truth-table; each subset T of defaults is simulated in
    listed order — a default in T is active iff its conditions hold in
    (strict-entailed ∪ earlier-active conclusions in T), no unless-condition
    holds there with matching value, and T's accumulated conclusions stay
    conflict-free. T's conclusion set must be internally consistent and
    consistent with the strict facts. Extensions are the maximal valid
    conclusion sets. The query is evaluated across extensions: universal
    agreement yields DERIVABLE/CONTRADICTED; disagreement (including a
    designed two-extension ambiguity) yields INDETERMINATE.
    """
    props = formal.get("props", [])
    premises = formal.get("premises", [])
    strict = [p for p in premises if p.get("kind") in ("prop_fact", "impl")]
    defaults = [p for p in premises if p.get("kind") == "default"]
    for p in premises:
        if p.get("kind") not in ("prop_fact", "impl", "default"):
            raise InvalidQualificationState(f"defaults: premise kind {p.get('kind')!r} unsupported")

    strict_models = _propositional_models(props, strict)
    if not strict_models:
        return {
            "derived_class": None,
            "status_note": "PREMISES-INCONSISTENT (strict part unsatisfiable)",
            "method": "default-extensions",
            "value": None,
            "trace": [],
        }
    entailed = _strict_entailed(props, strict)

    def _cond_holds(cond: dict, conclusions: "dict[str, bool]") -> bool:
        return conclusions.get(cond["prop"]) == cond.get("value", True)

    valid_sets: "list[frozenset]" = []
    for mask in range(2 ** len(defaults)):
        subset = [defaults[i] for i in range(len(defaults)) if mask >> i & 1]
        conclusions: "dict[str, bool]" = dict(entailed)
        active: "list[int]" = []
        consistent = True
        for index, default in enumerate(subset):
            conditions_ok = all(
                _cond_holds(cond, conclusions) for cond in default.get("if", [])
            )
            unless_blocked = any(
                _cond_holds(unless, conclusions) for unless in default.get("unless", [])
            )
            if not conditions_ok or unless_blocked:
                continue
            normally = default["normally"]
            prop, value = normally["prop"], normally.get("value", True)
            if prop in conclusions and conclusions[prop] != value:
                consistent = False
                break
            conclusions[prop] = value
            active.append(index)
        if not consistent:
            continue
        if any(conclusions.get(p) is None for p in props if _prop_referenced(p, premises)):
            pass
        valid_sets.append(frozenset((p, v) for p, v in conclusions.items() if v is not None))

    # maximal valid conclusion sets
    extensions = []
    for candidate_set in valid_sets:
        if any(candidate_set < other for other in valid_sets):
            continue
        if candidate_set not in extensions:
            extensions.append(candidate_set)
    if not extensions:
        return {
            "derived_class": None,
            "status_note": "NO-VALID-EXTENSION (all default subsets inconsistent with strict facts)",
            "method": "default-extensions",
            "value": None,
            "trace": [],
        }

    query = formal.get("query", {})
    prop = query.get("prop")
    want = query.get("value", True)
    if prop not in props:
        raise InvalidQualificationState(f"defaults: query references undeclared prop {prop!r}")
    answers = set()
    for ext in extensions:
        values = {p: v for p, v in ext}
        if prop not in values:
            answers.add("ABSENT")
        elif values[prop] == want:
            answers.add("TRUE")
        else:
            answers.add("FALSE")
    if answers == {"TRUE"}:
        derived = "DERIVABLE"
    elif answers == {"FALSE"}:
        derived = "CONTRADICTED"
    else:
        derived = "INDETERMINATE"
    return {
        "derived_class": derived,
        "method": "default-extensions",
        "value": None,
        "extension_count": len(extensions),
        "extension_solutions": [
            [{"prop": p, "value": v} for p, v in sorted(ext)] for ext in sorted(extensions)
        ][:4],
        "trace": [
            {"strict_models": len(strict_models), "defaults": len(defaults), "extensions": len(extensions)},
            {"query_answers": sorted(answers)},
        ],
    }


def _prop_referenced(prop: str, premises: "list[dict]") -> bool:
    for premise in premises:
        if premise.get("kind") == "prop_fact" and premise.get("prop") == prop:
            return True
        if premise.get("kind") == "impl" and (
            prop in premise.get("if", []) or prop == premise.get("then")
        ):
            return True
        if premise.get("kind") == "default":
            if prop == premise.get("normally", {}).get("prop"):
                return True
            if any(c.get("prop") == prop for c in premise.get("if", []) + premise.get("unless", [])):
                return True
    return False


_VERIFIERS = {
    "relational-closure": verify_relational_closure,
    "propositional-truth-table": verify_propositional,
    "constraint-enumeration": verify_constraint_enumeration,
    "default-extensions": verify_default_extensions,
}


def verify_ground_truth(formal: dict) -> dict:
    """Dispatch the formal layer to its verification backend."""
    semantics = formal.get("semantics")
    if semantics not in _VERIFIERS:
        return {
            "derived_class": None,
            "status_note": f"UNVERIFIABLE (unknown semantics {semantics!r})",
            "method": "none",
            "value": None,
            "trace": [],
        }
    try:
        return _VERIFIERS[semantics](formal)
    except InvalidQualificationState as exc:
        return {
            "derived_class": None,
            "status_note": f"MALFORMED ({exc})",
            "method": semantics,
            "value": None,
            "trace": [],
        }


# ---------------------------------------------------------------------------
# Structural skeletons (novelty N3) — renaming-invariant abstraction
# ---------------------------------------------------------------------------


def _canonical_indices(tokens: "list[str]") -> "dict[str, int]":
    indices: "dict[str, int]" = {}
    for token in tokens:
        if token not in indices:
            indices[token] = len(indices)
    return indices


def structural_skeleton(candidate: dict) -> "str | None":
    """Renaming-invariant structural skeleton hash, or None when the
    formal layer is absent (skeleton novelty then not computable)."""
    content = candidate.get("content", {})
    formal = content.get("formal")
    if not isinstance(formal, dict):
        return None
    family = normalize_text(content.get("proposed_reasoning_family", ""))
    semantics = formal.get("semantics")

    if semantics == "relational-closure":
        entities: "list[str]" = []
        for fact in formal.get("premises", []):
            if fact.get("kind") == "rel_fact":
                entities.extend(a for a in fact["args"] if a not in entities)
        query = formal.get("query", {})
        for arg in query.get("args", []):
            if arg not in entities:
                entities.append(arg)
        ent_idx = _canonical_indices(entities)
        relations: "list[str]" = []
        for premise in formal.get("premises", []):
            for atom in ([premise] if premise.get("kind") == "rel_fact" else premise.get("if", []) + [premise.get("then", {})]):
                if atom and atom.get("relation") and atom["relation"] not in relations:
                    relations.append(atom["relation"])
        if query.get("relation") and query["relation"] not in relations:
            relations.append(query["relation"])
        rel_idx = _canonical_indices(relations)

        facts_pattern = sorted(
            (
                rel_idx[fact["relation"]],
                tuple(ent_idx[a] for a in fact["args"]),
                not fact.get("negated", False),
            )
            for fact in formal.get("premises", [])
            if fact.get("kind") == "rel_fact"
        )
        rules_pattern = sorted(
            (
                len(rule.get("vars", [])),
                tuple(sorted(
                    (
                        rel_idx[cond["relation"]],
                        tuple(
                            rule.get("vars", []).index(a) if a in rule.get("vars", [])
                            else len(rule.get("vars", [])) + ent_idx[a]
                            for a in cond["args"]
                        ),
                    )
                    for cond in rule.get("if", [])
                )),
                (
                    rel_idx[rule["then"]["relation"]],
                    tuple(
                        rule.get("vars", []).index(a) if a in rule.get("vars", [])
                        else len(rule.get("vars", [])) + ent_idx[a]
                        for a in rule["then"]["args"]
                    ),
                ),
                not rule["then"].get("negated", False),
            )
            for rule in formal.get("premises", [])
            if rule.get("kind") == "rel_rule"
        )
        if query.get("kind") == "consistency":
            query_pattern = ("consistency",)
        elif query.get("kind") == "repair_count":
            query_pattern = ("repair_count",)
        elif query.get("relation"):
            query_pattern = (
                "statement",
                rel_idx[query["relation"]],
                tuple(ent_idx[a] for a in query.get("args", [])),
            )
        else:
            return None
        structure = [family, semantics, facts_pattern, rules_pattern, query_pattern]

    elif semantics == "propositional-truth-table":
        props: "list[str]" = []
        for premise in formal.get("premises", []):
            for token in premise.get("if", []) + [premise.get("then")]:
                if token and token not in props:
                    props.append(token)
            if premise.get("kind") == "prop_fact" and premise.get("prop") not in props:
                props.append(premise["prop"])
        query = formal.get("query", {})
        if query.get("prop") and query["prop"] not in props:
            props.append(query["prop"])
        prop_idx = _canonical_indices(props)
        impls = sorted(
            (
                tuple(sorted(prop_idx[p] for p in premise.get("if", []))),
                prop_idx[premise["then"]],
                premise.get("then_value", True),
            )
            for premise in formal.get("premises", [])
            if premise.get("kind") == "impl"
        )
        facts = sorted(
            (prop_idx[premise["prop"]], premise.get("value", True))
            for premise in formal.get("premises", [])
            if premise.get("kind") == "prop_fact"
        )
        if query.get("kind") == "consistency":
            query_pattern = ("consistency",)
        elif query.get("kind") == "repair_count":
            query_pattern = ("repair_count",)
        elif query.get("prop"):
            query_pattern = ("statement", prop_idx[query["prop"]], query.get("value", True))
        else:
            return None
        structure = [family, semantics, impls, facts, query_pattern]

    elif semantics == "constraint-enumeration":
        variables = formal.get("variables", [])
        domains = formal.get("domains", {})
        sizes = sorted(len(_domain_values(domains.get(v, []))) for v in variables)
        constraints = sorted(
            (
                premise.get("kind"),
                len(premise.get("vars", premise.get("if", []))) if premise.get("kind") == "all_different" else 1,
            )
            for premise in formal.get("premises", [])
        )
        query = formal.get("query", {})
        query_pattern = query.get("kind", "statement")
        structure = [family, semantics, len(variables), sizes, constraints, query_pattern]

    elif semantics == "default-extensions":
        props: "list[str]" = []

        def _note_prop(token):
            if isinstance(token, str) and token and token not in props:
                props.append(token)

        for premise in formal.get("premises", []):
            kind = premise.get("kind")
            if kind == "prop_fact":
                _note_prop(premise.get("prop"))
            elif kind == "impl":
                for token in premise.get("if", []):
                    _note_prop(token)
                _note_prop(premise.get("then"))
            elif kind == "default":
                _note_prop(premise.get("normally", {}).get("prop"))
                for cond in premise.get("if", []) + premise.get("unless", []):
                    if isinstance(cond, dict):
                        _note_prop(cond.get("prop"))
        query = formal.get("query", {})
        _note_prop(query.get("prop"))
        prop_idx = _canonical_indices(props)
        strict = sorted(
            (prop_idx[premise["prop"]], premise.get("value", True))
            for premise in formal.get("premises", [])
            if premise.get("kind") == "prop_fact"
        )
        defaults = sorted(
            (
                tuple(sorted((prop_idx[c["prop"]] for c in premise.get("if", [])))),
                prop_idx[premise["normally"]["prop"]],
                premise["normally"].get("value", True),
                tuple(sorted((prop_idx[u["prop"]] for u in premise.get("unless", [])))),
            )
            for premise in formal.get("premises", [])
            if premise.get("kind") == "default"
        )
        query_pattern = ("statement", prop_idx[query["prop"]], query.get("value", True)) if query.get("prop") else None
        if query_pattern is None:
            return None
        structure = [family, semantics, strict, defaults, query_pattern]

    else:
        return None

    return hash_document({"structure": structure})


# ---------------------------------------------------------------------------
# Leakage helpers
# ---------------------------------------------------------------------------


def _answer_core(answer_text: str) -> "list[str]":
    """Normalized answer tokens with yes/no/abstention boilerplate stripped."""
    tokens = normalize_tokens(answer_text)
    strip_prefixes = ("yes", "no", "cannot", "be", "determined", "the", "a")
    core: "list[str]" = []
    skipped = True
    for token in tokens:
        if skipped and token in strip_prefixes and len(core) == 0:
            continue
        skipped = False
        core.append(token)
    while core and core[-1] in strip_prefixes:
        core.pop()
    return core


def _normalized_contiguous(needle: "list[str]", haystack: "list[str]") -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    window = len(needle)
    return any(haystack[i:i + window] == needle for i in range(len(haystack) - window + 1))


def _jaccard(a: "list[str]", b: "list[str]") -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb)


def _identifier_issues(candidate: dict) -> "list[str]":
    """N5/N6 registry checks over formal symbols, ids and NL text."""
    content = candidate.get("content", {})
    formal = content.get("formal") or {}
    issues: "list[str]" = []

    identifiers: "list[tuple[str, str]]" = [
        ("case_id", candidate.get("source", {}).get("case_id", "")),
        ("family", content.get("proposed_reasoning_family", "")),
    ]
    semantics = formal.get("semantics")
    if semantics == "relational-closure":
        for entity in formal.get("entities", []):
            identifiers.append(("entity", entity))
        relations = set()
        for premise in formal.get("premises", []):
            if premise.get("kind") == "rel_fact":
                relations.add(premise["relation"])
            elif premise.get("kind") == "rel_rule":
                relations.add(premise["then"]["relation"])
                for cond in premise.get("if", []):
                    relations.add(cond["relation"])
        for relation in relations:
            identifiers.append(("relation", relation))
    elif semantics == "propositional-truth-table":
        for prop in formal.get("props", []):
            identifiers.append(("prop", prop))
    elif semantics == "constraint-enumeration":
        for variable in formal.get("variables", []):
            identifiers.append(("variable", variable))
    elif semantics == "default-extensions":
        for prop in formal.get("props", []):
            identifiers.append(("prop", prop))

    # N5/N6 registry scan over CASE-CONTENT identifiers (entities, relations,
    # props, variables, source case_id, family). The protocol-layer
    # candidate_id (ECP-CAND-...) is NOT case content and is excluded.
    for label, value in identifiers:
        lowered = normalize_text(str(value))
        for token in IMPLEMENTATION_TOKENS:
            if token in lowered:
                issues.append(f"N5: {label} {value!r} contains implementation token {token!r}")
        for token in ANSWER_BEARING_TOKENS:
            if token in lowered and label not in ("family",):
                issues.append(f"N6: {label} {value!r} contains answer-bearing token {token!r}")
        for token in _PATH_TOKENS:
            if token in str(value):
                issues.append(f"N5: {label} {value!r} contains path/extension token {token!r}")

    task_text = normalize_text(
        " ".join(content.get("premises", [])) + " " + content.get("question", "")
    )
    for token in _PATH_TOKENS:
        if token in task_text:
            issues.append(f"N5: task text contains implementation token {token!r}")

    return issues


# ---------------------------------------------------------------------------
# Per-candidate qualification
# ---------------------------------------------------------------------------


def _empty_dimensions() -> dict:
    return {
        "identity": {"status": "PENDING"},
        "structural": {"status": "PENDING", "findings": []},
        "ground_truth": {"status": "PENDING", "findings": []},
        "novelty": {"status": "PENDING", "findings": []},
        "leakage": {"status": "PENDING", "findings": []},
        "independence": {"status": "PENDING", "findings": []},
        "representation_bias": {"status": "PENDING", "findings": []},
        "environmental_pre_check": {"status": "PENDING", "findings": []},
    }


def _symbol_coverage_issues(candidate: dict) -> "list[str]":
    """Partial mechanical NL-to-formal correspondence: every declared formal
    symbol (entities, relations, props and their underscore parts,
    variables, domain values) must appear in the NL task text."""
    content = candidate.get("content", {})
    formal = content.get("formal") or {}
    task_tokens = set(
        normalize_tokens(
            " ".join(content.get("premises", [])) + " " + content.get("question", "")
        )
    )
    issues: "list[str]" = []
    semantics = formal.get("semantics")

    def _check(symbol: str, label: str):
        parts = [p for p in str(symbol).split("_") if p]
        missing = [p for p in parts if p not in task_tokens]
        if missing:
            issues.append(
                f"correspondence: {label} {symbol!r} not covered by task text (missing parts {missing})"
            )

    if semantics == "relational-closure":
        for entity in formal.get("entities", []):
            _check(entity, "entity")
        relations = set()
        for premise in formal.get("premises", []):
            if premise.get("kind") == "rel_fact":
                relations.add(premise["relation"])
            elif premise.get("kind") == "rel_rule":
                relations.add(premise["then"]["relation"])
                for cond in premise.get("if", []):
                    relations.add(cond["relation"])
        for relation in relations:
            _check(relation, "relation")
    elif semantics == "propositional-truth-table":
        for prop in formal.get("props", []):
            _check(prop, "prop")
    elif semantics == "constraint-enumeration":
        for variable in formal.get("variables", []):
            _check(variable, "variable")
        for var, spec in (formal.get("domains") or {}).items():
            for value in _domain_values(spec):
                if str(value) not in task_tokens:
                    issues.append(
                        f"correspondence: domain value {value!r} of {var!r} not covered by task text"
                    )
    elif semantics == "default-extensions":
        for prop in formal.get("props", []):
            _check(prop, "prop")
    return issues


def _value_agrees(derived_value, candidate: dict) -> "bool | None":
    """Mechanical prose-value agreement: the derived value must appear in the
    authored answer or GT statement (digit or number word)."""
    content = candidate.get("content", {})
    answer = " ".join(a.get("value", "") for a in content.get("intended_correct_answers", []))
    gt_statement = (content.get("ground_truth") or {}).get("statement", "")
    hay = normalize_text(answer + " " + gt_statement)
    tokens = set(hay.split())
    if isinstance(derived_value, bool):
        return None
    if isinstance(derived_value, (int, float)):
        candidates_str = {str(derived_value)}
        for word, number in _NUMBER_WORDS.items():
            if number == derived_value:
                candidates_str.add(word)
        return bool(candidates_str & tokens) or None
    if isinstance(derived_value, str):
        return (normalize_text(derived_value) in hay) or None
    if isinstance(derived_value, list):
        return None
    return None


def qualify_candidate(
    candidate: dict,
    prior_in_pool: "list[dict]",
    prior_population: "list[dict]",
    run_id: str,
    qualified_at: str,
    operator: str,
    entry_index: int,
    prev_artifact_hash: str,
    engine_profile: str = ENGINE_VERSION,
) -> "tuple[dict, str]":
    """Qualify one candidate; returns (artifact, artifact_hash).

    A REJECTED/INCONCLUSIVE intake is still materialized as a full artifact
    with the evidence (no silent discards — order §11).
    """
    if engine_profile not in ENGINE_PROFILES:
        raise InvalidQualificationState(
            f"unknown engine profile {engine_profile!r}; known: {list(ENGINE_PROFILES)}"
        )
    protocol_v, schema_v, engine_v = engine_profile, engine_profile, engine_profile

    dimensions = _empty_dimensions()
    reason_codes: "list[str]" = []
    forwarded: "list[dict]" = []

    # --- intake validation (schema + versions) ---
    schema_issues = validate_document(candidate, "case-candidate")
    version_problems = version_issues(candidate)
    if schema_issues or version_problems:
        dimensions["structural"] = {
            "status": "INCOMPLETE",
            "findings": ["INTAKE-SCHEMA-INVALID: " + "; ".join((schema_issues + version_problems)[:5])],
        }
        decision, reasons = "REJECT", ["INTAKE-SCHEMA-INVALID"]
        artifact = _assemble_artifact(
            candidate=candidate,
            dimensions=dimensions,
            qualified_at=qualified_at,
            operator=operator,
            run_id=run_id,
            entry_index=entry_index,
            prev_artifact_hash=prev_artifact_hash,
            decision=decision,
            reason_codes=reasons,
            engine_version=engine_v,
            protocol_version=protocol_v,
            schema_version=schema_v,
        )
        return artifact, artifact["artifact_hash"]

    if candidate.get("content_class") == "format-illustration":
        raise QualificationError(
            f"candidate {candidate.get('candidate_id', '?')!r} is content_class "
            "'format-illustration': public illustration material cannot be "
            "qualified (real review material only)"
        )

    content = candidate["content"]

    # --- Q1 identity ---
    recomputed = hash_document(content)
    identity_ok = recomputed == candidate.get("content_hash")
    dimensions["identity"] = {
        "status": "PASS" if identity_ok else "FAIL",
        "content_hash_verified": identity_ok,
        "canonicalization": "ECP-CANONICAL-JSON-1.0",
    }
    if not identity_ok:
        reason_codes.append("Q1-IDENTITY-FAIL")

    # --- Q2 structural (§5 fields) ---
    # NOTE: the formal layer is deliberately NOT in the core set: its absence
    # does not reject the candidate — it makes the ground truth mechanically
    # unverifiable, which routes to Q3 (UNVERIFIABLE -> INCONCLUSIVE, the
    # honest "cannot qualify now"), per order §6/§11.
    core_fields = {
        "premises": content.get("premises"),
        "question": content.get("question"),
        "intended_correct_answers": content.get("intended_correct_answers"),
        "derivations": content.get("derivations"),
        "ground_truth": content.get("ground_truth"),
        "proposed_reasoning_family": content.get("proposed_reasoning_family"),
    }
    auxiliary_fields = {
        "expected_property": content.get("expected_property"),
        "forbidden_shortcuts": content.get("forbidden_shortcuts"),
        "structural_signature": content.get("structural_signature"),
        "self_review": content.get("self_review"),
    }
    missing_core = [name for name, value in core_fields.items() if not value]
    missing_aux = [name for name, value in auxiliary_fields.items() if not value]
    gt = content.get("ground_truth") or {}
    if gt.get("class") not in GT_CLASSES:
        missing_core.append("ground_truth.class")
    structural_findings = []
    if missing_core:
        structural_findings.append(f"missing §5 core fields: {missing_core}")
    if missing_aux:
        structural_findings.append(f"missing §5 auxiliary fields: {missing_aux}")
    structural_status = "PASS"
    if missing_core:
        structural_status = "INCOMPLETE-CORE"
    elif missing_aux:
        structural_status = "INCOMPLETE-AUX"
    dimensions["structural"] = {"status": structural_status, "findings": structural_findings}
    if missing_core:
        reason_codes.append("Q2-CORE-INCOMPLETE")
    elif missing_aux:
        reason_codes.append("Q2-AUX-INCOMPLETE")

    # --- Q3 ground truth (mechanical verification) ---
    formal = content.get("formal") or {}
    gt_findings: "list[str]" = []
    authored_class = gt.get("class")
    if not formal:
        dimensions["ground_truth"] = {
            "status": "UNVERIFIABLE",
            "findings": ["formal verification layer absent: ground truth cannot be verified mechanically"],
        }
        reason_codes.append("Q3-GT-UNVERIFIABLE")
        forwarded.append(
            {
                "code": "FWD-GT-UNVERIFIABLE",
                "note": "candidate carries no machine-checkable verification layer; "
                "ground truth is author-attested only",
                "target_stage": "authoring-revision",
            }
        )
    else:
        verification = verify_ground_truth(formal)
        derived_class = verification.get("derived_class")
        status = "PASS"
        if derived_class is None:
            note = verification.get("status_note", "unverifiable")
            if note.startswith("MALFORMED"):
                status = "MALFORMED"
                reason_codes.append("Q3-FORMAL-MALFORMED")
            elif "INCONSISTENT" in note:
                status = "INCONSISTENT-DESIGN"
                reason_codes.append("Q3-PREMISES-INCONSISTENT")
            else:
                status = "UNVERIFIABLE"
                reason_codes.append("Q3-GT-UNVERIFIABLE")
            gt_findings.append(note)
            forwarded.append(
                {
                    "code": "FWD-GT-NONDETERMINATE" if "INCONSISTENT" in note else "FWD-GT-UNVERIFIABLE",
                    "note": note,
                    "target_stage": "authoring-revision",
                }
            )
        elif derived_class != authored_class:
            status = "MISMATCH"
            gt_findings.append(
                f"authored ground-truth class {authored_class!r} does not match the "
                f"mechanically derived class {derived_class!r} ({verification.get('method')})"
            )
            reason_codes.append("Q3-GT-MISMATCH")
            forwarded.append(
                {
                    "code": "FWD-GT-MISMATCH",
                    "note": "authored ground truth is not supported by the formal layer",
                    "target_stage": "authoring-revision",
                }
            )
        else:
            derived_value = verification.get("value")
            if derived_value is not None:
                agrees = _value_agrees(derived_value, candidate)
                if agrees is False:
                    status = "MISMATCH"
                    gt_findings.append(
                        f"derived value {derived_value!r} does not appear in the authored answer/statement"
                    )
                    reason_codes.append("Q3-VALUE-MISMATCH")
                else:
                    verification = dict(verification)
                    verification["value_agreement"] = "PASS" if agrees else "NOT-APPLICABLE"
            if status == "PASS" and derived_class == "INDETERMINATE" and gt.get("ambiguity_note"):
                forwarded.append(
                    {
                        "code": "FWD-GT-DESIGNED-AMBIGUITY",
                        "note": "designed indeterminacy recorded and mechanically verified "
                        f"({gt.get('ambiguity_note')})",
                        "target_stage": "registration-readiness",
                    }
                )
        coverage_issues = _symbol_coverage_issues(candidate)
        if coverage_issues:
            gt_findings.extend(coverage_issues)
            reason_codes.append("Q3-CORRESPONDENCE-GAP")
        dimensions["ground_truth"] = {
            "status": status,
            "findings": gt_findings,
            "verification": verification,
            "authored_class": authored_class,
            "derived_class": derived_class,
        }

    # --- Q4 novelty (N1–N6) ---
    novelty_findings: "list[str]" = []
    skeleton = structural_skeleton(candidate)
    n3_status = "UNIQUE"
    if skeleton is None:
        n3_status = "NOT-COMPUTABLE"
        novelty_findings.append("N3: skeleton not computable (formal layer absent)")
    else:
        for other in prior_in_pool:
            other_skeleton = structural_skeleton(other)
            if other_skeleton == skeleton:
                n3_status = "DUPLICATE"
                novelty_findings.append(
                    f"N3: structural skeleton identical to {other.get('candidate_id')} "
                    f"({other.get('source', {}).get('case_id')}) — entity/relation renaming is "
                    "not a new case (order §7)"
                )
                reason_codes.append("Q4-N3-DUPLICATE")
                break

    # N4: cross-population replay (text-level; prior pool has no formal layer)
    n4_status = "CLEAR"
    case_tokens = normalize_tokens(" ".join(content.get("premises", [])))
    signature_tokens = normalize_tokens(content.get("structural_signature", ""))
    for prior_candidate in prior_population:
        prior_content = prior_candidate.get("content", {})
        prior_tokens = normalize_tokens(" ".join(prior_content.get("premises", [])))
        overlap = _jaccard(case_tokens, prior_tokens)
        sig_overlap = _jaccard(signature_tokens, normalize_tokens(prior_content.get("structural_signature", "")))
        if case_tokens and case_tokens == prior_tokens:
            n4_status = "DUPLICATE"
            novelty_findings.append(
                f"N4: premise text identical to prior-pool candidate "
                f"{prior_candidate.get('candidate_id')}"
            )
            reason_codes.append("Q4-N4-DUPLICATE")
            break
        if overlap >= CROSS_POP_JACCARD_THRESHOLD or sig_overlap >= CROSS_POP_JACCARD_THRESHOLD:
            n4_status = "SUSPICION"
            novelty_findings.append(
                f"N4: replay suspicion vs prior-pool candidate "
                f"{prior_candidate.get('candidate_id')} "
                f"(premise jaccard {overlap:.2f}, signature jaccard {sig_overlap:.2f})"
            )
            reason_codes.append("Q4-N4-SUSPICION")
            break

    # N1/N2: external novelty — honest open question (O-01 stance)
    # N5/N6: identifier registry
    identifier_issues = _identifier_issues(candidate)
    for issue in identifier_issues:
        novelty_findings.append(issue)
        reason_codes.append("Q4-N5-ENCODING" if issue.startswith("N5") else "Q4-N6-FIXTURE")

    dimensions["novelty"] = {
        "status": n3_status if n3_status != "UNIQUE" else (n4_status if n4_status != "CLEAR" else "UNIQUE"),
        "n1_direct_retrieval": "OPEN-QUESTION (external novelty NOT_ESTABLISHABLE_MECHANICALLY; retrieval risk as authored)",
        "n2_solution_retrieval": "OPEN-QUESTION (same basis as N1)",
        "n3_within_pool": n3_status,
        "n4_cross_population": {
            "status": n4_status,
            "basis": "text-normalized premise/signature overlap; the prior format-1 pool carries no formal layer, so structure-level cross-comparison is not applicable",
        },
        "n5_implementation_encoding": "FLAGGED" if any(i.startswith("N5") for i in identifier_issues) else "CLEAR",
        "n6_fixture_leakage": "FLAGGED" if any(i.startswith("N6") for i in identifier_issues) else "CLEAR",
        "findings": novelty_findings,
        "skeleton": skeleton,
    }

    # --- Q5 leakage pre-screen (§8 classes) ---
    leakage_findings: "list[str]" = []
    leakage_status = "CLEAN"
    answer_text = " ".join(a.get("value", "") for a in content.get("intended_correct_answers", []))
    question_tokens = normalize_tokens(content.get("question", ""))
    premises_tokens = normalize_tokens(" ".join(content.get("premises", [])))
    task_tokens = question_tokens + premises_tokens

    # direct: queried atom present as a premise fact (triviality leak)
    direct_confirmed = False
    query = formal.get("query", {})
    if query.get("relation") and formal.get("semantics") == "relational-closure":
        for premise in formal.get("premises", []):
            if premise.get("kind") == "rel_fact" and not premise.get("negated", False):
                if _atom_key(premise["relation"], premise["args"]) == _atom_key(query["relation"], query.get("args", [])):
                    direct_confirmed = True
                    leakage_findings.append(
                        "direct answer leakage: the queried statement is itself a premise fact "
                        "(no derivation required — the case does not test reasoning)"
                    )
                    reason_codes.append("Q5-DIRECT-LEAK-CONFIRMED")
    if query.get("prop") and formal.get("semantics") in ("propositional-truth-table", "default-extensions"):
        want = query.get("value", True)
        for premise in formal.get("premises", []):
            if premise.get("kind") == "prop_fact" and premise.get("prop") == query["prop"] and premise.get("value", True) == want:
                direct_confirmed = True
                leakage_findings.append(
                    "direct answer leakage: the queried proposition is asserted directly by a premise fact"
                )
                reason_codes.append("Q5-DIRECT-LEAK-CONFIRMED")
    if query.get("kind") == "value_of" and formal.get("semantics") == "constraint-enumeration":
        for premise in formal.get("premises", []):
            if premise.get("kind") == "equals" and premise.get("var") == query.get("var"):
                direct_confirmed = True
                leakage_findings.append(
                    "direct answer leakage: the queried value is assigned directly by a premise"
                )
                reason_codes.append("Q5-DIRECT-LEAK-CONFIRMED")

    # semantic: answer core appears contiguously in the task text
    answer_core = _answer_core(answer_text)
    semantic_status = "CLEAR"
    if len(answer_core) >= ANSWER_CORE_MIN_TOKENS and _normalized_contiguous(answer_core, task_tokens):
        semantic_status = "CONFIRMED"
        leakage_status = "RISK"
        leakage_findings.append(
            "semantic answer leakage: the answer's content appears verbatim inside the task text"
        )
        reason_codes.append("Q5-SEMANTIC-LEAK-CONFIRMED")
    elif _jaccard(answer_core, question_tokens) >= SEMANTIC_ANSWER_JACCARD_THRESHOLD:
        semantic_status = "RISK"
        leakage_status = "RISK"
        leakage_findings.append(
            "semantic answer leakage risk: very high answer/question token overlap"
        )
        reason_codes.append("Q5-SEMANTIC-LEAK-RISK")

    # solution/trajectory: derivation text embedded in the premises
    solution_status = "CLEAR"
    derivation_text = " ".join(d.get("raw", "") for d in content.get("derivations", []))
    derivation_tokens = normalize_tokens(derivation_text)
    if (
        len(derivation_tokens) >= SOLUTION_CONTAINMENT_MIN_TOKENS
        and _normalized_contiguous(derivation_tokens, premises_tokens)
    ):
        solution_status = "CONFIRMED"
        leakage_status = "RISK"
        leakage_findings.append(
            "solution/trajectory leakage: the derivation appears verbatim inside the premises"
        )
        reason_codes.append("Q5-SOLUTION-LEAK-CONFIRMED")

    if direct_confirmed:
        leakage_status = "CONFIRMED"

    dimensions["leakage"] = {
        "status": leakage_status,
        "classes": {
            "direct_answer": "CONFIRMED" if direct_confirmed else "CLEAR",
            "semantic_answer": semantic_status,
            "solution_trajectory": solution_status,
            "implementation_encoding": "FLAGGED" if any(i.startswith("N5") for i in identifier_issues) else "CLEAR",
            "fixture": "FLAGGED" if any(i.startswith("N6") for i in identifier_issues) else "CLEAR",
            "model": "NOT-APPLICABLE-PRE-EXECUTION (no model has been exposed to the case; "
            "pretraining exposure remains a declared, bounded, permanent limitation — "
            "threat model §8.2)",
        },
        "findings": leakage_findings,
    }

    # --- Q6 independence (§3 record) ---
    independence = candidate.get("authoring_independence")
    independence_findings: "list[str]" = []
    required_independence_keys = (
        "author_identity", "authoring_environment", "model_tool", "model_version",
        "prompt_instructions", "information_available", "information_unavailable",
        "relationship_to_ecp_developers", "relationship_to_evaluated_systems",
        "access_to_prior_ecp_results", "independence_status",
    )
    if not isinstance(independence, dict):
        independence_status_label = "MISSING"
        independence_findings.append("authoring-independence record absent (order §3)")
        reason_codes.append("Q6-INDEPENDENCE-MISSING")
    else:
        missing_keys = [k for k in required_independence_keys if not independence.get(k)]
        if missing_keys:
            independence_status_label = "INCOMPLETE"
            independence_findings.append(f"independence record missing keys: {missing_keys}")
            reason_codes.append("Q6-INDEPENDENCE-INCOMPLETE")
        else:
            independence_status_label = "COMPLETE"
        status_block = independence.get("independence_status")
        label = status_block.get("label") if isinstance(status_block, dict) else status_block
        if isinstance(label, str) and label.strip().upper() == "INDEPENDENT":
            independence_findings.append(
                "bare 'INDEPENDENT' status label rejected: independence is declared per "
                "dimension with an explicit bounded label (order §3)"
            )
            reason_codes.append("Q6-BARE-INDEPENDENT-CLAIM")
    dimensions["independence"] = {
        "status": independence_status_label,
        "findings": independence_findings,
    }

    # --- Q7 representation-bias disclosure (§9) ---
    rb = candidate.get("representation_bias_disclosure")
    rb_findings: "list[str]" = []
    if not isinstance(rb, dict) or not rb.get("status") or not rb.get("evidence") or not rb.get("known_limitation"):
        rb_status = "UNDISCLOSED"
        rb_findings.append("representation-bias disclosure incomplete (status/evidence/known limitation)")
        reason_codes.append("Q7-DISCLOSURE-MISSING")
    else:
        rb_status = "PRESENT"
    dimensions["representation_bias"] = {"status": rb_status, "findings": rb_findings}

    # --- Q8 environmental pre-check (§10) ---
    env = candidate.get("environmental_pre_check")
    env_findings: "list[str]" = []
    if not isinstance(env, dict):
        env_status = "ABSENT"
        env_findings.append("environmental pre-check record absent (order §10)")
        reason_codes.append("Q8-ENVIRONMENTAL-MISSING")
    else:
        required_env_keys = (
            "knowledge_sources", "fixtures", "implementation_artifacts",
            "memory_paths", "model_access_paths", "answer_bearing_artifacts",
        )
        missing_env = [k for k in required_env_keys if not env.get(k)]
        if missing_env:
            env_status = "INCOMPLETE"
            env_findings.append(f"environmental pre-check missing keys: {missing_env}")
            reason_codes.append("Q8-ENVIRONMENTAL-INCOMPLETE")
        else:
            env_status = "PRESENT"
    dimensions["environmental_pre_check"] = {"status": env_status, "findings": env_findings}

    # --- decision (deterministic precedence: REJECT > REVISE > INCONCLUSIVE > ACCEPT) ---
    decision = "ACCEPT"
    if "Q1-IDENTITY-FAIL" in reason_codes:
        decision = "REJECT"
    elif "Q3-GT-MISMATCH" in reason_codes or "Q3-VALUE-MISMATCH" in reason_codes:
        decision = "REJECT"
    elif "Q5-DIRECT-LEAK-CONFIRMED" in reason_codes:
        decision = "REJECT"
    elif "Q2-CORE-INCOMPLETE" in reason_codes:
        decision = "REJECT"
    elif "Q6-INDEPENDENCE-MISSING" in reason_codes:
        decision = "REJECT"
    elif "Q4-N4-DUPLICATE" in reason_codes:
        decision = "REJECT"
    elif "Q3-PREMISES-INCONSISTENT" in reason_codes:
        decision = "REJECT"
    elif (
        "Q4-N3-DUPLICATE" in reason_codes
        or "Q4-N4-SUSPICION" in reason_codes
        or "Q5-SEMANTIC-LEAK-CONFIRMED" in reason_codes
        or "Q5-SOLUTION-LEAK-CONFIRMED" in reason_codes
        or "Q2-AUX-INCOMPLETE" in reason_codes
        or "Q3-FORMAL-MALFORMED" in reason_codes
        or "Q6-INDEPENDENCE-INCOMPLETE" in reason_codes
        or "Q6-BARE-INDEPENDENT-CLAIM" in reason_codes
        or "Q7-DISCLOSURE-MISSING" in reason_codes
        or "Q8-ENVIRONMENTAL-MISSING" in reason_codes
        or "Q8-ENVIRONMENTAL-INCOMPLETE" in reason_codes
    ):
        decision = "REVISE"
    elif "Q3-GT-UNVERIFIABLE" in reason_codes:
        decision = "INCONCLUSIVE"

    if decision not in QUALIFICATION_STATES:
        raise InvalidQualificationState(
            f"decision mapping produced {decision!r} outside {QUALIFICATION_STATES}"
        )

    artifact = _assemble_artifact(
        candidate=candidate,
        dimensions=dimensions,
        qualified_at=qualified_at,
        operator=operator,
        run_id=run_id,
        entry_index=entry_index,
        prev_artifact_hash=prev_artifact_hash,
        decision=decision,
        reason_codes=reason_codes,
        engine_version=engine_v,
        protocol_version=protocol_v,
        schema_version=schema_v,
        forwarded=forwarded,
    )
    return artifact, artifact["artifact_hash"]


def _assemble_artifact(
    candidate: dict,
    dimensions: dict,
    qualified_at: str,
    operator: str,
    run_id: str,
    entry_index: int,
    prev_artifact_hash: str,
    decision: str,
    reason_codes: "list[str]",
    engine_version: str,
    protocol_version: str,
    schema_version: str,
    forwarded: "list[dict] | None" = None,
) -> dict:
    if decision not in QUALIFICATION_STATES:
        raise InvalidQualificationState(
            f"decision {decision!r} outside the four qualification states"
        )
    source = candidate.get("source", {})
    artifact = {
        "ecp_object": "case-qualification",
        "qualification_id": f"ECP-QUAL-{entry_index + 100:06d}",
        "candidate_id": candidate.get("candidate_id"),
        "run_id": run_id,
        "qualified_at": qualified_at,
        "operator": operator,
        "source_case_id": source.get("case_id"),
        "content_hash": candidate.get("content_hash"),
        "entry_index": entry_index,
        "prev_qualification_hash": prev_artifact_hash,
        "engine": {"id": ENGINE_ID, "version": engine_version},
        "dimensions": dimensions,
        "decision": decision,
        "reason_codes": reason_codes,
        "forwarded": forwarded or [],
        "boundary": "QUALIFIED-POOL-ONLY — NOT REGISTERED (order §14: registration closed)",
        "protocol_version": protocol_version,
        "schema_version": schema_version,
    }
    artifact["artifact_hash"] = hash_document_excluding(artifact, "artifact_hash")
    return artifact


# ---------------------------------------------------------------------------
# Run-level orchestration
# ---------------------------------------------------------------------------


def _current_operator() -> str:
    return "ECP Foundation Executor <foundation@ecp-protocol.local>"


def run_qualification(
    candidates: "list[dict]",
    run_id: str,
    qualified_at: str,
    operator: "str | None" = None,
    prior_population: "list[dict] | None" = None,
    source_label: "str | None" = None,
    source_sha: "str | None" = None,
    engine_profile: str = ENGINE_VERSION,
) -> dict:
    """Run the deterministic qualification over *candidates*.

    Returns ``{artifacts, run}`` — per-candidate artifacts (hash-chained in
    candidate order) and the run manifest. Pure function of the inputs.
    """
    if engine_profile not in ENGINE_PROFILES:
        raise InvalidQualificationState(
            f"unknown engine profile {engine_profile!r}; known: {list(ENGINE_PROFILES)}"
        )
    operator = operator or _current_operator()
    prior_population = prior_population or []

    artifacts: "list[dict]" = []
    prev_hash = "0" * 64
    for index, candidate in enumerate(candidates, start=1):
        prior_in_pool = candidates[: index - 1]
        artifact, artifact_hash = qualify_candidate(
            candidate,
            prior_in_pool=prior_in_pool,
            prior_population=prior_population,
            run_id=run_id,
            qualified_at=qualified_at,
            operator=operator,
            entry_index=index,
            prev_artifact_hash=prev_hash,
            engine_profile=engine_profile,
        )
        artifacts.append(artifact)
        prev_hash = artifact_hash

    tallies = {
        "accept": sum(1 for a in artifacts if a["decision"] == "ACCEPT"),
        "revise": sum(1 for a in artifacts if a["decision"] == "REVISE"),
        "reject": sum(1 for a in artifacts if a["decision"] == "REJECT"),
        "inconclusive": sum(1 for a in artifacts if a["decision"] == "INCONCLUSIVE"),
    }

    run = {
        "ecp_object": "qualification-run",
        "run_id": run_id,
        "qualified_at": qualified_at,
        "operator": operator,
        "source": {
            "label": source_label,
            "sha256": source_sha,
        },
        "engine": {
            "id": ENGINE_ID,
            "version": engine_profile,
            "profile": engine_profile,
        },
        "decision_rules": {
            "precedence": "REJECT > REVISE > INCONCLUSIVE > ACCEPT",
            "reject": [
                "Q1 identity failure",
                "Q3 ground-truth mismatch (authored class or value not supported mechanically)",
                "Q3 premises inconsistent w.r.t. a statement query",
                "Q5 confirmed direct answer leakage",
                "Q2 missing §5 core content fields",
                "Q6 authoring-independence record missing",
                "Q4 exact cross-population duplication",
            ],
            "revise": [
                "Q4 within-pool structural duplication (later of the pair)",
                "Q4 cross-population replay suspicion",
                "Q5 semantic/solution leakage overlap",
                "Q2 missing auxiliary §5 fields",
                "Q3 malformed formal-layer shape",
                "Q6/Q7/Q8 incomplete independence/disclosure records",
            ],
            "inconclusive": [
                "Q3 ground truth not mechanically verifiable (formal layer absent)",
            ],
            "accept": ["all checks pass; open risk questions (N1/N2, pretraining exposure) recorded, non-blocking"],
        },
        "parameters": {
            "within_pool_skeleton": WITHIN_POOL_SKELETON,
            "cross_population_jaccard_threshold": CROSS_POP_JACCARD_THRESHOLD,
            "semantic_answer_jaccard_threshold": SEMANTIC_ANSWER_JACCARD_THRESHOLD,
        },
        "prior_population": {
            "label": "prior-pool (format-1) candidates used for cross-population novelty",
            "count": len(prior_population),
            "candidate_ids": [c.get("candidate_id") for c in prior_population],
            "content_hashes": [c.get("content_hash") for c in prior_population],
        },
        "entries": [
            {
                "qualification_id": artifact["qualification_id"],
                "candidate_id": artifact["candidate_id"],
                "source_case_id": artifact["source_case_id"],
                "content_hash": artifact["content_hash"],
                "decision": artifact["decision"],
                "artifact_hash": artifact["artifact_hash"],
            }
            for artifact in artifacts
        ],
        "decisions": tallies,
        "chain_head": artifacts[-1]["artifact_hash"] if artifacts else "0" * 64,
        "boundary": "STOP-BEFORE-REGISTRATION (order §14: registration closed)",
        "execution_isolation": "NO evaluated model execution; NO benchmark scoring; authoring + qualification only (order §13)",
        "determinism": "pure function of (candidates, run metadata, prior population content)",
        "protocol_version": engine_profile,
        "schema_version": engine_profile,
    }
    run["run_hash"] = hash_document_excluding(run, "run_hash")
    return {"artifacts": artifacts, "run": run}


# ---------------------------------------------------------------------------
# Verification (integrity-only; never scientific adjudication)
# ---------------------------------------------------------------------------


def verify_artifact(artifact: dict) -> "list[str]":
    """Integrity issues for one qualification artifact (issue list)."""
    issues: "list[str]" = []
    if not isinstance(artifact, dict):
        return ["<root>: expected a JSON object"]
    if artifact.get("ecp_object") != "case-qualification":
        issues.append("ecp_object: expected 'case-qualification'")
    if artifact.get("decision") not in QUALIFICATION_STATES:
        issues.append(f"decision {artifact.get('decision')!r} outside the four states")
    stored_hash = artifact.get("artifact_hash")
    if not isinstance(stored_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", stored_hash):
        issues.append("artifact_hash: not a sha256 hex string")
        return issues
    recomputed = hash_document_excluding(artifact, "artifact_hash")
    if recomputed != stored_hash:
        issues.append("artifact_hash: recomputation mismatch (tampering or corruption)")
    prev = artifact.get("prev_qualification_hash")
    if not isinstance(prev, str) or not re.fullmatch(r"[0-9a-f]{64}", prev):
        issues.append("prev_qualification_hash: not a sha256 hex string")
    dimensions = artifact.get("dimensions", {})
    if not isinstance(dimensions, dict) or len(dimensions) != 8:
        issues.append("dimensions: expected the 8 qualification dimensions")
    return issues


def verify_run(run: dict, artifacts: "list[dict]") -> "list[str]":
    """Integrity issues for a run manifest (issue list)."""
    issues: "list[str]" = []
    if not isinstance(run, dict):
        return ["<root>: expected a JSON object"]
    if run.get("ecp_object") != "qualification-run":
        issues.append("ecp_object: expected 'qualification-run'")
    stored_hash = run.get("run_hash")
    if not isinstance(stored_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", stored_hash):
        issues.append("run_hash: not a sha256 hex string")
        return issues
    recomputed = hash_document_excluding(run, "run_hash")
    if recomputed != stored_hash:
        issues.append("run_hash: recomputation mismatch (tampering or corruption)")

    entries = run.get("entries", [])
    if len(entries) != len(artifacts):
        issues.append(f"entries: manifest lists {len(entries)} but {len(artifacts)} artifacts provided")
    for entry, artifact in zip(entries, artifacts):
        if entry.get("artifact_hash") != artifact.get("artifact_hash"):
            issues.append(
                f"{entry.get('candidate_id', '?')}: entry artifact_hash does not match the artifact"
            )
        if entry.get("decision") != artifact.get("decision"):
            issues.append(
                f"{entry.get('candidate_id', '?')}: entry decision does not match the artifact"
            )
        if entry.get("content_hash") != artifact.get("content_hash"):
            issues.append(
                f"{entry.get('candidate_id', '?')}: entry content_hash does not match the artifact"
            )

    tallies = {
        "accept": sum(1 for a in artifacts if a.get("decision") == "ACCEPT"),
        "revise": sum(1 for a in artifacts if a.get("decision") == "REVISE"),
        "reject": sum(1 for a in artifacts if a.get("decision") == "REJECT"),
        "inconclusive": sum(1 for a in artifacts if a.get("decision") == "INCONCLUSIVE"),
    }
    if run.get("decisions") != tallies:
        issues.append(f"decisions: tallies {run.get('decisions')} do not match artifacts {tallies}")

    if artifacts:
        head = artifacts[-1].get("artifact_hash")
        if run.get("chain_head") != head:
            issues.append("chain_head: does not match the last artifact hash")
        prev = "0" * 64
        for artifact in artifacts:
            if artifact.get("prev_qualification_hash") != prev:
                issues.append(
                    f"{artifact.get('qualification_id', '?')}: chain link broken "
                    "(prev_qualification_hash does not match the previous artifact)"
                )
            prev = artifact.get("artifact_hash", "")
    elif run.get("chain_head") != "0" * 64:
        issues.append("chain_head: expected genesis hash for an empty run")
    return issues
