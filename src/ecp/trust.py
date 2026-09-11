"""Protected Evaluation + Registration Trust Layer (M3-RG0, 0.7.0).

Implements the eight components ordered by M3-RG0 §2 (the trust boundary
whose existence ADJ-06 makes a hard precondition for ever opening
registration):

1. **Protected Store** (:func:`init_trust_store`, :func:`load_trust_manifest`)
   — a trust-store root OUTSIDE the public repository with three
   ownership-explicit zones (order §3)::

       authoritative/   registered reference truth (immutable, append-only)
       operational/     mutable runtime state (NON-AUTHORITATIVE by contract)
       evidence/        scientific execution evidence (reserved; NO writer
                        exists at 0.7.0 — order §10)

   Ordinary evaluation operations have NO write path into the
   authoritative zone: the only writers are the governed seams below.

2. **Registration Authority** (:class:`RegistrationAuthority`) — the
   governed ceremony that accepts a registration *package* into the
   protected boundary (order §4): schema validation, cryptographic
   commitment verification, ground-truth seam check, Owner-bound ruling
   citation check, duplicate control, deterministic identity assignment,
   provenance preservation, fail-closed refusal of everything malformed,
   conflicting or Owner-incomplete. The authority NEVER invents missing
   Owner decisions: an absent required Owner-bound value is REFUSED, not
   inferred.

3. **Immutable Registration Records** — accepted records are write-once
   files (``authoritative/registrations/ECP-TREG-NNNNNN.json``); any
   correction is a NEW :func:`RegistrationAuthority.amend_registration`
   event, never an edit; the original commitments remain verifiable
   forever (order §5).

4. **State / Reference-Truth Separation** (order §6) —
   :func:`store_reference_truth` answers WHAT WAS REGISTERED from the
   authoritative zone alone; :func:`store_runtime_state` answers WHAT
   LATER HAPPENED from the operational zone alone; runtime state is
   structurally incapable of becoming registration truth (zone markers +
   verification), and :func:`resolve_registration` returns the two
   answers side by side, never merged.

5. **Cryptographic Commitment** (order §7) — deterministic SHA-256 over
   ECP-CANONICAL-JSON-1.0 for case content, ground truth, success
   criterion, environment, provenance, package and record; self-
   referential hashes use the established exclusion rule
   (:func:`ecp.hashing.hash_document_excluding`) — a document's own hash
   field is removed before hashing, never hashed populated.

6. **Provenance / Lineage** (order §8) — a hash-chained append-only
   lineage (``authoritative/lineage/NNNNNNNN.json``) answering, for every
   registration: origin package, artifact + version, identifying
   commitments, accepting event, and subsequent amendments. No execution
   result can overwrite registration provenance (execution material is
   not an event kind and has no authoritative writer).

7. **Controlled Access** (order §9) — the default posture is read/verify
   (:func:`store_gate_state`, :func:`store_reference_truth`,
   :func:`store_runtime_state`, :func:`resolve_registration`,
   :func:`verify_trust_store`); every mutation is an explicitly governed
   seam: :class:`RegistrationAuthority` (registrar identity required),
   :func:`apply_owner_gate_order` (the ONLY gate-transition instrument)
   and :func:`record_runtime_observation` (operational zone ONLY). There
   is no automatic approval, no implicit registration, no hidden
   mutation, no bypass path and no ungoverned administrative write.

8. **Registration Integrity Verification** (:func:`verify_trust_store`)
   — full deterministic recomputation (order §11): manifest, gate state
   and gate-history replay, every record and amendment hash, lineage
   chain and bindings, write-once/monotone-id discipline, duplicate
   control, zone ownership markers, evidence-zone writer prohibition and
   fail-closed cross-checks.

The registration gate REMAINS CLOSED at the end of M3-RG0 (order §10):
``init_trust_store`` writes the authoritative gate state as
``REGISTRATION = CLOSED / MODEL EXECUTION = CLOSED / SCIENTIFIC RESULTS =
NONE``; the ONLY transition path is an explicit owner-gate-order
instrument applied through :func:`apply_owner_gate_order` (all six
Owner-bound rulings required, scope-bound, legality-checked, lineage-
recorded). A successful infrastructure test in ``development`` scope is
NEVER an authorization to register real cases: a development-scope order
cannot govern an operational-scope trust store, and no operational owner
order exists.

This is infrastructure only: nothing here executes models, scores
results, or adjudicates science.
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .canonical import canonical_bytes
from .hashing import hash_document, hash_document_excluding
from .validate import validate_document
from .versions import version_issues

GENESIS_HASH = "0" * 64
INDEX_PAD = 8

AUTHORITATIVE_DIR = "authoritative"
REGISTRATIONS_DIR = "authoritative/registrations"
AMENDMENTS_DIR = "authoritative/amendments"
LINEAGE_DIR = "authoritative/lineage"
GATE_FILE = "authoritative/gate.json"
OPERATIONAL_DIR = "operational"
RUNTIME_DIR = "operational/runtime"
EVIDENCE_DIR = "evidence"
MANIFEST_FILE = "trust.json"

TRUST_ID_PATTERN = re.compile(r"^ECP-TRUST-[A-Za-z0-9][A-Za-z0-9._:-]*$")
GATE_ID_PATTERN = re.compile(r"^ECP-GATE-[A-Za-z0-9][A-Za-z0-9._:-]*$")
GATEORDER_ID_PATTERN = re.compile(r"^ECP-GATEORDER-[A-Za-z0-9][A-Za-z0-9._:-]*$")
REGISTRAR_PATTERN = re.compile(r"^ECP-REGISTRAR-[A-Za-z0-9][A-Za-z0-9._:-]*$")
EVALUATION_ID_PATTERN = re.compile(r"^ECP-EVAL-[A-Za-z0-9][A-Za-z0-9._:-]*$")
PACKAGE_ID_PATTERN = re.compile(r"^ECP-PKG-[A-Za-z0-9][A-Za-z0-9._:-]*$")
TREG_ID_PATTERN = re.compile(r"^ECP-TREG-[0-9]{6}$")
TAMND_ID_PATTERN = re.compile(r"^ECP-TAMND-[0-9]{6}$")
OBS_ID_PATTERN = re.compile(r"^ECP-OBS-[A-Za-z0-9][A-Za-z0-9._:-]*$")
HEX64_PATTERN = re.compile(r"^[0-9a-f]{64}$")

SCOPES = ("development", "operational")
GATE_STATES = ("CLOSED", "OPEN")

#: The six Owner-bound operational openings carried open from
#: ECP-OWNDEC-000004 (ruling null — never inferred). An owner gate order
#: must supply ALL of them (non-empty) before the registration gate may
#: open; the Registration Authority refuses any package whose citations
#: diverge from the authoritative gate.
OWNER_BOUND_SLOTS = ("O-01", "O-02", "O-04", "F-01a", "F-01b", "POP")

INITIAL_GATE_BASIS = [
    "ADJ-06 (ECP-OWNDEC-000004, ADOPTED — ARCHITECTURAL LAYER, IMMUTABLE): "
    "APPROVE WITH HARD PRECONDITION — no registration before the trust "
    "boundary exists and is verified",
    "M3-RG0 order §10: infrastructure construction only — REGISTRATION = "
    "CLOSED, MODEL EXECUTION = CLOSED, SCIENTIFIC RESULTS = NONE",
    "the six Owner-bound operational openings (O-01/O-02/O-04/F-01a/"
    "F-01b/POP) remain exactly as recorded in ECP-OWNDEC-000004 (ruling "
    "null); no value is inferred",
]

GATE_TRANSITION_RULE = (
    "gate transitions ONLY via an explicit owner-gate-order instrument "
    "applied through apply_owner_gate_order (scope-bound, all six Owner-"
    "bound rulings required, legality-checked) and recorded as a lineage "
    "gate-transition event; no other writer exists"
)

IMMUTABILITY_CLAUSE = (
    "append-only — the original record is never rewritten; corrections "
    "are new registration-amendment events; the original commitments "
    "remain independently verifiable"
)

EVIDENCE_WRITER_NOTE = (
    "none (0.7.0): no evidence write path exists in M3-RG0; "
    "execution-side writes require a separate owner gate"
)

OPERATIONAL_OWNERSHIP_NOTE = (
    "mutable operational state — NON-AUTHORITATIVE: never a source of "
    "reference truth; replaceable without affecting the registered truth"
)

ZONE_READMES = {
    AUTHORITATIVE_DIR: (
        "# ECP Trust Store — AUTHORITATIVE zone\n\n"
        "Registered reference truth (order M3-RG0 §3/§6): the gate state,\n"
        "immutable registration records, append-only amendments and the\n"
        "hash-chained lineage. EVERYTHING here is governed-mutation-only:\n"
        "the Registration Authority ceremony and the owner gate-order\n"
        "seam are the only writers. There is no write path from ordinary\n"
        "evaluation code. Files are write-once; corrections are new\n"
        "amendment events, never edits.\n"
    ),
    OPERATIONAL_DIR: (
        "# ECP Trust Store — OPERATIONAL zone (NON-AUTHORITATIVE)\n\n"
        "Mutable runtime state (order M3-RG0 §6): WHAT LATER HAPPENED —\n"
        "runtime observations recorded by record_runtime_observation.\n"
        "This zone is NEVER a source of reference truth for WHAT WAS\n"
        "REGISTERED; every document carries authority_class =\n"
        "NON-AUTHORITATIVE and zone = operational; verify_trust_store\n"
        "rejects any document here that lacks the markers or claims an\n"
        "authoritative object type. The zone as a whole may be archived\n"
        "or pruned without affecting the authoritative zone.\n"
    ),
    EVIDENCE_DIR: (
        "# ECP Trust Store — EVIDENCE zone (reserved)\n\n"
        "Scientific execution evidence (order M3-RG0 §3/§10). NO writer\n"
        "exists at 0.7.0: M3-RG0 is infrastructure construction only —\n"
        "MODEL EXECUTION = CLOSED and SCIENTIFIC RESULTS = NONE. An\n"
        "execution-evidence write path may only be created by a separate\n"
        "owner order after the execution gate opens. Any file other than\n"
        "this README present at 0.7.0 is flagged by verify_trust_store\n"
        "(execution cannot occur merely because the infrastructure\n"
        "exists).\n"
    ),
}


class TrustError(Exception):
    """Base class for trust-layer errors."""


class TrustInvalid(TrustError):
    """The trust store state on disk is structurally invalid or unverifiable."""


class RegistrationRefused(TrustError):
    """A registration submission was refused (fail-closed) before any
    authoritative registration write; the refusal itself is recorded as a
    lineage event."""

    def __init__(self, reason: str, stage: str = "gate"):
        super().__init__(reason)
        self.reason = reason
        self.stage = stage


class AmendmentRefused(TrustError):
    """An amendment submission was refused before any write."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class OwnerOrderRejected(TrustError):
    """An owner gate order was rejected (malformed, out of scope, illegal
    transition or duplicate) — the gate state is untouched."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class WriteOnceViolation(TrustError):
    """A write attempted to replace committed authoritative content."""


class AccessBoundaryError(TrustError):
    """A write attempted to cross a zone ownership boundary (e.g. an
    operational writer targeting authoritative content, or an operational
    document claiming an authoritative object type)."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve(root: "str | Path") -> Path:
    return Path(root).resolve()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Two-phase write: temp file + atomic rename (POSIX rename is atomic)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.tmp-{uuid.uuid4().hex}"
    try:
        with open(temp, "wb") as fh:
            fh.write(data)
        os.replace(temp, path)
    finally:
        if temp.exists():  # pragma: no cover - only on hard failures
            temp.unlink()


