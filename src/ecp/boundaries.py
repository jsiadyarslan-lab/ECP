"""Public/protected boundary enforcement.

The public Git repository is a provenance/distribution layer, NOT the
complete scientific trust boundary. This module machine-checks the rules
that keep it that way:

R1  the reserved directories (``cases/``, ``evaluation/``, ``evidence/``,
    ``verification/``) are empty at R0 — only ``README.md`` is allowed
    inside them;
R2  no ``ecp_object: "ground-truth"`` document outside ``examples/``;
R3  no document carrying ground-truth content keys (``expected_answer``,
    ``derivation``) outside ``examples/``;
R4  inside ``examples/``, ground-truth documents must be explicitly marked
    ``content_class: "format-illustration"`` (public dummy values);
R5  every ``case`` document must carry a ground-truth commitment
    (64 hex chars) — a public case never contains its own answer.

The scanner walks the repository tree (skipping dot-directories such as
``.git``) and returns a list of violation records. An empty list means the
public tree respects the boundary. This is an *infrastructural* check: it
says nothing about the scientific quality of any future case.
"""

import json
import re
from pathlib import Path

RESERVED_DIRS = ("cases", "evaluation", "evidence", "verification")
RESERVED_ALLOWED_FILES = {"README.md"}
GROUND_TRUTH_CONTENT_KEYS = (
    "expected_answer",
    "derivation",
    "intended_correct_answers",
    "derivations",
)
COMMITMENT_PATTERN = re.compile(r"^[0-9a-f]{64}$")

#: Review-layer object types (M3-CA0 + M3-CA0-A): they belong ONLY in a
#: private review area, never in the public repository (public
#: illustrations under examples/ must be content_class
#: 'format-illustration').
REVIEW_OBJECTS = (
    "case-candidate",
    "case-review",
    "review-run",
    "review-adjudication",
    "case-amendment",
)
#: Review-layer types that carry ground-truth-class content.
REVIEW_GT_CARRYING = ("case-candidate", "case-review")


def scan_repository(root: "str | Path") -> "list[dict]":
    """Scan the repository tree at *root* for boundary violations.

    Returns:
        A list of violation records
        ``{"rule": str, "path": str, "detail": str}`` (empty = clean).
    """
    root = Path(root)
    violations: "list[dict]" = []

    # R1 — reserved directories stay empty (README.md only).
    for directory in RESERVED_DIRS:
        reserved = root / directory
        if not reserved.is_dir():
            violations.append(
                {
                    "rule": "reserved-dir-missing",
                    "path": directory,
                    "detail": f"reserved directory {directory}/ does not exist",
                }
            )
            continue
        for entry in sorted(reserved.iterdir()):
            rel = f"{directory}/{entry.name}"
            if entry.is_dir():
                violations.append(
                    {
                        "rule": "reserved-dir-foreign-entry",
                        "path": rel,
                        "detail": "no subdirectories allowed in reserved directory at R0",
                    }
                )
            elif entry.name not in RESERVED_ALLOWED_FILES:
                violations.append(
                    {
                        "rule": "reserved-dir-foreign-file",
                        "path": rel,
                        "detail": "reserved directories must contain only README.md at R0",
                    }
                )

    # R2–R5 — walk all JSON documents outside dot-directories.
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        if any(part.startswith(".") for part in path.relative_to(root).parts[:-1]):
            continue  # skip .git and friends
        try:
            with open(path, "r", encoding="utf-8") as fh:
                document = json.load(fh)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            violations.append(
                {
                    "rule": "invalid-json",
                    "path": rel,
                    "detail": f"unparseable JSON: {exc}",
                }
            )
            continue
        if not isinstance(document, dict):
            continue

        in_examples = rel.startswith("examples/")
        is_gt_object = document.get("ecp_object") == "ground-truth"
        has_gt_keys = any(key in document for key in GROUND_TRUTH_CONTENT_KEYS)

        if (is_gt_object or has_gt_keys) and not in_examples:
            violations.append(
                {
                    "rule": "ground-truth-outside-examples",
                    "path": rel,
                    "detail": "protected ground-truth content is forbidden in the public tree outside examples/",
                }
            )
        elif in_examples and (is_gt_object or has_gt_keys):
            if document.get("content_class") != "format-illustration":
                violations.append(
                    {
                        "rule": "example-ground-truth-not-illustration",
                        "path": rel,
                        "detail": "ground-truth content under examples/ must be content_class 'format-illustration'",
                    }
                )

        if document.get("ecp_object") == "case":
            reference = document.get("ground_truth_reference")
            valid_commitment = (
                isinstance(reference, dict)
                and isinstance(reference.get("commitment"), str)
                and bool(COMMITMENT_PATTERN.match(reference["commitment"]))
            )
            if not valid_commitment:
                violations.append(
                    {
                        "rule": "case-missing-ground-truth-commitment",
                        "path": rel,
                        "detail": "public cases must carry a sha256 ground-truth commitment",
                    }
                )

        # R6/R7 — review-layer objects (M3-CA0) never appear in the public
        # repository outside examples/; inside examples/ the ground-truth
        # carrying ones must be explicit format illustrations.
        ecp_object = document.get("ecp_object")
        if ecp_object in REVIEW_OBJECTS:
            if not in_examples:
                violations.append(
                    {
                        "rule": "review-object-outside-examples",
                        "path": rel,
                        "detail": "review-layer material belongs in a private "
                        "review area, never in the public repository",
                    }
                )
            elif ecp_object in REVIEW_GT_CARRYING and document.get("content_class") != "format-illustration":
                violations.append(
                    {
                        "rule": "example-review-object-not-illustration",
                        "path": rel,
                        "detail": "review-layer examples under examples/ must be "
                        "content_class 'format-illustration' (public dummy values)",
                    }
                )

    return violations


