"""Verification layer — integrity only, NEVER scientific adjudication.

Every function here answers an *integrity* question: "is this artifact the
artifact it claims to be?" — "do these bytes match this commitment?",
"does this manifest cover these files?", "was this document produced under
the protocol version it cites?".

No function here answers a *scientific* question ("is this result
correct?", "is this execution a valid measurement?", "is this case well
authorized?"). A cryptographically intact result is not automatically a
scientifically valid result. Scientific adjudication lives in the audit /
classification layer, under independent auditors, in later phases.

All checks return a list of issues (empty = intact). They never raise on
content mismatch — mismatch is a finding, not an exception.
"""

from pathlib import Path

from .hashing import hash_document, hash_file
from .identity import load_identity
from .manifest import compute_manifest_hash
from .validate import validate_document


def verify_protocol_compatibility(
    document: dict, identity: "dict | None" = None
) -> "list[str]":
    """Check that *document* cites a protocol (and schema) version that is
    explicitly compatible with this repository's protocol.

    Since the 0.2.0 additive bundle (R1-I) and the 0.3.0 additive bundle
    (M3-CA0), compatibility is an explicit matrix (see
    :mod:`ecp.versions`): 0.1.x/0.2.x artifacts remain valid — they are
    not silently reinterpreted, and they are not silently invalidated.
    The document's cited versions must be members of the accepted sets
    (``ecp.versions.PROTOCOL_VERSIONS`` / per-object-type accepted
    ``schema_version`` sets).
    """
    from .versions import PROTOCOL_VERSIONS, version_issues

    identity = identity or load_identity()
    issues = version_issues(document)
    # The identity itself pins the CURRENT bundle; cross-check that the
    # repository is in a state this tooling understands.
    if identity.get("schema_version") not in PROTOCOL_VERSIONS:
        issues.append(
            f"identity: repository pins unsupported schema_version "
            f"{identity.get('schema_version')!r}"
        )
    return issues


def verify_commitment(public_case: dict, ground_truth_document: dict) -> "list[str]":
    """Verify the seal binding a public case to a protected ground truth.

    Recomputes SHA-256 over the ECP-CANONICAL-JSON-1.0 serialization of
    *ground_truth_document* and compares it with the commitment recorded in
    the public case's ``ground_truth_reference``.
    """
    issues = []
    reference = public_case.get("ground_truth_reference")
    if not isinstance(reference, dict) or "commitment" not in reference:
        return ["ground_truth_reference: case carries no commitment"]
    expected = reference["commitment"]
    actual = hash_document(ground_truth_document)
    if expected != actual:
        issues.append(
            f"ground_truth_reference.commitment: case cites {expected!r}, "
            f"recomputed {actual!r} — ground truth does not match the seal"
        )
    return issues


def verify_artifact_hash(path: "str | Path", expected_hash: str) -> "list[str]":
    """Verify that a file's raw bytes hash to *expected_hash*."""
    issues = []
    if not Path(path).is_file():
        return [f"artifact {path}: file not found"]
    actual = hash_file(path)
    if actual != expected_hash:
        issues.append(
            f"artifact {path}: expected sha256 {expected_hash}, recomputed {actual}"
        )
    return issues


def verify_manifest(manifest: dict, file_hashes: "dict[str, str]") -> "list[str]":
    """Verify a manifest against a mapping ``{path: sha256_hex}``.

    Checks, in order:

    1. schema validity (manifest);
    2. ``manifest_hash`` recomputation over the canonical document minus
       the ``manifest_hash`` field;
    3. entry path uniqueness;
    4. every entry path resolves in *file_hashes* and matches its hash.

    Integrity only: a clean manifest says nothing about the scientific
    meaning of the artifacts.
    """
    issues = []
    issues.extend(validate_document(manifest, "manifest"))
    if issues:
        return issues  # schema-invalid: do not attempt hash semantics

    stored = manifest["manifest_hash"]
    recomputed = compute_manifest_hash(manifest)
    if stored != recomputed:
        issues.append(
            f"manifest_hash: stored {stored!r}, recomputed {recomputed!r}"
        )

    seen = set()
    for entry in manifest["entries"]:
        path = entry["path"]
        if path in seen:
            issues.append(f"entries: duplicate path {path!r}")
        seen.add(path)
        if path not in file_hashes:
            issues.append(f"entries: no hash provided for path {path!r}")
            continue
        if file_hashes[path] != entry["hash"]:
            issues.append(
                f"entries: {path!r} stored {entry['hash']!r} but provided "
                f"{file_hashes[path]!r}"
            )
    return issues


def verify_evidence_reference(
    audit_record: dict, evidence_document: dict
) -> "list[str]":
    """Verify that an audit record's evidence reference (id + canonical hash)
    matches the evidence document it points to."""
    issues = []
    reviewed = audit_record.get("evidence_reviewed", [])
    if not reviewed:
        return ["evidence_reviewed: audit reviews no evidence"]
    expected_ids = {r["evidence_id"] for r in reviewed}
    actual_id = evidence_document.get("evidence_id")
    if actual_id not in expected_ids:
        issues.append(
            f"evidence_reviewed: evidence {actual_id!r} is not among reviewed "
            f"{sorted(expected_ids)}"
        )
        return issues
    for reference in reviewed:
        if reference["evidence_id"] != actual_id:
            continue
        actual_hash = hash_document(evidence_document)
        if reference["evidence_hash"] != actual_hash:
            issues.append(
                f"evidence_reviewed: {actual_id!r} cited hash "
                f"{reference['evidence_hash']!r} != recomputed {actual_hash!r}"
            )
    return issues