def _write_canonical(path: Path, document: dict) -> None:
    _atomic_write_bytes(path, canonical_bytes(document))


def _load_json(path: Path) -> dict:
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def _validate_or_issues(document: dict, object_name: str) -> "list[str]":
    issues = validate_document(document, object_name)
    if issues:
        return issues
    return version_issues(document)


def _schema_ok(document: dict, object_name: str) -> bool:
    return not _validate_or_issues(document, object_name)


def _clone(document: object) -> object:
    return json.loads(json.dumps(document))


# ---------------------------------------------------------------------------
# lineage (component 6 — append-only, hash-chained)
# ---------------------------------------------------------------------------

def _lineage_paths(root: Path) -> "list[Path]":
    return sorted((root / LINEAGE_DIR).glob("*.json"))


def _load_lineage(root: Path) -> "list[dict]":
    """Load all lineage events in index order (structural read; raises on
    gaps/duplicates)."""
    events = []
    expected = 1
    for path in _lineage_paths(root):
        index = int(path.stem)
        if index != expected:
            raise TrustInvalid(f"lineage gap/duplicate at index {index}")
        events.append(_load_json(path))
        expected += 1
    return events


def _lineage_head(root: Path) -> "tuple[int, str]":
    count = 0
    head = GENESIS_HASH
    for path in _lineage_paths(root):
        index = int(path.stem)
        if index != count + 1:
            raise TrustInvalid(f"lineage gap/duplicate at index {index}")
        head = _load_json(path)["event_hash"]
        count = index
    return count, head


def _lineage_event_path(root: Path, index: int) -> Path:
    return root / LINEAGE_DIR / f"{index:0{INDEX_PAD}d}.json"


def _append_lineage(
    root: Path, trust_store_id: str, kind: str, actor: str, payload: dict, at: str
) -> dict:
    """Append one chained lineage event (governed mutation primitive)."""
    from .identity import load_identity

    ident = load_identity()
    count, head = _lineage_head(root)
    index = count + 1
    event = {
        "ecp_object": "lineage-event",
        "trust_store_id": trust_store_id,
        "event_index": index,
        "event_kind": kind,
        "actor": actor,
        "payload": dict(payload),
        "claimed_at": at,
        "protocol_version": ident["protocol_version"],
        "schema_version": ident["schema_version"],
        "prev_event_hash": head,
        "event_hash": None,
    }
    event["event_hash"] = hash_document_excluding(event, "event_hash")
    _write_canonical(_lineage_event_path(root, index), event)
    return event


# ---------------------------------------------------------------------------
# gate state (component 7 — the ONLY governed mutation is apply_owner_gate_order)
# ---------------------------------------------------------------------------

def _gate_document_path(root: Path) -> Path:
    return root / GATE_FILE


def load_gate_state(root: "str | Path") -> dict:
    """Load and fully verify the AUTHORITATIVE gate state document.

    Read/verify path (order §9): allowed to everyone. Raises
    :class:`TrustInvalid` on any schema, version or self-hash problem.
    """
    root = _resolve(root)
    path = _gate_document_path(root)
    if not path.is_file():
        raise TrustInvalid(f"no gate state at {path}")
    gate = _load_json(path)
    issues = _validate_or_issues(gate, "registration-gate-state")
    if issues:
        raise TrustInvalid("gate state invalid: " + "; ".join(issues))
    if gate["gate_hash"] != hash_document_excluding(gate, "gate_hash"):
        raise TrustInvalid("gate state gate_hash does not recompute")
    return gate


def _write_gate(root: Path, gate: dict) -> None:
    gate["gate_hash"] = hash_document_excluding(gate, "gate_hash")
    _write_canonical(_gate_document_path(root), gate)


def store_gate_state(root: "str | Path") -> dict:
    """Public read API: the verified authoritative gate state summary."""
    gate = load_gate_state(root)
    return {
        "trust_store_id": gate["trust_store_id"],
        "registration_gate": gate["registration_gate"],
        "model_execution_gate": gate["model_execution_gate"],
        "scientific_results": gate["scientific_results"],
        "owner_ruling_citations": dict(gate["owner_ruling_citations"]),
        "gate_order_reference": gate.get("gate_order_reference"),
        "recorded_at": gate["recorded_at"],
        "gate_hash": gate["gate_hash"],
    }


# ---------------------------------------------------------------------------
# store lifecycle + manifest (components 1 and 8)
# ---------------------------------------------------------------------------

def _manifest_document(
    trust_store_id: str,
    scope: str,
    gate: dict,
    lineage_count: int,
    lineage_head_hash: str,
    registrations: int,
    amendments: int,
    observations: int,
    evidence_files: int,
    generated_at: str,
    protocol_version: str,
    schema_version: str,
) -> dict:
    manifest = {
        "ecp_object": "trust-store-manifest",
        "trust_store_id": trust_store_id,
        "scope": scope,
        "zones": {
            "authoritative": {
                "registrations": registrations,
                "amendments": amendments,
                "lineage_events": lineage_count,
            },
            "operational": {
                "observations": observations,
                "ownership": OPERATIONAL_OWNERSHIP_NOTE,
            },
            "evidence": {"files": evidence_files, "writer": EVIDENCE_WRITER_NOTE},
        },
        "gate": {
            "registration_gate": gate["registration_gate"],
            "model_execution_gate": gate["model_execution_gate"],
            "scientific_results": gate["scientific_results"],
            "gate_hash": gate["gate_hash"],
        },
        "lineage": {"event_count": lineage_count, "head_event_hash": lineage_head_hash},
        "generated_at": generated_at,
        "protocol_version": protocol_version,
        "schema_version": schema_version,
        "manifest_hash": None,
    }
    manifest["manifest_hash"] = hash_document_excluding(manifest, "manifest_hash")
    return manifest


