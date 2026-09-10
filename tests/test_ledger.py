"""Registration ledger tests (R1-I §4/§11/§12: append, chain, freeze,
commitment linkage, duplicates, amendment semantics, anchor, tamper).

All fixtures are synthetic; the dev-ledger pattern (never published, never
scientific evidence) is what these tests exercise.
"""

import copy
import json

import pytest

from ecp import ledger, store

PINNED = "2026-09-09T00:00:00Z"


def _gt(case_id="ECP-CASE-SYNTH-0001", answer=6):
    return {
        "ecp_object": "ground-truth",
        "content_class": "sealed",
        "case_id": case_id,
        "case_version": "0.1.0",
        "expected_answer": {"answer_kind": "single-value", "value": answer},
        "derivation": [
            {"step": 1, "statement": "SYNTHETIC FIXTURE - not scientific data"},
            {"step": 2, "statement": "double the input value"},
        ],
        "verification_rule": {"rule_id": "synth-0001-int", "rule_type": "exact-match"},
        "seal_note": "SYNTHETIC TEST FIXTURE - never scientific evidence",
        "protocol_version": "0.2.0",
        "schema_version": "0.2.0",
    }


def _public_case(gt, commitment):
    return {
        "ecp_object": "case",
        "case_id": gt["case_id"],
        "case_version": gt["case_version"],
        "case_status": "candidate",
        "case_family": "synthetic",
        "case_definition": {"statement": "SYNTHETIC - not scientific data"},
        "input": {"prompt": "SYNTHETIC - not scientific data"},
        "condition": {"constraints": ["synthetic constraint"], "permitted_resources": []},
        "success_criterion": "synthetic success criterion (frozen copy)",
        "verification_rule": {
            "rule_id": "synth-0001-int",
            "rule_type": "exact-match",
            "description": "public description of the synthetic rule",
        },
        "ground_truth_reference": {
            "commitment": commitment,
            "hash_algorithm": "sha256",
            "canonicalization": "ECP-CANONICAL-JSON-1.0",
            "committed_object": "ground-truth",
            "sealing_status": "sealed",
        },
        "authoring_provenance": {
            "authored_at": "2026-09-09T00:00:00Z",
            "author_role": "internal-author",
            "information_boundary": "isolated",
        },
        "protocol_version": "0.2.0",
        "schema_version": "0.2.0",
    }


_SYSTEM = {
    "ecp_object": "system",
    "identity_mode": "model-only",
    "system_id": "ECP-SYSTEM-SYNTH-0001",
    "system_version": "0.1.0",
    "model": {
        "name": "synthetic-model",
        "provider": "synthetic",
        "model_version": "1.0.0",
        "api_version": "1",
    },
    "protocol_version": "0.2.0",
    "schema_version": "0.2.0",
    "case_set_version": "0.1.0",
    "description": "SYNTHETIC TEST FIXTURE - never scientific data",
}


@pytest.fixture()
def seam(tmp_path):
    """A dev store with one sealed GT + a matching public case + a ledger."""
    store_root = tmp_path / "store"
    ledger_root = tmp_path / "ledger"
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    store.init_store(
        store_root, "ECP-STORE-DEV-0001", "development", at=PINNED
    )
    ledger.init_ledger(ledger_root, "ECP-LEDGER-DEV-0001", at=PINNED)
    gt = _gt()
    seal_info = store.seal(store_root, gt, at="2026-09-09T00:00:01Z")
    case = _public_case(gt, seal_info["commitment"])
    (cases_dir / "case.json").write_text(json.dumps(case), encoding="utf-8")
    return {
        "store": store_root,
        "ledger": ledger_root,
        "cases": cases_dir,
        "gt": gt,
        "case": case,
        "commitment": seal_info["commitment"],
    }


# --- init -----------------------------------------------------------------

def test_init_creates_clean_genesis_state(tmp_path):
    anchor = ledger.init_ledger(tmp_path / "l", "ECP-LEDGER-T-0001", at=PINNED)
    assert anchor["entry_count"] == 0
    assert anchor["head_entry_hash"] == ledger.GENESIS_HASH
    assert anchor["genesis"] is True
    assert (tmp_path / "l" / "entries").is_dir()
    assert (tmp_path / "l" / "records").is_dir()
    report = ledger.ledger_verify(tmp_path / "l")
    assert report["ok"], report["issues"]
    assert report["entries"] == 0


def test_init_rejects_invalid_or_nonempty(tmp_path):
    with pytest.raises(ledger.LedgerError):
        ledger.init_ledger(tmp_path / "l", "bad id", at=PINNED)
    ledger.init_ledger(tmp_path / "l2", "ECP-LEDGER-T-0002", at=PINNED)
    with pytest.raises(ledger.LedgerError):
        ledger.init_ledger(tmp_path / "l2", "ECP-LEDGER-T-0003", at=PINNED)


