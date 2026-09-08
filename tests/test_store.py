"""Protected store tests (R1-I §3/§11: CAS write-once, oplog chain,
manifest determinism, tamper detection).

All fixtures are synthetic and clearly marked; nothing here is scientific
data (the dev store pattern: scope 'development').
"""

import copy
import json

import pytest

from ecp import store
from ecp.hashing import hash_document

PINNED = "2026-09-09T00:00:00Z"


def _gt(case_id="ECP-CASE-SYNTH-0001", answer=6):
    """A synthetic sealed ground-truth document (dev fixture)."""
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
        "verification_rule": {
            "rule_id": "synth-0001-int",
            "rule_type": "exact-match",
        },
        "seal_note": "SYNTHETIC TEST FIXTURE - never scientific evidence",
        "protocol_version": "0.2.0",
        "schema_version": "0.2.0",
    }


@pytest.fixture()
def dev_store(tmp_path):
    store.init_store(
        tmp_path / "store",
        "ECP-STORE-TEST-0001",
        "development",
        at=PINNED,
    )
    return tmp_path / "store"


# --- init -----------------------------------------------------------------

def test_init_creates_structure_and_genesis_manifest(dev_store):
    manifest = store.load_manifest(dev_store)
    assert manifest["ecp_object"] == "store-manifest"
    assert manifest["scope"] == "development"
    assert manifest["seals"] == []
    assert manifest["oplog"]["entry_count"] == 1
    assert manifest["zones"]["sealed-gt"]["blob_count"] == 0
    assert (dev_store / "oplog" / "00000001.json").is_file()
    for zone in store.RESERVED_ZONES:
        assert (dev_store / zone / "README.md").is_file()


def test_init_rejects_nonempty_root(tmp_path):
    store.init_store(tmp_path / "s", "ECP-STORE-X-0001", "development")
    with pytest.raises(store.StoreError):
        store.init_store(tmp_path / "s", "ECP-STORE-X-0002", "development")


def test_init_rejects_invalid_ids(tmp_path):
    with pytest.raises(store.StoreError):
        store.init_store(tmp_path / "s", "not-a-store-id", "development")
    with pytest.raises(store.StoreError):
        store.init_store(tmp_path / "s", "ECP-STORE-X-0001", "sciencey")


# --- seal / write-once / idempotence --------------------------------------

def test_seal_creates_cas_blob_and_chains_oplog(dev_store):
    gt = _gt()
    result = store.seal(dev_store, gt, at="2026-09-09T00:00:01Z")
    commitment = hash_document(gt)
    assert result["commitment"] == commitment
    assert result["idempotent"] is False
    blob = dev_store / store.blob_path_for(commitment)
    assert blob.is_file()
    assert blob.read_bytes() == store.canonical_bytes(gt)  # canonical storage
    manifest = store.load_manifest(dev_store)
    assert manifest["seals"][0]["commitment"] == commitment
    assert manifest["oplog"]["entry_count"] == 2
    assert manifest["manifest_hash"] == store.hash_document_excluding(
        manifest, "manifest_hash"
    )


def test_seal_rejects_format_illustration_class(dev_store):
    gt = _gt()
    gt["content_class"] = "format-illustration"
    with pytest.raises(store.SealRejected):
        store.seal(dev_store, gt)


def test_seal_rejects_schema_invalid_document(dev_store):
    gt = _gt()
    del gt["derivation"]  # required field
    with pytest.raises(store.SealRejected):
        store.seal(dev_store, gt)


def test_seal_idempotent_for_identical_content(dev_store):
    gt = _gt()
    first = store.seal(dev_store, gt, at="2026-09-09T00:00:01Z")
    second = store.seal(dev_store, gt, at="2026-09-09T00:00:02Z")
    assert second["idempotent"] is True
    assert second["commitment"] == first["commitment"]
    manifest = store.load_manifest(dev_store)
    assert len(manifest["seals"]) == 1  # still exactly one seal
    assert manifest["oplog"]["entry_count"] == 3  # init, seal, idempotent