def rebuild_manifest(root: "str | Path", at: "str | None" = None) -> dict:
    """Re-derive the trust store manifest from the underlying files (the
    manifest is a derived index, never a trust anchor) and write it."""
    from .identity import load_identity

    root = _resolve(root)
    gate = load_gate_state(root)
    manifest = load_trust_manifest(root)
    ident = load_identity()
    at = at or _now_iso()
    count, head = _lineage_head(root)
    registrations = len(list((root / REGISTRATIONS_DIR).glob("ECP-TREG-*.json")))
    amendments = len(list((root / AMENDMENTS_DIR).glob("ECP-TAMND-*.json")))
    observations = len(list((root / RUNTIME_DIR).glob("ECP-OBS-*.json")))
    evidence_files = len(
        [p for p in (root / EVIDENCE_DIR).iterdir() if p.is_file() and p.name != "README.md"]
    ) if (root / EVIDENCE_DIR).is_dir() else 0
    doc = _manifest_document(
        manifest["trust_store_id"],
        manifest["scope"],
        gate,
        count,
        head,
        registrations,
        amendments,
        observations,
        evidence_files,
        at,
        ident["protocol_version"],
        ident["schema_version"],
    )
    _write_canonical(root / MANIFEST_FILE, doc)
    return doc


def load_trust_manifest(root: "str | Path") -> dict:
    """Load and validate the trust store manifest (schema + self-hash)."""
    root = _resolve(root)
    path = root / MANIFEST_FILE
    if not path.is_file():
        raise TrustInvalid(f"no trust store manifest at {path} (not initialized?)")
    manifest = _load_json(path)
    issues = _validate_or_issues(manifest, "trust-store-manifest")
    if issues:
        raise TrustInvalid("trust store manifest invalid: " + "; ".join(issues))
    if manifest["manifest_hash"] != hash_document_excluding(manifest, "manifest_hash"):
        raise TrustInvalid("trust store manifest manifest_hash does not recompute")
    return manifest


def init_trust_store(
    root: "str | Path",
    trust_store_id: str,
    scope: str,
    at: "str | None" = None,
    identity: "dict | None" = None,
) -> dict:
    """Initialize a new (empty) protected trust store at *root*.

    The gate starts CLOSED (order §10 / ADJ-06): REGISTRATION = CLOSED,
    MODEL EXECUTION = CLOSED, SCIENTIFIC RESULTS = NONE, the six
    Owner-bound citations null (never inferred). The ONLY way to change
    this state is an explicit owner gate order
    (:func:`apply_owner_gate_order`).

    Args:
        root: trust store root (outside the public repository; must not
            exist or be empty).
        trust_store_id: ``ECP-TRUST-…`` identifier.
        scope: ``development`` (synthetic fixtures/tests only) or
            ``operational``.
        at: pinned UTC timestamp (default: now).
        identity: protocol identity (default: repository identity).

    Returns:
        The initial trust store manifest.
    """
    root = _resolve(root)
    if not TRUST_ID_PATTERN.fullmatch(trust_store_id or ""):
        raise TrustError(f"invalid trust_store_id {trust_store_id!r}")
    if scope not in SCOPES:
        raise TrustError(f"invalid scope {scope!r}")
    if root.exists() and any(root.iterdir()):
        raise TrustError(f"trust store root is not empty: {root}")

    from .identity import load_identity

    ident = identity or load_identity()
    at = at or _now_iso()

    for zone, readme in ZONE_READMES.items():
        (root / zone).mkdir(parents=True, exist_ok=True)
        (root / zone / "README.md").write_text(readme, encoding="utf-8")
    (root / REGISTRATIONS_DIR).mkdir(parents=True, exist_ok=True)
    (root / AMENDMENTS_DIR).mkdir(parents=True, exist_ok=True)
    (root / LINEAGE_DIR).mkdir(parents=True, exist_ok=True)
    (root / RUNTIME_DIR).mkdir(parents=True, exist_ok=True)

    gate = {
        "ecp_object": "registration-gate-state",
        "gate_id": f"ECP-GATE-{trust_store_id.split('-', 2)[2] if trust_store_id.count('-') >= 2 else '000001'}",
        "trust_store_id": trust_store_id,
        "scope": scope,
        "registration_gate": "CLOSED",
        "model_execution_gate": "CLOSED",
        "scientific_results": "NONE",
        "basis": list(INITIAL_GATE_BASIS),
        "transition_rule": GATE_TRANSITION_RULE,
        "owner_ruling_citations": {slot: None for slot in OWNER_BOUND_SLOTS},
        "recorded_at": at,
        "protocol_version": ident["protocol_version"],
        "schema_version": ident["schema_version"],
        "gate_hash": None,
    }
    _write_gate(root, gate)

    _append_lineage(
        root,
        trust_store_id,
        "trust-init",
        "trust-init",
        {"scope": scope, "gate_state": "CLOSED/CLOSED/NONE"},
        at,
    )

    manifest = _manifest_document(
        trust_store_id,
        scope,
        gate,
        1,
        _lineage_head(root)[1],
        0,
        0,
        0,
        0,
        at,
        ident["protocol_version"],
        ident["schema_version"],
    )
    _write_canonical(root / MANIFEST_FILE, manifest)
    return manifest


# ---------------------------------------------------------------------------
# state / reference-truth separation (component 4)
# ---------------------------------------------------------------------------

def _registration_files(root: Path) -> "list[Path]":
    return sorted((root / REGISTRATIONS_DIR).glob("ECP-TREG-*.json"))


def _amendment_files(root: Path) -> "list[Path]":
    return sorted((root / AMENDMENTS_DIR).glob("ECP-TAMND-*.json"))


def _observation_files(root: Path) -> "list[Path]":
    return sorted((root / RUNTIME_DIR).glob("ECP-OBS-*.json"))


def store_reference_truth(root: "str | Path") -> dict:
    """WHAT WAS REGISTERED — derived ONLY from the authoritative zone.

    Deterministic: a pure function of the authoritative files; runtime
    and evidence zones are never consulted. Every record is hash-verified
    before being reported (fail-closed: a tampered record raises
    :class:`TrustInvalid`).
    """
    root = _resolve(root)
    manifest = load_trust_manifest(root)
    gate = load_gate_state(root)
    registrations = []
    for path in _registration_files(root):
        record = _load_json(path)
        issues = _validate_or_issues(record, "trust-registration")
        if issues:
            raise TrustInvalid(f"{path.name} invalid: " + "; ".join(issues))
        if record["registration_hash"] != hash_document_excluding(record, "registration_hash"):
            raise TrustInvalid(f"{path.name}: registration_hash does not recompute")
        registrations.append(
            {
                "registration_id": record["registration_id"],
                "package_id": record["package_id"],
                "evaluation_id": record["evaluation_id"],
                "case": dict(record["case"]),
                "environment_id": record["environment_id"],
                "commitments": dict(record["commitments"]),
                "owner_ruling_citations": dict(record["owner_ruling_citations"]),
                "authority": dict(record["authority"]),
                "gate": dict(record["gate"]),
                "registered_at": record["registered_at"],
                "lineage": dict(record["lineage"]),
            }
        )
    amendments = []
    for path in _amendment_files(root):
        doc = _load_json(path)
        issues = _validate_or_issues(doc, "registration-amendment")
        if issues:
            raise TrustInvalid(f"{path.name} invalid: " + "; ".join(issues))
        if doc["amendment_hash"] != hash_document_excluding(doc, "amendment_hash"):
            raise TrustInvalid(f"{path.name}: amendment_hash does not recompute")
        amendments.append(
            {
                "amendment_id": doc["amendment_id"],
                "target_registration_id": doc["target_registration_id"],
                "amendment_kind": doc["amendment_kind"],
                "motivation": doc["motivation"],
                "lineage": dict(doc["lineage"]),
            }
        )
    return {
        "trust_store_id": manifest["trust_store_id"],
        "source_zone": "authoritative",
        "gate": {
            "registration_gate": gate["registration_gate"],
            "model_execution_gate": gate["model_execution_gate"],
            "scientific_results": gate["scientific_results"],
        },
        "registrations": registrations,
        "amendments": amendments,
    }


