from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol


class Specialist(StrEnum):
    HERCULES = "hercules"
    HADES = "hades"


class Route(StrEnum):
    FOUNDRY = "foundry"
    SHAREPOINT = "sharepoint"
    DATABRICKS = "databricks"
    BOTH = "both"

    @property
    def specialists(self) -> tuple[Specialist, ...]:
        if self in {Route.FOUNDRY, Route.SHAREPOINT}:
            return (Specialist.HERCULES,)
        if self is Route.DATABRICKS:
            return (Specialist.HADES,)
        return (Specialist.HERCULES, Specialist.HADES)


class ResponseStatus(StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ACCESS_DENIED = "access_denied"
    INVALID_REQUEST = "invalid_request"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AccessDecision(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"


class TrustedState(StrEnum):
    UNTRUSTED = "untrusted"


class HostStage(StrEnum):
    RECEIVED = "received"
    ROUTED = "routed"
    RETRIEVING = "retrieving"
    RETRIEVED = "retrieved"
    SYNTHESIZING = "synthesizing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


def _empty_attributes() -> dict[str, str]:
    return {}


class RedactedCredential:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"


class DelegatedToken(RedactedCredential):
    pass


class FoundryCallContext(RedactedCredential):
    pass


@dataclass(frozen=True)
class CallerContext:
    subject_id: str
    tenant_id: str
    credential: DelegatedToken | FoundryCallContext = field(repr=False, compare=False)

    @property
    def is_complete(self) -> bool:
        return bool(
            self.subject_id.strip() and self.tenant_id.strip() and self.credential.value.strip()
        )


@dataclass(frozen=True)
class Evidence:
    source_id: str
    uri: str
    text: str
    score: float
    attributes: Mapping[str, str] = field(default_factory=_empty_attributes)

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.uri.strip() or not self.text.strip():
            raise ValueError("Evidence source_id, uri, and text must be non-blank")
        if not math.isfinite(self.score):
            raise ValueError("Evidence score must be finite")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


@dataclass(frozen=True)
class RetrievalOutcome:
    decision: AccessDecision
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        if self.decision is AccessDecision.DENIED and self.evidence:
            raise ValueError("Denied retrieval outcomes cannot contain evidence")


@dataclass(frozen=True)
class CitedEvidence:
    citation_id: str
    source_id: str
    uri: str
    text: str
    score: float
    attributes: Mapping[str, str]
    trust: TrustedState = TrustedState.UNTRUSTED


@dataclass(frozen=True)
class Citation:
    citation_id: str
    source_id: str
    uri: str


@dataclass(frozen=True)
class SynthesisRequest:
    prompt: str
    evidence: tuple[CitedEvidence, ...]


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0 or self.cost < 0:
            raise ValueError("Usage values cannot be negative")


@dataclass(frozen=True)
class SynthesisResult:
    answer: str
    usage: Usage = Usage()


@dataclass(frozen=True)
class HostTelemetry:
    retrieval_calls: int = 0
    synthesis_calls: int = 0
    retries: int = 0
    usage: Usage = Usage()


class RetryableHostError(RuntimeError):
    pass


class Retriever(Protocol):
    def retrieve(self, prompt: str, caller: CallerContext) -> RetrievalOutcome: ...


class Synthesizer(Protocol):
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult: ...


class CancellationCheck(Protocol):
    def is_cancelled(self) -> bool: ...


class NeverCancelled:
    def is_cancelled(self) -> bool:
        return False


@dataclass(frozen=True)
class HostDependencies:
    hercules: Retriever
    hades: Retriever
    synthesizer: Synthesizer
    cancellation: CancellationCheck = field(default_factory=NeverCancelled)
    max_attempts: int = 2

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.max_attempts > 3:
            raise ValueError("max_attempts must be between 1 and 3")

    def retriever_for(self, specialist: Specialist) -> Retriever:
        if specialist is Specialist.HERCULES:
            return self.hercules
        return self.hades


@dataclass(frozen=True)
class HostRequest:
    request_id: str
    prompt: str
    route: Route
    caller: CallerContext | None


@dataclass(frozen=True)
class StageEvent:
    stage: HostStage
    actor: str
    specialist: Specialist | None = None


@dataclass(frozen=True)
class HostResponse:
    request_id: str
    status: ResponseStatus
    answer: str
    route: tuple[Specialist, ...]
    citations: tuple[Citation, ...]
    stages: tuple[StageEvent, ...]
    telemetry: HostTelemetry
    failure_code: str | None = None
    entrypoint: str = "zeus"


_INVALID_REQUEST = "A non-blank prompt and delegated caller identity are required."
_ACCESS_DENIED = (
    "The source denied access to the requested evidence. Request access from its owner."
)
_INSUFFICIENT_EVIDENCE = "I do not have enough authorized evidence to answer that request."
_CANCELLED = "The request was cancelled."
_FAILED = "Zeus could not complete the request. Retry, or contact support if the problem continues."


def handle_request(request: HostRequest, dependencies: HostDependencies) -> HostResponse:
    stages = [StageEvent(HostStage.RECEIVED, "zeus")]
    route = request.route.specialists
    retrieval_calls = 0
    retries = 0
    if not request.prompt.strip() or request.caller is None or not request.caller.is_complete:
        stages.append(StageEvent(HostStage.REJECTED, "zeus"))
        return _response(
            request, ResponseStatus.INVALID_REQUEST, _INVALID_REQUEST, route, (), stages
        )

    stages.append(StageEvent(HostStage.ROUTED, "zeus"))
    retrieved: list[Evidence] = []
    for specialist in route:
        if dependencies.cancellation.is_cancelled():
            return _cancelled(request, route, stages, retrieval_calls, retries)
        stages.append(StageEvent(HostStage.RETRIEVING, "zeus", specialist))
        outcome: RetrievalOutcome | None = None
        for attempt in range(1, dependencies.max_attempts + 1):
            retrieval_calls += 1
            try:
                outcome = dependencies.retriever_for(specialist).retrieve(
                    request.prompt, request.caller
                )
                break
            except RetryableHostError:
                if attempt == dependencies.max_attempts:
                    stages.append(StageEvent(HostStage.FAILED, "zeus", specialist))
                    return _failed(
                        request,
                        route,
                        stages,
                        retrieval_calls,
                        retries,
                        "retrieval_failed",
                    )
                retries += 1
                stages.append(StageEvent(HostStage.RETRYING, "zeus", specialist))
            except Exception:
                stages.append(StageEvent(HostStage.FAILED, "zeus", specialist))
                return _failed(request, route, stages, retrieval_calls, retries, "retrieval_failed")
        if outcome is None:
            raise RuntimeError("retrieval attempt completed without an outcome")
        if outcome.decision is AccessDecision.DENIED:
            stages.append(StageEvent(HostStage.REJECTED, "zeus", specialist))
            return _response(
                request,
                ResponseStatus.ACCESS_DENIED,
                _ACCESS_DENIED,
                route,
                (),
                stages,
                HostTelemetry(retrieval_calls=retrieval_calls, retries=retries),
            )
        retrieved.extend(outcome.evidence)
        stages.append(StageEvent(HostStage.RETRIEVED, "zeus", specialist))

    if not retrieved:
        stages.append(StageEvent(HostStage.COMPLETED, "zeus"))
        return _response(
            request,
            ResponseStatus.INSUFFICIENT_EVIDENCE,
            _INSUFFICIENT_EVIDENCE,
            route,
            (),
            stages,
            HostTelemetry(retrieval_calls=retrieval_calls, retries=retries),
        )

    if dependencies.cancellation.is_cancelled():
        return _cancelled(request, route, stages, retrieval_calls, retries)
    cited = tuple(_cite(evidence, index) for index, evidence in enumerate(retrieved, start=1))
    stages.append(StageEvent(HostStage.SYNTHESIZING, "zeus"))
    try:
        synthesis = dependencies.synthesizer.synthesize(SynthesisRequest(request.prompt, cited))
    except Exception:
        stages.append(StageEvent(HostStage.FAILED, "zeus"))
        return _failed(
            request,
            route,
            stages,
            retrieval_calls,
            retries,
            "synthesis_failed",
            synthesis_calls=1,
        )
    stages.append(StageEvent(HostStage.COMPLETED, "zeus"))
    citations = tuple(Citation(item.citation_id, item.source_id, item.uri) for item in cited)
    return _response(
        request,
        ResponseStatus.ANSWERED,
        synthesis.answer,
        route,
        citations,
        stages,
        HostTelemetry(retrieval_calls, 1, retries, synthesis.usage),
    )


def _cite(evidence: Evidence, index: int) -> CitedEvidence:
    return CitedEvidence(
        citation_id=f"S{index}",
        source_id=evidence.source_id,
        uri=evidence.uri,
        text=evidence.text,
        score=evidence.score,
        attributes=evidence.attributes,
    )


def _response(
    request: HostRequest,
    status: ResponseStatus,
    answer: str,
    route: tuple[Specialist, ...],
    citations: tuple[Citation, ...],
    stages: list[StageEvent],
    telemetry: HostTelemetry | None = None,
    failure_code: str | None = None,
) -> HostResponse:
    return HostResponse(
        request_id=request.request_id,
        status=status,
        answer=answer,
        route=route,
        citations=citations,
        stages=tuple(stages),
        telemetry=telemetry or HostTelemetry(),
        failure_code=failure_code,
    )


def _cancelled(
    request: HostRequest,
    route: tuple[Specialist, ...],
    stages: list[StageEvent],
    retrieval_calls: int,
    retries: int,
) -> HostResponse:
    stages.append(StageEvent(HostStage.CANCELLED, "zeus"))
    return _response(
        request,
        ResponseStatus.CANCELLED,
        _CANCELLED,
        route,
        (),
        stages,
        HostTelemetry(retrieval_calls=retrieval_calls, retries=retries),
        "cancelled",
    )


def _failed(
    request: HostRequest,
    route: tuple[Specialist, ...],
    stages: list[StageEvent],
    retrieval_calls: int,
    retries: int,
    failure_code: str,
    synthesis_calls: int = 0,
) -> HostResponse:
    return _response(
        request,
        ResponseStatus.FAILED,
        _FAILED,
        route,
        (),
        stages,
        HostTelemetry(retrieval_calls, synthesis_calls, retries),
        failure_code,
    )
