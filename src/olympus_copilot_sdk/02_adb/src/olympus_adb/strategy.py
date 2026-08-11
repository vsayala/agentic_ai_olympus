from enum import StrEnum


class RetrievalStrategy(StrEnum):
    VECTOR_SEARCH = "vector_search"
    GENIE = "genie"
    MCP = "mcp"
