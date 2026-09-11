"""Protocol identity tests (§6 versioned protocol identity)."""

import json
import tomllib

import pytest

from ecp import identity as identity_module
from ecp.canonical import CANONICALIZATION_ID
from ecp.hashing import SUPPORTED_ALGORITHMS
from ecp.validate import validate_document

import ecp


def test_identity_file_exists(repo_root):
    assert (repo_root / "ECP-IDENTITY.json").is_file()


def test_identity_validates_against_protocol_schema():
    document = identity_module.load_identity()
    assert validate_document(document, "protocol") == []


def test_identity_core_fields(repo_root):
    with open(repo_root / "ECP-IDENTITY.json", encoding="utf-8") as fh:
        document = json.load(fh)
    assert document["protocol_name"] == "ECP"
    # Protocol/repository identity remains 0.7.0; the approved 0.8.0
    # operational schema bundle is a distinct additive metadata contract.
    assert document["protocol_version"] == "0.7.0"
    assert document["schema_version"] == "0.8.0"
    assert document["repository_version"] == "0.7.0"
    assert document["protocol_status"] == "draft"


def test_identity_matches_module_constants():
    document = identity_module.load_identity()
    assert document["canonicalization"] == CANONICALIZATION_ID
    assert document["hash_algorithm"] in SUPPORTED_ALGORITHMS
    assert ecp.__version__ == document["repository_version"]


def test_package_metadata_and_schema_bundle_relationship(repo_root):
    with open(repo_root / "pyproject.toml", "rb") as fh:
        project = tomllib.load(fh)["project"]
    identity = identity_module.load_identity()
    assert project["version"] == identity["repository_version"] == "0.7.0"
    assert identity["schema_version"] == "0.8.0"
    assert identity["protocol_version"] == "0.7.0"


def test_schema_bundle_version_does_not_expand_protocol_versions():
    from ecp.versions import PROTOCOL_VERSIONS, allowed_schema_versions

    assert allowed_schema_versions("provider") == ("0.8.0",)
    assert allowed_schema_versions("target") == ("0.8.0",)
    assert allowed_schema_versions("adapter") == ("0.8.0",)
    assert "0.8.0" not in PROTOCOL_VERSIONS


def test_get_identity_equals_load_identity():
    assert identity_module.get_identity() == identity_module.load_identity()


def test_load_identity_rejects_invalid_identity(tmp_path):
    bad = {
        "ecp_object": "protocol",
        "protocol_name": "SOMEONE-ELSE",
        "protocol_version": "0.1.0",
        "schema_version": "0.1.0",
        "repository_version": "0.1.0",
        "protocol_status": "draft",
    }
    (tmp_path / "ECP-IDENTITY.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        identity_module.load_identity(repo_root=tmp_path)


def test_load_identity_requires_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        identity_module.load_identity(repo_root=tmp_path)


def test_identity_rejects_nonsemver_version():
    document = identity_module.load_identity()
    broken = dict(document, protocol_version="1")
    assert validate_document(broken, "protocol") != []


def test_identity_rejects_unknown_status():
    document = identity_module.load_identity()
    broken = dict(document, protocol_status="golden")
    assert validate_document(broken, "protocol") != []


def test_identity_rejects_wrong_object_type():
    document = identity_module.load_identity()
    broken = dict(document, ecp_object="proto")
    assert validate_document(broken, "protocol") != []
