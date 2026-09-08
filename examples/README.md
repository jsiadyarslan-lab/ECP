# examples/ — format illustrations and development cases

Everything in this directory is a **format illustration**. Nothing here is:

- a registered case;
- benchmark data;
- a real execution record;
- real evidence;
- protected ground truth.

The ground-truth example (`ground-truth.format-example.json`) uses public dummy
values and is explicitly marked `content_class: "format-illustration"`. Real sealed
ground truth (`content_class: "sealed"`) never enters the public repository; public
cases bind to it through SHA-256 commitments over `ECP-CANONICAL-JSON-1.0`
(see `spec/ECP-SPEC.md`).

All JSON documents in this directory validate against the schemas in `schemas/` and
all embedded hashes/commitments are real (recomputed and verified by the test suite):

| File | Schema | Illustrates |
|---|---|---|
| `case.development.example.json` | `case` | a public development case with a ground-truth commitment |
| `ground-truth.format-example.json` | `ground-truth` | the protected format (dummy values) behind the commitment |
| `system.model-only.example.json` | `system` | model-only target identity |
| `system.complete-system.example.json` | `system` | complete-system target identity |
| `evaluation.example.json` | `evaluation` | a defined (not registered) evaluation |
| `registration.example.json` | `registration` | a frozen registration record with its hash |
| `execution.example.json` | `execution` | an execution record (simulated, clearly marked) |
| `evidence.example.json` | `evidence` | an evidence bundle with per-artifact hashes |
| `manifest.example.json` | `manifest` | the evidence-bundle manifest |
| `audit.two-auditor.example.json` | `audit` | the default two-auditor record |
| `audit.single-auditor-fallback.example.json` | `audit` | the honest single-auditor fallback declaration |
| `ledger-entry.example.json` | `ledger-entry` (0.2.0) | a genesis chained ledger entry wrapping the registration example (real record_hash, real frozen commitment) |
| `store-manifest.example.json` | `store-manifest` (0.2.0) | the manifest of an empty development store (byte-identical to a fresh `store-init` with pinned arguments) |
| `artifacts/raw-output.demo.txt` | — | simulated raw output artifact (hashed) |
| `artifacts/execution-trace.demo.txt` | — | simulated execution trace artifact (hashed) |

The two 0.2.0 examples (R1-I) are format illustrations of the registration
ledger and the protected store. No ledger exists in this repository and no
store exists here either: the public ledger lives in its own repository
(starting empty, per the R1-I decision), and real protected stores live
outside any public repository. Their hashes are real and recompute via the
same tooling (`tools/ecp_cli.py validate`, and the test suite).
