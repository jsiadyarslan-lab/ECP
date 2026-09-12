# Universal Target Onboarding Fabric v1

Owner order 2026-09-12 — `UNIVERSAL TARGET ONBOARDING & PROVIDER-NEUTRAL
EVALUATION FABRIC v1`. Phase: `IMPLEMENTATION + VERIFICATION`. Real external
provider calls: `FORBIDDEN` in this phase (all verification is offline,
local, mock/fixture based).

Governing principle:

> Build the onboarding mechanism once → configure/register Targets → reuse
> the existing universal execution fabric.

## What existed already (and is reused, unchanged)

| Fabric element | Existing implementation (reused) |
|---|---|
| Provider Registry | `ecp.targets.ProviderRegistry` + `provider_document()` + `schemas/provider.schema.json` |
| Target Registry / Universal Target Contract | `ecp.targets.TargetRegistry` + `target_hash()` + `schemas/target.schema.json` (the target document IS the universal target representation) |
| Adapter metadata Registry | `ecp.adapters.AdapterRegistry` + `schemas/adapter.schema.json` |
| Compatibility resolution + identity freeze | `ecp.adapters.TargetResolver` → frozen `ResolvedTarget` (exact provider/interface/adapter/system-kind/capability identity, binding-scoped via `resolve_for_binding`) |
| Runtime dispatch seam (single execution registry) | `ecp.runtime_adapters.RuntimeAdapterRegistry` + the provider adapters behind it |
| Universal Execution Contract | `ecp.execution_contract` — `ClientExecutionIntent` → `ExecutionContractResolver` → `ResolvedUniversalExecutionRequest` → `UniversalExecutionResult`, with the frozen `ExperimentIdentity` |
| Execution Runner / Evidence Writer / Audit Writer | `ecp.console.LocalGateway` (single universal path: intent → resolve → lease → adapter → universal result → evidence → audit → local persistence) |
| Credential Gateway / Credential Ref / binding / grant / scoped release | `ecp.credentials.CredentialGateway` + `ecp.credential_binding` |
| Evaluation Registry / Test Registry (console catalog source) | `ecp.console.AuthorizedEvaluation` / `AuthorizedTest` |
| Evaluation Console | `console/` static UI + `/api/v1/catalog` (already registry-driven; no model list, no rewrite needed) |

## What this phase adds (the minimal extension)

Exactly one new composition layer plus its contract, launcher, example and
tests — **no parallel contract, no parallel registry, no parallel runner, no
parallel identity, credential, evidence or audit system**:

* `src/ecp/onboarding.py` — `TargetOnboardingService`: the onboarding
  pipeline that composes the existing fabric listed above. Pipeline (owner
  order §9): validation → provider resolution → target registration
  (idempotent by canonical `target_hash`) → adapter + binding resolution
  (existing `TargetResolver`) → runtime adapter resolution (strict identity,
  idempotent) → credential resolution (gateway metadata only) →
  authorization resolution (owner-supplied grant, diagnostics only) →
  execution readiness (nine checks, offline probe through the real
  `ExecutionContractResolver`) → infrastructure registration
  (`AuthorizedEvaluation` linkage) → persisted target record.
* `schemas/onboarding-record.schema.json` (+ registration in
  `ecp.validate` and `ecp.versions` as an 0.8.0-bundle contract) — the
  deterministic onboarding record: references and readiness verdicts only,
  byte-identical for identical configurations.
* `run_console.py` — the ONE configuration-driven console entry. Serves the
  existing console UI and the existing gateway endpoint; onboards all
  declared targets from a JSON configuration. Built-in adapter kinds only
  (`offline-mock`, `openai-responses`, `gemini-generate-content`,
  `openrouter-chat-completions`): a configuration can never import arbitrary
  modules or classes. The shipped default is a fully OFFLINE demo; real
  provider kinds fail closed without their environment credential and are
  reserved for the separately authorized real external evaluation phase.
* `examples/onboarding.example.json` — format illustration with real,
  recomputable hashes (verified by the test suite).
* `tests/test_onboarding.py` — the full owner-order test matrix (A/B/C/D,
  provider neutrality, security, launcher).

## Architectural invariants (locked by tests)

* **New Target = configuration/registry entry + existing provider adapter.**
  A new model on an existing provider is a new target document + a new
  adapter metadata entry + a configured runtime adapter instance — zero core
  code. A new provider additionally needs one adapter implementation behind
  the universal adapter contract. There is no per-model or per-provider
  conditional routing anywhere in the universal core seam
  (`targets/adapters/execution_contract/console/credentials/
  credential_binding/onboarding`); the neutrality tests scan the module
  sources and the `RuntimeAdapterRegistry` seam directly.
* **Idempotency.** Re-onboarding the same configuration produces the same
  canonical identity, the same registrations, the same linkage and a
  byte-identical record; divergent re-registration under any occupied
  identity is a deterministic failure (the §7 freeze: no model switching, no
  silent adapter substitution).
* **Authorization is never bypassed.** The `AuthorizationGrant` is an
  owner-supplied input; the service performs diagnostics only
  (`OWNER DECISION REQUIRED` when missing) and the material-release
  authority remains `CredentialGateway.release`. Readiness re-checks detect
  drift (revoked credential, expired grant) and execution then fails closed.
* **Secret-free surfaces.** Target configurations and records are scanned
  for secret-bearing keys and rejected; credential values never enter any
  registry, record, catalog, evidence, audit or error message (verified by
  scanning every persisted surface in the tests).
* **Client boundary.** The client of the execution path still controls
  exactly the five authorized identifiers; injection of endpoints, prompts
  or provider transports is rejected loudly by the existing contract.

## Readiness battery (owner order §14)

`provider_available`, `adapter_metadata_available`,
`runtime_adapter_available`, `model_identified`, `credential_resolved`,
`authorization_valid`, `interface_valid`, `execution_contract_valid`,
`test_available` → `READY` / `NOT_READY` with a diagnostic reason per failed
check. `TargetOnboardingService.readiness(target_id)` re-runs the battery
read-only for drift detection.

## Usage

```python
from ecp.onboarding import TargetOnboardingService

service = TargetOnboardingService(providers, targets, adapters,
                                   runtime, credential_gateway)
service.register_provider_integration(provider_doc, adapter_doc)
onboarded = service.onboard(
    target_document,
    runtime_adapter=configured_adapter_instance,   # exact model identifier
    credential_identity=credential_identity,
    binding=binding,                               # owner-wired
    grant=grant,                                   # owner decision
    tests={test.test_id: test for test in authorized_tests},
)
gateway = LocalGateway(config, service.evaluations, credential_gateway,
                       runtime)
```

Console (offline demo):

```bash
python run_console.py                 # built-in offline configuration
python run_console.py --config my-onboarding-config.json
```

## Scope boundary

This phase is infrastructure only. It changes no scientific cases, no
Ground Truth, no historical outcomes or registrations, no M1/M2/T1 records,
no manuscript or ICLR artifacts. Real external evaluation against a real
provider is a separate, explicitly authorized phase after this one.
