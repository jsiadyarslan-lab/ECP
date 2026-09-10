"""Deterministic hashing tests (§14: what is hashed, in what representation)."""

import re
import subprocess
import sys

import pytest

from ecp.hashing import (
    hash_document,
    hash_document_excluding,
    hash_file,
    sha256_hex,
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def test_document_hash_hex_format():
    digest = hash_document({"a": 1})
    assert HEX64.match(digest)


def test_document_hash_deterministic():
    document = {"b": [2, 1], "a": "ü", "n": None}
    assert hash_document(document) == hash_document(document)


def test_document_hash_uses_canonical_form():
    # same content, different key order -> same hash
    first = {"a": 1, "b": 2}
    second = {"b": 2, "a": 1}
    assert hash_document(first) == hash_document(second)


def test_different_documents_differ():
    assert hash_document({"a": 1}) != hash_document({"a": 2})


def test_file_hash_deterministic(repo_root):
    path = repo_root / "examples" / "artifacts" / "raw-output.demo.txt"
    assert hash_file(path) == hash_file(path)


def test_file_hash_matches_sha256_of_bytes(repo_root):
    path = repo_root / "examples" / "artifacts" / "raw-output.demo.txt"
    assert hash_file(path) == sha256_hex(path.read_bytes())


def test_unsupported_algorithm_rejected():
    with pytest.raises(ValueError):
        hash_document({"a": 1}, algorithm="md5")


def test_unsupported_algorithm_rejected_for_files(tmp_path):
    target = tmp_path / "f.txt"
    target.write_text("data", encoding="utf-8")
    with pytest.raises(ValueError):
        hash_file(target, algorithm="sha1")


def test_sha256_hex_requires_bytes():
    with pytest.raises(TypeError):
        sha256_hex("not-bytes")


def test_excluding_removes_exactly_one_top_level_field():
    document = {
        "ecp_object": "x",
        "payload": {"manifest_hash": "inner-not-removed"},
        "manifest_hash": "outer",
    }
    stripped = {k: v for k, v in document.items() if k != "manifest_hash"}
    assert hash_document_excluding(document, "manifest_hash") == hash_document(stripped)


def test_excluding_is_insensitive_to_excluded_field_value():
    first = {"a": 1, "self_hash": "x"}
    second = {"a": 1, "self_hash": "y"}
    assert hash_document_excluding(first, "self_hash") == hash_document_excluding(
        second, "self_hash"
    )


def test_excluding_is_sensitive_to_other_fields():
    first = {"a": 1, "self_hash": "x"}
    second = {"a": 2, "self_hash": "x"}
    assert hash_document_excluding(first, "self_hash") != hash_document_excluding(
        second, "self_hash"
    )


def test_excluding_requires_dict():
    with pytest.raises(TypeError):
        hash_document_excluding(["not", "a", "dict"], "self_hash")


def test_cross_process_determinism(repo_root):
    # Determinism must hold across processes, not just within one.
    code = (
        "from ecp.hashing import hash_document; "
        "print(hash_document({'b':1,'a':'ü','c':[True,None]}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env={"PYTHONPATH": str(repo_root / "src"), "PATH": ""},
        check=True,
    )
    assert result.stdout.strip() == hash_document({"b": 1, "a": "ü", "c": [True, None]})
