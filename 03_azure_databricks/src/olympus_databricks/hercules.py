from __future__ import annotations

from dataclasses import replace

from olympus_databricks.contracts import Evidence, Retriever


class HerculesDatabricksTool:
    """Normalizes governed retrieval results for the Olympus Hercules boundary."""

    def __init__(self, retriever: Retriever) -> None:
        self._retriever = retriever

    def retrieve(self, query: str, limit: int = 8) -> list[Evidence]:
        if not query.strip():
            return []
        results = self._retriever.search(query, limit)
        return [replace(result, citation_id=f"S{index}") for index, result in enumerate(results, 1)]