def store_runtime_state(root: "str | Path") -> dict:
    """WHAT LATER HAPPENED — derived ONLY from the operational zone.

    Non-authoritative by construction: the return value is explicitly
    marked and is never consulted by reference-truth resolution.
    Documents are schema-checked (fail-closed) but, by design, replaceable.
    """
    root = _resolve(root)
    manifest = load_trust_manifest(root)
    observations = []
    for path in _observation_files(root):
        doc = _load_json(path)
        issues = _validate_or_issues(doc, "runtime-observation")
        if issues:
            raise TrustInvalid(f"{path.name} invalid: " + "; ".join(issues))
        observations.append(
            {
                "observation_id": doc["observation_id"],
                "observation_kind": doc["observation_kind"],
                "registration_id": doc["registration_id"],
                "recorded_at": doc["recorded_at"],
                "observation_hash": doc["observation_hash"],
            }
        )
    return {
        "trust_store_id": manifest["trust_store_id"],
        "source_zone": "operational",
        "non_authoritative": True,
        "observations": observations,
    }


def resolve_registration(root: "str | Path", registration_id: str) -> dict:
    """Deterministic resolution of one registration (order §6/§8).

    Returns WHAT WAS REGISTERED (the immutable record, all commitments,
    the accepting lineage event) and WHAT LATER HAPPENED (amendments and
    runtime observations referencing it) — side by side, never merged.
    The original record's integrity is recomputed here (fail-closed).
    """
    root = _resolve(root)
    if not TREG_ID_PATTERN.fullmatch(registration_id or ""):
        raise TrustError(f"invalid registration_id {registration_id!r}")
    path = root / REGISTRATIONS_DIR / f"{registration_id}.json"
    if not path.is_file():
        raise TrustInvalid(f"no registration record {registration_id}")
    record = _load_json(path)
    issues = _validate_or_issues(record, "trust-registration")
    if issues:
        raise TrustInvalid(f"{registration_id} invalid: " + "; ".join(issues))
    if record["registration_hash"] != hash_document_excluding(record, "registration_hash"):
        raise TrustInvalid(f"{registration_id}: registration_hash does not recompute")

    events = []
    for event in _load_lineage(root):
        payload = event.get("payload", {})
        if payload.get("registration_id") == registration_id and event["event_kind"] == "registration-accepted":
            events.append({"event_index": event["event_index"], "event_hash": event["event_hash"]})
    amendments = []
    for am_path in _amendment_files(root):
        doc = _load_json(am_path)
        if doc["target_registration_id"] == registration_id:
            if doc["amendment_hash"] != hash_document_excluding(doc, "amendment_hash"):
                raise TrustInvalid(f"{am_path.name}: amendment_hash does not recompute")
            amendments.append(doc)
    observations = []
    for obs_path in _observation_files(root):
        doc = _load_json(obs_path)
        if doc.get("registration_id") == registration_id:
            observations.append(
                {
                    "observation_id": doc["observation_id"],
                    "observation_kind": doc["observation_kind"],
                    "recorded_at": doc["recorded_at"],
                }
            )
    invalidated = any(a["amendment_kind"] == "invalidation" for a in amendments)
    return {
        "registration_id": registration_id,
        "what_was_registered": record,
        "record_hash": hash_document(record),
        "commitments": dict(record["commitments"]),
        "authority": dict(record["authority"]),
        "accepting_event": events[0] if events else None,
        "what_later_happened": {
            "amendments": [
                {
                    "amendment_id": a["amendment_id"],
                    "amendment_kind": a["amendment_kind"],
                    "motivation": a["motivation"],
                    "recorded_at": a["recorded_at"],
                    "new_commitments": a.get("new_commitments", {}),
                }
                for a in amendments
            ],
            "runtime_observations": observations,
        },
        "current_state": "INVALIDATED" if invalidated else ("AMENDED" if amendments else "LIVE"),
    }


# ---------------------------------------------------------------------------
# owner seam (component 7 — the ONLY gate-transition instrument)
# ---------------------------------------------------------------------------

def apply_owner_gate_order(
    root: "str | Path", order: dict, at: "str | None" = None
) -> dict:
    """Apply an explicit owner gate order — the ONLY legal gate transition.

    Validates (fail-closed, gate untouched on any rejection):
      - schema + versions (owner-gate-order contract);
      - scope binding: the order scope MUST equal the trust store scope
        (a development order can never govern an operational store);
      - duplicate order_id (already applied) rejection;
      - ruling completeness: all six Owner-bound rulings non-empty
        (schema-enforced; re-checked — an incomplete order is refused,
        never completed by inference);
      - transition legality: model execution may not open while the
        resulting registration gate is closed; CLOSED->CLOSED no-ops and
        OPEN->OPEN re-opens under a different order are rejected (close
        first, then open: a clean audit trail).

    On success: a new authoritative gate state (citations frozen to the
    order's six rulings, gate_order_reference pinned) + a lineage
    ``gate-transition`` event + manifest rebuild.
    """
    root = _resolve(root)
    manifest = load_trust_manifest(root)
    gate = load_gate_state(root)
    ident_order = dict(order) if isinstance(order, dict) else {}
    issues = _validate_or_issues(ident_order, "owner-gate-order")
    if issues:
        raise OwnerOrderRejected(
            "owner gate order invalid: " + "; ".join(issues)
        )
    at = at or _now_iso()
    order_id = order["order_id"]
    order_scope = order["scope"]
    rulings = order["owner_rulings"]

    if order_scope != manifest["scope"]:
        raise OwnerOrderRejected(
            f"scope mismatch: order scope {order_scope!r} cannot govern a "
            f"{manifest['scope']!r}-scope trust store (scope binding)"
        )
    for slot in OWNER_BOUND_SLOTS:
        value = rulings.get(slot)
        if not isinstance(value, str) or not value.strip():
            raise OwnerOrderRejected(
                f"owner gate order incomplete: slot {slot} is empty — the "
                "authority never invents Owner decisions (fail-closed)"
            )
    for event in _load_lineage(root):
        payload = event.get("payload", {})
        if event["event_kind"] == "gate-transition" and payload.get("order_id") == order_id:
            raise OwnerOrderRejected(
                f"owner gate order {order_id} was already applied "
                f"(lineage event {event['event_index']}); re-application is refused"
            )

    new_reg = order["new_registration_gate"]
    new_exec = order["new_model_execution_gate"]
    cur_reg = gate["registration_gate"]
    if new_exec == "OPEN" and new_reg != "OPEN":
        raise OwnerOrderRejected(
            "illegal transition: model execution may not open while the "
            "registration gate is closed"
        )
    if new_reg == "CLOSED" and new_exec == "CLOSED" and cur_reg == "CLOSED":
        raise OwnerOrderRejected(
            "no-op order: CLOSED -> CLOSED with both gates already closed; "
            "nothing to transition"
        )
    if new_reg == "OPEN" and cur_reg == "OPEN":
        raise OwnerOrderRejected(
            "the registration gate is already OPEN; a re-open under a new "
            "order requires an explicit close transition first (clean audit trail)"
        )

    new_gate = {
        "ecp_object": "registration-gate-state",
        "gate_id": gate["gate_id"],
        "trust_store_id": gate["trust_store_id"],
        "scope": gate["scope"],
        "registration_gate": new_reg,
        "model_execution_gate": new_exec,
        "scientific_results": gate["scientific_results"],
        "basis": gate["basis"] + [
            f"gate transition via owner gate order {order_id} "
            f"({order['order_reference']['basis']})"
        ],
        "transition_rule": GATE_TRANSITION_RULE,
        "owner_ruling_citations": dict(rulings),
        "gate_order_reference": {
            "order_id": order_id,
            "order_sha256": hash_document(order),
            "applied_at": at,
        },
        "recorded_at": at,
        "protocol_version": gate["protocol_version"],
        "schema_version": gate["schema_version"],
        "gate_hash": None,
    }
    _write_gate(root, new_gate)
    _append_lineage(
        root,
        manifest["trust_store_id"],
        "gate-transition",
        order_id,
        {
            "order_id": order_id,
            "from_registration_gate": cur_reg,
            "to_registration_gate": new_reg,
            "from_model_execution_gate": gate["model_execution_gate"],
            "to_model_execution_gate": new_exec,
            "owner_rulings": dict(rulings),
        },
        at,
    )
    rebuild_manifest(root, at=at)
    return store_gate_state(root)


# ---------------------------------------------------------------------------
# runtime observation writer (component 7 — operational zone ONLY)
# ---------------------------------------------------------------------------

