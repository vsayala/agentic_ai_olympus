from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import pytest

from olympus_copilot_sdk.evaluation.comparison import (
    record_vector_result,
    run_knowledge_baseline,
)
from olympus_copilot_sdk.evaluation.metrics import evaluate_response
from olympus_copilot_sdk.knowledge_01.agents import KnowledgeOrchestrator, Stage


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int
    cost: float = 0.0
    model: str = "test-model"
    calls: int = 3
    has_sdk_cost: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class FakeResult:
    response: str
    sources: list[str]
    usage: FakeUsage
    approach: str = "02_Vector_DB"


class FakeKnowledgeOrchestrator:
    received_query = ""

    async def answer(self, query: str, on_stage: Callable[[Stage, str], None]) -> FakeResult:
        self.received_query = query
        return FakeResult(
            "Baseline. [Source: story.md]",
            ["story.md"],
            FakeUsage(40, 10),
            "01_Knowledge",
        )


def test_vector_record_does_not_spend_or_invent_baseline_usage() -> None:
    result = FakeResult("Answer. [Source: story.md]", ["story.md"], FakeUsage(80, 20))

    record = record_vector_result("Question", result, 1.5, "test-model", 0.0, 0.0)

    assert record.vector.metrics.total_tokens == 100
    assert record.lexical is None
    assert record.lower_usage_approach is None
    assert record.higher_quality_approach is None
    assert record.source_overlap_ratio is None


def test_metrics_reject_citations_not_returned_by_retrieval() -> None:
    result = FakeResult(
        "Supported. [Source: story.md] Invented. [Source: missing.md]",
        ["story.md"],
        FakeUsage(90, 10),
    )

    metrics = evaluate_response(result, 0.5)

    assert metrics.valid_citation_ratio == 0.5
    assert metrics.source_coverage_ratio == 1.0
    assert metrics.total_tokens == 100


@pytest.mark.asyncio
async def test_baseline_uses_stored_query_and_preserves_run_configuration() -> None:
    vector = FakeResult("Vector. [Source: story.md]", ["story.md"], FakeUsage(80, 20))
    record = record_vector_result("Exact stored prompt", vector, 1.5, "saved-model", 1.25, 5.0)
    orchestrator = FakeKnowledgeOrchestrator()

    completed = await run_knowledge_baseline(
        record,
        cast(KnowledgeOrchestrator, orchestrator),
        lambda stage, detail: None,
    )

    assert orchestrator.received_query == "Exact stored prompt"
    assert (completed.model, completed.input_price, completed.output_price) == (
        "saved-model",
        1.25,
        5.0,
    )
    assert completed.lexical is not None
    assert completed.lexical.result.approach == "01_Knowledge"
