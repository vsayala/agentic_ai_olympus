from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from copilot import CopilotClient, RuntimeConnection
from copilot.session_events import AssistantUsageData, SessionEvent

from olympus_copilot_sdk.vector_db_02.milvus import VectorKnowledgeBase
from olympus_copilot_sdk.vector_db_02.prompts import specialist_system_message, system_messages
from olympus_copilot_sdk.vector_db_02.retrieval import QueryMode, SearchResult, classify_query
from olympus_copilot_sdk.vector_db_02.router import SpecialistName, route_query
from olympus_copilot_sdk.vector_db_02.skills import (
    AgentSkills,
    EvidenceRequest,
    SynthesisRequest,
)
from olympus_copilot_sdk.vector_db_02.tools import AgentTools

Stage = Literal[
    "zeus_thinking",
    "delegating",
    "hercules_working",
    "hercules_done",
    "hades_working",
    "hades_done",
    "zeus_final",
]
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
    routing: tuple[str, ...] = field(default_factory=lambda: ("hercules",))


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
        secondary_data_directory: Path | None = None,
        secondary_index: VectorKnowledgeBase | None = None,
    ) -> None:
        self.knowledge = index or VectorKnowledgeBase(data_directory)
        self.secondary_knowledge = secondary_index or (
            VectorKnowledgeBase(secondary_data_directory)
            if secondary_data_directory is not None
            else None
        )
        self.model = model
        self.input_price = input_price_per_million
        self.output_price = output_price_per_million
        self.tools = AgentTools.defaults(self.knowledge)
        self.secondary_tools = (
            AgentTools.defaults(self.secondary_knowledge)
            if self.secondary_knowledge is not None
            else None
        )
        self.skills = AgentSkills(self.tools.text_generation)

    async def answer(self, query: str, on_stage: StageCallback) -> AgentResult:
        usage = Usage(model=self.model)
        mode = classify_query(query)
        specialist_tools: dict[SpecialistName, AgentTools] = {"hercules": self.tools}
        if self.secondary_tools is not None:
            specialist_tools["hades"] = self.secondary_tools
        retrieved = await asyncio.gather(
            *(tools.retrieval.execute(query) for tools in specialist_tools.values())
        )
        evidence = dict(zip(specialist_tools, retrieved, strict=True))
        routing = route_query(query, evidence)
        if not routing:
            return AgentResult(
                "I don't have enough relevant information in the indexed documents to answer "
                "that request.",
                [],
                usage,
                query_mode=mode,
                routing=(),
            )

        selected_results = _renumber_results(routing, evidence)
        async with CopilotClient(
            connection=runtime_connection(),
            working_directory=str(self.knowledge.data_directory.parent),
        ) as client:
            zeus = await client.create_session(
                model=self.model,
                system_message={"mode": "replace", "content": system_messages(mode)[0]},
                available_tools=[],
                streaming=False,
                on_event=lambda event: self._track_usage(event, usage),
            )
            on_stage("zeus_thinking", "Zeus is preparing hybrid retrieval.")
            on_stage("delegating", f"Zeus routed the request to {', '.join(routing)}.")
            evidence_reports: list[str] = []
            for specialist in routing:
                results = selected_results[specialist]
                session = await client.create_session(
                    model=self.model,
                    system_message={
                        "mode": "replace",
                        "content": specialist_system_message(specialist, mode),
                    },
                    available_tools=[],
                    streaming=False,
                    on_event=lambda event: self._track_usage(event, usage),
                )
                working_stage: Stage = (
                    "hercules_working" if specialist == "hercules" else "hades_working"
                )
                done_stage: Stage = "hercules_done" if specialist == "hercules" else "hades_done"
                on_stage(
                    working_stage,
                    f"{specialist.title()} is examining {len(results)} matches.",
                )
                report = await self.skills.research(EvidenceRequest(session, query, results))
                evidence_reports.append(f"{specialist.upper()} REPORT:\n{report}")
                on_stage(done_stage, report)
            all_results = tuple(
                result for results in selected_results.values() for result in results
            )
            citation_map = {result.citation_id: result.source for result in all_results}
            citation_display_map = {
                result.citation_id: result.display_label for result in all_results
            }
            on_stage("zeus_final", "Zeus is synthesizing the vector-grounded answer.")
            response = await self.skills.synthesize(
                SynthesisRequest(zeus, query, "\n\n".join(evidence_reports), citation_display_map)
            )
        if not usage.has_sdk_cost:
            usage.cost = (
                usage.input_tokens * self.input_price + usage.output_tokens * self.output_price
            ) / 1_000_000
        sources = list(dict.fromkeys(item.source for item in all_results))
        expected_topics = tuple(
            dict.fromkeys(topic for item in all_results for topic in item.topics)
        )
        topic_citation_map = {
            topic: tuple(item.citation_id for item in all_results if topic in item.topics)
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
            routing=routing,
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


def _renumber_results(
    routing: tuple[SpecialistName, ...],
    evidence: dict[SpecialistName, tuple[SearchResult, ...]],
) -> dict[SpecialistName, tuple[SearchResult, ...]]:
    citation_number = 1
    selected: dict[SpecialistName, tuple[SearchResult, ...]] = {}
    for specialist in routing:
        numbered: list[SearchResult] = []
        for result in evidence[specialist]:
            numbered.append(replace(result, citation_id=f"S{citation_number}"))
            citation_number += 1
        selected[specialist] = tuple(numbered)
    return selected


def _with_source_legend(response: str, citation_map: dict[str, str]) -> str:
    if not citation_map:
        return response
    legend = "\n".join(f"- [{key}] {source}" for key, source in citation_map.items())
    return f"{response.rstrip()}\n\nSources:\n{legend}"
