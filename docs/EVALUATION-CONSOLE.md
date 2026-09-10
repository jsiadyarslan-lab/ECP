# ECP Evaluation Console v1

This repository now contains a **controlled local-console scaffold** for the future external execution phase. It is an execution surface only; it does not author cases, change registrations, expose Ground Truth, score results, or execute a real external provider from this repository.

## Existing contracts reused

| Boundary | Existing implementation | Console use |
|---|---|---|
| Credential Gateway | `src/ecp/credentials.py`, `CredentialGateway.retrieve()` | Resolves a scoped `SecretLease` using `credential_ref`; the browser sees only metadata. |
| Secret backend | `EnvironmentSecretStore` in `src/ecp/credentials.py` | Existing runtime/test seam. A Windows Credential Manager implementation is not present in this baseline and must be supplied as an owner-side adapter before production use. |
| Provider Adapter | `ExternalSystemAdapter` protocol in `src/ecp/credentials.py` | `src/ecp/console.py`, `ProviderAdapter`; the default adapter is fail-closed and performs no provider call. |
| Execution path | No existing path in the baseline | `LocalGateway.execute()` is the new integration seam, not a replacement for a scientific execution engine. |
| Evidence Writer | No existing writer in the baseline | `ExecutionStore.persist()` writes only safe console metadata under a configured local artifact root. |
| Audit Writer | No existing writer in the baseline | The same safe store writes an audit-safe reference marked `PENDING_HUMAN_REVIEW`. |
| Git persistence | No existing console persistence in the baseline | Automatic commit/push is intentionally not implemented. If no artifact root is configured, status is `PUSH_PENDING`. |

## Authentication and origin boundary

The gateway binds to `127.0.0.1` only. A short-lived pairing code is generated at startup, printed to the local terminal, held in memory, and expires after ten minutes by default. Pairing creates an in-memory session token. The token is not written to the repository, embedded in the static UI, or persisted in artifacts. The gateway accepts requests only from the explicit `ECP_CONSOLE_ALLOWED_ORIGINS` allowlist.

The default origins are the GitHub Pages origin and a local static-console origin on port `8766`. The port is fixed at `8765` by default and can be changed only with `ECP_GATEWAY_PORT`. The gateway refuses non-loopback binding by construction.

## Lifecycle

Start with:

```bash
python -m ecp.console --port 8765 --artifact-root /path/to/local-records
```

The process is manual and stops with the normal process interrupt. The terminal prints the temporary pairing code. The static UI polls status on load, pairs with the code, loads the safe authorization catalog, and sends only `evaluation_id`, `system_id`, `credential_ref`, `test_id`, and `request_id` to `/api/v1/executions`.

The current implementation performs the execution in the request thread and returns a terminal record. The API also exposes `GET /api/v1/executions/{execution_id}` for reconnecting to a stored in-memory status. The catalog declares a 1.5-second polling interval and a 120-second execution timeout for the eventual asynchronous adapter contract; no adapter is enabled in this baseline.

## Safety status

The example gateway is deliberately **fail-closed**: without a registered provider adapter and a configured protected runtime credential, it returns `INCONCLUSIVE` / `ADAPTER_UNAVAILABLE` and makes no external call. No real credential is requested, provisioned, or executed by this implementation. The repository's prior ECP regression baseline also contains three pre-existing example-hash failures; historical example files were not changed to conceal them.
