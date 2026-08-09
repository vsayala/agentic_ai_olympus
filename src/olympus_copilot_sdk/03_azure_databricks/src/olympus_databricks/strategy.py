from __future__ import annotations

from enum import StrEnum

from olympus_databricks.config import SourceConfig


class RetrievalStrategy(StrEnum):
    AI_SEARCH = "ai_search"
    GENIE = "genie"
    EXTERNAL_MCP = "external_mcp"


def retrieval_strategy(config: SourceConfig) -> RetrievalStrategy:
    if config.kind == "files":
        return RetrievalStrategy.AI_SEARCH
    if config.kind == "api":
        return RetrievalStrategy.GENIE
    if config.kind == "mcp":
        return RetrievalStrategy.EXTERNAL_MCP
    raise ValueError(f"Unsupported source kind: {config.kind!r}")
