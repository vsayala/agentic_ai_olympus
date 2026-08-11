from __future__ import annotations

from olympus_sp.contracts import RetrievalResult, Retriever


class SharePointEvidenceTool:
    def __init__(self, retriever: Retriever) -> None:
        self._retriever = retriever

    def retrieve(self, query: str, limit: int = 8) -> RetrievalResult:
        return self._retriever.search(query, limit)