# --- register: freeze + append --------------------------------------------

def test_register_appends_chained_entry_and_record(seam):
    result = ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
        notes=["DEV - synthetic fixture"],
    )
    assert result["registration_id"] == "ECP-REG-000001"
    entry = json.loads(
        (seam["ledger"] / "entries" / "00000001.json").read_text()
    )
    assert entry["entry_index"] == 1
    assert entry["prev_entry_hash"] == ledger.GENESIS_HASH
    assert entry["entry_kind"] == "registration"
    assert entry["registrar"] == "ECP-REGISTRAR-DEV-0001"
    assert entry["ground_truth_commitments"][0]["commitment"] == seam["commitment"]

    record = json.loads(
        (seam["ledger"] / "records" / "ECP-REG-000001.json").read_text()
    )
    # frozen fields are COPIES from the case at registration time
    assert record["condition"] == seam["case"]["condition"]
    assert record["success_criterion"] == seam["case"]["success_criterion"]
    assert record["verification_rule"] == {
        "rule_id": "synth-0001-int",
        "rule_type": "exact-match",
    }
    assert record["immutability"] == "append-only"

    report = ledger.ledger_verify(seam["ledger"], cases_dir=seam["cases"])
    assert report["ok"], report["issues"]
    assert report["live_registrations"] == 1
    assert report["commitment_checks"] == 1


def test_register_rejects_commitment_divergence(seam):
    """RA-2: the seam check — case commitment must equal the store seal."""
    tampered_case = copy.deepcopy(seam["case"])
    tampered_case["ground_truth_reference"]["commitment"] = "0" * 64
    with pytest.raises(ledger.RegistrationRejected):
        ledger.register(
            seam["ledger"], "ECP-REGISTRAR-DEV-0001", tampered_case,
            seam["store"], _SYSTEM, "ECP-EVAL-DEV-0001",
        )
    # nothing was appended
    assert ledger.ledger_verify(seam["ledger"])["entries"] == 0


def test_register_rejects_unsealed_case(seam):
    case = copy.deepcopy(seam["case"])
    case["ground_truth_reference"]["sealing_status"] = "pending"
    with pytest.raises(ledger.RegistrationRejected):
        ledger.register(
            seam["ledger"], "ECP-REGISTRAR-DEV-0001", case,
            seam["store"], _SYSTEM, "ECP-EVAL-DEV-0001",
        )


def test_register_requires_store_custody(tmp_path, seam):
    empty_store = tmp_path / "empty-store"
    store.init_store(empty_store, "ECP-STORE-EMPTY-0001", "development", at=PINNED)
    with pytest.raises(ledger.RegistrationRejected):
        ledger.register(
            seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"],
            empty_store, _SYSTEM, "ECP-EVAL-DEV-0001",
        )


def test_register_rejects_invalid_documents(seam):
    bad_case = copy.deepcopy(seam["case"])
    del bad_case["input"]  # schema violation
    with pytest.raises(ledger.RegistrationRejected):
        ledger.register(
            seam["ledger"], "ECP-REGISTRAR-DEV-0001", bad_case,
            seam["store"], _SYSTEM, "ECP-EVAL-DEV-0001",
        )
    bad_system = copy.deepcopy(_SYSTEM)
    del bad_system["model"]
    with pytest.raises(ledger.RegistrationRejected):
        ledger.register(
            seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"],
            seam["store"], bad_system, "ECP-EVAL-DEV-0001",
        )
    with pytest.raises(ledger.LedgerError):
        ledger.register(
            seam["ledger"], "bad-registrar", seam["case"],
            seam["store"], _SYSTEM, "ECP-EVAL-DEV-0001",
        )


# --- duplicate registration (L5) -------------------------------------------

def test_duplicate_registration_rejected(seam):
    """§12: duplicate registration."""
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    with pytest.raises(ledger.DuplicateRegistration):
        ledger.register(
            seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"],
            seam["store"], _SYSTEM, "ECP-EVAL-DEV-0001",
            at="2026-09-09T00:00:03Z",
        )
    assert ledger.ledger_verify(seam["ledger"])["entries"] == 1


def test_different_system_is_not_a_duplicate(seam):
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    other_system = copy.deepcopy(_SYSTEM)
    other_system["system_id"] = "ECP-SYSTEM-SYNTH-0002"
    result = ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        other_system, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:03Z",
    )
    assert result["registration_id"] == "ECP-REG-000002"
    report = ledger.ledger_verify(seam["ledger"])
    assert report["live_registrations"] == 2


# --- amendment semantics (RA-5/RA-6) ---------------------------------------

