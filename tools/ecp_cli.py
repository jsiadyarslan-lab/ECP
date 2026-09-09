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

Case review pipeline (M3-CA0 — review/eligibility gate ONLY; no execution,
no registration, no ledger writes):

  review-extract --source F --provenance F --out D
                                                 extract case-candidate records
  review-run --review-root D --run-id ID --reviewer S --at ISO
                                                 deterministic three-state review
  review-verify --review-root D                 verify artifacts, chain, determinism
  review-adjudicate --review-root D --adjudication F
                                                 install an owner decision (the seam)

Case qualification (M3-CA0-A — owner adjudication & case amendment layer;
STRICTLY before registration; still no execution, no ledger writes):

  amendment-draft ...                            STEP 1: draft a versioned case
                                                 amendment (no disclosure here)
  amendment-disclose --amendment F --value V ...  STEP 2: complete the separate
                                                 representation-bias disclosure
  review-run --review-root D ... [--prior-run-id ID --prior-run-hash H]
                                                 re-review incl. amended v2 views

Case authoring + qualification (M3-CA0 v1 — authoring/qualification gate
ONLY; no model execution, no registration, no ledger writes; the formal
ground-truth verification is deterministic computation, never a model):

  authoring-intake --source F --sidecar F --out D
                                                 extract format-2 case-candidates
                                                 (structured authoring layer)
  qualify-run --qualify-root D --run-id ID --operator S --at ISO
            [--prior-candidates D]
                                                 deterministic four-state
                                                 qualification (ACCEPT/REVISE/
                                                 REJECT/INCONCLUSIVE)
  qualify-verify --qualify-root D [--prior-candidates D]
                                                 verify artifacts, chain,
                                                 manifest and determinism

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
    if args.review_root:
        review_violations = boundaries.scan_review_tree(args.review_root)
        print(
            "REVIEW TREE "
            + (
                f"{len(review_violations)} violation(s)"
                if review_violations
                else "CLEAN — review-area boundary respected"
            )
        )
        for violation in review_violations:
            print(
                f"  [{violation['rule']}] {violation['path']}: {violation['detail']}"
            )
        exit_code = exit_code or (1 if review_violations else 0)
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
# Case review pipeline (M3-CA0 — review/eligibility gate ONLY; no execution)
# ---------------------------------------------------------------------------

def _atomic_write_bytes(path: Path, data: bytes) -> None:
    import os
    import uuid

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.tmp-{uuid.uuid4().hex}"
    try:
        with open(temp, "wb") as fh:
            fh.write(data)
        os.replace(temp, path)
    finally:
        if temp.exists():  # pragma: no cover
            temp.unlink()


