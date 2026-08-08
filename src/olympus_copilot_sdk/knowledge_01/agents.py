from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from copilot import CopilotClient, RuntimeConnection
from copilot.session_events import AssistantUsageData, SessionEvent

from olympus_copilot_sdk.knowledge_01.lexical import KnowledgeBase
from olympus_copilot_sdk.knowledge_01.prompts import (
    HERCULES_SYSTEM_MESSAGE,
    ZEUS_SYSTEM_MESSAGE,
)
from olympus_copilot_sdk.knowledge_01.skills import (
    AgentSkills,
    EvidenceRequest,
    RetrievalBriefRequest,
    SynthesisRequest,
)
from olympus_copilot_sdk.knowledge_01.tools import AgentTools

Stage = Literal["zeus_thinking", "delegating", "hercules_working", "hercules_done", "zeus_final"]
StageCallback = Callable[[Stage, str], None]


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
    approach: str = "01_Knowledge"


def runtime_connection() -> RuntimeConnection:
    server_url = os.getenv("COPILOT_SERVER_URL")
    token = os.getenv("COPILOT_CONNECTION_TOKEN")
    if server_url:
        return RuntimeConnection.for_uri(server_url, connection_token=token)
    return RuntimeConnection.for_stdio(
        path=os.getenv("COPILOT_CLI_PATH") or shutil.which("copilot")
    )


class KnowledgeOrchestrator:
    def __init__(
        self,
        data_directory: Path,
        model: str,
        input_price_per_million: float = 0.0,
        output_price_per_million: float = 0.0,
    ) -> None:
        self.knowledge = KnowledgeBase(data_directory)
        self.model = model
        self.input_price = input_price_per_million
        self.output_price = output_price_per_million
        self.tools = AgentTools.defaults(self.knowledge)
        self.skills = AgentSkills(self.tools.text_generation)

    async def answer(self, query: str, on_stage: StageCallback) -> AgentResult:
        usage = Usage(model=self.model)
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
                for message in (ZEUS_SYSTEM_MESSAGE, HERCULES_SYSTEM_MESSAGE)
            ]
            zeus, hercules = sessions
            on_stage("zeus_thinking", "Zeus is preparing a lexical research brief.")
            delegation = await self.skills.create_brief(
                RetrievalBriefRequest(zeus, query, self.knowledge.summary.indexed_files)
            )
            on_stage("delegating", delegation)
            results = await self.tools.retrieval.execute(query)
            on_stage("hercules_working", f"Hercules is examining {len(results)} excerpts.")
            report = await self.skills.research(
                EvidenceRequest(hercules, query, delegation, results)
            )
            on_stage("hercules_done", report)
            on_stage("zeus_final", "Zeus is synthesizing the lexical baseline answer.")
            response = await self.skills.synthesize(SynthesisRequest(zeus, query, report))
        if not usage.has_sdk_cost:
            usage.cost = (
                usage.input_tokens * self.input_price + usage.output_tokens * self.output_price
            ) / 1_000_000
        return AgentResult(response, list(dict.fromkeys(item.source for item in results)), usage)

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
