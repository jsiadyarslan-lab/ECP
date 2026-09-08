# ECP — Evidentiary Evaluation Protocol

**ECP PUBLIC CROSS-SYSTEM EVALUATION PLATFORM**

A public, provider-neutral foundation for **cross-system evidentiary evaluation** of AI
systems: registered cases, sealed ground truth, versioned system identity, immutable
registration, preserved execution evidence, two-auditor audit, and cryptographic
provenance — with a strict separation between **verification** (integrity) and
**scientific adjudication** (validity).

> **STATUS: R1-I — MINIMAL COUPLED FOUNDATION (infrastructure only).**
> This repository contains protocol contracts, versioned schemas,
> canonicalization/hashing, verification tooling, boundary enforcement,
> foundation tests, and — as of R1-I (schema bundle 0.2.0) — the **protected
> evidence store** and **registration ledger** machinery decided in
> [docs/M3-R1-ARCHITECTURE-DECISION.md](docs/M3-R1-ARCHITECTURE-DECISION.md)
> (Option C — minimal coupled foundation).
>
> - No evaluation case is registered (the public ledger starts **empty**).
> - No evaluated model or system has been executed.
> - No experimental result or benchmark score exists.
> - **M3 scientific validation has NOT yet been completed.**
>
> Everything herein is infrastructure. Scientific execution begins only in
> later, separately authorized phases.

---

## 1. What ECP is

ECP is a protocol — a set of versioned contracts and reference tooling — for evaluating
AI systems under explicit evidentiary discipline. Its object hierarchy is:

```
Evaluation
    └── System
         └── Case
              └── Execution
                   └── Evidence
```

Each layer is a distinct versioned object with distinct provenance: a case is not an
execution, an execution is not a result, and a result is not evidence. The protocol
binds them through:

- **Versioned protocol identity** — every artifact cites the protocol version and
  schema version it was produced under; there is no implicit "current version".
- **Versioned system identity** — an evaluation target is a full configuration
  (model, provider, API version, system prompt, agent framework, tools, retrieval,
  external services, adapter, runtime), never a bare model name.
- **Public case / protected ground-truth boundary** — public cases carry only a
  SHA-256 commitment over the canonically serialized ground-truth document; the
  ground truth itself (expected answer, derivation, verification rule) lives outside
  the public repository.
- **Immutable registration** — a registered evaluation freezes protocol version, case
  version, target version, condition, success criterion and verification rule before
  any execution, and is append-only. Since R1-I this is enforced by an actual
  **registration ledger**: an append-only, hash-chained, plain-file ledger (its own
  public repository, starting empty) with a CLI ceremony and public verification;
> corrections supersede (never edit), invalidations are explicit entries.
- **Evidence preservation** — raw outputs are preserved without post-hoc correction,
  with per-artifact hashes and manifests.
- **Audit model** — two-auditor operation by design, with an explicitly declared
  (never disguised) single-auditor fallback.
- **Deterministic provenance** — canonical JSON serialization (`ECP-CANONICAL-JSON-1.0`)
  and SHA-256 hashing defined normatively: what is hashed, and in exactly what
  representation.

## 2. What ECP is not

- **Not** a model, an agent framework, or an AI provider integration.
- **Not** a benchmark dataset, leaderboard, or scoring service.
- **Not** a completed or scientifically validated protocol (see status above).
- **Not** a JARVIS repository, submodule, benchmark directory, or evidence store.
- **Not** a place for historical experimental evidence from any system.

## 3. Relationship to evaluated systems

The scientific core of this repository is **provider-neutral**: it assumes no OpenAI,
Anthropic, Google, Ollama, JARVIS, or any other specific model, provider, framework, or
cloud. Evaluated systems — including agent platforms such as JARVIS, which may later be
one evaluated target among many — are *external* targets described by the versioned
System identity contract (`schemas/system.schema.json`). Any provider- or
system-specific adapter belongs outside the protocol core, in a future integration
layer.

## 4. Public / protected boundary

| Public (this repository) | Protected (never in this repository) |
|---|---|
| protocol specification | hidden cases |
| versioned schemas | sealed ground truth (expected answer, derivation, verification rule) |
| reference implementation & tooling | scoring commitments |
| public documentation & examples | protected evidence |
| development cases (clearly marked) | private evaluations |
| verification & reproducibility tooling | controlled execution metadata |

The public Git repository is a **provenance and distribution layer**, not the complete
scientific trust boundary. Ground truth is bound to public cases through commitments
computed over `ECP-CANONICAL-JSON-1.0`; the protected values themselves live outside
the public repository. The boundary is machine-checked:
`python tools/ecp_cli.py boundary-scan`.

## 5. Repository layout

```
ECP-IDENTITY.json      protocol identity (name/protocol/schema/repository versions)
docs/                  ARCHITECTURE, TRUST-MODEL, REPRODUCIBILITY, SECURITY, OPEN-CORE, CONTRIBUTING
spec/                  normative protocol specification (ECP-SPEC.md)
schemas/               machine-validatable JSON Schema (draft 2020-12) for all foundation objects
src/ecp/               provider-neutral reference core (identity, canonical,
                       hashing, manifest, validation, versions, verification,
                       boundaries, linkage, store, ledger)
tests/                 foundation tests (infrastructure correctness only)
examples/              format illustrations & development cases (not scientific data)
tools/                 ecp_cli.py — identity, validate, hash, manifest,
                       boundary-scan, verify-commitment, store-init, store-seal,
                       store-verify, ledger-init, register, invalidate,
                       ledger-verify, anchor-publish
cases/ evaluation/ evidence/ verification/   RESERVED — empty
```

Outside this repository (operator site, R1-I):

