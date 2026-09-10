# ECP Credential Boundary

## Purpose

ECP stores only non-secret credential metadata. A credential value is supplied at runtime by a protected source and is retrieved only through the provider-neutral `CredentialGateway`. This module does not call providers and does not execute evaluated systems.

## Identity versus secret

A `CredentialIdentity` is safe metadata:

```text
credential_id
provider
purpose
scope
version
status
created_at
expires_at
```

The secret value is never part of the identity, registration record, case artifact, evidence, manifest, report, Git history, or public repository.

## Runtime sources

Local development can inject a value through an operating-system environment variable. The ECP process may read it at runtime through `CredentialGateway.from_environment(...)`. The variable name is configuration; the value must not be written to source, `.env` files, CLI arguments, reports, or logs.

The environment source is read-only. Provisioning, rotation, and revocation of a real provider credential remain responsibilities of the external secret manager or provider. Synthetic in-memory provisioning helpers exist only for unit tests.

Production can replace the environment source behind the same `SecretStore` seam with a self-hosted vault, enterprise secret manager, cloud secret manager, or managed ECP credential service. Higher-level ECP contracts do not need to contain provider-specific secret logic.

## Gateway rules

The gateway is the only public retrieval boundary. Retrieval requires:

1. a known logical credential identity;
2. a requested scope included in the identity policy;
3. a non-revoked, non-expired status;
4. a provisioned value in the runtime source.

A successful retrieval returns a short-lived in-memory `SecretLease`. Its string representation is redacted, and its metadata contains no secret. Callers must use the lease only for the narrowly scoped provider-adapter operation and must not persist it.

## Lifecycle

The logical identity remains stable while the physical secret version rotates:

```text
PROVISIONED → ACTIVE → USED → ROTATED → REVOKED / EXPIRED
```

Rotation changes `version` and the runtime secret while preserving the logical `credential_id`. Revocation removes the synthetic test value and blocks further retrieval. Real-provider revocation must occur at the provider or protected secret manager.

## Exposure controls

Secrets must not appear in:

- Git or Git history;
- case, registration, evidence, or manifest artifacts;
- stdout, stderr, exception messages, or debug dumps;
- CLI arguments, prompts, environment dumps, or reports;
- public or protected ECP metadata.

The redaction helpers are defense-in-depth. They do not make it safe to print secrets. The correct practice is never to log the value.

## Scientific isolation

Credential metadata may describe the access path in a future system identity, but authorization headers, API keys, bearer tokens, refresh tokens, and credential payloads are not scientific evidence. Credential handling must not alter cases, ground truth, scoring, registration, execution classification, or evidence interpretation.

## Recovery

Recovery means restoring the protected credential metadata and obtaining a fresh secret from the provider or protected secret manager. ECP must not contain an unprotected backup of the secret. Synthetic tests cover gateway retrieval, rotation, revocation, expiry, redaction, and environment isolation; they do not validate a real provider credential.
