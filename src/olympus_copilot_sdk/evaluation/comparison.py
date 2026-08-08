from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Literal

from olympus_copilot_sdk.evaluation.metrics import ResponseMetrics, ResultLike, evaluate_response
from olympus_copilot_sdk.knowledge_01.agents import KnowledgeOrchestrator, Stage

Preference = Literal["01_Knowledge", "02_Vector_DB", "Tie"]


@dataclass(frozen=True)
class UsageSnapshot:
    input_tokens: int
    output_tokens: int
    cost: float
    model: str
    calls: int
    has_sdk_cost: bool

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class ResultSnapshot:
    response: str
    sources: list[str]
    usage: UsageSnapshot
    approach: str


@dataclass(frozen=True)
class ApproachEvaluation:
    result: ResultSnapshot
    metrics: ResponseMetrics


@dataclass(frozen=True)
class EvaluationRecord:
    query: str
    vector: ApproachEvaluation
    model: str
    input_price: float
    output_price: float
    lexical: ApproachEvaluation | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    preference: Preference | None = None

    @property
    def source_overlap_ratio(self) -> float | None:
        if self.lexical is None:
            return None
        lexical_sources = set(self.lexical.result.sources)
        vector_sources = set(self.vector.result.sources)
        union = lexical_sources | vector_sources
        return len(lexical_sources & vector_sources) / len(union) if union else 0.0

    @property
    def lower_usage_approach(self) -> Preference | None:
        if self.lexical is None:
            return None
        if self.lexical.metrics.total_tokens == self.vector.metrics.total_tokens:
            return "Tie"
        return (
            "01_Knowledge"
            if self.lexical.metrics.total_tokens < self.vector.metrics.total_tokens
            else "02_Vector_DB"
        )

    @property
    def higher_quality_approach(self) -> Preference | None:
        if self.lexical is None:
            return None
        if self.lexical.metrics.quality_score == self.vector.metrics.quality_score:
            return "Tie"
        return (
            "01_Knowledge"
            if self.lexical.metrics.quality_score > self.vector.metrics.quality_score
            else "02_Vector_DB"
        )


def record_vector_result(
    query: str,
    result: ResultLike,
    latency_seconds: float,
    model: str,
    input_price: float,
    output_price: float,
) -> EvaluationRecord:
    return EvaluationRecord(
        query=query,
        vector=_evaluation(result, latency_seconds),
        model=model,
        input_price=input_price,
        output_price=output_price,
    )


async def run_knowledge_baseline(
    record: EvaluationRecord,
    orchestrator: KnowledgeOrchestrator,
    on_stage: Callable[[Stage, str], None],
) -> EvaluationRecord:
    start = time.perf_counter()
    result = await orchestrator.answer(record.query, on_stage)
    return replace(record, lexical=_evaluation(result, time.perf_counter() - start))


def _evaluation(result: ResultLike, latency_seconds: float) -> ApproachEvaluation:
    usage = result.usage
    snapshot = ResultSnapshot(
        response=result.response,
        sources=list(result.sources),
        usage=UsageSnapshot(
            usage.input_tokens,
            usage.output_tokens,
            usage.cost,
            usage.model,
            usage.calls,
            usage.has_sdk_cost,
        ),
        approach=result.approach,
    )
    return ApproachEvaluation(snapshot, evaluate_response(result, latency_seconds))
