from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Evidence:
    source_id: str
    source_uri: str
    text: str
    score: float
    attributes: dict[str, str]


@dataclass(frozen=True)
class RetrievalResult:
    evidence: tuple[Evidence, ...]
    access_denied: bool = False
    denial_reason: str | None = None

    def __post_init__(self) -> None:
        if self.access_denied and self.evidence:
            raise ValueError("access-denied results cannot contain evidence")


class Retriever(Protocol):
    def search(self, query: str, limit: int = 8) -> RetrievalResult: ...