def test_seal_write_once_rejects_replacement(dev_store):
    """§12: unauthorized overwrite / modified committed object."""
    store.seal(dev_store, _gt(), at="2026-09-09T00:00:01Z")
    with pytest.raises(store.WriteOnceViolation):
        store.seal(dev_store, _gt(answer=999), at="2026-09-09T00:00:02Z")
    # the rejected attempt is op-logged (recorded, not hidden)
    oplog = sorted((dev_store / "oplog").glob("*.json"))
    kinds = [json.loads(p.read_text())["op"] for p in oplog]
    assert kinds == ["init", "seal", "rejected-seal"]
    # and the original content is untouched
    report = store.verify_store(dev_store)
    assert report["ok"], report["issues"]
    assert report["seal_count"] == 1


def test_seal_write_once_target_is_case_and_version(dev_store):
    """Different cases seal independently; same target does not."""
    store.seal(dev_store, _gt("ECP-CASE-SYNTH-0001"), at="2026-09-09T00:00:01Z")
    store.seal(dev_store, _gt("ECP-CASE-SYNTH-0002"), at="2026-09-09T00:00:02Z")
    with pytest.raises(store.WriteOnceViolation):
        store.seal(
            dev_store, _gt("ECP-CASE-SYNTH-0001", answer=42),
            at="2026-09-09T00:00:03Z",
        )
    assert store.verify_store(dev_store)["seal_count"] == 2


# --- determinism -----------------------------------------------------------

def test_manifest_is_deterministic_for_same_sequence(tmp_path):
    gt = _gt()

    def build(name):
        root = tmp_path / name
        store.init_store(root, "ECP-STORE-DET-0001", "development", at=PINNED)
        store.seal(root, gt, at="2026-09-09T00:00:01Z")
        store.seal(root, gt, at="2026-09-09T00:00:02Z")
        return (root / "store.json").read_bytes()

    assert build("a") == build("b")


# --- verification: tamper batteries ---------------------------------------

def test_verify_clean_store_passes(dev_store):
    store.seal(dev_store, _gt(), at="2026-09-09T00:00:01Z")
    report = store.verify_store(dev_store)
    assert report["ok"], report["issues"]
    assert report["seal_count"] == 1
    assert report["oplog_count"] == 2


def test_verify_detects_modified_committed_object(dev_store):
    """§12: modified committed object."""
    result = store.seal(dev_store, _gt(), at="2026-09-09T00:00:01Z")
    blob = dev_store / result["blob_path"]
    blob.write_bytes(store.canonical_bytes(_gt(answer=999)))
    report = store.verify_store(dev_store)
    assert not report["ok"]
    assert any("hash mismatch" in issue for issue in report["issues"])


def test_verify_detects_noncanonical_blob(dev_store):
    result = store.seal(dev_store, _gt(), at="2026-09-09T00:00:01Z")
    blob = dev_store / result["blob_path"]
    blob.write_text(json.dumps(_gt(), indent=4), encoding="utf-8")
    report = store.verify_store(dev_store)
    assert not report["ok"]
    assert any("hash mismatch" in issue for issue in report["issues"])


def test_verify_detects_modified_oplog_entry(dev_store):
    """§12: modified ledger/metadata equivalent — oplog chain tamper."""
    store.seal(dev_store, _gt(), at="2026-09-09T00:00:01Z")
    path = dev_store / "oplog" / "00000002.json"
    entry = json.loads(path.read_text())
    entry["claimed_at"] = "2030-01-01T00:00:00Z"
    path.write_text(json.dumps(entry), encoding="utf-8")
    report = store.verify_store(dev_store)
    assert not report["ok"]
    assert any("oplog_hash does not recompute" in issue for issue in report["issues"])


def test_verify_detects_removed_oplog_entry(dev_store):
    store.seal(dev_store, _gt(), at="2026-09-09T00:00:01Z")
    (dev_store / "oplog" / "00000002.json").unlink()
    report = store.verify_store(dev_store)
    assert not report["ok"]
    assert any("oplog" in issue for issue in report["issues"])


