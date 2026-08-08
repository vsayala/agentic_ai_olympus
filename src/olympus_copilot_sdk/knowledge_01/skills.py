from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from copilot import CopilotSession

from olympus_copilot_sdk.knowledge_01.prompts import (
    render_evidence_request,
    render_retrieval_brief,
    render_synthesis_request,
)
from olympus_copilot_sdk.knowledge_01.retrieval import SearchResult
from olympus_copilot_sdk.knowledge_01.tools import TextGenerationTool


@dataclass(frozen=True)
class RetrievalBriefRequest:
    session: CopilotSession
    query: str
    filenames: Sequence[str]


@dataclass(frozen=True)
class EvidenceRequest:
    session: CopilotSession
    query: str
    delegation: str
    results: Sequence[SearchResult]


@dataclass(frozen=True)
class SynthesisRequest:
    session: CopilotSession
    query: str
    evidence_report: str


@dataclass(frozen=True)
class AgentSkills:
    text_generation: TextGenerationTool

    async def create_brief(self, request: RetrievalBriefRequest) -> str:
        return await self.text_generation.execute(
            request.session,
            render_retrieval_brief(request.query, request.filenames),
        )

    async def research(self, request: EvidenceRequest) -> str:
        return await self.text_generation.execute(
            request.session,
            render_evidence_request(request.query, request.delegation, request.results),
        )

    async def synthesize(self, request: SynthesisRequest) -> str:
        return await self.text_generation.execute(
            request.session,
            render_synthesis_request(request.query, request.evidence_report),
        )