```
protected-store/       CAS write-once custody of sealed ground truth
                       (zones, registry manifest, hash-chained op log)
<ledger repository>   the public registration ledger (separate repository,
                       starts empty: ANCHOR.json genesis + entries/ + records/)
```

## 6. Protocol identity

Pinned at the repository root in [`ECP-IDENTITY.json`](ECP-IDENTITY.json):

| Field | Value (R1-I) |
|---|---|
| `protocol_name` | `ECP` |
| `protocol_version` | `0.2.0` |
| `protocol_status` | `draft` |
| `schema_version` | `0.2.0` |
| `repository_version` | `0.2.0` |
| `canonicalization` | `ECP-CANONICAL-JSON-1.0` |
| `hash_algorithm` | `sha256` |

Every future evaluation artifact MUST cite the protocol version (and, where defined,
the schema version) it was produced under. There are no implicit "current version"
semantics anywhere in the tooling.

## 7. Quickstart

Requirements: Python ≥ 3.10 with `jsonschema` (test dependency) and `pytest`.

```bash
# run the foundation test suite (infrastructure correctness only)
python -m pytest

# inspect protocol identity
python tools/ecp_cli.py identity

# validate a document against a foundation schema
python tools/ecp_cli.py validate --schema case --file examples/case.development.example.json

# deterministic canonical hash of a JSON document / raw file hash
python tools/ecp_cli.py hash --doc examples/ground-truth.format-example.json
python tools/ecp_cli.py hash --file examples/artifacts/raw-output.demo.txt

# build or verify a manifest
python tools/ecp_cli.py manifest build --dir examples/artifacts --out /tmp/manifest.json
python tools/ecp_cli.py manifest verify --manifest examples/manifest.example.json --root .

# enforce the public/protected boundary over the repository tree
# (optionally also scan a public ledger tree: --ledger-root <dir>)
python tools/ecp_cli.py boundary-scan

# verify the commitment binding a public case to a ground-truth document
python tools/ecp_cli.py verify-commitment --case examples/case.development.example.json \
    --ground-truth examples/ground-truth.format-example.json

# --- R1-I: protected store (CAS write-once custody) ---
python tools/ecp_cli.py store-init --root /path/to/protected-store \
    --store-id ECP-STORE-OPERATIONS-0001 --scope operational
python tools/ecp_cli.py store-seal --root /path/to/protected-store --gt gt.json
python tools/ecp_cli.py store-verify --root /path/to/protected-store

# --- R1-I: registration ledger (append-only, hash-chained) ---
python tools/ecp_cli.py ledger-init --root /path/to/ecp-ledger \
    --ledger-id ECP-LEDGER-MAIN
python tools/ecp_cli.py register --ledger /path/to/ecp-ledger \
    --registrar ECP-REGISTRAR-0001 --case case.json \
    --store /path/to/protected-store --system system.json \
    --evaluation-id ECP-EVAL-0001
python tools/ecp_cli.py ledger-verify --ledger /path/to/ecp-ledger
python tools/ecp_cli.py anchor-publish --ledger /path/to/ecp-ledger
```

The package can also be imported directly (`src/` layout):

```python
from ecp.identity import load_identity
from ecp.canonical import canonical_bytes, CANONICALIZATION_ID
from ecp.hashing import hash_document
from ecp.validate import validate_document

identity = load_identity()
issues  = validate_document(doc, "case")
digest  = hash_document(doc)
```

## 8. Documentation index

| Document | Purpose |
|---|---|
| [spec/ECP-SPEC.md](spec/ECP-SPEC.md) | Normative protocol specification (canonicalization, hashing, contracts, boundaries) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Layered architecture, object hierarchy, repository topology |
| [docs/TRUST-MODEL.md](docs/TRUST-MODEL.md) | Trust assumptions, independence model, what is never blindly trusted |
| [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) | Reproducible vs re-runnable vs auditable vs publicly inspectable |
| [docs/SECURITY.md](docs/SECURITY.md) | Threat boundary (documented at R0; implementation deferred to later gates) |
| [docs/OPEN-CORE.md](docs/OPEN-CORE.md) | Open scientific core vs future commercial layer (architectural separation only) |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Contribution rules, hard boundaries, schema versioning policy |
| [docs/M3-R1-ARCHITECTURE-DECISION.md](docs/M3-R1-ARCHITECTURE-DECISION.md) | R1 architecture decision record: Option C — minimal coupled foundation (protected store + registration ledger), threat model, rejected alternatives |

## 9. Development status & roadmap

- **R0 (closed)** — repository foundation: identity, contracts, schemas,
  canonicalization, deterministic hashing, manifests, verification boundary, audit
  boundary, public/protected boundary enforcement, foundation tests.
- **R1 (closed: discovery + decision)** — architecture decision record
  ([docs/M3-R1-ARCHITECTURE-DECISION.md](docs/M3-R1-ARCHITECTURE-DECISION.md)):
  Option C — minimal coupled foundation.
- **R1-I (this state)** — implementation of the minimal coupled foundation:
  protected store (CAS write-once, hash-chained op log, deterministic manifest),
  registration ledger (append-only chained entries, explicit supersession /
  invalidation, duplicate control), external Git anchoring, public verification
  tooling, explicit 0.1.x→0.2.0 compatibility. The public ledger exists and is
  EMPTY; no case is registered.
- **Case review pipeline / authoring / registration of real cases / execution /
  analysis (future, separately gated)** — none of these exist yet. In particular:
  no model execution, no case-review pipeline, no evidence ingestion, no audit
  workflow, no isolation enforcement, no CI, no cross-language platform.

Nothing in this repository constitutes, implies, or claims any experimental result.

## 10. License

Apache-2.0 (see [LICENSE](LICENSE)). The open scientific core is and remains
provider-neutral and free of scientific case data.
