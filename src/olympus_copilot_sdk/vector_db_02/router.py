from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Literal

from olympus_copilot_sdk.vector_db_02.retrieval import SearchResult

SpecialistName = Literal["hercules", "hades"]

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
_HALF_YEAR_PATTERN = re.compile(r"\bhy(\d{2})\b", re.IGNORECASE)
_PRIMARY_DATA_PATTERN = re.compile(r"\bdata(?:\s+folder)?\b")
_SECONDARY_DATA_PATTERN = re.compile(r"\bdata_2\b")
_SECONDARY_HINTS = (
    "secondary",
    "second corpus",
    "additional corpus",
    "another corpus",
    "other corpus",
    "extra corpus",
    "another folder",
    "other folder",
)
_ROUTING_STOP_WORDS = {
    "a",
    "about",
    "and",
    "can",
    "for",
    "give",
    "me",
    "of",
    "on",
    "please",
    "summary",
    "summarize",
    "the",
    "what",
    "were",
    "you",
}
MIN_RELEVANCE = 0.25
ROUTING_MARGIN = 0.15


def route_query(
    query: str,
    evidence: Mapping[SpecialistName, Sequence[SearchResult]],
) -> tuple[SpecialistName, ...]:
    normalized = query.casefold().strip()
    has_primary = bool(_PRIMARY_DATA_PATTERN.search(normalized))
    has_secondary = bool(_SECONDARY_DATA_PATTERN.search(normalized)) or any(
        hint in normalized for hint in _SECONDARY_HINTS
    )
    if has_secondary and has_primary:
        return tuple(
            name
            for name in ("hercules", "hades")
            if name in evidence and _years_are_compatible(query, evidence[name])
        )
    if has_secondary:
        return (
            ("hades",)
            if "hades" in evidence and _years_are_compatible(query, evidence["hades"])
            else ()
        )
    if has_primary:
        return (
            ("hercules",)
            if "hercules" in evidence and _years_are_compatible(query, evidence["hercules"])
            else ()
        )

    scores = {name: _relevance(query, results) for name, results in evidence.items()}
    if not scores:
        return ()
    best_score = max(scores.values())
    if best_score < MIN_RELEVANCE:
        return ()
    return tuple(
        name
        for name in ("hercules", "hades")
        if name in scores and scores[name] >= max(MIN_RELEVANCE, best_score - ROUTING_MARGIN)
    )


def _relevance(query: str, results: Sequence[SearchResult]) -> float:
    query_terms = _terms(query)
    if not query_terms:
        return 0.0
    requested_years = _years(query)
    return max(
        (
            len(query_terms & _terms(evidence_text)) / len(query_terms)
            if not requested_years or requested_years & _years(evidence_text)
            else 0.0
            for result in results
            for evidence_text in (f"{result.source} {result.text}",)
        ),
        default=0.0,
    )


def _years(value: str) -> set[str]:
    years = set(_YEAR_PATTERN.findall(value))
    years.update(f"20{match}" for match in _HALF_YEAR_PATTERN.findall(value))
    return years


def _years_are_compatible(query: str, results: Sequence[SearchResult]) -> bool:
    requested_years = _years(query)
    return not requested_years or any(
        requested_years & _years(f"{result.source} {result.text}") for result in results
    )


def _terms(value: str) -> set[str]:
    normalized = re.sub(
        r"\bhy([0-9]{2})\b",
        lambda match: f"20{match.group(1)} half year",
        value.casefold(),
    )
    return {
        token
        for token in _TOKEN_PATTERN.findall(normalized)
        if token not in _ROUTING_STOP_WORDS and len(token) > 1
    }
