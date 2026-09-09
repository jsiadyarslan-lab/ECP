# schemas/ — versioned foundation schemas

Machine-validatable [JSON Schema](https://json-schema.org/) (draft 2020-12) contracts
for the ECP foundation objects:

| Schema | Object (`ecp_object`) | Contract version | Boundary |
|---|---|---|---|
| `protocol.schema.json` | `protocol` | 0.1.0 (unchanged) | public — repository identity |
| `system.schema.json` | `system` | 0.1.0 (unchanged) | public — versioned evaluation target |
| `evaluation.schema.json` | `evaluation` | 0.1.0 (unchanged) | public — hierarchy root |
| `case.schema.json` | `case` | 0.1.0 (unchanged) | public — never contains ground truth |
| `ground-truth.schema.json` | `ground-truth` | 0.1.0 (unchanged) | **protected FORMAT only** — values never enter the public repository |
| `registration.schema.json` | `registration` | 0.1.0 (unchanged) | public record of a frozen registration |
| `execution.schema.json` | `execution` | 0.1.0 (unchanged) | public/protected by evaluation mode |
| `evidence.schema.json` | `evidence` | 0.1.0 (unchanged) | evidence bundle contract |
| `audit.schema.json` | `audit` | 0.1.0 (unchanged) | audit record contract |
| `manifest.schema.json` | `manifest` | 0.1.0 (unchanged) | deterministic artifact-set manifest |
| `ledger-entry.schema.json` | `ledger-entry` | **0.2.0 (new, R1-I)** | public — chained append-only ledger entry |
| `store-manifest.schema.json` | `store-manifest` | **0.2.0 (new, R1-I)** | protected store — deterministic index/manifest |
| `case-candidate.schema.json` | `case-candidate` | **0.3.0 (new, M3-CA0)** | review layer — canonical candidate intake (private review area only) |
| `case-review.schema.json` | `case-review` | **0.3.0 (new, M3-CA0)** | review layer — deterministic three-state review artifact |
| `review-run.schema.json` | `review-run` | **0.3.0 (new, M3-CA0)** | review layer — run manifest (determinism re-derivable) |
| `review-adjudication.schema.json` | `review-adjudication` | **0.3.0 (new, M3-CA0)** | review layer — owner decision record (the human seam) |

Notes:

- The `$id` values are **stable identifiers**, not fetchable URLs.
- The schema bundle version is pinned in the repository-root `ECP-IDENTITY.json`
  (`schema_version`). Every schema change requires a schema-version bump.
- The 0.2.0 and 0.3.0 bundles are **additive**: the ten 0.1.0 contract
  files are unchanged; the two 0.2.0 contracts (ledger-entry,
  store-manifest) implement the R1-I minimal coupled foundation (protected
  store + registration ledger, see `spec/ECP-SPEC.md` §15–§18 and
  `docs/M3-R1-ARCHITECTURE-DECISION.md`); the four 0.3.0 contracts
  (case-candidate, case-review, review-run, review-adjudication)
  implement the M3-CA0 case review pipeline (see `spec/ECP-SPEC.md` §19).
  0.1.x and 0.2.x artifacts remain valid — the explicit compatibility
  matrix is `src/ecp/versions.py`.
- There are **no provider-specific schemas** in this directory; provider/system
  integrations belong outside the protocol core (see `docs/ARCHITECTURE.md`).
- The `ground-truth` schema describes the **format** of sealed ground-truth
  documents so that public commitments can be computed and verified. Real
  ground-truth values (`content_class: "sealed"`) are never committed to this
  repository; only `content_class: "format-illustration"` documents may appear,
  and only under `examples/`. This is machine-enforced by
  `tools/ecp_cli.py boundary-scan` and the test suite.
