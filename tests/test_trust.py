"""M3-RG0 trust-layer tests — the order §11 verification battery.

Sections (order M3-RG0 v1 §11):
  integrity    — valid registration accepted; malformed refused; altered
                 case / ground truth / criterion / environment /
                 provenance / registration record detected.
  immutability — accepted record cannot be silently rewritten; amendment
                 creates a new event; original commitment stays verifiable.
  boundary     — ordinary runtime cannot mutate protected truth;
                 registration cannot occur through an ungoverned path;
                 execution cannot occur merely because the infrastructure
                 exists.
  lineage      — original artifact resolves to its registration event;
                 registration resolves to its committed artifact;
                 amendment lineage is deterministic.
  fail-closed  — every missing or contradictory mandatory trust input
                 produces refusal/blocking rather than inference.

All material is SYNTHETIC DEVELOPMENT fixtures (order §10: a successful
infrastructure test is never an authorization to register cases; the
operational gate stays CLOSED — exercised in the boundary section).
"""

import json
from pathlib import Path

import pytest

from trust_fixtures import AT, ENV, RULINGS, build_observation, build_order, build_package

from ecp import trust
from ecp.hashing import hash_document, hash_document_excluding


@pytest.fixture()
def dev_store(tmp_path):
    """An initialized development-scope trust store (gate CLOSED)."""
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
    order = build_order()
    trust.apply_owner_gate_order(dev_store["root"], order, at=AT)
    return dev_store


# ---------------------------------------------------------------------------
# store lifecycle + gate (components 1, 7)
# ---------------------------------------------------------------------------


def test_init_creates_closed_gate_with_null_citations(dev_store):
    gate = trust.store_gate_state(dev_store["root"])
    assert gate["registration_gate"] == "CLOSED"
    assert gate["model_execution_gate"] == "CLOSED"
    assert gate["scientific_results"] == "NONE"
    assert gate["owner_ruling_citations"] == {slot: None for slot in RULINGS}


def test_init_rejects_invalid_ids_and_scopes(tmp_path):
    with pytest.raises(trust.TrustError):
        trust.init_trust_store(tmp_path / "a", "BAD-ID", "development", at=AT)
    with pytest.raises(trust.TrustError):
        trust.init_trust_store(tmp_path / "b", "ECP-TRUST-DEV-0002", "production", at=AT)


def test_init_refuses_non_empty_root(dev_store, tmp_path):
    with pytest.raises(trust.TrustError):
        trust.init_trust_store(dev_store["root"], "ECP-TRUST-DEV-0003", "development", at=AT)


def test_zones_are_ownership_explicit(dev_store):
    root = dev_store["root"]
    for zone in ("authoritative", "operational", "evidence"):
        assert (root / zone / "README.md").is_file(), zone
    assert (root / "authoritative" / "gate.json").is_file()
    assert (root / "authoritative" / "registrations").is_dir()
    assert (root / "authoritative" / "amendments").is_dir()
    assert (root / "authoritative" / "lineage").is_dir()
    assert (root / "operational" / "runtime").is_dir()
    assert list((root / "evidence").glob("*")) == [(root / "evidence" / "README.md")]


def test_init_is_deterministic(tmp_path):
    a = trust.init_trust_store(tmp_path / "a", "ECP-TRUST-DEV-0010", "development", at=AT)
    b = trust.init_trust_store(tmp_path / "b", "ECP-TRUST-DEV-0010", "development", at=AT)
    assert a == b
    assert (tmp_path / "a" / "trust.json").read_bytes() == (tmp_path / "b" / "trust.json").read_bytes()


def test_manifest_gate_hash_matches_gate(dev_store):
    manifest = trust.load_trust_manifest(dev_store["root"])
    gate = trust.store_gate_state(dev_store["root"])
    assert manifest["gate"]["gate_hash"] == gate["gate_hash"]


# ---------------------------------------------------------------------------
# owner seam (component 7 — the ONLY gate transition)
# ---------------------------------------------------------------------------


def test_gate_order_opens_registration_only(opened_store):
    gate = trust.store_gate_state(opened_store["root"])
    assert gate["registration_gate"] == "OPEN"
    assert gate["model_execution_gate"] == "CLOSED"
    assert gate["scientific_results"] == "NONE"
    assert gate["owner_ruling_citations"] == RULINGS
    assert gate["gate_order_reference"]["order_id"] == "ECP-GATEORDER-DEV-0001"


