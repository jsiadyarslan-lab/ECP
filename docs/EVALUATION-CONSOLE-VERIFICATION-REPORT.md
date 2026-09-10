# ECP Evaluation Console v1 — Verification Report

## Conclusion

The ECP Evaluation Console integration boundary was implemented and verified through focused security tests and a real local Chromium browser flow. The implementation is **not marked `IMPLEMENTED / VERIFIED` for repository release** because the pre-existing full regression suite remains red in three historical example-hash tests. Those historical artifacts were not modified.

The implementation is also deliberately fail-closed for external execution. No real provider adapter, Windows Credential Manager backend, real credential, or real external call was introduced during this task.

## Repository state

| Item | Result |
|---|---|
| Repository | `jsiadyarslan-lab/ECP` |
| Branch | `main` |
| Baseline HEAD | `df3b2f86c128fe9e54962546de1cc1f57955fe75` |
| Origin baseline | `df3b2f86c128fe9e54962546de1cc1f57955fe75` |
| Final HEAD | unchanged; no commit created |
| Worktree | contains only the intended uncommitted console files |
| Push | not performed because the full regression gate is not green |

## Reused architecture

| Boundary | Evidence | Status |
|---|---|---|
| Credential Gateway | `src/ecp/credentials.py:215-240`, `CredentialGateway.retrieve()` | Reused |
| Secret backend | `src/ecp/credentials.py:160-178`, `EnvironmentSecretStore` | Reused runtime seam; Windows backend is absent in the baseline |
| Provider Adapter | `src/ecp/credentials.py:200-212`, `ExternalSystemAdapter` | Reused as the provider-neutral contract |
| Local execution boundary | `src/ecp/console.py:218-264`, `LocalGateway.execute()` | Added integration seam; fail-closed by default |
| Evidence and audit-safe persistence | `src/ecp/console.py:254-264`, `ExecutionStore.persist()` | Added safe metadata-only local writer |
| Git persistence | No existing console writer found | Automatic commit and push intentionally not implemented |

## Console contract

| Item | Implemented value |
|---|---|
| Static UI | `console/index.html`, `console/app.js`, `console/style.css` |
| Local endpoint | `http://127.0.0.1:8765` |
| Binding | Loopback only; the server constructs `ThreadingHTTPServer(("127.0.0.1", port), ...)` |
| Default port | `8765` |
| Port override | `ECP_GATEWAY_PORT` or `--port` |
| Pairing | In-memory random code, ten-minute lifetime, one session token in memory |
| Allowed origins | `ECP_CONSOLE_ALLOWED_ORIGINS`; explicit defaults only |
| Request fields | `evaluation_id`, `system_id`, `credential_ref`, `test_id`, `request_id` |
| Forbidden request data | Secret values, API keys, tokens, shell commands, URLs, Ground Truth, scoring data |
| Idempotency | `request_id` returns the existing execution record instead of silently re-running |
| Polling contract | Catalog declares 1.5 seconds; execution timeout contract declares 120 seconds |
| Persistence | Configured local artifact root only; otherwise `PUSH_PENDING` |

The public UI is not configured with a provider URL or repository token. It sends requests only to the fixed loopback gateway. The gateway does not expose the `SecretLease.value` field through HTTP responses.

## Verification results

### Focused tests

The new test module contains seven focused tests. All seven passed. The tests cover pairing and origin denial, authentication, request validation, credential-gateway resolution, secret redaction, idempotency, fail-closed adapter behavior, partial success, and static UI inspection.

### Full regression

The full suite collected **781 tests**. **778 passed and 3 failed**. The failures are unchanged historical example integrity failures:

| Test | Failure |
|---|---|
| `tests/test_examples.py::test_evidence_bundle_hashes_are_real` | `examples/artifacts/raw-output.demo.txt` hash mismatch |
| `tests/test_verification.py::test_artifact_hash_verification_passes` | Same raw-output artifact hash mismatch |
| `tests/test_verification.py::test_manifest_verification_passes_on_example` | Three stored example artifact hashes mismatch |

The mismatch was present before the console changes. The historical examples and manifests were not rewritten because doing so would violate the scientific-isolation and historical-artifact constraints.

### Real browser flow

A local Chromium browser loaded the static console, paired with the loopback gateway, loaded one authorized evaluation, executed the registered synthetic adapter, and displayed the terminal result:

```text
CONNECTED
LOADED
SUCCESS
execution_id = ECP-EXEC-CONSOLE-36bc1b5aef8948da9cd81a850571ea94
external = SUCCESS
browser_result = PASS
browser-visible secret = false
```

This test used a synthetic in-memory credential and a synthetic adapter. It did not call a real provider. The deployed HTTPS GitHub Pages to HTTP localhost path was not claimed as verified because GitHub Pages was not enabled in the repository before this task and no commit was pushed. The local-console fallback path was verified.

### Boundary and secret checks

The ECP boundary scan returned:

```text
BOUNDARY SCAN: CLEAN — public/protected boundary respected.
```

Focused secret checks confirmed that the synthetic test secret was absent from the HTTP result, execution record, evidence, audit-safe record, and persistence files. The source contains only defensive field names and synthetic test fixtures; no owner credential was used.

## Scientific isolation

| Protected area | Modified |
|---|---|
| T1 | No |
| M1 | No |
| M2 | No |
| Ground Truth | No |
| Historical registration | No |
| Frozen Manuscript | No |
| Existing credential foundation | No |

## Release decision

The implementation is ready for owner review as an uncommitted integration boundary. It is **not released or pushed** because the existing full regression suite is not green and the Windows protected backend plus real provider adapter remain owner-side prerequisites.

The next safe actions are to reconcile the three pre-existing example hashes in a separately authorized maintenance change, supply the approved Windows Credential Manager adapter behind the existing `CredentialGateway` seam, register a real provider adapter, and then rerun the full release gate.

## References

[1]: https://github.com/jsiadyarslan-lab/ECP/blob/main/src/ecp/credentials.py "ECP credential boundary implementation"

[2]: https://github.com/jsiadyarslan-lab/ECP/blob/main/src/ecp/console.py "ECP local evaluation gateway implementation"

[3]: https://github.com/jsiadyarslan-lab/ECP/blob/main/console/index.html "ECP static evaluation console"

[4]: https://github.com/jsiadyarslan-lab/ECP/blob/main/tests/test_console.py "ECP console security tests"

[5]: https://github.com/jsiadyarslan-lab/ECP/blob/main/docs/EVALUATION-CONSOLE.md "ECP console integration documentation"