def record_runtime_observation(
    root: "str | Path", observation: dict, at: "str | None" = None
) -> dict:
    """Record a runtime observation into the OPERATIONAL zone only.

    This is the only operational write path. It structurally CANNOT write
    into the authoritative zone, and it refuses (fail-closed):
      - documents that are not runtime observations (an authoritative
        object type attempted through the operational seam);
      - observations lacking the NON-AUTHORITATIVE / operational markers;
      - non-null registration references that do not resolve to an
        existing authoritative registration (fabricated references);
      - duplicate observation ids (write-once per id).
    """
    root = _resolve(root)
    load_trust_manifest(root)  # fail-closed: store must exist and be valid
    issues = _validate_or_issues(observation, "runtime-observation")
    if issues:
        if isinstance(observation, dict) and observation.get("ecp_object") in (
            "registration-gate-state",
            "owner-gate-order",
            "registration-package",
            "trust-registration",
            "registration-amendment",
            "lineage-event",
            "trust-store-manifest",
        ):
            raise AccessBoundaryError(
                "boundary violation: an authoritative object type "
                f"({observation.get('ecp_object')!r}) cannot be written "
                "through the operational seam"
            )
        raise TrustError("runtime observation invalid: " + "; ".join(issues))
    at = at or _now_iso()
    obs_id = observation["observation_id"]
    target = root / RUNTIME_DIR / f"{obs_id}.json"
    if target.exists():
        raise TrustError(f"observation {obs_id} already exists (write-once per id)")
    ref = observation.get("registration_id")
    if ref is not None:
        if not (root / REGISTRATIONS_DIR / f"{ref}.json").is_file():
            raise TrustError(
                f"observation cites unresolvable registration {ref} "
                "(fail-closed: fabricated references are refused)"
            )
    if observation.get("recorded_at") is None:
        observation = dict(observation)
        observation["recorded_at"] = at
        observation["observation_hash"] = None
        observation["observation_hash"] = hash_document_excluding(
            observation, "observation_hash"
        )
    _write_canonical(target, observation)
    # the manifest is a derived index over ALL zones (never a trust
    # anchor); refresh it so the operational count cannot drift
    rebuild_manifest(root, at=at)
    return observation


# ---------------------------------------------------------------------------
# Registration Authority (components 2, 3, 5, 6 — the governed ceremony)
# ---------------------------------------------------------------------------

def _live_registrations(root: Path) -> "dict[tuple, dict]":
    """Frozen-tuple -> live record (not invalidated by amendment)."""
    live: "dict[tuple, dict]" = {}
    records = {
        p.stem: _load_json(p) for p in _registration_files(root)
    }
    invalidated = set()
    for am_path in _amendment_files(root):
        doc = _load_json(am_path)
        if doc["amendment_kind"] == "invalidation":
            invalidated.add(doc["target_registration_id"])
    for reg_id, record in records.items():
        if reg_id in invalidated:
            continue
        key = (
            record["evaluation_id"],
            record["case"]["case_id"],
            record["case"]["case_version"],
            record["environment_id"],
        )
        if key in live:
            raise TrustInvalid(
                f"duplicate live registration for tuple {key}: "
                f"{live[key]['registration_id']} and {reg_id}"
            )
        live[key] = record
    return live


def _next_treg_id(root: Path) -> str:
    existing = {p.stem for p in _registration_files(root)}
    n = 1
    while f"ECP-TREG-{n:06d}" in existing:
        n += 1
    return f"ECP-TREG-{n:06d}"


def _next_tamnd_id(root: Path) -> str:
    existing = {p.stem for p in _amendment_files(root)}
    n = 1
    while f"ECP-TAMND-{n:06d}" in existing:
        n += 1
    return f"ECP-TAMND-{n:06d}"