def test_gate_order_is_scope_bound(dev_store):
    order = build_order(scope="operational")
    with pytest.raises(trust.OwnerOrderRejected, match="scope mismatch"):
        trust.apply_owner_gate_order(dev_store["root"], order, at=AT)


def test_gate_order_rejects_incomplete_rulings(dev_store):
    order = build_order()
    order["owner_rulings"]["POP"] = " "  # whitespace passes minLength, fails the completeness check
    with pytest.raises(trust.OwnerOrderRejected, match="incomplete"):
        trust.apply_owner_gate_order(dev_store["root"], order, at=AT)


def test_gate_order_rejects_execution_before_registration(dev_store):
    order = build_order(open_registration=False, open_execution=True)
    with pytest.raises(trust.OwnerOrderRejected, match="execution may not open"):
        trust.apply_owner_gate_order(dev_store["root"], order, at=AT)


def test_gate_order_rejects_noop_transition(dev_store):
    order = build_order(open_registration=False, open_execution=False)
    with pytest.raises(trust.OwnerOrderRejected, match="no-op"):
        trust.apply_owner_gate_order(dev_store["root"], order, at=AT)


def test_gate_order_rejects_duplicate_application(opened_store):
    order = build_order()
    with pytest.raises(trust.OwnerOrderRejected, match="already applied"):
        trust.apply_owner_gate_order(opened_store["root"], order, at=AT)


def test_gate_order_rejects_reopen_without_close(opened_store):
    order = build_order(order_id="ECP-GATEORDER-DEV-0002")
    with pytest.raises(trust.OwnerOrderRejected, match="close transition first"):
        trust.apply_owner_gate_order(opened_store["root"], order, at=AT)


def test_gate_order_close_then_reopen_is_legal(opened_store):
    root = opened_store["root"]
    close = build_order(order_id="ECP-GATEORDER-DEV-CLOSE", open_registration=False)
    closed = trust.apply_owner_gate_order(root, close, at=AT)
    assert closed["registration_gate"] == "CLOSED"
    reopen = build_order(order_id="ECP-GATEORDER-DEV-REOPEN")
    reopened = trust.apply_owner_gate_order(root, reopen, at=AT)
    assert reopened["registration_gate"] == "OPEN"
    assert trust.verify_trust_store(root)["ok"]


def test_gate_order_malformed_rejected(dev_store):
    with pytest.raises(trust.OwnerOrderRejected):
        trust.apply_owner_gate_order(dev_store["root"], {"ecp_object": "nope"}, at=AT)


def test_gate_state_tampering_detected(dev_store):
    root = dev_store["root"]
    path = root / "authoritative" / "gate.json"
    gate = json.loads(path.read_text())
    gate["registration_gate"] = "OPEN"
    path.write_text(json.dumps(gate, indent=2))
    with pytest.raises(trust.TrustInvalid, match="gate state invalid|gate_hash"):
        trust.load_gate_state(root)


# ---------------------------------------------------------------------------
# INTEGRITY (order §11): acceptance + refusal battery
# ---------------------------------------------------------------------------


