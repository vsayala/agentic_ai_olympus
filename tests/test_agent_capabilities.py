from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from copilot import CopilotSession
from copilot.session_events import AssistantUsageData, SessionEvent, SessionEventType

from olympus_copilot_sdk.knowledge_01.retrieval import SearchResult as KnowledgeResult
from olympus_copilot_sdk.knowledge_01.skills import AgentSkills as KnowledgeSkills
from olympus_copilot_sdk.knowledge_01.skills import EvidenceRequest as KnowledgeEvidenceRequest
from olympus_copilot_sdk.vector_db_02 import agents as vector_agents
from olympus_copilot_sdk.vector_db_02.agents import VectorOrchestrator
from olympus_copilot_sdk.vector_db_02.prompts import (
    render_evidence_request,
    render_synthesis_request,
)
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


@dataclass
class FakeSession:
    on_event: Callable[[SessionEvent], None]


class FakeClient:
    def __init__(self, **kwargs: object) -> None:
        del kwargs

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        del args

    async def create_session(self, **kwargs: object) -> FakeSession:
        return FakeSession(cast(Callable[[SessionEvent], None], kwargs["on_event"]))


@dataclass
class UsageTextTool:
    responses: list[str]
    prompts: list[str] = field(default_factory=_empty_prompts)

    async def execute(self, session: CopilotSession, prompt: str) -> str:
        fake_session = cast(FakeSession, session)
        self.prompts.append(prompt)
        fake_session.on_event(
            SessionEvent(
                data=AssistantUsageData(
                    model="test-model",
                    input_tokens=10,
                    output_tokens=5,
                ),
                id=uuid4(),
                timestamp=datetime.now(UTC),
                type=SessionEventType.ASSISTANT_USAGE,
            )
        )
        return self.responses.pop(0)


@dataclass
class FakeVectorIndex:
    data_directory: Path

    def search(self, query: str, limit: int = 6) -> list[VectorResult]:
        assert query == "What happened by the river?"
        assert limit == 6
        return [
            VectorResult(
                "story.md",
                "Mole met Rat by the river.",
                0.5,
                7,
                "S1",
                "page 2, chunk 8",
            ),
            VectorResult(
                "story.md",
                "Badger waited on the next page.",
                0.4,
                8,
                "S2",
                "page 3, chunk 9",
            ),
        ]


def test_numbered_stacks_are_isolated_and_ui_routing_is_explicit() -> None:
    root = Path(__file__).parents[1]
    source_root = root / "src" / "olympus_copilot_sdk"
    vector_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (source_root / "vector_db_02").glob("*.py")
    )
    knowledge_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (source_root / "knowledge_01").glob("*.py")
    )
    chat_source = (source_root / "ui" / "chat_page.py").read_text(encoding="utf-8")
    evaluation_source = (source_root / "ui" / "evaluation_page.py").read_text(encoding="utf-8")

    assert "knowledge_01" not in vector_sources
    assert "vector_db_02" not in knowledge_sources
    assert "VectorOrchestrator" in chat_source
    assert "KnowledgeOrchestrator" not in chat_source
    assert "Run 01_Knowledge baseline" in evaluation_source
    assert "KnowledgeOrchestrator" in evaluation_source


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
            (VectorResult("vector.md", "Semantic evidence", 0.9, 1, "S1"),),
        )
    )

    assert response == "vector report"
    assert "[S1 | Source: vector.md — chunk 2]" in tool.prompts[0]


@pytest.mark.asyncio
async def test_vector_orchestration_uses_two_model_calls_and_stable_citations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vector_agents, "CopilotClient", FakeClient)
    monkeypatch.setattr(vector_agents, "runtime_connection", lambda: object())
    index = FakeVectorIndex(tmp_path / "data")
    orchestrator = VectorOrchestrator(
        index.data_directory,
        "test-model",
        index=cast(vector_agents.VectorKnowledgeBase, index),
    )
    text_tool = UsageTextTool(["Evidence from the river. [S1]", "Rat met Mole. [S1]"])
    orchestrator.skills = VectorSkills(text_tool)

    result = await orchestrator.answer("What happened by the river?", lambda stage, detail: None)

    assert len(text_tool.prompts) == 2
    assert result.usage.calls == 2
    assert (result.usage.input_tokens, result.usage.output_tokens) == (20, 10)
    assert result.citation_map == {"S1": "story.md", "S2": "story.md"}
    assert result.citation_display_map == {
        "S1": "story.md — page 2, chunk 8",
        "S2": "story.md — page 3, chunk 9",
    }
    assert result.response.endswith(
        "Sources:\n- [S1] story.md — page 2, chunk 8\n- [S2] story.md — page 3, chunk 9"
    )


def test_prompt_budgets_adapt_without_weakening_citation_or_coverage_rules() -> None:
    broad_results = (
        VectorResult(
            "policy.pdf",
            "Speak up reports are confidential.",
            1.0,
            1,
            "S1",
            "page 3",
            ("reporting/speak-up",),
        ),
    )
    broad_query = "Summarize the employee code of conduct"

    evidence_prompt = render_evidence_request(broad_query, broad_results)
    synthesis_prompt = render_synthesis_request(
        broad_query,
        "Confidential reporting. [S1]",
        {"S1": "policy.pdf — page 3"},
    )
    targeted_prompt = render_synthesis_request(
        "What is the Speak Up process?",
        "Use the hotline. [S1]",
        {"S1": "policy.pdf — page 3"},
    )

    assert "1,100 words" in evidence_prompt
    assert "reporting/speak-up" in evidence_prompt
    assert "under 900 words" in synthesis_prompt
    assert "every retrieved topic family" in synthesis_prompt
    assert "under 300 words" in targeted_prompt
