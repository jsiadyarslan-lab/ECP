# Contributing to ECP

Version 0.1.0-draft (R0 foundation).

## 1. What contributions are in scope

This repository is a **protocol foundation**. In-scope contributions:

- corrections and clarifications to `spec/ECP-SPEC.md`;
- schema changes (with version bumps — see §3);
- improvements to the reference core (`src/ecp/`): canonicalization,
  hashing, manifests, validation, verification, boundaries, linkage;
- tests — especially determinism, boundary-enforcement and
  invalid-rejection cases;
- documentation improvements;
- tooling (`tools/ecp_cli.py`).

## 2. Hard boundaries (contribution red lines)

A contribution MUST NOT:

1. add ground-truth content (`expected_answer`, `derivation`, or any
   `content_class: "sealed"` document) anywhere in the tree — the
   boundary scanner rejects it and so will review;
2. add real case data, execution records, evidence, scores, or any
   scientific result — none exist yet and none may be introduced
   through a PR;
3. couple the core to a specific model, provider, API, agent framework
   or cloud — provider-specific integration belongs outside the core;
4. weaken strictness (`additionalProperties: false` is a design
   decision, not an inconvenience);
5. claim or imply scientific validation of the protocol.

## 3. Versioning policy

- Any schema change requires a `schema_version` bump in
  `ECP-IDENTITY.json` (and in the changed schema's `$id` namespace).
- Any change to canonicalization or hashing rules requires a
  `protocol_version` bump — and is a major event: it invalidates every
  existing commitment by definition (see spec §14).
- Update the affected tests in the same change; the suite must pass
  with zero failures before merge.

## 4. Process

1. Open an issue describing the defect or proposal (spec section,
   schema, module).
2. Proposals that change contract semantics get a short written
   rationale in the issue: what breaks, what migrates.
3. Submit a change that: states which § of the spec it touches; updates
   spec + schema + tests together; keeps diffs minimal.
4. Review checks, in order: boundary scanner clean → tests green →
   schema strictness preserved → spec/test agreement.

## 5. Development setup

```bash
python -m pytest                    # full foundation suite
python tools/ecp_cli.py boundary-scan
python tools/ecp_cli.py validate --schema case --file examples/case.development.example.json
```

Requirements: Python ≥ 3.10, `jsonschema` ≥ 4.18, `pytest`.

## 6. License

Contributions are licensed under Apache-2.0 (see [LICENSE](../LICENSE)).
By submitting a contribution you agree it is licensed under those terms.