class RegistrationAuthority:
    """The governed registration ceremony (order §4/§5).

    The authority is the ONLY writer of registration records and
    amendments. It refuses (fail-closed, each refusal lineage-logged):
    closed gate, malformed package, schema/version failure, commitment
    recomputation mismatch (altered case / ground truth / criterion /
    environment / provenance), Owner-bound citation divergence or
    absence, ground-truth seam break, duplicate frozen tuple, and
    write-once violations. It NEVER invents missing Owner decisions.
    """

    def __init__(self, trust_root: "str | Path", registrar: str):
        root = _resolve(trust_root)
        if not REGISTRAR_PATTERN.fullmatch(registrar or ""):
            raise TrustError(f"invalid registrar {registrar!r}")
        self._root = root
        self.registrar = registrar
        self._manifest = load_trust_manifest(root)

    # -- fail-closed refusal: lineage-logged, never silent -----------------

    def _refuse(self, package_id: str, stage: str, reason: str, at: str) -> "None":
        try:
            _append_lineage(
                self._root,
                self._manifest["trust_store_id"],
                "registration-refused",
                self.registrar,
                {"package_id": package_id, "stage": stage, "reason": reason},
                at,
            )
            rebuild_manifest(self._root, at=at)
        except TrustError:
            # A structurally broken store must not turn a refusal into a
            # partial write: the refusal stands even if the log is broken.
            pass
        raise RegistrationRefused(reason, stage=stage)

    # -- §4 acceptance ------------------------------------------------------

    def submit_registration(self, package: dict, at: "str | None" = None) -> dict:
        """Submit a registration package for acceptance (fail-closed)."""
        from .identity import load_identity

        at = at or _now_iso()
        gate = load_gate_state(self._root)
        package_id = (
            package.get("package_id") if isinstance(package, dict) else None
        ) or "UNPARSEABLE"
        citations = (
            package.get("owner_ruling_citations", {})
            if isinstance(package, dict)
            else {}
        )
        slot_summary = {slot: citations.get(slot) for slot in OWNER_BOUND_SLOTS}

        # 1. gate check FIRST (order §10 — the cheapest fail-closed exit)
        if gate["registration_gate"] != "OPEN":
            self._refuse(
                package_id,
                "gate",
                "REFUSED: the registration gate is CLOSED "
                f"({gate['registration_gate']}) — M3-RG0 §10 / ADJ-06 hard "
                "precondition; only an explicit owner gate order "
                "(owner-gate-order instrument, all six Owner-bound rulings "
                "supplied) can open it; Owner-bound openings in force: "
                + json.dumps(slot_summary),
                at,
            )

        # 2. package schema + versions
        issues = _validate_or_issues(package, "registration-package")
        if issues:
            self._refuse(
                package_id,
                "package",
                "REFUSED: registration package malformed: " + "; ".join(issues),
                at,
            )
        if package["package_hash"] != hash_document_excluding(package, "package_hash"):
            self._refuse(
                package_id,
                "commitments",
                "REFUSED: package_hash does not recompute — the package was "
                "modified after hashing (altered-submission detection)",
                at,
            )

        # 3. Owner-bound citations must match the authoritative gate exactly
        gate_citations = gate["owner_ruling_citations"]
        for slot in OWNER_BOUND_SLOTS:
            value = package["owner_ruling_citations"].get(slot)
            if not isinstance(value, str) or not value.strip():
                self._refuse(
                    package_id,
                    "owner-bound",
                    f"REFUSED: Owner-bound slot {slot} absent in the package — "
                    "missing mandatory trust inputs are REFUSED/BLOCKED, "
                    "never inferred (order §4/§11 fail-closed)",
                    at,
                )
            if value != gate_citations.get(slot):
                self._refuse(
                    package_id,
                    "owner-bound",
                    f"REFUSED: Owner-bound slot {slot} citation divergence — "
                    f"package cites {value!r}, authoritative gate holds "
                    f"{gate_citations.get(slot)!r} (never merged, never "
                    "reinterpreted)",
                    at,
                )

        # 4. case document validation (public contract)
        case_document = package["case_document"]
        issues = validate_document(case_document, "case") + version_issues(case_document)
        if issues:
            self._refuse(
                package_id,
                "case",
                "REFUSED: embedded case document invalid: " + "; ".join(issues),
                at,
            )
        reference = case_document.get("ground_truth_reference") or {}
        case_commitment = reference.get("commitment")
        if not isinstance(case_commitment, str) or not HEX64_PATTERN.fullmatch(
            case_commitment
        ):
            self._refuse(
                package_id,
                "case",
                "REFUSED: case carries no valid ground-truth commitment",
                at,
            )
        if reference.get("sealing_status") != "sealed":
            self._refuse(
                package_id,
                "case",
                "REFUSED: case ground_truth_reference.sealing_status must be "
                "'sealed' before registration",
                at,
            )

        # 5. ground-truth seam (commitment equality, never content access)
        gt = package["ground_truth"]
        if gt["commitment"] != case_commitment:
            self._refuse(
                package_id,
                "ground-truth",
                "REFUSED: ground-truth commitment divergence — package cites "
                f"{gt['commitment']}, case cites {case_commitment} "
                "(seam broken; nothing was written)",
                at,
            )

        # 6. criterion freeze check (criterion tampering detection)
        if package["success_criterion"] != case_document.get("success_criterion"):
            self._refuse(
                package_id,
                "commitments",
                "REFUSED: success-criterion divergence — the package's frozen "
                "criterion copy differs from the case document's criterion "
                "(altered criterion detected)",
                at,
            )

        # 7. commitment recomputation (order §7 — all document commitments
        #    are derived here, never trusted from the package). The
        #    criterion may be a plain string (the case contract pins it as
        #    a non-empty string), so its commitment wraps it in a JSON
        #    object to stay canonical: hash({"success_criterion": value}).
        commitments = {
            "algorithm": "sha256",
            "canonicalization": "ECP-CANONICAL-JSON-1.0",
            "case": hash_document(case_document),
            "ground_truth": gt["commitment"],
            "criterion": hash_document({"success_criterion": package["success_criterion"]}),
            "environment": hash_document(package["environment"]),
            "provenance": hash_document(package["provenance"]),
            "package": package["package_hash"],
        }

        # 8. duplicate control (frozen tuple)
        try:
            live = _live_registrations(self._root)
        except TrustInvalid as exc:
            raise TrustInvalid(f"trust store unreadable: {exc}") from exc
        candidate_key = (
            package["evaluation_id"],
            case_document["case_id"],
            case_document["case_version"],
            package["environment"]["environment_id"],
        )
        for existing_key, existing in live.items():
            if existing_key == candidate_key:
                self._refuse(
                    package_id,
                    "duplicate",
                    "REFUSED: a live registration already exists for this "
                    f"frozen tuple: {existing['registration_id']} — "
                    "supersede/ invalidate it explicitly (amendment), never "
                    "duplicate it",
                    at,
                )

        # 9. deterministic identity + immutable record (order §5)
        ident = load_identity()
        registration_id = _next_treg_id(self._root)
        count, head = _lineage_head(self._root)
        record = {
            "ecp_object": "trust-registration",
            "registration_id": registration_id,
            "package_id": package["package_id"],
            "evaluation_id": package["evaluation_id"],
            "case": {
                "case_id": case_document["case_id"],
                "case_version": case_document["case_version"],
            },
            "environment_id": package["environment"]["environment_id"],
            "commitments": commitments,
            "owner_ruling_citations": {
                slot: package["owner_ruling_citations"][slot]
                for slot in OWNER_BOUND_SLOTS
            },
            "authority": {
                "registrar": self.registrar,
                "decision": "ACCEPTED",
                "decided_at": at,
            },
            "gate": {
                "registration_gate": gate["registration_gate"],
                "gate_id": gate["gate_id"],
                "gate_order_id": gate["gate_order_reference"]["order_id"],
            },
            "lineage": {"event_index": count + 1},
            "registered_at": at,
            "immutability": IMMUTABILITY_CLAUSE,
            "hash_algorithm": "sha256",
            "canonicalization": "ECP-CANONICAL-JSON-1.0",
            "protocol_version": ident["protocol_version"],
            "schema_version": ident["schema_version"],
            "registration_hash": None,
        }
        record["registration_hash"] = hash_document_excluding(
            record, "registration_hash"
        )
        record_hash = hash_document(record)

        record_path = self._root / REGISTRATIONS_DIR / f"{registration_id}.json"
        if record_path.exists():
            raise WriteOnceViolation(
                f"registration record {registration_id} already exists "
                "(monotone identity discipline violated)"
            )

        # 10. append the accepting lineage event (the event cites the
        #     record hash — bidirectional binding, no circular hashing)
        event = _append_lineage(
            self._root,
            self._manifest["trust_store_id"],
            "registration-accepted",
            self.registrar,
            {
                "registration_id": registration_id,
                "record_hash": record_hash,
                "registration_hash": record["registration_hash"],
                "package_id": package["package_id"],
                "evaluation_id": package["evaluation_id"],
                "case_id": case_document["case_id"],
                "case_version": case_document["case_version"],
                "commitments": commitments,
            },
            at,
        )
        _write_canonical(record_path, record)
        rebuild_manifest(self._root, at=at)
        return {
            "registration_id": registration_id,
            "registration_hash": record["registration_hash"],
            "record_hash": record_hash,
            "event_index": event["event_index"],
            "event_hash": event["event_hash"],
            "commitments": commitments,
            "registration_record": record,
            "lineage_event": event,
        }

    # -- §5 amendments (new events, never rewrites) -------------------------

    def amend_registration(self, request: dict, at: "str | None" = None) -> dict:
        """Record an amendment event (append-only; original untouched).

        *request* is the amendment REQUEST (not the final document): it
        carries ``target_registration_id``, ``target_registration_hash``,
        ``amendment_kind``, ``motivation`` and (unless invalidating) the
        ``replacement`` content. The authority assigns the deterministic
        amendment identity, recomputes the new commitments, builds the
        schema-valid amendment document and binds it to the lineage —
        the ORIGINAL record is never touched.
        """
        from .identity import load_identity

        at = at or _now_iso()
        load_trust_manifest(self._root)
        if not isinstance(request, dict):
            raise AmendmentRefused("REFUSED: amendment request must be a JSON object")
        for field in ("target_registration_id", "target_registration_hash", "amendment_kind", "motivation"):
            if field not in request:
                raise AmendmentRefused(f"REFUSED: amendment request missing {field}")
        kind = request["amendment_kind"]
        if kind not in ("environment-revision", "provenance-correction", "invalidation"):
            raise AmendmentRefused(f"REFUSED: unknown amendment_kind {kind!r}")
        if not isinstance(request["motivation"], str) or not request["motivation"].strip():
            raise AmendmentRefused("REFUSED: amendment motivation is required (silent corrections are forbidden)")
        replacement = request.get("replacement")
        if kind == "invalidation":
            if replacement:
                raise AmendmentRefused(
                    "REFUSED: invalidation carries no replacement content"
                )
        else:
            if not isinstance(replacement, dict) or not replacement:
                raise AmendmentRefused(
                    "REFUSED: non-invalidating amendments require replacement "
                    "content (environment and/or provenance)"
                )
            illegal = set(replacement) - {"environment", "provenance"}
            if illegal:
                raise AmendmentRefused(
                    "REFUSED: replacement fields outside the amendable set "
                    f"{sorted(illegal)} — case content and ground truth are "
                    "never amendable; invalidation is the only path"
                )
            if kind == "environment-revision" and "environment" not in replacement:
                raise AmendmentRefused(
                    "REFUSED: environment-revision requires replacement.environment"
                )
            if kind == "provenance-correction" and "provenance" not in replacement:
                raise AmendmentRefused(
                    "REFUSED: provenance-correction requires replacement.provenance"
                )
            if "environment" in replacement and (
                not isinstance(replacement["environment"], dict)
                or "environment_id" not in replacement["environment"]
            ):
                raise AmendmentRefused(
                    "REFUSED: replacement.environment requires environment_id"
                )
            if "provenance" in replacement and (
                not isinstance(replacement["provenance"], dict)
                or "origin" not in replacement["provenance"]
            ):
                raise AmendmentRefused(
                    "REFUSED: replacement.provenance requires origin"
                )

        target_id = request["target_registration_id"]
        target_path = self._root / REGISTRATIONS_DIR / f"{target_id}.json"
        if not target_path.is_file():
            raise AmendmentRefused(
                f"REFUSED: target registration {target_id} does not exist"
            )
        target = _load_json(target_path)
        target_hash = hash_document(target)
        if request["target_registration_hash"] != target_hash:
            raise AmendmentRefused(
                "REFUSED: target_registration_hash divergence — the "
                "amendment does not bind to the exact original record "
                "(stale or mismatched amendment)"
            )
        for am_path in _amendment_files(self._root):
            doc = _load_json(am_path)
            if doc["target_registration_id"] == target_id:
                if doc["amendment_kind"] == "invalidation":
                    raise AmendmentRefused(
                        f"REFUSED: {target_id} is already invalidated; "
                        "further amendments are refused (append-only "
                        "history preserves the invalidation)"
                    )

        new_commitments: "dict[str, str]" = {}
        if replacement:
            if "environment" in replacement:
                new_commitments["environment"] = hash_document(
                    replacement["environment"]
                )
            if "provenance" in replacement:
                new_commitments["provenance"] = hash_document(
                    replacement["provenance"]
                )

        ident = load_identity()
        amendment_id = _next_tamnd_id(self._root)
        count, head = _lineage_head(self._root)
        document = {
            "ecp_object": "registration-amendment",
            "amendment_id": amendment_id,
            "target_registration_id": target_id,
            "target_registration_hash": request["target_registration_hash"],
            "amendment_kind": kind,
            "motivation": request["motivation"],
            "lineage": {"event_index": count + 1},
            "recorded_at": at,
            "protocol_version": ident["protocol_version"],
            "schema_version": ident["schema_version"],
            "amendment_hash": None,
        }
        if replacement:
            document["replacement"] = _clone(replacement)
            document["new_commitments"] = dict(new_commitments)
        document["amendment_hash"] = hash_document_excluding(
            document, "amendment_hash"
        )
        # self-check: the constructed document must be schema-valid before
        # anything is written (fail-closed construction)
        issues = _validate_or_issues(document, "registration-amendment")
        if issues:
            raise TrustError(
                "constructed amendment invalid: " + "; ".join(issues)
            )
        amendment_path = self._root / AMENDMENTS_DIR / f"{amendment_id}.json"
        if amendment_path.exists():
            raise WriteOnceViolation(
                f"amendment {amendment_id} already exists"
            )
        event = _append_lineage(
            self._root,
            self._manifest["trust_store_id"],
            "amendment-recorded",
            self.registrar,
            {
                "amendment_id": amendment_id,
                "target_registration_id": target_id,
                "target_registration_hash": request["target_registration_hash"],
                "amendment_kind": kind,
                "amendment_hash": document["amendment_hash"],
                "new_commitments": dict(new_commitments),
            },
            at,
        )
        _write_canonical(amendment_path, document)
        rebuild_manifest(self._root, at=at)
        return {
            "amendment_id": amendment_id,
            "amendment_hash": document["amendment_hash"],
            "event_index": event["event_index"],
            "event_hash": event["event_hash"],
            "amendment_document": document,
            "lineage_event": event,
        }