def test_valid_registration_accepted(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    result = authority.submit_registration(package, at=AT)
    assert result["registration_id"] == "ECP-TREG-000001"
    assert result["registration_record"]["authority"]["decision"] == "ACCEPTED"
    report = trust.verify_trust_store(opened_store["root"])
    assert report["ok"], report["issues"]


def test_registration_refused_while_gate_closed(dev_store, example_case):
    authority = trust.RegistrationAuthority(dev_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration(package, at=AT)
    assert excinfo.value.stage == "gate"
    assert "gate is CLOSED" in excinfo.value.reason
    # the refusal itself is lineage-logged (never silent)
    events = trust._load_lineage(dev_store["root"])
    assert events[-1]["event_kind"] == "registration-refused"
    assert events[-1]["payload"]["stage"] == "gate"


def test_refusal_leaves_zero_records(dev_store, example_case):
    authority = trust.RegistrationAuthority(dev_store["root"], "ECP-REGISTRAR-DEV-0001")
    with pytest.raises(trust.RegistrationRefused):
        authority.submit_registration(build_package(example_case), at=AT)
    assert list((dev_store["root"] / "authoritative" / "registrations").glob("*.json")) == []
    assert trust.verify_trust_store(dev_store["root"])["ok"]


def test_malformed_package_refused(opened_store):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration({"ecp_object": "registration-package"}, at=AT)
    assert excinfo.value.stage == "package"


def test_version_incompatible_package_refused(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    package["protocol_version"] = "0.6.0"
    package["schema_version"] = "0.6.0"
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration(package, at=AT)
    assert excinfo.value.stage == "package"


def test_altered_package_hash_detected(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    package["environment"]["pins"]["python"] = "3.13"  # mutate after hashing
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration(package, at=AT)
    assert excinfo.value.stage == "commitments"


def test_altered_case_detected(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    other = json.loads(json.dumps(package))
    other["case_document"]["case_id"] = "S-999"
    other["package_hash"] = hash_document_excluding(other, "package_hash")
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration(other, at=AT)
    assert excinfo.value.stage == "case"


def test_altered_ground_truth_detected(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    other = json.loads(json.dumps(package))
    other["ground_truth"]["commitment"] = "f" * 64  # diverges from the case's commitment
    other["package_hash"] = hash_document_excluding(other, "package_hash")
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration(other, at=AT)
    assert excinfo.value.stage == "ground-truth"


def test_altered_criterion_detected(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    other = json.loads(json.dumps(package))
    other["success_criterion"] = "an easier criterion"
    other["package_hash"] = hash_document_excluding(other, "package_hash")
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration(other, at=AT)
    assert excinfo.value.stage == "commitments"


def test_altered_environment_detected(opened_store, example_case):
    # a diverging environment_id changes the frozen tuple -> accepted as a
    # NEW registration; but a mutated environment AFTER hashing is caught
    # by package_hash (altered-submission detection)
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    result = authority.submit_registration(package, at=AT)
    # the recorded environment commitment recomputes from the package
    assert result["commitments"]["environment"] == hash_document(package["environment"])
    tampered = json.loads(json.dumps(package))
    tampered["environment"]["pins"]["python"] = "3.13"
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration(tampered, at=AT)
    assert excinfo.value.stage == "commitments"


def test_altered_provenance_detected(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    result = authority.submit_registration(package, at=AT)
    assert result["commitments"]["provenance"] == hash_document(package["provenance"])
    tampered = json.loads(json.dumps(package))
    tampered["provenance"]["origin"]["sha256"] = "0" * 64
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration(tampered, at=AT)
    assert excinfo.value.stage == "commitments"


def test_altered_registration_record_detected(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    result = authority.submit_registration(package, at=AT)
    path = opened_store["root"] / "authoritative" / "registrations" / "ECP-TREG-000001.json"
    record = json.loads(path.read_text())
    record["commitments"]["case"] = "0" * 64
    path.write_text(json.dumps(record, indent=2))
    report = trust.verify_trust_store(opened_store["root"])
    assert not report["ok"]
    assert any("registration_hash does not recompute" in i for i in report["issues"])


def test_owner_citation_divergence_refused(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    package["owner_ruling_citations"]["POP"] = "18-ONLY"  # diverges from the gate
    package["package_hash"] = hash_document_excluding(package, "package_hash")
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration(package, at=AT)
    assert excinfo.value.stage == "owner-bound"
    assert "divergence" in excinfo.value.reason


def test_missing_owner_citation_refused_not_inferred(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    del package["owner_ruling_citations"]["O-04"]  # schema-level absence
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration(package, at=AT)
    assert excinfo.value.stage == "package"


def test_duplicate_tuple_refused(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    authority.submit_registration(package, at=AT)
    with pytest.raises(trust.RegistrationRefused) as excinfo:
        authority.submit_registration(package, at=AT)
    assert excinfo.value.stage == "duplicate"


def test_distinct_environment_is_not_a_duplicate(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    authority.submit_registration(build_package(example_case), at=AT)
    env2 = json.loads(json.dumps(ENV))
    env2["environment_id"] = "ENV-DEV-002"
    package2 = build_package(example_case, package_id="ECP-PKG-DEV-0002", environment=env2)
    result = authority.submit_registration(package2, at=AT)
    assert result["registration_id"] == "ECP-TREG-000002"


def test_commitments_are_authority_recomputed(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    result = authority.submit_registration(package, at=AT)
    c = result["commitments"]
    assert c["case"] == hash_document(example_case)
    assert c["criterion"] == hash_document({"success_criterion": example_case["success_criterion"]})
    assert c["environment"] == hash_document(package["environment"])
    assert c["provenance"] == hash_document(package["provenance"])
    assert c["package"] == package["package_hash"]
    assert c["algorithm"] == "sha256"
    assert c["canonicalization"] == "ECP-CANONICAL-JSON-1.0"


def test_registration_hash_uses_exclusion_rule(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    result = authority.submit_registration(build_package(example_case), at=AT)
    record = result["registration_record"]
    assert record["registration_hash"] == hash_document_excluding(record, "registration_hash")
    # populating the field then hashing the full doc gives a DIFFERENT value
    # (the exclusion rule is what prevents self-referential hashing errors)
    assert hash_document(record) != record["registration_hash"]


# ---------------------------------------------------------------------------
# IMMUTABILITY (order §11)
# ---------------------------------------------------------------------------


def test_accepted_record_cannot_be_silently_rewritten(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    result = authority.submit_registration(build_package(example_case), at=AT)
    path = opened_store["root"] / "authoritative" / "registrations" / "ECP-TREG-000001.json"
    record = json.loads(path.read_text())
    record["case"]["case_id"] = "S-999"
    path.write_text(json.dumps(record, indent=2))
    report = trust.verify_trust_store(opened_store["root"])
    assert not report["ok"]
    assert any("registration_hash does not recompute" in i for i in report["issues"])
    assert any("lineage event record_hash does not match" in i for i in report["issues"])


def test_amendment_creates_new_event_not_rewrite(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    result = authority.submit_registration(package, at=AT)
    path = opened_store["root"] / "authoritative" / "registrations" / "ECP-TREG-000001.json"
    original_bytes = path.read_bytes()
    target_hash = hash_document(result["registration_record"])
    env2 = json.loads(json.dumps(ENV))
    env2["pins"]["ecp"] = "0.7.0"
    am = authority.amend_registration(
        {
            "target_registration_id": "ECP-TREG-000001",
            "target_registration_hash": target_hash,
            "amendment_kind": "environment-revision",
            "motivation": "fixture: environment pin refresh",
            "replacement": {"environment": env2},
        },
        at=AT,
    )
    assert am["amendment_id"] == "ECP-TAMND-000001"
    assert path.read_bytes() == original_bytes  # the ORIGINAL is untouched
    assert trust.verify_trust_store(opened_store["root"])["ok"]


def test_original_commitment_remains_verifiable_after_amendment(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    result = authority.submit_registration(package, at=AT)
    target_hash = hash_document(result["registration_record"])
    authority.amend_registration(
        {
            "target_registration_id": "ECP-TREG-000001",
            "target_registration_hash": target_hash,
            "amendment_kind": "provenance-correction",
            "motivation": "fixture: provenance correction",
            "replacement": {
                "provenance": {
                    "origin": {"source_label": "development fixture (corrected)", "sha256": hash_document(example_case)},
                }
            },
        },
        at=AT,
    )
    resolved = trust.resolve_registration(opened_store["root"], "ECP-TREG-000001")
    # WHAT WAS REGISTERED still verifies
    assert resolved["what_was_registered"]["registration_hash"] == result["registration_hash"]
    assert resolved["commitments"] == result["commitments"]


def test_amendment_requires_motivation(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    result = authority.submit_registration(build_package(example_case), at=AT)
    with pytest.raises(trust.AmendmentRefused, match="motivation"):
        authority.amend_registration(
            {
                "target_registration_id": "ECP-TREG-000001",
                "target_registration_hash": hash_document(result["registration_record"]),
                "amendment_kind": "environment-revision",
                "motivation": "   ",
                "replacement": {"environment": ENV},
            },
            at=AT,
        )


def test_amendment_never_touches_case_or_ground_truth(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    result = authority.submit_registration(build_package(example_case), at=AT)
    with pytest.raises(trust.AmendmentRefused, match="never amendable"):
        authority.amend_registration(
            {
                "target_registration_id": "ECP-TREG-000001",
                "target_registration_hash": hash_document(result["registration_record"]),
                "amendment_kind": "environment-revision",
                "motivation": "fixture: illegal replacement",
                "replacement": {"case_document": example_case},
            },
            at=AT,
        )


def test_amendment_binds_exact_target(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    result = authority.submit_registration(build_package(example_case), at=AT)
    with pytest.raises(trust.AmendmentRefused, match="divergence"):
        authority.amend_registration(
            {
                "target_registration_id": "ECP-TREG-000001",
                "target_registration_hash": "0" * 64,
                "amendment_kind": "invalidation",
                "motivation": "fixture: stale binding",
            },
            at=AT,
        )


def test_invalidation_is_explicit_and_final(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    result = authority.submit_registration(build_package(example_case), at=AT)
    target_hash = hash_document(result["registration_record"])
    authority.amend_registration(
        {
            "target_registration_id": "ECP-TREG-000001",
            "target_registration_hash": target_hash,
            "amendment_kind": "invalidation",
            "motivation": "fixture: explicit retirement",
        },
        at=AT,
    )
    resolved = trust.resolve_registration(opened_store["root"], "ECP-TREG-000001")
    assert resolved["current_state"] == "INVALIDATED"
    # further amendments on an invalidated registration are refused
    with pytest.raises(trust.AmendmentRefused, match="already invalidated"):
        authority.amend_registration(
            {
                "target_registration_id": "ECP-TREG-000001",
                "target_registration_hash": target_hash,
                "amendment_kind": "environment-revision",
                "motivation": "fixture: too late",
                "replacement": {"environment": ENV},
            },
            at=AT,
        )
    # the same package can now be registered again (the tuple is free)
    again = authority.submit_registration(build_package(example_case, package_id="ECP-PKG-DEV-0009"), at=AT)
    assert again["registration_id"] == "ECP-TREG-000002"
    assert trust.verify_trust_store(opened_store["root"])["ok"]


def test_amendment_of_unknown_target_refused(opened_store):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    with pytest.raises(trust.AmendmentRefused, match="does not exist"):
        authority.amend_registration(
            {
                "target_registration_id": "ECP-TREG-000099",
                "target_registration_hash": "0" * 64,
                "amendment_kind": "invalidation",
                "motivation": "fixture: no such target",
            },
            at=AT,
        )


# ---------------------------------------------------------------------------
# BOUNDARY (order §11)
# ---------------------------------------------------------------------------


def test_runtime_cannot_mutate_protected_truth(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    result = authority.submit_registration(build_package(example_case), at=AT)
    original = json.loads(
        (opened_store["root"] / "authoritative" / "registrations" / "ECP-TREG-000001.json").read_text()
    )
    # the ONLY runtime write path records an observation — never a record
    obs = build_observation(registration_id="ECP-TREG-000001")
    trust.record_runtime_observation(opened_store["root"], obs, at=AT)
    after = json.loads(
        (opened_store["root"] / "authoritative" / "registrations" / "ECP-TREG-000001.json").read_text()
    )
    assert after == original
    assert list((opened_store["root"] / "operational" / "runtime").glob("*.json")) != []
    assert trust.verify_trust_store(opened_store["root"])["ok"]


def test_operational_seam_refuses_authoritative_objects(opened_store):
    with pytest.raises(trust.AccessBoundaryError):
        trust.record_runtime_observation(opened_store["root"], {"ecp_object": "trust-registration"}, at=AT)


def test_operational_docs_cannot_masquerade_as_authoritative(opened_store, example_case):
    # a runtime observation that drops the NON-AUTHORITATIVE marker is
    # schema-invalid AND the verifier flags marker-less operational files
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    authority.submit_registration(build_package(example_case), at=AT)
    root = opened_store["root"]
    bad = build_observation(registration_id="ECP-TREG-000001")
    bad.pop("authority_class")
    bad.pop("observation_hash")
    bad["observation_hash"] = hash_document_excluding(bad, "observation_hash")
    path = root / "operational" / "runtime" / f"{bad['observation_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    from ecp.canonical import canonical_bytes

    path.write_bytes(canonical_bytes(bad))
    report = trust.verify_trust_store(root)
    assert not report["ok"]
    assert any("NON-AUTHORITATIVE marker" in i or bad["observation_id"] in i for i in report["issues"])


def test_runtime_observation_refuses_fabricated_references(opened_store):
    obs = build_observation(registration_id="ECP-TREG-000099")
    with pytest.raises(trust.TrustError, match="unresolvable registration"):
        trust.record_runtime_observation(opened_store["root"], obs, at=AT)


def test_runtime_observation_ids_are_write_once(opened_store):
    obs = build_observation()
    trust.record_runtime_observation(opened_store["root"], obs, at=AT)
    with pytest.raises(trust.TrustError, match="write-once"):
        trust.record_runtime_observation(opened_store["root"], build_observation(), at=AT)


def test_ungoverned_registration_detected(opened_store, example_case):
    # a record file dropped into the authoritative zone WITHOUT the
    # authority ceremony (no lineage event) is detected by verification
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    result = authority.submit_registration(build_package(example_case), at=AT)
    root = opened_store["root"]
    rogue = json.loads(json.dumps(result["registration_record"]))
    rogue["registration_id"] = "ECP-TREG-000002"
    rogue["package_id"] = "ECP-PKG-ROGUE"
    rogue["registration_hash"] = hash_document_excluding(rogue, "registration_hash")
    from ecp.canonical import canonical_bytes

    (root / "authoritative" / "registrations" / "ECP-TREG-000002.json").write_bytes(canonical_bytes(rogue))
    report = trust.verify_trust_store(root)
    assert not report["ok"]
    assert any("ungoverned write detected" in i for i in report["issues"])


def test_execution_cannot_occur_merely_because_infrastructure_exists(opened_store, example_case):
    # the execution gate stays CLOSED even after the registration gate
    # opens; an evidence file appearing at 0.7.0 (no writer exists) is a
    # verification issue
    root = opened_store["root"]
    gate = trust.store_gate_state(root)
    assert gate["model_execution_gate"] == "CLOSED"
    (root / "evidence" / "results.json").write_text("{}")
    report = trust.verify_trust_store(root)
    assert not report["ok"]
    assert any("no evidence writer exists" in i for i in report["issues"])
    (root / "evidence" / "results.json").unlink()
    assert trust.verify_trust_store(root)["ok"]


def test_lineage_chain_break_detected(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    authority.submit_registration(build_package(example_case), at=AT)
    root = opened_store["root"]
    # reorder: remove the first event (trust-init) -> chain breaks
    (root / "authoritative" / "lineage" / "00000001.json").unlink()
    report = trust.verify_trust_store(root)
    assert not report["ok"]
    assert any("gap/duplicate" in i or "chain break" in i or "not trust-init" in i for i in report["issues"])


def test_lineage_event_tampering_detected(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    authority.submit_registration(build_package(example_case), at=AT)
    root = opened_store["root"]
    path = root / "authoritative" / "lineage" / "00000001.json"
    event = json.loads(path.read_text())
    event["payload"]["scope"] = "operational"  # rewrite the init payload
    from ecp.canonical import canonical_bytes

    path.write_bytes(canonical_bytes(event))
    report = trust.verify_trust_store(root)
    assert not report["ok"]
    assert any("event_hash does not recompute" in i for i in report["issues"])


def test_manifest_drift_detected(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    authority.submit_registration(build_package(example_case), at=AT)
    root = opened_store["root"]
    path = root / "trust.json"
    manifest = json.loads(path.read_text())
    manifest["zones"]["authoritative"]["registrations"] = 99
    # tamper CANONICALLY (self-hash recomputes, so the DRIFT check fires
    # rather than the self-hash check)
    manifest["manifest_hash"] = hash_document_excluding(manifest, "manifest_hash")
    from ecp.canonical import canonical_bytes

    path.write_bytes(canonical_bytes(manifest))
    report = trust.verify_trust_store(root)
    assert not report["ok"]
    assert any("manifest drift" in i for i in report["issues"])


def test_acceptance_outside_open_window_detected(dev_store, example_case):
    # forge a store where a record exists while the gate says CLOSED:
    # build it via the legal path, then close the gate; then ALSO strip
    # the close event — the replay must catch the inconsistency
    authority_forbidden = None  # noqa: F841
    root = dev_store["root"]
    order = build_order()
    trust.apply_owner_gate_order(root, order, at=AT)
    authority = trust.RegistrationAuthority(root, "ECP-REGISTRAR-DEV-0001")
    authority.submit_registration(build_package(example_case), at=AT)
    # legally close the gate
    trust.apply_owner_gate_order(root, build_order(order_id="ECP-GATEORDER-DEV-CLOSE", open_registration=False), at=AT)
    assert trust.verify_trust_store(root)["ok"]  # acceptance happened inside the OPEN window
    # now forge: remove BOTH gate-transition events (un-governed re-close)
    import shutil as _shutil

    events = sorted((root / "authoritative" / "lineage").glob("*.json"))
    kept = [json.loads(p.read_text()) for p in events if json.loads(p.read_text())["event_kind"] in ("trust-init", "registration-accepted")]
    _shutil.rmtree(root / "authoritative" / "lineage")
    (root / "authoritative" / "lineage").mkdir()
    prev = "0" * 64
    from ecp.canonical import canonical_bytes

    for i, event in enumerate(kept, start=1):
        event["event_index"] = i
        event["prev_event_hash"] = prev
        event["event_hash"] = hash_document_excluding(event, "event_hash")
        prev = event["event_hash"]
        (root / "authoritative" / "lineage" / f"{i:08d}.json").write_bytes(canonical_bytes(event))
    # relink the record to the (new) accepting event index
    rec_path = root / "authoritative" / "registrations" / "ECP-TREG-000001.json"
    record = json.loads(rec_path.read_text())
    record["lineage"]["event_index"] = 2
    record["registration_hash"] = hash_document_excluding(record, "registration_hash")
    rec_path.write_bytes(canonical_bytes(record))
    # gate.json says CLOSED; the replay sees no transitions at all
    report = trust.verify_trust_store(root)
    assert not report["ok"]
    assert any("registration-accepted while" in i for i in report["issues"])


# ---------------------------------------------------------------------------
# LINEAGE (order §11)
# ---------------------------------------------------------------------------


def test_original_artifact_resolves_to_its_registration_event(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    result = authority.submit_registration(package, at=AT)
    resolved = trust.resolve_registration(opened_store["root"], "ECP-TREG-000001")
    event = resolved["accepting_event"]
    assert event["event_index"] == result["event_index"] == resolved["what_was_registered"]["lineage"]["event_index"]
    # the event's record hash resolves back to the committed artifact
    chain = trust._load_lineage(opened_store["root"])
    accepting = [e for e in chain if e["event_kind"] == "registration-accepted"][0]
    assert accepting["payload"]["record_hash"] == hash_document(resolved["what_was_registered"])


def test_registration_resolves_to_its_committed_artifact(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    result = authority.submit_registration(package, at=AT)
    resolved = trust.resolve_registration(opened_store["root"], "ECP-TREG-000001")
    assert resolved["record_hash"] == result["record_hash"]
    assert resolved["commitments"]["case"] == hash_document(package["case_document"])
    assert resolved["commitments"]["package"] == package["package_hash"]


def test_amendment_lineage_is_deterministic(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    result = authority.submit_registration(build_package(example_case), at=AT)
    target_hash = hash_document(result["registration_record"])
    am1 = authority.amend_registration(
        {
            "target_registration_id": "ECP-TREG-000001",
            "target_registration_hash": target_hash,
            "amendment_kind": "environment-revision",
            "motivation": "fixture: env v2",
            "replacement": {"environment": {**ENV, "description": "dev v2"}},
        },
        at=AT,
    )
    am2 = authority.amend_registration(
        {
            "target_registration_id": "ECP-TREG-000001",
            "target_registration_hash": target_hash,
            "amendment_kind": "provenance-correction",
            "motivation": "fixture: provenance v2",
            "replacement": {
                "provenance": {"origin": {"source_label": "dev (corrected)", "sha256": hash_document(example_case)}}
            },
        },
        at=AT,
    )
    resolved = trust.resolve_registration(opened_store["root"], "ECP-TREG-000001")
    ids = [a["amendment_id"] for a in resolved["what_later_happened"]["amendments"]]
    assert ids == [am1["amendment_id"], am2["amendment_id"]] == ["ECP-TAMND-000001", "ECP-TAMND-000002"]
    assert resolved["current_state"] == "AMENDED"
    assert resolved["what_was_registered"] == result["registration_record"]


def test_no_execution_result_overwrites_registration_provenance(opened_store, example_case):
    # execution material is not an event kind: a runtime observation about
    # an execution attempt NEVER enters the lineage or the record
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    result = authority.submit_registration(build_package(example_case), at=AT)
    before = trust._load_lineage(opened_store["root"])
    obs = build_observation(observation_id="ECP-OBS-DEV-EXEC", registration_id="ECP-TREG-000001")
    obs["observation_kind"] = "execution-attempt-observation"
    obs["content"] = {"attempted": True, "note": "a runtime execution attempt observation (FORMAT ILLUSTRATION)"}
    obs.pop("observation_hash")
    obs["observation_hash"] = hash_document_excluding(obs, "observation_hash")
    trust.record_runtime_observation(opened_store["root"], obs, at=AT)
    after = trust._load_lineage(opened_store["root"])
    assert before == after  # lineage untouched by runtime material
    resolved = trust.resolve_registration(opened_store["root"], "ECP-TREG-000001")
    assert resolved["what_was_registered"] == result["registration_record"]


# ---------------------------------------------------------------------------
# STATE / REFERENCE-TRUTH SEPARATION (order §11 / §6)
# ---------------------------------------------------------------------------


def test_reference_truth_ignores_runtime_zone(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    authority.submit_registration(build_package(example_case), at=AT)
    trust.record_runtime_observation(opened_store["root"], build_observation(registration_id="ECP-TREG-000001"), at=AT)
    truth = trust.store_reference_truth(opened_store["root"])
    assert truth["source_zone"] == "authoritative"
    assert len(truth["registrations"]) == 1
    assert "observations" not in truth


def test_runtime_state_is_explicitly_non_authoritative(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    authority.submit_registration(build_package(example_case), at=AT)
    trust.record_runtime_observation(opened_store["root"], build_observation(registration_id="ECP-TREG-000001"), at=AT)
    runtime = trust.store_runtime_state(opened_store["root"])
    assert runtime["non_authoritative"] is True
    assert runtime["source_zone"] == "operational"
    assert len(runtime["observations"]) == 1
    assert "registrations" not in runtime


def test_what_was_registered_independent_of_what_later_happened(opened_store, example_case):
    authority = trust.RegistrationAuthority(opened_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    result = authority.submit_registration(package, at=AT)
    target_hash = hash_document(result["registration_record"])
    authority.amend_registration(
        {
            "target_registration_id": "ECP-TREG-000001",
            "target_registration_hash": target_hash,
            "amendment_kind": "environment-revision",
            "motivation": "fixture: change after registration",
            "replacement": {"environment": {**ENV, "description": "dev v2"}},
        },
        at=AT,
    )
    trust.record_runtime_observation(opened_store["root"], build_observation(registration_id="ECP-TREG-000001"), at=AT)
    resolved = trust.resolve_registration(opened_store["root"], "ECP-TREG-000001")
    assert resolved["what_was_registered"]["environment_id"] == package["environment"]["environment_id"]
    assert resolved["commitments"]["environment"] == hash_document(package["environment"])
    assert len(resolved["what_later_happened"]["amendments"]) == 1
    assert len(resolved["what_later_happened"]["runtime_observations"]) == 1


# ---------------------------------------------------------------------------
# FAIL-CLOSED (order §11)
# ---------------------------------------------------------------------------


def test_missing_store_is_trust_invalid(tmp_path):
    with pytest.raises(trust.TrustInvalid):
        trust.load_trust_manifest(tmp_path / "nothing")


def test_unreadable_store_verification_reports_issues(tmp_path):
    report = trust.verify_trust_store(tmp_path / "nothing")
    assert not report["ok"]


def test_authority_requires_registrar_identity(dev_store):
    with pytest.raises(trust.TrustError):
        trust.RegistrationAuthority(dev_store["root"], "not-a-registrar")


def test_every_refusal_is_lineage_logged(dev_store, example_case):
    authority = trust.RegistrationAuthority(dev_store["root"], "ECP-REGISTRAR-DEV-0001")
    package = build_package(example_case)
    with pytest.raises(trust.RegistrationRefused):
        authority.submit_registration(package, at=AT)  # gate
    gate_order = build_order()
    trust.apply_owner_gate_order(dev_store["root"], gate_order, at=AT)
    with pytest.raises(trust.RegistrationRefused):
        authority.submit_registration({"bad": "package"}, at=AT)  # package
    events = trust._load_lineage(dev_store["root"])
    refusals = [e for e in events if e["event_kind"] == "registration-refused"]
    assert [r["payload"]["stage"] for r in refusals] == ["gate", "package"]
    assert trust.verify_trust_store(dev_store["root"])["ok"]


def test_gate_open_requires_complete_citations(dev_store):
    # a hand-forged OPEN gate without citations fails schema verification
    root = dev_store["root"]
    path = root / "authoritative" / "gate.json"
    gate = json.loads(path.read_text())
    gate["registration_gate"] = "OPEN"
    gate["gate_hash"] = hash_document_excluding(gate, "gate_hash")
    from ecp.canonical import canonical_bytes

    path.write_bytes(canonical_bytes(gate))
    with pytest.raises(trust.TrustInvalid):
        trust.load_gate_state(root)


def test_verify_clean_store_passes(dev_store):
    report = trust.verify_trust_store(dev_store["root"])
    assert report["ok"]
    assert report["counts"]["registrations"] == 0
    assert report["counts"]["lineage_events"] == 1
    assert report["gate"]["registration_gate"] == "CLOSED"
