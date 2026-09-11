"""Machine-checkable verification of the CA0v1 qualification evidence matrix.

Covers the investigation-specific requirements of the order
CA0v1 QUALIFICATION PROVENANCE RESTORATION & AUTHORITATIVE POPULATION
RE-ADJUDICATION v1 (section 19):

- CA0v1 artifact identity / hash consistency / provenance chain
- historical-vs-reconstructed distinction
- artifact recovery classification
- execution provenance classification
- qualification traceability decision
- KNOWN / INFERRED / UNKNOWN separation
- Native/CA0v1 relationship handling (fail-closed)
- namespace result and collision record consistency
- five-gate population decision rule
- recovery-artifact labeling (NEW GOVERNANCE/RECOVERY ARTIFACT; no backdating)
- zero scientific execution counters

These tests are OFFLINE: they read committed JSON documents only; they never
invoke a provider, never touch the network, and never re-run qualification.
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = REPO_ROOT / "provenance" / "m3-ca0v1-qualification-evidence-matrix.json"
NS_MANIFEST_PATH = REPO_ROOT / "provenance" / "m3-population-namespace-manifest.json"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HEX8_RE = re.compile(r"^[0-9a-f]{8}")

ARTIFACT_STATUSES = {"FOUND", "NOT FOUND"}
HISTORICAL_STATUSES = {
    "ORIGINAL (git custody)",
    "ORIGINAL (session custody)",
    "ORIGINAL (protected custody)",
    "ORIGINAL (external custody)",
    "RECONSTRUCTED-BYTE-VERIFIED",
    "ABSENT (PIN-RECORDED)",
    "ABSENT (PIN-RECORDED, RECONSTRUCTION-PROVEN)",
    "RECONSTRUCTION-EVENTS-DOCUMENTED",
}
CONFIDENCE_CLASSES = {"KNOWN", "INFERRED", "UNKNOWN"}
LAYER_ENUMS = {
    "artifact_recovery": {"PARTIAL", "FULL", "NONE"},
    "provenance_recovery": {"VERIFIED", "PARTIALLY VERIFIED", "UNKNOWN", "NOT RECOVERABLE"},
    "historical_execution_provenance": {"VERIFIED", "PARTIALLY VERIFIED", "UNKNOWN", "NOT RECOVERABLE"},
    "deterministic_reconstruction": {"RECONSTRUCTIBLE", "NOT RECONSTRUCTIBLE", "UNKNOWN"},
}
OVERALL_ENUM = {
    "RESTORED",
    "PARTIALLY RESTORED",
    "RECONSTRUCTIBLE BUT NOT HISTORICALLY RESTORED",
    "NOT RECOVERABLE",
}
TRACEABILITY_ENUM = {"VERIFIED", "PARTIALLY VERIFIED", "RECONSTRUCTIBLE ONLY", "NOT RECOVERABLE"}
RELATIONSHIP_ENUM = {"REPLACEMENT", "DERIVED", "INDEPENDENT", "UNKNOWN"}
GATE_ENUM = {"PASS", "FAIL", "UNKNOWN", "PARTIAL"}


@pytest.fixture(scope="module")
def matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ns_manifest() -> dict:
    return json.loads(NS_MANIFEST_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- labeling & dating


class TestRecoveryArtifactLabeling:
    def test_artifact_class_is_explicit_new_governance_artifact(self, matrix):
        assert matrix["artifact_class"] == "NEW GOVERNANCE/RECOVERY ARTIFACT"

    def test_artifact_class_note_disclaims_historicity(self, matrix):
        note = matrix["artifact_class_note"]
        assert "NOT a historical artifact" in note
        assert "NOT a qualification record" in note
        assert "No timestamp was backdated" in note

    def test_created_at_not_backdated(self, matrix):
        # the record must be dated at or after the baseline commit date
        # (baseline 8873cb4 was created 2026-09-11T21:39Z)
        assert matrix["created_at"] >= "2026-09-11T21:39:50Z"

    def test_baseline_commit_is_order_baseline(self, matrix):
        assert matrix["baseline_commit"].startswith("8873cb4")

    def test_phase_name_recorded(self, matrix):
        assert "QUALIFICATION PROVENANCE RESTORATION" in matrix["phase"]
        assert "RE-ADJUDICATION" in matrix["phase"]


# ---------------------------------------------------------------- artifact identity & hashes


class TestArtifactIdentityAndHashes:
    def test_every_recovery_row_has_required_fields(self, matrix):
        for row in matrix["artifact_recovery"]:
            for field in (
                "artifact", "path", "identity", "content_hash", "source",
                "provenance", "historical_status", "relationship_to_ca0v1",
                "artifact_status",
            ):
                assert field in row, (row.get("artifact"), field)
                assert row[field], (row.get("artifact"), field)

    def test_artifact_status_enum(self, matrix):
        for row in matrix["artifact_recovery"]:
            assert row["artifact_status"] in ARTIFACT_STATUSES

    def test_historical_status_enum(self, matrix):
        for row in matrix["artifact_recovery"]:
            assert row["historical_status"] in HISTORICAL_STATUSES, row["historical_status"]

    def test_pinned_hashes_are_well_formed(self, matrix):
        for name, value in matrix["pins"].items():
            assert SHA256_RE.match(value), (name, value)

    def test_qualification_layer_pins_present(self, matrix):
        pins = matrix["pins"]
        assert pins["qualification_chain_head"].startswith("f137598d")
        assert pins["qualification_run_file"].startswith("0bb9eeee")
        assert pins["qualification_run_hash"].startswith("1678694c")

    def test_authoring_layer_pins_present(self, matrix):
        pins = matrix["pins"]
        assert pins["ca0v1_source"].startswith("8144818c")
        assert pins["ca0v1_sidecar"].startswith("0f4e2318")
        assert pins["ca0v1_intake_report"].startswith("fc8a3532")
        assert pins["ca0v1_order_reference"].startswith("2695594b")


# ---------------------------------------------------------------- historical vs reconstructed


class TestHistoricalVsReconstructed:
    def test_authoring_layer_is_reconstructed_byte_verified_not_original(self, matrix):
        statuses = {r["artifact"]: r["historical_status"] for r in matrix["artifact_recovery"]}
        for name in (
            "CA0v1 authored case-set source",
            "CA0v1 provenance sidecar",
            "CA0v1 intake report",
            "CA0v1 candidates (30)",
        ):
            assert statuses[name] == "RECONSTRUCTED-BYTE-VERIFIED", name

    def test_qualification_layer_is_absent_pin_recorded(self, matrix):
        statuses = {r["artifact"]: r["historical_status"] for r in matrix["artifact_recovery"]}
        assert statuses["CA0v1 qualification artifacts (30)"] == (
            "ABSENT (PIN-RECORDED, RECONSTRUCTION-PROVEN)"
        )
        assert statuses["CA0v1 qualification run manifest"] == (
            "ABSENT (PIN-RECORDED, RECONSTRUCTION-PROVEN)"
        )

    def test_qualification_layer_reported_not_found(self, matrix):
        statuses = {r["artifact"]: r["artifact_status"] for r in matrix["artifact_recovery"]}
        assert statuses["CA0v1 qualification artifacts (30)"] == "NOT FOUND"
        assert statuses["CA0v1 qualification run manifest"] == "NOT FOUND"
        assert statuses["CA0v1 order reference (order text)"] == "NOT FOUND"

    def test_reconstructible_is_not_restored(self, matrix):
        # the deterministic-reconstruction layer must never upgrade the overall
        # classification to a historically-restored state while the artifact
        # layer is NOT FOUND
        overall = matrix["overall_recovery_classification"]
        assert overall in OVERALL_ENUM
        qual_not_found = any(
            r["artifact"] == "CA0v1 qualification artifacts (30)"
            and r["artifact_status"] == "NOT FOUND"
            for r in matrix["artifact_recovery"]
        )
        if qual_not_found:
            # the qualification record objects are gone: the overall verdict
            # can only be reconstruction-grade or worse, never restored-grade
            assert overall in (
                "RECONSTRUCTIBLE BUT NOT HISTORICALLY RESTORED",
                "NOT RECOVERABLE",
            )

    def test_reconstruction_layer_does_not_execute(self, matrix):
        summary = matrix["recovery_layers"]["deterministic_reconstruction"]["summary"]
        assert "NOT re-executed in this phase" in summary
        assert "RECONSTRUCTIBLE does NOT equal HISTORICALLY RESTORED" in summary


# ---------------------------------------------------------------- layer classifications


class TestRecoveryLayerClassifications:
    def test_layer_enums(self, matrix):
        layers = matrix["recovery_layers"]
        for layer, allowed in LAYER_ENUMS.items():
            assert layers[layer]["classification"] in allowed, (
                layer, layers[layer]["classification"]
            )

    def test_overall_classification_enum(self, matrix):
        assert matrix["overall_recovery_classification"] in OVERALL_ENUM

    def test_traceability_enum(self, matrix):
        decision = matrix["qualification_traceability"]["decision"]
        assert decision in TRACEABILITY_ENUM

    def test_execution_provenance_is_partially_verified(self, matrix):
        # script exists + report exists + same-party attestation => PARTIAL,
        # never auto-upgraded to VERIFIED from report language alone
        layer = matrix["recovery_layers"]["historical_execution_provenance"]
        assert layer["classification"] == "PARTIALLY VERIFIED"

    def test_traceability_consistent_with_layers(self, matrix):
        # traceability must not exceed what the layers support: with the
        # artifact layer NOT FOUND and same-party attestation, VERIFIED is
        # unreachable
        decision = matrix["qualification_traceability"]["decision"]
        assert decision != "VERIFIED"

    def test_custody_event_history_is_ordered_and_anchored(self, matrix):
        events = matrix["custody_event_history"]
        assert len(events) >= 10
        for event in events:
            assert event["at"]
            assert event["evidence"]
        # the contemporaneous anchor (report committed minutes after the run)
        anchors = [e for e in events if e["at"].startswith("2026-09-09T04:44")]
        assert anchors and "d6c456c" in anchors[0]["evidence"]


# ---------------------------------------------------------------- evidence matrix rows


class TestEvidenceMatrixRows:
    def test_every_row_has_required_fields(self, matrix):
        for row in matrix["evidence_matrix"]:
            for field in (
                "claim", "artifact", "artifact_hash", "source", "provenance",
                "historical_status", "verification_status", "confidence_class",
            ):
                assert field in row, (row.get("claim"), field)

    def test_confidence_class_enum(self, matrix):
        for row in matrix["evidence_matrix"]:
            assert row["confidence_class"] in CONFIDENCE_CLASSES, row["claim"]

    def test_known_inferred_unknown_separation(self, matrix):
        classes = {row["claim"]: row["confidence_class"] for row in matrix["evidence_matrix"]}
        # present, byte-verified content => KNOWN
        assert classes["CA0v1 source artifact content equals sha256 8144818c..."] == "KNOWN"
        assert classes[
            "30 candidates ECP-CAND-000101..000130 are complete, ordered, unique, and hash-consistent"
        ] == "KNOWN"
        # documented same-party claims about absent artifacts => INFERRED, never KNOWN
        assert classes[
            "qualification decisions were ACCEPT=30 / REVISE=0 / REJECT=0 / INCONCLUSIVE=0 (30/30 ACCEPT)"
        ] == "INFERRED"
        assert classes[
            "ground truth was mechanically verified for all 30 candidates (Q3 PASS x30, four deterministic semantics)"
        ] == "INFERRED"
        assert classes[
            "qualify-run ECP-QUALRUN-CA0V1-R1 executed at 2026-09-09T04:38:30Z with operator ECP Foundation Executor"
        ] == "INFERRED"
        # unresolved relationship => UNKNOWN
        assert classes[
            "the Native population (ECP-POP-M3-NATIVE-V1) is a REPLACEMENT of, DERIVED from, or INDEPENDENT of CA0v1"
        ] == "UNKNOWN"

    def test_negative_existence_claim_is_known(self, matrix):
        classes = {row["claim"]: row["confidence_class"] for row in matrix["evidence_matrix"]}
        assert classes[
            "the original (first-write) qualification artifact file objects still exist somewhere on this host or in any repository"
        ] == "KNOWN"

    def test_no_claim_of_independent_verification_from_report_language(self, matrix):
        # rows whose verification is documentary must say so explicitly
        for row in matrix["evidence_matrix"]:
            if row["confidence_class"] == "INFERRED":
                assert row["verification_status"] != "VERIFIED-TODAY", row["claim"]


# ---------------------------------------------------------------- relationship & namespace


class TestNativeRelationshipFailClosed:
    def test_relationship_enum_and_value(self, matrix):
        rel = matrix["native_ca0v1_relationship"]
        assert rel["decision"] in RELATIONSHIP_ENUM
        assert rel["decision"] == "UNKNOWN"

    def test_relationship_basis_forbids_chronology_inference(self, matrix):
        basis = " ".join(matrix["native_ca0v1_relationship"]["basis"])
        assert "inadmissible as relationship evidence" in basis

    def test_qualification_id_range_overlap_recorded(self, matrix):
        basis = " ".join(matrix["native_ca0v1_relationship"]["basis"])
        assert "ECP-QUAL-000100" in basis


class TestNamespaceResult:
    def test_collision_record_matches_namespace_manifest(self, matrix, ns_manifest):
        affected = ns_manifest["collision_record"]["affected_candidate_ids"]
        assert affected == [
            "ECP-CAND-000101", "ECP-CAND-000102", "ECP-CAND-000103",
        ]
        assert matrix["namespace_verification"]["collision_status"].startswith("COLLISION ISOLATED")

    def test_bare_lookup_rejection_recorded(self, matrix):
        policy = matrix["namespace_verification"]["bare_lookup_policy"]
        assert "ALWAYS rejected" in policy
        assert "AmbiguousCandidateIdError" in policy

    def test_cross_population_reuse_is_valid_distinct_identities(self, matrix):
        assert matrix["namespace_verification"]["cross_population_reuse"].startswith(
            "VALID DISTINCT IDENTITIES"
        )

    def test_candidate_count_consistent_with_manifest(self, matrix, ns_manifest):
        pops = {p["population_id"]: p for p in ns_manifest["populations"]}
        assert pops["ECP-POP-M3-CA0V1-V1"]["candidate_count"] == 30
        assert pops["ECP-POP-M3-NATIVE-V1"]["candidate_count"] == 3

    def test_ca0v1_collision_hashes_match_manifest(self, matrix, ns_manifest):
        manifest_hashes = ns_manifest["collision_record"]["hash_comparison"]
        assert manifest_hashes["ECP-CAND-000101"]["ECP-POP-M3-CA0V1-V1"].startswith("28562c5c")
        assert manifest_hashes["ECP-CAND-000101"]["ECP-POP-M3-NATIVE-V1"].startswith("8e8feb01")


# ---------------------------------------------------------------- five gates & decision


class TestFiveGateDecision:
    def test_gate_enums(self, matrix):
        gates = matrix["five_gates"]
        assert set(gates) == {
            "gate_1_provenance", "gate_2_scientific_fitness", "gate_3_integrity",
            "gate_4_namespace_uniqueness", "gate_5_historical_integrity",
        }
        for name, gate in gates.items():
            assert gate["status"] in GATE_ENUM, (name, gate["status"])
            assert gate["basis"]

    def test_decision_rule_recorded(self, matrix):
        assert "all five gates must be PASS" in matrix["population_decision_rule"]

    def test_blocked_because_not_all_pass(self, matrix):
        statuses = [g["status"] for g in matrix["five_gates"].values()]
        all_pass = all(s == "PASS" for s in statuses)
        decision = matrix["population_decision"]
        if all_pass:
            assert decision.startswith("AUTHORITATIVE POPULATION")
        else:
            assert decision == "BLOCKED — NO AUTHORITATIVE POPULATION"

    def test_current_decision_is_blocked(self, matrix):
        assert matrix["population_decision"] == "BLOCKED — NO AUTHORITATIVE POPULATION"

    def test_gates_consistent_with_traceability(self, matrix):
        # Gate 1 must not be PASS while traceability is below VERIFIED
        trace = matrix["qualification_traceability"]["decision"]
        gate1 = matrix["five_gates"]["gate_1_provenance"]["status"]
        if trace != "VERIFIED":
            assert gate1 != "PASS"

    def test_gate2_not_pass_while_qualification_layer_absent(self, matrix):
        qual_found = any(
            r["artifact"] == "CA0v1 qualification artifacts (30)"
            and r["artifact_status"] == "FOUND"
            for r in matrix["artifact_recovery"]
        )
        gate2 = matrix["five_gates"]["gate_2_scientific_fitness"]["status"]
        if not qual_found:
            assert gate2 != "PASS"


# ---------------------------------------------------------------- execution isolation


class TestExecutionIsolation:
    def test_zero_counters(self, matrix):
        status = matrix["scientific_execution_status"]
        assert status["m3_executions"] == 0
        assert status["provider_calls"] == 0
        assert status["qualification_reruns"] == 0
        assert status["credential_access"] == 0

    def test_no_authoritative_population_implies_no_auto_m3(self, matrix):
        # the decision block must not carry any M3-start authorization
        assert "M3" not in matrix["population_decision"]
