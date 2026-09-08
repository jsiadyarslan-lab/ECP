"""Public/protected boundary tests (§10, §17, §24)."""

import json

from ecp.boundaries import (
    GROUND_TRUTH_CONTENT_KEYS,
    RESERVED_DIRS,
    scan_repository,
)


def _rule(violations, rule):
    return [v for v in violations if v["rule"] == rule]


def test_repository_boundary_scan_is_clean(repo_root):
    violations = scan_repository(repo_root)
    assert violations == []


def test_reserved_dirs_exist(repo_root):
    for directory in RESERVED_DIRS:
        assert (repo_root / directory).is_dir()


def test_reserved_dirs_contain_only_readme(repo_root):
    for directory in RESERVED_DIRS:
        entries = sorted(p.name for p in (repo_root / directory).iterdir())
        assert entries == ["README.md"], f"{directory}/: {entries}"


def test_no_ground_truth_content_outside_examples(repo_root):
    for path in repo_root.rglob("*.json"):
        relative = path.relative_to(repo_root).as_posix()
        if any(part.startswith(".") for part in path.relative_to(repo_root).parts[:-1]):
            continue
        if relative.startswith("examples/"):
            continue
        with open(path, encoding="utf-8") as fh:
            document = json.load(fh)
        if isinstance(document, dict):
            for key in GROUND_TRUTH_CONTENT_KEYS:
                assert key not in document, f"{relative} carries protected key {key!r}"


def test_example_ground_truth_is_format_illustration(examples):
    assert examples["ground-truth.format-example.json"]["content_class"] == "format-illustration"


def test_example_case_commitment_present_and_hex(examples):
    import re

    commitment = examples["case.development.example.json"]["ground_truth_reference"]["commitment"]
    assert re.fullmatch(r"[0-9a-f]{64}", commitment)


# ------- synthetic violations in a scratch tree -------

def _scratch(tmp_path):
    for directory in RESERVED_DIRS:
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "README.md").write_text("reserved", encoding="utf-8")
    (tmp_path / "examples").mkdir()
    return tmp_path


def test_scan_flags_foreign_file_in_reserved_dir(tmp_path):
    root = _scratch(tmp_path)
    (root / "cases" / "case-42.json").write_text("{}", encoding="utf-8")
    violations = scan_repository(root)
    assert _rule(violations, "reserved-dir-foreign-file")


def test_scan_flags_subdirectory_in_reserved_dir(tmp_path):
    root = _scratch(tmp_path)
    (root / "evidence" / "bundle-01").mkdir()
    violations = scan_repository(root)
    assert _rule(violations, "reserved-dir-foreign-entry")


def test_scan_flags_ground_truth_object_outside_examples(tmp_path):
    root = _scratch(tmp_path)
    (root / "gt.json").write_text(json.dumps({"ecp_object": "ground-truth", "content_class": "sealed"}), encoding="utf-8")
    violations = scan_repository(root)
    assert _rule(violations, "ground-truth-outside-examples")


def test_scan_flags_ground_truth_keys_outside_examples(tmp_path):
    root = _scratch(tmp_path)
    (root / "leak.json").write_text(json.dumps({"expected_answer": {"value": 5}}), encoding="utf-8")
    violations = scan_repository(root)
    assert _rule(violations, "ground-truth-outside-examples")


def test_scan_flags_sealed_content_in_examples(tmp_path):
    root = _scratch(tmp_path)
    (root / "examples" / "gt.json").write_text(
        json.dumps({"ecp_object": "ground-truth", "content_class": "sealed", "derivation": []}), encoding="utf-8"
    )
    violations = scan_repository(root)
    assert _rule(violations, "example-ground-truth-not-illustration")


def test_scan_flags_case_without_commitment(tmp_path):
    root = _scratch(tmp_path)
    (root / "examples" / "case.json").write_text(
        json.dumps({"ecp_object": "case", "ground_truth_reference": {}}), encoding="utf-8"
    )
    violations = scan_repository(root)
    assert _rule(violations, "case-missing-ground-truth-commitment")


def test_scan_flags_unparseable_json(tmp_path):
    root = _scratch(tmp_path)
    (root / "broken.json").write_text("{not json", encoding="utf-8")
    violations = scan_repository(root)
    assert _rule(violations, "invalid-json")


def test_scan_skips_dot_directories(tmp_path):
    root = _scratch(tmp_path)
    hidden = root / ".git"
    hidden.mkdir()
    (hidden / "config.json").write_text("{", encoding="utf-8")
    assert scan_repository(root) == []
