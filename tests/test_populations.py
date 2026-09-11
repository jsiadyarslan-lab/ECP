"""M3 population namespace governance — machine-checkable invariant battery.

Ordered by M3 AUTHORITATIVE SCIENTIFIC POPULATION GOVERNANCE &
NAMESPACE COLLISION CLOSURE v1 §17: namespace uniqueness, candidate-ID
collision detection, content-hash collision distinction,
population-qualified lookup, ambiguous candidate-ID rejection,
provenance consistency, historical preservation, and architecture
boundary (no new runner, no duplicate registry, no execution-path
coupling).

Everything here is OFFLINE and read-only: the manifest is historical
metadata (hashes only); no case content, ground truth, or protected
material is present in this repository.
"""

import json
import re
from pathlib import Path

import pytest

from ecp.populations import (
    AmbiguousCandidateIdError,
    CandidateIdentity,
    ContentHashMismatchError,
    NamespaceCollisionError,
    PopulationNamespaceIndex,
    PopulationRecord,
    UnknownNamespaceError,
    read_manifest_document,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "provenance" / "m3-population-namespace-manifest.json"
REGISTRATION_SUMMARY = (
    REPO_ROOT / "registration" / "M3-NATIVE-REGISTRATION-SUMMARY.json"
)
CORPUS_MANIFEST = REPO_ROOT / "provenance" / "m3-native-corpus-manifest.json"

NATIVE = "ECP-POP-M3-NATIVE-V1"
CA0V1 = "ECP-POP-M3-CA0V1-V1"
NATIVE_PACK = "ECP-CASEPACK-M3-NATIVE"
CA0V1_PACK = "ECP-CASEPACK-M3-CA0V1"

# The historical collision, hash-pinned by M3 AIR v1.1 and re-derived here
# from the public registration records and the CA0v1 intake report.
COLLIDING_IDS = ["ECP-CAND-000101", "ECP-CAND-000102", "ECP-CAND-000103"]
NATIVE_HASHES = {
    "ECP-CAND-000101": "8e8feb011bfb8895b59fafff6091f36308393ae53bb11262fbbc6f29a9c817f5",
    "ECP-CAND-000102": "73fbb9904cfd1c1af6eb063dcffaa8bb07dc77a9366b68960c7d5bb63ca6a7da",
    "ECP-CAND-000103": "0d054c99dd5957c23b2948fbac8c59f697ea6b0f0ef074407910b0d915832711",
}
CA0V1_HASHES = {
    "ECP-CAND-000101": "28562c5ca5bedc911f7a124e7ca31103703c5ae27df401e1c0672cf5a275ecd9",
    "ECP-CAND-000102": "17fcf09cd9826ace859e4349fd46479417258022f9a87d180167b5a4d891d2bf",
    "ECP-CAND-000103": "06ab98eb689fa50001e3e2dc6189e1e983706b7583264e1c897993ba96ccd598",
}


@pytest.fixture(scope="module")
def index() -> PopulationNamespaceIndex:
    return PopulationNamespaceIndex.from_manifest_file(MANIFEST_PATH)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return read_manifest_document(MANIFEST_PATH)


# ---------------------------------------------------------------------------
# Namespace: uniqueness, model shape
# ---------------------------------------------------------------------------


def test_manifest_object_type(manifest):
    assert manifest["ecp_object"] == "m3-population-namespace-manifest"


def test_exactly_two_historical_populations(index, manifest):
    """Populations A (Native) and B (CA0v1) only — no future population."""
    assert index.population_count == 2
    assert set(index.population_ids) == {NATIVE, CA0V1}
    assert all("FUTURE" not in pid for pid in index.population_ids)
    assert "future" in manifest["future_population_policy"].lower()


def test_namespace_uniqueness(index):
    """No two populations share a namespace key or population_id."""
    keys = [p.namespace_key.as_tuple() for p in index.populations]
    assert len(set(keys)) == len(keys) == 2
    assert len(set(index.population_ids)) == 2


def test_identity_fields_are_five_part(manifest):
    fields = manifest["namespace_model"]["identity_fields"]
    assert fields == [
        "population_id",
        "case_pack_id",
        "case_pack_version",
        "candidate_id",
        "content_hash",
    ]


# ---------------------------------------------------------------------------
# Collision: detection, distinction, invariant
# ---------------------------------------------------------------------------


def test_candidate_id_collision_detected(index):
    """The historical collision is machine-visible: 3 overlapping IDs."""
    overlaps = index.cross_population_overlaps()
    assert sorted(overlaps) == COLLIDING_IDS
    report = index.collision_report()
    assert report["collision_detected"] is True
    assert report["overlap_count"] == 3


def test_colliding_ids_have_divergent_hashes(index):
    """Same ID, two populations, DIFFERENT content hashes (not a merge)."""
    for cid in COLLIDING_IDS:
        identities = index.distinct_identities(cid)
        assert len(identities) == 2
        hashes = {i.population_id: i.content_hash for i in identities}
        assert hashes[NATIVE] == NATIVE_HASHES[cid]
        assert hashes[CA0V1] == CA0V1_HASHES[cid]
        assert hashes[NATIVE] != hashes[CA0V1]


def test_content_hash_collision_distinction(index):
    """Same candidate_id + different namespace = distinct, unequal identities."""
    for cid in COLLIDING_IDS:
        native_identity = index.lookup(NATIVE, NATIVE_PACK, 1, cid)
        ca0v1_identity = index.lookup(CA0V1, CA0V1_PACK, 1, cid)
        assert native_identity != ca0v1_identity
        assert native_identity.candidate_id == ca0v1_identity.candidate_id
        assert native_identity.content_hash != ca0v1_identity.content_hash
        assert native_identity.qualified_reference() != ca0v1_identity.qualified_reference()


def test_within_namespace_collision_invariant_holds(index):
    """Real data: no namespace maps one candidate_id to two hashes."""
    index.assert_collision_invariant()  # must not raise
    assert index.collision_report()["within_namespace_collisions"] == []


def test_within_namespace_collision_invariant_enforced_synthetic():
    """Same namespace + same candidate_id + different content_hash = COLLISION."""
    with pytest.raises(NamespaceCollisionError):
        PopulationRecord(
            population_id="SYNTH-POP",
            case_pack_id="SYNTH-PACK",
            case_pack_version=1,
            status="SYNTHETIC",
            candidates=(
                ("ECP-CAND-000001", "0" * 64),
                ("ECP-CAND-000001", "1" * 64),
            ),
            candidate_count=2,
        )


# ---------------------------------------------------------------------------
# Lookup: the permitted path and the rejected path
# ---------------------------------------------------------------------------


def test_population_qualified_lookup_native(index):
    identity = index.lookup(NATIVE, NATIVE_PACK, 1, "ECP-CAND-000102")
    assert isinstance(identity, CandidateIdentity)
    assert identity.content_hash == NATIVE_HASHES["ECP-CAND-000102"]
    assert identity.population_id == NATIVE
    assert identity.case_pack_version == 1


def test_population_qualified_lookup_ca0v1(index):
    identity = index.lookup(CA0V1, CA0V1_PACK, 1, "ECP-CAND-000130")
    assert identity.population_id == CA0V1
    assert re.fullmatch(r"[0-9a-f]{64}", identity.content_hash)


def test_population_qualified_lookup_with_hash_verification(index):
    identity = index.lookup(
        CA0V1, CA0V1_PACK, 1, "ECP-CAND-000101",
        expected_content_hash=CA0V1_HASHES["ECP-CAND-000101"],
    )
    assert index.verify(identity, CA0V1_HASHES["ECP-CAND-000101"]) is True


def test_lookup_rejects_cross_population_hash_confusion(index):
    """Presenting the NATIVE hash under the CA0V1 namespace is rejected:
    the collision cannot be exploited to smuggle one population's
    artifact as the other's."""
    with pytest.raises(ContentHashMismatchError):
        index.lookup(CA0V1, CA0V1_PACK, 1, "ECP-CAND-000102",
                     expected_content_hash=NATIVE_HASHES["ECP-CAND-000102"])
    with pytest.raises(ContentHashMismatchError):
        index.lookup(NATIVE, NATIVE_PACK, 1, "ECP-CAND-000102",
                     expected_content_hash=CA0V1_HASHES["ECP-CAND-000102"])


def test_lookup_rejects_wrong_case_pack(index):
    with pytest.raises(UnknownNamespaceError):
        index.lookup(NATIVE, CA0V1_PACK, 1, "ECP-CAND-000101")


def test_lookup_rejects_wrong_version(index):
    with pytest.raises(UnknownNamespaceError):
        index.lookup(NATIVE, NATIVE_PACK, 2, "ECP-CAND-000101")


def test_lookup_rejects_unknown_candidate(index):
    with pytest.raises(UnknownNamespaceError):
        index.lookup(NATIVE, NATIVE_PACK, 1, "ECP-CAND-000999")


def test_ambiguous_candidate_id_rejected(index):
    """ECP-CAND-000101 exists in BOTH populations -> AMBIGUOUS_ID -> REJECTED."""
    with pytest.raises(AmbiguousCandidateIdError, match="AMBIGUOUS_ID"):
        index.lookup_by_candidate_id("ECP-CAND-000101")


def test_ambiguous_rejection_even_when_id_is_unique_today(index):
    """ECP-CAND-000130 exists in ONE population, but with 2 populations
    registered the unqualified path stays closed — the native corpus
    proved that today's unique ID is tomorrow's collision."""
    with pytest.raises(AmbiguousCandidateIdError, match="AMBIGUOUS_ID"):
        index.lookup_by_candidate_id("ECP-CAND-000130")


def test_ambiguous_rejection_for_unknown_id(index):
    with pytest.raises(AmbiguousCandidateIdError, match="AMBIGUOUS_ID"):
        index.lookup_by_candidate_id("ECP-CAND-999999")


def test_content_hash_mismatch_rejected(index):
    identity = index.lookup(NATIVE, NATIVE_PACK, 1, "ECP-CAND-000101")
    with pytest.raises(ContentHashMismatchError):
        index.verify(identity, CA0V1_HASHES["ECP-CAND-000101"])


# ---------------------------------------------------------------------------
# Provenance: manifest consistency with the historical public records
# ---------------------------------------------------------------------------


def test_native_index_matches_public_registration_records(index):
    """The native candidate_index is re-derived from the registration
    records committed in this repository — independent cross-check."""
    summary = json.loads(REGISTRATION_SUMMARY.read_text())
    derived = {r["candidate_id"]: r["case_hash"] for r in summary["records"]}
    assert index.population(NATIVE).candidate_index == derived


def test_native_provenance_pins_match_corpus_manifest(index, manifest):
    corpus = json.loads(CORPUS_MANIFEST.read_text())
    native = index.population(NATIVE)
    assert native.provenance["source_sha256"] == corpus["native_corpus"]["source_sha256"]
    assert native.candidate_count == corpus["native_corpus"]["case_count"]
    assert native.provenance["semantic_families"] == corpus["native_corpus"]["semantic_families"]
    assert native.provenance["registration_set_id"] == "ECP-REGSET-M3-NATIVE-V1"


def test_native_authoring_order_pin_recorded_as_null(index):
    """The native provenance gap (all-zero order pin) is preserved as-is."""
    pin = index.population(NATIVE).provenance["authoring_order_pin_sha256"]
    assert pin == "0" * 64
    assert index.population(NATIVE).provenance["authoring_order_pin_status"].startswith("NULL")


def test_ca0v1_population_internal_consistency(index):
    ca0v1 = index.population(CA0V1)
    ids = ca0v1.candidate_ids
    assert ca0v1.candidate_count == 30 == len(ids)
    assert ids == tuple(f"ECP-CAND-{n:06d}" for n in range(101, 131))
    assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in ca0v1.candidate_index.values())


