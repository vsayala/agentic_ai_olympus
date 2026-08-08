from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

_CITATION_PATTERN = re.compile(r"\[Source:\s*([^\]]+)\]", re.IGNORECASE)
_UNCERTAINTY_PATTERN = re.compile(
    r"\b(?:insufficient|unclear|unknown|not available|cannot determine|missing evidence)\b",
    re.IGNORECASE,
)


class UsageLike(Protocol):
    @property
    def input_tokens(self) -> int: ...

    @property
    def output_tokens(self) -> int: ...

    @property
    def cost(self) -> float: ...

    @property
    def calls(self) -> int: ...

    @property
    def model(self) -> str: ...

    @property
    def has_sdk_cost(self) -> bool: ...

    @property
    def total_tokens(self) -> int: ...


class ResultLike(Protocol):
    @property
    def response(self) -> str: ...

    @property
    def sources(self) -> list[str]: ...

    @property
    def usage(self) -> UsageLike: ...

    @property
    def approach(self) -> str: ...


@dataclass(frozen=True)
class ResponseMetrics:
    latency_seconds: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model_calls: int
    cost: float
    word_count: int
    sentence_count: int
    citation_count: int
    valid_citation_ratio: float
    source_coverage_ratio: float
    grounded_sentence_ratio: float
    uncertainty_disclosed: bool
    token_efficiency: float
    quality_score: float


def evaluate_response(result: ResultLike, latency_seconds: float) -> ResponseMetrics:
    sentences = [
        part.strip() for part in re.split(r"(?<=[.!?])\s+", result.response) if part.strip()
    ]
    citations = _CITATION_PATTERN.findall(result.response)
    normalized_sources = {source.casefold() for source in result.sources}
    valid_citations = [
        citation for citation in citations if citation.strip().casefold() in normalized_sources
    ]
    cited_sources = {citation.strip().casefold() for citation in valid_citations}
    valid_ratio = _ratio(len(valid_citations), len(citations)) if citations else 0.0
    source_coverage = _ratio(len(cited_sources), len(normalized_sources))
    grounded = sum(bool(_CITATION_PATTERN.search(sentence)) for sentence in sentences)
    grounded_ratio = _ratio(grounded, len(sentences))
    total_tokens = result.usage.total_tokens
    token_efficiency = 1_000 * len(valid_citations) / max(total_tokens, 1)
    concision_score = min(1.0, 300 / max(len(result.response.split()), 1))
    quality_score = 100 * (
        0.4 * valid_ratio + 0.3 * source_coverage + 0.2 * grounded_ratio + 0.1 * concision_score
    )
    return ResponseMetrics(
        latency_seconds=latency_seconds,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        total_tokens=total_tokens,
        model_calls=result.usage.calls,
        cost=result.usage.cost,
        word_count=len(result.response.split()),
        sentence_count=len(sentences),
        citation_count=len(citations),
        valid_citation_ratio=valid_ratio,
        source_coverage_ratio=source_coverage,
        grounded_sentence_ratio=grounded_ratio,
        uncertainty_disclosed=bool(_UNCERTAINTY_PATTERN.search(result.response)),
        token_efficiency=token_efficiency,
        quality_score=quality_score,
    )


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
