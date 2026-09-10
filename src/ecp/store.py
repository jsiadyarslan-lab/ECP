"""Protected Evidence Store — minimal CAS foundation (R1-I, Option C).

Implements the custody half of the coupled seam decided in
``docs/M3-R1-ARCHITECTURE-DECISION.md`` (Option C — minimal coupled
foundation, owner-approved with O1–O8):

- **content-addressed, write-once blob storage** for sealed ground truth:
  ``zones/sealed-gt/<sha256[:2]>/<sha256>.json`` holds exactly the
  ``ECP-CANONICAL-JSON-1.0`` bytes of the sealed document, so the storage
  path is a function of the content hash — "modifying" a blob produces a
  different path and the original bytes remain in place;
- **a hash-chained, append-only operation log** (``oplog/NNNNNNNN.json``):
  every store operation (init, seal, idempotent re-seal, rejected seal) is
  appended and chained (each entry carries the previous entry's hash);
- **a deterministic store manifest** (``store.json``, contract
  ``store-manifest`` schema 0.2.0) indexing seals and checkpointing the
  oplog head — a derived, re-computable index, never a trust anchor;
- **atomic two-phase writes** (temp file + ``os.replace``): a crashed
  operation leaves either no trace or a complete record, never a partial
  write;
- **full verification** (:func:`verify_store`) re-derives everything from
  the oplog, the seal index and the blobs.

The store lives OUTSIDE the public repository — its root is a parameter;
nothing in this module writes into the repository tree. There is
deliberately NO API that serves ground-truth content to an execution
context: the execution environment has no read path to this store by
construction (the only readers are the registrar ceremony, which treats
bytes as opaque, and — at a future gate — adjudication-time audit).

This is infrastructure only: nothing here registers a case, executes a
model, or produces scientific results.
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .canonical import canonical_bytes
from .hashing import hash_document, hash_document_excluding, sha256_hex
from .validate import validate_document
from .versions import version_issues

GENESIS_HASH = "0" * 64
OPLOG_PAD = 8

SEAL_ZONE = "zones/sealed-gt"
RESERVED_ZONES = ("zones/hidden-cases", "zones/evidence", "zones/exports")
MANIFEST_FILE = "store.json"
OPLOG_DIR = "oplog"

BLOB_PATH_PATTERN = re.compile(r"^zones/sealed-gt/([0-9a-f]{2})/([0-9a-f]{64})\.json$")

OP_KINDS = ("init", "seal", "idempotent-seal", "rejected-seal")


class StoreError(Exception):
    """Base class for protected-store errors."""


class StoreInvalid(StoreError):
    """The store state on disk is structurally invalid or unverifiable."""


class SealRejected(StoreError):
    """A seal attempt was rejected (schema, class or content problem)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class WriteOnceViolation(SealRejected):
    """A seal attempt tried to replace committed content (write-once)."""


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


def _atomic_write_canonical(path: Path, document: dict) -> None:
    _atomic_write_bytes(path, canonical_bytes(document))


def _load_json(path: Path) -> dict:
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def _oplog_entry_path(root: Path, index: int) -> Path:
    return root / OPLOG_DIR / f"{index:0{OPLOG_PAD}d}.json"


def _oplog_head(root: Path) -> "tuple[int, str]":
    """Current oplog (entry_count, head_oplog_hash) — structural read."""
    count = 0
    head = GENESIS_HASH
    for path in sorted((root / OPLOG_DIR).glob("*.json")):
        index = int(path.stem)
        if index != count + 1:
            raise StoreInvalid(f"oplog gap/duplicate at index {index}")
        entry = _load_json(path)
        head = entry["oplog_hash"]
        count = index
    return count, head


