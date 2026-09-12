# M3-ELR Scientific Campaign Browser Console (v1)

**Owner order 2026-09-13.** The registered M3-ELR execution surface exposed
in the EXISTING evaluation console: the owner opens the console in the
browser, pairs with the launcher-printed code, submits the OpenRouter
credential through the existing credential-session gateway, presses
RUN CAMPAIGN, and the frozen 30-case campaign executes with live results —
evidence, audit, and the campaign ledger persist exactly as the registered
CLI surface produces them.

This surface executes the SAME frozen protocol as
`python run_m3_elr_console.py`; only the trigger (browser instead of
terminal) and the credential entry point (browser credential session
instead of a launch-time environment variable) differ. There is ONE
campaign engine — `ecp.m3_elr_campaign.execute_campaign` — consumed by
both surfaces, so there cannot be two divergent execution loops.

## Run it

```
python run_m3_elr_browser_console.py [--evidence-root DIR] [--case-area DIR]
                                     [--gateway-port 8765] [--console-port 8766]
```

### The private case area (required once, owner-side)

The 30 registered case artifacts are private scientific instruments: they
live OUTSIDE the repository (never committed, never pushed) and must exist
on the machine that runs the campaign. Resolution order:

1. explicit `--case-area DIR`;
2. the `ECP_CASE_AREA` environment variable;
3. a sibling `ecp-ca0v1` directory next to the repository checkout — the
   documented owner-side placement (e.g.
   `…/Documents/GitHub/ecp-ca0v1` next to `…/Documents/GitHub/ECP`);
4. the executor-sandbox default `/home/z/ecp-ca0v1`.

If none is present the launcher fail-closes at boot with these same
instructions. The launcher prints the resolved case area at boot, and the
four-surface hash verification proves the delivered bytes are exactly the
frozen `ECP-PKG-M3-ELR-V1` material wherever it runs.

1. The launcher fail-closes at boot unless the frozen registration package
   verifies (identity + hash), the 30 registered cases verify on all four
   surfaces, and the §22 readiness gate has zero FAIL checks. Keep the
   checkout synchronized (`git pull`) before launching — the gate includes
   a delivery-sync check (HEAD == origin/main).
2. Open `http://127.0.0.1:8766/` in the browser and PAIR with the code the
   launcher prints (short-lived, held in gateway memory only).
3. Paste the OpenRouter credential and press OPEN CREDENTIAL SESSION — the
   value is submitted once to the loopback gateway, held in-process behind
   the credential gateway, and referenced afterwards only by a credential
   reference. It is never stored by the page, never printed, never
   committed, never written to evidence or audit.
4. (Optional, informational) DISCOVER PROVIDER & MODELS — verify the pinned
   target `inclusionai/ling-3.0-flash-sante:free` is listed and AVAILABLE.
   Model selection here is for the universal conformance probe only; the
   campaign always executes the pinned target.
5. Press RUN CAMPAIGN in the "M3-ELR scientific campaign" section. The 30
   registered tests execute in the frozen F-01b order, one attempt each,
   no retries; each completed test appears in the live ledger table
   (execution status, provider status, answer state, task outcome), and
   the final summary appears when the campaign completes.

## Where the documentation lands (as agreed, outside the repository)

Default evidence root: a sibling of the repository checkout
(`<repo-parent>/ecp-m3-elr-evidence`, overridable with `--evidence-root`):

```
<evidence-root>/executions/ECP-EXEC-M3ELR-*-evidence.json   # per-execution evidence
<evidence-root>/executions/ECP-EXEC-M3ELR-*-audit.json      # per-execution audit (PENDING_HUMAN_REVIEW)
<evidence-root>/m3-elr-campaign-ledger.json                 # campaign ledger + summary
```

The evidence/audit/ledger artifacts are byte-compatible with the CLI
surface: same fields, same frozen classifier classifications, same
registration reference (package id + hash), same transport attribution.
The protected ground truth never leaves the process — evidence carries
classifications (answer state, declared key, premise citation, task
outcome), never the ground truth itself.

## Discipline

- **One campaign per launcher process.** After a campaign has started
  (completed OR failed), a second start is refused; restart the launcher
  to execute a new campaign. This preserves the frozen single-attempt
  discipline (one attempt per registered test per campaign, no retries).
- **Transport failures are honest.** A provider timeout/error (e.g. HTTP
  401 on an invalid key) is recorded as an INVALID execution with the
  provider status and HTTP code in the evidence — execution success is
  never converted into reasoning success and vice versa. If the key was
  wrong, restart the launcher and run again; the failed campaign remains
  on disk as an honest record.
- **The pinned target never changes.** The frozen registration pins
  `inclusionai/ling-3.0-flash-sante:free` @ OpenRouter under
  ECP-COND-M3-ELR-1 (MODEL-ENABLED, L1 model-only, temperature 0.0,
  max_tokens 1024, transport timeout 30s).

## Architecture (no new authority)

| Piece | Role |
|---|---|
| `run_m3_elr_browser_console.py` | Launcher: verifies the frozen package/cases/gate at boot, builds the frozen adapter, wires the existing session console + the campaign component, serves the existing console UI + loopback gateway |
| `ecp.m3_elr_campaign` | The ONE frozen campaign engine (also consumed by the registered CLI launcher); per-test intent resolution, scoped credential release, adapter execution, frozen classification, evidence/audit/ledger persistence |
| `ecp.m3_elr_campaign_console.M3ELRCampaignConsole` | Session-console component: delegates the five standard session routes to the existing `ConsoleSessionManager`, adds the two campaign routes, runs the engine on a background thread, exposes live state |
| `console/` (existing UI) | The M3-ELR section is auto-detected: it appears only when the gateway serves the campaign routes (other launchers are unaffected) |

Routes (dispatched by the existing `LocalGateway` session-route seam,
behind pairing authentication, with submitted-secret redaction):

```
POST /api/v1/m3elr/campaign/status  -> registration facts + readiness gate + live campaign state
POST /api/v1/m3elr/campaign         -> start the frozen campaign {credential_ref}
```

The credential value flows ONLY through the session credential gateway's
existing `release()` path — the component never sees it, the browser never
receives it, and it appears in no response, log, or artifact.
