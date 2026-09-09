"""Authored case-set intake for format ``M3-CA0V1-case-set-md-2`` (M3-CA0 v1).

This module is the **format adapter** of the M3-CA0 v1 authoring layer: it
parses an authored candidate case-set document (format 2 — the structured
extension of the original M3-CA0 case-set format with expected-property,
ground-truth, forbidden-shortcuts, formal verification, representation-bias
disclosure and environmental pre-check sections) into canonical
``case-candidate`` documents (schema 0.5.0) that the qualification engine
(:mod:`ecp.qualification`) consumes.

Like :mod:`ecp.candidates` (format 1) it is deliberately dumb and faithful:

- every authored section is retained verbatim in ``raw_block`` so the engine
  can verify the candidate → source chain byte-exactly;
- a **coverage check** accounts for every line of the source document so no
  content can be silently dropped during extraction;
- the FORMAL section is captured as fenced JSON text and parsed loudly
  (malformed JSON is an extraction failure, never silently repaired);
- extraction is a pure function of (source bytes, provenance sidecar): no
  wall-clock, no randomness, no network — re-extraction reproduces
  byte-identical candidate documents;
- the sidecar's acquisition hash must match the actual source document or
  extraction fails loudly.

The provenance sidecar additionally carries the order §3
``authoring_independence`` record (author identity, environment, model/tool,
prompt/instructions, information available/unavailable, relationships,
explicit independence status). The parser transcribes it verbatim; it never
invents, upgrades, or reinterprets independence claims.

This is authoring-layer infrastructure only: nothing here executes models,
calls providers, registers cases, or touches the public ledger.
"""

import json
import re
from pathlib import Path

from .canonical import canonical_bytes
from .hashing import hash_document, sha256_hex
from .candidates import normalize_text, validate_sidecar

#: Source format identifier recorded in every extracted candidate.
SOURCE_FORMAT_V2 = "M3-CA0V1-case-set-md-2"

#: Extraction identity recorded in the intake report.
EXTRACTOR_ID_V2 = "ECP-AUTHORING-INTAKE-2"

#: Section labels of the format-2 case block.
SECTION_LABELS_V2 = (
    "PROPOSED_REASONING_FAMILY",
    "STRUCTURAL_SIGNATURE",
    "PREMISES",
    "QUESTION",
    "EXPECTED_PROPERTY",
    "INTENDED_CORRECT_ANSWER",
    "DERIVATION",
    "GROUND_TRUTH_CLASS",
    "GROUND_TRUTH_STATEMENT",
    "GROUND_TRUTH_AMBIGUITY_NOTE",
    "FORBIDDEN_SHORTCUTS",
    "FORMAL",
    "DIFFICULTY",
    "RETRIEVAL_RISK",
    "AMBIGUITY_RISK",
    "STRUCTURAL_UNIQUENESS_RATIONALE",
    "REPRESENTATION_BIAS_DISCLOSURE",
    "ENVIRONMENTAL_PRE_CHECK",
    "SELF_REVIEW",
)

#: Labels allowed to occur more than once per case (authored anomaly class).
MULTI_LABELS_V2 = ("INTENDED_CORRECT_ANSWER", "DERIVATION")

#: Sub-block keys of the representation-bias disclosure (order §9).
REPRESENTATION_BIAS_KEYS = ("STATUS", "EVIDENCE", "KNOWN_LIMITATION")

#: Sub-block keys of the environmental pre-check (order §10).
ENVIRONMENTAL_PRE_CHECK_KEYS = (
    "KNOWLEDGE_SOURCES",
    "FIXTURES",
    "IMPLEMENTATION_ARTIFACTS",
    "MEMORY_PATHS",
    "MODEL_ACCESS_PATHS",
    "ANSWER_BEARING_ARTIFACTS",
)

SELF_REVIEW_KEYS = (
    "Derivable",
    "Unique",
    "Self-contained",
    "No external knowledge",
    "No real-world entity dependency",
    "Structurally distinct",
)

