from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Evidence:
    citation_id: str
    source: str
    text: str
    score: float
    attributes: dict[str, str]


class Retriever(Protocol):
    def search(self, query: str, limit: int = 8) -> list[Evidence]: ...


class SparkSessionLike(Protocol):
    def sql(self, query: str) -> object: ...
