"""Shared fixtures for the M3-RG0 trust-layer tests (development scope).

Everything here is SYNTHETIC DEVELOPMENT material (format-illustration):
development-scope trust stores, synthetic owner gate orders, synthetic
registration packages built around the public example case. No
operational material is created anywhere in this module — the
operational-scope gate stays CLOSED by construction (order §10).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecp.hashing import hash_document, hash_document_excluding  # noqa: E402

AT = "2026-09-10T01:00:00Z"
RULINGS = {slot: f"DEV-RULING-{slot}" for slot in ("O-01", "O-02", "O-04", "F-01a", "F-01b", "POP")}
ENV = {
    "environment_id": "ENV-DEV-001",
    "description": "development fixture environment",
    "pins": {"python": "3.12"},
}


def build_package(case_document, package_id="ECP-PKG-DEV-0001", evaluation_id="ECP-EVAL-DEV-0001", environment=None, provenance_extra=None):
    """Build a schema-valid development registration package with real hashes."""
    # deep-copy the module-level fixtures: packages must never alias shared
    # state (a mutated ENV in one test would silently leak into the next)
    environment = json.loads(json.dumps(environment or ENV))
    case_document = json.loads(json.dumps(case_document))
    provenance = {
        "origin": {
            "source_label": "development fixture",
            "sha256": hash_document(case_document),
        },
        "qualification": {
            "qualification_id": "ECP-QUAL-DEV-0001",
            "artifact_hash": hash_document({"fixture": True}),
        },
        "readiness": {
            "run_id": "ECP-RDNY-DEV-0001",
            "run_hash": hash_document({"fixture": "readiness"}),
        },
    }
    if provenance_extra:
        provenance.update(provenance_extra)
    package = {
        "ecp_object": "registration-package",
        "content_class": "format-illustration",
        "package_id": package_id,
        "evaluation_id": evaluation_id,
        "case_document": case_document,
        "ground_truth": {
            "commitment": case_document["ground_truth_reference"]["commitment"],
            "sealing_status": "sealed",
            "store_reference": "development fixture store",
        },
        "success_criterion": case_document["success_criterion"],
        "environment": environment,
        "provenance": provenance,
        "owner_ruling_citations": dict(RULINGS),
        "protocol_version": "0.7.0",
        "schema_version": "0.7.0",
        "package_hash": None,
    }
    package["package_hash"] = hash_document_excluding(package, "package_hash")
    return package


def build_order(order_id="ECP-GATEORDER-DEV-0001", scope="development", open_registration=True, open_execution=False):
    return {
        "ecp_object": "owner-gate-order",
        "content_class": "format-illustration",
        "order_id": order_id,
        "scope": scope,
        "owner_rulings": dict(RULINGS),
        "new_registration_gate": "OPEN" if open_registration else "CLOSED",
        "new_model_execution_gate": "OPEN" if open_execution else "CLOSED",
        "order_reference": {
            "basis": "development fixture order (FORMAT ILLUSTRATION: public template)",
        },
        "recorded_at": AT,
        "protocol_version": "0.7.0",
        "schema_version": "0.7.0",
    }


def build_observation(observation_id="ECP-OBS-DEV-0001", registration_id=None):
    obs = {
        "ecp_object": "runtime-observation",
        "content_class": "format-illustration",
        "observation_id": observation_id,
        "observation_kind": "runtime-note",
        "registration_id": registration_id,
        "content": {"note": "development fixture runtime note (FORMAT ILLUSTRATION)"},
        "authority_class": "NON-AUTHORITATIVE",
        "zone": "operational",
        "recorded_at": AT,
        "protocol_version": "0.7.0",
        "schema_version": "0.7.0",
        "observation_hash": None,
    }
    obs["observation_hash"] = hash_document_excluding(obs, "observation_hash")
    return obs


@pytest.fixture()
def dev_store(tmp_path):
    """An initialized development-scope trust store (gate CLOSED)."""
    from ecp import trust

    root = tmp_path / "trust"
    manifest = trust.init_trust_store(root, "ECP-TRUST-DEV-0001", "development", at=AT)
    return {"root": root, "manifest": manifest}


@pytest.fixture()
def example_case():
    return json.loads(
        (Path(__file__).resolve().parents[1] / "examples" / "case.development.example.json").read_text()
    )


@pytest.fixture()
def opened_store(dev_store):
    """A development trust store whose gate was opened by a synthetic order."""
    from ecp import trust

    order = build_order()
    trust.apply_owner_gate_order(dev_store["root"], order, at=AT)
    return dev_store
