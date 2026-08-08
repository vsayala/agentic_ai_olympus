from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast

_CITATION_PATTERN = re.compile(r"\[Source:\s*([^\]]+)\]", re.IGNORECASE)
_CANONICAL_CITATION_PATTERN = re.compile(r"\[(S\d+)\]", re.IGNORECASE)
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
    evidence_topic_completeness: float | None = None


def evaluate_response(result: ResultLike, latency_seconds: float) -> ResponseMetrics:
    response_body = result.response.split("\nSources:\n", 1)[0]
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", response_body) if part.strip()]
    legacy_citations = _CITATION_PATTERN.findall(response_body)
    canonical_citations = _CANONICAL_CITATION_PATTERN.findall(response_body)
    normalized_sources = {source.casefold() for source in result.sources}
    raw_citation_map = getattr(result, "citation_map", {}) or {}
    citation_map = cast(Mapping[str, str], raw_citation_map)
    normalized_map = {key.casefold(): source.casefold() for key, source in citation_map.items()}
    legacy_source_sets = [
        _legacy_sources(citation, normalized_sources) for citation in legacy_citations
    ]
    valid_legacy_count = sum(bool(sources) for sources in legacy_source_sets)
    legacy_cited_sources: set[str] = set()
    for sources in legacy_source_sets:
        legacy_cited_sources.update(sources)
    valid_canonical = [
        normalized_map[citation.casefold()]
        for citation in canonical_citations
        if citation.casefold() in normalized_map
        and normalized_map[citation.casefold()] in normalized_sources
    ]
    valid_citation_count = valid_legacy_count + len(valid_canonical)
    citation_count = len(legacy_citations) + len(canonical_citations)
    cited_sources = legacy_cited_sources | set(valid_canonical)
    valid_ratio = _ratio(valid_citation_count, citation_count) if citation_count else 0.0
    source_coverage = _ratio(len(cited_sources), len(normalized_sources))
    grounded = sum(
        bool(_CITATION_PATTERN.search(sentence) or _CANONICAL_CITATION_PATTERN.search(sentence))
        for sentence in sentences
    )
    grounded_ratio = _ratio(grounded, len(sentences))
    total_tokens = result.usage.total_tokens
    token_efficiency = 1_000 * valid_citation_count / max(total_tokens, 1)
    concision_score = min(1.0, 300 / max(len(response_body.split()), 1))
    quality_score = 100 * (
        0.4 * valid_ratio + 0.3 * source_coverage + 0.2 * grounded_ratio + 0.1 * concision_score
    )
    raw_topic_citations = getattr(result, "topic_citation_map", {}) or {}
    topic_citations = cast(Mapping[str, tuple[str, ...]], raw_topic_citations)
    cited_ids = {citation.casefold() for citation in canonical_citations}
    completeness = (
        _ratio(
            sum(
                any(citation.casefold() in cited_ids for citation in citations)
                for citations in topic_citations.values()
            ),
            len(topic_citations),
        )
        if getattr(result, "query_mode", "targeted") == "broad" and topic_citations
        else None
    )
    return ResponseMetrics(
        latency_seconds=latency_seconds,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        total_tokens=total_tokens,
        model_calls=result.usage.calls,
        cost=result.usage.cost,
        word_count=len(response_body.split()),
        sentence_count=len(sentences),
        citation_count=citation_count,
        valid_citation_ratio=valid_ratio,
        source_coverage_ratio=source_coverage,
        grounded_sentence_ratio=grounded_ratio,
        uncertainty_disclosed=bool(_UNCERTAINTY_PATTERN.search(response_body)),
        token_efficiency=token_efficiency,
        quality_score=quality_score,
        evidence_topic_completeness=completeness,
    )


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _legacy_sources(citation: str, sources: set[str]) -> set[str]:
    normalized = citation.strip().casefold()
    return {
        source
        for source in sources
        if re.search(
            rf"(?:^|[;,]\s*){re.escape(source)}(?:$|[;,])",
            normalized,
        )
    }
