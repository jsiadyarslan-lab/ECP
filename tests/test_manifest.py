"""Manifest generation tests (§14 deterministic manifests)."""

import copy

import pytest

from ecp.hashing import hash_document_excluding
from ecp.manifest import build_manifest, compute_manifest_hash
from ecp.validate import validate_document

ITEMS = [
    {"role": "b", "path": "b/z.txt", "hash": "a" * 64},
    {"role": "a", "path": "a/m.txt", "hash": "b" * 64},
    {"role": "c", "path": "b/a.txt", "hash": "c" * 64},
]


def _build(generated_at="2026-09-09T00:00:00Z"):
    return build_manifest(
        copy.deepcopy(ITEMS),
        manifest_type="artifact-set",
        protocol_version="0.1.0",
        schema_version="0.1.0",
        generated_at=generated_at,
    )


def test_entries_sorted_by_path():
    manifest = _build()
    paths = [entry["path"] for entry in manifest["entries"]]
    assert paths == sorted(paths)
    assert paths == ["a/m.txt", "b/a.txt", "b/z.txt"]


def test_built_manifest_is_schema_valid():
    assert validate_document(_build(), "manifest") == []


def test_manifest_hash_recomputes():
    manifest = _build()
    assert manifest["manifest_hash"] == compute_manifest_hash(manifest)
    recomputed = hash_document_excluding(manifest, "manifest_hash")
    assert manifest["manifest_hash"] == recomputed


def test_manifest_hash_covers_every_field_but_itself():
    manifest = _build()
    role_changed = copy.deepcopy(manifest)
    for entry in role_changed["entries"]:
        entry["role"] = entry["role"] + "-changed"
    assert compute_manifest_hash(role_changed) != manifest["manifest_hash"]


def test_deterministic_for_fixed_inputs():
    assert _build() == _build()


def test_timestamp_participates_in_hash():
    first = _build(generated_at="2026-09-09T00:00:00Z")
    second = _build(generated_at="2026-09-09T00:00:01Z")
    assert first["entries"] == second["entries"]
    assert first["manifest_hash"] != second["manifest_hash"]


def test_duplicate_paths_rejected():
    items = [
        {"role": "a", "path": "same.txt", "hash": "a" * 64},
        {"role": "b", "path": "same.txt", "hash": "b" * 64},
    ]
    with pytest.raises(ValueError):
        build_manifest(
            items,
            manifest_type="artifact-set",
            protocol_version="0.1.0",
            schema_version="0.1.0",
            generated_at="2026-09-09T00:00:00Z",
        )


def test_input_order_irrelevant():
    reversed_items = list(reversed(copy.deepcopy(ITEMS)))
    other = build_manifest(
        reversed_items,
        manifest_type="artifact-set",
        protocol_version="0.1.0",
        schema_version="0.1.0",
        generated_at="2026-09-09T00:00:00Z",
    )
    assert other == _build()


def test_entry_fields_complete():
    manifest = _build()
    for entry in manifest["entries"]:
        assert set(entry) == {"role", "path", "algorithm", "hash"}
        assert entry["algorithm"] == "sha256"
