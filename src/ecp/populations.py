"""M3 population namespace governance model (v1).

Established by the owner order *M3 AUTHORITATIVE SCIENTIFIC POPULATION
GOVERNANCE & NAMESPACE COLLISION CLOSURE v1* (2026-09-12): once more than
one candidate population exists, a bare ``candidate_id`` is NOT a
complete scientific artifact identity.  The addressable identity is the
tuple::

    (population_id, case_pack_id, case_pack_version, candidate_id)

and every resolution is verified against the artifact ``content_hash``.

The 2026-09 artifact-identity reconciliation (M3 AIR v1.1) proved a real
collision: ``ECP-CAND-000101..000103`` denote DIFFERENT content in the
CA0v1 authored 30-candidate pool (2026-09-09) and in the registered
3-case ECP-native corpus (2026-09-10).  Both chains are individually
hash-consistent; the overlap is a namespace fact, not a content defect.
This module isolates that collision by construction:

* population-qualified lookup is the ONLY permitted resolution path;
* unqualified ``lookup(candidate_id)`` is rejected fail-closed
  (``AMBIGUOUS_ID -> REJECTED``) whenever multiple populations are
  registered — exactly the guard whose absence let the native corpus
  silently reuse the CA0v1 ID range;
* the collision invariant ``same namespace + same candidate_id +
  different content_hash = COLLISION`` is enforced at load time;
* ``same candidate_id + different population namespace`` yields
  DISTINCT identities (never conflated, never merged).

Governance boundary (hard):
* this module is namespace/provenance machinery ONLY — it imports
  nothing from the execution path; Universal Experiment Execution
  Contract v1 (execution_contract.py / console.py / adapters.py /
  runtime_adapters.py) stays byte-unchanged;
* it creates NO runner and NO adapter/provider registry;
* it registers NO new population: the indexed populations are the two
  historical corpora (Native, CA0v1), preserved read-only with their
  historical IDs, content, and provenance — nothing is renamed,
  modified, merged, or deleted;
* the future population (Population C) is a conceptual namespace only
  and is deliberately absent from the manifest.

The population namespace manifest lives at
``provenance/m3-population-namespace-manifest.json``; it is derived
read-only from the historical artifacts (public registration records,
the native corpus manifest, the CA0v1 authoring intake report) and pins
their hashes.  See ``docs/M3-POPULATION-NAMESPACE-GOVERNANCE.md`` for
the governance record and the two decisions (NAMESPACE DECISION /
POPULATION DECISION).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

__all__ = [
    "MANIFEST_OBJECT",
    "DEFAULT_MANIFEST_PATH",
    "PopulationNamespaceError",
    "AmbiguousCandidateIdError",
    "UnknownNamespaceError",
    "NamespaceCollisionError",
    "ContentHashMismatchError",
    "NamespaceKey",
    "CandidateIdentity",
    "PopulationRecord",
    "PopulationNamespaceIndex",
    "load_manifest",
    "read_manifest_document",
]

MANIFEST_OBJECT = "m3-population-namespace-manifest"
DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[2] / "provenance" / "m3-population-namespace-manifest.json"
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Errors (fail-closed family)
# ---------------------------------------------------------------------------


class PopulationNamespaceError(ValueError):
    """Base class for population-namespace governance violations."""


class AmbiguousCandidateIdError(PopulationNamespaceError):
    """A bare candidate_id cannot resolve a scientific identity.

    Raised whenever an unqualified ``lookup(candidate_id)`` is attempted
    while multiple populations are registered (``AMBIGUOUS_ID ->
    REJECTED``), regardless of how many populations currently contain
    the id: a future population may claim the same id at any time —
    which is precisely how the historical collision arose.
    """


class UnknownNamespaceError(PopulationNamespaceError):
    """The requested population namespace (or candidate within it) is
    not registered.  Lookups never fall back to a partial match."""


class NamespaceCollisionError(PopulationNamespaceError):
    """Collision invariant violated: same namespace + same
    candidate_id + different content_hash = COLLISION."""


class ContentHashMismatchError(PopulationNamespaceError):
    """The resolved artifact content hash differs from the expected
    hash — identity verification failed."""


def _require_nonempty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _require_hex64(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise ValueError(f"{name} must be a 64-character lowercase hex sha256")
    return value


# ---------------------------------------------------------------------------
# Identity types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NamespaceKey:
    """The namespace half of a scientific artifact identity."""

    population_id: str
    case_pack_id: str
    case_pack_version: int

    def __post_init__(self) -> None:
        _require_nonempty_str(self.population_id, "population_id")
        _require_nonempty_str(self.case_pack_id, "case_pack_id")
        if (
            not isinstance(self.case_pack_version, int)
            or isinstance(self.case_pack_version, bool)
            or self.case_pack_version < 1
        ):
            raise ValueError("case_pack_version must be an integer >= 1")

    def as_tuple(self) -> tuple[str, str, int]:
        return (self.population_id, self.case_pack_id, self.case_pack_version)


@dataclass(frozen=True)
class CandidateIdentity:
    """A fully qualified, hash-verified scientific artifact identity.

    Equality compares ALL five fields: the same ``candidate_id`` under a
    different population namespace — or with a different content hash —
    is a DIFFERENT identity, never a conflated one.
    """

    population_id: str
    case_pack_id: str
    case_pack_version: int
    candidate_id: str
    content_hash: str

    def __post_init__(self) -> None:
        _require_nonempty_str(self.population_id, "population_id")
        _require_nonempty_str(self.case_pack_id, "case_pack_id")
        if (
            not isinstance(self.case_pack_version, int)
            or isinstance(self.case_pack_version, bool)
            or self.case_pack_version < 1
        ):
            raise ValueError("case_pack_version must be an integer >= 1")
        _require_nonempty_str(self.candidate_id, "candidate_id")
        _require_hex64(self.content_hash, "content_hash")

    def namespace_key(self) -> NamespaceKey:
        return NamespaceKey(
            population_id=self.population_id,
            case_pack_id=self.case_pack_id,
            case_pack_version=self.case_pack_version,
        )

    def qualified_reference(self) -> str:
        """Human-readable fully-qualified reference (identity, not proof)."""
        return (
            f"{self.population_id}/{self.case_pack_id}"
            f"@v{self.case_pack_version}/{self.candidate_id}"
        )


# ---------------------------------------------------------------------------
# Population record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PopulationRecord:
    """One historical population, preserved read-only.

    ``candidates`` is an ordered tuple of ``(candidate_id,
    content_hash)`` pairs sorted by candidate_id; the population's own
    namespace must be collision-free by construction (validated on
    load): the same candidate_id may never map to two content hashes
    inside one namespace.
    """

    population_id: str
    case_pack_id: str
    case_pack_version: int
    status: str
    candidates: tuple[tuple[str, str], ...]
    candidate_count: int
    provenance: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        _require_nonempty_str(self.population_id, "population_id")
        _require_nonempty_str(self.case_pack_id, "case_pack_id")
        if (
            not isinstance(self.case_pack_version, int)
            or isinstance(self.case_pack_version, bool)
            or self.case_pack_version < 1
        ):
            raise ValueError("case_pack_version must be an integer >= 1")
        _require_nonempty_str(self.status, "status")
        if not isinstance(self.candidates, tuple):
            raise ValueError("candidates must be a tuple of (candidate_id, content_hash) pairs")
        seen: dict[str, str] = {}
        for pair in self.candidates:
            if not (isinstance(pair, tuple) and len(pair) == 2):
                raise ValueError("each candidate entry must be a (candidate_id, content_hash) pair")
            candidate_id = _require_nonempty_str(pair[0], "candidate_id")
            content_hash = _require_hex64(pair[1], f"content_hash of {candidate_id}")
            if candidate_id in seen and seen[candidate_id] != content_hash:
                raise NamespaceCollisionError(
                    "COLLISION: within population "
                    f"{self.population_id} the candidate_id {candidate_id} maps to "
                    f"two different content hashes ({seen[candidate_id]}, {content_hash})"
                )
            seen[candidate_id] = content_hash
        if self.candidate_count != len(seen):
            raise ValueError(
                "candidate_count must equal the number of unique candidate ids "
                f"(declared {self.candidate_count}, actual {len(seen)})"
            )

    # -- accessors ---------------------------------------------------------

    @property
    def namespace_key(self) -> NamespaceKey:
        return NamespaceKey(
            population_id=self.population_id,
            case_pack_id=self.case_pack_id,
            case_pack_version=self.case_pack_version,
        )

    @property
    def candidate_index(self) -> dict[str, str]:
        return dict(self.candidates)

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(candidate_id for candidate_id, _ in self.candidates)

    def lookup(self, candidate_id: str) -> CandidateIdentity:
        """Resolve a candidate WITHIN this population's namespace."""
        _require_nonempty_str(candidate_id, "candidate_id")
        index = self.candidate_index
        if candidate_id not in index:
            raise UnknownNamespaceError(
                f"candidate_id {candidate_id} is not present in population "
                f"{self.population_id} (case pack {self.case_pack_id} "
                f"v{self.case_pack_version})"
            )
        return CandidateIdentity(
            population_id=self.population_id,
            case_pack_id=self.case_pack_id,
            case_pack_version=self.case_pack_version,
            candidate_id=candidate_id,
            content_hash=index[candidate_id],
        )

    # -- construction from manifest dict ------------------------------------

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PopulationRecord":
        if not isinstance(data, Mapping):
            raise ValueError("population entry must be a JSON object")
        candidate_index = data.get("candidate_index")
        if not isinstance(candidate_index, Mapping) or not candidate_index:
            raise ValueError(
                "population entry must carry a non-empty 'candidate_index' "
                "{candidate_id: content_hash} mapping"
            )
        pairs = tuple(
            sorted((str(cid), str(ch)) for cid, ch in candidate_index.items())
        )
        provenance = data.get("provenance", {})
        if not isinstance(provenance, Mapping):
            raise ValueError("population 'provenance' must be a JSON object")
        return cls(
            population_id=data["population_id"],
            case_pack_id=data["case_pack_id"],
            case_pack_version=data["case_pack_version"],
            status=data.get("status", "UNKNOWN"),
            candidates=pairs,
            candidate_count=int(data.get("candidate_count", len(pairs))),
            provenance=dict(provenance),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "population_id": self.population_id,
            "case_pack_id": self.case_pack_id,
            "case_pack_version": self.case_pack_version,
            "status": self.status,
            "candidate_count": self.candidate_count,
            "candidate_index": self.candidate_index,
            "provenance": dict(self.provenance),
        }