def _append_oplog(root: Path, op: str, store_id: str, at: str, details: dict) -> dict:
    """Append one chained oplog entry (the ONLY mutation primitive).

    For ``seal`` entries, ``details.oplog_index`` is auto-filled with the
    new entry's own index (the seal record points at the entry that created
    it). For ``idempotent-seal`` entries, ``details.oplog_index`` refers to
    the ORIGINAL seal entry being re-affirmed (passed by the caller).
    """
    if op not in OP_KINDS:
        raise StoreError(f"unknown op {op!r}")
    count, head = _oplog_head(root)
    index = count + 1
    details = dict(details)
    if op == "seal":
        details["oplog_index"] = index
    entry = {
        "oplog_index": index,
        "op": op,
        "store_id": store_id,
        "claimed_at": at,
        "details": details,
        "prev_oplog_hash": head,
        "oplog_hash": None,
    }
    entry["oplog_hash"] = hash_document_excluding(entry, "oplog_hash")
    _atomic_write_canonical(_oplog_entry_path(root, index), entry)
    return entry


def _manifest(
    store_id: str,
    scope: str,
    created_at: str,
    protocol_version: str,
    schema_version: str,
    seals: "list[dict]",
    oplog_count: int,
    oplog_head: str,
    notes: "list[str] | None" = None,
) -> dict:
    """Build the deterministic store manifest document."""
    manifest = {
        "ecp_object": "store-manifest",
        "store_id": store_id,
        "scope": scope,
        "protocol_version": protocol_version,
        "schema_version": schema_version,
        "created_at": created_at,
        "hash_algorithm": "sha256",
        "canonicalization": "ECP-CANONICAL-JSON-1.0",
        "zones": {
            "sealed-gt": {"blob_count": len({seal["commitment"] for seal in seals})},
            "hidden-cases": {"state": "reserved"},
            "evidence": {"state": "reserved"},
            "exports": {"state": "reserved"},
        },
        "seals": sorted(seals, key=lambda s: (s["case_id"], s["case_version"])),
        "oplog": {"entry_count": oplog_count, "head_oplog_hash": oplog_head},
    }
    if notes:
        manifest["notes"] = list(notes)
    manifest["manifest_hash"] = hash_document_excluding(manifest, "manifest_hash")
    return manifest


def _write_manifest(root: Path, manifest: dict) -> None:
    _atomic_write_canonical(root / MANIFEST_FILE, manifest)


def load_manifest(root: "str | Path") -> dict:
    """Load and validate the store manifest (schema + version compat)."""
    root = _resolve(root)
    path = root / MANIFEST_FILE
    if not path.is_file():
        raise StoreInvalid(f"no store manifest at {path}")
    manifest = _load_json(path)
    issues = validate_document(manifest, "store-manifest") + version_issues(manifest)
    if issues:
        raise StoreInvalid("store manifest invalid: " + "; ".join(issues))
    if manifest["manifest_hash"] != hash_document_excluding(manifest, "manifest_hash"):
        raise StoreInvalid("store manifest manifest_hash does not recompute")
    return manifest


def init_store(
    root: "str | Path",
    store_id: str,
    scope: str,
    at: "str | None" = None,
    identity: "dict | None" = None,
) -> dict:
    """Initialize a new (empty) protected store at *root*.

    Args:
        root: store root directory (outside the public repository). Must
            not exist, or be an empty directory.
        store_id: ``ECP-STORE-…`` identifier.
        scope: ``development`` (synthetic fixtures only) or ``operational``.
        at: pinned UTC timestamp (default: now).
        identity: protocol identity (default: repository identity).

    Returns:
        The initial store manifest.
    """
    root = _resolve(root)
    if not re.fullmatch(r"ECP-STORE-[A-Za-z0-9][A-Za-z0-9._:-]*", store_id or ""):
        raise StoreError(f"invalid store_id {store_id!r}")
    if scope not in ("development", "operational"):
        raise StoreError(f"invalid scope {scope!r}")
    if root.exists() and any(root.iterdir()):
        raise StoreError(f"store root is not empty: {root}")

    from .identity import load_identity

    ident = identity or load_identity()
    at = at or _now_iso()

    (root / "zones" / "sealed-gt").mkdir(parents=True, exist_ok=True)
    for zone in RESERVED_ZONES:
        zone_dir = root / zone
        zone_dir.mkdir(parents=True, exist_ok=True)
        readme = zone_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                f"# {zone.split('/')[-1]} (reserved)\n\n"
                "Reserved zone of the ECP protected store. Not implemented at R1-I; "
                "see docs/M3-R1-ARCHITECTURE-DECISION.md and spec/ECP-SPEC.md.\n",
                encoding="utf-8",
            )
    (root / OPLOG_DIR).mkdir(parents=True, exist_ok=True)

    _append_oplog(
        root,
        "init",
        store_id,
        at,
        {"scope": scope},
    )
    count, head = _oplog_head(root)
    manifest = _manifest(
        store_id,
        scope,
        at,
        ident["protocol_version"],
        ident["schema_version"],
        seals=[],
        oplog_count=count,
        oplog_head=head,
    )
    _write_manifest(root, manifest)
    return manifest


