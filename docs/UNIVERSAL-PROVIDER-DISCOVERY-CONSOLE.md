# Universal Visual Provider & Model Evaluation Console v1

**Owner order:** 2026-09-12 — "UNIVERSAL VISUAL PROVIDER & MODEL EVALUATION CONSOLE v1"
**Branch:** `main`
**Status:** implemented over the EXISTING universal fabric (no parallel console, no new credential system, no rebuilt fabric)

```text
Browser on the owner's computer
        |
        |  pairing code (existing mechanism)
        v
ECP Local Server  (127.0.0.1:8765 gateway + 127.0.0.1:8766 static console)
        |
        |  existing composition root (run_console.py)
        v
Universal Target / Provider Fabric  (TargetOnboardingService + registries)
        |
        v
CredentialGateway  (session credentials enter HERE, once, in-process only)
        |
        v
Unified Provider & Model Discovery  (ecp.discovery — descriptor data, no per-provider code)
        |
        v
Provider + Models identified (or explicitly UNKNOWN / DISCOVERY_FAILED)
        |
        v
Owner selects a model  ->  target configuration  ->  EXISTING onboarding pipeline
        |
        v
Evaluation through the EXISTING universal execution path (POST /api/v1/executions)
        |
        v
Result + Evidence + Audit + Safe persistence (unchanged writers)
```

---

## 1. How the owner starts the console

```bash
python run_console.py
```

Default start (no configuration file needed):

```text
ECP universal gateway listening on 127.0.0.1:8765
Onboarded targets (configuration-driven): 1        (offline demonstration target)
PAIRING CODE: <printed once, short-lived>
Console: http://127.0.0.1:8766/
```

Open **http://127.0.0.1:8766/** in the browser and pair with the printed code. Both servers bind `127.0.0.1` only; the gateway additionally enforces the existing origin allowlist and session authentication on every API route. `--gateway-port`, `--console-port`, `--config` and `--artifact-root` behave exactly as before.

## 2. Where the owner puts the credential

In the console page, section **"Universal provider & model discovery"**:

* **Provider credential** field (password-type input). Paste the provider API key there and press **OPEN CREDENTIAL SESSION**.
* The value is read once, sent **only** to the loopback gateway (`http://127.0.0.1:8765/api/v1/credentials/session`) over the paired session, and the input field is cleared immediately.
* The page **never** stores the value: no `localStorage`, no session storage, no variable that outlives the submission. After submission the browser only holds the returned **credential reference** in memory.
* The gateway stores the value **in process memory only** (the session credential gateway's protected store) — never on disk, never in Git, never in logs, never in evidence, audit, reports or any HTTP response.

## 3. How the credential links to the credential reference

`POST /api/v1/credentials/session` returns:

```json
{"credential_ref": "ECP-SESSION-CREDENTIAL-1A2B3C4D5E6F7788", "status": "OPEN", "expires_at": "...", "session_provider": "ECP-PROVIDER-OWNER-SESSION"}
```

* `credential_ref` is the ONLY thing the browser keeps. It is a non-secret session handle.
* All later operations (discovery, model selection, evaluation) reference the credential **only** by this reference.
* The value is releasable exclusively through the EXISTING `CredentialGateway.release()` path with a real binding and authorization grant (discovery scope first; evaluation scope after the provider is identified). There is no second secret path.
* Sessions expire automatically (default 8 hours; `ECP_SESSION_TTL_SECONDS` clamps 60–86400). **FORGET CREDENTIAL** revokes immediately (value deleted from memory).

## 4. How discovery starts and how ECP identifies the provider/models

Press **DISCOVER PROVIDER & MODELS**. Options:

* **Provider (optional)** dropdown — comes from the server's discovery registry (`GET /api/v1/discovery/descriptors`), not hard-coded in the page. Default is Auto-detect.
* **Custom endpoint (optional)** — any OpenAI-compatible base URL (e.g. `http://127.0.0.1:11434/v1` for local servers). When supplied, only that endpoint is probed.

ECP then probes each registered dialect descriptor with a gateway-released lease:

| Descriptor | Probe | Credential header | Model list shape |
|---|---|---|---|
| OpenAI | `GET https://api.openai.com/v1/models` | `Authorization: Bearer …` | `{"data":[{"id":…}]}` |
| Anthropic | `GET https://api.anthropic.com/v1/models` | `x-api-key` + `anthropic-version` | `{"data":[{"id":…,"display_name":…}]}` |
| Google Gemini | `GET https://generativelanguage.googleapis.com/v1beta/models` | `x-goog-api-key` | `{"models":[{"name":…,"supportedGenerationMethods":…}]}` |
| Groq | `GET https://api.groq.com/openai/v1/models` | `Authorization: Bearer …` | OpenAI shape |
| OpenRouter | `GET https://openrouter.ai/api/v1/models` | `Authorization: Bearer …` | OpenAI shape |
| Custom OpenAI-compatible | `GET <owner endpoint>/models` | `Authorization: Bearer …` | OpenAI shape |

A provider is reported **IDENTIFIED** only when its models endpoint answered HTTP 200 with a parseable model list. Every probe outcome is reported honestly (`IDENTIFIED`, `CREDENTIAL_REJECTED`, `UNREACHABLE`, `NOT_SUPPORTED`, `MALFORMED`, `NO_MODELS`, `RATE_LIMITED`) in the **Probe diagnostics** panel. If nothing answers, the state is **UNKNOWN / DISCOVERY_FAILED** — the console never guesses a provider identity.

Each discovered model carries the provider-neutral representation: `provider`, `model_identifier`, `display_name`, `capabilities` (when the dialect advertises them), `availability`, `discovery timestamp`, `adapter_kind`, `protocol`. Long lists are capped at 250 with an explicit truncation flag.

## 5. How the owner selects a model and starts the evaluation

* Click a model row in **Discovered models** (it highlights).
* Press **RUN EVALUATION**. The console then:
  1. `POST /api/v1/session/targets` — the server builds a **plain target configuration** (deterministic identifiers derived from provider + model + endpoint + credential reference) and onboards it through the **EXISTING** `TargetOnboardingService` pipeline: validation → provider/target/adapter registration → binding/grant resolution → 9-check readiness battery → evaluation registration. No provider-specific code is involved anywhere.
  2. `POST /api/v1/executions` — the single existing execution contract (the same endpoint the configured targets use). Authorization, credential release, the provider adapter call, normalization, evidence, audit and persistence all flow through the unchanged universal path.
* The evaluation sends the registered conformance probe (`ECP-CONFORMANCE-OK`); it is a transport/conformance test, not a scientific case.
* The selected model identifier reaches the provider adapter **verbatim** (it is adapter configuration, never client data), and the execution request carries **identifiers only** — `evaluation_id`, `system_id`, `credential_ref`, `test_id`, `request_id`. No secret travels through the browser or the request payload after the session opens.
* There is **no fallback** to the offline demo anywhere on this path: the session target, its adapter and its credential binding are distinct objects, and the demo evaluation can only run through its own explicit **RUN TEST** button.

## 6. Where the result, evidence and audit appear

The **Execution** card shows, live: execution id, **Provider**, **Model**, **Adapter**, **Endpoint**, **Transport**, **Provider status code**, **Latency**, execution status, response status, **Failure classification** (on failures), evidence status + **Evidence reference** (`ECP-EVID-CONSOLE-…`), **Audit reference** (`ECP-AUDIT-CONSOLE-…`), audit status, persistence status and the on-disk persistence location, plus the redacted safe result. Evidence/audit files are persisted under the artifact root exactly as before (`local-browser-artifacts/external-executions/<execution_id>/` by default). Audit records are `PENDING_HUMAN_REVIEW` as always.

### Execution attribution — real external calls vs offline demonstrations

Every execution record and evidence document now carries non-secret **transport attribution** (owner order: UNIVERSAL REAL PROVIDER EXECUTION BINDING v1):

| Field | Real external execution (any provider) | Offline demo execution |
|---|---|---|
| `transport_kind` | `http` | `offline-mock` |
| `endpoint` | the exact provider URL the request was sent to (e.g. `https://openrouter.ai/api/v1/chat/completions`) | absent (no network) |
| `http_status` | the provider's HTTP status for the call (e.g. `200`; on failures the rejected status, e.g. `401`) | absent |
| `latency_ms` | measured round-trip time | absent |
| `network` | — | `none` |

A real **failure** is displayed just as honestly: the record keeps the provider, model, adapter, endpoint and the provider's HTTP status, with the real classification (`PROVIDER_AUTHENTICATION_FAILED`, `PROVIDER_RATE_LIMITED`, `PROVIDER_TIMEOUT`, `PROVIDER_REQUEST_FAILED`, `PROVIDER_QUOTA_EXCEEDED`, `PROVIDER_CONNECTION_FAILED`) — never a fabricated SUCCESS. Because the demo and a real call can produce the same `normalized_output` (`ECP-CONFORMANCE-OK` by design of the conformance probe), the transport fields above are the definitive distinction.

## 7. Security properties (owner order §4)

* The submitted key is a real secret and is treated as one: in-process only, reference-only across every boundary, redacted from all error paths, never echoed to the browser.
* The browser never calls a provider directly — only the loopback gateway.
* The local server is a thin composition layer: it cannot bypass the CredentialGateway, provider policies, authorization, evidence, audit or the evaluation contract (no new authority).
* Loopback-only binding, origin allowlist, session authentication and request-size limits apply to every new route exactly as to the existing ones.
* Cloud metadata endpoints are rejected as custom endpoints; credentials-in-URL are rejected; local/private endpoints are allowed (local model servers).

## 8. Notes and limits

* **OpenRouter** serves its model list publicly: a wrong key can still "identify" the provider and list models; execution will then fail honestly with `PROVIDER_AUTHENTICATION_FAILED` and the provider's HTTP status in the record. Identification is a dialect claim, not a credential-validity claim.
* **Custom-header chat-completions gateways** (credential in a non-standard header plus static routing headers) work through BOTH paths now: the launcher configuration (`examples/launcher/onboarding-chat-completions-gateway.example.json`) and the **browser session flow** — enter the endpoint plus the optional **Gateway headers** JSON (`{"token_header":…,"bearer_value":…,"extra_headers":{…}}`) in the discovery card. These knobs are non-secret configuration only (header names, public markers, routing values); the credential value itself still flows exclusively through the credential gateway's release path, in the same placement the runtime adapter uses.
* Adding a provider = one descriptor entry (data) in `ecp.discovery` plus, only for a genuinely new transport dialect, one adapter class in `ecp.runtime_adapters`. Adding models requires nothing — they arrive from the provider's own models endpoint.
* The console's own regression battery: `tests/test_discovery.py`, `tests/test_console_session.py` (fully synthetic — no real credential, no network), plus the real-provider binding tests in `tests/test_console_session.py` (UNIVERSAL REAL PROVIDER EXECUTION BINDING v1 section: the selected model reaches the real adapter verbatim at the real endpoint with the session lease; the offline demo is never invoked; real failures surface honestly; no credential leakage).