def test_verify_detects_modified_manifest(dev_store):
    """§12: altered metadata (manifest index tamper)."""
    store.seal(dev_store, _gt(), at="2026-09-09T00:00:01Z")
    manifest = json.loads((dev_store / "store.json").read_text())
    manifest["seals"][0]["commitment"] = "0" * 64
    (dev_store / "store.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = store.verify_store(dev_store)
    assert not report["ok"]  # manifest_hash fails AND seals rebuild mismatch


def test_verify_detects_missing_blob(dev_store):
    result = store.seal(dev_store, _gt(), at="2026-09-09T00:00:01Z")
    (dev_store / result["blob_path"]).unlink()
    report = store.verify_store(dev_store)
    assert not report["ok"]
    assert any("blob missing" in issue for issue in report["issues"])


def test_verify_detects_orphan_blob(dev_store):
    result = store.seal(dev_store, _gt(), at="2026-09-09T00:00:01Z")
    orphan = dev_store / store.blob_path_for("1" * 64)
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"{}")
    report = store.verify_store(dev_store)
    assert not report["ok"]
    assert any("orphan" in issue for issue in report["issues"])
    # the original seal is still fine
    assert (dev_store / result["blob_path"]).is_file()


def test_verify_detects_reserved_zone_violation(dev_store):
    (dev_store / "zones" / "evidence" / "bundle.json").write_text("{}")
    report = store.verify_store(dev_store)
    assert not report["ok"]
    assert any("evidence" in issue for issue in report["issues"])


def test_verify_detects_forged_seal_in_oplog(dev_store):
    """A seal entry whose details do not match its oplog_hash (invalid hash)."""
    store.seal(dev_store, _gt(), at="2026-09-09T00:00:01Z")
    path = dev_store / "oplog" / "00000002.json"
    entry = json.loads(path.read_text())
    entry["details"]["commitment"] = "2" * 64  # forge without re-hashing
    path.write_text(json.dumps(entry), encoding="utf-8")
    report = store.verify_store(dev_store)
    assert not report["ok"]
    assert any("oplog" in issue for issue in report["issues"])


# --- public case cross-check (the seam) ------------------------------------

def _public_case(gt, commitment):
    return {
        "ecp_object": "case",
        "case_id": gt["case_id"],
        "case_version": gt["case_version"],
        "case_status": "candidate",
        "case_family": "synthetic",
        "case_definition": {"statement": "SYNTHETIC - not scientific data"},
        "input": {"prompt": "SYNTHETIC - not scientific data"},
        "condition": {"constraints": ["synthetic"]},
        "success_criterion": "synthetic",
        "verification_rule": {"rule_id": "synth", "rule_type": "exact-match"},
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


def test_verify_cross_check_passes_on_matching_public_case(dev_store, tmp_path):
    gt = _gt()
    result = store.seal(dev_store, gt, at="2026-09-09T00:00:01Z")
    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "case.json").write_text(
        json.dumps(_public_case(gt, result["commitment"])), encoding="utf-8"
    )
    report = store.verify_store(dev_store, cases_dir=cases)
    assert report["ok"], report["issues"]


def test_verify_detects_broken_seam(dev_store, tmp_path):
    """§12: modified commitment (public case no longer matches the seal)."""
    gt = _gt()
    result = store.seal(dev_store, gt, at="2026-09-09T00:00:01Z")
    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "case.json").write_text(
        json.dumps(_public_case(gt, "0" * 64)), encoding="utf-8"
    )
    report = store.verify_store(dev_store, cases_dir=cases)
    assert not report["ok"]
    assert any("seam broken" in issue for issue in report["issues"])


def test_verify_treats_hidden_case_as_legitimate(dev_store, tmp_path):
    """A seal with no public case document is fine (hidden cases)."""
    store.seal(dev_store, _gt(), at="2026-09-09T00:00:01Z")
    empty = tmp_path / "cases"
    empty.mkdir()
    report = store.verify_store(dev_store, cases_dir=empty)
    assert report["ok"], report["issues"]
