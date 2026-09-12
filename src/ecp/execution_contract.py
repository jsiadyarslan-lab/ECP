"""Universal Experiment Execution Contract v1.

Conceptual path (one contract for every provider/model):

    ClientExecutionIntent
        -> Internal Resolution (ExecutionContractResolver)
        -> ResolvedUniversalExecutionRequest
        -> Existing RuntimeAdapterRegistry  (the single execution registry)
        -> Provider Adapter
        -> UniversalExecutionResult
        -> Evidence
        -> Audit

Architectural invariant (owner order 2026-09-12):

    Adapter = how to reach a provider (transport contract).
    Model   = identity/configuration of the system to run.

Changing a model identifier or model configuration never requires a new
adapter; only a genuinely different provider transport contract does.

Boundary invariants enforced by this module:

* The client may supply ONLY execution identifiers (ClientExecutionIntent).
  Arbitrary prompts, endpoints, provider transports, ground truth, or scoring
  semantics are rejected loudly at the intent boundary.
* The resolved request is built internally from registered artifacts
  (evaluation registration, runtime adapter registration, registered case
  artifacts); the client cannot force resolved values.
* In the scientific path the registered case artifact is the sole prompt
  authority: the resolved request carries case_id, case_artifact_hash, and
  prompt_hash; the full prompt text stays server-side (evidence records only
  the reference, never the protected text).
* The universal execution result carries execution/transport facts only. It
  structurally cannot carry ground truth, expected classes, or scientific
  scores: payloads containing scientific keys are rejected (ContractViolation),
  never silently stored.
* Scientific evaluation (ground truth, scoring, adjudication) remains a
  separate downstream layer over Evidence; it is out of scope here by design.

This module adds NO new runner and NO parallel adapter registry: execution
continues to dispatch through the existing
:class:`ecp.runtime_adapters.RuntimeAdapterRegistry`, and authorization
continues through the existing credential binding / grant / lease machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlparse

from .hashing import hash_document

#: Identity of the local execution runtime that resolves requests.
RUNTIME_IDENTITY = "ECP-RUNTIME-LOCAL-GATEWAY-1"

#: The only fields a client may send for an execution (order §4).
INTENT_FIELDS = ("evaluation_id", "test_id", "system_id", "credential_ref", "request_id")

#: Scientific adjudication keys that must NEVER appear in a provider payload
#: (order §7: execution is not an adjudicator).
SCIENTIFIC_RESULT_KEYS = frozenset({
    "ground_truth",
    "ground_truth_class",
    "ground_truth_statement",
    "expected_class",
    "expected_property",
    "intended_correct_answer",
    "correct_answer",
    "answer_key",
    "score",
    "scientific_score",
    "reasoning_family_score",
    "scoring",
    "adjudication",
    "scientific_adjudication",
    "scientific_result",
})

#: Secret-bearing key names dropped from provider payloads (defense in depth;
#: the gateway additionally value-redacts anything containing the lease secret).
SECRET_BEARING_KEYS = frozenset({
    "secret",
    "secret_value",
    "api_key",
    "token",
    "authorization",
    "password",
    "credential",
    "credential_value",
    "key",
})


class ContractViolation(ValueError):
    """A universal execution contract boundary was violated."""


class ContractResolutionError(ValueError):
    """Base class for internal resolution failures."""


class UnknownEvaluationError(ContractResolutionError):
    pass


class UnknownCredentialError(ContractResolutionError):
    pass


class UnknownTestError(ContractResolutionError):
    pass


class ExecutionNotAuthorizedError(ContractResolutionError):
    pass


def _default_protocol_version() -> str:
    try:
        from .identity import protocol_version
        return protocol_version()
    except Exception:  # pragma: no cover - non-checkout installs only
        from .versions import PROTOCOL_VERSIONS
        return PROTOCOL_VERSIONS[-1]


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


# ---------------------------------------------------------------------------
# Layer 1 — ClientExecutionIntent (what the client is allowed to ask for)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClientExecutionIntent:
    """The complete set of values a client may control for one execution.

    Exactly the five authorized identifiers (order §4). Nothing else — no
    prompt, no endpoint, no provider transport, no ground truth — can enter
    the execution path from the client side.
    """

    evaluation_id: str
    test_id: str
    system_id: str
    credential_ref: str
    request_id: str

    @classmethod
    def from_client_payload(cls, payload: Mapping[str, Any]) -> "ClientExecutionIntent":
        """Parse and enforce the client boundary on a raw request payload."""
        if not isinstance(payload, Mapping):
            raise ContractViolation("request must be a JSON object")
        keys = set(payload)
        if keys != set(INTENT_FIELDS):
            raise ContractViolation("request fields are not exactly the authorized identifiers")
        values: dict[str, str] = {}
        for name in INTENT_FIELDS:
            value = payload[name]
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation("request identifiers must be non-empty strings")
            values[name] = value
        return cls(**values)

    def identifiers(self) -> dict[str, str]:
        return {
            "evaluation_id": self.evaluation_id,
            "test_id": self.test_id,
            "system_id": self.system_id,
            "credential_ref": self.credential_ref,
            "request_id": self.request_id,
        }


# ---------------------------------------------------------------------------
# Registered case artifacts — the sole prompt authority (order §6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegisteredCaseArtifact:
    """A server-side registered case artifact backing one registered test.

    The scientific prompt is derived ONLY from this record. ``prompt_hash``
    proves which prompt text was used; ``case_artifact_hash`` pins the case
    identity. ``protected`` keeps the full prompt text out of public records
    (evidence carries the reference, not the text).
    """

    case_id: str
    case_artifact_hash: str
    prompt: str
    prompt_hash: str
    protected: bool = True

    def __post_init__(self) -> None:
        if not self.case_id or not isinstance(self.case_id, str):
            raise ContractViolation("case artifact requires a case_id")
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ContractViolation("case artifact requires a non-empty prompt")
        computed = hash_document({"prompt": self.prompt})
        if self.prompt_hash != computed:
            raise ContractViolation("case artifact prompt_hash does not match its prompt")

    @classmethod
    def for_prompt(
        cls,
        case_id: str,
        prompt: str,
        *,
        case_artifact_hash: str | None = None,
        protected: bool = True,
    ) -> "RegisteredCaseArtifact":
        """Register a case artifact from its case identity and prompt text."""
        prompt_hash = hash_document({"prompt": prompt})
        artifact_hash = case_artifact_hash or hash_document(
            {"case_id": case_id, "prompt_hash": prompt_hash}
        )
        return cls(case_id, artifact_hash, prompt, prompt_hash, protected)

    def prompt_reference(self) -> str:
        mode = "protected" if self.protected else "inline"
        return f"{mode}:{self.case_id}:{self.prompt_hash}"


# ---------------------------------------------------------------------------
# Experiment identity (order §9) — freezable, provable
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentIdentity:
    """The frozen identity of one experiment binding (system x case).

    This is experiment identity, not model implementation: it pins the
    provider, the exact model identifier, the adapter identity/version, the
    protocol and runtime identity, the configuration identity, the tools and
    retrieval policies, and the case/prompt authority fields.
    """

    system_id: str
    provider_id: str
    model_identifier: str
    adapter_id: str
    adapter_version: str
    protocol_version: str
    runtime_identity: str
    configuration_hash: str
    tools_policy: str
    retrieval_policy: str
    case_id: str | None = None
    case_artifact_hash: str | None = None
    prompt_hash: str | None = None

    def identity_document(self) -> dict[str, Any]:
        return {
            "system_id": self.system_id,
            "provider_id": self.provider_id,
            "model_identifier": self.model_identifier,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "protocol_version": self.protocol_version,
            "runtime_identity": self.runtime_identity,
            "configuration_hash": self.configuration_hash,
            "tools_policy": self.tools_policy,
            "retrieval_policy": self.retrieval_policy,
            "case_id": self.case_id,
            "case_artifact_hash": self.case_artifact_hash,
            "prompt_hash": self.prompt_hash,
        }

    def identity_hash(self) -> str:
        return hash_document(self.identity_document())


# ---------------------------------------------------------------------------
# Layer 2 — ResolvedUniversalExecutionRequest (internal resolution output)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedUniversalExecutionRequest:
    """Everything the actual execution needs, resolved from registration.

    Built exclusively by :class:`ExecutionContractResolver` from registered
    artifacts; the client cannot force any resolved value. Carries NO ground
    truth and NO scoring semantics — adjudication is a downstream layer over
    Evidence, never part of the execution request.
    """

    intent: ClientExecutionIntent
    experiment: ExperimentIdentity
    test_label: str
    test_scope: str
    binding_id: str
    grant_id: str
    prompt: str | None = field(default=None)
    prompt_reference: str | None = field(default=None)

    @property
    def evaluation_id(self) -> str:
        return self.intent.evaluation_id

    @property
    def test_id(self) -> str:
        return self.intent.test_id

    @property
    def system_id(self) -> str:
        return self.intent.system_id

    @property
    def credential_ref(self) -> str:
        return self.intent.credential_ref

    @property
    def request_id(self) -> str:
        return self.intent.request_id

    @property
    def provider_id(self) -> str:
        return self.experiment.provider_id

    @property
    def model_identifier(self) -> str:
        return self.experiment.model_identifier

    @property
    def adapter_id(self) -> str:
        return self.experiment.adapter_id

    @property
    def adapter_version(self) -> str:
        return self.experiment.adapter_version

    @property
    def protocol_version(self) -> str:
        return self.experiment.protocol_version

    def transport_request(self) -> dict[str, str]:
        """The string mapping handed to the provider adapter at execution.

        Contains client identifiers (echoed for traceability) plus the
        server-resolved identity fields and, when a registered case artifact
        backs the test, the authoritative prompt. The adapter is the provider
        transport; the model/prompt live in configuration and registration,
        never in adapter code.
        """
        request: dict[str, str] = dict(self.intent.identifiers())
        request.update({
            "provider_id": self.experiment.provider_id,
            "model_identifier": self.experiment.model_identifier,
            "adapter_id": self.experiment.adapter_id,
            "adapter_version": self.experiment.adapter_version,
            "protocol_version": self.experiment.protocol_version,
        })
        if self.prompt is not None:
            request["prompt"] = self.prompt
            request["prompt_hash"] = self.experiment.prompt_hash or ""
        if self.experiment.case_id is not None:
            request["case_id"] = self.experiment.case_id
        return request


# ---------------------------------------------------------------------------
# Layer 3 — UniversalExecutionResult (provider/model-independent facts)
# ---------------------------------------------------------------------------


#: Provider payload keys with defined universal meanings.
KNOWN_PAYLOAD_KEYS = frozenset({"provider_status", "response_id", "model", "output_text", "request_id"})


@dataclass(frozen=True)
class UniversalExecutionResult:
    """Normalized execution/transport facts, independent of provider/model.

    Carries ONLY execution facts (order §7): transport status, provider
    status, normalized output, response/execution metadata. Ground truth,
    expected classes, and scientific scores are structurally refused
    (``from_provider_payload`` raises ContractViolation) — execution is not
    an adjudicator.
    """

    transport_status: str
    provider_status: str | None
    normalized_output: str | None
    response_metadata: dict[str, Any]
    execution_metadata: dict[str, str]
    provider_extras: dict[str, Any]

    @classmethod
    def from_provider_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        request_id: str,
    ) -> "UniversalExecutionResult":
        """Normalize one adapter payload into the universal result.

        Rejects scientific keys loudly, drops secret-bearing keys, maps the
        known transport facts to universal fields, and keeps remaining scalar
        values as provider extras for traceability.
        """
        if not isinstance(payload, Mapping):
            raise ContractViolation("provider payload must be a mapping")
        scientific = sorted(SCIENTIFIC_RESULT_KEYS & {str(k) for k in payload})
        if scientific:
            raise ContractViolation(
                "provider payload carries forbidden scientific keys: " + ", ".join(scientific)
            )
        cleaned = {
            key: value
            for key, value in payload.items()
            if str(key).lower() not in SECRET_BEARING_KEYS
        }
        provider_status = cleaned.get("provider_status")
        if provider_status is not None and not isinstance(provider_status, str):
            raise ContractViolation("provider_status must be a string")
        response_id = cleaned.get("response_id")
        provider_model = cleaned.get("model")
        normalized_output = cleaned.get("output_text")
        if normalized_output is not None and not isinstance(normalized_output, str):
            raise ContractViolation("output_text must be a string")
        execution_request_id = cleaned.get("request_id", request_id)
        if not isinstance(execution_request_id, str):
            raise ContractViolation("request_id must be a string")
        response_metadata: dict[str, Any] = {}
        if isinstance(response_id, str):
            response_metadata["response_id"] = response_id
        if isinstance(provider_model, str):
            response_metadata["model"] = provider_model
        extras = {
            key: value
            for key, value in cleaned.items()
            if str(key) not in KNOWN_PAYLOAD_KEYS and _scalar(value)
        }
        return cls(
            transport_status="RECEIVED",
            provider_status=provider_status if isinstance(provider_status, str) else None,
            normalized_output=normalized_output,
            response_metadata=response_metadata,
            execution_metadata={"request_id": execution_request_id},
            provider_extras=extras,
        )

    def to_record_dict(self) -> dict[str, Any]:
        """Flat, redaction-friendly record form (scalars only)."""
        record: dict[str, Any] = {
            "transport_status": self.transport_status,
            "provider_status": self.provider_status,
            "normalized_output": self.normalized_output,
        }
        record.update(self.response_metadata)
        record.update(self.execution_metadata)
        record.update(self.provider_extras)
        return record


# ---------------------------------------------------------------------------
# Internal resolution (order §5 path)
# ---------------------------------------------------------------------------


class ExecutionContractResolver:
    """Resolve a ClientExecutionIntent against registered artifacts.

    Resolution path (order §5):

        Client identifiers
            -> Gateway
            -> registered artifacts (evaluation registration, runtime adapter
               registration, registered case artifacts)
            -> ResolvedUniversalExecutionRequest

    The resolver performs NO authorization (binding/grant checks are reported,
    the credential gateway remains the release authority), NO network access,
    and NO writes: ``resolve`` is a pure function of its registrations.
    """

    def __init__(
        self,
        evaluations: Mapping[str, Any],
        cases: Mapping[str, RegisteredCaseArtifact] | None = None,
        runtime_registry: Any | None = None,
        *,
        protocol_version: str | None = None,
        runtime_identity: str = RUNTIME_IDENTITY,
        tools_policy: str = "NONE-DECLARED",
        retrieval_policy: str = "NONE-DECLARED",
    ) -> None:
        self._evaluations = dict(evaluations)
        self._cases = dict(cases or {})
        self._runtime = runtime_registry
        self._protocol_version = protocol_version or _default_protocol_version()
        self._runtime_identity = runtime_identity
        self._tools_policy = tools_policy
        self._retrieval_policy = retrieval_policy

    @property
    def runtime_registry(self) -> Any:
        """The single execution registry this resolver resolves against."""
        return self._runtime

    def register(self, evaluation: Any) -> None:
        """Register one additional authorized evaluation (additive seam).

        Console sessions that onboard targets at runtime (for example the
        universal provider discovery console) register the resulting
        evaluation here so execution continues to flow through this single
        resolver. Structural wiring is not validated by this seam — the
        evaluation must already be fully wired (credential binding and
        authorization grant included) by its onboarding path.
        """
        evaluation_id = getattr(evaluation, "evaluation_id", None)
        if not isinstance(evaluation_id, str) or not evaluation_id.strip():
            raise ContractViolation("registered evaluations require an evaluation_id")
        self._evaluations[evaluation_id] = evaluation

    def resolve(self, intent: ClientExecutionIntent) -> ResolvedUniversalExecutionRequest:
        if not isinstance(intent, ClientExecutionIntent):
            raise ContractViolation("resolve requires a ClientExecutionIntent")
        evaluation = self._evaluations.get(intent.evaluation_id)
        if evaluation is None or evaluation.system_id != intent.system_id:
            raise UnknownEvaluationError("unknown evaluation or system")
        if evaluation.credential.credential_id != intent.credential_ref:
            raise UnknownCredentialError("unknown credential_ref")
        test = next((x for x in evaluation.tests if x.test_id == intent.test_id), None)
        if test is None:
            raise UnknownTestError("unknown test")
        if evaluation.credential_binding is None or evaluation.authorization_grant is None:
            raise ExecutionNotAuthorizedError(
                "credential binding and authorization grant are required"
            )
        case = self._cases.get(intent.test_id)
        adapter = self._runtime.get(evaluation.adapter) if self._runtime is not None else None
        model_identifier = getattr(adapter, "model", None) or "UNCONFIGURED"
        adapter_version = getattr(adapter, "adapter_version", None) or "RUNTIME-UNVERSIONED"
        endpoint = getattr(adapter, "endpoint", None)
        endpoint_host = urlparse(endpoint).hostname if endpoint else None
        configuration = {
            "adapter_id": evaluation.adapter,
            "provider_id": evaluation.provider,
            "model_identifier": model_identifier,
            "endpoint_host": endpoint_host,
        }
        experiment = ExperimentIdentity(
            system_id=intent.system_id,
            provider_id=evaluation.provider,
            model_identifier=model_identifier,
            adapter_id=evaluation.adapter,
            adapter_version=adapter_version,
            protocol_version=self._protocol_version,
            runtime_identity=self._runtime_identity,
            configuration_hash=hash_document(configuration),
            tools_policy=self._tools_policy,
            retrieval_policy=self._retrieval_policy,
            case_id=case.case_id if case is not None else None,
            case_artifact_hash=case.case_artifact_hash if case is not None else None,
            prompt_hash=case.prompt_hash if case is not None else None,
        )
        return ResolvedUniversalExecutionRequest(
            intent=intent,
            experiment=experiment,
            test_label=test.label,
            test_scope=test.scope,
            binding_id=evaluation.credential_binding.binding_id,
            grant_id=evaluation.authorization_grant.authorization_ref,
            prompt=case.prompt if case is not None else None,
            prompt_reference=case.prompt_reference() if case is not None else None,
        )


__all__ = [
    "ClientExecutionIntent",
    "ContractResolutionError",
    "ContractViolation",
    "ExecutionContractResolver",
    "ExecutionNotAuthorizedError",
    "ExperimentIdentity",
    "RegisteredCaseArtifact",
    "ResolvedUniversalExecutionRequest",
    "RUNTIME_IDENTITY",
    "UniversalExecutionResult",
    "UnknownCredentialError",
    "UnknownEvaluationError",
    "UnknownTestError",
]