def test_ca0v1_qualification_gap_recorded(index):
    """The qualification-layer persistence gap is recorded, not hidden."""
    prov = index.population(CA0V1).provenance
    assert prov["qualification_persistence"].startswith("NOT-PERSISTED")
    assert set(prov["qualification_record_pins"]) == {
        "chain_head_sha256",
        "run_manifest_file_sha256",
        "run_hash",
    }


def test_collision_record_consistent_with_indexes(index, manifest):
    record = manifest["collision_record"]
    overlaps = index.cross_population_overlaps()
    assert record["affected_candidate_ids"] == sorted(overlaps)
    for cid, holders in record["hash_comparison"].items():
        by_pop = {h["population_id"]: h["content_hash"] for h in overlaps[cid]}
        assert holders == by_pop


def test_relationship_status_unknown_on_both_sides(index):
    """No invented relationship: both sides declare UNKNOWN."""
    for pid in (NATIVE, CA0V1):
        rel = index.population(pid).provenance["relationship_to_other_populations"]
        assert rel.startswith("UNKNOWN")


def test_manifest_pins_baseline_and_jarvis(manifest):
    assert manifest["baseline_commit"] == "7420eac93ff0eb11b1f0b4836296402cfdeb64da"
    jarvis = manifest["jarvis_reference"]
    assert jarvis["sha256"] == (
        "cc867e9794d72b160396f3527f928cb919641812dc8ef1ae3bd7db21723bf001"
    )
    assert jarvis["case_count"] == 23
    assert "M3-S30-LINF-01" in jarvis["status"]