GT_CLASSES = ("DERIVABLE", "CONTRADICTED", "IMPOSSIBLE", "INDETERMINATE")
DIFFICULTY_VALUES = ("SHALLOW", "MEDIUM", "DEEP")

#: Required keys of the order §3 authoring-independence sidecar block.
INDEPENDENCE_REQUIRED_KEYS = (
    "author_identity",
    "authoring_environment",
    "model_tool",
    "model_version",
    "prompt_instructions",
    "information_available",
    "information_unavailable",
    "relationship_to_ecp_developers",
    "relationship_to_evaluated_systems",
    "access_to_prior_ecp_results",
    "independence_status",
    "validation_procedure",
    "independence_limitations",
)

_CASE_HEADER_RE = re.compile(r"^CASE ID: (.+?)\s*$")
_LABEL_RE = re.compile(r"^([A-Z][A-Z_]*):\s*(.*)$")
_PREMISE_RE = re.compile(r"^(\d+)\.\s+(.*)$")
_BULLET_RE = re.compile(r"^-\s+(.*)$")
_SUBKEY_RE = re.compile(r"^([A-Z][A-Z_]+):\s*(.*)$")
_SELF_REVIEW_RE = re.compile(r"^-\s*(.+?):\s*(Yes|No)\b.*$")
_SEPARATOR_RE = re.compile(r"^---\s*$")
_FENCE_OPEN_RE = re.compile(r"^```(\w*)\s*$")
_FENCE_CLOSE_RE = re.compile(r"^```\s*$")
_TAIL_RE = re.compile(r"^(AUTHORING PROVENANCE|CASE SET SUMMARY)\s*$")


