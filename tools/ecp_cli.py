#!/usr/bin/env python3
"""ECP foundation CLI.

Commands (all infrastructure-only; nothing here executes models, scores
results, or adjudicates science):

  identity                              print the pinned protocol identity
  validate --schema S --file F          validate a JSON document against schema S
  hash --doc F | --file F               canonical-document hash / raw-file hash
  manifest build --dir D --out F        build a deterministic manifest over a directory
  manifest verify --manifest F --root R verify a manifest against real files
  boundary-scan [--ledger-root L]      enforce the public/protected boundary
                                        (optionally also scan a ledger tree)
  verify-commitment --case F --ground-truth F
                                        verify a case's ground-truth seal

Protected store (R1-I, Option C — custody half of the seam):

  store-init --root D --store-id ID --scope S   initialize a protected store
  store-seal --root D --gt F                     seal a ground-truth document
  store-verify --root D [--cases D]             full store verification

Registration ledger (R1-I, Option C — authority half of the seam):

  ledger-init --root D --ledger-id ID           initialize an empty ledger
  register --ledger D --registrar ID --case F --store D --system F
            --evaluation-id ID [--note S ...] [--supersedes ID]
                                                 registration ceremony (freeze + append)
  invalidate --ledger D --registrar ID --registration-id ID --reason S
                                                 explicit invalidation entry
  ledger-verify --ledger D [--cases D]           public verification
  anchor-publish --ledger D                      publish the chain HEAD anchor

Run from the repository root:  python tools/ecp_cli.py <command> ...
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ecp import boundaries, canonical, hashing, identity, ledger as ledger_mod, manifest as manifest_mod, store as store_mod, validate, verification  # noqa: E402


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
    exit_code = 1 if violations else 0
    if args.ledger_root:
        ledger_violations = boundaries.scan_ledger_tree(args.ledger_root)
        print(
            "LEDGER TREE "
            + (
                f"{len(ledger_violations)} violation(s)"
                if ledger_violations
                else "CLEAN — public ledger boundary respected"
            )
        )
        for violation in ledger_violations:
            print(
                f"  [{violation['rule']}] {violation['path']}: {violation['detail']}"
            )
        exit_code = exit_code or (1 if ledger_violations else 0)
    return exit_code


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


# ---------------------------------------------------------------------------
# Protected store (R1-I, Option C — custody half of the seam)
# ---------------------------------------------------------------------------

def cmd_store_init(args: argparse.Namespace) -> int:
    try:
        manifest = store_mod.init_store(
            args.root, args.store_id, args.scope, at=args.at
        )
    except store_mod.StoreError as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    print(f"store initialized: {args.root}")
    _print_json(manifest)
    return 0


def cmd_store_seal(args: argparse.Namespace) -> int:
    gt_doc = canonical.load_json(args.gt)
    try:
        result = store_mod.seal(args.root, gt_doc, at=args.at)
    except store_mod.SealRejected as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    print(f"sealed: {result['case_id']}@{result['case_version']}")
    _print_json(result)
    return 0


def cmd_store_verify(args: argparse.Namespace) -> int:
    report = store_mod.verify_store(args.root, cases_dir=args.cases)
    if report["ok"]:
        print(
            f"STORE VERIFIED: {report['seal_count']} seal(s), "
            f"{report['oplog_count']} oplog entries, "
            f"head {report['head_oplog_hash'][:16]}…"
        )
        if args.cases:
            print(f"public-case cross-check: {args.cases}")
        return 0
    print(f"STORE ISSUES ({args.root}):")
    for issue in report["issues"]:
        print(f"  - {issue}")
    return 1


# ---------------------------------------------------------------------------
# Registration ledger (R1-I, Option C — authority half of the seam)
# ---------------------------------------------------------------------------

def cmd_ledger_init(args: argparse.Namespace) -> int:
    try:
        anchor = ledger_mod.init_ledger(args.root, args.ledger_id, at=args.at)
    except ledger_mod.LedgerError as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    print(f"ledger initialized (clean state, zero entries): {args.root}")
    _print_json(anchor)
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    case_doc = canonical.load_json(args.case)
    system_doc = canonical.load_json(args.system)
    try:
        result = ledger_mod.register(
            args.ledger,
            args.registrar,
            case_doc,
            args.store,
            system_doc,
            args.evaluation_id,
            at=args.at,
            notes=tuple(args.note or ()),
            supersedes=args.supersedes,
        )
    except ledger_mod.RegistrationRejected as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    except ledger_mod.LedgerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    summary = {
        "registration_id": result["registration_id"],
        "registration_hash": result["registration_hash"],
        "record_hash": result["record_hash"],
        "entry_index": result["entry_index"],
        "entry_hash": result["entry_hash"],
        "ground_truth_commitments": result["commitments"],
    }
    print(f"registered: {result['registration_id']} (entry {result['entry_index']})")
    _print_json(summary)
    return 0


def cmd_invalidate(args: argparse.Namespace) -> int:
    try:
        result = ledger_mod.invalidate(
            args.ledger,
            args.registrar,
            args.registration_id,
            args.reason,
            at=args.at,
        )
    except ledger_mod.RegistrationRejected as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    except ledger_mod.LedgerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        f"invalidated: {result['registration_id']} "
        f"(entry {result['entry_index']})"
    )
    _print_json(result)
    return 0


def cmd_ledger_verify(args: argparse.Namespace) -> int:
    report = ledger_mod.ledger_verify(args.ledger, cases_dir=args.cases)
    if report["ok"]:
        print(
            f"LEDGER VERIFIED: {report['entries']} entries, "
            f"{report['live_registrations']} live registration(s), "
            f"{len(report['invalidated'])} invalidated, "
            f"{len(report['superseded'])} superseded"
        )
        if report["unanchored_tail"]:
            print(
                f"NOTE: {report['unanchored_tail']} unanchored tail "
                "entries (anchor behind chain head; run anchor-publish)"
            )
        if args.cases:
            print(
                f"public-case commitment checks: {report['commitment_checks']}"
            )
        return 0
    print(f"LEDGER ISSUES ({args.ledger}):")
    for issue in report["issues"]:
        print(f"  - {issue}")
    return 1


def cmd_anchor_publish(args: argparse.Namespace) -> int:
    try:
        anchor = ledger_mod.anchor_publish(args.ledger, at=args.at)
    except ledger_mod.LedgerError as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    print(
        f"ANCHOR PUBLISHED: entry_count {anchor['entry_count']}, "
        f"head {anchor['head_entry_hash'][:16]}…"
    )
    print(
        "operator ceremony: commit + push the ledger repository now "
        "(one commit per anchor; never rewrite historical anchors)"
    )
    _print_json(anchor)
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
    p_scan.add_argument(
        "--ledger-root",
        help="additionally scan a public ledger tree for protected-content "
        "violations and structural boundary rules",
    )
    p_scan.set_defaults(func=cmd_boundary_scan)

    p_commit = sub.add_parser("verify-commitment", help="verify a case's ground-truth seal")
    p_commit.add_argument("--case", required=True)
    p_commit.add_argument("--ground-truth", required=True)
    p_commit.set_defaults(func=cmd_verify_commitment)

    # --- protected store (R1-I) ---
    p_store_init = sub.add_parser("store-init", help="initialize a protected store")
    p_store_init.add_argument("--root", required=True, help="store root (outside the public repository)")
    p_store_init.add_argument("--store-id", required=True, help="ECP-STORE-… identifier")
    p_store_init.add_argument("--scope", required=True, choices=["development", "operational"])
    p_store_init.add_argument("--at", default=None, help="pinned UTC timestamp (default: now)")
    p_store_init.set_defaults(func=cmd_store_init)

    p_store_seal = sub.add_parser("store-seal", help="seal a ground-truth document (write-once)")
    p_store_seal.add_argument("--root", required=True, help="store root")
    p_store_seal.add_argument("--gt", required=True, help="ground-truth JSON document (content_class: sealed)")
    p_store_seal.add_argument("--at", default=None, help="pinned UTC timestamp (default: now)")
    p_store_seal.set_defaults(func=cmd_store_seal)

    p_store_verify = sub.add_parser("store-verify", help="full store verification (recomputation)")
    p_store_verify.add_argument("--root", required=True, help="store root")
    p_store_verify.add_argument("--cases", default=None, help="public cases directory for seam cross-check")
    p_store_verify.set_defaults(func=cmd_store_verify)

    # --- registration ledger (R1-I) ---
    p_ledger_init = sub.add_parser("ledger-init", help="initialize an empty ledger (clean state)")
    p_ledger_init.add_argument("--root", required=True, help="ledger root")
    p_ledger_init.add_argument("--ledger-id", required=True, help="ECP-LEDGER-… identifier")
    p_ledger_init.add_argument("--at", default=None, help="pinned UTC timestamp (default: now)")
    p_ledger_init.set_defaults(func=cmd_ledger_init)

    p_register = sub.add_parser("register", help="registration ceremony (freeze + append)")
    p_register.add_argument("--ledger", required=True, help="ledger root")
    p_register.add_argument("--registrar", required=True, help="ECP-REGISTRAR-… identity")
    p_register.add_argument("--case", required=True, help="public case JSON document")
    p_register.add_argument("--store", required=True, help="protected store root")
    p_register.add_argument("--system", required=True, help="system identity JSON document")
    p_register.add_argument("--evaluation-id", required=True, help="ECP-EVAL-… identifier")
    p_register.add_argument("--note", action="append", help="optional note (repeatable)")
    p_register.add_argument("--supersedes", default=None, help="prior registration_id this record replaces")
    p_register.add_argument("--at", default=None, help="pinned UTC timestamp (default: now)")
    p_register.set_defaults(func=cmd_register)

    p_invalidate = sub.add_parser("invalidate", help="append an explicit invalidation entry")
    p_invalidate.add_argument("--ledger", required=True, help="ledger root")
    p_invalidate.add_argument("--registrar", required=True, help="ECP-REGISTRAR-… identity")
    p_invalidate.add_argument("--registration-id", required=True, help="registration to invalidate")
    p_invalidate.add_argument("--reason", required=True, help="explicit invalidation reason")
    p_invalidate.add_argument("--at", default=None, help="pinned UTC timestamp (default: now)")
    p_invalidate.set_defaults(func=cmd_invalidate)

    p_ledger_verify = sub.add_parser("ledger-verify", help="public verification of the ledger")
    p_ledger_verify.add_argument("--ledger", required=True, help="ledger root")
    p_ledger_verify.add_argument("--cases", default=None, help="public cases directory for commitment cross-check")
    p_ledger_verify.set_defaults(func=cmd_ledger_verify)

    p_anchor = sub.add_parser("anchor-publish", help="publish the chain HEAD as ANCHOR.json")
    p_anchor.add_argument("--ledger", required=True, help="ledger root")
    p_anchor.add_argument("--at", default=None, help="pinned UTC timestamp (default: now)")
    p_anchor.set_defaults(func=cmd_anchor_publish)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