def cmd_review_extract(args: argparse.Namespace) -> int:
    from ecp import candidates as candidates_mod

    sidecar = canonical.load_json(args.provenance)
    try:
        extracted, report = candidates_mod.extract_candidates(
            args.source,
            sidecar,
            source_label=args.source_label,
        )
    except candidates_mod.ExtractionError as exc:
        print(f"EXTRACTION FAILED: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out).resolve()
    candidates_dir = out_dir / "candidates"
    for candidate in extracted:
        target = candidates_dir / f"{candidate['candidate_id']}.json"
        _atomic_write_bytes(target, canonical.canonical_bytes(candidate))
    report_target = out_dir / "extraction-report.json"
    _atomic_write_bytes(
        report_target,
        json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8") + b"\n",
    )
    # retain the provenance sidecar inside the review area (self-contained;
    # review-verify and re-extraction depend on retained inputs)
    _atomic_write_bytes(
        out_dir / "source" / "source-provenance.json",
        canonical.canonical_bytes(sidecar),
    )
    print(f"EXTRACTED: {len(extracted)} candidates -> {candidates_dir}")
    print(f"source sha256: {report['source']['sha256']}")
    print(f"coverage: {report['coverage']['status']} ({report['coverage']['accounted_lines']}/{report['coverage']['total_lines']} lines accounted)")
    anomaly_cases = [a["case_id"] for a in report["per_case_anomalies"]]
    print(f"cases with recorded anomalies: {anomaly_cases if anomaly_cases else 'none'}")
    print(f"extraction report: {report_target}")
    return 0


def _load_review_root(
    review_root: Path,
) -> "tuple[list[dict], str | None, str | None, list[dict], list[dict]]":
    """Load (candidates, source_text, source_label, adjudications,
    amendments) from a review root layout."""
    candidates_dir = review_root / "candidates"
    candidates = [
        canonical.load_json(path)
        for path in sorted(candidates_dir.glob("*.json"))
    ]
    source_text = None
    source_label = None
    source_dir = review_root / "source"
    if source_dir.is_dir():
        docs = sorted(
            p for p in source_dir.iterdir()
            if p.is_file() and p.suffix in (".md", ".txt")
        )
        if len(docs) == 1:
            source_text = docs[0].read_text(encoding="utf-8")
            source_label = f"source/{docs[0].name}"
    adjudications = [
        canonical.load_json(path)
        for path in sorted((review_root / "adjudications").glob("*.json"))
    ]
    amendments = [
        canonical.load_json(path)
        for path in sorted((review_root / "amendments").glob("*.json"))
    ]
    return candidates, source_text, source_label, adjudications, amendments


def _adjudication_error():
    """Lazily import AdjudicationError (used only in exception clauses)."""
    from ecp.adjudication import AdjudicationError

    return AdjudicationError


def cmd_review_run(args: argparse.Namespace) -> int:
    from ecp import review as review_mod

    review_root = Path(args.review_root).resolve()
    candidates, source_text, source_label, adjudications, amendments = _load_review_root(review_root)
    if args.source:
        source_path = Path(args.source).resolve()
        source_text = source_path.read_text(encoding="utf-8")
        source_label = args.source_label or source_path.name
    if not candidates:
        print("error: no candidates found in review root (candidates/*.json)", file=sys.stderr)
        return 2

    lineage = None
    if getattr(args, "prior_run_id", None) or getattr(args, "prior_run_hash", None):
        if not (args.prior_run_id and args.prior_run_hash):
            print(
                "error: --prior-run-id and --prior-run-hash must be supplied together",
                file=sys.stderr,
            )
            return 2
        lineage = {
            "prior_run_id": args.prior_run_id,
            "prior_run_hash": args.prior_run_hash,
            "basis": args.lineage_basis
            or "M3-CA0-A re-review of a preserved prior run (§8: both runs retained)",
        }

    try:
        result = review_mod.run_review(
            candidates,
            run_id=args.run_id,
            reviewed_at=args.at,
            operator=args.reviewer,
            source_text=source_text,
            source_label=source_label,
            adjudications=adjudications,
            amendments=amendments,
            lineage=lineage,
        )
    except (review_mod.ReviewError, _adjudication_error()) as exc:
        print(f"REVIEW RUN FAILED: {exc}", file=sys.stderr)
        return 1

    reviews_dir = review_root / "reviews"
    for artifact in result["artifacts"]:
        target = reviews_dir / f"{artifact['review_id']}.json"
        _atomic_write_bytes(target, canonical.canonical_bytes(artifact))
    _atomic_write_bytes(
        review_root / "review-run.json",
        canonical.canonical_bytes(result["run"]),
    )
    decisions = result["run"]["decisions"]
    print(f"REVIEW RUN COMPLETE: {result['run']['run_id']}")
    print(
        f"inspected: {result['run']['input']['candidates_inspected']}  "
        f"eligible: {decisions['eligible']}  rejected: {decisions['rejected']}  "
        f"requires_review: {decisions['requires_review']}"
    )
    print(f"adjudications applied: {result['run']['adjudications']['applied']}")
    if "amendments" in result["run"]:
        applied = result["run"]["amendments"]
        print(
            f"amendments applied: {applied['applied']} "
            + (
                "(" + ", ".join(r["amendment_id"] for r in applied["records"]) + ")"
                if applied["records"]
                else ""
            )
        )
    if "lineage" in result["run"]:
        print(
            "lineage: "
            + result["run"]["lineage"]["prior_run_id"]
            + " ("
            + result["run"]["lineage"]["prior_run_hash"][:16]
            + "...)"
        )
    print(f"chain_head: {result['run']['chain_head']}")
    print(f"artifacts: {reviews_dir}")
    return 0


def cmd_review_verify(args: argparse.Namespace) -> int:
    from ecp import adjudication as adjudication_mod
    from ecp import review as review_mod

    review_root = Path(args.review_root).resolve()
    run_path = review_root / "review-run.json"
    if not run_path.is_file():
        print(f"error: no review-run.json under {review_root}", file=sys.stderr)
        return 2
    run = canonical.load_json(run_path)
    artifacts = [
        canonical.load_json(path)
        for path in sorted((review_root / "reviews").glob("*.json"))
    ]

    issues: "list[str]" = []
    for artifact in artifacts:
        issues.extend(review_mod.verify_artifact(artifact))
    issues.extend(review_mod.verify_run(run, artifacts))
    for path in sorted((review_root / "adjudications").glob("*.json")):
        issues.extend(review_mod.verify_adjudication(canonical.load_json(path)))
    for path in sorted((review_root / "amendments").glob("*.json")):
        issues.extend(adjudication_mod.verify_amendment(canonical.load_json(path)))

    # determinism re-derivation: re-run from retained inputs (under the
    # engine profile the stored run was produced with) and compare
    candidates, source_text, source_label, adjudications, amendments = _load_review_root(review_root)
    if candidates:
        stored_profile = run.get("reviewer", {}).get("engine_version")
        if stored_profile not in review_mod.ENGINE_PROFILES:
            issues.append(
                f"stored run cites unknown engine version {stored_profile!r} "
                f"(known profiles: {list(review_mod.ENGINE_PROFILES)})"
            )
        else:
            lineage = run.get("lineage")
            try:
                rederived = review_mod.run_review(
                    candidates,
                    run_id=run["run_id"],
                    reviewed_at=run["reviewed_at"],
                    operator=run["reviewer"]["operator"],
                    source_text=source_text,
                    source_label=source_label,
                    adjudications=adjudications,
                    amendments=amendments,
                    engine_profile=stored_profile,
                    lineage=lineage,
                )
            except (review_mod.ReviewError, _adjudication_error()) as exc:
                issues.append(f"re-derivation failed: {exc}")
                rederived = None
            if rederived is not None:
                for stored, fresh in zip(artifacts, rederived["artifacts"]):
                    if stored.get("artifact_hash") != fresh.get("artifact_hash"):
                        issues.append(
                            f"{stored.get('review_id', '?')}: DETERMINISM VIOLATION — "
                            "re-derivation from retained inputs produced a different "
                            "artifact hash"
                        )
                if len(artifacts) != len(rederived["artifacts"]):
                    issues.append("DETERMINISM VIOLATION — artifact count differs on re-derivation")
                if run.get("run_hash") != rederived["run"].get("run_hash"):
                    issues.append("DETERMINISM VIOLATION — run manifest hash differs on re-derivation")

    if issues:
        print(f"REVIEW VERIFICATION ISSUES ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print(
        f"REVIEW RUN INTACT: {run['run_id']} — {len(artifacts)} artifact(s), "
        "chain, hashes, cross-references and determinism re-derivation all verified"
    )
    return 0


def cmd_review_adjudicate(args: argparse.Namespace) -> int:
    from ecp import review as review_mod

    review_root = Path(args.review_root).resolve()
    adjudication = canonical.load_json(args.adjudication)
    issues = review_mod.verify_adjudication(adjudication)
    if issues:
        print(f"INVALID ADJUDICATION ({args.adjudication}):")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    adj_id = adjudication["adjudication_id"]
    target = review_root / "adjudications" / f"{adj_id}.json"
    if target.exists():
        print(f"error: adjudication {adj_id} already recorded (append-only)", file=sys.stderr)
        return 1
    _atomic_write_bytes(target, canonical.canonical_bytes(adjudication))
    print(f"ADJUDICATION RECORDED: {adj_id} -> {target}")
    print(
        "owner decision installed; re-run 'review-run' to apply it "
        "(the engine never fabricates owner decisions)"
    )
    return 0


# ---------------------------------------------------------------------------
# Case amendment (M3-CA0-A §7 — versioned case correction, two-step
# draft-then-disclose; the disclosure is NEVER completed at drafting time)
# ---------------------------------------------------------------------------

def cmd_amendment_draft(args: argparse.Namespace) -> int:
    from ecp import adjudication as adjudication_mod

    candidate = canonical.load_json(args.candidate)
    if getattr(args, "disclosure_value", None):
        print(
            "error: the representation-bias disclosure is completed in a "
            "SEPARATE later step ('amendment-disclose'), never at drafting "
            "time (M3-CA0-A §7 amended)",
            file=sys.stderr,
        )
        return 2
    try:
        drafted = adjudication_mod.draft_case_amendment(
            candidate,
            amendment_id=args.amendment_id,
            order_basis=args.order_basis,
            defect_code=args.defect_code,
            defect_description=args.defect_description,
            defect_why=args.defect_why,
            defect_evidence=args.defect_evidence,
            retained_answer_block=args.retained_answer_block,
            retained_derivation_block=args.retained_derivation_block,
            removed_answer_blocks=[
                int(v) for v in str(args.removed_answer_blocks).split(",") if v.strip()
            ],
            removed_derivation_blocks=[
                int(v)
                for v in str(args.removed_derivation_blocks).split(",")
                if v.strip()
            ],
            not_outcome_statement=args.not_outcome_statement,
            not_outcome_basis=args.not_outcome_basis,
            amendment_author=args.amendment_author,
            drafted_at=args.drafted_at,
            operator=args.operator,
            order_reference=args.order_reference,
        )
    except adjudication_mod.AdjudicationError as exc:
        print(f"AMENDMENT DRAFT FAILED: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out).resolve() if args.out else Path(args.review_root).resolve() / "amendments"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{drafted['amendment_id']}.json"
    if target.exists():
        print(
            f"error: amendment {drafted['amendment_id']} already exists "
            "(append-only; never rewritten)",
            file=sys.stderr,
        )
        return 1
    _atomic_write_bytes(target, canonical.canonical_bytes(drafted))
    print(f"AMENDMENT DRAFTED (STEP 1 — disclosure PENDING): {drafted['amendment_id']} -> {target}")
    print(f"prior content: {drafted['prior']['content_hash'][:16]}...")
    print(f"new content:   {drafted['new']['content_hash'][:16]}... (case_version 2)")
    print(
        "NEXT (separate step): complete the representation-bias disclosure "
        "with 'amendment-disclose' — only then can the amendment be applied "
        "in a review run"
    )
    return 0


def cmd_amendment_disclose(args: argparse.Namespace) -> int:
    from ecp import adjudication as adjudication_mod

    drafted = canonical.load_json(args.amendment)
    try:
        completed = adjudication_mod.complete_disclosure(
            drafted,
            value=args.value,
            completed_by=args.completed_by,
            completed_at=args.completed_at,
            basis=args.basis,
        )
    except adjudication_mod.AdjudicationError as exc:
        print(f"AMENDMENT DISCLOSURE FAILED: {exc}", file=sys.stderr)
        return 1

    target = Path(args.amendment).resolve()
    _atomic_write_bytes(target, canonical.canonical_bytes(completed))
    print(f"AMENDMENT DISCLOSURE COMPLETED (STEP 2): {completed['amendment_id']} -> {target}")
    print(f"disclosure value: {completed['representation_bias_disclosure']['value']}")
    print(
        "disclosed against draft_hash "
        + completed["representation_bias_disclosure"]["disclosed_against_draft_hash"][:16]
        + "... (machine evidence: disclosure completed AFTER drafting)"
    )
    if completed["representation_bias_disclosure"]["value"] in ("POSSIBLE", "KNOWN"):
        print(
            "note: this amendment is and remains traceable to a "
            f"{completed['representation_bias_disclosure']['value']} "
            "disclosure — it is never silently treated as unbiased"
        )
    return 0


# ---------------------------------------------------------------------------
# Authoring + qualification pipeline (M3-CA0 v1 — authoring/qualification
# gate ONLY; no model execution, no registration, no ledger writes)
# ---------------------------------------------------------------------------

def cmd_authoring_intake(args: argparse.Namespace) -> int:
    from ecp import authoring as authoring_mod

    source = Path(args.source).resolve()
    sidecar = canonical.load_json(args.sidecar)
    try:
        candidates, report = authoring_mod.extract_candidates_v2(
            source,
            sidecar,
            source_label=args.source_label,
            candidate_offset=args.candidate_offset,
        )
    except authoring_mod.ExtractionError as exc:
        print(f"AUTHORING INTAKE FAILED: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out).resolve()
    candidates_dir = out_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    for candidate in candidates:
        target = candidates_dir / f"{candidate['candidate_id']}.json"
        _atomic_write_bytes(target, canonical.canonical_bytes(candidate))
    report_path = out_dir / "intake-report.json"
    _atomic_write_bytes(report_path, canonical.canonical_bytes(report))

    print(f"AUTHORING INTAKE COMPLETE: {len(candidates)} candidates -> {candidates_dir}")
    if report["per_case_anomalies"]:
        print(
            f"per-case anomalies recorded: {len(report['per_case_anomalies'])} "
            "(retained verbatim, never silently resolved)"
        )
    print(f"intake report: {report_path}")
    return 0


def _load_prior_population(prior_candidates: "str | None") -> "list[dict]":
    if not prior_candidates:
        return []
    prior_dir = Path(prior_candidates).resolve()
    return [
        canonical.load_json(path)
        for path in sorted(prior_dir.glob("ECP-CAND-*.json"))
    ]


def cmd_qualify_run(args: argparse.Namespace) -> int:
    from ecp import qualification as qualification_mod

    qualify_root = Path(args.qualify_root).resolve()
    candidates_dir = qualify_root / "candidates"
    candidates = [
        canonical.load_json(path)
        for path in sorted(candidates_dir.glob("*.json"))
    ]
    if not candidates:
        print(f"error: no candidates under {candidates_dir}", file=sys.stderr)
        return 2
    prior_population = _load_prior_population(args.prior_candidates)

    source_label, source_sha = None, None
    intake_report_path = qualify_root / "intake-report.json"
    if intake_report_path.is_file():
        intake_report = canonical.load_json(intake_report_path)
        source_label = intake_report.get("source", {}).get("label")
        source_sha = intake_report.get("source", {}).get("sha256")

    try:
        result = qualification_mod.run_qualification(
            candidates,
            run_id=args.run_id,
            qualified_at=args.at,
            operator=args.operator,
            prior_population=prior_population,
            source_label=source_label,
            source_sha=source_sha,
        )
    except qualification_mod.QualificationError as exc:
        print(f"QUALIFICATION RUN FAILED (loud, no silent states): {exc}", file=sys.stderr)
        return 1

    qualification_dir = qualify_root / "qualification"
    qualification_dir.mkdir(parents=True, exist_ok=True)
    for artifact in result["artifacts"]:
        target = qualification_dir / f"{artifact['qualification_id']}.json"
        _atomic_write_bytes(target, canonical.canonical_bytes(artifact))
    run_path = qualify_root / "qualification-run.json"
    _atomic_write_bytes(run_path, canonical.canonical_bytes(result["run"]))

    tallies = result["run"]["decisions"]
    print(f"QUALIFICATION RUN COMPLETE: {result['run']['run_id']}")
    print(
        "decisions: "
        f"ACCEPT={tallies['accept']} REVISE={tallies['revise']} "
        f"REJECT={tallies['reject']} INCONCLUSIVE={tallies['inconclusive']} "
        f"(of {len(result['artifacts'])} candidates)"
    )
    print(f"artifacts: {qualification_dir}")
    print(f"run manifest: {run_path}")
    print("boundary: QUALIFIED-POOL-ONLY — NOT REGISTERED (order §14)")
    return 0


def cmd_qualify_verify(args: argparse.Namespace) -> int:
    from ecp import qualification as qualification_mod

    qualify_root = Path(args.qualify_root).resolve()
    run_path = qualify_root / "qualification-run.json"
    if not run_path.is_file():
        print(f"error: no qualification-run.json under {qualify_root}", file=sys.stderr)
        return 2
    run = canonical.load_json(run_path)
    artifacts = [
        canonical.load_json(path)
        for path in sorted((qualify_root / "qualification").glob("*.json"))
    ]

    issues: "list[str]" = []
    for artifact in artifacts:
        issues.extend(qualification_mod.verify_artifact(artifact))
    issues.extend(qualification_mod.verify_run(run, artifacts))

    # determinism re-derivation: re-run from retained inputs (stored metadata)
    candidates_dir = qualify_root / "candidates"
    candidates = [
        canonical.load_json(path)
        for path in sorted(candidates_dir.glob("*.json"))
    ]
    if candidates:
        prior_population = _load_prior_population(args.prior_candidates)
        stored_prior = run.get("prior_population", {})
        if stored_prior.get("count", 0) > 0 and not prior_population:
            issues.append(
                "re-derivation skipped: the stored run used a prior population but "
                "--prior-candidates was not supplied"
            )
        else:
            try:
                rederived = qualification_mod.run_qualification(
                    candidates,
                    run_id=run["run_id"],
                    qualified_at=run["qualified_at"],
                    operator=run["operator"],
                    prior_population=prior_population,
                    source_label=run.get("source", {}).get("label"),
                    source_sha=run.get("source", {}).get("sha256"),
                )
            except qualification_mod.QualificationError as exc:
                issues.append(f"re-derivation failed: {exc}")
                rederived = None
            if rederived is not None:
                for stored, fresh in zip(artifacts, rederived["artifacts"]):
                    if stored.get("artifact_hash") != fresh.get("artifact_hash"):
                        issues.append(
                            f"{stored.get('qualification_id', '?')}: DETERMINISM VIOLATION — "
                            "re-derivation from retained inputs produced a different "
                            "artifact hash"
                        )
                if len(artifacts) != len(rederived["artifacts"]):
                    issues.append("DETERMINISM VIOLATION — artifact count differs on re-derivation")
                if run.get("run_hash") != rederived["run"].get("run_hash"):
                    issues.append("DETERMINISM VIOLATION — run manifest hash differs on re-derivation")

    if issues:
        print(f"QUALIFICATION VERIFICATION ISSUES ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print(
        f"QUALIFICATION RUN INTACT: {run['run_id']} — {len(artifacts)} artifact(s), "
        "chain, hashes, cross-references and determinism re-derivation all verified"
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
    p_scan.add_argument(
        "--review-root",
        help="additionally scan a private review-area tree for review-layer "
        "boundary rules (M3-CA0)",
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

    # --- case review pipeline (M3-CA0) ---
    p_extract = sub.add_parser("review-extract", help="extract case candidates from a source case-set document")
    p_extract.add_argument("--source", required=True, help="source candidate case-set document (markdown)")
    p_extract.add_argument("--provenance", required=True, help="provenance sidecar JSON (operator-transcribed source provenance)")
    p_extract.add_argument("--out", required=True, help="review root directory (candidates/ is created inside)")
    p_extract.add_argument("--source-label", default=None, help="label recorded for the source document")
    p_extract.set_defaults(func=cmd_review_extract)

    p_review_run = sub.add_parser("review-run", help="run the deterministic case review (three-state decisions)")
    p_review_run.add_argument("--review-root", required=True, help="review root directory (candidates/, source/, adjudications/)")
    p_review_run.add_argument("--run-id", required=True, help="ECP-REVRUN-… run identifier")
    p_review_run.add_argument("--reviewer", required=True, help="operator identity recorded on the run")
    p_review_run.add_argument("--at", required=True, help="explicit UTC review timestamp (determinism: no wall clock)")
    p_review_run.add_argument("--source", default=None, help="override source document path")
    p_review_run.add_argument("--source-label", default=None, help="override source label")
    p_review_run.add_argument("--prior-run-id", default=None, help="prior preserved run id (lineage, M3-CA0-A §8)")
    p_review_run.add_argument("--prior-run-hash", default=None, help="prior preserved run_hash (lineage, M3-CA0-A §8)")
    p_review_run.add_argument("--lineage-basis", default=None, help="basis recorded in the lineage block")
    p_review_run.set_defaults(func=cmd_review_run)

    p_review_verify = sub.add_parser("review-verify", help="verify review artifacts, chain, manifest and determinism")
    p_review_verify.add_argument("--review-root", required=True, help="review root directory")
    p_review_verify.set_defaults(func=cmd_review_verify)

    p_adj = sub.add_parser("review-adjudicate", help="install an owner adjudication record (the human review seam)")
    p_adj.add_argument("--review-root", required=True, help="review root directory")
    p_adj.add_argument("--adjudication", required=True, help="review-adjudication JSON document")
    p_adj.set_defaults(func=cmd_review_adjudicate)

    p_amd_draft = sub.add_parser(
        "amendment-draft",
        help="STEP 1: draft a versioned case amendment (representation-bias disclosure NOT completed here)",
    )
    p_amd_draft.add_argument("--candidate", required=True, help="case-candidate JSON document (the v1 record)")
    p_amd_draft.add_argument("--amendment-id", required=True, help="ECP-AMD-NNNNNN identifier")
    p_amd_draft.add_argument("--order-basis", required=True, help="the owner order clause authorizing this amendment")
    p_amd_draft.add_argument("--defect-code", required=True, help="defect code (e.g. SPEC-DUPLICATE-GT)")
    p_amd_draft.add_argument("--defect-description", required=True, help="exact defect description")
    p_amd_draft.add_argument("--defect-why", required=True, help="why this is a defect")
    p_amd_draft.add_argument("--defect-evidence", required=True, help="preserved evidence for the defect")
    p_amd_draft.add_argument("--retained-answer-block", required=True, type=int, help="1-based source_block index of the retained answer block")
    p_amd_draft.add_argument("--retained-derivation-block", required=True, type=int, help="1-based source_block index of the retained derivation block")
    p_amd_draft.add_argument("--removed-answer-blocks", required=True, help="comma-separated defective answer block indices")
    p_amd_draft.add_argument("--removed-derivation-blocks", required=True, help="comma-separated defective derivation block indices")
    p_amd_draft.add_argument("--not-outcome-statement", required=True, help="stated reason the change is not outcome-dependent")
    p_amd_draft.add_argument("--not-outcome-basis", required=True, help="basis for the not-outcome-dependent statement")
    p_amd_draft.add_argument("--amendment-author", required=True, help="identity of the amendment author")
    p_amd_draft.add_argument("--drafted-at", required=True, help="explicit UTC draft timestamp (determinism)")
    p_amd_draft.add_argument("--operator", required=True, help="operator identity recording the amendment")
    p_amd_draft.add_argument("--order-reference", required=True, help="the authorizing execution order reference")
    p_amd_draft.add_argument("--review-root", default=None, help="review root (amendments/ created inside; default)")
    p_amd_draft.add_argument("--out", default=None, help="explicit output directory for the amendment record")
    p_amd_draft.set_defaults(func=cmd_amendment_draft)

    p_amd_disclose = sub.add_parser(
        "amendment-disclose",
        help="STEP 2: complete the SEPARATE representation-bias disclosure on an existing draft",
    )
    p_amd_disclose.add_argument("--amendment", required=True, help="drafted case-amendment JSON (disclosure PENDING)")
    p_amd_disclose.add_argument("--value", required=True, choices=["NONE", "POSSIBLE", "KNOWN"], help="disclosure value (audit field, never an eligibility decision)")
    p_amd_disclose.add_argument("--completed-by", required=True, help="identity completing the disclosure")
    p_amd_disclose.add_argument("--completed-at", required=True, help="explicit UTC disclosure timestamp (after drafting)")
    p_amd_disclose.add_argument("--basis", required=True, help="honest disclosure basis (knowledge state, influence surface)")
    p_amd_disclose.set_defaults(func=cmd_amendment_disclose)

    # --- case authoring + qualification pipeline (M3-CA0 v1) ---
    p_intake = sub.add_parser(
        "authoring-intake",
        help="extract format-2 case candidates from an authored case-set document (structured authoring layer)",
    )
    p_intake.add_argument("--source", required=True, help="authored candidate case-set document (format M3-CA0V1-case-set-md-2)")
    p_intake.add_argument("--sidecar", required=True, help="provenance sidecar JSON (order §3 authoring-independence record)")
    p_intake.add_argument("--out", required=True, help="qualification root directory (candidates/ + intake-report.json are created inside)")
    p_intake.add_argument("--source-label", default=None, help="label recorded for the source document")
    p_intake.add_argument("--candidate-offset", type=int, default=100, help="numeric offset for ECP-CAND ids (default 100 => ECP-CAND-000101+)")
    p_intake.set_defaults(func=cmd_authoring_intake)

    p_qualify_run = sub.add_parser(
        "qualify-run",
        help="run the deterministic four-state qualification (ACCEPT/REVISE/REJECT/INCONCLUSIVE)",
    )
    p_qualify_run.add_argument("--qualify-root", required=True, help="qualification root directory (candidates/, qualification/)")
    p_qualify_run.add_argument("--run-id", required=True, help="ECP-QUALRUN-… run identifier")
    p_qualify_run.add_argument("--operator", required=True, help="operator identity recorded on the run")
    p_qualify_run.add_argument("--at", required=True, help="explicit UTC qualification timestamp (determinism: no wall clock)")
    p_qualify_run.add_argument("--prior-candidates", default=None, help="prior-pool candidates directory for cross-population novelty (read-only)")
    p_qualify_run.set_defaults(func=cmd_qualify_run)

    p_qualify_verify = sub.add_parser(
        "qualify-verify",
        help="verify qualification artifacts, chain, manifest and determinism re-derivation",
    )
    p_qualify_verify.add_argument("--qualify-root", required=True, help="qualification root directory")
    p_qualify_verify.add_argument("--prior-candidates", default=None, help="prior-pool candidates directory (required when the stored run used one)")
    p_qualify_verify.set_defaults(func=cmd_qualify_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
