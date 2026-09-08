"""Canonical serialization tests (§14 deterministic canonical representation)."""

import json

import pytest

from ecp.canonical import (
    CANONICALIZATION_ID,
    canonical_bytes,
    canonical_bytes_from_file,
    canonical_dumps,
    load_json,
)


def test_canonicalization_id_is_pinned():
    assert CANONICALIZATION_ID == "ECP-CANONICAL-JSON-1.0"


def test_no_insignificant_whitespace():
    assert canonical_dumps({"a": 1, "b": [1, 2]}) == '{"a":1,"b":[1,2]}'


def test_keys_sorted_recursively():
    document = {"z": 1, "a": {"y": [3, {"b": 1, "a": 2}], "x": 2}, "m": 3}
    text = canonical_dumps(document)
    assert text == '{"a":{"x":2,"y":[3,{"a":2,"b":1}]},"m":3,"z":1}'


def test_key_order_independence():
    first = {"a": 1, "b": {"x": 2, "y": 3}}
    second = {"b": {"y": 3, "x": 2}, "a": 1}
    assert canonical_bytes(first) == canonical_bytes(second)


def test_unicode_preserved_not_ascii_escaped():
    text = canonical_dumps({"key": "αβ ≥ 3 — 文"})
    assert "αβ ≥ 3 — 文" in text
    assert "\\u" not in text


def test_nan_forbidden():
    with pytest.raises(ValueError):
        canonical_dumps({"bad": float("nan")})


def test_infinity_forbidden():
    with pytest.raises(ValueError):
        canonical_dumps({"bad": float("inf")})


def test_rejects_raw_string_input():
    with pytest.raises(TypeError):
        canonical_dumps('{"already":"serialized"}')


def test_rejects_raw_bytes_input():
    with pytest.raises(TypeError):
        canonical_dumps(b'{"already":"serialized"}')


def test_roundtrip_preserves_value():
    document = {"s": "ü", "i": 17, "f": 2.5, "b": True, "n": None, "l": [1, {"k": "v"}]}
    assert json.loads(canonical_dumps(document)) == document


def test_deterministic_across_repeated_calls():
    document = {"z": [1, 2, {"q": None}], "a": "ünïcode", "m": {"β": True}}
    first = canonical_bytes(document)
    for _ in range(5):
        assert canonical_bytes(document) == first


def test_integer_rendering_is_minimal_decimal():
    assert canonical_dumps({"n": 7}) == '{"n":7}'


def test_canonical_bytes_from_file(repo_root):
    path = repo_root / "examples" / "ground-truth.format-example.json"
    with open(path, encoding="utf-8") as fh:
        document = json.load(fh)
    assert canonical_bytes_from_file(path) == canonical_bytes(document)


def test_load_json_returns_parsed_value(repo_root):
    document = load_json(repo_root / "ECP-IDENTITY.json")
    assert document["protocol_name"] == "ECP"
