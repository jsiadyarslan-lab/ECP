"""Universal Target Onboarding Fabric v1 — build the mechanism once.

Governing principle (owner order 2026-09-12):

    Build the onboarding mechanism once
        -> configure/register Targets
        -> reuse the existing universal execution fabric.

This module adds NO new execution path, NO parallel registry and NO second
contract. It is a composition layer over machinery that already exists and is
reused unchanged:

* target/provider/adapter contracts — :mod:`ecp.targets`, :mod:`ecp.adapters`
  and ``schemas/{target,provider,adapter}.schema.json`` (the target document
  IS the universal target contract; its names and structure are followed
  exactly);
* runtime dispatch seam — :class:`ecp.runtime_adapters.RuntimeAdapterRegistry`
  (the single execution registry) and the provider adapters behind it;
* universal execution contract — :mod:`ecp.execution_contract`
  (``ClientExecutionIntent`` -> ``ResolvedUniversalExecutionRequest`` ->
  ``UniversalExecutionResult``, with the frozen ``ExperimentIdentity``);
* credential boundary — :class:`ecp.credentials.CredentialGateway` plus
  :mod:`ecp.credential_binding` (binding / grant / scoped release);
* evaluation + test registration — :class:`ecp.console.AuthorizedEvaluation`
  and :class:`ecp.console.AuthorizedTest`, the registry the evaluation
  console catalog is dynamically built from;
* evidence/audit writers — :class:`ecp.console.LocalGateway` (unchanged).

Onboarding pipeline (owner order §9), each step reusing existing checks:

    target configuration
        -> validation                       (target schema + secret scan)
        -> provider resolution              (ProviderRegistry)
        -> target registration              (TargetRegistry, idempotent)
        -> adapter resolution               (TargetResolver + binding scope)
        -> runtime adapter resolution       (RuntimeAdapterRegistry, strict)
        -> credential resolution            (CredentialGateway metadata)
        -> authorization resolution         (owner-supplied grant diagnostics)
        -> execution readiness              (READY / NOT_READY + reasons)
        -> infrastructure registration      (AuthorizedEvaluation linkage)
        -> persisted target record          (deterministic onboarding record)

Architectural invariants enforced here:

* **Configuration-driven.** A new target is a target document plus a
  configured runtime adapter instance; the exact model identifier is instance
  configuration (``adapter.model``), never core code. No per-model or
  per-provider conditional routing exists anywhere in this module or in the
  universal core seam it composes.
* **Idempotent.** Re-onboarding the same configuration yields the same
  canonical identity (``target_hash``), the same registrations, the same
  linkage and a byte-identical onboarding record — never a duplicate.
* **Fail-closed and deterministic.** Every failure raises a diagnostic error
  built from references and reason codes only; the same input always fails
  with the same error.
* **Authorization is never bypassed.** The :class:`AuthorizationGrant` is an
  owner-supplied input; onboarding performs diagnostics only, and the
  material-release authority remains
  :meth:`ecp.credentials.CredentialGateway.release`. Onboarding never
  provisions, rotates or revokes credentials.
* **Secret-free.** Target configurations and onboarding records are scanned
  for secret-bearing keys and rejected loudly; credential values never enter
  any registry, record or diagnostic message.
* **Freeze respected.** Once a target is onboarded, re-onboarding the same
  target identity with a divergent configuration (different target content,
  model, binding or grant wiring) is a deterministic failure — no model
  switching, no silent adapter substitution, no registry mutation through
  the onboarding path.

This module performs no network access and no provider execution. Following
the established convention for the execution-side fabric (``ecp.console``,
``ecp.runtime_adapters``), it is imported explicitly
(``from ecp.onboarding import TargetOnboardingService``) and is not part of
the lightweight ``ecp`` package root import graph.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .adapters import (
    AdapterRegistry,
    DuplicateAdapter,
    ResolutionError,
    ResolvedTarget,
    TargetResolver,
    UnknownAdapter,
)
from .console import AuthorizedEvaluation, AuthorizedTest
from .credential_binding import (
    AuthorizationGrant,
    BindingScopeError,
    CredentialBinding,
)
from .credentials import (
    CredentialGateway,
    CredentialIdentity,
    CredentialNotFound,
)
from .execution_contract import (
    ClientExecutionIntent,
    ContractResolutionError,
    ContractViolation,
    ExecutionContractResolver,
)
from .hashing import sha256_hex
from .runtime_adapters import (
    RuntimeAdapterBindingError,
    RuntimeAdapterRegistry,
    RuntimeAdapterUnavailable,
)
from .targets import (
    DuplicateProvider,
    DuplicateTarget,
    InvalidTarget,
    ProviderRegistry,
    TargetRegistry,
    UnknownProvider,
    _contains_secret_key,
    target_hash,
)
from .validate import validate_document

#: Readiness check names, in evaluation order (owner order §14).
READINESS_CHECKS = (
    "provider_available",
    "adapter_metadata_available",
    "runtime_adapter_available",
    "model_identified",
    "credential_resolved",
    "authorization_valid",
    "interface_valid",
    "execution_contract_valid",
    "test_available",
)

#: Deterministic request identifier used by the offline readiness probe.
_READINESS_REQUEST_ID = "ECP-ONBOARD-READINESS-PROBE"

#: Marker for a runtime adapter whose model configuration is absent.
_UNCONFIGURED_MODEL = "UNCONFIGURED"

#: Default schema bundle cited by generated onboarding records.
_ONBOARDING_SCHEMA_VERSION = "0.8.0"


class OnboardingError(ValueError):
    """Base error for universal target onboarding failures (diagnostic only)."""


class InvalidTargetConfiguration(OnboardingError):
    """The target configuration is malformed or carries secret-bearing keys."""


class DuplicateTargetConfiguration(OnboardingError):
    """The target identity is already registered with divergent content."""


class ProviderIntegrationMismatch(OnboardingError):
    """Provider/adapter metadata re-registration diverges from the registered entry."""


class RuntimeAdapterMismatch(OnboardingError):
    """The runtime adapter instance does not match the target's declared identity."""


