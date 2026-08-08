from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from copilot import CopilotSession

from olympus_copilot_sdk.vector_db_02.prompts import (
    render_evidence_request,
    render_synthesis_request,
)
from olympus_copilot_sdk.vector_db_02.retrieval import SearchResult
from olympus_copilot_sdk.vector_db_02.tools import TextGenerationTool


@dataclass(frozen=True)
class EvidenceRequest:
    session: CopilotSession
    query: str
    results: Sequence[SearchResult]


@dataclass(frozen=True)
class SynthesisRequest:
    session: CopilotSession
    query: str
    evidence_report: str
    citation_map: Mapping[str, str]


@dataclass(frozen=True)
class AgentSkills:
    text_generation: TextGenerationTool

    async def research(self, request: EvidenceRequest) -> str:
        return await self.text_generation.execute(
            request.session,
            render_evidence_request(request.query, request.results),
        )

    async def synthesize(self, request: SynthesisRequest) -> str:
        return await self.text_generation.execute(
            request.session,
            render_synthesis_request(
                request.query,
                request.evidence_report,
                request.citation_map,
            ),
        )
