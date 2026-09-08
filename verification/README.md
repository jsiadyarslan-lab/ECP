# verification/ — RESERVED (empty at R0)

This directory is reserved for **future verification artifacts** — the outputs of the
verification layer (integrity results over manifests, commitments and evidence
bundles).

Note the boundary: verification answers *integrity* questions; it never performs
scientific adjudication. The verification *tooling* itself already exists
(`src/ecp/verification.py`, exposed via `tools/ecp_cli.py`); this directory is for
future recorded verification output, which does not exist yet.

Only this `README.md` may be present. The boundary scanner
(`python tools/ecp_cli.py boundary-scan`) and the test suite enforce this rule.