def format_violations(violations: "list[dict]") -> str:
    """Render violations as a human-readable report."""
    if not violations:
        return "BOUNDARY SCAN: CLEAN — public/protected boundary respected."
    lines = [f"BOUNDARY SCAN: {len(violations)} violation(s)"]
    for violation in violations:
        lines.append(
            f"  [{violation['rule']}] {violation['path']}: {violation['detail']}"
        )
    return "\n".join(lines)


# --- public ledger tree boundary (R1-I, Option C / O1) ---------------------
#
# The public registration ledger (a separate repository from the ECP
# contract repository) carries public metadata only: chained entries,
# registration records, the ANCHOR checkpoint. These rules machine-check
# that nothing protected ever lands in it.

LEDGER_REQUIRED_PATHS = ("ANCHOR.json", "entries", "records")
LEDGER_ALLOWED_OBJECTS = ("ledger-entry", "registration")


def scan_ledger_tree(ledger_root: "str | Path") -> "list[dict]":
    """Scan a public ledger tree for boundary violations.

    Rules:

    - LR1  the required ledger structure exists (``ANCHOR.json``,
      ``entries/``, ``records/``);
    - LR2  no ground-truth content keys (``expected_answer``,
      ``derivation``) in any JSON document;
    - LR3  no ``ecp_object: "ground-truth"`` document;
    - LR4  only ``ledger-entry`` and ``registration`` ECP objects appear
      (any other ECP object type is foreign to the ledger repository);
    - LR5  every JSON file parses (an unparseable file is a violation).

    Chain integrity itself is verified by ``ecp.ledger.ledger_verify``,
    not by this scanner.
    """
    root = Path(ledger_root)
    violations: "list[dict]" = []

    # LR1 — structure
    for required in LEDGER_REQUIRED_PATHS:
        if not (root / required).exists():
            violations.append(
                {
                    "rule": "ledger-structure-missing",
                    "path": required,
                    "detail": f"public ledger requires {required}",
                }
            )

    # LR2–LR5 — walk all JSON documents
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        if any(part.startswith(".") for part in path.relative_to(root).parts[:-1]):
            continue  # skip .git and friends
        try:
            with open(path, "r", encoding="utf-8") as fh:
                document = json.load(fh)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            violations.append(
                {
                    "rule": "ledger-invalid-json",
                    "path": rel,
                    "detail": f"unparseable JSON: {exc}",
                }
            )
            continue
        if not isinstance(document, dict):
            continue

        has_gt_keys = any(key in document for key in GROUND_TRUTH_CONTENT_KEYS)
        is_gt_object = document.get("ecp_object") == "ground-truth"
        if has_gt_keys or is_gt_object:
            violations.append(
                {
                    "rule": "ledger-ground-truth-content",
                    "path": rel,
                    "detail": "protected ground-truth content is forbidden in "
                    "the public ledger",
                }
            )
        ecp_object = document.get("ecp_object")
        if isinstance(ecp_object, str) and ecp_object not in LEDGER_ALLOWED_OBJECTS:
            violations.append(
                {
                    "rule": "ledger-foreign-ecp-object",
                    "path": rel,
                    "detail": f"ecp_object {ecp_object!r} does not belong in "
                    "the ledger repository",
                }
            )

    return violations


# --- review-area boundary (M3-CA0) --------------------------------------------
#
# The private/local review area holds review-layer material (candidates
# with embedded ground-truth-class content, review artifacts, run
# manifests, owner adjudications). These rules machine-check that the
# review area never becomes anything else — in particular that it never
# fabricates case/registration identities and never masquerades as a
# ledger.

