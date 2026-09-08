# evidence/ — RESERVED (empty at R0)

This directory is reserved for **future evidence bundles** (per the evidence contract
in `schemas/evidence.schema.json`).

At repository foundation (R0) it MUST remain empty: no model or system has been
executed, no raw output exists, and no evidence of any kind has been collected.
Public evidence storage policy (and its relation to the protected evidence store)
will be defined in a later phase.

Only this `README.md` may be present. The boundary scanner
(`python tools/ecp_cli.py boundary-scan`) and the test suite enforce this rule.
