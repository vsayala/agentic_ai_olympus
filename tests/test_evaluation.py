from dataclasses import dataclass

import pytest

from olympus_copilot_sdk.evaluation.comparison import (
    attach_baseline_result,
    record_vector_result,
)
from olympus_copilot_sdk.evaluation.metrics import evaluate_response


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
    citation_map: dict[str, str] | None = None
    query_mode: str = "targeted"
    topic_citation_map: dict[str, tuple[str, ...]] | None = None


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


def test_metrics_accept_canonical_ids_and_annotated_legacy_citations() -> None:
    result = FakeResult(
        "Canonical fact. [S1] Legacy fact. [Source: appendix.pdf; see p3]\n\n"
        "Sources:\n- [S1] story.md",
        ["story.md", "appendix.pdf"],
        FakeUsage(90, 10),
        citation_map={"S1": "story.md"},
    )

    metrics = evaluate_response(result, 0.5)

    assert metrics.citation_count == 2
    assert metrics.valid_citation_ratio == 1.0
    assert metrics.source_coverage_ratio == 1.0


def test_legacy_multi_source_citation_covers_each_retrieved_source() -> None:
    result = FakeResult(
        "Obligations span both policies. [Source: conduct.pdf; promotion.pdf]",
        ["conduct.pdf", "promotion.pdf"],
        FakeUsage(90, 10),
        approach="01_Knowledge",
    )

    metrics = evaluate_response(result, 0.5)

    assert metrics.citation_count == 1
    assert metrics.valid_citation_ratio == 1.0
    assert metrics.source_coverage_ratio == 1.0


def test_broad_evidence_topic_completeness_uses_retrieved_citation_contract() -> None:
    result = FakeResult(
        "Reporting is confidential. [S1] Other detail. [S3]",
        ["policy.pdf"],
        FakeUsage(90, 10),
        citation_map={"S1": "policy.pdf", "S2": "policy.pdf", "S3": "policy.pdf"},
        query_mode="broad",
        topic_citation_map={
            "reporting/speak-up": ("S1",),
            "privacy/data": ("S2",),
            "enforcement/accountability": ("S3",),
        },
    )

    metrics = evaluate_response(result, 0.5)

    assert metrics.evidence_topic_completeness == pytest.approx(2 / 3)


def test_topic_completeness_is_unavailable_and_does_not_change_quality_for_baseline() -> None:
    targeted = FakeResult(
        "Supported. [S1]",
        ["story.md"],
        FakeUsage(90, 10),
        citation_map={"S1": "story.md"},
    )
    baseline = FakeResult(
        "Supported. [S1]",
        ["story.md"],
        FakeUsage(90, 10),
        "01_Knowledge",
        {"S1": "story.md"},
    )

    targeted_metrics = evaluate_response(targeted, 0.5)
    baseline_metrics = evaluate_response(baseline, 0.5)

    assert baseline_metrics.evidence_topic_completeness is None
    assert baseline_metrics.quality_score == targeted_metrics.quality_score


def test_baseline_snapshot_preserves_run_configuration() -> None:
    vector = FakeResult("Vector. [Source: story.md]", ["story.md"], FakeUsage(80, 20))
    record = record_vector_result("Exact stored prompt", vector, 1.5, "saved-model", 1.25, 5.0)
    baseline = FakeResult(
        "Baseline. [Source: story.md]",
        ["story.md"],
        FakeUsage(40, 10),
        "01_Knowledge",
    )
    completed = attach_baseline_result(record, baseline, 0.75)

    assert completed.query == "Exact stored prompt"
    assert (completed.model, completed.input_price, completed.output_price) == (
        "saved-model",
        1.25,
        5.0,
    )
    assert completed.lexical is not None
    assert completed.lexical.result.approach == "01_Knowledge"