# ---------------------------------------------------------------------------
# The namespace index (population-qualified lookup only)
# ---------------------------------------------------------------------------


class PopulationNamespaceIndex:
    """Fail-closed index over the registered population namespaces.

    Contract (owner order §6/§7/§13):

    * ``lookup(population_id, case_pack_id, case_pack_version,
      candidate_id)`` is the ONLY resolution path; an optional
      ``expected_content_hash`` turns resolution into verification.
    * ``lookup_by_candidate_id(candidate_id)`` is REJECTED whenever
      multiple populations are registered (AMBIGUOUS_ID), even if the
      id currently exists in only one of them.
    * ``assert_collision_invariant()`` proves that no namespace maps
      one candidate_id to two content hashes.
    * ``distinct_identities(candidate_id)`` proves that the same
      candidate_id under different namespaces yields distinct,
      non-equal identities.
    """

    def __init__(self, populations: Sequence[PopulationRecord]) -> None:
        if not populations:
            raise ValueError("at least one population is required")
        by_key: dict[tuple[str, str, int], PopulationRecord] = {}
        by_population_id: dict[str, PopulationRecord] = {}
        for record in populations:
            key = record.namespace_key.as_tuple()
            if key in by_key:
                raise ValueError(f"duplicate population namespace: {key}")
            if record.population_id in by_population_id:
                raise ValueError(
                    f"duplicate population_id: {record.population_id} "
                    "(one namespace per population_id)"
                )
            by_key[key] = record
            by_population_id[record.population_id] = record
        self._populations: tuple[PopulationRecord, ...] = tuple(populations)
        self._by_key = by_key
        self._by_population_id = by_population_id

    # -- properties ---------------------------------------------------------

    @property
    def population_count(self) -> int:
        return len(self._populations)

    @property
    def population_ids(self) -> tuple[str, ...]:
        return tuple(record.population_id for record in self._populations)

    @property
    def populations(self) -> tuple[PopulationRecord, ...]:
        return self._populations

    def population(self, population_id: str) -> PopulationRecord:
        _require_nonempty_str(population_id, "population_id")
        if population_id not in self._by_population_id:
            raise UnknownNamespaceError(
                f"population_id {population_id} is not registered; registered "
                f"populations: {', '.join(sorted(self._by_population_id))}"
            )
        return self._by_population_id[population_id]

    # -- the permitted lookup path -------------------------------------------

    def lookup(
        self,
        population_id: str,
        case_pack_id: str,
        case_pack_version: int,
        candidate_id: str,
        expected_content_hash: Optional[str] = None,
    ) -> CandidateIdentity:
        """Population-qualified lookup, then (optional) hash verification."""
        key = NamespaceKey(
            population_id=population_id,
            case_pack_id=case_pack_id,
            case_pack_version=case_pack_version,
        )
        record = self._by_key.get(key.as_tuple())
        if record is None:
            raise UnknownNamespaceError(
                f"namespace {key.as_tuple()} is not registered; registered "
                f"namespaces: {sorted(self._by_key)}"
            )
        identity = record.lookup(candidate_id)
        if expected_content_hash is not None:
            self.verify(identity, expected_content_hash)
        return identity

    def verify(
        self, identity: CandidateIdentity, expected_content_hash: str
    ) -> bool:
        """Verify a resolved identity against an expected content hash."""
        _require_hex64(expected_content_hash, "expected_content_hash")
        if identity.content_hash != expected_content_hash:
            raise ContentHashMismatchError(
                f"content hash mismatch for {identity.qualified_reference()}: "
                f"resolved {identity.content_hash}, expected {expected_content_hash}"
            )
        return True

    # -- the forbidden lookup path -------------------------------------------

    def lookup_by_candidate_id(self, candidate_id: str) -> CandidateIdentity:
        """UNQUALIFIED LOOKUP — rejected fail-closed by design.

        While multiple populations are registered, a bare candidate_id is
        never a sufficient scientific identity, whether it currently hits
        zero, one, or several populations.  This is the guard whose
        absence allowed the 2026-09 native corpus to silently reuse the
        CA0v1 ID range ECP-CAND-000101..000103.
        """
        _require_nonempty_str(candidate_id, "candidate_id")
        holders = [
            record.population_id
            for record in self._populations
            if candidate_id in record.candidate_index
        ]
        if self.population_count > 1:
            raise AmbiguousCandidateIdError(
                "AMBIGUOUS_ID -> REJECTED: a bare candidate_id cannot resolve "
                f"a scientific artifact identity while {self.population_count} "
                "populations are registered; use the population-qualified "
                "lookup(population_id, case_pack_id, case_pack_version, "
                f"candidate_id). Id '{candidate_id}' is present in: "
                f"{', '.join(holders) if holders else 'no indexed population'}"
            )
        if not holders:
            raise UnknownNamespaceError(
                f"candidate_id {candidate_id} is not present in any indexed population"
            )
        return self._populations[0].lookup(candidate_id)

    # -- collision machinery ---------------------------------------------------

    def distinct_identities(self, candidate_id: str) -> tuple[CandidateIdentity, ...]:
        """All identities carried by one candidate_id across namespaces.

        Same candidate_id + different population namespace = distinct
        identities (never equal, never merged).
        """
        _require_nonempty_str(candidate_id, "candidate_id")
        return tuple(
            record.lookup(candidate_id)
            for record in sorted(
                (r for r in self._populations if candidate_id in r.candidate_index),
                key=lambda r: r.population_id,
            )
        )

    def cross_population_overlaps(self) -> dict[str, list[dict[str, str]]]:
        """candidate_ids used by more than one population, with per-population hashes."""
        hits: dict[str, list[dict[str, str]]] = {}
        all_ids = sorted(
            {cid for record in self._populations for cid in record.candidate_index}
        )
        for candidate_id in all_ids:
            holders = [
                {
                    "population_id": record.population_id,
                    "case_pack_id": record.case_pack_id,
                    "case_pack_version": str(record.case_pack_version),
                    "content_hash": record.candidate_index[candidate_id],
                }
                for record in sorted(
                    (r for r in self._populations if candidate_id in r.candidate_index),
                    key=lambda r: r.population_id,
                )
            ]
            if len(holders) > 1:
                hits[candidate_id] = holders
        return hits

    def assert_collision_invariant(self) -> None:
        """same namespace + same candidate_id + different content_hash = COLLISION.

        Structurally impossible after load (PopulationRecord rejects it),
        but asserted here as an explicit, machine-checkable invariant.
        """
        for record in self._populations:
            index = record.candidate_index
            if len(index) != record.candidate_count:
                raise NamespaceCollisionError(
                    f"population {record.population_id}: candidate_count "
                    f"{record.candidate_count} != unique ids {len(index)}"
                )
        return None

    def collision_report(self) -> dict[str, Any]:
        """Machine-readable collision evidence for this index."""
        overlaps = self.cross_population_overlaps()
        return {
            "population_count": self.population_count,
            "within_namespace_collisions": [],  # impossible by construction
            "cross_population_id_overlaps": overlaps,
            "overlap_count": len(overlaps),
            "collision_detected": bool(overlaps),
        }

    # -- manifest loading --------------------------------------------------------

    @classmethod
    def from_manifest_dict(cls, data: Mapping[str, Any]) -> "PopulationNamespaceIndex":
        if not isinstance(data, Mapping):
            raise ValueError("manifest document must be a JSON object")
        if data.get("ecp_object") != MANIFEST_OBJECT:
            raise ValueError(
                f"manifest ecp_object must be '{MANIFEST_OBJECT}', got "
                f"{data.get('ecp_object')!r}"
            )
        populations = data.get("populations")
        if not isinstance(populations, list) or not populations:
            raise ValueError("manifest must carry a non-empty 'populations' list")
        index = cls([PopulationRecord.from_dict(entry) for entry in populations])
        index.assert_collision_invariant()
        return index

    @classmethod
    def from_manifest_file(cls, path: "str | Path | None" = None) -> "PopulationNamespaceIndex":
        manifest_path = Path(path) if path else DEFAULT_MANIFEST_PATH
        with open(manifest_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_manifest_dict(data)


def read_manifest_document(path: "str | Path | None" = None) -> dict[str, Any]:
    """Read the raw manifest document (for governance cross-checks)."""
    manifest_path = Path(path) if path else DEFAULT_MANIFEST_PATH
    with open(manifest_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_manifest(path: "str | Path | None" = None) -> PopulationNamespaceIndex:
    """Convenience alias for :meth:`PopulationNamespaceIndex.from_manifest_file`."""
    return PopulationNamespaceIndex.from_manifest_file(path)
