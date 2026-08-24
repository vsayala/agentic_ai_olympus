from __future__ import annotations

import importlib
import os
from collections.abc import Mapping
from typing import Protocol, cast

from olympus_copilot_sdk.foundry.host import HostDependencies
from olympus_copilot_sdk.foundry.runtime import (
    AgentFrameworkBridge,
    HostedRuntimeSettings,
    ZeusHostedAgent,
    azure_request_context,
    load_dependency_provider,
)


class Server(Protocol):
    def run(self) -> None: ...


class ServerFactory(Protocol):
    def __call__(self, agent: object) -> Server: ...


def build_agent(values: Mapping[str, str] | None = None) -> ZeusHostedAgent:
    settings = HostedRuntimeSettings.from_mapping(os.environ if values is None else values)
    dependencies = load_dependency_provider(settings.dependency_provider)()
    if not isinstance(dependencies, HostDependencies):
        raise RuntimeError("OLYMPUS_DEPENDENCY_PROVIDER must return HostDependencies")
    return ZeusHostedAgent(
        dependencies,
        settings.route,
        azure_request_context,
        AgentFrameworkBridge(),
    )


def main() -> None:
    hosting = importlib.import_module("agent_framework_foundry_hosting")
    server_factory = cast(ServerFactory, hosting.ResponsesHostServer)
    server_factory(build_agent()).run()


if __name__ == "__main__":
    main()
