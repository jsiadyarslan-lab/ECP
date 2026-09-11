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
