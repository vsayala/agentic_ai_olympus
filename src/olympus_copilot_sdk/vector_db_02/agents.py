from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from copilot import CopilotClient, RuntimeConnection
from copilot.session_events import AssistantUsageData, SessionEvent

from olympus_copilot_sdk.vector_db_02.milvus import VectorKnowledgeBase
from olympus_copilot_sdk.vector_db_02.prompts import (
    system_messages,
)
from olympus_copilot_sdk.vector_db_02.retrieval import QueryMode, classify_query
from olympus_copilot_sdk.vector_db_02.skills import (
    AgentSkills,
    EvidenceRequest,
    SynthesisRequest,
)
from olympus_copilot_sdk.vector_db_02.tools import AgentTools

Stage = Literal["zeus_thinking", "delegating", "hercules_working", "hercules_done", "zeus_final"]
StageCallback = Callable[[Stage, str], None]


def _empty_citation_map() -> dict[str, str]:
    return {}


def _empty_topics() -> tuple[str, ...]:
    return ()


def _empty_topic_citations() -> dict[str, tuple[str, ...]]:
    return {}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    model: str = ""
    calls: int = 0
    has_sdk_cost: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class AgentResult:
    response: str
    sources: list[str]
    usage: Usage = field(default_factory=Usage)
    approach: str = "02_Vector_DB"
    citation_map: dict[str, str] = field(default_factory=_empty_citation_map)
    citation_display_map: dict[str, str] = field(default_factory=_empty_citation_map)
    query_mode: QueryMode = "targeted"
    expected_topics: tuple[str, ...] = field(default_factory=_empty_topics)
    topic_citation_map: dict[str, tuple[str, ...]] = field(default_factory=_empty_topic_citations)


def runtime_connection() -> RuntimeConnection:
    server_url = os.getenv("COPILOT_SERVER_URL")
    token = os.getenv("COPILOT_CONNECTION_TOKEN")
    if server_url:
        return RuntimeConnection.for_uri(server_url, connection_token=token)
    return RuntimeConnection.for_stdio(
        path=os.getenv("COPILOT_CLI_PATH") or shutil.which("copilot")
    )


async def list_available_models(working_directory: Path) -> list[tuple[str, str]]:
    async with CopilotClient(
        connection=runtime_connection(),
        working_directory=str(working_directory),
    ) as client:
        models = await client.list_models()
    return [
        (item.id, item.name)
        for item in models
        if item.policy is None or item.policy.state == "enabled"
    ]


class VectorOrchestrator:
    def __init__(
        self,
        data_directory: Path,
        model: str,
        input_price_per_million: float = 0.0,
        output_price_per_million: float = 0.0,
        *,
        index: VectorKnowledgeBase | None = None,
    ) -> None:
        self.knowledge = index or VectorKnowledgeBase(data_directory)
        self.model = model
        self.input_price = input_price_per_million
        self.output_price = output_price_per_million
        self.tools = AgentTools.defaults(self.knowledge)
        self.skills = AgentSkills(self.tools.text_generation)

    async def answer(self, query: str, on_stage: StageCallback) -> AgentResult:
        usage = Usage(model=self.model)
        mode = classify_query(query)
        async with CopilotClient(
            connection=runtime_connection(),
            working_directory=str(self.knowledge.data_directory.parent),
        ) as client:
            sessions = [
                await client.create_session(
                    model=self.model,
                    system_message={"mode": "replace", "content": message},
                    available_tools=[],
                    streaming=False,
                    on_event=lambda event: self._track_usage(event, usage),
                )
                for message in system_messages(mode)
            ]
            zeus, hercules = sessions
            on_stage("zeus_thinking", "Zeus is preparing hybrid retrieval.")
            on_stage("delegating", "Hercules is receiving the top fused evidence excerpts.")
            results = await self.tools.retrieval.execute(query)
            citation_map = {result.citation_id: result.source for result in results}
            citation_display_map = {result.citation_id: result.display_label for result in results}
            on_stage("hercules_working", f"Hercules is examining {len(results)} hybrid matches.")
            report = await self.skills.research(EvidenceRequest(hercules, query, results))
            on_stage("hercules_done", report)
            on_stage("zeus_final", "Zeus is synthesizing the vector-grounded answer.")
            response = await self.skills.synthesize(
                SynthesisRequest(zeus, query, report, citation_display_map)
            )
        if not usage.has_sdk_cost:
            usage.cost = (
                usage.input_tokens * self.input_price + usage.output_tokens * self.output_price
            ) / 1_000_000
        sources = list(dict.fromkeys(item.source for item in results))
        expected_topics = tuple(dict.fromkeys(topic for item in results for topic in item.topics))
        topic_citation_map = {
            topic: tuple(item.citation_id for item in results if topic in item.topics)
            for topic in expected_topics
        }
        return AgentResult(
            _with_source_legend(response, citation_display_map),
            sources,
            usage,
            citation_map=citation_map,
            citation_display_map=citation_display_map,
            query_mode=mode,
            expected_topics=expected_topics,
            topic_citation_map=topic_citation_map,
        )

    @staticmethod
    def _track_usage(event: SessionEvent, usage: Usage) -> None:
        if not isinstance(event.data, AssistantUsageData):
            return
        usage.input_tokens += event.data.input_tokens or 0
        usage.output_tokens += event.data.output_tokens or 0
        usage.model = event.data.model
        usage.calls += 1
        if event.data.cost is not None:
            usage.cost += event.data.cost
            usage.has_sdk_cost = True


def _with_source_legend(response: str, citation_map: dict[str, str]) -> str:
    if not citation_map:
        return response
    legend = "\n".join(f"- [{key}] {source}" for key, source in citation_map.items())
    return f"{response.rstrip()}\n\nSources:\n{legend}"
