"""Case-candidate extraction from the M3-CA0 candidate case-set format.

This module is the **format adapter** of the M3-CA0 case review pipeline: it
parses the delivered candidate case-set document (markdown-like, fenced
``text`` blocks, ``CASE ID:`` separated) into canonical
``case-candidate`` documents (schema 0.3.0) that the review engine
(:mod:`ecp.review`) consumes. It is deliberately dumb and faithful:

- every authored section is retained (multiple INTENDED_CORRECT_ANSWER /
  DERIVATION blocks are ALL kept — anomalies are surfaced downstream,
  never reconciled or dropped here);
- each candidate keeps its verbatim ``raw_block`` so the engine can verify
  the candidate → source chain byte-exactly (R6);
- a **coverage check** accounts for every line of the source document
  (cases, separators, fences, tail blocks) so no content can be silently
  dropped during extraction;
- extraction is a pure function of (source bytes, provenance sidecar):
  no wall-clock, no randomness, no network — re-extraction reproduces
  byte-identical candidate documents.

Provenance (author, provider, acquisition, transformation history, honest
NOT-AVAILABLE fields) comes from a **provenance sidecar** supplied by the
operator (transcribed from the delivery/source report); this module never
invents provenance values. The sidecar's acquisition hash must match the
actual source document or extraction fails loudly.

This is review-layer infrastructure only: nothing here executes models,
calls providers, registers cases, or touches the public ledger.
"""

import re
from pathlib import Path

from .canonical import canonical_bytes
from .hashing import hash_document, sha256_hex

#: Source format identifier recorded in every extracted candidate.
SOURCE_FORMAT = "M3-CA0-case-set-md-1"

#: Extraction identity recorded in the extraction report.
EXTRACTOR_ID = "ECP-CANDIDATE-EXTRACTOR-1"

SECTION_LABELS = (
    "PROPOSED_REASONING_FAMILY",
    "STRUCTURAL_SIGNATURE",
    "PREMISES",
    "QUESTION",
    "INTENDED_CORRECT_ANSWER",
    "DERIVATION",
    "DIFFICULTY",
    "RETRIEVAL_RISK",
    "AMBIGUITY_RISK",
    "STRUCTURAL_UNIQUENESS_RATIONALE",
    "SELF_REVIEW",
)

#: Labels allowed to occur more than once per case (authored anomaly class).
MULTI_LABELS = ("INTENDED_CORRECT_ANSWER", "DERIVATION")

SELF_REVIEW_KEYS = (
    "Derivable",
    "Unique",
    "Self-contained",
    "No external knowledge",
    "No real-world entity dependency",
    "Structurally distinct",
)

DIFFICULTY_VALUES = ("SHALLOW", "MEDIUM", "DEEP")

SIDECAR_REQUIRED_KEYS = (
    "authored_by",
    "authored_at",
    "information_boundary",
    "acquisition",
    "transformation_history",
    "provenance_completeness",
)

_CASE_HEADER_RE = re.compile(r"^CASE ID: (.+?)\s*$")
_LABEL_RE = re.compile(r"^([A-Z][A-Z_]*):\s*(.*)$")
_PREMISE_RE = re.compile(r"^(\d+)\.\s+(.*)$")
_SEPARATOR_RE = re.compile(r"^---\s*$")
_FENCE_RE = re.compile(r"^```")


