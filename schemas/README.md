# schemas/ — versioned foundation schemas

Machine-validatable [JSON Schema](https://json-schema.org/) (draft 2020-12) contracts
for the ECP foundation objects:

| Schema | Object (`ecp_object`) | Boundary |
|---|---|---|
| `protocol.schema.json` | `protocol` | public — repository identity |
| `system.schema.json` | `system` | public — versioned evaluation target |
| `evaluation.schema.json` | `evaluation` | public — hierarchy root |
| `case.schema.json` | `case` | public — never contains ground truth |
| `ground-truth.schema.json` | `ground-truth` | **protected FORMAT only** — values never enter the public repository |
| `registration.schema.json` | `registration` | public record of a frozen registration |
| `execution.schema.json` | `execution` | public/protected by evaluation mode |
| `evidence.schema.json` | `evidence` | evidence bundle contract |
| `audit.schema.json` | `audit` | audit record contract |
| `manifest.schema.json` | `manifest` | deterministic artifact-set manifest |

Notes:

- The `$id` values are **stable identifiers**, not fetchable URLs.
- The schema bundle version is pinned in the repository-root `ECP-IDENTITY.json`
  (`schema_version`). Every schema change requires a schema-version bump.
- There are **no provider-specific schemas** in this directory; provider/system
  integrations belong outside the protocol core (see `docs/ARCHITECTURE.md`).
- The `ground-truth` schema describes the **format** of sealed ground-truth
  documents so that public commitments can be computed and verified. Real
  ground-truth values (`content_class: "sealed"`) are never committed to this
  repository; only `content_class: "format-illustration"` documents may appear,
  and only under `examples/`. This is machine-enforced by
  `tools/ecp_cli.py boundary-scan` and the test suite.
