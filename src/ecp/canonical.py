"""ECP-CANONICAL-JSON-1.0: canonical JSON serialization.

Normative rules (see spec/ECP-SPEC.md, "Canonicalization"):

1. The input is a parsed JSON value (RFC 8259). NaN and infinities are
   forbidden (JSON does not define them and they are not portable).
2. Object keys are sorted by Unicode code point, ascending, recursively.
3. Serialization uses no insignificant whitespace: the separators are
   exactly ``","`` and ``":"``.
4. Strings are serialized with minimal escaping: ``"`` and ``\\`` are
   escaped, control characters use their shortest JSON escape, and all
   other characters (including non-ASCII) appear literally (UTF-8,
   no \\uXXXX folding, no BOM).
5. Integers are serialized in minimal decimal form. Floats, if used at
   all, use the shortest round-trip representation of an IEEE 754 double
   (Python >= 3.1 and modern ECMAScript engines agree on this); artifacts
   that require exact cross-language reproducibility should prefer
   integers or strings.
6. The canonical form of a document is the UTF-8 encoding of its
   canonical serialization. All commitments and document hashes are
   SHA-256 over exactly these bytes.

This module is the reference implementation of those rules.
"""

import json
from pathlib import Path

CANONICALIZATION_ID = "ECP-CANONICAL-JSON-1.0"


def canonical_dumps(document: object) -> str:
    """Return the canonical JSON serialization of *document* as a string.

    Raises:
        TypeError: if *document* is a string/bytes (callers must pass a
            parsed value, not serialized text) or contains non-JSON types.
        ValueError: if *document* contains NaN or infinity.
    """
    if isinstance(document, (str, bytes, bytearray)):
        raise TypeError(
            "canonical_dumps expects a parsed JSON value, not serialized text; "
            "parse it first (json.loads / load_json)."
        )
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_bytes(document: object) -> bytes:
    """Return the canonical form of *document* as UTF-8 bytes."""
    return canonical_dumps(document).encode("utf-8")


def load_json(path: "str | Path") -> object:
    """Parse a UTF-8 JSON file and return the value (no canonicalization)."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def canonical_bytes_from_file(path: "str | Path") -> bytes:
    """Parse a UTF-8 JSON file and return its canonical bytes."""
    return canonical_bytes(load_json(path))
