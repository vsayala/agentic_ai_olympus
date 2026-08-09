from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePath
from typing import Literal

from olympus_copilot_sdk.vector_db_02.chunking import VectorChunk

HYBRID_RETRIEVAL_VERSION = "hierarchical-rrf-coverage-v2"
DENSE_CANDIDATE_MULTIPLIER = 4
MIN_CANDIDATES = 20
RRF_K = 60
BROAD_RESULT_LIMIT = 10
BROAD_CONTEXT_MAX_CHARACTERS = 20_000

QueryMode = Literal["targeted", "broad"]

_BROAD_CUE = re.compile(
    r"\b(?:summari[sz]e|summary|overview|brief(?:\s+me)?(?:\s+about)?|"
    r"tell\s+me\s+about|explain)\b",
    re.IGNORECASE,
)
_NARROW_FOCUS = re.compile(
    r"\b(?:process|procedure|steps?|deadline|contact|phone|email|where|when|who)\b",
    re.IGNORECASE,
)
_FINANCIAL_RESULTS_FOCUS = re.compile(
    r"\b(?:financial\s+results?|half[- ]year\s+results?|quarterly\s+results?|"
    r"q[1-4]\s+(?:results?|earnings)|earnings\s+(?:release|results?))\b",
    re.IGNORECASE,
)

_TOKEN_PATTERN = re.compile(r"[\w'-]+", re.UNICODE)

POLICY_TOPIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "purpose/scope/principles": ("purpose", "scope", "principle", "values", "applies to"),
    "reporting/speak-up": (
        "speak up",
        "report concern",
        "whistleblow",
        "anonymous",
        "confidential",
        "non-retaliation",
        "retaliation",
    ),
    "ethics/anti-bribery": (
        "anti-bribery",
        "bribery",
        "corruption",
        "financial crime",
        "money laundering",
    ),
    "third parties/suppliers": ("third party", "third-party", "supplier", "vendor"),
    "people/human rights": (
        "human rights",
        "modern slavery",
        "diversity",
        "harassment",
        "workplace",
    ),
    "sustainability/environment": ("sustainability", "environment", "climate", "emissions"),
    "privacy/data": ("data protection", "personal data", "privacy", "cybersecurity"),
    "enforcement/accountability": (
        "accountability",
        "disciplinary",
        "enforcement",
        "investigation",
        "violation",
    ),
    "related policies": ("related policy", "related policies", "supporting policy", "see also"),
}


@dataclass(frozen=True)
class SearchResult:
    source: str
    text: str
    score: float
    chunk_id: int = -1
    citation_id: str = ""
    location: str = ""
    topics: tuple[str, ...] = ()

    @property
    def display_label(self) -> str:
        return f"{self.source} — {self.location or f'chunk {self.chunk_id + 1}'}"


@dataclass(frozen=True)
class IndexSummary:
    indexed_files: tuple[str, ...]
    skipped_files: tuple[str, ...]
    chunk_count: int


def classify_query(query: str) -> QueryMode:
    if is_financial_results_query(query):
        return "targeted"
    cue = _BROAD_CUE.search(query)
    if cue is None:
        return "targeted"
    subject = query[cue.end() :].strip(" :-,.?")
    if not _tokens(subject) or _NARROW_FOCUS.search(subject):
        return "targeted"
    return "broad"


def is_financial_results_query(query: str) -> bool:
    return _FINANCIAL_RESULTS_FOCUS.search(query) is not None


def hybrid_rank(
    query: str,
    chunks: Sequence[VectorChunk],
    dense_results: Sequence[SearchResult],
    limit: int,
) -> list[SearchResult]:
    if limit <= 0:
        return []
    chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    fused = _fused_scores(query, chunks, dense_results)
    candidate_ids = set(fused)
    ordered = sorted(candidate_ids, key=lambda chunk_id: (-fused[chunk_id], chunk_id))
    deduplicated: list[int] = []
    seen_text: set[str] = set()
    for chunk_id in ordered:
        normalized = " ".join(chunk_by_id[chunk_id].text.casefold().split())
        if normalized not in seen_text:
            seen_text.add(normalized)
            deduplicated.append(chunk_id)

    selected: list[int] = []
    source_counts: Counter[str] = Counter()
    token_cache = {chunk_id: set(_tokens(chunk_by_id[chunk_id].text)) for chunk_id in deduplicated}
    while deduplicated and len(selected) < limit:

        def diversity_score(chunk_id: int) -> tuple[float, int]:
            source = chunk_by_id[chunk_id].source
            similarity = max(
                (_jaccard(token_cache[chunk_id], token_cache[item]) for item in selected),
                default=0.0,
            )
            penalty = 1 + 0.05 * source_counts[source] + 0.35 * similarity
            return fused[chunk_id] / penalty, -chunk_id

        best = max(deduplicated, key=diversity_score)
        deduplicated.remove(best)
        selected.append(best)
        source_counts[chunk_by_id[best].source] += 1

    return [
        SearchResult(
            source=chunk_by_id[chunk_id].source,
            text=chunk_by_id[chunk_id].text,
            score=fused[chunk_id],
            chunk_id=chunk_id,
            citation_id=f"S{rank}",
            location=chunk_by_id[chunk_id].child_location,
        )
        for rank, chunk_id in enumerate(selected, start=1)
    ]


