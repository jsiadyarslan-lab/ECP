"""Shared fixtures and mutation helpers for the ECP foundation tests."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ecp import identity as identity_module  # noqa: E402


@pytest.fixture(autouse=True)
def _platform_neutral_text_writes(monkeypatch):
    """Keep test-generated text files byte-identical on Windows and POSIX.

    Provenance tests intentionally hash the exact UTF-8 source bytes. Python's
    default text writer translates LF to CRLF on Windows, which makes a hash
    computed from ``text.encode()`` differ from the file actually written.
    Test fixtures therefore disable newline translation for pathlib text
    writes; production code continues to verify raw file bytes unchanged.
    """
    original = Path.write_text

    def write_text(path, data, encoding=None, errors=None, newline=""):
        return original(path, data, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "write_text", write_text)
    yield


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def ident() -> dict:
    return identity_module.load_identity()


@pytest.fixture(scope="session")
def examples() -> dict:
    """All example documents, loaded once (filename -> document)."""
    import json

    docs = {}
    for path in sorted((REPO_ROOT / "examples").glob("*.json")):
        with open(path, "r", encoding="utf-8") as fh:
            docs[path.name] = json.load(fh)
    return docs
