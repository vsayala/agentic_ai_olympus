from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    source: str
    text: str
    score: float


@dataclass(frozen=True)
class IndexSummary:
    indexed_files: tuple[str, ...]
    skipped_files: tuple[str, ...]
    chunk_count: int
