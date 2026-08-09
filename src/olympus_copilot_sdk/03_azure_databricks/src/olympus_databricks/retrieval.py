from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

from olympus_databricks.contracts import Evidence


class IndexLike(Protocol):
    def similarity_search(self, **kwargs: object) -> dict[str, Any]: ...


class AISearchRetriever:
    def __init__(self, index: IndexLike) -> None:
        self._index = index

    def search(self, query: str, limit: int = 8) -> list[Evidence]:
        response = self._index.similarity_search(
            query_text=query,
            columns=["chunk_id", "chunk_to_retrieve", "source_uri", "pages"],
            num_results=limit,
            query_type="HYBRID",
        )
        manifest = cast(dict[str, Any], response.get("manifest", {}))
        columns = [item["name"] for item in cast(list[dict[str, str]], manifest.get("columns", []))]
        result = cast(dict[str, Any], response.get("result", {}))
        rows = cast(list[list[Any]], result.get("data_array", []))
        return [_row_to_evidence(dict(zip(columns, row, strict=True))) for row in rows]


class ServingEndpointRetriever:
    def __init__(self, invoke: Callable[[str], list[dict[str, object]]]) -> None:
        self._invoke = invoke

    def search(self, query: str, limit: int = 8) -> list[Evidence]:
        rows = self._invoke(query)[:limit]
        return [_row_to_evidence(row) for row in rows]


def _row_to_evidence(row: dict[str, object]) -> Evidence:
    source = str(row.get("source_uri", "unknown"))
    raw_score = row.get("score", 0.0)
    score = float(raw_score) if isinstance(raw_score, int | float | str) else 0.0
    return Evidence(
        citation_id="",
        source=source,
        text=str(row.get("chunk_to_retrieve", "")),
        score=score,
        attributes={
            key: str(value)
            for key, value in row.items()
            if key not in {"chunk_to_retrieve", "score"}
        },
    )
