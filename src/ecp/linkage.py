"""Cross-document provenance linkage checks.

The ECP hierarchy keeps distinct objects with distinct provenance:

    Evaluation > System > Case > Execution > Evidence   (+ Registration, Audit)

This module checks that a provided set of documents references each other
consistently: an execution must point at the evaluation, system and case it
belongs to; evidence must point at its execution and evaluation; an audit
must point at the evidence it reviewed (including its canonical hash).
Linkage is structural provenance only — it does not adjudicate anything.
"""

from .hashing import hash_document

_KEYS = ("evaluation", "system", "case", "registration", "execution", "evidence", "audit")


def check_linkage(documents: dict) -> "list[str]":
    """Check identifier consistency across a provided document set.

    Args:
        documents: mapping with any subset of the keys ``evaluation``,
            ``system``, ``case``, ``registration``, ``execution``,
            ``evidence``, ``audit`` (values = document dicts).

    Returns:
        A list of issues (empty = consistent).
    """
    for key in documents:
        if key not in _KEYS:
            raise KeyError(f"unknown linkage document {key!r}; expected one of {_KEYS}")

    evaluation = documents.get("evaluation")
    system = documents.get("system")
    case = documents.get("case")
    registration = documents.get("registration")
    execution = documents.get("execution")
    evidence = documents.get("evidence")
    audit = documents.get("audit")
    issues: "list[str]" = []

    def _id(document, *path):
        node = document
        for part in path:
            node = node.get(part, {}) if isinstance(node, dict) else {}
        return node

    if evaluation and system:
        if _id(evaluation, "system", "system_id") != _id(system, "system_id"):
            issues.append(
                f"evaluation.system.system_id {_id(evaluation, 'system', 'system_id')!r} "
                f"!= system.system_id {_id(system, 'system_id')!r}"
            )
    if evaluation and case:
        member_ids = _id(evaluation, "case_set", "case_ids")
        if isinstance(member_ids, list) and _id(case, "case_id") not in member_ids:
            issues.append(
                f"case.case_id {_id(case, 'case_id')!r} not enumerated by "
                f"evaluation.case_set.case_ids"
            )
    if registration and evaluation:
        if _id(registration, "evaluation_id") != _id(evaluation, "evaluation_id"):
            issues.append(
                f"registration.evaluation_id {_id(registration, 'evaluation_id')!r} "
                f"!= evaluation.evaluation_id {_id(evaluation, 'evaluation_id')!r}"
            )
    if registration and system:
        if _id(registration, "system", "system_id") != _id(system, "system_id"):
            issues.append(
                f"registration.system.system_id {_id(registration, 'system', 'system_id')!r} "
                f"!= system.system_id {_id(system, 'system_id')!r}"
            )
    if registration and case:
        if _id(registration, "case", "case_id") != _id(case, "case_id"):
            issues.append(
                f"registration.case.case_id {_id(registration, 'case', 'case_id')!r} "
                f"!= case.case_id {_id(case, 'case_id')!r}"
            )
    if execution and evaluation:
        if _id(execution, "evaluation_id") != _id(evaluation, "evaluation_id"):
            issues.append(
                f"execution.evaluation_id {_id(execution, 'evaluation_id')!r} "
                f"!= evaluation.evaluation_id {_id(evaluation, 'evaluation_id')!r}"
            )
    if execution and system:
        if _id(execution, "system", "system_id") != _id(system, "system_id"):
            issues.append(
                f"execution.system.system_id {_id(execution, 'system', 'system_id')!r} "
                f"!= system.system_id {_id(system, 'system_id')!r}"
            )
    if execution and case:
        if _id(execution, "case", "case_id") != _id(case, "case_id"):
            issues.append(
                f"execution.case.case_id {_id(execution, 'case', 'case_id')!r} "
                f"!= case.case_id {_id(case, 'case_id')!r}"
            )
    if evidence and execution:
        if _id(evidence, "execution_id") != _id(execution, "execution_id"):
            issues.append(
                f"evidence.execution_id {_id(evidence, 'execution_id')!r} "
                f"!= execution.execution_id {_id(execution, 'execution_id')!r}"
            )
        if _id(evidence, "evaluation_id") != _id(execution, "evaluation_id"):
            issues.append(
                f"evidence.evaluation_id {_id(evidence, 'evaluation_id')!r} "
                f"!= execution.evaluation_id {_id(execution, 'evaluation_id')!r}"
            )
    if audit and evidence:
        reviewed = {
            item.get("evidence_id"): item.get("evidence_hash")
            for item in _id(audit, "evidence_reviewed")
            if isinstance(item, dict)
        }
        if _id(evidence, "evidence_id") not in reviewed:
            issues.append(
                f"audit.evidence_reviewed does not include "
                f"evidence.evidence_id {_id(evidence, 'evidence_id')!r}"
            )
        else:
            actual = hash_document(evidence)
            cited = reviewed[_id(evidence, "evidence_id")]
            if cited != actual:
                issues.append(
                    f"audit.evidence_reviewed hash for {_id(evidence, 'evidence_id')!r}: "
                    f"cited {cited!r} != recomputed {actual!r}"
                )
    return issues