def test_supersession_is_append_only(seam):
    first = ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    second = ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:04Z",
        supersedes=first["registration_id"],
        notes=["explicit supersession demo"],
    )
    # both records exist; the old one is untouched
    old = json.loads(
        (seam["ledger"] / "records" / "ECP-REG-000001.json").read_text()
    )
    assert old == first["registration_record"]
    assert second["registration_record"]["supersedes"] == "ECP-REG-000001"
    report = ledger.ledger_verify(seam["ledger"])
    assert report["ok"], report["issues"]
    assert report["live_registrations"] == 1  # only the superseding one
    assert report["superseded"] == ["ECP-REG-000001"]


def test_supersession_target_must_exist(seam):
    with pytest.raises(ledger.RegistrationRejected):
        ledger.register(
            seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"],
            seam["store"], _SYSTEM, "ECP-EVAL-DEV-0001",
            supersedes="ECP-REG-999999",
        )


def test_invalidation_is_explicit_and_once(seam):
    first = ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    inv = ledger.invalidate(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", first["registration_id"],
        "dev demonstration", at="2026-09-09T00:00:03Z",
    )
    assert inv["entry_index"] == 2
    with pytest.raises(ledger.RegistrationRejected):
        ledger.invalidate(
            seam["ledger"], "ECP-REGISTRAR-DEV-0001",
            first["registration_id"], "again",
        )
    report = ledger.ledger_verify(seam["ledger"])
    assert report["ok"]
    assert report["invalidated"] == ["ECP-REG-000001"]
    assert report["live_registrations"] == 0


def test_invalidation_requires_reason_and_existing_target(seam):
    with pytest.raises(ledger.LedgerError):
        ledger.invalidate(
            seam["ledger"], "ECP-REGISTRAR-DEV-0001", "ECP-REG-000001", ""
        )
    with pytest.raises(ledger.RegistrationRejected):
        ledger.invalidate(
            seam["ledger"], "ECP-REGISTRAR-DEV-0001", "ECP-REG-000001", "reason"
        )


# --- anchor (O2) ------------------------------------------------------------

def test_anchor_publish_and_unanchored_tail(seam):
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    anchor = ledger.anchor_publish(seam["ledger"], at="2026-09-09T00:00:03Z")
    assert anchor["entry_count"] == 1
    report = ledger.ledger_verify(seam["ledger"])
    assert report["ok"]
    assert report["unanchored_tail"] == 0
    # append beyond the anchor: informational tail, not a failure
    ledger.invalidate(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", "ECP-REG-000001",
        "tail demo", at="2026-09-09T00:00:04Z",
    )
    report = ledger.ledger_verify(seam["ledger"])
    assert report["ok"]
    assert report["unanchored_tail"] == 1


def test_anchor_publish_refuses_broken_chain(seam):
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    path = seam["ledger"] / "entries" / "00000001.json"
    entry = json.loads(path.read_text())
    entry["claimed_at"] = "2030-01-01T00:00:00Z"
    path.write_text(json.dumps(entry), encoding="utf-8")
    with pytest.raises(ledger.LedgerInvalid):
        ledger.anchor_publish(seam["ledger"])


# --- verification: tamper batteries -----------------------------------------

def test_verify_detects_modified_ledger_entry(seam):
    """§12: modified ledger entry."""
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    path = seam["ledger"] / "entries" / "00000001.json"
    entry = json.loads(path.read_text())
    entry["claimed_at"] = "2000-01-01T00:00:00Z"  # backdate!
    path.write_text(json.dumps(entry), encoding="utf-8")
    report = ledger.ledger_verify(seam["ledger"])
    assert not report["ok"]
    assert any("entry_hash does not recompute" in i for i in report["issues"])


def test_verify_detects_removed_entry(seam):
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    (seam["ledger"] / "entries" / "00000001.json").unlink()
    report = ledger.ledger_verify(seam["ledger"])
    assert not report["ok"]


def test_verify_detects_modified_registration_record(seam):
    """§12: modified committed object (record tamper)."""
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    path = seam["ledger"] / "records" / "ECP-REG-000001.json"
    record = json.loads(path.read_text())
    record["success_criterion"] = "an easier criterion"
    path.write_text(json.dumps(record), encoding="utf-8")
    report = ledger.ledger_verify(seam["ledger"])
    assert not report["ok"]
    assert any("registration_hash" in i or "record_hash" in i for i in report["issues"])


def test_verify_detects_missing_record(seam):
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    (seam["ledger"] / "records" / "ECP-REG-000001.json").unlink()
    report = ledger.ledger_verify(seam["ledger"])
    assert not report["ok"]
    assert any("missing" in i for i in report["issues"])