class ExtractionError(Exception):
    """Extraction failed loudly (contradiction, malformed structure)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# --- text normalization (shared with the review engine) ---------------------


def normalize_text(text: str) -> str:
    """Lossy normalization for equivalence checks: NFKC, lowercase, all
    non-alphanumeric runs collapsed to single spaces, trimmed."""
    import unicodedata

    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return normalized.strip()


def normalize_tokens(text: str) -> "list[str]":
    """Token list of :func:`normalize_text`."""
    return normalize_text(text).split()


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


def parse_case_set(text: str) -> dict:
    """Parse the raw text of an M3-CA0 candidate case-set document.

    Returns:
        ``{cases, tail_blocks, coverage}`` where

        - ``cases`` is a list of
          ``{case_id, source_position, raw_block, sections}`` — ``sections``
          maps label -> list of block dicts ``{text, block_index, lines}``
          (order of occurrence, 1-based block index per label);
        - ``tail_blocks`` are the non-case trailing sections
          (``AUTHORING PROVENANCE``, ``CASE SET SUMMARY``);
        - ``coverage`` is ``{status, total_lines, accounted_lines,
          unaccounted_lines}`` — every line of the document must be
          accounted for (case headers, section labels, section bodies,
          separators, fences, tail blocks).
    """
    lines = text.split("\n")
    cases: "list[dict]" = []
    tail_blocks: "list[dict]" = []
    unaccounted: "list[int]" = []

    current_case = None  # dict when inside a case
    current_tail = None  # dict when inside a tail block
    in_tail = False

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r")

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
                # separator terminates the current case / tail block
                current_case = None
                current_tail = None
                in_tail = False
                continue
            unaccounted.append(lineno)
            continue

        if _FENCE_RE.match(line):
            # opening/closing code fences are structural, always accounted
            continue

        # inside a case?
        if current_case is not None:
            current_case["raw_lines"].append(line)
            label_match = _LABEL_RE.match(line)
            if label_match and label_match.group(1) in SECTION_LABELS:
                label = label_match.group(1)
                blocks = current_case["sections"].setdefault(label, [])
                blocks.append(
                    {"lines": [], "block_index": len(blocks) + 1, "first_line": lineno}
                )
                current_case["open"] = blocks[-1]
                remainder = label_match.group(2)
                if remainder.strip():
                    blocks[-1]["lines"].append(remainder)
                continue
            if label_match and label_match.group(1) not in SECTION_LABELS:
                # unknown label: recorded as anomaly, still accounted
                current_case.setdefault("unknown_labels", []).append(
                    {"label": label_match.group(1), "line": lineno}
                )
                continue
            # content line -> the explicitly open block (last label seen)
            open_block = current_case.get("open")
            if open_block is not None:
                open_block["lines"].append(line)
            elif line.strip():
                # non-blank free text before any label: keep it visible
                current_case.setdefault("pre_label_lines", []).append(
                    {"line": lineno, "text": line}
                )
            continue

        # not inside a case: tail material (before/after cases) or blank
        if not line.strip():
            continue  # blank inter-block lines are accounted
        tail_title = re.match(r"^(AUTHORING PROVENANCE|CASE SET SUMMARY)\s*$", line)
        if tail_title:
            in_tail = True
            current_tail = {
                "title": tail_title.group(1),
                "lines": [],
                "first_line": lineno,
            }
            tail_blocks.append(current_tail)
            continue
        tail_label = _LABEL_RE.match(line)
        title = tail_label.group(1) if tail_label else None
        if title in ("AUTHORING PROVENANCE", "CASE SET SUMMARY"):
            in_tail = True
            current_tail = {
                "title": title,
                "lines": [tail_label.group(2)] if tail_label.group(2).strip() else [],
                "first_line": lineno,
            }
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
        "unaccounted_lines": unaccounted,
    }

    # finalize cases
    for case in cases:
        case["raw_block"] = "\n".join(case.pop("raw_lines"))
        sections = {}
        for label, blocks in case["sections"].items():
            sections[label] = [
                {
                    "text": _join_block(block["lines"]),
                    "block_index": block["block_index"],
                    "first_line": block["first_line"],
                }
                for block in blocks
            ]
        case["sections"] = sections

    for tail in tail_blocks:
        tail["text"] = _join_block(tail.pop("lines"))

    return {"cases": cases, "tail_blocks": tail_blocks, "coverage": coverage}


def _open_block(case: dict) -> "dict | None":
    """The explicitly open section block of *case* (last label seen)."""
    return case.get("open")


# --- provenance sidecar handling --------------------------------------------


def validate_sidecar(sidecar: dict) -> "list[str]":
    """Required-key and shape issues for a provenance sidecar (issue list)."""
    issues: "list[str]" = []
    if not isinstance(sidecar, dict):
        return ["sidecar: expected a JSON object"]
    for key in SIDECAR_REQUIRED_KEYS:
        if key not in sidecar:
            issues.append(f"sidecar: missing required key {key!r}")
    acquisition = sidecar.get("acquisition")
    if isinstance(acquisition, dict):
        for sub in ("label", "sha256", "acquired_at"):
            if sub not in acquisition:
                issues.append(f"sidecar.acquisition: missing {sub!r}")
    completeness = sidecar.get("provenance_completeness")
    if isinstance(completeness, dict):
        for sub in ("status", "not_available"):
            if sub not in completeness:
                issues.append(f"sidecar.provenance_completeness: missing {sub!r}")
    return issues


# --- extraction --------------------------------------------------------------


def _self_review_value(block_text: str) -> "tuple[dict, list[str]]":
    """Parse a SELF_REVIEW block into the six verbatim Yes/No items.

    Authored lines may carry an explanation after the Yes/No value (e.g.
    ``- Derivable: Yes, the conclusion follows ...``); the value is parsed
    and the explanation remains retained verbatim in the candidate's
    ``raw_block`` (the canonical record keeps every authored byte).
    """
    values: "dict[str, str]" = {}
    anomalies: "list[str]" = []
    for line in block_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^-\s*(.+?):\s*(Yes|No)\b.*$", line)
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
                anomalies.append(f"self_review: unexpected item {key!r}")
        else:
            anomalies.append(f"self_review: unparsable line {line[:60]!r}")
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
            anomalies.append(f"self_review: missing item {key!r} recorded as No")
    return values, anomalies


def _parse_premises(block_text: str) -> "tuple[list[str], list[str]]":
    """Parse a PREMISES block into numbered premise strings.

    Numbered lines (``N. text``) start premises; indented continuation
    lines (including bullet sub-items such as ``*   Record R1: ...``)
    append to the preceding premise (bullet markers are formatting and
    are stripped; the verbatim text always remains in ``raw_block``).
    Unindented non-numbered text is an anomaly, never silently dropped.
    """
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
            # indented continuation / bullet sub-item of the last premise
            stripped = re.sub(r"^\s*[*\-]\s*", "", line).strip()
            if premises:
                if stripped:
                    premises[-1] = premises[-1] + "\n" + stripped
            else:
                anomalies.append(
                    f"premises: indented line before any numbered premise "
                    f"{line.strip()[:60]!r}"
                )
            continue
        anomalies.append(f"premises: non-numbered line {line.strip()[:60]!r}")
    return premises, anomalies


def build_candidate(
    parsed_case: dict,
    source_label: str,
    source_sha256: str,
    provenance: dict,
    candidate_id: str,
    content_class: str = "review",
    protocol_version: str = "0.3.0",
    schema_version: str = "0.3.0",
) -> "tuple[dict, list[str]]":
    """Build one ``case-candidate`` document from a parsed case block.

    Returns (candidate_document, anomalies). The document embeds the
    verbatim raw_block, the provenance block, the parsed content, and the
    deterministic content hash. Anomalies are recorded, never silently
    resolved.
    """
    sections = parsed_case["sections"]
    anomalies: "list[str]" = []

    def single(label: str) -> str:
        blocks = sections.get(label, [])
        if len(blocks) != 1:
            anomalies.append(
                f"{label}: expected exactly 1 block, found {len(blocks)}"
            )
            if not blocks:
                return ""
            return blocks[0]["text"]
        return blocks[0]["text"]

    family = single("PROPOSED_REASONING_FAMILY")
    signature = single("STRUCTURAL_SIGNATURE")
    question = single("QUESTION")
    difficulty = single("DIFFICULTY").strip()
    retrieval_risk = single("RETRIEVAL_RISK")
    ambiguity_risk = single("AMBIGUITY_RISK")
    rationale = single("STRUCTURAL_UNIQUENESS_RATIONALE")

    if difficulty not in DIFFICULTY_VALUES:
        anomalies.append(f"DIFFICULTY: value {difficulty!r} not in {DIFFICULTY_VALUES}")

    premises, premise_anomalies = _parse_premises(single("PREMISES"))
    anomalies.extend(premise_anomalies)

    answers = [
        {"value": block["text"], "source_block": block["block_index"]}
        for block in sections.get("INTENDED_CORRECT_ANSWER", [])
    ]
    derivations = [
        {"raw": block["text"], "source_block": block["block_index"]}
        for block in sections.get("DERIVATION", [])
    ]
    if not answers:
        anomalies.append("INTENDED_CORRECT_ANSWER: no block found")
    if not derivations:
        anomalies.append("DERIVATION: no block found")

    self_review, self_review_anomalies = _self_review_value(single("SELF_REVIEW"))
    anomalies.extend(self_review_anomalies)

    for label in MULTI_LABELS:
        blocks = sections.get(label, [])
        if len(blocks) > 1:
            anomalies.append(
                f"{label}: {len(blocks)} blocks retained (authored anomaly; "
                "all blocks kept, review engine flags the case)"
            )

    for unknown in parsed_case.get("unknown_labels", []):
        anomalies.append(
            f"unknown label {unknown['label']!r} at line {unknown['line']}"
        )
    for pre in parsed_case.get("pre_label_lines", []):
        anomalies.append(
            f"free text before first label at line {pre['line']}: {pre['text'][:40]!r}"
        )

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
    }

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
                "format": SOURCE_FORMAT,
            },
        },
        "raw_block": parsed_case["raw_block"],
        "provenance": provenance,
        "content": content,
        "content_hash": hash_document(content),
        "protocol_version": protocol_version,
        "schema_version": schema_version,
    }
    return candidate, anomalies


def extract_candidates(
    source_path: "str | Path",
    sidecar: dict,
    source_label: "str | None" = None,
    candidate_prefix: str = "ECP-CAND",
    content_class: str = "review",
    protocol_version: str = "0.3.0",
) -> "tuple[list[dict], dict]":
    """Extract case-candidate documents from *source_path*.

    The sidecar's ``acquisition.sha256`` must equal the actual source-file
    hash (contradiction = loud failure). Returns (candidates, report); the
    report records coverage, per-case anomalies, the tail blocks and the
    extractor identity. Deterministic: a pure function of the source bytes
    and the sidecar content.
    """
    source_file = Path(source_path)
    source_bytes = source_file.read_bytes()
    source_sha = sha256_hex(source_bytes)
    text = source_bytes.decode("utf-8")
    source_label = source_label or source_file.name

    sidecar_issues = validate_sidecar(sidecar)
    if sidecar_issues:
        raise ExtractionError("; ".join(sidecar_issues))

    declared = sidecar.get("acquisition", {}).get("sha256")
    if declared != source_sha:
        raise ExtractionError(
            f"provenance sidecar acquisition sha256 {declared!r} does not match "
            f"the actual source document hash {source_sha!r}"
        )

    parsed = parse_case_set(text)
    if parsed["coverage"]["status"] != "PASS":
        raise ExtractionError(
            "source coverage check FAILED: "
            f"{parsed['coverage']['unaccounted_lines'][:10]} lines unaccounted "
            "(extraction refuses to silently drop content)"
        )

    case_flags: "dict[str, list[str]]" = sidecar.get("candidate_flags") or {}
    candidates: "list[dict]" = []
    all_anomalies: "list[dict]" = []
    for parsed_case in parsed["cases"]:
        index = parsed_case["source_position"]
        candidate_id = f"{candidate_prefix}-{index:06d}"
        provenance = dict(sidecar)
        provenance.pop("candidate_flags", None)
        flags = list(case_flags.get(parsed_case["case_id"], []))
        if flags:
            provenance["candidate_flags"] = flags
        candidate, anomalies = build_candidate(
            parsed_case,
            source_label=source_label,
            source_sha256=source_sha,
            provenance=provenance,
            candidate_id=candidate_id,
            content_class=content_class,
            protocol_version=protocol_version,
        )
        candidates.append(candidate)
        if anomalies:
            all_anomalies.append(
                {"case_id": parsed_case["case_id"], "anomalies": anomalies}
            )

    report = {
        "extractor": EXTRACTOR_ID,
        "source": {
            "label": source_label,
            "sha256": source_sha,
            "format": SOURCE_FORMAT,
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