class CredentialNotResolved(OnboardingError):
    """The target credential reference does not resolve in the gateway."""


class AuthorizationNotResolved(OnboardingError):
    """The owner-supplied authorization grant does not cover the binding."""


class AuthorizedTestNotResolved(OnboardingError):
    """A declared test binding has no supplied authorized test."""


class EvaluationConflict(OnboardingError):
    """The evaluation linkage identity is already wired with different wiring."""


class OnboardingNotReady(OnboardingError):
    """The target failed the execution readiness battery."""

    def __init__(self, reasons: "list[str]") -> None:
        self.reasons = list(reasons)
        super().__init__("target is NOT_READY: " + "; ".join(self.reasons))


def _default_protocol_version() -> str:
    try:
        from .identity import protocol_version
        return protocol_version()
    except Exception:  # pragma: no cover - non-checkout installs only
        from .versions import PROTOCOL_VERSIONS
        return PROTOCOL_VERSIONS[-1]


def _parse_grant_expiry(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ReadinessCheck:
    """One readiness battery check result (name, PASS/FAIL, detail)."""

    check: str
    result: str
    detail: str

    def to_document(self) -> dict[str, str]:
        return {"check": self.check, "result": self.result, "detail": self.detail}


@dataclass(frozen=True)
class TargetReadiness:
    """The READY / NOT_READY verdict for one target, with full diagnostics."""

    target_id: str
    state: str
    checks: tuple[ReadinessCheck, ...]

    def failed_details(self) -> "list[str]":
        return [f"{c.check}: {c.detail}" for c in self.checks if c.result != "PASS"]

    def to_document(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "state": self.state,
            "checks": [c.to_document() for c in self.checks],
        }


@dataclass(frozen=True)
class OnboardedTarget:
    """The immutable result of one successful universal onboarding run."""

    onboarding_id: str
    target: dict[str, Any]
    target_hash: str
    resolved: ResolvedTarget
    evaluation: AuthorizedEvaluation
    model_identifier: str
    readiness: TargetReadiness
    registered_now: bool

    def record_document(
        self,
        *,
        protocol_version: str,
        schema_version: str = _ONBOARDING_SCHEMA_VERSION,
    ) -> dict[str, Any]:
        """The deterministic, schema-valid onboarding record for this target.

        The record is a pure function of the registered configuration: no
        timestamps, no run counters — the same configuration always produces
        a byte-identical record (provable idempotency). It carries references
        and verdicts only, never secret material.
        """
        record: dict[str, Any] = {
            "ecp_object": "onboarding-record",
            "onboarding_id": self.onboarding_id,
            "onboarding_version": "1.0.0",
            "protocol_version": protocol_version,
            "schema_version": schema_version,
            "target_id": self.target["target_id"],
            "target_version": self.target["target_version"],
            "target_hash": self.target_hash,
            "system_id": self.target["system"]["system_id"],
            "system_kind": self.target["system"]["system_kind"],
            "provider_id": self.resolved.provider_id,
            "provider_interface": self.resolved.provider_interface,
            "adapter_id": self.resolved.adapter_id,
            "adapter_version": self.resolved.adapter_version,
            "model_identifier": self.model_identifier,
            "credential_ref": self.target["credential_ref"],
            "authorization_ref": self.target["authorization_ref"],
            "binding_id": self.evaluation.credential_binding.binding_id,
            "authorization_grant_ref": self.evaluation.authorization_grant.authorization_ref,
            "evaluation_id": self.evaluation.evaluation_id,
            "test_ids": [t.test_id for t in self.evaluation.tests],
            "readiness_state": self.readiness.state,
            "readiness_checks": [c.to_document() for c in self.readiness.checks],
        }
        return record


@dataclass(frozen=True)
class _TargetWiring:
    """Internal per-target wiring snapshot used for readiness re-checks."""

    target_id: str
    evaluation_id: str
    credential_identity: CredentialIdentity
    binding: CredentialBinding
    grant: AuthorizationGrant
    tests: tuple[AuthorizedTest, ...]
    runtime_adapter: Any


class TargetOnboardingService:
    """The universal target onboarding pipeline over the existing fabric.

    Composes — never duplicates — the provider/target/adapter registries, the
    runtime adapter registry, the credential gateway, the target resolver and
    the universal execution contract. Holds no secrets, performs no network
    access, and mutates no closed foundation layer: every write goes through
    the registries' own ``register`` seams, idempotently.
    """

    def __init__(
        self,
        providers: ProviderRegistry,
        targets: TargetRegistry,
        adapters: AdapterRegistry,
        runtime: RuntimeAdapterRegistry,
        credential_gateway: CredentialGateway,
        *,
        protocol_version: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.providers = providers
        self.targets = targets
        self.adapters = adapters
        self.runtime = runtime
        self.credential_gateway = credential_gateway
        self._protocol_version = protocol_version or _default_protocol_version()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._evaluations: dict[str, AuthorizedEvaluation] = {}
        self._wiring: dict[str, _TargetWiring] = {}
        self._records: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Read-only views for the existing execution fabric
    # ------------------------------------------------------------------

    @property
    def evaluations(self) -> dict[str, AuthorizedEvaluation]:
        """The evaluation registry this service wired (feeds LocalGateway)."""
        return dict(self._evaluations)

    @property
    def records(self) -> "list[dict[str, Any]]":
        """All persisted onboarding records, deterministic order."""
        return [deepcopy(self._records[key]) for key in sorted(self._records)]

    def record(self, onboarding_id: str) -> dict[str, Any]:
        """One persisted onboarding record by its deterministic identifier."""
        try:
            return deepcopy(self._records[onboarding_id])
        except KeyError as exc:
            raise OnboardingError(f"unknown onboarding record {onboarding_id}") from exc

    # ------------------------------------------------------------------
    # Provider integration registration (the "New Provider" path)
    # ------------------------------------------------------------------

    def register_provider_integration(
        self,
        provider: Mapping[str, Any],
        adapter: Mapping[str, Any],
    ) -> None:
        """Idempotently register provider and adapter metadata documents.

        Registering a provider integration is metadata only: it grants no
        execution capability. Equal re-registration is a no-op; divergent
        re-registration under the same identity is a deterministic failure.
        The adapter implementation itself is supplied separately as a runtime
        adapter instance (see :meth:`onboard`).
        """
        provider_document = deepcopy(dict(provider))
        adapter_document = deepcopy(dict(adapter))
        try:
            self.providers.register(provider_document)
        except DuplicateProvider:
            existing = self.providers.get(provider_document["provider_id"])
            if existing != provider_document:
                raise ProviderIntegrationMismatch(
                    f"provider {provider_document['provider_id']} is already "
                    "registered with different metadata"
                ) from None
        try:
            self.adapters.register(adapter_document)
        except DuplicateAdapter:
            existing = self.adapters.get(
                adapter_document["adapter_id"], adapter_document["adapter_version"]
            )
            if existing != adapter_document:
                raise ProviderIntegrationMismatch(
                    f"adapter {adapter_document['adapter_id']}@"
                    f"{adapter_document['adapter_version']} is already "
                    "registered with different metadata"
                ) from None

    # ------------------------------------------------------------------
    # The universal onboarding pipeline (owner order §9)
    # ------------------------------------------------------------------

    def onboard(
        self,
        target_configuration: Mapping[str, Any],
        *,
        runtime_adapter: Any,
        credential_identity: CredentialIdentity,
        binding: CredentialBinding,
        grant: AuthorizationGrant | None,
        tests: Mapping[str, AuthorizedTest],
    ) -> OnboardedTarget:
        """Onboard one target from configuration, through the full pipeline.

        Args:
            target_configuration: a target document (validated against
                ``target.schema.json``; secret-bearing keys rejected).
            runtime_adapter: the executable provider adapter instance for
                this target, configured with the exact model identifier. The
                instance must declare the target's adapter identity and
                provider binding.
            credential_identity: the non-secret credential identity registered
                in the credential gateway (reference only).
            binding: the credential binding linking target, provider,
                interface and credential reference.
            grant: the OWNER-SUPPLIED authorization grant covering the
                binding. Onboarding reports diagnostics only; the release
                authority remains the credential gateway.
            tests: authorized tests for every test binding the target
                declares.

        Returns:
            The immutable :class:`OnboardedTarget` with its readiness verdict
            and deterministic onboarding record.

        Raises:
            OnboardingError subclasses: deterministic, diagnostic failures.
        """
        # --- 1. Validation (reuse the existing target contract) ---------
        if not isinstance(target_configuration, Mapping):
            raise InvalidTargetConfiguration(
                "target configuration must be a JSON-style mapping"
            )
        document = deepcopy(dict(target_configuration))
        if _contains_secret_key(document):
            raise InvalidTargetConfiguration(
                "invalid target configuration: <root>: secret-bearing fields are forbidden"
            )
        issues = validate_document(document, "target")
        if issues:
            raise InvalidTargetConfiguration(
                "invalid target configuration: " + "; ".join(issues)
            )
        target_id = document["target_id"]
        provider_id = document["provider"]["provider_id"]
        adapter_key = document["adapter"]["adapter_id"]

        # --- 2. Provider resolution ------------------------------------
        try:
            provider = self.providers.get(provider_id)
        except UnknownProvider as exc:
            raise OnboardingError(f"unknown provider {provider_id}") from exc
        if provider["status"] != "active":
            raise OnboardingError(f"provider {provider_id} is not active")

        # --- 3. Target registration (idempotent by canonical hash) -----
        registered_now = True
        try:
            self.targets.register(document)
        except DuplicateTarget:
            existing = self.targets.get(target_id)
            if target_hash(existing) != target_hash(document):
                raise DuplicateTargetConfiguration(
                    f"target {target_id} is already registered with a different "
                    "configuration"
                ) from None
            registered_now = False
        # InvalidTarget from the registry propagates: it is already a
        # deterministic, diagnostic validation failure.

        # --- 4. Adapter metadata + binding resolution (reuse resolver) --
        resolver = TargetResolver(self.providers, self.targets, self.adapters)
        try:
            resolved = resolver.resolve_for_binding(target_id, binding)
        except ResolutionError as exc:
            raise OnboardingError(f"adapter resolution failed: {exc}") from exc
        except BindingScopeError as exc:
            raise OnboardingError(f"binding does not match the target: {exc}") from exc
        except InvalidTarget as exc:
            raise OnboardingError(f"target resolution failed: {exc}") from exc

        # --- 5. Runtime adapter resolution (strict, idempotent) --------
        runtime_instance, runtime_registered_now = self._register_runtime_adapter(
            document, runtime_adapter
        )
        model_identifier = getattr(runtime_instance, "model", None)

        # --- 6. Credential resolution (references only, no secrets) ----
        credential_ref = document["credential_ref"]
        try:
            credential_metadata = self.credential_gateway.metadata(credential_ref)
        except CredentialNotFound as exc:
            raise CredentialNotResolved(
                f"credential {credential_ref} is not registered in the gateway"
            ) from exc
        if credential_metadata.get("status") in {"REVOKED", "EXPIRED"}:
            raise CredentialNotResolved(
                f"credential {credential_ref} is {credential_metadata['status']}"
            )
        if credential_metadata.get("provider") != provider_id:
            raise CredentialNotResolved(
                f"credential {credential_ref} belongs to provider "
                f"{credential_metadata.get('provider')!r}; the target requires "
                f"{provider_id!r}"
            )
        if credential_identity.credential_id != credential_ref:
            raise CredentialNotResolved(
                "supplied credential identity does not match the target "
                "credential_ref"
            )

        # --- 7. Authorization resolution (owner-supplied grant) --------
        if grant is None:
            raise AuthorizationNotResolved(
                "authorization grant is required (OWNER DECISION REQUIRED); "
                "onboarding never fabricates authorization"
            )
        authorization_reasons = self._authorization_reasons(binding, grant)
        if authorization_reasons:
            raise AuthorizationNotResolved("; ".join(authorization_reasons))

        # --- 8. Test resolution ----------------------------------------
        test_bindings = list(document["test_bindings"])
        supplied = dict(tests or {})
        missing = [test_id for test_id in test_bindings if test_id not in supplied]
        if missing:
            raise AuthorizedTestNotResolved(
                "no authorized test supplied for test bindings: "
                + ", ".join(missing)
            )
        authorized_tests = tuple(supplied[test_id] for test_id in test_bindings)

        # --- 9. Evaluation linkage + execution readiness (offline probe) -
        evaluation_id = document["evaluation_bindings"][0]
        evaluation = AuthorizedEvaluation(
            evaluation_id,
            document["system"]["system_id"],
            provider_id,
            adapter_key,
            credential_identity,
            authorized_tests,
            binding,
            grant,
        )
        readiness = self._evaluate_readiness(
            document=document,
            evaluation=evaluation,
            runtime_instance=runtime_instance,
        )
        if readiness.state != "READY":
            raise OnboardingNotReady(readiness.failed_details())

        # --- 10. Infrastructure registration (idempotent linkage) ------
        existing_evaluation = self._evaluations.get(evaluation_id)
        if existing_evaluation is not None:
            if not self._same_evaluation(existing_evaluation, evaluation):
                raise EvaluationConflict(
                    f"evaluation {evaluation_id} is already registered with "
                    "different wiring"
                )
        else:
            self._evaluations[evaluation_id] = evaluation
        self._wiring[target_id] = _TargetWiring(
            target_id=target_id,
            evaluation_id=evaluation_id,
            credential_identity=credential_identity,
            binding=binding,
            grant=grant,
            tests=authorized_tests,
            runtime_adapter=runtime_instance,
        )

        # --- 11. Persisted target record (deterministic) ---------------
        onboarded = OnboardedTarget(
            onboarding_id=self._onboarding_id_for(target_hash(document)),
            target=self.targets.get(target_id),
            target_hash=target_hash(document),
            resolved=resolved,
            evaluation=self._evaluations[evaluation_id],
            model_identifier=model_identifier or _UNCONFIGURED_MODEL,
            readiness=readiness,
            registered_now=registered_now or runtime_registered_now
            or existing_evaluation is None,
        )
        record = onboarded.record_document(
            protocol_version=self._protocol_version,
            schema_version=_ONBOARDING_SCHEMA_VERSION,
        )
        record_issues = validate_document(record, "onboarding-record")
        if record_issues or _contains_secret_key(record):  # pragma: no cover - guard
            raise OnboardingError(
                "generated onboarding record is invalid: " + "; ".join(record_issues)
            )
        self._records[onboarded.onboarding_id] = record
        return onboarded

    # ------------------------------------------------------------------
    # Readiness re-check (drift detection, read-only)
    # ------------------------------------------------------------------

    def readiness(self, target_id: str) -> TargetReadiness:
        """Re-run the readiness battery for a previously onboarded target.

        Read-only: detects drift (revoked credential, expired grant,
        deactivated provider or adapter, disabled runtime adapter) and
        reports READY / NOT_READY with diagnostic reasons. It performs no
        registration, no authorization and no network access.
        """
        wiring = self._wiring.get(target_id)
        if wiring is None:
            raise OnboardingError(f"target {target_id} has not been onboarded")
        try:
            target = self.targets.get(target_id)
        except InvalidTarget as exc:  # pragma: no cover - registry integrity
            raise OnboardingError(f"target resolution failed: {exc}") from exc
        evaluation = self._evaluations.get(wiring.evaluation_id)
        if evaluation is None:  # pragma: no cover - wiring integrity
            raise OnboardingError(
                f"evaluation {wiring.evaluation_id} is no longer registered"
            )
        return self._evaluate_readiness(
            document=target,
            evaluation=evaluation,
            runtime_instance=wiring.runtime_adapter,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _onboarding_id_for(hash_hex: str) -> str:
        return f"ECP-ONBOARD-{hash_hex[:16]}"

    def _register_runtime_adapter(
        self, document: Mapping[str, Any], runtime_adapter: Any
    ) -> "tuple[Any, bool]":
        """Register (idempotently) and return the runtime adapter instance.

        The instance must declare exactly the target's adapter identity and
        provider binding. Re-registering the same configured identity is a
        no-op; a divergent configuration under the same adapter identity is
        a deterministic failure (the §7 freeze: no model switching, no silent
        adapter substitution).
        """
        adapter_key = document["adapter"]["adapter_id"]
        provider_id = document["provider"]["provider_id"]
        declared = getattr(runtime_adapter, "adapter_id", None)
        adapter_provider = getattr(runtime_adapter, "provider", None)
        if declared != adapter_key:
            raise RuntimeAdapterMismatch(
                f"runtime adapter declares identity {declared!r}; the target "
                f"requires {adapter_key!r}"
            )
        if adapter_provider != provider_id:
            raise RuntimeAdapterMismatch(
                f"runtime adapter is bound to provider {adapter_provider!r}; "
                f"the target requires {provider_id!r}"
            )
        existing = self.runtime.get(adapter_key)
        if existing is None:
            self.runtime.register(adapter_key, runtime_adapter)
            return self.runtime.get(adapter_key), True
        existing_identity = (
            getattr(existing, "adapter_id", adapter_key),
            getattr(existing, "provider", ""),
            getattr(existing, "model", None),
        )
        supplied_identity = (declared, adapter_provider, getattr(runtime_adapter, "model", None))
        if existing_identity != supplied_identity:
            raise RuntimeAdapterMismatch(
                f"runtime adapter {adapter_key} is already registered with a "
                "different configuration (provider or model identity differs); "
                "re-onboarding cannot switch the frozen configuration — use a "
                "new target configuration instead"
            )
        return existing, False

    def _authorization_reasons(
        self, binding: CredentialBinding, grant: AuthorizationGrant
    ) -> "list[str]":
        """Diagnostic authorization checks (the release authority is the gateway)."""
        reasons: "list[str]" = []
        if grant.status != "GRANTED":
            reasons.append(f"authorization grant status is {grant.status}")
        if grant.binding_id != binding.binding_id:
            reasons.append("authorization grant does not match the binding")
        if grant.target_id != binding.target_id:
            reasons.append("authorization grant does not match the binding target")
        if grant.purpose != binding.purpose:
            reasons.append("authorization grant purpose does not match the binding purpose")
        if not set(binding.scope).issubset(grant.scope):
            reasons.append("authorization grant scope does not cover the binding scope")
        now = self._clock().astimezone(timezone.utc)
        if now >= _parse_grant_expiry(grant.expires_at):
            reasons.append("authorization grant has expired")
        return reasons

    def _evaluate_readiness(
        self,
        *,
        document: Mapping[str, Any],
        evaluation: AuthorizedEvaluation,
        runtime_instance: Any,
    ) -> TargetReadiness:
        """Run the nine readiness checks (owner order §14). Read-only."""
        target_id = document["target_id"]
        provider_id = document["provider"]["provider_id"]
        interface = document["provider"]["interface"]
        adapter_id = document["adapter"]["adapter_id"]
        adapter_version = document["adapter"]["adapter_version"]
        credential_ref = document["credential_ref"]
        binding = evaluation.credential_binding
        grant = evaluation.authorization_grant
        checks: "list[ReadinessCheck]" = []
        provider: dict[str, Any] | None = None
        adapter_interface_matches = False

        def record(check: str, ok: bool, detail: str) -> None:
            checks.append(ReadinessCheck(check, "PASS" if ok else "FAIL", detail))

        # 1. provider available
        try:
            provider = self.providers.get(provider_id)
            ok = provider["status"] == "active"
            record(
                "provider_available",
                ok,
                f"provider {provider_id} is active"
                if ok
                else f"provider {provider_id} is {provider['status']}",
            )
        except UnknownProvider as exc:
            record("provider_available", False, str(exc))

        # 2. adapter metadata available
        try:
            adapter_meta = self.adapters.get(adapter_id, adapter_version)
            ok = adapter_meta["status"] == "active"
            record(
                "adapter_metadata_available",
                ok,
                f"adapter {adapter_id}@{adapter_version} is active"
                if ok
                else f"adapter {adapter_id}@{adapter_version} is {adapter_meta['status']}",
            )
            adapter_interface_matches = (
                adapter_meta["provider_interface"] == interface
            )
        except UnknownAdapter as exc:
            record("adapter_metadata_available", False, str(exc))
            adapter_interface_matches = False

        # 3. runtime adapter available
        try:
            self.runtime.resolve(adapter_id, provider_id)
            record(
                "runtime_adapter_available",
                True,
                f"runtime adapter {adapter_id} is registered and enabled",
            )
        except (RuntimeAdapterUnavailable, RuntimeAdapterBindingError) as exc:
            record("runtime_adapter_available", False, str(exc))

        # 4. exact model/system identified
        model = getattr(runtime_instance, "model", None)
        if isinstance(model, str) and model.strip() and model != _UNCONFIGURED_MODEL:
            record("model_identified", True, f"model identifier is configured: {model}")
        else:
            record(
                "model_identified",
                False,
                "model identifier is not configured on the runtime adapter "
                f"(found {model!r})",
            )

        # 5. credential_ref valid
        try:
            metadata = self.credential_gateway.metadata(credential_ref)
            status = metadata.get("status")
            provider_match = metadata.get("provider") == provider_id
            ok = status not in {"REVOKED", "EXPIRED"} and provider_match
            if status in {"REVOKED", "EXPIRED"}:
                detail = f"credential {credential_ref} is {status}"
            elif not provider_match:
                detail = (
                    f"credential {credential_ref} belongs to provider "
                    f"{metadata.get('provider')!r}; the target requires {provider_id!r}"
                )
            else:
                detail = f"credential {credential_ref} is registered and resolves"
            record("credential_resolved", ok, detail)
        except CredentialNotFound as exc:
            record("credential_resolved", False, str(exc))

        # 6. authorization valid
        if grant is None:
            record(
                "authorization_valid",
                False,
                "authorization grant is missing (OWNER DECISION REQUIRED)",
            )
        else:
            reasons = self._authorization_reasons(binding, grant)
            record(
                "authorization_valid",
                not reasons,
                "authorization grant is active and covers the binding"
                if not reasons
                else "; ".join(reasons),
            )

        # 7. interface valid
        provider_declares = (
            provider is not None and interface in provider.get("interfaces", [])
        )
        interface_ok = provider_declares and adapter_interface_matches
        record(
            "interface_valid",
            interface_ok,
            f"interface {interface} is declared by the provider and the adapter contract"
            if interface_ok
            else f"interface {interface} is not consistently declared "
            f"(provider declares: "
            f"{provider.get('interfaces') if provider is not None else 'unknown provider'})",
        )

        # 8. execution contract valid (offline probe through the real path)
        try:
            probe_resolver = ExecutionContractResolver(
                {evaluation.evaluation_id: evaluation}, None, self.runtime
            )
            first_test = evaluation.tests[0].test_id if evaluation.tests else None
            if first_test is None:
                raise ContractResolutionError("evaluation has no tests")
            probe_resolver.resolve(
                ClientExecutionIntent(
                    evaluation_id=evaluation.evaluation_id,
                    test_id=first_test,
                    system_id=evaluation.system_id,
                    credential_ref=credential_ref,
                    request_id=_READINESS_REQUEST_ID,
                )
            )
            record(
                "execution_contract_valid",
                True,
                "the universal execution contract resolves the evaluation, "
                "system, credential, test and authorization",
            )
        except (ContractResolutionError, ContractViolation) as exc:
            record("execution_contract_valid", False, str(exc))

        # 9. test available
        test_bindings = list(document["test_bindings"])
        wired = tuple(t.test_id for t in evaluation.tests)
        missing_tests = [t for t in test_bindings if t not in wired]
        if test_bindings and not missing_tests:
            record(
                "test_available",
                True,
                f"authorized tests are available: {', '.join(test_bindings)}",
            )
        else:
            record(
                "test_available",
                False,
                "test bindings without an available authorized test: "
                + (", ".join(missing_tests) or "no test bindings declared"),
            )

        ordered = sorted(checks, key=lambda c: READINESS_CHECKS.index(c.check))
        state = "READY" if all(c.result == "PASS" for c in ordered) else "NOT_READY"
        return TargetReadiness(target_id=target_id, state=state, checks=tuple(ordered))

    @staticmethod
    def _same_evaluation(a: AuthorizedEvaluation, b: AuthorizedEvaluation) -> bool:
        """Structural wiring equality for idempotent linkage checks."""
        return (
            a.evaluation_id == b.evaluation_id
            and a.system_id == b.system_id
            and a.provider == b.provider
            and a.adapter == b.adapter
            and a.credential.credential_id == b.credential.credential_id
            and tuple(t.test_id for t in a.tests) == tuple(t.test_id for t in b.tests)
            and a.credential_binding is not None
            and b.credential_binding is not None
            and a.credential_binding.binding_id == b.credential_binding.binding_id
            and a.authorization_grant is not None
            and b.authorization_grant is not None
            and a.authorization_grant.authorization_ref
            == b.authorization_grant.authorization_ref
        )


__all__ = [
    "AuthorizationNotResolved",
    "CredentialNotResolved",
    "DuplicateTargetConfiguration",
    "EvaluationConflict",
    "InvalidTargetConfiguration",
    "OnboardedTarget",
    "OnboardingError",
    "OnboardingNotReady",
    "ProviderIntegrationMismatch",
    "READINESS_CHECKS",
    "ReadinessCheck",
    "RuntimeAdapterMismatch",
    "TargetOnboardingService",
    "TargetReadiness",
    "AuthorizedTestNotResolved",
]