def test_verify_detects_stale_anchor(seam):
    """§12: altered metadata (anchor tamper)."""
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    ledger.anchor_publish(seam["ledger"], at="2026-09-09T00:00:03Z")
    path = seam["ledger"] / "ANCHOR.json"
    anchor = json.loads(path.read_text())
    anchor["head_entry_hash"] = "3" * 64
    path.write_text(json.dumps(anchor), encoding="utf-8")
    report = ledger.ledger_verify(seam["ledger"])
    assert not report["ok"]
    assert any("ANCHOR" in i for i in report["issues"])


def test_verify_detects_broken_provenance(seam):
    """§12: broken provenance (incompatible cited versions)."""
    result = ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    entry = copy.deepcopy(result["ledger_entry"])
    entry["protocol_version"] = "9.9.9"  # future/unknown protocol
    # recompute the self-hash so ONLY the provenance is broken
    from ecp.hashing import hash_document_excluding
    entry.pop("entry_hash")
    entry["entry_hash"] = hash_document_excluding(entry, "entry_hash")
    (seam["ledger"] / "entries" / "00000001.json").write_text(
        json.dumps(entry), encoding="utf-8"
    )
    report = ledger.ledger_verify(seam["ledger"])
    assert not report["ok"]
    assert any("protocol_version" in i for i in report["issues"])


def test_verify_detects_broken_linkage_missing_public_case(seam):
    """§12: broken linkage detection (commitment cross-check)."""
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    (seam["cases"] / "case.json").unlink()
    report = ledger.ledger_verify(seam["ledger"], cases_dir=seam["cases"])
    assert not report["ok"]
    assert any("not found in cases_dir" in i for i in report["issues"])


def test_verify_detects_commitment_mismatch_vs_public_case(seam):
    """§12: modified commitment (public case swapped after registration)."""
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    swapped = copy.deepcopy(seam["case"])
    swapped["ground_truth_reference"]["commitment"] = "4" * 64
    (seam["cases"] / "case.json").write_text(json.dumps(swapped), encoding="utf-8")
    report = ledger.ledger_verify(seam["ledger"], cases_dir=seam["cases"])
    assert not report["ok"]
    assert any("frozen commitment" in i for i in report["issues"])


def test_verify_detects_invalid_schema_entry(seam):
    """§12: invalid schema (entry missing required fields)."""
    ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    path = seam["ledger"] / "entries" / "00000001.json"
    entry = json.loads(path.read_text())
    del entry["registrar"]  # required field removed
    path.write_text(json.dumps(entry), encoding="utf-8")
    report = ledger.ledger_verify(seam["ledger"])
    assert not report["ok"]
    assert any("schema violations" in i for i in report["issues"])


def test_verify_detects_duplicate_reg_id_in_chain(seam):
    """§12: replay of a registration id as a second entry."""
    first = ledger.register(
        seam["ledger"], "ECP-REGISTRAR-DEV-0001", seam["case"], seam["store"],
        _SYSTEM, "ECP-EVAL-DEV-0001", at="2026-09-09T00:00:02Z",
    )
    entry = copy.deepcopy(first["ledger_entry"])
    entry["entry_index"] = 2
    entry["prev_entry_hash"] = entry["entry_hash"]
    from ecp.hashing import hash_document_excluding
    entry.pop("entry_hash")
    entry["entry_hash"] = hash_document_excluding(entry, "entry_hash")
    (seam["ledger"] / "entries" / "00000002.json").write_text(
        json.dumps(entry), encoding="utf-8"
    )
    report = ledger.ledger_verify(seam["ledger"])
    assert not report["ok"]
    assert any("duplicate registration_id" in i for i in report["issues"])


def test_verify_on_nonexistent_ledger(tmp_path):
    report = ledger.ledger_verify(tmp_path / "nope")
    assert not report["ok"]


# --- determinism ------------------------------------------------------------

def test_register_is_deterministic_for_pinned_time(tmp_path):
    outputs = []
    for name in ("a", "b"):
        root = tmp_path / name
        store_root = root / "store"
        ledger_root = root / "ledger"
        cases_dir = root / "cases"
        cases_dir.mkdir(parents=True)
        store.init_store(store_root, "ECP-STORE-DET-0001", "development", at=PINNED)
        ledger.init_ledger(ledger_root, "ECP-LEDGER-DET-0001", at=PINNED)
        gt = _gt()
        seal_info = store.seal(store_root, gt, at="2026-09-09T00:00:01Z")
        case = _public_case(gt, seal_info["commitment"])
        result = ledger.register(
            ledger_root, "ECP-REGISTRAR-DET-0001", case, store_root,
            _SYSTEM, "ECP-EVAL-DET-0001", at="2026-09-09T00:00:02Z",
        )
        outputs.append(
            (
                result["registration_hash"],
                (ledger_root / "records" / "ECP-REG-000001.json").read_bytes(),
                (ledger_root / "entries" / "00000001.json").read_bytes(),
            )
        )
    assert outputs[0] == outputs[1]
