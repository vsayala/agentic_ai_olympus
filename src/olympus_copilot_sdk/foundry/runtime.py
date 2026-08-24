from __future__ import annotations

import asyncio
import importlib
from collections.abc import AsyncIterable, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Protocol, cast
from uuid import uuid4

from olympus_copilot_sdk.foundry.host import (
    CallerContext,
    FoundryCallContext,
    HostDependencies,
    HostRequest,
    HostResponse,
    Route,
    handle_request,
)


class RequestContext(Protocol):
    @property
    def call_id(self) -> str | None: ...

    @property
    def user_id(self) -> str | None: ...


class FrameworkBridge(Protocol):
    def response(self, text: str) -> object: ...

    def update(self, text: str) -> object: ...

    def stream(self, updates: AsyncIterable[object]) -> object: ...

    def create_session(self, session_id: str | None = None) -> object: ...

    def get_session(self, service_session_id: object, session_id: str | None = None) -> object: ...


DependencyProvider = Callable[[], object]
RequestContextProvider = Callable[[], RequestContext]


@dataclass(frozen=True)
class HostedRuntimeSettings:
    route: Route
    dependency_provider: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> HostedRuntimeSettings:
        route_text = values.get("OLYMPUS_DEFAULT_ROUTE", "").strip()
        provider = values.get("OLYMPUS_DEPENDENCY_PROVIDER", "").strip()
        if not route_text:
            raise RuntimeError("OLYMPUS_DEFAULT_ROUTE is required")
        if not provider:
            raise RuntimeError("OLYMPUS_DEPENDENCY_PROVIDER is required")
        try:
            route = Route(route_text)
        except ValueError as error:
            choices = ", ".join(item.value for item in Route)
            raise RuntimeError(f"OLYMPUS_DEFAULT_ROUTE must be one of: {choices}") from error
        return cls(route, provider)


class AgentFrameworkBridge:
    def __init__(self, framework: ModuleType | None = None) -> None:
        self._framework = framework or importlib.import_module("agent_framework")

    def response(self, text: str) -> object:
        message = self._framework.Message(
            role="assistant",
            contents=[self._framework.Content.from_text(text=text)],
        )
        return self._framework.AgentResponse(messages=[message])

    def update(self, text: str) -> object:
        return self._framework.AgentResponseUpdate(
            role="assistant",
            contents=[self._framework.Content.from_text(text=text)],
        )

    def stream(self, updates: AsyncIterable[object]) -> object:
        return self._framework.ResponseStream(
            updates,
            finalizer=self._framework.AgentResponse.from_updates,
        )

    def create_session(self, session_id: str | None = None) -> object:
        return self._framework.AgentSession(session_id=session_id)

    def get_session(self, service_session_id: object, session_id: str | None = None) -> object:
        return self._framework.AgentSession(
            service_session_id=service_session_id,
            session_id=session_id,
        )


class ZeusHostedAgent:
    id = "zeus"
    name = "Zeus"
    description = "Governed Olympus retrieval orchestrator"

    def __init__(
        self,
        dependencies: HostDependencies,
        route: Route,
        context_provider: RequestContextProvider,
        bridge: FrameworkBridge,
    ) -> None:
        self._dependencies = dependencies
        self._route = route
        self._context_provider = context_provider
        self._bridge = bridge

    def run(
        self,
        messages: object = None,
        *,
        stream: bool = False,
        session: object = None,
        function_invocation_kwargs: Mapping[str, object] | None = None,
        client_kwargs: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> Awaitable[object] | object:
        del session, function_invocation_kwargs, client_kwargs, kwargs
        if stream:
            return self._bridge.stream(self._run_stream(messages))
        return self._run(messages)

    def create_session(self, *, session_id: str | None = None) -> object:
        return self._bridge.create_session(session_id)

    def get_session(
        self,
        service_session_id: object,
        *,
        session_id: str | None = None,
    ) -> object:
        return self._bridge.get_session(service_session_id, session_id)

    async def _run(self, messages: object) -> object:
        response = await self._handle(messages)
        return self._bridge.response(_render_response(response))

    async def _run_stream(self, messages: object) -> AsyncIterable[object]:
        response = await self._handle(messages)
        yield self._bridge.update(_render_response(response))

    async def _handle(self, messages: object) -> HostResponse:
        prompt = extract_latest_user_text(messages)
        caller = caller_from_context(self._context_provider())
        request = HostRequest(uuid4().hex, prompt, self._route, caller)
        return await asyncio.to_thread(handle_request, request, self._dependencies)


def extract_latest_user_text(messages: object) -> str:
    if isinstance(messages, str):
        return messages
    if not isinstance(messages, Sequence) or isinstance(messages, (bytes, bytearray)):
        return _message_text(messages)
    sequence = cast(Sequence[object], messages)
    for message in reversed(sequence):
        role = str(getattr(message, "role", "")).lower()
        if role in {"user", "developer", "system", "assistant"} and role != "user":
            continue
        text = _message_text(message)
        if text:
            return text
    return ""


def caller_from_context(context: RequestContext) -> CallerContext | None:
    if not context.user_id or not context.call_id:
        return None
    return CallerContext(
        subject_id=context.user_id,
        tenant_id="foundry",
        credential=FoundryCallContext(context.call_id),
    )


def load_dependency_provider(specification: str) -> DependencyProvider:
    module_name, separator, attribute_name = specification.partition(":")
    if not separator or not module_name or not attribute_name:
        raise RuntimeError("OLYMPUS_DEPENDENCY_PROVIDER must use module:function syntax")
    module = importlib.import_module(module_name)
    provider = getattr(module, attribute_name, None)
    if not callable(provider):
        raise RuntimeError("OLYMPUS_DEPENDENCY_PROVIDER does not name a callable")
    return cast(DependencyProvider, provider)


def azure_request_context() -> RequestContext:
    core = importlib.import_module("azure.ai.agentserver.core")
    provider = cast(Callable[[], RequestContext], core.get_request_context)
    return provider()


def _message_text(message: object) -> str:
    if isinstance(message, str):
        return message
    text = getattr(message, "text", None)
    return text if isinstance(text, str) else ""


def _render_response(response: HostResponse) -> str:
    if not response.citations:
        return response.answer
    sources = "\n".join(
        f"[{citation.citation_id}] {citation.uri}" for citation in response.citations
    )
    return f"{response.answer}\n\nSources\n{sources}"