class ExtractionError(Exception):
    """Extraction failed loudly (contradiction, malformed structure)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _join_block(lines: "list[str]") -> str:
    """Join the lines of one section block, trimming leading/trailing blank
    lines but preserving interior structure verbatim."""
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


# --- source document parsing ------------------------------------------------


def parse_case_set_v2(text: str) -> dict:
    """Parse the raw text of a format-2 candidate case-set document.

    Returns ``{cases, tail_blocks, coverage}`` — same shape as the format-1
    parser, with ``sections[label] = [{text, block_index, first_line}]``
    plus fenced-JSON capture for FORMAL and sub-key capture for the
    disclosure blocks. Every line of the document must be accounted for.
    """
    lines = text.split("\n")
    cases: "list[dict]" = []
    tail_blocks: "list[dict]" = []
    header_lines: "list[int]" = []
    unaccounted: "list[int]" = []

    current_case = None
    current_tail = None
    in_tail = False
    in_fence = False
    fence_lang = ""
    fence_lines: "list[str]" = []

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r")

        # fence handling: inside a fence everything is content until close.
        # Fence lines are ALSO retained in the case's raw_lines so the
        # candidate -> source chain stays byte-exact (provenance integrity).
        if in_fence:
            if current_case is not None:
                current_case["raw_lines"].append(line)
            if _FENCE_CLOSE_RE.match(line):
                # closing fence terminates the open FORMAL block
                open_block = current_case.get("open") if current_case else None
                if open_block is not None:
                    open_block["fence"] = "\n".join(fence_lines)
                    open_block["fence_lang"] = fence_lang
                    current_case["open"] = None
                in_fence = False
            else:
                fence_lines.append(line)
            continue
        fence_open = _FENCE_OPEN_RE.match(line)
        if fence_open:
            open_block = current_case.get("open") if current_case else None
            if open_block is not None and open_block.get("label") == "FORMAL":
                if current_case is not None:
                    current_case["raw_lines"].append(line)
                in_fence = True
                fence_lang = fence_open.group(1)
                fence_lines = []
                continue
            # a fence outside a FORMAL section is structural/unaccounted
            unaccounted.append(lineno)
            continue

        header = _CASE_HEADER_RE.match(line)
        if header and not in_tail:
            current_case = {
                "case_id": header.group(1),
                "source_position": len(cases) + 1,
                "raw_lines": [line],
                "sections": {},
                "first_line": lineno,
            }
            cases.append(current_case)
            current_tail = None
            continue

        if _SEPARATOR_RE.match(line):
            if current_case is not None or current_tail is not None:
                current_case = None
                current_tail = None
                in_tail = False
                continue
            unaccounted.append(lineno)
            continue

        # inside a case?
        if current_case is not None:
            current_case["raw_lines"].append(line)
            label_match = _LABEL_RE.match(line)
            if label_match and label_match.group(1) in SECTION_LABELS_V2:
                label = label_match.group(1)
                blocks = current_case["sections"].setdefault(label, [])
                blocks.append(
                    {
                        "label": label,
                        "lines": [],
                        "block_index": len(blocks) + 1,
                        "first_line": lineno,
                    }
                )
                current_case["open"] = blocks[-1]
                remainder = label_match.group(2)
                if remainder.strip():
                    blocks[-1]["lines"].append(remainder)
                continue
            if label_match and label_match.group(1) not in SECTION_LABELS_V2:
                # unknown label: sub-key of an open disclosure block?
                sub_match = _SUBKEY_RE.match(line)
                open_block = current_case.get("open")
                if (
                    sub_match
                    and open_block is not None
                    and open_block.get("label") in ("REPRESENTATION_BIAS_DISCLOSURE", "ENVIRONMENTAL_PRE_CHECK")
                    and sub_match.group(1) in REPRESENTATION_BIAS_KEYS + ENVIRONMENTAL_PRE_CHECK_KEYS
                ):
                    open_block.setdefault("sub", []).append((sub_match.group(1), sub_match.group(2)))
                    continue
                current_case.setdefault("unknown_labels", []).append(
                    {"label": label_match.group(1), "line": lineno}
                )
                continue
            # content line -> the explicitly open block (last label seen)
            open_block = current_case.get("open")
            if open_block is not None:
                open_block["lines"].append(line)
            elif line.strip():
                current_case.setdefault("pre_label_lines", []).append(
                    {"line": lineno, "text": line}
                )
            continue

        # not inside a case: header (before any case), tail material, or blank
        if not line.strip():
            continue
        if not cases and not in_tail:
            # document header (title/preamble before the first CASE ID):
            # accounted verbatim, never dropped
            header_lines.append(lineno)
            continue
        tail_title = _TAIL_RE.match(line)
        if tail_title:
            in_tail = True
            current_tail = {"title": tail_title.group(1), "lines": [], "first_line": lineno}
            tail_blocks.append(current_tail)
            continue
        if current_tail is not None:
            current_tail["lines"].append(line)
            continue
        unaccounted.append(lineno)

    total = len(lines)
    accounted = total - len(unaccounted)
    coverage = {
        "status": "PASS" if not unaccounted else "FAIL",
        "total_lines": total,
        "accounted_lines": accounted,
        "header_lines": header_lines,
        "unaccounted_lines": unaccounted,
    }

    for case in cases:
        case["raw_block"] = "\n".join(case.pop("raw_lines"))
        sections = {}
        for label, blocks in case["sections"].items():
            sections[label] = [
                {
                    "text": _join_block(block["lines"]),
                    "fence": block.get("fence"),
                    "fence_lang": block.get("fence_lang"),
                    "sub": dict(block.get("sub", [])),
                    "block_index": block["block_index"],
                    "first_line": block["first_line"],
                }
                for block in blocks
            ]
        case["sections"] = sections

    for tail in tail_blocks:
        tail["text"] = _join_block(tail.pop("lines"))

    return {"cases": cases, "tail_blocks": tail_blocks, "coverage": coverage}


# --- section-level parsing helpers ------------------------------------------


def _single(sections: dict, label: str, anomalies: "list[str]", case_id: str) -> str:
    blocks = sections.get(label, [])
    if len(blocks) != 1:
        anomalies.append(
            f"{case_id}: {label}: expected exactly 1 block, found {len(blocks)}"
        )
        if not blocks:
            return ""
        if len(blocks) > 1:
            anomalies.append(
                f"{case_id}: {label}: {len(blocks)} blocks retained (authored anomaly; "
                "all blocks kept, qualification engine flags the case)"
            )
        return blocks[0]["text"]
    return blocks[0]["text"]


def _parse_premises(block_text: str, case_id: str) -> "tuple[list[str], list[str]]":
    premises: "list[str]" = []
    anomalies: "list[str]" = []
    for raw in block_text.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        match = _PREMISE_RE.match(line.strip())
        if match:
            premises.append(match.group(2).strip())
            continue
        if raw[:1] in (" ", "\t"):
            stripped = re.sub(r"^\s*[*\-]\s*", "", line).strip()
            if premises:
                if stripped:
                    premises[-1] = premises[-1] + "\n" + stripped
            else:
                anomalies.append(
                    f"{case_id}: premises: indented line before any numbered premise {line.strip()[:60]!r}"
                )
            continue
        anomalies.append(f"{case_id}: premises: non-numbered line {line.strip()[:60]!r}")
    return premises, anomalies


def _parse_bullets(block_text: str, case_id: str, label: str) -> "tuple[list[str], list[str]]":
    items: "list[str]" = []
    anomalies: "list[str]" = []
    for raw in block_text.split("\n"):
        if not raw.strip():
            continue
        match = _BULLET_RE.match(raw.strip())
        if match:
            items.append(match.group(1).strip())
        else:
            anomalies.append(f"{case_id}: {label}: non-bullet line {raw.strip()[:60]!r}")
    return items, anomalies


def _parse_self_review(block_text: str, case_id: str) -> "tuple[dict, list[str]]":
    values: "dict[str, str]" = {}
    anomalies: "list[str]" = []
    for line in block_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = _SELF_REVIEW_RE.match(line)
        if match:
            key, value = match.group(1), match.group(2)
            if key in SELF_REVIEW_KEYS:
                snake = {
                    "Derivable": "derivable",
                    "Unique": "unique",
                    "Self-contained": "self_contained",
                    "No external knowledge": "no_external_knowledge",
                    "No real-world entity dependency": "no_real_world_dependency",
                    "Structurally distinct": "structurally_distinct",
                }[key]
                values[snake] = value
            else:
                anomalies.append(f"{case_id}: self_review: unexpected item {key!r}")
        else:
            anomalies.append(f"{case_id}: self_review: unparsable line {line[:60]!r}")
    for key in SELF_REVIEW_KEYS:
        snake = {
            "Derivable": "derivable",
            "Unique": "unique",
            "Self-contained": "self_contained",
            "No external knowledge": "no_external_knowledge",
            "No real-world entity dependency": "no_real_world_dependency",
            "Structurally distinct": "structurally_distinct",
        }[key]
        if snake not in values:
            values[snake] = "No"
            anomalies.append(f"{case_id}: self_review: missing item {key!r} recorded as No")
    return values, anomalies


def _parse_sub_block(sections: dict, label: str, case_id: str, keys: tuple) -> "tuple[dict, list[str]]":
    blocks = sections.get(label, [])
    if len(blocks) != 1:
        return {}, [f"{case_id}: {label}: expected exactly 1 block, found {len(blocks)}"]
    sub = blocks[0].get("sub", {})
    parsed = {}
    anomalies = []
    for key in keys:
        if key in sub:
            parsed[key.lower()] = sub[key].strip()
        else:
            anomalies.append(f"{case_id}: {label}: missing sub-key {key}")
    return parsed, anomalies


# --- extraction --------------------------------------------------------------


def validate_sidecar_v2(sidecar: dict) -> "list[str]":
    """Required-key and shape issues for a format-2 provenance sidecar."""
    issues = validate_sidecar(sidecar)
    if not isinstance(sidecar, dict):
        return issues
    independence = sidecar.get("authoring_independence")
    if not isinstance(independence, dict):
        issues.append("sidecar: missing 'authoring_independence' block (order §3 record)")
        return issues
    for key in INDEPENDENCE_REQUIRED_KEYS:
        if key not in independence:
            issues.append(f"sidecar.authoring_independence: missing {key!r}")
    status = independence.get("independence_status")
    if isinstance(status, dict):
        if "label" not in status:
            issues.append("sidecar.authoring_independence.independence_status: missing 'label'")
    elif status is not None and not isinstance(status, str):
        issues.append("sidecar.authoring_independence.independence_status: expected object or string")
    return issues


def build_candidate_v2(
    parsed_case: dict,
    source_label: str,
    source_sha256: str,
    provenance: dict,
    candidate_id: str,
    content_class: str = "review",
    protocol_version: str = "0.5.0",
    schema_version: str = "0.5.0",
    authoring_independence: "dict | None" = None,
) -> "tuple[dict, list[str]]":
    """Build one format-2 ``case-candidate`` document (0.5.0).

    Returns (candidate_document, anomalies). Anomalies are recorded, never
    silently resolved. The FORMAL fence must parse as JSON; a malformed
    formal layer is a loud extraction failure (the case cannot be admitted
    to qualification with a corrupt verification layer).
    """
    sections = parsed_case["sections"]
    case_id = parsed_case["case_id"]
    anomalies: "list[str]" = []

    family = _single(sections, "PROPOSED_REASONING_FAMILY", anomalies, case_id)
    signature = _single(sections, "STRUCTURAL_SIGNATURE", anomalies, case_id)
    question = _single(sections, "QUESTION", anomalies, case_id)
    expected_property = _single(sections, "EXPECTED_PROPERTY", anomalies, case_id)
    gt_class = _single(sections, "GROUND_TRUTH_CLASS", anomalies, case_id).strip()
    gt_statement = _single(sections, "GROUND_TRUTH_STATEMENT", anomalies, case_id)
    # GROUND_TRUTH_AMBIGUITY_NOTE is optional: present only for
    # designed-indeterminate cases (order §6 ambiguity reporting)
    ambiguity_blocks = sections.get("GROUND_TRUTH_AMBIGUITY_NOTE", [])
    ambiguity_note = ""
    if len(ambiguity_blocks) > 1:
        anomalies.append(
            f"{case_id}: GROUND_TRUTH_AMBIGUITY_NOTE: {len(ambiguity_blocks)} blocks "
            "(all kept; qualification engine flags the case)"
        )
    if ambiguity_blocks:
        ambiguity_note = ambiguity_blocks[0]["text"]
    difficulty = _single(sections, "DIFFICULTY", anomalies, case_id).strip()
    retrieval_risk = _single(sections, "RETRIEVAL_RISK", anomalies, case_id)
    ambiguity_risk = _single(sections, "AMBIGUITY_RISK", anomalies, case_id)
    rationale = _single(sections, "STRUCTURAL_UNIQUENESS_RATIONALE", anomalies, case_id)

    if gt_class not in GT_CLASSES:
        anomalies.append(f"{case_id}: GROUND_TRUTH_CLASS: value {gt_class!r} not in {GT_CLASSES}")
    if difficulty not in DIFFICULTY_VALUES:
        anomalies.append(f"{case_id}: DIFFICULTY: value {difficulty!r} not in {DIFFICULTY_VALUES}")

    premises, premise_anomalies = _parse_premises(
        _single(sections, "PREMISES", anomalies, case_id), case_id
    )
    anomalies.extend(premise_anomalies)

    forbidden, forbidden_anomalies = _parse_bullets(
        _single(sections, "FORBIDDEN_SHORTCUTS", anomalies, case_id), case_id, "FORBIDDEN_SHORTCUTS"
    )
    anomalies.extend(forbidden_anomalies)
    if not forbidden:
        anomalies.append(f"{case_id}: FORBIDDEN_SHORTCUTS: no items found")

    answers = [
        {"value": block["text"], "source_block": block["block_index"]}
        for block in sections.get("INTENDED_CORRECT_ANSWER", [])
    ]
    derivations = [
        {"raw": block["text"], "source_block": block["block_index"]}
        for block in sections.get("DERIVATION", [])
    ]
    if not answers:
        anomalies.append(f"{case_id}: INTENDED_CORRECT_ANSWER: no block found")
    if not derivations:
        anomalies.append(f"{case_id}: DERIVATION: no block found")

    # FORMAL: fenced JSON (loud failure on malformed content)
    formal_blocks = sections.get("FORMAL", [])
    formal = None
    if len(formal_blocks) != 1:
        anomalies.append(f"{case_id}: FORMAL: expected exactly 1 block, found {len(formal_blocks)}")
    else:
        fence_text = formal_blocks[0].get("fence")
        if fence_text is None:
            anomalies.append(f"{case_id}: FORMAL: no fenced JSON block found")
        else:
            try:
                formal = json.loads(fence_text)
                if not isinstance(formal, dict):
                    anomalies.append(f"{case_id}: FORMAL: fenced content is not a JSON object")
                    formal = None
            except json.JSONDecodeError as exc:
                raise ExtractionError(
                    f"{case_id}: FORMAL: fenced JSON does not parse ({exc}); "
                    "a corrupt verification layer is never silently repaired"
                ) from exc

    self_review, self_review_anomalies = _parse_self_review(
        _single(sections, "SELF_REVIEW", anomalies, case_id), case_id
    )
    anomalies.extend(self_review_anomalies)

    representation_bias, rb_anomalies = _parse_sub_block(
        sections, "REPRESENTATION_BIAS_DISCLOSURE", case_id, REPRESENTATION_BIAS_KEYS
    )
    anomalies.extend(rb_anomalies)
    environmental, env_anomalies = _parse_sub_block(
        sections, "ENVIRONMENTAL_PRE_CHECK", case_id, ENVIRONMENTAL_PRE_CHECK_KEYS
    )
    anomalies.extend(env_anomalies)

    for label in MULTI_LABELS_V2:
        blocks = sections.get(label, [])
        if len(blocks) > 1:
            anomalies.append(
                f"{case_id}: {label}: {len(blocks)} blocks retained (authored anomaly; "
                "all blocks kept, qualification engine flags the case)"
            )
    for unknown in parsed_case.get("unknown_labels", []):
        anomalies.append(
            f"{case_id}: unknown label {unknown['label']!r} at line {unknown['line']}"
        )
    for pre in parsed_case.get("pre_label_lines", []):
        anomalies.append(
            f"{case_id}: free text before first label at line {pre['line']}: {pre['text'][:40]!r}"
        )

    ground_truth: "dict | None" = None
    if gt_class or gt_statement:
        ground_truth = {"class": gt_class, "statement": gt_statement}
        if ambiguity_note:
            ground_truth["ambiguity_note"] = ambiguity_note

    content = {
        "proposed_reasoning_family": family,
        "structural_signature": signature,
        "premises": premises,
        "question": question,
        "intended_correct_answers": answers,
        "derivations": derivations,
        "difficulty": difficulty,
        "retrieval_risk": retrieval_risk,
        "ambiguity_risk": ambiguity_risk,
        "structural_uniqueness_rationale": rationale,
        "self_review": self_review,
        "expected_property": expected_property,
        "forbidden_shortcuts": forbidden,
        "ground_truth": ground_truth,
        "formal": formal,
    }

    if authoring_independence is None:
        authoring_independence = provenance.get("authoring_independence")

    candidate = {
        "ecp_object": "case-candidate",
        "content_class": content_class,
        "candidate_id": candidate_id,
        "source": {
            "case_id": parsed_case["case_id"],
            "source_position": parsed_case["source_position"],
            "source_document": {
                "label": source_label,
                "sha256": source_sha256,
                "format": SOURCE_FORMAT_V2,
            },
        },
        "raw_block": parsed_case["raw_block"],
        "provenance": provenance,
        "authoring_independence": authoring_independence,
        "representation_bias_disclosure": representation_bias or None,
        "environmental_pre_check": environmental or None,
        "content": content,
        "content_hash": hash_document(content),
        "protocol_version": protocol_version,
        "schema_version": schema_version,
    }
    return candidate, anomalies


def extract_candidates_v2(
    source_path: "str | Path",
    sidecar: dict,
    source_label: "str | None" = None,
    candidate_offset: int = 100,
    content_class: str = "review",
    protocol_version: str = "0.5.0",
) -> "tuple[list[dict], dict]":
    """Extract format-2 case-candidate documents from *source_path*.

    The sidecar's ``acquisition.sha256`` must equal the actual source-file
    hash. Returns (candidates, report). Deterministic: a pure function of
    the source bytes and the sidecar content.
    """
    source_file = Path(source_path)
    source_bytes = source_file.read_bytes()
    source_sha = sha256_hex(source_bytes)
    text = source_bytes.decode("utf-8")
    source_label = source_label or source_file.name

    sidecar_issues = validate_sidecar_v2(sidecar)
    if sidecar_issues:
        raise ExtractionError("; ".join(sidecar_issues))

    declared = sidecar.get("acquisition", {}).get("sha256")
    if declared != source_sha:
        raise ExtractionError(
            f"provenance sidecar acquisition sha256 {declared!r} does not match "
            f"the actual source document hash {source_sha!r}"
        )

    parsed = parse_case_set_v2(text)
    if parsed["coverage"]["status"] != "PASS":
        raise ExtractionError(
            "source coverage check FAILED: "
            f"{parsed['coverage']['unaccounted_lines'][:10]} lines unaccounted "
            "(extraction refuses to silently drop content)"
        )

    case_flags: "dict[str, list[str]]" = sidecar.get("candidate_flags") or {}
    independence_record = sidecar.get("authoring_independence")
    candidates: "list[dict]" = []
    all_anomalies: "list[dict]" = []
    for parsed_case in parsed["cases"]:
        index = parsed_case["source_position"]
        candidate_id = f"ECP-CAND-{candidate_offset + index:06d}"
        provenance = dict(sidecar)
        provenance.pop("candidate_flags", None)
        provenance.pop("authoring_independence", None)
        flags = list(case_flags.get(parsed_case["case_id"], []))
        if flags:
            provenance["candidate_flags"] = flags
        candidate, anomalies = build_candidate_v2(
            parsed_case,
            source_label=source_label,
            source_sha256=source_sha,
            provenance=provenance,
            candidate_id=candidate_id,
            content_class=content_class,
            protocol_version=protocol_version,
            authoring_independence=independence_record,
        )
        candidates.append(candidate)
        if anomalies:
            all_anomalies.append(
                {"case_id": parsed_case["case_id"], "anomalies": anomalies}
            )

    report = {
        "extractor": EXTRACTOR_ID_V2,
        "source": {
            "label": source_label,
            "sha256": source_sha,
            "format": SOURCE_FORMAT_V2,
        },
        "cases_extracted": len(candidates),
        "candidate_ids": [c["candidate_id"] for c in candidates],
        "content_hashes": [c["content_hash"] for c in candidates],
        "coverage": parsed["coverage"],
        "per_case_anomalies": all_anomalies,
        "tail_blocks": {t["title"]: t["text"] for t in parsed["tail_blocks"]},
        "deterministic": "pure function of (source bytes, provenance sidecar)",
    }
    return candidates, report


def canonical_candidate_bytes(candidate: dict) -> bytes:
    """Canonical serialization of a candidate document (for file output)."""
    return canonical_bytes(candidate)
