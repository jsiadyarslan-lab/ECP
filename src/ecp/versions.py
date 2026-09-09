"""Explicit protocol/schema version compatibility (0.3.0 → 0.4.0 → 0.5.0 additive).

O8 (M3-R1 architecture decision, owner-approved) advanced the schema bundle
to 0.2.0 by ADDING two new object contracts (``ledger-entry``,
``store-manifest``). M3-CA0 advanced it to 0.3.0 by ADDING four review-layer
contracts (``case-candidate``, ``case-review``, ``review-run``,
``review-adjudication``). M3-CA0-A advances it to 0.4.0 by ADDING one
adjudication-layer contract (``case-amendment``) and EXTENDING the three
0.3.0 review contracts additively (optional ``case_version``/``amendment``
fields on case-candidate, optional ``amendment`` linkage on case-review,
optional ``amendments``/``lineage`` blocks on review-run). M3-CA0 v1
advances it to 0.5.0 by ADDING two authoring-layer contracts
(``case-qualification``, ``qualification-run``) and EXTENDING
``case-candidate`` additively (optional authoring-layer fields:
``expected_property``/``forbidden_shortcuts``/``ground_truth``/``formal``
inside content; ``authoring_independence``/
``representation_bias_disclosure``/``environmental_pre_check`` at the top
level — schema-optional, engine-mandatory for 0.5.0-protocol candidates).
The earlier bundles' contracts are unchanged, and 0.1.x/0.2.x/0.3.x/0.4.x
artifacts are NOT silently reinterpreted: they remain exactly as valid as
they were. This module is the single place where that compatibility policy
is stated machine-checkably.

Rules (normative, see spec §18–§21):

- The *protocol* axis is backward compatible: documents citing
  ``0.1.0``, ``0.2.0``, ``0.3.0`` or ``0.4.0`` remain valid under a
  ``0.5.0`` toolchain (the protocol only gained mechanisms; no earlier
  semantics changed).
- The *schema* axis is per-object-type:
  - object types whose contract file is unchanged since 0.1.0 accept
    ``0.1.0`` through ``0.5.0``;
  - object types introduced at 0.2.0 (unchanged in later bundles) accept
    ``0.2.0`` through ``0.5.0``;
  - object types introduced at 0.3.0 (case-candidate/case-review/
    review-run/review-adjudication) accept ``0.3.0`` through ``0.5.0``
    (the 0.4.0/0.5.0 extensions are additive optional fields);
  - object types introduced at 0.4.0 (case-amendment) accept ``0.4.0``
    and ``0.5.0``;
  - object types introduced at 0.5.0 (case-qualification/
    qualification-run) accept only ``0.5.0``.

Anything outside these sets is a compatibility violation (an issue, not an
exception — the caller decides severity). There is still no implicit
"current version": every artifact must cite a version explicitly.
"""

# Object types defined by the 0.1.0 schema bundle (contract files unchanged
# in the 0.2.0 and 0.3.0 bundles):
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

# Object types introduced by the 0.2.0 schema bundle (unchanged in 0.3.0):
V020_CONTRACTS = (
    "ledger-entry",
    "store-manifest",
)

# Object types introduced by the 0.3.0 schema bundle (M3-CA0 case review;
# extended additively in 0.4.0):
V030_CONTRACTS = (
    "case-candidate",
    "case-review",
    "review-run",
    "review-adjudication",
)

# Object types introduced by the 0.4.0 schema bundle (M3-CA0-A case
# amendment / adjudication layer; unchanged in 0.5.0):
V040_CONTRACTS = (
    "case-amendment",
)

# Object types introduced by the 0.5.0 schema bundle (M3-CA0 v1 authoring
# + qualification layer):
V050_CONTRACTS = (
    "case-qualification",
    "qualification-run",
)

#: Per-object-type accepted ``schema_version`` values.
SCHEMA_VERSIONS: dict = {
    **{name: ("0.1.0", "0.2.0", "0.3.0", "0.4.0", "0.5.0") for name in V010_CONTRACTS},
    **{name: ("0.2.0", "0.3.0", "0.4.0", "0.5.0") for name in V020_CONTRACTS},
    **{name: ("0.3.0", "0.4.0", "0.5.0") for name in V030_CONTRACTS},
    **{name: ("0.4.0", "0.5.0") for name in V040_CONTRACTS},
    **{name: ("0.5.0",) for name in V050_CONTRACTS},
}

#: Accepted ``protocol_version`` values for every artifact (protocol axis is
#: backward compatible; all versions share identical semantics for all
#: pre-0.5.0 mechanisms).
PROTOCOL_VERSIONS = ("0.1.0", "0.2.0", "0.3.0", "0.4.0", "0.5.0")


def allowed_schema_versions(object_type: "str | None") -> tuple:
    """Accepted ``schema_version`` values for *object_type*.

    Unknown object types fall back to the union of all accepted versions
    (the caller's schema validation will already have rejected unknown
    types; this fallback keeps the version check from masking the real
    error).
    """
    return SCHEMA_VERSIONS.get(object_type, PROTOCOL_VERSIONS)


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
