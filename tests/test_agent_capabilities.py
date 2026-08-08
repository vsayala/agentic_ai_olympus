from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import pytest
from copilot import CopilotSession

from olympus_copilot_sdk.knowledge_01.retrieval import SearchResult as KnowledgeResult
from olympus_copilot_sdk.knowledge_01.skills import AgentSkills as KnowledgeSkills
from olympus_copilot_sdk.knowledge_01.skills import EvidenceRequest as KnowledgeEvidenceRequest
from olympus_copilot_sdk.vector_db_02.retrieval import SearchResult as VectorResult
from olympus_copilot_sdk.vector_db_02.skills import AgentSkills as VectorSkills
from olympus_copilot_sdk.vector_db_02.skills import EvidenceRequest as VectorEvidenceRequest


def _empty_prompts() -> list[str]:
    return []


@dataclass
class FakeTextTool:
    responses: list[str]
    prompts: list[str] = field(default_factory=_empty_prompts)

    async def execute(self, session: CopilotSession, prompt: str) -> str:
        del session
        self.prompts.append(prompt)
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_knowledge_skill_uses_its_own_lexical_results() -> None:
    tool = FakeTextTool(["baseline report"])
    skill = KnowledgeSkills(tool)
    session = cast(CopilotSession, object())

    response = await skill.research(
        KnowledgeEvidenceRequest(
            session,
            "What happened?",
            "Find evidence",
            (KnowledgeResult("lexical.md", "Lexical evidence", 1.0),),
        )
    )

    assert response == "baseline report"
    assert "[Source: lexical.md]" in tool.prompts[0]


@pytest.mark.asyncio
async def test_vector_skill_uses_its_own_milvus_results() -> None:
    tool = FakeTextTool(["vector report"])
    skill = VectorSkills(tool)
    session = cast(CopilotSession, object())

    response = await skill.research(
        VectorEvidenceRequest(
            session,
            "What happened?",
            "Find evidence",
            (VectorResult("vector.md", "Semantic evidence", 0.9),),
        )
    )

    assert response == "vector report"
    assert "[Source: vector.md]" in tool.prompts[0]