def blob_path_for(commitment: str) -> str:
    """Content-addressed relative storage path for *commitment*."""
    return f"{SEAL_ZONE}/{commitment[:2]}/{commitment}.json"


def _seals_from_oplog(root: Path) -> "dict[tuple[str, str], dict]":
    """Rebuild the seal index from the oplog (the authoritative record)."""
    seals: "dict[tuple[str, str], dict]" = {}
    for path in sorted((root / OPLOG_DIR).glob("*.json")):
        entry = _load_json(path)
        if entry["op"] == "rejected-seal":
            continue
        if entry["op"] not in ("seal", "idempotent-seal"):
            if entry["op"] != "init":
                raise StoreInvalid(f"unknown oplog op {entry['op']!r}")
            continue
        details = entry["details"]
        key = (details["case_id"], details["case_version"])
        prior = seals.get(key)
        if entry["op"] == "idempotent-seal" and prior is None:
            raise StoreInvalid(
                f"oplog[{entry['oplog_index']}]: idempotent-seal with no prior seal "
                f"for {key[0]}@{key[1]} (corrupt or tampered oplog)"
            )
        if prior is None:
            seals[key] = {
                "case_id": details["case_id"],
                "case_version": details["case_version"],
                "commitment": details["commitment"],
                "blob_path": details["blob_path"],
                "blob_hash": details["blob_hash"],
                "sealed_at": details["sealed_at"],
                "oplog_index": details["oplog_index"],
            }
        elif prior["commitment"] != details["commitment"]:
            raise StoreInvalid(
                f"oplog records conflicting seals for {key[0]}@{key[1]}"
            )
    return seals


