#!/usr/bin/env python3
"""ECP foundation CLI.

Commands (all infrastructure-only; nothing here executes models, scores
results, or adjudicates science):

  identity                              print the pinned protocol identity
  validate --schema S --file F          validate a JSON document against schema S
  hash --doc F | --file F               canonical-document hash / raw-file hash
  manifest build --dir D --out F        build a deterministic manifest over a directory
  manifest verify --manifest F --root R verify a manifest against real files
  boundary-scan                         enforce the public/protected boundary
  verify-commitment --case F --ground-truth F
                                        verify a case's ground-truth seal

Run from the repository root:  python tools/ecp_cli.py <command> ...
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ecp import boundaries, canonical, hashing, identity, manifest as manifest_mod, validate, verification  # noqa: E402


def _print_json(document: dict) -> None:
    print(json.dumps(document, indent=2, ensure_ascii=False))


def cmd_identity(_args: argparse.Namespace) -> int:
    _print_json(identity.load_identity())
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    document = canonical.load_json(args.file)
    issues = validate.validate_document(document, args.schema)
    if issues:
        print(f"INVALID ({args.schema}): {args.file}")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print(f"VALID ({args.schema}): {args.file}")
    return 0


def cmd_hash(args: argparse.Namespace) -> int:
    if bool(args.doc) == bool(args.file):
        print("error: exactly one of --doc / --file is required", file=sys.stderr)
        return 2
    if args.doc:
        digest = hashing.hash_document(canonical.load_json(args.doc))
        print(f"canonical-document sha256 ({args.doc}): {digest}")
    else:
        digest = hashing.hash_file(args.file)
        print(f"raw-file sha256 ({args.file}): {digest}")
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    if args.command != "manifest":
        return 2
    if args.action == "build":
        directory = Path(args.dir).resolve()
        if not directory.is_dir():
            print(f"error: not a directory: {directory}", file=sys.stderr)
            return 2
        root = (Path(args.root) if args.root else REPO_ROOT).resolve()
        items = []
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                items.append(
                    {
                        "role": "artifact",
                        "path": path.relative_to(root).as_posix(),
                        "hash": hashing.hash_file(path),
                    }
                )
        ident = identity.load_identity()
        document = manifest_mod.build_manifest(
            items,
            manifest_type=args.type,
            protocol_version=ident["protocol_version"],
            schema_version=ident["schema_version"],
            generated_at=args.generated_at,
        )
        out = Path(args.out)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(document, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"manifest written: {out} ({len(document['entries'])} entries)")
        print(f"manifest_hash: {document['manifest_hash']}")
        return 0
    if args.action == "verify":
        manifest_doc = canonical.load_json(args.manifest)
        root = (Path(args.root) if args.root else REPO_ROOT).resolve()
        file_hashes = {
            entry["path"]: hashing.hash_file(root / entry["path"])
            for entry in manifest_doc.get("entries", [])
        }
        issues = verification.verify_manifest(manifest_doc, file_hashes)
        if issues:
            print(f"MANIFEST ISSUES ({args.manifest}):")
            for issue in issues:
                print(f"  - {issue}")
            return 1
        print(f"MANIFEST INTACT ({args.manifest}): {len(manifest_doc['entries'])} entries verified")
        return 0
    return 2


def cmd_boundary_scan(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else REPO_ROOT
    violations = boundaries.scan_repository(root)
    print(boundaries.format_violations(violations))
    return 1 if violations else 0


def cmd_verify_commitment(args: argparse.Namespace) -> int:
    case_doc = canonical.load_json(args.case)
    gt_doc = canonical.load_json(args.ground_truth)
    issues = verification.verify_commitment(case_doc, gt_doc)
    if issues:
        print(f"COMMITMENT MISMATCH ({args.case} vs {args.ground_truth}):")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print(
        f"COMMITMENT VERIFIED: case {case_doc.get('case_id')} seal matches "
        f"ground truth {args.ground_truth}"
    )
    return 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(prog="ecp_cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("identity", help="print the pinned protocol identity").set_defaults(func=cmd_identity)

    p_validate = sub.add_parser("validate", help="validate a JSON document against a schema")
    p_validate.add_argument("--schema", required=True, help="object name, e.g. case, system, evidence")
    p_validate.add_argument("--file", required=True)
    p_validate.set_defaults(func=cmd_validate)

    p_hash = sub.add_parser("hash", help="compute a deterministic hash")
    p_hash.add_argument("--doc", help="JSON document: canonical-form hash")
    p_hash.add_argument("--file", help="raw file: byte hash")
    p_hash.set_defaults(func=cmd_hash)

    p_manifest = sub.add_parser("manifest", help="build or verify a manifest")
    p_manifest.add_argument("action", choices=["build", "verify"])
    p_manifest.add_argument("--dir", help="directory to manifest (build)")
    p_manifest.add_argument("--out", default="manifest.json", help="output path (build)")
    p_manifest.add_argument("--manifest", help="manifest file (verify)")
    p_manifest.add_argument("--root", help="root for path resolution (default: repository root)")
    p_manifest.add_argument("--type", default="artifact-set", help="manifest_type (build)")
    p_manifest.add_argument("--generated-at", default="1970-01-01T00:00:00Z", help="pinned UTC timestamp (build)")
    p_manifest.set_defaults(func=cmd_manifest)

    p_scan = sub.add_parser("boundary-scan", help="enforce the public/protected boundary")
    p_scan.add_argument("--root", help="repository root (default: this checkout)")
    p_scan.set_defaults(func=cmd_boundary_scan)

    p_commit = sub.add_parser("verify-commitment", help="verify a case's ground-truth seal")
    p_commit.add_argument("--case", required=True)
    p_commit.add_argument("--ground-truth", required=True)
    p_commit.set_defaults(func=cmd_verify_commitment)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