# ---------------------------------------------------------------------------
# verification (component 8 — full deterministic recomputation, order §11)
# ---------------------------------------------------------------------------

def _walk_gate_history(events: "list[dict]") -> "tuple[str, list[str]]":
    """Replay the lineage to reconstruct the registration-gate timeline.

    Returns (final_registration_gate_state, issues). Every
    registration-accepted event must fall inside an OPEN window; the
    replayed final state must equal the authoritative gate.json.
    """
    issues: "list[str]" = []
    state = "CLOSED"
    if not events or events[0]["event_kind"] != "trust-init":
        issues.append("lineage: first event is not trust-init")
    for event in events:
        kind = event["event_kind"]
        payload = event.get("payload", {})
        if kind == "gate-transition":
            if payload.get("from_registration_gate") != state:
                issues.append(
                    f"lineage {event['event_index']}: gate-transition claims "
                    f"from {payload.get('from_registration_gate')!r} but the "
                    f"replayed state is {state!r}"
                )
            state = payload.get("to_registration_gate", state)
        elif kind == "registration-accepted":
            if state != "OPEN":
                issues.append(
                    f"lineage {event['event_index']}: registration-accepted "
                    f"while the replayed gate state is {state!r} (acceptance "
                    "is only legal inside an OPEN window)"
                )
    return state, issues