def broad_rank(
    query: str,
    chunks: Sequence[VectorChunk],
    dense_results: Sequence[SearchResult],
    limit: int = BROAD_RESULT_LIMIT,
    *,
    cover_policy_topics: bool = True,
) -> list[SearchResult]:
    if limit <= 0:
        return []
    chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    fused = _fused_scores(query, chunks, dense_results)
    if not fused:
        return []
    primary_source = _primary_source(query, chunk_by_id, fused)
    parents: dict[tuple[str, int], tuple[VectorChunk, float]] = {}
    for chunk in chunks:
        score = fused.get(chunk.chunk_id, 0.0)
        parent_key = (chunk.source, chunk.parent_id if chunk.parent_id >= 0 else chunk.chunk_id)
        existing = parents.get(parent_key)
        if existing is None:
            parents[parent_key] = (chunk, score)
        else:
            parents[parent_key] = (existing[0], existing[1] + score * 0.25)

    candidates = sorted(
        parents.values(),
        key=lambda item: (item[0].source != primary_source, -item[1], item[0].chunk_id),
    )
    selected: list[tuple[VectorChunk, float]] = []
    selected_keys: set[tuple[str, int]] = set()
    context_characters = 0

    def add(candidate: tuple[VectorChunk, float]) -> bool:
        nonlocal context_characters
        chunk, _ = candidate
        key = (chunk.source, chunk.parent_id if chunk.parent_id >= 0 else chunk.chunk_id)
        text = chunk.parent_text or chunk.text
        if (
            key in selected_keys
            or len(selected) >= limit
            or context_characters + len(text) > BROAD_CONTEXT_MAX_CHARACTERS
        ):
            return False
        selected.append(candidate)
        selected_keys.add(key)
        context_characters += len(text)
        return True

    primary = [item for item in candidates if item[0].source == primary_source]
    related = [item for item in candidates if item[0].source != primary_source]
    if cover_policy_topics:
        for topic in POLICY_TOPIC_PATTERNS:
            match = next(
                (item for item in primary if topic in evidence_topics(item[0].parent_text)), None
            )
            if match is not None:
                add(match)
                continue
            match = next(
                (item for item in related if topic in evidence_topics(item[0].parent_text)), None
            )
            if match is not None:
                add(match)
    for candidate in primary:
        add(candidate)

    return [
        SearchResult(
            source=chunk.source,
            text=chunk.parent_text or chunk.text,
            score=score,
            chunk_id=chunk.chunk_id,
            citation_id=f"S{rank}",
            location=chunk.location,
            topics=evidence_topics(chunk.parent_text or chunk.text),
        )
        for rank, (chunk, score) in enumerate(selected, start=1)
    ]


def evidence_topics(text: str) -> tuple[str, ...]:
    normalized = " ".join(text.casefold().split())
    return tuple(
        topic
        for topic, aliases in POLICY_TOPIC_PATTERNS.items()
        if any(alias in normalized for alias in aliases)
    )


def _primary_source(
    query: str,
    chunk_by_id: dict[int, VectorChunk],
    fused: dict[int, float],
) -> str:
    query_terms = set(_tokens(query)) - {
        "a",
        "about",
        "an",
        "brief",
        "explain",
        "me",
        "overview",
        "summarize",
        "summary",
        "tell",
        "the",
    }
    scores: dict[str, float] = {}
    source_ranks: dict[str, list[float]] = {}
    for chunk_id, score in fused.items():
        chunk = chunk_by_id[chunk_id]
        source_ranks.setdefault(chunk.source, []).append(score)
    for source, values in source_ranks.items():
        scores[source] = sum(sorted(values, reverse=True)[:4])
        filename_terms = set(_tokens(PurePath(source).stem))
        scores[source] += 0.02 * len(query_terms & filename_terms)
        first_chunk = min(
            (chunk for chunk in chunk_by_id.values() if chunk.source == source),
            key=lambda chunk: chunk.chunk_id,
        )
        title_terms = set(_tokens((first_chunk.parent_text or first_chunk.text)[:240]))
        scores[source] += 0.005 * len(query_terms & title_terms)
    return max(scores, key=lambda source: (scores[source], source))


def _fused_scores(
    query: str,
    chunks: Sequence[VectorChunk],
    dense_results: Sequence[SearchResult],
) -> dict[int, float]:
    chunk_ids = {chunk.chunk_id for chunk in chunks}
    dense_rank = {
        result.chunk_id: rank
        for rank, result in enumerate(dense_results, start=1)
        if result.chunk_id in chunk_ids
    }
    lexical_rank = {
        chunk_id: rank for rank, (chunk_id, _) in enumerate(_bm25_scores(query, chunks), start=1)
    }
    return {
        chunk_id: sum(
            1 / (RRF_K + rank)
            for rank in (dense_rank.get(chunk_id), lexical_rank.get(chunk_id))
            if rank is not None
        )
        for chunk_id in set(dense_rank) | set(lexical_rank)
    }


def candidate_limit(result_limit: int) -> int:
    return max(MIN_CANDIDATES, result_limit * DENSE_CANDIDATE_MULTIPLIER)


def _bm25_scores(query: str, chunks: Sequence[VectorChunk]) -> list[tuple[int, float]]:
    query_terms = set(_tokens(query))
    if not query_terms or not chunks:
        return []
    documents = [_tokens(chunk.text) for chunk in chunks]
    average_length = sum(map(len, documents)) / len(documents) or 1.0
    document_frequency = Counter(
        term for document in documents for term in query_terms.intersection(document)
    )
    scored: list[tuple[int, float]] = []
    for chunk, document in zip(chunks, documents, strict=True):
        frequencies = Counter(document)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            inverse_frequency = math.log(
                1
                + (len(documents) - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            denominator = frequency + 1.2 * (0.25 + 0.75 * len(document) / average_length)
            score += inverse_frequency * frequency * 2.2 / denominator
        if score > 0:
            scored.append((chunk.chunk_id, score))
    return sorted(scored, key=lambda item: (-item[1], item[0]))


def _tokens(text: str) -> list[str]:
    return [match.group().casefold() for match in _TOKEN_PATTERN.finditer(text)]


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0
