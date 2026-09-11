# Provider-Neutral Execution Adapter Fabric

ECP now separates registered adapter metadata from executable runtime adapters. The provider-neutral metadata registry remains in `src/ecp/adapters.py`; the runtime dispatch seam is implemented by `RuntimeAdapterRegistry` in `src/ecp/runtime_adapters.py`. Runtime registration contains only adapter identity, provider binding, enablement, and an executable instance. It never stores credential values, authorization headers, or `SecretLease` objects.

The local gateway resolves the authorized credential through the existing `CredentialGateway`, then resolves the runtime adapter by the registered adapter identifier and provider binding. The adapter receives the scoped lease and the safe execution identifiers. It returns a normalized result, after which the gateway owns execution status, evidence generation, audit-safe records, and local persistence. Pairing, session authentication, browser request fields, and 401/403 semantics are unchanged.

## Conformance coverage

Synthetic adapters exercise the same runtime boundary with different provider identities. The existing provider-neutral target registries continue to represent multiple system kinds and keep provider identity, system identity, model/configuration identity, and adapter identity distinct. Runtime tests cover unknown or disabled adapters, provider-binding mismatch, response normalization, provider authentication failure, malformed response handling, gateway persistence, idempotency, and secret redaction.

## First provider implementation

`src/ecp/runtime_adapters.py` contains the isolated OpenAI Responses API conformance adapter. Provider-specific transport and response mapping remain inside that integration module; no OpenAI fields or transport dependencies are added to the ECP core registries or generic execution contract. `src/ecp/openai_conformance.py` wires one operational integration evaluation to the already registered OpenAI provider, adapter, system, evaluation, test, credential reference, and authorization reference.

The conformance gateway is intentionally explicit and opt-in:

```python
from ecp.console import GatewayConfig
from ecp.openai_conformance import build_openai_conformance_gateway

gateway = build_openai_conformance_gateway(
    GatewayConfig(frozenset({"http://127.0.0.1:8766"}), artifact_root=records_root),
    model="gpt-5-mini",
)
```

The credential is read from the runtime environment into the private credential test seam only for the controlled execution. It is never placed in a registry, browser payload, execution record, evidence, audit record, source file, or log. A real execution must be one-off, authorized, non-scientific, and reported only with its safe execution record. Provider reachability or credential resolution alone is not a successful execution.

## Scope boundary

This implementation demonstrates architectural extensibility and one tested provider adapter. It does not claim broad provider coverage, scientific scoring, Ground Truth access, authoring, or historical-artifact modification. The first provider is a conformance implementation, not the ECP architecture.

## Universal Experiment Execution Contract v1

`src/ecp/execution_contract.py` completes the abstraction into a single universal execution contract so ECP can address any supported provider/model through one structure — build once, configure many, normalize once, evidence once, audit once. The enforced architectural rule: **Adapter = how to reach the provider; Model = identity/configuration of the system to run.** Changing a model identifier or model configuration never requires a new adapter; only a genuinely different provider transport contract does.

The conceptual path is materialized as explicit types (it may never collapse into one request):

```text
ClientExecutionIntent
        -> Internal Resolution (ExecutionContractResolver)
        -> ResolvedUniversalExecutionRequest
        -> Existing RuntimeAdapterRegistry (the single execution registry)
        -> Provider Adapter
        -> UniversalExecutionResult
        -> Evidence
        -> Audit
```

- `ClientExecutionIntent` — the complete set of values a client may control: exactly the five authorized identifiers (`evaluation_id`, `test_id`, `system_id`, `credential_ref`, `request_id`). Arbitrary prompts, model endpoints, provider transports, ground truth, or scoring semantics are rejected loudly at this boundary.
- `ResolvedUniversalExecutionRequest` — built internally by `ExecutionContractResolver` from registered artifacts (evaluation registration, runtime adapter registration, registered case artifacts). The client cannot force resolved values. Carries the full `ExperimentIdentity`: system, provider, exact model identifier, adapter identity/version, protocol and runtime identity, configuration hash, tools/retrieval policy, and the case/prompt authority fields.
- `RegisteredCaseArtifact` — the sole prompt authority. In the scientific path the prompt is derived only from this server-side registration; the resolved request carries `case_id`, `case_artifact_hash`, and `prompt_hash`; evidence records the prompt reference, never the protected prompt text.
- `UniversalExecutionResult` — normalized execution/transport facts only (transport status, provider status, normalized output, response/execution metadata). Provider transport structures (`output`, `choices`, `candidates`) never leak into it, and scientific keys (ground truth, expected class, scores, adjudication) are structurally refused — execution is not an adjudicator. Scientific evaluation remains a separate downstream layer over Evidence.

Boundary guarantees are enforced by tests (`tests/test_execution_contract.py`, invariants A–J): model neutrality (model substitution needs no new adapter), provider neutrality (all adapters flow through the same contract), client boundary, case authority, ground-truth isolation across all three contract types, scientific separation, evidence/audit neutrality (identical schema shape across providers), adapter boundary, and historical integrity (the contract layer writes nothing).

The `LocalGateway` now executes through this contract: the HTTP payload is parsed into a `ClientExecutionIntent`, resolved internally, released through the existing credential binding/grant machinery, dispatched through the existing `RuntimeAdapterRegistry`, and normalized into a `UniversalExecutionResult` before evidence/audit generation. Evidence additionally records the contract metadata (`model`, `adapter_version`, `protocol_version`, `case_id`, `prompt_hash`, `prompt_reference`, `experiment_identity`, `experiment_identity_hash`) as flat, provider-neutral fields.