def seal(
    root: "str | Path",
    ground_truth_document: dict,
    at: "str | None" = None,
    identity: "dict | None" = None,
) -> dict:
    """Seal a ground-truth document into the store (write-once, CAS).

    Steps: schema-validate the document; require ``content_class: sealed``;
    compute the canonical commitment; enforce one seal per
    ``(case_id, case_version)`` (identical content is idempotent, different
    content is a :class:`WriteOnceViolation` recorded in the oplog as a
    rejected attempt); write the blob atomically; append the oplog entry;
    rewrite the manifest.

    Returns:
        ``{case_id, case_version, commitment, blob_path, blob_hash,
        oplog_index, idempotent}``.
    """
    root = _resolve(root)
    manifest = load_manifest(root)
    at = at or _now_iso()

    issues = validate_document(ground_truth_document, "ground-truth")
    if issues:
        raise SealRejected(
            "ground-truth document does not validate: " + "; ".join(issues)
        )
    issues = version_issues(ground_truth_document)
    if issues:
        raise SealRejected(
            "ground-truth document version incompatible: " + "; ".join(issues)
        )
    if ground_truth_document.get("content_class") != "sealed":
        raise SealRejected(
            "only content_class 'sealed' documents may be sealed "
            "(format-illustration documents belong in examples/, not in a store)"
        )

    commitment = hash_document(ground_truth_document)
    blob_path = blob_path_for(commitment)
    case_id = ground_truth_document["case_id"]
    case_version = ground_truth_document["case_version"]

    seals = _seals_from_oplog(root)
    prior = seals.get((case_id, case_version))
    if prior is not None:
        if prior["commitment"] != commitment:
            _append_oplog(
                root,
                "rejected-seal",
                manifest["store_id"],
                at,
                {
                    "case_id": case_id,
                    "case_version": case_version,
                    "attempted_commitment": commitment,
                    "reason": "write-once violation: target already sealed with "
                    "different content",
                },
            )
            count, head = _oplog_head(root)
            _write_manifest(
                root,
                _manifest(
                    manifest["store_id"],
                    manifest["scope"],
                    manifest["created_at"],
                    manifest["protocol_version"],
                    manifest["schema_version"],
                    seals=list(seals.values()),
                    oplog_count=count,
                    oplog_head=head,
                    notes=manifest.get("notes"),
                ),
            )
            raise WriteOnceViolation(
                f"case {case_id}@{case_version} is already sealed with a different "
                f"commitment ({prior['commitment']}); write-once is enforced and the "
                "rejected attempt is op-logged"
            )
        # identical content — idempotent
        entry = _append_oplog(
            root,
            "idempotent-seal",
            manifest["store_id"],
            at,
            {
                "case_id": case_id,
                "case_version": case_version,
                "commitment": commitment,
                "blob_path": blob_path,
                "blob_hash": commitment,
                "sealed_at": prior["sealed_at"],
                "oplog_index": prior["oplog_index"],
            },
        )
        count, head = _oplog_head(root)
        _write_manifest(
            root,
            _manifest(
                manifest["store_id"],
                manifest["scope"],
                manifest["created_at"],
                manifest["protocol_version"],
                manifest["schema_version"],
                seals=list(seals.values()),
                oplog_count=count,
                oplog_head=head,
                notes=manifest.get("notes"),
            ),
        )
        return {
            "case_id": case_id,
            "case_version": case_version,
            "commitment": commitment,
            "blob_path": blob_path,
            "blob_hash": commitment,
            "oplog_index": entry["oplog_index"],
            "idempotent": True,
        }

    # CAS check: an existing blob at this path must be byte-identical.
    blob_file = root / blob_path
    if blob_file.exists():
        with open(blob_file, "rb") as fh:
            existing = fh.read()
        if existing != canonical_bytes(ground_truth_document):  # pragma: no cover
            raise SealRejected(
                f"CAS anomaly: blob exists at {blob_path} with different bytes"
            )

    entry = _append_oplog(
        root,
        "seal",
        manifest["store_id"],
        at,
        {
            "case_id": case_id,
            "case_version": case_version,
            "commitment": commitment,
            "blob_path": blob_path,
            "blob_hash": commitment,
            "sealed_at": at,
        },
    )

    _atomic_write_bytes(blob_file, canonical_bytes(ground_truth_document))

    seals[(case_id, case_version)] = {
        "case_id": case_id,
        "case_version": case_version,
        "commitment": commitment,
        "blob_path": blob_path,
        "blob_hash": commitment,
        "sealed_at": at,
        "oplog_index": entry["oplog_index"],
    }
    count, head = _oplog_head(root)
    _write_manifest(
        root,
        _manifest(
            manifest["store_id"],
            manifest["scope"],
            manifest["created_at"],
            manifest["protocol_version"],
            manifest["schema_version"],
            seals=list(seals.values()),
            oplog_count=count,
            oplog_head=head,
            notes=manifest.get("notes"),
        ),
    )
    return {
        "case_id": case_id,
        "case_version": case_version,
        "commitment": commitment,
        "blob_path": blob_path,
        "blob_hash": commitment,
        "oplog_index": entry["oplog_index"],
        "idempotent": False,
    }