REVIEW_ALLOWED_OBJECTS = REVIEW_OBJECTS
REVIEW_OBJECT_DIRS = {
    "case-candidate": ("candidates",),
    "case-review": ("reviews",),
    "review-run": (),  # only at the root, as review-run.json
    "review-adjudication": ("adjudications",),
    "case-amendment": ("amendments",),
}
#: Identity strings the review layer must NEVER assign (registration- and
#: case-layer identities are later, separately authorized acts).
FORBIDDEN_ID_PREFIXES = ("ECP-CASE-", "ECP-REG-")
#: Non-object files allowed in a review area (operator/ops artifacts).
REVIEW_ALLOWED_OPS_FILES = {
    "README.md",
    "extraction-report.json",
    "adjudications/README.md",
    "amendments/README.md",
    "candidates/README.md",
    "reviews/README.md",
    "source/README.md",
}


def scan_review_tree(review_root: "str | Path") -> "list[dict]":
    """Scan a private review-area tree for boundary violations.

    Rules:

    - RV1  the review area contains only expected locations
      (``candidates/``, ``reviews/``, ``adjudications/``,
      ``amendments/``, ``source/`` and root files);
    - RV2  every ECP object sits in its designated directory
      (case-candidate in candidates/, case-review in reviews/,
      review-adjudication in adjudications/, case-amendment in
      amendments/, review-run only as the root ``review-run.json``);
    - RV3  no foreign ECP object type appears (ledger, registration, case,
      system, execution, evaluation, evidence, audit, ground-truth, store
      objects do not belong in a review area);
    - RV4  no ``ECP-CASE-`` or ``ECP-REG-`` identity is ever assigned by
      the review layer (string scan over every file);
    - RV5  every JSON file parses and validates against its schema;
    - RV6  unexpected non-object files are flagged.
    """
    root = Path(review_root)
    violations: "list[dict]" = []

    if not root.is_dir():
        return [
            {
                "rule": "review-root-missing",
                "path": str(root),
                "detail": "review root is not a directory",
            }
        ]

    allowed_top_entries = {
        "candidates", "reviews", "adjudications", "amendments", "source",
        "review-run.json", "README.md", "extraction-report.json",
    }
    for entry in sorted(root.iterdir()):
        name = entry.name
        if name not in allowed_top_entries:
            violations.append(
                {
                    "rule": "review-unexpected-top-entry",
                    "path": name,
                    "detail": "review area allows only candidates/, reviews/, "
                    "adjudications/, source/ and root ops files",
                }
            )

    # RV4 — forbidden identity prefixes, over raw file text.
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for prefix in FORBIDDEN_ID_PREFIXES:
            if prefix in text:
                violations.append(
                    {
                        "rule": "review-fabricated-identity",
                        "path": rel,
                        "detail": f"review layer must never assign {prefix}* identities",
                    }
                )

    # RV2/RV3/RV5/RV6 — walk JSON documents.
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).as_posix()
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                document = json.load(fh)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            violations.append(
                {
                    "rule": "review-invalid-json",
                    "path": rel,
                    "detail": f"unparseable JSON: {exc}",
                }
            )
            continue
        if not isinstance(document, dict) or "ecp_object" not in document:
            if rel not in REVIEW_ALLOWED_OPS_FILES and not rel.startswith("source/"):
                violations.append(
                    {
                        "rule": "review-unexpected-ops-file",
                        "path": rel,
                        "detail": "non-ECP-object JSON files are not expected here",
                    }
                )
            continue

        ecp_object = document.get("ecp_object")
        if ecp_object not in REVIEW_ALLOWED_OBJECTS:
            violations.append(
                {
                    "rule": "review-foreign-ecp-object",
                    "path": rel,
                    "detail": f"ecp_object {ecp_object!r} does not belong in a review area",
                }
            )
            continue

        allowed_dirs = REVIEW_OBJECT_DIRS[ecp_object]
        if ecp_object == "review-run":
            if rel != "review-run.json":
                violations.append(
                    {
                        "rule": "review-object-wrong-location",
                        "path": rel,
                        "detail": "review-run manifests live only at the root as review-run.json",
                    }
                )
        elif not any(rel.startswith(d + "/") for d in allowed_dirs):
            violations.append(
                {
                    "rule": "review-object-wrong-location",
                    "path": rel,
                        "detail": f"{ecp_object} objects belong in "
                        f"{'/'.join(allowed_dirs)}/",
                }
            )

        if ecp_object != "review-run":
            from .validate import validate_document

            issues = validate_document(document, ecp_object)
            if issues:
                violations.append(
                    {
                        "rule": "review-object-schema-invalid",
                        "path": rel,
                        "detail": "; ".join(issues[:3]),
                    }
                )

    return violations
