from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from olympus_sp.config import SharePointConfig
from olympus_sp.contracts import Evidence, RetrievalResult
from olympus_sp.identity import OboIdentity


class AccessDeniedError(PermissionError):
    pass


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    source_uri: str
    text: str
    score: float
    attributes: dict[str, str]


class FoundrySharePointBackend(Protocol):
    def search(
        self,
        *,
        connection_id: str,
        site_id: str,
        library_id: str,
        query: str,
        user_access_token: str,
        limit: int,
    ) -> list[SourceRecord]: ...


class GraphRetrievalBackend(Protocol):
    def search(
        self,
        *,
        endpoint: str,
        site_id: str,
        library_id: str,
        query: str,
        user_access_token: str,
        limit: int,
    ) -> list[SourceRecord]: ...


class SharePointRetriever:
    def __init__(
        self,
        config: SharePointConfig,
        identity: OboIdentity,
        backend: FoundrySharePointBackend | GraphRetrievalBackend,
    ) -> None:
        if identity.tenant_id != config.tenant_id:
            raise ValueError("OBO tenant does not match configured tenant")
        self._config = config
        self._identity = identity
        self._backend = backend

    def search(self, query: str, limit: int = 8) -> RetrievalResult:
        try:
            if self._config.mode.value == "foundry":
                backend = cast(FoundrySharePointBackend, self._backend)
                rows = backend.search(
                    connection_id=self._config.foundry_connection_id,
                    site_id=self._config.site_id,
                    library_id=self._config.library_id,
                    query=query,
                    user_access_token=self._identity.access_token,
                    limit=limit,
                )
            else:
                backend = cast(GraphRetrievalBackend, self._backend)
                rows = backend.search(
                    endpoint=self._config.graph_endpoint,
                    site_id=self._config.site_id,
                    library_id=self._config.library_id,
                    query=query,
                    user_access_token=self._identity.access_token,
                    limit=limit,
                )
        except AccessDeniedError:
            return RetrievalResult((), access_denied=True, denial_reason="source_access_denied")
        return RetrievalResult(tuple(_normalize(row) for row in rows[:limit]))


def _normalize(row: SourceRecord) -> Evidence:
    return Evidence(row.source_id, row.source_uri, row.text, row.score, dict(row.attributes))