# ---------------------------------------------------------------------------
# Historical preservation
# ---------------------------------------------------------------------------


def test_populations_are_read_only(index):
    for population in index.populations:
        assert population.status == "HISTORICAL-PRESERVED-READ-ONLY"


def test_historical_ids_and_ranges_preserved(manifest):
    native, ca0v1 = manifest["populations"]
    assert native["provenance"]["registered_case_ids"] == [
        "ECP-NATIVE-001", "ECP-NATIVE-002", "ECP-NATIVE-003",
    ]
    assert ca0v1["candidate_id_range"] == ["ECP-CAND-000101", "ECP-CAND-000130"]


def test_decisions_recorded_and_separated(manifest):
    decisions = manifest["decisions"]
    assert decisions["namespace_decision"] == "COLLISION ISOLATED / NAMESPACES VALID"
    assert decisions["population_decision"] == "BLOCKED — NO AUTHORITATIVE POPULATION"
    for pid in (NATIVE, CA0V1):
        assert pid in decisions["criterion_status"]


# ---------------------------------------------------------------------------
# Architecture boundary: governance only, execution path untouched
# ---------------------------------------------------------------------------


def test_populations_module_has_no_execution_coupling():
    """The namespace model imports nothing from the execution path —
    Universal Experiment Execution Contract v1 stays decoupled."""
    source = (REPO_ROOT / "src" / "ecp" / "populations.py").read_text()
    for forbidden in (
        "from .console", "from ecp.console", "import console",
        "from .adapters", "from ecp.adapters",
        "from .runtime_adapters", "from ecp.runtime_adapters",
        "from .execution_contract", "from ecp.execution_contract",
        "from .credential", "from .credentials", "from .openai_adapter",
        "from .openrouter_adapter", "from .gemini_adapter",
    ):
        assert forbidden not in source, f"forbidden coupling: {forbidden}"


def test_no_new_runner_and_no_duplicate_registry():
    """src/ecp declares exactly the baseline registries and no runner."""
    registry_classes = set()
    runner_classes = set()
    for path in sorted((REPO_ROOT / "src" / "ecp").glob("*.py")):
        for match in re.finditer(r"^class\s+(\w+)\b", path.read_text(), re.M):
            name = match.group(1)
            if "Registry" in name:
                registry_classes.add(name)
            if "Runner" in name:
                runner_classes.add(name)
    assert registry_classes == {
        "AdapterRegistry",
        "RuntimeAdapterRegistry",
        "ProviderRegistry",
        "TargetRegistry",
    }
    assert runner_classes == set()


def test_manifest_is_metadata_only(manifest):
    """No case content, ground truth, or protected material in the manifest."""
    blob = json.dumps(manifest)
    for forbidden in ("GROUND_TRUTH", "ground_truth", "intended_correct_answer", "DERIVATION", "premises"):
        assert forbidden not in blob
    assert manifest["populations"][0]["provenance"]["source_sha256"]
