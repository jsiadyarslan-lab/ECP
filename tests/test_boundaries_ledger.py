"""Ledger-tree boundary tests (R1-I: boundary-scan --ledger-root).

Machine-checks that the public ledger repository can never carry
protected ground-truth content or foreign ECP objects.
"""

import json

from ecp.boundaries import scan_ledger_tree


def _init_ledger(tmp_path):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from ecp import ledger

    root = tmp_path / "ledger"
    ledger.init_ledger(root, "ECP-LEDGER-TEST-0001", at="2026-09-09T00:00:00Z")
    return root


def test_clean_ledger_tree_scans_clean(tmp_path):
    root = _init_ledger(tmp_path)
    assert scan_ledger_tree(root) == []


def test_ground_truth_content_detected(tmp_path):
    root = _init_ledger(tmp_path)
    (root / "records" / "leak.json").write_text(
        json.dumps({"expected_answer": {"value": 42}}), encoding="utf-8"
    )
    violations = scan_ledger_tree(root)
    assert any(v["rule"] == "ledger-ground-truth-content" for v in violations)


def test_ground_truth_object_detected(tmp_path):
    root = _init_ledger(tmp_path)
    (root / "entries" / "extra.json").write_text(
        json.dumps({"ecp_object": "ground-truth"}), encoding="utf-8"
    )
    violations = scan_ledger_tree(root)
    assert any(v["rule"] == "ledger-ground-truth-content" for v in violations)


def test_foreign_ecp_object_detected(tmp_path):
    root = _init_ledger(tmp_path)
    (root / "records" / "case.json").write_text(
        json.dumps({"ecp_object": "case"}), encoding="utf-8"
    )
    violations = scan_ledger_tree(root)
    assert any(v["rule"] == "ledger-foreign-ecp-object" for v in violations)


def test_missing_structure_detected(tmp_path):
    violations = scan_ledger_tree(tmp_path / "not-a-ledger")
    assert any(v["rule"] == "ledger-structure-missing" for v in violations)


def test_unparseable_json_detected(tmp_path):
    root = _init_ledger(tmp_path)
    (root / "records" / "broken.json").write_text("{not json", encoding="utf-8")
    violations = scan_ledger_tree(root)
    assert any(v["rule"] == "ledger-invalid-json" for v in violations)


def test_allowed_objects_pass(tmp_path):
    root = _init_ledger(tmp_path)
    (root / "records" / "ECP-REG-000001.json").write_text(
        json.dumps({"ecp_object": "registration", "registration_id": "ECP-REG-000001"}),
        encoding="utf-8",
    )
    (root / "entries" / "00000001.json").write_text(
        json.dumps({"ecp_object": "ledger-entry", "entry_index": 1}),
        encoding="utf-8",
    )
    assert scan_ledger_tree(root) == []


def test_git_directory_is_skipped(tmp_path):
    root = _init_ledger(tmp_path)
    git_dir = root / ".git"
    git_dir.mkdir()
    (git_dir / "index.json").write_text(
        json.dumps({"anything": "goes"}), encoding="utf-8"
    )
    assert scan_ledger_tree(root) == []
