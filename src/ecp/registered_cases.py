"""Registered M3-ELR case loader — the sole scientific prompt authority.

Reconstructed 2026-09-13 (custody event D-01 #7; see
docs/M3-ELR-READINESS-RECONSTRUCTION.md). Loads the 30 registered cases
from the PRIVATE qualification area (never inside the public repository),
verifies each candidate fail-closed on FOUR surfaces, and produces
:class:`ecp.execution_contract.RegisteredCaseArtifact` objects whose
prompt is the deterministic PREMISES/QUESTION presentation.

Four-surface hash verification (all four must agree, else refuse):

1. canonical re-derivation — ``ecp.hashing.hash_document(content)``;
2. the candidate's embedded ``content_hash``;
3. the registration package's per-case ``content_hash``;
4. the population namespace manifest ``candidate_index``.

The protected ground truth (intended answers, GT class, derivations) is
exposed ONLY through :func:`protected_ground_truth` for the in-process
classifier — it is never rendered into the prompt, never persisted into
evidence, and never written inside the repository.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .canonical import load_json
from .execution_contract import RegisteredCaseArtifact
from .hashing import hash_document
from .m3_registration import (
    CASE_ID_TEMPLATE,
    CANDIDATE_ID_TEMPLATE,
    TEST_ID_TEMPLATE,
    candidate_number,
)

#: Private qualification area (outside the repository; recovered byte-exact).
CASE_AREA = Path("/home/z/ecp-ca0v1")

#: Presentation rule (deterministic; reconstructed — the original bytes were
#: lost with c49b18f and never used by any execution, so no outcome could
#: ever have depended on them).
PRESENTATION_RULE = (
    "deterministic PREMISES/QUESTION presentation: numbered premises, blank "
    "line, the registered question verbatim (the question embeds the authored "
    "answer-format instruction)"
)


def _presentation(content: Mapping[str, Any]) -> str:
    lines = ["PREMISES:"]
    for index, premise in enumerate(content.get("premises") or [], start=1):
        lines.append(f"{index}. {premise}")
    lines.append("")
    lines.append(f"QUESTION: {content.get('question', '')}")
    return "\n".join(lines) + "\n"


def load_registered_cases(
    package: Mapping[str, Any],
    *,
    case_area: "str | Path" = CASE_AREA,
    manifest_index: "Mapping[str, str] | None" = None,
) -> "dict[str, RegisteredCaseArtifact]":
    """Load every registered case as a prompt-authority artifact.

    Returns ``{test_id: RegisteredCaseArtifact}`` (the resolver keys cases
    by test_id). Fails closed on any four-surface hash mismatch.
    """
    candidates_dir = Path(case_area) / "qualification" / "candidates"
    artifacts: "dict[str, RegisteredCaseArtifact]" = {}
    for entry in package.get("cases") or []:
        number = int(str(entry["test_id"]).rsplit("-", 1)[-1])
        candidate_id = entry["candidate_id"]
        if candidate_id != CANDIDATE_ID_TEMPLATE.format(n=number + 100):
            raise ValueError(f"case {number}: candidate_id {candidate_id!r} breaks the registered numbering")
        path = candidates_dir / f"{candidate_id}.json"
        if not path.is_file():
            raise FileNotFoundError(f"registered case artifact absent: {path}")
        candidate = load_json(path)
        content = candidate.get("content")
        if not isinstance(content, dict):
            raise ValueError(f"{path}: malformed candidate content")
        surfaces = {
            "canonical": hash_document(content),
            "embedded": candidate.get("content_hash"),
            "package": entry.get("content_hash"),
        }
        if manifest_index is not None:
            surfaces["manifest"] = manifest_index.get(candidate_id)
        values = set(surfaces.values())
        if None in values or len(values) != 1:
            raise ValueError(
                f"case {number}: four-surface hash verification FAILED "
                f"({surfaces})"
            )
        prompt = _presentation(content)
        artifact = RegisteredCaseArtifact.for_prompt(
            CASE_ID_TEMPLATE.format(n=number),
            prompt,
            case_artifact_hash=hash_document(
                {
                    "case_id": CASE_ID_TEMPLATE.format(n=number),
                    "test_id": TEST_ID_TEMPLATE.format(n=number),
                    "content_hash": surfaces["canonical"],
                    "gt_commitment": entry.get("gt_commitment"),
                }
            ),
        )
        artifacts[TEST_ID_TEMPLATE.format(n=number)] = artifact
    if not artifacts:
        raise ValueError("package carries no registered cases")
    return artifacts


def load_case_contents(
    package: Mapping[str, Any],
    *,
    case_area: "str | Path" = CASE_AREA,
) -> "dict[str, dict]":
    """Load the PROTECTED content of every registered case, keyed by test_id.

    Protected context only: the caller (scientific launcher / classifier)
    must never persist these contents.
    """
    candidates_dir = Path(case_area) / "qualification" / "candidates"
    contents: "dict[str, dict]" = {}
    for entry in package.get("cases") or []:
        number = int(str(entry["test_id"]).rsplit("-", 1)[-1])
        candidate = load_json(candidates_dir / f"{entry['candidate_id']}.json")
        contents[TEST_ID_TEMPLATE.format(n=number)] = candidate["content"]
    return contents


def protected_ground_truth(content: Mapping[str, Any]) -> dict:
    """The sealed ground-truth view for the in-process classifier."""
    return {
        "premises": list(content.get("premises") or []),
        "question": content.get("question", ""),
        "ground_truth": content.get("ground_truth"),
        "intended_correct_answers": content.get("intended_correct_answers"),
        "derivations": content.get("derivations"),
    }


def candidate_manifest_index(manifest: Mapping[str, Any], population_id: str) -> "dict[str, str]":
    """Extract the candidate_index of one population namespace manifest."""
    population = next(
        (p for p in manifest.get("populations", []) if p.get("population_id") == population_id),
        None,
    )
    if population is None or "candidate_index" not in population:
        raise ValueError(f"population {population_id} not found in manifest")
    return dict(population["candidate_index"])


__all__ = [
    "CASE_AREA",
    "PRESENTATION_RULE",
    "candidate_manifest_index",
    "load_case_contents",
    "load_registered_cases",
    "protected_ground_truth",
]
