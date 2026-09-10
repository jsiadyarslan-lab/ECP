"""Registration Ledger — append-only, hash-chained (R1-I, Option C).

Implements the authority half of the coupled seam decided in
``docs/M3-R1-ARCHITECTURE-DECISION.md`` (Option C — minimal coupled
foundation, owner-approved with O1–O8). The Registration Authority is NOT
a service: it is an offline CLI ceremony (:func:`register`,
:func:`invalidate`) operating on a plain-file ledger directory, plus
public verification (:func:`ledger_verify`) that recomputes everything
from public data alone. The approved architectural alternatives — cloud
service, daemon + database, blockchain/external consensus — were rejected
in the decision record and are not implemented.

Ledger directory layout (the ledger lives in its own repository,
separate from the ECP contract repository — O1):

::

    <ledger_root>/
      ANCHOR.json          published checkpoint of the chain state
      entries/NNNNNNNN.json   chained ledger entries (schema 0.2.0)
      records/ECP-REG-….json  full registration records (canonical bytes)
      README.md

Guarantees implemented here:

- **append-only**: no entry or record file is ever edited or removed by
  the tooling; a correction is a NEW superseding record; an invalidation
  is an explicit entry of kind ``invalidation``;
- **hash-chained order**: ``entry_hash`` covers the entry including
  ``prev_entry_hash`` — inserting, removing, reordering or editing any
  historical entry breaks every subsequent entry;
- **registration-before-execution (mechanical half)**: the registration
  ceremony requires a sealed store commitment that matches the public
  case's commitment before anything is appended (RA-2 of the decision
  record);
- **registrar-controlled identity**: ``registration_id`` is assigned by
  the ledger (monotone), never chosen by the case author;
- **duplicate control**: at most one LIVE registration per frozen tuple
  (evaluation, case version, system version, condition hash);
- **public verification**: :func:`ledger_verify` recomputes the chain,
  every record hash and registration hash, the duplicate rules and the
  supersession graph, and (when public case documents are supplied)
  cross-checks every frozen ground-truth commitment.

This is infrastructure only: nothing here executes models, scores
results, or adjudicates science.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .canonical import canonical_bytes
from .hashing import hash_document, hash_document_excluding
from .validate import validate_document
from .versions import version_issues

GENESIS_HASH = "0" * 64
ENTRY_PAD = 8

ENTRIES_DIR = "entries"
RECORDS_DIR = "records"
ANCHOR_FILE = "ANCHOR.json"

LEDGER_ID_PATTERN = re.compile(r"^ECP-LEDGER-[A-Za-z0-9][A-Za-z0-9._:-]*$")
REGISTRAR_PATTERN = re.compile(r"^ECP-REGISTRAR-[A-Za-z0-9][A-Za-z0-9._:-]*$")
EVALUATION_ID_PATTERN = re.compile(r"^ECP-EVAL-[A-Za-z0-9][A-Za-z0-9._:-]*$")
REGISTRATION_ID_PATTERN = re.compile(r"^ECP-REG-[A-Za-z0-9][A-Za-z0-9._:-]*$")

REGISTRABLE_CASE_STATUSES = ("candidate", "registered", "active")


class LedgerError(Exception):
    """Base class for ledger errors."""


class LedgerInvalid(LedgerError):
    """The ledger state on disk is structurally invalid."""


class RegistrationRejected(LedgerError):
    """A registration attempt was rejected before any append."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class DuplicateRegistration(RegistrationRejected):
    """A live registration already exists for the frozen tuple."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve(root: "str | Path") -> Path:
    return Path(root).resolve()


def _atomic_write(path: Path, data: bytes) -> None:
    import os
    import uuid

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.tmp-{uuid.uuid4().hex}"
    try:
        with open(temp, "wb") as fh:
            fh.write(data)
        os.replace(temp, path)
    finally:
        if temp.exists():  # pragma: no cover
            temp.unlink()


def _write_canonical(path: Path, document: dict) -> None:
    _atomic_write(path, canonical_bytes(document))


def _load_json(path: Path) -> dict:
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def _entry_path(root: Path, index: int) -> Path:
    return root / ENTRIES_DIR / f"{index:0{ENTRY_PAD}d}.json"


def _entries(root: Path) -> "list[dict]":
    """Load all chain entries in index order (structural read)."""
    entries = []
    expected = 1
    for path in sorted((root / ENTRIES_DIR).glob("*.json")):
        index = int(path.stem)
        if index != expected:
            raise LedgerInvalid(f"entries gap/duplicate at index {index}")
        entries.append(_load_json(path))
        expected += 1
    return entries


def current_head(root: "str | Path") -> "tuple[int, str]":
    """Current chain (entry_count, head_entry_hash)."""
    root = _resolve(root)
    entries = _entries(root)
    if not entries:
        return 0, GENESIS_HASH
    return len(entries), entries[-1]["entry_hash"]


def _next_registration_id(root: Path) -> str:
    existing = {
        p.stem for p in (root / RECORDS_DIR).glob("ECP-REG-*.json")
    }
    n = 1
    while f"ECP-REG-{n:06d}" in existing:
        n += 1
    return f"ECP-REG-{n:06d}"


def init_ledger(
    root: "str | Path",
    ledger_id: str,
    at: "str | None" = None,
    identity: "dict | None" = None,
) -> dict:
    """Initialize an empty ledger at *root* (explicitly defined clean state).

    The public ledger starts EMPTY (O5): zero entries, genesis anchor. The
    first real registration will be entry 1. Development ledgers are
    initialized the same way but live outside any published repository.
    """
    root = _resolve(root)
    if not LEDGER_ID_PATTERN.fullmatch(ledger_id or ""):
        raise LedgerError(f"invalid ledger_id {ledger_id!r}")
    if root.exists() and any(root.iterdir()):
        raise LedgerError(f"ledger root is not empty: {root}")

    from .identity import load_identity

    ident = identity or load_identity()
    at = at or _now_iso()

    (root / ENTRIES_DIR).mkdir(parents=True, exist_ok=True)
    (root / RECORDS_DIR).mkdir(parents=True, exist_ok=True)

    anchor = {
        "ledger_id": ledger_id,
        "entry_count": 0,
        "head_entry_hash": GENESIS_HASH,
        "genesis": True,
        "anchored_at": at,
        "protocol_version": ident["protocol_version"],
        "schema_version": ident["schema_version"],
        "notes": [
            "GENESIS - explicitly defined clean state: the public ledger "
            "starts empty; zero registrations exist."
        ],
    }
    _write_canonical(root / ANCHOR_FILE, anchor)

    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(
            "# ECP Registration Ledger\n\n"
            "Append-only, hash-chained public ledger of ECP registration "
            "records (see the ECP protocol repository and "
            "docs/M3-R1-ARCHITECTURE-DECISION.md).\n\n"
            "- `entries/NNNNNNNN.json` — chained ledger entries "
            "(ledger-entry schema)\n"
            "- `records/ECP-REG-*.json` — full registration records "
            "(canonical bytes)\n"
            "- `ANCHOR.json` — published checkpoint of the chain state; "
            "verify with `python tools/ecp_cli.py ledger-verify "
            "--ledger <this repo>` from the ECP repository.\n\n"
            "NEVER place protected ground truth (or any answer-bearing "
            "content) in this repository. Entries are append-only: no "
            "edits, no removals, no history rewrite, no force-push.\n",
            encoding="utf-8",
        )
    return anchor


def _live_registrations(root: Path) -> "dict[tuple, dict]":
    """Map frozen-tuple -> live registration record (not superseded,
    not invalidated). Raises on structural corruption."""
    entries = _entries(root)
    invalidated: "set[str]" = set()
    superseded: "set[str]" = set()
    records: "dict[str, dict]" = {}
    for entry in entries:
        if entry["entry_kind"] == "invalidation":
            invalidated.add(entry["record_ref"]["registration_id"])
    for entry in entries:
        if entry["entry_kind"] != "registration":
            continue
        reg_id = entry["record_ref"]["registration_id"]
        record_path = root / RECORDS_DIR / f"{reg_id}.json"
        record = _load_json(record_path)
        records[reg_id] = record
        if record.get("supersedes"):
            superseded.add(record["supersedes"])
    live = {}
    for reg_id, record in records.items():
        if reg_id in invalidated or reg_id in superseded:
            continue
        key = _tuple_key(record)
        if key in live:
            raise LedgerInvalid(
                f"duplicate live registration for tuple {key}: "
                f"{live[key]['registration_id']} and {reg_id}"
            )
        live[key] = record
    return live


def _tuple_key(record: dict) -> tuple:
    from .hashing import hash_document

    return (
        record["evaluation_id"],
        record["case"]["case_id"],
        record["case"]["case_version"],
        record["system"]["system_id"],
        record["system"]["system_version"],
        hash_document(record["condition"]),
    )


def register(
    ledger_root: "str | Path",
    registrar: str,
    case_document: dict,
    store_root: "str | Path",
    system_document: dict,
    evaluation_id: str,
    at: "str | None" = None,
    notes: "tuple[str, ...] | list[str]" = (),
    supersedes: "str | None" = None,
    identity: "dict | None" = None,
) -> dict:
    """Registration ceremony: freeze the tuple, bind the commitment, append.

    Rejections (RA-1..RA-5, L5, L6 of the decision record) happen BEFORE
    anything is written: the ledger is never appended-to with a rejected
    attempt.

    Args:
        ledger_root: the ledger directory.
        registrar: ``ECP-REGISTRAR-…`` identity performing the append.
        case_document: the PUBLIC case document (schema ``case``).
        store_root: the protected store root holding the sealed ground
            truth for this case (the registrar reads it as opaque bytes
            and compares commitments).
        system_document: the versioned system identity document (schema
            ``system``).
        evaluation_id: ``ECP-EVAL-…`` identifier of the owning evaluation.
        at: pinned UTC timestamp (default: now; a claim, not evidence).
        notes: optional notes recorded on the registration record.
        supersedes: optional prior ``registration_id`` this record
            explicitly replaces (append-only correction; never an edit).

    Returns:
        ``{registration_id, registration_hash, record_hash, entry_index,
        entry_hash, commitments, registration_record, ledger_entry}``.
    """
    root = _resolve(ledger_root)
    if not REGISTRAR_PATTERN.fullmatch(registrar or ""):
        raise LedgerError(f"invalid registrar {registrar!r}")
    if not EVALUATION_ID_PATTERN.fullmatch(evaluation_id or ""):
        raise LedgerError(f"invalid evaluation_id {evaluation_id!r}")
    if not (root / ANCHOR_FILE).is_file():
        raise LedgerInvalid(f"no ledger at {root} (missing ANCHOR.json)")

    from .identity import load_identity
    from .store import load_manifest as load_store_manifest

    ident = identity or load_identity()
    at = at or _now_iso()

    # --- case document: schema + versions + registrable state ---
    issues = validate_document(case_document, "case")
    if issues:
        raise RegistrationRejected(
            "case document does not validate: " + "; ".join(issues)
        )
    issues = version_issues(case_document)
    if issues:
        raise RegistrationRejected(
            "case document version incompatible: " + "; ".join(issues)
        )
    if case_document.get("case_status") not in REGISTRABLE_CASE_STATUSES:
        raise RegistrationRejected(
            f"case_status {case_document.get('case_status')!r} is not registrable"
        )
    reference = case_document.get("ground_truth_reference") or {}
    case_commitment = reference.get("commitment")
    if not isinstance(case_commitment, str) or not re.fullmatch(
        r"[0-9a-f]{64}", case_commitment
    ):
        raise RegistrationRejected("case carries no ground-truth commitment")
    if reference.get("sealing_status") != "sealed":
        raise RegistrationRejected(
            "case ground_truth_reference.sealing_status must be 'sealed' "
            "before registration"
        )

    # --- store seal: the custody half of the seam (RA-2) ---
    store_root = Path(store_root).resolve()
    try:
        store_manifest = load_store_manifest(store_root)
    except Exception as exc:  # StoreInvalid
        raise RegistrationRejected(f"protected store not verifiable: {exc}") from exc
    seal = None
    for candidate in store_manifest["seals"]:
        if (
            candidate["case_id"] == case_document["case_id"]
            and candidate["case_version"] == case_document["case_version"]
        ):
            seal = candidate
            break
    if seal is None:
        raise RegistrationRejected(
            "no sealed ground truth in the store for case "
            f"{case_document['case_id']}@{case_document['case_version']} "
            "(registration requires prior custody)"
        )
    if seal["commitment"] != case_commitment:
        raise RegistrationRejected(
            "commitment divergence: public case cites "
            f"{case_commitment}, store seal holds {seal['commitment']} "
            "(seam broken; nothing was appended)"
        )

    # --- system identity ---
    issues = validate_document(system_document, "system")
    if issues:
        raise RegistrationRejected(
            "system document does not validate: " + "; ".join(issues)
        )
    issues = version_issues(system_document)
    if issues:
        raise RegistrationRejected(
            "system document version incompatible: " + "; ".join(issues)
        )

    # --- duplicate control (L5) ---
    try:
        live = _live_registrations(root)
    except LedgerInvalid as exc:
        raise LedgerInvalid(f"ledger unreadable: {exc}") from exc
    candidate_record = {
        "evaluation_id": evaluation_id,
        "case": {
            "case_id": case_document["case_id"],
            "case_version": case_document["case_version"],
        },
        "system": {
            "system_id": system_document["system_id"],
            "system_version": system_document["system_version"],
        },
        "condition": case_document["condition"],
    }
    candidate_key = _tuple_key(candidate_record)
    for existing_key, existing in live.items():
        if existing_key == candidate_key and (
            supersedes is None or existing["registration_id"] != supersedes
        ):
            raise DuplicateRegistration(
                "a live registration already exists for this frozen tuple: "
                f"{existing['registration_id']} — supersede it explicitly "
                "(new record with supersedes) instead of duplicating"
            )

    # --- supersession target must exist ---
    if supersedes is not None:
        if not REGISTRATION_ID_PATTERN.fullmatch(supersedes):
            raise LedgerError(f"invalid supersedes id {supersedes!r}")
        target = root / RECORDS_DIR / f"{supersedes}.json"
        if not target.is_file():
            raise RegistrationRejected(
                f"supersedes target {supersedes} does not exist"
            )

    # --- build the registration record (frozen copy, RA-1) ---
    registration_id = _next_registration_id(root)
    record = {
        "ecp_object": "registration",
        "registration_id": registration_id,
        "protocol_version": ident["protocol_version"],
        "schema_version": ident["schema_version"],
        "evaluation_id": evaluation_id,
        "system": {
            "system_id": system_document["system_id"],
            "system_version": system_document["system_version"],
        },
        "case": {
            "case_id": case_document["case_id"],
            "case_version": case_document["case_version"],
        },
        "condition": json.loads(json.dumps(case_document["condition"])),
        "success_criterion": case_document["success_criterion"],
        "verification_rule": {
            "rule_id": case_document["verification_rule"]["rule_id"],
            "rule_type": case_document["verification_rule"]["rule_type"],
        },
        "registered_at": at,
        "hash_algorithm": "sha256",
        "canonicalization": "ECP-CANONICAL-JSON-1.0",
        "registration_hash": None,
        "immutability": "append-only",
    }
    if supersedes:
        record["supersedes"] = supersedes
    if notes:
        record["notes"] = list(notes)
    record["registration_hash"] = hash_document_excluding(record, "registration_hash")
    record_hash = hash_document(record)

    # --- append the ledger entry (chained) ---
    count, head = current_head(root)
    entry = {
        "ecp_object": "ledger-entry",
        "ledger_id": _load_json(root / ANCHOR_FILE)["ledger_id"],
        "entry_index": count + 1,
        "entry_kind": "registration",
        "registrar": registrar,
        "record_ref": {
            "registration_id": registration_id,
            "record_hash": record_hash,
        },
        "ground_truth_commitments": [
            {
                "case_id": case_document["case_id"],
                "case_version": case_document["case_version"],
                "commitment": case_commitment,
            }
        ],
        "protocol_version": ident["protocol_version"],
        "schema_version": ident["schema_version"],
        "claimed_at": at,
        "prev_entry_hash": head,
        "entry_hash": None,
    }
    entry["entry_hash"] = hash_document_excluding(entry, "entry_hash")

    issues = validate_document(entry, "ledger-entry") + version_issues(entry)
    if issues:
        raise LedgerError("constructed ledger entry invalid: " + "; ".join(issues))

    _write_canonical(root / RECORDS_DIR / f"{registration_id}.json", record)
    _write_canonical(_entry_path(root, entry["entry_index"]), entry)

    return {
        "registration_id": registration_id,
        "registration_hash": record["registration_hash"],
        "record_hash": record_hash,
        "entry_index": entry["entry_index"],
        "entry_hash": entry["entry_hash"],
        "commitments": entry["ground_truth_commitments"],
        "registration_record": record,
        "ledger_entry": entry,
    }


def invalidate(
    ledger_root: "str | Path",
    registrar: str,
    registration_id: str,
    reason: str,
    at: "str | None" = None,
    identity: "dict | None" = None,
) -> dict:
    """Append an explicit invalidation entry (append-only, never an edit).

    Post-execution amendments can only be invalidations — never silent
    tuple rewrites (decision record RA-5 / no-path rule 5).
    """
    root = _resolve(ledger_root)
    if not REGISTRAR_PATTERN.fullmatch(registrar or ""):
        raise LedgerError(f"invalid registrar {registrar!r}")
    if not REGISTRATION_ID_PATTERN.fullmatch(registration_id or ""):
        raise LedgerError(f"invalid registration_id {registration_id!r}")
    if not (root / ANCHOR_FILE).is_file():
        raise LedgerInvalid(f"no ledger at {root} (missing ANCHOR.json)")
    if not reason or not isinstance(reason, str):
        raise LedgerError("an explicit reason is required for invalidation")

    from .identity import load_identity

    ident = identity or load_identity()
    at = at or _now_iso()

    record_path = root / RECORDS_DIR / f"{registration_id}.json"
    if not record_path.is_file():
        raise RegistrationRejected(
            f"registration {registration_id} does not exist"
        )
    record = _load_json(record_path)
    record_hash = hash_document(record)

    entries = _entries(root)
    for entry in entries:
        if (
            entry["entry_kind"] == "invalidation"
            and entry["record_ref"]["registration_id"] == registration_id
        ):
            raise RegistrationRejected(
                f"registration {registration_id} is already invalidated "
                "(entry "
                f"{entry['entry_index']}); double invalidation is rejected"
            )

    count, head = current_head(root)
    entry = {
        "ecp_object": "ledger-entry",
        "ledger_id": _load_json(root / ANCHOR_FILE)["ledger_id"],
        "entry_index": count + 1,
        "entry_kind": "invalidation",
        "registrar": registrar,
        "record_ref": {
            "registration_id": registration_id,
            "record_hash": record_hash,
        },
        "protocol_version": ident["protocol_version"],
        "schema_version": ident["schema_version"],
        "claimed_at": at,
        "prev_entry_hash": head,
        "entry_hash": None,
        "notes": [f"invalidation reason: {reason}"],
    }
    entry["entry_hash"] = hash_document_excluding(entry, "entry_hash")

    issues = validate_document(entry, "ledger-entry") + version_issues(entry)
    if issues:
        raise LedgerError("constructed ledger entry invalid: " + "; ".join(issues))

    _write_canonical(_entry_path(root, entry["entry_index"]), entry)
    return {"entry_index": entry["entry_index"], "entry_hash": entry["entry_hash"],
            "registration_id": registration_id}


def anchor_publish(
    ledger_root: "str | Path",
    at: "str | None" = None,
    identity: "dict | None" = None,
) -> dict:
    """Publish the chain HEAD as the ledger ANCHOR (O2: per-registration).

    Verifies the chain first (a broken chain is never anchored), then
    atomically rewrites ``ANCHOR.json`` to the current head. Past anchor
    states are preserved by the ledger repository's Git history — one
    commit per anchor, never rewritten (see the ledger README). The git
    commit + push themselves are an operator ceremony, deliberately NOT
    performed by this tooling.
    """
    root = _resolve(ledger_root)
    at = at or _now_iso()

    from .identity import load_identity

    ident = identity or load_identity()

    report = ledger_verify(root)
    if not report["ok"]:
        raise LedgerInvalid(
            "chain does not verify; refusing to anchor: "
            + "; ".join(report["issues"][:5])
        )

    count, head = current_head(root)
    anchor = {
        "ledger_id": _load_json(root / ANCHOR_FILE)["ledger_id"],
        "entry_count": count,
        "head_entry_hash": head,
        "genesis": count == 0,
        "anchored_at": at,
        "protocol_version": ident["protocol_version"],
        "schema_version": ident["schema_version"],
    }
    if count == 0:
        anchor["notes"] = [
            "GENESIS - explicitly defined clean state: the public ledger "
            "starts empty; zero registrations exist."
        ]
    _write_canonical(root / ANCHOR_FILE, anchor)
    return anchor


def _verify_entry(entry: dict, index: int, prev_hash: str, issues: list) -> "tuple[bool, str]":
    """Validate one chain entry; append issues; return (ok, entry_hash).

    On a corrupt entry the returned hash falls back to the previous hash so
    the walk can continue and collect all findings instead of crashing.
    """
    ok = True
    if entry.get("entry_index") != index:
        issues.append(f"entries/{index:08d}.json: entry_index mismatch")
        ok = False
    if entry.get("prev_entry_hash") != prev_hash:
        issues.append(f"entries/{index:08d}.json: prev_entry_hash does not chain")
        ok = False
    recomputed = hash_document_excluding(entry, "entry_hash")
    if entry.get("entry_hash") != recomputed:
        issues.append(f"entries/{index:08d}.json: entry_hash does not recompute")
        ok = False
    schema_issues = validate_document(entry, "ledger-entry")
    version_compat = version_issues(entry)
    if schema_issues:
        issues.append(
            f"entries/{index:08d}.json: schema violations: " + "; ".join(schema_issues)
        )
        ok = False
    if version_compat:
        issues.append(
            f"entries/{index:08d}.json: " + "; ".join(version_compat)
        )
        ok = False
    return ok, entry.get("entry_hash", prev_hash)


def ledger_verify(
    ledger_root: "str | Path",
    cases_dir: "str | Path | None" = None,
) -> dict:
    """Public verification: recompute everything from public data only.

    Checks (findings, not exceptions):

    1. structure: ``entries/``, ``records/``, ``ANCHOR.json`` present;
    2. chain: contiguous indices, prev-linkage, per-entry self-hash and
       schema validity (protocol/schema version compatibility included);
    3. records: every registration entry's record exists, validates
       against the registration schema, its document hash equals
       ``record_ref.record_hash`` and its internal ``registration_hash``
       recomputes;
    4. commitments: every frozen commitment in
       ``ground_truth_commitments`` equals the public case's commitment
       (when *cases_dir* is supplied and a matching public case exists);
       a missing public case is reported (public verification requires the
       public case to be, well, public);
    5. duplicates: at most one LIVE registration per frozen tuple (live =
       neither superseded nor invalidated);
    6. supersession graph: supersede targets exist; no registration is
       superseded twice; invalidation targets exist; no double
       invalidation;
    7. anchor: ``ANCHOR.json``'s head matches the chain at its recorded
       entry_count; entries beyond the anchor are reported as an
       unanchored tail (informational, not a failure).

    Returns:
        ``{"ok": bool, "issues": [...], "entries": int,
        "live_registrations": int, "invalidated": [...],
        "superseded": [...], "anchor": {...} | None,
        "unanchored_tail": int}``.
    """
    root = _resolve(ledger_root)
    issues: "list[str]" = []
    ok = True

    if not (root / ANCHOR_FILE).is_file():
        return {
            "ok": False,
            "issues": [f"no ledger at {root} (missing ANCHOR.json)"],
            "entries": 0, "live_registrations": 0, "invalidated": [],
            "superseded": [], "anchor": None, "unanchored_tail": 0,
        }

    try:
        entries = _entries(root)
    except (LedgerInvalid, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "issues": [f"ledger unreadable: {exc}"],
            "entries": 0, "live_registrations": 0, "invalidated": [],
            "superseded": [], "anchor": None, "unanchored_tail": 0,
        }

    # 2 — chain
    prev = GENESIS_HASH
    seen_registrations: "dict[str, dict]" = {}
    invalidated: "list[str]" = []
    superseded_by: "dict[str, str]" = {}
    for index, entry in enumerate(entries, start=1):
        entry_ok, prev = _verify_entry(entry, index, prev, issues)
        ok = ok and entry_ok
        reg_id = entry.get("record_ref", {}).get("registration_id")
        if entry.get("entry_kind") == "registration":
            if reg_id in seen_registrations:
                issues.append(
                    f"entries/{index:08d}.json: duplicate registration_id {reg_id}"
                )
                ok = False
            else:
                seen_registrations[reg_id] = entry
        elif entry.get("entry_kind") == "invalidation":
            if reg_id in invalidated:
                issues.append(
                    f"entries/{index:08d}.json: double invalidation of {reg_id}"
                )
                ok = False
            invalidated.append(reg_id)

    # 3 — records
    records: "dict[str, dict]" = {}
    for reg_id, entry in seen_registrations.items():
        record_path = root / RECORDS_DIR / f"{reg_id}.json"
        if not record_path.is_file():
            issues.append(f"record {reg_id}: file missing")
            ok = False
            continue
        try:
            record = _load_json(record_path)
        except json.JSONDecodeError:
            issues.append(f"record {reg_id}: unparseable")
            ok = False
            continue
        records[reg_id] = record
        record_hash = (entry.get("record_ref") or {}).get("record_hash")
        if record_hash is None:
            issues.append(f"record {reg_id}: entry lacks record_hash")
            ok = False
        elif hash_document(record) != record_hash:
            issues.append(
                f"record {reg_id}: document hash != record_ref.record_hash"
            )
            ok = False
        schema_issues = validate_document(record, "registration")
        version_compat = version_issues(record)
        if schema_issues:
            issues.append(f"record {reg_id}: " + "; ".join(schema_issues))
            ok = False
        if version_compat:
            issues.append(f"record {reg_id}: " + "; ".join(version_compat))
            ok = False
        if record.get("registration_hash") != hash_document_excluding(
            record, "registration_hash"
        ):
            issues.append(f"record {reg_id}: registration_hash does not recompute")
            ok = False
        target = record.get("supersedes")
        if target:
            if target not in records and not (
                root / RECORDS_DIR / f"{target}.json"
            ).is_file():
                issues.append(f"record {reg_id}: supersedes target {target} missing")
                ok = False
            if target in superseded_by:
                issues.append(
                    f"record {reg_id}: supersedes target {target} already "
                    f"superseded by {superseded_by[target]}"
                )
                ok = False
            superseded_by[target] = reg_id

    for reg_id in invalidated:
        if reg_id not in records and not (
            root / RECORDS_DIR / f"{reg_id}.json"
        ).is_file():
            issues.append(f"invalidation target {reg_id} missing")
            ok = False

    # orphaned records: a record file no entry references (entry removal
    # leaves the record behind — detectable evidence)
    for path in sorted((root / RECORDS_DIR).glob("*.json")):
        if path.stem not in records and path.stem not in invalidated:
            issues.append(
                f"orphaned record (no entry references it): {path.stem}"
            )
            ok = False

    # 5 — duplicate live tuples
    live: "dict[tuple, str]" = {}
    for reg_id, record in records.items():
        if reg_id in invalidated or reg_id in superseded_by:
            continue
        key = _tuple_key(record)
        if key in live:
            issues.append(
                f"duplicate live registration for tuple {key}: "
                f"{live[key]} and {reg_id}"
            )
            ok = False
        else:
            live[key] = reg_id

    # 4 — public case commitments
    commitment_checks = 0
    if cases_dir is not None:
        cases_root = Path(cases_dir).resolve()
        public_cases: "dict[tuple[str, str], dict]" = {}
        if cases_root.is_dir():
            for path in cases_root.rglob("*.json"):
                if any(
                    part.startswith(".")
                    for part in path.relative_to(cases_root).parts
                ):
                    continue
                try:
                    document = _load_json(path)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if isinstance(document, dict) and document.get("ecp_object") == "case":
                    public_cases[
                        (document.get("case_id"), document.get("case_version"))
                    ] = document
        for reg_id, entry in seen_registrations.items():
            for frozen in entry.get("ground_truth_commitments", []):
                key = (frozen["case_id"], frozen["case_version"])
                case = public_cases.get(key)
                if case is None:
                    issues.append(
                        f"entry {entry['entry_index']}: public case "
                        f"{key[0]}@{key[1]} not found in cases_dir "
                        "(public verification requires the public case)"
                    )
                    ok = False
                    continue
                cited = (
                    case.get("ground_truth_reference", {}).get("commitment")
                )
                if cited != frozen["commitment"]:
                    issues.append(
                        f"entry {entry['entry_index']}: frozen commitment "
                        f"{frozen['commitment']} != public case commitment "
                        f"{cited}"
                    )
                    ok = False
                commitment_checks += 1

    # 7 — anchor
    anchor = None
    unanchored_tail = 0
    try:
        anchor = _load_json(root / ANCHOR_FILE)
        anchored_count = anchor.get("entry_count", 0)
        if not isinstance(anchored_count, int) or anchored_count < 0:
            issues.append("ANCHOR.json: invalid entry_count")
            ok = False
        elif anchored_count > len(entries):
            issues.append("ANCHOR.json: entry_count beyond chain length")
            ok = False
        else:
            if anchored_count == 0:
                expected_head = GENESIS_HASH
            else:
                expected_head = entries[anchored_count - 1]["entry_hash"]
            if anchor.get("head_entry_hash") != expected_head:
                issues.append(
                    "ANCHOR.json: head_entry_hash does not match the chain "
                    "at its recorded entry_count (stale or tampered anchor)"
                )
                ok = False
            unanchored_tail = len(entries) - anchored_count
    except (json.JSONDecodeError, UnicodeDecodeError):
        issues.append("ANCHOR.json: unparseable")
        ok = False

    return {
        "ok": ok,
        "issues": issues,
        "entries": len(entries),
        "live_registrations": len(live),
        "invalidated": sorted(invalidated),
        "superseded": sorted(superseded_by),
        "anchor": anchor,
        "unanchored_tail": unanchored_tail,
        "commitment_checks": commitment_checks,
    }
