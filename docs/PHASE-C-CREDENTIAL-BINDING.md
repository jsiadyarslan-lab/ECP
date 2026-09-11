# Phase C — Credential Binding Architecture v1

Phase C establishes a **control-plane credential boundary** over the existing ECP gateway. It does not implement a production secret store, provider integration, OAuth, Vault, rotation service, distributed revocation, or runtime execution bridge.

## Contract separation

ECP now distinguishes the following non-secret objects:

| Object | Meaning | Contains material? |
|---|---|---:|
| `CredentialDefinition` | Provider/interface/access-mechanism definition for a purpose | No |
| `CredentialRequirement` | A Target-specific requirement for that definition | No |
| `CredentialBinding` | Explicit relationship between requirement, Target, provider/interface, purpose, scope, and `credential_ref` | No |
| `AuthorizationGrant` | Explicit authorization decision bound to one binding and Target | No |
| `ScopedReleaseRequest` | A bounded request for a future controlled release | No |
| `SecretLease` | Existing in-memory release object used only after all checks | Contains material in memory only |

`credential_ref` is an opaque non-secret identity. It is not an API key, environment variable name, reversible encoding, authentication value, or provider secret.

## Only material-release path

The former unscoped call:

```text
credential_id + requested_scope → material
```

is closed. `CredentialGateway.retrieve()` now fails closed and directs callers to the only valid path:

```text
ScopedReleaseRequest
        +
CredentialBinding
        +
AuthorizationGrant
        ↓
CredentialGateway.release()
        ↓
bounded SecretLease
```

`release()` requires exact matches for binding identity, Target, credential reference, purpose, and scope. The authorization grant must be active, bound to the same binding and Target, cover the requested purpose and scope, and not be expired. The credential identity's provider must match the binding provider, and the credential's own lifecycle/scope checks still apply.

Binding does **not** grant authorization. Target resolution does **not** release material. Credential existence does **not** prove validity or authorization. No component receives material through a backend API directly.

## Lease boundary

`lease_seconds` and `one_use` are represented in `ScopedReleaseRequest` and release metadata as future-contract fields. Phase C does not claim to provide a production lease service, distributed expiry enforcement, rotation, or revocation engine. Existing local/test lifecycle seams remain explicitly marked as testing/runtime seams.

## Non-disclosure

Control-plane metadata, representations, serialization, validation failures, and gateway errors must not contain material. `SecretLease.__repr__` and `__str__` are redacted. Provider adapters receive a lease only after the gateway checks; adapters do not receive a backend or credential store.

## Provider neutrality

The contract names mechanisms generically (`access_mechanism`, `interface`, `purpose`) and is not tied to OpenAI, Anthropic, Gemini, Ollama, OAuth, Vault, or any other provider. Adding a model to an existing provider is a Target/configuration concern; adding a provider may add provider and adapter metadata but does not require a new credential core.
