from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterable, AsyncIterator, Awaitable
from dataclasses import dataclass, field
from types import ModuleType
from typing import cast

import pytest

from olympus_copilot_sdk.foundry import (
    AccessDecision,
    CallerContext,
    Evidence,
    HostDependencies,
    RetrievalOutcome,
    Route,
    SynthesisRequest,
    SynthesisResult,
)
from olympus_copilot_sdk.foundry.runtime import (
    HostedRuntimeSettings,
    ZeusHostedAgent,
    caller_from_context,
    extract_latest_user_text,
    load_dependency_provider,
)


@dataclass(frozen=True)
class FakeContext:
    user_id: str | None
    call_id: str | None


@dataclass(frozen=True)
class FakeMessage:
    role: str
    text: str


@dataclass
class FakeRetriever:
    calls: list[tuple[str, CallerContext]] = field(default_factory=lambda: [])

    def retrieve(self, prompt: str, caller: CallerContext) -> RetrievalOutcome:
        self.calls.append((prompt, caller))
        return RetrievalOutcome(
            AccessDecision.ALLOWED,
            (Evidence("document", "https://example.test/document", "fact", 1.0),),
        )


class FakeSynthesizer:
    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        return SynthesisResult(f"answer [{request.evidence[0].citation_id}]")


@dataclass
class FakeStream:
    updates: AsyncIterable[object]

    def __aiter__(self) -> AsyncIterator[object]:
        return self.updates.__aiter__()


class FakeBridge:
    def response(self, text: str) -> object:
        return ("response", text)

    def update(self, text: str) -> object:
        return ("update", text)

    def stream(self, updates: AsyncIterable[object]) -> object:
        return FakeStream(updates)

    def create_session(self, session_id: str | None = None) -> object:
        return {"session_id": session_id}

    def get_session(self, service_session_id: object, session_id: str | None = None) -> object:
        return {"service_session_id": service_session_id, "session_id": session_id}


def _agent(route: Route = Route.SHAREPOINT) -> tuple[ZeusHostedAgent, FakeRetriever, FakeRetriever]:
    hercules = FakeRetriever()
    hades = FakeRetriever()
    dependencies = HostDependencies(hercules, hades, FakeSynthesizer())
    agent = ZeusHostedAgent(
        dependencies,
        route,
        lambda: FakeContext("user-1", "opaque-call-id"),
        FakeBridge(),
    )
    return agent, hercules, hades


def test_extract_latest_user_text_ignores_newer_assistant_message() -> None:
    messages = [FakeMessage("user", "question"), FakeMessage("assistant", "old answer")]

    assert extract_latest_user_text(messages) == "question"


def test_agent_delegates_service_session_creation() -> None:
    agent, _, _ = _agent()

    assert agent.create_session(session_id="local") == {"session_id": "local"}
    assert agent.get_session("service", session_id="local") == {
        "service_session_id": "service",
        "session_id": "local",
    }


def test_hosted_settings_require_explicit_route_and_provider() -> None:
    with pytest.raises(RuntimeError, match="OLYMPUS_DEFAULT_ROUTE"):
        HostedRuntimeSettings.from_mapping({})
    with pytest.raises(RuntimeError, match="OLYMPUS_DEPENDENCY_PROVIDER"):
        HostedRuntimeSettings.from_mapping({"OLYMPUS_DEFAULT_ROUTE": "both"})


def test_caller_requires_both_platform_identity_values() -> None:
    assert caller_from_context(FakeContext("user-1", None)) is None
    assert caller_from_context(FakeContext(None, "call-1")) is None

    caller = caller_from_context(FakeContext("user-1", "opaque-call-id"))

    assert caller is not None
    assert caller.subject_id == "user-1"
    assert "opaque-call-id" not in repr(caller)
    assert "opaque-call-id" not in repr(caller.credential)


def test_non_streaming_request_uses_configured_route_and_renders_citations() -> None:
    agent, hercules, hades = _agent(Route.SHAREPOINT)

    async def invoke() -> object:
        return await cast(Awaitable[object], agent.run("question"))

    result = asyncio.run(invoke())

    assert result == (
        "response",
        "answer [S1]\n\nSources\n[S1] https://example.test/document",
    )
    assert len(hercules.calls) == 1
    assert hades.calls == []


def test_streaming_request_emits_one_governed_update() -> None:
    agent, _, _ = _agent()

    async def collect() -> list[object]:
        stream = cast(AsyncIterable[object], agent.run("question", stream=True))
        return [update async for update in stream]

    updates = asyncio.run(collect())

    assert updates == [("update", "answer [S1]\n\nSources\n[S1] https://example.test/document")]


def test_missing_platform_identity_fails_before_retrieval() -> None:
    agent, hercules, hades = _agent()
    agent = ZeusHostedAgent(
        agent._dependencies,  # pyright: ignore[reportPrivateUsage]
        Route.BOTH,
        lambda: FakeContext("user-1", None),
        FakeBridge(),
    )

    async def invoke() -> object:
        return await cast(Awaitable[object], agent.run("question"))

    result = asyncio.run(invoke())

    assert result == (
        "response",
        "A non-blank prompt and delegated caller identity are required.",
    )
    assert hercules.calls == []
    assert hades.calls == []


def test_dependency_provider_loads_only_named_callable() -> None:
    module = ModuleType("test_olympus_provider")
    module.build = lambda: None  # type: ignore[attr-defined]
    sys.modules[module.__name__] = module
    try:
        assert load_dependency_provider("test_olympus_provider:build") is module.build
        with pytest.raises(RuntimeError, match="module:function"):
            load_dependency_provider("test_olympus_provider")
        with pytest.raises(RuntimeError, match="callable"):
            load_dependency_provider("test_olympus_provider:missing")
    finally:
        del sys.modules[module.__name__]