def verify_trust_store(root: "str | Path") -> dict:
    """Full deterministic verification of a trust store (order §11).

    Recomputes everything from the files alone: manifest (derived index
    cross-check), gate state (schema + self-hash + gate-history replay),
    every registration record (schema, self-hash, record hash, lineage
    binding, citations, duplicate control), every amendment (schema,
    self-hash, lineage binding, target binding, invalidation rules), the
    lineage chain (contiguity, chaining, hashes), zone ownership markers
    (operational documents must be NON-AUTHORITATIVE; authoritative types
    may not appear outside the authoritative zone), the evidence-zone
    writer prohibition (any non-README file at 0.7.0 is an issue —
    execution cannot occur merely because the infrastructure exists) and
    the state/reference-truth separation invariants.

    Returns a report dict; ``ok`` is True only when ``issues`` is empty.
    This never raises on content problems (they are issues); structural
    unreadability is also reported as issues (fail-closed reporting).
    """
    root = _resolve(root)
    issues: "list[str]" = []

    def report(**extra):
        base = {
            "ecp_object": "trust-verification-report",
            "trust_root": str(root),
            "ok": not issues,
            "issues": list(issues),
        }
        base.update(extra)
        return base

    # -- manifest ----------------------------------------------------------
    # Read the manifest raw first (without hash verification) so that
    # a canonically-recomputed tampered manifest_hash does not prevent
    # us from reaching the drift cross-check below.  We then separately
    # verify the self-hash and report it as an issue rather than raising.
    manifest_path = root / MANIFEST_FILE
    if not manifest_path.is_file():
        issues.append(f"manifest unreadable: no trust store manifest at {manifest_path}")
        return report()
    try:
        manifest = _load_json(manifest_path)
    except Exception as exc:
        issues.append(f"manifest unreadable: {exc}")
        return report()
    # Cross-check the derived index before schema validation and before loading
    # the remaining trust-store objects. This ensures canonical manifest
    # tampering is reported as drift even when a platform's JSON Schema
    # validator rejects another aspect of the same document first.
    manifest_disk_counts = {
        "registrations": len(list((root / REGISTRATIONS_DIR).glob("ECP-TREG-*.json"))),
        "amendments": len(list((root / AMENDMENTS_DIR).glob("ECP-TAMND-*.json"))),
        "lineage_events": len(list((root / LINEAGE_DIR).glob("*.json"))),
    }
    manifest_authoritative = manifest.get("zones", {}).get("authoritative", {})
    for key, value in manifest_disk_counts.items():
        if manifest_authoritative.get(key) != value:
            issues.append(
                f"manifest drift: zones.authoritative.{key} = "
                f"{manifest_authoritative.get(key)} but disk holds {value}"
            )

    # schema check (fail-closed on structural problems)
    _m_issues = _validate_or_issues(manifest, "trust-store-manifest")
    if _m_issues:
        issues.append("manifest invalid: " + "; ".join(_m_issues[:3]))
        return report()
    # self-hash check: report as issue, do NOT return — drift check must run
    if manifest.get("manifest_hash") != hash_document_excluding(manifest, "manifest_hash"):
        issues.append("manifest: manifest_hash does not recompute")

    # -- gate ---------------------------------------------------------------
    try:
        gate = load_gate_state(root)
    except TrustInvalid as exc:
        issues.append(f"gate state: {exc}")
        return report()
    if gate["registration_gate"] == "OPEN":
        ref = gate.get("gate_order_reference")
        if not ref or not GATEORDER_ID_PATTERN.fullmatch(ref.get("order_id", "")):
            issues.append("gate state: OPEN without a valid gate_order_reference")
        for slot in OWNER_BOUND_SLOTS:
            if not isinstance(gate["owner_ruling_citations"].get(slot), str):
                issues.append(f"gate state: OPEN with unresolved citation {slot}")
    if gate["model_execution_gate"] == "OPEN" and gate["registration_gate"] != "OPEN":
        issues.append("gate state: model execution OPEN while registration CLOSED")

    # -- lineage chain ------------------------------------------------------
    try:
        events = _load_lineage(root)
    except TrustInvalid as exc:
        issues.append(f"lineage: {exc}")
        return report()
    prev = GENESIS_HASH
    for event in events:
        idx = event.get("event_index")
        if event.get("prev_event_hash") != prev:
            issues.append(f"lineage {idx}: prev_event_hash chain break")
        if event.get("event_hash") != hash_document_excluding(event, "event_hash"):
            issues.append(f"lineage {idx}: event_hash does not recompute")
        ev_issues = _validate_or_issues(event, "lineage-event")
        if ev_issues:
            issues.append(f"lineage {idx}: " + "; ".join(ev_issues[:3]))
        prev = event.get("event_hash", prev)
    replayed_state, gate_history_issues = _walk_gate_history(events)
    issues.extend(gate_history_issues)
    if replayed_state != gate["registration_gate"]:
        issues.append(
            "gate state: lineage replay ends at "
            f"{replayed_state!r} but gate.json holds "
            f"{gate['registration_gate']!r}"
        )

    # -- registration records ----------------------------------------------
    accepted_payloads = {
        e["payload"].get("registration_id"): e
        for e in events
        if e["event_kind"] == "registration-accepted"
    }
    live_keys: "dict[tuple, str]" = {}
    invalidated: "set[str]" = set()
    for path in _amendment_files(root):
        try:
            doc = _load_json(path)
            if doc.get("amendment_kind") == "invalidation":
                invalidated.add(doc.get("target_registration_id"))
        except Exception:  # pragma: no cover - defensive
            issues.append(f"{path.name}: unreadable")
    reg_files = _registration_files(root)
    expected_index = 1
    for path in reg_files:
        try:
            record = _load_json(path)
        except Exception:
            issues.append(f"{path.name}: unreadable JSON")
            continue
        # hash integrity check FIRST — must not be hidden by a schema-fail
        # continue; the record may fail schema due to non-canonical encoding
        # written by a test/tool, but the tamper-detection message must still
        # appear.
        if record.get("registration_hash") != hash_document_excluding(
            record, "registration_hash"
        ):
            issues.append(f"{path.name}: registration_hash does not recompute")
        rid = record.get("registration_id")
        event = accepted_payloads.get(rid)
        if event is not None and event["payload"].get("record_hash") != hash_document(record):
            issues.append(f"{rid}: lineage event record_hash does not match the record")
        rec_issues = _validate_or_issues(record, "trust-registration")
        if rec_issues:
            issues.append(f"{path.name}: " + "; ".join(rec_issues[:3]))
            continue
        rid = record["registration_id"]
        if rid != path.stem:
            issues.append(f"{path.name}: registration_id/file name mismatch ({rid})")
        if int(rid.split("-")[-1]) != expected_index:
            issues.append(
                f"{path.name}: monotone-identity discipline broken "
                f"(expected ECP-TREG-{expected_index:06d})"
            )
        expected_index += 1
        event = accepted_payloads.get(rid)
        if event is None:
            issues.append(
                f"{rid}: no registration-accepted lineage event (ungoverned "
                "write detected — records cannot appear outside the authority)"
            )
        else:
            if event.get("event_index") != record["lineage"]["event_index"]:
                issues.append(f"{rid}: lineage event_index binding mismatch")
        for slot in OWNER_BOUND_SLOTS:
            if not isinstance(record["owner_ruling_citations"].get(slot), str):
                issues.append(f"{rid}: accepted record with unresolved citation {slot}")
        if rid not in invalidated:
            key = (
                record["evaluation_id"],
                record["case"]["case_id"],
                record["case"]["case_version"],
                record["environment_id"],
            )
            if key in live_keys:
                issues.append(
                    f"duplicate live tuple {key}: {live_keys[key]} and {rid}"
                )
            else:
                live_keys[key] = rid
    orphan_accepted = set(accepted_payloads) - {p.stem for p in reg_files}
    if orphan_accepted:
        issues.append(
            "lineage registration-accepted events without records: "
            + ", ".join(sorted(orphan_accepted))
        )

    # -- amendments ---------------------------------------------------------
    invalidations: "set[str]" = set()
    for path in _amendment_files(root):
        try:
            doc = _load_json(path)
        except Exception:
            issues.append(f"{path.name}: unreadable JSON")
            continue
        am_issues = _validate_or_issues(doc, "registration-amendment")
        if am_issues:
            issues.append(f"{path.name}: " + "; ".join(am_issues[:3]))
            continue
        if doc["amendment_hash"] != hash_document_excluding(doc, "amendment_hash"):
            issues.append(f"{path.name}: amendment_hash does not recompute")
        target_id = doc["target_registration_id"]
        target_path = root / REGISTRATIONS_DIR / f"{target_id}.json"
        if not target_path.is_file():
            issues.append(f"{path.name}: target {target_id} does not exist")
        else:
            target = _load_json(target_path)
            if doc["target_registration_hash"] != hash_document(target):
                issues.append(
                    f"{path.name}: target_registration_hash does not bind to "
                    f"the current original record {target_id}"
                )
        if target_id in invalidations:
            issues.append(
                f"{path.name}: amendment after invalidation of {target_id}"
            )
        if doc["amendment_kind"] == "invalidation":
            invalidations.add(target_id)
        amend_events = {
            e["payload"].get("amendment_id"): e
            for e in events
            if e["event_kind"] == "amendment-recorded"
        }
        ev = amend_events.get(doc["amendment_id"])
        if ev is None:
            issues.append(
                f"{path.name}: no amendment-recorded lineage event "
                "(ungoverned write detected)"
            )
        elif ev["payload"].get("amendment_hash") != doc["amendment_hash"]:
            issues.append(f"{path.name}: lineage amendment_hash binding mismatch")

    # -- operational zone (ownership markers) -------------------------------
    observations = 0
    for path in _observation_files(root):
        observations += 1
        try:
            doc = _load_json(path)
        except Exception:
            issues.append(f"{path.name}: unreadable JSON")
            continue
        obs_issues = _validate_or_issues(doc, "runtime-observation")
        if obs_issues:
            issues.append(f"{path.name}: " + "; ".join(obs_issues[:3]))
            continue
        if doc.get("authority_class") != "NON-AUTHORITATIVE":
            issues.append(f"{path.name}: operational document missing NON-AUTHORITATIVE marker")
        if doc.get("zone") != "operational":
            issues.append(f"{path.name}: operational document missing zone marker")
        if doc.get("observation_hash") != hash_document_excluding(doc, "observation_hash"):
            issues.append(f"{path.name}: observation_hash does not recompute")
        ref = doc.get("registration_id")
        if ref is not None and not (root / REGISTRATIONS_DIR / f"{ref}.json").is_file():
            issues.append(f"{path.name}: unresolvable registration reference {ref}")
    # authoritative object types must NOT appear in the operational zone
    for path in (root / OPERATIONAL_DIR).rglob("*.json"):
        try:
            doc = _load_json(path)
        except Exception:
            issues.append(f"operational/{path.name}: unreadable JSON")
            continue
        if doc.get("ecp_object") != "runtime-observation":
            issues.append(
                f"operational/{path.name}: non-operational object type "
                f"{doc.get('ecp_object')!r} in the operational zone (zone "
                "ownership violation)"
            )

    # -- evidence zone (writer prohibition at 0.7.0) -------------------------
    evidence_files = []
    if (root / EVIDENCE_DIR).is_dir():
        for path in (root / EVIDENCE_DIR).iterdir():
            if path.is_file() and path.name != "README.md":
                evidence_files.append(path.name)
                issues.append(
                    f"evidence/{path.name}: evidence file present at 0.7.0 — "
                    "no evidence writer exists (model execution gate CLOSED; "
                    "execution cannot occur merely because the infrastructure "
                    "exists)"
                )

    # -- manifest cross-check (derived index, never trusted) ----------------
    cross = {
        "registrations": len(reg_files),
        "amendments": len(_amendment_files(root)),
        "lineage_events": len(events),
    }
    az = manifest["zones"]["authoritative"]
    for key, value in cross.items():
        if az.get(key) != value:
            issues.append(
                f"manifest drift: zones.authoritative.{key} = {az.get(key)} "
                f"but disk holds {value}"
            )
    if manifest["zones"]["operational"].get("observations") != observations:
        issues.append("manifest drift: operational.observations count mismatch")
    if manifest["zones"]["evidence"].get("files") != len(evidence_files):
        issues.append("manifest drift: evidence.files count mismatch")
    if manifest["gate"].get("gate_hash") != gate["gate_hash"]:
        issues.append("manifest drift: gate hash mismatch")
    if manifest["gate"].get("registration_gate") != gate["registration_gate"]:
        issues.append("manifest drift: gate registration state mismatch")
    if manifest["lineage"].get("event_count") != len(events):
        issues.append("manifest drift: lineage event_count mismatch")
    head = events[-1]["event_hash"] if events else GENESIS_HASH
    if manifest["lineage"].get("head_event_hash") != head:
        issues.append("manifest drift: lineage head mismatch")

    # -- state/reference-truth separation invariant --------------------------
    # reference truth resolution must not consult operational/evidence zones:
    # structural by construction; re-verify the reference truth end-to-end.
    try:
        truth = store_reference_truth(root)
        if len(truth["registrations"]) != len(reg_files):
            issues.append("reference truth: registration count divergence")
    except TrustInvalid as exc:
        issues.append(f"reference truth: {exc}")

    return report(
        trust_store_id=manifest["trust_store_id"],
        scope=manifest["scope"],
        gate={
            "registration_gate": gate["registration_gate"],
            "model_execution_gate": gate["model_execution_gate"],
            "scientific_results": gate["scientific_results"],
            "gate_hash": gate["gate_hash"],
        },
        counts={
            "registrations": len(reg_files),
            "amendments": len(_amendment_files(root)),
            "lineage_events": len(events),
            "runtime_observations": observations,
            "evidence_files": len(evidence_files),
            "live_registrations": len(live_keys),
        },
    )
