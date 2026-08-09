from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from copilot import CopilotSession
from copilot.session_events import AssistantMessageData

from olympus_copilot_sdk.vector_db_02.milvus import VectorKnowledgeBase
from olympus_copilot_sdk.vector_db_02.retrieval import SearchResult


class TextGenerationTool(Protocol):
    async def execute(self, session: CopilotSession, prompt: str) -> str: ...


@dataclass(frozen=True)
class CopilotTextTool:
    async def execute(self, session: CopilotSession, prompt: str) -> str:
        response = await session.send_and_wait(prompt, timeout=180.0)
        if response is None or not isinstance(response.data, AssistantMessageData):
            raise RuntimeError("Copilot returned no assistant message.")
        return response.data.content.strip()


@dataclass(frozen=True)
class VectorRetrievalTool:
    index: VectorKnowledgeBase

    async def execute(self, query: str, limit: int = 6) -> tuple[SearchResult, ...]:
        return tuple(await asyncio.to_thread(self.index.search, query, limit))


@dataclass(frozen=True)
class AgentTools:
    text_generation: TextGenerationTool
    retrieval: VectorRetrievalTool

    @classmethod
    def defaults(cls, index: VectorKnowledgeBase) -> AgentTools:
        return cls(CopilotTextTool(), VectorRetrievalTool(index))