def verify_store(root: "str | Path", cases_dir: "str | Path | None" = None) -> dict:
    """Full store verification — recomputation, never trust.

    Checks (all findings, no exceptions):

    1. manifest: schema + version compatibility + manifest_hash recompute;
    2. oplog chain: contiguous indices, prev-linkage, per-entry self-hash,
       head and count match the manifest;
    3. seal index: rebuilt from the oplog equals the manifest seals exactly;
    4. per seal: blob exists, file hash == blob_hash == commitment, blob is
       canonical, schema-valid ground truth with content_class 'sealed';
    5. write-once: no conflicting seals for one (case_id, case_version);
    6. zones: reserved zones contain only README.md; sealed-gt contains
       only CAS-pattern blob files; no orphan blobs;
    7. public-case cross-check (when *cases_dir* is given): any public case
       document matching a sealed (case_id, case_version) must carry the
       same commitment (mismatch = tamper evidence; a case with no public
       document is legitimate — hidden cases).

    Returns:
        ``{"ok": bool, "issues": [...], "seal_count": int,
        "oplog_count": int, "head_oplog_hash": str}``.
    """
    root = _resolve(root)
    issues: "list[str]" = []
    ok = True

    try:
        manifest = load_manifest(root)
    except StoreInvalid as exc:
        return {"ok": False, "issues": [str(exc)], "seal_count": 0, "oplog_count": 0,
                "head_oplog_hash": GENESIS_HASH}

    # 2 — oplog chain
    oplog_count = 0
    head = GENESIS_HASH
    oplog_dir = root / OPLOG_DIR
    for path in sorted(oplog_dir.glob("*.json")):
        index = int(path.stem)
        if index != oplog_count + 1:
            issues.append(f"oplog: expected index {oplog_count + 1}, found {index}")
            ok = False
            break
        try:
            entry = _load_json(path)
            if entry.get("oplog_index") != index:
                issues.append(f"oplog[{index}]: entry_index mismatch")
                ok = False
            if entry.get("prev_oplog_hash") != head:
                issues.append(f"oplog[{index}]: prev_oplog_hash does not chain")
                ok = False
            recomputed = hash_document_excluding(entry, "oplog_hash")
            if entry.get("oplog_hash") != recomputed:
                issues.append(f"oplog[{index}]: oplog_hash does not recompute")
                ok = False
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            issues.append(f"oplog[{index}]: unparseable/corrupt entry ({exc})")
            ok = False
            break
        head = entry["oplog_hash"]
        oplog_count = index
    extra_files = [
        p.name for p in oplog_dir.iterdir()
        if p.is_file() and (not p.name.endswith(".json") or not p.stem.isdigit())
    ]
    if extra_files:
        issues.append(f"oplog: foreign files present: {sorted(extra_files)}")
        ok = False

    if manifest["oplog"]["entry_count"] != oplog_count:
        issues.append(
            f"manifest oplog count {manifest['oplog']['entry_count']} != actual "
            f"{oplog_count}"
        )
        ok = False
    if manifest["oplog"]["head_oplog_hash"] != head:
        issues.append("manifest oplog head does not match actual chain head")
        ok = False

    # 3 — seal index
    try:
        rebuilt = _seals_from_oplog(root)
    except StoreInvalid as exc:
        issues.append(str(exc))
        ok = False
        rebuilt = {}
    manifest_seals = {
        (s["case_id"], s["case_version"]): s for s in manifest["seals"]
    }
    if set(rebuilt) != set(manifest_seals):
        issues.append(
            "manifest seals differ from oplog-derived seals "
            f"(oplog-only: {sorted(set(rebuilt) - set(manifest_seals))}, "
            f"manifest-only: {sorted(set(manifest_seals) - set(rebuilt))})"
        )
        ok = False
    else:
        for key, derived in rebuilt.items():
            if manifest_seals[key] != derived:
                issues.append(f"seal {key[0]}@{key[1]}: manifest entry != oplog entry")
                ok = False

    # 4 — per-seal blob checks
    seen_blobs: "set[str]" = set()
    for key in sorted(rebuilt):
        seal_info = rebuilt[key]
        blob_rel = seal_info["blob_path"]
        blob_file = root / blob_rel
        match = BLOB_PATH_PATTERN.fullmatch(blob_rel)
        if not match or match.group(2) != seal_info["commitment"]:
            issues.append(f"seal {key[0]}@{key[1]}: blob path is not CAS-shaped")
            ok = False
            continue
        seen_blobs.add(blob_rel)
        if not blob_file.is_file():
            issues.append(f"seal {key[0]}@{key[1]}: blob missing at {blob_rel}")
            ok = False
            continue
        raw = blob_file.read_bytes()
        file_hash = sha256_hex(raw)
        if file_hash != seal_info["blob_hash"] or file_hash != seal_info["commitment"]:
            issues.append(
                f"seal {key[0]}@{key[1]}: blob hash mismatch "
                f"(file {file_hash}, recorded {seal_info['blob_hash']}, "
                f"commitment {seal_info['commitment']})"
            )
            ok = False
            continue
        try:
            document = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            issues.append(f"seal {key[0]}@{key[1]}: blob is not valid JSON")
            ok = False
            continue
        if canonical_bytes(document) != raw:
            issues.append(
                f"seal {key[0]}@{key[1]}: blob is not stored in canonical form"
            )
            ok = False
        doc_issues = validate_document(document, "ground-truth") + version_issues(document)
        if doc_issues:
            issues.append(
                f"seal {key[0]}@{key[1]}: blob fails ground-truth contract: "
                + "; ".join(doc_issues)
            )
            ok = False
        if document.get("content_class") != "sealed":
            issues.append(
                f"seal {key[0]}@{key[1]}: blob content_class != 'sealed'"
            )
            ok = False
        if (document.get("case_id"), document.get("case_version")) != key:
            issues.append(f"seal {key[0]}@{key[1]}: blob cites different case identity")
            ok = False

    # 5 — write-once scan is implicit in _seals_from_oplog (raises on conflict);
    # re-check manifest duplicates defensively:
    keys = [(s["case_id"], s["case_version"]) for s in manifest["seals"]]
    if len(keys) != len(set(keys)):
        issues.append("manifest contains duplicate seal targets (write-once broken)")
        ok = False

    # 6 — zones
    for zone in RESERVED_ZONES:
        zone_dir = root / zone
        if not zone_dir.is_dir():
            issues.append(f"zone {zone} missing")
            ok = False
            continue
        foreign = [
            p.name for p in zone_dir.iterdir() if p.name != "README.md"
        ]
        if foreign:
            issues.append(f"zone {zone} contains non-README entries: {sorted(foreign)}")
            ok = False
    sealed_dir = root / SEAL_ZONE
    for path in sealed_dir.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        if rel not in seen_blobs:
            issues.append(f"orphan blob not referenced by any seal: {rel}")
            ok = False
        if not BLOB_PATH_PATTERN.fullmatch(rel):
            issues.append(f"sealed-gt contains non-CAS file: {rel}")
            ok = False

    # 7 — public case cross-check
    if cases_dir is not None:
        cases_root = Path(cases_dir).resolve()
        if cases_root.is_dir():
            public_cases: "dict[tuple[str, str], dict]" = {}
            for path in cases_root.rglob("*.json"):
                if any(part.startswith(".") for part in path.relative_to(cases_root).parts):
                    continue
                try:
                    document = _load_json(path)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if isinstance(document, dict) and document.get("ecp_object") == "case":
                    public_cases[
                        (document.get("case_id"), document.get("case_version"))
                    ] = document
            for key in sorted(rebuilt):
                case = public_cases.get(key)
                if case is None:
                    continue  # hidden case: legitimate
                cited = case.get("ground_truth_reference", {}).get("commitment")
                if cited != rebuilt[key]["commitment"]:
                    issues.append(
                        f"public case {key[0]}@{key[1]} cites commitment {cited}, "
                        f"store seal holds {rebuilt[key]['commitment']} — seam broken"
                    )
                    ok = False
        else:
            issues.append(f"cases_dir does not exist or is not a directory: {cases_dir}")
            ok = False

    return {
        "ok": ok,
        "issues": issues,
        "seal_count": len(rebuilt),
        "oplog_count": oplog_count,
        "head_oplog_hash": head,
    }
