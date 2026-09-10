# evaluation/ — RESERVED (empty at R0)

This directory is reserved for **future evaluation records** (the `Evaluation → System
→ Case → Execution → Evidence` hierarchy root).

At repository foundation (R0) it MUST remain empty: no evaluation has been defined,
registered, started or completed, and no evaluation record exists.

Only this `README.md` may be present. The boundary scanner
(`python tools/ecp_cli.py boundary-scan`) and the test suite enforce this rule.

Registration and execution are later, separately authorized phases; they do not exist
in this repository yet.
