# ECP Open-Core / Commercial Boundary

Version 0.1.0-draft (R0 foundation).

## 1. Purpose

ECP is intended to remain an **open scientific core** while allowing a
future **commercial layer** to be built around it. This document fixes
the architectural boundary so that open and commercial scope never
blur. At R0 this is *architectural separation only*.

## 2. Open scientific core (this repository)

```text
ECP specification            (spec/)
versioned schemas            (schemas/)
reference implementation     (src/ecp/: canonicalization, hashing,
                              manifests, validation, verification,
                              boundaries, linkage)
reference CLI tooling        (tools/)
public examples              (examples/)
reproducibility utilities    (verification + boundary scanning)
protocol validators          (schema validation)
documentation                (docs/)
```

Properties the core must keep, permanently: provider neutrality,
provider-specific integration excluded, no scientific case data, no
sealed ground truth, machine-checkable public/protected boundary,
deterministic hashing, Apache-2.0 license.

## 3. Future commercial layer (outside this repository)

Candidate scope, explicitly **not built and not claimed at R0**:

```text
private evaluations          hosted execution
private case vault           enterprise workspaces
advanced dashboards          API services
continuous evaluation        rotating private test suites
enterprise governance        access control
```

## 4. R0 prohibitions (enforced by this document's existence)

R0 does **not** implement: pricing, billing, customer accounts,
commercial dashboards, or any commercial claim. Nothing in this
repository may be presented as a product, a service, or a
commercially validated benchmark.

## 5. Why the boundary is architectural, not aspirational

The separation is already load-bearing in the contracts:

- the **case/ground-truth split** lets a commercial layer run private
  evaluations against private case vaults while public cases remain
  open;
- the **system identity contract** lets hosted execution be described
  exactly like local execution — same schema, different adapter;
- the **provider-neutral core** means the commercial layer owns
  integration, never the protocol;
- the **commitment mechanism** works identically for public and private
  seals.

Any future commercial layer must consume the core as-is; protocol
semantics must not fork between open and commercial variants. If a
commercial need requires protocol change, the change happens in the
open core through the normal versioned process (see
[CONTRIBUTING.md](CONTRIBUTING.md)).

## 6. Governance note

The open core is governed as a scientific artifact: changes are
versioned, tested, and publicly reviewed. Commercial layering is
permitted under the Apache-2.0 license; the name "ECP" may be used to
denote compatibility with this protocol, but commercial offerings must
not claim the protocol's scientific validation status — which, at R0,
does not exist.
