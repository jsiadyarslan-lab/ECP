"""Explicit protocol/schema version compatibility (0.2.0 additive).

O8 (M3-R1 architecture decision, owner-approved) advances the schema bundle
to 0.2.0 by ADDING two new object contracts (``ledger-entry``,
``store-manifest``). The ten 0.1.0 contracts are unchanged, and 0.1.x
artifacts are NOT silently reinterpreted: they remain exactly as valid as
they were. This module is the single place where that compatibility policy
is stated machine-checkably.

Rules (normative, see spec §18):

- The *protocol* axis is backward compatible: documents citing
  ``0.1.0`` remain valid under a ``0.2.0`` toolchain (the protocol only
  gained mechanisms; no 0.1.0 semantics changed).
- The *schema* axis is per-object-type:
  - object types whose contract file is unchanged since 0.1.0 accept
    BOTH ``0.1.0`` (the original contract version) and ``0.2.0`` (the
    current bundle version, under which new artifacts may equally cite
    them, since the contract content is identical);
  - object types introduced at 0.2.0 accept only ``0.2.0``.

Anything outside these sets is a compatibility violation (an issue, not an
exception — the caller decides severity). There is still no implicit
"current version": every artifact must cite a version explicitly.
"""

# Object types defined by the 0.1.0 schema bundle (contract files unchanged
# in the 0.2.0 bundle):
V010_CONTRACTS = (
    "protocol",
    "system",
    "evaluation",
    "case",
    "ground-truth",
    "registration",
    "execution",
    "evidence",
    "audit",
    "manifest",
)

# Object types introduced by the 0.2.0 schema bundle:
V020_CONTRACTS = (
    "ledger-entry",
    "store-manifest",
)

#: Per-object-type accepted ``schema_version`` values.
SCHEMA_VERSIONS: dict = {
    **{name: ("0.1.0", "0.2.0") for name in V010_CONTRACTS},
    **{name: ("0.2.0",) for name in V020_CONTRACTS},
}

#: Accepted ``protocol_version`` values for every artifact (protocol axis is
#: backward compatible; both versions share identical semantics for all
#: pre-0.2.0 mechanisms).
PROTOCOL_VERSIONS = ("0.1.0", "0.2.0")


def allowed_schema_versions(object_type: "str | None") -> tuple:
    """Accepted ``schema_version`` values for *object_type*.

    Unknown object types fall back to the union of all accepted versions
    (the caller's schema validation will already have rejected unknown
    types; this fallback keeps the version check from masking the real
    error).
    """
    return SCHEMA_VERSIONS.get(object_type, ("0.1.0", "0.2.0"))


def version_issues(document: dict) -> "list[str]":
    """Explicit version-compatibility issues for *document*.

    Checks (issue list, empty = compatible):

    - ``protocol_version`` present and in :data:`PROTOCOL_VERSIONS`;
    - ``schema_version``, when the document carries one, is in the accepted
      set for the document's ``ecp_object`` type.

    This never raises on mismatch — a mismatch is a finding.
    """
    issues: "list[str]" = []
    if not isinstance(document, dict):
        return ["<root>: version check expects a JSON object (dict)"]

    object_type = document.get("ecp_object")
    protocol_version = document.get("protocol_version")
    if protocol_version is None:
        issues.append("<root>: missing protocol_version (no implicit 'current version')")
    elif protocol_version not in PROTOCOL_VERSIONS:
        issues.append(
            f"protocol_version: document cites {protocol_version!r}, "
            f"accepted: {list(PROTOCOL_VERSIONS)}"
        )

    schema_version = document.get("schema_version")
    if schema_version is not None:
        allowed = allowed_schema_versions(object_type)
        if schema_version not in allowed:
            issues.append(
                f"schema_version: document cites {schema_version!r} for object "
                f"type {object_type!r}, accepted: {list(allowed)}"
            )
    return issues
