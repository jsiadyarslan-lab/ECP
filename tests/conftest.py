"""Shared fixtures and mutation helpers for the ECP foundation tests."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ecp import identity as identity_module  # noqa: E402


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
