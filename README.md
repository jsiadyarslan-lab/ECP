# ECP — Evidentiary Evaluation Protocol

**ECP PUBLIC CROSS-SYSTEM EVALUATION PLATFORM**

A public, provider-neutral foundation for **cross-system evidentiary evaluation** of AI
systems: registered cases, sealed ground truth, versioned system identity, immutable
registration, preserved execution evidence, two-auditor audit, and cryptographic
provenance — with a strict separation between **verification** (integrity) and
**scientific adjudication** (validity).

> **STATUS: R0 — REPOSITORY FOUNDATION.**
> This repository currently contains protocol contracts, versioned schemas,
> canonicalization/hashing, verification tooling, boundary enforcement and foundation
> tests **only**.
>
> - No evaluation case is registered.
> - No evaluated model or system has been executed.
> - No experimental result or benchmark score exists.
> - **M3 scientific validation has NOT yet been completed.**
>
> Everything herein is infrastructure. Scientific execution begins only in later,
> separately authorized phases.

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
  any execution, and is append-only.
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
src/ecp/               provider-neutral reference core (identity, canonical, hashing,
                       manifest, validation, verification, boundaries, linkage)
tests/                 foundation tests (infrastructure correctness only)
examples/              format illustrations & development cases (not scientific data)
tools/                 ecp_cli.py — identity, validate, hash, manifest, boundary-scan, verify-commitment
cases/                 RESERVED — empty at R0
evaluation/            RESERVED — empty at R0
evidence/              RESERVED — empty at R0
verification/          RESERVED — empty at R0
```

## 6. Protocol identity

Pinned at the repository root in [`ECP-IDENTITY.json`](ECP-IDENTITY.json):

| Field | Value (R0) |
|---|---|
| `protocol_name` | `ECP` |
| `protocol_version` | `0.1.0` |
| `protocol_status` | `draft` |
| `schema_version` | `0.1.0` |
| `repository_version` | `0.1.0` |
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
python tools/ecp_cli.py boundary-scan

# verify the commitment binding a public case to a ground-truth document
python tools/ecp_cli.py verify-commitment --case examples/case.development.example.json \
    --ground-truth examples/ground-truth.format-example.json
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

## 9. Development status & roadmap

- **R0 (this state)** — repository foundation: identity, contracts, schemas,
  canonicalization, deterministic hashing, manifests, verification boundary, audit
  boundary, public/protected boundary enforcement, foundation tests.
- **R1 (future, separately gated)** — repository architecture deepening and core
  implementation as revealed by R0.
- **Case authoring / registration / execution / analysis (future, separately gated)** —
  independent external case authoring, case registration, model execution, evidence
  collection, audit and classification. None of these exist in this repository.

Nothing in this repository constitutes, implies, or claims any experimental result.

## 10. License

Apache-2.0 (see [LICENSE](LICENSE)). The open scientific core is and remains
provider-neutral and free of scientific case data.
