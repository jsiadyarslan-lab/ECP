# ECP Secrets Boundary

## Trust boundaries

```text
PUBLIC ECP REPOSITORY
  protocol, schemas, runner contracts, non-secret metadata

PROTECTED EVALUATION STORE
  hidden cases, ground truth, scoring commitments, protected evidence

SECRET STORE
  credential_id → secret value
```

These are distinct logical namespaces. A secret must never be stored beside a hidden case, ground truth, evidence artifact, registration manifest, or public protocol record.

## Access path

```text
ECP execution layer
        ↓
Credential Gateway
        ↓
scoped short-lived lease
        ↓
Provider Adapter
        ↓
External System
```

The evaluated external system does not receive access to the secret store. The runner does not receive permission to enumerate all credentials. Each request is bound to a logical credential identity and an allowed scope.

## What is persisted

ECP may persist only non-secret metadata such as `credential_ref`, provider, purpose, scope, version, expiry, and status. A future system identity may bind to the credential version without recording the credential payload.

The following are forbidden in every ECP artifact:

```text
Authorization header
API key
Bearer token
Refresh token
Credential payload
```

## Local and commercial migration

The current local source is environment injection for controlled development and tests. The interface is provider-neutral and can later be implemented by a self-hosted vault, enterprise vault, cloud secret manager, or managed credential service. Replacing the source does not require changing ECP scientific contracts.

No billing, SaaS, customer-account, multi-tenant, or commercial API implementation is part of this foundation.

## Operational requirements

Real credentials must be provisioned outside Git and outside chat. They must be scoped, purpose-bound, provider-bound, and time-bounded where supported. Rotation must change a physical secret version without rewriting cases or scientific artifacts. Revocation and expiry must prevent future gateway retrieval. Recovery must obtain a fresh credential from the protected source rather than restore an unprotected backup.

## Validation status

The repository tests cover the boundary with synthetic values only. They demonstrate metadata safety, gateway-only retrieval, scope checks, expiry, revocation, rotation, redaction, exception safety, serialization safety, environment injection, and no-secret-in-artifact behavior. They do not claim production security, host-level isolation, encryption at rest, or real-provider security.
