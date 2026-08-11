from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from olympus_adb.config import DatabricksConfig
from olympus_adb.contracts import AccessContext, Evidence, RetrievalResult
from olympus_adb.strategy import RetrievalStrategy


class AccessDeniedError(PermissionError):
    pass


@dataclass(frozen=True)
class SourceRow:
    source_id: str
    source_uri: str
    text: str
    score: float
    attributes: dict[str, str]


class VectorSearchBackend(Protocol):
    def query(
        self,
        *,
        endpoint: str,
        index: str,
        query: str,
        user_id: str,
        user_access_token: str,
        limit: int,
    ) -> list[SourceRow]: ...


class GenieBackend(Protocol):
    def ask(
        self,
        *,
        space_id: str,
        warehouse_id: str,
        question: str,
        user_id: str,
        user_access_token: str,
        limit: int,
    ) -> list[SourceRow]: ...


class McpBackend(Protocol):
    def search(
        self,
        *,
        connection: str,
        query: str,
        user_id: str,
        user_access_token: str,
        limit: int,
    ) -> list[SourceRow]: ...


class DatabricksRetriever:
    def __init__(
        self,
        config: DatabricksConfig,
        context: AccessContext,
        backend: VectorSearchBackend | GenieBackend | McpBackend,
    ) -> None:
        self._config = config
        self._context = context
        self._backend = backend

    def search(self, query: str, limit: int = 8) -> RetrievalResult:
        try:
            rows = self._search(query, limit)
        except AccessDeniedError:
            return RetrievalResult((), access_denied=True, denial_reason="source_access_denied")
        return RetrievalResult(tuple(_normalize(row) for row in rows[:limit]))

    def _search(self, query: str, limit: int) -> list[SourceRow]:
        if self._config.strategy is RetrievalStrategy.VECTOR_SEARCH:
            backend = cast(VectorSearchBackend, self._backend)
            return backend.query(
                endpoint=self._config.vector_search_endpoint,
                index=self._config.vector_search_index,
                query=query,
                user_id=self._context.user_id,
                user_access_token=self._context.access_token,
                limit=limit,
            )
        if self._config.strategy is RetrievalStrategy.GENIE:
            backend = cast(GenieBackend, self._backend)
            return backend.ask(
                space_id=self._config.genie_space_id,
                warehouse_id=self._config.warehouse_id,
                question=query,
                user_id=self._context.user_id,
                user_access_token=self._context.access_token,
                limit=limit,
            )
        backend = cast(McpBackend, self._backend)
        return backend.search(
            connection=self._config.mcp_connection,
            query=query,
            user_id=self._context.user_id,
            user_access_token=self._context.access_token,
            limit=limit,
        )


def _normalize(row: SourceRow) -> Evidence:
    return Evidence(row.source_id, row.source_uri, row.text, row.score, dict(row.attributes))
